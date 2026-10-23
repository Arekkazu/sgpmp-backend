# DIAGNÓSTICO TÉCNICO Y DE VIABILIDAD — TC-M03-G165 (RF-62 / RF-63)

**Módulo:** Módulo 3 — Telemetría IoT  
**Requerimientos:** RF-62 (Evaluación de Calidad de Datos Telemétricos) y RF-63 (Bitácora de Auditoría IoT)  
**Grupo de Prueba:** TC-M03-G165 (Evaluación puntual, motor de descuentos, saturación y aptitud)  
**Casos originales agrupados:** TC-M03-303, TC-M03-318 (a, b, c), TC-M03-319, TC-M03-320  
**Ambiente:** TEST (`https://api.inmero.co/back-sigab-test`)  
**Fecha de Diagnóstico:** 2026-10-16  
**Rol del Evaluador:** Ingeniero QA Senior (Modo Solo Lectura)

---

## A. Resumen Ejecutivo (y Semáforo por Subcaso)

Se realizó un diagnóstico exhaustivo de arquitectura, base de datos y contratos en vivo (OpenAPI del servidor TEST) para el grupo de pruebas **TC-M03-G165**. Los endpoints centrales `POST /iot/calidad/{id_telemetria}/evaluar` y `GET /iot/calidad/{id_telemetria}` están **100% desplegados y operativos** en TEST, respaldados por la tabla `modulo3.telemetria_calidad` y gobernados por RBAC (recurso 38, acción 5 para evaluar; roles Administrador e Ingeniero de Campo).

No obstante, se identifican **3 discrepancias críticas entre la especificación del plan y la implementación actual**:
1. **Fase 5 de Gap Temporal Incompleta:** El motor de cálculo (`EvaluarCalidadTelemetriaUseCase.py:194-198`) tiene la detección de `gap_temporal_anomalo` como comentario no implementado (no activa el flag).
2. **Incompatibilidad Lógica Outlier + Congelado:** Matemáticamente, una lectura no puede ser idéntica a las anteriores (congelada) y simultáneamente diferir por $>3\sigma$ (outlier). Con $\sigma=0$, la división no explota porque el código protege con `if sigma > 0:`, pero **nunca** activa el flag de outlier estadístico.
3. **ParametrosCalidadStubAdapter Fijo:** Los parámetros $k=3.0$, $M=5$, $N=20$, $P=3$ (en vez de $P=5$), `umbral_drift=5.0%` están cableados en un stub en memoria (`ParametrosCalidadStubAdapter.py:14-22`) y no se leen de M09.

### Semáforo de Viabilidad por Subcaso:
* 🟢 **TC-M03-303 (Happy Path evaluación puntual):** **EJECUTABLE CON AJUSTE** (Precondición de lectura no evaluada requiere estrategia de aislamiento o ingestión previa; aserción de RF-53 verificable; bitácora RF-63 verificable en BD).
* 🟡 **TC-M03-318(a) (Flags múltiples: Outlier + Drift + Gap $\rightarrow$ 60):** **EJECUTABLE CON AJUSTE** (El gap no se activa por código; drift 7% requiere offset de calibración; outlier requiere inyectar salto $>3\sigma$ en la lectura evaluada).
* 🟡 **TC-M03-318(b) (Congelado MODERADO + Drift 15% $\rightarrow$ 40):** **EJECUTABLE CON AJUSTE** (Requiere 20 lecturas de serie con $\ge 10$ repeticiones y calibración con offset 15%).
* 🔴 **TC-M03-318(c) (Congelado CRÍTICO + Outlier $\rightarrow$ 0):** **DEFECTO PROBABLE / DISCREPANCIA ESPECIFICACIÓN** (Con 20 lecturas idénticas $\sigma=0$; el código omite el outlier por `sigma > 0`. El índice resultante es 10, no 0).
* 🟢 **TC-M03-319 (APTO lectura nominal $\rightarrow$ 100):** **EJECUTABLE** (Serie sin perturbaciones, índice 100, ambos flags `true`).
* 🔴 **TC-M03-320 (NO_APTO Congelado MODERADO + Outlier + Gap $\rightarrow$ 35):** **DEFECTO PROBABLE / DISCREPANCIA ESPECIFICACIÓN** (Gap inactivo y contradicción outlier/congelado. Exclusión en M04/M06 no existe en el sistema).
* 🟡 **Aserción Evento RF-63:** **EJECUTABLE CON AJUSTE** (Auditoría se escribe en `modulo3.bitacora_auditoria_iot` con `componente_origen='RF62'`, `clasificacion_registro='NIC41'`, `retencion_aplicable=5`. No hay endpoint REST para filtrar por lectura; debe verificarse vía `POST /test-control/query`).
* 🔴 **Aserción Exclusión M04 y M06:** **BLOQUEADO** (No existen filtros por `apto_para_ia` ni `apto_para_nic41` en los endpoints de M04 ni M06).

