"""Entidad de dominio ``TipoArea`` — catálogo administrable de tipos de área productiva (RF-20).

Python puro, sin dependencias de SQLAlchemy ni FastAPI.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(eq=False)
class TipoArea:
    """Tipo de área productiva del catálogo gestionado en Configuración (M09).

    Attributes:
        nombre: Nombre del tipo de área (ej. "Galpón"). Único en el catálogo.
        es_activo: Si es ``False``, no se ofrece al registrar nuevas áreas.
        id_tipo_area: Identidad. ``None`` hasta que se persiste.
        fecha_creacion: Timestamp de alta.
        fecha_actualizacion: Timestamp de la última desactivación/reactivación.
    """

    nombre: str
    es_activo: bool
    id_tipo_area: Optional[int] = None
    fecha_creacion: Optional[datetime] = None
    fecha_actualizacion: Optional[datetime] = None

    @classmethod
    def crear(cls, *, nombre: str, fecha_creacion: datetime) -> TipoArea:
        """Construye un tipo de área nuevo, aún sin persistir. Nace activo."""
        return cls(nombre=nombre, es_activo=True, fecha_creacion=fecha_creacion)

    def desactivar(self) -> None:
        """Marca el tipo de área como inactivo (baja lógica)."""
        self.es_activo = False

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, TipoArea):
            return NotImplemented
        if self.id_tipo_area is None or other.id_tipo_area is None:
            return self is other
        return self.id_tipo_area == other.id_tipo_area

    def __hash__(self) -> int:
        return hash(self.id_tipo_area)
