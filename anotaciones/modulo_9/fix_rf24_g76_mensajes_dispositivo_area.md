# RF-24 v2.0 — Mensajes de dispositivo inactivo y área no asociada

Incidencia: `INC-M09-70-G76-v2.0`, issue `#506`.
Grupo: `TC-M09-G76-v2.0`. Casos: `TC-M09-146-v2.0` y `TC-M09-147-v2.0`.
Rama: `fix/rf24-g76-mensajes-dispositivo-area`.
Base: `origin/dev`, commit `5541ea36`.

## Diagnóstico y alcance

Los dos textos en `RegistrarCalibracionUseCase._validar` no coincidían con
los flujos alternos de RF-24 v2.0 de `Requerimientos_3.md`.
La validación funcional y el manejo de errores ya eran correctos.

- Dispositivo inactivo: el mensaje era genérico y no identificaba el serial.
- Área no asociada: faltaba únicamente el prefijo `Conflicto de ubicación:`.

La rama se creó desde `dev` actualizado, sin incorporar los commits de G75.
No modifica los mensajes de formato/rango ni `modo_calibracion` (G74).

## Corrección

Para `DISPOSITIVO_INACTIVO`, se utiliza el serial de la entidad recuperada por
el repositorio existente, mediante `SerialDispositivo.__str__`, sin otra consulta:

```text
Operación rechazada: El dispositivo <SERIAL> está inactivo. Debe activar el dispositivo antes de proceder con el registro de nuevos parámetros de calibración.
```

Para `SENSOR_AREA_INVALIDA`, se conserva el sensor y el área solicitados:

```text
Conflicto de ubicación: El sensor <ID_SENSOR> no está asociado al área <ID_AREA>. Verifique la ubicación física y lógica del equipo antes de calibrar.
```

Se conservan HTTP 422/400, códigos, condiciones y orden de validación, campo
`id_infraestructura`, alcance por finca, auditoría y transacciones. El handler
existente propaga el nuevo texto a `message` y, cuando corresponde, a `fields`.
No cambia el esquema ni requiere migración.

El doble del dispositivo inactivo de la prueba unitaria existente recibió
un serial para reflejar el contrato de la entidad real.

## Verificación automatizada

Se añadieron nueve escenarios HTTP en
`tests/configuration/test_rf24_g76_mensajes_dispositivo_area.py`:

| Escenario | Comprobación |
| --- | --- |
| Inactivo con historial vacío | 422, código y mensaje exacto con serial |
| Inactivo con otro serial e historial existente | Interpolación dinámica y rechazo |
| Asociación vigente con otra área | 400, código, mensaje e IDs exactos |
| Sin asociación vigente y otros IDs | Se conserva el rechazo de la misma condición |
| Fallo de auditoría en ambos rechazos | Se conserva el 4xx y el texto; rollback |
| Activo con área asociada, valores 0, 25 y 45 | 201, creación y auditoría |

Los rechazos comprueban ausencia de llamadas para guardar calibraciones y
de auditorías de creación, igualdad del historial PRE/POST, y conservación
del dispositivo, asociación y rango. Los eventos de rechazo mantienen su
código y el motivo actualizado. El commit de estos rechazos corresponde a
su auditoría; no crea una calibración.

Los históricos con IDs 14–10 son simulados en memoria, no registros de TEST.
Las pruebas usan router, DTO, caso de uso y handlers reales, sustituyendo
repositorios, sesión, autenticación, permisos y alcance por dobles.

Antes del cambio, las nuevas pruebas dieron **6 fallidas y 3 aprobadas**.
Los seis fallos fueron comparaciones exactas de mensajes: cuatro variantes
de rechazo y dos escenarios de fallo de auditoría.

```powershell
.\.venv\Scripts\python.exe -m pytest --confcutdir=tests/configuration tests/configuration/test_rf24_g76_mensajes_dispositivo_area.py -q --tb=short
```

Después del cambio, la ejecución enfocada dio **23 aprobadas**:

```powershell
.\.venv\Scripts\python.exe -m pytest --confcutdir=tests/configuration tests/configuration/test_rf24_g76_mensajes_dispositivo_area.py tests/configuration/test_rf24_calibracion_json_numerico.py tests/test_registrar_calibracion_use_case.py tests/test_rango_calibracion.py -q --tb=short
```

La regresión existente cubre también auditoría obligatoria, rollback,
auditoría de rechazos, 403, formato/rango, modo de calibración, alcance por
finca e historial. Se conserva la serialización numérica de calibraciones.
La advertencia corresponde a la deprecación existente de Starlette/httpx.

Se utilizó `--confcutdir=tests/configuration` por la importación de `fcntl`
en el conftest global de M02, incompatible con Windows. No se modificó esa
dependencia ni se ejecutaron la suite global o las pruebas de integración.

## Límites y cierre QA

No se escribieron datos en DEV o TEST ni se ejecutaron migraciones.
El reporte Newman suministrado describe 55 assertions y dos fallos, pero
no se dispone de los artefactos originales para repetir su RUN_ID.

QA debe repetir los dos requests en TEST tras el despliegue, comprobar los
mensajes con el serial e IDs de su fixture y verificar el historial PRE/POST.
La aprobación oficial de G76 sigue pendiente de esa ejecución.
