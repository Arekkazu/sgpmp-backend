from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional
from uuid import UUID

from src.telemetry.domain.entities.evento_auditoria_iot import EventoAuditoriaIot


class BitacoraAuditoriaIotRepository(ABC):

    @abstractmethod
    def registrar(self, evento: EventoAuditoriaIot) -> EventoAuditoriaIot: ...

    @abstractmethod
    def obtener(self, id_evento: UUID) -> Optional[EventoAuditoriaIot]: ...

    @abstractmethod
    def listar(
        self,
        fecha_desde: Optional[datetime] = None,
        fecha_hasta: Optional[datetime] = None,
        tipo_evento: Optional[str] = None,
        severidad_log: Optional[str] = None,
        clasificacion_registro: Optional[str] = None,
        entidad_afectada_id: Optional[str] = None,
        resultado: Optional[str] = None,
        pagina: int = 1,
        por_pagina: int = 50,
    ) -> tuple[list[EventoAuditoriaIot], int]: ...

    @abstractmethod
    def listar_todos_para_verificacion(
        self,
        fecha_desde: Optional[datetime] = None,
        fecha_hasta: Optional[datetime] = None,
    ) -> list[EventoAuditoriaIot]: ...
