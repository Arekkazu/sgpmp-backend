# TC-M02-G93 — TERCERA EVALUACIÓN (V3)

**Caso agrupado:** TC-M02-G93 — Reglas negativas de consumo de datos consolidados
**Casos originales:** TC-M02-155 — Rechazar acceso de módulo sin scope autorizado · TC-M02-156 — Rechazar rango de fechas inválido (variantes A y B) · TC-M02-157 — Rechazar consulta NIC-41 con datos de PESO insuficientes
**Requerimiento:** RF-50
**Caso de uso:** CU12 — Consultar indicadores y exponer datos
**Responsable QA:** Juan Esteban
**RUN_ID:** `G93-REEVAL-V3-20260927-191233`
**Fecha:** 2026-09-27
**Ambiente decisorio:** TEST

---

## DECISIÓN GENERAL

### TC-M02-G93: APROBADO

### TC-M02-155: APROBADO
### TC-M02-156: APROBADO
- TC-M02-156-A: APROBADO
- TC-M02-156-B: APROBADO
### TC-M02-157: APROBADO

La tercera evaluación se ejecutó funcionalmente con la identidad técnica M06 como consumidor y las
tres reglas negativas de RF-50 se comportaron exactamente como el caso exige: rechazo por scope
granular del `tipo_dato`, rechazo de rangos de fechas inválidos en sus dos variantes y rechazo de la
consulta NIC-41 cuando el activo no registra métricas de peso en el rango solicitado.

El control positivo previo confirmó que el token de M06 era válido, que el activo era visible y que su
permiso general y su scope de métricas estaban operativos, de modo que ninguno de los rechazos
posteriores es atribuible a autenticación, permisos generales ni alcance.

Ejecución automatizada: **33 assertions, 0 fallidas.**

---

## RESUMEN DEL RESULTADO

| Caso | Esperado | Obtenido | Resultado |
|---|---|---|---|
| TC-M02-155 | 403 `SCOPE_TIPO_DATO_NO_AUTORIZADO` | 403 con el código esperado y mensaje que identifica `eventos` | **APROBADO** |
| TC-M02-156-A | 400 `PARAMETROS_INVALIDOS` por rango invertido | 400 con motivo funcional de orden invertido | **APROBADO** |
| TC-M02-156-B | 400 `PARAMETROS_INVALIDOS` por rango futuro | 400 con motivo funcional de fecha futura | **APROBADO** |
| TC-M02-157 | 422 `METRICAS_PESO_INSUFICIENTES` | 422 con el código esperado y mensaje de insuficiencia de peso en el rango | **APROBADO** |

Ninguna de las respuestas de rechazo expuso datos consolidados del activo, y ninguna de las respuestas
de error filtró detalles internos de validación.

---

## ANTECEDENTES

**V1 — EJECUTADA. Resultado: RECHAZADO.** TC-M02-155 BLOQUEADO (no existía scope por `tipo_dato`),
TC-M02-156-A APROBADO, TC-M02-156-B RECHAZADO (se aceptaban fechas futuras), TC-M02-157 BLOQUEADO
(M06 no existía como consumidor autenticable). De ahí surgieron #242, #390, #391, #392 y #393.

**V2 — REEVALUACIÓN NO EJECUTADA / APLAZADA POR ERROR DE QA.** No hubo reevaluación funcional: los
hallazgos estaban registrados en Excel/Taiga pero cuatro de los cinco no se habían publicado en
GitHub. No se hicieron peticiones al ambiente, ni ejecución automatizada, ni consultas de base de
datos, y no se produjo veredicto experimental nuevo; V2 conservó como referencia el resultado de V1.

**Correcciones de Desarrollo.** Los cinco issues quedaron cerrados, con correcciones para el rechazo de
fechas futuras, el scope granular por `tipo_dato`, la identidad técnica M06, el 422 por insuficiencia
de PESO, la advertencia de peso fuera del rango y la sanitización de los mensajes de error.

**V3.** Primera reevaluación funcional posterior a las correcciones, comprobando el comportamiento
realmente desplegado.

---

## ENTORNO

| Ambiente | Uso |
|---|---|
| TEST | Ambiente decisorio; ejecución funcional V3 |
| DEV | No se requirió: TEST aprobó con todas las precondiciones satisfechas |

`/health` respondió 200. El contrato de `GET /activos-biologicos/{id_activo}/datos-consolidados`
acepta `tipo_dato` con los valores `eventos | fases | estado | metricas | todos`, junto con
`fecha_inicio`, `fecha_fin`, `pagina` y `page_size`, y declara las respuestas 200, 400, 401, 403, 404,
422, 429 y 500.

Tiempos de respuesta observados: entre 135 ms y 166 ms en los cuatro escenarios del caso.

