"""INC-M02-39-G90 v2.0 (issue #351): POST /activos-biologicos/{id}/sensores ya
no acepta tipo_asociacion=AMBIENTAL -- ese caso anida un activo puntual en
lugar de la infraestructura. Debe usarse POST /infraestructuras/{id}/sensores.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.biological_assets.infrastructure.dto.asociar_sensor_activo_dto import AsociarSensorActivoDTO


def test_tipo_asociacion_ambiental_rechazado_por_el_dto():
    with pytest.raises(ValidationError):
        AsociarSensorActivoDTO(
            tipo_activo='INDIVIDUAL',
            tipo_asociacion='AMBIENTAL',
            dispositivo_iot_id=1,
            sensor_id=1,
            id_infraestructura=1,
        )


@pytest.mark.parametrize('tipo_asociacion', ['DIRECTA', 'POBLACIONAL'])
def test_tipos_soportados_siguen_aceptados(tipo_asociacion):
    dto = AsociarSensorActivoDTO(
        tipo_activo='INDIVIDUAL',
        tipo_asociacion=tipo_asociacion,
        dispositivo_iot_id=1,
        sensor_id=1,
        id_infraestructura=1,
    )
    assert dto.tipo_asociacion == tipo_asociacion
