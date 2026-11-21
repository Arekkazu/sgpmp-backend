# INC-M03-172-G79 — Estado no catalogado: 422 TRANSICION_INVALIDA en vez de 400 (RF-57 CA-11)

**RF:** RF-57 CA-11 ("cuando se intente actualizar hacia un estado **no catalogado** (incluyendo el
término informal CERRADA), el sistema debe rechazar la petición con error HTTP **422
(TRANSICION_INVALIDA)**") y la nota de aclaración RFC-008. **Issue:** #751.
**Estado:** corregido y verificado con PostgreSQL real. El defecto se **reproduce** en `dev`.

## Causa

`ActualizarEstadoAlertaDTO` solo dejaba pasar al dominio una lista fija (EN_ATENCION, RESUELTA,
DESCARTADA, VENCIDA y CERRADA). Cualquier otro valor lo rechazaba Pydantic con **400 VAL_ENTRADA**:
`FINALIZADA` por el validador, la cadena vacía por `min_length=2` y `null` por el tipo. Solo CERRADA
llegaba al dominio y recibía el 422 que pide CA-11.

## Solución

- **DTO:** `nuevo_estado` sigue siendo **obligatorio** y **de texto**, pero ya no filtra contra una lista.
  Acepta `null` y lo normaliza a mayúsculas. Omitir el campo o mandar otro tipo (número, lista) sigue
  siendo **400 VAL_ENTRADA**, porque eso sí es un error de forma.
- **Caso de uso:** si el estado no pertenece al catálogo de RF-57 (`EstadoAlerta`), responde **422
  TRANSICION_INVALIDA** con `field: nuevo_estado` y la lista de destinos válidos. Pasa por el mismo camino
  que las demás transiciones inválidas: **la alerta no cambia** y el rechazo queda en la bitácora RF-63
  como `TRANSICION_ALERTA_RECHAZADA`, con el estado solicitado.
- **Alcance:** aplica en `PATCH /iot/alertas/{id}/estado` y en `PATCH /iot/alertas-tecnicas/{id}/estado`,
  que usan el mismo DTO.

| Valor de `nuevo_estado` | Antes | Ahora |
|---|---|---|
| `FINALIZADA`, `""`, `"   "`, `null` | 400 VAL_ENTRADA | **422 TRANSICION_INVALIDA**, con registro en la bitácora |
| `CERRADA` / `cerrada` | 422 | 422 (sin cambio) |
| Campo ausente, número, lista | 400 | 400 (sin cambio) |
| `EN_ATENCION`, `en_atencion` | 200 | 200 (sin cambio) |

## Pruebas existentes actualizadas

Afirmaban el comportamiento anterior, que es el que CA-11 corrige:
- `test_dev30_permisos_transiciones_alertas.py`:
  - `test_dto_conserva_validacion_estructural` ahora prueba la forma con `12` y con una lista.
  - Nuevo `test_dto_deja_el_estado_no_catalogado_al_dominio`.
  - `test_desconocido_conserva_http_400` pasa a `test_desconocido_es_422_transicion_invalida`, que sigue
    verificando que no se persiste nada.
- `test_dev49_alertas_historial_auditoria.py::test_400_no_se_registra_como_rechazo_403`: su objetivo es que
  un 400 no quede registrado como rechazo por permisos. Para conservarlo, ahora usa un cuerpo mal formado
  (`nuevo_estado: 12`).

## Evidencia

`tests/integration/test_inc_m03_172_g79_estado_no_catalogado.py`: routers reales, JWT de administrador y
PostgreSQL real.

| Prueba | Rama | `dev` |
|---|---|---|
| `test_estado_no_catalogado_es_422_transicion_invalida[FINALIZADA/vacío/None/espacios]` | 422, la alerta sigue ACTIVA, 1 rechazo en la bitácora | **400** (fallan los 4) |
| `…[CERRADA/cerrada]` | 422 | 422 |
| `test_cuerpo_mal_formado_sigue_siendo_400[{}, 5, lista]` | 400 | 400 |
| `test_transicion_valida_sigue_funcionando` | 200, EN_ATENCION | 200 |
| `test_alertas_tecnicas_aplica_la_misma_regla` | 422 | **400** |

### Ejecución (2026-10-28)

- **BD efímera:** `pruebas_g79_test` en el PostgreSQL 18 local, con `alembic upgrade head` hasta
  `ebbb160365e5`, en un contenedor con la imagen del backend. Se borró al terminar.
- **Resultados:**

```
Integración (G79 + DEV-30, DEV-49)                     32 passed, 6 skipped
Misma prueba de G79 sobre dev                          5 failed, 6 passed  ← reproduce el defecto
Unitarias DEV-30 + DEV-49 (actualizadas)               48 passed
Suite completa (sin red): 2265 passed; mismos 4 failed / 25 errors preexistentes que la base
```
