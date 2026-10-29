# TC-M03-G89 — resultado RUN-G89-V1-20261025-045219

## Identificación

Grupo G89; casos TC-M03-173 y TC-M03-174; RF-58; versión V1; RUN RUN-G89-V1-20261025-045219; ambiente TEST; autorización AUT-G89-V1-R2-20261025; operación reintentar; commit NO_VERIFICADO; inicio 2026-10-25T04:52:19.560Z; fin 2026-10-25T04:52:49.185Z. Herramientas: Node v22.15.1, Newman con 8 ejecuciones JSON; Cypress no exigido por la matriz.

## Alcance y oráculo

Fuente: Casos_Prueba(Modulo3 Agrupado).csv, fila G89, RF-58. Herramienta API Postman/Newman. GET /iot/monitoreo/dashboard. La semilla se revalidó por GET: sí. Las marcas de ingesta se calcularon antes de abrir el RUN: sí.

## Resumen de veredictos

| Caso | Veredicto funcional | Estado técnico | Motivo |
|---|---|---|---|
| TC-M03-173 | APROBADO | OK | — |
| TC-M03-174 | RECHAZADO | OK | — |

## Esperado y observado por caso

### TC-M03-173

**Esperado:** Valor dentro del rango óptimo, alerta CRITICO ACTIVA asociada: HTTP 200, ROJO e id_alerta asociado.

**Observado:** PRE-173-01: VERDE, id_alerta=null (HTTP 200); API-173-01: ROJO, id_alerta=298 (HTTP 200)

| ID | Etapa | Estado esperado | Estado observado | HTTP | Evaluación | Evidencia |
|---|---|---|---|---:|---|---|
| PRE-173-01 | base173 | VERDE | VERDE; id_alerta=null | 200 | Cumple | newman/newman-TC-M03-173-01.json |
| API-173-01 | critica | ROJO; id_alerta=298 | ROJO; id_alerta=298 | 200 | Cumple | newman/newman-TC-M03-173-02.json |

**Veredicto funcional:** APROBADO. **Estado técnico:** OK. 

### TC-M03-174

**Esperado:** Base VERDE y alerta no crítica ACTIVA: AMARILLO; alerta RESUELTA o DESCARTADA: VERDE sin elevación indebida.

**Observado:** PRE-174-01: VERDE, id_alerta=null (HTTP 200); API-174-01: AMARILLO, id_alerta=299 (HTTP 200); API-174-02: AMARILLO, id_alerta=null (HTTP 200); PRE-174-02: VERDE, id_alerta=null (HTTP 200); API-174-03: AMARILLO, id_alerta=300 (HTTP 200); API-174-04: AMARILLO, id_alerta=null (HTTP 200)

| ID | Etapa | Estado esperado | Estado observado | HTTP | Evaluación | Evidencia |
|---|---|---|---|---:|---|---|
| PRE-174-01 | base174 | VERDE | VERDE; id_alerta=null | 200 | Cumple | newman/newman-TC-M03-174-03.json |
| API-174-01 | noCriticaActiva | AMARILLO | AMARILLO; id_alerta=299 | 200 | Cumple | newman/newman-TC-M03-174-04.json |
| API-174-02 | resuelta | VERDE | AMARILLO; id_alerta=null | 200 | Difiere | newman/newman-TC-M03-174-05.json |
| PRE-174-02 | baseDescarte | VERDE | VERDE; id_alerta=null | 200 | Cumple | newman/newman-TC-M03-174-06.json |
| API-174-03 | noCriticaDescarte | AMARILLO | AMARILLO; id_alerta=300 | 200 | Cumple | newman/newman-TC-M03-174-07.json |
| API-174-04 | descartada | VERDE | AMARILLO; id_alerta=null | 200 | Difiere | newman/newman-TC-M03-174-08.json |

**Veredicto funcional:** RECHAZADO. **Estado técnico:** OK. 

## Comprobaciones API/UI

