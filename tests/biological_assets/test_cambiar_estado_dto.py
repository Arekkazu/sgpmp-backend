"""RF-44: el DTO del cambio manual de estado solo rechaza lo que no es un estado.

CERRADO/BAJA, fecha futura y motivo vacío son flujos alternos que RF-44
clasifica como 422, así que los rechaza ``CambiarEstadoUseCase`` y no Pydantic
(que saldría como 400). Esos casos viven en ``test_gaps_flujo_alterno_m02.py``.
"""
from __future__ import annotations

from datetime import date

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


@pytest.mark.parametrize('estado', ['ACTIVO', 'INACTIVO', 'EN_TRATAMIENTO', 'AISLADO', 'CERRADO', 'BAJA'])
def test_acepta_los_estados_del_sistema(estado: str) -> None:
    dto = CambiarEstadoDTO(**_dto(estado))
    assert dto.estado_nuevo == estado


def test_rechaza_estado_desconocido() -> None:
    with pytest.raises(ValidationError):
        CambiarEstadoDTO(**_dto('VENDIDO'))


def test_mapa_id_estado_nuevo() -> None:
    assert CambiarEstadoDTO(**_dto('INACTIVO')).id_estado_nuevo == 2
    assert CambiarEstadoDTO(**_dto('AISLADO')).id_estado_nuevo == 4
    assert CambiarEstadoDTO(**_dto('BAJA')).id_estado_nuevo == 6
