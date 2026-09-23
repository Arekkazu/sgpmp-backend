# Gaps BD y RBAC — RF-37: fase_destino/confirmacion_no_estandar, fecha no futura, RBAC

Tarea Taiga "RF-37: fase_destino/confirmacion_no_estandar, fecha no futura,
RBAC" (5 pts). Sigue a `cu02_gaps_bd_rf35_rf37.md` (implementación original
de CU02).

## 1. Modelo "fase destino + confirmación de transición no estándar"

### Gap detectado

El DTO real (`cambiar_fase_dto.py`) solo tenía `id_ciclo_productiva`,
`motivo_cambio` y `fecha_inicio` — no existía `fase_destino_id` ni
`confirmacion_no_estandar`. El use case siempre avanzaba automáticamente a
la siguiente fase de la secuencia (`fase_siguiente_idx = len(gestiones_en_ciclo)`).
**Consecuencia:** el flujo alterno "transición no estándar sin confirmación"
(409) era inalcanzable — nunca se podía solicitar una transición fuera de
secuencia, ni saltando pasos hacia adelante ni retrocediendo.

### Gap de BD encontrado en el Paso 0 (bloqueante, no solo de código)

Verificado en vivo vía MCP Postgres antes de escribir código:

```sql
SELECT column_name, data_type FROM information_schema.columns
WHERE table_schema = 'modulo2' AND table_name = 'gestiones_fases';
```

`modulo2.gestiones_fases` **no tiene ninguna columna que registre a qué fase
específica del ciclo corresponde cada fila**. `paso_actual`/
`nombre_fase_actual` se reconstruían contando cuántas filas existen para
`(id_activo_biologico, id_ciclo_productiva)` y mapeando ese conteo a una
posición en `ciclos_productivos_biologicos` ordenado por
`id_ciclos_productivo_biologico ASC` — un modelo que **asume avance
estrictamente secuencial**. Sin una columna que persista la fase real
alcanzada, permitir una transición no estándar (salto o retroceso) habría
dejado al sistema sin forma de saber en qué fase quedó el activo: el
siguiente cálculo de "fase estándar siguiente" habría vuelto a asumir
secuencia estricta y habría quedado mal — un problema de integridad de
datos, no solo una limitación de la API.

**Decisión:** agregar `id_ciclos_productivo_biologico` (FK a
`modulo9.ciclos_productivos_biologicos`) a `modulo2.gestiones_fases`, con
backfill de las filas existentes usando la misma lógica de conteo que el
código ya asumía (`ROW_NUMBER() OVER (PARTITION BY id_activo_biologico,
id_ciclo_productiva ORDER BY fecha_inicio, id_gestion_fases)` mapeado a la
fase en esa posición). El backfill es seguro porque ninguna fila existente
puede representar un "salto" — esa capacidad no existía hasta ahora.
Verificado en vivo: 19 filas reales, posición máxima alcanzada = 2, todos
los ciclos referenciados tienen suficientes fases para esa posición — 100%
de cobertura del backfill, confirmado por la propia migración (`RAISE
EXCEPTION` si alguna fila quedara sin backfillear).

### Segundo gap de BD encontrado al verificar el backfill en vivo

El primer intento de backfill falló contra `sgpmp_dev` real:
`trg_fase_activo_estado_valido` (`BEFORE INSERT OR UPDATE` sobre
`gestiones_fases`, **sin filtro de columna**) rechaza cualquier `UPDATE`
sobre esta tabla si el activo asociado está en estado `BAJA` — y existen
filas reales de activos en `BAJA`. Como el backfill no cambia
`fecha_inicio`/`fecha_finalizacion`/`es_activa` (solo agrega metadata
histórica en la columna nueva), se desactiva puntualmente ese trigger
(`ALTER TABLE ... DISABLE TRIGGER`) solo durante el `UPDATE` del backfill y
se reactiva inmediatamente después, dentro de la misma migración. Verificado
en vivo que, con este ajuste, el backfill corre limpio sobre las 19 filas
reales (incluida la del activo en `BAJA`).

### Nueva lógica del use case

- `_execute()` calcula la "fase estándar siguiente" a partir de la fase
  **realmente persistida** de la última gestión en ese ciclo (no de un
  conteo), buscando su posición en `ciclo.fases`.
- Sin `fase_destino_id`: comportamiento histórico exacto — avanza a la fase
  estándar siguiente, o `422 CICLO_COMPLETADO` si ya no hay más.
- Con `fase_destino_id`: se permite cualquier fase del ciclo. Si coincide
  con la estándar, procede igual que antes (`es_transicion_no_estandar=false`).
  Si no coincide (salto hacia adelante, retroceso, o re-entrar a cualquier
  fase después de completar el ciclo), exige `confirmacion_no_estandar=true`
  o rechaza con `409 TRANSICION_NO_ESTANDAR_SIN_CONFIRMAR`.
- `fase_destino_id` que no pertenece a la secuencia del ciclo → `400
  FASE_DESTINO_INVALIDA` (vía `ValidationError`, campo `fase_destino_id`).

**Pendiente de confirmación del grupo de análisis:** el texto completo de
RF-37 no está en este repositorio (mismo caso que RF-35). La interpretación
de "transición no estándar" aplicada aquí (cualquier fase que no sea la
inmediatamente siguiente en la secuencia definida del ciclo, incluyendo
retrocesos y re-entradas tras completar el ciclo) se apoya en el propio
nombre de los campos que pide la tarea (`fase_destino_id`,
`confirmacion_no_estandar`) y en el modelo de secuencia ya existente — no en
el texto original del RF.

