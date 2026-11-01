# Plan de ejecución adaptado — E2, E3, E5 (IDs 65 y 48)

Fecha: 2026-10-30. **No ejecutado.** Sin PUBLISH MQTT, sin `POST /v1/commands`, sin PATCH de umbrales, sin reinicio, sin E6.

Variables autorizadas (Majo + `UMBRALES_ORIGINALES.json`):

| id_umbral_ambiental | Nombre en disco / M09 | unidad | version vigente |
|---|---|---|---|
| **65** (preferido para E2/E3/E5) | `Humedad Relativa` | `%` | `2026-10-08T21:11:56.393005+00:00` |
| **48** (equivalente para ACK) | `pH del agua` | `pH` | `2026-10-08T21:16:43.262342+00:00` |

`id_variable_ambiental` del catálogo (p. ej. 10 en G29 para Humedad Relativa) **no viaja** en el comando RF-17. El Edge indexa por `id_umbral_ambiental`.

---

## 1. Cómo identifica cada componente la variable

| Capa | Qué usa | Qué espera | Código / contrato |
|---|---|---|---|
| Backend catálogo | `modulo9.variables_ambientales.nombre` + `id_variable_ambiental` + `codigo_telemetria` | Nombre de negocio, p. ej. `Humedad Relativa`; código `HUMEDAD_RELATIVA` | modelo `variable_ambiental_model.py`; migración RF-53 |
| Backend → broker | `variable`: **nombre** pasado a `payload_umbral(umbral, nombre_variable)` | El mismo `nombre` de M09, no el snake_case del firmware ni el código `HUMEDAD_RELATIVA` | `sincronizar_umbral_edge.py` |
| Backend → broker | `id_umbral_ambiental` | Entero del umbral RF-17 (65 / 48), no el id de catálogo | mismo payload |
| Broker | Copia `variable` y `id_umbral_ambiental` al MQTT; no resuelve catálogo | `UmbralCommandRequest.variable: str` (cualquier no vacío); `id_umbral_ambiental: int > 0`; `niveles` mínimo 1 banda | `app/schemas.py`, `dispatch._cuerpo_comando` |
| Broker | `serial` | Serial del **Gateway Edge** | RF-17: `RASPBERRY3B-TEST`, no el nodo ESP |
| Topic | `sgpmp/<serial>/command` | `tipo_comando: "UMBRAL_AMBIENTAL"` | `INTEGRACION_DISPOSITIVOS_RF17.md` |
| Firmware `handle_umbral` | `id_umbral_ambiental` para `UmbralStore.get` | Entero > 0; clave de persistencia | `commands.py` + `agent.py` `self._umbrales.get(id)` |
| Firmware `handle_umbral` | `variable` | String no vacío; se **guarda tal cual** si el umbral es válido | no normaliza a snake_case |
| Firmware evaluador | `umbral.variable == reading.variable` | **Igualdad exacta de cadena** | `evaluador.py` |
| Firmware THI (`VARIABLES_DEFECTO`) | canónico `HUMEDAD_RELATIVA` → `humedad_relativa` | Solo reglas 55.2; **no** reescribe el umbral RF-17 | `formulas.py` |
| Telemetría fake | `FakeVariable.nombre` | El texto de `EDGE_FAKE_VARIABLES` | `sources.py` |
| Disco lab | `"variable": "Humedad Relativa"` | — | `UMBRALES_ORIGINALES.json` |

El broker **no** exige las tres bandas ni `valor_min < valor_max`. Un E2/E3/E5 inválido **puede publicarse** por `POST /v1/commands` y llegar al Edge. El rechazo RF-55 es del firmware (`motivo_niveles`), no del schema del broker.

---

## 2. `humedad_relativa` vs `Humedad Relativa`

No son el mismo identificador.

| Forma | Uso | ¿Está en el lab? |
|---|---|---|
| `Humedad Relativa` | `modulo9.variables_ambientales.nombre`; disco Edge; contrato RF-17 (`variable` = nombre M09) | **Sí** (umbral 65) |
| `HUMEDAD_RELATIVA` | `codigo_telemetria` RF-53; clave canónica interna 55.2 | No viaja en `umbrales.json` |
| `humedad_relativa` | Valor por defecto de `VARIABLES_DEFECTO` y de `casos_rf55.json` (inyector) | **No** en disco |

Si un comando **válido** guardara `variable: "humedad_relativa"` sobre el id 65, las lecturas que el Edge emita como `Humedad Relativa` (si el fake/LoRa usa el nombre M09) **dejarían de casar** el umbral. E2/E3/E5 no deben introducir ese snake_case.

Para estos tres escenarios el campo `variable` es obligatorio pero, si `motivo_niveles` falla, **no se llama a `set()`**. Aun así el payload usará el nombre real del laboratorio, no uno inventado.

---

## 3. ¿Se pueden usar 65 o 48 sin cambiar código?

**Sí**, para E2, E3 y E5:

- No hace falta parche de firmware, broker ni backend.
- El store sustituye/consulta por **id**; 65 y 48 ya existen.
- El nombre va en el JSON del comando, copiado del disco.
- No se usa `temperatura_ambiente` ni id 7 del fixture.

Preferencia: **id 65** (`Humedad Relativa`), análogo ambiental al T de `casos_rf55.json`. El 48 sirve igual para el CA de ACK ERROR. No mezclar los dos ids en el mismo intento.

Canal previsto (sin ejecutar):

1. **Técnicamente alineado con el producto:** `POST {MQTT_BROKER_URL}/v1/commands` `origen: "umbral"`, `serial: "RASPBERRY3B-TEST"`. El broker añade `id_comando`, `emitido_en`, `tipo_comando`.
2. **MQTT directo** a `sgpmp/RASPBERRY3B-TEST/command`: el usuario de monitorización de QA **solo se comprobó en SUB**. El usuario del dispositivo suele **SUB** `command`, no PUB. **Publicar MQTT no está confirmado** (Sergio).

No usar `PATCH /configuracion/umbrales/{id}`: escribiría la BD de TEST y, si el umbral fuera válido, sincronizaría de verdad.

---

## 4. Persistencia vs ACK ERROR

`motivo_niveles` (`evaluador.py` develop) corre **antes** de guardar. Si devuelve texto → `ACK_UMBRAL` `resultado: ERROR` y `Umbral.umbral is None` → **no hay `set()`** → disco y memoria **no cambian**.

| Escenario | Defecto | Motivo firmware esperado (substring) | ¿Persiste? |
|---|---|---|---|
| E2 | `valor_min == valor_max == 0` | `valor_min y valor_max deben ser números con valor_min < valor_max` | **No** (código `e618a75`) |
| E3 | banda `precaucion` ancho 0 | `la banda precaucion debe tener ancho mayor que 0` | **No** |
| E5 | solo banda `normal` | `niveles debe traer normal, precaucion y critico, una vez cada uno` | **No** |

Riesgo residual: si el binario de la Pi no coincidiera con ese `motivo_niveles`, un comando “inválido” podría guardarse. Por eso el paso de **verificar el JSON** es obligatorio aunque el código diga que no persiste.

`valor_min`/`valor_max`/`límites` deben ir como **números JSON**, no como strings. `_es_numero` solo acepta `int|float`. El backend manda strings; el broker (float) los convierte. Un PUB MQTT con `"0"` en string saldría ERROR por tipo, no por el CA de E2.

No reutilizar `comando_id` ya guardado (`6743369e…` / `7b899854…`): el firmware respondería **OK** de reentrega y no ejercitaría E2/E3/E5. El broker genera un UUID nuevo; en MQTT directo hay que generar otro.

---

## 5. Payloads (aún no enviados)

Topic lógico: `sgpmp/RASPBERRY3B-TEST/command`.  
Cuerpo HTTP: lo de abajo **más** `origen` y `serial`. El broker completa `id_comando` y `emitido_en`.  
`version` se copia de la vigente para no inventar otra; en E2/E3/E5 da igual porque el rechazo de bandas ocurre **antes** del chequeo de versión.

### E2 — TC-M03-095 (id 65)

CA original: umbral en cero se rechaza; no hay clasificación de la lectura; **no** división por cero.

```json
{
  "origen": "umbral",
  "serial": "RASPBERRY3B-TEST",
  "id_umbral_ambiental": 65,
  "version": "2026-10-08T21:11:56.393005+00:00",
  "variable": "Humedad Relativa",
  "unidad": "%",
  "valor_min": 0.0,
  "valor_max": 0.0,
  "niveles": [
    {"nivel": "normal", "limite_inferior": 0.0, "limite_superior": 0.0},
    {"nivel": "precaucion", "limite_inferior": 0.0, "limite_superior": 0.0},
    {"nivel": "critico", "limite_inferior": 0.0, "limite_superior": 0.0}
  ]
}
```

Esperado MQTT `sgpmp/RASPBERRY3B-TEST/status`: `tipo_mensaje=ACK_UMBRAL`, `resultado=ERROR`, `id_comando` del comando, motivo con `valor_min < valor_max`. Sin `evento` de clasificación por este comando.

### E3 — TC-M03-095 (id 65, bandas del lab con precaución degenerada)

CA original: banda de ancho cero → ACK ERROR. Números de **Humedad Relativa** (40–98), no los 18–32 de temperatura del fixture.

```json
{
  "origen": "umbral",
  "serial": "RASPBERRY3B-TEST",
  "id_umbral_ambiental": 65,
  "version": "2026-10-08T21:11:56.393005+00:00",
  "variable": "Humedad Relativa",
  "unidad": "%",
  "valor_min": 40.0,
  "valor_max": 98.0,
  "niveles": [
    {"nivel": "normal", "limite_inferior": 40.0, "limite_superior": 70.0},
    {"nivel": "precaucion", "limite_inferior": 70.0, "limite_superior": 70.0},
    {"nivel": "critico", "limite_inferior": 70.0, "limite_superior": 98.0}
  ]
}
```

