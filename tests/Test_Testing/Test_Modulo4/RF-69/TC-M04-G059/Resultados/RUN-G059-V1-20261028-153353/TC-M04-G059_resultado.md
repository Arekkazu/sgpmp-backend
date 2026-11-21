# TC-M04-G059 — APROBADO

Grupo G059; casos TC-M04-161, TC-M04-162, TC-M04-163, TC-M04-164, TC-M04-165; RF-69 v2.1; V1; RUN RUN-G059-V1-20261028-153353; ambiente TEST; autorización AUT-G059-V1-20261028; código consultado origin/test daefc3a5 (despliegue no verificado); Newman 6.2.2; Cypress no aplica (0).

## Decisión del caso

Agrupado **TC-M04-G059**; originales **TC-M04-161, TC-M04-162, TC-M04-163, TC-M04-164, TC-M04-165**.

**Decisión: APROBADO.** TC-M04-161: La versión 109 siguió APROBADO tras los intentos de cambio; su salida prevista es la activación. TC-M04-162: La versión 108 siguió ACTIVO, en producción y como única activa de su tipo. TC-M04-163: La versión 107 siguió DEPRECADO y se rechazó su reactivación con HTTP 409. TC-M04-164: La versión 110 siguió RECHAZADO, con las mismas métricas y detalle, y se rechazó su activación con HTTP 409. TC-M04-165: La versión 107 siguió ACTIVO hasta activar la 108; entonces pasó a DEPRECADO y esta quedó como única ACTIVO.

| Caso | Comprobación | Decisión | Motivo breve |
|---|---|---|---|
| TC-M04-161 | API-161-01 | APROBADO | La versión 109 siguió APROBADO tras los intentos de cambio; su salida prevista es la activación |
| TC-M04-162 | API-162-01 | APROBADO | La versión 108 siguió ACTIVO, en producción y como única activa de su tipo |
| TC-M04-163 | API-163-01 | APROBADO | La versión 107 siguió DEPRECADO y se rechazó su reactivación con HTTP 409 |
| TC-M04-164 | API-164-01 | APROBADO | La versión 110 siguió RECHAZADO, con las mismas métricas y detalle, y se rechazó su activación con HTTP 409 |
| TC-M04-165 | API-165-01 | APROBADO | La versión 107 siguió ACTIVO hasta activar la 108; entonces pasó a DEPRECADO y esta quedó como única ACTIVO |

**RUN oficial: sí.** **Qué falta: nada para este grupo.**

## Detalle por caso

### TC-M04-161 — APROBADO

**Qué se hizo:** El Administrador envió una nota a la versión 109 con el campo estado_version no declarado en PATCH /prediccion/modelos/109/notas; después intentó llevarla a RECHAZADO, DEPRECADO y EN_VALIDACION mediante PUT y PATCH sobre /prediccion/modelos/109, y consultó la versión tras los intentos.
**Qué se esperaba:** La versión V3 debe conservar APROBADO; no debe pasar a RECHAZADO, DEPRECADO ni EN_VALIDACION; RF-69 v2.1, líneas 1822-1833 y 1887-1888.
**Qué se observó:** La nota respondió HTTP 200; los 6 intentos PUT/PATCH respondieron HTTP 405; las lecturas posteriores mostraron la 109 en APROBADO (esta_produccion=false).
**Por qué APROBADO:** El campo no declarado no cambió el estado; ninguno de los tres destinos se alcanzó y la versión 109 conservó APROBADO. La activación sigue siendo la salida prevista para una versión aprobada.

### TC-M04-162 — APROBADO