## 2. Fecha no futura

**Gap:** ni el DTO ni ningún trigger de `gestiones_fases` validaban que
`fecha_inicio` no fuera futura.

**Corrección:** `@field_validator('fecha_inicio')` en `CambiarFaseDTO`,
mismo patrón que `CambiarEstadoDTO.fecha_no_futura` (RF-44) — rechaza con
`ValueError` (→ 400, comportamiento estándar de Pydantic en este proyecto,
ver Hallazgo transversal #3 de `estado_M02.md`) si la fecha es posterior a
"ahora" en UTC.

## 3. RBAC — Ingeniero de Campo incluido cuando el RF solo lista Productor/Veterinario/Administrador

Verificado en vivo vía MCP Postgres:

```sql
SELECT p.id_permiso, p.nombre, p.id_rol, r.nombre_rol
FROM modulo1.permisos p JOIN modulo1.roles r ON r.id_rol = p.id_rol
WHERE p.id_recurso = 29 AND p.id_accion = 5;
```

Resultado: Administrador, Productor, Veterinario **e Ingeniero de Campo**
tienen el permiso `(recurso 29, acción E=5)`. El RF (según la tarea Taiga)
solo lista Productor/Veterinario/Administrador como actores.

**Decisión: documentar, no ajustar.** El recurso 29 / acción E (5) no es
exclusivo de RF-37 — lo comparten `PATCH /{id}/estado` (RF-44) y
`POST /{id}/transferencias` (RF-48, dos endpoints), confirmado en el router
(`activo_biologico_router.py`, 4 usos de `require_permission_m02(_RECURSO, 5, ...)`
sobre RF-37/RF-44/RF-48×2). Revocarle a Ingeniero de Campo el permiso
`ing_ejecutar_cambio_fase` para "arreglar" RF-37 le quitaría también acceso
a RF-44 y RF-48, dos RFs donde no hay evidencia de que su exclusión sea
correcta — un ajuste más amplio del que pide esta tarea, con riesgo real de
regresión. Mismo patrón ya documentado como hallazgo transversal #5 en
`estado_M02.md` ("RBAC más amplio que la lista de actores del RF, de forma
sistemática... el recurso 29 agrupa demasiadas operaciones bajo el mismo par
acción+recurso"). Corregirlo de raíz requeriría separar `cambiar_fase` en su
propio recurso RBAC (mismo patrón que ya se usó para los scopes de RF-50) —
fuera de alcance de esta tarea de 5 puntos.

## Migración

`alembic/versions/69d26aea234c_v5_5_0_rf37_id_fase_ciclo_gestiones_.py` —
`down_revision=c8d4f1a9b7e2` (head real de `origin/dev` al momento de
escribir esta migración). DDL (columna + FK) + backfill DML en una sola
migración porque el backfill es indispensable para que la columna pueda
cerrarse `NOT NULL` de forma segura — separarlos habría dejado una ventana
con la columna nullable y sin garantía de cobertura.

`downgrade()` es real y reversible: quita la FK y la columna. No hay
permisos `admin_*` de por medio (esta migración no toca RBAC), así que no
aplica la inmutabilidad que sí afecta a otras migraciones de esta cadena.

### Verificación en vivo (credenciales `dba`, transacción revertida con `ROLLBACK`)

| Comprobación | Resultado |
|---|---|
| Migración corre sin error (incluye el fix del trigger `DISABLE`/`ENABLE`) | ✅ |
| Las 19 filas reales quedan backfilleadas (0 con `id_ciclos_productivo_biologico IS NULL`) | ✅ |
| `SqlAlchemyActivoBiologicoRepository.obtener_gestiones_fases()` real lee la fase persistida y calcula `paso_actual`/`nombre_fase_actual` correctamente (activo 1, ciclo 1: fase 1 → paso 1/3, fase 2 → paso 2/3) | ✅ |
| `crear_gestion_fase()` real persiste `id_ciclos_productivo_biologico` en una fila nueva | ✅ |
| Estado de `sgpmp_dev` tras el `ROLLBACK` final | ✅ Sin cambios |

No se corrió el `alembic upgrade head` real vía CLI ni el `downgrade()` en
vivo (se priorizó verificar el backfill real, que era el riesgo principal de
esta migración) — queda para quien la aplique con aprobación del DBA.

## Fuera de alcance

- No se resuelve el hallazgo transversal #5 de RBAC de forma general (ver
  sección 3) — solo se documenta para RF-37.
- No hay inmutabilidad reforzada por trigger de DB para el historial de
  fases (a diferencia de `historicos_estados_activos`) — gap ya documentado
  en `estado_M02.md`, no pedido por esta tarea.
- El desempate `ORDER BY gf.fecha_inicio ASC, gf.id_gestion_fases ASC`
  agregado a `obtener_gestiones_fases` es una corrección menor encontrada de
  paso (varias filas semilla comparten el mismo `fecha_inicio` exacto, lo
  que hacía el orden de retorno no determinístico) — no afecta la lógica de
  `paso_actual`/`nombre_fase_actual` de cada fila individual, que ya no
  depende del orden desde esta tarea.
