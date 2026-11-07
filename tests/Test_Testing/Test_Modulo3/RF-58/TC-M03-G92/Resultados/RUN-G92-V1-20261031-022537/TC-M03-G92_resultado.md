# TC-M03-G92 — RECHAZADO

## 1. Identificación

Proyecto SIGAB/SGPMP; módulo 3, RF-58/CU04, CA-14; grupo G92; casos TC-M03-181, TC-M03-182, TC-M03-183; versión V1; ambiente TEST según el registro del RUN; fecha y hora 2026-10-31 02:25:37 (marca del RUN; zona no acreditada); RUN RUN-G92-V1-20261031-022537; autorización AUT-G92-V1-R10-20261031. Rama NO_VERIFICADA; commit NO_VERIFICADO. Colección Postman/Newman: 1 ejecución registrada, 4 solicitudes y 16 aserciones (3 fallidas). Node de regeneración v22.15.1 (verificado localmente); versiones de Node, Newman y Postman del RUN: NO_VERIFICADAS en los artefactos; Cypress no exigido ni ejecutado.

## 2. Resumen ejecutivo y decisión del grupo

**Decisión del caso del grupo:** RECHAZADO. RUN oficial, estado COMPLETO. Total 3: aprobados 2, rechazados 1, bloqueados 0 y no concluyentes 0; 1 incidencia funcional confirmada. El filtrado de unidades y el resumen ROJO de B se registraron como aprobados; el resumen de A en página 1 oculta el ROJO de la página 2. TC-M03-181 está APROBADO por PRE-181-01 y las obligatorias API-181-01/02. Dos fallos históricos de Newman corresponden a desajustes de automatización QA, sin efecto en ese veredicto.

| Caso | Funcional | Técnico |
|---|---|---|
| TC-M03-181 | APROBADO | OK |
| TC-M03-182 | APROBADO | OK |
| TC-M03-183 | RECHAZADO | OK |

## 3. Detalle por caso y comprobaciones API/UI

### TC-M03-181

**Caso original y objetivo:** Consolidar el estado general de una unidad utilizando el peor semáforo entre sus sensores.

**Precondiciones:** Unidad B (698), tres sensores 1202–1204 con lectura de 25 °C; alerta ESTRES_TERMICO CRITICO activa asociada a 1204. La matriz pide VERDE, AMARILLO y ROJO.

**Pasos ejecutados:** Se ingresaron las tres lecturas y la alerta del escenario; se consultó GET /iot/monitoreo/dashboard filtrado por unidad B. Newman ejecutó además dos aserciones heredadas fuera del alcance QA vigente.

**Entradas:** `id_infraestructura=698&pagina=1&por_pagina=50`; sensores 1202, 1203 y 1204.

**Esperado:** El resumen de la unidad presenta ROJO como estado general (peor estado presente), incluyendo variables en atención/críticas, alertas activas asociadas y timestamp de actualización.

**Observado por API pública:** **PRE-181-01:** HTTP 200; 1202/1203 VERDE; 1204 ROJO; AMARILLO ausente. **API-181-01:** HTTP 200; estado_general=ROJO; total 3. **API-181-02:** HTTP 200; alertas_activas_count=1; asociada a 1204: sí. **API-181-03:** HTTP 200; variable crítica Temperatura Ambiental en sensor 1204 ROJO; el resumen no expone campo de variables en atención/críticas; 2026-10-31T02:24:41.500000Z.

**Decisión del caso:** **APROBADO en resultado.json.** Las obligatorias API-181-01 y API-181-02 fueron aprobadas; PRE-181-01 cumple VERDE+ROJO según ORD-G92-026. API-181-03 está EXCLUIDA_DEL_ORACULO por decisión QA 2026-10-25, sin efecto en el veredicto.

**Qué falta o cambió:** AMARILLO no fue construible en el sandbox (SBX-G92-02) y queda como observación de entorno. Newman aplicó la versión anterior que exigía AMARILLO; desajuste de automatización QA. API-181-03 se evaluó indebidamente como aserción en esa colección histórica.

