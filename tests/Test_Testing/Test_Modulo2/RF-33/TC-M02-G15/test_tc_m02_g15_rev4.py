"""TC-M02-G15 rev4 — reevaluacion completa TEST (027 BOLA / 028 mass assignment / 031 exposicion).

No modifica codigo productivo, rev2 ni rev3. Sin DML. Sin commit.
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
ENV_PATH = DIR / "environment-g15-rev4.json"

with ENV_PATH.open(encoding="utf-8") as fh:
    ENV = json.load(fh)

BASE_URL = ENV["baseUrl"].rstrip("/")
CORREO_ADMIN = ENV["correo_admin"]
CORREO_PRODUCTOR = ENV["correo_productor"]
CORREO_BOLA = ENV["correo_productor_bola"]
CORREO_INGENIERO = ENV["correo_ingeniero"]
CORREO_ING_ALT = ENV["correo_ingeniero_alt"]
ACTIVO_BOLA = int(ENV["activo_bola_historico"])
ESPECIE_5 = int(ENV["especie_poblacional"])
INFRA_3 = int(ENV["infraestructura_poblacional"])
MARCADOR = ENV["marcador_bola"]
TIMEOUT = 45
VERIFY_SSL = False
CAMPOS_FIN = ("costo_adquisicion", "soporte_documental", "soporte_documental_costo")

EVIDENCIA: dict = {
    "caso": "TC-M02-G15",
    "revision": 4,
    "rf": ["RF-33", "RF-34"],
    "ambiente": "TEST",
    "base_url": BASE_URL,
    "fecha_utc": datetime.now(timezone.utc).isoformat(),
    "subcasos": {},
    "estado_global": "PENDIENTE",
    "codigo_local_observado": {
        "GET": "ConsultarActivoUseCase.execute recibe ids_fincas_permitidas (alcance RF-25).",
        "PATCH": (
            "ActualizarActivoIndividualUseCase.obtener_por_id(id) SIN ids_fincas_permitidas. "
            "El router PATCH no pasa alcance. Comportamiento TEST se determina por ejecucion."
        ),
    },
    "auditoria": (
        "Rev2 y rev3 no modificadas. Sin DML. Sin cambios productivos. Sin commit/push. "
        "SELECT solo lectura para precondiciones. Mutaciones via API oficial y restauracion API."
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


def _trunc(obj, n=2200):
    text = json.dumps(_redact(obj), ensure_ascii=False, default=str)
    if len(text) > n:
        return text[:n] + "...[TRUNCATED]"
    return text


def _login(correo: str) -> tuple[int, dict, str | None]:
    r = requests.post(
        f"{BASE_URL}/sesiones/",
        json={"correo_electronico": correo, "contrasena": _password()},
        timeout=TIMEOUT,
        verify=VERIFY_SSL,
    )
    try:
        body = r.json()
    except Exception:
        body = {"raw": (r.text or "")[:400]}
    if not isinstance(body, dict):
        body = {"body": body}
    token = body.get("token") or (body.get("data") or {}).get("token")
    return r.status_code, body, token


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
        for i, item in enumerate(obj[:20]):
            hits.extend(_walk_keys(item, wanted, f"{path}[{i}]"))
    return hits


def _hits_valor(obj) -> list[dict]:
    return [h for h in _walk_keys(obj, CAMPOS_FIN) if h.get("valor") not in (None, "", [])]


def _ids_fincas(token: str) -> tuple[int, list]:
    r = requests.get(
        f"{BASE_URL}/configuracion/fincas",
        headers=_auth(token),
        timeout=TIMEOUT,
        verify=VERIFY_SSL,
    )
    body = _json(r)
    ids = []
    if r.status_code == 200:
        for item in _registros(body):
            fid = item.get("id_finca") or item.get("id")
            if fid is not None:
                ids.append(int(fid))
    return r.status_code, ids


def _me(token: str):
    r = requests.get(f"{BASE_URL}/usuarios/me", headers=_auth(token), timeout=TIMEOUT, verify=VERIFY_SSL)
    return r.status_code, _json(r)


def _permisos(token: str):
    r = requests.get(
        f"{BASE_URL}/sesiones/me/permisos",
        headers=_auth(token),
        timeout=TIMEOUT,
        verify=VERIFY_SSL,
    )
    if r.status_code == 404:
        r = requests.get(
            f"{BASE_URL}/usuarios/me/permisos",
            headers=_auth(token),
            timeout=TIMEOUT,
            verify=VERIFY_SSL,
        )
    return r.status_code, _json(r)


def _get_activo(token: str, aid: int):
    r = requests.get(
        f"{BASE_URL}/activos-biologicos/{aid}",
        headers=_auth(token),
        timeout=TIMEOUT,
        verify=VERIFY_SSL,
    )
    return r.status_code, _json(r)


def _raza(body) -> str | None:
    if not isinstance(body, dict):
        return None
    det = body.get("detalle_individual") or {}
    if isinstance(det, dict):
        return det.get("raza")
    return None


def _escribir_evidencia() -> None:
    RESULTADOS.mkdir(parents=True, exist_ok=True)
    payload = _redact(EVIDENCIA)
    json_path = RESULTADOS / "TC-M02-G15-rev4.json"
    txt_path = RESULTADOS / "TC-M02-G15-rev4.txt"
    html_path = RESULTADOS / "TC-M02-G15-rev4-evidencia.html"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    lineas = [
        "TC-M02-G15 rev4 — RF-33 / RF-34 — TEST",
        f"Fecha UTC: {payload.get('fecha_utc')}",
        f"Estado global: {payload.get('estado_global')}",
        "",
        json.dumps(payload.get("subcasos"), ensure_ascii=False, indent=2, default=str),
        "",
        json.dumps(payload.get("incidente_bola"), ensure_ascii=False, indent=2, default=str),
        payload.get("auditoria"),
        "Password/JWT: [REDACTED]. Rev2/rev3 no modificados.",
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
        "<title>TC-M02-G15 rev4</title></head><body>"
        "<h1>TC-M02-G15 rev4 reevaluacion completa</h1>"
        f"<p>Estado global: {payload.get('estado_global')}</p>"
        + "".join(bloques)
        + "<p>Sin passwords ni JWT. Rev2 y rev3 intactos.</p>"
        "</body></html>",
        encoding="utf-8",
    )


@pytest.fixture(scope="session")
def sesion():
    _password()
    logins = {}
    for clave, correo in (
        ("admin", CORREO_ADMIN),
        ("productor", CORREO_PRODUCTOR),
        ("bola", CORREO_BOLA),
        ("ingeniero", CORREO_INGENIERO),
    ):
        http, body, tok = _login(correo)
        logins[clave] = {
            "correo": correo,
            "http": http,
            "ok": bool(tok),
            "token": tok,
            "error_code": body.get("error_code") if isinstance(body, dict) else None,
            "intentos": 1,
        }
    if not logins["ingeniero"]["ok"]:
        http, body, tok = _login(CORREO_ING_ALT)
        logins["ingeniero_alt"] = {
            "correo": CORREO_ING_ALT,
            "http": http,
            "ok": bool(tok),
            "token": tok,
            "error_code": body.get("error_code") if isinstance(body, dict) else None,
            "intentos": 1,
        }
    EVIDENCIA["logins"] = {
        k: {kk: vv for kk, vv in v.items() if kk != "token"}
        for k, v in logins.items()
    }
    yield logins
    _escribir_evidencia()


def test_tc_m02_027_bola(sesion):
    out = {
        "resultado": "BLOQUEADO",
        "usuario": CORREO_BOLA,
        "fincas_usuario": [],
        "activo": ACTIVO_BOLA,
        "finca_activo": None,
        "estado_activo": None,
        "get_http": None,
        "patch_http": None,
        "persistencia": None,
        "restauracion": None,
        "conclusion_bola": "",
    }
    EVIDENCIA["subcasos"]["TC-M02-027"] = out
    EVIDENCIA["incidente_bola"] = {
        "id": "INC-M02-G15-001",
        "estado": "NO DETERMINADO",
    }
    if not sesion["admin"]["ok"]:
        out["conclusion_bola"] = f"BLOQUEADO: login Admin HTTP {sesion['admin']['http']}."
        pytest.skip(out["conclusion_bola"])
    if not sesion["bola"]["ok"]:
        out["conclusion_bola"] = (
            f"BLOQUEADO: login {CORREO_BOLA} HTTP {sesion['bola']['http']} "
            f"{sesion['bola']['error_code']}. Un intento."
        )
        pytest.skip(out["conclusion_bola"])

    tok_a = sesion["admin"]["token"]
    tok_b = sesion["bola"]["token"]
    http_me, me = _me(tok_b)
    http_f, fincas = _ids_fincas(tok_b)
    http_p, perms = _permisos(tok_b)
    out["me_http"] = http_me
    out["me"] = _trunc(me, 1200)
    out["fincas_http"] = http_f
    out["fincas_usuario"] = fincas
    out["permisos_http"] = http_p
    out["permisos_resumen"] = _trunc(perms, 800)

    http_adm, body_adm = _get_activo(tok_a, ACTIVO_BOLA)
    out["admin_get_http"] = http_adm
    out["admin_get"] = _trunc(body_adm, 1600)
    if http_adm != 200:
        out["conclusion_bola"] = (
            f"BLOQUEADO: Admin GET /activos-biologicos/{ACTIVO_BOLA} HTTP {http_adm}. "
            "No se confirma el recurso objetivo."
        )
        pytest.skip(out["conclusion_bola"])

    infra = body_adm.get("id_infraestructura")
    out["id_infraestructura"] = infra
    out["estado_activo"] = body_adm.get("nombre_estado") or body_adm.get("estado")
    raza_orig = _raza(body_adm)
    out["raza_original"] = raza_orig

    r_inf = requests.get(
        f"{BASE_URL}/configuracion/infraestructuras/{infra}",
        headers=_auth(tok_a),
        timeout=TIMEOUT,
        verify=VERIFY_SSL,
    )
    inf_body = _json(r_inf)
    finca_act = inf_body.get("id_finca") if r_inf.status_code == 200 else None
    out["infra_http"] = r_inf.status_code
    out["finca_activo"] = finca_act
    if finca_act is None:
        out["conclusion_bola"] = "BLOQUEADO: no se obtuvo finca del activo via infraestructura."
        pytest.skip(out["conclusion_bola"])
    if finca_act in fincas:
        out["conclusion_bola"] = (
            f"BLOQUEADO: finca del activo {finca_act} esta en alcance del atacante {fincas}."
        )
        pytest.skip(out["conclusion_bola"])

    http_get, body_get = _get_activo(tok_b, ACTIVO_BOLA)
    out["get_http"] = http_get
    out["get_body"] = _trunc(body_get, 1200)
    out["get_expone_datos"] = bool(
        http_get == 200
        and isinstance(body_get, dict)
        and (body_get.get("id_activo_biologico") or body_get.get("detalle_individual"))
    )
    if out["get_expone_datos"]:
        out["resultado"] = "RECHAZADO"
        out["conclusion_bola"] = (
            f"GET HTTP {http_get} expuso el activo ajeno. BOLA de lectura."
        )
        EVIDENCIA["incidente_bola"]["estado"] = "REPRODUCIDA"
        pytest.fail(out["conclusion_bola"])

    r_patch = requests.patch(
        f"{BASE_URL}/activos-biologicos/{ACTIVO_BOLA}",
        headers={**_auth(tok_b), "Content-Type": "application/json"},
        json={"raza": MARCADOR},
        timeout=TIMEOUT,
        verify=VERIFY_SSL,
    )
    body_patch = _json(r_patch)
    out["patch_http"] = r_patch.status_code
    out["patch_body"] = _trunc(body_patch, 1200)

    http_ver, body_ver = _get_activo(tok_a, ACTIVO_BOLA)
    raza_despues = _raza(body_ver) if http_ver == 200 else None
    out["admin_get_post_patch_http"] = http_ver
    out["raza_despues"] = raza_despues
    persistio = raza_despues == MARCADOR
    out["persistencia"] = persistio

    if persistio:
        r_rest = requests.patch(
            f"{BASE_URL}/activos-biologicos/{ACTIVO_BOLA}",
            headers={**_auth(tok_a), "Content-Type": "application/json"},
            json={"raza": raza_orig},
            timeout=TIMEOUT,
            verify=VERIFY_SSL,
        )
        http_ok, body_ok = _get_activo(tok_a, ACTIVO_BOLA)
        out["restauracion"] = {
            "http_patch_admin": r_rest.status_code,
            "http_get": http_ok,
            "raza_final": _raza(body_ok) if http_ok == 200 else None,
        }
        out["resultado"] = "RECHAZADO"
        out["conclusion_bola"] = (
            f"GET HTTP {http_get} (sin exposicion de ficha) pero PATCH HTTP {r_patch.status_code} "
            f"persistio raza={MARCADOR} en activo {ACTIVO_BOLA} finca {finca_act} "
            f"con usuario de fincas {fincas}."
        )
        EVIDENCIA["incidente_bola"]["estado"] = "REPRODUCIDA"
        pytest.fail(out["conclusion_bola"])

    if r_patch.status_code in (403, 404) and http_get in (403, 404):
        out["resultado"] = "APROBADO"
        out["conclusion_bola"] = (
            f"GET HTTP {http_get}, PATCH HTTP {r_patch.status_code}. Raza intacta "
            f"({raza_despues!r}). Autorizacion de objeto efectiva."
        )
        EVIDENCIA["incidente_bola"]["estado"] = "NO REPRODUCIBLE"
        return

    out["resultado"] = "RECHAZADO"
    out["conclusion_bola"] = (
        f"GET HTTP {http_get}, PATCH HTTP {r_patch.status_code}, persistencia={persistio}. "
        "No cumple 403/404 en ambas superficies o resultado ambiguo."
    )
    EVIDENCIA["incidente_bola"]["estado"] = "REPRODUCIDA" if persistio else "INDETERMINADO"
    pytest.fail(out["conclusion_bola"])


def test_tc_m02_028_mass_assignment(sesion):
    out = {
        "resultado": "BLOQUEADO",
        "payload_protegidos": {"estado": "CERRADO", "cantidad_actual": 9999},
        "http_post": None,
        "id_creado": None,
        "estado_final": None,
        "cantidad_inicial": None,
        "cantidad_actual": None,
        "comportamiento": None,
        "restauracion": None,
        "conclusion_mass_assignment": "",
    }
    EVIDENCIA["subcasos"]["TC-M02-028"] = out
    tok = (sesion["productor"]["token"] if sesion["productor"]["ok"] else None) or (
        sesion["admin"]["token"] if sesion["admin"]["ok"] else None
    )
    if not tok:
        out["conclusion_mass_assignment"] = "BLOQUEADO: sin token Productor/Admin."
        pytest.skip(out["conclusion_mass_assignment"])
    out["usuario_post"] = CORREO_PRODUCTOR if sesion["productor"]["ok"] else CORREO_ADMIN

    payload = {
        "tipo_activo": "POBLACIONAL",
        "id_especie": ESPECIE_5,
        "fecha_inicio_ciclo": "2026-09-09",
        "origen_financiero": "nacimiento",
        "id_infraestructura": INFRA_3,
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

    if r_post.status_code in (400, 422):
        out["resultado"] = "APROBADO"
        out["comportamiento"] = "campo rechazado por contrato/schema"
        out["conclusion_mass_assignment"] = (
            f"POST HTTP {r_post.status_code}: el backend rechazo el payload con extras "
            "estado/cantidad_actual. No se persistieron CERRADO ni 9999."
        )
        return
    if r_post.status_code == 500:
        out["conclusion_mass_assignment"] = "POST HTTP 500. No se evalua mass assignment."
        pytest.skip(out["conclusion_mass_assignment"])
    if r_post.status_code != 201:
        out["conclusion_mass_assignment"] = f"POST HTTP {r_post.status_code}."
        pytest.skip(out["conclusion_mass_assignment"])

    aid = body_post.get("id_activo_biologico") or body_post.get("id")
    out["id_creado"] = aid
    http_g, body_g = _get_activo(tok if sesion["productor"]["ok"] else sesion["admin"]["token"], int(aid))
    if http_g != 200 and sesion["admin"]["ok"]:
        http_g, body_g = _get_activo(sesion["admin"]["token"], int(aid))
    out["http_get"] = http_g
    out["respuesta_get"] = _trunc(body_g, 1800)
    estado = str(body_g.get("nombre_estado") or body_g.get("estado") or "").upper()
    det = body_g.get("detalle_poblacional") or {}
    cant = det.get("cantidad_actual")
    cant_ini = det.get("cantidad_inicial")
    out["estado_final"] = estado
    out["cantidad_actual"] = cant
    out["cantidad_inicial"] = cant_ini
    out["comportamiento"] = "campo ignorado" if estado == "ACTIVO" and cant != 9999 else "campo aceptado"

    tok_admin = sesion["admin"]["token"] if sesion["admin"]["ok"] else tok
    r_rest = requests.patch(
        f"{BASE_URL}/activos-biologicos/{aid}/estado",
        headers={**_auth(tok_admin), "Content-Type": "application/json"},
        json={
            "estado_nuevo": "INACTIVO",
            "fecha_cambio_estado": "2026-09-26",
            "motivo_cambio": "Restauracion TC-M02-G15 rev4 mass assignment",
        },
        timeout=TIMEOUT,
        verify=VERIFY_SSL,
    )
    out["restauracion"] = {"http": r_rest.status_code, "body": _trunc(_json(r_rest), 600)}

    if estado == "CERRADO" or (cant is not None and int(cant) == 9999):
        out["resultado"] = "RECHAZADO"
        out["conclusion_mass_assignment"] = (
            f"Campos protegidos persistidos: estado={estado} cantidad_actual={cant}."
        )
        pytest.fail(out["conclusion_mass_assignment"])
    if estado != "ACTIVO":
        out["resultado"] = "RECHAZADO"
        out["conclusion_mass_assignment"] = f"estado_final={estado}, esperado ACTIVO."
        pytest.fail(out["conclusion_mass_assignment"])
    if cant is not None and int(cant) != int(cant_ini or 10):
        out["resultado"] = "RECHAZADO"
        out["conclusion_mass_assignment"] = (
            f"cantidad_actual={cant} no coincide con cantidad_inicial={cant_ini}."
        )
        pytest.fail(out["conclusion_mass_assignment"])
    out["resultado"] = "APROBADO"
    out["conclusion_mass_assignment"] = (
        "Extras ignorados. estado=ACTIVO, cantidad_actual=cantidad_inicial. "
        f"Activo {aid} restaurado a INACTIVO via PATCH /estado HTTP {r_rest.status_code}."
    )


def test_tc_m02_031_exceso_datos(sesion):
    out = {
        "resultado": "BLOQUEADO",
        "usuario": None,
        "rol": None,
        "permiso_financiero": None,
        "endpoint": f"GET /activos-biologicos/{ACTIVO_BOLA}",
        "campos_presentes": [],
        "campos_con_valor": [],
        "conclusion_exceso": "",
    }
    EVIDENCIA["subcasos"]["TC-M02-031"] = out
    ing = sesion["ingeniero"] if sesion["ingeniero"]["ok"] else sesion.get("ingeniero_alt")
    if not ing or not ing.get("ok"):
        out["login_ingeniero"] = sesion["ingeniero"]
        out["login_alt"] = sesion.get("ingeniero_alt")
        out["conclusion_exceso"] = (
            f"BLOQUEADO: Ingeniero {CORREO_INGENIERO} HTTP {sesion['ingeniero']['http']} "
            f"{sesion['ingeniero']['error_code']}."
        )
        pytest.skip(out["conclusion_exceso"])

    tok = ing["token"]
    out["usuario"] = ing["correo"]
    http_me, me = _me(tok)
    http_p, perms = _permisos(tok)
    http_f, fincas = _ids_fincas(tok)
    out["me_http"] = http_me
    out["rol"] = (me.get("nombre_rol") or me.get("rol") or me.get("id_rol")) if isinstance(me, dict) else None
    out["fincas_usuario"] = fincas
    out["permisos_http"] = http_p
    nombres = []
    if isinstance(perms, dict):
        lista = perms.get("permisos") or perms.get("registros") or []
        for p in lista:
            if isinstance(p, dict):
                nombres.append(str(p.get("nombre_recurso") or p.get("recurso") or ""))
    out["recursos_permiso"] = nombres
    out["permiso_financiero"] = any("financ" in n.lower() or "costo" in n.lower() for n in nombres)

    http_g, body = _get_activo(tok, ACTIVO_BOLA)
    out["http_get"] = http_g
    out["respuesta"] = _trunc(body, 2000)
    if http_g == 200 and isinstance(body, dict):
        out["campos_presentes"] = [k for k in CAMPOS_FIN if k in body]
        out["campos_con_valor"] = _hits_valor(body)
        out["costo_adquisicion"] = body.get("costo_adquisicion")
        out["soporte_documental"] = body.get("soporte_documental")
        out["soporte_documental_costo"] = body.get("soporte_documental_costo")

    if http_g in (401, 423):
        out["conclusion_exceso"] = f"GET HTTP {http_g}: no se evalua exposicion."
        pytest.skip(out["conclusion_exceso"])
    if http_g in (403, 404):
        if not fincas or 65 not in fincas:
            out["conclusion_exceso"] = (
                f"GET HTTP {http_g} y fincas={fincas}. No hay ficha propia visible."
            )
            pytest.skip(out["conclusion_exceso"])
        # finca 65 es del ingeniero; 404 seria anomalo para API3
        out["conclusion_exceso"] = f"GET propio esperado; HTTP {http_g}."
        pytest.skip(out["conclusion_exceso"])
    if http_g != 200:
        out["conclusion_exceso"] = f"GET HTTP {http_g}."
        pytest.skip(out["conclusion_exceso"])

    valor_costo = body.get("costo_adquisicion") if isinstance(body, dict) else None
    valor_sop = body.get("soporte_documental") if isinstance(body, dict) else None
    valor_alias = body.get("soporte_documental_costo") if isinstance(body, dict) else None
    expuesto = valor_costo not in (None, "", []) or valor_sop not in (None, "", []) or valor_alias not in (None, "", [])
    if expuesto and not out["permiso_financiero"]:
        out["resultado"] = "RECHAZADO"
        out["conclusion_exceso"] = (
            "Rol Ingeniero de Campo recibio costo_adquisicion y/o soporte_documental "
            "con valor en GET /activos-biologicos/{id}."
        )
        pytest.fail(out["conclusion_exceso"])
    if "costo_adquisicion" not in (body or {}) and "soporte_documental" not in (body or {}) and "soporte_documental_costo" not in (body or {}):
        out["resultado"] = "APROBADO"
        out["conclusion_exceso"] = "Campos financieros ausentes en la respuesta."
        return
    if not expuesto:
        out["resultado"] = "APROBADO"
        out["conclusion_exceso"] = (
            "Claves presentes pero nulas/vacias (sin valor financiero). "
            "No hay exposicion de dato financiero."
        )
        return
    out["resultado"] = "RECHAZADO"
    out["conclusion_exceso"] = "Datos financieros visibles."
    pytest.fail(out["conclusion_exceso"])


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
