from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from src.biological_assets.domain.entities.activo_biologico import MarcaReconciliacion, RegistroRf46


class ReconciliacionAuditoriaRepository(ABC):
    """RF-52 E5: cruce entre el historial RF-46 y la bitácora RF-52.

    Las tablas del historial se nombran como en ``registros_rf46`` de la bitácora:
    eventos_activos, historicos_estados_activos, gestiones_fases, movimientos e
    historial_activos.
    """

    @abstractmethod
    def adquirir_turno(self) -> bool:
        """Toma el candado de la corrida para la transacción actual; False si otra réplica lo tiene."""

    @abstractmethod
    def ids_maximos(self) -> dict[str, int]:
        """Último id de cada tabla del historial."""

    @abstractmethod
    def ultimas_marcas(self, limite: int) -> list[MarcaReconciliacion]:
        """Marcas de las corridas anteriores, la más reciente primero."""

    @abstractmethod
    def registros_sin_bitacora(
        self,
        desde: dict[str, int],
        hasta: dict[str, int],
        bitacora_desde: datetime,
    ) -> list[RegistroRf46]:
        """Filas del historial con id en (desde, hasta] sin ninguna entrada de la bitácora
        registrada a partir de ``bitacora_desde`` que las referencie."""

    @abstractmethod
    def obtener_registro(self, tabla: str, id_registro: int) -> Optional[RegistroRf46]:
        """La fila del historial, o None si no existe o no forma parte de RF-46."""

    @abstractmethod
    def tiene_auditoria(self, tabla: str, id_registro: int) -> bool:
        """Si alguna entrada de la bitácora, que no sea un aviso de inconsistencia, la referencia."""