| Comprobación | Tipo | Esperado | Observado | HTTP | Estado | Evidencia |
|---|---|---|---|---|---|---|
| PRE-181-01 | Precondición | Al menos un sensor VERDE y uno ROJO en B (decisión QA 2026-10-31) | 1202/1203 VERDE; 1204 ROJO; AMARILLO ausente | 200 | APROBADO | [newman/newman-TC-M03-G92.json](newman/newman-TC-M03-G92.json) |
| API-181-01 | API | Estado general ROJO | estado_general=ROJO; total 3 | 200 | APROBADO | [newman/newman-TC-M03-G92.json](newman/newman-TC-M03-G92.json) |
| API-181-02 | API | Alerta activa asociada y timestamp | alertas_activas_count=1; asociada a 1204: sí | 200 | APROBADO | [newman/newman-TC-M03-G92.json](newman/newman-TC-M03-G92.json) |
| API-181-03 | Observación | EXCLUIDA_DEL_ORACULO por decisión QA 2026-10-25; registrar variables visibles | variable crítica Temperatura Ambiental en sensor 1204 ROJO; el resumen no expone campo de variables en atención/críticas; 2026-10-31T02:24:41.500000Z | 200 | EXCLUIDA_DEL_ORACULO | [newman/newman-TC-M03-G92.json](newman/newman-TC-M03-G92.json) |

### TC-M03-182

**Caso original y objetivo:** Consultar el monitoreo de una unidad productiva específica, mostrando solo su información.

**Precondiciones:** Productor autorizado con acceso a dos unidades; A (697) con 60 sensores y B (698) con tres, lecturas y alertas del escenario.

**Pasos ejecutados:** Se consultó el dashboard de A en dos páginas y el de B en una; se compararon los IDs de sensores y el único resumen de unidad de cada respuesta.

**Entradas:** `id_infraestructura=697&pagina=1&por_pagina=50`; `id_infraestructura=697&pagina=2&por_pagina=50`; `id_infraestructura=698&pagina=1&por_pagina=50`.

**Esperado:** El monitoreo muestra únicamente los sensores e información de la unidad seleccionada, sin datos de otras unidades.

**Observado por API pública:** **PRE-182-01:** HTTP 200; A 60 sensores; B 3. **API-182-01:** HTTP 200; A: 50+10; B: 3; IDs ajenos: 0. **API-182-02:** HTTP 200; A: id 697 y 697; B: id 698.

**Decisión del caso:** **APROBADO.** Los tres listados y sus resúmenes quedaron limitados al filtro solicitado; no aparecieron IDs de la otra unidad.

**Qué falta o cambió:** El fallo de consolidación de 183 afecta el color del resumen A en página 1, pero no contradice el aislamiento del filtro comprobado aquí.

| Comprobación | Tipo | Esperado | Observado | HTTP | Estado | Evidencia |
|---|---|---|---|---|---|---|
| PRE-182-01 | Precondición | Acceso a A y B, sensores disponibles | A 60 sensores; B 3 | 200 | APROBADO | [newman/newman-TC-M03-G92.json](newman/newman-TC-M03-G92.json) |
| API-182-01 | API | Sensores solo de la unidad filtrada | A: 50+10; B: 3; IDs ajenos: 0 | 200 | APROBADO | [newman/newman-TC-M03-G92.json](newman/newman-TC-M03-G92.json) |
| API-182-02 | API | Resumen solo de la unidad filtrada | A: id 697 y 697; B: id 698 | 200 | APROBADO | [newman/newman-TC-M03-G92.json](newman/newman-TC-M03-G92.json) |

### TC-M03-183

**Caso original y objetivo:** Calcular el estado general de la unidad considerando todos sus sensores, no solo los de la página consultada.

**Precondiciones:** Unidad A (697) con 60 sensores ordenados por ID; único ROJO en sensor 1196, posición 55, por alerta ESTRES_TERMICO CRITICO; los otros 59 permanecen VERDE.

**Pasos ejecutados:** Se consultó la página 1 (50 sensores) y la página 2 (10 sensores) del dashboard de A; se comparó el estado_general y la alerta activa en ambos resúmenes.

