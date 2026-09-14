# TC-M09-G78 — PRIMERA EVALUACIÓN

Caso original: **TC-M09-149 — Mantener calibración pendiente cuando falla la propagación al firmware**
Requerimiento: **RF-24 — Calibración de dispositivos IoT** · CU-05 Gestionar Dispositivos IoT
Responsable QA: Juan Esteban · RUN_ID: `G78-EVAL-V1-20260913-002659` · Fecha local: 2026-09-13

Esta es la evaluación inicial de TC-M09-149. No existe una evaluación anterior
con la cual comparar ni una incidencia previa asociada.

---

## DECISIÓN GENERAL

### TC-M09-149: DESAPROBADO — DEFECTO DEL PRODUCTO / FUNCIONALIDAD NO IMPLEMENTADA

En DEV, el ambiente decisorio, el registro de una calibración es una operación
REST que solo escribe en base de datos. Ni el contrato desplegado ni el código
de `origin/dev` contienen propagación al firmware por MQTT, estado pendiente de
propagación ni reintento automático. Sin esos tres elementos, el escenario de
TC-M09-149 («sensor válido + firmware sin respuesta → CALIBRACIÓN_PENDIENTE +
reintento + solicitud no perdida») no puede producirse en el producto.

| Caso | Resultado | Ambiente decisorio | Motivo | Categoría | Equipo | Acción |
| --- | --- | --- | --- | --- | --- | --- |
| TC-M09-149 | DESAPROBADO — DEFECTO DEL PRODUCTO / FUNCIONALIDAD NO IMPLEMENTADA | DEV | La calibración no se propaga al firmware: no invoca MQTT, no tiene estado pendiente y no tiene reintento. Confirmado en el contrato desplegado en DEV y en el código de `origin/dev`. | FLUJO — Flujo / Proceso | Desarrollo | REPORTAR A DESARROLLO |

No se ejecutó ningún POST: el checklist previo exigía un flujo MQTT, un estado
pendiente y un reintento identificables para calibraciones, y ninguno existe.
Consumir la creación no habría aportado evidencia nueva y habría dejado una
calibración en DEV sin propósito. Presupuesto usado: **0 de 2 POST**.

> **Discrepancia que Desarrollo debe conocer antes del triage.** RF-24 define la
> calibración como un ajuste lógico aplicado al procesamiento que no modifica el
> hardware, y la documentación de implementación de Desarrollo afirma
> expresamente que la calibración «no corresponde al broker MQTT». La propagación
> al firmware es un requisito que añade la matriz G78. Por instrucción del
> paquete, la matriz es el oráculo de este caso y el resultado se clasifica como
> funcionalidad no implementada. Es posible que el triage concluya que lo que
> debe corregirse es la matriz y no el producto. Esa decisión no corresponde a QA
> y no se tomó aquí. Detalle en «TRAZABILIDAD RF-24 / G78».

---

## ENTORNO FUNCIONAL UTILIZADO

| Elemento | Valor |
| --- | --- |
| Ambiente decisorio | **DEV**, porque MQTT solo existe en DEV |
| Backend DEV | `https://sigab-backenddev-jpuya4-ea3a74-158-69-200-27.sslip.io/api-sgpmp` — `/health` 200, `/openapi.json` 200 |
| Frontend DEV | No utilizado; no hace falta para TC-149 |
| TEST | Solo se consultó el contrato REST desplegado, sin concluir nada sobre MQTT |
| Herramienta | Pytest 9.0.3 (Python 3.13.13), verificación de solo lectura |
| Tipo de evidencia | Verificación de implementación: contrato OpenAPI desplegado (GET sin autenticación) y código de `origin/dev` (`git show` / `git grep`, sin checkout ni fetch) |
| POST / login / SQL / MQTT | Ninguno |
| Cypress | No ejecutado |

---

## VERIFICACIÓN TEST

| Elemento | Resultado |
| --- | --- |
| URL suministrada `http://…/api-sgpmp-test` | `/health` y `/openapi.json` responden **404 del proxy**: el esquema HTTP no está enrutado en TEST (mismo comportamiento ya documentado en G77) |
| Mismo host por HTTPS, solo GET del contrato | `/health` 200, `/openapi.json` 200 |
| Flujo REST de calibración presente | **Sí** — `POST /configuracion/sensores/{id_sensor}/calibrar` (201/400/401/403/404/422/500) |
| Estado pendiente observable | **No** — `CalibracionResponse` no tiene campo de estado |
| MQTT | No disponible en TEST (fuera de alcance por regla) |

