# Reevaluación TC-M02-G89 — V3 (definitivo)
Fecha: 2026-09-25
SHA ejecutado: cc6450218654f6ddb6866ebbacf5d5adc6a61159
Entorno: TEST (`https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test`)

## Contexto
Reevaluación tras fixes #397 (permiso RBAC para PATCH de asociaciones sensor-activo) y #398 (soporte de endpoints de infraestructura) y corrección de aserción SUPERADA (añadida en Fase 1.5) en TC-M02-217.

## Secuencia del ciclo
1. **Auditoría Fase 1:** Detectado que TC-M02-217 creaba la segunda asociación pero no verificaba que la primera hubiese transitado efectivamente al estado `SUPERADA`. Además, scripts PowerShell apuntaban a credenciales quemadas o endpoints sin auth dinámico.
2. **Correcciones Fase 1.5:** Se incorporó el request de verificación GET `?tipo_consulta=HISTORIAL` con aserciones estrictas para `SUPERADA` y `fecha_fin != null`; se agregó bloque de teardown con aserciones; se repararon scripts y se diseñó cleanup SQL idempotent.
3. **Ejecución Fase 2 (esta corrida):** Pre-cleanup en BD TEST, ejecución automatizada Newman con exportación HTML extra y resumen JSON forense, generación de JSON computable con `checkpoints[]` y post-cleanup en BD TEST.

## Resumen ejecutivo
- **Newman:** 11 requests ejecutados, 21/21 assertions exitosas, 0 fallidas (100% efectividad).
- **Exit Code:** 0.
- **Veredicto final:** APROBADO.

## Resultados por subcaso
| Subcaso | Antes (V3 previo) | Ahora | Veredicto | Notas |
|---|---|---|---|---|
| TC-M02-217 | PASS (parcial) | PASS (201 + 200 GET) | APROBADO | Verificación explícita de transición de Asoc A (ID 102) a SUPERADA con fecha_fin poblada y Asoc B (ID 103) ACTIVA |
| TC-M02-216 | FAIL (403) | PASS (200 OK) | APROBADO | Fix #397 validado: Desactivación manual a INACTIVA exitosa con fecha_fin |
| TC-M02-218 | FAIL (403) | PASS (200 OK) | APROBADO | Fix #397 validado: Reactivación manual a ACTIVA exitosa con fecha_fin null |
| TC-M02-219 | FAIL (404/403) | PASS (422 Unprocessable) | APROBADO | Rechazo de transición manual hacia SUPERADA con código `TRANSICION_INVALIDA` |

## Hallazgos nuevos (si aplica)
No se identificaron nuevos hallazgos ni regresiones. El endpoint `GET /activos-biologicos/{id}/sensores?tipo_consulta=HISTORIAL` expone correctamente las asociaciones con estado `SUPERADA` y la máquina de estados opera según las reglas de negocio de RF-49.

## Estado de BD post-cleanup
- **ACTIVA remanentes:** 0
- **Huérfanas:** 0
- **Asociaciones de la corrida:** ID 102 (`SUPERADA`), ID 103 (`INACTIVA`).
- **Integridad referencial:** Cumplida íntegramente sin borrado físico de registros de auditoría.

## Conclusión
Validación end-to-end de los fixes #397 y del ciclo de vida completo de asociaciones sensor-activo biológico completada con éxito rotundo. El caso de prueba grupal TC-M02-G89 queda en estado Aprobado y listo para consumo del dashboard de aseguramiento de calidad.
