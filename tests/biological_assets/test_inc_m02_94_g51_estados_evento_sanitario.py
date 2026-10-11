"""INC-M02-94-G51 (#488, RF-41): estados que admiten un evento sanitario.

RF-41 v1.1 (corrección de coherencia 2026-10-02, ratificada para #488): el
seguimiento de un tratamiento se registra sobre un activo EN_TRATAMIENTO o
AISLADO, igual que en RF-39. Solo un activo fuera de operación (INACTIVO,
CERRADO, BAJA) responde 409 ESTADO_NO_PERMITE_EVENTOS. `RegistrarEventoSanitario`
usa este validador compartido (ver test_g35 para el cableado con CERRADO).
"""
from __future__ import annotations

import pytest

from src.biological_assets.application.use_cases.gestion._event_validations import (
    validar_estado_permite_eventos,
)
from src.biological_assets.domain.entities.activo_biologico import ActivoBiologico
from src.biological_assets.domain.value_objects.estado_activo import EstadoActivo
from src.shared.errors import ConflictError


def _activo(estado: EstadoActivo) -> ActivoBiologico:
    return ActivoBiologico(
        id_especie=4,
        tipo='INDIVIDUAL',
        origen_financiero='nacimiento',
        id_infraestructura=1,
        id_estado=estado,
        id_usuario=1,
        id_activo_biologico=746,
    )


@pytest.mark.parametrize('estado', [EstadoActivo.ACTIVO, EstadoActivo.EN_TRATAMIENTO, EstadoActivo.AISLADO])
def test_estados_operativos_admiten_evento_sanitario(estado: EstadoActivo) -> None:
    validar_estado_permite_eventos(_activo(estado))


@pytest.mark.parametrize('estado', [EstadoActivo.INACTIVO, EstadoActivo.CERRADO, EstadoActivo.BAJA])
def test_estados_fuera_de_operacion_responden_409(estado: EstadoActivo) -> None:
    with pytest.raises(ConflictError) as exc:
        validar_estado_permite_eventos(_activo(estado))

    assert exc.value.status_code == 409
    assert exc.value.code == 'ESTADO_NO_PERMITE_EVENTOS'
