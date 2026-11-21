# REEVALUACIÓN V2 — TC-M03-G87 — APROBADO

## Identificación

SIGAB/SGPMP; módulo 3; RF-58; TC-M03-G87; TC-M03-168, TC-M03-177, TC-M03-178.
Responsable QA de la matriz: Juan Esteban.
RUN RUN-G87-V2-20261030-150450; V2; intento 11; operación REINTENTAR; ambiente TEST; autorización AUT-G87-V2-R4-20261030.
Inicio 2026-10-30T15:04:50.404Z; fin 2026-10-30T15:05:33.144Z. Rama local qa/juan-esteban-m03-reevaluacion; commit local 15a6042fe9de48d0f231bc36ae830d7dc0ed1120; revisión desplegada en TEST sin acreditar por código local.
Herramientas: Node v22.15.1; Newman sin determinar; Cypress/Chrome 156.0.8078.74.
Identidades de comprobación V2: API (dashboard, Newman, visibilidad y lecturas por rol) y Cypress usan las mismas cuentas UI de Productor e Ingeniero de Campo, con un inicio de sesión por cuenta antes del RUN. La RLS forzada desde 2026-10-29 exige alcance sobre la finca 184; rol y finca se comprueban por /usuarios/me. No se incluyen correos.

## Resumen de veredictos

Aprobados 3; rechazados 0; bloqueados 0; ERROR_QA 0; NO_CONCLUYENTE 0; no ejecutados 0.
Veredicto grupal APROBADO; estado CONCLUIDA; Oficialidad: OFICIAL.

| Caso | Veredicto | V1 → V2 | Motivo V2 |
| --- | --- | --- | --- |
| TC-M03-168 | APROBADO | APROBADO → APROBADO | Todas las comprobaciones verificadas. |
| TC-M03-177 | APROBADO | RECHAZADO → APROBADO | Todas las comprobaciones verificadas. |
| TC-M03-178 | APROBADO | RECHAZADO → APROBADO | Todas las comprobaciones verificadas. |

## Alcance de reevaluación

Vsin determinar → V2; casos TC-M03-168, TC-M03-177, TC-M03-178; motivo correcciones informadas del issue #678 y regresión de TC-M03-168.

## Referencia V1 y correcciones informadas por Desarrollo

V1 oficial: Resultados/RUN-G87-V1-20261023-145303/TC-M03-G87_resultado.md. TC-M03-168 APROBADO; TC-M03-177 RECHAZADO (REF-G87-01); TC-M03-178 RECHAZADO (REF-G87-02).
Comparación de identidad: V1 empleó cuentas API separadas para Productor e Ingeniero. V2 usa las cuentas UI del mismo rol también en API porque las cuentas API V1 no tienen la finca 184 bajo la RLS forzada desde 2026-10-29. Los oráculos y los IDs de comprobación se conservan.
Reporte transmitido por el responsable QA, issue #678: backend PR #793 separó la última lectura válida de la condición reciente y añadió estado_calidad_valor_operativo, timestamp_estado_actual, indicador_anomalia y datos según permiso. Frontend PR #453 adaptó el dashboard, «Última lectura válida», anomalía visible para Productor y «Requiere calibración» para Ingeniero. Su despliegue en TEST se juzga con la respuesta y la UI servidas en este RUN.
Correcciones informadas por el responsable QA: issue #678; backend PR #793; frontend PR #453.
Alcance autorizado: Vsin determinar → V2; comprobar correcciones y regresión de los tres casos.

## Resultado por caso

### TC-M03-168 — Última lectura válida de cada sensor activo, ignorando una lectura posterior FUERA_DE_RANGO

**Resultado V1 → Resultado V2:** APROBADO → APROBADO. Todas las comprobaciones verificadas.
**Esperado:** HTTP 200. Por cada sensor se devuelven ultimo_valor, ultima_unidad y ultimo_timestamp_captura correspondientes a la última lectura LECTURA_VALIDA, no a la posterior inválida.
**Escenario:** Sensor 552, área 349, válidas 23, 24, 25 °C y posterior 31 °C FUERA_DE_RANGO.
**Observado por API pública:** Productor: HTTP 200, finca asignada true, sensor visible true; contrato {"ultimo_valor":"25.0000","ultima_unidad":"°C","ultimo_timestamp_captura":"2026-10-30T15:00:59.659000Z","estado_calidad":"FUERA_DE_RANGO","estado_semaforo":"VERDE","estado_calidad_valor_operativo":"LECTURA_VALIDA","timestamp_estado_actual":"2026-10-30T15:01:59.659000Z","indicador_anomalia":true,"es_valor_operativo":true,"etiqueta_estado":"Lectura fuera de rango","id_alerta":null,"nivel_bateria_pct":null,"calidad_senal_rssi":null,"calidad_senal_snr":null}
**Observado por UI servida:** sin captura real para este caso; UI no requerida o no ejecutada.
**Qué cambió:** se comprobó regresión de valor, unidad y hora.
**Qué falta:** Ninguna comprobación obligatoria del caso; el despliegue exacto sigue sin acreditar por código local.

