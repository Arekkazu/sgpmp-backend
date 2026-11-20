# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-19 | Arekkazu | INC-M07-373-G37 RF-98: período de gracia del contrato contable configurable desde M09 |
"""Período de gracia de las versiones del contrato contable (RF-98 / RNF-98.10), configurable desde M09.

Mismo almacén y validación que los demás parámetros de M09 (``modulo4.parametros_mlops``). M07 lee
el mínimo y el valor por defecto en cada registro y deprecación; sin configurar, rigen 30 y 90 días.
"""
from __future__ import annotations

from src.configuration.application.use_cases.configuracion_global.parametros_alertas_use_case import (
    ParametrosAlertasUseCase,
)
from src.configuration.domain.entities.parametro_mlops import (
    RF98_GRACIA_DEFECTO,
    RF98_GRACIA_DEFECTO_BASE,
    RF98_GRACIA_MINIMA,
    RF98_GRACIA_MINIMA_BASE,
)

PARAMETROS_INTEGRACION_CONTABLE = {
    RF98_GRACIA_MINIMA: (RF98_GRACIA_MINIMA_BASE,
                         "Días mínimos que una versión deprecada del contrato contable sigue disponible"),
    RF98_GRACIA_DEFECTO: (RF98_GRACIA_DEFECTO_BASE,
                          "Días de gracia que se aplican cuando no se indica otro valor"),
}


class ParametrosIntegracionContableUseCase(ParametrosAlertasUseCase):
    catalogo = PARAMETROS_INTEGRACION_CONTABLE
    codigo_invalido, rf = "PARAMETRO_INTEGRACION_CONTABLE_INVALIDO", "la integración contable"

    def gracia(self) -> tuple[int, int]:
        """(mínimo, por defecto) efectivos, en días."""
        valores = {p.nombre: int(p.valor) for p in self.consultar()}
        return valores[RF98_GRACIA_MINIMA], valores[RF98_GRACIA_DEFECTO]
