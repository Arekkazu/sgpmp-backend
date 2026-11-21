# TC-M09-G29 — REEVALUACIÓN V2

RF-17 — Configuración de Umbrales de Monitoreo y Niveles de Alerta Ambiental
Casos: TC-M09-62 (propagación hacia Nodo Edge) · TC-M09-63 (fallo de sincronización)
Responsable QA: Juan Esteban · RUN_ID: `G29-REEVAL-V2-20260913-014534` · Fecha local: 2026-09-13 · Entorno decisorio: **DEV**

---

## DECISIÓN GENERAL

### REEVALUACIÓN DESAPROBADA — DEFECTO DEL PRODUCTO / FUNCIONALIDAD NO IMPLEMENTADA

En DEV, que es el ambiente con MQTT, la configuración de umbrales RF-17 es un
flujo REST que solo escribe en base de datos y auditoría:

- **No publica** hacia MQTT ni hacia ningún Nodo Edge.
- **No tiene estado** «Pendiente de Sincronización».
- **No declara ni implementa** el HTTP 500 con la configuración central
  guardada.
- **No existe una vía** para observar la configuración efectiva de un Edge.

Así lo confirman el contrato desplegado en DEV, el código de `origin/dev` y los
umbrales reales consultados en DEV con un Administrador autenticado. Sin ese
flujo, ninguno de los dos originales puede cumplirse.

| Caso | V1 | V2 | Ambiente decisorio | Motivo | Categoría | Equipo | Acción |
| --- | --- | --- | --- | --- | --- | --- | --- |
| TC-M09-62 | BLOCKED (TEST sin MQTT/Edge, sin cliente MQTT) | **DESAPROBADO — FUNCIONALIDAD NO IMPLEMENTADA** | DEV | Guardar un umbral no dispara publicación ni sincronización hacia el Edge: los casos de uso de crear y editar no invocan MQTT, broker ni Nodo Edge; no hay ACK ni estado sincronizado | FLUJO — Flujo / Proceso | Desarrollo | **REPORTAR A DESARROLLO** |
| TC-M09-63 | BLOCKED (sin Edge offline seguro en TEST) | **DESAPROBADO — FUNCIONALIDAD NO IMPLEMENTADA** | DEV | No existe intento de sincronización que pueda fallar, ni estado pendiente, ni respuesta 500 con la configuración guardada (el contrato solo declara 201/200/401/403/404/409/412/422) | FLUJO — Flujo / Proceso | Desarrollo | **REPORTAR A DESARROLLO** |

**Escrituras: 0.** No se ejecutó ningún POST ni PATCH de umbral. La checklist
previa (§145 y §147) tenía condiciones esenciales en «No»: flujo MQTT de RF-17,
topic, Edge identificable, estado y ACK. Una escritura habría creado o alterado
un umbral sin nada que observar después.

---

## RESUMEN V1

Evidencia V1: `RF-17/TC-M09-G29/RESULTADOS/run-20260905/` (solo lectura, intacta).

| Aspecto | TC-M09-62 | TC-M09-63 |
| --- | --- | --- |
| ¿Se ejecutó? | No; solo revisión de viabilidad | No; solo revisión de viabilidad |
| Ambiente | TEST | TEST |
| ¿MQTT observado / publish? | No | No |
| ¿Edge real? | No: solo `NodoEdgeStubAdapter` (stub) | No |
| ¿Aplicación en Edge comprobada? | No | No |
| ¿Cómo se produjo el fallo? | No aplica | No hubo escenario: no existía un mecanismo seguro para dejar un Edge offline |
| ¿Estado pendiente / HTTP 500? | No aplica | No observados (sin ejecución) |
| Escrituras | 0/2 | 0/2 |
| Resultado | **BLOCKED — MQTT_TEST_INFRASTRUCTURE_NOT_AVAILABLE** (y `MQTT_CLIENT_MISSING`) | **BLOCKED — NO EXISTE MECANISMO SEGURO/AUTORIZADO PARA INDUCIR EDGE OFFLINE** |
| Categoría / equipo V1 | INFRAESTRUC → AIoT e Implementación | INFRAESTRUC → AIoT e Implementación |
| Incidencia | Ninguna de producto. V1 recomendó a AIoT confirmar si G29 pertenece a RF-17 o a RF-23 y, si RF-17 lo exige, crear un defecto FLUJO para Desarrollo | Ídem |

