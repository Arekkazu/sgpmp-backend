# INC-M02-93-G93 — Identidad M06 + 422 por métricas de peso insuficientes (issue #391)

**RF:** RF-50 — Disponibilidad de datos para módulos analíticos
**CU:** CU12 / **Caso QA:** TC-M02-157 / **Grupo:** TC-M02-G93
**Endpoint:** `GET /activos-biologicos/{id_activo}/datos-consolidados`

---

## Reporte de QA (resumen)

TC-M02-157 exige ejecutar la consulta con M06 como consumidor autenticado,
con scope de valoración/NIC-41, sobre un activo con rango de fechas que no
tenga métricas PESO (pero sí las tenga fuera de ese rango, para descartar que
el bloqueo sea por falta de datos de prueba). No existía ninguna identidad
autenticable que representara a M06 — mismo tipo de bloqueo que
INC-M02-92-G93 (#390) reportó para M04, resuelto con el mismo patrón.

---

## Paso 0 — Contraste contra el RF y el código real

RF-50 flujo alterno #3 ("Datos insuficientes para proceso crítico NIC 41"):

> *"El módulo M06 solicita datos de valoración, pero el activo no registra
> eventos de peso o crecimiento en el periodo consultado. El sistema
> responde con: HTTP 422 — 'Información incompleta: El activo [ID_ACTIVO] no
> registra métricas de peso necesarias para el cálculo de transformación
> biológica en el rango de fechas solicitado.'"*

RF-50 también distingue explícitamente el nivel de exigencia por consumidor:
*"políticas de consistencia fuerte para consultas críticas (M06 – valoración
financiera) y consistencia eventual para consultas no críticas (M08 –
dashboards)"*. Esto es clave para el alcance de la corrección (ver Decisión).

### Gaps detectados

1. **Sin identidad M06** (el gap que reporta QA, mismo patrón que M04 en
   INC-M02-90-G92): no existe rol ni usuario técnico para M06 en `sgpmp_dev`.
2. **El FA-03 (422 por métricas de peso insuficientes) no está implementado
   en absoluto.** Ya documentado como gap en `estado_M02.md` (RF-50): *"No
   hay validación de integridad referencial/completitud mínima antes de
   exponer datos... si no hay eventos de peso, el campo simplemente sale
   `null`."* Confirmado en código: `_obtener_metricas()` en
   `indicadores_repository.py` ni siquiera recibe `fecha_inicio`/`fecha_fin`
   — consulta `vw_rf47_ficha_integral_activo` (snapshot "actual" del activo),
   sin acotar al rango solicitado. No existía ninguna consulta que contestara
   "¿hay mediciones de peso dentro de este rango?".
3. Sin este segundo gap resuelto, otorgarle a M06 solo la identidad no
   habría sido suficiente para que TC-M02-157 termine de pasar: el propio
   reporte de QA anticipa en su "Resultado esperado cuando se desbloquee"
   que, una vez disponible M06, debe verificarse el 422 — que hoy no existe.

## Decisión

1. **Identidad M06**: mismo patrón que M04 (rol técnico `'Integración M06'`
   + usuario `integracion.m06.test@pecuaria.co`, sin mecanismo M2M nuevo).
2. **Scope de valoración/NIC-41**: se le otorga a M06 únicamente el scope
   `datos_analiticos_metricas` (recurso 62, creado en INC-M02-92-G93) —
   es el único que TC-M02-157 pide, y coincide con lo que RF-50 describe
   como dato de valoración (peso, biomasa, indicadores).
3. **El 422 de FA-03 se implementa, pero acotado a M06** (`modulo_consumidor
   == 'modulo6'`), no de forma universal. Aplicarlo a todos los consumidores
   habría sido una regresión real: hoy Administrador/Productor/Veterinario/
   Ingeniero de Campo reciben `200` con `metricas_actuales` en `null` cuando
   no hay peso — comportamiento que RF-50 no prohíbe para ellos, y que la
   propia distinción "consistencia fuerte (M06) vs. eventual (resto)" del RF
   respalda como intencional, no como un descuido a corregir de forma
   global. Se activa quando `tipo_dato` pide la sección de métricas
   (`'metricas'` o `'todos'`).

