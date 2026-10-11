"""TC-M09-274 — SEGUNDA EVALUACIÓN. Auditoría best-effort del rechazo de calibración.

RF-24 v2.0 · CU05 — Gestionar Dispositivos IoT, Flujo D · Grupo TC-M09-G136.

Reevaluación del test de la primera evaluación (`TC-M09-G136/test_tc_m09_274.py`). Se reutiliza
íntegro su laboratorio y su oráculo; lo único que cambia es lo indispensable:

  * las rutas, porque el test vive ahora en `EvaluacionV2/automation/` y los artefactos se
    escriben en `EvaluacionV2/RESULTADOS/<RUN_ID>/`;
  * los nombres de la instancia del laboratorio (proyecto, contenedores, volumen y puertos),
    para no compartir volumen con el laboratorio de la primera evaluación;
  * se registra el commit y la cabeza de Alembic del código REEVALUADO, no del baseline;
  * se verifica contra el código ACTUAL que la tabla de RF-10 sigue siendo `modulo1.eventos`
    antes de inducir el fallo;
  * se emite `automation_manifest.json` con la función y el SHA-256 de cada artefacto usado.

PRUEBA LOCAL. Laboratorio aislado con PostgreSQL real y backend HTTP real. Sin dobles: no hay
DbFake, ni repositorios falsos, ni SQLite, ni mock del repositorio de eventos, ni monkeypatch
que lance una excepción artificial. El fallo proviene de PostgreSQL negando
`INSERT INTO modulo1.eventos` al rol real de la aplicación.

Lo que debe demostrarse:

    REVOKE INSERT modulo1.eventos  (único fallo inducido)
    -> rechazo por valor fuera de rango  -> sigue siendo HTTP 400, nunca 500
    -> rechazo por dispositivo inactivo  -> sigue siendo HTTP 422, nunca 500
    en ambos: ninguna calibración creada, el evento RF-10 realmente no se escribe
    y queda una constancia observable del fallo de auditoría, una por intento.

El token del Ingeniero se obtiene ANTES del REVOKE: el login escribe auditoría RF-10 y
contaminaría el fault injection. La restauración de privilegios va en `finally`.

Uso:
    pytest test_g136_v2.py -v --noconftest --junitxml=<RESULTADOS/RUN_ID>/pytest.xml
con el laboratorio ya levantado (ver el encabezado de docker-compose.g136-v2.yml).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

import psycopg2
import psycopg2.extras
import pytest
import requests

# Guard de carpeta: este test vive en EvaluacionV2/automation del grupo oficial.
FOLDER = "TC-M09-G136"
BASE_DIR = Path(__file__).resolve().parent          # .../TC-M09-G136/EvaluacionV2/automation
EVAL_DIR = BASE_DIR.parent                          # .../TC-M09-G136/EvaluacionV2
CASE_DIR = EVAL_DIR.parent                          # .../TC-M09-G136
if BASE_DIR.name != "automation" or EVAL_DIR.name != "EvaluacionV2" or CASE_DIR.name != FOLDER:
    raise RuntimeError(f"Directorio no autorizado para {FOLDER}: {BASE_DIR}")

REPO_DIR = CASE_DIR
for _ in range(12):
    if (REPO_DIR / ".git").exists() or (REPO_DIR / "alembic.ini").exists():
        break
    REPO_DIR = REPO_DIR.parent

GRUPO = "TC-M09-G136"
CASO = "TC-M09-274"
RF = "RF-24 v2.0"
CU = "CU05 — Gestionar Dispositivos IoT, Flujo D"
EVALUACION = "SEGUNDA EVALUACION"
BASELINE_RUN = "run-20261007-140122"
BASELINE_COMMIT = "30ddd72144102a60af006b265a20cb18c1c72c85"

BD_ESPERADA = "sgpmp_g136_lab"
APP_ROLE = "g136_app"
OWNER_ROLE = "g136_owner"
CONTAINER_DB = "sgpmp-g136-v2-db"
CONTAINER_BACKEND = "sgpmp-g136-v2-backend"
COMPOSE_PROJECT = "sgpmp-g136-v2"
VOLUMEN = "sgpmp_g136_v2_pgdata"

TABLA_EVENTOS = "modulo1.eventos"
# Código del producto que escribe la auditoría RF-10 del rechazo: se verifica que siga siendo
# esta tabla en el código ACTUAL antes de inducir el fallo (no se asume por el baseline).
FUENTE_RF10 = REPO_DIR / "src/configuration/application/use_cases/sensores/registrar_calibracion_use_case.py"
MODELO_EVENTOS = REPO_DIR / "src/identity_access/infrastructure/models/eventos_model.py"

ACTOR_CORREO = os.environ.get("G136_ING_EMAIL", "ingeniero.g136@pecuaria.co")
ROL_ESPERADO = "Ingeniero de Campo"

RUN_ID = os.environ["G136_RUN_ID"]
if not re.fullmatch(r"run-\d{8}-\d{6}", RUN_ID):
    raise RuntimeError("G136_RUN_ID debe tener formato run-YYYYMMDD-HHMMSS")
OUT_DIR = EVAL_DIR / "RESULTADOS" / RUN_ID
OUT_DIR.mkdir(parents=True, exist_ok=True)


# Mensajes del FA exigidos por RF-24 v2.0. No se sustituyen por lo que implemente el backend.
def msg_fuera_de_rango(valor: str, variable: str) -> str:
    return (f"Valor fuera de límites: El ajuste de {valor} excede los rangos de seguridad "
            f"para la variable {variable}. Verifique el estándar de calibración utilizado.")


def msg_dispositivo_inactivo(serial: str) -> str:
    return (f"Operación rechazada: El dispositivo {serial} está inactivo. Debe activar el "
            f"dispositivo antes de proceder con el registro de nuevos parámetros de calibración.")


# --------------------------------------------------------------------------- utilidades
def _secretos() -> list[str]:
    return [v for v in (
        os.environ.get("G136_OWNER_PASSWORD"), os.environ.get("G136_APP_PASSWORD"),
        os.environ.get("G136_ING_PASSWORD"), os.environ.get("G136_SECRET_KEY"),
    ) if v]


def clean(texto: Any) -> str:
    """Redacta secretos, JWT, Bearer y contraseñas embebidas en cadenas de conexión."""
    s = str(texto)
    for secreto in set(_secretos()):
        s = s.replace(secreto, "[REDACTED]")
    s = re.sub(r"eyJ[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]*", "[JWT REDACTED]", s)
    s = re.sub(r"Bearer\s+[A-Za-z0-9_.\-]{12,}", "Bearer [REDACTED]", s)
    s = re.sub(r"(postgres(?:ql)?://[^:/\s]+):[^@\s]+@", r"\1:[REDACTED]@", s)
    return s


def ahora_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_cmd(args: list[str], timeout: int = 180, cwd: str | None = None,
            env: dict | None = None) -> tuple[int, str]:
    p = subprocess.run(args, capture_output=True, text=True, timeout=timeout,
                       encoding="utf-8", errors="replace", cwd=cwd, env=env)
    return p.returncode, clean((p.stdout or "") + (p.stderr or ""))


def psql_owner(sql: str) -> tuple[int, str]:
    """SQL administrativo como DB_OWNER, solo dentro de la base aislada."""
    return run_cmd(["docker", "exec", "-i", CONTAINER_DB, "psql", "-U", OWNER_ROLE,
                    "-d", BD_ESPERADA, "-v", "ON_ERROR_STOP=1", "-c", sql])


def logs_backend(desde: str | None = None) -> str:
    args = ["docker", "logs", CONTAINER_BACKEND]
    if desde:
        args += ["--since", desde]
    return run_cmd(args)[1]


def filas(conn, sql: str, params: tuple = ()) -> list[dict]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, params)
        return [dict(f) for f in cur.fetchall()]


def uno(conn, sql: str, params: tuple = ()) -> Any:
    with conn.cursor() as cur:
        cur.execute(sql, params)
        f = cur.fetchone()
        return f[0] if f and len(f) == 1 else f


def sha256_de(ruta: Path) -> str | None:
    if not ruta.exists():
        return None
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


# --------------------------------------------------------------------------- seed local
# La BD es exclusivamente local, así que la matriz autoriza sembrar por SQL. Solo se crea lo
# imprescindible; nada se copia de TEST. Es idempotente: puede reejecutarse sin duplicar.
SEED_SQL = """
DO $$
DECLARE
  v_finca int; v_area int; v_disp_act int; v_disp_inact int;
  v_sensor_act int; v_sensor_inact int; v_usuario int;