---

## VERIFICACIÓN DEV

| Elemento | Resultado | Evidencia |
| --- | --- | --- |
| Flujo REST presente | **Sí** | `POST /configuracion/sensores/{id_sensor}/calibrar` desplegado |
| MQTT presente en la calibración | **No** | `RegistrarCalibracionUseCase` y `sensor_router` no referencian `MqttPort`, `MqttHttpAdapter`, broker ni firmware |
| MQTT presente en el producto | Sí, pero **solo para RF-23** | Los únicos consumidores de `MqttPort` son `configurar_remotamente_use_case.py` y `dispositivo_iot_router.py` (`POST /dispositivos-iot/{id}/configurar`) |
| Estado pendiente presente | **No** | `modulo9.calibraciones` tiene `id_calibracion, id_dispositivo_iot, id_sensor, fecha_calibracion, valor_referencia, ganancia, offset_calibracion, observaciones, id_usuario`; ninguna columna de estado ni de propagación. `CalibracionResponse` y `RegistrarCalibracionDTO` tampoco exponen estado |
| Retry presente | **No** | No hay ruta de reintento de calibraciones en el OpenAPI de DEV ni código de worker, scheduler o poller que trate calibraciones. La única ruta `…/reintentar` es de suministros |
| Timeout / ACK para calibración | **No** | El ACK de 30 s y el timeout HTTP de 35 s solo existen en el adaptador RF-23 (`mqtt_http_adapter.py`) |
| Feature flag desactivado | **No aplica** | No es una integración apagada por configuración: el caso de uso no tiene ningún camino hacia MQTT. `MQTT_BROKER_URL`/`MQTT_BROKER_TOKEN` solo los lee el adaptador RF-23 |
| Código local frente a `origin/dev` | Idéntico en `src/` | HEAD `ff5f6c9` frente a `origin/dev` `5d39b366` (rc.37, 2026-09-11): `git diff --stat -- src` vacío |

Pytest: **9 pruebas: 5 aprobadas (precondiciones) y 4 fallidas (oráculo TC-149)**.

| Prueba | Resultado |
| --- | --- |
| `test_rama_obligatoria` | PASSED |
| `test_dev_backend_accesible` | PASSED |
| `test_dev_endpoint_calibracion_desplegado` | PASSED |
| `test_codigo_local_equivale_a_origin_dev` | PASSED |
| `test_test_y_dev_comparten_contrato_de_calibracion` | PASSED |
| `test_oraculo_contrato_dev_expone_estado_de_propagacion` | **FAILED** — contrato sin campo de estado |
| `test_oraculo_calibracion_propaga_al_firmware_via_mqtt` | **FAILED** — el caso de uso no invoca MQTT |
| `test_oraculo_calibracion_persiste_estado_pendiente` | **FAILED** — el modelo no tiene estado |
| `test_oraculo_existe_reintento_automatico_de_calibraciones` | **FAILED** — no hay ruta ni código de reintento |

### Comparación TEST / DEV

| Elemento | TEST | DEV |
| --- | --- | --- |
| Endpoint calibración | Sí | Sí |
| Estado pending | No | No |
| MQTT | No disponible | No en calibración (solo RF-23) |
| Retry | No | No |
| TC149 ejecutable completo | No | **No** |

**No hay desfase de despliegue TEST ↔ DEV** en el componente de calibración: los
dos contratos coinciden en endpoint, respuestas, `CalibracionResponse`,
`RegistrarCalibracionDTO` y rutas. La ausencia no se explica por un TEST sin
desplegar: DEV tampoco tiene el flujo.

---

## TRAZABILIDAD RF-24 / G78

| Fuente | Qué dice sobre la calibración |
| --- | --- |
| RF-24 | Ajuste **lógico** aplicado al procesamiento de datos; **no modifica directamente el hardware**. Nivel de sensor, dispositivo activo, área correcta, rango válido, trazabilidad y restricción a Ingeniero de Campo o Administrador |
| Matriz G78 / TC-M09-149 | Añade la **propagación al firmware vía MQTT**, con `CALIBRACIÓN_PENDIENTE`, reintento y no pérdida cuando el firmware no responde |
| Documentación de implementación (`anotaciones/modulo_9/feature_rf24_rango_calibracion_mod9.md`) | «Se confirmó que no corresponde al broker MQTT (`BROKER-MQTT-SGPMP`): ese repo no tiene concepto de calibración […]. RF-24 es un caso de uso REST del backend» |
| Implementación DEV | Coherente con RF-24 y con esa nota: persiste la calibración y su auditoría; telemetría la aplica como `valor_ajustado = ganancia × crudo + offset` (`calibracion_m09_adapter.py`) |

