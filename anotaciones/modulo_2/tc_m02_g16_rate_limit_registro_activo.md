# TC-M02-G16 (issue #331) — Rate limiting ausente en POST /activos-biologicos

**RF:** RF-33 — Registro de Activos Biológicos.
**Endpoint:** `POST /activos-biologicos`.

## Qué reportó QA

Ráfaga controlada de 101 solicitudes en ~41.5s (payload mínimo inválido `{}`
para no crear activos) contra `POST /activos-biologicos`: 101 respuestas
HTTP 400 (rechazadas por validación de Pydantic), 0 respuestas HTTP 429. Sin
mecanismo de rate limiting, un cliente puede superar el umbral de 100
solicitudes/minuto sin que el sistema aplique ningún control.

## Causa raíz

El endpoint no tenía ningún limitador conectado. El mecanismo ya existe y ya
se usa dos veces en el mismo módulo (mismo estilo que `require_permission`):
`src/shared/rate_limit.py::rate_limit(max_llamadas, ventana_segundos,
alcance=...)`, reutilizado tal cual — no se crea nada nuevo. Ejemplo ya en
este mismo router: `_LIMITE_DATOS_CONSOLIDADOS` (INC-M02-96-G94), también
100/60.

## Fix

```python
_LIMITE_REGISTRO_ACTIVO = rate_limit(100, 60, alcance="activos_registro")
```
agregado a `dependencies=[...]` del `POST ''` (`activo_biologico_router.py`),
junto al `require_permission_m02` existente. `429` agregado a `responses` del
endpoint (documentación OpenAPI).

## Caveats (heredados del propio `rate_limit.py`, no introducidos aquí)

- En memoria, por proceso — no distribuido entre workers/réplicas. No hay
  evidencia de que el deploy actual use >1 worker; si eso cambia, migrar a
  Redis INCR/EXPIRE.
- Por usuario autenticado, no por IP anónima — el endpoint ya exige auth
  (precondición de RF-33), así que no hay tráfico anónimo que proteger.

## Verificación

- Nuevo `tests/biological_assets/test_tc_m02_g16_rate_limit_registro_activo.py`
  (mismo patrón que `test_inc_m02_96_g94_rate_limit_datos_consolidados.py`):
  confirma que la ruta declara el limitador y que corta con
  `TooManyRequestsError`/429 tras 100 llamadas.
- Reproducción manual del escenario exacto de QA (TestClient, mismo usuario,
  101 solicitudes con payload `{}`): las primeras 100 responden 400
  (validación), la 101 responde 429 `LIMITE_TASA_EXCEDIDO`.
