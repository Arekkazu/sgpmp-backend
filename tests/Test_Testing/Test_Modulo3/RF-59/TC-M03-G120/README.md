# [TC-M03-G120 — APROBADO (RUN oficial RUN-G120-V1-20261026-233328)](Resultados/RUN-G120-V1-20261026-233328/TC-M03-G120_resultado.md)

## Estado e historial breve

Casos TC-M03-241/242/243: **APROBADO** en el intento 6, RUN oficial `RUN-G120-V1-20261026-233328`. El [informe oficial](Resultados/RUN-G120-V1-20261026-233328/TC-M03-G120_resultado.md) conserva el detalle transcrito de los cinco intentos técnicos eliminados por decisión del responsable QA el 2026-10-26.

| Intento | RUN V1 (2026-10-26) | Síntesis |
| --- | --- | --- |
| 1 | `221656` | BLOQUEADO por filtros de semilla; 0 escrituras. |
| 2 | `222558` | NO_CONCLUYENTE; búsqueda acotada a 12 dispositivos sin sensores. |
| 3 | `223634` | NO_CONCLUYENTE; semilla sin lecturas recientes y timeout de unidad. |
| 4 | `225306` | Veredictos inválidos: todas las lecturas rechazadas por el formato de variable probable; contraste 404. |
| 5 | `231619` | 242/243 APROBADO; 241 NO_CONCLUYENTE por `ERROR_TIEMPO` en contraste. |
| 6 | `233328` | 241/242/243 APROBADO; único RUN conservado. |

Estructura vigente: `README.md`, `g120.mjs` (ejecutor canónico), `G120.postman_collection.json` (colección vigente), `lib/` (módulos y presupuesto), `pruebas/` (regresiones y ensayo local), `Resultados/RUN-G120-V1-20261026-233328/` (informe, JSON de resultado/preflight/contexto y reportes Newman). Los cinco RUN técnicos ya no están en el árbol; las menciones siguientes son antecedentes documentales.

## Preparación RF-59 (antecedentes)

Órdenes ORD-G120-002, ORD-G120-003, ORD-G120-005, ORD-G120-007 y ORD-G120-009, fase `preparar`, casos TC-M03-241/242/243. En ORD-G120-009 no se consultó TEST, no se creó RUN real ni SOL y no se modificaron los RUN V1. Las validaciones usan datos sintéticos y un servidor de loopback local.

## Oráculos y decisión QA

Fuente original: `tests/Test_Testing/Test_Modulo3/Casos_Prueba(Modulo3 Agrupado).csv`, registro `TC-M03-G120`; RF-59 en `tests/Test_Testing/Requerimientos/Especificacion-Requerimientos-Modulo3.md`, CA-3 (líneas 6240-6241), CA-18 (6289-6290) y Restricción 14 (5718-5721).

- TC-M03-241: «Las lecturas sincronizadas aparecen en el historial con su timestamp_captura original, se identifican con origen_dato = BUFFER_LOCAL y se diferencian de las lecturas TIEMPO_REAL, sin dejar vacíos dentro del intervalo controlado.»
- TC-M03-242: «Después de la segunda sincronización, el historial contiene una sola lectura lógica para la combinación (sensor_id, timestamp_captura); no aparecen duplicados ni se altera el timestamp original.»
- TC-M03-243: «Ambas lecturas son integradas al historial conservando su timestamp_captura original. El sistema registra también el momento de sincronización, permitiendo comprobar el retraso de 23 h y 24 h respectivamente.»

Decisión del responsable QA, 2026-10-26: API-243-01 se decide por las dos lecturas `BUFFER_LOCAL` de 23 h y 24 h integradas en historial con su captura original. El momento de sincronización es una observación: el ejecutor intenta GET de auditoría RF-63 como Administrador dentro del RUN, con eco y filtro por cada ID de lectura, si dispone de credenciales y permiso (39,2). Registra HTTP, eventos vinculados y campo de sincronización encontrado. La ausencia, nulidad o inaccesibilidad del momento no cambia el veredicto. RF-59 Restricción 14 pide registrarlo para auditoría y no exige mostrarlo en historial.

La matriz habla de clave de dos campos y límite de 24 h; RF-59 CA-18 usa cuatro campos `(sensor_id, tipo_variable, timestamp_captura, origen)` y Restricción 14 permite 72 h. El duplicado conserva variable y origen, y los dos bordes caben en 72 h. La discrepancia es documental, sin alterar los resultados esperados anteriores.

