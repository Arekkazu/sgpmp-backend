# TC-M04-G057 — APROBADO

Grupo G057; casos TC-M04-150, TC-M04-151, TC-M04-152, TC-M04-153; RF-69 v2.1; V1; RUN RUN-G057-V1-20261028-064235; ambiente TEST; autorización AUT-G057-V1-R2-20261028; código local consultado origin/test daefc3a5 (despliegue no verificado); Newman 6.2.2; Cypress no aplica (0).

## Decisión del caso

Agrupado **TC-M04-G057 (RF-69)**; originales **TC-M04-150, TC-M04-151, TC-M04-152, TC-M04-153**.

**Decisión: APROBADO.** Sin ACTIVO previa la 97 se activó sola; al activar la 98 la 97 pasó a DEPRECADO quedando una única ACTIVO de MODELO_ESPECIES_GRANDES; ambos eventos comparten correlacion_id 863155c6-df4d-4c98-b550-c50c8eebbb6e; las activaciones sin notas o con notas de espacios se rechazaron con 422 sin alterar estados.

| Caso | Comprobación | Decisión | Motivo breve |
|---|---|---|---|
| TC-M04-150 | API-150-01 | APROBADO | La versión 97 quedó ACTIVO; el listado mostró solo esa versión y la respuesta no reportó versión deprecada. |
| TC-M04-151 | API-151-01 | APROBADO | La versión 97 quedó DEPRECADO y la 98 ACTIVO; el listado mostró una sola activa del tipo MODELO_ESPECIES_GRANDES sin componente. |
| TC-M04-152 | API-152-01 | APROBADO | La deprecación de 97 y la activación de 98 compartieron el identificador 863155c6-df4d-4c98-b550-c50c8eebbb6e; la activación inicial tuvo 6cb802be-466a-4708-9766-2599b70b9f8b. |
| TC-M04-153 | API-153-01 | APROBADO | Las versiones 99 y 100 quedaron APROBADO tras las activaciones rechazadas con HTTP 422; la 98 siguió ACTIVO. |

**RUN oficial: sí** (registro QA OFICIAL, intento 2; DELETE 200, rollback confirmado y contrastado tras el cierre: 97-100 → 404, sin ACTIVO del tipo). **Qué falta: nada para este grupo.**

## Detalle por caso

### TC-M04-150 — APROBADO

**Qué se hizo:** Se registró la versión 97 APROBADO del tipo MODELO_ESPECIES_GRANDES sin componente; el Veterinario envió una nota de validación no vacía y activó la versión. El Administrador consultó la versión y los listados de activas y deprecadas.
**Qué se esperaba:** La versión nueva debía pasar a ACTIVO sin deprecar otra; el listado debía mostrar solo esa versión activa y la respuesta no debía reportar versión deprecada (RF-69, Fase 5, líneas 2070-2087; Salida 3, líneas 2231-2235; criterio de TC-M04-150 en la matriz).
**Qué se observó:** La activación y el GET de 97 devolvieron HTTP 200 y estado ACTIVO. El listado devolvió HTTP 200 con una sola activa, 97; el de deprecadas devolvió HTTP 200 con total 0. La respuesta de activación no reportó versión deprecada.
**Por qué APROBADO:** La versión 97 quedó como única activa, no apareció una deprecada y la respuesta cumplió la condición sobre versión deprecada.

### TC-M04-151 — APROBADO

**Qué se hizo:** Se registró la versión 98 APROBADO del mismo tipo sin componente; el Administrador envió una nota de validación no vacía y la activó cuando la 97 estaba ACTIVO. Después consultó ambas versiones y el listado filtrado de activas.
**Qué se esperaba:** La 97 debía pasar a DEPRECADO y la 98 a ACTIVO en la misma operación; debía quedar exactamente una ACTIVO del mismo tipo y componente (RF-69, E5, líneas 2183-2190; CA-7, líneas 2307-2311; criterio de TC-M04-151 en la matriz).
**Qué se observó:** La activación de 98 y los GET de 97 y 98 devolvieron HTTP 200; los estados fueron DEPRECADO y ACTIVO, respectivamente. El listado devolvió HTTP 200, total 1, con solo la versión 98 activa de MODELO_ESPECIES_GRANDES sin componente.
**Por qué APROBADO:** Las lecturas posteriores acreditaron la transición de ambas versiones y la unicidad de la activa para ese tipo y componente.

