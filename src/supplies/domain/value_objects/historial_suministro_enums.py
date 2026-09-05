"""Enums de dominio del historial/trazabilidad de suministros (RF-81 / CU-04)."""
from __future__ import annotations

from enum import Enum


class TipoTrabajoHistorial(str, Enum):
    """Tipo de trabajo async encolado (motor RF-81)."""

    CONSULTA_PESADA = "CONSULTA_PESADA"  # nivel de volumen 3/4
    EXPORTACION = "EXPORTACION"          # > 10.000 registros


class OrigenPrecio(str, Enum):
    """Origen del precio resuelto de un registro (columna real en BD)."""

    MANUAL = "MANUAL"
    M40_AUTOMATICO = "M40_AUTOMATICO"


class NaturalezaCosto(str, Enum):
    """Naturaleza contable del costo (columna real en BD, ver RF-78)."""

    MANTENIMIENTO = "MANTENIMIENTO"
    INVERSION = "INVERSION"
    VENTA = "VENTA"


class TipoSuministroFiltro(str, Enum):
    """Valores admitidos del filtro ``tipo_suministro_filtro`` (RF-81).

    SERVICIO_VETERINARIO e INSEMINACION se aceptan en el contrato pero no
    tienen tabla origen en modulo5 todavía (ver gap doc) — siempre devuelven
    0 resultados hasta que existan.
    """

    ALIMENTO = "ALIMENTO"
    MEDICAMENTO = "MEDICAMENTO"
    SERVICIO_VETERINARIO = "SERVICIO_VETERINARIO"
    INSEMINACION = "INSEMINACION"
    TODOS = "TODOS"


class OrigenPrecioFiltro(str, Enum):
    MANUAL = "MANUAL"
    M40_AUTOMATICO = "M40_AUTOMATICO"
    TODOS = "TODOS"


class NivelVolumen(int, Enum):
    """Nivel de volumen histórico del activo (Restricción 11 de RF-81).

    Simplificación deliberada frente a los 4 niveles del RF: la configuración
    (``configuracion_batch_historial_suministros``) solo define dos umbrales
    (``umbral_nivel3``, ``umbral_nivel4``), que son los que determinan el modo
    de procesamiento (síncrono vs. asíncrono). Los antiguos Nivel 1 y Nivel 2
    del RF se colapsan aquí en ``NIVEL_1`` porque ambos son síncronos y no
    requieren un umbral propio — ver ``cu04_gaps_bd_rf77_rf81.md``.
    """

    NIVEL_1 = 1  # <= umbral_nivel3: síncrono
    NIVEL_3 = 3  # > umbral_nivel3 y <= umbral_nivel4: asíncrono obligatorio
    NIVEL_4 = 4  # > umbral_nivel4: asíncrono obligatorio
