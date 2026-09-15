# TC-M02-G20 — Resultado de ejecución

## 🔴 ESTADO ACTUAL (2026-09-15): FAIL — regresión confirmada

**No pasa.** El caso pasó la primera vez que se ejecutó (2026-09-09), pero al reevaluarlo hoy el backend de TEST está roto: el primer paso (crear el activo de prueba) responde `500` y todo lo demás no se puede probar porque depende de ese activo. La sección de más abajo, "Histórico — ejecución 2026-09-09 (PASS)", ya **no** refleja el estado real del sistema — se conserva solo como referencia de que en algún momento sí funcionó.

| | |
|---|---|
| **Sub-casos** | TC-M02-033, TC-M02-034 — ambos bloqueados |
| **Dónde falla** | `POST /activos-biologicos` (paso de setup, antes de poder probar RF-35) |
| **Qué responde** | `500 ERROR_INTERNO` en vez de `201` |
| **Reproducido con** | Postman/Newman **y** Cypress, por separado, mismo resultado en ambas |
| **Causa raíz** | **Confirmada.** El código que ya está en TEST espera 2 columnas nuevas (`tipo_dato`, `es_obligatorio`) en `modulo9.metricas_produccion`, pero la migración que las crea nunca se corrió en esa base de datos. Es un despliegue incompleto, no un bug de código — ver detalle abajo. |
| **Cómo se arregla** | Aplicar la migración `alembic/versions/b92f7e1a4c63_rf16_metadatos_atributos_dinamicos.py` contra la base de datos `sgpmp_test`. No requiere cambios de código. |

### Qué se probó y qué devolvió

| Paso | Antes (09-09) | Ahora (09-15) |
|---|---|---|
| Crear activo INDIVIDUAL de prueba | `201` | **`500 ERROR_INTERNO`** |
| `GET /activos-biologicos/{id}` | `200` | `404` (el activo nunca se creó) |
| `GET /{id}/historial` | `200` | `400` |
| `PATCH /{id}` (actualizar) | `200` | `404` |
| `GET /{id}` posterior (verificar que persiste) | `200` | `404` |
| `GET /activos-biologicos/auditoria` | `200`, evento presente | `400` |

Respuesta exacta del `500`:

```json
{
  "error_code": "ERROR_INTERNO",
  "message": "Ocurrió un error interno. Intenta de nuevo; si el problema persiste, contacta al equipo de soporte.",
  "fields": [],
  "timestamp": "2026-09-15T03:25:10.888873+00:00"
}
```

### Causa raíz, explicada paso a paso

1. El 10 de septiembre se subió un cambio de código: cada vez que se crea un activo biológico, el backend ahora también consulta la tabla `modulo9.metricas_produccion` para validar sus atributos, usando dos columnas nuevas: `tipo_dato` y `es_obligatorio`.
2. Ese mismo cambio incluía la migración que agrega esas columnas a la base de datos (`b92f7e1a4c63`).
3. El código se desplegó a TEST, pero la migración no se aplicó ahí.
4. Se confirmó conectándose de solo lectura a la base de datos de TEST (`sgpmp_test`) y corriendo:

   ```sql
   SELECT column_name FROM information_schema.columns
   WHERE table_schema = 'modulo9' AND table_name = 'metricas_produccion'
     AND column_name IN ('tipo_dato', 'es_obligatorio');
   -- Resultado: 0 filas → las columnas no existen
   ```
5. Como el código pide columnas que no están ahí, PostgreSQL responde con un error, y el backend lo deja pasar como un `500` genérico en lugar de un mensaje claro.

Código involucrado (para quien vaya a corregirlo):
- `src/biological_assets/application/use_cases/registro/registrar_activo_use_case.py:187-193`
- `src/biological_assets/infrastructure/adapters/parametros_especie_m09_adapter.py:35-46`

*(No se pudo revisar `alembic_version` para saber exactamente cuántas migraciones quedaron pendientes — el usuario de solo lectura usado no tiene permiso sobre esa tabla — pero no hace falta: la ausencia de las columnas ya confirma el problema.)*

### Sobre los 2 hallazgos que ya existían desde el 09-09

Estos no son parte de la causa del `500` — son observaciones aparte, que siguen sin corregirse (verificado por revisión de código, ya que el flujo real no se pudo re-probar):

1. **El historial del activo (RF-46) no muestra ni la creación ni la actualización del individuo.** Sigue así; el único cambio reciente en ese código (10-sep) solo agrega un mensaje cuando se filtra y no hay resultados, no soluciona esto.
2. **No existe validación de "razas por especie"** al actualizar un activo, aunque el caso de prueba lo espera. Sin cambios desde el 09-09.

### Evidencia

