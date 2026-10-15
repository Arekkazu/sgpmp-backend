# TC-M09-G29 — REEVALUACIÓN V5

RF-17 — Configuración de Umbrales de Monitoreo y Niveles de Alerta Ambiental
CU-03 — Configurar Umbrales y Alertas Ambientales por Especie

Grupo: Propagación y sincronización de umbrales hacia el Nodo Edge (incluye fallo)
Casos: TC-M09-62 (propagación hacia Nodo Edge) · TC-M09-63 (fallo de sincronización)
Tipo: Integración / Disponibilidad / Integridad
Componente: Backend + Broker MQTT + Gateway/Edge
Responsable QA: Juan Esteban · Prioridad: Alta
RUN_ID válido: `G29-REEVAL-V5-20261008-200906`
Fecha: 2026-10-08
Entorno decisorio: **TEST**

---

## DECISIÓN GENERAL

### TC-M09-62 — APROBADO. La propagación de umbrales al Gateway Edge funciona y queda confirmada por ACK real.

El backend resolvió el Gateway Edge destino, publicó el umbral por el broker MQTT y recibió el
`ACK_UMBRAL` del Edge, tanto al crear (`POST`, HTTP 201) como al editar (`PATCH`, HTTP 200). En
ambos casos el umbral quedó `APLICADA` con `fecha_ultima_sincronizacion` informada y sin motivo
de fallo.

### TC-M09-63 — APROBADO. Con el Edge indisponible el servidor conserva la configuración como pendiente, responde 500 y no la aplica en campo.

Con la Raspberry físicamente desconectada, la edición a Configuración B quedó guardada
centralmente, el flujo respondió **HTTP 500 `FALLO_SINCRONIZACION_EDGE` en 0,449 s**, el umbral
quedó `PENDIENTE` con el motivo informado y `fecha_ultima_sincronizacion` **no avanzó**. Al
reconectar no hubo reenvío automático de B, y la edición siguiente (Configuración C) volvió a
quedar `APLICADA`.

### Estado general del grupo: APROBADO CON OBSERVACIONES.

| Caso | Resultado V5 | Escrituras oficiales | Ambiente |
| --- | --- | ---: | --- |
| TC-M09-62 | **APROBADO** (observación de tiempo de respuesta) | 2 | TEST |
| TC-M09-63 | **APROBADO** (conservación en campo inferida, no observada) | 2 | TEST |
| **Grupo TC-M09-G29** | **APROBADO CON OBSERVACIONES** | **4** | TEST |

**INCIDENCIA REQUERIDA: NO.**

Es la primera de las cinco evaluaciones en que la propagación RF-17 al Nodo Edge queda demostrada
en ejecución, en los tres escenarios: aplicada con el Edge presente, pendiente con el Edge
ausente, y reaplicada en la edición siguiente tras reconectar.

---

## RESUMEN DEL RESULTADO

**Escrituras oficiales de los casos: 4.** Dos de TC-M09-62 (`POST` + `PATCH`), dos de TC-M09-63
(`PATCH` de B con el Edge apagado y `PATCH` de C tras reconectar). Ningún reintento. 0 SQL de
escritura, 0 publicaciones MQTT fabricadas, 0 cambios de configuración del broker.

Aparte de esas cuatro, y registradas separadamente, se realizaron **5 escrituras de saneamiento
de fixture** y **2 de cleanup**. No cuentan como escrituras de los casos.

El contraste que sostiene el resultado es el comportamiento del mismo endpoint en los dos
escenarios:

| Escenario | HTTP | Tiempo | `estado_sincronizacion` | `fecha_ultima_sincronizacion` |
| --- | ---: | ---: | --- | --- |
| Edge ONLINE (crear, 40–90) | 201 | 1,278 s | `APLICADA` | 20:13:24.445890Z |
| Edge ONLINE (editar a A, 40–95) | 200 | 1,321 s | `APLICADA` | 20:18:32.740677Z |
| Edge DESCONECTADO (editar a B, 40–100) | **500** | **0,449 s** | `PENDIENTE` | **sin avanzar** |
| Edge RECONECTADO (editar a C, 40–98) | 200 | 0,888 s | `APLICADA` | 21:11:56.933882Z |

Un stub no puede producir esa diferencia de estados ni de tiempos, y con un **único destino** la
consolidación de RF-17 no puede enmascarar un Gateway que no haya confirmado.

---

## ANTECEDENTES

V1–V4 se conservan intactas y en solo lectura. No se reescribió ninguna.

