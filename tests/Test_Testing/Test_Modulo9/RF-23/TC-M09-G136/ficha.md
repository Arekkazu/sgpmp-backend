# TC-M09-G136 — RF-23

Fuente: `TCs_M09_v2_2026-10-06.md` (matriz corregida, 2026-10-06).

**Estado de la ejecución (TEST, 2026-10-09, reintento2):** APROBADO (12/12) — **DESBLOQUEADO**: `fps` ya es un campo real del contrato de escritura.

### G136-02 — Parámetros por categoría / fps (nuevo)
- **CORREGIDO.** El TEST desplegado ahora tiene `fps` (1-60) en `ConfigurarRemotamenteDTO`, junto a `frecuencia_captura`/`intervalo_transmision` (confirmado vía `GET /openapi.json` en vivo — el checkout local de este repo todavía no lo tiene, mismo patrón de desvío local-vs-live ya visto en G69). El use case decide qué juego de parámetros aplica según la categoría del tipo de dispositivo (catálogo `tipos-dispositivo-iot` ahora expone `categoria: SENSOR|CAMARA`) y cruza correctamente: enviar `frecuencia_captura` a una cámara → `400 PARAMETRO_NO_APLICA_A_CAMARA`; enviar `fps` a un sensor → `400 PARAMETRO_NO_APLICA_A_SENSOR`.

## Reintento1 (2026-10-09, temprano) — histórico, superado por el reintento2
- Script: `test_tc_m09_g136_sin_fps_reintento1.py` (pytest, inspección de código — sin red/BD)
- Reporte: `resultados/resultado_TC-M09-G136_reintento1.html`
- 2/2 passed (confirmó correctamente el estado del checkout LOCAL — que seguía bloqueado — pero TEST ya tenía el fix desplegado).

## Reintento2 (2026-10-09, TEST, en vivo)
- Colección: `tc_m09_g136_reintento2.postman_collection.json`
- Reporte: `resultados/resultado_TC-M09-G136_reintento2.html`
- 12/12 passed: fps en rango (202 PENDIENTE), fps=61/fps=0 fuera de rango (400 VAL_ENTRADA), parámetros de sensor en cámara y viceversa (400, códigos de error cruzados correctos).
