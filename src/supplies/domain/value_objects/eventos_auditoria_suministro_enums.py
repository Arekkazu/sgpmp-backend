# | Fecha      | Nombre           | Que se hizo                                   |
# |------------|------------------|-----------------------------------------------|
# | 2026-10-22 | Arekkazu         | M05 RF-80: catálogo completo y retención      |
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
    PRECIO_MANUAL_INGRESADO = "PRECIO_MANUAL_INGRESADO"
    ACUMULADO_ACTUALIZADO = "ACUMULADO_ACTUALIZADO"
    PROVISION_PENDIENTE = "PROVISION_PENDIENTE"
    CONSULTA_HISTORIAL_EJECUTADA = "CONSULTA_HISTORIAL_EJECUTADA"
    EXPORTACION_HISTORIAL_GENERADA = "EXPORTACION_HISTORIAL_GENERADA"
    EXPORTACION_HISTORIAL_ELIMINADA = "EXPORTACION_HISTORIAL_ELIMINADA"


# RF-80 Fase 3: estos eventos se retienen 5 años (NIC41); el resto 1 año (TECNICO).
# Un tipo que no esté en el catálogo de M05 se trata como NIC41 (ambigüedad → conservador).
_EVENTOS_NIC41 = {
    "SUMINISTRO_REGISTRADO",
    "SUMINISTRO_CORREGIDO",
    "ACUMULADO_ACTUALIZADO",
    "CICLO_CONSOLIDADO",
    "REPORTE_COSTOS_GENERADO",
}
_EVENTOS_CATALOGO = {e.value for e in TipoEventoAuditoriaSuministro}


def clasificar_retencion(tipo_operacion: str) -> tuple[str, str]:
    """Devuelve ``(clasificacion_registro, retencion_aplicable)`` de un evento (RF-80 Fase 3)."""
    if tipo_operacion in _EVENTOS_NIC41 or tipo_operacion not in _EVENTOS_CATALOGO:
        return "NIC41", "5 años"
    return "TECNICO", "1 año"


class ResultadoAuditoriaSuministro(str, Enum):
    """Mapea ``enum_auditoria_suministro_resultado`` (ya existente, sin cambios)."""

    EXITOSO = "EXITOSO"
    FALLIDO = "FALLIDO"
    RECHAZADO = "RECHAZADO"