BEGIN
  IF EXISTS (SELECT 1 FROM modulo9.dispositivos_iot WHERE serial = 'IOT-G136-LAB-ACT') THEN
    RETURN; -- fixture ya sembrado
  END IF;

  INSERT INTO modulo9.fincas (nombre, ubicacion, tamano_h, fecha_actualizacion, fecha_creacion, es_activo)
  VALUES ('Finca Laboratorio Auditoria', '{"lat": 4.6, "lng": -74.1}'::jsonb, 10.0, now(), now(), true)
  RETURNING id_finca INTO v_finca;

  INSERT INTO modulo9.infraestructuras (descripcion, nombre, id_finca, superficie, es_activo, tipo, fecha_actualizacion)
  VALUES ('Area del laboratorio G136', 'Estanque Laboratorio', v_finca, 100.0, true, 'Estanque', now())
  RETURNING id_infraestructura INTO v_area;

  -- Fixture A: dispositivo ACTIVO con sensor activo (variante de valor fuera de rango).
  INSERT INTO modulo9.dispositivos_iot (serial, descripcion, es_activo, fecha_creacion, id_infraestructura, id_tipo_dispositivo)
  VALUES ('IOT-G136-LAB-ACT', 'Dispositivo activo del laboratorio G136', true, now(), v_area, 2)
  RETURNING id_dispositivo_iot INTO v_disp_act;

  INSERT INTO modulo9.sensores (id_dispositivo_iot, es_activo, nombre, categoria)
  VALUES (v_disp_act, true, 'Sensor temperatura activo', 'TEMPERATURA')
  RETURNING id_sensores INTO v_sensor_act;

  -- Fixture B: dispositivo INACTIVO con sensor propio (variante de dispositivo inactivo).
  INSERT INTO modulo9.dispositivos_iot (serial, descripcion, es_activo, fecha_creacion, id_infraestructura, id_tipo_dispositivo)
  VALUES ('IOT-G136-LAB-INACT', 'Dispositivo inactivo del laboratorio G136', false, now(), v_area, 2)
  RETURNING id_dispositivo_iot INTO v_disp_inact;

  INSERT INTO modulo9.sensores (id_dispositivo_iot, es_activo, nombre, categoria)
  VALUES (v_disp_inact, true, 'Sensor temperatura inactivo', 'TEMPERATURA')
  RETURNING id_sensores INTO v_sensor_inact;

  -- Ingeniero de Campo (id_rol 4, sembrado por las migraciones) con cuenta activa.
  INSERT INTO modulo1.usuarios (tipo_identificacion, numero_identificacion, nombre, apellidos,
                                fecha_nacimiento, correo_electronico, contrasena_cifrada, telefono, direccion, id_rol)
  VALUES ('CC', '1079000136', 'Ingeniero', 'Laboratorio Auditoria', '1990-01-01',
          %(correo)s, %(hash)s, '3000000136', 'Laboratorio G136', 4)
  RETURNING id_usuario INTO v_usuario;

  INSERT INTO modulo1.cuentas_usuarios (id_usuario, id_estado_cuenta, tiene_correo_verificado, fecha_verificacion)
  VALUES (v_usuario, 2, true, now());

  -- Alcance de finca: las políticas RLS de modulo9 filtran por fn_fincas_del_usuario.
  INSERT INTO modulo9.usuarios_fincas (id_usuario_finca, id_usuario, id_finca, es_activo)
  VALUES (nextval('modulo9.usuarios_fincas_id_usuario_finca_seq'), v_usuario, v_finca, true);

  -- Asociaciones vigentes: así la ÚNICA invalidez de cada variante es la intencional.
  INSERT INTO modulo9.sensores_areas_asociadas (id_sensor, id_dispositivo_iot, id_infraestructura,
         punto_instalacion, tiene_estado, fecha_asociacion, fecha_finalizacion, id_usuario)
  VALUES (v_sensor_act, v_disp_act, v_area, 'Punto A', true, now(), NULL, v_usuario),
         (v_sensor_inact, v_disp_inact, v_area, 'Punto B', true, now(), NULL, v_usuario);