---

## B. Matriz de Trazabilidad de Endpoints y Subcasos

| ID Subcaso | Paso / Acción | Endpoint (Método + Ruta) | ¿Existe en TEST? | Rol Requerido | Resultado Esperado (Spec) | Comportamiento Actual (Código / TEST) | Viabilidad | Herramienta |
| :--- | :--- | :--- | :---: | :--- | :--- | :--- | :---: | :--- |
| **TC-M03-303** | Evaluar lectura virgen | `POST /iot/calidad/{id_telemetria}/evaluar` | **SÍ** | Admin (1), Ing (4) · `(38, 5)` | HTTP 201, `estado_evaluacion="VIGENTE"`, flags `apto_para_ia`/`apto_para_nic41` actualizados en RF-53, evento en bitácora RF-63. | Retorna HTTP 201, `TelemetriaCalidadSchema`. Actualiza `modulo3.telemetrias` y registra en `modulo3.bitacora_auditoria_iot`. | **EJECUTABLE CON AJUSTE** | Newman / Postman |
| **TC-M03-303 (Cons)** | Consultar evaluación creada | `GET /iot/calidad/{id_telemetria}` | **SÍ** | Admin, Prod, Vet, Ing, Cont · `(38, 2)` | HTTP 200, detalle idéntico al emitido en el POST. | Retorna HTTP 200 con la evaluación vigente. | **EJECUTABLE** | Newman / Postman |
| **TC-M03-318(a)** | Descuentos combinados (Outlier -20, Drift -10, Gap -10) | `POST /iot/calidad/{id_telemetria}/evaluar` | **SÍ** | Admin, Ing · `(38, 5)` | HTTP 201, índice 60, `APTO_CON_RESERVA`, `apto_ia=true`, `apto_nic41=false`, 3 flags activos. | Gap inactivo en código. Solo aplica Outlier (-20) y Drift (-10), arrojando índice 70 (`APTO_CON_RESERVA`). | **EJECUTABLE CON AJUSTE** | Newman con Oráculo JS |
| **TC-M03-318(b)** | Frontera inferior (Congelado MOD -35, Drift 15% -25) | `POST /iot/calidad/{id_telemetria}/evaluar` | **SÍ** | Admin, Ing · `(38, 5)` | HTTP 201, índice 40, `APTO_CON_RESERVA`, `apto_ia=true`, `apto_nic41=false`. | Código aplica Congelado MOD (-35) y Drift entre 10-20% (-25) $\rightarrow$ $100 - 60 = 40$. Coincide con spec. | **EJECUTABLE CON AJUSTE** | Newman con Oráculo JS |
| **TC-M03-318(c)** | Saturación en cero (Congelado CRIT -90, Outlier -20) | `POST /iot/calidad/{id_telemetria}/evaluar` | **SÍ** | Admin, Ing · `(38, 5)` | HTTP 201, $\Sigma = -110 \rightarrow \max(0, -10) = 0$, `NO_APTO`, ambos flags `false`. | Incompatibilidad matemática: si 20 lecturas son idénticas, $\sigma=0$ y el código no activa outlier. Queda en $100 - 90 = 10$. | **DEFECTO PROBABLE** | Newman con Oráculo JS |
| **TC-M03-319** | Lectura nominal sin anomalías | `POST /iot/calidad/{id_telemetria}/evaluar` | **SÍ** | Admin, Ing · `(38, 5)` | HTTP 201, índice 100, `APTO`, `apto_ia=true`, `apto_nic41=true`, cero flags activos. | Cero descuentos aplicados $\rightarrow$ índice 100, clasificación `APTO`, ambos flags `true`. | **EJECUTABLE** | Newman / Postman |
| **TC-M03-320** | NO_APTO combinado (Cong. MOD -35, Outlier -20, Gap -10) | `POST /iot/calidad/{id_telemetria}/evaluar` | **SÍ** | Admin, Ing · `(38, 5)` | HTTP 201, índice 35, `NO_APTO`, ambos flags `false`. Exclusión en M04 y M06. | Gap no implementado; contradicción congelado/outlier. M04/M06 no filtran por aptitud. | **DEFECTO PROBABLE / BLOQUEADO** | Newman / Postman |
| **TC-Bitácora** | Trazabilidad RF-63 | `POST /test-control/query` (o `GET /iot/auditoria`) | **SÍ** | Admin (1) | Registro en bitácora con `componente_origen='RF62'`, `clasificacion_registro='NIC41'`, `retencion_aplicable=5`. | `RegistrarEventoAuditoriaIotUseCase` inserta en `modulo3.bitacora_auditoria_iot`. `GET /iot/auditoria` no filtra por `entidad_afectada_id`. | **EJECUTABLE CON AJUSTE** | Query Sandbox en Teardown |
| **TC-Exclusión** | Exclusión M04 (IA) y M06 (Sanidad) | Consultas M04 / M06 | **NO** | N/A | Lecturas con `apto=false` son excluidas de modelos e historiales de patología. | No existen parámetros ni lógica en `src/prediction/` ni en `src/supplies/` para excluir lecturas por flags de telemetría. | **BLOQUEADO** | N/A |

