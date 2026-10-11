"""RF-15 / INC-M09-62-G03 (#231): una especie recién creada tiene
``fecha_actualizacion`` NULL. El DTO la exigía no nula, así que el cliente
mandaba su propia hora y la concurrencia optimista respondía 412 en la
primera edición de cualquier especie.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.configuration.application.use_cases.especies.editar_especie_use_case import (
    EditarEspecieUseCase,
)
from src.configuration.domain.entities.especie import Especie
from src.configuration.domain.value_objects.nombre_especie import NombreEspecie
from src.configuration.infrastructure.dto.editar_especie_dto import EditarEspecieDTO
from src.shared.errors import PreconditionFailedError
from tests.configuration.test_rf36_densidad_maxima_especie import (
    AuditoriaFake,
    DbFake,
    EspecieRepoFake,
    _usuario,
)


def _especie(fecha_actualizacion: datetime | None) -> Especie:
    return Especie(
        id_especie=4,
        nombre=NombreEspecie('Equino'),
        descripcion=None,
        densidad_maxima_por_especie=None,
        es_activo=True,
        fecha_creacion=datetime(2026, 10, 1, tzinfo=timezone.utc),
        fecha_actualizacion=fecha_actualizacion,
    )


def _editar(especie: Especie, fecha_dto: datetime | None) -> Especie:
    caso_uso = EditarEspecieUseCase(DbFake(), EspecieRepoFake(especie), AuditoriaFake())
    return caso_uso.execute(
        4, EditarEspecieDTO(nombre='Equino', descripcion='Editada', fecha_actualizacion=fecha_dto), _usuario()
    )


def test_dto_acepta_fecha_actualizacion_null() -> None:
    assert EditarEspecieDTO(nombre='Equino', fecha_actualizacion=None).fecha_actualizacion is None


def test_primera_edicion_de_especie_nunca_editada_responde_ok() -> None:
    actualizada = _editar(_especie(None), None)

    assert actualizada.descripcion == 'Editada'
    assert actualizada.fecha_actualizacion is not None


def test_null_sobre_especie_ya_editada_sigue_siendo_conflicto() -> None:
    with pytest.raises(PreconditionFailedError):
        _editar(_especie(datetime(2026, 10, 4, tzinfo=timezone.utc)), None)


def test_hora_del_cliente_sobre_especie_nunca_editada_sigue_siendo_conflicto() -> None:
    with pytest.raises(PreconditionFailedError):
        _editar(_especie(None), datetime.now(timezone.utc))
