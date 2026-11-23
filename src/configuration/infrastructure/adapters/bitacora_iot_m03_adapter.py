# | Fecha      | Nombre   | Que se hizo                                      |
# |------------|----------|--------------------------------------------------|
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
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
    """Registra en la bitácora IoT las propagaciones de configuración."""

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
        """Best-effort: nunca lanza. ``detalle`` jamás debe incluir la contraseña."""
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
        """Un intento de propagar un umbral a sus Gateway Edge. Best-effort: nunca lanza.

        ``estado`` es el consolidado del umbral; ``fallo`` indica si RF-17 lo
        reporta como error (500) o si no hubo a quién/con qué enviarlo.
        """
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

    def registrar_propagacion_tipo_modelo(
        self,
        *,
        evento: str,
        id_dispositivo_iot: int,
        serial: str,
        id_infraestructura: int,
        id_usuario: int,
        estado: str,
        detalle: dict,
    ) -> None:
        """DEV-10: resultado de enviar el ``tipo_modelo_asignado`` de un área a UN Gateway Edge.

        Un evento por Gateway, sobre la entidad DISPOSITIVO. ``estado`` es el
        veredicto del broker (APLICADA / PENDIENTE / NO_CONF / SIN_INTEGRACION).
        Best-effort: nunca lanza.
        """
        if estado == "APLICADA":
            resultado, severidad = TipoResultado.EXITOSO, SeveridadLog.INFO
        elif estado == "NO_CONF":
            resultado, severidad = TipoResultado.FALLIDO, SeveridadLog.ERROR
        else:
            # PENDIENTE (Gateway desconectado) o sin broker en el ambiente: no se
            # intentó publicar, el nodo sigue con el modelo anterior.
            resultado, severidad = TipoResultado.ADVERTENCIA, SeveridadLog.WARNING
        RegistrarEventoAuditoriaIotUseCase(
            db=self.db, auditoria_repo=SqlAlchemyBitacoraAuditoriaIotRepository(self.db)
        ).execute(
            tipo_evento=evento,
            resultado=resultado,
            componente_origen=ComponenteOrigen.RF20,
            severidad_log=severidad,
            descripcion=(
                f"Propagación del tipo_modelo_asignado del área {id_infraestructura} "
                f"al Gateway Edge {serial}: {estado}"
            ),
            entidad_afectada_tipo=EntidadAfectadaTipo.DISPOSITIVO,
            entidad_afectada_id=str(id_dispositivo_iot),
            accion_detallada={
                "serial": serial,
                "id_infraestructura": id_infraestructura,
                "estado": estado,
                **detalle,
            },
            id_usuario=id_usuario,
        )