## Inventario y ejecución futura

Ejecutor canónico: `g120.mjs`; colección Newman vigente: `G120.postman_collection.json`; lógica y contrato: `lib/`; regresiones y ensayo: `pruebas/`. No hay Cypress spec/config porque los tres casos requieren API. Se retiró `.gitkeep` como legado sin referencias. La limpieza posterior conservó intactas las evidencias del RUN oficial salvo su Markdown y eliminó los cinco RUN técnicos autorizados.

El lanzador externo aporta `QA_AUTORIZADO=SI` y `contexto_operacion.json` real con grupo, versión, intento, RUN, operación, referencia, casos, alcance de reevaluación y versión anterior. El ejecutor exige base TEST canónica y RUN ya creado por el lanzador. `QA_G120_EFECTOS_AUTORIZADOS` no existe como barrera. `preflight.json` conserva la decisión QA como dato informativo.

Fuente única del presupuesto: `lib/g120_presupuesto.cjs` (consultable localmente con `node lib/g120_presupuesto.cjs`). Máximo **72 solicitudes directas**: OpenAPI 1, logins Productor/Administrador 2, listados de semilla y catálogo 3, hasta 8 dashboards de unidad, hasta 12 listados de sensores, hasta 36 historiales de semilla, basal 1, ingestas 5, auditoría 2 y cierre/rollback 2; **1** Newman; **600 s** totales y guarda de **170 s** entre inicios de peticiones del RUN frente al límite de inactividad de 180 s. Las consultas de descubrimiento usan **20 s** de timeout; la guardia global corta nuevas consultas antes de 540 s para reservar cierre. El cierre y la lectura de rollback ocupan las dos solicitudes reservadas. No hay pausas deliberadas.

## Corrección de semilla ORD-G120-005 y ORD-G120-007

Contratos consultados en `origin/test` (SHA `5b46ca00a0ba92774f8e3d4b9eeaeec169344f17`):

- `src/configuration/infrastructure/routers/dispositivo_iot_router.py:129-161` y `src/configuration/infrastructure/schema/dispositivo_iot_schema.py:11-49`: `GET /configuracion/dispositivos-iot?solo_activos=true` devuelve `{total,items}`; cada dispositivo expone `id_dispositivo_iot`, `serial`, `id_infraestructura`, `categoria`, `es_activo`.
- `src/telemetry/infrastructure/routers/infraestructura_iot_router.py:118-142` y `src/telemetry/infrastructure/schema/estado_dispositivo_iot_schema.py:61-74`: `GET /iot/dispositivos` devuelve arreglo con `id_dispositivo_iot` y `estado_actual`. Ese estado RF-60 es de conectividad y se registra solo como diagnóstico.
- `src/configuration/infrastructure/routers/dispositivo_iot_router.py:276-298` y `src/configuration/infrastructure/schema/sensor_schema.py:9-30`: `GET /configuracion/dispositivos-iot/{id}/sensores` devuelve `{total,items}` con `id_sensores`, `id_dispositivo_iot`, `es_activo`.
- `src/telemetry/infrastructure/routers/monitoreo_router.py:111-148,206-281` y `src/telemetry/infrastructure/schema/monitoreo_schema.py:15-46,68-108,137-151`: dashboard por unidad devuelve `sensores` con `estado_semaforo`, `estado_calidad`, `ultimo_valor`, `ultima_unidad`; historial devuelve `{total,items}` con `estado_calidad`, `valor`, `unidad_medida`, `timestamp_captura` y umbrales opcionales.
- `src/telemetry/application/use_cases/ingesta/ingerir_telemetria_use_case.py:40-45` y `src/telemetry/infrastructure/adapters/dispositivo_m09_adapter.py:15-43`: la ingesta comprueba correspondencia de `device_id` y `serial` con el dispositivo registrado y su condición `es_activo`; el sensor debe estar activo y vinculado. No usa `estado_actual` de conectividad RF-60 como requisito de ingreso.

