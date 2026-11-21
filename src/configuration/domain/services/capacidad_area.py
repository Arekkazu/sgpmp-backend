# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-20 | Arekkazu | DEV-22 RF-20: capacidad_efectiva y validaciones de capacidad por densidad (RFC-012) |
# | 2026-10-20 | Arekkazu | DEV-21 RF-15: AreaOcupada y validar_reduccion_densidad |
"""Regla de capacidad por densidad de un área multiespecie (RFC-012 v1.1, RF-20).

``capacidad_efectiva(area) = floor(MIN(densidad ind/m² de las especies presentes) × superficie)``
y ``Σ individuos ≤ capacidad_efectiva``. La comparten RF-20 (M09) y RF-33/36/48 (M02):
el techo se evalúa sobre el estado resultante y lo paga quien ingresa (H-12.3).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, replace
from decimal import Decimal
from typing import Iterable, Optional

from src.shared.errors import BusinessRuleError


@dataclass(frozen=True)
class EspecieDelArea:
    """Lo que la regla de capacidad necesita de cada especie presente en un área."""
    id_especie: int
    nombre: str
    grupo_manejo: Optional[str]
    densidad: Optional[Decimal]  # ind/m²; None = no configurada


@dataclass(frozen=True)
class AreaOcupada:
    """Área con individuos alojados, con lo necesario para recalcular su techo."""
    nombre: str
    superficie: Decimal
    especies: list[EspecieDelArea]
    carga: int


def capacidad_efectiva(superficie: Decimal, especies: Iterable[EspecieDelArea]) -> Optional[int]:
    """Individuos que caben en el área, o ``None`` si no hay especies o alguna no tiene densidad."""
    densidades = [e.densidad for e in especies]
    if not densidades or any(d is None for d in densidades):
        return None
    return math.floor(min(densidades) * Decimal(superficie))


def exigir_densidades(especies: Iterable[EspecieDelArea]) -> None:
    """422 si alguna especie presente no tiene densidad (H-12.4): no se opera la capacidad."""
    for e in especies:
        if e.densidad is None:
            raise BusinessRuleError(
                code="ESPECIE_SIN_DENSIDAD",
                message=(
                    f"Configuración faltante: la especie '{e.nombre}' no tiene densidad poblacional "
                    "máxima (ind/m²) definida. Configúrela en el catálogo de especies antes de "
                    "operar la capacidad del área."
                ),
                field="especies",
            )


def validar_capacidad(
    *,
    nombre_area: str,
    superficie: Decimal,
    especies: list[EspecieDelArea],
    carga_resultante: int,
    field: str = "especies",
) -> int:
    """422 si ``carga_resultante`` (Σ individuos tras la operación) supera la capacidad
    efectiva calculada con ``especies`` (las presentes tras la operación, entrante incluida).

    Devuelve la capacidad efectiva.
    """
    exigir_densidades(especies)
    densidad = min(e.densidad for e in especies)
    capacidad = capacidad_efectiva(superficie, especies)
    if carga_resultante > capacidad:
        raise BusinessRuleError(
            code="CAPACIDAD_EXCEDIDA",
            message=(
                f"Capacidad excedida: la carga del área '{nombre_area}' superaría su capacidad "
                f"efectiva ({capacidad} individuos = MIN densidad {densidad} ind/m² × superficie "
                f"{superficie} m²). Reduzca la cantidad o revise la mezcla de especies."
            ),
            field=field,
        )
    return capacidad


def validar_mismo_grupo(nombre_area: str, especies: list[EspecieDelArea]) -> Optional[str]:
    """R-MULTIESPECIE-01: 422 si las especies no comparten ``grupo_manejo``. Devuelve el grupo común."""
    grupo = especies[0].grupo_manejo if especies else None
    for e in especies[1:]:
        if e.grupo_manejo != grupo:
            raise BusinessRuleError(
                code="GRUPOS_MANEJO_INCOMPATIBLES",
                message=(
                    f"Grupos de manejo incompatibles: el área '{nombre_area}' aloja especies del grupo "
                    f"'{grupo}' y '{e.nombre}' pertenece a '{e.grupo_manejo}'. Un área solo admite "
                    "especies del mismo grupo de manejo."
                ),
                field="especies",
            )
    return grupo


def validar_reduccion_densidad(nombre_especie: str, id_especie: int, nueva: Decimal, areas: list[AreaOcupada]) -> None:
    """RF-15 (RFC-012): 422 si con ``nueva`` densidad algún área donde está la especie
    quedaría con más individuos que su capacidad efectiva. Las áreas cuyo techo ya era
    indefinido (otra especie sin densidad) no se evalúan."""
    for area in areas:
        especies = [replace(e, densidad=nueva) if e.id_especie == id_especie else e for e in area.especies]
        capacidad = capacidad_efectiva(area.superficie, especies)
        if capacidad is not None and area.carga > capacidad:
            raise BusinessRuleError(
                code="DENSIDAD_DEJA_AREA_EXCEDIDA",
                message=(
                    f"Operación denegada: con {nueva} ind/m² para '{nombre_especie}', el área "
                    f"'{area.nombre}' quedaría con {area.carga} individuos sobre una capacidad efectiva "
                    f"de {capacidad}. Resuelva primero el exceso del área."
                ),
                field="densidad_poblacional_max",
            )
