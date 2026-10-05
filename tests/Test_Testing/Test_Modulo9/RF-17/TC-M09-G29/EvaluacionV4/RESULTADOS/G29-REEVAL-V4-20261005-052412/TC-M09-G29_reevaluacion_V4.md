# TC-M09-G29 — REEVALUACIÓN V4

RF-17 — Configuración de Umbrales de Monitoreo y Niveles de Alerta Ambiental
CU-03 — Configurar Umbrales y Alertas Ambientales por Especie

Grupo: Propagación y sincronización de umbrales hacia el Nodo Edge (incluye fallo)
Casos: TC-M09-62 (propagación hacia Nodo Edge) · TC-M09-63 (fallo de sincronización)
Tipo: Integración / Disponibilidad / Integridad
Componente: Backend + MQTT/Edge
Responsable QA: Juan Esteban · Prioridad: Alta
RUN_ID: `G29-REEVAL-V4-20261005-052412`
Fecha: 2026-10-05
Entorno decisorio: **DEV**

---

## DECISIÓN GENERAL

### TC-M09-62 — RECHAZADO. La propagación de umbrales hacia el Nodo Edge sigue sin estar implementada.

El backend desplegado en DEV continúa resolviendo la propagación de RF-17 con un adaptador
stub. `umbral_router.py` inyecta `EdgeSincronizacionStubAdapter()` tanto en el POST como en el
PATCH de umbrales, y ese adaptador devuelve **siempre** `PENDIENTE` sin contactar el broker.
No existe destino Edge, ni topic de umbrales, ni ACK, ni timeout. En consecuencia **no se
emitió la escritura oficial**: el gate de ejecutabilidad la detuvo antes, porque ninguna
escritura podría haber aportado evidencia de propagación real.

### TC-M09-63 — NO EJECUTADA.

Pendiente de coordinación con AIoT para disponer de una ventana controlada de indisponibilidad
del Nodo Edge. QA no está autorizado a desconectar el Raspberry, el Gateway ni los nodos. No
se simuló el fallo por ninguna vía alternativa.

### Estado general del grupo: NO APROBADO — PARCIALMENTE EJECUTADO.

| Caso | Resultado V4 | Escrituras | Ambiente |
| --- | --- | ---: | --- |
| TC-M09-62 | **RECHAZADO** (sin escritura: gate de ejecutabilidad) | 0 | DEV |
| TC-M09-63 | **NO EJECUTADA** — pendiente de coordinación con AIoT | 0 | — |
| **Grupo TC-M09-G29** | **NO APROBADO / PARCIALMENTE EJECUTADO** | **0** | DEV |

Las dos decisiones son independientes: TC-M09-62 tiene un resultado funcional real y adverso;
TC-M09-63 no tiene resultado porque no se ejecutó.

---

## RESUMEN DEL RESULTADO

**Escrituras funcionales: 0.** 0 SQL de escritura, 0 publicaciones MQTT, 0 cambios de
infraestructura, 0 cambios en el broker, 0 cambios de gateway, 0 desconexiones de hardware.

El preflight encontró que las cuatro primeras condiciones del gate se cumplen y las tres
últimas no:

| Condición del gate | Resultado | Observación |
| --- | --- | --- |
| A. DEV disponible | **Sí** | `/health` 200, `/openapi.json` 200 (versión 1.0.0) |
| B. El actor puede ejecutar RF-17 | **Sí** | Rol Administrador, recurso 20 `umbrales_ambientales` con acciones 1, 2, 3 y 4 |
| C. Fixture funcional válido | **Sí** | Finca, área, especies activas y variables ambientales descubiertas en runtime |
| D. Nodo/Edge válido | **Sí** | `ESP32PRUEBA2` existe, activo, en `Piscina-Cam-01` y colgado del gateway del fixture |
| E. RF-17 intenta propagación **real** | **No** | El único implementador del puerto es el stub; devuelve `PENDIENTE` sin transporte |
| F. Evidencia de recepción/aplicación identificable | **No** | Sin destino, sin topic, sin ACK: no hay nada que observar en el Edge |
| G. Verificación posterior razonable | **No** | Tras la escritura solo podría comprobarse el `PENDIENTE` central, que ya es conocido |

