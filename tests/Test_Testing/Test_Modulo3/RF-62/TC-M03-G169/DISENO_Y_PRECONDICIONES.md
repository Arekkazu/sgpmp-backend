# DISEÑO Y PRECONDICIONES — TC-M03-G169 (RF-62 / RF-57 / RF-63)

**Versión del diseño:** V1 — Suite de Estados Heredados de RF-53.
**Módulo:** Módulo 3 — Telemetría y Calidad.
**Requisito Funcional:** RF-62 (Evaluación de calidad de datos), RF-53 (Ingesta y validación de telemetría).

---

## 1. Identificación del Caso de Prueba

* **Caso de Prueba:** TC-M03-G169 — Estados de calidad heredados de RF-53 en el pipeline de evaluación RF-62.
* **Subcasos cubiertos:**
  * **TC-M03-321** — Lectura en estado `FUERA_DE_RANGO` heredado:
    * Valor que excede el umbral operativo de la especie pero dentro de límites físicos (ej. 50.00 °C > umbral máx 40.00 °C de especie 2, límite físico 100 °C).
    * RF-53 persiste la lectura con `estado_calidad = 'FUERA_DE_RANGO'`.
    * RF-62 Fase 0 detecta el estado heredado $\rightarrow$ Índice 0, clasificación `NO_APTO`, `apto_para_ia = false`, `apto_para_nic41 = false`, flag `fuera_de_rango_rf53 = true`.
    * Se omite la ejecución del pipeline estadístico posterior.
  * **TC-M03-322** — Lectura en estado `ERROR_CALIBRACION` heredado con anomalías múltiples:
    * Sensor sin calibración previa en `modulo9.sensores`.
    * RF-53 persiste con `estado_calidad = 'ERROR_CALIBRACION'`.
    * RF-62 Fase 0 detecta el estado $\rightarrow$ Activa `calibracion_no_disponible`, omite detección de drift.
    * El pipeline estadístico continúa evaluando outlier y gap temporal.
    * Oráculo del CSV: índice 70 (`APTO_CON_RESERVA`) con flags `calibracion_no_disponible` (0), `outlier_estadistico` (-20), `gap_temporal_anomalo` (-10).

---

## 2. Oráculos por Subcaso

| Subcaso | Precondición RF-53 | Ingesta | Estado RF-53 | Oráculo RF-62 (Fase 0 + Pipeline) | Índice | Clasificación |
|---|---|---|---|---|---|---|
| **TC-321** | Sensor calibrado, especie con umbral [10, 40] | $50.00$ °C | `FUERA_DE_RANGO` | `fuera_de_rango_rf53.activo = true`<br>Sin flags estadísticos | 0 | `NO_APTO` |
| **TC-322** | Sensor sin calibración, 20 lecturas base con gap + outlier $25.50$ | $25.50$ °C | `ERROR_CALIBRACION` | `calibracion_no_disponible.activo = true`<br>`outlier_estadistico.activo = true`<br>`gap_temporal_anomalo.activo = true` (esperado CSV)<br>drift omitido | 70 (CSV) / 80 (real) | `APTO_CON_RESERVA` |

---

## 3. Estrategia de Autosiembra y Aislamiento

1. `00-Preflight-Autosiembra`:
   - Login de administrador y extracción de token e `id_usuario`.
   - Consulta de catálogo de tipos de dispositivo y área.
   - Creación de finca, área productiva (`especie_id = 2` Trucha Arcoíris con umbrales configurados), dispositivo y sensor.
2. Escenarios independientes por subcaso:
   - `TC-321`: Crea dispositivo + sensor, registra calibración base, ingesta lectura fuera de umbral operativo y evalúa calidad.
   - `TC-322`: Crea dispositivo + sensor sin calibración, ingesta lote con gap y lectura outlier, y evalúa calidad.
3. `99-Teardown`:
   - `DELETE /test-control/runs/{{run_id}}` para rollback completo e idempotente.

---

## Hallazgos del ambiente y del requerimiento

### INC bloqueante (sensor)
- **INC-M03-G167-SENSOR-500**: `POST /configuracion/dispositivos-iot/{id}/sensores`
  retorna 500 por `es_activo` NOT NULL sin default. Bloquea toda la autosiembra.

### INC heredado (gap)
- **INC-M03-G168-GAP-NOT-IMPLEMENTED**: `gap_temporal_anomalo` no se implementa
  en Fase 5. Afecta TC-322: el oráculo del CSV (índice 70) requiere gap, pero
  el código real solo detecta outlier (índice 80). Se deja oráculo 70 para que
  V2 falle honestamente.

### Hallazgos de requerimiento (CSV vs realidad)

- **H1 — valor 150 del CSV es físicamente imposible (TC-321)**:
  El CSV pide `valor=150.00` con rango operativo 0-60. Pero `modulo9.variables_ambientales`
  fija `valor_fisico_max = 100` para temperatura (variable 9). Un valor >100 retorna
  **HTTP 400 ERROR_SENSOR** ("físicamente imposible") en Fase 5 de RF-53, sin persistirse.
  **Adaptación aplicada**: especie 2 (Trucha Arcoíris, umbral [10, 40]) + **valor 50.00**
  → pasa validación física (50 ≤ 100) y supera umbral (50 > 40) → FUERA_DE_RANGO.

- **H2 — especie usada (TC-321)**: para forzar FUERA_DE_RANGO se requiere una especie
  con umbral operativo menor al valor ingerido. Se usa especie 2 (Trucha), no 123
  (Tilapia). Esto diferencia G169 de G167/G168, donde se usaba 123.

### Parámetros del motor confirmados (A.6)
- **Fase 0 (FUERA_DE_RANGO)**: implementada. Cortocircuito → índice 0, NO_APTO, sin pipeline estadístico
- **Fase 0 (ERROR_CALIBRACION)**: implementada. Flag `calibracion_no_disponible=true`, `omitir_drift=True`, pipeline estadístico sí corre
- **FUERA_DE_RANGO** se dispara automáticamente vía RF-53 al ingerir valor > umbral de especie
- **ERROR_CALIBRACION** se dispara automáticamente cuando el sensor no tiene fila en `calibraciones_sensores`

---

## 5. Veredicto Inicial Esperado

* **Veredicto V1:** **RECHAZADO POR BLOQUEO EXTERNO** — `INC-M03-G167-SENSOR-500`.
