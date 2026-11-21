# TC-M09-G29 — REEVALUACIÓN V3

RF-17 — Configuración de Umbrales de Monitoreo y Niveles de Alerta Ambiental
CU-03 — Configurar Umbrales y Alertas Ambientales por Especie

Casos: TC-M09-62 (propagación hacia Nodo Edge) · TC-M09-63 (fallo de sincronización)
Tipo: Integración / Disponibilidad / Integridad
Responsable QA: Juan Esteban
RUN_ID: `G29-REEVAL-V3-20260926-013154`
Fecha: 2026-09-26
Entorno decisorio: **DEV**

---

## 0. DECISIÓN GENERAL

### V3 DESAPROBADA — PROPAGACIÓN AL EDGE AÚN NO IMPLEMENTADA (avance parcial respecto de V2)

**TC-M09-62: RECHAZADO.** El backend desplegado en DEV **sí intenta** propagar ahora —algo
que en V2 no existía— pero lo hace contra un **adaptador stub**: `umbral_router.py` inyecta
`EdgeSincronizacionStubAdapter()` en los casos de uso de crear y editar, y ese stub devuelve
**siempre** `PENDIENTE` sin publicar nada. No hay publish real, ni topic, ni ACK, ni timeout,
ni Nodo Edge destino, ni forma de consultar la configuración efectiva de un Edge. No puede
demostrarse propagación ni aplicación reales.

**TC-M09-63: RECHAZADO.** El flujo alterno de fallo de sincronización **no puede demostrarse
porque no existe una integración real que pueda fallar**. La parte central sí progresó
(estado de sincronización, motivo del fallo y un 500 implementado en el caso de uso), pero la
condición esencial del caso —que el Edge conserve la configuración anterior mientras está
offline— es inverificable: el Edge nunca recibe ninguna configuración.

**Raspberry / Nodo Edge: NO REQUERIDO y NO LIMITANTE.**

> El Nodo Edge/Raspberry físico no constituye una precondición limitante en esta ejecución
> porque el backend desplegado no intenta comunicarse con él; la integración está sustituida
> por un stub.

Por eso **no se solicitó a AIoT encender el Raspberry** ni se clasificó el resultado como
bloqueo de hardware. El hallazgo es de **Producto / Integración Backend–AIoT**.

**Escrituras ejecutadas: 0.** Ejecutar el POST y el PATCH solo habría demostrado persistencia
central y un `PENDIENTE` simulado por el stub; no habría probado propagación ni conservación
en el Edge. Además, `DEV_ADMIN_PASSWORD` no estaba disponible en el proceso, así que los GET
autenticados de DEV quedaron omitidos (sin sustituir el actor).

| Caso | V1 | V2 | V3 | Evolución |
| --- | --- | --- | --- | --- |
| TC-M09-62 | BLOCKED (TEST sin MQTT/Edge) | DESAPROBADO — no implementada | **RECHAZADO — propagación simulada por stub** | Avance parcial: ahora hay intento y estado, pero no propagación real |
| TC-M09-63 | BLOCKED (sin Edge offline seguro) | DESAPROBADO — no implementada | **RECHAZADO — el fallo de Edge no es demostrable** | Avance parcial: existe estado PENDIENTE y motivo, pero no hay Edge que conserve la configuración anterior |

**INC-M09-104-G29: PARCIALMENTE CORREGIDO.**

---

## 1. MOTIVO DE V3

V2 demostró, en el ambiente correcto (DEV), que RF-17 no propagaba nada hacia el Edge. Tras
V2, Desarrollo introdujo cambios asociados a **INC-M09-104-G29** que añaden estado de
sincronización y manejo del fallo. V3 debe determinar con evidencia si esa corrección
constituye una integración real o sigue siendo una simulación, y si el Raspberry es o no una
precondición material.

---

## 2. EVALUACIÓN V1 — solo lectura

Evidencia: `TC-M09-G29/RESULTADOS/run-20260905/` (intacta).

| Caso | Resultado | Motivo |
| --- | --- | --- |
| TC-M09-62 | **BLOCKED** | `MQTT_TEST_INFRASTRUCTURE_NOT_AVAILABLE` + `MQTT_CLIENT_MISSING`: TEST sin MQTT/Edge observable |
| TC-M09-63 | **BLOCKED** | Sin mecanismo seguro ni autorizado para inducir Edge offline |

