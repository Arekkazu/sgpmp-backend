# TC-M03-G169 — Resultado V1

**Veredicto**: RECHAZADO POR BLOQUEO EXTERNO
**Fecha**: 2026-10-23
**Ejecutado**: PARCIAL (preflight hasta crear sensor)

## Resumen

La suite se ejecutó hasta `00.06-Crear-Dispositivo` (201). Falla en
`00.07-Crear-Sensor` con HTTP 500 ERROR_INTERNO por INC-M03-G167-SENSOR-500.
Los 2 subcasos (TC-321, TC-322) no pudieron ejecutarse.

## INCs bloqueantes
- INC-M03-G167-SENSOR-500 (bloqueante de siembra)
- INC-M03-G168-GAP-NOT-IMPLEMENTED (afecta oráculo de TC-322)

## Hallazgos de requerimiento
- H1: valor 150 del CSV físicamente imposible (max 100). Adaptado a 50 + especie 2
- H2: especie 2 (Trucha) reemplaza a 123 (Tilapia) en esta suite

## Evidencia
- Reporte HTML: `resultados/resultado_TC-M03-G169.html`
- Consola: `evidencias/console_run.log`
- Sandbox cerrado: sí

## Listo para V2 (cuando se resuelvan los INCs)
- Renombrar a `resultado_TC-M03-G169_reintento1.{html,json}`
- TC-322 seguirá fallando por INC-GAP hasta que se implemente el gap