Por lo tanto el bloqueo **no** proviene del entorno, ni de los permisos, ni del fixture, ni del
hardware AIoT: los cuatro estaban disponibles. Proviene del producto.

Dos observaciones de runtime sostienen el mismo diagnóstico sin necesidad de escribir:

- **Censo de sincronización en DEV:** 10 umbrales activos, **10 en `PENDIENTE`**, **0** con
  `fecha_ultima_sincronizacion`, **0** con `motivo_fallo_sincronizacion`. Ningún umbral de DEV
  ha alcanzado nunca el estado `APLICADA`. El comportamiento desplegado coincide exactamente
  con el stub revisado en código.
- **Coincidencia código ↔ despliegue:** `git diff --stat HEAD origin/dev -- src/configuration/`
  devuelve vacío, de modo que el código inspeccionado es el que está desplegado en DEV.

---

## ANTECEDENTES

| Evaluación | RUN / evidencia | Ambiente | TC-M09-62 | TC-M09-63 | Escrituras |
| --- | --- | --- | --- | --- | ---: |
| **V1** | `RESULTADOS/run-20260905/` | TEST | BLOQUEADO — infraestructura MQTT/Edge no disponible en TEST y sin cliente MQTT | BLOQUEADO — sin mecanismo autorizado para inducir Edge offline | 0 |
| **V2** | `EvaluacionV2/RESULTADOS/G29-REEVAL-V2-20260913-014534/` | DEV | DESAPROBADO — funcionalidad no implementada: guardar un umbral no disparaba ninguna propagación | DESAPROBADO — no existía intento de sincronización que pudiera fallar, ni estado pendiente, ni 500 | 0 |
| **V3** | `EvaluacionV3/RESULTADOS/G29-REEVAL-V3-20260926-013154/` | DEV | RECHAZADO — ya existía intento de propagación, pero contra `EdgeSincronizacionStubAdapter`, que devuelve siempre `PENDIENTE` | RECHAZADO — el flujo de fallo no puede demostrarse porque no hay integración real que pueda fallar | 0 |

V1, V2 y V3 se conservan intactas y en solo lectura. El avance parcial que V3 reconoció —el
estado de sincronización, el motivo del fallo y el HTTP 500 del caso de uso— sigue presente en
V4; lo que no ha cambiado es la propagación misma.

---

## ENTORNO

| Elemento | Valor |
| --- | --- |
| Ambiente decisorio | **DEV** |
| Backend DEV | `https://api.inmero.co/back-sigab-dev` |
| Frontend DEV | `https://dev.inmero.co/` |
| Broker DEV | `https://api.inmero.co/broker-sigab-dev` |
| `GET /health` | 200 · `{"status":"ok"}` |
| `GET /openapi.json` | 200 · versión 1.0.0 |
| Rama QA (backend y frontend) | `qa/juan-esteban-cuarta-evaluacion-M09-y-M02` |
| HEAD backend | `0371f2ec1d97ddfe7f3f33526d0db071d016e6ea` |
| HEAD frontend | `cd3af47c07302f7310b17e6800642aab2253f479` |
| `HEAD...origin/test` backend | `0 0` (sin divergencia) |
| `HEAD...origin/test` frontend | `2 0` |
| `HEAD` vs `origin/dev` en `src/configuration/` | sin diferencias |

TEST no se utilizó como evidencia decisoria. El broker DEV no expone una raíz ni un `/health`
HTTP consultables (`404` en ambos); no se sondearon puertos ni se adivinaron rutas, topics ni
credenciales.

Contrato de RF-17 publicado en DEV:

| Ruta | Métodos |
| --- | --- |
| `/configuracion/umbrales` | `GET`, `POST` |
| `/configuracion/umbrales/{id_umbral_ambiental}` | `PATCH` |
| `/configuracion/umbrales/{id_umbral_ambiental}/desactivar` | `PATCH` |
| `/configuracion/umbrales/{id_umbral_ambiental}/auditoria` | `GET` |

