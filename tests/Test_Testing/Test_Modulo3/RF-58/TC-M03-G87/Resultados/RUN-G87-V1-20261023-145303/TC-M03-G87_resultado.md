# RESULTADO DE EVALUACIÓN — TC-M03-G87 — V1

## Identificación

Proyecto SIGAB/SGPMP; módulo 3; RF-58; G87; TC-M03-168, TC-M03-177, TC-M03-178.
RUN RUN-G87-V1-20261023-145303; intento 7; operación REINTENTAR; ambiente TEST; 2026-10-23T14:53:03.235Z → 2026-10-23T14:54:39.760Z; autorización AUT-G87-V1-R5-20261023.
Responsable QA de la matriz: Juan Esteban. Rama local: qa/juan-esteban-m03-rf58-rf59; commit local: 352a12e70e4ccc126922cec10a906a8a6525fdcc. Rama y commit desplegados en TEST: sin determinar.
Herramientas verificadas en el RUN: Node v22.15.1; Newman versión sin determinar; Cypress/Chrome 155.0.8059.85.
Segunda regeneración documental 2026-10-23T16:11:12Z (ORD-G87-026) a partir de las evidencias sin cambios del RUN; reemplazaría al informe vigente (SHA-256 3ec5d9b941a3dca8a301cb556ab2e761541a68a251792ffb220085ba89d7ecac), previa conservación de su copia fuera del RUN. La primera regeneración fue ORD-G87-025 y reemplazó el informe original (SHA-256 8e3567fcb2bb30bc497af93c7a17891c137b39c0960a4b8dfce889713e8ffc98). resultado.json conserva un aviso QA erróneo ('Cypress: 0 comprobaciones') no aplicable: Cypress ejecutó 11 pruebas.

## Resumen ejecutivo

Aprobados 1; rechazados 2; bloqueados 0; ERROR_QA 0; no ejecutados 0.
Incidencias funcionales observadas: 2. Veredicto grupal: RECHAZADO. Estado CONCLUIDA; Oficialidad: OFICIAL.

| Caso | Veredicto | Motivo |
| --- | --- | --- |
| TC-M03-168 | APROBADO | La API conservó valor, unidad y hora de la última lectura válida. |
| TC-M03-177 | RECHAZADO | La lectura válida siguió como referencia, pero la anomalía posterior quedó invisible para el Productor. |
| TC-M03-178 | RECHAZADO | El Productor recibió la vista prevista; el Ingeniero no vio la necesidad de calibración. |

## Resultado por caso

### TC-M03-168 — Última lectura válida de cada sensor activo, ignorando una lectura posterior FUERA_DE_RANGO

**Qué se quería comprobar.** HTTP 200. Por cada sensor se devuelven ultimo_valor, ultima_unidad y ultimo_timestamp_captura correspondientes a la última lectura LECTURA_VALIDA, no a la posterior inválida.
**Cómo se preparó.** Sensor 552, dispositivo 357, área 349: lecturas 23, 24, 25 °C clasificadas LECTURA_VALIDA y después 31 °C FUERA_DE_RANGO; umbral 15–30 °C. Consulta del Productor.
**Qué debía verse.** HTTP 200 y valor, unidad y hora de la última lectura válida, sin tomar la lectura posterior inválida.
**Qué se vio realmente.** Las comprobaciones API aprobaron HTTP 200 y la correspondencia con la última válida: 25.0000 °C, capturada a las 2026-10-23T14:49:10.759000Z. La lectura posterior no reemplazó esa referencia. No se exigía UI para este caso.
**Conclusión.** APROBADO: La API conservó valor, unidad y hora de la última lectura válida.

Comprobaciones requeridas: API; pruebas Cypress del RUN: no aplica.

