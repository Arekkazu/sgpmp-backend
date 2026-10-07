# TC-M09-G142 — Resultado

**Resultado general: BLOQUEADO / NO VERIFICABLE.** RUN_ID: run-20261007-103146. Ambiente: TEST; prueba local: NO.

## Decisión general

| Caso | Evento M02 previsto | Resultado | Motivo |
|---|---|---|---|
| TC-M09-288 | Alta de lote poblacional | BLOQUEADO / NO VERIFICABLE | No se identificó una fuente formal de observaciones VISION ni una línea base verificable. |
| TC-M09-289 | Cierre de ciclo | BLOQUEADO / NO VERIFICABLE | La misma dependencia VISION falta; no se cerró un lote sin poder observar el efecto automático. |

## Ejecutabilidad VISION/M03

Newman consultó `GET https://api.inmero.co/back-sigab-test/openapi.json` y verificó los cuatro contratos necesarios: POST de alta M02, POST de cierre M02, GET de detalle y GET de auditoría. El OpenAPI respondió HTTP 200; Pytest confirmó que el contrato no cambió durante el preflight. TEST publica 210 rutas y 305 esquemas.

La ausencia de un endpoint **manual** VISION se registra solo como contexto: un disparo M02→M09 podría ser interno. Por eso la decisión se apoya en las precondiciones de datos y verificación, no en esa ausencia aislada.

En la conexión `member_qa` a `sgpmp_test`, `transaction_read_only=on`, se ejecutaron únicamente cuatro SELECT de catálogo. En `modulo3` se observaron `telemetrias`, `telemetria_calidad`, `eventos_edge_computing` y `paquetes_inferencia`; las dos primeras incluyen `apto_para_ia`, pero ninguna de esas estructuras expone una relación formal de vector de comportamiento VISION con cámara, área, ventana y aptitud. El contrato API tampoco publica un recurso de vectores VISION.

La búsqueda de tablas/vistas y columnas semánticas no identificó una persistencia de línea base VISION en M09. `modulo9.calibraciones` tiene campos de calibración SENSOR (`id_sensor`, `valor_referencia`, `id_usuario`) y no los campos de área/especie, origen automático, usuario nullable y vigencia exigidos para esta prueba. `modulo1.integridad_baseline` pertenece a RF-10 y no es la baseline VISION. Los nombres/columnas examinados y los SELECT exactos figuran en `evidencia.json`.

**Conclusión de precondiciones:** no se encontró una fuente formal consultable que permita demostrar observaciones VISION aptas `>= N` ni una superficie para validar la baseline automática. No se inventó N: su fuente y valor quedan **no evaluados** porque falta antes la semántica de los vectores. Tampoco se evaluaron A1, especie y C1, que no resolverían esta dependencia global.

## TC-M09-288 — nuevo lote

**Escenario esperado.** Admin registra en A1 un lote POBLACIONAL de especie AVES. Sin llamar manualmente a VISION, la integración debería publicar una baseline para (A1, especie) con `origen_disparo=AUTOMATICO`, `usuario_id=null`, `vigente=true` y auditoría M09 EXITOSO. El usuario Admin del alta no debe atribuirse como autor del cálculo automático.

**Qué se observó.** La ruta y el DTO de alta M02 sí están publicados. Sin embargo, antes de crear un lote no fue posible demostrar la fuente formal de vectores VISION, el umbral N ni dónde consultar la baseline resultante. No se envió POST `/activos-biologicos`: `id_activo`, timestamp del evento, señal de trigger, baseline y auditoría M09 son **no observables**, no fallos medidos. No existe un tiempo transcurrido que reportar.

**Decisión: BLOQUEADO / NO VERIFICABLE.** Falta la precondición que permitiría alcanzar y evaluar la cadena automática. No se concluye que M02 haya omitido el disparo o que M09 haya fallado, porque el evento M02 nunca se produjo en este RUN.

## TC-M09-289 — fin de ciclo

**Escenario esperado.** Admin cierra un lote QA activo y cerrable de A1. El cierre M02 debe provocar un nuevo cálculo automático del mismo par, con origen AUTOMATICO, usuario nulo, baseline vigente y auditoría M09 EXITOSO; no se debe ejecutar VISION manualmente.

**Qué se observó.** El POST de cierre está publicado, pero la misma fuente formal VISION y la verificación de baseline faltan. Además, no se preparó ni se cerró un lote: no se evaluaron sus fases, sensores o fecha de cierre, porque hacerlo ahora produciría un evento irreversible sin un oráculo M09 verificable. HTTP del cierre, señal de trigger, baseline posterior y auditoría son **no observables**.

**Decisión: BLOQUEADO / NO VERIFICABLE.** No se confunde la falta de precondición con un defecto de integración. Tampoco se deduce nada de un timeout: no hubo evento y RF-24 no fija un SLA para el procesamiento automático.

## Ejecución y trazabilidad

- Rama: `qa/juan-esteban-rf24-v2`; HEAD: `30ddd72144102a60af006b265a20cb18c1c72c85`; origin/test: `30ddd72144102a60af006b265a20cb18c1c72c85`; divergencia: `0	0`. Estado Git previo completo en `evidencia.json`.
- POST alta M02: 0; POST cierre M02: 0; POST manual VISION: 0; setup: 0. STOP_ALL: NO. SQL: únicamente los SELECT indicados en la evidencia, en sesión read-only.
- `newman.html` contiene el GET real y sus assertions. `pytest.xml` registra la segunda lectura del contrato y del esquema TEST. Ninguno ejecuta el oráculo funcional bloqueado.

## Incidencias

**INCIDENCIA REQUERIDA: SÍ, de aclaración de dependencia; no se declara bug de integración.** La evidencia de API y esquema no identifica una fuente formal de observaciones VISION ni una superficie verificable de baseline. Se requiere que el proyecto identifique el contrato/pipeline y la configuración N que habilitarían el RUN, o confirme que aún no están entregados.

- **Grupo responsable:** Por determinar. **Componente a aclarar:** M03 (vector/cámara), M09 (baseline) e integración con M02. **Grupo de prueba:** TC-M09-G142. **Casos afectados:** TC-M09-288 y TC-M09-289. **Resultado:** BLOQUEADO / NO VERIFICABLE.
- **Esperado:** fuente formal de vectores VISION aptos vinculados a C1/A1, mínimo N, baseline VISION consultable; luego eventos M02 y auditoría M09 automática.
- **Obtenido:** rutas M02 disponibles, pero ninguna estructura/API formal identificada que permita montar `>= N` observaciones VISION ni verificar la baseline. No se ejecutaron los disparadores M02.
- **Causa raíz:** por determinar: contrato de M03/M09 no publicado, implementación pendiente o despliegue/documentación no accesible. La inspección de esquema por sí sola no distingue esas posibilidades.
- **Type:** question. **Severity:** Normal. **Priority:** Normal. **Evidencia:** `evidencia.json`, `newman.html`, `pytest.xml`. Si se confirma una entrega obligatoria ausente, reclasificar con evidencia al componente responsable.

## Conclusión

G142 queda **BLOQUEADO / NO VERIFICABLE**. Las rutas M02 están desplegadas, pero TEST no permite demostrar las precondiciones y la superficie de verificación de VISION automática. No se registró ni cerró un lote y no se adjudicó a M02/M09 un fallo de disparo no observado.
