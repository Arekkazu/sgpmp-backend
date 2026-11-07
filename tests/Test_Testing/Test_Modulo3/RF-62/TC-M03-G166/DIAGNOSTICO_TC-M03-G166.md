# DIAGNÓSTICO ESTÁTICO DE QA: TC-M03-G166
**Módulo:** 3 — Telemetría IoT / Monitoreo  
**Requisitos:** RF-62 (Evaluación de calidad de datos telemétricos - Sensor congelado), RF-57 (Generación de alertas técnicas), RF-63 (Bitácora de auditoría IoT)  
**Casos agrupados:** TC-M03-309, TC-M03-310, TC-M03-311  
**Modo de análisis:** Estático y lectura exclusiva de código/documentación local (cero tráfico de red hacia TEST, cero invocaciones a pytest/scripts, cero escrituras en BD).  
**Fecha:** 2026-10-18  

---

## A. Resumen Ejecutivo y Semáforo por Subcaso

El caso TC-M03-G166 evalúa la detección de anomalía por **sensor congelado** en sus tres niveles de severidad (`LEVE`, `MODERADO`, `CRITICO`) y su frontera inferior sin flag ($R=4$).

El motor matemático central de RF-62 (`EvaluarCalidadTelemetriaUseCase:131-147`) implementa fielmente los descuentos de penalización (-15, -35, -90), los índices de calidad resultantes (100, 85, 65, 10), la clasificación de calidad (`APTO`, `APTO_CON_RESERVA`, `NO_APTO`) y la derivación de aptitud para IA y NIC 41. Sin embargo, el análisis estático revela **dos discrepancias normativas críticas**:
1. **Desconexión de Alertas Técnicas RF-57:** `EvaluarCalidadTelemetriaUseCase` únicamente interactúa con RF-63 (bitácora de auditoría IoT); **no tiene inyectado el repositorio ni el caso de uso de alertas RF-57**. Ninguna evaluación de calidad por sensor congelado emite actualmente alerta técnica en el backend.
2. **Semántica de "Repeticiones" ($R$) y Lectura Evaluada:** El motor consulta la serie histórica con `timestamp_captura < ts` (`telemetria_repository.py:124`), excluyendo la lectura evaluada del historial. Además, exige que las últimas $M=5$ lecturas históricas sean idénticas (`ultimas_m = serie[:params.M]`), tras lo cual cuenta las repeticiones en toda la ventana histórica $N=20$. Si se evalúa una lectura puntual, las $R$ repeticiones deben estar ya consolidadas en la serie histórica previa.

### Semáforo de Viabilidad por Subcaso

| Subcaso / Aserción | Clasificación QA | Causa Raíz / Justificación Estática |
| :--- | :---: | :--- |
| **TC-309 ($R=4$)**: Sin flag sensor congelado | 🟢 **EJECUTABLE** | Cumple: con 4 repeticiones previas, `len(set(ultimas_m)) == 1` da False ($M=5$). Índice 100, `APTO`. |
| **TC-309 ($R=5$)**: Flag LEVE, descuento -15 | 🟢 **EJECUTABLE CON AJUSTE** | Motor devuelve `LEVE`, descuento 15, índice 85, `APTO`. Requiere serie previa con $R=5$ idénticos. |
| **TC-309 ($R=9$)**: Flag LEVE, descuento -15 | 🟢 **EJECUTABLE CON AJUSTE** | Motor devuelve `LEVE`, descuento 15, índice 85, `APTO`. Requiere serie previa con $R=9$ idénticos. |
| **TC-310 ($R=10$)**: Flag MODERADO, descuento -35 | 🟢 **EJECUTABLE CON AJUSTE** | Motor devuelve `MODERADO`, descuento 35, índice 65, `APTO_CON_RESERVA`. Requiere serie previa con $R=10$. |
| **TC-310 ($R=19$)**: Flag MODERADO, descuento -35 | 🟢 **EJECUTABLE CON AJUSTE** | Motor devuelve `MODERADO`, descuento 35, índice 65, `APTO_CON_RESERVA`. Requiere serie previa con $R=19$. |
| **TC-311 ($R=20$)**: Flag CRITICO, descuento -90 | 🟢 **EJECUTABLE CON AJUSTE** | Motor devuelve `CRITICO`, descuento 90, índice 10, `NO_APTO`. $\sigma=0$ protegido contra ZeroDivisionError. |
| **Aserción Alertas Técnicas RF-57** | 🔴 **DEFECTO PROBABLE / BLOQUEADO** | En `evaluar_calidad_telemetria_use_case.py:223-225`, la Fase 8 no invoca a RF-57. No genera alertas. |
| **Aserción Eventos Auditoría RF-63** | 🟢 **EJECUTABLE** | Emite `EVALUACION_CALIDAD_COMPLETADA` en `modulo3.bitacora_auditoria_iot` con `componente_origen='RF62'`. |

