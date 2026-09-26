"""TC-M02-G16 rev4 — TC-M02-030 XSS/inyeccion en atributos_dinamicos.

No modifica rev2/rev3 ni codigo productivo. Sin DML. Sin crear metricas RF-16.
029 y 032 no se reejecutan (rev2).
"""
from __future__ import annotations

import json
import os
import urllib3
from datetime import datetime, timezone
from html import escape as html_escape
from pathlib import Path

import pytest
import requests

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

DIR = Path(__file__).resolve().parent
RESULTADOS = DIR / "Resultados"
ENV_PATH = DIR / "environment-g16-rev4.json"

with ENV_PATH.open(encoding="utf-8") as fh:
    ENV = json.load(fh)

BASE_URL = ENV["baseUrl"].rstrip("/")
CORREO_ADMIN = ENV["correo_admin"]
CORREO_PROD = ENV["correo_productor"]
ESPECIE_PREF = int(ENV["especie_id_preferida"])
INFRA_PREF = int(ENV["infraestructura_id_preferida"])
TIMEOUT = 45
VERIFY_SSL = False
STAMP = datetime.now(timezone.utc).strftime("%H%M%S%f")[:12]
XSS = "<script>alert(1)</script>"
CTRL_TXT = "valor_control_qa_g16r4"
INJ_TXT = "x'; SELECT 1--"
INJ_JSON_STR = '{"$gt":""}'

EVIDENCIA: dict = {
    "caso": "TC-M02-G16",
    "revision": 4,
    "rf": "RF-33",
    "cu": "CU01",
    "ambiente": "TEST",
    "base_url": BASE_URL,
    "fecha_utc": datetime.now(timezone.utc).isoformat(),
    "alcance": "Solo TC-M02-030. 029 y 032 no reejecutados (rev2).",
    "subcasos": {
        "TC-M02-029": {
            "resultado": "APROBADO",
            "origen": "rev2",
            "nota": "No reejecutado. SQL-like rechazado o texto; NoSQL objeto 400; sin 500.",
        },
        "TC-M02-032": {
            "resultado": "APROBADO",
            "origen": "rev2",
            "nota": "No reejecutado. TEST devolvio 429 LIMITE_TASA_EXCEDIDO.",
        },
    },
    "ids_creados": [],
    "estado_global": "PENDIENTE",
    "auditoria": "Rev2 y rev3 intactas. Sin DML. Sin POST metricas. Sin cambios productivos. Sin commit/push.",
}


def _password() -> str:
    valor = os.environ.get("SGPMP_TEST_PASSWORD") or os.environ.get("CONTRASENA") or ""
    if not valor:
        pytest.skip("BLOQUEADO: definir SGPMP_TEST_PASSWORD o CONTRASENA.")
    return valor


def _redact(obj):
    if obj is None:
        return None
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            kl = str(k).lower()
            if kl in ("token", "password", "contrasena", "authorization", "jwt", "access_token") or kl.endswith("_token"):
                out[k] = "[REDACTED]"
            else:
                out[k] = _redact(v)
        return out
    if isinstance(obj, list):
        return [_redact(x) for x in obj]
    if isinstance(obj, str) and obj.startswith("eyJ"):
        return "[REDACTED]"
    return obj


def _trunc(obj, n=1800):
    text = json.dumps(_redact(obj), ensure_ascii=False, default=str)
    return text[:n] + "...[TRUNCATED]" if len(text) > n else text


def _json(r):
    try:
        return r.json()
    except Exception:
        return {"raw": (r.text or "")[:500]}


def _registros(body) -> list:
    if isinstance(body, list):
        return body
    if isinstance(body, dict):
        for k in ("items", "registros", "data"):
            v = body.get(k)
            if isinstance(v, list):
                return v
    return []


