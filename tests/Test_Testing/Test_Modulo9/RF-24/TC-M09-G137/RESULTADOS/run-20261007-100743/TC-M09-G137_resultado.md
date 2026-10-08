# TC-M09-G137 — Resultado

**Resultado general: RECHAZADO.** RUN_ID: run-20261007-100743. Ambiente decisorio: TEST. Prueba local: NO.

## Decisión general

| Caso | Resultado | Motivo principal |
|---|---|---|
| TC-M09-275 | BLOQUEADO / NO VERIFICABLE | No hay operación VISION para el disparo manual del Ingeniero. |
| TC-M09-276 | BLOQUEADO / NO VERIFICABLE | No hay operación VISION para el disparo manual del Administrador. |
| TC-M09-277 | RECHAZADO | No existe la operación VISION sobre la cual exigir el 403 contractual al Productor. |

## Preflight VISION

Newman consultó **GET https://api.inmero.co/back-sigab-test/openapi.json** y recibió HTTP 200. El documento contiene 210 rutas, 77 operaciones POST y 305 esquemas. La revisión de rutas, descripciones y cuerpos no identificó una operación RF-24 VISION.

La única operación de calibración publicada es `POST /configuracion/sensores/{id_sensor}/calibrar`, descrita como **Flujo D: calibración de sensor**. Su body `RegistrarCalibracionDTO` declara `id_dispositivo_iot`, `id_infraestructura`, `valor_referencia`, `ganancia`, `offset`, `fecha_calibracion` y `observaciones`. No declara `modo_calibracion`, `area_id` ni `ventana_observacion`. En todo el OpenAPI hay cero apariciones exactas de `VISION`, `modo_calibracion`, `ventana_observacion` y `origen_disparo`. Por ello ese POST SENSOR no demuestra el Flujo F.

**Operación VISION encontrada:** NO. **Método/ruta:** no publicados. **Schema/respuestas/security VISION:** no publicados. Hash SHA-256 del OpenAPI consultado: `3c5399809538cc403904725612dc20072bbc2c964eb10c8ad7f802731d21eed8`.

El preflight termina aquí conforme al orden del paquete. Persistencia de línea base, dependencias M03, área/especie/modelo/cámara y volumen mínimo: **no evaluados**. No se infiere que esas dependencias falten; su verificación solo tendría sentido después de identificar la operación VISION. No se hicieron consultas SQL, Pytest, login de actores ni preparación de Productor.

## TC-M09-275 — Ingeniero de Campo

**Escenario esperado.** El Ingeniero dispara manualmente VISION con un área y una ventana válida. Tras un 2xx, debe quedar una línea base nueva, vigente, de origen MANUAL y atribuida a él, además de una auditoría exitosa.

**Qué se pudo comprobar.** TEST no publica método, ruta ni body VISION. Por eso no hay un request contractual que permita iniciar el caso. No se envió POST y no se buscó una línea base que este RUN no podía crear.

**Decisión: BLOQUEADO / NO VERIFICABLE.** Es un bloqueo de precondición: no se alcanzó el flujo positivo. No se afirma que la persistencia, M03 o la auditoría hayan fallado; quedaron sin evaluar por la ausencia anterior.

## TC-M09-276 — Administrador

**Escenario esperado.** El Administrador repite la misma calibración VISION válida y debe generar otra línea base manual, vigente y atribuida a su usuario, diferenciable de la del Ingeniero.

**Qué se pudo comprobar.** La misma ausencia de contrato VISION impide construir su POST. Ejecutar el endpoint SENSOR cambiaría la operación bajo prueba. No se utilizó la cuenta Administrador para una escritura ni se preparó un fixture.

**Decisión: BLOQUEADO / NO VERIFICABLE.** Falta la operación VISION publicada; la sustitución de línea base y el usuario responsable no son verificables todavía.

## TC-M09-277 — Productor

**Escenario esperado.** Un Productor activo envía un request VISION estructuralmente válido y recibe HTTP 403 con el mensaje exacto: “Acceso denegado: La calibración de sensores es una función crítica restringida exclusivamente al Ingeniero de Campo o al Administrador.” No debe existir efecto funcional.

**Qué se obtuvo.** TEST no publica una operación VISION ni el schema necesario para construir ese request. En consecuencia no hay un endpoint VISION que pueda responder 403 o el mensaje contractual. No se envió POST; el HTTP obtenido y el mensaje son **no observables**, y no se realizó login del Productor porque el preflight se detuvo antes de usar cualquier actor.

**Decisión: RECHAZADO.** La matriz de G137 califica expresamente como rechazo la ausencia de la operación VISION para este caso de seguridad. La evidencia demuestra falta de exposición del control contractual; no demuestra cómo se comportaría un endpoint VISION si llegara a publicarse.

## Ejecución y trazabilidad

- Rama: `qa/juan-esteban-rf24-v2`; HEAD: `30ddd72144102a60af006b265a20cb18c1c72c85`; origin/test: `30ddd72144102a60af006b265a20cb18c1c72c85`; divergencia: `0	0`.
- Estado Git previo: hay carpetas QA sin seguimiento de grupos anteriores y G137; detalle en evidencia.json. Diff de archivos seguidos: vacío; staged: vacío.
- POST VISION planificados: 0 tras el preflight; ejecutados: 0. POST de setup: 0. SELECT/SQL: ninguno. No hubo cambios de cuenta ni de BD.

## Incidencias

**INCIDENCIA REQUERIDA: SÍ.** Una incidencia para la causa compartida: la operación RF-24 VISION no está publicada en el contrato de TEST. Afecta a los tres casos, con distinto resultado por el oráculo de cada uno.

- **Casos:** TC-M09-275, TC-M09-276, TC-M09-277. **Grupo responsable:** Desarrollo. **Grupo de prueba:** TC-M09-G137.
- **Motivo:** TC-275 y TC-276 no pueden iniciar la calibración manual; TC-277 no puede observar el 403 y el mensaje exigidos a un Productor en la operación VISION.
- **Esperado:** operación VISION publicada, con body para área y ventana; disparos positivos 2xx y control Productor 403 con texto exacto.
- **Obtenido:** solo POST de calibración SENSOR Flujo D; ningún método/ruta/body VISION en 210 rutas, 77 POST y 305 esquemas del OpenAPI de TEST.
- **Causa raíz observable:** falta de exposición del contrato RF-24 VISION en TEST. Con la API sola no se distingue si falta implementación o despliegue; Desarrollo debe determinar ese mecanismo.
- **Type:** bug. **Severity:** Important. **Priority:** High. **Evidencia:** `evidencia.json` (resumen y hash OpenAPI), `newman.html` (GET contractual).

## Conclusión

G137 queda **RECHAZADO** porque TC-277 tiene un incumplimiento concluyente según la matriz. TC-275 y TC-276 permanecen **BLOQUEADOS / NO VERIFICABLES**. El siguiente paso del producto es publicar el contrato VISION en TEST; solo entonces podrán prepararse y evaluarse las dependencias M03, la línea base y los tres POST reales.
