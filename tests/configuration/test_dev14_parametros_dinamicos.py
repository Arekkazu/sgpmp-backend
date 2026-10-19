from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock
import uuid

import pytest

from src.configuration.domain.entities.parametro_mlops import (
    RF57_CONFIANZA, RF72_VENTANA, ParametroMLOps, calidad_configurada, numero_configurado,
)
from src.configuration.application.use_cases.configuracion_global.configurar_parametros_mlops_use_case import ConfigurarParametrosMLOpsUseCase
from src.prediction.application.use_cases.retroalimentacion.registrar_retroalimentacion_use_case import RegistrarRetroalimentacionUseCase
from src.prediction.infrastructure.dto.registrar_retroalimentacion_dto import RegistrarRetroalimentacionDTO
from src.shared.errors import BusinessRuleError, ServiceUnavailableError, ValidationError
from src.telemetry.application.use_cases.alertas.generar_alerta_use_case import GenararAlertaUseCase
from src.telemetry.application.use_cases.calidad.evaluar_calidad_telemetria_use_case import EvaluarCalidadTelemetriaUseCase
from src.telemetry.infrastructure.adapters.parametros_alertas_mlops_adapter import ParametrosAlertasMLOpsAdapter
from src.telemetry.infrastructure.adapters.parametros_calidad_mlops_adapter import ParametrosCalidadMLOpsAdapter
from src.telemetry.infrastructure.dto.procesar_evento_alerta_dto import ProcesarEventoAlertaDTO


def configuracion(**cambios):
    valores = dict(rf62_k=3, rf62_m=3, rf62_n=6, rf62_umbral_drift=5, rf62_p=3,
                   umbral_confianza_edge_ia=.85, ventana_retroalimentacion_dias=30)
    return {k: ParametroMLOps(k,v) for k,v in (valores | cambios).items()}


def repositorio(valores):
    repo = Mock()
    repo.obtener.side_effect = lambda nombres: {n: valores[n] for n in nombres if n in valores}
    return repo


def calidad_use_case(db, repo, configuracion_repo=None, serie=None):
    parametros = ParametrosCalidadMLOpsAdapter(repo, configuracion_repo or SimpleNamespace(
        obtener_activo=lambda: SimpleNamespace(frecuencia_muestreo=SimpleNamespace(valor=7))))
    telemetria = Mock()
    datos = serie or [Decimal(str(v)) for v in (19,20,21,22,23,24)]
    telemetria.obtener_serie_temporal.side_effect = lambda sensor,n,ts: datos[:n]
    calidad = Mock()
    calidad.guardar.side_effect = lambda evaluacion: evaluacion
    return EvaluarCalidadTelemetriaUseCase(db,telemetria,calidad,parametros)


def evaluar(uc, *, valor=Decimal(25), calibracion=None):
    return uc.execute(1,7,9,valor,valor,datetime.now(timezone.utc),'LECTURA_VALIDA',calibracion)


def alerta_use_case(db, repo):
    alertas = Mock()
    alertas.buscar_activa_duplicada.return_value = None
    def guardar(alerta):
        alerta.id_alerta = 1
        return alerta
    alertas.guardar.side_effect = guardar
    return GenararAlertaUseCase(db,alertas,Mock(),Mock(),ParametrosAlertasMLOpsAdapter(repo))


def evento_alerta(**cambios):
    return ProcesarEventoAlertaDTO(**(dict(device_id=3,sensor_id=7,access_key='credencial-test',
        tipo_variable='NH3',valor=25,unidad='ppm',timestamp_evento=datetime.now(timezone.utc),
        estado_dato='LECTURA_VALIDA',severidad_edge='LEVE',origen_evento='EDGE',
        tipo_alerta_ia='ESTRES_TERMICO',severidad_ia='CRITICO',probabilidad_ia='.88') | cambios))


def retro_use_case(db, repo):
    resultados = Mock()
    resultados.obtener_por_id.return_value = dict(fecha_inferencia=datetime.now(timezone.utc)-timedelta(days=20),id_activo_biologico=11)
    salidas = Mock()
    salidas.obtener_por_resultado_y_usuario.return_value = None
    salidas.listar_por_resultado.return_value = []
    def guardar(entidad):
        entidad.id_retroalimentacion=uuid.uuid4()
        return entidad
    salidas.guardar.side_effect=guardar
    return RegistrarRetroalimentacionUseCase(db=db,repo=salidas,resultado_port=resultados,
        patologia_repo=Mock(),auditoria_repo=Mock(),parametros_port=repo)


def retro_dto():
    return RegistrarRetroalimentacionDTO(id_resultado_inferencia=uuid.uuid4(),id_activo_biologico=11,estado_retroalimentacion='CORRECTO')


@pytest.mark.parametrize('valor',[True,False,None,'3',{},[],float('nan'),float('inf'),-1,0])
def test_k_invalido_no_activa_constante_de_respaldo(valor):
    with pytest.raises(ServiceUnavailableError): calidad_configurada(configuracion(rf62_k=valor))


