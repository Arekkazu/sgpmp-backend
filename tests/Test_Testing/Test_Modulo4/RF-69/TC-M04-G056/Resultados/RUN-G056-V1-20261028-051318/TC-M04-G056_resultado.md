# TC-M04-G056 — APROBADO

Grupo G056; casos TC-M04-146, TC-M04-147, TC-M04-148, TC-M04-149; RF-69 v2.1; V1; RUN RUN-G056-V1-20261028-051318; ambiente TEST; autorización AUT-G056-V1-R2-20261028; código local consultado daefc3a5 (despliegue no verificado); Newman 6.2.2; Cypress no aplica: 0 ejecuciones.

## Decisión del caso

Agrupado **TC-M04-G056 (RF-69)**; casos originales **TC-M04-146, TC-M04-147, TC-M04-148 y TC-M04-149**.

**Decisión: APROBADO.** Ambos roles registran notas sin alterar el estado; una versión RECHAZADA solo admite consulta; la versión aprobada persiste sin activarse; el listado y sus filtros devuelven estado y métricas.

| Caso | Comprobación | Decisión | Motivo breve |
|---|---|---|---|
| TC-M04-146 | API-146-01 | APROBADO | Notas 200/200 de Veterinario y Administrador, consultables; V1 y V1b siguen APROBADO. |
| TC-M04-147 | API-147-01 | APROBADO | V2 RECHAZADO consultable; modificación 405 y activación 409; transiciones intactas 2/2 por rol. |
| TC-M04-148 | API-148-01 | APROBADO | V1 con nota sigue APROBADO tras V3 y `esta_produccion=false`. |
| TC-M04-149 | API-149-01 | APROBADO | Ambos roles: 26 sin filtro, 5 por tipo, 2 RECHAZADO y 3 APROBADO; cuatro versiones del RUN con estado y métricas. |

**RUN oficial: sí** (registro QA OFICIAL, intento 2; DELETE 200, rollback confirmado por el sandbox, sin lectura posterior de BD).

**Qué falta:** nada para este grupo; queda una observación de datos heredados en TEST.

## Detalle por caso

### TC-M04-146 — APROBADO
**Qué se hizo:** Se registraron dos versiones aprobadas del mismo tipo: V1, id 93, y V1b, id 94. El Veterinario envió a la 93 la nota «G056 RUN-G056-V1-20261028-051318 Veterinario nota clínica» y el Administrador envió a la 94 la nota «G056 RUN-G056-V1-20261028-051318 Administrador nota clínica»; cada rol consultó después su versión.
**Qué se esperaba:** Las notas debían quedar asociadas y consultables, sin cambiar el estado, y ambos roles debían poder registrarlas (matriz G056, «Documentacion de los resultados de la prueba», punto 1; RF-69 v2.1, líneas 1792, 1968, 2045-2063 y 2369-2376).
**Qué se observó:** Los dos registros respondieron HTTP 201 con estado APROBADO. Ambos envíos de notas y ambas consultas respondieron HTTP 200; la 93 conservó la nota del Veterinario y la 94 la del Administrador, las dos en APROBADO.
**Por qué APROBADO:** Se verificó el permiso de cada rol sobre una versión distinta, la persistencia de cada texto al consultar y la conservación del estado APROBADO en ambas.

### TC-M04-147 — APROBADO
**Qué se hizo:** Se consultaron la versión V2 rechazada, id 95, y su historial con Administrador y Veterinario. Cada rol intentó cambiar su estado a APROBADO con PUT y PATCH, activarla, y modificar o borrar su historial con PUT, PATCH y DELETE; después repitió las consultas.
**Qué se esperaba:** Debían poder consultarse métricas e historial, sin permitir cambiar el estado, activar la versión ni intervenir sus transiciones (matriz G056, «Documentacion de los resultados de la prueba», punto 2; RF-69 v2.1, líneas 1887-1891, 2048-2059, 2177-2181 y 2313-2315).
**Qué se observó:** V2 se registró con HTTP 200 y estado RECHAZADO. Ambos roles obtuvieron HTTP 200 al consultar la versión y el historial antes y después, con métricas completas; PUT y PATCH sobre la versión y PUT, PATCH y DELETE sobre el historial devolvieron HTTP 405, y la activación devolvió HTTP 409. La versión siguió RECHAZADA y cada rol conservó las mismas dos transiciones antes y después.
**Por qué APROBADO:** Se pudieron consultar métricas e historial, se rechazaron todos los cambios intentados y la activación, y no cambió ninguna transición. Los eventos de consulta creados por las propias consultas GET de auditoría realizadas en este RUN se ignoraron al comparar el historial porque no son intervenciones sobre sus transiciones.