Esperado: ACK ERROR, motivo de ancho 0 en `precaucion`.

### E5 — TC-M03-122 (id 65, solo `normal`)

CA original: umbral sin bandas de severidad → ACK ERROR; no inventar CRITICO (eso es E6, **fuera de este plan**).

```json
{
  "origen": "umbral",
  "serial": "RASPBERRY3B-TEST",
  "id_umbral_ambiental": 65,
  "version": "2026-10-08T21:11:56.393005+00:00",
  "variable": "Humedad Relativa",
  "unidad": "%",
  "valor_min": 40.0,
  "valor_max": 98.0,
  "niveles": [
    {"nivel": "normal", "limite_inferior": 40.0, "limite_superior": 98.0}
  ]
}
```

Esperado: ACK ERROR, motivo de las tres bandas. El broker acepta `niveles` de longitud 1; el Edge no.

Variante id 48: mismos defectos, `variable: "pH del agua"`, `unidad: "pH"`, rangos 5.6 / 8.4 y bandas 5.6–6.53 / 6.53–7.46 / 7.46–8.4 (E3: precaución 6.53–6.53).

---

## 6. Restauración y sincronía disco ↔ memoria

Respaldo ya tomado: `UMBRALES_ORIGINALES.json` (cat 2026-10-30T15:28:28Z).

Si E2/E3/E5 se comportan como `develop`:

1. Tras cada ACK ERROR: `sudo -n -u sgpmp-edge cat /var/lib/sgpmp-edge/umbrales.json`.
2. Comparar con el respaldo (ids 65 y 48, bandas, `version`, `comando_id`).
3. Memoria: `UmbralStore.set` no corre → el proceso sigue con lo cargado al arranque / último `set` válido. **No hay API de volcado de memoria.** Comprobar memoria exigiría una lectura clasificada con las bandas originales (telemetría no observada) o reiniciar y volver a leer disco. El reinicio **no está autorizado** en esta preparación.

Si el JSON **difiere** del respaldo:

1. Detenerse. No seguir con el siguiente escenario.
2. Restauración segura (fase posterior, con autorización): copiar el respaldo a `umbrales.json` **y** recargar memoria (`systemctl restart edge-agent`) **o** republicar el umbral **válido original** (65 o 48) por `POST /v1/commands` con `version` **≥** la vigente para que `handle_umbral` haga `set()`. Un `cat` solo, con el agente vivo, **no** actualiza memoria.

No restaurar con `humedad_relativa` ni con id 7.

---

## 7. Matriz de ejecución

| ID | ¿Ejecutable técnicamente ahora? | Falta Sergio / ops | Precondiciones | Payload | Esperado | Evidencia |
|---|---|---|---|---|---|---|
| E2 | **Sí, condicionado** al canal de comando | Token broker TEST (`MQTT_BROKER_TOKEN` / servicio); confirmar `serial` Gateway; **no** PUB MQTT hasta confirmar ACL; monitor ya SUB `#` | Respaldo JSON; agente `active`; MQTT ESTAB; no reusar `comando_id` viejo; números JSON; nombre `Humedad Relativa` | §5 E2, id **65** | `ACK_UMBRAL` ERROR; motivo min&lt;max; JSON = respaldo | `status` MQTT; HTTP 200 del broker con estado acorde al ACK ERROR (NO_CONF típico); `cat` umbrales; no evento de clasificación |
| E3 | Igual | Igual | Igual; E2 ya verificado sin mutar disco | §5 E3 | ACK ERROR ancho 0; JSON intacto | Igual |
| E5 | Igual | Igual | Igual | §5 E5 | ACK ERROR tres bandas; JSON intacto | Igual |
| E2/E3/E5 por MQTT PUB QA | **No** hasta confirmar | ACL PUB `command` del usuario de prueba | — | — | — | — |
| E2/E3/E5 vía PATCH backend | **No** | Escribiría BD TEST | — | — | — | — |
| E1, E4, E6, S8 | **No** (informe de sensores) | Lecturas HR/pH; E6 disco+memoria | — | — | — | — |
| Probar con `humedad_relativa` | **No** | Introduciría un nombre que el lab no usa | — | — | — | — |

Orden si se autoriza: **E2 → verificar JSON → E3 → verificar → E5 → verificar**. Un solo id (65). Si E2 muta disco, abortar y restaurar.

---

## 8. Qué sigue siendo de Sergio

1. Autorización para enviar **un** comando de prueba (broker HTTP, no PATCH).
2. Cómo entregar el Bearer del broker sin dejarlo en Git.
3. Confirmación de que el destino es `RASPBERRY3B-TEST` (Gateway).
4. Si insistimos en MQTT crudo: qué usuario puede **PUB** `command`.
5. Opcional: id 48 en lugar de 65.
6. Cómo quiere ver la memoria (reinicio vs telemetría HR), si el `cat` no basta.

Hasta esa autorización, E2/E3/E5 están **preparados y no ejecutados**.