| Comprobación | Fuente | Estado | Observado |
| --- | --- | --- | --- |
| SETUP Respuesta atendida dentro del RUN (eco X-Test-Run-Id) | API | APROBADO | Petición 168 Lectura válida 1 de S1 con eco del RUN validado. |
| PRE-168-01 Lectura válida 1 aceptada como LECTURA_VALIDA | API | APROBADO | Precondición PRE-168-01 aprobada; ver ingestas y HTTP en resultado.json y Newman. |
| SETUP Respuesta atendida dentro del RUN (eco X-Test-Run-Id) | API | APROBADO | Petición 168 Lectura válida 2 de S1 con eco del RUN validado. |
| PRE-168-01 Lectura válida 2 aceptada como LECTURA_VALIDA | API | APROBADO | Precondición PRE-168-01 aprobada; ver ingestas y HTTP en resultado.json y Newman. |
| SETUP Respuesta atendida dentro del RUN (eco X-Test-Run-Id) | API | APROBADO | Petición 168/177 Lectura válida 3 de S1 (valor 25) con eco del RUN validado. |
| PRE-168-01 Lectura válida 3 aceptada como LECTURA_VALIDA | API | APROBADO | Precondición PRE-168-01 aprobada; ver ingestas y HTTP en resultado.json y Newman. |
| SETUP Respuesta atendida dentro del RUN (eco X-Test-Run-Id) | API | APROBADO | Petición 168/177 Lectura posterior fuera del rango operativo de S1 con eco del RUN validado. |
| PRE-168-02 Lectura posterior clasificada FUERA_DE_RANGO (RF-53) | API | APROBADO | Precondición PRE-168-02 aprobada; ver ingestas y HTTP en resultado.json y Newman. |
| SETUP Respuesta atendida dentro del RUN (eco X-Test-Run-Id) | API | APROBADO | Petición Dashboard del Productor con eco del RUN validado. |
| PRE-168-03 Sesión del Productor vigente (no 401) | API | APROBADO | Precondición PRE-168-03 aprobada; ver ingestas y HTTP en resultado.json y Newman. |
| API-168-01 Dashboard del Productor responde HTTP 200 | API | APROBADO | HTTP 200; {"ultimo_valor":"25.0000","ultima_unidad":"°C","ultimo_timestamp_captura":"2026-10-30T15:00:59.659000Z","estado_calidad":"FUERA_DE_RANGO","estado_semaforo":"VERDE","estado_calidad_valor_operativo":"LECTURA_VALIDA","timestamp_estado_actual":"2026-10-30T15:01:59.659000Z","indicador_anomalia":true,"es_valor_operativo":true,"etiqueta_estado":"Lectura fuera de rango","id_alerta":null,"nivel_bateria_pct":null,"calidad_senal_rssi":null,"calidad_senal_snr":null} |
| API-168-02 El sensor S1 aparece en el dashboard | API | APROBADO | HTTP 200; {"ultimo_valor":"25.0000","ultima_unidad":"°C","ultimo_timestamp_captura":"2026-10-30T15:00:59.659000Z","estado_calidad":"FUERA_DE_RANGO","estado_semaforo":"VERDE","estado_calidad_valor_operativo":"LECTURA_VALIDA","timestamp_estado_actual":"2026-10-30T15:01:59.659000Z","indicador_anomalia":true,"es_valor_operativo":true,"etiqueta_estado":"Lectura fuera de rango","id_alerta":null,"nivel_bateria_pct":null,"calidad_senal_rssi":null,"calidad_senal_snr":null} |
| API-168-03 ultimo_valor = valor de la última LECTURA_VALIDA | API | APROBADO | HTTP 200; {"ultimo_valor":"25.0000","ultima_unidad":"°C","ultimo_timestamp_captura":"2026-10-30T15:00:59.659000Z","estado_calidad":"FUERA_DE_RANGO","estado_semaforo":"VERDE","estado_calidad_valor_operativo":"LECTURA_VALIDA","timestamp_estado_actual":"2026-10-30T15:01:59.659000Z","indicador_anomalia":true,"es_valor_operativo":true,"etiqueta_estado":"Lectura fuera de rango","id_alerta":null,"nivel_bateria_pct":null,"calidad_senal_rssi":null,"calidad_senal_snr":null} |
| API-168-04 ultima_unidad = unidad de la última LECTURA_VALIDA | API | APROBADO | HTTP 200; {"ultimo_valor":"25.0000","ultima_unidad":"°C","ultimo_timestamp_captura":"2026-10-30T15:00:59.659000Z","estado_calidad":"FUERA_DE_RANGO","estado_semaforo":"VERDE","estado_calidad_valor_operativo":"LECTURA_VALIDA","timestamp_estado_actual":"2026-10-30T15:01:59.659000Z","indicador_anomalia":true,"es_valor_operativo":true,"etiqueta_estado":"Lectura fuera de rango","id_alerta":null,"nivel_bateria_pct":null,"calidad_senal_rssi":null,"calidad_senal_snr":null} |
| API-168-05 ultimo_timestamp_captura = timestamp de la última LECTURA_VALIDA | API | APROBADO | HTTP 200; {"ultimo_valor":"25.0000","ultima_unidad":"°C","ultimo_timestamp_captura":"2026-10-30T15:00:59.659000Z","estado_calidad":"FUERA_DE_RANGO","estado_semaforo":"VERDE","estado_calidad_valor_operativo":"LECTURA_VALIDA","timestamp_estado_actual":"2026-10-30T15:01:59.659000Z","indicador_anomalia":true,"es_valor_operativo":true,"etiqueta_estado":"Lectura fuera de rango","id_alerta":null,"nivel_bateria_pct":null,"calidad_senal_rssi":null,"calidad_senal_snr":null} |