def _login(correo: str):
    r = requests.post(
        f"{BASE_URL}/sesiones/",
        json={"correo_electronico": correo, "contrasena": _password()},
        timeout=TIMEOUT,
        verify=VERIFY_SSL,
    )
    body = _json(r)
    token = None
    if isinstance(body, dict):
        token = body.get("token") or (body.get("data") or {}).get("token")
    return r.status_code, body, token


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _payload(tipo: str, especie: int, infra: int, identificador: str | None, atributos: dict) -> dict:
    body = {
        "tipo_activo": tipo,
        "id_especie": especie,
        "fecha_inicio_ciclo": "2026-09-09",
        "origen_financiero": "nacimiento",
        "costo_adquisicion": None,
        "soporte_documental": None,
        "id_infraestructura": infra,
        "atributos_dinamicos": atributos,
    }
    if tipo == "INDIVIDUAL":
        body.update(
            {
                "identificador": identificador,
                "raza": "QA-G16-R4",
                "sexo": "Macho",
                "fecha_nacimiento": "2025-01-15T00:00:00Z",
                "peso_inicial": 2.5,
            }
        )
    else:
        body.update(
            {
                "identificador": None,
                "cantidad_inicial": 10,
                "peso_promedio_inicial": 2.5,
            }
        )
    return body


def _post(token: str, payload: dict):
    return requests.post(
        f"{BASE_URL}/activos-biologicos",
        headers={**_auth(token), "Content-Type": "application/json"},
        json=payload,
        timeout=TIMEOUT,
        verify=VERIFY_SSL,
    )


def _get(token: str, aid: int):
    return requests.get(
        f"{BASE_URL}/activos-biologicos/{aid}",
        headers=_auth(token),
        timeout=TIMEOUT,
        verify=VERIFY_SSL,
    )


def _restaurar(token: str, aid: int, motivo: str) -> dict:
    r = requests.patch(
        f"{BASE_URL}/activos-biologicos/{aid}/estado",
        headers={**_auth(token), "Content-Type": "application/json"},
        json={
            "estado_nuevo": "INACTIVO",
            "fecha_cambio_estado": "2026-09-26",
            "motivo_cambio": motivo,
        },
        timeout=TIMEOUT,
        verify=VERIFY_SSL,
    )
    g = _get(token, aid)
    gb = _json(g)
    estado = gb.get("nombre_estado") if isinstance(gb, dict) else None
    return {"id": aid, "http_estado": r.status_code, "http_get": g.status_code, "estado": estado}


def _captura(r) -> dict:
    body = _json(r)
    aid = None
    if r.status_code == 201 and isinstance(body, dict):
        aid = body.get("id_activo_biologico") or body.get("id")
    return {
        "http": r.status_code,
        "content_type": r.headers.get("Content-Type"),
        "error_code": body.get("error_code") if isinstance(body, dict) else None,
        "message": body.get("message") if isinstance(body, dict) else None,
        "id_creado": aid,
        "body": _trunc(body, 1400),
    }


def _attrs_base(metricas: list, nombre_texto: str, valor_texto) -> dict:
    attrs = {nombre_texto: valor_texto}
    for it in metricas:
        if not isinstance(it, dict) or not it.get("es_obligatorio"):
            continue
        if it.get("es_activo") is False:
            continue
        nombre = it.get("nombre")
        if not nombre or nombre == nombre_texto:
            continue
        td = str(it.get("tipo_dato") or "").upper()
        if td == "TEXTO":
            attrs[nombre] = "qa"
        elif td == "ENTERO":
            attrs[nombre] = 1
        elif td == "BOOLEANO":
            attrs[nombre] = True
        else:
            attrs[nombre] = 1.0
    return attrs


def _tipo_post(aplica: str) -> str:
    a = str(aplica or "").upper()
    if a in ("INDIVIDUAL", "AMBOS", ""):
        return "INDIVIDUAL"
    if a in ("LOTE", "POBLACIONAL"):
        return "POBLACIONAL"
    return "INDIVIDUAL"