### TC-M04-148 — APROBADO
**Qué se hizo:** Se dejó sin activar V1, id 93, con la nota del Veterinario; después se registró V3, id 96, del mismo tipo y el Administrador volvió a consultar la 93.
**Qué se esperaba:** La versión aprobada con notas debía permanecer APROBADA, sin activarse sola y disponible para activación (matriz G056, «Documentacion de los resultados de la prueba», punto 3; RF-69 v2.1, líneas 1814-1832 y 2061-2068).
**Qué se observó:** V3 se registró con HTTP 201 y estado APROBADO. La consulta posterior de la 93 respondió HTTP 200: conservó la nota clínica, el estado APROBADO y el indicador de producción en falso.
**Por qué APROBADO:** La nueva versión no cambió el estado de la 93 ni la activó automáticamente; al seguir APROBADA, conserva la condición de elegibilidad para activación prevista por RF-69. No se ejecutó una activación de la 93 en este caso.

### TC-M04-149 — APROBADO
**Qué se hizo:** Administrador y Veterinario consultaron el listado de modelos sin filtro, por tipo MODELO_ESPECIES_GRANDES, por estado RECHAZADO y por estado APROBADO. Se revisaron las versiones del RUN: 93, 94, 95 y 96.
**Qué se esperaba:** El listado debía devolver estado y métricas completas y acotar correctamente cada filtro (matriz G056, «Documentacion de los resultados de la prueba», punto 4; RF-69 v2.1, líneas 2048-2051 y 2204-2223).
**Qué se observó:** Las ocho consultas respondieron HTTP 200. Cada rol recibió 26 versiones sin filtro, 5 del tipo solicitado, 2 RECHAZADAS y 3 APROBADAS. Las versiones 93, 94 y 96 figuraron APROBADAS y la 95 RECHAZADA; las cuatro mostraron las siete métricas. También aparecieron registros heredados con datos incompletos o sin tipo.
**Por qué APROBADO:** Ambos roles recibieron los mismos conjuntos acotados por tipo y estado, y las cuatro versiones creadas en el RUN tuvieron estado y métricas completas. Los datos heredados se registraron como observación; no demostraron un defecto del listado probado aquí.

### Esperado y observado por caso

| Caso | Comprobación | Esperado | Estado | Observado y motivo |
|---|---|---|---|---|
| TC-M04-146 | API-146-01 | Las notas quedan asociadas y consultables; el estado no cambia al registrarlas; ambos roles pueden hacerlo | APROBADO | V1 93 y V1b 94: POST 201 APROBADO; PATCH notas 200/200; GET 200/200, estado APROBADO y notas asociadas |
| TC-M04-147 | API-147-01 | Puede consultar métricas e historial; no puede modificar el estado, activar ni intervenir el historial | APROBADO | V2 95 RECHAZADO; ambos roles: GET inicial/posterior 200, auditoría 200, PUT/PATCH versión y PUT/PATCH/DELETE auditoría 4xx, activar 409; transiciones Administrador 2/2; Veterinario 2/2 |
| TC-M04-148 | API-148-01 | Permanece en APROBADO, no se activa sola y sigue disponible para activación | APROBADO | V1 93 con nota de Veterinario: tras V3 POST 201, GET 200, estado APROBADO, esta_produccion=false |
| TC-M04-149 | API-149-01 | Se devuelven estado y métricas completas y los filtros acotan correctamente el resultado | APROBADO | Administrador/Veterinario: sin filtro 26/26, tipo 5/5, RECHAZADO 2/2, APROBADO 3/3; V1/V1b/V2/V3 presentes con estado y métricas |

## Solicitudes API

