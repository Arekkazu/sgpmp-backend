# | Fecha      | Nombre                   | Que se hizo                                                          |
# |------------|--------------------------|----------------------------------------------------------------------|
# | 2026-10-27 | HulkyZeus                | RF-73 TC-M04-G089: correo admin configurable; 275 acepta fields      |
# | 2026-10-30 | Juan Sebastian Gutierrez | RF-73 TC-M04-G089: D1 asertos estrictos 422 ErrorResponse; D2 cota 0 |
"""
TC-M04-G089 — Límites de paginación en GET /prediccion/auditoria (httpx).
Subcasos: TC-M04-273 (default 50), 274 (max 200), 275 (201 y 0 → rechazo 422).

Diseño (P1'=B / P2=A / P3=A / D1=B / D2=A / D3=A / D4=Si):
- P1'=B: httpx.Client contra $env:BACKEND (backend desplegado).
- P2=A: 1 login + 1 GET + 1 DELETE por test. DEF-04 respetado.
- D1=B: Asertos estrictos del contrato ErrorResponse (HTTP 422, VAL_ENTRADA, fields).
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
    run_id = _new_run_id()
    try:
        token = _login(client, run_id)

        # Cota superior: por_pagina=201 (le=200) -> HTTP 422 ErrorResponse
        r = client.get(
            "/prediccion/auditoria",
            params={"por_pagina": 201},
            headers=_auth(token, run_id),
        )
        assert r.status_code == 422, (
            f"OpenAPI declara 422 para por_pagina=201; backend "
            f"devolvió {r.status_code}. Body: {r.text[:300]}"
        )
        body = r.json()
        assert body.get("error_code") == "VAL_ENTRADA", (
            f"error_code esperado 'VAL_ENTRADA', obtenido {body.get('error_code')}"
        )
        assert "message" in body, "falta 'message' en ErrorResponse"
        assert "fields" in body, "falta 'fields' en ErrorResponse"
        assert isinstance(body["fields"], list), "fields debe ser list"
        assert any(
            f.get("field") == "por_pagina" for f in body["fields"]
        ), f"fields debe contener 'por_pagina': {body['fields']}"

        # Cota inferior: por_pagina=0 (ge=1) -> HTTP 422 ErrorResponse
        r0 = client.get(
            "/prediccion/auditoria",
            params={"por_pagina": 0},
            headers=_auth(token, run_id),
        )
        assert r0.status_code == 422, (
            f"OpenAPI declara 422 para por_pagina=0; backend "
            f"devolvió {r0.status_code}. Body: {r0.text[:300]}"
        )
        body0 = r0.json()
        assert body0.get("error_code") == "VAL_ENTRADA", (
            f"error_code esperado 'VAL_ENTRADA', obtenido {body0.get('error_code')}"
        )
        assert "message" in body0, "falta 'message' en ErrorResponse"
        assert "fields" in body0, "falta 'fields' en ErrorResponse"
        assert isinstance(body0["fields"], list), "fields debe ser list"
        assert any(
            f.get("field") == "por_pagina" for f in body0["fields"]
        ), f"fields debe contener 'por_pagina' para el caso 0: {body0['fields']}"
    finally:
        _teardown(client, run_id)