`UmbralAmbientalResponse` expone `estado_sincronizacion`, `fecha_ultima_sincronizacion` y
`motivo_fallo_sincronizacion`. El contrato **no** declara destino Edge, topic, payload
publicado ni mecánica de ACK.

---

## ACTOR / IDENTIDAD TÉCNICA

| Campo | Valor |
| --- | --- |
| Correo | `admin.dev@gmail.com` |
| `id_usuario` | 50 |
| Nombre | Admin Camila |
| Rol | Administrador |
| Estado de cuenta | Activo |
| Fincas asignadas | `[]` (alcance no limitado por finca) |
| Permisos sobre recurso 20 `umbrales_ambientales` | acciones 1 (CREATE), 2 (READ), 3 (UPDATE), 4 (DESACTIVAR) |

La contraseña se tomó exclusivamente de la variable de entorno `DEV_ADMIN_PASSWORD` y no
aparece en ningún artefacto de este RUN. No se persistieron JWT, cookies de sesión, cabeceras
`Authorization` ni credenciales MQTT.

---

## CONFIGURACIÓN UTILIZADA / FIXTURE

Todos los identificadores se descubrieron en runtime; no se reutilizó ningún ID histórico.

### Fixture AIoT suministrado por los líderes

| Elemento | Valor descubierto | Estado |
| --- | --- | --- |
| Finca | `Camaronera Costa Azul` — `id_finca` **3** | activa |
| Área productiva | `Piscina-Cam-01` — `id_infraestructura` **6**, tipo Estanque, 5000.00 m², «Estanque de engorde de camarón blanco con recirculación parcial» | activa |
| Gateway | `DISPOSITIVOCAMARONERA41` — `id_dispositivo_iot` **38**, tipo `GATEWAY_EDGE`, en área 6 | activo |
| Nodo seleccionado | `ESP32PRUEBA2` — `id_dispositivo_iot` **41**, tipo `SENSOR_AMBIENTAL`, área 6, `id_dispositivo_gateway` 38 | activo |
| Nodos no utilizados | `ESP32PRUEBA3` (id 43) y `QA-G69-131-358` (id 33), ambos colgados del gateway 38 | activos |

Se seleccionó **un solo nodo**, respetando la preferencia indicada: `ESP32PRUEBA2`. Los otros
dos no se utilizaron.

**Sobre el estado operativo de los nodos.** El estado lo gobierna la máquina de estados por
heartbeat y alterna automáticamente `ACTIVO` ⇄ `SIN_SEÑAL`. Durante el preflight se observó al
gateway y a los tres nodos en `ACTIVO`, con último contacto a las 05:17 UTC, y minutos después
el sistema registró la transición automática a `SIN_SEÑAL` (05:22 UTC, nota «Transición
automática por evaluación periódica (sin heartbeat)»). Por eso el estado instantáneo no se usó
como criterio de descarte del fixture: el nodo se consideró apto por existencia, actividad,
pertenencia al área y relación con el gateway. La credencial MQTT del gateway figura
`habilitada` y `conectada` (sus valores no se registraron: son secretos). Es decir, **la
infraestructura AIoT estaba operativa y no fue el factor limitante**.

### Catálogo funcional y la cuestión de «Bovino»

La matriz histórica define el dato de TC-M09-62 como «Nuevos umbrales para Bovino».

**En DEV no existe la especie Bovino.** Las especies activas son `Camarón Blanco` (3),
`Trucha Arcoíris` (2), `Cachama Blanca` (4), `Mojarra Plateada` (5), `Tilapia` (10) y `Prueba`
(12) — todas acuícolas. La infraestructura AIoT suministrada corresponde a un estanque de
engorde de camarón, por lo que la especie semánticamente equivalente para este fixture sería
`Camarón Blanco` (`id_especie` 3), que ya tiene tres umbrales activos (variables Temperatura
del agua, Amoniaco total y Salinidad).

No se inventó ninguna relación entre Bovino y la camaronera. La sustitución de especie queda
**identificada y documentada, pero no utilizada**: al detenerse el gate antes de la escritura,
no se llegó a configurar ningún umbral, de modo que en V4 no hubo cambio de dato efectivo.

