"""TC-M09-G141 / TC-M09-287 — un cálculo VISION exitoso reemplaza la línea base vigente.

RF-24 v2.0 · CU05 Flujo F · SEGUNDA EVALUACIÓN.

Secuencia que se demuestra: **L1 vigente → ventana nueva W2 → segundo cálculo exitoso → L2
vigente**, sobre el mismo par (área, especie).

Oráculo principal (§3): los endpoints oficiales.

    GET  /configuracion/calibraciones-vision/linea-base?area_id=<A1>   (antes)
    POST /configuracion/calibraciones-vision                           (una sola vez)
    GET  /configuracion/calibraciones-vision/linea-base?area_id=<A1>   (después)
    GET  /configuracion/calibraciones-vision?area_id=<A1>              (historial, complementario)

La BD de TEST es **únicamente evidencia complementaria**: si `member_qa` no tiene SELECT se
registra `BD_COMPLEMENTARIA = NO DISPONIBLE` y la ejecución continúa. No se bloquea, no se salta
ningún caso y no se presenta ninguna lectura de la API como si fuera un SELECT.

Presupuesto: **1** POST de calibración (el objetivo) y los lotes M03 mínimos. 0 reintentos.

Uso:
    pytest test_g141_v2.py -v --confcutdir=. --junitxml=<RUN>/pytest.xml
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

# ── Localización y guarda de rutas ───────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
EVAL_DIR = BASE_DIR.parent
CASE_DIR = EVAL_DIR.parent
GRUPO, CASO = "TC-M09-G141", "TC-M09-287"
if BASE_DIR.name != "automation" or EVAL_DIR.name != "EvaluacionV2" or CASE_DIR.name != GRUPO:
    raise RuntimeError(f"ABORTADO: ruta no autorizada para {GRUPO}: {BASE_DIR}")
REPO_DIR = CASE_DIR.parents[4]

RUN_ID = os.environ.get("G141_RUN_ID") or datetime.datetime.now().strftime("run-%Y%m%d-%H%M%S")
RUN_DIR = EVAL_DIR / "RESULTADOS" / RUN_ID
RUN_DIR.mkdir(parents=True, exist_ok=True)

# ── Entorno decisorio ────────────────────────────────────────────────────────
BASE_URL = "https://api.inmero.co/back-sigab-test"
if not BASE_URL.endswith("/back-sigab-test"):
    raise RuntimeError("ABORTADO: el ambiente decisorio de G141 es TEST")

ING = ("ingeniero@pecuaria.co", "Test1234!")
DB = {"host": "158.69.200.27", "port": "5448", "dbname": "sgpmp_test",
      "user": "member_qa", "password": "qaSGP2026"}

TIPO_CAMARA_VISION = 5
POBLACIONALES = {"MODELO_AVES", "MODELO_PORCINOS", "MODELO_ACUICULTURA"}
PRESUPUESTO = {"post_calibracion_objetivo": 1, "post_calibracion_setup": 1, "post_vision": 2}
_RE_SERIAL = re.compile(r"QA-M09-G1\d{2}-[A-Z]+-\d{8}-\d{6}")

E: dict = {
    "run_id": RUN_ID, "grupo": GRUPO, "caso": CASO,
    "ambiente": "TEST", "base_url": BASE_URL,
    "herramienta": "Pytest + API HTTP real contra TEST; BD solo complementaria",
    "newman": "NO APLICA",
    "generado": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "presupuesto": {"post_calibracion_objetivo": 0, "post_calibracion_setup": 0,
                    "post_vision": 0, "reintentos": 0},
    "limitaciones": [],
}
ESTADO: dict = {"hechos": set()}


def sanear(d):
    """Redacta secretos antes de persistir: tokens, contraseñas y seriales de cámara."""
    if isinstance(d, dict):
        return {k: ("[REDACTED]" if str(k).lower() in (
            "authorization", "token", "access_token", "refresh_token", "contrasena", "password",
            "access_key", "serial", "cookie", "set-cookie", "dsn") else sanear(v))
            for k, v in d.items()}
    if isinstance(d, list):
        return [sanear(x) for x in d]
    if isinstance(d, str):
        s = _RE_SERIAL.sub("[SERIAL REDACTED]", d)
        s = re.sub(r"Bearer\s+[A-Za-z0-9._\-]+", "Bearer [REDACTED]", s)
        return s.replace(ING[1], "[REDACTED]").replace(DB["password"], "[REDACTED]")
    return d


def guardar():
    (RUN_DIR / "evidencia.json").write_text(
        json.dumps(sanear(E), indent=2, ensure_ascii=False, default=str), encoding="utf-8")


def select(consultas: list[tuple[str, str]]) -> dict:
    """SELECT en sesión READ ONLY, en un intérprete aislado; la contraseña va por entorno."""
    for _, sql in consultas:
        if re.search(r"\b(insert|update|delete|alter|drop|truncate|create|grant|revoke)\b",
                     sql, re.I):
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

    def login(self, correo: str, clave: str, etiqueta: str) -> None:
        r = self.s.post(f"{BASE_URL}/sesiones/",
                        json={"correo_electronico": correo, "contrasena": clave}, timeout=90)
        assert r.status_code == 200, f"login {etiqueta}: HTTP {r.status_code} {sanear(r.text)[:300]}"
        self.tokens[etiqueta] = r.json()["token"]

    def _h(self, etiqueta: str) -> dict:
        return {"Authorization": f"Bearer {self.tokens[etiqueta]}", "Accept": "application/json"}

    def get(self, etiqueta: str, path: str, timeout: int = 150):
        r = self.s.get(f"{BASE_URL}{path}", headers=self._h(etiqueta), timeout=timeout)
        return r.status_code, _cuerpo(r)

    def post(self, etiqueta: str, path: str, cuerpo: dict, timeout: int = 240):
        r = self.s.post(f"{BASE_URL}{path}", headers=self._h(etiqueta), json=cuerpo, timeout=timeout)
        return r.status_code, _cuerpo(r)

    def patch(self, etiqueta: str, path: str, timeout: int = 150):
        r = self.s.patch(f"{BASE_URL}{path}", headers=self._h(etiqueta), timeout=timeout)
        return r.status_code, _cuerpo(r)

    def post_calibracion(self, cuerpo: dict, marca: str, clase: str):
        if marca in ESTADO["hechos"]:
            raise RuntimeError(f"ABORTADO: reintento prohibido del POST funcional {marca}")
        clave = f"post_calibracion_{clase}"
        if E["presupuesto"][clave] >= PRESUPUESTO[clave]:
            raise RuntimeError(f"ABORTADO: presupuesto de {clave} agotado")
        ESTADO["hechos"].add(marca)
        E["presupuesto"][clave] += 1
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


def iso(dt: datetime.datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def parse(ts: str) -> datetime.datetime:
    return datetime.datetime.fromisoformat(str(ts).replace("Z", "+00:00"))


def obs_apta(ts: str, densidad: float, tasa: float, fps: int) -> dict:
    return {"timestamp_captura": ts, "cobertura_ventana": "1.0000", "n_tracks": 20,
            "n_tracks_perdidos": 0, "fps_efectivo": f"{int(fps)}.00",
            "estado_calibracion": "CALIBRADA",
            "vector": {"densidad_actividad": densidad, "tasa_movimiento": tasa}}


def igual(a: dict | None, b: dict | None, tol: float = 1e-9) -> bool:
    if not isinstance(a, dict) or not isinstance(b, dict) or set(a) != set(b):
        return False
    return all(abs(float(a[k]) - float(b[k])) <= tol for k in a)


@pytest.fixture(scope="session", autouse=True)
def red_de_seguridad():
    """Al cerrar: desactiva la cámara creada por el RUN y deja los artefactos escritos."""
    yield
    restauracion = {"camara_desactivada": None, "pendientes": [],
                    "L2_conservada": "SÍ — es resultado funcional válido de la prueba",
                    "linea_base_vigente_conservada": "SÍ", "sql_dml": 0}
    cam = ESTADO.get("camara_creada")
    if cam and "ingeniero" in API.tokens:
        try:
            c, _ = API.patch("ingeniero", f"/configuracion/dispositivos-iot/{cam}/desactivar")
            restauracion["camara_desactivada"] = {"id": cam, "http": c}
            if c not in (200, 204):
                restauracion["pendientes"].append(f"cámara {cam} no desactivada (HTTP {c})")
            else:
                cc, bb = API.get("ingeniero", f"/configuracion/dispositivos-iot/{cam}")
                restauracion["verificacion"] = {"http": cc, "es_activo": (bb or {}).get("es_activo")}
        except Exception as exc:  # pragma: no cover - red
            restauracion["pendientes"].append(f"error al desactivar la cámara {cam}: {exc}")
    elif ESTADO.get("camara_reutilizada"):
        restauracion["camara_desactivada"] = (
            f"no aplica: se reutilizó la cámara {ESTADO['camara_reutilizada']}, que ya existía "
            "activa y no la creó este RUN")
    E["restauracion"] = restauracion
    guardar()
    _escribir_manifest()


def _escribir_manifest():
    fuente = BASE_DIR / "test_g141_v2.py"
    artefactos = [{"archivo": p.name, "bytes": p.stat().st_size,
                   "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
                  for p in sorted(RUN_DIR.rglob("*"))
                  if p.is_file() and p.name != "automation_manifest.json"]
    (RUN_DIR / "automation_manifest.json").write_text(json.dumps({
        "run_id": RUN_ID, "grupo": GRUPO, "caso": CASO, "ambiente": "TEST",
        "herramienta": "pytest", "newman": "NO APLICA",
        "informe": "TC-M09-G141_reevaluacion_V2.md",
        "automatizacion": [{"path": f"EvaluacionV2/automation/{fuente.name}",
                            "funcion": ("automatización oficial de TC-M09-287: reemplazo de la "
                                        "línea base VISION del par (área, especie)"),
                            "bytes": fuente.stat().st_size,
                            "sha256": hashlib.sha256(fuente.read_bytes()).hexdigest()}],
        "artefactos_resultados": artefactos,
    }, indent=2, ensure_ascii=False), encoding="utf-8")


# ══════════════════════════════════════════════════════════════════════════════
# PRECHECK
# ══════════════════════════════════════════════════════════════════════════════

def test_01_rama_y_baseline():
    rama = subprocess.run(["git", "branch", "--show-current"], cwd=str(REPO_DIR),
                          capture_output=True, text=True).stdout.strip()
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(REPO_DIR),
                            capture_output=True, text=True).stdout.strip()
    estado = subprocess.run(["git", "status", "--short"], cwd=str(REPO_DIR),
                            capture_output=True, text=True).stdout.strip()
    E["git"] = {"rama": rama, "commit": commit, "status_short": estado.splitlines()}
    assert rama == "qa/juan-esteban-segunda-evaluacion-rf24-v2.0", f"rama inesperada: {rama}"
    baseline = CASE_DIR / "RESULTADOS" / "run-20261007-102458"
    E["baseline_primera_evaluacion"] = {
        "run_id": "run-20261007-102458",
        "existe": baseline.is_dir(),
        "archivos": sorted(p.name for p in baseline.iterdir()) if baseline.is_dir() else [],
        "resultado_previo": {"TC-M09-287": "BLOQUEADO / NO VERIFICABLE",
                             "TC-M09-G141": "BLOQUEADO / NO VERIFICABLE"},
        "solo_lectura": True,
    }
    ESTADO["rama"] = True


def test_02_openapi_y_actor():
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

    API.login(*ING, "ingeniero")
    c, _ = API.get("ingeniero", "/sesiones/me/permisos")
    assert c == 200, f"permisos del Ingeniero HTTP {c}"
    E["actor"] = {"rol": "Ingeniero de Campo", "correo": ING[0], "login": "PASS",
                  "uso": "actor funcional único del caso"}
    ESTADO["precheck"] = True


def test_03_resolver_N():
    requiere("precheck")
    fuente = REPO_DIR / "src/configuration/domain/entities/linea_base_vision.py"
    texto = fuente.read_text(encoding="utf-8")
    m = re.search(r"min_observaciones:\s*int\s*=\s*(\d+)", texto)
    assert m, "no se pudo leer min_observaciones de ParametrosLineaBase"
    uso = (REPO_DIR / "src/configuration/application/use_cases/sensores/calibrar_vision_use_case.py"
           ).read_text(encoding="utf-8")
    assert "parametros: ParametrosLineaBase = ParametrosLineaBase()" in uso, \
        "el caso de uso ya no toma los parámetros por defecto; reconfirmar N"
    ESTADO["N"] = int(m.group(1))
    E["N"] = {
        "valor": ESTADO["N"],
        "fuente": ("ParametrosLineaBase.min_observaciones — "
                   "src/configuration/domain/entities/linea_base_vision.py"),
        "inyeccion": "el caso de uso lo toma por defecto; no se modificó nada en TEST",
        "commit": E["git"]["commit"],
    }
    ESTADO["resolver_n"] = True


def test_04_bd_complementaria():
    """La BD es evidencia complementaria (§4): se registra y nunca bloquea."""
    requiere("resolver_n")
    res = select([
        ("privilegios", """
            SELECT 'modulo3.observaciones_vision' AS tabla,
                   has_table_privilege('member_qa','modulo3.observaciones_vision','SELECT') AS puede_select
            UNION ALL SELECT 'modulo9.calibraciones_vision',
                   has_table_privilege('member_qa','modulo9.calibraciones_vision','SELECT')
            UNION ALL SELECT 'modulo9.lineas_base_vision',
                   has_table_privilege('member_qa','modulo9.lineas_base_vision','SELECT')"""),
    ])
    privs = {f["tabla"]: f["puede_select"] for f in res.get("privilegios", [])
             if isinstance(f, dict)}
    disponible = bool(privs) and all(privs.values())
    ESTADO["bd_ok"] = disponible
    E["bd_complementaria"] = {
        "rol_en_la_matriz": "evidencia COMPLEMENTARIA; no condiciona la ejecución",
        "host": DB["host"], "puerto": DB["port"], "base": DB["dbname"], "usuario": DB["user"],
        "sesion": "READ ONLY — solo SELECT, 0 DML",
        "privilegios_select": privs,
        "error_de_conexion": res.get("_error"),
        "BD_COMPLEMENTARIA": "DISPONIBLE" if disponible else "NO DISPONIBLE",
        "motivo": None if disponible else "member_qa sin privilegio SELECT sobre las tablas VISION",
    }
    if not disponible:
        E["limitaciones"].append({
            "tema": "BD complementaria",
            "detalle": ("member_qa no tiene SELECT sobre las tablas VISION; el contraste de BD no "
                        "se pudo hacer. No es bug funcional ni bloquea el caso (§4 y §40)."),
            "responsable": "DBA / Implementación",
        })
    ESTADO["bd"] = True


# ══════════════════════════════════════════════════════════════════════════════
# L1 — línea base vigente previa
# ══════════════════════════════════════════════════════════════════════════════

def test_05_resolver_A1_y_L1():
    """§12 a §15: se resuelve dinámicamente un área con línea base VISION vigente."""
    requiere("bd")
    # RF-20 lista las áreas por finca (`finca_id` es obligatorio), así que primero se resuelven
    # las fincas del Ingeniero y luego sus áreas activas.
    cf, fincas = API.get("ingeniero", "/configuracion/fincas")
    assert cf == 200, f"listado de fincas HTTP {cf}"
    ids_fincas = [f["id_finca"] for f in fincas.get("items", []) if f.get("es_activo")]
    items: list[dict] = []
    for id_finca in ids_fincas:
        c, lista = API.get("ingeniero",
                           f"/configuracion/infraestructuras?finca_id={id_finca}&solo_activas=true",
                           timeout=200)
        assert c == 200, f"listado de áreas de la finca {id_finca} HTTP {c}"
        items.extend(lista.get("items", []))
    candidatas = [a for a in items
                  if a.get("es_activo")
                  and a.get("especie_id") is not None
                  and str(a.get("tipo_modelo_asignado")) in POBLACIONALES]
    # Orden determinista: de la más reciente a la más antigua, para apoyarse en el fixture QA
    # de esta campaña antes que en datos compartidos más viejos.
    candidatas.sort(key=lambda a: a["id_infraestructura"], reverse=True)

    evaluadas, elegida, l1 = [], None, None
    for a in candidatas:
        area = a["id_infraestructura"]
        cl, lb = API.get("ingeniero",
                         f"/configuracion/calibraciones-vision/linea-base?area_id={area}")
        evaluadas.append({"area_id": area, "nombre": a.get("nombre_infraestructura"),
                          "especie_id": a.get("especie_id"),
                          "tipo_modelo_asignado": a.get("tipo_modelo_asignado"),
                          "linea_base_http": cl,
                          "id_calibracion_vision": lb.get("id_calibracion_vision") if cl == 200 else None})
        if cl == 200 and elegida is None:
            elegida, l1 = a, lb
    E["resolucion_A1"] = {
        "fincas_del_ingeniero": ids_fincas,
        "areas_activas_encontradas": len(items),
        "areas_poblacionales_activas_evaluadas": evaluadas,
        "criterio": ("activa, con especie, tipo_modelo_asignado del paradigma POBLACIONAL, "
                     "accesible para el Ingeniero y con GET linea-base en 200"),
        "nota_tc275": ("§14: no se exige que L1 siga siendo el id creado por TC-M09-275; "
                       "basta una L1 vigente y verificable por API"),
    }
    assert elegida is not None, (
        "ninguna área poblacional del Ingeniero tiene línea base VISION vigente; habría que "
        "crear una L1 de setup (§16)")

    ESTADO["a1"] = elegida["id_infraestructura"]
    ESTADO["especie"] = elegida["especie_id"]
    ESTADO["L1_ID"] = l1["id_calibracion_vision"]
    ESTADO["L1_VALORES"] = (l1.get("linea_base") or {}).get("valores")
    ESTADO["L1_FECHA"] = l1.get("fecha_publicacion")
    E["A1"] = {
        "id": ESTADO["a1"], "nombre": elegida.get("nombre_infraestructura"),
        "especie_id": ESTADO["especie"], "tipo_modelo_asignado": elegida.get("tipo_modelo_asignado"),
        "paradigma": "POBLACIONAL", "es_activo": elegida.get("es_activo"),
        "finca_id": elegida.get("id_finca"),
        "accesible_para_el_ingeniero": True,
    }
    E["L1"] = {
        "fuente": "REUTILIZADA — no se creó ninguna calibración de setup",
        "id_calibracion_vision": ESTADO["L1_ID"],
        "area_id": l1.get("area_id"), "especie_id": l1.get("especie_id"),
        "valores": ESTADO["L1_VALORES"],
        "componentes_no_calibrables": (l1.get("linea_base") or {}).get("componentes_no_calibrables"),
        "fecha_publicacion": ESTADO["L1_FECHA"],
    }
    assert l1.get("especie_id") == ESTADO["especie"], (l1, ESTADO["especie"])
    assert ESTADO["L1_VALORES"], "la línea base L1 no trae valores por componente"
    ESTADO["l1"] = True


def test_06_historial_pre_y_ventana_W2():
    """§18 y §23: W2 posterior a la ventana de L1, sin solapamiento, cerrada y en el pasado."""
    requiere("l1")
    c, hist = API.get("ingeniero", f"/configuracion/calibraciones-vision?area_id={ESTADO['a1']}")
    assert c == 200, f"historial PRE HTTP {c}"
    items = hist.get("items", [])
    ESTADO["hist_pre_ids"] = [i["id_calibracion_vision"] for i in items]
    ventanas = []
    for i in items:
        v = i.get("ventana_observacion") or {}
        if v.get("inicio") and v.get("fin"):
            ventanas.append({"id_calibracion_vision": i["id_calibracion_vision"],
                             "inicio": v["inicio"], "fin": v["fin"]})
    E["historial_PRE"] = {"http": c, "total": hist.get("total"),
                          "ids": ESTADO["hist_pre_ids"],
                          "ventanas_usadas": ventanas,
                          "L1_en_historial": ESTADO["L1_ID"] in ESTADO["hist_pre_ids"]}

    ahora = datetime.datetime.now(datetime.timezone.utc)
    ultimo_fin = max((parse(v["fin"]) for v in ventanas), default=ahora - datetime.timedelta(days=60))
    # Determinista: 15 días después del último fin conocido, a medianoche, con 6 h de duración.
    inicio = (ultimo_fin + datetime.timedelta(days=15)).replace(
        hour=0, minute=0, second=0, microsecond=0)
    fin = inicio + datetime.timedelta(hours=6)
    if fin >= ahora:
        # Si el último fin estuviera demasiado cerca del presente, se retrocede a una
        # ventana claramente cerrada y aún posterior a la de L1.
        inicio = (ahora - datetime.timedelta(days=2)).replace(
            hour=0, minute=0, second=0, microsecond=0)
        fin = inicio + datetime.timedelta(hours=6)
    ESTADO["W2"] = (iso(inicio), iso(fin))
    solapa = [v for v in ventanas if not (parse(v["fin"]) < inicio or parse(v["inicio"]) > fin)]
    E["W2"] = {
        "inicio": ESTADO["W2"][0], "fin": ESTADO["W2"][1],
        "posterior_a_la_ventana_de_L1": True,
        "ultimo_fin_conocido_del_area": iso(ultimo_fin),
        "solapamientos_detectados": solapa,
        "cerrada_y_en_el_pasado": True,
    }
    assert not solapa, f"W2 se solapa con una ventana ya usada por el área: {solapa}"
    assert fin < ahora, "W2 debe estar cerrada y en el pasado"
    assert inicio > ultimo_fin, "W2 debe ser posterior a la ventana usada por L1"
    ESTADO["w2"] = True


def test_07_camara_para_W2():
    """§17: cámara QA activa y exclusiva del área; si no hay ninguna activa, se crea por API."""
    requiere("w2")
    c, lista = API.get("ingeniero", "/configuracion/dispositivos-iot", timeout=240)
    assert c == 200, f"listado de dispositivos HTTP {c}"
    del_area = [d for d in lista["items"] if d.get("id_infraestructura") == ESTADO["a1"]]
    activas = [d for d in del_area if d.get("es_activo") and d.get("categoria") == "CAMARA"]
    E["camara"] = {
        "camaras_del_area": [{"id": d["id_dispositivo_iot"], "categoria": d.get("categoria"),
                              "es_activo": d.get("es_activo"), "fps": d.get("fps")}
                             for d in del_area],
        "activas_preexistentes": [d["id_dispositivo_iot"] for d in activas],
    }
    # Se registra una cámara nueva y exclusiva del RUN, que es lo que da el aislamiento de W2
    # sin depender de la BD (§19): una cámara recién creada no puede tener observaciones
    # anteriores, así que el `duplicadas = 0` de la ingesta es concluyente. Si hubiera cámaras
    # activas previas en el área, se registran en la evidencia pero no se usan.
    E["camara"]["decision"] = (
        "cámara NUEVA y exclusiva del RUN"
        + (f"; había activas previas en el área ({[d['id_dispositivo_iot'] for d in activas]}), "
           "no se usaron para no arrastrar observaciones históricas a W2"
           if activas else
           "; no había ninguna cámara activa en el área (las de los grupos anteriores quedaron "
           "inactivas y RF-21 no publica reactivación)"))
    sufijo = RUN_ID.replace("run-", "")
    serial = f"QA-M09-G141-CAM-{sufijo}"
    cuerpo = {"serial": serial,
              "descripcion": f"QA {GRUPO} camara VISION del RUN {RUN_ID}",
              "id_infraestructura": ESTADO["a1"], "id_tipo_dispositivo": TIPO_CAMARA_VISION,
              "es_activo": True, "resolucion": "1920x1080", "fps": 30,
              "area_cobertura_m2": "50.00"}
    c, cam = API.post("ingeniero", "/configuracion/dispositivos-iot", cuerpo)
    assert c in (200, 201), f"registro de cámara HTTP {c}: {sanear(cam)}"
    ESTADO["camara"] = cam["id_dispositivo_iot"]
    ESTADO["camara_creada"] = cam["id_dispositivo_iot"]
    ESTADO["serial"] = serial
    ESTADO["fps"] = cam.get("fps") or 30
    E["camara"]["creada"] = {
        "id": ESTADO["camara"], "serial": "[SERIAL REDACTED]",
        "categoria": cam.get("categoria"), "es_activo": cam.get("es_activo"),
        "fps_nominal": cam.get("fps"), "resolucion": cam.get("resolucion"),
        "id_infraestructura": cam.get("id_infraestructura"),
    }
    assert cam.get("categoria") == "CAMARA" and cam.get("es_activo") is True
    assert cam.get("id_infraestructura") == ESTADO["a1"], "la cámara no quedó asociada a A1"
    ESTADO["cam"] = True


def test_08_observaciones_W2_distintas_de_L1():
    """§20 a §22: exactamente N aptas, con vectores deliberadamente distintos de L1."""
    requiere("cam", "N")
    n = ESTADO["N"]
    l1 = ESTADO["L1_VALORES"] or {}
    # Los componentes de W2 son los mismos que los de L1, para que la comparación sea
    # componente a componente, pero con valores lejanos: así L2 no puede salir igual a L1
    # por construcción del dataset.
    objetivo: dict[str, float] = {}
    for comp in sorted(l1):
        base = float(l1[comp])
        candidato = 20.0 if comp == "densidad_actividad" else 8.0
        # Si el valor de referencia estuviera cerca del de L1, se aleja de forma determinista.
        objetivo[comp] = candidato if abs(candidato - base) >= max(1.0, abs(base) * 0.5) \
            else round(base * 3 + 17.0, 4)
    assert objetivo, "L1 no declara componentes; no se puede construir un dataset comparable"

    ini, fin = ESTADO["W2"]
    base_dt = parse(ini)
    observaciones = []
    for i in range(n):
        ts = iso(base_dt + datetime.timedelta(minutes=5 * i))
        # Variación determinista y pequeña: ni aleatoria ni suficiente para mover la mediana.
        vals = {c: round(v + (i % 3) * 0.01, 4) for c, v in objetivo.items()}
        observaciones.append(obs_apta(ts, vals.get("densidad_actividad", 20.0),
                                      vals.get("tasa_movimiento", 8.0), ESTADO["fps"]))
    cuerpo = {"device_id": ESTADO["camara"], "access_key": ESTADO["serial"],
              "area_id": ESTADO["a1"], "observaciones": observaciones}
    c, b = API.post_vision(cuerpo, "lote_w2")
    aptas = [o for o in b.get("observaciones", []) if o.get("apto_para_ia")]
    E["W2"]["dataset"] = {
        "componentes_objetivo": objetivo,
        "L1_valores_de_referencia": l1,
        "n_enviadas": n, "paso_minutos": 5,
        "calidad": {"cobertura_ventana": "1.0000", "n_tracks": 20, "n_tracks_perdidos": 0,
                    "fps_efectivo": f"{int(ESTADO['fps'])}.00", "estado_calibracion": "CALIBRADA"},
        "variacion": "determinista, (i % 3) * 0.01; sin aleatoriedad",
    }
    E["W2"]["ingesta"] = {
        "http": c, "total": b.get("total"), "aceptadas": b.get("aceptadas"),
        "duplicadas": b.get("duplicadas"), "aptas": len(aptas),
        "indices_distintos": sorted({o["indice_calidad"] for o in b.get("observaciones", [])}),
        "clasificaciones": sorted({o["clasificacion_calidad"] for o in b.get("observaciones", [])}),
        "ids": [o["id_observacion_vision"] for o in b.get("observaciones", [])],
    }
    assert c in (200, 201), f"ingesta de W2 HTTP {c}: {sanear(b)}"
    assert b["total"] == n and b["aceptadas"] == n, f"ingesta: {b['total']}/{b['aceptadas']} de {n}"
    assert b["duplicadas"] == 0, (
        "había observaciones previas en W2; la ventana no está limpia y no se ejecuta TC-287")
    assert len(aptas) == n, f"se requieren exactamente {n} aptas; hay {len(aptas)}"
    ESTADO["lote"] = True


def test_09_snapshot_PRE():
    """§23: la vigencia PRE se captura inmediatamente antes del POST objetivo."""
    requiere("lote")
    c, lb = API.get("ingeniero",
                    f"/configuracion/calibraciones-vision/linea-base?area_id={ESTADO['a1']}")
    assert c == 200, f"línea base PRE HTTP {c}"
    ch, hist = API.get("ingeniero", f"/configuracion/calibraciones-vision?area_id={ESTADO['a1']}")
    assert ch == 200, f"historial PRE HTTP {ch}"
    ESTADO["PRE_BASELINE_ID"] = lb["id_calibracion_vision"]
    ESTADO["PRE_VALORES"] = (lb.get("linea_base") or {}).get("valores")
    E["snapshot_PRE"] = {
        "http": c,
        "PRE_BASELINE_ID": ESTADO["PRE_BASELINE_ID"],
        "PRE_ESPECIE_ID": lb.get("especie_id"),
        "PRE_LINEA_BASE": lb.get("linea_base"),
        "PRE_FECHA_PUBLICACION": lb.get("fecha_publicacion"),
        "historial_ids": [i["id_calibracion_vision"] for i in hist.get("items", [])],
        "coincide_con_L1": ESTADO["PRE_BASELINE_ID"] == ESTADO["L1_ID"],
    }
    assert ESTADO["PRE_BASELINE_ID"] == ESTADO["L1_ID"], (
        f"la vigencia PRE cambió entre la resolución de L1 y el POST: "
        f"{ESTADO['L1_ID']} -> {ESTADO['PRE_BASELINE_ID']}")
    ESTADO["pre"] = True


# ══════════════════════════════════════════════════════════════════════════════
# TC-M09-287 — segundo cálculo
# ══════════════════════════════════════════════════════════════════════════════

def test_10_post_objetivo():
    requiere("pre")
    ini, fin = ESTADO["W2"]
    cuerpo = {"modo_calibracion": "VISION", "area_id": ESTADO["a1"],
              "ventana_observacion": {"inicio": ini, "fin": fin},
              "observaciones": "QA TC-M09-287 reemplazo línea base",
              "fecha_calibracion": datetime.datetime.now(datetime.timezone.utc).isoformat()}
    c, b = API.post_calibracion(cuerpo, "tc287", "objetivo")
    E["post_objetivo"] = {"request": cuerpo, "http": c, "response": b, "http_esperado": "2xx"}
    assert 200 <= c < 300, f"TC-M09-287 esperaba 2xx y obtuvo {c}: {sanear(b)}"
    assert b["estado"] == "EXITOSA", f"estado {b['estado']}"
    assert b["etapa_fallo"] is None, b["etapa_fallo"]
    assert b["linea_base"] is not None, "la calibración no devolvió línea base"
    assert b["especie_id"] == ESTADO["especie"], (b["especie_id"], ESTADO["especie"])
    assert b["n_observaciones_validas"] >= ESTADO["N"], (
        f"n_observaciones_validas {b['n_observaciones_validas']} < N {ESTADO['N']}")
    ESTADO["L2_ID"] = b["id_calibracion_vision"]
    ESTADO["L2_VALORES"] = b["linea_base"]["valores"]
    E["post_objetivo"]["resumen"] = {
        "L2_CAL_ID": ESTADO["L2_ID"], "estado": b["estado"], "especie_id": b["especie_id"],
        "n_observaciones": b["n_observaciones"],
        "n_observaciones_validas": b["n_observaciones_validas"],
        "iteraciones": b.get("iteraciones"), "origen_disparo": b.get("origen_disparo"),
        "id_usuario": b.get("id_usuario"), "valores": ESTADO["L2_VALORES"],
    }
    ESTADO["post"] = True


def test_11_linea_base_POST_y_reemplazo():
    """§26 a §28: la vigencia pasa de L1 a L2 y los valores del GET coinciden con el POST."""
    requiere("post")
    c, lb = API.get("ingeniero",
                    f"/configuracion/calibraciones-vision/linea-base?area_id={ESTADO['a1']}")
    assert c == 200, f"línea base POST HTTP {c}"
    vigente = lb["id_calibracion_vision"]
    valores = (lb.get("linea_base") or {}).get("valores")
    E["linea_base_POST"] = {
        "http": c, "id_calibracion_vision": vigente, "especie_id": lb.get("especie_id"),
        "linea_base": lb.get("linea_base"), "fecha_publicacion": lb.get("fecha_publicacion"),
    }
    E["comparacion_L1_L2"] = {
        "L1_ID": ESTADO["L1_ID"], "L2_ID": ESTADO["L2_ID"],
        "L1_VALORES": ESTADO["L1_VALORES"], "L2_VALORES": ESTADO["L2_VALORES"],
        "PRE_vigente": ESTADO["PRE_BASELINE_ID"], "POST_vigente": vigente,
        "L1_distinta_de_L2": "SÍ" if ESTADO["L2_ID"] != ESTADO["L1_ID"] else "NO",
        "GET_apunta_a_L2": "SÍ" if vigente == ESTADO["L2_ID"] else "NO",
        "POST_igual_a_GET": "SÍ" if igual(valores, ESTADO["L2_VALORES"]) else "NO",
        "L1_ya_no_vigente": "SÍ" if vigente != ESTADO["L1_ID"] else "NO",
        "valores_L2_distintos_de_L1": "SÍ" if not igual(ESTADO["L2_VALORES"], ESTADO["L1_VALORES"])
                                      else "NO",
        "reemplazo_confirmado": "SÍ" if (vigente == ESTADO["L2_ID"]
                                         and ESTADO["L2_ID"] != ESTADO["L1_ID"]) else "NO",
    }
    assert ESTADO["L2_ID"] != ESTADO["L1_ID"], (
        f"la calibración nueva reutilizó el id de L1: {ESTADO['L2_ID']}")
    assert vigente == ESTADO["L2_ID"], (
        f"la línea base vigente apunta a {vigente} y no a L2 ({ESTADO['L2_ID']}): el segundo "
        "cálculo no reemplazó la línea base")
    assert vigente != ESTADO["L1_ID"], "L1 sigue siendo la línea base vigente"
    assert igual(valores, ESTADO["L2_VALORES"]), (
        f"los valores del GET no coinciden con los del POST: {valores} vs {ESTADO['L2_VALORES']}")
    assert not igual(ESTADO["L2_VALORES"], ESTADO["L1_VALORES"]), (
        "L2 tiene los mismos valores que L1 pese a que W2 se construyó con un dataset distinto; "
        "revisar el fixture antes de concluir nada (§34)")
    ESTADO["reemplazo"] = True


def test_12_historial_POST():
    """§29: L2 debe figurar como EXITOSA. La conservación de L1 se registra, no se exige."""
    requiere("reemplazo")
    c, hist = API.get("ingeniero", f"/configuracion/calibraciones-vision?area_id={ESTADO['a1']}")
    assert c == 200, f"historial POST HTTP {c}"
    items = hist.get("items", [])
    ids = [i["id_calibracion_vision"] for i in items]
    de_l2 = next((i for i in items if i["id_calibracion_vision"] == ESTADO["L2_ID"]), None)
    E["historial_POST"] = {
        "http": c, "total": hist.get("total"), "ids": ids,
        "L2_en_historial": "SÍ" if de_l2 else "NO",
        "L2": {k: de_l2.get(k) for k in
               ("id_calibracion_vision", "estado", "etapa_fallo", "n_observaciones",
                "n_observaciones_validas", "iteraciones", "origen_disparo", "id_usuario",
                "ventana_observacion")} if de_l2 else None,
        "L1_conservada_en_historial": "SÍ" if ESTADO["L1_ID"] in ids else "NO",
        "nota": ("la matriz no exige conservación histórica de L1 (§29 y §39): su presencia se "
                 "registra como evidencia y su ausencia no rechazaría el caso"),
    }
    assert de_l2 is not None, f"L2 ({ESTADO['L2_ID']}) no aparece en el historial"
    assert de_l2["estado"] == "EXITOSA", de_l2["estado"]
    ESTADO["historial"] = True


def test_13_bd_complementaria_post():
    """§30: contraste opcional. Si el SELECT está denegado se registra y se continúa."""
    requiere("historial")
    res = select([
        ("linea_base_vigente", f"""
            SELECT id_infraestructura, id_especie, id_calibracion_vision, json_valor
            FROM modulo9.lineas_base_vision
            WHERE id_infraestructura = {ESTADO['a1']} AND id_especie = {ESTADO['especie']}"""),
        ("calibracion_L2", f"""
            SELECT id_calibracion_vision, estado, cantidad_observaciones,
                   cantidad_observaciones_validas, iteraciones
            FROM modulo9.calibraciones_vision
            WHERE id_calibracion_vision = {ESTADO['L2_ID']}"""),
    ])
    contraste = {"disponible": ESTADO.get("bd_ok", False), "resultado": res,
                 "contradice_a_la_api": "NO"}
    if ESTADO.get("bd_ok"):
        lb = (res.get("linea_base_vigente") or [{}])[0]
        cal = (res.get("calibracion_L2") or [{}])[0]
        contraste["linea_base_apunta_a_L2"] = lb.get("id_calibracion_vision") == ESTADO["L2_ID"]
        contraste["calibracion_L2_exitosa"] = cal.get("estado") == "EXITOSA"
        assert lb.get("id_calibracion_vision") == ESTADO["L2_ID"], lb
        assert cal.get("estado") == "EXITOSA", cal
    else:
        contraste["nota"] = ("NO DISPONIBLE: member_qa sin SELECT sobre las tablas VISION. "
                             "El oráculo del caso es la API (§3 y §4); no se bloquea ni se "
                             "presenta ninguna lectura de API como si fuera un SELECT.")
    E["bd_complementaria"]["contraste_post"] = contraste
    ESTADO["contraste"] = True


def test_14_cierre():
    requiere("contraste")
    comp = E["comparacion_L1_L2"]
    E["criterio_aprobacion"] = [
        {"n": 1, "criterio": "L1 vigente PRE verificable por API",
         "cumple": E["snapshot_PRE"]["coincide_con_L1"]},
        {"n": 2, "criterio": "W2 posterior y con >= N observaciones aptas",
         "cumple": E["W2"]["ingesta"]["aptas"] >= ESTADO["N"] and E["W2"]["posterior_a_la_ventana_de_L1"]},
        {"n": 3, "criterio": "ingesta con aceptadas = esperadas y duplicadas = 0",
         "cumple": (E["W2"]["ingesta"]["aceptadas"] == ESTADO["N"]
                    and E["W2"]["ingesta"]["duplicadas"] == 0)},
        {"n": 4, "criterio": "POST del segundo cálculo 2xx",
         "cumple": 200 <= E["post_objetivo"]["http"] < 300},
        {"n": 5, "criterio": "estado EXITOSA",
         "cumple": E["post_objetivo"]["resumen"]["estado"] == "EXITOSA"},
        {"n": 6, "criterio": "se obtiene L2_CAL_ID",
         "cumple": bool(ESTADO["L2_ID"])},
        {"n": 7, "criterio": "GET línea-base POST apunta a L2_CAL_ID",
         "cumple": comp["GET_apunta_a_L2"] == "SÍ"},
        {"n": 8, "criterio": "L2_CAL_ID != L1_ID", "cumple": comp["L1_distinta_de_L2"] == "SÍ"},
        {"n": 9, "criterio": "la API ya no presenta L1 como vigente",
         "cumple": comp["L1_ya_no_vigente"] == "SÍ"},
        {"n": 10, "criterio": "valores del GET L2 iguales a los del POST",
         "cumple": comp["POST_igual_a_GET"] == "SÍ"},
        {"n": 11, "criterio": "L2 aparece en el historial",
         "cumple": E["historial_POST"]["L2_en_historial"] == "SÍ"},
        {"n": 12, "criterio": "la BD, si está disponible, no contradice la API",
         "cumple": E["bd_complementaria"]["contraste_post"]["contradice_a_la_api"] == "NO"},
    ]
    todos = all(c["cumple"] for c in E["criterio_aprobacion"])
    E["resultado"] = {
        "TC-M09-287": "APROBADO" if todos else "RECHAZADO",
        "TC-M09-G141": "APROBADO" if todos else "RECHAZADO",
        "incidencia_requerida": "NO" if todos else "SÍ",
        "BD_COMPLEMENTARIA": E["bd_complementaria"]["BD_COMPLEMENTARIA"],
        "nota_bd": ("la ausencia de SELECT de QA no es incidencia funcional y no bloqueó el "
                    "caso (§4 y §40)"),
    }
    E["seguridad"] = {
        "credenciales_persistidas": "NO",
        "serial_access_key_persistido": "NO — redactado por patrón, solo en memoria",
        "sql_dml_en_test": 0,
        "sesion_bd": "READ ONLY",
        "baseline_primera_evaluacion_modificada": "NO",
    }
    assert E["presupuesto"]["post_calibracion_objetivo"] == 1, E["presupuesto"]
    assert E["presupuesto"]["post_calibracion_setup"] == 0, E["presupuesto"]
    assert E["presupuesto"]["reintentos"] == 0, E["presupuesto"]
    guardar()
    assert todos, [c for c in E["criterio_aprobacion"] if not c["cumple"]]
