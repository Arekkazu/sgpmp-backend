# INC-M03-118-G61 — Validación pendiente del SLA de detección en Edge (RF-55, TC-M03-123)

**RF:** RF-55 (restricción 1 y CA-1). **Grupo:** TC-M03-G61. **Caso:** TC-M03-123
(`test_tc_m03_123_sla_edge_aislado_de_rf56`). **Issue:** #662.
**Estado:** **bloqueado** por el equipo Edge. El backend deja la evidencia por evento.

## Respuesta a las preguntas de QA

### ¿Existe ya el simulador en otro repositorio o entorno?

**Existe un simulador de datos, pero no el detector que mide el SLA.** Se revisó el repo de firmware
`SerBy48/EDGE-FIRMWARE-SGPMP` (rama `develop`, commit `66a22a2`, solo lectura):

| Pieza | Estado |
|---|---|
| `FakeLoraSource` (`raspberry/edge_agent/sources.py`), con `EDGE_SOURCE=fake` y `EDGE_FAKE_VARIABLES=temperatura_ambiente:C:20:30` | **Existe.** Genera lecturas sintéticas y el agente las publica como telemetría |
| `SENSOR_SIMULADO` en el firmware ESP32 | **Existe.** Temperatura y humedad sintéticas en el nodo sensor |
| Umbrales de RF-17 en el Edge (`UmbralStore`, `umbrales.json`) | **Existe.** Los recibe, los guarda y confirma con `ACK_UMBRAL` |
| **Detección RF-55** (evaluar cada lectura contra los umbrales y generar el evento NORMAL / DESVIACION_SIMPLE) | **No existe.** El README del agente dice: *"Evaluar las lecturas contra esos umbrales es de RF-55"*. El agente publica telemetría, heartbeat y estado, pero no eventos Edge |

El SLA de RF-55 mide justamente esa detección, así que **no hay nada que medir todavía**. Es la
misma causa del bloqueo de INC-M03-111-G43 (#647): el `edge_agent` no implementa RF-55.

### ¿Debe implementarse?

**Sí, en el `edge_agent`** (equipo Edge / AIoT), no en el backend. RF-55 ubica la detección en
el nodo Edge. Al implementarla, para que el SLA sea verificable, el agente debe:

1. tomar `timestamp_captura` al recibir la lectura (LoRa o `FakeLoraSource`);
2. evaluarla contra los umbrales del `UmbralStore`: validación, evaluación y clasificación, lo
   que RF-55 incluye en los 500 ms;
3. tomar `timestamp_procesamiento` al terminar la clasificación;
4. publicar el evento en el topic `evento`, que el broker ya reenvía a `POST /iot/eventos-edge`.

`FakeLoraSource` sirve como simulador para TC-M03-123 en cuanto exista el paso 2.

### ¿Hay que aclarar el criterio de aceptación?

No. RF-55 es explícito y coincide con lo que pide QA:
- **Restricción 1:** "el procesamiento de cada medición debe ejecutarse en ≤ 500 ms desde la
  captura", e incluye validación, evaluación y clasificación.
- **CA-1:** "cuando el sistema lo procese en el Edge, la detección de desviación debe completarse
  en ≤ 500 ms".

La medición es del nodo y queda separada de la latencia de consolidación del backend (RF-56), como
pide QA. **Exactamente 500 ms cumple.**

## Lo que hace el backend (evidencia por evento)

Cada evento Edge ya trae `timestamp_captura` y `timestamp_procesamiento_edge`, ambos del reloj del
nodo. Su diferencia es la latencia de detección medida en el Edge: no incluye red, broker ni
backend. Desde ahora `RecibirEventoEdgeUseCase`:

- calcula `latencia_edge_ms = timestamp_procesamiento_edge − timestamp_captura`
  (`latencia_edge_ms()` en `telemetria.py`, con el límite `LATENCIA_MAX_MS_RF55 = 500`);
- marca `sla_edge_excedido` cuando supera los 500 ms;
- guarda ambos valores en `eventos_edge_computing.metadatos`, sin migración. Si el Edge envía
  esas claves en `metadata_edge`, prevalece el cálculo del backend;
- los devuelve en la respuesta `201` de `POST /iot/eventos-edge`.

Así, cuando exista el detector, **cada evento real trae su medición** y TC-M03-123 puede
comprobarla contra el límite, en la respuesta o en `metadatos`.

**Limitación:** el backend confía en los timestamps del nodo. Si el reloj del Edge no está
sincronizado (NTP, precondición de RF-53/RF-55), la medición no es fiable. G42
(INC-M03-110) ya rechaza los eventos con el procesamiento anterior a la captura.

**Datos actuales en DEV (solo lectura):** 16 eventos Edge, todos de prueba (de 2024 y de julio de
2026, sin un detector real detrás). 6 superan 500 ms y el máximo es de 60 s. No sirven como
evidencia del SLA.

## Pruebas

`tests/telemetry/test_inc_m03_118_g61_latencia_edge.py`, 14 pruebas, con dobles. **No miden al
Edge:**

- **Límite y cálculo:** el límite es 500 ms, y la latencia es procesamiento menos captura (0, 1,
  250, 499, 500, 501 y 60 000 ms).
- **Evidencia por evento:** se guarda y se devuelve para 120, 500, 501 y 1500 ms; exactamente
  500 ms no excede.
- **`metadata_edge`:** se conserva la del Edge, y prevalece el cálculo del backend.
- **Respuesta:** `EventoEdgeResponse` expone los dos campos.

CURL: nota en `curls_m03_cu02_procesar_enviar_inferencia.md`.
