"""Auditoría de credenciales MQTT y de la propagación de umbrales (RF-17) en la
bitácora IoT de modulo3 (RF-63).

Reutiliza ``RegistrarEventoAuditoriaIotUseCase`` de telemetry (hash de
integridad y clasificación incluidos), que ya es best-effort: un fallo de la
bitácora no rompe la emisión ni la revocación.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from src.configuration.domain.repositories.bitacora_iot_port import (
    BitacoraIotPort,
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


class BitacoraIotM03Adapter(BitacoraIotPort):

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

    def registrar_propagacion_umbral(
        self,
        *,
        evento: str,
        id_umbral_ambiental: int,
        id_usuario: int,
        estado: str,
        fallo: bool,
        detalle: dict,
    ) -> None:
        if estado == "APLICADA":
            resultado, severidad = TipoResultado.EXITOSO, SeveridadLog.INFO
        elif fallo:
            resultado, severidad = TipoResultado.FALLIDO, SeveridadLog.ERROR
        else:
            resultado, severidad = TipoResultado.ADVERTENCIA, SeveridadLog.WARNING
        RegistrarEventoAuditoriaIotUseCase(
            db=self.db, auditoria_repo=SqlAlchemyBitacoraAuditoriaIotRepository(self.db)
        ).execute(
            tipo_evento=evento,
            resultado=resultado,
            componente_origen=ComponenteOrigen.RF17,
            severidad_log=severidad,
            descripcion=f"Propagación del umbral {id_umbral_ambiental} al Nodo Edge: {estado}",
            entidad_afectada_tipo=EntidadAfectadaTipo.UMBRAL,
            entidad_afectada_id=str(id_umbral_ambiental),
            accion_detallada={"id_umbral_ambiental": id_umbral_ambiental, "estado": estado, **detalle},
            id_usuario=id_usuario,
        )
