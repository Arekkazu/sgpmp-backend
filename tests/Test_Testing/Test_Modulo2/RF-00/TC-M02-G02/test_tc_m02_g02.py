"""TC-M02-G02 / TC-M02-003 — RF-00 pruebas generales M02.

Control de acceso (OWASP API5): un Productor autenticado no debe poder
crear especies en POST /configuracion/especies.

Caja negra contra TEST. Un login por usuario. Password via entorno.
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
ENV_PATH = DIR / "environment-g02.json"

with ENV_PATH.open(encoding="utf-8") as fh:
    ENV = json.load(fh)

BASE_URL = ENV["baseUrl"].rstrip("/")
CORREO_ADMIN = ENV["correo_admin"]
CORREO_PRODUCTOR = ENV["correo_productor"]
NOMBRE_PREFERIDO = ENV["nombre_preferido"]
DESCRIPCION = ENV["descripcion"]
TIMEOUT = 30
VERIFY_SSL = False

_EVIDENCIA: dict = {
    "caso": "TC-M02-G02",
    "subcaso": "TC-M02-003",
    "rf": "RF-00",
    "ambiente": "TEST",
    "base_url": BASE_URL,
    "fecha_utc": datetime.now(timezone.utc).isoformat(),
    "pasos": [],
    "http": {},
    "aserciones": [],
    "clasificacion_funcional": "PENDIENTE",
    "auditoria": (
        "La auditoria del intento no pudo verificarse mediante API publica "
        "disponible."
    ),
    "limitaciones": [
        "POST /configuracion/especies exige RBAC recurso 8 accion C=1; el 403 "
        "sale de require_permission ANTES del caso de uso de registro.",
        "No hay GET publico de intentos de autorizacion fallidos sobre especies.",
        "Disponibilidad M02/M03/M04 no aplica a este escenario de denegacion.",
    ],
    "residuo": "ninguno esperado",
}


def _password() -> str:
    valor = os.environ.get("SGPMP_TEST_PASSWORD") or os.environ.get("CONTRASENA") or ""
    if not valor:
        pytest.skip(
            "BLOQUEADO: definir SGPMP_TEST_PASSWORD o CONTRASENA. "
            "No se hardcodea password."
        )
    return valor


def _redact(obj):
    if obj is None:
        return None
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            kl = str(k).lower()
            if any(x in kl for x in ("token", "password", "contrasena", "authorization", "jwt")):
                out[k] = "[REDACTED]"
            else:
                out[k] = _redact(v)
        return out
    if isinstance(obj, list):
        return [_redact(x) for x in obj]
    if isinstance(obj, str) and obj.startswith("eyJ"):
        return "[REDACTED]"
    return obj


def _paso(texto: str) -> None:
    _EVIDENCIA["pasos"].append(texto)


def _aser(nombre: str, ok: bool, detalle: str) -> None:
    _EVIDENCIA["aserciones"].append({"nombre": nombre, "ok": ok, "detalle": detalle})


def _escribir_evidencia() -> None:
    RESULTADOS.mkdir(parents=True, exist_ok=True)
    json_path = RESULTADOS / "TC-M02-G02.json"
    txt_path = RESULTADOS / "TC-M02-G02-ejecucion.txt"
    html_path = RESULTADOS / "TC-M02-G02-evidencia.html"
    payload = _redact(_EVIDENCIA)
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    lineas = [
        "TC-M02-G02 / TC-M02-003 - RF-00 - TEST",
        f"Fecha UTC: {payload.get('fecha_utc')}",
        f"Clasificacion funcional: {payload.get('clasificacion_funcional')}",
        f"HTTP: {json.dumps(payload.get('http'), ensure_ascii=False)}",
        "",
        "Pasos:",
        *[f"- {p}" for p in payload.get("pasos") or []],
        "",
        "Aserciones:",
        *[
            f"- [{'PASS' if a['ok'] else 'FAIL'}] {a['nombre']}: {a['detalle']}"
            for a in payload.get("aserciones") or []
        ],
        "",
        f"Auditoria: {payload.get('auditoria')}",
        f"Residuo: {payload.get('residuo')}",
        "",
        "Limitaciones:",
        *[f"- {x}" for x in payload.get("limitaciones") or []],
        "",
        "Password/JWT: no incluidos ([REDACTED]).",
    ]
    txt_path.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    filas = "".join(
        f"<tr><td>{a['nombre']}</td><td>{'PASS' if a['ok'] else 'FAIL'}</td>"
        f"<td>{a['detalle']}</td></tr>"
        for a in payload.get("aserciones") or []
    )
    html_path.write_text(
        "<!DOCTYPE html><html lang='es'><head><meta charset='utf-8'>"
        "<title>TC-M02-G02</title></head><body>"
        "<h1>TC-M02-G02 / TC-M02-003</h1>"
        f"<p>Clasificacion: {payload.get('clasificacion_funcional')}</p>"
        f"<p>HTTP: {payload.get('http')}</p>"
        f"<table border='1'><tr><th>Asercion</th><th>Resultado</th><th>Detalle</th></tr>"
        f"{filas}</table>"
        f"<p>{payload.get('auditoria')}</p>"
        "<p>Sin passwords ni JWT.</p>"
        "</body></html>",
        encoding="utf-8",
    )


def _login_una_vez(correo: str, etiqueta: str) -> tuple[int, dict, str | None]:
    resp = requests.post(
        f"{BASE_URL}/sesiones/",
        json={"correo_electronico": correo, "contrasena": _password()},
        timeout=TIMEOUT,
        verify=VERIFY_SSL,
    )
    cuerpo = {}
    try:
        cuerpo = resp.json()
    except Exception:
        cuerpo = {"raw": resp.text[:500]}
    _EVIDENCIA["http"][f"login_{etiqueta}"] = resp.status_code
    _paso(f"Login {etiqueta} ({correo}) HTTP {resp.status_code} (un intento).")
    token = cuerpo.get("token") if resp.status_code == 200 else None
    if isinstance(token, str) and not token:
        token = None
    return resp.status_code, _redact(cuerpo), token


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _nombres(items: list) -> set[str]:
    return {str(e.get("nombre") or "").strip().lower() for e in items}


def _catalogo(token: str, etiqueta: str) -> tuple[int, dict]:
    resp = requests.get(
        f"{BASE_URL}/configuracion/especies",
        headers=_headers(token),
        timeout=TIMEOUT,
        verify=VERIFY_SSL,
    )
    cuerpo = {}
    try:
        cuerpo = resp.json()
    except Exception:
        cuerpo = {"raw": resp.text[:500]}
    _EVIDENCIA["http"][f"get_{etiqueta}"] = resp.status_code
    _paso(f"GET /configuracion/especies ({etiqueta}) HTTP {resp.status_code}.")
    return resp.status_code, cuerpo


def _elegir_nombre(items: list) -> str:
    usados = _nombres(items)
    candidatos = [
        NOMBRE_PREFERIDO,
        "Especie Seguridad Laura Dos",
        "Especie Acceso Productor",
        "Especie Prueba Rbacqa",
    ]
    for n in candidatos:
        if n.strip().lower() not in usados:
            return n
    raise RuntimeError("No hay nombre libre valido (solo letras y espacios).")


def test_tc_m02_003_productor_no_puede_crear_especie():
    """TC-M02-003: Productor autenticado recibe 403 y no se crea la especie."""
    try:
        token_prod = None
        token_admin = None
        http_prod, _cuerpo_prod, token_prod = _login_una_vez(CORREO_PRODUCTOR, "productor")
        if http_prod != 200 or not token_prod:
            _EVIDENCIA["clasificacion_funcional"] = "BLOQUEADO"
            _aser(
                "login_productor",
                False,
                f"HTTP {http_prod}. No se interpreta como fallo de RBAC.",
            )
            pytest.skip(
                f"BLOQUEADO por autenticacion del Productor (HTTP {http_prod}). "
                "No se reintenta login. No se evalua autorizacion."
            )

        _aser("login_productor", True, "HTTP 200 con token (redactado).")

        http_admin, _cuerpo_admin, token_admin = _login_una_vez(CORREO_ADMIN, "admin")
        if http_admin != 200:
            _paso(
                "Login Admin no OK; el precheck/postcheck dependera del GET del Productor."
            )

        http_get_prod, cat_prod = _catalogo(token_prod, "productor_pre")
        items_pre = []
        lector = None

        if http_get_prod == 200 and isinstance(cat_prod, dict) and isinstance(cat_prod.get("items"), list):
            items_pre = cat_prod["items"]
            lector = "productor"
            _aser("get_productor_precheck", True, "Productor tiene lectura del catalogo.")
        elif http_get_prod == 403:
            _aser(
                "get_productor_precheck",
                True,
                "GET Productor 403: no se trata como defecto; el caso exige denegar POST.",
            )
            if token_admin:
                http_get_admin, cat_admin = _catalogo(token_admin, "admin_pre")
                if http_get_admin != 200 or not isinstance(cat_admin.get("items"), list):
                    _EVIDENCIA["clasificacion_funcional"] = "BLOQUEADO"
                    _aser("precheck_catalogo", False, f"Admin GET HTTP {http_get_admin}.")
                    pytest.skip(
                        "BLOQUEADO: no hay forma API de comprobar ausencia del nombre "
                        "(GET Productor 403 y GET Admin no 200)."
                    )
                items_pre = cat_admin["items"]
                lector = "admin"
            else:
                _EVIDENCIA["clasificacion_funcional"] = "BLOQUEADO"
                pytest.skip(
                    "BLOQUEADO: GET Productor 403 y Admin no autenticado; "
                    "no se puede demostrar no-creacion."
                )
        elif http_get_prod == 401:
            _EVIDENCIA["clasificacion_funcional"] = "BLOQUEADO"
            _aser("get_productor_precheck", False, "GET 401: problema de token, no RBAC de POST.")
            pytest.skip("BLOQUEADO: GET Productor 401 (autenticacion/token).")
        else:
            _EVIDENCIA["clasificacion_funcional"] = "BLOQUEADO"
            _aser("get_productor_precheck", False, f"GET Productor HTTP {http_get_prod}.")
            pytest.skip(f"BLOQUEADO: GET catalogo Productor HTTP {http_get_prod}.")

        nombre = _elegir_nombre(items_pre)
        _EVIDENCIA["nombre_prueba"] = nombre
        _EVIDENCIA["total_pre"] = (
            cat_prod.get("total") if lector == "productor" and isinstance(cat_prod, dict) else len(items_pre)
        )
        assert nombre.strip().lower() not in _nombres(items_pre)
        _aser("nombre_ausente_pre", True, f"'{nombre}' no existe en precheck ({lector}).")
        _paso(f"Nombre de prueba elegido: {nombre}")

        body = {"nombre": nombre, "descripcion": DESCRIPCION}
        post = requests.post(
            f"{BASE_URL}/configuracion/especies",
            headers=_headers(token_prod),
            json=body,
            timeout=TIMEOUT,
            verify=VERIFY_SSL,
        )
        post_json = {}
        try:
            post_json = post.json()
        except Exception:
            post_json = {"raw": post.text[:800]}
        _EVIDENCIA["http"]["post_productor"] = post.status_code
        _EVIDENCIA["post_cuerpo"] = _redact(post_json)
        _paso(f"POST /configuracion/especies (Productor) HTTP {post.status_code}.")

        if post.status_code == 401:
            _EVIDENCIA["clasificacion_funcional"] = "BLOQUEADO"
            _aser("post_403", False, "POST 401: autenticacion/token, no autorizacion.")
            pytest.skip("BLOQUEADO: POST 401. No se interpreta como fallo de RBAC.")

        if post.status_code == 201:
            _EVIDENCIA["clasificacion_funcional"] = "RECHAZADO"
            creado_id = post_json.get("id_especie")
            _EVIDENCIA["residuo"] = f"especie creada id={creado_id} nombre={nombre}"
            _aser("post_403", False, f"POST {post.status_code}: el Productor pudo crear.")
            if token_admin and creado_id:
                des = requests.patch(
                    f"{BASE_URL}/configuracion/especies/{creado_id}/desactivar",
                    headers=_headers(token_admin),
                    timeout=TIMEOUT,
                    verify=VERIFY_SSL,
                )
                _EVIDENCIA["http"]["desactivar_residuo"] = des.status_code
                _paso(f"Intento desactivar residuo HTTP {des.status_code} (no es DELETE).")
            pytest.fail(
                f"Defecto potencial de autorizacion: Productor obtuvo HTTP {post.status_code} "
                f"en POST /configuracion/especies. Cuerpo redactado={_redact(post_json)}"
            )

        ok_403 = post.status_code == 403
        _aser("post_403", ok_403, f"HTTP {post.status_code} (esperado 403).")
        assert post.status_code == 403, (
            f"Se esperaba 403 Forbidden. Obtenido {post.status_code}. "
            f"Cuerpo={_redact(post_json)}"
        )

        error_code = post_json.get("error_code")
        ok_code = error_code == "ACCESO_DENEGADO"
        _aser("error_code_acceso_denegado", ok_code, f"error_code={error_code}")
        assert error_code == "ACCESO_DENEGADO"

        mensaje = str(post_json.get("message") or "")
        ok_msg = "permiso" in mensaje.lower() or "denegad" in mensaje.lower()
        _aser("mensaje_autorizacion", ok_msg, mensaje)
        assert ok_msg, f"Mensaje de 403 no coherente con falta de permisos: {mensaje}"

        token_lectura = token_prod if lector == "productor" else token_admin
        etiqueta_post = "productor_post" if lector == "productor" else "admin_post"
        http_postcheck, cat_post = _catalogo(token_lectura, etiqueta_post)
        assert http_postcheck == 200, f"POSTCHECK GET HTTP {http_postcheck}"
        items_post = cat_post.get("items") if isinstance(cat_post, dict) else []
        assert isinstance(items_post, list)
        presentes = [e for e in items_post if str(e.get("nombre") or "").strip().lower() == nombre.strip().lower()]
        ok_ausente = len(presentes) == 0
        _aser("no_creacion", ok_ausente, f"coincidencias postcheck={len(presentes)}")
        assert ok_ausente, f"La especie '{nombre}' aparecio en el catalogo tras el 403."
        _EVIDENCIA["total_post"] = cat_post.get("total") if isinstance(cat_post, dict) else len(items_post)
        _EVIDENCIA["clasificacion_funcional"] = "APROBADO"
        _EVIDENCIA["residuo"] = "ninguno: el POST no creo la especie"
        _paso("Auditoria de intento no verificable por API publica.")
    finally:
        _escribir_evidencia()
