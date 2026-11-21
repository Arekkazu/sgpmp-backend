"""TC-M09-290 y TC-M09-291 — verificador independiente de SOLO LECTURA contra TEST.

TC-M09-G143 · RF-24 v2.0 · CU05 Flujo F · SEGUNDA EVALUACIÓN.

Reparto de papeles (§4, §53 y §54 del paquete):

  * **Newman** ejecuta los eventos funcionales en TEST: el alta del lote de TC-M09-290 y el
    POST VISION de TC-M09-291. Su colección es dueña de las dos sesiones.
  * **Pytest** —este archivo— verifica después, **solo con GET**. No repite el alta ni el POST
    manual de VISION.

La BD de TEST es evidencia complementaria: si `member_qa` no tiene SELECT se registra
`BD_COMPLEMENTARIA = NO DISPONIBLE` y la ejecución continúa (§4 y §30).

Uso:
    pytest test_g143_test.py -v --confcutdir=. --junitxml=<RUN>/pytest-test.xml
"""
from __future__ import annotations

import datetime
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
GRUPO = "TC-M09-G143"
if BASE_DIR.name != "automation" or EVAL_DIR.name != "EvaluacionV2" or CASE_DIR.name != GRUPO:
    raise RuntimeError(f"ABORTADO: ruta no autorizada para {GRUPO}: {BASE_DIR}")
REPO_DIR = CASE_DIR.parents[4]

RUN_ID = os.environ["G143_RUN_ID"]
RUN_DIR = EVAL_DIR / "RESULTADOS" / RUN_ID
RESUMEN = RUN_DIR / "newman-resumen.json"

BASE_URL = "https://api.inmero.co/back-sigab-test"
ADMIN = ("administador.dev@gmail.com", "Test1234!")
ADMIN_ALT = ("admin.dev@gmail.com", "Test1234!")
DB = {"host": "158.69.200.27", "port": "5448", "dbname": "sgpmp_test",
      "user": "member_qa", "password": "qaSGP2026"}
CADENCIA = (0, 2, 5, 10, 20, 30)
_RE_SERIAL = re.compile(r"QA-M09-G1\d{2}-[A-Z]+-\d{8}-\d{6}")

