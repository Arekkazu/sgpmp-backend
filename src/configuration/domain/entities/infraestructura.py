# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-20 | Arekkazu | DEV-22 RF-20: id_especies (1..N), nivel_criticidad y capacidad_maxima derivada |
"""Entidad de dominio ``Infraestructura`` — área productiva de una finca (RF-20)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from src.configuration.domain.value_objects.nombre_infraestructura import NombreInfraestructura
from src.configuration.domain.value_objects.superficie import Superficie


@dataclass(eq=False)
class Infraestructura:
    """Área productiva de una finca (corral, estanque, galpón...) con tipo y superficie
    en m² (RF-20).
    """
    nombre: NombreInfraestructura
    tipo: str
    superficie: Superficie
    id_finca: int
    es_activo: bool
    id_infraestructura: Optional[int] = None
    descripcion: Optional[str] = None
    fecha_actualizacion: Optional[datetime] = None
    # RFC-012: 1..N especies del mismo grupo de manejo, en orden de asociación.
    id_especies: list[int] = field(default_factory=list)
    # RF-20 v1.1 (RFC-009): modelo de IA que M04 le aplica, único por área.
    tipo_modelo_asignado: Optional[str] = None
    # RFC-016: ALTA / MEDIA / BAJA, insumo de la priorización bajo saturación (RF-53 E15).
    nivel_criticidad: str = "MEDIA"
    # RFC-012: derivada (capacidad_efectiva); la llena el repositorio al leer, no se edita.
    capacidad_maxima: Optional[int] = None

    @property
    def id_especie(self) -> Optional[int]:
        """La especie del área si tiene una sola; ``None`` si tiene varias o ninguna."""
        # ponytail: compatibilidad de lectura para RF-24 visión hasta DEV-24 (una línea base por especie).
        return self.id_especies[0] if len(self.id_especies) == 1 else None

    @classmethod
    def crear(
        cls,
        *,
        nombre: NombreInfraestructura,
        tipo: str,
        superficie: Superficie,
        id_finca: int,
        descripcion: Optional[str] = None,
        id_especies: Optional[list[int]] = None,
        tipo_modelo_asignado: Optional[str] = None,
        nivel_criticidad: str = "MEDIA",
    ) -> Infraestructura:
        return cls(
            nombre=nombre,
            tipo=tipo,
            superficie=superficie,
            id_finca=id_finca,
            descripcion=descripcion,
            es_activo=True,
            id_especies=list(id_especies or []),
            tipo_modelo_asignado=tipo_modelo_asignado,
            nivel_criticidad=nivel_criticidad,
        )

    def actualizar(
        self,
        *,
        nombre: NombreInfraestructura,
        tipo: str,
        superficie: Superficie,
        descripcion: Optional[str],
        fecha_actualizacion: datetime,
        id_especies: Optional[list[int]] = None,
        tipo_modelo_asignado: Optional[str] = None,
        nivel_criticidad: Optional[str] = None,
    ) -> None:
        self.nombre = nombre
        self.tipo = tipo
        self.superficie = superficie
        self.descripcion = descripcion
        self.fecha_actualizacion = fecha_actualizacion
        if id_especies is not None:
            self.id_especies = list(id_especies)
        self.tipo_modelo_asignado = tipo_modelo_asignado
        if nivel_criticidad is not None:
            self.nivel_criticidad = nivel_criticidad

    def desactivar(self) -> None:
        self.es_activo = False

    def activar(self) -> None:
        self.es_activo = True

    def _snapshot(self) -> dict:
        return {
            "nombre": self.nombre.valor,
            "tipo": self.tipo,
            "superficie": str(self.superficie.valor),
            "id_finca": self.id_finca,
            "descripcion": self.descripcion,
            "es_activo": self.es_activo,
            "id_especies": list(self.id_especies),
            "tipo_modelo_asignado": self.tipo_modelo_asignado,
            "nivel_criticidad": self.nivel_criticidad,
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
