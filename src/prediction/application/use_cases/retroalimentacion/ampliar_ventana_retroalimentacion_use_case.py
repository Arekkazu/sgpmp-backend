# | Fecha      | Nombre   | Que se hizo                                                  |
# |------------|----------|--------------------------------------------------------------|
# | 2026-10-30 | Arekkazu | INC-M04-229-G070 RF-72: ampliación de ventana por resultado  |
"""RF-72: el administrador amplía la ventana de un resultado específico (registrado en RF-73).

Solo habilita ese resultado: la ventana global (``ventana_retroalimentacion_dias``) no cambia.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.prediction.domain.entities.ampliacion_ventana_retroalimentacion import AmpliacionVentanaRetroalimentacion
from src.prediction.domain.repositories.ampliacion_ventana_retroalimentacion_repository import (
    AmpliacionVentanaRetroalimentacionRepository,
)
from src.prediction.domain.repositories.evento_auditoria_m04_repository import EventoAuditoriaM04Repository
from src.prediction.domain.repositories.resultado_inferencia_port import ResultadoInferenciaPort
from src.shared.errors import NotFoundError


class AmpliarVentanaRetroalimentacionUseCase:
    def __init__(
        self,
        *,
        db: Session,
        repo: AmpliacionVentanaRetroalimentacionRepository,
        resultado_port: ResultadoInferenciaPort,
        auditoria_repo: EventoAuditoriaM04Repository,
    ) -> None:
        self._db = db
        self._repo = repo
        self._resultado_port = resultado_port
        self._auditoria_repo = auditoria_repo

    def execute(
        self, *, id_resultado_inferencia: uuid.UUID, dias_habilitados: int, justificacion: str, id_usuario: int,
    ) -> AmpliacionVentanaRetroalimentacion:
        if self._resultado_port.obtener_por_id(id_resultado_inferencia) is None:
            raise NotFoundError(
                code="RESULTADO_INFERENCIA_NO_ENCONTRADO",
                message="El resultado de inferencia no existe o no está disponible.",
            )
        entidad = AmpliacionVentanaRetroalimentacion.autorizar(
            id_resultado_inferencia=id_resultado_inferencia,
            dias_habilitados=dias_habilitados,
            justificacion=justificacion,
            id_usuario_autorizador=id_usuario,
            ahora=datetime.now(timezone.utc),
        )
        try:
            entidad = self._repo.guardar(entidad)
            self._db.commit()
        except Exception:
            self._db.rollback()
            raise

        self._auditoria_repo.registrar(
            tipo_evento="VENTANA_RETROALIMENTACION_AMPLIADA",
            tipo_actor="USUARIO",
            id_usuario=id_usuario,
            id_referencia=str(id_resultado_inferencia),
            entidad_referencia="resultado_inferencia",
            resultado_operacion="EXITOSO",
            severidad_evento="WARNING",
            payload_evento={**entidad._snapshot(), "dias_habilitados": dias_habilitados},
        )
        try:
            self._db.commit()
        except Exception:
            self._db.rollback()
        return entidad
