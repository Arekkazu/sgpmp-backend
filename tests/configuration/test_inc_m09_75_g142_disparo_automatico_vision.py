"""INC-M09-75-G142 (#551): el alta de un lote y el cierre de ciclo de M02 disparan la
calibración por visión automática de M09 (RF-24 v2.0, TC-M09-288/289).

Fakes en memoria: los de G138 para M09 y los de los tests de M02.
"""
from datetime import timedelta
from decimal import Decimal

import pytest

from src.biological_assets.application.use_cases.gestion.cerrar_ciclo_use_case import CerrarCicloUseCase
from src.biological_assets.domain.value_objects.estado_activo import EstadoActivo
from src.configuration.application.use_cases.sensores.calibrar_vision_use_case import VENTANA_DISPARO_AUTOMATICO
from src.configuration.domain.value_objects.calibracion_vision import EstadoCalibracionVision, OrigenDisparo
from src.shared.errors import BusinessRuleError
from tests.biological_assets import test_cerrar_ciclo_use_case as cierre
from tests.biological_assets import test_registrar_activo_use_case as alta
from tests.configuration.test_inc_m09_78_g138_calibracion_vision import (
    _T0, _Calibraciones, _Eventos, _LineasBase, _Observaciones, _area, _camara, _obs, _uc,
)

_SERVICIO = 132
_MOMENTO = _T0 + timedelta(days=1)


def _automatico(uc):
    return uc.execute_automatico(2, _MOMENTO, id_usuario_auditoria=_SERVICIO, motivo_disparo="nuevo lote 792")


# ── M09: execute_automatico ──────────────────────────────────────────────────

class _ObservacionesVentana(_Observaciones):
    def listar(self, ids, inicio, fin):
        self.ventana = (inicio, fin)
        return self.obs


def test_disparo_automatico_exitoso_publica_sin_usuario_y_audita_como_servicio():
    lineas, eventos, calibraciones = _LineasBase(), _Eventos(), _Calibraciones()
    uc = _uc(lineas=lineas, eventos=eventos, calibraciones=calibraciones)
    uc.observacion_port = obs = _ObservacionesVentana(_obs())

    cal = _automatico(uc)

    assert cal.estado == EstadoCalibracionVision.EXITOSA
    assert cal.origen_disparo == OrigenDisparo.AUTOMATICO and cal.id_usuario is None
    assert (cal.id_infraestructura, cal.id_especie) == (2, 4) and cal.observaciones == "nuevo lote 792"
    assert obs.ventana == (_MOMENTO - VENTANA_DISPARO_AUTOMATICO, _MOMENTO)
    assert calibraciones.guardadas == [cal]
    assert lineas.vigente.id_calibracion_vision == cal.id_calibracion_vision
    [evento] = eventos.eventos
    assert evento["exitoso"] is True and evento["id_usuario"] == _SERVICIO
    assert evento["detalle"]["origen_disparo"] == "AUTOMATICO"


@pytest.mark.parametrize("area, camaras", [
    (_area(), []),
    (_area(), [_camara(activa=False)]),
    (_area(tipo_modelo_asignado="MODELO_ESPECIES_GRANDES"), [_camara()]),
    (_area(id_especie=None), [_camara()]),
])
def test_area_sin_vision_no_aplica_y_no_deja_rastro(area, camaras):
    calibraciones, eventos = _Calibraciones(), _Eventos()
    uc = _uc(area=area, camaras=camaras, obs=_obs(), eventos=eventos, calibraciones=calibraciones)
    assert _automatico(uc) is None
    assert calibraciones.guardadas == [] and eventos.eventos == []


def test_disparo_automatico_sin_datos_queda_fallida_y_conserva_la_vigente():
    vigente = type("LB", (), dict(id_infraestructura=2, id_especie=4, id_calibracion_vision=1))()
    lineas, eventos, calibraciones = _LineasBase(vigente), _Eventos(), _Calibraciones()
    with pytest.raises(BusinessRuleError) as exc:
        _automatico(_uc(obs=_obs(n=29), lineas=lineas, eventos=eventos, calibraciones=calibraciones))
    assert exc.value.code == "LINEA_BASE_NO_CALCULADA"
    [cal] = calibraciones.guardadas
    assert cal.estado == EstadoCalibracionVision.FALLIDA and cal.origen_disparo == OrigenDisparo.AUTOMATICO
    assert lineas.vigente is vigente
    [evento] = eventos.eventos
    assert evento["id_usuario"] == _SERVICIO and evento["detalle"]["origen_disparo"] == "AUTOMATICO"


# ── M02: los ganchos ─────────────────────────────────────────────────────────

class _Recalibracion:
    def __init__(self): self.solicitudes = []
    def solicitar(self, id_infraestructura, momento, motivo):
        self.solicitudes.append((id_infraestructura, motivo))


def _dto_lote():
    return alta._dto(
        tipo_activo='POBLACIONAL', identificador=None, raza=None, sexo=None, fecha_nacimiento=None,
        cantidad_inicial=10, peso_promedio_inicial=Decimal('2.5'),
    )


def test_alta_de_lote_solicita_recalibracion_y_la_de_individual_no():
    for dto, esperado in ((_dto_lote(), 1), (alta._dto(), 0)):
        recalibracion = _Recalibracion()
        uc = alta._use_case(alta.ActivoRepoFake(), alta.DbFake())
        uc.recalibracion_vision = recalibracion
        activo = uc.execute(dto, alta._usuario())
        assert len(recalibracion.solicitudes) == esperado
        if esperado:
            assert recalibracion.solicitudes[0] == (
                1, f'Disparo automático M02: nuevo lote {activo.id_activo_biologico}'
            )


def test_cierre_de_ciclo_de_lote_solicita_recalibracion():
    activo = cierre._activo(id_estado=EstadoActivo.ACTIVO)
    activo.tipo = 'POBLACIONAL'
    recalibracion = _Recalibracion()
    CerrarCicloUseCase(
        db=cierre.DbFake(), repo=cierre.ActivoRepoFake(activo), evento_repo=cierre.EventoRepoFake(),
        historico_repo=cierre.HistoricoRepoFake(), recalibracion_vision=recalibracion,
    ).execute(10, cierre._dto(), cierre._usuario())
    assert recalibracion.solicitudes == [(1, 'Disparo automático M02: fin de ciclo del lote 10')]


def test_cierre_rechazado_no_solicita_recalibracion():
    activo = cierre._activo(id_estado=EstadoActivo.CERRADO)
    activo.tipo = 'POBLACIONAL'
    recalibracion = _Recalibracion()
    with pytest.raises(Exception):
        CerrarCicloUseCase(
            db=cierre.DbFake(), repo=cierre.ActivoRepoFake(activo), evento_repo=cierre.EventoRepoFake(),
            historico_repo=cierre.HistoricoRepoFake(), recalibracion_vision=recalibracion,
        ).execute(10, cierre._dto(), cierre._usuario())
    assert recalibracion.solicitudes == []
