# DISEÑO Y PRECONDICIONES — TC-M03-G168 (RF-62 / RF-57 / RF-63)

**Versión del diseño:** V1 — Suite autosuficiente de Flags Individuales.
**Módulo:** Módulo 3 — Telemetría y Calidad.
**Requisito Funcional:** RF-62 (Evaluación de calidad), RF-57 (Alertas técnicas), RF-63 (Bitácora de auditoría).

---

## 1. Identificación del Caso de Prueba

* **Caso de Prueba:** TC-M03-G168 — Detección de flags individuales de calidad sin severidad acumulada.
* **Subcasos cubiertos:**
  * **TC-M03-312** — Detección de Outlier Estadístico:
    * `312a`: Lectura con desviación extrema ($25.50$ vs base $\mu=22.00, \sigma\approx 0.513$) $\rightarrow$ Activa `outlier_estadistico` (descuento -20, índice 80, `APTO`, NIC41=true).
    * `312b`: Lectura dentro de rango normal ($23.50$) $\rightarrow$ No activa outlier (índice 100, `APTO`, NIC41=true).
    * `312c`: Lectura en frontera ($23.51$) $\rightarrow$ Con $\sigma$ muestral ($3s \approx 1.539 \rightarrow 23.539$) no supera umbral (índice 100).
  * **TC-M03-316** — Detección de Gap Temporal Anómalo:
    * `316a`: Salto de timestamp de 25 min (esperado 5 min) $\rightarrow$ Evaluación de gap temporal.
    * `316b`: Salto menor (20 min).
    * `316c`: Salto con periodo de inactividad justificado.
  * **TC-M03-317** — Detección de Serie Temporal Insuficiente:
    * `317`: Sensor con 3 lecturas previas + 1 evaluada ($N=4 < 20$) $\rightarrow$ Activa `serie_insuficiente` (índice `null`, clasificación `INDETERMINADA`, NIC41=false, IA=false).
  * **TC-M03-323** — Sensor sin Calibración previa:
    * `323a`: Sensor con calibración registrada y lectura $25.50$ $\rightarrow$ Índice 80, calibración activa.
    * `323b`: Sensor sin calibración previa y lectura $25.50$ $\rightarrow$ Activa `calibracion_no_disponible` (omite drift, mantiene índice 80 por outlier).

---

## 2. Parámetros del Motor de Calidad (Inspección Backend)

A partir de la inspección de `evaluar_calidad_telemetria_use_case.py` y `ParametrosCalidad`:
* **Desviación Estándar ($\sigma$):** **Muestral** (`statistics.stdev`, división entre $N-1$).
* **Frecuencia de Muestreo:** En **minutos**, valor por defecto `5` min (`frecuencia_muestreo_min: int = 5`).
* **$N$ Mínimo para análisis temporal:** Exactamente **20** lecturas (`params.N = 20`). Si `len(serie) < 20`, se activa `serie_insuficiente` y se aborta el cálculo estadístico retornando `INDETERMINADA`.
* **$k$ para outliers:** `3.0` desviaciones estándar.

---

## 3. Oráculos por Escenario

| Subcaso | Escenario | Serie Base ($N=20$) | Lectura Evaluada | Flag Esperado | Índice | Clasificación |
|---|---|---|---|---|---|---|
| TC-312 | `312a` | 20 lecturas (21.5/22.5) | 25.50 | `outlier_estadistico.activo = true` | 80 | `APTO` |
| TC-312 | `312b` | 20 lecturas (21.5/22.5) | 23.50 | Ninguno | 100 | `APTO` |
| TC-312 | `312c` | 20 lecturas (21.5/22.5) | 23.51 | Ninguno ($\sigma$ muestral) | 100 | `APTO` |
| TC-316 | `316a` | 20 lecturas | +25 min | `gap_temporal_anomalo` (ver hallazgo) | 90 / 100 | `APTO` |
| TC-316 | `316b` | 20 lecturas | +20 min | Ninguno | 100 | `APTO` |
| TC-316 | `316c` | 20 lecturas + inactividad | +25 min | Ninguno (inactividad) | 100 | `APTO` |
| TC-317 | `317` | 3 lecturas previas | 22.00 | `serie_insuficiente.activo = true` | `null` | `INDETERMINADA` |
| TC-323 | `323a` | 20 lecturas con calibración | 25.50 | `outlier_estadistico` | 80 | `APTO` |
| TC-323 | `323b` | 20 lecturas sin calibración | 25.50 | `calibracion_no_disponible` | 80 | `APTO` |

