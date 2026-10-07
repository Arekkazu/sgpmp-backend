# TC-M09-G69-02 — RF-23

Fuente: `TCs_M09_v2_2026-10-06.md` (matriz corregida, 2026-10-06).

**Estado de la ejecución (TEST, 2026-10-06):** FALLA (3/5): `protocolo` aceptado con 202 (debe rechazarse)

### G69-02 — Transporte MQTT sobre LoRaWAN
- **Tipo:** Integración · **Estado:** **Parcial.** Reintento4 (DEV, 2026-10-05): `protocolo` se ignora (202 con LoRaWAN e inexistente). El viaje MQTT con dispositivo real requiere credenciales de broker (pendiente).

## Ejecución automatizada (2026-10-06, TEST)
- Colección: `tc_m09_g69_02.postman_collection.json`
- Reporte: `resultados/resultado_TC-M09-G69-02.html`
- Aserciones: 5 total, 2 fallidas (incluye el login)
- Nota: El rechazo esperado (400/422) es la expectativa del contrato: `protocolo` no existe en `ConfigurarRemotamenteDTO`.
- Fallo: protocolo LORAWAN en configuracion -> 400/422 — expected [ 400, 422 ] to include 202
- Fallo: protocolo inexistente -> 400/422 — expected [ 400, 422 ] to include 202