Evidencias del caso: [resultado.json](resultado.json), [newman/newman-TC-M03-G87.html](newman/newman-TC-M03-G87.html), [newman/newman-TC-M03-G87.json](newman/newman-TC-M03-G87.json).

### TC-M03-177 — La lectura FUERA_DE_RANGO no es valor operativo del Productor y la anomalía sigue visible

**Resultado V1 → Resultado V2:** RECHAZADO → APROBADO. Todas las comprobaciones verificadas.
**Esperado:** La lectura FUERA_DE_RANGO no se utiliza como lectura operativa activa; el dashboard conserva la última LECTURA_VALIDA como referencia, y la anomalía permanece visible mediante un indicador claro (ROJO/ícono), sin ocultarse ni descartarse.
**Escenario:** Sensor 552, área 349, válidas 23, 24, 25 °C y posterior 31 °C FUERA_DE_RANGO.
**Observado por API pública:** Productor: HTTP 200, finca asignada true, sensor visible true; contrato {"ultimo_valor":"25.0000","ultima_unidad":"°C","ultimo_timestamp_captura":"2026-10-30T15:00:59.659000Z","estado_calidad":"FUERA_DE_RANGO","estado_semaforo":"VERDE","estado_calidad_valor_operativo":"LECTURA_VALIDA","timestamp_estado_actual":"2026-10-30T15:01:59.659000Z","indicador_anomalia":true,"es_valor_operativo":true,"etiqueta_estado":"Lectura fuera de rango","id_alerta":null,"nivel_bateria_pct":null,"calidad_senal_rssi":null,"calidad_senal_snr":null}
**Observado por UI servida:** [cypress/g87.cy.js/TC-M03-177_productor_S1.png](cypress/g87.cy.js/TC-M03-177_productor_S1.png), [cypress/g87.cy.js/UI-177-02_valor_25.png](cypress/g87.cy.js/UI-177-02_valor_25.png), [cypress/g87.cy.js/UI-177-03_anomalia.png](cypress/g87.cy.js/UI-177-03_anomalia.png); UI-177-01=APROBADO, UI-177-02=APROBADO, UI-177-03=APROBADO.
**Qué cambió:** REF-G87-01 CORREGIDA.
**Qué falta:** Ninguna comprobación obligatoria del caso; el despliegue exacto sigue sin acreditar por código local.

