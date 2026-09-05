"""Eventos de negocio de RF-78/RF-79 registrados en ``auditorias_suministros``.

Mapea los 8 valores agregados a ``modulo5.enum_auditoria_suministro_tipo_operacion``
(ver ``anotaciones/modulo_5/cu05_gaps_bd_rf78_rf79.md`` Gap 4), coexistiendo con
los valores genéricos ``INSERT``/``UPDATE``/``DELETE``/``SELECT`` usados por los
triggers de auditoría DML de CU-01/02/04.
"""
from __future__ import annotations

from enum import Enum


class TipoEventoAuditoriaSuministro(str, Enum):
    SUMINISTRO_REGISTRADO = "SUMINISTRO_REGISTRADO"
    SUMINISTRO_CORREGIDO = "SUMINISTRO_CORREGIDO"
    REGISTRO_FALLIDO = "REGISTRO_FALLIDO"
    CONFLICTO_CONCURRENCIA = "CONFLICTO_CONCURRENCIA"
    CICLO_CONSOLIDADO = "CICLO_CONSOLIDADO"
    PROVISION_INCREMENTAL_ENTREGADA = "PROVISION_INCREMENTAL_ENTREGADA"
    PROVISION_INCREMENTAL_FALLIDA = "PROVISION_INCREMENTAL_FALLIDA"
    REPORTE_COSTOS_GENERADO = "REPORTE_COSTOS_GENERADO"


class ResultadoAuditoriaSuministro(str, Enum):
    """Mapea ``enum_auditoria_suministro_resultado`` (ya existente, sin cambios)."""

    EXITOSO = "EXITOSO"
    FALLIDO = "FALLIDO"
    RECHAZADO = "RECHAZADO"
