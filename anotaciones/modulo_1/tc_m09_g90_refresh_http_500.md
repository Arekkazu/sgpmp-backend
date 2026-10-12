# TC-M09-G90 — HTTP 500 en `POST /sesiones/refresh`

## Diagnóstico

La base oficial `sgpmp_dev` tenía desplegado el soporte estructural del refresh
token:

- valor `refresco` en `modulo1.enum_token_tipo`;
- `tokens.hash_valor` y `tokens.id_sesion`;
- `sesiones.id_token_refresco`;
- FKs, índices y trigger de token de un solo uso.

Sin embargo, no contenía los registros 23 y 24 de
`modulo1.tipos_eventos`. Estos se habían aplicado originalmente mediante SQL
manual y nunca se formalizaron en Alembic.

En una renovación válida, el caso de uso rotaba los tokens y luego intentaba
registrar `tipo_evento=23`. La FK de `modulo1.eventos.tipo_evento` rechazaba la
fila; la auditoría obligatoria propagaba el fallo y el rollback deshacía toda la
rotación. El resultado era HTTP 500 y la sesión no se renovaba.

El mismo gap afectaba la detección de reuso, que registra `tipo_evento=24`.

## Corrección

La migración `v5.3.0_sesiones_catalogo_eventos_refresh` agrega de forma
idempotente:

| ID | Nombre |
|---:|---|
| 23 | `REFRESH_TOKEN_ROTADO` |
| 24 | `REUSO_TOKEN_REFRESCO_DETECTADO` |

La revisión valida colisiones de ID/nombre, normaliza las descripciones e
incluye downgrade seguro cuando no existen eventos que referencien las filas.

## Contrato verificado

- refresh válido: HTTP 200, rotación de cookie y evento 23;
- cookie ausente: HTTP 401 `REFRESH_TOKEN_REQUERIDO`;
- cookie desconocida: HTTP 401 `REFRESH_TOKEN_INVALIDO`;
- refresh expirado: HTTP 410 `REFRESH_TOKEN_EXPIRADO`;
- refresh reutilizado: HTTP 401 `REFRESH_TOKEN_REUTILIZADO`, revocación de la
  sesión y evento 24.

Las pruebas de integración usan una transacción exterior; los commits del caso
de uso se convierten en savepoints y al finalizar se ejecuta rollback.

## Validación en `sgpmp_dev`

La migración y el endpoint se ejecutaron contra la base oficial dentro de una
transacción exterior:

```text
Tipos 23/24 antes:                 0
Tipos 23/24 durante la migración:  2
Refresh válido:                    200
Cookie rotada:                     sí
Evento 23 registrado:              1
Refresh reutilizado:               401 REFRESH_TOKEN_REUTILIZADO
Evento 24 registrado:              1
Sesión revocada por reuso:          sí
Refresh desconocido:               401 REFRESH_TOKEN_INVALIDO
Cookie ausente:                     401 REFRESH_TOKEN_REQUERIDO
Refresh expirado:                  410 REFRESH_TOKEN_EXPIRADO
Sesión cerrada por expiración:      sí
```

Después del rollback:

```text
Usuarios de prueba persistidos: 0
Tipos 23/24 persistidos:         0
```

La migración queda incluida en la rama, pero no fue desplegada sobre la base
oficial durante esta validación.
