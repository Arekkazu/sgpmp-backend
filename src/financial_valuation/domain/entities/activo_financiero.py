# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-04 | Arekkazu | M06 RF-82/83: vista financiera del activo biológico (M02 + finca + titular) |
# | 2026-11-09 | destroyerban | INC-M06-326-G30 RF-85: la magnitud del activo descuenta lo cosechado desde el último pesaje |
"""Read-model del activo biológico que M06 necesita para valorarlo (NIC 41 ¶10, ¶12)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Optional

from src.financial_valuation.domain.value_objects.nic41 import CategoriaPrecio

ESTADOS_VALORABLES = ("ACTIVO", "EN_TRATAMIENTO")


@dataclass(frozen=True)
class DatosActivo:
    id_activo_biologico: int
    identificador: str
    tipo: str  # INDIVIDUAL | POBLACIONAL
    id_especie: int
    especie: str
    estado: str
    id_infraestructura: int
    id_finca: int
    finca: str
    numero_id_tributaria: Optional[str]
    razon_social: Optional[str]
    fecha_ingreso: date
    origen_financiero: Optional[str]  # compra | nacimiento | donacion | transferencia_interna
    costo_adquisicion: Optional[Decimal]
    soporte_documental: Optional[str]
    cantidad_actual: Optional[int]
    peso_kg: Optional[Decimal]  # INDIVIDUAL: último pesaje; POBLACIONAL: peso promedio por individuo
    id_evento_peso: Optional[int]
    id_dispositivo_iot: Optional[int]
    # RF-85: kg ya cosechados como producto de consumo después del último pesaje. M02 no baja el peso con las
    # cosechas, así que sin descontarlos cada cosecha se calcularía sobre el activo completo.
    kg_cosechados: Decimal = Decimal(0)

    @property
    def es_poblacional(self) -> bool:
        return self.tipo == "POBLACIONAL"

    @property
    def es_valorable(self) -> bool:
        """¶10 b: beneficios económicos futuros probables (activo en producción)."""
        return self.estado in ESTADOS_VALORABLES

    @property
    def cabezas(self) -> int:
        return (self.cantidad_actual or 0) if self.es_poblacional else 1

    def magnitud(self, categoria: str) -> tuple[Optional[Decimal], str]:
        """Magnitud física sobre la que se aplica el precio (RF-84; NIC 41 ¶15 agrupa por atributos)."""
        if categoria == CategoriaPrecio.POR_CABEZA.value:
            return Decimal(self.cabezas), "cabeza"
        if self.peso_kg is None:
            return None, "kg"
        return max(Decimal(0), Decimal(self.peso_kg) * self.cabezas - self.kg_cosechados), "kg"