| Rol | Operación | HTTP | Eco RUN | ID | Estado | Notas observadas | Siete métricas | Items | Eventos |
|---|---|---:|---|---:|---|---|---|---:|---:|
| Administrador | POST /sesiones/ | 200 | — | — | — | — | false | — | — |
| Veterinario | POST /sesiones/ | 200 | — | — | — | — | false | — | — |
| Administrador | GET /configuracion/variables-ambientales | 200 | true | — | — | — | false | 16 | 0 |
| RF-71 interno | POST /prediccion/modelos | 201 | true | 93 | APROBADO | — | true | — | — |
| RF-71 interno | POST /prediccion/modelos | 201 | true | 94 | APROBADO | — | true | — | — |
| RF-71 interno | POST /prediccion/modelos | 200 | true | 95 | RECHAZADO | — | true | — | — |
| Veterinario | PATCH /prediccion/modelos/93/notas | 200 | true | 93 | APROBADO | G056 RUN-G056-V1-20261028-051318 Veterinario nota clínica | true | — | — |
| Veterinario | GET /prediccion/modelos/93 | 200 | true | 93 | APROBADO | G056 RUN-G056-V1-20261028-051318 Veterinario nota clínica | true | — | — |
| Administrador | PATCH /prediccion/modelos/94/notas | 200 | true | 94 | APROBADO | G056 RUN-G056-V1-20261028-051318 Administrador nota clínica | true | — | — |
| Administrador | GET /prediccion/modelos/94 | 200 | true | 94 | APROBADO | G056 RUN-G056-V1-20261028-051318 Administrador nota clínica | true | — | — |
| Administrador | GET /prediccion/modelos/95 | 200 | true | 95 | RECHAZADO | — | true | — | — |
| Administrador | GET /prediccion/auditoria?[filtro] | 200 | true | — | — | — | false | 3 | 3 |
| Administrador | PUT /prediccion/modelos/95 | 405 | true | — | — | — | false | — | — |
| Administrador | PATCH /prediccion/modelos/95 | 405 | true | — | — | — | false | — | — |
| Administrador | POST /prediccion/modelos/95/activar | 409 | true | — | — | — | false | — | — |
| Administrador | PUT /prediccion/auditoria?[filtro] | 405 | true | — | — | — | false | — | — |
| Administrador | PATCH /prediccion/auditoria?[filtro] | 405 | true | — | — | — | false | — | — |
| Administrador | DELETE /prediccion/auditoria?[filtro] | 405 | true | — | — | — | false | — | — |
| Administrador | GET /prediccion/modelos/95 | 200 | true | 95 | RECHAZADO | — | true | — | — |
| Administrador | GET /prediccion/auditoria?[filtro] | 200 | true | — | — | — | false | 4 | 4 |
| Veterinario | GET /prediccion/modelos/95 | 200 | true | 95 | RECHAZADO | — | true | — | — |
| Veterinario | GET /prediccion/auditoria?[filtro] | 200 | true | — | — | — | false | 5 | 5 |
| Veterinario | PUT /prediccion/modelos/95 | 405 | true | — | — | — | false | — | — |
| Veterinario | PATCH /prediccion/modelos/95 | 405 | true | — | — | — | false | — | — |
| Veterinario | POST /prediccion/modelos/95/activar | 409 | true | — | — | — | false | — | — |
| Veterinario | PUT /prediccion/auditoria?[filtro] | 405 | true | — | — | — | false | — | — |
| Veterinario | PATCH /prediccion/auditoria?[filtro] | 405 | true | — | — | — | false | — | — |
| Veterinario | DELETE /prediccion/auditoria?[filtro] | 405 | true | — | — | — | false | — | — |
| Veterinario | GET /prediccion/modelos/95 | 200 | true | 95 | RECHAZADO | — | true | — | — |
| Veterinario | GET /prediccion/auditoria?[filtro] | 200 | true | — | — | — | false | 6 | 6 |
| RF-71 interno | POST /prediccion/modelos | 201 | true | 96 | APROBADO | — | true | — | — |
| Administrador | GET /prediccion/modelos/93 | 200 | true | 93 | APROBADO | G056 RUN-G056-V1-20261028-051318 Veterinario nota clínica | true | — | — |
| Administrador | GET /prediccion/modelos?[filtro] | 200 | true | — | — | — | false | 26 | 0 |
| Administrador | GET /prediccion/modelos?[filtro] | 200 | true | — | — | — | false | 5 | 0 |
| Administrador | GET /prediccion/modelos?[filtro] | 200 | true | — | — | — | false | 2 | 0 |
| Administrador | GET /prediccion/modelos?[filtro] | 200 | true | — | — | — | false | 3 | 0 |
| Veterinario | GET /prediccion/modelos?[filtro] | 200 | true | — | — | — | false | 26 | 0 |
| Veterinario | GET /prediccion/modelos?[filtro] | 200 | true | — | — | — | false | 5 | 0 |
| Veterinario | GET /prediccion/modelos?[filtro] | 200 | true | — | — | — | false | 2 | 0 |
| Veterinario | GET /prediccion/modelos?[filtro] | 200 | true | — | — | — | false | 3 | 0 |
| Sistema | DELETE /test-control/runs/RUN-G056-V1-20261028-051318 | 200 | — | — | — | — | false | — | — |

## Incidencias de producto

