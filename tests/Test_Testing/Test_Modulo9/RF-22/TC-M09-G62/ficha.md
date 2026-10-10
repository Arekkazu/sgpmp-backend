# TC-M09-G62 — RF-22

Fuente: `TCs_M09_v2_2026-10-06.md` (matriz corregida, 2026-10-06).

**Estado de la ejecución (TEST, 2026-10-10, reintento1):** PARCIAL — sensor inexistente **CORREGIDO** (ahora 422); el resto sigue bloqueado por un bug nuevo (ver abajo).

### G62-02 — Integridad de la asociación
- **Tipo:** Integridad · **Ejecutable:** Parcial.
- **CORREGIDO (confirmado en vivo 2026-10-10):** sensor inexistente → ahora **422 `SENSOR_DISPOSITIVO_INVALIDO`** (antes 404). Coincide con lo que pedía el consolidado.
- **BLOQUEADO por bug nuevo (no relacionado a este TC):** `POST /configuracion/dispositivos-iot/{id}/sensores` responde **500 `ERROR_INTERNO` de forma incondicional** en TEST (confirmado en 3 dispositivos distintos, 2 infraestructuras distintas, con y sin `categoria`, 2026-10-10). Esto bloquea "dispositivo inexistente → 404" (necesita un sensor real para probarlo) y cualquier otro sub-caso que dependa de un sensor fresco. Ver hallazgo nuevo abajo y en `Issues_M09_RF21-23_2026-10-06.md`.
- **Pendiente (sigue igual):** sensor de otro dispositivo → 422 (verificar código real); área inexistente o inactiva → 404; duplicado vigente → 409 `ASOCIACION_DUPLICADA`. Todos bloqueados por el mismo bug nuevo.

## Reintento1 (2026-10-10, TEST)
- Probado manualmente (sin colección nueva, dado el bloqueo): sensor inexistente sobre dispositivo real → `422 SENSOR_DISPOSITIVO_INVALIDO`. Confirmado corregido.
- **Hallazgo nuevo y bloqueante:** `POST /configuracion/dispositivos-iot/{id}/sensores` → 500 incondicional. Reportar como bug nuevo de RF-22 (afecta también TC-M09-G133 y cualquier TC que necesite un sensor fresco).

## Ejecución automatizada (2026-10-06, TEST)
- Colección: `tc_m09_g62.postman_collection.json`
- Reporte: `resultados/resultado_TC-M09-G62.html`
- Aserciones: 11 total, 2 fallidas (incluye el login)
- Nota: Discrepancia con la matriz (decisión 7): el backend responde 404 para sensor inexistente.
- Fallo: Sensor inexistente -> 422 (consolidado) — expected response to have status code 422 but got 404
- Fallo: Dispositivo inexistente -> 404 — expected response to have status code 404 but got 422
