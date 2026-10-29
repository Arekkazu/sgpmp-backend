"""TC-M09-284 y TC-M09-285 contra TEST — TC-M09-G140 (RF-24 v2.0, CU05 Flujo F).

  TC-M09-284 · Etapa 1 — las observaciones no aptas para IA quedan fuera del cálculo:
              dos áreas gemelas, el mismo conjunto K en las dos y 10 observaciones NO aptas
              con valores extremos añadidas solo a la segunda. La línea base debe ser idéntica.
  TC-M09-285 · Etapas 2 y 3 — recorte p5/p95 y refinamiento iterativo contra un oráculo
              independiente que entrega las DOS lecturas admitidas por la matriz
              (DESCARTE y WINSORIZACION), congeladas antes de ejecutar el producto.

MATRIZ ACTUALIZADA (autorización QA de reejecución parcial). La herramienta oficial de estos
dos casos es **Pytest + API**: la persistencia y la vigencia se demuestran con
`GET /configuracion/calibraciones-vision` y `GET .../linea-base`, y la ingesta con la respuesta
de `POST /iot/telemetria/vision`. La BD queda como **verificación complementaria cuando esté
disponible**: que `member_qa` no tenga SELECT sobre `modulo3.observaciones_vision`,
`modulo9.calibraciones_vision` ni `modulo9.lineas_base_vision` ya **no** bloquea nada; se
registra como `BD_COMPLEMENTARIA: NO DISPONIBLE POR PERMISOS QA` y se continúa. No se fabrica
evidencia de BD a partir de la API: cada dato dice de dónde sale.

Presupuesto cuando la compuerta abre: 3 POST de calibración y 3 lotes de telemetría, 0 reintentos.

Uso:
    pytest test_g140_test.py -v --confcutdir=. --junitxml=<RUN>/pytest-test.xml
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
import requests

BASE_DIR = Path(__file__).resolve().parent
EVAL_DIR = BASE_DIR.parent
CASE_DIR = EVAL_DIR.parent
GRUPO = "TC-M09-G140"
if BASE_DIR.name != "automation" or EVAL_DIR.name != "EvaluacionV2" or CASE_DIR.name != GRUPO:
    raise RuntimeError(f"ABORTADO: ruta no autorizada para {GRUPO}: {BASE_DIR}")
REPO_DIR = CASE_DIR.parents[4]
sys.path.insert(0, str(BASE_DIR))

import oracle_g140 as ORACULO  # noqa: E402

RUN_ID = os.environ.get("G140_RUN_ID") or datetime.datetime.now().strftime("run-%Y%m%d-%H%M%S")
RUN_DIR = EVAL_DIR / "RESULTADOS" / RUN_ID
RUN_DIR.mkdir(parents=True, exist_ok=True)

# ── Ejecuciones dentro del MISMO RUN logico (§1 a §6) ───────────────────────
# El RUN no se duplica cuando Desarrollo corrige: se incrementa el numero de
# ejecucion del grupo y se reejecuta el grupo completo, sobreescribiendo los
# artefactos tecnicos. La historia vive en el informe y en `historial_ejecuciones`.
EJECUCION_GRUPO = 3
TIPO_EJECUCION = "REEJECUCION_COMPLETA_POST_FIX"
AUTORIZADO_POR = "LIDER_DESARROLLO"
PR_CORRECCION = 550
FIX_ESPERADO = "JSONB(none_as_null=True)"
MODELO_FIX = "src/configuration/infrastructure/models/calibracion_vision_model.py"
# Sello propio de esta ejecucion: el RUN_ID es el mismo, asi que los nombres y
# seriales del fixture no pueden derivarse de el sin chocar con la ejecucion 2.
SELLO = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d-%H%M%S")

HISTORIAL_EJECUCIONES = [
    {
        "ejecucion": 1,
        "run_id": "run-20261010-141449",
        "fecha": "2026-10-10T14:14:49-05:00",
        "tipo": "EVALUACION_INICIAL",
        "resultados": {"TC-M09-284": "BLOQUEADO", "TC-M09-285": "BLOQUEADO",
                       "TC-M09-286": "RECHAZADO", "TC-M09-G140": "RECHAZADO"},
        "motivo": ("284 y 285 bloqueados por precondicion de acceso QA/DBA (sin SELECT sobre "
                   "las tablas VISION, exigido entonces por la matriz); 286 rechazado porque "
                   "el POST objetivo devolvio 400 VALOR_NO_PERMITIDO en vez del 422: la "
                   "calibracion NO_CONVERGIDA/REFINAMIENTO no se pudo persistir (JSON 'null' "
                   "en vez de SQL NULL). La linea base previa se conservo."),
        "nota": "RUN historico; no se modifica ni se reutiliza como resultado vigente",
    },
    {
        "ejecucion": 2,
        "run_id": "run-20261010-150013",
        "fecha": "2026-10-10T15:00:13-05:00",
        "tipo": "REEJECUCION_PARCIAL",
        "resultados": {"TC-M09-284": "APROBADO", "TC-M09-285": "APROBADO",
                       "TC-M09-286": "NO REEJECUTADO / RECHAZADO heredado",
                       "TC-M09-G140": "RECHAZADO"},
        "motivo": ("QA autorizo reejecutar solo 284 y 285 con la BD como complementaria; "
                   "286 conservo su RECHAZADO y el grupo siguio RECHAZADO"),
        "pytest_test": {"collected": 16, "passed": 16, "failed": 0, "skipped": 0, "errors": 0},
    },
]

BASE_URL = "https://api.inmero.co/back-sigab-test"
if not BASE_URL.endswith("/back-sigab-test"):
    raise RuntimeError("ABORTADO: el ambiente decisorio de TC-284/285 es TEST")

ING = ("ingeniero@pecuaria.co", "Test1234!")
ADM = ("administador.dev@gmail.com", "Test1234!")
ADM_ALT = ("admin.dev@gmail.com", "Test1234!")
DB = {"host": "158.69.200.27", "port": "5448", "dbname": "sgpmp_test",
      "user": "member_qa", "password": "qaSGP2026"}

TABLAS_ORACULO = ("modulo3.observaciones_vision", "modulo9.calibraciones_vision",
                  "modulo9.lineas_base_vision")
TIPO_CAMARA_VISION = 5
#: Matriz actualizada: la BD no condiciona AUTORIZAR_TEST. Se conserva la variable solo para
#: poder volver a exigir el oráculo de BD si la matriz cambiara otra vez.
BD_OBLIGATORIA = os.environ.get("G140_EXIGIR_BD", "").strip().lower() in ("1", "si", "sí", "true")

# Ventanas nuevas, disjuntas y en el pasado (§6). Las cámaras también son nuevas, así que
# ninguna observación histórica puede caer dentro: se exige `duplicadas = 0` en los tres lotes.
# Ejecucion 3: ventanas NUEVAS (§29). Las de la ejecucion 2 (01, 03 y 05 de junio)
# no se reutilizan, de modo que ninguna observacion anterior pueda contaminar el conteo.
VENTANAS = {
    "WINDOW_284_K": ("2026-06-11T00:00:00Z", "2026-06-11T06:00:00Z"),
    "WINDOW_284_KM": ("2026-06-13T00:00:00Z", "2026-06-13T06:00:00Z"),
    "WINDOW_285": ("2026-06-15T00:00:00Z", "2026-06-15T06:00:00Z"),
}
VENTANAS_EJECUCIONES_ANTERIORES = {
    "ejecucion_2_WINDOW_284_K": ("2026-06-01T00:00:00Z", "2026-06-01T06:00:00Z"),
    "ejecucion_2_WINDOW_284_KM": ("2026-06-03T00:00:00Z", "2026-06-03T06:00:00Z"),
    "ejecucion_2_WINDOW_285": ("2026-06-05T00:00:00Z", "2026-06-05T06:00:00Z"),
}
PRESUPUESTO = {"post_calibracion": 3, "post_vision": 3}
#: Paginacion de `GET /auditoria/` que usaria el arnes. El PRECHECK la compara contra el
#: maximo que declara OpenAPI antes de cualquier POST (§64).
AUDITORIA_TAMANO = 50
#: Campos del item de auditoria que el arnes lee. NO existe `exitoso`: el resultado viaja
#: en `resultado` y la IP en `direccion_ip`.
CAMPOS_AUDITORIA = ("id_evento", "tipo_evento", "fecha_evento", "modulo", "resultado",
                    "detalle", "id_usuario", "nombre_usuario", "direccion_ip", "user_agent",
                    "integridad_ok")
_RE_SERIAL = re.compile(r"QA-M09-G1\d{2}-[A-Z]+-\d{8}-\d{6}")

E: dict = {
    "run_id": RUN_ID, "grupo": GRUPO, "ambiente": "TEST", "base_url": BASE_URL,
    "herramienta": "Pytest + requests (HTTP real) + BD TEST por SELECT",
    "newman": "NO APLICA",
    "generado": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "execution_number_group": EJECUCION_GRUPO,
    "execution_type": TIPO_EJECUCION,
    "nuevo_run_creado": "NO",
    "grupo_completo_reejecutado": "SÍ",
    "autorizado_por": AUTORIZADO_POR,
    "correccion": {"pr": PR_CORRECCION, "fix": FIX_ESPERADO, "archivo": MODELO_FIX},
    "historial_ejecuciones": [dict(h) for h in HISTORIAL_EJECUCIONES],
    "presupuesto": {"post_calibracion": 0, "post_vision": 0, "reintentos": 0},
    "casos": {}, "limitaciones": [],
}
ESTADO: dict = {"hechos": set()}


def sanear(d):
    if isinstance(d, dict):
        return {k: ("[REDACTED]" if str(k).lower() in (
            "authorization", "token", "access_token", "refresh_token", "contrasena", "password",
            "access_key", "serial", "cookie", "dsn") else sanear(v)) for k, v in d.items()}
    if isinstance(d, list):
        return [sanear(x) for x in d]
    if isinstance(d, str):
        s = _RE_SERIAL.sub("[SERIAL REDACTED]", d)
        s = re.sub(r"Bearer\s+[A-Za-z0-9._\-]+", "Bearer [REDACTED]", s)
        return s.replace(ING[1], "[REDACTED]").replace(DB["password"], "[REDACTED]")
    return d


def guardar():
    (RUN_DIR / "evidencia-test.json").write_text(
        json.dumps(sanear(E), indent=2, ensure_ascii=False, default=str), encoding="utf-8")


def select(consultas: list[tuple[str, str]]) -> dict:
    """SELECT en sesión READ ONLY, en un intérprete aislado; la contraseña va por entorno."""
    for _, sql in consultas:
        if re.search(r"\b(insert|update|delete|alter|drop|truncate|create|grant|revoke)\b", sql, re.I):
            raise RuntimeError("ABORTADO: la consulta no es de solo lectura")
    programa = (
        "import json,os,psycopg2,psycopg2.extras\n"
        "c=psycopg2.connect('host=%s port=%s dbname=%s user=%s password=%s connect_timeout=25'%("
        "os.environ['H'],os.environ['P'],os.environ['D'],os.environ['U'],os.environ['W']))\n"
        "c.autocommit=True;c.set_session(readonly=True)\n"
        "cu=c.cursor(cursor_factory=psycopg2.extras.RealDictCursor);out={}\n"
        "for t,s in json.loads(os.environ['Q']):\n"
        "    try:\n"
        "        cu.execute(s);out[t]=[dict(x) for x in cu.fetchall()]\n"
        "    except Exception as e:\n"
        "        out[t]={'error':str(e).splitlines()[0]}\n"
        "print(json.dumps(out,default=str,ensure_ascii=False))\n"
    )
    env = dict(os.environ, H=DB["host"], P=DB["port"], D=DB["dbname"], U=DB["user"],
               W=DB["password"], Q=json.dumps(consultas))
    p = subprocess.run([sys.executable, "-I", "-c", programa], capture_output=True, text=True,
                       env=env, timeout=240)
    return json.loads(p.stdout) if p.returncode == 0 else {"_error": (p.stderr or "")[-200:]}


class Api:
    def __init__(self) -> None:
        self.s = requests.Session()
        self.tokens: dict[str, str] = {}

    def login(self, correo: str, clave: str, etiqueta: str) -> str:
        r = self.s.post(f"{BASE_URL}/sesiones/",
                        json={"correo_electronico": correo, "contrasena": clave}, timeout=90)
        assert r.status_code == 200, f"login {etiqueta}: HTTP {r.status_code} {sanear(r.text)[:300]}"
        self.tokens[etiqueta] = r.json()["token"]
        return self.tokens[etiqueta]

    def _h(self, etiqueta: str) -> dict:
        return {"Authorization": f"Bearer {self.tokens[etiqueta]}", "Accept": "application/json"}

    def get(self, etiqueta: str, path: str, timeout: int = 120):
        r = self.s.get(f"{BASE_URL}{path}", headers=self._h(etiqueta), timeout=timeout)
        return r.status_code, _cuerpo(r)

    def post(self, etiqueta: str, path: str, cuerpo: dict, timeout: int = 240):
        r = self.s.post(f"{BASE_URL}{path}", headers=self._h(etiqueta), json=cuerpo, timeout=timeout)
        return r.status_code, _cuerpo(r)

    def patch(self, etiqueta: str, path: str, timeout: int = 120):
        r = self.s.patch(f"{BASE_URL}{path}", headers=self._h(etiqueta), timeout=timeout)
        return r.status_code, _cuerpo(r)

    def post_calibracion(self, cuerpo: dict, marca: str):
        if marca in ESTADO["hechos"]:
            raise RuntimeError(f"ABORTADO: reintento prohibido del POST funcional {marca}")
        if E["presupuesto"]["post_calibracion"] >= PRESUPUESTO["post_calibracion"]:
            raise RuntimeError("ABORTADO: presupuesto de POST /calibraciones-vision agotado")
        ESTADO["hechos"].add(marca)
        E["presupuesto"]["post_calibracion"] += 1
        return self.post("ingeniero", "/configuracion/calibraciones-vision", cuerpo)

    def post_vision(self, cuerpo: dict, marca: str):
        if marca in ESTADO["hechos"]:
            raise RuntimeError(f"ABORTADO: reenvío prohibido del lote {marca}")
        if E["presupuesto"]["post_vision"] >= PRESUPUESTO["post_vision"]:
            raise RuntimeError("ABORTADO: presupuesto de POST /iot/telemetria/vision agotado")
        ESTADO["hechos"].add(marca)
        E["presupuesto"]["post_vision"] += 1
        r = self.s.post(f"{BASE_URL}/iot/telemetria/vision", json=cuerpo, timeout=400)
        return r.status_code, _cuerpo(r)


def _cuerpo(r: requests.Response):
    try:
        return r.json()
    except ValueError:
        return {"_texto": r.text[:500]}


API = Api()


def requiere(*claves: str):
    for c in claves:
        if c not in ESTADO:
            pytest.skip(f"falta la precondición {c}")


def autorizado():
    if not ESTADO.get("autorizar_test"):
        pytest.skip(ESTADO.get("motivo_compuerta", "compuerta del §12 cerrada"))


def instantes(inicio: str, cantidad: int, paso_min: int) -> list[str]:
    base = datetime.datetime.fromisoformat(inicio.replace("Z", "+00:00"))
    return [(base + datetime.timedelta(minutes=paso_min * i)).strftime("%Y-%m-%dT%H:%M:%SZ")
            for i in range(cantidad)]


def obs(ts: str, densidad: float, tasa: float, fps: int, apta: bool) -> dict:
    if apta:
        return {"timestamp_captura": ts, "cobertura_ventana": "1.0000", "n_tracks": 20,
                "n_tracks_perdidos": 0, "fps_efectivo": f"{fps}.00",
                "estado_calibracion": "CALIBRADA",
                "vector": {"densidad_actividad": densidad, "tasa_movimiento": tasa}}
    return {"timestamp_captura": ts, "cobertura_ventana": "0.1000", "n_tracks": 0,
            "n_tracks_perdidos": 10, "fps_efectivo": "0.00",
            "estado_calibracion": "SIN_DETECCION",
            "vector": {"densidad_actividad": densidad, "tasa_movimiento": tasa}}


@pytest.fixture(scope="session", autouse=True)
def red_de_seguridad():
    yield
    restauracion = {"camaras_desactivadas": [], "pendientes": [], "nota": ""}
    for clave in ("cam_k", "cam_km"):
        cam = ESTADO.get(clave)
        if cam and "ingeniero" in API.tokens:
            try:
                c, _ = API.patch("ingeniero", f"/configuracion/dispositivos-iot/{cam}/desactivar")
                restauracion["camaras_desactivadas"].append({"id": cam, "http": c})
                if c not in (200, 204):
                    restauracion["pendientes"].append(f"cámara {cam} no desactivada (HTTP {c})")
            except Exception as exc:  # pragma: no cover - red
                restauracion["pendientes"].append(f"error al desactivar {cam}: {exc}")
    if ESTADO.get("a1") or ESTADO.get("a1p"):
        restauracion["nota"] = (
            "RF-20/RF-19 no publican eliminación de áreas ni de fincas: las áreas "
            f"{ESTADO.get('a1')} y {ESTADO.get('a1p')} quedan como dato QA trazable. "
            "No se inventó limpieza por SQL (§65).")
    else:
        restauracion["nota"] = ("no se creó fixture en TEST: la compuerta del §12 no abrió, "
                                "así que no hay nada que restaurar.")
    restauracion["calibraciones_borradas"] = 0
    restauracion["lineas_base_borradas"] = 0
    E["restauracion"] = restauracion
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
    previo.update({"run_id": RUN_ID, "grupo": GRUPO, "newman": "NO APLICA",
                   "execution_number_group": EJECUCION_GRUPO,
                   "execution_type": TIPO_EJECUCION,
                   "automatizacion": entradas,
                   "nota": "los scripts no se copian dentro del RUN (§84); aquí va su SHA-256"})
    previo["artefactos_resultados"] = [
        {"archivo": p.name, "bytes": p.stat().st_size,
         "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
        for p in sorted(RUN_DIR.rglob("*"))
        if p.is_file() and p.name != "automation_manifest.json"]
    destino.write_text(json.dumps(previo, indent=2, ensure_ascii=False), encoding="utf-8")


# ══════════════════════════════════════════════════════════════════════════════
# PREFLIGHT DE SOLO LECTURA
# ══════════════════════════════════════════════════════════════════════════════

def test_01_rama_y_baseline():
    rama = subprocess.run(["git", "branch", "--show-current"], cwd=str(REPO_DIR),
                          capture_output=True, text=True).stdout.strip()
    estado = subprocess.run(["git", "status", "--short"], cwd=str(REPO_DIR),
                            capture_output=True, text=True).stdout.strip()
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(REPO_DIR),
                            capture_output=True, text=True).stdout.strip()
    E["git"] = {"rama": rama, "commit": commit, "status_short": estado.splitlines()}
    assert rama == "qa/juan-esteban-segunda-evaluacion-rf24-v2.0", f"rama inesperada: {rama}"
    baseline = CASE_DIR / "RESULTADOS"
    runs = sorted(p.name for p in baseline.iterdir() if p.is_dir()) if baseline.is_dir() else []
    E["baseline_primera_evaluacion"] = {
        "informe": "TC-M09-G140_resultado.md",
        "runs": runs,
        "solo_lectura": True,
    }
    assert (baseline / "TC-M09-G140_resultado.md").is_file(), "no se encuentra el informe baseline"

    # §16 — el fix del PR #550 se comprueba por LECTURA de origin/test. Sin checkout,
    # sin switch, sin merge: `git show`. Que este en Git no prueba el despliegue; para
    # TC-284/285 el veredicto lo da TEST y para TC-286 el codigo que corre el laboratorio.
    def _git(*args):
        return subprocess.run(["git", *args], cwd=str(REPO_DIR), capture_output=True,
                              text=True, encoding="utf-8", errors="replace").stdout
    sha_origin = _git("rev-parse", "origin/test").strip()
    linea_origin = next((l.strip() for l in _git("show", f"origin/test:{MODELO_FIX}").splitlines()
                         if "json_linea_base" in l), None)
    linea_arbol = next((l.strip() for l in (REPO_DIR / MODELO_FIX).read_text(
        encoding="utf-8").splitlines() if "json_linea_base" in l), None)
    E["correccion"].update({
        "origin_test_sha": sha_origin,
        "linea_en_origin_test": linea_origin,
        "fix_presente_en_origin_test": "SÍ" if FIX_ESPERADO in (linea_origin or "") else "NO",
        "linea_en_working_tree_qa": linea_arbol,
        "fix_presente_en_working_tree_qa": "SÍ" if FIX_ESPERADO in (linea_arbol or "") else "NO",
        "metodo": f"git show origin/test:{MODELO_FIX} (lectura; sin checkout/switch/merge)",
        "consecuencia_para_el_laboratorio": (
            "si el working tree de la rama QA no trae el fix, el laboratorio de TC-286 NO "
            "puede montarse sobre el working tree: se construye desde un snapshot de solo "
            "lectura de origin/test fuera del arbol de trabajo (§44/§45)"),
    })
    assert sha_origin, "no se pudo leer origin/test"
    assert FIX_ESPERADO in (linea_origin or ""), (
        f"el PR #{PR_CORRECCION} no esta en origin/test: {linea_origin!r}")
    ESTADO["rama"] = True


def test_02_openapi_vision():
    requiere("rama")
    r = requests.get(f"{BASE_URL}/openapi.json", timeout=150)
    assert r.status_code == 200, f"openapi.json HTTP {r.status_code}"
    paths = r.json().get("paths", {})
    requeridos = [("/configuracion/calibraciones-vision", "post"),
                  ("/configuracion/calibraciones-vision", "get"),
                  ("/configuracion/calibraciones-vision/linea-base", "get"),
                  ("/iot/telemetria/vision", "post")]
    contrato = {f"{m.upper()} {p}": ("PRESENTE" if m in paths.get(p, {}) else "AUSENTE")
                for p, m in requeridos}
    E["openapi"] = contrato
    ausentes = [k for k, v in contrato.items() if v != "PRESENTE"]
    assert not ausentes, f"endpoints VISION ausentes en TEST: {ausentes}"
    ESTADO["openapi"] = True


def test_03_precheck_bd_complementaria():
    """Verificación complementaria: se registra lo que QA puede leer, sin condicionar nada."""
    requiere("openapi")
    res = select([
        ("rol", "SELECT current_user"),
        ("privilegios", """
            SELECT 'modulo3.observaciones_vision' AS tabla,
                   has_table_privilege('member_qa','modulo3.observaciones_vision','SELECT') AS puede_select
            UNION ALL SELECT 'modulo9.calibraciones_vision',
                   has_table_privilege('member_qa','modulo9.calibraciones_vision','SELECT')
            UNION ALL SELECT 'modulo9.lineas_base_vision',
                   has_table_privilege('member_qa','modulo9.lineas_base_vision','SELECT')"""),
        ("grants_visibles", """
            SELECT table_schema, table_name, grantee, privilege_type
            FROM information_schema.role_table_grants
            WHERE (table_schema,table_name) IN (('modulo3','observaciones_vision'),
              ('modulo9','calibraciones_vision'),('modulo9','lineas_base_vision'))
            ORDER BY 1,2,3,4"""),
        ("roles_heredados", """
            SELECT r.rolname AS rol FROM pg_auth_members m JOIN pg_roles r ON r.oid=m.roleid
            JOIN pg_roles u ON u.oid=m.member WHERE u.rolname='member_qa'"""),
    ])
    privs = {f["tabla"]: f["puede_select"] for f in res.get("privilegios", [])
             if isinstance(f, dict)}
    etiqueta = {"modulo3.observaciones_vision": "OBSERVACIONES_VISION_SELECT",
                "modulo9.calibraciones_vision": "CALIBRACIONES_VISION_SELECT",
                "modulo9.lineas_base_vision": "LINEAS_BASE_VISION_SELECT"}
    veredicto = {etiqueta[t]: ("PASS" if privs.get(t) else "FAIL") for t in TABLAS_ORACULO}
    disponible = all(v == "PASS" for v in veredicto.values()) and "_error" not in res
    E["acceso_bd"] = {
        "rol_en_la_matriz": "VERIFICACIÓN COMPLEMENTARIA CUANDO ESTÉ DISPONIBLE",
        "host": DB["host"], "puerto": DB["port"], "base": DB["dbname"], "usuario": DB["user"],
        "sesion": "READ ONLY — solo SELECT, 0 DML",
        "consulta": "SELECT has_table_privilege('member_qa', <tabla>, 'SELECT')",
        "resultado": veredicto,
        "privilegios_crudos": privs,
        "grants_visibles": res.get("grants_visibles"),
        "roles_heredados": res.get("roles_heredados"),
        "error_de_conexion": res.get("_error"),
        "BD_COMPLEMENTARIA": "DISPONIBLE" if disponible else "NO DISPONIBLE POR PERMISOS QA",
    }
    ESTADO["bd_ok"] = disponible
    ESTADO["precheck_bd"] = True


def test_04_actores():
    requiere("precheck_bd")
    API.login(*ING, "ingeniero")
    try:
        API.login(*ADM, "admin")
        usado = ADM[0]
    except AssertionError:
        API.login(*ADM_ALT, "admin")
        usado = ADM_ALT[0]
    c, _ = API.get("ingeniero", "/sesiones/me/permisos")
    assert c == 200, f"permisos del Ingeniero HTTP {c}"
    E["actores"] = {"ingeniero": {"correo": ING[0], "login": "PASS"},
                    "administrador": {"correo": usado, "login": "PASS",
                                      "uso": "discovery y diagnóstico"}}
    ESTADO["actores"] = True


def test_05_parametros():
    requiere("actores")
    fuente = REPO_DIR / "src/configuration/domain/entities/linea_base_vision.py"
    texto = fuente.read_text(encoding="utf-8")
    def leer(nombre: str, tipo):
        m = re.search(rf"{nombre}:\s*(?:int|float)\s*=\s*([0-9.]+)", texto)
        assert m, f"no se pudo leer {nombre}"
        return tipo(m.group(1))
    par = {"min_observaciones": leer("min_observaciones", int),
           "cobertura_minima": leer("cobertura_minima", float),
           "tracks_minimos": leer("tracks_minimos", int),
           "min_datos_componente": leer("min_datos_componente", int),
           "epsilon": leer("epsilon", float),
           "max_iteraciones": leer("max_iteraciones", int)}
    uso = (REPO_DIR / "src/configuration/application/use_cases/sensores/calibrar_vision_use_case.py"
           ).read_text(encoding="utf-8")
    assert "parametros: ParametrosLineaBase = ParametrosLineaBase()" in uso, \
        "el caso de uso ya no toma los parámetros por defecto; reconfirmar"
    # §22 — el build desplegado en TEST es origin/test, asi que los umbrales se leen
    # tambien de alli y se comparan: si difirieran, el oraculo estaria congelado con
    # parametros que no son los del producto bajo prueba.
    texto_origin = subprocess.run(
        ["git", "show", "origin/test:src/configuration/domain/entities/linea_base_vision.py"],
        cwd=str(REPO_DIR), capture_output=True, text=True, encoding="utf-8",
        errors="replace").stdout

    def leer_origin(nombre: str, tipo):
        m = re.search(rf"{nombre}:\s*(?:int|float)\s*=\s*([0-9.]+)", texto_origin)
        return tipo(m.group(1)) if m else None

    par_origin = {k: leer_origin(k, type(v)) for k, v in par.items()}
    ESTADO["par"] = par
    E["parametros"] = {
        **par,
        "fuente": ("ParametrosLineaBase — src/configuration/domain/entities/linea_base_vision.py; "
                   "el caso de uso los toma por defecto"),
        "commit": E["git"]["commit"],
        "en_origin_test": par_origin,
        "coinciden_arbol_y_origin_test": "SÍ" if par_origin == par else "NO",
        "max_iteraciones_TEST": par["max_iteraciones"],
        "max_iteraciones_LOCAL_TC286": 1,
        "nota": ("no se modifica max_iteraciones en TEST (§50); el 1 solo existe en el "
                 "laboratorio local de TC-M09-286"),
    }
    assert par_origin == par, (
        f"los umbrales difieren entre el arbol QA y origin/test: {par} vs {par_origin}")
    ESTADO["parametros"] = True


def test_06_oraculos_congelados():
    """§17 y §37: las dos lecturas quedan calculadas y registradas ANTES de ejecutar el producto."""
    requiere("parametros")
    p = ESTADO["par"]
    par = ORACULO.Parametros(**p)
    k, m = ORACULO.dataset_k(), ORACULO.dataset_m()
    d285 = ORACULO.dataset_285()
    congelados = {
        "independencia": ("oracle_g140.py no importa calcular_linea_base, recortar_p5_p95, "
                          "mediana, percentil ni ningún módulo src.configuration/src.telemetry"),
        "parametros": p,
        "TC-M09-284": {
            "vectores_K": [{"i": i, "densidad_actividad": d, "tasa_movimiento": t}
                           for i, (d, t) in ((i, ORACULO.vector_k(i)) for i in range(40))],
            "M": {"n": len(m), "densidad_actividad": 1000.0, "tasa_movimiento": 500.0,
                  "aproximadamente_100x_la_mediana_de_K": True},
            "K": ORACULO.ambas_lecturas(k, par),
            "K+M": ORACULO.ambas_lecturas(k + m, par),
        },
        "TC-M09-285": {
            "densidad_actividad": ORACULO.DENSIDAD_285,
            "tasa_movimiento": [d * 10 for d in ORACULO.DENSIDAD_285],
            **ORACULO.ambas_lecturas(d285, par),
        },
    }
    E["oraculos_congelados"] = congelados
    ESTADO["oraculos"] = congelados
    # Coherencia interna del oráculo: M no debe mover nada en ninguna de las dos lecturas.
    for modo in ("ORACLE_DESCARTE", "ORACLE_WINSORIZACION"):
        assert ORACULO.coincide(congelados["TC-M09-284"]["K"][modo]["valores"],
                                congelados["TC-M09-284"]["K+M"][modo]["valores"]), modo
    # El dataset de TC-285 debe discriminar entre las dos lecturas, o no probaría nada.
    assert not ORACULO.coincide(congelados["TC-M09-285"]["ORACLE_DESCARTE"]["valores"],
                                congelados["TC-M09-285"]["ORACLE_WINSORIZACION"]["valores"]), \
        "el dataset de TC-285 no distingue DESCARTE de WINSORIZACION"
    ESTADO["oraculos_ok"] = True


def test_06b_precheck_de_automatizacion():
    """PRECHECK DE AUTOMATIZACION (§9 a §13): el arnes se valida ANTES de escribir nada.

    Nace de un fallo real de la reejecucion de G139: la consulta de auditoria pedia
    `tamano=100` cuando el contrato declara 50 como maximo, y eso se descubrio despues
    de los POST, cuando ya no se podian repetir. Aqui se comprueba contra OpenAPI que
    cada parametro que usa el arnes esta dentro del contrato, que los campos que lee
    existen en el esquema de respuesta, que el oraculo acierta en casos conocidos y que
    las ventanas son validas. Si algo de esto falla, no se autorizan los POST (§13).
    """
    requiere("oraculos_ok")
    informe: dict = {}

    # 1 · Contrato OpenAPI de todos los endpoints que usa el arnes ───────────
    r = requests.get(f"{BASE_URL}/openapi.json", timeout=150)
    assert r.status_code == 200, f"openapi.json HTTP {r.status_code}"
    doc = r.json()
    rutas, esquemas = doc.get("paths", {}), doc.get("components", {}).get("schemas", {})

    usados = [
        ("/configuracion/calibraciones-vision", "post"),
        ("/configuracion/calibraciones-vision", "get"),
        ("/configuracion/calibraciones-vision/linea-base", "get"),
        ("/iot/telemetria/vision", "post"),
        ("/configuracion/infraestructuras", "post"),
        ("/configuracion/infraestructuras/{id_infraestructura}", "get"),
        ("/configuracion/dispositivos-iot", "post"),
        ("/configuracion/dispositivos-iot/{id_dispositivo_iot}/desactivar", "patch"),
        ("/configuracion/fincas", "get"),
        ("/configuracion/especies", "get"),
        ("/configuracion/tipos-area", "get"),
        ("/sesiones/", "post"),
        ("/sesiones/me/permisos", "get"),
        ("/auditoria/", "get"),
        ("/auditoria/catalogo/tipos-evento", "get"),
    ]
    presencia, ausentes = {}, []
    for ruta, metodo in usados:
        hay = metodo in rutas.get(ruta, {})
        presencia[f"{metodo.upper()} {ruta}"] = "PRESENTE" if hay else "AUSENTE"
        if not hay:
            ausentes.append(f"{metodo.upper()} {ruta}")
    informe["endpoints_usados_por_el_arnes"] = presencia
    assert not ausentes, f"el arnes usa endpoints que TEST no publica: {ausentes}"

    # 2 · Cuerpos requeridos: lo que el arnes envia debe cubrir los required ─
    def requeridos(ruta, metodo):
        ref = (rutas[ruta][metodo].get("requestBody", {}).get("content", {})
               .get("application/json", {}).get("schema", {}).get("$ref"))
        return set(esquemas.get(ref.split("/")[-1], {}).get("required", []) or []) if ref else set()

    cuerpos = {
        "POST /configuracion/calibraciones-vision": {
            "requeridos": sorted(requeridos("/configuracion/calibraciones-vision", "post")),
            "enviados": sorted(["modo_calibracion", "area_id", "ventana_observacion",
                                "observaciones", "fecha_calibracion"]),
        },
        "POST /iot/telemetria/vision": {
            "requeridos": sorted(requeridos("/iot/telemetria/vision", "post")),
            "enviados": sorted(["device_id", "access_key", "area_id", "observaciones"]),
        },
    }
    for etiqueta, d in cuerpos.items():
        faltan = set(d["requeridos"]) - set(d["enviados"])
        d["cubre_los_requeridos"] = "SÍ" if not faltan else f"NO: faltan {sorted(faltan)}"
        assert not faltan, f"{etiqueta}: el arnes no envia {sorted(faltan)}"
    informe["cuerpos_requeridos"] = cuerpos

    # 3 · Query params obligatorios y limites min/max (§10) ──────────────────
    def params(ruta, metodo):
        return {q["name"]: q for q in rutas[ruta][metodo].get("parameters", [])}

    obligatorios = {}
    for ruta in ("/configuracion/calibraciones-vision",
                 "/configuracion/calibraciones-vision/linea-base"):
        req = sorted(n for n, q in params(ruta, "get").items() if q.get("required"))
        obligatorios[f"GET {ruta}"] = {"requeridos": req, "enviados_por_el_arnes": ["area_id"]}
        assert set(req) <= {"area_id"}, (
            f"GET {ruta} exige parametros que el arnes no envia: {req}")
    informe["query_params_obligatorios"] = obligatorios

    # El limite de paginacion de auditoria: el defecto exacto que rompio G139.
    aud = params("/auditoria/", "get")
    tam = aud.get("tamano", {}).get("schema", {})
    pag = aud.get("pagina", {}).get("schema", {})
    limites = {
        "tamano": {"minimum": tam.get("minimum"), "maximum": tam.get("maximum"),
                   "default": tam.get("default")},
        "pagina": {"minimum": pag.get("minimum"), "default": pag.get("default")},
        "tamano_que_usaria_el_arnes": AUDITORIA_TAMANO,
    }
    informe["limites_de_paginacion_auditoria"] = limites
    assert isinstance(tam.get("maximum"), int), "OpenAPI no declara el maximo de `tamano`"
    assert AUDITORIA_TAMANO <= tam["maximum"], (
        f"el arnes pediria tamano={AUDITORIA_TAMANO} y el contrato admite "
        f"{tam['maximum']} como maximo (este es el defecto que rompio G139)")
    assert AUDITORIA_TAMANO >= tam.get("minimum", 1), limites

    # 4 · Campos del esquema de respuesta que el arnes lee (§11) ─────────────
    item = esquemas.get("AuditoriaItemResponse", {}).get("properties", {})
    informe["esquema_auditoria"] = {
        "campos_declarados": sorted(item),
        "campos_que_lee_el_arnes": sorted(CAMPOS_AUDITORIA),
        "campo_exitoso_existe": "NO" if "exitoso" not in item else "SÍ",
    }
    assert item, "no se encontro AuditoriaItemResponse en el esquema"
    faltan = sorted(set(CAMPOS_AUDITORIA) - set(item))
    assert not faltan, f"el arnes leeria campos que el esquema no declara: {faltan}"
    assert "exitoso" not in item, (
        "el esquema volvio a declarar `exitoso`; revisar el arnes antes de usarlo")
    assert "resultado" in item, "el esquema de auditoria no declara `resultado`"

    # 5 · Autotest del oraculo (§24): casos conocidos, calculados a mano ─────
    muestra = [1.0, 2.0, 3.0, 4.0]
    casos = {
        "percentil_p50_par": (ORACULO.percentil(muestra, 50), 2.5),
        "percentil_p0": (ORACULO.percentil(muestra, 0), 1.0),
        "percentil_p100": (ORACULO.percentil(muestra, 100), 4.0),
        "percentil_interpolado": (ORACULO.percentil([10.0, 20.0], 25), 12.5),
        "mediana_impar": (ORACULO.mediana([5.0, 1.0, 3.0]), 3.0),
        "mediana_par": (ORACULO.mediana([1.0, 2.0, 3.0, 4.0]), 2.5),
        "cambio_relativo": (ORACULO.cambio_relativo(4.0, 4.5), 0.5 / 4.5),
        "cambio_relativo_desde_cero": (ORACULO.cambio_relativo(1.0, 0.0), 1.0),
    }
    fallos = {k: v for k, v in casos.items() if abs(v[0] - v[1]) > 1e-9}
    # Recorte: con [1..10], p5 = 1.45 y p95 = 9.55, asi que 1 y 10 quedan fuera.
    datos10 = [float(i) for i in range(1, 11)]
    p5, p95 = ORACULO.limites_p5_p95(datos10)
    descarte = ORACULO.aplicar_descarte(datos10)
    winsor = ORACULO.aplicar_winsorizacion(datos10)
    informe["oracle_self_test"] = {
        "casos_numericos": {k: {"obtenido": v[0], "esperado": v[1]} for k, v in casos.items()},
        "p5_p95_de_1_a_10": [p5, p95],
        "descarte": {"n": len(descarte), "min": min(descarte), "max": max(descarte)},
        "winsorizacion": {"n": len(winsor), "min": min(winsor), "max": max(winsor)},
        "fallos": sorted(fallos),
    }
    assert not fallos, f"el oraculo falla en casos conocidos: {fallos}"
    assert len(descarte) == 8 and min(descarte) == 2.0 and max(descarte) == 9.0, descarte
    assert len(winsor) == 10 and abs(min(winsor) - p5) < 1e-9 and abs(max(winsor) - p95) < 1e-9
    # Epsilon y max_iteraciones: la no convergencia debe declararse, no inferirse.
    par286 = ORACULO.Parametros(**{**ESTADO["par"], "max_iteraciones": 1})
    no_conv = ORACULO.calcular(ORACULO.dataset_286_fail(), par286, "DESCARTE")
    informe["oracle_self_test"]["no_convergencia_con_max_iteraciones_1"] = {
        "estado": no_conv.estado, "etapa_fallo": no_conv.etapa_fallo,
        "iteraciones": no_conv.iteraciones,
    }
    assert no_conv.estado == "NO_CONVERGIDA" and no_conv.etapa_fallo == "REFINAMIENTO"

    # 6 · Independencia del oraculo (§23) ───────────────────────────────────
    fuente = (BASE_DIR / "oracle_g140.py").read_text(encoding="utf-8")
    prohibidos = [n for n in ("calcular_linea_base", "recortar_p5_p95", "src.configuration",
                              "src.telemetry")
                  if re.search(rf"^\s*(from|import)\s+.*{re.escape(n)}", fuente, re.M)]
    informe["independencia_del_oraculo"] = {
        "imports_prohibidos_encontrados": prohibidos,
        "veredicto": "PASS" if not prohibidos else "FAIL",
    }
    assert not prohibidos, f"el oraculo importa del producto: {prohibidos}"

    # 7 · Ventanas: cerradas, pasadas, disjuntas y nuevas (§29) ─────────────
    ahora = datetime.datetime.now(datetime.timezone.utc)

    def _ts(v):
        return datetime.datetime.fromisoformat(v.replace("Z", "+00:00"))

    pares = [(k, *v) for k, v in VENTANAS.items()]
    for k, ini, fin in pares:
        assert _ts(ini) < _ts(fin), f"{k}: inicio no es anterior al fin"
        assert _ts(fin) < ahora, f"{k}: la ventana no esta cerrada en el pasado"
    for i in range(len(pares)):
        for j in range(i + 1, len(pares)):
            (_, ai, af), (_, bi, bf) = pares[i], pares[j]
            assert af < bi or bf < ai, f"ventanas solapadas: {pares[i][0]} y {pares[j][0]}"
    for k, ini, fin in pares:
        for k1, (ai, af) in VENTANAS_EJECUCIONES_ANTERIORES.items():
            assert fin < ai or af < ini, f"{k} solapa {k1} de una ejecucion anterior"
    informe["ventanas"] = {
        "de_esta_ejecucion": {k: {"inicio": v[0], "fin": v[1]} for k, v in VENTANAS.items()},
        "de_ejecuciones_anteriores": {k: {"inicio": v[0], "fin": v[1]}
                                      for k, v in VENTANAS_EJECUCIONES_ANTERIORES.items()},
        "start_menor_que_end": "PASS", "cerradas_en_el_pasado": "PASS",
        "disjuntas_entre_si": "PASS", "disjuntas_de_ejecuciones_anteriores": "PASS",
    }

    # 8 · Rutas, artefactos y sanitizacion ─────────────────────────────────
    sonda = sanear({"Authorization": "Bearer abc.def", "password": ING[1],
                    "serial": f"QA-M09-G140-CAMK-{SELLO}",
                    "texto": f"token Bearer xyz.123 y clave {ING[1]}"})
    informe["artefactos_y_sanitizacion"] = {
        "RUN_DIR": str(RUN_DIR.relative_to(REPO_DIR)).replace("\\", "/"),
        "escribible": RUN_DIR.is_dir() and os.access(RUN_DIR, os.W_OK),
        "ficheros_canonicos_esperados": ["TC-M09-G140_reevaluacion_V2.md", "evidencia-test.json",
                                         "pytest-test.xml", "evidencia-local.json",
                                         "pytest-local.xml", "backend-local.log",
                                         "automation_manifest.json"],
        "sanitizacion": sonda,
    }
    assert RUN_DIR.is_dir() and os.access(RUN_DIR, os.W_OK), f"RUN_DIR no escribible: {RUN_DIR}"
    assert ING[1] not in json.dumps(sonda, ensure_ascii=False), "el sanitizador deja pasar la clave"
    assert "abc.def" not in json.dumps(sonda, ensure_ascii=False), "el sanitizador deja pasar el token"

    informe["AUTOMATION_PRECHECK"] = "PASS"
    informe["AUTORIZAR_POSTS"] = "SÍ"
    E["precheck_automatizacion"] = informe
    ESTADO["precheck_automatizacion"] = True
    guardar()


def test_07_compuerta_del_paquete():
    """§12 y §13: sin oráculos congelados y sin PRECHECK de automatización en PASS no se
    inician los POST oficiales de G140."""
    requiere("oraculos_ok", "precheck_automatizacion")
    if ESTADO.get("bd_ok") or not BD_OBLIGATORIA:
        ESTADO["autorizar_test"] = True
        E["compuerta"] = {
            "AUTORIZAR_TEST": "SÍ",
            "motivo": ("matriz actualizada: la herramienta oficial de TC-284 y TC-285 es "
                       "Pytest + API y la BD es verificación complementaria, así que su "
                       "disponibilidad no condiciona la ejecución"),
            "BD_COMPLEMENTARIA": E["acceso_bd"]["BD_COMPLEMENTARIA"],
        }
    else:
        faltantes = [t for t, v in E["acceso_bd"]["resultado"].items() if v == "FAIL"]
        motivo = (
            "PRECONDICIÓN DE ACCESO QA / DBA: member_qa no tiene SELECT sobre "
            f"{', '.join(TABLAS_ORACULO)} ({', '.join(faltantes)} en FAIL) y se pidió "
            "explícitamente exigir el oráculo de BD (G140_EXIGIR_BD).")
        ESTADO["autorizar_test"] = False
        ESTADO["motivo_compuerta"] = motivo
        E["compuerta"] = {
            "AUTORIZAR_TEST": "NO",
            "motivo": motivo,
            "clasificacion": "precondición de ambiente QA (no es bug funcional, §73)",
            "responsable": "DBA / Implementación",
            "remedio": ("GRANT SELECT sobre las tres tablas a member_qa (o al rol rol_qa que "
                        "hereda), y reejecutar este módulo en un RUN nuevo"),
            "no_se_hizo": ["crear fincas, áreas o cámaras en TEST",
                           "POST /iot/telemetria/vision",
                           "POST /configuracion/calibraciones-vision",
                           "modificar grants",
                           "presentar lecturas de la API como si fueran SELECT de BD"],
            "bd_exigida_por_variable": BD_OBLIGATORIA,
        }
        for caso in ("TC-M09-284", "TC-M09-285"):
            E["casos"][caso] = {"resultado": "BLOQUEADO",
                                "causa": "precondición de acceso QA / DBA (oráculo de BD)",
                                "post_ejecutados": 0}
    guardar()


# ══════════════════════════════════════════════════════════════════════════════
# FIXTURE EN TEST (solo si la compuerta abre)
# ══════════════════════════════════════════════════════════════════════════════

def test_08_fixture_test():
    requiere("oraculos_ok")
    autorizado()
    # El sufijo lleva el SELLO de la ejecucion, no el RUN_ID: el RUN es el mismo y
    # las areas y camaras de la ejecucion 2 no se reutilizan (§26).
    sufijo = SELLO
    # Finca QA compartida por los dos actores, resuelta dinámicamente. Hace falta la
    # intersección porque el Ingeniero NO tiene Crear sobre infraestructuras (recurso 10 solo
    # con acción 2, Leer): las áreas las crea el Administrador, y después el Ingeniero —actor
    # de los tres POST funcionales— tiene que poder verlas. Cada listado ya viene filtrado por
    # el alcance de quien pregunta.
    c, fincas_ing = API.get("ingeniero", "/configuracion/fincas")
    assert c == 200, f"listado de fincas del Ingeniero HTTP {c}"
    ca, fincas_adm = API.get("admin", "/configuracion/fincas")
    assert ca == 200, f"listado de fincas del Administrador HTTP {ca}"
    activas_ing = {f["id_finca"] for f in fincas_ing.get("items", []) if f.get("es_activo")}
    activas_adm = {f["id_finca"] for f in fincas_adm.get("items", []) if f.get("es_activo")}
    compartidas = sorted(activas_ing & activas_adm)
    assert compartidas, (
        "no hay ninguna finca activa en el alcance de los dos actores; el Administrador no "
        "podría crear las áreas donde el Ingeniero pueda calibrar")
    # Se prefiere la 163 (el fixture de G137, compartido desde su origen) si sigue válida.
    finca = 163 if 163 in compartidas else compartidas[0]
    E["fincas"] = {"del_ingeniero": sorted(activas_ing), "del_administrador": sorted(activas_adm),
                   "compartidas": compartidas, "elegida": finca}

    # §20: especie AVES existente, compatible con MODELO_AVES.
    c, especies = API.get("admin", "/configuracion/especies?limite=200")
    assert c == 200, f"catálogo de especies HTTP {c}"
    lista = especies.get("items", especies if isinstance(especies, list) else [])
    aves = [e for e in lista if str(e.get("tipo_modelo")) == "MODELO_AVES" and e.get("es_activo")]
    assert aves, "no hay especie activa con tipo_modelo MODELO_AVES"
    # Se prefiere reutilizar la especie AVES que ya usaron G137 y G139 si sigue activa.
    especie = next((e["id_especie"] for e in aves if e["id_especie"] == 41), aves[0]["id_especie"])

    c, tipos = API.get("admin", "/configuracion/tipos-area")
    tipo_area = None
    if c == 200:
        ta = tipos.get("items", tipos if isinstance(tipos, list) else [])
        activos = [t for t in ta if t.get("es_activo")]
        tipo_area = next((t.get("nombre") for t in activos
                          if "galp" in str(t.get("nombre")).lower()),
                         (activos[0].get("nombre") if activos else None))
    assert tipo_area, "no se pudo resolver un tipo de área activo del catálogo"

    areas = {}
    for clave, etiqueta in (("a1", "A1"), ("a1p", "A1P")):
        # Nombres de RF-20: nombre_infraestructura, tipo_area, superficie, finca_id,
        # descripcion_infraestructura, especie_id, tipo_modelo_asignado. El campo lleva el
        # MODELO (MODELO_AVES); el paradigma POBLACIONAL se deriva de él.
        cuerpo = {"nombre_infraestructura": f"QA-G140-{etiqueta}-{sufijo}",
                  "tipo_area": tipo_area, "superficie": 120.0, "finca_id": finca,
                  "descripcion_infraestructura": f"Area gemela {etiqueta} de {GRUPO} ({RUN_ID})",
                  "especie_id": especie, "tipo_modelo_asignado": "MODELO_AVES"}
        # Crea el Administrador: el Ingeniero no tiene Crear sobre infraestructuras (RF-20).
        c, a = API.post("admin", "/configuracion/infraestructuras", cuerpo)
        assert c in (200, 201), f"creación del área {etiqueta} HTTP {c}: {sanear(a)}"
        ESTADO[clave] = a["id_infraestructura"]
        areas[etiqueta] = {"id": a["id_infraestructura"],
                           "nombre": a.get("nombre_infraestructura"),
                           "especie_id": a.get("especie_id"),
                           "tipo_modelo_asignado": a.get("tipo_modelo_asignado"),
                           "es_activo": a.get("es_activo"), "finca_id": a.get("id_finca")}
        assert a.get("especie_id") == especie, a
        assert a.get("tipo_modelo_asignado") == "MODELO_AVES", a

    # Compuerta de alcance: si el Ingeniero no viera las áreas, los POST funcionales fallarían
    # por una precondición de datos y no por el comportamiento bajo prueba.
    for clave, etiqueta in (("a1", "A1"), ("a1p", "A1P")):
        cv, vista = API.get("ingeniero", f"/configuracion/infraestructuras/{ESTADO[clave]}")
        areas[etiqueta]["visible_para_el_ingeniero"] = cv
        assert cv == 200, (
            f"el Ingeniero no ve el área {etiqueta} ({ESTADO[clave]}) creada por el "
            f"Administrador: HTTP {cv}")
        assert vista.get("es_activo") is True, f"el área {etiqueta} no quedó activa"

    camaras = {}
    for clave, etiqueta, area in (("cam_k", "CAM_K", ESTADO["a1"]),
                                  ("cam_km", "CAM_KM", ESTADO["a1p"])):
        serial = f"QA-M09-G140-{'CAMK' if etiqueta == 'CAM_K' else 'CAMKM'}-{sufijo}"
        cuerpo = {"serial": serial,
                  "descripcion": f"QA {GRUPO} camara VISION {etiqueta} ({RUN_ID})",
                  "id_infraestructura": area, "id_tipo_dispositivo": TIPO_CAMARA_VISION,
                  "es_activo": True, "resolucion": "1920x1080", "fps": 30,
                  "area_cobertura_m2": "50.00"}
        c, d = API.post("ingeniero", "/configuracion/dispositivos-iot", cuerpo)
        assert c in (200, 201), f"registro de {etiqueta} HTTP {c}: {sanear(d)}"
        ESTADO[clave] = d["id_dispositivo_iot"]
        ESTADO[f"{clave}_serial"] = serial
        ESTADO[f"{clave}_fps"] = d.get("fps")
        camaras[etiqueta] = {"id": d["id_dispositivo_iot"], "serial": "[SERIAL REDACTED]",
                             "categoria": d.get("categoria"), "es_activo": d.get("es_activo"),
                             "fps_nominal": d.get("fps"), "id_infraestructura": d.get("id_infraestructura")}
        assert d.get("categoria") == "CAMARA" and d.get("es_activo") is True

    E["fixture"] = {"finca_id": finca, "especie_id": especie, "tipo_area": tipo_area,
                    "areas": areas, "camaras": camaras,
                    "gemelas": "misma finca, misma especie, MODELO_AVES, activas, una cámara activa cada una"}
    ESTADO["fixture"] = True


# ══════════════════════════════════════════════════════════════════════════════
# TC-M09-284 — Etapa 1
# ══════════════════════════════════════════════════════════════════════════════

def test_09_lotes_284():
    requiere("fixture")
    autorizado()
    k = [ORACULO.vector_k(i) for i in range(40)]
    fechas_k = instantes(VENTANAS["WINDOW_284_K"][0], 40, 5)
    cuerpo_k = {"device_id": ESTADO["cam_k"], "access_key": ESTADO["cam_k_serial"],
                "area_id": ESTADO["a1"],
                "observaciones": [obs(ts, d, t, ESTADO["cam_k_fps"], True)
                                  for ts, (d, t) in zip(fechas_k, k)]}
    c1, b1 = API.post_vision(cuerpo_k, "lote_k")
    assert c1 in (200, 201), f"lote K HTTP {c1}: {sanear(b1)}"

    fechas_km = instantes(VENTANAS["WINDOW_284_KM"][0], 50, 4)
    observaciones = [obs(ts, d, t, ESTADO["cam_km_fps"], True)
                     for ts, (d, t) in zip(fechas_km[:40], k)]
    observaciones += [obs(ts, 1000.0, 500.0, ESTADO["cam_km_fps"], False)
                      for ts in fechas_km[40:]]
    cuerpo_km = {"device_id": ESTADO["cam_km"], "access_key": ESTADO["cam_km_serial"],
                 "area_id": ESTADO["a1p"], "observaciones": observaciones}
    c2, b2 = API.post_vision(cuerpo_km, "lote_km")
    assert c2 in (200, 201), f"lote K+M HTTP {c2}: {sanear(b2)}"

    aptas_k = [o for o in b1["observaciones"] if o["apto_para_ia"]]
    aptas_km = [o for o in b2["observaciones"] if o["apto_para_ia"]]
    E["casos"]["TC-M09-284"] = {
        "ventanas": {"WINDOW_284_K": dict(zip(("inicio", "fin"), VENTANAS["WINDOW_284_K"])),
                     "WINDOW_284_KM": dict(zip(("inicio", "fin"), VENTANAS["WINDOW_284_KM"]))},
        "lote_K": {"http": c1, "total": b1["total"], "aceptadas": b1["aceptadas"],
                   "duplicadas": b1["duplicadas"], "aptas": len(aptas_k),
                   "indices_distintos": sorted({o["indice_calidad"] for o in b1["observaciones"]})},
        "lote_KM": {"http": c2, "total": b2["total"], "aceptadas": b2["aceptadas"],
                    "duplicadas": b2["duplicadas"], "aptas": len(aptas_km),
                    "no_aptas": b2["aceptadas"] - len(aptas_km),
                    "indices_distintos": sorted({o["indice_calidad"] for o in b2["observaciones"]})},
        "vectores_K": E["oraculos_congelados"]["TC-M09-284"]["vectores_K"],
    }
    assert b1["aceptadas"] == 40 and b1["duplicadas"] == 0 and len(aptas_k) == 40
    assert b2["aceptadas"] == 50 and b2["duplicadas"] == 0 and len(aptas_km) == 40
    ESTADO["lotes_284"] = True


def test_10_bd_pre_284():
    requiere("lotes_284")
    autorizado()
    res = select([
        ("A1", f"""SELECT COUNT(*) AS total,
                          SUM(CASE WHEN es_apto_para_ia THEN 1 ELSE 0 END) AS aptas
                   FROM modulo3.observaciones_vision
                   WHERE id_dispositivo_iot = {ESTADO['cam_k']}
                     AND fecha_observacion BETWEEN '{VENTANAS['WINDOW_284_K'][0]}'
                                              AND '{VENTANAS['WINDOW_284_K'][1]}'"""),
        ("A1_PRIMA", f"""SELECT COUNT(*) AS total,
                                SUM(CASE WHEN es_apto_para_ia THEN 1 ELSE 0 END) AS aptas
                         FROM modulo3.observaciones_vision
                         WHERE id_dispositivo_iot = {ESTADO['cam_km']}
                           AND fecha_observacion BETWEEN '{VENTANAS['WINDOW_284_KM'][0]}'
                                                    AND '{VENTANAS['WINDOW_284_KM'][1]}'"""),
    ])
    E["casos"]["TC-M09-284"]["conteos_bd"] = {
        "disponible": ESTADO.get("bd_ok", False),
        "nota": ("verificación complementaria; el conteo funcional sale de la respuesta de "
                 "POST /iot/telemetria/vision (total, aceptadas, duplicadas y el apto_para_ia "
                 "de cada observación)"),
        "resultado": res,
    }
    if ESTADO.get("bd_ok"):
        a1, a1p = res.get("A1", [{}])[0], res.get("A1_PRIMA", [{}])[0]
        assert int(a1.get("total", -1)) == 40 and int(a1.get("aptas", -1)) == 40, a1
        assert int(a1p.get("total", -1)) == 50 and int(a1p.get("aptas", -1)) == 40, a1p
    ESTADO["bd_pre_284"] = True


def test_11_corridas_284():
    requiere("bd_pre_284")
    autorizado()
    resultados = {}
    for etiqueta, area, ventana, nota, marca in (
            ("K", ESTADO["a1"], "WINDOW_284_K", "QA TC-M09-284 K", "cal_k"),
            ("K+M", ESTADO["a1p"], "WINDOW_284_KM", "QA TC-M09-284 K+M", "cal_km")):
        ini, fin = VENTANAS[ventana]
        cuerpo = {"modo_calibracion": "VISION", "area_id": area,
                  "ventana_observacion": {"inicio": ini, "fin": fin}, "observaciones": nota,
                  "fecha_calibracion": datetime.datetime.now(datetime.timezone.utc).isoformat()}
        c, b = API.post_calibracion(cuerpo, marca)
        resultados[etiqueta] = {"request": cuerpo, "http": c, "response": b}
        assert 200 <= c < 300, f"corrida {etiqueta} esperaba 2xx y obtuvo {c}: {sanear(b)}"
        assert b["estado"] == "EXITOSA", f"{etiqueta}: estado {b['estado']}"
    E["casos"]["TC-M09-284"]["corridas"] = resultados
    k, km = resultados["K"]["response"], resultados["K+M"]["response"]
    ESTADO["cal_k_id"], ESTADO["cal_km_id"] = k["id_calibracion_vision"], km["id_calibracion_vision"]
    ESTADO["base_k"] = k["linea_base"]["valores"]
    ESTADO["base_km"] = km["linea_base"]["valores"]
    assert k["n_observaciones"] == 40 and k["n_observaciones_validas"] == 40, k
    assert km["n_observaciones"] == 50 and km["n_observaciones_validas"] == 40, km
    ESTADO["corridas_284"] = True


def test_12_oraculo_y_bd_284():
    requiere("corridas_284")
    autorizado()
    base_k, base_km = ESTADO["base_k"], ESTADO["base_km"]
    congelado = ESTADO["oraculos"]["TC-M09-284"]
    coincidencias = {
        modo: {"K": ORACULO.coincide(base_k, congelado["K"][modo]["valores"]),
               "K+M": ORACULO.coincide(base_km, congelado["K+M"][modo]["valores"])}
        for modo in ("ORACLE_DESCARTE", "ORACLE_WINSORIZACION")}
    res = select([
        ("calibracion_K", f"""SELECT id_calibracion_vision, estado, cantidad_observaciones,
                                     cantidad_observaciones_validas, json_linea_base
                              FROM modulo9.calibraciones_vision
                              WHERE id_calibracion_vision = {ESTADO['cal_k_id']}"""),
        ("calibracion_KM", f"""SELECT id_calibracion_vision, estado, cantidad_observaciones,
                                      cantidad_observaciones_validas, json_linea_base
                               FROM modulo9.calibraciones_vision
                               WHERE id_calibracion_vision = {ESTADO['cal_km_id']}"""),
        ("lineas_base", f"""SELECT id_infraestructura, id_especie, id_calibracion_vision, json_valor
                            FROM modulo9.lineas_base_vision
                            WHERE id_infraestructura IN ({ESTADO['a1']}, {ESTADO['a1p']})
                            ORDER BY id_infraestructura"""),
    ])
    caso = E["casos"]["TC-M09-284"]
    caso["BASE_K"] = base_k
    caso["BASE_KM"] = base_km
    caso["identicas"] = "SÍ" if ORACULO.coincide(base_k, base_km) else "NO"
    caso["coincidencia_con_oraculo"] = coincidencias
    caso["verificacion_bd"] = {"disponible": ESTADO.get("bd_ok", False),
                               "nota": "verificación complementaria", "resultado": res}

    # ── Oráculo funcional: persistencia y vigencia por los endpoints oficiales ──
    api = {}
    for etiqueta, area, cal_id in (("K", ESTADO["a1"], ESTADO["cal_k_id"]),
                                   ("K+M", ESTADO["a1p"], ESTADO["cal_km_id"])):
        ch, hist = API.get("ingeniero", f"/configuracion/calibraciones-vision?area_id={area}")
        assert ch == 200, f"historial de {etiqueta} HTTP {ch}"
        fila = next((i for i in hist.get("items", [])
                     if i["id_calibracion_vision"] == cal_id), None)
        cl, lb = API.get("ingeniero",
                         f"/configuracion/calibraciones-vision/linea-base?area_id={area}")
        assert cl == 200, f"línea base de {etiqueta} HTTP {cl}"
        api[etiqueta] = {
            "historial_http": ch, "historial_total": hist.get("total"),
            "historial_ids": [i["id_calibracion_vision"] for i in hist.get("items", [])],
            "en_historial": "PASS" if fila else "FAIL",
            "fila": {k: fila.get(k) for k in
                     ("id_calibracion_vision", "estado", "etapa_fallo", "n_observaciones",
                      "n_observaciones_validas", "origen_disparo", "id_usuario")} if fila else None,
            "linea_base_http": cl,
            "linea_base_vigente": lb.get("id_calibracion_vision"),
            "linea_base_valores": (lb.get("linea_base") or {}).get("valores"),
        }
        assert fila is not None, f"{etiqueta}: la calibración {cal_id} no aparece en el historial"
        assert fila["estado"] == "EXITOSA", f"{etiqueta}: {fila['estado']}"
        assert lb.get("id_calibracion_vision") == cal_id, (
            f"{etiqueta}: la línea base vigente apunta a {lb.get('id_calibracion_vision')} "
            f"y no a {cal_id}")
    caso["verificacion_api"] = api
    assert api["K"]["fila"]["n_observaciones_validas"] == 40
    assert api["K+M"]["fila"]["n_observaciones"] == 50
    assert api["K+M"]["fila"]["n_observaciones_validas"] == 40
    assert ORACULO.coincide(api["K"]["linea_base_valores"], base_k)
    assert ORACULO.coincide(api["K+M"]["linea_base_valores"], base_km)

    caso["cuadro"] = [
        {"criterio": "Total", "K": 40, "K+M": 50},
        {"criterio": "Aptas", "K": 40, "K+M": 40},
        {"criterio": "No aptas", "K": 0, "K+M": 10},
        {"criterio": "HTTP", "K": caso["corridas"]["K"]["http"], "K+M": caso["corridas"]["K+M"]["http"]},
        {"criterio": "Estado", "K": "EXITOSA", "K+M": "EXITOSA"},
        {"criterio": "Válidas backend", "K": 40, "K+M": 40},
        {"criterio": "Línea base", "K": base_k, "K+M": base_km},
    ]
    assert ORACULO.coincide(base_k, base_km), (
        f"la presencia de M alteró la línea base: {base_k} vs {base_km}")
    if ESTADO.get("bd_ok"):
        bd_k = res.get("calibracion_K", [{}])[0]
        bd_km = res.get("calibracion_KM", [{}])[0]
        assert bd_k.get("estado") == "EXITOSA" and bd_k.get("cantidad_observaciones") == 40
        assert bd_k.get("cantidad_observaciones_validas") == 40
        assert bd_km.get("estado") == "EXITOSA" and bd_km.get("cantidad_observaciones") == 50
        assert bd_km.get("cantidad_observaciones_validas") == 40
        lb = {f["id_infraestructura"]: f["id_calibracion_vision"]
              for f in res.get("lineas_base", []) if isinstance(f, dict)}
        assert lb.get(ESTADO["a1"]) == ESTADO["cal_k_id"], lb
        assert lb.get(ESTADO["a1p"]) == ESTADO["cal_km_id"], lb
    caso["resultado"] = "APROBADO"
    ESTADO["tc284"] = True


# ══════════════════════════════════════════════════════════════════════════════
# TC-M09-285 — Etapas 2 y 3
# ══════════════════════════════════════════════════════════════════════════════

def test_13_dataset_285():
    requiere("tc284")
    autorizado()
    valores = [(d, d * 10) for d in ORACULO.DENSIDAD_285]
    fechas = instantes(VENTANAS["WINDOW_285"][0], len(valores), 5)
    cuerpo = {"device_id": ESTADO["cam_k"], "access_key": ESTADO["cam_k_serial"],
              "area_id": ESTADO["a1"],
              "observaciones": [obs(ts, d, t, ESTADO["cam_k_fps"], True)
                                for ts, (d, t) in zip(fechas, valores)]}
    c, b = API.post_vision(cuerpo, "lote_285")
    assert c in (200, 201), f"lote 285 HTTP {c}: {sanear(b)}"
    aptas = [o for o in b["observaciones"] if o["apto_para_ia"]]
    res = select([("ventana", f"""SELECT COUNT(*) AS total,
                                        SUM(CASE WHEN es_apto_para_ia THEN 1 ELSE 0 END) AS aptas
                                 FROM modulo3.observaciones_vision
                                 WHERE id_dispositivo_iot = {ESTADO['cam_k']}
                                   AND fecha_observacion BETWEEN '{VENTANAS['WINDOW_285'][0]}'
                                                            AND '{VENTANAS['WINDOW_285'][1]}'""")])
    E["casos"]["TC-M09-285"] = {
        "ventana": dict(zip(("inicio", "fin"), VENTANAS["WINDOW_285"])),
        "area_id": ESTADO["a1"], "camara_id": ESTADO["cam_k"],
        "dataset": {"densidad_actividad": ORACULO.DENSIDAD_285,
                    "tasa_movimiento": [d * 10 for d in ORACULO.DENSIDAD_285]},
        "lote": {"http": c, "total": b["total"], "aceptadas": b["aceptadas"],
                 "duplicadas": b["duplicadas"], "aptas": len(aptas)},
        "conteo_bd": {"disponible": ESTADO.get("bd_ok", False),
                      "nota": "verificación complementaria", "resultado": res.get("ventana")},
    }
    assert b["aceptadas"] == 40 and b["duplicadas"] == 0 and len(aptas) == 40
    assert all(o["clasificacion_calidad"] == "APTO" for o in b["observaciones"])
    if ESTADO.get("bd_ok"):
        fila = res.get("ventana", [{}])[0]
        assert int(fila.get("total", -1)) == 40 and int(fila.get("aptas", -1)) == 40, fila
    ESTADO["dataset_285"] = True


def test_14_corrida_285():
    requiere("dataset_285")
    autorizado()
    ini, fin = VENTANAS["WINDOW_285"]
    cuerpo = {"modo_calibracion": "VISION", "area_id": ESTADO["a1"],
              "ventana_observacion": {"inicio": ini, "fin": fin},
              "observaciones": "QA TC-M09-285",
              "fecha_calibracion": datetime.datetime.now(datetime.timezone.utc).isoformat()}
    c, b = API.post_calibracion(cuerpo, "cal_285")
    caso = E["casos"]["TC-M09-285"]
    caso["request"] = cuerpo
    caso["response"] = {"http": c, "body": b}
    assert 200 <= c < 300, f"TC-285 esperaba 2xx y obtuvo {c}: {sanear(b)}"
    assert b["estado"] == "EXITOSA", b["estado"]
    assert b["etapa_fallo"] is None, b["etapa_fallo"]
    assert b["linea_base"] is not None
    assert b["iteraciones"] is not None and b["iteraciones"] <= ESTADO["par"]["max_iteraciones"], b
    ESTADO["cal_285_id"] = b["id_calibracion_vision"]
    ESTADO["base_285"] = b["linea_base"]["valores"]
    ESTADO["iter_285"] = b["iteraciones"]
    ESTADO["corrida_285"] = True


def test_15_comparacion_285():
    requiere("corrida_285")
    autorizado()
    congelado = ESTADO["oraculos"]["TC-M09-285"]
    producto = ESTADO["base_285"]
    descarte = congelado["ORACLE_DESCARTE"]
    winsor = congelado["ORACLE_WINSORIZACION"]
    coincide_d = ORACULO.coincide(producto, descarte["valores"])
    coincide_w = ORACULO.coincide(producto, winsor["valores"])
    interpretacion = ("DESCARTE" if coincide_d else ("WINSORIZACION" if coincide_w else "NINGUNA"))
    limites = descarte["traza"]["etapa_2"]
    caso = E["casos"]["TC-M09-285"]
    caso["cuadro_por_componente"] = [
        {"componente": comp, "producto": producto.get(comp),
         "descarte": descarte["valores"].get(comp), "winsorizacion": winsor["valores"].get(comp),
         "coincide": ("DESCARTE" if abs(producto.get(comp, 0) - descarte["valores"].get(comp, 0)) <= 1e-9
                      else ("WINSORIZACION" if abs(producto.get(comp, 0) - winsor["valores"].get(comp, 0)) <= 1e-9
                            else "NINGUNA"))}
        for comp in sorted(producto)]
    caso["p5_p95"] = {comp: {"p5": v["p5"], "p95": v["p95"],
                             "n_tras_descarte": v["n_tras_recorte"]}
                      for comp, v in limites.items()}
    caso["epsilon"] = ESTADO["par"]["epsilon"]
    caso["max_iteraciones"] = ESTADO["par"]["max_iteraciones"]
    caso["iteraciones_producto"] = ESTADO["iter_285"]
    caso["INTERPRETACION_OBSERVADA"] = interpretacion
    res = select([
        ("calibracion", f"""SELECT id_calibracion_vision, estado, cantidad_observaciones,
                                   cantidad_observaciones_validas, iteraciones, json_linea_base
                            FROM modulo9.calibraciones_vision
                            WHERE id_calibracion_vision = {ESTADO['cal_285_id']}"""),
        ("linea_base", f"""SELECT id_calibracion_vision, json_valor FROM modulo9.lineas_base_vision
                           WHERE id_infraestructura = {ESTADO['a1']}"""),
    ])
    caso["verificacion_bd"] = {"disponible": ESTADO.get("bd_ok", False),
                               "nota": "verificación complementaria", "resultado": res}

    # ── Oráculo funcional: persistencia y vigencia por los endpoints oficiales ──
    ch, hist = API.get("ingeniero", f"/configuracion/calibraciones-vision?area_id={ESTADO['a1']}")
    assert ch == 200, f"historial de TC-285 HTTP {ch}"
    fila = next((i for i in hist.get("items", [])
                 if i["id_calibracion_vision"] == ESTADO["cal_285_id"]), None)
    cl, lb = API.get("ingeniero",
                     f"/configuracion/calibraciones-vision/linea-base?area_id={ESTADO['a1']}")
    assert cl == 200, f"línea base de TC-285 HTTP {cl}"
    caso["verificacion_api"] = {
        "historial_http": ch, "historial_total": hist.get("total"),
        "historial_ids": [i["id_calibracion_vision"] for i in hist.get("items", [])],
        "en_historial": "PASS" if fila else "FAIL",
        "fila": {k: fila.get(k) for k in
                 ("id_calibracion_vision", "estado", "etapa_fallo", "n_observaciones",
                  "n_observaciones_validas", "iteraciones", "origen_disparo", "id_usuario")}
        if fila else None,
        "linea_base_http": cl,
        "linea_base_vigente": lb.get("id_calibracion_vision"),
        "linea_base_valores": (lb.get("linea_base") or {}).get("valores"),
    }
    assert interpretacion != "NINGUNA", (
        "el resultado del producto no coincide con DESCARTE ni con WINSORIZACION: "
        f"producto={producto} descarte={descarte['valores']} winsor={winsor['valores']}")
    assert fila is not None, "la calibración de TC-285 no aparece en el historial"
    assert fila["estado"] == "EXITOSA", fila["estado"]
    assert fila["n_observaciones"] == 40 and fila["n_observaciones_validas"] == 40, fila
    assert lb.get("id_calibracion_vision") == ESTADO["cal_285_id"], lb
    assert ORACULO.coincide((lb.get("linea_base") or {}).get("valores"), producto), (
        "la línea base vigente no trae los mismos valores que devolvió el POST")
    if ESTADO.get("bd_ok"):
        bd = res.get("calibracion", [{}])[0]
        assert bd.get("estado") == "EXITOSA" and bd.get("cantidad_observaciones") == 40
        assert bd.get("cantidad_observaciones_validas") == 40
        assert bd.get("iteraciones") == ESTADO["iter_285"]
        assert (res.get("linea_base", [{}])[0] or {}).get("id_calibracion_vision") == ESTADO["cal_285_id"]
    caso["resultado"] = "APROBADO"
    ESTADO["tc285"] = True


def test_16_cierre_test():
    requiere("oraculos_ok")
    r284 = E["casos"].get("TC-M09-284", {}).get("resultado", "BLOQUEADO")
    r285 = E["casos"].get("TC-M09-285", {}).get("resultado", "BLOQUEADO")
    E["resultado"] = {
        "TC-M09-284": r284,
        "TC-M09-285": r285,
        "AUTORIZAR_TEST": E.get("compuerta", {}).get("AUTORIZAR_TEST"),
        "AUTORIZAR_POSTS": E.get("precheck_automatizacion", {}).get("AUTORIZAR_POSTS"),
        "BD_COMPLEMENTARIA": E["acceso_bd"]["BD_COMPLEMENTARIA"],
        "TC-M09-286": ("se reejecuta en el laboratorio LOCAL de esta misma ejecucion; "
                       "el veredicto esta en evidencia-local.json"),
        "regresiones_284_285": "NINGUNA" if (r284 == "APROBADO" and r285 == "APROBADO")
                               else "SÍ: revisar producto, fixture y automatizacion (§77)",
        "nueva_incidencia_284_285": "NO" if (r284 == "APROBADO" and r285 == "APROBADO") else "SÍ",
    }
    # §83 — la ejecucion 3 se anexa al historial; las anteriores no se borran.
    E["historial_ejecuciones"].append({
        "ejecucion": EJECUCION_GRUPO,
        "run_id": RUN_ID,
        "fecha": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "tipo": TIPO_EJECUCION,
        "autorizado_por": AUTORIZADO_POR,
        "pr": PR_CORRECCION,
        "mitad": "TEST (TC-M09-284 y TC-M09-285)",
        "resultados": {"TC-M09-284": r284, "TC-M09-285": r285},
        "fixture": {"finca_id": E.get("fixture", {}).get("finca_id"),
                    "especie_id": E.get("fixture", {}).get("especie_id"),
                    "areas": {k: v.get("id") for k, v in
                              E.get("fixture", {}).get("areas", {}).items()},
                    "camaras": {k: v.get("id") for k, v in
                                E.get("fixture", {}).get("camaras", {}).items()},
                    "ventanas": [v[0][:10] for v in VENTANAS.values()]},
        "presupuesto": dict(E["presupuesto"]),
    })
    E["comparacion_del_grupo"] = [
        {"caso": "TC-M09-284", "ejecucion_1": "BLOQUEADO", "ejecucion_2": "APROBADO",
         "ejecucion_3": r284},
        {"caso": "TC-M09-285", "ejecucion_1": "BLOQUEADO", "ejecucion_2": "APROBADO",
         "ejecucion_3": r285},
        {"caso": "TC-M09-286", "ejecucion_1": "RECHAZADO",
         "ejecucion_2": "RECHAZADO heredado (no reejecutado)",
         "ejecucion_3": "ver evidencia-local.json"},
    ]
    E["seguridad"] = {
        "credenciales_persistidas": "NO",
        "serial_access_key_persistido": "NO — redactado por patrón, solo en memoria",
        "sql_dml_en_test": 0,
        "sesion_bd": "READ ONLY",
        "baseline_primera_evaluacion_modificada": "NO",
    }
    if ESTADO.get("autorizar_test"):
        assert E["presupuesto"]["post_calibracion"] == 3, E["presupuesto"]
        assert E["presupuesto"]["post_vision"] == 3, E["presupuesto"]
    else:
        assert E["presupuesto"]["post_calibracion"] == 0, (
            "la compuerta del §12 no abrió y aun así se ejecutaron POST")
        assert E["presupuesto"]["post_vision"] == 0, E["presupuesto"]
    guardar()