El intento 3 (`RUN-G120-V1-20261026-223634`) mostró cuatro sensores en unidad 1 y uno en unidad 268, sin VERDE ni lectura válida reciente; la unidad 337 terminó en `TimeoutError` a 8 s y el ejecutor abortó. La decisión QA ORD-G120-009 adopta la opción A: sensor existente, activo y vinculado a un dispositivo activo en configuración con serial, aunque esté sin señal. La matriz G120, columna «Datos de prueba», pide lecturas `BUFFER_LOCAL` con sensor y captura conocidos, sin exigir semáforo o lecturas recientes. RF-53 exige dispositivo registrado y activo, serial y sensor vinculado (`src/telemetry/infrastructure/adapters/dispositivo_m09_adapter.py:15-43`); RF-60 no es condición de ingreso. Son requisitos de la semilla, no cambios de oráculo.

Tras leer una sola vez los listados de configuración y RF-60, el selector consulta `GET /iot/monitoreo/dashboard/{id}` como Productor dentro del RUN, con `pagina=1&por_pagina=50`, para las unidades 1, 268 y 337 y luego otras unidades visibles hasta el tope de ocho. Acepta sensores GRIS y sin lectura reciente si están activos, vinculados a un dispositivo activo en configuración con serial. Prefiere los que tienen lectura válida reciente, sin exigirla. Si una unidad falla por timeout o transporte, registra el error y continúa; si al final no logra evaluar la semilla por ese impedimento, devuelve `NO_CONCLUYENTE`. Consulta el listado de sensores para confirmar vínculo y actividad. Si el dashboard no aporta semilla, recorre hasta 12 dispositivos como último recurso, con hasta tres sensores por dispositivo. El estado RF-60 queda informativo. El historial basal comprueba límites y colisión de timestamps antes de ingestas. No crea dispositivos, sensores ni cuentas.

El valor se toma del historial público `GET /iot/monitoreo/historial` por sensor, `LECTURA_VALIDA`, `orden=DESC`, desde 1970-01-01 para abarcar el historial disponible sin exigir lecturas recientes. El máximo de 90 días solo aplica a consultas sin filtro adicional (`src/telemetry/application/use_cases/monitoreo/consultar_historial_use_case.py:31,93-113`); aquí siempre se filtra por sensor. La API expone `valor_min_umbral` y `valor_max_umbral` de M09/RF-17 por lectura (`src/telemetry/infrastructure/schema/monitoreo_schema.py:89-105`; `src/telemetry/infrastructure/routers/monitoreo_router.py:205-279`). Si ambos límites son numéricos y coherentes, usa su punto medio; en otro caso, usa el valor de la última lectura válida del sensor, sin exigir VERDE. El historial aporta `id_variable` y una etiqueta de presentación; el catálogo público aporta `id_variable_ambiental`, nombre y unidad. El ejecutor los cruza y construye el código normalizado del nombre del catálogo para la ingesta, tal como admite `VariableCatalogoM09Adapter`. El catálogo público no expone `codigo_telemetria`; por ello no se afirma haber leído esa columna. El historial sigue filtrándose por nombre de presentación. `diagnostico_semilla.fuente_valor` registra método, captura, unidad y rango usado. Sin umbral ni lectura válida no inventa valor y declara `DATOS_SEMILLA_SIN_VALOR_SEGURO` (`BLOQUEADO`) si el alcance fue completo. Si el alcance se agotó por tope o fallo técnico, devuelve `NO_CONCLUYENTE` con diagnóstico. Con valor dentro del rango configurado no debería generarse alerta RF-57; un umbral histórico puede haber cambiado y, cuando solo hay valor histórico sin umbral, la ausencia de alerta tampoco se puede garantizar antes del RUN. Las ingestas del escenario quedan dentro del sandbox y el cierre comprueba su desaparición del historial público.

`diagnostico_semilla` en `resultado.json` y en el informe generado por un RUN futuro registra HTTP, eco, cantidades recibidas y cantidades que pasan cada filtro, sin seriales, correos ni nombres. Un listado vacío completamente revisado produce `BLOQUEADO` por `DATOS_SEMILLA_NO_DISPONIBLES`; una forma de respuesta inesperada produce `ERROR_QA_CONTRATO_SEMILLA` técnico y `NO_CONCLUYENTE`. Con cero escrituras confirmadas, cero resultados de escritura desconocidos y DELETE 200, el rollback queda verificado con motivo `sin escrituras de escenario; DELETE 200`. Cuando hay escrituras, se mantiene la comprobación de historial público posterior al DELETE.

