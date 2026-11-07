# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-10-26 | Leandro | INC-M03-104-G165 RF-62: verificar descuentos compuestos, sigma cero y auditoria de alertas pendientes con dobles. |
"""Regresiones del motor con puertos simulados; no prueban PostgreSQL ni RLS."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest

from src.telemetry.application.use_cases.calidad.evaluar_calidad_telemetria_use_case import EvaluarCalidadTelemetriaUseCase
from src.telemetry.application.use_cases.calidad.generar_alerta_calidad_use_case import GenerarAlertaCalidadUseCase
from src.telemetry.domain.repositories.contexto_calidad_port import ContextoCalidad, LecturaCalidad, LimitesFisicosCalidad
from src.telemetry.domain.repositories.parametros_calidad_port import ParametrosCalidad


def escenario(serie, valor, *, offset=0, gap=10, version_limites=None):
    captura = datetime(2026, 10, 26, 12, tzinfo=timezone.utc)
    lecturas = tuple(LecturaCalidad(i + 1, captura - timedelta(minutes=gap + 10 * i),
                                  Decimal(str(v)), 10) for i, v in enumerate(serie))
    contexto = Mock()
    limites = (LimitesFisicosCalidad(Decimal(0), Decimal(60), version_limites, 'doble_versionado')
               if version_limites else None)
    contexto.obtener.return_value = ContextoCalidad(lecturas, (), 10, limites, lecturas)
    calidad = Mock()
    calidad.obtener_por_lectura.return_value = None

    def guardar(ev):
        ev.id_evaluacion = uuid4()
        return ev

    calidad.guardar.side_effect = guardar
    auditoria = Mock()
    auditoria.registrar.side_effect = lambda _: SimpleNamespace(id_evento=uuid4())
    repo_alertas = Mock()
    repo_alertas.buscar_tecnica_calidad.return_value = None
    repo_alertas.contexto_sensor_calidad.return_value = {'id_dispositivo_iot': 3, 'id_infraestructura': 8}
    params = SimpleNamespace(obtener_parametros=lambda *_: ParametrosCalidad(
        N=20, M=5, k=3, P=5, umbral_drift=5, frecuencia_muestreo_min=10,
        umbral_drift_significativo=10,
    ))
    db = Mock()
    uc = EvaluarCalidadTelemetriaUseCase(
        db, Mock(), calidad, params, auditoria, contexto,
        GenerarAlertaCalidadUseCase(repo_alertas),
    )
    datos = dict(id_telemetria=21, id_sensor=7, id_variable=9, valor=Decimal(str(valor)),
                 valor_ajustado=Decimal(str(valor)) + Decimal(str(offset)), timestamp_captura=captura,
                 estado_calidad_rf53='LECTURA_VALIDA', parametros_calibracion={'ganancia': 1, 'offset': offset})
    return SimpleNamespace(uc=uc, datos=datos, db=db, calidad=calidad, auditoria=auditoria,
                           alertas=repo_alertas)


@pytest.mark.parametrize('serie,valor,offset,gap,indice,clase,flags', [
    pytest.param([19.8, 20.2] * 10, 20, 0, 10, 100, 'APTO', set(), id='base'),
    pytest.param([19.8, 20.2] * 10, 26, 1.5054, 25, 60, 'APTO_CON_RESERVA',
                 {'outlier_estadistico', 'posible_drift', 'gap_temporal_anomalo'}, id='318a'),
    pytest.param([20] * 10 + [19.8, 20.2] * 5, 20, 3.5294, 10, 40, 'APTO_CON_RESERVA',
                 {'sensor_congelado', 'posible_drift'}, id='318b'),
    pytest.param([20] * 20, 26, 0, 10, 0, 'NO_APTO',
                 {'sensor_congelado', 'outlier_estadistico'}, id='318c'),
    pytest.param([20] * 10 + [19.8, 20.2] * 5, 26, 0, 25, 35, 'NO_APTO',
                 {'sensor_congelado', 'outlier_estadistico', 'gap_temporal_anomalo'}, id='320'),
])
def test_escenarios_compuestos_del_reporte(serie, valor, offset, gap, indice, clase, flags):
    s = escenario(serie, valor, offset=offset, gap=gap)
    ev = s.uc.execute(**s.datos)
    assert ev.indice_calidad == indice
    assert ev.clasificacion_calidad.value == clase
    assert (ev.apto_para_ia, ev.apto_para_nic41) == (clase != 'NO_APTO', clase == 'APTO')
    assert {k for k, v in ev.flags_detectados.items() if v.get('activo')} == flags
    if 'posible_drift' in flags:
        drift = ev.flags_detectados['posible_drift']
        assert drift['magnitud_drift_porcentaje'] == pytest.approx(15 if offset > 3 else 7, abs=0.001)
        assert drift['P_lecturas_consistentes'] >= 5
    if 'gap_temporal_anomalo' in flags:
        assert ev.flags_detectados['gap_temporal_anomalo']['gap_real_minutos'] == 25
    json.dumps(ev.flags_detectados, allow_nan=False)
    s.db.commit.assert_called_once()
    s.db.rollback.assert_not_called()


@pytest.mark.parametrize('valor,outlier', [(20, False), (26, True), (14, True)])
def test_sigma_cero_no_divide_por_cero_ni_marca_un_valor_igual(valor, outlier):
    s = escenario([20] * 20, valor)
    ev = s.uc.execute(**s.datos)
    assert ('outlier_estadistico' in ev.flags_detectados) is outlier
    assert ev.indice_calidad == (0 if outlier else 10)
    if outlier:
        evidencia = ev.flags_detectados['outlier_estadistico']
        assert evidencia['media_serie'] == 20
        assert evidencia['desviacion_estandar'] == 0
        assert evidencia['magnitud_desviacion'] is None
        assert evidencia['desviacion_absoluta'] == 6
        assert evidencia['sigma_cero'] is True
        assert evidencia['causa'] == 'ESTADISTICO'
        assert ev.version_limites_fisicos_aplicada is None
    json.dumps(ev.flags_detectados, allow_nan=False)


def test_drift_sin_severidad_se_guarda_con_pendiente_auditable():
    s = escenario([20] * 10 + [19.8, 20.2] * 5, 20, offset=3.5294, version_limites='prueba-v1')
    ev = s.uc.execute(**s.datos)
    assert ev.indice_calidad == 40
    # La alerta MODERADO de congelamiento sí se conserva.
    assert s.alertas.guardar.call_count == 1
    assert s.alertas.guardar.call_args.args[0].metadato_evento['anomalia'] == 'sensor_congelado'
    evento = s.auditoria.registrar.call_args.args[0]
    pendiente = evento.accion_detallada['notificaciones_pendientes'][0]
    assert pendiente['anomalia'] == 'posible_drift'
    assert pendiente['motivo'] == 'SEVERIDAD_DRIFT_NO_CONFIGURADA'
    assert evento.resultado.value == 'PARCIAL'
    assert len(evento.hash_integridad) == 64
    assert s.calidad.guardar.call_count == 1
    s.db.commit.assert_called_once()
    s.db.rollback.assert_not_called()


def test_drift_no_significativo_no_inventa_alerta_pendiente():
    s = escenario([19.8, 20.2] * 10, 20, offset=1.5054, version_limites='prueba-v1')
    ev = s.uc.execute(**s.datos)
    assert ev.flags_detectados['posible_drift']['activo'] is True
    s.alertas.guardar.assert_not_called()
    assert not s.auditoria.registrar.call_args.args[0].accion_detallada.get('notificaciones_pendientes')
    assert s.auditoria.registrar.call_args.args[0].resultado.value == 'EXITOSO'


def test_error_real_de_alerta_sigue_revirtiendo_la_evaluacion():
    s = escenario([20] * 20, 20)
    s.alertas.guardar.side_effect = RuntimeError('fallo real de persistencia simulado')
    with pytest.raises(RuntimeError, match='persistencia'):
        s.uc.execute(**s.datos)
    s.db.rollback.assert_called_once()
    s.db.commit.assert_not_called()
    s.auditoria.registrar.assert_not_called()
