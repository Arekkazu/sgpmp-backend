# DISEÑO Y PRECONDICIONES — TC-M03-G167 (RF-62 / RF-57 / RF-63)

**Versión del diseño:** V3 — Suite autosuficiente (autosiembra en sandbox).
**Cambio mayor respecto a V1/V2:** reemplaza la estrategia que asumía INSERT SQL
para calibración e inyección de sensores preexistentes. Ver §3.

---

## 1. Identificación del Caso

* **Caso de Prueba:** TC-M03-G167 — Detección de drift: fronteras de porcentaje.
* **Subcasos cubiertos:**
  * **TC-M03-313** — drift < 10 %
    * 5.00 %: μ=21.000, offset=−1.000 → esperado 20.000, magnitud 5.00 %. Inactivo (índice 100, `APTO`, NIC41=true)
    * 7.00 %: μ=21.400, offset=−1.400 → esperado 20.000, magnitud 7.00 %. Activo (−10, índice 90, `APTO`, NIC41=true)
    * 9.99 %: μ=21.998, offset=−1.998 → esperado 20.000, magnitud 9.99 %. Activo (−10, índice 90, `APTO`, NIC41=true)
  * **TC-M03-314** — drift 10 %–20 %
    * 10.00 %: μ=22.000, offset=−2.000 → esperado 20.000, magnitud 10.00 %. Activo (−25, índice 75, `APTO_CON_RESERVA`, NIC41=false)
    * 15.00 %: μ=23.000, offset=−3.000 → esperado 20.000, magnitud 15.00 %. Activo (−25, índice 75, `APTO_CON_RESERVA`, NIC41=false)
  * **TC-M03-315** — drift > 20 %
    * 20.01 %: μ=24.002, offset=−4.002 → esperado 20.000, magnitud 20.01 %. Activo (−40, índice 60, `APTO_CON_RESERVA`, NIC41=false, **alerta técnica RF-57 exigida**)
    * 25.00 %: μ=25.000, offset=−5.000 → esperado 20.000, magnitud 25.00 %. Activo (−40, índice 60, `APTO_CON_RESERVA`, NIC41=false, **alerta técnica RF-57 exigida**, bitácora RF-63)

---

## 2. Parámetros del Motor y Fórmulas

* **Fórmula de drift** (`evaluar_calidad_telemetria_use_case.py:178-185`):
  ```
  val_cal_esperado = mean(serie) * ganancia + offset
  media_n          = mean(serie)
  magnitud         = |media_n - val_cal_esperado| / |val_cal_esperado| * 100
  ```
  Activación: `magnitud > 5.0` **y** `misma_direccion >= P` (P=3 por defecto en `parametros_calidad_stub_adapter.py`).
* **Ventana N=20:** `telemetria_repository.py:124` filtra `timestamp_captura < ts`. La lectura #21 (la evaluada) **no entra en μ ni en la ventana**.
* **Parámetros por defecto (stub, no configurables en TEST):**
  - `N = 20`, `P = 3`, `M = 5`, `k = 3.0`
  - `umbral_drift = 5.0` (activa el flag; estricto `>`)
  - `umbral_drift_significativo = 10.0` (usado en el índice; el índice real lo reaplica en `telemetria_calidad.py:49-57`)
* **Fronteras y penalizaciones:**
  - ≤ 5 %: inactivo (índice 100, `APTO`, NIC41=true)
  - > 5 % y < 10 %: −10 (índice 90, `APTO`, NIC41=true)
  - 10 % ≤ drift ≤ 20 %: −25 (índice 75, `APTO_CON_RESERVA`, NIC41=false)
  - > 20 %: −40 (índice 60, `APTO_CON_RESERVA`, NIC41=false)

---

## 3. Estrategia V3 — autosiembra en sandbox

### 3.1 Supuestos que la V1/V2 tenía y que resultaron falsos

Tras 5 fases de diagnóstico contra TEST se confirmó:

| Supuesto V1/V2 | Estado real en TEST | Fuente |
|---|---|---|
| `modulo9.sensores` tenía datos utilizables | **Vacía** (0 filas) | Fase 2 B.4 + Fase 3 A |
| `modulo9.calibraciones` tenía offsets sembrados | **Vacía** (0 filas) | Fase 2 B.3 |
| Se podía inyectar calibración vía `INSERT` en `/test-control/query` | **Bloqueado**: HTTP 403 "Solo se permiten consultas SELECT en el sandbox" | Fase 3 B.1 |
| El DTO de ingesta usaba `access_key` como credencial | **Renombrado a `serial`** en commit `1d503b5` (17-oct-2026). `access_key` ya no existe | Fase 5 Q5 |
| `POST /iot/telemetria` no requería Bearer del broker | **Sí requiere** `Authorization: Bearer <BROKER_SERVICE_TOKEN>` (validado en `broker_auth.py`) | Fase 3 D.3 + Fase 5 Q5 |
| `POST /iot/telemetria` aceptaba `device_id` como string del catálogo | **Requiere `int`** en el DTO Pydantic. Un `parseInt("{{...}}")` produce `NaN` | Fase 3 D.1 + Fase 5 Q5 |
| La colección podía apuntar a `back-sigab-test` | **Correcto es** `https://www.api.inmero.co/api-sgpmp-test` | Guía §1 |

### 3.2 Estrategia adoptada

* **Autosiembra total dentro del `run_id`.** La suite crea: finca → área → dispositivo → sensor → asociación. Al hacer `DELETE /test-control/runs/{run_id}` al final, todo se revierte (asumiendo que `/configuracion/*` está cubierto por el middleware de sandbox — **ver §7 Riesgos**).
* **Calibración vía endpoint público:** `POST /configuracion/sensores/{id}/calibrar` con `{ganancia, offset, valor_referencia, fecha_calibracion, ...}`. Existe, está en OpenAPI, requiere permiso `sensores:Crear` (el admin lo tiene).
* **Ingesta vía `POST /iot/telemetria/batch`** (20 lecturas por escenario, `origen: BUFFER_LOCAL`) y `POST /iot/telemetria` (lectura 21). Ambos con `Authorization: Bearer <BROKER_SERVICE_TOKEN>`.
* **Nombres únicos por `run_id`** para evitar colisiones en re-ejecuciones (`G167-FINCA-<run_id>`, `G167-DEV-<run_id>`, etc.).

---

## 4. Estructura de la suite (43 requests, ~66 s)

```
00-Preflight-Autosiembra (8 requests):
  00.01  POST /sesiones/                                     → token_admin
  00.02  GET  /configuracion/tipos-dispositivo-iot           → id_tipo_dispositivo (SENSOR)
  00.03  GET  /configuracion/tipos-area?solo_activos=true    → tipo_area_nombre ("Galpón")
  00.04  POST /configuracion/fincas                          → id_finca
  00.05  POST /configuracion/infraestructuras                → id_infraestructura
  00.06  POST /configuracion/dispositivos-iot                → device_id, device_serial
  00.07  POST /configuracion/dispositivos-iot/{id}/sensores  → sensor_id
  00.08  POST /configuracion/sensores/{id}/asociar           → asociación vigente

Escenarios 1A..3B (7 carpetas × 4–7 requests):
  {n}.01  POST /configuracion/sensores/{id}/calibrar        (7)
  {n}.02  POST /iot/telemetria/batch                        (7)
  {n}.03  POST /iot/telemetria                              (7)
  {n}.04  POST /iot/calidad/{id}/evaluar                    (7)
  3A.05–3B.07  SELECT /test-control/query (RF-57, RF-63, D7) (6)

99-Teardown (1 request):
  99.01  DELETE /test-control/runs/{{run_id}}
```

Total: 8 + 7×4 + 6 + 1 = **43 requests**. Duración estimada ≈ 66 s (por debajo del timeout de 180 s del sandbox).

---

## 5. Bugs corregidos respecto a V2

| # | Bug V2 | Fix V3 |
|---|---|---|
| B1 | `baseUrl` default `https://api.inmero.co/back-sigab-test` | `https://www.api.inmero.co/api-sgpmp-test` |
| B2 | `device_id: parseInt("{{device_id}}", 10)` → `NaN` | Se envía como string `"{{device_id}}"` (Pydantic coacciona a int) |
| B3 | `access_key: "{{device_serial}}"` (campo inexistente) | `serial: "{{device_serial}}"` (campo del DTO post-commit `1d503b5`) |
| B4 | Ingesta sin `Authorization: Bearer` | `Authorization: Bearer {{broker_token}}` en `/iot/telemetria` y `/iot/telemetria/batch` |
| B5 | `INSERT INTO modulo9.calibraciones` vía `/test-control/query` | `POST /configuracion/sensores/{id}/calibrar` |
| B6 | `id_usuario: 1` hardcoded en INSERT | Eliminado (el endpoint resuelve desde el token) |
| B7 | `01-Descubrimiento-Sensor` asumía sensores existentes | Reemplazado por autosiembra (00.04–00.08) |
| B8 | `entidad_afectada_id = '{{id_tel_3a}}'` como string en SELECT | Se mantiene como string (columna es varchar) — verificado en Fase 2 B.10 |

