"""TC-M02-G15 rev3 — cierre de subcasos bloqueados en TEST.

No reejecuta BOLA (INC-M02-G15-001). No modifica historico, rev2 ni backend.
"""
from __future__ import annotations

import base64
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
ENV_PATH = DIR / "environment-g15-rev3.json"

with ENV_PATH.open(encoding="utf-8") as fh:
    ENV = json.load(fh)

BASE_URL = ENV["baseUrl"].rstrip("/")
CORREO_ADMIN = ENV["correo_admin"]
CORREO_INGENIERO = ENV["correo_ingeniero"]
ACTIVO_HIST_031 = int(ENV["activo_historico_031"])
TIMEOUT = 45
VERIFY_SSL = False
CAMPOS_FINANCIEROS = ("costo_adquisicion", "soporte_documental", "soporte_documental_costo")

EVIDENCIA: dict = {
    "caso": "TC-M02-G15",
    "revision": 3,
    "rf": ["RF-33", "RF-34"],
    "ambiente": "TEST",
    "base_url": BASE_URL,
    "fecha_utc": datetime.now(timezone.utc).isoformat(),
    "subcasos": {},
    "estado_global": "PENDIENTE",
    "inc_m02_g15_001": {
        "id": "INC-M02-G15-001",
        "severidad": "CRITICO",
        "estado": "PENDIENTE",
        "nota": (
            "BOLA de escritura confirmada en rev2: Productor m2m.nuevo@ejemplo.com "
            "finca 57 PATCH /activos-biologicos/350 (finca 65) HTTP 200 y persistio raza. "
            "Esta rev3 no reejecuta el escenario. Backend no validado como corregido."
        ),
    },
    "auditoria": (
        "Historico Newman y evidencias rev2 no modificados. Codigo productivo no "
        "modificado. Sin commit ni push. Un login por usuario en esta corrida."
    ),
}


def _password() -> str:
    valor = os.environ.get("SGPMP_TEST_PASSWORD") or os.environ.get("CONTRASENA") or ""
    if not valor:
        pytest.skip("BLOQUEADO: definir SGPMP_TEST_PASSWORD o CONTRASENA.")
    return valor


def _password_ingeniero() -> str:
    return (
        os.environ.get("SGPMP_INGENIERO_PASSWORD")
        or os.environ.get("ENGINEER_PASSWORD")
        or _password()
    )


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


def _trunc(obj, n=2500):
    text = json.dumps(_redact(obj), ensure_ascii=False, default=str)
    if len(text) > n:
        return text[:n] + "...[TRUNCATED]"
    return text


def _jwt_claims(token: str) -> dict:
    try:
        payload = token.split(".")[1]
        pad = "=" * (-len(payload) % 4)
        data = json.loads(base64.urlsafe_b64decode(payload + pad))
        return {
            "rol": data.get("rol") or data.get("role"),
            "correo": data.get("correo") or data.get("sub"),
            "id_usuario": data.get("id_usuario") or data.get("uid"),
            "claves": sorted(str(k) for k in data.keys()),
        }
    except Exception as exc:
        return {"error": f"NO DETERMINABLE: {exc}"}


def _login(correo: str, password: str) -> tuple[int, dict | None, str | None]:
    r = requests.post(
        f"{BASE_URL}/sesiones/",
        json={"correo_electronico": correo, "contrasena": password},
        timeout=TIMEOUT,
        verify=VERIFY_SSL,
    )
    body = None
    try:
        body = r.json()
    except Exception:
        body = {"raw": (r.text or "")[:400]}
    token = None
    if isinstance(body, dict):
        token = body.get("token") or (body.get("data") or {}).get("token")
    return r.status_code, body if isinstance(body, dict) else {"body": body}, token


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _json(r: requests.Response):
    try:
        return r.json()
    except Exception:
        return {"raw": (r.text or "")[:600]}


