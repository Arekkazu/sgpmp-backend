# TC-M03-G94 — BLOQUEADO

## Decisión del caso

- **Caso agrupado:** TC-M03-G94
- **Caso original:** TC-M03-185 (RF-58 / CU04 E4) — usuario sin unidades productivas asignadas.
- **Decisión:** **BLOQUEADO**
- **Motivo:** API-185-01 y API-185-02 están APROBADAS en dos RUN. UI-185-01 sigue sin veredicto por la dependencia de sesión INC-M03-184-G93-02 (DBA); la UI es obligatoria para aprobar el caso.

| Comprobación | Resultado |
|---|---|
| API-185-01 | APROBADO en intentos 1 y 2 |
| API-185-02 | APROBADO en intentos 1 y 2 |
| UI-185-01 | BLOQUEADO en intento 1; NO_CONCLUYENTE en intento 2 |

- **¿RUN oficial?:** No; falta el veredicto de UI-185-01.
- **Qué falta para cerrar:** DBA debe corregir INC-M03-184-G93-02; después, un único RUN autorizado de reevaluación de la UI y revisión de su oráculo visual.

## Identificación del RUN consolidado

Grupo G94; caso TC-M03-185; RF-58/CU04 E4; V1; RUN-G94-V1-20261026-043704 (intento 2, único RUN conservado); ambiente TEST; autorización AUT-G94-V1-R2-20261026. Commit NO VERIFICADO (Git prohibido). Herramientas verificadas en el preflight del intento 2: Node v22.15.1, Newman 6.2.2, Cypress 14.5.4 y Chrome disponible. RUN oficial: no; consume versión: sí. Este informe consolida también el intento 1, RUN-G94-V1-20261026-041954, autorizado como AUT-G94-V1-20261026. Ambos son V1.

## Esperado y observado por caso

Esperado literal de la matriz: HTTP 200 con arreglos vacíos. La interfaz muestra "No tiene unidades productivas asignadas" y sugiere contactar al administrador; no se devuelve ningún dato de otras granjas ni error interno.

Observado en ambos RUN: las dos comprobaciones API devolvieron HTTP 200, total 0 y arreglos vacíos, sin datos ajenos. La UI no llegó a cargar /telemetria/monitoreo ni a solicitar el dashboard. Ningún intento acredita el texto, la sugerencia de contacto o la ausencia de tarjetas y error interno en la pantalla del caso.

## Comprobaciones API/UI por intento

| Comprobación | Intento 1: RUN 041954 (transcripción histórica) | Intento 2: RUN 043704 (evidencia conservada) |
|---|---|---|
| API-185-01 | APROBADO: HTTP 200, total 0, arreglos vacíos, eco RUN | APROBADO: HTTP 200, total 0, arreglos vacíos, eco RUN; [Newman JSON](newman/newman-G94.json) |
| API-185-02 | APROBADO: HTTP 200, total 0, arreglos vacíos, eco RUN | APROBADO: HTTP 200, total 0, arreglos vacíos, eco RUN; [Newman JSON](newman/newman-G94.json) |
| UI-185-01 | BLOQUEADO: refresh 200; perfil y permisos 500 dentro del sandbox; dashboard no solicitado | NO_CONCLUYENTE: perfil y permisos fuera del sandbox sin respuesta durante el RUN; dashboard no solicitado; [acta UI](cypress/UI-185-01.json) y [captura](cypress/g94.cy.js/UI-185-01.png) |

El estado funcional del intento 2 en su resultado.json es NO_CONCLUYENTE; su estado técnico es NO_CONCLUYENTE. La decisión consolidada BLOQUEADO expresa que la dependencia DBA sigue abierta y la UI obligatoria carece de veredicto; no reescribe los estados de los artefactos.

## Decisión metodológica de la UI en el intento 2

El responsable QA autorizó el 2026-10-26 que solo POST /sesiones/refresh, GET /usuarios/me y GET /sesiones/me/permisos del navegador viajaran fuera del sandbox, sin cabeceras RUN ni eco. Las demás peticiones, incluidos contexto y GET /iot/monitoreo/dashboard, permanecieron dentro y exigían eco RUN. Los registros de peticiones acreditan el aislamiento por cabeceras: las rutas externas no tienen eco y las internas con respuesta lo tienen. La sesión restaurada fuera del sandbox no permitió llegar al dashboard; por tanto, esta variante no resolvió la dependencia. La rotación real de sesión por refresh fuera del sandbox persiste después del DELETE y no queda cubierta por el rollback.

