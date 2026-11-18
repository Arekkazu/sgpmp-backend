# | Fecha      | Nombre      | Que se hizo |
# |------------|-------------|-------------|
# | 2026-11-17 | Laura López | E3.2/E3.3 contra PostgreSQL Docker local aislado (sin TEST). |
"""Crea BD temporal local, aplica esquema mínimo RF-102 y ejecuta E3.2 / E3.3.

Usa contenedor Docker ``infra-db-1`` (127.0.0.1:5433). No usa api.inmero ni BD TEST.
No aplica el historial Alembic completo (dependencias de roles/extensiones/módulos);
el DDL de ENUM+PK se toma de la migración 94b14a6931d6.

    python tests/Test_Testing/Test_Modulo7/RF-102/TC-M07-G052/_ejecutar_e3_postgres_aislada.py
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

CARPETA = Path(__file__).resolve().parent
RESULTADO = CARPETA / "Resultado"
SQL_SCHEMA = CARPETA / "_sql_schema_e3_aislada.sql"
EV_E32 = RESULTADO / "evidencia_e3_2_duplicado_uuid_TC-M07-G52.json"
EV_E33 = RESULTADO / "evidencia_e3_3_tipo_no_catalogado_TC-M07-G52.json"
EV_DIAG = RESULTADO / "diagnostico_postgres_aislada_TC-M07-G52.json"

CONTAINER = "infra-db-1"
DB_NAME = "sgpmp_g052_e3_tmp"
HASH_OK = "a" * 64
UUID_DUP = "22222222-2222-4222-8222-222222222252"
TIPO_INVALIDO = "TIPO_NO_CATALOGADO_QA_G52"
MIGRACION = "94b14a6931d6_m07_integracion_aaef_rfc017.py"


def ahora() -> str:
    return datetime.now(timezone.utc).isoformat()


def docker_psql(sql: str, db: str = "postgres", tuples_only: bool = False) -> subprocess.CompletedProcess:
    cmd = ["docker", "exec", "-i", CONTAINER, "psql", "-U", "postgres", "-d", db, "-v", "ON_ERROR_STOP=1"]
    if tuples_only:
        cmd.extend(["-t", "-A"])
    return subprocess.run(cmd, input=sql, text=True, capture_output=True)


def docker_psql_file(path: Path, db: str) -> subprocess.CompletedProcess:
    # Evita docker cp (falla con rutas OneDrive en este host): pipe por stdin.
    sql = path.read_text(encoding="utf-8")
    return docker_psql(sql, db=db)


def clasificar_error(stderr: str, stdout: str) -> dict:
    texto = (stderr or "") + "\n" + (stdout or "")
    out = {
        "sqlstate": None,
        "es_unique_violation": False,
        "es_invalid_enum": False,
        "es_conexion": False,
        "es_permiso": False,
        "es_estructura": False,
        "mensaje": texto.strip()[:1200],
    }
    # PostgreSQL suele imprimir ERROR: ... / DETAIL
    if "Connection refused" in texto or "could not connect" in texto.lower():
        out["es_conexion"] = True
    if "permission denied" in texto.lower():
        out["es_permiso"] = True
    if "does not exist" in texto.lower() and ("relation" in texto.lower() or "type" in texto.lower() or "schema" in texto.lower()):
        out["es_estructura"] = True
    if "unique" in texto.lower() or "duplicate key" in texto.lower() or "eventos_integracion_pkey" in texto:
        out["es_unique_violation"] = True
        out["sqlstate"] = "23505"
    if "invalid input value for enum" in texto.lower() or "enum_evento_integracion_tipo_evento" in texto:
        out["es_invalid_enum"] = True
        out["sqlstate"] = out["sqlstate"] or "22P02"
    return out


def insert_sql(uuid_val: str, tipo: str) -> str:
    return f"""