---

## B. Tabla por Subcaso y Aserción

| ID | Paso | Endpoint | ¿Existe? (código / openapi local) | Rol | Resultado Esperado (Especificación) | Comportamiento Actual (Código Fuente) | Viabilidad | Herramienta |
| :--- | :--- | :--- | :---: | :--- | :--- | :--- | :---: | :---: |
| **TC-309.1** | Evaluar lectura con $R=4$ repeticiones previas | `POST /iot/calidad/{id}/evaluar` | SÍ (`calidad_router.py:104`) | Admin (rec 38, act 5) | HTTP 201; `sensor_congelado` no activo o ausente; `indice_calidad=100`; `clasificacion='APTO'`; `apto_para_ia=true`; `apto_para_nic41=true`. | HTTP 201; `flags_detectados` no contiene `sensor_congelado`; índice 100; `APTO`; ambos apto en True. | 🟢 EJECUTABLE | Pytest + requests |
| **TC-309.2** | Evaluar lectura con $R=5$ repeticiones | `POST /iot/calidad/{id}/evaluar` | SÍ (`calidad_router.py:104`) | Admin (rec 38, act 5) | HTTP 201; `sensor_congelado.activo=true`; `severidad='LEVE'`; `M_repeticiones=5`; `valor_repetido='25.40'`; índice 85; `APTO`. | HTTP 201; `sensor_congelado.activo=true`; `severidad='LEVE'`; `M_repeticiones=5`; `valor_repetido='25.4000'`; índice 85; `APTO`. | 🟢 EJECUTABLE CON AJUSTE | Pytest + requests |
| **TC-309.3** | Evaluar lectura con $R=9$ repeticiones | `POST /iot/calidad/{id}/evaluar` | SÍ (`calidad_router.py:104`) | Admin (rec 38, act 5) | HTTP 201; `sensor_congelado.activo=true`; `severidad='LEVE'`; `M_repeticiones=9`; `valor_repetido='25.40'`; índice 85; `APTO`. | HTTP 201; `sensor_congelado.activo=true`; `severidad='LEVE'`; `M_repeticiones=9`; `valor_repetido='25.4000'`; índice 85; `APTO`. | 🟢 EJECUTABLE CON AJUSTE | Pytest + requests |
| **TC-310.1** | Evaluar lectura con $R=10$ repeticiones | `POST /iot/calidad/{id}/evaluar` | SÍ (`calidad_router.py:104`) | Admin (rec 38, act 5) | HTTP 201; `sensor_congelado.activo=true`; `severidad='MODERADO'`; `M_repeticiones=10`; índice 65; `APTO_CON_RESERVA`; `apto_para_nic41=false`. | HTTP 201; `sensor_congelado.activo=true`; `severidad='MODERADO'`; `M_repeticiones=10`; índice 65; `APTO_CON_RESERVA`; `apto_para_nic41=false`. | 🟢 EJECUTABLE CON AJUSTE | Pytest + requests |
| **TC-310.2** | Evaluar lectura con $R=19$ repeticiones | `POST /iot/calidad/{id}/evaluar` | SÍ (`calidad_router.py:104`) | Admin (rec 38, act 5) | HTTP 201; `sensor_congelado.activo=true`; `severidad='MODERADO'`; `M_repeticiones=19`; índice 65; `APTO_CON_RESERVA`; `apto_para_nic41=false`. | HTTP 201; `sensor_congelado.activo=true`; `severidad='MODERADO'`; `M_repeticiones=19`; índice 65; `APTO_CON_RESERVA`; `apto_para_nic41=false`. | 🟢 EJECUTABLE CON AJUSTE | Pytest + requests |
| **TC-311.1** | Evaluar lectura con $R=20$ repeticiones | `POST /iot/calidad/{id}/evaluar` | SÍ (`calidad_router.py:104`) | Admin (rec 38, act 5) | HTTP 201; `sensor_congelado.activo=true`; `severidad='CRITICO'`; `M_repeticiones=20`; índice 10; `NO_APTO`; ambos flags de aptitud en False. | HTTP 201; `sensor_congelado.activo=true`; `severidad='CRITICO'`; `M_repeticiones=20`; índice 10; `NO_APTO`; ambos flags en False; $\sigma=0$ ignorado. | 🟢 EJECUTABLE CON AJUSTE | Pytest + requests |
| **ASERCION-ALERTA** | Alerta técnica ante sensor congelado (RF-57) | `GET /iot/alertas` | SÍ (`alerta_router.py:97`) | Ingeniero / Admin (rec 32, act 2) | Alerta tipo `TECNICA`, severidad coincidente (`LEVE`/`MODERADO`/`CRITICO`), asociada a `id_sensor`. | **NO SE GENERA NINGUNA ALERTA**. `EvaluarCalidadTelemetriaUseCase` no invoca a RF-57. | 🔴 DEFECTO PROBABLE | Pytest + requests / SELECT |
| **ASERCION-AUDITORIA** | Evento de auditoría en bitácora IoT (RF-63) | `GET /iot/auditoria` o `POST /test-control/query` | SÍ (`auditoria_iot_router.py:41`) | Admin (rec 39, act 2) o Sandbox query | Registro con `tipo_evento='EVALUACION_CALIDAD_COMPLETADA'`, `componente_origen='RF62'`, `entidad_afectada_id=str(id_telemetria)`. | Registrado en `modulo3.bitacora_auditoria_iot`. En `accion_detallada` incluye el diccionario `flags`. | 🟢 EJECUTABLE | Pytest + requests / SELECT |

