"""Puerto del repositorio de fallos persistentes del cálculo ICA (RF-74 / E5)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from src.supplies.domain.entities.fallo_calculo_ica import FalloCalculoICA
from src.supplies.domain.value_objects.eficiencia_enums import PeriodoEvaluacion


class FalloCalculoICARepository(ABC):
    @abstractmethod
    def registrar(self, fallo: FalloCalculoICA) -> FalloCalculoICA:
        """Registra (o actualiza el conteo de) un fallo abierto para (activo, período)."""
        raise NotImplementedError

    @abstractmethod
    def obtener_abierto(
        self, id_activo_biologico: int, periodo: Optional[PeriodoEvaluacion]
    ) -> Optional[FalloCalculoICA]:
        raise NotImplementedError

    @abstractmethod
    def listar_no_resueltos(self) -> list[FalloCalculoICA]:
        raise NotImplementedError

    @abstractmethod
    def marcar_resuelto(
        self, id_fallo: int, *, tipo_resolucion: str, cuando: datetime
    ) -> None:
        raise NotImplementedError