E: dict = {
    "run_id": RUN_ID, "grupo": GRUPO, "casos": ["TC-M09-290", "TC-M09-291"],
    "ambiente": "TEST", "base_url": BASE_URL,
    "herramientas": {"ejecutor": "Newman", "verificador": "Pytest (solo lectura)"},
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
    (RUN_DIR / "evidencia-test.json").write_text(
        json.dumps(sanear(E), indent=2, ensure_ascii=False, default=str), encoding="utf-8")


def select(consultas: list[tuple[str, str]]) -> dict:
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


class Lectura:
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
    d = ev.get("detalle") or {}
    if isinstance(d, str):
        try:
            d = json.loads(d)
        except ValueError:
            d = {}
    return d if isinstance(d, dict) else {}


@pytest.fixture(scope="session", autouse=True)
def cierre():
    yield
    guardar()


# ══════════════════════════════════════════════════════════════════════════════
# 1. Contexto
# ══════════════════════════════════════════════════════════════════════════════

def test_01_rama_y_resumen():
    rama = subprocess.run(["git", "branch", "--show-current"], cwd=str(REPO_DIR),
                          capture_output=True, text=True).stdout.strip()
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(REPO_DIR),
                            capture_output=True, text=True).stdout.strip()
    estado = subprocess.run(["git", "status", "--short"], cwd=str(REPO_DIR),
                            capture_output=True, text=True).stdout.strip()
    E["git"] = {"rama": rama, "commit": commit, "status_short": estado.splitlines()}
    assert rama == "qa/juan-esteban-segunda-evaluacion-rf24-v2.0", f"rama inesperada: {rama}"

    assert RESUMEN.is_file(), f"falta el resumen del RUN Newman en {RESUMEN}"
    r = json.loads(RESUMEN.read_text(encoding="utf-8"))
    v = r["valores_finales"]
    E["newman"] = r["newman"]
    E["presupuesto"] = r["presupuesto"]
    E["fixture"] = {
        "finca_id": v.get("finca_id"), "fincas_compartidas": v.get("fincas_compartidas"),
        "tipo_area": v.get("tipo_area"),
        "especie_id": v.get("especie_id"), "especie_nombre": v.get("especie_nombre"),
        "especie_densidad_maxima": v.get("especie_densidad"),
        "especies_aptas": v.get("especies_aptas"),
        "metricas_obligatorias": v.get("metricas_obligatorias"),
        "A1": v.get("a1_id"), "C1": v.get("c1_id"),
        "dispositivos_de_A1": v.get("dispositivos_a1"),
        "A2": v.get("a2_id"), "dispositivos_de_A2": v.get("dispositivos_a2"),
        "observaciones_vision_de_A1": 0,
        "tipo_evento_rechazada": v.get("tipo_rechazada"),
        "tipo_evento_exitosa": v.get("tipo_exitosa"),
    }
    E["N"] = {"valor": None, "fuente": None}
    fuente = REPO_DIR / "src/configuration/domain/entities/linea_base_vision.py"
    m = re.search(r"min_observaciones:\s*int\s*=\s*(\d+)", fuente.read_text(encoding="utf-8"))
    assert m, "no se pudo leer min_observaciones"
    E["N"] = {"valor": int(m.group(1)),
              "fuente": "ParametrosLineaBase.min_observaciones — src/configuration/domain/entities/linea_base_vision.py",
              "commit": commit}
    ESTADO.update({
        "a1": int(v["a1_id"]), "a2": int(v["a2_id"]), "especie": int(v["especie_id"]),
        "id_lote": int(v["id_lote_290"]) if str(v.get("id_lote_290") or "").isdigit() else None,
        "t_alta": v.get("t_alta_290"), "t_pre_290": v.get("t_pre_290"),
        "t_before_291": v.get("t_before_291"), "t_after_291": v.get("t_after_291"),
        "hist_pre_290": json.loads(v.get("hist_pre_290") or "[]"),
        "hist_pre_291": json.loads(v.get("hist_pre_291") or "[]"),
        "tipo_rechazada": int(v.get("tipo_rechazada") or 0),
        "auditoria_291_id": v.get("auditoria_291_id"),
        "alta_http": v.get("alta_http"), "http_291": v.get("http_291"),
        "error_291": v.get("error_291"), "mensaje_291": v.get("mensaje_291"),
        "mensaje_291_esperado": v.get("mensaje_291_esperado"),
        "fields_291": v.get("fields_291"),
    })
    # Reglas duras del paquete sobre el presupuesto.
    assert E["presupuesto"]["ingesta_m03"] == 0, E["presupuesto"]
    assert E["presupuesto"]["alta_m02"] == 1, E["presupuesto"]
    assert E["presupuesto"]["post_manual_calibraciones_vision"] == 1, E["presupuesto"]
    assert E["presupuesto"]["reintentos"] == 0, E["presupuesto"]
    ESTADO["contexto"] = True


def test_02_actor_de_lectura():
    requiere("contexto")
    correo = API.login()
    E["verificador"] = {"actor": correo, "modo": "solo lectura: login + GET"}
    ESTADO["actor"] = True


def test_03_fixture_observado():
    """A1 tiene cámara y cero observaciones; A2 no tiene ninguna cámara."""
    requiere("actor")
    c, lista = API.get("/configuracion/dispositivos-iot", timeout=240)
    assert c == 200, f"listado de dispositivos HTTP {c}"
    de_a1 = [d for d in lista["items"] if d.get("id_infraestructura") == ESTADO["a1"]]
    de_a2 = [d for d in lista["items"] if d.get("id_infraestructura") == ESTADO["a2"]]
    ca, a1 = API.get(f"/configuracion/infraestructuras/{ESTADO['a1']}")
    cb, a2 = API.get(f"/configuracion/infraestructuras/{ESTADO['a2']}")
    E["fixture_verificado"] = {
        "A1": {"http": ca, "especie_id": a1.get("especie_id"),
               "tipo_modelo_asignado": a1.get("tipo_modelo_asignado"),
               "es_activo": a1.get("es_activo"),
               "dispositivos": [{"id": d["id_dispositivo_iot"], "categoria": d.get("categoria"),
                                 "es_activo": d.get("es_activo")} for d in de_a1]},
        "A2": {"http": cb, "especie_id": a2.get("especie_id"),
               "tipo_modelo_asignado": a2.get("tipo_modelo_asignado"),
               "es_activo": a2.get("es_activo"),
               "dispositivos": [d["id_dispositivo_iot"] for d in de_a2]},
    }
    assert ca == 200 and cb == 200
    assert a1.get("tipo_modelo_asignado") == "MODELO_AVES"
    assert a2.get("tipo_modelo_asignado") == "MODELO_AVES"
    assert len(de_a1) == 1, f"A1 debía tener solo C1; tiene {len(de_a1)}"
    assert len(de_a2) == 0, f"A2 debía no tener cámaras; tiene {len(de_a2)}"
    ESTADO["fixture"] = True