### Estado central de los umbrales en DEV (solo lectura)

| `id_umbral` | `id_especie` | `id_variable` | Rango | Activo | `estado_sincronizacion` | `fecha_ultima_sincronizacion` |
| ---: | ---: | ---: | --- | --- | --- | --- |
| 4 | 2 | 1 | 0.00–100.00 °C | sí | `PENDIENTE` | `null` |
| 5 | 2 | 2 | 0.00–100.00 pH | sí | `PENDIENTE` | `null` |
| 6 | 2 | 3 | 0.00–100.00 mg/L | sí | `PENDIENTE` | `null` |
| 7 | 3 | 1 | 0.00–100.00 °C | sí | `PENDIENTE` | `null` |
| 8 | 3 | 6 | 0.00–100.00 ppt | sí | `PENDIENTE` | `null` |
| 9 | 3 | 4 | 0.00–100.00 mg/L | sí | `PENDIENTE` | `null` |
| 10 | 4 | 1 | 0.00–100.00 °C | sí | `PENDIENTE` | `null` |
| 11 | 4 | 3 | 0.00–100.00 mg/L | sí | `PENDIENTE` | `null` |
| 12 | 5 | 1 | 0.00–100.00 °C | sí | `PENDIENTE` | `null` |
| 13 | 5 | 2 | 0.00–100.00 pH | sí | `PENDIENTE` | `null` |

---

## TC-M09-62 — PROPAGACIÓN HACIA NODO EDGE

**Veredicto: RECHAZADO.** Escrituras funcionales: **0**.

### PRE — estado previo (solo lectura)

Capturado en `preflight.json`: actor, ambiente, SHA de ambos repositorios, fixture
seleccionado, catálogo de especies y variables, los 10 umbrales centrales con su estado de
sincronización, el estado operativo e historial de transiciones del gateway y de los tres
nodos, y el historial de configuraciones remotas del nodo seleccionado.

### Operación — no emitida

No se ejecutó POST ni PATCH de umbral. El gate de ejecutabilidad lo impidió y **esa decisión
es parte del procedimiento, no un fallo de ejecución**: el paquete de instrucciones ordena
detenerse antes de la escritura si se comprueba inequívocamente que el flujo termina en el
stub. Al no haber operación, no hay endpoint, payload, HTTP, `id_umbral`,
`estado_sincronizacion` ni `fecha_ultima_sincronizacion` que registrar. Tampoco hubo
reintentos ni reconciliación, porque no hubo primera llamada.

### Resultado central

Sin cambios. Los 10 umbrales de DEV permanecen tal como se leyeron en el PRE.

### Evidencia MQTT

**No obtenida — y no existe por esta vía.** La cadena del código desplegado es:

```
POST /configuracion/umbrales            PATCH /configuracion/umbrales/{id}
        ↓                                        ↓
RegistrarUmbralUseCase                   EditarUmbralUseCase
        ↓                                        ↓
   edge_port.propagar_umbral(id_especie, id_variable_ambiental, payload)
        ↓
EdgeSincronizacionStubAdapter  →  ResultadoEnvioMqtt(estado="PENDIENTE")
        ↓
marcar_pendiente_sincronizacion()  →  201 / 200 con estado_sincronizacion=PENDIENTE
```

Hechos verificados en `origin/dev`, que es el código desplegado:

- `umbral_router.py:73` y `umbral_router.py:154` inyectan `EdgeSincronizacionStubAdapter()` en
  el POST y en el PATCH respectivamente. La inyección está fija en el router, sin override.
- El **único** implementador de `EdgeSincronizacionPort` es el stub. No existe un adaptador
  real.
- Los **únicos** archivos de `src/` que mencionan a la vez umbrales y MQTT son el propio
  puerto y su stub: `edge_sincronizacion_port.py` y `edge_sincronizacion_stub_adapter.py`. No
  hay ninguna otra ruta funcional que propague umbrales.
- `umbral_router.py` **no** inyecta `MqttHttpAdapter` ni `MqttPort`.
- La firma del puerto es `propagar_umbral(id_especie, id_variable_ambiental, payload)`: **no
  admite dispositivo, gateway ni nodo destino**. El fixture AIoT no es direccionable desde
  RF-17 ni siquiera en principio.
