"""RF-44: el cambio manual de estado no puede fijar CERRADO ni BAJA.

CERRADO y BAJA quedan fuera de ``PATCH /{id}/estado`` (principio de
centralización obligatoria de RF-44): solo se alcanzan vía cierre de ciclo
(RF-38) y registro de baja (RF-45), que aplican sus propias validaciones y
efectos secundarios.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from pydantic import ValidationError

from src.biological_assets.infrastructure.dto.cambiar_estado_dto import CambiarEstadoDTO


def _dto(estado: str, **overrides) -> dict:
    base = {
        'estado_nuevo': estado,
        'fecha_cambio_estado': date.today(),
        'motivo_cambio': 'motivo de prueba',
    }
    base.update(overrides)
    return base


@pytest.mark.parametrize('estado', ['ACTIVO', 'INACTIVO', 'EN_TRATAMIENTO', 'AISLADO'])
def test_acepta_estados_manuales(estado: str) -> None:
    dto = CambiarEstadoDTO(**_dto(estado))
    assert dto.estado_nuevo == estado


@pytest.mark.parametrize('estado', ['CERRADO', 'BAJA'])
def test_rechaza_cerrado_y_baja(estado: str) -> None:
    with pytest.raises(ValidationError):
        CambiarEstadoDTO(**_dto(estado))


def test_mapa_id_estado_nuevo() -> None:
    assert CambiarEstadoDTO(**_dto('INACTIVO')).id_estado_nuevo == 2
    assert CambiarEstadoDTO(**_dto('AISLADO')).id_estado_nuevo == 4


def test_fecha_futura_rechazada() -> None:
    with pytest.raises(ValidationError):
        CambiarEstadoDTO(**_dto('ACTIVO', fecha_cambio_estado=date.today() + timedelta(days=1)))


def test_motivo_vacio_rechazado() -> None:
    with pytest.raises(ValidationError):
        CambiarEstadoDTO(**_dto('ACTIVO', motivo_cambio='   '))
