# INC-M03-111-G43 — Bloqueo de pruebas de clasificación de umbrales RF-55.1

**RF:** RF-55.1 (procesamiento básico por umbrales en Edge). **Grupo:** TC-M03-G43.
**Casos:** TC-M03-076 (dentro del rango → NORMAL), TC-M03-077 (sobre el máximo →
DESVIACION_SIMPLE), TC-M03-078 (bajo el mínimo → DESVIACION_SIMPLE). **Issue:** #647.

## Diagnóstico

QA tiene razón en que los casos están **bloqueados, no fallidos**: `localizar_motor_edge()`
devuelve `None` porque no hay un motor Edge disponible.

- La clasificación RF-55.1 la hace el **Edge** (RF-55, Fases 3 y 5: "evaluación de umbrales y
  generación de evento simple"). El componente es el `edge_agent` del repo de firmware
  (`SerBy48/EDGE-FIRMWARE-SGPMP`), no el backend.
- `POST /iot/eventos-edge` recibe `clasificacion_rf55` ya calculada. Enviarla a mano no prueba
  el clasificador, como ya señala QA.
- `SemaforoCalculator` (`src/telemetry/domain/entities/monitoreo.py`) calcula el semáforo del
  monitoreo histórico y no tiene relación con RF-55.1.

### Causa confirmada: el `edge_agent` no implementa RF-55

> **Actualización (2026-10-27, al revisar INC-M03-118-G61 / #662).** Se revisó en modo de solo
> lectura el repo de firmware `SerBy48/EDGE-FIRMWARE-SGPMP` (rama `develop`, commit `66a22a2`).
> De las tres causas posibles (detector no implementado, detector sin desplegar o localizador de
> QA mal configurado), **es la primera**.

| Pieza del firmware | Estado |
|---|---|
| Simulador de datos `FakeLoraSource` (`raspberry/edge_agent/sources.py`), con `EDGE_SOURCE=fake` y `EDGE_FAKE_VARIABLES=temperatura_ambiente:C:20:30` | **Existe.** Genera lecturas sintéticas y el agente las publica como telemetría |
| `SENSOR_SIMULADO` en el firmware ESP32 | **Existe.** Temperatura y humedad sintéticas en el nodo |
| Umbrales de RF-17 en el Edge (`UmbralStore`, `umbrales.json`) | **Existe.** Los recibe, los guarda y confirma con `ACK_UMBRAL` |
| **Clasificación RF-55.1** (comparar la lectura con `umbral_min`/`umbral_max` y generar el evento NORMAL / DESVIACION_SIMPLE) | **No existe.** El README del agente dice: *"Evaluar las lecturas contra esos umbrales es de RF-55"*. El agente publica telemetría, heartbeat y estado, pero no eventos Edge |

Por eso `localizar_motor_edge()` no encuentra nada: no hay detector que devuelva un evento
clasificado. El mismo bloqueo afecta al SLA de 500 ms de RF-55 (TC-M03-123, #662).

Cuando el equipo Edge implemente la clasificación, **`FakeLoraSource` sirve como simulador** para
TC-M03-076/077/078: con `EDGE_FAKE_VARIABLES` se fija el rango de las lecturas, y los umbrales
llegan por RF-17 al `UmbralStore`.

## Hueco del backend que sí se corrige aquí

Una de las acciones que pide QA es tener evidencia observable del valor medido y de los umbrales
usados. La tabla `modulo3.eventos_edge_computing` ya tenía las columnas para eso
(`valor_evaluado`, `umbral_min_aplicado`, `umbral_max_aplicado`, todas `numeric NULL`), pero el
backend nunca las llenaba:

| Capa | Antes | Ahora |
|------|-------|-------|
| `RecibirEventoEdgeDTO` | No los recibía | `valor_evaluado`, `umbral_min_aplicado`, `umbral_max_aplicado` opcionales; si el mínimo es mayor que el máximo devuelve 422 |
| `EventoEdgeComputing` / `ResultadoEventoEdge` | No los tenían | Los conservan |
| `SqlAlchemyEventoEdgeRepository` | No los escribía | Los persiste y los vuelve a leer |
| `EventoEdgeResponse` | No los devolvía | Los devuelve |

- **No requiere DDL:** las columnas ya existen.
- **Es compatible con lo anterior:** los tres campos son opcionales, así que un Edge que todavía
  no los envía sigue funcionando y quedan en `NULL`.
- **El backend no recalcula ni valida la clasificación** contra los umbrales, porque esa
  responsabilidad es del Edge. `desviacion_pct` se deja sin llenar mientras no exista una
  fórmula definida en el RF.

## Lo que queda fuera del backend (bloqueo vigente)

1. **Equipo Edge/AIoT:** implementar la clasificación RF-55.1 en el `edge_agent`, que hoy no existe
   (ver "Causa confirmada"). El agente debe evaluar cada lectura contra los umbrales del
   `UmbralStore` y publicar el evento en el topic `evento`, que el broker ya reenvía a
   `POST /iot/eventos-edge`, con `valor_evaluado`, `umbral_min_aplicado` y `umbral_max_aplicado`.
2. **QA:** definir los valores concretos. Una propuesta para la matriz, con temperatura
   ambiental, `umbral_min = 18`, `umbral_max = 30`:
   - TC-M03-076: medición de 25.
   - TC-M03-077: medición de 35.
   - TC-M03-078: medición de 10.
3. **Grupo de análisis:** confirmar qué pasa cuando la medición es exactamente igual a un límite.
   Se revisó la especificación del Módulo 3 y `ESPECIFICACION_REQUERIMIENTOS_COMPLETA.xlsx`
   (carpeta de requerimientos en Drive, versión del 2026-10-26):
   - **RF-55 no lo define.** Solo dice "NORMAL: valor dentro de rango" y "DESVIACIÓN SIMPLE: una
     variable fuera de rango".
   - **RF-58 sí lo define, y para todo el sistema.** En la Fase 3 (Cálculo del Estado del
     Semáforo) establece `VERDE: valor ∈ [umbral_min, umbral_max]` (intervalo cerrado) y agrega:
     "Esta lógica debe aplicarse de forma determinística y consistente en todo el sistema"
     (`Especificacion-Requerimientos-Modulo3.md`, líneas 5197 y 5207).
   - **RF-16 aplica el mismo criterio** a los valores de las métricas dinámicas: "dentro de ese
     rango, inclusive".

   **Propuesta:** el intervalo es inclusivo. `umbral_min ≤ valor ≤ umbral_max` → NORMAL, y solo
   `valor < umbral_min` o `valor > umbral_max` → DESVIACION_SIMPLE. Así, una medición igual a 18 o
   a 30, con los umbrales propuestos, es NORMAL. Como RF-55 no lo dice de forma explícita, el
   grupo de análisis debe ratificarlo, y el equipo Edge lo debe implementar en el `edge_agent`.
   Se sugieren dos casos de borde para la matriz de QA: medición igual a 18 y medición igual
   a 30, ambas NORMAL.
4. **QA:** cuando el motor esté disponible, ejecutar los tres casos y guardar como evidencia la
   respuesta del endpoint o la fila de `modulo3.eventos_edge_computing`, con el valor y los
   umbrales.

## Pruebas

`tests/telemetry/test_inc_m03_111_g43_umbrales_evento_edge.py`:

- Los tres escenarios de TC-M03-076/077/078 conservan la clasificación, el valor y los umbrales
  en la entidad y en el resultado.
- Un evento sin umbrales se sigue aceptando.
- Un mínimo mayor que el máximo devuelve 422; un mínimo igual al máximo es válido.
- El repositorio persiste las tres columnas.

CURL: `curls_m03_cu02_procesar_enviar_inferencia.md`, sección "RF-55.1 — Evento con valor y
umbrales aplicados".
