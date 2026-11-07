# TC-M03-G89 — APROBADO

## Identificación

Grupo G89; casos TC-M03-173, TC-M03-174; RF-58; V2; RUN RUN-G89-V2-20261030-212919; ambiente TEST; autorización AUT-G89-V2-R3-20261030; operación reintentar; commit NO_VERIFICADO. Inicio 2026-10-30T21:29:19.987Z; fin 2026-10-30T21:29:34.783Z. Herramientas: Node v22.15.1; Newman 1 ejecución JSON, versión no verificada; Cypress no exigido (0 pruebas).

## Decisión del caso

APROBADO. Oficialidad OFICIAL; cierre HTTP 200; rollback VERIFICADO.

## Alcance de reevaluación

V1 → V2; casos TC-M03-173, TC-M03-174. Motivo: Reintento técnico de la V2 (intento 5). RUN-G89-V2-20261030-211230 (TÉCNICO, rollback CONFIRMADO): las altas de alerta de 37 °C y 31 °C respondieron 422 por la regla compuesta ESTRES_TERMICO (REGLA_COMPUESTA_NO_ACTIVADA: la temperatura ambiental exige THI con humedad). ORD-G89-012: cada alta incluye correlacion_variables HUMEDAD_RELATIVA=40 (dato del evento) → THI 85,20/77,97/81,58 con severidad CRITICO/LEVE/MODERADO; validado localmente contra el DTO y reglas_base_rf57 del backend (pruebas/validar_alertas_rf57.py: DTO=OK, condición=OK); se guarda el cuerpo de toda respuesta no 2xx. Ensayo del responsable QA 14/14 y --comprobar válido. SHA-256 g89.mjs b9cebe3a0b037ed5ecc1cdda6bfc4bc946a323dab73dba85b2f797cc0fcf70ef; colección 3f3d3a7e6aff9416139926f46469666c4c917616938d9c857dbdbcf8a37140ad.. Incumplimientos previos: V1 oficial RUN-G89-V1-20261025-045219: 173 APROBADO; 174 RECHAZADO, INC-G89-174-01 (tras RESUELTA de la alerta 299 LEVE y DESCARTADA de la 300 MODERADO, el dashboard devolvió AMARILLO con id_alerta=null; API-174-02 y API-174-04).. Correcciones informadas: Desarrollo, issue #705 / PR #732: recálculo del semáforo tras RESUELTA o DESCARTADA con la última lectura válida, los umbrales RF-17, la conectividad y las demás alertas abiertas; best-effort; sin migración.; su despliegue exacto no se deduce del código local. Resultado esperado: 173 APROBADO: con CRITICO activa → ROJO con su id_alerta. 174 APROBADO: LEVE activa → AMARILLO y al resolverla → VERDE con id_alerta null; MODERADO activa → AMARILLO y al descartarla → VERDE con id_alerta null; sin nueva ingesta. INC-G89-174-01 CORREGIDA si se cumple.. V1 oficial: Resultados/RUN-G89-V1-20261025-045219/TC-M03-G89_resultado.md; 173 APROBADO, 174 RECHAZADO (INC-G89-174-01).

## Resumen de veredictos y comparación V1 → V2

| Caso | V1 | V2 | Motivo |
|---|---|---|---|
| TC-M03-173 | APROBADO | APROBADO | — |
| TC-M03-174 | RECHAZADO | APROBADO | — |

## Detalle por caso

### TC-M03-173

**Esperado:** HTTP 200. estado_semaforo="ROJO" pese a que el valor está en rango VERDE, y se devuelve el id_alerta asociado.
**Observado por API pública:** PRE-173-01: HTTP 200, VERDE, id_alerta=null, lectura=25.0000, vigente=sí, en_rango=sí; API-173-01: HTTP 200, ROJO, id_alerta=1343, lectura=25.0000, vigente=sí, en_rango=sí
**Decisión del caso:** APROBADO; V1 APROBADO → V2 APROBADO.
**Qué falta o cambió:** Se cumplieron las comprobaciones obligatorias; sin pendientes del caso.

