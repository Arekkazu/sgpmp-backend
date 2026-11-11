# TC-M06-G36 — RECHAZADO

## Identificación

Grupo G36; casos TC-M06-009, TC-M06-010; RF-86 CA-12/13, Restricción 5; versión 1, intento 2; RUN RUN-G36-V1-20261108-161426; ambiente TEST; autorización AUT-G36-V1-R2-20261108; commit TEST no verificado; Node v22.15.1; Newman 6.2.2; Cypress 0 (matriz solo API).

## Decisión del caso

| Caso | Estado | Motivo |
|---|---|---|
| TC-M06-009 | RECHAZADO | 9 respuesta(s) no orientaron al registro correctivo. |
| TC-M06-010 | RECHAZADO | El contrato OpenAPI desplegado no expone ambas operaciones: crear y aprobar correctivo de variación. |

Oficial: true.

## Preparación y candidatos

Activo 945, período 8, precio vigente 18, rebase false, evento 1286, variación 249, línea 892.

- Activo 943: DESCARTADO. Elegible con rebase; se prefirió candidato sin rebase.
- Activo 944: DESCARTADO. Elegible con rebase; se prefirió candidato sin rebase.
- Activo 945: SELECCIONADO. Elegible; cálculo previo usa precio y peso vigentes; sin rebase.
- Activo 946: DESCARTADO. Elegible con rebase; se prefirió candidato sin rebase.
- Activo 947: DESCARTADO. Elegible con rebase; se prefirió candidato sin rebase.
- Activo 948: DESCARTADO. Activo no ACTIVO.
- Activo 951: DESCARTADO. Especie no bovina.
- Activo 949: DESCARTADO. Especie no bovina.
- Activo 950: DESCARTADO. Especie no bovina.

## Detalle por caso

### TC-M06-009

- **Preparación:** Activo 945, período 8 ABIERTO, evento 1286, variación 249 y línea 892; precio vigente 18, sin rebase.
- **Esperado:** PUT, PATCH y DELETE bloqueados sobre variación y línea; respuesta orienta al correctivo; ambos registros idénticos campo a campo.
- **Observado:** 9 intentos PUT, PATCH y DELETE sobre /finanzas/variaciones/249, /finanzas/periodos/8/variaciones/249, /finanzas/lineas/892: todos HTTP 404 Not Found, sin código de error ni mensaje que mencione el registro correctivo. Comparación campo a campo: variación (17 campos), SHA-256 idéntica antes y después; línea (26 campos), SHA-256 idéntica antes y después.
- **Qué se cumplió:** Los 9 intentos quedaron bloqueados y no alteraron ningún campo: se cumplió la inmutabilidad append-only de la variación y su línea.
- **Qué falló y por qué:** CA-12: 9 respuesta(s) no orientaron al registro correctivo. El bloqueo por sí solo no satisface la orientación exigida.
- **Decisión:** RECHAZADO.

### TC-M06-010

- **Preparación:** Activo 945, período 8 ABIERTO, evento 1286, variación 249 y línea 892; precio vigente 18, sin rebase.
- **Esperado:** Nuevo correctivo con monto opuesto y referencia explícita al UUID original; ineficaz antes de aprobación del Contador; ambos visibles sin eliminación; línea inversa de valor positivo.
- **Observado:** Contrato /openapi.json: HTTP 200; operaciones M06 49; operaciones correctivas ninguna; huella SHA-256 769bc4329d9189b92e35ae18782b1da38d798e1e49e8ca381728ff748f966d2d.
- **Qué se cumplió:** Se completó la lectura del contrato público; no se acreditó la ejecución de un correctivo.
- **Qué falló y por qué:** CA-13: El contrato OpenAPI desplegado no expone ambas operaciones: crear y aprobar correctivo de variación. Sin operaciones públicas de creación y aprobación, no se pudo ejecutar el mecanismo exigido.
- **Decisión:** RECHAZADO.

## Comprobaciones API

- G36-API-010-01 (TC-M06-010): RECHAZADO; El contrato OpenAPI desplegado no expone ambas operaciones: crear y aprobar correctivo de variación.; evidencia resultado.json.
- G36-API-010-02 (TC-M06-010): RECHAZADO; El contrato OpenAPI desplegado no expone ambas operaciones: crear y aprobar correctivo de variación.; evidencia resultado.json.
- G36-API-009-01 (TC-M06-009): RECHAZADO; 9 respuesta(s) no orientaron al registro correctivo.; evidencia resultado.json.
- G36-API-009-02 (TC-M06-009): RECHAZADO; 9 respuesta(s) no orientaron al registro correctivo.; evidencia resultado.json.

