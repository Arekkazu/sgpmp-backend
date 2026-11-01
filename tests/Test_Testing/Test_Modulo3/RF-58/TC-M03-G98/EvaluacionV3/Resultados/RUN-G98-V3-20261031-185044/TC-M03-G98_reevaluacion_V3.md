# TC-M03-G98 — APROBADO

## 1. Identificación

Grupo G98; caso TC-M03-191; RF-58/CU04, Salida 2 y CA-11; versión V3; operación REEVALUAR; RUN RUN-G98-V3-20261031-185044; ambiente TEST; autorización AUT-G98-V3-20261031; backend código local consultado; despliegue no verificado; frontend PR #456 informado por Desarrollo; despliegue no verificado; commit TEST no verificado. Node v22.15.1; Newman 6.2.2; Postman y Cypress no ejecutados. Contrato API.

## 2. Resumen de veredictos y comparación V1 → V2 → V3

V1 RUN-G98-V1-20261026-181259: RECHAZADO por panel ausente. V2 RUN-G98-V2-20261031-183417: RECHAZADO por el oráculo temporal anterior; total, orden, tipo, variable y activo ya cumplían. V3 RUN-G98-V3-20261031-185044: **APROBADO** por HTTP 200 con eco, total 3, orden CRITICO → MODERADO → LEVE, campos y vínculo al activo 928; el tiempo cumple la ventana temporal del RUN.

## 3. Detalle por caso y comprobaciones API/UI

### TC-M03-191

**Objetivo:** verificar el total y el orden por severidad del panel de alertas activas, sus datos y el identificador que permite navegar al activo afectado.

**Precondiciones:** «Alertas activas de severidad CRITICO, ALTA y MEDIA sobre distintos sensores de la misma unidad.» La decisión QA aceptó la escala RF-57 CRITICO > MODERADO > LEVE para la terna real. Semilla persistente QA-G98-PANEL: finca 184, área 702, dispositivo 789, sensores 1210/1211/1212, activo biológico 928. Los GET públicos del RUN acreditaron área, activo, sensores y lecturas. Antes de crear las alertas, no había un área visible con tres alertas ACTIVA de severidades distintas en sensores distintos; por eso se crearon tres en el sandbox. Vía CREACION_SANDBOX; las alertas 1388, 1389, 1390 se crearon solo en el sandbox del RUN.

**Pasos:** iniciar sesión; comprobar área, activo, dispositivo, sensores y lecturas; ejecutar el canario E7; crear y verificar las tres alertas en el sandbox; consultar el dashboard por Newman; cotejar total, orden, campos, tiempo y activo; cerrar el RUN y comprobar rollback.

**Entradas:** área 702; alertas 1388, 1389, 1390; inicio del RUN 2026-10-31T18:50:44.192Z.

**Esperado:** «HTTP 200. Se devuelve el total de alertas activas y la lista ordenada por severidad con CRITICO primero, indicando tipo de alerta, variable afectada y tiempo transcurrido, con navegación al detalle del activo biológico afectado.» Orden aceptado por decisión QA: CRITICO > MODERADO > LEVE. Para el tiempo, el oráculo V3 exige un entero dentro de la ventana entre el inicio del RUN menos 120 s y la respuesta, con un minuto de tolerancia por extremo; la fecha de generación no debe superar la respuesta más 60 s.

**Observado:** HTTP 200 con eco del RUN; total 3 y tres alertas ACTIVA del área 702, ordenadas CRITICO → MODERADO → LEVE. Cada fila contiene tipo, variable, tiempo e identificador del activo 928. Los minutos −1 son enteros dentro de la ventana temporal de V3: las alertas se crearon después del inicio del RUN y el reloj de la transacción sandbox quedó fijo. Las fechas de generación van de 2026-10-31T18:50:53.902046Z a 2026-10-31T18:50:54.535007Z; el RUN empezó a las 2026-10-31T18:50:44.192Z.

**Valores observados en Newman:** total 3; 3 filas.

| ID | Severidad | Tipo de alerta | Variable | Valor | Minutos transcurridos | Activo biológico |
| ---: | --- | --- | --- | ---: | ---: | --- |
| 1388 | CRITICO | SINDROME_RESPIRATORIO | NH3 | 50 ppm | -1 | 928 (identificador presente) |
| 1389 | MODERADO | RIESGO_HIDRICO | PH_AGUA | 5,7 pH | -1 | 928 (identificador presente) |
| 1390 | LEVE | FIEBRE | TEMP_CORPORAL | 36,2 °C | -1 | 928 (identificador presente) |

**Decisión con porqué:** **APROBADO**. API-191-01 acreditó HTTP 200, eco, total, lista, alcance, orden, tipo, variable y tiempo dentro de la ventana del RUN; API-191-02 acreditó las tres severidades ACTIVA en sensores distintos; API-191-03 acreditó id_activo_biologico e identificador_activo; API-191-04 acreditó severidad_alerta en los sensores. Comprobaciones acreditadas.

**Qué falta:** Nada para decidir el caso por API. La navegación visual no se ejecutó; este caso está clasificado como API Postman/Newman.