Para una SOL futura cambia el orden de lectura: los dashboards se consultan incluso antes de saber si un dispositivo tiene sensores; por ello puede haber más consultas de dashboard y menos consultas por dispositivo e historiales. `src/telemetry/application/use_cases/monitoreo/obtener_dashboard_use_case.py:62-78,153-159` llama al aviso por sensores sin umbral; `src/telemetry/infrastructure/adapters/aviso_sin_umbral_email_adapter.py:66-99,108-135` puede registrar auditoría y enviar correo a administradores fuera del rollback del escenario. El preflight y el diagnóstico declaran este efecto para revisión particular antes de ejecutar. Las escrituras de escenario y los demás efectos declarados siguen sujetos a la decisión QA y a autorización particular del lanzador externo.

En ORD-G120-007 se leyeron el CSV y RF citados arriba, `src/telemetry/infrastructure/schema/monitoreo_schema.py`, `src/telemetry/infrastructure/routers/monitoreo_router.py` y `src/telemetry/application/use_cases/monitoreo/obtener_dashboard_use_case.py`, además del `resultado.json` saneado del intento 2. En ORD-G120-003 se consultaron `src/telemetry/infrastructure/routers/auditoria_iot_router.py` y `src/telemetry/infrastructure/schema/bitacora_auditoria_iot_schema.py`. La preparación previa declaró búsquedas acotadas de `entidad_afectada_id` en `src/telemetry/application/` y `src/telemetry/infrastructure/repositories/postcommit_repository.py`. No se consultó SQL ni código frontend en esta orden. Las referencias anteriores a `origin/test` describen la preparación ORD-G120-001; no se verificó Git ni el despliegue en esta orden.

## Corrección ORD-G120-011 (preparar, sin TEST)

En el intento 4, el historial entregó una etiqueta de presentación (por ejemplo, `Temperatura Corporal`) y el ejecutor la envió literalmente como `tipo_variable`. En `origin/test` (`5b46ca00a0ba92774f8e3d4b9eeaeec169344f17`), `src/telemetry/infrastructure/dto/ingerir_telemetria_dto.py:62-64` solo aplica mayúsculas y trim; `src/telemetry/infrastructure/adapters/variable_catalogo_m09_adapter.py:19-20,32-54` busca el código `codigo_telemetria` o el nombre normalizado con guiones bajos. `src/telemetry/application/use_cases/ingesta/ingerir_telemetria_use_case.py:55-59` devuelve `VARIABLE_NO_ENCONTRADA` si no hay correspondencia. Es la causa **más probable**, no confirmada, de los rechazos del intento 4: ese RUN descartó los errores por ítem. El `POST /iot/telemetria` existe en `src/telemetry/infrastructure/routers/telemetria_router.py:61-77`; el 404 observado podría ser el mismo `VARIABLE_NO_ENCONTRADA`, pero el cuerpo tampoco se guardó. No se atribuye el 404 a una ruta ausente sin conocer su error.

El catálogo público `GET /configuracion/variables-ambientales` (`src/configuration/infrastructure/routers/variable_ambiental_router.py:50-68`) expone ID, nombre y unidad (`src/configuration/infrastructure/schema/umbral_schema.py:57-69`), pero no `codigo_telemetria`. Se consulta con el token Administrador cuando está disponible porque exige permiso de lectura de umbrales; sin ese token, se intenta con Productor y un 403 queda como impedimento técnico. El historial expone `id_variable` y nombre de presentación (`src/telemetry/infrastructure/schema/monitoreo_schema.py:78-86`; `src/telemetry/infrastructure/repositories/historial_telemetria_repository.py:25-34`). Se cruza el ID, nombre y unidad entre ambas APIs y se usa el nombre normalizado aceptado por el adaptador; el `id_variable` se incluye en el cuerpo. El listado público de sensores solo confirma ID, dispositivo y actividad (`src/configuration/infrastructure/schema/sensor_schema.py:9-16`); no contiene vinculación directa con variable. El dispositivo aporta el serial y la ingesta lo contrasta con `device_id` (`src/telemetry/infrastructure/adapters/dispositivo_m09_adapter.py:47-68`); la pertenencia del sensor al dispositivo se comprueba en el listado y en la función de ingesta. El DTO exige `device_id`, `sensor_id`, `tipo_variable`, `valor`, `unidad`, `timestamp_captura` y `serial`; `timestamp_envio` y `origen` son opcionales, pero se envían explícitamente (`ingerir_telemetria_dto.py:18-29,67-68`). El catálogo exige unidad coherente (`variable_catalogo_m09_adapter.py:52-55`).