| Comprobación | Fuente | Estado | Obtenido |
| --- | --- | --- | --- |
| SETUP Respuesta atendida dentro del RUN (eco X-Test-Run-Id) | API | APROBADO | Criterio verificado en el RUN. |
| PRE-168-01 Lectura válida 1 aceptada como LECTURA_VALIDA | API | APROBADO | Criterio verificado en el RUN. |
| SETUP Respuesta atendida dentro del RUN (eco X-Test-Run-Id) | API | APROBADO | Criterio verificado en el RUN. |
| PRE-168-01 Lectura válida 2 aceptada como LECTURA_VALIDA | API | APROBADO | Criterio verificado en el RUN. |
| SETUP Respuesta atendida dentro del RUN (eco X-Test-Run-Id) | API | APROBADO | Criterio verificado en el RUN. |
| PRE-168-01 Lectura válida 3 aceptada como LECTURA_VALIDA | API | APROBADO | Criterio verificado en el RUN. |
| SETUP Respuesta atendida dentro del RUN (eco X-Test-Run-Id) | API | APROBADO | Criterio verificado en el RUN. |
| PRE-168-02 Lectura posterior clasificada FUERA_DE_RANGO (RF-53) | API | APROBADO | Criterio verificado en el RUN. |
| SETUP Respuesta atendida dentro del RUN (eco X-Test-Run-Id) | API | APROBADO | Criterio verificado en el RUN. |
| PRE-168-03 Sesión del Productor vigente (no 401) | API | APROBADO | Criterio verificado en el RUN. |
| API-168-01 Dashboard del Productor responde HTTP 200 | API | APROBADO | Criterio verificado en el RUN. |
| API-168-02 El sensor S1 aparece en el dashboard | API | APROBADO | Criterio verificado en el RUN. |
| API-168-03 ultimo_valor = valor de la última LECTURA_VALIDA | API | APROBADO | Criterio verificado en el RUN. |
| API-168-04 ultima_unidad = unidad de la última LECTURA_VALIDA | API | APROBADO | Criterio verificado en el RUN. |
| API-168-05 ultimo_timestamp_captura = timestamp de la última LECTURA_VALIDA | API | APROBADO | Criterio verificado en el RUN. |

Evidencia: [resultado.json](resultado.json), [newman/newman-TC-M03-G87.html](newman/newman-TC-M03-G87.html), [newman/newman-TC-M03-G87.json](newman/newman-TC-M03-G87.json).

### TC-M03-177 — La lectura FUERA_DE_RANGO no es valor operativo del Productor y la anomalía sigue visible

**Qué se quería comprobar.** La lectura FUERA_DE_RANGO no se utiliza como lectura operativa activa; el dashboard conserva la última LECTURA_VALIDA como referencia, y la anomalía permanece visible mediante un indicador claro (ROJO/ícono), sin ocultarse ni descartarse.
**Cómo se preparó.** Sensor 552, dispositivo 357, área 349: lecturas 23, 24, 25 °C clasificadas LECTURA_VALIDA y después 31 °C FUERA_DE_RANGO; umbral 15–30 °C. Consulta del Productor.
**Qué debía verse.** La lectura válida como referencia operativa y un indicador ROJO o ícono que avisara de la anomalía.
**Qué se vio realmente.** La API entregó 25.0000 °C, calidad LECTURA_VALIDA, semáforo VERDE y alerta ninguna. La captura [cypress/g87.cy.js/TC-M03-177_productor_S1.png](cypress/g87.cy.js/TC-M03-177_productor_S1.png) muestra 25.0000 °C en verde con «Normal», sin ROJO ni ícono de anomalía.
**Conclusión.** RECHAZADO: La lectura válida siguió como referencia, pero la anomalía posterior quedó invisible para el Productor.

Comprobaciones requeridas: API y UI; pruebas Cypress del RUN: 11.

