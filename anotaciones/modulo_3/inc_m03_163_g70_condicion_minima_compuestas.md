# INC-M03-163-G70 — Condición mínima de las reglas compuestas en POST /iot/alertas (TC-M03-G70, G71, G72)

**RF:** RF-57, Fase 5 (reglas compuestas: condiciones de activación completas), E14 y E15. **Issue:** #741.
**Depende de:** INC-M03-162-G68 (#740). Esta rama parte de la de G68 y su PR apunta a esa rama.
**Estado:** corregido y verificado con PostgreSQL real.

## Causa

El backend tomaba el tipo de alerta del mapa variable → tipo (`TEMPERATURA_AMBIENTAL` y `HUMEDAD_RELATIVA`
→ ESTRES_TERMICO; `PH_AGUA`, `TDS` y `OXIGENO_DISUELTO` → RIESGO_HIDRICO) y aceptaba `reglas_activadas`
tal como llegaba. Nunca comprobaba que la regla compuesta se hubiera activado según el RF. Eso producía
alertas compuestas falsas, con los destinatarios y las acciones de la compuesta.

## Condición mínima (RF-57 Fase 5)

| Compuesta | Variables requeridas | Condición mínima de activación | Implementación |
|---|---|---|---|
| **ESTRES_TERMICO** | temperatura_ambiental + humedad_relativa | THI en LEVE o más (≥ 72) | Usa el THI de `correlacion_variables`. Si no llega, lo calcula con la temperatura y la humedad (la del evento y la de la correlación) con la fórmula **NRC**. Sin las dos variables ni THI, la condición no se cumple |
| **RIESGO_HIDRICO** | pH_agua + TDS (oxígeno disuelto es complementario) | pH fuera de rango LEVE **o** TDS en LEVE o superior | Usa el valor del evento si la variable es pH o TDS; si no, el de la correlación |

**THI con la fórmula NRC:** `(1.8·T + 32) − (0.55 − 0.0055·HR)·(1.8·T − 26)`, con T en °C. Es la escala de
los umbrales 72/79/84 del RF y la que usa QA (24.4 °C con 60 % da **71.98**, el valor de TC-M03-G72). La
fórmula escrita en RF-57 es la variante en °C y nunca llega a 72; ver la decisión 1 de G68.

## Comportamiento (solo `POST /iot/alertas`, `origen_evento` distinto de IA)

Decisión del equipo, ya que el RF no define el tipo de una alerta simple:

| Situación | Respuesta | Bitácora RF-63 |
|---|---|---|
| El evento **declara** una compuesta en `reglas_activadas` (texto u objeto `{id, nombre}`) y no cumple su condición mínima | **422 `EVENTO_INCOHERENTE_REGLA_COMPUESTA`** (`field: reglas_activadas`) | `EVENTO_INCOHERENTE_REGLA_COMPUESTA`, con el motivo |
| La variable **solo genera** una compuesta (no hay otro tipo) y su condición mínima no se cumple | **422 `REGLA_COMPUESTA_NO_ACTIVADA`** (`field: correlacion_variables`) | `REGLA_COMPUESTA_NO_ACTIVADA`, con el motivo |
| Valor en banda NORMAL (G68) | 201 sin alerta | `EVENTO_SIN_DESVIACION_RF57` |
| Condición cumplida | 201 con la alerta compuesta; severidad de G68 | — |

Orden de la evaluación: FALLO_AMBIENTAL (G68) → banda NORMAL (G68) → severidad por valor (G68) →
**condición mínima (G70)** → deduplicación y creación.

## Decisiones y puntos para Análisis

1. **Tipo de las alertas simples.** RF-57 Fase 5 define reglas simples con severidad propia, y E14 dice
   que, sin compuesta aplicable, "se genera una alerta independiente por cada variable". Pero **no dice
   qué `tipo_alerta` lleva**, y `enum_tipo_alerta` solo tiene tipos compuestos. Por decisión del equipo,
   un evento que no activa su compuesta se **rechaza con 422**, sin crear un falso positivo.
   **Consecuencia:** una lectura simple aislada, aunque sea CRITICO, no genera alerta. Por ejemplo, una
   temperatura en CRITICO sin humedad, o un frío extremo con THI < 72. Hay que definir un tipo para las
   alertas simples (eso implica un valor nuevo en el enum, con migración y aprobación del DBA).
2. **Contrato con el Edge y el broker.** Para que haya una alerta ESTRES_TERMICO, el evento de temperatura
   o de humedad debe traer la otra variable (o el THI) en `correlacion_variables`. Para RIESGO_HIDRICO, un
   evento de oxígeno debe traer pH o TDS. Formato: el de G68 (`{"HUMEDAD_RELATIVA": 75}`, `{"THI": 79.1}`,
   `{"PH_AGUA": 6.4}`).
3. **Otras compuestas.** El ticket nombra ESTRES_TERMICO y RIESGO_HIDRICO. Hay casos análogos sin validar:
   - **SINDROME_RESPIRATORIO:** requiere frecuencia respiratoria y temperatura corporal; NH3 y CO2 son
     complementarios, pero un evento de NH3 o CO2 aislado hoy da ese tipo.
   - **FIEBRE:** la frecuencia cardíaca aislada, que es complementaria, da FIEBRE, y la hipotermia
     (< 36.5 °C) también, aunque la condición es > 40 °C.

   Quedan anotados para una tarea aparte. El mecanismo (`condicion_minima`) ya admite agregarlas.

## Cambios

- `src/telemetry/domain/entities/reglas_base_rf57.py`: `calcular_thi` (NRC), `_thi` (el THI recibido
  prevalece), `condicion_minima`, `compuestas_declaradas` y `COMPUESTAS_VALIDADAS`.
- `generar_alerta_use_case.py`: `_validar_condicion_minima`, que registra en la bitácora y lanza 422.
- Pruebas actualizadas, sin relajar ninguna aserción:
  - `test_inc_m03_162_g68_severidad_alertas_rf57.py`: los casos de severidad envían la condición mínima
    de su compuesta. El caso de frío (13.9 °C) sale de ahí: ahora es 422 (decisión 1).
  - `test_dev49_alertas_historial_auditoria.py`: el evento de 38.5 °C lleva la humedad (THI 91.77).

## Evidencia

**Pruebas unitarias.** `tests/telemetry/test_inc_m03_163_g70_condicion_minima.py`, sin BD: THI NRC (71.98,
83.70 y 71.74), la condición mínima de cada compuesta (bordes 71.99 y 72, TDS 1000 y 1001, pH normal),
las compuestas no validadas y las declaradas como texto u objeto.

**Pruebas de integración.** `tests/integration/test_inc_m03_163_g70_condicion_minima_compuestas.py`:
router real, M09 y PostgreSQL real.

| Caso de QA | Prueba | Resultado |
|---|---|---|
| G70: oxígeno disuelto 4.0 aislado | `test_oxigeno_aislado_no_activa_riesgo_hidrico` | 422 `REGLA_COMPUESTA_NO_ACTIVADA`, sin alerta, con registro en la bitácora |
| G70: oxígeno con pH 6.4 o TDS 1200 | `test_oxigeno_con_ph_o_tds_en_leve_activa_riesgo_hidrico` | 201 RIESGO_HIDRICO LEVE |
| G70: pH o TDS por sí mismos | `test_ph_o_tds_cumplen_la_condicion_por_si_mismos` | 201 RIESGO_HIDRICO |
| G70: temperatura o humedad sin la otra | `test_variable_de_estres_termico_sin_la_otra_no_activa_la_compuesta` | 422 |
| G71: 31 °C con `[ESTRES_TERMICO]` sin humedad (texto u objeto) | `test_temperatura_que_declara_estres_termico_sin_humedad_es_incoherente`, `test_declaracion_como_objeto_tambien_se_valida` | 422 `EVENTO_INCOHERENTE_REGLA_COMPUESTA` |
| G71: 31 °C con humedad 75 % que declara bien | `test_temperatura_con_humedad_declara_bien_la_compuesta` | 201 ESTRES_TERMICO **MODERADO** (THI 83.70) |
| G71: declara RIESGO_HIDRICO en un evento de temperatura | `test_compuesta_declarada_distinta_de_la_variable_se_valida` | 422 |
| G72: 24.4 °C con 60 % (THI 71.98) | `test_thi_normal_con_temperatura_normal_no_genera_alerta` | 201 sin alerta |
| G72: THI < 72 con temperatura en LEVE (THI 71.98 recibido, o 31 °C con 2 %) | `test_thi_bajo_72_no_activa_estres_termico_aunque_la_temperatura_este_en_leve` | 422 |

### Ejecución (2026-10-28)

- **BD efímera:** `pruebas_g70_test` en el PostgreSQL 18 local, con `alembic upgrade head` hasta
  `ebbb160365e5`, en un contenedor con la imagen del backend. Se borró al terminar.
- **Resultados:**

```
tests/telemetry (G70 + G68 + DEV-41, DEV-49, DEV-13, DEV-30)                 168 passed
tests/integration: G70 (19) + G68 + DEV-04, DEV-30, DEV-41, DEV-43, DEV-49, DEV-17   130 passed, 6 skipped
Suite completa (sin red): 2348 passed; mismos 4 failed / 25 errors preexistentes que la base
```

La intermitencia de `test_dev41_..._no_duplican_condicion_ni_frecuencia` es la misma que ya existía
(ver G68).

## Para QA

- **Volver a ejecutar TC-M03-G70, G71 y G72.** Los eventos que esperan una alerta compuesta deben traer
  en `correlacion_variables` la variable requerida que falta, o el THI.
- **Respuesta esperada para un evento sin condición mínima:** 422 con `error_code`
  `REGLA_COMPUESTA_NO_ACTIVADA` o `EVENTO_INCOHERENTE_REGLA_COMPUESTA`, con su registro en la bitácora.
