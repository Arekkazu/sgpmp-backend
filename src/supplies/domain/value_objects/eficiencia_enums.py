"""Enums de dominio para la eficiencia alimenticia / ICA (RF-74 / CU-02).

Se mantienen como ``str``-``Enum`` en la aplicación; en la BD las columnas
correspondientes son ``varchar`` (ver ``cu02_gaps_bd_rf74.md``). Persistir/leer
usa siempre ``.value``.
"""
from __future__ import annotations

from enum import Enum


class PeriodoEvaluacion(str, Enum):
    """Ventana temporal sobre la que se calcula el ICA."""

    SEMANAL = "SEMANAL"
    MENSUAL = "MENSUAL"
    POR_CICLO = "POR_CICLO"


class ClasificacionCA(str, Enum):
    """Clasificación del índice según los umbrales del RF-74."""

    EXCELENTE = "EXCELENTE"   # CA < 2.0
    ACEPTABLE = "ACEPTABLE"   # 2.0 <= CA <= 3.5
    BAJA = "BAJA"             # 3.5 < CA <= 5.0
    CRITICA = "CRITICA"       # CA > 5.0


class EstadoResultadoCA(str, Enum):
    """Estado del resultado de un cálculo ICA."""

    CALCULADO = "CALCULADO"
    CA_NO_CALCULABLE = "CA_NO_CALCULABLE"


class TipoCalculo(str, Enum):
    """Origen del cálculo (auditoría / trazabilidad)."""

    MANUAL = "MANUAL"
    AUTOMATICO = "AUTOMATICO"
    REINTENTO_AUTOMATICO = "REINTENTO_AUTOMATICO"
    REINTENTO_MANUAL = "REINTENTO_MANUAL"


class CausaNoCalculo(str, Enum):
    """Causa por la que el ICA no es calculable (jerarquía de precedencia).

    Orden de precedencia (mayor a menor): SIN_PESO_INICIAL > SIN_PESO_FINAL >
    SIN_REGISTROS_CONSUMO > POBLACION_INVALIDA > PESO_INVALIDO >
    PESO_SIN_VARIACION_POSITIVA > DATO_INVALIDO.
    """

    SIN_PESO_INICIAL = "SIN_PESO_INICIAL"
    SIN_PESO_FINAL = "SIN_PESO_FINAL"
    SIN_REGISTROS_CONSUMO = "SIN_REGISTROS_CONSUMO"
    POBLACION_INVALIDA = "POBLACION_INVALIDA"
    PESO_INVALIDO = "PESO_INVALIDO"
    PESO_SIN_VARIACION_POSITIVA = "PESO_SIN_VARIACION_POSITIVA"
    DATO_INVALIDO = "DATO_INVALIDO"


class EstadoEjecucionBatch(str, Enum):
    """Estado de una corrida del motor batch ICA."""

    EN_EJECUCION = "EN_EJECUCION"
    COMPLETADO = "COMPLETADO"
    INTERRUMPIDO = "INTERRUMPIDO"


class EstadoItemCola(str, Enum):
    """Estado de un activo dentro de la cola de cálculo ICA."""

    EN_COLA = "EN_COLA"
    PROCESANDO = "PROCESANDO"
    COMPLETADO = "COMPLETADO"
    OMITIDO = "OMITIDO"


class MotivoEncolado(str, Enum):
    """Razón por la que un activo se envía a la cola."""

    LIMITE_SUPERADO = "LIMITE_SUPERADO"
    VENTANA_EXCEDIDA = "VENTANA_EXCEDIDA"
    INTERRUMPIDO = "INTERRUMPIDO"
    REINTENTO = "REINTENTO"


class CausaInterrupcionBatch(str, Enum):
    """Causa por la que una corrida del batch se interrumpe."""

    VENTANA_EXCEDIDA = "VENTANA_EXCEDIDA"
    MANUAL = "MANUAL"
