"""Entidad de dominio ``Infraestructura`` — área productiva de una finca (RF-20)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from src.configuration.domain.value_objects.nombre_infraestructura import NombreInfraestructura
from src.configuration.domain.value_objects.superficie import Superficie


@dataclass(eq=False)
class Infraestructura:
    nombre: NombreInfraestructura
    tipo: str
    superficie: Superficie
    id_finca: int
    es_activo: bool
    id_infraestructura: Optional[int] = None
    descripcion: Optional[str] = None
    fecha_actualizacion: Optional[datetime] = None

    @classmethod
    def crear(
        cls,
        *,
        nombre: NombreInfraestructura,
        tipo: str,
        superficie: Superficie,
        id_finca: int,
        descripcion: Optional[str] = None,
    ) -> Infraestructura:
        return cls(
            nombre=nombre,
            tipo=tipo,
            superficie=superficie,
            id_finca=id_finca,
            descripcion=descripcion,
            es_activo=True,
        )

    def actualizar(
        self,
        *,
        nombre: NombreInfraestructura,
        tipo: str,
        superficie: Superficie,
        descripcion: Optional[str],
        fecha_actualizacion: datetime,
    ) -> None:
        self.nombre = nombre
        self.tipo = tipo
        self.superficie = superficie
        self.descripcion = descripcion
        self.fecha_actualizacion = fecha_actualizacion

    def desactivar(self) -> None:
        self.es_activo = False

    def _snapshot(self) -> dict:
        return {
            "nombre": self.nombre.valor,
            "tipo": self.tipo,
            "superficie": str(self.superficie.valor),
            "id_finca": self.id_finca,
            "descripcion": self.descripcion,
            "es_activo": self.es_activo,
            "fecha_actualizacion": self.fecha_actualizacion.isoformat() if self.fecha_actualizacion else None,
        }

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Infraestructura):
            return NotImplemented
        if self.id_infraestructura is None or other.id_infraestructura is None:
            return self is other
        return self.id_infraestructura == other.id_infraestructura

    def __hash__(self) -> int:
        return hash(self.id_infraestructura)
