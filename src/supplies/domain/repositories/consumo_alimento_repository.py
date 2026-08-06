"""Puerto del repositorio de consumos de alimento (RF-75).

Expresado en términos de dominio: recibe y devuelve la entidad
``ConsumoAlimento``. La implementación SQLAlchemy hace ``flush`` interno; el
``commit`` lo emite el caso de uso.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, time
from decimal import Decimal
from typing import Optional

from src.supplies.domain.entities.consumo_alimento import ConsumoAlimento


@dataclass
class TipoAlimentoRef:
    """Vista de solo lectura del catálogo de tipos de alimento (RF-75)."""

    id_tipo_elemento: int
    nombre: str
    unidad_medida: str
    costo_unitario: Decimal
    estado: Optional[str]

    @property
    def esta_activo(self) -> bool:
        return (self.estado or "").upper() == "ACTIVO"


class ConsumoAlimentoRepository(ABC):
    """Contrato de persistencia de registros de consumo de alimento."""

    @abstractmethod
    def obtener_tipo_alimento(self, id_tipo_alimento: int) -> Optional[TipoAlimentoRef]:
        """Devuelve el tipo de alimento del catálogo o ``None`` si no existe."""
        raise NotImplementedError

    @abstractmethod
    def existe_duplicado_validado(
        self,
        *,
        id_activo_biologico: int,
        fecha_consumo: date,
        hora_suministro: Optional[time],
        tipo_alimento: str,
    ) -> bool:
        """Indica si ya existe un consumo VALIDADO con la misma clave de duplicidad."""
        raise NotImplementedError

    @abstractmethod
    def guardar(self, consumo: ConsumoAlimento) -> ConsumoAlimento:
        """Persiste un consumo nuevo y devuelve la entidad con los campos derivados."""
        raise NotImplementedError

    @abstractmethod
    def obtener_por_id(self, id_consumo: int) -> Optional[ConsumoAlimento]:
        """Devuelve el consumo por id o ``None`` si no existe."""
        raise NotImplementedError

    @abstractmethod
    def anular(self, consumo: ConsumoAlimento) -> ConsumoAlimento:
        """Aplica la anulación (solo estado y campos de anulación)."""
        raise NotImplementedError

    @abstractmethod
    def listar(
        self,
        *,
        id_activo_biologico: Optional[int] = None,
        fecha_desde: Optional[date] = None,
        fecha_hasta: Optional[date] = None,
        tipo_alimento: Optional[str] = None,
        estado_registro: Optional[str] = None,
    ) -> list[ConsumoAlimento]:
        """Lista consumos aplicando los filtros de búsqueda de RF-75."""
        raise NotImplementedError