**Entradas:** `id_infraestructura=697&pagina=1&por_pagina=50` y `id_infraestructura=697&pagina=2&por_pagina=50`.

**Esperado:** En la página 1, estado_general="ROJO" aunque el sensor en ROJO no aparezca en el arreglo de sensores de esa página.

**Observado por API pública:** **PRE-183-01:** HTTP 200; página 1: 50 VERDE; página 2: 10, 1196 ROJO en posición 55. **API-183-01:** HTTP 200; total 60; página 1 50 VERDE. **API-183-02:** HTTP 200; página 1 VERDE; página 2 ROJO; alertas activas 1.

**Decisión del caso:** **RECHAZADO.** API-183-02 observó VERDE en la primera página pese al ROJO de 1196 en la segunda y a una alerta activa; el resumen cambia con la página.

**Qué falta o cambió:** La causa raíz no quedó comprobada; se requiere corrección y reevaluación autorizada de ambas páginas.

| Comprobación | Tipo | Esperado | Observado | HTTP | Estado | Evidencia |
|---|---|---|---|---|---|---|
| PRE-183-01 | Precondición | 60 sensores; único ROJO en posición 55 | página 1: 50 VERDE; página 2: 10, 1196 ROJO en posición 55 | 200 | APROBADO | [newman/newman-TC-M03-G92.json](newman/newman-TC-M03-G92.json) |
| API-183-01 | API | Página 1 con 50 sensores de A, sin ROJO | total 60; página 1 50 VERDE | 200 | APROBADO | [newman/newman-TC-M03-G92.json](newman/newman-TC-M03-G92.json) |
| API-183-02 | API | estado_general ROJO en página 1 y 2 | página 1 VERDE; página 2 ROJO; alertas activas 1 | 200 | RECHAZADO | [newman/newman-TC-M03-G92.json](newman/newman-TC-M03-G92.json) |

La matriz exige API Postman/Newman para estos tres casos; no exige UI. Las tablas muestran el veredicto de resultado.json. API-181-03 se presenta como EXCLUIDA_DEL_ORACULO conforme a la decisión QA de 2026-10-25 aunque el registro histórico la conserve como ASSERT/APROBADO. PRE-181-01 se interpreta según ORD-G92-026.

## 4. Incidencias y observaciones

### Incidencia funcional confirmada

**INC-M03-183-G92 — TC-M03-183: resumen de unidad cambia con la página.**

- **Esperado:** con 60 sensores de A (697) y único ROJO en 1196, posición 55, estado_general ROJO en página 1 y 2.
- **Obtenido y primer punto comprobado:** GET público /iot/monitoreo/dashboard HTTP 200; página 1 VERDE, página 2 ROJO, alertas_activas_count 1 en página 1. API-183-02 RECHAZADO.
- **Evidencia:** [Newman](newman/newman-TC-M03-G92.json), [resultado.json](resultado.json).
- **Impacto y severidad:** **ALTA**; el productor puede ver VERDE mientras existe un sensor ROJO fuera de la página, sin alternativa en ese resumen.
- **Equipo inicial:** **Desarrollo**; la primera discrepancia se observa en la respuesta de la API pública. Esta derivación no atribuye causa raíz.
- **Certeza:** discrepancia **CONFIRMADA** en TEST; causa raíz **NO DETERMINADA**. **Hipótesis:** agregación limitada a la página; el archivo local obtener_dashboard_use_case.py:100-108 es una pista no verificada contra el commit de TEST.
- **Ruta de investigación y acción correctiva:** revisar el agregado del resumen antes de paginar sensores, corregirlo y comprobar ambas páginas por API pública en reevaluación autorizada.
- **Reproducción:** 1) Usar unidad A 697 con 60 sensores, lectura de 25 °C en todos y alerta ESTRES_TERMICO CRITICO activa en 1196 (posición 55). 2) GET /iot/monitoreo/dashboard?id_infraestructura=697&pagina=1&por_pagina=50. 3) Repetir con pagina=2. 4) Comparar estado_general con el ROJO de 1196 y alertas_activas_count=1.

### Incidencias del entorno de pruebas

