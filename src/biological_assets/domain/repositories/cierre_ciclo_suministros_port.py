# | Fecha      | Nombre           | Que se hizo                                   |
# |------------|------------------|-----------------------------------------------|
# | 2026-10-22 | Arekkazu         | M05 RF-38→RF-74/76/77/78/79: cierre de ciclo  |
"""Puerto hacia M05 para lo que el cierre del ciclo (RF-38) dispara en suministros.

- Antes de cerrar (la fase aún está activa): RF-76 exige que no queden
  tratamientos con retiro vigente (409) y RF-74 calcula el CA final del ciclo.
- Después de cerrar la fase, en la misma transacción: RF-78 Fase 9 / RF-79
  consolidan la inversión del ciclo y la entregan a M06; RF-77 deja el reporte
  final de gastos del ciclo.
- Tras el commit: avisos (consolidado potencialmente incompleto).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date


class CierreCicloSuministrosPort(ABC):
    @abstractmethod
    def antes_de_cerrar(self, id_activo: int, id_usuario: int, fecha_cierre: date) -> None:
        raise NotImplementedError

    @abstractmethod
    def despues_de_cerrar(self, id_activo: int, id_gestion_fases: int, id_usuario: int, fecha_cierre: date) -> None:
        raise NotImplementedError

    @abstractmethod
    def despues_del_commit(self) -> None:
        raise NotImplementedError
