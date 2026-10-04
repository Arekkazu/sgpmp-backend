"""Caso de uso: Desactivar dispositivo IoT (PATCH /{id}/desactivar RF-21).

Si el dispositivo es un Gateway Edge, sus dispositivos activos se desactivan en
cascada en la misma transacción (cada uno con su auditoría DEACTIVATE): sin el
Edge no tienen por dónde comunicarse. El vínculo id_dispositivo_gateway se
conserva para saber de dónde venía cada uno. No hay reactivación en cascada.
"""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session

from src.configuration.application.use_cases.dispositivos_iot.credencial_mqtt_use_case import revocar_y_auditar
from src.configuration.domain.entities.dispositivo_iot import DispositivoIot
from src.configuration.domain.repositories.auditoria_dispositivo_iot_repository import AuditoriaDispositivoIotRepository
from src.configuration.domain.repositories.bitacora_iot_port import BitacoraIotPort
from src.configuration.domain.repositories.configuracion_remota_repository import ConfiguracionRemotaRepository
from src.configuration.domain.repositories.dispositivo_iot_repository import DispositivoIotRepository
from src.configuration.domain.repositories.mqtt_port import MqttPort
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import AppError, BusinessRuleError, NotFoundError

logger = logging.getLogger(__name__)

MOTIVO_CASCADA = "gateway_edge_desactivado"


class DesactivarDispositivoIotUseCase:

    def __init__(
        self,
        db: Session,
        dispositivo_repo: DispositivoIotRepository,
        config_repo: ConfiguracionRemotaRepository,
        auditoria_repo: AuditoriaDispositivoIotRepository,
        mqtt_port: Optional[MqttPort] = None,
        bitacora: Optional[BitacoraIotPort] = None,
    ) -> None:
        self.db = db
        self.dispositivo_repo = dispositivo_repo
        self.config_repo = config_repo
        self.auditoria_repo = auditoria_repo
        self.mqtt_port = mqtt_port
        self.bitacora = bitacora

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

        # Solo un Gateway Edge tiene dispositivos que apunten a él (lo valida RF-21).
        atendidos = self.dispositivo_repo.listar_por_gateway(id_dispositivo_iot)
        con_pendiente = [
            d.serial.valor
            for d in atendidos
            if self.config_repo.obtener_pendiente(d.id_dispositivo_iot) is not None
        ]
        if con_pendiente:
            raise BusinessRuleError(
                code="CONFIG_PENDIENTE_EN_DISPOSITIVOS_DEL_EDGE",
                message=(
                    "No se puede desactivar el Gateway Edge: estos dispositivos que atiende tienen "
                    f"una configuración pendiente de aplicación: {', '.join(con_pendiente)}."
                ),
            )

        try:
            dispositivo_actualizado = self._desactivar(dispositivo, usuario_actual, motivo=None)
            desactivados = [
                self._desactivar(d, usuario_actual, motivo=MOTIVO_CASCADA) for d in atendidos
            ]
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        # POST-commit (TC-M09-250/251): un dispositivo desactivado no debe poder
        # seguir conectándose al broker ni ser atendido por un Edge. Best-effort:
        # si el broker no responde, la desactivación se mantiene, el fallo queda en
        # la bitácora y el broker lo corrige al reconciliar con modulo9 la próxima
        # vez que el gateway conecte.
        self._revocar(dispositivo_actualizado, usuario_actual, "dispositivo_desactivado")
        for d in desactivados:
            self._revocar(d, usuario_actual, MOTIVO_CASCADA)

        return dispositivo_actualizado

    def _desactivar(
        self, dispositivo: DispositivoIot, usuario_actual: UsuarioActual, *, motivo: Optional[str]
    ) -> DispositivoIot:
        snapshot_anterior = dispositivo._snapshot()
        dispositivo.desactivar()
        actualizado = self.dispositivo_repo.actualizar(dispositivo)
        valores_nuevos = actualizado._snapshot()
        if motivo is not None:
            valores_nuevos["motivo"] = motivo
        self.auditoria_repo.registrar(
            id_dispositivo_iot=actualizado.id_dispositivo_iot,
            id_usuario=usuario_actual.id_usuario,
            tipo_operacion="DEACTIVATE",
            valores_nuevos=valores_nuevos,
            valores_anteriores=snapshot_anterior,
        )
        return actualizado

    def _revocar(self, dispositivo: DispositivoIot, usuario_actual: UsuarioActual, motivo: str) -> None:
        if self.mqtt_port is None or self.bitacora is None:
            return
        try:
            revocar_y_auditar(
                self.mqtt_port, self.bitacora, dispositivo, usuario_actual.id_usuario, motivo=motivo
            )
        except AppError:
            logger.warning(
                "No se pudo revocar la credencial MQTT de %s al desactivarlo.",
                dispositivo.serial.valor,
                exc_info=True,
            )
