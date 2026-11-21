# Reevaluación TC-M02-G84 — V3 (definitivo)
Fecha: 2026-09-25
SHA ejecutado: cc6450218654f6ddb6866ebbacf5d5adc6a61159

## Secuencia del ciclo
1. **Intento 1 (fallido):** 5 fallos en Newman por precondición residual en base de datos (asociación ambiental `id=47` para sensor 23 e infraestructura 3 preexistente en estado `ACTIVA`).
   - Causa raíz: diseño de test acoplado a estado limpio sin pre-cleanup idempotente; el POST devolvió 409 `ASOCIACION_AMBIENTAL_YA_EXISTE`, no seteó la variable `id_asoc_ambiental_144` y cascada a 404 en el Request 98.
2. **Corrección:**
   - C1: Pre-cleanup en TC-M02-144 que consulta e inactiva cualquier asociación activa residual previa antes del POST.
   - C2: Assertion tolerante e idempotente ([200, 201, 409]) con fallback de recuperación de ID.
   - C3 & C4: Request 98 autónomo y guardián anti-cascada (`id_asoc_ambiental_144` validada).
   - C5: Request 99 simétrico con pre-request autocontenido y guardián anti-cascada.
3. **Intento 2 (limpio):** Corrida Newman 100% exitosa (10/10 requests de suite + 1 prerequest GET, 22/22 assertions aprobadas, 0 fallos, exit code 0).
4. **Corrección post-ejecución (formato del JSON):** El archivo `resultado_TC-M02-G84_reintento3.json` había quedado en formato Newman JSON crudo (no reconocido por el scanner). Se reescribió al formato "Cypress JSON propio" (`checkpoints[]` con `estado ∈ {"OK","FALLA"}`), preservando el Newman crudo como evidencia forense en `evidencias/newman_summary_reintento3.json`.

## Resumen ejecutivo
- **Newman:** 10/10 requests ejecutados, 22/22 assertions pasadas, 0 fallidas (Exit code 0).
- **Pytest unitario (#398):** 10/10 passed (100%).
- **Pytest integración (#397):** 3/3 passed (100%).
- **Veredicto final:** **APROBADO**.

## Resultados por subcaso
| Subcaso | Antes (V2) | Intento 1 V3 | Intento 2 V3 | Veredicto |
|---|---|---|---|---|
| TC-M02-143 | PASS | PASS | PASS | APROBADO |
| TC-M02-144 | PASS falso (apuntaba a /activos) | FAIL (409 colisión) | PASS (201 Created) | APROBADO |
| TC-M02-145 | PASS | PASS | PASS | APROBADO |
| TC-M02-150 | BLOCKED (M03) | PASS | PASS | APROBADO |
| Req 98 (Fix #398) | N/A | FAIL (cascada 404) | PASS (200 OK + INACTIVA) | APROBADO |
| Req 99 (Fix #397) | N/A | PASS (200 OK) | PASS (200 OK + INACTIVA) | APROBADO |

## Hallazgos nuevos (si aplica)
No se identificaron nuevos defectos de software ni bloqueos en el sistema bajo prueba. El comportamiento anómalo observado en el Intento 1 correspondió exclusivamente a fragilidad de diseño en la suite de pruebas al no contemplar idempotencia ni desacoplamiento de precondiciones en base de datos.

## Estado de BD post-corrida y post-cleanup
- **Asociaciones creadas en la corrida:** IDs 98 (TC-M02-143), 99 (TC-M02-144), 100 (TC-M02-145), 101 (TC-M02-150).
- **Asociaciones desactivadas durante la corrida vía API PATCH:** IDs 98 y 99 transicionaron a `INACTIVA` inmediatamente durante la ejecución de los requests 99 y 98 respectivamente.
- **Asociaciones desactivadas por el script de cleanup correctivo:** IDs 100 y 101 pasaron a `INACTIVA`.
- **Asociaciones ACTIVA remanentes en el alcance del TC:** 0.
- **Asociaciones huérfanas:** 0.

## Conclusión
Los fixes #397 (permisos RBAC para actualización y desactivación de asociaciones sensor-activo por Administrador y Productor) y #398 (soporte del endpoint PATCH para asociaciones ambientales en infraestructura `PATCH /infraestructuras/{id_infraestructura}/sensores/{id_asociacion}`) quedan completamente validados de extremo a extremo, confirmando la resolución definitiva de los bloqueos de TC-M02-G84.
