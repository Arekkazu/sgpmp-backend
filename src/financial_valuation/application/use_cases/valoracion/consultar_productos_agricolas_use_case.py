# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-11-09 | destroyerban | INC-M06-325-G30 RF-85 RNF-85-05: historial de productos con filtros, evento y usuario |
"""Caso de uso RF-85 RNF-85-05: historial de productos agrícolas reconocidos con filtros.

Filtros por activo, período, tipo de producto y rango de valores (más especie y producto, que el listado de la
pantalla también usa). Cada registro trae su evento productivo (RNF-85-03) y el usuario que lo registró."""
from __future__ import annotations

from src.financial_valuation.domain.repositories.valoracion_repository import ValoracionRepository
from src.shared.errors import ValidationError


class ConsultarProductosAgricolasUseCase:
    def __init__(self, valoraciones: ValoracionRepository) -> None:
        self.valoraciones = valoraciones

    def execute(self, filtros: dict) -> list[dict]:
        minimo, maximo = filtros.get("valor_min"), filtros.get("valor_max")
        if minimo is not None and maximo is not None and minimo > maximo:
            raise ValidationError(code="RANGO_VALOR_INVALIDO", field="valor_min",
                                  message="El valor mínimo no puede ser mayor que el valor máximo.")
        return self.valoraciones.productos_agricolas(filtros)
