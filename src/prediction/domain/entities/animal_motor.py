# | Fecha      | Nombre   | Que se hizo                                                     |
# |------------|----------|-----------------------------------------------------------------|
# | 2026-11-02 | Arekkazu | RF-66/RF-69: animal individual que el motor IA debe atender      |
"""Read-model: un animal individual que el motor IA atiende y la versión que le toca."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class AnimalMotor:
    id_activo_biologico: int
    #: ``tipo_modelo_asignado`` del área (RF-20).
    tipo_modelo: str
    #: Versión propia del animal en ACTIVO o SOMBRA (RFC-010); None si todavía no tiene.
    id_version_modelo: Optional[int] = None
    nombre_version: Optional[str] = None
    hash_artefacto_sha256: Optional[str] = None
    fuente_datos: Optional[str] = None
