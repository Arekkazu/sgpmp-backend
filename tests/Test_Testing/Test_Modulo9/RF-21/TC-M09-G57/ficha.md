# TC-M09-G57 — RF-21

Fuente: `TCs_M09_v2_2026-10-06.md` (matriz corregida, 2026-10-06).

**Estado de la ejecución (TEST, 2026-10-10, reintento1):** APROBADO (9/9) — **CORREGIDO**: la respuesta ya incluye `categoria`.

### G57-02 — Identificador único y consulta
- **Tipo:** Integridad · **Ejecutable:** Sí para SENSOR.
- **Pasos:** registrar dos dispositivos; consultar; verificar que `id_tipo_dispositivo` y la categoría derivada aparezcan en la respuesta. Un SENSOR no debe mostrar valores de visión.
- **Observado:** la respuesta de registro ya incluye `id_dispositivo_gateway`, campo que el consolidado no menciona.

## Ejecución automatizada (2026-10-06, TEST) — histórico, superado por el reintento1
- Colección: `tc_m09_g57.postman_collection.json`
- Reporte: `resultados/resultado_TC-M09-G57.html`
- Aserciones: 9 total, 1 fallidas (incluye el login)
- Fallo (en ese momento): DispositivoIotResponse no incluía `categoria` (ya corregido)

## Reintento1 (2026-10-10, TEST, misma colección sin cambios)
- Reporte: `resultados/resultado_TC-M09-G57_reintento1.html`
- 9/9 passed: `GET /configuracion/dispositivos-iot/{id}` ahora devuelve `"categoria":"SENSOR"` directamente (parte del mismo despliegue que agregó la categoría CAMARA, ver TC-M09-G134/G136/G137).
