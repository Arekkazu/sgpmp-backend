# Informe de ejecución offline — TC-M03-G43 / RF-55.1

Fecha de consolidación documental: 2026-10-30.  
Alcance: pruebas **offline del firmware** en `.worktrees/sgpmp-rf55-validation` (`qa/rf55-validation-e618a75`, HEAD `e618a75`).  
Esta ejecución **no** es integración MQTT, **no** usa Mosquitto ni Raspberry, **no** desbloquea el pytest de `sgpmp-backend`.

Los informes históricos `Resultados/TC-M03-07{6,7,8}/TC-M03-07{6,7,8}_resultado.md` (25 de octubre de 2026, SKIPPED) **permanecen vigentes** para el runner del backend. Este documento no los sustituye.

---

## Trazabilidad del grupo

| Campo | Valor |
|---|---|
| Grupo | TC-M03-G43 |
| Requisito | RF-55.1 |
| Caso de uso | CU-02 |
| Firmware | `raspberry/tests/test_tc_m03_g43.py` (parametrize, clasificador `evaluar_simple` real) |
| Backend | `test_tc_m03_g43.py` — tres pruebas **SKIPPED** (`skip_sin_motor_edge`; no hay motor en `src/`) |
| Suite firmware | **6 passed** |
| Por caso | 2 passed, 4 deselected (`-k TC-M03-07x`) |

## Fixture de prueba (no es umbral de producción ni umbral 65 de laboratorio)

| Campo | Valor |
|---|---|
| `id_umbral_ambiental` | 90043 |
| Variable | `temperatura_ambiente` |
| `valor_min` | 18 °C |
| `valor_max` | 32 °C |
| Bandas RF-17 | normal 18–24 / precaucion 24–28 / critico 28–32 °C |

No se usó 25 °C de INC-M03-111/#647 como NORMAL: en esta fixture 25 °C caería en precaución.

## Resumen de casos

| Caso | Objetivo | Datos | Esperado (firmware real) | Obtenido | Estado |
|---|---|---|---|---|---|
| TC-M03-076 | Valor en banda `normal` | 21.0 °C | `evaluar_simple` → `None`; historial `NORMAL`/`LOCAL`; sin `evento` MQTT | Coincide | **PASS offline** |
| TC-M03-077 | Valor > `valor_max` | 35.0 °C | `DESVIACION_SIMPLE` / `CRITICO` / `fuera_de_rango`; mock `.../evento` | Coincide | **PASS offline** |
| TC-M03-078 | Valor < `valor_min` | 10.0 °C | Igual que 077 | Coincide | **PASS offline** |

Los tres PASS son **exclusivamente** pruebas offline del firmware.

## Limitaciones comunes

- Publicación 077/078: **FakeLink** (mock). No hay broker real.
- 076 **no publica** evento MQTT; eso es el comportamiento del clasificador, no un fallo.
- Recepción en backend (`POST /iot/eventos-edge`) **no** se ejercitó.
- Pytest G43 del backend: **SKIPPED**.
- Integración MQTT e ingesta de eventos: **pendientes**.

## Informes individuales

- `Resultados/TC-M03-076/RESULTADO_OFFLINE_2026-10-30.md`
- `Resultados/TC-M03-077/RESULTADO_OFFLINE_2026-10-30.md`
- `Resultados/TC-M03-078/RESULTADO_OFFLINE_2026-10-30.md`

Evidencias (no sustituyen las de 2026-10-25): `evidencias/offline-2026-10-30/pytest.{txt,html,xml}` en cada carpeta.

## Comando (referencia; no se reejecuta en esta consolidación)

```
cd .worktrees/sgpmp-rf55-validation/raspberry
python -m pytest -v -rs --tb=short tests/test_tc_m03_g43.py
```

## Pendientes de validación integral

1. Pytest G43 en `sgpmp-backend` (motor ausente en `src/`).
2. Publicación real en Mosquitto (`sgpmp/<serial>/evento`) para 077/078.
3. Confirmación de que 076 **no** genera evento MQTT en un nodo desplegado (solo historial).
4. Recepción y persistencia del evento en el backend.
5. Alineación del CA documental “evento NORMAL” con el firmware (`evaluar_simple` → `None`).
