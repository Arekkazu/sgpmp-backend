"""Auditoría de credenciales MQTT en la bitácora IoT de modulo3 (RF-63).

Reutiliza ``RegistrarEventoAuditoriaIotUseCase`` de telemetry (hash de
integridad y clasificación incluidos), que ya es best-effort: un fallo de la
bitácora no rompe la emisión ni la revocación.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from src.configuration.domain.repositories.bitacora_credencial_mqtt_port import (
    BitacoraCredencialMqttPort,
)
from src.telemetry.application.use_cases.auditoria.registrar_evento_auditoria_iot_use_case import (
    RegistrarEventoAuditoriaIotUseCase,
)
from src.telemetry.domain.entities.evento_auditoria_iot import (
    ComponenteOrigen,
    EntidadAfectadaTipo,
    SeveridadLog,
    TipoResultado,
)
from src.telemetry.infrastructure.repositories.bitacora_auditoria_iot_repository import (
    SqlAlchemyBitacoraAuditoriaIotRepository,
)


class BitacoraCredencialMqttM03Adapter(BitacoraCredencialMqttPort):

    def __init__(self, db: Session) -> None:
        self.db = db

    def registrar(
        self,
        *,
        evento: str,
        exitoso: bool,
        id_dispositivo_iot: int,
        serial: str,
        id_usuario: int,
        detalle: dict,
    ) -> None:
        RegistrarEventoAuditoriaIotUseCase(
            db=self.db, auditoria_repo=SqlAlchemyBitacoraAuditoriaIotRepository(self.db)
        ).execute(
            tipo_evento=evento,
            resultado=TipoResultado.EXITOSO if exitoso else TipoResultado.FALLIDO,
            componente_origen=ComponenteOrigen.RF23,
            severidad_log=SeveridadLog.INFO if exitoso else SeveridadLog.WARNING,
            descripcion=f"{evento} para el dispositivo {serial}",
            entidad_afectada_tipo=EntidadAfectadaTipo.DISPOSITIVO,
            entidad_afectada_id=str(id_dispositivo_iot),
            accion_detallada={"serial": serial, **detalle},
            id_usuario=id_usuario,
        )
