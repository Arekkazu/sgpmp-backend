# | Fecha      | Nombre      | Que se hizo |
# |------------|-------------|-------------|
# | 2026-11-17 | Laura López | G053 E2 corrupción + E3 triggers en Postgres Docker aislado. |
"""PostgreSQL aislado (infra-db-1) para E2/E3 de TC-M07-G053. No usa TEST.

    python tests/Test_Testing/Test_Modulo7/RF-102/TC-M07-G053/_ejecutar_postgres_aislada_g53.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

CARPETA = Path(__file__).resolve().parent
RESULTADO = CARPETA / "Resultado"
SQL_SCHEMA = CARPETA / "_sql_schema_g53_aislada.sql"
EV_E2 = RESULTADO / "evidencia_e2_corrupcion_TC-M07-G053.json"
EV_E3 = RESULTADO / "evidencia_e3_inmutabilidad_sql_TC-M07-G053.json"
EV_DIAG = RESULTADO / "diagnostico_postgres_aislada_TC-M07-G053.json"
REPO = CARPETA.parents[4]

CONTAINER = "infra-db-1"
DB_NAME = "sgpmp_g053_e_tmp"
UUID_OK = "66666666-6666-4666-8666-666666666663"
UUID_BAD = "77777777-7777-4777-8777-777777777773"


def ahora() -> str:
    return datetime.now(timezone.utc).isoformat()


def docker_psql(sql: str, db: str = "postgres") -> subprocess.CompletedProcess:
    # Windows: text=True reencoda stdin en cp1252 y rompe UTF-8 (acentos) hacia psql.
    return subprocess.run(
        ["docker", "exec", "-i", CONTAINER, "psql", "-U", "postgres", "-d", db, "-v", "ON_ERROR_STOP=1"],
        input=sql.encode("utf-8"),
        capture_output=True,
    )


def _txt(data: bytes | str | None) -> str:
    if data is None:
        return ""
    if isinstance(data, bytes):
        return data.decode("utf-8", "replace")
    return data


def clasificar(stderr: bytes | str, stdout: bytes | str = "") -> dict:
    t = (_txt(stderr) + "\n" + _txt(stdout)).strip()
    return {
        "mensaje": t[:1000],
        "es_inmutable_trigger": "TGR-M07-14" in t or "inmutable" in t.lower(),
        "es_conexion": "could not connect" in t.lower() or "connection refused" in t.lower(),
        "es_estructura": "does not exist" in t.lower(),
    }


def main() -> int:
    RESULTADO.mkdir(parents=True, exist_ok=True)
    # Import hash helpers with dummy env (no conexión real)
    env = os.environ.copy()
    env.setdefault("SECRET_KEY", "test-g53")
    env.setdefault("DATABASE_URL", "postgresql://g53:g53@127.0.0.1:5432/g53_no_usar")
    env["PYTHONPATH"] = str(REPO / "_win_fcntl_stub_borrar") + os.pathsep + str(REPO)
    # Ejecutar lógica de hash en proceso actual si posible
    sys.path.insert(0, str(REPO / "_win_fcntl_stub_borrar"))
    sys.path.insert(0, str(REPO))
    os.environ.setdefault("SECRET_KEY", env["SECRET_KEY"])
    os.environ.setdefault("DATABASE_URL", env["DATABASE_URL"])

    from src.accounting_integration.domain.entities.evento_integracion import EventoIntegracion
    from src.accounting_integration.application.use_cases.auditoria.consultar_auditoria_integracion_use_case import (
        ConsultarAuditoriaIntegracionUseCase,
    )
    from unittest.mock import MagicMock
    from datetime import datetime as dt, timezone as tz

    AHORA = dt(2026, 11, 17, 21, 0, tzinfo=tz.utc)
    diag = {"fecha_utc": ahora(), "container": CONTAINER, "db": DB_NAME, "alembic_completo": False,
            "ddl": SQL_SCHEMA.name, "migracion_origen": "94b14a6931d6", "pasos": [], "viable": False}

    probe = subprocess.run(["docker", "inspect", "-f", "{{.State.Running}}", CONTAINER], capture_output=True, text=True)
    if probe.stdout.strip() != "true":
        diag["dependencia"] = f"Contenedor {CONTAINER} no disponible"
        EV_DIAG.write_text(json.dumps(diag, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"viable": False, **diag}, ensure_ascii=False, indent=2))
        return 2

    docker_psql(f"DROP DATABASE IF EXISTS {DB_NAME} WITH (FORCE);")
    create = docker_psql(f"CREATE DATABASE {DB_NAME};")
    diag["pasos"].append({"paso": "create_db", "ok": create.returncode == 0})
    if create.returncode != 0:
        EV_DIAG.write_text(json.dumps(diag, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return 2

    schema = docker_psql(SQL_SCHEMA.read_text(encoding="utf-8"), db=DB_NAME)
    diag["pasos"].append({"paso": "schema", "ok": schema.returncode == 0, "stderr": _txt(schema.stderr)[:400]})
    if schema.returncode != 0:
        EV_DIAG.write_text(json.dumps(diag, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return 2
    diag["viable"] = True

    # --- E1 aislado: INSERT con hash correcto y recalcular ---
    ev_ok = EventoIntegracion(
        tipo_evento="CONTRATO_ACTIVADO", version_contrato="3.0",
        fecha_evento=AHORA, fecha_registro=AHORA, id_evento_integracion=UUID_OK,
    )
    hash_ok = ev_ok.hash_integridad
    ins_ok = docker_psql(f"""