def _registros(body) -> list:
    if isinstance(body, list):
        return body
    if isinstance(body, dict):
        for k in ("registros", "items", "data"):
            v = body.get(k)
            if isinstance(v, list):
                return v
    return []


def _walk_keys(obj, wanted: tuple[str, ...], path="") -> list[dict]:
    hits = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{path}.{k}" if path else str(k)
            if str(k) in wanted:
                hits.append({"path": p, "valor": v})
            hits.extend(_walk_keys(v, wanted, p))
    elif isinstance(obj, list):
        for i, item in enumerate(obj[:30]):
            hits.extend(_walk_keys(item, wanted, f"{path}[{i}]"))
    return hits


def _hits_con_valor(obj) -> list[dict]:
    return [h for h in _walk_keys(obj, CAMPOS_FINANCIEROS) if h.get("valor") not in (None, "", [])]


def _listar_activos(token: str, page_size=100, max_paginas=8) -> tuple[int, list]:
    todos = []
    last_http = 0
    for pagina in range(1, max_paginas + 1):
        r = requests.get(
            f"{BASE_URL}/activos-biologicos",
            params={"pagina": pagina, "page_size": page_size},
            headers=_auth(token),
            timeout=TIMEOUT,
            verify=VERIFY_SSL,
        )
        last_http = r.status_code
        if r.status_code != 200:
            return last_http, todos
        body = _json(r)
        regs = _registros(body)
        todos.extend(regs)
        total = body.get("total_registros") if isinstance(body, dict) else None
        if not regs:
            break
        if total is not None and len(todos) >= int(total):
            break
        if len(regs) < page_size:
            break
    return last_http, todos


def _escribir_evidencia() -> None:
    RESULTADOS.mkdir(parents=True, exist_ok=True)
    payload = _redact(EVIDENCIA)
    json_path = RESULTADOS / "TC-M02-G15-rev3.json"
    txt_path = RESULTADOS / "TC-M02-G15-rev3.txt"
    html_path = RESULTADOS / "TC-M02-G15-rev3-evidencia.html"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    lineas = [
        "TC-M02-G15 rev3 — cierre bloqueos TEST",
        f"Fecha UTC: {payload.get('fecha_utc')}",
        f"Estado global: {payload.get('estado_global')}",
        "",
        json.dumps(payload.get("subcasos"), ensure_ascii=False, indent=2, default=str),
        "",
        json.dumps(payload.get("inc_m02_g15_001"), ensure_ascii=False, indent=2, default=str),
        payload.get("auditoria"),
        "Password/JWT: [REDACTED]. Historico Newman y rev2 no modificados.",
    ]
    txt_path.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    bloques = []
    for k, v in (payload.get("subcasos") or {}).items():
        bloques.append(
            f"<h2>{k}</h2><p>Resultado: {v.get('resultado')}</p>"
            f"<pre>{json.dumps(v, ensure_ascii=False, indent=2, default=str)}</pre>"
        )
    html_path.write_text(
        "<!DOCTYPE html><html lang='es'><head><meta charset='utf-8'>"
        "<title>TC-M02-G15 rev3</title></head><body>"
        "<h1>TC-M02-G15 rev3 cierre de bloqueos</h1>"
        f"<p>Estado global: {payload.get('estado_global')}</p>"
        + "".join(bloques)
        + "<p>Sin passwords ni JWT. Historico y rev2 no modificados.</p>"
        "</body></html>",
        encoding="utf-8",
    )


