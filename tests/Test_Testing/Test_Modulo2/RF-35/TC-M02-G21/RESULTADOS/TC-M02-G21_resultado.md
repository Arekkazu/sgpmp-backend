# TC-M02-G21 — Resultado de ejecución

## 🔴 ESTADO ACTUAL (2026-09-15): FAIL — misma regresión que TC-M02-G20

**No pasa.** Igual que en [TC-M02-G20](../../TC-M02-G20/RESULTADOS/TC-M02-G20_resultado.md): el setup (crear el activo INDIVIDUAL de prueba) responde `500` en vez de `201`, así que ninguno de los 2 sub-casos se pudo ejecutar. El PASS de más abajo ("Histórico — 2026-09-09") ya **no** refleja el estado actual del backend TEST.

| | |
|---|---|
| **Sub-casos** | TC-M02-035, TC-M02-036 — ambos bloqueados |
| **Dónde falla** | `POST /activos-biologicos` (setup, antes de poder probar RF-35) |
| **Qué responde** | `500 ERROR_INTERNO` en vez de `201` |
| **Causa raíz** | La misma que en TC-M02-G20, ya confirmada contra la BD de TEST: al backend le faltan las columnas `tipo_dato` y `es_obligatorio` en `modulo9.metricas_produccion` — la migración que las crea nunca se aplicó en el ambiente TEST. No es un bug nuevo ni distinto, es la misma falla de despliegue afectando cualquier endpoint que registre un activo. |
| **Cómo se arregla** | Aplicar la migración `alembic/versions/b92f7e1a4c63_rf16_metadatos_atributos_dinamicos.py` contra `sgpmp_test`. Una sola vez arregla TC-M02-G20, TC-M02-G21 y cualquier otro caso que dependa de crear un activo biológico. |

Respuesta exacta del `500` (idéntica a la de TC-M02-G20 — mismo `error_code`, mismo mensaje, distinto únicamente el timestamp):

```json
{
  "error_code": "ERROR_INTERNO",
  "message": "Ocurrió un error interno. Intenta de nuevo; si el problema persiste, contacta al equipo de soporte.",
  "fields": [],
  "timestamp": "2026-09-15T04:42:09.015150+00:00"
}
```

### Qué se probó y qué devolvió

| Paso | Antes (09-09) | Ahora (09-15) |
|---|---|---|
| Crear activo INDIVIDUAL de prueba (`id_especie=3`) | `201` | **`500 ERROR_INTERNO`** |
| 1a. `PATCH` solo con `id_especie` (sin campo editable) → debe rechazarse | `400` | `404` (el activo nunca se creó) |
| 1b. `PATCH` `id_especie` + campo válido → especie debe permanecer intacta | `200` | `404` |
| 2a. `PATCH` solo con `tipo_activo` → debe rechazarse | `400` | `404` |
| 2b. `PATCH` `tipo_activo` + campo válido → tipo debe permanecer INDIVIDUAL | `200` | `404` |
| Verificación final `GET` — especie y tipo siguen intactos | `200` | `404` |

No se pudo re-probar la inmutabilidad de `id_especie`/`tipo` en sí (el hallazgo de la ejecución del 09-09, ver abajo) porque el activo nunca llegó a existir.

### Evidencia

- [`newman-TC-M02-G21-FALLA-HOY-2026-09-15.html`](reevaluacion_2026-09-15/newman-TC-M02-G21-FALLA-HOY-2026-09-15.html) — reporte visual de Newman de HOY (ábrelo así, igual que el viejo `newman-TC-M02-G21.html`, pero este muestra el `500` en rojo).
- [`evidencia-newman-error500-al-crear-activo.json`](reevaluacion_2026-09-15/evidencia-newman-error500-al-crear-activo.json) — la misma corrida, en JSON crudo.

> ⚠️ **Ojo con `newman-TC-M02-G21.html` (sin fecha, en la carpeta de arriba):** ese es el reporte original del
> 2026-09-09 — todavía en verde, porque ese día sí pasó. No lo actualicé ni lo borré porque sigue siendo evidencia
> real de esa fecha. El reporte de HOY es el que está en `reevaluacion_2026-09-15/`, con "FALLA-HOY" en el nombre.

