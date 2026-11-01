# TC-M03-G55 — RF-56 generación, envío y fragmentación (2026-10-31)

Ejecución local en `sgpmp-backend`. Sin Git. Sin POST a DEV/TEST/MAIN. `IOT_INFERENCIA_M04_URL` y `IOT_INFERENCIA_M04_TOKEN` **UNSET**. `G55_M04_INTEGRATION` no activado.

## Dictamen por caso

| Caso | Resultado | Evidencia | Limitaciones |
|---|---|---|---|
| TC-M03-090 | **APROBADO PARCIALMENTE** | JSON generado (`tc_m03_090_paquete.json`); pytest de consolidación y serialización; campos del contrato vigente `PaqueteInferencia` + `dataclasses.asdict` del adapter G63 | El paquete **no** usa los nombres de ficha (`id_paquete` UUID, `sensor_id`, `valor`); `id_version_modelo` queda `null`; no hay `area_id` ni `VECTOR_COMPORTAMIENTO` en este DTO; no existe esquema JSON publicado por M04 para validar contra IA-1 |
| TC-M03-091 | **BLOQUEADO** | Skip explícito `test_tc_m03_091_envio_real_a_m04`; URL/token de proceso UNSET | No hay receptor M04 TEST confirmado ni JWT; no se fabricó HTTP 200; la ficha `POST /inferencia` **no existe** en `src/prediction` |
| TC-M03-092 | **APROBADO PARCIALMENTE** | `DrenarPaquetesPendientesUseCase` real: 500→`[500]`, 501→`[500,1]`, 1000→`[500,500]`, 1001→`[500,500,1]`; orden de ids 1..N; fallo del primer lote con `max_lotes=1` deja el registro 501 sin intento | La ficha pide partir **501 registros de un paquete**; el código parte **501 paquetes pendientes**. Un evento con 501 variables sigue generando **un** `PaqueteInferencia`. El envío de ambos fragmentos a M04 no se ejecutó (mismo bloqueo que 091) |

## 1. Archivos inspeccionados

- `src/telemetry/application/use_cases/inferencia/consolidar_paquete_inferencia_use_case.py`
- `src/telemetry/application/use_cases/inferencia/drenar_paquetes_pendientes_use_case.py`
- `src/telemetry/infrastructure/adapters/motor_inferencia_http_adapter.py`
- `src/telemetry/infrastructure/adapters/motor_inferencia_stub_adapter.py`
- `src/telemetry/domain/entities/telemetria.py` (`MAX_REGISTROS_POR_ENVIO_INFERENCIA = 500`, `PaqueteInferencia`, huella)
- `src/telemetry/domain/repositories/motor_inferencia_port.py`
- `src/telemetry/infrastructure/schema/paquete_inferencia_schema.py`
- `src/telemetry/infrastructure/routers/evento_edge_router.py` (elige HTTP o stub según env)
- `src/telemetry/infrastructure/workers/reenvio_inferencia_worker.py`
- `src/prediction/infrastructure/routers/monitor_prediccion_router.py` (`GET /prediccion/inferencias`, no recibe paquetes)
- `anotaciones/modulo_3/inc_m03_112_g55_paquetes_inferencia_lotes.md`
- `anotaciones/modulo_3/inc_m03_120_g63_canal_seguro_m04.md`
- `tests/telemetry/test_inc_m03_112_g55_paquetes_inferencia.py`
- `tests/telemetry/test_inc_m03_120_g63_canal_seguro_m04.py`
- `.env.example` (variables `IOT_INFERENCIA_*`)

## 2. Archivos creados o modificados

- **Modificado:** `tests/Test_Testing/Test_Modulo3/RF-56/TC-M03-G55/test_tc_m03_g55.py` (090 JSON, 091 skip/gated, 092 drenado real + 500/1000/1001)
- **Modificado:** `tests/Test_Testing/Test_Modulo3/rf56_dobles.py` (`MotorObservado.enviar_lote`, requerido por `MotorInferenciaPort`)
- **Creado:** evidencias `run-2026-10-31-g55/` (`tc_m03_090_paquete.json`, `tc_m03_092_lotes_*.json`, `pytest-junit.xml`, este informe)

**No se modificó código productivo.** Hallazgos para M03/M04 (no aplicados): UUID vs entero; `version_modelo_objetivo`/`area_id`/vector estructurado ausentes; contrato IA-1 provisional; ficha `POST /inferencia` vs URL completa `IOT_INFERENCIA_M04_URL`.

## 3. Endpoint real de M04 identificado

- Ficha QA: `POST /inferencia`. **No implementado** como router de recepción en este backend.
- Cliente RF-56: `MotorInferenciaHttpAdapter` hace `POST` a **`IOT_INFERENCIA_M04_URL` completa** (no concatena path). TLS ≥ 1.3, `https://` obligatorio.
- Las pruebas G63 usan como ejemplo `{scheme}://{host}:{port}/inferencia/paquetes`. Eso es el path de **prueba local TLS**, no una URL TEST confirmada.
- Monitor M04 en backend: `GET /prediccion/inferencias` (RF-66), no es el receptor de paquetes.
- Este entorno: `IOT_INFERENCIA_M04_URL=UNSET` → stub `MotorInferenciaNoIntegradoError`.

