# TC-M03-G93 — RECHAZADO

## Decisión del caso

- **Caso agrupado:** TC-M03-G93.
- **Caso original:** TC-M03-184 (RF-58 / CU04 E1) — unidad sin lecturas mostrada en GRIS con «Sin datos disponibles».
- **Decisión:** **RECHAZADO**.

En tres RUN autorizados (intentos 2, 3 y 6), una unidad recién creada sin sensores no aparece en `resumen_unidades` del dashboard: HTTP 200 sin la unidad. API-184-01/02 están RECHAZADAS por INC-M03-184-G93-01 (Desarrollo); API-184-03 fue APROBADA en el intento 3 (área 1). UI-184-01/02 siguen sin veredicto de producto por INC-M03-184-G93-02 (DBA).

| Comprobación | Resultado |
|---|---|
| API-184-01 | RECHAZADO (intentos 2, 3 y 6) |
| API-184-02 | RECHAZADO (intentos 2, 3 y 6) |
| API-184-03 | APROBADO (intento 3) |
| UI-184-01 | BLOQUEADO para el cierre (DBA, INC-M03-184-G93-02); NO_CONCLUYENTE en resultado.json del intento 6 |
| UI-184-02 | BLOQUEADO para el cierre (DBA, INC-M03-184-G93-02); NO_EJECUTADA en resultado.json del intento 6 |

**¿RUN oficial?** No; faltan veredictos UI.

**Qué falta para cerrar:** Desarrollo debe corregir INC-M03-184-G93-01 y DBA debe corregir INC-M03-184-G93-02. Después, una reevaluación V2 autorizada debe ejecutar toda la API (V1 y V2) antes de Cypress.

## Informe del RUN-G93-V1-20261026-014819

## Identificación

| Campo | Dato |
|---|---|
| Grupo y caso | G93; TC-M03-184 |
| Requisito | RF-58, CU04, flujo alterno E1; matriz Casos_Prueba(Modulo3 Agrupado).csv, fila TC-M03-G93 |
| Versión y RUN | V1, reintento 6; RUN-G93-V1-20261026-014819 |
| Ambiente y autorización del RUN | TEST; AUT-G93-V1-R6-20261026 |
| Commit | NO VERIFICADO; no se usó Git |
| Herramientas verificadas en preflight | Node v22.15.1; Newman 6.2.2; Cypress 14.5.4; Chrome disponible |
| Ejecuciones del RUN | Newman V1: 1; Cypress V1: 1; V2: 0 |
| Oficialidad | NO OFICIAL (resultado.json: oficial=false); faltan comprobaciones UI con veredicto y la variante V2 en este RUN |

Esta revisión documental de cierre no realizó solicitudes, no inició RUN y no modificó las evidencias del último RUN salvo este Markdown.

## Resultado consolidado del caso

**TC-M03-184: funcional RECHAZADO; técnico NO_CONCLUYENTE; RUN no oficial.** La API de V1 incumplió el oráculo en los intentos autorizados 2, 3 y 6: HTTP 200 sin la unidad recién creada en resumen_unidades. API-184-01 y API-184-02 quedan RECHAZADAS. API-184-03 quedó APROBADA en el intento 3 con el área 1; en el intento 6 consta NO_EJECUTADA. Las comprobaciones UI-184-01/02 están **BLOQUEADAS para el cierre consolidado** por la dependencia de sesión del entorno descrita en INC-M03-184-G93-02. Esto no sustituye los estados inmutables del último resultado.json: UI-184-01 = NO_CONCLUYENTE después de una prueba Cypress; UI-184-02 = NO_EJECUTADA. Ninguna UI se declara APROBADA ni RECHAZADA por el producto.

El resultado.json del intento 6 consigna RECHAZADO, NO_CONCLUYENTE y oficial=false. Su motivo genérico menciona “API/UI pública”; la discrepancia funcional acreditada para este cierre es la de la **API**, no una evaluación visual concluyente del panel.

## Esperado literal de la matriz y decisiones QA

**Oráculo literal de TC-M03-184:** «La unidad se muestra con estado GRIS y el mensaje "Sin datos disponibles", junto con la fecha del último dato histórico si existe; la unidad no desaparece del panel y no se devuelven errores 5xx ni valores fabricados».

