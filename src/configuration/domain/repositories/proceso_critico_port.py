"""Puerto para verificar procesos críticos activos asociados a una especie.

Abstracción cross-módulo: el módulo ``configuration`` no puede importar
directamente de ``prediction`` (M04). Este puerto invierte la dependencia:
``configuration`` declara lo que necesita y M04 proveerá la implementación
real cuando esté disponible.

Mientras M04 no esté implementado, el adaptador stub
(``infrastructure/adapters/proceso_critico_stub.py``) siempre retorna ``False``.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class ProcesoCriticoPort(ABC):
    """Contrato para consultar si una especie tiene procesos críticos activos."""

    @abstractmethod
    def tiene_proceso_activo(self, id_especie: int) -> bool:
        """Indica si la especie tiene algún proceso crítico en ejecución.

        Un proceso crítico activo (ej: reentrenamiento de modelos IA en M04)
        impide desactivar la especie hasta que finalice.

        Args:
            id_especie: Especie a verificar.

        Returns:
            ``True`` si existe al menos un proceso crítico activo, ``False``
            en caso contrario.
        """
        raise NotImplementedError
