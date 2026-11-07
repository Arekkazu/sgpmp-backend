# TC-M03-G98 — RECHAZADO

## 1. Identificación

Grupo G98; caso TC-M03-191; RF-58/CU04, Salida 2 y CA-11; versión V2; operación REINTENTAR; RUN RUN-G98-V2-20261031-183417; ambiente TEST; autorización AUT-G98-V2-R4-20261031; backend código local consultado; despliegue no verificado; frontend PR #456 informado por Desarrollo; despliegue no verificado; commit TEST no verificado (referencia informada por orden: edc7593e). Node v22.15.1; Newman 6.2.2; Postman y Cypress no ejecutados. Contrato API. Intento 5; intento técnico anterior de V2: RUN-G98-V2-20261031-172140 (no oficial).

## 2. Resumen ejecutivo y decisión del grupo

**RECHAZADO**, veredicto oficial de V2. El oráculo automatizado de V2 rechazó minutos_transcurridos=−1 en las alertas 1385, 1386, 1387 porque exigía un valor no negativo. Newman ejecutó una consulta; total 3, orden, campos y activo ya cumplían.

## 3. Detalle por caso y comprobaciones API/UI

### TC-M03-191

**Objetivo:** verificar el total y el orden por severidad del panel de alertas activas, sus datos y el identificador que permite navegar al activo afectado.

**Precondiciones:** «Alertas activas de severidad CRITICO, ALTA y MEDIA sobre distintos sensores de la misma unidad.» La decisión QA aceptó la escala RF-57 CRITICO > MODERADO > LEVE para la terna real. Semilla persistente QA-G98-PANEL: finca 184, área 702, dispositivo 789, sensores 1210/1211/1212, activo biológico 928. Los GET públicos del RUN acreditaron área, activo, sensores y lecturas. Antes de crear las alertas, no había un área visible con las tres severidades ACTIVA; se usó la semilla apta del área 702. Vía CREACION_SANDBOX; las alertas 1385, 1386, 1387 se crearon solo en el sandbox del RUN.

**Pasos:** iniciar sesión; comprobar área, activo, dispositivo, sensores y lecturas; ejecutar el canario E7; crear y verificar las tres alertas en el sandbox; consultar el dashboard por Newman; cotejar total, orden, campos, tiempo y activo; cerrar el RUN y comprobar rollback.

**Entradas:** área 702; alertas 1385, 1386, 1387; inicio del RUN 2026-10-31T18:34:17.958Z.

**Esperado:** «HTTP 200. Se devuelve el total de alertas activas y la lista ordenada por severidad con CRITICO primero, indicando tipo de alerta, variable afectada y tiempo transcurrido, con navegación al detalle del activo biológico afectado.» Orden aceptado por decisión QA: CRITICO > MODERADO > LEVE. El oráculo automatizado vigente durante V2 exigía tiempo no negativo.

**Observado:** El oráculo automatizado vigente en V2 marcó inválido el campo minutos_transcurridos: valor −1 en cada alerta (1385, 1386, 1387); exigía un tiempo no negativo. El panel ya mostraba total, orden, campos y activo correctos.

**Valores observados en Newman:** total 3; 3 filas.

| ID | Severidad | Tipo de alerta | Variable | Valor | Minutos transcurridos | Activo biológico |
| ---: | --- | --- | --- | ---: | ---: | --- |
| 1385 | CRITICO | SINDROME_RESPIRATORIO | NH3 | 50 ppm | -1 | 928 (identificador presente) |
| 1386 | MODERADO | RIESGO_HIDRICO | PH_AGUA | 5,7 pH | -1 | 928 (identificador presente) |
| 1387 | LEVE | FIEBRE | TEMP_CORPORAL | 36,2 °C | -1 | 928 (identificador presente) |

**Decisión con porqué:** **RECHAZADO** según el oráculo automatizado de ese RUN: El oráculo automatizado vigente en V2 marcó inválido el campo minutos_transcurridos: valor −1 en cada alerta (1385, 1386, 1387); exigía un tiempo no negativo. API-191-02, API-191-03 y API-191-04 aprobaron. La nota posterior documenta por qué V3 anuló la incidencia temporal; el veredicto histórico de V2 permanece RECHAZADO.

**Qué falta:** En V2 faltaba resolver la discrepancia temporal del oráculo automatizado. V3 documenta su resolución sin alterar este veredicto histórico.

| Comprobación | Fuente | Estado | Motivo | Evidencia |
| --- | --- | --- | --- | --- |
| API-191-01 | API | RECHAZADO | El oráculo automatizado vigente en V2 marcó inválido el campo minutos_transcurridos: valor −1 en cada alerta (1385, 1386, 1387); exigía un tiempo no negativo. | [newman/newman-G98.json](newman/newman-G98.json) |
| API-191-02 | API | APROBADO | Tres severidades RF-57 ACTIVA y sensores distintos; área segura | [resultado.json](resultado.json) |
| API-191-03 | API | APROBADO | Cada alerta del panel tiene id_activo_biologico e identificador_activo | [newman/newman-G98.json](newman/newman-G98.json) |
| API-191-04 | API | APROBADO | Sensores con id_alerta tienen severidad_alerta | [newman/newman-G98.json](newman/newman-G98.json) |

| Área | HTTP | Eco | Estado del panel |
| ---: | ---: | --- | --- |
| 702 | 200 | sí | RECHAZADO |

La API comprobó los identificadores de navegación; no se ejecutó navegación visual.

## 4. Incidencias y observaciones

INC-M03-191-G98-02 se registró en V2 como incidencia **MEDIA**, certeza de la discrepancia temporal CONFIRMADA por la respuesta API, equipo inicial Desarrollo por ser el dashboard la primera superficie observada. El campo minutos_transcurridos valía −1 en las alertas 1385, 1386 y 1387; el oráculo de entonces exigía valor no negativo. La causa raíz no quedó determinada en V2. La nota posterior deja constancia de su anulación, sin cambiar el RECHAZADO histórico.

INC-M03-191-G98-01: **CORREGIDA** en V2 respecto de la ausencia del panel en V1. Ya se observaron total 3, orden y campos del activo. No había tres alertas ACTIVA aptas antes de crear la terna en el sandbox.

Problemas técnicos QA registrados en este RUN: ninguno.

## 5. Análisis de causas y certeza

La primera discrepancia registrada en V2 fue el valor −1 del campo minutos_transcurridos frente al oráculo automatizado que exigía un valor no negativo. La respuesta pública y el reporte Newman confirman el dato observado; la causa raíz no se estableció en ese RUN. La lectura local de código citada en la preparación anterior no verifica el despliegue de TEST. En esta orden no se consultó código del producto.

## 6. Conclusiones y acciones

RECHAZADO según el oráculo temporal vigente en V2: El oráculo automatizado de V2 rechazó minutos_transcurridos=−1 en las alertas 1385, 1386, 1387 porque exigía un valor no negativo. La reevaluación V3 posterior aclaró este falso positivo; conservar el veredicto y la evidencia histórica sin derivar una incidencia vigente a Desarrollo.

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


## Nota posterior (V3)

INC-M03-191-G98-02 fue **ANULADA** en RUN-G98-V3-20261031-185044: el valor −1 provenía del falso positivo del oráculo QA frente al now() fijo del sandbox. El panel de V2 ya cumplía total 3, orden, campos y vínculo al activo 928. Esta nota no modifica el veredicto RECHAZADO ni resultado.json de V2.