---

## C. Motor de Cálculo: Análisis Detallado de Algoritmos y Reglas

Ubicación del motor: [`src/telemetry/application/use_cases/calidad/evaluar_calidad_telemetria_use_case.py`](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/src/telemetry/application/use_cases/calidad/evaluar_calidad_telemetria_use_case.py) y [`src/telemetry/domain/entities/telemetria_calidad.py`](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/src/telemetry/domain/entities/telemetria_calidad.py).

### 1. Detección de Outlier Estadístico (Fase 3, L149-L173)
* **Ventana:** $N=20$ lecturas previas (`SqlAlchemyTelemetriaRepository.obtener_serie_temporal` filtra por `timestamp_captura < ts` y `estado_calidad = 'LECTURA_VALIDA'`).
* **Inclusión de la lectura evaluada:** La lectura evaluada **NO entra** en el cálculo de $\mu$ ni $\sigma$. Solo se calcula sobre la serie previa de tamaño $N$.
* **Fórmula:** $|v - \mu| > k \times \sigma$, con $k=3.0$.
* **Tratamiento de $\sigma = 0$:**
  * En L152 se evalúa: `if sigma > 0 and abs(float(valor) - mu) > params.k * sigma:`.
  * **Comportamiento real:** Si $\sigma = 0$ (todas las lecturas previas idénticas), la condición evalúa a `False`. **No ocurre excepción de división por cero**, pero **tampoco se activa el flag de outlier estadístico**, salvo que el valor esté fuera de `_RANGOS_FISICOS` (L162-L172), en cuyo caso se activa por causa `LIMITE_FISICO`.

### 2. Detección de Sensor Congelado (Fase 2, L131-L148)
* **Ventana y Muestreo:** Toma las últimas $M=5$ lecturas de la serie previa (`serie[:params.M]`). Si las 5 son idénticas (`len(set(str(v) for v in ultimas_m)) == 1`), cuenta cuántas lecturas en toda la serie ($N=20$) repiten ese valor:
  * $\ge 20$ repeticiones: `severidad = 'CRITICO'` (descuento -90).
  * $\ge 10$ repeticiones: `severidad = 'MODERADO'` (descuento -35).
  * $< 10$ repeticiones: `severidad = 'LEVE'` (descuento -15).