Las tablas anteriores detallan los GET del dashboard. UI: cero comprobaciones porque la matriz no exige UI. POST /iot/telemetria, POST /iot/alertas, PATCH /iot/alertas/{id}/estado y GET de alertas acreditan precondiciones cuando sus respuestas figuran en la bitácora.

## Incidencias

### Producto

### INC-G89-174-01: AMARILLO persistente tras alerta terminal

- **Identificación y título:** INC-G89-174-01; TC-M03-174; elevación persistente tras RESUELTA/DESCARTADA; RUN-G89-V1-20261025-045219.
- **Contexto funcional:** RF-58 fase 3 combina lectura y alertas ACTIVA; CA-4 exige ROJO con CRITICO activa. Una no crítica ACTIVA eleva a AMARILLO. El caso 174 exige cesar esa elevación al resolver o descartar.
- **Precondiciones:** Sensor 552, área 349, especie 126; lectura 25.0000 °C, umbral normal 20-30 °C; base VERDE sin alerta; alertas 299 LEVE y 300 MODERADO.
- **Pasos y escenarios:** LEVE a RESUELTA (alerta 299): POST ingesta 25 °C HTTP 201, id_telemetria=117079; PRE-174-01: GET HTTP 200, estado_semaforo=VERDE, id_alerta=null; [newman/newman-TC-M03-174-03.json](newman/newman-TC-M03-174-03.json); POST alerta LEVE HTTP 201, id_alerta=299; API-174-01: GET HTTP 200, estado_semaforo=AMARILLO, id_alerta=299; [newman/newman-TC-M03-174-04.json](newman/newman-TC-M03-174-04.json); PATCH /iot/alertas/299/estado EN_ATENCION a RESUELTA HTTP 200, 200; GET inmediato sin nueva ingesta API-174-02: GET HTTP 200, estado_semaforo=AMARILLO, id_alerta=null; [newman/newman-TC-M03-174-05.json](newman/newman-TC-M03-174-05.json). MODERADO a DESCARTADA (alerta 300): POST ingesta 25 °C HTTP 201, id_telemetria=117080; PRE-174-02: GET HTTP 200, estado_semaforo=VERDE, id_alerta=null; [newman/newman-TC-M03-174-06.json](newman/newman-TC-M03-174-06.json); POST alerta MODERADO HTTP 201, id_alerta=300; API-174-03: GET HTTP 200, estado_semaforo=AMARILLO, id_alerta=300; [newman/newman-TC-M03-174-07.json](newman/newman-TC-M03-174-07.json); PATCH /iot/alertas/300/estado DESCARTADA HTTP 200; GET inmediato sin nueva ingesta API-174-04: GET HTTP 200, estado_semaforo=AMARILLO, id_alerta=null; [newman/newman-TC-M03-174-08.json](newman/newman-TC-M03-174-08.json).
- **Esperado y fundamento:** GET dashboard HTTP 200 debe devolver VERDE tras RESUELTA o DESCARTADA, sin nueva telemetría, si la lectura vigente está en rango y no hay otra condición activa.
- **Observado:** API-174-02, API-174-04: GET HTTP 200 devolvió AMARILLO con id_alerta=null tras los PATCH terminales.
- **Requisito incumplido:** RF-58 fase 3: «Si hay una alerta ACTIVA asociada → al menos AMARILLO»; matriz G89: «Con alerta resuelta o descartada: estado_semaforo="VERDE", sin elevación indebida.»
- **Evidencia:** API-174-02, API-174-04; [newman/newman-TC-M03-174-05.json](newman/newman-TC-M03-174-05.json); [newman/newman-TC-M03-174-08.json](newman/newman-TC-M03-174-08.json); HTTP de POST/PATCH en bitácora; evidencias de base y alerta activa enlazadas en cada escenario.
- **Impacto:** Monitoreo indica precaución con lectura normal y sin alerta activa asociada; altera la interpretación operativa del semáforo.
- **Severidad:** MEDIA: afecta dos transiciones de este sensor; no hay evidencia de bloqueo general ni pérdida de datos.
- **Certeza:** CONFIRMADA para las respuestas de producto en TEST; causa raíz NO DETERMINADA.
- **Equipo inicial:** Desarrollo, backend de monitoreo/alertas: primera discrepancia en GET dashboard tras PATCH; derivación inicial, no causa raíz.
- **Análisis técnico:** Hipótesis de código local, sin confirmar en despliegue TEST: alembic/baseline/esquema_baseline.sql:7478-7482 limpia id_alerta sin recalcular estado_semaforo; src/telemetry/infrastructure/repositories/monitoreo_repository.py:70 consulta alerta ACTIVA; src/telemetry/application/use_cases/monitoreo/obtener_dashboard_use_case.py:73-78 parte del estado persistido.
- **Acción correctiva:** Recalcular semáforo al pasar una alerta a RESUELTA o DESCARTADA con lectura vigente y demás alertas activas; no asignar VERDE incondicionalmente.
- **Criterio de aceptación:** Lectura normal sin alerta VERDE; LEVE activa AMARILLO; LEVE resuelta VERDE si no hay otra condición; MODERADO activa AMARILLO; MODERADO descartada VERDE si no hay otra condición; sin nueva telemetría; considerar otras alertas activas.
- **Estado actual:** Hallazgo funcional confirmado en TEST en este RUN; pendiente de corrección y reevaluación autorizada.