No se modificó la colección Postman ni ningún archivo fuera de `tests/` — solo se re-ejecutó la suite existente y se documentó el resultado.

---

## Histórico — ejecución 2026-09-09 (PASS, ya no vigente)

> Todo lo de aquí abajo describe cómo se comportaba el sistema el 2026-09-09. Se conserva como registro, pero **no es el estado actual** — ver la sección de arriba.

**Estado en esa fecha: PASS — 2/2 sub-casos (TC-M02-035, TC-M02-036), 16/16 assertions vía Postman/Newman contra el backend TEST desplegado.**

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

### Precondición

Se registró (RF-33) un activo INDIVIDUAL propio de la prueba con `id_especie=3` (activa en TEST) e infraestructura 6
(activa), tal como exige la precondición del caso:

```json
{
  "id_activo_biologico": 194, "id_especie": 3, "tipo": "INDIVIDUAL",
  "detalle_individual": { "raza": "Camaron QA-G21 original", "sexo": "Macho", "peso_inicial": "2.500" }
}
```

### TC-M02-035 — Rechazar cambio de especie tras el registro

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

### TC-M02-036 — Rechazar conversión de INDIVIDUAL a POBLACIONAL

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

### Verificación final

`GET /activos-biologicos/194` tras los 4 intentos anteriores confirma que **`id_especie=3` y `tipo=INDIVIDUAL`
siguen intactos**, es decir, ninguno de los 4 intentos (2 por sub-caso) logró alterar esos campos, sin importar si la
respuesta individual de cada intento fue 400 o 200.

### Evidencia (ejecución 2026-09-09)

- [Colección Postman](../TC-M02-G21.postman_collection.json)
- [Reporte Newman HTML](newman-TC-M02-G21.html) (htmlextra, headers/entorno omitidos)
- [Reporte Newman JSON](newman-TC-M02-G21.json)

### Hallazgo / observación de esa ejecución (no es un defecto, es una precisión sobre el propio caso de prueba)

El texto del caso dice "el sistema rechaza el cambio" / "el sistema rechaza la operación", que se lee naturalmente
como "responde con un código de error". **Eso solo ocurre si el intento de cambio va solo en el body** (variante a).
Si va acompañado de un campo editable legítimo (variante b, un escenario realista: un usuario que actualiza la raza
y por error o mala fe también manda `id_especie`), el sistema responde **200 OK** y el cambio prohibido simplemente
nunca se aplica — no hay ningún mensaje que le diga al cliente "tu intento de cambiar la especie fue ignorado".

Esto coincide con un gap ya documentado en la auditoría del módulo (`anotaciones/modulo_2/estado_M02.md`, sección
RF-35): la inmutabilidad de `tipo`/`id_especie` se cumple **estructuralmente** (ausencia del campo en el DTO +
trigger de DB `trg_activo_biologico_inmutabilidad` como segunda capa, no ejercitado por este endpoint porque nunca
intenta escribir esas columnas) pero sin ningún rechazo explícito al usuario cuando el campo llega mezclado con
datos válidos. No se marca como FAIL porque el resultado de negocio exigido por el RF —la especie y el tipo nunca
cambian— se cumple en el 100% de los intentos; se deja constancia para que el equipo decida si el contrato de API
debería advertir explícitamente (p. ej. 422 o un campo `advertencias` en la respuesta) cuando el cliente intenta
tocar un campo no editable, en vez de ignorarlo en silencio. Sigue sin corregirse — no hay commits posteriores al
09-09 que toquen `actualizar_activo_individual_use_case.py` en ese sentido.

### Nota sobre acceso a datos (de esa ejecución)

Esa verificación se hizo enteramente vía API (no se usó acceso a la base de datos PostgreSQL de TEST en esa fecha)
— coincide con el alcance declarado del propio caso ("API - Postman", "verificable por código/mensaje de respuesta
del API"). El acceso de solo lectura a la BD de TEST usado en la reevaluación de TC-M02-G20 (y reflejado arriba)
se obtuvo después, el 2026-09-15.