### TC-M04-152 — APROBADO

**Qué se hizo:** El Administrador consultó por API la auditoría de la versión 97 tras la primera activación y las auditorías de 97 y 98 tras activar 98; comparó los identificadores de los eventos de activación y deprecación.
**Qué se esperaba:** Los eventos de deprecación de la anterior y activación de la nueva debían compartir identificador de correlación, diferente del de la primera activación (RF-69, E5, líneas 2191-2192; criterio de TC-M04-152 en la matriz).
**Qué se observó:** Las tres consultas de auditoría devolvieron HTTP 200. La activación inicial de 97 tuvo identificador 6cb802be-466a-4708-9766-2599b70b9f8b; la deprecación de 97 y la activación de 98 tuvieron 863155c6-df4d-4c98-b550-c50c8eebbb6e.
**Por qué APROBADO:** Los dos eventos de la sustitución compartieron identificador y este fue distinto del de la primera activación, lo que permite vincular la transición observada.

### TC-M04-153 — APROBADO

**Qué se hizo:** Se registraron las versiones 99 y 100 APROBADO sin notas; el Veterinario intentó activar 99 sin notas y el Administrador envió solo espacios como notas de 100 e intentó activarla. Luego consultó 99, 100, 98 y el listado de activas.
**Qué se esperaba:** Debían rechazarse ambas activaciones por falta de notas con contenido; 99 y 100 debían seguir APROBADO y la activa previa no debía deprecarse (RF-69, CA-13, líneas 2337-2342; criterio de TC-M04-153 en la matriz).
**Qué se observó:** Activar 99, enviar notas de solo espacios a 100 y activar 100 devolvieron HTTP 422. Los GET devolvieron HTTP 200: 99 y 100 siguieron APROBADO, 98 siguió ACTIVO; el listado devolvió HTTP 200 con solo 98 activa.
**Por qué APROBADO:** Ambas activaciones fueron rechazadas, las versiones sin notas válidas permanecieron APROBADO y la activa previa conservó su estado.

## Esperado y observado

| Caso | Esperado | Observado |
|---|---|---|
| TC-M04-150 | A ACTIVO, ninguna previa deprecada, listado={A}, respuesta sin versión deprecada | APROBADO: A 97 ACTIVO; lista ACTIVO={A}; respuesta sin versión deprecada |
| TC-M04-151 | A DEPRECADO, B ACTIVO, exactamente una ACTIVO de la llave | APROBADO: 97 DEPRECADO, 98 ACTIVO; una ACTIVO en MODELO_ESPECIES_GRANDES/<NULL> |
| TC-M04-152 | VERSION_DEPRECADA(A) y VERSION_ACTIVADA(B) con correlacion_id igual y distinto del de A inicial | APROBADO: VERSION_DEPRECADA(97) y VERSION_ACTIVADA(98) correlacion_id=863155c6-df4d-4c98-b550-c50c8eebbb6e; previa inicial=6cb802be-466a-4708-9766-2599b70b9f8b |
| TC-M04-153 | C/D rechazadas por notas vacías, C/D APROBADO, B ACTIVO | APROBADO: C/D APROBADO sin notas; activar C/D 4xx; activa previa intacta |

## Solicitudes API

