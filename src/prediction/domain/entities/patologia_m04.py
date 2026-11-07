# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-25 | Arekkazu | INC-M04-139-G001 RF-64: version_catalogo es la del catálogo, no por patología |
# | 2026-10-25 | Arekkazu | USAB-M04 M4-02 RF-64: nombre y unidad de variables y nombre de la especie (read-model) |
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional

from src.prediction.domain.entities.patologia_variable import PatologiaVariable


@dataclass(eq=False)
class PatologiaM04:
    """``version_catalogo`` es la versión del catálogo completo en la que la
    patología se agregó o cambió por última vez (RF-64): cada alta, edición o
    inactivación sube la versión del catálogo."""
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
    # M4-02 (read-model): "221" no le dice nada al usuario. None con TODAS.
    nombre_especie: Optional[str] = None

    @classmethod
    def crear(
        cls,
        *,
        nombre: str,
        especie_aplicable: str,
        descripcion_clinica: str,
        variables: list[PatologiaVariable],
        id_usuario_creador: int,
        version_catalogo: int,
    ) -> PatologiaM04:
        return cls(
            nombre=nombre,
            especie_aplicable=especie_aplicable,
            descripcion_clinica=descripcion_clinica,
            es_base=False,
            es_activo=True,
            version_catalogo=version_catalogo,
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
        version_catalogo: int,
    ) -> None:
        self.nombre = nombre
        self.descripcion_clinica = descripcion_clinica
        self.variables = variables
        self.version_catalogo = version_catalogo
        self.fecha_actualizacion = fecha_actualizacion

    def desactivar(self, *, version_catalogo: int) -> None:
        # RF-64 regla 10: toda modificación de una patología no base es una versión nueva.
        self.es_activo = False
        self.version_catalogo = version_catalogo

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
