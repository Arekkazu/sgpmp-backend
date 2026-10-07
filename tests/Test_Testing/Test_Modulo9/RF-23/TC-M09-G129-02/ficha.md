# TC-M09-G129-02 — RF-23

Fuente: `TCs_M09_v2_2026-10-06.md` (matriz corregida, 2026-10-06).

**Estado de la ejecución (TEST, 2026-10-06):** PASA (3/3): ingesta con dispositivo inexistente y dado de baja rechazada

### G129-02 — Spoofing de identidad IoT
- **Tipo:** Seguridad (OWASP A01/A07/A09) · **Ejecutable:** Sí para identificador inexistente y dado de baja.
- **Trazabilidad a corregir:** este grupo prueba **ingesta de telemetría** (M03, RF-53/RF-60), no configuración remota. Reasignar el RF de referencia. Los hallazgos de ingesta ya están en M3-03 / M9-03.

## Ejecución automatizada (2026-10-06, TEST)
- Colección: `tc_m09_g129_02.postman_collection.json`
- Reporte: `resultados/resultado_TC-M09-G129-02.html`
- Aserciones: 3 total, 0 fallidas (incluye el login)
