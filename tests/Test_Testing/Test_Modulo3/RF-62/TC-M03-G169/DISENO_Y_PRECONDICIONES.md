# DISEÑO Y PRECONDICIONES — TC-M03-G169 (RF-62 / RF-63)

## 1. Identificación del Caso
* **Caso de Prueba:** TC-M03-G169 — Comportamiento de RF-62 según estado heredado de RF-53.
* **Subcasos cubiertos:**
  - **TC-M03-321 (FUERA_DE_RANGO):**
    - **Hallazgo Crítico:** En el backend actual, `_evaluar_rango` (`ingerir_telemetria_use_case.py:356-365`) rechaza los valores fuera de rango físico con `ERROR_SENSOR` (HTTP 400), impidiendo su persistencia por flujo normal.
    - **Precondición Transaccional:** Se siembra la telemetría directamente en `modulo3.telemetrias` con `estado_calidad = 'FUERA_DE_RANGO'` y `valor_crudo = 150.00` vía `POST /test-control/query` para validar formalmente el comportamiento de la Fase 0 de RF-62.
    - Al invocar `POST /iot/calidad/{id}/evaluar`, el motor ejecuta la Fase 0 inmediata: `indice_calidad = 0`, `clasificacion_calidad = 'NO_APTO'`, `apto_para_ia = false`, `apto_para_nic41 = false`, `flags.fuera_de_rango_rf53.activo = true`.
    - Ausencia estricta de anomalías calculadas en Fases 1 a 5 (sensor congelado, outlier, drift, gap temporal).
    - Verificación de metadatos mínimos y confirmación de que no se emite alerta técnica en `modulo3.alertas`.
    - Confirmación por snapshot de la inmutabilidad del valor original en `modulo3.telemetrias`.
  - **TC-M03-322 (ERROR_CALIBRACION):**
    - **Aislamiento de Serie Temporal:** En `telemetria_repository.py:127`, el motor recupera la serie de $N=20$ filtrando estrictamente `estado_calidad = 'LECTURA_VALIDA'`. Si las 20 lecturas base no estuvieran calibradas, quedarían en `ERROR_CALIBRACION` y el motor las ignoraría (disparando `serie_insuficiente`).
    - **Estrategia Implementada:** Se siembran las 20 lecturas base con calibración nominal para garantizar que queden como `LECTURA_VALIDA` (confirmado mediante aserción `pm.test` estricta). Inmediatamente antes de ingresar la lectura evaluada ($25.50$), se borra la calibración dentro del sandbox (`DELETE FROM modulo9.calibraciones WHERE id_sensor = {{s2_sensor_id}}`), asegurando que la lectura evaluada sea clasificada por RF-53 como `ERROR_CALIBRACION`.
    - `POST /iot/calidad/{id}/evaluar` arroja: `calibracion_no_disponible.activo = true` (informativo, sin descuento adicional), `outlier_estadistico.activo = true` (-20 puntos) y `posible_drift` omitido.
    - Se registra con prefijo `[DEFECTO CONOCIDO RF-62 Fase 5]` la aserción de gap temporal activo e índice 70 ($100 - 20 - 10$).
    - Clasificación esperada: `APTO_CON_RESERVA`, `apto_para_ia = true`, `apto_para_nic41 = false`.
  - **Invariante D7:**
    - Verificación mediante `SELECT COUNT(*)` en `modulo3.telemetria_calidad` confirmando que cada lectura conserve exactamente una sola fila con `estado_evaluacion = 'VIGENTE'` (con prefijo `[DEFECTO CONOCIDO D7]`).

---

## 2. Precondiciones, Control de Fechas y Aislamiento Transaccional
1. **Control de Fechas:** Todas las fechas empleadas son estrictamente pasadas y anteriores al 19-oct-2026 (`2026-10-15` y `2026-10-16`).
2. **Aislamiento Sandbox:**
   - La suite corre bajo el Sandbox transaccional del backend utilizando `X-Test-Run-Id` y `X-Sandbox-Secret`.
   - Limpieza completa al finalizar mediante `DELETE /test-control/runs/{{run_id}}`.
3. **Duración Estimada:** 19 requests totales con una duración aproximada de **4 a 7 segundos**.
