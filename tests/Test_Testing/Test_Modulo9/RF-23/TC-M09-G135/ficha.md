# TC-M09-G135 — RF-23

Fuente: `TCs_M09_v2_2026-10-06.md` (matriz corregida, 2026-10-06).

**Estado de la ejecución (TEST, 2026-10-08, reintento1):** BLOQUEADO (confirmado por código, 3 passed / 1 skipped) — el mecanismo que pide este TC no existe en este repo.

### G135-02 — Envío automático de PENDIENTE (nuevo)
- **Tipo:** Integración · **Ejecutable:** No desde este repo. Hallazgo estructural: este backend no mantiene conexión MQTT propia ni escucha reconexión de dispositivos — `ConfigurarRemotamenteUseCase` hace una única llamada HTTP síncrona a BROKER-MQTT-SGPMP dentro de la misma request del usuario; no hay listener/`on_connect`/job en segundo plano en todo `src/configuration` que reenvíe configuraciones PENDIENTES al reconectar. Si ese reenvío automático existe, vive en BROKER-MQTT-SGPMP (fuera de este repo) — misma conclusión de alcance que G127 (ACLs/TLS de Mosquitto) y G128 (LoRaWAN). Necesita decisión del equipo/acceso a ese microservicio para probarse de verdad.

## Reintento1 (2026-10-08)
- Script: `test_tc_m09_g135_envio_automatico_pendiente.py` (pytest, inspección de código — sin red/BD)
- Reporte: `resultados/resultado_TC-M09-G135_reintento1.html`
- 3 passed (confirman la ausencia del mecanismo) / 1 skipped (placeholder explícito del caso bloqueado).