---

## C. Motor de Congelado: Definición Exacta y Comportamiento del Código

### 1. Definición Exacta en el Código Fuente
En `src/telemetry/application/use_cases/calidad/evaluar_calidad_telemetria_use_case.py:131-147`:
```python
# ── Fase 2: Sensor congelado ───────────────────────────────────────────
ultimas_m = serie[:params.M]
if len(ultimas_m) == params.M and len(set(str(v) for v in ultimas_m)) == 1:
    repeticiones = sum(1 for v in serie if v == ultimas_m[0])
    if repeticiones >= 20:
        sev = 'CRITICO'
    elif repeticiones >= 10:
        sev = 'MODERADO'
    else:
        sev = 'LEVE'
    flags['sensor_congelado'] = {
        'activo': True,
        'severidad': sev,
        'N_evaluadas': len(serie),
        'M_repeticiones': repeticiones,
        'valor_repetido': str(ultimas_m[0]),
    }
```

### 2. Puntos Clave del Mecanismo
1. **Población de `serie`:**
   En `SqlAlchemyTelemetriaRepository.obtener_serie_temporal` (`telemetria_repository.py:121-129`):
   ```sql
   SELECT valor_crudo FROM modulo3.telemetrias
   WHERE id_sensor = :sensor
     AND estado_calidad = 'LECTURA_VALIDA'
     AND timestamp_captura < :ts
   ORDER BY timestamp_captura DESC LIMIT :n
   ```
   - **La lectura que se está evaluando NO entra en `serie`**: la cláusula estricta `timestamp_captura < :ts` solo recupera lecturas estrictamente anteriores.
   - `serie` tiene longitud máxima $N=20$ (`params.N = 20` según `ParametrosCalidadStubAdapter`).
   - `serie[:params.M]` toma las primeras $M=5$ filas retornadas, que corresponden a las **5 lecturas previas más recientes** (orden descendente).
2. **Condición de Disparo:**
   - Requiere `len(ultimas_m) == 5` y que las 5 más recientes sean idénticas según `str(v)`.
   - **No exige que toda la ventana sea consecutiva**: una vez que las últimas 5 son idénticas a un valor $V_0$, calcula `sum(1 for v in serie if v == ultimas_m[0])`. Si en la serie histórica de 20 lecturas existen otras lecturas aisladas con ese mismo valor, se sumarán al conteo total.
3. **Fronteras de Severidad:**
   - `repeticiones >= 20` $\rightarrow$ `CRITICO`
   - `10 <= repeticiones < 20` $\rightarrow$ `MODERADO`
   - `repeticiones < 10` (al activarse con al menos 5) $\rightarrow$ `LEVE`

### 3. Tabla Comparativa de Interpretaciones (Evitando el Error "Off-by-One")

Se analiza el comportamiento según dos interpretaciones de los datos de prueba:
- **Interpretación (i) — La lectura evaluada es la $R$-ésima idéntica:** La serie histórica previa contiene solo $(R-1)$ lecturas idénticas.
- **Interpretación (ii) — La serie histórica previa contiene ya $R$ lecturas idénticas:** Se evalúa una lectura posterior que también tiene el valor $25.40$ (o se evalúa una lectura que tiene tras de sí exactamente $R$ idénticas).