| Comprobación | Fuente | Estado | Obtenido |
| --- | --- | --- | --- |
| SETUP Respuesta atendida dentro del RUN (eco X-Test-Run-Id) | API | APROBADO | Criterio verificado en el RUN. |
| SETUP Respuesta atendida dentro del RUN (eco X-Test-Run-Id) | API | APROBADO | Criterio verificado en el RUN. |
| SETUP Respuesta atendida dentro del RUN (eco X-Test-Run-Id) | API | APROBADO | Criterio verificado en el RUN. |
| PRE-177-01 Lectura 25 aceptada como LECTURA_VALIDA | API | APROBADO | Criterio verificado en el RUN. |
| SETUP Respuesta atendida dentro del RUN (eco X-Test-Run-Id) | API | APROBADO | Criterio verificado en el RUN. |
| PRE-177-02 Lectura posterior clasificada FUERA_DE_RANGO (RF-53) | API | APROBADO | Criterio verificado en el RUN. |
| SETUP Respuesta atendida dentro del RUN (eco X-Test-Run-Id) | API | APROBADO | Criterio verificado en el RUN. |
| PRE-177-03 Sesión del Productor vigente (no 401) | API | APROBADO | Criterio verificado en el RUN. |
| API-177-01 Dashboard HTTP 200 y el sensor S1 no se oculta | API | APROBADO | Criterio verificado en el RUN. |
| API-177-02 La lectura FUERA_DE_RANGO no reemplaza el valor operativo 25 | API | APROBADO | Criterio verificado en el RUN. |
| API-177-03 La anomalía permanece visible (estado_calidad FUERA_DE_RANGO o semáforo ROJO) | API | RECHAZADO | Valor 25.0000 °C; calidad LECTURA_VALIDA; semáforo VERDE; alerta ninguna. |
| PRE-UI-01 Productor: la UI recibe el dashboard real del RUN | UI | APROBADO | Criterio verificado en el RUN. |
| UI-177-01 Productor: la tarjeta de S1 es visible | UI | APROBADO | Criterio verificado en el RUN. |
| UI-177-02 Productor: S1 muestra 25 como valor operativo, no el anómalo | UI | APROBADO | Criterio verificado en el RUN. |
| UI-177-03 Productor: la anomalía de S1 es visible (ROJO / ícono) | UI | RECHAZADO | Tarjeta en verde con «Normal»; no se encontró indicador ROJO ni ícono de anomalía. |

Evidencia: [resultado.json](resultado.json), [newman/newman-TC-M03-G87.html](newman/newman-TC-M03-G87.html), [newman/newman-TC-M03-G87.json](newman/newman-TC-M03-G87.json), [cypress/g87.cy.js/TC-M03-177_productor_S1.png](cypress/g87.cy.js/TC-M03-177_productor_S1.png).

### TC-M03-178 — Presentación de ERROR_CALIBRACION diferenciada entre Productor e Ingeniero de Campo

**Qué se quería comprobar.** Productor: ERROR_CALIBRACION no se presenta como lectura operativa ni genera alerta operativa, sin exponer información técnica reservada al Ingeniero. Ingeniero de Campo: identifica el sensor con condición de error técnico y visualiza el detalle necesario para reconocer que requiere calibración. El sensor permanece visible y la lectura inválida no se trata como operacional normal.
**Cómo se preparó.** Sensor 77, dispositivo 266, sin calibración: lecturas 21.7 y 22.3 °C clasificadas ERROR_CALIBRACION. Se consultó como Productor y como Ingeniero de Campo.
**Qué debía verse.** El Productor no debía recibir una lectura ni alerta operativa por el error, ni datos técnicos. El Ingeniero debía ver el sensor, el error técnico y el detalle que indicara que requiere calibración, sin tratar la lectura inválida como normal.
**Qué se vio realmente.** Las comprobaciones del Productor aprobaron y su [cypress/g87.cy.js/TC-M03-178_productor_S2.png](cypress/g87.cy.js/TC-M03-178_productor_S2.png) no muestra datos técnicos. Para el Ingeniero, la API devolvió 25.0000 °C, calidad LECTURA_VALIDA, semáforo VERDE, batería 77.00 % y RSSI -83.00 dBm, sin indicador de calibración. El valor mostrado corresponde a la última lectura VÁLIDA anterior del sensor 77, capturada el 2026-10-21T19:58:32.541708Z, según resultado.json. Las dos lecturas nuevas de 21.7 y 22.3 °C, clasificadas ERROR_CALIBRACION, no aparecen en esa vista. La [cypress/g87.cy.js/TC-M03-178_ingeniero_S2.png](cypress/g87.cy.js/TC-M03-178_ingeniero_S2.png) muestra la tarjeta verde «Normal»; el detalle textual conservado en resultado.json también muestra «Normal» y LECTURA_VALIDA, sin mencionar calibración.
**Conclusión.** RECHAZADO: el Ingeniero solo vio la lectura válida anterior de 25.0000 °C; las dos lecturas nuevas ERROR_CALIBRACION no aparecen y no puede reconocer la necesidad de calibración en esa vista.

