# DISEÑO Y PRECONDICIONES — TC-M03-G167 (RF-62 / RF-57 / RF-63)

## 1. Identificación del Caso
* **Caso de Prueba:** TC-M03-G167 — Detección de drift: fronteras de porcentaje.
* **Subcasos cubiertos:**
  - **TC-M03-313:** Drift $<10\%$ (fronteras de inactividad $\le 5\%$ y actividad $<10\%$).
    - $5.00\%$: $\mu=21.000$, $\text{offset}=-1.000 \rightarrow$ esperado $20.000$, magnitud $5.00\%$. Inactivo (descuento $0$, índice $100$, `APTO`, `apto_para_nic41=true`).
    - $7.00\%$: $\mu=21.400$, $\text{offset}=-1.400 \rightarrow$ esperado $20.000$, magnitud $7.00\%$. Activo (descuento $-10$, índice $90$, `APTO`, `apto_para_nic41=true`).
    - $9.99\%$: $\mu=21.998$, $\text{offset}=-1.998 \rightarrow$ esperado $20.000$, magnitud $9.99\%$. Activo (descuento $-10$, índice $90$, `APTO`, `apto_para_nic41=true`).
  - **TC-M03-314:** Drift $10\%–20\%$ (frontera inferior exacta $10.00\%$ e intermedio $15.00\%$).
    - $10.00\%$: $\mu=22.000$, $\text{offset}=-2.000 \rightarrow$ esperado $20.000$, magnitud $10.00\%$. Activo (descuento $-25$, índice $75$, `APTO_CON_RESERVA`, `apto_para_nic41=false`).
    - $15.00\%$: $\mu=23.000$, $\text{offset}=-3.000 \rightarrow$ esperado $20.000$, magnitud $15.00\%$. Activo (descuento $-25$, índice $75$, `APTO_CON_RESERVA`, `apto_para_nic41=false`).
  - **TC-M03-315:** Drift $>20\%$ (frontera superior exacta $20.01\%$ y severo $25.00\%$).
    - $20.01\%$: $\mu=24.002$, $\text{offset}=-4.002 \rightarrow$ esperado $20.000$, magnitud $20.01\%$. Activo (descuento $-40$, índice $60$, `APTO_CON_RESERVA`, `apto_para_nic41=false`, alerta técnica RF-57 exigida).
    - $25.00\%$: $\mu=25.000$, $\text{offset}=-5.000 \rightarrow$ esperado $20.000$, magnitud $25.00\%$. Activo (descuento $-40$, índice $60$, `APTO_CON_RESERVA`, `apto_para_nic41=false`, alerta técnica RF-57 exigida, bitácora RF-63).

---

## 2. Parámetros del Motor y Fórmulas
* **Fórmula de drift (`evaluar_calidad_telemetria_use_case.py:178-185`):**  
  $$\text{val\_cal\_esperado} = \mu(\text{serie}) \times \text{ganancia} + \text{offset}$$
  $$\text{media\_n} = \mu(\text{serie})$$
  $$\text{magnitud} = \frac{|\text{media\_n} - \text{val\_cal\_esperado}|}{|\text{val\_cal\_esperado}|} \times 100$$
  Condición de activación: $\text{magnitud} > 5.0\%$ y $\text{misma\_dir} \ge P$ ($P=3$).
* **Composición de la Ventana ($N=20$):**
  La serie histórica consultada por el repositorio (`telemetria_repository.py:124`) filtra estrictamente `timestamp_captura < ts`. Por lo tanto, **la lectura evaluada (lectura #21) no entra en el cálculo de $\mu_{\text{serie}}$ ni en la ventana de $N=20$ lecturas**.
* **Fronteras y Penalizaciones:**
  - $\le 5\%$: Inactivo (0 puntos de descuento $\rightarrow$ Índice 100, `APTO`, NIC41=true).
  - $> 5\%$ y $< 10\%$: Penalización -10 puntos (Índice 90, `APTO`, NIC41=true).
  - $10\% \le \text{drift} \le 20\%$: Penalización -25 puntos (Índice 75, `APTO_CON_RESERVA`, NIC41=false).
  - $> 20\%$: Penalización -40 puntos (Índice 60, `APTO_CON_RESERVA`, NIC41=false).

---

## 3. Precondiciones y Estrategia de Inocuidad
1. **Calibraciones:** Precondición inyectada dinámicamente mediante `INSERT INTO modulo9.calibraciones` a través de `POST /test-control/query` para cada escenario. Al estar bajo el contexto transaccional del sandbox (`X-Test-Run-Id`), se aíslan en la sesión de pruebas y se eliminan en el rollback.
2. **Descubrimiento y Limpieza de Ventana:**
   - Se descubre un sensor activo en `modulo9.sensores` emparejado con `modulo9.dispositivos_iot`.
   - Se valida mediante consulta SQL que el sensor elegido no tenga lecturas posteriores a las de la serie de prueba (`total_posteriores = 0`). Si tuviera lecturas previas, el orden cronológico o el desfase de timestamps podría alterar la serie de $N=20$.
3. **Mitigación de Timeout (180 s):**
   - Para no disparar 20 peticiones HTTP individuales por cada uno de los 7 escenarios (140 requests), cada serie de 20 lecturas previas se siembra mediante un único llamado a `POST /iot/telemetria/batch` con origen `BUFFER_LOCAL`.
   - La lectura #21 (evaluada) se ingresa mediante `POST /iot/telemetria` individual.
   - El volumen total de requests se reduce de ~155 a tan solo **38 requests**, completando la corrida en aproximadamente 6 a 12 segundos (muy por debajo del límite de 180 s).

---

## 4. Defectos Conocidos y Hallazgos Normativos
1. **[DEFECTO CONOCIDO RF-57] Alertas técnicas no emitidas:**
   En `evaluar_calidad_telemetria_use_case.py:223-225`, la Fase 8 del pipeline solo emite auditoría a la bitácora RF-63; no invoca el use case ni el repositorio de alertas de RF-57. En los escenarios de drift severo ($>20\%$, $20.01\%$ y $25\%$), el test exige la presencia de la alerta técnica en `modulo3.alertas` con el prefijo `[DEFECTO CONOCIDO RF-57]`, evidenciando el defecto para control de calidad.
2. **[DEFECTO CONOCIDO D7] Invariante de una sola evaluación VIGENTE:**
   Se valida mediante consulta SQL sobre `modulo3.telemetria_calidad` que cada lectura evaluada conserve una única fila con `estado_evaluacion = 'VIGENTE'`.