0 escrituras. V1 no demostró defecto de producto: fue una limitación de entorno/testabilidad.

---

## 3. REEVALUACIÓN V2 — solo lectura

Evidencia: `EvaluacionV2/RESULTADOS/G29-REEVAL-V2-20260913-014534/` (intacta). Ambiente: DEV.

| Caso | Resultado |
| --- | --- |
| TC-M09-62 | **DESAPROBADO — FUNCIONALIDAD NO IMPLEMENTADA** |
| TC-M09-63 | **DESAPROBADO — FUNCIONALIDAD NO IMPLEMENTADA** |

Hallazgos de V2: RF-17 solo persistía umbral y niveles; no publicaba MQTT; no había Edge
destino, ACK, timeout, estado de sincronización, estado PENDIENTE, ni 500 asociado al fallo;
no existía forma de consultar la configuración efectiva del Edge; MQTT solo lo usaba RF-23.
0 POST/PATCH, 0 escrituras.

---

## 4. CAMBIOS ENTRE V2 Y V3

| Aspecto | V2 (2026-09-13) | V3 (2026-09-26) | Estado |
| --- | --- | --- | --- |
| RF-17 invoca propagación | No | **Sí** — `edge_port.propagar_umbral(...)` en registrar y editar | **Nuevo** |
| Puerto de dominio | No existía | **`EdgeSincronizacionPort`** | **Nuevo** |
| Adaptador inyectado | — | **`EdgeSincronizacionStubAdapter`** | **Stub** |
| Estado de sincronización | No existía | **`estado_sincronizacion`, `fecha_ultima_sincronizacion`, `motivo_fallo_sincronizacion`** en el contrato DEV | **Nuevo** |
| Estado PENDIENTE | No existía | **Implementado** (`marcar_pendiente_sincronizacion`) | **Nuevo** |
| HTTP 500 por fallo Edge | No existía | **Implementado** en el caso de uso (`FALLO_SINCRONIZACION_EDGE`)… | **Parcial** |
| …declarado en el contrato | No | **No** — POST y PATCH de DEV siguen sin declarar 500 | **Pendiente** |
| Publish real MQTT para umbrales | No | **No** — MQTT sigue siendo exclusivo de RF-23 | **Pendiente** |
| Topic / payload / ACK / timeout | No | **No** — pendiente de definición con IoT | **Pendiente** |
| Consulta de configuración efectiva del Edge | No | **No** | **Pendiente** |

Fuente documental del propio equipo:
`anotaciones/modulo_9/inc_m09_104_g29_sincronizacion_edge_umbrales.md`, que describe la
decisión de diseño: *«Adaptador stub, no un adaptador "real"… El contrato de publicación
(destino, topic, payload, confirmación, timeout) para propagar un umbral por especie+variable
no existe»*.

---

## 5. GIT / SHAs

| Repositorio | Rama | HEAD | `HEAD...origin/test` | Estado |
| --- | --- | --- | --- | --- |
| sgpmp-backend | `qa/juan-esteban-tercera-evaluacion-M09` | `91f7738667a934a4eaf3db5519a57d7cf4803b0e` | `0  0` | Limpio al inicio; al cierre solo `?? .../TC-M09-G29/EvaluacionV3/` |
| SGPMP-FRONT-END-PWA | `qa/juan-esteban-tercera-evaluacion-M09` | `ad2b1e59bb872491bae368ae812993a3ded08d63` | `0  0` | `?? .../TC-M09-G22/EvaluacionV3/` y `?? .../TC-M09-G28/EvaluacionV3/` (evidencia ajena preexistente) |

`origin/dev` en el momento de la evaluación: `1214b3ff` (2026-09-26).

**Diferencia `HEAD` (rama QA) vs `origin/dev` en `src/`**: 5 archivos de
`biological_assets` y `shared/rate_limit.py`. **Ninguno de RF-17, umbrales, Edge o MQTT**: el
código que se inspeccionó para este caso es idéntico en ambas referencias, así que la lectura
sobre `origin/dev` describe fielmente lo desplegado en DEV.

