# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-08 | Arekkazu | RFC-025 RF-80 v2.0 RNF-08: orden por fecha del evento o de emisión |
# | Fecha | Nombre | Que se hizo |
# |-------|--------|-------------|
# | 2026-11-08 | Leandro | INC-M05-276-G38 RF-80: rechazar rangos temporales invertidos antes de consultar o exportar. |
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
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from src.shared.errors import ValidationError

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
    ordenar_por: str = "fecha_evento"  # RNF-08: fecha_evento (registro) o fecha_emision (emisión en M05)

    def __post_init__(self) -> None:
        if self.fecha_desde is None or self.fecha_hasta is None:
            return
        # Igual que el contrato de entrada: un instante sin zona representa UTC.
        # Comparar instantes permite offsets diferentes sin alterar los filtros.
        desde = self.fecha_desde
        hasta = self.fecha_hasta
        if desde.tzinfo is None:
            desde = desde.replace(tzinfo=timezone.utc)
        if hasta.tzinfo is None:
            hasta = hasta.replace(tzinfo=timezone.utc)
        if desde.astimezone(timezone.utc) > hasta.astimezone(timezone.utc):
            raise ValidationError(
                code="VAL_ENTRADA",
                message=(
                    "El inicio del rango no puede ser posterior al final. "
                    "Corrige las fechas e intenta de nuevo."
                ),
                field="fecha_hasta",
            )


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