| $R$ del Plan | Interpr. (i): Serie previa con $(R-1)$ idénticos | Interpr. (ii): Serie previa con $R$ idénticos | ¿Cuál coincide con el Plan? | Discrepancia / Hallazgo |
| :---: | :--- | :--- | :---: | :--- |
| **$R=4$** | Serie previa tiene 3 idénticos $\rightarrow$ `len(set(ultimas_m))` mezcla valores $\rightarrow$ **Sin flag** (Índice 100, `APTO`) | Serie previa tiene 4 idénticos $\rightarrow$ `len(set(ultimas_m))` mezcla valores ($M=5$) $\rightarrow$ **Sin flag** (Índice 100, `APTO`) | **Ambas** | En ambas interpretaciones $R=4$ no activa el flag porque no alcanza $M=5$. |
| **$R=5$** | Serie previa tiene 4 idénticos $\rightarrow$ `len(set(ultimas_m))` mezcla con la lectura 5 anterior $\rightarrow$ **NO ACTIVA FLAG** (Índice 100). | Serie previa tiene 5 idénticos $\rightarrow$ `len(set)` = 1 $\rightarrow$ `M_repeticiones=5` $\rightarrow$ **LEVE**, -15 (Índice 85, `APTO`) | **Interpretación (ii)** | **CRÍTICO:** Si solo se envían 5 lecturas idénticas en total y se evalúa la 5.ª (Interpr. i), la serie previa solo tiene 4 y **el test fallará** (no detecta congelado). Para probar $R=5$, deben existir **5 lecturas idénticas en el historial previo** antes de la evaluada. |
| **$R=9$** | Serie previa tiene 8 idénticos $\rightarrow$ `M_repeticiones=8`, **LEVE**, -15 (Índice 85, `APTO`) | Serie previa tiene 9 idénticos $\rightarrow$ `M_repeticiones=9`, **LEVE**, -15 (Índice 85, `APTO`) | **Interpretación (ii)** | El plan exige explícitamente asertar `M_repeticiones == 9`. Solo la Interpr. (ii) produce `M_repeticiones=9`. |
| **$R=10$** | Serie previa tiene 9 idénticos $\rightarrow$ `M_repeticiones=9`, **LEVE** (Índice 85, `APTO`) $\rightarrow$ **FALLO DE TRANSICIÓN** | Serie previa tiene 10 idénticos $\rightarrow$ `M_repeticiones=10`, **MODERADO**, -35 (Índice 65, `APTO_CON_RESERVA`) | **Interpretación (ii)** | **CRÍTICO:** Con la Interpr. (i), $R=10$ daría 9 repeticiones y quedaría en `LEVE` en vez de `MODERADO`. Solo la Interpr. (ii) valida la frontera de severidad. |
| **$R=19$** | Serie previa tiene 18 idénticos $\rightarrow$ `M_repeticiones=18`, **MODERADO** (Índice 65) | Serie previa tiene 19 idénticos $\rightarrow$ `M_repeticiones=19`, **MODERADO**, -35 (Índice 65, `APTO_CON_RESERVA`) | **Interpretación (ii)** | Solo la Interpr. (ii) reproduce la aserción esperada `M_repeticiones == 19`. |
| **$R=20$** | Serie previa tiene 19 idénticos $\rightarrow$ `M_repeticiones=19`, **MODERADO** (Índice 65) $\rightarrow$ **FALLO DE TRANSICIÓN** | Serie previa tiene 20 idénticos $\rightarrow$ `M_repeticiones=20`, **CRITICO**, -90 (Índice 10, `NO_APTO`) | **Interpretación (ii)** | **CRÍTICO:** Con la Interpr. (i), $R=20$ daría 19 repeticiones y no alcanzaría `CRITICO`. Requiere 20 lecturas idénticas en la serie previa. |

> **Conclusión Normativa de QA:** La serie debe construirse de modo que **el historial previo contenga exactamente $R$ lecturas idénticas** ($R \in \{4, 5, 9, 10, 19, 20\}$) antes del timestamp de la lectura evaluada.

### 4. Estabilidad Numérica y Efecto en Otros Flags (Fases 3, 4, 5)
- **División por Cero en Outlier ($\sigma = 0$ con $R=20$):**
  En `evaluar_calidad_telemetria_use_case.py:153`, el código valida: `if sigma > 0 and abs(float(valor) - mu) > params.k * sigma:`.  
  Cuando las 20 lecturas son idénticas a 25.40, `sigma = 0.0`. La condición `sigma > 0` es falsa, por lo que **no se produce ZeroDivisionError** ni se activa outlier estadístico espurio.
- **Rango Físico (Límite Físico):**
  Para la variable 9 (`TEMPERATURA_AMBIENTAL`), `_RANGOS_FISICOS[9] = (-40, 60)`. El valor nominal $25.40$ se encuentra holgadamente dentro del rango físico, por lo que la rama `elif id_variable in _RANGOS_FISICOS` no activa ningún flag.
- **Drift Estadístico (Fase 4):**
  Con calibración nominal (ganancia = 1.0, offset = 0.0), `val_cal_esperado` es exactamente igual a `media_n`. Por tanto, `media_n - val_cal_esperado = 0`, la magnitud de drift es 0.0% y no se activa `posible_drift`.
- **Gap Temporal (Fase 5):**
  No está implementado en la evaluación de calidad (`evaluar_calidad_telemetria_use_case.py:195-197`).
