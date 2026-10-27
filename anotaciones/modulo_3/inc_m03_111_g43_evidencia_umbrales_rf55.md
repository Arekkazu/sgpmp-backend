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

1. **Equipo Edge/AIoT:** habilitar el `edge_agent`, o un simulador representativo, que clasifique
   por umbrales y envíe a `POST /iot/eventos-edge` el evento con `valor_evaluado`,
   `umbral_min_aplicado` y `umbral_max_aplicado`.
2. **QA:** definir los valores concretos. Una propuesta para la matriz, con temperatura
   ambiental, `umbral_min = 18`, `umbral_max = 30`:
   - TC-M03-076: medición de 25.
   - TC-M03-077: medición de 35.
   - TC-M03-078: medición de 10.
3. **Grupo de análisis:** decidir qué pasa cuando la medición es exactamente igual a un límite.
   El RF solo dice "valor dentro de rango". *Pendiente: se completa con el documento de
   requerimientos que comparte el equipo.*
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