---

## ACTOR / IDENTIDAD TÉCNICA

Consumidor utilizado: la identidad técnica M06, sin sustituirla en ningún momento por una cuenta
humana ni por otro módulo.

| Verificación | Estado |
|---|---|
| Rol `Integración M06` existe | sí |
| Identidad técnica descubierta y validada | sí, por consulta actual; no se usó ningún identificador histórico |
| Cuenta activa | sí |
| Autentica | sí |
| Rol confirmado en el token | `Integración M06` |
| Permiso general READ sobre `activos_biologicos` | sí |
| Scope `metricas` | **sí** |
| Scope `eventos` | **no** |
| Scope `fases` | no |
| Scope `estado` | no |

Esta configuración de scopes es la que hace verificables los dos escenarios del grupo: con `metricas`
autorizado se llega hasta la regla NIC-41, y con `eventos` no autorizado se provoca el rechazo
granular. **No se modificó ningún scope ni permiso** para obtener el 403.

---

## PREPARACIÓN DE DATOS

La identidad técnica M06 requirió alcance sobre la finca del fixture. La finca correspondiente al
activo seleccionado fue asignada mediante el endpoint oficial `PUT /usuarios/{id_usuario}/fincas`
antes de iniciar la ejecución oficial, enviando el conjunto completo de fincas que debían quedar
asignadas y preservando cualquier asignación activa preexistente (la identidad no tenía ninguna).

La operación fue ejecutada por una cuenta administrativa cuyo permiso de actualización sobre Usuarios
se confirmó previamente, y nunca por la propia identidad M06. La respuesta fue HTTP 200 y la
asignación se verificó después en la fuente autoritativa.

No se modificaron roles, scopes, eventos de crecimiento ni datos analíticos. No se ejecutó ninguna
sentencia directa contra la base de datos.

Efecto comprobado: tras la asignación, M06 pasó de ver 0 activos a ver 29, y el control positivo sobre
el activo del fixture pasó de 404 a **200**.

Esta preparación es una precondición del caso, no su oráculo.

---

## CONFIGURACIÓN UTILIZADA

| Elemento | Valor |
|---|---|
| Activo biológico | 279 |
| Identificador | `QAJE-CREC-OK` |
| Tipo | INDIVIDUAL |
| Estado | ACTIVO |
| Inicio de ciclo | 2026-06-01 |
| Infraestructura | 48 |
| Finca | 57 |
| Métricas de PESO registradas | 5 (2026-09-09 ×3, 2026-09-10, 2026-09-19) |

Rangos derivados de los datos reales, sin valores fijos:

| Uso | Rango | Comprobación |
|---|---|---|
| TC-M02-157 (NIC-41) | 2026-06-01 → 2026-09-08 | 0 métricas de PESO dentro del rango; sí hay PESO fuera; rango pasado y dentro del ciclo |
| TC-M02-156-A | 2026-09-18 → 2026-08-29 | ambas fechas pasadas; la única invalidez es el orden |
| TC-M02-156-B | 2026-09-29 → 2026-09-30 | ambas futuras respecto de la fecha observada, con inicio < fin |
| Verificación complementaria | 2026-09-09 → 2026-09-18 | 4 métricas de PESO dentro del rango y la más reciente (2026-09-19) fuera |

---

## TC-M02-155

**Resultado: APROBADO.**

Petición con el mismo token M06 y el mismo activo del control positivo, solicitando `tipo_dato=eventos`,
para el que la identidad no tiene scope.

| Verificación | Resultado |
|---|---|
| HTTP 403 | CUMPLE |
| `error_code` = `SCOPE_TIPO_DATO_NO_AUTORIZADO` | CUMPLE |
| El mensaje identifica el `tipo_dato` solicitado | CUMPLE — «Acceso denegado: El módulo solicitante no tiene autorización para consumir datos de tipo eventos.» |
| El mensaje indica falta de autorización del módulo solicitante | CUMPLE |
| Sin exposición de datos consolidados | CUMPLE |

El rechazo proviene del scope granular por `tipo_dato` y no de otro mecanismo: el control positivo
inmediatamente anterior, con el mismo token y el mismo activo, devolvió 200 con la sección de
métricas, de modo que quedan descartados token inválido, permiso general ausente, rol incorrecto y
falta de alcance.

---

## TC-M02-156

**Resultado: APROBADO** (ambas variantes).

### TC-M02-156-A

Rango invertido, con ambas fechas en el pasado.

| Verificación | Resultado |
|---|---|
| HTTP 400 | CUMPLE |
| `error_code` = `PARAMETROS_INVALIDOS` | CUMPLE |
| Motivo funcional sobre rango invertido | CUMPLE — «La fecha de inicio (2026-09-18) no puede ser posterior a la fecha de fin (2026-08-29).» |
| Sin datos consolidados | CUMPLE |
| Sin detalles internos de validación | CUMPLE |

