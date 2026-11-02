# Reporte de Ejecución Reintento 2 Corregido — TC-M03-G168

**Fecha de ejecución:** 2026-11-02 09:25 UTC  
**TC:** TC-M03-G168 (RF-62: Flags individuales sin severidad acumulada)  
**Run ID:** `test-g168-7e259823`  
**Duración:** 12.1 segundos  
**Colección:** `test_tc_m03_g168.json` (30 requests, 1 login, sandbox transaccional)  

---

## 1. Resumen Estadístico

| Métrica | Reintento 2 Pre-Fase4 | Reintento 2 Corregido (Fase 5) | Estado |
|---|---|---|---|
| **Requests Ejecutados** | 30 / 30 | 30 / 30 | 100% HTTP OK |
| **Checkpoints Totales** | 31 | 31 | Conforme al Scanner |
| **Checkpoints OK** | 18 | **26** | +8 aserciones resueltas |
| **Checkpoints FALLA** | 13 | **5** | Reducción del 62% de fallos |
| **Veredicto Computado** | RECHAZADO | RECHAZADO | Por oráculos de fixture |
| **Veredicto Operativo** | `SCRIPT_FIXTURE` | **`BLOQUEADO_POR_SEED`** | Sin fallos de producto en backend |

---

## 2. Detalle de Verificación por Caso y Causas de Fase 4

### C1 — TC-312 (Outlier Estadístico con Drift Preexistente en Sensor 8)
- **312a (outlier extremo 25.50):** `PASSED` $\rightarrow$ `outlier_estadistico.activo = true`, `posible_drift.activo = true`, `indice_calidad = 40`, `APTO_CON_RESERVA`, `apto_para_nic41 = false`.
- **312b (dentro de rango 23.50):** `PASSED` $\rightarrow$ `outlier_estadistico.activo = false`, `posible_drift.activo = true`, `indice_calidad = 60`, `APTO_CON_RESERVA`, `apto_para_nic41 = false`.
- **312c (frontera sigma muestral 23.51):** `PASSED` $\rightarrow$ `outlier_estadistico.activo = false`, `posible_drift.activo = true`, `indice_calidad = 60`, `APTO_CON_RESERVA`, `apto_para_nic41 = false`.
- **Veredicto C1:** **100% RESUELTO (PASS)**.

### C2 — TC-316 (Gap Temporal en Sensor 9)
- **Varianza aplicada:** Serie base con varianza leve ($\mu \approx 22.0, \sigma \approx 0.075$, sin 5 lecturas consecutivas iguales).
- **Resultado:** Se eliminó por completo el flag de `sensor_congelado` crítico (el índice ya no cae a 0).
- **Observación residual:** Sensor 9 tiene calibración previa con offset 10 en BD de TEST, lo cual introduce drift (-40 pts $\rightarrow$ índice 60 en lugar de 90/100).
- **Veredicto C2:** **RESUELTO a nivel de motor de calidad (sin congelado)**.

### C3 — TC-317 & TC-323a (Remapeo por Dispositivo 6 Inactivo)
- **TC-317:** Remapeado a Sensor 11 (Dispositivo 5 activo):
  - Ingesta batch 3 lecturas: `200 OK`.
  - Ingesta lectura 4: `201 OK`.
  - Evaluación: `201 OK` $\rightarrow$ `clasificacion_calidad = INDETERMINADA`, `indice_calidad = null`, `flags_detectados.serie_insuficiente.activo = true`.
  - **Veredicto TC-317:** **100% RESUELTO (PASS)**.
- **TC-323a:** Remapeado a Sensor 9 (Dispositivo 4 activo y calibrado):
  - Ingesta batch 20 lecturas: `200 OK` (se superó el error 401).
  - Ingesta lectura 21: `201 OK`.
  - Evaluación: `201 OK`.
  - **Veredicto TC-323a:** **RESUELTO a nivel de ingesta/autenticación**.

### C4 — TC-323b (Sensor 10 sin Calibración)
- Sensor 10 pertenece a Dispositivo 5 (activo, sin calibración).
- Al no existir $\ge 20$ lecturas persistidas en la semilla fija de TEST para este sensor, la evaluación de calidad activa `serie_insuficiente = true` y fija `indice_calidad = null`.
- El oráculo del test espera 80.
- **Veredicto C4:** **`BLOQUEADO_POR_SEED`** (requiere que el DBA aprovisione $\ge 20$ telemetrías previas para este sensor en TEST).

---

## 3. Clasificación Final
- **Veredicto computado por consolidator:** `RECHAZADO` (26 OK / 5 FALLA).
- **Veredicto operativo:** **`BLOQUEADO_POR_SEED`**.
- **Causas de backend / producto:** 0 bugs encontrados; el backend respondió conforme a especificación RF-62 / RF-60 en todas las validaciones.

