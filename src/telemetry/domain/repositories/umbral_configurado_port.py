# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-28 | destroyerban | INC-M03-173-G85 RF-57 E9: ¿hay umbral RF-17 para la variable en el área? |
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class UmbralConfigurado:
    """``configurado`` False → E9 (regla ausente). Lo demás es diagnóstico para el administrador."""
    configurado: bool
    id_variable: Optional[int] = None
    especies: tuple[int, ...] = field(default_factory=tuple)
    motivo: Optional[str] = None   # VARIABLE_FUERA_DEL_CATALOGO | AREA_SIN_ESPECIES | SIN_UMBRAL_PARA_LAS_ESPECIES


class UmbralConfiguradoPort(ABC):
    @abstractmethod
    def consultar(self, tipo_variable: str, id_infraestructura: Optional[int]) -> UmbralConfigurado:
        """Si existe un umbral RF-17 activo de la variable para alguna especie del área (sin área:
        para cualquier especie)."""
