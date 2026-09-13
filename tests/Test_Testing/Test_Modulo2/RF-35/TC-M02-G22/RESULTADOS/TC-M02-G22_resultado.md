# TC-M02-G22 — Resultado de ejecución

**Estado general: FAIL — 0/2 sub-casos cumplen el comportamiento exigido por el RF. 5/10 assertions PASS, 5/10 FAIL, vía Postman/Newman contra el backend TEST desplegado.** Los 5 FAIL son hallazgos reales, no errores de la prueba — ver detalle abajo.

> **Nota de corrección:** la primera ejecución de esta colección tenía un defecto propio — el valor de prueba
> enviado en `raza` durante TC-M02-038 contenía literalmente la palabra "pendiente" ("... pese a estado
> pendiente"), lo que hacía que la assertion que busca esa palabra en la respuesta diera un falso PASS al
> encontrarla en el eco de los propios datos enviados, no en un mensaje de error real del sistema (la respuesta fue
> 200, sin ningún mensaje de error). Se corrigió el valor de prueba y se re-ejecutó; el resultado correcto (5/10,
> no el 6/10 inicial) es el que se documenta en esta versión.

| Campo | Valor |
|---|---|
| Caso de prueba | TC-M02-G22 (agrupa TC-M02-037 y TC-M02-038) |
| RF / CU | RF-35 / CU-02 — Gestión Individual de Activos Biológicos |
| Endpoints | `PATCH /activos-biologicos/{id_activo}` · `POST /activos-biologicos/{id_activo}/eventos/sanitario` (bloqueado, ver `NOTA_BLOQUEO.md`) · `PATCH /activos-biologicos/{id_activo}/estado` (workaround) · `GET /activos-biologicos/{id_activo}` |
| Entorno | TEST — `https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test` |
| Cuenta usada | `admin.test@sgpmp.com.co` (Administrador, `id_usuario=47`) |
| Fecha de ejecución | 2026-09-09, ~23:06 UTC |
| Herramientas | Newman 6.2.2 + htmlextra 1.23.1 |
| Activo de prueba | `id_activo_biologico = 198`, identificador `QA-G22-1788995207698`, `id_especie=3` |

## TC-M02-037 — Rechazar cambio de estado directo desde RF-35

**FAIL en las dos variantes.**

**(a) Solo `estado_activo` en el body** — `PATCH {"estado_activo": "BAJA"}`:

```json
// HTTP 400 — el código coincide con lo esperado, pero el mensaje NO
{
  "error_code": "VAL_ENTRADA",
  "message": "Errores de validacion en la solicitud",
  "fields": [{ "field": null, "message": "Value error, Al menos un campo debe estar presente para actualizar." }]
}
```

El RF exige el mensaje *"El cambio de estado debe realizarse mediante el módulo de gestión de estados (RF-44)"*.
`ActualizarActivoIndividualDTO` no declara `estado_activo`, así que el 400 real ocurre por una razón completamente
distinta (el validador genérico "al menos un campo"), no porque el sistema haya detectado y rechazado
específicamente un intento de tocar el estado. Un cliente que reciba este mensaje no tiene ninguna pista de que
debería usar RF-44.

**(b) `estado_activo` combinado con un campo editable válido (`raza`)** — `PATCH {"estado_activo": "BAJA", "raza": "Camaron QA-G22 raza cambiada"}`:

```json
// HTTP 200 — el RF exige 400 aqui tambien
{
  "id_activo_biologico": 198, "id_estado": 1, "nombre_estado": "ACTIVO",
  "detalle_individual": { "raza": "Camaron QA-G22 raza cambiada", ... }
}
```

**Esta es la variante más importante**: el `estado_activo` nunca cambia (correcto, `id_estado` sigue en 1/ACTIVO),
pero la solicitud se acepta con **200 OK**, sin ningún rechazo ni advertencia. Un cliente que intente cambiar el
estado por error desde este endpoint no recibe ninguna señal de que lo está haciendo mal — el campo simplemente se
ignora.

## TC-M02-038 — Bloquear operación si hay eventos pendientes

**FAIL**, y con un bloqueo adicional en la precondición (ver `NOTA_BLOQUEO.md`).

Se intentó primero la precondición literal: registrar un evento sanitario `CONTROL_PREVENTIVO` con
`solicitar_estado=EN_TRATAMIENTO` vía `POST /activos-biologicos/198/eventos/sanitario`. Resultado:

```json
// HTTP 500 — defecto independiente de RF-41, no de RF-35
{"error_code":"ERROR_INTERNO","message":"Error inesperado en base de datos","fields":[]}
```

Reproducido igual con `DIAGNOSTICO` y con `CONTROL_PREVENTIVO` sin `solicitar_estado`, en activos distintos — ver
`NOTA_BLOQUEO.md` para el detalle completo. Esto bloquea la vía directa de crear "eventos sanitarios pendientes".

**Workaround usado**: `PATCH /activos-biologicos/198/estado` (RF-44, no afectado por el bloqueo) para dejar el
activo en `EN_TRATAMIENTO`:

```json
// HTTP 200
{"id_activo_biologico":198,"estado_anterior":1,"estado_nuevo":3, "historial": {"modulo_origen":"MANUAL", ...}}
```

Con el activo confirmado en `EN_TRATAMIENTO` (`GET` intermedio, `nombre_estado: "EN_TRATAMIENTO"`), se intentó una
actualización normal y legítima:

```json
// PATCH {"raza": "Camaron QA-G22 actualizado con proceso abierto"}
// HTTP 200 — el RF exige 409 aqui, y ademas ningun mensaje de la respuesta
// menciona "pendiente" ni ningun otro aviso sobre el estado abierto
{
  "id_activo_biologico": 198, "id_estado": 3, "nombre_estado": "EN_TRATAMIENTO",
  "detalle_individual": { "raza": "Camaron QA-G22 actualizado con proceso abierto", ... }
}
```

La actualización se acepta sin ninguna restricción, mientras el activo tiene un proceso sanitario abierto sin
resolver. Confirma en vivo el gap ya documentado por lectura de código: no existe ninguna validación de "eventos
pendientes" en `ActualizarActivoIndividualUseCase` ni en `ActivoBiologico.actualizar_detalle_individual()` — y una
búsqueda exhaustiva (`grep -ri "pendiente" src/biological_assets`) no encontró ningún código relacionado con ese
concepto en todo el módulo.

## Verificación final

`GET /activos-biologicos/198` confirma el estado final consistente con todo lo anterior: `id_estado=3`
(`EN_TRATAMIENTO`, por el workaround de RF-44) y `raza` con el último valor aceptado — nada de esto contradice lo
observado en cada paso.

## Resumen de assertions (Newman)

| # | Assertion | Resultado |
|---|---|---|
| 1 | Login exitoso (200) | PASS |
| 2 | Se crea el activo INDIVIDUAL de prueba (201) | PASS |
| 3 | TC-M02-037a: 400 BAD REQUEST | PASS (código correcto) |
| 4 | TC-M02-037a: mensaje menciona RF-44/"gestión de estados" | **FAIL** — mensaje genérico, no el específico del RF |
| 5 | TC-M02-037b: 400 BAD REQUEST | **FAIL** — obtuvo 200 |
| 6 | Precondición RF-41: evento sanitario se registra (201) | **FAIL** — obtuvo 500 (bloqueo, ver NOTA_BLOQUEO.md) |
| 7 | Workaround RF-44: cambio a EN_TRATAMIENTO (200) | PASS |
| 8 | TC-M02-038: 409 CONFLICT | **FAIL** — obtuvo 200 |
| 9 | TC-M02-038: mensaje menciona "pendiente" | **FAIL** — la respuesta (200, sin error) no menciona "pendiente" en ningún lado |
| 10 | Verificación final: GET responde 200 | PASS |

**Total: 5 PASS / 5 FAIL de 10 assertions.**

## Evidencia

- [Colección Postman](../TC-M02-G22.postman_collection.json)
- [Nota de bloqueo — RF-41](../NOTA_BLOQUEO.md)
- [Reporte Newman HTML](newman-TC-M02-G22.html) (htmlextra, headers/entorno omitidos)
- [Reporte Newman JSON](newman-TC-M02-G22.json)

## Conclusión

TC-M02-G22 confirma en vivo, contra el TEST real, dos gaps que ya estaban señalados por lectura de código en la
auditoría del módulo:

1. **RF-35 no tiene ningún mecanismo para detectar y rechazar explícitamente un intento de cambiar `estado_activo`
   por este endpoint** — el campo se ignora estructuralmente (correcto en cuanto al dato: el estado nunca cambia),
   pero sin ningún aviso al cliente ni el código/mensaje que el RF documenta.
2. **RF-35 no valida "eventos pendientes sin cerrar" antes de aceptar una edición**, tal como el RF lo exige en su
   Proceso — cualquier actualización se acepta sin importar el estado operativo del activo.

Ninguno de los dos es un fallo de esta sesión de pruebas: son gaps reales del código actual, ahora verificados con
evidencia de ejecución en vivo en lugar de solo por lectura de código. Se recomienda al equipo de desarrollo tratar
esto como hallazgo priorizable para RF-35, y revisar por separado el bloqueo de RF-41 documentado en
`NOTA_BLOQUEO.md` antes de escribir los casos de prueba de ese RF.
