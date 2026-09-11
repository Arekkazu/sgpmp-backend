"""Entidad de dominio ``Plantilla`` — plantilla de configuración reutilizable (RF-31).

Inmutable por diseño: una vez creada, no se modifica. Nuevas versiones se crean
como registros separados con el mismo template_name y version incrementada.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional


@dataclass(eq=False)
class Plantilla:
    """Plantilla de configuración con snapshot de parámetros productivos.

    Attributes:
        id_especie: Especie de origen del snapshot.
        id_usuario: Usuario que creó la plantilla.
        template_name: Nombre descriptivo. Único con version.
        params_snapshot: Snapshot JSONB con schema_version y categorías de params.
        version: Número de versión incremental (1, 2, 3, ...).
        fecha_creacion: Timestamp de creación.
        id_plantilla: PK. ``None`` hasta persistir.
    """

    id_especie: int
    id_usuario: int
    template_name: str
    params_snapshot: dict
    version: int
    fecha_creacion: datetime
    id_plantilla: Optional[int] = None

    @classmethod
    def crear(
        cls,
        *,
        id_especie: int,
        id_usuario: int,
        template_name: str,
        params_snapshot: dict,
        version: int,
        fecha_creacion: datetime,
    ) -> Plantilla:
        return cls(
            id_especie=id_especie,
            id_usuario=id_usuario,
            template_name=template_name,
            params_snapshot=params_snapshot,
            version=version,
            fecha_creacion=fecha_creacion,
        )

    def _snapshot(self) -> dict[str, Any]:
        return {
            'id_plantilla': self.id_plantilla,
            'id_especie': self.id_especie,
            'id_usuario': self.id_usuario,
            'template_name': self.template_name,
            'version': self.version,
            'params_snapshot': self.params_snapshot,
            'fecha_creacion': self.fecha_creacion.isoformat() if self.fecha_creacion else None,
        }

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Plantilla):
            return NotImplemented
        if self.id_plantilla is None or other.id_plantilla is None:
            return self is other
        return self.id_plantilla == other.id_plantilla

    def __hash__(self) -> int:
        return hash(self.id_plantilla)
