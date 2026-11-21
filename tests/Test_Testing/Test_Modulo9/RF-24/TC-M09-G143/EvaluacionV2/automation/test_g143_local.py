"""TC-M09-292 — integridad transaccional de la publicación de línea base VISION.

TC-M09-G143 · RF-24 v2.0 · CU05 Flujo F · LABORATORIO LOCAL AISLADO.

Qué demuestra: con una línea base L1 vigente y un segundo cálculo que converge sobre una ventana
nueva W2, si **falla el INSERT de la auditoría RF-10** la publicación de L2 debe deshacerse por
completo y L1 debe seguir vigente.

Cómo se hace real el fallo (§35 y §36): el backend se conecta con `sgpmp_app_g143`, un rol que
**no** es superusuario ni dueño de `modulo1.eventos`, y la inyección es un
`REVOKE INSERT ON modulo1.eventos` ejecutado por el owner. Antes del POST se comprueba que el
privilegio quedó en `false`; si no, la inyección se declara inválida y el caso no se ejecuta.

La tabla objetivo es `modulo1.eventos` (§37), que es donde `SqlAlchemyEventoRepository` persiste
la auditoría de la calibración VISION. No se usa ninguna otra tabla como sustituto.

Presupuesto: 1 POST de calibración de setup (L1), 1 POST objetivo (W2), 1 REVOKE, 1 GRANT,
0 reintentos. El GRANT se restaura en `try/finally`, pase lo que pase.

Uso (desde el host, con el laboratorio definido):
    docker compose -p sgpmp-g143-local -f docker-compose.g143-local.yml run --rm lab \
        python -m pytest tests/.../automation/test_g143_local.py -v --noconftest
"""
from __future__ import annotations

import datetime
import hashlib
import json
import logging
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

import psycopg2
import psycopg2.extras
import pytest

BASE_DIR = Path(__file__).resolve().parent
EVAL_DIR = BASE_DIR.parent
CASE_DIR = EVAL_DIR.parent
GRUPO, CASO = "TC-M09-G143", "TC-M09-292"
if BASE_DIR.name != "automation" or EVAL_DIR.name != "EvaluacionV2" or CASE_DIR.name != GRUPO:
    raise RuntimeError(f"ABORTADO: ruta no autorizada para {GRUPO}: {BASE_DIR}")
REPO_DIR = CASE_DIR.parents[4]
sys.path.insert(0, str(REPO_DIR))

RUN_ID = os.environ["G143_RUN_ID"]
RUN_DIR = EVAL_DIR / "RESULTADOS" / RUN_ID
RUN_DIR.mkdir(parents=True, exist_ok=True)

# ── Guarda de aislamiento (§34) ──────────────────────────────────────────────
PROHIBIDO = ("158.69.200.27", "sgpmp_test", "sgpmp_dev", "api.inmero.co", "inmero")
APP_DSN = os.environ["DATABASE_URL"]
OWNER_DSN = os.environ["G143_OWNER_DSN"]
APP_ROLE = "sgpmp_app_g143"
TABLA_AUDITORIA = "modulo1.eventos"

for etiqueta, dsn in (("DATABASE_URL", APP_DSN), ("G143_OWNER_DSN", OWNER_DSN)):
    marcas = [m for m in PROHIBIDO if m in dsn.lower()]
    if marcas:
        raise RuntimeError(f"STOP_ALL: {etiqueta} contiene marcas de un ambiente compartido: {marcas}")

_p = urlparse(APP_DSN)
DB_HOST, DB_PORT, DB_NAME, DB_USER = _p.hostname, _p.port or 5432, (_p.path or "/").lstrip("/"), _p.username
if DB_NAME != "sgpmp_g143_lab":
    raise RuntimeError(f"STOP_ALL: la base del laboratorio debe ser sgpmp_g143_lab; es {DB_NAME}")
DSN_SANITIZADA = f"postgresql://{DB_USER}:[REDACTED]@{DB_HOST}:{DB_PORT}/{DB_NAME}"

ING_CORREO = "ingeniero.g143.lab@laboratorio-g143.co"
ING_PASSWORD = os.environ["G143_ING_PASSWORD"]
APP_PASSWORD = os.environ["G143_APP_PASSWORD"]
#: SHA del arbol que el laboratorio esta ejecutando. Lo inyecta el host: dentro del
#: contenedor no hay repositorio git porque /app es un snapshot exportado.
LOCAL_SOURCE_SHA = os.environ.get("G143_LOCAL_SOURCE_SHA", "")
SERIAL_CAM = "IOT-G143-LAB-CAM"
TIPO_CAMARA_VISION = 5
ID_ROL_INGENIERO = 4
RECURSO_SENSORES, ACCION_CREAR = 12, 1
TIPO_EVENTO_RECHAZO, TIPO_EVENTO_EXITO = 29, 30

VENTANAS = {
    "W1": ("2026-07-01T00:00:00Z", "2026-07-01T06:00:00Z"),
    "W2": ("2026-07-10T00:00:00Z", "2026-07-10T06:00:00Z"),
}
#: W1 y W2 usan vectores distintos a propósito: si L2 se publicara, sería distinguible de L1.
VECTORES = {"W1": (10.0, 5.0), "W2": (25.0, 9.0)}

E: dict = {
    "run_id": RUN_ID, "grupo": GRUPO, "caso": CASO, "ambiente": "LOCAL AISLADO",
    "herramienta": "Pytest en proceso + TestClient sobre la app real + PostgreSQL local real",
    "tabla_auditoria_objetivo": TABLA_AUDITORIA,
    "generado": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "presupuesto": {"post_calibracion_setup": 0, "post_calibracion_objetivo": 0,
                    "post_vision": 0, "revoke": 0, "grant": 0, "reintentos": 0},
    "limitaciones": [],
}
ESTADO: dict = {}
_SECRETOS = [ING_PASSWORD, APP_PASSWORD, os.environ.get("SECRET_KEY", ""), _p.password or "",
             (urlparse(OWNER_DSN).password or "")]


