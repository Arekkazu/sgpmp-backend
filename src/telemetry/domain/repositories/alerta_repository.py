from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from src.telemetry.domain.entities.alerta import Alerta


class AlertaRepository(ABC):

    @abstractmethod
    def guardar(self, alerta: Alerta) -> Alerta: ...

    @abstractmethod
    def buscar_activa_duplicada(
        self,
        id_sensor: int,
        tipo_variable: str,
        ventana_min: int = 30,
    ) -> Optional[Alerta]: ...

    @abstractmethod
    def actualizar_deduplicacion(
        self,
        id_alerta: int,
        ultima_ocurrencia: datetime,
        nueva_severidad: Optional[str] = None,
    ) -> None: ...

    @abstractmethod
    def actualizar_estado(
        self,
        id_alerta: int,
        nuevo_estado: str,
        id_usuario: Optional[int],
        motivo: Optional[str],
        fecha_atencion: Optional[datetime] = None,
        fecha_resolucion: Optional[datetime] = None,
    ) -> Alerta: ...

    @abstractmethod
    def obtener_por_id(self, id_alerta: int) -> Optional[Alerta]: ...

    @abstractmethod
    def listar(
        self,
        estado: Optional[str] = None,
        severidad: Optional[str] = None,
        tipo_alerta: Optional[str] = None,
        id_sensor: Optional[int] = None,
        id_activo_biologico: Optional[int] = None,
        origen_evento: Optional[str] = None,
        fecha_desde: Optional[datetime] = None,
        fecha_hasta: Optional[datetime] = None,
        pagina: int = 1,
        por_pagina: int = 50,
    ) -> tuple[list[Alerta], int]: ...