| Evaluación | RUN / evidencia | Ambiente | TC-M09-62 | TC-M09-63 | Escrituras |
| --- | --- | --- | --- | --- | ---: |
| **V1** | `RESULTADOS/run-20260905/` | TEST | BLOQUEADO — infraestructura MQTT/Edge no disponible | BLOQUEADO — sin mecanismo autorizado para inducir Edge offline | 0 |
| **V2** | `EvaluacionV2/RESULTADOS/G29-REEVAL-V2-20260913-014534/` | DEV | DESAPROBADO — guardar un umbral no disparaba ninguna propagación | DESAPROBADO — no existía intento de sincronización que pudiera fallar | 0 |
| **V3** | `EvaluacionV3/RESULTADOS/G29-REEVAL-V3-20260926-013154/` | DEV | RECHAZADO — propagación contra `EdgeSincronizacionStubAdapter`, siempre `PENDIENTE` | RECHAZADO — sin integración real que pudiera fallar | 0 |
| **V4** | `EvaluacionV4/RESULTADOS/G29-REEVAL-V4-20261005-052412/` | DEV | RECHAZADO — el stub seguía inyectado; gate cerrado antes de escribir | NO EJECUTADA — pendiente de coordinación con AIoT | 0 |

---

## CAMBIO QUE MOTIVA V5

