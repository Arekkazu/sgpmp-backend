# | Fecha      | Nombre  | Que se hizo |
# |------------|---------|-------------|
# | 2026-10-22 | Leandro | DEV-42 RF-60: prueba reloj, bateria y transiciones |
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src.shared.errors import BusinessRuleError
from src.telemetry.application.use_cases.infraestructura.recibir_heartbeat_use_case import ProcesarHeartbeatPersistidoUseCase
from src.telemetry.application.use_cases.alertas.actualizar_estado_alerta_use_case import ActualizarEstadoAlertaUseCase
from src.telemetry.domain.entities.alerta import Alerta
from src.telemetry.domain.entities.estado_dispositivo_iot import EstadoDispositivoIoT
from src.telemetry.domain.repositories.parametros_heartbeat_port import ParametrosComunicacionHeartbeat, ParametrosHeartbeat
from src.telemetry.infrastructure.dto.heartbeat_dto import HeartbeatDTO


def estado(origen):
    return EstadoDispositivoIoT(1, 1, origen, None, None, None, None, None, datetime.now(timezone.utc), None)


@pytest.mark.parametrize('origen,destino,permitida', [
    ('INACTIVO','EN_MANTENIMIENTO',True),('EN_MANTENIMIENTO','ACTIVO',True),
    ('ACTIVO','EN_MANTENIMIENTO',False),('SIN_SEÑAL','ACTIVO',False),
    ('INACTIVO','ACTIVO',False),('EN_MANTENIMIENTO','INACTIVO',False),
    ('BUFFER_ACTIVO','EN_MANTENIMIENTO',False),('ACTIVO','ACTIVO',False),
])
def test_transiciones_manuales_no_alteran_automaticas(origen,destino,permitida):
    e = estado(origen)
    if permitida:
        e.validar_transicion_manual(destino)
    else:
        with pytest.raises(BusinessRuleError) as error:
            e.validar_transicion_manual(destino)
        assert error.value.code == 'TRANSICION_INVALIDA'
    assert e.estado_actual == origen


@pytest.mark.parametrize('hb,tele,primera,esperado', [
    (241,1,600,True),(240,1,600,False),(239,1,600,False),
    (500,601,600,False),(None,1,241,True),(None,1,240,False),
    (None,None,None,False),(500,-5,600,False),
])
def test_heartbeat_ausente_respeta_dos_intervalos_y_telemetria_reciente(hb,tele,primera,esperado):
    ahora = datetime.now(timezone.utc)
    instante = lambda segundos: ahora-timedelta(seconds=segundos) if segundos is not None else None
    p = ParametrosComunicacionHeartbeat(120,600,300,3600,None,
        instante(tele),instante(hb),instante(primera))
    assert p.heartbeat_ausente(ahora) is esperado


def servicio():
    alertas, parametros = Mock(), Mock()
    alertas.buscar_tecnica_activa_dispositivo.return_value = None
    parametros.obtener.return_value = ParametrosHeartbeat(Decimal(10),Decimal(30),Decimal(-100),Decimal(-10))
    return ProcesarHeartbeatPersistidoUseCase(Mock(),alertas,parametros,Mock()), alertas


def heartbeat(bateria=None):
    ahora = datetime.now(timezone.utc)
    return SimpleNamespace(id_heartbeat=1,id_dispositivo_iot=1,nivel_bateria_pct=bateria,
        calidad_senal_rssi=None,calidad_senal_snr=None,fecha_registro=ahora,fecha_recepcion=ahora)


@pytest.mark.parametrize('bateria,causa', [(None,None),(31,None),(30,'BATERIA_BAJA'),
    (10,'BATERIA_CRITICA'),(Decimal('5.01'),'BATERIA_CRITICA'),(5,'APAGADO_INMINENTE'),(0,'APAGADO_INMINENTE')])
def test_bateria_respeta_limites_y_sin_dato_no_infiere_fallo(bateria,causa):
    uc,r = servicio()
    uc.procesar_alertas(heartbeat(bateria),1)
    assert [c.args[0].tipo_variable for c in r.guardar.call_args_list] == ([causa] if causa else [])


def test_escalamiento_reutiliza_id_y_no_incrementa_por_reintento():
    uc,r = servicio()
    previa = SimpleNamespace(id_alerta=7,tipo_variable='BATERIA_BAJA',metadato_evento=None)
    r.buscar_tecnica_activa_dispositivo.side_effect = lambda device,causa: previa if causa=='BATERIA_BAJA' else None
    uc.procesar_alertas(heartbeat(5),1)
    r.guardar.assert_not_called()
    assert r.escalar_bateria.call_args.args[:3] == (7,'APAGADO_INMINENTE','CRITICO')
    r.actualizar_deduplicacion.assert_not_called()


def test_timestamp_futuro_conserva_diagnostico_sin_necesitar_bateria():
    uc,r = servicio()
    h = heartbeat()
    h.fecha_registro += timedelta(hours=1)
    uc.procesar_alertas(h,1)
    a = r.guardar.call_args.args[0]
    assert a.tipo_variable == 'DESINCRONIZACION_RELOJ'
    assert a.metadato_evento['reloj_desincronizado'] is True
    assert a.fecha_evento == h.fecha_recepcion


@pytest.mark.parametrize('causa', ['BATERIA_BAJA','APAGADO_INMINENTE','SOBRECALENTAMIENTO',
    'FIRMWARE_DESACTUALIZADO','DESINCRONIZACION_RELOJ'])
def test_recuperacion_no_cierra_condiciones_independientes(causa):
    repo = Mock()
    a = Alerta('TECNICA','LEVE','ACTIVA','HEARTBEAT',causa,datetime.now(timezone.utc),datetime.now(timezone.utc))
    ActualizarEstadoAlertaUseCase.resolver_conectividad(a,repo,datetime.now(timezone.utc))
    repo.actualizar_estado.assert_not_called()


@pytest.mark.parametrize('cambio', [{'fecha_registro':'2026-10-21T10:00:00'}, {'estado_local_buffer':'Z'}])
def test_dto_rechaza_tiempo_sin_zona_y_buffer_desconocido(cambio):
    from pydantic import ValidationError
    datos = dict(device_id=1,serial='TEST',tipo_mensaje='HEARTBEAT',fecha_registro=datetime.now(timezone.utc).isoformat())
    datos.update(cambio)
    with pytest.raises(ValidationError):
        HeartbeatDTO(**datos)


def test_transicion_automatica_no_hereda_actor_manual():
    e=estado('ACTIVO')
    e.id_usuario=17
    e.aplicar_transicion('SIN_SEÑAL','FALLO_CONECTIVIDAD',datetime.now(timezone.utc))
    assert e.id_usuario is None
