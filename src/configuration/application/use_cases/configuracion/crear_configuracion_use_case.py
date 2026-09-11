"""Caso de uso: Crear parámetros operativos globales (POST RF-18).

Solo se permite si no existe ninguna configuración activa (FA-13).
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
from src.configuration.infrastructure.dto.crear_configuracion_dto import CrearConfiguracionDTO
from src.identity_access.infrastructure.dependencies import UsuarioActual
from src.shared.errors import ConflictError


class CrearConfiguracionUseCase:

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

    def execute(self, dto: CrearConfiguracionDTO, usuario_actual: UsuarioActual) -> ConfiguracionGlobal:
        existente = self.config_repo.obtener_activo()
        if existente is not None:
            raise ConflictError(
                code="CONFIG_ACTIVA_EXISTENTE",
                message=(
                    "Ya existe una configuración operativa activa. "
                    "Utilice el método de actualización para modificar los valores vigentes."
                ),
            )

        frecuencia = FrecuenciaMuestreo(dto.frecuencia_muestreo)
        heartbeat = Heartbeat(dto.heartbeat)

        config = ConfiguracionGlobal.crear(
            frecuencia_muestreo=frecuencia,
            heartbeat=heartbeat,
            id_usuario=usuario_actual.id_usuario,
            fecha_actualizacion=datetime.now(timezone.utc),
        )

        try:
            config_guardada = self.config_repo.guardar(config)
            self.auditoria_repo.registrar(
                id_configuracion_global=config_guardada.id_configuracion_global,
                id_usuario=usuario_actual.id_usuario,
                tipo_operacion="CREATE",
                valores_nuevos=config_guardada._snapshot(),
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        self.iot_port.notificar_configuracion(
            frecuencia_muestreo=config_guardada.frecuencia_muestreo.valor,
            heartbeat=config_guardada.heartbeat.valor,
        )
        return config_guardada
