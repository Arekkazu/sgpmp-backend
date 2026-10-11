# TC-M09-G127 / G128 — Seguridad del canal IoT (RF-23)

**RF:** RF-23 — Configuración remota de dispositivos IoT.
**Repos:** `BROKER-MQTT-SGPMP` (rama `fix/lote-qa-2026-09-26`) y `sgpmp-backend`.

## Resumen

| Caso | Prueba de QA | Estado | Dónde |
|---|---|---|---|
| TC-M09-250 | Publicar en el topic de configuración de un dispositivo ajeno | **Abierto** — RFC | broker (`docs/RFC_credencial_mqtt_por_dispositivo.md`) |
| TC-M09-251 | `SUBSCRIBE #` para interceptar tráfico de otros dispositivos | **Abierto** — RFC | igual |
| TC-M09-252 | Reenviar (replay) un mensaje de configuración o ACK capturado | **Resuelto en servidor** | broker: `id_comando` + `emitido_en` |
| TC-M09-253 | El broker acepta conexiones sin TLS | **Resuelto en servidor** para test/prod | broker: `MQTT_PUERTO_PUBLICO` / `MQTT_WS_PUERTO_PUBLICO` |
| TC-M09-254 | Replay de un *join-request* LoRaWAN | **No aplica a este sistema** | ver más abajo |
| TC-M09-255 | Unicidad de las claves de sesión LoRaWAN | **No aplica a este sistema** | ver más abajo |

"Resuelto en servidor" quiere decir que el broker ya lo hace; en 252 falta además que el firmware devuelva el
`id_comando` en el ACK, y en 253 que Ops monte los certificados y defina las dos variables en test/prod. `dev`
sigue sin TLS por decisión del equipo.

## TC-M09-250 y 251 — por qué no se cierran en este lote

Todos los dispositivos usan **una sola credencial MQTT** (`sgpmp_devices`). Reproducido contra Mosquitto 2.1.2
con la ACL actual: un cliente con esa credencial se suscribe a `#`, el `SUBACK` se concede y recibe
`sgpmp/OTRO-DISPOSITIVO/command {"frecuencia_captura":60,"intervalo_transmision":300}`. La telemetría y el
`status` sí quedan filtrados; el `command` no, porque la ACL da `topic read sgpmp/+/command` a todo el que
tenga la credencial.

Sin una credencial por dispositivo, Mosquitto no puede distinguir a un dispositivo de otro, y tampoco hay
forma de probar el aislamiento. Cerrarlo exige un usuario MQTT por dispositivo (usuario = serial), lo que
toca lo que el sistema debe hacer (alta y revocación por dispositivo) y por tanto **pasa por RFC formal**. Se
dejó la propuesta con mediciones reales en el repositorio del broker:

- Con `dynamic-security` y un rol con `%u`: `#`, `sgpmp/#`, `sgpmp/+/command` y el `command` de otro serial →
  denegados (el `SUBSCRIBE` recibe un código de fallo); publicar en `status`/`command` de otro serial →
  `RC:135`; el dispositivo víctima solo recibió el mensaje legítimo del gateway.
- Con `acl_file` + `pattern %u` la fuga también se cierra en la práctica (solo entrega lo propio), pero el
  `SUBACK` de `#` se concede, así que **no** cumple el criterio literal de TC-M09-251.
- Un dato para quien escriba la prueba: en MQTT 3.1.1 un publish denegado se responde con `PUBACK RC:0` y se
  descarta en silencio. Para verificar el aislamiento hay que usar MQTT v5 o comprobar la entrega real.

**Consecuencia sobre 252:** con la credencial compartida un dispositivo malicioso puede leer el `command` de
otro serial (251) y, por tanto, su `id_comando`, y forjar el ACK. El anti-replay cierra el ACK reenviado o
forjado *sin* conocer el id; cerrar 251 cierra también esa vía.

## TC-M09-252 — anti-replay (hecho)

El comando lleva `id_comando` (uuid4) y `emitido_en` (UTC). La espera de ACK guarda el id esperado por serial y
un ACK con **otro** id se ignora sin consumir la espera, de modo que el ACK legítimo que llegue después
todavía resuelve. Un ACK sin id se acepta por compatibilidad (con un aviso) hasta que el firmware lo devuelva;
`MQTT_ACK_REQUIERE_ID_COMANDO=true` lo rechaza.

