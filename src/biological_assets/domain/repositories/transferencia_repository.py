from __future__ import annotations

from abc import ABC, abstractmethod

from src.biological_assets.domain.entities.activo_biologico import PaginaHistorial, Transferencia


class TransferenciaRepository(ABC):

    @abstractmethod
    def guardar(self, transferencia: Transferencia) -> Transferencia:
        """Inserta el registro en movimientos y retorna la entidad con id asignado."""

    @abstractmethod
    def consultar_historial(
        self,
        id_activo: int,
        fecha_inicio: object = None,
        fecha_fin: object = None,
        categoria: object = None,
        pagina: int = 1,
        page_size: int = 20,
    ) -> PaginaHistorial:
        """Consolida todas las categorías históricas del activo y retorna paginado."""

    @abstractmethod
    def hay_transferencia_en_progreso(self, id_activo: int) -> bool:
        """Verifica si existe una transferencia concurrente en progreso para el activo."""
