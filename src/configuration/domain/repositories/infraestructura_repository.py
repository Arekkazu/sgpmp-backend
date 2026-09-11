"""Puerto de persistencia del agregado ``Infraestructura`` (RF-20)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from src.configuration.domain.entities.infraestructura import Infraestructura


class InfraestructuraRepository(ABC):

    @abstractmethod
    def obtener_por_id(
        self,
        id_infraestructura: int,
        *,
        ids_fincas_permitidas: Optional[list[int]] = None,
    ) -> Optional[Infraestructura]:
        raise NotImplementedError

    @abstractmethod
    def guardar(self, infraestructura: Infraestructura) -> Infraestructura:
        raise NotImplementedError

    @abstractmethod
    def actualizar(self, infraestructura: Infraestructura) -> Infraestructura:
        raise NotImplementedError

    @abstractmethod
    def listar_por_finca(
        self,
        id_finca: int,
        *,
        solo_activas: bool = False,
        ids_fincas_permitidas: Optional[list[int]] = None,
    ) -> list[Infraestructura]:
        raise NotImplementedError
