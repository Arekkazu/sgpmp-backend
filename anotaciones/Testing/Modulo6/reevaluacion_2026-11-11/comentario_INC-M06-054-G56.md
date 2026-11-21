**Reevaluación 11/11/2026 (TEST, código de `dev` del 11/11 con el merge dev → test de las 08:18) — RESULTADO: SIGUE FALLANDO (cambió el síntoma: ya no es 500, ahora es 404)**

**Qué se hizo**
Se repitió TC-M06-G56 (RF-91, TCG-10), subcaso TC-91-054, con el usuario Contador y sin sandbox, sobre dos períodos CERRADOS: el 7 (con `fecha_cierre`) y el 2 (sin `fecha_cierre`, el de esta incidencia). Petición: `POST /finanzas/periodos/{id}/cierre` con `{"autorizar_exclusiones": false}`.

| Período | fecha_cierre | Esperado | Obtenido | X-Request-Id | Hora (Colombia) |
|---|---|---|---|---|---|
| 7 | con fecha | 409 PERIODO_CERRADO | **404 PERIODO_NO_ENCONTRADO** | `cfe34829-9d04-49b3-9ccb-0a0da40f1417` | 11:51:49 |
| 2 | sin fecha | 409 PERIODO_CERRADO | **404 PERIODO_NO_ENCONTRADO** | `8a73547e-6327-470c-b0cb-a01083a86e2f` | 11:51:49 |

Los dos períodos existen: aparecen en `GET /finanzas/periodos` y la re-verificación `POST /finanzas/periodos/7/trazabilidad` responde bien (422 PERIODO_NO_ABIERTO).

**Qué cambió respecto al reporte original:** el período 2 antes daba 500 ERROR_INTERNO; ahora, igual que cualquier período CERRADO, da 404 antes de llegar al punto donde fallaba. El error original sigue en el código (ver abajo) pero hoy no se puede alcanzar.

**Causa confirmada por el DBA (11/11):** el cierre busca el período con bloqueo de escritura (`FOR UPDATE NOWAIT`) y la seguridad de la base de datos (política por fila) no permite bloquear un período CERRADO. La consulta vuelve vacía y el caso de uso responde «no encontrado» en vez de «ya está cerrado». Con el mismo usuario y la misma consulta: sin bloqueo los períodos se ven; con bloqueo devuelve 0 filas. Los períodos 2, 7 y 8 no se tocaron.

**Revisión del código (origin/test y origin/dev, 11/11):**
- `src/financial_valuation/application/use_cases/cierre/ejecutar_cierre_periodo_use_case.py:228-236`: `obtener(id, bloquear=True)` y, si devuelve `None`, responde 404.
- `infrastructure/repositories/periodo_repository.py:35-42`: la consulta lleva `FOR UPDATE NOWAIT`.
- Línea 234: el mensaje del 409 sigue formateando `periodo.fecha_cierre:%Y-%m-%d`; con `fecha_cierre` nula seguiría fallando cuando se corrija el 404.
- Las notas de lanzamiento 1.4.0 / 1.5.0 no incluyen una corrección para esta incidencia.

**Resumen del grupo:** TC-M06-G56, 61 aserciones, 4 fallidas (las 2 peticiones de cierre × estado HTTP y error_code). El resto del grupo pasa.

**Corrección pedida a Desarrollo (dos partes):**
1. Que el cierre lea el período sin bloqueo para validar su estado, y solo bloquee cuando está ABIERTO o EN_CIERRE; un CERRADO debe responder 409 PERIODO_CERRADO.
2. Que el mensaje del 409 no formatee `fecha_cierre` cuando es nula.

**Criterio de re-prueba:** `POST /finanzas/periodos/7/cierre` y `/2/cierre` responden 409 PERIODO_CERRADO, con mensaje legible y X-Request-Id.

**Adjunto:** `reeval_RF-91_TC-M06-G56.html` (sin contraseña, tokens ni cookies).

**Estado propuesto:** se mantiene abierta; no pasar a resuelta. El 404 se reporta aparte como INC-M06-054B-G56 (otra causa); esta incidencia conserva su título y su defecto de `fecha_cierre` nula, que se podrá re-probar cuando se corrija el 404.
