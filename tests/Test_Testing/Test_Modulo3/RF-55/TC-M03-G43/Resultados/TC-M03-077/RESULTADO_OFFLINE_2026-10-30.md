# TC-M03-077 — resultado offline 2026-10-30

No sustituye `TC-M03-077_resultado.md` (25 de octubre de 2026, SKIPPED del pytest backend).  
Los tres PASS de G43 son **solo** pruebas offline del firmware.

## Requisito asociado

RF-55.1. Grupo TC-M03-G43. CU-02.

## Identificador del caso

**TC-M03-077**

Pruebas: `test_tc_m03_g43_evaluar_simple[TC-M03-077-35.0-DESVIACION_SIMPLE]` y `test_tc_m03_g43_historial_y_mqtt_mock[TC-M03-077-35.0-DESVIACION_SIMPLE]` en el firmware (`e618a75`), `raspberry/tests/test_tc_m03_g43.py`.

## Objetivo

Comprobar que un valor **estrictamente superior a `valor_max`** produce `DESVIACION_SIMPLE` en el clasificador real y que el evento se construye para el tópico `evento`.

## Datos de prueba (fixture 90043, no producción)

| Campo | Valor |
|---|---|
| Variable | `temperatura_ambiente` |
| `valor_max` | 32 °C |
| Valor aplicado | **35.0 °C** |

Bandas de la fixture: 18–24 / 24–28 / 28–32 °C.

## Resultado esperado

- Clasificación `DESVIACION_SIMPLE`
- Severidad `CRITICO`
- Motivo `nivel_umbral=fuera_de_rango`
- Payload con `clasificacion_rf55` y valor 35.0
- Publicación **solo en mock** (`FakeLink`), tópico `sgpmp/IOT-TEST-001/evento`
- Historial: `DESVIACION_SIMPLE`, ruta `DIRECTA`

## Resultado obtenido

Coincide con lo esperado. Suite: 2 passed, 4 deselected.

## Evidencia disponible

`evidencias/offline-2026-10-30/pytest.{txt,html,xml}`  
Evidencias del 25 de octubre **intactas**.

## Estado de ejecución

**PASS offline**

Pytest backend G43: **SKIPPED**.

## Limitaciones

- La publicación se verificó **mediante mock**, no con Mosquitto ni Raspberry.
- El backend **no** recibió el evento.
- Integración MQTT e ingesta `POST /iot/eventos-edge`: **pendientes**.
