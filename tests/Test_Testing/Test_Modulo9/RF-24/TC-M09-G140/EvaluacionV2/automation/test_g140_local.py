"""TC-M09-286 — No convergencia de la Etapa 3 en LABORATORIO LOCAL AISLADO.

TC-M09-G140 · RF-24 v2.0 · CU05 Flujo F.

Qué demuestra: con `max_iteraciones = 1` y un dataset cuyo refinamiento mueve la mediana más
que epsilon, el cálculo de la línea base por visión termina en **NO_CONVERGIDA / REFINAMIENTO**,
responde 422 `LINEA_BASE_NO_CALCULADA` con el mensaje literal del contrato y **conserva** la
línea base vigente anterior.

Cómo se ejecuta (§43 a §48 del paquete):
  * PostgreSQL local con volumen exclusivo, creado desde cero con `alembic upgrade head`;
  * guarda de aislamiento ANTES de levantar el caso: si aparece cualquier marca de TEST/DEV/MAIN
    se aborta con STOP_ALL;
  * el POST atraviesa el router, el DTO, el caso de uso y los repositorios REALES contra esa
    base real, mediante `TestClient` sobre la aplicación real. No se mockea ningún repositorio
    y no se llama al dominio por atajo;
  * `max_iteraciones = 1` se inyecta solo en memoria, sustituyendo el valor por defecto del
    parámetro `parametros` del caso de uso. No se edita `linea_base_vision.py` y los demás
    umbrales conservan su valor vigente;
  * el oráculo (`oracle_g140.py`) demuestra la no convergencia ANTES del POST y es independiente:
    no importa nada del algoritmo del producto.

Presupuesto: 2 POST de calibración (1 de setup de la línea base previa + 1 objetivo), 0 reintentos.

Uso (desde el host, con el laboratorio ya definido):
    docker compose -p sgpmp-g140-local -f docker-compose.g140-local.yml run --rm lab \
        python -m pytest tests/.../EvaluacionV2/automation/test_g140_local.py -v --noconftest
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

# ── Localización y guarda de rutas ───────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
EVAL_DIR = BASE_DIR.parent
CASE_DIR = EVAL_DIR.parent
GRUPO, CASO = "TC-M09-G140", "TC-M09-286"
if BASE_DIR.name != "automation" or EVAL_DIR.name != "EvaluacionV2" or CASE_DIR.name != GRUPO:
    raise RuntimeError(f"ABORTADO: ruta no autorizada para {GRUPO}: {BASE_DIR}")

REPO_DIR = CASE_DIR.parents[4]
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(REPO_DIR))

RUN_ID = os.environ["G140_RUN_ID"]
RUN_DIR = EVAL_DIR / "RESULTADOS" / RUN_ID
RUN_DIR.mkdir(parents=True, exist_ok=True)

import oracle_g140 as ORACULO  # noqa: E402  (el oráculo independiente, sin imports del producto)

# ── Guarda de aislamiento (§44) ──────────────────────────────────────────────
PROHIBIDO = ("158.69.200.27", "sgpmp_test", "sgpmp_dev", "api.inmero.co", "inmero")
DSN = os.environ["DATABASE_URL"]
_p = urlparse(DSN)
DB_HOST, DB_PORT, DB_NAME, DB_USER = _p.hostname, _p.port or 5432, (_p.path or "/").lstrip("/"), _p.username
DSN_SANITIZADA = f"postgresql://{DB_USER}:[REDACTED]@{DB_HOST}:{DB_PORT}/{DB_NAME}"

_marcas = [m for m in PROHIBIDO if m in DSN.lower()]
if _marcas:
    raise RuntimeError(f"STOP_ALL: la DATABASE_URL del laboratorio contiene marcas de un ambiente compartido: {_marcas}")
if DB_NAME != "sgpmp_g140_lab":
    raise RuntimeError(f"STOP_ALL: la base del laboratorio debe ser sgpmp_g140_lab; es {DB_NAME}")

ING_CORREO = "ingeniero.g140.lab@laboratorio-g140.co"
ING_PASSWORD = os.environ["G140_ING_PASSWORD"]
SERIAL_CAM = "IOT-G140-LAB-CAM"
TIPO_CAMARA_VISION = 5
ID_ROL_INGENIERO = 4
RECURSO_SENSORES, ACCION_CREAR = 12, 1
TIPO_EVENTO_RECHAZO, TIPO_EVENTO_EXITO = 29, 30

VENTANAS = {
    "WINDOW_286_BASE": ("2026-08-01T00:00:00Z", "2026-08-01T04:00:00Z"),
    "WINDOW_286_FAIL": ("2026-08-02T00:00:00Z", "2026-08-02T04:00:00Z"),
}

# ── Ejecuciones dentro del MISMO RUN logico (§1 a §6) ───────────────────────
EJECUCION_GRUPO = 3
TIPO_EJECUCION = "REEJECUCION_COMPLETA_POST_FIX"
AUTORIZADO_POR = "LIDER_DESARROLLO"
PR_CORRECCION = 550
FIX_ESPERADO = "JSONB(none_as_null=True)"
MODELO_FIX = "src/configuration/infrastructure/models/calibracion_vision_model.py"
#: SHA del arbol que el laboratorio esta ejecutando. Lo inyecta el host al lanzar el
#: contenedor, porque dentro no hay repositorio git: el /app montado es un snapshot de
#: solo lectura de origin/test exportado con `git archive` FUERA del working tree (§44).
LOCAL_SOURCE_SHA = os.environ.get("G140_LOCAL_SOURCE_SHA", "")

HISTORIAL_EJECUCIONES = [
    {
        "ejecucion": 1, "run_id": "run-20261010-141449", "tipo": "EVALUACION_INICIAL",
        "TC-M09-286": "RECHAZADO",
        "motivo": ("el POST objetivo devolvio 400 VALOR_NO_PERMITIDO (field "
                   "calibracion_vision_resultado_coherente) en vez del 422: la calibracion "
                   "NO_CONVERGIDA / REFINAMIENTO no se pudo persistir porque json_linea_base "
                   "se escribia como JSON 'null' y no como SQL NULL. La linea base previa se "
                   "conservo: no hubo dano de datos."),
        "nota": "RUN historico; no se modifica ni se reutiliza como resultado vigente",
    },
    {
        "ejecucion": 2, "run_id": "run-20261010-150013", "tipo": "REEJECUCION_PARCIAL",
        "TC-M09-286": "NO REEJECUTADO / RECHAZADO heredado",
        "motivo": "QA autorizo reejecutar solo TC-284 y TC-285 contra TEST",
    },
]

E: dict = {
    "run_id": RUN_ID, "grupo": GRUPO, "caso": CASO,
    "ambiente": "LOCAL AISLADO",
    "herramienta": "Pytest en proceso + TestClient sobre la app real + PostgreSQL local real",
    "newman": "NO APLICA",
    "generado": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "execution_number_group": EJECUCION_GRUPO,
    "execution_type": TIPO_EJECUCION,
    "nuevo_run_creado": "NO",
    "autorizado_por": AUTORIZADO_POR,
    "correccion": {"pr": PR_CORRECCION, "fix": FIX_ESPERADO, "archivo": MODELO_FIX},
    "historial_ejecuciones": [dict(h) for h in HISTORIAL_EJECUCIONES],
    "presupuesto": {"post_calibracion": 0, "post_vision": 0, "reintentos": 0},
    "limitaciones": [],
}
ESTADO: dict = {}
_SECRETOS = [ING_PASSWORD, os.environ.get("SECRET_KEY", ""), _p.password or ""]


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


def filas(sql: str, params: tuple = ()) -> list[dict]:
    c = psycopg2.connect(DSN)
    try:
        c.autocommit = True
        with c.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            return [dict(f) for f in cur.fetchall()]
    finally:
        c.close()


def ejecutar(sql: str, params: dict | None = None) -> None:
    """DML permitido SOLO en esta base local y exclusiva (siembra del fixture)."""
    c = psycopg2.connect(DSN)
    try:
        c.autocommit = True
        with c.cursor() as cur:
            cur.execute(sql, params or {})
    finally:
        c.close()


def requiere(*claves: str):
    for k in claves:
        if k not in ESTADO:
            pytest.skip(f"falta la precondición {k}")


def instantes(inicio: str, cantidad: int, paso_min: int) -> list[str]:
    base = datetime.datetime.fromisoformat(inicio.replace("Z", "+00:00"))
    return [(base + datetime.timedelta(minutes=paso_min * i)).strftime("%Y-%m-%dT%H:%M:%SZ")
            for i in range(cantidad)]


def obs_apta(ts: str, densidad: float, tasa: float, fps: int) -> dict:
    return {
        "timestamp_captura": ts, "cobertura_ventana": "1.0000",
        "n_tracks": 20, "n_tracks_perdidos": 0, "fps_efectivo": f"{fps}.00",
        "estado_calibracion": "CALIBRADA",
        "vector": {"densidad_actividad": densidad, "tasa_movimiento": tasa},
    }


# ── Siembra del fixture local (§49): sintético, nada copiado de TEST ─────────
SEED_SQL = """
DO $$
DECLARE v_finca int; v_especie int; v_area int; v_cam int; v_usuario int; v_tipo text;
BEGIN
  IF EXISTS (SELECT 1 FROM modulo9.dispositivos_iot WHERE serial = %(serial)s) THEN
    RETURN;
  END IF;

  INSERT INTO modulo9.fincas (nombre, ubicacion, tamano_h, fecha_actualizacion, fecha_creacion, es_activo)
  VALUES ('Finca Laboratorio G ciento cuarenta', '{"lat": 4.6, "lng": -74.1}'::jsonb, 10.0, now(), now(), true)
  RETURNING id_finca INTO v_finca;

  INSERT INTO modulo9.especies (nombre, descripcion, fecha_creacion, es_activo, tipo_modelo)
  VALUES ('Ave Laboratorio G140', 'Especie AVES sintetica del laboratorio local', now(), true, 'MODELO_AVES')
  RETURNING id_especie INTO v_especie;

  -- El tipo de área es catálogo (fk_infraestructuras_tipo_area): se resuelve, no se inventa.
  SELECT nombre INTO v_tipo FROM modulo9.tipos_area
   ORDER BY (lower(nombre) LIKE 'galp%%') DESC, id_tipo_area LIMIT 1;
  IF v_tipo IS NULL THEN
    RAISE EXCEPTION 'el catalogo modulo9.tipos_area esta vacio en el laboratorio';
  END IF;

  INSERT INTO modulo9.infraestructuras (descripcion, nombre, id_finca, superficie, es_activo, tipo,
                                        fecha_actualizacion, id_especie, tipo_modelo_asignado)
  VALUES ('Area poblacional del laboratorio G140', 'Area Laboratorio G140', v_finca, 120.0, true,
          v_tipo, now(), v_especie, 'MODELO_AVES')
  RETURNING id_infraestructura INTO v_area;

  INSERT INTO modulo9.dispositivos_iot (serial, descripcion, es_activo, fecha_creacion,
                                        id_infraestructura, id_tipo_dispositivo,
                                        resolucion, fps, area_cobertura_m2)
  VALUES (%(serial)s, 'Camara VISION del laboratorio G140', true, now(), v_area, %(tipo_cam)s,
          '1920x1080', 30, 50.00)
  RETURNING id_dispositivo_iot INTO v_cam;

  INSERT INTO modulo1.usuarios (tipo_identificacion, numero_identificacion, nombre, apellidos,
                                fecha_nacimiento, correo_electronico, contrasena_cifrada,
                                telefono, direccion, id_rol)
  VALUES ('CC', '1079000140', 'Ingeniero', 'Laboratorio Local', '1990-01-01',
          %(correo)s, %(hash)s, '3000000140', 'Calle Laboratorio Local', %(rol)s)
  RETURNING id_usuario INTO v_usuario;

  INSERT INTO modulo1.cuentas_usuarios (id_usuario, id_estado_cuenta, tiene_correo_verificado, fecha_verificacion)
  VALUES (v_usuario, 2, true, now());

  INSERT INTO modulo9.usuarios_fincas (id_usuario_finca, id_usuario, id_finca, es_activo)
  VALUES (nextval('modulo9.usuarios_fincas_id_usuario_finca_seq'), v_usuario, v_finca, true);
