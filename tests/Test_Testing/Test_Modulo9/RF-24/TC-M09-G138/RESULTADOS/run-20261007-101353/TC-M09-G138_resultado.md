# TC-M09-G138 — Resultado

**Resultado general: RECHAZADO.** RUN_ID: run-20261007-101353. Ambiente decisorio: TEST. Prueba local: NO.

## Decisión general

| Caso | Precondición negativa | Resultado | Motivo |
|---|---|---|---|
| TC-M09-278 | Área sin cámara | RECHAZADO | VISION no está publicada en TEST. |
| TC-M09-279 | Única cámara inactiva | RECHAZADO | VISION no está publicada en TEST. |
| TC-M09-280 | Paradigma INDIVIDUAL | RECHAZADO | VISION no está publicada en TEST. |
| TC-M09-281 | Sin `tipo_modelo_asignado` | RECHAZADO | VISION no está publicada en TEST. |

## OpenAPI VISION

Newman consultó `GET https://api.inmero.co/back-sigab-test/openapi.json` y obtuvo HTTP 200, con sus dos assertions correctas. Se revisaron 210 rutas, 77 POST y 305 esquemas. No se publicó ninguna operación VISION: método, ruta, body, respuestas y seguridad VISION figuran ausentes.

La única calibración publicada es `POST /configuracion/sensores/{id_sensor}/calibrar`, identificada en el contrato como **Flujo D SENSOR**. `RegistrarCalibracionDTO` requiere dispositivo, infraestructura y fecha; no declara `modo_calibracion`, `area_id` ni `ventana_observacion`. Tampoco aparece `VISION` como término exacto en el OpenAPI. Aceptar campos extras en ese endpoint no demuestra una operación de Flujo F.

Hash SHA-256 del OpenAPI consultado: `3c5399809538cc403904725612dc20072bbc2c964eb10c8ad7f802731d21eed8`. La búsqueda estructurada y los campos del DTO SENSOR se encuentran en `evidencia.json`.

## Fixtures y fuente de discovery

No se crearon A2, A3, A4, A5 ni cámaras. El preflight de operación es anterior a cualquier setup; al fallar, crear esos fixtures solo modificaría TEST sin permitir probar VISION. Los IDs, el conteo de cámaras y los snapshots de línea base se registran como **no aplicables/no evaluados**, nunca como cero medido.

## Fuente formal del paradigma TC-280

No se consultó RFC-009 ni se clasificó MODELO_ESPECIES_GRANDES. El caso ya tiene una causa de rechazo anterior y concluyente: la operación VISION falta en TEST. Esta decisión no equivale a afirmar que el paradigma esté confirmado o que haya un defecto documental.

## Resultado por caso

### TC-M09-278 — RECHAZADO

**Escenario que debía probarse.** A2 activa, especie AVES y modelo MODELO_AVES, sin cámaras asociadas. El Ingeniero debía recibir HTTP 422 y el mensaje VISION exacto con el ID de esa área; no debía aparecer una nueva línea base.

**Qué ocurrió en TEST.** Sin una operación VISION publicada no se puede enviar la ventana de observación para A2 ni comprobar que la falta de cámara produzca el 422 específico. No se preparó el área ni se envió POST. Por ello HTTP, mensaje y línea base PRE/POST son **no observables**, no un 422 fallido medido.

**Por qué se rechaza.** La matriz de G138 considera la ausencia de la operación VISION un incumplimiento ejecutable para este caso. El defecto comprobado es que TEST no expone la funcionalidad necesaria para aplicar la regla; el comportamiento interno de esa regla aún no se ha evaluado.

### TC-M09-279 — RECHAZADO

**Escenario que debía probarse.** A3 activa con una única cámara C3 asociada e inactiva. El Ingeniero debía recibir HTTP 422 y el mensaje VISION exacto con el ID de esa área; no debía aparecer una nueva línea base.

**Qué ocurrió en TEST.** No se creó ni desactivó C3: el caso no tiene un endpoint VISION donde comprobar que una cámara inactiva provoca el 422 contractual. No se preparó el área ni se envió POST. Por ello HTTP, mensaje y línea base PRE/POST son **no observables**, no un 422 fallido medido.