Estos antecedentes describen limitaciones del sandbox QA; **no son defectos funcionales del producto**. El índice conserva el RUN y el SHA-256 de cada original: [indice.json](api/antecedentes-sandbox/indice.json).

- **SBX-G92-01.** En la transacción única del RUN, `NOW()` queda fijo en su apertura (4007369f8d3d_fix_fn_ingesta_telemetria.py:49,593,651). La ingesta exige también fecha_asociacion ≤ timestamp_captura (15cb081c4835_fix_segundofningestatelemetria.py:181-190), mientras la asociación toma el reloj real (sensor_area.py:47). En el intento 012236, POST /iot/telemetria devolvió HTTP 400 ERROR_TIEMPO pese a que la captura no era futura respecto del reloj del servidor; en el intento 013032, una captura anterior a la apertura para un sensor asociado dentro del RUN devolvió HTTP 401 ERROR_AUTENTICACION, mensaje «Dispositivo o sensor no encontrado o inactivo» (traducción genérica en ingerir_telemetria_use_case.py:26).
  - Impacto: impide ingestas de sensores asociados dentro del RUN. Mitigación aplicada: semilla persistente de las áreas 697/698.
  - Equipo de atención del entorno: **DBA**, con apoyo de **Desarrollo**; la primera discrepancia está en la semántica temporal de la transacción sandbox.
  - Severidad **MEDIA**, limitada a la preparación QA; certeza de los HTTP **CONFIRMADA**, explicación causal **PROBABLE** por código local.
  - Evidencia: [sbx-g92-01-error-tiempo.json](api/antecedentes-sandbox/sbx-g92-01-error-tiempo.json) (origen 012236) y [sbx-g92-01-asociacion.json](api/antecedentes-sandbox/sbx-g92-01-asociacion.json) (origen 013032).
  - **Esperado:** ingesta válida con sensor asociado y captura temporalmente válida.
  - **Obtenido:** HTTP 400 ERROR_TIEMPO y HTTP 401 ERROR_AUTENTICACION en los antecedentes.
  - **Hipótesis:** diferencia entre reloj transaccional y reloj real de asociación; causa no confirmada en TEST.
  - **Ruta y acción:** DBA y Desarrollo deben contrastar marcas de transacción/asociación e indicar una forma segura de preparar sensores.
  - **Reproducción:** 1) abrir RUN sandbox; 2) asociar sensor nuevo dentro de la transacción; 3) enviar telemetría con captura anterior a la apertura y luego con captura posterior a la asociación; 4) comparar HTTP y marcas. No repetir sin autorización.
- **SBX-G92-02.** La clasificación RF-17 por niveles pasa por el worker postcommit con conexión propia y lecturas confirmadas (postcommit_worker.py:155,173-185; reclasificar_semaforo_use_case.py:89). En el intento 021342, el sensor 1203 con 19,5 °C y el 1196 con 16 °C quedaron VERDE; el 1204 con 16 °C quedó ROJO por alerta CRITICO. Las lecturas del RUN no se confirman durante la evaluación.
  - Impacto: AMARILLO de la precondición de TC-M03-181 no es construible por lectura en este sandbox; el ROJO se obtuvo por alerta.
  - Mitigación: conservar esa limitación documentada y evaluar el escenario ROJO por alerta sin alterar el oráculo.
  - Equipo de atención del entorno: **DBA**, con apoyo de **Desarrollo**; la primera limitación se observa en la visibilidad de lecturas entre transacciones.
  - Severidad **MEDIA**, porque bloquea escenarios QA dependientes del color por lectura; certeza de los colores **CONFIRMADA**, explicación causal **PROBABLE** por código local.
  - Evidencia: [sbx-g92-02-semaforo.json](api/antecedentes-sandbox/sbx-g92-02-semaforo.json) (origen 021342).
  - **Esperado:** lecturas de atención clasificadas AMARILLO según RF-17 durante la prueba.
  - **Obtenido:** 1203 a 19,5 °C y 1196 a 16 °C siguieron VERDE; 1204 a 16 °C fue ROJO por alerta CRITICO.
  - **Hipótesis:** worker postcommit no ve lecturas sin confirmar; causa no acreditada contra el despliegue TEST.
  - **Ruta y acción:** DBA y Desarrollo deben comprobar visibilidad transaccional y definir un escenario que permita observar AMARILLO.
  - **Reproducción:** 1) ingestar lectura de atención en sandbox; 2) consultar GET /iot/monitoreo/dashboard dentro del RUN; 3) comparar semáforo antes y después del commit en evaluación autorizada. No repetir sin autorización.

