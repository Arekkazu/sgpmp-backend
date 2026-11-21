# TC-M07-G037 — Reevaluación V2 — RECHAZADO (error de oráculo, sustituida por la V3)

## Identificación

TC-M07-G037, que agrupa TC-M07-06 a TC-M07-08: formato de la versión del contrato AAEF, período de gracia configurable en M09 y deprecación con gracia. RF-98 v1.2, apartados 5.8, RNF-98.10 y FA-10; criterio CA-7. Versión 2 (reevaluación del grupo completo). RUN RUN-G037-V2-20261120-210522, ambiente TEST, autorización AUT-G037-V2-20261120. Versión anterior: V1 oficial RUN-G037-V1-20261118-071829. Actor: Administrador QA. Commit desplegado en TEST no consultado; la rama origin/test del repositorio contiene la corrección 0553cefd. Herramientas: Node v22.15.1 y Newman (código 0); sin UI. RUN oficial, en una sola fase transaccional; 44 de 60 solicitudes.

## Motivo de la reevaluación

En la V1, el caso 07 salió RECHAZADO con severidad MEDIA (INC-M07-G037-01): el mínimo de 30 días y el valor por defecto de 90 eran constantes del código y M09 no permitía configurarlos. Desarrollo lo corrigió en 0553cefd (#1167). La V2 repite los tres casos.

## Resumen de veredictos

| Caso | V1 | V2 | Motivo |
|---|---|---|---|
| TC-M07-06 | APROBADO | APROBADO | Los siete formatos mal formados se rechazaron sin alta y la 6.0 se registró en PENDIENTE. |
| TC-M07-07 | RECHAZADO | RECHAZADO | Todas las comprobaciones del requisito se cumplieron; el ejecutor rechazó solo `patch_invalido` por el código de error, que el RF-98 no fija. |
| TC-M07-08 | APROBADO | APROBADO | La deprecación de la 3.0 exige el mínimo configurado y fija la inactivación a +45 días exactos. |

## Detalle por caso

### TC-M07-06 — Formato de la versión

- **Esperado:** un formato distinto de MAJOR.MINOR se rechaza sin crear nada; una versión válida queda en PENDIENTE.
- **Observado:** los siete formatos respondieron HTTP 400 VAL_ENTRADA en `contrato_version` (G037-007 a G037-013) y la 6.0 se registró con HTTP 201, id 29, en PENDIENTE (G037-015).
- **Decisión: APROBADO.**

### TC-M07-07 — Período de gracia configurable en M09

- **Esperado:** la gracia mínima y por defecto salen de M09, los registros aplican sus valores también tras cambiarlos, y una configuración inválida no se acepta.
- **Observado:** con la base (30 y 90), 29 días se rechazó con PERIODO_GRACIA_INVALIDO, 30 se aceptó y sin gracia se aplicaron 90 (G037-018, G037-020 y G037-022). El PATCH a 45 y 120 respondió 200 y el GET los devolvió con fuente CONFIGURADO (G037-024 y G037-025); después, 44 se rechazó, 45 se aceptó y sin gracia se aplicaron 120 (G037-027, G037-029 y G037-031). El PATCH inválido (por defecto 44, menor que el mínimo) respondió HTTP 400 `PARAMETRO_MLOPS_INVALIDO`, `field` nulo, y la gracia no cambió (G037-033 y G037-034).
- **Decisión del ejecutor: RECHAZADO**, solo en `patch_invalido`, porque su oráculo exigía `PARAMETRO_INTEGRACION_CONTABLE_INVALIDO`.
- **Análisis QA:** ese código se tomó de la implementación; el RF-98 (5.8, RNF-98.10 y FA-10) exige que una configuración inválida no se acepte, pero no fija el código de error de M09. La respuesta observada (400 sin cambios) cumple el requisito. El rechazo es un **error del oráculo de QA**, no un incumplimiento del producto, y la etiqueta de incidencia que generó el ejecutor («PATCH_INVALIDO_ACEPTADO») es incorrecta, porque el PATCH no se aceptó. El oráculo se corrigió (ORD-G037-009) y el grupo se reevaluó en la V3.

### TC-M07-08 — Deprecación con período de gracia

- **Esperado:** con menos del mínimo se rechaza y la versión sigue ACTIVO; con el mínimo pasa a DEPRECADO con la inactivación al final del plazo.
- **Observado:** con 44 días, HTTP 400 PERIODO_GRACIA_INVALIDO (G037-036); con 45, la 3.0 pasó a DEPRECADO con inactivación el 2027-01-04 a las 21:05:30 UTC, 45 días exactos después (G037-038).
- **Decisión: APROBADO.**

## Evidencias reales

resultado.json, preflight.json, contexto_operacion.json, newman/newman-G037.json y newman/newman-G037.html. Sin correos, contraseñas, tokens ni el secreto del sandbox.

## Incidencias de producto

Ninguna. `resultado.json` contiene la incidencia «PATCH_INVALIDO_ACEPTADO» que el ejecutor generó automáticamente a partir del oráculo `patch_invalido`; QA la descarta, porque la evidencia del mismo RUN muestra HTTP 400 y la gracia sin cambios (G037-033 y G037-034). El rechazo del 07 no se atribuye a ningún equipo: es un problema técnico de automatización de QA, ya corregido. Las demás comprobaciones confirman que 0553cefd corrige INC-M07-G037-01.

## Problemas técnicos de automatización

El oráculo `patch_invalido` exigía un código de error derivado de la implementación. Corregido en ORD-G037-009; la V3 (RUN-G037-V3-20261120-213856) repite el grupo con el oráculo ajustado al requisito.

## Cierre y rollback

`DELETE /test-control/runs/RUN-G037-V2-20261120-210522` respondió HTTP 200 y la lectura posterior sin cabeceras del RUN coincidió con la base: versiones, estados y gracia de M09 (30 y 90, VALOR_BASE). Rollback verificado. El único efecto persistente es el inicio de sesión del Administrador QA antes del RUN.

## Conclusión y acciones

La V2 queda oficial con el 07 RECHAZADO por un error de oráculo de QA, sin incidencia de producto. El resultado válido del grupo es el de la V3, APROBADO.

## Historial del informe

Informe redactado por el orquestador QA (2026-11-20) a partir de resultado.json y newman/. Veredictos y evidencias sin cambios.
Corrección (2026-11-20): precisados la incidencia automática de resultado.json (V2) y el alcance de la corrección de INC-M07-G037-01 (V3); veredictos y evidencias sin cambios.
