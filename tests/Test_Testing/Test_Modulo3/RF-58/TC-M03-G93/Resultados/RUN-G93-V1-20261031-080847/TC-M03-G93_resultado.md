# TC-M03-G93 — RECHAZADO

## 1. Identificación

Proyecto SIGAB/SGPMP; módulo 3, RF-58/CU04, flujo alterno E1; grupo G93; caso TC-M03-184; versión V1; ambiente TEST según el registro del RUN; fecha y hora 2026-10-31 08:08:47 (marca del RUN; zona no acreditada); RUN RUN-G93-V1-20261031-080847; autorización AUT-G93-V1-R8-20261031. Rama NO_VERIFICADA; commit NO_VERIFICADO. Node de regeneración v22.15.1 (verificado localmente); versiones de Node, Newman, Cypress y Postman del RUN: NO_VERIFICADAS en los artefactos. Newman: 1 ejecución registrada, 2 solicitudes y 5 aserciones. Cypress: 2 pruebas registradas.

## 2. Resumen ejecutivo y decisión del grupo

**Decisión del caso del grupo:** RECHAZADO. RUN oficial; estado técnico OK. Total 1 caso: aprobados 0, rechazados 1, bloqueados 0 y no concluyentes 0. La API mostró el área nueva #700 en GRIS y sin sensores; la UI omitió su tarjeta. La variante del área #1 sí mostró tarjeta GRIS, «Sin datos» y fecha histórica. Estas son cinco comprobaciones de un mismo caso.

| Caso | Funcional | Técnico |
|---|---|---|
| TC-M03-184 | RECHAZADO | OK |

## 3. Detalle por caso y comprobaciones API/UI

### TC-M03-184

**Caso original y objetivo:** Verificar que una unidad sin lecturas se muestre en GRIS con el mensaje "Sin datos disponibles".

**Precondiciones:** Cero lecturas válidas en el periodo esperado. Unidad autorizada recién creada sin lecturas y una segunda unidad con todos sus sensores sin señal. En el RUN: área #700 con 0 sensores; área #1 con 4 sensores (3 INACTIVO y 1 BUFFER_ACTIVO, según el registro de candidata).

**Pasos ejecutados:** Se creó y consultó el área nueva; se consultó la segunda área con sensores sin datos actuales. Newman verificó ambas respuestas del dashboard; Cypress comprobó el panel global y la vista filtrada de ambas variantes. Se consultó la restricción por finca y se verificó el cierre público del RUN.

**Entradas:** `GET /iot/monitoreo/dashboard?id_infraestructura=700&pagina=1&por_pagina=50`; `GET /iot/monitoreo/dashboard?id_infraestructura=1&pagina=1&por_pagina=50`; filtros de Monitoreo para las áreas #700 y #1.

**Esperado:** La unidad se muestra con estado GRIS y el mensaje "Sin datos disponibles", junto con la fecha del último dato histórico si existe; la unidad no desaparece del panel y no se devuelven errores 5xx ni valores fabricados.

**Observado por API pública:** **API-184-01:** HTTP 200; área #700 incluida en resumen_unidades; estado GRIS. **API-184-02:** 0 sensores; mensaje «Sin datos disponibles»; sin valores actuales fabricados; último dato no registrado. **API-184-03:** HTTP 200; área #1, 3 INACTIVO, 1 BUFFER_ACTIVO; estado GRIS; último dato 2026-10-25T23:03:14.722257Z.

**Observado por UI:** **UI-184-01:** área #700 seleccionada; no aparece la tarjeta GRIS de la unidad; KPI en 0, «0 alertas activas» y «No hay sensores para mostrar con los filtros actuales». **UI-184-02:** área #1; tarjeta visible, GRIS, «Sin datos»; fecha histórica visible; sin valores fabricados.

**Decisión del caso:** **RECHAZADO.** API-184-01/02/03 y UI-184-02 cumplen; UI-184-01 incumple el oráculo: «la unidad no desaparece del panel» y «se muestra con estado GRIS y Sin datos disponibles». Con el área #700 seleccionada no aparece la tarjeta GRIS ni el mensaje de estado en la unidad. Los KPI en cero y el mensaje genérico no sustituyen esa presentación.