Comprobaciones requeridas: API y UI; pruebas Cypress del RUN: 11.

| Comprobación | Fuente | Estado | Obtenido |
| --- | --- | --- | --- |
| SETUP Respuesta atendida dentro del RUN (eco X-Test-Run-Id) | API | APROBADO | Criterio verificado en el RUN. |
| SETUP S2 asociado al área del escenario (RF-22) | API | APROBADO | Criterio verificado en el RUN. |
| SETUP Respuesta atendida dentro del RUN (eco X-Test-Run-Id) | API | APROBADO | Criterio verificado en el RUN. |
| PRE-178-01 Lectura 1 de S2 clasificada ERROR_CALIBRACION | API | APROBADO | Criterio verificado en el RUN. |
| SETUP Respuesta atendida dentro del RUN (eco X-Test-Run-Id) | API | APROBADO | Criterio verificado en el RUN. |
| PRE-178-01 Lectura 2 de S2 clasificada ERROR_CALIBRACION | API | APROBADO | Criterio verificado en el RUN. |
| SETUP Respuesta atendida dentro del RUN (eco X-Test-Run-Id) | API | APROBADO | Criterio verificado en el RUN. |
| PRE-178-02 Sesión del Productor vigente (no 401) | API | APROBADO | Criterio verificado en el RUN. |
| API-178-01 Productor: HTTP 200 y el sensor S2 permanece visible | API | APROBADO | Criterio verificado en el RUN. |
| API-178-02 Productor: ERROR_CALIBRACION no se presenta como lectura operativa | API | APROBADO | Criterio verificado en el RUN. |
| API-178-03 Productor: S2 no genera alerta operativa | API | APROBADO | Criterio verificado en el RUN. |
| API-178-04 Productor: no recibe información técnica (batería, RSSI, SNR) | API | APROBADO | Criterio verificado en el RUN. |
| SETUP Respuesta atendida dentro del RUN (eco X-Test-Run-Id) | API | APROBADO | Criterio verificado en el RUN. |
| PRE-178-03 Sesión del Ingeniero vigente (no 401) | API | APROBADO | Criterio verificado en el RUN. |
| API-178-05 Ingeniero: HTTP 200 y el sensor S2 permanece visible | API | APROBADO | Criterio verificado en el RUN. |
| API-178-06 Ingeniero: identifica condición técnica o necesidad de calibración en el dashboard | API | RECHAZADO | Valor 25.0000; calidad LECTURA_VALIDA; semáforo VERDE; batería 77.00 %; RSSI -83.00 dBm; sin indicador de calibración. |
| API-178-07 Ingeniero: la lectura inválida no se trata como operacional normal | API | APROBADO | Criterio verificado en el RUN. |
| PRE-UI-01 Productor: la UI recibe el dashboard real del RUN | UI | APROBADO | Criterio verificado en el RUN. |
| UI-178-01 Productor: la tarjeta de S2 es visible | UI | APROBADO | Criterio verificado en el RUN. |
| UI-178-02 Productor: ERROR_CALIBRACION no se muestra como lectura operativa | UI | APROBADO | Criterio verificado en el RUN. |
| UI-178-03 Productor: sin información técnica (batería %, dBm) | UI | APROBADO | Criterio verificado en el RUN. |
| PRE-UI-01 Ingeniero: la UI recibe el dashboard real del RUN | UI | APROBADO | Criterio verificado en el RUN. |
| UI-178-04 Ingeniero: la tarjeta de S2 es visible | UI | APROBADO | Criterio verificado en el RUN. |
| UI-178-05 Ingeniero: el detalle muestra ERROR_CALIBRACION / requiere calibración | UI | RECHAZADO | Detalle con lectura válida y «Normal», batería y señal; no indica necesidad de calibración. |