| Comprobación | Tipo | Esperado | Observado | HTTP | Estado | Evidencia |
|---|---|---|---|---:|---|---|
| PRE-173-01 | PRE | VERDE | VERDE; id_alerta=null | 200 | APROBADO | [api/PRE-173-01.json](api/PRE-173-01.json) |
| API-173-01 | ASSERT | ROJO | ROJO; id_alerta=1343 | 200 | APROBADO | [api/API-173-01.json](api/API-173-01.json) |

### TC-M03-174

**Esperado:** Con alerta activa: estado_semaforo="AMARILLO". Con alerta resuelta o descartada: estado_semaforo="VERDE", sin elevación indebida.
**Observado por API pública:** PRE-174-01: HTTP 200, VERDE, id_alerta=null, lectura=25.0000, vigente=sí, en_rango=sí; API-174-01: HTTP 200, AMARILLO, id_alerta=1344, lectura=25.0000, vigente=sí, en_rango=sí; API-174-02: HTTP 200, VERDE, id_alerta=null, lectura=25.0000, vigente=sí, en_rango=sí; PRE-174-02: HTTP 200, VERDE, id_alerta=null, lectura=25.0000, vigente=sí, en_rango=sí; API-174-03: HTTP 200, AMARILLO, id_alerta=1345, lectura=25.0000, vigente=sí, en_rango=sí; API-174-04: HTTP 200, VERDE, id_alerta=null, lectura=25.0000, vigente=sí, en_rango=sí
**Decisión del caso:** APROBADO; V1 RECHAZADO → V2 APROBADO.
**Qué falta o cambió:** Se cumplieron las comprobaciones obligatorias; sin pendientes del caso.

| Comprobación | Tipo | Esperado | Observado | HTTP | Estado | Evidencia |
|---|---|---|---|---:|---|---|
| PRE-174-01 | PRE | VERDE | VERDE; id_alerta=null | 200 | APROBADO | [api/PRE-174-01.json](api/PRE-174-01.json) |
| API-174-01 | ASSERT | AMARILLO | AMARILLO; id_alerta=1344 | 200 | APROBADO | [api/API-174-01.json](api/API-174-01.json) |
| API-174-02 | ASSERT | VERDE | VERDE; id_alerta=null | 200 | APROBADO | [api/API-174-02.json](api/API-174-02.json) |
| PRE-174-02 | PRE | VERDE | VERDE; id_alerta=null | 200 | APROBADO | [api/PRE-174-02.json](api/PRE-174-02.json) |
| API-174-03 | ASSERT | AMARILLO | AMARILLO; id_alerta=1345 | 200 | APROBADO | [api/API-174-03.json](api/API-174-03.json) |
| API-174-04 | ASSERT | VERDE | VERDE; id_alerta=null | 200 | APROBADO | [newman/newman-TC-M03-G89.json](newman/newman-TC-M03-G89.json) |

## Comprobaciones API/UI

GET /iot/monitoreo/dashboard con Productor; IDs PRE y API conservados. Los GET previos tienen evidencia JSON saneada en api/; API-174-04 usa la única ejecución Newman. UI no requerida por la matriz. Acceso: Productor con rol, identidad y finca 184 acreditados; Administrador con rol, identidad y lectura del área 349 acreditados.

## Altas RF-57 y respuestas POST

Via EDGE: 37 C (CRITICO), 31 C (LEVE) y 34 C (MODERADO), vinculadas a sus telemetrias reales, con HUMEDAD_RELATIVA=40 en correlacion_variables. El THI calculado cumple la condicion minima de ESTRES_TERMICO y conserva la severidad esperada. Cada alta va seguida de 25 C y comprobacion de lectura vigente en rango por dashboard. Fuentes: reglas_base_rf57.py:49-75,92-112,131-148 y generar_alerta_use_case.py:155-175,377-387,429-466. Un HTTP 201 sin id_alerta deja el caso sin veredicto y conserva motivo_descarte.