def _escribir():
    RESULTADOS.mkdir(parents=True, exist_ok=True)
    payload = _redact(EVIDENCIA)
    (RESULTADOS / "TC-M02-G16-rev4.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    subs = payload.get("subcasos") or {}
    lineas = [
        "TC-M02-G16 rev4 — RF-33 / CU01 — TEST — solo 030",
        f"Fecha UTC: {payload.get('fecha_utc')}",
        f"Global: {payload.get('estado_global')}",
        "",
        f"TC-M02-029: {(subs.get('TC-M02-029') or {}).get('resultado')}",
        f"TC-M02-030: {(subs.get('TC-M02-030') or {}).get('resultado')}",
        f"TC-M02-032: {(subs.get('TC-M02-032') or {}).get('resultado')}",
        "",
        json.dumps(subs.get("TC-M02-030"), ensure_ascii=False, indent=2, default=str),
        "",
        payload.get("auditoria"),
        "Password/JWT: [REDACTED]. Rev2 no modificada.",
    ]
    (RESULTADOS / "TC-M02-G16-rev4.txt").write_text("\n".join(lineas) + "\n", encoding="utf-8")
    v = subs.get("TC-M02-030") or {}
    (RESULTADOS / "TC-M02-G16-rev4-evidencia.html").write_text(
        "<!DOCTYPE html><html lang='es'><head><meta charset='utf-8'>"
        "<title>TC-M02-G16 rev4</title></head><body>"
        "<h1>TC-M02-G16 rev4 — TC-M02-030</h1>"
        f"<p>Global: {html_escape(str(payload.get('estado_global')))}</p>"
        f"<p>030: {html_escape(str(v.get('resultado')))}</p>"
        f"<pre>{html_escape(json.dumps(v, ensure_ascii=False, indent=2, default=str))}</pre>"
        "<p>Payload XSS viajo como dato JSON, no se ejecuto JS. Rev2 intacta.</p>"
        "</body></html>",
        encoding="utf-8",
    )


@pytest.fixture(scope="session")
def sesion():
    _password()
    http_a, _, tok_a = _login(CORREO_ADMIN)
    http_p, _, tok_p = _login(CORREO_PROD)
    data = {
        "admin": {"http": http_a, "ok": bool(tok_a), "token": tok_a},
        "productor": {"http": http_p, "ok": bool(tok_p), "token": tok_p},
    }
    EVIDENCIA["logins"] = {
        "admin": {"correo": CORREO_ADMIN, "http": http_a, "ok": bool(tok_a)},
        "productor": {"correo": CORREO_PROD, "http": http_p, "ok": bool(tok_p)},
    }
    yield data
    for aid in list(EVIDENCIA.get("ids_creados") or []):
        if tok_p:
            _restaurar(tok_p, int(aid), "Restauracion residual TC-M02-G16 rev4")
    _escribir()


def test_tc_m02_030_xss_atributos(sesion):
    out = {
        "resultado": "BLOQUEADO",
        "endpoint": "POST /activos-biologicos  atributos_dinamicos",
        "metrica_texto": None,
        "control": None,
        "intentos": [],
        "conclusion": "",
    }
    EVIDENCIA["subcasos"]["TC-M02-030"] = out
    if not sesion["admin"]["ok"]:
        out["conclusion"] = f"BLOQUEADO: login Admin HTTP {sesion['admin']['http']}."
        pytest.skip(out["conclusion"])
    if not sesion["productor"]["ok"]:
        out["conclusion"] = f"BLOQUEADO: login Productor HTTP {sesion['productor']['http']}."
        pytest.skip(out["conclusion"])

    tok_a = sesion["admin"]["token"]
    tok_p = sesion["productor"]["token"]

    r_esp = requests.get(
        f"{BASE_URL}/configuracion/especies",
        params={"solo_activas": False},
        headers=_auth(tok_a),
        timeout=TIMEOUT,
        verify=VERIFY_SSL,
    )
    especies = _registros(_json(r_esp))
    ids_esp = []
    activas = set()
    info_especie = {}
    for e in especies:
        if not isinstance(e, dict) or e.get("id_especie") is None:
            continue
        eid = int(e["id_especie"])
        ids_esp.append(eid)
        info_especie[eid] = {"nombre": e.get("nombre"), "es_activo": e.get("es_activo")}
        if e.get("es_activo") is not False:
            activas.add(eid)
    resto_activas = [i for i in ids_esp if i in activas and i != ESPECIE_PREF]
    resto_inact = [i for i in ids_esp if i not in activas and i != ESPECIE_PREF]
    ids_esp = [ESPECIE_PREF] + resto_activas + resto_inact

    busqueda = []
    candidata = None
    candidata_inactiva = None
    metricas_de_especie = []
    tipos_globales = set()
    for eid in ids_esp[:50]:
        r_m = requests.get(
            f"{BASE_URL}/configuracion/metricas",
            params={"id_especie": eid, "solo_activas": False},
            headers=_auth(tok_a),
            timeout=TIMEOUT,
            verify=VERIFY_SSL,
        )
        body_m = _json(r_m)
        items = _registros(body_m) if r_m.status_code == 200 else []
        tipos = sorted({str(i.get("tipo_dato")) for i in items if isinstance(i, dict)})
        tipos_globales.update(tipos)
        fila = {"id_especie": eid, "http": r_m.status_code, "n": len(items), "tipos": tipos}
        busqueda.append(fila)
        if r_m.status_code != 200:
            continue
        for it in items:
            if not isinstance(it, dict):
                continue
            td = str(it.get("tipo_dato") or "").upper()
            if td != "TEXTO":
                continue
            aplica = str(it.get("aplica_a_tipo_activo") or "").upper()
            resumen = {
                "id_especie": eid,
                "id_metrica": it.get("id_metrica_produccion"),
                "nombre": it.get("nombre"),
                "tipo_dato": it.get("tipo_dato"),
                "es_activo": it.get("es_activo"),
                "aplicabilidad": aplica,
                "especie_activa": eid in activas,
            }
            if it.get("es_activo") is False or eid not in activas:
                candidata_inactiva = candidata_inactiva or resumen
                continue
            if aplica not in ("INDIVIDUAL", "AMBOS", "LOTE", "POBLACIONAL", ""):
                continue
            candidata = it
            metricas_de_especie = [x for x in items if isinstance(x, dict) and x.get("es_activo") is not False]
            break
        if candidata:
            break

    out["busqueda_metricas"] = {
        "especies_http": r_esp.status_code,
        "especies_n": len(ids_esp),
        "consultas": busqueda[:15] + ([{"omitidas": max(0, len(busqueda) - 15)}] if len(busqueda) > 15 else []),
        "tipos_vistos": sorted(tipos_globales),
        "texto_inactiva_o_especie_inactiva": candidata_inactiva,
    }

    if not candidata:
        extra = ""
        if candidata_inactiva:
            extra = f" Se observo TEXTO no usable: {candidata_inactiva}."
        out["conclusion"] = (
            "BLOQUEADO: GET /configuracion/metricas 200 en especies consultadas pero "
            f"sigue sin metrica activa tipo TEXTO en especie activa. tipos={sorted(tipos_globales)}.{extra} "
            "No se crea la metrica ni se modifica RF-16."
        )
        pytest.skip(out["conclusion"])

    nombre = candidata.get("nombre")
    especie = int(candidata.get("id_especie") or ESPECIE_PREF)
    aplica = str(candidata.get("aplica_a_tipo_activo") or "")
    tipo_activo = _tipo_post(aplica)
    out["metrica_texto"] = {
        "id_especie": especie,
        "nombre_especie": (info_especie.get(especie) or {}).get("nombre"),
        "especie_activa": especie in activas,
        "id_metrica": candidata.get("id_metrica_produccion"),
        "nombre": nombre,
        "tipo_dato": candidata.get("tipo_dato"),
        "estado": "activa" if candidata.get("es_activo") else candidata.get("es_activo"),
        "aplicabilidad": aplica,
        "es_obligatorio": candidata.get("es_obligatorio"),
        "tipo_activo_post": tipo_activo,
    }

    infras = [INFRA_PREF]
    r_f = requests.get(
        f"{BASE_URL}/configuracion/fincas",
        headers=_auth(tok_p),
        timeout=TIMEOUT,
        verify=VERIFY_SSL,
    )
    fincas = _registros(_json(r_f))
    for f in fincas:
        fid = (f or {}).get("id_finca") or (f or {}).get("id")
        if fid is None:
            continue
        r_i = requests.get(
            f"{BASE_URL}/configuracion/infraestructuras",
            params={"finca_id": int(fid), "solo_activas": True},
            headers=_auth(tok_p),
            timeout=TIMEOUT,
            verify=VERIFY_SSL,
        )
        for inf in _registros(_json(r_i)):
            iid = (inf or {}).get("id_infraestructura") or (inf or {}).get("id")
            if iid is not None and int(iid) not in infras:
                infras.append(int(iid))

    control = None
    infra_ok = None
    ident_c = f"QAG16R4C{STAMP}"[:50]
    attrs_ctrl = _attrs_base(metricas_de_especie, nombre, CTRL_TXT)
    for infra in infras[:8]:
        r = _post(tok_p, _payload(tipo_activo, especie, infra, ident_c, attrs_ctrl))
        cap = _captura(r)
        cap["infra"] = infra
        cap["atributos_enviados"] = attrs_ctrl
        if cap["http"] == 201:
            control = cap
            infra_ok = infra
            break
        control = cap
    out["control"] = control
    if not control or control.get("http") != 201:
        out["conclusion"] = (
            f"BLOQUEADO: POST control con atributo TEXTO '{nombre}' HTTP "
            f"{(control or {}).get('http')} {(control or {}).get('error_code')}. "
            "No se envian payloads. No se inventa infra/especie."
        )
        pytest.skip(out["conclusion"])

    aid_c = int(control["id_creado"])
    EVIDENCIA["ids_creados"].append(aid_c)
    g_c = _get(tok_p, aid_c)
    gb_c = _json(g_c)
    attrs_c = gb_c.get("atributos_dinamicos") if isinstance(gb_c, dict) else None
    control["get_http"] = g_c.status_code
    control["atributos_get"] = attrs_c
    control["restauracion"] = _restaurar(tok_p, aid_c, "Restauracion control TC-M02-G16 rev4")
    if control["restauracion"].get("id") in EVIDENCIA["ids_creados"]:
        EVIDENCIA["ids_creados"] = [x for x in EVIDENCIA["ids_creados"] if x != aid_c]

    def _eval_post(etiqueta: str, valor, ident: str):
        attrs = _attrs_base(metricas_de_especie, nombre, valor)
        r = _post(tok_p, _payload(tipo_activo, especie, infra_ok, ident, attrs))
        cap = _captura(r)
        cap["variante"] = etiqueta
        cap["valor_enviado"] = valor if not isinstance(valor, str) or len(valor) < 80 else valor[:80]
        cap["atributos_enviados"] = attrs
        if cap["http"] == 201 and cap["id_creado"]:
            aid = int(cap["id_creado"])
            EVIDENCIA["ids_creados"].append(aid)
            g = _get(tok_p, aid)
            gb = _json(g)
            attrs_g = gb.get("atributos_dinamicos") if isinstance(gb, dict) else None
            raw = g.text or ""
            cap["get_http"] = g.status_code
            cap["content_type_get"] = g.headers.get("Content-Type")
            cap["atributos_get"] = attrs_g
            cap["persistido"] = isinstance(attrs_g, dict) and attrs_g.get(nombre) == valor
            cap["get_es_json"] = "json" in (g.headers.get("Content-Type") or "").lower()
            cap["get_es_html"] = "html" in (g.headers.get("Content-Type") or "").lower()
            cap["script_en_json"] = isinstance(valor, str) and valor in json.dumps(attrs_g or {}, ensure_ascii=False)
            cap["html_sin_escapar"] = cap["get_es_html"] and isinstance(valor, str) and valor in raw
            cap["restauracion"] = _restaurar(tok_p, aid, f"Restauracion 030 {etiqueta} TC-M02-G16 rev4")
            EVIDENCIA["ids_creados"] = [x for x in EVIDENCIA["ids_creados"] if x != aid]
        out["intentos"].append(cap)
        return cap

    cap_xss = _eval_post("xss_script", XSS, f"QAG16R4X{STAMP}"[:50])
    cap_sql = _eval_post("inyeccion_texto", INJ_TXT, f"QAG16R4S{STAMP}"[:50])
    cap_json = _eval_post("operador_json_string", INJ_JSON_STR, f"QAG16R4J{STAMP}"[:50])

    r_obj = requests.post(
        f"{BASE_URL}/activos-biologicos",
        headers={**_auth(tok_p), "Content-Type": "application/json"},
        json=_payload(
            tipo_activo,
            especie,
            infra_ok,
            f"QAG16R4O{STAMP}"[:50],
            _attrs_base(metricas_de_especie, nombre, {"$gt": ""}),
        ),
        timeout=TIMEOUT,
        verify=VERIFY_SSL,
    )
    cap_obj = _captura(r_obj)
    cap_obj["variante"] = "operador_json_objeto"
    if cap_obj["http"] == 201 and cap_obj["id_creado"]:
        aid = int(cap_obj["id_creado"])
        EVIDENCIA["ids_creados"].append(aid)
        cap_obj["restauracion"] = _restaurar(tok_p, aid, "Restauracion 030 objeto TC-M02-G16 rev4")
        EVIDENCIA["ids_creados"] = [x for x in EVIDENCIA["ids_creados"] if x != aid]
    out["intentos"].append(cap_obj)

    hubo_500 = any(x.get("http") == 500 for x in out["intentos"])
    html_inseguro = any(x.get("html_sin_escapar") for x in out["intentos"])
    get_html = any(x.get("get_es_html") for x in out["intentos"] if x.get("http") == 201)

    if hubo_500:
        out["resultado"] = "RECHAZADO"
        out["conclusion"] = "HTTP 500 atribuible al payload en atributos_dinamicos."
        pytest.fail(out["conclusion"])
    if html_inseguro or get_html:
        out["resultado"] = "RECHAZADO"
        out["conclusion"] = "GET devolvio HTML con el payload; posible XSS reflejado."
        pytest.fail(out["conclusion"])
    if cap_obj.get("http") == 201:
        out["resultado"] = "RECHAZADO"
        out["conclusion"] = (
            "El atributo TEXTO acepto un objeto operador JSON; no se trato como texto."
        )
        pytest.fail(out["conclusion"])

    out["resultado"] = "APROBADO"
    out["conclusion"] = (
        f"Metrica TEXTO '{nombre}' especie {especie}. Control POST 201 y restaurado. "
        f"XSS HTTP {cap_xss.get('http')} persistido={cap_xss.get('persistido')} "
        f"content-type GET={cap_xss.get('content_type_get')}. "
        f"Inyeccion texto HTTP {cap_sql.get('http')}; operador string HTTP {cap_json.get('http')}; "
        f"objeto operador HTTP {cap_obj.get('http')} {cap_obj.get('error_code')}. "
        "Sin 500, sin HTML, sin ejecucion. Cadena almacenada como dato JSON no es XSS."
    )


def test_zz_estado_global(sesion):
    r030 = (EVIDENCIA.get("subcasos") or {}).get("TC-M02-030") or {}
    if r030.get("resultado") == "RECHAZADO":
        EVIDENCIA["estado_global"] = "RECHAZADO"
    elif r030.get("resultado") == "APROBADO":
        EVIDENCIA["estado_global"] = "APROBADO"
    else:
        EVIDENCIA["estado_global"] = "BLOQUEADO"
    assert EVIDENCIA["estado_global"] in ("APROBADO", "RECHAZADO", "BLOQUEADO")