| Comprobación | Fuente | Estado | Observado |
| --- | --- | --- | --- |
| SETUP Respuesta atendida dentro del RUN (eco X-Test-Run-Id) | API | APROBADO | Petición 168 Lectura válida 1 de S1 con eco del RUN validado. |
| SETUP Respuesta atendida dentro del RUN (eco X-Test-Run-Id) | API | APROBADO | Petición 168 Lectura válida 2 de S1 con eco del RUN validado. |
| SETUP Respuesta atendida dentro del RUN (eco X-Test-Run-Id) | API | APROBADO | Petición 168/177 Lectura válida 3 de S1 (valor 25) con eco del RUN validado. |
| PRE-177-01 Lectura 25 aceptada como LECTURA_VALIDA | API | APROBADO | Precondición PRE-177-01 aprobada; ver ingestas y HTTP en resultado.json y Newman. |
| SETUP Respuesta atendida dentro del RUN (eco X-Test-Run-Id) | API | APROBADO | Petición 168/177 Lectura posterior fuera del rango operativo de S1 con eco del RUN validado. |
| PRE-177-02 Lectura posterior clasificada FUERA_DE_RANGO (RF-53) | API | APROBADO | Precondición PRE-177-02 aprobada; ver ingestas y HTTP en resultado.json y Newman. |
| SETUP Respuesta atendida dentro del RUN (eco X-Test-Run-Id) | API | APROBADO | Petición Dashboard del Productor con eco del RUN validado. |
| PRE-177-03 Sesión del Productor vigente (no 401) | API | APROBADO | Precondición PRE-177-03 aprobada; ver ingestas y HTTP en resultado.json y Newman. |
| API-177-01 Dashboard HTTP 200 y el sensor S1 no se oculta | API | APROBADO | HTTP 200; {"ultimo_valor":"25.0000","ultima_unidad":"°C","ultimo_timestamp_captura":"2026-10-30T15:00:59.659000Z","estado_calidad":"FUERA_DE_RANGO","estado_semaforo":"VERDE","estado_calidad_valor_operativo":"LECTURA_VALIDA","timestamp_estado_actual":"2026-10-30T15:01:59.659000Z","indicador_anomalia":true,"es_valor_operativo":true,"etiqueta_estado":"Lectura fuera de rango","id_alerta":null,"nivel_bateria_pct":null,"calidad_senal_rssi":null,"calidad_senal_snr":null} |
| API-177-02 La lectura FUERA_DE_RANGO no reemplaza el valor operativo 25 | API | APROBADO | HTTP 200; {"ultimo_valor":"25.0000","ultima_unidad":"°C","ultimo_timestamp_captura":"2026-10-30T15:00:59.659000Z","estado_calidad":"FUERA_DE_RANGO","estado_semaforo":"VERDE","estado_calidad_valor_operativo":"LECTURA_VALIDA","timestamp_estado_actual":"2026-10-30T15:01:59.659000Z","indicador_anomalia":true,"es_valor_operativo":true,"etiqueta_estado":"Lectura fuera de rango","id_alerta":null,"nivel_bateria_pct":null,"calidad_senal_rssi":null,"calidad_senal_snr":null} |
| API-177-03 La anomalía permanece visible (estado_calidad, indicador o semáforo) | API | APROBADO | HTTP 200; {"ultimo_valor":"25.0000","ultima_unidad":"°C","ultimo_timestamp_captura":"2026-10-30T15:00:59.659000Z","estado_calidad":"FUERA_DE_RANGO","estado_semaforo":"VERDE","estado_calidad_valor_operativo":"LECTURA_VALIDA","timestamp_estado_actual":"2026-10-30T15:01:59.659000Z","indicador_anomalia":true,"es_valor_operativo":true,"etiqueta_estado":"Lectura fuera de rango","id_alerta":null,"nivel_bateria_pct":null,"calidad_senal_rssi":null,"calidad_senal_snr":null} |
| PRE-UI-01 Productor: la UI recibe el dashboard real del RUN | UI | APROBADO | Precondición PRE-UI-01 aprobada; ver ingestas y HTTP en resultado.json y Newman. |
| UI-177-01 Productor: la tarjeta de S1 es visible | UI | APROBADO | Aserción Cypress APROBADO; TC-M03-177_productor_S1.png, UI-177-02_valor_25.png, UI-177-03_anomalia.png. |
| UI-177-02 Productor: S1 muestra 25 como valor operativo, no el anómalo | UI | APROBADO | Aserción Cypress APROBADO; TC-M03-177_productor_S1.png, UI-177-02_valor_25.png, UI-177-03_anomalia.png. |
| UI-177-03 Productor: la anomalía de S1 es visible (ROJO / ícono) | UI | APROBADO | Aserción Cypress APROBADO; TC-M03-177_productor_S1.png, UI-177-02_valor_25.png, UI-177-03_anomalia.png. |

