"""Entidad de dominio ``Especie`` del contexto de configuración.

Python puro, sin dependencias de SQLAlchemy ni FastAPI. Concentra las reglas
de negocio del catálogo de especies productivas (RF-15).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional

from src.configuration.domain.value_objects.nombre_especie import NombreEspecie
from src.shared.tipo_modelo import tipo_modelo_de_grupo


@dataclass(eq=False)
class Especie:
    """Especie productiva del catálogo maestro del sistema.

    Attributes:
        nombre: Nombre validado y normalizado (value object).
        es_activo: Estado de disponibilidad en el sistema.
        id_especie: Identidad. ``None`` hasta que se persiste.
        descripcion: Descripción general opcional.
        fecha_creacion: Timestamp de alta. Lo asigna la aplicación al crear.
        fecha_actualizacion: Timestamp de la última modificación. Usado para
            control de concurrencia optimista en ediciones.
    """

    nombre: NombreEspecie
    es_activo: bool
    id_especie: Optional[int] = None
    descripcion: Optional[str] = None
    densidad_maxima_por_especie: Optional[Decimal] = None
    # RF-15 v1.1: clasificación productiva; de ella sale el modelo que RF-20 exige al área.
    grupo_manejo: Optional[str] = None
    fecha_creacion: Optional[datetime] = None
    fecha_actualizacion: Optional[datetime] = None

    @classmethod
    def crear(
        cls,
        *,
        nombre: NombreEspecie,
        descripcion: Optional[str],
        densidad_maxima_por_especie: Optional[Decimal] = None,
        grupo_manejo: Optional[str] = None,
        fecha_creacion: datetime,
    ) -> Especie:
        """Construye una especie nueva, aún sin persistir.

        La especie nace activa. El ``id_especie`` y ``fecha_actualizacion``
        son ``None`` hasta que el repositorio la guarda y la DB los asigna.
        """
        return cls(
            nombre=nombre,
            descripcion=descripcion,
            densidad_maxima_por_especie=densidad_maxima_por_especie,
            grupo_manejo=grupo_manejo,
            es_activo=True,
            fecha_creacion=fecha_creacion,
        )

    def actualizar(
        self,
        *,
        nombre: NombreEspecie,
        descripcion: Optional[str],
        densidad_maxima_por_especie: Optional[Decimal],
        fecha_actualizacion: datetime,
        grupo_manejo: Optional[str] = None,
    ) -> None:
        """Aplica los nuevos valores tras una edición validada."""
        self.nombre = nombre
        self.descripcion = descripcion
        self.densidad_maxima_por_especie = densidad_maxima_por_especie
        self.grupo_manejo = grupo_manejo
        self.fecha_actualizacion = fecha_actualizacion

    @property
    def tipo_modelo(self) -> Optional[str]:
        """Modelo de IA de la especie, derivado de ``grupo_manejo`` (mapeo 1:1)."""
        return tipo_modelo_de_grupo(self.grupo_manejo)

    def desactivar(self) -> None:
        """Marca la especie como inactiva (baja lógica)."""
        self.es_activo = False

    def activar(self) -> None:
        """Reactiva una especie previamente desactivada."""
        self.es_activo = True

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Especie):
            return NotImplemented
        if self.id_especie is None or other.id_especie is None:
            return self is other
        return self.id_especie == other.id_especie

    def __hash__(self) -> int:
        return hash(self.id_especie)
