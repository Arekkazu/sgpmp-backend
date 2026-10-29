# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-26 | Arekkazu | INC-M04 lote 26-10 RF-65/70/73: pesos, truncado, E7 y ventana PROGRAMADO |
# | 2026-10-27 | Leandro | INC-M04-158-G086 RF-73: verificar E7 con tipo catalogado e identidad y referencia validas. |
"""M04: pesos de contagio por rango (G42), truncado con mínimos (G088), corrección de
timestamp (G099) y ventana de la OTA PROGRAMADO (G43/G46)."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest

from src.prediction.application.use_cases.motor_ia.configurar_motor_use_case import ConfigurarMotorUseCase
from src.prediction.application.use_cases.ota._aviso_fase import (
    MOTIVO_FUERA_VENTANA,
    avisar_despliegues,
    fuera_de_ventana,
)
from src.prediction.infrastructure.dto.configurar_motor_dto import ConfigurarMotorDTO
from src.prediction.infrastructure.repositories.evento_auditoria_m04_repository import (
    _PAYLOAD_MAX_BYTES,
    SqlAlchemyEventoAuditoriaM04Repository,
    _truncar_payload,
)
from src.shared.errors import BusinessRuleError

AHORA = datetime(2026, 10, 26, 12, tzinfo=timezone.utc)


@pytest.mark.parametrize('pesos', [('-0.1', '0.6', '0.5'), ('1.2', '-0.1', '-0.1')])
def test_peso_fuera_de_0_1_se_rechaza_aunque_la_suma_sea_1(pesos):
    dto = ConfigurarMotorDTO(tipo_modelo='MODELO_RIESGO_CONTAGIO', ventana_temporal_min=10,
                             w_factor_sanitario=Decimal(pesos[0]), w_factor_ambiental=Decimal(pesos[1]),
                             w_factor_densidad=Decimal(pesos[2]))
    with pytest.raises(BusinessRuleError) as exc:
        ConfigurarMotorUseCase._validar_comunes(None, dto, [])
    assert exc.value.code == 'PESOS_CONTAGIO_INVALIDOS' and exc.value.status_code == 422


def test_pesos_validos_pasan():
    dto = ConfigurarMotorDTO(tipo_modelo='MODELO_RIESGO_CONTAGIO', ventana_temporal_min=10,
                             w_factor_sanitario=Decimal('0.4'), w_factor_ambiental=Decimal('0.3'),
                             w_factor_densidad=Decimal('0.3'))
    ConfigurarMotorUseCase._validar_comunes(None, dto, [])


def test_truncado_conserva_los_campos_minimos_como_claves():
    payload = {'blob': 'x' * (_PAYLOAD_MAX_BYTES + 10), 'tipo_modelo': 'MODELO_RIESGO_CONTAGIO',
               'id_version': 7, 'nota': 'cabecera'}
    resultado, truncado = _truncar_payload(payload, ['tipo_modelo', 'id_version'])
    assert truncado and resultado['tipo_modelo'] == 'MODELO_RIESGO_CONTAGIO' and resultado['id_version'] == 7
    assert resultado['nota'] == 'cabecera' and resultado['campos_omitidos'] == ['blob']
    assert resultado['payload_truncado'] is True
    assert len(json.dumps(resultado).encode()) <= _PAYLOAD_MAX_BYTES


def test_payload_pequeno_no_se_toca():
    assert _truncar_payload({'a': 1}, ['a']) == ({'a': 1}, False)


class _Db:
    def __init__(self, ultimo):
        self.ultimo = ultimo

    def execute(self, _stmt):
        return SimpleNamespace(scalar_one_or_none=lambda: self.ultimo)


def _repo(ultimo=None):
    repo = SqlAlchemyEventoAuditoriaM04Repository.__new__(SqlAlchemyEventoAuditoriaM04Repository)
    repo._db = _Db(ultimo)
    return repo


def test_e7_timestamp_futuro_o_desordenado_se_corrige():
    corr = uuid.uuid4()
    assert _repo()._fecha_evento(AHORA + timedelta(hours=1), corr, AHORA) == (AHORA, 'FUTURO')
    assert _repo(AHORA - timedelta(minutes=1))._fecha_evento(AHORA - timedelta(minutes=5), corr, AHORA) == (
        AHORA, 'DESORDENADO')
    origen = AHORA - timedelta(minutes=5)
    assert _repo(AHORA - timedelta(minutes=10))._fecha_evento(origen, corr, AHORA) == (origen, None)
    assert _repo()._fecha_evento(None, corr, AHORA) == (AHORA, None)


def test_e7_registra_timestamp_corregido_warning():
    repo = _repo()
    persistidos = []
    repo._persistir = lambda campos, **_kw: persistidos.append(campos)
    repo.registrar(tipo_evento='CONFIGURACION_MOTOR_CAMBIADA', tipo_actor='SISTEMA',
                   id_sistema='M04', id_referencia='config-1',
                   payload_evento={'accion': 'ACTUALIZADA', 'valores_anteriores': {}, 'valores_nuevos': {'id_configuracion': 1}},
                   timestamp_evento=datetime.now(timezone.utc) + timedelta(hours=2))
    evento, correccion = persistidos
    assert correccion['tipo_evento'] == 'TIMESTAMP_CORREGIDO' and correccion['severidad_evento'] == 'WARNING'
    assert correccion['payload_evento']['motivo'] == 'FUTURO'
    assert correccion['id_referencia'] == str(evento['id_evento'])
    assert correccion['correlacion_id'] == evento['correlacion_id']


def _distribucion(modo='PROGRAMADO', inicio=AHORA + timedelta(hours=2), fin=AHORA + timedelta(hours=4)):
    return SimpleNamespace(modo_distribucion=modo, ventana_inicio=inicio, ventana_fin=fin)


def test_programado_solo_dentro_de_su_ventana():
    assert fuera_de_ventana(_distribucion(), AHORA)
    assert not fuera_de_ventana(_distribucion(inicio=AHORA - timedelta(hours=1)), AHORA)
    assert not fuera_de_ventana(_distribucion(modo='INMEDIATO'), AHORA)


def test_fuera_de_ventana_no_se_avisa_y_queda_pendiente():
    from src.prediction.domain.entities.despliegue_ota import DespliegueOta
    despliegue = DespliegueOta(
        id_despliegue_ota=1, id_version_modelo=1, id_dispositivo_iot=5, tipo_modelo='X', modo_distribucion='PROGRAMADO',
        estado_despliegue='PENDIENTE', hash_modelo_sha256='a' * 64, resultado_validacion_hash=None,
        id_version_modelo_anterior=None, rollback_ejecutado=False, intentos_descarga=0, max_reintentos=3,
        tamano_modelo_bytes=None, tamano_descargado_bytes=None, duracion_proceso_ms=None, ventana_inicio=None,
        ventana_fin=None, nivel_bateria_al_inicio=None, fecha_inicio=AHORA, fecha_fin=None, motivo_fallo=None,
    )

    class _NoUsar:
        def __getattr__(self, nombre):
            raise AssertionError(f'no debía llamarse {nombre}')

    repo = SimpleNamespace(actualizar=lambda d: d)
    [resultado] = avisar_despliegues(despliegues=[despliegue], distribucion=_distribucion(), version=None,
                                     despliegue_repo=repo, nodo_port=_NoUsar(), aviso_port=_NoUsar(),
                                     url_port=_NoUsar(), ahora=AHORA)
    assert resultado.estado_despliegue == 'PENDIENTE' and resultado.motivo_fallo == MOTIVO_FUERA_VENTANA
