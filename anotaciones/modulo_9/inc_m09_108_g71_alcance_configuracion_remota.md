# TC-M09-108-G71 — Alcance por finca en configuración remota

## Desvío confirmado

`POST /configuracion/dispositivos-iot/{id}/configurar` verificaba únicamente el permiso
RBAC `dispositivos_iot/U`. Un Ingeniero de Campo con ese permiso podía indicar el ID de un
dispositivo ubicado en cualquier finca y crear una configuración remota. La ejecución llegaba
incluso a persistir el comando y publicarlo por MQTT.

El reporte Newman es correcto: el subcaso BOLA recibió `202 PENDIENTE` y creó la
configuración 21 para el dispositivo 17 a nombre del usuario 4, aunque ese usuario no tenía
ninguna finca vinculada.

La colección entregada tiene una aserción inconsistente con su propio nombre y con la issue:
el texto dice que acepta `403/404`, pero el script ejecuta
`pm.response.to.have.status(403)`. Como el contrato elegido oculta la existencia del recurso
ajeno, la reevaluación debe esperar `404` o usar
`pm.expect([403, 404]).to.include(pm.response.code)` si se desea conservar ambas alternativas.

## Corrección

- El router resuelve el alcance mediante `AlcanceFincaAdapter` y lo entrega al caso de uso.
- `ConfigurarRemotamenteUseCase` busca el dispositivo con ese alcance antes de consultar el
  tipo, pendientes, persistir o invocar MQTT.
- El repositorio incorpora el filtro de finca en la misma consulta SQL; no carga primero el
  dispositivo ajeno para descartarlo después.
- El historial `GET /{id}/configuraciones`, parte del mismo RF-23, aplica la misma barrera para
  evitar que el flujo quede protegido solo para escritura.
- Un ID inexistente o fuera del alcance responde `404 DISPOSITIVO_NO_ENCONTRADO`. La respuesta
  indistinguible evita confirmar la existencia de recursos de otra finca.

No se requirió migración Alembic ni cambio de permisos: la autorización combina el RBAC
existente con el alcance territorial ya soportado por el repositorio.

## Validación

- Pruebas unitarias: rechazo antes de persistencia/MQTT y rechazo del historial antes de leer
  configuraciones.
- Regresión RF-23: rangos y resultados MQTT `APLICADA`, `PENDIENTE` y `NO_CONF`.
- Validación HTTP contra `sgpmp_dev` con el usuario Ingeniero 4 y un dispositivo activo de la
  finca del usuario 2: POST e historial respondieron 404; el conteo de configuraciones se
  mantuvo en cero antes y después. La prueba se ejecutó dentro de una transacción exterior y
  finalizó con rollback.