END $$;
"""


def sembrar_fixture(conn) -> None:
    sys.path.insert(0, str(REPO_DIR))
    from src.identity_access.domain.value_objects.contrasena import Contrasena  # noqa: E402
    hash_pwd = Contrasena.desde_texto_plano(os.environ["G136_ING_PASSWORD"]).hash
    with conn.cursor() as cur:
        cur.execute(SEED_SQL, {"correo": ACTOR_CORREO, "hash": hash_pwd})


# --------------------------------------------------------------------------- fixtures
@pytest.fixture(scope="module")
def conn():
    c = psycopg2.connect(os.environ["G136_ADMIN_DSN"])
    c.autocommit = True
    yield c
    c.close()


@pytest.fixture(scope="module")
def api_base() -> str:
    return os.environ["G136_API_URL"].rstrip("/")


def test_tc_m09_274_auditoria_best_effort(conn, api_base):
    ev: dict = {
        "grupo": GRUPO, "caso": CASO, "requisito": RF, "casoDeUso": CU, "run_id": RUN_ID,
        "evaluacion": EVALUACION,
        "baseline": {"run_id": BASELINE_RUN, "commit": BASELINE_COMMIT,
                     "nota": "El commit del baseline NO es el código reevaluado."},
        "ambiente": "LOCAL_AISLADO", "prueba_local": True,
        "herramienta": "Pytest + PostgreSQL local real + logs del backend. Newman: NO APLICA.",
        "carpeta": f"tests/Test_Testing/Test_Modulo9/RF-24/{GRUPO}/EvaluacionV2/",
    }

    # ------------------------------------------------------------------ git
    g = lambda *a: run_cmd(["git", "-C", str(REPO_DIR), *a])[1].strip() or "(vacio)"
    ev["git"] = {
        "rama": g("branch", "--show-current"), "status_short": g("status", "--short"),
        "diff_stat": g("diff", "--stat"), "diff_cached_stat": g("diff", "--cached", "--stat"),
        "head": g("rev-parse", "HEAD"), "origin_test": g("rev-parse", "origin/test"),
        "divergencia": g("rev-list", "--left-right", "--count", "HEAD...origin/test"),
        "fecha_head": g("show", "-s", "--format=%cI", "HEAD"),
        "fecha_del_run": ahora_iso(),
        "commit_evaluado": g("rev-parse", "HEAD"),
        "commit_baseline_primera_evaluacion": BASELINE_COMMIT,
        "es_el_commit_del_baseline": g("rev-parse", "HEAD") == BASELINE_COMMIT,
        "operaciones_git_de_escritura": ("ninguna: sin add, commit, push, merge, rebase, reset, "
                                         "clean, stash, switch ni checkout"),
    }
    assert not ev["git"]["es_el_commit_del_baseline"], (
        "BLOQUEADO: el laboratorio está ejecutando el commit del baseline, no el código a reevaluar")

    # ------------------------------------------------------- guard del laboratorio
    ident = filas(conn, "SELECT current_database() AS db, current_user AS usuario, "
                        "inet_server_addr()::text AS addr, inet_server_port() AS port")[0]
    dsn = os.environ.get("G136_ADMIN_DSN", "")
    host_dsn = (re.search(r"@([^:/?]+)", dsn) or [None, ""])[1]
    host_api = (re.search(r"://([^:/?]+)", api_base) or [None, ""])[1]
    problemas = []
    if ident["db"] != BD_ESPERADA:
        problemas.append(f"la base es {ident['db']} y se esperaba {BD_ESPERADA}")
    if host_dsn not in {"127.0.0.1", "localhost", "::1"}:
        problemas.append(f"el host del DSN ({host_dsn}) no es local")
    if host_api not in {"127.0.0.1", "localhost", "::1"}:
        problemas.append(f"el host de la API ({host_api}) no es local")
    for patron in ("inmero.co", "sslip.io", "back-sigab", "dokploy"):
        if patron in dsn.lower() or patron in api_base.lower():
            problemas.append(f"la conexión referencia un entorno remoto ({patron})")
    # La configuración efectiva del backend también debe ser local y apuntar a esta base.
    rc_cfg, cfg_backend = run_cmd(["docker", "exec", CONTAINER_BACKEND, "sh", "-c",
                                   "printenv DATABASE_URL ENV ALLOWED_ORIGINS"])
    for patron in ("inmero.co", "sslip.io", "back-sigab", "dokploy"):
        if patron in cfg_backend.lower():
            problemas.append(f"la configuración del backend referencia un entorno remoto ({patron})")
    if rc_cfg == 0 and BD_ESPERADA not in cfg_backend:
        problemas.append("el backend no apunta a la base del laboratorio")
    if rc_cfg == 0 and f"@db:5432/{BD_ESPERADA}" not in cfg_backend:
        problemas.append("el DATABASE_URL del backend no es el del contenedor local del laboratorio")

    ev["lab_guard"] = {
        "base_de_datos": ident["db"], "usuario_conexion": ident["usuario"],
        "host_dsn": host_dsn, "host_api": host_api, "puerto": ident["port"],
        "compose_project": COMPOSE_PROJECT,
        "contenedores": {"db": CONTAINER_DB, "backend": CONTAINER_BACKEND},
        "volumen": f"{VOLUMEN} (exclusivo de esta reevaluación)",
        "config_efectiva_backend": clean(cfg_backend).strip().splitlines(),
        "referencias_a_entornos_compartidos": "NINGUNA" if not problemas else problemas,
        "problemas": problemas, "resultado": "PASS" if not problemas else "BLOCKED / SAFETY GUARD",
        "postgres": str(uno(conn, "SELECT version()")),
        "alembic_version_en_bd": str(uno(conn, "SELECT version_num FROM alembic_version")),
        "credenciales_de_TEST_utilizadas": "NINGUNA: el laboratorio usa identidades locales propias",
    }
    assert not problemas, "BLOCKED / SAFETY GUARD: " + "; ".join(problemas)

    # ------------------------------------------------------- migraciones del proyecto
    entorno = {**os.environ, "ALEMBIC_DATABASE_URL": dsn, "DATABASE_URL": dsn}
    _, alembic_current = run_cmd([sys.executable, "-m", "alembic", "current"],
                                 cwd=str(REPO_DIR), env=entorno)
    _, alembic_heads = run_cmd([sys.executable, "-m", "alembic", "heads"],
                               cwd=str(REPO_DIR), env=entorno)
    rev_bd = str(ev["lab_guard"]["alembic_version_en_bd"])
    ev["migraciones"] = {
        "fuente": "migraciones reales del proyecto, aplicadas con alembic upgrade head como owner",
        "alembic_current": alembic_current.strip().splitlines()[-3:],
        "alembic_heads": alembic_heads.strip().splitlines()[-3:],
        "version_en_bd": rev_bd,
        "cabeza_coherente_con_el_codigo": rev_bd in alembic_heads and rev_bd in alembic_current,
        "migraciones_modificadas_para_pasar_la_prueba": "NINGUNA",
    }
    assert ev["migraciones"]["cabeza_coherente_con_el_codigo"], (
        f"BLOQUEADO: la revisión de la BD ({rev_bd}) no coincide con la cabeza del código actual")

    # --------------------------------- la tabla del fault debe ser la del CÓDIGO ACTUAL
    fuente_uc = FUENTE_RF10.read_text(encoding="utf-8") if FUENTE_RF10.exists() else ""
    fuente_modelo = MODELO_EVENTOS.read_text(encoding="utf-8") if MODELO_EVENTOS.exists() else ""
    tabla_modelo = re.search(r"__tablename__\s*=\s*'([^']+)'", fuente_modelo)
    schema_modelo = re.search(r"'schema'\s*:\s*'([^']+)'", fuente_modelo)
    tabla_actual = (f"{schema_modelo.group(1)}.{tabla_modelo.group(1)}"
                    if tabla_modelo and schema_modelo else None)
    ev["tabla_rf10"] = {
        "tabla_usada_en_el_fault": TABLA_EVENTOS,
        "tabla_declarada_en_el_codigo_actual": tabla_actual,
        "fuente_modelo": str(MODELO_EVENTOS.relative_to(REPO_DIR)),
        "fuente_best_effort": str(FUENTE_RF10.relative_to(REPO_DIR)),
        "best_effort_presente_en_el_codigo": bool(
            re.search(r"except Exception:\s*\n\s*db\.rollback\(\)", fuente_uc)
            and "no se pudo auditar el rechazo de calibración" in fuente_uc),
        "coincide": tabla_actual == TABLA_EVENTOS,
        "nota": ("Se verifica contra el código reevaluado, no se asume por el baseline. Si la "
                 "implementación hubiera cambiado de tabla, el fault injection sería inválido."),
    }
    assert ev["tabla_rf10"]["coincide"], (
        f"BLOQUEADO: RF-10 ya no escribe en {TABLA_EVENTOS} sino en {tabla_actual}")

    # ------------------------------------------------------- roles de base de datos
    rol_app = filas(conn, "SELECT rolname, rolsuper, rolinherit, rolbypassrls, rolcanlogin "
                          "FROM pg_roles WHERE rolname = %s", (APP_ROLE,))[0]
    owners = filas(conn, """
        SELECT schemaname, tablename, tableowner FROM pg_tables
        WHERE (schemaname, tablename) IN (('modulo1','eventos'), ('modulo9','calibraciones'),
                                          ('modulo9','auditorias_calibraciones'))
        ORDER BY schemaname, tablename
    """)
    hereda = uno(conn, """
        SELECT EXISTS(SELECT 1 FROM pg_auth_members m
                      JOIN pg_roles r ON r.oid = m.roleid
                      JOIN pg_roles gg ON gg.oid = m.member
                      WHERE gg.rolname = %s)
    """, (APP_ROLE,))
    app_owner_eventos = any(o["tablename"] == "eventos" and o["tableowner"] == APP_ROLE for o in owners)
    ev["db_roles"] = {
        "owner": {"rol": OWNER_ROLE, "uso": "migraciones, seed, REVOKE/GRANT y consultas administrativas"},
        "app": {**rol_app, "uso": "DATABASE_URL real del backend"},
        "rol_que_usa_el_backend": APP_ROLE,
        "app_es_superuser": rol_app["rolsuper"],
        "app_es_owner_eventos": app_owner_eventos,
        "app_hereda_de_otro_rol": hereda,
        "owners_tablas": owners,
        "nota_bypassrls": ("BYPASSRLS es necesario porque las políticas RLS leen app.current_user_id, "
                           "que la aplicación fija después de autenticar: sin él el login es imposible. "
                           "Solo afecta políticas de FILA, no privilegios de TABLA, de modo que el "
                           "REVOKE de INSERT sobre modulo1.eventos sigue siendo efectivo, y el RUN lo "
                           "comprueba empíricamente antes de enviar los POST."),
    }
    assert rol_app["rolcanlogin"] is True
    assert rol_app["rolsuper"] is False, "el rol de la aplicación NO puede ser superusuario"
    assert app_owner_eventos is False, "el rol de la aplicación NO puede ser owner de modulo1.eventos"
    assert hereda is False, "el rol de la aplicación no puede heredar privilegios de otro rol"

    # ------------------------------------------------------------------ fixture local
    sembrar_fixture(conn)
    fx = filas(conn, """
        SELECT d.id_dispositivo_iot, d.serial, d.es_activo,
               s.id_sensores AS id_sensor, s.categoria::text AS categoria, s.es_activo AS sensor_activo,
               a.id_infraestructura, r.valor_min, r.valor_max
        FROM modulo9.dispositivos_iot d
        JOIN modulo9.sensores s ON s.id_dispositivo_iot = d.id_dispositivo_iot
        JOIN modulo9.sensores_areas_asociadas a
          ON a.id_sensor = s.id_sensores AND a.tiene_estado = true AND a.fecha_finalizacion IS NULL
        JOIN modulo9.rangos_calibracion r ON r.categoria = s.categoria::text
        WHERE d.serial IN ('IOT-G136-LAB-ACT', 'IOT-G136-LAB-INACT')
        ORDER BY d.serial
    """)
    activo = next(f for f in fx if f["serial"] == "IOT-G136-LAB-ACT")
    inactivo = next(f for f in fx if f["serial"] == "IOT-G136-LAB-INACT")
    assert activo["es_activo"] is True and inactivo["es_activo"] is False
    assert activo["sensor_activo"] is True and inactivo["sensor_activo"] is True

    # Determinista aunque el seed use otro máximo: valor_fuera = max + 0.0001.
    vmax = Decimal(str(activo["valor_max"]))
    vmin = Decimal(str(activo["valor_min"]))
    valor_fuera = (vmax + Decimal("0.0001")).quantize(Decimal("0.0001"))
    valor_valido = ((vmin + vmax) / 2).quantize(Decimal("0.0001"))
    assert valor_fuera > vmax, "el valor de la variante RANGE debe exceder el máximo"
    assert vmin < valor_valido < vmax, "la variante INACTIVE debe usar un valor válido"

    actor = filas(conn, """
        SELECT u.id_usuario, u.correo_electronico, r.nombre_rol, e.nombre AS estado_cuenta
        FROM modulo1.usuarios u
        JOIN modulo1.roles r ON r.id_rol = u.id_rol
        JOIN modulo1.cuentas_usuarios c ON c.id_usuario = u.id_usuario
        JOIN modulo1.estados_cuentas e ON e.id_estado_cuenta = c.id_estado_cuenta
        WHERE u.correo_electronico = %s
    """, (ACTOR_CORREO,))[0]
    assert actor["nombre_rol"] == ROL_ESPERADO and actor["estado_cuenta"] == "Activo"

    ev["fixtures"] = {
        "origen": "sembrado por SQL local e idempotente; nada copiado de TEST",
        "actor": {"id_usuario": actor["id_usuario"], "correo": actor["correo_electronico"],
                  "rol": actor["nombre_rol"], "estado": actor["estado_cuenta"], "credencial": "[REDACTED]",
                  "credencial_nota": "sintética y exclusiva del laboratorio local; no se persiste"},
        "rango": {
            "id_dispositivo_iot": activo["id_dispositivo_iot"], "serial": activo["serial"],
            "es_activo": activo["es_activo"], "id_sensor": activo["id_sensor"],
            "sensor_activo": activo["sensor_activo"],
            "categoria": activo["categoria"], "id_infraestructura": activo["id_infraestructura"],
            "asociacion": "vigente (tiene_estado=true, fecha_finalizacion=NULL)",
            "valor_min": str(vmin), "valor_max": str(vmax), "valor_fuera": str(valor_fuera),
            "criterio_valor": "max + 0.0001, determinista respecto al rango sembrado",
            "unica_invalidez": "VALOR FUERA DE RANGO",
        },
        "dispositivo_inactivo": {
            "id_dispositivo_iot": inactivo["id_dispositivo_iot"], "serial": inactivo["serial"],
            "es_activo": inactivo["es_activo"], "id_sensor": inactivo["id_sensor"],
            "sensor_activo": inactivo["sensor_activo"],
            "categoria": inactivo["categoria"], "id_infraestructura": inactivo["id_infraestructura"],
            "asociacion": "vigente (tiene_estado=true, fecha_finalizacion=NULL)",
            "valor_usado": str(valor_valido), "valor_dentro_del_rango": vmin < valor_valido < vmax,
            "unica_invalidez": "DISPOSITIVO INACTIVO",
        },
    }

    # ------------------------------------- token ANTES del REVOKE (el login audita RF-10)
    r = requests.post(f"{api_base}/sesiones/",
                      json={"correo_electronico": ACTOR_CORREO, "contrasena": os.environ["G136_ING_PASSWORD"]},
                      timeout=30)
    assert r.status_code == 200 and r.json().get("token"), f"BLOQUEADO: el Ingeniero no autentica ({r.status_code})"
    token = r.json()["token"]  # vive solo en memoria; nunca se persiste
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    me = requests.get(f"{api_base}/usuarios/me", headers=headers, timeout=30)
    assert me.status_code == 200 and me.json()["nombre_rol"] == ROL_ESPERADO
    # Control de LECTURA sin fault: no consume el caso ni crea auditoría adicional.
    lectura = requests.get(f"{api_base}/configuracion/sensores/{activo['id_sensor']}/calibraciones",
                           headers=headers, timeout=30)
    assert lectura.status_code == 200
    ev["control_sin_fault"] = {
        "login_ingeniero_http": r.status_code,
        "identidad_http": me.status_code,
        "get_historial_http": lectura.status_code,
        "token_obtenido_antes_del_revoke": True,
        "nuevos_logins_durante_el_fault": 0,
        "nota": ("El token se obtuvo antes del REVOKE porque el login escribe auditoría RF-10 y "
                 "contaminaría el fault injection. Durante el fault se reutiliza la misma sesión."),
    }
    ev["fixtures"]["actor"]["token_obtenido_antes_del_revoke"] = True
    ev["fixtures"]["actor"]["control_de_lectura_http"] = lectura.status_code

    # ------------------------------------- privilegios y snapshots ANTES del fault
    priv = lambda: filas(conn, f"""
        SELECT has_table_privilege(%s, '{TABLA_EVENTOS}', 'INSERT')          AS eventos_insert,
               has_table_privilege(%s, '{TABLA_EVENTOS}', 'SELECT')          AS eventos_select,
               has_table_privilege(%s, 'modulo9.calibraciones', 'INSERT')    AS calibraciones_insert,
               has_table_privilege(%s, 'modulo9.auditorias_calibraciones', 'INSERT') AS audit_m9_insert
    """, (APP_ROLE, APP_ROLE, APP_ROLE, APP_ROLE))[0]
    priv_antes = priv()
    assert priv_antes["eventos_insert"] is True, "BLOQUEADO: la app no tiene INSERT sobre RF-10 antes del fault"
    ev["control_sin_fault"]["insert_eventos_efectivo_antes"] = priv_antes["eventos_insert"]

    snap = lambda sid: filas(conn, "SELECT id_calibracion FROM modulo9.calibraciones "
                                   "WHERE id_sensor = %s ORDER BY id_calibracion", (sid,))
    pre_range = [f["id_calibracion"] for f in snap(activo["id_sensor"])]
    pre_inact = [f["id_calibracion"] for f in snap(inactivo["id_sensor"])]
    eventos_previos = uno(conn, f"SELECT count(*) FROM {TABLA_EVENTOS} WHERE id_usuario = %s",
                          (actor["id_usuario"],))
    ev["pre"] = {
        "rango": {"id_sensor": activo["id_sensor"], "total": len(pre_range), "ids": pre_range},
        "inactive": {"id_sensor": inactivo["id_sensor"], "total": len(pre_inact), "ids": pre_inact},
        "eventos_rf10_del_actor_antes_del_fault": eventos_previos,
        "nota": ("Ningún evento RF-10 de los intentos existe todavía porque los POST aún no "
                 "ocurrieron; los eventos previos corresponden al login del control."),
    }

    # Marca para acotar la captura de logs del backend al fault injection.
    marca_logs = ahora_iso()
    ev["ventana_de_log"] = {"marca_inicial": marca_logs,
                            "criterio": ("la búsqueda de alertas se limita a esta ventana: no se "
                                         "cuentan logs de arranque, migraciones, seed, login ni "
                                         "ejecuciones anteriores")}

    restaurado = {"ok": None}
    try:
        # --------------------------------------------- FAULT INJECTION
        rc, salida_rev = psql_owner(
            f"REVOKE INSERT ON TABLE {TABLA_EVENTOS} FROM {APP_ROLE};")
        assert rc == 0, f"el REVOKE no se aplicó: {salida_rev}"
        priv_durante = priv()
        ev["privilegios"] = {
            "rol": APP_ROLE, "tabla": TABLA_EVENTOS,
            "insert_eventos_antes": priv_antes["eventos_insert"],
            "insert_eventos_durante": priv_durante["eventos_insert"],
            "select_eventos_conservado": priv_durante["eventos_select"],
            "calibraciones_insert_conservado": priv_durante["calibraciones_insert"],
            "auditoria_m9_insert_conservado": priv_durante["audit_m9_insert"],
            "insert_eventos_restaurado": None,
            "alcance": ("solo INSERT sobre la tabla de RF-10; no se revoca SELECT ni los INSERT de "
                        "modulo9.calibraciones y modulo9.auditorias_calibraciones"),
        }
        # Si el REVOKE no es efectivo, el laboratorio es inválido: no se envían los POST.
        assert priv_durante["eventos_insert"] is False, (
            "BLOQUEADO / LABORATORIO INVÁLIDO: el REVOKE no eliminó el INSERT sobre RF-10 "
            "(¿app owner, superuser o rol heredado?)")
        # El único fallo inducido debe ser la escritura RF-10.
        assert priv_durante["eventos_select"] is True
        assert priv_durante["calibraciones_insert"] is True
        assert priv_durante["audit_m9_insert"] is True
        assert filas(conn, "SELECT count(*) AS n FROM modulo9.sensores WHERE id_sensores = %s",
                     (activo["id_sensor"],))[0]["n"] == 1, "el SELECT del fixture debe seguir funcionando"

        def ejecutar(variante: str, id_sensor: int, id_dispositivo: int, id_area: int,
                     valor: Decimal, observaciones: str, http_esperado: int, mensaje_esperado: str,
                     error_code_esperado: str, pre_ids: list[int]) -> dict:
            t_before = ahora_iso()
            body = {
                "modo_calibracion": "SENSOR",
                "id_dispositivo_iot": id_dispositivo,
                "id_infraestructura": id_area,
                "valor_referencia": float(valor),
                "observaciones": observaciones,
                "fecha_calibracion": t_before,
            }
            resp = requests.post(f"{api_base}/configuracion/sensores/{id_sensor}/calibrar",
                                 headers=headers, data=json.dumps(body), timeout=60)
            t_after = ahora_iso()
            cuerpo = resp.json() if resp.content else None
            post_ids = [f["id_calibracion"] for f in snap(id_sensor)]
            # ¿Se escribió realmente el evento RF-10 del rechazo en la ventana?
            eventos = filas(conn, f"""
                SELECT id_evento, tipo_evento, fecha_evento
                FROM {TABLA_EVENTOS}
                WHERE fecha_evento >= %s::timestamptz AND fecha_evento <= %s::timestamptz
                  AND id_usuario = %s
                ORDER BY id_evento
            """, (t_before, t_after, actor["id_usuario"]))
            mensaje = (cuerpo or {}).get("message")
            codigo = (cuerpo or {}).get("error_code")
            return {
                "variante": variante,
                "invalidez_intencional": observaciones,
                "request": {"endpoint": f"/configuracion/sensores/{id_sensor}/calibrar", "metodo": "POST",
                            "headers": {"Authorization": "[REDACTED]", "Content-Type": "application/json"},
                            "body": body, "intentos": 1, "reintentos": 0},
                "response": {"http": resp.status_code, "cuerpo": cuerpo},
                "ventana": {"t_before": t_before, "t_after": t_after},
                "http_esperado": http_esperado, "http_obtenido": resp.status_code,
                "no_es_500": resp.status_code != 500,
                "error_code_esperado": error_code_esperado, "error_code_obtenido": codigo,
                "error_code_coincide": codigo == error_code_esperado,
                "mensaje_esperado": mensaje_esperado, "mensaje_obtenido": mensaje,
                "mensaje_coincide": mensaje == mensaje_esperado,
                "comparacion_de_mensaje": "literal estricta contra el FA de RF-24 v2.0",
                "id_calibracion_en_respuesta": (cuerpo or {}).get("id_calibracion"),
                "calibraciones_pre": {"ids": pre_ids, "total": len(pre_ids)},
                "calibraciones_post": {"ids": post_ids, "total": len(post_ids)},
                "calibracion_creada": post_ids != pre_ids,
                "evento_rf10_creado": len(eventos) > 0,
                "eventos_en_la_ventana": eventos,
                "nota_rf10": ("La ausencia del evento RF-10 es la condición PROVOCADA del caso, no "
                              "un defecto: demuestra que la escritura de auditoría falló de verdad."),
            }

        # --------------------------------------------- Variante A: valor fuera de rango
        range_res = ejecutar(
            "RANGE", activo["id_sensor"], activo["id_dispositivo_iot"], activo["id_infraestructura"],
            valor_fuera, "QA TC-M09-274 RANGE", 400,
            msg_fuera_de_rango(str(valor_fuera), activo["categoria"]), "VALOR_FUERA_DE_RANGO", pre_range)

        # Antes de la segunda variante: el fault sigue activo y el dispositivo sigue inactivo.
        fault_sigue = priv()["eventos_insert"] is False
        sigue_inactivo = uno(conn, "SELECT es_activo FROM modulo9.dispositivos_iot "
                                   "WHERE id_dispositivo_iot = %s", (inactivo["id_dispositivo_iot"],))

        # --------------------------------------------- Variante B: dispositivo inactivo
        inactive_res = ejecutar(
            "INACTIVE", inactivo["id_sensor"], inactivo["id_dispositivo_iot"], inactivo["id_infraestructura"],
            valor_valido, "QA TC-M09-274 INACTIVE", 422,
            msg_dispositivo_inactivo(inactivo["serial"]), "DISPOSITIVO_INACTIVO", pre_inact)
        inactive_res["fault_sigue_activo_al_ejecutar"] = fault_sigue
        inactive_res["dispositivo_realmente_inactivo"] = sigue_inactivo is False
        inactive_res["serial_proviene_del_fixture"] = (
            inactivo["serial"] in (inactive_res["mensaje_obtenido"] or "")
            or inactivo["serial"] == "IOT-G136-LAB-INACT")
        assert fault_sigue, "el fault dejó de estar activo antes de la variante INACTIVE"
        assert sigue_inactivo is False, "el dispositivo de la variante INACTIVE debe seguir inactivo"

        # --------------------------------------------- constancia observable del fallo
        log = logs_backend(desde=marca_logs)
        (OUT_DIR / "backend.log").write_text(clean(log), encoding="utf-8")
        lineas_log = clean(log).splitlines()
        captura_ok = bool(log.strip())

        def eventos_de_alerta():
            """Agrupa el log en eventos de alerta: uno por fallo de auditoria.

            Cada constancia abre un bloque y arrastra su propio stacktrace, de modo que las
            multiples lineas de una misma excepcion cuentan como UN evento y no como varias
            alertas. La correlacion con su POST se hace por el sensor que nombra la propia
            constancia, que es mas fiable que el orden de aparicion.
            """
            eventos = []
            # Patrón deliberadamente tolerante al acento de "calibración": basta con la
            # constancia de que no se pudo auditar y el sensor que nombra.
            patron = re.compile(r"no se pudo auditar.*?sensor\s+(\d+)", re.I)
            for linea in lineas_log:
                m = patron.search(linea)
                if m:
                    eventos.append({
                        "id_sensor": int(m.group(1)),
                        "constancia": linea.strip()[:300],
                        "lineas_de_la_excepcion": 0,
                        "permission_denied_eventos": False,
                    })
                elif eventos:
                    eventos[-1]["lineas_de_la_excepcion"] += 1
                    if "permission denied for table eventos" in linea.lower():
                        eventos[-1]["permission_denied_eventos"] = True
            return eventos

        total_alertas = eventos_de_alerta()
        por_sensor = {e["id_sensor"]: e for e in total_alertas}

        def alerta_de(id_sensor):
            e = por_sensor.get(id_sensor)
            return {
                "captura_de_logs_operativa": captura_ok,
                "alerta_encontrada": e is not None,
                "correlacion": f"la constancia nombra el sensor {id_sensor}",
                "constancia": e["constancia"] if e else None,
                "permission_denied_eventos": e["permission_denied_eventos"] if e else False,
                "lineas_de_la_excepcion": e["lineas_de_la_excepcion"] if e else 0,
            }

        range_res["alerta_log"] = alerta_de(activo["id_sensor"])
        inactive_res["alerta_log"] = alerta_de(inactivo["id_sensor"])
        ev["alertas_detectadas"] = {
            "total_eventos_de_alerta": len(total_alertas),
            "eventos_logicos_esperados": 2,
            "distinguibles": len({e["id_sensor"] for e in total_alertas}) == 2,
            "eventos": total_alertas,
            "criterio": ("Una constancia observable por cada fallo de auditoria. Las lineas de una "
                         "misma excepcion se agrupan como un unico evento de alerta, y cada evento se "
                         "correlaciona con su POST por el sensor que nombra la constancia. El RF no "
                         "define sink, formato ni texto literal: el canal elegido es el log del backend."),
        }

        # --------------------------------------------- oráculo por variante
        for res in (range_res, inactive_res):
            res["oraculo"] = {
                "http_correcto": res["http_obtenido"] == res["http_esperado"],
                "no_es_500": res["no_es_500"],
                "error_code_correcto": res["error_code_coincide"],
                "mensaje_fa_correcto": res["mensaje_coincide"],
                "sin_calibracion_creada": res["calibracion_creada"] is False,
                "sin_id_calibracion_en_respuesta": res["id_calibracion_en_respuesta"] is None,
                "evento_rf10_no_escrito": res["evento_rf10_creado"] is False,
                "alerta_observable": res["alerta_log"]["alerta_encontrada"] is True,
            }
            res["resultado"] = "APROBADO" if all(res["oraculo"].values()) else "RECHAZADO"

        ev["range"] = range_res
        ev["inactive"] = inactive_res

    finally:
        # --------------------------------------------- restauración, siempre
        rc_res, salida_res = psql_owner(
            f"GRANT INSERT ON TABLE {TABLA_EVENTOS} TO {APP_ROLE};")
        priv_despues = priv()
        restaurado["ok"] = priv_despues["eventos_insert"] is True
        ev.setdefault("privilegios", {})["insert_eventos_restaurado"] = priv_despues["eventos_insert"]
        ev["restauracion"] = {
            "obligatoria": "sí, en finally: se ejecuta aunque Pytest, RANGE o INACTIVE fallen",
            "grant_ejecutado": rc_res == 0, "privilegios_restaurados": restaurado["ok"],
            "insert_antes": priv_antes["eventos_insert"],
            "insert_durante": (ev.get("privilegios") or {}).get("insert_eventos_durante"),
            "insert_despues": priv_despues["eventos_insert"],
            "salida": salida_res.strip()[:400],
            "resultado_infraestructura": "PASS" if restaurado["ok"] else "FAIL",
            "nota": "Se devuelve exactamente el privilegio que el snapshot PRE demostró disponible.",
        }
        _escribir_evidencia(ev)
        _escribir_manifest()

    assert restaurado["ok"] is True, (
        "EJECUCIÓN INVÁLIDA / LABORATORIO NO CERRADO CORRECTAMENTE: no se restauró el INSERT sobre RF-10")

    # --------------------------------------------- aserciones del oráculo
    r_a, r_b = ev["range"], ev["inactive"]
    assert r_a["no_es_500"], "el fallo de auditoría se propagó al cliente: la variante RANGE devolvió 500"
    assert r_b["no_es_500"], "el fallo de auditoría se propagó al cliente: la variante INACTIVE devolvió 500"
    assert r_a["http_obtenido"] == 400, f"RANGE: HTTP esperado 400, obtenido {r_a['http_obtenido']}"
    assert r_b["http_obtenido"] == 422, f"INACTIVE: HTTP esperado 422, obtenido {r_b['http_obtenido']}"
    assert r_a["error_code_coincide"], f"RANGE: error_code {r_a['error_code_obtenido']}"
    assert r_b["error_code_coincide"], f"INACTIVE: error_code {r_b['error_code_obtenido']}"
    assert r_a["calibracion_creada"] is False and r_b["calibracion_creada"] is False
    assert r_a["id_calibracion_en_respuesta"] is None and r_b["id_calibracion_en_respuesta"] is None
    assert r_a["evento_rf10_creado"] is False and r_b["evento_rf10_creado"] is False
    assert r_a["alerta_log"]["alerta_encontrada"], "no se observó constancia del fallo de auditoría en RANGE"
    assert r_b["alerta_log"]["alerta_encontrada"], "no se observó constancia del fallo de auditoría en INACTIVE"
    assert ev["alertas_detectadas"]["distinguibles"], (
        "las dos constancias deben ser distinguibles: una por sensor")
    assert r_a["mensaje_coincide"], (
        "RANGE: el mensaje no coincide con el FA de RF-24 v2.0.\n"
        f"  esperado: {r_a['mensaje_esperado']}\n  obtenido: {r_a['mensaje_obtenido']}")
    assert r_b["mensaje_coincide"], (
        "INACTIVE: el mensaje no coincide con el FA de RF-24 v2.0.\n"
        f"  esperado: {r_b['mensaje_esperado']}\n  obtenido: {r_b['mensaje_obtenido']}")


# --------------------------------------------------------------------------- comparación
BASELINE = {
    "range": {"resultado": "RECHAZADO", "http": "400", "es_500": "NO",
              "error_code": "VALOR_FUERA_DE_RANGO", "mensaje": "Incorrecto",
              "mensaje_literal": ("El ajuste de 45.0001 excede los rangos de seguridad para la "
                                  "variable TEMPERATURA (permitido 0.0000–45.0000). Verifique el "
                                  "estándar de calibración utilizado."),
              "persistencia": "Ninguna", "rf10": "NO", "alerta": "Sí",
              "unico_fallo": "el mensaje: faltaba el prefijo «Valor fuera de límites:» y sobraba «(permitido 0.0000–45.0000)»"},
    "inactive": {"resultado": "RECHAZADO", "http": "422", "es_500": "NO",
                 "error_code": "DISPOSITIVO_INACTIVO", "mensaje": "Incorrecto",
                 "mensaje_literal": "Solo se pueden calibrar sensores de dispositivos activos.",
                 "persistencia": "Ninguna", "rf10": "NO", "alerta": "Sí",
                 "unico_fallo": ("el mensaje: texto completamente distinto, sin prefijo, sin el serial "
                                 "y sin la instrucción de activar el dispositivo")},
    "caso": "RECHAZADO", "grupo": "RECHAZADO", "best_effort": "FUNCIONABA",
}


def _comparacion(ev: dict) -> dict:
    def seg(res, clave):
        if not res:
            return "no ejecutada"
        if clave == "http":
            return str(res.get("http_obtenido"))
        if clave == "es_500":
            return "NO" if res.get("no_es_500") else "SÍ"
        if clave == "error_code":
            return str(res.get("error_code_obtenido"))
        if clave == "mensaje":
            return "Correcto (literal del FA)" if res.get("mensaje_coincide") else "Incorrecto"
        if clave == "persistencia":
            return "Ninguna" if res.get("calibracion_creada") is False else "INDEBIDA"
        if clave == "rf10":
            return "NO" if res.get("evento_rf10_creado") is False else "SÍ"
        if clave == "alerta":
            return "Sí" if (res.get("alerta_log") or {}).get("alerta_encontrada") else "No"
        return "?"

    r_a, r_b = ev.get("range") or {}, ev.get("inactive") or {}
    dims = ("http", "es_500", "error_code", "mensaje", "persistencia", "rf10", "alerta")
    best_effort_segunda = (
        "FUNCIONA" if r_a.get("no_es_500") and r_b.get("no_es_500")
        and r_a.get("calibracion_creada") is False and r_b.get("calibracion_creada") is False
        else "REGRESIÓN")
    return {
        "baseline_unico": f"PRIMERA EVALUACION OFICIAL {BASELINE_RUN}",
        "fuente": f"tests/Test_Testing/Test_Modulo9/RF-24/{GRUPO}/RESULTADOS/{BASELINE_RUN}/{GRUPO}_resultado.md",
        "range": {d: {"primera": BASELINE["range"][d], "segunda": seg(r_a, d),
                      "cambio": ("SIN CAMBIO" if BASELINE["range"][d] == seg(r_a, d)
                                 else f"{BASELINE['range'][d]} -> {seg(r_a, d)}")} for d in dims},
        "inactive": {d: {"primera": BASELINE["inactive"][d], "segunda": seg(r_b, d),
                         "cambio": ("SIN CAMBIO" if BASELINE["inactive"][d] == seg(r_b, d)
                                    else f"{BASELINE['inactive'][d]} -> {seg(r_b, d)}")} for d in dims},
        "mensajes": {
            "range": {"primera": BASELINE["range"]["mensaje_literal"],
                      "esperado": r_a.get("mensaje_esperado"), "segunda": r_a.get("mensaje_obtenido")},
            "inactive": {"primera": BASELINE["inactive"]["mensaje_literal"],
                         "esperado": r_b.get("mensaje_esperado"), "segunda": r_b.get("mensaje_obtenido")},
        },
        "por_variante": {
            "RANGE": {"primera": BASELINE["range"]["resultado"], "segunda": r_a.get("resultado")},
            "INACTIVE": {"primera": BASELINE["inactive"]["resultado"], "segunda": r_b.get("resultado")},
        },
        "caso": {"primera": BASELINE["caso"], "segunda": ev.get("resultado")},
        "grupo": {"primera": BASELINE["grupo"], "segunda": ev.get("resultado")},
        "best_effort": {"primera": BASELINE["best_effort"], "segunda": best_effort_segunda},
        "causa_anterior": ("CORREGIDA" if ev.get("resultado") == "APROBADO"
                           else "REGRESIÓN" if best_effort_segunda == "REGRESIÓN"
                           else "NO CORREGIDA"),
    }


def _causa_raiz(ev: dict) -> str:
    r_a, r_b = ev.get("range") or {}, ev.get("inactive") or {}
    o_a, o_b = r_a.get("oraculo") or {}, r_b.get("oraculo") or {}
    if not o_a or not o_b:
        return "Por determinar: el caso no completó ambas variantes."
    if r_a.get("http_obtenido") == 500 or r_b.get("http_obtenido") == 500:
        return ("C. REGRESIÓN del mecanismo best-effort: el fallo de auditoría RF-10 se propagó al "
                "cliente y transformó el rechazo funcional en HTTP 500.")
    if r_a.get("evento_rf10_creado") or r_b.get("evento_rf10_creado"):
        return ("E. Fault injection INVÁLIDO: el evento RF-10 se escribió a pesar del REVOKE. No se "
                "evalúa el producto con esta corrida.")
    if not o_a.get("alerta_observable") or not o_b.get("alerta_observable"):
        return ("D. No se observó constancia del fallo de auditoría: revisar logger y configuración "
                "del backend antes de atribuir el defecto al producto.")
    if o_a.get("mensaje_fa_correcto") and o_b.get("mensaje_fa_correcto"):
        return ("A. 400 y 422 con los mensajes literales del FA y una constancia por intento: la "
                "causa del rechazo anterior está corregida y desplegada en el código reevaluado. El "
                "mecanismo best-effort sigue siendo correcto.")
    return ("B. Los códigos y el best-effort son correctos, pero al menos un mensaje conserva el "
            "texto antiguo: la corrección textual del FA no está aplicada.")


def _escribir_evidencia(ev: dict) -> None:
    """Consolida toda la evidencia del RUN en un único archivo, ya sanitizado."""
    r_a = ev.get("range") or {}
    r_b = ev.get("inactive") or {}
    resultados = [r_a.get("resultado"), r_b.get("resultado")]
    if not all(resultados):
        ev["resultado"] = "BLOQUEADO / NO VERIFICABLE"
        ev["motivo"] = "No se completaron ambas variantes del caso."
    elif all(x == "APROBADO" for x in resultados):
        ev["resultado"] = "APROBADO"
        ev["motivo"] = ("Con el INSERT de RF-10 denegado, ambos rechazos conservaron su código "
                        "funcional y su mensaje del FA, no crearon calibraciones y dejaron "
                        "constancia observable del fallo de auditoría.")
    else:
        ev["resultado"] = "RECHAZADO"
        fallos = []
        for res in (r_a, r_b):
            malos = [k for k, v in (res.get("oraculo") or {}).items() if v is not True]
            if malos:
                fallos.append(f"{res.get('variante')}: {', '.join(malos)}")
        ev["motivo"] = "El oráculo se alcanzó y el producto incumple en: " + " | ".join(fallos)

    ev["resultado_caso"] = {CASO: ev["resultado"]}
    ev["resultado_grupo"] = ev["resultado"]
    ev["comparacion_primera_segunda"] = _comparacion(ev)
    ev["causa_raiz"] = _causa_raiz(ev)

    if ev["resultado"] == "APROBADO":
        ev["incidencia"] = {
            "requerida": "NO",
            "causa_anterior": "CORREGIDA",
            "best_effort": "sigue siendo correcto: el fallo de auditoría no altera el código HTTP "
                           "ni crea calibraciones",
            "propuesta": "validar y cerrar la incidencia previa de TC-M09-274 (mensajes del FA)",
        }
    else:
        solo_mensaje = all(
            (res.get("oraculo") or {}).get("http_correcto") and (res.get("oraculo") or {}).get("no_es_500")
            and (res.get("oraculo") or {}).get("sin_calibracion_creada")
            and (res.get("oraculo") or {}).get("alerta_observable")
            and not (res.get("oraculo") or {}).get("mensaje_fa_correcto")
            for res in (r_a, r_b) if res.get("oraculo")
        )
        regresion = any(res.get("http_obtenido") == 500 for res in (r_a, r_b) if res)
        ev["incidencia"] = {
            "requerida": "SÍ", "grupo_responsable": "Desarrollo", "grupo_de_prueba": GRUPO, "caso": CASO,
            "variantes_afectadas": "ambas (RANGE e INACTIVE)" if len(resultados) == 2 else "parcial",
            "resultado": ev["resultado"],
            "motivo": ("Los mensajes funcionales de ambos rechazos no corresponden al FA de RF-24 v2.0."
                       if solo_mensaje else ev["motivo"]),
            "esperado": {"RANGE": r_a.get("mensaje_esperado"), "INACTIVE": r_b.get("mensaje_esperado")},
            "obtenido": {"RANGE": r_a.get("mensaje_obtenido"), "INACTIVE": r_b.get("mensaje_obtenido")},
            "causa_raiz": ev["causa_raiz"],
            "type": "bug",
            "severity": "Important" if regresion else ("Normal" if solo_mensaje else "Important"),
            "priority": "High" if regresion else ("Normal" if solo_mensaje else "High"),
            "evidencia": "evidencia.json / backend.log / pytest.xml",
        }

    serializada = json.dumps(ev, default=str)
    patrones = [("JWT", r"eyJ[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,}\."),
                ("Authorization con token", r"Bearer\s+[A-Za-z0-9_.\-]{12,}"),
                ("cadena de conexión con contraseña", r"postgres(?:ql)?://[^:/\s]+:[^@\s\[]+@")]
    credenciales = [c for c in _secretos() if c and c in serializada]
    ev["seguridad"] = {
        "hallazgos": [n for n, p in patrones if re.search(p, serializada)],
        "credenciales_en_claro": len(credenciales),
        "limpio": not credenciales and not any(re.search(p, serializada) for _, p in patrones),
        "credencial_sintetica_del_laboratorio_persistida": "NO",
        "criterio": "Se buscan valores de secreto, no vocabulario. El token vive solo en memoria.",
    }
    ev["git_final"] = {
        "rama": run_cmd(["git", "-C", str(REPO_DIR), "branch", "--show-current"])[1].strip(),
        "status_short": run_cmd(["git", "-C", str(REPO_DIR), "status", "--short"])[1].strip(),
        "primera_evaluacion_RESULTADOS": (
            run_cmd(["git", "-C", str(REPO_DIR), "status", "--short", "--",
                     f"tests/Test_Testing/Test_Modulo9/RF-24/{GRUPO}/RESULTADOS"])[1].strip()
            or "(vacio = intacta)"),
    }
    (OUT_DIR / "evidencia.json").write_text(
        clean(json.dumps(ev, indent=2, ensure_ascii=False, default=str)), encoding="utf-8")


def _escribir_manifest() -> None:
    """Registra ruta, función y SHA-256 de los artefactos de automatización realmente usados."""
    rel = lambda p: str(p.relative_to(REPO_DIR)).replace("\\", "/")
    artefactos = [
        (BASE_DIR / "test_g136_v2.py",
         "Test Pytest único de la reevaluación: guard del laboratorio, verificación de la tabla "
         "RF-10 contra el código actual, roles y privilegios, seed local idempotente, control sin "
         "fault, fault injection por REVOKE, las dos variantes, correlación de alertas, "
         "restauración en finally y consolidación de evidencia."),
        (BASE_DIR / "docker-compose.g136-v2.yml",
         "Laboratorio local aislado: PostgreSQL real con volumen exclusivo y backend del proyecto "
         "construido desde el código reevaluado, ambos publicados solo en localhost."),
        (CASE_DIR / "test_tc_m09_274.py",
         "Test de la primera evaluación. Reutilizado como base de esta reevaluación; se conserva "
         "intacto y no se ejecuta en este RUN."),
        (CASE_DIR / "docker-compose.g136.yml",
         "Compose de la primera evaluación. Reutilizado como base; se conserva intacto y no se "
         "ejecuta en este RUN."),
        (FUENTE_RF10,
         "Código del producto que audita el rechazo de calibración en modo best-effort. Se lee en "
         "solo lectura para verificar la tabla de RF-10 y la presencia del mecanismo."),
    ]
    filas_manifest = []
    for ruta, funcion in artefactos:
        filas_manifest.append({
            "archivo": ruta.name,
            "ruta": rel(ruta) if ruta.exists() else str(ruta),
            "funcion": funcion,
            "sha256": sha256_de(ruta),
            "bytes": ruta.stat().st_size if ruta.exists() else None,
            "estado": "PRESENTE" if ruta.exists() else "AUSENTE",
        })
    (OUT_DIR / "automation_manifest.json").write_text(json.dumps({
        "grupo": GRUPO, "caso": CASO, "run_id": RUN_ID, "evaluacion": EVALUACION,
        "herramienta": "Pytest. Newman: NO APLICA.",
        "nota": ("Artefactos finales de la SEGUNDA EVALUACION. Los ejecutables viven únicamente en "
                 "EvaluacionV2/automation/; no se copian scripts dentro de RESULTADOS."),
        "automation_dentro_de_RESULTADOS": "NO",
        "artefactos": filas_manifest,
    }, indent=2, ensure_ascii=False), encoding="utf-8")
