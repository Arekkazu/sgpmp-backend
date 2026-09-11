"""Pruebas de la red de seguridad global de errores.

Sin estos handlers, un fallo de base de datos a mitad de request escapa a
Starlette y sale como `Internal Server Error` en texto plano, sin `error_code`
ni `timestamp` — con una forma distinta a la del resto de la API, que el
frontend no sabe interpretar (INC-M01-06-024).
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import InterfaceError, OperationalError, ProgrammingError

from src.shared.error_handlers import register_error_handlers

CLAVES_ESPERADAS = {"error_code", "message", "fields", "timestamp"}
SECRETO = "password=superclave host=10.0.0.7"


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/bd-caida")
    def bd_caida():
        raise OperationalError("SELECT 1", {}, Exception(SECRETO))

    @app.get("/bd-desconectada")
    def bd_desconectada():
        raise InterfaceError("SELECT 1", {}, Exception(SECRETO))

    @app.get("/sql-roto")
    def sql_roto():
        raise ProgrammingError("SELECT * FROM no_existe", {}, Exception(SECRETO))

    @app.get("/explota")
    def explota():
        return 1 / 0

    return TestClient(app, raise_server_exceptions=False)


@pytest.mark.parametrize("ruta", ["/bd-caida", "/bd-desconectada"])
def test_fallo_de_conexion_responde_503(client: TestClient, ruta: str) -> None:
    respuesta = client.get(ruta)

    assert respuesta.status_code == 503
    cuerpo = respuesta.json()
    assert cuerpo["error_code"] == "BD_NO_DISPONIBLE"
    assert "temporalmente" in cuerpo["message"]


def test_error_de_sql_responde_500_con_el_formato_estandar(client: TestClient) -> None:
    respuesta = client.get("/sql-roto")

    assert respuesta.status_code == 500
    assert respuesta.json()["error_code"] == "ERROR_INTERNO"


def test_excepcion_cualquiera_responde_500_con_el_formato_estandar(client: TestClient) -> None:
    respuesta = client.get("/explota")

    assert respuesta.status_code == 500
    assert respuesta.json()["error_code"] == "ERROR_INTERNO"


@pytest.mark.parametrize("ruta", ["/bd-caida", "/bd-desconectada", "/sql-roto", "/explota"])
def test_todas_las_respuestas_traen_el_mismo_cuerpo(client: TestClient, ruta: str) -> None:
    cuerpo = client.get(ruta).json()

    assert set(cuerpo) == CLAVES_ESPERADAS
    assert cuerpo["fields"] == []


@pytest.mark.parametrize("ruta", ["/bd-caida", "/bd-desconectada", "/sql-roto"])
def test_no_se_filtran_detalles_de_la_conexion_al_cliente(client: TestClient, ruta: str) -> None:
    texto = client.get(ruta).text

    assert SECRETO not in texto
    assert "password" not in texto
    assert "Traceback" not in texto