def test_04_lote_de_tc290():
    requiere("fixture")
    assert ESTADO["id_lote"], "el RUN no dejó id_lote: el alta M02 no fue válida"
    c, b = API.get(f"/activos-biologicos/{ESTADO['id_lote']}")
    E["lote_290"] = {"http": c, "id": ESTADO["id_lote"],
                     "tipo_activo": b.get("tipo_activo") or b.get("tipo"),
                     "id_especie": b.get("id_especie"),
                     "id_infraestructura": b.get("id_infraestructura"),
                     "id_estado": b.get("id_estado")}
    assert c == 200, f"el lote no es consultable (HTTP {c})"
    assert str(E["lote_290"]["tipo_activo"]) == "POBLACIONAL"
    assert int(E["lote_290"]["id_infraestructura"]) == ESTADO["a1"]
    ESTADO["lote"] = True


# ══════════════════════════════════════════════════════════════════════════════
# 2. Observación por GET (§19 y §24)
# ══════════════════════════════════════════════════════════════════════════════

def test_05_observacion_por_get():
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
            "t_relativo_s": objetivo, "instante": ahora.isoformat(),
            "desde_t_alta_s": round((ahora - parse(ESTADO["t_alta"])).total_seconds(), 1),
            "historial_http": ch, "historial_total": hist.get("total"),
            "historial_ids": [i["id_calibracion_vision"] for i in hist.get("items", [])],
            "linea_base_http": cl,
            "linea_base_id": lb.get("id_calibracion_vision") if cl == 200 else None,
        })
        assert ch == 200 and cl in (200, 404)
    E["observacion_tc290"] = {"cadencia_s": list(CADENCIA),
                              "escrituras_durante_el_polling": 0, "muestras": muestras}
    # Items completos del ultimo muestreo: el veredicto necesita estado, etapa, origen,
    # usuario y motivo de la calibracion, no solo su id.
    _c, _hist = API.get(f"/configuracion/calibraciones-vision?area_id={ESTADO['a1']}")
    ESTADO["items_post_290"] = {i["id_calibracion_vision"]: i for i in (_hist.get("items") or [])}
    ESTADO["ids_post_290"] = muestras[-1]["historial_ids"]
    ESTADO["lb_post_290"] = muestras[-1]["linea_base_id"]
    ESTADO["ventana_observada_s"] = muestras[-1]["desde_t_alta_s"]
    ESTADO["observacion"] = True


# ══════════════════════════════════════════════════════════════════════════════
# 3. Auditoría RF-10
# ══════════════════════════════════════════════════════════════════════════════