Un RUN futuro conservará `error` de cada `ItemBatchResponse` (`src/telemetry/infrastructure/schema/telemetria_schema.py:17-23`) y `error_code`, `message` y otros campos públicos del cuerpo de cada POST individual, saneados en `resultado.json` e informe. Sin aceptación de las lecturas necesarias, la falta de filas en historial produce `NO_CONCLUYENTE` y un diagnóstico `ERROR_QA` cuando el cuerpo es inválido; fallos de datos o infraestructura comprobados pueden dar `BLOQUEADO`. Un rechazo explícito por antigüedad de una captura a 23 h/24 h contradice RF-59 Restricción 14 (`Especificacion-Requerimientos-Modulo3.md:5718-5721`) y permite `RECHAZADO` con incidencia. El ensayo `todo_rechazado_cuerpo` altera el tipo solo en loopback y debe dar tres `NO_CONCLUYENTE`, errores por ítem guardados y ninguna incidencia; `rechazo_por_antiguedad_23h` debe dar `APROBADO,APROBADO,RECHAZADO` y la plantilla de incidencia cita Restricción 14; `contraste_404` debe dar `NO_CONCLUYENTE,APROBADO,APROBADO` con cuerpo de error y diagnóstico técnico. El flujo feliz conserva tres `APROBADO`.

## Efectos para declarar en una SOL futura

- Esperados revertidos: filas de ingesta e historial dentro de la sesión sandbox; se acredita solo mediante GET público posterior a DELETE.
- Persistentes aceptados por QA: auditoría de login y consultas fuera del RUN; `ruta_ingesta_auditada.py` puede registrar auditoría fuera del sandbox ante 422 estructural o fallo de persistencia. DELETE no la revierte.
- Externos posibles: el worker postcommit usa conexión propia y podría persistir efectos si llegara a procesar datos visibles. El ejecutor no envía MQTT ni llama a Edge.
- Externos posibles del nuevo descubrimiento: GET dashboard puede enviar correo a administradores y registrar auditoría si encuentra sensores sin umbral. DELETE del RUN no deshace correos ya enviados.
- No se afirma cierre ni rollback por un HTTP 200 aislado.

## Validación local

Ejecutar desde esta carpeta:

```text
node --check g120.mjs
node --check lib/g120_escenario.mjs
node --check pruebas/g120_ensayo.mjs
node g120.mjs --capacidades
node g120.mjs --comprobar
node pruebas/g120.test.mjs
node pruebas/g120_ensayo.mjs
```

Salida esperada del ensayo local, observada el 2026-10-26:

```text
OK aprobado: APROBADO,APROBADO,APROBADO oficial=true registro=true
OK semilla_dashboard_verde: APROBADO,APROBADO,APROBADO oficial=true registro=true
OK semilla_dashboard_reciente: APROBADO,APROBADO,APROBADO oficial=true registro=true
OK intento2_dashboard: APROBADO,APROBADO,APROBADO oficial=true registro=true
OK intento3_sin_lecturas_recientes: APROBADO,APROBADO,APROBADO oficial=true registro=true
OK unidad_timeout_continua: APROBADO,APROBADO,APROBADO oficial=true registro=true
OK sin_valor_seguro: BLOQUEADO,BLOQUEADO,BLOQUEADO oficial=false registro=false
OK busqueda_acotada: NO_CONCLUYENTE,NO_CONCLUYENTE,NO_CONCLUYENTE oficial=false registro=false
OK rf60_activo_recurso: APROBADO,APROBADO,APROBADO oficial=true registro=true
OK timestamp_alterado: RECHAZADO,APROBADO,APROBADO oficial=true registro=true
OK duplicado: APROBADO,RECHAZADO,APROBADO oficial=true registro=true
OK origen_incorrecto: RECHAZADO,APROBADO,APROBADO oficial=true registro=true
OK sync_invalido: APROBADO,APROBADO,APROBADO oficial=true registro=true
OK sync_ausente: APROBADO,APROBADO,APROBADO oficial=true registro=true
OK auditoria_denegada: APROBADO,APROBADO,APROBADO oficial=true registro=true
OK todo_rechazado_cuerpo: NO_CONCLUYENTE,NO_CONCLUYENTE,NO_CONCLUYENTE oficial=false registro=false
OK rechazo_por_antiguedad_23h: APROBADO,APROBADO,RECHAZADO oficial=true registro=true
OK contraste_404: NO_CONCLUYENTE,APROBADO,APROBADO oficial=false registro=false
OK contraste_error_tiempo: NO_CONCLUYENTE,APROBADO,APROBADO oficial=false registro=false
OK contraste_existente: APROBADO,APROBADO,APROBADO oficial=true registro=true
OK error5xx: APROBADO,APROBADO,BLOQUEADO oficial=false registro=false
OK sin_semilla: BLOQUEADO,BLOQUEADO,BLOQUEADO oficial=false registro=false
OK contrato_inesperado: NO_CONCLUYENTE,NO_CONCLUYENTE,NO_CONCLUYENTE oficial=false registro=false
OK sin_eco: NO_CONCLUYENTE,NO_CONCLUYENTE,NO_CONCLUYENTE oficial=false registro=false
G120 ENSAYO 24/24
```