El producto cumple la lectura de RF-24 como ajuste lógico, algo que G74 a G77
ya ejercitaron. Lo que no implementa es el comportamiento adicional que exige
la matriz G78. Según el paquete de esta evaluación (§43), un RF-24 básico que
guarda la calibración no basta para aprobar TC-149, así que el resultado es
DESAPROBADO. La discrepancia queda expuesta para que el triage decida entre
implementar la propagación o corregir la matriz.

---

## ACTOR

| Elemento | Valor |
| --- | --- |
| Actor funcional previsto | Ingeniero de Campo (`ingeniero@pecuaria.co`, y como alternativa `ingeniero.finca@pecuaria.co`); fallback autorizado: `admin.general@pecuaria.co` |
| Autenticación ejecutada | **No** |
| Motivo | La decisión no depende del actor. La ausencia es estructural: el contrato y el código no tienen el flujo para ningún rol. Sin POST justificado no hacía falta abrir sesión. Además, las credenciales DEV no se suministraron en esta sesión y adivinarlas está prohibido (§15) |
| Productor | No utilizado |
| Fincas / usuarios | No modificados; no se usó `PUT /usuarios/{id}/fincas` |

---

## DATOS UTILIZADOS

No se seleccionaron dispositivo, sensor, área ni valor de referencia en DEV. El
descubrimiento de datos solo tiene sentido para alimentar el POST funcional, y
ese POST no se ejecutó porque la verificación de implementación demostró que no
existe el flujo que ejercitaría. Ningún dato de DEV ni de TEST fue creado o
alterado.

---

## MQTT

| Elemento | Resultado |
| --- | --- |
| Flujo MQTT de calibración identificado | **No existe** |
| Cliente MQTT disponible | **No**: `paho-mqtt` no está instalado; `mosquitto_sub`/`mosquitto_pub`, MQTT.js y MQTTX tampoco. No se instaló nada |
| Broker DEV | No verificado por MQTT: no hay cliente ni configuración QA legítima de host, puerto, topic o credenciales. No hubo escaneo de puertos ni adivinación |
| Repositorio `BROKER-MQTT-SGPMP` local | **No utilizado**: está en la rama `develop`, no en `qa/juan-esteban-re-evaluacion-M02` (§16–§18). La copia `BROKER-MQTT-SGPMP-develop` no es un repositorio Git con rama verificable |
| Topic / ACK / timeout de calibración | No existen en el backend |
| Publicación observada | No aplica; no se generaron `mqtt-publicacion-inicial.json`, `mqtt-timeout.json` ni `mqtt-retry.json`, porque esa evidencia no existió |

La falta de cliente MQTT y de acceso al broker **no** es la base de la
decisión. Si el producto tuviera el flujo, esa carencia habría dejado el caso en
BLOCKED (`MQTT_CLIENT_MISSING`). La conclusión se apoya en que el backend DEV no
tiene ningún camino de código que publique una calibración, lo cual se
comprueba sin cliente MQTT.

---

## EJECUCIÓN

1. Git inicial en backend y frontend: rama correcta en ambos.
2. Fase 0 de solo lectura: revisión del código de calibración, MQTT, reintentos
   y schedulers; comparación HEAD frente a `origin/dev`.
3. Contratos OpenAPI desplegados en DEV y TEST (GET sin autenticación).
4. Harness Pytest `test_tc_m09_149.py`, que automatiza la verificación y emite
   log, JUnit XML y JSON de evidencia.
5. Checklist previo al POST: faltan condiciones esenciales (flujo MQTT, broker
   verificable, cliente, topic, ACK, timeout, pending, retry, mecanismo seguro
   de firmware sin respuesta). **POST no consumido.**
6. Escaneo de secretos y Git final.

Ejecución completa de Pytest: 9 pruebas en 3.69 s, 5 aprobadas y 4 fallidas.

---

## ESTADO PENDIENTE

