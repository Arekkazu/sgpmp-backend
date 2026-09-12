# INC-M02-75-G53 — POST .../eventos/reproductivo responde 500 en el primer evento válido

**RF:** RF-42 (evento reproductivo), pero la causa raíz es transversal a **todos**
los tipos de evento del módulo (crecimiento, sanitario, productivo, baja,
reproductivo) porque vive en el trigger compartido sobre `eventos_activos`.

## Qué reportó QA

`POST /activos-biologicos/{id}/eventos/reproductivo` respondía `500 ERROR_INTERNO`
al registrar un evento `servicio`/`inseminacion` válido sobre una hembra activa
con un padre válido. El propio reporte apuntaba a `db_error_translator.py` sin
mapear un ERRCODE de trigger como causa probable.

## Investigación

Reproducir contra la base real (`sgpmp`) con el use case real, no con fakes de
test (que no ejecutan triggers de Postgres), dio el traceback real:

```
psycopg2.InternalError: INVALID_DATE: La fecha del evento (2026-09-12 11:25:17.840696+00)
no puede ser futura. Fecha actual del sistema: 2026-09-12 11:25:17.833359+00.
CONTEXT: PL/pgSQL function modulo2.trg_fn_evento_fecha_coherente() line 6 at RAISE
```

La fecha del evento es **7 milisegundos posterior** a la fecha "actual" que vio
el trigger — pese a que el evento se registró en el mismo instante. Causa raíz:

- `trg_fn_evento_fecha_coherente()` compara `NEW.fecha > now()`.
- En Postgres, `now()` (alias de `CURRENT_TIMESTAMP`/`transaction_timestamp()`)
  queda **congelado al inicio de la transacción**, no se reevalúa por sentencia.
- `RegistrarEventoReproductivoUseCase.execute()` abre la transacción con su
  primera consulta (`activo_repo.obtener_por_id(id_activo)`) y **después**
  calcula `fecha = dto.fecha or datetime.now(timezone.utc)` — con la
  transacción ya abierta. El reloj real sigue avanzando; el `now()` de Postgres
  no. Para cuando el `INSERT` llega al trigger, `NEW.fecha` (reloj real, más
  tardío) siempre es "futura" respecto al `now()` congelado, aunque en tiempo
  real nunca lo fue.
- El mismo problema existía en el `CHECK (fecha <= now())` de la propia columna
  (`chk_eventos_fecha_no_futura`), que también se dispara antes que el trigger
  personalizado pueda dar un mensaje más claro en algunos casos.

Esto **no es específico de reproductivo** ni de la categoría `servicio`: el
trigger vive en `modulo2.eventos_activos`, la tabla padre compartida por los 5
subtipos de evento del módulo. Cualquier endpoint de registro de eventos que no
reciba `fecha` explícita en el body (y calcule "ahora" en Python) es susceptible
al mismo fallo, con una ventana de tiempo que depende de cuántas consultas
previas haga el use case dentro de la misma transacción antes de calcular
`fecha`. Los ejemplos de curl existentes en este módulo siempre incluían una
`fecha` explícita en el pasado, lo que evitaba tropezar con el bug — probable
razón de que no se hubiera detectado antes.

## Fix

Migración `68232a1efcc2` (aplicada a `sgpmp` y `pruebas`):

1. `trg_fn_evento_fecha_coherente()`: `now()` → `clock_timestamp()` en la
   comparación de "no futura" (la comparación contra `fecha_creacion` del
   activo no cambia, no depende de "ahora").
2. `chk_eventos_fecha_no_futura` (CHECK de columna en `eventos_activos`):
   mismo cambio, `now()` → `clock_timestamp()`.

`clock_timestamp()` se reevalúa en cada llamada (no se congela por
transacción), que es el comportamiento correcto para "¿esta fecha es futura
en este instante real?".

Adicional, defensa en profundidad en `src/shared/db_error_translator.py`:
el ERRCODE `P0215` que usa este trigger (clase `P0`, no mapeada por
psycopg2/SQLAlchemy) ahora se traduce a `ValidationError` (400,
`FECHA_INVALIDA`) en vez de cae al 500 genérico — por si alguna vez una fecha
sí es genuinamente inválida y llega a esta vía sin pasar por la validación de
aplicación (`validar_fecha_evento` en `_event_validations.py`, que ya rechaza
fechas futuras con un 422 `FECHA_FUTURA` antes de tocar la BD).

## Pruebas

- `tests/integration/test_inc_m02_75_g53_evento_fecha_race.py` (nueva, requiere
  `TEST_DATABASE_URL` con la migración aplicada): reproduce la carrera real
  (transacción ya abierta antes de calcular `fecha`) y confirma que se acepta;
  confirma también que una fecha genuinamente futura se sigue rechazando.
  Verificado que este test **falla** si se hace `alembic downgrade -1`
  (confirma que prueba el fix real, no una tautología).
- `tests/shared/test_db_error_translator.py`: caso nuevo para `P0215`.
- Suite completa de `tests/biological_assets/` y `tests/shared/` sin
  regresiones (108 passed). Suite de integración sin regresiones nuevas (los
  7 fallos preexistentes en `test_rf20_tipos_area.py` y dos más son
  independientes de este cambio — fallan igual con o sin la migración,
  problema de generación de datos de prueba con nombres de finca que
  incluyen dígitos, no relacionado con INC-M02-75-G53).

## Alcance

No se tocó `RegistrarEventoReproductivoUseCase` ni ningún otro use case de
eventos — la causa raíz vivía enteramente en BD (trigger + CHECK compartidos),
así que el fix beneficia a los 5 tipos de evento del módulo sin tocar código
de aplicación.