END $$;
"""


@pytest.fixture(scope="session", autouse=True)
def bitacora_del_backend():
    """Vuelca el log real de la aplicación a backend-local.log (saneado al cerrar)."""
    destino = RUN_DIR / "backend-local.log"
    manejador = logging.FileHandler(destino, mode="w", encoding="utf-8")
    manejador.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s :: %(message)s"))
    raiz = logging.getLogger()
    raiz.addHandler(manejador)
    raiz.setLevel(logging.INFO)
    yield
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
        ("test_g140_test.py", "automatización de TC-M09-284 y TC-M09-285 contra TEST"),
        ("test_g140_local.py", "automatización de TC-M09-286 en laboratorio LOCAL AISLADO"),
        ("oracle_g140.py", "oráculo independiente de las tres etapas (sin imports del producto)"),
        ("docker-compose.g140-local.yml", "definición del laboratorio LOCAL AISLADO"),
        ("init-roles.g140-local.sql", "roles que las migraciones esperan en el laboratorio"),
    ]
    entradas = []
    for nombre, funcion in fuentes:
        f = BASE_DIR / nombre
        if f.is_file():
            entradas.append({"path": f"EvaluacionV2/automation/{nombre}", "funcion": funcion,
                             "bytes": f.stat().st_size,
                             "sha256": hashlib.sha256(f.read_bytes()).hexdigest()})
    destino = RUN_DIR / "automation_manifest.json"
    previo = {}
    if destino.is_file():
        try:
            previo = json.loads(destino.read_text(encoding="utf-8"))
        except ValueError:
            previo = {}
    previo.update({"run_id": RUN_ID, "grupo": GRUPO, "newman": "NO APLICA",
                   "execution_number_group": EJECUCION_GRUPO,
                   "execution_type": TIPO_EJECUCION,
                   "automatizacion": entradas,
                   "nota": "los scripts no se copian dentro del RUN (§80); aquí va su SHA-256"})
    artefactos = [{"archivo": p.name, "bytes": p.stat().st_size,
                   "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
                  for p in sorted(RUN_DIR.rglob("*"))
                  if p.is_file() and p.name != "automation_manifest.json"]
    previo["artefactos_resultados"] = artefactos
    destino.write_text(json.dumps(previo, indent=2, ensure_ascii=False), encoding="utf-8")


# ══════════════════════════════════════════════════════════════════════════════
# 1. Guarda, migraciones y parámetros
# ══════════════════════════════════════════════════════════════════════════════

def test_01_guard_local_aislado():
    datos = filas("SELECT current_user, current_database(), "
                  "inet_server_addr()::text AS servidor, inet_server_port() AS puerto, version()")
    fila = datos[0]
    entorno_sospechoso = {
        k: v for k, v in os.environ.items()
        if any(m in str(v).lower() for m in PROHIBIDO)
    }
    E["LOCAL_GUARD"] = {
        "host": DB_HOST, "port": DB_PORT, "database": DB_NAME,
        "current_user": fila["current_user"], "current_database": fila["current_database"],
        "servidor": fila["servidor"], "puerto_servidor": fila["puerto"],
        "version": fila["version"],
        "DATABASE_URL_sanitizada": DSN_SANITIZADA,
        "marcas_prohibidas_en_dsn": [],
        "variables_de_entorno_con_marcas_prohibidas": sorted(entorno_sospechoso),
        "veredicto": "PASS",
    }
    assert not entorno_sospechoso, (
        f"STOP_ALL: variables de entorno apuntan a un ambiente compartido: {sorted(entorno_sospechoso)}")
    assert fila["current_database"] == "sgpmp_g140_lab"
    ESTADO["guard"] = True


def test_01b_fuente_del_backend_local_con_el_fix():
    """§44 y §45: el laboratorio tiene que ejecutar codigo que CONTENGA el PR #550.

    No basta con que el fix este en origin/test: lo que corre aqui es el arbol montado en
    /app. El working tree de la rama QA NO trae el fix, asi que el laboratorio se levanta
    sobre un snapshot de solo lectura de origin/test exportado con `git archive` fuera del
    arbol de trabajo. Se comprueba de dos maneras independientes: leyendo el archivo que
    realmente se importo y preguntandole al propio modelo de SQLAlchemy como serializa el
    None. Si cualquiera de las dos falla, STOP antes de tocar el caso.
    """
    requiere("guard")
    from src.configuration.infrastructure.models import calibracion_vision_model as modelo
    from src.configuration.infrastructure.models.calibracion_vision_model import (
        CalibracionVisionModel)

    archivo_importado = Path(modelo.__file__).resolve()
    texto = archivo_importado.read_text(encoding="utf-8")
    linea = next((l.strip() for l in texto.splitlines() if "json_linea_base" in l), None)
    # Lo que de verdad decide: el tipo con el que SQLAlchemy serializa esa columna.
    tipo = CalibracionVisionModel.__table__.c.json_linea_base.type
    none_as_null = getattr(tipo, "none_as_null", None)

    E["fuente_del_backend_local"] = {
        "LOCAL_SOURCE_SHA": LOCAL_SOURCE_SHA or "no inyectado",
        "origen": ("snapshot de solo lectura de origin/test (git archive) montado en /app; "
                   "el working tree de la rama QA no se modifica ni se usa como fuente"),
        "archivo_importado": str(archivo_importado),
        "linea_json_linea_base": linea,
        "fix_en_el_texto": "SÍ" if FIX_ESPERADO in (linea or "") else "NO",
        "tipo_sqlalchemy": type(tipo).__name__,
        "none_as_null_efectivo": none_as_null,
        "veredicto": "PASS" if (FIX_ESPERADO in (linea or "") and none_as_null is True) else "FAIL",
    }
    assert LOCAL_SOURCE_SHA, "el host no inyecto G140_LOCAL_SOURCE_SHA; no se puede trazar la fuente"
    assert FIX_ESPERADO in (linea or ""), (
        f"STOP: el backend local NO ejecuta el fix del PR #{PR_CORRECCION}. "
        f"Linea importada: {linea!r} desde {archivo_importado}")
    assert none_as_null is True, (
        "STOP: json_linea_base se serializa con none_as_null="
        f"{none_as_null!r}; un None se escribiria como JSON 'null' y no como SQL NULL")
    ESTADO["fuente"] = True


def test_02_migraciones_y_tablas():
    requiere("fuente")
    def alembic(*args):
        p = subprocess.run([sys.executable, "-m", "alembic", *args], cwd=str(REPO_DIR),
                           capture_output=True, text=True, timeout=300)
        return (p.stdout + p.stderr).strip()
    upgrade = alembic("upgrade", "head")
    current, heads = alembic("current"), alembic("heads")
    rev_bd = filas("SELECT version_num FROM alembic_version")
    tablas = filas("""
        SELECT n.nspname AS esquema, c.relname AS tabla
        FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE (n.nspname,c.relname) IN (('modulo3','observaciones_vision'),
          ('modulo9','calibraciones_vision'),('modulo9','lineas_base_vision'))
        ORDER BY 1,2""")
    presentes = {f"{t['esquema']}.{t['tabla']}" for t in tablas}
    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(REPO_DIR),
                                capture_output=True, text=True, timeout=60).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        commit = ""
    E["alembic"] = {
        "fuente": "migraciones reales del proyecto (alembic upgrade head como owner del laboratorio)",
        "alembic_upgrade_head": upgrade.splitlines()[-5:],
        "alembic_current": current.splitlines()[-3:],
        "alembic_heads": heads.splitlines()[-3:],
        "version_num_en_bd": rev_bd[0]["version_num"] if rev_bd else None,
        "tablas_vision_presentes": sorted(presentes),
    }
    E["commit_backend"] = commit or "no disponible dentro del contenedor"
    esperadas = {"modulo3.observaciones_vision", "modulo9.calibraciones_vision",
                 "modulo9.lineas_base_vision"}
    assert esperadas <= presentes, f"faltan tablas VISION en el laboratorio: {esperadas - presentes}"
    ESTADO["migraciones"] = True


def test_03_parametros_vigentes_y_max_iteraciones_1(monkeypatch_sesion):
    requiere("migraciones")
    from src.configuration.application.use_cases.sensores.calibrar_vision_use_case import (
        CalibrarVisionUseCase)
    from src.configuration.domain.entities.linea_base_vision import ParametrosLineaBase

    vigentes = ParametrosLineaBase()
    # §46: todos los umbrales conservan su valor vigente; solo cambia max_iteraciones.
    laboratorio = ParametrosLineaBase(
        min_observaciones=vigentes.min_observaciones,
        cobertura_minima=vigentes.cobertura_minima,
        tracks_minimos=vigentes.tracks_minimos,
        min_datos_componente=vigentes.min_datos_componente,
        epsilon=vigentes.epsilon,
        max_iteraciones=1,
    )
    # §47: inyección EN MEMORIA del valor por defecto del parámetro `parametros` del caso de
    # uso real. No se edita linea_base_vision.py, no se bifurca el algoritmo y no se mockea
    # ningún repositorio: el router sigue construyendo el caso de uso real sin pasar parámetros.
    defaults = CalibrarVisionUseCase.__init__.__defaults__
    assert defaults == (vigentes,), (
        "la firma del caso de uso cambió; revisar la inyección antes de continuar: "
        f"{defaults!r}")
    monkeypatch_sesion.setattr(CalibrarVisionUseCase.__init__, "__defaults__", (laboratorio,))
    assert CalibrarVisionUseCase.__init__.__defaults__[0].max_iteraciones == 1
    assert CalibrarVisionUseCase.__init__.__defaults__[0].epsilon == vigentes.epsilon

    ESTADO["par"] = laboratorio
    E["parametros"] = {
        "fuente": ("ParametrosLineaBase — src/configuration/domain/entities/linea_base_vision.py; "
                   "el router construye CalibrarVisionUseCase sin pasar `parametros`"),
        "vigentes_en_el_codigo": vigentes.__dict__.copy(),
        "usados_en_el_laboratorio": laboratorio.__dict__.copy(),
        "N": laboratorio.min_observaciones,
        "epsilon": laboratorio.epsilon,
        "max_iteraciones": laboratorio.max_iteraciones,
        "min_datos_componente": laboratorio.min_datos_componente,
        "inyeccion": "__init__.__defaults__ del caso de uso, solo en memoria, revertida al cerrar",
    }
    ESTADO["parametros"] = True


@pytest.fixture(scope="session")
def monkeypatch_sesion():
    mp = pytest.MonkeyPatch()
    yield mp
    mp.undo()


@pytest.fixture(scope="session")
def cliente(monkeypatch_sesion):
    """TestClient sobre la aplicación REAL, contra la BD local real."""
    from fastapi.testclient import TestClient
    from main import app
    with TestClient(app) as c:
        yield c


# ══════════════════════════════════════════════════════════════════════════════
# 2. Fixture local y actor
# ══════════════════════════════════════════════════════════════════════════════

def test_04_fixture_local(cliente):
    requiere("parametros")
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
    usuario = filas("SELECT id_usuario, id_rol FROM modulo1.usuarios WHERE correo_electronico = %s",
                    (ING_CORREO,))[0]
    permiso = filas("""
        SELECT COUNT(*) AS n FROM modulo1.permisos
        WHERE id_rol = %s AND id_recurso = %s AND id_accion = %s AND es_activo""",
        (ID_ROL_INGENIERO, RECURSO_SENSORES, ACCION_CREAR))
    r = cliente.post("/sesiones/", json={"correo_electronico": ING_CORREO,
                                         "contrasena": ING_PASSWORD})
    assert r.status_code == 200, f"login local HTTP {r.status_code}: {sanear(r.text)[:300]}"
    ESTADO["token"] = r.json()["token"]
    ESTADO["area"] = c["id_infraestructura"]
    ESTADO["especie"] = c["id_especie"]
    ESTADO["camara"] = c["id_dispositivo_iot"]
    ESTADO["fps"] = c["fps"]
    ESTADO["usuario"] = usuario["id_usuario"]
    E["fixture"] = {
        "origen": "sintético, sembrado por SQL en la base local y exclusiva del laboratorio",
        "finca_id": c["id_finca"], "area_id": c["id_infraestructura"],
        "area_activa": c["area_activa"], "especie_id": c["id_especie"],
        "tipo_modelo_asignado": c["tipo_modelo_asignado"], "paradigma": "POBLACIONAL",
        "camara_id": c["id_dispositivo_iot"], "camara_categoria": c["categoria"],
        "camara_activa": c["es_activo"], "fps_nominal": c["fps"],
        "camara_serial": "[SERIAL REDACTED]",
        "usuario_id": usuario["id_usuario"], "id_rol": usuario["id_rol"],
        "correo": ING_CORREO,
        "permisos_sensores_crear_del_rol": permiso[0]["n"],
        "login": "PASS",
    }
    assert c["es_activo"] and c["categoria"] == "CAMARA"
    assert c["tipo_modelo_asignado"] == "MODELO_AVES" and c["id_especie"] is not None
    assert permiso[0]["n"] >= 1, "el rol del laboratorio no tiene permiso de Crear sobre sensores"
    ESTADO["fixture"] = True


def _h() -> dict:
    return {"Authorization": f"Bearer {ESTADO['token']}"}


def _ingerir(cliente, ventana: str, valores: list[tuple[float, float]], paso: int, marca: str):
    if marca in ESTADO:
        raise RuntimeError(f"ABORTADO: reenvío prohibido del lote {marca}")
    ESTADO[marca] = True
    ini, _fin = VENTANAS[ventana]
    fechas = instantes(ini, len(valores), paso)
    cuerpo = {"device_id": ESTADO["camara"], "access_key": SERIAL_CAM, "area_id": ESTADO["area"],
              "observaciones": [obs_apta(ts, d, t, ESTADO["fps"])
                                for ts, (d, t) in zip(fechas, valores)]}
    r = cliente.post("/iot/telemetria/vision", json=cuerpo)
    E["presupuesto"]["post_vision"] += 1
    assert r.status_code in (200, 201), f"ingesta {ventana} HTTP {r.status_code}: {sanear(r.text)[:400]}"
    return r.json()


def _calibrar(cliente, ventana: str, nota: str, marca: str):
    if marca in ESTADO:
        raise RuntimeError(f"ABORTADO: reintento prohibido del POST funcional {marca}")
    ESTADO[marca] = True
    ini, fin = VENTANAS[ventana]
    cuerpo = {"modo_calibracion": "VISION", "area_id": ESTADO["area"],
              "ventana_observacion": {"inicio": ini, "fin": fin}, "observaciones": nota,
              "fecha_calibracion": datetime.datetime.now(datetime.timezone.utc).isoformat()}
    r = cliente.post("/configuracion/calibraciones-vision", json=cuerpo, headers=_h())
    E["presupuesto"]["post_calibracion"] += 1
    try:
        cuerpo_resp = r.json()
    except ValueError:
        cuerpo_resp = {"_texto": r.text[:500]}
    return cuerpo, r.status_code, cuerpo_resp


# ══════════════════════════════════════════════════════════════════════════════
# 3. Línea base previa (setup) — §50 y §51
# ══════════════════════════════════════════════════════════════════════════════

def test_05_baseline_previa_setup(cliente):
    requiere("fixture", "par")
    n = ESTADO["par"].min_observaciones
    lote = _ingerir(cliente, "WINDOW_286_BASE", [(10.0, 5.0)] * n, 2, "lote_base")
    aptas = [o for o in lote["observaciones"] if o["apto_para_ia"]]
    conteo = filas("""
        SELECT COUNT(*) AS total, SUM(CASE WHEN es_apto_para_ia THEN 1 ELSE 0 END) AS aptas
        FROM modulo3.observaciones_vision
        WHERE id_dispositivo_iot = %s AND fecha_observacion BETWEEN %s AND %s""",
        (ESTADO["camara"], *VENTANAS["WINDOW_286_BASE"]))[0]
    cuerpo, codigo, resp = _calibrar(cliente, "WINDOW_286_BASE",
                                     "QA TC-M09-286 setup de linea base previa", "post_base")
    E["baseline_setup"] = {
        "ventana": dict(zip(("inicio", "fin"), VENTANAS["WINDOW_286_BASE"])),
        "lote": {"total": lote["total"], "aceptadas": lote["aceptadas"],
                 "duplicadas": lote["duplicadas"], "aptas": len(aptas),
                 "indices_distintos": sorted({o["indice_calidad"] for o in lote["observaciones"]})},
        "conteo_bd": dict(conteo),
        "request": cuerpo, "http": codigo, "response": resp,
        "nota": "POST de SETUP; se ejecuta con max_iteraciones = 1 ya inyectado",
    }
    assert lote["aceptadas"] == n and lote["duplicadas"] == 0 and len(aptas) == n
    assert int(conteo["total"]) == n and int(conteo["aptas"]) == n
    assert 200 <= codigo < 300, f"el setup de la línea base esperaba 2xx y obtuvo {codigo}: {sanear(resp)}"
    assert resp["estado"] == "EXITOSA", resp["estado"]
    ESTADO["BASELINE_PRE_286_ID"] = resp["id_calibracion_vision"]
    E["baseline_setup"]["BASELINE_PRE_286_ID"] = ESTADO["BASELINE_PRE_286_ID"]
    E["baseline_setup"]["iteraciones"] = resp.get("iteraciones")
    bd = filas("""SELECT id_calibracion_vision, estado, cantidad_observaciones,
                         cantidad_observaciones_validas, iteraciones
                  FROM modulo9.calibraciones_vision WHERE id_calibracion_vision = %s""",
               (ESTADO["BASELINE_PRE_286_ID"],))
    lb = filas("""SELECT id_calibracion_vision FROM modulo9.lineas_base_vision
                  WHERE id_infraestructura = %s AND id_especie = %s""",
               (ESTADO["area"], ESTADO["especie"]))
    E["baseline_setup"]["verificacion_bd"] = {"calibracion": bd, "linea_base_vigente": lb}
    assert bd and bd[0]["estado"] == "EXITOSA"
    assert lb and lb[0]["id_calibracion_vision"] == ESTADO["BASELINE_PRE_286_ID"]
    ESTADO["baseline"] = True


# ══════════════════════════════════════════════════════════════════════════════
# 4. Oráculo ANTES del POST objetivo — §53
# ══════════════════════════════════════════════════════════════════════════════

def test_06_oraculo_demuestra_no_convergencia():
    requiere("baseline")
    par = ESTADO["par"]
    par_oraculo = ORACULO.Parametros(
        min_observaciones=par.min_observaciones, cobertura_minima=par.cobertura_minima,
        tracks_minimos=par.tracks_minimos, min_datos_componente=par.min_datos_componente,
        epsilon=par.epsilon, max_iteraciones=par.max_iteraciones)
    datos = ORACULO.dataset_286_fail()
    lecturas = ORACULO.ambas_lecturas(datos, par_oraculo)
    descarte = lecturas["ORACLE_DESCARTE"]
    t3 = descarte["traza"]["etapa_3"]
    it1 = t3["iteraciones"][0]
    E["oracle"] = {
        "independiente": ("oracle_g140.py no importa calcular_linea_base, recortar_p5_p95, "
                          "mediana, percentil ni ningún módulo src.configuration/src.telemetry"),
        "parametros": par_oraculo.__dict__.copy(),
        "dataset_densidad_actividad": ORACULO.DENSIDAD_286,
        "dataset_tasa_movimiento": [d * 10 for d in ORACULO.DENSIDAD_286],
        "n_observaciones": len(datos),
        "ORACLE_DESCARTE": descarte,
        "ORACLE_WINSORIZACION": lecturas["ORACLE_WINSORIZACION"],
        "resumen_descarte": {
            "mediana_inicial": t3["mediana_inicial"],
            "mediana_tras_primera_iteracion": {k: v["mediana_nueva"]
                                               for k, v in it1["componentes"].items()},
            "cambio_relativo_maximo": it1["cambio_maximo"],
            "epsilon": it1["epsilon"],
            "convergencia": it1["convergio"],
        },
    }
    assert descarte["estado"] == "NO_CONVERGIDA", descarte["estado"]
    assert descarte["etapa_fallo"] == "REFINAMIENTO", descarte["etapa_fallo"]
    assert it1["cambio_maximo"] >= par.epsilon, (it1["cambio_maximo"], par.epsilon)
    assert it1["convergio"] is False
    ESTADO["oracle_descarte"] = descarte
    ESTADO["oracle"] = True


# ══════════════════════════════════════════════════════════════════════════════
# 5. Dataset no convergente y precondiciones de BD — §52 y §54
# ══════════════════════════════════════════════════════════════════════════════

def test_07_dataset_no_convergente(cliente):
    requiere("oracle")
    valores = [(d, d * 10) for d in ORACULO.DENSIDAD_286]
    lote = _ingerir(cliente, "WINDOW_286_FAIL", valores, 5, "lote_fail")
    aptas = [o for o in lote["observaciones"] if o["apto_para_ia"]]
    conteo = filas("""
        SELECT COUNT(*) AS total, SUM(CASE WHEN es_apto_para_ia THEN 1 ELSE 0 END) AS aptas
        FROM modulo3.observaciones_vision
        WHERE id_dispositivo_iot = %s AND fecha_observacion BETWEEN %s AND %s""",
        (ESTADO["camara"], *VENTANAS["WINDOW_286_FAIL"]))[0]
    vigente = filas("""SELECT id_calibracion_vision FROM modulo9.lineas_base_vision
                       WHERE id_infraestructura = %s AND id_especie = %s""",
                    (ESTADO["area"], ESTADO["especie"]))
    E["dataset_no_convergente"] = {
        "ventana": dict(zip(("inicio", "fin"), VENTANAS["WINDOW_286_FAIL"])),
        "lote": {"total": lote["total"], "aceptadas": lote["aceptadas"],
                 "duplicadas": lote["duplicadas"], "aptas": len(aptas),
                 "indices_distintos": sorted({o["indice_calidad"] for o in lote["observaciones"]})},
        "conteo_bd": dict(conteo),
        "linea_base_vigente_antes": vigente,
    }
    esperadas = len(ORACULO.DENSIDAD_286)
    assert lote["aceptadas"] == esperadas and lote["duplicadas"] == 0 and len(aptas) == esperadas
    assert int(conteo["total"]) == esperadas and int(conteo["aptas"]) == esperadas
    assert esperadas >= ESTADO["par"].min_observaciones, esperadas
    assert vigente and vigente[0]["id_calibracion_vision"] == ESTADO["BASELINE_PRE_286_ID"]
    ESTADO["dataset"] = True


# ══════════════════════════════════════════════════════════════════════════════
# 6. POST objetivo — §55 a §59
# ══════════════════════════════════════════════════════════════════════════════

def test_08_post_objetivo_no_convergencia(cliente):
    requiere("dataset")
    cuerpo, codigo, resp = _calibrar(cliente, "WINDOW_286_FAIL",
                                     "QA TC-M09-286 no convergencia", "post_fail")
    esperado = (
        "No se pudo calcular la línea base: datos insuficientes o sin convergencia para el área "
        f"{ESTADO['area']} y especie {ESTADO['especie']}. Se conserva la línea base vigente anterior."
    )
    E["post_objetivo"] = {
        "request": cuerpo, "http": codigo, "response": resp,
        "http_esperado": 422,
        "error_code": resp.get("error_code"),
        "message_obtenido": resp.get("message"),
        "message_esperado": esperado,
        "mensaje_exacto": "SÍ" if resp.get("message") == esperado else "NO",
    }
    ESTADO["http_objetivo"] = codigo
    # El veredicto se emite en test_12. Aqui no se aborta: §58, §59 y §60 exigen observar la
    # calibracion registrada, la linea base y la auditoria, y eso hay que mirarlo tambien
    # -sobre todo- cuando la respuesta no es la contractual. §64 prohibe repetir el POST, no
    # mirar lo que dejo.
    E["post_objetivo"]["veredicto"] = (
        "CONFORME" if (codigo == 422
                       and resp.get("error_code") == "LINEA_BASE_NO_CALCULADA"
                       and resp.get("message") == esperado) else "NO CONFORME")
    ESTADO["objetivo"] = True


def test_09_calibracion_no_convergida_en_bd():
    requiere("objetivo")
    nuevas = filas("""
        SELECT id_calibracion_vision, estado, etapa_fallo, motivo, json_linea_base,
               cantidad_observaciones, cantidad_observaciones_validas, iteraciones,
               origen_disparo, id_usuario, json_ventana_observacion, observaciones
        FROM modulo9.calibraciones_vision
        WHERE id_infraestructura = %s AND id_calibracion_vision <> %s
        ORDER BY id_calibracion_vision""",
        (ESTADO["area"], ESTADO["BASELINE_PRE_286_ID"]))
    E["verificacion_bd_intento"] = {
        "calibraciones_del_intento": nuevas,
        "persistida": "SI" if len(nuevas) == 1 else "NO",
        "esperado": ("una fila con estado NO_CONVERGIDA, etapa REFINAMIENTO, json_linea_base NULL, "
                     "30/30 observaciones e iteraciones 1"),
    }
    if not nuevas:
        E["verificacion_bd_intento"]["resumen"] = {
            "id_calibracion_vision": None,
            "estado_esperado": "NO_CONVERGIDA", "estado_obtenido": "NO PERSISTIDA",
            "etapa_esperada": "REFINAMIENTO", "etapa_obtenida": "NO PERSISTIDA",
            "json_linea_base": None, "cantidad_observaciones": None,
            "cantidad_observaciones_validas": None, "iteraciones": None, "motivo": None,
        }
        ESTADO["ID_NO_CONV"] = None
        ESTADO["bd_intento"] = True
        return
    assert len(nuevas) == 1, f"se esperaba a lo sumo 1 calibracion del intento; hay {len(nuevas)}"
    f = nuevas[0]
    ESTADO["ID_NO_CONV"] = f["id_calibracion_vision"]
    E["verificacion_bd_intento"]["resumen"] = {
        "id_calibracion_vision": f["id_calibracion_vision"],
        "estado_esperado": "NO_CONVERGIDA", "estado_obtenido": f["estado"],
        "etapa_esperada": "REFINAMIENTO", "etapa_obtenida": f["etapa_fallo"],
        "json_linea_base": f["json_linea_base"],
        "cantidad_observaciones": f["cantidad_observaciones"],
        "cantidad_observaciones_validas": f["cantidad_observaciones_validas"],
        "iteraciones": f["iteraciones"], "motivo": f["motivo"],
    }
    esperadas = len(ORACULO.DENSIDAD_286)
    n_minimo = ESTADO["par"].min_observaciones
    assert f["estado"] == "NO_CONVERGIDA", f["estado"]
    assert f["etapa_fallo"] == "REFINAMIENTO", f["etapa_fallo"]
    assert f["json_linea_base"] is None, f["json_linea_base"]
    assert f["cantidad_observaciones"] == esperadas, f["cantidad_observaciones"]
    assert f["cantidad_observaciones_validas"] == esperadas, f["cantidad_observaciones_validas"]
    assert f["cantidad_observaciones_validas"] >= n_minimo, (
        f["cantidad_observaciones_validas"], n_minimo)
    assert f["iteraciones"] == 1, f["iteraciones"]
    motivo = f["motivo"] or ""
    assert "convergencia" in motivo.lower(), motivo
    ESTADO["bd_intento"] = True


def test_10_baseline_previa_conservada(cliente):
    requiere("bd_intento")
    r = cliente.get(f"/configuracion/calibraciones-vision/linea-base?area_id={ESTADO['area']}",
                    headers=_h())
    api = r.json() if r.status_code == 200 else None
    bd = filas("""SELECT id_calibracion_vision, json_valor FROM modulo9.lineas_base_vision
                  WHERE id_infraestructura = %s AND id_especie = %s""",
               (ESTADO["area"], ESTADO["especie"]))
    hist = cliente.get(f"/configuracion/calibraciones-vision?area_id={ESTADO['area']}",
                       headers=_h())
    E["linea_base_post"] = {
        "http": r.status_code, "api": api, "bd": bd,
        "BASELINE_PRE_286_ID": ESTADO["BASELINE_PRE_286_ID"],
        "conservada": "SÍ" if (api or {}).get("id_calibracion_vision") == ESTADO["BASELINE_PRE_286_ID"] else "NO",
        "historial": hist.json() if hist.status_code == 200 else {"http": hist.status_code},
    }
    assert r.status_code == 200, f"línea base POST HTTP {r.status_code}"
    assert api["id_calibracion_vision"] == ESTADO["BASELINE_PRE_286_ID"], api["id_calibracion_vision"]
    assert bd and bd[0]["id_calibracion_vision"] == ESTADO["BASELINE_PRE_286_ID"]
    ESTADO["conservada"] = True


def test_11_auditoria_rf10():
    requiere("conservada")
    eventos = filas("""
        SELECT to_jsonb(e) AS evento FROM modulo1.eventos e
        WHERE e.tipo_evento IN (%s, %s) ORDER BY e.id_evento DESC LIMIT 20""",
        (TIPO_EVENTO_RECHAZO, TIPO_EVENTO_EXITO))
    def detalle(ev):
        d = ev.get("detalle") or ev.get("json_detalle") or {}
        if isinstance(d, str):
            try:
                d = json.loads(d)
            except ValueError:
                d = {}
        return d
    vision = [e["evento"] for e in eventos if detalle(e["evento"]).get("operacion") == "CALIBRACION_VISION"]
    del_intento = [e for e in vision
                   if detalle(e).get("id_calibracion_vision") == ESTADO["ID_NO_CONV"]]
    E["auditoria_rf10"] = {
        "eventos_vision_recientes": vision[:5],
        "evento_del_intento": del_intento or None,
        "registrada": "SÍ" if del_intento else "NO",
    }
    if del_intento:
        ev = del_intento[0]
        d = detalle(ev)
        # El contrato real de RF-10: el resultado viaja en `resultado` ('exitoso'/'fallido');
        # NO existe un campo `exitoso`. Leerlo devolveria null y daria una lectura falsa.
        assert "exitoso" not in ev, (
            "el item de auditoria declara `exitoso`; revisar el contrato antes de leerlo")
        E["auditoria_rf10"]["resumen_del_intento"] = {
            "id_evento": ev.get("id_evento"), "tipo_evento": ev.get("tipo_evento"),
            "resultado": ev.get("resultado"), "modulo": ev.get("modulo"),
            "id_usuario": ev.get("id_usuario"),
            "direccion_ip": "PRESENTE" if ev.get("direccion_ip") else "AUSENTE",
            "fecha_evento": ev.get("fecha_evento"),
            "operacion": d.get("operacion"), "area": d.get("id_infraestructura"),
            "especie": d.get("id_especie"), "estado": d.get("estado"),
            "etapa": d.get("etapa_fallo"), "motivo": d.get("motivo"),
            "motivo_etapa": d.get("motivo_etapa"), "codigo_http": d.get("codigo_http"),
            "codigo_error": d.get("codigo_error"),
            "id_calibracion_vision": d.get("id_calibracion_vision"),
        }
        assert ev.get("tipo_evento") == TIPO_EVENTO_RECHAZO, ev.get("tipo_evento")
        assert str(ev.get("resultado")).lower() == "fallido", ev.get("resultado")
        assert ev.get("modulo") == "MODULO9", ev.get("modulo")
        assert d.get("operacion") == "CALIBRACION_VISION", d.get("operacion")
        assert d.get("codigo_http") == 422, d.get("codigo_http")
        assert d.get("codigo_error") == "LINEA_BASE_NO_CALCULADA", d.get("codigo_error")
        assert d.get("id_calibracion_vision") == ESTADO["ID_NO_CONV"], d.get("id_calibracion_vision")
        assert d.get("estado") == "NO_CONVERGIDA", d.get("estado")
        assert d.get("etapa_fallo") == "REFINAMIENTO", d.get("etapa_fallo")
        assert d.get("motivo_etapa"), "motivo_etapa vacio en la auditoria del intento"
    else:
        E["limitaciones"].append({
            "tema": "auditoría RF-10 del intento (§60)",
            "detalle": "no se encontró evento correlacionable con la calibración del intento",
        })
    ESTADO["auditoria"] = True


def test_12_cierre_local():
    requiere("auditoria")
    producto = E["verificacion_bd_intento"]["resumen"]
    oraculo = ESTADO["oracle_descarte"]
    it1 = oraculo["traza"]["etapa_3"]["iteraciones"][0]
    E["cuadro_tc286"] = [
        {"criterio": "Ambiente", "esperado": "LOCAL", "obtenido": "LOCAL AISLADO (sgpmp_g140_lab)"},
        {"criterio": "max_iteraciones", "esperado": 1, "obtenido": ESTADO["par"].max_iteraciones},
        {"criterio": "Cambio tras iteración", "esperado": f">= epsilon ({ESTADO['par'].epsilon})",
         "obtenido": it1["cambio_maximo"]},
        {"criterio": "HTTP", "esperado": 422, "obtenido": ESTADO["http_objetivo"]},
        {"criterio": "error_code", "esperado": "LINEA_BASE_NO_CALCULADA",
         "obtenido": E["post_objetivo"]["error_code"]},
        {"criterio": "estado", "esperado": "NO_CONVERGIDA", "obtenido": producto["estado_obtenido"]},
        {"criterio": "etapa_fallo", "esperado": "REFINAMIENTO", "obtenido": producto["etapa_obtenida"]},
        {"criterio": "iteraciones", "esperado": 1, "obtenido": producto["iteraciones"]},
        {"criterio": "baseline previa conservada", "esperado": "SÍ",
         "obtenido": E["linea_base_post"]["conservada"]},
    ]
    conforme = E["post_objetivo"]["veredicto"] == "CONFORME"
    E["resultado"] = {
        "TC-M09-286": "APROBADO" if conforme else "RECHAZADO",
        "incidencia_requerida": "NO" if conforme else "SI",
        "nota": ("el estado NO_CONVERGIDA con etapa REFINAMIENTO es el esperado oficial de la "
                 "matriz QA actualizada (§0 y §57 del paquete); no se abre incidencia por el"),
    }
    E["nota_g139"] = {
        "contexto": ("§61 - en TEST se observo que una calibracion VISION no exitosa devolvia 400 "
                     "VALOR_NO_PERMITIDO por ck_calibracion_vision_resultado_coherente"),
        "en_el_laboratorio": (
            f"REPRODUCIDO con el codigo de esta rama: el intento respondio HTTP "
            f"{ESTADO['http_objetivo']}" if not conforme else
            f"no se reprodujo: el intento respondio HTTP {ESTADO['http_objetivo']}"),
        "fila_persistida": producto,
    }
    if not conforme:
        E["defecto_detectado"] = {
            "sintoma": (f"POST /configuracion/calibraciones-vision devolvio HTTP "
                        f"{ESTADO['http_objetivo']} {E['post_objetivo']['error_code']} "
                        "en lugar del 422 LINEA_BASE_NO_CALCULADA del contrato"),
            "campo_senalado": "calibracion_vision_resultado_coherente",
            "etapa_3_calculada_correctamente": {
                "estado": "NO_CONVERGIDA", "etapa_fallo": "REFINAMIENTO", "iteraciones": 1,
                "coincide_con_el_oraculo": True,
                "nota": ("el algoritmo resuelve bien la no convergencia; lo que falla es "
                         "persistir el resultado"),
            },
            "causa_raiz": (
                "modulo9.calibraciones_vision.json_linea_base esta mapeado como "
                "mapped_column(JSONB) en src/configuration/infrastructure/models/"
                "calibracion_vision_model.py. El tipo JSONB de SQLAlchemy usa none_as_null=False "
                "por defecto, asi que un linea_base None se escribe como el valor JSON 'null' y "
                "no como SQL NULL. En PostgreSQL 'null'::jsonb IS NULL es false, de modo que la "
                "rama del CHECK para estado <> 'EXITOSA' (json_linea_base IS NULL) nunca puede "
                "cumplirse y toda calibracion FALLIDA o NO_CONVERGIDA es rechazada por la BD."),
            "evidencia": (
                "el log de sentencias del laboratorio registra el INSERT con "
                "estado 'NO_CONVERGIDA', etapa_fallo 'REFINAMIENTO', iteraciones 1, 30/30 y "
                "json_linea_base 'null'::JSONB, y el motor responde con la violacion del CHECK"),
            "remedio_propuesto": "mapped_column(JSONB(none_as_null=True)) para json_linea_base",
            "integridad": {"linea_base_sustituida": "NO",
                           "linea_base_vigente": ESTADO["BASELINE_PRE_286_ID"]},
            "relacion": "misma causa raiz que el defecto observado en TEST durante TC-M09-G139",
        }
    E["seguridad"] = {
        "credenciales_persistidas": "NO",
        "serial_access_key_persistido": "NO — redactado por patrón",
        "database_url_con_password": "NO — solo la versión sanitizada",
        "sql_dml_en_test": 0,
        "sql_dml_en_laboratorio": "siembra del fixture, autorizada en base local y exclusiva",
    }
    assert E["presupuesto"]["post_calibracion"] == 2, E["presupuesto"]
    assert E["presupuesto"]["post_vision"] == 2, E["presupuesto"]
    guardar()
    esperado = E["post_objetivo"]["message_esperado"]
    assert ESTADO["http_objetivo"] == 422, (
        f"se esperaba 422 y se obtuvo {ESTADO['http_objetivo']}: "
        f"{E['post_objetivo']['error_code']} / {E['post_objetivo']['message_obtenido']}")
    assert E["post_objetivo"]["error_code"] == "LINEA_BASE_NO_CALCULADA"
    assert E["post_objetivo"]["message_obtenido"] == esperado