- [`newman-TC-M02-G20-FALLA-HOY-2026-09-15.html`](reevaluacion_2026-09-15/newman-TC-M02-G20-FALLA-HOY-2026-09-15.html) — reporte visual de Newman de HOY (ábrelo así, igual que el viejo `newman-TC-M02-G20.html`, pero este muestra el `500` en rojo).
- [`evidencia-newman-error500-al-crear-activo.json`](reevaluacion_2026-09-15/evidencia-newman-error500-al-crear-activo.json) — la misma corrida, en JSON crudo.
- [`evidencia-cypress-error500-al-crear-activo.png`](reevaluacion_2026-09-15/evidencia-cypress-error500-al-crear-activo.png) — captura de Cypress con el mismo `500`.

> ⚠️ **Ojo con `newman-TC-M02-G20.html` (sin fecha, en la carpeta de arriba):** ese es el reporte original del
> 2026-09-09 — todavía en verde, porque ese día sí pasó. No lo actualicé ni lo borré porque sigue siendo evidencia
> real de esa fecha. El reporte de HOY es el que está en `reevaluacion_2026-09-15/`, con "FALLA-HOY" en el nombre.

No se modificó la colección Postman, el spec Cypress, ni ningún archivo fuera de `tests/` — solo se re-ejecutaron las suites existentes y se documentó el resultado.

---

## Histórico — ejecución 2026-09-09 (PASS, ya no vigente)

> Todo lo de aquí abajo describe cómo se comportaba el sistema el 2026-09-09. Se conserva como registro, pero **no es el estado actual** — ver la sección de arriba.

**Estado en esa fecha: PASS — 2/2 sub-casos (TC-M02-033, TC-M02-034), 16/16 assertions en Postman/Newman y 5/5 tests en Cypress, ambas suites ejecutadas de forma independiente contra el mismo backend TEST.**

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

### TC-M02-033 — Consultar activo individual existente

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

### TC-M02-034 — Actualizar atributos permitidos del individuo

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

### Cypress (redundancia independiente)

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

Reporte HTML: [`reporte-cypress-2026-09-09.html`](reporte-cypress-2026-09-09/reporte-cypress-2026-09-09.html).

### Evidencia (ejecución 2026-09-09)

- [Colección Postman](../TC-M02-G20.postman_collection.json)
- [Reporte Newman HTML](newman-TC-M02-G20.html) (htmlextra, headers/entorno omitidos)
- [Reporte Newman JSON](newman-TC-M02-G20.json)
- [Spec Cypress](../tc-m02-g20-consulta-actualizacion.cy.js)
- [Reporte Cypress](reporte-cypress-2026-09-09/reporte-cypress-2026-09-09.html)

### Hallazgos y observaciones (de la ejecución 2026-09-09)

**No son defectos nuevos — confirman en vivo dos gaps ya documentados en `anotaciones/modulo_2/estado_M02.md` para RF-35/RF-46, no algo introducido por esta prueba:**

1. **El historial del activo (`GET /{id_activo}/historial`, RF-46) no lista la creación ni la actualización de datos individuales.** Con `total_registros: 0` justo después de crear el activo y de actualizar sus atributos, la vista de historial no refleja ninguna de las dos operaciones — solo la bitácora de auditoría (RF-52) las captura. Coincide con el hallazgo ya documentado de que no existe un "Evento 0"/snapshot inicial, y de que `ACTIVO_INDIVIDUAL_ACTUALIZADO` no tiene mapeo hacia la categoría de historial de RF-46.
2. **"Se valida integridad de datos por especie" (texto del resultado esperado) no tiene ninguna validación observable en el código ni en la respuesta.** Se pudo actualizar `raza` a un valor arbitrario sin ninguna verificación contra un catálogo de razas por especie — no existe tal catálogo ni tal validación en `ActivoBiologico.actualizar_detalle_individual()` (`src/biological_assets/domain/entities/activo_biologico.py:348-372`). No se marca como FAIL porque el RF real (RF-35) no define ese catálogo ni ese código de error; se deja constancia para que el equipo confirme si la frase del caso de prueba corresponde a una regla pendiente de implementar o a una expectativa a ajustar en el propio caso de prueba.

Ninguno de los dos hallazgos afectaba el resultado PASS de esa fecha: ambos sub-casos verificaban exactamente lo que el RF-35 exige (consulta correcta, actualización de los 4 campos permitidos, inmutabilidad de tipo/especie/estado, y registro en la bitácora RF-52).

### Nota sobre el entorno de esa ejecución

`node_modules/` (incluyendo Cypress) se instaló en este repo vía `npm ci` a partir del `package-lock.json` ya existente — no se modificó `package.json` ni `package-lock.json`. `node_modules/` está en `.gitignore`, por lo que no aparece como cambio en el control de versiones.

Durante la revisión final de `git status` se observó un archivo ya eliminado del árbol de trabajo, ajeno a este caso de prueba: `tests/Test_Testing/Test_Modulo9/RF-17/TC-M09-G24/RESULTADOS/screenshots/.../TC-M09-52 (failed).png`. No se tocó ni se investigó esa carpeta durante esta ejecución (TC-M02-G20 no depende de RF-17/M09); se deja constancia para que el responsable de ese caso lo revise.
