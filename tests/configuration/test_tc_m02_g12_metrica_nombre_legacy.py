"""TC-M02-G12 (issue #324) — GET /configuracion/metricas?id_especie=4 fallaba
al reconstruir métricas ya persistidas cuyo nombre (p. ej. 'peso_destete')
predata la regex de NombreMetrica (que no permitía '_'). Además, `_a_entidad`
construía TipoMedicion/AplicaTipoActivo/TipoDatoAtributo con el constructor
crudo del enum en vez de `.desde_string(...)`, así que cualquier valor legacy
no mapeado habría producido un ValueError sin controlar (500) en vez de un
ValidationError (400) -- afectando también a POST /activos-biologicos por la
via de _validar_atributos_dinamicos si esa especie tuviera datos legacy.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import pytest

from src.configuration.domain.value_objects.nombre_metrica import NombreMetrica
from src.configuration.infrastructure.repositories.metrica_produccion_repository import (
    SqlAlchemyMetricaProduccionRepository,
)
from src.shared.errors import ValidationError


def test_nombre_metrica_acepta_guion_bajo():
    # 'peso_destete' es el dato real que rompia el GET -- ya no debe rechazarse.
    assert NombreMetrica('peso_destete').valor == 'peso_destete'


@dataclass
class _OrmFake:
    id_metrica_produccion: int = 15
    nombre: str = 'peso_destete'
    unidad_medida: str = 'kg'
    tipo_medicion: str = 'PESO'
    aplica_a_tipo_activo: str = 'AMBOS'
    tipo_dato: str = 'NUMERICO'
    es_obligatorio: bool = True
    id_especie: int = 4
    es_activo: bool = True
    fecha_actualizacion: datetime = datetime(2026, 1, 1, tzinfo=timezone.utc)


def test_a_entidad_reconstruye_dato_legacy_con_guion_bajo():
    entidad = SqlAlchemyMetricaProduccionRepository._a_entidad(_OrmFake())
    assert entidad.nombre.valor == 'peso_destete'


def test_a_entidad_valor_legacy_no_mapeado_da_validation_error_no_500():
    # Simula un valor de enum legacy que ya no existe en el set actual --
    # antes: ValueError sin controlar (500). Ahora: ValidationError (400).
    orm = _OrmFake(tipo_medicion='CATEGORIA_VIEJA_YA_NO_EXISTE')
    with pytest.raises(ValidationError) as exc:
        SqlAlchemyMetricaProduccionRepository._a_entidad(orm)
    assert exc.value.code == 'TIPO_MEDICION_INVALIDO'