**Qué se hizo:** El Administrador envió a la versión 108 una nota con el campo estado_version no declarado en PATCH /prediccion/modelos/108/notas; intentó pasarla a APROBADO, RECHAZADO y EN_VALIDACION con PUT y PATCH sobre /prediccion/modelos/108, y consultó la versión y el listado de activas.
**Qué se esperaba:** La versión activa debe conservar ACTIVO y esta_produccion=true y ser la única ACTIVO de su tipo; RF-69 v2.1, líneas 1822-1833, 1839 y 2307-2311.
**Qué se observó:** La nota respondió HTTP 409 NOTAS_INMUTABLES; los 6 intentos PUT/PATCH respondieron HTTP 405; la lectura final mostró ACTIVO (esta_produccion=true) y el listado devolvió 1 versión activa.
**Por qué APROBADO:** El campo no declarado fue rechazado, los tres cambios propuestos no alteraron a la 108 y la lectura y el listado confirmaron que seguía en producción como única ACTIVO del tipo.

### TC-M04-163 — APROBADO

**Qué se hizo:** El Administrador envió a la versión 107 una nota con el campo estado_version no declarado en PATCH /prediccion/modelos/107/notas; intentó pasarla a APROBADO, ACTIVO, RECHAZADO y EN_VALIDACION con PUT y PATCH, probó POST /prediccion/modelos/107/activar y consultó la versión y su auditoría.
**Qué se esperaba:** V1 debe conservar DEPRECADO; la reactivación debe responder HTTP 409; el criterio menciona describir el intento auditado; RF-69 v2.1, líneas 1817-1833, 2177-2181 y 2302-2305.
**Qué se observó:** La nota respondió HTTP 409 NOTAS_INMUTABLES; los 8 intentos PUT/PATCH respondieron HTTP 405; /activar respondió HTTP 409 TRANSICION_ESTADO_INVALIDA; la lectura final mostró DEPRECADO (esta_produccion=false). No apareció un evento del intento inválido en la auditoría.
**Por qué APROBADO:** La versión 107 permaneció DEPRECADO y la reactivación fue rechazada con HTTP 409. La ausencia del evento del intento se registró como observación por la decisión QA sobre FA-08.

### TC-M04-164 — APROBADO

**Qué se hizo:** Con la versión 110 RECHAZADA (f1 0.7200), el Administrador envió una nota con estado_version no declarado en PATCH /prediccion/modelos/110/notas, intentó llevarla a APROBADO, ACTIVO, DEPRECADO y EN_VALIDACION mediante PUT y PATCH, y probó POST /prediccion/modelos/110/activar. RF-71 interno reenvió el registro con el mismo id_proceso_rf71 y la métrica f1 corregida.
**Qué se esperaba:** La versión rechazada debe conservar RECHAZADO, métricas y detalle; su activación debe responder HTTP 409; RF-69 v2.1, líneas 1819-1833, 2177-2181 y 2302-2305.
**Qué se observó:** La nota respondió HTTP 200; los 8 intentos PUT/PATCH respondieron HTTP 405; /activar respondió HTTP 409 TRANSICION_ESTADO_INVALIDA; el reenvío respondió HTTP 409 RECURSO_DUPLICADO; la lectura final mostró RECHAZADO (esta_produccion=false), con las mismas métricas y detalle registrados.
**Por qué APROBADO:** El campo no declarado no cambió el estado; los cuatro destinos y la activación fueron rechazados, el reenvío no reevaluó a la 110, y sus métricas y detalle permanecieron iguales.

### TC-M04-165 — APROBADO

**Qué se hizo:** El Veterinario había activado la versión 107. El Administrador envió a esa versión una nota con estado_version no declarado en PATCH /prediccion/modelos/107/notas, intentó deprecarla directamente con POST /prediccion/modelos/107/deprecar y PATCH /prediccion/modelos/107/estado, y luego activó la versión 108 con POST /prediccion/modelos/108/activar; consultó ambas versiones, el listado y la auditoría.
**Qué se esperaba:** V1 solo debe pasar a DEPRECADO al activar V2; V2 debe quedar como única ACTIVO; RF-69 v2.1, líneas 1827-1833, 2070-2087, 2183-2192 y 2307-2311.
**Qué se observó:** La nota respondió HTTP 409 NOTAS_INMUTABLES; /deprecar respondió HTTP 404 y /estado HTTP 404; las lecturas previas mantuvieron la 107 en ACTIVO (esta_produccion=true). La activación de 108 respondió HTTP 200; después, 107 quedó DEPRECADO (esta_produccion=false) y 108 ACTIVO (esta_produccion=true), con 1 versión activa en el listado.
**Por qué APROBADO:** El campo no declarado y las dos vías directas no deprecaron a la 107; solo la activación de 108 la llevó a DEPRECADO, dejó a 108 como única ACTIVO y produjo el evento de deprecación verificado en la auditoría.