La matriz pide una unidad autorizada recién creada sin lecturas y una segunda unidad con todos sus sensores sin señal; exige Cypress y Postman. Decisión QA del 2026-10-25: «Sin datos» y «Sin datos disponibles» son equivalentes como mensaje visible. INACTIVO se acepta como condición sin señal para la segunda variante. La fecha histórica solo se exige si existe; no se fabrica una fecha para aprobar. Estas decisiones no dispensan la visibilidad de la unidad ni la comprobación UI.

## Comprobaciones y evidencias

| ID | Resultado guardado en este RUN | Resultado consolidado / límite |
|---|---|---|
| API-184-01 | RECHAZADO; área 519, HTTP 200, ausente de resumen_unidades | RECHAZADO, confirmado también en áreas 514 y 515 de intentos 2 y 3 |
| API-184-02 | RECHAZADO; al faltar la unidad no puede acreditarse su estado GRIS ni ausencia de valores fabricados en el resumen | RECHAZADO por la misma discrepancia de visibilidad; no es una segunda incidencia |
| UI-184-01 | NO_CONCLUYENTE; Cypress ejecutó una prueba, sin consulta de dashboard concluyente | BLOQUEADO para cierre por sesión del entorno; no hay veredicto visual del producto |
| API-184-03 | NO_EJECUTADA | APROBADO históricamente en intento 3, área 1; no se extrapola a este RUN |
| UI-184-02 | NO_EJECUTADA | BLOQUEADO para cierre por la misma dependencia; ninguna comprobación visual acreditada |

En V1, Newman registró HTTP 200 y la aserción “unidad visible: expected undefined to exist” en [newman/newman-V1-519.json](newman/newman-V1-519.json). [resultado.json](resultado.json) conserva las cinco comprobaciones y la bitácora. [preflight.json](preflight.json) acredita herramientas; [newman/newman-G93-consolidado.html](newman/newman-G93-consolidado.html) es el reporte generado.

En UI V1, [cypress/UI-184-V1.json](cypress/UI-184-V1.json) registra una prueba NO_CONCLUYENTE, criterio INICIAL:CARGA_SIN_RESPUESTA_DIAGNOSTICO_PENDIENTE; la vista inicial terminó sin carga, con cero unidades, y la vista filtrada no se evaluó. La [captura real](cypress/g93.cy.js/UI-184-V1.png) muestra “No tienes acceso a esta sección”. El [diagnóstico Cypress](cypress/UI-184-V1.diagnostico.json) y su [bitácora](cypress/UI-184-V1.diagnostico.log) quedan dentro del RUN. La ausencia de una respuesta de dashboard en esta UI no permite atribuirle el rechazo funcional de la API.

Referencia histórica transcrita antes de depurar: intento 2, área 514, GET /iot/monitoreo/dashboard/514 HTTP 200 sin unidad, API-184-01/02 RECHAZADO; intento 3, área 515, misma respuesta y veredictos, y área 1 con API-184-03 APROBADO según newman-V2-1.json de ese intento. Esas evidencias históricas se retiraron por la autorización de limpieza; el rechazo del intento 6 mantiene evidencia primaria en este RUN.

## Incidencias de producto

### INC-M03-184-G93-01 — Desarrollo

**Título:** Una unidad productiva sin sensores no aparece en el resumen del dashboard de monitoreo.

