"""TC-M02-G15 rev5 — solo TC-M02-031 (exceso de datos financieros / API3).

No modifica codigo productivo ni rev1-rev4. Sin DML. Sin commit.
027 y 028 no se reejecutan: permanecen APROBADO desde rev4.
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
ENV_PATH = DIR / "environment-g15-rev5.json"

with ENV_PATH.open(encoding="utf-8") as fh:
    ENV = json.load(fh)

BASE_URL = ENV["baseUrl"].rstrip("/")
CORREO_ADMIN = ENV["correo_admin"]
CORREO_INGENIERO = ENV["correo_ingeniero"]
CORREO_ING_ALT = ENV["correo_ingeniero_alt"]
ROL_ESPERADO = ENV["rol_esperado"]
ACTIVO_HIST = int(ENV["activo_historico_031"])
TIMEOUT = 45
VERIFY_SSL = False
CAMPOS_FIN = ("costo_adquisicion", "soporte_documental", "soporte_documental_costo")

EVIDENCIA: dict = {
    "caso": "TC-M02-G15",
    "revision": 5,
    "rf": ["RF-33", "RF-34"],
    "ambiente": "TEST",
    "base_url": BASE_URL,
    "fecha_utc": datetime.now(timezone.utc).isoformat(),
    "alcance": "Solo TC-M02-031. 027 y 028 no reejecutados (APROBADO rev4).",
    "contrato_dto": (
        "ActivoBiologicoResponse incluye origen_financiero, costo_adquisicion y "
        "soporte_documental. No existe soporte_documental_costo. "
        "origen_financiero es clasificacion de origen, no el monto/soporte."
    ),
    "endpoint_oficial": "GET /activos-biologicos/{id_activo}",
    "subcasos": {
        "TC-M02-027": {
            "resultado": "APROBADO",
            "origen": "rev4",
            "nota": "No reejecutado. GET/PATCH 404, sin persistencia.",
        },
        "TC-M02-028": {
            "resultado": "APROBADO",
            "origen": "rev4",
            "nota": "No reejecutado. Mass assignment ignorado.",
        },
    },
    "estado_global": "PENDIENTE",
    "auditoria": (
        "Rev4 intacta. Sin DML. Sin cambios productivos. Sin commit/push. "
        "Un intento de login por usuario Ingeniero. Admin solo lectura de confirmacion."
    ),
}


def _password_admin() -> str:
    return os.environ.get("SGPMP_TEST_PASSWORD") or os.environ.get("CONTRASENA") or ""


def _password_ingeniero() -> str:
    valor = (
        os.environ.get("SGPMP_INGENIERO_PASSWORD")
        or os.environ.get("ENGINEER_PASSWORD")
        or ""
    )
    if not valor:
        pytest.skip("BLOQUEADO: definir SGPMP_INGENIERO_PASSWORD o ENGINEER_PASSWORD.")
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


def _login(correo: str, password: str) -> tuple[int, dict, str | None]:
    r = requests.post(
        f"{BASE_URL}/sesiones/",
        json={"correo_electronico": correo, "contrasena": password},
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
        for i, item in enumerate(obj[:30]):
            hits.extend(_walk_keys(item, wanted, f"{path}[{i}]"))
    return hits


def _valor_expuesto(valor) -> bool:
    if valor in (None, "", [], {}):
        return False
    if isinstance(valor, str) and valor.strip().lower() in ("null", "none", "n/a", "-", "***", "****", "[redacted]", "oculto", "masked"):
        return False
    return True


def _hits_valor(obj) -> list[dict]:
    return [h for h in _walk_keys(obj, CAMPOS_FIN) if _valor_expuesto(h.get("valor"))]


def _get_activo(token: str, aid: int):
    r = requests.get(
        f"{BASE_URL}/activos-biologicos/{aid}",
        headers=_auth(token),
        timeout=TIMEOUT,
        verify=VERIFY_SSL,
    )
    return r.status_code, _json(r)


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
    return r.status_code, _json(r)


def _catalogo_recursos(token: str):
    r = requests.get(
        f"{BASE_URL}/roles/catalogo/recursos",
        headers=_auth(token),
        timeout=TIMEOUT,
        verify=VERIFY_SSL,
    )
    return r.status_code, _json(r)


def _listar(token: str, pagina: int = 1, page_size: int = 100):
    r = requests.get(
        f"{BASE_URL}/activos-biologicos",
        headers=_auth(token),
        params={"pagina": pagina, "page_size": page_size},
        timeout=TIMEOUT,
        verify=VERIFY_SSL,
    )
    return r.status_code, _json(r)


def _escribir_evidencia() -> None:
    RESULTADOS.mkdir(parents=True, exist_ok=True)
    payload = _redact(EVIDENCIA)
    json_path = RESULTADOS / "TC-M02-G15-rev5.json"
    txt_path = RESULTADOS / "TC-M02-G15-rev5.txt"
    html_path = RESULTADOS / "TC-M02-G15-rev5-evidencia.html"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    lineas = [
        "TC-M02-G15 rev5 — solo TC-M02-031 — TEST",
        f"Fecha UTC: {payload.get('fecha_utc')}",
        f"Estado global: {payload.get('estado_global')}",
        "",
        json.dumps(payload.get("subcasos"), ensure_ascii=False, indent=2, default=str),
        "",
        payload.get("auditoria"),
        "Password/JWT: [REDACTED]. Rev4 no modificada.",
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
        "<title>TC-M02-G15 rev5</title></head><body>"
        "<h1>TC-M02-G15 rev5 — TC-M02-031</h1>"
        f"<p>Estado global: {payload.get('estado_global')}</p>"
        + "".join(bloques)
        + "<p>Sin passwords ni JWT. Rev4 intacta. 027/028 no reejecutados.</p>"
        "</body></html>",
        encoding="utf-8",
    )


@pytest.fixture(scope="session")
def sesion():
    pwd_ing = _password_ingeniero()
    http, body, tok = _login(CORREO_INGENIERO, pwd_ing)
    logins = {
        "ingeniero": {
            "correo": CORREO_INGENIERO,
            "http": http,
            "ok": bool(tok) and http == 200,
            "token": tok,
            "error_code": body.get("error_code") if isinstance(body, dict) else None,
            "intentos": 1,
        }
    }
    if logins["ingeniero"]["http"] == 401:
        http2, body2, tok2 = _login(CORREO_ING_ALT, pwd_ing)
        logins["ingeniero_alt"] = {
            "correo": CORREO_ING_ALT,
            "http": http2,
            "ok": bool(tok2) and http2 == 200,
            "token": tok2,
            "error_code": body2.get("error_code") if isinstance(body2, dict) else None,
            "intentos": 1,
        }
    EVIDENCIA["logins"] = {
        k: {kk: vv for kk, vv in v.items() if kk != "token"}
        for k, v in logins.items()
    }
    yield logins
    _escribir_evidencia()


def test_tc_m02_031_exceso_datos(sesion):
    out = {
        "resultado": "BLOQUEADO",
        "usuario": None,
        "login": None,
        "rol_confirmado": None,
        "estado_cuenta": None,
        "permiso_financiero": None,
        "activo_consultado": None,
        "endpoint": "GET /activos-biologicos/{id_activo}",
        "http_status": None,
        "campos_financieros_presentes": [],
        "campos_financieros_con_valor": [],
        "criterio": "Ingeniero sin permiso financiero no debe ver costo_adquisicion ni soporte_documental con valor.",
        "conclusion_exceso": "",
    }
    EVIDENCIA["subcasos"]["TC-M02-031"] = out

    ing = sesion["ingeniero"] if sesion["ingeniero"]["ok"] else sesion.get("ingeniero_alt")
    out["login_ingeniero"] = {k: v for k, v in sesion["ingeniero"].items() if k != "token"}
    if "ingeniero_alt" in sesion:
        out["login_alt"] = {k: v for k, v in sesion["ingeniero_alt"].items() if k != "token"}

    if not ing or not ing.get("ok"):
        out["login"] = "fallido"
        out["conclusion_exceso"] = (
            f"BLOQUEADO: {CORREO_INGENIERO} HTTP {sesion['ingeniero']['http']} "
            f"{sesion['ingeniero'].get('error_code')}"
            + (
                f"; alt {CORREO_ING_ALT} HTTP {sesion['ingeniero_alt']['http']} "
                f"{sesion['ingeniero_alt'].get('error_code')}"
                if "ingeniero_alt" in sesion
                else "."
            )
            + ". Un intento por usuario. No se evalua exposicion."
        )
        pytest.skip(out["conclusion_exceso"])

    tok = ing["token"]
    out["usuario"] = ing["correo"]
    out["login"] = f"HTTP {ing['http']}"

    http_me, me = _me(tok)
    out["me_http"] = http_me
    out["me"] = _trunc(me, 1500)
    rol = None
    estado = None
    fincas_me = []
    if isinstance(me, dict):
        rol = me.get("nombre_rol") or me.get("rol")
        estado = me.get("estado_cuenta") or me.get("estado")
        fincas_me = me.get("fincas") if isinstance(me.get("fincas"), list) else []
    out["rol_confirmado"] = rol
    out["estado_cuenta"] = estado
    out["fincas_me"] = _trunc(fincas_me, 800)

    if http_me != 200:
        out["conclusion_exceso"] = f"BLOQUEADO: GET /usuarios/me HTTP {http_me}."
        pytest.skip(out["conclusion_exceso"])
    if str(rol).strip().lower() != ROL_ESPERADO.lower():
        out["conclusion_exceso"] = (
            f"BLOQUEADO: rol confirmado='{rol}', esperado '{ROL_ESPERADO}'. "
            "No se sustituye por otro rol."
        )
        pytest.skip(out["conclusion_exceso"])
    if estado and str(estado).strip().lower() not in ("activo", "activa"):
        out["conclusion_exceso"] = f"BLOQUEADO: estado_cuenta='{estado}', esperado Activo."
        pytest.skip(out["conclusion_exceso"])

    http_p, perms = _permisos(tok)
    out["permisos_http"] = http_p
    out["permisos"] = _trunc(perms, 1200)

    http_cat, catalogo = _catalogo_recursos(tok)
    out["catalogo_recursos_http"] = http_cat
    mapa = {}
    for rec in _registros(catalogo) if http_cat == 200 else []:
        if isinstance(rec, dict):
            rid = rec.get("id_recurso") or rec.get("id")
            nombre = rec.get("nombre_recurso") or rec.get("nombre")
            if rid is not None:
                mapa[int(rid)] = str(nombre or "")
    if http_cat != 200:
        out["catalogo_recursos_nota"] = (
            f"GET /roles/catalogo/recursos HTTP {http_cat}; se evalua por ids y nombres disponibles."
        )

    nombres_perm = []
    pares = []
    if isinstance(perms, dict):
        for p in perms.get("permisos") or []:
            if not isinstance(p, dict):
                continue
            rid = p.get("id_recurso")
            acc = p.get("id_accion")
            nom = mapa.get(int(rid), "") if rid is not None else ""
            pares.append({"id_recurso": rid, "id_accion": acc, "nombre_recurso": nom or None})
            if nom:
                nombres_perm.append(nom)
    out["permisos_resueltos"] = pares[:80]
    financieros = [
        n for n in nombres_perm
        if any(x in n.lower() for x in ("financ", "costo", "gasto", "nic41", "provision"))
    ]
    out["recursos_financieros_asignados"] = financieros
    out["permiso_financiero"] = bool(financieros)

    http_l, lista = _listar(tok)
    out["listado_http"] = http_l
    registros = _registros(lista) if http_l == 200 else []
    total = lista.get("total_registros") if isinstance(lista, dict) else None
    out["listado_total"] = total
    out["listado_muestra"] = len(registros)
    ids_acceso = []
    con_fin_en_listado = []
    for item in registros:
        if not isinstance(item, dict):
            continue
        aid = item.get("id_activo_biologico")
        if aid is not None:
            ids_acceso.append(int(aid))
        if _valor_expuesto(item.get("costo_adquisicion")) or _valor_expuesto(item.get("soporte_documental")):
            con_fin_en_listado.append(int(aid))
    out["ids_accesibles_pagina1"] = ids_acceso
    out["ids_con_valor_financiero_en_listado"] = con_fin_en_listado

    activo_id = None
    admin_confirm = None
    if con_fin_en_listado:
        activo_id = con_fin_en_listado[0]
        out["precondicion_datos"] = "Listado del Ingeniero ya incluye valor financiero almacenado/expuesto."
    elif ids_acceso:
        pwd_admin = _password_admin()
        if not pwd_admin:
            out["conclusion_exceso"] = (
                "BLOQUEADO: listado sin valores financieros visibles; no hay SGPMP_TEST_PASSWORD "
                "para confirmar con Admin (solo lectura)."
            )
            pytest.skip(out["conclusion_exceso"])
        http_a, _body_a, tok_a = _login(CORREO_ADMIN, pwd_admin)
        out["login_admin_confirmacion"] = {
            "correo": CORREO_ADMIN,
            "http": http_a,
            "ok": http_a == 200,
            "intentos": 1,
            "uso": "solo lectura para confirmar datos financieros almacenados",
        }
        if http_a != 200:
            out["conclusion_exceso"] = (
                f"BLOQUEADO: no se pudo confirmar precondicion de datos (Admin HTTP {http_a}). "
                "Listado Ingeniero sin costo/soporte con valor."
            )
            pytest.skip(out["conclusion_exceso"])
        hallado = None
        revisados = []
        candidatos = list(ids_acceso)
        if ACTIVO_HIST not in candidatos:
            candidatos.append(ACTIVO_HIST)
        for aid in candidatos[:40]:
            st, body_adm = _get_activo(tok_a, aid)
            tiene = False
            if st == 200 and isinstance(body_adm, dict):
                tiene = _valor_expuesto(body_adm.get("costo_adquisicion")) or _valor_expuesto(
                    body_adm.get("soporte_documental")
                )
            revisados.append({"id": aid, "http": st, "tiene_financiero": tiene})
            if tiene and aid in ids_acceso:
                hallado = aid
                admin_confirm = {
                    "id": aid,
                    "http": st,
                    "costo_adquisicion": body_adm.get("costo_adquisicion"),
                    "soporte_documental": body_adm.get("soporte_documental"),
                    "origen_financiero": body_adm.get("origen_financiero"),
                }
                break
        out["admin_revisados"] = revisados
        out["admin_confirmacion"] = admin_confirm
        if hallado is None:
            # historico 350 puede estar fuera de alcance del ingeniero
            out["conclusion_exceso"] = (
                "BLOQUEADO: el Ingeniero no tiene un activo accesible con "
                "costo_adquisicion y/o soporte_documental almacenados. Sin DML."
            )
            pytest.skip(out["conclusion_exceso"])
        activo_id = hallado
        out["precondicion_datos"] = "Admin confirmo datos financieros en activo accesible al Ingeniero."
    else:
        # intentar historico 350
        activo_id = ACTIVO_HIST
        out["precondicion_datos"] = (
            f"Listado vacio o HTTP {http_l}; se intenta activo historico {ACTIVO_HIST}."
        )

    http_g, body = _get_activo(tok, activo_id)
    out["activo_consultado"] = activo_id
    out["http_status"] = http_g
    out["respuesta_ingeniero"] = _trunc(body, 2500)
    if http_g == 200 and isinstance(body, dict):
        out["campos_financieros_presentes"] = [k for k in CAMPOS_FIN if k in body]
        out["campos_financieros_con_valor"] = _hits_valor(body)
        out["costo_adquisicion"] = body.get("costo_adquisicion")
        out["soporte_documental"] = body.get("soporte_documental")
        out["soporte_documental_costo"] = body.get("soporte_documental_costo")
        out["origen_financiero"] = body.get("origen_financiero")
        out["claves_respuesta"] = sorted(str(k) for k in body.keys())

    if http_g in (401, 423):
        out["conclusion_exceso"] = f"BLOQUEADO: GET HTTP {http_g}; no se evalua exposicion."
        pytest.skip(out["conclusion_exceso"])
    if http_g in (403, 404):
        out["conclusion_exceso"] = (
            f"BLOQUEADO: GET /activos-biologicos/{activo_id} HTTP {http_g}. "
            "No hay ficha accesible para comprobar exposicion."
        )
        pytest.skip(out["conclusion_exceso"])
    if http_g != 200:
        out["conclusion_exceso"] = f"BLOQUEADO: GET HTTP {http_g}."
        pytest.skip(out["conclusion_exceso"])

    expuesto = bool(out.get("campos_financieros_con_valor"))
    if expuesto and not out["permiso_financiero"]:
        out["resultado"] = "RECHAZADO"
        out["conclusion_exceso"] = (
            "RECHAZADO / API3: Ingeniero de Campo sin permiso financiero recibio "
            "costo_adquisicion y/o soporte_documental con valor en "
            f"GET /activos-biologicos/{activo_id}."
        )
        pytest.fail(out["conclusion_exceso"])
    presentes = out.get("campos_financieros_presentes") or []
    if not presentes:
        out["resultado"] = "APROBADO"
        out["conclusion_exceso"] = "Campos financieros ausentes en la respuesta del Ingeniero."
        return
    if not expuesto:
        out["resultado"] = "APROBADO"
        out["conclusion_exceso"] = (
            "Claves del DTO presentes (contrato ActivoBiologicoResponse) pero nulas/enmascaradas. "
            "No hay exposicion de dato financiero."
        )
        return
    out["resultado"] = "RECHAZADO"
    out["conclusion_exceso"] = "Datos financieros visibles."
    pytest.fail(out["conclusion_exceso"])


def test_zz_estado_global(sesion):
    subs = EVIDENCIA.get("subcasos") or {}
    r031 = (subs.get("TC-M02-031") or {}).get("resultado")
    if r031 == "RECHAZADO":
        EVIDENCIA["estado_global"] = "RECHAZADO"
    elif r031 == "APROBADO":
        EVIDENCIA["estado_global"] = "APROBADO"
    else:
        EVIDENCIA["estado_global"] = "BLOQUEADO"
    assert EVIDENCIA["estado_global"] in ("APROBADO", "RECHAZADO", "BLOQUEADO")