Evidencias del caso: [resultado.json](resultado.json), [newman/newman-TC-M03-G87.html](newman/newman-TC-M03-G87.html), [newman/newman-TC-M03-G87.json](newman/newman-TC-M03-G87.json), [cypress/g87.cy.js/TC-M03-177_productor_S1.png](cypress/g87.cy.js/TC-M03-177_productor_S1.png), [cypress/g87.cy.js/UI-177-02_valor_25.png](cypress/g87.cy.js/UI-177-02_valor_25.png), [cypress/g87.cy.js/UI-177-03_anomalia.png](cypress/g87.cy.js/UI-177-03_anomalia.png).

### TC-M03-178 — Presentación de ERROR_CALIBRACION diferenciada entre Productor e Ingeniero de Campo

**Resultado V1 → Resultado V2:** RECHAZADO → APROBADO. Todas las comprobaciones verificadas.
**Esperado:** Productor: ERROR_CALIBRACION no se presenta como lectura operativa ni genera alerta operativa, sin exponer información técnica reservada al Ingeniero. Ingeniero de Campo: identifica el sensor con condición de error técnico y visualiza el detalle necesario para reconocer que requiere calibración. El sensor permanece visible y la lectura inválida no se trata como operacional normal.
**Escenario:** Sensor 77, área 349, sin calibración; 21.7 y 22.3 °C ERROR_CALIBRACION.
**Observado por API pública:** Productor: HTTP 200, finca asignada true, sensor visible true; contrato {"ultimo_valor":"25.0000","ultima_unidad":"°C","ultimo_timestamp_captura":"2026-10-21T19:58:32.541708Z","estado_calidad":null,"estado_semaforo":"VERDE","estado_calidad_valor_operativo":"LECTURA_VALIDA","timestamp_estado_actual":"2026-10-30T14:59:59.659000Z","indicador_anomalia":true,"es_valor_operativo":true,"etiqueta_estado":"En revisión técnica","id_alerta":null,"nivel_bateria_pct":null,"calidad_senal_rssi":null,"calidad_senal_snr":null} Ingeniero: HTTP 200, finca asignada true, sensor visible true; contrato {"ultimo_valor":"25.0000","ultima_unidad":"°C","ultimo_timestamp_captura":"2026-10-21T19:58:32.541708Z","estado_calidad":"ERROR_CALIBRACION","estado_semaforo":"VERDE","estado_calidad_valor_operativo":"LECTURA_VALIDA","timestamp_estado_actual":"2026-10-30T14:59:59.659000Z","indicador_anomalia":true,"es_valor_operativo":true,"etiqueta_estado":"Requiere calibración","id_alerta":null,"nivel_bateria_pct":"77.00","calidad_senal_rssi":"-83.00","calidad_senal_snr":"4.50"}
**Observado por UI servida:** [cypress/g87.cy.js/TC-M03-178_ingeniero_detalle_S2.png](cypress/g87.cy.js/TC-M03-178_ingeniero_detalle_S2.png), [cypress/g87.cy.js/TC-M03-178_ingeniero_S2.png](cypress/g87.cy.js/TC-M03-178_ingeniero_S2.png), [cypress/g87.cy.js/TC-M03-178_productor_S2.png](cypress/g87.cy.js/TC-M03-178_productor_S2.png), [cypress/g87.cy.js/UI-178-02_sin_valor_error.png](cypress/g87.cy.js/UI-178-02_sin_valor_error.png), [cypress/g87.cy.js/UI-178-03_productor_detalle.png](cypress/g87.cy.js/UI-178-03_productor_detalle.png); UI-178-01=APROBADO, UI-178-02=APROBADO, UI-178-03=APROBADO, UI-178-04=APROBADO, UI-178-05=APROBADO.
**Qué cambió:** REF-G87-02 CORREGIDA.
**Qué falta:** Ninguna comprobación obligatoria del caso; el despliegue exacto sigue sin acreditar por código local.

