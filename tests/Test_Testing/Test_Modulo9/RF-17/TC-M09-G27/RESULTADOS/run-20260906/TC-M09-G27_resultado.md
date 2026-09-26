# TC-M09-G27 — RESULTADO

## DECISIÓN GENERAL

**APROBADO.**

TC-M09-59 demuestra que un actor autenticado cuyo rol no es Administrador ni
Veterinario no puede modificar un umbral ambiental real: el `PATCH` devolvió
**HTTP 403** con `ACCESO_DENEGADO`, y el GET administrativo posterior confirmó
que ningún dato funcional del umbral cambió. **No reportar a Desarrollo.**

| Caso | Resultado | Motivo | ¿Reportar a Desarrollo? |
|---|---|---|---|
| TC-M09-59 | APROBADO | Gestor de Granja autenticado, sin permiso RF-17 20/3, recibió 403 `ACCESO_DENEGADO`; BEFORE = AFTER | No |

## Entorno, versiones y alcance

- Fecha del PATCH: 2026-09-06 00:36:47 UTC; las evidencias mantienen timestamps exactos.
- TEST frontend: `https://sigab-frontendtest-6aqrny-d2b730-158-69-200-27.sslip.io`.
- TEST backend: `https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test`.
- Backend local: rama `qa/juan-esteban-m09`, SHA `adc3932b9f0293a76ebec7e89ed877274791b6a1`.
- Frontend local: rama `qa/juan-esteban-m09`, SHA `966621df4e2c6a1f2c9233ea5ebefbb9e3bc2f56`.
- **SHA desplegado en TEST no confirmado.** Los SHA anteriores son locales.
- Preflight: frontend `/login`, backend `/health` y `/openapi.json` respondieron 200.
- Newman 6.2.2; `newman-reporter-htmlextra` 1.23.1; Node 22.15.1. Dependencias verificadas, no instaladas.
- Herramienta única: Newman. No se ejecutó Cypress, navegación UI, SQL ni PostgreSQL directo.
- Alcance único: TC-M09-G27 / TC-M09-59. No se reejecutaron G22, G23, G24, G25 ni G26, y no se inició G28.

## Contrato y oráculo RBAC revisados

La revisión de solo lectura del backend local y de OpenAPI fue única antes del
PATCH. El endpoint de edición real es:

| Punto | Confirmación |
|---|---|
| Método y ruta | `PATCH /configuracion/umbrales/{id_umbral_ambiental}` |
| Identificador | ID de umbral existente en la ruta |
| DTO | `valor_min`, `valor_max`, tres `niveles`; `fecha_actualizacion` opcional |
| Permiso requerido | recurso 20 (`umbrales_ambientales`), acción 3 (actualizar) |
| GET de contraste | `GET /configuracion/umbrales?id_especie={id}` |
| 403 publicado | Sí, junto con 200, 401, 404, 412 y 422 |
| Respuesta de RBAC | `ACCESO_DENEGADO`: «Acceso denegado. Su rol no tiene permisos para realizar esta operación.» |

`umbral_router.py` protege el PATCH mediante `require_permission(20, 3)`.
`rbac.py` consulta el rol vigente y un permiso activo en cada request y devuelve
`AuthorizationError`/403 con `ACCESO_DENEGADO` cuando falta. El PATCH pasa por
esa dependencia antes de `EditarUmbralUseCase.execute`; por eso un rechazo de
este tipo corresponde al RBAC del backend, no a CSRF, gateway, proxy ni URL
incorrecta. El router documenta Administrador y Veterinario como roles
autorizados para RF-17.

## Actor y autenticación

El actor preferido Productor (`m2m.nuevo@ejemplo.com`) no fue utilizable: el login
real devolvió 403. El siguiente candidato Supervisor devolvió 400. No se usaron
como ataques y no se almacenaron respuestas sensibles. Según la adaptación
permitida por el caso, se seleccionó el primer actor posterior que sí demostró
ser no autorizado, sin ampliar cobertura a varios roles.

| Actor usado | Rol real | Login | `/usuarios/me` | `/sesiones/me/permisos` | Permiso 20/3 |
|---|---|---:|---:|---:|---|
| `gestor.granja.test@pecuaria.co` | Gestor de Granja | 200 | 200 | 200 | Ausente |

Gestor de Granja no pertenece a Administrador/Veterinario y su endpoint de
permisos no expone la acción 20/3. Por tanto se demostró usuario autenticado y
rol no autorizado antes del PATCH; 401 no intervino en el resultado.

## Registro objetivo, payload y comparación funcional

Se descubrió mediante GET administrativo el umbral real activo **#10**, especie
**4 Cachama Blanca**, variable **1 Temperatura del agua** (`°C`, catálogo físico
0–45). La preferencia académica de temperatura se cumplió. No se creó ningún
registro de preparación.