Evidencia: [resultado.json](resultado.json), [newman/newman-TC-M03-G87.html](newman/newman-TC-M03-G87.html), [newman/newman-TC-M03-G87.json](newman/newman-TC-M03-G87.json), [cypress/g87.cy.js/TC-M03-178_ingeniero_S2.png](cypress/g87.cy.js/TC-M03-178_ingeniero_S2.png), [cypress/g87.cy.js/TC-M03-178_productor_S2.png](cypress/g87.cy.js/TC-M03-178_productor_S2.png).

## Incidencias funcionales

### REF-G87-01 — El dashboard del Productor no muestra la lectura fuera de rango: el sensor aparece en verde como Normal

**ID:** provisional; no es un ticket.
**Caso y requisito afectado:** TC-M03-177. «La lectura FUERA_DE_RANGO no se utiliza como lectura operativa activa; el dashboard conserva la última LECTURA_VALIDA como referencia, y la anomalía permanece visible mediante un indicador claro (ROJO/ícono), sin ocultarse ni descartarse.»
**Descripción:** El Productor ve la última lectura válida, pero no recibe una señal visual de la lectura posterior fuera de rango.
**Pasos para reproducir:**
1. Usar el RUN RUN-G87-V1-20261023-145303: sensor 552, dispositivo 357, área 349, umbral 15–30 °C.
2. Enviar en orden 23, 24 y 25 °C como LECTURA_VALIDA; después 31 °C como FUERA_DE_RANGO.
3. Consultar GET /iot/monitoreo/dashboard y abrir Monitoreo como Productor; ver la tarjeta del sensor y el indicador de anomalía.
**Resultado esperado:** La lectura FUERA_DE_RANGO no se utiliza como lectura operativa activa; el dashboard conserva la última LECTURA_VALIDA como referencia, y la anomalía permanece visible mediante un indicador claro (ROJO/ícono), sin ocultarse ni descartarse.
**Resultado obtenido:** API: valor 25.0000 °C, estado_calidad LECTURA_VALIDA, estado_semaforo VERDE, id_alerta ninguna. UI: tarjeta verde «Normal», sin ROJO ni ícono. Captura: [cypress/g87.cy.js/TC-M03-177_productor_S1.png](cypress/g87.cy.js/TC-M03-177_productor_S1.png).
**Evidencia:** [resultado.json](resultado.json); [newman/newman-TC-M03-G87.json](newman/newman-TC-M03-G87.json); [newman/newman-TC-M03-G87.html](newman/newman-TC-M03-G87.html); [cypress/g87.cy.js/TC-M03-177_productor_S1.png](cypress/g87.cy.js/TC-M03-177_productor_S1.png).
**Impacto para el usuario:** El Productor puede pasar por alto una temperatura anómala porque el sensor parece normal.
**Severidad:** MEDIA. El RUN demuestra un fallo funcional parcial en este escenario; el alcance general y la disponibilidad de otras vías de aviso no están determinados.
**Responsable inicial de atención y diagnóstico:** **Desarrollo**. La asignación orienta la investigación; no certifica la causa raíz.
**Fundamento de asignación:** E1: PRE-177-02 APROBADOS; telemetría 116855 FUERA_DE_RANGO. E2: API-177-03 RECHAZADO; ultimo_valor="25.0000", ultima_unidad="°C", ultimo_timestamp_captura="2026-10-23T14:49:10.759000Z", estado_calidad="LECTURA_VALIDA", estado_semaforo="VERDE", id_alerta=null, nivel_bateria_pct=null, calidad_senal_rssi=null. E3: resultado.json; newman/newman-TC-M03-G87.json.
**Certeza:** incumplimiento funcional CONFIRMADO (API y UI); causa raíz NO CONFIRMADA. El código exacto desplegado en TEST no se verificó.
**Causa probable — HIPÓTESIS:** El mecanismo que conserva la última lectura válida como valor operativo podría no transportar por separado el evento posterior FUERA_DE_RANGO hasta el estado que consulta el dashboard. El mecanismo exacto sigue por verificar.
**Puntos concretos de investigación:** Inspeccionar src/telemetry/application/use_cases/monitoreo/obtener_dashboard_use_case.py (_calcular_semaforo_efectivo), src/telemetry/infrastructure/repositories/monitoreo_repository.py y su lectura de modulo3.estados_actuales_sensores; contrastar con el contrato API y la UI. Los archivos y la referencia a la tabla existen en el código local; no se acreditó que esta revisión esté desplegada en TEST. El trigger trg_rf58_01_cache_estado_sensor y la función fn_actualizar_estado_sensor fueron mencionados en la propuesta, pero su definición no se verificó en src/telemetry.
**Verificación a cargo de Desarrollo:** Correlacionar la ingesta FUERA_DE_RANGO con estado persistido, respuesta API y UI; identificar el primer punto causal y la revisión desplegada. Solicitar apoyo a DBA solo si se acredita causalidad SQL; a AIoT o Implementación solo con señales propias de sus componentes.
**Acción correctiva esperada:** Conservar la última lectura válida como referencia operativa y comunicar simultáneamente la anomalía mediante el indicador exigido; reevaluar API/UI solo con autorización QA.

