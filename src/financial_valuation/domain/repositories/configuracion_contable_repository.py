# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-04 | Arekkazu | M06 RF-82..94: puerto del módulo financiero |
# | 2026-11-14 | Arekkazu | INC-M06-365-G21 RF-84: costos de venta por especie y región (departamento de la finca) |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Puerto de la configuración contable: periodicidad, parámetros por especie, costos de venta y
matriz contable (RF-84, RF-88, RF-109)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Optional

from src.financial_valuation.domain.entities.contabilidad import (
    AsignacionCuenta,
    ConfiguracionContable,
    ParametroCostosVenta,
    ParametroEspecie,
)


class ConfiguracionContableRepository(ABC):
    """Puerto de la configuración contable."""
    @abstractmethod
    def obtener(self) -> ConfiguracionContable:
        """Devuelve la configuración vigente."""
        ...

    @abstractmethod
    def actualizar(self, tipo_cierre: str, pct_umbral: Decimal, dias_alerta: int, id_usuario: int) -> ConfiguracionContable:
        """Actualiza la configuración general."""
        ...

    @abstractmethod
    def parametro_especie(self, id_especie: int) -> Optional[ParametroEspecie]:
        """Devuelve el parámetro de la especie, o ``None``."""
        ...

    @abstractmethod
    def listar_parametros_especie(self) -> list[dict]:
        """Lista los parámetros por especie."""
        ...

    @abstractmethod
    def guardar_parametro_especie(self, parametro: ParametroEspecie, id_usuario: int) -> None:
        """Guarda el parámetro de la especie."""
        ...

    @abstractmethod
    def costos_venta_vigentes(self, id_especie: int, region: Optional[str] = None) -> Optional[ParametroCostosVenta]:
        """El vigente de la especie en la región del activo; si la región no tiene uno propio, el GENERAL."""

    @abstractmethod
    def listar_costos_venta(self) -> list[dict]:
        """Lista los costos de venta configurados."""
        ...

    @abstractmethod
    def guardar_costos_venta(self, id_especie: int, region: str, pct_transporte: Decimal, pct_comisiones: Decimal,
                             pct_impuestos: Decimal, id_usuario: int) -> int:
        """Desactiva el vigente de la especie y región y crea uno nuevo (historial, RNF-84-05)."""

    @abstractmethod
    def resolver_cuenta(self, tipo_hecho: str, sentido: str, id_especie: int,
                        subtipo_costo: Optional[str]) -> Optional[AsignacionCuenta]:
        """Par vigente más específico: especie y subtipo exactos antes que los generales."""

    @abstractmethod
    def listar_asignaciones(self) -> list[AsignacionCuenta]:
        """Lista las asignaciones de cuentas."""
        ...

    @abstractmethod
    def guardar_asignacion(self, tipo_hecho: str, sentido: str, id_especie: Optional[int], subtipo_costo: Optional[str],
                           cuenta_debito: str, cuenta_credito: str, id_usuario: int) -> int:
        """Guarda una asignación de cuentas."""
        ...

    @abstractmethod
    def desactivar_asignacion(self, id_asignacion: int) -> bool:
        """Desactiva la asignación; ``False`` si no existe."""
        ...