* **Paradoja Lógica Outlier vs Congelado (TC-318c y TC-320):**
  * Si una lectura es idéntica a las últimas 10 o 20 ($v = \text{valor\_repetido}$), entonces $v \approx \mu$ y la desviación es nula. Es **matemáticamente imposible** que esa misma lectura sea outlier estadístico ($|v - \mu| > 3\sigma$).
  * Si la lectura evaluada salta a un valor drásticamente distinto para forzar el outlier ($v \gg \mu$), entonces esa lectura puntual **no está congelada** (rompe la congelación). Sin embargo, como el congelado se evalúa sobre la serie histórica previa (`serie[:params.M]`), **sí es posible activar ambos flags** si la serie histórica estuvo congelada en las últimas 5 lecturas ($M=5$) y la lectura evaluada es un pico extremo ($v = \mu + 4\sigma$).
  * **Caso Crítico TC-318(c):** El plan pide 20 repeticiones idénticas (toda la serie congelada $\rightarrow \sigma=0$) y que la lectura evaluada sea outlier. Al ser $\sigma=0$, el código no activa el outlier estadístico. Para activarlo requeriría que la lectura viole el rango físico absoluto ($< -40$ o $> 60$ para temperatura).

### 3. Detección de Deriva (Drift) (Fase 4, L174-L193)
* **Fórmula:**
  $$\text{val\_cal\_esperado} = \frac{1}{N} \sum_{i=1}^N (v_i \times \text{ganancia} + \text{offset})$$
  $$\text{media\_N} = \frac{1}{N} \sum_{i=1}^N v_i$$
  $$\text{magnitud\_drift\_pct} = \frac{|\text{media\_N} - \text{val\_cal\_esperado}|}{|\text{val\_cal\_esperado}|} \times 100$$
* **Activación del Flag:** Requiere que $\text{magnitud} > \text{umbral\_drift}$ (5.0%) y que al menos $P=3$ lecturas mantengan la misma dirección de desviación respecto a `val_cal_esperado`.
* **Cómo producir 7% y 15% de forma determinista:**
  * Si la serie de lecturas crudas tiene promedio $\mu = 20.0$ y ganancia $g = 1.0$:
    * Para 7% de drift: configurar $\text{offset} = 1.4$ ($\text{val\_cal\_esperado} = 21.4 \rightarrow |20 - 21.4| / 21.4 = 6.54\%$; o exactamente $\text{offset} = -1.308 \rightarrow 7.0\%$).
    * Para 15% de drift: configurar $\text{offset} = -2.608$ ($|20 - 17.39| / 17.39 = 15.0\%$).

### 4. Detección de Gap Temporal (Fase 5, L194-L198)
* **Estado en código:**
  ```python
  # ── Fase 5: Gap temporal ───────────────────────────────────────────────
  # La detección de gap temporal requiere el timestamp anterior; se omite
  # cuando la serie no tiene contexto suficiente. Aquí se marca si la
  # frecuencia_muestreo indica una anomalía ya detectada en la ingesta.
  ```
  **HALLAZGO CRÍTICO:** La Fase 5 no contiene código ejecutable. No evalúa `timestamp_captura - timestamp_anterior` ni activa `'gap_temporal_anomalo'` en el diccionario de `flags`. Por tanto, el descuento de -10 puntos por gap **nunca se aplica en la implementación actual**.

### 5. Tabla de Descuentos Real vs Plan

| Concepto / Flag | Descuento Especificación (Plan) | Descuento Implementación Real (`telemetria_calidad.py:24-29`) | Estado / Discrepancia |
| :--- | :---: | :---: | :--- |
| **Sensor Congelado LEVE** | -15 | -15 | Conforme |
| **Sensor Congelado MODERADO** | -35 | -35 | Conforme ($\ge 10$ repeticiones) |
| **Sensor Congelado CRÍTICO** | -90 | -90 | Conforme ($\ge 20$ repeticiones) |
| **Outlier Estadístico** | -20 | -20 | Conforme |
| **Posible Drift (<10%)** | -10 (5% a 10%) | -10 (`mag < 10`) | Conforme |
| **Posible Drift (10% a 20%)** | -25 (10% a 20%) | -25 (`10 <= mag <= 20`) | Conforme |
| **Posible Drift (>20%)** | -40 (>20%) | -40 (`mag > 20`) | Conforme |
| **Gap Temporal Anómalo** | -10 | -10 | Algoritmo de detección no implementado en el use case |