| Caso | Severidad esperada | HTTP | Duplicado | ID | Severidad POST | Motivo de descarte | Error code | Message | Fields | Evidencia |
|---|---|---:|---|---:|---|---|---|---|---|---|
| TC-M03-173 | CRITICO | 201 | false | 1343 | CRITICO | — | — | — | [] | [api/POST-ALERTA-CRITICO.json](api/POST-ALERTA-CRITICO.json) |
| TC-M03-174 | LEVE | 201 | false | 1344 | LEVE | — | — | — | [] | [api/POST-ALERTA-LEVE.json](api/POST-ALERTA-LEVE.json) |
| TC-M03-174 | MODERADO | 201 | false | 1345 | MODERADO | — | — | — | [] | [api/POST-ALERTA-MODERADO.json](api/POST-ALERTA-MODERADO.json) |

## Estado de la incidencia V1

INC-G89-174-01: CORREGIDA. Los GET tras RESUELTA y DESCARTADA devolvieron VERDE e id_alerta=null sin nueva ingesta entre PATCH y GET.

## Incidencias de producto

Sin discrepancias funcionales acreditadas en este RUN.

## Automatización y entorno

Sin problemas técnicos registrados. 

## Análisis de causas

Hecho: no se registró discrepancia funcional concluyente en las comprobaciones ejecutadas. Hipótesis: el recálculo informado por Desarrollo puede explicar un cambio de V1 a V2; no demuestra la causa raíz ni el despliegue en TEST.

## Evidencias reales

- [resultado.json](resultado.json)
- [preflight.json](preflight.json)
- [api/PRE-173-01.json](api/PRE-173-01.json)
- [api/POST-ALERTA-CRITICO.json](api/POST-ALERTA-CRITICO.json)
- [api/GET-ALERTA-CRITICO.json](api/GET-ALERTA-CRITICO.json)
- [api/API-173-01.json](api/API-173-01.json)
- [api/PRE-174-01.json](api/PRE-174-01.json)
- [api/POST-ALERTA-LEVE.json](api/POST-ALERTA-LEVE.json)
- [api/GET-ALERTA-LEVE.json](api/GET-ALERTA-LEVE.json)
- [api/API-174-01.json](api/API-174-01.json)
- [api/API-174-02.json](api/API-174-02.json)
- [api/PRE-174-02.json](api/PRE-174-02.json)
- [api/POST-ALERTA-MODERADO.json](api/POST-ALERTA-MODERADO.json)
- [api/GET-ALERTA-MODERADO.json](api/GET-ALERTA-MODERADO.json)
- [api/API-174-03.json](api/API-174-03.json)
- [newman/newman-TC-M03-G89.json](newman/newman-TC-M03-G89.json)
- [newman/newman-TC-M03-G89.html](newman/newman-TC-M03-G89.html)

## Bitácora de solicitudes

