# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-20 | Arekkazu | DEV-25 RF-17: marcar es_critica audita valores anterior y nuevo (RFC-016) |
"""DEV-25 (RFC-016 B.7): marcar una variable ambiental como crítica."""
from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

import pytest

from src.configuration.application.use_cases.umbrales.actualizar_variable_critica_use_case import (
    TIPO_EVENTO_CAMBIO_VARIABLE_CRITICA,
    ActualizarVariableCriticaUseCase,
)
from src.configuration.domain.entities.variable_ambiental import VariableAmbiental
from src.configuration.infrastructure.schema.umbral_schema import VariableAmbientalResponse
from src.shared.errors import NotFoundError


class _Db:
    def __init__(self): self.commits = 0
    def commit(self): self.commits += 1
    def rollback(self): pass


class _Repo:
    def __init__(self, variable): self.variable = variable
    def obtener_por_id(self, _id): return self.variable
    def actualizar(self, v): return v


class _Eventos:
    def __init__(self): self.eventos = []
    def registrar(self, **kw): self.eventos.append(kw)


def _variable(es_critica=False):
    return VariableAmbiental(id_variable_ambiental=3, nombre="Amoniaco", unidad="ppm",
                             valor_fisico_min=Decimal("0"), valor_fisico_max=Decimal("100"),
                             es_activo=True, es_critica=es_critica)


def _uc(variable):
    db, eventos = _Db(), _Eventos()
    return ActualizarVariableCriticaUseCase(db, _Repo(variable), eventos), db, eventos


def test_marcar_como_critica_audita_y_hace_commit():
    uc, db, eventos = _uc(_variable())
    variable = uc.execute(3, True, SimpleNamespace(id_usuario=7))
    assert variable.es_critica and db.commits == 1
    [evento] = eventos.eventos
    assert evento["tipo_evento"] == TIPO_EVENTO_CAMBIO_VARIABLE_CRITICA and evento["id_usuario"] == 7
    assert evento["detalle"]["valores_anteriores"]["es_critica"] is False
    assert evento["detalle"]["valores_nuevos"]["es_critica"] is True
    assert VariableAmbientalResponse.model_validate(variable).es_critica is True


def test_sin_cambio_no_audita_ni_hace_commit():
    uc, db, eventos = _uc(_variable(es_critica=True))
    assert uc.execute(3, True, SimpleNamespace(id_usuario=7)).es_critica
    assert db.commits == 0 and eventos.eventos == []


def test_variable_inexistente_es_404():
    uc, _, _ = _uc(None)
    with pytest.raises(NotFoundError) as e:
        uc.execute(99, True, SimpleNamespace(id_usuario=7))
    assert e.value.code == "VARIABLE_AMBIENTAL_NO_ENCONTRADA"
