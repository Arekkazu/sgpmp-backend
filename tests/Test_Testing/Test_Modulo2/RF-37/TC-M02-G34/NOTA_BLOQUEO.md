# TC-M02-G34 — BLOQUEO total: los 4 sub-casos dependen de RF-37 `cambiar_fase`, y uno además de un segundo defecto en RF-45

## 1. Bloqueo común a los 4 sub-casos — INC-M02-37-01 (ya reportado)

`POST /activos-biologicos/{id}/fases` crashea con 500 para cualquier activo/ciclo. Causa confirmada por código:
`cambiar_fase_use_case.py:72` llama `cerrar_gestion_activa()` con 3 argumentos, el método exige 4 (falta
`usuario_id`). Detalle completo en `tests/Test_Testing/Test_Modulo2/RF-35/TC-M02-G23/NOTA_BLOQUEO.md`. Re-confirmado
aquí en 3 intentos más (activo 204, especie 2/Trucha, ciclo productivo 2).

Efecto sobre cada sub-caso:
- **TC-M02-040** (fecha inválida): el 500 ocurre antes de que exista cualquier validación de fecha — y de hecho
  `CambiarFaseDTO` no valida `fecha_inicio` en absoluto (sin `field_validator` de rango). Aunque se corrija
  INC-M02-37-01, este sub-caso **seguirá fallando** hasta que se agregue esa validación — es un segundo gap,
  independiente del crash.
- **TC-M02-041** (salto sin confirmación): no es solo el crash — `CambiarFaseDTO` no declara `fase_destino_id` ni
  `confirmacion_no_estandar` (mismo gap ya reportado como **INC-M02-37-02** desde TC-M02-G33). No hay forma de
  siquiera expresar "un salto" en la petición.
- **TC-M02-043** (solapamiento): bloqueado en su precondición — no se puede crear ni la primera fase, mucho menos
  una segunda que se solape con ella. **Buena noticia, confirmada con acceso a BD:** `trg_fn_fase_solapamiento`
  SÍ existe y está bien implementado (compara `fecha_inicio` de la nueva fase contra la `fecha_finalizacion` de la
  última fase cerrada, `RAISE EXCEPTION ... ERRCODE='P0227'` si se solapan) — una vez corregido INC-M02-37-01, este
  sub-caso debería funcionar a nivel de base de datos. Sigue pendiente que `raise_from_db_error` traduzca `P0227`
  a un 409 controlado en vez de dejarlo caer al 500 genérico (mismo gap transversal que INC-M02-41-01).
- **TC-M02-044** (activo BAJA/CERRADO): bloqueado igual por INC-M02-37-01 en el paso de prueba, **y además** su
  precondición (llevar un activo a BAJA o CERRADO) está bloqueada por un defecto distinto — ver sección 2. **Buena
  noticia adicional:** `trg_fn_fase_activo_estado_valido` (rechaza cambios de fase si el último estado es
  CERRADO/BAJA, `ERRCODE='P0228'`) también está bien implementado — una vez resueltos los bloqueos de precondición
  y aplicada la traducción de errores, este sub-caso también debería pasar sin cambios de lógica adicionales.

## 2. Bloqueo nuevo y adicional — precondición de TC-M02-044 (RF-45), causa raíz CONFIRMADA

**Corrección importante:** la hipótesis original de esta sección (CHECK `chk_historico_modulo_origen_valido`
desactualizado) **era incorrecta** — verificado con acceso directo a la base de datos de TEST (credencial de solo
consulta, autorizada explícitamente por el usuario): ese CHECK **ya incluye** `'MANUAL'`, `'RF-38'` y `'RF-45'`
explícitamente:

```sql
CHECK (modulo_origen = ANY (ARRAY['MANUAL','RF-38','RF-45','modulo1',...,'modulo9']))
```

