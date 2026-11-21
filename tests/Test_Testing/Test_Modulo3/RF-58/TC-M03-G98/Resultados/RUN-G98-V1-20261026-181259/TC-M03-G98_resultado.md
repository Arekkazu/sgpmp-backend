# TC-M03-G98 — RECHAZADO

## Decisión del caso

TC-M03-191: **RECHAZADO**. Respuesta 200 sin panel de alertas activas (total + lista). RUN OFICIAL. Incidencia **INC-M03-191-G98-01**.

| Comprobación | Fuente | Estado | Evidencia |
| --- | --- | --- | --- |
| API-191-01 | API | RECHAZADO | newman/newman-G98.json |

## Identificación

Grupo G98; RF-58 / CU04; versión V1; RUN RUN-G98-V1-20261026-181259; ambiente TEST; autorización AUT-G98-V1-20261026; backend origin/test 5b46ca00a0ba92774f8e3d4b9eeaeec169344f17; frontend origin/test 81058af57d5d80d523fb5225f8eab48e0307ba85; Newman 6.2.2. UI no requerida; Cypress 0.

## Esperado y requisito

Matriz TC-M03-191: «HTTP 200. Se devuelve el total de alertas activas y la lista ordenada por severidad con CRITICO primero, indicando tipo de alerta, variable afectada y tiempo transcurrido, con navegación al detalle del activo biológico afectado.» Datos: «Alertas activas de severidad CRITICO, ALTA y MEDIA sobre distintos sensores de la misma unidad.» RF-58 Salida 2, Especificacion-Requerimientos-Modulo3.md:5400-5407: número total, lista ordenada (CRITICO primero), tipo, variable, tiempo y enlace. CA-11, línea 5531-5532: alertas ACTIVAS integradas, ordenadas y con acceso al activo. RF-57, línea 3785: «CRITICO > MODERADO > LEVE»; línea 4547: «severidad: LEVE | MODERADO | CRITICO». La matriz usa ALTA/MEDIA; ambas escalas se comprueban de forma explícita y no se mezclan.

## Observado por unidad

| Unidad | HTTP | Eco | Alertas detectadas | Campos raíz | Conteos por unidad | Severidades por sensor | Panel: ruta, campos, total, lista y severidades |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 200 | sí | sí | ["total","pagina","por_pagina","resumen_unidades","sensores","conteo_semaforo"] | [{"id_infraestructura":1,"alertas_activas_count":1}] | [null] | {"presente":false,"campos":["total","pagina","por_pagina","resumen_unidades","sensores","conteo_semaforo"],"candidatos":[{"ruta":"raiz","campos":["total","pagina","por_pagina","resumen_unidades","sensores","conteo_semaforo"]}]} |

Candidatas: 1, 268, 337, 3, 390, 2. Páginas 1/12; presupuesto: 15 GET dentro del RUN, 1 DELETE y 600 s. 

## Incidencias de producto

### INC-M03-191-G98-01 — El dashboard de monitoreo no incluye el panel de alertas activas exigido por RF-58 (total y lista ordenada por severidad)

