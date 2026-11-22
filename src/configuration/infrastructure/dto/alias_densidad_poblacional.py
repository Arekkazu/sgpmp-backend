# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-20 | Arekkazu | DEV-21 RF-15: densidad_poblacional_max con alias deprecado densidad_maxima_por_especie (RFC-012) |
"""RFC-012 / P-4: la ficha llama ``densidad_poblacional_max`` a la columna existente
``densidad_maxima_por_especie``. Se acepta cualquiera de los dos nombres, sin
renombrar la columna (mismo patrón que ``umbral_sin_senal``)."""
from decimal import Decimal, InvalidOperation

from pydantic import AliasChoices, Field

CANONICO = "densidad_poblacional_max"
ANTERIOR = "densidad_maxima_por_especie"


def campo_densidad():
    return Field(default=None, validation_alias=AliasChoices(CANONICO, ANTERIOR))


def validar_alias_densidad(datos):
    if isinstance(datos, dict) and CANONICO in datos and ANTERIOR in datos:
        try:
            iguales = (datos[CANONICO] is None and datos[ANTERIOR] is None) or Decimal(str(datos[CANONICO])) == Decimal(str(datos[ANTERIOR]))
        except (InvalidOperation, TypeError):
            iguales = False
        if not iguales:
            raise ValueError(f"{ANTERIOR} y {CANONICO} identifican el mismo parámetro y deben coincidir.")
        datos = {k: v for k, v in datos.items() if k != ANTERIOR}
    return datos


def validar_densidad(v):
    if v is None:
        return v
    if v <= 0:
        raise ValueError("La densidad poblacional máxima (ind/m²) debe ser mayor a cero.")
    if v != v.quantize(Decimal("0.01")):
        raise ValueError("La densidad poblacional máxima (ind/m²) admite máximo 2 decimales.")
    return v