INSERT INTO modulo7.eventos_integracion (
  id_evento_integracion, tipo_evento, severidad, tipo_actor, modulo,
  fecha_evento, fecha_registro, version_contrato, hash_integridad
) VALUES (
  '{UUID_OK}', 'CONTRATO_ACTIVADO', 'INFO', 'SISTEMA', 'M07',
  '{AHORA.isoformat()}', '{AHORA.isoformat()}', '3.0', '{hash_ok}'
);
""", db=DB_NAME)
    sel = docker_psql(
        f"SELECT hash_integridad FROM modulo7.eventos_integracion WHERE id_evento_integracion='{UUID_OK}';",
        db=DB_NAME,
    )
    hash_db = ""
    for line in _txt(sel.stdout).splitlines():
        line = line.strip()
        if len(line) == 64 and all(c in "0123456789abcdef" for c in line):
            hash_db = line
            break
    e1_aislada = {
        "insert_ok": ins_ok.returncode == 0,
        "hash_python": hash_ok,
        "hash_db": hash_db,
        "coinciden": hash_ok == hash_db and bool(hash_db),
    }

    # --- E2: INSERT con hash incorrecto (sin UPDATE) + detección _presentar ---
    hash_malo = "a" * 64
    assert hash_malo != hash_ok
    ins_bad = docker_psql(f"""
INSERT INTO modulo7.eventos_integracion (
  id_evento_integracion, tipo_evento, severidad, tipo_actor, modulo,
  fecha_evento, fecha_registro, version_contrato, hash_integridad
) VALUES (
  '{UUID_BAD}', 'CONTRATO_ACTIVADO', 'INFO', 'SISTEMA', 'M07',
  '{AHORA.isoformat()}', '{AHORA.isoformat()}', '3.0', '{hash_malo}'
);
""", db=DB_NAME)
    ev_bad = EventoIntegracion(
        tipo_evento="CONTRATO_ACTIVADO", version_contrato="3.0",
        fecha_evento=AHORA, fecha_registro=AHORA, id_evento_integracion=UUID_BAD,
    )
    alertas = []
    uc = ConsultarAuditoriaIntegracionUseCase(MagicMock(), lambda m, d: alertas.append({"mensaje": m, "detalle": d}))
    presentado = uc._presentar([(ev_bad, hash_malo, {})], restringida=False)
    e2 = {
        "escenario": "E2",
        "fecha_utc": ahora(),
        "metodo": "INSERT con hash_integridad deliberadamente incorrecto + _presentar (sin UPDATE; triggers lo impedirían)",
        "uuid": UUID_BAD,
        "hash_contenido_recalculado": ev_bad.hash_integridad,
        "hash_almacenado_falso": hash_malo,
        "insert_ok": ins_bad.returncode == 0,
        "integridad": presentado[0]["integridad"],
        "alerta_generada": bool(alertas),
        "alerta": alertas[:1],
        "estado": "APROBADO" if (
            ins_bad.returncode == 0 and presentado[0]["integridad"] == "CORRUPTO" and alertas
        ) else "RECHAZADO",
    }

    # --- E3 SQL: UPDATE / DELETE / TRUNCATE ---
    upd = docker_psql(
        f"UPDATE modulo7.eventos_integracion SET version_contrato='9.9' WHERE id_evento_integracion='{UUID_OK}';",
        db=DB_NAME,
    )
    dele = docker_psql(
        f"DELETE FROM modulo7.eventos_integracion WHERE id_evento_integracion='{UUID_OK}';",
        db=DB_NAME,
    )
    trunc = docker_psql("TRUNCATE modulo7.eventos_integracion;", db=DB_NAME)
    cnt = docker_psql(
        f"SELECT count(*) FROM modulo7.eventos_integracion WHERE id_evento_integracion='{UUID_OK}';",
        db=DB_NAME,
    )
    cnt_out = _txt(cnt.stdout)
    filas_ok = "1" if "1" in cnt_out else cnt_out.strip()
    e3 = {
        "escenario": "E3_SQL",
        "fecha_utc": ahora(),
        "update": {"ok": upd.returncode == 0, **clasificar(upd.stderr, upd.stdout)},
        "delete": {"ok": dele.returncode == 0, **clasificar(dele.stderr, dele.stdout)},
        "truncate": {"ok": trunc.returncode == 0, **clasificar(trunc.stderr, trunc.stdout)},
        "filas_uuid_ok_tras_intentos": filas_ok,
        "estado": "APROBADO" if (
            upd.returncode != 0 and dele.returncode != 0 and trunc.returncode != 0
            and clasificar(upd.stderr)["es_inmutable_trigger"]
            and clasificar(dele.stderr)["es_inmutable_trigger"]
            and clasificar(trunc.stderr)["es_inmutable_trigger"]
            and "1" in cnt_out
        ) else "RECHAZADO",
    }

    docker_psql(f"DROP DATABASE IF EXISTS {DB_NAME} WITH (FORCE);")
    diag["pasos"].append({"paso": "drop_db", "ok": True})
    diag["e1_aislada_hash"] = e1_aislada
    diag["resultado_e2"] = e2["estado"]
    diag["resultado_e3_sql"] = e3["estado"]

    EV_E2.write_text(json.dumps(e2, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    EV_E3.write_text(json.dumps(e3, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    EV_DIAG.write_text(json.dumps(diag, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "viable": True,
        "e1_hash_coincide": e1_aislada["coinciden"],
        "E2": e2["estado"],
        "E3_SQL": e3["estado"],
    }, ensure_ascii=False, indent=2))
    return 0 if e2["estado"] == "APROBADO" and e3["estado"] == "APROBADO" and e1_aislada["coinciden"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