- No existe topic de umbrales, ni mecánica de ACK, ni timeout.

El propio stub lo documenta: la propagación «todavía no está disponible: el contrato de
publicación (destino, topic, payload, ACK) está pendiente de definición con el equipo de IoT».

### Evidencia Edge / Raspberry

**No obtenida.** No porque falte acceso, sino porque por la vía de RF-17 no se publica nada
que el Raspberry pueda recibir ni almacenar. No se inventó evidencia MQTT ni de Edge, y no se
generó ningún artefacto de publicación u observación de broker.

Lo que **sí** se observó en el nodo seleccionado es propagación real, pero de **otro
requerimiento**:

| `id_configuracion_remota` | `frecuencia_captura` | `intervalo_transmision` | Estado | `id_usuario` | Creación | Aplicación |
| ---: | ---: | ---: | --- | ---: | --- | --- |
| 77 | 119 | 240 | `APLICADA` | 50 | 05:11:31.447 UTC | 05:11:32.350 UTC |
| 72 | 5 | 15 | `APLICADA` | 29 | 03:30:22.844 UTC | 03:30:24.739 UTC |
| 71 | 5 | 15 | `APLICADA` | 29 | 02:23:51.746 UTC | 02:23:52.979 UTC |

Son 9 configuraciones remotas en total sobre `ESP32PRUEBA2`, con confirmación en campo
aproximadamente un segundo después de cada creación. Pertenecen a
`POST /configuracion/dispositivos-iot/{id}/configurar` (**RF-23**), que sí inyecta
`MqttHttpAdapter` contra el broker real. Su payload transporta frecuencia de captura e
intervalo de transmisión: **ningún valor de umbral ni nivel de alerta**.

### POST — verificación posterior

Sin cambios respecto del PRE, al no haber operación.

### Oráculo del caso

| Condición exigida por TC-M09-62 | Cumple | Evidencia |
| --- | --- | --- |
| 1. La configuración se crea o modifica correctamente | **No evaluada** | No se emitió la operación (gate) |
| 2. Se guarda centralmente | **Sí** (ya conocido) | RF-17 hace commit del umbral antes de intentar propagarlo |
| 3. Intento **real** de propagación | **No** | El intento existe, pero contra un stub sin transporte |
| 4. La configuración sale hacia MQTT/Edge | **No** | Ningún archivo de `src/` relaciona umbrales con MQTT salvo puerto y stub |
| 5. El Gateway/Raspberry la recibe | **No** | El puerto no admite destino; el Edge no es direccionable |
| 6. Queda almacenada/aplicada en campo | **No** | Sin publicación no hay nada que almacenar |
| 7. Existe ACK o confirmación equivalente | **No** | No hay ACK ni timeout de umbrales |
| 8. El sistema determina que la sincronización fue exitosa | **No** | `estado_sincronizacion` solo alcanza `PENDIENTE`: 10/10 en DEV, 0 con fecha de sincronización |

**Veredicto: RECHAZADO.** Se cumple 1 de las 8 condiciones y ninguna de las que definen el
caso. Conforme al criterio de aprobación, persistencia central más `PENDIENTE` no basta, y la
propagación real de RF-23 no puede sustituir a la de RF-17.

---

## TC-M09-63 — FALLO DE SINCRONIZACIÓN

**Resultado: NO EJECUTADA.**

No se clasifica como PASS, FAIL, RECHAZADO, BLOCKED, APROBADO ni DESAPROBADO.

**Motivo operativo.** La comprobación requiere generar de manera controlada una
indisponibilidad del Nodo Edge, y QA no está autorizado a desconectar el Raspberry, el Gateway
ni los nodos sin coordinación con AIoT y los responsables de la infraestructura. No se simuló
el fallo por ninguna vía alternativa: no se apagaron dispositivos, no se revocaron ni rotaron
credenciales MQTT, no se cambió el gateway, no se tocó el broker y no se provocó ninguna caída
artificial.

Queda pendiente una ventana coordinada con AIoT que permita verificar la secuencia completa:

1. configuración A aplicada y activa en el Edge;
2. Edge queda no disponible;
3. se intenta la nueva configuración B;
4. B queda guardada centralmente;
5. se registra fallo o pendiente de sincronización;
6. se genera el HTTP 500 que exige RF-17;
7. el Edge conserva A y no sustituye sus valores por B;
8. se advierte que el Edge sigue operando con los valores anteriores;
9. restauración del Edge.

Nota de secuencia: mientras la propagación de TC-M09-62 no exista, el paso 1 no es alcanzable,
porque el Edge nunca recibe una configuración A de umbrales. La ventana coordinada con AIoT es
necesaria, pero no suficiente por sí sola: TC-M09-63 solo podrá ejecutarse cuando además exista
la propagación real que TC-M09-62 exige.

No se generó `tc63-result.json`: no hubo ejecución que registrar.

---

## RESULTADO DEL ORÁCULO

| Oráculo | Valor observado |
| --- | --- |
| Stub `EdgeSincronizacionStubAdapter` sigue existiendo | **Sí** |
| El stub es el adaptador inyectado en RF-17 | **Sí** (POST y PATCH) |
| Existe un adaptador real del puerto Edge | **No** |
| RF-17 usa `MqttPort` / `MqttHttpAdapter` | **No** |
| El puerto recibe un destino Edge | **No** |
| Existe topic de umbrales | **No** |
| Existe ACK de umbrales | **No** |
| Existe timeout de umbrales | **No** |
| Umbrales consultados en DEV | 10 |
| Estados de sincronización observados | `PENDIENTE` (10/10) |
| Umbrales con `fecha_ultima_sincronizacion` | 0 |
| Algún umbral sincronizado alguna vez | **No** |
| Código inspeccionado == código desplegado en DEV | **Sí** (diff vacío en `src/configuration/`) |
| Escrituras funcionales del RUN | **0** |
| SQL de escritura | **0** |
| Publicaciones MQTT emitidas por QA | **0** |
| Cambios de infraestructura | **0** |

---

## COMPARACIÓN V1 VS V2 VS V3 VS V4

| Aspecto | V1 (TEST) | V2 (DEV) | V3 (DEV) | **V4 (DEV)** |
| --- | --- | --- | --- | --- |
| TC-M09-62 | BLOQUEADO | DESAPROBADO | RECHAZADO | **RECHAZADO** |
| TC-M09-63 | BLOQUEADO | DESAPROBADO | RECHAZADO | **NO EJECUTADA** |
| Resultado del grupo | BLOQUEADO | DESAPROBADA | DESAPROBADA | **NO APROBADO / PARCIALMENTE EJECUTADO** |
| Escrituras funcionales | 0 | 0 | 0 | **0** |
| ¿RF-17 invoca un puerto de sincronización? | No | No | Sí | **Sí** |
| Adaptador inyectado | — | — | Stub | **Stub (sin cambio)** |
| ¿Publicación MQTT de umbrales? | No | No | No | **No** |
| ¿Destino Edge direccionable desde RF-17? | No | No | No | **No** |
| ¿Topic / ACK / timeout de umbrales? | No | No | No | **No** |
| Estado de sincronización en el contrato | No existía | No existía | Sí | **Sí** |
| HTTP 500 ante fallo de sincronización | No | No implementado | Implementado en el caso de uso | **Implementado (no ejercitable)** |
| Fixture AIoT disponible para QA | No | No evaluado | No limitante (el backend no contacta el Edge) | **Sí: finca, área, gateway y 3 nodos operativos** |
| Factor limitante | Infraestructura TEST | Funcionalidad inexistente | Integración sustituida por stub | **Integración sustituida por stub** |

Lo que cambió entre V3 y V4 es el **contexto**, no el producto: en V4 el fixture AIoT real
(Camaronera Costa Azul, Piscina-Cam-01, gateway y tres nodos con heartbeat y credencial MQTT
conectada) está disponible y verificado, de modo que ya no queda duda sobre la disponibilidad
de la infraestructura. La propagación de umbrales sigue siendo exactamente la misma que en V3.

---

