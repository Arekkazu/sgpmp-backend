"""Entidad de dominio ``Patologia`` — catálogo global de patologías (RF-16).

M09 CU02 gestiona nombre, descripcion y es_activo.
Los campos de M04 (etiologia, categoria, etc.) son gestionados por Módulo de Predicción IA.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from src.configuration.domain.value_objects.nombre_patologia import NombrePatologia


@dataclass(eq=False)
class Patologia:
    """Patología del catálogo global.

    Attributes:
        nombre: Nombre validado y único globalmente (case-insensitive).
        es_activo: Estado de disponibilidad.
        id_patologia: Identidad. ``None`` hasta que se persiste.
        descripcion: Descripción opcional.
        fecha_actualizacion: Timestamp de última modificación (concurrencia optimista).
    """

    nombre: NombrePatologia
    es_activo: bool
    id_patologia: Optional[int] = None
    descripcion: Optional[str] = None
    fecha_actualizacion: Optional[datetime] = None

    @classmethod
    def crear(
        cls,
        *,
        nombre: NombrePatologia,
        descripcion: Optional[str] = None,
    ) -> Patologia:
        return cls(
            nombre=nombre,
            descripcion=descripcion,
            es_activo=True,
        )

    def actualizar(
        self,
        *,
        nombre: NombrePatologia,
        descripcion: Optional[str],
        fecha_actualizacion: datetime,
    ) -> None:
        self.nombre = nombre
        self.descripcion = descripcion
        self.fecha_actualizacion = fecha_actualizacion

    def desactivar(self) -> None:
        self.es_activo = False

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Patologia):
            return NotImplemented
        if self.id_patologia is None or other.id_patologia is None:
            return self is other
        return self.id_patologia == other.id_patologia

    def __hash__(self) -> int:
        return hash(self.id_patologia)