* **Fórmula de saturación:** `indice = max(0, 100 - sum(descuentos))` implementada en `telemetria_calidad.py:62`.
* **Umbrales de clasificación:**
  * $\ge 80 \rightarrow$ `APTO`
  * $40 \le \text{indice} < 80 \rightarrow$ `APTO_CON_RESERVA`
  * $< 40 \rightarrow$ `NO_APTO`
* **Derivación de Aptitud:**
  * `APTO`: `apto_para_ia = True`, `apto_para_nic41 = True`
  * `APTO_CON_RESERVA`: `apto_para_ia = True`, `apto_para_nic41 = False`
  * `NO_APTO` o `INDETERMINADA`: `apto_para_ia = False`, `apto_para_nic41 = False`

---

## D. Estrategia de Construcción de Series y Datos Dinámicos

### 1. Mecánica de Ingestión y Reglas Temporales
* **Endpoint de Ingestión:** `POST /iot/telemetria` (RF-53). Acepta `timestamp_captura` enviado por el cliente.
* **Restricciones de Timestamp:**
  * Máximo futuro tolerado: `ahora + 300 segundos` (`_MAX_DRIFT_FUTURO_SEG = 300`).
  * En `BUFFER_LOCAL`: hasta 72 horas en el pasado. En `TIEMPO_REAL`: no puede ser futuro.
* **Comportamiento de Autoevaluación en Ingestión:**
  * La ingestión ejecuta `evaluar_calidad_use_case.execute` inmediatamente en L267.
  * Si la serie previa tiene $< 20$ lecturas, la lectura nace evaluada con clasificación `INDETERMINADA`, `indice_calidad = None` y `estado_evaluacion = 'VIGENTE'`.
  * **Impacto en TC-303:** `POST /iot/calidad/{id_telemetria}/evaluar` **no rechaza** lecturas ya evaluadas; crea una nueva evaluación con `estado_evaluacion = 'VIGENTE'`, pero **no marca la anterior como SUPERADA** (esa lógica de superación solo la tiene `POST /iot/calidad/reevaluar`). Por tanto, ejecutar `evaluar` sobre una lectura existente funciona como reevaluación puntual idempotente.

### 2. Receta Paso a Paso por Escenario

#### Serie Base Común (20 Lecturas Previas para Estabilizar Ventana $N=20$):
* Se ingieren 20 lecturas con intervalos de 10 minutos hacia el pasado:
  $$t_i = \text{ahora} - (21 - i) \times 10\text{ minutos}, \quad i \in [1, 20]$$
* Valores base para sensor de temperatura (id_variable 9): $v_i \approx 20.0 \pm 0.2$ °C.

#### Escenario 1: TC-M03-303 (Happy Path de Evaluación Puntual)
1. Ingerir la lectura 21 con valor nominal $20.1$ °C.
2. Disparar `POST /iot/calidad/{{id_telemetria_21}}/evaluar`.
3. Validar HTTP 201, `indice_calidad = 100`, `clasificacion = "APTO"`.

#### Escenario 2: TC-M03-318(a) (Outlier + Drift 7% + Gap)
1. Sensor con calibración registrada: $\text{offset} = -1.308$, $\text{ganancia} = 1.0$ (produce drift $\approx 7.0\%$).
2. Serie base de 20 lecturas con $v_i = 20.0$ °C y pequeñas variaciones ($\sigma \approx 0.5$).
3. Lectura 21: valor extremo $v_{21} = 20.0 + 4 \times 0.5 = 22.0$ °C ($>3\sigma$).
4. Timestamp de lectura 21 con salto de 25 minutos respecto a lectura 20.
5. *Resultado Real Esperado:* Índice 70 (`APTO_CON_RESERVA`) debido a que el gap no aplica descuento en el backend actual.