**Qué falta o cambió:** Corregir la presentación de la unidad nueva sin sensores y acreditar la tarjeta GRIS y el mensaje en una reevaluación API/UI autorizada; la causa raíz en TEST no está determinada.

| Comprobación | Tipo | Esperado | Observado | HTTP | Estado | Evidencia |
|---|---|---|---|---|---|---|
| API-184-01 | API | HTTP 200; unidad nueva presente en resumen_unidades, GRIS | HTTP 200; área #700 incluida en resumen_unidades; estado GRIS | 200 | APROBADO | [newman/newman-G93.json](newman/newman-G93.json) |
| API-184-02 | API | cero sensores; mensaje Sin datos disponibles; fecha histórica válida si existe; sin valores fabricados | 0 sensores; mensaje «Sin datos disponibles»; sin valores actuales fabricados; último dato no registrado | 200 | APROBADO | [newman/newman-G93.json](newman/newman-G93.json) |
| API-184-03 | API | unidad con todos los sensores SIN_SEÑAL/INACTIVO/BUFFER_ACTIVO, GRIS; histórico real si existe | HTTP 200; área #1, 3 INACTIVO, 1 BUFFER_ACTIVO; estado GRIS; último dato 2026-10-25T23:03:14.722257Z | 200 | APROBADO | [newman/newman-G93.json](newman/newman-G93.json) |
| UI-184-01 | UI | tarjeta nueva GRIS y Sin datos/Sin datos disponibles; sin valores de sensores fabricados | área #700 seleccionada; no aparece la tarjeta GRIS de la unidad; KPI en 0, «0 alertas activas» y «No hay sensores para mostrar con los filtros actuales» | 200 | RECHAZADO | [cypress/UI-184-V1.json](cypress/UI-184-V1.json), [cypress/g93.cy.js/UI-184-V1.png](cypress/g93.cy.js/UI-184-V1.png) |
| UI-184-02 | UI | tarjeta de unidad sin señal visible, GRIS y fecha histórica si existe | área #1; tarjeta visible, GRIS, «Sin datos»; fecha histórica visible; sin valores fabricados | 200 | APROBADO | [cypress/UI-184-V2.json](cypress/UI-184-V2.json), [cypress/g93.cy.js/UI-184-V2.png](cypress/g93.cy.js/UI-184-V2.png) |

El spec registró `filtro_aplicado_por_spec` cuando añadió el ID a una petición inicial del frontend. La respuesta procede de la API real filtrada; la segunda vista utilizó el selector de la página. La matriz exige Cypress y Postman/Newman para TC-M03-184.

## 4. Incidencias y observaciones

### Incidencias funcionales y antecedentes

### INC-M03-184-G93-01 — CORREGIDA en API (#785)

La unidad nueva figura en el resumen de la API, con cero sensores, estado GRIS y «Sin datos disponibles» ([Newman](newman/newman-G93.json)). Equipo inicial: Desarrollo. Severidad MEDIA por la afectación parcial observada antes; certeza CONFIRMADA del estado API en este RUN. Esto no acredita la UI ni una causa raíz.

Antecedente previo a #785: el área 519 faltó en resumen_unidades ([API del intento 6](api/antecedentes/intento-6-api-area-519.json)); el intento 7 confirmó API-184-01/02 APROBADO ([candidatas V2 del intento 7](api/antecedentes/intento-7-candidatas-v2.json)). [índice con SHA-256 de originales](api/antecedentes/indice.json). Los RUN técnicos de origen se eliminan después de preservar estos extractos; los enlaces apuntan al RUN oficial.

### INC-M03-184-G93-02 — NO REPRODUCIDA con peticiones serializadas

Sesión UI: /usuarios/me y /sesiones/me/permisos respondieron HTTP 200 con eco del RUN en ambas vistas ([acta V1](cypress/UI-184-V1.json), [acta V2](cypress/UI-184-V2.json)). Equipo inicial: DBA, por la discrepancia previa del sandbox (DBA-01). La concurrencia sobre una conexión/transacción única es una hipótesis reforzada por la serialización, NO CONFIRMADA como causa. Severidad MEDIA por el bloqueo visual del intento 7; en este RUN no se reprodujo. Certeza CONFIRMADA del estado de sesión bajo estas condiciones, sin extrapolar a concurrencia libre.