| Comprobación | Fuente | Estado | Motivo | Evidencia |
| --- | --- | --- | --- | --- |
| API-191-01 | API | APROBADO | Panel, total, estados, alcance, campos y orden acreditados | [newman/newman-G98.json](newman/newman-G98.json) |
| API-191-02 | API | APROBADO | Tres severidades RF-57 ACTIVA y sensores distintos; área segura | [resultado.json](resultado.json) |
| API-191-03 | API | APROBADO | Cada alerta del panel tiene id_activo_biologico e identificador_activo | [newman/newman-G98.json](newman/newman-G98.json) |
| API-191-04 | API | APROBADO | Sensores con id_alerta tienen severidad_alerta | [newman/newman-G98.json](newman/newman-G98.json) |

| Área | HTTP | Eco | Estado del panel |
| ---: | ---: | --- | --- |
| 702 | 200 | sí | APROBADO |

La API comprobó los identificadores de navegación; no se ejecutó navegación visual.

## 4. Incidencias y observaciones

INC-M03-191-G98-01: **CORREGIDA**. El panel faltaba en V1; en V3 la API pública devolvió total 3, lista ordenada, campos y activo. Equipo inicial Desarrollo por la ausencia API observada en V1; severidad ALTA de aquel hallazgo, certeza CONFIRMADA de la corrección en este RUN oficial.

INC-M03-191-G98-02: **ANULADA**. El rechazo temporal V2 fue un falso positivo del oráculo QA: el sandbox fijó now() al inicio de la transacción mientras las alertas se crearon después. No es incidencia de producto. El valor −1 se registra como observación; no hay nueva discrepancia funcional en V3.

**Historial de intentos técnicos V2:** [intento 165339](api/antecedentes/intento-165339.json), BLOQUEADO porque no había tres severidades ACTIVA previas; [intento 172140](api/antecedentes/intento-172140.json), BLOQUEADO sin terna segura y sin POST; [intento 182607](api/antecedentes/intento-182607.json), BLOQUEADO porque las 24 consultas de historial registradas respondieron HTTP 422 al combinar sensor_id con id_infraestructura, filtro no admitido por la Restricción 12 de RF-59. [Índice de origen y SHA-256](api/antecedentes/indice.json). Son extractos saneados dentro de este RUN oficial; los originales técnicos no son dependencias del informe.

Problemas técnicos QA de V3: ninguno.

## 5. Análisis de causas y certeza

La lectura local documentada en la preparación anterior señaló src/telemetry/infrastructure/repositories/indicadores_alertas_repository.py:70, donde se calcula el tiempo con now(), y src/telemetry/application/use_cases/alertas/generar_alerta_use_case.py:110, donde se fija la fecha al crear la alerta. En esta orden no se consultó código del producto. La comparación entre los RUN V2 y V3 confirma el falso positivo del oráculo QA; el mecanismo del reloj transaccional es una explicación PROBABLE del −1, sin verificar el despliegue exacto de TEST.

## 6. Conclusión y acciones

APROBADO: el RUN V3 acreditó por API pública el total, orden, datos, tiempo dentro de la ventana y vínculo al activo. Conservar esta evidencia, cerrar INC-M03-191-G98-01 como corregida y dejar INC-M03-191-G98-02 anulada como falso positivo QA.

## 7. Evidencias, herramientas, cierre y rollback

Node v22.15.1; Newman 6.2.2; Postman y Cypress no ejecutados. Presupuesto: 224 solicitudes directas, hasta 3 POST de alerta, 1 DELETE de cierre y 3 GET posteriores.

**Bitácora resumida por tipo de petición:**

| Método | Ruta saneada | HTTP | Eco | Peticiones |
| --- | --- | ---: | --- | ---: |
| POST | /sesiones/ | 200 | no aplica | 2 |
| GET | /configuracion/infraestructuras | 200 | sí | 6 |
| GET | /configuracion/fincas | 200 | sí | 2 |
| GET | /iot/alertas | 200 | sí | 8 |
| GET | /configuracion/dispositivos-iot | 200 | sí | 1 |
| GET | /activos-biologicos | 200 | sí | 1 |
| GET | /configuracion/dispositivos-iot/{id}/sensores | 200 | sí | 1 |
| GET | /iot/monitoreo/historial | 200 | sí | 3 |
| GET | /iot/monitoreo/dashboard/{área} | 200 | sí | 2 |
| POST | /iot/alertas | 201 | sí | 3 |
| GET | /iot/alertas/{id} | 200 | sí | 3 |
| DELETE | /test-control/runs/{RUN} | 200 | no aplica | 1 |
| GET | /iot/alertas/{id} | 404 | no aplica | 3 |

El detalle de cada petición consta en [resultado.json](resultado.json); la respuesta de Newman consta en [newman/newman-G98.json](newman/newman-G98.json). Otras evidencias del RUN: [preflight.json](preflight.json), [newman/newman-G98.json](newman/newman-G98.json), [newman/newman-G98.html](newman/newman-G98.html).

Cierre DELETE HTTP 200. Rollback: 3 IDs ausentes o no ACTIVOS tras DELETE 200. El login y los posibles efectos E7 no se declaran revertidos.

