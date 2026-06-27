"""Entidad de dominio ``CicloBiologico`` — etapa del ciclo productivo por especie (RF-16)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from src.configuration.domain.value_objects.duracion_dias import DuracionDias
from src.configuration.domain.value_objects.nombre_etapa import NombreEtapa


@dataclass(eq=False)
class CicloBiologico:
    """Etapa del ciclo productivo asociada a una especie.

    Attributes:
        nombre: Nombre validado (único por especie, case-insensitive).
        duracion_dias: Duración estimada en días (> 0).
        id_especie: Especie a la que pertenece esta etapa.
        es_activo: Estado de disponibilidad.
        id_ciclo_biologico: Identidad. ``None`` hasta que se persiste.
        descripcion: Descripción opcional de la etapa.
        fecha_actualizacion: Timestamp de última modificación (concurrencia optimista).
    """

    nombre: NombreEtapa
    duracion_dias: DuracionDias
    id_especie: int
    es_activo: bool
    id_ciclo_biologico: Optional[int] = None
    descripcion: Optional[str] = None
    fecha_actualizacion: Optional[datetime] = None

    @classmethod
    def crear(
        cls,
        *,
        nombre: NombreEtapa,
        duracion_dias: DuracionDias,
        id_especie: int,
        descripcion: Optional[str] = None,
    ) -> CicloBiologico:
        return cls(
            nombre=nombre,
            duracion_dias=duracion_dias,
            id_especie=id_especie,
            descripcion=descripcion,
            es_activo=True,
        )

    def actualizar(
        self,
        *,
        nombre: NombreEtapa,
        duracion_dias: DuracionDias,
        descripcion: Optional[str],
        fecha_actualizacion: datetime,
    ) -> None:
        self.nombre = nombre
        self.duracion_dias = duracion_dias
        self.descripcion = descripcion
        self.fecha_actualizacion = fecha_actualizacion

    def desactivar(self) -> None:
        self.es_activo = False

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, CicloBiologico):
            return NotImplemented
        if self.id_ciclo_biologico is None or other.id_ciclo_biologico is None:
            return self is other
        return self.id_ciclo_biologico == other.id_ciclo_biologico

    def __hash__(self) -> int:
        return hash(self.id_ciclo_biologico)
