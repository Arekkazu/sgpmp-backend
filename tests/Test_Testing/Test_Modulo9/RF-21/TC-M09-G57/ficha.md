# TC-M09-G57 — RF-21

Fuente: `TCs_M09_v2_2026-10-06.md` (matriz corregida, 2026-10-06).

**Estado de la ejecución (TEST, 2026-10-06):** FALLA contra ficha (8/9): categoría derivada ausente en la respuesta

### G57-02 — Identificador único y consulta
- **Tipo:** Integridad · **Ejecutable:** Sí para SENSOR.
- **Pasos:** registrar dos dispositivos; consultar; verificar que `id_tipo_dispositivo` y la categoría derivada aparezcan en la respuesta. Un SENSOR no debe mostrar valores de visión.
- **Observado:** la respuesta de registro ya incluye `id_dispositivo_gateway`, campo que el consolidado no menciona.

## Ejecución automatizada (2026-10-06, TEST)
- Colección: `tc_m09_g57.postman_collection.json`
- Reporte: `resultados/resultado_TC-M09-G57.html`
- Aserciones: 9 total, 1 fallidas (incluye el login)
- Nota: DispositivoIotResponse no incluye `categoria`; la ficha lo pide en la respuesta.
- Fallo: Consultar dispositivo 1 — expected undefined to deeply equal 'SENSOR'