Ninguna incidencia de producto confirmada.

## Observaciones

- TC-M04-148 usó V1 (93), con nota de Veterinario.
- Datos heredados de TEST: entre las versiones 8-31, las observadas **8, 9, 10, 13, 14, 15, 17, 19, 23, 25 y 27-31** figuran `EN_VALIDACION` con `tipo_modelo` nulo; la 57 `MODELO_RIESGO_CONTAGIO` figura `ACTIVO` sin métricas almacenadas completas; la 56 `MODELO_ACUICULTURA` y la 42 `MODELO_AVES` figuran `ACTIVO` sin métricas poblacionales. Contradicen RF-69: `EN_VALIDACION` es transitorio en Fases 1-3 (líneas 1972-2043), `tipo_modelo` es obligatorio en Entradas (1959) y las métricas se exigen en Salida 1 (2204-2223). Son registros preexistentes, no un defecto demostrado del listado de TC-M04-149. **Atención sugerida: DBA/Desarrollo**, para revisar origen y saneamiento; causa raíz no determinada y sin incidencia de producto confirmada en este grupo.
- Efectos persistentes de este RUN: cuatro archivos ONNX; un aviso por correo de V2 RECHAZADA, por destinatario activo según la ruta consultada. Cantidad de destinatarios no verificada. DELETE no revierte estos efectos.

## Historial de intentos

| Intento | RUN | Autorización | Resultado técnico | Registro QA | Decisión |
|---|---|---|---|---|---|
| 1 | RUN-G056-V1-20261028-050237 | AUT-G056-V1-20261028 | Ejecutor exit 0; DELETE 200 | INCIERTO / ABIERTO_PENDIENTE: `resultado.json` no seguía el contrato del registro | No oficial; evidencia nativa eliminada por decisión del responsable QA el 2026-10-28. |
| 2 | RUN-G056-V1-20261028-051318 | AUT-G056-V1-R2-20261028 | DELETE 200; cuatro casos APROBADOS | OFICIAL | RUN oficial V1. |

En el intento 1, TC-M04-146 registró notas HTTP 200 en versiones 89 (Veterinario) y 90 (Administrador); TC-M04-147 obtuvo 405 para las modificaciones y 409 al activar la versión RECHAZADA, sin cambios en transiciones; TC-M04-148 fue conforme; TC-M04-149 tuvo filtros conformes. El ejecutor marcó 147 y 149 `RECHAZADO` por falsos positivos: contó eventos propios `HISTORIAL_CONSULTADO` como intervención y trató datos heredados incompletos como fallo del listado. ORD-G056-005 corrigió ambas reglas y el contrato del registro QA. El intento 1 dejó un aviso por correo y cuatro ONNX probables, no revertidos por DELETE; no se verificó su persistencia directamente. Su `resultado.json` informó `rollback_verificado=false`. El resumen se transcribió antes de eliminar su evidencia nativa, conforme a la autorización QA.

## Incidencias técnicas QA

- **Resuelta en ORD-G056-005:** falso rechazo de 147 por eventos `HISTORIAL_CONSULTADO` creados por consultas GET; la comprobación actual compara las transiciones de estado.
- **Resuelta en ORD-G056-005:** falso rechazo de 149 por exigir métricas completas a registros heredados en el listado sin filtro; la comprobación actual valida las cuatro versiones del RUN y los filtros, y separa los datos heredados como observación.
- **Resuelta en ORD-G056-005:** estructura anterior de `resultado.json` incompatible con el registro QA; el intento 2 fue clasificado OFICIAL. Estos fallos eran de automatización, sin equipo de producto asignado.

## Evidencias y cierre

- preflight.json
- newman/newman-G056-V1.json
- newman/newman-G056-V1.html
- newman/newman-G056-V1b.json
- newman/newman-G056-V1b.html
- newman/newman-G056-V2.json
- newman/newman-G056-V2.html
- newman/newman-G056-V3.json
- newman/newman-G056-V3.html
- resultado.json
- TC-M04-G056_resultado.md

DELETE del RUN: HTTP 200. `resultado.json` registra rollback verificado por confirmación del sandbox («Sandbox informó cierre; rollback de BD sin lectura posterior»). No hubo lectura posterior de BD; ONNX y correo no se revierten por DELETE.

## Conclusión y acción

Cerrar G056 como APROBADO en el registro QA. Revisar por separado los datos heredados con DBA/Desarrollo y gestionar los ONNX y el aviso persistentes conforme al procedimiento del entorno; no hay incidencia de producto confirmada por los cuatro casos de este RUN.
