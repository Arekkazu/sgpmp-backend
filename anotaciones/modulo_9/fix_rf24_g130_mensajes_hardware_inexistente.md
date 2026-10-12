# RF-24 — Mensajes de hardware inexistente (G130, issue #509)

## Alcance y contrato

Incidencia `INC-M09-73-G130`, RF-24 v2.0, CU05 Flujo D.
Casos: TC-M09-256 (dispositivo inexistente) y TC-M09-257 (sensor inexistente).

La evidencia proporcionada por QA describe HTTP 404, códigos correctos y ausencia
de persistencia, con dos fallos de comparación exacta de mensajes en el RUN
`run-20261007-085922`. Los artefactos originales `evidencia.json`, `newman.html`
y `TC-M09-G130_resultado.md` no se adjuntaron a esta ejecución local.

El RF-24 v2.0 compartido en `Requerimientos_3.md` define este mensaje común:

```text
Error de referencia: El sensor o dispositivo especificado no existe. No se puede registrar una calibración sobre un hardware inexistente.
```

## Causa y corrección

`RegistrarCalibracionUseCase._validar` utilizaba mensajes genéricos diferentes
para las dos referencias. Se agrega una constante local con el texto contractual
y se utiliza en los dos `NotFoundError` del registro de calibraciones.

Se conservan las consultas, el orden de validación (dispositivo antes que sensor),
HTTP 404, `DISPOSITIVO_NO_ENCONTRADO` y `SENSOR_NO_ENCONTRADO`. La calibración y su
auditoría interna no se escriben ante estos rechazos. La auditoría RF-10 existente
de intentos rechazados continúa recibiendo el código, los identificadores y el
motivo; este último refleja ahora el mensaje contractual.

El filtro por fincas permanece intacto: un dispositivo fuera del alcance del
usuario continúa tratándose como no encontrado y recibe el mismo mensaje, sin
confirmar su existencia. Los mensajes genéricos de otros flujos, incluido RF-22
y la consulta de historial con alcance restringido, no se modifican.

## Revisión de BD y RBAC

Se inspeccionó DEV (`sgpmp_dev`) mediante una conexión de solo lectura, con
rollback al finalizar. Se verificaron las columnas existentes de sensores,
dispositivos IoT y calibraciones. El cambio no necesita columnas, constraints,
catálogos, recursos ni permisos adicionales; no requiere migración.

Las consultas del recurso 12 y sus permisos no devolvieron filas visibles bajo
la conexión utilizada. Esta observación no demuestra ausencia de permisos en
TEST ni autoriza cambios de RBAC; el reporte QA indica que la autorización pasó.
No se ejecutó DDL ni DML en DEV o TEST.

## Validación local

Pruebas HTTP con el router, DTO, caso de uso y handlers reales, usando identidad,
alcance y repositorios sustituidos en memoria. No son pruebas contra PostgreSQL
ni contra el ambiente TEST.

Antes de la corrección, los nueve escenarios nuevos dieron **5 fallidos y 4
aprobados**: los cinco fallos correspondieron al mensaje común (dos casos, con
auditoría disponible o fallida, y dispositivo fuera de alcance).

La regresión ejecuta:

- Ambos casos QA: HTTP 404, código específico, mensaje exacto y ausencia de ID.
- Historial real simulado con IDs 15, 14, 13, 12, 11 y 10 sin cambios.
- Historial vacío del sensor inexistente sin cambios, bajo alcance global.
- Ausencia de llamadas a persistencia de calibraciones y auditoría interna.
- Evento de rechazo RF-10 tipo 29; una falla de auditoría conserva HTTP 404.
- Ocultamiento de dispositivos fuera del alcance por finca.
- Registro válido y conservación del historial para 0.0000, 22.5000 y 45.0000.
- Mensaje genérico de sensor inexistente en RF-22 sin modificaciones.
- Pruebas existentes de calibración, rango, auditoría y serialización numérica.

```powershell
.\.venv\Scripts\python.exe -m pytest --confcutdir=tests/configuration tests/configuration/test_rf24_g130_mensajes_hardware_inexistente.py tests/configuration/test_rf24_calibracion_json_numerico.py tests/test_registrar_calibracion_use_case.py tests/test_rango_calibracion.py -q --tb=short --show-capture=no
```

Resultado: **23 aprobadas**, con una advertencia preexistente de Starlette/httpx.
`--confcutdir` evita cargar el conftest global que importa `fcntl` de M02,
incompatible con Windows; no se modifica ni se sustituye esa dependencia.

## Entrega y reevaluación

Rama independiente `fix/rf24-g130-mensajes-hardware-inexistente`, creada desde
`origin/dev` (`5541ea36`). No incorpora soluciones de G75, G76, G77 o G80, ni
cambios de `modo_calibracion`.

La ejecución Newman oficial de TC-M09-G130 en TEST queda pendiente tras desplegar
la corrección. Este trabajo local no modifica el estado de aprobación oficial
de TC-M09-256 o TC-M09-257 ni implica despliegue o publicación de la rama.
