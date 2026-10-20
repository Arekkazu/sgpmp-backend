from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from pydantic import ValidationError

from src.shared.errors import ServiceUnavailableError
from src.telemetry.application.use_cases.infraestructura.evaluar_diagnostico_heartbeat_use_case import EvaluarDiagnosticoHeartbeatUseCase
from src.telemetry.application.use_cases.infraestructura.recibir_heartbeat_use_case import RecibirHeartbeatUseCase
from src.telemetry.domain.repositories.diagnostico_heartbeat_port import ComparacionFirmware, UmbralesTemperaturaDispositivo
from src.telemetry.infrastructure.dto.heartbeat_dto import HeartbeatDTO


def entrada(**cambios):
    return dict(device_id=3, serial='SERIAL-TEST', tipo_mensaje='HEARTBEAT', fecha_registro=datetime.now(timezone.utc), **cambios)


def heartbeat(**cambios):
    ahora=datetime.now(timezone.utc)
    return SimpleNamespace(id_heartbeat=12,id_dispositivo_iot=3,tipo_mensaje='HEARTBEAT',fecha_registro=ahora,
        fecha_recepcion=ahora,**(dict(sensores_operativos=None,temperatura_dispositivo=None,version_firmware=None)|cambios))


@pytest.mark.parametrize('campos',[{}, {'sensores_operativos':None}, {'sensores_operativos':[]},
    {'sensores_operativos':[{'sensor':'humedad','operativo':False}]},
    {'temperatura_dispositivo':45.5}, {'temperatura_dispositivo':None},
    {'sensores_operativos':[],'temperatura_dispositivo':Decimal('-12.25')}])
def test_campos_opcionales_validos(campos):
    dto=HeartbeatDTO(**entrada(**campos))
    assert dto.tipo_mensaje=='HEARTBEAT'


@pytest.mark.parametrize('valor',[{},'fallido',[False],[{}],[{'sensor':'x'}],
    [{'sensor':'','operativo':False}],[{'sensor':'  ','operativo':False}],
    [{'sensor':3,'operativo':False}],[{'sensor':'x','operativo':'false'}],
    [{'sensor':'x','operativo':0}],[{'sensor':'x','operativo':None}],
    [{'sensor':'x','operativo':False,'otro':'campo'}]])
def test_sensores_incompatibles_se_rechazan(valor):
    with pytest.raises(ValidationError): HeartbeatDTO(**entrada(sensores_operativos=valor))


@pytest.mark.parametrize('valor',[True,'45.5',{},[],float('nan'),float('inf'),1000,Decimal('45.555')])
def test_temperatura_invalida_o_no_representable_en_db03(valor):
    with pytest.raises(ValidationError): HeartbeatDTO(**entrada(temperatura_dispositivo=valor))


def servicio(politica=None):
    repo=Mock()
    repo.buscar_tecnica_activa_dispositivo.return_value=None
    return EvaluarDiagnosticoHeartbeatUseCase(repo,politica),repo


@pytest.mark.parametrize('sensores',[None,[],[{'sensor':'x','operativo':True}]])
def test_ausencia_o_sensores_operativos_no_generan_fallo(sensores):
    uc,repo=servicio()
    uc.sensores(heartbeat(sensores_operativos=sensores),9)
    repo.guardar.assert_not_called()


def test_sensores_fallidos_se_consolidan_identifican_y_conservan_origen():
    uc,repo=servicio()
    sensores=[{'sensor':'z','operativo':False},{'sensor':'a','operativo':False},{'sensor':'z','operativo':False}]
    uc.sensores(heartbeat(sensores_operativos=sensores),9)
    alerta=repo.guardar.call_args.args[0]
    assert alerta.tipo_variable=='SENSOR_FISICO_FALLIDO' and alerta.id_dispositivo_ioit==3
    assert alerta.metadato_evento=={'id_heartbeat':12,'sensores_fallidos':['a','z']}
    repo.buscar_tecnica_activa_dispositivo.assert_called_once_with(3,'SENSOR_FISICO_FALLIDO',sensores_fallidos=['a','z'])


