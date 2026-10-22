# | Fecha      | Nombre  | Que se hizo                                      |
# |------------|---------|--------------------------------------------------|
# | 2026-10-21 | Leandro | DEV-41 RF-53/57: prueba clasificacion y etapa critica |
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src.shared.errors import ServiceUnavailableError
from src.telemetry.application.use_cases.alertas.generar_alerta_telemetria_use_case import GenerarAlertaTelemetriaUseCase
from src.telemetry.application.use_cases.alertas.generar_alerta_use_case import GenararAlertaUseCase
from src.telemetry.application.use_cases.monitoreo.reclasificar_semaforo_use_case import ReclasificarSemaforoUseCase
from src.telemetry.domain.repositories.postcommit_port import EtapaPostcommit
from src.telemetry.infrastructure.dto.procesar_evento_alerta_dto import ProcesarEventoAlertaDTO
from src.telemetry.infrastructure.adapters.variable_alerta_m09_adapter import variable_para_alerta


def escenario(valor='40', calidad='LECTURA_VALIDA'):
    lectura = SimpleNamespace(id_telemetria=11,id_sensor=6,id_variable=9,id_dispositivo_iot=3,
        valor_crudo=Decimal(valor),valor_ajustado=Decimal(valor),estado_calidad=calidad,
        timestamp_captura=datetime.now(timezone.utc),unidad_medida='°C',origen='TIEMPO_REAL')
    lecturas = Mock()
    lecturas.obtener_por_id.return_value = lectura
    lecturas.evaluacion_vigente.return_value = {'apto_para_ia':False,'apto_para_nic41':False}
    lecturas.vinculacion.return_value = {'id_activo_biologico':7}
    lecturas.contexto_alerta.return_value = {'variable':{'tipo_variable':'TEMPERATURA_AMBIENTAL'},
        'serial':'PRUEBA-41','id_infraestructura':2,'id_finca':1}
    especie, umbrales = Mock(), Mock()
    especie.obtener_id_especie.return_value = 2
    umbrales.obtener_umbral_vigente.return_value = {'id_umbral_ambiental':4,'version':datetime.now(timezone.utc),
        'niveles':[{'nivel':n,'limite_inferior':Decimal(str(a)),'limite_superior':Decimal(str(b))}
                   for n,a,b in [('normal',20,30),('precaucion',31,35),('critico',36,45)]]}
    clasificador = ReclasificarSemaforoUseCase(Mock(),lecturas,especie,umbrales,Mock())
    generador = Mock()
    generador.execute.return_value = SimpleNamespace(id_alerta=9,es_duplicado=False)
    return GenerarAlertaTelemetriaUseCase(lecturas,clasificador,generador)


@pytest.mark.parametrize('valor,critica', [('20',False),('30',False),('31',False),('35',False),
    ('36',True),('45',True),('46',True),('19',True)])
def test_reutiliza_limites_y_fallback_oficiales_rf17(valor,critica):
    uc = escenario(valor)
    resultado = uc.execute(11)
    assert uc.generador.execute.called is critica
    assert resultado['decision'] == ('CREADA' if critica else 'NO_CRITICA')
    uc.clasificador.db.commit.assert_not_called()
    uc.clasificador.monitoreo_repo.actualizar_estado_semaforo_si_vigente.assert_not_called()


@pytest.mark.parametrize('calidad',['FUERA_DE_RANGO','ERROR_CALIBRACION'])
def test_calidad_excluida_no_consulta_umbral_ni_genera_alerta(calidad):
    uc = escenario(calidad=calidad)
    assert uc.execute(11)['decision']=='EXCLUIDA_POR_CALIDAD'
    uc.clasificador.umbral_port.obtener_umbral_vigente.assert_not_called()
    uc.generador.execute.assert_not_called()


def test_evalua_origen_exacto_no_la_ultima_lectura_ni_el_cache():
    uc = escenario()
    uc.execute(11)
    uc.lecturas.ultima_lectura_valida.assert_not_called()
    assert all(c.args==(11,) for c in uc.lecturas.obtener_por_id.call_args_list)
    uc.clasificador.umbral_port.obtener_umbral_vigente.assert_called_once_with(
        id_variable_ambiental=9,id_especie=2,timestamp=uc.lecturas.obtener_por_id.return_value.timestamp_captura)


def test_aptitud_ia_no_sustituye_calidad_para_alerta_local():
    uc = escenario()
    assert uc.execute(11)['decision']=='CREADA'
    dto = uc.generador.execute.call_args.args[0]
    assert dto.id_telemetria==11 and dto.severidad_edge=='CRITICO' and dto.origen_evento=='BACKEND'
    assert dto.metadata_evento['id_finca']==1
    assert dto.metadata_evento['id_umbral_ambiental']==4
    assert dto.metadata_evento['valor_evaluado']=='40'


@pytest.mark.parametrize('vinculo',[None,{'id_activo_biologico':None}])
def test_contexto_sin_resolver_permanece_pendiente(vinculo):
    uc = escenario()
    uc.lecturas.vinculacion.return_value = vinculo
    with pytest.raises(ServiceUnavailableError) as e:
        uc.execute(11)
    assert e.value.code=='CONTEXTO_ALERTA_PENDIENTE'
    uc.generador.execute.assert_not_called()


def test_sin_evaluacion_vigente_no_hay_exito_falso():
    uc = escenario()
    uc.lecturas.evaluacion_vigente.return_value = None
    with pytest.raises(ServiceUnavailableError):
        uc.execute(11)
    uc.generador.execute.assert_not_called()