No existe. `modulo9.calibraciones` no tiene columna de estado,
`CalibracionResponse` no expone ninguna y la entidad `Calibracion` es un evento
inmutable sin ciclo de vida. El producto no puede dejar una calibración en
`CALIBRACIÓN_PENDIENTE` ni en ningún equivalente (`PENDING`, `PENDIENTE`,
`SYNC_PENDING`…). El único `PENDIENTE` del dominio de dispositivos pertenece a
la configuración remota de RF-23.

---

## REINTENTO

No existe para calibraciones: no hay ruta de reintento, `retry_count`,
`next_retry_at`, worker, scheduler ni poller. Los mecanismos de reintento del
backend pertenecen a otros módulos (cola de exportación de auditoría y lotes de
eficiencia alimenticia).

---

## PERSISTENCIA

Sin escrituras de QA: 0 POST, 0 SQL y ninguna modificación de datos. El
comportamiento de persistencia de RF-24 (calibración y auditoría en la misma
transacción, con rollback ante fallo) ya fue verificado en G74 a G79 y no forma
parte del defecto. Como no hay propagación, la «solicitud no perdida» de la
matriz no tiene contraparte: la calibración se guarda de forma definitiva y no
existe una solicitud de propagación que conservar.

---

## ORIGEN DEL FALLO

| Origen | Resultado |
| --- | --- |
| Producto | **Sí**: el flujo que exige la matriz no está implementado en DEV |
| Desfase TEST ↔ DEV | No: los contratos coinciden |
| Infraestructura / broker caído | No es la causa; el backend no llama al broker para calibraciones |
| Feature flag | No: no hay camino de código condicionado |
| Error de prueba / automatización | No |
| Bloqueo QA (cliente MQTT, credenciales, datos) | Existe, pero no determina el resultado |

Checklist previo a declarar «no implementado» (§130):

| # | Pregunta | Respuesta |
| --- | --- | --- |
| 1 | ¿Se verificó DEV? | Sí: contrato desplegado y código `origin/dev` |
| 2 | ¿No es simplemente TEST sin despliegue? | Sí: DEV y TEST coinciden |
| 3 | ¿Broker operativo? | No verificable; no es causa, porque la calibración nunca llama al broker |
| 4 | ¿Cliente MQTT funciona? | No hay cliente; no es causa, porque la ausencia es visible sin él |
| 5 | ¿Datos válidos? | No aplica: la ausencia es independiente de los datos |
| 6 | ¿Actor correcto? | No aplica: la ausencia es independiente del rol |
| 7 | ¿Código/contrato DEV carece del flujo? | **Sí** |
| 8 | ¿No es simplemente un bloqueo de QA? | Sí: la conclusión no depende de los bloqueos QA |
| 9 | ¿No es infraestructura caída? | Sí: DEV responde 200 |

---

## CATEGORÍA / EQUIPO / ACCIÓN

- **Categoría:** FLUJO — Flujo / Proceso
- **Equipo responsable:** Desarrollo
- **Acción:** REPORTAR A DESARROLLO

## DEFECTO DETECTADO — DEBE REPORTARSE

| Campo | Valor |
| --- | --- |
| ID | ID pendiente de asignación según Registro de Errores vigente |
| Caso | TC-M09-149 (grupo TC-M09-G78) |
| Requerimiento | RF-24 — Calibración de dispositivos IoT · CU-05 |
| Ambiente | DEV (`https://sigab-backenddev-jpuya4-ea3a74-158-69-200-27.sslip.io/api-sgpmp`) |
| Título | La calibración de sensores no se propaga al firmware: no existe estado pendiente ni reintento cuando el firmware no responde |
| Categoría | FLUJO — Flujo / Proceso |
| Severidad | Pendiente de validar contra Registro de Errores vigente |
| Responsable | Desarrollo |
| Acción | REPORTAR A DESARROLLO |
| Actor | No aplica: la ausencia es independiente del rol (Ingeniero de Campo o Administrador) |
| Dispositivo / sensor / calibration_id | No aplica: no se creó ninguna calibración, porque el flujo no existe |
| Publish | Inexistente: `RegistrarCalibracionUseCase` no invoca `MqttPort` ni el broker |
| ACK | Inexistente para calibraciones |
| Timeout | Inexistente para calibraciones |
| Pending | Inexistente: sin columna ni campo de estado en modelo, entidad o contrato |
| Retry | Inexistente: sin ruta, worker ni scheduler |
| Persistencia | La calibración se persiste de forma definitiva al registrarse; no hay solicitud de propagación que conservar |
| Esperado (matriz) | Sensor válido + firmware sin respuesta → `CALIBRACIÓN_PENDIENTE` + reintento + solicitud no perdida |
| Obtenido | La calibración solo se registra en BD y la aplica telemetría; no hay propagación, estado ni reintento |
| Reproducibilidad | Determinista: se reproduce leyendo `GET /openapi.json` de DEV y el código de `origin/dev` (rc.37) |
| Nota para el triage | RF-24 describe la calibración como ajuste lógico que no modifica el hardware, y la nota de implementación de Desarrollo descarta el broker. Validar si corresponde implementar la propagación o actualizar la matriz G78 |
| Evidencias | `pytest-TC-M09-149.log`, `pytest-TC-M09-149.xml`, `TC-M09-149-evidencia.json` |

