# RF-10 — Categorías funcionales de eventos de auditoría

## Problema corregido

`SqlAlchemyEventoRepository.registrar()` guardaba literalmente
`categoria="AUTENTICACION"` para todos los eventos. Esto clasificaba como
autenticación las modificaciones de perfil, roles, permisos y estados de
cuenta, además de las consultas del historial y de usuarios.

## Clasificación canónica

| Categoría | Tipos de evento |
|---|---|
| `AUTENTICACION` | 1–8 y 20–24 |
| `MODIFICACION` | 9–15 |
| `CONSULTA` | 16–19 |

La relación vive en el value object
`domain/value_objects/evento_categoria.py`. Los casos de uso continúan
enviando únicamente `tipo_evento`; el repositorio deriva la categoría antes
de persistir. Un tipo nuevo sin clasificación provoca
`CATEGORIA_EVENTO_NO_DEFINIDA` y revierte la transacción, evitando volver a
ocultar el error mediante una categoría predeterminada.

## Eventos históricos

La tabla `modulo1.eventos` es inmutable por trigger. Por esa razón no se
actualizaron registros históricos que ya contienen `AUTENTICACION` de forma
incorrecta. Al leerlos, el repositorio expone la categoría canónica derivada
de `tipo_evento`; al filtrar `GET /auditoria/?categoria=...`, la consulta usa
los tipos asociados y no la columna histórica. Esto conserva la integridad y
permite consultar correctamente eventos anteriores y nuevos.

## Base de datos

No requiere DDL ni DML: las columnas y los tipos de evento ya existen. La
corrección es de dominio y persistencia. Los tipos 23 y 24 deben estar
sembrados en cada ambiente como parte de la implementación de refresh tokens,
pero no fueron creados ni modificados por este cambio.