Antecedentes de sandbox: [sesión UI del intento 6](api/antecedentes/intento-6-sesion-ui.json) registra refresh 200 seguido de /usuarios/me y /sesiones/me/permisos 500; [sesión UI concurrente del intento 7](api/antecedentes/intento-7-sesion-ui.json) registra respuestas concurrentes 500/401. [candidatas V2 del intento 7](api/antecedentes/intento-7-candidatas-v2.json) documenta candidatas V2 descartadas antes de la decisión QA sobre BUFFER_ACTIVO. Las [capturas del intento 6](api/antecedentes/intento-6-ui.png) y [intento 7](api/antecedentes/intento-7-ui.png) no muestran datos personales. En este RUN oficial, con cola de peticiones, esos 500/401 no se reprodujeron. Los RUN técnicos de origen se eliminan después de preservar estos extractos.

### INC-M03-184-G93-03 — La unidad sin sensores no aparece en el panel; se muestran KPI en cero

- **Esperado:** Con el área #700 seleccionada, tarjeta de la unidad en GRIS con «Sin datos disponibles» (o «Sin datos» por decisión QA), aunque no tenga sensores; la unidad no desaparece.
- **Obtenido:** área #700 seleccionada; no aparece la tarjeta GRIS de la unidad; KPI en 0, «0 alertas activas» y «No hay sensores para mostrar con los filtros actuales». Las respuestas filtradas del dashboard fueron HTTP 200 y la API incluyó el área en resumen_unidades.
- **Evidencia:** [cypress/UI-184-V1.json](cypress/UI-184-V1.json) y [cypress/g93.cy.js/UI-184-V1.png](cypress/g93.cy.js/UI-184-V1.png); [Newman](newman/newman-G93.json). Discrepancia UI confirmada en TEST; causa técnica NO CONFIRMADA.
- **Impacto y severidad:** MEDIA. El Productor no ve la unidad en el panel, aunque puede recuperarse por la API; el alcance comprobado es esta variante.
- **Equipo inicial:** Desarrollo. La primera discrepancia está en la interfaz con respuesta API correcta; no se atribuye causa raíz.
- **Relación:** issue #779 / PR #452; solicitar reapertura o seguimiento de corrección incompleta de la UI.
- **Hipótesis por lectura local:** `SGPMP-FRONT-END-PWA/src/telemetry/pages/MonitoreoView.tsx:208-214` muestra el mensaje cuando `sensores.length === 0 && !error` antes de los grupos con `UnidadCard` (líneas 215-230); `src/telemetry/components/UnidadCard.tsx:4` registra INC-M03-205-G93. Esto orienta la investigación y no prueba qué código exacto se desplegó en TEST.

**Reproducción y acción correctiva:**

1. Abrir Monitoreo como Productor con el área #700 sin sensores.
2. Seleccionar el área en el filtro.
3. Comparar la tarjeta ausente, los KPI y el mensaje con `GET /iot/monitoreo/dashboard?id_infraestructura=700`.
4. Revisar la rama de render, mostrar la tarjeta aunque la lista de sensores esté vacía y repetir la comprobación API/UI en un RUN autorizado.

### RLS y decisiones QA

**RLS-G93-01:** CUMPLE; Unidad ajena ausente del resumen; HTTP 200. Es una comprobación técnica, separada del oráculo del caso.

Decisión QA 2026-10-25: en UI, «Sin datos» y «Sin datos disponibles» son equivalentes; INACTIVO acredita ausencia de señal. Decisión QA 2026-10-31: BUFFER_ACTIVO también acredita ausencia de señal en la variante 2 solo si todos los sensores están en SIN_SEÑAL, INACTIVO o BUFFER_ACTIVO y ninguno ACTIVO. La fecha histórica se exige solo si existe. V2, panel global: texto observado «Sin datos»; equivalente a «Sin datos disponibles» por decisión QA de 2026-10-25. Sin incidencia ni efecto en el veredicto. V2, vista filtrada: texto observado «Sin datos»; equivalente a «Sin datos disponibles» por decisión QA de 2026-10-25. Sin incidencia ni efecto en el veredicto.

### Problemas técnicos QA

- Ninguno registrado.

### Dependencias y rendimiento

- Ninguna registrada.

Sin hallazgos adicionales registrados.

## 5. Análisis de fallos

