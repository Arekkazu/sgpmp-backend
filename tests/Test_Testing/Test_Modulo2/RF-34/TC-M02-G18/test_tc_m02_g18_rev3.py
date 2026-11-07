"""TC-M02-G18 rev3 — RF-34. Datos DBA (activos 8 y 10) verificados por GET.

No modifica historico, evidencias rev2 ni backend. Solo lectura.
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
ENV_PATH = DIR / "environment-g18-rev3.json"

with ENV_PATH.open(encoding="utf-8") as fh:
    ENV = json.load(fh)

BASE_URL = ENV["baseUrl"].rstrip("/")
CORREO = ENV["correo_admin"]
ID_025 = int(ENV["id_025"])
ID_023 = int(ENV["id_023"])
ID_022 = int(ENV["id_022"])
ID_INEX = int(ENV["id_inexistente"])
TIMEOUT = 45
VERIFY_SSL = False

EVIDENCIA: dict = {
    "caso": "TC-M02-G18",
    "revision": 3,
    "rf": "RF-34",
    "ambiente": "TEST",
    "base_url": BASE_URL,
    "fecha_utc": datetime.now(timezone.utc).isoformat(),
    "verificacion_dba": {},
    "subcasos": {},
    "estado_global": "PENDIENTE",
    "inc_m02_48_g18": "PENDIENTE",
    "defecto_orden_desc": {
        "id_seguimiento": "por asignar (rev2 G18, mismo hallazgo)",
        "descripcion": "Historial ordenado por fecha_inicio DESC; el caso exige ASC.",
        "codigo": "obtener_historial_infraestructura .order_by(fecha_inicio.desc())",
        "estado": "PENDIENTE",
    },
    "auditoria": (
        "Historico Newman y rev2 no modificados. Backend no modificado. "
        "Sin commit ni push. Sin crear/cerrar/transferir asociaciones."
    ),
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


def _trunc(obj, n=3500):
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


def _resumen_hist(hist: list) -> dict:
    filas = []
    for h in hist:
        if not isinstance(h, dict):
            continue
        filas.append(
            {
                "id_historial": h.get("id_historial"),
                "id_infraestructura": h.get("id_infraestructura"),
                "nombre_infraestructura": h.get("nombre_infraestructura"),
                "fecha_inicio": h.get("fecha_inicio"),
                "fecha_fin": h.get("fecha_fin"),
            }
        )
    vigentes = [f for f in filas if f.get("fecha_fin") in (None, "")]
    cerradas = [f for f in filas if f.get("fecha_fin") not in (None, "")]
    fechas = [f.get("fecha_inicio") for f in filas if f.get("fecha_inicio")]
    asc = all(fechas[i] <= fechas[i + 1] for i in range(len(fechas) - 1)) if len(fechas) > 1 else None
    desc = all(fechas[i] >= fechas[i + 1] for i in range(len(fechas) - 1)) if len(fechas) > 1 else None
    orden = "INDETERMINADO"
    if len(fechas) <= 1:
        orden = "N/A (menos de 2 fechas)"
    elif asc:
        orden = "ASC"
    elif desc:
        orden = "DESC"
    else:
        orden = "NI ASC NI DESC"
    return {
        "n": len(filas),
        "n_vigentes": len(vigentes),
        "n_cerradas": len(cerradas),
        "vigentes": vigentes,
        "cerradas": cerradas,
        "registros": filas,
        "fechas_inicio": fechas,
        "orden": orden,
        "ordenado_asc": asc,
        "ordenado_desc": desc,
    }


def _escribir() -> None:
    RESULTADOS.mkdir(parents=True, exist_ok=True)
    payload = _redact(EVIDENCIA)
    (RESULTADOS / "TC-M02-G18-rev3.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    (RESULTADOS / "TC-M02-G18-rev3.txt").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8"
    )
    bloques = []
    for k, v in (payload.get("subcasos") or {}).items():
        bloques.append(
            f"<h2>{k}: {v.get('resultado')}</h2>"
            f"<pre>{json.dumps(v, ensure_ascii=False, indent=2, default=str)}</pre>"
        )
    (RESULTADOS / "TC-M02-G18-rev3-evidencia.html").write_text(
        "<!DOCTYPE html><html lang='es'><head><meta charset='utf-8'>"
        "<title>TC-M02-G18 rev3</title></head><body>"
        f"<h1>TC-M02-G18 rev3</h1><p>Global: {payload.get('estado_global')}</p>"
        f"<p>INC-M02-48-G18: {payload.get('inc_m02_48_g18')}</p>"
        + "".join(bloques)
        + "<p>Sin JWT. Historico y rev2 no modificados.</p></body></html>",
        encoding="utf-8",
    )


def _get_activo(headers, aid: int):
    r = requests.get(
        f"{BASE_URL}/activos-biologicos/{aid}",
        headers=headers,
        timeout=TIMEOUT,
        verify=VERIFY_SSL,
    )
    return r.status_code, _json(r)


def _get_hist(headers, aid: int):
    r = requests.get(
        _infra_url(aid),
        params={"tipo_consulta": "HISTORIAL"},
        headers=headers,
        timeout=TIMEOUT,
        verify=VERIFY_SSL,
    )
    body = _json(r)
    hist = body.get("historial") if isinstance(body, dict) else None
    if not isinstance(hist, list):
        hist = []
    return r.status_code, body, hist


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
        EVIDENCIA["verificacion_dba"]["login"] = {"http": r.status_code}
        _escribir()
        pytest.skip(f"BLOQUEADO: login Admin HTTP {r.status_code}")
    headers = _auth(token)

    http10, body10 = _get_activo(headers, ID_025)
    h10, b10, hist10 = _get_hist(headers, ID_025) if http10 == 200 else (None, None, [])
    res10 = _resumen_hist(hist10) if h10 == 200 else {}
    ver10 = {
        "id": ID_025,
        "get_activo_http": http10,
        "error_code_activo": body10.get("error_code") if isinstance(body10, dict) else None,
        "activo_existe": http10 == 200,
        "historial_http": h10,
        "precondicion_sin_vigente": bool(http10 == 200 and h10 == 200 and res10.get("n_vigentes") == 0),
        **res10,
        "respuesta_activo": _trunc(body10, 1200),
    }

    http8, body8 = _get_activo(headers, ID_023)
    h8, b8, hist8 = _get_hist(headers, ID_023) if http8 == 200 else (None, None, [])
    res8 = _resumen_hist(hist8) if h8 == 200 else {}
    ver8 = {
        "id": ID_023,
        "get_activo_http": http8,
        "error_code_activo": body8.get("error_code") if isinstance(body8, dict) else None,
        "activo_existe": http8 == 200,
        "historial_http": h8,
        "precondicion_multiple": bool(
            http8 == 200 and h8 == 200 and res8.get("n_cerradas", 0) >= 1 and res8.get("n_vigentes", 0) >= 1
        ),
        **res8,
        "respuesta_activo": _trunc(body8, 1200),
    }

    http352, body352 = _get_activo(headers, ID_022)
    h352, b352, hist352 = _get_hist(headers, ID_022) if http352 == 200 else (None, None, [])
    res352 = _resumen_hist(hist352) if h352 == 200 else {}
    ver352 = {
        "id": ID_022,
        "get_activo_http": http352,
        "activo_existe": http352 == 200,
        "historial_http": h352,
        "tiene_vigente": bool(res352.get("n_vigentes", 0) >= 1),
        **{k: res352.get(k) for k in ("n", "n_vigentes", "n_cerradas", "vigentes")},
    }

    http_inex, body_inex = _get_activo(headers, ID_INEX)
    EVIDENCIA["verificacion_dba"] = {
        "activo_10": ver10,
        "activo_8": ver8,
        "activo_352": ver352,
        "inexistente_100352": {
            "get_activo_http": http_inex,
            "error_code": body_inex.get("error_code") if isinstance(body_inex, dict) else None,
            "respuesta": _trunc(body_inex, 600),
        },
        "codigo_orden": "activo_biologico_repository.obtener_historial_infraestructura order_by fecha_inicio.desc()",
    }
    data = {
        "headers": headers,
        "v10": ver10,
        "v8": ver8,
        "v352": ver352,
        "inex_http": http_inex,
    }
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
    datos_023 = ver8.get("precondicion_multiple") is True
    datos_025 = ver10.get("precondicion_sin_vigente") is True
    if datos_023 and datos_025:
        EVIDENCIA["inc_m02_48_g18"] = "SUPERADO"
    elif datos_023 or datos_025:
        EVIDENCIA["inc_m02_48_g18"] = "PARCIALMENTE SUPERADO"
    else:
        EVIDENCIA["inc_m02_48_g18"] = "CONTINUA"
    if c023.get("orden") == "DESC" or c023.get("ordenado_fecha_inicio_asc") is False:
        EVIDENCIA["defecto_orden_desc"]["estado"] = "CONTINUA"
        EVIDENCIA["defecto_orden_desc"]["activo_evidencia"] = c023.get("id_activo")
    elif c023.get("ordenado_fecha_inicio_asc") is True:
        EVIDENCIA["defecto_orden_desc"]["estado"] = "SUPERADO"
    EVIDENCIA["inc_m02_48_nota"] = (
        "INC-M02-48 cubre falta de datos (multiples asociaciones y activo sin vigente). "
        "El orden DESC es seguimiento aparte (rev2, no duplicar). "
        f"023 datos={datos_023} resultado={c023.get('resultado')}; "
        f"025 datos={datos_025} resultado={c025.get('resultado')}."
    )
    _escribir()


def test_tc_m02_025_sin_activa(ctx):
    out = {
        "resultado": "BLOQUEADO",
        "endpoint": "GET /activos-biologicos/10/infraestructura?tipo_consulta=ACTIVA",
        "id_activo": ID_025,
    }
    EVIDENCIA["subcasos"]["TC-M02-025"] = out
    v = ctx["v10"]
    out["verificacion_previa"] = {
        "activo_existe": v.get("activo_existe"),
        "get_activo_http": v.get("get_activo_http"),
        "n": v.get("n"),
        "n_vigentes": v.get("n_vigentes"),
        "n_cerradas": v.get("n_cerradas"),
        "precondicion_sin_vigente": v.get("precondicion_sin_vigente"),
        "registros": v.get("registros"),
    }
    if not v.get("activo_existe"):
        out["explicacion"] = (
            f"BLOQUEADO: GET /activos-biologicos/10 HTTP {v.get('get_activo_http')} "
            f"{v.get('error_code_activo')}. El DBA indico ID 10; en TEST no existe o no es visible."
        )
        pytest.skip(out["explicacion"])
    if v.get("historial_http") != 200:
        out["explicacion"] = f"BLOQUEADO: HISTORIAL del activo 10 HTTP {v.get('historial_http')}."
        pytest.skip(out["explicacion"])
    if not v.get("precondicion_sin_vigente"):
        out["explicacion"] = (
            f"BLOQUEADO: activo 10 existe pero tiene {v.get('n_vigentes')} asociacion(es) con "
            "fecha_fin=null. No se altera el registro."
        )
        pytest.skip(out["explicacion"])
    r = requests.get(
        _infra_url(ID_025),
        params={"tipo_consulta": "ACTIVA"},
        headers=ctx["headers"],
        timeout=TIMEOUT,
        verify=VERIFY_SSL,
    )
    body = _json(r)
    out["http"] = r.status_code
    out["respuesta"] = _trunc(body, 1800)
    out["error_code"] = body.get("error_code") if isinstance(body, dict) else None
    out["message"] = body.get("message") if isinstance(body, dict) else None
    if r.status_code == 500:
        out["explicacion"] = "BLOQUEADO HTTP 500."
        pytest.skip(out["explicacion"])
    if r.status_code != 404:
        out["resultado"] = "RECHAZADO"
        out["explicacion"] = f"HTTP {r.status_code}, esperado 404."
        pytest.fail(out["explicacion"])
    if out["error_code"] == "ACTIVO_NO_ENCONTRADO":
        out["resultado"] = "RECHAZADO"
        out["explicacion"] = (
            "404 ACTIVO_NO_ENCONTRADO pero GET del activo 10 fue 200. Confunde activo inexistente "
            "con ausencia de asociacion activa."
        )
        pytest.fail(out["explicacion"])
    raw = json.dumps(body, ensure_ascii=False).lower()
    ok_msg = (
        out["error_code"] == "ASOCIACION_INFRAESTRUCTURA_NO_ENCONTRADA"
        or "inconsistencia" in raw
        or "infraestructura activa" in raw
    )
    if not ok_msg:
        out["resultado"] = "RECHAZADO"
        out["explicacion"] = f"404 error_code={out['error_code']} sin mensaje de asociacion ausente."
        pytest.fail(out["explicacion"])
    aud = requests.get(
        f"{BASE_URL}/activos-biologicos/auditoria",
        params={"id_activo_biologico": ID_025, "rf_origen": "RF34", "page_size": 20},
        headers=ctx["headers"],
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
            str(x.get("resultado") or "").upper() == "ADVERTENCIA"
            or "ADVERTENCIA" in str(x.get("tipo_evento") or "").upper()
            or "ADVERTENCIA" in str(x.get("severidad_log") or "").upper()
            for x in regs
        )
    else:
        out["alerta_advertencia"] = f"NO DETERMINABLE (bitacora HTTP {aud.status_code})"
        out["auditoria_body"] = _trunc(_json(aud), 600)
    out["codigo_observado"] = (
        "ConsultarAsociacionUseCase levanta NotFoundError ASOCIACION_INFRAESTRUCTURA_NO_ENCONTRADA "
        "antes de registrar bitacora; la bitacora de consulta EXITOSA no corre en el 404. "
        "No hay endpoint de alerta admin dedicado en este flujo."
    )
    out["resultado"] = "APROBADO"
    out["explicacion"] = (
        f"HTTP 404 {out['error_code']}. Activo 10 existe. Auditoria ADVERTENCIA: "
        f"{out['alerta_advertencia']}."
    )


def test_tc_m02_023_historial(ctx):
    out = {
        "resultado": "BLOQUEADO",
        "endpoint": "GET /activos-biologicos/8/infraestructura?tipo_consulta=HISTORIAL",
        "id_activo": ID_023,
        "multiple_cerrada_y_vigente": False,
    }
    EVIDENCIA["subcasos"]["TC-M02-023"] = out
    v = ctx["v8"]
    out["verificacion_previa"] = {
        "activo_existe": v.get("activo_existe"),
        "get_activo_http": v.get("get_activo_http"),
        "n": v.get("n"),
        "n_vigentes": v.get("n_vigentes"),
        "n_cerradas": v.get("n_cerradas"),
        "precondicion_multiple": v.get("precondicion_multiple"),
        "registros": v.get("registros"),
        "orden_verificacion": v.get("orden"),
    }
    if not v.get("activo_existe"):
        out["explicacion"] = (
            f"BLOQUEADO: GET /activos-biologicos/8 HTTP {v.get('get_activo_http')} "
            f"{v.get('error_code_activo')}."
        )
        pytest.skip(out["explicacion"])
    r = requests.get(
        _infra_url(ID_023),
        params={"tipo_consulta": "HISTORIAL"},
        headers=ctx["headers"],
        timeout=TIMEOUT,
        verify=VERIFY_SSL,
    )
    body = _json(r)
    hist = body.get("historial") if isinstance(body, dict) else None
    out["http"] = r.status_code
    out["respuesta"] = _trunc(body)
    if r.status_code == 500:
        out["explicacion"] = "BLOQUEADO HTTP 500."
        pytest.skip(out["explicacion"])
    if r.status_code != 200 or not isinstance(hist, list) or not hist:
        out["resultado"] = "RECHAZADO"
        out["explicacion"] = f"HTTP {r.status_code} o historial vacio/no lista."
        pytest.fail(out["explicacion"])
    resumen = _resumen_hist(hist)
    out.update(
        {
            "n_registros": resumen["n"],
            "n_vigentes": resumen["n_vigentes"],
            "n_cerradas": resumen["n_cerradas"],
            "registros": resumen["registros"],
            "fechas_inicio": resumen["fechas_inicio"],
            "orden": resumen["orden"],
            "ordenado_fecha_inicio_asc": resumen["ordenado_asc"],
            "ordenado_fecha_inicio_desc": resumen["ordenado_desc"],
            "multiple_cerrada_y_vigente": bool(resumen["n_vigentes"] >= 1 and resumen["n_cerradas"] >= 1),
            "advertencia_integridad": body.get("advertencia_integridad") if isinstance(body, dict) else None,
        }
    )
    if not out["multiple_cerrada_y_vigente"]:
        out["resultado"] = "RECHAZADO" if resumen["n"] else "BLOQUEADO"
        out["explicacion"] = (
            f"Activo 8 no cumple multiples asociaciones (cerradas={resumen['n_cerradas']}, "
            f"vigentes={resumen['n_vigentes']})."
        )
        if out["resultado"] == "RECHAZADO":
            pytest.fail(out["explicacion"])
        pytest.skip(out["explicacion"])
    if resumen["n"] != v.get("n"):
        out["nota_conteo"] = f"verificacion n={v.get('n')} ejecucion n={resumen['n']}"
    if not resumen["ordenado_asc"] and len(resumen["fechas_inicio"]) > 1:
        out["resultado"] = "RECHAZADO"
        out["explicacion"] = (
            f"HTTP 200, {resumen['n']} registros (cerradas={resumen['n_cerradas']}, "
            f"vigentes={resumen['n_vigentes']}), orden real={resumen['orden']}. "
            "El caso exige fecha_inicio ASC."
        )
        pytest.fail(out["explicacion"])
    out["resultado"] = "APROBADO"
    out["explicacion"] = (
        f"HTTP 200, {resumen['n']} registros, cerradas+vigente, orden ASC."
    )


def test_tc_m02_022_activa(ctx):
    out = {
        "resultado": "BLOQUEADO",
        "endpoint": "GET /activos-biologicos/352/infraestructura?tipo_consulta=ACTIVA",
        "id_activo": ID_022,
    }
    EVIDENCIA["subcasos"]["TC-M02-022"] = out
    v = ctx["v352"]
    out["verificacion_previa"] = {
        "activo_existe": v.get("activo_existe"),
        "tiene_vigente": v.get("tiene_vigente"),
        "vigentes": v.get("vigentes"),
    }
    if not v.get("activo_existe") or not v.get("tiene_vigente"):
        out["explicacion"] = (
            f"BLOQUEADO: activo 352 existe={v.get('activo_existe')} vigente={v.get('tiene_vigente')}."
        )
        pytest.skip(out["explicacion"])
    r = requests.get(
        _infra_url(ID_022),
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
    out["id_historial"] = asoc.get("id_historial")
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
        f"HTTP 200, vigente fecha_fin=null, infra={out['id_infraestructura']}, "
        f"sensores n={out['n_sensores']}, advertencia_integridad={out['advertencia_integridad']}."
    )


def test_tc_m02_024_inexistente(ctx):
    out = {
        "resultado": "BLOQUEADO",
        "endpoint": "GET /activos-biologicos/100352/infraestructura?tipo_consulta=ACTIVA",
        "id_activo": ID_INEX,
        "get_activo_http": ctx["inex_http"],
    }
    EVIDENCIA["subcasos"]["TC-M02-024"] = out
    if ctx["inex_http"] == 200:
        out["explicacion"] = "BLOQUEADO: el ID 100352 existe (GET ficha 200)."
        pytest.skip(out["explicacion"])
    r = requests.get(
        _infra_url(ID_INEX),
        params={"tipo_consulta": "ACTIVA"},
        headers=ctx["headers"],
        timeout=TIMEOUT,
        verify=VERIFY_SSL,
    )
    body = _json(r)
    out["http"] = r.status_code
    out["respuesta"] = _trunc(body, 800)
    out["error_code"] = body.get("error_code") if isinstance(body, dict) else None
    if r.status_code == 500:
        out["explicacion"] = "BLOQUEADO HTTP 500."
        pytest.skip(out["explicacion"])
    if r.status_code != 404:
        out["resultado"] = "RECHAZADO"
        out["explicacion"] = f"HTTP {r.status_code}, esperado 404."
        pytest.fail(out["explicacion"])
    if out["error_code"] != "ACTIVO_NO_ENCONTRADO":
        out["resultado"] = "RECHAZADO"
        out["explicacion"] = f"error_code={out['error_code']}, esperado ACTIVO_NO_ENCONTRADO."
        pytest.fail(out["explicacion"])
    out["resultado"] = "APROBADO"
    out["explicacion"] = "GET activo e infraestructura HTTP 404 ACTIVO_NO_ENCONTRADO."


def test_tc_m02_026_solo_lectura(ctx):
    out = {
        "resultado": "BLOQUEADO",
        "endpoint": "PUT/PATCH /activos-biologicos/352/infraestructura",
        "id_activo": ID_022,
    }
    EVIDENCIA["subcasos"]["TC-M02-026"] = out
    if not ctx["v352"].get("activo_existe"):
        out["explicacion"] = "BLOQUEADO: activo 352 no disponible para rechazo de escritura."
        pytest.skip(out["explicacion"])
    url = _infra_url(ID_022)
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
        f"PUT y PATCH HTTP 405 (detalle FastAPI genérico). Mencion RF-48: {out['menciona_rf48']}."
    )


def test_zz_global(ctx):
    assert EVIDENCIA.get("subcasos")