Desarrollo reportó la corrección de **INC-M09-104-G29** (issue #493): reemplazar
`EdgeSincronizacionStubAdapter` por un adaptador MQTT real y añadir el manejo del Edge
desconectado.

Verificado en código y en despliegue, no por notas de release:

- [`edge_sincronizacion_mqtt_adapter.py`](../../../../../../src/configuration/infrastructure/adapters/edge_sincronizacion_mqtt_adapter.py)
  existe en `origin/dev`, introducido por los commits `f7dc7120` y `7d94f5a2`.
- [`umbral_router.py`](../../../../../../src/configuration/infrastructure/routers/umbral_router.py)
  inyecta `EdgeSincronizacionMqttAdapter()` en el `POST` (línea 75) y en el `PATCH` (línea 157).
  **`EdgeSincronizacionStubAdapter` no se define ni se instancia en ningún punto de `src/`**: su
  nombre solo sobrevive citado en el docstring del adaptador que lo reemplazó.
- Resolución de destino real por la migración
  [`a3c9e5d17b42`](../../../../../../alembic/versions/a3c9e5d17b42_rf17_destinos_edge_umbrales.py):
  `modulo9.fn_seriales_gateway_edge_por_especie`.
- **Evidencia de despliegue:** el OpenAPI vivo declara en `POST` y `PATCH` un 500
  `FALLO_SINCRONIZACION_EDGE` con la cadena literal del código corregido. En el snapshot de V3
  esos dos métodos no declaraban 500.

---

## ENTORNO

| Elemento | Valor |
| --- | --- |
| Ambiente decisorio | **TEST** |
| Backend TEST | `https://api.inmero.co/back-sigab-test` |
| Broker TEST | `https://api.inmero.co/broker-sigab-test` |
| `GET /health` | 200 |
| `GET /openapi.json` | 200 · versión 1.0.0 |
| Rama QA backend | `qa/juan-esteban-quinta-evaluacion-M09` |
| HEAD backend | `15121f3f5a69c6126b6613f2dcf1cecd4cf6aa7c` |
| `HEAD...origin/test` | `0 0` (sin divergencia) |
| `HEAD` vs `origin/dev` en `src/configuration/` | sin diferencias |

### Por qué TEST y no DEV

El paquete V5 designaba DEV como ambiente decisorio. Se cambió a TEST por decisión del
responsable QA, con un motivo material: **la infraestructura MQTT/Edge necesaria fue preparada
por AIoT en TEST específicamente para esta prueba**. En DEV el único Gateway Edge destino de la
especie 4 (`DISPOSITIVOCAMARONERA41`) estaba offline desde el 2026-10-05 y no había ningún Edge
real conectado. DEV quedó como contraste de solo lectura.

Contrato de RF-17 publicado en TEST:

| Ruta | Métodos |
| --- | --- |
| `/configuracion/umbrales` | `GET`, `POST` |
| `/configuracion/umbrales/{id}` | `PATCH` |
| `/configuracion/umbrales/{id}/desactivar` | `PATCH` |
| `/configuracion/umbrales/{id}/auditoria` | `GET` |

`POST` y `PATCH` declaran `500`: *"FALLO_SINCRONIZACION_EDGE: guardado, pero la propagación al
Nodo Edge se intentó y falló (RF-17)."*

---

## ACTOR / IDENTIDAD TÉCNICA

| Elemento | Valor |
| --- | --- |
| Cuenta | `administador.dev@gmail.com` |
| `id_usuario` | 104 |
| Rol | Administrador · estado `Activo` |
| Permisos recurso 20 (`umbrales_ambientales`) | acciones `[1, 2, 3, 4]` |
| Alcance de fincas | global (recurso 9, acciones `[1,2,3,4]`) |

La contraseña se usó únicamente desde variable de entorno. No se persistió ninguna credencial,
JWT, cabecera `Authorization` ni credencial MQTT en ningún artefacto.

---

## CONFIGURACIÓN UTILIZADA / FIXTURE

Fixture oficial entregado por Desarrollo y verificado en runtime:

| Elemento | Valor |
| --- | --- |
| Finca | 44 — `Finca Prueba QA femjscac` |
| Área | 22 — `QA-G36-Infra-1789010064` |
| Especie | 4 — Cachama Blanca |
| Variable ambiental | 10 — Humedad Relativa (`%`), rango físico `[0, 100]` |
| Gateway Edge | `SERBY-TAX-FIRMWARE` (id 138) |
| Nodo | `TEST-AMBIENTAL` (id 139), colgado del Gateway 138 |
| Umbral utilizado | 65 (creado por esta reevaluación) |

### Adaptación del fixture, documentada

La matriz usa *"Nuevos umbrales para Bovino"*. **Bovino no existe en DEV** (cero coincidencias) y
en TEST no tiene ruta a un Gateway Edge. Se utilizó la **especie 4 Cachama Blanca**, la única con
ruta real al Gateway conectado. Es una adaptación del fixture, no una equivalencia silenciosa, y
no modifica el oráculo de propagación: lo que se prueba es el mecanismo genérico de propagación
de umbrales RF-17.

El área 22 entra en la resolución por la segunda fuente de la función SQL —activos biológicos
vivos de la especie 4 (ids 235 y 236)—, porque `especie_id` está NULL en todas las áreas de TEST.

### Saneamiento previo del fixture, necesario para que el caso fuera ejecutable

`fn_seriales_gateway_edge_por_especie` agrega por especie en **todas** sus áreas activas, y la
consolidación de RF-17 exige que **todos** los Gateway confirmen para llegar a `APLICADA`: uno
solo desconectado degrada el umbral a `PENDIENTE` y fuerza el 500. La especie 4 resolvía **6
destinos**, de los cuales solo `SERBY-TAX-FIRMWARE` estaba conectado.

Se trazaron los 5 destinos OFFLINE. Ninguno tenía credencial MQTT emitida, ninguno había
registrado un heartbeat jamás, y ninguno tenía configuraciones RF-23, sensores ni dispositivos
colgados: no estaban desconectados, **no estaban provisionados para conectarse**. Con
confirmación de AIoT de que eran registros de prueba ya no utilizados, y autorización expresa del
responsable QA, se desactivaron por el endpoint oficial
`PATCH /configuracion/dispositivos-iot/{id}/desactivar`:

| Gateway | id | Resultado |
| --- | ---: | --- |
| `TC-M09-G59-1791163477491` | 133 | HTTP 200, `es_activo=false` |
| `TC-M09-G59-RESUELTO-1791163477491` | 134 | HTTP 200, `es_activo=false` |
| `PRUEBA2` | 132 | HTTP 200, `es_activo=false` |
| `RASPBERRY3BPRUEBA` | 128 | HTTP 200, `es_activo=false` |
| `DISPOSITIVO-CAMARONERA-10` | 130 | HTTP 200, `es_activo=false` |

El diferencial PRE/POST confirmó que cambió exclusivamente `es_activo` de esos 5 dispositivos:
cero cambios en áreas, fincas, especies, activos biológicos y cualquier otro dispositivo; cero
cascadas. Tras el saneamiento, RF-17 resuelve **un único destino**, que es justamente la condición
que permite atribuir sin ambigüedad el `APLICADA` a un ACK real.

Estas 5 escrituras están registradas como **PREPARACIÓN / SANEAMIENTO DE FIXTURE** y no cuentan
como escrituras de TC-M09-62/63.

---

## PREFLIGHT Y ESTADO INICIAL DEL EDGE

Las 11 precondiciones del preflight del RUN válido pasaron:

| Precondición | |
| --- | --- |
| Especie 4 activa | ✅ |
| Variable 10 disponible y válida (admite 40–100) | ✅ |
| Sin umbral activo para especie 4 + variable 10 (sin riesgo de 409) | ✅ |
| Gateway activo administrativamente | ✅ |
| Gateway `conectada=true` | ✅ |
| Heartbeat reciente (`tiempo_sin_contacto` 0 s) | ✅ |
| Credencial MQTT emitida y habilitada | ✅ |
| Único destino RF-17 = `SERBY-TAX-FIRMWARE` | ✅ |
| Actor autenticado y autorizado | ✅ |
| Contrato `POST`/`PATCH` disponible en OpenAPI | ✅ |
| Fixture sin cambios respecto a lo entregado por Desarrollo | ✅ |

Contrato de propagación documentado desde el código desplegable, sin secretos:
`POST {MQTT_BROKER_URL}/v1/commands` con `origen: "umbral"` por Gateway → el broker publica en
`sgpmp/<serial>/command` con `tipo_comando: "UMBRAL_AMBIENTAL"` → espera `ACK_UMBRAL` hasta 30 s
→ devuelve `APLICADA` / `PENDIENTE` / `NO_CONF`. Timeout HTTP del backend: 35 s. El umbral se
guarda en un primer commit y el estado de sincronización en un segundo, por lo que **el 500 no
implica rollback**.

---

## TC-M09-62 — PROPAGACIÓN EXITOSA

### Parte 1 — Crear con Edge ONLINE

```
POST /configuracion/umbrales
{ id_especie: 4, id_variable_ambiental: 10, valor_min: 40, valor_max: 90,
  niveles: [normal 40–70, precaucion 70–80, critico 80–90] }
```

| Resultado | |
| --- | --- |
| HTTP | **201** en 1,278 s |
| `id_umbral_ambiental` | **65** |
| Persistido | 40.00–90.00 · normal 40–70 \| precaucion 70–80 \| critico 80–90 |
| `estado_sincronizacion` | **APLICADA** |
| `fecha_ultima_sincronizacion` | 2026-10-08T20:13:24.445890Z |
| `motivo_fallo_sincronizacion` | `null` |
| Auditoría | 1 registro (`CREATE`) |

### Parte 2 — Editar con Edge ONLINE (Configuración A)

```
PATCH /configuracion/umbrales/65
{ valor_min: 40, valor_max: 95,
  niveles: [normal 40–70, precaucion 70–85, critico 85–95],
  fecha_actualizacion: null }   ← valor exacto obtenido del GET previo
```

| Resultado | |
| --- | --- |
| HTTP | **200** en 1,321 s |
| Persistido | 40.00–95.00 · normal 40–70 \| precaucion 70–85 \| critico 85–95 |
| `estado_sincronizacion` | **APLICADA** |
| `fecha_ultima_sincronizacion` | 2026-10-08T20:18:32.740677Z (avanzó respecto al POST) |
| `motivo_fallo_sincronizacion` | `null` |
| Auditoría | 2 registros |

### Evidencia del ACK real

No se apoya solo en el valor `APLICADA`. Tres elementos convergen:

1. En el contrato desplegado, `APLICADA` solo puede originarse en el cuerpo que devuelve el broker
   **tras** el `ACK_UMBRAL` del Edge. El backend no construye ese estado por su cuenta y el stub
   que siempre devolvía `PENDIENTE` no existe en `src/`.
2. Con **un único destino**, la consolidación no puede enmascarar un Gateway sin ACK: habría dado
   `PENDIENTE` o `NO_CONF` con HTTP 500.
3. Los tiempos. 1,28 s y 1,32 s son coherentes con un viaje de ida y vuelta real a un Raspberry.
   El mismo endpoint, con el Edge ausente, falló en **0,449 s**: no salió a esperar a nadie.

### Resultado: APROBADO

**Observación 1 (no bloqueante):** el `POST` tardó **1,278 s** frente al objetivo de `< 1 s`
indicado por Desarrollo. Se clasifica como observación y no como fallo: las reglas de resultado
definen TC-M09-62 por propagación, ACK y `APLICADA`, y el tiempo medido es el viaje completo
backend → broker → publicación → `ACK_UMBRAL` → persistencia, con hardware real al otro extremo.

---

## PAUSA / INTERVENCIÓN AIoT

Entre TC-M09-62 y TC-M09-63, AIoT detuvo el servicio `edge-agent` y después desconectó
físicamente la Raspberry. QA no apagó, reinició ni manipuló hardware, no publicó mensajes MQTT
fabricados, no modificó la configuración del broker ni desconectó clientes.

Durante la espera se verificó por runtime, en solo lectura, que la indisponibilidad fuera real y
no una afirmación humana: heartbeat congelado en id 300 desde 20:19:55.802292Z, transición
automática `ACTIVO → SIN_SEÑAL` a las 20:25:50.176369Z con `causa_primaria: FALLO_CONECTIVIDAD`,
y ninguna transición posterior.

---

## TC-M09-63 — FALLO DE SINCRONIZACIÓN

### Estado previo verificado

| Elemento | Valor |
| --- | --- |
| Gateway | `SIN_SEÑAL` · `FALLO_CONECTIVIDAD` · heartbeat 300 congelado (~29 min sin contacto) |
| Broker | operativo (HTTP 200 en `/credencial-mqtt`) |
| Único destino RF-17 | `SERBY-TAX-FIRMWARE` |
| Baseline A | umbral 65 · 40.00–95.00 · `APLICADA` |
| `fecha_actualizacion` usada | 2026-10-08T20:18:31.855303Z |

### Escritura única — Configuración B

```
PATCH /configuracion/umbrales/65
{ valor_min: 40, valor_max: 100,
  niveles: [normal 40–70, precaucion 70–85, critico 85–100],
  fecha_actualizacion: "2026-10-08T20:18:31.855303Z" }
```

| Resultado | Esperado | Obtenido |
| --- | --- | --- |
| HTTP | 500 | **500** en **0,449 s** |
| `error_code` | `FALLO_SINCRONIZACION_EDGE` | **`FALLO_SINCRONIZACION_EDGE`** |
| Configuración central | B persistida | **40.00–100.00** |
| `estado_sincronizacion` | `PENDIENTE` | **`PENDIENTE`** |
| `motivo_fallo_sincronizacion` | Gateway no conectado | *"SERBY-TAX-FIRMWARE: Dispositivo offline. La configuración quedará pendiente hasta que reconecte."* |
| `fecha_ultima_sincronizacion` | no debe indicar que B se aplicó | **20:18:32.740677Z — la de A, sin avanzar** |
| ACK | ninguno | ninguno |
| Auditoría | asiento generado | 3 registros |

El mensaje contractual de RF-17 llegó en el cuerpo del 500: *"Configuración guardada en la base de
datos, pero falló la actualización de los nodos Edge. Es posible que las alertas en campo sigan
operando con los valores anteriores hasta que se restablezca la conexión."*

**La prueba más limpia de que B nunca llegó al campo es `fecha_ultima_sincronizacion`:** quedó en
el valor que dejó A. Si B se hubiera aplicado, habría avanzado. En cambio `fecha_actualizacion`
sí avanzó a 20:48:54.475814Z: B se guardó centralmente. El 500 no revirtió nada, como RF-17 exige.

### Hallazgo sobre las señales de conectividad

En el momento del PATCH, `GET /configuracion/dispositivos-iot/138/credencial-mqtt` reportaba
`conectada=true`, y sin embargo **el broker respondió al comando que el dispositivo estaba
offline**. Son dos señales distintas con semánticas distintas: `conectada` del endpoint de
credencial no es el estado de sesión que el broker usa para decidir si publica un comando.

Esto queda como **Observación 3**: `conectada` no debe utilizarse por sí sola como equivalente al
estado operativo que usa RF-17. Las señales fiables son la respuesta del propio broker al comando,
`estado_actual` `SIN_SEÑAL`/`INACTIVO` con `FALLO_CONECTIVIDAD`, y `fecha_ultimo_contacto`
congelada. No es un defecto: el flujo funcional se comportó exactamente como exige el requisito.

Observación operativa menor: `tiempo_sin_contacto` **no es un transcurrido en vivo** — se mantuvo
congelado en 354 s desde la evaluación periódica. Para medir frescura hay que derivarla de
`fecha_ultimo_contacto`.

---

## RESTAURACIÓN DEL EDGE

AIoT reconectó la Raspberry. Verificado por runtime en solo lectura:

| Elemento | Valor |
| --- | --- |
| Transición | `SIN_SEÑAL → ACTIVO` a las 20:55:36.386825Z · *"Reconexión por heartbeat id=302"* |
| Gateway 138 | `ACTIVO` · `conectada=true` · `causa_primaria=null` |
| Nodo 139 | `ACTIVO` |
| Heartbeats | 304 (20:55:48) → 306 (21:00:48) → 308 (21:05:48) · cadencia de 5 min exactos |

---

## POST-CHECK Y CLEANUP

### Ausencia de reenvío automático de B

Once muestras entre las 20:58:14 y las 21:07:22 — **~12 minutos tras la reconexión, con dos ciclos
completos de heartbeat cumplidos**. En todas:

| Campo | Valor constante |
| --- | --- |
| Configuración central | 40.00–100.00 (B) |
| `estado_sincronizacion` | `PENDIENTE` |
| `fecha_ultima_sincronizacion` | 20:18:32.740677Z — la de A |
| `motivo_fallo_sincronizacion` | *"…Dispositivo offline…"* (persiste) |
| `fecha_actualizacion` | 20:48:54.475814Z (nadie más editó el umbral) |

Si al reconectar se hubiera reenviado B, `fecha_ultima_sincronizacion` habría avanzado y el estado
habría pasado a `APLICADA`. **No hay reenvío automático**, coincidiendo con lo documentado en el
caso de uso: el umbral se propaga en la próxima edición.

### Edición final ONLINE — Configuración C

```
PATCH /configuracion/umbrales/65
{ valor_min: 40, valor_max: 98,
  niveles: [normal 40–70, precaucion 70–85, critico 85–98],
  fecha_actualizacion: "2026-10-08T20:48:54.475814Z" }
```

| Resultado | |
| --- | --- |
| HTTP | **200** en 0,888 s |
| Persistido | 40.00–98.00 · normal 40–70 \| precaucion 70–85 \| critico 85–98 |
| `estado_sincronizacion` | **APLICADA** |
| `fecha_ultima_sincronizacion` | 21:11:56.933882Z (avanzó respecto a A) |
| `motivo_fallo_sincronizacion` | `null` (el motivo de offline quedó limpio) |
| Auditoría | 4 registros |

B dejó de ser la configuración pendiente efectiva y C quedó aplicada.

### Traza de auditoría completa del umbral 65

```
#59 CREATE      ———      → 40–90    20:13:23   APLICADA   (TC-62 parte 1, Edge online)
#60 UPDATE      40–90    → 40–95    20:18:31   APLICADA   (TC-62 parte 2 · Configuración A)
#61 UPDATE      40–95    → 40–100   20:48:54   PENDIENTE  (TC-63 · Configuración B, Edge apagado, 500)
#62 UPDATE      40–100   → 40–98    21:11:56   APLICADA   (cierre · Configuración C, Edge reconectado)
#63 DEACTIVATE  40–98    → inactivo 21:16:41   —          (cleanup)
```

---

## RESULTADO DEL ORÁCULO

### TC-M09-62 — 8 de 8

Operación aceptada · Configuración persistida · destino Gateway real · intento real de
propagación · Edge confirmado disponible · propagación confirmada por el mecanismo real ·
`estado_sincronizacion = APLICADA` · `fecha_ultima_sincronizacion` correlacionable con el RUN ·
valores enviados iguales a los persistidos · `APLICADA` atribuible a ACK real y no a un stub.

### TC-M09-63 — 9 de 9 en la fase offline, 7 de 7 en la fase final

HTTP 500 · `error_code` correcto · B persistida · `PENDIENTE` · motivo informado · sin ACK ·
configuración central no perdida · respuesta rápida sin esperar ACK · `fecha_ultima_sincronizacion`
sin indicar que B se aplicó. Fase final: HTTP 200 · C persistida · `APLICADA` · fecha avanzada ·
sin motivo de fallo · B deja de ser la pendiente efectiva · ACK.

Ninguna de las cinco causas de rechazo tipificadas se materializó: no devolvió `NO_CONF`, no
esperó ~30 s intentando el ACK, el broker no lo trató como conectado ni publicó, no hubo estado
incompatible, y B sí persistió.

### Oráculo de conservación

```
A estaba aplicada antes de desconectar              ✅ verificado
B quedó centralmente PENDIENTE durante la caída     ✅ verificado
B no se reenvió al reconectar                       ✅ verificado (11 muestras, ~12 min, 2 ciclos)
C se aplicó en la edición siguiente                 ✅ verificado
A fue la configuración efectiva en campo            ⬜ NO VERIFICADA DIRECTAMENTE
```

**Observación 2 (no bloqueante): la conservación física de la Configuración A en
`/var/lib/sgpmp-edge/umbrales.json` NO fue verificada directamente.** QA no tiene acceso al
sistema de archivos del Raspberry ni existe endpoint del producto que devuelva la configuración
efectiva en campo.

Lo que sí demuestra la evidencia disponible: **B no fue reenviada automáticamente**, ni de forma
inmediata ni diferida. De ello se puede **inferir** que nada pudo sobrescribir A durante la
ventana offline, porque el broker nunca publicó B al Edge. Eso es una inferencia derivada del
contrato y del estado persistido, **no una observación física**, y así queda registrada. No se
presenta como evidencia de campo.

Nota operativa: ese punto ya **no es verificable retroactivamente**, porque la edición C
sobrescribió en el Edge lo que hubiera allí. Para cerrarlo en el futuro hay que leer
`umbrales.json` **durante** la ventana offline.

---

## COMPARACIÓN V1 VS V2 VS V3 VS V4 VS V5

| | V1 | V2 | V3 | V4 | **V5** |
| --- | --- | --- | --- | --- | --- |
| Ambiente | TEST | DEV | DEV | DEV | **TEST** |
| Propagación implementada | no | no | stub | stub | **adaptador MQTT real** |
| Intento real de propagación | — | no | no | no | **sí** |
| ACK del Edge | — | — | — | — | **sí** |
| `APLICADA` alcanzado | no | no | no | no | **sí** |
| Flujo de fallo (500 + `PENDIENTE`) | — | no | parcial | parcial | **sí, demostrado** |
| Edge real conectado | no | no | no | no | **sí** |
| TC-M09-62 | BLOQUEADO | DESAPROBADO | RECHAZADO | RECHAZADO | **APROBADO** |
| TC-M09-63 | BLOQUEADO | DESAPROBADO | RECHAZADO | NO EJECUTADA | **APROBADO** |
| Escrituras oficiales | 0 | 0 | 0 | 0 | **4** |

El avance parcial que V3 reconoció —estado de sincronización, motivo de fallo y HTTP 500— sigue
presente. Lo que cambia en V5 es la propagación misma: por primera vez existe, llega y se
confirma.

---

## ORIGEN / INTERPRETACIÓN DEL RESULTADO

El resultado adverso histórico tenía una causa de producto (el stub) y se corrigió. El resultado
favorable de V5 **no** se debe a una relajación del oráculo: se endureció. Se exigió un único
destino para que el `APLICADA` no pudiera provenir de una consolidación ambigua, y se contrastó el
mismo endpoint en los dos escenarios opuestos con el mismo fixture.

Dos impedimentos que aparecieron durante V5 **no eran defectos del producto** y conviene dejarlo
registrado para no confundir el historial:

1. **Dispersión del fixture de TEST.** La especie 4 acumulaba activos vivos en 34 áreas de muchas
   fincas, 6 con Gateway Edge registrado y solo uno conectado. El fan-out es correcto por diseño
   —un umbral pertenece a una especie, no a un área— y exigir que todos confirmen antes de
   declarar `APLICADA` es la lectura conservadora y correcta del RF. El impedimento era la
   dispersión del dato de prueba.
2. **Un intento anterior del RUN que terminó en `NO_CONF`** (ver sección siguiente). No se
   atribuyó causa ni responsable sin evidencia, y la reejecución con el fixture definitivo lo
   superó.

### Observación de diseño para el dueño del RF (no es defecto de este grupo)

En cualquier ambiente con más de un Gateway Edge por especie, `APLICADA` solo es alcanzable si
**todos** están simultáneamente online, de modo que toda edición de umbral devolvería HTTP 500
mientras alguno esté caído. En producción, con varias fincas, eso haría del 500 la respuesta
habitual y no la excepcional. Puede ser exactamente lo que RF-17 quiere, pero merece una decisión
explícita. Se registra como observación, sin incidencia y sin atribuir responsable.

---

## INTENTO ANTERIOR DEL RUN — `G29-REEVAL-V5-20261007-214956`

Se conserva como **antecedente y evidencia**. Sus escrituras **no se mezclan** con las del RUN
válido final.

Se ejecutó antes de disponer del fixture definitivo de Desarrollo y del Edge preparado por AIoT.
Recorrido:

- Preflight en DEV: gate cerrado por una única condición, el Edge destino
  (`DISPOSITIVOCAMARONERA41`) offline desde el 2026-10-05. 0 escrituras.
- Verificación del fixture indicado inicialmente por AIoT: existía en **TEST**, no en DEV
  (ids 138/139 inexistentes en DEV con actor de alcance global). 0 escrituras.
- Discovery completo en TEST (cobertura verificada: 76/76 especies, 152/152 fincas, 189/189
  dispositivos, 651/651 activos): ninguna especie resolvía solo Gateway online. 0 escrituras.
- Trazabilidad de los 5 destinos OFFLINE y su clasificación. 0 escrituras.
- Saneamiento del fixture: 5 desactivaciones de Gateway (preparación, no caso).
- **Una escritura oficial de TC-M09-62** sobre el umbral 48 (`PATCH` a 5.90–8.70), que resultó
  **RECHAZADO**: HTTP 500 con `estado_sincronizacion = NO_CONF` y motivo *"No se pudo contactar al
  broker MQTT para propagar el umbral"*, en 290 ms.

Diagnóstico de ese intento: **causa raíz Por determinar, responsable Por determinar.** La
evidencia accesible a QA confirma únicamente que la integración real fue intentada y terminó en
`NO_CONF` sin `ACK_UMBRAL`, y que **no fue por agotamiento de timeout** (el backend llegó al error
en 290 ms, muy lejos de los 30 s de espera de ACK y de los 35 s de timeout HTTP).

No fue posible recuperar la causa concreta: el camino de propagación de umbrales **no escribe en
la bitácora IoT** —`EdgeSincronizacionMqttAdapter` y `sincronizar_umbral_edge` solo usan
`logger.error`, a diferencia de RF-23, credenciales y alta/baja de dispositivos—, `/iot/auditoria`
no registró nada en la ventana, no hay tipos de evento de umbral ni de broker en el catálogo, y
ninguna de las 210 rutas de la API expone logs de aplicación. La única constancia es la línea de
log del contenedor del backend TEST, inaccesible para QA.

Ese intento no invalida el RUN final ni se contabiliza en su resultado. El umbral 48 que utilizó
quedó restaurado a su PRE original en el cleanup.

---

## INCIDENCIA

**INCIDENCIA REQUERIDA: NO.**

La corrección de **INC-M09-104-G29** (issue #493) está completa en lo que a este grupo concierne:
la propagación de umbrales RF-17 al Gateway Edge funciona, se confirma por ACK real y el flujo
alterno de fallo de sincronización se comporta como exige el requisito. **Se propone el cierre /
validación de la incidencia.**

Observaciones registradas, ninguna con incidencia asociada:

| # | Observación | Type | Severity | Priority |
| ---: | --- | --- | --- | --- |
| 1 | `POST` inicial de TC-M09-62 en 1,278 s frente al objetivo de `< 1 s` | Enhancement | Wishlist | Low |
| 2 | Conservación física de A en `umbrales.json` no observable desde QA; queda inferida | — | — | — |
| 3 | `conectada` del endpoint de credencial MQTT no equivale al estado operativo que usa RF-17 | Enhancement | Minor | Low |
| 4 | `tiempo_sin_contacto` es un valor almacenado, no un transcurrido en vivo | Enhancement | Wishlist | Low |
| 5 | El camino de propagación de umbrales no deja rastro en la bitácora IoT, lo que dificultó el diagnóstico del intento anterior | Enhancement | Minor | Normal |

No se atribuye causa ni responsable a ninguna sin evidencia.

---

## CLEANUP

Registrado como **CLEANUP / RESTAURACIÓN DE DATOS**, separado de las escrituras de TC-M09-62/63.
2 escrituras. 0 SQL. 0 registros eliminados físicamente.

### Umbral 65 — desactivado

| Elemento | Valor |
| --- | --- |
| Mecanismo | `PATCH /configuracion/umbrales/65/desactivar` (Flujo D de RF-17) |
| Resultado | **HTTP 200** · `es_activo = false` |
| Auditoría | asiento `DEACTIVATE` a las 21:16:41.872682Z (5 registros en total) |
| Confirmación independiente | una segunda llamada devuelve `422 UMBRAL_YA_INACTIVO`, sin efecto |
| Naturaleza | baja lógica, sin borrado físico y sin propagación al Edge |

### Umbral 48 — restaurado a su PRE original

| Elemento | Valor |
| --- | --- |
| Estado previo | 5.90–8.70 · `NO_CONF` (tal como lo dejó QA en el intento anterior) |
| Mecanismo | `PATCH /configuracion/umbrales/48` con el PRE exacto |
| Resultado | **HTTP 200** · **5.60–8.40** · normal 5.60–6.53 \| precaucion 6.53–7.46 \| critico 7.46–8.40 |
| `estado_sincronizacion` | `APLICADA` · `fecha_ultima_sincronizacion` 21:16:44.753466Z |
| `motivo_fallo_sincronizacion` | `null` |

La restauración se propagó porque el Edge estaba ONLINE. Se registra el resultado real por
transparencia, pero **no constituye una ejecución de TC-M09-62**: su finalidad fue devolver el
dato a su valor original.

### Estado final de los datos

| Umbral | Variable | Rango | `es_activo` | Sincronización | Nota |
| ---: | ---: | --- | --- | --- | --- |
| 10 | 1 | 0.00–100.00 | sí | `PENDIENTE` | preexistente, no tocado |
| 48 | 2 | 5.60–8.40 | sí | `APLICADA` | restaurado a su PRE original |
| 11 | 3 | 0.00–100.00 | sí | `PENDIENTE` | preexistente, no tocado |
| 65 | 10 | 40.00–98.00 | **no** | `APLICADA` | creado por esta reevaluación, desactivado |

**No quedaron datos temporales de esta ejecución**, con una única excepción documentada: los **5
Gateway Edge saneados permanecen inactivos** por decisión expresa del responsable QA, con
confirmación de AIoT de que eran registros antiguos de prueba ya no utilizados. No se reactivan.

No se modificó nada más: especie 4, finca 44, área 22, `SERBY-TAX-FIRMWARE` (138) y
`TEST-AMBIENTAL` (139) quedan intactos. Los informes V1–V4 no se alteraron.

### Seguridad

Escaneo final sobre `EvaluacionV5/`: 0 contraseñas, 0 JWT, 0 cabeceras `Authorization`, 0
credenciales MQTT. Solo aparecen nombres de clave (`tokenPersistido: false`). Git intacto: no se
ejecutó `add`, `commit`, `push`, `merge`, `rebase`, `reset`, `clean`, `stash`, `switch` ni
`checkout`.

---

## CONCLUSIÓN

**TC-M09-G29 queda APROBADO CON OBSERVACIONES.**

Las dos preguntas que V5 debía responder con evidencia quedan respondidas:

> **TC-M09-62 — ¿Un cambio RF-17 realmente llega al Gateway/Edge y queda confirmado como aplicado?**
>
> **Sí.** Crear y editar un umbral con el Edge presente produce HTTP 201/200, `estado_sincronizacion
> = APLICADA` y `fecha_ultima_sincronizacion` informada, con un único Gateway destino real y en
> tiempos coherentes con un ACK de hardware real (1,28 s y 1,32 s).

> **TC-M09-63 — ¿Cuando ese mismo Edge no está disponible, el servidor conserva la nueva
> configuración como pendiente, responde 500 y el Edge mantiene la configuración anterior?**
>
> **Sí en las tres primeras partes, inferido en la cuarta.** La configuración queda guardada
> centralmente, el umbral pasa a `PENDIENTE` con el motivo informado, se responde HTTP 500
> `FALLO_SINCRONIZACION_EDGE` en 0,449 s sin esperar ACK, y `fecha_ultima_sincronizacion` no
> avanza. Que el Edge mantuviera la configuración anterior **no pudo observarse directamente**: se
> infiere de que B nunca se publicó —ni con el equipo apagado ni al reconectar— y se registra como
> inferencia, no como evidencia física.

El defecto histórico de integración de RF-17 está corregido. Se propone el cierre de
**INC-M09-104-G29**.

Para cerrar el único punto que quedó inferido, la próxima evaluación que toque este flujo debería
contar con una vía de lectura de la configuración efectiva en el Edge —el archivo
`umbrales.json` o un endpoint del producto— y consultarla **durante** la ventana de desconexión.