| Comprobación | Fuente | Estado | Observado |
| --- | --- | --- | --- |
| SETUP Respuesta atendida dentro del RUN (eco X-Test-Run-Id) | API | APROBADO | Petición SETUP Reasignar S2 al área del escenario con eco del RUN validado. |
| SETUP S2 asociado al área del escenario (RF-22) | API | APROBADO | Petición SETUP Reasignar S2 al área del escenario con eco del RUN validado. |
| SETUP Respuesta atendida dentro del RUN (eco X-Test-Run-Id) | API | APROBADO | Petición 178 Lectura 1 de S2 (sin calibración) con eco del RUN validado. |
| PRE-178-01 Lectura 1 de S2 clasificada ERROR_CALIBRACION | API | APROBADO | Precondición PRE-178-01 aprobada; ver ingestas y HTTP en resultado.json y Newman. |
| SETUP Respuesta atendida dentro del RUN (eco X-Test-Run-Id) | API | APROBADO | Petición 178 Lectura 2 de S2 (sin calibración) con eco del RUN validado. |
| PRE-178-01 Lectura 2 de S2 clasificada ERROR_CALIBRACION | API | APROBADO | Precondición PRE-178-01 aprobada; ver ingestas y HTTP en resultado.json y Newman. |
| SETUP Respuesta atendida dentro del RUN (eco X-Test-Run-Id) | API | APROBADO | Petición Dashboard del Productor con eco del RUN validado. |
| PRE-178-02 Sesión del Productor vigente (no 401) | API | APROBADO | Precondición PRE-178-02 aprobada; ver ingestas y HTTP en resultado.json y Newman. |
| API-178-01 Productor: HTTP 200 y el sensor S2 permanece visible | API | APROBADO | HTTP 200; {"ultimo_valor":"25.0000","ultima_unidad":"°C","ultimo_timestamp_captura":"2026-10-21T19:58:32.541708Z","estado_calidad":null,"estado_semaforo":"VERDE","estado_calidad_valor_operativo":"LECTURA_VALIDA","timestamp_estado_actual":"2026-10-30T14:59:59.659000Z","indicador_anomalia":true,"es_valor_operativo":true,"etiqueta_estado":"En revisión técnica","id_alerta":null,"nivel_bateria_pct":null,"calidad_senal_rssi":null,"calidad_senal_snr":null} |
| API-178-02 Productor: ERROR_CALIBRACION no se presenta como lectura operativa | API | APROBADO | HTTP 200; {"ultimo_valor":"25.0000","ultima_unidad":"°C","ultimo_timestamp_captura":"2026-10-21T19:58:32.541708Z","estado_calidad":null,"estado_semaforo":"VERDE","estado_calidad_valor_operativo":"LECTURA_VALIDA","timestamp_estado_actual":"2026-10-30T14:59:59.659000Z","indicador_anomalia":true,"es_valor_operativo":true,"etiqueta_estado":"En revisión técnica","id_alerta":null,"nivel_bateria_pct":null,"calidad_senal_rssi":null,"calidad_senal_snr":null} |
| API-178-03 Productor: S2 no genera alerta operativa | API | APROBADO | HTTP 200; {"ultimo_valor":"25.0000","ultima_unidad":"°C","ultimo_timestamp_captura":"2026-10-21T19:58:32.541708Z","estado_calidad":null,"estado_semaforo":"VERDE","estado_calidad_valor_operativo":"LECTURA_VALIDA","timestamp_estado_actual":"2026-10-30T14:59:59.659000Z","indicador_anomalia":true,"es_valor_operativo":true,"etiqueta_estado":"En revisión técnica","id_alerta":null,"nivel_bateria_pct":null,"calidad_senal_rssi":null,"calidad_senal_snr":null} |
| API-178-04 Productor: no recibe información técnica ni diagnóstico reservado | API | APROBADO | HTTP 200; {"ultimo_valor":"25.0000","ultima_unidad":"°C","ultimo_timestamp_captura":"2026-10-21T19:58:32.541708Z","estado_calidad":null,"estado_semaforo":"VERDE","estado_calidad_valor_operativo":"LECTURA_VALIDA","timestamp_estado_actual":"2026-10-30T14:59:59.659000Z","indicador_anomalia":true,"es_valor_operativo":true,"etiqueta_estado":"En revisión técnica","id_alerta":null,"nivel_bateria_pct":null,"calidad_senal_rssi":null,"calidad_senal_snr":null} |
| SETUP Respuesta atendida dentro del RUN (eco X-Test-Run-Id) | API | APROBADO | Petición Dashboard del Ingeniero de Campo con eco del RUN validado. |
| PRE-178-03 Sesión del Ingeniero vigente (no 401) | API | APROBADO | Precondición PRE-178-03 aprobada; ver ingestas y HTTP en resultado.json y Newman. |
| API-178-05 Ingeniero: HTTP 200 y el sensor S2 permanece visible | API | APROBADO | HTTP 200; {"ultimo_valor":"25.0000","ultima_unidad":"°C","ultimo_timestamp_captura":"2026-10-21T19:58:32.541708Z","estado_calidad":"ERROR_CALIBRACION","estado_semaforo":"VERDE","estado_calidad_valor_operativo":"LECTURA_VALIDA","timestamp_estado_actual":"2026-10-30T14:59:59.659000Z","indicador_anomalia":true,"es_valor_operativo":true,"etiqueta_estado":"Requiere calibración","id_alerta":null,"nivel_bateria_pct":"77.00","calidad_senal_rssi":"-83.00","calidad_senal_snr":"4.50"} |
| API-178-06 Ingeniero: identifica condición técnica o necesidad de calibración en el dashboard | API | APROBADO | HTTP 200; {"ultimo_valor":"25.0000","ultima_unidad":"°C","ultimo_timestamp_captura":"2026-10-21T19:58:32.541708Z","estado_calidad":"ERROR_CALIBRACION","estado_semaforo":"VERDE","estado_calidad_valor_operativo":"LECTURA_VALIDA","timestamp_estado_actual":"2026-10-30T14:59:59.659000Z","indicador_anomalia":true,"es_valor_operativo":true,"etiqueta_estado":"Requiere calibración","id_alerta":null,"nivel_bateria_pct":"77.00","calidad_senal_rssi":"-83.00","calidad_senal_snr":"4.50"} |
| API-178-07 Ingeniero: la lectura inválida no se trata como operacional normal | API | APROBADO | HTTP 200; {"ultimo_valor":"25.0000","ultima_unidad":"°C","ultimo_timestamp_captura":"2026-10-21T19:58:32.541708Z","estado_calidad":"ERROR_CALIBRACION","estado_semaforo":"VERDE","estado_calidad_valor_operativo":"LECTURA_VALIDA","timestamp_estado_actual":"2026-10-30T14:59:59.659000Z","indicador_anomalia":true,"es_valor_operativo":true,"etiqueta_estado":"Requiere calibración","id_alerta":null,"nivel_bateria_pct":"77.00","calidad_senal_rssi":"-83.00","calidad_senal_snr":"4.50"} |
| PRE-UI-01 Productor: la UI recibe el dashboard real del RUN | UI | APROBADO | Precondición PRE-UI-01 aprobada; ver ingestas y HTTP en resultado.json y Newman. |
| UI-178-01 Productor: la tarjeta de S2 es visible | UI | APROBADO | Aserción Cypress APROBADO; TC-M03-178_ingeniero_detalle_S2.png, TC-M03-178_ingeniero_S2.png, TC-M03-178_productor_S2.png, UI-178-02_sin_valor_error.png, UI-178-03_productor_detalle.png. |
| UI-178-02 Productor: ERROR_CALIBRACION no se muestra como lectura operativa | UI | APROBADO | Aserción Cypress APROBADO; TC-M03-178_ingeniero_detalle_S2.png, TC-M03-178_ingeniero_S2.png, TC-M03-178_productor_S2.png, UI-178-02_sin_valor_error.png, UI-178-03_productor_detalle.png. |
| UI-178-03 Productor: sin información técnica (batería %, dBm) | UI | APROBADO | Aserción Cypress APROBADO; TC-M03-178_ingeniero_detalle_S2.png, TC-M03-178_ingeniero_S2.png, TC-M03-178_productor_S2.png, UI-178-02_sin_valor_error.png, UI-178-03_productor_detalle.png. |
| PRE-UI-01 Ingeniero: la UI recibe el dashboard real del RUN | UI | APROBADO | Precondición PRE-UI-01 aprobada; ver ingestas y HTTP en resultado.json y Newman. |
| UI-178-04 Ingeniero: la tarjeta de S2 es visible | UI | APROBADO | Aserción Cypress APROBADO; TC-M03-178_ingeniero_detalle_S2.png, TC-M03-178_ingeniero_S2.png, TC-M03-178_productor_S2.png, UI-178-02_sin_valor_error.png, UI-178-03_productor_detalle.png. |
| UI-178-05 Ingeniero: el detalle muestra ERROR_CALIBRACION / requiere calibración | UI | APROBADO | Aserción Cypress APROBADO; TC-M03-178_ingeniero_detalle_S2.png, TC-M03-178_ingeniero_S2.png, TC-M03-178_productor_S2.png, UI-178-02_sin_valor_error.png, UI-178-03_productor_detalle.png. |

