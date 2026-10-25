# | Fecha      | Nombre  | Que se hizo                                      |
# |------------|---------|--------------------------------------------------|
# | 2026-10-21 | Leandro | DEV-43 RF-62: prueba gaps, omision y notificacion tecnica |
"""Dobles explícitos: las versiones V1/V2 no representan el esquema M09 actual."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest

from src.shared.errors import ServiceUnavailableError
from src.telemetry.application.use_cases.calidad.evaluar_calidad_telemetria_use_case import EvaluarCalidadTelemetriaUseCase
from src.telemetry.application.use_cases.calidad.generar_alerta_calidad_use_case import GenerarAlertaCalidadUseCase
from src.telemetry.domain.entities.consistencia_temporal_calidad import detectar_gaps, unir_periodos
from src.telemetry.domain.repositories.contexto_calidad_port import (
    ContextoCalidad, LecturaCalidad, IntervaloInactividad, LimitesFisicosCalidad,
)
from src.telemetry.domain.repositories.parametros_calidad_port import ParametrosCalidad

TS = datetime(2026,10,20,12,tzinfo=timezone.utc)


def muestra(minutos, valor=22, frecuencia=None):
    return LecturaCalidad(int(minutos*100+10000),TS+timedelta(minutes=minutos),Decimal(valor),frecuencia)


@pytest.mark.parametrize('gap,anomalo', [(9,False),(10,False),(10.01,True),(15,True)])
def test_limite_estricto_doble_intervalo(gap,anomalo):
    gaps,_ = detectar_gaps([muestra(-gap)],TS,5,[])
    assert bool(gaps) is anomalo
    if anomalo:
        assert gaps[0]['gap_real_minutos']==pytest.approx(gap)
        assert gaps[0]['umbral_gap_minutos']==10


def test_periodos_consecutivos_y_solapados_se_unen():
    periodos=tuple(IntervaloInactividad(TS+timedelta(minutes=a),TS+timedelta(minutes=b))
                  for a,b in [(-20,-10),(-10,0),(-15,-5)])
    unidos=unir_periodos(periodos,TS)
    gaps,excluidos=detectar_gaps([muestra(-20)],TS,5,unidos)
    assert gaps==[] and len(excluidos)==1


def test_solapamiento_parcial_permanece_explicito():
    with pytest.raises(ServiceUnavailableError,match='parcialmente'):
        detectar_gaps([muestra(-20)],TS,5,[(TS-timedelta(minutes=15),TS-timedelta(minutes=5))])


def test_orden_zona_horaria_y_repetidos():
    filas=[muestra(-5),muestra(-20),muestra(-5)]
    captura=TS.astimezone(timezone(timedelta(hours=-5)))
    gaps,_=detectar_gaps(filas,captura,5,[])
    assert len(gaps)==1 and gaps[0]['gap_real_minutos']==15


def test_primera_lectura_no_inventa_gap():
    assert detectar_gaps([],TS,5,[])==([],[])


def test_frecuencia_persistida_prevalece_sobre_configuracion_actual():
    assert detectar_gaps([muestra(-15,frecuencia=10)],TS,1,[])==([],[])
    gaps,_=detectar_gaps([muestra(-15,frecuencia=5)],TS,30,[])
    assert gaps[0]['gap_esperado_minutos']==5


@pytest.mark.parametrize('frecuencia',[0,-1,None,True,float('nan'),float('inf')])
def test_frecuencia_invalida_no_parece_evaluacion_normal(frecuencia):
    with pytest.raises(ServiceUnavailableError):
        detectar_gaps([muestra(-5)],TS,frecuencia,[])


def escenario(*,periodos=(),limites=None,congelado=False):
    filas=tuple(muestra(-20+i,22 if congelado else 22+i%2) for i in range(20))
    contexto=Mock()
    contexto.obtener.return_value=ContextoCalidad(filas,periodos,5,limites)
    db=Mock(); repo=Mock(); repo.obtener_por_lectura.return_value=None
    def guardar(ev):
        ev.id_evaluacion=uuid4()
        return ev
    repo.guardar.side_effect=guardar
    auditoria=Mock()
    auditoria.registrar.side_effect=lambda e: SimpleNamespace(id_evento=uuid4())
    params=SimpleNamespace(obtener_parametros=lambda *a:ParametrosCalidad())
    alertas=Mock()
    uc=EvaluarCalidadTelemetriaUseCase(db,Mock(),repo,params,auditoria,
                                      contexto_port=contexto,alertas_calidad=alertas)
    datos=dict(id_telemetria=123,id_sensor=7,id_variable=9,valor=Decimal(22),
               valor_ajustado=Decimal(22),timestamp_captura=TS,
               estado_calidad_rf53='LECTURA_VALIDA',parametros_calibracion=None)
    return SimpleNamespace(uc=uc,db=db,repo=repo,auditoria=auditoria,
                           contexto=contexto,alertas=alertas,datos=datos)


def test_omision_es_evento_no_calificacion_inventada():
    s=escenario(periodos=(IntervaloInactividad(TS-timedelta(minutes=30),None),))
    assert s.uc.execute(**s.datos) is None
    s.repo.guardar.assert_not_called();s.alertas.execute.assert_not_called()
    evento=s.auditoria.registrar.call_args.args[0]
    assert evento.tipo_evento=='EVALUACION_OMITIDA_POR_INACTIVIDAD'
    assert evento.accion_detallada['flags']=={}
    assert evento.hash_integridad and len(evento.hash_integridad)==64
    s.db.commit.assert_called_once()


def test_ventana_mixta_no_se_marca_omitida():
    s=escenario(periodos=(IntervaloInactividad(TS-timedelta(minutes=10),TS-timedelta(minutes=5)),))
    ev=s.uc.execute(**s.datos)
    assert ev.clasificacion_calidad.value=='INDETERMINADA'
    assert ev.parametros_aplicados['consistencia_temporal']['lecturas_excluidas_rf60']>0


@pytest.mark.parametrize('version',['V1','V2'])
def test_snapshot_verificado_llega_a_persistencia(version):
    s=escenario(limites=LimitesFisicosCalidad(Decimal(0),Decimal(100),version,'doble_M09_versionado'))
    ev=s.uc.execute(**s.datos)
    assert ev.version_limites_fisicos_aplicada==version
    assert ev.parametros_aplicados['limites_fisicos_aplicados']['maximo']=='100'


def test_snapshot_sin_version_no_se_presenta_como_aplicado():
    s=escenario(limites=LimitesFisicosCalidad(Decimal(0),Decimal(10),None,'modulo9.variables_ambientales'))
    ev=s.uc.execute(**s.datos)
    assert ev.version_limites_fisicos_aplicada is None
    assert ev.parametros_aplicados['limites_fisicos']['aplicados'] is False
    assert 'outlier_estadistico' not in ev.flags_detectados


def test_fallo_alerta_revierte_evaluacion_y_no_emite_exito():
    s=escenario(congelado=True)
    s.alertas.execute.side_effect=RuntimeError('fallo técnico')
    with pytest.raises(RuntimeError,match='fallo técnico'):s.uc.execute(**s.datos)
    s.db.rollback.assert_called_once();s.db.commit.assert_not_called()
    s.auditoria.registrar.assert_not_called()


def test_fallo_evidencia_revierte_evaluacion_y_alerta():
    s=escenario()
    s.auditoria.registrar.return_value=None
    s.auditoria.registrar.side_effect=lambda e:SimpleNamespace(id_evento=None)
    with pytest.raises(ServiceUnavailableError):s.uc.execute(**s.datos)
    s.db.rollback.assert_called_once();s.db.commit.assert_not_called()


def test_auditoria_limites_pendientes_informa_resultado_parcial():
    s=escenario()
    s.uc.execute(**s.datos)
    assert s.auditoria.registrar.call_args.args[0].resultado.value=='PARCIAL'


def test_sin_antecedentes_no_se_infiere_serie_inactiva():
    s=escenario()
    s.contexto.obtener.return_value=ContextoCalidad((),(IntervaloInactividad(TS-timedelta(minutes=30),None),),5)
    ev=s.uc.execute(**s.datos)
    assert ev.clasificacion_calidad.value=='INDETERMINADA'
    assert s.auditoria.registrar.call_args.args[0].tipo_evento=='EVALUACION_CALIDAD_COMPLETADA'


def test_alerta_congelado_escala_sin_incrementar_por_reevaluacion():
    s=escenario(congelado=True);ev=s.uc.execute(**s.datos)
    repo=Mock()
    repo.buscar_tecnica_calidad.return_value=SimpleNamespace(id_alerta=1,estado_alerta='ACTIVA',severidad='LEVE')
    GenerarAlertaCalidadUseCase(repo).execute(ev)
    repo.escalar_calidad.assert_called_once_with(1,'CRITICO')
    repo.guardar.assert_not_called();repo.actualizar_deduplicacion.assert_not_called()


def test_alerta_congelado_reutiliza_tipo_tecnico_y_severidad_del_flag():
    s=escenario(congelado=True);ev=s.uc.execute(**s.datos)
    repo=Mock();repo.buscar_tecnica_calidad.return_value=None
    repo.contexto_sensor_calidad.return_value={'id_dispositivo_iot':3,'id_infraestructura':8}
    GenerarAlertaCalidadUseCase(repo).execute(ev)
    alerta=repo.guardar.call_args.args[0]
    assert alerta.tipo_alerta=='TECNICA' and alerta.severidad=='CRITICO'
    assert alerta.id_sensor==7 and alerta.id_telemetria==123
    assert alerta.tipo_variable=='SENSOR_FISICO_FALLIDO'
    assert alerta.metadato_evento['anomalia']=='sensor_congelado'


def test_alerta_existente_evitar_duplicado_y_frecuencia_artificial():
    s=escenario(congelado=True);ev=s.uc.execute(**s.datos)
    repo=Mock();repo.buscar_tecnica_calidad.return_value=SimpleNamespace(id_alerta=1,estado_alerta='ACTIVA',severidad='CRITICO')
    GenerarAlertaCalidadUseCase(repo).execute(ev)
    repo.guardar.assert_not_called();repo.actualizar_deduplicacion.assert_not_called()


@pytest.mark.parametrize('magnitud,pendiente',[(9,False),(10,False),(11,True)])
def test_drift_significativo_no_inventa_severidad(magnitud,pendiente):
    ev=SimpleNamespace(flags_detectados={'posible_drift':{'activo':True,
                       'magnitud_drift_porcentaje':magnitud}},
                       parametros_aplicados={'umbral_drift_significativo':10})
    repo=Mock();servicio=GenerarAlertaCalidadUseCase(repo)
    if pendiente:
        with pytest.raises(ServiceUnavailableError,match='severidad'):servicio.execute(ev)
    else:servicio.execute(ev)
    repo.guardar.assert_not_called()
