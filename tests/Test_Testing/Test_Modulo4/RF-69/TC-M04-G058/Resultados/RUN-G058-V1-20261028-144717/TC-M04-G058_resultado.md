# TC-M04-G058 — APROBADO

Grupo G058; casos TC-M04-157, TC-M04-158, TC-M04-159; RF-69 v2.1; V1; RUN RUN-G058-V1-20261028-144717; ambiente TEST; autorización AUT-G058-V1-R2-20261028; código consultado origin/test daefc3a5 (despliegue no verificado); Newman 6.2.2; Cypress no aplica (0).

## Decisión del caso

Agrupado **TC-M04-G058 (RF-69)**; originales **TC-M04-157, TC-M04-158, TC-M04-159**.

**Decisión: APROBADO.** Activar una versión que no está APROBADA respondió siempre HTTP 409 sin cambiar estados: la 105 ACTIVA, la 104 DEPRECADA y la 106 RECHAZADA (con ambos roles) siguieron igual y la 105 continuó como única ACTIVA de MODELO_ESPECIES_GRANDES.

| Caso | Comprobación | Decisión | Motivo breve |
|---|---|---|---|
| TC-M04-157 | API-157-01 | APROBADO | Ambos roles recibieron HTTP 409; la versión 106 siguió RECHAZADA, la 105 siguió ACTIVA y no hubo transiciones de estado nuevas. |
| TC-M04-158 | API-158-01 | APROBADO | El intento recibió HTTP 409; la versión 104 siguió DEPRECADA, la 105 siguió ACTIVA y no hubo transiciones de estado nuevas. La ausencia de evento del intento quedó como observación según la decisión QA sobre FA-08. |
| TC-M04-159 | API-159-01 | APROBADO | La repetición recibió HTTP 409 VERSION_NO_APROBADA; la versión 105 siguió ACTIVA y en producción, fue la única activa del tipo y no se duplicaron eventos de estado. |

**RUN oficial: sí.** **Qué falta: nada para este grupo.**

## Detalle por caso

### TC-M04-157 — APROBADO

**Qué se hizo:** Se registró la versión 106 con F1 0.72 y recall 0.95; respondió HTTP 200 RECHAZADO en 31 058 ms. Veterinario y Administrador intentaron POST /prediccion/modelos/106/activar. Se consultaron la 106, la versión activa 105, el listado y la auditoría.
**Qué se esperaba:** Ambos roles debían recibir HTTP 409; la 106 debía seguir RECHAZADA, la versión ACTIVA debía permanecer intacta y no debía haber transiciones de estado nuevas (RF-69 E4, líneas 2177-2181; CA-5, líneas 2297-2300; CA-6, líneas 2302-2305).
**Qué se observó:** Los dos POST devolvieron HTTP 409 TRANSICION_ESTADO_INVALIDA. GET /prediccion/modelos/106 devolvió HTTP 200 RECHAZADO y esta_produccion false. GET /prediccion/modelos/105 devolvió HTTP 200 ACTIVO antes y después; el listado mostró solo la 105. La auditoría de la 106 no añadió transiciones de estado al excluir HISTORIAL_CONSULTADO, generado por las lecturas.
**Por qué APROBADO:** Ambos roles recibieron el 409 exigido; la 106 conservó RECHAZADO, la 105 conservó ACTIVO y siguió como única activa, y no apareció una transición de estado nueva en la auditoría.

### TC-M04-158 — APROBADO

**Qué se hizo:** Se activó la versión 104 con Veterinario (HTTP 200 ACTIVO) y después la 105 con Administrador (HTTP 200 ACTIVO), lo que dejó la 104 DEPRECADA. Administrador intentó POST /prediccion/modelos/104/activar; luego se consultaron ambas versiones y sus auditorías.
**Qué se esperaba:** La reactivación debía recibir HTTP 409; la 104 debía permanecer DEPRECADA, la 105 no debía cambiar y no debían aparecer transiciones de estado nuevas (RF-69 transiciones, líneas 1829-1833; E4, líneas 2177-2181; CA-6, líneas 2302-2305).
**Qué se observó:** El POST devolvió HTTP 409 TRANSICION_ESTADO_INVALIDA; GET /prediccion/modelos/104 devolvió HTTP 200 DEPRECADO y esta_produccion false; GET /prediccion/modelos/105 devolvió HTTP 200 ACTIVO y esta_produccion true. No hubo transiciones nuevas en las auditorías al excluir HISTORIAL_CONSULTADO. Tampoco se generó un evento propio del intento rechazado.
**Por qué APROBADO:** El 409 impidió reactivar la 104; esta siguió DEPRECADA, la 105 siguió ACTIVA y no hubo transición nueva. La ausencia de un evento propio del intento quedó como observación: QA no localizó en RF-69 v2.1 un oráculo verificable para FA-08 que permita exigirlo como condición de aprobación.

### TC-M04-159 — APROBADO

