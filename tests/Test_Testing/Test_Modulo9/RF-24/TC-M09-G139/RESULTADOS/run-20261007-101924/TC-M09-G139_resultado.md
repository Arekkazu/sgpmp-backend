# TC-M09-G139 — Resultado

**Resultado general: BLOQUEADO / NO VERIFICABLE.** RUN_ID: run-20261007-101924. Ambiente decisorio: TEST. Prueba local: NO.

## Decisión general

| Caso | Condición | Resultado | Motivo |
|---|---|---|---|
| TC-M09-282 | 0 observaciones VISION aptas | BLOQUEADO / NO VERIFICABLE | Sin operación VISION no se puede montar ni ejecutar la ventana de 0 aptas. |
| TC-M09-283, corrida N | Exactamente N aptas | BLOQUEADO / NO VERIFICABLE | Sin operación VISION no se ejecuta el umbral ni se conoce BASELINE_N. |
| TC-M09-283, corrida N−1 | Exactamente N−1 aptas | BLOQUEADO / NO VERIFICABLE | Depende de N y de BASELINE_N; ninguna precondición llegó a ejecutarse. |

## Ejecutabilidad VISION/M03

Newman consultó `GET https://api.inmero.co/back-sigab-test/openapi.json` y terminó con código 0. Un segundo GET en TEST devolvió HTTP 200; Pytest confirmó que el hash del OpenAPI permaneció igual entre consultas. Se revisaron 210 rutas, 77 POST y 305 esquemas. No hay operación formal VISION, ni `modo_calibracion` o `ventana_observacion` en el contrato.

La única calibración publicada es `POST /configuracion/sensores/{id_sensor}/calibrar`, identificada como Flujo D SENSOR. Su `RegistrarCalibracionDTO` recibe dispositivo, infraestructura, valor y fecha; no define área y ventana VISION. Enviar campos extras a esa ruta no demostraría el proceso del Flujo F.

**Operación VISION publicada:** NO. Método/ruta/body/respuestas/security: no publicados. Hash SHA-256 de OpenAPI: `3c5399809538cc403904725612dc20072bbc2c964eb10c8ad7f802731d21eed8`.

La fase 1 bloqueó las demás. La fuente formal de observaciones VISION, el vínculo cámara–observación, el flag de aptitud propio del proceso, N y la superficie de línea base figuran **NO EVALUADOS**. Esto no significa que se haya demostrado su ausencia: no se consultaron M03 ni BD después del bloqueo. La telemetría común no se trató como vector VISION.

## Fixture

No se prepararon A1/C1 ni ventanas. No hay IDs de observaciones, conteos ni snapshots PRE/POST. El valor de N no se leyó ni se supuso. No se ejecutó SQL ni se cambiaron flags o líneas base.

## TC-M09-282 — cero observaciones aptas

**Escenario esperado.** Con A1/C1 válidas y una ventana cerrada cuya cantidad de observaciones VISION aptas sea exactamente 0, el Ingeniero debe recibir HTTP 422. No debe aparecer una línea base nueva y la vigente previa debe permanecer intacta. Este caso no exige un mensaje literal único porque pueden aplicar dos rutas de rechazo.

**Qué se pudo observar.** No existe una operación VISION publicada para enviar la ventana. Por eso el conteo de 0 aptas no fue medido, el POST no se envió y tampoco se pudo comparar la línea base PRE/POST. `HTTP obtenido` y `baseline conservada` quedan **no observables**, no se registran falsamente como 422 y SÍ.

**Decisión: BLOQUEADO / NO VERIFICABLE.** Falta la primera precondición de ejecutabilidad; no hay evidencia de que la regla de 0 aptas funcione o falle.

## TC-M09-283 — límite N y N−1

### Corrida N

**Escenario esperado.** Leer N desde una configuración real, construir una ventana con exactamente N observaciones VISION aptas y obtener 2xx y una BASELINE_N nueva y vigente. Una cantidad mayor a N no probaría el límite exacto.

**Qué se pudo observar.** Sin operación VISION no se llegó a descubrir una fuente formal de vectores ni N, y no se preparó la ventana. La corrida N no se ejecutó. HTTP y BASELINE_N son **no observables**.

### Corrida N−1

**Escenario esperado.** En otra ventana cerrada y no solapada, exactamente N−1 aptas deben producir 422 y el mensaje contractual de datos insuficientes. Debe existir auditoría FALLIDA y BASELINE_N debe seguir vigente sin cambios.

**Qué se pudo observar.** La corrida N−1 depende de BASELINE_N creada por la corrida N. Como esa primera corrida no fue posible, tampoco se ejecutó la segunda; no se consultó auditoría de un intento que no existió. HTTP, mensaje, auditoría y persistencia son **no observables**.

**Decisión TC-M09-283: BLOQUEADO / NO VERIFICABLE.** Faltan operación VISION y, por la puerta del preflight, no se pudieron montar N, N−1 ni verificar las dos respuestas. No se afirma que N no exista en el sistema; simplemente no se alcanzó su descubrimiento.

## Ejecución y trazabilidad

- Rama: `qa/juan-esteban-rf24-v2`; HEAD: `30ddd72144102a60af006b265a20cb18c1c72c85`; origin/test: `30ddd72144102a60af006b265a20cb18c1c72c85`; divergencia: `0	0`.
- Estado Git previo y detalle de búsqueda contractual: `evidencia.json`.
- POST VISION planificados tras preflight: 0; ejecutados: 0. POST de setup: 0. STOP_ALL: NO (no hubo escritura). SQL: ninguno.
- `newman.html` contiene el GET real y sus assertions. `pytest.xml` registra la comprobación independiente de estabilidad del contrato. Ninguno ejecuta el oráculo funcional bloqueado.

## Incidencias

**INCIDENCIA REQUERIDA: NO, con la evidencia disponible.** Los dos casos están bloqueados antes de alcanzar su oráculo, y la matriz prevé el bloqueo hasta que se publiquen las dependencias VISION/M03. No se dispone de confirmación de que esa entrega ya fuera obligatoria en TEST; por eso no se registra un bug de Desarrollo ni de AIoT solo a partir de este preflight.

Grupo: TC-M09-G139. Casos: TC-M09-282 y TC-M09-283. Resultado: BLOQUEADO / NO VERIFICABLE. Esperado: operación VISION y fuente formal de observaciones, N y baseline para probar 0, N y N−1. Obtenido: VISION no publicada; las fases siguientes no evaluadas. Grupo responsable de una eventual incidencia: Por determinar hasta confirmar el estado formal de entrega. Type/Severity/Priority: no aplican a una incidencia no abierta. Evidencia: `evidencia.json`, `newman.html` y `pytest.xml`.

## Conclusión

G139 permanece **BLOQUEADO / NO VERIFICABLE**. La ausencia de contrato VISION impidió alcanzar ambos oráculos. Una vez publicada la operación, habrá que demostrar la fuente formal de vectores, N y la línea base antes de enviar cualquiera de los tres POST previstos para la ejecución completa.