El **replay de un ACK real capturado** que QA ya probó (no duplicaba el registro) sigue sin duplicar. Lo que
cambia es que un ACK reenviado dentro de la ventana de otro comando ya no lo confirma. Del lado del
dispositivo, el contrato pide no re-aplicar un `id_comando` ya procesado y descartar un `emitido_en` viejo.

## TC-M09-253 — TLS (hecho para test/prod)

El gateway usa el texto plano por la red interna de Docker, así que ese listener no se puede apagar; lo que se
controla es qué puertos se publican al host. Con `MQTT_PUERTO_PUBLICO=8883` y `MQTT_WS_PUERTO_PUBLICO=9002` el
host publica solo los listeners TLS **en los mismos puertos de host de siempre** (no hay que tocar el
firewall). Si se pide TLS y faltan los certificados, el broker no arranca.

Verificado con un certificado autofirmado y un cliente paho desde el host: TCP y WebSocket en texto plano con
credenciales válidas no reciben `CONNACK`; `mqtts` y `wss` conectan; los puertos planos no están publicados.
`dev` no tiene certificados y sigue en texto plano, tal como dice el propio caso de prueba
("debe exigirse en producción").

## TC-M09-254 y 255 — LoRaWAN: por qué no aplican

Las dos pruebas piden repetir un *join-request* con el mismo `DevNonce` y comparar las claves de sesión
(`AppSKey`/`NwkSKey`) entre dispositivos. Eso ocurre dentro de un **servidor de red LoRaWAN**, y este sistema
no tiene ninguno: la Raspberry y el gateway hablan **MQTT directo** con Mosquitto (topics
`sgpmp/<serial>/command` y `sgpmp/<serial>/status`). No hay ningún *join-request* ni clave de sesión por
en medio. Armar una prueba parcial ahí sería fingir una cobertura que no existe.

### Qué es ChirpStack y quién lo maneja

Son capas distintas, y por eso la confusión es natural:

- **LoRaWAN** es el protocolo de **radio** de largo alcance y bajo consumo entre los *sensores* (con un chip
  LoRa) y los *gateways LoRa* (un concentrador de radio; una Raspberry con una placa LoRa puede hacer ese
  papel).
- El **servidor de red LoRaWAN** recibe las tramas de los gateways, atiende el *join* (donde aparecen el
  `DevNonce` y se derivan las claves `NwkSKey`/`AppSKey`), descarta duplicados y repeticiones, y descifra. Es
  el software que hace todo eso. **ChirpStack es una implementación de código abierto de ese servidor de red.**
  No es un broker MQTT: lo que hace es *usar* un broker MQTT como bus de integración (entre el gateway y el
  servidor, y para publicar los datos ya decodificados hacia otras aplicaciones).
- Lo maneja quien administre la red de sensores (el equipo de IoT/infraestructura), no este backend ni este
  broker. Sus protecciones anti-replay y de claves las da el propio servidor de red y el firmware del sensor.

Así que "MQTT sobre LoRaWAN" del RF-23 describe una **arquitectura** posible: sensores LoRa → gateway LoRa →
servidor de red (ChirpStack) → broker MQTT → SGPMP. La que está construida y que QA observó es más corta:
dispositivo/Raspberry → MQTT → Mosquitto → SGPMP.

### Pregunta abierta para Análisis / IoT

**¿RF-23 realmente exige soportar LoRaWAN?** El texto (`Especificacion-Requerimientos-Modulo9.md`, líneas
1845, 1928 y 2099) dice "mediante el protocolo MQTT sobre la red LoRaWAN", y el flujo alterno menciona "el
gateway LoRaWAN está inaccesible".

- **Si la respuesta es no:** TC-M09-254/255 se declaran fuera de alcance del sistema, y el RF debería
  corregirse para no mencionar LoRaWAN.
- **Si la respuesta es sí:** el defecto real no es G128 sino **G69**: el campo `protocolo` no existe en el
  sistema (ni en el DTO, ni en el modelo, ni en la BD) y se ignora sin avisar; habría que modelarlo, validarlo
  y desplegar el servidor de red. Es un cambio de arquitectura, no de este lote.

Mientras tanto, G128 queda sin ejecutar a propósito.