**Qué se hizo:** Con la versión 105 ya ACTIVA, Veterinario repitió POST /prediccion/modelos/105/activar. Después se consultaron la 105, el listado de MODELO_ESPECIES_GRANDES y la auditoría.
**Qué se esperaba:** La repetición debía recibir HTTP 409; la 105 debía seguir ACTIVA y en producción, ser la única versión activa del tipo y no duplicar eventos de estado (RF-69 E4, líneas 2177-2181; CA-5, líneas 2297-2300; Fase 6, líneas 2089-2099).
**Qué se observó:** El POST devolvió HTTP 409 VERSION_NO_APROBADA. GET /prediccion/modelos/105 devolvió HTTP 200 ACTIVO con esta_produccion true; el listado tuvo un solo elemento, la 105 ACTIVA de MODELO_ESPECIES_GRANDES. La auditoría conservó los eventos de estado previos, sin duplicados nuevos al excluir HISTORIAL_CONSULTADO.
**Por qué APROBADO:** La API rechazó la activación repetida con HTTP 409; la 105 conservó ACTIVO y esta_produccion true, siguió como única activa del tipo y no se duplicaron eventos de estado.

## Esperado y observado

| Caso | Esperado | Observado |
|---|---|---|
| TC-M04-157 | Ambos roles HTTP 409; la 106 permanece RECHAZADA, la 105 ACTIVA no cambia y no hay transiciones nuevas. | APROBADO: dos HTTP 409 TRANSICION_ESTADO_INVALIDA; 106 RECHAZADO, 105 ACTIVO y sin transiciones nuevas. |
| TC-M04-158 | HTTP 409; la 104 permanece DEPRECADA, la 105 no cambia y no hay transiciones nuevas. | APROBADO: HTTP 409 TRANSICION_ESTADO_INVALIDA; 104 DEPRECADO, 105 ACTIVO y sin transiciones nuevas. |
| TC-M04-159 | HTTP 409; la 105 permanece ACTIVA y en producción, única activa del tipo, sin duplicar eventos de estado. | APROBADO: HTTP 409 VERSION_NO_APROBADA; 105 ACTIVO y esta_produccion true, única ACTIVA del tipo, sin duplicados nuevos. |

## Solicitudes API

| Rol | Operación | HTTP | Estado antes | Estado después | Eventos/items | Duración ms |
|---|---|---:|---|---|---|---:|
| admin | POST /sesiones/ | 200 | — | — | — | 910 |
| vet | POST /sesiones/ | 200 | — | — | — | 633 |
| Administrador | GET /configuracion/variables-ambientales | 200 | — | — | null:null, null:null, null:null, null:null, null:null, null:null, null:null, null:null, null:null, null:null, null:null, null:null, null:null, null:null, null:null, null:null | 151 |
| Administrador | GET /prediccion/modelos?[filtro] | 200 | — | — |  | 159 |
| RF-71 interno | POST /prediccion/modelos A | 201 | — | APROBADO | — | 2966 |
| RF-71 interno | POST /prediccion/modelos B | 201 | — | APROBADO | — | 386 |
| RF-71 interno | POST /prediccion/modelos R | 200 | — | RECHAZADO | — | 31058 |
| Veterinario | PATCH /prediccion/modelos/104/notas | 200 | APROBADO | APROBADO | — | 491 |
| Administrador | PATCH /prediccion/modelos/105/notas | 200 | APROBADO | APROBADO | — | 388 |
| Veterinario | POST /prediccion/modelos/104/activar | 200 | APROBADO | ACTIVO | — | 158 |
| Administrador | POST /prediccion/modelos/105/activar | 200 | APROBADO | ACTIVO | — | 152 |
| Administrador | GET /prediccion/modelos/104 | 200 | — | DEPRECADO | — | 141 |
| Administrador | GET /prediccion/modelos/105 | 200 | — | ACTIVO | — | 144 |
| Administrador | GET /prediccion/auditoria?[filtro] | 200 | — | — | HISTORIAL_CONSULTADO:104, VERSION_DEPRECADA:104, VERSION_ACTIVADA:104, VERSION_APROBADA:104, VERSION_APROBADA:104, VERSION_REGISTRADA:104 | 155 |
| Administrador | GET /prediccion/auditoria?[filtro] | 200 | — | — | HISTORIAL_CONSULTADO:105, VERSION_ACTIVADA:105, VERSION_APROBADA:105, VERSION_APROBADA:105, VERSION_REGISTRADA:105 | 152 |
| Administrador | GET /prediccion/auditoria?[filtro] | 200 | — | — | VERSION_RECHAZADA:106, VERSION_REGISTRADA:106 | 140 |
| Veterinario | POST /prediccion/modelos/105/activar | 409 | ACTIVO | — | — | 134 |
| Administrador | GET /prediccion/modelos/105 | 200 | — | ACTIVO | — | 142 |
| Administrador | GET /prediccion/modelos?[filtro] | 200 | — | — | ACTIVO:105 | 143 |
| Administrador | GET /prediccion/auditoria?[filtro] | 200 | — | — | HISTORIAL_CONSULTADO:105, HISTORIAL_CONSULTADO:105, VERSION_ACTIVADA:105, VERSION_APROBADA:105, VERSION_APROBADA:105, VERSION_REGISTRADA:105 | 155 |
| Administrador | POST /prediccion/modelos/104/activar | 409 | DEPRECADO | — | — | 132 |
| Administrador | GET /prediccion/modelos/104 | 200 | — | DEPRECADO | — | 136 |
| Administrador | GET /prediccion/modelos/105 | 200 | — | ACTIVO | — | 135 |
| Administrador | GET /prediccion/auditoria?[filtro] | 200 | — | — | HISTORIAL_CONSULTADO:104, HISTORIAL_CONSULTADO:104, VERSION_DEPRECADA:104, VERSION_ACTIVADA:104, VERSION_APROBADA:104, VERSION_APROBADA:104, VERSION_REGISTRADA:104 | 153 |
| Administrador | GET /prediccion/auditoria?[filtro] | 200 | — | — | HISTORIAL_CONSULTADO:105, HISTORIAL_CONSULTADO:105, HISTORIAL_CONSULTADO:105, VERSION_ACTIVADA:105, VERSION_APROBADA:105, VERSION_APROBADA:105, VERSION_REGISTRADA:105 | 150 |
| Administrador | GET /prediccion/modelos/105 | 200 | — | ACTIVO | — | 143 |
| Veterinario | POST /prediccion/modelos/106/activar | 409 | RECHAZADO | — | — | 136 |
| Administrador | POST /prediccion/modelos/106/activar | 409 | RECHAZADO | — | — | 144 |
| Administrador | GET /prediccion/modelos/105 | 200 | — | ACTIVO | — | 140 |
| Administrador | GET /prediccion/modelos/106 | 200 | — | RECHAZADO | — | 138 |
| Administrador | GET /prediccion/modelos?[filtro] | 200 | — | — | ACTIVO:105 | 138 |
| Administrador | GET /prediccion/auditoria?[filtro] | 200 | — | — | HISTORIAL_CONSULTADO:106, VERSION_RECHAZADA:106, VERSION_REGISTRADA:106 | 263 |
| Sistema | DELETE /test-control/runs/RUN-G058-V1-20261028-144717 | 200 | — | — | — | 129 |
| Administrador poscierre | GET /prediccion/modelos/104 | 404 | — | — | — | 140 |
| Administrador poscierre | GET /prediccion/modelos/105 | 404 | — | — | — | 140 |
| Administrador poscierre | GET /prediccion/modelos/106 | 404 | — | — | — | 136 |
| Administrador poscierre | GET /prediccion/modelos?[filtro] | 200 | — | — |  | 142 |

