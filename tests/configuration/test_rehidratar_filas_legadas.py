"""#166 / #178: una fila guardada antes de endurecer la regla de formato no
debe tumbar la lectura (los listados respondían 400 VEREDA_REQUERIDO y
SERIAL_FORMATO_INVALIDO). La regla sigue aplicando al escribir."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.configuration.domain.value_objects.serial_dispositivo import SerialDispositivo
from src.configuration.domain.value_objects.ubicacion_finca import UbicacionFinca
from src.configuration.infrastructure.repositories.dispositivo_iot_repository import (
    SqlAlchemyDispositivoIotRepository,
)
from src.shared.errors import ValidationError


def test_finca_sin_vereda_se_lee():
    # Finca #34 de TEST: solo coordenadas, sin departamento/municipio/vereda.
    ubicacion = UbicacionFinca.from_dict({"latitud": 2.9273, "longitud": -75.2819})
    assert ubicacion.vereda == ""
    assert str(ubicacion.latitud) == "2.9273"


def test_finca_valida_se_sigue_normalizando():
    ubicacion = UbicacionFinca.from_dict(
        {"departamento": " Huila ", "municipio": "Neiva", "vereda": "El Caguan", "latitud": 2.9, "longitud": -75.2}
    )
    assert ubicacion.departamento == "Huila"


def test_serial_legado_se_lee():
    orm = SimpleNamespace(
        id_dispositivo_iot=54, serial="' OR '1'='1' -- 1788623493750", descripcion="x",
        id_infraestructura=1, id_tipo_dispositivo=1, es_activo=False, fecha_creacion=None,
    )
    dispositivo = SqlAlchemyDispositivoIotRepository._a_entidad(orm)
    assert dispositivo.serial.valor == orm.serial


def test_la_regla_sigue_aplicando_al_escribir():
    with pytest.raises(ValidationError):
        SerialDispositivo("' OR '1'='1' --")
    with pytest.raises(ValidationError):
        UbicacionFinca(departamento="Huila", municipio="Neiva", vereda="", latitud=0, longitud=0)