La causa real, confirmada reproduciendo el `INSERT` exacto que hace la app (vía SQLAlchemy ORM, en una transacción
con `ROLLBACK` explícito, autorizada por el usuario): `modulo2.trg_fn_baja_cantidad_valida` (trigger sobre
`modulo2.eventos_bajas`) tiene un **bug de mayúsculas/minúsculas**:

```sql
DECLARE
    v_tipo_activo modulo2.enum_activo_biologico_tipo;  -- tipo ENUM real de Postgres
BEGIN
    ...
    IF v_tipo_activo = 'poblacional' THEN   -- ← literal en minúscula
```

El enum real (`SELECT enum_range(NULL::modulo2.enum_activo_biologico_tipo)`) solo acepta `POBLACIONAL`/`INDIVIDUAL`
**en mayúscula**. Postgres necesita convertir el literal `'poblacional'` a ese tipo enum para poder comparar, y esa
conversión falla con `invalid input value for enum` — **antes de siquiera evaluar si el activo es individual o
poblacional**. Por eso el trigger revienta en el 100% de los `INSERT` a `eventos_bajas`, sin importar el tipo de
activo:

```
psycopg2.errors.InvalidTextRepresentation: invalid input value for enum modulo2.enum_activo_biologico_tipo: "poblacional"
CONTEXT:  PL/pgSQL function modulo2.trg_fn_baja_cantidad_valida() line 13 at IF
```

Este es exactamente el mismo **patrón de bug** ya documentado en la auditoría del módulo para RF-40
(`trg_fn_evento_crecimiento_tipo_activo`, que compara `tipo_activo = 'poblacional'` en minúscula) — aquí aparece
de nuevo en un trigger distinto de RF-45, con un efecto más grave: en RF-40 esa rama simplemente nunca se
ejecutaba (comparación de texto silenciosamente falsa); aquí, al ser una comparación contra un tipo ENUM real, la
conversión de tipo falla de forma dura y bloquea el `INSERT` completo.

**Fix (una línea, en la base de datos, no en el código Python):**
```sql
-- Dentro de trg_fn_baja_cantidad_valida(), cambiar:
IF v_tipo_activo = 'poblacional' THEN
-- por:
IF v_tipo_activo = 'POBLACIONAL' THEN
```

**Impacto confirmado:** el 100% de los registros de baja (`POST /activos-biologicos/{id}/eventos/baja`) fallan hoy
en TEST, para activos INDIVIDUAL y POBLACIONAL por igual — no es específico de la precondición de TC-M02-044, es
un defecto de RF-45 en sí mismo, independiente de RF-37.

### Sección original (conservada por trazabilidad, causa descartada)

La hipótesis de abajo se mantiene tachada conceptualmente para que quede registro de qué se descartó y por qué —
la evidencia real está arriba.

Para preparar un activo en BAJA (sin depender de RF-37), se intentó `POST /activos-biologicos/{id}/eventos/baja`
sobre un activo **sin ninguna fase previa** (así se evita por completo el código de `cerrar_gestion_activa`, que
solo se invoca condicionalmente si existe una fase activa). Aun así:

```
POST /activos-biologicos/205/eventos/baja {"tipo_baja":"muerte","fecha_baja":"...","motivo_baja":"..."}
→ HTTP 500 {"error_code":"ERROR_INTERNO","message":"Error inesperado en base de datos"}
```

Nótese que el mensaje es **"Error inesperado en base de datos"** (el que usa `raise_from_db_error` para errores
reales de SQLAlchemy), distinto del genérico "Ocurrió un error interno" que da el `TypeError` de INC-M02-37-01 —
es una pista de que este es un problema distinto, a nivel de base de datos, no un error de Python.

