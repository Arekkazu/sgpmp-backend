# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-04 | Arekkazu | M06 RF-82..94: puerto del módulo financiero |
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
    @abstractmethod
    def obtener(self) -> ConfiguracionContable: ...

    @abstractmethod
    def actualizar(self, tipo_cierre: str, pct_umbral: Decimal, dias_alerta: int, id_usuario: int) -> ConfiguracionContable: ...

    @abstractmethod
    def parametro_especie(self, id_especie: int) -> Optional[ParametroEspecie]: ...

    @abstractmethod
    def listar_parametros_especie(self) -> list[dict]: ...

    @abstractmethod
    def guardar_parametro_especie(self, parametro: ParametroEspecie, id_usuario: int) -> None: ...

    @abstractmethod
    def costos_venta_vigentes(self, id_especie: int) -> Optional[ParametroCostosVenta]: ...

    @abstractmethod
    def listar_costos_venta(self) -> list[dict]: ...

    @abstractmethod
    def guardar_costos_venta(self, id_especie: int, region: str, pct_transporte: Decimal, pct_comisiones: Decimal,
                             pct_impuestos: Decimal, id_usuario: int) -> int:
        """Desactiva el vigente de la especie y región y crea uno nuevo (historial, RNF-84-05)."""

    @abstractmethod
    def resolver_cuenta(self, tipo_hecho: str, sentido: str, id_especie: int,
                        subtipo_costo: Optional[str]) -> Optional[AsignacionCuenta]:
        """Par vigente más específico: especie y subtipo exactos antes que los generales."""

    @abstractmethod
    def listar_asignaciones(self) -> list[AsignacionCuenta]: ...

    @abstractmethod
    def guardar_asignacion(self, tipo_hecho: str, sentido: str, id_especie: Optional[int], subtipo_costo: Optional[str],
                           cuenta_debito: str, cuenta_credito: str, id_usuario: int) -> int: ...

    @abstractmethod
    def desactivar_asignacion(self, id_asignacion: int) -> bool: ...
