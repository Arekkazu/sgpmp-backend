# TC-M02-G21 — Restricciones de inmutabilidad del activo individual (especie y tipo de activo)

**CU-02 · RF-35 — Gestión Individual de Activos Biológicos.**

| Campo | Valor |
|---|---|
| Sub-casos | (TC-M02-035) Rechazar cambio de especie tras el registro · (TC-M02-036) Rechazar conversión de INDIVIDUAL a POBLACIONAL |
| Tipo | Validación / Pruebas de integridad |
| Herramienta | API — Postman |
| Precondiciones | 1. Activo individual con especie_id=3. 2. Activo tipo INDIVIDUAL existente |
| Datos de entrada | 1. `especie_id` inmutable tras el registro (rechazo de cualquier cambio). 2. `tipo_activo` inmutable: no se permite INDIVIDUAL → POBLACIONAL |
| Pasos | 1. Intentar actualizar `especie_id` a 7 (Ovino). 2. Intentar modificar `tipo_activo` a POBLACIONAL |
| Resultado esperado | 1. El sistema rechaza el cambio; la especie del activo permanece inmutable tras el registro. 2. El sistema rechaza la operación; no se permite convertir el tipo de activo después del registro |
| Responsable | Juan Manuel |
| Prioridad | Alta |
| Endpoints | `GET /activos-biologicos/{id_activo}` · `PATCH /activos-biologicos/{id_activo}` |

## Adaptación de datos al entorno TEST real

El texto del caso usa nombres de especie de ejemplo genéricos ("Bovino"/"Ovino") que **no existen** en el catálogo real
de especies del entorno TEST desplegado (es un sistema acuícola: Camarón Blanco, Trucha Arcoíris, Tilapia, Cachama
Blanca, Mojarra Plateada — confirmado vía `GET /configuracion/especies?solo_activas=true` antes de ejecutar). Se
mantuvieron los **IDs literales** del caso (`especie_id=3` como precondición, intento de cambio a `especie_id=7`) para
no reinterpretar el caso, y adicionalmente se probó un intento de cambio a una especie **real y activa** distinta
(`id_especie=4`, Cachama Blanca) para que el "intento de cambio" no dependa de si el ID 7 existe o no — el
comportamiento del endpoint (ignora el campo, nunca lo persiste) es el mismo en ambos casos porque
`ActualizarActivoIndividualDTO` no declara `id_especie` ni `tipo`.

## Ejecución

**Estado: PASS — 2/2 sub-casos, 16/16 assertions vía Postman/Newman contra el entorno TEST desplegado.** Ver
`RESULTADOS/TC-M02-G21_resultado.md` para el detalle de evidencia y un hallazgo relevante sobre **cómo** el sistema
rechaza el cambio (no es un único código de error — depende de si el intento va acompañado de un campo editable
válido).

El caso crea su **propio** activo individual de prueba en el setup (especie_id=3, igual que pide la precondición),
sin depender de datos de otros testers en el entorno compartido.

### GIVEN / WHEN / THEN

| Caso | GIVEN | WHEN | THEN |
|---|---|---|---|
| TC-M02-035 | Activo INDIVIDUAL con `id_especie=3` | (a) `PATCH` solo con `id_especie` nuevo, sin ningún campo editable. (b) `PATCH` con `id_especie` nuevo + un campo editable válido (`raza`) | (a) 400 — la solicitud se rechaza explícitamente. (b) 200, pero `id_especie` en la respuesta sigue siendo 3 — el cambio de especie nunca se aplica |
| TC-M02-036 | Mismo activo, tipo `INDIVIDUAL` | (a) `PATCH` solo con `tipo_activo=POBLACIONAL`, sin ningún campo editable. (b) `PATCH` con `tipo_activo=POBLACIONAL` + un campo editable válido (`peso_inicial`) | (a) 400 — la solicitud se rechaza explícitamente. (b) 200, pero `tipo` en la respuesta sigue siendo `INDIVIDUAL` y `detalle_poblacional` sigue `null` — la conversión nunca se aplica |
| Verificación final | — | `GET /activos-biologicos/{id_activo}` tras los 4 intentos anteriores | `id_especie=3` y `tipo=INDIVIDUAL` siguen intactos |

### Por qué dos variantes (a)/(b) por sub-caso

`ActualizarActivoIndividualDTO` (`src/biological_assets/infrastructure/dto/actualizar_activo_individual_dto.py`) no
declara `id_especie` ni `tipo`/`tipo_activo` — Pydantic los descarta sin más (comportamiento por defecto de `BaseDTO`,
sin `extra='forbid'`). Eso significa que:

- Si el body **solo** trae el campo prohibido, el validador `al_menos_un_campo` del DTO (que exige al menos uno de
  `raza`/`sexo`/`fecha_nacimiento`/`peso_inicial`) falla y la API devuelve **400** — un rechazo explícito de la
  solicitud completa.
- Si el body combina el campo prohibido con un campo editable válido, la solicitud **sí se acepta (200)** porque
  tiene un campo legítimo que actualizar, pero el campo prohibido nunca llega al caso de uso ni al repositorio
  (`SqlAlchemyActivoBiologicoRepository.actualizar_detalle_individual`, verificado en código: solo toca columnas de
  `detalle_individual`, nunca `tipo` ni `id_especie` en la tabla padre) — así que el valor **no cambia**, sin que la
  respuesta sea un código de error.

Probar solo la variante (a) daría una imagen incompleta ("el sistema siempre rechaza con 400"), y probar solo la
variante (b) también sería incompleta ("el sistema nunca rechaza explícitamente"). Las dos juntas son la evidencia
completa de que el RF se cumple: **el dato nunca cambia**, independientemente del código HTTP que devuelva cada
variante.

### Entorno

- Backend TEST: `https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test` (verificado `GET /health` → 200 antes de ejecutar).
- Cuenta usada: `admin.test@sgpmp.com.co` (Administrador, `id_rol=1`).
- Newman 6.2.2 + `newman-reporter-htmlextra` 1.23.1.
- Sin acceso directo a la base de datos: toda la verificación es vía API (coincide con el alcance declarado del caso: "API - Postman").
- Fecha de ejecución: 2026-09-09.

### Cómo re-ejecutar

```bash
cd tests/Test_Testing/Test_Modulo2/RF-35/TC-M02-G21
newman run TC-M02-G21.postman_collection.json -r cli,json,htmlextra \
  --reporter-json-export RESULTADOS/newman-TC-M02-G21.json \
  --reporter-htmlextra-export RESULTADOS/newman-TC-M02-G21.html
```

Cada ejecución crea un activo INDIVIDUAL nuevo (identificador único con timestamp), por lo que se puede repetir sin
limpiar datos y sin interferir con los activos de otros testers en el entorno compartido.