#### Escenario 3: TC-M03-318(b) (Congelado MODERADO + Drift 15%)
1. Sensor con calibración registrada: $\text{offset} = -2.608$, $\text{ganancia} = 1.0$ (produce drift $\approx 15.0\%$).
2. Serie previa donde las últimas 10 lecturas son exactamente $20.00$ °C (congelado MODERADO).
3. Lectura 21: valor $20.00$ °C.
4. *Resultado Real Esperado:* Descuento Congelado MOD (-35) + Drift 10-20% (-25) $\rightarrow$ Índice 40 (`APTO_CON_RESERVA`).

#### Escenario 4: TC-M03-318(c) (Congelado CRÍTICO + Outlier por Límite Físico)
1. Serie previa donde las 20 lecturas son exactamente $20.00$ °C ($\sigma = 0$).
2. Para forzar el outlier sin división por cero, la lectura evaluada debe violar el límite físico ($v_{21} = 65.0$ °C, superior a 60 °C de temperatura ambiental).
3. *Resultado Real Esperado:* Congelado CRÍTICO (-90) + Outlier por límite físico (-20) $\rightarrow 100 - 110 = -10 \rightarrow \text{saturación en } 0$ (`NO_APTO`).

#### Escenario 5: TC-M03-319 (APTO Nominal)
1. Serie base normal de 20 lecturas entre 19.8 y 20.2 °C. Calibración nominal ($g=1.0, \text{offset}=0.0$).
2. Lectura 21 con $20.0$ °C.
3. *Resultado Real Esperado:* Índice 100, `APTO`, `apto_para_ia = true`, `apto_para_nic41 = true`.

#### Escenario 6: TC-M03-320 (NO_APTO Combinado)
1. Serie con 10 repeticiones (congelado MOD -35) + lectura 21 que viola límite físico (-20).
2. *Resultado Real Esperado:* $100 - 55 = 45$ (con gap ausente sería 45 `APTO_CON_RESERVA`). Si el backend implementara gap (-10), daría 35 `NO_APTO`.

---

## E. Precondiciones, Descubrimiento Dinámico y Política Anti-Hardcode

Para cumplir estrictamente la **política anti-hardcode**, el script no utilizará ningún ID estático. Toda entidad se descubrirá en la fase de **Preflight**:

```javascript
// Estructura del bloque centralizado SPEC (Único lugar de constantes normativas)
const spec = {
    rf: "RF-62",
    version_fase: "Fase 6",
    descuentos: {
        sensor_congelado: { LEVE: 15, MODERADO: 35, CRITICO: 90 },
        outlier_estadistico: 20,
        drift_tramo_bajo: 10,   // < 10%
        drift_tramo_medio: 25,  // 10% - 20%
        drift_tramo_alto: 40,   // > 20%
        gap_temporal: 10
    },
    umbrales_clasificacion: {
        apto_min: 80,
        apto_con_reserva_min: 40,
        no_apto_max: 39
    },
    parametros_estadisticos: {
        N_min: 20,
        M_congelado_base: 5,
        k_desviacion: 3.0,
        umbral_drift_pct: 5.0,
        P_consistencia: 3
    }
};
```

### Fuentes Dinámicas de Datos:
1. **Credenciales y Tokens:** Se obtienen dinámicamente mediante `POST /sesiones/` con `$env:TEST_ADMIN_PASSWORD` para `administador.dev@gmail.com`.
2. **Descubrimiento de Dispositivo y Sensor Activo:**
   * Llamar a `GET /configuracion/dispositivos-iot` para obtener un dispositivo en estado `ACTIVO` que posea al menos un sensor de tipo ambiental (`TEMPERATURA_AMBIENTAL`).
   * La `access_key` requerida por `POST /iot/telemetria` es el campo `serial` del dispositivo IoT (`DispositivoM09Adapter.py:31`).
3. **Calibración:**
   * En lugar de alterar la BD con scripts SQL fijos, se utiliza `POST /configuracion/sensores/{id_sensor}/calibrar` con el DTO validado (`modo_calibracion: "SENSOR"`, `ganancia`, `offset`).
