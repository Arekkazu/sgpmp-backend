# | Fecha      | Nombre       | Que se hizo |
# |------------|--------------|-------------|
# | 2026-10-28 | destroyerban | INC-M03-171-G78 RF-57: catálogo de los filtros del listado de alertas (400 en vez de 500) |
"""Valores admitidos en los filtros de ``GET /iot/alertas`` y ``GET /iot/alertas-tecnicas``.

Son los enums de ``modulo3.alertas`` en la BD. Un valor fuera del catálogo llegaba al ``CAST`` a enum de
PostgreSQL y respondía 500; con estos tipos, FastAPI lo rechaza en la frontera y el handler global
responde 400 VAL_ENTRADA, con el campo y los valores admitidos.
"""
from typing import Annotated, Literal, Optional

from pydantic import BeforeValidator


def _vacio_es_sin_filtro(valor):
    # ``?estado=`` siempre significó "sin filtro" (respondía 200); se conserva.
    return None if valor == "" else valor


def _filtro(*valores):
    return Annotated[Optional[Literal[valores]], BeforeValidator(_vacio_es_sin_filtro)]


FiltroEstadoAlerta = _filtro("ACTIVA", "EN_ATENCION", "RESUELTA", "DESCARTADA", "VENCIDA", "PENDIENTE_SINCRONIZACION")
FiltroSeveridadAlerta = _filtro("LEVE", "MODERADO", "CRITICO")
FiltroTipoAlerta = _filtro(
    "ESTRES_TERMICO", "SINDROME_RESPIRATORIO", "RIESGO_HIDRICO", "FIEBRE", "INACTIVIDAD_ANORMAL", "FALLO_AMBIENTAL",
    "PREDICCION_PATOLOGIA", "TORMENTA_DE_ALERTAS", "TECNICA", "CONVERSION_ALIMENTICIA", "RIESGO_CONTAGIO",
)
FiltroOrigenEventoAlerta = _filtro("EDGE", "BACKEND", "IA", "HEARTBEAT", "EVALUACION_PERIODICA")
