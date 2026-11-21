"""TC-M02-G17 rev4 — solo TC-M02-187 (atributo dinamico obligatorio ausente).

No modifica rev1/rev2/rev3, RF-16 ni codigo productivo. Restaura via PATCH /estado.
188 y 189 no se reejecutan (APROBADO rev3).
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
ENV_PATH = DIR / "environment-g17-rev4.json"

with ENV_PATH.open(encoding="utf-8") as fh:
    ENV = json.load(fh)

BASE_URL = ENV["baseUrl"].rstrip("/")
CORREO_ADMIN = ENV["correo_admin"]
CORREO_PROD = ENV["correo_productor"]
INFRA_PREF = int(ENV["infraestructura_id_preferida"])
ESPECIE_PREF = int(ENV["especie_id_preferida"])
TIMEOUT = 45
VERIFY_SSL = False
STAMP = datetime.now(timezone.utc).strftime("%H%M%S%f")[:12]

EVIDENCIA: dict = {
    "caso": "TC-M02-G17",
    "revision": 4,
    "rf": ["RF-33", "RF-16"],
    "cu": "CU01",
    "ambiente": "TEST",
    "base_url": BASE_URL,
    "fecha_utc": datetime.now(timezone.utc).isoformat(),
    "alcance": "Solo TC-M02-187. 188 y 189 no reejecutados (APROBADO rev3).",
    "comparacion_historica": {
        "rev2_rev3": "187 BLOQUEADO: no habia metrica activa+obligatoria aplicable a INDIVIDUAL.",
        "rev4": "Reevaluacion con precondicion DBA; el resultado se determina por ejecucion.",
    },
    "contrato": {
        "POST": "POST /activos-biologicos",
        "ATRIBUTO_REQUERIDO": "BusinessRuleError HTTP 422",
        "aplica_individual": "INDIVIDUAL o AMBOS (adapter M09: LOTE = poblacional)",
    },
    "subcasos": {
        "TC-M02-188": {
            "resultado": "APROBADO",
            "origen": "rev3",
            "nota": "No reejecutado. HTTP 422 ATRIBUTO_TIPO_INVALIDO.",
        },
        "TC-M02-189": {
            "resultado": "APROBADO",
            "origen": "rev3",
            "nota": "No reejecutado. transferencia_interna aceptada.",
        },
    },
    "ids_creados": [],
    "estado_global": "PENDIENTE",
    "auditoria": "Rev1/rev2/rev3 intactas. Sin DML. Sin cambios RF-16 ni productivos. Sin commit/push.",
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
        for k in ("registros", "items", "data"):
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


def _aplica_individual(aplica: str) -> bool:
    a = str(aplica or "").upper()
    return a in ("INDIVIDUAL", "AMBOS", "")


def _valor(metrica: dict):
    td = str(metrica.get("tipo_dato") or "").upper()
    nombre = str(metrica.get("nombre") or "").lower()
    if td == "BOOLEANO":
        return True
    if td == "TEXTO":
        return "QA"
    if td == "ENTERO":
        return 25 if "destete" in nombre else 1
    if "destete" in nombre:
        return 25
    return 1.0


def _payload(especie: int, infra: int, identificador: str, atributos: dict) -> dict:
    return {
        "tipo_activo": "INDIVIDUAL",
        "id_especie": especie,
        "fecha_inicio_ciclo": "2026-09-09",
        "origen_financiero": "nacimiento",
        "costo_adquisicion": None,
        "soporte_documental": None,
        "id_infraestructura": infra,
        "atributos_dinamicos": atributos,
        "identificador": identificador,
        "raza": "QA-G17-R4",
        "sexo": "Macho",
        "fecha_nacimiento": "2025-01-15T00:00:00Z",
        "peso_inicial": 2.5,
    }


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
    return {
        "id": aid,
        "http_estado": r.status_code,
        "http_get": g.status_code,
        "estado": gb.get("nombre_estado") if isinstance(gb, dict) else None,
    }


def _cap(r: requests.Response) -> dict:
    body = _json(r)
    aid = None
    if r.status_code == 201 and isinstance(body, dict):
        aid = body.get("id_activo_biologico") or body.get("id")
    return {
        "http": r.status_code,
        "error_code": body.get("error_code") if isinstance(body, dict) else None,
        "message": body.get("message") if isinstance(body, dict) else None,
        "fields": body.get("fields") if isinstance(body, dict) else None,
        "id_creado": aid,
        "claves_atributos_enviados": None,
        "body": _trunc(body, 1400),
    }


def _buscar_identificador(token: str, ident: str) -> dict:
    r = requests.get(
        f"{BASE_URL}/activos-biologicos",
        params={"pagina": 1, "page_size": 100},
        headers=_auth(token),
        timeout=TIMEOUT,
        verify=VERIFY_SSL,
    )
    hits = []
    if r.status_code == 200:
        for it in _registros(_json(r)):
            if isinstance(it, dict) and it.get("identificador") == ident:
                hits.append(it.get("id_activo_biologico"))
    return {"http": r.status_code, "ids": hits}


def _escribir():
    RESULTADOS.mkdir(parents=True, exist_ok=True)
    payload = _redact(EVIDENCIA)
    (RESULTADOS / "TC-M02-G17-rev4.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    subs = payload.get("subcasos") or {}
    lineas = [
        "TC-M02-G17 rev4 — RF-33 / RF-16 — TEST — solo 187",
        f"Fecha UTC: {payload.get('fecha_utc')}",
        f"Global: {payload.get('estado_global')}",
        "",
        f"TC-M02-187: {(subs.get('TC-M02-187') or {}).get('resultado')}",
        f"TC-M02-188: {(subs.get('TC-M02-188') or {}).get('resultado')}",
        f"TC-M02-189: {(subs.get('TC-M02-189') or {}).get('resultado')}",
        "",
        json.dumps(subs.get("TC-M02-187"), ensure_ascii=False, indent=2, default=str),
        "",
        payload.get("auditoria"),
        "Password/JWT: [REDACTED]. Rev1/rev2/rev3 no modificadas.",
    ]
    (RESULTADOS / "TC-M02-G17-rev4.txt").write_text("\n".join(lineas) + "\n", encoding="utf-8")
    v = subs.get("TC-M02-187") or {}
    (RESULTADOS / "TC-M02-G17-rev4-evidencia.html").write_text(
        "<!DOCTYPE html><html lang='es'><head><meta charset='utf-8'>"
        "<title>TC-M02-G17 rev4</title></head><body>"
        "<h1>TC-M02-G17 rev4 — TC-M02-187</h1>"
        f"<p>Global: {html_escape(str(payload.get('estado_global')))}</p>"
        f"<p>187: {html_escape(str(v.get('resultado')))}</p>"
        f"<pre>{html_escape(json.dumps(v, ensure_ascii=False, indent=2, default=str))}</pre>"
        "<p>Rev1/rev2/rev3 intactas. 188/189 no reejecutados.</p>"
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
    if tok_p:
        for aid in list(EVIDENCIA.get("ids_creados") or []):
            _restaurar(tok_p, int(aid), "Restauracion residual TC-M02-G17 rev4")
    _escribir()


def test_tc_m02_187_atributo_obligatorio_ausente(sesion):
    out = {
        "resultado": "BLOQUEADO",
        "endpoint": "POST /activos-biologicos",
        "metrica": None,
        "control": None,
        "omision": None,
        "null": None,
        "conclusion": "",
    }
    EVIDENCIA["subcasos"]["TC-M02-187"] = out
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
    info = {}
    activas = []
    for e in especies:
        if not isinstance(e, dict) or e.get("id_especie") is None:
            continue
        eid = int(e["id_especie"])
        info[eid] = {"nombre": e.get("nombre"), "es_activo": e.get("es_activo")}
        if e.get("es_activo") is not False:
            activas.append(eid)
    orden = [ESPECIE_PREF] + [i for i in activas if i != ESPECIE_PREF]

    scan = []
    objetivo = None
    otras_oblig = []
    metricas_especie = []
    for eid in orden[:40]:
        r_m = requests.get(
            f"{BASE_URL}/configuracion/metricas",
            params={"id_especie": eid, "solo_activas": False},
            headers=_auth(tok_a),
            timeout=TIMEOUT,
            verify=VERIFY_SSL,
        )
        items = _registros(_json(r_m)) if r_m.status_code == 200 else []
        scan.append({"id_especie": eid, "http": r_m.status_code, "n": len(items), "especie_activa": eid in activas})
        if r_m.status_code != 200 or eid not in activas:
            continue
        cands = []
        for it in items:
            if not isinstance(it, dict):
                continue
            if it.get("es_activo") is False:
                continue
            if it.get("es_obligatorio") is not True:
                continue
            if not _aplica_individual(it.get("aplica_a_tipo_activo")):
                continue
            cands.append(it)
        if cands:
            objetivo = cands[0]
            otras_oblig = cands[1:]
            metricas_especie = [x for x in items if isinstance(x, dict) and x.get("es_activo") is not False]
            objetivo["_id_especie"] = eid
            break

    out["busqueda"] = {"especies_http": r_esp.status_code, "scan": scan[:20], "encontrada": bool(objetivo)}
    if not objetivo:
        out["conclusion"] = (
            "BLOQUEADO: no hay metrica activa, obligatoria y aplicable a INDIVIDUAL "
            "en una especie activa. No se modifica RF-16."
        )
        pytest.skip(out["conclusion"])

    eid = int(objetivo["_id_especie"])
    nombre = objetivo.get("nombre")
    out["metrica"] = {
        "id_especie": eid,
        "nombre_especie": (info.get(eid) or {}).get("nombre"),
        "estado_especie": "activa" if eid in activas else "inactiva",
        "id_metrica": objetivo.get("id_metrica_produccion"),
        "nombre": nombre,
        "tipo_dato": objetivo.get("tipo_dato"),
        "es_obligatorio": objetivo.get("es_obligatorio"),
        "aplicabilidad": objetivo.get("aplica_a_tipo_activo"),
        "estado_metrica": "activa" if objetivo.get("es_activo") else objetivo.get("es_activo"),
        "otras_obligatorias": [x.get("nombre") for x in otras_oblig],
    }

    attrs_ctrl = {nombre: _valor(objetivo)}
    for extra in otras_oblig:
        attrs_ctrl[extra["nombre"]] = _valor(extra)
    # incluir cualquier otro obligatorio de la misma especie/INDIVIDUAL no en cands (defensivo)
    for it in metricas_especie:
        if it.get("es_obligatorio") is True and _aplica_individual(it.get("aplica_a_tipo_activo")):
            if it.get("nombre") and it.get("nombre") not in attrs_ctrl:
                attrs_ctrl[it["nombre"]] = _valor(it)

    infras = [INFRA_PREF]
    r_f = requests.get(f"{BASE_URL}/configuracion/fincas", headers=_auth(tok_p), timeout=TIMEOUT, verify=VERIFY_SSL)
    for f in _registros(_json(r_f)):
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

    ident_c = f"QAG17R4C{STAMP}"[:50]
    control = None
    infra_ok = None
    for infra in infras[:8]:
        r_c = _post(tok_p, _payload(eid, infra, ident_c, attrs_ctrl))
        cap = _cap(r_c)
        cap["infra"] = infra
        cap["claves_atributos_enviados"] = sorted(attrs_ctrl.keys())
        cap["atributos_enviados"] = attrs_ctrl
        if cap["http"] == 201:
            control = cap
            infra_ok = infra
            break
        control = cap
    out["control"] = control
    if not control or control.get("http") != 201:
        out["conclusion"] = (
            f"BLOQUEADO: POST control HTTP {(control or {}).get('http')} "
            f"{(control or {}).get('error_code')} incluyendo '{nombre}'. No se evalua omision."
        )
        pytest.skip(out["conclusion"])

    aid_c = int(control["id_creado"])
    EVIDENCIA["ids_creados"].append(aid_c)
    out["control"]["restauracion"] = _restaurar(tok_p, aid_c, "Restauracion control 187 TC-M02-G17 rev4")
    EVIDENCIA["ids_creados"] = [x for x in EVIDENCIA["ids_creados"] if x != aid_c]

    attrs_omit = {k: v for k, v in attrs_ctrl.items() if k != nombre}
    assert nombre not in attrs_omit
    ident_o = f"QAG17R4O{STAMP}"[:50]
    r_o = _post(tok_p, _payload(eid, infra_ok, ident_o, attrs_omit))
    out["omision"] = _cap(r_o)
    out["omision"]["claves_atributos_enviados"] = sorted(attrs_omit.keys())
    out["omision"]["clave_omitida"] = nombre
    out["omision"]["clave_presente_en_json"] = nombre in attrs_omit
    if out["omision"]["http"] == 201 and out["omision"]["id_creado"]:
        aid = int(out["omision"]["id_creado"])
        EVIDENCIA["ids_creados"].append(aid)
        out["omision"]["restauracion"] = _restaurar(tok_p, aid, "Restauracion omision 187 (no debio crear)")
        EVIDENCIA["ids_creados"] = [x for x in EVIDENCIA["ids_creados"] if x != aid]
        out["resultado"] = "RECHAZADO"
        out["conclusion"] = "El POST sin el atributo obligatorio creo un activo."
        pytest.fail(out["conclusion"])
    out["omision"]["busqueda_identificador"] = _buscar_identificador(tok_p, ident_o)

    attrs_null = dict(attrs_ctrl)
    attrs_null[nombre] = None
    ident_n = f"QAG17R4N{STAMP}"[:50]
    r_n = _post(tok_p, _payload(eid, infra_ok, ident_n, attrs_null))
    out["null"] = _cap(r_n)
    out["null"]["atributo"] = {nombre: None}
    if out["null"]["http"] == 201 and out["null"]["id_creado"]:
        aid = int(out["null"]["id_creado"])
        EVIDENCIA["ids_creados"].append(aid)
        out["null"]["restauracion"] = _restaurar(tok_p, aid, "Restauracion null 187 (no debio crear)")
        EVIDENCIA["ids_creados"] = [x for x in EVIDENCIA["ids_creados"] if x != aid]
        out["resultado"] = "RECHAZADO"
        out["conclusion"] = "El POST con atributo obligatorio null creo un activo."
        pytest.fail(out["conclusion"])

    om = out["omision"]
    code = str(om.get("error_code") or "")
    msg = str(om.get("message") or "").lower()
    rechazo_ok = (
        om.get("id_creado") is None
        and om.get("http") == 422
        and (
            code == "ATRIBUTO_REQUERIDO"
            or "obligator" in msg
            or "requerid" in msg
            or "atributo" in code.lower()
        )
    )
    persistio = bool((om.get("busqueda_identificador") or {}).get("ids"))
    if persistio:
        out["resultado"] = "RECHAZADO"
        out["conclusion"] = f"Omision sin ID en POST pero el identificador {ident_o} aparece en listado."
        pytest.fail(out["conclusion"])
    if not rechazo_ok:
        out["resultado"] = "RECHAZADO"
        out["conclusion"] = (
            f"Omision HTTP {om.get('http')} {om.get('error_code')} no cumple "
            "rechazo contractual 422 ATRIBUTO_REQUERIDO (o equivalente)."
        )
        pytest.fail(out["conclusion"])

    out["resultado"] = "APROBADO"
    out["conclusion"] = (
        f"Precondicion OK: especie {eid} {(info.get(eid) or {}).get('nombre')} activa; "
        f"metrica '{nombre}' obligatoria={objetivo.get('es_obligatorio')} "
        f"tipo={objetivo.get('tipo_dato')} aplica={objetivo.get('aplica_a_tipo_activo')}. "
        f"Control HTTP {out['control']['http']} id={out['control']['id_creado']} restaurado "
        f"{out['control']['restauracion']['estado']}. "
        f"Omision (clave '{nombre}' ausente) HTTP {om['http']} {om['error_code']} sin ID. "
        f"Null HTTP {out['null']['http']} {out['null']['error_code']}. "
        "Bloqueo historico 187 resuelto."
    )


def test_zz_estado_global(sesion):
    r187 = (EVIDENCIA.get("subcasos") or {}).get("TC-M02-187") or {}
    if r187.get("resultado") == "RECHAZADO":
        EVIDENCIA["estado_global"] = "RECHAZADO"
    elif r187.get("resultado") == "APROBADO":
        EVIDENCIA["estado_global"] = "APROBADO"
    else:
        EVIDENCIA["estado_global"] = "BLOQUEADO"
    assert EVIDENCIA["estado_global"] in ("APROBADO", "RECHAZADO", "BLOQUEADO")
