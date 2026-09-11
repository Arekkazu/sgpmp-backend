"""Entidad de dominio ``AcumuladoCiclo`` (RF-78 — acumulado por instancia de ciclo).

Python puro. Read-model del acumulado de inversión de una instancia real de
ciclo productivo de un activo (clave ``id_gestion_fases``, no
``id_ciclo_productivo`` — ver ``anotaciones/modulo_5/cu05_gaps_bd_rf78_rf79.md``
Gap 1). La mutación real del acumulado la hace el trigger de BD
``trg_acumular_costo_ciclo`` (``INSERT ... ON CONFLICT DO UPDATE``, atómico);
esta entidad no expone ningún método que module ``acumulado_total_ciclo`` — solo
valida, **antes** de insertar una corrección, que el delta resultante no
dejaría el acumulado en negativo (FA-09), replicando en la app la misma
aritmética que aplicará el trigger.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Optional

from src.shared.errors import BusinessRuleError


@dataclass(eq=False)
class AcumuladoCiclo:
    """Acumulado de inversión de una instancia de ciclo productivo (``id_gestion_fases``)."""

    id_activo_biologico: int
    id_ciclo_productivo: int
    id_gestion_fases: int
    acumulado_total_ciclo: Decimal
    acumulado_por_categoria: dict[str, Decimal] = field(default_factory=dict)
    version_acumulado: int = 0
    estado: str = "ACTIVO"
    id_acumulado_ciclo: Optional[int] = None
    fecha_ultima_actualizacion: Optional[datetime] = None

    def validar_correccion_no_negativa(self, costo_original: Decimal, costo_nuevo: Decimal) -> Decimal:
        """Calcula el delta de una corrección y valida que no deje el acumulado en negativo.

        Devuelve el delta (``costo_nuevo - costo_original``) si es seguro aplicarlo.
        Lanza ``BusinessRuleError`` 422 (FA-09) si ``acumulado_total_ciclo + delta < 0``.
        """
        delta = costo_nuevo - costo_original
        resultante = self.acumulado_total_ciclo + delta
        if resultante < 0:
            raise BusinessRuleError(
                code="ACUMULADO_NEGATIVO",
                message=(
                    "No es posible registrar la corrección: el acumulado del ciclo "
                    f"resultante sería {resultante} (negativo). El registro original "
                    "permanece intacto."
                ),
                field="cantidad_corregida",
            )
        return delta

    def _snapshot(self) -> dict:
        """Estado actual en formato JSON-serializable, para auditoría."""
        return {
            "acumulado_total_ciclo": str(self.acumulado_total_ciclo),
            "acumulado_por_categoria": {
                categoria: str(monto) for categoria, monto in self.acumulado_por_categoria.items()
            },
            "version_acumulado": self.version_acumulado,
            "estado": self.estado,
        }

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, AcumuladoCiclo):
            return NotImplemented
        if self.id_acumulado_ciclo is None or other.id_acumulado_ciclo is None:
            return self is other
        return self.id_acumulado_ciclo == other.id_acumulado_ciclo

    def __hash__(self) -> int:
        return hash(self.id_acumulado_ciclo)
