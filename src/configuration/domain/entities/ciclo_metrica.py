"""Ciclo productivo de la especie y si admite una métrica como producto (RF-43 E-04)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CicloMetrica:
    """Un ciclo productivo de la especie de la métrica, marcado si la habilita."""
    id_ciclo_productivo: int
    nombre: str
    habilitada: bool
