# TC-M03-076 — resultado offline 2026-10-30

No sustituye `TC-M03-076_resultado.md` (25 de octubre de 2026, SKIPPED del pytest backend).  
Los tres PASS de G43 son **solo** pruebas offline del firmware. Este caso **no** es integración MQTT.

## Requisito asociado

RF-55.1 (clasificación por umbrales en Edge). Grupo TC-M03-G43. CU-02.

## Identificador del caso

**TC-M03-076**

Pruebas: `test_tc_m03_g43_evaluar_simple[TC-M03-076-21.0-NORMAL]` y `test_tc_m03_g43_historial_y_mqtt_mock[TC-M03-076-21.0-NORMAL]` en el firmware (`qa/rf55-validation-e618a75`, HEAD `e618a75`), archivo `raspberry/tests/test_tc_m03_g43.py`.

## Objetivo

Comprobar que un valor **inequívocamente dentro de la banda `normal`** se clasifica como NORMAL en el Edge, según la implementación real: **sin** EventoEdge MQTT y **con** registro local.

## Datos de prueba (fixture 90043, no producción)

| Campo | Valor |
|---|---|
| Variable | `temperatura_ambiente` |
| `valor_min` / `valor_max` | 18 °C / 32 °C |
| Bandas | 18–24 / 24–28 / 28–32 °C |
| Valor aplicado | **21.0 °C** (interior de `normal`) |

No se usó 25 °C de #647.

## Resultado esperado

- `evaluar_simple` **devuelve `None`** para NORMAL (no construye evento).
- Historial SQLite temporal: `NORMAL`, ruta `LOCAL`, estado `LOCAL`.
- Mock MQTT: **ningún** mensaje en `sgpmp/<serial>/evento`.
- La ausencia de MQTT **no** se interpreta como fallo del clasificador.

## Resultado obtenido

Coincide con lo esperado. Suite: 2 passed, 4 deselected.

## Evidencia disponible

`evidencias/offline-2026-10-30/pytest.{txt,html,xml}`  
Evidencias del 25 de octubre (`evidencias/pytest.*`, SKIPPED backend) **intactas**.

## Estado de ejecución

**PASS offline**

Pytest backend G43: **SKIPPED** (no hay motor en `src/`).

## Limitaciones

- Sin Mosquitto, sin Raspberry, sin backend.
- Integración MQTT y recepción de eventos por el backend: **pendientes**.
- El CA histórico “evento NORMAL” **no** se cumple como publicación MQTT; el PASS cubre historial local + `evaluar_simple is None`.
