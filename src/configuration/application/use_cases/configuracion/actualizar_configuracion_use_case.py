"""Caso de uso: Actualizar parámetros operativos globales (PATCH RF-18).

Aplica concurrencia optimista: rechaza si ``fecha_actualizacion`` no coincide.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.configuration.domain.entities.configuracion_global import ConfiguracionGlobal
from src.configuration.domain.repositories.auditoria_config_repository import AuditoriaConfigRepository
from src.configuration.domain.repositories.configuracion_global_repository import ConfiguracionGlobalRepository
from src.configuration.domain.repositories.iot_notificacion_port import IotNotificacionPort
from src.configuration.domain.value_objects.frecuencia_muestreo import FrecuenciaMuestreo
from src.configuration.domain.value_objects.heartbeat import Heartbeat
from src.configuration.infrastructure.dto.actualizar_configuracion_dto import ActualizarConfiguracionDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import NotFoundError, PreconditionFailedError


class ActualizarConfiguracionUseCase:

    def __init__(
        self,
        db: Session,
        config_repo: ConfiguracionGlobalRepository,
        auditoria_repo: AuditoriaConfigRepository,
        iot_port: IotNotificacionPort,
    ) -> None:
        self.db = db
        self.config_repo = config_repo
        self.auditoria_repo = auditoria_repo
        self.iot_port = iot_port

    def execute(
        self, id_configuracion_global: int, dto: ActualizarConfiguracionDTO, usuario_actual: UsuarioActual
    ) -> ConfiguracionGlobal:
        config = self.config_repo.obtener_por_id(id_configuracion_global)
        if config is None:
            raise NotFoundError(
                code="CONFIG_NO_ENCONTRADA",
                message=f"No existe una configuración con ID {id_configuracion_global}.",
            )

        ts_actual = config.fecha_actualizacion
        ts_dto = dto.fecha_actualizacion
        if ts_actual is not None and ts_dto is not None:
            if ts_actual.astimezone(timezone.utc) != ts_dto.astimezone(timezone.utc):
                raise PreconditionFailedError(
                    code="CONFLICTO_CONCURRENCIA",
                    message=(
                        "Los parámetros operativos han sido modificados por otro administrador "
                        "mientras usted realizaba los cambios. Por favor, recargue la configuración "
                        "antes de intentar de nuevo."
                    ),
                )
        elif ts_actual != ts_dto:
            raise PreconditionFailedError(
                code="CONFLICTO_CONCURRENCIA",
                message=(
                    "Los parámetros operativos han sido modificados por otro administrador. "
                    "Recargue la configuración antes de intentar de nuevo."
                ),
            )

        snapshot_anterior = config._snapshot()

        frecuencia = FrecuenciaMuestreo(dto.frecuencia_muestreo)
        heartbeat = Heartbeat(dto.heartbeat)

        config.actualizar(
            frecuencia_muestreo=frecuencia,
            heartbeat=heartbeat,
            id_usuario=usuario_actual.id_usuario,
            fecha_actualizacion=datetime.now(timezone.utc),
        )

        try:
            config_actualizada = self.config_repo.actualizar(config)
            self.auditoria_repo.registrar(
                id_configuracion_global=config_actualizada.id_configuracion_global,
                id_usuario=usuario_actual.id_usuario,
                tipo_operacion="UPDATE",
                valores_nuevos=config_actualizada._snapshot(),
                valores_anteriores=snapshot_anterior,
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        self.iot_port.notificar_configuracion(
            frecuencia_muestreo=config_actualizada.frecuencia_muestreo.valor,
            heartbeat=config_actualizada.heartbeat.valor,
        )
        return config_actualizada
