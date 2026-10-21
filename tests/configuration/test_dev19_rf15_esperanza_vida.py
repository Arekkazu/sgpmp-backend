# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-20 | Arekkazu | DEV-19 RF-15: esperanza_vida_dias en registro, edición y auditoría (RFC-014) |
"""DEV-19 (RFC-014): la especie tiene una esperanza de vida opcional en días (> 0)."""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from pydantic import ValidationError as PydanticValidationError

from src.configuration.application.use_cases.especies.editar_especie_use_case import EditarEspecieUseCase
from src.configuration.application.use_cases.especies.registrar_especie_use_case import RegistrarEspecieUseCase
from src.configuration.domain.entities.especie import Especie
from src.configuration.domain.value_objects.nombre_especie import NombreEspecie
from src.configuration.infrastructure.dto.editar_especie_dto import EditarEspecieDTO
from src.configuration.infrastructure.dto.registrar_especie_dto import RegistrarEspecieDTO
from src.configuration.infrastructure.schema.especie_schema import EspecieResponse

USUARIO = SimpleNamespace(id_usuario=1)
TS = datetime(2026, 10, 1, tzinfo=timezone.utc)


class _Db:
    def commit(self): pass
    def rollback(self): pass


class _Auditoria:
    def __init__(self): self.registros = []
    def registrar(self, **kw): self.registros.append(kw)


class _Repo:
    def __init__(self, especie=None): self.especie = especie
    def obtener_por_nombre(self, _n): return None
    def obtener_por_id(self, _id, **_): return self.especie
    def guardar(self, e):
        e.id_especie = 9
        return e
    def actualizar(self, e): return e


def _existente(esperanza=365):
    return Especie(id_especie=9, nombre=NombreEspecie("Cachama"), es_activo=True, grupo_manejo="ACUICULTURA",
                   esperanza_vida_dias=esperanza, fecha_creacion=TS, fecha_actualizacion=TS)


@pytest.mark.parametrize("valor", [730, None])
def test_registrar_con_y_sin_esperanza_de_vida(valor):
    auditoria = _Auditoria()
    extra = {} if valor is None else {"esperanza_vida_dias": valor}
    dto = RegistrarEspecieDTO(nombre="Cachama", grupo_manejo="ACUICULTURA", **extra)
    especie = RegistrarEspecieUseCase(_Db(), _Repo(), auditoria).execute(dto, USUARIO)
    assert especie.esperanza_vida_dias == valor
    assert auditoria.registros[0]["valores_nuevos"]["esperanza_vida_dias"] == valor
    assert EspecieResponse.model_validate(especie).esperanza_vida_dias == valor


def _editar(**cambio):
    auditoria = _Auditoria()
    dto = EditarEspecieDTO(nombre="Cachama", fecha_actualizacion=TS, **cambio)
    especie = EditarEspecieUseCase(_Db(), _Repo(_existente()), auditoria).execute(9, dto, USUARIO)
    return especie, auditoria.registros[0]


def test_editar_cambia_la_esperanza_y_la_audita():
    especie, registro = _editar(esperanza_vida_dias=500)
    assert especie.esperanza_vida_dias == 500
    assert (registro["valores_anteriores"]["esperanza_vida_dias"], registro["valores_nuevos"]["esperanza_vida_dias"]) == (365, 500)


def test_editar_sin_enviarla_la_conserva_y_con_null_la_borra():
    assert _editar()[0].esperanza_vida_dias == 365
    assert _editar(esperanza_vida_dias=None)[0].esperanza_vida_dias is None


@pytest.mark.parametrize("valor", [0, -1])
@pytest.mark.parametrize("dto", [RegistrarEspecieDTO, EditarEspecieDTO])
def test_cero_o_negativa_se_rechaza(dto, valor):
    with pytest.raises(PydanticValidationError, match="mayor a cero"):
        dto(nombre="Cachama", grupo_manejo="ACUICULTURA", esperanza_vida_dias=valor)