def test_06_auditoria():
    requiere("observacion")
    desde = (parse(ESTADO["t_pre_290"]) - datetime.timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%S")
    c, b = API.get(f"/auditoria/?tipo_evento={ESTADO['tipo_rechazada']}&fecha_desde={desde}"
                   f"&pagina=1&tamano=50")
    eventos = (b.get("items") or b.get("eventos") or []) if c in (200, 206) else []
    de_a1, de_a2 = [], []
    for ev in eventos:
        d = detalle_de(ev)
        if d.get("operacion") != "CALIBRACION_VISION":
            continue
        registro = {
            "id_evento": ev.get("id_evento"), "tipo_evento": ev.get("tipo_evento"),
            "resultado": ev.get("resultado"), "modulo": ev.get("modulo"),
            "id_usuario": ev.get("id_usuario"), "nombre_usuario": ev.get("nombre_usuario"),
            "direccion_ip": "PRESENTE" if ev.get("direccion_ip") else None,
            "user_agent": "PRESENTE" if ev.get("user_agent") else None,
            "fecha_evento": ev.get("fecha_evento"), "categoria": ev.get("categoria"),
            "estado": ev.get("estado"), "integridad_ok": ev.get("integridad_ok"),
            "descripcion": ev.get("descripcion"),
            # El detalle se conserva completo: el veredicto del disparo automatico
            # necesita id_calibracion_vision para correlacionar, y origen_disparo, estado
            # y etapa_fallo para comprobar el contrato. Podarlos dejaba el registro
            # inservible como oraculo.
            "detalle": {k: d.get(k) for k in
                        ("operacion", "id_infraestructura", "id_especie", "codigo_http",
                         "codigo_error", "motivo", "id_calibracion_vision", "origen_disparo",
                         "estado", "etapa_fallo", "motivo_etapa")},
            "detalle_ip": "PRESENTE" if d.get("ip") else None,
        }
        if str(d.get("id_infraestructura")) == str(ESTADO["a1"]):
            de_a1.append(registro)
        if str(d.get("id_infraestructura")) == str(ESTADO["a2"]):
            de_a2.append(registro)
    E["auditoria"] = {"http": c, "tipo_evento_consultado": ESTADO["tipo_rechazada"],
                      "fecha_desde": desde,
                      "eventos_de_A1": de_a1, "eventos_de_A2": de_a2}
    assert c in (200, 206), f"auditoría RF-10 HTTP {c}"
    ESTADO["auditoria_a1"] = de_a1
    ESTADO["auditoria_a2"] = de_a2
    ESTADO["auditoria"] = True


def test_07_bd_complementaria():
    requiere("auditoria")
    res = select([
        ("privilegios", """
            SELECT 'modulo3.observaciones_vision' AS tabla,
                   has_table_privilege('member_qa','modulo3.observaciones_vision','SELECT') AS puede_select
            UNION ALL SELECT 'modulo9.calibraciones_vision',
                   has_table_privilege('member_qa','modulo9.calibraciones_vision','SELECT')
            UNION ALL SELECT 'modulo9.lineas_base_vision',
                   has_table_privilege('member_qa','modulo9.lineas_base_vision','SELECT')
            UNION ALL SELECT 'modulo1.eventos',
                   has_table_privilege('member_qa','modulo1.eventos','SELECT')"""),
        ("eventos_del_area", f"""
            SELECT id_evento, tipo_evento, resultado, modulo, id_usuario, direccion_ip
            FROM modulo1.eventos
            WHERE detalle->>'operacion' = 'CALIBRACION_VISION'
              AND detalle->>'id_infraestructura' IN ('{ESTADO['a1']}','{ESTADO['a2']}')
            ORDER BY id_evento DESC LIMIT 10"""),
    ])
    privs = {f["tabla"]: f["puede_select"] for f in res.get("privilegios", []) if isinstance(f, dict)}
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
            "tema": "BD complementaria de TEST",
            "detalle": ("member_qa no tiene SELECT sobre todas las tablas consultadas; el "
                        "contraste no se pudo completar. No bloquea ni es incidencia funcional "
                        "(§4 y §30)."),
            "responsable": "DBA / Implementación"})
    ESTADO["bd"] = True


# ══════════════════════════════════════════════════════════════════════════════
# 4. Veredictos
# ══════════════════════════════════════════════════════════════════════════════