### Observación documental separada

La matriz original menciona variables en atención/críticas. El sensor 1204 muestra la variable crítica Temperatura Ambiental; el resumen público no expone campo de variables en atención/críticas. El responsable QA confirmó el 2026-10-25 (SOL-G92-004 §9/§12 y SOL-G92-009) que RF-58 no exige ese campo en el resumen: API-181-03 es EXCLUIDA_DEL_ORACULO, observación documental sin efecto en veredicto u oficialidad.

### Problemas técnicos QA

Ninguno adicional registrado en resultado.json.

- PRE-181-01: Newman aplicó la versión anterior de la colección que exigía AMARILLO; la precondición vigente por ORD-G92-026 es VERDE+ROJO. La colección no estaba sincronizada con el ejecutor.
- API-181-03: Newman la evaluó como aserción fallida. El registro del intento 10 la incluyó entre las obligatorias por arrastre técnico del ejecutor, pese a la exclusión decidida por QA el 2026-10-25. El registro histórico se conserva sin cambios. Ambos son problemas de automatización QA, sin equipo de producto.

El intento histórico 1 registró timeout de GET global y riesgo de correo E7 sin envío confirmado; no constituye evidencia de producto de este RUN. Los dos desajustes de 181 quedaron conciliados con las decisiones QA vigentes; el tercer fallo de Newman corresponde a API-183-02.

### RLS y comprobaciones técnicas

- RLS-G92-01: APROBADO; Creacion autorizada y lectura posterior por API publica; [resultado.json](resultado.json).
- RLS-G92-02: APROBADO; Lectura HTTP 200 con total 0 e items []; creación HTTP 403 ACCESO_DENEGADO por rol: no aísla RLS de INSERT; UPDATE no expuesto por API pública; [resultado.json](resultado.json).
- RLS-G92-03: NO_CONCLUYENTE; No existe UPDATE publico de sensor que permita probar traslado de dispositivo; SQL directa prohibida; [resultado.json](resultado.json).

## 5. Análisis de fallos

**Hecho confirmado de 183:** GET público /iot/monitoreo/dashboard de A devuelve HTTP 200 en ambas páginas, con 60 sensores y una alerta activa. El primer punto de discrepancia es estado_general=VERDE en página 1, aunque el único ROJO (1196) está en posición 55 y página 2 devuelve ROJO. La causa raíz en TEST no está determinada. **Hipótesis:** el resumen se calcula sobre sensores paginados; la referencia local obtener_dashboard_use_case.py:100-108 procede de análisis anterior, sin versión ni commit verificados en esta orden. Desarrollo debe trazar la selección de sensores previa al agregado, corregir el cálculo global y comprobar ambas páginas en una reevaluación autorizada.

**Análisis de 181:** VERDE y ROJO en B satisfacen PRE-181-01 según ORD-G92-026; API-181-01/02 acreditan resumen ROJO, alerta asociada y timestamp. AMARILLO no se construyó con la transacción sandbox; la explicación causal del worker postcommit RF-17 es PROBABLE según los antecedentes de código local. Newman exigió AMARILLO con la colección anterior y evaluó API-181-03 como aserción, pese a su exclusión por QA; son desajustes técnicos, sin incidencia de producto. Código del producto consultado en esta orden: ninguna ruta; se leyeron la matriz original y RF-58 CA-14, además de la automatización y evidencias locales.

## 6. Conclusiones y acciones

Se comprobó el aislamiento por unidad de 182 y el ROJO de B con alerta y fecha en 181. No se cumplió CA-14 para A en la primera página (183). AMARILLO queda como observación de entorno y API-181-03 como observación documental excluida del oráculo, sin alterar el APROBADO de 181. Desarrollo debe atender INC-M03-183-G92. Una nueva evaluación de 183 requiere decisión y autorización propias; esta edición documental no ejecutó pruebas.