@pytest.fixture(scope="session")
def sesion():
    _password()
    http_a, body_a, tok_a = _login(CORREO_ADMIN, _password())
    http_i, body_i, tok_i = _login(CORREO_INGENIERO, _password_ingeniero())
    data = {
        "admin": {
            "http": http_a,
            "token": tok_a,
            "claims": _jwt_claims(tok_a) if tok_a else None,
            "login_ok": bool(tok_a),
            "claves_body": list((body_a or {}).keys()) if isinstance(body_a, dict) else [],
        },
        "ingeniero": {
            "http": http_i,
            "token": tok_i,
            "claims": _jwt_claims(tok_i) if tok_i else None,
            "login_ok": bool(tok_i),
            "claves_body": list((body_i or {}).keys()) if isinstance(body_i, dict) else [],
            "error_code": (body_i or {}).get("error_code") if isinstance(body_i, dict) else None,
        },
        "veterinario": {
            "login": "NO EJECUTADO",
            "motivo": "El caso historico 031 usa GET ficha con Ingeniero; Admin confirma campos financieros.",
        },
    }
    EVIDENCIA["logins"] = {
        "admin": {"correo": CORREO_ADMIN, "http": http_a, "ok": bool(tok_a), "intentos": 1},
        "ingeniero": {
            "correo": CORREO_INGENIERO,
            "http": http_i,
            "ok": bool(tok_i),
            "intentos": 1,
            "error_code": data["ingeniero"]["error_code"],
        },
        "veterinario": data["veterinario"],
    }
    yield data
    _escribir_evidencia()


def test_tc_m02_027_bola_no_reejecutado(sesion):
    out = {
        "resultado": "RECHAZADO",
        "reejecutado": False,
        "incidente": "INC-M02-G15-001",
        "evidencia_previa": "TC-M02-G15-rev2.json TC-M02-027",
        "conclusion_bola": (
            "No se reejecuto BOLA. Permanece pendiente INC-M02-G15-001: PATCH HTTP 200 "
            "sobre activo 350 (finca 65) por Productor de finca 57. GET habia sido 404."
        ),
    }
    EVIDENCIA["subcasos"]["TC-M02-027"] = out
    pytest.skip(out["conclusion_bola"])