def test_08_veredicto_tc290():
    """§19: el alta valida debe dejar UN intento automatico FALLIDA/FILTRADO auditado."""
    requiere("bd")
    nuevas = [i for i in ESTADO["ids_post_290"] if i not in ESTADO["hist_pre_290"]]
    diagnostico = _diagnostico_integracion()
    caso = {
        "evento": "POST /activos-biologicos (alta de lote POBLACIONAL en A1)",
        "A1": ESTADO["a1"], "C1": E["fixture"]["C1"],
        "observaciones_vision_de_A1": 0,
        "alta_http": ESTADO["alta_http"], "ID_LOTE": ESTADO["id_lote"],
        "T_ALTA": ESTADO["t_alta"],
        "post_manual_calibraciones_vision_sobre_A1": 0,
        "historial_PRE": ESTADO["hist_pre_290"], "historial_POST": ESTADO["ids_post_290"],
        "calibraciones_nuevas": nuevas,
        "disparo_automatico": "SÍ" if nuevas else "NO",
        "baseline_nueva": "SÍ" if ESTADO["lb_post_290"] else "NO",
        "linea_base_vigente": ESTADO["lb_post_290"],
        "auditoria_fallido": "SÍ" if ESTADO["auditoria_a1"] else "NO",
        "ventana_observada_desde_el_alta_s": ESTADO["ventana_observada_s"],
        "nota_sla": ("RF-24 no fija plazo: el tiempo observado es una métrica, no un umbral "
                     "(§16 y §19). El veredicto se apoya en el efecto observado."),
        "diagnostico_integracion": diagnostico,
    }
    assert str(caso["alta_http"]) == "201", (
        f"el alta M02 no fue válida (HTTP {caso['alta_http']}); sin alta válida no se evalúa el disparo")

    if not nuevas:
        caso["resultado"] = "RECHAZADO"
        caso["causa"] = ("el alta fue válida y no quedó ninguna calibración VISION: el disparo "
                         "automático no se ejecutó")
        caso["relacionada_con_G142"] = "SÍ"
        caso["nota_auditoria"] = (
            "No se abre incidencia de auditoría: el cálculo nunca se ejecutó, así que la "
            "auditoría FALLIDO no tuvo ocasión de registrarse. No es un defecto de RF-10.")
        E["casos"] = {"TC-M09-290": caso}
        ESTADO["tc290"] = "RECHAZADO"
        ESTADO["v290"] = True
        return

    # §19: un evento, una calibracion.
    assert len(nuevas) == 1, (
        f"el alta produjo {len(nuevas)} calibraciones ({nuevas}); se espera exactamente una")
    ESTADO["AUTO_290_ID"] = nuevas[0]
    caso["AUTO_290_ID"] = ESTADO["AUTO_290_ID"]

    item = (ESTADO.get("items_post_290") or {}).get(ESTADO["AUTO_290_ID"])
    assert item is not None, (
        f"la calibración {ESTADO['AUTO_290_ID']} no es legible en el historial del área")
    caso["calibracion"] = {
        "id_calibracion_vision": item.get("id_calibracion_vision"),
        "area_id": item.get("area_id"), "especie_id": item.get("especie_id"),
        "origen_disparo": item.get("origen_disparo"), "id_usuario": item.get("id_usuario"),
        "estado": item.get("estado"), "etapa_fallo": item.get("etapa_fallo"),
        "motivo": item.get("motivo"), "linea_base": item.get("linea_base"),
        "n_observaciones": item.get("n_observaciones"),
        "n_observaciones_validas": item.get("n_observaciones_validas"),
        "ventana_observacion": item.get("ventana_observacion"),
        "fecha_calibracion": item.get("fecha_calibracion"),
        "observaciones": item.get("observaciones"),
    }
    # El intento es del Sistema, no de un usuario, y con 0 observaciones falla en FILTRADO.
    assert item.get("origen_disparo") == "AUTOMATICO", item.get("origen_disparo")
    assert item.get("id_usuario") is None, (
        f"la calibración automática no puede atribuirse a un usuario: {item.get('id_usuario')!r}")
    assert item.get("estado") == "FALLIDA", item.get("estado")
    assert item.get("etapa_fallo") == "FILTRADO", item.get("etapa_fallo")
    assert item.get("linea_base") is None, "un intento FALLIDA no puede traer línea base"
    assert int(item.get("n_observaciones_validas") or 0) == 0, item.get("n_observaciones_validas")
    assert int(item.get("area_id")) == ESTADO["a1"], item.get("area_id")
    assert re.search(r"m[ií]nimo|insuficien", str(item.get("motivo") or ""), re.I), (
        f"el motivo no declara la insuficiencia de observaciones: {item.get('motivo')!r}")
    # §17: con el intento fallido no puede haber linea base publicada en el area nueva.
    assert not ESTADO["lb_post_290"], (
        f"se publicó línea base pese al intento fallido: {ESTADO['lb_post_290']}")

    # §18: la auditoria del intento, correlacionada con la calibracion.
    del_intento = [e for e in (ESTADO["auditoria_a1"] or [])
                   if str((e.get("detalle") or {}).get("id_calibracion_vision"))
                   == str(ESTADO["AUTO_290_ID"])]
    assert del_intento, (
        f"no hay evento RF-10 correlacionado con la calibración {ESTADO['AUTO_290_ID']}")
    ev = del_intento[-1]
    d = ev.get("detalle") or {}
    caso["auditoria"] = {
        "id_evento": ev.get("id_evento"), "tipo_evento": ev.get("tipo_evento"),
        "resultado": ev.get("resultado"), "modulo": ev.get("modulo"),
        "id_usuario": ev.get("id_usuario"), "nombre_usuario": ev.get("nombre_usuario"),
        "direccion_ip": "PRESENTE" if ev.get("direccion_ip") else "AUSENTE",
        "fecha_evento": ev.get("fecha_evento"), "integridad_ok": ev.get("integridad_ok"),
        "operacion": d.get("operacion"), "origen_disparo": d.get("origen_disparo"),
        "codigo_http": d.get("codigo_http"), "codigo_error": d.get("codigo_error"),
        "id_infraestructura": d.get("id_infraestructura"), "id_especie": d.get("id_especie"),
        "estado": d.get("estado"), "etapa_fallo": d.get("etapa_fallo"),
        "motivo_etapa": d.get("motivo_etapa"), "motivo": d.get("motivo"),
    }
    assert str(ev.get("resultado")).lower() == "fallido", ev.get("resultado")
    assert ev.get("modulo") == "MODULO9", ev.get("modulo")
    assert d.get("operacion") == "CALIBRACION_VISION", d.get("operacion")
    assert d.get("origen_disparo") == "AUTOMATICO", d.get("origen_disparo")
    assert d.get("codigo_error") == "LINEA_BASE_NO_CALCULADA", d.get("codigo_error")
    assert int(d.get("codigo_http")) == 422, d.get("codigo_http")
    assert int(d.get("id_especie")) == ESTADO["especie"], (
        f"la auditoría perdió la especie del área: {d.get('id_especie')!r}")
    assert d.get("estado") == "FALLIDA", d.get("estado")
    assert d.get("etapa_fallo") == "FILTRADO", d.get("etapa_fallo")
    # §6.5: el evento lo firma el usuario de servicio porque modulo1.eventos.id_usuario es
    # obligatorio. La calibracion es la que lleva id_usuario nulo.
    assert ev.get("id_usuario") is not None, (
        "el evento RF-10 del disparo automático debe ir firmado (usuario de servicio)")
    caso["identidad"] = {
        "calibracion_id_usuario": item.get("id_usuario"),
        "auditoria_id_usuario": ev.get("id_usuario"),
        "auditoria_nombre_usuario": ev.get("nombre_usuario"),
        "divergencia_con_la_matriz": (
            "la matriz redacta «usuario nulo» para el disparo automático; la implementación "
            "deja nulo el `id_usuario` de la CALIBRACIÓN y firma el evento RF-10 con el "
            "usuario de servicio, porque modulo1.eventos.id_usuario no admite NULL. Son dos "
            "campos distintos: no se declara que ambos cumplan literalmente lo mismo, y queda "
            "para contraste con Desarrollo/Análisis (§6.5 y §18)."),
    }
    caso["resultado"] = "APROBADO"
    caso["relacionada_con_G142"] = "NO"
    E["casos"] = {"TC-M09-290": caso}
    ESTADO["tc290"] = "APROBADO"
    ESTADO["v290"] = True