Evidencias del caso: [resultado.json](resultado.json), [newman/newman-TC-M03-G87.html](newman/newman-TC-M03-G87.html), [newman/newman-TC-M03-G87.json](newman/newman-TC-M03-G87.json), [cypress/g87.cy.js/TC-M03-178_ingeniero_detalle_S2.png](cypress/g87.cy.js/TC-M03-178_ingeniero_detalle_S2.png), [cypress/g87.cy.js/TC-M03-178_ingeniero_S2.png](cypress/g87.cy.js/TC-M03-178_ingeniero_S2.png), [cypress/g87.cy.js/TC-M03-178_productor_S2.png](cypress/g87.cy.js/TC-M03-178_productor_S2.png), [cypress/g87.cy.js/UI-178-02_sin_valor_error.png](cypress/g87.cy.js/UI-178-02_sin_valor_error.png), [cypress/g87.cy.js/UI-178-03_productor_detalle.png](cypress/g87.cy.js/UI-178-03_productor_detalle.png).

## Estado de incidencias V1

REF-G87-01: CORREGIDA. API-177-03 y UI-177-03 aprobaron.
REF-G87-02: CORREGIDA. API-178-06 y UI-178-05 aprobaron.

## Incidencias funcionales nuevas

Ninguna nueva confirmada.