| Método | Ruta | HTTP | Eco RUN | Error saneado |
|---|---|---:|---|---|
| POST | /sesiones/ | 200 | N/A | — |
| POST | /sesiones/ | 200 | N/A | — |
| GET | /usuarios/me | 200 | Sí | — |
| GET | /usuarios/me | 200 | Sí | — |
| GET | /configuracion/dispositivos-iot/357 | 200 | Sí | — |
| GET | /configuracion/infraestructuras/349 | 200 | Sí | — |
| GET | /configuracion/dispositivos-iot/357/sensores | 200 | Sí | — |
| GET | /configuracion/sensores/552/asociaciones | 200 | Sí | — |
| GET | /configuracion/sensores/552/calibraciones | 200 | Sí | — |
| GET | /configuracion/umbrales | 200 | Sí | — |
| GET | /iot/alertas | 200 | Sí | — |
| GET | /iot/alertas | 200 | Sí | — |
| GET | /iot/monitoreo/dashboard | 200 | Sí | — |
| POST | /iot/telemetria | 201 | Sí | — |
| GET | /iot/monitoreo/dashboard | 200 | Sí | — |
| POST | /iot/telemetria | 201 | Sí | — |
| POST | /iot/alertas | 201 | Sí | — |
| GET | /iot/alertas/1343 | 200 | Sí | — |
| POST | /iot/telemetria | 201 | Sí | — |
| GET | /iot/monitoreo/dashboard | 200 | Sí | — |
| PATCH | /iot/alertas/1343/estado | 200 | Sí | — |
| PATCH | /iot/alertas/1343/estado | 200 | Sí | — |
| GET | /iot/monitoreo/dashboard | 200 | Sí | — |
| POST | /iot/telemetria | 201 | Sí | — |
| POST | /iot/alertas | 201 | Sí | — |
| GET | /iot/alertas/1344 | 200 | Sí | — |
| POST | /iot/telemetria | 201 | Sí | — |
| GET | /iot/monitoreo/dashboard | 200 | Sí | — |
| PATCH | /iot/alertas/1344/estado | 200 | Sí | — |
| PATCH | /iot/alertas/1344/estado | 200 | Sí | — |
| GET | /iot/monitoreo/dashboard | 200 | Sí | — |
| POST | /iot/telemetria | 201 | Sí | — |
| GET | /iot/monitoreo/dashboard | 200 | Sí | — |
| POST | /iot/telemetria | 201 | Sí | — |
| POST | /iot/alertas | 201 | Sí | — |
| GET | /iot/alertas/1345 | 200 | Sí | — |
| POST | /iot/telemetria | 201 | Sí | — |
| GET | /iot/monitoreo/dashboard | 200 | Sí | — |
| PATCH | /iot/alertas/1345/estado | 200 | Sí | — |
| GET | /iot/monitoreo/dashboard | 200 | Sí | — |
| DELETE | /test-control/runs/G89-V2-20261030-212919 | 200 | Sí | — |
| POST | /sesiones/ | 200 | N/A | — |
| POST | /sesiones/ | 200 | N/A | — |
| GET | /iot/monitoreo/dashboard | 200 | N/A | — |
| GET | /iot/alertas/1343 | 404 | N/A | {   "error_code": "ALERTA_NO_ENCONTRADA",   "message": "Alerta 1343 no encontrada.",   "fields": [],   "timestamp": "2026-10-30T21:29:34.451244+00:00" } |
| GET | /iot/alertas/1344 | 404 | N/A | {   "error_code": "ALERTA_NO_ENCONTRADA",   "message": "Alerta 1344 no encontrada.",   "fields": [],   "timestamp": "2026-10-30T21:29:34.587811+00:00" } |
| GET | /iot/alertas/1345 | 404 | N/A | {   "error_code": "ALERTA_NO_ENCONTRADA",   "message": "Alerta 1345 no encontrada.",   "fields": [],   "timestamp": "2026-10-30T21:29:34.741797+00:00" } |
| GET | /iot/monitoreo/historial | 200 | N/A | — |

## Cierre y rollback

DELETE /test-control/runs/{id}: HTTP 200. Rollback VERIFICADO por lecturas posteriores. DELETE y lecturas posteriores acreditan reversión de los objetos comprobados.

| Comprobación | HTTP | Coincide |
|---|---:|---|
| dashboard_previo | 200 | Sí |
| alerta_ausente | 404 | Sí |
| alerta_ausente | 404 | Sí |
| alerta_ausente | 404 | Sí |
| telemetrias_ausentes | 200 | Sí |

## Conclusión y acciones concretas

APROBADO. Responsable QA: registrar la comparación V1 → V2 y decidir cierre o derivación de las incidencias acreditadas.