---

## 6. Defectos conocidos que la suite documenta (sin `xfail`)

* **`INC-M03-RF57-NOT-EMITTED`** — `EvaluarCalidadTelemetriaUseCase` (líneas 223–225)
  no invoca el caso de uso ni el repositorio de alertas RF-57. Los escenarios 3A y 3B
  (drift > 20 %) exigen la alerta técnica en `modulo3.alertas`. **Sin `xfail`: la
  assertion falla honestamente.**
* **D7 (una sola `VIGENTE` por lectura)** — verificado sin `xfail`. El script evalúa
  cada lectura una sola vez, así que D7 se cumple.

---

## 7. Riesgos identificados

| # | Riesgo | Mitigación |
|---|---|---|
| R1 | **¿El middleware de sandbox intercepta `/configuracion/*`?** Si no, la autosiembra contamina TEST permanentemente (finca/área/dispositivo/sensor huérfanos) | Verificar con `DELETE /test-control/runs/{run_id}` tras una corrida de prueba y confirmar que la finca ya no existe. Si no se revierte → escalar a Desarrollo |
| R2 | `grupo_manejo` está `NULL` en las 10 especies activas (Fase 5 Q1). `POST /configuracion/infraestructuras` puede exigirlo | Si 422 por `grupo_manejo`, ajustar `especie_id` a una que tenga grupo asignado, o pedir DBA que complete el campo. Fallback: usar `MODELO_ACUICULTURA` + especie acuícola (Tilapia, id=1) |
| R3 | `categoria` de sensor usada en el script ("TEMPERATURA") puede no coincidir con el enum real | Verificar el enum real del backend. Ajustar `categoria: "TEMPERATURA"` al valor válido |
| R4 | Si `BROKER_SERVICE_TOKEN` no está vigente en TEST, toda la ingesta falla con 503 | Preflight de diagnóstico (§12.1 de la guía) |

---

## 8. Veredicto esperado

Con `INC-M03-RF57-NOT-EMITTED` vigente:

* **Assertions passed:** ~41 de 43
* **Assertions fallidas:** 2 (`3A.05`, `3B.05` — alerta RF-57 no emitida)
* **Veredicto:** **RECHAZADO** por `INC-M03-RF57-NOT-EMITTED`.

Coherente con §17.9 de `GUIA_PRUEBAS_Y_ESTRUCTURA.md`: *"xfail NO se usa para aprobar con defectos"*.

---

## 9. Evidencias esperadas

* `resultados/resultado_TC-M03-G167.html` — Newman + htmlextra (escaneado por dashboard)
* `evidencias/console_run.log` — salida CLI de Newman
* (Opcional) `evidencias/run-YYYYMMDD/` — snapshot completo del run

---

## 10. Referencias cruzadas

* **Diagnóstico Fase 1–5:** documento independiente, resumen en §3.1
* **Bug GitHub:** `INC-M03-RF57-NOT-EMITTED` (severidad Media, Desarrollo, pendiente)
* **Commit que renombró `access_key` → `serial`:** `1d503b5` (17-oct-2026)
* **Commit que separó `POST /configuracion/sensores/{id}/calibrar`:** ver `sensor_router.py:185`

---

## 11. VEREDICTO FINAL — 2026-10-23

**RECHAZADO POR BLOQUEO EXTERNO** — `INC-M03-G167-SENSOR-500`.

Ver `resultados/resultado_TC-M03-G167.md` para detalle.

## 12. Seguimiento

Pendiente de fix backend:
- `SensorModel.es_activo`: agregar `default=True` (o `server_default=text("true")`)
- `Sensor.crear()`: aceptar `es_activo: bool = True`

Después del fix, la suite está lista para re-correr. Solo falta que el DBA
complete `modulo9.calibraciones` (una fila por escenario) o que se confirme
que `POST /configuracion/sensores/{id}/calibrar` ya lo cubre.
