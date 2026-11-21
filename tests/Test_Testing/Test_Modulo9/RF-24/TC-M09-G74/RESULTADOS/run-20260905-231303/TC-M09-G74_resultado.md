# TC-M09-G74 — RESULTADO

## DECISIÓN GENERAL

### APROBADO

`TC-M09-141` verificó en TEST real el registro de una calibración válida de
un sensor asociado a un dispositivo activo y su persistencia trazable en el
historial del mismo sensor.

| Caso | Resultado | Motivo | Categoría de error | Equipo responsable | Acción |
| --- | --- | --- | --- | --- | --- |
| TC-M09-141 | APROBADO | El POST válido respondió 201 y la calibración ID 9 quedó localizada en el historial; el registro previo se conservó. | No aplica | No aplica | No requiere reporte a Desarrollo, Implementación ni DBA. |

La matriz de pruebas asigna prioridad Alta al caso TC-M09-G74, mientras RF-24
v1.0 define prioridad Media/Should. Para la ejecución QA se conserva la
prioridad del caso de prueba sin modificar el requerimiento.

## ALCANCE Y AMBIENTE

| Elemento | Valor |
| --- | --- |
| Requerimiento | RF-24 — Calibración de dispositivos IoT, versión 1.0 |
| Caso | TC-M09-141 |
| Ejecución | `run-20260905-231303` |
| Fecha/hora de la creación | 2026-09-05 23:13:05.499 -05:00 (2026-09-06T04:13:05.499000Z) |
| Ambiente API | Backend TEST HTTPS: `https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test` |
| Ambiente web de referencia | Frontend TEST HTTPS: `https://sigab-frontendtest-6aqrny-d2b730-158-69-200-27.sslip.io` |
| Newman / htmlextra | 6.2.2 / 1.23.1 |
| Backend | `qa/juan-esteban-m09` — `adc3932b9f0293a76ebec7e89ed877274791b6a1` |
| Frontend | `qa/juan-esteban-m09` — `966621df4e2c6a1f2c9233ea5ebefbb9e3bc2f56` |
| SHA desplegado en TEST | No confirmado. |

## CONTRATO Y PRECONDICIONES DEMOSTRADAS

El contrato revisado define `POST /configuracion/sensores/{id_sensor}/calibrar`
con respuesta exitosa `201`. El DTO requiere dispositivo, infraestructura y
fecha de calibración; el responsable se obtiene de la sesión autenticada, por
lo que no se envió un usuario manualmente. El historial se consulta mediante
`GET /configuracion/sensores/{id_sensor}/calibraciones`.

Las consultas API previas y las assertions de Newman demostraron: actor
autenticado con el rol Ingeniero de Campo; permisos de lectura de dispositivos,
registro de calibración y consulta de historial; dispositivo activo; sensor
activo perteneciente al dispositivo; y asociación activa sensor–dispositivo–área.

## DATOS UTILIZADOS

| Dato | Valor |
| --- | --- |
| Actor | Ingeniero de Campo, usuario ID 4 |
| Dispositivo ID / serial | 1 / `IOT-EST01-HLA-001` |
| Dispositivo activo | Sí |
| Estructura productiva | ID 1 |
| Sensor ID / nombre | 3 / Sensor oxígeno disuelto estanque-01 |
| Tipo de sensor | OXIGENO |
| Sensor activo y asociado al dispositivo | Sí, dispositivo ID 1 |
| Área ID | 1 |
| Asociación dispositivo–sensor–área | Sí; activa y coherente |
| Rango técnico del catálogo | OXIGENO: 0.0000 a 20.0000 |
| Valor de referencia | 10.0000, interior al rango |
| Observaciones | `QA TC-M09-141 G74 run-20260905-231303` |
| Calibración ID | 9 |

## TRAZABILIDAD DEL REGISTRO

