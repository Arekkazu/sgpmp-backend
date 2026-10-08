"""Casos de uso de configuración remota de dispositivos IoT (RF-23).

El sistema envía la configuración vía MQTT (BROKER-MQTT-SGPMP), que espera
de forma acotada el ACK del dispositivo. Según el resultado, la
configuración queda PENDIENTE (dispositivo offline / broker inalcanzable),
APLICADA (ACK recibido) o NO_CONF (se publicó pero no hubo ACK a tiempo).
Una PENDIENTE o NO_CONF se puede reintentar o cancelar desde el historial.
"""
from __future__ import annotations

import datetime
from typing import Optional

from sqlalchemy.orm import Session

from src.configuration.domain.entities.configuracion_remota import ConfiguracionRemota
from src.configuration.domain.entities.dispositivo_iot import DispositivoIot
from src.configuration.domain.repositories.bitacora_iot_port import BitacoraIotPort
from src.configuration.domain.repositories.configuracion_remota_repository import ConfiguracionRemotaRepository
from src.configuration.domain.repositories.dispositivo_iot_repository import DispositivoIotRepository
from src.configuration.domain.repositories.mqtt_port import MqttPort
from src.configuration.domain.repositories.tipo_dispositivo_iot_repository import TipoDispositivoIotRepository
from src.configuration.infrastructure.dto.configurar_remotamente_dto import ConfigurarRemotamenteDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import BusinessRuleError, ConflictError, NotFoundError, ValidationError

EVENTO_REINTENTADA = "CONFIGURACION_REMOTA_REINTENTADA"
EVENTO_CANCELADA = "CONFIGURACION_REMOTA_CANCELADA"


def _dispositivo_en_alcance(
    dispositivo_repo: DispositivoIotRepository,
    id_dispositivo_iot: int,
    ids_fincas_permitidas: Optional[list[int]],
) -> DispositivoIot:
    dispositivo = dispositivo_repo.obtener_por_id(
        id_dispositivo_iot,
        ids_fincas_permitidas=ids_fincas_permitidas,
    )
    if dispositivo is None:
        raise NotFoundError(
            code="DISPOSITIVO_NO_ENCONTRADO",
            message=f"No existe un dispositivo IoT con ID {id_dispositivo_iot}.",
        )
    return dispositivo


def _verificar_activo(dispositivo: DispositivoIot) -> None:
    if not dispositivo.es_activo:
        raise BusinessRuleError(
            code="DISPOSITIVO_INACTIVO",
            message="No se puede configurar un dispositivo inactivo.",
        )


def _configuracion_sin_aplicar(
    config_repo: ConfiguracionRemotaRepository,
    id_dispositivo_iot: int,
    id_configuracion_remota: int,
) -> ConfiguracionRemota:
    config = config_repo.obtener_por_id(id_configuracion_remota)
    if config is None or config.id_dispositivo_iot != id_dispositivo_iot:
        raise NotFoundError(
            code="CONFIGURACION_NO_ENCONTRADA",
            message=f"No existe la configuración {id_configuracion_remota} para este dispositivo.",
        )
    if not config.sin_aplicar:
        raise ConflictError(
            code="CONFIGURACION_YA_RESUELTA",
            message=f"La configuración está {config.estado}: solo se puede reintentar o cancelar una PENDIENTE o NO_CONF.",
        )
    return config


def _enviar_y_registrar(
    db: Session,
    config_repo: ConfiguracionRemotaRepository,
    mqtt_port: MqttPort,
    serial: str,
    config: ConfiguracionRemota,
) -> tuple[ConfiguracionRemota, str]:
    """Envía por el broker (bloqueante, hasta ~35 s) y persiste el estado resultante."""
    resultado = mqtt_port.enviar_configuracion(
        serial,
        {
            "frecuencia_captura": config.frecuencia_captura,
            "intervalo_transmision": config.intervalo_transmision,
        },
    )

    estado_previo = config.estado
    if resultado.estado == "PENDIENTE":
        config.marcar_pendiente()
    elif resultado.estado == "APLICADA":
        config.marcar_aplicada(datetime.datetime.now(datetime.timezone.utc))
    else:
        config.marcar_no_confirmada()
    if config.estado == estado_previo:
        return config, resultado.mensaje

    try:
        config = config_repo.actualizar(config)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return config, resultado.mensaje


