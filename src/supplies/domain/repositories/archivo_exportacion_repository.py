# | Fecha      | Nombre           | Que se hizo                                   |
# |------------|------------------|-----------------------------------------------|
# | 2026-10-22 | Arekkazu         | M05 RF-77/RF-81: archivos exportados          |
"""Puerto de los archivos exportados de M05 (RF-77 y RF-81)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional
from uuid import UUID

from src.supplies.domain.entities.archivo_exportacion import ArchivoExportacion


class ArchivoExportacionRepository(ABC):
    @abstractmethod
    def guardar(self, archivo: ArchivoExportacion) -> ArchivoExportacion:
        raise NotImplementedError

    @abstractmethod
    def obtener(self, id_archivo: UUID) -> Optional[ArchivoExportacion]:
        raise NotImplementedError

    @abstractmethod
    def obtener_por_referencia(self, origen: str, id_referencia: int) -> Optional[ArchivoExportacion]:
        """El archivo más reciente generado para un trabajo/reporte."""
        raise NotImplementedError

    @abstractmethod
    def purgar_vencidos(self, ahora: datetime) -> list[ArchivoExportacion]:
        """Borra el contenido de los archivos vencidos y devuelve los purgados (RF-81 RNF-06)."""
        raise NotImplementedError
