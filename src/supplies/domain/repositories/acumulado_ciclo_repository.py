"""Puerto del repositorio de acumulados de ciclo (RF-78, CU-05).

Expresado en términos de dominio: recibe y devuelve ``AcumuladoCiclo``. La
mutación real del acumulado la hace el trigger de BD
``trg_acumular_costo_ciclo`` (ver ``anotaciones/modulo_5/cu05_gaps_bd_rf78_rf79.md``
Gap 6) — este puerto solo lee. ``obtener_bloqueando`` (``SELECT FOR UPDATE``)
se usa exclusivamente en el flujo de corrección, para leer el valor vigente
antes de decidir si el delta resultante dejaría el acumulado en negativo
(FA-09) — la propia inserción posterior la resuelve el trigger.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from src.supplies.domain.entities.acumulado_ciclo import AcumuladoCiclo


class AcumuladoCicloRepository(ABC):
    """Contrato de lectura del acumulado de inversión de una instancia de ciclo."""

    @abstractmethod
    def obtener(self, id_gestion_fases: int) -> Optional[AcumuladoCiclo]:
        """Devuelve el acumulado vigente, o ``None`` si aún no existe (ciclo sin suministros)."""
        raise NotImplementedError

    @abstractmethod
    def obtener_bloqueando(self, id_gestion_fases: int) -> Optional[AcumuladoCiclo]:
        """Igual que ``obtener`` pero con ``SELECT ... FOR UPDATE`` (solo flujo de corrección)."""
        raise NotImplementedError

    @abstractmethod
    def marcar_consolidado(self, id_gestion_fases: int) -> None:
        """Marca ``estado='CONSOLIDADO'`` tras el cierre definitivo del ciclo (informativo)."""
        raise NotImplementedError
