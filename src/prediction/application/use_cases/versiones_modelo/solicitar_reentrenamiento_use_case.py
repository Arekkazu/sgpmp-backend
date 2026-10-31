# | Fecha      | Nombre   | Que se hizo                                                        |
# |------------|----------|--------------------------------------------------------------------|
# | 2026-10-31 | Arekkazu | RF-71/RF-73: solicitud de reentrenamiento como evento de auditoría |
"""RF-71: solicitar el reentrenamiento de un modelo individual.

La solicitud no ejecuta el pipeline: queda en la bitácora de M04 (RF-73) como
``REENTRENAMIENTO_SOLICITADO``, con quién la pidió y con cuántas retroalimentaciones
nuevas. Solo se admite desde el mínimo de solicitud (200 por defecto).
"""
from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from src.prediction.application.use_cases.versiones_modelo.consultar_estado_reentrenamiento_use_case import (
    ConsultarEstadoReentrenamientoUseCase,
)
from src.prediction.domain.entities.estado_reentrenamiento import TIPOS_MODELO_INDIVIDUAL, EstadoReentrenamiento
from src.prediction.domain.repositories.evento_auditoria_m04_repository import EventoAuditoriaM04Repository
from src.shared.errors import BusinessRuleError, InfrastructureError, ValidationError


class SolicitarReentrenamientoUseCase:
    def __init__(
        self, *, db: Session, estado_use_case: ConsultarEstadoReentrenamientoUseCase,
        auditoria_repo: EventoAuditoriaM04Repository,
    ) -> None:
        self._db = db
        self._estado = estado_use_case
        self._auditoria = auditoria_repo

    def execute(self, tipo_modelo: str, motivo: Optional[str], id_usuario: int) -> tuple[EstadoReentrenamiento, UUID]:
        if tipo_modelo not in TIPOS_MODELO_INDIVIDUAL:
            raise ValidationError(
                "TIPO_MODELO_NO_INDIVIDUAL",
                f"Solo se solicita el reentrenamiento de los modelos individuales: {', '.join(TIPOS_MODELO_INDIVIDUAL)}.",
                field="tipo_modelo",
            )
        estado = next(e for e in self._estado.execute() if e.tipo_modelo == tipo_modelo)
        if estado.estado == "INSUFICIENTE":
            raise BusinessRuleError(
                "DATOS_INSUFICIENTES_REENTRENAMIENTO",
                f"Hay {estado.registros_nuevos} retroalimentaciones nuevas; faltan {estado.faltan} para poder "
                f"solicitar el reentrenamiento (desde {estado.minimo_solicitud}).",
            )
        try:
            resultado = self._auditoria.registrar(
                tipo_evento="REENTRENAMIENTO_SOLICITADO",
                tipo_actor="USUARIO",
                id_usuario=id_usuario,
                id_referencia=tipo_modelo,
                entidad_referencia="tipo_modelo",
                resultado_operacion="EXITOSO",
                payload_evento={
                    "tipo_modelo": tipo_modelo,
                    "registros_nuevos": estado.registros_nuevos,
                    "minimo_solicitud": estado.minimo_solicitud,
                    "minimo_reentrenamiento": estado.minimo_reentrenamiento,
                    "estado": estado.estado,
                    "desde": estado.desde.isoformat() if estado.desde else None,
                    "id_usuario_solicitante": id_usuario,
                    "motivo": motivo,
                },
            )
            if not resultado.aceptado:
                raise InfrastructureError("SOLICITUD_NO_REGISTRADA", "No se pudo registrar la solicitud de reentrenamiento.")
            self._db.commit()
        except Exception:
            self._db.rollback()
            raise
        return estado, resultado.id_evento