4. **Capacidad de `/test-control/query`:**
   * El endpoint **SOLO ACEPTA SELECT**. Rechaza estrictamente cualquier sentencia que no comience por `SELECT` o que contenga punto y coma (`;`). Por tanto, **no se pueden ejecutar INSERT ni UPDATE** a través de este endpoint.

---

## F. Seguridad, Sandbox y Verificación de Efectos Colaterales

### 1. Comportamiento del Sandbox (`X-Test-Run-Id`)
* Tanto `POST /iot/telemetria` como `POST /iot/calidad/{id_telemetria}/evaluar` resuelven la sesión de base de datos a través de `get_db` / `get_db_sistema`.
* En presencia de `X-Test-Run-Id` y `X-Sandbox-Secret`, `get_db` extrae la conexión aislada de `testing_sandbox.py` (Savepoint transaccional).
* **Confirmación de Inocuidad:** Aunque el código ejecute `self.db.commit()`, SQLAlchemy opera en modo `join_transaction_mode="create_savepoint"`, de modo que el commit solo cierra el SAVEPOINT interno. Al emitir `DELETE /test-control/runs/{run_id}`, se ejecuta un `ROLLBACK` completo de la conexión externa, dejando la base de datos **100% limpia sin registros residuales**.

### 2. Verificación de Efectos Colaterales
* **RF-53 (Lectura en `modulo3.telemetrias`):**
  * `EvaluarCalidadTelemetriaUseCase` actualiza `apto_para_ia` y `apto_para_nic41` en la fila de telemetría (L217).
  * *Vía de verificación:* `POST /test-control/query` con `SELECT apto_para_ia, apto_para_nic41 FROM modulo3.telemetrias WHERE id_telemetria = :id`.
* **RF-63 (Bitácora de Auditoría IoT):**
  * Registra evento con `componente_origen = 'RF62'`, `tipo_evento = 'EVALUACION_CALIDAD_COMPLETADA'`, `clasificacion_registro = 'NIC41'`, `retencion_aplicable = 5`.
  * *Vía de verificación:* `POST /test-control/query` con `SELECT tipo_evento, componente_origen, clasificacion_registro, retencion_aplicable FROM modulo3.bitacora_auditoria_iot WHERE entidad_afectada_id = :id`.
* **M04 y M06 (Exclusión por `apto=false`):**
  * **BLOQUEADO.** Ningún router ni use case en `src/prediction/` ni en `src/supplies/` implementa filtros ni consultas sobre estas banderas.

---

## G. Riesgos, Discrepancias Spec vs Implementación y Defectos Probables

### 1. [DISCREPANCIA / DEFECTO] Fase 5 de Gap Temporal Inactiva
* **Evidencia:** `evaluar_calidad_telemetria_use_case.py:194-198`.
* **Impacto:** Subcasos TC-M03-318(a) y TC-M03-320 no activarán el flag `gap_temporal_anomalo` ni descontarán los 10 puntos, alterando el índice final calculado por la API respecto al valor esperado en la especificación.

### 2. [DISCREPANCIA LÓGICA] Contradicción Outlier + Congelado con $\sigma=0$
* **Evidencia:** `evaluar_calidad_telemetria_use_case.py:152`.
* **Impacto:** En TC-M03-318(c), si las 20 lecturas previas son idénticas, $\sigma=0$. El motor no ejecuta la rama de outlier estadístico. El caso obtendrá índice 10 en lugar de 0, a menos que se fuerce un valor fuera del rango físico absoluto.

### 3. [PARÁMETRO DESINCRONIZADO] Valor de $P$ para Drift
* **Evidencia:** El plan especifica $P=5$ lecturas en la misma dirección; el código en `ParametrosCalidadStubAdapter.py:20` fija `P=3`.

### 4. [PRESUPUESTO DE TIEMPO VS TIMEOUT 180s]
* La construcción de series mediante 20+ peticiones individuales de telemetría por cada subcaso (6 subcasos $\times 21 = 126$ peticiones) a ~200 ms por petición tomaría $> 25$ segundos por subcaso.
* **Riesgo:** Si se corre toda la suite bajo un único `run_id`, cualquier retraso acumulado o pausa puede rozar los 180 segundos del temporizador de inactividad de `testing_sandbox.py`.
* **Recomendación:** Se recomienda **un `run_id` independiente por subcaso** o correr los subcasos modulares por separado para garantizar aislamiento y evitar timeouts de sandbox.

