"""Puerto de consulta del ciclo productivo abierto (RF-37 / RF-38 / RF-78).

Un activo tiene ciclo/fase productiva abierta cuando existe una fila activa en
``modulo2.gestiones_fases``. La ``fecha_inicio`` de esa fase es la
``fecha_cambio_fase`` usada como cota inferior de la fecha de consumo (RF-75).

``id_gestion_fases`` (no ``id_ciclo_productivo``, que es un catálogo/plantilla
reutilizable entre activos — ver ``anotaciones/modulo_5/cu05_gaps_bd_rf78_rf79.md``
Gap 1) es la clave real de "instancia de ciclo productivo de un activo" que
usa RF-78 para acumular costos. ``FaseProductiva``/``obtener_por_id`` se
agregan en CU-05 para que ``ConsolidarCicloUseCase`` pueda verificar que una
fase ya cerrada (``es_activa=False``) antes de permitir la consolidación
(RF-41 no existe como hook en la app — Gap 9).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class CicloAbierto:
    """Fase/ciclo productivo abierto de un activo."""

    id_ciclo_productivo: int
    fecha_inicio: Optional[datetime]
    id_gestion_fases: Optional[int] = None


@dataclass
class FaseProductiva:
    """Fase productiva de un activo, abierta o cerrada."""

    id_gestion_fases: int
    id_activo_biologico: int
    id_ciclo_productivo: int
    fecha_inicio: Optional[datetime]
    fecha_finalizacion: Optional[datetime]
    es_activa: bool


class CicloAbiertoPort(ABC):
    """Contrato para verificar si un activo tiene ciclo productivo abierto."""

    @abstractmethod
    def obtener_abierto(self, id_activo: int) -> Optional[CicloAbierto]:
        """Devuelve la fase activa del activo o ``None`` si no tiene ciclo abierto."""
        raise NotImplementedError

    @abstractmethod
    def obtener_por_id(self, id_gestion_fases: int) -> Optional[FaseProductiva]:
        """Devuelve la fase (abierta o cerrada) por ``id_gestion_fases``, o ``None``."""
        raise NotImplementedError
