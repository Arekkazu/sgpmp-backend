from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy.orm import Session

from src.prediction.domain.repositories.evento_auditoria_m04_repository import EventoAuditoriaM04Repository
from src.prediction.infrastructure.models.evento_auditoria_m04_model import EventoAuditoriaM04Model
from src.shared.db_error_translator import raise_from_db_error


class SqlAlchemyEventoAuditoriaM04Repository(EventoAuditoriaM04Repository):
    def __init__(self, db: Session) -> None:
        self._db = db

    def registrar(
        self,
        *,
        tipo_evento: str,
        tipo_actor: str,
        payload_evento: dict,
        severidad_evento: str = "INFO",
        id_usuario: Optional[int] = None,
        id_sistema: Optional[str] = None,
        id_referencia: Optional[str] = None,
        entidad_referencia: Optional[str] = None,
        resultado_operacion: Optional[str] = None,
        correlacion_id: Optional[uuid.UUID] = None,
    ) -> None:
        try:
            self._db.add(
                EventoAuditoriaM04Model(
                    tipo_evento=tipo_evento,
                    tipo_actor=tipo_actor,
                    payload_evento=payload_evento,
                    severidad_evento=severidad_evento,
                    id_usuario=id_usuario,
                    id_sistema=id_sistema,
                    id_referencia=id_referencia,
                    entidad_referencia=entidad_referencia,
                    resultado_operacion=resultado_operacion,
                    correlacion_id=correlacion_id or uuid.uuid4(),
                    origen_registro="DESARROLLO_M04",
                )
            )
            self._db.flush()
        except Exception as exc:
            raise_from_db_error(exc)
