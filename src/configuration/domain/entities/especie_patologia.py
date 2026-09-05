"""Entidad de dominio ``EspeciePatologia`` — patología por especie (RF-16).

Es la entidad **propia de M09** para patologías configuradas por especie. Vive en
la tabla `modulo9.especies_patologias`, que lleva el nombre, la descripción y el
estado de la patología a nivel de cada especie (únicos por especie,
case-insensitive). El catálogo clínico global `modulo9.patologias` es de M04; el
vínculo hacia él (``id_patologia``) es **opcional**: las patologías creadas por M09
lo dejan en ``None``.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from src.configuration.domain.value_objects.nombre_patologia import NombrePatologia


@dataclass(eq=False)
class EspeciePatologia:
    """Patología configurada para una especie concreta (config M09).

    Attributes:
        id_especie: FK a la especie a la que pertenece.
        nombre: Nombre validado, único por especie (case-insensitive).
        es_activo: Estado de disponibilidad (baja lógica).
        id_especies_patologias: Identidad. ``None`` hasta que se persiste.
        id_patologia: Vínculo opcional al catálogo clínico M04. ``None`` en las
            patologías creadas por M09.
        descripcion: Descripción opcional (propia por especie).
        fecha_actualizacion: Para concurrencia optimista al editar.
        fecha_creacion: Timestamp de creación.
    """

    id_especie: int
    nombre: NombrePatologia
    es_activo: bool
    id_especies_patologias: Optional[int] = None
    id_patologia: Optional[int] = None
    descripcion: Optional[str] = None
    fecha_actualizacion: Optional[datetime] = None
    fecha_creacion: Optional[datetime] = None

    @classmethod
    def crear(
        cls,
        *,
        id_especie: int,
        nombre: NombrePatologia,
        descripcion: Optional[str] = None,
    ) -> EspeciePatologia:
        return cls(
            id_especie=id_especie,
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

    def _snapshot(self) -> dict:
        return {
            "id_especies_patologias": self.id_especies_patologias,
            "id_especie": self.id_especie,
            "id_patologia": self.id_patologia,
            "nombre": self.nombre.valor,
            "descripcion": self.descripcion,
            "es_activo": self.es_activo,
            "fecha_actualizacion": (
                self.fecha_actualizacion.isoformat() if self.fecha_actualizacion else None
            ),
        }

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, EspeciePatologia):
            return NotImplemented
        if self.id_especies_patologias is None or other.id_especies_patologias is None:
            return self is other
        return self.id_especies_patologias == other.id_especies_patologias

    def __hash__(self) -> int:
        return hash(self.id_especies_patologias)
