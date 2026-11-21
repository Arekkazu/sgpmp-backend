# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-10 | Arekkazu | #512 RF-16/RF-37: ciclos productivos de la especie con sus fases en orden |
"""Ciclo productivo de una especie (RF-16): la secuencia ordenada de etapas que RF-37 usa como fases.

Las etapas son el catálogo (``ciclos_biologicos``); el ciclo productivo fija su orden. RF-37 abre el ciclo
de un activo en la primera fase y avanza en ese orden; M05 exige ese ciclo abierto (RF-75, RF-76)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from src.shared.errors import ConflictError, ValidationError


@dataclass(frozen=True)
class FaseCicloProductivo:
    id_ciclo_biologico: int
    nombre: str
    duracion_dias: int


@dataclass(eq=False)
class CicloProductivo:
    nombre: str
    id_especie: int
    fases: list[FaseCicloProductivo] = field(default_factory=list)
    id_ciclo_productivo: Optional[int] = None
    en_uso: bool = False  # algún activo tiene o tuvo una fase de este ciclo (RF-37)

    @property
    def duracion_dias(self) -> int:
        return sum(f.duracion_dias for f in self.fases)

    @classmethod
    def crear(cls, nombre: str, id_especie: int, fases: list[FaseCicloProductivo]) -> "CicloProductivo":
        ciclo = cls(nombre="", id_especie=id_especie)
        ciclo._definir(nombre, fases)
        return ciclo

    def redefinir(self, nombre: str, fases: list[FaseCicloProductivo]) -> None:
        """Con activos que ya lo usan solo cambia el nombre: sus fases son la historia de esos activos."""
        if self.en_uso and [f.id_ciclo_biologico for f in fases] != [f.id_ciclo_biologico for f in self.fases]:
            raise ConflictError(code="CICLO_PRODUCTIVO_EN_USO", field="id_ciclos_biologicos", message=(
                f"Hay animales o lotes que ya pasaron por el ciclo «{self.nombre}». Puede cambiarle el nombre, "
                "pero sus fases no se modifican. Cree un ciclo nuevo con las fases que necesita."))
        self._definir(nombre, fases)

    def _definir(self, nombre: str, fases: list[FaseCicloProductivo]) -> None:
        nombre = " ".join((nombre or "").split())
        if not 3 <= len(nombre) <= 100:
            raise ValidationError(code="NOMBRE_CICLO_INVALIDO", field="nombre",
                                  message="El nombre del ciclo debe tener entre 3 y 100 caracteres.")
        if not fases:
            raise ValidationError(code="CICLO_SIN_FASES", field="id_ciclos_biologicos",
                                  message="El ciclo productivo necesita al menos una fase.")
        ids = [f.id_ciclo_biologico for f in fases]
        if len(set(ids)) != len(ids):
            raise ValidationError(code="FASE_REPETIDA", field="id_ciclos_biologicos",
                                  message="Una etapa no puede aparecer dos veces en el mismo ciclo.")
        self.nombre, self.fases = nombre, list(fases)
