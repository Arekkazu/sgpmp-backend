"""
TC-M01-024 - Respuesta HTTP 503 cuando el servicio de identidad o la
base de datos no responde tras 3 reintentos internos.

RF relacionado: RF-02
Categoria: Manejo de errores (RESILIENCIA)

Criterio de aceptacion (segun la ficha, flujo alterno "Indisponibilidad
del servicio de identidad"):
    "El motor de base de datos... no responde tras 3 intentos internos.
    El sistema responde con HTTP 503: Service Unavailable."

Este archivo prueba ese criterio en dos niveles:

1. test_get_db_reintenta_3_veces_y_traduce_a_service_unavailable
   Nivel unitario: simula que SessionLocal() falla siempre y verifica
   directamente sobre get_db() que (a) se reintenta 3 veces y (b) el
   error final es un ServiceUnavailableError (503), no la excepcion
   cruda de SQLAlchemy.

2. test_endpoint_login_responde_503_cuando_bd_no_disponible
   Nivel de integracion (in-process, sin red): monta el router real de
   /sesiones con los error handlers reales de la app y confirma que un
   POST /sesiones/ con la BD caida efectivamente devuelve HTTP 503 al
   cliente, que es lo que la ficha exige en terminos de contrato HTTP.

Estado conocido al momento de escribir este archivo: `get_db()` en
src/shared/database.py NO implementa reintentos ni traduce el fallo a
ServiceUnavailableError (a diferencia de src/shared/email.py, que si
tiene _MAX_RETRIES=3). Por lo tanto se espera que AMBAS pruebas FALLEN
hoy, documentando honestamente que TC-M01-024 esta REPROBADO: la
excepcion cruda de SQLAlchemy queda sin manejar y el endpoint responde
500 (no controlado), no 503. Esto debe reportarse como hallazgo
(INC-M01-02-xxx), no interpretarse como un error de la prueba.

Por que local y no contra el backend TEST desplegado: simular una BD
caida contra ese entorno exigiria o bien detener el contenedor de
Postgres (acceso de infraestructura que el equipo de QA no tiene), o
bien agotar max_connections desde el usuario de BD de pruebas, lo cual
tumbaria la BD compartida para cualquier otra persona probando en ese
momento (frontend, Postman, otros pytest). Como get_db() es exactamente
el mismo codigo que corre en el backend desplegado, parchear
SessionLocal en local prueba el comportamiento real sin ese riesgo:
no se abre ninguna conexion de red ni a Postgres real.

Requiere la variable de entorno DATABASE_URL (por el import de
src.shared.database, que crea el engine de SQLAlchemy al importarse).
Cualquier valor con formato de URL de PostgreSQL sirve: no se abre
conexion real, SessionLocal queda parcheado en cada test.

Como correrlo (desde la raiz del repo):

    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    python -m pytest <ruta>\\test_tc_m01_024_reintentos_bd.py -v \
        --html=reporte-TC-M01-024.html --self-contained-html
"""
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from src.shared.database import get_db
from src.shared.errors import ServiceUnavailableError


class TestTCM01024ReintentosBD:
    """Suite de pruebas para TC-M01-024."""

    @patch("src.shared.database.SessionLocal")
    def test_get_db_reintenta_3_veces_y_traduce_a_service_unavailable(
        self, mock_session_local
    ):
        """
        RF-02: ante un fallo de conexion, get_db() debe reintentar 3 veces
        y, si los 3 fallan, lanzar ServiceUnavailableError (503) en vez de
        la excepcion cruda de SQLAlchemy.
        """
        mock_session_local.side_effect = OperationalError(
            "conexion rechazada (simulada)", None, None
        )

        generador = get_db()
        try:
            next(generador)
            excepcion_lanzada = None
        except Exception as exc:
            excepcion_lanzada = exc

        assert excepcion_lanzada is not None, (
            "Se esperaba que get_db() lanzara una excepcion ante el fallo "
            "de conexion simulado, pero no lanzo ninguna."
        )
        assert mock_session_local.call_count == 3, (
            f"RF-02 exige 3 intentos internos de conexion antes de fallar; "
            f"get_db() intento conectar {mock_session_local.call_count} "
            f"vez/veces."
        )
        assert isinstance(excepcion_lanzada, ServiceUnavailableError), (
            f"RF-02 exige que, agotados los reintentos, se lance "
            f"ServiceUnavailableError (mapeado a HTTP 503) en vez de la "
            f"excepcion cruda de infraestructura. Se obtuvo: "
            f"{type(excepcion_lanzada).__name__}: {excepcion_lanzada}"
        )
        assert getattr(excepcion_lanzada, "status_code", None) == 503

    @patch("src.shared.database.SessionLocal")
    def test_endpoint_login_responde_503_cuando_bd_no_disponible(
        self, mock_session_local
    ):
        """
        RF-02: un POST /sesiones/ con la BD caida debe devolver HTTP 503
        con un mensaje claro, no un error no controlado.
        """
        from src.identity_access.infrastructure.routers.sesiones_routers import (
            router as sesiones_router,
        )
        from src.shared.error_handlers import register_error_handlers

        mock_session_local.side_effect = OperationalError(
            "conexion rechazada (simulada)", None, None
        )

        app = FastAPI()
        register_error_handlers(app)
        app.include_router(sesiones_router)
        # raise_server_exceptions=False: que devuelva la respuesta HTTP
        # real (como la veria un cliente contra un servidor desplegado)
        # en vez de relanzar la excepcion en el proceso de la prueba.
        client = TestClient(app, raise_server_exceptions=False)

        response = client.post(
            "/sesiones/",
            json={
                "correo_electronico": "usuario.prueba@ejemplo.com",
                "contrasena": "cualquiera",
            },
        )

        assert response.status_code == 503, (
            f"RF-02 exige HTTP 503 cuando la BD no responde tras 3 "
            f"reintentos internos; el endpoint respondio "
            f"{response.status_code}. Cuerpo: {response.text}"
        )