def test_alerta_equivalente_activa_evade_duplicado():
    uc,repo=servicio()
    repo.buscar_tecnica_activa_dispositivo.return_value=object()
    uc.sensores(heartbeat(sensores_operativos=[{'sensor':'x','operativo':False}]),9)
    repo.guardar.assert_not_called()


@pytest.mark.parametrize('valor,genera,severidad',[(Decimal(39),False,None),(Decimal(40),False,None),
    (Decimal(41),True,'MODERADO'),(Decimal(50),True,'MODERADO'),(Decimal(51),True,'CRITICO')])
def test_temperatura_usa_umbrales_inyectados_sin_inventar_configuracion_real(valor,genera,severidad):
    politica=Mock()
    politica.obtener_umbrales_temperatura.return_value=UmbralesTemperaturaDispositivo(Decimal(40),Decimal(50))
    uc,repo=servicio(politica)
    uc.temperatura(heartbeat(temperatura_dispositivo=valor),9)
    assert repo.guardar.called==genera
    if genera: assert repo.guardar.call_args.args[0].severidad==severidad


def test_cambio_politica_temperatura_afecta_mismo_consumidor():
    politica=Mock()
    politica.obtener_umbrales_temperatura.side_effect=[UmbralesTemperaturaDispositivo(Decimal(40)),UmbralesTemperaturaDispositivo(Decimal(50))]
    uc,repo=servicio(politica)
    uc.temperatura(heartbeat(temperatura_dispositivo=Decimal(45)),9)
    uc.temperatura(heartbeat(temperatura_dispositivo=Decimal(45)),9)
    repo.guardar.assert_called_once()


@pytest.mark.parametrize('anterior',[False,True])
def test_firmware_respeta_comparacion_del_puerto_sin_ordenar_textos(anterior):
    politica=Mock()
    politica.comparar_firmware.return_value=ComparacionFirmware('minima-del-contrato',anterior)
    uc,repo=servicio(politica)
    uc.firmware(heartbeat(version_firmware='version-reportada'),9)
    assert repo.guardar.called==anterior
    politica.comparar_firmware.assert_called_once_with(3,'version-reportada')
    if anterior: assert repo.guardar.call_args.args[0].metadato_evento['version_minima']=='minima-del-contrato'


@pytest.mark.parametrize('metodo,cambios,codigo',[
    ('temperatura',{'temperatura_dispositivo':Decimal(45)},'UMBRAL_SOBRECALENTAMIENTO_NO_DISPONIBLE'),
    ('firmware',{'version_firmware':'pi-test'},'POLITICA_FIRMWARE_NO_DISPONIBLE')])
def test_dependencia_ausente_falla_visible_sin_alerta_ficticia(metodo,cambios,codigo):
    uc,repo=servicio()
    with pytest.raises(ServiceUnavailableError) as e: getattr(uc,metodo)(heartbeat(**cambios),9)
    assert e.value.code==codigo
    repo.guardar.assert_not_called()


def test_campos_ausentes_no_exigen_politica():
    uc,repo=servicio()
    uc.temperatura(heartbeat(),9);uc.firmware(heartbeat(),9)
    repo.guardar.assert_not_called()


def test_error_de_commit_no_confirma_heartbeat():
    db,dispositivos,repo=Mock(),Mock(),Mock()
    dispositivos.validar_dispositivo_heartbeat.return_value=SimpleNamespace(es_activo=True)
    db.commit.side_effect=RuntimeError('fallo persistencia')
    uc=RecibirHeartbeatUseCase(db,dispositivos,repo)
    with pytest.raises(RuntimeError): uc.execute(HeartbeatDTO(**entrada(sensores_operativos=[])))
    assert repo.guardar.call_args.args[0].sensores_operativos==[]
    db.rollback.assert_called_once()
