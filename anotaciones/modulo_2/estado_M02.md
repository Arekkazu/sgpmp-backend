# Estado de cumplimiento — Módulo 2 (Gestión de Activos Biológicos)

**Fecha de la auditoría:** 2026-08-06
**Alcance:** RF-33 a RF-52, contra el código real de `src/biological_assets/` y el estado real de la base de datos (schema `modulo2`, más lo que sus 5 adaptadores consultan de `modulo9`/`configuration` y de `modulo1`/RBAC), verificado con lectura directa de código (use cases, entidades, value objects, repositorios, DTOs, routers) y consultas directas vía MCP de Postgres (constraints, triggers, datos reales sembrados en dev).

**Nota metodológica importante:** el módulo 2 tiene una carpeta de notas de desarrollo propia, `anotaciones/modulo_2/` (un doc `cuNN_gaps_bd_*` y un doc `curls_m02_cuNN_*` por cada uno de los 13 casos de uso, más un `api_reference_m02_activos_biologicos.md` consolidado). Son notas internas de trabajo del desarrollador original, **no fuente de verdad** — se usaron como pista, no como verdad asumida, y en al menos dos puntos concretos (ver Hallazgos transversales #7) se confirmó que están desactualizadas respecto al código y al RBAC real en base de datos. Este documento describe lo que el código y la base de datos hacen **hoy**, verificado de forma independiente.

Los porcentajes son una estimación orientativa de cuánto del RF está cubierto, no una medición exacta — sirven para priorizar, no como cifra oficial.

---

## Resumen ejecutivo

| RF | Título | Veredicto | Cobertura aprox. |
|----|--------|-----------|-------------------|
| RF-33 | Registro de Activos Biológicos | ⚠️ Cumple parcialmente | ~65% |
| RF-34 | Asociación del Activo a Infraestructura (lectura) | ⚠️ Cumple parcialmente | ~55% |
| RF-35 | Gestión Individual de Activos Biológicos | ⚠️ Cumple parcialmente | ~55% |
| RF-36 | Gestión Poblacional de Activos Biológicos | ⚠️ Cumple parcialmente | ~40% |
| RF-37 | Gestión de Fases del Ciclo Productivo | ⚠️ Cumple parcialmente | ~55% |
| RF-38 | Cierre del Ciclo Productivo | ⚠️ Cumple parcialmente | ~85% |
| RF-39 | Registro de Eventos Biológicos (base) | ⚠️ Cumple parcialmente | ~80% |
| RF-40 | Registro de Eventos de Crecimiento | ⚠️ Cumple parcialmente | ~75% |
| RF-41 | Registro de Eventos Sanitarios | ✅ Cumple | ~90% |
| RF-42 | Registro de Eventos Reproductivos | ⚠️ Cumple parcialmente | ~65% |
| RF-43 | Registro de Eventos Productivos | ✅ Cumple | ~95% |
| RF-44 | Gestión del Estado del Activo Biológico | ⚠️ Cumple parcialmente | ~65% |
| RF-45 | Registro de Bajas | ⚠️ Cumple parcialmente | ~85% |
| RF-46 | Consulta de Historial del Activo | ⚠️ Cumple parcialmente | ~85% |
| RF-47 | Ficha Integral del Activo Biológico | ⚠️ Cumple parcialmente | ~65% |
| RF-48 | Transferencia Interna de Activos Biológicos | ⚠️ Cumple parcialmente | ~85% |
| RF-49 | Asociación de Activos Biológicos con Sensores IoT | ⚠️ Cumple parcialmente | ~65% |
| RF-50 | Disponibilidad de Datos para Módulos Analíticos | ⚠️ Cumple parcialmente | ~55% |
| RF-51 | Generación de Indicadores Zootécnicos | ⚠️ Cumple parcialmente | ~60% |
| RF-52 | Auditoría y Trazabilidad de Eventos (bitácora) | ⚠️ Cumple parcialmente | ~50% |

**Lectura rápida:** este es, por lejos, el módulo más desarrollado de los auditados hasta ahora — las 20 RFs tienen use cases reales y sustanciales (22 a 255 líneas), no stubs, con arquitectura hexagonal completa y ~25 triggers de base de datos reforzando reglas de negocio críticas (máquina de estados, inmutabilidad de eventos, fase única activa, cantidad/biomasa de lotes). No hay ningún RF en estado "no cumple" — el peor caso (RF-36, ~40%) tiene el motor de coherencia de datos bien resuelto, pero le falta la mitad del contrato funcional (ficha del lote como entidad propia, validación de densidad máxima). Los gaps más serios no son de "falta código": son grietas puntuales en el principio central de RF-44 (el punto de control de estado se puede saltar por un segundo camino), en la integridad de la bitácora de auditoría del RF-52 (sin inmutabilidad garantizada por DB, justo lo que el RF exige como no negociable), y un problema sistémico de traducción de errores que convierte violaciones de reglas de negocio detectadas solo por trigger en HTTP 500 genérico en vez del código específico documentado por cada RF. RBAC está, en general, muy bien resuelto (ningún `id_rol` quemado en ningún use case de los 20 auditados — mejor disciplina que el módulo 1), aunque el recorte de roles por recurso no siempre coincide con la lista de actores que cada RF describe en su ficha.

---

## RF-33 — Registro de Activos Biológicos

**Veredicto: ⚠️ Cumple parcialmente (~65%)**

### Qué SÍ cumple

- Endpoint `POST /activos-biologicos` con RBAC correcto (`require_permission(29,1)`, `infrastructure/routers/activo_biologico_router.py:187-191`), coincide con el RBAC real en `modulo1.permisos` (Administrador, Ingeniero de Campo, Productor, Veterinario).
- **Exclusividad `tipo_activo` reforzada con `model_validator` de Pydantic**: INDIVIDUAL exige `identificador`+`raza`+`sexo`+`fecha_nacimiento` y prohíbe `cantidad_inicial`; POBLACIONAL exige `cantidad_inicial>0` y prohíbe los campos individuales (`infrastructure/dto/registrar_activo_dto.py:32-62`).
- **Unicidad de identificador**: validada en el use case (case-insensitive, `registro/registrar_activo_use_case.py:99-104`) → 409, reforzada en DB con índice único parcial `uix_activo_indentficador_individual` (`WHERE tipo='INDIVIDUAL'`).
- Especie e infraestructura activas verificadas contra los adaptadores de M09 antes de persistir → 400.
- `fecha_inicio_ciclo` no futura / no anterior a 1970-01-01, validada en DTO **y** reforzada por dos CHECK en DB (`chk_activos_fecha_inicio_ciclo_no_futura`, `chk_activos_fecha_inicio_ciclo_valida`).
- **Reglas de `origen_financiero_activo` completas y correctas** (`registrar_activo_dto.py:75-100`): COMPRA/DONACION exigen `costo_adquisicion>0`+`soporte_documental`; NACIMIENTO exige ambos `None`; TRANSFERENCIA_INTERNA opcional — coincide exactamente con el RF.
- `atributos_dinamicos` validado contra la configuración real de la especie (RF-16), no contra el payload (`_validar_atributos_dinamicos()`, `registro/registrar_activo_use_case.py:21-54`).
- Estado inicial forzado a ACTIVO (`ActivoBiologico.crear()` + trigger `trg_activo_biologico_estado_inicial`), no configurable por el usuario.
- `cantidad_actual` inicializado = `cantidad_inicial` para POBLACIONAL; `cantidad_inicial`/`peso_promedio_inicial` inmutables vía `trg_fn_poblacional_cantidad_inmutable`.
- `costo_adquisicion` inmutable post-registro vía `trg_activo_biologico_inmutabilidad` (también protege `tipo`, `id_especie`, `origen_financiero`).
- La primera asociación con infraestructura (RF-34) se crea atómicamente en el mismo `INSERT` (`infrastructure/repositories/activo_biologico_repository.py:136-142`).
- Auditoría de éxito y fallo hacia la bitácora RF-52. Sin `id_rol` quemado.

### Qué NO cumple / gaps

- **No existe el mecanismo de "snapshot inicial / Evento 0" que el RF exige explícitamente.** No hay ninguna tabla `historial_activos` en `modulo2` — confirmado en vivo (`information_schema.tables` solo devuelve `historial_infraestructura_activo` y 4 vistas). El método `ActivoBiologico._snapshot()` existe (`activo_biologico.py:344-357`) pero **nunca se invoca** desde el registro del activo — solo lo usa `asociar_sensor_activo_use_case.py` para su propia auditoría. El criterio de aceptación "el sistema registra un snapshot inicial (Evento 0) en `historial_activos`... `version=1`, `tipo_evento=CREACION`" no se cumple.
- **No hay CHECK a nivel de DB para "`soporte_documental` obligatorio si `costo_adquisicion` no es nulo"** — solo se valida en el DTO. Confirmado con datos reales: el activo `BOV-003` tiene `origen_financiero='compra'`, `costo_adquisicion=8000000.0000` y `soporte_documental=NULL` en la base de datos dev.
- **Discrepancia de código HTTP en el flujo alterno #8**: el RF exige `422` para "costo de adquisición inválido para el origen", pero la validación vive en un `model_validator` de Pydantic, que al fallar produce `RequestValidationError` de FastAPI → **400** (confirmado en `src/shared/error_handlers.py:57-83`).
- Tiempo de respuesta ≤2s no verificable por lectura de código — no instrumentado, se marca como no verificado.

---

## RF-34 — Asociación del Activo Biológico a Infraestructura Productiva (solo lectura)

**Veredicto: ⚠️ Cumple parcialmente (~55%)**

### Qué SÍ cumple

- Es genuinamente de solo lectura: no existe ningún endpoint de escritura sobre `/{id}/infraestructura` en todo el router.
- Las dos vistas (`ACTIVA`/`HISTORIAL`) están implementadas vía `tipo_consulta` (default `ACTIVA`).
- Filtro `fecha_fin IS NULL` para la asociación activa, reforzado por índice único parcial en DB `uq_activo_asociacion_activa` — garantiza a nivel de base de datos que solo existe un registro activo por activo.
- Vista HISTORIAL ordenada cronológicamente (descendente; el RF no exige una dirección específica, solo orden cronológico).
- Activo inexistente → 404. RBAC correcto, sin `id_rol` quemado. Auditoría de cada consulta hacia RF-52.

### Qué NO cumple / gaps

- **Falta por completo el parámetro `fecha_referencia`** que el RF exige explícitamente ("útil para RF-61"). La firma del endpoint solo acepta `id_activo` y `tipo_consulta` — el criterio de aceptación "consulta por fecha de referencia" (CA-3) es inalcanzable con la API actual.
- **El flujo alterno E2 ("activo sin asociación activa" → 404 con alerta técnica) no está implementado.** Cuando no hay asociación activa, el use case retorna `None` y el router responde **HTTP 200** con `asociacion_activa=None`, no el 404 con mensaje de inconsistencia que exige CA-5.
- `sensores_en_infraestructura` (enriquecimiento vía RF-22, parte del contrato de salida "Vista 1" del RF) no existe en ningún lugar del código.
- `advertencia_integridad` no existe en ningún lugar (entidad, schema o repositorio) — no hay ninguna verificación de solapamiento de periodos a nivel de aplicación.
- Sin scoping de acceso "por granja y rol" — el RBAC es binario por recurso, cualquier usuario con permiso de lectura sobre el recurso 29 puede consultar la asociación de cualquier activo de cualquier finca.

---

## RF-35 — Gestión Individual de Activos Biológicos

**Veredicto: ⚠️ Cumple parcialmente (~55%)**

### Qué SÍ cumple

- `GET`/`PATCH /{id}` implementados, activo inexistente → 404.
- Valida que el activo sea tipo INDIVIDUAL antes de editar (`activo.actualizar_detalle_individual()`, `TIPO_INVALIDO` si no lo es).
- El campo `estado_activo` no es editable desde este endpoint — el DTO de actualización ni siquiera acepta ese campo, cumpliendo estructuralmente la restricción sin necesitar rechazo explícito.
- No se puede cambiar `tipo` ni `especie` tras el registro (doble capa: ausencia en el DTO + trigger `trg_activo_biologico_inmutabilidad`).
- Transacción con `commit()`/`rollback()` correctos, auditoría de éxito/fallo. RBAC vía router, sin `id_rol` quemado.

### Qué NO cumple / gaps

- **Discrepancia de RBAC confirmada: Veterinario, listado explícitamente como actor de RF-35, no tiene permiso de actualización.** Verificado en vivo contra `modulo1.permisos`: para la acción de `PATCH` (U=3) sobre el recurso 29, los roles son Administrador, Ingeniero de Campo y Productor — Veterinario está ausente.
- **No valida "eventos pendientes sin cerrar" ni "inconsistencias en el historial"** antes de aceptar una edición, pese a que el RF lo exige explícitamente en su Proceso.
- No hay ningún vínculo/atajo desde este RF hacia el registro de eventos asociados, ni hacia "transferir ubicación" — ambos listados como operaciones disponibles en el texto del RF, aunque viven correctamente en otros RFs (separación de responsabilidad razonable, pero sin ningún puente).
- Sin concurrencia optimista (ni 412 ni versión) en el `PATCH`, a diferencia del patrón documentado como estándar del proyecto en `CLAUDE.md`.

---

## RF-36 — Gestión Poblacional de Activos Biológicos

**Veredicto: ⚠️ Cumple parcialmente (~40%)** — el más bajo de las 20 RFs auditadas.

### Qué SÍ cumple

- Coherencia `cantidad_actual`/`biomasa_total`/`densidad` forzada tanto en el dominio (`aplicar_evento_baja()`/`aplicar_evento_crecimiento()`, `activo_biologico.py:399-422`) como en DB (`chk_poblacional_biomasa_coherente`, `chk_poblacional_cantidad_actual_coherente`, `chk_poblacional_cantidad_actual_no_negativa`, `chk_poblacional_cantidad_inicial_positiva`).
- Ningún DTO permite editar directamente `cantidad_actual`, `peso_promedio`, `biomasa_total` ni `densidad` — el único mecanismo de cambio son los eventos, tal como exige el RF.
- `cantidad_inicial`/`peso_promedio_inicial` inmutables vía trigger, satisfaciendo la referencia histórica permanente.
- Un lote no puede convertirse en INDIVIDUAL (tipo inmutable). El estado del lote no es editable desde ningún flujo de este RF, solo vía RF-44.

### Qué NO cumple / gaps

- **No existe un endpoint ni caso de uso propio de "gestión de lote"** con la ficha operativa completa que describe el RF (cantidad_actual + peso_promedio + biomasa_total + densidad + estado + historial en una sola vista). El único endpoint con RF-36 implícito, `GET /{id}/eventos`, **solo devuelve la lista de eventos**, no las métricas del lote — para verlas hay que usar `GET /{id}` (pensado para individuales) o la ficha integral (RF-47). El RF describe una "ficha del lote" propia que no existe como endpoint dedicado.
- **No se valida `densidad_maxima_por_especie` en absoluto** — grep exhaustivo sin coincidencias. El flujo alterno #4 del RF ("409 — densidad supera el máximo permitido") no está implementado; el sistema calcula la densidad pero nunca la contrasta contra ningún límite.
- No hay ningún mecanismo de "ingreso"/alta de individuos al lote — solo existe el flujo de BAJA. La restricción "`cantidad_actual` no puede ser mayor a `cantidad_inicial` + ingresos" es hoy trivialmente cierta porque el mecanismo de ingreso simplemente no existe, no porque esté validado.
- No hay ninguna validación cruzada que fuerce o recuerde que un evento sanitario con `cantidad_afectada` por muertes debe ir acompañado de un evento de tipo BAJA independiente, tal como exige el RF — queda a discreción manual del usuario.
- Reglas de validación agregada por especie más allá del rango de medición puntual (ej. rango de peso promedio del lote, tipos de evento permitidos por especie) no están implementadas a nivel de lote.

---

## RF-37 — Gestión de Fases del Ciclo Productivo

**Veredicto: ⚠️ Cumple parcialmente (~55%)**

### Qué SÍ cumple

- Fase única activa por activo: índice único parcial `uix_gestion_fase_activa_por_activo` + trigger `trg_fn_fase_unica_activa`.
- No permite cambio de fase en CERRADO/BAJA (`trg_fn_fase_activo_estado_valido`).
- No solapamiento de fases (`trg_fn_fase_solapamiento`).
- Transacción atómica: cierra la fase activa y crea la nueva antes de un único `commit()`.
- RBAC en el router, sin `id_rol` quemado.

### Qué NO cumple / gaps

- **El modelo de "fase destino + confirmación de transición no estándar" del RF no está implementado.** El DTO real (`cambiar_fase_dto.py`) solo tiene `id_ciclo_productiva`, `motivo_cambio` y `fecha_inicio` — no existe `fase_destino_id` ni `confirmacion_no_estandar`. El use case siempre avanza automáticamente a la siguiente fase de la secuencia. **Consecuencia: el flujo alterno "transición no estándar sin confirmación" (409) es inalcanzable** — nunca se puede solicitar una transición fuera de secuencia, ni saltando pasos hacia adelante ni retrocediendo.
- No se valida que la fecha no sea futura — ni el DTO ni ningún trigger de `gestiones_fases` lo comprueban.
- Sin inmutabilidad reforzada por trigger de DB para el historial de fases, a diferencia de `historicos_estados_activos` y las tablas de eventos.
- RBAC más amplio que los actores del RF: el permiso de ejecutar cambio de fase también está concedido a Ingeniero de Campo, pese a que el RF solo lista Productor/Veterinario/Administrador.

---

## RF-38 — Cierre del Ciclo Productivo

**Veredicto: ⚠️ Cumple parcialmente (~85%)**

### Qué SÍ cumple

- Estado ya CERRADO/BAJA → 409. `motivo_cierre` obligatorio y `fecha_cierre` no futura → 400.
- Fecha de cierre anterior al último evento → 400. Sin fase activa → 422, mensaje casi textual al del RF.
- Valida adicionalmente (no pedido explícitamente pero razonable) que no tenga sensores IoT activos antes de cerrar.
- Cierre de fase + cambio de estado en una sola transacción.
- **RBAC coincide exactamente con los actores del RF** — de los pocos endpoints del módulo donde el recorte de roles en `modulo1.permisos` coincide con el texto del RF (Ingeniero de Campo excluido a propósito, documentado por el propio dev).

### Qué NO cumple / gaps

- **No "invoca" un proceso compartido de RF-44** — duplica el patrón `activo.cambiar_estado()` + `historico_repo.registrar()` en vez de llamar a un componente único de cambio de estado (ver detalle en RF-44).
- **`modulo_origen` se graba como `'modulo2'`, nunca `'RF-38'`** como exige textualmente el RF — confirmado en vivo (`historicos_estados_activos.modulo_origen` solo tiene los valores `modulo2`/`modulo5` en toda la tabla). Decisión forzada por el CHECK `chk_historico_modulo_origen_valido`, que solo permite literales `'modulo1'..'modulo9'`.
- Bitácora RF-52 sin ninguna fila con `rf_origen='RF38'`, pese a que sí existen cierres reales en `historicos_estados_activos`/`gestiones_fases`.

---

## RF-39 — Registro de Eventos Biológicos del Activo (base)

**Veredicto: ⚠️ Cumple parcialmente (~80%)**

### Qué SÍ cumple

- Gate de estados centralizado (`_event_validations.py:validar_estado_permite_eventos`): bloquea CERRADO/BAJA, permite ACTIVO/EN_TRATAMIENTO/AISLADO — reforzado en DB por `trg_fn_evento_activo_estado_valido` (código fuente verificado, misma regla).
- Fecha no futura / no anterior al registro del activo, reforzado también por trigger (`trg_evento_fecha_coherente`).
- Inmutabilidad real: `trg_fn_eventos_activos_inmutable` bloquea UPDATE/DELETE en las 5 tablas hijas de eventos y en la tabla padre `eventos_activos` (confirmado, 21 triggers listados en `pg_trigger`).
- RBAC correcto y uniforme en los 5 endpoints POST de eventos, sin `id_rol` quemado.

### Qué NO cumple / gaps

- **El gate de estados es inconsistente entre tipos de evento.** El RF exige que ACTIVO/EN_TRATAMIENTO/AISLADO permitan **todos** los tipos de evento. Pero los use cases de crecimiento (RF-40) y productivo (RF-43) no usan el gate compartido — tienen su propio chequeo que exige **solo ACTIVO**, rechazando EN_TRATAMIENTO/AISLADO. Esto coincide con la letra de las precondiciones específicas de esos dos RFs, pero contradice el criterio de aceptación general de RF-39 — es una contradicción real entre fichas de RF que el código resuelve de forma no uniforme.
- **Fallo sistémico de traducción de errores de DB, transversal a este grupo de RFs (ver Hallazgos transversales #4).** Los triggers de este módulo lanzan excepciones con `ERRCODE` propios (`P0214`..`P0223`), pero `raise_from_db_error` solo traduce `IntegrityError`/`DataError`/`OperationalError` — cualquier violación que solo el trigger detecte (no anticipada por el use case) cae en el catch-all final → **HTTP 500**, no el 400/409/422 documentado por cada RF. Confirmado 100% reproducible en RF-40 y RF-42 (ver abajo).

---

## RF-40 — Registro de Eventos de Crecimiento

**Veredicto: ⚠️ Cumple parcialmente (~75%)**

### Qué SÍ cumple

- `tipo_medicion` limitado a PESO/TALLA/BIOMASA, `valor_medicion>0`, coherencia unidad↔tipo vía `model_validator`.
- `tipo_agregacion` prohibido para INDIVIDUAL y obligatorio para POBLACIONAL, junto con `nuevo_peso_promedio`/`cantidad_medida`.
- Exige fase productiva activa antes de aceptar el evento. Rango min/max configurado por especie (columnas `valor_min`/`valor_max` en `modulo9.metricas_produccion`).
- Recalcula correctamente `biomasa_total`/`densidad` para POBLACIONAL. Avance automático de fase por duración configurada, con fallback silencioso si falla (no bloquea el evento).

### Qué NO cumple / gaps

- **Bug confirmado y 100% reproducible: inconsistencia de unidades entre el DTO y el trigger de DB.** El DTO acepta `'gr'` como unidad válida para PESO, pero el trigger `trg_fn_evento_crecimiento_tipo_activo` (código fuente verificado) solo acepta `('kg','g','lb')` — **`'g'`, no `'gr'`**. Un request con `tipo_medicion=PESO, unidad_medida=gr`, válido según el propio contrato del sistema, pasa Pydantic y el use case, y el trigger lo rechaza en el INSERT. Por el gap de traducción de errores de RF-39, esto se convierte en **HTTP 500** en vez de un 400 claro.
- El trigger de DB no valida ninguna unidad para `tipo_medicion='BIOMASA'` — la segunda capa de defensa está incompleta para ese caso.
- Bug de mayúsculas en el propio trigger: compara `tipo_activo = 'poblacional'` (minúscula) contra un enum cuyos valores reales son `'POBLACIONAL'`/`'INDIVIDUAL'` — esa rama del trigger nunca se ejecuta (no visible al usuario porque Python ya valida correctamente antes).
- El campo `frecuencia` (Diaria/Semanal/Quincenal/Mensual, pedido en las Entradas del RF) es texto libre sin validar contra esos 4 valores. El campo `metodo_medicion` (paso 4 del Proceso del RF) no existe en el DTO ni se persiste.

---

## RF-41 — Registro de Eventos Sanitarios

**Veredicto: ✅ Cumple (~90%)**

### Qué SÍ cumple

- Campos obligatorios por tipo exactamente según la tabla de Restricciones del RF, validados en el DTO **y** reforzados por 4 CHECK constraints nombrados en DB (`check_vacunacion`, `check_tratamiento`, `check_diagnostico`, `check_control`).
- Secuencia lógica (no TRATAMIENTO/VACUNACION sin DIAGNOSTICO previo) implementada consultando directamente `tipo='DIAGNOSTICO'` en el repositorio.
- `solicitar_estado` (EN_TRATAMIENTO/AISLADO) restringido a TRATAMIENTO/CONTROL_PREVENTIVO en el DTO, y el cambio de estado pasa por `activo.cambiar_estado()` + registro en histórico — respeta la centralización de RF-44, no escribe el estado directamente.
- Gate de estado correcto (ACTIVO/EN_TRATAMIENTO/AISLADO), coherente con la justificación explícita del propio RF-41.

### Qué NO cumple / gaps

- El trigger `trg_fn_evento_sanitario_secuencia` implementa la misma regla de secuencia con lógica distinta y más frágil (infiere "diagnóstico previo" por proxy — presencia/ausencia de `medicamento`/`dosis` — en vez de por `tipo`). Funciona igual en el camino feliz, pero un evento DIAGNOSTICO con medicamento/dosis opcionales podría disparar la regla incorrectamente, y si lo hace, cae en el mismo problema de traducción a HTTP 500 de RF-39.

---

## RF-42 — Registro de Eventos Reproductivos

**Veredicto: ⚠️ Cumple parcialmente (~65%)**

### Qué SÍ cumple

- Secuencia lógica (diagnóstico requiere servicio/inseminación previa; parto/aborto requieren diagnóstico positivo previo; nacimiento requiere ambos) implementada correctamente para activos INDIVIDUAL.
- `id_padre` obligatorio y validado como activo para servicio/inseminación. `numero_crias >= 1` para parto/aborto/nacimiento, con CHECK a nivel de columna.
- El gap de BD original (`id_padre` era NOT NULL, bloqueando diagnóstico/parto/aborto) fue corregido a nullable — confirmado en vivo.

### Qué NO cumple / gaps

- **Bug confirmado: la restricción "LOTE solo puede registrar NACIMIENTO" nunca se aplica, porque compara contra un valor que no existe.** `registrar_evento_reproductivo_use_case.py:56` hace `if activo.tipo == 'LOTE' and dto.categoria != 'nacimiento':` — pero `TipoActivo` (`domain/value_objects/tipo_activo.py`, verificado directamente: solo define `INDIVIDUAL` y `POBLACIONAL`) **nunca vale `'LOTE'`**. La condición es código muerto (siempre `False`): un activo POBLACIONAL puede hoy registrar `servicio`, `inseminacion`, `diagnostico`, `parto` o `aborto` sin que el use case lo impida, violando directamente la restricción del RF.
- La regla sí está bien implementada en el trigger de DB (`trg_fn_evento_reproductivo_secuencia`, verificado: compara correctamente contra `'POBLACIONAL'`), así que nada se persiste incorrectamente — pero por el gap de traducción de RF-39, cuando el trigger efectivamente bloquea, el cliente recibe **HTTP 500** en vez del `422` con el mensaje documentado por el propio RF. La regla de negocio se cumple; el contrato de error HTTP no.
- Discrepancia entre 3 fuentes para la regla de "nacimiento": el RF y el use case exigen servicio/inseminación + diagnóstico exitoso previos, pero el trigger de DB exige en cambio un evento previo de `parto` — una tercera regla no descrita en ningún RF. No se manifiesta en el camino feliz porque el use case bloquea primero según su propia regla.

---

## RF-43 — Registro de Eventos Productivos

**Veredicto: ✅ Cumple (~95%)** — el más riguroso de las 20 RFs auditadas.

### Qué SÍ cumple

- Cubre los 9 flujos alternos del RF (E-01 a E-09) con código de error y texto casi idénticos al documento: estado≠ACTIVO, catálogo RF-16, unidad según RF-16, fase activa existente, producto habilitado en el ciclo activo, fecha no futura, fecha no anterior al inicio del activo, fecha dentro del rango de la fase activa, duplicidad tipo+activo+fecha (reforzada además por trigger `trg_fn_evento_productivo_duplicado`, verificado con la misma regla).
- `cantidad_producida > 0` validado en el DTO. Es el caso con mejor trazabilidad 1:1 RF↔código de todo el módulo.

### Qué NO cumple / gaps

- No reutiliza las validaciones compartidas de fecha/estado del resto del módulo — reimplementa su propia lógica (correcta, pero duplicada).
- No se pudo confirmar si el trigger de duplicidad sufre el mismo problema de traducción a 500 bajo condiciones de carrera concurrente real; en el camino secuencial normal el use case lo detecta primero con 409 limpio.

---

## RF-44 — Gestión del Estado del Activo Biológico

**Veredicto: ⚠️ Cumple parcialmente (~65%)** — el motor de reglas de transición es sólido y está reforzado en dos capas independientes, pero el "punto de control centralizado" que el RF exige explícitamente tiene una grieta real y verificada.

### Qué SÍ cumple

- **Matriz de transiciones exacta al RF, en dos capas independientes**: Python (`estado_activo.py:TRANSICIONES_VALIDAS`) y trigger SQL `trg_fn_estado_activo_transicion_valida` (código fuente verificado, coincide literalmente).
- BAJA irreversible y cambio redundante rechazados en ambas capas. `trg_estado_activo_no_baja_modify` bloquea **cualquier** UPDATE sobre la fila del activo si el último estado es BAJA.
- **Bloqueo real de escritura directa del campo de estado**: trigger `trg_activo_biologico_bloquear_cambio_estado_directo` (BEFORE UPDATE OF `id_estado`) — confirmado en vivo, cualquier UPDATE directo del campo fuera del flujo de `historicos_estados_activos` es rechazado por la DB.
- Sincronización automática vía `trg_fn_sincronizar_estado_activo`. `motivo_cambio` obligatorio. Único estado vigente reforzado por `trg_fn_estado_activo_unico_vigente`.

### Qué NO cumple / gaps

- **El contrato de `modulo_origen` (MANUAL/RF-38/RF-45) no se cumple en absoluto.** Confirmado con datos reales: `SELECT modulo_origen, count(*) FROM historicos_estados_activos GROUP BY 1` devuelve únicamente `{modulo2: 25, modulo5: 2}` — ni un solo valor distinto en toda la tabla. Es imposible, mirando esta tabla, saber si un cambio de estado fue manual, por cierre de ciclo o por baja. Causa raíz: el CHECK `chk_historico_modulo_origen_valido` solo acepta literales `'modulo1'..'modulo9'`, no strings como `'RF-38'`.
- **RF-38 y RF-45 no invocan un proceso compartido de RF-44** — cada uno (y también RF-41 para sus cambios sanitarios) reimplementa por su cuenta `activo.cambiar_estado()` + registro en histórico. El resultado final es idéntico porque comparten entidad y repositorio, pero no hay una "invocación" real de un componente único — es la misma regla copiada en varios lugares.
- **Gap más serio del módulo, verificado directamente: `PATCH /{id}/estado` permite fijar `CERRADO` o `BAJA` sin las reglas ni efectos secundarios propios de RF-38/RF-45.** `CambiarEstadoDTO._ESTADOS_VALIDOS` (verificado: `{ACTIVO, INACTIVO, EN_TRATAMIENTO, AISLADO, CERRADO, BAJA}`) incluye ambos sin restricción, y `CambiarEstadoUseCase` no los excluye. Si se usa para llegar a CERRADO por esta vía: no valida fase activa ni sensores IoT activos, y **no cierra la fase productiva activa** (solo `CerrarCicloUseCase`/`RegistrarEventoBajaUseCase` llaman `cerrar_gestion_activa()`) — el activo quedaría en CERRADO con una fase huérfana `es_activa=true` permanentemente. Si se usa para llegar a BAJA en un lote: no se crea fila en `eventos_bajas`, no se descuenta `cantidad_actual` ni se recalculan `biomasa_total`/`densidad` (esa lógica vive solo en `RegistrarEventoBajaUseCase`). El lote quedaría "dado de baja" con la cantidad de individuos intacta. Esto contradice directamente el "Principio de Centralización Obligatoria" que el propio RF-44 declara como su razón de ser.
- RBAC más amplio que los actores del RF: `PATCH /estado` también está concedido a Ingeniero de Campo, mientras RF-44 lista los actores de "cambio manual" como solo Productor/Administrador/Veterinario.
- Bitácora RF-52 sin ninguna fila con `rf_origen='RF44'`.

---

## RF-45 — Registro de Bajas del Activo Biológico

**Veredicto: ⚠️ Cumple parcialmente (~85%)**

### Qué SÍ cumple

- Activo inexistente → 404. Activo ya en BAJA → 409, mensaje casi idéntico al del RF.
- Fecha futura → 400; fecha anterior al último evento → 400.
- **Cantidad de baja superior a existencia (lotes) → 422, reforzado además por trigger de DB `trg_fn_baja_cantidad_valida`** (verificado: `cantidad_afectada > 0` y `<= cantidad_actual`) — doble capa real.
- `tipo_baja`/`motivo_baja` obligatorios. Baja total: cambia a BAJA y cierra la fase activa. Baja parcial en lote: descuenta `cantidad_actual` sin permitir negativos.
- Irreversibilidad reforzada también por trigger. RBAC en router sin `id_rol` quemado.

### Qué NO cumple / gaps

- **Cálculo de `cantidad_actual`/`biomasa_total`/`densidad` duplicado en dos capas que no se comunican entre sí**: el use case lo recalcula en Python antes del INSERT, y el trigger `trg_fn_baja_actualizar_cantidad_lote` (AFTER INSERT) lo vuelve a calcular de forma independiente leyendo la fila en ese momento. Hoy probablemente coinciden, pero es lógica de negocio duplicada sin una única fuente de verdad.
- **RBAC más amplio que los actores del RF, con la misma causa raíz que RF-37/RF-44**: `POST /eventos/baja` exige el mismo par (recurso 29, acción C) que RF-43 (eventos productivos, donde sí aplican los 4 roles), concedido también a Ingeniero de Campo — pero RF-45 lista actores como solo Productor/Administrador/Veterinario. El propio doc `cu09_gaps_bd_rf43_rf45.md` revisó el RBAC de este caso de uso y concluyó "sin gaps de RBAC" sin notar esta discrepancia, precisamente porque el mismo par recurso+acción sirve a dos RFs con listas de actores distintas.
- `modulo_origen` también fijo en `'modulo2'` — mismo gap transversal de RF-44. Bitácora RF-52 sin ninguna fila con `rf_origen='RF45'`, pese a existir 2 eventos de baja reales.

---

## RF-46 — Consulta de Historial del Activo Biológico

**Veredicto: ⚠️ Cumple parcialmente (~85%)**

### Qué SÍ cumple

- Solo lectura confirmado — ninguna operación de escritura en el use case.
- Consolida 8 de las 9 categorías del RF vía la vista `vw_rf46_historial_completo_activo` (ESTADO, FASE_PRODUCTIVA, SANITARIO, CRECIMIENTO, PRODUCTIVO, REPRODUCTIVO) más BAJA y TRANSFERENCIA añadidas por queries separadas. La categoría "EVENTO_BIOLOGICO" no existe como bucket propio, pero no es un hueco real de datos: todo evento en `eventos_activos` siempre tiene un subtipo concreto, no hay "evento biológico puro" sin categoría.
- Orden cronológico ascendente por defecto. Filtros por fecha y categoría validados, incluyendo rechazo de `fecha_inicio > fecha_fin` (400).
- **Paginación siempre aplicada** (1-100, default 20) — cumple "paginación obligatoria para >500 registros" de forma más estricta que lo pedido. Auditoría de cada consulta. Activo inexistente → 404.

### Qué NO cumple / gaps

- **Sin control de acceso por granja/rol que exige la Restricción 3 del RF** ("consulta limitada por permisos del rol... no debe exponer registros de categorías no autorizadas"). El router solo aplica RBAC genérico por recurso; no hay ninguna comprobación de finca/ownership — cualquier usuario con permiso de lectura puede consultar el historial de cualquier activo, sin importar granja.
- La categoría "EVENTO_BIOLOGICO", listada como válida en el DTO, no tiene mapeo en el repositorio — si un cliente filtra explícitamente por ella, devuelve 0 resultados silenciosamente en vez de un error de contrato claro.
- `modulo_origen` se hardcodea como `'modulo2'` genérico en casi todos los registros del historial, en vez de indicar el RF específico de origen como sugiere el ejemplo de salida del propio RF.
- La consulta vive dentro de `SqlAlchemyTransferenciaRepository`, no en un repositorio dedicado — inconsistencia de nomenclatura respecto a la convención de "un repositorio por agregado" de `CLAUDE.md`, no un incumplimiento funcional.

---

## RF-47 — Ficha Integral del Activo Biológico

**Veredicto: ⚠️ Cumple parcialmente (~65%)**

### Qué SÍ cumple

- Solo lectura, sin edición de campos. Consolida datos base + estado/fase + ubicación + datos biológicos vía la vista `vw_rf47_ficha_integral_activo` (Secciones 1-4, 7).
- Sección 5 (últimos 5 eventos por categoría) implementada con `LIMIT 5` explícito para sanitarios, productivos, crecimiento y reproductivos, cada uno contra su propia vista.
- Sección 6 (indicadores) implementada vía vista dedicada.
- **Detección de inconsistencia estado/fase implementada explícitamente**: si el estado actual es CERRADO/BAJA y la fase productiva sigue activa, añade advertencia en lenguaje natural sin bloquear la respuesta — coincide con la Regla de Inconsistencia Detectada del RF.
- Auditoría de cada consulta, envuelta en manejo de excepción para no bloquear el flujo si falla.

### Qué NO cumple / gaps

- **No existe la Sección 8 (Accesos directos) en absoluto** — ni la entidad `FichaIntegral` ni el schema de respuesta tienen campo alguno de enlaces/acciones disponibles. El RF la exige explícitamente como sección obligatoria (historial, registrar evento, cambiar estado, registrar baja), filtrada por permisos del usuario. Gap real, no cosmético.
- **`densidad` está hardcodeada a `None` sin importar el tipo de activo** — nunca se calcula, pese a que el RF exige densidad calculada para la Sección 7 (solo-LOTE).
- **Sin manejo granular de fallo parcial por sección.** El código solo tiene un fallback de toda la ficha completa si la vista principal no devuelve fila; si falla una sub-consulta individual de eventos, no hay try/except por sección — la excepción se propagaría y tumbaría toda la ficha, violando el requisito explícito de que "las demás secciones se cargan normalmente".
- Sin filtrado de secciones/accesos por rol, pese a que el RF lo exige como restricción explícita.

---

## RF-48 — Transferencia Interna de Activos Biológicos

**Veredicto: ⚠️ Cumple parcialmente (~85%)**

### Qué SÍ cumple

- **Control de concurrencia real, no aspiracional**: usa `SELECT ... FOR UPDATE NOWAIT` — un lock genuino de Postgres; si otra transacción ya bloqueó la fila, se rechaza con 409 `TRANSFERENCIA_CONCURRENTE`.
- Todos los flujos alternos de activo/infraestructura inválidos implementados con los códigos documentados.
- **Regla C1 (especie) y C3 (capacidad, con cálculo correcto de cantidad para LOTE vs INDIVIDUAL) implementadas.**
- Fecha futura rechazada en el DTO. Transacción atómica real (cierra/abre asociación en `historial_infraestructura_activo` + actualiza infraestructura del activo + registra `Movimiento`, todo en un único bloque commit/rollback). Auditoría en éxito y en fallo.
- LOTE se transfiere completo por diseño estructural (el DTO no acepta cantidad parcial).
- **Corrección a las notas del propio desarrollador**: el doc de curls afirma "solo admin y productor" pueden transferir, pero verificado en vivo contra `modulo1.permisos`, los 4 roles tienen el permiso. El use case no tiene ningún `id_rol` quemado — el gap es de documentación desactualizada, no de código.

### Qué NO cumple / gaps

- **Regla C2 (compatibilidad de tipo de infraestructura) no está implementada.** El RF exige que el tipo de infraestructura destino sea adecuado para el tipo de activo, como regla obligatoria simultánea a C1 y C3. El campo `tipo` de la infraestructura está disponible en el adaptador pero **nunca se usa** para esta validación — una transferencia de un activo avícola a un estanque, por ejemplo, no sería rechazada por tipo.
- El error de fecha futura, al venir de un `@field_validator` de Pydantic, se traduce a HTTP 400 con formato `{error_code, fields[]}`, no al `422` con formato `{code, message, field}` que documenta el propio doc de curls del módulo ni el formato estándar de error de dominio de `CLAUDE.md` — patrón sistémico, no exclusivo de este RF (ver Hallazgos transversales #3).

---

## RF-49 — Asociación de Activos Biológicos con Sensores IoT

**Veredicto: ⚠️ Cumple parcialmente (~65%)**

### Qué SÍ cumple

- Las 6 validaciones de precondición (existencia de activo/sensor, activo no en BAJA, sensor y dispositivo activos, sensor con área asociada, coherencia de finca) implementadas en orden.
- **Cardinalidad DIRECTA correcta**: un sensor con asociación DIRECTA activa no puede vincularse a otro activo sin liberarlo primero; un mismo activo individual puede tener varios sensores.
- **Cardinalidad POBLACIONAL correcta**: un lote no puede tener dos sensores POBLACIONAL activos simultáneos. AMBIENTAL correctamente sin restricción de exclusividad.
- **Auto-supersede real y funcional**: si ya existe una asociación ACTIVA para el mismo par sensor+activo, se marca SUPERADA con snapshot de auditoría antes de crear la nueva.
- **Corrección importante a un hallazgo de la exploración inicial: la tabla de auditoría dedicada `auditorias_asociaciones_sensor_activo` sí se escribe desde código real** (`SqlAlchemyAsociacionSensorActivoRepository.registrar_auditoria`, INSERT real en la misma transacción). Sus 0 filas en dev no son un bug — las 4 asociaciones existentes en `asociaciones_activos_sensores` tienen fechas de 2024, es decir, fueron sembradas directamente por SQL, no creadas vía este endpoint; el código simplemente no se ha ejercitado todavía en este entorno.
- El `fk_usuario` duplicado y mal nombrado en `asociaciones_activos_sensores` (apunta otra vez a `id_activo_biologico`) es basura de migración inofensiva — el FK real hacia `usuarios` existe correctamente bajo otro nombre autogenerado.

### Qué NO cumple / gaps

- **No existe validación de compatibilidad de especie** (Restricción 3 del RF: "el sensor debe ser compatible con la especie del activo según el catálogo I3P-1"). Grep exhaustivo confirma cero referencias a "especie" en todo el flujo de asociación — solo se valida coherencia de finca. Un sensor parametrizado para aves podría asociarse hoy a un activo bovino sin rechazo.
- **Ciclo de vida incompleto: solo existe `POST /{id}/sensores`.** No hay ningún endpoint para desactivar manualmente una asociación, reactivarla, ni siquiera para listar/consultar las asociaciones activas de un activo. El RF exige explícitamente "gestionar el ciclo de vida completo: creación, modificación, desactivación e historial inmutable" — hoy solo la creación (y el auto-supersede indirecto) están cubiertas.
- Coherente con lo anterior: el RBAC del recurso dedicado solo tiene permisos C y R sembrados, ni siquiera está previsto en el modelo de permisos actual.
- No hay verificación de "dispositivo IoT fuera de línea" (heartbeat) que describe el flujo alterno del RF — solo se valida el estado booleano del dispositivo.

---

## RF-50 — Disponibilidad de Datos para Módulos Analíticos

**Veredicto: ⚠️ Cumple parcialmente (~55%)**

### Qué SÍ cumple

- Endpoint `GET /{id}/datos-consolidados` con RBAC y sesión, expone en JSON estructurado los 4 conjuntos mínimos de datos que pide el RF (base del activo, eventos, fases, estado, métricas), filtrables por `tipo_dato`.
- Rango de fechas inválido → 400. Activo inexistente → 404. Paginación obligatoria (`page_size` acotado 1-100).
- Auditoría de cada acceso hacia RF-52 — confirmado en vivo (2 filas `RF50/DATOS_ANALITICOS_CONSULTADOS`). Sin `id_rol` quemado.

### Qué NO cumple / gaps

- **No es una "interfaz de servicio interno" real con control por módulo, es un endpoint humano reutilizado.** El RF describe un mecanismo M2M con "scopes" por módulo consumidor y exige registrar el "módulo solicitante". El campo `modulo_consumidor` en `EventoAuditoria` tiene default `'modulo2'` y **ningún use case lo sobre-escribe nunca** (grep sin resultados) — el campo existe pero siempre queda con el valor por defecto, inútil para identificar qué módulo externo consultó.
- **No hay rate limiting.** El RF exige "límite de solicitudes por módulo" y el error 429; la clase `TooManyRequestsError` existe en `src/shared/errors.py` pero **no se usa en ningún punto de `src/biological_assets/`**.
- **No hay validación de integridad referencial/completitud mínima antes de exponer datos** — el sistema devuelve lo que encuentra sin ninguna de las comprobaciones 409/422/500 que describen los flujos alternos del RF; si no hay eventos de peso, el campo simplemente sale `null`.
- No hay diferenciación de consistencia fuerte (para M06) vs. eventual (para M08) — todo es una lectura síncrona simple.
- **La escritura de auditoría es best-effort silenciosa** (`try/except Exception: pass`), decisión documentada conscientemente por el propio dev para no bloquear el flujo principal, pero contradice el criterio de RF-52 de que todo evento debe registrarse "sin excepción" (ver Hallazgos transversales #6).

---

## RF-51 — Generación de Indicadores Zootécnicos

**Veredicto: ⚠️ Cumple parcialmente (~60%)**

### Qué SÍ cumple

- Endpoint `GET /{id}/indicadores` con RBAC. **4 de los 5 indicadores mínimos del RF están realmente calculados con datos reales**, no simulados: `ganancia_peso`, `produccion_promedio`, `tasa_morbilidad`, `tasa_mortalidad` — fórmulas coincidentes con el texto del RF, verificadas con datos reales en `modulo2.indicadores_zootecnicos` (14 filas, aritmética coherente).
- Cálculo on-demand (satisface la disyunción "on-demand O batch" del RF). Soporta individual y lote. Filtro por rango de fechas validado. Resultado incluye variables usadas y fecha de cálculo. Auditoría de cada consulta. Activo inexistente → 404. Sin `id_rol` quemado.

### Qué NO cumple / gaps

- **El 5º indicador mínimo, `conversion_alimenticia`, NO se calcula.** Siempre retorna `disponible=False` con advertencia "REQUIERE_M05: aún no está implementado" — dependencia real y honestamente documentada de un módulo (M05) no implementado. Uno de los 5 indicadores obligatorios del RF simplemente no existe en la práctica.
- **"Datos insuficientes" no retorna HTTP 422 como pide el flujo alterno del RF** — cuando hay menos de 2 mediciones de peso, el sistema retorna HTTP 200 con `disponible=false` y una advertencia de texto, no un rechazo formal de la petición.
- **"Incompatibilidad biológica del indicador" (RF: HTTP 400) tampoco se implementa como error** — cuando el tipo de activo no aplica (ej. tasa de morbilidad en un individual), retorna 200 con advertencia, no 400.
- **"Rango de fechas fuera del ciclo biológico del activo" (RF: HTTP 400) no se valida en absoluto** — solo se valida el formato del rango (inicio≤fin), nunca se contrasta contra la fecha de registro/nacimiento o baja del activo.
- `indicadores_zootecnicos` no tiene modelo ORM propio — todo el acceso es SQL crudo, inconsistente con el resto del módulo.

---

## RF-52 — Auditoría y Trazabilidad de Eventos de Transformación Biológica

**Veredicto: ⚠️ Cumple parcialmente (~50%)** — el mecanismo central (bitácora + hash + clasificación + emisión desde ~18 use cases) existe y es real, pero el requisito más crítico del RF — inmutabilidad garantizada a nivel de base de datos — no está implementado, y varias piezas de "cadena de custodia" son placeholders sin cablear.

### Qué SÍ cumple

- Mecanismo real y centralizado: entidad `EventoAuditoria`, puerto y repositorio dedicados, tabla `bitacora_auditoria_m02` con 6 índices.
- **Emisión real desde 18 archivos de use case, 30 puntos de emisión**, cubriendo tanto camino exitoso como fallido en la mayoría.
- **Hash de integridad SHA-256 real, calculado en Python antes de persistir**, sobre un payload determinístico de 9 campos, serializado con `sort_keys=True` — reproducible, y se expone en el schema de respuesta.
- Endpoint de consulta con filtros completos (`rf_origen`, `tipo_evento`, `activo`, `clasificacion_biologica`, `resultado`, `severidad_log`, fechas), paginación, RBAC vía recurso dedicado — confirmado en vivo que el acceso de lectura coincide con los roles de consulta que describe el RF (Admin/Contador/Veterinario/Productor, Ingeniero de Campo excluido).
- Asíncrono respecto al flujo principal, sin bloquear operaciones — decisión de diseño documentada explícitamente por el dev. Sin `id_rol` quemado.

### Qué NO cumple / gaps

- **🔴 Gap más grave del módulo: la bitácora NO es append-only a nivel de base de datos.** Verificado en vivo: `SELECT tgname FROM pg_trigger WHERE tgrelid = 'modulo2.bitacora_auditoria_m02'::regclass AND NOT tgisinternal` → **cero triggers**. A diferencia de `eventos_activos`, `historicos_estados_activos` y `auditoria_activos_biologicos`, que sí tienen triggers `trg_fn_*_inmutable` con `RAISE EXCEPTION`, esta tabla no tiene ninguna protección. Esto contradice directamente la Restricción #1 del RF ("esta restricción debe estar implementada a nivel de base de datos, no solo a nivel de lógica de negocio") y su CA-3. Hoy, cualquiera con acceso de escritura a la tabla puede modificar o borrar registros de auditoría sin ningún rastro.
- **`clasificacion_biologica` no se asigna automáticamente** como exige el RF ("mediante tabla de clasificación configurada en M09") — se pasa manualmente y hardcodeada desde cada uno de los 18 use cases (30 literales string repartidos), con riesgo real de inconsistencia entre desarrolladores/casos de uso.
- **El `hash_integridad` nunca se verifica/recalcula** — solo se calcula una vez al insertar. No existe ningún endpoint ni lógica que, al consultar un registro, recalcule el hash y lo compare contra el almacenado. La "verificabilidad" que exige el RF (CA-11) es una capacidad latente, no una función implementada.
- **`id_evento_correlacionado` nunca se establece** — ni siquiera en `asociar_sensor_activo_use_case.py` (RF-49), el caso explícito que el RF pide correlacionar con la bitácora de M03. CA-9 no se cumple.
- **Las 6 vistas SQL auxiliares de indicadores de actividad (`vw_rf52_*`) están completamente sin usar** — existen en la DB pero ningún archivo de `src/` las referencia. La sección "Indicadores de Actividad" de la Salida del RF (consumida por M08) no está expuesta por ningún endpoint, pese a que la infraestructura de datos ya existe.
- No hay retención diferenciada (5 años transformación biológica/sanitario, 2 años resto) ni archivado — sin ninguna evidencia en el código.
- **El registro de auditoría es best-effort, no "sin excepción" como exige el RF** (`except Exception: pass`, decisión intencional documentada por el dev) — si el INSERT a la bitácora falla, el evento se pierde silenciosamente y nadie se entera; no hay buffer, cola ni reintento como describe la Fase 4 del Proceso del RF.

---

## Hallazgos transversales (afectan a varios RFs)

1. **RF-44, el "punto de control centralizado" de estado, tiene un segundo camino que se lo salta.** `PATCH /{id}/estado` permite llevar un activo a CERRADO o BAJA sin las validaciones ni efectos secundarios (cierre de fase, descuento de cantidad de lote) que sí aplican `CerrarCicloUseCase` (RF-38) y `RegistrarEventoBajaUseCase` (RF-45). *(Afecta RF-38, RF-44, RF-45.)*

2. **El campo `modulo_origen` de `historicos_estados_activos` no distingue nada.** Todos los cambios de estado quedan grabados como `'modulo2'` (o `'modulo5'` en 2 casos), nunca `'MANUAL'`/`'RF-38'`/`'RF-45'` como exige textualmente RF-44 — imposible reconstruir el origen real de un cambio de estado desde esta tabla. Causa raíz: el CHECK `chk_historico_modulo_origen_valido` solo acepta literales `'modulo1'..'modulo9'`. *(Afecta RF-38, RF-44, RF-45.)*

3. **Errores de validación en `@field_validator` de Pydantic no siguen el formato de error de dominio `{code, message, field}` de `CLAUDE.md`.** Salen como HTTP 400 genérico vía el handler de `RequestValidationError` de FastAPI, con formato `{error_code, fields[]}` — a veces en contradicción directa con el código HTTP que el propio RF documenta (ej. RF-33 flujo #8 pide 422, RF-48 fecha futura documentada como 422 en las notas del dev). Afecta a cualquier DTO del módulo que use `@field_validator`, no es exclusivo de un RF.

4. **Los errores de negocio que solo detecta un trigger de PL/pgSQL (con `ERRCODE` propio `P02xx`) caen en HTTP 500 genérico, no en el código específico del RF.** `raise_from_db_error` (`src/shared/db_error_translator.py`) solo traduce `IntegrityError`/`DataError`/`OperationalError` de SQLAlchemy — no reconoce los `RAISE EXCEPTION ... USING ERRCODE='P02xx'` que usan los triggers de este módulo. Confirmado 100% reproducible en RF-40 (mismatch de unidad `'gr'` vs `'g'`) y RF-42 (bloqueo de LOTE en reproductivo). *(Afecta RF-39, RF-40, RF-41, RF-42.)*

5. **RBAC más amplio que la lista de actores del RF, de forma sistemática (Ingeniero de Campo incluido donde el RF no lo menciona), y en un caso al revés (Veterinario excluido donde el RF sí lo lista).** El recurso 29 (`activos_biologicos`) agrupa demasiadas operaciones bajo el mismo par acción+recurso — por ejemplo, la acción C (crear) sirve tanto para "registrar evento productivo" (RF-43, donde los 4 roles aplican) como para "registrar baja" (RF-45, donde el RF solo lista 3), así que no se puede dar a uno sin dársela al otro con el modelo de permisos actual. El caso inverso: RF-35 excluye a Veterinario de `PATCH /{id}` pese a listarlo como actor explícito. *(Afecta RF-35, RF-37, RF-44, RF-45.)* Ningún use case tiene `id_rol` quemado — es puramente un problema de granularidad del catálogo de recursos/permisos, no de disciplina de código.

6. **La bitácora de auditoría RF-52 no es append-only a nivel de base de datos y su escritura es best-effort, no "sin excepción".** Es el hallazgo más serio del módulo desde la perspectiva de valor de negocio: RF-52 es explícitamente la fuente de evidencia para valoración NIC 41 (M06) y auditorías ICA/UPRA, y hoy ni la inmutabilidad ni la garantía de "todo evento se registra sin excepción" están reforzadas más allá de la buena voluntad del código de aplicación. *(Afecta RF-50, RF-51, RF-52, y de rebote la confiabilidad de la bitácora que citan RF-33 a RF-49.)*

7. **Las notas de desarrollo en `anotaciones/modulo_2/` contienen afirmaciones desactualizadas confirmadas, no solo en RF-48** (transferencias "solo admin y productor" cuando el RBAC real da el permiso a los 4 roles) **sino también en RF-45** (el propio doc de gaps de BD revisó el RBAC de bajas y concluyó "sin gaps" sin notar que Ingeniero de Campo puede registrar bajas pese a no ser actor del RF). Confirma que estas notas deben tratarse como evidencia a verificar, no como fuente de verdad — igual que se hizo con `CLAUDE.md` en la auditoría del módulo 1.

8. **RF-33's snapshot inicial ("Evento 0" en `historial_activos`) no existe ni como tabla.** El único punto de origen inmutable que el RF exige para el historial de cada activo simplemente no está modelado — la trazabilidad del activo empieza con el primer evento real, no con un snapshot de creación.

9. **Nota positiva, a diferencia del módulo 1: ningún use case de las 20 RFs auditadas tiene un `id_rol` quemado para decidir acceso.** La autorización vive consistentemente en `require_permission` a nivel de router en todo el módulo — la disciplina de `CLAUDE.md` en este punto se respeta mejor aquí que en `identity_access`.
