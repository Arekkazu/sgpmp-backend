# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-04 | Arekkazu | M06 RF-82..94: puerto del módulo financiero |
"""Puerto de los reportes del período: estado de resultados (RF-93) e informe de revelaciones (RF-92)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional


class ReporteRepository(ABC):
    @abstractmethod
    def movimientos(self, id_periodo_contable: int, filtros: dict) -> list[dict]:
        """Líneas REGISTRADAS del período con activo, especie, finca e infraestructura."""

    @abstractmethod
    def agregar_estado(self, datos: dict) -> int: ...

    @abstractmethod
    def obtener_estado(self, id_estado: int) -> Optional[dict]: ...

    @abstractmethod
    def aprobar_estado(self, id_estado: int, id_usuario: int) -> None: ...

    @abstractmethod
    def listar_estados(self, id_periodo_contable: int) -> list[dict]: ...

    @abstractmethod
    def siguiente_version_estado(self, id_periodo_contable: int) -> int: ...

    @abstractmethod
    def datos_revelaciones(self, id_periodo_contable: int) -> dict:
        """Insumos de RF-92: activos, rollforward, supuestos, precios, costo, riesgos."""

    @abstractmethod
    def agregar_informe(self, datos: dict) -> int: ...

    @abstractmethod
    def obtener_informe(self, id_informe: int) -> Optional[dict]: ...

    @abstractmethod
    def aprobar_informe(self, id_informe: int, id_usuario: int) -> None:
        """Aprueba y archiva la versión APROBADA anterior del período (RF-92 R4)."""

    @abstractmethod
    def rechazar_informe(self, id_informe: int, razon: str) -> None: ...

    @abstractmethod
    def listar_informes(self, id_periodo_contable: int) -> list[dict]: ...

    @abstractmethod
    def siguiente_version_informe(self, id_periodo_contable: int) -> int: ...