def test_tc_m02_028_mass_assignment(sesion):
    out = {
        "resultado": "BLOQUEADO",
        "payload_campos_protegidos": {"estado": "CERRADO", "cantidad_actual": 9999},
        "http_post": None,
        "id_creado": None,
        "estado_persistido": None,
        "cantidad_actual_persistida": None,
        "residuo": None,
        "conclusion_mass_assignment": "",
    }
    EVIDENCIA["subcasos"]["TC-M02-028"] = out
    if not sesion["admin"]["login_ok"]:
        out["conclusion_mass_assignment"] = f"BLOQUEADO: login Admin HTTP {sesion['admin']['http']}."
        pytest.skip(out["conclusion_mass_assignment"])
    tok = sesion["admin"]["token"]
    r_esp = requests.get(
        f"{BASE_URL}/configuracion/especies",
        headers=_auth(tok),
        timeout=TIMEOUT,
        verify=VERIFY_SSL,
    )
    especies = _registros(_json(r_esp)) if r_esp.status_code == 200 else []
    especie = next(
        (e for e in especies if e.get("id_especie") == 4 or "cachama" in str(e.get("nombre") or "").lower()),
        especies[0] if especies else None,
    )
    r_inf = requests.get(
        f"{BASE_URL}/configuracion/infraestructuras",
        params={"finca_id": 1, "solo_activas": True},
        headers=_auth(tok),
        timeout=TIMEOUT,
        verify=VERIFY_SSL,
    )
    infras = _registros(_json(r_inf)) if r_inf.status_code == 200 else []
    infra = infras[0] if infras else None
    if not especie or not infra:
        out["conclusion_mass_assignment"] = (
            f"BLOQUEADO: precondicion especie/infra. especies_http={r_esp.status_code} "
            f"infra_http={r_inf.status_code}."
        )
        pytest.skip(out["conclusion_mass_assignment"])
    payload = {
        "tipo_activo": "POBLACIONAL",
        "id_especie": int(especie.get("id_especie") or especie.get("id")),
        "fecha_inicio_ciclo": "2026-09-09",
        "origen_financiero": "nacimiento",
        "id_infraestructura": int(infra.get("id_infraestructura") or infra.get("id")),
        "atributos_dinamicos": {},
        "cantidad_inicial": 10,
        "peso_promedio_inicial": 2.5,
        "costo_adquisicion": None,
        "soporte_documental": None,
        "estado": "CERRADO",
        "cantidad_actual": 9999,
    }
    out["payload"] = payload
    r_post = requests.post(
        f"{BASE_URL}/activos-biologicos",
        headers={**_auth(tok), "Content-Type": "application/json"},
        json=payload,
        timeout=TIMEOUT,
        verify=VERIFY_SSL,
    )
    body_post = _json(r_post)
    out["http_post"] = r_post.status_code
    out["respuesta_post"] = _trunc(body_post, 1800)
    if r_post.status_code == 500:
        out["resultado"] = "BLOQUEADO"
        out["residuo"] = "ninguno (POST no creo ID)"
        out["conclusion_mass_assignment"] = (
            "POST HTTP 500 ERROR_INTERNO. No se declara PASS ni vulnerabilidad de mass assignment. "
            "Impide comprobar persistencia de estado=CERRADO / cantidad_actual=9999."
        )
        pytest.skip(out["conclusion_mass_assignment"])
    if r_post.status_code == 422:
        out["resultado"] = "APROBADO"
        out["residuo"] = "ninguno"
        out["conclusion_mass_assignment"] = (
            "POST 422: el contrato rechazo campos no permitidos o validacion asociada. "
            "CERRADO/9999 no se persistieron."
        )
        return
    if r_post.status_code != 201:
        out["resultado"] = "BLOQUEADO"
        out["conclusion_mass_assignment"] = (
            f"POST HTTP {r_post.status_code}. No se completo la evaluacion de persistencia."
        )
        pytest.skip(out["conclusion_mass_assignment"])

    aid = body_post.get("id_activo_biologico") or body_post.get("id")
    out["id_creado"] = aid
    out["residuo"] = f"activo creado id={aid} (POST 201 del caso; no hay restore seguro de DELETE)"
    r_get = requests.get(
        f"{BASE_URL}/activos-biologicos/{aid}",
        headers=_auth(tok),
        timeout=TIMEOUT,
        verify=VERIFY_SSL,
    )
    body_get = _json(r_get)
    out["http_get"] = r_get.status_code
    out["respuesta_get"] = _trunc(body_get, 1800)
    estado = str(body_get.get("nombre_estado") or body_get.get("estado") or "").upper()
    det = body_get.get("detalle_poblacional") or {}
    cant = det.get("cantidad_actual")
    cant_ini = det.get("cantidad_inicial")
    out["estado_persistido"] = estado
    out["cantidad_actual_persistida"] = cant
    out["cantidad_inicial_persistida"] = cant_ini
    if r_get.status_code != 200:
        out["resultado"] = "BLOQUEADO"
        out["conclusion_mass_assignment"] = f"POST 201 pero GET HTTP {r_get.status_code}."
        pytest.skip(out["conclusion_mass_assignment"])
    if estado == "CERRADO" or (cant is not None and int(cant) == 9999):
        out["resultado"] = "RECHAZADO"
        out["conclusion_mass_assignment"] = (
            "Se persistieron valores inyectados (estado CERRADO y/o cantidad_actual 9999)."
        )
        EVIDENCIA["estado_global"] = "RECHAZADO"
        pytest.fail(out["conclusion_mass_assignment"])
    if estado != "ACTIVO":
        out["resultado"] = "RECHAZADO"
        out["conclusion_mass_assignment"] = f"estado persistido={estado}, esperado ACTIVO."
        pytest.fail(out["conclusion_mass_assignment"])
    if cant is not None and int(cant) != 10:
        out["resultado"] = "RECHAZADO"
        out["conclusion_mass_assignment"] = (
            f"cantidad_actual persistida={cant}, esperado 10 (cantidad_inicial)."
        )
        pytest.fail(out["conclusion_mass_assignment"])
    out["resultado"] = "APROBADO"
    out["conclusion_mass_assignment"] = (
        "DTO ignora extras; persistido estado=ACTIVO y cantidad_actual=cantidad_inicial. "
        "Los valores inyectados no quedaron en servidor."
    )


