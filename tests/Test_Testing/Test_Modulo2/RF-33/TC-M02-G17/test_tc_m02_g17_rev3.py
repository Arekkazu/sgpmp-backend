"""TC-M02-G17 rev3 — atributos dinamicos obligatorios/tipo y TRANSFERENCIA_INTERNA.

No modifica rev1/rev2, RF-16 ni codigo productivo. Restaura via PATCH /estado.
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
ENV_PATH = DIR / "environment-g17-rev3.json"

with ENV_PATH.open(encoding="utf-8") as fh:
    ENV = json.load(fh)

BASE_URL = ENV["baseUrl"].rstrip("/")
CORREO_ADMIN = ENV["correo_admin"]
CORREO_PROD = ENV["correo_productor"]
INFRA = int(ENV["infraestructura_id"])
ESPECIE_189 = int(ENV["especie_sin_metricas"])
TIMEOUT = 45
VERIFY_SSL = False
STAMP = datetime.now(timezone.utc).strftime("%H%M%S%f")[:12]

EVIDENCIA: dict = {
    "caso": "TC-M02-G17",
    "revision": 3,
    "rf": ["RF-33", "RF-16"],
    "cu": "CU01",
    "ambiente": "TEST",
    "base_url": BASE_URL,
    "fecha_utc": datetime.now(timezone.utc).isoformat(),
    "contrato": {
        "POST": "POST /activos-biologicos — OpenAPI 201/400/401/403/409/422",
        "GET_metricas": "GET /configuracion/metricas?id_especie= — RF-16, incluye es_obligatorio y tipo_dato",
        "GET_activo": "GET /activos-biologicos/{id}",
        "restaurar": "PATCH /activos-biologicos/{id}/estado",
        "origen_financiero": "campo origen_financiero; valores compra|nacimiento|donacion|transferencia_interna",
        "costo": "costo_adquisicion y soporte_documental (no soporte_documental_costo)",
        "ATRIBUTO_REQUERIDO": "BusinessRuleError HTTP 422",
        "ATRIBUTO_TIPO_INVALIDO": "BusinessRuleError HTTP 422",
        "FA08_transferencia": "transferencia_interna no exige ni rechaza costo (solo compra/donacion exigen; nacimiento rechaza)",
    },
    "subcasos": {},
    "ids_creados": [],
    "estado_global": "PENDIENTE",
    "auditoria": "Rev1/rev2 no modificadas. Sin DML. Sin cambios RF-16 ni productivos. Sin commit/push.",
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


def _payload_ind(especie: int, identificador: str, origen: str, atributos: dict | None, costo=None, soporte=None) -> dict:
    return {
        "tipo_activo": "INDIVIDUAL",
        "id_especie": especie,
        "fecha_inicio_ciclo": "2026-09-09",
        "origen_financiero": origen,
        "costo_adquisicion": costo,
        "soporte_documental": soporte,
        "id_infraestructura": INFRA,
        "atributos_dinamicos": atributos if atributos is not None else {},
        "identificador": identificador,
        "raza": "QA-G17-R3",
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
        "body": _trunc(body, 1400),
    }


def _valor_control_numerico(metrica: dict):
    # GET metricas no expone min/max; usar 25 si hay historial de peso_destete 20-40, si no 1.
    nombre = str(metrica.get("nombre") or "").lower()
    if "destete" in nombre:
        return 25
    return 1


def _escribir():
    RESULTADOS.mkdir(parents=True, exist_ok=True)
    payload = _redact(EVIDENCIA)
    (RESULTADOS / "TC-M02-G17-rev3.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    subs = payload.get("subcasos") or {}
    lineas = [
        "TC-M02-G17 rev3 — RF-33 — TEST",
        f"Fecha UTC: {payload.get('fecha_utc')}",
        f"Global: {payload.get('estado_global')}",
        "",
        f"TC-M02-187: {(subs.get('TC-M02-187') or {}).get('resultado')}",
        f"TC-M02-188: {(subs.get('TC-M02-188') or {}).get('resultado')}",
        f"TC-M02-189: {(subs.get('TC-M02-189') or {}).get('resultado')}",
        "",
        json.dumps(subs, ensure_ascii=False, indent=2, default=str),
        "",
        payload.get("auditoria"),
        "Password/JWT: [REDACTED]. Rev1/rev2 no modificadas.",
    ]
    (RESULTADOS / "TC-M02-G17-rev3.txt").write_text("\n".join(lineas) + "\n", encoding="utf-8")
    bloques = []
    for k, v in subs.items():
        bloques.append(
            f"<h2>{k}</h2><p>Resultado: {v.get('resultado')}</p>"
            f"<pre>{json.dumps(v, ensure_ascii=False, indent=2, default=str)}</pre>"
        )
    (RESULTADOS / "TC-M02-G17-rev3-evidencia.html").write_text(
        "<!DOCTYPE html><html lang='es'><head><meta charset='utf-8'>"
        "<title>TC-M02-G17 rev3</title></head><body>"
        "<h1>TC-M02-G17 rev3</h1>"
        f"<p>Global: {payload.get('estado_global')}</p>"
        + "".join(bloques)
        + "<p>Sin secretos. Rev1/rev2 intactas.</p></body></html>",
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
        "obligatoria": None,
        "tipo": None,
        "metricas_scan": [],
        "metricas_500": [],
    }
    EVIDENCIA["logins"] = {
        "admin": {"correo": CORREO_ADMIN, "http": http_a, "ok": bool(tok_a)},
        "productor": {"correo": CORREO_PROD, "http": http_p, "ok": bool(tok_p)},
    }
    if tok_a:
        re = requests.get(
            f"{BASE_URL}/configuracion/especies",
            headers=_auth(tok_a),
            timeout=TIMEOUT,
            verify=VERIFY_SSL,
        )
        especies = _registros(_json(re)) if re.status_code == 200 else []
        data["especies_http"] = re.status_code
        data["especies_n"] = len(especies)
        for e in especies:
            eid = e.get("id_especie") or e.get("id")
            if eid is None:
                continue
            rm = requests.get(
                f"{BASE_URL}/configuracion/metricas",
                params={"id_especie": int(eid)},
                headers=_auth(tok_a),
                timeout=TIMEOUT,
                verify=VERIFY_SSL,
            )
            bm = _json(rm)
            items = bm.get("items") or [] if isinstance(bm, dict) else []
            row = {"id_especie": int(eid), "http": rm.status_code, "n": len(items) if rm.status_code == 200 else None}
            if rm.status_code == 500:
                data["metricas_500"].append(int(eid))
            data["metricas_scan"].append(row)
            if rm.status_code != 200:
                continue
            for it in items:
                if not isinstance(it, dict) or it.get("es_activo") is False:
                    continue
                if data["obligatoria"] is None and it.get("es_obligatorio") is True and _aplica_individual(it.get("aplica_a_tipo_activo")):
                    data["obligatoria"] = {"id_especie": int(eid), **{k: it.get(k) for k in (
                        "id_metrica_produccion", "nombre", "tipo_dato", "es_obligatorio",
                        "aplica_a_tipo_activo", "es_activo",
                    )}}
                td = str(it.get("tipo_dato") or "").upper()
                if data["tipo"] is None and td in ("NUMERICO", "ENTERO", "TEXTO", "BOOLEANO") and _aplica_individual(it.get("aplica_a_tipo_activo")):
                    data["tipo"] = {"id_especie": int(eid), **{k: it.get(k) for k in (
                        "id_metrica_produccion", "nombre", "tipo_dato", "es_obligatorio",
                        "aplica_a_tipo_activo", "es_activo",
                    )}}
        EVIDENCIA["precondiciones_metricas"] = {
            "especies_http": data["especies_http"],
            "especies_n": data["especies_n"],
            "scan": data["metricas_scan"],
            "http_500_especies": data["metricas_500"],
            "obligatoria": data["obligatoria"],
            "para_tipo": data["tipo"],
        }
    yield data
    _escribir()


def test_tc_m02_187_atributo_obligatorio_ausente(sesion):
    out = {
        "resultado": "BLOQUEADO",
        "endpoint": "POST /activos-biologicos",
        "metrica": sesion.get("obligatoria"),
        "control": None,
        "omision": None,
        "null": None,
        "conclusion": "",
    }
    EVIDENCIA["subcasos"]["TC-M02-187"] = out
    if not sesion["productor"]["ok"]:
        out["conclusion"] = f"BLOQUEADO: login Productor HTTP {sesion['productor']['http']}."
        pytest.skip(out["conclusion"])
    if sesion.get("metricas_500") and not sesion.get("obligatoria"):
        out["conclusion"] = f"BLOQUEADO: GET metricas HTTP 500 en {sesion['metricas_500']}."
        pytest.skip(out["conclusion"])
    met = sesion.get("obligatoria")
    if not met:
        out["conclusion"] = (
            "BLOQUEADO: no hay metrica RF-16 activa, obligatoria y aplicable a INDIVIDUAL. "
            "No se inventa ni se modifica RF-16."
        )
        pytest.skip(out["conclusion"])

    tok = sesion["productor"]["token"]
    eid = met["id_especie"]
    nombre = met["nombre"]
    td = str(met.get("tipo_dato") or "").upper()
    if td in ("NUMERICO", "ENTERO"):
        valor_ok = _valor_control_numerico(met)
        if td == "ENTERO":
            valor_ok = int(valor_ok)
    elif td == "BOOLEANO":
        valor_ok = True
    else:
        valor_ok = "QA"
    ident_c = f"QAG17R3C{STAMP}"[:50]
    r_c = _post(tok, _payload_ind(eid, ident_c, "nacimiento", {nombre: valor_ok}))
    out["control"] = _cap(r_c)
    out["control"]["atributo_enviado"] = {nombre: valor_ok}
    if out["control"]["http"] == 201 and out["control"]["id_creado"]:
        EVIDENCIA["ids_creados"].append(int(out["control"]["id_creado"]))
        out["control"]["restauracion"] = _restaurar(
            tok, int(out["control"]["id_creado"]), "Restauracion control 187 TC-M02-G17 rev3"
        )
    elif out["control"]["http"] == 500:
        out["conclusion"] = "BLOQUEADO: POST control HTTP 500; no se evalua omision."
        pytest.skip(out["conclusion"])
    elif out["control"]["http"] != 201:
        out["conclusion"] = (
            f"BLOQUEADO: POST control HTTP {out['control']['http']} "
            f"{out['control']['error_code']} al incluir '{nombre}'. No se evalua omision."
        )
        pytest.skip(out["conclusion"])

    ident_o = f"QAG17R3O{STAMP}"[:50]
    r_o = _post(tok, _payload_ind(eid, ident_o, "nacimiento", {}))
    out["omision"] = _cap(r_o)
    if out["omision"]["http"] == 201 and out["omision"]["id_creado"]:
        EVIDENCIA["ids_creados"].append(int(out["omision"]["id_creado"]))
        out["omision"]["restauracion"] = _restaurar(
            tok, int(out["omision"]["id_creado"]), "Restauracion omision 187 (no debio crear)"
        )
        out["resultado"] = "RECHAZADO"
        out["conclusion"] = "El POST sin atributo obligatorio creo un activo."
        pytest.fail(out["conclusion"])

    ident_n = f"QAG17R3N{STAMP}"[:50]
    r_n = _post(tok, _payload_ind(eid, ident_n, "nacimiento", {nombre: None}))
    out["null"] = _cap(r_n)
    if out["null"]["http"] == 201 and out["null"]["id_creado"]:
        EVIDENCIA["ids_creados"].append(int(out["null"]["id_creado"]))
        out["null"]["restauracion"] = _restaurar(
            tok, int(out["null"]["id_creado"]), "Restauracion null 187 (no debio crear)"
        )
        out["resultado"] = "RECHAZADO"
        out["conclusion"] = "El POST con atributo obligatorio null creo un activo."
        pytest.fail(out["conclusion"])

    def _ok_rechazo(cap: dict) -> bool:
        if cap["id_creado"]:
            return False
        if cap["http"] == 422:
            return True
        if cap["http"] in (400, 422) and str(cap.get("error_code") or "") in (
            "ATRIBUTO_REQUERIDO", "VAL_ENTRADA", "VALOR_FUERA_DE_RANGO",
        ):
            return True
        code = str(cap.get("error_code") or "")
        msg = str(cap.get("message") or "").lower()
        return cap["http"] in (400, 422) and ("obligator" in msg or "requerid" in msg or "ATRIBUTO" in code)

    if not _ok_rechazo(out["omision"]):
        out["resultado"] = "RECHAZADO"
        out["conclusion"] = (
            f"Omision HTTP {out['omision']['http']} {out['omision']['error_code']} "
            "no evidencia rechazo del atributo obligatorio."
        )
        pytest.fail(out["conclusion"])
    out["resultado"] = "APROBADO"
    out["conclusion"] = (
        f"Metrica '{nombre}' especie {eid} obligatoria={met.get('es_obligatorio')} "
        f"tipo={td} aplica={met.get('aplica_a_tipo_activo')}. "
        f"Control HTTP {out['control']['http']}. Omision HTTP {out['omision']['http']} "
        f"{out['omision']['error_code']}. Null HTTP {out['null']['http']} {out['null']['error_code']}. "
        "Sin ID creado en omision/null."
    )


def test_tc_m02_188_tipo_incorrecto(sesion):
    out = {
        "resultado": "BLOQUEADO",
        "endpoint": "POST /activos-biologicos",
        "metrica": sesion.get("tipo"),
        "intento": None,
        "conclusion": "",
    }
    EVIDENCIA["subcasos"]["TC-M02-188"] = out
    if not sesion["productor"]["ok"]:
        out["conclusion"] = "BLOQUEADO: sin Productor."
        pytest.skip(out["conclusion"])
    met = sesion.get("tipo")
    if not met:
        out["conclusion"] = "BLOQUEADO: no hay metrica activa con tipo_dato utilizable. No se modifica RF-16."
        pytest.skip(out["conclusion"])

    tok = sesion["productor"]["token"]
    eid = met["id_especie"]
    nombre = met["nombre"]
    td = str(met.get("tipo_dato") or "").upper()
    if td in ("NUMERICO", "ENTERO"):
        valor_malo = "texto-no-numerico"
    elif td == "TEXTO":
        valor_malo = 12345
    elif td == "BOOLEANO":
        valor_malo = "no-bool"
    else:
        out["conclusion"] = f"BLOQUEADO: tipo_dato {td} no mapeado."
        pytest.skip(out["conclusion"])

    ident = f"QAG17R3T{STAMP}"[:50]
    extras = {}
    obl = sesion.get("obligatoria")
    if obl and obl.get("id_especie") == eid and obl.get("nombre") != nombre:
        otd = str(obl.get("tipo_dato") or "").upper()
        extras[obl["nombre"]] = 25 if otd in ("NUMERICO", "ENTERO") else True if otd == "BOOLEANO" else "QA"

    r = _post(tok, _payload_ind(eid, ident, "nacimiento", {nombre: valor_malo, **extras}))
    out["intento"] = _cap(r)
    out["intento"]["valor_enviado"] = {nombre: valor_malo}
    out["intento"]["tipo_configurado"] = td
    if out["intento"]["http"] == 201 and out["intento"]["id_creado"]:
        aid = int(out["intento"]["id_creado"])
        EVIDENCIA["ids_creados"].append(aid)
        g = _get(tok, aid)
        gb = _json(g)
        attrs = gb.get("atributos_dinamicos") if isinstance(gb, dict) else None
        out["intento"]["persistido"] = attrs
        out["intento"]["restauracion"] = _restaurar(tok, aid, "Restauracion 188 (no debio crear)")
        out["resultado"] = "RECHAZADO"
        out["conclusion"] = f"Acepto y persistio valor incompatible con tipo {td}."
        pytest.fail(out["conclusion"])
    if out["intento"]["http"] == 500:
        out["resultado"] = "RECHAZADO"
        out["conclusion"] = "HTTP 500 ante tipo incorrecto."
        pytest.fail(out["conclusion"])
    code = str(out["intento"].get("error_code") or "")
    if out["intento"]["http"] in (400, 422) and (
        code in ("ATRIBUTO_TIPO_INVALIDO", "VAL_ENTRADA")
        or "tipo" in str(out["intento"].get("message") or "").lower()
    ):
        out["resultado"] = "APROBADO"
        out["conclusion"] = (
            f"Metrica '{nombre}' tipo={td} especie {eid}. POST HTTP {out['intento']['http']} "
            f"{code}. Sin ID creado."
        )
        return
    out["resultado"] = "RECHAZADO"
    out["conclusion"] = (
        f"HTTP {out['intento']['http']} {code} no evidencia rechazo de tipo."
    )
    pytest.fail(out["conclusion"])


def test_tc_m02_189_transferencia_interna(sesion):
    out = {
        "resultado": "BLOQUEADO",
        "endpoint": "POST /activos-biologicos",
        "campo_origen": "origen_financiero",
        "valor_origen": "transferencia_interna",
        "control": None,
        "post": None,
        "get": None,
        "restauracion": None,
        "conclusion": "",
    }
    EVIDENCIA["subcasos"]["TC-M02-189"] = out
    if not sesion["productor"]["ok"]:
        out["conclusion"] = "BLOQUEADO: sin Productor."
        pytest.skip(out["conclusion"])
    tok = sesion["productor"]["token"]
    ident_c = f"QAG17R3K{STAMP}"[:50]
    r_c = _post(tok, _payload_ind(ESPECIE_189, ident_c, "nacimiento", {}))
    out["control"] = _cap(r_c)
    if out["control"]["http"] == 201 and out["control"]["id_creado"]:
        EVIDENCIA["ids_creados"].append(int(out["control"]["id_creado"]))
        out["control"]["restauracion"] = _restaurar(
            tok, int(out["control"]["id_creado"]), "Restauracion control 189 TC-M02-G17 rev3"
        )
    elif out["control"]["http"] == 500:
        out["conclusion"] = "BLOQUEADO: POST control nacimiento HTTP 500 (historico INC-M02-47-G17)."
        pytest.skip(out["conclusion"])
    elif out["control"]["http"] != 201:
        out["conclusion"] = (
            f"BLOQUEADO: control HTTP {out['control']['http']} {out['control']['error_code']}."
        )
        pytest.skip(out["conclusion"])

    ident = f"QAG17R3F{STAMP}"[:50]
    payload = _payload_ind(ESPECIE_189, ident, "transferencia_interna", {}, costo=None, soporte=None)
    out["request_campos"] = {
        "origen_financiero": payload["origen_financiero"],
        "costo_adquisicion": payload["costo_adquisicion"],
        "soporte_documental": payload["soporte_documental"],
    }
    r = _post(tok, payload)
    out["post"] = _cap(r)
    if r.status_code == 500:
        out["resultado"] = "RECHAZADO"
        out["conclusion"] = "POST transferencia_interna HTTP 500 ERROR_INTERNO."
        pytest.fail(out["conclusion"])
    if r.status_code in (400, 422):
        code = str(out["post"].get("error_code") or "")
        if "COSTO" in code or "SOPORTE" in code:
            out["resultado"] = "RECHAZADO"
            out["conclusion"] = f"Exige costo/soporte para transferencia_interna: {code}."
            pytest.fail(out["conclusion"])
        out["resultado"] = "RECHAZADO"
        out["conclusion"] = f"POST HTTP {r.status_code} {code}; esperado 201."
        pytest.fail(out["conclusion"])
    if r.status_code != 201 or not out["post"]["id_creado"]:
        out["conclusion"] = f"POST HTTP {r.status_code}; no se obtuvo ID."
        pytest.skip(out["conclusion"])

    aid = int(out["post"]["id_creado"])
    EVIDENCIA["ids_creados"].append(aid)
    g = _get(tok, aid)
    gb = _json(g)
    out["get"] = {
        "http": g.status_code,
        "origen_financiero": gb.get("origen_financiero") if isinstance(gb, dict) else None,
        "costo_adquisicion": gb.get("costo_adquisicion") if isinstance(gb, dict) else None,
        "soporte_documental": gb.get("soporte_documental") if isinstance(gb, dict) else None,
        "nombre_estado": gb.get("nombre_estado") if isinstance(gb, dict) else None,
        "body": _trunc(gb, 1400),
    }
    origen_ok = str(out["get"]["origen_financiero"] or "").lower() == "transferencia_interna"
    costo_ok = out["get"]["costo_adquisicion"] in (None, "", [])
    sop_ok = out["get"]["soporte_documental"] in (None, "", [])
    out["restauracion"] = _restaurar(tok, aid, "Restauracion 189 TRANSFERENCIA_INTERNA TC-M02-G17 rev3")
    if g.status_code != 200 or not origen_ok or not costo_ok or not sop_ok:
        out["resultado"] = "RECHAZADO"
        out["conclusion"] = (
            f"GET HTTP {g.status_code} origen={out['get']['origen_financiero']} "
            f"costo={out['get']['costo_adquisicion']} soporte={out['get']['soporte_documental']}."
        )
        pytest.fail(out["conclusion"])
    if str(out["restauracion"].get("estado") or "").upper() != "INACTIVO":
        out["resultado"] = "RECHAZADO"
        out["conclusion"] = f"Restauracion no dejo INACTIVO: {out['restauracion']}."
        pytest.fail(out["conclusion"])
    out["resultado"] = "APROBADO"
    out["conclusion"] = (
        f"POST 201 id={aid} origen=transferencia_interna sin costo/soporte. "
        f"GET confirma nulls. Restaurado INACTIVO HTTP {out['restauracion']['http_estado']}."
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