| Campo esperado | Valor persistido | Coincide |
| --- | --- | --- |
| Dispositivo | ID 1 | Sí |
| Sensor | ID 3 | Sí |
| Área / asociación | Área ID 1 validada antes del POST; la respuesta de calibración no expone área | Sí |
| Usuario | ID 4, correspondiente al Ingeniero autenticado | Sí |
| Fecha/hora | `2026-09-06T04:13:05.499000Z` | Sí, presente y dentro de la ejecución |
| Valor referencia | 10.0000 | Sí |
| Observaciones | `QA TC-M09-141 G74 run-20260905-231303` | Sí |

## HISTORIAL DE CALIBRACIONES

- Registros BEFORE: total 1; IDs `[3]`.
- Registros AFTER: total 2; IDs `[9, 3]`.
- Nueva calibración localizada: Sí, por ID 9 y por observaciones de la ejecución.
- Históricos previos conservados: Sí; el ID 3 continúa presente y el total aumentó exactamente en uno.

## EJECUCIÓN Y EVIDENCIA

La ejecución válida realizó 10 solicitudes: login, identidad, permisos, rango
técnico, dispositivo, sensores, asociación de área, historial BEFORE, POST y
historial AFTER. Sus estados fueron ocho `200`, un `201` para el POST y un
`200` final. Las 23 assertions pasaron; no hubo failures.

- Método y endpoint: `POST /configuracion/sensores/3/calibrar`.
- Respuesta de creación: `201 Created`; ID de calibración `9`.
- Persistencia: comprobada mediante el historial del sensor 3 después del POST.
- Evidencia HTML: [Newman intento 2](newman/newman-TC-M09-141-intento2.html).
- Evidencia JSON sanitizada: [resumen intento 2](newman-TC-M09-141-intento2.json).
- Escaneo de secretos: [resultado del escaneo](seguridad-evidencias.json). No se almacenaron credenciales, tokens, cabeceras de autenticación ni datos de sesión.

### Control de intentos

Se consumieron dos POST como máximo permitido. El intento 1 respondió `401`
porque la automatización no propagó el token de sesión desde el login a las
solicitudes posteriores. Una verificación posterior de solo lectura confirmó
que la observación de ese intento no existía en el historial; no hubo
persistencia parcial. Se corrigió únicamente la configuración de autenticación
de la colección y el intento 2 completó el flujo válido con `201`.

La causa del primer intento fue de **automatización QA** y quedó resuelta antes
del segundo intento. No es un defecto del producto ni una incidencia para
Desarrollo, Implementación o DBA. No se ejecutó un tercer POST.

## CONTROLES DE ALCANCE Y SEGURIDAD

- No se modificó código funcional, dependencias, infraestructura, Docker, Dokploy, Nginx, migraciones ni datos directamente en PostgreSQL.
- No se ejecutó SQL de escritura ni Cypress; la evidencia funcional es API real con Newman.
- No se modificaron dispositivo, sensor ni asociación; no se eliminaron ni alteraron calibraciones o históricos.
- No se instalaron dependencias ni se ejecutaron commit, push, pull, merge o cambios de rama.
- G22 queda fuera de alcance y no fue revisado ni modificado.

## GIT FINAL

Ambos repositorios permanecen en `qa/juan-esteban-m09` y `git diff --stat` no
mostró cambios rastreados. En backend, los artefactos nuevos de esta ejecución
están limitados a `tests/Test_Testing/Test_Modulo9/RF-24/TC-M09-G74/`; también
había artefactos sin seguimiento de grupos RF-17 previos, que se preservaron.
En frontend no se realizaron cambios; sus artefactos sin seguimiento de G22 y
G28 se preservaron sin intervención.

El cierre read-only registró 37 entradas en `git status --short` del backend:
9 pertenecen a G74 y 28 son externas a este grupo. `git ls-files --others
--exclude-standard` enumeró 114 archivos sin seguimiento en backend. En
frontend registró 18 entradas de estado y 47 archivos sin seguimiento, ninguno
de G74. No hubo diferencias de archivos rastreados en ninguno de los dos
repositorios.

La ejecución queda detenida para revisión humana.
