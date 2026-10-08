# RF-24 v2.0 — Mensaje de acceso denegado en calibraciones

Incidencia: `INC-M09-71-G77-v2.0`, issue `#507`.
Grupo: `TC-M09-G77-v2.0`. Caso: `TC-M09-148-v2.0` (Productor y Contador).
Rama: `fix/rf24-g77-mensaje-acceso-denegado`.
Base: `origin/dev`, commit `5541ea36`.

## Diagnóstico

La dependencia `_permiso_calibrar_auditado` del endpoint
`POST /configuracion/sensores/{id_sensor}/calibrar` invocaba el RBAC sin
mensaje propio, por lo que devolvía su texto genérico para `ACCESO_DENEGADO`.
El contrato se contrastó con el flujo alterno de RF-24 v2.0 de
`Requerimientos_3.md` suministrado por el usuario.

La compuerta de permisos ya funcionaba: el defecto corresponde al texto,
no a la autorización. La evidencia compartida es el reporte de QA, sin
los artefactos originales enumerados para repetir el RUN_ID.

## Corrección y alcance

Se utiliza el parámetro existente `mensaje_denegado` de `require_permission`
solo dentro de la dependencia de registro de calibraciones:

```text
Acceso denegado: La calibración de sensores es una función crítica restringida exclusivamente al Ingeniero de Campo o al Administrador.
```

Se conservan HTTP 403, `ACCESO_DENEGADO`, el recurso y acción existentes
(`sensores`, ID 12, CREATE 1), la consulta dinámica a `modulo1.permisos`
y la auditoría del rechazo. El motivo auditado recibe el mismo texto
contractual que la respuesta HTTP.

No se cambia `src/shared/rbac.py`, ninguna matriz de permisos, asignación
de roles, estado de cuenta, caso de uso, repositorio, DTO ni esquema.
No se hardcodean roles para permitir o denegar operaciones.
`CUENTA_NO_ACTIVA` y el mensaje genérico de otros endpoints se conservan.

La rama se creó desde `dev` actualizado y no incorpora las soluciones de
G75 o G76. `modo_calibracion` (G74) queda fuera del alcance.

## Pruebas HTTP y regresión

Se agregaron once escenarios en
`tests/configuration/test_rf24_g77_mensaje_acceso_denegado.py`:

| Escenario | Resultado comprobado |
| --- | --- |
| Productor con READ y sin CREATE | 403, código y mensaje exacto, sin calibración |
| Contador sin permisos | 403, código y mensaje exacto, sin calibración |
| Administrador e Ingeniero con CREATE simulado | 201 y auditoría de creación |
| ID de rol arbitrario con CREATE simulado | La autorización sigue dependiendo de permisos |
| Fallo de auditoría para ambos roles sin CREATE | Conserva 403 y mensaje; rollback |
| Cuenta no activa con CREATE simulado | Conserva `CUENTA_NO_ACTIVA` y su texto |
| Request sin autenticación | Conserva 401, sin entrar al caso de uso |
| Lectura de historial y asociación sin permiso | Conservan el mensaje RBAC genérico |

En los rechazos se verifica que el caso de uso de registro no se instancia,
no se llama a guardar calibraciones ni a registrar auditorías de creación,
el historial PRE/POST permanece idéntico y no cambian la identidad ni los
permisos simulados. La consulta de control del historial usa otro lector
autorizado; no concede READ al Contador.

Los tests ejercitan `require_permission`, `tiene_permiso`, router, DTO,
caso de uso y handlers reales. La consulta SQLAlchemy de permisos se
resuelve mediante una matriz en memoria; los demás repositorios, sesión,
alcance e identidad autenticada se sustituyen por dobles. Los IDs y roles
del fixture no representan cuentas ni permisos consultados en TEST.

Con las pruebas preparadas y antes de modificar el router, el resultado fue
**4 fallidas y 7 aprobadas**. Los cuatro fallos fueron comparaciones exactas
de mensajes para ambos roles, con auditoría disponible y con fallo de auditoría.

```powershell
.\.venv\Scripts\python.exe -m pytest --confcutdir=tests/configuration tests/configuration/test_rf24_g77_mensaje_acceso_denegado.py -q --tb=short
```

Tras la corrección, la ejecución enfocada y de regresión dio **32 aprobadas**:

```powershell
.\.venv\Scripts\python.exe -m pytest --confcutdir=tests/configuration tests/configuration/test_rf24_g77_mensaje_acceso_denegado.py tests/configuration/test_rf24_calibracion_json_numerico.py tests/configuration/test_rf29_idioma_rbac.py tests/test_registrar_calibracion_use_case.py tests/test_rango_calibracion.py -q --tb=short
```

La regresión incluye validaciones de calibración, serialización numérica,
auditoría obligatoria, rollback, alcance por finca y mensajes RBAC de RF-29.
Se observó únicamente la advertencia existente de Starlette/httpx.

Se utilizó `--confcutdir=tests/configuration` porque el conftest global de M02
importa `fcntl`, incompatible con Windows. No se modificó esa dependencia
ni se ejecutaron la suite global o las pruebas de integración.

## Base de datos y cierre QA

No requiere migración ni cambios de permisos. No se escribieron datos en
DEV o TEST. La integridad comprobada corresponde a repositorios en memoria,
no a los históricos oficiales de QA.

Tras desplegar, QA debe repetir ambos requests con las identidades y permisos
originales, comprobar el texto exacto y verificar el historial PRE/POST.
La aprobación oficial de G77 sigue pendiente de esa ejecución.
