# Reintento 1 — INVÁLIDO (descartado)

**Fecha original:** 2026-10-30T09:17:20Z
**Motivo de descarte:**
- JSON raw de Newman (428 KB) sin estructura `checkpoints` requerida por el scanner del QA Dashboard (§5.1.1 del guide).
- Queries de inmutabilidad 321.07 y 322.07 usaban columna `valor` inexistente en `modulo3.telemetrias` → HTTP 400 falso positivo.
- Sensor 15 (TC-322) tiene `frecuencia_muestreo_min = 45` incompatible con el oráculo del test (gap 25 min < 2×45 = 90 min → nunca dispara gap_temporal_anomalo).
- Timestamps de la serie TC-322 colapsados en un solo instante (`inicio_serie == fin_serie`) → backend clasificó como serie_insuficiente.

**Veredicto del ciclo 1:** RECHAZADO_POR_SCRIPT (no es evidencia del producto backend).

**Propósito de este respaldo:** trazabilidad histórica del proceso de corrección. NO es evidencia formal del caso. El reintento 1 canónico es el regenerado tras el ciclo 2.