- **Equipo inicial:** Desarrollo. La primera discrepancia pública confirmada es la respuesta del dashboard en TEST; la asignación orienta atención, no atribuye causa raíz.
- **Severidad:** MEDIA. La unidad desaparece del panel, incumpliendo RF-58/CU04 E1; el impacto observado es parcial. **Certeza:** CONFIRMADA para la omisión en la API; causa raíz NO DETERMINADA.
- **Requisito:** matriz TC-M03-184: “la unidad se muestra con estado GRIS y el mensaje Sin datos disponibles… la unidad no desaparece del panel”.
- **Pasos:** crear un área en una finca visible para el Productor, sin dispositivos ni sensores; consultar como Productor GET /iot/monitoreo/dashboard/{id_infraestructura}.
- **Esperado:** HTTP 200 con la unidad en resumen_unidades, estado_general GRIS, sin valores ni fechas fabricadas.
- **Obtenido:** HTTP 200 sin la unidad en resumen_unidades para las áreas 514, 515 y 519 en tres RUN autorizados. El 519 figura en [newman/newman-V1-519.json](newman/newman-V1-519.json); los otros dos resultados están transcritos en el historial.
- **Impacto y comprobaciones:** el Productor no puede distinguir desde el panel la unidad sin telemetría de una unidad ausente. Afecta API-184-01 y API-184-02; UI pendiente de evaluación.
- **Hipótesis local no confirmada:** en la ruta realmente leída, src/telemetry/infrastructure/repositories/monitoreo_repository.py:92-134, el resumen parte de modulo3.estados_actuales_sensores, por lo que un área sin sensores no produciría fila. En la ruta frontend realmente leída, SGPMP-FRONT-END-PWA/src/telemetry/pages/MonitoreoView.tsx:158-172, sensores.length === 0 muestra el mensaje general sin iterar unidades. No existe comprobación UI concluyente en TEST para afirmar el efecto visual ni prueba de causa raíz.

### INC-M03-184-G93-02 — DBA

**Título:** Tras recargar la página (POST /sesiones/refresh) dentro del sandbox de pruebas, /usuarios/me y /sesiones/me/permisos responden HTTP 500.

- **Equipo inicial:** DBA. Primer contacto por la relación operativa con DBA-01 de G88 y la hipótesis de identidad RLS heredada en la Session compartida del sandbox; esa relación no demuestra la causa.
- **Severidad:** ALTA para QA: bloquea la evaluación de UI con sesión dentro de este sandbox. La evidencia disponible no acredita impacto en usuarios fuera del sandbox. **Certeza:** CONFIRMADA para los HTTP 500 observados; causa RLS PROBABLE, no confirmada.
- **Contexto y pasos:** RUN con X-Test-Run-Id; abrir el frontend TEST con sesión de Productor y cargar /telemetria/monitoreo; el frontend restaura la sesión con la cookie mediante POST /sesiones/refresh; observar las peticiones siguientes.
- **Esperado:** refresh HTTP 200 y GET /usuarios/me y GET /sesiones/me/permisos HTTP 200 con perfil y permisos del Productor.
- **Obtenido:** en [cypress/UI-184-V1.json](cypress/UI-184-V1.json), 2026-10-26 01:48:44 UTC: refresh 200 en 163 ms; /usuarios/me 500 en 149 ms; /sesiones/me/permisos 500 en 145 ms, todos con eco RUN. La [captura](cypress/g93.cy.js/UI-184-V1.png) muestra “No tienes acceso a esta sección”. Después, el token anterior del ejecutor recibió 401 en GET /configuracion/fincas?solo_activas=true, según [resultado.json](resultado.json).
- **Hipótesis no confirmada:** misma causa raíz que DBA-01 de G88: identidad RLS no renovada para tablas de módulo 1 tras rotación de sesión en el sandbox. El diagnóstico de autenticación fuera del sandbox registró login HTTP 200 para Administrador y Productor; no demuestra que el refresh o las consultas posteriores funcionen fuera de él.
- **Comprobaciones afectadas:** UI-184-01 y UI-184-02; el 401 también impidió preparar V2 en este RUN. Corresponde revisar trazas de sesión/RLS y repetir la ruta pública en un RUN autorizado.

## Incidencias técnicas QA

1. **Secuencia V2 del ejecutor:** en este RUN la UI de V1 se ejecutó antes de la API de V2. El refresh dentro del sandbox dejó al ejecutor con el token previo inválido; GET /configuracion/fincas?solo_activas=true dio 401 y API-184-03 no se ejecutó. Para una reevaluación, ejecutar toda la API de V1 y V2 antes de Cypress; verificar localmente esa secuencia y luego usar autorización humana específica. Esto es un problema de orden de automatización separado de INC-02.
2. **Registro crudo del intento 6:** resultado.json contiene UI V1 NO_CONCLUYENTE y el código técnico CONTROL_AUTO_ON_AUSENTE, además de PRE_FINCAS_PRODUCTOR_NO_VISIBLES para V2. Los HTTP 500 aportan la explicación comprobada del bloqueo de sesión; no se convierte una observación UI incompleta en rechazo de producto.
3. **Incidencias anteriores resueltas en la automatización vigente:** intento 1, carga de .env.qa; intento 2, configuración Cypress 14; intento 3, error de programación del spec; intento 4, plazo de 5 s para comprobar Newman; intento 5, timeout transitorio del login. Los intentos técnicos no sustituyen la evidencia funcional de 2, 3 y 6.