## Catorce combinaciones

| Caso | Origen → destino | Vías intentadas | Estado después |
|---|---|---|---|
| TC-M04-161 | V3 109 APROBADO → RECHAZADO | PUT HTTP 405; PATCH HTTP 405 | APROBADO |
| TC-M04-161 | V3 109 APROBADO → DEPRECADO | PUT HTTP 405; PATCH HTTP 405 | APROBADO |
| TC-M04-161 | V3 109 APROBADO → EN_VALIDACION | PUT HTTP 405; PATCH HTTP 405 | APROBADO |
| TC-M04-162 | V2 108 ACTIVO → APROBADO | PUT HTTP 405; PATCH HTTP 405 | ACTIVO |
| TC-M04-162 | V2 108 ACTIVO → RECHAZADO | PUT HTTP 405; PATCH HTTP 405 | ACTIVO |
| TC-M04-162 | V2 108 ACTIVO → EN_VALIDACION | PUT HTTP 405; PATCH HTTP 405 | ACTIVO |
| TC-M04-163 | V1 107 DEPRECADO → APROBADO | PUT HTTP 405; PATCH HTTP 405 | DEPRECADO |
| TC-M04-163 | V1 107 DEPRECADO → ACTIVO | PUT HTTP 405; PATCH HTTP 405; POST /activar HTTP 409 | DEPRECADO |
| TC-M04-163 | V1 107 DEPRECADO → RECHAZADO | PUT HTTP 405; PATCH HTTP 405 | DEPRECADO |
| TC-M04-163 | V1 107 DEPRECADO → EN_VALIDACION | PUT HTTP 405; PATCH HTTP 405 | DEPRECADO |
| TC-M04-164 | R 110 RECHAZADO → APROBADO | PUT HTTP 405; PATCH HTTP 405 | RECHAZADO |
| TC-M04-164 | R 110 RECHAZADO → ACTIVO | PUT HTTP 405; PATCH HTTP 405; POST /activar HTTP 409 | RECHAZADO |
| TC-M04-164 | R 110 RECHAZADO → DEPRECADO | PUT HTTP 405; PATCH HTTP 405 | RECHAZADO |
| TC-M04-164 | R 110 RECHAZADO → EN_VALIDACION | PUT HTTP 405; PATCH HTTP 405 | RECHAZADO |

## Observaciones

- PATCH /notas V3: HTTP 200, estado intacto; respuesta 2xx observada
- PATCH /notas R: HTTP 200, estado intacto; respuesta 2xx observada
- 163: sin evento del intento inválido; FA-08 no localizado en RF-69 v2.1

## Incidencias de producto

Sin incidencias confirmadas.

## Problemas técnicos

Sin problemas técnicos.

## Historial de intentos API

