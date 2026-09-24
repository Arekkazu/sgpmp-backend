# CU03 — Gaps de BD y RBAC — RF-36

## Fecha de análisis
2026-06-27

## Schema: modulo2

---

## Gaps encontrados

### GAP-01: Permiso faltante para Veterinario (RBAC)

**Situación:** El veterinario (id_rol=3) solo tenía R(2) sobre el recurso 29 (`activos_biologicos`). Según RF-36, el Veterinario es actor principal y puede registrar eventos sanitarios.

**Decisión:** Agregar acción C(1) al rol vet sobre recurso 29. Se reutiliza el recurso 29 existente para los eventos de lote (son sub-recursos de `/activos-biologicos/{id}/eventos`).

**SQL aplicado:**
```sql
INSERT INTO modulo1.permisos (id_rol, id_recurso, id_accion, nombre, es_activo)
VALUES (3, 29, 1, 'vet_crear_activo_biologico', true);
```

**Estado:** Aplicado el 2026-06-27.

---

## Gaps de DDL: Ninguno

Las tablas de eventos ya existían en modulo2 con la estructura correcta:
- `modulo2.eventos_activos` (tabla padre)
- `modulo2.eventos_crecimeinto` (typo intencional en la BD)
- `modulo2.eventos_bajas`
- `modulo2.eventos_sanitarios`
- `modulo2.eventos_productivos`

Los modelos ORM, puertos, repositorios, use cases y endpoints fueron creados en código durante esta iteración.

---

## Decisiones de diseño

### D-01: Densidad máxima por especie — RESUELTO (INC-M02-48-G25, 2026-09-20)

**Situación:** RF-36 exige comparar `cantidad_actual / superficie` con una
`densidad_maxima_por_especie` definida en M09. La corrección inicial interpretó
el límite como `infraestructuras.capacidad_maxima / superficie`, pero ese dato
representa capacidad física, no la parametrización biológica por especie.

**Resolución:** la revisión Alembic `7abae1ee50f6` agrega
`modulo9.especies.densidad_maxima_por_especie`. El campo se administra mediante
los endpoints de especies de M09 y se consulta desde M02 mediante
`ParametrosEspeciePort`.

Registro, crecimiento y transferencia de lotes usan la misma política. La
ausencia de límite o de superficie produce un `422` controlado; exceder el
límite produce `409 DENSIDAD_MAXIMA_SUPERADA`. No se usan valores inventados
para las especies existentes y `capacidad_maxima` conserva su responsabilidad
independiente.

### D-02: Typo en nombre de tabla respetado

La tabla `modulo2.eventos_crecimeinto` (le falta la 'i' en "crecimiento") tiene el typo en la BD. El ORM mapea el nombre literal en `__tablename__` para no romper la FK existente.

### D-03: Enums PG mapeados como String

Los enums de PostgreSQL (`enum_evento_bajas_tipo`, `enum_evento_sanitario_tipo`) se mapean como `String` en los modelos ORM, siguiendo el patrón del proyecto para evitar conflicto con tipos existentes en la BD.

### D-04: Arquitectura sin herencia de tabla en SQLAlchemy

Aunque `sqlacodegen` generó los sub-modelos como clases Python que heredan de `EventosActivos`, el proyecto usa relaciones FK simples (`back_populates`) sin herencia de tabla SQLAlchemy. Esto es consistente con el resto del módulo y evita complejidad de mapeo.

---

## Iteración 2026-09-23 — Ficha de gestión de lote, densidad máxima, ingreso de individuos

Tarea Taiga "RF-36: Ficha de gestión de lote, densidad máxima, ingreso de
individuos" (8 pts). Al retomar el RF (~40% completo tras la iteración
anterior) seguían faltando: (1) un endpoint/caso de uso propio de "ficha de
lote" con la vista operativa completa (cantidad_actual + peso_promedio +
biomasa_total + densidad + estado + historial en una sola respuesta,
distinta de la ficha integral genérica de RF-47 que no expone densidad ni
densidad_maxima), y (2) cualquier mecanismo de ingreso/alta de individuos a
un lote — solo existía el flujo de BAJA. La validación de
`densidad_maxima_por_especie` (tercer punto original del RF) ya estaba
resuelta por INC-M02-38-G25 (ver D-01 arriba); no requirió trabajo adicional,
solo reutilizar el mismo cálculo (`capacidad_maxima/superficie`) en el nuevo
`RegistrarEventoIngresoUseCase`, evaluado antes de aplicar el cambio (a
diferencia de crecimiento, el ingreso sí incrementa `cantidad_actual`).

### GAP-02: Sin mecanismo de ingreso/alta de individuos (DDL + código)

**Situación:** RF-36 exige que `cantidad_actual` se modifique "únicamente
mediante eventos de tipo BAJA o mediante registros de ingresos asociados a
eventos". Solo existía `modulo2.eventos_bajas`; no había tabla ni enum para
ingresos.

**Decisión:** Se crea `modulo2.eventos_ingresos`, mismo patrón que
`eventos_bajas` (sub-tabla 1:1 de `eventos_activos`, FK como PK). El tipo de
ingreso reutiliza los 4 valores que ya usa `origen_financiero` del registro
inicial (`compra`, `nacimiento`, `donacion`, `transferencia_interna`).
`RegistrarEventoIngresoUseCase` (nuevo) sigue la misma estructura que
`RegistrarEventoBajaUseCase`, con la validación adicional de densidad máxima.

