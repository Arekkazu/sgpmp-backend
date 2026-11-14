# Diagnóstico: Paho CONNACK 135 vs mosquitto_sub de Sergio

Fecha: 2026-10-30. **Sin cambios de código, sin CONNECT nuevo, sin G38, sin secretos.**

Cliente QA analizado: script de la corrida `run-2026-10-30-mqtt-v5-device` (paho 2.x, MQTT v5) y el patrón permanente G69 (`test_tc_m09_g69_protocolo_mqtt_reintento1.py`).

Sergio: `mosquitto_sub` MQTT v5, usuario `RASPBERRY3B-TEST`, clave de la Raspberry, éxito.

---

## 1. Lectura de variables

| Fuente | Cómo lee |
|---|---|
| G69 (repo) | `os.environ.get("MQTT_HOST")` etc. **en import**. **Sin `.strip()`**. Puerto: `int(MQTT_HOST_PORT)`. |
| Corrida v5 QA | PowerShell copia User → proceso; Python `os.environ.get(...).strip()` en host/puerto/usuario/prefijo. **`MQTT_PASSWORD` sin strip.** `username_pw_set(user, password)` antes de `connect`. |

Higiene User (2026-10-30, sin revelar valores):

| Variable | SET | Extra WS / CR / LF / TAB / NBSP | Notas |
|---|---|---|---|
| MQTT_HOST | sí | no | igual a `149.130.169.209` |
| MQTT_HOST_PORT | sí | no | igual a `1886` |
| MQTT_USERNAME | sí | no | igual a `RASPBERRY3B-TEST` (16 caracteres) |
| MQTT_PASSWORD | sí | no | **8 caracteres UTF-8**; `equals_strip` true |
| MQTT_TOPIC_PREFIX | sí | no | igual a `sgpmp` |

No hay espacios ni saltos de línea en la contraseña almacenada. El fallo **no** se explica por padding.

---

## 2. `username_pw_set()`

En G69 y en la corrida v5: se llama **antes** de `connect`, con usuario y contraseña no vacíos. Eso es el uso correcto de Paho. No se encontró un CONNECT sin usuario.

---

## 3. MQTT v5

- Corrida que dio 135: `protocol=mqtt.MQTTv5`, `CallbackAPIVersion.VERSION2`. Alineado con `test_dev_acl.py` del firmware y con `mosquitto_sub -V mqttv5` de la guía del broker.
- G69 usa **`MQTTv311`**, no v5.
- El `edge_agent` en la Pi usa **`MQTTv311`**, `clean_session=False`, `client_id` fijo `edge-<primer serial>` (`mqtt_client.py`).

Sergio en v5 y el agente en v3.1.1 pueden convivir; el 135 no es un error de “Paho no estaba en v5”.

---

## 4. Callback e interpretación de CONNACK

Paho 2 VERSION2: `on_connect(..., reason_code, properties)`.

- `int(reason_code)` / `reason_code.value` → **135** = MQTT 5 **0x87 Not authorized**.
- El texto del broker/`ReasonCode` fue `Not authorized`.
- MQTT 5 distingue **134** Bad user name or password vs **135** Not authorized. Mosquitto/dynsec a menudo usa **135** también cuando la clave no coincide.

**No hay mala interpretación del código.** El CONNACK es de rechazo de autorización, no un 0 mal mapeado.

Disconnect **128** Unspecified error es el cierre posterior al CONNACK de rechazo (comportamiento de Paho), no una segunda causa.

---

## 5. `client_id`

| Cliente | client_id |
|---|---|
| Raspberry `edge_agent` | `edge-RASPBERRY3B-TEST` (fijo, sesión persistente) |
| Paho QA v5 | `qa-g38-v5-<unix>` (distinto en cada corrida) |
| `mosquitto_sub` típico | id aleatorio tipo `mosq-...` si no se pasa `-i` |

**No hay colisión con la Raspberry.** Dos clientes con el mismo `client_id` se expulsan; eso no produce 135, produce desconexión del otro. Un id QA aleatorio es lo correcto y coincide con el estilo de `mosquitto_sub` y de `acl-probe-*` en `test_dev_acl.py`.

---

## 6. Comparación con mosquitto_sub (guía broker + Sergio)

Guía (`GUIA_CONEXION_IOT.md` / RF-17):

```text
mosquitto_sub -h <host> -p <puerto> -V mqttv5 -u <serial Edge> -P '<clave>' -t "sgpmp/<serial>/command"
```

| | mosquitto_sub (Sergio / docs) | Paho QA v5 |
|---|---|---|
| Protocolo | MQTT v5 | MQTT v5 |
| Auth | `-u` serial `-P` clave | `username_pw_set` |
| TLS | no en el ejemplo; la Pi TEST usa **TLS=False** en `:1886` | sin `tls_set` (correcto para 1886 plano) |
| client_id | usualmente omitido | `qa-g38-v5-*` |
| Topics | a menudo `sgpmp/<serial>/command` | `sgpmp/+/…` (solo se envían **después** de CONNECT OK; aquí no se llegó) |
| Origen de la clave | archivo/env de la **Raspberry** | User Windows vía Get-Credential |

La guía dice que TEST “solo TLS”; **contradice** el laboratorio: `edge-agent` y Danna usan TCP **1886 sin TLS**. Un fallo TLS no daría CONNACK MQTT 135. Se descarta como causa de este 135.

Los wildcards `sgpmp/+/#` podrían fallar en **SUBACK** (ACL por serial), no en CONNECT. Sergio se suscribe a un topic del propio serial. Eso **no explica** el 135 de CONNECT.

---

## Causas posibles (antes de tocar código)

1. **Más probable — contraseña User ≠ clave dynsec de la Pi.** La Pi conecta; Sergio usa esa clave; Windows User tiene un secreto de **8 caracteres**, típico de una clave corta o incompleta al teclear en Get-Credential, no de un secreto rotado largo. Mosquitto responde 135. **No se modificó código ni se reintentó CONNECT.** Acción: volver a cargar `MQTT_PASSWORD` desde la fuente de Sergio/Pi (cuadro seguro), no desde memoria.
2. **Poco probable — client_id.** No coincide con `edge-RASPBERRY3B-TEST`; mosquitto_sub tampoco usa ese id.
3. **Descartado — espacios en env, MQTT v3 vs v5 mal anunciado, mala lectura del rc, G69 sin username_pw_set.**
4. **Fuera del cliente QA —** usuario deshabilitado para un segundo login; Sergio habría fallado igual salvo que su prueba fuera **en** la Pi (un solo cliente). Preguntar si `mosquitto_sub` fue en la Raspberry o en su PC.

## Qué no hacer todavía

No cambiar Paho a v3.1.1 “por si acaso”, no reutilizar `client_id` del agente (echaría a la Pi), no publicar, no G38.

Si tras recargar la **misma** clave que usa Sergio el CONNACK sigue en 135, entonces sí conviene un CONNECT de diagnóstico con `client_id=""` (id asignado por el broker, como mosquitto_sub) — **previa autorización**.
