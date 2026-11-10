# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-04 | Arekkazu | M06 RF-82..94: puerto del módulo financiero |
# | 2026-11-09 | destroyerban | INC-M06-323-G27 RF-85 FA-1/FA-2: la cosecha pendiente continúa con precio o costos manuales |
"""Puerto de los eventos biológicos de M02 que disparan la medición por evento (RF-83, RF-85)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class EventoM02:
    id_evento: int
    id_activo_biologico: int
    fecha: datetime
    tipo: str  # CRECIMIENTO | PRODUCTIVO | BAJA | INGRESO | REPRODUCTIVO | SANITARIO | OTRO
    datos: dict = field(default_factory=dict)


class EventoM02Port(ABC):
    @abstractmethod
    def pendientes(self, limite: int) -> list[EventoM02]:
        """Eventos posteriores al reconocimiento aún sin procesar (incluye los encolados por un cierre)."""

    @abstractmethod
    def cosechas_pendientes(self) -> list[dict]:
        """Cosechas cuyo reconocimiento quedó pendiente, con activo, producto, cantidad y motivo (RF-85 FA-1/FA-2)."""

    @abstractmethod
    def cosecha_pendiente(self, id_evento: int) -> EventoM02 | None:
        """El evento productivo si su reconocimiento quedó pendiente (MEDICION_PENDIENTE, RF-85 FA-1/FA-2)."""

    @abstractmethod
    def registrar_procesamiento(self, id_evento: int, resultado: str, detalle: str | None) -> None: ...

    @abstractmethod
    def pendientes_del_titular(self, numero_id_tributaria: str) -> int: ...