**SQL aplicado:** ver `alembic/versions/2848535f94f5_v5_4_0_rf36_eventos_ingresos_lote.py`.

**RBAC:** no requirió cambios — `POST /{id}/eventos/ingreso` reutiliza
`(recurso 29, acción C=1)`, el mismo par que ya usa `POST /{id}/eventos/baja`.
Confirmado en vivo que Administrador, Productor, Veterinario e Ingeniero de
Campo ya lo tienen los cuatro (incluyendo el permiso `vet_crear_activo_biologico`
sembrado en GAP-01 de la iteración anterior).

### GAP-03: CHECK bloqueaba cualquier ingreso real (bloqueante)

**Situación:** `modulo2.detalles_activos_biologicos_poblacionales` tenía
`chk_poblacional_cantidad_actual_coherente = (cantidad_actual <=
cantidad_inicial)` — una regla escrita bajo el supuesto de que
`cantidad_actual` solo podía decrecer desde `cantidad_inicial` (vía baja),
nunca crecer. Confirmado en vivo (transacción revertida): un ingreso real
sobre un lote con `cantidad_inicial=500` fallaba con `CheckViolation` al
intentar dejar `cantidad_actual=550`.

**Decisión:** se elimina ese CHECK. El piso ya lo garantiza
`chk_poblacional_cantidad_actual_no_negativa` (`cantidad_actual >= 0`, se
conserva), y el techo real (`densidad_maxima_por_especie`) no es una regla de
tabla simple — depende de `capacidad_maxima`/`superficie` de la
infraestructura, así que se aplica a nivel de aplicación
(`RegistrarEventoIngresoUseCase`), igual que ya hace INC-M02-38-G25 para
crecimiento.

### GAP-04: Eventos de INGRESO nunca aparecerían en el historial (bloqueante para la ficha de lote)

**Situación:** `ConsultarFichaLoteUseCase` reutiliza
`SqlAlchemyTransferenciaRepository.consultar_historial()` (el mismo método
que ya usan RF-46/RF-48) para su campo `historial`. Ese método filtra por un
set fijo `categorias_a_consultar` en
`src/biological_assets/infrastructure/repositories/transferencia_repository.py`
que nunca pudo incluir `'INGRESO'` porque la categoría no existía hasta esta
migración.

Investigación en vivo inicial sugirió, incorrectamente, que `eventos_bajas`
también faltaba en `modulo2.vw_rf46_historial_completo_activo` y que por eso
los eventos de BAJA tampoco aparecerían en el historial. Verificación más
detallada mostró que ese diagnóstico era equivocado: BAJA nunca dependió de
esa vista — se resuelve en un bloque separado del mismo repository contra
`modulo2.vw_rf46_eventos_bajas`, una vista dedicada que ya existía y ya
funcionaba. Queda como nota para no repetir la confusión: al verificar por
qué una categoría "no aparece en el historial", revisar primero qué vista
consulta realmente `consultar_historial()` para esa categoría antes de asumir
que el problema está en `vw_rf46_historial_completo_activo`.

**Decisión (corrección real aplicada):**
- Se agrega la categoría `INGRESO` a `vw_rf46_historial_completo_activo`
  (mismo patrón de columnas que `SANITARIO`/`CRECIMIENTO`), vía
  `CREATE OR REPLACE VIEW` en la misma migración.
- Se agrega `'INGRESO'` al set `categorias_a_consultar` del repository.
- No se tocó nada de la vista/ruta de BAJA — ya funcionaba.

**Verificado en vivo** (transacción revertida, nunca comiteada): con un
activo POBLACIONAL efímero creado dentro de la misma transacción de prueba,
tras el fix un evento de BAJA y uno de INGRESO registrados sobre ese activo
aparecen ambos en `ConsultarFichaLoteUseCase.execute(...).historial`. También
se verificó `downgrade()`: restaura la vista a su definición original
verbatim (capturada con `pg_get_viewdef`) y elimina `eventos_ingresos`/el enum.

**Fuera de alcance (relacionado, no corregido):** el DTO de RF-46
(`ConsultarHistorialDTO._CATEGORIAS_VALIDAS`) no incluye `'INGRESO'` en su
whitelist de filtro explícito por categoría (`GET
/{id}/historial?categoria_evento=...`). La ficha de lote de RF-36 no pasa por
ese DTO (llama `consultar_historial()` directamente sin filtro), así que no
bloqueaba esta tarea. Agregar `'INGRESO'` a esa whitelist es una mejora de
RF-46 que queda pendiente para cuando se trabaje ese RF explícitamente.

### D-05: Paréntesis desbalanceados al reconstruir la vista a mano

Al escribir el `CREATE OR REPLACE VIEW` para agregar la rama `INGRESO`, una
primera transcripción manual de la rama `FASE_PRODUCTIVA` (concatenación de
`duracion_dias`/`es_activa`/`fecha_finalizacion`) introdujo un paréntesis de
más, y una corrección posterior con `sed` lo dejó con uno de menos —
ambos casos fallan en `CREATE OR REPLACE VIEW` con `syntax error at or near
"AS"`. Se resolvió capturando la definición completa de la vista en vivo con
`SELECT pg_get_viewdef('modulo2.vw_rf46_historial_completo_activo'::regclass,
true)` y copiándola verbatim (en vez de reconstruirla a mano) tanto para el
`upgrade()` como para el `downgrade()`. Lección para migraciones futuras que
modifiquen una vista existente: siempre partir de `pg_get_viewdef` en vivo,
nunca reescribir la definición de memoria.