### REF-G87-02 — El Ingeniero no ve que el sensor necesita calibración: aparece como Normal

**ID:** provisional; no es un ticket.
**Caso y requisito afectado:** TC-M03-178. «Productor: ERROR_CALIBRACION no se presenta como lectura operativa ni genera alerta operativa, sin exponer información técnica reservada al Ingeniero. Ingeniero de Campo: identifica el sensor con condición de error técnico y visualiza el detalle necesario para reconocer que requiere calibración. El sensor permanece visible y la lectura inválida no se trata como operacional normal.»
**Descripción:** El Ingeniero ve la última lectura válida anterior del sensor 77 (25.0000 °C, 2026-10-21T19:58:32.541708Z), pero las dos lecturas nuevas ERROR_CALIBRACION no aparecen y el dashboard no comunica la necesidad de calibración.
**Pasos para reproducir:**
1. Usar el RUN RUN-G87-V1-20261023-145303: sensor 77, dispositivo 266, área 349, sin calibración.
2. Enviar en orden 21.7 y 22.3 °C como ERROR_CALIBRACION.
3. Consultar GET /iot/monitoreo/dashboard y abrir Monitoreo como Ingeniero de Campo; ver la tarjeta del sensor y su detalle.
**Resultado esperado:** Productor: ERROR_CALIBRACION no se presenta como lectura operativa ni genera alerta operativa, sin exponer información técnica reservada al Ingeniero. Ingeniero de Campo: identifica el sensor con condición de error técnico y visualiza el detalle necesario para reconocer que requiere calibración. El sensor permanece visible y la lectura inválida no se trata como operacional normal.
**Resultado obtenido:** API: valor 25.0000 °C, estado_calidad LECTURA_VALIDA, estado_semaforo VERDE, id_alerta ninguna, batería 77.00 %, RSSI -83.00 dBm; es la última lectura válida anterior del sensor 77 (2026-10-21T19:58:32.541708Z). Las lecturas nuevas 21.7 y 22.3 °C ERROR_CALIBRACION no aparecen en la vista. UI: tarjeta verde «Normal»; el detalle textual tampoco menciona calibración. Captura: [cypress/g87.cy.js/TC-M03-178_ingeniero_S2.png](cypress/g87.cy.js/TC-M03-178_ingeniero_S2.png).
**Evidencia:** [resultado.json](resultado.json); [newman/newman-TC-M03-G87.json](newman/newman-TC-M03-G87.json); [newman/newman-TC-M03-G87.html](newman/newman-TC-M03-G87.html); [cypress/g87.cy.js/TC-M03-178_ingeniero_S2.png](cypress/g87.cy.js/TC-M03-178_ingeniero_S2.png).
**Impacto para el usuario:** El Ingeniero no puede reconocer en esa vista que debe calibrar el sensor.
**Severidad:** MEDIA. El RUN demuestra un fallo funcional parcial en este escenario; el alcance general y la disponibilidad de otras vías de aviso no están determinados.
**Responsable inicial de atención y diagnóstico:** **Desarrollo**. La asignación orienta la investigación; no certifica la causa raíz.
**Fundamento de asignación:** E1: PRE-178-01 APROBADOS; telemetría 116856 ERROR_CALIBRACION, 116857 ERROR_CALIBRACION. E2: API-178-06 RECHAZADO; ultimo_valor="25.0000", estado_calidad="LECTURA_VALIDA", estado_semaforo="VERDE", id_alerta=null, nivel_bateria_pct="77.00", calidad_senal_rssi="-83.00". E3: resultado.json; newman/newman-TC-M03-G87.json.
**Certeza:** incumplimiento funcional CONFIRMADO (API y UI); causa raíz NO CONFIRMADA. El código exacto desplegado en TEST no se verificó.
**Causa probable — HIPÓTESIS:** La selección correcta de la última lectura válida como valor operativo podría no estar acompañada de un estado técnico independiente que informe al Ingeniero de los eventos posteriores ERROR_CALIBRACION. El mecanismo exacto sigue por verificar.
**Puntos concretos de investigación:** Inspeccionar la proyección de estado_calidad en modulo3.estados_actuales_sensores, src/telemetry/infrastructure/repositories/monitoreo_repository.py, src/telemetry/application/use_cases/monitoreo/obtener_dashboard_use_case.py y el contrato por rol. Los archivos y la referencia a la tabla existen en el código local; no se acreditó que esta revisión esté desplegada en TEST. La definición del trigger o función de caché citados en la propuesta no se verificó en src/telemetry.
**Verificación a cargo de Desarrollo:** Correlacionar las ingestas ERROR_CALIBRACION con el registro, estado actual, respuesta API y detalle del Ingeniero; ubicar dónde se pierde la condición técnica y verificar la revisión desplegada. Solicitar apoyo a DBA solo si se acredita causalidad SQL; a AIoT o Implementación solo con señales propias de sus componentes.
**Acción correctiva esperada:** Conservar la última lectura válida sin presentar como normal la condición técnica del sensor ante el Ingeniero; indicar la necesidad de calibración y reevaluar ambos roles solo con autorización QA.


