# | Fecha      | Nombre    | Que se hizo                                                          |
# |------------|-----------|----------------------------------------------------------------------|
# | 2026-10-27 | HulkyZeus | RF-73 TC-M04-G089: correo admin configurable; 275 acepta fields |
"""
TC-M04-G089 — Límites de paginación en GET /prediccion/auditoria (httpx).
Subcasos: TC-M04-273 (default 50), 274 (max 200), 275 (201 → rechazo).

Diseño (P1'=B / P2=A / P3=A / D1=B / D2=A / D3=A / D4=Si):
- P1'=B: httpx.Client contra $env:BACKEND (backend desplegado).
- P2=A: 1 login + 1 GET + 1 DELETE por test. DEF-04 respetado.
- D1=B: test 275 verifica OpenAPI primero.
- D2=A: baseline dinámico; no se hardcodea 973.
- D3=A: cada GET +1 HISTORIAL_CONSULTADO (contaminación conocida).
- D4=Si: schema de login del desplegado = {"correo_electronico", "contrasena"}.
"""
import os
import uuid

import httpx
import pytest


BASE_URL = (os.environ.get("BACKEND") or os.environ["TEST_BASE_URL"]).rstrip("/")
ADMIN_EMAIL = os.environ.get("TEST_ADMIN_EMAIL", "administador.dev@gmail.com")
SANDBOX_SECRET = os.environ["TEST_SANDBOX_SECRET"]


def _new_run_id() -> str:
    return f"pytest-g089-{uuid.uuid4()}"


def _sandbox_headers(run_id: str) -> dict:
    return {
        "X-Test-Run-Id": run_id,
        "X-Sandbox-Secret": SANDBOX_SECRET,
    }


def _login(client: httpx.Client, run_id: str) -> str:
    r = client.post(
        "/sesiones/",
        headers=_sandbox_headers(run_id),
        json={
            "correo_electronico": ADMIN_EMAIL,
            "contrasena": os.environ["TEST_ADMIN_PASSWORD"],
        },
    )
    assert r.status_code == 200, (
        f"Login {r.status_code}: {r.text[:300]}"
    )
    body = r.json()
    assert "token" in body, f"Sin token: {list(body.keys())}"
    return body["token"]


def _auth(token: str, run_id: str) -> dict:
    h = _sandbox_headers(run_id)
    h["Authorization"] = f"Bearer {token}"
    return h


def _teardown(client: httpx.Client, run_id: str) -> None:
    r = client.delete(
        f"/test-control/runs/{run_id}",
        headers={"X-Sandbox-Secret": SANDBOX_SECRET},
    )
    assert r.status_code == 200, (
        f"Teardown {r.status_code}: {r.text[:300]}"
    )


def _openapi_declares_422(client: httpx.Client) -> bool:
    r = client.get("/openapi.json")
    if r.status_code != 200:
        return False
    schema = r.json()
    path = schema.get("paths", {}).get("/prediccion/auditoria", {})
    get_op = path.get("get", {})
    responses = get_op.get("responses", {})
    return "422" in responses


@pytest.fixture
def client():
    with httpx.Client(base_url=BASE_URL, timeout=15.0) as c:
        yield c


def test_tc_m04_273_default_50(client):
    run_id = _new_run_id()
    try:
        token = _login(client, run_id)
        r = client.get(
            "/prediccion/auditoria",
            headers=_auth(token, run_id),
        )
        assert r.status_code == 200, f"GET: {r.status_code}: {r.text[:300]}"
        body = r.json()
        assert body["por_pagina"] == 50, (
            f"Default por_pagina esperado 50; obtenido {body['por_pagina']}"
        )
        assert body["pagina"] == 1, (
            f"Default pagina esperado 1; obtenido {body['pagina']}"
        )
        assert body["total"] >= 50, (
            f"total={body['total']} insuficiente para validar paginación 50"
        )
        assert len(body["items"]) == min(50, body["total"]), (
            f"len(items)={len(body['items'])} != min(50, total={body['total']})"
        )
    finally:
        _teardown(client, run_id)


def test_tc_m04_274_max_200(client):
    run_id = _new_run_id()
    try:
        token = _login(client, run_id)
        r = client.get(
            "/prediccion/auditoria",
            params={"por_pagina": 200},
            headers=_auth(token, run_id),
        )
        assert r.status_code == 200, f"GET: {r.status_code}: {r.text[:300]}"
        body = r.json()
        assert body["por_pagina"] == 200, (
            f"por_pagina esperado 200; obtenido {body['por_pagina']}"
        )
        assert body["pagina"] == 1
        assert body["total"] >= 200, (
            f"total={body['total']} insuficiente para validar paginación 200"
        )
        assert len(body["items"]) == min(200, body["total"]), (
            f"len(items)={len(body['items'])} != min(200, total={body['total']})"
        )
    finally:
        _teardown(client, run_id)


def test_tc_m04_275_max_excedido_201(client):
    declares_422 = _openapi_declares_422(client)
    run_id = _new_run_id()
    try:
        token = _login(client, run_id)
        r = client.get(
            "/prediccion/auditoria",
            params={"por_pagina": 201},
            headers=_auth(token, run_id),
        )
        if declares_422:
            assert r.status_code == 422, (
                f"OpenAPI declara 422 para por_pagina>200; backend "
                f"devolvió {r.status_code}. INC a M04 (HTTP_COM). "
                f"Body: {r.text[:300]}"
            )
            cuerpo = r.json()
            # formato estandar del backend (error_code/message/fields); "detail" es el crudo de Pydantic/FastAPI
            detail = cuerpo.get("detail") or cuerpo.get("fields") or []
            assert len(detail) > 0, f"422 sin detalle de validacion (ni detail ni fields): {r.text[:300]}"
        else:
            assert r.status_code == 400, (
                f"Backend devolvió {r.status_code}; esperado 400 según "
                f"patrón real (B5). Body: {r.text[:300]}"
            )
            body = r.json()
            assert body.get("error_code") == "VAL_ENTRADA", (
                f"error_code esperado VAL_ENTRADA; obtenido "
                f"{body.get('error_code')}"
            )
    finally:
        _teardown(client, run_id)
