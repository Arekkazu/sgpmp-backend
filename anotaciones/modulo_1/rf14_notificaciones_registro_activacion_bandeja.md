# RF-14 — Registro, activación y bandeja de notificaciones

## Decisiones

- El registro y la activación utilizan `NotificacionService` después del
  `commit` de su operación principal, igual que los demás flujos del módulo.
- Cada evento genera registros por EMAIL (`id=1`) e INTERNO (`id=2`) y pasa
  por la ventana anti-spam de cinco minutos.
- El HTML de activación con el token se entrega únicamente al adaptador de
  correo. `notificaciones.mensaje` guarda el mensaje general y nunca el token.
- El canal INTERNO queda con `estado_envio=enviado` cuando se persiste en la
  bandeja. Firebase es una entrega complementaria: que no haya dispositivo o
  que falle el push no invalida la notificación interna ya disponible.
- Las rutas no usan un permiso administrativo: `get_current_user` determina
  el propietario y el repositorio filtra siempre por `id_usuario` y canal 2.

## Endpoints

### `GET /notificaciones`

Parámetros:

- `pagina` (1 por defecto).
- `tamano` (20 por defecto, máximo 50).
- `solo_no_leidas` (`false` por defecto).

Retorna `total`, `no_leidas`, los datos de paginación y los items ordenados
por `fecha_envio DESC, id_notificacion DESC`.

### `PATCH /notificaciones/{id_notificacion}/leida`

Marca una notificación interna propia como leída. La operación es idempotente:
repetirla retorna `200`. Una notificación inexistente, de otro usuario o de un
canal distinto a INTERNO retorna `404 NOTIFICACION_NO_ENCONTRADA`, sin revelar
si el identificador pertenece a otra persona.

## Base de datos

La columna `modulo1.notificaciones.es_leido BOOLEAN NOT NULL` ya existía. No se
agregaron columnas ni se modificaron enums. El script
[`rf14_bandeja_notificaciones.sql`](./rf14_bandeja_notificaciones.sql) valida
el canal y la columna, y crea de forma idempotente un índice parcial para la
bandeja interna.

El 20/08/2026 se ejecutó y verificó el script en la base local
`pruebas-integrador`. No se modificaron filas ni columnas: únicamente se creó
el índice parcial `ix_notificaciones_bandeja_usuario`.

Aplicación desde `psql`:

```sql
\i 'anotaciones/modulo_1/rf14_bandeja_notificaciones.sql'
```

## Pruebas

- Unitarias: anti-spam, separación entre HTML sensible y mensaje persistido,
  aislamiento por propietario e idempotencia de lectura.
- Integración PostgreSQL: registro y activación generan ambos canales; listado
  excluye correo y notificaciones ajenas; filtro de no leídas; marcado propio;
  rechazo de una notificación ajena.