INSERT INTO modulo7.eventos_integracion (
  id_evento_integracion, tipo_evento, severidad, tipo_actor, modulo,
  fecha_evento, fecha_registro, hash_integridad
) VALUES (
  '{uuid_val}'::uuid,
  '{tipo}'::modulo7.enum_evento_integracion_tipo_evento,
  'INFO'::modulo7.enum_evento_integracion_severidad,
  'SISTEMA'::modulo7.enum_evento_integracion_tipo_actor,
  'M07',
  now(), now(),
  '{HASH_OK}'
);
"""


def main() -> int:
    RESULTADO.mkdir(parents=True, exist_ok=True)
    diagnostico = {
        "fecha_utc": ahora(),
        "objetivo": "E3.2 PK + E3.3 ENUM en PostgreSQL local aislado",
        "prohibido": "INSERT en BD TEST / api.inmero",
        "container": CONTAINER,
        "host_port": "127.0.0.1:5433",
        "db_temporal": DB_NAME,
        "migracion_origen_ddl": MIGRACION,
        "alembic_upgrade_completo": False,
        "motivo_no_alembic_completo": (
            "El historial Alembic de SGPMP requiere roles (sgpmp_app/owner), extensiones "
            "(p.ej. pg_cron), schemas previos (modulo1..modulo9) y cientos de revisiones. "
            "Para E3.2/E3.3 se aplicó DDL mínimo equivalente a la migración RF-102 "
            "(ENUM + PRIMARY KEY + FKs con stubs), sin modificar archivos de migración."
        ),
        "pasos": [],
        "viable": False,
    }

    # 1) Contenedor disponible
    probe = subprocess.run(["docker", "inspect", "-f", "{{.State.Running}}", CONTAINER], capture_output=True, text=True)
    if probe.returncode != 0 or probe.stdout.strip() != "true":
        diagnostico["pasos"].append({"paso": "probe_container", "ok": False, "detalle": probe.stderr or probe.stdout})
        diagnostico["dependencia_faltante"] = f"Contenedor Docker {CONTAINER} no está en ejecución"
        EV_DIAG.write_text(json.dumps(diagnostico, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(diagnostico, ensure_ascii=False, indent=2))
        return 2
    diagnostico["pasos"].append({"paso": "probe_container", "ok": True})

    # 2) Crear BD temporal (drop if exists para corrida limpia)
    drop = docker_psql(f"DROP DATABASE IF EXISTS {DB_NAME} WITH (FORCE);")
    create = docker_psql(f"CREATE DATABASE {DB_NAME};")
    diagnostico["pasos"].append({
        "paso": "create_database",
        "ok": create.returncode == 0,
        "stdout": (create.stdout or "")[:400],
        "stderr": (create.stderr or "")[:400],
    })
    if create.returncode != 0:
        diagnostico["dependencia_faltante"] = "No se pudo CREATE DATABASE en Postgres local Docker"
        EV_DIAG.write_text(json.dumps(diagnostico, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(diagnostico, ensure_ascii=False, indent=2))
        return 2

    # 3) Aplicar esquema
    schema = docker_psql_file(SQL_SCHEMA, DB_NAME)
    diagnostico["pasos"].append({
        "paso": "apply_schema_minimo_rf102",
        "ok": schema.returncode == 0,
        "archivo": SQL_SCHEMA.name,
        "stdout": (schema.stdout or "")[:800],
        "stderr": (schema.stderr or "")[:800],
    })
    if schema.returncode != 0:
        diagnostico["dependencia_faltante"] = "Falló la aplicación del DDL mínimo"
        EV_DIAG.write_text(json.dumps(diagnostico, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(diagnostico, ensure_ascii=False, indent=2))
        return 2

    # Verificar constraints
    ver = docker_psql(
        """
        SELECT c.conname, c.contype
        FROM pg_constraint c
        JOIN pg_class t ON t.oid = c.conrelid
        JOIN pg_namespace n ON n.oid = t.relnamespace
        WHERE n.nspname='modulo7' AND t.relname='eventos_integracion'
        ORDER BY c.conname;
        """,
        db=DB_NAME,
    )
    enum_vals = docker_psql(
        "SELECT enumlabel FROM pg_enum e JOIN pg_type t ON t.oid=e.enumtypid "
        "JOIN pg_namespace n ON n.oid=t.typnamespace "
        "WHERE n.nspname='modulo7' AND t.typname='enum_evento_integracion_tipo_evento' ORDER BY enumsortorder;",
        db=DB_NAME,
    )
    diagnostico["pasos"].append({
        "paso": "verify_constraints",
        "ok": ver.returncode == 0 and "eventos_integracion_pkey" in (ver.stdout or ""),
        "constraints": ver.stdout,
        "enum_sample": (enum_vals.stdout or "")[:500],
    })
    diagnostico["viable"] = True
    diagnostico["esquema_aplicado"] = [
        "CREATE SCHEMA modulo1/modulo7 (stubs)",
        "CREATE TYPE modulo7.enum_evento_integracion_tipo_evento (desde _TIPOS_EVENTO de 94b14a6931d6)",
        "CREATE TYPE severidad/tipo_actor",
        "CREATE TABLE modulo7.eventos_integracion con PRIMARY KEY id_evento_integracion",
    ]

    # ---- E3.2 ----
    e32 = {
        "escenario": "E3.2",
        "caso": "TC-M07-G052",
        "fecha_utc": ahora(),
        "bd": DB_NAME,
        "container": CONTAINER,
        "uuid_ficticio": UUID_DUP,
        "funcion_evaluada": "CONSTRAINT eventos_integracion_pkey PRIMARY KEY (id_evento_integracion)",
        "migracion_origen": MIGRACION,
        "entrada": {"id_evento_integracion": UUID_DUP, "tipo_evento": "CONTRATO_ACTIVADO", "intentos": 2},
        "esperado": "Primer INSERT OK; segundo INSERT rechazado por unique/PK (SQLSTATE 23505)",
        "pasos": [],
        "estado": "BLOQUEADO",
    }
    first = docker_psql(insert_sql(UUID_DUP, "CONTRATO_ACTIVADO"), db=DB_NAME)
    e32["pasos"].append({
        "intento": 1,
        "ok": first.returncode == 0,
        "stdout": (first.stdout or "")[:300],
        "stderr": (first.stderr or "")[:300],
        "error": clasificar_error(first.stderr or "", first.stdout or ""),
    })
    second = docker_psql(insert_sql(UUID_DUP, "CONTRATO_ACTIVADO"), db=DB_NAME)
    err2 = clasificar_error(second.stderr or "", second.stdout or "")
    e32["pasos"].append({
        "intento": 2,
        "ok": second.returncode == 0,
        "stdout": (second.stdout or "")[:300],
        "stderr": (second.stderr or "")[:500],
        "error": err2,
    })
    count = docker_psql(
        f"SELECT count(*) FROM modulo7.eventos_integracion WHERE id_evento_integracion = '{UUID_DUP}';",
        db=DB_NAME,
        tuples_only=True,
    )
    filas = (count.stdout or "").strip()
    e32["filas_con_uuid"] = filas
    e32["obtenido"] = {
        "primer_insert_ok": first.returncode == 0,
        "segundo_insert_ok": second.returncode == 0,
        "rechazo_pk": err2["es_unique_violation"],
        "sqlstate": err2["sqlstate"],
        "confusion_conexion": err2["es_conexion"],
        "confusion_permiso": err2["es_permiso"],
        "confusion_estructura": err2["es_estructura"],
        "filas": filas,
    }
    if (
        first.returncode == 0
        and second.returncode != 0
        and err2["es_unique_violation"]
        and not err2["es_conexion"]
        and not err2["es_permiso"]
        and not err2["es_estructura"]
        and filas == "1"
    ):
        e32["estado"] = "APROBADO"
    elif first.returncode != 0 or err2["es_conexion"] or err2["es_estructura"]:
        e32["estado"] = "BLOQUEADO"
    else:
        e32["estado"] = "RECHAZADO"

    # ---- E3.3 ----
    e33 = {
        "escenario": "E3.3",
        "caso": "TC-M07-G052",
        "fecha_utc": ahora(),
        "bd": DB_NAME,
        "container": CONTAINER,
        "tipo_ficticio": TIPO_INVALIDO,
        "uuid_ficticio": "33333333-3333-4333-8333-333333333353",
        "funcion_evaluada": "CAST / columna tipo_evento modulo7.enum_evento_integracion_tipo_evento",
        "migracion_origen": MIGRACION,
        "entrada": {"tipo_evento": TIPO_INVALIDO},
        "esperado": "INSERT rechazado por enum inválido (invalid input value for enum / SQLSTATE 22P02)",
        "pasos": [],
        "estado": "BLOQUEADO",
    }
    bad = docker_psql(insert_sql(e33["uuid_ficticio"], TIPO_INVALIDO), db=DB_NAME)
    err3 = clasificar_error(bad.stderr or "", bad.stdout or "")
    e33["pasos"].append({
        "intento": 1,
        "ok": bad.returncode == 0,
        "stdout": (bad.stdout or "")[:300],
        "stderr": (bad.stderr or "")[:800],
        "error": err3,
    })
    # control positivo: tipo válido distinto UUID
    ctrl_uuid = "44444444-4444-4444-8444-444444444454"
    ctrl = docker_psql(insert_sql(ctrl_uuid, "TOKEN_CANAL_RECHAZADO"), db=DB_NAME)
    e33["pasos"].append({
        "control_tipo_valido": "TOKEN_CANAL_RECHAZADO",
        "ok": ctrl.returncode == 0,
        "stdout": (ctrl.stdout or "")[:200],
        "stderr": (ctrl.stderr or "")[:200],
    })
    count_bad = docker_psql(
        f"SELECT count(*) FROM modulo7.eventos_integracion WHERE id_evento_integracion = '{e33['uuid_ficticio']}';",
        db=DB_NAME,
        tuples_only=True,
    )
    e33["filas_con_uuid_invalido"] = (count_bad.stdout or "").strip()
    e33["obtenido"] = {
        "insert_invalido_ok": bad.returncode == 0,
        "rechazo_enum": err3["es_invalid_enum"],
        "sqlstate": err3["sqlstate"],
        "confusion_conexion": err3["es_conexion"],
        "confusion_permiso": err3["es_permiso"],
        "confusion_estructura": err3["es_estructura"],
        "control_valido_ok": ctrl.returncode == 0,
        "filas_invalidas": e33["filas_con_uuid_invalido"],
    }
    if (
        bad.returncode != 0
        and err3["es_invalid_enum"]
        and not err3["es_conexion"]
        and not err3["es_permiso"]
        and not err3["es_estructura"]
        and e33["filas_con_uuid_invalido"] == "0"
        and ctrl.returncode == 0
    ):
        e33["estado"] = "APROBADO"
    elif err3["es_conexion"] or err3["es_estructura"] or err3["es_permiso"]:
        e33["estado"] = "BLOQUEADO"
    else:
        e33["estado"] = "RECHAZADO"

    diagnostico["resultado_e3_2"] = e32["estado"]
    diagnostico["resultado_e3_3"] = e33["estado"]
    diagnostico["nota_estado_caso"] = (
        "No se modifica el estado general de TC-M07-G052 en este paso; solo evidencias E3.2/E3.3."
    )

    # Cleanup BD temporal
    cleanup = docker_psql(f"DROP DATABASE IF EXISTS {DB_NAME} WITH (FORCE);")
    diagnostico["pasos"].append({
        "paso": "drop_database_temporal",
        "ok": cleanup.returncode == 0,
        "stderr": (cleanup.stderr or "")[:300],
    })

    EV_E32.write_text(json.dumps(e32, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    EV_E33.write_text(json.dumps(e33, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    EV_DIAG.write_text(json.dumps(diagnostico, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({
        "viable": diagnostico["viable"],
        "db_temporal_creada": True,
        "alembic_completo": False,
        "ddl_origen": MIGRACION,
        "E3.2": e32["estado"],
        "E3.3": e33["estado"],
        "evidencias": [EV_DIAG.name, EV_E32.name, EV_E33.name],
        "estado_caso_agrupado": "SIN CAMBIO (pedido explícito)",
    }, ensure_ascii=False, indent=2))
    return 0 if e32["estado"] == "APROBADO" and e33["estado"] == "APROBADO" else 1


if __name__ == "__main__":
    raise SystemExit(main())
