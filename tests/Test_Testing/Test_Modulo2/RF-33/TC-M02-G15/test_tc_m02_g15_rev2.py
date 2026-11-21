"""TC-M02-G15 rev2 — RF-33 / RF-34. Segunda evaluacion.

TC-M02-027 BOLA, TC-M02-028 mass assignment, TC-M02-031 excessive data exposure.
Caja negra contra TEST. No modifica historico ni codigo productivo.
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
ENV_PATH = DIR / "environment-g15-rev2.json"

with ENV_PATH.open(encoding="utf-8") as fh:
    ENV = json.load(fh)

BASE_URL = ENV["baseUrl"].rstrip("/")
CORREO_ADMIN = ENV["correo_admin"]
CORREO_PRODUCTOR = ENV["correo_productor"]
CORREO_PRODUCTOR_HIST = ENV.get("correo_productor_historico_g15") or "m2m.nuevo@ejemplo.com"
CORREO_INGENIERO = ENV["correo_ingeniero"]
TIMEOUT = 45
VERIFY_SSL = False
CAMPOS_FINANCIEROS = ("costo_adquisicion", "soporte_documental", "soporte_documental_costo")

EVIDENCIA: dict = {
    "caso": "TC-M02-G15",
    "revision": 2,
    "rf": ["RF-33", "RF-34"],
    "cu": "CU01",
    "ambiente": "TEST",
    "base_url": BASE_URL,
    "fecha_utc": datetime.now(timezone.utc).isoformat(),
    "openapi": {},
    "subcasos": {},
    "estado_global": "PENDIENTE",
    "comparacion_primera_evaluacion": (
        "Primera evaluacion (Newman HTML 2026-09-12): 027 GET ajeno 404 sin "
        "cuerpo de activo (asercion 403/404 PASS) y PATCH ajeno HTTP 200 sobre "
        "activo 348 (FAIL BOLA escritura). 028 POST 201 estado ACTIVO "
        "cantidad_actual=10 (PASS). 031 GET ingeniero 200 con costo_adquisicion "
        "y soporte_documental (FAIL exposicion). Correo productor historico "
        "m2m.nuevo@ejemplo.com. Esta rev2 no reutiliza ese password hardcodeado."
    ),
    "auditoria": (
        "Historico no modificado. Codigo productivo no modificado. Sin commit ni push."
    ),
}


def _password() -> str:
    valor = os.environ.get("SGPMP_TEST_PASSWORD") or os.environ.get("CONTRASENA") or ""
    if not valor:
        pytest.skip(
            "BLOQUEADO: definir SGPMP_TEST_PASSWORD o CONTRASENA. "
            "No se hardcodea password."
        )
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


def _login(correo: str, password: str | None = None) -> tuple[int, dict | None, str | None]:
    r = requests.post(
        f"{BASE_URL}/sesiones/",
        json={"correo_electronico": correo, "contrasena": password or _password()},
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


def _escribir_evidencia() -> None:
    RESULTADOS.mkdir(parents=True, exist_ok=True)
    payload = _redact(EVIDENCIA)
    json_path = RESULTADOS / "TC-M02-G15-rev2.json"
    txt_path = RESULTADOS / "TC-M02-G15-rev2.txt"
    html_path = RESULTADOS / "TC-M02-G15-rev2-evidencia.html"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    lineas = [
        "TC-M02-G15 rev2 — RF-33 / RF-34 — TEST",
        f"Fecha UTC: {payload.get('fecha_utc')}",
        f"Estado global: {payload.get('estado_global')}",
        "",
        json.dumps(payload.get("subcasos"), ensure_ascii=False, indent=2, default=str),
        "",
        payload.get("comparacion_primera_evaluacion"),
        payload.get("auditoria"),
        "Password/JWT: [REDACTED]. Historico Newman no modificado.",
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
        "<title>TC-M02-G15 rev2</title></head><body>"
        "<h1>TC-M02-G15 segunda evaluacion</h1>"
        f"<p>Estado global: {payload.get('estado_global')}</p>"
        + "".join(bloques)
        + "<p>Sin passwords ni JWT. Historico no modificado.</p>"
        "</body></html>",
        encoding="utf-8",
    )


def _mapear_infra_fincas(token_admin: str, extra_infra_ids: list[int] | None = None) -> dict[int, int]:
    mapping: dict[int, int] = {}
    for finca_id in range(1, 8):
        r = requests.get(
            f"{BASE_URL}/configuracion/infraestructuras",
            params={"finca_id": finca_id, "solo_activas": False},
            headers=_auth(token_admin),
            timeout=TIMEOUT,
            verify=VERIFY_SSL,
        )
        if r.status_code != 200:
            continue
        for item in _registros(_json(r)):
            iid = item.get("id_infraestructura") or item.get("id")
            fid = item.get("id_finca")
            if iid is not None and fid is not None:
                mapping[int(iid)] = int(fid)
    for raw in extra_infra_ids or []:
        iid = int(raw)
        if iid in mapping:
            continue
        r = requests.get(
            f"{BASE_URL}/configuracion/infraestructuras/{iid}",
            headers=_auth(token_admin),
            timeout=TIMEOUT,
            verify=VERIFY_SSL,
        )
        body = _json(r)
        if r.status_code == 200 and isinstance(body, dict) and body.get("id_finca") is not None:
            mapping[iid] = int(body["id_finca"])
    return mapping


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


def _sensible_en_error(body) -> bool:
    if not isinstance(body, dict):
        return False
    claves = ("id_infraestructura", "costo_adquisicion", "soporte_documental", "identificador", "detalle_individual")
    return any(k in body and body.get(k) not in (None, "", []) for k in claves)


@pytest.fixture(scope="session")
def sesion():
    _password()
    r = requests.get(f"{BASE_URL}/openapi.json", timeout=TIMEOUT, verify=VERIFY_SSL)
    paths = {}
    if r.status_code == 200:
        spec = r.json()
        for p, ops in (spec.get("paths") or {}).items():
            if "activo" in p.lower():
                paths[p] = sorted(ops.keys())
    EVIDENCIA["openapi"] = {
        "http": r.status_code,
        "activos_paths": paths,
        "put_activos_id": any(
            p.endswith("/{id_activo}") and "put" in [x.lower() for x in ops]
            for p, ops in paths.items()
        ),
        "patch_activos_id": any(
            p.endswith("/{id_activo}") and "patch" in [x.lower() for x in ops]
            for p, ops in paths.items()
        ),
    }
    http_a, body_a, tok_a = _login(CORREO_ADMIN)
    http_p, body_p, tok_p = _login(CORREO_PRODUCTOR)
    http_i, body_i, tok_i = _login(CORREO_INGENIERO, _password_ingeniero())
    data = {
        "admin": {"http": http_a, "token": tok_a, "claims": _jwt_claims(tok_a) if tok_a else None, "login_ok": bool(tok_a)},
        "productor": {"http": http_p, "token": tok_p, "claims": _jwt_claims(tok_p) if tok_p else None, "login_ok": bool(tok_p)},
        "ingeniero": {"http": http_i, "token": tok_i, "claims": _jwt_claims(tok_i) if tok_i else None, "login_ok": bool(tok_i)},
        "login_bodies": {
            "admin": {"http": http_a, "claves": list((body_a or {}).keys())},
            "productor": {"http": http_p, "claves": list((body_p or {}).keys())},
            "ingeniero": {"http": http_i, "claves": list((body_i or {}).keys())},
        },
    }
    yield data
    _escribir_evidencia()


def test_tc_m02_027_bola(sesion):
    out = {
        "resultado": "BLOQUEADO",
        "usuario": CORREO_PRODUCTOR,
        "rol_jwt": None,
        "finca_usuario": "NO DETERMINABLE CON LA EVIDENCIA HISTORICA DISPONIBLE",
        "finca_activo_objetivo": None,
        "id_activo": None,
        "endpoint_get": "GET /activos-biologicos/{id}",
        "endpoint_patch": "PATCH /activos-biologicos/{id}",
        "put_existe": EVIDENCIA["openapi"].get("put_activos_id"),
        "http_get": None,
        "http_patch": None,
        "respuesta_get": None,
        "respuesta_patch": None,
        "exposicion_datos": False,
        "modificacion": False,
        "conclusion_bola": "",
    }
    EVIDENCIA["subcasos"]["TC-M02-027"] = out
    if not sesion["admin"]["login_ok"]:
        out["conclusion_bola"] = f"BLOQUEADO: login Admin HTTP {sesion['admin']['http']}."
        pytest.skip(out["conclusion_bola"])
    if not sesion["productor"]["login_ok"]:
        out["aviso_productor_pecuaria"] = (
            f"productor@pecuaria.co login HTTP {sesion['productor']['http']}; "
            "se intenta el productor historico G15."
        )

    tok_p = sesion["productor"]["token"]
    tok_a = sesion["admin"]["token"]
    out["rol_jwt"] = (sesion["productor"]["claims"] or {}).get("rol")

    http_h, _, tok_h = _login(CORREO_PRODUCTOR_HIST)
    out["login_productor_historico"] = {"correo": CORREO_PRODUCTOR_HIST, "http": http_h, "ok": bool(tok_h)}
    if tok_h:
        tok_p = tok_h
        out["usuario"] = CORREO_PRODUCTOR_HIST
        out["rol_jwt"] = _jwt_claims(tok_h).get("rol")
    if not tok_p:
        out["conclusion_bola"] = "BLOQUEADO: no hay token de Productor para evaluar BOLA."
        pytest.skip(out["conclusion_bola"])

    http_list_p, propios = _listar_activos(tok_p)
    http_list_a, admin_regs = _listar_activos(tok_a)
    out["listado_productor_http"] = http_list_p
    out["listado_admin_http"] = http_list_a
    out["cantidad_propios"] = len(propios)
    out["cantidad_admin_muestra"] = len(admin_regs)
    if http_list_p != 200:
        out["conclusion_bola"] = (
            f"BLOQUEADO: Productor GET /activos-biologicos HTTP {http_list_p}."
        )
        pytest.skip(out["conclusion_bola"])
    if http_list_a != 200:
        out["conclusion_bola"] = f"BLOQUEADO: Admin GET /activos-biologicos HTTP {http_list_a}."
        pytest.skip(out["conclusion_bola"])

    extra_ids = []
    for regs in (propios, admin_regs):
        for x in regs:
            iid = x.get("id_infraestructura")
            if iid is not None:
                extra_ids.append(int(iid))
    mapping = _mapear_infra_fincas(tok_a, extra_ids)
    out["infra_fincas_mapeadas"] = len(mapping)

    alcance_infra = {}
    for finca_id in range(1, 8):
        r_inf = requests.get(
            f"{BASE_URL}/configuracion/infraestructuras",
            params={"finca_id": finca_id, "solo_activas": False},
            headers=_auth(tok_p),
            timeout=TIMEOUT,
            verify=VERIFY_SSL,
        )
        items = _registros(_json(r_inf)) if r_inf.status_code == 200 else []
        alcance_infra[str(finca_id)] = {"http": r_inf.status_code, "n": len(items)}
    out["alcance_infra_productor"] = alcance_infra
    out["nota_alcance_infra"] = (
        "HTTP 200 al listar infra de varias fincas NO se usa como fincas del usuario "
        "para BOLA de activos; la finca se deriva de id_infraestructura de sus activos."
    )

    def _fincas_de(regs):
        s = set()
        for x in regs:
            iid = x.get("id_infraestructura")
            if iid is not None and int(iid) in mapping:
                s.add(mapping[int(iid)])
        return s

    def _ids_de(regs):
        return {
            int(x.get("id_activo_biologico") or x.get("id"))
            for x in regs
            if (x.get("id_activo_biologico") or x.get("id")) is not None
        }

    def _buscar_candidato(ids_propios, fincas_usuario):
        found = None
        for item in admin_regs:
            aid = item.get("id_activo_biologico") or item.get("id")
            if aid is None:
                continue
            aid = int(aid)
            if aid in ids_propios:
                continue
            iid = item.get("id_infraestructura")
            fid = mapping.get(int(iid)) if iid is not None else None
            if fid is None or fid in fincas_usuario:
                continue
            cand = {
                "id": aid,
                "tipo": item.get("tipo"),
                "id_infraestructura": iid,
                "id_finca": fid,
                "prueba_finca": True,
            }
            if str(item.get("tipo") or "").upper() == "INDIVIDUAL":
                return cand
            if found is None:
                found = cand
        return found

    ids_propios = _ids_de(propios)
    fincas_productor = _fincas_de(propios)
    out["fincas_presentes_en_activos_admin"] = sorted(_fincas_de(admin_regs))
    out["infras_sin_finca"] = sorted(
        {
            int(x.get("id_infraestructura"))
            for x in (propios + admin_regs)
            if x.get("id_infraestructura") is not None
            and int(x.get("id_infraestructura")) not in mapping
        }
    )
    if fincas_productor:
        out["finca_usuario"] = sorted(fincas_productor)
    else:
        out["finca_usuario"] = (
            "NO DETERMINABLE CON LA EVIDENCIA DISPONIBLE EN TEST "
            "(activos propios sin id_infraestructura mapeable)"
        )

    candidato = None
    if isinstance(out["finca_usuario"], list):
        candidato = _buscar_candidato(ids_propios, set(out["finca_usuario"]))

    if candidato is None or not candidato.get("prueba_finca"):
        out["precondicion"] = (
            "No se encontro un activo de Admin demostrablemente de otra finca "
            "respecto del usuario evaluado. No se usa ID 500 por matriz."
        )
        out["conclusion_bola"] = (
            "BLOQUEADO: no hay combinacion Usuario A / finca propia / activo de otra finca verificable."
        )
        pytest.skip(out["conclusion_bola"])

    out["id_activo"] = candidato["id"]
    out["tipo_activo"] = candidato["tipo"]
    out["id_infraestructura_objetivo"] = candidato["id_infraestructura"]
    out["finca_activo_objetivo"] = candidato["id_finca"]

    r_get = requests.get(
        f"{BASE_URL}/activos-biologicos/{candidato['id']}",
        headers=_auth(tok_p),
        timeout=TIMEOUT,
        verify=VERIFY_SSL,
    )
    body_get = _json(r_get)
    out["http_get"] = r_get.status_code
    out["respuesta_get"] = _trunc(body_get, 1800)
    if r_get.status_code == 200:
        out["exposicion_datos"] = True
        out["resultado"] = "RECHAZADO"
        out["conclusion_bola"] = (
            "GET devolvio 200 con cuerpo de activo de otra finca. BOLA de lectura confirmada. "
            "No se ejecuto PATCH para no modificar datos ajenos adicionales."
        )
        EVIDENCIA["estado_global"] = "RECHAZADO"
        pytest.fail(out["conclusion_bola"])
    if r_get.status_code == 500:
        out["resultado"] = "BLOQUEADO"
        out["conclusion_bola"] = "GET HTTP 500. No se declara BOLA PASS ni vulnerabilidad por el 500."
        pytest.skip(out["conclusion_bola"])
    if r_get.status_code == 401:
        out["resultado"] = "BLOQUEADO"
        out["conclusion_bola"] = "GET HTTP 401: problema de autenticacion, no de autorizacion BOLA."
        pytest.skip(out["conclusion_bola"])
    if r_get.status_code not in (403, 404):
        out["resultado"] = "RECHAZADO"
        out["conclusion_bola"] = f"GET HTTP {r_get.status_code} no esperado para denegacion de acceso."
        pytest.fail(out["conclusion_bola"])
    if _sensible_en_error(body_get):
        out["exposicion_datos"] = True
        out["resultado"] = "RECHAZADO"
        out["conclusion_bola"] = f"GET HTTP {r_get.status_code} pero el cuerpo expone datos del activo."
        pytest.fail(out["conclusion_bola"])

    if not EVIDENCIA["openapi"].get("patch_activos_id"):
        out["resultado"] = "APROBADO"
        out["conclusion_bola"] = (
            f"GET {r_get.status_code} sin datos del activo. OpenAPI no documenta PATCH; "
            "escritura no evaluada."
        )
        return

    tipo = str(candidato.get("tipo") or "").upper()
    if tipo != "INDIVIDUAL":
        out["http_patch"] = "NO EJECUTADO"
        out["resultado"] = "APROBADO"
        out["conclusion_bola"] = (
            f"GET {r_get.status_code} sin exposicion. El activo de otra finca es {tipo}; "
            "PATCH RF-35 solo aplica a INDIVIDUAL. Escritura BOLA no aplicable sobre este recurso."
        )
        return

    r_admin = requests.get(
        f"{BASE_URL}/activos-biologicos/{candidato['id']}",
        headers=_auth(tok_a),
        timeout=TIMEOUT,
        verify=VERIFY_SSL,
    )
    admin_body = _json(r_admin)
    raza_orig = None
    if r_admin.status_code == 200 and isinstance(admin_body, dict):
        det = admin_body.get("detalle_individual") or {}
        raza_orig = det.get("raza")

    r_patch = requests.patch(
        f"{BASE_URL}/activos-biologicos/{candidato['id']}",
        headers={**_auth(tok_p), "Content-Type": "application/json"},
        json={"raza": "QA-G15-R2-BOLA-MARKER"},
        timeout=TIMEOUT,
        verify=VERIFY_SSL,
    )
    body_patch = _json(r_patch)
    out["http_patch"] = r_patch.status_code
    out["respuesta_patch"] = _trunc(body_patch, 1800)
    if r_patch.status_code == 200:
        out["modificacion"] = True
        if raza_orig is not None:
            requests.patch(
                f"{BASE_URL}/activos-biologicos/{candidato['id']}",
                headers={**_auth(tok_a), "Content-Type": "application/json"},
                json={"raza": raza_orig},
                timeout=TIMEOUT,
                verify=VERIFY_SSL,
            )
            out["restauracion_raza"] = "intentada_via_admin"
        out["resultado"] = "RECHAZADO"
        out["conclusion_bola"] = (
            "PATCH HTTP 200 sobre activo de otra finca. BOLA de escritura. "
            "GET habia denegado o ocultado el recurso."
        )
        EVIDENCIA["estado_global"] = "RECHAZADO"
        pytest.fail(out["conclusion_bola"])
    if r_patch.status_code == 500:
        out["resultado"] = "BLOQUEADO"
        out["conclusion_bola"] = (
            f"GET {r_get.status_code} sin datos. PATCH HTTP 500. Escritura no evaluable. "
            "No se declara BOLA PASS."
        )
        pytest.skip(out["conclusion_bola"])
    if r_patch.status_code == 403 or r_patch.status_code == 404:
        out["resultado"] = "APROBADO"
        out["conclusion_bola"] = (
            f"GET {r_get.status_code} sin datos sensibles y PATCH {r_patch.status_code} "
            "sin modificacion. Control de acceso demostrado para este par usuario/activo."
        )
        return
    if r_patch.status_code in (400, 422):
        out["resultado"] = "APROBADO"
        out["conclusion_bola"] = (
            f"GET {r_get.status_code} sin exposicion. PATCH {r_patch.status_code} no persistio "
            "cambio (validacion/tipo), no 200. No hay BOLA de escritura demostrada."
        )
        return
    out["resultado"] = "RECHAZADO"
    out["conclusion_bola"] = f"PATCH HTTP {r_patch.status_code} no clasificable como denegacion."
    pytest.fail(out["conclusion_bola"])


def test_tc_m02_028_mass_assignment(sesion):
    out = {
        "resultado": "BLOQUEADO",
        "payload_campos_protegidos": {"estado": "CERRADO", "cantidad_actual": 9999},
        "http_post": None,
        "id_creado": None,
        "estado_persistido": None,
        "cantidad_actual_persistida": None,
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
        (e for e in especies if e.get("id_especie") == 4 or str(e.get("nombre") or "").lower().find("cachama") >= 0),
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
            f"BLOQUEADO: precondicion de especie/infra. especies_http={r_esp.status_code} "
            f"infra_http={r_inf.status_code}."
        )
        pytest.skip(out["conclusion_mass_assignment"])
    especie_id = int(especie.get("id_especie") or especie.get("id"))
    infra_id = int(infra.get("id_infraestructura") or infra.get("id"))
    payload = {
        "tipo_activo": "POBLACIONAL",
        "id_especie": especie_id,
        "fecha_inicio_ciclo": "2026-09-09",
        "origen_financiero": "nacimiento",
        "id_infraestructura": infra_id,
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
        out["conclusion_mass_assignment"] = (
            "POST HTTP 500 ERROR_INTERNO. No se declara PASS ni vulnerabilidad de mass assignment. "
            "Impide comprobar persistencia de campos protegidos."
        )
        pytest.skip(out["conclusion_mass_assignment"])
    if r_post.status_code == 422:
        out["resultado"] = "APROBADO"
        out["conclusion_mass_assignment"] = (
            "POST 422: el contrato rechazo campos no permitidos o validacion asociada. "
            "Los valores CERRADO/9999 no se persistieron."
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
    r_get = requests.get(
        f"{BASE_URL}/activos-biologicos/{aid}",
        headers=_auth(tok),
        timeout=TIMEOUT,
        verify=VERIFY_SSL,
    )
    body_get = _json(r_get)
    out["http_get"] = r_get.status_code
    out["respuesta_get"] = _trunc(body_get, 1800)
    estado = str(
        body_get.get("nombre_estado") or body_get.get("estado") or ""
    ).upper()
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
        "permisos_relevantes": (
            "No hay endpoint publico de matriz RBAC financiera en esta prueba. "
            "Se usa el usuario de TEST ingeniero@pecuaria.co. No se asume la matriz historica."
        ),
        "endpoint": "GET /activos-biologicos/{id} y GET /activos-biologicos (listado)",
        "campos_financieros_buscados": list(CAMPOS_FINANCIEROS),
        "expuestos": [],
        "conclusion_exceso": "",
    }
    EVIDENCIA["subcasos"]["TC-M02-031"] = out
    if not sesion["ingeniero"]["login_ok"]:
        out["conclusion_exceso"] = (
            f"BLOQUEADO: login Ingeniero HTTP {sesion['ingeniero']['http']}. "
            "No se evaluo exposicion."
        )
        pytest.skip(out["conclusion_exceso"])
    tok_i = sesion["ingeniero"]["token"]
    out["rol_jwt"] = (sesion["ingeniero"]["claims"] or {}).get("rol")
    http_list, regs = _listar_activos(tok_i, page_size=20, max_paginas=2)
    out["listado_http"] = http_list
    if http_list == 500:
        out["conclusion_exceso"] = "GET listado HTTP 500. No se declara PASS."
        pytest.skip(out["conclusion_exceso"])
    if http_list != 200:
        out["conclusion_exceso"] = f"BLOQUEADO: Ingeniero GET listado HTTP {http_list}."
        pytest.skip(out["conclusion_exceso"])
    if not regs:
        out["conclusion_exceso"] = (
            "BLOQUEADO: Ingeniero no tiene activos visibles; no hay JSON de ficha que auditar."
        )
        pytest.skip(out["conclusion_exceso"])

    ids = []
    for x in regs:
        i = x.get("id_activo_biologico") or x.get("id")
        if i is not None:
            ids.append(int(i))
    ids = ids[:8]
    hits_total = []
    detalle = []
    for aid in ids:
        r = requests.get(
            f"{BASE_URL}/activos-biologicos/{aid}",
            headers=_auth(tok_i),
            timeout=TIMEOUT,
            verify=VERIFY_SSL,
        )
        body = _json(r)
        hits = _walk_keys(body, CAMPOS_FINANCIEROS) if r.status_code == 200 else []
        hits_val = [h for h in hits if h.get("valor") not in (None, "", [])]
        detalle.append({"id": aid, "http": r.status_code, "hits_con_valor": hits_val, "hits": hits})
        if r.status_code == 500:
            out["resultado"] = "BLOQUEADO"
            out["detalle"] = detalle
            out["conclusion_exceso"] = f"GET /activos-biologicos/{aid} HTTP 500."
            pytest.skip(out["conclusion_exceso"])
        hits_total.extend(hits_val)
        r_f = requests.get(
            f"{BASE_URL}/activos-biologicos/{aid}/ficha-integral",
            headers=_auth(tok_i),
            timeout=TIMEOUT,
            verify=VERIFY_SSL,
        )
        if r_f.status_code == 200:
            hits_f = [h for h in _walk_keys(_json(r_f), CAMPOS_FINANCIEROS) if h.get("valor") not in (None, "", [])]
            if hits_f:
                hits_total.extend(hits_f)
                detalle[-1]["ficha_integral"] = hits_f

    list_hits = [h for h in _walk_keys(regs, CAMPOS_FINANCIEROS) if h.get("valor") not in (None, "", [])]
    hits_total.extend(list_hits)
    out["detalle"] = detalle
    out["expuestos"] = hits_total
    admin_confirm = []
    if sesion["admin"]["login_ok"] and hits_total:
        for aid in ids[:5]:
            ra = requests.get(
                f"{BASE_URL}/activos-biologicos/{aid}",
                headers=_auth(sesion["admin"]["token"]),
                timeout=TIMEOUT,
                verify=VERIFY_SSL,
            )
            if ra.status_code == 200:
                admin_confirm.append(
                    {"id": aid, "admin_hits": _walk_keys(_json(ra), CAMPOS_FINANCIEROS)}
                )
    out["contraste_admin"] = admin_confirm
    if hits_total:
        out["resultado"] = "RECHAZADO"
        out["conclusion_exceso"] = (
            "El JSON del Ingeniero incluye costo_adquisicion y/o soporte_documental "
            "con valor. Excessive data exposure."
        )
        EVIDENCIA["estado_global"] = "RECHAZADO"
        pytest.fail(out["conclusion_exceso"])
    out["resultado"] = "APROBADO"
    out["conclusion_exceso"] = (
        "En listado, GET por id y ficha-integral del Ingeniero no aparecen valores "
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
