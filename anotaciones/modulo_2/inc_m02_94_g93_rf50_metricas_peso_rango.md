# INC-M02-94-G93 [RF-50][TC-M02-157] — Suficiencia de métricas PESO en rango

**Issue:** [#392](https://github.com/Arekkazu/sgpmp-backend/issues/392)

## Qué reportó QA

Diagnosticando TC-M02-157 (bloqueado oficialmente por falta de identidad M06,
ver INC-M02-93-G93 / #391) con un consumidor autorizado existente, sobre el
activo 279 y el rango `2026-06-01 → 2026-08-31` (0 métricas PESO dentro de
ese rango, 4 métricas PESO reales en septiembre, fuera de rango):

- `GET /{id}/datos-consolidados` respondió `200 OK`.
- `historial_eventos` respetó el rango y quedó vacío (correcto).
- `metricas_actuales.peso_actual` mostró la métrica de septiembre — **fuera**
  del rango solicitado, sin ninguna indicación de que estaba fuera de rango.
- No existía ninguna validación de suficiencia de métricas PESO que
  produjera el `422` que exige el flujo alterno "Datos insuficientes para
  proceso crítico (NIC 41)" de RF-50.

## Preguntas abiertas que dejó el issue (sin resolver unilateralmente aquí)

1. ¿`metricas_actuales` debería respetar siempre `fecha_inicio`/`fecha_fin`?
2. ¿Debe señalarse cuando una métrica queda fuera del periodo consultado?
3. ¿Dónde debe implementarse la regla de suficiencia de métricas PESO?
4. ¿En qué condiciones debe devolverse `HTTP 422`?

## Decisión tomada en este PR

Se implementa la lectura más literal del texto de RF-50 (flujo alterno
"Datos insuficientes para proceso crítico (NIC 41)"), sin rediseñar el
contrato de `metricas_actuales`:

> "El módulo M06 solicita datos de valoración, pero el activo no registra
> eventos de peso o crecimiento en el periodo consultado" → HTTP 422.

- **Cuándo se valida:** solo cuando el consumidor pide un **rango de fechas
  explícito** (`fecha_inicio` y/o `fecha_fin`) **y** `tipo_dato` incluye
  métricas (`metricas` o `todos`). Sin rango explícito, no se valida — se
  mantiene el comportamiento actual (última métrica conocida, sin importar
  antigüedad), porque sin rango no hay "periodo consultado" contra el cual
  juzgar insuficiencia.
- **Qué se valida:** que exista al menos un evento de crecimiento con
  `tipo_medicion = 'PESO'` dentro de `[fecha_inicio, fecha_fin]` para ese
  activo (`SqlAlchemyIndicadoresRepository.existen_metricas_peso_en_rango`,
  nuevo método del puerto `IndicadoresRepository`).
- **Dónde se valida:** en `ConsultarDatosConsolidadosUseCase.execute()`,
  antes de construir la respuesta — es una regla de negocio, no una
  transformación de datos, así que vive en el use case (`CLAUDE.md`).
- **Qué NO se cambia:** el contenido de `metricas_actuales` cuando la
  validación pasa. No se agrega un flag "fuera de rango" ni se filtra
  `metricas_actuales` por fecha — eso es la pregunta 1/2 de QA, que sigue
  abierta y requiere una decisión de Análisis sobre el contrato del campo
  (¿debería `metricas_actuales` dejar de ser "estado actual" y pasar a ser
  "estado dentro del rango"? Eso afecta a todo consumidor existente que
  llama sin rango esperando el estado más reciente).

## Por qué no se ató la validación a la identidad M06

El flujo alterno de RF-50 dice literalmente "el módulo M06 solicita...", pero
condicionar la regla a la identidad del llamador habría acoplado esta
validación a INC-M02-93-G93/#391 (identidad M06), que en la fecha de este PR
es un issue separado y encadenado. La regla de suficiencia de datos es válida
para cualquier consumidor que pida métricas en un rango — no depende de
quién pregunta, sino de si los datos alcanzan para responder. Mantenerla
desacoplada de la identidad del llamador también evita que un humano con el
mismo permiso de lectura (recurso 29, acción 2) reciba una respuesta
"suficiente" con datos que en realidad no cubren el rango pedido.

## Qué cambia

- `IndicadoresRepository.existen_metricas_peso_en_rango` (puerto, nuevo).
- `SqlAlchemyIndicadoresRepository.existen_metricas_peso_en_rango` (implementación).
- `ConsultarDatosConsolidadosUseCase.execute()`: nueva validación → `422 METRICAS_PESO_INSUFICIENTES`.
- Pruebas unitarias (`tests/biological_assets/test_inc_m02_94_g93_rf50_metricas_peso_rango.py`)
  y de integración contra Postgres real
  (`tests/integration/test_inc_m02_94_g93_rf50_metricas_peso_rango_e2e.py`).

## Pendiente explícito (no se resuelve aquí)

Reejecutar TC-M02-157 con la identidad M06 real una vez esté disponible
(#391) contra el mismo escenario (activo 279, rango `2026-06-01 → 2026-08-31`)
para confirmar el `422` de punta a punta con el consumidor oficial que exige
el caso de prueba.
