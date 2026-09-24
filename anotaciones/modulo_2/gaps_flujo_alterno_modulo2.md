# Auditoría de Flujo Alterno — Módulo 2 (Activos Biológicos)

Comparación entre la sección **Flujo alterno** de cada RF en
`anotaciones/Requerimientos/Especificacion-Requerimientos-Modulo2.md` y el
comportamiento real del código en `src/biological_assets`. Solo lectura — no
se modificó código. Verificado contra `dev` en `5cd6f76c`.

Convención: `código_dominio → HTTP` según `src/shared/errors.py`
(`ValidationError`→400, `ConflictError`→409, `BusinessRuleError`/`FlowError`→422,
`NotFoundError`→404, `AuthorizationError`→403, sin manejo específico→500).
**Todo error de Pydantic (DTO) se traduce globalmente a HTTP 400** vía
`request_validation_error_handler` en `src/shared/error_handlers.py` — esto es
clave para varios de los gaps: cuando un RF pide 422 para un caso que el
código valida con un `@field_validator` de Pydantic, el resultado real es 400.

> **Estado (2026-09-23): corregido en la rama `fix/gaps-flujo-alterno-m02`**
> (derivada de `fix/inc-m02-51-g44-refresh-token-http-500`), más **RF-52 E5** en
> `feat/rf52-e5-reconciliacion-bitacora`, encima de ella: un PR aparte porque trae
> la migración `094d4799c3ca` (tipo de evento y permiso), que requiere autorización
> del DBA. **Con los dos PRs no queda ningún gap abierto en M02.** Cada fila
> corregida lleva el `archivo:línea` de la corrección. Tres de los gaps ya los
> habían cerrado PRs posteriores a la auditoría: RF-49 especie (#354), RF-49
> dispositivo desconectado (#377) y RF-50 NIC 41 (#424). Sin migración de BD.
>
> **Recuento:** la tabla resumen original suma 16 ❌ y 5 ⚠️, pero contando fila
> por fila en las tablas de detalle son **18 ❌ y 4 ⚠️**: RF-52 tiene 4 ❌ (E1,
> E2, E3 y E5) y ningún ⚠️. Las columnas de abajo usan el recuento real.
>
> **Códigos HTTP que cambian para el frontend** (el `error_code` se conserva
> salvo donde se indica):
>
> | Endpoint | Caso | Antes → Ahora |
> |---|---|---|
> | `POST .../eventos/crecimiento`, `.../sanitario`, `.../reproductivo` | fecha futura o incoherente | 422 → **400** |
> | `POST .../eventos/reproductivo` | falta `id_padre` o `numero_crias` | 422 → **400** |
> | `POST .../eventos/productivo` | fecha inválida (futura, anterior al activo, fuera de fase) | 400 → **422** |
> | `POST .../eventos/productivo` | cantidad ≤ 0 (nuevo código `CANTIDAD_INVALIDA`) | 400 → **422** |
> | `POST .../eventos/productivo` | unidad de medida incompatible | 400 → **422** |
> | `PATCH .../estado` | fecha futura (`FECHA_FUTURA`), motivo vacío (`MOTIVO_REQUERIDO`) | 400 → **422** |
> | `PATCH .../estado` | CERRADO o BAJA (`VALIDACIONES_PREVIAS_REQUERIDAS`) | 400 → **422** |
> | `GET .../historial` | fecha_inicio > fecha_fin (`RANGO_FECHAS_INVALIDO`) | 400 → **422** |
> | `GET .../ficha-integral` | una sección no carga | 500 → **200** con advertencia de la sección |
> | `GET .../indicadores` | consumo de alimento en 0 (`CONSUMO_ALIMENTO_CERO`) | 422 → **409** |
> | `GET .../indicadores` | outlier crítico (`OUTLIER_CRITICO`) | 422 → **500** |
> | `GET .../datos-consolidados` | métrica negativa (`METRICAS_CORRUPTAS`) | 200 → **500** |

## Hallazgo transversal (antes de la tabla por RF)

El patrón correcto para que un caso de negocio responda 422 (no 400) es
levantar `BusinessRuleError` **dentro del use case**, nunca un validador de
Pydantic en el DTO — el equipo lo documenta explícitamente en comentarios de
código en **RF-33** (`_validar_origen_financiero`) y **RF-48** (fecha de
transferencia futura): *"vive aquí ... para que el rechazo sea
BusinessRuleError -> 422, como exige el RF, y no un 400 genérico de
RequestValidationError"*. RF-33, RF-45, RF-48, RF-49 y RF-34 aplican este
patrón de forma consistente y quedan sin gaps de código HTTP. RF-40, RF-41,
RF-42, RF-44, RF-46 y RF-51 no lo aplicaron para casos equivalentes, y RF-43
lo aplica al revés (usa `ValidationError` donde el RF pide 422). No es una
limitación arquitectónica — es inconsistencia de ejecución entre endpoints
hermanos del mismo módulo.

Segundo patrón transversal: la función compartida `validar_fecha_evento`
(`gestion/_event_validations.py`, usada por RF-40/41/42) levanta
`BusinessRuleError` (422) para toda fecha inválida, pero RF-39/40/41/42 piden
**400** para ese caso. Un único fix en esa función resolvería el gap en las
tres RFs a la vez.

## Resumen

| RF | Título | Casos revisados | ❌ Gaps | ⚠️ Parciales |
|----|--------|:---:|:---:|:---:|
| RF-33 | Registro de activos | 5 | 0 | 0 |
| RF-34 | Asociación a infraestructura (consulta) | 4 | 0 | 0 |
| RF-35 | Gestión individual | — | N/A | N/A |
| RF-36 | Gestión poblacional | — | N/A | N/A |
| RF-37 | Gestión de fases | — | N/A | N/A |
| RF-38 | Cierre de ciclo | 7 | 0 | 0 |
| RF-39 | Eventos biológicos (umbrella) | 4 | ver RF-40/41/42 | — |
| RF-40 | Eventos de crecimiento | 6 | 1 | 0 |
| RF-41 | Eventos sanitarios | 5 | 1 | 0 |
| RF-42 | Eventos reproductivos | 8 | 1 | 1 |
| RF-43 | Eventos productivos | 9 | 3 | 0 |
| RF-44 | Cambio de estado | 8 | 2 | 1 |
| RF-45 | Registro de bajas | 7 | 0 | 0 |
| RF-46 | Consulta de historial | 5 | 1 | 0 |
| RF-47 | Ficha integral | 5 | 0 | 1 |
| RF-48 | Transferencia interna | 11 | 0 | 0 |
| RF-49 | Asociación sensor IoT | 6 | 2 | 0 |
| RF-50 | Datos consolidados | 7 | 2 | 0 |
| RF-51 | Indicadores zootécnicos (x2, texto idéntico) | 7 | 1 | 1 |
| RF-52 | Auditoría y trazabilidad | 5 | 3 | 1 |

**Total: ~104 casos revisados, 16 gaps ❌, 5 parciales ⚠️.**
| RF | Título | Casos revisados | ❌ Gaps | ⚠️ Parciales | Pendiente hoy |
|----|--------|:---:|:---:|:---:|:---:|
| RF-33 | Registro de activos | 5 | 0 | 0 | 0 |
| RF-34 | Asociación a infraestructura (consulta) | 4 | 0 | 0 | 0 |
| RF-35 | Gestión individual | — | N/A | N/A | — |
| RF-36 | Gestión poblacional | — | N/A | N/A | — |
| RF-37 | Gestión de fases | — | N/A | N/A | — |
| RF-38 | Cierre de ciclo | 7 | 0 | 0 | 0 |
| RF-39 | Eventos biológicos (umbrella) | 4 | ver RF-40/41/42 | — | — |
| RF-40 | Eventos de crecimiento | 6 | 1 | 0 | 0 |
| RF-41 | Eventos sanitarios | 5 | 1 | 0 | 0 |
| RF-42 | Eventos reproductivos | 8 | 1 | 1 | 0 |
| RF-43 | Eventos productivos | 9 | 3 | 0 | 0 |
| RF-44 | Cambio de estado | 8 | 2 | 1 | 0 |
| RF-45 | Registro de bajas | 7 | 0 | 0 | 0 |
| RF-46 | Consulta de historial | 5 | 1 | 0 | 0 |
| RF-47 | Ficha integral | 5 | 0 | 1 | 0 |
| RF-48 | Transferencia interna | 11 | 0 | 0 | 0 |
| RF-49 | Asociación sensor IoT | 6 | 2 | 0 | 0 |
| RF-50 | Datos consolidados | 7 | 2 | 0 | 0 |
| RF-51 | Indicadores zootécnicos (x2, texto idéntico) | 7 | 1 | 1 | 0 |
| RF-52 | Auditoría y trazabilidad | 5 | 4 | 0 | 0 |

**Total: ~104 casos revisados, 18 gaps ❌, 4 parciales ⚠️. Pendientes hoy: 0.**

RF-33, RF-34, RF-38, RF-45 y RF-48 están implementados sin gaps de código HTTP
— casi calcados al RF, incluyendo comentarios en código que citan
explícitamente la exigencia del RF. RF-35, RF-36 y RF-37 no tienen sección de
flujo alterno con códigos HTTP en el documento fuente (RF-37 solo dice "en
caso de error, rollback completo", sin código) — no son auditables contra una
spec que no existe.

---

## RF-33 — Registro de Activos Biológicos

El documento no trae un bloque `**Flujo alterno:**` estructurado; los casos
con código HTTP están embebidos en **Restricciones** (RFC-004).

| Caso | HTTP esperado | HTTP real | Archivo:línea | Veredicto |
|------|:---:|:---:|---|:---:|
| Atributo dinámico obligatorio faltante/`null` | 422 | 422 (`BusinessRuleError` `ATRIBUTO_REQUERIDO`) | `registro/registrar_activo_use_case.py:78` | ✅ |
| Atributo dinámico tipo incompatible | 422 | 422 (`BusinessRuleError` `ATRIBUTO_TIPO_INVALIDO`) | `registro/registrar_activo_use_case.py:117` | ✅ |
| Atributo dinámico fuera de rango | 422 | 422 (`BusinessRuleError` `ATRIBUTO_FUERA_DE_RANGO`) | `registro/registrar_activo_use_case.py:127,133` | ✅ |
| Atributo no configurado/no reconocido | 400 | 400 (`ValidationError` `ATRIBUTO_INVALIDO`) | `registro/registrar_activo_use_case.py:87` | ✅ |
| `origen_financiero_activo` COMPRA/DONACION sin costo o soporte | 422 | 422 (`BusinessRuleError`) | `registro/registrar_activo_use_case.py:30,36` | ✅ |

Nota: el comentario en `_validar_origen_financiero` (línea 22-26) documenta
explícitamente que la validación vive en el use case *"para que el rechazo
sea BusinessRuleError -> 422, como exige el RF"* — patrón ejemplar.

---

## RF-34 — Asociación a Infraestructura (consulta)

| Caso | HTTP esperado | HTTP real | Archivo:línea | Veredicto |
|------|:---:|:---:|---|:---:|
| E1 / CA-4: activo inexistente | 404 | 404 (`NotFoundError`) | `registro/consultar_asociacion_use_case.py:75` | ✅ |
| E2 / CA-5: sin asociación activa | 404 | 404 (`NotFoundError` `ASOCIACION_INFRAESTRUCTURA_NO_ENCONTRADA`) | `registro/consultar_asociacion_use_case.py:105` | ✅ |
| CA-6: sin permiso sobre la finca | 403 | 403 (RBAC `require_permission_m02` + filtro `ids_fincas_permitidas`) | `routers/activo_biologico_router.py:526` | ✅ |
| CA-7: intento de escritura por este endpoint | 405 | 405 implícito (solo `GET` definido en la ruta) | `routers/activo_biologico_router.py:523` | ✅ |

Bonus: la detección de solapamiento de periodos (`_detectar_solapamiento`) se
reporta como `advertencia_integridad` sin bloquear la consulta, tal como pide
la Restricción 4 del RF.

---

## RF-35 / RF-36 / RF-37

Sin bloque de flujo alterno con código HTTP en el documento fuente:
- RF-35 y RF-36: cero menciones de `HTTP` en todo el texto del RF.
- RF-37: una sola mención, genérica ("en caso de error, rollback completo de
  la operación"), sin código.

No hay contra qué auditar. Si se necesita cobertura de estos casos, el primer
paso es que Análisis complete la ficha, no una inferencia del código hacia
atrás.

---

## RF-38 — Cierre del Ciclo Productivo

| Caso | HTTP esperado | HTTP real | Archivo:línea | Veredicto |
|------|:---:|:---:|---|:---:|
| Activo no encontrado | 404 | 404 (`NotFoundError`) | `gestion/cerrar_ciclo_use_case.py:55` | ✅ |
| Estado inválido para cierre (ya CERRADO/BAJA) | 409 | 409 (`ConflictError`) | `gestion/cerrar_ciclo_use_case.py:63` | ✅ |
| Fecha de cierre futura | 400 | 400 (Pydantic `fecha_no_futura` → handler global) | `dto/cerrar_ciclo_dto.py:20` | ✅ |
| Fecha de cierre anterior al último evento | 400 | 400 (`ValidationError`) | `gestion/cerrar_ciclo_use_case.py:97` | ✅ |
| Motivo de cierre vacío | 400 | 400 (Pydantic `motivo_no_vacio` → handler global) | `dto/cerrar_ciclo_dto.py:27` | ✅ |
| Sin fase productiva activa | 422 | 422 (`BusinessRuleError`) | `gestion/cerrar_ciclo_use_case.py:84` | ✅ |
| Acceso no autorizado (rol no habilitado) | 403 | 403 (RBAC, acción 4 sobre recurso 29) | `routers/activo_biologico_router.py:841` | ✅ |
| Fallo en persistencia atómica | 500 | 500 (excepción no controlada → handler global) | `gestion/cerrar_ciclo_use_case.py:131` | ✅ |

Cero gaps — incluyendo el detalle no trivial de que "fecha inconsistente"
cubre dos condiciones (futura / anterior al último evento) y ambas están
implementadas, cada una en una capa distinta pero con el mismo HTTP.

---

## RF-39 — Registro de Eventos Biológicos (umbrella)

RF-39 no tiene endpoint propio de registro (su GET de consulta en el router
usa `rf_origen='RF39'`, pero es solo lectura). Sus 4 casos de flujo alterno
son idénticos en sustancia a los de RF-40/41/42 (activo no existe, estado no
operativo, fecha inválida, datos obligatorios faltantes) y se verifican allí.
Los estados que "permiten registro de eventos" que define aquí (ACTIVO,
EN_TRATAMIENTO, AISLADO) sí están implementados literalmente en
`_event_validations.py:10` y son la fuente de verdad que usan RF-41 y RF-42
(ver nota en esas secciones sobre la aparente contradicción con su propio
texto de "solo ACTIVO").

---

## RF-40 — Registro de Eventos de Crecimiento

| Caso | HTTP esperado | HTTP real | Archivo:línea | Veredicto |
|------|:---:|:---:|---|:---:|
| Activo no existe | 404 | 404 (`NotFoundError`) | `gestion/registrar_evento_crecimiento_use_case.py:74` | ✅ |
| Activo no está en estado ACTIVO | 409 | 409 (`ConflictError`) | `gestion/registrar_evento_crecimiento_use_case.py:80` | ✅ |
| Fecha inválida/incoherente | 400 | **422** (`BusinessRuleError`, vía `validar_fecha_evento`) | `gestion/_event_validations.py:36,44,53` | ❌ |
| Fecha inválida/incoherente | 400 | 400 (`ValidationError`, vía `validar_fecha_evento`) — antes 422 | `gestion/_event_validations.py:39,47,56` | ✅ corregido |
| Datos obligatorios faltantes (POBLACIONAL) | 400 | 400 (`ValidationError`) | `gestion/registrar_evento_crecimiento_use_case.py:141,147,153` | ✅ |
| Datos no numéricos | 400 | 400 (Pydantic `Decimal` coercion → handler global) | `dto/registrar_evento_crecimiento_dto.py:25` | ✅ |
| Unidad no corresponde al tipo de medición | 400 | 400 (Pydantic `validar_unidad_por_tipo` → handler global) | `dto/registrar_evento_crecimiento_dto.py:68` | ✅ |

---

## RF-41 — Registro de Eventos Sanitarios

| Caso | HTTP esperado | HTTP real | Archivo:línea | Veredicto |
|------|:---:|:---:|---|:---:|
| Activo no existe | 404 | 404 (`NotFoundError`) | `gestion/registrar_evento_sanitario_use_case.py:74` | ✅ |
| Activo no está en estado ACTIVO | 409 | 409 (`ConflictError`, vía `validar_estado_permite_eventos`) | `gestion/_event_validations.py:17` | ✅¹ |
| Fecha inválida/incoherente | 400 | **422** (`BusinessRuleError`) | `gestion/_event_validations.py:36,44,53` | ❌ |
| Fecha inválida/incoherente | 400 | 400 (`ValidationError`, misma función compartida) — antes 422 | `gestion/_event_validations.py:39,47,56` | ✅ corregido |
| Violación de secuencia lógica (diagnóstico previo) | 422 | 422 (`BusinessRuleError` `DIAGNOSTICO_PREVIO_REQUERIDO`) | `gestion/registrar_evento_sanitario_use_case.py:83` | ✅ |
| Datos obligatorios faltantes | 400 | 400 (Pydantic, campos requeridos del DTO) | `dto/registrar_evento_sanitario_dto.py` | ✅ |

¹ El código acepta ACTIVO, EN_TRATAMIENTO y AISLADO (no solo ACTIVO como dice
literalmente el texto de este RF) — sigue la especificación más detallada de
RF-39, que es la fuente de verdad y lista exactamente esos tres estados. No
se cuenta como gap.

---

## RF-42 — Registro de Eventos Reproductivos

| Caso | HTTP esperado | HTTP real | Archivo:línea | Veredicto |
|------|:---:|:---:|---|:---:|
| Activo no existe | 404 | 404 (`NotFoundError`) | `gestion/registrar_evento_reproductivo_use_case.py:83` | ✅ |
| Activo no está en estado ACTIVO | 409 | 409 (`ConflictError`, ver nota RF-41) | `gestion/_event_validations.py:17` | ✅ |
| Fase productiva incompatible | 409 | 409 (`ConflictError` `FASE_NO_COMPATIBLE_REPRODUCCION`) | `gestion/registrar_evento_reproductivo_use_case.py:98` | ✅ |
| Tipo de evento inválido para tipo de activo | 422 | 422 (`BusinessRuleError` `EVENTO_NO_PERMITIDO_LOTE`) | `gestion/registrar_evento_reproductivo_use_case.py:108` | ✅ |
| Fecha inválida/incoherente | 400 | **422** (`BusinessRuleError`) | `gestion/_event_validations.py:36,44,53` | ❌ |
| Activo relacionado inválido (padre/madre) | 404 | 404 (`NotFoundError` `ACTIVO_RELACIONADO_NO_ENCONTRADO`) | `gestion/registrar_evento_reproductivo_use_case.py:241,250` | ✅ |
| Violación de secuencia lógica | 422 | 422 (`BusinessRuleError` `SECUENCIA_REPRODUCTIVA_INVALIDA`) | `gestion/registrar_evento_reproductivo_use_case.py:134-167` | ✅ |
| Datos obligatorios faltantes (padre/nº crías) | 400 | **422** (`BusinessRuleError` `PADRE_REQUERIDO`/`NUMERO_CRIAS_REQUERIDO`) | `gestion/registrar_evento_reproductivo_use_case.py:118,172` | ⚠️ |

El ⚠️: estos dos campos son "obligatorios condicionales" (dependen de la
categoría del evento), tratados como regla de negocio → 422, mientras el RF
los agrupa bajo el caso genérico "datos obligatorios faltantes" → 400. Es una
zona gris razonable, pero técnicamente no coincide con el HTTP del RF.
| Fecha inválida/incoherente | 400 | 400 (`ValidationError`, misma función compartida) — antes 422 | `gestion/_event_validations.py:39,47,56` | ✅ corregido |
| Activo relacionado inválido (padre/madre) | 404 | 404 (`NotFoundError` `ACTIVO_RELACIONADO_NO_ENCONTRADO`) | `gestion/registrar_evento_reproductivo_use_case.py:241,250` | ✅ |
| Violación de secuencia lógica | 422 | 422 (`BusinessRuleError` `SECUENCIA_REPRODUCTIVA_INVALIDA`) | `gestion/registrar_evento_reproductivo_use_case.py:134-167` | ✅ |
| Datos obligatorios faltantes (padre/nº crías) | 400 | 400 (`ValidationError` `PADRE_REQUERIDO`/`NUMERO_CRIAS_REQUERIDO`) — antes 422 | `gestion/registrar_evento_reproductivo_use_case.py:120,174` | ✅ corregido |

El antiguo ⚠️: estos dos campos son "obligatorios condicionales" (dependen de la
categoría del evento) y se trataban como regla de negocio → 422, mientras el RF
los agrupa bajo el caso genérico "datos obligatorios faltantes" → 400. Se
alinearon al RF: que la obligatoriedad dependa de la categoría no cambia que el
RF los clasifique como dato faltante.

---

## RF-43 — Registro de Eventos Productivos

El RF con más gaps del módulo: usa `ValidationError` (400) para varios casos
que el propio RF etiqueta explícitamente como "Error de validación" con
**HTTP 422** — el patrón invertido respecto a RF-40/41/42 (que usan 422 donde
el RF pide 400).

| Caso | HTTP esperado | HTTP real | Archivo:línea | Veredicto |
|------|:---:|:---:|---|:---:|
| E-01: estado no ACTIVO | 409 | 409 (`ConflictError`) | `gestion/registrar_evento_productivo_use_case.py:71` | ✅ |
| E-02: sin fase productiva activa | 422 | 422 (`BusinessRuleError`) | `gestion/registrar_evento_productivo_use_case.py:107` | ✅ |
| E-03: tipo de producto fuera de catálogo | 422 | 422 (`BusinessRuleError`) | `gestion/registrar_evento_productivo_use_case.py:84` | ✅ |
| E-04: tipo de producto no habilitado en fase | 422 | 422 (`BusinessRuleError`) | `gestion/registrar_evento_productivo_use_case.py:119` | ✅ |
| E-05: fecha del evento inválida | 422 | **400** (`ValidationError`) | `gestion/registrar_evento_productivo_use_case.py:136,146,162,183` | ❌ |
| E-06: cantidad inválida (≤0) | 422 | **400** (Pydantic `cantidad_positiva`) | `dto/registrar_evento_productivo_dto.py:37` | ❌ |
| E-07: unidad de medida incompatible | 422 | **400** (`ValidationError`) | `gestion/registrar_evento_productivo_use_case.py:95` | ❌ |
| E-08: duplicidad | 409 | 409 (`ConflictError`) | `gestion/registrar_evento_productivo_use_case.py:194` | ✅ |
| E-09: fallo transaccional | 500 | 500 (excepción no controlada) | `gestion/registrar_evento_productivo_use_case.py:225` | ✅ |

| E-05: fecha del evento inválida | 422 | 422 (`BusinessRuleError`: futura, anterior al activo, fuera de fase) — antes 400 | `gestion/registrar_evento_productivo_use_case.py:140-205` | ✅ corregido |
| E-06: cantidad inválida (≤0) | 422 | 422 (`BusinessRuleError` `CANTIDAD_INVALIDA`, con el valor ingresado en el mensaje) — antes 400 de Pydantic; el validador salió del DTO | `gestion/registrar_evento_productivo_use_case.py:97` | ✅ corregido |
| E-07: unidad de medida incompatible | 422 | 422 (`BusinessRuleError`) — antes 400 | `gestion/registrar_evento_productivo_use_case.py:108` | ✅ corregido |
| E-08: duplicidad | 409 | 409 (`ConflictError`) | `gestion/registrar_evento_productivo_use_case.py:194` | ✅ |
| E-09: fallo transaccional | 500 | 500 (excepción no controlada) | `gestion/registrar_evento_productivo_use_case.py:225` | ✅ |

Un valor no numérico en `cantidad_producida` sigue saliendo 400: falla la
conversión de tipo de Pydantic antes de llegar a cualquier regla, y E-06 habla
de un valor numérico que no es positivo.

---

## RF-44 — Gestión del Estado del Activo Biológico

| Caso | HTTP esperado | HTTP real | Archivo:línea | Veredicto |
|------|:---:|:---:|---|:---:|
| E-01: activo inexistente | 404 | 404 (`NotFoundError`) | `gestion/cambiar_estado_use_case.py:54` | ✅ |
| E-02: BAJA irreversible | 409 | 409 (`ConflictError`) | `domain/entities/activo_biologico.py:427` | ✅ |
| E-03: estado redundante | 409 | 409 (`ConflictError`) | `domain/entities/activo_biologico.py:432` | ✅ |
| E-04: transición no permitida | 422 | 422 (`BusinessRuleError`) | `domain/entities/activo_biologico.py:442` | ✅ |
| E-05: fecha futura | 422 | **400** (Pydantic `fecha_no_futura`) | `dto/cambiar_estado_dto.py:40` | ❌ |
| E-06: motivo vacío | 422 | **400** (Pydantic `motivo_no_vacio`) | `dto/cambiar_estado_dto.py:47` | ❌ |
| E-07: módulo invocante sin validaciones previas | 422 | 400 (Pydantic `estado_valido`, rechaza CERRADO/BAJA en este endpoint) | `dto/cambiar_estado_dto.py:31` | ⚠️ |
| E-08: fallo transaccional | 500 | 500 (excepción no controlada) | `gestion/cambiar_estado_use_case.py:81` | ✅ |

E-07 ⚠️: la implementación real (rechazar CERRADO/BAJA en el DTO porque esos
estados solo se alcanzan vía RF-38/RF-45) es un mecanismo distinto al que
describe el RF ("módulo invocante sin validaciones previas"), pero cumple el
mismo propósito de fondo — igual da 400, no el 422 declarado.
| E-05: fecha futura | 422 | 422 (`BusinessRuleError` `FECHA_FUTURA`, referencia UTC) — antes 400 de Pydantic | `gestion/cambiar_estado_use_case.py:78` | ✅ corregido |
| E-06: motivo vacío | 422 | 422 (`BusinessRuleError` `MOTIVO_REQUERIDO`) — antes 400 de Pydantic | `gestion/cambiar_estado_use_case.py:89` | ✅ corregido |
| E-07: módulo invocante sin validaciones previas | 422 | 422 (`BusinessRuleError` `VALIDACIONES_PREVIAS_REQUERIDAS` para CERRADO/BAJA) — antes 400 de Pydantic | `gestion/cambiar_estado_use_case.py:66` | ✅ corregido |
| E-08: fallo transaccional | 500 | 500 (excepción no controlada) | `gestion/cambiar_estado_use_case.py:81` | ✅ |

E-07: rechazar CERRADO/BAJA en este endpoint (esos estados solo se alcanzan
vía RF-38/RF-45) cumple el mismo propósito que el RF describe como "módulo
invocante sin validaciones previas". Ahora lo rechaza el use case con 422 y el
mensaje del RF; el DTO solo rechaza (400) un estado que no existe en el sistema.

---

## RF-45 — Registro de Bajas del Activo Biológico

| Caso | HTTP esperado | HTTP real | Archivo:línea | Veredicto |
|------|:---:|:---:|---|:---:|
| Activo no encontrado | 404 | 404 (`NotFoundError`) | `gestion/registrar_evento_baja_use_case.py:60` | ✅ |
| Baja sobre activo ya en BAJA | 409 | 409 (`ConflictError`) | `gestion/registrar_evento_baja_use_case.py:67` | ✅ |
| Fecha de baja inconsistente (futura/anterior) | 400 | 400 (`ValidationError`) | `gestion/registrar_evento_baja_use_case.py:82,93` | ✅ |
| Cantidad de baja superior a existencia | 422 | 422 (`BusinessRuleError`) | `gestion/registrar_evento_baja_use_case.py:130` | ✅ |
| Datos obligatorios faltantes (tipo/motivo) | 400 | 400 (Pydantic, campos requeridos) | `dto/registrar_evento_baja_dto.py` | ✅ |
| Acceso denegado (restricción de rol) | 403 | 403 (RBAC) | `routers/activo_biologico_router.py:728` | ✅ |
| Fallo en persistencia transaccional | 500 | 500 (excepción no controlada) | `gestion/registrar_evento_baja_use_case.py:180` | ✅ |

Cero gaps. RF-45 es, junto con RF-33/34/38/48, ejemplo de implementación
completa.

---

## RF-46 — Consulta de Historial del Activo Biológico

| Caso | HTTP esperado | HTTP real | Archivo:línea | Veredicto |
|------|:---:|:---:|---|:---:|
| E-01: activo inexistente | 404 | 404 (`NotFoundError`) | `gestion/consultar_historial_use_case.py:43` | ✅ |
| E-02: sin permisos de consulta | 403 | 403 (RBAC) | `routers/activo_biologico_router.py:948` | ✅ |
| E-03: filtro de fecha inválido (inicio > fin) | 422 | **400** (Pydantic `validar_rango_fechas` en el DTO, capturado por el router y re-lanzado como `ValidationError`) | `dto/consultar_historial_dto.py:53`, `routers/activo_biologico_router.py:979` | ❌ |
| E-03: filtro de fecha inválido (inicio > fin) | 422 | 422 (`BusinessRuleError` `RANGO_FECHAS_INVALIDO`), validado antes de cualquier consulta a la BD — antes 400 | `gestion/consultar_historial_use_case.py:43` | ✅ corregido |
| E-04: sin registros en el filtro | 200 | 200 con `mensaje` informativo | `gestion/consultar_historial_use_case.py:59` | ✅ |
| E-05: fallo de carga del historial | 500 | 500 (excepción no controlada → handler global) | — | ✅ |

---

## RF-47 — Ficha Integral del Activo Biológico

| Caso | HTTP esperado | HTTP real | Archivo:línea | Veredicto |
|------|:---:|:---:|---|:---:|
| E-01: activo inexistente | 404 | 404 (`NotFoundError`) | `gestion/consultar_ficha_integral_use_case.py:40` | ✅ |
| E-02: sin permisos de consulta | 403 | 403 (RBAC) | `routers/activo_biologico_router.py:1018` | ✅ |
| E-03: módulo fuente no disponible (fallo parcial) | 200 con advertencia por sección | ⚠️ solo la vista base tiene *fallback* (`ficha_row` ausente → advertencia genérica); las 4 subconsultas de eventos (`_ultimos_sanitarios/productivos/crecimiento/reproductivos`) no tienen try/except individual — si una vista falla, se propaga como 500 para **toda** la ficha, no como degradación de una sola sección | `gestion/consultar_ficha_integral_use_case.py:142-222` | ⚠️ |
| E-03: módulo fuente no disponible (fallo parcial) | 200 con advertencia por sección | 200: cada sección (4 de eventos + indicadores) carga en su propio savepoint; si falla, llega vacía con "La sección [nombre] no pudo cargarse en este momento." y el resto se muestra. Antes, una vista caída tumbaba toda la ficha con 500. Verificado en vivo contra PostgreSQL | `gestion/consultar_ficha_integral_use_case.py:149` | ✅ corregido |
| E-04: inconsistencia entre módulos | 200 con advertencia | 200 con advertencia, pero solo detecta un tipo de inconsistencia (estado CERRADO/BAJA con fase aún activa) | `gestion/consultar_ficha_integral_use_case.py:63-71` | ✅ |
| E-05: fallo total de carga | 500 | 500 (excepción no controlada) | — | ✅ |

---

## RF-48 — Transferencia Interna de Activos Biológicos

| Caso | HTTP esperado | HTTP real | Archivo:línea | Veredicto |
|------|:---:|:---:|---|:---:|
| E-01: transferencia concurrente | 409 | 409 (`ConflictError`) | `gestion/registrar_transferencia_use_case.py:59` | ✅ |
| E-02: activo inexistente | 404 | 404 (`NotFoundError`) | `gestion/registrar_transferencia_use_case.py:70` | ✅ |
| E-03: estado no ACTIVO | 409 | 409 (`ConflictError`) | `gestion/registrar_transferencia_use_case.py:77` | ✅ |
| E-04: sin infraestructura origen | 422 | 422 (`BusinessRuleError`, INC-M02-88-G83) | `gestion/registrar_transferencia_use_case.py:91` | ✅ |
| E-05: infraestructura destino inexistente/inactiva | 422 | 422 (`BusinessRuleError`, INC-M02-88/89-G83) | `gestion/registrar_transferencia_use_case.py:120` | ✅ |
| E-06: destino igual a origen | 422 | 422 (`BusinessRuleError`, INC-M02-73-G80) | `gestion/registrar_transferencia_use_case.py:128` | ✅ |
| E-07: incompatibilidad especie (C1) | 422 | 422 (`BusinessRuleError`) | `gestion/registrar_transferencia_use_case.py:136` | ✅ |
| E-08: incompatibilidad tipo infra (C2) | 422 | 422 (`BusinessRuleError`) | `gestion/registrar_transferencia_use_case.py:147` | ✅ |
| E-09: capacidad excedida (C3) | 422 | 422 (`BusinessRuleError`) | `gestion/registrar_transferencia_use_case.py:183` | ✅ |
| E-10: fecha futura | 422 | 422 (`BusinessRuleError`, comentario explícito citando el contrato) | `gestion/registrar_transferencia_use_case.py:197` | ✅ |
| E-11: fallo transaccional | 500 | 500 (excepción no controlada) | `gestion/registrar_transferencia_use_case.py:285` | ✅ |

Cero gaps — el más completo y mejor documentado del módulo (varios `INC-*`
en comentarios muestran que cada 422 fue corregido a propósito en incidentes
previos).

---

## RF-49 — Asociación de Activos Biológicos con Sensores IoT

| Caso | HTTP esperado | HTTP real | Archivo:línea | Veredicto |
|------|:---:|:---:|---|:---:|
| Activo no válido (inexistente o BAJA) | 422 | 422 (`BusinessRuleError`, ambos sub-casos) | `gestion/asociar_sensor_activo_use_case.py:83,90` | ✅ |
| Conflicto de ubicación (fincas distintas) | 409 | 409 (`ConflictError`) | `gestion/asociar_sensor_activo_use_case.py:141` | ✅ |
| Sensor ya vinculado (exclusividad) | 409 | 409 (`ConflictError`) | `gestion/asociar_sensor_activo_use_case.py:160` | ✅ |
| Incompatibilidad de especie | 400 | **No implementado** — `SensorConsulta` (`domain/repositories/sensor_consulta_port.py`) no tiene campo de especie; no hay ninguna validación de compatibilidad biológica sensor↔activo en el use case | — | ❌ |
| Dispositivo IoT fuera de línea (warning, 201) | 201 + advertencia | **No implementado** — la respuesta hardcodea `advertencia=None` en el router; no se consulta heartbeat/última conexión en ningún punto | `routers/activo_biologico_router.py:1234,1274` | ❌ |
| Incompatibilidad de especie | 400 | 400 (`ValidationError` `INCOMPATIBILIDAD_ESPECIE_SENSOR`, contra `modulo9.compatibilidad_sensores_especies`) — ya lo había cerrado el PR #354 (INC-M02-36-G85) | `gestion/asociar_sensor_activo_use_case.py:174` | ✅ ya estaba |
| Dispositivo IoT fuera de línea (warning, 201) | 201 + advertencia | 201 con advertencia si el dispositivo no reporta hace más de 30 min — ya lo había cerrado el PR #377 (INC-M02-35-G84) | `gestion/asociar_sensor_activo_use_case.py:350` | ✅ ya estaba |
| Error de persistencia en auditoría | 500 | 500 (mismo bloque transaccional que el resto de la operación → rollback y re-raise) | `gestion/asociar_sensor_activo_use_case.py:270` | ✅ |

---

## RF-50 — Disponibilidad de Datos para Módulos Analíticos

| Caso | HTTP esperado | HTTP real | Archivo:línea | Veredicto |
|------|:---:|:---:|---|:---:|
| Activo no encontrado | 404 | 404 (`NotFoundError`) | `gestion/consultar_datos_consolidados_use_case.py:42` | ✅ |
| Rango de fechas inválido/futuro | 400 | 400 (Pydantic `validar_rango_fechas`, capturado y re-lanzado por el router) | `dto/datos_consolidados_dto.py:47` | ✅ |
| Datos insuficientes para NIC 41 | 422 | **No implementado** — no hay ninguna validación de "sin eventos de peso/crecimiento en el rango" en este use case | — | ❌ |
| Acceso de módulo no autorizado | 403 | 403 (RBAC) | `routers/activo_biologico_router.py:1354` | ✅ |
| Saturación de peticiones (rate limit) | 429 | 429, exactamente 100 req/min como pide el RF | `routers/activo_biologico_router.py:149,1355` | ✅ |
| Conflicto de integridad referencial | 409 | 409 (`ConflictError` `INCONSISTENCIA_JERARQUICA`) | `gestion/consultar_datos_consolidados_use_case.py:49` | ✅ |
| Fallo de normalización (outliers, ej. peso negativo) | 500 | **No implementado** — no hay detección de valores físicamente imposibles | — | ❌ |
| Datos insuficientes para NIC 41 | 422 | 422 (`BusinessRuleError` `METRICAS_PESO_INSUFICIENTES`, solo para M06, el consumidor de "consistencia fuerte") — ya lo había cerrado el PR #424 (INC-M02-93-G93) | `gestion/consultar_datos_consolidados_use_case.py:92` | ✅ ya estaba |
| Acceso de módulo no autorizado | 403 | 403 (RBAC) | `routers/activo_biologico_router.py:1354` | ✅ |
| Saturación de peticiones (rate limit) | 429 | 429, exactamente 100 req/min como pide el RF | `routers/activo_biologico_router.py:149,1355` | ✅ |
| Conflicto de integridad referencial | 409 | 409 (`ConflictError` `INCONSISTENCIA_JERARQUICA`) | `gestion/consultar_datos_consolidados_use_case.py:49` | ✅ |
| Fallo de normalización (outliers, ej. peso negativo) | 500 | 500 (`InfrastructureError` `METRICAS_CORRUPTAS`) si `peso_actual`, `biomasa_total` o `cantidad_actual` son negativos; la exportación se cancela antes de auditarse como consumida. Solo se valida el signo: no existe un catálogo de rangos plausibles por especie | `gestion/consultar_datos_consolidados_use_case.py:111` | ✅ corregido |

---

## RF-51 — Generación de Indicadores Zootécnicos

El bloque aparece **dos veces en el documento fuente** (líneas 4963 y 5221)
con **texto idéntico** en título, entradas, flujo alterno y salida — no son
dos requerimientos distintos mal numerados, es una duplicación literal del
mismo contenido. Se audita una sola vez.

| Caso | HTTP esperado | HTTP real | Archivo:línea | Veredicto |
|------|:---:|:---:|---|:---:|
| Activo no encontrado | 404 | 404 (`NotFoundError`) | `gestion/consultar_indicadores_use_case.py:55` | ✅ |
| Datos insuficientes (mínimo 2 mediciones) | 422 | 422 (`BusinessRuleError` `INDICADOR_NO_DISPONIBLE`) | `gestion/consultar_indicadores_use_case.py:75` | ✅ |
| Incompatibilidad biológica (sexo/especie) | 400 | 400 (`ValidationError` `INDICADOR_NO_APLICABLE_SEXO`) | `gestion/consultar_indicadores_use_case.py:94` | ✅ |
| División por cero (consumo = 0) | 409 | **422** — el caso "sin consumo validado" (`indicadores_repository.py:215-221`) marca `disponible=False` y cae en el mismo `INDICADOR_NO_DISPONIBLE` genérico que "datos insuficientes", sin distinguir el código HTTP que pide el RF | `gestion/consultar_indicadores_use_case.py:71-75` | ⚠️ |
| Rango de fechas fuera del ciclo biológico | 400 | 400 (`ValidationError` `RANGO_FUERA_DE_CICLO_VIDA`) | `gestion/consultar_indicadores_use_case.py:114,123,139` | ✅ |
| Inconsistencia de datos (outliers) | 500 | **No implementado** — no hay detección de valores físicamente imposibles | — | ❌ |
| Fallo de autorización de acceso a datos | 403 | 403 (RBAC) | `routers/activo_biologico_router.py:1283` | ✅ |

| División por cero (consumo = 0) | 409 | 409 (`ConflictError` `CONSUMO_ALIMENTO_CERO`, mensaje del RF). El indicador ahora trae `causa_no_disponible` y el use case decide el HTTP por causa, en vez de todo al 422 genérico | `gestion/consultar_indicadores_use_case.py:86`, `repositories/indicadores_repository.py:223` | ✅ corregido |
| Rango de fechas fuera del ciclo biológico | 400 | 400 (`ValidationError` `RANGO_FUERA_DE_CICLO_VIDA`) | `gestion/consultar_indicadores_use_case.py:114,123,139` | ✅ |
| Inconsistencia de datos (outliers) | 500 | 500 (`InfrastructureError` `OUTLIER_CRITICO`, mensaje del RF). La detección (ganancia de peso > 10 kg/día) ya existía desde el PR #271, pero respondía el 422 genérico; también invalida la conversión alimenticia que depende de ese peso | `gestion/consultar_indicadores_use_case.py:86`, `repositories/indicadores_repository.py:141,179` | ✅ corregido |
| Fallo de autorización de acceso a datos | 403 | 403 (RBAC) | `routers/activo_biologico_router.py:1283` | ✅ |

Con `tipo_indicador=TODOS` no se rechaza nada: la respuesta es 200 y cada
indicador no disponible viaja con su advertencia. Los códigos 409/422/500 aplican
cuando se pide un indicador concreto.

---

## RF-52 — Auditoría y Trazabilidad de Eventos de Transformación Biológica

| Caso | Comportamiento esperado | Comportamiento real | Archivo:línea | Veredicto |
|------|---|---|---|:---:|
| E1: fallo persistente del repositorio de auditoría (buffer + recuperación) | Eventos se acumulan en buffer, se recuperan sin pérdida al volver el servicio | **No implementado** — no existe mecanismo de buffer/cola de reintento; un fallo de BD en `registrar_evento_bitacora` se propaga como excepción normal | — | ❌ |
| E2: evento con esquema incompleto → `registro_incompleto=true`, no se rechaza | Se persiste con el flag y WARNING | **No implementado en la práctica** — el campo `registro_incompleto` existe en la entidad/modelo/schema (siempre `False` por defecto) pero **ningún use case lo pone en `True`**; en la práctica, un campo obligatorio faltante se **rechaza** vía Pydantic (400), justo lo contrario del principio "no perder trazabilidad" que pide el RF | `domain/entities/activo_biologico.py:516` | ❌ |
| E3: tormenta de eventos (control de tasa con priorización) | Cola con prioridad CRITICAL/ERROR > TRANSFORMACION_BIOLOGICA > INFO | **No implementado** — `registrar_evento_bitacora` es una escritura síncrona simple, sin cola ni priorización | `application/use_cases/_registrar_evento_bitacora.py` | ❌ |
| E4: consulta sin permisos por alcance de rol | HTTP 403 + registro propio en bitácora con `tipo_evento=ACCESO_NO_AUTORIZADO` | 403 (`AuthorizationError`) y se auto-registra en la bitácora antes de lanzar el error, exactamente como pide el RF | `gestion/consultar_bitacora_use_case.py:132-158` | ✅ |
| E5: inconsistencia entre RF-52 y RF-46 (reconciliación) | Alerta CRITICAL + registro correctivo manual | **No implementado** — no existe job ni endpoint de reconciliación entre `historial_activos` (RF-46) y `bitacora_auditoria_m02` (RF-52) | — | ❌ |

E4 es el único caso de RF-52 que es una respuesta HTTP directa y verificable
contra un endpoint; los otros cuatro son comportamientos de resiliencia de
sistema (buffer, cola con prioridad, reconciliación batch) que no tienen
equivalente en el código actual — son gaps reales, pero de una naturaleza
distinta (funcionalidad ausente) a los "código HTTP incorrecto" del resto del
informe.
| E1: fallo persistente del repositorio de auditoría (buffer + recuperación) | Eventos se acumulan en buffer, se recuperan sin pérdida al volver el servicio | El archivo de *fallback* que ya existía (#265) se volvió un buffer recuperable: guarda el evento completo, alerta con CRITICAL en el log y la primera escritura exitosa lo persiste en orden cronológico, con un registro `INDISPONIBILIDAD_AUDITORIA` del periodo caído. Si la recuperación falla, el buffer se conserva. Los rechazos auditados y el handler de 400 también pasan por él (antes se perdían en silencio). Además de la siguiente escritura exitosa, una tarea periódica de `main.py` (cada 5 s) lo vacía aunque no lleguen eventos nuevos. Verificado en vivo | `application/use_cases/_registrar_evento_bitacora.py:152,189`, `main.py:427` | ✅ corregido |
| E2: evento con esquema incompleto → `registro_incompleto=true`, no se rechaza | Se persiste con el flag y WARNING | Se persiste con `registro_incompleto=true`, la causa en `detalle_tecnico.causas_registro_incompleto` y un WARNING en el log. Se aplica en el repositorio, el único punto por el que pasan todos los emisores. Incompleto = campo base vacío, o sin `activo_biologico_id` en un evento TRANSFORMACION_BIOLOGICA, SANITARIO o CONTROL_ESTADO. Verificado en vivo | `domain/entities/activo_biologico.py:535`, `repositories/bitacora_auditoria_repository.py:45` | ✅ corregido |
| E3: tormenta de eventos (control de tasa con priorización) | Cola con prioridad CRITICAL/ERROR > TRANSFORMACION_BIOLOGICA > INFO | Con carga normal no cambia nada: todo se escribe en el momento. Si la tasa del proceso supera `AUDITORIA_M02_EVENTOS_POR_SEGUNDO` (100 por defecto, ventana de 5 s), los INFO que no son de transformación biológica se encolan en el buffer durable de E1 —ninguno se descarta— y la tarea periódica los persiste por lotes. CRITICAL, ERROR, WARNING y TRANSFORMACION_BIOLOGICA se siguen escribiendo de inmediato. Se registran `ALTA_CARGA_AUDITORIA_INICIO` y `..._FIN` como WARNING, con los eventos encolados | `application/use_cases/_registrar_evento_bitacora.py:72,265,301` | ✅ corregido |
| E4: consulta sin permisos por alcance de rol | HTTP 403 + registro propio en bitácora con `tipo_evento=ACCESO_NO_AUTORIZADO` | 403 (`AuthorizationError`) y se auto-registra en la bitácora antes de lanzar el error, exactamente como pide el RF | `gestion/consultar_bitacora_use_case.py:132-158` | ✅ |
| E5: inconsistencia entre RF-52 y RF-46 (reconciliación) | Alerta CRITICAL + registro correctivo manual | **Llave:** los 9 emisores que crean filas del historial RF-46 (eventos, estados, fases, transferencias y la creación del activo) dejan `detalle_tecnico.registros_rf46`; el avance automático de fase por crecimiento, que no dejaba ningún registro, ahora emite `FASE_AVANZADA_AUTOMATICAMENTE`. **Reconciliación:** una tarea diaria (05:00 UTC, con lock de PostgreSQL) revisa, con una corrida de retraso, las filas nuevas entre marcas. Lo que falta queda como `INCONSISTENCIA_RF46_RF52` (CRITICAL) con los ids, y quien puede crear el correctivo recibe una notificación interna (tipo de evento 28), igual que la alerta de RF-10. El historial no se modifica. **Correctivo:** `POST /activos-biologicos/auditoria/registros-correctivos`, solo Administrador, crea `REGISTRO_CORRECTIVO_AUDITORIA` con el motivo (404 si la fila no está en RF-46, 409 si ya tiene registro). Verificado en vivo contra la BD de dev | `domain/entities/activo_biologico.py:558`, `auditoria/reconciliar_bitacora_historial_use_case.py:44`, `auditoria/registrar_correctivo_auditoria_use_case.py:23`, `main.py:449` | ✅ corregido |

E4 es el único caso de RF-52 que es una respuesta HTTP directa y verificable
contra un endpoint; los otros cuatro son comportamientos de resiliencia de
sistema. Los cuatro quedaron resueltos. Dos decisiones que Análisis puede revisar:
- **E3:** el umbral de "alta carga" es configurable porque el RF no lo fija; 100
  eventos por segundo y proceso está muy por encima del uso actual. La
  restricción 3 del RF pide una bitácora asíncrona: con carga normal sigue siendo
  síncrona (después del commit de negocio y sin poder tumbarlo), para que un
  evento se vea en la bitácora apenas ocurre.
- **E5:** los registros anteriores a la llave no se pueden reconciliar; la
  primera corrida solo fija el punto de partida. `indicadores_zootecnicos` queda
  fuera: RF-51 calcula en el momento y ningún código de M02 escribe esa tabla,
  así que no hay emisor que pueda haber fallado.

---

## Lectura para QA

Antes de correr pruebas de "primera revisión" contra estos endpoints, tener
presente que un `400 Bad Request` recibido donde se esperaba `422
Unprocessable Entity` (o viceversa) en **RF-40/41/42/43/44/46/49/50/51/52**
no es necesariamente "el sistema no valida la regla" — la regla casi siempre
SÍ se aplica y el registro SÍ se rechaza; lo que no coincide es el código de
estado HTTP exacto que documenta el RF. Los gaps de funcionalidad genuinamente
ausente (nada se valida, el caso no se contempla) están en: RF-49
(incompatibilidad de especie, warning de dispositivo offline), RF-50/RF-51
(outliers, datos insuficientes NIC-41) y RF-52 (E1/E3/E5).
Con la corrección del 2026-09-23 los códigos HTTP de RF-40/41/42/43/44/46/47/50/51
coinciden con el texto del RF (ver la tabla de cambios al inicio). Pruebas
escritas contra el comportamiento anterior van a fallar en esos casos, y es lo
esperado. No queda ningún caso de flujo alterno sin cubrir en M02.

Pruebas del contrato: `tests/biological_assets/test_gaps_flujo_alterno_m02.py`.
