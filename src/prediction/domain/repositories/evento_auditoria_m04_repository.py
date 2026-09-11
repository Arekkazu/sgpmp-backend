from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from src.prediction.domain.entities.evento_auditoria_m04 import EventoAuditoriaM04


class EventoAuditoriaM04Repository(ABC):
    @abstractmethod
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
    ) -> None: ...

    @abstractmethod
    def consultar(
        self,
        *,
        tipo_evento: Optional[str] = None,
        fecha_desde: Optional[datetime] = None,
        fecha_hasta: Optional[datetime] = None,
        id_usuario: Optional[int] = None,
        id_sistema: Optional[str] = None,
        id_referencia: Optional[str] = None,
        severidad_evento: Optional[str] = None,
        pagina: int = 1,
        por_pagina: int = 50,
    ) -> tuple[list["EventoAuditoriaM04"], int]: ...

    @abstractmethod
    def obtener_por_id(self, id_evento: uuid.UUID) -> "EventoAuditoriaM04": ...