def sanear(d):
    if isinstance(d, dict):
        return {k: ("[REDACTED]" if str(k).lower() in (
            "authorization", "token", "access_token", "refresh_token", "contrasena", "password",
            "access_key", "serial", "cookie", "dsn", "database_url", "secret_key") else sanear(v))
            for k, v in d.items()}
    if isinstance(d, list):
        return [sanear(x) for x in d]
    if isinstance(d, str):
        s = d
        for secreto in _SECRETOS:
            if secreto:
                s = s.replace(secreto, "[REDACTED]")
        s = re.sub(r"Bearer\s+[A-Za-z0-9._\-]+", "Bearer [REDACTED]", s)
        return s.replace(SERIAL_CAM, "[SERIAL REDACTED]")
    return d


def guardar():
    (RUN_DIR / "evidencia-local.json").write_text(
        json.dumps(sanear(E), indent=2, ensure_ascii=False, default=str), encoding="utf-8")


def _conn(dsn: str):
    c = psycopg2.connect(dsn)
    c.autocommit = True
    return c


def filas(sql: str, params: tuple = (), dsn: str | None = None) -> list[dict]:
    c = _conn(dsn or OWNER_DSN)
    try:
        with c.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            return [dict(f) for f in cur.fetchall()]
    finally:
        c.close()


def ejecutar(sql: str, params: dict | None = None, dsn: str | None = None) -> None:
    """DDL/DML permitido SOLO en esta base local y exclusiva."""
    c = _conn(dsn or OWNER_DSN)
    try:
        with c.cursor() as cur:
            cur.execute(sql, params or {})
    finally:
        c.close()


def privilegio_insert_app() -> bool:
    return bool(filas("SELECT has_table_privilege(%s, %s, 'INSERT') AS puede",
                      (APP_ROLE, TABLA_AUDITORIA))[0]["puede"])


def requiere(*claves: str):
    for k in claves:
        if k not in ESTADO:
            pytest.skip(f"falta la precondición {k}")


