# | Fecha      | Nombre   | Que se hizo                                      |
# |------------|----------|--------------------------------------------------|
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Puerto de persistencia de despliegues OTA."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from src.prediction.domain.entities.despliegue_ota import DespliegueOta


class DespliegueOtaRepository(ABC):
    """Puerto de persistencia de despliegues OTA."""
    @abstractmethod
    def obtener_por_version(
        self,
        id_version: int,
        id_dispositivo: Optional[int] = None,
        estado: Optional[str] = None,
    ) -> list[DespliegueOta]:
        """Lista los despliegues de la versión."""
        ...

    @abstractmethod
    def listar(
        self,
        id_version: Optional[int] = None,
        id_dispositivo: Optional[int] = None,
        estado: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[DespliegueOta], int]:
        """Lista los despliegues con filtros."""
        ...

    @abstractmethod
    def obtener_por_id(self, id_despliegue: int, *, bloquear: bool = False) -> Optional[DespliegueOta]:
        """Devuelve el despliegue, opcionalmente bloqueado, o ``None``."""
        ...

    # ── DEV-15: orquestador OTA ─────────────────────────────────────────────

    @abstractmethod
    def crear(self, entidad: DespliegueOta) -> DespliegueOta:
        """Inserta un despliegue PENDIENTE. Un despliegue vigente del mismo
        (nodo, tipo_modelo, componente) viola la unicidad de DB-04 (409)."""
        ...

    @abstractmethod
    def actualizar(self, entidad: DespliegueOta) -> DespliegueOta:
        """Actualiza el despliegue."""
        ...

    @abstractmethod
    def listar_por_distribucion(self, id_distribucion: int, fase: Optional[str] = None) -> list[DespliegueOta]:
        """Lista los despliegues de la distribución, opcionalmente de una fase."""
        ...

    @abstractmethod
    def nodos_con_despliegue_vigente(
        self, ids_dispositivo: list[int], tipo_modelo: str, componente: Optional[str]
    ) -> list[int]:
        """Nodos que ya tienen un despliegue PENDIENTE o EN_PROCESO de ese componente."""
        ...

    @abstractmethod
    def version_instalada(self, id_dispositivo: int, tipo_modelo: str, componente: Optional[str]) -> Optional[int]:
        """Versión del último despliegue EXITOSO de ese componente en el nodo (la que tiene hoy)."""
        ...
