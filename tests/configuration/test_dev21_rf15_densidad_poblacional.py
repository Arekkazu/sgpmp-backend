# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-20 | Arekkazu | DEV-21 RF-15: alias densidad_poblacional_max, 2 decimales y reducción que deja áreas excedidas |
"""DEV-21 (RFC-012, P-4): la densidad se expone como ``densidad_poblacional_max`` con el
nombre anterior como alias deprecado, y no se baja por debajo de lo alojado."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest
from pydantic import ValidationError as PydanticValidationError

from src.configuration.application.use_cases.especies.editar_especie_use_case import EditarEspecieUseCase
from src.configuration.domain.entities.especie import Especie
from src.configuration.domain.services.capacidad_area import AreaOcupada, EspecieDelArea
from src.configuration.domain.value_objects.nombre_especie import NombreEspecie
from src.configuration.infrastructure.dto.editar_especie_dto import EditarEspecieDTO
from src.configuration.infrastructure.dto.registrar_especie_dto import RegistrarEspecieDTO
from src.configuration.infrastructure.schema.especie_schema import EspecieResponse
from src.shared.errors import BusinessRuleError

TS = datetime(2026, 10, 1, tzinfo=timezone.utc)


def _dto(**kw):
    return RegistrarEspecieDTO(nombre="Cachama", grupo_manejo="ACUICULTURA", **kw)


@pytest.mark.parametrize("campo", ["densidad_poblacional_max", "densidad_maxima_por_especie"])
def test_acepta_el_nombre_de_la_ficha_y_el_anterior(campo):
    assert _dto(**{campo: "80.5"}).densidad_maxima_por_especie == Decimal("80.5")


def test_los_dos_nombres_juntos_deben_coincidir():
    assert _dto(densidad_poblacional_max="80", densidad_maxima_por_especie="80.00").densidad_maxima_por_especie == 80
    with pytest.raises(PydanticValidationError, match="deben coincidir"):
        _dto(densidad_poblacional_max="80", densidad_maxima_por_especie="81")


@pytest.mark.parametrize("valor, mensaje", [("80.123", "2 decimales"), ("0", "mayor a cero"), ("-1", "mayor a cero")])
def test_valores_invalidos(valor, mensaje):
    with pytest.raises(PydanticValidationError, match=mensaje):
        _dto(densidad_poblacional_max=valor)


def test_el_esquema_de_entrada_publica_el_nombre_de_la_ficha():
    assert "densidad_poblacional_max" in RegistrarEspecieDTO.model_json_schema()["properties"]


def test_la_respuesta_trae_los_dos_nombres():
    especie = Especie(id_especie=1, nombre=NombreEspecie("Cachama"), es_activo=True,
                      densidad_maxima_por_especie=Decimal("80"), fecha_creacion=TS)
    r = EspecieResponse.model_validate(especie)
    assert r.densidad_poblacional_max == r.densidad_maxima_por_especie == Decimal("80")


# ── reducción ────────────────────────────────────────────────────────────────

class _Db:
    def commit(self): pass
    def rollback(self): pass


class _Repo:
    def __init__(self, especie, areas): self.especie, self.areas, self.consultas = especie, areas, 0
    def obtener_por_id(self, _id, **_): return self.especie
    def obtener_por_nombre(self, _n): return self.especie
    def listar_areas_ocupadas(self, _id):
        self.consultas += 1
        return self.areas
    def actualizar(self, e): return e


class _Auditoria:
    def registrar(self, **_): pass


def _editar(actual, nueva, areas):
    especie = Especie(id_especie=1, nombre=NombreEspecie("Salmon"), es_activo=True, grupo_manejo="ACUICULTURA",
                      densidad_maxima_por_especie=None if actual is None else Decimal(actual), fecha_actualizacion=TS)
    repo = _Repo(especie, areas)
    dto = EditarEspecieDTO(nombre="Salmon", fecha_actualizacion=TS, densidad_poblacional_max=nueva)
    return EditarEspecieUseCase(_Db(), repo, _Auditoria()).execute(1, dto, SimpleNamespace(id_usuario=1)), repo


def _estanque(carga, otra_densidad="100"):
    return AreaOcupada(nombre="Estanque 1", superficie=Decimal("50"), carga=carga, especies=[
        EspecieDelArea(1, "Salmon", "ACUICULTURA", Decimal("100")),
        EspecieDelArea(2, "Cachama", "ACUICULTURA", None if otra_densidad is None else Decimal(otra_densidad)),
    ])


def test_bajar_la_densidad_que_deja_un_area_excedida_es_422():
    with pytest.raises(BusinessRuleError) as e:
        _editar("100", "80", [_estanque(4001)])  # techo 5000 → 4000
    assert e.value.code == "DENSIDAD_DEJA_AREA_EXCEDIDA" and e.value.status_code == 422
    assert "'Estanque 1'" in e.value.message and "4001 individuos" in e.value.message and "4000" in e.value.message


def test_bajar_la_densidad_que_todavia_cabe_se_guarda():
    especie, _ = _editar("100", "80", [_estanque(4000)])
    assert especie.densidad_maxima_por_especie == Decimal("80")


def test_definirla_por_primera_vez_tambien_se_valida():
    with pytest.raises(BusinessRuleError):
        _editar(None, "10", [_estanque(501)])


def test_area_con_otra_especie_sin_densidad_no_se_evalua():
    especie, _ = _editar("100", "1", [_estanque(4001, otra_densidad=None)])
    assert especie.densidad_maxima_por_especie == Decimal("1")


@pytest.mark.parametrize("actual, nueva", [("80", "100"), ("80", None)], ids=["subir", "quitar"])
def test_subir_o_quitar_la_densidad_no_consulta_areas(actual, nueva):
    _, repo = _editar(actual, nueva, [_estanque(10 ** 6)])
    assert repo.consultas == 0
