# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-21 | Arekkazu | DEV-32 RF-57: umbrales de tormenta (E8) |
# | 2026-10-28 | destroyerban | INC-M03-166-G73 RF-57 CA-2: umbral mínimo de confianza de IA para PREDICCION_PATOLOGIA |
# | 2026-10-28 | destroyerban | INC-M03-167-G75 RF-57 E16: ventana de reevaluación por IA (valor base 60 min) |
# | 2026-10-28 | destroyerban | INC-M03-176-G57A RF-57: ventana de deduplicación y plazos SLA configurables (valores base del RF) |
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Optional


class ParametrosAlertasPort(ABC):
    @abstractmethod
    def obtener_confianza_edge_ia(self) -> Decimal:
        """Umbral configurable de resolución de conflictos E12/E13 de RF-57."""

    @abstractmethod
    def obtener_confianza_minima_ia(self) -> Decimal:
        """RF-57 CA-2: probabilidad mínima para generar PREDICCION_PATOLOGIA (valor base 0.75)."""

    @abstractmethod
    def obtener_ventana_reevaluacion_min(self) -> int:
        """RF-57 E16: minutos de la ventana de reevaluación por IA (valor base 60)."""

    @abstractmethod
    def obtener_ventana_deduplicacion_min(self) -> int:
        """RF-57 E4: minutos en los que un evento de la misma condición se consolida (valor base 30)."""

    @abstractmethod
    def obtener_sla_minutos(self) -> dict[str, int]:
        """RF-57 SLA por severidad, {CRITICO, MODERADO, LEVE} → minutos (valores base 5, 30, 120)."""

    @abstractmethod
    def obtener_umbrales_tormenta(self) -> Optional[tuple[int, int]]:
        """RF-57 E8: (alertas/min del sistema, alertas/min por unidad) que activan la
        tormenta, o ``None`` si no están configurados (sin agrupación)."""