## Bloqueos, automatización y análisis de causas

Comprobaciones no concluyentes: ninguna.
Problemas técnicos: ninguno registrado. Los fallos de herramienta o de alcance de cuenta no prueban un defecto funcional.
La causa raíz de cualquier discrepancia funcional requiere contraste del despliegue TEST, la ingesta, la respuesta pública y la UI servida; la revisión local no acredita el despliegue.

## Cierre, rollback y evidencias

Newman 9 solicitudes, 37 aserciones, 0 fallidas; Cypress 11 pruebas.
Archivos reales: [resultado.json](resultado.json), [newman/newman-TC-M03-G87.html](newman/newman-TC-M03-G87.html), [newman/newman-TC-M03-G87.json](newman/newman-TC-M03-G87.json), [cypress/g87.cy.js/eng_PRE-UI-01_area_filtrada.png](cypress/g87.cy.js/eng_PRE-UI-01_area_filtrada.png), [cypress/g87.cy.js/prod_PRE-UI-01_area_filtrada.png](cypress/g87.cy.js/prod_PRE-UI-01_area_filtrada.png), [cypress/g87.cy.js/TC-M03-177_productor_S1.png](cypress/g87.cy.js/TC-M03-177_productor_S1.png), [cypress/g87.cy.js/TC-M03-178_ingeniero_detalle_S2.png](cypress/g87.cy.js/TC-M03-178_ingeniero_detalle_S2.png), [cypress/g87.cy.js/TC-M03-178_ingeniero_S2.png](cypress/g87.cy.js/TC-M03-178_ingeniero_S2.png), [cypress/g87.cy.js/TC-M03-178_productor_S2.png](cypress/g87.cy.js/TC-M03-178_productor_S2.png), [cypress/g87.cy.js/UI-177-02_valor_25.png](cypress/g87.cy.js/UI-177-02_valor_25.png), [cypress/g87.cy.js/UI-177-03_anomalia.png](cypress/g87.cy.js/UI-177-03_anomalia.png), [cypress/g87.cy.js/UI-178-02_sin_valor_error.png](cypress/g87.cy.js/UI-178-02_sin_valor_error.png), [cypress/g87.cy.js/UI-178-03_productor_detalle.png](cypress/g87.cy.js/UI-178-03_productor_detalle.png).
Cierre RUN HTTP 200; rollback verificado por API e historial; sensores con historial 2; sesiones HTTP 200, 200, 200, 200, 200.

## Conclusión y acciones

APROBADO; oficialidad confirmada. Conservar las evidencias y cerrar las referencias V1 solo si el RUN es oficial. 
