# TC-M09-G57-02 — RF-21

Fuente: `TCs_M09_v2_2026-10-06.md` (matriz corregida, 2026-10-06).

**Estado de la ejecución (TEST, 2026-10-06):** NO EJECUTADO (ver Resultados_M09_RF21-23_2026-10-06.md)

### G57-02 — Identificador único y consulta
- **Tipo:** Integridad · **Ejecutable:** Sí para SENSOR.
- **Pasos:** registrar dos dispositivos; consultar; verificar que `id_tipo_dispositivo` y la categoría derivada aparezcan en la respuesta. Un SENSOR no debe mostrar valores de visión.
- **Observado:** la respuesta de registro ya incluye `id_dispositivo_gateway`, campo que el consolidado no menciona.