## 7. Herramientas, evidencias, bitácora y rollback

**Newman:** una ejecución, 4 solicitudes y 16 aserciones, 3 fallidas: PRE-181-01, API-181-03 y API-183-02 según [newman/newman-TC-M03-G92.json](newman/newman-TC-M03-G92.json). Reporte HTML: [newman/newman-TC-M03-G92.html](newman/newman-TC-M03-G92.html). No hubo sesiones Cypress.

**Evidencias existentes del RUN:**

- [preflight.json](preflight.json)
- [resultado.json](resultado.json)
- [TC-M03-G92_resultado.md](TC-M03-G92_resultado.md)
- [api/E7-CANARIO-baseline-697.json](api/E7-CANARIO-baseline-697.json)
- [api/E7-CANARIO-baseline-698.json](api/E7-CANARIO-baseline-698.json)
- [api/ESCRITURA-FALLIDA-001.json](api/ESCRITURA-FALLIDA-001.json)
- [api/E7-CANARIO-previo-newman-698.json](api/E7-CANARIO-previo-newman-698.json)
- [api/E7-CANARIO-previo-newman-697.json](api/E7-CANARIO-previo-newman-697.json)
- [newman/newman-TC-M03-G92.json](newman/newman-TC-M03-G92.json)
- [newman/newman-TC-M03-G92.html](newman/newman-TC-M03-G92.html)
- [api/E7-CANARIO-cierre-697.json](api/E7-CANARIO-cierre-697.json)
- [api/E7-CANARIO-cierre-698.json](api/E7-CANARIO-cierre-698.json)

**Bitácora resumida:**

Se registraron 378 solicitudes directas. Se agrupan por método, ruta, HTTP, fase y eco del RUN; el detalle saneado permanece en [resultado.json](resultado.json).