@pytest.mark.parametrize('cambios',[{'rf62_m':1.5},{'rf62_n':1},{'rf62_p':0},{'rf62_m':7},{'rf62_p':7},{'rf62_umbral_drift':-1}])
def test_ventanas_y_porcentaje_invalidos_se_rechazan(cambios):
    with pytest.raises(ServiceUnavailableError): calidad_configurada(configuracion(**cambios))


def test_parametro_ausente_no_usa_valor_por_defecto():
    with pytest.raises(ServiceUnavailableError) as error: numero_configurado({},RF72_VENTANA,entero=True)
    assert error.value.code=='PARAMETRO_CONFIGURACION_AUSENTE'


def test_rango_persistido_no_amplia_limites_funcionales():
    datos={RF57_CONFIANZA:ParametroMLOps(RF57_CONFIANZA,.96,Decimal(0),Decimal(1))}
    with pytest.raises(ServiceUnavailableError): numero_configurado(datos,RF57_CONFIANZA,minimo='.70',maximo='.95')


@pytest.mark.parametrize('parametro,inicial,posterior,serie,calibracion,flag',[
    ('rf62_k',1,4,[19,20,21,22,23,24],None,'outlier_estadistico'),
    ('rf62_m',3,4,[20,20,20,21,22,23],None,'sensor_congelado'),
    ('rf62_umbral_drift',5,20,[20,20.5,21,21.5,22,22.5],{'ganancia':1.2,'offset':0},'posible_drift'),
    ('rf62_p',3,6,[20,20.5,21,21.5,22,22.5],{'ganancia':1.05,'offset':0},'posible_drift'),
])
def test_parametro_modifica_calculo_mismo_consumidor(parametro,inicial,posterior,serie,calibracion,flag):
    datos=configuracion(**{parametro:inicial})
    if parametro=='rf62_p': datos['rf62_umbral_drift']=ParametroMLOps('rf62_umbral_drift',1)
    uc=calidad_use_case(Mock(),repositorio(datos),serie=[Decimal(str(v)) for v in serie])
    assert evaluar(uc,calibracion=calibracion).flags_detectados[flag]['activo']
    datos[parametro]=ParametroMLOps(parametro,posterior)
    assert flag not in evaluar(uc,calibracion=calibracion).flags_detectados


def test_n_modifica_suficiencia_de_serie_sin_recrear_use_case():
    datos=configuracion(rf62_n=5)
    uc=calidad_use_case(Mock(),repositorio(datos))
    assert evaluar(uc).clasificacion_calidad.value!='INDETERMINADA'
    datos['rf62_n']=ParametroMLOps('rf62_n',8)
    assert evaluar(uc).clasificacion_calidad.value=='INDETERMINADA'


def test_confianza_modifica_tipo_y_compromiso_sin_cambiar_bandas_de_severidad():
    datos=configuracion(umbral_confianza_edge_ia=.80)
    uc=alerta_use_case(Mock(),repositorio(datos))
    primero=uc.execute(evento_alerta())
    datos[RF57_CONFIANZA]=ParametroMLOps(RF57_CONFIANZA,.90)
    segundo=uc.execute(evento_alerta())
    assert primero.tipo_alerta=='ESTRES_TERMICO' and primero.severidad=='CRITICO'
    assert segundo.tipo_alerta=='SINDROME_RESPIRATORIO' and segundo.severidad=='MODERADO'


def test_sin_ia_no_se_consume_un_umbral_que_no_interviene():
    repo=repositorio({})
    uc=alerta_use_case(Mock(),repo)
    assert uc.execute(evento_alerta(probabilidad_ia=None,severidad_ia=None)).severidad=='LEVE'
    repo.obtener.assert_not_called()


def test_ventana_rf72_modifica_aceptacion_en_el_mismo_consumidor():
    datos=configuracion(ventana_retroalimentacion_dias=30)
    uc=retro_use_case(Mock(),repositorio(datos))
    assert uc.execute(retro_dto(),4).id_retroalimentacion
    datos[RF72_VENTANA]=ParametroMLOps(RF72_VENTANA,7)
    with pytest.raises(BusinessRuleError) as error: uc.execute(retro_dto(),4)
    assert error.value.code=='FUERA_DE_VENTANA_TEMPORAL'


def test_carga_invalida_revierte_sin_escribir():
    repo=repositorio(configuracion())
    db=Mock()
    with pytest.raises(ValidationError): ConfigurarParametrosMLOpsUseCase(db,repo).execute({'rf62_p':20},1)
    repo.guardar.assert_not_called()
    db.commit.assert_not_called()
    db.rollback.assert_called_once()


def test_sin_conflicto_ia_no_se_consume_un_umbral_innecesario():
    repo=repositorio({})
    uc=alerta_use_case(Mock(),repo)
    resultado=uc.execute(evento_alerta(tipo_alerta_ia='SINDROME_RESPIRATORIO',severidad_ia='LEVE'))
    assert resultado.tipo_alerta=='SINDROME_RESPIRATORIO'
    repo.obtener.assert_not_called()