## Clasificación de bloqueos y discrepancias

Sin comprobaciones bloqueadas o incompletas.

## Problemas de automatización QA

Ninguno.

## Análisis de fallos

**Hechos confirmados:** 4 comprobaciones funcionales fallidas, agrupadas en 2 incidencias. TC-M03-177: ingesta 116855 clasificada FUERA_DE_RANGO; TC-M03-178: ingestas 116856 y 116857 clasificadas ERROR_CALIBRACION. Primer punto comprobado de discrepancia: TC-M03-177: API (API-177-03); TC-M03-178: API (API-178-06). TC-M03-168 aprobó la conservación de la última lectura válida; debe preservarse ese comportamiento.

**Diagnóstico preliminar y asignación:** TC-M03-177: Desarrollo; TC-M03-178: Desarrollo. La causa raíz NO está confirmada. Los puntos de investigación específicos se indican en cada incidencia y provienen de QA_PROPUESTAS_G87/TC-M03-G87_resultado_PROPUESTA.md, contrastado con resultado.json del RUN-G87-V1-20261023-145303 y código local de src/telemetry; revisión desplegada en TEST no acreditada. El código local no está acreditado como desplegado en TEST.

**Responsable de confirmar la causa:** el equipo inicial debe contrastar la revisión desplegada, la ingesta, persistencia, API y UI. Apoyos de AIoT, DBA o Implementación requieren señales propias de sus componentes; cualquier reasignación debe registrar evidencia y motivo.

