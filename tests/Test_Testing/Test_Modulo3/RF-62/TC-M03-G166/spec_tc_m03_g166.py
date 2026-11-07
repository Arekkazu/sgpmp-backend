"""spec_tc_m03_g166.py — Especificación normativa y parámetros para TC-M03-G166.

Requisitos cubiertos:
- RF-62: Evaluación estadística de calidad de datos telemétricos (Sensor congelado).
- RF-57: Generación de alertas técnicas ante anomalías de sensor.
- RF-63: Bitácora de auditoría IoT (evento EVALUACION_CALIDAD_COMPLETADA).

Casos originales agrupados: TC-M03-309, TC-M03-310, TC-M03-311.

POLÍTICA ANTI-HARDCODE:
- Prohibido fijar contraseñas, secretos, IDs numéricos de entidades o URLs fuera de TEST_BASE_URL.
- Un único bloque de constantes normativas extraídas de la ESPECIFICACIÓN (RF-62 Fases 1, 2, 6, 8
  y hoja 'Parámetros base').
- El valor base 25.40 es un parámetro del dataset que se valida en preflight contra el rango
  físico/biológico del sensor, no una constante estática no comprobable.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple


class SpecTCM03G166:
    """Constantes normativas del caso de prueba TC-M03-G166 con origen explícito."""

    # Orígenes documentales
    ORIGEN_RF62_FASE1 = "RF-62 Fase 1: Contexto y serie temporal"
    ORIGEN_RF62_FASE2 = "RF-62 Fase 2: Detección de sensor congelado"
    ORIGEN_RF62_FASE6 = "RF-62 Fase 6: Índice de calidad y clasificación"
    ORIGEN_RF62_FASE8 = "RF-62 Fase 8: Alertas técnicas y bitácora de auditoría"
    ORIGEN_RF57 = "RF-57: Sistema de alertas IoT (alertas técnicas)"
    ORIGEN_RF63 = "RF-63: Bitácora de auditoría IoT inmutable"
    ORIGEN_PARAMETROS = "Hoja 'Parámetros base' (M09 / Stub Adapter)"

    # ── Parámetros del motor de calidad (RF-62 / M09) ─────────────────────────
    # N: Tamaño máximo de la ventana histórica previa recuperada por el motor.
    N: int = 20  # Origen: ORIGEN_PARAMETROS / ORIGEN_RF62_FASE1

    # M: Mínimo de lecturas consecutivas idénticas para activar sensor congelado.
    M: int = 5   # Origen: ORIGEN_PARAMETROS / ORIGEN_RF62_FASE2

    # Espaciado nominal entre lecturas consecutivas (en minutos).
    MUESTREO_MINUTOS: int = 10  # Origen: Hoja 'Parámetros base' / Plan de pruebas

    # ── Fronteras de severidad para sensor congelado ───────────────────────────
    # NOTA TÉCNICA: La relación 2M (10) y 4M (20) con M=5 NO está confirmada
    # normativamente por el texto de RF-62. Se establecen como constantes explícitas
    # con su origen en el código del motor (evaluar_calidad_telemetria_use_case.py:135-140)
    # y la tabla del caso de prueba.
    FRONTERA_LEVE_MIN: int = 5        # Origen: RF-62 Fase 2 (>= M=5 repeticiones)
    FRONTERA_LEVE_MAX: int = 9        # Origen: RF-62 Fase 2 (hasta 9 repeticiones)
    FRONTERA_MODERADO_MIN: int = 10   # Origen: RF-62 Fase 2 (>= 10 repeticiones)
    FRONTERA_MODERADO_MAX: int = 19   # Origen: RF-62 Fase 2 (hasta 19 repeticiones)
    FRONTERA_CRITICO_MIN: int = 20    # Origen: RF-62 Fase 2 (>= 20 repeticiones)

    # ── Descuentos de penalización (RF-62 Fase 6) ──────────────────────────────
    DESCUENTO_LEVE: int = 15          # Origen: ORIGEN_RF62_FASE6
    DESCUENTO_MODERADO: int = 35      # Origen: ORIGEN_RF62_FASE6
    DESCUENTO_CRITICO: int = 90       # Origen: ORIGEN_RF62_FASE6

    # ── Umbrales de clasificación (RF-62 Fase 6) ───────────────────────────────
    UMBRAL_APTO_MIN: int = 80             # Índice >= 80 -> APTO
    UMBRAL_APTO_RESERVA_MIN: int = 40     # Índice 40..79 -> APTO_CON_RESERVA
    UMBRAL_NO_APTO_MAX: int = 39          # Índice < 40 -> NO_APTO

    # ── Literales de clasificación de calidad ──────────────────────────────────
    CLASIFICACION_APTO: str = "APTO"
    CLASIFICACION_APTO_CON_RESERVA: str = "APTO_CON_RESERVA"
    CLASIFICACION_NO_APTO: str = "NO_APTO"
    CLASIFICACION_INDETERMINADA: str = "INDETERMINADA"

    # ── Tabla de aptitud (apto_para_ia, apto_para_nic41) ───────────────────────
    TABLA_APTITUD: Dict[str, Tuple[bool, bool]] = {
        CLASIFICACION_APTO: (True, True),
        CLASIFICACION_APTO_CON_RESERVA: (True, False),
        CLASIFICACION_NO_APTO: (False, False),
        CLASIFICACION_INDETERMINADA: (False, False),
    }

    # ── Dataset base para telemetría ───────────────────────────────────────────
    # Valor base nominal propuesto en el plan de pruebas
    VALOR_BASE: Decimal = Decimal("25.40")
    TIPO_VARIABLE: str = "TEMPERATURA_AMBIENTAL"
    ID_VARIABLE_AMBIENTAL: int = 9        # Catálogo I3P-1
    UNIDAD_ESTANDAR: str = "°C"
    ORIGEN_INGESTA: str = "BUFFER_LOCAL"  # Flujo C para sincronización de histórico

    # ── Ciclo de vida y literales de estado (Decisión D7) ──────────────────────
    class Estados:
        """Decisión D7 RESUELTO:
        Definido por análisis (respuesta registrada; RFC de aclaración de RF-62 en trámite, nº pendiente). Descartado ACTIVA.
        Literal oficial: 'VIGENTE'. Catálogo: {'VIGENTE', 'SUPERADA'}.
        Regla canónica: máximo UNA evaluación VIGENTE por lectura.
        """
        estado_superado: str = "SUPERADA"  # RF-62 restricción 9
        estado_vigente: str = "VIGENTE"  # Definido por análisis (respuesta registrada; RFC de aclaración de RF-62 en trámite, nº pendiente). Descartado ACTIVA.
        catalogo_estados: List[str] = ["VIGENTE", "SUPERADA"]  # Definido por análisis (respuesta registrada; RFC de aclaración de RF-62 en trámite, nº pendiente). Descartado ACTIVA.
        evaluar_supera_anterior: bool = True  # Definido por análisis (respuesta registrada; RFC de aclaración de RF-62 en trámite, nº pendiente). Descartado ACTIVA.
        ESTADOS_DEFINIDOS: bool = True


# ── ORÁCULO INDEPENDIENTE PURO (Sin dependencias de red ni del backend) ────────

def severidad_esperada(r: int) -> Optional[str]:
    """Determina la severidad puramente a partir de R y las constantes de spec."""
    if r < SpecTCM03G166.FRONTERA_LEVE_MIN:
        return None
    if r >= SpecTCM03G166.FRONTERA_CRITICO_MIN:
        return "CRITICO"
    if r >= SpecTCM03G166.FRONTERA_MODERADO_MIN:
        return "MODERADO"
    return "LEVE"


def descuento_esperado(severidad: Optional[str]) -> int:
    """Calcula el descuento del flag sensor congelado según spec."""
    if severidad is None:
        return 0
    if severidad == "CRITICO":
        return SpecTCM03G166.DESCUENTO_CRITICO
    if severidad == "MODERADO":
        return SpecTCM03G166.DESCUENTO_MODERADO
    if severidad == "LEVE":
        return SpecTCM03G166.DESCUENTO_LEVE
    raise ValueError(f"Severidad desconocida: {severidad}")


def indice_esperado(severidad: Optional[str]) -> int:
    """Calcula el índice de calidad esperado (100 - descuento)."""
    return max(0, 100 - descuento_esperado(severidad))


def clasificacion_esperada(indice: int) -> str:
    """Deriva la clasificación de calidad desde el índice según spec."""
    if indice >= SpecTCM03G166.UMBRAL_APTO_MIN:
        return SpecTCM03G166.CLASIFICACION_APTO
    if indice >= SpecTCM03G166.UMBRAL_APTO_RESERVA_MIN:
        return SpecTCM03G166.CLASIFICACION_APTO_CON_RESERVA
    return SpecTCM03G166.CLASIFICACION_NO_APTO


def aptitud_esperada(clasificacion: str) -> Tuple[bool, bool]:
    """Retorna (apto_para_ia, apto_para_nic41) esperado."""
    return SpecTCM03G166.TABLA_APTITUD[clasificacion]