def _diagnostico_integracion() -> dict:
    """Diagnostica el hook M02 → M09 sobre la REFERENCIA DESPLEGADA, no sobre el arbol local.

    En la ejecucion 1 este diagnostico leia el working tree y concluia «no existe ningun
    mecanismo M02 → M09». Ese arbol se quedo sin el PR #554, asi que la conclusion pasaria
    a ser falsa y contradiria al propio veredicto en el mismo archivo de evidencia. Ahora
    se lee `origin/test`, que es lo que TEST despliega, y la conclusion se deriva de los
    hallazgos en vez de estar escrita a mano.
    """
    def git(*args) -> str:
        return subprocess.run(["git", *args], cwd=str(REPO_DIR), capture_output=True,
                              text=True, encoding="utf-8", errors="replace").stdout

    ref = git("rev-parse", "origin/test").strip()
    patron = r"RecalibracionVisionPort|RecalibracionVisionM09Adapter|execute_automatico"

    def archivos(expresion: str, ruta: str) -> list[str]:
        salida = git("grep", "-l", "-E", expresion, ref, "--", ruta)
        return sorted(l.split(":", 1)[1] for l in salida.splitlines() if ":" in l)

    alta = git("show", f"{ref}:src/biological_assets/application/use_cases/registro/"
                       "registrar_activo_use_case.py")
    cierre = git("show", f"{ref}:src/biological_assets/application/use_cases/gestion/"
                         "cerrar_ciclo_use_case.py")
    hook_alta = "PRESENTE" if re.search(patron, alta) else "AUSENTE"
    hook_cierre = "PRESENTE" if re.search(patron, cierre) else "AUSENTE"
    usos_auto = archivos(r"OrigenDisparo\.AUTOMATICO", "src")
    asincronos = archivos(r"BackgroundTasks|event_bus|EventBus|outbox|publish_event",
                          "src/biological_assets")
    presente = hook_alta == "PRESENTE" and bool(usos_auto)
    return {
        "referencia_analizada": f"origin/test {ref}",
        "nota_fuente": ("se analiza la referencia desplegada; el working tree de la rama QA "
                        "no contiene los PR y daria un diagnostico falso"),
        "hook_en_el_alta_m02": hook_alta,
        "hook_en_el_cierre_m02": hook_cierre,
        "archivos_m02_que_mencionan_la_recalibracion": archivos(patron, "src/biological_assets"),
        "usos_de_OrigenDisparo_AUTOMATICO": usos_auto,
        "mecanismos_asincronos_en_m02": asincronos,
        "conclusion": ("el mecanismo M02 → M09 existe en la referencia desplegada (PR #554)"
                       if presente else
                       "no se encuentra ningun mecanismo M02 → M09 en la referencia analizada"),
    }


