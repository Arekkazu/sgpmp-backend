# TC-M02-G20 — Consulta y actualización de atributos permitidos del activo individual

**CU-02 · RF-35 — Gestión Individual de Activos Biológicos.**

| Campo | Valor |
|---|---|
| Sub-casos | (TC-M02-033) Consultar activo individual existente · (TC-M02-034) Actualizar atributos permitidos del individuo |
| Tipo | Funcional |
| Herramienta | TC-M02-033: Frontend / API — Cypress + Postman · TC-M02-034: API — Postman |
| Precondiciones | 1. Activo individual registrado y accesible por el usuario. 2. Activo individual existente sin eventos pendientes |
| Datos de entrada | Campos editables: `raza`, `sexo`, `peso_inicial`, `fecha_nacimiento` (no `especie` ni `tipo`) |
| Pasos | 1. Seleccionar el activo desde el listado y abrir su ficha. 2. Actualizar `raza`, `sexo`, `peso_inicial` o `fecha_nacimiento` |
| Resultado esperado | 1. El sistema muestra la información actual del activo y su historial disponible. 2. Los cambios se guardan, se valida integridad de datos por especie y se registra la operación en auditoría |
| Responsable | Juan Manuel |
| Prioridad | Alta |
| Endpoints | `GET /activos-biologicos/{id_activo}` · `PATCH /activos-biologicos/{id_activo}` |

## Ejecución

**Estado: PASS — 2/2 sub-casos, ejecutados dos veces (Postman/Newman y Cypress) de forma independiente contra el mismo entorno TEST desplegado.** Ver `RESULTADOS/TC-M02-G20_resultado.md` para el detalle de evidencia (requests/responses reales, IDs generados, hallazgos).

Ambas suites crean su **propio** activo individual de prueba en el `before`/setup (no reutilizan datos de otros testers en el entorno compartido) y no requieren datos previos aparte de: una especie activa (`id_especie=4`, Cachama Blanca) y una infraestructura activa (`id_infraestructura=6`), ya usadas exitosamente por activos existentes en TEST antes de esta ejecución.

### GIVEN / WHEN / THEN

| Caso | GIVEN | WHEN | THEN |
|---|---|---|---|
| TC-M02-033 | Activo individual existente, accesible por el usuario autenticado | `GET /activos-biologicos/{id_activo}` | 200, la ficha trae `raza`/`sexo`/`fecha_nacimiento`/`peso_inicial` actuales; el historial del activo (`GET /{id_activo}/historial`) responde 200 y es consultable |
| TC-M02-034 | Mismo activo, sin eventos pendientes | `PATCH /activos-biologicos/{id_activo}` con `raza`, `sexo`, `fecha_nacimiento`, `peso_inicial` nuevos (y, deliberadamente, `tipo`/`id_especie`/`estado_activo` que el RF prohíbe tocar) | 200; los 4 campos editables quedan actualizados y persisten en una consulta posterior; `tipo`/`id_especie`/`estado` permanecen intactos; queda un registro `ACTIVO_INDIVIDUAL_ACTUALIZADO` en la bitácora RF-52 |

### Por qué se incluyen `tipo`/`id_especie`/`estado_activo` en el PATCH de TC-M02-034

El RF exige explícitamente que esos campos no sean editables desde esta operación. `ActualizarActivoIndividualDTO`
(`src/biological_assets/infrastructure/dto/actualizar_activo_individual_dto.py`) ni siquiera los declara, así que
Pydantic los descarta silenciosamente (comportamiento por defecto de `BaseDTO`, sin `extra='forbid'`). Enviarlos y
comprobar que la respuesta no cambia es la forma más directa de verificar en vivo que la restricción del RF se
cumple estructuralmente, no solo por ausencia de un botón en la UI.

### Entorno

- Backend TEST: `https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test` (verificado `GET /health` → 200 antes de ejecutar).
- Cuenta usada: `admin.test@sgpmp.com.co` (Administrador, `id_rol=1`) — tiene permiso de lectura (R) y actualización (U) sobre el recurso 29 (`activos_biologicos`).
- Newman 6.2.2 + `newman-reporter-htmlextra` 1.23.1 (ya instalados globalmente). Cypress 14.5.4, Electron 130 headless (instalado en esta ejecución vía `npm ci`, ya declarado en `package.json`/`package-lock.json` del repo — no se modificó ninguno de los dos).
- Fecha de ejecución: 2026-09-09.

### Cómo re-ejecutar

```bash
# Postman/Newman
cd tests/Test_Testing/Test_Modulo2/RF-35/TC-M02-G20
newman run TC-M02-G20.postman_collection.json -r cli,json,htmlextra \
  --reporter-json-export RESULTADOS/newman-TC-M02-G20.json \
  --reporter-htmlextra-export RESULTADOS/newman-TC-M02-G20.html

# Cypress (desde la raíz del backend)
npx cypress run --spec "tests/Test_Testing/Test_Modulo2/RF-35/TC-M02-G20/tc-m02-g20-consulta-actualizacion.cy.js"
```

Cada ejecución crea un activo INDIVIDUAL nuevo (identificador único con timestamp), por lo que se puede repetir sin
limpiar datos y sin interferir con los activos de otros testers en el entorno compartido.
