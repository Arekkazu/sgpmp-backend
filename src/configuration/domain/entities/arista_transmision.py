# | Fecha      | Nombre   | Que se hizo                                                     |
# |------------|----------|-----------------------------------------------------------------|
# | 2026-11-02 | Arekkazu | RFC-021 RF-110 C21.1: arista de transmisión entre dos áreas      |
"""Arista de la topología sanitaria (RF-110, RFC-021 §1.1): una vía por la que una enfermedad puede
pasar de un área a otra de la misma finca."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from src.shared.errors import BusinessRuleError

VIAS = ("PROXIMIDAD", "AIRE", "AGUA", "PERSONAL", "FOMITES", "ALIMENTO", "MOVIMIENTO_ANIMAL")
DIRECCIONES = ("DIRIGIDA", "BIDIRECCIONAL")


@dataclass
class AristaTransmision:
    id_infraestructura_origen: int
    id_infraestructura_destino: int
    via: str
    direccion: str
    intensidad: Decimal
    factor_barrera: Decimal = Decimal("1")
    origen_dato: str = "DECLARADA"
    descripcion: Optional[str] = None
    es_activo: bool = True
    id_usuario: Optional[int] = None
    id_arista_transmision: Optional[int] = None
    fecha_creacion: Optional[datetime] = None
    fecha_actualizacion: Optional[datetime] = None

    @classmethod
    def declarar(cls, *, id_infraestructura_origen: int, id_infraestructura_destino: int, via: str,
                 direccion: str, intensidad: Decimal, factor_barrera: Decimal, descripcion: Optional[str],
                 id_usuario: int) -> "AristaTransmision":
        if id_infraestructura_origen == id_infraestructura_destino:
            raise BusinessRuleError(
                code="ARISTA_MISMA_AREA",
                message="Una arista de transmisión une dos áreas distintas.",
                field="id_infraestructura_destino",
            )
        return cls(id_infraestructura_origen, id_infraestructura_destino, via, direccion, intensidad,
                   factor_barrera, descripcion=descripcion, id_usuario=id_usuario)

    @property
    def peso(self) -> Decimal:
        """w de RFC-021 §1.2 sin el término de bioseguridad del destino (llega con RF-20 v2.2)."""
        return self.intensidad * self.factor_barrera

    def desactivar(self) -> None:
        self.es_activo = False
        self.fecha_actualizacion = datetime.now(timezone.utc)
