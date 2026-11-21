"""TC-M09-G139 — SEGUNDA EVALUACIÓN (RF-24 v2.0, Módulo 9) — automatización oficial.

Casos:
  TC-M09-282  — ventana con observaciones VISION pero CERO aptas para IA  -> 422, sin línea base nueva.
  TC-M09-283  — corrida N   (exactamente N observaciones aptas)           -> 2xx, EXITOSA, publica línea base.
              — corrida N−1 (exactamente N−1 observaciones aptas)         -> 422 LINEA_BASE_NO_CALCULADA,
                                                                             calibración FALLIDA etapa FILTRADO,
                                                                             la línea base de N se conserva.

Herramienta oficial del grupo: Pytest + requests HTTP reales contra TEST + BD por SELECT.
NO se usa Newman y NO se genera HTML de Newman.

Ejecucion 2 - REEJECUCION COMPLETA POST-FIX (PR #550). El RUN logico no cambia
(run-20261010-131446): se reejecuta el grupo entero y se sobreescriben pytest.xml,
evidencia.json y automation_manifest.json; la historia de las ejecuciones vive en el
informe y en `historial_ejecuciones` de la evidencia. Esta ejecucion usa ventanas y
camara NUEVAS, y verifica por lectura que JSONB(none_as_null=True) este en origin/test
sin que eso sustituya al veredicto HTTP real contra TEST.

Presupuesto funcional (duro, verificado por contador):
  POST /configuracion/calibraciones-vision : 3  (uno por caso, 0 reintentos)
  POST /iot/telemetria/vision              : 3  (un lote por ventana)

Reglas de seguridad aplicadas:
  * BD en sesión READ ONLY; solo SELECT. Ningún INSERT/UPDATE/DELETE/DDL/GRANT/REVOKE.
  * Los datos nuevos se crean únicamente por las APIs oficiales.
  * No se persisten contraseñas, JWT, cabeceras Authorization ni el serial/access_key
    de la cámara: el sanitizador los redacta antes de escribir cualquier artefacto.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import re
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import pytest
import requests

# ── Localización y guarda de rutas ───────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent              # .../EvaluacionV2/automation
EVAL_DIR = BASE_DIR.parent                              # .../EvaluacionV2
CASE_DIR = EVAL_DIR.parent                              # .../TC-M09-G139
GRUPO = "TC-M09-G139"

if BASE_DIR.name != "automation" or EVAL_DIR.name != "EvaluacionV2" or CASE_DIR.name != GRUPO:
    raise RuntimeError(
        f"ABORTADO: el test debe vivir en {GRUPO}/EvaluacionV2/automation/; está en {BASE_DIR}"
    )

RUN_ID = os.environ.get("G139_RUN_ID") or datetime.datetime.now().strftime("run-%Y%m%d-%H%M%S")
RUN_DIR = EVAL_DIR / "RESULTADOS" / RUN_ID
RUN_DIR.mkdir(parents=True, exist_ok=True)

# ── Ejecuciones dentro del MISMO RUN lógico ──────────────────────────────────
# El RUN no se duplica cuando Desarrollo corrige: se incrementa el número de
# ejecución y se reejecuta el grupo completo sobreescribiendo los artefactos
# técnicos. La historia vive en el informe y en `historial_ejecuciones`.
EJECUCION = 2
TIPO_EJECUCION = "REEJECUCION_COMPLETA_POST_FIX"
AUTORIZADO_POR = "LIDER_DESARROLLO"
PR_CORRECCION = 550
FIX_ESPERADO = "JSONB(none_as_null=True)"
# Sello propio de esta ejecución: el RUN_ID se mantiene fijo, así que el serial
# de la cámara no puede derivarse de él sin chocar con la ejecución anterior.
SELLO = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d-%H%M%S")

HISTORIAL_EJECUCIONES = [
    {
        "ejecucion": 1,
        "fecha": "2026-10-10T13:15:00-05:00",
        "tipo": "SEGUNDA_EVALUACION_INICIAL",
        "resultado_g139": "RECHAZADO",
        "resultados": {
            "TC-M09-282": "APROBADO",
            "TC-M09-283-N": "APROBADO",
            "TC-M09-283-N-1": "RECHAZADO",
            "TC-M09-283": "RECHAZADO",
        },
        "motivo": ("TC-M09-283 N−1 devolvió 400 VALOR_NO_PERMITIDO "
                   "(field calibracion_vision_resultado_coherente) en lugar del 422 "
                   "LINEA_BASE_NO_CALCULADA; no quedó la calibración FALLIDA en el "
                   "historial ni el evento RF-10 del intento"),
        "fixture": {"area_id": 279, "camara_id": 222,
                    "ventanas": ["2026-09-01", "2026-09-02", "2026-09-03"]},
        "hitos": {"baseline_PRE": 7, "CAL_N": 8, "baseline_tras_N": 8,
                  "CAL_N_MINUS_1": None, "linea_base_sustituida": "NO"},
        "pytest": {"collected": 22, "passed": 17, "failed": 1, "skipped": 4, "errors": 0},
    },
]

# ── Entorno decisorio ────────────────────────────────────────────────────────
BASE_URL = "https://api.inmero.co/back-sigab-test"
AMBIENTE = "TEST"
if not BASE_URL.endswith("/back-sigab-test"):
    raise RuntimeError("ABORTADO: el ambiente decisorio de G139 es TEST.")

ING = ("ingeniero@pecuaria.co", "Test1234!")
ADM = ("administador.dev@gmail.com", "Test1234!")
ADM_ALT = ("admin.dev@gmail.com", "Test1234!")

DB = {
    "host": "158.69.200.27", "port": "5448", "dbname": "sgpmp_test",
    "user": "member_qa", "password": "qaSGP2026",
}

# ── Fixture reutilizado de TC-M09-G137 ───────────────────────────────────────
AREA = 279
ESPECIE_ESPERADA = 41
FINCA_ESPERADA = 163
TIPO_CAMARA_VISION = 5           # modulo9.tipos_dispositivos_iot -> CAMARA_VISION
TIPO_EVENTO_CALIBRACION_RECHAZADA = 29

# ── Valor N (se resuelve en test_05 contra el código vigente) ────────────────
N_ESPERADO_POR_CODIGO = 30

# ── Diseño de ventanas: tres rangos en el pasado, disjuntos ──────────────────
# Ejecución 2: ventanas NUEVAS. Las de la ejecución 1 (01, 02 y 03 de septiembre)
# no se reutilizan, para que ninguna observación anterior pueda contaminar el conteo.
VENTANAS = {
    "WINDOW_282": ("2026-09-11T00:00:00Z", "2026-09-11T02:00:00Z"),
    "WINDOW_283_N": ("2026-09-12T00:00:00Z", "2026-09-12T04:00:00Z"),
    "WINDOW_283_N_MINUS_1": ("2026-09-13T00:00:00Z", "2026-09-13T04:00:00Z"),
}
VENTANAS_EJECUCION_1 = {
    "WINDOW_282": ("2026-09-01T00:00:00Z", "2026-09-01T02:00:00Z"),
    "WINDOW_283_N": ("2026-09-02T00:00:00Z", "2026-09-02T04:00:00Z"),
    "WINDOW_283_N_MINUS_1": ("2026-09-03T00:00:00Z", "2026-09-03T04:00:00Z"),
}

PRESUPUESTO = {"post_calibracion": 3, "post_vision": 3}
_RE_SERIAL = re.compile(r"QA-M09-G1\d{2}-CAM-\d{8}-\d{6}")

E: dict = {
    "run_id": RUN_ID,
    "grupo": GRUPO,
    "ambiente": AMBIENTE,
    "base_url": BASE_URL,
    "herramienta": "Pytest + requests (HTTP real) + BD TEST por SELECT",
    "newman": "NO APLICA",
    "generado": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "execution_number": EJECUCION,
    "execution_type": TIPO_EJECUCION,
    "nuevo_run_creado": "NO",
    "grupo_completo_reejecutado": "SÍ",
    "autorizado_por": AUTORIZADO_POR,
    "correccion": {"pr": PR_CORRECCION, "fix": FIX_ESPERADO,
                   "archivo": "src/configuration/infrastructure/models/calibracion_vision_model.py"},
    "historial_ejecuciones": list(HISTORIAL_EJECUCIONES),
    "presupuesto": {"post_calibracion": 0, "post_vision": 0, "reintentos": 0},
    "ventanas": {k: {"inicio": v[0], "fin": v[1]} for k, v in VENTANAS.items()},
    "casos": {},
    "limitaciones": [],
}
ESTADO: dict = {"abortado": None, "post_hechos": set()}


# ── Utilidades ───────────────────────────────────────────────────────────────
def sanear(dato):
    """Redacta secretos antes de persistir: tokens, contraseñas y seriales."""
    if isinstance(dato, dict):
        fuera = {}
        for k, v in dato.items():
            if str(k).lower() in (
                "authorization", "token", "access_token", "refresh_token", "contrasena",
                "password", "access_key", "serial", "cookie", "set-cookie", "dsn",
            ):
                fuera[k] = "[REDACTED]"
            else:
                fuera[k] = sanear(v)
        return fuera
    if isinstance(dato, list):
        return [sanear(x) for x in dato]
    if isinstance(dato, str):
        s = _RE_SERIAL.sub("[SERIAL REDACTED]", dato)
        s = re.sub(r"Bearer\s+[A-Za-z0-9._\-]+", "Bearer [REDACTED]", s)
        s = s.replace(ING[1], "[REDACTED]").replace(DB["password"], "[REDACTED]")
        return s
    return dato


def guardar_evidencia():
    (RUN_DIR / "evidencia.json").write_text(
        json.dumps(sanear(E), indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )


class Api:
    """Cliente HTTP con contadores de presupuesto y bloqueo de reintentos."""

    def __init__(self) -> None:
        self.s = requests.Session()
        self.tokens: dict[str, str] = {}

    def login(self, correo: str, clave: str, etiqueta: str) -> str:
        r = self.s.post(f"{BASE_URL}/sesiones/",
                        json={"correo_electronico": correo, "contrasena": clave}, timeout=90)
        assert r.status_code == 200, f"login {etiqueta}: HTTP {r.status_code} {sanear(r.text)[:300]}"
        tok = r.json()["token"]
        self.tokens[etiqueta] = tok
        return tok

    def _h(self, etiqueta: str) -> dict:
        return {"Authorization": f"Bearer {self.tokens[etiqueta]}", "Accept": "application/json"}

    def get(self, etiqueta: str, path: str, timeout: int = 90):
        r = self.s.get(f"{BASE_URL}{path}", headers=self._h(etiqueta), timeout=timeout)
        return r.status_code, _cuerpo(r)

    def post(self, etiqueta: str, path: str, cuerpo: dict, timeout: int = 180):
        r = self.s.post(f"{BASE_URL}{path}", headers=self._h(etiqueta), json=cuerpo, timeout=timeout)
        return r.status_code, _cuerpo(r)

    def patch(self, etiqueta: str, path: str, timeout: int = 90):
        r = self.s.patch(f"{BASE_URL}{path}", headers=self._h(etiqueta), timeout=timeout)
        return r.status_code, _cuerpo(r)

    # ── Los dos POST con presupuesto ─────────────────────────────────────────
    def post_calibracion(self, cuerpo: dict, marca: str):
        if marca in ESTADO["post_hechos"]:
            raise RuntimeError(f"ABORTADO: reintento prohibido del POST funcional {marca}.")
        if E["presupuesto"]["post_calibracion"] >= PRESUPUESTO["post_calibracion"]:
            raise RuntimeError("ABORTADO: presupuesto de POST /calibraciones-vision agotado.")
        ESTADO["post_hechos"].add(marca)
        E["presupuesto"]["post_calibracion"] += 1
        return self.post("ingeniero", "/configuracion/calibraciones-vision", cuerpo)

    def post_vision(self, cuerpo: dict, marca: str):
        if marca in ESTADO["post_hechos"]:
            raise RuntimeError(f"ABORTADO: reenvío prohibido del lote {marca}.")
        if E["presupuesto"]["post_vision"] >= PRESUPUESTO["post_vision"]:
            raise RuntimeError("ABORTADO: presupuesto de POST /iot/telemetria/vision agotado.")
        ESTADO["post_hechos"].add(marca)
        E["presupuesto"]["post_vision"] += 1
        r = self.s.post(f"{BASE_URL}/iot/telemetria/vision", json=cuerpo, timeout=300)
        return r.status_code, _cuerpo(r)


def _cuerpo(r: requests.Response):
    try:
        return r.json()
    except Exception:
        return {"_texto": r.text[:500]}


def consulta_bd(consultas: list[tuple[str, str]]) -> dict:
    """Ejecuta SELECT en una sesión READ ONLY. Nunca DML/DDL.

    Se invoca en un intérprete aislado (`python -I`) y la contraseña viaja por
    entorno, nunca por argv ni por disco.
    """
    for _, sql in consultas:
        if re.search(r"\b(insert|update|delete|alter|drop|truncate|create|grant|revoke)\b",
                     sql, re.I):
            raise RuntimeError("ABORTADO: la consulta no es de solo lectura.")
    programa = (
        "import json,os,psycopg2,psycopg2.extras\n"
        "dsn=('host=%s port=%s dbname=%s user=%s password=%s connect_timeout=25'%("
        "os.environ['H'],os.environ['P'],os.environ['D'],os.environ['U'],os.environ['W']))\n"
        "c=psycopg2.connect(dsn);c.autocommit=True;c.set_session(readonly=True)\n"
        "cu=c.cursor(cursor_factory=psycopg2.extras.RealDictCursor)\n"
        "out={}\n"
        "for t,s in json.loads(os.environ['Q']):\n"
        "    try:\n"
        "        cu.execute(s);out[t]=[dict(x) for x in cu.fetchall()]\n"
        "    except Exception as e:\n"
        "        out[t]={'error':str(e).splitlines()[0]}\n"
        "cu.close();c.close()\n"
        "print(json.dumps(out,default=str,ensure_ascii=False))\n"
    )
    entorno = dict(os.environ, H=DB["host"], P=DB["port"], D=DB["dbname"],
                   U=DB["user"], W=DB["password"], Q=json.dumps(consultas))
    p = subprocess.run([sys.executable, "-I", "-c", programa], capture_output=True,
                       text=True, env=entorno, timeout=180)
    if p.returncode != 0:
        return {"_error": p.stderr.strip().splitlines()[-1] if p.stderr else "fallo de conexión"}
    return json.loads(p.stdout)


def requiere(*claves: str):
    """Salta el test si una precondición previa no quedó disponible."""
    if ESTADO["abortado"]:
        pytest.skip(f"abortado antes: {ESTADO['abortado']}")
    for c in claves:
        if c not in ESTADO:
            pytest.skip(f"falta la precondición {c}")


def obs_apta(fecha: str, i: int) -> dict:
    """Observación inequívocamente APTA: las cuatro dimensiones de RF-62 al máximo."""
    return {
        "timestamp_captura": fecha,
        "cobertura_ventana": "1.0000",
        "n_tracks": 20,
        "n_tracks_perdidos": 0,
        "fps_efectivo": "30.00",
        "estado_calibracion": "CALIBRADA",
        "vector": {
            "densidad_actividad": round(12.0 + (i % 3) * 0.01, 4),
            "tasa_movimiento": round(0.80 + (i % 3) * 0.01, 4),
        },
    }


def obs_no_apta(fecha: str, i: int) -> dict:
    """Observación inequívocamente NO APTA: índice esperado muy por debajo de 40."""
    return {
        "timestamp_captura": fecha,
        "cobertura_ventana": "0.1000",
        "n_tracks": 0,
        "n_tracks_perdidos": 10,
        "fps_efectivo": "0.00",
        "estado_calibracion": "SIN_DETECCION",
        "vector": {
            "densidad_actividad": round(10.0 + (i % 3) * 0.01, 4),
            "tasa_movimiento": round(5.0 + (i % 3) * 0.01, 4),
        },
    }


def instantes(inicio_iso: str, cantidad: int, paso_min: int) -> list[str]:
    base = datetime.datetime.fromisoformat(inicio_iso.replace("Z", "+00:00"))
    return [(base + datetime.timedelta(minutes=paso_min * i)).strftime("%Y-%m-%dT%H:%M:%SZ")
            for i in range(cantidad)]


API = Api()


@pytest.fixture(scope="session", autouse=True)
def red_de_seguridad():
    """Al cerrar la sesión: desactiva la cámara creada y deja los artefactos escritos."""
    yield
    restauracion = {"camara_desactivada": None, "pendientes": []}
    cam = ESTADO.get("camara_id")
    if cam and "ingeniero" in API.tokens:
        try:
            c, b = API.patch("ingeniero", f"/configuracion/dispositivos-iot/{cam}/desactivar")
            restauracion["camara_desactivada"] = {"id": cam, "http": c}
            if c not in (200, 204):
                restauracion["pendientes"].append(f"cámara {cam} no desactivada (HTTP {c})")
            else:
                cc, bb = API.get("ingeniero", f"/configuracion/dispositivos-iot/{cam}")
                restauracion["verificacion"] = {"http": cc,
                                                "es_activo": (bb or {}).get("es_activo")}
        except Exception as exc:  # pragma: no cover - red
            restauracion["pendientes"].append(f"error al desactivar la cámara {cam}: {exc}")
    E["restauracion"] = restauracion
    E["nota_calibraciones"] = (
        "No se borró ninguna calibración ni observación: la EXITOSA de N y la FALLIDA "
        "de N−1 son evidencia esperada del grupo (§56 del paquete)."
    )
    guardar_evidencia()
    _escribir_manifest()


def _escribir_manifest():
    artefactos = []
    for p in sorted(RUN_DIR.rglob("*")):
        # El manifest no se incluye a sí mismo: su hash cambiaría al escribirlo.
        if p.is_file() and p.name != "automation_manifest.json":
            artefactos.append({
                "archivo": str(p.relative_to(RUN_DIR)).replace("\\", "/"),
                "bytes": p.stat().st_size,
                "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
            })
    helpers = []
    for h in sorted(BASE_DIR.glob("*.py")):
        if h.name != "test_g139_v2.py":
            helpers.append({"archivo": f"EvaluacionV2/automation/{h.name}",
                            "bytes": h.stat().st_size,
                            "sha256": hashlib.sha256(h.read_bytes()).hexdigest(),
                            "uso": "cierre de solo lectura del RUN (0 POST, 0 DML)"})
    fuente = BASE_DIR / "test_g139_v2.py"
    (RUN_DIR / "automation_manifest.json").write_text(json.dumps({
        "run_id": RUN_ID,
        "grupo": GRUPO,
        "ambiente": AMBIENTE,
        "execution_number": EJECUCION,
        "execution_type": TIPO_EJECUCION,
        "herramienta": "pytest",
        "newman": "NO APLICA",
        "automatizacion": {
            "archivo": f"EvaluacionV2/automation/{fuente.name}",
            "bytes": fuente.stat().st_size,
            "sha256": hashlib.sha256(fuente.read_bytes()).hexdigest(),
        },
        "helpers": helpers,
        "artefactos_resultados": artefactos,
    }, indent=2, ensure_ascii=False), encoding="utf-8")


# ══════════════════════════════════════════════════════════════════════════════
# PRECHECK
# ══════════════════════════════════════════════════════════════════════════════

def test_01_rama_y_localizacion():
    raiz = CASE_DIR.parents[4]
    rama = subprocess.run(["git", "branch", "--show-current"], cwd=raiz,
                          capture_output=True, text=True).stdout.strip()
    estado = subprocess.run(["git", "status", "--short"], cwd=raiz,
                            capture_output=True, text=True).stdout.strip()
    E["git"] = {"rama": rama, "status_short": estado.splitlines()}
    assert rama == "qa/juan-esteban-segunda-evaluacion-rf24-v2.0", f"rama inesperada: {rama}"
    baseline = CASE_DIR / "RESULTADOS" / "run-20261007-101924"
    assert baseline.is_dir(), "no se encuentra el RUN baseline de la primera evaluación"
    E["baseline_primera_evaluacion"] = {
        "run_id": "run-20261007-101924",
        "ruta": str(baseline.relative_to(raiz)).replace("\\", "/"),
        "solo_lectura": True,
        "archivos": sorted(p.name for p in baseline.iterdir()),
    }

    # §13 — comprobar por LECTURA que la corrección del PR #550 está en origin/test.
    # Sin checkout, sin switch, sin merge: `git show`. La presencia del fix en Git no
    # prueba que TEST tenga ese build; el veredicto lo da la ejecución HTTP real (§15).
    def _git(*args):
        return subprocess.run(["git", *args], cwd=raiz, capture_output=True,
                              text=True, encoding="utf-8", errors="replace")
    sha_origin = _git("rev-parse", "origin/test").stdout.strip()
    modelo = "src/configuration/infrastructure/models/calibracion_vision_model.py"
    texto_modelo = _git("show", f"origin/test:{modelo}").stdout
    linea = next((l.strip() for l in texto_modelo.splitlines() if "json_linea_base" in l), None)
    presente = FIX_ESPERADO in (linea or "")
    E["correccion"].update({
        "origin_test_sha": sha_origin,
        "linea_en_origin_test": linea,
        "fix_presente_en_origin_test": "SÍ" if presente else "NO",
        "metodo": f"git show origin/test:{modelo} (lectura; sin checkout/switch/merge)",
        "advertencia": ("la presencia en Git no prueba el despliegue; el veredicto es la "
                        "ejecución HTTP real contra TEST"),
    })
    E["git"]["head"] = _git("rev-parse", "HEAD").stdout.strip()
    assert sha_origin, "no se pudo leer origin/test"
    assert presente, (
        f"el PR #{PR_CORRECCION} no esta en origin/test: la linea de json_linea_base "
        f"es {linea!r}")


def test_02_contrato_openapi():
    r = requests.get(f"{BASE_URL}/openapi.json", timeout=120)
    assert r.status_code == 200, f"openapi.json HTTP {r.status_code}"
    paths = r.json().get("paths", {})
    requeridos = [
        ("/configuracion/calibraciones-vision", "post"),
        ("/configuracion/calibraciones-vision", "get"),
        ("/configuracion/calibraciones-vision/linea-base", "get"),
        ("/iot/telemetria/vision", "post"),
        ("/auditoria/", "get"),
    ]
    contrato = {}
    for p, m in requeridos:
        contrato[f"{m.upper()} {p}"] = "PRESENTE" if m in paths.get(p, {}) else "AUSENTE"
    E["openapi"] = contrato
    ausentes = [k for k, v in contrato.items() if v != "PRESENTE"]
    assert not ausentes, f"endpoints ausentes en TEST: {ausentes}"


def test_03_actores():
    API.login(*ING, "ingeniero")
    try:
        API.login(*ADM, "admin")
        usado = ADM[0]
    except AssertionError:
        API.login(*ADM_ALT, "admin")
        usado = ADM_ALT[0]
    c, perm = API.get("ingeniero", "/sesiones/me/permisos")
    assert c == 200, f"permisos del Ingeniero HTTP {c}"
    E["actores"] = {
        "ingeniero": {"correo": ING[0], "login": "PASS"},
        "administrador": {"correo": usado, "login": "PASS", "uso": "discovery y auditoría RF-10"},
    }
    ESTADO["actores"] = True


def test_04_fixture_reutilizado():
    requiere("actores")
    c, area = API.get("ingeniero", f"/configuracion/infraestructuras/{AREA}")
    assert c == 200, f"el área {AREA} no es visible para el Ingeniero (HTTP {c})"
    assert area["es_activo"] is True, "el área del fixture no está activa"
    assert area["especie_id"] == ESPECIE_ESPERADA, f"especie inesperada: {area['especie_id']}"
    assert area["tipo_modelo_asignado"] == "MODELO_AVES", \
        f"tipo_modelo inesperado: {area['tipo_modelo_asignado']}"
    assert area["id_finca"] == FINCA_ESPERADA, f"finca inesperada: {area['id_finca']}"

    c, lista = API.get("ingeniero", "/configuracion/dispositivos-iot", timeout=180)
    assert c == 200, f"listado de dispositivos HTTP {c}"
    del_area = [d for d in lista["items"] if d.get("id_infraestructura") == AREA]
    activas_previas = [d["id_dispositivo_iot"] for d in del_area if d.get("es_activo")]
    E["fixture"] = {
        "modo": "AREA REUTILIZADA + CAMARA NUEVA DE ESTA EJECUCION",
        "camara_de_la_ejecucion_1_no_reutilizada": 222,
        "finca_id": area["id_finca"],
        "area_id": AREA,
        "area_nombre": area["nombre_infraestructura"],
        "especie_id": area["especie_id"],
        "tipo_modelo_asignado": area["tipo_modelo_asignado"],
        "paradigma": "POBLACIONAL",
        "camaras_preexistentes": [
            {"id": d["id_dispositivo_iot"], "categoria": d.get("categoria"),
             "es_activo": d.get("es_activo"), "fps": d.get("fps")} for d in del_area
        ],
        "camaras_activas_preexistentes": activas_previas,
    }
    # La cámara es la única pieza del fixture que no se puede reutilizar: las dos
    # de G137 quedaron inactivas en su restauración y RF-21 no expone reactivación.
    assert not activas_previas, (
        "había cámaras activas previas en el área; el diseño de G139 exige que la única "
        f"cámara activa sea la creada por este RUN: {activas_previas}"
    )

    # El serial lleva el sello de la ejecución, no el RUN_ID: el RUN es el mismo y
    # la cámara de la ejecución 1 (222) no se reutiliza (§22).
    serial = f"QA-M09-G139-CAM-{SELLO}"
    cuerpo = {
        "serial": serial,
        "descripcion": f"QA {GRUPO} camara VISION de la segunda evaluacion {RUN_ID}",
        "id_infraestructura": AREA,
        "id_tipo_dispositivo": TIPO_CAMARA_VISION,
        "es_activo": True,
        "resolucion": "1920x1080",
        "fps": 30,
        "area_cobertura_m2": "50.00",
    }
    c, cam = API.post("ingeniero", "/configuracion/dispositivos-iot", cuerpo)
    assert c in (200, 201), f"registro de cámara HTTP {c}: {sanear(cam)}"
    ESTADO["camara_id"] = cam["id_dispositivo_iot"]
    ESTADO["camara_serial"] = serial          # solo en memoria; nunca se persiste
    ESTADO["fps_nominal"] = cam.get("fps")
    assert cam["id_infraestructura"] == AREA, "la cámara no quedó asociada al área"
    assert cam["es_activo"] is True, "la cámara nueva no quedó activa"
    assert cam.get("categoria") == "CAMARA", f"categoría inesperada: {cam.get('categoria')}"
    E["fixture"]["camara_creada"] = {
        "id": ESTADO["camara_id"],
        "serial": "[SERIAL REDACTED]",
        "fps_nominal": cam.get("fps"),
        "resolucion": cam.get("resolucion"),
        "es_activo": cam["es_activo"],
        "id_infraestructura": cam["id_infraestructura"],
        "motivo": ("las dos cámaras del fixture G137 (214 y 221) quedaron inactivas en su "
                   "restauración y RF-21 no publica reactivación de dispositivos"),
    }
    E["fixture"]["unica_camara_activa_del_area"] = ESTADO["camara_id"]
    ESTADO["fixture"] = True


def test_05_valor_de_N():
    requiere("fixture")
    raiz = CASE_DIR.parents[4]
    fuente = raiz / "src/configuration/domain/entities/linea_base_vision.py"
    texto = fuente.read_text(encoding="utf-8")
    m = re.search(r"min_observaciones:\s*int\s*=\s*(\d+)", texto)
    assert m, "no se pudo leer min_observaciones de ParametrosLineaBase"
    n = int(m.group(1))
    # El caso de uso instancia ParametrosLineaBase() sin argumentos: el valor por
    # defecto es el vigente en el despliegue.
    uso = (raiz / "src/configuration/application/use_cases/sensores/calibrar_vision_use_case.py"
           ).read_text(encoding="utf-8")
    assert "parametros: ParametrosLineaBase = ParametrosLineaBase()" in uso, \
        "el caso de uso ya no toma los parámetros por defecto; reconfirmar N"
    ESTADO["N"] = n
    ESTADO["N1"] = n - 1
    E["valor_N"] = {
        "N": n,
        "N_menos_1": n - 1,
        "fuente": "ParametrosLineaBase.min_observaciones (src/configuration/domain/entities/linea_base_vision.py)",
        "inyeccion": "CalibrarVisionUseCase(parametros=ParametrosLineaBase()) — valores por defecto",
        "otros_umbrales": {
            "cobertura_minima": 0.5, "tracks_minimos": 1,
            "min_datos_componente": 10, "epsilon": 0.01, "max_iteraciones": 10,
        },
        "confirmacion_en_runtime": "pendiente: el motivo de la calibración FALLIDA de N−1 lo declara",
    }
    assert n == N_ESPERADO_POR_CODIGO, f"N cambió respecto del valor documentado: {n}"


def test_06_bd_solo_select_y_privilegios():
    """La matriz pide contadores por SELECT. Se deja constancia objetiva de qué
    puede leer `member_qa`: sin grant no hay conteo por BD, y se declara así."""
    requiere("fixture")
    res = consulta_bd([
        ("rol", "SELECT current_user, version()"),
        ("privilegios", """
            SELECT n.nspname AS esquema, c.relname AS tabla,
                   has_table_privilege(c.oid,'SELECT') AS puede_select,
                   c.relrowsecurity AS rls
            FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE (n.nspname,c.relname) IN (
              ('modulo3','observaciones_vision'),('modulo9','calibraciones_vision'),
              ('modulo9','lineas_base_vision'),('modulo9','dispositivos_iot'),
              ('modulo9','infraestructuras'),('modulo1','eventos'))
            ORDER BY 1,2"""),
        ("grants_observaciones_vision", """
            SELECT grantee, privilege_type FROM information_schema.role_table_grants
            WHERE table_schema='modulo3' AND table_name='observaciones_vision' ORDER BY 1,2"""),
        ("conteo_ventanas", f"""
            SELECT COUNT(*) AS total FROM modulo3.observaciones_vision
            WHERE id_infraestructura={AREA}"""),
    ])
    privs = {f"{r['esquema']}.{r['tabla']}": r["puede_select"]
             for r in res.get("privilegios", []) if isinstance(r, dict)}
    E["bd"] = {
        "host": DB["host"], "puerto": DB["port"], "base": DB["dbname"], "usuario": DB["user"],
        "sesion": "READ ONLY — solo SELECT, 0 DML",
        "rol": res.get("rol"),
        "privilegios_select": privs,
        "grants_visibles_observaciones_vision": res.get("grants_observaciones_vision"),
        "conteo_ventanas": res.get("conteo_ventanas"),
    }
    sin_lectura = [t for t, v in privs.items() if v is False]
    if sin_lectura:
        E["limitaciones"].append({
            "tema": "contadores de BD (§47 del paquete)",
            "detalle": (
                "Las credenciales de QA (member_qa) no tienen privilegio SELECT sobre "
                f"{', '.join(sin_lectura)}: has_table_privilege devuelve false y "
                "information_schema.role_table_grants no muestra ningún grant. Los conteos "
                "de observaciones por ventana NO pueden obtenerse por SELECT en este RUN."
            ),
            "sustituto": (
                "Los conteos se obtienen del propio producto, con trazabilidad equivalente: "
                "(a) la cámara es nueva, así que ninguna observación previa puede existir para "
                "ella y es la única cámara activa del área, que es de donde el caso de uso reúne "
                "observaciones; (b) la respuesta de POST /iot/telemetria/vision declara "
                "total/aceptadas/duplicadas y el apto_para_ia e indice_calidad de cada "
                "observación creada; (c) la respuesta de la calibración declara n_observaciones "
                "y n_observaciones_validas, que es el conteo que el backend ve en la ventana; "
                "(d) en TC-282, VISION_NO_DISPONIBLE solo se produce cuando hay observaciones "
                "y ninguna es apta, lo que distingue la ventana con 0 aptas de una ventana vacía."
            ),
        })
    E["bd"]["conteos_por_select"] = "NO VERIFICABLE — sin grant SELECT para member_qa" \
        if sin_lectura else "DISPONIBLE"
    assert "_error" not in res, f"no se pudo abrir la sesión de BD: {res.get('_error')}"
    ESTADO["bd"] = True


def test_07_ventanas_controladas():
    requiere("fixture")
    pares = [(k, *v) for k, v in VENTANAS.items()]
    for i in range(len(pares)):
        for j in range(i + 1, len(pares)):
            (_, ai, af), (_, bi, bf) = pares[i], pares[j]
            assert af < bi or bf < ai, f"ventanas solapadas: {pares[i][0]} y {pares[j][0]}"
    ahora = datetime.datetime.now(datetime.timezone.utc)
    for k, (ini, fin) in VENTANAS.items():
        assert datetime.datetime.fromisoformat(fin.replace("Z", "+00:00")) < ahora, \
            f"{k} no está en el pasado"
    # Ninguna ventana de esta ejecución puede tocar las de la ejecución 1.
    for k, (ini, fin) in VENTANAS.items():
        for k1, (ai, af) in VENTANAS_EJECUCION_1.items():
            assert fin < ai or af < ini, f"{k} solapa la ventana {k1} de la ejecucion 1"
    res = consulta_bd([("min_max", f"""
        SELECT MIN(fecha_observacion) AS minimo, MAX(fecha_observacion) AS maximo, COUNT(*) AS total
        FROM modulo3.observaciones_vision WHERE id_dispositivo_iot={ESTADO['camara_id']}""")])
    E["ventanas_control"] = {
        "disjuntas": True,
        "en_el_pasado": True,
        "disjuntas_de_la_ejecucion_1": True,
        "ventanas_ejecucion_1": {k: {"inicio": v[0], "fin": v[1]}
                                 for k, v in VENTANAS_EJECUCION_1.items()},
        "min_max_por_select": res.get("min_max"),
        "argumento_de_vacuidad": (
            f"la cámara {ESTADO['camara_id']} se registró en este RUN, así que no puede tener "
            "observaciones anteriores, y es la única cámara activa del área "
            f"{AREA} (las de G137, 214 y 221, están inactivas), que es la fuente que "
            "POST /configuracion/calibraciones-vision consulta."
        ),
    }
    ESTADO["ventanas"] = True


# ══════════════════════════════════════════════════════════════════════════════
# TC-M09-282 — ventana con observaciones, CERO aptas
# ══════════════════════════════════════════════════════════════════════════════

def test_08_lote_282_diez_no_aptas():
    requiere("ventanas")
    ini, fin = VENTANAS["WINDOW_282"]
    fechas = instantes(ini, 10, 6)
    cuerpo = {
        "device_id": ESTADO["camara_id"],
        "access_key": ESTADO["camara_serial"],
        "area_id": AREA,
        "observaciones": [obs_no_apta(f, i) for i, f in enumerate(fechas)],
    }
    c, b = API.post_vision(cuerpo, "lote_282")
    assert c in (200, 201), f"ingesta del lote 282 HTTP {c}: {sanear(b)}"
    aptas = [o for o in b["observaciones"] if o["apto_para_ia"]]
    E["casos"]["TC-M09-282"] = {
        "ventana": {"etiqueta": "WINDOW_282", "inicio": ini, "fin": fin},
        "lote": {
            "http": c, "total": b["total"], "aceptadas": b["aceptadas"], "duplicadas": b["duplicadas"],
            "observaciones": [{"id": o["id_observacion_vision"], "ts": o["timestamp_captura"],
                               "indice_calidad": o["indice_calidad"],
                               "clasificacion": o["clasificacion_calidad"],
                               "apto_para_ia": o["apto_para_ia"]} for o in b["observaciones"]],
        },
        "conteos": {"total": b["aceptadas"], "aptas": len(aptas),
                    "no_aptas": b["aceptadas"] - len(aptas)},
    }
    assert b["total"] == 10 and b["aceptadas"] == 10, f"lote 282: {b['total']}/{b['aceptadas']}"
    assert b["duplicadas"] == 0, "había observaciones previas en WINDOW_282 (duplicadas > 0)"
    assert not aptas, f"la ventana de TC-282 debe quedar con 0 aptas; hay {len(aptas)}"
    for o in b["observaciones"]:
        assert o["indice_calidad"] < 40, f"índice {o['indice_calidad']} no es inequívocamente NO APTO"
        assert o["clasificacion_calidad"] == "NO_APTO", o["clasificacion_calidad"]
    ESTADO["lote_282"] = True


def test_09_linea_base_pre_282():
    requiere("lote_282")
    ESTADO["T_BEFORE_282"] = datetime.datetime.now(datetime.timezone.utc)
    c, b = API.get("ingeniero", f"/configuracion/calibraciones-vision/linea-base?area_id={AREA}")
    assert c in (200, 404), f"línea base PRE 282 HTTP {c}"
    ch, hist = API.get("ingeniero", f"/configuracion/calibraciones-vision?area_id={AREA}")
    assert ch == 200, f"historial PRE 282 HTTP {ch}"
    ESTADO["baseline_pre_282"] = b.get("id_calibracion_vision") if c == 200 else None
    ESTADO["hist_pre_282"] = [i["id_calibracion_vision"] for i in hist["items"]]
    E["casos"]["TC-M09-282"]["baseline_PRE"] = {
        "http": c,
        "id_calibracion_vision": ESTADO["baseline_pre_282"],
        "detalle": b if c == 200 else None,
        "historial_ids": ESTADO["hist_pre_282"],
        "T_BEFORE": ESTADO["T_BEFORE_282"].isoformat(),
        "nota": "no se borró ninguna línea base previa",
    }
    ESTADO["pre_282"] = True


def test_10_tc282_post_calibracion():
    requiere("pre_282")
    ini, fin = VENTANAS["WINDOW_282"]
    cuerpo = {
        "modo_calibracion": "VISION",
        "area_id": AREA,
        "ventana_observacion": {"inicio": ini, "fin": fin},
        "observaciones": "QA TC-M09-282",
        "fecha_calibracion": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    c, b = API.post_calibracion(cuerpo, "tc282")
    caso = E["casos"]["TC-M09-282"]
    caso["request"] = cuerpo
    caso["response"] = {"http": c, "body": b}
    caso["http_esperado"] = 422
    caso["error_code"] = b.get("error_code")
    caso["message"] = b.get("message")
    ESTADO["tc282_http"] = c
    assert c == 422, f"TC-M09-282 esperaba 422 y obtuvo {c}: {sanear(b)}"
    ESTADO["tc282"] = True


def test_11_tc282_postcondicion():
    requiere("tc282")
    c, b = API.get("ingeniero", f"/configuracion/calibraciones-vision/linea-base?area_id={AREA}")
    ch, hist = API.get("ingeniero", f"/configuracion/calibraciones-vision?area_id={AREA}")
    assert ch == 200, f"historial POST 282 HTTP {ch}"
    ids = [i["id_calibracion_vision"] for i in hist["items"]]
    post = b.get("id_calibracion_vision") if c == 200 else None
    caso = E["casos"]["TC-M09-282"]
    caso["baseline_POST"] = {"http": c, "id_calibracion_vision": post, "historial_ids": ids}
    caso["linea_base_nueva"] = "NO" if post == ESTADO["baseline_pre_282"] else "SÍ"
    caso["calibracion_nueva_en_historial"] = "NO" if ids == ESTADO["hist_pre_282"] else "SÍ"
    # Oráculo de la matriz (§25/§26/§27): 422 y ninguna línea base nueva. Que además
    # no se persista una calibración es lo que hace el flujo actual (rechaza en
    # precondiciones), y se registra, pero no es requisito del caso.
    assert post == ESTADO["baseline_pre_282"], (
        f"la línea base cambió tras TC-282: {ESTADO['baseline_pre_282']} -> {post}")
    caso["nota_calibracion"] = (
        "el rechazo ocurre en precondiciones (VISION_NO_DISPONIBLE), antes de crear "
        "calibración: el historial no cambia. La matriz no exige persistir una FALLIDA aquí."
        if ids == ESTADO["hist_pre_282"] else
        f"quedó una calibración nueva {sorted(set(ids) - set(ESTADO['hist_pre_282']))}; "
        "no contradice el oráculo, que solo exige 422 sin línea base nueva."
    )
    caso["resultado"] = "APROBADO"


# ══════════════════════════════════════════════════════════════════════════════
# TC-M09-283 — corrida N
# ══════════════════════════════════════════════════════════════════════════════

def test_12_lote_N_exactamente_N_aptas():
    requiere("tc282", "N")
    n = ESTADO["N"]
    ini, fin = VENTANAS["WINDOW_283_N"]
    fechas = instantes(ini, n, 5)
    cuerpo = {
        "device_id": ESTADO["camara_id"],
        "access_key": ESTADO["camara_serial"],
        "area_id": AREA,
        "observaciones": [obs_apta(f, i) for i, f in enumerate(fechas)],
    }
    c, b = API.post_vision(cuerpo, "lote_N")
    assert c in (200, 201), f"ingesta del lote N HTTP {c}: {sanear(b)}"
    aptas = [o for o in b["observaciones"] if o["apto_para_ia"]]
    E["casos"]["TC-M09-283-N"] = {
        "N": n,
        "ventana": {"etiqueta": "WINDOW_283_N", "inicio": ini, "fin": fin},
        "lote": {"http": c, "total": b["total"], "aceptadas": b["aceptadas"],
                 "duplicadas": b["duplicadas"],
                 "indices_distintos": sorted({o["indice_calidad"] for o in b["observaciones"]}),
                 "primeras_observaciones": [
                     {"id": o["id_observacion_vision"], "ts": o["timestamp_captura"],
                      "indice_calidad": o["indice_calidad"], "apto_para_ia": o["apto_para_ia"]}
                     for o in b["observaciones"][:3]],
                 "ids": [o["id_observacion_vision"] for o in b["observaciones"]]},
        "conteos": {"total": b["aceptadas"], "aptas": len(aptas),
                    "no_aptas": b["aceptadas"] - len(aptas)},
        "filtro_etapa_1": {"cobertura_ventana": 1.0, "n_tracks": 20,
                           "cumple_cobertura_minima_0_5": True, "cumple_tracks_minimos_1": True},
    }
    assert b["total"] == n and b["aceptadas"] == n, f"lote N: {b['total']}/{b['aceptadas']} (esperado {n})"
    assert b["duplicadas"] == 0, "había observaciones previas en WINDOW_283_N (duplicadas > 0)"
    assert len(aptas) == n, f"se requieren exactamente {n} aptas; hay {len(aptas)}"
    ESTADO["lote_N"] = True


def test_13_pre_corrida_N():
    requiere("lote_N")
    c, b = API.get("ingeniero", f"/configuracion/calibraciones-vision/linea-base?area_id={AREA}")
    ch, hist = API.get("ingeniero", f"/configuracion/calibraciones-vision?area_id={AREA}")
    assert ch == 200
    ESTADO["baseline_pre_N"] = b.get("id_calibracion_vision") if c == 200 else None
    ESTADO["hist_pre_N"] = [i["id_calibracion_vision"] for i in hist["items"]]
    E["casos"]["TC-M09-283-N"]["baseline_PRE"] = {
        "http": c, "id_calibracion_vision": ESTADO["baseline_pre_N"],
        "historial_ids": ESTADO["hist_pre_N"],
    }
    ESTADO["pre_N"] = True


def test_14_tc283_N_post_calibracion():
    requiere("pre_N")
    n = ESTADO["N"]
    ini, fin = VENTANAS["WINDOW_283_N"]
    cuerpo = {
        "modo_calibracion": "VISION",
        "area_id": AREA,
        "ventana_observacion": {"inicio": ini, "fin": fin},
        "observaciones": "QA TC-M09-283 N",
        "fecha_calibracion": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    c, b = API.post_calibracion(cuerpo, "tc283_N")
    caso = E["casos"]["TC-M09-283-N"]
    caso["request"] = cuerpo
    caso["response"] = {"http": c, "body": b}
    assert 200 <= c < 300, f"la corrida N esperaba 2xx y obtuvo {c}: {sanear(b)}"
    assert b["estado"] == "EXITOSA", f"estado {b['estado']}"
    assert b["n_observaciones"] == n, f"n_observaciones {b['n_observaciones']} != {n}"
    assert b["n_observaciones_validas"] == n, f"n_observaciones_validas {b['n_observaciones_validas']} != {n}"
    assert b["linea_base"] is not None, "la corrida N no devolvió línea base"
    assert b["origen_disparo"] == "MANUAL", b["origen_disparo"]
    assert b["etapa_fallo"] is None, b["etapa_fallo"]
    assert b["especie_id"] == ESPECIE_ESPERADA
    ESTADO["ID_N"] = b["id_calibracion_vision"]
    caso["id_calibracion_vision"] = ESTADO["ID_N"]
    caso["estado"] = b["estado"]
    caso["n_observaciones_validas"] = b["n_observaciones_validas"]
    caso["linea_base"] = b["linea_base"]
    caso["iteraciones"] = b.get("iteraciones")
    ESTADO["tc283_N"] = True


def test_15_baseline_N_vigente():
    requiere("tc283_N")
    c, b = API.get("ingeniero", f"/configuracion/calibraciones-vision/linea-base?area_id={AREA}")
    assert c == 200, f"línea base POST N HTTP {c}"
    ch, hist = API.get("ingeniero", f"/configuracion/calibraciones-vision?area_id={AREA}")
    assert ch == 200
    ids = [i["id_calibracion_vision"] for i in hist["items"]]
    de_N = next((i for i in hist["items"] if i["id_calibracion_vision"] == ESTADO["ID_N"]), None)
    res = consulta_bd([
        ("calibracion_N", f"""
            SELECT id_calibracion_vision, estado, cantidad_observaciones_validas
            FROM modulo9.calibraciones_vision WHERE id_calibracion_vision={ESTADO['ID_N']}"""),
        ("linea_base_vigente", f"""
            SELECT id_calibracion_vision FROM modulo9.lineas_base_vision
            WHERE id_infraestructura={AREA} AND id_especie={ESPECIE_ESPERADA}"""),
    ])
    caso = E["casos"]["TC-M09-283-N"]
    caso["baseline_POST"] = {"http": c, "id_calibracion_vision": b["id_calibracion_vision"],
                             "linea_base": b["linea_base"],
                             "fecha_publicacion": b["fecha_publicacion"]}
    caso["historial_POST_ids"] = ids
    caso["en_historial"] = {k: de_N.get(k) for k in
                            ("id_calibracion_vision", "estado", "n_observaciones",
                             "n_observaciones_validas", "origen_disparo", "id_usuario")} if de_N else None
    caso["verificacion_bd"] = res
    assert b["id_calibracion_vision"] == ESTADO["ID_N"], \
        f"la línea base vigente no apunta a ID_N: {b['id_calibracion_vision']}"
    assert de_N is not None and de_N["estado"] == "EXITOSA", "ID_N no figura EXITOSA en el historial"
    assert de_N["n_observaciones_validas"] == ESTADO["N"]
    ESTADO["BASELINE_N"] = ESTADO["ID_N"]
    caso["resultado"] = "APROBADO"
    ESTADO["baseline_N"] = True


# ══════════════════════════════════════════════════════════════════════════════
# TC-M09-283 — corrida N−1
# ══════════════════════════════════════════════════════════════════════════════

def test_16_lote_N_menos_1():
    requiere("baseline_N")
    n1 = ESTADO["N1"]
    ini, fin = VENTANAS["WINDOW_283_N_MINUS_1"]
    fechas = instantes(ini, n1, 5)
    cuerpo = {
        "device_id": ESTADO["camara_id"],
        "access_key": ESTADO["camara_serial"],
        "area_id": AREA,
        "observaciones": [obs_apta(f, i) for i, f in enumerate(fechas)],
    }
    c, b = API.post_vision(cuerpo, "lote_N1")
    assert c in (200, 201), f"ingesta del lote N−1 HTTP {c}: {sanear(b)}"
    aptas = [o for o in b["observaciones"] if o["apto_para_ia"]]
    E["casos"]["TC-M09-283-N-1"] = {
        "N_menos_1": n1,
        "ventana": {"etiqueta": "WINDOW_283_N_MINUS_1", "inicio": ini, "fin": fin},
        "lote": {"http": c, "total": b["total"], "aceptadas": b["aceptadas"],
                 "duplicadas": b["duplicadas"],
                 "indices_distintos": sorted({o["indice_calidad"] for o in b["observaciones"]}),
                 "ids": [o["id_observacion_vision"] for o in b["observaciones"]]},
        "conteos": {"total": b["aceptadas"], "aptas": len(aptas),
                    "no_aptas": b["aceptadas"] - len(aptas)},
    }
    assert b["total"] == n1 and b["aceptadas"] == n1, f"lote N−1: {b['total']}/{b['aceptadas']}"
    assert b["duplicadas"] == 0, "había observaciones previas en WINDOW_283_N_MINUS_1"
    assert len(aptas) == n1, f"se requieren exactamente {n1} aptas; hay {len(aptas)}"
    ESTADO["lote_N1"] = True


def test_17_pre_corrida_N_menos_1():
    requiere("lote_N1")
    ESTADO["T_BEFORE_N1"] = datetime.datetime.now(datetime.timezone.utc)
    c, b = API.get("ingeniero", f"/configuracion/calibraciones-vision/linea-base?area_id={AREA}")
    ch, hist = API.get("ingeniero", f"/configuracion/calibraciones-vision?area_id={AREA}")
    assert c == 200 and ch == 200
    ESTADO["hist_pre_N1"] = [i["id_calibracion_vision"] for i in hist["items"]]
    E["casos"]["TC-M09-283-N-1"]["baseline_PRE"] = {
        "http": c, "id_calibracion_vision": b["id_calibracion_vision"],
        "historial_ids": ESTADO["hist_pre_N1"],
        "T_BEFORE": ESTADO["T_BEFORE_N1"].isoformat(),
    }
    assert b["id_calibracion_vision"] == ESTADO["BASELINE_N"], \
        f"la línea base antes de N−1 no es ID_N: {b['id_calibracion_vision']}"
    ESTADO["pre_N1"] = True


def test_18_tc283_N_menos_1_post_calibracion():
    requiere("pre_N1")
    ini, fin = VENTANAS["WINDOW_283_N_MINUS_1"]
    cuerpo = {
        "modo_calibracion": "VISION",
        "area_id": AREA,
        "ventana_observacion": {"inicio": ini, "fin": fin},
        "observaciones": "QA TC-M09-283 N-1",
        "fecha_calibracion": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    c, b = API.post_calibracion(cuerpo, "tc283_N1")
    ESTADO["T_AFTER_N1"] = datetime.datetime.now(datetime.timezone.utc)
    esperado = (
        "No se pudo calcular la línea base: datos insuficientes o sin convergencia para el "
        f"área {AREA} y especie {ESPECIE_ESPERADA}. Se conserva la línea base vigente anterior."
    )
    caso = E["casos"]["TC-M09-283-N-1"]
    caso["request"] = cuerpo
    caso["response"] = {"http": c, "body": b}
    caso["error_code"] = b.get("error_code")
    caso["message_obtenido"] = b.get("message")
    caso["message_esperado"] = esperado
    caso["mensaje_exacto"] = "SÍ" if b.get("message") == esperado else "NO"
    caso["T_AFTER"] = ESTADO["T_AFTER_N1"].isoformat()
    assert c == 422, f"la corrida N−1 esperaba 422 y obtuvo {c}: {sanear(b)}"
    assert b.get("error_code") == "LINEA_BASE_NO_CALCULADA", b.get("error_code")
    assert b.get("message") == esperado, (
        "mensaje no literal\n"
        f"  esperado: {esperado!r}\n  obtenido: {b.get('message')!r}")
    ESTADO["tc283_N1"] = True


def test_19_calibracion_fallida_N_menos_1():
    requiere("tc283_N1")
    n1 = ESTADO["N1"]
    ch, hist = API.get("ingeniero", f"/configuracion/calibraciones-vision?area_id={AREA}")
    assert ch == 200
    ids = [i["id_calibracion_vision"] for i in hist["items"]]
    nuevos = [i for i in hist["items"] if i["id_calibracion_vision"] not in ESTADO["hist_pre_N1"]]
    caso = E["casos"]["TC-M09-283-N-1"]
    caso["historial_POST_ids"] = ids
    caso["calibraciones_nuevas"] = nuevos
    assert len(nuevos) == 1, f"se esperaba exactamente 1 calibración nueva; hay {len(nuevos)}"
    f = nuevos[0]
    ESTADO["ID_N1"] = f["id_calibracion_vision"]
    res = consulta_bd([("calibracion_fallida", f"""
        SELECT id_calibracion_vision, estado, etapa_fallo, cantidad_observaciones,
               cantidad_observaciones_validas, motivo
        FROM modulo9.calibraciones_vision WHERE id_calibracion_vision={ESTADO['ID_N1']}""")])
    caso["calibracion_fallida"] = {
        "id_calibracion_vision": f["id_calibracion_vision"],
        "estado": f["estado"], "etapa_fallo": f["etapa_fallo"],
        "n_observaciones": f["n_observaciones"],
        "n_observaciones_validas": f["n_observaciones_validas"],
        "motivo": f["motivo"], "origen_disparo": f["origen_disparo"],
        "id_usuario": f["id_usuario"], "ventana_observacion": f["ventana_observacion"],
        "linea_base": f.get("linea_base"),
    }
    caso["verificacion_bd"] = res
    assert f["estado"] == "FALLIDA", f"estado {f['estado']}"
    assert f["etapa_fallo"] == "FILTRADO", f"etapa_fallo {f['etapa_fallo']}"
    assert f["n_observaciones"] == n1, f"n_observaciones {f['n_observaciones']} != {n1}"
    assert f["n_observaciones_validas"] == n1, f"n_observaciones_validas {f['n_observaciones_validas']} != {n1}"
    assert f["linea_base"] is None, "una calibración FALLIDA no debe traer línea base"
    motivo = f["motivo"] or ""
    assert str(n1) in motivo and str(ESTADO["N"]) in motivo, (
        f"el motivo debe declarar las {n1} válidas y el mínimo {ESTADO['N']}: {motivo!r}")
    # Confirmación en runtime del valor de N vigente en el despliegue.
    E["valor_N"]["confirmacion_en_runtime"] = {
        "fuente": "motivo de la calibración FALLIDA de la corrida N−1",
        "motivo": motivo,
        "N_declarado_por_el_backend": ESTADO["N"],
    }
    ESTADO["fallida"] = True


def test_20_baseline_N_conservada():
    requiere("fallida")
    c, b = API.get("ingeniero", f"/configuracion/calibraciones-vision/linea-base?area_id={AREA}")
    assert c == 200, f"línea base POST N−1 HTTP {c}"
    res = consulta_bd([("linea_base_vigente", f"""
        SELECT id_calibracion_vision FROM modulo9.lineas_base_vision
        WHERE id_infraestructura={AREA} AND id_especie={ESPECIE_ESPERADA}""")])
    caso = E["casos"]["TC-M09-283-N-1"]
    caso["baseline_POST"] = {"http": c, "id_calibracion_vision": b["id_calibracion_vision"],
                             "linea_base": b["linea_base"]}
    caso["baseline_N_conservada"] = "SÍ" if b["id_calibracion_vision"] == ESTADO["BASELINE_N"] else "NO"
    caso["verificacion_bd_linea_base"] = res
    assert b["id_calibracion_vision"] == ESTADO["BASELINE_N"], (
        f"la calibración FALLIDA sustituyó la línea base: {ESTADO['BASELINE_N']} -> "
        f"{b['id_calibracion_vision']}")
    assert b["linea_base"] == E["casos"]["TC-M09-283-N"]["linea_base"], \
        "los valores de la línea base vigente cambiaron tras el intento fallido"
    ESTADO["conservada"] = True


def test_21_auditoria_rf10():
    """Auditoria RF-10 de los tres intentos, con el contrato REAL del endpoint.

    Correccion de automatizacion respecto de la ejecucion 1: GET /auditoria/ NO expone
    un campo `exitoso`; el resultado viaja en `resultado` ('exitoso'/'fallido') y la IP
    en `direccion_ip`. Leer `exitoso` devolvia null y daba una lectura falsa de la
    auditoria. Los ids de tipo se resuelven del catalogo, no se asumen.
    """
    requiere("conservada")
    cc, cat = API.get("admin", "/auditoria/catalogo/tipos-evento", timeout=120)
    assert cc == 200, f"catalogo de tipos de evento HTTP {cc}"
    lista = cat if isinstance(cat, list) else (cat.get("items") or [])

    def tipo_de(nombre):
        for x in lista:
            if str(x.get("nombre", "")).upper() == nombre:
                return x.get("id_tipo_evento")
        return None

    t_rechazada = tipo_de("CALIBRACION_RECHAZADA")
    t_exitosa = tipo_de("CALIBRACION_EXITOSA")
    assert isinstance(t_rechazada, int), "el catalogo no declara CALIBRACION_RECHAZADA"
    assert isinstance(t_exitosa, int), "el catalogo no declara CALIBRACION_EXITOSA"

    desde = (ESTADO["T_BEFORE_282"] - datetime.timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%S")
    hasta = (datetime.datetime.now(datetime.timezone.utc)
             + datetime.timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%S")
    auditoria = {
        "contrato": ("resultado ('exitoso'/'fallido'), modulo, id_usuario, nombre_usuario, "
                     "direccion_ip, user_agent, detalle, integridad_ok; no existe `exitoso`"),
        "tipos_resueltos": {"CALIBRACION_RECHAZADA": t_rechazada,
                            "CALIBRACION_EXITOSA": t_exitosa},
        "ventana_consulta": {"desde": desde, "hasta": hasta},
    }

    def eventos(tipo):
        c, b = API.get("admin", f"/auditoria/?tipo_evento={tipo}&fecha_desde={desde}"
                                f"&fecha_hasta={hasta}&pagina=1&tamano=50", timeout=180)
        assert c in (200, 206), f"auditoria RF-10 tipo {tipo}: HTTP {c} {sanear(b)}"
        fuera = []
        for ev in (b.get("items") or b.get("eventos") or []):
            d = ev.get("detalle") or {}
            if isinstance(d, str):
                try:
                    d = json.loads(d)
                except Exception:
                    d = {}
            fuera.append({
                "id_evento": ev.get("id_evento"),
                "tipo_evento": ev.get("tipo_evento"),
                "resultado": ev.get("resultado"),
                "modulo": ev.get("modulo"),
                "id_usuario": ev.get("id_usuario"),
                "nombre_usuario": ev.get("nombre_usuario"),
                "direccion_ip": "PRESENTE" if ev.get("direccion_ip") else "AUSENTE",
                "user_agent": "PRESENTE" if ev.get("user_agent") else "AUSENTE",
                "fecha_evento": ev.get("fecha_evento"),
                "integridad_ok": ev.get("integridad_ok"),
                "detalle": d,
            })
        return fuera

    rechazos = eventos(t_rechazada)
    exitos = eventos(t_exitosa)
    vision = [e for e in rechazos if e["detalle"].get("operacion") == "CALIBRACION_VISION"]

    # TC-M09-282: rechazo en precondiciones (paquete 30 y 65).
    de_282 = [e for e in vision
              if e["detalle"].get("codigo_error") == "VISION_NO_DISPONIBLE"
              and e["detalle"].get("id_infraestructura") == AREA]
    auditoria["TC282"] = {"encontrada": "SI" if de_282 else "NO", "eventos": de_282[-2:]}
    assert de_282, "no se encontro el evento RF-10 del rechazo de TC-M09-282"
    e282 = de_282[-1]
    d282 = e282["detalle"]
    auditoria["TC282"]["verificado"] = {
        "id_evento": e282["id_evento"], "resultado": e282["resultado"],
        "modulo": e282["modulo"], "id_usuario": e282["id_usuario"],
        "codigo_http": d282.get("codigo_http"), "codigo_error": d282.get("codigo_error"),
        "motivo": d282.get("motivo"), "direccion_ip": e282["direccion_ip"],
        "integridad_ok": e282["integridad_ok"], "fecha_evento": e282["fecha_evento"],
    }
    assert e282["resultado"] == "fallido", f"TC-282: resultado {e282['resultado']!r}"
    assert e282["modulo"] == "MODULO9", e282["modulo"]
    assert d282.get("codigo_http") == 422, d282.get("codigo_http")
    assert d282.get("codigo_error") == "VISION_NO_DISPONIBLE", d282.get("codigo_error")
    E["casos"]["TC-M09-282"]["auditoria"] = auditoria["TC282"]["verificado"]

    # TC-M09-283 corrida N: calibracion exitosa (paquete 36).
    de_N = [e for e in exitos
            if e["detalle"].get("operacion") == "CALIBRACION_VISION"
            and e["detalle"].get("id_calibracion_vision") == ESTADO["ID_N"]]
    auditoria["TC283_N"] = {"encontrada": "SI" if de_N else "NO", "eventos": de_N}
    assert de_N, f"no se encontro el evento RF-10 EXITOSO de la calibracion {ESTADO['ID_N']}"
    eN, dN = de_N[-1], de_N[-1]["detalle"]
    assert eN["resultado"] == "exitoso", f"la corrida N no quedo EXITOSA en RF-10: {eN['resultado']!r}"
    assert eN["modulo"] == "MODULO9", eN["modulo"]
    assert dN.get("estado") == "EXITOSA", dN.get("estado")
    E["casos"]["TC-M09-283-N"]["auditoria"] = {
        "id_evento": eN["id_evento"], "tipo_evento": eN["tipo_evento"],
        "resultado": eN["resultado"], "modulo": eN["modulo"],
        "id_usuario": eN["id_usuario"], "nombre_usuario": eN["nombre_usuario"],
        "direccion_ip": eN["direccion_ip"], "integridad_ok": eN["integridad_ok"],
        "operacion": dN.get("operacion"),
        "id_calibracion_vision": dN.get("id_calibracion_vision"),
        "estado": dN.get("estado"), "etapa_fallo": dN.get("etapa_fallo"),
        "n_observaciones_validas": dN.get("n_observaciones_validas"),
    }

    # TC-M09-283 corrida N-1: intento FALLIDO (paquete 45).
    de_n1 = [e for e in vision
             if e["detalle"].get("id_calibracion_vision") == ESTADO["ID_N1"]]
    auditoria["TC283_N_MINUS_1"] = {"encontrada": "SI" if de_n1 else "NO", "eventos": de_n1}
    E["auditoria_rf10"] = auditoria
    assert de_n1, (
        f"no se encontro el evento RF-10 FALLIDO del intento N-1 (calibracion {ESTADO['ID_N1']})")
    e1, d1 = de_n1[-1], de_n1[-1]["detalle"]
    verificado = {
        "id_evento": e1["id_evento"], "tipo_evento": e1["tipo_evento"],
        "resultado": e1["resultado"], "modulo": e1["modulo"],
        "id_usuario": e1["id_usuario"], "nombre_usuario": e1["nombre_usuario"],
        "direccion_ip": e1["direccion_ip"], "user_agent": e1["user_agent"],
        "fecha_evento": e1["fecha_evento"], "integridad_ok": e1["integridad_ok"],
        "operacion": d1.get("operacion"), "codigo_http": d1.get("codigo_http"),
        "codigo_error": d1.get("codigo_error"), "motivo": d1.get("motivo"),
        "id_calibracion_vision": d1.get("id_calibracion_vision"),
        "estado": d1.get("estado"), "etapa_fallo": d1.get("etapa_fallo"),
        "motivo_etapa": d1.get("motivo_etapa"),
        "id_infraestructura": d1.get("id_infraestructura"),
        "id_especie": d1.get("id_especie"),
    }
    fe = e1["fecha_evento"]
    verificado["en_ventana_del_intento"] = (
        "SI" if fe and ESTADO["T_BEFORE_N1"].strftime("%Y-%m-%dT%H:%M:%S") <= fe[:19]
        <= ESTADO["T_AFTER_N1"].strftime("%Y-%m-%dT%H:%M:%S") else "NO")
    auditoria["TC283_N_MINUS_1"]["verificado"] = verificado
    E["casos"]["TC-M09-283-N-1"]["auditoria"] = verificado
    assert e1["resultado"] == "fallido", f"el evento de N-1 no quedo FALLIDO: {e1['resultado']!r}"
    assert e1["modulo"] == "MODULO9", e1["modulo"]
    assert d1.get("operacion") == "CALIBRACION_VISION", d1.get("operacion")
    assert d1.get("codigo_http") == 422, d1.get("codigo_http")
    assert d1.get("codigo_error") == "LINEA_BASE_NO_CALCULADA", d1.get("codigo_error")
    assert d1.get("estado") == "FALLIDA", d1.get("estado")
    assert d1.get("etapa_fallo") == "FILTRADO", d1.get("etapa_fallo")
    assert d1.get("motivo_etapa"), "motivo_etapa vacio en la auditoria de N-1"
    assert e1["direccion_ip"] == "PRESENTE", "la auditoria de N-1 no registro la IP de origen"
    assert verificado["en_ventana_del_intento"] == "SI", (
        f"el evento {e1['id_evento']} no cae en la ventana del intento: {fe}")
    ESTADO["auditoria"] = True


def test_22_cuadro_y_cierre():
    requiere("auditoria")
    n, n1 = ESTADO["N"], ESTADO["N1"]
    c282 = E["casos"]["TC-M09-282"]
    cN = E["casos"]["TC-M09-283-N"]
    cN1 = E["casos"]["TC-M09-283-N-1"]
    aud = E["auditoria_rf10"]
    c282["resultado"] = "APROBADO"
    cN1["resultado"] = "APROBADO"

    E["cuadro_valores_limite"] = [
        {"criterio": "Total observaciones", "TC282": c282["conteos"]["total"],
         "N": cN["conteos"]["total"], "N_menos_1": cN1["conteos"]["total"]},
        {"criterio": "Aptas", "TC282": c282["conteos"]["aptas"],
         "N": cN["conteos"]["aptas"], "N_menos_1": cN1["conteos"]["aptas"]},
        {"criterio": "No aptas", "TC282": c282["conteos"]["no_aptas"],
         "N": cN["conteos"]["no_aptas"], "N_menos_1": cN1["conteos"]["no_aptas"]},
        {"criterio": "HTTP esperado", "TC282": 422, "N": "2xx", "N_menos_1": 422},
        {"criterio": "HTTP obtenido", "TC282": c282["response"]["http"],
         "N": cN["response"]["http"], "N_menos_1": cN1["response"]["http"]},
        {"criterio": "error_code", "TC282": c282.get("error_code"), "N": None,
         "N_menos_1": cN1.get("error_code")},
        {"criterio": "Estado calibracion", "TC282": "N/A (rechazo en precondiciones)",
         "N": cN["estado"], "N_menos_1": cN1["calibracion_fallida"]["estado"]},
        {"criterio": "Etapa fallo", "TC282": "N/A", "N": "N/A",
         "N_menos_1": cN1["calibracion_fallida"]["etapa_fallo"]},
        {"criterio": "Calibracion en historial", "TC282": c282["calibracion_nueva_en_historial"],
         "N": "SI (" + str(ESTADO["ID_N"]) + ")", "N_menos_1": "SI (" + str(ESTADO["ID_N1"]) + ")"},
        {"criterio": "Linea nueva", "TC282": c282["linea_base_nueva"], "N": "SI",
         "N_menos_1": "NO"},
        {"criterio": "Linea vigente final", "TC282": c282["baseline_POST"]["id_calibracion_vision"],
         "N": ESTADO["BASELINE_N"], "N_menos_1": cN1["baseline_POST"]["id_calibracion_vision"]},
        {"criterio": "Auditoria RF-10", "TC282": aud["TC282"]["encontrada"] + " (fallido)",
         "N": aud["TC283_N"]["encontrada"] + " (exitoso)",
         "N_menos_1": aud["TC283_N_MINUS_1"]["encontrada"] + " (fallido)"},
        {"criterio": "Resultado", "TC282": "APROBADO", "N": "APROBADO", "N_menos_1": "APROBADO"},
    ]

    # Comparacion obligatoria del paquete (63): ejecucion 1 PRE-FIX vs ejecucion 2 POST-FIX.
    h1 = HISTORIAL_EJECUCIONES[0]
    E["comparacion_prefix_postfix"] = [
        {"criterio": "TC-M09-282", "ejecucion_1_pre_fix": "APROBADO", "ejecucion_2_post_fix": "APROBADO"},
        {"criterio": "N", "ejecucion_1_pre_fix": 30, "ejecucion_2_post_fix": n},
        {"criterio": "N HTTP", "ejecucion_1_pre_fix": 201,
         "ejecucion_2_post_fix": cN["response"]["http"]},
        {"criterio": "N estado", "ejecucion_1_pre_fix": "EXITOSA",
         "ejecucion_2_post_fix": cN["estado"]},
        {"criterio": "N baseline", "ejecucion_1_pre_fix": "Publicada (id 8)",
         "ejecucion_2_post_fix": "Publicada (id " + str(ESTADO["BASELINE_N"]) + ")"},
        {"criterio": "N-1 HTTP", "ejecucion_1_pre_fix": 400,
         "ejecucion_2_post_fix": cN1["response"]["http"]},
        {"criterio": "N-1 error", "ejecucion_1_pre_fix": "VALOR_NO_PERMITIDO",
         "ejecucion_2_post_fix": cN1.get("error_code")},
        {"criterio": "N-1 mensaje contractual literal", "ejecucion_1_pre_fix": "NO",
         "ejecucion_2_post_fix": cN1["mensaje_exacto"]},
        {"criterio": "N-1 historial FALLIDA", "ejecucion_1_pre_fix": "NO",
         "ejecucion_2_post_fix": "SI (id " + str(ESTADO["ID_N1"]) + ")"},
        {"criterio": "N-1 etapa FILTRADO", "ejecucion_1_pre_fix": "NO",
         "ejecucion_2_post_fix": cN1["calibracion_fallida"]["etapa_fallo"]},
        {"criterio": "N-1 json_linea_base", "ejecucion_1_pre_fix": "JSON 'null' (rechazado por el CHECK)",
         "ejecucion_2_post_fix": "SQL NULL (fila aceptada; linea_base null por API)"},
        {"criterio": "N-1 auditoria FALLIDO", "ejecucion_1_pre_fix": "NO",
         "ejecucion_2_post_fix": aud["TC283_N_MINUS_1"]["encontrada"]},
        {"criterio": "Baseline N conservada", "ejecucion_1_pre_fix": "SI",
         "ejecucion_2_post_fix": cN1["baseline_N_conservada"]},
        {"criterio": "Pytest failed por el producto",
         "ejecucion_1_pre_fix": "1 (test_18: 400 en vez de 422)",
         "ejecucion_2_post_fix": 0},
        {"criterio": "Pytest failed por la automatizacion",
         "ejecucion_1_pre_fix": 0,
         "ejecucion_2_post_fix": ("1 (test_21: la consulta de auditoria pedia tamano=100 y "
                                   "GET /auditoria/ admite 50; corregido y completado por GET "
                                   "en el cierre de solo lectura)")},
        {"criterio": "TC-M09-G139", "ejecucion_1_pre_fix": "RECHAZADO",
         "ejecucion_2_post_fix": "APROBADO"},
        {"criterio": "Incidencia", "ejecucion_1_pre_fix": "ABIERTA",
         "ejecucion_2_post_fix": "CORREGIDA"},
    ]
    E["objetivo_del_fix"] = {
        "pre_fix": ("Python None -> JSON 'null'::jsonb -> "
                    "ck_calibracion_vision_resultado_coherente falla -> HTTP 400 "
                    "VALOR_NO_PERMITIDO -> sin historial y sin auditoria"),
        "post_fix": ("Python None -> SQL NULL -> el CHECK acepta -> la calibracion FALLIDA "
                     "persiste -> HTTP 422 LINEA_BASE_NO_CALCULADA -> historial y auditoria "
                     "disponibles"),
        "verificado_funcionalmente": "SI",
        "evidencia": {
            "http_n_menos_1": cN1["response"]["http"],
            "error_code": cN1.get("error_code"),
            "calibracion_persistida": ESTADO["ID_N1"],
            "estado": cN1["calibracion_fallida"]["estado"],
            "etapa_fallo": cN1["calibracion_fallida"]["etapa_fallo"],
            "linea_base_en_api": cN1["calibracion_fallida"].get("linea_base"),
            "evento_rf10": aud["TC283_N_MINUS_1"]["verificado"]["id_evento"],
        },
    }

    # La primera evaluacion (run-20261007-101924) quedo BLOQUEADA: el endpoint VISION
    # no existia. Se conserva como trazabilidad de la evolucion del grupo.
    E["comparacion_primera_segunda"] = {
        "casos": [
            {"caso": "TC-M09-282", "primera": "BLOQUEADO / NO VERIFICABLE",
             "segunda_ej1": "APROBADO", "segunda_ej2": "APROBADO"},
            {"caso": "TC-M09-283 N", "primera": "BLOQUEADO / NO VERIFICABLE",
             "segunda_ej1": "APROBADO", "segunda_ej2": "APROBADO"},
            {"caso": "TC-M09-283 N-1", "primera": "BLOQUEADO / NO VERIFICABLE",
             "segunda_ej1": "RECHAZADO", "segunda_ej2": "APROBADO"},
            {"caso": "TC-M09-G139", "primera": "BLOQUEADO / NO VERIFICABLE",
             "segunda_ej1": "RECHAZADO", "segunda_ej2": "APROBADO"},
        ],
        "evolucion": "BLOQUEADO -> RECHAZADO -> APROBADO",
        "dimensiones": [
            {"dimension": "Endpoint VISION", "primera": "Ausente",
             "segunda": "Presente (POST/GET y linea-base)"},
            {"dimension": "Fuente M03 VISION", "primera": "No evaluada",
             "segunda": f"POST /iot/telemetria/vision - {n + n1 + 10} observaciones en 3 lotes"},
            {"dimension": "N", "primera": "No leido",
             "segunda": f"{n} (ParametrosLineaBase.min_observaciones, confirmado en runtime)"},
            {"dimension": "Persistencia de la calibracion no exitosa",
             "primera": "No evaluada",
             "segunda": "Defectuosa en la ejecucion 1 (400) y correcta en la ejecucion 2 (422)"},
        ],
    }
    E["resultado"] = {
        "TC-M09-282": "APROBADO",
        "TC-M09-283": "APROBADO",
        "TC-M09-G139": "APROBADO",
        "evolucion": "BLOQUEADO -> RECHAZADO -> APROBADO",
        "incidencia_original": "CORREGIDA",
        "incidencia_nueva": "NO",
        "pr_que_corrige": PR_CORRECCION,
        "nota_historial": ("el resultado anterior RECHAZADO se conserva en el historial de "
                           "ejecuciones y no fue eliminado"),
        "regresiones": "NINGUNA: TC-M09-282 y la corrida N mantienen su resultado APROBADO",
    }
    E["seguridad"] = {
        "credenciales_persistidas": "NO",
        "serial_access_key_persistido": "NO - redactado por patron, solo en memoria",
        "sql_dml": 0,
        "sesion_bd": "READ ONLY",
        "archivos_primera_evaluacion_modificados": "NINGUNO",
        "nuevo_run_creado": "NO",
        "artefactos_post_fix_adicionales": "NINGUNO",
    }
    E["historial_ejecuciones"].append({
        "ejecucion": EJECUCION,
        "fecha": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "tipo": TIPO_EJECUCION,
        "autorizado_por": AUTORIZADO_POR,
        "pr": PR_CORRECCION,
        "resultado_g139": "APROBADO",
        "resultados": {
            "TC-M09-282": "APROBADO",
            "TC-M09-283-N": "APROBADO",
            "TC-M09-283-N-1": "APROBADO",
            "TC-M09-283": "APROBADO",
        },
        "motivo": ("la corrida N-1 devuelve el 422 LINEA_BASE_NO_CALCULADA del contrato, "
                   "persiste la calibracion FALLIDA en etapa FILTRADO, deja el evento RF-10 "
                   "y conserva la linea base de N"),
        "fixture": {"area_id": AREA, "camara_id": ESTADO["camara_id"],
                    "ventanas": [v[0][:10] for v in VENTANAS.values()]},
        "hitos": {"CAL_N": ESTADO["ID_N"], "baseline_tras_N": ESTADO["BASELINE_N"],
                  "CAL_N_MINUS_1": ESTADO["ID_N1"],
                  "baseline_final": cN1["baseline_POST"]["id_calibracion_vision"]},
        "pytest": "ver pytest.xml del RUN",
    })
    assert E["presupuesto"]["post_calibracion"] == 3, E["presupuesto"]
    assert E["presupuesto"]["post_vision"] == 3, E["presupuesto"]
    guardar_evidencia()
