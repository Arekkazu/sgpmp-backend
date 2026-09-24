# INC-M02-95-G93 — Respuesta 400 exponía detalles internos de Pydantic

## Hallazgo

En `GET /activos-biologicos/{id_activo}/datos-consolidados`, un rango con
`fecha_inicio > fecha_fin` respondía correctamente `HTTP 400`, pero el mensaje
incluía la representación completa de `pydantic.ValidationError`: nombre del
DTO, tipo de error, input y enlace de documentación del framework.

## Causa raíz

`pydantic.ValidationError` hereda de `ValueError`. El router capturaba primero
`ValueError` y concatenaba `str(exc)`, por lo que la rama posterior destinada a
normalizar errores Pydantic nunca podía ejecutarse.

El mismo patrón estaba presente en las construcciones manuales de DTO de:

- listado de activos;
- consulta de bitácora;
- consulta de historial;
- consulta de indicadores;
- consulta de datos consolidados.

## Corrección

El router ahora:

- captura `pydantic.ValidationError` antes de `ValueError`;
- extrae únicamente el primer mensaje funcional del validador;
- nunca serializa `str(exc)` al consumidor;
- usa mensajes estables para fechas y fechas-hora mal formadas;
- conserva `HTTP 400`, `PARAMETROS_INVALIDOS` y `fields: []`.

Para TC-M02-156-A, la respuesta queda limitada a:

```json
{
  "error_code": "PARAMETROS_INVALIDOS",
  "message": "La fecha de inicio (2026-09-10) no puede ser posterior a la fecha de fin (2026-09-09).",
  "fields": []
}
```

## Alcance técnico

La validación ocurre antes de invocar el caso de uso y antes de cualquier acceso
a persistencia. La corrección no requiere migración, DDL, DML ni pruebas contra
la base oficial.

La cobertura HTTP verifica el caso reportado, fechas futuras y mal formadas,
tipo de dato inválido, las rutas de historial e indicadores, bitácora y listado.
También comprueba que la respuesta no contenga nombres de DTO, `validation
error`, `type=value_error`, `input_value` ni enlaces de Pydantic.
