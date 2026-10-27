# TC-M03-G88 — RF-58

**Estado:** ÚLTIMO RUN CONSERVADO — EVALUACIÓN NO OFICIAL / PENDIENTE DE CIERRE FUNCIONAL.

G88 cubre TC-M03-169, 170, 171, 172, 180 y 266. La fuente de oráculos es la fila TC-M03-G88 de Casos_Prueba(Modulo3 Agrupado).csv (RF-58, CA-2/12/16, E7 y restricción 4). El [informe del intento 9](Resultados/RUN-G88-V1-20261025-020636/TC-M03-G88_resultado.md) conserva 169 APROBADO/OK; 170, 171 y 266 RECHAZADO/OK; 172 y 180 ERROR_QA sin veredicto funcional. El rollback, incluido el umbral QA 91, quedó verificado según ese intento. Este RUN no constituye un cierre oficial.

## Estructura y ejecución

g88.mjs es el ejecutor canónico; usa lib/ (incluido g88_escenario.json), G88.postman_collection.json, g88.cy.js y g88.cypress.config.cjs. pruebas/ contiene regresiones locales de esta automatización. Resultados/RUN-G88-V1-20261025-020636/ conserva el informe y las evidencias reales del intento 9. La ejecución en TEST corresponde exclusivamente al lanzador externo con contrato y autorización humana particular; node g88.mjs --comprobar solo comprueba la preparación local.

**Reanudación:** corrección DBA-01 desplegada y verificada en TEST; después, el responsable QA decide una nueva autorización de evaluación. El anexo técnico de DBA-01 fue entregado al DBA por la orquestación QA (HALLAZGO-G88-RLS-SANDBOX y REGRESION-RLS-SANDBOX-PROPUESTA).

## Historial breve de intentos V1

Los directorios 1–8 se retiraron por ORD-G88-040 con autorización QA del 2026-10-25. Solo se conserva el intento 9. Las referencias de la tabla son históricas y no implican evaluaciones oficiales vigentes.

| Intento | RUN | Referencia registrada | Resultado y motivo de no oficialización |
| --- | --- | --- | --- |
| 1 | RUN-G88-V1-20261024-190425 | AUT-G88-V1-20261024 | Solo contexto de operación; no consta resultado ni informe evaluable. |
| 2 | RUN-G88-V1-20261024-195711 | AUT-G88-V1-R2-20261024 | Contexto y preflight; no consta resultado ni informe evaluable. |
| 3 | RUN-G88-V1-20261024-203214 | AUT-G88-V1-R4-20261024 | Sin veredictos funcionales completos: 169 no concluyente por vínculo; 170/171 error de configuración; 172/180/266 con precondiciones sin acreditar. |
| 4 | RUN-G88-V1-20261024-205233 | AUT-G88-V1-R5-20261024 | 169–171 no concluyentes por vínculo; 172 error de automatización por serial; 180 timeout; 266 semilla no acreditada. |
| 5 | RUN-G88-V1-20261024-213141 | AUT-G88-V1-R6-20261024 | 169–171 con precondiciones fallidas; 172 sin API/UI concordantes; 180 timeout de asociaciones y 266 escenario/lectura no acreditados. |
| 6 | RUN-G88-V1-20261025-005659 | AUT-G88-V1-R7-20261025 | 169 aprobado, 170/171 rechazados; 172 sin UI concordante, 180 timeout de asociaciones y 266 escenario/lectura no acreditados. |
| 7 | RUN-G88-V1-20261025-011851 | AUT-G88-V1-R8-20261025 | 169 aprobado, 170/171/266 rechazados; 172 sin UI concordante y 180 timeout de dashboard. |
| 8 | RUN-G88-V1-20261025-014059 | AUT-G88-V1-R9-20261025 | 169 aprobado, 170/171/266 rechazados; 172 sin UI concordante y 180 timeout de umbrales. El cierre M09 no quedó confirmado según el resultado de ese intento. |
| 9 | RUN-G88-V1-20261025-020636 | AUT-G88-V1-R10-20261025 | 169 aprobado; 170, 171 y 266 rechazados; 172 y 180 ERROR_QA sin veredicto funcional. Rollback confirmado, incluido umbral QA 91 REVERTIDO_VERIFICADO. Último RUN conservado, evaluación no oficial. |

La numeración procede de los contextos/resultados históricos. No consta referencia R3 entre las nueve carpetas examinadas.