El estado existente tenía valores heredados `0.00–100.00`; el payload fue
deliberadamente distinto y válido según el catálogo actual: rango `9–36` y
niveles contiguos `9–18`, `18–27`, `27–36`, todos dentro de 0–45. También se
incluyó el `fecha_actualizacion` real (`null`) para que el payload no fallara por
concurrencia. No se hizo actualización positiva como Administrador.

| Campo funcional | BEFORE | Solicitado por actor no autorizado | AFTER |
|---|---|---|---|
| ID | 10 | 10 en ruta | 10 |
| Especie / variable | 4 / 1 | No modificables en PATCH | 4 / 1 |
| Estado | Activo | — | Activo |
| Rango | 0.00–100.00 | 9–36 | 0.00–100.00 |
| Crítico | 0.00–22.00 | 27–36 | 0.00–22.00 |
| Precaución | 22.00–26.00 | 18–27 | 22.00–26.00 |
| Normal | 26.00–32.00 | 9–18 | 26.00–32.00 |

La comparación normalizó solamente los campos funcionales del umbral y ordenó los
niveles por nombre. No exigió igualdad byte a byte ni comparó timestamps de
auditoría. Resultado: **BEFORE = AFTER; persistencia = false**.

## Ejecución Newman

- Intentos PATCH: **1 de máximo 2**. No se ejecutó reintento porque el primero fue PASS.
- Solicitud real: `PATCH /configuracion/umbrales/10` con el actor Gestor de Granja.
- HTTP obtenido: **403 Forbidden**.
- Código/mensaje: `ACCESO_DENEGADO` — acceso denegado por permisos del rol.
- Assertions Newman: **4 total, 0 failures**.
- GET posterior con Administrador: **200**; encontró el mismo umbral #10 sin cambios.
- No hubo 200, 201, 204, 401, 404, 400, 422 ni 500 en el PATCH.
- No se creó un umbral nuevo ni se persistió ningún cambio funcional.

Evidencias sanitizadas:

- [Datos, rol, BEFORE y payload](datos-TC-M09-59-intento1.json)
- [Resultado estructurado Newman](newman-TC-M09-59-intento1.json)
- [HTML Newman real](newman/newman-TC-M09-59-intento1.html)
- [Revisión de seguridad](seguridad-evidencias.json)

## ORIGEN DE LOS FALLOS

No aplica una desaprobación: TC-M09-59 fue aprobado.

- Producto: **No**. El control de acceso funcionó correctamente.
- Automatización/prueba: **No**. Se verificó login, identidad, rol, permiso,
  contrato, payload válido, request y snapshot posterior.
- Entorno: **No** para el caso ejecutado. TEST y las rutas requeridas estuvieron
  accesibles. Productor y Supervisor no fueron utilizables como actor, pero la
  adaptación a Gestor de Granja permitió evaluar el requisito sin ambigüedad.
- Bloqueo: **No**.
- Acción: **NO REPORTAR A DESARROLLO**.

## DEFECTO DETECTADO

No aplica. No se creó ticket, issue, PR ni identificador de defecto. Por la misma
razón no se asigna severidad, plazo ni fecha límite.

## Seguridad y restricciones respetadas

- Credenciales y tokens se manejaron únicamente en memoria de los procesos.
- El reporter omitió headers, variables de entorno y globales; el HTML recibió
  sanitización adicional después de ejecutarse.
- El escaneo de artefactos encontró cero contraseñas reales, JWT, Bearer con
  valor, connection strings o cookies con valor. Ver
  [seguridad-evidencias.json](seguridad-evidencias.json).
- No se conectó ni escribió en PostgreSQL; los GET de API resolvieron discovery y
  verificación posterior.
- No se modificó código de producto, dependencias, infraestructura, datos
  directamente, migraciones, permisos, roles ni configuraciones compartidas.
- No se hizo commit, push, pull, merge, rebase, cambio de rama, tag ni PR.

## Git final

Ambos repositorios permanecen en `qa/juan-esteban-m09`. Backend SHA
`adc3932b9f0293a76ebec7e89ed877274791b6a1`; frontend SHA
`966621df4e2c6a1f2c9233ea5ebefbb9e3bc2f56`. El backend conserva como untracked
fuera de alcance G24, G25 y G26; el frontend conserva G22. El estado final también
incluye `TC-M09-G26/README.md`, que no fue tocado durante G27. No se revirtieron ni
modificaron esos archivos. `git diff --stat` está vacío en ambos repositorios: los
artefactos de G27 son archivos QA nuevos/untracked dentro de
`tests/Test_Testing/Test_Modulo9/RF-17/TC-M09-G27/`.

Se detiene G27 para revisión humana.