## Historial de intentos y diagnósticos

Los datos siguientes se transcriben antes de retirar las carpetas antiguas; sus archivos originales ya no forman parte del grupo. No se presentan como evidencias generadas por este RUN.

| Registro | Autorización | Resultado y dato preservado |
|---|---|---|
| Intento 1 — RUN-G93-V1-20261025-150037 | AUT-G93-V1-20261025 | Aborto local: .env.qa no cargado; sin peticiones de negocio. |
| Intento 2 — RUN-G93-V1-20261025-154913 | AUT-G93-V1-R2-20261025 | Área V1 514; Newman GET /iot/monitoreo/dashboard/514 HTTP 200 sin unidad en resumen_unidades; API-184-01/02 RECHAZADO. UI ERROR_QA por configuración Cypress; rollback CONFIRMADO. |
| Diagnóstico — DIAG-G93-20261025-173337 | AUT-G93-DIAG-20261025 | Áreas 1, 2 y 3, finca 1, todos sus sensores INACTIVO; 268 y 337 ACTIVO; 349, 390, 389 y 399 sin resumen. |
| Intento 3 — RUN-G93-V1-20261025-182304 | AUT-G93-V1-R3-20261025 | Área V1 515, HTTP 200 sin unidad; API-184-01/02 RECHAZADO. Área V2 1, finca 1, sensores INACTIVO y dato_desactualizado; API-184-03 APROBADO, unidad GRIS y sin valores actuales fabricados (evidencia entonces newman-V2-1.json). UI ERROR_QA por error del spec; rollback CONFIRMADO. |
| Intento 4 — RUN-G93-V1-20261025-221324 | AUT-G93-V1-R4-20261025 | Aborto en preflight: Newman --version superó 5 s; sin peticiones de negocio. |
| Intento 5 — RUN-G93-V1-20261025-222242 | AUT-G93-V1-R5-20261025 | Timeout transitorio de login; sin peticiones de negocio. |
| Diagnóstico — DIAG-G93-20261026-013518 | AUT-G93-DIAG-AUTH-20261025 | Login Administrador y Productor HTTP 200 en https://www.api.inmero.co/api-sgpmp-test; base observada del frontend https://api.inmero.co/api-sgpmp-test. |
| Intento 6 — RUN-G93-V1-20261026-014819 | AUT-G93-V1-R6-20261026 | Área V1 519, HTTP 200 sin unidad; API-184-01/02 RECHAZADO. UI V1 NO_CONCLUYENTE por dependencia de sesión, V2 NO_EJECUTADA; rollback CONFIRMADO según comprobaciones públicas. Único RUN conservado. |

## Cierre y rollback

En el intento 6, DELETE /test-control/runs/RUN-G93-V1-20261026-014819 respondió HTTP 200. La verificación posterior registró GET del área 519 HTTP 404 y GET del dashboard filtrado HTTP 200; resultado.json consigna rollback CONFIRMADO para estos recursos públicos. No se verificó reversión de auditoría, correo u otros efectos externos, ni se extrapola el rollback a los diagnósticos. El cierre del RUN no vuelve oficial el resultado funcional.

## Conclusión y acciones

G93 queda **CERRADO documentalmente, RECHAZADO funcionalmente por API y con UI BLOQUEADA por INC-M03-184-G93-02**. El RUN conservado es no oficial. Desarrollo debe atender INC-M03-184-G93-01; DBA debe diagnosticar INC-M03-184-G93-02 con la relación a DBA-01 de G88, sin asumir causa raíz. Antes de una nueva evaluación autorizada, resolver la dependencia de sesión y reordenar el ejecutor para completar API V1/V2 antes de Cypress; repetir las comprobaciones API y UI exigidas y emitir un veredicto UI con evidencia real.