def test_falta_configuracion_m09_no_se_reemplaza_por_cinco_minutos():
    adapter=ParametrosCalidadMLOpsAdapter(repositorio(configuracion()),SimpleNamespace(obtener_activo=lambda:None))
    with pytest.raises(ServiceUnavailableError) as error: adapter.obtener_parametros(7)
    assert error.value.code=='CONFIGURACION_OPERATIVA_AUSENTE'


@pytest.mark.parametrize('frecuencia',[0,True,-1,1.5])
def test_muestreo_persistido_invalido_se_rechaza(frecuencia):
    adapter=ParametrosCalidadMLOpsAdapter(repositorio(configuracion()),SimpleNamespace(
        obtener_activo=lambda:SimpleNamespace(frecuencia_muestreo=SimpleNamespace(valor=frecuencia))))
    with pytest.raises(ServiceUnavailableError): adapter.obtener_parametros(7)


@pytest.mark.parametrize('actualizar',[False,True])
@pytest.mark.parametrize('campos',[{'heartbeat':14},{'umbral_sin_senal':14},{'heartbeat':14,'umbral_sin_senal':'14'}])
def test_rf18_acepta_nombre_canonico_y_alias_sin_duplicar_valor(actualizar,campos):
    from src.configuration.infrastructure.dto.crear_configuracion_dto import CrearConfiguracionDTO
    from src.configuration.infrastructure.dto.actualizar_configuracion_dto import ActualizarConfiguracionDTO
    clase=ActualizarConfiguracionDTO if actualizar else CrearConfiguracionDTO
    entrada={'frecuencia_muestreo':7}|campos
    if actualizar: entrada['fecha_actualizacion']=datetime.now(timezone.utc)
    assert clase(**entrada).heartbeat==14


def test_rf18_rechaza_aliases_con_valores_distintos():
    from pydantic import ValidationError as PydanticError
    from src.configuration.infrastructure.dto.crear_configuracion_dto import CrearConfiguracionDTO
    with pytest.raises(PydanticError): CrearConfiguracionDTO(frecuencia_muestreo=7,heartbeat=14,umbral_sin_senal=20)


def test_rf18_respuesta_mantiene_alias_y_publica_nombre_canonico():
    from src.configuration.infrastructure.schema.configuracion_global_schema import ConfiguracionGlobalResponse
    response=ConfiguracionGlobalResponse(id_configuracion_global=1,frecuencia_muestreo=7,heartbeat=14,
        fecha_actualizacion=datetime.now(timezone.utc),id_usuario=1,es_activo=True).model_dump()
    assert response['heartbeat']==response['umbral_sin_senal']==14


def test_evento_edge_conserva_generacion_de_alerta_con_nueva_dependencia(monkeypatch):
    from src.telemetry.application.use_cases.inferencia import recibir_evento_edge_use_case as modulo
    from src.telemetry.infrastructure.dto.recibir_evento_edge_dto import RecibirEventoEdgeDTO

    alertas = Mock()
    alertas.buscar_activa_duplicada.return_value = None
    def guardar_alerta(entidad):
        entidad.id_alerta = 42
        return entidad
    alertas.guardar.side_effect = guardar_alerta
    monkeypatch.setattr(modulo, 'SqlAlchemyAlertaRepository', lambda db: alertas)
    monkeypatch.setattr(modulo, 'SqlAlchemyHistoricoEstadoAlertaRepository', lambda db: Mock())
    monkeypatch.setattr(modulo, 'SqlAlchemyReglaAlertaRepository', lambda db: Mock())
    # La entrega RF-56 es otra frontera; no se simula una confirmación a IA.
    consolidar = Mock()
    consolidar.execute.return_value = None
    monkeypatch.setattr(modulo, 'ConsolidarEnviarPaqueteUseCase', lambda **kwargs: consolidar)
    eventos = Mock()
    def guardar_evento(entidad):
        entidad.id_evento_edge_computing = 12
        return entidad
    eventos.guardar.side_effect = guardar_evento
    dispositivos = Mock()
    dispositivos.obtener_dispositivo_activo.return_value = SimpleNamespace(
        id_dispositivo_iot=3, id_sensor=7, id_infraestructura=9)
    parametros = Mock()
    uc = modulo.RecibirEventoEdgeUseCase(Mock(), eventos, Mock(), dispositivos, Mock(), parametros)
    ahora = datetime.now(timezone.utc)
    dto = RecibirEventoEdgeDTO(device_id=3, sensor_id=7, access_key='credencial-test',
        clasificacion_rf55='DESVIACION_SIMPLE', severidad='LEVE',
        variables_involucradas=[{'tipo_variable':'NH3','valor':25,'unidad':'ppm'}],
        timestamp_captura=ahora, timestamp_procesamiento_edge=ahora, estado_conectividad=True)

    resultado = uc.execute(dto)

    assert resultado.id_evento_edge_computing == 12
    alertas.guardar.assert_called_once()
    alerta = alertas.guardar.call_args.args[0]
    assert (alerta.tipo_alerta, alerta.severidad) == ('SINDROME_RESPIRATORIO', 'LEVE')
    parametros.obtener_confianza_edge_ia.assert_not_called()