### Automatización QA

Sin incidencias tecnicas registradas.

### Casos sin veredicto

Ninguno.

## Hallazgos y análisis de causas

El código local puede diferir del despliegue TEST; no se atribuye causa raíz sin evidencia de TEST.

## Bitácora de solicitudes

| Método | Ruta | En RUN | Latencia ms | HTTP | Eco RUN | Error saneado |
|---|---|---|---:|---:|---|---|
| POST | /sesiones/ | No | 1135 | 200 | N/A | — |
| POST | /sesiones/ | No | 644 | 200 | N/A | — |
| GET | /usuarios/me | Sí | 341 | 200 | Sí | — |
| GET | /configuracion/dispositivos-iot/357 | Sí | 553 | 200 | Sí | — |
| GET | /configuracion/infraestructuras/349 | Sí | 209 | 200 | Sí | — |
| GET | /configuracion/dispositivos-iot/357/sensores | Sí | 151 | 200 | Sí | — |
| GET | /configuracion/sensores/552/asociaciones | Sí | 164 | 200 | Sí | — |
| GET | /configuracion/sensores/552/calibraciones | Sí | 159 | 200 | Sí | — |
| GET | /configuracion/umbrales | Sí | 202 | 200 | Sí | — |
| GET | /iot/alertas | Sí | 242 | 200 | Sí | — |
| GET | /iot/alertas | Sí | 164 | 200 | Sí | — |
| GET | /iot/monitoreo/dashboard | Sí | 297 | 200 | Sí | — |
| POST | /iot/telemetria | Sí | 153 | 201 | Sí | — |
| GET | /iot/monitoreo/dashboard | Sí | 3542 | 200 | Sí | — |
| POST | /iot/alertas | Sí | 177 | 201 | Sí | — |
| GET | /iot/alertas/298 | Sí | 161 | 200 | Sí | — |
| GET | /iot/monitoreo/dashboard | Sí | 2663 | 200 | Sí | — |
| PATCH | /iot/alertas/298/estado | Sí | 148 | 200 | Sí | — |
| PATCH | /iot/alertas/298/estado | Sí | 149 | 200 | Sí | — |
| POST | /iot/telemetria | Sí | 135 | 201 | Sí | — |
| GET | /iot/monitoreo/dashboard | Sí | 2856 | 200 | Sí | — |
| POST | /iot/alertas | Sí | 138 | 201 | Sí | — |
| GET | /iot/alertas/299 | Sí | 222 | 200 | Sí | — |
| GET | /iot/monitoreo/dashboard | Sí | 2572 | 200 | Sí | — |
| PATCH | /iot/alertas/299/estado | Sí | 150 | 200 | Sí | — |
| PATCH | /iot/alertas/299/estado | Sí | 151 | 200 | Sí | — |
| GET | /iot/monitoreo/dashboard | Sí | 2426 | 200 | Sí | — |
| POST | /iot/telemetria | Sí | 139 | 201 | Sí | — |
| GET | /iot/monitoreo/dashboard | Sí | 2396 | 200 | Sí | — |
| POST | /iot/alertas | Sí | 138 | 201 | Sí | — |
| GET | /iot/alertas/300 | Sí | 143 | 200 | Sí | — |
| GET | /iot/monitoreo/dashboard | Sí | 2433 | 200 | Sí | — |
| PATCH | /iot/alertas/300/estado | Sí | 147 | 200 | Sí | — |
| GET | /iot/monitoreo/dashboard | Sí | 2500 | 200 | Sí | — |
| DELETE | /test-control/runs/G89-V1-20261025-045219 | Sí | 129 | 200 | Sí | — |
| POST | /sesiones/ | No | 415 | 200 | N/A | — |
| POST | /sesiones/ | No | 409 | 200 | N/A | — |
| GET | /iot/monitoreo/dashboard | No | 256 | 200 | N/A | — |
| GET | /iot/alertas/298 | No | 142 | 404 | N/A | {   "error_code": "ALERTA_NO_ENCONTRADA",   "message": "Alerta 298 no encontrada.",   "fields": [],   "timestamp": "2026-10-25T04:52:48.717086+00:00" } |
| GET | /iot/alertas/299 | No | 141 | 404 | N/A | {   "error_code": "ALERTA_NO_ENCONTRADA",   "message": "Alerta 299 no encontrada.",   "fields": [],   "timestamp": "2026-10-25T04:52:48.856685+00:00" } |
| GET | /iot/alertas/300 | No | 147 | 404 | N/A | {   "error_code": "ALERTA_NO_ENCONTRADA",   "message": "Alerta 300 no encontrada.",   "fields": [],   "timestamp": "2026-10-25T04:52:48.997499+00:00" } |
| GET | /iot/monitoreo/historial | No | 151 | 200 | N/A | — |