V1 ya había detectado en código que los casos de uso de umbrales no referencian
`mqtt`, `broker`, `edge`, sincronización ni `ack`, y que `MqttHttpAdapter`
pertenece a RF-23. No lo clasificó como defecto porque se evaluó en TEST y
quedó pendiente de confirmar el alcance.

## LIMITACIONES V1

La evaluación anterior no podía verificar completamente el alcance de TC62 y
TC63 porque MQTT no está disponible en TEST. Tampoco había cliente MQTT ni un
Edge observable. Su resultado era una **limitación de entorno y prueba, no un
defecto demostrado**. V2 traslada la verificación al ambiente adecuado (DEV).
Por tanto, V2 **no** «verifica una corrección»: registra por primera vez un
defecto demostrado en el ambiente correcto.

---

## ENTORNO

| Elemento | Valor |
| --- | --- |
| Ambiente decisorio | **DEV** — `https://sigab-backenddev-jpuya4-ea3a74-158-69-200-27.sslip.io/api-sgpmp` (`/health` 200, `/openapi.json` 200) |
| TEST (solo comparación REST) | URL suministrada `http://…/api-sgpmp-test`: 404 del proxy. Por `https://` responde 200. Contrato RF-17 idéntico a DEV |
| Frontend | No utilizado |
| Herramienta | Pytest 9.0.3 (Python 3.13.13): verificación de implementación de solo lectura |
| Cliente MQTT | **No disponible**: `paho-mqtt`, `mosquitto_sub`, `mosquitto_pub`, `mqttx`, CLI `mqtt` y MQTT Explorer ausentes. No se instaló nada |
| Broker DEV | No consultado: no hay cliente ni configuración QA legítima, y el backend no lo usa para RF-17. Sin escaneo de puertos ni adivinación |
| Repositorio `BROKER-MQTT-SGPMP` | No utilizado: la copia local está en la rama `develop`, no en la obligatoria |
| SQL / PostgreSQL | No utilizado |

---

## GIT / SHAs

| Repositorio | Rama | SHA | Uso |
| --- | --- | --- | --- |
| sgpmp-backend | `qa/juan-esteban-re-evaluacion-M02` | `ff5f6c9f6161e46c94d3d6f325a7d07d80d84aa0` | Lectura de código y única zona escribible (`TC-M09-G29/EvaluacionV2/`) |
| `origin/dev` (referencia local) | — | `5d39b366` (rc.37, 2026-09-11) | `git diff --stat HEAD origin/dev -- src` vacío: el código revisado equivale a `dev` |

---

## ACTOR

| Elemento | Valor |
| --- | --- |
| Usuario DEV | `admin.general@pecuaria.co` |
| Rol (`GET /usuarios/me`) | **Administrador**, cuenta `Activo` |
| Permisos recurso 20 (umbrales) | `[1, 2, 3, 4]` |
| Uso | Solo login y GET (umbrales, especies, auditoría); ninguna escritura |
| Veterinario / Ingeniero / Productor | No utilizados |
| Credenciales | Contraseña solo por variable de proceso; token no persistido |

---

## IMPLEMENTACIÓN MQTT/EDGE

Flujo real en DEV, según el código:

`Cambio RF-17 (POST /configuracion/umbrales o PATCH /configuracion/umbrales/{id})`
→ `_validar_rangos` → persistencia del umbral y sus niveles → auditoría →
**respuesta 201/200. Fin del flujo.**

No existe publish MQTT, Nodo Edge destino, ACK, timeout, estado final de
sincronización, reintento ni HTTP 500 por fallo de propagación.

| Elemento buscado | Hallazgo en DEV |
| --- | --- |
| Publicación MQTT desde RF-17 | **No existe.** `registrar_umbral_use_case.py`, `editar_umbral_use_case.py`, `umbral_router.py`, `umbral_schema.py` y `umbral_ambiental.py` no contienen referencias a MQTT, broker, Nodo Edge, publicación ni sincronización |
| Integraciones MQTT existentes | Solo RF-23: `MqttPort` lo consumen únicamente `configurar_remotamente_use_case.py` y `dispositivo_iot_router.py` (`POST /configuracion/dispositivos-iot/{id}/configurar`) |
| Nodo Edge | `NodoEdgePort` solo lo usa el motor IA (`prediction`), mediante `NodoEdgeStubAdapter`, un «Stub temporal» cuyo `hay_nodos_activos()` devuelve `True`. No se relaciona con umbrales |
| Topic / QoS / ACK / timeout | No existen para umbrales |
| Estado de sincronización | No existe: `UmbralAmbientalResponse` expone `id_umbral_ambiental, id_especie, id_variable_ambiental, unidad_medida, valor_min, valor_max, es_activo, fecha_actualizacion, niveles` |
| HTTP de fallo | POST: `201, 401, 403, 404, 409, 422`; PATCH: `200, 401, 403, 404, 412, 422`. Ningún 500 declarado |
| Endpoints Edge | Solo `/iot/eventos-edge` (entrada de eventos Edge → servidor, módulo de telemetría); no expone configuración efectiva de umbrales |
| Feature flag | No aplica: no hay ningún camino de código condicionado por configuración |

