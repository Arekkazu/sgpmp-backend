from datetime import datetime, timezone
from unittest.mock import Mock

import pytest

from src.shared.errors import AppError, ServiceUnavailableError
from src.telemetry.application.use_cases.ingesta.ingerir_telemetria_use_case import IngerirTelemetriaUseCase, SincronizarBufferUseCase
from src.telemetry.domain.repositories.ingesta_telemetria_port import ResultadoPersistenciaIngesta
from src.telemetry.infrastructure.dto.ingerir_telemetria_dto import IngerirTelemetriaBatchDTO, IngerirTelemetriaDTO


def entrada(**cambios):
    return IngerirTelemetriaDTO(**dict(dict(device_id=3, sensor_id=6,
        tipo_variable='TEMPERATURA_AMBIENTAL', valor='22.5', unidad='°C',
        timestamp_captura=datetime.now(timezone.utc), serial='SERIAL-PRUEBA'), **cambios))


def construir(resultado):
    db, port, identidad, bitacora = Mock(), Mock(), Mock(), Mock()
    port.ingerir.return_value = resultado
    return IngerirTelemetriaUseCase(db, port, identidad, bitacora)


@pytest.mark.parametrize('codigo,http', [
    ('ERROR_DUPLICADO',409), ('ERROR_ESTRUCTURA',400), ('ERROR_AUTENTICACION',401),
    ('ERROR_TIEMPO',400), ('ERROR_UNIDAD',400), ('ERROR_SENSOR',422),
])
def test_rechazos_sql_confirman_bitacora_antes_de_responder(codigo, http):
    uc = construir(ResultadoPersistenciaIngesta(None, None, codigo + ': detalle SQL que no se expone'))
    with pytest.raises(AppError) as error:
        uc.execute(entrada())
    assert error.value.code == codigo and error.value.status_code == http
    assert 'SQL' not in error.value.message
    uc.db.commit.assert_called_once()
    uc.db.rollback.assert_not_called()
    uc.bitacora_repo.registrar_exito.assert_not_called()
    uc.bitacora_repo.registrar_error.assert_not_called()


@pytest.mark.parametrize('estado', ['LECTURA_VALIDA','FUERA_DE_RANGO','ERROR_CALIBRACION'])
def test_solo_id_y_estado_persistido_permiten_confirmar(estado):
    ahora = datetime.now(timezone.utc)
    uc = construir(ResultadoPersistenciaIngesta(10, estado, 'OK', ahora, 4))
    resultado = uc.execute(entrada(), gateway_id='gateway-prueba')
    assert resultado.id_telemetria == 10 and resultado.estado_calidad == estado
    assert resultado.timestamp_procesamiento == ahora
    uc.db.commit.assert_called_once()
    parametros = uc.ingesta_port.ingerir.call_args.args[0]
    assert parametros['valor'] == entrada().valor
    assert parametros['unidad'] == '°C'
    assert 'SERIAL-PRUEBA' not in repr(parametros)
    uc.bitacora_repo.registrar_exito.assert_not_called()


@pytest.mark.parametrize('resultado', [ResultadoPersistenciaIngesta(None, None, 'Error inesperado'),
                                     ResultadoPersistenciaIngesta(10, 'INVENTADO', 'OK')])
def test_resultado_inconsistente_no_confirma(resultado):
    uc = construir(resultado)
    with pytest.raises(ServiceUnavailableError):
        uc.execute(entrada())
    uc.db.rollback.assert_called_once()
    uc.db.commit.assert_not_called()


def test_error_de_persistencia_revierte_sin_acuse_falso():
    uc = construir(None)
    uc.ingesta_port.ingerir.side_effect = RuntimeError('base no disponible')
    with pytest.raises(RuntimeError):
        uc.execute(entrada())
    uc.db.rollback.assert_called_once()
    uc.db.commit.assert_not_called()


def test_error_en_commit_no_devuelve_id_aceptado():
    uc = construir(ResultadoPersistenciaIngesta(10,'LECTURA_VALIDA','OK',datetime.now(timezone.utc)))
    uc.db.commit.side_effect = RuntimeError('No se pudo confirmar')
    with pytest.raises(RuntimeError):
        uc.execute(entrada())
    uc.db.rollback.assert_called_once()


def test_credencial_invalida_no_llega_a_sql_y_no_se_registra_en_payload():
    uc = construir(None)
    uc.dispositivo_port.validar_dispositivo_heartbeat.return_value = None
    with pytest.raises(AppError) as error:
        uc.execute(entrada())
    assert error.value.status_code == 401
    uc.ingesta_port.ingerir.assert_not_called()
    assert 'SERIAL-PRUEBA' not in repr(uc.bitacora_repo.registrar_error.call_args)
    uc.db.commit.assert_called_once()


def test_batch_conserva_aceptados_rechazados_y_duplicados():
    ucs = [construir(ResultadoPersistenciaIngesta(10,'LECTURA_VALIDA','OK',datetime.now(timezone.utc))),
           construir(ResultadoPersistenciaIngesta(None,None,'ERROR_DUPLICADO: repetido')),
           construir(ResultadoPersistenciaIngesta(None,None,'ERROR_TIEMPO: futuro'))]
    items = iter(ucs)
    resultado = SincronizarBufferUseCase(lambda: next(items), Mock()).execute(
        IngerirTelemetriaBatchDTO(registros=[entrada(),entrada(),entrada()]))
    assert (resultado['aceptados'], resultado['duplicados'], resultado['rechazados']) == (1,1,1)
    assert [x.id_telemetria for x in resultado['detalle']] == [10,None,None]


def test_batch_no_convierte_indisponibilidad_en_confirmacion_de_rechazo():
    uc = construir(ResultadoPersistenciaIngesta(None,None,'DESCONOCIDO'))
    with pytest.raises(ServiceUnavailableError):
        SincronizarBufferUseCase(lambda: uc, Mock()).execute(IngerirTelemetriaBatchDTO(registros=[entrada()]))
