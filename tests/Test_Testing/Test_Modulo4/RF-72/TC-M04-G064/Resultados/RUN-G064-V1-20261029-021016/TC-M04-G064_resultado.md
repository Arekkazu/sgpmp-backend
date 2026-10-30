# TC-M04-G064 — APROBADO

## Identificación

Grupo G064; casos TC-M04-194, TC-M04-195, TC-M04-196 y TC-M04-197; RF-72; versión V1, intento 3; RUN oficial RUN-G064-V1-20261029-021016; ambiente TEST; autorización AUT-G064-V1-R3-20261029; contrato identificado en el RUN como `origin/test` `daefc3a5`; ejecutor Node.js y colección Postman. Cuatro comprobaciones API; no había UI obligatoria ni pruebas Cypress. Esta edición documental no repitió TEST ni verificó el commit mediante Git.

## Decisión del caso

Con resultados de inferencia MODELO_ESPECIES_MEDIANAS sembrados en el activo 885, el Veterinario registró CORRECTO, SIN_EVENTO, PARCIAL e INCORRECTO y las cuatro respondieron 201 con estado_registro ACTIVO; los diagnósticos se exigieron solo donde corresponde.

| Caso | Decisión | Motivo en lenguaje claro |
|---|---|---|
| TC-M04-194 | APROBADO | CORRECTO se aceptó sin diagnóstico real; la respuesta asignó fecha y el registro apareció en historial y auditoría. |
| TC-M04-195 | APROBADO | SIN_EVENTO se aceptó sin diagnóstico real para una predicción de riesgo sin evento posterior; corresponde al falso positivo descrito por RF-72. |
| TC-M04-196 | APROBADO | PARCIAL se aceptó con la patología activa 1 como diagnóstico principal; el registro apareció en historial y auditoría. |
| TC-M04-197 | APROBADO | INCORRECTO se aceptó con la patología activa 1, distinta de la estimada 10; corresponde al falso negativo descrito por RF-72. |

Los cuatro estados y el carácter oficial coinciden con `resultado.json`.

## Precondición de datos (semilla)

En el intento 2, TEST mostraba cinco activos INDIVIDUAL. Solo el 876 tenía historial: 58 eventos, de ellos 57 inferencias de MODELO_ACUICULTURA sin patología y una retroalimentación; había cero inferencias de modelos INDIVIDUAL aptas para los cuatro casos. El responsable QA insertó el 2026-10-28 catorce resultados permanentes de MODELO_ESPECIES_MEDIANAS, versión 43, en el activo 885, con riesgos 0–3 y patologías activas 8–14. El diagnóstico de selección del RUN oficial encontró esas 14 inferencias, 11 con patología. Procedencia y permanencia: documento externo del repositorio de orquestación `estado/SEMILLA-RF72.md`; se cita sin copiarlo. La semilla permanece tras el cierre del sandbox.

## Detalle por caso

### TC-M04-194 — APROBADO

**Qué se hizo:** Se eligió el resultado `511a6d66-a862-4822-bf47-2634333531b3` del activo 885, inferido el 2026-10-28T00:06:22Z, con riesgo 3 y patología estimada 8: era una inferencia individual reciente dentro de la ventana. El Veterinario envió CORRECTO sin diagnóstico real.

**Qué se esperaba:** La matriz G064 exige HTTP 201, estado CORRECTO, diagnósticos nulos, registro ACTIVO y fecha asignada; RF-72 líneas 4156–4167, 4299–4323 y CA-1/CA-4.

**Qué se observó:** HTTP 201; respuesta con estado CORRECTO, `diagnosticos_reales=null`, `estado_registro=ACTIVO`, `fecha_retroalimentacion=2026-10-29T02:10:18.389649Z` y `es_fuente_desconocida=false`. El historial devolvió HTTP 200 con el nuevo evento (15 en esa lectura) y la auditoría HTTP 200 con un registro; la lectura poscierre devolvió 14 eventos sin esta retroalimentación.

**Por qué APROBADO:** Coinciden el HTTP 201, CORRECTO, la ausencia de diagnósticos, ACTIVO y la fecha posterior a la inferencia. Historial y auditoría corroboraron el alta; la lectura poscierre corroboró su ausencia tras el cierre.

### TC-M04-195 — APROBADO

**Qué se hizo:** Se eligió el resultado `997b8cda-b608-4bb3-a7d2-ea37cf12b944` del activo 885, inferido el 2026-10-26T01:06:22Z, con riesgo 2 y patología estimada 9: había predicción de riesgo y se evaluó la ausencia de evento posterior. El Veterinario envió SIN_EVENTO sin diagnóstico real.

