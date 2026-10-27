# TC-M03-G93 — RECHAZADO (API: unidad sin sensores ausente del resumen; UI pendiente de DBA)

**Estado: CERRADO documentalmente.** El caso está RECHAZADO funcionalmente por API: en tres RUN autorizados una unidad recién creada sin sensores no figuró en resumen_unidades. La UI queda BLOQUEADA para el cierre por INC-M03-184-G93-02 (sesión del sandbox). El [informe consolidado del último RUN](Resultados/RUN-G93-V1-20261026-014819/TC-M03-G93_resultado.md) contiene las incidencias INC-M03-184-G93-01 para Desarrollo e INC-M03-184-G93-02 para DBA, su evidencia, las limitaciones y el historial transcrito. El RUN es **no oficial**; su resultado.json permanece intacto.

La fuente del oráculo es la fila TC-M03-G93 de Casos_Prueba(Modulo3 Agrupado).csv: «La unidad se muestra con estado GRIS y el mensaje "Sin datos disponibles", junto con la fecha del último dato histórico si existe; la unidad no desaparece del panel y no se devuelven errores 5xx ni valores fabricados». Se exige API y UI. QA considera equivalentes «Sin datos»/«Sin datos disponibles», admite INACTIVO como ausencia de señal para V2 y exige fecha histórica solo si existe.

## Estructura vigente

- g93.mjs: ejecutor canónico y contrato de operaciones.
- G93.postman_collection.json: colección Newman única.
- g93.cy.js y g93.cypress.config.cjs: spec y configuración Cypress únicos.
- lib/: lógica y resguardos compartidos del ejecutor.
- pruebas/: regresiones y ensayos locales de la automatización; sus datos son sintéticos y sus artefactos se crean en el directorio temporal del sistema.
- Resultados/RUN-G93-V1-20261026-014819/: único RUN conservado, con un solo Markdown oficial, resultado.json, preflight.json, contexto_operacion.json, reportes Newman y acta/captura Cypress reales.

La operación diagnostico sigue en el ejecutor para futuros usos expresamente autorizados y escribiría una carpeta diagnostico/ nueva. Ningún diagnóstico histórico ni RUN anterior es dependencia de las pruebas vigentes. No invocar diagnostico durante este cierre.

## Historial resumido

| Registro | Hecho |
|---|---|
| Intento 1, 20261025-150037 | Aborto local por carga de entorno; sin peticiones de negocio. |
| Intento 2, 20261025-154913 | Área 514 ausente del resumen, API-184-01/02 RECHAZADO; UI ERROR_QA; rollback confirmado. |
| Diagnóstico 20261025-173337 | Áreas 1/2/3 con sensores INACTIVO; 268/337 ACTIVO; 349/390/389/399 sin resumen. |
| Intento 3, 20261025-182304 | Área 515 ausente, API-184-01/02 RECHAZADO; área 1 API-184-03 APROBADO; UI ERROR_QA; rollback confirmado. |
| Intento 4, 20261025-221324 | Preflight Newman agotó plazo de 5 s; sin peticiones de negocio. |
| Intento 5, 20261025-222242 | Timeout transitorio de login; sin peticiones de negocio. |
| Diagnóstico 20261026-013518 | Login de Administrador y Productor HTTP 200 fuera del sandbox. |
| Intento 6, 20261026-014819 | Área 519 ausente, API-184-01/02 RECHAZADO; UI V1 NO_CONCLUYENTE por sesión, V2 no ejecutada; rollback confirmado. |

## Validación e invocaciones vigentes

Desde esta carpeta, las consultas locales sin TEST son:

- node g93.mjs --capacidades
- node g93.mjs --comprobar
- node pruebas/g93.test.mjs
- node pruebas/g93_ensayo_spec_real.mjs (ensayo local del spec con servidor loopback y temporales del sistema; requiere Cypress/Chrome operativos).

La ejecución sobre TEST corresponde exclusivamente al lanzador externo con autorización humana específica. El contrato del ejecutor usa g93.mjs --operacion reintentar --version 1 --intento N --run-id RUN-G93-V1-AAAAMMDD-HHMMSS --autorizacion REF --contexto RUTA_ABSOLUTA_AL_CONTEXTO. Esta línea documenta el contrato; no autoriza ejecutarla. V2 requiere decisión explícita de reevaluación y su propia estructura EvaluacionV2/Resultados/.

## Condiciones para reevaluar

Atender INC-M03-184-G93-01 y resolver la dependencia de sesión de DBA-01/INC-M03-184-G93-02. Corregir y validar localmente la secuencia para ejecutar toda la API V1 y V2 antes de Cypress; en el último RUN, el refresh de la UI de V1 dejó inválido el token previo del ejecutor para preparar V2. Tras autorización humana específica, repetir API y UI públicas, conservar evidencias reales bajo el nuevo RUN y verificar cierre y rollback con alcance explícito.