## 4. Esquema JSON utilizado

Cuerpo provisional G63 (documentado como no-IA-1):

```json
{ "paquetes": [ { /* dataclasses.asdict(PaqueteInferencia) */ } ] }
```

Campos del registro (contrato de código, no de la ficha): `id_paquetes_inferencia` (int), `id_sensor`, `id_dispositivo_iot`, `id_evento_edge_computing`, `tipo_variable`, `valor_numerico`, `unidad`, `estado_calidad`, `estado_desviacion`, `severidad`, `origen`, `contexto_ambiental`, `contexto_incompleto`, `metadatos` (`timestamp_captura`, `timestamp_procesamiento_edge`, `clasificacion_rf55`, `huella_contenido`), `id_version_modelo`, `fecha_envio`, `estado_paquete`, `intento_envios`.

RFC-011 / AIOT-SPEC-01 (`area_id`, `VECTOR_COMPORTAMIENTO`, `densidad_actividad`, `dispersion_espacial`, `tasa_movimiento`): **no aparecen** en `PaqueteInferencia` ni en la consolidación.

## 5. Configuración de autenticación

- Header `Authorization: Bearer {IOT_INFERENCIA_M04_TOKEN}` si el token no está vacío.
- Sin token, el POST sale **sin** Bearer (sigue siendo provisional).
- En esta máquina: TOKEN UNSET. No se imprimió ni guardó ningún secreto.

Integración gated: `G55_M04_INTEGRATION=1` + URL identificable como TEST + token. Por defecto no envía.

## 6. Comandos ejecutados

```text
python -m pytest --noconftest tests/Test_Testing/Test_Modulo3/RF-56/TC-M03-G55/test_tc_m03_g55.py tests/telemetry/test_inc_m03_112_g55_paquetes_inferencia.py --tb=short -q --junitxml=.../pytest-junit.xml
```

`--noconftest` porque `tests/conftest.py` importa `fcntl` (no disponible en Windows). Las pruebas G55/G112 no dependen de ese conftest.

## 7. Cantidad de pruebas

| | |
|---|---|
| Aprobadas | **32** |
| Fallidas | **0** |
| Omitidas | **1** (`test_tc_m03_091_envio_real_a_m04`) |

## 8. Resultado real de recepción de M04

**No hay.** No se abrió HTTP hacia M04. Un `MotorObservado(exito=True)` solo demuestra el mapeo del puerto a `ENVIADO`; no es ACK de M04.

## 9. Evidencia de fragmentación

Componente real: `DrenarPaquetesPendientesUseCase` + `MAX_REGISTROS_POR_ENVIO_INFERENCIA=500`.

| Pendientes | Lotes |
|---:|---|
| 500 | `[500]` |
| 501 | `[500, 1]` |
| 1000 | `[500, 500]` |
| 1001 | `[500, 500, 1]` |

Ids 1..N una sola vez, en orden. Primer lote `False` + `max_lotes=1`: 500 reprogramados, id 501 sin intento. Stub: no commit, todo `PENDIENTE`.

## 10. Problemas encontrados

1. **Contrato IA-1 indefinido:** endpoint, ACK e id de recepción de M04 no están fijados; el adapter trata cualquier HTTP 2xx como éxito y **no parsea el cuerpo**.
2. **Nombres de ficha vs código:** UUID/`id_paquete` vs entero `id_paquetes_inferencia`; `valor` vs `valor_numerico`.
3. **RFC-011 / vector estructurado** no implementados en el paquete RF-56 de este repo.
4. **Fragmentación de ficha vs implementación:** lotes de paquetes pendientes, no split de 501 variables.
5. **FA-03:** delta de timestamps >5 s ya no lanza `PAQUETE_INCONSISTENTE`; descarta agrupación (`agrupacion_descartada`).
6. **Fallo de envío síncrono:** `False` del puerto deja `PENDIENTE` (reintento), no `FALLIDO` (G56).
7. Entorno Windows: `fcntl` en conftest global.

## 11. Dictamen QA

- **TC-M03-090:** generación y JSON del contrato **interno** demostrados. Incompleto respecto a ficha RF-56 + RFC-011 y sin validador M04 → **APROBADO PARCIALMENTE** (no NO APROBADO: el código cumple su propio DTO).
- **TC-M03-091:** condiciones TEST/JWT no confirmadas → **BLOQUEADO**. Skip ≠ aprobación.
- **TC-M03-092:** el drenado real fragmenta 501 pendientes en 500+1 con trazabilidad de `id_paquetes_inferencia`. No cubre “501 registros en un JSON” ni el envío HTTP de ambos fragmentos → **APROBADO PARCIALMENTE**.
