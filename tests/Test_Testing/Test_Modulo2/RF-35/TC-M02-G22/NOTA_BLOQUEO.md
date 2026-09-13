# TC-M02-G22 (TC-M02-038) — BLOQUEO en la precondición: RF-41 no permite registrar eventos sanitarios en TEST

**RF-35 / CU-02.** No es un bug de RF-35 — es un defecto de RF-41 (`POST /activos-biologicos/{id}/eventos/sanitario`)
que impide construir la precondición literal de TC-M02-038 ("Activo con eventos sanitarios/biológicos pendientes
sin cerrar"). Se documenta aquí porque bloqueó el camino directo de la prueba, y porque es un hallazgo real e
independiente que vale la pena que el equipo revise.

## Qué se observó

`POST /activos-biologicos/{id_activo}/eventos/sanitario` devuelve **500** para los dos únicos tipos de evento
sanitario que no requieren un diagnóstico previo (`DIAGNOSTICO` y `CONTROL_PREVENTIVO`), en dos activos distintos
recién creados:

```json
// POST .../eventos/sanitario {"tipo":"DIAGNOSTICO","diagnostico":"Infeccion bacteriana QA-G22"}
// HTTP 500
{"error_code":"ERROR_INTERNO","message":"Error inesperado en base de datos","fields":[],"timestamp":"2026-09-09T22:59:28.020067+00:00"}
```

```json
// POST .../eventos/sanitario {"tipo":"CONTROL_PREVENTIVO","observaciones":"Control preventivo QA-G22"}
// (sin solicitar_estado, para descartar que el cambio de estado sea la causa)
// HTTP 500
{"error_code":"ERROR_INTERNO","message":"Error inesperado en base de datos","fields":[],"timestamp":"2026-09-09T23:01:18.849310+00:00"}
```

Reproducido en **3 intentos independientes**, en **2 activos distintos** (id 195 y 196), con y sin `solicitar_estado`
— consistente, no es un fallo intermitente.

Esto crea un **bloqueo circular**: `TRATAMIENTO` y `VACUNACION` exigen un `DIAGNOSTICO` previo
(`RegistrarEventoSanitarioUseCase._TIPOS_REQUIEREN_DIAGNOSTICO`), pero registrar ese `DIAGNOSTICO` es precisamente
lo que falla con 500. En la práctica, **ningún tipo de evento sanitario se puede registrar hoy en este entorno TEST**
sobre un activo sin historial sanitario previo.

## Causa raíz — CONFIRMADA con acceso directo a la base de datos (corrige la hipótesis original de abajo)

**Actualización posterior con acceso a PostgreSQL de TEST** (credencial de solo consulta, autorizada explícitamente
por el usuario): la hipótesis original de este documento (el trigger de secuencia sanitaria) **era incorrecta**.
Se revisó `trg_fn_evento_sanitario_secuencia` directamente y su condición de disparo exige `medicamento IS NOT NULL
AND dosis IS NOT NULL` — nunca se activa para `DIAGNOSTICO`/`CONTROL_PREVENTIVO`, que no tienen esos campos.

La causa real es otro trigger, sobre la tabla **padre** `modulo2.eventos_activos`: `trg_fn_evento_fecha_coherente`
(SQLSTATE `P0215`), que rechaza `fecha > now()` con **tolerancia prácticamente nula** (se confirmó un rechazo con
solo ~1.1 segundos de diferencia). El use case (`registrar_evento_sanitario_use_case.py`, `fecha = dto.fecha or
datetime.now(timezone.utc)`) usa "ahora" calculado en el servidor de aplicación cuando el cliente no manda `fecha`
explícita — que es exactamente lo que hicieron todas las peticiones de esta sesión. Confirmado de forma concluyente
contra la API real (no solo en un script aislado):

```
POST .../eventos/sanitario {"tipo":"DIAGNOSTICO","diagnostico":"..."}                     (sin fecha) → HTTP 500
POST .../eventos/sanitario {"tipo":"DIAGNOSTICO","diagnostico":"...","fecha":"<hace 10 min>"} → HTTP 201
```

Y por qué sale como 500 genérico en vez de un 400/422 limpio: `raise_from_db_error()`
(`src/shared/db_error_translator.py`) solo tiene mapeos hardcodeados para 4 SQLSTATE de **módulo 9**
(`P0104`, `P0109`, `P0130`, `P0140`) — ningún SQLSTATE de módulo 2 (`P0215`, `P0219`, `P0224`-`P0228`, ninguno)
está mapeado. Postgres clasifica un `RAISE EXCEPTION ... USING ERRCODE='P0215'` como `InternalError` genérico, que
no es `IntegrityError`/`DataError`/`OperationalError`, así que cae directo en el `raise InfrastructureError(code=
"ERROR_INTERNO", message="Error inesperado en base de datos", ...)` del final de la función — el mensaje exacto
observado en todos los intentos.

## Cómo desbloquear (confirmado, ya no requiere seguir investigando)

1. Causa raíz real: el timestamp por defecto calculado en el servidor de aplicación puede leerse como "futuro" por
   la base de datos con una tolerancia casi nula. Revisar por qué (desfase de reloj entre el contenedor del backend
   y el de PostgreSQL en TEST, o latencia entre el cálculo en Python y la ejecución del `INSERT`) y, como mitigación
   robusta, agregar un pequeño margen de tolerancia en `trg_fn_evento_fecha_coherente` (p. ej. rechazar solo si
   `fecha > now() + interval '2 seconds'`) en vez de una comparación exacta.
2. Extender `raise_from_db_error` para mapear los SQLSTATE `P02xx` propios de `modulo2` (no solo los 4 de
   `modulo9` que ya cubre) a errores de dominio controlados — así cualquier violación real de regla de negocio
   sale como 400/409/422 con el código documentado por su RF, no como 500 genérico. Afecta a los `P02xx` de RF-37,
   RF-39/40/41/42 y RF-44/45 por igual (mismo gap transversal ya señalado en la auditoría del módulo).

## Alcance del bloqueo

Cualquier caso de RF-41 (CU-07, no cubierto todavía por ningún `TC-M02-G*` de este módulo) que registre un evento
`DIAGNOSTICO` o `CONTROL_PREVENTIVO` fallará igual mientras esto no se corrija — y por el bloqueo circular descrito
arriba, `TRATAMIENTO`/`VACUNACION` tampoco se pueden probar sobre un activo sin historial sanitario previo sembrado
de antes. Vale la pena confirmar esto antes de escribir los casos de RF-41.

**Para TC-M02-G22 (RF-35) específicamente**: el bloqueo impidió reproducir la precondición literal de TC-M02-038 vía
RF-41. Se usó como alternativa el endpoint `PATCH /{id}/estado` (RF-44) para dejar el activo en `EN_TRATAMIENTO` sin
pasar por RF-41 — ver `RESULTADOS/TC-M02-G22_resultado.md`, sección TC-M02-038, para el resultado de esa
verificación adaptada (que sigue siendo válida para lo que RF-35 necesita probar: si el endpoint bloquea operaciones
mientras el activo tiene un proceso abierto sin cerrar).