- **Resultado en $R=4$:**
  Al no activarse ningún flag, `calcular_indice_calidad(flags)` retorna `100 - 0 = 100`, con clasificación `APTO` y ambos flags de aptitud en `True`. Ningún flag contamina el resultado.

### 5. Comparación de Valores y Formato Decimal
- En `telemetria_repository.py:129`, `obtener_serie_temporal` lee `valor_crudo` y retorna `[Decimal(str(r[0])) for r in rows]`.
- La columna `modulo3.telemetrias.valor_crudo` es `Numeric(10, 4)`.
- En PostgreSQL, un valor insertado como `25.40` se almacena como `25.4000`. Al recuperarlo en Python como `Decimal(str(r[0]))`, se obtiene `Decimal('25.4000')`.
- En el código del motor:
  `valor_repetido = str(ultimas_m[0])` $\rightarrow$ produce la cadena `'25.4000'`.
- **Aserción de QA:** La aserción sobre `valor_repetido` debe normalizarse numéricamente (`float(valor_repetido) == 25.4` o `Decimal(valor_repetido) == Decimal('25.40')`) en lugar de comparar la cadena rígida `"25.40"`, ya que el backend devuelve `'25.4000'`.

---

## D. Estrategia de Construcción de la Serie

### 1. Receta Determinista de las 20 Lecturas Previas Distintas
Para evitar que una lectura previa distinta active accidentalmente sensor congelado o drift, y para mantener la media cercana a 25.40 °C sin outliers ($\sigma$ moderado):
- **Variable:** `TEMPERATURA_AMBIENTAL` (id=9 en `CATALOGO_I3P1`).
- **Rango Físico:** [-40.0, 60.0] °C. Rango nominal biológico seguro: [20.0, 30.0] °C.
- **Valor Base:** 25.40 °C.
- **Valores Deterministas (20 lecturas espaciadas 10 min):**
  Generar 10 pares simétricos alrededor de 25.40:
  $25.40 \pm \delta_i$, con $\delta_i \in \{0.15, 0.25, 0.35, 0.45, 0.55, 0.65, 0.75, 0.85, 0.95, 1.05\}$.
  Ningún valor de la serie base es exactamente $25.40$, evitando contaminación del conteo de congelado.  
  Media exacta = $25.40$ °C, desviación estándar $\sigma \approx 0.67$ °C (con $k=3.0$, la banda de outlier es $[23.39, 27.41]$, ningún punto cae fuera).

### 2. Comparación de Estrategias: Incremental vs. Por Frontera

| Criterio | Opción A: Serie Incremental Única | Opción B: Sensores / Series Independientes por Frontera |
| :--- | :--- | :--- |
| **Descripción** | 1 sensor. 20 lecturas distintas base. Se inyectan sucesivamente bloques de lecturas idénticas (hasta 4 $\rightarrow$ eval; +1 [llega a 5] $\rightarrow$ eval; +4 [llega a 9] $\rightarrow$ eval; +1 [llega a 10] $\rightarrow$ eval; +9 [llega a 19] $\rightarrow$ eval; +1 [llega a 20] $\rightarrow$ eval). | 6 sensores independientes (o 6 series temporales aisladas en el tiempo): cada uno recibe sus 20 distintas base + exactamente $R$ lecturas idénticas ($R \in \{4, 5, 9, 10, 19, 20\}$). |
| **Número de Ingestas (POST)** | 20 (base) + 4 + 1 + 4 + 1 + 9 + 1 + 6 (evaluadas) = **46 requests de ingesta**. | $6 \times 20$ (base) + (4+5+9+10+19+20) + 6 = **193 requests de ingesta**. |
| **Riesgo de Aislamiento** | Medio: Si una lectura intermedia falla, descalibra los conteos subsiguientes. | Bajo: Aislamiento total entre escenarios. |
| **Tiempo de Ejecución** | ~46 requests $\times$ 70 ms $\approx$ **3.2 segundos**. | ~193 requests $\times$ 70 ms $\approx$ **13.5 segundos**. |
| **Presupuesto Timeout Sandbox (180 s)** | Holgado (< 2% del límite). | Seguro (< 8% del límite), pero mayor riesgo si hay latencia. |
| **Riesgo de Deduplicación / Enfriamiento** | **Inexistente en RF-62:** El motor de calidad no tiene enfriamiento; cada `POST /evaluar` reevalúa la telemetría solicitada. En alertas RF-57 no impacta porque RF-57 no está conectado. | Inexistente. |

