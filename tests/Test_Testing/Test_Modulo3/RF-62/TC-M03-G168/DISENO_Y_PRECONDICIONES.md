# DISEÑO Y PRECONDICIONES — TC-M03-G168 (RF-62)

## 1. Identificación del Caso
* **Caso de Prueba:** TC-M03-G168 — Flags individuales sin escala de severidad.
* **Subcasos cubiertos:**
  - **TC-M03-312 (Outlier estadístico):**
    - Serie base de $N=20$ lecturas alternadas entre $21.50$ y $22.50$ ($\mu=22.00$, $\sigma_{\text{poblacional}}=0.50$, $s_{\text{muestral}}\approx 0.513$). Intervalo de 10 minutos.
    - Lectura $25.50$: Outlier claro ($>6.8\sigma$), activo=true, descuento $-20$ puntos, índice $80$, `APTO`, aptitud IA y NIC41 en true.
    - Lectura $23.50$: Frontera inactiva ($\le 3.0\sigma$), activo=false, índice $100$, `APTO`.
    - Lectura $23.51$: Frontera activa según diseño conceptual (asumiendo $\sigma$ poblacional $0.50 \rightarrow 22 + 3(0.50) = 23.50$). Marcado con prefijo `[DISCREPANCIA RF-62 σ muestral vs poblacional]` dado que el motor calcula $s_{\text{muestral}}$ vía `statistics.stdev` ($0.51299 \rightarrow$ umbral $23.539$), documentando formalmente la discrepancia con un SELECT/log explícito.
  - **TC-M03-316 (Gap temporal anómalo):**
    - Subcaso (a): Intervalo de 25 min frente a frecuencia nominal de 10 min ($>2\times$). Se marca con prefijo `[DEFECTO CONOCIDO RF-62 Fase 5]` exigiendo gap activo, $gap\_real=25$, $gap\_esperado=10$ e índice $90$ para evidenciar que el caso de uso no tiene implementada la Fase 5.
    - Subcaso (b): Intervalo de 20 min ($\le 2\times$ nominal). Sin flag de anomalía, índice $100$.
    - Subcaso (c) (Período de inactividad RF-60): **BLOQUEADO**. Se conserva el request pero **sin aserciones `pm.test`** (solo `console.log`) para no falsear el cómputo de pruebas aprobadas en el scanner.
  - **TC-M03-317 (Serie insuficiente):**
    - Sensor S2 con únicamente 3 lecturas previas ($<N=20$).
    - Aserciones estrictas: `flags.serie_insuficiente.activo = true`, `clasificacion_calidad = 'INDETERMINADA'`, `indice_calidad = null`, y ausencia total de flags estadísticos (sensor congelado, outlier, drift, gap).
    - Para `apto_para_ia` y `apto_para_nic41` se emite únicamente `console.log` del valor observado, sin `pm.expect`.
  - **TC-M03-323 (Calibración no disponible vs disponible):**
    - Comparación cruzada de la misma serie base + lectura $25.50$ entre sensor S3 (sin fila en `modulo9.calibraciones`) y sensor S4 (con calibración nominal ganancia=1.0, offset=0.0).
    - S3: `calibracion_no_disponible.activo = true`, omisión de evaluación de drift.
    - S4: `calibracion_no_disponible.activo = false` o undefined.
    - Ambos deben arrojar exactamente el mismo índice de calidad ($80$, penalización exclusiva por outlier), verificado mediante una aserción explícita de igualdad entre las variables de colección.
  - **Invariante D7 (Estado Canónico):**
    - Verificación mediante `SELECT COUNT(*)` en `modulo3.telemetria_calidad` confirmando que cada lectura evaluada conserve exactamente una sola fila con `estado_evaluacion = 'VIGENTE'` (con prefijo `[DEFECTO CONOCIDO D7]`).

---

## 2. Parámetros del Motor y Fórmulas
* **Outlier Estadístico (`evaluar_calidad_telemetria_use_case.py:150-161`):**
  $$\mu = \text{mean}(v), \quad s = \text{stdev}(v) \quad \text{sobre la serie de } N=20$$
  $$\text{Condición:} \quad |v - \mu| > k \times s \quad (k=3.0)$$
* **Serie Temporal ($N=20$):**
  Filtro estricto `timestamp_captura < ts` en `telemetria_repository.py:124`. La lectura evaluada (lectura #21) **no forma parte de la serie de cálculo de $\mu$ y $\sigma$**.
* **Aislamiento Temporal de Ventanas:**
  Para evitar contaminación de ventanas entre lecturas evaluadas sucesivas ($25.50$, $23.50$, $23.51$, gap 25 min, gap 20 min), cada una se ejecuta sobre un bloque temporal independiente y limpio de $N=20$ lecturas base separadas por fechas distintas (+1 día por bloque: 2026-10-20, 2026-10-21, 2026-10-22, etc.).

---

## 3. Precondiciones, Sensores y Mitigación de Timeout
1. **Sensores Garantizados:**
   - **S1:** Sensor para Outlier y Gaps (con verificación de ventana limpia sin lecturas posteriores a 2026-10-20).
   - **S2:** Sensor para Serie Insuficiente (sembrado con solo 3 lecturas).
   - **S3:** Sensor sin calibración (se elimina cualquier calibración previa en `modulo9.calibraciones` dentro del sandbox).
   - **S4:** Sensor con calibración nominal (ganancia=1.0, offset=0.0).
2. **Siembra Eficiente por Batch:**
   - Las 20 lecturas base con intervalo de 10 minutos se siembran mediante una sola petición `POST /iot/telemetria/batch` con origen `BUFFER_LOCAL`.
   - La lectura evaluada entra por `POST /iot/telemetria` individual.
   - La suite completa ejecuta únicamente **34 requests** (frente a los más de 120 de una ingesta individual), completando la corrida en aproximadamente **5 a 10 segundos** (muy inferior al timeout de 180 s del Sandbox).
3. **Sandbox Transaccional:**
   - Pre-request a nivel de colección genera automáticamente `run_id` efímero e inyecta `X-Test-Run-Id` y `X-Sandbox-Secret`.
   - La suite finaliza con `DELETE /test-control/runs/{{run_id}}` garantizando la reversión total de cambios.