---

## H. Preguntas Abiertas y Decisiones Requeridas del Equipo

1. **Definición sobre Gap Temporal:** ¿Se reportará como defecto de implementación la ausencia del algoritmo de gap temporal en Fase 5, o se ajustará temporalmente la expectativa del test a $100 - (\text{outlier} + \text{drift})$?
2. **Tratamiento del Subcaso 318(c):** Para verificar saturación en 0, ¿se aprueba alterar la lectura evaluada para que sea físicamente imposible (ej: temperatura de 75 °C) de modo que active outlier por `LIMITE_FISICO` a pesar de $\sigma=0$?
3. **Exclusión M04 y M06:** Dado que M04 y M06 no tienen endpoints que consuman estas banderas actualmente, ¿se confirma dejar formalmente en estado **BLOQUEADO (SKIP)** la verificación de exclusión externa?
4. **Herramienta de Ejecución:** Debido a la necesidad de ingerir 20 lecturas cronológicas para cada subcaso, ¿se prefiere una colección **Newman modular** con preflight dinámico o un script **Pytest de integración** (`tests/integration/`) utilizando la fixture `sandbox_client`?

---

## I. Propuesta Preliminar de Estructura de la Colección (Newman)

### Variables de Colección Propuestas:
* `baseUrl`: `https://api.inmero.co/back-sigab-test`
* `admin_email`: `administador.dev@gmail.com`
* `admin_password`: `{{$env:TEST_ADMIN_PASSWORD}}`
* `sandbox_secret`: `{{$env:TEST_SANDBOX_SECRET}}`
* `run_id`: `""` (generado en Pre-request con `test-{{$guid}}`)
* `device_id`: `null` (descubierto dinámicamente)
* `sensor_id`: `null` (descubierto dinámicamente)
* `access_key`: `null` (serial del dispositivo descubierto)
* `id_infraestructura`: `null` (descubierto dinámicamente)
* `spec`: Objeto JSON con constantes normativas inmutables.

### Flujo de Requests Planificado:
1. `NW-01-Auth-Admin`: Iniciar sesión administrativa y capturar JWT.
2. `NW-02-Preflight-Descubrir-Dispositivo`: Consultar `GET /configuracion/dispositivos-iot` para aislar hardware activo.
3. `NW-03-TC303-Ingestar-Serie-Base`: 20 requests `POST /iot/telemetria` para inicializar ventana $N=20$.
4. `NW-04-TC303-Ingestar-Lectura-Evaluar`: Ingestar lectura 21.
5. `NW-05-TC303-Ejecutar-Evaluacion`: `POST /iot/calidad/{id_telemetria}/evaluar` (Aserción 201, índice 100, APTO).
6. `NW-06-TC303-Verificar-GET`: `GET /iot/calidad/{id_telemetria}`.
7. `NW-07-TC303-Auditoria-BD`: `POST /test-control/query` verificando banderas en `telemetrias` y evento en `bitacora_auditoria_iot`.
8. `NW-08-TC318a-Calibrar-Drift`: `POST /configuracion/sensores/{id_sensor}/calibrar` con offset ajustado.
9. `NW-09-TC318a-Ingestar-Y-Evaluar`: Ingestar y disparar evaluación (Aserción dual índice 70 real / 60 spec).
10. `NW-10-TC318b-Ingestar-Congelado-Y-Evaluar`: Ingestar repeticiones y evaluar (Aserción índice 40).
11. `NW-11-TC318c-Ingestar-Saturacion-Y-Evaluar`: Evaluar saturación cero.
12. `NW-12-TC319-Ingestar-Nominal-Y-Evaluar`: Evaluar serie limpia (Aserción índice 100).
13. `NW-13-Teardown-Rollback-Sandbox`: `DELETE /test-control/runs/{{run_id}}` (Aserción HTTP 200 Rollback exitoso).
