from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from src.prediction.domain.entities.evento_auditoria_m04 import EventoAuditoriaM04
from src.prediction.domain.repositories.evento_auditoria_m04_repository import EventoAuditoriaM04Repository


class ConsultarAuditoriaM04UseCase:
    def __init__(self, db: Session, repo: EventoAuditoriaM04Repository) -> None:
        self._db = db
        self._repo = repo

    def listar(
        self,
        *,
        tipo_evento: Optional[str],
        fecha_desde: Optional[datetime],
        fecha_hasta: Optional[datetime],
        id_usuario: Optional[int],
        id_sistema: Optional[str],
        id_referencia: Optional[str],
        severidad_evento: Optional[str],
        pagina: int,
        por_pagina: int,
        id_usuario_consultor: int,
    ) -> tuple[list[EventoAuditoriaM04], int]:
        items, total = self._repo.consultar(
            tipo_evento=tipo_evento,
            fecha_desde=fecha_desde,
            fecha_hasta=fecha_hasta,
            id_usuario=id_usuario,
            id_sistema=id_sistema,
            id_referencia=id_referencia,
            severidad_evento=severidad_evento,
            pagina=pagina,
            por_pagina=por_pagina,
        )
        self._emitir_evento_consulta(id_usuario_consultor, total, tipo_evento, pagina)
        return items, total

    def obtener_por_id(self, id_evento: uuid.UUID, id_usuario_consultor: int) -> EventoAuditoriaM04:
        return self._repo.obtener_por_id(id_evento)

    def _emitir_evento_consulta(
        self,
        id_usuario: int,
        total_resultados: int,
        filtro_tipo_evento: Optional[str],
        pagina: int,
    ) -> None:
        try:
            self._repo.registrar(
                tipo_evento="CONSULTA_AUDITORIA_M04",
                tipo_actor="USUARIO",
                id_usuario=id_usuario,
                severidad_evento="INFO",
                payload_evento={
                    "total_resultados": total_resultados,
                    "filtro_tipo_evento": filtro_tipo_evento,
                    "pagina": pagina,
                },
            )
            self._db.commit()
        except Exception:
            self._db.rollback()
