# | Fecha      | Nombre   | Que se hizo                                                        |
# |------------|----------|--------------------------------------------------------------------|
# | 2026-10-29 | Arekkazu | INC-M03-82-G192 RF-62: política de visión configurable desde M09   |
"""INC-M03-82-G192 (#843): los 7 parámetros de visión se consultan y cambian sin el script DEV-14."""
from decimal import Decimal
from unittest.mock import Mock

import pytest

from src.configuration.application.use_cases.configuracion_global.politica_vision_use_case import PoliticaVisionUseCase
from src.configuration.domain.entities.parametro_mlops import ParametroMLOps
from src.shared.errors import ValidationError


class _Repo:
    def __init__(self):
        self.filas = {}

    def bloquear_configuracion(self):
        pass

    def obtener(self, nombres):
        return {n: self.filas[n] for n in nombres if n in self.filas}

    def guardar(self, parametros, id_usuario):
        self.filas.update({p.nombre: p for p in parametros})


def test_bd_sin_sembrar_muestra_valores_base_y_el_patch_siembra_los_siete():
    repo = _Repo()
    caso = PoliticaVisionUseCase(Mock(), repo)
    assert {p.fuente for p in caso.consultar()} == {"VALOR_BASE"}
    caso.actualizar({"umbral_optima": 85}, id_usuario=1)
    assert set(repo.filas) == {"w1", "w2", "w3", "tracks_perdidos_tolerables",
                               "umbral_optima", "umbral_degradada", "factor_en_calibracion"}
    assert Decimal(str(repo.filas["umbral_optima"].valor)) == 85


@pytest.mark.parametrize("cambios", [
    {"w1": 0.5},                                    # w1 + w2 + w3 ≠ 1
    {"umbral_degradada": 90},                       # degradado ≥ óptimo
    {"tracks_perdidos_tolerables": 0},              # fuera de rango
    {"umbral_confianza_edge_ia": 0.8},              # ajeno a RF-62
])
def test_rechaza_politica_invalida_sin_guardar(cambios):
    repo = _Repo()
    with pytest.raises(ValidationError):
        PoliticaVisionUseCase(Mock(), repo).actualizar(cambios, id_usuario=1)
    assert repo.filas == {}


def test_pesos_que_suman_uno_se_aceptan():
    repo = _Repo()
    repo.filas["w1"] = ParametroMLOps("w1", Decimal("0.40"), 0, 1)
    PoliticaVisionUseCase(Mock(), repo).actualizar({"w1": 0.5, "w2": 0.25, "w3": 0.25}, id_usuario=1)
    assert Decimal(str(repo.filas["w1"].valor)) == Decimal("0.5")
