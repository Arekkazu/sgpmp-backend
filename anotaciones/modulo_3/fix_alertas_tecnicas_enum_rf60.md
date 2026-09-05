# Fix — Alertas técnicas IoT (RF-60): 500 en `GET /iot/alertas-tecnicas`

> Fecha: 2026-07-28 · Equipo: **Dev (backend)** · Módulo: M03 (Telemetría e IoT)
> Rama: `tweak/iot`. **No se hizo commit** (pendiente de indicación).

---

## Síntoma

`GET /api/iot/alertas-tecnicas?por_pagina=50&pagina=1` → **500 Internal Server Error**.

Se manifestaron **dos** errores encadenados (el segundo apareció al corregir el primero):

1. `TypeError: ConsultarAlertasUseCase.__init__() got an unexpected keyword argument 'db'`
2. `psycopg2.errors.InvalidTextRepresentation: invalid input value for enum modulo3.enum_tipo_alerta: "TECNICA"`

---

## Causa raíz

### Bug 1 — argumento `db` de más (trivial)

El handler `listar_alertas_tecnicas` instanciaba `ConsultarAlertasUseCase(db=db, ...)`, pero ese
caso de uso es de **solo lectura** y su `__init__` solo acepta `alerta_repo` e `historico_repo`
(no hace `commit()`, así que no necesita la sesión). El router hermano `alerta_router.py` ya lo
instanciaba correctamente sin `db`.

### Bug 2 — gap de BD (Paso 0 sin resolver)

Toda la feature de **"alertas técnicas" (RF-60)** se escribió contra valores de enum que **nunca se
aplicaron** a la tabla `modulo3.alertas` (compartida con las alertas biológicas). Verificado vía MCP
postgres:

| Columna | Enum real (antes) | Lo que el código escribía/filtraba |
|---|---|---|
| `tipo_alerta` (`enum_tipo_alerta`) | ESTRES_TERMICO, SINDROME_RESPIRATORIO, RIESGO_HIDRICO, FIEBRE, INACTIVIDAD_ANORMAL, FALLO_AMBIENTAL, PREDICCION_PATOLOGIA, TORMENTA_DE_ALERTAS | **`TECNICA`** ❌ |
| `origen_evento` (`enum_origen_evento_alerta`) | EDGE, BACKEND, IA | **`HEARTBEAT`**, **`EVALUACION_PERIODICA`** ❌ |
| `severidad` (`enum_buffer_nivel_severidad`) | LEVE, MODERADO, CRITICO | **`CRITICA` / `ALTA` / `MEDIA`** ❌ |

El 500 del listado (`WHERE tipo_alerta = 'TECNICA'`) era solo la punta: los **tres sitios de
escritura** compartían el mismo defecto latente. La feature nunca funcionó end-to-end (cualquier
heartbeat con batería baja habría dado 500 + rollback). En la tabla no había ni una sola alerta
técnica; todos los datos eran biológicos.

Sitios afectados:
- `recibir_heartbeat_use_case.py` (alertas por batería/señal) — write
- `evaluar_estado_dispositivos_use_case.py` (alertas por inactividad) — write
- `infraestructura_iot_router.py` (filtro fijo del listado) — read

---

## Decisión (Paso 0)

Elegida por el líder: **extender los enums** (en vez de crear una tabla separada de alertas técnicas),
porque el código y la documentación (`api_reference_m03_telemetria_iot.md`) ya estaban escritos en
torno a `tipo_alerta='TECNICA'` + `origen_evento='HEARTBEAT'`. Es el camino de menor fricción que
deja coherentes lectura y escritura.

Sub-decisión de **severidad**: no crear una escala paralela. Se **mapea** la severidad técnica a la
escala existente `LEVE / MODERADO / CRITICO` en el código (no se toca el enum de severidad).

---

## Cambios aplicados

### DDL (vía MCP postgres) — **no gestionado por migraciones**

```sql
ALTER TYPE modulo3.enum_tipo_alerta            ADD VALUE IF NOT EXISTS 'TECNICA';
ALTER TYPE modulo3.enum_origen_evento_alerta   ADD VALUE IF NOT EXISTS 'HEARTBEAT';
ALTER TYPE modulo3.enum_origen_evento_alerta   ADD VALUE IF NOT EXISTS 'EVALUACION_PERIODICA';
```

> `EVALUACION_PERIODICA` se descubrió durante la implementación (segundo `origen_evento` inválido, en
> `evaluar_estado`). Se añadió por consistencia con la misma decisión, para conservar la trazabilidad
> del origen. **`ALTER TYPE … ADD VALUE` es prácticamente irreversible** en Postgres (quitar un valor
> obliga a recrear el tipo). Solo aplicado en la BD **dev**.

Estado final de los enums:
- `enum_tipo_alerta`: …, TORMENTA_DE_ALERTAS, **TECNICA**
- `enum_origen_evento_alerta`: EDGE, BACKEND, IA, **HEARTBEAT**, **EVALUACION_PERIODICA**

### Código

- `infraestructura_iot_router.py` — se quita `db=db` de la instanciación de `ConsultarAlertasUseCase`
  (queda igual que en `alerta_router.py`).
- `recibir_heartbeat_use_case.py` — severidad `CRITICA→CRITICO`, `ALTA→MODERADO`, `MEDIA→LEVE`
  (batería crítica / batería baja / señal degradada).
- `evaluar_estado_dispositivos_use_case.py` — severidad `ALTA→MODERADO` (INACTIVO), `MEDIA→LEVE` (resto).

`tipo_alerta='TECNICA'` y `origen_evento` (`HEARTBEAT` / `EVALUACION_PERIODICA`) se dejan como estaban
en el código: ahora son válidos gracias al DDL.

---

## Verificación (contra BD dev)

1. `SELECT count(*) … WHERE tipo_alerta='TECNICA'` → **0**, sin error (antes: `InvalidTextRepresentation`).
2. Cast de los 4 valores nuevos (`TECNICA`, `HEARTBEAT`, `EVALUACION_PERIODICA`, `CRITICO`) → aceptado.
3. Import de router + ambos use cases → sin errores.
4. `ConsultarAlertasUseCase(...).listar(tipo_alerta='TECNICA')` contra la sesión real →
   `total=0, items=0` (el endpoint responderá `{total:0, pagina:1, por_pagina:50, items:[]}`).

**Pendiente de prueba manual:** un `POST /iot/heartbeat` con `nivel_bateria_pct <= 10` debería ahora
generar una alerta técnica `CRITICO` visible en `GET /iot/alertas-tecnicas` (antes reventaba). No
probado en este fix por no tener credenciales de dispositivo a mano.

---

## Nota de documentación

`api_reference_m03_telemetria_iot.md` (línea ~217) todavía documenta el enum `origen_evento` como
`{EDGE, BACKEND, IA}`. Tras este cambio incluye además `HEARTBEAT` y `EVALUACION_PERIODICA`.
Actualizar si se busca exactitud.
