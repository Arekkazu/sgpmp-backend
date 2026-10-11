# TC-M09-G127 — RF-23

Fuente: `TCs_M09_v2_2026-10-06.md` (matriz corregida, 2026-10-06).

**Estado de la ejecución (TEST, 2026-10-08, reintento1):** PARCIAL (3/3 de lo ejecutable) — M9-05 y M9-06 confirmados en vivo contra el broker de **TEST**. Escenario 5 (publicación directa) sigue sin ejecutar, pendiente de confirmación explícita del usuario antes de publicar en el broker real.

**Nota 2026-10-09 (usuario):** M9-06 (sin TLS en el broker) se maneja junto con Módulo 3 (Telemetría IoT) — **en standby desde este TC**, no se le da seguimiento adicional aquí. Lo que queda abierto propiamente en G127 es M9-05 (wildcard, confirmado) y el Escenario 5 (publicación directa, pendiente de acordar tópico/payload).

### G127-02 — Ataques a MQTT
- **Tipo:** Seguridad · **Ejecutable:** Sí, con las credenciales de broker de TEST entregadas 2026-10-07/08.
- **Hallazgos confirmados de nuevo, ahora en TEST (antes solo DEV):** cuenta genérica con `#` concedido (M9-05); listener acepta texto plano sin TLS (M9-06, host/puerto del broker no se documentan aquí por discreción con la infraestructura — ver variables de entorno `MQTT_HOST`/`MQTT_HOST_PORT`). Control negativo: password inválida sí se rechaza (auth no está completamente abierta).
- **Escenario 5 (publicación directa en el broker):** sigue sin ejecutarse — requiere decidir con el usuario un tópico/payload seguro que no afecte un dispositivo real antes de publicar.

## Reintento1 (2026-10-08, TEST)
- Script: `test_tc_m09_g127_ataques_mqtt_reintento1.py` (pytest + paho-mqtt)
- Reporte: `resultados/resultado_TC-M09-G127_reintento1.html`
- 3/3 passed (los 3 escenarios ejecutables sin publicar): texto plano aceptado, wildcard `#` concedido, credencial inválida rechazada.