## Herramientas, evidencias y rollback

Newman: 9 solicitudes, 37 aserciones, 2 fallidas. Cypress: 11 pruebas ejecutadas, 11 comprobaciones registradas.
Archivos existentes: [resultado.json](resultado.json), [newman/newman-TC-M03-G87.html](newman/newman-TC-M03-G87.html), [newman/newman-TC-M03-G87.json](newman/newman-TC-M03-G87.json), [cypress/g87.cy.js/TC-M03-177_productor_S1.png](cypress/g87.cy.js/TC-M03-177_productor_S1.png), [cypress/g87.cy.js/TC-M03-178_ingeniero_S2.png](cypress/g87.cy.js/TC-M03-178_ingeniero_S2.png), [cypress/g87.cy.js/TC-M03-178_productor_S2.png](cypress/g87.cy.js/TC-M03-178_productor_S2.png).
Cierre RUN HTTP 200; rollback verificado por API e historial; historial de 2 sensores; sesiones HTTP 200, 200, 200, 200, 200.
El marcador histórico run-pendiente.json conserva run_id G87-V1-20261023-145303 y estado CIERRE_INTENTADO. Su formato no coincide con el cierre y rollback verificados en resultado.json; se preserva intacto como evidencia histórica.

## Conclusión y acciones

RECHAZADO; oficialidad confirmada. Asignar a Desarrollo la atención inicial de REF-G87-01 (TC-M03-177); Asignar a Desarrollo la atención inicial de REF-G87-02 (TC-M03-178). El equipo inicial debe confirmar el punto causal y proponer la corrección sin alterar los veredictos históricos. Nueva evaluación solo con autorización QA. Cierre RUN HTTP 200; rollback verificado por API e historial.

## Anexo técnico — mensajes originales de las herramientas

Los mensajes siguientes se conservan para trazabilidad; los campos JSON se recortan a lo observado en la comprobación.

### TC-M03-177 API-177-03 (API)

```text
{"ultimo_valor":"25.0000","ultima_unidad":"°C","ultimo_timestamp_captura":"2026-10-23T14:49:10.759000Z","estado_calidad":"LECTURA_VALIDA","estado_semaforo":"VERDE","id_alerta":null,"nivel_bateria_pct":null,"calidad_senal_rssi":null,"calidad_senal_snr":null}: expected false to deeply equal true
```

### TC-M03-178 API-178-06 (API)

```text
{"ultimo_valor":"25.0000","estado_calidad":"LECTURA_VALIDA","estado_semaforo":"VERDE","id_alerta":null,"nivel_bateria_pct":"77.00","calidad_senal_rssi":"-83.00"}: expected false to deeply equal true
```

### TC-M03-177 UI-177-03 (UI)

```text
AssertionError: semáforo ROJO con ícono visible: expected undefined to exist
```

### TC-M03-178 UI-178-05 (UI)

```text
AssertionError: detalle="Detalle del sensor · QA58 A1-S02 G87-2 valor 25 y fuera de rango25.0000°CNormalVariable medidaTemperatura AmbientalCategoríaAMBIENTALEstado de calidadLECTURA_VALIDAEstado de desviación—ConectividadACTIVOBatería77.00%Señal LoRaWAN (RSSI)-83.00 dBmSNR4.50 dBTendencia—Última lectura02:58:32 p. m.Sin reporte—Unidad productivaÁrea QA M03 G87FincaFinca Prueba AlfaAlerta activa asociada—Dispositivo IoT#266": expected false to equal true
```