El índice de Git no se tocó: `git diff --cached --stat` vacío en ambos repositorios. No se
ejecutó `git add`, `commit`, `push`, `merge`, `rebase`, `reset`, `clean`, `stash`, `tag`,
`checkout` ni `switch`.

---

## 6. ENTORNO DEV

| Recurso | Valor | Estado |
| --- | --- | --- |
| Backend DEV | `https://sigab-backenddev-jpuya4-ea3a74-158-69-200-27.sslip.io/api-sgpmp` | `/health` **200**, `/openapi.json` **200** |

DEV es el ambiente decisorio de G29. TEST se usó únicamente como comparación técnica de
contrato, no como sustituto.

---

## 7. ACTOR

Actor histórico previsto: `admin.general@pecuaria.co` (Administrador, permisos recurso 20
`[1,2,3,4]`).

**No se pudo autenticar**: la variable `DEV_ADMIN_PASSWORD` no estaba disponible en el
proceso. Conforme al procedimiento, **no se sustituyó el actor** por ningún otro y los GET
autenticados de DEV quedaron omitidos (`test_oraculo_dev_runtime_expone_estado_sincronizacion`
→ SKIPPED, con el motivo registrado en la evidencia).

Esto **no cambia el veredicto**: la conclusión se sostiene sobre el contrato desplegado —que
es público— y sobre el código de `origin/dev`. Lo único que aportaría la credencial es la
confirmación en runtime de que los umbrales de DEV muestran `estado_sincronizacion`; el
bloqueo funcional está en la ausencia de integración real, no en la falta de esa lectura.

---

## 8. OPENAPI DEV

| Operación | Respuestas declaradas en DEV | En V2 |
| --- | --- | --- |
| `POST /configuracion/umbrales` | `201, 401, 403, 404, 409, 422` | idéntico |
| `PATCH /configuracion/umbrales/{id_umbral_ambiental}` | `200, 401, 403, 404, 412, 422` | idéntico |
| `GET /configuracion/umbrales` | `200, 401, 403, 422` | — |

`UmbralAmbientalResponse` en DEV: `es_activo`, **`estado_sincronizacion`**,
`fecha_actualizacion`, **`fecha_ultima_sincronizacion`**, `id_especie`, `id_umbral_ambiental`,
`id_variable_ambiental`, **`motivo_fallo_sincronizacion`**, `niveles`, `unidad_medida`,
`valor_max`, `valor_min`.

**Cambio respecto de V2:** el esquema ya expone los tres campos de sincronización.
**Sin cambio respecto de V2:** ninguna escritura declara **500**, pese a que el caso de uso lo
lanza cuando la propagación no queda `APLICADA`. El contrato publicado y el comportamiento
implementado no están alineados.

Rutas con semántica edge/mqtt/sincronización en DEV: únicamente `/iot/eventos-edge`, que
pertenece a la ingesta de eventos IoT y **no** permite consultar la configuración efectiva de
un Edge para umbrales.

---

## 9. IMPLEMENTACIÓN ACTUAL EDGE

Lectura de `origin/dev` (solo lectura, sin checkout):

| Pregunta | Respuesta |
| --- | --- |
| Puerto / caso de uso | `EdgeSincronizacionPort.propagar_umbral(id_especie, id_variable_ambiental, payload)`, invocado por `registrar_umbral_use_case.py:185` y `editar_umbral_use_case.py:114` |
| Adaptador realmente inyectado | **`EdgeSincronizacionStubAdapter()`** en `umbral_router.py:72` (POST) y `umbral_router.py:152` (PATCH) |
| Qué devuelve | **Siempre** `ResultadoEnvioMqtt(estado="PENDIENTE", mensaje=…)` |
| Condición para `APLICADA` | Inalcanzable con el stub |
| Condición para `PENDIENTE` | Todas |
| Condición para `FALLIDA` | Inalcanzable con el stub |
| Topic | **No existe** para umbrales |
| Timeout | **No existe** |
| ACK | **No existe** |
| Retry | **No existe** |
| Observabilidad del Edge | **No existe** ruta ni mecanismo |
| Manejo del resultado | `APLICADA → marcar_sincronizado`; `PENDIENTE → marcar_pendiente_sincronizacion`; otro → `marcar_fallo_sincronizacion`; si el resultado no es `APLICADA`, el caso de uso lanza `InfrastructureError(code='FALLO_SINCRONIZACION_EDGE')` → **HTTP 500** con el umbral ya persistido |