**Por qué se rechaza.** La matriz de G138 considera la ausencia de la operación VISION un incumplimiento ejecutable para este caso. El defecto comprobado es que TEST no expone la funcionalidad necesaria para aplicar la regla; el comportamiento interno de esa regla aún no se ha evaluado.

### TC-M09-280 — RECHAZADO

**Escenario que debía probarse.** A4 con cámara activa y paradigma INDIVIDUAL formalmente confirmado. El Ingeniero debía recibir HTTP 422 y el mensaje VISION exacto con el ID de esa área; no debía aparecer una nueva línea base.

**Qué ocurrió en TEST.** La ausencia de VISION impide la prueba antes de resolver el mapeo formal de MODELO_ESPECIES_GRANDES a INDIVIDUAL. No se atribuye un fallo adicional al paradigma ni a RFC-009. No se preparó el área ni se envió POST. Por ello HTTP, mensaje y línea base PRE/POST son **no observables**, no un 422 fallido medido.

**Por qué se rechaza.** La matriz de G138 considera la ausencia de la operación VISION un incumplimiento ejecutable para este caso. El defecto comprobado es que TEST no expone la funcionalidad necesaria para aplicar la regla; el comportamiento interno de esa regla aún no se ha evaluado.

### TC-M09-281 — RECHAZADO

**Escenario que debía probarse.** A5 activa, especie AVES, cámara activa y tipo_modelo_asignado=null. El Ingeniero debía recibir HTTP 422 y el mensaje VISION exacto con el ID de esa área; no debía aparecer una nueva línea base.

**Qué ocurrió en TEST.** Sin el request VISION no puede comprobarse que la falta de modelo asignado origine el 422 ni que la línea base permanezca igual. No se preparó el área ni se envió POST. Por ello HTTP, mensaje y línea base PRE/POST son **no observables**, no un 422 fallido medido.

**Por qué se rechaza.** La matriz de G138 considera la ausencia de la operación VISION un incumplimiento ejecutable para este caso. El defecto comprobado es que TEST no expone la funcionalidad necesaria para aplicar la regla; el comportamiento interno de esa regla aún no se ha evaluado.

## Ejecución y trazabilidad

- Rama: `qa/juan-esteban-rf24-v2`; HEAD: `30ddd72144102a60af006b265a20cb18c1c72c85`; origin/test: `30ddd72144102a60af006b265a20cb18c1c72c85`; divergencia: `0	0`.
- Git previo: carpetas QA sin seguimiento; detalle en evidencia.json; diff de archivos seguidos: vacío; staged: vacío.
- POST VISION planificados tras el preflight: 0; ejecutados: 0. POST/PATCH de setup: 0. STOP_ALL: NO (no hubo intento funcional). SQL: ninguno. No se utilizó actor funcional ni Administrador.

## Incidencias

**INCIDENCIA REQUERIDA: SÍ.** Se consolida una sola incidencia porque los cuatro casos comparten la misma causa observable: TEST no publica la operación RF-24 VISION.

- **Grupo responsable:** Desarrollo. **Grupo de prueba:** TC-M09-G138. **Casos afectados:** TC-M09-278, TC-M09-279, TC-M09-280 y TC-M09-281. **Resultado:** RECHAZADO.
- **Motivo:** no es posible ejecutar las cuatro validaciones obligatorias de VISION ni obtener sus respuestas contractuales.
- **Esperado:** operación VISION publicada; cada fixture válido salvo una precondición negativa debe obtener HTTP 422, mensaje exacto con su ID de área y ninguna línea base nueva.
- **Obtenido:** operación VISION ausente en 210 rutas y 305 esquemas de OpenAPI TEST. El único POST de calibración publicado es SENSOR Flujo D.
- **Causa raíz observable:** contrato VISION no expuesto en TEST. La API no permite distinguir si la lógica aún no está implementada o si está pendiente su despliegue; Desarrollo debe investigar ese punto. No hay evidencia para atribuir el fallo a AIoT o DBA.
- **Type:** bug. **Severity:** Important. **Priority:** High. **Evidencia:** `evidencia.json` y `newman.html`.

## Conclusión

Los cuatro casos y G138 quedan **RECHAZADOS** por la regla explícita del paquete para una operación VISION no publicada. No se midió un 422 incorrecto ni se afirmó que un fixture o la línea base fallara: esas comprobaciones requieren primero la operación VISION en TEST.
