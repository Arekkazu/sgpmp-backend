"""Entidad de dominio ``Sensor`` — sensor perteneciente a un dispositivo IoT (RF-22)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(eq=False)
class Sensor:
    nombre: str
    id_dispositivo_iot: int
    es_activo: bool
    categoria: Optional[str] = None
    id_sensores: Optional[int] = None

    @classmethod
    def crear(
        cls,
        *,
        nombre: str,
        id_dispositivo_iot: int,
        categoria: Optional[str] = None,
    ) -> Sensor:
        return cls(
            nombre=nombre,
            id_dispositivo_iot=id_dispositivo_iot,
            es_activo=True,
            categoria=categoria,
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Sensor):
            return NotImplemented
        if self.id_sensores is None or other.id_sensores is None:
            return self is other
        return self.id_sensores == other.id_sensores

    def __hash__(self) -> int:
        return hash(self.id_sensores)