| Rol | Operación | HTTP | Tipo de fallo | Estado antes | Estado después | Total | Items/eventos y correlacion_id | Duración ms |
|---|---|---:|---|---|---|---:|---|---:|
| admin | POST /sesiones/ | 200 | — | — | — | — | — | 1082 |
| vet | POST /sesiones/ | 200 | — | — | — | — | — | 636 |
| Administrador | GET /configuracion/variables-ambientales | 200 | — | — | — | 16 | 16 variables | 143 |
| Administrador | GET /prediccion/modelos?[filtro] | 200 | — | — | — | 4 | ACTIVO:57:—, ACTIVO:56:—, ACTIVO:43:—, ACTIVO:42:— | 169 |
| RF-71 interno | POST /prediccion/modelos A | 201 | — | — | APROBADO | — | — | 2759 |
| RF-71 interno | POST /prediccion/modelos B | 201 | — | — | APROBADO | — | — | 381 |
| RF-71 interno | POST /prediccion/modelos C | 201 | — | — | APROBADO | — | — | 417 |
| RF-71 interno | POST /prediccion/modelos D | 201 | — | — | APROBADO | — | — | 359 |
| Veterinario | PATCH /prediccion/modelos/97/notas | 200 | — | APROBADO | APROBADO | — | — | 454 |
| Administrador | PATCH /prediccion/modelos/98/notas | 200 | — | APROBADO | APROBADO | — | — | 134 |
| Administrador | GET /prediccion/modelos?[filtro] | 200 | — | — | — | 0 |  | 139 |
| Veterinario | POST /prediccion/modelos/97/activar | 200 | — | APROBADO | ACTIVO | — | — | 140 |
| Administrador | GET /prediccion/modelos/97 | 200 | — | — | ACTIVO | — | — | 133 |
| Administrador | GET /prediccion/modelos?[filtro] | 200 | — | — | — | 1 | ACTIVO:97:— | 129 |
| Administrador | GET /prediccion/modelos?[filtro] | 200 | — | — | — | 0 |  | 133 |
| Administrador | GET /prediccion/auditoria?[filtro] | 200 | — | — | — | 5 | HISTORIAL_CONSULTADO:97:ce601317-5d48-4194-970d-2f6033096e44, VERSION_ACTIVADA:97:6cb802be-466a-4708-9766-2599b70b9f8b, VERSION_APROBADA:97:3555c94e-303b-459c-a959-6ba41923cf49, VERSION_APROBADA:97:d9ef3e36-b467-4d09-9eda-d0a7e3797201, VERSION_REGISTRADA:97:d7a3b0cb-3de0-4a9f-8ccd-96ee1a4fda68 | 141 |
| Administrador | POST /prediccion/modelos/98/activar | 200 | — | APROBADO | ACTIVO | — | — | 615 |
| Administrador | GET /prediccion/modelos/97 | 200 | — | — | DEPRECADO | — | — | 136 |
| Administrador | GET /prediccion/modelos/98 | 200 | — | — | ACTIVO | — | — | 133 |
| Administrador | GET /prediccion/modelos?[filtro] | 200 | — | — | — | 1 | ACTIVO:98:— | 133 |
| Administrador | GET /prediccion/auditoria?[filtro] | 200 | — | — | — | 7 | HISTORIAL_CONSULTADO:97:98fa8c04-7d7c-4a1e-922d-409736160218, VERSION_DEPRECADA:97:863155c6-df4d-4c98-b550-c50c8eebbb6e, HISTORIAL_CONSULTADO:97:ce601317-5d48-4194-970d-2f6033096e44, VERSION_ACTIVADA:97:6cb802be-466a-4708-9766-2599b70b9f8b, VERSION_APROBADA:97:3555c94e-303b-459c-a959-6ba41923cf49, VERSION_APROBADA:97:d9ef3e36-b467-4d09-9eda-d0a7e3797201, VERSION_REGISTRADA:97:d7a3b0cb-3de0-4a9f-8ccd-96ee1a4fda68 | 210 |
| Administrador | GET /prediccion/auditoria?[filtro] | 200 | — | — | — | 5 | HISTORIAL_CONSULTADO:98:ac9cfaa6-399f-44c1-a353-a2b951670467, VERSION_ACTIVADA:98:863155c6-df4d-4c98-b550-c50c8eebbb6e, VERSION_APROBADA:98:038e1718-6c43-4aec-99ec-48ed8e6167dc, VERSION_APROBADA:98:bb4def83-3a2e-4343-940b-63811a5d4439, VERSION_REGISTRADA:98:ef40ad0e-ff0e-4c82-bdd1-7e5bd0b55219 | 142 |
| Veterinario | POST /prediccion/modelos/99/activar | 422 | — | APROBADO | — | — | — | 129 |
| Administrador | PATCH /prediccion/modelos/100/notas | 422 | — | APROBADO | — | — | — | 132 |
| Administrador | POST /prediccion/modelos/100/activar | 422 | — | APROBADO | — | — | — | 135 |
| Administrador | GET /prediccion/modelos/99 | 200 | — | — | APROBADO | — | — | 133 |
| Administrador | GET /prediccion/modelos/100 | 200 | — | — | APROBADO | — | — | 132 |
| Administrador | GET /prediccion/modelos/98 | 200 | — | — | ACTIVO | — | — | 135 |
| Administrador | GET /prediccion/modelos?[filtro] | 200 | — | — | — | 1 | ACTIVO:98:— | 132 |
| Sistema | DELETE /test-control/runs/RUN-G057-V1-20261028-064235 | 200 | — | — | — | — | — | 117 |
| Administrador poscierre | GET /prediccion/modelos/97 | 404 | — | — | — | — | — | 137 |
| Administrador poscierre | GET /prediccion/modelos/98 | 404 | — | — | — | — | — | 133 |
| Administrador poscierre | GET /prediccion/modelos/99 | 404 | — | — | — | — | — | 129 |
| Administrador poscierre | GET /prediccion/modelos/100 | 404 | — | — | — | — | — | 137 |
| Administrador poscierre | GET /prediccion/modelos?[filtro] | 200 | — | — | — | 0 |  | 145 |

