# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-23 | Arekkazu | DEV-24 RF-24: una línea base por visión por cada especie del área (RFC-012) |
"""DEV-24 (RFC-012 en RF-24): la línea base por visión ya no lee la especie única del área;
con dos especies se publican dos líneas base del mismo cálculo."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from src.configuration.application.use_cases.sensores.calibrar_vision_use_case import (
    ConsultarCalibracionVisionUseCase,
)
from src.configuration.domain.value_objects.calibracion_vision import EstadoCalibracionVision
from src.shared.errors import BusinessRuleError

_ruta = Path(__file__).with_name("test_inc_m09_78_g138_calibracion_vision.py")
_spec = importlib.util.spec_from_file_location("rf24_vision_base", _ruta)
h = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(h)


class _LineasPorEspecie:
    def __init__(self): self.vigentes = {}
    def obtener_vigente(self, id_area, id_especie): return self.vigentes.get((id_area, id_especie))
    def publicar(self, lb):
        self.vigentes[(lb.id_infraestructura, lb.id_especie)] = lb
        return lb


def _multiespecie():
    return h._area(id_especie=None, id_especies=[9, 4])


def test_area_con_dos_especies_publica_dos_lineas_base():
    lineas, eventos = _LineasPorEspecie(), h._Eventos()
    calibraciones = h._uc(area=_multiespecie(), obs=h._obs(), lineas=lineas, eventos=eventos).execute(
        h._dto(), h._USUARIO)
    assert [c.id_especie for c in calibraciones] == [4, 9]
    assert all(c.estado == EstadoCalibracionVision.EXITOSA for c in calibraciones)
    assert sorted(lineas.vigentes) == [(2, 4), (2, 9)]
    assert lineas.vigentes[(2, 4)].valor == lineas.vigentes[(2, 9)].valor  # mismas observaciones del área
    assert len([e for e in eventos.eventos if e["exitoso"]]) == 2


def test_especie_id_calibra_solo_esa_especie():
    lineas = _LineasPorEspecie()
    [cal] = h._uc(area=_multiespecie(), obs=h._obs(), lineas=lineas).execute(h._dto(especie_id=9), h._USUARIO)
    assert cal.id_especie == 9 and list(lineas.vigentes) == [(2, 9)]


def test_especie_que_no_esta_en_el_area_422():
    with pytest.raises(BusinessRuleError) as exc:
        h._uc(area=_multiespecie(), obs=h._obs()).execute(h._dto(especie_id=77), h._USUARIO)
    assert exc.value.code == "ESPECIE_NO_ALOJADA_EN_AREA"


def test_consulta_de_linea_base_exige_especie_si_el_area_tiene_varias():
    lineas = _LineasPorEspecie()
    h._uc(area=_multiespecie(), obs=h._obs(), lineas=lineas).execute(h._dto(), h._USUARIO)
    consulta = ConsultarCalibracionVisionUseCase(h._Areas(_multiespecie()), h._Calibraciones(), lineas)
    with pytest.raises(BusinessRuleError) as exc:
        consulta.obtener_linea_base_vigente(2)
    assert exc.value.code == "ESPECIE_REQUERIDA"
    assert consulta.obtener_linea_base_vigente(2, especie_id=9).id_especie == 9