**Primer punto de discrepancia:** la API pública devolvió HTTP 200 e incluyó el área #700 en `resumen_unidades` con GRIS y cero sensores; Cypress registró HTTP 200 y mostró que su tarjeta no apareció en la interfaz. INC-03 se deriva inicialmente a Desarrollo por la presentación UI; la causa raíz de lo desplegado en TEST sigue NO DETERMINADA. **Hipótesis por lectura local anterior:** `SGPMP-FRONT-END-PWA/src/telemetry/pages/MonitoreoView.tsx:208-230` podría mostrar el estado vacío antes de renderizar `UnidadCard`; no se leyó el checkout frontend en esta orden ni se verificó su versión en TEST. INC-02 no se reprodujo con la sesión serializada y su explicación por concurrencia sigue como hipótesis. Código del producto consultado en esta orden: ninguna ruta; se leyeron la matriz, la referencia local RF-58/CU04 y las evidencias del RUN.

## 6. Conclusiones y acciones

RECHAZADO: la API y UI-184-02 cumplieron, pero UI-184-01 no mostró la unidad nueva en GRIS con el mensaje requerido. Desarrollo debe atender INC-03 y comprobar la tarjeta en una reevaluación API/UI autorizada; relacionar el seguimiento con #779 / PR #452. Responsable QA: cerrar documentalmente INC-01 en API y conservar INC-02 como no reproducida bajo estas condiciones. Esta edición documental no ejecutó pruebas ni cambia veredictos.

## 7. Herramientas, evidencias, bitácora y rollback

**Newman:** 1 ejecución registrada, 2 solicitudes y 5 aserciones (0 fallidas): [JSON](newman/newman-G93.json) y [HTML](newman/newman-G93-consolidado.html). **Cypress:** 2 pruebas; [acta V1](cypress/UI-184-V1.json), [captura V1](cypress/g93.cy.js/UI-184-V1.png), [acta V2](cypress/UI-184-V2.json) y [captura V2](cypress/g93.cy.js/UI-184-V2.png).

**Evidencias existentes del RUN:**

- [preflight.json](preflight.json)
- [newman/newman-G93.json](newman/newman-G93.json)
- [cypress/UI-184-V1.json](cypress/UI-184-V1.json)
- [cypress/UI-184-V1.diagnostico.json](cypress/UI-184-V1.diagnostico.json)
- [cypress/UI-184-V1.diagnostico.log](cypress/UI-184-V1.diagnostico.log)
- [cypress/UI-184-V2.json](cypress/UI-184-V2.json)
- [cypress/UI-184-V2.diagnostico.json](cypress/UI-184-V2.diagnostico.json)
- [cypress/UI-184-V2.diagnostico.log](cypress/UI-184-V2.diagnostico.log)
- [newman/newman-G93-consolidado.html](newman/newman-G93-consolidado.html)
- [cypress/g93.cy.js/UI-184-V1.png](cypress/g93.cy.js/UI-184-V1.png)
- [cypress/g93.cy.js/UI-184-V2.png](cypress/g93.cy.js/UI-184-V2.png)

**Antecedentes:** [índice con SHA-256 de originales](api/antecedentes/indice.json), [API del intento 6](api/antecedentes/intento-6-api-area-519.json), [sesión UI del intento 6](api/antecedentes/intento-6-sesion-ui.json), [sesión UI concurrente del intento 7](api/antecedentes/intento-7-sesion-ui.json), [candidatas V2 del intento 7](api/antecedentes/intento-7-candidatas-v2.json); [captura del intento 6](api/antecedentes/intento-6-ui.png) y [captura del intento 7](api/antecedentes/intento-7-ui.png).

**Bitácora resumida:** 23 solicitudes directas registradas; 16 dentro del RUN. El detalle saneado está en [resultado.json](resultado.json).

**Cierre y rollback:** DELETE HTTP 200; rollback CONFIRMADO con 3/3 comprobaciones conformes. DELETE y relaciones públicas acreditadas.

| Recurso | HTTP | Conforme |
|---|---|---|
| area_v1 | 404 | Sí |
| dashboard_area_v1 | 200 | Sí |
| semilla_v2_estable | 200 | Sí |

El área #700 devolvió 404 tras el cierre; la lectura pública del dashboard y la semilla estable de la variante 2 quedaron conformes. No consta reversión de auditoría ni de posibles efectos externos en las evidencias de rollback.