| Cantidad | Método | Ruta | HTTP | RUN | Eco |
|---:|---|---|---:|---|---|
| 5 | POST | `/sesiones/` | 200 | fuera | N/A |
| 2 | GET | `/usuarios/me` | 200 | dentro | sí |
| 1 | GET | `/configuracion/fincas/{id}` | 200 | dentro | sí |
| 2 | GET | `/configuracion/infraestructuras/{id}` | 200 | dentro | sí |
| 2 | GET | `/configuracion/dispositivos-iot/{id}` | 200 | dentro | sí |
| 4 | GET | `/configuracion/dispositivos-iot/{id}/sensores` | 200 | dentro | sí |
| 63 | GET | `/configuracion/sensores/{id}/asociaciones` | 200 | dentro | sí |
| 63 | GET | `/configuracion/sensores/{id}/calibraciones` | 200 | dentro | sí |
| 1 | GET | `/iot/alertas?id_infraestructura=697&por_pagina=200` | 200 | dentro | sí |
| 1 | GET | `/iot/monitoreo/historial?fecha_inicio=2026-10-30&fecha_fin=2026-10-31&id_infraestructura=697&por_pagina=500` | 200 | dentro | sí |
| 1 | GET | `/iot/alertas?id_infraestructura=698&por_pagina=200` | 200 | dentro | sí |
| 1 | GET | `/iot/monitoreo/historial?fecha_inicio=2026-10-30&fecha_fin=2026-10-31&id_infraestructura=698&por_pagina=500` | 200 | dentro | sí |
| 2 | GET | `/configuracion/variables-ambientales` | 200 | dentro | sí |
| 2 | GET | `/configuracion/umbrales?id_especie=126` | 200 | dentro | sí |
| 2 | GET | `/iot/monitoreo/dashboard?id_infraestructura=697&pagina=1&por_pagina=1` | 200 | dentro | sí |
| 2 | GET | `/iot/monitoreo/dashboard?id_infraestructura=698&pagina=1&por_pagina=1` | 200 | dentro | sí |
| 1 | GET | `/iot/monitoreo/dashboard?id_infraestructura=697&pagina=1&por_pagina=50` | 200 | dentro | sí |
| 1 | GET | `/iot/monitoreo/dashboard?id_infraestructura=698&pagina=1&por_pagina=50` | 200 | dentro | sí |
| 1 | POST | `/configuracion/dispositivos-iot/{id}/sensores` | 201 | dentro | sí |
| 1 | POST | `/configuracion/dispositivos-iot/{id}/sensores` | 403 | dentro | sí |
| 63 | POST | `/iot/telemetria` | 201 | dentro | sí |
| 2 | POST | `/iot/alertas` | 201 | dentro | sí |
| 2 | GET | `/iot/alertas/{id}` | 200 | dentro | sí |
| 4 | GET | `/iot/monitoreo/dashboard` | 200 | dentro | sí |
| 1 | DELETE | `/test-control/runs/G92-V1-20261031-022537` | 200 | fuera | N/A |
| 2 | GET | `/iot/alertas/{id}` | 404 | fuera | N/A |
| 2 | GET | `/iot/alertas?id_infraestructura=697&por_pagina=200` | 200 | fuera | N/A |
| 2 | GET | `/iot/monitoreo/historial?fecha_inicio=2026-10-30&fecha_fin=2026-10-31&id_infraestructura=697&por_pagina=500` | 200 | fuera | N/A |
| 2 | GET | `/iot/alertas?id_infraestructura=698&por_pagina=200` | 200 | fuera | N/A |
| 2 | GET | `/iot/monitoreo/historial?fecha_inicio=2026-10-30&fecha_fin=2026-10-31&id_infraestructura=698&por_pagina=500` | 200 | fuera | N/A |
| 3 | GET | `/configuracion/dispositivos-iot/{id}/sensores` | 200 | fuera | N/A |
| 1 | GET | `/iot/monitoreo/dashboard?id_infraestructura=697&pagina=1&por_pagina=1` | 200 | fuera | N/A |
| 1 | GET | `/iot/monitoreo/dashboard?id_infraestructura=697&pagina=1&por_pagina=50` | 200 | fuera | N/A |
| 1 | GET | `/iot/monitoreo/dashboard?id_infraestructura=698&pagina=1&por_pagina=1` | 200 | fuera | N/A |
| 1 | GET | `/iot/monitoreo/dashboard?id_infraestructura=698&pagina=1&por_pagina=50` | 200 | fuera | N/A |
| 1 | GET | `/configuracion/fincas/{id}` | 200 | fuera | N/A |
| 2 | GET | `/configuracion/infraestructuras/{id}` | 200 | fuera | N/A |
| 2 | GET | `/configuracion/dispositivos-iot/{id}` | 200 | fuera | N/A |
| 63 | GET | `/configuracion/sensores/{id}/asociaciones` | 200 | fuera | N/A |
| 63 | GET | `/configuracion/sensores/{id}/calibraciones` | 200 | fuera | N/A |

**Canarios E7:**

- baseline, unidad 697: CONFORME, HTTP 200; [api/E7-CANARIO-baseline-697.json](api/E7-CANARIO-baseline-697.json).
- baseline, unidad 698: CONFORME, HTTP 200; [api/E7-CANARIO-baseline-698.json](api/E7-CANARIO-baseline-698.json).
- previo-newman, unidad 698: CONFORME, HTTP 200; [api/E7-CANARIO-previo-newman-698.json](api/E7-CANARIO-previo-newman-698.json).
- previo-newman, unidad 697: CONFORME, HTTP 200; [api/E7-CANARIO-previo-newman-697.json](api/E7-CANARIO-previo-newman-697.json).
- cierre, unidad 697: CONFORME, HTTP 200; [api/E7-CANARIO-cierre-697.json](api/E7-CANARIO-cierre-697.json).
- cierre, unidad 698: CONFORME, HTTP 200; [api/E7-CANARIO-cierre-698.json](api/E7-CANARIO-cierre-698.json).

**Cierre:** DELETE HTTP 200; rollback VERIFICADO con 10/10 comprobaciones coincidentes y semilla intacta. DELETE y GET posteriores acreditan reversion sin borrar semilla persistente. La reversión de correo E7 y auditoría de GET no fue verificada ni está incluida en el DELETE. Estado final del RUN: COMPLETO.
