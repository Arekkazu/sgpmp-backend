"""Puerto de cambio de estado del activo biológico (RF-44).

RF-76 exige que, al registrar un medicamento con período de retiro, el activo
pase a ``EN_TRATAMIENTO``. Ese cambio es responsabilidad exclusiva de RF-44
(módulo 2). El módulo de suministros solo declara esta necesidad; la
implementación concreta (adapter) reutiliza el flujo de biological_assets y
participa en la MISMA transacción del caso de uso (``flush`` sin ``commit``).
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class EstadoActivoPort(ABC):
    """Contrato para transicionar el estado del activo vía RF-44."""

    @abstractmethod
    def marcar_en_tratamiento(self, id_activo: int, id_usuario: int, motivo: str) -> None:
        """Cambia el estado del activo a EN_TRATAMIENTO (RF-44).

        Debe ser idempotente: si el activo ya está EN_TRATAMIENTO, no realiza
        ningún cambio. No emite ``commit`` — lo hace el caso de uso.
        """
        raise NotImplementedError

    @abstractmethod
    def revertir_a_activo(self, id_activo: int, id_usuario: int, motivo: str) -> None:
        """Cambia el estado del activo a ACTIVO (RF-44, RF-76 pasos 11-13).

        Debe ser idempotente: si el activo ya está ACTIVO, no realiza ningún
        cambio. No emite ``commit`` — lo hace el caso de uso.
        """
        raise NotImplementedError
