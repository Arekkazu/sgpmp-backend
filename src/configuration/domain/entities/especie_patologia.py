"""Entidad de dominio ``EspeciePatologia`` — asociación patología ↔ especie (RF-16).

Read-model del pivot `modulo9.especies_patologias`. Incluye los campos de
la patología necesarios para la consulta por especie (FLUJO H).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from src.configuration.domain.value_objects.nombre_patologia import NombrePatologia


@dataclass(eq=False)
class EspeciePatologia:
    """Asociación entre una patología global y una especie específica.

    Attributes:
        id_especies_patologias: PK del pivot.
        id_patologia: FK a la patología global.
        id_especie: FK a la especie.
        nombre: Nombre de la patología (para respuestas al cliente).
        es_activo: Estado de la patología global.
        descripcion: Descripción de la patología (opcional).
        fecha_actualizacion: Para concurrencia optimista al editar.
    """

    id_especies_patologias: int
    id_patologia: int
    id_especie: int
    nombre: NombrePatologia
    es_activo: bool
    descripcion: Optional[str] = None
    fecha_actualizacion: Optional[datetime] = None

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, EspeciePatologia):
            return NotImplemented
        return self.id_especies_patologias == other.id_especies_patologias

    def __hash__(self) -> int:
        return hash(self.id_especies_patologias)