### 3. Recomendación de QA
**Se recomienda la Opción A (Incremental)** organizada dentro de una misma clase de prueba por dispositivo/sensor, utilizando timestamps estrictamente crecientes espaciados 10 minutos.  
- **Optimización:** En lugar de hacer requests individuales, las 20 lecturas base pueden inyectarse mediante **un único request de batch** (`POST /iot/telemetria/batch`, Flujo C `BUFFER_LOCAL`), reduciendo los requests de red de 46 a solo **15 requests en total** (1 batch de 20 + inyecciones puntuales + 6 llamadas a `/evaluar`), ejecutándose en menos de **2 segundos**.

---

## E. Precondiciones y Selección Dinámica de Datos

En cumplimiento de la **Política Anti-Hardcode**:

1. **Descubrimiento Dinámico de Sensor y Dispositivo:**
   - No fijar IDs numéricos en el código de prueba.
   - En preflight, consultar vía `POST /test-control/query`:
     ```sql
     SELECT d.id_dispositivo_iot, d.serial, s.id_sensores, s.id_variable_ambiental
     FROM modulo9.dispositivos_iot d
     JOIN modulo9.sensores s ON s.id_dispositivo_iot = d.id_dispositivo_iot
     WHERE d.es_activo = true AND s.es_activo = true AND s.id_variable_ambiental = 9
     LIMIT 1;
     ```
   - Utilizar el `serial` del dispositivo descubierto como `access_key` para la autenticación de ingesta (`DispositivoM09Adapter:31`).
2. **Aislamiento Temporal de la Ventana:**
   - La ventana de evaluación se aísla por rango temporal relativo a `ahora`:
     $T_0 = \text{ahora} - 24\text{ horas}$.
   - Cada lectura se genera con $T_i = T_0 + i \times 10\text{ minutos}$.
   - Dado que $T_i < \text{ahora}$, no se viola el límite de drift futuro ($+300$ s) y se mantiene dentro de la ventana admisible de buffer local ($72$ horas).
   - El filtro `timestamp_captura < :ts` solo tomará las lecturas inyectadas en esa ventana, previniendo cualquier lectura intrusa previa.
3. **Calibración Nominal del Sensor:**
   - Para que la ganancia sea 1.0 y el offset 0.0, el test debe verificar en preflight si el sensor tiene una calibración activa en `modulo9.calibraciones` (`CalibracionM09Adapter:30`).
   - Si no existe calibración, `CalibracionM09Adapter.obtener_parametros` retorna `None`, lo que omite la fase de drift (`omitir_drift = True` en `evaluar_calidad_telemetria_use_case.py:175`), manteniendo el índice en 100 sin perturbaciones.
   - Si se requiere fijar explícitamente calibración nominal, el endpoint administrativo es:
     `POST /configuracion/sensores/{id_sensor}/calibrar` (`sensor_router.py:171`), enviando `ganancia=1.0` y `offset_calibracion=0.0`.

---

## F. Efectos Colaterales: Alertas RF-57, Auditoría RF-63 y Sandbox

### 1. Generación de Alertas Técnicas RF-57 (Hallazgo Crítico)
- **Especificación (RF-62 Fase 8 / Plan):** Toda detección de sensor congelado (incluso `LEVE`) debe emitir una alerta técnica (tipo `TECNICA`) dirigida al ingeniero de campo vía RF-57.
- **Implementación Real:**
  Al revisar `evaluar_calidad_telemetria_use_case.py:223-225`:
  ```python
  # ── Fase 8: Notificaciones ─────────────────────────────────────────────
  self._emitir_auditoria(TipoResultado.EXITOSO, id_telemetria, flags)
  return evaluacion
  ```
  El caso de uso **no tiene ninguna referencia a `AlertaRepository` ni a `GenararAlertaUseCase`**.
- **Consecuencia para QA:**
  Cualquier aserción que espere encontrar una alerta en `GET /iot/alertas` o en la tabla `modulo3.alertas` **fallará con un Defecto Probable del Backend (funcionalidad no implementada / desconectada)**.
  Se recomienda clasificar esta aserción como `DEFECTO PROBABLE` y acondicionarla en el test con `pytest.skip` documentado o aserción condicional para no bloquear la ejecución de la validación matemática de RF-62.

### 2. Evento de Bitácora de Auditoría IoT RF-63
- **Implementación Real:**
  `_emitir_auditoria` (`evaluar_calidad_telemetria_use_case.py:255-279`) ejecuta `RegistrarEventoAuditoriaIotUseCase`:
  - `tipo_evento = 'EVALUACION_CALIDAD_COMPLETADA'`
  - `componente_origen = ComponenteOrigen.RF62`
  - `severidad_log = SeveridadLog.WARNING if anomalias else SeveridadLog.INFO`
  - `entidad_afectada_id = str(id_telemetria)`
  - `accion_detallada = {'flags': flags}`
