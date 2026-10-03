"""Caso de uso: Desactivar dispositivo IoT (PATCH /{id}/desactivar RF-21)."""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session

from src.configuration.application.use_cases.dispositivos_iot.credencial_mqtt_use_case import revocar_y_auditar
from src.configuration.domain.entities.dispositivo_iot import DispositivoIot
from src.configuration.domain.repositories.auditoria_dispositivo_iot_repository import AuditoriaDispositivoIotRepository
from src.configuration.domain.repositories.bitacora_credencial_mqtt_port import BitacoraCredencialMqttPort
from src.configuration.domain.repositories.configuracion_remota_repository import ConfiguracionRemotaRepository
from src.configuration.domain.repositories.dispositivo_iot_repository import DispositivoIotRepository
from src.configuration.domain.repositories.mqtt_port import MqttPort
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import AppError, BusinessRuleError, NotFoundError

logger = logging.getLogger(__name__)


class DesactivarDispositivoIotUseCase:

    def __init__(
        self,
        db: Session,
        dispositivo_repo: DispositivoIotRepository,
        config_repo: ConfiguracionRemotaRepository,
        auditoria_repo: AuditoriaDispositivoIotRepository,
        mqtt_port: Optional[MqttPort] = None,
        bitacora_credencial: Optional[BitacoraCredencialMqttPort] = None,
    ) -> None:
        self.db = db
        self.dispositivo_repo = dispositivo_repo
        self.config_repo = config_repo
        self.auditoria_repo = auditoria_repo
        self.mqtt_port = mqtt_port
        self.bitacora_credencial = bitacora_credencial

    def execute(self, id_dispositivo_iot: int, usuario_actual: UsuarioActual) -> DispositivoIot:
        dispositivo = self.dispositivo_repo.obtener_por_id(id_dispositivo_iot)
        if dispositivo is None:
            raise NotFoundError(
                code="DISPOSITIVO_NO_ENCONTRADO",
                message=f"No existe un dispositivo IoT con ID {id_dispositivo_iot}.",
            )
        if not dispositivo.es_activo:
            raise BusinessRuleError(
                code="DISPOSITIVO_YA_INACTIVO",
                message="El dispositivo ya se encuentra inactivo.",
            )
        if self.config_repo.obtener_pendiente(id_dispositivo_iot) is not None:
            raise BusinessRuleError(
                code="CONFIG_PENDIENTE_EXISTENTE",
                message="El dispositivo tiene una configuración pendiente de aplicación. Espere a que se aplique antes de desactivarlo.",
            )

        snapshot_anterior = dispositivo._snapshot()
        dispositivo.desactivar()

        try:
            dispositivo_actualizado = self.dispositivo_repo.actualizar(dispositivo)
            self.auditoria_repo.registrar(
                id_dispositivo_iot=dispositivo_actualizado.id_dispositivo_iot,
                id_usuario=usuario_actual.id_usuario,
                tipo_operacion="DEACTIVATE",
                valores_nuevos=dispositivo_actualizado._snapshot(),
                valores_anteriores=snapshot_anterior,
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        # POST-commit (TC-M09-250/251): un dispositivo desactivado no debe poder
        # seguir conectándose al broker con su credencial MQTT. Best-effort: si el
        # broker no responde, la desactivación se mantiene, el fallo queda en la
        # bitácora y el broker deshabilita la credencial al reconciliar con modulo9
        # la próxima vez que el gateway conecte.
        if self.mqtt_port is not None and self.bitacora_credencial is not None:
            try:
                revocar_y_auditar(
                    self.mqtt_port,
                    self.bitacora_credencial,
                    dispositivo_actualizado,
                    usuario_actual.id_usuario,
                    motivo="dispositivo_desactivado",
                )
            except AppError:
                logger.warning(
                    "No se pudo revocar la credencial MQTT de %s al desactivarlo.",
                    dispositivo_actualizado.serial.valor,
                    exc_info=True,
                )

        return dispositivo_actualizado