**Nueva query** (`IndicadoresRepository.contar_metricas_peso_en_rango`):
reutiliza el mismo `WHERE` que ya usa `_calcular_ganancia_peso` (RF-51) —
`modulo2.eventos_crecimeinto` con `tipo_medicion='peso'`, acotado al rango —
en vez de inventar una fuente de datos nueva.

## SQL aplicado

Migración Alembic `2b747aaae732` (`v5.4.0_inc_m02_93_g93_identidad_m06_scope_metricas`,
`down_revision=d944f4d8c215`) — **depende de que `d944f4d8c215` (INC-M02-92-G93,
PR #390) se aplique primero**, porque referencia el recurso `datos_analiticos_metricas`
que esa migración crea. El propio archivo lo valida con un `RAISE EXCEPTION`
explícito si ese recurso todavía no existe.

A diferencia de `d944f4d8c215`, esta migración **sí tiene un `downgrade()`
real y reversible** — ninguno de los permisos de M06 usa el prefijo `admin_`,
así que no hereda la inmutabilidad por trigger.

**Verificado en vivo contra `sgpmp_dev`** (credenciales `dba`, dentro de una
transacción con `ROLLBACK` final — nunca se dejó aplicado): se corrieron en
secuencia `d944f4d8c215` → `2b747aaae732` (upgrade) → `2b747aaae732`
(downgrade), confirmando que el rol/usuario/permisos de M06 se crean
correctamente y que el downgrade los elimina limpiamente. Al final,
`sgpmp_dev` quedó sin cambios (58 recursos, 12 roles, `alembic_version` sin
modificar).

## Código

- `src/biological_assets/domain/repositories/indicadores_repository.py`:
  nuevo método de puerto `contar_metricas_peso_en_rango`.
- `src/biological_assets/infrastructure/repositories/indicadores_repository.py`:
  implementación (reutiliza el `WHERE` de `_calcular_ganancia_peso`).
- `src/biological_assets/application/use_cases/gestion/consultar_datos_consolidados_use_case.py`:
  `modulo_consumidor` ahora se resuelve una sola vez al inicio (antes solo se
  calculaba al final, para la auditoría); si resuelve a `'modulo6'` y
  `tipo_dato` incluye métricas, valida el conteo y lanza `BusinessRuleError`
  (`METRICAS_PESO_INSUFICIENTES`, HTTP 422) con el mensaje literal de RF-50
  FA-03 antes de construir la respuesta.
- `src/biological_assets/infrastructure/routers/activo_biologico_router.py`:
  se agrega `422` a `responses` del endpoint (documentación OpenAPI).

## Fuera de alcance

- **El 422 no queda auditado en RF-52.** Mismo patrón ya existente en este
  use case: los rechazos por `404` (activo inexistente) y `409`
  (inconsistencia jerárquica) tampoco emiten evento de auditoría hoy — este
  cambio no introduce una asimetría nueva, mantiene el comportamiento
  existente del archivo. Corregir esto (auditar también los rechazos 404/409/422)
  es un gap más amplio, ya cubierto en general por el Hallazgo transversal #6
  de `estado_M02.md` sobre auditoría best-effort.
- **Identidades para M03 y M08** (los 2 consumidores de RF-50 que aún no
  tienen identidad): sin un incidente puntual que los pida explícitamente,
  igual que se dejó fuera en INC-M02-92-G93 para M06 hasta este ticket.
- **Scope de M06 limitado a `metricas`.** El issue solo pide el scope de
  valoración/NIC-41; si M06 también necesita `estado` (para saber si el
  activo sigue vigente antes de valorarlo) u otro tipo_dato, es una
  ampliación de permisos vía la API de roles existente
  (`POST /roles/{id_rol}/permisos`), no requiere una migración nueva.
- **Distinguir INDIVIDUAL vs. POBLACIONAL en el conteo de métricas de peso.**
  La query nueva no discrimina por `tipo_activo`, igual que la query
  existente de `_calcular_ganancia_peso` que reutiliza — consistente con el
  código ya existente, no una limitación nueva de este cambio.
