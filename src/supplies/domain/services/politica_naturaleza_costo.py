"""Servicio de dominio: política de ``naturaleza_costo`` por tipo de suministro (RF-78).

**Pendiente real**: ``modulo9.especies`` no tiene ninguna columna de política de
capitalización por especie (RF-78 la menciona como "configurada en M09", pero
no existe — ver ``anotaciones/modulo_5/cu05_gaps_bd_rf78_rf79.md`` Gap 7, mismo
patrón que "M40 fuera de alcance" en CU-01). Esta función centraliza el default
documentado, aislada para reemplazarse sin tocar los use cases cuando M09
tenga la configuración real.
"""
from __future__ import annotations

from src.supplies.domain.value_objects.tipo_suministro import TipoSuministro

_NATURALEZA_POR_TIPO: dict[TipoSuministro, str] = {
    TipoSuministro.ALIMENTO: "MANTENIMIENTO",
    TipoSuministro.MEDICAMENTO: "MANTENIMIENTO",
    TipoSuministro.SERVICIO_VETERINARIO: "MANTENIMIENTO",
    TipoSuministro.INSEMINACION: "INVERSION",
}


def resolver_naturaleza_costo(tipo_suministro: str) -> str:
    """Resuelve la naturaleza de costo (MANTENIMIENTO/INVERSION) por tipo de suministro."""
    return _NATURALEZA_POR_TIPO[TipoSuministro(tipo_suministro)]