## Observaciones

- Tipo elegido MODELO_ESPECIES_GRANDES; sin ACTIVO heredada de ese tipo. En TEST se observaron las ACTIVO heredadas 57, 56, 43 y 42, ninguna de MODELO_ESPECIES_GRANDES.
- La respuesta de POST /activar no incluye `version_activa_actual` ni `version_deprecada` (RF-69 Salida 3, líneas 2231-2235; `VersionModeloResponse`, `version_modelo_schema.py:13-41`). No altera el oráculo de TC-M04-151 fijado en la matriz.
- La auditoría de cada versión registrada contiene dos eventos `VERSION_APROBADA` con `correlacion_id` distintos: 97 (3555c94e…, d9ef3e36…) y 98 (038e1718…, bb4def83…). Posible duplicado de RF-73 fuera del alcance de G057; valorar en el grupo que pruebe la auditoría.
- Efectos persistentes posibles fuera del rollback: cuatro ONNX en `MODELOS_STORAGE_PATH`, auditoría de los dos logins y posible respaldo RF-73. Sin correos.

## Incidencias de producto

Sin incidencias de producto confirmadas.

## Problemas técnicos

Intento 1: login del Administrador sin respuesta a unos 30 s, antes de cualquier petición dentro del RUN. Causa técnica QA resuelta en ORD-G057-005: timeout de login ampliado a 120 s y registro del tipo de fallo. En el intento 2 ambos logins respondieron en 1082 y 636 ms; no hubo problema técnico pendiente.

## Historial de intentos

- Intento 1: RUN-G057-V1-20261028-062649; autorización AUT-G057-V1-20261028; exit 2 (`EJECUCION_POST_PREFLIGHT`); preflight OK. Única solicitud: POST /sesiones/ del Administrador sin respuesta a unos 30 s (timeout de 30 s); ninguna petición dentro del RUN. Registro QA TECNICO/PREPARADO, sin efectos remotos; V1 no consumida. La evidencia nativa de este intento se eliminó por decisión del responsable QA el 2026-10-28, tras transcribir aquí su historial desde `resultado.json` y `preflight.json`.
- Intento 2: RUN-G057-V1-20261028-064235; autorización AUT-G057-V1-R2-20261028; registro QA OFICIAL; cuatro casos APROBADOS.

## Cierre y rollback

Operación reintentar; intento 2; 35 solicitudes. DELETE HTTP 200. Rollback comprobado por GET poscierre: GET poscierre: 4 versiones HTTP 404; activos iniciales de MODELO_ESPECIES_GRANDES restaurados (ninguno). Los cuatro ONNX en MODELOS_STORAGE_PATH y posible respaldo RF-73 no quedan cubiertos por DELETE.

## Evidencias

- preflight.json
- newman/newman-G057-A.json
- newman/newman-G057-A.html
- newman/newman-G057-B.json
- newman/newman-G057-B.html
- newman/newman-G057-C.json
- newman/newman-G057-C.html
- newman/newman-G057-D.json
- newman/newman-G057-D.html
- resultado.json
- TC-M04-G057_resultado.md

## Conclusión y acción

Cierre documental de G057: cuatro casos APROBADOS, sin incidencias de producto confirmadas. Conservar las observaciones de Salida 3 y auditoría para los grupos correspondientes y tener presentes los efectos persistentes indicados; no queda comprobación pendiente en este grupo.