---

## 4. Estrategia de Autosiembra y Aislamiento

La suite es 100% autosuficiente y transaccional:
1. `00-Preflight-Autosiembra`:
   - `00.01-Login-Admin`: Login y extracción de `token_admin` y `id_usuario_admin` (desde payload JWT `sub`).
   - `00.02-Descubrir-Tipo-Dispositivo`: Identifica tipo `SENSOR`.
   - `00.03-Descubrir-Tipo-Area`: Identifica tipo área activa `Galpón`.
   - `00.04-Crear-Finca`: Crea finca con nombre aleatorio alfabético (`id_usuario = id_usuario_admin`).
   - `00.05-Crear-Area`: Crea área productiva con `especie_id = 123` (`ACUICULTURA`).
   - `00.06-Crear-Dispositivo`: Registra dispositivo IoT con serial `GDEV...`.
   - `00.07-Crear-Sensor`: Crea sensor en `/configuracion/dispositivos-iot/{id}/sensores`.
   - `00.08-Asociar-Sensor-Area`: Asocia el sensor al área creada.
2. Cada bloque de escenarios opera sobre sensores dedicados o el sensor aprovisionado.
3. `99-Teardown`: Invoca `DELETE /test-control/runs/{{run_id}}` para rollback completo en la base de datos de test.

---

## Hallazgos del ambiente y del requerimiento

### INC bloqueante (a nivel de sensor)
- **INC-M03-G167-SENSOR-500**: `POST /configuracion/dispositivos-iot/{id}/sensores`
  retorna 500 por `es_activo` NOT NULL sin default. Bloquea toda la autosiembra.

### INC nuevos del subcaso (a nivel de motor de calidad)
- **INC-M03-G168-GAP-NOT-IMPLEMENTED**: La detección de `gap_temporal_anomalo`
  en `evaluar_calidad_telemetria_use_case.py` (Fase 5) está **comentada / no activa**.
  Los 3 sub-pasos de TC-316 (gap 25min, gap 20min, gap 25min con inactividad)
  no marcarán el flag aunque la lectura cumpla la condición del CSV. Requiere
  implementación en backend antes de poder validar el caso.

### Discrepancias requerimiento (CSV) vs código (hallazgos de requerimiento)
- **σ poblacional vs muestral (TC-312)**: El CSV asume σ poblacional = 0.50000
  (frontera 23.50 = μ+3σ). El backend usa `statistics.stdev` (muestral) = 0.51299
  (frontera 23.5390). Bajo el código real, **23.51 NO marca** (contradice CSV).
  El oráculo de 312c se ajusta al código: `activo=false, índice 100, APTO`.

- **frecuencia_muestreo (TC-316)**: El CSV asume 10 min (umbral gap = 20 min).
  El código real usa `frecuencia_muestreo_min = 5` (umbral = 10 min). Con 5 min,
  el gap 20 min **debería marcar** por fórmula, pero no lo hace por el INC anterior.

### Bloqueos de infraestructura del subcaso
- **TC-316(c) periodo_inactividad**: No existe endpoint POST para crear
  `modulo3.periodos_inactividad`. Solo lo crea el worker interno. `INSERT` vía
  `/test-control/query` está bloqueado (403). El sub-paso (c) se marca como
  **BLOCKED** en la colección y no ejecutable en V1/V2.

### Parámetros del motor confirmados (A.5)
- σ: **muestral** (`statistics.stdev`, ÷ N-1)
- `frecuencia_muestreo_min`: **5 minutos**
- `_N_MINIMO_SERIE_ANALISIS`: **20** (coincide con CSV)
- `periodo_inactividad`: **no creable vía API**

---

## 6. Veredicto Inicial Esperado

* **Veredicto V1:** **RECHAZADO POR BLOQUEO EXTERNO** — debido a `INC-M03-G167-SENSOR-500`.
* Suite estructurada y lista para ejecución V2 una vez corregido el backend.