Consumidores reales de `MqttPort`/`MqttHttpAdapter` en `origin/dev`: únicamente
`dispositivos_iot` (RF-23, `dispositivo_iot_router.py:272`). **Ningún flujo de umbrales
publica por MQTT.**

El propio docstring del stub lo declara: la propagación *«todavía no está disponible: el
contrato de publicación (destino, topic, payload, ACK) está pendiente de definición con el
equipo de IoT»*.

---

## 10. GATE RASPBERRY / AIoT

| Pregunta | Respuesta |
| --- | --- |
| **¿El backend contacta el Raspberry?** | **No.** El puerto de propagación está cubierto por un stub que retorna sin realizar ninguna comunicación |
| **¿El Raspberry es necesario?** | **No**, para esta ejecución |
| **¿Estuvo disponible?** | **No aplica** — no se solicitó a AIoT |
| **¿Limitó la prueba?** | **No** |

**Justificación técnica.** La limitante no es el hardware sino la ausencia de integración: el
flujo desplegado termina en el stub, que no abre conexión con broker alguno, no publica en
ningún topic y no espera confirmación. Encender el Raspberry no habría cambiado ninguna
observación, porque ningún mensaje habría llegado a él. Por eso **no se pidió a AIoT
habilitar el dispositivo** y el hallazgo se clasifica contra **Producto / Integración
Backend–AIoT**, no como bloqueo de precondición.

Checklist de ejecutabilidad (§22):

| | Condición | Estado |
| --- | --- | --- |
| A | DEV disponible | **Sí** |
| B | Actor correcto | **No** — sin `DEV_ADMIN_PASSWORD` |
| C | RF-17 tiene integración **real** | **No** — stub |
| D | Adaptador identificado | **Sí** — `EdgeSincronizacionStubAdapter` |
| E | Broker disponible para umbrales | **No aplica** |
| F | Topic conocido | **No** — no existe |
| G | Payload conocido | Parcial — el stub recibe un dict, pero no hay contrato de publicación |
| H | Edge/Raspberry identificado | **No** — no hay mapeo (especie, variable) → dispositivos |
| I | Configuración efectiva del Edge observable | **No** |
| J | Mecanismo de ACK conocido | **No** |
| K | Mecanismo seguro de Edge offline para TC63 | **No aplica** |
| L | AIoT puede controlar el Raspberry | No consultado (innecesario) |
| M | Herramienta QA para observar mensajes | **No** — sin cliente MQTT instalado |

Como **C = No por stub**, el Raspberry **no** se clasifica como limitante (§22).

---

## 11. MQTT / BROKER

**No hubo tráfico MQTT y no se generó `mqtt-observed.json`**, porque el flujo de umbrales no
produce ninguna publicación real: crear ese archivo sería fingir una observación.

- Broker: no utilizado por RF-17. El broker `BROKER-MQTT-SGPMP` existe y lo usa RF-23 vía
  `MqttHttpAdapter` (`POST {base}/v1/commands` con `{"serial": …}`), un contrato por
  dispositivo que no cubre «propagar por especie+variable».
- Topic para umbrales: **inexistente**. No se inventó ninguno ni se intentó adivinarlo.
- Puertos del broker DEV: **no se verificaron ni se escanearon**, por innecesario.
- Cliente MQTT disponible en el equipo QA: **ninguno** (`paho-mqtt`, `mosquitto_sub`,
  `mosquitto_pub`, `mqttx`, `mqtt` → todos ausentes). No se instaló software. Esta carencia
  **no es la limitante** del caso: aunque hubiera cliente, no habría nada que observar.

---

## 12. DISCOVERY DE DATOS

**No se realizó discovery de especies ni se preparó fixture bovino.** El gate de
ejecutabilidad cerró en `C = No` antes de esa fase: sin integración real no hay nada que
propagar, y el discovery solo habría servido para preparar escrituras que el procedimiento
desaconseja en el escenario de stub (§40). Tampoco se dispone de credencial DEV para los GET
autenticados.

---

## 13. PLAN V3

`plan-v3.json`:

| Campo | Valor |
| --- | --- |
| Ambiente decisorio | DEV |
| Escrituras planificadas | **0** |
| Motivo | Escenario A (stub): un POST/PATCH solo demostraría persistencia central y un `PENDIENTE` simulado; no probaría propagación ni comportamiento del Edge real. Además falta `DEV_ADMIN_PASSWORD` |
| Raspberry | No requerido, no limitante |
| MQTT | Sin flujo real; sin topic; sin cliente |

---

## 14. TC-M09-62

| Pregunta del caso | Respuesta con evidencia |
| --- | --- |
| ¿El backend intenta propagar? | **Sí** — invoca `edge_port.propagar_umbral(...)` tras persistir |
| ¿Existe publicación/salida hacia MQTT/Edge? | **No** — el adaptador inyectado es un stub; ningún flujo de umbrales consume `MqttPort` |
| ¿El Nodo Edge recibe la configuración? | **No verificable** — no se envía nada |
| ¿La aplica? | **No verificable** |
| ¿El backend registra estado de sincronización? | **Sí** — queda `PENDIENTE` con `motivo_fallo_sincronizacion` |
| ¿Existe ACK o equivalente? | **No** — pendiente de definición con IoT |
| ¿La configuración efectiva del Edge coincide con la central? | **No verificable** — no hay forma de consultarla |

Escrituras: **0**. **Resultado: RECHAZADO.** El caso exige propagación y aplicación reales; un
estado favorable producido por un stub no constituye evidencia de recepción.

---

## 15. ESTADO EDGE DESPUÉS DE TC62

No aplica: no se ejecutó escritura y no existe Edge en el flujo desplegado. **No se generaron**
`edge-before.json` ni `edge-after-tc62.json`, porque no hay fuente real de la que obtenerlos.

---

## 16. TC-M09-63

| Pregunta del caso | Respuesta con evidencia |
| --- | --- |
| ¿Qué ocurre si el Edge no está disponible? | Indistinguible del caso normal: el stub siempre degrada a `PENDIENTE`, esté el Edge como esté |
| ¿La configuración nueva se conserva centralmente? | Según el código, sí (se persiste y se hace commit antes de propagar). **No ejecutado**: 0 escrituras |
| ¿El backend devuelve el HTTP esperado por RF-17? | El caso de uso lanza **500 `FALLO_SINCRONIZACION_EDGE`**, pero el contrato DEV **no lo declara** |
| ¿El estado queda PENDIENTE? | Sí, implementado y expuesto en el contrato |
| ¿El Nodo Edge conserva la configuración anterior? | **No verificable** — el Edge nunca recibió ninguna configuración |
| ¿El sistema advierte que la propagación no se completó? | Sí: `estado_sincronizacion = PENDIENTE` + `motivo_fallo_sincronizacion` |

Escrituras: **0**. Edge offline controlado: **no aplica** (no hay Edge en el flujo; no se
solicitó a AIoT ningún cambio de estado). **Resultado: RECHAZADO.** La condición central del
caso —que el Edge conserve la configuración anterior— es inverificable por diseño actual.

---

## 17. ESTADO CENTRAL DURANTE FALLO

No se ejecutó ninguna escritura en DEV, así que no hay medición de runtime propia de este
grupo. Como referencia técnica (no decisoria, ambiente TEST): en **TC-M09-G22 V3** y
**TC-M09-G28 V3** se observó que el mismo código guarda el umbral completo, deja
`estado_sincronizacion = PENDIENTE` con el motivo del stub y responde **HTTP 500
`FALLO_SINCRONIZACION_EDGE`**. Eso confirma el comportamiento central implementado, pero
pertenece a TEST y no sustituye la verificación en DEV.

---

## 18. ESTADO EDGE DURANTE FALLO

**No verificable.** No existe Edge en el flujo, ni ruta de consulta, ni ACK, ni telemetría de
configuración efectiva. Un `estado_sincronizacion = PENDIENTE` describe el estado **central**
y no dice nada sobre qué configuración usa un Raspberry: son evidencias distintas y el caso
requiere ambas.

---

## 19. COMPARACIÓN V1 ↔ V2 ↔ V3

