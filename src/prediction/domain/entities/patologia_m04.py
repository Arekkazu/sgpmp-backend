from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional

from src.prediction.domain.entities.patologia_variable import PatologiaVariable


@dataclass(eq=False)
class PatologiaM04:
    nombre: str
    especie_aplicable: str
    descripcion_clinica: str
    es_base: bool
    es_activo: bool
    version_catalogo: int
    variables: list[PatologiaVariable]
    id_patologia: Optional[int] = None
    id_usuario_creador: Optional[int] = None
    fecha_creacion_m04: Optional[datetime] = None
    fecha_actualizacion: Optional[datetime] = None

    @classmethod
    def crear(
        cls,
        *,
        nombre: str,
        especie_aplicable: str,
        descripcion_clinica: str,
        variables: list[PatologiaVariable],
        id_usuario_creador: int,
    ) -> PatologiaM04:
        return cls(
            nombre=nombre,
            especie_aplicable=especie_aplicable,
            descripcion_clinica=descripcion_clinica,
            es_base=False,
            es_activo=True,
            version_catalogo=1,
            variables=variables,
            id_usuario_creador=id_usuario_creador,
        )

    def actualizar(
        self,
        *,
        nombre: str,
        descripcion_clinica: str,
        variables: list[PatologiaVariable],
        fecha_actualizacion: datetime,
    ) -> None:
        self.nombre = nombre
        self.descripcion_clinica = descripcion_clinica
        self.variables = variables
        self.version_catalogo += 1
        self.fecha_actualizacion = fecha_actualizacion

    def desactivar(self) -> None:
        self.es_activo = False

    def _snapshot(self) -> dict:
        return {
            "nombre": self.nombre,
            "especie_aplicable": self.especie_aplicable,
            "descripcion_clinica": self.descripcion_clinica,
            "es_base": self.es_base,
            "es_activo": self.es_activo,
            "version_catalogo": self.version_catalogo,
            "variables": [
                {
                    "id_variable_ambiental": v.id_variable_ambiental,
                    "peso_evidencia": str(v.peso_evidencia),
                    "es_variable_critica": v.es_variable_critica,
                }
                for v in self.variables
            ],
        }

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, PatologiaM04):
            return NotImplemented
        if self.id_patologia is None or other.id_patologia is None:
            return self is other
        return self.id_patologia == other.id_patologia

    def __hash__(self) -> int:
        return hash(self.id_patologia)
