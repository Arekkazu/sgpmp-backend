# TC-M02-G20 — Resultado de ejecución

**Estado general: PASS — 2/2 sub-casos (TC-M02-033, TC-M02-034), 16/16 assertions en Postman/Newman y 5/5 tests en Cypress, ambas suites ejecutadas de forma independiente contra el mismo backend TEST.**

| Campo | Valor |
|---|---|
| Caso de prueba | TC-M02-G20 (agrupa TC-M02-033 y TC-M02-034) |
| RF / CU | RF-35 / CU-02 — Gestión Individual de Activos Biológicos |
| Endpoints | `GET /activos-biologicos/{id_activo}` · `GET /activos-biologicos/{id_activo}/historial` · `PATCH /activos-biologicos/{id_activo}` · `GET /activos-biologicos/auditoria` |
| Entorno | TEST — `https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test` |
| Cuenta usada | `admin.test@sgpmp.com.co` (Administrador, `id_usuario=47`) |
| Fecha de ejecución | 2026-09-09, ~22:45 UTC |
| Herramientas | Newman 6.2.2 + htmlextra 1.23.1 · Cypress 14.5.4 (Electron 130 headless) |
| Activo de prueba (Postman) | `id_activo_biologico = 191`, identificador `QA-G20-1788993931486` |
| Activo de prueba (Cypress) | Activo independiente propio, identificador `QA-G20-CY-<timestamp>` (creado en el `before` del spec) |

## TC-M02-033 — Consultar activo individual existente

**PASS.** Antes de tocar nada se registró (RF-33) un activo INDIVIDUAL propio de la prueba —especie 4 "Cachama Blanca", infraestructura 6, ambas ya activas y validadas en TEST— para no depender de datos dejados por otros testers en el entorno compartido.

`GET /activos-biologicos/191` devolvió `200` con la ficha completa, incluyendo el detalle individual con los valores exactos con los que se creó el activo:

```json
{
  "id_activo_biologico": 191, "id_especie": 4, "tipo": "INDIVIDUAL",
  "identificador": "QA-G20-1788993931486", "nombre_estado": "ACTIVO",
  "detalle_individual": {
    "raza": "Cachama QA-G20 original", "sexo": "Macho",
    "fecha_nacimiento": "2025-01-15T00:00:00Z", "peso_inicial": "2.500"
  }
}
```

`GET /activos-biologicos/191/historial` respondió `200` con la estructura paginada esperada (`total_registros: 0` — el activo es nuevo y todavía no tiene eventos ni transferencias que listar; ver nota en "Hallazgos"). El endpoint está disponible y responde correctamente, que es lo que exige este sub-caso ("el sistema muestra... su historial disponible").

## TC-M02-034 — Actualizar atributos permitidos del individuo

**PASS.** `PATCH /activos-biologicos/191` con los 4 campos editables en valores nuevos, **más `tipo`, `id_especie` y `estado_activo`** (deliberadamente, para verificar en vivo que el RF los bloquea):

```json
// Request body
{
  "raza": "Cachama QA-G20 actualizada", "sexo": "Hembra",
  "fecha_nacimiento": "2025-02-20T00:00:00Z", "peso_inicial": 3.750,
  "tipo": "POBLACIONAL", "id_especie": 999, "estado_activo": "BAJA"
}
```

Respuesta `200`:

```json
{
  "id_activo_biologico": 191, "id_especie": 4, "tipo": "INDIVIDUAL",
  "nombre_estado": "ACTIVO",
  "detalle_individual": {
    "raza": "Cachama QA-G20 actualizada", "sexo": "Hembra",
    "fecha_nacimiento": "2025-02-20T00:00:00Z", "peso_inicial": "3.750"
  }
}
```

Los 4 campos editables cambiaron a los valores nuevos; `id_especie` (4, no 999), `tipo` (`INDIVIDUAL`, no `POBLACIONAL`) y `nombre_estado` (`ACTIVO`, no `BAJA`) **permanecieron intactos** pese a venir en el body — `ActualizarActivoIndividualDTO` no declara esos campos, así que Pydantic los descarta antes de que lleguen al caso de uso. Confirma en vivo el punto del RF: "no especie ni tipo".

Una segunda consulta (`GET /activos-biologicos/191`) inmediatamente después confirmó que los cambios **persistieron** con los mismos valores — no es solo el eco de la respuesta del PATCH.

Por último, `GET /activos-biologicos/auditoria?rf_origen=RF35&id_activo_biologico=191` devolvió `200` con 3 registros para este activo, incluyendo:

```json
{
  "id_bitacora": 449, "rf_origen": "RF35",
  "tipo_evento": "ACTIVO_INDIVIDUAL_ACTUALIZADO",
  "clasificacion_biologica": "GESTION_OPERATIVA", "resultado": "EXITOSO",
  "descripcion": "Detalle individual actualizado para activo 191",
  "id_usuario_responsable": 47
}
```

confirmando el punto del resultado esperado "se registra la operación en auditoría". Los otros dos registros (`ACTIVO_INDIVIDUAL_CONSULTA`) corresponden a las dos consultas GET de TC-M02-033/034, evidencia adicional de que cada acceso queda trazado.

## Cypress (redundancia independiente)

La misma secuencia se repitió en `tc-m02-g20-consulta-actualizacion.cy.js` (`cy.request`, sin mocks, mismo patrón que usan otros specs de este repo como `tests/Test_Testing/Test_Modulo1/RF-06/TC-M01-105/gestionar_cuenta_105.cy.js`), contra un **segundo activo independiente** creado en su propio `before`:

```
TC-M02-G20 - RF-35 Gestion Individual de Activos Biologicos (TC-M02-033 / TC-M02-034)
  √ TC-M02-033: Debe consultar el activo individual existente y mostrar su informacion actual
  √ TC-M02-033: El historial del activo debe estar disponible para consulta
  √ TC-M02-034: Debe actualizar raza, sexo, fecha_nacimiento y peso_inicial
  √ TC-M02-034: Los cambios deben persistir al recargar la ficha del activo
  √ TC-M02-034: La actualizacion debe quedar registrada en la bitacora de auditoria

5 passing (3s)
```

Reporte HTML: [`mochawesome-report/mochawesome.html`](mochawesome-report/mochawesome.html).

## Evidencia

- [Colección Postman](../TC-M02-G20.postman_collection.json)
- [Reporte Newman HTML](newman-TC-M02-G20.html) (htmlextra, headers/entorno omitidos)
- [Reporte Newman JSON](newman-TC-M02-G20.json)
- [Spec Cypress](../tc-m02-g20-consulta-actualizacion.cy.js)
- [Reporte Cypress](mochawesome-report/mochawesome.html)

## Hallazgos y observaciones

**No son defectos nuevos — confirman en vivo dos gaps ya documentados en `anotaciones/modulo_2/estado.md` para RF-35/RF-46, no algo introducido por esta prueba:**

1. **El historial del activo (`GET /{id_activo}/historial`, RF-46) no lista la creación ni la actualización de datos individuales.** Con `total_registros: 0` justo después de crear el activo y de actualizar sus atributos, la vista de historial no refleja ninguna de las dos operaciones — solo la bitácora de auditoría (RF-52) las captura. Coincide con el hallazgo ya documentado de que no existe un "Evento 0"/snapshot inicial, y de que `ACTIVO_INDIVIDUAL_ACTUALIZADO` no tiene mapeo hacia la categoría de historial de RF-46.
2. **"Se valida integridad de datos por especie" (texto del resultado esperado) no tiene ninguna validación observable en el código ni en la respuesta.** Se pudo actualizar `raza` a un valor arbitrario sin ninguna verificación contra un catálogo de razas por especie — no existe tal catálogo ni tal validación en `ActivoBiologico.actualizar_detalle_individual()` (`src/biological_assets/domain/entities/activo_biologico.py:348-372`). No se marca como FAIL porque el RF real (RF-35) no define ese catálogo ni ese código de error; se deja constancia para que el equipo confirme si la frase del caso de prueba corresponde a una regla pendiente de implementar o a una expectativa a ajustar en el propio caso de prueba.

Ninguno de los dos hallazgos afecta el resultado PASS de TC-M02-G20: ambos sub-casos verifican exactamente lo que el RF-35 exige (consulta correcta, actualización de los 4 campos permitidos, inmutabilidad de tipo/especie/estado, y registro en la bitácora RF-52).

## Nota sobre el entorno de ejecución

`node_modules/` (incluyendo Cypress) se instaló en este repo vía `npm ci` a partir del `package-lock.json` ya existente — no se modificó `package.json` ni `package-lock.json`. `node_modules/` está en `.gitignore`, por lo que no aparece como cambio en el control de versiones.

Durante la revisión final de `git status` se observó un archivo ya eliminado del árbol de trabajo, ajeno a este caso de prueba: `tests/Test_Testing/Test_Modulo9/RF-17/TC-M09-G24/RESULTADOS/screenshots/.../TC-M09-52 (failed).png`. No se tocó ni se investigó esa carpeta durante esta ejecución (TC-M02-G20 no depende de RF-17/M09); se deja constancia para que el responsable de ese caso lo revise.