- **Consulta y Verificación:**
  - Dentro del sandbox, se puede verificar consultando `POST /test-control/query`:
    ```sql
    SELECT tipo_evento, severidad_log, accion_detallada 
    FROM modulo3.bitacora_auditoria_iot 
    WHERE entidad_afectada_id = :id_telemetria
    ```
  - También es consultable vía endpoint `GET /iot/auditoria?entidad_afectada_id={id_telemetria}` (`auditoria_iot_router.py:49`), el cual requiere permiso (39, 2).

### 3. Aislamiento y Comportamiento del Sandbox (`X-Test-Run-Id`)
- **Operación Transaccional:**
  Tanto la ingesta (`telemetria_router.py`), como la evaluación puntual (`calidad_router.py`) y la bitácora (`SqlAlchemyBitacoraAuditoriaIotRepository`) utilizan las dependencias `get_db` y `get_db_sistema` (`database.py:161-215`).
- Cuando `ENABLE_TEST_SANDBOX=true` y se envía `X-Test-Run-Id`:
  - `get_or_create_test_session` (`testing_sandbox.py:55`) asocia la sesión a la conexión transaccional con `join_transaction_mode="create_savepoint"`.
  - Los `commit()` internos de la aplicación únicamente consolidan el savepoint dentro de la sesión de prueba.
  - Al invocar `DELETE /test-control/runs/{run_id}`, se ejecuta `entry['transaction'].rollback()`, eliminando **todas** las lecturas, evaluaciones y eventos de bitácora insertados.
- **Riesgo de Fugas Externas:**
  - No hay emisión de notificaciones push (FCM) ni envío de correos electrónicos en `EvaluarCalidadTelemetriaUseCase`.
  - La tabla `modulo1.eventos` no es impactada por la evaluación de calidad de telemetría (solo se escribe en `modulo3.bitacora_auditoria_iot`).
  - **Inocuidad garantizada:** El rollback del sandbox limpia el 100% de los datos generados durante la prueba.

---

## G. Riesgos, Discrepancias Spec vs. Implementación y Defectos Probables

1. **Discrepancia D-01: Alertas Técnicas RF-57 no emitidas (Defecto Crítico de Integración)**
   - *Evidencia:* `evaluar_calidad_telemetria_use_case.py:223-225`.
   - *Detalle:* El plan y la especificación de RF-62 Fase 8 exigen emitir alerta técnica ante anomalía de sensor congelado. El backend solo implementó la bitácora RF-63 en la Fase 8.
2. **Discrepancia D-02: Ausencia del campo `ventana_temporal` en el flag `sensor_congelado`**
   - *Evidencia:* `evaluar_calidad_telemetria_use_case.py:141-147`.
   - *Detalle:* El flag contiene únicamente `{'activo': True, 'severidad': sev, 'N_evaluadas': int, 'M_repeticiones': int, 'valor_repetido': str}`. La especificación del plan mencionaba verificar `ventana_temporal`, pero este campo no existe en el schema ni en la entidad.
3. **Discrepancia D-03: Semántica de Conteo de Repeticiones e Inclusión de Lectura Evaluada**
   - *Evidencia:* `evaluar_calidad_telemetria_use_case.py:132-134` y `telemetria_repository.py:124`.
   - *Detalle:* La lectura evaluada puntual no suma a las repeticiones porque `obtener_serie_temporal` filtra con `timestamp_captura < ts`. La serie previa debe contener la totalidad de las $R$ repeticiones para que `M_repeticiones` coincida con $R$.
4. **Discrepancia D-04: Autoevaluación en Ingesta crea evaluaciones paralelas**
   - *Evidencia:* `ingerir_telemetria_use_case.py:265-276`.
   - *Detalle:* Cada lectura ingerida dispara su propia evaluación de calidad de fondo. Al ejecutar luego `POST /iot/calidad/{id}/evaluar`, se genera una segunda evaluación en `modulo3.telemetria_calidad`. El endpoint `GET /iot/calidad/{id}` (`telemetria_calidad_repository.py:53`) recupera la evaluación vigente más reciente (`order_by(fecha_creacion.desc()).first()`).  
   - *Mitigación:* Se debe usar directamente el payload retornado por `POST /iot/calidad/{id}/evaluar` como fuente primaria de aserción.

---

## H. Preguntas Abiertas para el Equipo de Desarrollo y Análisis