**Qué se esperaba:** La matriz G064 exige HTTP 201 y estado SIN_EVENTO para registrar el falso positivo; RF-72 líneas 3987–3988, 4156–4167, 4299–4323 y CA-1/CA-4. La respuesta debe conservar registro ACTIVO y fecha asignada.

**Qué se observó:** HTTP 201; respuesta con estado SIN_EVENTO, `diagnosticos_reales=null`, `estado_registro=ACTIVO`, `fecha_retroalimentacion=2026-10-29T02:10:18.389649Z` y `es_fuente_desconocida=false`. El historial devolvió HTTP 200 con el nuevo evento (16 en esa lectura) y la auditoría HTTP 200 con un registro; la lectura poscierre devolvió 14 eventos sin esta retroalimentación.

**Por qué APROBADO:** Coinciden el HTTP 201, SIN_EVENTO, los diagnósticos nulos, ACTIVO y la fecha asignada. Historial y auditoría corroboraron el registro. Según RF-72 3987–3988, SIN_EVENTO expresa el falso positivo; el criterio no pide otro campo con esa etiqueta.

### TC-M04-196 — APROBADO

**Qué se hizo:** Se eligió el resultado `f056f99d-78bf-478d-86f0-5b2ee1a70873` del activo 885, inferido el 2026-10-26T21:06:22Z, con riesgo 0 y sin patología estimada: permitía contrastar un diagnóstico clínico parcial. El Veterinario envió PARCIAL y la patología activa 1 como diagnóstico real principal.

**Qué se esperaba:** La matriz G064 exige HTTP 201, PARCIAL y el diagnóstico activo elegido como principal; RF-72 líneas 4067–4068, 4156–4167, 4299–4323 y CA-5. La respuesta debe conservar registro ACTIVO y fecha asignada.

**Qué se observó:** HTTP 201; respuesta con estado PARCIAL, `diagnosticos_reales=[1]`, `estado_registro=ACTIVO`, `fecha_retroalimentacion=2026-10-29T02:10:18.389649Z` y `es_fuente_desconocida=true`. El historial devolvió HTTP 200 con el nuevo evento (17 en esa lectura) y la auditoría HTTP 200 con un registro; la lectura poscierre devolvió 14 eventos sin esta retroalimentación.

**Por qué APROBADO:** Coinciden el HTTP 201, PARCIAL, la patología activa 1 en primera posición, ACTIVO y la fecha asignada. Historial y auditoría corroboraron el registro; la lectura poscierre corroboró su ausencia. La fuente desconocida se explica en Observaciones.

### TC-M04-197 — APROBADO

**Qué se hizo:** Se eligió el resultado `d1f3cc43-3bf9-4492-a5b9-ec0cc5025d7e` del activo 885, inferido el 2026-10-24T19:06:22Z, con riesgo 1 y patología estimada 10: permitía informar un diagnóstico distinto. El Veterinario envió INCORRECTO y la patología activa 1 como diagnóstico real principal.

**Qué se esperaba:** La matriz G064 exige HTTP 201, INCORRECTO y diagnóstico activo distinto del estimado, identificado como falso negativo; RF-72 líneas 3987–3988, 4067–4068, 4156–4167, 4299–4323 y CA-5. La respuesta debe conservar registro ACTIVO y fecha asignada.

**Qué se observó:** HTTP 201; respuesta con estado INCORRECTO, `diagnosticos_reales=[1]`, `estado_registro=ACTIVO`, `fecha_retroalimentacion=2026-10-29T02:10:18.389649Z` y `es_fuente_desconocida=true`. El historial devolvió HTTP 200 con el nuevo evento (18 en esa lectura) y la auditoría HTTP 200 con un registro; la lectura poscierre devolvió 14 eventos sin esta retroalimentación.

**Por qué APROBADO:** Coinciden el HTTP 201, INCORRECTO, la patología activa 1 como principal y distinta de la estimada 10, ACTIVO y la fecha asignada. Historial y auditoría corroboraron el registro. Según RF-72 3987–3988, INCORRECTO expresa el falso negativo; el criterio no pide otro campo con esa etiqueta.

## Datos elegidos