## ORIGEN / INTERPRETACIÓN DEL RESULTADO

### Defecto de producto

El hallazgo principal es un **defecto de producto / funcionalidad no implementada**: RF-17
declara un estado de sincronización hacia el Nodo Edge que ningún camino del código puede
hacer avanzar más allá de `PENDIENTE`. La parte central del requerimiento está construida
(persistencia, auditoría, estado, motivo de fallo, HTTP 500), pero la integración que le da
sentido está sustituida por un stub. Responsable: **Desarrollo backend en coordinación con
AIoT**, que debe definir destino, topic, payload, ACK y timeout antes de que exista un
adaptador real.

### Limitación de testabilidad

No hubo ninguna. DEV estaba disponible, el actor tenía todos los permisos de RF-17, el fixture
funcional era válido y el fixture AIoT estaba operativo. La prueba no se detuvo por falta de
medios de QA.

### Dependencia operativa con AIoT

Afecta únicamente a **TC-M09-63**, que requiere una ventana coordinada de indisponibilidad
controlada del Nodo Edge. Es una dependencia organizativa legítima, no un defecto.

### Resultado real observado — y precisión sobre la prueba manual informada

Las observaciones del líder son correctas y se reprodujeron en DEV: hay confirmación de MQTT,
hay configuración almacenada en el Raspberry y el frontend muestra la última configuración como
activa. **Esa propagación existe y funciona.** Lo que la evidencia delimita es *a qué
requerimiento pertenece*:

- Lo que llega al Raspberry y recibe confirmación es
  `POST /configuracion/dispositivos-iot/{id}/configurar` — **RF-23**, configuración remota de
  dispositivos IoT —, que inyecta `MqttHttpAdapter` contra el broker real.
- Su payload son `frecuencia_captura` e `intervalo_transmision`. **No transporta valores de
  umbral ni niveles de alerta.**
- En el nodo `ESP32PRUEBA2` hay 9 configuraciones remotas, varias en `APLICADA` con
  `fecha_aplicacion` un segundo después de la creación. La más reciente (`id` 77, 05:11 UTC del
  2026-10-05) fue creada con `id_usuario` 50, que es la misma identidad entregada a QA para
  esta evaluación — un dato coherente con una prueba manual reciente realizada por esa vía.
- En paralelo, **ningún** umbral de DEV registra sincronización alguna.

Es decir: la prueba manual demuestra que el canal MQTT hacia el Raspberry está sano, lo cual es
una buena noticia para el proyecto, pero no demuestra la cadena que exige TC-M09-62. Aprobar
TC-M09-62 con esa evidencia equivaldría a sustituir RF-17 por RF-23, lo que el propio paquete
de instrucciones prohíbe. **No se detectó ninguna contradicción entre lo informado por el
líder y lo observado**: ambas cosas son ciertas y pertenecen a requerimientos distintos.

Conviene señalar que el canal de RF-23 ya resuelto es precisamente el activo técnico que
facilitaría implementar RF-17: existe broker operativo, credencial de Raspberry habilitada y
conectada, y un gateway con nodos asociados. Lo que falta es el contrato de publicación de
umbrales y la resolución del destino a partir de `(especie, variable)`.

---

## INCIDENCIA

**INC-M09-104-G29 — Sincronización Edge de umbrales (RF-17).**

Estado tras V4: **VIGENTE — PARCIALMENTE VERIFICADA / PENDIENTE DE VERIFICACIÓN COMPLETA.**

| Alcance de la incidencia | Estado en V4 | Evidencia |
| --- | --- | --- |
| Estado de sincronización en el modelo y en el contrato | **Corregido** (ya desde V3) | `estado_sincronizacion`, `fecha_ultima_sincronizacion` y `motivo_fallo_sincronizacion` en `UmbralAmbientalResponse` |
| HTTP 500 ante fallo de sincronización | **Implementado, no ejercitable** | Presente en el caso de uso; inalcanzable porque el stub nunca devuelve `NO_CONF` |
| `PENDIENTE` no se trata como fallo (201/200) | **Corregido** | `ESTADOS_SINCRONIZACION_SIN_FALLO` |
| Propagación real hacia el Nodo Edge | **No corregido** | Único implementador del puerto: el stub |
| Contrato de publicación (destino, topic, payload, ACK, timeout) | **No definido** | Documentado como pendiente en el propio stub |
| Conservación de la configuración anterior en campo | **No verificable** | Depende de la propagación y de la ventana coordinada con AIoT |

