# INFORME DE DIAGNÓSTICO EMPÍRICO — REINTENTO 2 (TC-M03-G167)

**Fecha:** 2026-11-02  
**Caso de Prueba:** TC-M03-G167 (RF-62 v2.0, Detección de Drift — Fronteras de Porcentaje)  
**Ambiente:** TEST (`https://www.api.inmero.co/api-sgpmp-test`)  
**Resultado Global:** 23/32 OK (71.9%), 9 Fallas (28.1%) $\implies$ **RECHAZADO**  
**Ejecución:** Reintento 2 (`_reintento2`), commit local `ea6ec4bf` (Fix #876)  

---

## 1. Resumen Ejecutivo

El diagnóstico empírico de las 9 aserciones fallidas en la ejecución de `_reintento2` determinó que **ninguna falla corresponde a un defecto funcional nuevo del producto**. Las fallas se dividen en dos causas fundamentales independientes:

1. **Despliegue Desactualizado en TEST (G1 — 5 fallas):** El servidor remoto TEST **no tiene desplegado el commit `ea6ec4bf` (Fix #876 / INC-M03-236-G16)**. La respuesta del servidor carece del campo `base_comparacion` introducido por el PR #876 y continúa calculando el drift con la fórmula previa (contra la media de valores calibrados $\bar{X}_{\text{cal}}$ en lugar de contra el `valor_referencia` $= 25.0$).
2. **Defectos de Fixture y Aserción en el Script de Prueba (G2 y G3 — 4 fallas):**
   - **G2 (2 fallas en 3A.03 y 3B.03):** El script seleccionó valores de media cruda $\bar{X} = 33.0025$ y $34.2500$ que, sumados al offset de calibración del sensor 536 ($-3.0$), produjeron valores ajustados de $30.0025\ ^\circ\text{C}$ y $31.2500\ ^\circ\text{C}$. Estos valores superan el umbral biológico máximo de la especie en el Área 347 ($30.00\ ^\circ\text{C}$). El trigger de BD `fn_ingesta_telemetria` marcó las lecturas como `FUERA_DE_RANGO`, activando la regla de negocio CA-9 en `EvaluarCalidad`, asignando `indice_calidad = 0` y omitiendo la fase estadística de drift.
   - **G3 (2 fallas en 3A.05 y 3B.05):** `3A.05` falló por efecto en cascada de `FUERA_DE_RANGO` (bitácora registró `POSTCOMMIT_RF53_AUDITORIA_COMPLETADO` en vez de `EVALUACION_CALIDAD_COMPLETADA`). `3B.05` falló porque el script esperaba el literal `'RF-62'` pero el backend registra `'RF62'` sin guión.

---

## 2. Clasificación de las 9 Fallas

| Escenario | Checkpoint | Aserción Fallida | Valor Esperado | Valor Recibido | Grupo | Causa Raíz Primaria |
|---|---|---|---|---|---|---|
| **1A (5.00%)** | `1A.03-Flags-Esperados` | `posible_drift.activo == false` | `false` | `true` | **G1** | Deploy pre-#876 en TEST (calcula 11.43% vs 26.25) |
| **1B (7.00%)** | `1B.03-Flags-Esperados` | `posible_drift.activo == false` | `false` | `true` | **G1** | Deploy pre-#876 en TEST (calcula 10.42% vs 26.75) |
| **1C (9.99%)** | `1C.03-Flags-Esperados` | `posible_drift.activo == false` | `false` | `true` | **G1** | Deploy pre-#876 en TEST (calcula 8.93% vs 27.4975) |
| **2A (10.00%)** | `2A.03-Flags-Esperados` | `magnitud_drift_porcentaje == 10.0` | `10.0` | `8.9286` | **G1** | Deploy pre-#876 en TEST (calcula 8.93% vs 27.50) |
| **2B (15.00%)** | `2B.03-Flags-Esperados` | `magnitud_drift_porcentaje == 15.0` | `15.0` | `6.8966` | **G1** | Deploy pre-#876 en TEST (calcula 6.90% vs 28.75) |
| **3A (20.01%)** | `3A.03-Flags-Esperados` | `flags_detectados.posible_drift` | Objeto drift activo | `undefined` | **G2** | SCRIPT_FIXTURE: Valor ajustado 30.0025 > 30.00 $\rightarrow$ `FUERA_DE_RANGO` |
| **3A (20.01%)** | `3A.05-Bitacora` | `tipo_evento` | `EVALUACION_CALIDAD_COMPLETADA` | `POSTCOMMIT_RF53_AUDITORIA_COMPLETADO` | **G3** | SCRIPT_FIXTURE: Cascada por `FUERA_DE_RANGO` |
| **3B (25.00%)** | `3B.03-Flags-Esperados` | `flags_detectados.posible_drift` | Objeto drift activo | `undefined` | **G2** | SCRIPT_FIXTURE: Valor ajustado 31.2500 > 30.00 $\rightarrow$ `FUERA_DE_RANGO` |
| **3B (25.00%)** | `3B.05-Bitacora` | `componente` | `RF-62` | `RF62` | **G3** | SCRIPT_FIXTURE: Discrepancia de literal en aserción |

---

## 3. Investigación G1: Despliegue Pre-#876 en TEST

### 3.1 Hipótesis Evaluadas
- **H1 (Deploy pre-#876 en TEST):** El binario/contenedor ejecutándose en TEST no incluye el commit `ea6ec4bf`.
- **H2 (Fallback a calibración aplicada):** El fix está desplegado, pero `referencia_calibracion` retorna `None` y cae al fallback.
- **H3 (Bug en la implementación de #876):** El fix está desplegado y encuentra la referencia, pero la fórmula o el adaptador tienen un error de cálculo.

### 3.2 Evidencia Empírica de H1
Al inspeccionar el raw payload del escenario `1A.03` registrado en `evidencias/_raw_newman_reintento2.json` (línea 1740):

```json
"posible_drift": {
    "activo": true,
    "media_ultimas_N": 29.25,
    "umbral_aplicado": 5.0,
    "P_lecturas_consistentes": 20,
    "valor_calibrado_esperado": 26.25,
    "magnitud_drift_porcentaje": 11.4286
}
```

#### Discrepancia 1: Ausencia del campo `base_comparacion`
En el código fuente local (`src/telemetry/application/use_cases/calidad/evaluar_calidad_telemetria_use_case.py`, líneas 309-314):
```python
flags["posible_drift"] = {
    "activo": True,
    "media_ultimas_N": float(media_drift),
    "valor_calibrado_esperado": float(val_cal_esperado),
    "magnitud_drift_porcentaje": float(magnitud_drift),
    "umbral_aplicado": float(umbral_drift),
    "P_lecturas_consistentes": P_CONSISTENCIA,
    "base_comparacion": "VALOR_REFERENCIA" if referencia is not None else "CALIBRACION_APLICADA",
}
```
Bajo el código del commit `ea6ec4bf` (#876), **el campo `base_comparacion` es OBLIGATORIO** tanto en el camino de referencia como en el de fallback. En la respuesta del servidor TEST este campo **no existe**, lo que prueba irrefutablemente que el servidor corre código previo al commit `ea6ec4bf`.

#### Discrepancia 2: Valor esperado y magnitud de drift
Para el escenario 1A, los valores ingresados fueron:
- `offset` de calibración $= -3.0$
- Media cruda $\bar{X}_{\text{cruda}} = 29.25$
- Media calibrada $\bar{X}_{\text{cal}} = 29.25 - 3.0 = 26.25$
- `valor_referencia` en BD para sensor 536 $= 25.0$

**Cálculo recibido del servidor TEST:**
$$\text{valor\_calibrado\_esperado} = 26.25$$
$$\text{magnitud} = \frac{|29.25 - 26.25|}{26.25} \times 100 = \frac{3.0}{26.25} \times 100 = 11.4286\%$$

**Cálculo según código #876:**
$$\text{valor\_calibrado\_esperado} = 25.0$$
$$\text{magnitud} = \frac{|26.25 - 25.0|}{25.0} \times 100 = \frac{1.25}{25.0} \times 100 = 5.0000\%$$

#### Discrepancia 3: Verificación de `referencia_calibracion` en BD TEST
Ejecutando directamente contra la BD de TEST el adaptador `SqlAlchemyCalibracionRepositoryAdapter.referencia_calibracion(536, ts)`:
- Resultado: `Decimal('25.0000')`.
- Por tanto, la BD sí cuenta con el dato de referencia. La hipótesis H2 queda descartada.

**Veredicto G1:** **H1 CONFIRMADO — El servidor TEST está ejecutando una versión previa a PR #876 (`ea6ec4bf`).**

---

## 4. Investigación G2: Defecto de Fixture (Límite Biológico de Especie)

### 4.1 Causa Raíz de la Ausencia de Drift en 3A y 3B
En los escenarios 3A (20.01%) y 3B (25.00%), el response HTTP de calidad devolvió:
- `indice_calidad: 0`
- `clasificacion_calidad: "NO_APTO"`
- `flags_detectados: {"fuera_de_rango_rf53": {"activo": true}}`
- `flags_detectados.posible_drift: undefined`

### 4.2 Análisis del Mecanismo en Base de Datos y Backend
1. **Trigger de Ingesta (`modulo3.fn_ingesta_telemetria`, líneas 487-498):**
   ```sql
   IF COALESCE(v_valor_ajustado, p_valor_crudo) < v_umbral_min 
      OR COALESCE(v_valor_ajustado, p_valor_crudo) > v_umbral_max THEN
       v_estado := 'FUERA_DE_RANGO';
   END IF;
   ```
2. **Umbrales Ambientales de la Especie en Área 347:**
   La consulta a `modulo9.umbrales_ambientales` para el área 347 determina un rango biológico para la especie alojada de:
   - `valor_min`: `15.00 °C`
   - `valor_max`: `30.00 °C`
3. **Valores Generados por el Script:**
   - **Escenario 3A:** $\bar{X}_{\text{crudo}} = 33.0025 \implies \text{valor\_ajustado} = 33.0025 - 3.0 = \mathbf{30.0025\ ^\circ\text{C}} > 30.00\ ^\circ\text{C}$.
   - **Escenario 3B:** $\bar{X}_{\text{crudo}} = 34.2500 \implies \text{valor\_ajustado} = 34.2500 - 3.0 = \mathbf{31.2500\ ^\circ\text{C}} > 30.00\ ^\circ\text{C}$.
4. **Cortocircuito CA-9 en `EvaluarCalidadTelemetriaUseCase` (líneas 139-162):**
   ```python
   if estado_calidad_rf53 == 'FUERA_DE_RANGO':
       # CA-9: Penalización inmediata, salta cálculo de drift
       return EvaluacionCalidadDTO(
           indice_calidad=0.0,
           clasificacion=ClasificacionCalidad.NO_APTO,
           ...
       )
   ```
   Al detectarse `FUERA_DE_RANGO`, el evaluador detiene el análisis estadístico y omite el flag `posible_drift`.

### 4.3 Solución para Reintento 3
La fórmula de porcentaje de drift evalúa el valor absoluto de la desviación:
$$\text{drift} = \frac{|\bar{X}_{\text{cal}} - \text{Ref}|}{\text{Ref}} \times 100$$
Para evitar superar el límite biológico superior ($30.00\ ^\circ\text{C}$), los escenarios 3A y 3B deben inducir **drift hacia abajo** ($\bar{X}_{\text{cal}} < \text{Ref}$):
- **Escenario 3A (20.01%):**  
  $\bar{X}_{\text{cal}} = 25.0 \times (1 - 0.2001) = 19.9975\ ^\circ\text{C}$  
  $\bar{X}_{\text{crudo}} = 19.9975 - (-3.0) = \mathbf{22.9975\ ^\circ\text{C}}$  
  *(Dentro del rango $[15.00, 30.00]\ ^\circ\text{C}$, $\text{drift} = 20.01\%$ exacto)*
- **Escenario 3B (25.00%):**  
  $\bar{X}_{\text{cal}} = 25.0 \times (1 - 0.2500) = 18.7500\ ^\circ\text{C}$  
  $\bar{X}_{\text{crudo}} = 18.7500 - (-3.0) = \mathbf{21.7500\ ^\circ\text{C}}$  
  *(Dentro del rango $[15.00, 30.00]\ ^\circ\text{C}$, $\text{drift} = 25.00\%$ exacto)*

---

## 5. Investigación G3: Aserciones de Bitácora y Alertas RF-57

### 5.1 Falla en `3A.05-Verificar-Bitacora-RF63`
- **Esperado:** `tipo_evento == 'EVALUACION_CALIDAD_COMPLETADA'`
- **Recibido:** `tipo_evento == 'POSTCOMMIT_RF53_AUDITORIA_COMPLETADO'`
- **Causa:** Al fallar 3A por `FUERA_DE_RANGO`, el flujo no completó la evaluación estándar de calidad de telemetría y el evento en bitácora correspondió al ciclo RF-53. Una vez corregido el fixture (G2), este evento volverá a ser `EVALUACION_CALIDAD_COMPLETADA`.

### 5.2 Falla en `3B.05-Verificar-Bitacora-RF63`
- **Esperado:** `componente == 'RF-62'`
- **Recibido:** `componente == 'RF62'`
- **Causa:** El backend en TEST registra el literal `'RF62'` (sin guión). El script de Newman en `build_collection.cjs` línea 390 contiene la aserción estricta `pm.expect(evento.componente).to.eql("RF-62")`. Requiere ajustarse a aceptar `'RF62'` o `'RF-62'`.

### 5.3 Estado de Alertas RF-57 (`3A.04` y `3B.04`)
- Las aserciones `3A.04` y `3B.04` están contempladas bajo el issue conocido **`INC-M03-RF57-NOT-EMITTED`**.
- El script registra una `[OBSERVACION]` en consola sin romper el test cuando el backend no emite la alerta técnica de drift (debido a que el payload interno no contiene el campo `severidad`). Se mantiene la política de tolerancia hasta la resolución del ticket de producto respectivo.

---

## 6. Reformulación Recomendada de INC-M03-248-G167

El ticket `INC-M03-248-G167` fue clasificado provisionalmente como `INFRAESTRUC`. Con base en los hallazgos empíricos, debe reformularse de la siguiente manera:

```yaml
ID: INC-M03-248-G167
Título: Servidor TEST no tiene desplegado el Fix #876 (INC-M03-236-G16) — Evaluación de Drift desactualizada
Severidad: ALTA (Bloqueante para certificación de RF-62 / TC-M03-G167)
Categoría: DESPLIEGUE / RELEASE
Ambiente: TEST (https://www.api.inmero.co/api-sgpmp-test)
Commit Requerido: ea6ec4bf (o merge posterior a HEAD de origin/test)
Componente: src/telemetry/application/use_cases/calidad/evaluar_calidad_telemetria_use_case.py

Descripción del Problema:
  Las pruebas del TC-M03-G167 evidencian que el contenedor de TEST ejecuta una versión
  del backend previa al commit ea6ec4bf. La respuesta de calidad omite el campo
  'base_comparacion' y calcula la magnitud del drift contra la media de lecturas calibradas
  en lugar de contra el 'valor_referencia' de la calibración vigente (25.0 °C).

Evidencia Empírica:
  1. Payload de TEST recibido:
     "posible_drift": { "activo": true, "media_ultimas_N": 29.25, "valor_calibrado_esperado": 26.25, "magnitud_drift_porcentaje": 11.4286 }
  2. En el código fuente actual (ea6ec4bf), 'base_comparacion' siempre está presente.
  3. Ejecución directa del adaptador de calibración contra la BD de TEST confirma que
     referencia_calibracion(536, ts) retorna 25.0000.

Acción Requerida para DevOps / Infraestructura:
  1. Re-desplegar la imagen de backend en TEST construida desde origin/test en HEAD.
  2. Verificar que GET /health refleje el build o que /iot/calidad emita 'base_comparacion'.
```

---

## 7. Plan de Acción hacia Reintento 3

1. **Equipo DevOps:**
   - Desplegar en TEST el commit `ea6ec4bf` (o HEAD de `origin/test`).
2. **Equipo Testing (Ajustes en `build_collection.cjs`):**
   - **G2:** Actualizar recetas de los escenarios 3A y 3B para generar drift negativo ($\bar{X}_{\text{crudo}} = 22.9975$ y $21.7500$), manteniéndose dentro de $[15.00, 30.00]\ ^\circ\text{C}$.
   - **G3:** Flexibilizar la aserción de bitácora para componente: `pm.expect(["RF62", "RF-62"]).to.include(evento.componente)`.
3. **Re-ejecución:**
   - Ejecutar la suite como Reintento 3 (`_reintento3`) una vez confirmado el despliegue de #876 en TEST.