## Observaciones

- 158: no se genera evento de auditoría para el intento rechazado; sin requisito normativo localizado

## Incidencias de producto

Sin incidencias de producto confirmadas.

## Problemas técnicos

Sin problemas técnicos.

## Historial de intentos, cierre y rollback

### Intento 1 — RUN-G058-V1-20261028-143302

Exit 2, EJECUCION_POST_PREFLIGHT; registro QA TÉCNICO y V1 ABIERTA. A 101 y B 102: HTTP 201 APROBADO; R 103: HTTP 200 RECHAZADO con eco e ID, 34,9 s y correo síncrono enviado. Preparación: A DEPRECADO y B ACTIVO (HTTP 200). TC-M04-159: activar 102 devolvió 409 VERSION_NO_APROBADA; B siguió ACTIVO, sin eventos nuevos: APROBADO. TC-M04-158: activar 101 devolvió 409 TRANSICION_ESTADO_INVALIDA; A siguió DEPRECADO, B intacta y sin evento del intento observado: APROBADO. TC-M04-157: NO_CONCLUYENTE por clasificación técnica de R como ambigua; no se envió POST /103/activar, aunque GET posterior confirmó RECHAZADO. Causa técnica: el ejecutor exigía 201 a los tres registros y el ensayo respondía 201 a todos. DELETE HTTP 200; rollback NO_VERIFICADO. Evidencia nativa eliminada por decisión del responsable QA el 2026-10-28; este párrafo conserva la transcripción del intento 1.

Operación reintentar; intento 2; 37 solicitudes. DELETE HTTP 200. Rollback comprobado por API: GET poscierre: 3 versiones HTTP 404; listado ACTIVO restaurado. Tres ONNX y posible respaldo RF-73 no quedan cubiertos por DELETE; el aviso por correo a cada usuario activo con permiso 43/3 es irreversible.

## Evidencias

- preflight.json
- newman/newman-G058-A.html
- newman/newman-G058-A.json
- newman/newman-G058-B.html
- newman/newman-G058-B.json
- newman/newman-G058-R.html
- newman/newman-G058-R.json
- resultado.json
- TC-M04-G058_resultado.md

## Conclusión y acción

Entregar al registro QA y revisar incidencias y efectos persistentes.
