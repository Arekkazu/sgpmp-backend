# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-10-27 | Leandro | INC-M03-131-G23 RF-53/54: verificar contrato opcional y conservacion de la secuencia original hacia la ingesta comun. |
"""Pruebas con puertos simulados; la persistencia real se acredita en integración."""
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError
from unittest.mock import Mock

from tests.telemetry.test_dev05_ingesta_bplus import construir, entrada
from src.telemetry.application.use_cases.ingesta.ingerir_telemetria_use_case import SincronizarBufferUseCase
from src.telemetry.domain.repositories.ingesta_telemetria_port import ResultadoPersistenciaIngesta
from src.telemetry.infrastructure.dto.ingerir_telemetria_dto import IngerirTelemetriaBatchDTO, IngerirTelemetriaDTO

MAX_LONG = 2**63-1


@pytest.mark.parametrize('secuencia', [0, 1, 37, MAX_LONG])
def test_recibe_y_conserva_secuencia_entera_sin_generarla(secuencia):
    dto = entrada(origen='BUFFER_LOCAL',buffer_sequence_id=secuencia)
    assert dto.model_dump()['buffer_sequence_id'] == secuencia
    ahora = datetime.now(timezone.utc)
    uc = construir(ResultadoPersistenciaIngesta(9,'LECTURA_VALIDA','OK',ahora,1))
    uc.execute(dto,gateway_id='GW-G23')
    metadatos = uc.ingesta_port.ingerir.call_args.args[0]['metadatos']
    assert metadatos == {'gateway_id':'GW-G23','checksum':None,'frecuencia_muestreo':None,
                        'buffer_sequence_id':secuencia}
    uc.db.commit.assert_called_once()
    uc.db.rollback.assert_not_called()


@pytest.mark.parametrize('secuencia', [-1, MAX_LONG+1, True, False, 1.0, 1.5, '1', 'abc', {}, []])
def test_rechaza_identificador_que_no_es_long_no_negativo(secuencia):
    with pytest.raises(ValidationError):
        entrada(buffer_sequence_id=secuencia)


@pytest.mark.parametrize('cambio', [{}, {'buffer_sequence_id':None}])
def test_cliente_anterior_no_recibe_secuencia_inventada(cambio):
    uc = construir(ResultadoPersistenciaIngesta(9,'LECTURA_VALIDA','OK',datetime.now(timezone.utc),1))
    uc.execute(entrada(**cambio))
    metadatos = uc.ingesta_port.ingerir.call_args.args[0]['metadatos']
    assert 'buffer_sequence_id' not in metadatos
    assert metadatos == {'gateway_id':None,'checksum':None,'frecuencia_muestreo':None}


def test_batch_conserva_secuencia_por_registro_y_orden_cronologico_existente():
    ahora = datetime.now(timezone.utc)
    ucs = [construir(ResultadoPersistenciaIngesta(i,'LECTURA_VALIDA','OK',ahora,1)) for i in (1,2)]
    it = iter(ucs)
    dto = IngerirTelemetriaBatchDTO(registros=[
        entrada(timestamp_captura=ahora,buffer_sequence_id=12,origen='BUFFER_LOCAL'),
        entrada(timestamp_captura=ahora-timedelta(minutes=10),buffer_sequence_id=11,origen='BUFFER_LOCAL'),
    ])
    r = SincronizarBufferUseCase(lambda:next(it),Mock()).execute(dto)
    assert (r['aceptados'],r['rechazados'],r['duplicados']) == (2,0,0)
    assert [uc.ingesta_port.ingerir.call_args.args[0]['metadatos']['buffer_sequence_id'] for uc in ucs] == [11,12]


def test_campo_es_opcional_en_openapi_sin_hacerlo_clave_de_idempotencia():
    schema = IngerirTelemetriaDTO.model_json_schema()
    assert 'buffer_sequence_id' in schema['properties']
    assert 'buffer_sequence_id' not in schema['required']
    entero = next(tipo for tipo in schema['properties']['buffer_sequence_id']['anyOf'] if tipo['type']=='integer')
    assert (entero['minimum'],entero['maximum']) == (0,MAX_LONG)
