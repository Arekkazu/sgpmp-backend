"""
TC-M01-024 - Respuesta HTTP 503 cuando el servicio de identidad o la
base de datos no responde tras 3 reintentos internos.

RF relacionado: RF-02
Categoria: Manejo de errores (RESILIENCIA)

IMPORTANTE - Resultado esperado de este test:
Segun src/shared/database.py, la funcion get_db() NO implementa ningun
mecanismo de reintentos (a diferencia de src/shared/email.py, que si
tiene un _MAX_RETRIES=3 explicito). get_db() simplemente instancia
SessionLocal() sin try/except ni bucle.

Por lo tanto, se espera que este test demuestre que:
1. Ante un fallo de conexion, NO hay 3 reintentos (el conteo real sera 1).
2. El error que se propaga es la excepcion cruda de SQLAlchemy
   (OperationalError), NO un ServiceUnavailableError controlado con
   codigo 503.

Si estas dos aserciones "de defecto documentado" SI pasan, significa
que TC-M01-024 esta REPROBADO tal como esta implementado el codigo hoy:
el comportamiento descrito en la ficha (3 reintentos, luego 503) no
existe en get_db(). Esto habria que reportarlo como hallazgo, no
como un error de la prueba.

Como correrlo:
    pytest test_tc_m01_024_reintentos_bd.py -v \
        --html=reporte-TC-M01-024.html --self-contained-html
"""
from unittest.mock import patch

import pytest
from sqlalchemy.exc import OperationalError

from src.shared.database import get_db
from src.shared.errors import ServiceUnavailableError


class TestTCM01024ReintentosBD:
    """Suite de pruebas para el (inexistente, segun el codigo) mecanismo
    de reintentos de conexion a base de datos."""

    @patch("src.shared.database.SessionLocal")
    def test_documenta_que_no_hay_reintentos_ante_fallo_de_conexion(
        self, mock_session_local
    ):
        """
        Simula que SessionLocal() falla siempre (BD caida). Documenta
        cuantas veces se intenta conectar en la practica.

        Resultado esperado segun la ficha: 3 intentos.
        Resultado real observado en el codigo actual: 1 intento
        (no hay reintentos implementados).
        """
        mock_session_local.side_effect = OperationalError(
            "conexion rechazada (simulada)", None, None
        )

        generador = get_db()

        with pytest.raises(OperationalError):
            next(generador)

        assert mock_session_local.call_count == 1, (
            f"Se esperaban 3 reintentos segun TC-M01-024, pero el codigo "
            f"actual de get_db() solo intento conectar "
            f"{mock_session_local.call_count} vez/veces. No hay logica de "
            f"reintentos implementada en src/shared/database.py."
        )

    @patch("src.shared.database.SessionLocal")
    def test_el_error_propagado_no_es_un_503_controlado(self, mock_session_local):
        """
        Documenta que el error que sale de get_db() es la excepcion CRUDA
        de SQLAlchemy, no un ServiceUnavailableError (que es el que el
        proyecto usa para mapear a HTTP 503 segun la jerarquia de errores
        del CLAUDE.md).
        """
        mock_session_local.side_effect = OperationalError(
            "conexion rechazada (simulada)", None, None
        )

        generador = get_db()

        with pytest.raises(OperationalError) as exc_info:
            next(generador)

        # Si esto pasa, confirma que NO se esta traduciendo a
        # ServiceUnavailableError/503 en ningun punto de get_db().
        assert isinstance(exc_info.value, OperationalError)
        assert not isinstance(exc_info.value, ServiceUnavailableError), (
            "Se esperaba que el error NO fuera un ServiceUnavailableError "
            "controlado (el que el proyecto usa para mapear a HTTP 503), "
            "sino la excepcion cruda de SQLAlchemy. Si esta asercion falla, "
            "significa que SI existe una traduccion a 503 en algun punto "
            "(buena noticia, pero contradice lo observado en el codigo)."
        )

    def test_get_db_no_tiene_bloque_try_except_para_la_conexion_inicial(self):
        """
        Verificacion de codigo fuente: confirma via inspeccion que
        get_db() no envuelve la creacion de la sesion en un manejo
        de errores propio.
        """
        import inspect

        from src.shared import database

        codigo_fuente = inspect.getsource(database.get_db)
        assert "except" not in codigo_fuente.split("db = SessionLocal()")[0], (
            "Se esperaba NO encontrar manejo de errores antes de "
            "'db = SessionLocal()', confirmando ausencia de reintentos "
            "o captura de fallos de conexion."
        )