| Caso | Rol | Solicitud | HTTP | Estado | Duración ms |
|---|---|---|---:|---|---:|
| preparación/cierre | admin | POST /sesiones/ | 200 | — | 1057 |
| preparación/cierre | vet | POST /sesiones/ | 200 | — | 668 |
| preparación/cierre | Administrador | GET /configuracion/variables-ambientales | 200 | — | 215 |
| preparación/cierre | Administrador | GET /prediccion/modelos?[filtro] | 200 | — | 151 |
| preparación/cierre | RF-71 interno | POST /prediccion/modelos | 201 | APROBADO | 3163 |
| preparación/cierre | RF-71 interno | POST /prediccion/modelos | 201 | APROBADO | 368 |
| preparación/cierre | RF-71 interno | POST /prediccion/modelos | 201 | APROBADO | 409 |
| preparación/cierre | RF-71 interno | POST /prediccion/modelos | 200 | RECHAZADO | 35901 |
| preparación/cierre | Veterinario | PATCH /prediccion/modelos/107/notas | 200 | APROBADO | 788 |
| preparación/cierre | Administrador | PATCH /prediccion/modelos/108/notas | 200 | APROBADO | 392 |
| TC-M04-161 | Administrador | PATCH /prediccion/modelos/109/notas | 200 | APROBADO | 155 |
| TC-M04-161 | Administrador | GET /prediccion/modelos/109 | 200 | APROBADO | 138 |
| TC-M04-164 | Administrador | PATCH /prediccion/modelos/110/notas | 200 | RECHAZADO | 161 |
| TC-M04-164 | Administrador | GET /prediccion/modelos/110 | 200 | RECHAZADO | 136 |
| preparación/cierre | Veterinario | POST /prediccion/modelos/107/activar | 200 | ACTIVO | 147 |
| TC-M04-165 | Administrador | GET /prediccion/auditoria?[filtro] | 200 | — | 140 |
| TC-M04-165 | Administrador | PATCH /prediccion/modelos/107/notas | 409 | — | 141 |
| TC-M04-165 | Administrador | GET /prediccion/modelos/107 | 200 | ACTIVO | 132 |
| TC-M04-165 | Administrador | POST /prediccion/modelos/107/deprecar | 404 | — | 131 |
| TC-M04-165 | Administrador | GET /prediccion/modelos/107 | 200 | ACTIVO | 132 |
| TC-M04-165 | Administrador | PATCH /prediccion/modelos/107/estado | 404 | — | 131 |
| TC-M04-165 | Administrador | GET /prediccion/modelos/107 | 200 | ACTIVO | 142 |
| TC-M04-165 | Administrador | POST /prediccion/modelos/108/activar | 200 | ACTIVO | 160 |
| TC-M04-165 | Administrador | GET /prediccion/modelos/107 | 200 | DEPRECADO | 145 |
| TC-M04-165 | Administrador | GET /prediccion/modelos/108 | 200 | ACTIVO | 140 |
| TC-M04-165 | Administrador | GET /prediccion/modelos?[filtro] | 200 | — | 133 |
| TC-M04-165 | Administrador | GET /prediccion/auditoria?[filtro] | 200 | — | 224 |
| TC-M04-162 | Administrador | GET /prediccion/auditoria?[filtro] | 200 | — | 215 |
| TC-M04-162 | Administrador | PATCH /prediccion/modelos/108/notas | 409 | — | 141 |
| TC-M04-162 | Administrador | GET /prediccion/modelos/108 | 200 | ACTIVO | 134 |
| TC-M04-162 | Administrador | PUT /prediccion/modelos/108 | 405 | — | 129 |
| TC-M04-162 | Administrador | PATCH /prediccion/modelos/108 | 405 | — | 119 |
| TC-M04-162 | Administrador | GET /prediccion/modelos/108 | 200 | ACTIVO | 143 |
| TC-M04-162 | Administrador | PUT /prediccion/modelos/108 | 405 | — | 118 |
| TC-M04-162 | Administrador | PATCH /prediccion/modelos/108 | 405 | — | 131 |
| TC-M04-162 | Administrador | GET /prediccion/modelos/108 | 200 | ACTIVO | 137 |
| TC-M04-162 | Administrador | PUT /prediccion/modelos/108 | 405 | — | 133 |
| TC-M04-162 | Administrador | PATCH /prediccion/modelos/108 | 405 | — | 122 |
| TC-M04-162 | Administrador | GET /prediccion/modelos/108 | 200 | ACTIVO | 142 |
| TC-M04-162 | Administrador | GET /prediccion/modelos/108 | 200 | ACTIVO | 136 |
| TC-M04-162 | Administrador | GET /prediccion/modelos?[filtro] | 200 | — | 148 |
| TC-M04-162 | Administrador | GET /prediccion/auditoria?[filtro] | 200 | — | 161 |
| TC-M04-163 | Administrador | GET /prediccion/auditoria?[filtro] | 200 | — | 167 |
| TC-M04-163 | Administrador | PATCH /prediccion/modelos/107/notas | 409 | — | 132 |
| TC-M04-163 | Administrador | GET /prediccion/modelos/107 | 200 | DEPRECADO | 143 |
| TC-M04-163 | Administrador | PUT /prediccion/modelos/107 | 405 | — | 120 |
| TC-M04-163 | Administrador | PATCH /prediccion/modelos/107 | 405 | — | 130 |
| TC-M04-163 | Administrador | GET /prediccion/modelos/107 | 200 | DEPRECADO | 132 |
| TC-M04-163 | Administrador | PUT /prediccion/modelos/107 | 405 | — | 128 |
| TC-M04-163 | Administrador | PATCH /prediccion/modelos/107 | 405 | — | 119 |
| TC-M04-163 | Administrador | GET /prediccion/modelos/107 | 200 | DEPRECADO | 146 |
| TC-M04-163 | Administrador | PUT /prediccion/modelos/107 | 405 | — | 122 |
| TC-M04-163 | Administrador | PATCH /prediccion/modelos/107 | 405 | — | 135 |
| TC-M04-163 | Administrador | GET /prediccion/modelos/107 | 200 | DEPRECADO | 134 |
| TC-M04-163 | Administrador | PUT /prediccion/modelos/107 | 405 | — | 130 |
| TC-M04-163 | Administrador | PATCH /prediccion/modelos/107 | 405 | — | 119 |
| TC-M04-163 | Administrador | GET /prediccion/modelos/107 | 200 | DEPRECADO | 145 |
| TC-M04-163 | Administrador | POST /prediccion/modelos/107/activar | 409 | — | 146 |
| TC-M04-163 | Administrador | GET /prediccion/modelos/107 | 200 | DEPRECADO | 144 |
| TC-M04-163 | Administrador | GET /prediccion/modelos/107 | 200 | DEPRECADO | 144 |
| TC-M04-163 | Administrador | GET /prediccion/modelos?[filtro] | 200 | — | 141 |
| TC-M04-163 | Administrador | GET /prediccion/auditoria?[filtro] | 200 | — | 234 |
| TC-M04-164 | Administrador | GET /prediccion/auditoria?[filtro] | 200 | — | 232 |
| TC-M04-164 | Administrador | PUT /prediccion/modelos/110 | 405 | — | 120 |
| TC-M04-164 | Administrador | PATCH /prediccion/modelos/110 | 405 | — | 131 |
| TC-M04-164 | Administrador | GET /prediccion/modelos/110 | 200 | RECHAZADO | 136 |
| TC-M04-164 | Administrador | PUT /prediccion/modelos/110 | 405 | — | 134 |
| TC-M04-164 | Administrador | PATCH /prediccion/modelos/110 | 405 | — | 140 |
| TC-M04-164 | Administrador | GET /prediccion/modelos/110 | 200 | RECHAZADO | 146 |
| TC-M04-164 | Administrador | PUT /prediccion/modelos/110 | 405 | — | 118 |
| TC-M04-164 | Administrador | PATCH /prediccion/modelos/110 | 405 | — | 128 |
| TC-M04-164 | Administrador | GET /prediccion/modelos/110 | 200 | RECHAZADO | 134 |
| TC-M04-164 | Administrador | PUT /prediccion/modelos/110 | 405 | — | 130 |
| TC-M04-164 | Administrador | PATCH /prediccion/modelos/110 | 405 | — | 119 |
| TC-M04-164 | Administrador | GET /prediccion/modelos/110 | 200 | RECHAZADO | 148 |
| TC-M04-164 | Administrador | POST /prediccion/modelos/110/activar | 409 | — | 131 |
| TC-M04-164 | Administrador | GET /prediccion/modelos/110 | 200 | RECHAZADO | 147 |
| TC-M04-164 | RF-71 interno | POST /prediccion/modelos | 409 | — | 455 |
| TC-M04-164 | Administrador | GET /prediccion/modelos/110 | 200 | RECHAZADO | 143 |
| TC-M04-164 | Administrador | GET /prediccion/modelos?[filtro] | 200 | — | 140 |
| TC-M04-164 | Administrador | GET /prediccion/auditoria?[filtro] | 200 | — | 164 |
| TC-M04-161 | Administrador | GET /prediccion/auditoria?[filtro] | 200 | — | 225 |
| TC-M04-161 | Administrador | PUT /prediccion/modelos/109 | 405 | — | 134 |
| TC-M04-161 | Administrador | PATCH /prediccion/modelos/109 | 405 | — | 121 |
| TC-M04-161 | Administrador | GET /prediccion/modelos/109 | 200 | APROBADO | 142 |
| TC-M04-161 | Administrador | PUT /prediccion/modelos/109 | 405 | — | 119 |
| TC-M04-161 | Administrador | PATCH /prediccion/modelos/109 | 405 | — | 131 |
| TC-M04-161 | Administrador | GET /prediccion/modelos/109 | 200 | APROBADO | 146 |
| TC-M04-161 | Administrador | PUT /prediccion/modelos/109 | 405 | — | 129 |
| TC-M04-161 | Administrador | PATCH /prediccion/modelos/109 | 405 | — | 124 |
| TC-M04-161 | Administrador | GET /prediccion/modelos/109 | 200 | APROBADO | 143 |
| TC-M04-161 | Administrador | GET /prediccion/modelos/109 | 200 | APROBADO | 134 |
| TC-M04-161 | Administrador | GET /prediccion/modelos?[filtro] | 200 | — | 145 |
| TC-M04-161 | Administrador | GET /prediccion/auditoria?[filtro] | 200 | — | 149 |
| preparación/cierre | Sistema | DELETE /test-control/runs/RUN-G059-V1-20261028-153353 | 200 | — | 129 |
| preparación/cierre | Administrador poscierre | GET /prediccion/modelos/107 | 404 | — | 136 |
| preparación/cierre | Administrador poscierre | GET /prediccion/modelos/108 | 404 | — | 143 |
| preparación/cierre | Administrador poscierre | GET /prediccion/modelos/109 | 404 | — | 135 |
| preparación/cierre | Administrador poscierre | GET /prediccion/modelos/110 | 404 | — | 144 |
| preparación/cierre | Administrador poscierre | GET /prediccion/modelos?[filtro] | 200 | — | 167 |

## Cierre y rollback

Operación evaluar; intento 1; 100 solicitudes. DELETE HTTP 200. Rollback comprobado por API: GET poscierre: 4 versiones HTTP 404; listado ACTIVO restaurado. Cuatro o cinco ONNX y posible respaldo RF-73 quedan fuera del DELETE; correo de R a cada usuario con permiso 43/3 irreversible.

## Evidencias

- preflight.json
- newman/newman-G059-V1.json
- newman/newman-G059-V1.html
- newman/newman-G059-V2.json
- newman/newman-G059-V2.html
- newman/newman-G059-V3.json
- newman/newman-G059-V3.html
- newman/newman-G059-R.json
- newman/newman-G059-R.html
- newman/newman-G059-R2.json
- newman/newman-G059-R2.html
- resultado.json
- TC-M04-G059_resultado.md

## Conclusión y acción

Entregar al registro QA y revisar incidencias y efectos persistentes.
