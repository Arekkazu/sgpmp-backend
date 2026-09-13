"""Pruebas de las cabeceras de seguridad HTTP (INC-M02-56-G04).

Un escaneo pasivo de OWASP ZAP sobre las 197 rutas documentadas del API
confirmó que ninguna respuesta traía X-Content-Type-Options, X-Frame-Options,
Content-Security-Policy ni Strict-Transport-Security.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.shared.middlewares import SecurityHeadersMiddleware


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.add_middleware(SecurityHeadersMiddleware)

    @app.get("/usuarios/me")
    def ruta_api():
        return {"ok": True}

    @app.get("/docs")
    def docs_falso():
        return {"swagger": "ui"}

    return TestClient(app)


def test_toda_respuesta_trae_las_cabeceras_basicas(client: TestClient) -> None:
    respuesta = client.get("/usuarios/me")

    assert respuesta.headers["X-Content-Type-Options"] == "nosniff"
    assert respuesta.headers["X-Frame-Options"] == "DENY"
    assert respuesta.headers["Strict-Transport-Security"] == "max-age=63072000; includeSubDomains"


def test_las_rutas_del_api_llevan_csp_estricta(client: TestClient) -> None:
    respuesta = client.get("/usuarios/me")

    assert respuesta.headers["Content-Security-Policy"] == "default-src 'none'"


def test_docs_no_lleva_csp_estricta_para_no_romper_swagger_ui(client: TestClient) -> None:
    respuesta = client.get("/docs")

    assert "Content-Security-Policy" not in respuesta.headers
    # El resto de cabeceras sí aplican en /docs.
    assert respuesta.headers["X-Content-Type-Options"] == "nosniff"