def test_tc_m02_031_exceso_datos(sesion):
    out = {
        "resultado": "BLOQUEADO",
        "rol_utilizado": CORREO_INGENIERO,
        "rol_jwt": None,
        "endpoint_historico": "GET /activos-biologicos/{id}",
        "endpoint_listado": "GET /activos-biologicos",
        "activo_objetivo": ACTIVO_HIST_031,
        "campos_financieros_buscados": list(CAMPOS_FINANCIEROS),
        "campos_en_respuesta": [],
        "expuestos": [],
        "http_get_objetivo": None,
        "conclusion_exceso": "",
        "codigo_respuesta_schema": (
            "ActivoBiologicoResponse incluye costo_adquisicion y soporte_documental "
            "sin filtrar por rol. FichaIntegralResponse no incluye esos campos. "
            "El caso historico consulta GET /activos-biologicos/{id}, no ficha-integral."
        ),
    }
    EVIDENCIA["subcasos"]["TC-M02-031"] = out
    out["login_ingeniero"] = {
        "http": sesion["ingeniero"]["http"],
        "ok": sesion["ingeniero"]["login_ok"],
        "error_code": sesion["ingeniero"]["error_code"],
        "intentos": 1,
    }
    if not sesion["ingeniero"]["login_ok"]:
        out["conclusion_exceso"] = (
            f"BLOQUEADO: login Ingeniero HTTP {sesion['ingeniero']['http']} "
            f"error_code={sesion['ingeniero']['error_code']}. Un solo intento. "
            "No se evaluo exposicion."
        )
        pytest.skip(out["conclusion_exceso"])
    tok_i = sesion["ingeniero"]["token"]
    out["rol_jwt"] = (sesion["ingeniero"]["claims"] or {}).get("rol")

    r_obj = requests.get(
        f"{BASE_URL}/activos-biologicos/{ACTIVO_HIST_031}",
        headers=_auth(tok_i),
        timeout=TIMEOUT,
        verify=VERIFY_SSL,
    )
    body_obj = _json(r_obj)
    out["http_get_objetivo"] = r_obj.status_code
    out["respuesta_objetivo"] = _trunc(body_obj, 2200)
    out["campos_en_respuesta"] = sorted(body_obj.keys()) if isinstance(body_obj, dict) else []
    hits_obj = _hits_con_valor(body_obj) if r_obj.status_code == 200 else []
    out["hits_objetivo"] = hits_obj

    if r_obj.status_code == 500:
        out["conclusion_exceso"] = f"GET /activos-biologicos/{ACTIVO_HIST_031} HTTP 500."
        pytest.skip(out["conclusion_exceso"])

    http_list, regs = _listar_activos(tok_i, page_size=20, max_paginas=2)
    out["listado_http"] = http_list
    out["listado_n"] = len(regs)
    list_hits = _hits_con_valor(regs) if http_list == 200 else []
    out["hits_listado"] = list_hits[:20]

    ids = []
    for x in regs:
        i = x.get("id_activo_biologico") or x.get("id")
        if i is not None:
            ids.append(int(i))
    if ACTIVO_HIST_031 not in ids:
        ids = [ACTIVO_HIST_031] + ids
    ids = ids[:8]
    detalle = []
    hits_total = list(hits_obj) + list(list_hits)
    for aid in ids:
        if aid == ACTIVO_HIST_031 and r_obj.status_code != 200:
            detalle.append({"id": aid, "http": r_obj.status_code, "nota": "respuesta ya capturada"})
            continue
        if aid == ACTIVO_HIST_031:
            detalle.append({"id": aid, "http": r_obj.status_code, "hits_con_valor": hits_obj})
            continue
        r = requests.get(
            f"{BASE_URL}/activos-biologicos/{aid}",
            headers=_auth(tok_i),
            timeout=TIMEOUT,
            verify=VERIFY_SSL,
        )
        body = _json(r)
        hits = _hits_con_valor(body) if r.status_code == 200 else []
        detalle.append({"id": aid, "http": r.status_code, "hits_con_valor": hits})
        if r.status_code == 500:
            out["detalle"] = detalle
            out["conclusion_exceso"] = f"GET /activos-biologicos/{aid} HTTP 500."
            pytest.skip(out["conclusion_exceso"])
        hits_total.extend(hits)

    if sesion["admin"]["login_ok"]:
        ra = requests.get(
            f"{BASE_URL}/activos-biologicos/{ACTIVO_HIST_031}",
            headers=_auth(sesion["admin"]["token"]),
            timeout=TIMEOUT,
            verify=VERIFY_SSL,
        )
        ba = _json(ra)
        out["contraste_admin_350"] = {
            "http": ra.status_code,
            "hits": _walk_keys(ba, CAMPOS_FINANCIEROS) if ra.status_code == 200 else [],
        }

    out["detalle"] = detalle
    out["expuestos"] = hits_total
    if r_obj.status_code == 403:
        out["resultado"] = "APROBADO"
        out["conclusion_exceso"] = (
            "GET historico HTTP 403. El criterio del caso historico acepta 403 "
            "como no exposicion financiera."
        )
        return
    if r_obj.status_code == 401:
        out["resultado"] = "BLOQUEADO"
        out["conclusion_exceso"] = "GET ficha HTTP 401: autenticacion, no evaluacion de exposicion."
        pytest.skip(out["conclusion_exceso"])
    if hits_total:
        out["resultado"] = "RECHAZADO"
        out["conclusion_exceso"] = (
            "El JSON del Ingeniero incluye costo_adquisicion y/o soporte_documental "
            "con valor. Excessive data exposure confirmada en TEST."
        )
        EVIDENCIA["estado_global"] = "RECHAZADO"
        pytest.fail(out["conclusion_exceso"])
    if r_obj.status_code not in (200, 403, 404):
        out["resultado"] = "RECHAZADO"
        out["conclusion_exceso"] = (
            f"GET historico HTTP {r_obj.status_code} no esperado (200 con campos ocultos, 403 o 404)."
        )
        pytest.fail(out["conclusion_exceso"])
    if r_obj.status_code == 404 and not regs:
        out["resultado"] = "BLOQUEADO"
        out["conclusion_exceso"] = (
            f"GET /activos-biologicos/{ACTIVO_HIST_031} HTTP 404 y listado vacio. "
            "No hay ficha visible para auditar exposicion."
        )
        pytest.skip(out["conclusion_exceso"])
    out["resultado"] = "APROBADO"
    out["conclusion_exceso"] = (
        "En GET por id (endpoint historico) y listado del Ingeniero no aparecen valores "
        "de costo_adquisicion / soporte_documental / soporte_documental_costo."
    )


def test_zz_estado_global(sesion):
    subs = EVIDENCIA.get("subcasos") or {}
    estados = [v.get("resultado") for v in subs.values()]
    if "RECHAZADO" in estados:
        EVIDENCIA["estado_global"] = "RECHAZADO"
    elif estados and all(e == "APROBADO" for e in estados):
        EVIDENCIA["estado_global"] = "APROBADO"
    elif estados and all(e == "BLOQUEADO" for e in estados):
        EVIDENCIA["estado_global"] = "BLOQUEADO"
    elif "APROBADO" in estados and "BLOQUEADO" in estados and "RECHAZADO" not in estados:
        EVIDENCIA["estado_global"] = "BLOQUEADO"
    else:
        EVIDENCIA["estado_global"] = EVIDENCIA.get("estado_global") or "BLOQUEADO"
    assert EVIDENCIA["estado_global"] in ("APROBADO", "RECHAZADO", "BLOQUEADO")
