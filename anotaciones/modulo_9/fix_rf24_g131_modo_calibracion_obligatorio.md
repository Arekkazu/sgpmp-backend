# RF-24 — Modo de calibración obligatorio (G131, issue #510)

## Incidencia y causa local

`INC-M09-74-G131`, RF-24 v2.0, CU05 Flujo D. QA reportó que TC-M09-259,
ejecutado sin `modo_calibracion`, respondió HTTP 201 y persistió el ID 16.
TC-M09-258 pasó; las variantes `OTRO` y `""` de TC-M09-260 no se ejecutaron
en TEST debido a STOP_ALL. No se adjuntaron los artefactos originales del RUN
`run-20261007-040706`; el reporte se toma como evidencia proporcionada por QA.

La base local `origin/dev` (`5541ea36`) ya declara el campo y publica un enum
en OpenAPI, a diferencia del contrato TEST descrito en el reporte. Sin embargo,
el DTO asignaba `ModoCalibracion.SENSOR` por defecto. Esa definición aceptaba
la omisión, permitía alcanzar el caso de uso y ocultaba el campo en `required`.
No se determinó el SHA desplegado en TEST.

## Corrección

Se elimina únicamente el default de `RegistrarCalibracionDTO.modo_calibracion`.
El campo conserva su enum, pero ahora debe enviarse explícitamente.

- Omisión, null y valores fuera del dominio del endpoint: HTTP 400 `VAL_ENTRADA`,
  con un error en `fields` para `modo_calibracion`, sin `id_calibracion`.
- El rechazo ocurre durante la validación de entrada, antes de ejecutar el
  caso de uso y de guardar una calibración o su auditoría interna.
- OpenAPI incluye el campo en `required`, sin default, y publica el enum.
- Un request válido con `modo_calibracion: "SENSOR"` mantiene HTTP 201,
  persistencia, modalidad en la respuesta y trazabilidad interna existente.

Se ajustan el fixture válido de pruebas y los ejemplos/documentación para enviar
la modalidad explícitamente. Los clientes que dependían del default deberán
enviar `"modo_calibracion": "SENSOR"`.

## Alcance respecto de G74 y VISION

RF-24 v2.0 describe `SENSOR | VISION`. El endpoint existente
`POST /configuracion/sensores/{id_sensor}/calibrar` implementa únicamente SENSOR,
y el enum publicado conserva ese único valor. VISION sigue rechazándose como
antes; no se habilita una modalidad sin su procesamiento y persistencia propios.
La implementación completa y el contrato de VISION permanecen pendientes en el
ámbito relacionado con G74; esta corrección no demuestra cumplimiento completo
de las dos modalidades de RF-24 v2.0. G131 permanece relacionado con G74, sin
tratarlo como duplicado ni incluir su solución en esta rama.

Se conservan los defaults de la entidad y del schema que representan registros
históricos de sensores. No se alteran los repositorios, los históricos existentes,
la matriz RBAC, los handlers compartidos ni los mensajes de otras incidencias.
Los rechazos de DTO siguen el handler existente; esta rama no agrega eventos RF-10
para esa capa ni incorpora la solución de calibración exitosa de G80.

## Inspección de BD y RBAC

La revisión de DEV (`sgpmp_dev`) se realizó con una conexión de solo lectura y
rollback final. `modulo9.calibraciones.id_sensor` es NOT NULL y no hay columna
`modo_calibracion`: el adaptador reconstruye las filas como SENSOR. La exigencia
de presencia en el request se resuelve en el DTO; no requiere migración ni cambios
de datos. El esquema de modalidades de visión no forma parte de este arreglo.

El recurso 12 y sus permisos no devolvieron filas visibles con la conexión
utilizada. Esto no acredita ausencia de RBAC en TEST, donde QA verificó permiso
de creación. No se modificaron permisos ni se ejecutó DDL/DML en DEV o TEST.

## Pruebas y límites de la verificación

Se utilizan FastAPI, el router, DTO, caso de uso y handlers reales, con identidad,
alcance y repositorios en memoria. Antes de cambiar producción, el fixture
corregido reprodujo **2 fallos y 18 aprobaciones**: HTTP 201 por omisión y campo
ausente de `required` en OpenAPI.

Después de corregir: **34 pruebas aprobadas**, incluyendo 20 escenarios nuevos:

- TC-M09-259: omisión, rechazo antes del caso de uso y conservación del historial
  simulado con IDs 10–15 y total 6.
- TC-M09-260: `OTRO` y `""` rechazados localmente; también null, número, booleano,
  minúsculas y VISION (rechazo existente de este endpoint).
- Contrato OpenAPI requerido, sin default y enum SENSOR explícito.
- SENSOR válido para 0.0000, 22.5000 y 45.0000; historial anterior conservado.
- TC-M09-258: HTTP 422 `SENSOR_DISPOSITIVO_INVALIDO`, historial simulado [3, 9]
  intacto; validaciones de área, rango, formato, hardware y dispositivo activo.
- Rechazo por autorización, auditoría y serialización numérica existentes.

```powershell
.\.venv\Scripts\python.exe -m pytest --confcutdir=tests/configuration tests/configuration/test_rf24_g131_modo_calibracion_obligatorio.py tests/configuration/test_rf24_calibracion_json_numerico.py tests/test_registrar_calibracion_use_case.py tests/test_rango_calibracion.py -q --tb=short --show-capture=no
```

Advertencia preexistente de Starlette/httpx. `--confcutdir` evita el conftest global
que importa `fcntl` de M02, incompatible con Windows; no se cambia esa dependencia.
`TEST_DATABASE_URL` no está configurada: no se ejecutó integración PostgreSQL ni
el RUN oficial en TEST. Las pruebas en memoria no prueban constraints o triggers
de PostgreSQL.

## Entrega

Rama `fix/rf24-g131-modo-calibracion-obligatorio`, desde `origin/dev`, independiente
de G75, G76, G77, G80 y G130. Pendiente desplegar y reevaluar TC-M09-259 y ejecutar
ambas variantes de TC-M09-260 con un RUN_ID nuevo. No se eliminó ni modificó la
calibración 16 del reporte QA ni ningún otro registro existente.