class ConfigurarRemotamenteUseCase:

    def __init__(
        self,
        db: Session,
        dispositivo_repo: DispositivoIotRepository,
        config_repo: ConfiguracionRemotaRepository,
        tipo_repo: TipoDispositivoIotRepository,
        mqtt_port: MqttPort,
    ) -> None:
        self.db = db
        self.dispositivo_repo = dispositivo_repo
        self.config_repo = config_repo
        self.tipo_repo = tipo_repo
        self.mqtt_port = mqtt_port

    def execute(
        self,
        id_dispositivo_iot: int,
        dto: ConfigurarRemotamenteDTO,
        usuario_actual: UsuarioActual,
        *,
        ids_fincas_permitidas: Optional[list[int]] = None,
    ) -> tuple[ConfiguracionRemota, str]:
        dispositivo = _dispositivo_en_alcance(self.dispositivo_repo, id_dispositivo_iot, ids_fincas_permitidas)
        _verificar_activo(dispositivo)

        tipo = self.tipo_repo.obtener_por_id(dispositivo.id_tipo_dispositivo)
        if tipo is None:
            raise NotFoundError(
                code="TIPO_DISPOSITIVO_NO_ENCONTRADO",
                message=f"No existe el tipo de dispositivo con ID {dispositivo.id_tipo_dispositivo}.",
            )
        if tipo.es_gateway_edge:
            raise BusinessRuleError(
                code="CONFIGURACION_NO_APLICA_A_GATEWAY_EDGE",
                message="Un Gateway Edge no captura datos: la configuración remota se hace sobre los dispositivos que atiende.",
            )
        violacion = tipo.verificar_rango(dto.frecuencia_captura, dto.intervalo_transmision)
        if violacion is not None:
            raise ValidationError(
                code="PARAMETRO_FUERA_DE_RANGO",
                message=(
                    f"Valor inválido: El parámetro {violacion['field']} debe estar entre "
                    f"{violacion['min']} y {violacion['max']} minutos para este tipo de dispositivo. "
                    f"Valor recibido: {violacion['valor']}."
                ),
                field=violacion["field"],
            )

        if self.config_repo.obtener_pendiente(id_dispositivo_iot) is not None:
            raise ConflictError(
                code="CONFIG_PENDIENTE_EXISTENTE",
                message=(
                    "Operación en curso: Ya existe una configuración pendiente de aplicación para el dispositivo "
                    f"{dispositivo.serial.valor}. Espere a que se aplique o cancele la anterior antes de enviar una nueva."
                ),
            )

        config = ConfiguracionRemota.crear(
            id_dispositivo_iot=id_dispositivo_iot,
            frecuencia_captura=dto.frecuencia_captura,
            intervalo_transmision=dto.intervalo_transmision,
            id_usuario=usuario_actual.id_usuario,
        )

        try:
            config_guardada = self.config_repo.guardar(config)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        # POST-commit: el envío no deshace la fila si el broker falla.
        return _enviar_y_registrar(
            self.db, self.config_repo, self.mqtt_port, dispositivo.serial.valor, config_guardada
        )