## Historial de intentos y evidencias reales

| Intento | RUN | UI y sesión | Cierre |
|---|---|---|---|
| 1 | RUN-G94-V1-20261026-041954 (eliminado por decisión QA) | Refresh 200 con cabeceras; GET /usuarios/me y GET /sesiones/me/permisos 500; pantalla "No tienes acceso a esta sección". GET /usuarios/me con token previo al RUN fue 200. | DELETE 200; asignaciones originales y posteriores iguales |
| 2 | RUN-G94-V1-20261026-043704 | Refresh 200 fuera; perfil y permisos fuera sin respuesta en unos 34 s mientras el RUN seguía abierto. Dentro, tema 401 con token rotado fuera; tras nuevo refresh, tema e idioma 500. Cypress agotó la espera del dashboard, que nunca se solicitó. | DELETE 200; asignaciones originales y posteriores iguales |

**Transcripción del intento 1 antes de su eliminación.** Autorización AUT-G94-V1-20261026; intervalo 2026-10-26 04:19:54–04:21:05 UTC. La bitácora del ejecutor registró dos logins HTTP 200 fuera del RUN; GET /usuarios/me HTTP 200 con el token previo; GET del detalle de usuario, de fincas y de áreas activas de finca 1 HTTP 200; PUT de fincas HTTP 200; verificaciones posteriores de detalle y fincas HTTP 200. Newman ejecutó API-185-01 y API-185-02: ambas respuestas HTTP 200, total 0, arreglos vacíos y eco RUN. En Cypress hubo una prueba ejecutada y fallida, sin pendientes ni omitidas. El acta UI registró dentro del sandbox y con eco: POST /sesiones/refresh 200, GET /configuracion/interfaz/contexto 200, GET /usuarios/me 500, GET /sesiones/me/permisos 500, GET /configuracion/personalizacion/idioma 200, GET /configuracion/personalizacion/tema 200 y GET /notificaciones 200. El dashboard no se solicitó. La captura mostró “No tienes acceso a esta sección”. El cierre registró DELETE HTTP 200 y lectura pública posterior HTTP 200; las fincas [1,57,80,184] quedaron restituidas al mismo conjunto original. El resultado funcional de TC-M03-185 fue BLOQUEADO y el técnico NO_CONCLUYENTE.

La evidencia nativa del intento 1 se eliminó por decisión del responsable QA el 2026-10-26; este párrafo conserva sus datos sin enlaces a archivos eliminados. La misma secuencia de sesión de INC-M03-184-G93-02 dentro del sandbox consta también en la evidencia conservada de G93: [acta UI V1](../../../TC-M03-G93/Resultados/RUN-G93-V1-20261026-014819/cypress/UI-184-V1.json) y [captura real](../../../TC-M03-G93/Resultados/RUN-G93-V1-20261026-014819/cypress/g93.cy.js/UI-184-V1.png). Es evidencia independiente de G93, no reemplaza los archivos eliminados de G94.

Evidencias conservadas del [intento 2](resultado.json): [preflight](preflight.json), [Newman JSON](newman/newman-G94.json), [Newman HTML](newman/newman-G94.html), [acta UI](cypress/UI-185-01.json), [log Cypress](cypress/UI-185-01.log), [resumen Cypress](cypress/UI-185-01-cypress.json) y [captura](cypress/g94.cy.js/UI-185-01.png). Los estados del intento 2 proceden de su resultado.json y acta UI; los del intento 1 se transcribieron antes de retirar sus artefactos.

## Incidencias de producto

