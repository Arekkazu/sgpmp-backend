"""TC-M02-G18 rev4 — RF-34 consulta asociacion infraestructura.

No modifica rev1/rev2/rev3 ni codigo productivo. Solo lectura (+ PUT/PATCH vacio 405).
"""
from __future__ import annotations

import json
import os
import urllib3
from datetime import datetime, timezone
from pathlib import Path

import pytest
import requests

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

DIR = Path(__file__).resolve().parent
RESULTADOS = DIR / "Resultados"
ENV_PATH = DIR / "environment-g18-rev4.json"

with ENV_PATH.open(encoding="utf-8") as fh:
    ENV = json.load(fh)

BASE_URL = ENV["baseUrl"].rstrip("/")
CORREO = ENV["correo_admin"]
ID_022_H = int(ENV["id_022_historico"])
ID_023_H = int(ENV["id_023_historico"])
ID_025_H = int(ENV["id_025_historico"])
ID_INEX_CAND = [int(x) for x in ENV["id_inexistente_candidatos"]]
TIMEOUT = 45
VERIFY_SSL = False

EVIDENCIA: dict = {
    "caso": "TC-M02-G18",
    "revision": 4,
    "rf": "RF-34",
    "cu": "CU01",
    "ambiente": "TEST",
    "base_url": BASE_URL,
    "fecha_utc": datetime.now(timezone.utc).isoformat(),
    "contrato": {
        "endpoint": "GET /activos-biologicos/{id}/infraestructura",
        "query": "tipo_consulta=ACTIVA|HISTORIAL (default ACTIVA); fecha_referencia solo ACTIVA",
        "openapi_metodos": "solo GET (sin PUT/PATCH documentados; 405 esperado del framework)",
        "openapi_http": "200, 400, 401, 403, 404, 422",
        "404_activo": "ACTIVO_NO_ENCONTRADO",
        "404_asociacion": "ASOCIACION_INFRAESTRUCTURA_NO_ENCONTRADA",
        "orden_repo_laura": "obtener_historial_infraestructura order_by fecha_inicio.desc() — veredicto = TEST",
    },
    "precondiciones": {},
    "subcasos": {},
    "estado_global": "PENDIENTE",
    "defecto_orden_historico": {"estado": "PENDIENTE"},
    "auditoria": "Rev1/rev2/rev3 no modificadas. Sin DML. Sin cambios productivos. Sin commit/push.",
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


def _trunc(obj, n=2000):
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
        for k in ("registros", "items", "data", "historial"):
            v = body.get(k)
            if isinstance(v, list):
                return v
    return []


def _login():
    r = requests.post(
        f"{BASE_URL}/sesiones/",
        json={"correo_electronico": CORREO, "contrasena": _password()},
        timeout=TIMEOUT,
        verify=VERIFY_SSL,
    )
    body = _json(r)
    token = body.get("token") if isinstance(body, dict) else None
    if isinstance(body, dict) and not token:
        token = (body.get("data") or {}).get("token")
    return r.status_code, token


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _get_activo(token, aid):
    return requests.get(
        f"{BASE_URL}/activos-biologicos/{aid}",
        headers=_auth(token),
        timeout=TIMEOUT,
        verify=VERIFY_SSL,
    )


def _get_infra(token, aid, tipo="ACTIVA"):
    return requests.get(
        f"{BASE_URL}/activos-biologicos/{aid}/infraestructura",
        params={"tipo_consulta": tipo},
        headers=_auth(token),
        timeout=TIMEOUT,
        verify=VERIFY_SSL,
    )


def _parse_hist(body) -> list[dict]:
    if not isinstance(body, dict):
        return []
    hist = body.get("historial") or []
    out = []
    for h in hist:
        if not isinstance(h, dict):
            continue
        out.append({
            "id_historial": h.get("id_historial"),
            "id_infraestructura": h.get("id_infraestructura"),
            "nombre_infraestructura": h.get("nombre_infraestructura"),
            "fecha_inicio": h.get("fecha_inicio"),
            "fecha_fin": h.get("fecha_fin"),
        })
    return out


def _clasificar(regs: list[dict]) -> dict:
    vigentes = [x for x in regs if x.get("fecha_fin") in (None, "", [])]
    cerradas = [x for x in regs if x.get("fecha_fin") not in (None, "", [])]
    fechas = [str(x.get("fecha_inicio") or "") for x in regs]
    asc = sorted(fechas)
    desc = sorted(fechas, reverse=True)
    orden = "N/A"
    if len(fechas) >= 2:
        if fechas == asc:
            orden = "ASC"
        elif fechas == desc:
            orden = "DESC"
        else:
            orden = "OTRO"
    return {
        "n": len(regs),
        "n_vigentes": len(vigentes),
        "n_cerradas": len(cerradas),
        "vigentes": vigentes,
        "cerradas": cerradas,
        "registros": regs,
        "fechas_inicio": fechas,
        "orden": orden,
        "ordenado_asc": fechas == asc if len(fechas) >= 2 else None,
        "ordenado_desc": fechas == desc if len(fechas) >= 2 else None,
    }


def _inspect(token, aid) -> dict:
    ga = _get_activo(token, aid)
    ba = _json(ga)
    existe = ga.status_code == 200
    gh = _get_infra(token, aid, "HISTORIAL") if existe else None
    bh = _json(gh) if gh is not None else {}
    regs = _parse_hist(bh) if gh is not None and gh.status_code == 200 else []
    info = _clasificar(regs)
    info.update({
        "id": aid,
        "get_activo_http": ga.status_code,
        "error_code_activo": ba.get("error_code") if isinstance(ba, dict) else None,
        "activo_existe": existe,
        "historial_http": gh.status_code if gh is not None else None,
    })
    return info


def _listar_ids(token, max_paginas=3, page_size=20) -> list[int]:
    ids = []
    for pagina in range(1, max_paginas + 1):
        r = requests.get(
            f"{BASE_URL}/activos-biologicos",
            params={"pagina": pagina, "page_size": page_size},
            headers=_auth(token),
            timeout=TIMEOUT,
            verify=VERIFY_SSL,
        )
        if r.status_code != 200:
            break
        for item in _registros(_json(r)):
            i = item.get("id_activo_biologico") or item.get("id")
            if i is not None:
                ids.append(int(i))
        body = _json(r)
        regs = _registros(body)
        if len(regs) < page_size:
            break
    return ids


def _escribir():
    RESULTADOS.mkdir(parents=True, exist_ok=True)
    payload = _redact(EVIDENCIA)
    (RESULTADOS / "TC-M02-G18-rev4.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    subs = payload.get("subcasos") or {}
    lineas = [
        "TC-M02-G18 rev4 — RF-34 — TEST",
        f"Fecha UTC: {payload.get('fecha_utc')}",
        f"Global: {payload.get('estado_global')}",
        "",
        json.dumps({k: v.get("resultado") for k, v in subs.items()}, ensure_ascii=False, indent=2),
        "",
        json.dumps(payload.get("defecto_orden_historico"), ensure_ascii=False, indent=2),
        "",
        json.dumps(subs, ensure_ascii=False, indent=2, default=str),
        payload.get("auditoria"),
    ]
    (RESULTADOS / "TC-M02-G18-rev4.txt").write_text("\n".join(lineas) + "\n", encoding="utf-8")
    bloques = []
    for k, v in subs.items():
        bloques.append(
            f"<h2>{k}</h2><p>Resultado: {v.get('resultado')}</p>"
            f"<pre>{json.dumps(v, ensure_ascii=False, indent=2, default=str)}</pre>"
        )
    (RESULTADOS / "TC-M02-G18-rev4-evidencia.html").write_text(
        "<!DOCTYPE html><html lang='es'><head><meta charset='utf-8'>"
        "<title>TC-M02-G18 rev4</title></head><body>"
        f"<h1>TC-M02-G18 rev4</h1><p>Global: {payload.get('estado_global')}</p>"
        + "".join(bloques)
        + "<p>Rev1-rev3 intactas.</p></body></html>",
        encoding="utf-8",
    )


@pytest.fixture(scope="session")
def sesion():
    _password()
    http, token = _login()
    if not token:
        pytest.skip(f"BLOQUEADO: login Admin HTTP {http}.")
    data = {"token": token, "headers": _auth(token)}
    hist = {
        "022": _inspect(token, ID_022_H),
        "023": _inspect(token, ID_023_H),
        "025": _inspect(token, ID_025_H),
    }
    EVIDENCIA["precondiciones"]["historicos"] = hist

    id_022 = ID_022_H if hist["022"].get("n_vigentes", 0) >= 1 else None
    id_023 = ID_023_H if hist["023"].get("n", 0) >= 2 and hist["023"].get("n_vigentes", 0) >= 1 and hist["023"].get("n_cerradas", 0) >= 1 else None
    if id_023 is None and hist["023"].get("n", 0) >= 2:
        id_023 = ID_023_H
    id_025 = ID_025_H if hist["025"].get("activo_existe") and hist["025"].get("n_vigentes", 0) == 0 else None

    id_inex = None
    inex_info = []
    for cand in ID_INEX_CAND:
        g = _get_activo(token, cand)
        inex_info.append({"id": cand, "http": g.status_code, "error_code": (_json(g) or {}).get("error_code")})
        if g.status_code == 404 and id_inex is None:
            id_inex = cand
    EVIDENCIA["precondiciones"]["inexistente"] = inex_info

    if id_022 is None or id_023 is None or id_025 is None:
        extras = []
        for aid in _listar_ids(token):
            if aid in (ID_022_H, ID_023_H, ID_025_H):
                continue
            info = _inspect(token, aid)
            extras.append({"id": aid, "n": info["n"], "n_vigentes": info["n_vigentes"], "n_cerradas": info["n_cerradas"]})
            if id_022 is None and info["n_vigentes"] >= 1:
                id_022 = aid
                EVIDENCIA["precondiciones"]["022_alternativo"] = info
            if id_023 is None and info["n"] >= 2 and info["n_cerradas"] >= 1:
                id_023 = aid
                EVIDENCIA["precondiciones"]["023_alternativo"] = info
            if id_025 is None and info["activo_existe"] and info["n_vigentes"] == 0:
                id_025 = aid
                EVIDENCIA["precondiciones"]["025_alternativo"] = info
            if id_022 and id_023 and id_025:
                break
        EVIDENCIA["precondiciones"]["scan_resumen"] = extras[:15]

    data["id_022"] = id_022
    data["id_023"] = id_023
    data["id_025"] = id_025
    data["id_inex"] = id_inex
    EVIDENCIA["precondiciones"]["ids_usados"] = {
        "022": id_022, "023": id_023, "025": id_025, "inexistente": id_inex,
    }
    yield data
    _escribir()


def test_tc_m02_022_asociacion_activa(sesion):
    out = {"resultado": "BLOQUEADO", "endpoint": None, "conclusion": ""}
    EVIDENCIA["subcasos"]["TC-M02-022"] = out
    aid = sesion["id_022"]
    if not aid:
        out["conclusion"] = "BLOQUEADO: no hay activo con asociacion vigente (fecha_fin=null)."
        pytest.skip(out["conclusion"])
    tok = sesion["token"]
    prev = _inspect(tok, aid)
    out["id_activo"] = aid
    out["verificacion_previa"] = prev
    if prev["n_vigentes"] < 1:
        out["conclusion"] = f"BLOQUEADO: activo {aid} sin vigente."
        pytest.skip(out["conclusion"])
    r = _get_infra(tok, aid, "ACTIVA")
    body = _json(r)
    out["endpoint"] = f"GET /activos-biologicos/{aid}/infraestructura?tipo_consulta=ACTIVA"
    out["http"] = r.status_code
    out["respuesta"] = _trunc(body, 2200)
    act = body.get("asociacion_activa") if isinstance(body, dict) else None
    out["fecha_fin"] = act.get("fecha_fin") if isinstance(act, dict) else None
    out["id_infraestructura"] = act.get("id_infraestructura") if isinstance(act, dict) else None
    out["id_historial"] = act.get("id_historial") if isinstance(act, dict) else None
    sensores = body.get("sensores_en_infraestructura") if isinstance(body, dict) else None
    out["n_sensores"] = len(sensores) if isinstance(sensores, list) else 0
    out["advertencia_integridad"] = body.get("advertencia_integridad") if isinstance(body, dict) else None
    if r.status_code != 200 or not isinstance(act, dict):
        out["resultado"] = "RECHAZADO"
        out["conclusion"] = f"HTTP {r.status_code} sin asociacion_activa."
        pytest.fail(out["conclusion"])
    if act.get("fecha_fin") not in (None, "", []):
        out["resultado"] = "RECHAZADO"
        out["conclusion"] = f"fecha_fin={act.get('fecha_fin')}; se esperaba null."
        pytest.fail(out["conclusion"])
    out["resultado"] = "APROBADO"
    out["conclusion"] = (
        f"HTTP 200, vigente hist={out['id_historial']} infra={out['id_infraestructura']}, "
        f"sensores={out['n_sensores']}, advertencia_integridad={out['advertencia_integridad']}."
    )


def test_tc_m02_023_historial_orden(sesion):
    out = {"resultado": "BLOQUEADO", "endpoint": None, "conclusion": ""}
    EVIDENCIA["subcasos"]["TC-M02-023"] = out
    aid = sesion["id_023"]
    if not aid:
        out["conclusion"] = "BLOQUEADO: no hay activo con multiples asociaciones."
        EVIDENCIA["defecto_orden_historico"] = {"estado": "BLOQUEADO", "reproduce": None}
        pytest.skip(out["conclusion"])
    tok = sesion["token"]
    prev = _inspect(tok, aid)
    out["id_activo"] = aid
    out["verificacion_previa"] = prev
    if prev["n"] < 2:
        out["conclusion"] = f"BLOQUEADO: activo {aid} n={prev['n']}."
        EVIDENCIA["defecto_orden_historico"] = {"estado": "BLOQUEADO", "reproduce": None}
        pytest.skip(out["conclusion"])
    r = _get_infra(tok, aid, "HISTORIAL")
    body = _json(r)
    regs = _parse_hist(body)
    info = _clasificar(regs)
    out["endpoint"] = f"GET /activos-biologicos/{aid}/infraestructura?tipo_consulta=HISTORIAL"
    out["http"] = r.status_code
    out["respuesta"] = _trunc(body, 2500)
    out.update({k: info[k] for k in (
        "n", "n_vigentes", "n_cerradas", "registros", "fechas_inicio", "orden",
        "ordenado_asc", "ordenado_desc",
    )})
    out["orden_esperado"] = "ASC"
    out["advertencia_integridad"] = body.get("advertencia_integridad") if isinstance(body, dict) else None
    if r.status_code != 200:
        out["resultado"] = "RECHAZADO"
        out["conclusion"] = f"HTTP {r.status_code}."
        pytest.fail(out["conclusion"])
    if info["n_cerradas"] < 1 or info["n_vigentes"] < 1:
        out["conclusion"] = (
            f"BLOQUEADO: n={info['n']} vigentes={info['n_vigentes']} cerradas={info['n_cerradas']}."
        )
        EVIDENCIA["defecto_orden_historico"] = {"estado": "BLOQUEADO", "reproduce": None}
        pytest.skip(out["conclusion"])
    if info["ordenado_asc"] is True:
        out["resultado"] = "APROBADO"
        out["conclusion"] = (
            f"HTTP 200, n={info['n']} (cerradas={info['n_cerradas']}, vigentes={info['n_vigentes']}), "
            f"fechas={info['fechas_inicio']}, orden=ASC. Defecto historico DESC NO REPRODUCIBLE."
        )
        EVIDENCIA["defecto_orden_historico"] = {
            "estado": "NO REPRODUCIBLE",
            "reproduce": False,
            "activo": aid,
            "fechas": info["fechas_inicio"],
        }
        return
    out["resultado"] = "RECHAZADO"
    out["conclusion"] = (
        f"HTTP 200, n={info['n']}, fechas={info['fechas_inicio']}, orden real={info['orden']}. "
        "El caso exige fecha_inicio ASC."
    )
    EVIDENCIA["defecto_orden_historico"] = {
        "estado": "REPRODUCIDO",
        "reproduce": True,
        "activo": aid,
        "fechas": info["fechas_inicio"],
        "esperado": "ASC",
    }
    pytest.fail(out["conclusion"])


def test_tc_m02_024_inexistente(sesion):
    out = {"resultado": "BLOQUEADO", "conclusion": ""}
    EVIDENCIA["subcasos"]["TC-M02-024"] = out
    aid = sesion["id_inex"]
    if not aid:
        out["conclusion"] = "BLOQUEADO: no se confirmo un ID inexistente (99999/100352 existentes)."
        pytest.skip(out["conclusion"])
    tok = sesion["token"]
    ga = _get_activo(tok, aid)
    r = _get_infra(tok, aid, "ACTIVA")
    body = _json(r)
    out["endpoint"] = f"GET /activos-biologicos/{aid}/infraestructura"
    out["id_activo"] = aid
    out["get_activo_http"] = ga.status_code
    out["http"] = r.status_code
    out["respuesta"] = _trunc(body, 800)
    out["error_code"] = body.get("error_code") if isinstance(body, dict) else None
    if r.status_code == 500:
        out["resultado"] = "RECHAZADO"
        out["conclusion"] = "HTTP 500 no es correcto para activo inexistente."
        pytest.fail(out["conclusion"])
    if r.status_code != 404:
        out["resultado"] = "RECHAZADO"
        out["conclusion"] = f"HTTP {r.status_code}, esperado 404."
        pytest.fail(out["conclusion"])
    msg = str(body.get("message") or "").lower()
    if out["error_code"] != "ACTIVO_NO_ENCONTRADO" and "no existe" not in msg and "no encontrado" not in msg:
        out["resultado"] = "RECHAZADO"
        out["conclusion"] = f"404 error_code={out['error_code']} sin indicar inexistencia."
        pytest.fail(out["conclusion"])
    out["resultado"] = "APROBADO"
    out["conclusion"] = f"HTTP 404 {out['error_code']}."


def test_tc_m02_025_sin_asociacion_activa(sesion):
    out = {"resultado": "BLOQUEADO", "conclusion": ""}
    EVIDENCIA["subcasos"]["TC-M02-025"] = out
    aid = sesion["id_025"]
    if not aid:
        out["conclusion"] = (
            "BLOQUEADO: no hay activo existente sin asociacion vigente. "
            "No se fabrica inconsistencia por SQL."
        )
        pytest.skip(out["conclusion"])
    tok = sesion["token"]
    prev = _inspect(tok, aid)
    out["id_activo"] = aid
    out["verificacion_previa"] = prev
    r = _get_infra(tok, aid, "ACTIVA")
    body = _json(r)
    out["endpoint"] = f"GET /activos-biologicos/{aid}/infraestructura?tipo_consulta=ACTIVA"
    out["http"] = r.status_code
    out["respuesta"] = _trunc(body, 1200)
    out["error_code"] = body.get("error_code") if isinstance(body, dict) else None
    out["message"] = body.get("message") if isinstance(body, dict) else None
    aud = requests.get(
        f"{BASE_URL}/activos-biologicos/auditoria",
        params={"id_activo_biologico": aid, "rf_origen": "RF34", "page_size": 20},
        headers=_auth(tok),
        timeout=TIMEOUT,
        verify=VERIFY_SSL,
    )
    out["auditoria_http"] = aud.status_code
    if aud.status_code == 200:
        regs = _registros(_json(aud))
        out["auditoria_n"] = len(regs)
        out["auditoria_resultados"] = list({str(x.get("resultado")) for x in regs})
        out["auditoria_tipos"] = list({str(x.get("tipo_evento")) for x in regs})
        out["alerta_advertencia"] = any(
            "ADVERTENCIA" in str(x.get("resultado") or "").upper()
            or "ADVERTENCIA" in str(x.get("tipo_evento") or "").upper()
            or "ADVERTENCIA" in str(x.get("severidad_log") or "").upper()
            for x in regs
        )
    else:
        out["alerta_advertencia"] = f"NO DETERMINABLE (HTTP {aud.status_code})"
    if r.status_code == 500:
        out["resultado"] = "RECHAZADO"
        out["conclusion"] = "HTTP 500."
        pytest.fail(out["conclusion"])
    if r.status_code != 404:
        out["resultado"] = "RECHAZADO"
        out["conclusion"] = f"HTTP {r.status_code}, esperado 404 de inconsistencia."
        pytest.fail(out["conclusion"])
    if out["error_code"] == "ACTIVO_NO_ENCONTRADO":
        out["resultado"] = "RECHAZADO"
        out["conclusion"] = "404 ACTIVO_NO_ENCONTRADO con activo existente."
        pytest.fail(out["conclusion"])
    raw = json.dumps(body, ensure_ascii=False).lower()
    ok = out["error_code"] == "ASOCIACION_INFRAESTRUCTURA_NO_ENCONTRADA" or "inconsistencia" in raw or "infraestructura activa" in raw
    if not ok:
        out["resultado"] = "RECHAZADO"
        out["conclusion"] = f"404 {out['error_code']} sin mensaje de asociacion ausente."
        pytest.fail(out["conclusion"])
    out["resultado"] = "APROBADO"
    out["conclusion"] = (
        f"HTTP 404 {out['error_code']}. Auditoria ADVERTENCIA={out.get('alerta_advertencia')}. "
        "El use case lanza NotFound antes de bitacora de consulta; no hay alerta admin dedicada."
    )


def test_tc_m02_026_solo_lectura(sesion):
    out = {"resultado": "BLOQUEADO", "conclusion": ""}
    EVIDENCIA["subcasos"]["TC-M02-026"] = out
    aid = sesion["id_022"] or sesion["id_023"]
    if not aid:
        out["conclusion"] = "BLOQUEADO: sin activo valido para 405."
        pytest.skip(out["conclusion"])
    tok = sesion["token"]
    url = f"{BASE_URL}/activos-biologicos/{aid}/infraestructura"
    # Sin cuerpo de asociacion: solo se prueba el metodo HTTP.
    r_put = requests.put(url, headers=_auth(tok), timeout=TIMEOUT, verify=VERIFY_SSL)
    r_patch = requests.patch(url, headers=_auth(tok), timeout=TIMEOUT, verify=VERIFY_SSL)
    out["endpoint"] = f"PUT/PATCH /activos-biologicos/{aid}/infraestructura"
    out["id_activo"] = aid
    out["http_put"] = r_put.status_code
    out["http_patch"] = r_patch.status_code
    out["put_body"] = _trunc(_json(r_put) if r_put.content else {"raw": (r_put.text or "")[:300]}, 400)
    out["patch_body"] = _trunc(_json(r_patch) if r_patch.content else {"raw": (r_patch.text or "")[:300]}, 400)
    raw = f"{r_put.text} {r_patch.text}".lower()
    out["menciona_rf48"] = "rf-48" in raw or "rf48" in raw or "transferencia" in raw
    if r_put.status_code == 200 or r_patch.status_code == 200:
        out["resultado"] = "RECHAZADO"
        out["conclusion"] = "PUT/PATCH 200: el endpoint no es solo lectura."
        pytest.fail(out["conclusion"])
    if r_put.status_code != 405 or r_patch.status_code != 405:
        out["resultado"] = "RECHAZADO"
        out["conclusion"] = f"PUT {r_put.status_code} PATCH {r_patch.status_code}, esperado 405."
        pytest.fail(out["conclusion"])
    out["resultado"] = "APROBADO"
    out["conclusion"] = (
        f"PUT/PATCH HTTP 405. OpenAPI solo declara GET. Mencion RF-48: {out['menciona_rf48']}."
    )


def test_zz_estado_global(sesion):
    subs = EVIDENCIA.get("subcasos") or {}
    estados = [v.get("resultado") for v in subs.values()]
    if "RECHAZADO" in estados:
        EVIDENCIA["estado_global"] = "RECHAZADO"
    elif estados and all(e == "APROBADO" for e in estados):
        EVIDENCIA["estado_global"] = "APROBADO"
    else:
        EVIDENCIA["estado_global"] = "BLOQUEADO"
    assert EVIDENCIA["estado_global"] in ("APROBADO", "RECHAZADO", "BLOQUEADO")