| Aspecto | V1 | V2 | V3 | Evolución |
| --- | --- | --- | --- | --- |
| Ambiente | TEST | DEV | DEV | Correcto desde V2 |
| MQTT en el flujo de umbrales | No observable | No existe | **No existe** | Sin cambio |
| Adaptador Edge | No existía | No existía | **Stub (`EdgeSincronizacionStubAdapter`)** | Nuevo, pero simulado |
| Edge real | No | No | **No** | Sin cambio |
| Raspberry | Limitante (no había Edge observable) | No evaluado | **No requerido / no limitante** | Aclarado |
| Cliente MQTT | Ausente | Ausente | **Ausente** (no limitante) | Sin cambio |
| Topic | Desconocido | Inexistente | **Inexistente** | Sin cambio |
| ACK | No | No | **No** | Sin cambio |
| Estado de sincronización | No | No | **Sí** (`estado_sincronizacion`, `fecha_ultima_sincronizacion`, `motivo_fallo_sincronizacion`) | **Nuevo** |
| HTTP éxito | 201/200 | 201/200 | 201/200 declarados | Sin cambio |
| HTTP fallo Edge | No existía | No existía | **Implementado (500) pero no declarado en OpenAPI** | Parcial |
| Configuración central | Se guarda | Se guarda | Se guarda (no ejecutado aquí) | Sin cambio |
| Configuración Edge | No observable | No existe | **No existe** | Sin cambio |
| Escrituras | 0 | 0 | **0** | Sin cambio |
| TC-M09-62 | BLOCKED | DESAPROBADO | **RECHAZADO** | Defecto confirmado, con avance parcial |
| TC-M09-63 | BLOCKED | DESAPROBADO | **RECHAZADO** | Defecto confirmado, con avance parcial |
| Resultado general | BLOQUEADO | DESAPROBADO | **DESAPROBADO** | Persiste |

---

## 20. ORIGEN DE FALLOS / BLOQUEOS

| Hallazgo | Responsable | Clasificación | Diagnóstico |
| --- | --- | --- | --- |
| RF-17 no publica hacia MQTT/Edge: adaptador stub | **Backend / Integración AIoT** | Defecto de producto (funcionalidad incompleta) | Causa confirmada por código: `umbral_router.py:72,152` inyecta el stub; el stub siempre devuelve `PENDIENTE`. Decisión documentada por el equipo a la espera del contrato de IoT |
| No existe contrato de propagación (destino, topic, payload, ACK, timeout) | **AIoT + Desarrollo** | Definición pendiente | Bloquea la implementación real; lo declara la propia nota del incidente |
| Sin ruta para consultar la configuración efectiva del Edge | **Backend / AIoT** | Testabilidad + funcionalidad | Impide verificar TC-62 y la parte de campo de TC-63 |
| 500 implementado pero no declarado en OpenAPI | **Backend / Contrato** | Desalineación de contrato | El caso de uso lanza `FALLO_SINCRONIZACION_EDGE`; POST y PATCH no declaran 500 |
| Sin `DEV_ADMIN_PASSWORD` | **Acceso / testabilidad** | Limitación de la ejecución, no defecto | Omitió los GET autenticados de DEV; no altera el veredicto |
| Sin cliente MQTT instalado | **Capacidad de prueba** | No limitante aquí | Aunque existiera, no habría tráfico que observar |
| Raspberry apagado o no solicitado | **No aplica** | **No es la causa** | El flujo desplegado no lo contacta |

---

## 21. INCIDENCIAS

**No se creó ninguna incidencia nueva y no se abrió ningún ticket.**

**INC-M09-104-G29 → PARCIALMENTE CORREGIDO.**

| Nivel de verificación | Estado |
| --- | --- |
| Fix reportado | **Sí** — estado de sincronización y manejo de fallo |
| Fix presente en código | **Sí** — puerto, stub, estados y 500 en `origin/dev` |
| Fix desplegado en DEV | **Sí, parcialmente** — el contrato DEV ya expone los tres campos de sincronización |
| Fix verificado por QA con Edge real | **No** — imposible: no hay propagación real ni Edge en el flujo |

Se sugiere **mantener abierta** INC-M09-104-G29 con el alcance restante explícito, sin
duplicarla: (1) definir con IoT el contrato de propagación por (especie, variable);
(2) sustituir el stub por el adaptador real con ACK y timeout; (3) exponer una vía para
consultar la configuración efectiva del Edge; (4) declarar el 500 en el contrato OpenAPI o
alinear el comportamiento con las respuestas declaradas.

