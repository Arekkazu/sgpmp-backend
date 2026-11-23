# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-04 | Arekkazu | M06 RF-82..94: puerto del módulo financiero |
# | 2026-11-05 | Arekkazu | M06 RF-94: orden descendente y conteo por severidad |
# | 2026-11-13 | Arekkazu | QA-M06 CU13 H-02 C3 RF-94: autores de la bitácora por nombre |
# | 2026-11-14 | Arekkazu | INC-M06-365-G93 RF-94: la auditoría se acota a los titulares de las fincas del usuario |
# | 2026-11-22 | Arekkazu | DOCS-pdoc: docstrings de módulo, clase y métodos |
"""Puerto de la auditoría inmutable de M06 (RF-94)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from src.financial_valuation.domain.entities.contabilidad import EventoAuditoria


class AuditoriaFinancieraRepository(ABC):
    """Puerto de la auditoría financiera."""
    @abstractmethod
    def registrar(self, evento: EventoAuditoria) -> None:
        """Registra un evento de auditoría."""
        ...

    @abstractmethod
    def consultar(self, filtros: dict, pagina: int, tamano: int, descendente: bool = False) -> tuple[int, list[dict]]:
        """Consulta eventos filtrados y paginados; devuelve el total y la página."""
        ...

    @abstractmethod
    def conteo_por_severidad(self, filtros: dict) -> dict[str, int]:
        """Cuenta los eventos filtrados por severidad."""
        ...

    @abstractmethod
    def actores(self, filtros: dict) -> list[dict]:
        """Usuarios que firmaron eventos con esos filtros: ``id_usuario`` y ``nombre`` (RF-94 Fase 7)."""

    @abstractmethod
    def en_alcance(self, id_periodo_contable: Optional[int], id_activo_biologico: Optional[int]) -> bool:
        """El período y el activo (los que vengan) son de los titulares de las fincas del usuario, o es Administrador."""
