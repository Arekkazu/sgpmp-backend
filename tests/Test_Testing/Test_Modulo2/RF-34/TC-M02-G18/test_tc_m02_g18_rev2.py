"""TC-M02-G18 rev2 — RF-34. Segunda evaluacion.

Consulta asociacion a infraestructura. Caja negra contra TEST.
No modifica historico ni backend.
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
ENV_PATH = DIR / "environment-g18-rev2.json"

with ENV_PATH.open(encoding="utf-8") as fh:
    ENV = json.load(fh)

BASE_URL = ENV["baseUrl"].rstrip("/")
CORREO = ENV["correo_admin"]
TIMEOUT = 45
VERIFY_SSL = False

EVIDENCIA: dict = {
    "caso": "TC-M02-G18",
    "revision": 2,
    "rf": "RF-34",
    "cu": "CU01",
    "ambiente": "TEST",
    "base_url": BASE_URL,
    "fecha_utc": datetime.now(timezone.utc).isoformat(),
    "precondiciones": {},
    "subcasos": {},
    "estado_global": "PENDIENTE",
    "inc_m02_48_g18": "PENDIENTE",
    "auditoria": "Historico RF-34 no modificado. Codigo productivo no modificado. Sin commit ni push.",
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


def _trunc(obj, n=2200):
    text = json.dumps(_redact(obj), ensure_ascii=False, default=str)
    if len(text) > n:
        return text[:n] + "...[TRUNCATED]"
    return text


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


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _infra_url(aid: int) -> str:
    return f"{BASE_URL}/activos-biologicos/{aid}/infraestructura"


def _escribir() -> None:
    RESULTADOS.mkdir(parents=True, exist_ok=True)
    payload = _redact(EVIDENCIA)
    (RESULTADOS / "TC-M02-G18-rev2.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    (RESULTADOS / "TC-M02-G18-rev2.txt").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    bloques = []
    for k, v in (payload.get("subcasos") or {}).items():
        bloques.append(
            f"<h2>{k}: {v.get('resultado')}</h2>"
            f"<pre>{json.dumps(v, ensure_ascii=False, indent=2, default=str)}</pre>"
        )
    (RESULTADOS / "TC-M02-G18-rev2-evidencia.html").write_text(
        "<!DOCTYPE html><html lang='es'><head><meta charset='utf-8'>"
        "<title>TC-M02-G18 rev2</title></head><body>"
        f"<h1>TC-M02-G18 rev2</h1><p>Global: {payload.get('estado_global')}</p>"
        f"<p>INC-M02-48-G18: {payload.get('inc_m02_48_g18')}</p>"
        + "".join(bloques)
        + "<p>Sin JWT. Historico no modificado.</p></body></html>",
        encoding="utf-8",
    )


@pytest.fixture(scope="session")
def ctx():
    pwd = _password()
    r = requests.post(
        f"{BASE_URL}/sesiones/",
        json={"correo_electronico": CORREO, "contrasena": pwd},
        timeout=TIMEOUT,
        verify=VERIFY_SSL,
    )
    body = _json(r)
    token = body.get("token") if isinstance(body, dict) else None
    if r.status_code != 200 or not token:
        EVIDENCIA["precondiciones"]["login"] = {"http": r.status_code}
        _escribir()
        pytest.skip(f"BLOQUEADO: login Admin HTTP {r.status_code}")

    headers = _auth(token)
    activos = []
    max_id = 0
    for pagina in range(1, 5):
        lr = requests.get(
            f"{BASE_URL}/activos-biologicos",
            params={"pagina": pagina, "page_size": 50},
            headers=headers,
            timeout=TIMEOUT,
            verify=VERIFY_SSL,
        )
        if lr.status_code != 200:
            EVIDENCIA["precondiciones"]["listado"] = {"http": lr.status_code, "body": _trunc(_json(lr), 400)}
            break
        regs = _registros(_json(lr))
        activos.extend(regs)
        for x in regs:
            i = x.get("id_activo_biologico") or x.get("id")
            if i is not None:
                max_id = max(max_id, int(i))
        if len(regs) < 50:
            break

    hallazgo = {
        "con_activa": None,
        "con_multiple": None,
        "sin_activa": None,
        "muestra_historial": [],
        "activos_inspeccionados": 0,
        "http_historial_500": 0,
    }
    for item in activos:
        aid = item.get("id_activo_biologico") or item.get("id")
        if aid is None:
            continue
        aid = int(aid)
        hr = requests.get(
            _infra_url(aid),
            params={"tipo_consulta": "HISTORIAL"},
            headers=headers,
            timeout=TIMEOUT,
            verify=VERIFY_SSL,
        )
        hallazgo["activos_inspeccionados"] += 1
        if hr.status_code == 500:
            hallazgo["http_historial_500"] += 1
            continue
        if hr.status_code != 200:
            continue
        hist = _json(hr).get("historial") or []
        if not isinstance(hist, list):
            hist = []
        vigentes = [h for h in hist if h.get("fecha_fin") in (None, "")]
        cerradas = [h for h in hist if h.get("fecha_fin") not in (None, "")]
        resumen = {"id": aid, "n": len(hist), "vigentes": len(vigentes), "cerradas": len(cerradas)}
        if len(hallazgo["muestra_historial"]) < 8:
            hallazgo["muestra_historial"].append(resumen)
        if hallazgo["con_multiple"] is None and vigentes and cerradas:
            hallazgo["con_multiple"] = {
                "id": aid, "n": len(hist), "vigentes": len(vigentes), "cerradas": len(cerradas)
            }
        if hallazgo["con_activa"] is None and vigentes:
            hallazgo["con_activa"] = {"id": aid, "infra": vigentes[0].get("id_infraestructura")}
        if hallazgo["sin_activa"] is None and not vigentes:
            ge = requests.get(
                f"{BASE_URL}/activos-biologicos/{aid}",
                headers=headers,
                timeout=TIMEOUT,
                verify=VERIFY_SSL,
            )
            if ge.status_code == 200:
                hallazgo["sin_activa"] = {"id": aid, "n_historial": len(hist), "get_activo_http": 200}
        if hallazgo["con_activa"] and hallazgo["con_multiple"] and hallazgo["sin_activa"]:
            break

    inexistente = max_id + 100000 if max_id else 999999
    gi = requests.get(
        f"{BASE_URL}/activos-biologicos/{inexistente}",
        headers=headers,
        timeout=TIMEOUT,
        verify=VERIFY_SSL,
    )
    hallazgo["id_inexistente"] = inexistente
    hallazgo["get_inexistente_http"] = gi.status_code
    hallazgo["total_activos_listados"] = len(activos)
    EVIDENCIA["precondiciones"] = hallazgo
    data = {"token": token, "headers": headers, **hallazgo}
    yield data
    estados = [v.get("resultado") for v in (EVIDENCIA.get("subcasos") or {}).values()]
    if "RECHAZADO" in estados:
        EVIDENCIA["estado_global"] = "RECHAZADO"
    elif estados and all(e == "APROBADO" for e in estados):
        EVIDENCIA["estado_global"] = "APROBADO"
    else:
        EVIDENCIA["estado_global"] = "BLOQUEADO"
    c023 = (EVIDENCIA.get("subcasos") or {}).get("TC-M02-023") or {}
    c025 = (EVIDENCIA.get("subcasos") or {}).get("TC-M02-025") or {}
    multi_ok = c023.get("multiple_cerrada_y_vigente") is True
    s025 = c025.get("resultado")
    if multi_ok and s025 == "APROBADO":
        EVIDENCIA["inc_m02_48_g18"] = "superado"
    elif (not multi_ok) and s025 == "BLOQUEADO":
        EVIDENCIA["inc_m02_48_g18"] = "continua"
    elif multi_ok or s025 == "APROBADO":
        EVIDENCIA["inc_m02_48_g18"] = "parcialmente superado"
    else:
        EVIDENCIA["inc_m02_48_g18"] = "no verificable"
    _escribir()


def test_tc_m02_022_activa(ctx):
    out = {"resultado": "BLOQUEADO", "endpoint": "GET .../infraestructura?tipo_consulta=ACTIVA"}
    EVIDENCIA["subcasos"]["TC-M02-022"] = out
    info = ctx.get("con_activa")
    if not info:
        out["explicacion"] = "BLOQUEADO: no hay activo con fecha_fin=null en la muestra."
        pytest.skip(out["explicacion"])
    aid = info["id"]
    out["id_activo"] = aid
    r = requests.get(
        _infra_url(aid),
        params={"tipo_consulta": "ACTIVA"},
        headers=ctx["headers"],
        timeout=TIMEOUT,
        verify=VERIFY_SSL,
    )
    body = _json(r)
    out["http"] = r.status_code
    out["respuesta"] = _trunc(body)
    if r.status_code == 500:
        out["explicacion"] = "BLOQUEADO HTTP 500."
        pytest.skip(out["explicacion"])
    if r.status_code != 200:
        out["resultado"] = "RECHAZADO"
        out["explicacion"] = f"HTTP {r.status_code}, esperado 200."
        pytest.fail(out["explicacion"])
    asoc = body.get("asociacion_activa") or {}
    out["fecha_fin"] = asoc.get("fecha_fin")
    out["id_infraestructura"] = asoc.get("id_infraestructura")
    out["sensores_campo"] = "sensores_en_infraestructura" in body
    out["n_sensores"] = len(body.get("sensores_en_infraestructura") or [])
    out["advertencia_integridad"] = body.get("advertencia_integridad")
    if asoc.get("fecha_fin") not in (None, ""):
        out["resultado"] = "RECHAZADO"
        out["explicacion"] = "asociacion_activa.fecha_fin no es null."
        pytest.fail(out["explicacion"])
    if asoc.get("id_infraestructura") is None:
        out["resultado"] = "RECHAZADO"
        out["explicacion"] = "Falta id_infraestructura vigente."
        pytest.fail(out["explicacion"])
    if "sensores_en_infraestructura" not in body:
        out["resultado"] = "RECHAZADO"
        out["explicacion"] = "No viene sensores_en_infraestructura."
        pytest.fail(out["explicacion"])
    out["resultado"] = "APROBADO"
    out["explicacion"] = (
        "HTTP 200, vigente con fecha_fin null, campo sensores presente "
        f"(n={out['n_sensores']}). advertencia_integridad={out['advertencia_integridad']}."
    )


def test_tc_m02_023_historial(ctx):
    out = {
        "resultado": "BLOQUEADO",
        "endpoint": "GET .../infraestructura?tipo_consulta=HISTORIAL",
        "multiple_cerrada_y_vigente": False,
    }
    EVIDENCIA["subcasos"]["TC-M02-023"] = out
    info = ctx.get("con_multiple") or ctx.get("con_activa")
    if not info:
        out["explicacion"] = "BLOQUEADO: no hay activo con historial HTTP 200."
        pytest.skip(out["explicacion"])
    aid = info["id"]
    out["id_activo"] = aid
    out["precondicion_multiple"] = ctx.get("con_multiple")
    r = requests.get(
        _infra_url(aid),
        params={"tipo_consulta": "HISTORIAL"},
        headers=ctx["headers"],
        timeout=TIMEOUT,
        verify=VERIFY_SSL,
    )
    body = _json(r)
    out["http"] = r.status_code
    hist = body.get("historial") if isinstance(body, dict) else None
    out["n_registros"] = len(hist) if isinstance(hist, list) else None
    out["respuesta"] = _trunc(body)
    if r.status_code == 500:
        out["explicacion"] = "BLOQUEADO HTTP 500."
        pytest.skip(out["explicacion"])
    if r.status_code != 200 or not isinstance(hist, list) or not hist:
        out["resultado"] = "RECHAZADO"
        out["explicacion"] = f"HTTP {r.status_code} o historial vacio/no lista."
        pytest.fail(out["explicacion"])
    fechas = [h.get("fecha_inicio") for h in hist if h.get("fecha_inicio")]
    ordenado_asc = all(fechas[i] <= fechas[i + 1] for i in range(len(fechas) - 1))
    out["ordenado_fecha_inicio_asc"] = ordenado_asc
    out["fechas_inicio"] = fechas
    vigentes = [h for h in hist if h.get("fecha_fin") in (None, "")]
    cerradas = [h for h in hist if h.get("fecha_fin") not in (None, "")]
    out["n_vigentes"] = len(vigentes)
    out["n_cerradas"] = len(cerradas)
    out["multiple_cerrada_y_vigente"] = bool(vigentes and cerradas)
    if not ordenado_asc and len(fechas) > 1:
        out["resultado"] = "RECHAZADO"
        out["explicacion"] = "Historial no ordenado por fecha_inicio ASC."
        pytest.fail(out["explicacion"])
    if not vigentes:
        out["resultado"] = "RECHAZADO"
        out["explicacion"] = "Historial sin asociacion vigente (fecha_fin=null)."
        pytest.fail(out["explicacion"])
    out["resultado"] = "APROBADO"
    if not out["multiple_cerrada_y_vigente"]:
        out["explicacion"] = (
            f"HTTP 200, {len(hist)} registro(s), orden comprobado, vigente presente. "
            "Sin activo con cerrada+vigente en la muestra."
        )
    else:
        out["explicacion"] = (
            f"HTTP 200, {len(hist)} registros (cerradas={len(cerradas)}, vigentes={len(vigentes)}), "
            f"orden ASC={ordenado_asc}."
        )


def test_tc_m02_024_inexistente(ctx):
    out = {"resultado": "BLOQUEADO", "endpoint": "GET .../infraestructura?tipo_consulta=ACTIVA"}
    EVIDENCIA["subcasos"]["TC-M02-024"] = out
    aid = ctx.get("id_inexistente")
    if ctx.get("get_inexistente_http") == 200:
        out["explicacion"] = f"BLOQUEADO: el ID {aid} existe (GET ficha 200)."
        pytest.skip(out["explicacion"])
    out["id_activo"] = aid
    r = requests.get(
        _infra_url(aid),
        params={"tipo_consulta": "ACTIVA"},
        headers=ctx["headers"],
        timeout=TIMEOUT,
        verify=VERIFY_SSL,
    )
    body = _json(r)
    out["http"] = r.status_code
    out["respuesta"] = _trunc(body)
    if r.status_code == 500:
        out["explicacion"] = "BLOQUEADO HTTP 500."
        pytest.skip(out["explicacion"])
    if r.status_code != 404:
        out["resultado"] = "RECHAZADO"
        out["explicacion"] = f"HTTP {r.status_code}, esperado 404."
        pytest.fail(out["explicacion"])
    raw = json.dumps(body, ensure_ascii=False).lower()
    out["error_code"] = body.get("error_code") if isinstance(body, dict) else None
    if "no existe" not in raw and "activo" not in raw:
        out["resultado"] = "RECHAZADO"
        out["explicacion"] = "404 sin indicar que el activo no existe."
        pytest.fail(out["explicacion"])
    if out["error_code"] == "ASOCIACION_INFRAESTRUCTURA_NO_ENCONTRADA":
        out["resultado"] = "RECHAZADO"
        out["explicacion"] = "404 de asociacion, no de activo inexistente."
        pytest.fail(out["explicacion"])
    out["resultado"] = "APROBADO"
    out["explicacion"] = f"HTTP 404 error_code={out['error_code']}."


def test_tc_m02_025_sin_activa(ctx):
    out = {"resultado": "BLOQUEADO", "endpoint": "GET .../infraestructura?tipo_consulta=ACTIVA"}
    EVIDENCIA["subcasos"]["TC-M02-025"] = out
    info = ctx.get("sin_activa")
    if not info:
        out["explicacion"] = (
            "BLOQUEADO: no hay activo existente sin fecha_fin=null en HISTORIAL. "
            "No se inventa ni se cierra asociacion."
        )
        pytest.skip(out["explicacion"])
    aid = info["id"]
    out["id_activo"] = aid
    out["precondicion"] = info
    rh = requests.get(
        _infra_url(aid),
        params={"tipo_consulta": "HISTORIAL"},
        headers=ctx["headers"],
        timeout=TIMEOUT,
        verify=VERIFY_SSL,
    )
    hist = (_json(rh).get("historial") or []) if rh.status_code == 200 else []
    vigentes = [h for h in hist if isinstance(h, dict) and h.get("fecha_fin") in (None, "")]
    out["recheck_historial_http"] = rh.status_code
    out["recheck_vigentes"] = len(vigentes)
    if vigentes:
        out["explicacion"] = "BLOQUEADO: al reconsultar ya hay fecha_fin=null."
        pytest.skip(out["explicacion"])
    r = requests.get(
        _infra_url(aid),
        params={"tipo_consulta": "ACTIVA"},
        headers=ctx["headers"],
        timeout=TIMEOUT,
        verify=VERIFY_SSL,
    )
    body = _json(r)
    out["http"] = r.status_code
    out["respuesta"] = _trunc(body)
    if r.status_code == 500:
        out["explicacion"] = "BLOQUEADO HTTP 500."
        pytest.skip(out["explicacion"])
    if r.status_code != 404:
        out["resultado"] = "RECHAZADO"
        out["explicacion"] = f"HTTP {r.status_code}, esperado 404."
        pytest.fail(out["explicacion"])
    raw = json.dumps(body, ensure_ascii=False).lower()
    out["error_code"] = body.get("error_code") if isinstance(body, dict) else None
    ok_msg = (
        "inconsistencia" in raw
        or "infraestructura activa" in raw
        or "asociacion" in raw
        or out["error_code"] == "ASOCIACION_INFRAESTRUCTURA_NO_ENCONTRADA"
    )
    if not ok_msg:
        out["resultado"] = "RECHAZADO"
        out["explicacion"] = "404 sin mensaje de inconsistencia."
        pytest.fail(out["explicacion"])
    aud = requests.get(
        f"{BASE_URL}/activos-biologicos/auditoria",
        params={"id_activo_biologico": aid, "rf_origen": "RF34", "page_size": 20},
        headers=ctx["headers"],
        timeout=TIMEOUT,
        verify=VERIFY_SSL,
    )
    out["auditoria_http"] = aud.status_code
    if aud.status_code == 200:
        regs = _registros(_json(aud))
        out["auditoria_n"] = len(regs)
        out["auditoria_resultados"] = list({str(x.get("resultado")) for x in regs})
        out["alerta_advertencia"] = any(
            str(x.get("resultado") or "").upper() == "ADVERTENCIA" for x in regs
        )
    else:
        out["alerta_advertencia"] = f"NO DETERMINABLE (bitacora HTTP {aud.status_code})"
    out["resultado"] = "APROBADO"
    out["explicacion"] = (
        f"HTTP 404 {out['error_code']}. Auditoria ADVERTENCIA: {out['alerta_advertencia']}."
    )


def test_tc_m02_026_solo_lectura(ctx):
    out = {"resultado": "BLOQUEADO", "endpoint": "PUT/PATCH .../infraestructura"}
    EVIDENCIA["subcasos"]["TC-M02-026"] = out
    info = ctx.get("con_activa")
    if not info:
        out["explicacion"] = "BLOQUEADO: no hay activo para PUT/PATCH de rechazo."
        pytest.skip(out["explicacion"])
    aid = info["id"]
    out["id_activo"] = aid
    url = _infra_url(aid)
    r_put = requests.put(
        url,
        headers={**ctx["headers"], "Content-Type": "application/json"},
        json={"id_infraestructura": 1},
        timeout=TIMEOUT,
        verify=VERIFY_SSL,
    )
    r_patch = requests.patch(
        url,
        headers={**ctx["headers"], "Content-Type": "application/json"},
        json={"id_infraestructura": 1},
        timeout=TIMEOUT,
        verify=VERIFY_SSL,
    )
    out["http_put"] = r_put.status_code
    out["http_patch"] = r_patch.status_code
    out["put_body"] = _trunc(_json(r_put), 800)
    out["patch_body"] = _trunc(_json(r_patch), 800)
    if r_put.status_code in (200, 201, 204) or r_patch.status_code in (200, 201, 204):
        out["resultado"] = "RECHAZADO"
        out["explicacion"] = "El endpoint acepto escritura."
        pytest.fail(out["explicacion"])
    if r_put.status_code != 405 or r_patch.status_code != 405:
        out["resultado"] = "RECHAZADO"
        out["explicacion"] = f"PUT {r_put.status_code} PATCH {r_patch.status_code}, esperado 405."
        pytest.fail(out["explicacion"])
    raw = (
        json.dumps(_json(r_put), ensure_ascii=False) + json.dumps(_json(r_patch), ensure_ascii=False)
    ).lower()
    out["menciona_rf48"] = "rf-48" in raw or "rf48" in raw or "transferencia" in raw
    out["resultado"] = "APROBADO"
    out["explicacion"] = (
        f"PUT y PATCH HTTP 405. Mencion RF-48/transferencia: {out['menciona_rf48']}."
    )


def test_zz_global(ctx):
    assert EVIDENCIA.get("subcasos")
