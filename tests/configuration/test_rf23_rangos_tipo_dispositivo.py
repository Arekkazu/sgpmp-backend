"""RF-23 / #1632 — Rangos por tipo de dispositivo + estado NO_CONF.

Verifica con fakes (sin BD; modulo9 no existe en la BD `pruebas`):
- valor fuera del rango del tipo → ValidationError 400 con el mensaje exacto del FA;
- valor dentro de rango + broker APLICADA/PENDIENTE/NO_CONF → estado correcto;
- NO_CONF es un estado terminal distinto de PENDIENTE/APLICADA (base del 504);
- TipoDispositivoIot.verificar_rango detecta la primera violación por parámetro.
"""
from __future__ import annotations

import pytest

from src.configuration.application.use_cases.dispositivos_iot.configurar_remotamente_use_case import (
    ConfigurarRemotamenteUseCase,
)
from src.configuration.domain.entities.dispositivo_iot import DispositivoIot
from src.configuration.domain.entities.tipo_dispositivo_iot import TipoDispositivoIot
from src.configuration.domain.repositories.mqtt_port import ResultadoEnvioMqtt
from src.configuration.domain.value_objects.serial_dispositivo import SerialDispositivo
from src.configuration.infrastructure.dto.configurar_remotamente_dto import ConfigurarRemotamenteDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import ValidationError

USUARIO = UsuarioActual(id_usuario=1, id_token=1, id_rol=1)

# Tipo con rangos acotados para forzar violaciones: freq 5..120, intervalo 5..240.
TIPO = TipoDispositivoIot(
    id_tipo_dispositivo=7,
    nombre="SENSOR_AMBIENTAL",
    frecuencia_captura_min=5,
    frecuencia_captura_max=120,
    intervalo_transmision_min=5,
    intervalo_transmision_max=240,
)


class DbFake:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


class DispositivoRepoFake:
    def __init__(self, dispositivo) -> None:
        self._d = dispositivo

    def obtener_por_id(self, _id):
        return self._d


class TipoRepoFake:
    def __init__(self, tipo) -> None:
        self._t = tipo

    def obtener_por_id(self, _id):
        return self._t


class ConfigRepoFake:
    def __init__(self) -> None:
        self.pendiente = None
        self._seq = 0

    def obtener_pendiente(self, _id):
        return self.pendiente

    def guardar(self, config):
        self._seq += 1
        config.id_configuracion_remota = self._seq
        return config

    def actualizar(self, config):
        return config


class MqttFake:
    def __init__(self, estado) -> None:
        self._estado = estado

    def enviar_configuracion(self, _serial, _payload):
        return ResultadoEnvioMqtt(estado=self._estado, mensaje=f"mensaje {self._estado}")


def _dispositivo(activo: bool = True) -> DispositivoIot:
    d = DispositivoIot.crear(
        serial=SerialDispositivo("IOT-EST01-HLA-001"),
        descripcion="sensor",
        id_infraestructura=1,
        id_tipo_dispositivo=TIPO.id_tipo_dispositivo,
        es_activo=activo,
    )
    d.id_dispositivo_iot = 1
    return d


def _use_case(estado_broker: str) -> ConfigurarRemotamenteUseCase:
    return ConfigurarRemotamenteUseCase(
        db=DbFake(),
        dispositivo_repo=DispositivoRepoFake(_dispositivo()),
        config_repo=ConfigRepoFake(),
        tipo_repo=TipoRepoFake(TIPO),
        mqtt_port=MqttFake(estado_broker),
    )


def test_frecuencia_fuera_de_rango_400():
    uc = _use_case("APLICADA")
    dto = ConfigurarRemotamenteDTO(frecuencia_captura=200, intervalo_transmision=200)
    with pytest.raises(ValidationError) as exc:
        uc.execute(1, dto, USUARIO)
    assert exc.value.status_code == 400
    assert exc.value.code == "PARAMETRO_FUERA_DE_RANGO"
    assert exc.value.field == "frecuencia_captura"
    assert exc.value.message == (
        "Valor inválido: El parámetro frecuencia_captura debe estar entre 5 y 120 "
        "minutos para este tipo de dispositivo. Valor recibido: 200."
    )


def test_intervalo_fuera_de_rango_400():
    uc = _use_case("APLICADA")
    # frecuencia válida (10), intervalo excede el max del tipo (240).
    dto = ConfigurarRemotamenteDTO(frecuencia_captura=10, intervalo_transmision=300)
    with pytest.raises(ValidationError) as exc:
        uc.execute(1, dto, USUARIO)
    assert exc.value.field == "intervalo_transmision"
    assert "entre 5 y 240" in exc.value.message


@pytest.mark.parametrize("estado", ["APLICADA", "PENDIENTE", "NO_CONF"])
def test_dentro_de_rango_propaga_estado_broker(estado):
    uc = _use_case(estado)
    dto = ConfigurarRemotamenteDTO(frecuencia_captura=10, intervalo_transmision=30)
    config, _mensaje = uc.execute(1, dto, USUARIO)
    assert config.estado == estado


def test_verificar_rango_unit():
    assert TIPO.verificar_rango(10, 30) is None
    v = TIPO.verificar_rango(1, 30)
    assert v["field"] == "frecuencia_captura" and v["min"] == 5 and v["max"] == 120 and v["valor"] == 1
    # frecuencia ok, intervalo bajo el min → detecta intervalo
    v2 = TIPO.verificar_rango(10, 1)
    assert v2["field"] == "intervalo_transmision" and v2["valor"] == 1