No se creó ninguna incidencia nueva: el hallazgo de V4 es el mismo de INC-M09-104-G29, sin
hechos nuevos que justifiquen un registro aparte. **No se cierra la incidencia**, porque su
alcance no se ha verificado por completo: TC-M09-63 sigue sin ejecutarse y la propagación sigue
sin existir. La decisión de cierre queda fuera de esta ejecución.

### Evidencia externa que debe solicitarse

1. A **AIoT**: confirmación de si existe o no un contrato de publicación de umbrales hacia el
   Edge, con destino, topic, formato de payload, mecánica de ACK y timeout.
2. A **Desarrollo**: si se considera que la propagación de umbrales ya está operativa, indicar
   la operación exacta del producto que la dispara, para poder reevaluarla.
3. A **AIoT**: ventana coordinada de indisponibilidad controlada del Nodo Edge para ejecutar
   TC-M09-63.

---

## CONCLUSIÓN

La cuarta evaluación de TC-M09-G29 cerró con **0 escrituras funcionales** y el grupo **no
aprobado**.

**TC-M09-62 queda RECHAZADO.** La propagación de umbrales hacia el Nodo Edge sigue resuelta por
`EdgeSincronizacionStubAdapter`, que devuelve siempre `PENDIENTE` sin contactar el broker; el
puerto no admite un destino Edge y no existen topic, ACK ni timeout de umbrales. El censo de
DEV lo confirma en runtime: 10 de 10 umbrales en `PENDIENTE` y ninguno sincronizado jamás. No
se emitió la escritura oficial porque, conforme al gate de ejecutabilidad, ninguna escritura
podía producir evidencia de propagación real: habría creado o modificado un umbral sin nada que
observar después.

**TC-M09-63 queda NO EJECUTADA**, pendiente de una ventana coordinada con AIoT para la
indisponibilidad controlada del Nodo Edge. No se simuló el fallo.

La diferencia relevante frente a V3 es que esta vez el fixture AIoT real estaba disponible y se
verificó operativo —finca, área, gateway y tres nodos con heartbeat y credencial MQTT
conectada—, lo que descarta definitivamente la infraestructura como causa. La prueba manual
informada por el líder es cierta y el canal MQTT hacia el Raspberry funciona, pero corresponde
a RF-23 y transporta frecuencia de captura e intervalo de transmisión, no umbrales. El trabajo
restante es de producto: definir con AIoT el contrato de publicación de umbrales e implementar
el adaptador real que hoy sustituye el stub.

**INC-M09-104-G29 permanece vigente y parcialmente verificada.** No se cierra ni se duplica.

---

### Artefactos de este RUN

`EvaluacionV4/RESULTADOS/G29-REEVAL-V4-20261005-052412/`

| Archivo | Contenido |
| --- | --- |
| `preflight.json` | Discovery completo de solo lectura: Git de ambos repos, DEV, actor, OpenAPI de RF-17, catálogos, censo de sincronización, fixture AIoT, oráculos de código y gate de ejecutabilidad |
| `tc62-result.json` | Decisión del gate para TC-M09-62, cadena exigida por el caso condición por condición y delimitación RF-17 vs RF-23 |
| `seguridad-evidencias.json` | Escaneo de secretos sobre los artefactos de `EvaluacionV4/` |
| `git-final.json` | Cierre de Git de solo lectura en backend y frontend |
| `TC-M09-G29_reevaluacion_V4.md` | Este informe |

`EvaluacionV4/preflight_v4.py` y `EvaluacionV4/cierre_v4.py` contienen la automatización de
solo lectura empleada. No se generó evidencia de MQTT, de broker ni de Raspberry, porque no se
observó ninguna por la vía de RF-17, y no se generó `tc63-result.json`, porque TC-M09-63 no se
ejecutó.