**INC-M03-184-G93-02 — abierta; equipo inicial de atención: DBA; severidad ALTA para QA.** Esperado: una sesión válida permite leer perfil y permisos con HTTP 200 y cargar /telemetria/monitoreo dentro del RUN. En el intento 1, refresh dentro del sandbox devolvió 200, pero perfil y permisos devolvieron 500; el perfil con token previo al RUN devolvió 200. En el intento 2, el refresh externo fue 200, pero perfil y permisos externos no respondieron durante unos 34 s mientras el RUN permanecía abierto; dentro del sandbox, tema devolvió 401 con el token rotado fuera y, tras otro refresh, tema e idioma devolvieron 500. El dashboard no se solicitó en ninguno de los intentos.

La primera discrepancia comprobada de sesión bajo el RUN orienta el primer contacto a DBA, según la incidencia ya abierta; esto no atribuye causa raíz. Certeza CONFIRMADA para los códigos HTTP y las ausencias de respuesta registradas; causa raíz NO DETERMINADA. La hipótesis de que la transacción abierta bloquee filas del Productor (patrón DBA-02, ultimo_acceso) y de que la sesión creada fuera no sea visible dentro sigue sin confirmar. La severidad ALTA se limita al impacto QA: no se puede evaluar la UI obligatoria ni otras UI con esta sesión dentro de un RUN. DBA: permitir que una sesión creada por refresh dentro del sandbox lea perfil y permisos, o impedir que el sandbox bloquee esas filas fuera del RUN; acreditar la corrección antes de reevaluar.

## Incidencias técnicas QA y hallazgo local

No hay incidencia de automatización abierta. El aislamiento de cabeceras del intento 2 quedó verificado por eco de las peticiones respondidas; las ausencias de respuesta se tratan como dependencia de sesión y no como prueba de un defecto del ejecutor.

**DEFECTO_FUNCIONAL_CANDIDATO, sin veredicto:** la lectura local de SGPMP-FRONT-END-PWA/src/telemetry/pages/MonitoreoView.tsx:159-160 y src/shared/i18n/locales/es-CO/telemetry.json:302 muestra el texto genérico "No hay sensores para mostrar con los filtros actuales", distinto del mensaje literal de la matriz. Solo una comprobación de la UI pública en TEST durante un RUN autorizado puede confirmar una discrepancia funcional. No se registra como incidencia de producto confirmada ni como RECHAZADO.

## Análisis de causas y efectos

La falla de sesión impidió observar la UI del caso. La correlación con el sandbox y la hipótesis de bloqueo de filas requieren comprobación DBA; los dos RUN no prueban la causa raíz. El hallazgo del texto de frontend procede solo de los archivos locales citados.

Los login y el refresh pueden dejar auditoría y rotación de sesión fuera del RUN; en el intento 2 también hubo lecturas de perfil y permisos fuera del sandbox. La escritura del escenario fue PUT de asignaciones dentro del sandbox. No se acreditó ausencia de efectos externos residuales ni reversión de login, auditoría o refresh. Sin sensores visibles, el código local del caso de uso no invoca el aviso E7; no se verificó por prueba externa que no hubiera otros efectos.

## Cierre y rollback de ambos RUN

| RUN | DELETE | Lectura pública posterior | Alcance acreditado |
|---|---|---|---|
| 041954 | HTTP 200 | Fincas originales [1,57,80,184] y posteriores [1,57,80,184] | Conjunto de asignaciones restituido |
| 043704 | HTTP 200 | Fincas originales [1,57,80,184] y posteriores [1,57,80,184] | Conjunto de asignaciones restituido |

El rollback de asignaciones del intento 2 está CONFIRMADO en su resultado.json por lectura pública posterior. La misma comprobación del intento 1 se transcribió antes de retirar su resultado.json. No se declara revertida la sesión, su auditoría ni otros efectos externos.

## Conclusión y acciones concretas

**TC-M03-G94: BLOQUEADO; informe consolidado no oficial.** API-185-01 y API-185-02 están aprobadas dos veces. UI-185-01 carece de veredicto y no permite aprobar TC-M03-185. DBA debe resolver INC-M03-184-G93-02 y aportar evidencia de lectura de perfil y permisos con sesión válida durante un RUN. Después, el responsable QA debe autorizar un único RUN de reevaluación de la UI, verificar el mensaje literal, el contacto al administrador, la ausencia de datos ajenos y error interno, y revisar cierre y efectos. El texto divergente observado en código local hace previsible un RECHAZADO, pero no se emite ese veredicto sin comprobación en TEST.
