# INC-M02-81-G61-03 — Baja PARCIAL de lote responde 400 VALOR_FUERA_DE_RANGO (no reproducible en `dev`)

**RF:** RF-45 — Registrar baja de activo biológico.
**Endpoint:** `POST /activos-biologicos/{id_activo}/eventos/baja`.

## Qué reportó QA

`POST .../eventos/baja` con `cantidad_afectada` menor a `cantidad_actual` (baja parcial que **no** cierra el lote) responde `400 VALOR_FUERA_DE_RANGO` de forma 100% reproducible en dos lotes distintos. QA descartó los triggers de cantidad/estado por lectura de esquema, pero no tuvo acceso a logs de servidor/BD para aislar el `DataError` exacto — el propio título del issue lo marca como "causa raíz sin confirmar".

## Investigación (Paso 0)

`VALOR_FUERA_DE_RANGO` es el código genérico que `src/shared/db_error_translator.py` asigna a cualquier `sqlalchemy.exc.DataError` (clase 22 de PostgreSQL — excepción de datos: overflow numérico, `invalid_text_representation`, etc.), no un mensaje específico de esta regla de negocio. Antes de inventar una causa, se hizo una revisión exhaustiva de todo lo que se ejecuta en una baja parcial de un lote poblacional:

1. **Código Python** (`RegistrarEventoBajaUseCase._execute`): sin diferencias de tipo entre baja parcial y total — mismo `EventoBaja(cantidad_afectada=int, ...)`, misma actualización de `detalle_poblacional` vía `Decimal`.
2. **Columnas involucradas** (`modulo2.detalles_activos_biologicos_poblacionales`, verificado contra `sgpmp_dev` real vía MCP, no solo el baseline): `cantidad_actual` es `integer`; `peso_promedio`, `biomasa_total`, `densidad` son `numeric` **sin precisión/escala** (`numeric_precision/scale = None`) — no hay overflow posible ahí, ni con divisiones que produzcan muchos decimales.
3. **Triggers en `eventos_bajas`/`detalles_activos_biologicos_poblacionales`** (listados vía `pg_trigger` contra `sgpmp_dev`): `trg_fn_baja_actualizar_cantidad_lote` (recalcula `cantidad_actual`/`biomasa_total`/`densidad` automáticamente al insertar en `eventos_bajas`), `trg_fn_baja_cantidad_valida` (valida cantidad positiva y no superior a existencia), `trg_fn_poblacional_cantidad_inmutable` (rechaza `cantidad_actual < 0`). Se leyó el texto completo de las 3 funciones (`pg_get_functiondef`): ninguna usa un `ERRCODE` de clase 22 (todas usan códigos custom `P0xxx`, que se traducen distinto, no como `DataError`). Nota aparte, no parte de este INC: `RegistrarEventoBajaUseCase` actualiza `detalle_poblacional` manualmente además del trigger automático — redundante pero no conflictivo, ambos cálculos parten del mismo valor original y llegan al mismo resultado.

## Reproducción directa contra `sgpmp_dev` (evidencia, no solo lectura de esquema)

Se ejecutó el use case real (mismo código, mismos repositorios, misma base) contra 3 escenarios, cada uno dentro de una transacción con `ROLLBACK` garantizado al final (nunca se dejó ningún cambio persistido):

| # | Escenario | Activo | Resultado |
|---|---|---|---|
| 1 | Baja parcial, `peso_promedio` configurado | 45 (cantidad_actual=500, baja de 50) | Éxito (`id_eventos=110`) |
| 2 | Baja parcial, `peso_promedio` NULL | 53 (cantidad_actual=500, baja de 50) | Éxito (`id_eventos=111`) |
| 3 | Baja total explícita (`cantidad_afectada = cantidad_actual`) | 45 (cantidad_actual=500, baja de 500) | Éxito (`id_eventos=112`), cierre automático del lote |

Ninguno de los tres reproduce `VALOR_FUERA_DE_RANGO` ni ningún otro error contra `dev`.

## Conclusión

No se pudo reproducir el defecto contra el código y la base de datos de `dev`. Mismo patrón que el resto de tickets de esta tanda de QA (`INC-M02-39-G27`, `INC-M02-40-G28`, `INC-M02-66-G90`, `INC-M02-79-G61-01`): todo apunta a que el entorno `sgpmp_test` corre una revisión de código y/o de triggers de base de datos desactualizada respecto a `dev` — posiblemente con un trigger equivalente a `trg_fn_baja_actualizar_cantidad_lote` en una versión anterior que sí produce un `DataError` genuino (ej. una versión con `::NUMERIC(p,s)` u otro cast estricto que en `dev` ya no existe). **No se puede confirmar la causa raíz exacta sin acceso a los logs de servidor/BD de `sgpmp_test`** — mismo bloqueo que QA ya señaló.

## Pruebas

No se agregó ningún test nuevo: no hay ningún cambio de código que probar (no se identificó ningún defecto en `dev`). La evidencia de esta investigación es la reproducción directa documentada arriba, ejecutada y revertida durante esta sesión.

## Fuera de alcance

- Diagnosticar `sgpmp_test` directamente (requiere acceso a sus logs de servidor/BD, que ni QA ni este repositorio tienen) — responsabilidad de quien administra ese entorno.
- Eliminar la actualización redundante de `detalle_poblacional` en `RegistrarEventoBajaUseCase` (ya que el trigger `trg_fn_baja_actualizar_cantidad_lote` la hace automáticamente) — es un hallazgo de diseño, no un defecto; no se toca aquí para no exceder el alcance de este INC.