### TC-M02-156-B

Rango futuro, calculado contra la fecha observada del ambiente, con inicio anterior al fin.

| Verificación | Resultado |
|---|---|
| HTTP 400 | CUMPLE |
| `error_code` = `PARAMETROS_INVALIDOS` | CUMPLE |
| Motivo funcional sobre la condición futura | CUMPLE — «La fecha de inicio (2026-09-29) no puede ser una fecha futura: los datos consolidados son sobre eventos ya ocurridos.» |
| Sin datos consolidados | CUMPLE |
| Sin detalles internos de validación | CUMPLE |

En V1 esta variante había sido RECHAZADA porque el rango futuro se aceptaba. El comportamiento quedó
corregido.

---

## TC-M02-157

**Resultado: APROBADO.**

Petición con M06, `tipo_dato=metricas` y el rango con cero métricas de PESO, previamente comprobado
como válido, pasado y dentro del ciclo del activo.

| Verificación | Resultado |
|---|---|
| HTTP 422 | CUMPLE |
| `error_code` = `METRICAS_PESO_INSUFICIENTES` | CUMPLE |
| Mensaje funcional de insuficiencia de PESO en el rango | CUMPLE — «Información incompleta: El activo 279 no registra métricas de peso necesarias para el cálculo de transformación biológica en el rango de fechas solicitado.» |
| No es un 422 genérico de validación de entrada | CUMPLE |
| Sin respuesta consolidada de éxito | CUMPLE |

El 422 corresponde a la regla de suficiencia de PESO asociada al consumidor de consistencia fuerte, no
a una validación de esquema. La precondición quedó demostrada antes de ejecutar: el activo era
visible, el scope de métricas estaba presente, el rango era válido y no futuro, y no había ninguna
métrica de peso dentro de él.

---

## SEGUIMIENTO DE INCIDENCIAS

| Incidencia | Estado en V3 |
|---|---|
| **#242** — fechas futuras aceptadas | **CORREGIDO Y VERIFICADO EN V3.** El rango futuro se rechaza con 400 y motivo temporal explícito. |
| **#390** — ausencia de scope granular por `tipo_dato` | **CORREGIDO Y VERIFICADO EN V3.** Los recursos de scope existen, los permisos los diferencian por tipo de dato y el rechazo responde con el código y el mensaje esperados, con control positivo previo que descarta cualquier otra causa. |
| **#391** — M06 no disponible como consumidor autenticable | **CORREGIDO Y VERIFICADO EN V3.** La identidad existe, está activa, autentica con su rol y la regla 422 de suficiencia de PESO se ejecuta para ella. |
| **#392** — métrica de peso fuera de rango | **CORREGIDO Y VERIFICADO EN V3.** Con al menos una métrica de PESO dentro del rango la consulta devuelve 200, `metricas_actuales` sigue visible y la respuesta incluye la advertencia que aclara que el peso mostrado no pertenece al período solicitado. |
| **#393** — exposición de detalles internos de validación | **CORREGIDO Y VERIFICADO EN V3.** Ninguna de las respuestas de error contiene referencias a esquemas internos, errores de validación, valores de entrada ni enlaces de la librería de validación. |

No se creó ninguna incidencia nueva y ninguna se reabre.

---

## RESULTADO DEL ORÁCULO

| Verificación | Resultado |
|---|---|
| Contrato con 400/403/422 declarados | CUMPLE |
| Identidad técnica M06 autenticada, activa y con rol confirmado | CUMPLE |
| Permiso general READ sobre `activos_biologicos` | CUMPLE |
| Scope `metricas` autorizado y `eventos` no autorizado | CUMPLE |
| Finca del activo identificada y asignada por el endpoint oficial | CUMPLE |
| Control positivo: M06 accede al activo con `tipo_dato=metricas` | CUMPLE — HTTP 200 |
| TC-M02-155: 403 por scope granular | CUMPLE |
| TC-M02-156-A: 400 por rango invertido | CUMPLE |
| TC-M02-156-B: 400 por rango futuro | CUMPLE |
| TC-M02-157: 422 por insuficiencia de PESO | CUMPLE |
| Verificación complementaria: advertencia de peso fuera del rango | CUMPLE |
| Respuestas de rechazo sin exposición de datos consolidados | CUMPLE |
| Respuestas de error sin fuga de detalles de validación | CUMPLE |

**Newman: 33 assertions, 0 fallidas.**

---

## COMPARACIÓN V1 VS V2 VS V3

