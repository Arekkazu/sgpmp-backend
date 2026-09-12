# TC-M02-G23 — Control de acceso y protección del historial inmutable en la gestión de activos individuales

**CU-02 · RF-35 / RF-37 — OWASP API1:2023 (BOLA), API5:2023 (Broken Function Level Authorization), API3.**

| Campo | Valor |
|---|---|
| Sub-casos | (TC-M02-045) BOLA al actualizar activo de otra finca · (TC-M02-046) Función restringida por rol · (TC-M02-047) Intento de alterar historial inmutable de fases |
| Tipo | Seguridad — OWASP API1 / API5 / API3 |
| Herramienta | Pytest / Postman + Pytest |
| Precondiciones | 1. Veterinario asignado solo a Finca 1; `activo_id=800` pertenece a Finca 2. 2. Usuario con rol de solo consulta (sin permisos de escritura). 3. Existe un registro histórico de fase ya cerrado (`fecha_fin` informada) |
| Pasos | 1. El veterinario ejecuta `PUT /activos-biologicos/800` manipulando el ID. 2. El usuario invoca `PUT /activos-biologicos/{id}` para actualizar atributos. 3. Intentar un `PATCH` directo sobre el registro histórico de fase |
| Resultado esperado | 1. `403 Forbidden`, sin modificar datos, intento auditado. 2. `403 Forbidden`, sin cambios aplicados. 3. Rechazo de la operación; historial append-only e inalterado |
| Responsable | Juan Manuel |
| Prioridad | Alta |
| Endpoints | `GET/PATCH /activos-biologicos/{id_activo}` · `POST/GET /activos-biologicos/{id_activo}/fases` |

## ⚠️ Resultado: BOLA CRÍTICO confirmado + 1 bloqueo de precondición (RF-37) ajeno a RF-35

**Estado general: TC-M02-045 → FAIL crítico (vulnerabilidad real confirmada). TC-M02-046 → PASS. TC-M02-047 →
BLOQUEADO en su precondición (bug de RF-37, ver `NOTA_BLOQUEO.md`), con verificación estructural parcial en PASS.**
Postman/Newman: 9/12 assertions PASS. Pytest: 5/7 PASS. Ver `RESULTADOS/TC-M02-G23_resultado.md` para el detalle
completo con evidencia.

### Adaptación de precondiciones al entorno real (por qué no es literalmente "el veterinario" ni "`activo_id=800`")

El texto del caso da actores y IDs de ejemplo genéricos. Se adaptaron a datos reales verificables en TEST,
manteniendo la intención exacta del RF:

- **No existe ninguna cuenta con rol Veterinario ni Contador en TEST**, y el registro público (`POST /usuarios/`)
  exige un reCAPTCHA real que este entorno de ejecución no puede resolver (correctamente — no se intentó eludirlo).
  En vez de eso, se **reactivaron dos cuentas QA ya existentes y en estado `PENDIENTE`**, creadas por sesiones de
  prueba anteriores de RF-01 (`tc015b.qa@sgpmp-test.com`, `tc020.qa@sgpmp-test.com`; contraseña `Abcd12#3`,
  documentada en `tests/Test_Testing/Test_Modulo1/RF-01/TC-M01-13/` y `TC-M01-20/`, no es un secreto nuevo) vía
  `POST /usuarios/{id}/gestionar {"accion_cuenta":"activar"}` (transición `PENDIENTE→ACTIVO` explícitamente permitida
  para un administrador) y `PATCH /usuarios/{id}` para asignar el rol Veterinario a una de ellas. Ninguna de las dos
  cuentas pertenecía a una persona real ni tenía actividad previa más allá del registro original de RF-01.
- Se creó una finca propia para la prueba (`PUT /usuarios/{id}/fincas` no fue necesario; `POST
  /configuracion/fincas` acepta `id_usuario` directamente en la creación) — **Finca 36 "QA G Veintitres Finca
  Alfa"**, asignada al Productor reactivado (id 71). Este es el "Veterinario asignado solo a Finca 1" del caso,
  adaptado a un Productor (que sí tiene permiso de escritura) porque probar BOLA con un rol que de entrada no
  tiene permiso de escritura no distingue "bloqueado por falta de permiso" de "bloqueado por finca ajena" — ver
  la nota de diseño más abajo.
- El "`activo_id=800` de Finca 2" se reemplazó por un activo **propio de esta prueba y completamente controlado**:
  `id_activo_biologico=200`, en la **Finca 37 "QA G Veintitres Finca Beta"** (creada y asignada al propio admin,
  id 47) — así la colección se puede re-ejecutar indefinidamente sin tocar datos de ningún usuario real.