No se creó ningún ticket (Taiga, issue ni PR).

---

## EVIDENCIAS

En `RF-24/TC-M09-G78/EvaluacionV1/RESULTADOS/G78-EVAL-V1-20260913-002659/`:

| Archivo | Contenido |
| --- | --- |
| `pytest-TC-M09-149.log` | Salida completa de Pytest (`-v -rA`) |
| `pytest-TC-M09-149.xml` | JUnit XML: 9 pruebas, 4 fallidas, 0 errores |
| `TC-M09-149-evidencia.json` | Git y SHAs, contratos DEV/TEST, desfase, referencias MQTT en archivos de calibración, consumidores de `MqttPort`, columnas del modelo y resultados del oráculo |
| `seguridad-evidencias.json` | Escaneo final de secretos |
| `git-final.json` | Estado Git de cierre |
| `TC-M09-G78_resultado.md` | Este reporte |

Automatización: `EvaluacionV1/test_tc_m09_149.py` y `EvaluacionV1/README.md`.

---

## SEGURIDAD

- No se usaron contraseñas, tokens, cookies, credenciales MQTT ni cadenas de
  conexión: la verificación no requirió autenticación.
- El escaneo final de `EvaluacionV1/` busca `Authorization`, `Bearer`,
  `access_token`, `refresh_token`, `password`, `cookie`, `jwt` y formas de JWT;
  el detalle está en `seguridad-evidencias.json`.
- No hubo escaneo de puertos, fuerza bruta ni adivinación de credenciales.

---

## GIT FINAL

| Repositorio | Rama | SHA | Uso |
| --- | --- | --- | --- |
| sgpmp-backend | `qa/juan-esteban-re-evaluacion-M02` | `ff5f6c9f6161e46c94d3d6f325a7d07d80d84aa0` | Lectura de código y única zona escribible |
| SGPMP-FRONT-END-PWA | `qa/juan-esteban-re-evaluacion-M02` | `49966d244673eb44d0be61e7df25c27d460b2c1c` | Solo verificación de rama; sin uso |
| BROKER-MQTT-SGPMP | `develop` | `910ce8aa` | **No utilizado**: rama distinta a la obligatoria |

Estado de cierre detallado en `git-final.json`.

- Todos los archivos nuevos de esta evaluación están en
  `tests/Test_Testing/Test_Modulo9/RF-24/TC-M09-G78/EvaluacionV1/`.
- `git diff --stat` del backend está vacío: ningún archivo rastreado fue
  modificado.
- `pytest-TC-M09-149.log` existe en disco pero no aparece en
  `git ls-files --others --exclude-standard`, porque la regla `*.log` del
  `.gitignore` del backend (línea 34) lo ignora. Hay que tenerlo en cuenta al
  consolidar la evidencia.
- Cambio preexistente ajeno a TC-M09-G78: la carpeta sin seguimiento
  `TC-M09-G77/EvaluacionV2/`, de la reevaluación anterior.
- Cambio preexistente ajeno a TC-M09-G78: una carpeta vacía
  `TC-M09-G78/EvaluacionV2/` (creada el 2026-09-13 a las 00:17, antes de esta
  ejecución; Git no la lista por estar vacía). No se tocó.
- Frontend sin cambios.

No hubo commit, push, pull, merge, rebase, reset, clean, stash, checkout, cambio
de rama, tag ni PR. No se modificó código funcional, infraestructura, broker,
usuarios, fincas, dispositivos, sensores ni áreas. No hubo SQL, POST, conexión
MQTT, ACK fabricado ni estado pendiente fabricado.

**La ejecución se detiene aquí para revisión humana.**
