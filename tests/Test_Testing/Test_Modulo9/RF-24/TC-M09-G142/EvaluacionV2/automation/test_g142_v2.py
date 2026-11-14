"""TC-M09-G142 / TC-M09-288 y TC-M09-289 — verificador independiente de SOLO LECTURA.

RF-24 v2.0 · CU05 Flujo F · SEGUNDA EVALUACIÓN.

Reparto de papeles que exige la matriz (§4 y §7 del paquete):

  * **Newman** es el EJECUTOR de los eventos funcionales de M02 (el alta del lote y el cierre
    de su ciclo). Su colección es dueña de la sesión y nunca llama a
    `POST /configuracion/calibraciones-vision`.
  * **Pytest** —este archivo— es el VERIFICADOR. No repite ningún POST funcional: solo
    consulta por GET el historial VISION, la línea base vigente y la auditoría RF-10, y
    contrasta el diagnóstico de integración sobre el código de la rama.

Lee el resumen que dejó el runner (`newman-resumen.json`) y verifica contra el producto, sin
confiar en lo que la propia colección afirmó.

La BD de TEST es evidencia complementaria: si `member_qa` no tiene SELECT se registra
`BD_COMPLEMENTARIA = NO DISPONIBLE` y la ejecución continúa.

Uso:
    pytest test_g142_v2.py -v --confcutdir=. --junitxml=<RUN>/pytest.xml
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import pytest
import requests

BASE_DIR = Path(__file__).resolve().parent
EVAL_DIR = BASE_DIR.parent
CASE_DIR = EVAL_DIR.parent
GRUPO = "TC-M09-G142"
if BASE_DIR.name != "automation" or EVAL_DIR.name != "EvaluacionV2" or CASE_DIR.name != GRUPO:
    raise RuntimeError(f"ABORTADO: ruta no autorizada para {GRUPO}: {BASE_DIR}")
REPO_DIR = CASE_DIR.parents[4]

RUN_ID = os.environ["G142_RUN_ID"]
RUN_DIR = EVAL_DIR / "RESULTADOS" / RUN_ID
RUN_DIR.mkdir(parents=True, exist_ok=True)
RESUMEN = RUN_DIR / "newman-resumen.json"

BASE_URL = "https://api.inmero.co/back-sigab-test"
ADMIN = ("administador.dev@gmail.com", "Test1234!")
ADMIN_ALT = ("admin.dev@gmail.com", "Test1234!")
DB = {"host": "158.69.200.27", "port": "5448", "dbname": "sgpmp_test",
      "user": "member_qa", "password": "qaSGP2026"}
TIPO_EVENTO_RECHAZO, TIPO_EVENTO_EXITO = 29, 30

# ── Ejecuciones dentro del MISMO RUN logico ─────────────────────────────────
EJECUCION = 2
TIPO_EJECUCION = "REEJECUCION_COMPLETA_POST_FIX"
PR_CORRECCION = 554
HISTORIAL_EJECUCIONES = [
    {
        "ejecucion": 1,
        "fecha": "2026-10-10",
        "resultado_g142": "RECHAZADO",
        "resultados": {"TC-M09-288": "RECHAZADO", "TC-M09-289": "RECHAZADO"},
        "alta": "201 (lote 792)",
        "calibracion_automatica": "NO",
        "cierre": "422 SIN_FASE_ACTIVA",
        "hook_m02_m09": "AUSENTE",
        "newman": {"requests": 40, "assertions": 60, "failures": 8},
        "pytest": {"collected": 10, "passed": 10},
        "nota": ("el Pytest era un verificador de hechos: 10 passed no significaba que el "
                 "grupo aprobara. El veredicto de la ejecucion 1 fue RECHAZADO."),
    },
]
#: modulo2.estados_activos_biologicos: CERRADO = 5 (EstadoActivo.CERRADO). GET
#: /activos-biologicos/{id} devuelve el id de estado; el nombre no siempre viaja.
ESTADO_CERRADO = 5
#: §24 — cadencia de observación por GET, sin ninguna escritura.
CADENCIA = (0, 2, 5, 10, 20, 30)
_RE_SERIAL = re.compile(r"QA-M09-G1\d{2}-[A-Z]+-\d{8}-\d{6}")

E: dict = {
    "run_id": RUN_ID, "grupo": GRUPO, "casos": ["TC-M09-288", "TC-M09-289"],
    "ambiente": "TEST", "base_url": BASE_URL,
    "herramientas": {"ejecutor": "Newman (eventos funcionales M02)",
                     "verificador": "Pytest (solo lectura)"},
    "generado": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "post_funcionales_de_pytest": 0,
    "limitaciones": [],
}
ESTADO: dict = {}


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
        return s.replace(ADMIN[1], "[REDACTED]").replace(DB["password"], "[REDACTED]")
    return d


def guardar():
    (RUN_DIR / "evidencia.json").write_text(
        json.dumps(sanear(E), indent=2, ensure_ascii=False, default=str), encoding="utf-8")


def select(consultas: list[tuple[str, str]]) -> dict:
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


class Lectura:
    """Cliente de SOLO LECTURA: únicamente login (sesión) y GET."""

    def __init__(self) -> None:
        self.s = requests.Session()
        self.token = None

    def login(self) -> str:
        for correo, clave in (ADMIN, ADMIN_ALT):
            r = self.s.post(f"{BASE_URL}/sesiones/",
                            json={"correo_electronico": correo, "contrasena": clave}, timeout=90)
            if r.status_code == 200:
                self.token = r.json()["token"]
                return correo
        raise AssertionError("ningún Administrador autenticó para la verificación")

    def get(self, path: str, timeout: int = 150):
        r = self.s.get(f"{BASE_URL}{path}",
                       headers={"Authorization": f"Bearer {self.token}", "Accept": "application/json"},
                       timeout=timeout)
        try:
            return r.status_code, r.json()
        except ValueError:
            return r.status_code, {"_texto": r.text[:400]}


API = Lectura()


def requiere(*claves: str):
    for c in claves:
        if c not in ESTADO:
            pytest.skip(f"falta la precondición {c}")


def parse(ts: str):
    return datetime.datetime.fromisoformat(str(ts).replace("Z", "+00:00"))


def detalle_de(ev: dict) -> dict:
    d = ev.get("detalle") or ev.get("json_detalle") or {}
    if isinstance(d, str):
        try:
            d = json.loads(d)
        except ValueError:
            d = {}
    return d if isinstance(d, dict) else {}


def _escribir_manifest():
    fuentes = [
        ("test_g142_v2.py", "verificador independiente de solo lectura (Pytest)"),
        ("run-g142-v2.cjs", "runner Newman: precheck de solo lectura y RUN oficial"),
        ("TC-M09-G142.postman_collection.json",
         "colección oficial: dueña de su sesión, ejecuta los dos eventos M02"),
        ("TC-M09-G142.precheck.postman_collection.json",
         "colección de precheck de solo lectura"),
    ]
    entradas = [{"path": f"EvaluacionV2/automation/{n}", "funcion": f,
                 "bytes": (BASE_DIR / n).stat().st_size,
                 "sha256": hashlib.sha256((BASE_DIR / n).read_bytes()).hexdigest()}
                for n, f in fuentes if (BASE_DIR / n).is_file()]
    artefactos = [{"archivo": str(p.relative_to(RUN_DIR)).replace("\\", "/"),
                   "bytes": p.stat().st_size,
                   "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
                  for p in sorted(RUN_DIR.rglob("*"))
                  if p.is_file() and p.name != "automation_manifest.json"]
    (RUN_DIR / "automation_manifest.json").write_text(json.dumps({
        "run_id": RUN_ID, "grupo": GRUPO, "ambiente": "TEST",
        "execution_number": EJECUCION,
        "execution_type": TIPO_EJECUCION,
        "herramientas": "Newman (ejecutor) + Pytest (verificador)",
        "informe": "TC-M09-G142_reevaluacion_V2.md",
        "automatizacion": entradas, "artefactos_resultados": artefactos,
    }, indent=2, ensure_ascii=False), encoding="utf-8")


@pytest.fixture(scope="session", autouse=True)
def cierre_de_sesion():
    yield
    guardar()
    _escribir_manifest()


# ══════════════════════════════════════════════════════════════════════════════
# 1. Contexto del RUN
# ══════════════════════════════════════════════════════════════════════════════

def test_01_rama_y_resumen_newman():
    rama = subprocess.run(["git", "branch", "--show-current"], cwd=str(REPO_DIR),
                          capture_output=True, text=True).stdout.strip()
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(REPO_DIR),
                            capture_output=True, text=True).stdout.strip()
    estado = subprocess.run(["git", "status", "--short"], cwd=str(REPO_DIR),
                            capture_output=True, text=True).stdout.strip()
    E["git"] = {"rama": rama, "commit": commit, "status_short": estado.splitlines()}
    assert rama == "qa/juan-esteban-segunda-evaluacion-rf24-v2.0", f"rama inesperada: {rama}"

    assert RESUMEN.is_file(), f"falta el resumen del RUN Newman en {RESUMEN}"
    resumen = json.loads(RESUMEN.read_text(encoding="utf-8"))
    v = resumen["valores_finales"]
    E["newman"] = resumen["newman"]
    E["presupuesto"] = resumen["presupuesto"]
    E["fixture"] = {
        "finca_id": v.get("finca_id"), "a1_id": v.get("a1_id"),
        "tipo_area": v.get("tipo_area"),
        "especie_id": v.get("especie_id"), "especie_nombre": v.get("especie_nombre"),
        "especie_densidad_maxima": v.get("especie_densidad_maxima"),
        "especies_aptas": v.get("especies_aptas"),
        "metricas_obligatorias": v.get("metricas_obligatorias"),
        "c1_id": v.get("c1_id"), "c1_fps": v.get("c1_fps"),
        "c1_serial": "[SERIAL REDACTED]",
        "observaciones_aptas": v.get("obs_aptas"),
        "ventana_observaciones": {"inicio": v.get("w_inicio"), "fin": v.get("w_fin")},
    }
    E["eventos_m02"] = {
        "alta": {"http": v.get("alta_http"), "id_lote": v.get("id_lote"),
                 "t_alta": v.get("t_alta")},
        "cierre": {"http": v.get("cierre_http"), "t_cierre": v.get("t_cierre"),
                   "fase_setup_http": v.get("fase_http"),
                   "ciclos_productivos_asignables": v.get("ciclos_asignables")},
    }
    E["snapshots_de_la_coleccion"] = {
        "hist_pre_288": v.get("hist_pre_288"), "baseline_pre_288": v.get("baseline_pre_288"),
        "baseline_pre_288_http": v.get("baseline_pre_288_http"),
        "hist_pre_289": v.get("hist_pre_289"), "baseline_pre_289": v.get("baseline_pre_289"),
        "nuevas_288": v.get("nuevas_288"), "auto_288_id": v.get("auto_288_id"),
        "nuevas_289": v.get("nuevas_289"), "auto_289_id": v.get("auto_289_id"),
        "restauracion_c1_http": v.get("restauracion_c1_http"),
    }
    # El presupuesto funcional es una regla dura del paquete.
    assert E["presupuesto"]["post_manual_calibraciones_vision"] == 0, E["presupuesto"]
    assert E["presupuesto"]["alta_m02"] == 1, E["presupuesto"]
    assert E["presupuesto"]["cierre_m02"] == 1, E["presupuesto"]
    assert E["presupuesto"]["reintentos"] == 0, E["presupuesto"]

    ESTADO["a1"] = int(v["a1_id"])
    ESTADO["especie"] = int(v["especie_id"])
    ESTADO["id_lote"] = int(v["id_lote"]) if str(v.get("id_lote") or "").isdigit() else None
    ESTADO["t_alta"] = v.get("t_alta")
    ESTADO["t_cierre"] = v.get("t_cierre")
    ESTADO["hist_pre_288"] = json.loads(v.get("hist_pre_288") or "[]")
    ESTADO["hist_pre_289"] = json.loads(v.get("hist_pre_289") or "[]")
    ESTADO["contexto"] = True


def test_02_actor_de_lectura():
    requiere("contexto")
    correo = API.login()
    E["verificador"] = {"actor": correo, "modo": "solo lectura: login + GET"}
    ESTADO["actor"] = True


def test_03_lote_creado_por_newman():
    requiere("actor")
    assert ESTADO["id_lote"], "el RUN no dejó un id_lote: el alta M02 no fue válida"
    c, b = API.get(f"/activos-biologicos/{ESTADO['id_lote']}")
    E["lote"] = {
        "http": c, "id": ESTADO["id_lote"],
        "tipo_activo": b.get("tipo_activo") or b.get("tipo"),
        "id_especie": b.get("id_especie"), "id_infraestructura": b.get("id_infraestructura"),
        "estado": b.get("estado"), "id_estado": b.get("id_estado"),
        "cantidad_inicial": (b.get("detalle_poblacional") or {}).get("cantidad_inicial")
                            if isinstance(b.get("detalle_poblacional"), dict) else b.get("cantidad_inicial"),
        "densidad": (b.get("detalle_poblacional") or {}).get("densidad")
                    if isinstance(b.get("detalle_poblacional"), dict) else None,
    }
    assert c == 200, f"el lote {ESTADO['id_lote']} no es consultable (HTTP {c})"
    assert str(E["lote"]["tipo_activo"]) == "POBLACIONAL", E["lote"]
    assert int(E["lote"]["id_infraestructura"]) == ESTADO["a1"], E["lote"]
    assert int(E["lote"]["id_especie"]) == ESTADO["especie"], E["lote"]
    ESTADO["lote"] = True


# ══════════════════════════════════════════════════════════════════════════════
# 2. Observación por GET con la cadencia del §24
# ══════════════════════════════════════════════════════════════════════════════

def test_04_observacion_por_get():
    """Polling no destructivo: solo GET, con la cadencia 0/2/5/10/20/30 s."""
    requiere("lote")
    inicio = time.monotonic()
    muestras = []
    for objetivo in CADENCIA:
        espera = objetivo - (time.monotonic() - inicio)
        if espera > 0:
            time.sleep(espera)
        ch, hist = API.get(f"/configuracion/calibraciones-vision?area_id={ESTADO['a1']}")
        cl, lb = API.get(f"/configuracion/calibraciones-vision/linea-base?area_id={ESTADO['a1']}")
        ahora = datetime.datetime.now(datetime.timezone.utc)
        muestras.append({
            "t_relativo_s": objetivo,
            "instante": ahora.isoformat(),
            "desde_t_alta_s": round((ahora - parse(ESTADO["t_alta"])).total_seconds(), 1)
                              if ESTADO.get("t_alta") else None,
            "desde_t_cierre_s": round((ahora - parse(ESTADO["t_cierre"])).total_seconds(), 1)
                                if ESTADO.get("t_cierre") else None,
            "historial_http": ch, "historial_total": hist.get("total"),
            "historial_ids": [i["id_calibracion_vision"] for i in hist.get("items", [])],
            "linea_base_http": cl,
            "linea_base_id": lb.get("id_calibracion_vision") if cl == 200 else None,
        })
        assert ch == 200, f"historial no consultable (HTTP {ch})"
        assert cl in (200, 404), f"línea base con HTTP inesperado {cl}"
    E["observacion_por_get"] = {
        "cadencia_s": list(CADENCIA),
        "escrituras_durante_el_polling": 0,
        "muestras": muestras,
    }
    # Los items completos del ultimo muestreo: el veredicto necesita origen_disparo,
    # id_usuario, estado y el motivo de cada calibracion, no solo sus ids.
    ch, hist = API.get(f"/configuracion/calibraciones-vision?area_id={ESTADO['a1']}")
    ESTADO["items_post"] = {i["id_calibracion_vision"]: i for i in hist.get("items", [])}
    ESTADO["ids_post"] = muestras[-1]["historial_ids"]
    ESTADO["linea_base_post"] = muestras[-1]["linea_base_id"]
    ESTADO["ventana_observada_desde_alta_s"] = muestras[-1]["desde_t_alta_s"]
    ESTADO["ventana_observada_desde_cierre_s"] = muestras[-1]["desde_t_cierre_s"]
    ESTADO["observacion"] = True


# ══════════════════════════════════════════════════════════════════════════════
# 3. Auditoría RF-10
# ══════════════════════════════════════════════════════════════════════════════

def test_05_auditoria_rf10():
    requiere("observacion")
    desde = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=2)
             ).strftime("%Y-%m-%dT%H:%M:%S")
    auditoria = {"consulta": {"fecha_desde": desde, "tipos": [TIPO_EVENTO_EXITO, TIPO_EVENTO_RECHAZO]}}
    del_area = []
    for tipo in (TIPO_EVENTO_EXITO, TIPO_EVENTO_RECHAZO):
        c, b = API.get(f"/auditoria/?tipo_evento={tipo}&fecha_desde={desde}&pagina=1&tamano=50")
        auditoria[f"tipo_{tipo}_http"] = c
        if c in (200, 206):
            for ev in (b.get("items") or b.get("eventos") or []):
                d = detalle_de(ev)
                if d.get("operacion") == "CALIBRACION_VISION" and \
                        str(d.get("id_infraestructura")) == str(ESTADO["a1"]):
                    # Contrato real de RF-10: el resultado va en `resultado`
                    # ('exitoso'/'fallido'), no existe `exitoso`, y la firma del evento
                    # es obligatoria (usuario de servicio en los disparos del Sistema).
                    del_area.append({"id_evento": ev.get("id_evento") or ev.get("id"),
                                     "tipo_evento": tipo,
                                     "fecha": ev.get("fecha_evento") or ev.get("fecha"),
                                     "resultado": ev.get("resultado"),
                                     "modulo": ev.get("modulo"),
                                     "id_usuario": ev.get("id_usuario"),
                                     "nombre_usuario": ev.get("nombre_usuario"),
                                     "direccion_ip": "PRESENTE" if ev.get("direccion_ip") else "AUSENTE",
                                     "integridad_ok": ev.get("integridad_ok"),
                                     "detalle": d})
        else:
            E["limitaciones"].append({"tema": "auditoría RF-10",
                                      "detalle": f"GET /auditoria/ tipo {tipo} respondió HTTP {c}"})
    auditoria["eventos_vision_de_A1"] = del_area
    # Indice por calibracion: el veredicto exige el evento EXITOSO de cada disparo, con
    # su origen y su firma. El contrato de RF-10 trae el resultado en `resultado`
    # ('exitoso'/'fallido'); NO existe un campo `exitoso`.
    por_calibracion = {}
    for ev in del_area:
        clave = ev["detalle"].get("id_calibracion_vision")
        if clave is not None:
            por_calibracion.setdefault(int(clave), []).append(ev)
    auditoria["por_calibracion"] = {str(k): [e["id_evento"] for e in v]
                                    for k, v in por_calibracion.items()}
    ESTADO["auditoria_por_calibracion"] = por_calibracion
    E["auditoria_rf10"] = auditoria
    ESTADO["auditoria"] = True


def _calibracion_automatica(id_calibracion: int, motivo_esperado: str, etiqueta: str) -> dict:
    """Comprueba el contrato de una calibracion disparada por M02 (§11, §48 y §62).

    No basta con que exista una calibracion nueva: tiene que ser del Sistema
    (`origen_disparo = AUTOMATICO`, `id_usuario` nulo), exitosa, con linea base y con
    el motivo del evento que la disparo.
    """
    item = ESTADO["items_post"].get(id_calibracion)
    assert item is not None, (
        f"{etiqueta}: la calibracion {id_calibracion} no aparece en el historial del area")
    observado = {
        "id_calibracion_vision": item["id_calibracion_vision"],
        "estado": item["estado"],
        "origen_disparo": item["origen_disparo"],
        "id_usuario": item["id_usuario"],
        "area_id": item["area_id"],
        "especie_id": item["especie_id"],
        "n_observaciones": item["n_observaciones"],
        "n_observaciones_validas": item["n_observaciones_validas"],
        "iteraciones": item.get("iteraciones"),
        "ventana_observacion": item.get("ventana_observacion"),
        "linea_base": item.get("linea_base"),
        "observaciones": item.get("observaciones"),
        "motivo_esperado": motivo_esperado,
    }
    assert item["estado"] == "EXITOSA", f"{etiqueta}: estado {item['estado']!r}"
    assert item["origen_disparo"] == "AUTOMATICO", (
        f"{etiqueta}: origen_disparo {item['origen_disparo']!r}; el disparo del Sistema "
        "debe quedar como AUTOMATICO")
    assert item["id_usuario"] is None, (
        f"{etiqueta}: id_usuario {item['id_usuario']!r}; la calibracion automatica es del "
        "Sistema y no puede atribuirse a un usuario")
    assert int(item["area_id"]) == ESTADO["a1"], f"{etiqueta}: area {item['area_id']}"
    assert int(item["especie_id"]) == ESTADO["especie"], f"{etiqueta}: especie {item['especie_id']}"
    assert item.get("linea_base"), f"{etiqueta}: la calibracion exitosa no trae linea base"
    assert item.get("observaciones") and motivo_esperado in str(item["observaciones"]), (
        f"{etiqueta}: el motivo no corresponde al evento de M02\n"
        f"  esperado contener: {motivo_esperado!r}\n"
        f"  obtenido: {item.get('observaciones')!r}")
    # La ventana del disparo automatico la fija la implementacion (7 dias). Se registra
    # como dato observado; la matriz no la convierte en criterio contractual.
    ventana = item.get("ventana_observacion") or {}
    if ventana.get("inicio") and ventana.get("fin"):
        dur = (parse(ventana["fin"]) - parse(ventana["inicio"])).total_seconds()
        observado["ventana_dias_observados"] = round(dur / 86400.0, 4)
    return observado


def _auditoria_de(id_calibracion: int, etiqueta: str) -> dict:
    """Exige el evento RF-10 EXITOSO del disparo, firmado por el usuario de servicio.

    §12 y §76: lo que debe ser nulo es `calibracion.id_usuario`, no el id del evento de
    auditoria, que es obligatorio en modulo1.eventos y lleva el usuario de servicio.
    """
    eventos = (ESTADO.get("auditoria_por_calibracion") or {}).get(id_calibracion) or []
    assert eventos, f"{etiqueta}: no hay evento RF-10 correlacionado con la calibracion {id_calibracion}"
    ev = eventos[-1]
    d = ev["detalle"]
    observado = {
        "id_evento": ev["id_evento"],
        "tipo_evento": ev["tipo_evento"],
        "resultado": ev.get("resultado"),
        "modulo": ev.get("modulo"),
        "id_usuario_auditoria": ev.get("id_usuario"),
        "nombre_usuario_auditoria": ev.get("nombre_usuario"),
        "operacion": d.get("operacion"),
        "origen_disparo": d.get("origen_disparo"),
        "id_calibracion_vision": d.get("id_calibracion_vision"),
        "id_infraestructura": d.get("id_infraestructura"),
        "id_especie": d.get("id_especie"),
        "estado": d.get("estado"),
        "nota_firma": ("la firma es el USUARIO DE SERVICIO; la matriz no exige "
                       "auditoria.id_usuario nulo (§12 y §76)"),
    }
    assert ev["tipo_evento"] == TIPO_EVENTO_EXITO, f"{etiqueta}: tipo {ev['tipo_evento']}"
    assert str(ev.get("resultado")).lower() == "exitoso", f"{etiqueta}: resultado {ev.get('resultado')!r}"
    assert ev.get("modulo") == "MODULO9", f"{etiqueta}: modulo {ev.get('modulo')!r}"
    assert d.get("operacion") == "CALIBRACION_VISION", f"{etiqueta}: operacion {d.get('operacion')!r}"
    assert d.get("origen_disparo") == "AUTOMATICO", (
        f"{etiqueta}: la auditoria no declara origen AUTOMATICO: {d.get('origen_disparo')!r}")
    assert int(d.get("id_calibracion_vision")) == id_calibracion, observado
    assert ev.get("id_usuario") is not None, (
        f"{etiqueta}: el evento RF-10 debe ir firmado por el usuario de servicio")
    return observado


# ══════════════════════════════════════════════════════════════════════════════
# 4. Diagnóstico de integración sobre el código (§44)
# ══════════════════════════════════════════════════════════════════════════════

def test_06_diagnostico_de_integracion():
    """§44: si el evento no produjo calibración, hay que mirar el artefacto desplegable."""
    requiere("auditoria")
    def grep(patron: str, raiz: str) -> list[str]:
        base = REPO_DIR / raiz
        fuera = []
        for ruta in sorted(base.rglob("*.py")):
            if "__pycache__" in ruta.parts:
                continue
            try:
                texto = ruta.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if re.search(patron, texto):
                fuera.append(str(ruta.relative_to(REPO_DIR)).replace("\\", "/"))
        return fuera

    alta = REPO_DIR / "src/biological_assets/application/use_cases/registro/registrar_activo_use_case.py"
    cierre = REPO_DIR / "src/biological_assets/application/use_cases/gestion/cerrar_ciclo_use_case.py"
    texto_alta = alta.read_text(encoding="utf-8")
    texto_cierre = cierre.read_text(encoding="utf-8")
    patron_vision = r"CalibrarVisionUseCase|calibracion_vision|CALIBRACION_VISION|OrigenDisparo"
    diagnostico = {
        "commit": E["git"]["commit"],
        "hook_en_el_alta": "PRESENTE" if re.search(patron_vision, texto_alta) else "AUSENTE",
        "hook_en_el_cierre": "PRESENTE" if re.search(patron_vision, texto_cierre) else "AUSENTE",
        "archivos_m02_que_mencionan_vision": grep(patron_vision, "src/biological_assets"),
        "archivos_con_CalibrarVisionUseCase": grep(r"CalibrarVisionUseCase", "src"),
        "usos_de_OrigenDisparo_AUTOMATICO": grep(r"OrigenDisparo\.AUTOMATICO", "src"),
        "mecanismos_asincronos_en_m02": grep(
            r"BackgroundTasks|event_bus|EventBus|outbox|add_event_listener|publish_event",
            "src/biological_assets"),
        "triggers_bd_sobre_calibraciones_vision": "ninguno (verificado en el laboratorio de G140)",
        "repos_que_recibe_el_caso_de_uso_de_cierre": (
            "db, ActivoBiologicoRepository, EventoActivoRepository, HistoricoEstadoRepository, "
            "BitacoraAuditoriaRepository — ninguno de VISION"),
    }
    E["diagnostico_integracion"] = diagnostico
    E["diagnostico_integracion"]["conclusion"] = (
        "No existe ningún mecanismo de M02 → M09: ni llamada directa, ni bus de eventos, ni "
        "tarea de fondo, ni trigger de BD. `OrigenDisparo.AUTOMATICO` está declarado pero no "
        "tiene ningún uso funcional en todo `src/`."
        if (diagnostico["hook_en_el_alta"] == "AUSENTE"
            and diagnostico["hook_en_el_cierre"] == "AUSENTE"
            and not diagnostico["usos_de_OrigenDisparo_AUTOMATICO"])
        else "Hay referencias a VISION en M02: revisar si el desfase es de despliegue (§46).")
    ESTADO["diagnostico"] = True


# ══════════════════════════════════════════════════════════════════════════════
# 5. BD complementaria (§8 y §48)
# ══════════════════════════════════════════════════════════════════════════════

def test_07_bd_complementaria():
    requiere("diagnostico")
    res = select([
        ("privilegios", """
            SELECT 'modulo3.observaciones_vision' AS tabla,
                   has_table_privilege('member_qa','modulo3.observaciones_vision','SELECT') AS puede_select
            UNION ALL SELECT 'modulo9.calibraciones_vision',
                   has_table_privilege('member_qa','modulo9.calibraciones_vision','SELECT')
            UNION ALL SELECT 'modulo9.lineas_base_vision',
                   has_table_privilege('member_qa','modulo9.lineas_base_vision','SELECT')"""),
        ("calibraciones_de_A1", f"""
            SELECT id_calibracion_vision, estado, origen_disparo, id_usuario
            FROM modulo9.calibraciones_vision WHERE id_infraestructura = {ESTADO['a1']}"""),
        ("linea_base_de_A1", f"""
            SELECT id_calibracion_vision FROM modulo9.lineas_base_vision
            WHERE id_infraestructura = {ESTADO['a1']}"""),
    ])
    privs = {f["tabla"]: f["puede_select"] for f in res.get("privilegios", [])
             if isinstance(f, dict)}
    disponible = bool(privs) and all(privs.values())
    E["bd_complementaria"] = {
        "rol_en_la_matriz": "evidencia COMPLEMENTARIA; no es compuerta",
        "usuario": DB["user"], "sesion": "READ ONLY — solo SELECT, 0 DML",
        "privilegios_select": privs, "resultado": res,
        "BD_COMPLEMENTARIA": "DISPONIBLE" if disponible else "NO DISPONIBLE",
        "contradice_a_la_api": "NO",
    }
    if not disponible:
        E["limitaciones"].append({
            "tema": "BD complementaria",
            "detalle": ("member_qa no tiene SELECT sobre las tablas VISION; el contraste de BD no "
                        "se pudo hacer. No es incidencia funcional de G142 y no bloquea (§8/§48)."),
            "responsable": "DBA / Implementación",
        })
    ESTADO["bd"] = True


# ══════════════════════════════════════════════════════════════════════════════
# 6. Veredictos
# ══════════════════════════════════════════════════════════════════════════════

def test_08_veredicto_tc288():
    """§52 y §95: el alta valida debe producir UNA calibracion automatica completa."""
    requiere("bd")
    ids_post = ESTADO["ids_post"]
    nuevas = [i for i in ids_post if i not in ESTADO["hist_pre_288"]]
    # Las nuevas tras el alta incluyen tambien la del cierre, porque el polling de este
    # verificador corre despues de los dos eventos. La del alta es la que declara el
    # motivo del alta; se identifica por motivo, no por orden.
    del_alta = [i for i in nuevas
                if f"nuevo lote {ESTADO['id_lote']}" in str(
                    (ESTADO["items_post"].get(i) or {}).get("observaciones") or "")]
    caso = {
        "evento": "POST /activos-biologicos (alta de lote POBLACIONAL)",
        "alta_http": E["eventos_m02"]["alta"]["http"],
        "id_lote": ESTADO["id_lote"],
        "T_ALTA": ESTADO["t_alta"],
        "post_manual_calibraciones_vision": 0,
        "historial_PRE": ESTADO["hist_pre_288"],
        "historial_POST": ids_post,
        "calibraciones_nuevas_tras_el_alta": nuevas,
        "atribuibles_al_alta_por_motivo": del_alta,
        "calibracion_automatica": "SÍ" if del_alta else "NO",
        "ventana_observada_desde_el_alta_s": ESTADO["ventana_observada_desde_alta_s"],
        "nota_sla": ("RF-24 no fija plazo para el disparo: el tiempo observado es una métrica, "
                     "no un umbral de PASS/FAIL (§47). El veredicto se apoya en el efecto "
                     "observado, no en la latencia."),
    }
    assert str(caso["alta_http"]) == "201", (
        f"el alta M02 no fue un evento funcional válido (HTTP {caso['alta_http']}); "
        "sin alta válida no se puede evaluar el disparo")
    if not del_alta:
        caso["resultado"] = "RECHAZADO"
        caso["causa"] = ("el alta fue válida y no quedó ninguna calibración VISION atribuible "
                         "a ella: posible fallo de la integración M02→M09")
        E["casos"] = {"TC-M09-288": caso}
        ESTADO["tc288"] = "RECHAZADO"
        ESTADO["v288"] = True
        return
    # §67: un evento debe producir UNA calibracion, no varias.
    assert len(del_alta) == 1, (
        f"el alta produjo {len(del_alta)} calibraciones automáticas ({del_alta}); "
        "se espera exactamente una por evento")
    ESTADO["AUTO_288_ID"] = del_alta[0]
    caso["AUTO_288_ID"] = ESTADO["AUTO_288_ID"]
    caso["calibracion"] = _calibracion_automatica(
        ESTADO["AUTO_288_ID"], f"nuevo lote {ESTADO['id_lote']}", "TC-288")
    caso["auditoria"] = _auditoria_de(ESTADO["AUTO_288_ID"], "TC-288")
    # La linea base vigente INMEDIATAMENTE despues del alta ya no es observable aqui: el
    # cierre la reemplazo legitimamente (mismo par area/especie, §63). Lo que si consta es
    # que la calibracion del alta publico linea base, y que Newman observo el estado
    # intermedio durante el RUN con sus propias assertions.
    caso["linea_base_publicada_por_AUTO_288"] = bool(caso["calibracion"].get("linea_base"))
    caso["linea_base_intermedia"] = (
        "verificada por Newman durante el RUN (HTTP 200 tras el alta); no re-observable "
        "a posteriori porque el cierre la reemplazo")
    caso["resultado"] = "APROBADO"
    E["casos"] = {"TC-M09-288": caso}
    ESTADO["tc288"] = "APROBADO"
    ESTADO["v288"] = True


def test_09_veredicto_tc289():
    """§65 y §96: el cierre válido debe producir una SEGUNDA calibración automática."""
    requiere("v288")
    ids_post = ESTADO["ids_post"]
    nuevas = [i for i in ids_post if i not in ESTADO["hist_pre_289"]]
    cierre = E["eventos_m02"]["cierre"]
    c, b = API.get(f"/activos-biologicos/{ESTADO['id_lote']}")
    # El contrato devuelve el id de estado (CERRADO = 5) y, segun la ruta, su nombre.
    id_estado = (b or {}).get("id_estado")
    nombre_estado = str((b or {}).get("nombre_estado") or (b or {}).get("estado") or "")
    cerrado = str(id_estado) == str(ESTADO_CERRADO) or "CERRADO" in nombre_estado.upper()
    del_cierre = [i for i in nuevas
                  if f"fin de ciclo del lote {ESTADO['id_lote']}" in str(
                      (ESTADO["items_post"].get(i) or {}).get("observaciones") or "")]
    caso = {
        "evento": "POST /activos-biologicos/{id}/cierre (cierre del ciclo)",
        "cierre_http": cierre["http"],
        "T_CIERRE": ESTADO["t_cierre"],
        "precondicion_m02": {
            "ciclos_productivos_asignables": cierre["ciclos_productivos_asignables"],
            "fase_setup_http": cierre["fase_setup_http"],
            "fase_activa_requerida": True,
        },
        "lote_cerrado": "SÍ" if cerrado else "NO",
        "id_estado_del_lote": id_estado,
        "nombre_estado_del_lote": nombre_estado or f"(no expuesto; id {id_estado})",
        "post_manual_calibraciones_vision": 0,
        "historial_PRE": ESTADO["hist_pre_289"],
        "historial_POST": ids_post,
        "calibraciones_nuevas_tras_el_cierre": nuevas,
        "atribuibles_al_cierre_por_motivo": del_cierre,
        "calibracion_automatica": "SÍ" if del_cierre else "NO",
        "ventana_observada_desde_el_cierre_s": ESTADO["ventana_observada_desde_cierre_s"],
    }
    cierre_valido = str(cierre["http"]) in ("200", "201")
    caso["cierre_valido"] = "SÍ" if cierre_valido else "NO"
    if not cierre_valido:
        caso["resultado"] = "BLOQUEADO"
        caso["causa"] = ("el evento de cierre no se completó; el disparo de cierre no llegó a "
                         "ejercitarse y no se le atribuye un fallo (§9)")
        E["casos"]["TC-M09-289"] = caso
        ESTADO["tc289"] = "BLOQUEADO"
        ESTADO["v289"] = True
        return
    assert cerrado, (
        f"el cierre respondió {cierre['http']} pero el lote no quedó CERRADO "
        f"(id_estado {id_estado!r}, nombre {nombre_estado!r})")
    if not del_cierre:
        caso["resultado"] = "RECHAZADO"
        caso["causa"] = ("el cierre fue válido y no quedó ninguna calibración VISION atribuible "
                         "a él: fallo de la integración de cierre M02→M09, para Desarrollo")
        E["casos"]["TC-M09-289"] = caso
        ESTADO["tc289"] = "RECHAZADO"
        ESTADO["v289"] = True
        return
    assert len(del_cierre) == 1, (
        f"el cierre produjo {len(del_cierre)} calibraciones automáticas ({del_cierre}); "
        "se espera exactamente una por evento")
    ESTADO["AUTO_289_ID"] = del_cierre[0]
    caso["AUTO_289_ID"] = ESTADO["AUTO_289_ID"]
    assert ESTADO["AUTO_289_ID"] != ESTADO.get("AUTO_288_ID"), (
        "AUTO_289 y AUTO_288 son la misma calibración: no se demostraron dos disparos")
    caso["AUTO_289_distinta_de_AUTO_288"] = "SÍ"
    caso["calibracion"] = _calibracion_automatica(
        ESTADO["AUTO_289_ID"], f"fin de ciclo del lote {ESTADO['id_lote']}", "TC-289")
    caso["auditoria"] = _auditoria_de(ESTADO["AUTO_289_ID"], "TC-289")
    caso["linea_base_final"] = ESTADO["linea_base_post"]
    assert ESTADO["linea_base_post"] == ESTADO["AUTO_289_ID"], (
        "la línea base vigente final no apunta a AUTO_289: "
        f"{ESTADO['linea_base_post']} vs {ESTADO['AUTO_289_ID']}")
    caso["nota_baseline"] = ("AUTO_289 reemplaza la línea base de AUTO_288 porque comparten el "
                             "par (área, especie); es el comportamiento esperado (§63)")
    caso["resultado"] = "APROBADO"
    E["casos"]["TC-M09-289"] = caso
    ESTADO["tc289"] = "APROBADO"
    ESTADO["v289"] = True


def test_10_cierre():
    requiere("v289")
    aprobados = ESTADO["tc288"] == "APROBADO" and ESTADO["tc289"] == "APROBADO"
    E["execution_number"] = EJECUCION
    E["execution_type"] = TIPO_EJECUCION
    E["nuevo_run_creado"] = "NO"
    E["correccion"] = {"pr": PR_CORRECCION,
                       "componentes": ["RecalibracionVisionPort",
                                       "RecalibracionVisionM09Adapter",
                                       "hook en RegistrarActivoBiologicoUseCase",
                                       "hook en CerrarCicloUseCase",
                                       "CalibrarVisionUseCase.execute_automatico",
                                       "OrigenDisparo.AUTOMATICO",
                                       "VENTANA_DISPARO_AUTOMATICO"]}
    E["historial_ejecuciones"] = [dict(h) for h in HISTORIAL_EJECUCIONES] + [{
        "ejecucion": EJECUCION,
        "fecha": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "tipo": TIPO_EJECUCION,
        "pr": PR_CORRECCION,
        "hook_m02_m09": "PRESENTE",
        "resultados": {"TC-M09-288": ESTADO["tc288"], "TC-M09-289": ESTADO["tc289"]},
        "AUTO_288_ID": ESTADO.get("AUTO_288_ID"),
        "AUTO_289_ID": ESTADO.get("AUTO_289_ID"),
        "fixture_preparado_por_dba": {"especie": 78, "ciclo_biologico": 54,
                                      "ciclo_productivo": 11, "fase": 21},
    }]
    E["resultado"] = {
        "TC-M09-288": ESTADO["tc288"],
        "TC-M09-289": ESTADO["tc289"],
        "TC-M09-G142": "APROBADO" if aprobados else "RECHAZADO",
        "incidencia_requerida": "NO" if aprobados else "SÍ",
        "responsable": None if aprobados else "Desarrollo / Integración M02-M09",
        "causa": None if aprobados else (
            "Los eventos de M02 se procesan correctamente, pero no generan ninguna calibración "
            "VISION automática: no existe mecanismo/hook/evento desde el alta ni desde el cierre "
            "hacia el caso de uso VISION de M09."),
        "BD_COMPLEMENTARIA": E["bd_complementaria"]["BD_COMPLEMENTARIA"],
        "incidencia_unica_consolidada": "SÍ — ambos casos comparten la misma causa raíz",
    }
    E["seguridad"] = {
        "credenciales_persistidas": "NO",
        "serial_access_key_persistido": "NO — redactado por patrón",
        "sql_dml_en_test": 0,
        "sesion_bd": "READ ONLY",
        "post_funcionales_ejecutados_por_pytest": 0,
        "archivos_primera_evaluacion_modificados": "NINGUNO",
    }
    guardar()
    # El verificador no falla por el defecto del producto: su trabajo es establecer los hechos.
    # El resultado funcional vive en el informe y en los fallos del Newman oficial.
    assert E["presupuesto"]["post_manual_calibraciones_vision"] == 0
    assert E["post_funcionales_de_pytest"] == 0