`pruebas/registro_qa.mjs` emula las comprobaciones obligatorias del registro: API-241-01, API-242-01 y API-243-01; no publica clave UI. Un informe real solo se genera dentro del RUN externo autorizado. Ningún resultado funcional de TEST se infiere del ensayo.

La regresión `pruebas/g120.test.mjs` comprueba UTF-8 válido y ausencia de secuencias mojibake en los archivos fuente del grupo. `pruebas/g120_ensayo.mjs` aplica la misma comprobación al informe Markdown generado en el directorio temporal del ensayo.

## Ajuste ORD-G120-013: contraste TIEMPO_REAL

Regla comprobada en `origin/test` (SHA `5b46ca00a0ba92774f8e3d4b9eeaeec169344f17`): `src/telemetry/application/use_cases/ingesta/ingerir_telemetria_use_case.py:24,81,92-96` envía los timestamps a la función de ingesta y traduce `ERROR_TIEMPO` al mensaje HTTP genérico; `alembic/versions/a0183109ae88_fixinfraesturaespecie.py:871,1041-1073` rechaza cuando `timestamp_captura` es posterior a `v_ts_procesamiento := NOW()`. La rama de antigüedad de 72 h (`:1075-1104`) solo aplica a `BUFFER_LOCAL`. `src/shared/fechas.py:33-40` normaliza instantes a UTC. El código consultado no condiciona este rechazo a `timestamp_envio`, milisegundos ni a la última lectura del sensor. En el intento 5, `g120.mjs` fijaba `m.real` a `Date.now() - 1000` y `timestamp_envio` al instante del POST: ese segundo de margen podía desaparecer frente al reloj del servidor. La regla está confirmada en código; que un desfase de relojes concreto causara el HTTP 400 de TEST es una inferencia, pues el cuerpo público no incluye la comparación interna.

El ejecutor toma primero una lectura `TIEMPO_REAL` única, del mismo sensor y variable, presente en el historial basal y dentro de la misma consulta que luego verifica Newman. No la escribe ni la cuenta para rollback. Si no existe, selecciona una captura cinco a diez minutos anterior al POST, sin colisión con historial ni marcas del escenario, y envía `timestamp_envio` actual en UTC. Si el POST de contraste falla, TC-M03-241 conserva la evaluación independiente del intervalo `BUFFER_LOCAL`: si captura, origen o continuidad incumplen, `RECHAZADO`; si están acreditados, `NO_CONCLUYENTE` parcial para la diferenciación, con HTTP y cuerpo público exactos. Un rechazo temporal aislado del contraste no crea incidencia de producto. TC-M03-242 y TC-M03-243 mantienen sus criterios y flujo.

El límite permanece en 72 solicitudes directas, una Newman, 600 s y guardia de 170 s. La reutilización ahorra un POST; el fallback consume el mismo POST ya presupuestado. Los efectos remotos declarados siguen siendo los de la sección anterior; esta preparación no crea SOL, RUN ni evidencia de TEST. El ensayo local agrega `contraste_error_tiempo` y `contraste_existente`; las salidas esperadas son las dos líneas nuevas del bloque anterior y `G120 ENSAYO 24/24`.