El punto (4) coincide con el hallazgo colateral registrado en **TC-M09-G22 V3** y
**TC-M09-G28 V3**; se relaciona con él y **no se duplica**.

---

## 22. SEGURIDAD

- `DEV_ADMIN_PASSWORD` y cualquier credencial MQTT se tratan solo como variables de proceso;
  no se imprimieron ni se escribieron en ningún artefacto. En esta ejecución no hubo login,
  así que no se emitió ningún token.
- El saneador redacta contraseñas y JWT antes de escribir cualquier evidencia.
- No se escanearon puertos, no se probaron credenciales, no se adivinaron topics y no se
  contactó ningún broker.

**Escaneo final de `EvaluacionV3/`** (`seguridad-evidencias.json`): **10 archivos revisados,
0 comprometidos**. Sin contraseñas literales, sin JWT y sin `Bearer` con valor. Las
coincidencias de palabras clave son nombres de variable o texto descriptivo.

---

## 23. GIT FINAL

| Repositorio | Rama | HEAD | `status --short` | `diff --stat` | `diff --cached --stat` |
| --- | --- | --- | --- | --- | --- |
| sgpmp-backend | `qa/juan-esteban-tercera-evaluacion-M09` | `91f7738667a934a4eaf3db5519a57d7cf4803b0e` | `?? .../TC-M09-G29/EvaluacionV3/` | (vacío) | **(vacío)** |
| SGPMP-FRONT-END-PWA | `qa/juan-esteban-tercera-evaluacion-M09` | `ad2b1e59bb872491bae368ae812993a3ded08d63` | `?? .../TC-M09-G22/EvaluacionV3/`, `?? .../TC-M09-G28/EvaluacionV3/` | (vacío) | **(vacío)** |

- **V1 intacta · V2 intacta · código productivo intacto.**
- Única zona escrita: `TC-M09-G29/EvaluacionV3/`. Las entradas del frontend son evidencia
  preexistente de otros grupos.
- Índice de Git sin modificar en ambos repositorios. Sin `git add`, commit, push, merge,
  rebase, reset, clean, stash, tag, checkout ni switch. Sin deploy.
- **0 escrituras de API · 0 SQL · 0 publicaciones MQTT.**

---

## 24. VEREDICTO FINAL

**TC-M09-G29 V3: DESAPROBADA.**

**TC-M09-62 — RECHAZADO.** RF-17 ya intenta propagar y ya registra un estado de
sincronización, lo que es un avance real respecto de V2, pero la propagación termina en un
adaptador stub que devuelve `PENDIENTE` sin publicar nada. No hay publish, topic, ACK,
timeout ni Edge destino, y no existe forma de consultar la configuración efectiva de un Nodo
Edge. La propagación real, que es lo que el caso exige, no está implementada.

**TC-M09-63 — RECHAZADO.** El caso requiere que una sincronización real falle y que el Edge
conserve la configuración anterior. Con un stub no hay integración que pueda fallar ni Edge
que conserve nada: la parte central (guardar la configuración, marcarla `PENDIENTE`, advertir
del fallo) está implementada, pero la parte de campo es inverificable por diseño actual.

**El Raspberry no fue la limitante y no se solicitó a AIoT**: el backend desplegado no intenta
comunicarse con él. El hallazgo pertenece a Producto / Integración Backend–AIoT, con una
dependencia declarada del contrato de publicación que debe definir el equipo de IoT.

**INC-M09-104-G29: PARCIALMENTE CORREGIDO** — corregido en la mitad central (estado,
motivo, 500 implementado), pendiente en la mitad de integración (propagación real,
ACK/timeout, observabilidad del Edge y declaración del 500 en el contrato).

Nota de alcance: no se dispuso de `DEV_ADMIN_PASSWORD`, de modo que los GET autenticados de
DEV quedaron omitidos. Eso no altera ninguna de las conclusiones anteriores, que se sostienen
sobre el contrato público desplegado y sobre el código de `origin/dev` verificado idéntico al
de la rama evaluada en los archivos de RF-17/Edge.