**Hipótesis con evidencia comparativa fuerte (no confirmada — sin acceso a BD/logs):**
`registrar_evento_baja_use_case.py` registra el cambio de estado vía `aplicar_cambio_estado(..., modulo_origen='RF-45')`
(`_cambio_estado.py:17-36`), que inserta esa cadena literal en `historico_estados_activos.modulo_origen`. En
cambio, `cambiar_estado_use_case.py:54` (el `PATCH /{id}/estado` de RF-44, que **sí funciona** — confirmado en
`TC-M02-G22`) usa `modulo_origen='MANUAL'`. `cerrar_ciclo_use_case.py:108` (RF-38) usa `modulo_origen='RF-38'` —
el mismo patrón que RF-45, así que probablemente falla igual (no se pudo probar de forma aislada porque además
requiere una fase activa, bloqueada por INC-M02-37-01).

La auditoría previa del módulo (`anotaciones/modulo_2/estado.md`, Hallazgo transversal #2) documentó que el CHECK
`chk_historico_modulo_origen_valido` **solo aceptaba literales `'modulo1'..'modulo9'`**, y que por eso el código
anterior usaba `'modulo2'` genérico en vez del RF específico. El código actual (docstring de `_cambio_estado.py`:
*"en lugar de un `modulo2` genérico"*) indica que esto ya se refactorizó para pasar el RF real (`'RF-45'`, `'RF-38'`,
`'MANUAL'`) — coincide con la rama `fix/rf38-44-45-centralizar-cambio-estado` vista en el historial de git. Es
plausible que esa migración de base de datos (ampliar el CHECK para aceptar `'MANUAL'`, `'RF-38'`, `'RF-44'`,
`'RF-45'`) se haya aplicado solo parcialmente en este servidor TEST — aceptando `'MANUAL'` pero no `'RF-45'`/`'RF-38'`
— igual al patrón ya visto en `tests/Test_Testing/Test_Modulo9/RF-20/TC-M09-G48/NOTA_BLOQUEO.md` (migración de
catálogo no aplicada en este servidor específico).

**Para confirmar (requiere acceso que esta sesión no tiene):**
```sql
SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conname = 'chk_historico_modulo_origen_valido';
```
más el traceback completo del backend en el timestamp `2026-09-10T00:44:20Z`.

**Impacto si se confirma:** toda baja de un activo INDIVIDUAL (100% de los casos, porque todos pasan por
`_procesar_baja_con_cierre`) y todo cierre de ciclo (RF-38) estarían rotos en este servidor TEST — no solo el
camino usado para preparar esta precondición.

## Cómo desbloquear (actualizado tras confirmar con acceso a BD)

1. Aplicar el fix de una línea de INC-M02-37-01 (ver `TC-M02-G23/NOTA_BLOQUEO.md`): agregar `usuario.id_usuario`
   como 4º argumento en `cambiar_fase_use_case.py:72`.
2. Corregir `trg_fn_baja_cantidad_valida` en la base de datos: cambiar el literal `'poblacional'` por
   `'POBLACIONAL'` (línea ~13 de la función) — ver sección 2 arriba. Un cambio de una línea en SQL, no en Python.
3. Extender `raise_from_db_error` para traducir los SQLSTATE `P02xx` propios de `modulo2` (`P0219`, `P0224`-`P0228`,
   etc.) a errores de dominio controlados, en vez de dejarlos caer al 500 genérico — necesario para que
   TC-M02-043 y TC-M02-044 devuelvan 409 en vez de 500 una vez resuelto (1).
4. Agregar validación de `fecha_inicio` (no futura, no anterior al inicio de la fase actual) en `CambiarFaseDTO`
   o en el use case — gap independiente, necesario para que TC-M02-040 pase.
5. Implementar el mecanismo de `fase_destino_id`/`confirmacion_no_estandar` — ya reportado como INC-M02-37-02.

Con (1) y (2) resueltos, se puede reintentar toda la colección de este caso desde cero — el DB ya tiene los
triggers correctos para TC-M02-043/044 (confirmado), así que con (1)+(2)+(3) esos dos deberían pasar sin más
cambios de lógica. (4) y (5) son necesarios además para que TC-M02-040 y TC-M02-041 pasen específicamente.
