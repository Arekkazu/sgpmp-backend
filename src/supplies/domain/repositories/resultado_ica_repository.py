"""Puerto del repositorio de resultados ICA (RF-74 / CU-02).

Expresado en términos de dominio: recibe/devuelve :class:`ResultadoICA`. La
implementación concreta (SQLAlchemy) vive en ``infrastructure/repositories``.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from src.supplies.domain.entities.resultado_ica import ResultadoICA
from src.supplies.domain.value_objects.eficiencia_enums import PeriodoEvaluacion


class ResultadoICARepository(ABC):
    """Contrato de persistencia/lectura de resultados ICA."""

    @abstractmethod
    def obtener_vigente(
        self, id_activo_biologico: int, periodo: PeriodoEvaluacion
    ) -> Optional[ResultadoICA]:
        """Devuelve el resultado vigente del activo para el período, o ``None``."""
        raise NotImplementedError

    @abstractmethod
    def listar_historial(
        self, id_activo_biologico: int, periodo: Optional[PeriodoEvaluacion] = None
    ) -> list[ResultadoICA]:
        """Historial (vigente + no vigentes) del activo, opcionalmente por período."""
        raise NotImplementedError

    @abstractmethod
    def guardar(self, resultado: ResultadoICA) -> ResultadoICA:
        """Persiste un resultado; si es vigente, desmarca el vigente anterior del
        mismo (activo, período) antes de insertar. Usa ``flush()`` (sin ``commit()``)."""
        raise NotImplementedError

    @abstractmethod
    def tiene_vigente_critica(self, id_activo_biologico: int) -> bool:
        """``True`` si el activo tiene algún resultado vigente clasificado ``CRITICA``
        (usado para priorizar en el batch — RF-74 FA-07)."""
        raise NotImplementedError