1. **Integración RF-62 $\rightarrow$ RF-57:** ¿Cuándo está planificada la integración para que la detección de anomalías de calidad invoque formalmente a `GenararAlertaUseCase` de RF-57? ¿Debe el test de aceptación saltar esta aserción mediante un `xfail`/`skip` justificado hasta que se complete dicha tarea?
2. **Definición de Literal de Estado Vigente (Decisión D7 - RESUELTO 2026-10-19):** Resuelto por respuesta oficial de análisis (RFC de aclaración de RF-62 en trámite, nº pendiente). Literal oficial: `VIGENTE`; catálogo: `{"VIGENTE", "SUPERADA"}`; descartado `ACTIVA`. Regla canónica: máximo UNA evaluación VIGENTE por lectura (la anterior pasa a `SUPERADA`). Se constató defecto en `/evaluar` que deja dos vigentes, el cual es probado de forma estricta.
3. **Mantenimiento del Parámetro $M$ configurable (RF-62 / M09):** Actualmente $M=5$ está fijo en el adapter stub (`ParametrosCalidadStubAdapter`). Cuando M09 permita parametrizar $M$, ¿las fronteras se recalcularán automáticamente como $[M, 2M)$ para `LEVE`, $[2M, 4M)$ para `MODERADO` y $[\ge 4M]$ para `CRITICO`?

---

## I. Propuesta Preliminar de Estructura de Tests y Variables `spec`

### 1. Bloque de Especificación Normativa (`spec`)
```python
spec = {
    # Parámetros base del motor estadístico
    "N": 20,                          # Tamaño de ventana histórica (RF-62 Fase 1)
    "M": 5,                           # Mínimo de lecturas consecutivas idénticas (Fase 2)
    "muestreo_minutos": 10,           # Frecuencia de muestreo nominal

    # Fronteras de severidad para sensor congelado (derivadas de M=5)
    "fronteras_repeticiones": {
        "LEVE_MIN": 5,                # M
        "LEVE_MAX": 9,                # 2M - 1
        "MODERADO_MIN": 10,           # 2M
        "MODERADO_MAX": 19,           # 4M - 1
        "CRITICO_MIN": 20,            # 4M
    },

    # Tabla de penalizaciones (RF-62 Fase 6)
    "descuentos": {
        "sensor_congelado": {
            "LEVE": 15,
            "MODERADO": 35,
            "CRITICO": 90,
        }
    },

    # Umbrales de clasificación de calidad
    "umbrales_clasificacion": {
        "APTO_MIN": 80,
        "APTO_CON_RESERVA_MIN": 40,
        "NO_APTO_MAX": 39,
    },

    # Mapeo de estados de ciclo de vida (Decisión D7)
    "estados": {
        "estado_superado": "SUPERADA",
        "estado_vigente": None,       # PENDIENTE DE ANÁLISIS
        "catalogo_estados": None,     # PENDIENTE DE ANÁLISIS
        "ESTADOS_DEFINIDOS": False,
    }
}
```

### 2. Estructura de Escenarios y Clases de Prueba Sugerida
- `TestTCM03G166Preflight`: Validación estática de conectividad, descubrimiento dinámico de sensor/dispositivo y verificación de permisos RBAC.
- `TestTCM03309SensorCongeladoLeve`:
  - `test_r4_sin_flag_indice_100`: Ejecuta evaluación con $R=4$ idénticos previos. Aserción de ausencia de flag e índice 100 (`APTO`).
  - `test_r5_frontera_inferior_leve`: Evalúa con $R=5$. Aserción de flag `sensor_congelado` activo, severidad `LEVE`, `M_repeticiones=5`, índice 85 (`APTO`).
  - `test_r9_frontera_superior_leve`: Evalúa con $R=9$. Aserción de severidad `LEVE`, `M_repeticiones=9`, índice 85 (`APTO`).
- `TestTCM03310SensorCongeladoModerado`:
  - `test_r10_frontera_inferior_moderado`: Evalúa con $R=10$. Aserción de severidad `MODERADO`, `M_repeticiones=10`, índice 65 (`APTO_CON_RESERVA`), `apto_para_nic41=false`.
  - `test_r19_frontera_superior_moderado`: Evalúa con $R=19$. Aserción de severidad `MODERADO`, `M_repeticiones=19`, índice 65 (`APTO_CON_RESERVA`).
- `TestTCM03311SensorCongeladoCritico`:
  - `test_r20_frontera_critico`: Evalúa con $R=20$. Aserción de severidad `CRITICO`, `M_repeticiones=20`, índice 10 (`NO_APTO`), ambos flags de aptitud en `False`.
  - `test_r20_estabilidad_sigma_cero`: Confirma que la ausencia de varianza ($\sigma=0$) no provoca errores numéricos.
- `TestTCM03G166EfectosColaterales`:
  - `test_evento_auditoria_rf63`: Verifica la emisión del evento `EVALUACION_CALIDAD_COMPLETADA` en `modulo3.bitacora_auditoria_iot`.
  - `test_alerta_tecnica_rf57`: Verificación condicional de alerta técnica RF-57 (marcada con skip/xfail ante la desconexión actual en el use case).

---
**Declaración de Cumplimiento:** Se confirma formalmente que no se generó ningún tráfico de red, no se ejecutó ningún comando ni script contra el entorno de pruebas, no se modificó el código fuente del backend y no se realizaron escrituras en base de datos.
