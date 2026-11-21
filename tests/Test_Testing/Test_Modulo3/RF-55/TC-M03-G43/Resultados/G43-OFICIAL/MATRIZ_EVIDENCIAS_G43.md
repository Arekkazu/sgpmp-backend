# Matriz de evidencias G43 oficial

Base de evidencias: `Resultados/G43-OFICIAL/evidencias/run-2026-11-01-integracion/`  
Offline firmware (no es esta matriz): `evidencias/run-2026-11-01-firmware-offline/`  
G43-PR1: **excluido**.

Leyenda: S = sí, verificable en la ruta citada. N = no hay evidencia.

## TC-M03-076 (21.0 °C, NORMAL)

| # | Criterio | S/N | Ruta / observación |
|---|---|---|---|
| 1 | Clasificación Edge real | S | `TC-M03-076/firmware.json` — NORMAL, severidad null, `evaluar_simple` + FakeLora min=max=21 |
| 2 | MQTT real | S | `TC-M03-076/mqtt.jsonl` y `mqtt.jsonl` — topic `sgpmp/G43-LAB-001/evento` |
| 3 | `id_evento_edge` | S | `edge-evt-813be948-1919-4175-b0b3-2ab0bfc03e3a` |
| 4 | Recepción Gateway | S | `gateway-extract-sin-secretos.txt` — handlers parseado 08:10:21Z |
| 5 | POST `/iot/eventos-edge` | S | mismo extracto httpx |
| 6 | HTTP 201 | S | Gateway 08:10:22Z; backend access log 201 (sin id en la línea) |
| 7 | Persistencia PG | S | `sql-cierre-solo-lectura-2026-11-01-0317.txt` — `sgpmp_g43_test` |
| 8 | Un registro | S | `count(*)=1` |
| 9 | Valor/unidad/clasificación/severidad | S | 21.0 C, NORMAL, severidad NULL (no CRITICO) |
| 10 | Umbral 90043 | S | `TC-M03-076/edge-state/umbrales.json`, MQTT, PG |

**076: 10/10 — APROBADO**

## TC-M03-077 (35.0 °C, DESVIACION_SIMPLE / CRITICO)

| # | Criterio | S/N | Ruta / observación |
|---|---|---|---|
| 1 | Clasificación Edge | S | `TC-M03-077/firmware.json` |
| 2 | MQTT real | S | `TC-M03-077/mqtt.jsonl` |
| 3 | Id | S | `edge-evt-6063f185-ecb2-443a-ad4c-418f190749b2` |
| 4 | Gateway | S | extracto 08:11:06Z |
| 5 | POST | S | httpx |
| 6 | 201 | S | 08:11:06Z |
| 7 | PG | S | SQL cierre |
| 8 | Un registro | S | count=1 |
| 9 | Datos | S | 35.0 C, DESVIACION_SIMPLE, CRITICO |
| 10 | Umbral 90043 | S | firmware + MQTT + PG |

**077: 10/10 — APROBADO**

## TC-M03-078 (10.0 °C, DESVIACION_SIMPLE / CRITICO)

| # | Criterio | S/N | Ruta / observación |
|---|---|---|---|
| 1 | Clasificación Edge | S | `TC-M03-078/firmware.json` |
| 2 | MQTT real | S | `TC-M03-078/mqtt.jsonl` |
| 3 | Id | S | `edge-evt-0fe71210-6dcd-428e-a6be-ab40130f55e7` |
| 4 | Gateway | S | extracto 08:11:34Z |
| 5 | POST | S | httpx |
| 6 | 201 | S | 08:11:34Z |
| 7 | PG | S | SQL cierre |
| 8 | Un registro | S | count=1 |
| 9 | Datos | S | 10.0 C, DESVIACION_SIMPLE, CRITICO |
| 10 | Umbral 90043 | S | firmware + MQTT + PG |

**078: 10/10 — APROBADO**

## Lo que no se usa

- Intentos fallidos de arranque (SECRET_KEY, defusedxml, Proactor): no son evidencia de caso.
- Pytest offline / FakeLink.
- Resultados G43-PR1.
