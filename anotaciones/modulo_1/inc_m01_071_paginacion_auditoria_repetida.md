# INC-M01-071 — paginación de auditoría inestable ante timestamps iguales

Fecha: 2026-09-08 · Rama: `fixes-report`

## Qué pasaba

`GET /auditoria/` (y la exportación) ordenaba los eventos **solo por
`fecha_evento`**:

```python
.order_by(modelo.fecha_evento.desc())
```

PostgreSQL no garantiza un orden determinista entre filas con el mismo valor de
ordenación. Cuando dos o más eventos compartían `fecha_evento` (muy frecuente en
cargas o registros automáticos que ocurren en el mismo instante), `OFFSET/LIMIT`
podía devolver la **misma fila en dos páginas distintas** o saltarse otra. El
test TC-M01-071 lo detectó como un `id_evento` repetido entre la página 1 y la 2.

## Qué se hizo

Se añadió `id_evento` como clave secundaria de orden (desempate total y estable):

```python
.order_by(modelo.fecha_evento.desc(), modelo.id_evento.desc())
```

en los dos puntos que recorren el conjunto paginado de `evento_repository.py`:

- `listar_eventos()` — paginación de la consulta.
- `_lotes()` — recorrido por lotes de la exportación (para que la exportación
  entregue las filas en el mismo orden que muestra la lista).

El propio repositorio ya usaba este desempate en el SQL del archivado
(`ORDER BY e.fecha_evento, e.id_evento`); era una omisión puntual de estos dos
métodos.

## Pruebas

- `tests/integration/test_rf10_paginacion_estable_integration.py` — inserta 6
  eventos con el **mismo** `fecha_evento` y verifica que las dos páginas no
  comparten ningún `id_evento` y cubren exactamente el conjunto. Se filtra por
  `tipo_evento` para aislar el evento que la propia consulta de auditoría
  registra (tipo 16) y que de otro modo contaminaría el conteo.
