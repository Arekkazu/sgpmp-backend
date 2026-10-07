# TC-M09-G127-02 — RF-23

Fuente: `TCs_M09_v2_2026-10-06.md` (matriz corregida, 2026-10-06).

**Estado de la ejecución (TEST, 2026-10-06):** NO EJECUTADO — Requiere credenciales del broker (publicación directa, cuenta con `#`). No se suministraron por variable de entorno en esta sesión; ejecutar en DEV con MQTT_* definidas.

### G127-02 — Ataques a MQTT
- **Tipo:** Seguridad · **Ejecutable:** Sí en DEV con credenciales de broker (pendientes).
- **Hallazgos previos:** cuenta genérica con `#` concedido (M9-05); listeners sin TLS (M9-06).
- **Escenario 5 (publicación directa en el broker):** solo se puede probar con credenciales de publicación.