| Caso | Resultado de inferencia | Activo | Fecha de inferencia (UTC) | Riesgo | Modelo | Patología estimada | Diagnóstico real enviado |
|---|---|---:|---|---:|---|---:|---:|
| TC-M04-194 | `511a6d66-a862-4822-bf47-2634333531b3` | 885 | 2026-10-28T00:06:22Z | 3 | MODELO_ESPECIES_MEDIANAS | 8 | ninguno |
| TC-M04-195 | `997b8cda-b608-4bb3-a7d2-ea37cf12b944` | 885 | 2026-10-26T01:06:22Z | 2 | MODELO_ESPECIES_MEDIANAS | 9 | ninguno |
| TC-M04-196 | `f056f99d-78bf-478d-86f0-5b2ee1a70873` | 885 | 2026-10-26T21:06:22Z | 0 | MODELO_ESPECIES_MEDIANAS | ninguna | 1 |
| TC-M04-197 | `d1f3cc43-3bf9-4492-a5b9-ec0cc5025d7e` | 885 | 2026-10-24T19:06:22Z | 1 | MODELO_ESPECIES_MEDIANAS | 10 | 1 |

## Observaciones e incidencias

- En TC-M04-196 y TC-M04-197 no se envió `fuente_diagnostico`; la respuesta indicó `es_fuente_desconocida=true`, conforme a RF-72 líneas 4119–4120.
- El diagnóstico real enviado fue la patología 1, existente y activa. La inspección de la semilla indicó que a la especie 220 solo le aplican las patologías genéricas 7–14; por ello, la 1 probablemente pertenece a otra especie. RF-72 líneas 4067–4068 y CA-5 solo exigen patología existente y activa, y la ruta de código revisada no filtra por especie. Queda para valoración en G066, sobre consistencia con el catálogo; no se abre incidencia en G064 ni se atribuye causa raíz.
- El activo 885 también es semilla de G88 (módulo 3) y conserva historial clínico permanente.

No hay incidencias de producto en `resultado.json`. La observación de especie es probable, no una discrepancia comprobada contra el oráculo de G064.

## Historial de intentos

| Intento | RUN y autorización | Resultado técnico | Hallazgo y efectos de negocio |
|---|---|---|---|
| 1 | RUN-G064-V1-20261029-011644; AUT-G064-V1-20261029 | Salida 2; 9 solicitudes; sin POST de retroalimentación; DELETE HTTP 200; cuatro NO_CONCLUYENTE | No se halló dato apto y el resultado aún no detallaba el descarte. No se creó retroalimentación; rollback de registros no verificable porque no hubo registros. |
| 2 | RUN-G064-V1-20261029-013016; AUT-G064-V1-R2-20261029 | Salida 2; 10 solicitudes; sin POST de retroalimentación; DELETE HTTP 200; cuatro NO_CONCLUYENTE | Cinco activos INDIVIDUAL; solo el 876 con 58 eventos, 57 inferencias MODELO_ACUICULTURA sin patología y ninguna de modelo INDIVIDUAL apta. No se creó retroalimentación; rollback de registros no verificable porque no hubo registros. |
| 3 | RUN-G064-V1-20261029-021016; AUT-G064-V1-R3-20261029 | RUN oficial; 26 solicitudes; cuatro APROBADO; DELETE HTTP 200 | Cuatro retroalimentaciones dentro del sandbox, ausentes en las lecturas públicas poscierre. |

Los RUN de los intentos 1 y 2 fueron técnicos y no produjeron efectos remotos de negocio de retroalimentación. Sus evidencias nativas se eliminaron por decisión expresa del responsable QA el 2026-10-29, después de transcribir este historial. El registro QA externo al repositorio no se modificó.

## Cierre y rollback

El RUN oficial registró 26 solicitudes y DELETE HTTP 200. Las lecturas públicas poscierre devolvieron 14 eventos en el activo 885, sin las cuatro retroalimentaciones creadas en el sandbox: rollback verificado para esos registros. Esta comprobación no demuestra reversión de eventos RF-67 que puedan generar las consultas poscierre ni de un posible respaldo local RF-73.

## Conclusión y acciones

Los cuatro casos cumplieron las comprobaciones API del criterio. Conservar la semilla y este RUN oficial; valorar en G066 la consistencia entre especie 220 y patología 1, sin cambiar los veredictos de G064.

## Evidencias

Este RUN se ejecutó por API con fetch; Newman no se ejecutó (desviación de la herramienta indicada en la matriz, API - Postman). La evidencia funcional completa está en resultado.json. El ejecutor se corrigió el 2026-10-29 para usar Newman en las ejecuciones siguientes (ORD-G064-008).

- `resultado.json`: estados, respuestas saneadas, historial y auditoría.
- `preflight.json`: preflight del RUN oficial.
- `contexto_operacion.json`: contexto autorizado del intento 3 y referencia a la semilla.
- `TC-M04-G064_resultado.md`: este informe oficial.