## Evidencias reales

- preflight.json
- resultado.json
- TC-M06-G36_resultado.md
- newman/newman-G36.json
- newman/newman-G36.html

## Incidencias de producto

### INC-M06-G36-01 — No existe el mecanismo de registro correctivo de variaciones y los intentos de modificación no orientan hacia él

**Casos:** TC-M06-009, TC-M06-010.

**Requisito:** RF-86 CA-12, CA-13, Restricción 5 (append-only) y CU05 FA-6.

**Pasos para reproducir:** Con el período 8 ABIERTO, activo 945 y variación 249 GANANCIA_TRANSFORMACION_BIOLOGICA ligada al evento 1286 y línea 892, intentar PUT, PATCH y DELETE sobre /finanzas/variaciones/249, /finanzas/periodos/8/variaciones/249 y /finanzas/lineas/892; leer variación y línea antes y después para comparar todos los campos; consultar GET /openapi.json y buscar operaciones públicas para crear y aprobar el correctivo de variación.

**Esperado:** Los intentos directos se bloquean con una respuesta que orienta al registro correctivo; variación y línea permanecen idénticas. El Contador puede crear un nuevo correctivo con monto opuesto y referencia explícita al UUID original, aprobarlo y consultar ambos registros en el historial del período y la línea inversa de valor positivo.

**Obtenido:** TC-M06-009: los 9 intentos devolvieron HTTP 404 Not Found, sin código de error ni mensaje que mencione el registro correctivo; variación (17 campos) y línea (26 campos) mantuvieron huellas SHA-256 idénticas antes y después. TC-M06-010: GET /openapi.json devolvió HTTP 200; entre 49 operaciones M06 no hay operaciones para crear ni aprobar un correctivo de variación; huella SHA-256 del contrato 769bc4329d9189b92e35ae18782b1da38d798e1e49e8ca381728ff748f966d2d. El flujo correctivo no pudo ejecutarse por la API pública observada.

**Apoyo de código leído, sin atribución causal:** src/financial_valuation/infrastructure/routers/m06_router.py:79-508 no declara PUT/PATCH/DELETE de variaciones o líneas ni rutas para crear/aprobar correctivos de variación. Las búsquedas en src/financial_valuation y SGPMP-FRONT-END-PWA/src/financial_valuation no encontraron referencias a correctivo. alembic/baseline/esquema_baseline.sql:12710-12739,43225-43235 protege variaciones frente a UPDATE/DELETE; alembic/versions/c4d81e6f2a95_m06_nic41_esquema_rfc018.py:745-824 define protección de líneas y campos id_linea_corregida y tipo_hecho_corregido. Estas lecturas no prueban la versión desplegada ni la causa raíz.

**Impacto y severidad:** ALTA. El Contador no puede corregir una variación errónea dentro del período abierto ni recibe guía hacia el mecanismo correctivo. El bloqueo append-only se cumple, pero sin una vía pública de corrección el error queda sin tratamiento contable. CA-13 exige una corrección contable relevante que quedó bloqueada sin alternativa pública acreditada; CA-12 tampoco orientó al usuario tras los nueve intentos. Certeza CONFIRMADA de la discrepancia observada; causa raíz NO DETERMINADA.

**Primera atención:** Desarrollo. La primera discrepancia se comprobó en respuestas y contrato de la API pública de TEST; la asignación inicial no atribuye causa técnica.

**Evidencias:** `resultado.json`, `newman/newman-G36.json`, `newman/newman-G36.html`.

## Problemas técnicos

Ninguno observado.

Las rutas de código local consultadas figuran en README; no prueban la versión desplegada ni la causa raíz.

## Cierre y rollback

DELETE HTTP 200; rollback verificado mediante lecturas públicas poscierre. ACTIVO y peso restaurados; eventos M02, variación, línea, cálculos y auditoría del RUN ausentes en lecturas poscierre. Los efectos RF-52 o backlog fuera de la transacción no quedan cubiertos por estas lecturas.

## Conclusión y acciones

TC-M06-009: bloqueo e inmutabilidad cumplen, pero falla la orientación al correctivo exigida por CA-12. TC-M06-010: el contrato público no ofrece crear ni aprobar el mecanismo exigido por CA-13. Ambos incumplimientos se agrupan en una sola incidencia. Desarrollo implementa el mecanismo y la orientación; QA reevalúa con nueva autorización. Solicitudes dentro del RUN: 56/80.

Actualización del informe (2026-11-08): detalle por caso legible e incidencia completa; veredictos sin cambios.