def test_sin_umbral_conserva_comportamiento_no_clasificable_rf17():
    uc = escenario()
    uc.clasificador.umbral_port.obtener_umbral_vigente.return_value = None
    assert uc.execute(11)['decision']=='SIN_CLASIFICACION_RF17'
    uc.generador.execute.assert_not_called()


def test_fallo_infraestructura_no_se_convierte_en_normal():
    uc = escenario()
    uc.clasificador.umbral_port.obtener_umbral_vigente.side_effect = RuntimeError('catálogo no disponible')
    with pytest.raises(RuntimeError,match='catálogo'):
        uc.execute(11)
    uc.generador.execute.assert_not_called()


def test_consolidacion_conserva_correlacion_de_lectura_distinta():
    uc = escenario()
    uc.generador.execute.return_value.es_duplicado = True
    resultado = uc.execute(11)
    assert {k:v for k,v in resultado.items() if k!='contexto_rf17'}=={
        'decision':'CONSOLIDADA','id_alerta':9,'id_telemetria':11,'id_variable':9,'estado_semaforo':'ROJO'}
    assert resultado['contexto_rf17']['id_umbral_ambiental']==4


def test_rf57_requiere_calidad_y_clasificacion_y_respeta_orden():
    etapas = list(EtapaPostcommit)
    assert etapas.index(EtapaPostcommit.RF57)>etapas.index(EtapaPostcommit.RF17)
    assert EtapaPostcommit.RF57.requisitos==(EtapaPostcommit.RF17,EtapaPostcommit.RF62)


def dto():
    return ProcesarEventoAlertaDTO(device_id=3,sensor_id=6,serial='PRUEBA-41',tipo_variable='TEMPERATURA_AMBIENTAL',
        valor=40,unidad='°C',timestamp_evento=datetime.now(timezone.utc),estado_dato='LECTURA_VALIDA',
        severidad_edge='CRITICO',origen_evento='BACKEND',id_telemetria=11)


def test_generador_reutilizado_bloquea_condicion_y_delega_historial_al_trigger():
    db, alertas, historico = Mock(), Mock(), Mock()
    alertas.buscar_activa_duplicada.return_value = None
    alertas.guardar.side_effect = lambda alerta: SimpleNamespace(id_alerta=9,tipo_alerta=alerta.tipo_alerta,severidad=alerta.severidad)
    uc = GenararAlertaUseCase(db,alertas,historico,Mock(),Mock())
    assert uc.execute(dto()).id_alerta==9
    alertas.bloquear_condicion.assert_called_once_with(6,'TEMPERATURA_AMBIENTAL')
    alertas.buscar_activa_duplicada.assert_called_once_with(id_sensor=6,tipo_variable='TEMPERATURA_AMBIENTAL',ventana_min=30)
    historico.registrar.assert_not_called()
    db.commit.assert_called_once()


def test_generador_consolida_sin_crear_ni_reinsertar_historial():
    alertas, historico = Mock(), Mock()
    alertas.buscar_activa_duplicada.return_value = SimpleNamespace(id_alerta=9,severidad='LEVE',tipo_alerta='ESTRES_TERMICO')
    resultado = GenararAlertaUseCase(Mock(),alertas,historico,Mock(),Mock()).execute(dto())
    assert resultado.es_duplicado and resultado.id_alerta==9
    assert alertas.actualizar_deduplicacion.call_args.kwargs['nueva_severidad']=='CRITICO'
    alertas.guardar.assert_not_called()
    historico.registrar.assert_not_called()


def catalogo(filas):
    db = Mock()
    db.execute.return_value.scalars.return_value.all.return_value = filas
    return db


def test_codigo_m09_tiene_precedencia_sobre_alias_de_compatibilidad():
    db = catalogo([{'id_variable_ambiental':9,'nombre':'Temperatura Ambiental','unidad':'°C',
        'codigo_telemetria':'TEMPERATURA_CONFIGURADA'}])
    resultado = variable_para_alerta(db,codigo='TEMPERATURA_AMBIENTAL')
    assert resultado['tipo_variable']=='TEMPERATURA_CONFIGURADA'
    assert 'TEMPERATURA_AMBIENTAL' in resultado['aliases']


def test_catalogo_posterior_dev40_no_depende_de_constante_legacy(monkeypatch):
    from src.telemetry.domain.entities import telemetria as contrato
    monkeypatch.delattr(contrato,'CATALOGO_I3P1')
    db = catalogo([{'id_variable_ambiental':123,'nombre':'Variable nueva','unidad':'ppm',
        'codigo_telemetria':'VARIABLE_NUEVA'}])
    assert variable_para_alerta(db,id_variable=123)['tipo_variable']=='VARIABLE_NUEVA'
    assert variable_para_alerta(db,codigo='VARIABLE_NUEVA')['id_variable']==123


def test_catalogo_ambiguo_no_se_elige_silenciosamente():
    db = catalogo([{'id_variable_ambiental':id,'nombre':'Repetida','unidad':'ppm',
        'codigo_telemetria':'REPETIDA'} for id in (100,101)])
    with pytest.raises(ServiceUnavailableError) as error:
        variable_para_alerta(db,codigo='REPETIDA')
    assert error.value.code=='CATALOGO_AMBIGUO'


def test_fallo_catalogo_no_usa_identidad_de_respaldo():
    db = Mock()
    db.execute.side_effect = RuntimeError('fallo de conexión de prueba')
    with pytest.raises(Exception) as error:
        variable_para_alerta(db,id_variable=9)
    assert error.value.code=='ERROR_INTERNO'
