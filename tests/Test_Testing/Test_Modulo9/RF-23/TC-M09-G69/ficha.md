# TC-M09-G69 — RF-23

Fuente: `TCs_M09_v2_2026-10-06.md` (matriz corregida, 2026-10-06).

**Estado de la ejecución (TEST, 2026-10-08, reintento1):** APROBADO (3/3) — **CORREGIDO**: `protocolo` ahora se rechaza con 400 `VAL_ENTRADA`.

### G69-02 — Transporte MQTT sobre LoRaWAN
- **Tipo:** Integración · **Estado:** **Corregido.** El TEST desplegado ahora rechaza `protocolo` con `400 VAL_ENTRADA` ("Este campo no está permitido en esta solicitud", `extra_forbidden`). El checkout local de `ConfigurarRemotamenteDTO` no tiene `extra='forbid'` — TEST corre una revisión más nueva de ese DTO que la de este repo (mismo patrón ya visto en DEV 2026-09-13). **No subir el issue de protocolo a Taiga** (ver `Issues_M09_RF21-23_2026-10-06.md`, queda marcado obsoleto).
- M9-05 (wildcard `#`) y M9-06 (sin TLS) siguen abiertos — confirmados de nuevo en esta misma suite, ahora contra TEST (antes solo DEV). Ver también TC-M09-G127.

## Ejecución automatizada (2026-10-06, TEST) — histórico, superado por el reintento1
- Colección: `tc_m09_g69.postman_collection.json`
- Reporte: `resultados/resultado_TC-M09-G69.html`
- Aserciones: 5 total, 2 fallidas (incluye el login)
- Fallo (en ese momento): protocolo LORAWAN/inexistente en configuracion -> se esperaba 400/422, respondía 202 (bug, ya corregido).

## Reintento1 (2026-10-08, TEST, con credenciales reales de broker)
- Script: `test_tc_m09_g69_protocolo_mqtt_reintento1.py` (pytest + paho-mqtt)
- Reporte: `resultados/resultado_TC-M09-G69_reintento1.html`
- 3/3 passed: `protocolo=LORAWAN` → 400 VAL_ENTRADA; `protocolo=INEXISTENTE` → 400 VAL_ENTRADA; confirmación en vivo de M9-05/M9-06 sobre el broker de TEST (host/puerto no se documentan aquí, ver `MQTT_HOST`/`MQTT_HOST_PORT`).