| Aspecto | V1 | V2 | V3 |
|---|---|---|---|
| TC-M02-G93 | RECHAZADO | **NO EJECUTADA — conserva referencia V1** | **APROBADO** |
| TC-M02-155 | BLOQUEADO | NO EJECUTADO | **APROBADO** |
| TC-M02-156-A | APROBADO | NO EJECUTADO | **APROBADO** |
| TC-M02-156-B | RECHAZADO | NO EJECUTADO | **APROBADO** |
| TC-M02-156 global | RECHAZADO | NO EJECUTADO | **APROBADO** |
| TC-M02-157 | BLOQUEADO | NO EJECUTADO | **APROBADO** |
| Scope por `tipo_dato` | No disponible | No reevaluado | **Desplegado y verificado (403 específico)** |
| Identidad M06 | No disponible | No reevaluada | **Existe, activa y autentica con su rol** |
| Alcance sobre el fixture | No aplicable | No reevaluado | **Asignado por endpoint oficial; control positivo 200** |
| Fechas futuras | Aceptadas incorrectamente | No reevaluado | **Rechazadas con 400 y motivo temporal** |
| Regla 422 NIC-41 | No implementada | No reevaluada | **Implementada y verificada** |
| Sanitización de errores de validación | No | No reevaluada | **Verificada en las tres respuestas de error** |
| Advertencia de peso fuera del rango | No existía | No reevaluada | **Presente y verificada** |

### Evolución

**V1** fue la ejecución funcional que detectó los defectos y los bloqueos, y originó las cinco
incidencias.

**V2** quedó aplazada por un error de publicación de issues por parte de QA; no produjo evidencia
funcional nueva y mantuvo como referencia el resultado de V1.

**V3** cierra el ciclo: los dos casos que V1 no pudo ejecutar quedan APROBADOS, el defecto funcional
que V1 sí detectó quedó corregido, y las cinco incidencias quedan verificadas. El grupo pasó de
RECHAZADO a APROBADO.

---

## ORIGEN / INTERPRETACIÓN DEL RESULTADO

Las correcciones de Desarrollo funcionan en el sistema desplegado, y no solo en el código: los tres
mecanismos bajo prueba —scope granular por `tipo_dato`, validación de rangos de fechas y regla de
suficiencia de PESO para el consumidor de consistencia fuerte— se observaron respondiendo con el
código HTTP, el `error_code` y el mensaje funcional que el caso define.

Lo único que V3 tuvo que preparar fue una precondición legítima: la identidad técnica M06 necesitaba
alcance sobre la finca del activo evaluado. El alcance se resuelve por RBAC —un rol que no gestiona
fincas queda limitado a las fincas asociadas al usuario— y la identidad técnica no tenía ninguna
asociación, de modo que todo activo le respondía 404. Al asignarla por el endpoint oficial, el
consumidor pasó a ver el activo y los casos quedaron ejecutables sin modificar nada más.

Conviene dejar constancia de una observación menor, ajena al oráculo del caso: el perfil devuelto por
la consulta de sesión propia no lista las fincas de esta identidad aunque la asignación exista y el
alcance efectivo sí las aplique. No afecta a RF-50 ni a ninguno de los subcasos; se deja anotada para
revisión posterior si el equipo lo considera pertinente.

Queda también una consideración de diseño para Desarrollo: un consumidor de servicio como M06 depende
hoy de asignaciones de finca propias de usuarios operativos. Si se prevé que consuma datos de varias
fincas, convendría decidir si los roles de integración deben tratarse como de alcance global. Es una
decisión de diseño, no un defecto, y no condiciona el resultado de esta evaluación.

---

## CONCLUSIÓN

**TC-M02-G93 queda APROBADO.**

Sus tres casos originales quedan igualmente **APROBADOS**: **TC-M02-155**, **TC-M02-156** —en sus dos
variantes— y **TC-M02-157**.

La tercera evaluación demuestra, sobre el sistema desplegado y con la identidad técnica que el caso
exige, que RF-50 rechaza correctamente el consumo de un tipo de dato sin scope autorizado, los rangos
de fechas inválidos —incluidos los futuros, que V1 había encontrado aceptados— y las consultas NIC-41
sobre activos sin métricas de peso en el rango solicitado, sin exponer datos consolidados ni detalles
internos en ninguno de los rechazos.

Las cinco incidencias asociadas al grupo —#242, #390, #391, #392 y #393— quedan **CORREGIDAS Y
VERIFICADAS EN V3**. No se crea ninguna incidencia nueva.

---

La evaluación se realizó sin modificar código productivo, sin escrituras directas en la base de datos
y sin sustituir la identidad técnica del caso. La única escritura fue la asignación de la finca del
fixture a la identidad técnica, mediante el endpoint oficial y como preparación de precondiciones. Las
evidencias técnicas se conservan en la carpeta del RUN_ID correspondiente.