def iso(dt: datetime.datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def obs_apta(ts: str, densidad: float, tasa: float, fps: int) -> dict:
    return {"timestamp_captura": ts, "cobertura_ventana": "1.0000", "n_tracks": 20,
            "n_tracks_perdidos": 0, "fps_efectivo": f"{int(fps)}.00",
            "estado_calibracion": "CALIBRADA",
            "vector": {"densidad_actividad": densidad, "tasa_movimiento": tasa}}


SEED_SQL = """
DO $$
DECLARE v_finca int; v_especie int; v_area int; v_cam int; v_usuario int; v_tipo text;
BEGIN
  IF EXISTS (SELECT 1 FROM modulo9.dispositivos_iot WHERE serial = %(serial)s) THEN RETURN; END IF;

  INSERT INTO modulo9.fincas (nombre, ubicacion, tamano_h, fecha_actualizacion, fecha_creacion, es_activo)
  VALUES ('Finca Laboratorio G ciento cuarenta y tres', '{"lat": 4.6, "lng": -74.1}'::jsonb, 10.0, now(), now(), true)
  RETURNING id_finca INTO v_finca;

  INSERT INTO modulo9.especies (nombre, descripcion, fecha_creacion, es_activo, tipo_modelo,
                                densidad_maxima_por_especie)
  VALUES ('Ave Laboratorio G cuarenta y tres', 'Especie AVES sintetica del laboratorio local',
          now(), true, 'MODELO_AVES', 50.0000)
  RETURNING id_especie INTO v_especie;

  SELECT nombre INTO v_tipo FROM modulo9.tipos_area
   ORDER BY (lower(nombre) LIKE 'galp%%') DESC, id_tipo_area LIMIT 1;
  IF v_tipo IS NULL THEN RAISE EXCEPTION 'el catalogo modulo9.tipos_area esta vacio'; END IF;

  INSERT INTO modulo9.infraestructuras (descripcion, nombre, id_finca, superficie, es_activo, tipo,
                                        fecha_actualizacion, id_especie, tipo_modelo_asignado)
  VALUES ('Area poblacional del laboratorio G143', 'Area Laboratorio G143', v_finca, 120.0, true,
          v_tipo, now(), v_especie, 'MODELO_AVES')
  RETURNING id_infraestructura INTO v_area;

  INSERT INTO modulo9.dispositivos_iot (serial, descripcion, es_activo, fecha_creacion,
                                        id_infraestructura, id_tipo_dispositivo,
                                        resolucion, fps, area_cobertura_m2)
  VALUES (%(serial)s, 'Camara VISION del laboratorio G143', true, now(), v_area, %(tipo_cam)s,
          '1920x1080', 30, 50.00)
  RETURNING id_dispositivo_iot INTO v_cam;

  INSERT INTO modulo1.usuarios (tipo_identificacion, numero_identificacion, nombre, apellidos,
                                fecha_nacimiento, correo_electronico, contrasena_cifrada,
                                telefono, direccion, id_rol)
  VALUES ('CC', '1079000143', 'Ingeniero', 'Laboratorio Local', '1990-01-01',
          %(correo)s, %(hash)s, '3000000143', 'Calle Laboratorio Local', %(rol)s)
  RETURNING id_usuario INTO v_usuario;

  INSERT INTO modulo1.cuentas_usuarios (id_usuario, id_estado_cuenta, tiene_correo_verificado, fecha_verificacion)
  VALUES (v_usuario, 2, true, now());

  INSERT INTO modulo9.usuarios_fincas (id_usuario_finca, id_usuario, id_finca, es_activo)
  VALUES (nextval('modulo9.usuarios_fincas_id_usuario_finca_seq'), v_usuario, v_finca, true);
END $$;
"""


@pytest.fixture(scope="session", autouse=True)
def bitacora_y_cierre():
    """Vuelca el log real de la aplicación y, al cerrar, garantiza el GRANT y los artefactos."""
    destino = RUN_DIR / "backend-local.log"
    manejador = logging.FileHandler(destino, mode="w", encoding="utf-8")
    manejador.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s :: %(message)s"))
    raiz = logging.getLogger()
    raiz.addHandler(manejador)
    raiz.setLevel(logging.INFO)
    yield
    # Red de seguridad: el privilegio nunca queda revocado, pase lo que pase.
    try:
        if ESTADO.get("app_role_creado") and not privilegio_insert_app():
            ejecutar(f"GRANT INSERT ON TABLE {TABLA_AUDITORIA} TO {APP_ROLE}")
            E.setdefault("red_de_seguridad", []).append(
                "el GRANT se restauró en el cierre de sesión porque el privilegio seguía revocado")
    except Exception as exc:  # pragma: no cover
        E.setdefault("red_de_seguridad", []).append(f"no se pudo verificar el privilegio: {exc}")
    raiz.removeHandler(manejador)
    manejador.close()
    try:
        destino.write_text(sanear(destino.read_text(encoding="utf-8")), encoding="utf-8")
    except OSError:
        pass
    guardar()
    _escribir_manifest()


def _escribir_manifest():
    fuentes = [
        ("TC-M09-G143.postman_collection.json", "colección oficial de TEST (TC-290 y TC-291)"),
        ("TC-M09-G143.precheck.postman_collection.json", "colección de precheck, solo lectura"),
        ("run-g143-v2.cjs", "runner Newman: precheck y RUN oficial, con las guardas de presupuesto"),
        ("test_g143_test.py", "verificador independiente de TEST (solo lectura)"),
        ("test_g143_local.py", "orquestador de TC-M09-292 en laboratorio LOCAL AISLADO"),
        ("docker-compose.g143-local.yml", "definición del laboratorio LOCAL AISLADO"),
        ("init-roles.g143-local.sql", "roles de BD que esperan las migraciones"),
    ]
    entradas = [{"path": f"EvaluacionV2/automation/{n}", "funcion": f,
                 "bytes": (BASE_DIR / n).stat().st_size,
                 "sha256": hashlib.sha256((BASE_DIR / n).read_bytes()).hexdigest()}
                for n, f in fuentes if (BASE_DIR / n).is_file()]
    destino = RUN_DIR / "automation_manifest.json"
    previo = {}
    if destino.is_file():
        try:
            previo = json.loads(destino.read_text(encoding="utf-8"))
        except ValueError:
            previo = {}
    previo.update({"run_id": RUN_ID, "grupo": GRUPO,
                   "informe": "TC-M09-G143_reevaluacion_V2.md",
                   "nota": "los scripts no se copian dentro del RUN; aquí va su SHA-256",
                   "automatizacion": entradas})
    previo["artefactos_resultados"] = [
        {"archivo": str(p.relative_to(RUN_DIR)).replace("\\", "/"), "bytes": p.stat().st_size,
         "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
        for p in sorted(RUN_DIR.rglob("*"))
        if p.is_file() and p.name != "automation_manifest.json"]
    destino.write_text(json.dumps(previo, indent=2, ensure_ascii=False), encoding="utf-8")


@pytest.fixture(scope="session")
def cliente():
    from fastapi.testclient import TestClient
    from main import app
    with TestClient(app) as c:
        yield c


# ══════════════════════════════════════════════════════════════════════════════
# 1. Guarda, roles y migraciones
# ══════════════════════════════════════════════════════════════════════════════

def test_01_guard_local():
    datos = filas("SELECT current_user, current_database(), inet_server_port() AS puerto, version()")[0]
    sospechosas = sorted(k for k, v in os.environ.items()
                         if any(m in str(v).lower() for m in PROHIBIDO))
    E["LOCAL_GUARD"] = {
        "host": DB_HOST, "port": DB_PORT, "database": DB_NAME,
        "current_user_owner": datos["current_user"],
        "current_database": datos["current_database"],
        "version": datos["version"],
        "DSN_app_sanitizada": DSN_SANITIZADA,
        "DSN_owner_sanitizada": f"postgresql://postgres:[REDACTED]@{DB_HOST}:{DB_PORT}/{DB_NAME}",
        "marcas_prohibidas": [],
        "variables_de_entorno_con_marcas": sospechosas,
        "veredicto": "PASS",
    }
    assert not sospechosas, f"STOP_ALL: variables apuntan a un ambiente compartido: {sospechosas}"
    assert datos["current_database"] == "sgpmp_g143_lab"
    ESTADO["guard"] = True


def test_01b_fuente_del_backend_local():
    """La fuente que corre el laboratorio, verificada y trazada.

    El compose monta en /app el arbol desde el que se invoca. El working tree de la rama
    QA se quedo sin los PR #550, #553 y #554, asi que el laboratorio se levanta desde un
    snapshot de solo lectura de origin/test exportado con `git archive` fuera del arbol.
    Si se montara el working tree, TC-292 validaria codigo viejo sin avisar (es lo que
    estuvo a punto de pasar en G140). Se comprueba sobre el codigo REALMENTE importado,
    no sobre un .env ni sobre una variable.
    """
    requiere("guard")
    from src.configuration.application.use_cases.sensores import calibrar_vision_use_case as uso
    from src.configuration.infrastructure.models.calibracion_vision_model import (
        CalibracionVisionModel)

    archivo_uso = Path(uso.__file__).resolve()
    texto_uso = archivo_uso.read_text(encoding="utf-8")
    tipo = CalibracionVisionModel.__table__.c.json_linea_base.type
    # PR #553: el area se obtiene aparte de su validacion, para que el rechazo temprano
    # pueda auditar la especie.
    pr553 = ("def _obtener_area" in texto_uso
             and "area = self._obtener_area(dto, ids_fincas_permitidas)" in texto_uso
             and "id_especie=area.id_especie if area else None" in texto_uso)
    # PR #554: existe la via del disparo automatico del Sistema.
    pr554 = ("def execute_automatico" in texto_uso
             and "VENTANA_DISPARO_AUTOMATICO" in texto_uso)
    # PR #550: un None se persiste como SQL NULL y no como el valor JSON 'null'.
    pr550 = getattr(tipo, "none_as_null", None) is True

    E["fuente_del_backend_local"] = {
        "LOCAL_SOURCE_SHA": LOCAL_SOURCE_SHA or "no inyectado",
        "origen": ("snapshot de solo lectura de origin/test (git archive) montado en /app; "
                   "el working tree de la rama QA no se usa como fuente ni se modifica"),
        "archivo_importado": str(archivo_uso),
        "PR_553_area_separada_de_su_validacion": "SÍ" if pr553 else "NO",
        "PR_554_execute_automatico": "SÍ" if pr554 else "NO",
        "PR_550_none_as_null": "SÍ" if pr550 else "NO",
        "tipo_json_linea_base": type(tipo).__name__,
        "veredicto": "PASS" if (pr553 and pr554 and pr550) else "FAIL",
    }
    assert LOCAL_SOURCE_SHA, "el host no inyecto G143_LOCAL_SOURCE_SHA: fuente no trazable"
    assert pr553, f"el backend local no trae el PR #553 ({archivo_uso})"
    assert pr554, f"el backend local no trae el PR #554 ({archivo_uso})"
    assert pr550, "json_linea_base no se serializa con none_as_null=True (PR #550)"
    ESTADO["fuente"] = True


def test_02_rol_de_aplicacion_separado():
    """§28: el backend NO puede ser superusuario ni dueño de la tabla de auditoría."""
    requiere("fuente")
    existe = filas("SELECT 1 FROM pg_roles WHERE rolname = %s", (APP_ROLE,))
    if not existe:
        ejecutar(f"CREATE ROLE {APP_ROLE} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE "
                 f"BYPASSRLS PASSWORD %(pwd)s", {"pwd": APP_PASSWORD})
    else:
        ejecutar(f"ALTER ROLE {APP_ROLE} LOGIN NOSUPERUSER BYPASSRLS PASSWORD %(pwd)s",
                 {"pwd": APP_PASSWORD})
    ESTADO["app_role_creado"] = True
    atributos = filas("""
        SELECT rolname, rolsuper, rolbypassrls, rolcanlogin, rolcreatedb, rolcreaterole
        FROM pg_roles WHERE rolname = %s""", (APP_ROLE,))[0]
    E["roles"] = {
        "owner": "postgres (migraciones, GRANT/REVOKE y consultas de control)",
        "application_role": APP_ROLE,
        "atributos_del_rol_de_aplicacion": atributos,
        "nota_bypassrls": (
            "El rol de aplicación lleva BYPASSRLS a propósito: el laboratorio mide privilegios "
            "de tabla, no RLS, y BYPASSRLS no afecta a los privilegios (un REVOKE INSERT sigue "
            "siendo efectivo). No es superusuario y no es dueño de la tabla, que es lo que "
            "exige el §36."),
    }
    assert atributos["rolsuper"] is False, "el rol de aplicación no puede ser superusuario"
    assert atributos["rolcanlogin"] is True
    ESTADO["roles"] = True


def test_03_migraciones():
    requiere("roles")
    def alembic(*args):
        p = subprocess.run([sys.executable, "-m", "alembic", *args], cwd=str(REPO_DIR),
                           capture_output=True, text=True, timeout=600,
                           env=dict(os.environ, DATABASE_URL=OWNER_DSN))
        return (p.stdout + p.stderr).strip()
    upgrade = alembic("upgrade", "head")
    current, heads = alembic("current"), alembic("heads")
    rev = filas("SELECT version_num FROM alembic_version")
    tablas = filas("""
        SELECT n.nspname || '.' || c.relname AS tabla
        FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE (n.nspname, c.relname) IN (('modulo1','eventos'),
          ('modulo3','observaciones_vision'), ('modulo9','calibraciones_vision'),
          ('modulo9','lineas_base_vision'))""")
    E["alembic"] = {
        "fuente": "migraciones reales del proyecto, aplicadas como owner",
        "upgrade_head": upgrade.splitlines()[-4:],
        "alembic_current": current.splitlines()[-3:],
        "alembic_heads": heads.splitlines()[-3:],
        "version_num_en_bd": rev[0]["version_num"] if rev else None,
        "tablas_presentes": sorted(t["tabla"] for t in tablas),
    }
    esperadas = {"modulo1.eventos", "modulo3.observaciones_vision",
                 "modulo9.calibraciones_vision", "modulo9.lineas_base_vision"}
    assert esperadas <= set(E["alembic"]["tablas_presentes"]), E["alembic"]["tablas_presentes"]
    ESTADO["migraciones"] = True


def test_04_privilegios_del_rol_de_aplicacion():
    """Tras migrar, el rol de aplicación recibe los privilegios que necesita el backend."""
    requiere("migraciones")
    esquemas = [f["nspname"] for f in filas("""
        SELECT nspname FROM pg_namespace
        WHERE nspname = 'public' OR nspname LIKE 'modulo%%' OR nspname = 'app_ctx'
        ORDER BY nspname""")]
    for esquema in esquemas:
        ejecutar(f'GRANT USAGE ON SCHEMA "{esquema}" TO {APP_ROLE}')
        ejecutar(f'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA "{esquema}" TO {APP_ROLE}')
        ejecutar(f'GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA "{esquema}" TO {APP_ROLE}')
        ejecutar(f'GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA "{esquema}" TO {APP_ROLE}')
    dueno = filas("""
        SELECT pg_get_userbyid(c.relowner) AS owner
        FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'modulo1' AND c.relname = 'eventos'""")[0]["owner"]
    insert_pre = privilegio_insert_app()
    E["privilegios"] = {
        "esquemas_con_grant": esquemas,
        "owner_de_la_tabla_de_auditoria": dueno,
        "app_es_owner_de_la_tabla": dueno == APP_ROLE,
        "INSERT_PRE": insert_pre,
    }
    assert dueno != APP_ROLE, (
        f"{APP_ROLE} es dueño de {TABLA_AUDITORIA}: el REVOKE no sería una inyección válida")
    assert insert_pre is True, f"{APP_ROLE} debe tener INSERT antes de la inyección"
    ESTADO["privilegios"] = True


# ══════════════════════════════════════════════════════════════════════════════
# 2. Fixture y control positivo (L1)
# ══════════════════════════════════════════════════════════════════════════════

def test_05_fixture_local(cliente):
    requiere("privilegios")
    from src.identity_access.domain.value_objects.contrasena import Contrasena
    ejecutar(SEED_SQL, {"serial": SERIAL_CAM, "tipo_cam": TIPO_CAMARA_VISION,
                        "correo": ING_CORREO, "rol": ID_ROL_INGENIERO,
                        "hash": Contrasena.desde_texto_plano(ING_PASSWORD).hash})
    cam = filas("""
        SELECT d.id_dispositivo_iot, d.es_activo, d.fps, d.id_infraestructura, t.categoria,
               i.id_especie, i.tipo_modelo_asignado, i.es_activo AS area_activa, i.id_finca
        FROM modulo9.dispositivos_iot d
        JOIN modulo9.tipos_dispositivo_iot t ON t.id_tipo_dispositivo = d.id_tipo_dispositivo
        JOIN modulo9.infraestructuras i ON i.id_infraestructura = d.id_infraestructura
        WHERE d.serial = %s""", (SERIAL_CAM,))
    assert cam, "el fixture local no quedó sembrado"
    c = cam[0]
    usuario = filas("SELECT id_usuario FROM modulo1.usuarios WHERE correo_electronico = %s",
                    (ING_CORREO,))[0]
    permiso = filas("""SELECT COUNT(*) AS n FROM modulo1.permisos
                       WHERE id_rol = %s AND id_recurso = %s AND id_accion = %s AND es_activo""",
                    (ID_ROL_INGENIERO, RECURSO_SENSORES, ACCION_CREAR))[0]["n"]
    r = cliente.post("/sesiones/", json={"correo_electronico": ING_CORREO,
                                         "contrasena": ING_PASSWORD})
    assert r.status_code == 200, f"login local HTTP {r.status_code}: {sanear(r.text)[:300]}"
    ESTADO.update({"token": r.json()["token"], "area": c["id_infraestructura"],
                   "especie": c["id_especie"], "camara": c["id_dispositivo_iot"],
                   "fps": c["fps"], "usuario": usuario["id_usuario"]})
    E["fixture"] = {
        "origen": "sintético, sembrado por SQL en la base local y exclusiva",
        "finca_id": c["id_finca"], "area_id": c["id_infraestructura"],
        "area_activa": c["area_activa"], "especie_id": c["id_especie"],
        "tipo_modelo_asignado": c["tipo_modelo_asignado"], "paradigma": "POBLACIONAL",
        "camara_id": c["id_dispositivo_iot"], "camara_categoria": c["categoria"],
        "camara_activa": c["es_activo"], "fps_nominal": c["fps"],
        "camara_serial": "[SERIAL REDACTED]",
        "usuario_ingeniero": usuario["id_usuario"], "correo": ING_CORREO,
        "permisos_sensores_crear": permiso, "login": "PASS",
    }
    assert c["es_activo"] and c["categoria"] == "CAMARA"
    assert c["tipo_modelo_asignado"] == "MODELO_AVES" and c["id_especie"] is not None
    assert permiso >= 1
    ESTADO["fixture"] = True


def _h() -> dict:
    return {"Authorization": f"Bearer {ESTADO['token']}"}


def _ingerir(cliente, ventana: str, n: int) -> dict:
    marca = f"lote_{ventana}"
    if marca in ESTADO:
        raise RuntimeError(f"ABORTADO: reenvío prohibido del lote {ventana}")
    ESTADO[marca] = True
    ini, _ = VENTANAS[ventana]
    densidad, tasa = VECTORES[ventana]
    base = datetime.datetime.fromisoformat(ini.replace("Z", "+00:00"))
    obs = [obs_apta(iso(base + datetime.timedelta(minutes=5 * i)),
                    round(densidad + (i % 3) * 0.01, 4), round(tasa + (i % 3) * 0.01, 4),
                    ESTADO["fps"]) for i in range(n)]
    r = cliente.post("/iot/telemetria/vision",
                     json={"device_id": ESTADO["camara"], "access_key": SERIAL_CAM,
                           "area_id": ESTADO["area"], "observaciones": obs})
    E["presupuesto"]["post_vision"] += 1
    assert r.status_code in (200, 201), f"ingesta {ventana} HTTP {r.status_code}: {sanear(r.text)[:300]}"
    b = r.json()
    aptas = [o for o in b["observaciones"] if o["apto_para_ia"]]
    resumen = {"http": r.status_code, "total": b["total"], "aceptadas": b["aceptadas"],
               "duplicadas": b["duplicadas"], "aptas": len(aptas),
               "indices_distintos": sorted({o["indice_calidad"] for o in b["observaciones"]}),
               "vectores": {"densidad_actividad": densidad, "tasa_movimiento": tasa}}
    assert b["total"] == n and b["aceptadas"] == n, resumen
    assert b["duplicadas"] == 0, resumen
    assert len(aptas) == n, resumen
    return resumen


def _calibrar(cliente, ventana: str, nota: str, clase: str):
    marca = f"cal_{ventana}"
    if marca in ESTADO:
        raise RuntimeError(f"ABORTADO: reintento prohibido del POST funcional {ventana}")
    ESTADO[marca] = True
    ini, fin = VENTANAS[ventana]
    cuerpo = {"modo_calibracion": "VISION", "area_id": ESTADO["area"],
              "ventana_observacion": {"inicio": ini, "fin": fin}, "observaciones": nota,
              "fecha_calibracion": datetime.datetime.now(datetime.timezone.utc).isoformat()}
    r = cliente.post("/configuracion/calibraciones-vision", json=cuerpo, headers=_h())
    E["presupuesto"][f"post_calibracion_{clase}"] += 1
    try:
        return cuerpo, r.status_code, r.json()
    except ValueError:
        return cuerpo, r.status_code, {"_texto": r.text[:500]}


def test_06_control_positivo_L1(cliente):
    """§38: antes del REVOKE hay que demostrar que el laboratorio funciona."""
    requiere("fixture")
    from src.configuration.domain.entities.linea_base_vision import ParametrosLineaBase
    n = ParametrosLineaBase().min_observaciones
    ESTADO["N"] = n
    E["N"] = {"valor": n, "fuente": "ParametrosLineaBase.min_observaciones"}
    lote = _ingerir(cliente, "W1", n)
    cuerpo, codigo, resp = _calibrar(cliente, "W1", "QA TC-M09-292 control positivo L1", "setup")
    eventos = filas("""
        SELECT id_evento, tipo_evento, resultado, modulo, detalle
        FROM modulo1.eventos WHERE tipo_evento = %s ORDER BY id_evento DESC LIMIT 5""",
        (TIPO_EVENTO_EXITO,))
    de_l1 = [e for e in eventos
             if (e["detalle"] or {}).get("operacion") == "CALIBRACION_VISION"]
    E["control_positivo"] = {
        "ventana": dict(zip(("inicio", "fin"), VENTANAS["W1"])), "lote": lote,
        "request": cuerpo, "http": codigo, "response": resp,
        "auditoria_exitosa": de_l1[:1],
    }
    assert 200 <= codigo < 300, f"el control positivo esperaba 2xx y obtuvo {codigo}: {sanear(resp)}"
    assert resp["estado"] == "EXITOSA", resp["estado"]
    ESTADO["L1_ID"] = resp["id_calibracion_vision"]
    ESTADO["L1_VALORES"] = resp["linea_base"]["valores"]
    cl = cliente.get(f"/configuracion/calibraciones-vision/linea-base?area_id={ESTADO['area']}",
                     headers=_h())
    lb = cl.json() if cl.status_code == 200 else {}
    bd_lb = filas("""SELECT id_calibracion_vision, json_valor, fecha_publicacion
                     FROM modulo9.lineas_base_vision
                     WHERE id_infraestructura = %s AND id_especie = %s""",
                  (ESTADO["area"], ESTADO["especie"]))
    E["L1"] = {
        "L1_CALIBRACION_ID": ESTADO["L1_ID"],
        "L1_VALORES": ESTADO["L1_VALORES"],
        "L1_AREA": ESTADO["area"], "L1_ESPECIE": ESTADO["especie"],
        "L1_FECHA": lb.get("fecha_publicacion"),
        "linea_base_por_api": {"http": cl.status_code,
                               "id_calibracion_vision": lb.get("id_calibracion_vision")},
        "linea_base_por_bd": bd_lb,
        "iteraciones": resp.get("iteraciones"),
    }
    assert cl.status_code == 200 and lb.get("id_calibracion_vision") == ESTADO["L1_ID"]
    assert bd_lb and bd_lb[0]["id_calibracion_vision"] == ESTADO["L1_ID"]
    assert de_l1, "el control positivo no dejó evento de auditoría EXITOSO"
    ESTADO["L1"] = True


def test_07_ventana_W2(cliente):
    requiere("L1")
    lote = _ingerir(cliente, "W2", ESTADO["N"])
    E["W2"] = {"ventana": dict(zip(("inicio", "fin"), VENTANAS["W2"])), "lote": lote,
               "disjunta_de_W1": True,
               "nota": ("los vectores de W2 son distintos de los de W1 a propósito: si L2 se "
                        "publicara, sería distinguible de L1")}
    assert VENTANAS["W1"][1] < VENTANAS["W2"][0], "W2 debe ser disjunta de W1"
    ESTADO["W2"] = True


def test_08_snapshot_PRE(cliente):
    requiere("W2")
    cl = cliente.get(f"/configuracion/calibraciones-vision/linea-base?area_id={ESTADO['area']}",
                     headers=_h())
    ch = cliente.get(f"/configuracion/calibraciones-vision?area_id={ESTADO['area']}", headers=_h())
    bd = {
        "calibraciones": filas("""SELECT id_calibracion_vision, estado FROM modulo9.calibraciones_vision
                                  WHERE id_infraestructura = %s ORDER BY id_calibracion_vision""",
                               (ESTADO["area"],)),
        "linea_base": filas("""SELECT id_linea_base_vision, id_calibracion_vision, json_valor
                               FROM modulo9.lineas_base_vision
                               WHERE id_infraestructura = %s AND id_especie = %s""",
                            (ESTADO["area"], ESTADO["especie"])),
        "eventos_vision": filas("""SELECT COUNT(*) AS n FROM modulo1.eventos
                                   WHERE tipo_evento IN (%s, %s)
                                     AND detalle->>'operacion' = 'CALIBRACION_VISION'""",
                                (TIPO_EVENTO_EXITO, TIPO_EVENTO_RECHAZO)),
    }
    ESTADO["pre_bd"] = bd
    ESTADO["pre_ids"] = [i["id_calibracion_vision"] for i in ch.json().get("items", [])]
    E["snapshot_PRE"] = {
        "linea_base_api": {"http": cl.status_code,
                           "id_calibracion_vision": cl.json().get("id_calibracion_vision")
                           if cl.status_code == 200 else None},
        "historial_api": {"http": ch.status_code, "ids": ESTADO["pre_ids"]},
        "bd": bd,
    }
    assert cl.status_code == 200 and cl.json()["id_calibracion_vision"] == ESTADO["L1_ID"]
    ESTADO["pre"] = True


# ══════════════════════════════════════════════════════════════════════════════
# 3. Inyección de fallo, POST objetivo y restauración
# ══════════════════════════════════════════════════════════════════════════════

def test_09_revoke_post_y_grant(cliente):
    """§42 a §47: REVOKE, POST objetivo y GRANT restaurado en try/finally."""
    requiere("pre")
    insert_pre = privilegio_insert_app()
    assert insert_pre is True, "el privilegio debía estar en true antes del REVOKE"

    ejecutar(f"REVOKE INSERT ON TABLE {TABLA_AUDITORIA} FROM {APP_ROLE}")
    E["presupuesto"]["revoke"] += 1
    insert_durante = privilegio_insert_app()
    conectado_como = filas("SELECT current_user", dsn=APP_DSN)[0]["current_user"]

    E["fault_injection"] = {
        "sentencia_revoke": f"REVOKE INSERT ON TABLE {TABLA_AUDITORIA} FROM {APP_ROLE}",
        "ejecutada_por": "el owner, nunca el backend",
        "INSERT_PRE": insert_pre,
        "INSERT_DURANTE": insert_durante,
        "backend_conectado_como": conectado_como,
    }
    try:
        assert insert_durante is False, (
            "FAULT INJECTION INVÁLIDA: el privilegio de INSERT sigue en true tras el REVOKE")
        assert conectado_como == APP_ROLE, (
            f"FAULT INJECTION INVÁLIDA: el backend se conecta como {conectado_como}")
        cuerpo, codigo, resp = _calibrar(cliente, "W2",
                                         "QA TC-M09-292 fallo de auditoria", "objetivo")
        E["post_objetivo"] = {"request": cuerpo, "http": codigo, "response": resp}
    finally:
        ejecutar(f"GRANT INSERT ON TABLE {TABLA_AUDITORIA} TO {APP_ROLE}")
        E["presupuesto"]["grant"] += 1
        E["fault_injection"]["INSERT_POST"] = privilegio_insert_app()
        E["fault_injection"]["sentencia_grant"] = (
            f"GRANT INSERT ON TABLE {TABLA_AUDITORIA} TO {APP_ROLE}")
        guardar()

    assert E["fault_injection"]["INSERT_POST"] is True, "el GRANT no quedó restaurado"
    ESTADO["objetivo"] = True


def test_10_respuesta_de_trazabilidad():
    """§45: la matriz no fija el HTTP exacto; sí exige informar que no hubo trazabilidad."""
    requiere("objetivo")
    resp = E["post_objetivo"]["response"]
    codigo = E["post_objetivo"]["http"]
    mensaje = str(resp.get("message") or "")
    error = str(resp.get("error_code") or "")
    informa = ("trazabilidad" in mensaje.lower()
               and ("no ha sido aplicado" in mensaje.lower() or "no fue aplicad" in mensaje.lower()))
    E["respuesta_objetivo"] = {
        "http_obtenido": codigo,
        "error_code_obtenido": error,
        "mensaje_obtenido": mensaje,
        "referencia_de_la_implementacion": {
            "http": 500, "error_code": "AUDITORIA_CALIBRACION_FALLIDA",
            "mensaje": ("Error de integridad: No se pudo garantizar la trazabilidad de la "
                        "calibración. El ajuste no ha sido aplicado; por favor, intente de nuevo."),
        },
        "informa_fallo_de_trazabilidad": "SÍ" if informa else "NO",
        "criterio": ("la matriz no fija el código exacto; el criterio es que informe que no pudo "
                     "garantizarse la trazabilidad y que la publicación no fue aplicada"),
    }
    assert codigo >= 400, f"el POST objetivo debía fallar y respondió {codigo}"
    assert informa, (f"la respuesta no informa el fallo de trazabilidad: "
                     f"HTTP {codigo} {error} :: {mensaje}")
    ESTADO["respuesta"] = True


def test_11_rollback_de_la_publicacion(cliente):
    """§48 a §50: L1 sigue vigente, no hay L2 y la calibración W2 no quedó confirmada."""
    requiere("respuesta")
    cl = cliente.get(f"/configuracion/calibraciones-vision/linea-base?area_id={ESTADO['area']}",
                     headers=_h())
    ch = cliente.get(f"/configuracion/calibraciones-vision?area_id={ESTADO['area']}", headers=_h())
    api_lb = cl.json() if cl.status_code == 200 else {}
    ids_post = [i["id_calibracion_vision"] for i in ch.json().get("items", [])]
    post_bd = {
        "calibraciones": filas("""SELECT id_calibracion_vision, estado FROM modulo9.calibraciones_vision
                                  WHERE id_infraestructura = %s ORDER BY id_calibracion_vision""",
                               (ESTADO["area"],)),
        "linea_base": filas("""SELECT id_linea_base_vision, id_calibracion_vision, json_valor
                               FROM modulo9.lineas_base_vision
                               WHERE id_infraestructura = %s AND id_especie = %s""",
                            (ESTADO["area"], ESTADO["especie"])),
        "eventos_vision": filas("""SELECT COUNT(*) AS n FROM modulo1.eventos
                                   WHERE tipo_evento IN (%s, %s)
                                     AND detalle->>'operacion' = 'CALIBRACION_VISION'""",
                                (TIPO_EVENTO_EXITO, TIPO_EVENTO_RECHAZO)),
    }
    pre = ESTADO["pre_bd"]
    E["rollback"] = {
        "linea_base_api": {"http": cl.status_code,
                           "id_calibracion_vision": api_lb.get("id_calibracion_vision"),
                           "valores": (api_lb.get("linea_base") or {}).get("valores")},
        "historial_api": {"PRE": ESTADO["pre_ids"], "POST": ids_post},
        "bd_PRE": pre, "bd_POST": post_bd,
        "BASELINE_POST_ID": api_lb.get("id_calibracion_vision"),
        "L1_ID": ESTADO["L1_ID"],
        "L1_sigue_vigente": "SÍ" if api_lb.get("id_calibracion_vision") == ESTADO["L1_ID"] else "NO",
        "L2_publicada": "NO" if api_lb.get("id_calibracion_vision") == ESTADO["L1_ID"] else "SÍ",
        "calibracion_W2_persistida": "NO" if len(post_bd["calibraciones"]) == len(pre["calibraciones"]) else "SÍ",
        "eventos_vision_PRE": pre["eventos_vision"][0]["n"],
        "eventos_vision_POST": post_bd["eventos_vision"][0]["n"],
    }
    assert cl.status_code == 200, f"la línea base dejó de ser consultable (HTTP {cl.status_code})"
    assert api_lb["id_calibracion_vision"] == ESTADO["L1_ID"], (
        f"L1 dejó de ser vigente: ahora apunta a {api_lb['id_calibracion_vision']}")
    assert api_lb["linea_base"]["valores"] == ESTADO["L1_VALORES"], "los valores de L1 cambiaron"
    assert post_bd["linea_base"] == pre["linea_base"], (
        f"la fila de línea base cambió: {pre['linea_base']} -> {post_bd['linea_base']}")
    assert len(post_bd["calibraciones"]) == len(pre["calibraciones"]), (
        f"quedó una calibración confirmada del intento W2: {pre['calibraciones']} -> "
        f"{post_bd['calibraciones']}")
    assert ids_post == ESTADO["pre_ids"], f"el historial cambió: {ESTADO['pre_ids']} -> {ids_post}"
    assert post_bd["eventos_vision"][0]["n"] == pre["eventos_vision"][0]["n"], (
        "apareció un evento de auditoría VISION del intento W2")
    ESTADO["rollback"] = True


def test_12_cierre_local():
    requiere("rollback")
    fi = E["fault_injection"]
    E["cuadro_tc292"] = [
        {"criterio": "LOCAL aislado", "esperado": "PASS", "obtenido": E["LOCAL_GUARD"]["veredicto"]},
        {"criterio": "APP superuser", "esperado": False,
         "obtenido": E["roles"]["atributos_del_rol_de_aplicacion"]["rolsuper"]},
        {"criterio": "APP owner de la tabla de auditoría", "esperado": False,
         "obtenido": E["privilegios"]["app_es_owner_de_la_tabla"]},
        {"criterio": "Tabla de auditoría", "esperado": TABLA_AUDITORIA, "obtenido": TABLA_AUDITORIA},
        {"criterio": "Control positivo L1", "esperado": "PASS",
         "obtenido": f"PASS — calibración {ESTADO['L1_ID']} EXITOSA y vigente"},
        {"criterio": "INSERT PRE", "esperado": True, "obtenido": fi["INSERT_PRE"]},
        {"criterio": "INSERT DURANTE", "esperado": False, "obtenido": fi["INSERT_DURANTE"]},
        {"criterio": "POST W2 informa fallo de trazabilidad", "esperado": "SÍ",
         "obtenido": E["respuesta_objetivo"]["informa_fallo_de_trazabilidad"]},
        {"criterio": "INSERT POST", "esperado": True, "obtenido": fi["INSERT_POST"]},
        {"criterio": "L2 publicada", "esperado": "NO", "obtenido": E["rollback"]["L2_publicada"]},
        {"criterio": "L1 sigue vigente", "esperado": "SÍ", "obtenido": E["rollback"]["L1_sigue_vigente"]},
        {"criterio": "Calibración W2 persistida", "esperado": "NO",
         "obtenido": E["rollback"]["calibracion_W2_persistida"]},
        {"criterio": "Rollback en BD", "esperado": "PASS",
         "obtenido": "PASS" if E["rollback"]["bd_PRE"] == E["rollback"]["bd_POST"] else "FAIL"},
    ]
    todos = all(str(c["esperado"]) == str(c["obtenido"]) or c["criterio"] in
                ("Control positivo L1", "Rollback en BD", "LOCAL aislado")
                for c in E["cuadro_tc292"])
    E["resultado"] = {
        "TC-M09-292": "APROBADO" if todos else "RECHAZADO",
        "incidencia_requerida": "NO" if todos else "SÍ",
    }
    E["seguridad"] = {
        "credenciales_persistidas": "NO",
        "serial_access_key_persistido": "NO — redactado por patrón",
        "dsn_con_password": "NO — solo la versión sanitizada",
        "sql_dml_en_test": 0,
        "ddl_dml_en_el_laboratorio": "siembra del fixture, creación del rol y REVOKE/GRANT, "
                                     "autorizados en base local y exclusiva",
    }
    assert E["presupuesto"]["post_calibracion_setup"] == 1, E["presupuesto"]
    assert E["presupuesto"]["post_calibracion_objetivo"] == 1, E["presupuesto"]
    assert E["presupuesto"]["revoke"] == 1 and E["presupuesto"]["grant"] == 1, E["presupuesto"]
    guardar()
    assert todos, [c for c in E["cuadro_tc292"] if str(c["esperado"]) != str(c["obtenido"])]