**Evidencia en tiempo de ejecución (DEV, GET autenticado):** umbrales reales de
Cachama Blanca (2, ej. #10) y Camarón Blanco (3, ej. #7) devuelven exactamente
los campos del contrato, sin estado de sincronización. La auditoría del umbral
#10 responde 200. No hay dato de sincronización que observar.

---

## DATOS UTILIZADOS

No se seleccionó una configuración para escribir. El discovery de datos solo
sirve para alimentar la escritura de TC62/TC63, y esta no se ejecutó porque no
existe el flujo que ejercitaría. Los datos consultados (5 especies activas en
DEV y los umbrales #10 y #7) se usaron solo para comprobar la forma real del
recurso. Ningún dato de DEV ni de TEST fue creado o alterado.

---

## TC-M09-62 — PROPAGACIÓN EXITOSA

**DESAPROBADO — DEFECTO DEL PRODUCTO / FUNCIONALIDAD NO IMPLEMENTADA** · DEV · 0 escrituras

| Etapa | Resultado |
| --- | --- |
| Central BEFORE | Observable por GET (ej. #10 Cachama Blanca: 0.00–100.00, activo); sin campo de versión ni de sincronización |
| Cambio válido | No ejecutado (checklist §145: flujo MQTT RF-17, topic y Edge identificable = No) |
| Central AFTER | No aplica |
| MQTT publish | **No**: no existe publicación en el flujo RF-17 |
| Edge receive/ACK | **No aplica por contrato**: no existe ACK ni Edge destino para umbrales |
| Edge AFTER | No observable: no existe vía |
| Sincronizado | **No**: no existe estado de sincronización |

## TC-M09-63 — FALLO DE SINCRONIZACIÓN

**DESAPROBADO — DEFECTO DEL PRODUCTO / FUNCIONALIDAD NO IMPLEMENTADA** · DEV · 0 escrituras

| Etapa | Resultado |
| --- | --- |
| Edge disponible antes | No aplica: no hay Edge asociado a umbrales |
| Edge BEFORE | No observable |
| Central BEFORE | Observable por GET |
| Nueva config válida | No ejecutada (checklist §147: mecanismo de timeout, estado pendiente y HTTP contractual = No) |
| Intento MQTT | **No**: el flujo no intenta sincronizar |
| Edge responde | No aplica |
| HTTP | **500 no implementado**: el contrato no lo declara y el código no tiene esa rama |
| Central AFTER | No aplica |
| Estado | **Pendiente no implementado** |
| Edge AFTER | No observable |

---

## ESTADO CENTRAL

La configuración central se gestiona correctamente como REST: umbrales y
niveles persistidos, auditados y consultables, verificado en G22 V2 y G24 V2.
Lo que falta es el estado de sincronización asociado.

`Configuración central conservada ante fallo de sincronización: No aplica (no existe sincronización)`

`Estado pending: No (no implementado)`

## ESTADO EDGE

`Edge conserva configuración previa: No verificable (no existe Edge destino ni vía de observación para umbrales)`

No se infiere ningún valor efectivo del Edge a partir del valor central.

## MQTT

No se inició observador MQTT porque no hay cliente MQTT disponible y, sobre
todo, porque el flujo RF-17 no publica. Esa ausencia se demuestra en el código
y en el contrato, sin necesidad de cliente. No se crearon archivos
`mqtt-publish`, `edge-ack`, `edge-before` ni `edge-after`, porque esa evidencia
no existió.

Si el flujo existiera, la falta de cliente MQTT habría dejado el caso en
`BLOCKED — MQTT_CLIENT_MISSING`. No es la base de la decisión.

---

## COMPARACIÓN V1 VS V2

| Caso | V1 | V2 | Ambiente V1 | Ambiente V2 | Motivo |
| --- | --- | --- | --- | --- | --- |
| TC62 | BLOCKED | DESAPROBADO — FUNCIONALIDAD NO IMPLEMENTADA | TEST | DEV | V1 no podía observar MQTT/Edge en TEST. En DEV se confirma que RF-17 no publica ni sincroniza |
| TC63 | BLOCKED | DESAPROBADO — FUNCIONALIDAD NO IMPLEMENTADA | TEST | DEV | V1 no disponía de un Edge offline seguro. En DEV se confirma que no existen el estado pendiente ni el 500 con la configuración guardada |

---

## COMPARACIÓN TEST VS DEV

| Elemento | TEST | DEV |
| --- | --- | --- |
| RF-17 REST | Sí (idéntico a DEV: operaciones, respuestas y `UmbralAmbientalResponse`) | Sí |
| MQTT disponible | No | No para RF-17 (solo RF-23 usa el broker vía HTTP) |
| Edge observable | No | No |
| TC62 ejecutable completo | No | No: funcionalidad no implementada |
| TC63 ejecutable completo | No | No: funcionalidad no implementada |

**No hay desfase de despliegue TEST ↔ DEV.** El resultado no se debe a la
ausencia de MQTT en TEST: DEV tampoco implementa el flujo.

---

## ORIGEN DE FALLOS

### TC-M09-62 y TC-M09-63

`Producto: Sí (funcionalidad no implementada en DEV)`

`Automatización: No`

`Entorno: No`

`Bloqueo: No determinante (sin cliente MQTT ni Edge observable, pero la ausencia del flujo se demuestra sin ellos)`

`Categoría: FLUJO — Flujo / Proceso`

`Equipo: Desarrollo`

`Acción: REPORTAR A DESARROLLO`

Checklist antes de declarar «no implementado» (§19 y §149):

| # | Pregunta | Respuesta |
| --- | --- | --- |
| 1 | ¿Actor correcto? | Sí — Administrador DEV autenticado, permisos del recurso 20 |
| 2 | ¿Se verificó DEV? | Sí — contrato desplegado, código `origin/dev` y GET en tiempo de ejecución |
| 3 | ¿No es solo TEST sin despliegue? | Sí — TEST y DEV coinciden |
| 4 | ¿Código/contrato DEV carece del flujo? | **Sí** — sin publish, sin Edge, sin estado pendiente, sin 500 |
| 5 | ¿Feature flag? | No — no hay camino condicionado |
| 6 | ¿Error QA descartado? | Sí — la conclusión no depende de datos, topic ni observador |
| 7 | ¿Infraestructura descartada? | Sí — DEV responde 200; el broker no interviene en RF-17 |
| 8 | ¿Contradice RF-17? | Sí — RF-17 exige propagación a los dispositivos IoT de campo y, ante fallo, «Pendiente de Sincronización» + HTTP 500 con la configuración guardada |

---

## CATEGORÍA / EQUIPO / ACCIÓN

| Hallazgo | Categoría | Equipo | Acción |
| --- | --- | --- | --- |
| RF-17 no propaga umbrales al Nodo Edge (TC-62) | FLUJO — Flujo / Proceso | Desarrollo | **REPORTAR A DESARROLLO** |
| RF-17 no gestiona el fallo de sincronización: sin estado pendiente ni HTTP 500 con la configuración conservada (TC-63) | FLUJO — Flujo / Proceso | Desarrollo | **REPORTAR A DESARROLLO** |
| Observación: sin cliente MQTT aprobado ni Edge QA observable/desconectable | Capacidad de prueba (no defecto) | Implementación / AIoT | Informar para cuando exista el flujo; no bloquea esta decisión |

---

## INCIDENCIAS

V1 no registró incidencia de producto (su resultado fue BLOCKED de entorno), así
que no hay ID que reutilizar. Se prepara una **incidencia nueva** que cubre
ambos originales.

| Campo | Valor |
| --- | --- |
| ID | ID pendiente de asignación según Registro de Errores vigente |
| Casos | TC-M09-62, TC-M09-63 (grupo TC-M09-G29) · RF-17 |
| Ambiente | DEV (`origin/dev` rc.37; contrato idéntico en TEST) |
| Título | La configuración de umbrales RF-17 no se propaga a los Nodos Edge y no gestiona el fallo de sincronización (sin estado «Pendiente de Sincronización» ni HTTP 500 con la configuración guardada) |
| Categoría | FLUJO — Flujo / Proceso |
| Severidad | Pendiente de validar contra Registro de Errores vigente |
| Responsable | Desarrollo |
| Acción | REPORTAR A DESARROLLO |
| Actor | Administrador DEV `admin.general@pecuaria.co` (autorizado RF-17) |
| Esperado | TC62: guardar → publicar/sincronizar → Edge recibe y usa la nueva configuración → estado sincronizado. TC63: guardar → intento fallido → configuración central conservada + «Pendiente de Sincronización» + HTTP 500 → Edge conserva los valores previos |
| Obtenido | Guardar un umbral solo persiste y audita (201/200). No hay publicación, ACK, estado de sincronización ni rama de 500; el único Nodo Edge del backend es un stub del motor IA |
| Evidencia | `pytest-TC-M09-G29-v2.log/.xml` (4 controles de oráculo fallidos), `TC-M09-G29-evidencia-v2.json` (contratos DEV/TEST, referencias de código, consumidores de `MqttPort`/`NodoEdgePort`, umbrales reales DEV) |
| Reproducibilidad | Determinista: leer `GET /openapi.json` de DEV, los casos de uso de umbrales en `origin/dev` y `GET /configuracion/umbrales?id_especie=…` en DEV |
| Nota para triage | V1 planteó a AIoT si G29 corresponde a RF-17 o a RF-23 (la única integración MQTT existente es RF-23). El texto de RF-17 aplicado en esta reevaluación exige explícitamente la propagación y el estado pendiente, por eso se clasifica como funcionalidad no implementada |

No se creó ningún ticket (Taiga, issue ni PR).

---

## EVIDENCIAS

En `RF-17/TC-M09-G29/EvaluacionV2/RESULTADOS/G29-REEVAL-V2-20260913-014534/`:

| Archivo | Contenido |
| --- | --- |
| `pytest-TC-M09-G29-v2.log` | Salida completa de Pytest: 9 pruebas, 5 aprobadas (precondiciones) y 4 fallidas (oráculo) |
| `pytest-TC-M09-G29-v2.xml` | JUnit XML |
| `TC-M09-G29-evidencia-v2.json` | Git/SHAs, cliente MQTT, contratos DEV/TEST, desfase, código `origin/dev`, runtime DEV (actor, umbrales reales, auditoría) y oráculo |
| `seguridad-evidencias.json` · `git-final.json` | Escaneo de secretos y estado Git |
| `TC-M09-G29_reevaluacion_V2.md` | Este reporte |

Automatización: `EvaluacionV2/test_tc_m09_g29.py` y `EvaluacionV2/README.md`.
Nota: la regla `*.log` del `.gitignore` del backend ignora el archivo `.log`,
que existe en disco.

---

## SEGURIDAD

- La contraseña del Administrador DEV se usó solo como variable de proceso
  (`DEV_ADMIN_PASSWORD`); el token vivió en memoria y la evidencia se sanea (sin
  JWT).
- Sin credenciales MQTT, cadenas de conexión ni cookies.
- Sin escaneo de puertos, fuerza bruta ni adivinación; sin conexión al broker;
  sin ACK fabricado ni estado modificado.
- Detalle del escaneo en `seguridad-evidencias.json`.

---

## GIT FINAL

Detalle en `git-final.json`.

- Backend (`qa/juan-esteban-re-evaluacion-M02`, `ff5f6c9`): `git diff --stat`
  vacío. Todos los archivos nuevos están en
  `tests/Test_Testing/Test_Modulo9/RF-17/TC-M09-G29/EvaluacionV2/`.
- Cambios preexistentes ajenos a TC-M09-G29 EvaluacionV2 (carpetas sin
  seguimiento de evaluaciones anteriores): `RF-17/TC-M09-G24/EvaluacionV2/`,
  `RF-24/TC-M09-G77/EvaluacionV2/` y `RF-24/TC-M09-G78/EvaluacionV1/`. No se
  tocaron.
- V1 de G29 intacta. Sin commit, push, pull, merge, rebase, reset, clean,
  stash, checkout, cambio de rama, tag ni PR. Sin cambios en código, Edge,
  broker, infraestructura ni dependencias. Sin SQL ni cleanup.

**La ejecución se detiene aquí para revisión humana. No se avanza a otro caso.**
