# Intento fallido del 2026-10-30 — rechazado por timeout y fixtures

**Resultado:** 3/52 PASS. Duración 229s > timeout sandbox 180s.

**Causas raíz:**
- Fixture eligió device_id=3 (89 periodos de inactividad abiertos) → 14 fallos.
- Timeout HTTP 15s + PATCH /configuracion/parametros/1 (FOR UPDATE lock global)
  → cascada de ReadTimeout en 318a/318b/318c/320 → 35 fallos.
- Duración acumulada 229s → teardown no confirmado.

**Backend NO involucrado.** Los 3 tests que pasaron lo hicieron sobre
el dispositivo correcto. El fix #632 y #685 están funcionando.

**Corrección aplicada en Fase 4b:**
- Fixture: filtrar por periodos_inactividad + fallback a IOT-TRU01-VLC-001.
- Ingesta: usar POST /iot/telemetria/batch (reduce 126 → ~10 requests).
- Sin PATCH de frecuencia: gap dinámico con 2×frecuencia + 5.
- Timeout HTTP: 15s → 45s (60s teardown).
- Split por 3 clases independientes.

**Este intento NO es un reintento válido.** No mide el fix. Es un
intento de descubrimiento de bugs del script.

