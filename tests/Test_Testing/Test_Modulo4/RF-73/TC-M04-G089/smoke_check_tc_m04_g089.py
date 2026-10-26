"""
Smoke check del ambiente TEST para TC-M04-G089 (httpx directo).
Verifica: GET /health, GET /openapi.json, login contra backend desplegado.
NO valida el endpoint GET /prediccion/auditoria (evita contaminación
adicional de HISTORIAL_CONSULTADO).
"""
import os
import uuid

import httpx


BASE_URL = (os.environ.get("BACKEND") or os.environ["TEST_BASE_URL"]).rstrip("/")
ADMIN_EMAIL = "administador.dev@gmail.com"
SANDBOX_SECRET = os.environ["TEST_SANDBOX_SECRET"]


def test_smoke_health_login_teardown():
    run_id = f"pytest-smoke-g089-{uuid.uuid4()}"
    with httpx.Client(base_url=BASE_URL, timeout=15.0) as c:
        r = c.get("/health")
        assert r.status_code == 200, f"Health {r.status_code}: {r.text[:200]}"

        r = c.get("/openapi.json")
        assert r.status_code == 200, f"OpenAPI {r.status_code}"
        paths = r.json().get("paths", {})
        assert "/prediccion/auditoria" in paths, (
            f"Endpoint ausente en OpenAPI: {list(paths.keys())[:5]}"
        )
        assert "/sesiones/" in paths, "Endpoint /sesiones/ ausente en OpenAPI"

        pwd = os.environ.get("TEST_ADMIN_PASSWORD")
        assert pwd, "TEST_ADMIN_PASSWORD no cargada"

        r = c.post(
            "/sesiones/",
            headers={
                "X-Test-Run-Id": run_id,
                "X-Sandbox-Secret": SANDBOX_SECRET,
            },
            json={"correo_electronico": ADMIN_EMAIL, "contrasena": pwd},
        )
        assert r.status_code == 200, (
            f"Login {r.status_code}: {r.text[:300]}"
        )
        body = r.json()
        assert "token" in body, (
            f"Sin token: {list(body.keys())}"
        )
        print(f"[SMOKE_OK] token_len={len(body['token'])}")

        r = c.delete(
            f"/test-control/runs/{run_id}",
            headers={"X-Sandbox-Secret": SANDBOX_SECRET},
        )
        assert r.status_code == 200, (
            f"Teardown {r.status_code}: {r.text[:200]}"
        )
        print("[SMOKE_OK] teardown OK")
