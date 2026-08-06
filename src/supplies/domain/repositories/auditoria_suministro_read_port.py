"""Puerto de lectura de la bitácora ``modulo5.auditorias_suministros`` (RF-80, CU-06).

Complementa a ``AuditoriaSuministroPort`` (solo escritura). ``tipo_operacion``
en ``FiltrosAuditoriaSuministro`` se valida como texto libre, no contra un
enum Python cerrado: la columna real mezcla los 8 valores de negocio de
RF-78/79/81 con los 4 genéricos ``INSERT/UPDATE/DELETE/SELECT`` que escriben
los triggers DML de otros CUs, y ambos deben ser filtrables desde este CU.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from src.supplies.domain.entities.evento_auditoria_suministro import EventoAuditoriaSuministroConsulta


@dataclass(frozen=True)
class FiltrosAuditoriaSuministro:
    tipo_operacion: Optional[str] = None
    id_usuario: Optional[int] = None
    fecha_desde: Optional[datetime] = None
    fecha_hasta: Optional[datetime] = None
    entidad_afectada: Optional[str] = None
    id_activo_biologico: Optional[int] = None
    id_ciclo_productivo: Optional[int] = None
    resultado: Optional[str] = None
    clasificacion_registro: Optional[str] = None
    pagina: int = 1
    registros_por_pagina: int = 50


class AuditoriaSuministroReadPort(ABC):
    """Contrato de consulta/exportación de la bitácora de auditoría de M05."""

    @abstractmethod
    def consultar(
        self, filtros: FiltrosAuditoriaSuministro
    ) -> tuple[list["EventoAuditoriaSuministroConsulta"], int]:
        """Retorna la página solicitada y el total de registros que matchean los filtros."""
        raise NotImplementedError

    @abstractmethod
    def obtener_por_id(self, id_auditoria_suministro: int) -> "EventoAuditoriaSuministroConsulta":
        """Retorna el detalle de un evento. Lanza ``NotFoundError`` si no existe."""
        raise NotImplementedError