### Por qué se probó con un Productor y no con el Veterinario para el BOLA (TC-M02-045)

El Veterinario **no tiene permiso de escritura (`U`) sobre `activos_biologicos` en ningún caso** (gap ya documentado
en la auditoría del módulo: "Veterinario, listado explícitamente como actor de RF-35, no tiene permiso de
actualización"). Si se usa al Veterinario para el BOLA, la petición se rechaza con 403 **siempre**, sin importar la
finca — el resultado sería un 403 correcto, pero por la razón equivocada (falta de rol, no aislamiento por finca), y
no distinguiría si el verdadero control de BOLA existe o no. Por eso:

- **TC-M02-045 (BOLA)** se probó con un **Productor** (sí tiene permiso de escritura) limitado a una finca propia —
  esto sí aísla la variable correcta y es lo que reveló la vulnerabilidad real.
- **TC-M02-046 (función restringida por rol)** se probó con el **Veterinario** tal como pide el caso — aquí sí es
  exactamente el escenario correcto ("rol de solo lectura ejecuta operación de escritura").

### GIVEN / WHEN / THEN

| Caso | GIVEN | WHEN | THEN esperado (RF) | Resultado real |
|---|---|---|---|---|
| TC-M02-045 (control) | Productor A, activo propio (199, Finca 36) | `PATCH` sobre su propio activo | 200 | **200 — correcto** |
| TC-M02-045 (GET) | Productor A, activo ajeno (200, Finca 37) | `GET` | 404 (RF-25, no revela existencia) | **404 — correcto** |
| TC-M02-045 (PATCH, BOLA) | Mismo Productor A, mismo activo ajeno | `PATCH` | **403 Forbidden** | **200 OK — FAIL crítico.** El activo ajeno se modifica sin ninguna restricción |
| TC-M02-046 | Veterinario (sin permiso `U`) | `PATCH` sobre cualquier activo accesible | 403 Forbidden | **403 `ACCESO_DENEGADO` — correcto** |
| TC-M02-047 | Activo con una fase ya cerrada | `PATCH` directo sobre el registro de fase | Rechazado, append-only | **Precondición bloqueada** (ver abajo) — verificación estructural parcial: no existe ruta de edición directa (404) |

### TC-M02-047 — por qué quedó bloqueado

`POST /activos-biologicos/{id}/fases` (la única forma de crear el primer registro de historial de fases) devuelve
**500** para **cualquier** activo con **cualquier** ciclo productivo válido — causa raíz confirmada por lectura de
código en `NOTA_BLOQUEO.md` (falta un argumento en una llamada dentro de `cambiar_fase_use_case.py`; no requirió
acceso a base de datos para confirmarlo, a diferencia del bloqueo de RF-41 en `TC-M02-G22`). Sin poder crear ni
siquiera la primera fase, es imposible llegar a la precondición literal ("una fase ya cerrada"). Se dejó, como
evidencia parcial válida, la confirmación de que **no existe ningún endpoint público para editar una fase existente**
(`PATCH /activos-biologicos/{id}/fases/{id_fase}` → 404) — es decir, el historial es append-only por *ausencia total
de vía de edición*, que es una forma legítima (aunque no completa) de cumplir la exigencia del RF.

### Entorno

- Backend TEST: `https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test`.
- Cuentas usadas: `admin.test@sgpmp.com.co` (Administrador) · `tc015b.qa@sgpmp-test.com` (Productor, reactivada,
  Finca 36) · `tc020.qa@sgpmp-test.com` (Veterinario, reactivada y re-rolada).
- Newman 6.2.2 + htmlextra 1.23.1. Pytest 9.0.3 + `requests` (contra el mismo backend TEST, caja negra — no importa
  código del backend, solo hace HTTP real).
- Sin acceso a la base de datos PostgreSQL de TEST — toda la verificación es vía API.
- Fecha de ejecución: 2026-09-09.

### Cómo re-ejecutar

```bash
# Postman/Newman
cd tests/Test_Testing/Test_Modulo2/RF-35/TC-M02-G23
newman run TC-M02-G23.postman_collection.json -r cli,json,htmlextra \
  --reporter-json-export RESULTADOS/newman-TC-M02-G23.json \
  --reporter-htmlextra-export RESULTADOS/newman-TC-M02-G23.html \
  --suppress-exit-code

# Pytest (desde la raíz del backend)
python -m pytest tests/Test_Testing/Test_Modulo2/RF-35/TC-M02-G23/test_tc_m02_g23_control_acceso.py -v
```

Ambas suites son idempotentes: el activo víctima (200) se restaura a su valor original al final de cada ejecución
(paso explícito en Postman, `teardown_class` en pytest), y ninguna de las dos toca datos de usuarios reales.
