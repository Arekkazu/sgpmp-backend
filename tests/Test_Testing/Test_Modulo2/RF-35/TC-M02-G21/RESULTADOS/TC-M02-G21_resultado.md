# TC-M02-G21 — Resultado de ejecución

**Estado general: PASS — 2/2 sub-casos (TC-M02-035, TC-M02-036), 16/16 assertions vía Postman/Newman contra el backend TEST desplegado.**

| Campo | Valor |
|---|---|
| Caso de prueba | TC-M02-G21 (agrupa TC-M02-035 y TC-M02-036) |
| RF / CU | RF-35 / CU-02 — Gestión Individual de Activos Biológicos |
| Endpoints | `PATCH /activos-biologicos/{id_activo}` · `GET /activos-biologicos/{id_activo}` |
| Entorno | TEST — `https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test` |
| Cuenta usada | `admin.test@sgpmp.com.co` (Administrador, `id_usuario=47`) |
| Fecha de ejecución | 2026-09-09, ~22:55 UTC |
| Herramientas | Newman 6.2.2 + htmlextra 1.23.1 |
| Activo de prueba | `id_activo_biologico = 194`, identificador `QA-G21-1788994538251`, `id_especie=3` |

## Precondición

Se registró (RF-33) un activo INDIVIDUAL propio de la prueba con `id_especie=3` (activa en TEST) e infraestructura 6
(activa), tal como exige la precondición del caso:

```json
{
  "id_activo_biologico": 194, "id_especie": 3, "tipo": "INDIVIDUAL",
  "detalle_individual": { "raza": "Camaron QA-G21 original", "sexo": "Macho", "peso_inicial": "2.500" }
}
```

## TC-M02-035 — Rechazar cambio de especie tras el registro

**PASS**, en sus dos variantes:

**(a) Solo `id_especie` en el body, sin ningún campo editable real** — `PATCH {"id_especie": 7}`:

```json
// HTTP 400
{
  "error_code": "VAL_ENTRADA",
  "message": "Errores de validacion en la solicitud",
  "fields": [{ "field": null, "message": "Value error, Al menos un campo debe estar presente para actualizar." }]
}
```

La solicitud se **rechaza explícitamente** — no hay forma de "solo cambiar la especie" por este endpoint, porque el
DTO exige al menos un campo de los que sí son editables.

**(b) `id_especie` combinado con un campo editable válido (`raza`)** — `PATCH {"id_especie": 4, "raza": "Camaron QA-G21 raza cambiada"}`:

```json
// HTTP 200
{
  "id_activo_biologico": 194, "id_especie": 3,
  "detalle_individual": { "raza": "Camaron QA-G21 raza cambiada", ... }
}
```

La solicitud se acepta (porque `raza` sí es válida), pero **`id_especie` sigue siendo 3, no 4** — el intento de
cambio de especie se ignora silenciosamente. El resultado de negocio ("la especie permanece inmutable") se cumple
igual que en la variante (a), aunque el código HTTP sea distinto.

## TC-M02-036 — Rechazar conversión de INDIVIDUAL a POBLACIONAL

**PASS**, mismo patrón:

**(a) Solo `tipo_activo` en el body** — `PATCH {"tipo_activo": "POBLACIONAL"}` → **HTTP 400**, mismo rechazo
`VAL_ENTRADA` por ausencia de un campo editable real.

**(b) `tipo_activo` combinado con `peso_inicial` válido** — `PATCH {"tipo_activo": "POBLACIONAL", "peso_inicial": 9.999}`:

```json
// HTTP 200
{
  "id_activo_biologico": 194, "tipo": "INDIVIDUAL",
  "detalle_individual": { "peso_inicial": "9.999", ... },
  "detalle_poblacional": null
}
```

`peso_inicial` sí se actualizó (confirma que el PATCH se procesó de verdad, no que falló completo), pero **`tipo`
sigue siendo `INDIVIDUAL`** y `detalle_poblacional` sigue `null` — el activo nunca se convierte en lote.

## Verificación final

`GET /activos-biologicos/194` tras los 4 intentos anteriores confirma que **`id_especie=3` y `tipo=INDIVIDUAL`
siguen intactos**, es decir, ninguno de los 4 intentos (2 por sub-caso) logró alterar esos campos, sin importar si la
respuesta individual de cada intento fue 400 o 200.

## Evidencia

- [Colección Postman](../TC-M02-G21.postman_collection.json)
- [Reporte Newman HTML](newman-TC-M02-G21.html) (htmlextra, headers/entorno omitidos)
- [Reporte Newman JSON](newman-TC-M02-G21.json)

## Hallazgo / observación (no es un defecto, es una precisión sobre el propio caso de prueba)

El texto del caso dice "el sistema rechaza el cambio" / "el sistema rechaza la operación", que se lee naturalmente
como "responde con un código de error". **Eso solo ocurre si el intento de cambio va solo en el body** (variante a).
Si va acompañado de un campo editable legítimo (variante b, un escenario realista: un usuario que actualiza la raza
y por error o mala fe también manda `id_especie`), el sistema responde **200 OK** y el cambio prohibido simplemente
nunca se aplica — no hay ningún mensaje que le diga al cliente "tu intento de cambiar la especie fue ignorado".

Esto coincide con un gap ya documentado en la auditoría del módulo (`anotaciones/modulo_2/estado.md`, sección RF-35):
la inmutabilidad de `tipo`/`id_especie` se cumple **estructuralmente** (ausencia del campo en el DTO + trigger de DB
`trg_activo_biologico_inmutabilidad` como segunda capa, no ejercitado por este endpoint porque nunca intenta escribir
esas columnas) pero sin ningún rechazo explícito al usuario cuando el campo llega mezclado con datos válidos. No se
marca como FAIL porque el resultado de negocio exigido por el RF —la especie y el tipo nunca cambian— se cumple en
el 100% de los intentos; se deja constancia para que el equipo decida si el contrato de API debería advertir
explícitamente (p. ej. 422 o un campo `advertencias` en la respuesta) cuando el cliente intenta tocar un campo no
editable, en vez de ignorarlo en silencio.

## Nota sobre acceso a datos

Esta verificación se hizo enteramente vía API (no hay acceso a la base de datos PostgreSQL de TEST desde este
entorno de ejecución) — coincide con el alcance declarado del propio caso ("API - Postman", "verificable por
código/mensaje de respuesta del API").
