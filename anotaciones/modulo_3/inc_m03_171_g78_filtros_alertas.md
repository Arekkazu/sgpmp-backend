# INC-M03-171-G78 — El listado de alertas respondía 500 con un filtro fuera del catálogo (TC-M03-G78)

**RF:** RF-57 FA-09 (consulta de alertas con filtros). **Issue:** #750.
**Estado:** corregido y verificado con PostgreSQL real. El defecto se **reproduce** en `dev` y se corrige en
esta rama.

## Causa

En `GET /iot/alertas`, los filtros `estado`, `severidad`, `tipo_alerta` y `origen_evento` eran `str` libres
y llegaban tal cual al `WHERE`. Como las columnas son enums de PostgreSQL, el `CAST` de un valor
desconocido (`INEXISTENTE`, o `activa` en minúsculas) fallaba en la BD y salía como **500
ERROR_INTERNO**. `GET /iot/alertas-tecnicas` tenía el mismo problema con `estado` y `severidad`.

## Solución

Los filtros se validan en la frontera contra el **catálogo real de la BD**
(`src/telemetry/infrastructure/dto/filtros_alerta_dto.py`). Un valor fuera del catálogo responde
**400 `VAL_ENTRADA`** con el campo y los valores admitidos, igual que el resto de los filtros inválidos
(fechas, `id_sensor`, `id_activo_biologico`).

| Filtro | Valores admitidos (enums de `modulo3.alertas`) |
|---|---|
| `estado` | ACTIVA, EN_ATENCION, RESUELTA, DESCARTADA, VENCIDA, PENDIENTE_SINCRONIZACION |
| `severidad` | LEVE, MODERADO, CRITICO |
| `tipo_alerta` | ESTRES_TERMICO, SINDROME_RESPIRATORIO, RIESGO_HIDRICO, FIEBRE, INACTIVIDAD_ANORMAL, FALLO_AMBIENTAL, PREDICCION_PATOLOGIA, TORMENTA_DE_ALERTAS, TECNICA, CONVERSION_ALIMENTICIA, RIESGO_CONTAGIO |
| `origen_evento` | EDGE, BACKEND, IA, HEARTBEAT, EVALUACION_PERIODICA |

**Decisiones:**
- **Fuente del catálogo:** se valida contra los enums de la BD y no contra los de Python, porque estos se
  quedan cortos. `TipoAlerta` no tiene TECNICA ni CONVERSION_ALIMENTICIA, y `OrigenEventoAlerta` no tiene
  HEARTBEAT ni EVALUACION_PERIODICA; validar con ellos rechazaría valores válidos.
- **Valor vacío:** `?estado=` siempre respondió 200 sin filtrar, y **se conserva** para no romper a los
  clientes que mandan el parámetro vacío.
- **Mayúsculas:** se exigen exactas. Las minúsculas también daban 500, así que no se rompe nada que
  funcionara.

## Cambios

- `src/telemetry/infrastructure/dto/filtros_alerta_dto.py` (nuevo).
- `alerta_router.py`: los cuatro filtros de `GET /iot/alertas`.
- `infraestructura_iot_router.py`: `estado` y `severidad` de `GET /iot/alertas-tecnicas`.

## Evidencia

`tests/integration/test_inc_m03_171_g78_filtros_alertas.py`: routers reales, JWT de administrador y
PostgreSQL real.

| Prueba | Escenario | Rama | `dev` |
|---|---|---|---|
| `test_filtro_fuera_del_catalogo_es_400[filtro × INEXISTENTE/activa]` | Los 4 filtros con dos valores inválidos | 400 `VAL_ENTRADA` con el campo | **500** en los 8 casos |
| `test_valor_del_catalogo_responde_200[...]` | Valores válidos, incluidos TECNICA y HEARTBEAT | 200 | 200 |
| `test_filtro_vacio_sigue_siendo_sin_filtro[...]` | `?filtro=` | 200 | 200 |
| `test_todos_los_filtros_validos_a_la_vez` | Los 4 filtros juntos | 200 | — |
| `test_alertas_tecnicas_tambien_valida_sus_filtros[estado/severidad]` | `/iot/alertas-tecnicas` | 400 / 200 | — |

### Ejecución (2026-10-28)

- **BD efímera:** `pruebas_g78_test` en el PostgreSQL 18 local, con `alembic upgrade head` hasta
  `ebbb160365e5`, en un contenedor con la imagen del backend. Se borró al terminar.
- **Resultados:**

```
Integración (G78 + DEV-30, DEV-49)                          42 passed, 6 skipped
Misma prueba de G78 sobre dev                               8 × "assert 500 == 400"  ← reproduce el defecto
Suite completa (sin red): 2264 passed; mismos 4 failed / 25 errors preexistentes que la base
```