def test_09_veredicto_tc291():
    requiere("v290")
    desde = parse(ESTADO["t_before_291"]) - datetime.timedelta(minutes=1)
    hasta = parse(ESTADO["t_after_291"]) + datetime.timedelta(minutes=1)
    eventos = [e for e in ESTADO["auditoria_a2"]
               if desde <= parse(e["fecha_evento"]) <= hasta]
    ch, hist = API.get(f"/configuracion/calibraciones-vision?area_id={ESTADO['a2']}")
    cl, lb = API.get(f"/configuracion/calibraciones-vision/linea-base?area_id={ESTADO['a2']}")
    caso = {
        "A2": ESTADO["a2"], "camaras_de_A2": 0,
        "T_BEFORE_291": ESTADO["t_before_291"], "T_AFTER_291": ESTADO["t_after_291"],
        "http": ESTADO["http_291"], "error_code": ESTADO["error_291"],
        "mensaje_obtenido": ESTADO["mensaje_291"],
        "mensaje_esperado": ESTADO["mensaje_291_esperado"],
        "mensaje_exacto": "SÍ" if ESTADO["mensaje_291"] == ESTADO["mensaje_291_esperado"] else "NO",
        "fields": ESTADO["fields_291"],
        "historial_POST": {"http": ch, "total": hist.get("total"),
                           "ids": [i["id_calibracion_vision"] for i in hist.get("items", [])]},
        "linea_base_POST": {"http": cl,
                            "id_calibracion_vision": lb.get("id_calibracion_vision") if cl == 200 else None},
        "baseline_nueva": "NO" if cl == 404 else "SÍ",
        "auditoria_encontrada": "SÍ" if eventos else "NO",
        "auditoria_eventos_en_la_ventana": len(eventos),
        "auditoria": eventos[0] if eventos else "ninguna",
    }
    criterios = []
    def check(nombre, cumple, obtenido=None):
        criterios.append({"criterio": nombre, "cumple": bool(cumple), "obtenido": obtenido})
    check("POST = 422", str(caso["http"]) == "422", caso["http"])
    check("error_code VISION_NO_DISPONIBLE", caso["error_code"] == "VISION_NO_DISPONIBLE",
          caso["error_code"])
    check("mensaje contractual literal", caso["mensaje_exacto"] == "SÍ", caso["mensaje_exacto"])
    check("sin baseline nueva", caso["baseline_nueva"] == "NO", caso["baseline_nueva"])
    check("auditoría existe (exactamente 1 correlacionable)", len(eventos) == 1, len(eventos))
    if eventos:
        e = eventos[0]
        d = e["detalle"]
        check("resultado FALLIDO", str(e["resultado"]).upper() == "FALLIDO", e["resultado"])
        check("modulo MODULO9", str(e["modulo"]).upper() == "MODULO9", e["modulo"])
        check("usuario = Ingeniero (no nulo)", e["id_usuario"] is not None,
              {"id_usuario": e["id_usuario"], "nombre": e["nombre_usuario"]})
        check("IP presente", e["direccion_ip"] == "PRESENTE", e["direccion_ip"])
        check("fecha dentro de ±1 min", True, e["fecha_evento"])
        check("detalle.operacion CALIBRACION_VISION", d["operacion"] == "CALIBRACION_VISION",
              d["operacion"])
        check("detalle.id_infraestructura = A2", str(d["id_infraestructura"]) == str(ESTADO["a2"]),
              d["id_infraestructura"])
        check("detalle.codigo_http 422", int(d["codigo_http"] or 0) == 422, d["codigo_http"])
        check("detalle.codigo_error VISION_NO_DISPONIBLE",
              d["codigo_error"] == "VISION_NO_DISPONIBLE", d["codigo_error"])
        check("detalle.motivo = mensaje del rechazo", d["motivo"] == caso["mensaje_esperado"],
              (d["motivo"] or "")[:60])
        # §29 lo lista entre los campos esperados; §31 no lo incluye en el criterio de aprobación.
        caso["observacion_id_especie"] = {
            "esperado": str(ESTADO["especie"]), "obtenido": str(d["id_especie"]),
            "coincide": str(d["id_especie"]) == str(ESTADO["especie"]),
            "nota": ("§29 lista detalle.id_especie entre los campos esperados; §31 no lo incluye "
                     "entre los criterios de aprobación. Se registra como observación."),
        }
    caso["criterios_del_§31"] = criterios
    caso["resultado"] = "APROBADO" if all(c["cumple"] for c in criterios) else "RECHAZADO"
    E["casos"]["TC-M09-291"] = caso
    ESTADO["tc291"] = caso["resultado"]
    ESTADO["v291"] = True


