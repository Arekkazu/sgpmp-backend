# INC-M02-69-G44-01 — Mensaje de validación de `valor_medicion` en inglés

**RF:** RF-40 (CU06, TC-M02-082), pero la causa raíz es transversal a **todo**
el sistema porque vive en el handler global de validación, no en el DTO de
crecimiento.

## Qué reportó QA

`POST /activos-biologicos/{id}/eventos/crecimiento` con `valor_medicion: "abc"`
rechaza correctamente con `400 VAL_ENTRADA` sobre el campo `valor_medicion`,
pero el mensaje es el texto interno de Pydantic en inglés:

```
Input should be a valid decimal
```

Hallazgo no bloqueante (`TC-M02-G44` quedó APROBADO) — el comportamiento
funcional es correcto, es una observación de localización/consistencia.

## Causa raíz

`valor_medicion` está declarado `Decimal` en `RegistrarEventoCrecimientoDTO`.
Cuando el valor recibido no es convertible, Pydantic falla la **coerción de
tipo** antes de ejecutar los `@field_validator` propios del DTO — por eso el
validador `valor_positivo` (que sí redacta su mensaje en español) nunca llega
a ejecutarse, y el error que sale es el de Pydantic (`type: "decimal_parsing"`,
`msg: "Input should be a valid decimal"`), sin traducir.

El handler global `request_validation_error_handler`
(`src/shared/error_handlers.py`) — el único punto por el que pasan **todos**
los `RequestValidationError` de la API — usaba `error["msg"]` tal cual, sin
ningún mapeo de idioma. Esto no es específico de `valor_medicion` ni de
`RegistrarEventoCrecimientoDTO`: cualquier campo `Decimal`/`int`/`bool`/
`date`/... de cualquier DTO del sistema que reciba un valor no convertible
tiene el mismo problema.

### Defecto relacionado encontrado de paso (no reportado por QA)

Los mensajes de los `@field_validator` propios (los que SÍ están en español)
tampoco llegaban limpios: Pydantic antepone el prefijo fijo `"Value error, "`
a cualquier `ValueError` lanzado dentro de un validador, y el handler global
tampoco lo quitaba. Ejemplo real, antes del fix:

```json
{"field": "valor_medicion", "message": "Value error, El valor de medición debe ser mayor a cero."}
```

Pasó desapercibido porque el resto del mensaje ya estaba en español y el
prefijo en inglés no llamaba tanto la atención como el caso reportado por QA,
pero es la misma familia de defecto (mensaje de Pydantic sin traducir/limpiar)
en el mismo handler — se corrige junto con el fix principal.

## Fix

`src/shared/error_handlers.py`, `request_validation_error_handler`:

- Nueva función `_mensaje_legible(error)`:
  - Si `error["type"] == "value_error"` (validador propio de dominio): usa
    `error["ctx"]["error"]`, que Pydantic siempre incluye para este tipo y
    es el mensaje original **sin** el prefijo `"Value error, "`.
  - Para el resto de tipos, usa el diccionario `_MENSAJES_PYDANTIC_POR_TIPO`
    (cubre los fallos de coerción más comunes: `decimal_parsing`,
    `int_parsing`, `float_parsing`, `bool_parsing`, `date_parsing`,
    `datetime_parsing`, `missing`, `enum`/`literal_error`, etc.).
  - Si el tipo no está mapeado, cae al mensaje original de Pydantic (mismo
    comportamiento que antes del fix — no hay regresión para casos no
    cubiertos, solo mejora para los cubiertos).

El fix vive en el handler compartido a propósito: arreglar solo
`registrar_evento_crecimiento_dto.py` habría dejado el mismo defecto en
`dosis` (eventos sanitarios), `cantidad` (eventos productivos), y cualquier
otro campo numérico/fecha de cualquier DTO del sistema.

## Pruebas

`tests/shared/test_error_handlers_localizacion_pydantic.py` (nueva, 6 casos,
DTOs sintéticos + el DTO real de RF-40, sin BD):

- Decimal no numérico, entero no numérico, booleano inválido y campo
  faltante → mensaje en español, sin rastro del texto de Pydantic.
- Validador de dominio propio → mensaje limpio, sin el prefijo `"Value
  error, "`.
- Reproducción exacta de TC-M02-082 contra `RegistrarEventoCrecimientoDTO`
  con el payload literal del ticket.

Suite completa sin regresiones: 642 passed (636 previos + 6 nuevos), mismos 2
fallos preexistentes en `test_registrar_transferencia_use_case.py` (no
relacionados, confirmados fallando igual en `origin/dev` sin este cambio).

## Alcance

No se tocó ningún DTO — el fix es enteramente en el handler compartido de
errores, así que beneficia a todos los módulos, no solo a M02/RF-40.
