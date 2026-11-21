"""RF-62 DEV-02: aptitud oficial y límites transaccionales de la evaluación."""
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import Mock
from uuid import uuid4

import pytest

from src.telemetry.application.use_cases.calidad.evaluar_calidad_telemetria_use_case import EvaluarCalidadTelemetriaUseCase
from src.telemetry.domain.entities.telemetria_calidad import EstadoEvaluacion
from src.telemetry.domain.repositories.parametros_calidad_port import ParametrosCalidad
from src.telemetry.domain.repositories.telemetria_calidad_repository import TelemetriaCalidadRepository
from src.telemetry.domain.repositories.telemetria_repository import TelemetriaRepository


def _escenario(serie):
    db = Mock()
    lecturas = Mock(spec=TelemetriaRepository)
    lecturas.obtener_serie_temporal.return_value = [Decimal(str(v)) for v in serie]
    calidad = Mock(spec=TelemetriaCalidadRepository)
    calidad.obtener_por_lectura.return_value = None

    def guardar(evaluacion):
        evaluacion.id_evaluacion = uuid4()
        return evaluacion

    calidad.guardar.side_effect = guardar
    parametros = Mock()
    parametros.obtener_parametros.return_value = ParametrosCalidad(
        k=3.0, M=5, N=20, umbral_drift=5.0, umbral_drift_significativo=10.0,
        P=3, frecuencia_muestreo_min=5,
    )
    caso = EvaluarCalidadTelemetriaUseCase(db, lecturas, calidad, parametros)
    datos = dict(
        id_telemetria=21, id_sensor=6, id_variable=9, valor=Decimal("22.5"),
        valor_ajustado=Decimal("22.5"), timestamp_captura=datetime.now(timezone.utc),
        estado_calidad_rf53="LECTURA_VALIDA", parametros_calibracion={"ganancia": 1, "offset": 0},
    )
    return caso, db, lecturas, calidad, datos


@pytest.mark.parametrize("serie,cambios,indice,clasificacion,ia,nic41", [
    pytest.param([22, 23] * 10, {}, 100, "APTO", True, True, id="apto-20-previas"),
    pytest.param([22, 23] * 10, {"valor": Decimal("30"), "parametros_calibracion": {"ganancia": 1, "offset": 1.5}},
                 70, "APTO_CON_RESERVA", True, False, id="reserva"),
    pytest.param([25] * 20, {"valor": Decimal("25")}, 10, "NO_APTO", False, False, id="congelado"),
    pytest.param([22, 23] * 9, {}, None, "INDETERMINADA", False, False, id="serie-insuficiente"),
    pytest.param([], {"estado_calidad_rf53": "FUERA_DE_RANGO"}, 0, "NO_APTO", False, False, id="fuera-de-rango"),
    pytest.param([22, 23] * 10, {"estado_calidad_rf53": "ERROR_CALIBRACION", "parametros_calibracion": None},
                 100, "APTO", True, True, id="sin-calibracion-conserva-reglas"),
])
def test_todas_las_ramas_persisten_y_confirman_calidad(serie, cambios, indice, clasificacion, ia, nic41):
    caso, db, lecturas, calidad, datos = _escenario(serie)
    evaluacion = caso.execute(**{**datos, **cambios})
    assert evaluacion.id_evaluacion is not None
    assert evaluacion.indice_calidad == indice
    assert evaluacion.clasificacion_calidad == clasificacion
    assert (evaluacion.apto_para_ia, evaluacion.apto_para_nic41) == (ia, nic41)
    calidad.guardar.assert_called_once_with(evaluacion)
    db.commit.assert_called_once()
    db.rollback.assert_not_called()
    assert not hasattr(lecturas, "actualizar_flags_aptitud")


def test_sustitucion_conserva_referencia_y_ocurre_antes_del_commit():
    caso, db, _lecturas, calidad, datos = _escenario([22, 23] * 10)
    anterior = Mock(id_evaluacion=uuid4(), estado_evaluacion=EstadoEvaluacion.VIGENTE)
    calidad.obtener_por_lectura.return_value = anterior
    operaciones = Mock()
    operaciones.attach_mock(calidad.guardar, "guardar")
    operaciones.attach_mock(calidad.marcar_superada, "superar")
    operaciones.attach_mock(db.commit, "commit")
    evaluacion = caso.execute(**datos)
    assert evaluacion.id_evaluacion_superada == anterior.id_evaluacion
    assert [llamada[0] for llamada in operaciones.mock_calls] == ["guardar", "superar", "commit"]
    assert calidad.marcar_superada.call_args.args == (anterior.id_evaluacion,)


@pytest.mark.parametrize("fase", ["guardar", "superar", "commit"])
def test_error_revierte_la_transaccion_y_se_propaga(fase):
    caso, db, _lecturas, calidad, datos = _escenario([22, 23] * 10)
    calidad.obtener_por_lectura.return_value = Mock(id_evaluacion=uuid4())
    destino = {"guardar": calidad.guardar, "superar": calidad.marcar_superada, "commit": db.commit}[fase]
    destino.side_effect = RuntimeError("fallo controlado de persistencia")
    with pytest.raises(RuntimeError, match="fallo controlado"):
        caso.execute(**datos)
    db.rollback.assert_called_once()
    if fase != "commit":
        db.commit.assert_not_called()


def test_auditoria_fallida_no_revierte_la_evaluacion_confirmada():
    caso, db, _lecturas, calidad, datos = _escenario([22, 23] * 10)
    caso.auditoria_repo = Mock()
    caso.auditoria_repo.registrar.side_effect = RuntimeError("fallo de auditoria")
    evaluacion = caso.execute(**datos)
    assert evaluacion.id_evaluacion is not None
    calidad.guardar.assert_called_once()
    db.commit.assert_called_once()
    db.rollback.assert_called_once()  # Solo revierte el intento posterior de auditoría.