## Evidencias reales

- [resultado.json](resultado.json)
- [preflight.json](preflight.json)
- [newman/newman-TC-M03-173-01.json](newman/newman-TC-M03-173-01.json)
- [newman/newman-TC-M03-173-02.json](newman/newman-TC-M03-173-02.json)
- [newman/newman-TC-M03-174-03.json](newman/newman-TC-M03-174-03.json)
- [newman/newman-TC-M03-174-04.json](newman/newman-TC-M03-174-04.json)
- [newman/newman-TC-M03-174-05.json](newman/newman-TC-M03-174-05.json)
- [newman/newman-TC-M03-174-06.json](newman/newman-TC-M03-174-06.json)
- [newman/newman-TC-M03-174-07.json](newman/newman-TC-M03-174-07.json)
- [newman/newman-TC-M03-174-08.json](newman/newman-TC-M03-174-08.json)
- [newman/newman-G89-consolidado.html](newman/newman-G89-consolidado.html)

## Cierre y rollback

DELETE /test-control/runs/{id}: HTTP 200. Rollback: VERIFICADO por GET posteriores. DELETE y lecturas posteriores acreditan reversión de los objetos comprobados.

| Comprobación | HTTP | Coincide |
|---|---:|---|
| dashboard_previo | 200 | Sí |
| alerta_ausente | 404 | Sí |
| alerta_ausente | 404 | Sí |
| alerta_ausente | 404 | Sí |
| telemetrias_ausentes | 200 | Sí |

## Conclusión y acción concreta

Estado final COMPLETO. Revisar las incidencias funcionales documentadas y decidir cierre de QA.