- **ID:** INC-M03-191-G98-01. Caso TC-M03-191; discrepancia funcional **CONFIRMADA** por API en TEST, RUN oficial `RUN-G98-V1-20261026-181259` (`AUT-G98-V1-20261026`). La causa raíz permanece **NO DETERMINADA**; este ID identifica la incidencia en el informe, no un ticket definitivo.
- **Equipo:** Desarrollo. Primer contacto por la discrepancia comprobada en la API pública del dashboard y la ausencia del panel en el código de la pantalla de monitoreo; esta derivación no atribuye causa raíz.
- **Severidad:** **ALTA**. CA-11 es un criterio de aceptación de RF-58: el usuario no ve en el dashboard qué alertas están activas, su severidad ni el activo afectado, y debe acudir a la página separada de Alertas. La falta del panel bloquea esta funcionalidad relevante en el dashboard evaluado.
- **Requisito incumplido:** RF-58, `tests/Test_Testing/Requerimientos/Especificacion-Requerimientos-Modulo3.md:5400-5406`, Salida 2: «Panel de Alertas Activas Integrado», «Número total de alertas activas», «Lista de alertas ordenada por severidad (CRITICO primero)», «Tipo de alerta, variable afectada y tiempo transcurrido», «Enlace directo al detalle del activo biológico afectado». CA-11, mismo archivo `:5531-5532`: «Dado que existen alertas ACTIVAS en RF-57, cuando el usuario visualice el dashboard, entonces las alertas deben estar visibles e integradas en el panel, ordenadas por severidad con acceso directo al activo afectado.» El submódulo de Integración de Alertas debe «consumir y reflejar el estado de alertas activas provenientes de RF-57» (`:4924`). Matriz `tests/Test_Testing/Test_Modulo3/Casos_Prueba(Modulo3 Agrupado).csv:75`, TC-M03-191: «HTTP 200. Se devuelve el total de alertas activas y la lista ordenada por severidad con CRITICO primero, indicando tipo de alerta, variable afectada y tiempo transcurrido, con navegación al detalle del activo biológico afectado.»
- **Precondiciones:** Usuario Productor con acceso a la unidad productiva 1 (área 1), con al menos una alerta ACTIVA en RF-57. En este RUN, `resumen_unidades[0].alertas_activas_count = 1`.
- **Pasos para reproducir:** 1) Iniciar sesión como Productor. 2) Hacer `GET /iot/monitoreo/dashboard/1?pagina=1&por_pagina=50` con `X-Test-Run-Id` y comprobar su eco; alternativamente, abrir Telemetría > Monitoreo y seleccionar el área 1. 3) Revisar la respuesta o pantalla buscando el total y la lista de alertas activas. La alternativa UI describe la ruta funcional, pero no se ejecutó una comprobación UI en este RUN.
- **Resultado esperado:** HTTP 200 con una sección integrada de alertas activas: número total y lista ordenada por severidad (CRITICO primero). Cada elemento debe indicar tipo de alerta, variable afectada, tiempo transcurrido y enlace directo al detalle del activo biológico afectado.
- **Resultado obtenido:** `GET /iot/monitoreo/dashboard/1?pagina=1&por_pagina=50` devolvió HTTP 200 con eco del RUN. La respuesta tiene solo los campos raíz `total=4` (sensores), `pagina=1`, `por_pagina=50`, `resumen_unidades` (una unidad, `id_infraestructura=1`, `alertas_activas_count=1`, `estado_general=GRIS`), `sensores` (4) y `conteo_semaforo={GRIS:4}`. No hay campo con el total global de alertas activas ni lista de alertas; `total=4` cuenta sensores. Un sensor (`id_sensor=1`) trae `id_alerta=439` y `severidad_alerta=null`; los otros tres no tienen alerta. Esa referencia aislada no aporta severidad, tipo de alerta, variable afectada como dato de la alerta, tiempo transcurrido ni enlace al activo. La consulta de sensores del backend se ordena por `id_sensor`, no por severidad (`src/telemetry/infrastructure/repositories/monitoreo_repository.py:70-74`). Por lectura del código frontend de referencia, `MonitoreoView.tsx:143-179` representa KPI y tarjetas de unidades/sensores sin panel de alertas; `AlertasTable.tsx:26-55` se usa en la página separada `AlertasView.tsx:18,132`, enrutada en `TelemetryPage.tsx:32,63`. Esta observación de UI es inferencia de código, sin ejecución UI en TEST.
- **Evidencia:** `newman/newman-G98.json` (petición, respuesta y aserción saneadas), `resultado.json` (RUN, comprobación `API-191-01` y veredicto). Ambos están en este RUN oficial, autorizado como `AUT-G98-V1-20261026`.
- **Análisis (hipótesis no confirmada):** `DashboardResponseSchema` solo declara `total`, `pagina`, `por_pagina`, `resumen_unidades` y `sensores` (`src/telemetry/infrastructure/schema/monitoreo_schema.py:67-73`); el repositorio consulta la referencia individual a una alerta activa y ordena sensores por ID (`src/telemetry/infrastructure/repositories/monitoreo_repository.py:33-45,70-74`), sin construir una lista de alertas del dashboard. El código de `MonitoreoView.tsx:143-179` tampoco representa el panel. Esto orienta el análisis; no demuestra la causa raíz del despliegue evaluado.
- **Impacto:** Los usuarios del dashboard (Productor, Veterinario e Ingeniero) no pueden ver allí las alertas activas integradas y priorizadas. Deben consultar otra vista, lo que dificulta reaccionar ante condiciones críticas que RF-58 busca hacer visibles.
- **Qué se necesita para cerrarla:** Que la API del dashboard y la pantalla de Monitoreo expongan el panel descrito en Salida 2 y CA-11, con total, lista ordenada y acceso al activo; QA comprobará el caso en una reevaluación autorizada.

## Incidencias técnicas QA

Ninguna.

## Análisis de causas y observaciones

**Observación para Desarrollo (no es otra incidencia):** En la respuesta del RUN, el sensor con `id_alerta=439` tiene `severidad_alerta=null` aunque el resumen de la unidad informa una alerta activa. Conviene verificar si la severidad debería acompañar a `id_alerta`; esta relación por sí sola no acredita un segundo defecto.

**Observación documental:** La matriz TC-M03-191 menciona CRITICO/ALTA/MEDIA (`Casos_Prueba(Modulo3 Agrupado).csv:75`), mientras RF-57 usa «CRITICO > MODERADO > LEVE» y «severidad: LEVE | MODERADO | CRITICO» (`tests/Test_Testing/Requerimientos/Especificacion-Requerimientos-Modulo3.md:3785,4547`). QA debe aclarar la escala aplicable sin cambiar el esperado literal del caso.

## Evidencias y efectos

preflight.json, newman/newman-G98.json, newman/newman-G98.html, resultado.json, TC-M03-G98_resultado.md. Login Productor previo al RUN puede registrar último acceso, auditoría, notificaciones y cierre de sesiones. Las lecturas del dashboard pueden generar correo RF-58 E7 por sensores GRIS sin umbral no desactualizados. Sin escrituras de escenario.

## Cierre y rollback

DELETE RUN HTTP 200. Rollback verificado: Bitácora: 4 GET con eco, ninguna escritura de escenario; DELETE 200. No se afirma reversión de efectos externos.

## Conclusión y acción

RECHAZADO: Respuesta 200 sin panel de alertas activas (total + lista). Derivar a Desarrollo con la respuesta pública saneada.
