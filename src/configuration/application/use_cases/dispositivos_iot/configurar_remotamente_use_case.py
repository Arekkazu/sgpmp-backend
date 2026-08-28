"""Caso de uso: Configurar dispositivo IoT remotamente (POST /{id}/configurar RF-23).

El sistema envía la configuración vía MQTT (BROKER-MQTT-SGPMP), que espera
de forma acotada el ACK del dispositivo. Según el resultado, la
configuración queda PENDIENTE (dispositivo offline / broker inalcanzable),
APLICADA (ACK recibido) o NO_CONF (se publicó pero no hubo ACK a tiempo).
"""
from __future__ import annotations

import datetime

from sqlalchemy.orm import Session

from src.configuration.domain.entities.configuracion_remota import ConfiguracionRemota
from src.configuration.domain.repositories.configuracion_remota_repository import ConfiguracionRemotaRepository
from src.configuration.domain.repositories.dispositivo_iot_repository import DispositivoIotRepository
from src.configuration.domain.repositories.mqtt_port import MqttPort
from src.configuration.domain.repositories.tipo_dispositivo_iot_repository import TipoDispositivoIotRepository
from src.configuration.infrastructure.dto.configurar_remotamente_dto import ConfigurarRemotamenteDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import BusinessRuleError, ConflictError, NotFoundError, ValidationError


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
        self, id_dispositivo_iot: int, dto: ConfigurarRemotamenteDTO, usuario_actual: UsuarioActual
    ) -> tuple[ConfiguracionRemota, str]:
        dispositivo = self.dispositivo_repo.obtener_por_id(id_dispositivo_iot)
        if dispositivo is None:
            raise NotFoundError(
                code="DISPOSITIVO_NO_ENCONTRADO",
                message=f"No existe un dispositivo IoT con ID {id_dispositivo_iot}.",
            )
        if not dispositivo.es_activo:
            raise BusinessRuleError(
                code="DISPOSITIVO_INACTIVO",
                message="No se puede configurar un dispositivo inactivo.",
            )

        tipo = self.tipo_repo.obtener_por_id(dispositivo.id_tipo_dispositivo)
        if tipo is None:
            raise NotFoundError(
                code="TIPO_DISPOSITIVO_NO_ENCONTRADO",
                message=f"No existe el tipo de dispositivo con ID {dispositivo.id_tipo_dispositivo}.",
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
                message="Ya existe una configuración pendiente de aplicación para este dispositivo. Espere a que se aplique antes de enviar una nueva.",
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

        # POST-commit: intento de envío MQTT vía el broker (bloqueante, hasta ~35s)
        resultado = self.mqtt_port.enviar_configuracion(
            dispositivo.serial.valor,
            {
                "frecuencia_captura": config_guardada.frecuencia_captura,
                "intervalo_transmision": config_guardada.intervalo_transmision,
            },
        )

        if resultado.estado == "PENDIENTE":
            return config_guardada, resultado.mensaje

        if resultado.estado == "APLICADA":
            config_guardada.marcar_aplicada(datetime.datetime.now(datetime.timezone.utc))
        else:
            config_guardada.marcar_no_confirmada()

        try:
            config_guardada = self.config_repo.actualizar(config_guardada)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return config_guardada, resultado.mensaje


class ConsultarConfiguracionesUseCase:

    def __init__(self, db: Session, config_repo: ConfiguracionRemotaRepository) -> None:
        self.db = db
        self.config_repo = config_repo

    def listar_por_dispositivo(self, id_dispositivo_iot: int) -> list[ConfiguracionRemota]:
        return self.config_repo.listar_por_dispositivo(id_dispositivo_iot)