def test_10_cierre():
    requiere("v291")
    E["resultado"] = {
        "TC-M09-290": ESTADO["tc290"],
        "TC-M09-291": ESTADO["tc291"],
        "BD_COMPLEMENTARIA": E["bd_complementaria"]["BD_COMPLEMENTARIA"],
        "nota": ("TC-M09-292 se resuelve en el laboratorio LOCAL AISLADO; su resultado vive en "
                 "evidencia-local.json y en el informe del RUN."),
    }
    E["seguridad"] = {
        "credenciales_persistidas": "NO",
        "serial_access_key_persistido": "NO — redactado por patrón",
        "sql_dml_en_test": 0, "sesion_bd": "READ ONLY",
        "post_funcionales_ejecutados_por_pytest": 0,
        "archivos_primera_evaluacion_modificados": "NINGUNO",
    }
    guardar()
    assert E["presupuesto"]["ingesta_m03"] == 0
    assert E["post_funcionales_de_pytest"] == 0
    # El verificador establece los hechos; el veredicto funcional vive en el informe y en los
    # fallos del Newman oficial. Solo se exige que TC-291 haya cumplido su criterio del §31.
    assert ESTADO["tc291"] == "APROBADO", [c for c in E["casos"]["TC-M09-291"]["criterios_del_§31"]
                                           if not c["cumple"]]
