"""Pruebas de INC-M01-06-024: get_db reintenta y traduce el fallo de BD a 503.

Antes de este cambio, una caída de PostgreSQL propagaba el `OperationalError`
crudo y el endpoint respondía `500 Internal Server Error`, dando a entender que
el fallo era de la aplicación. RF-02 exige agotar 3 reintentos internos y
responder `503` con un mensaje claro.
"""
import pytest
from sqlalchemy.exc import InterfaceError, OperationalError

from src.shared import database
from src.shared.database import _MAX_REINTENTOS_CONEXION, _conectar_con_reintentos, get_db
from src.shared.errors import ServiceUnavailableError


class SesionFalsa:
    """Doble de `Session` que falla las primeras `fallos` tomas de conexión."""

    def __init__(self, fallos: int, excepcion=OperationalError):
        self._fallos = fallos
        self._excepcion = excepcion
        self.intentos = 0
        self.rollbacks = 0
        self.cerrada = False

    def connection(self):
        self.intentos += 1
        if self.intentos <= self._fallos:
            raise self._excepcion("SELECT 1", {}, Exception("conexión rechazada"))
        return object()

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.cerrada = True


@pytest.fixture(autouse=True)
def sin_pausa(monkeypatch):
    """Evita que los reintentos duerman de verdad durante las pruebas."""
    monkeypatch.setattr(database, "_PAUSA_REINTENTO", 0)


def test_reintenta_y_conecta_antes_de_agotar_los_intentos() -> None:
    db = SesionFalsa(fallos=2)

    _conectar_con_reintentos(db)

    assert db.intentos == 3
    assert db.rollbacks == 2


def test_agota_tres_intentos_y_lanza_503() -> None:
    db = SesionFalsa(fallos=99)

    with pytest.raises(ServiceUnavailableError) as exc_info:
        _conectar_con_reintentos(db)

    assert db.intentos == _MAX_REINTENTOS_CONEXION == 3
    assert exc_info.value.code == "BD_NO_DISPONIBLE"
    assert exc_info.value.status_code == 503
    assert exc_info.value.original_error is not None


def test_interface_error_tambien_se_reintenta() -> None:
    db = SesionFalsa(fallos=1, excepcion=InterfaceError)

    _conectar_con_reintentos(db)

    assert db.intentos == 2


def test_el_mensaje_no_expone_detalles_internos() -> None:
    db = SesionFalsa(fallos=99)

    with pytest.raises(ServiceUnavailableError) as exc_info:
        _conectar_con_reintentos(db)

    mensaje = exc_info.value.message
    assert "conexión rechazada" not in mensaje
    assert "SELECT 1" not in mensaje
    assert "temporalmente" in mensaje


def test_get_db_entrega_la_sesion_y_la_cierra(monkeypatch) -> None:
    db = SesionFalsa(fallos=0)
    monkeypatch.setattr(database, "SessionLocal", lambda: db)

    generador = get_db()
    assert next(generador) is db

    generador.close()
    assert db.cerrada


def test_get_db_traduce_la_bd_caida_y_cierra_la_sesion(monkeypatch) -> None:
    db = SesionFalsa(fallos=99)
    monkeypatch.setattr(database, "SessionLocal", lambda: db)

    with pytest.raises(ServiceUnavailableError) as exc_info:
        next(get_db())

    assert exc_info.value.code == "BD_NO_DISPONIBLE"
    assert db.cerrada