class ReintentarConfiguracionUseCase:
    """Vuelve a enviar una configuración PENDIENTE o NO_CONF (POST .../reintentar)."""

    def __init__(
        self,
        db: Session,
        dispositivo_repo: DispositivoIotRepository,
        config_repo: ConfiguracionRemotaRepository,
        mqtt_port: MqttPort,
        bitacora: BitacoraIotPort,
    ) -> None:
        self.db = db
        self.dispositivo_repo = dispositivo_repo
        self.config_repo = config_repo
        self.mqtt_port = mqtt_port
        self.bitacora = bitacora

    def execute(
        self,
        id_dispositivo_iot: int,
        id_configuracion_remota: int,
        usuario_actual: UsuarioActual,
        *,
        ids_fincas_permitidas: Optional[list[int]] = None,
    ) -> tuple[ConfiguracionRemota, str]:
        dispositivo = _dispositivo_en_alcance(self.dispositivo_repo, id_dispositivo_iot, ids_fincas_permitidas)
        _verificar_activo(dispositivo)
        config = _configuracion_sin_aplicar(self.config_repo, id_dispositivo_iot, id_configuracion_remota)
        # Una NO_CONF vieja no bloquea enviar otra: reenviarla pisaría en el
        # dispositivo la configuración más reciente.
        if self.config_repo.listar_por_dispositivo(id_dispositivo_iot)[0] != config:
            raise ConflictError(
                code="CONFIGURACION_REEMPLAZADA",
                message="Hay una configuración más reciente para este dispositivo: reintentar esta la sobrescribiría.",
            )

        config, mensaje = _enviar_y_registrar(
            self.db, self.config_repo, self.mqtt_port, dispositivo.serial.valor, config
        )
        self.bitacora.registrar(
            evento=EVENTO_REINTENTADA,
            exitoso=config.estado == "APLICADA",
            id_dispositivo_iot=id_dispositivo_iot,
            serial=dispositivo.serial.valor,
            id_usuario=usuario_actual.id_usuario,
            detalle={"id_configuracion_remota": id_configuracion_remota, "estado": config.estado},
        )
        return config, mensaje


class CancelarConfiguracionUseCase:
    """Descarta una configuración PENDIENTE o NO_CONF (PATCH .../cancelar).

    No exige el dispositivo activo: cancelar es lo que permite desactivarlo.
    """

    def __init__(
        self,
        db: Session,
        dispositivo_repo: DispositivoIotRepository,
        config_repo: ConfiguracionRemotaRepository,
        bitacora: BitacoraIotPort,
    ) -> None:
        self.db = db
        self.dispositivo_repo = dispositivo_repo
        self.config_repo = config_repo
        self.bitacora = bitacora

    def execute(
        self,
        id_dispositivo_iot: int,
        id_configuracion_remota: int,
        usuario_actual: UsuarioActual,
        *,
        ids_fincas_permitidas: Optional[list[int]] = None,
    ) -> ConfiguracionRemota:
        dispositivo = _dispositivo_en_alcance(self.dispositivo_repo, id_dispositivo_iot, ids_fincas_permitidas)
        config = _configuracion_sin_aplicar(self.config_repo, id_dispositivo_iot, id_configuracion_remota)
        estado_previo = config.estado
        config.cancelar()
        try:
            config = self.config_repo.actualizar(config)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        self.bitacora.registrar(
            evento=EVENTO_CANCELADA,
            exitoso=True,
            id_dispositivo_iot=id_dispositivo_iot,
            serial=dispositivo.serial.valor,
            id_usuario=usuario_actual.id_usuario,
            detalle={"id_configuracion_remota": id_configuracion_remota, "estado_anterior": estado_previo},
        )
        return config


class ConsultarConfiguracionesUseCase:

    def __init__(
        self,
        db: Session,
        config_repo: ConfiguracionRemotaRepository,
        dispositivo_repo: DispositivoIotRepository,
    ) -> None:
        self.db = db
        self.config_repo = config_repo
        self.dispositivo_repo = dispositivo_repo

    def listar_por_dispositivo(
        self,
        id_dispositivo_iot: int,
        *,
        ids_fincas_permitidas: Optional[list[int]] = None,
    ) -> list[ConfiguracionRemota]:
        _dispositivo_en_alcance(self.dispositivo_repo, id_dispositivo_iot, ids_fincas_permitidas)
        return self.config_repo.listar_por_dispositivo(id_dispositivo_iot)
