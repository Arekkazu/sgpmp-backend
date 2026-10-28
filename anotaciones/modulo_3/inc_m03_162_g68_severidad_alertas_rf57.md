# INC-M03-162-G68 — POST /iot/alertas evalúa el valor contra RF-57 (TC-M03-G68, G69, G72)

**RF:** RF-57, Fase 5 (reglas y umbrales de negocio), CA-1 y Restricción 7. **Issue:** #740.
**Estado:** corregido y verificado con PostgreSQL real.

## Causa

`GenararAlertaUseCase` copiaba `severidad_edge` del emisor y nunca comparaba el valor con las reglas
de RF-57. Por eso:
- Una lectura imposible terminaba como alerta operativa.
- Una severidad contraria al valor pasaba tal cual, con el SLA equivocado.
- Un valor NORMAL generaba alerta.
- ESTRES_TERMICO no escalaba con las variables complementarias.

## Qué hace ahora `POST /iot/alertas`

El router inyecta `VariableAlertaM09Adapter`. Con él, el caso de uso evalúa el evento externo en este
orden:

1. **FALLO_AMBIENTAL** (RF-57, regla compuesta). Se dispara cuando el `estado_dato` es
   `ERROR_CALIBRACION` **o** cuando el valor está fuera del **rango absoluto del sensor**
   (`modulo9.variables_ambientales.valor_fisico_min/max`, no el rango operativo):
   - Crea una **alerta técnica**: `tipo_alerta='TECNICA'` y `tipo_variable='FALLO_AMBIENTAL'`, con el
     mismo patrón que las técnicas de RF-60 y RF-62. La ve el ingeniero de campo en
     `GET /iot/alertas-tecnicas` y no aparece en `GET /iot/alertas`. No hay alerta operativa.
   - **Severidad:** MODERADO, o CRITICO si la variable es crítica (`es_critica`, RF-17).
   - **Contenido:** `metadato_evento` guarda `causa` (`ERROR_CALIBRACION` o
     `VALOR_FUERA_DE_RANGO_ABSOLUTO`), el rango, `estado_dato` y la severidad reportada.
   - **Deduplicación:** el mismo sensor con un FALLO_AMBIENTAL abierto en los últimos 30 min se
     consolida y suma `frecuencia_evento`.
2. **Banda NORMAL.** Si la variable tiene bandas base y el valor no cae en ninguna, responde 201 con
   `id_alerta: null` y el motivo. En la bitácora RF-63 queda `EVENTO_SIN_DESVIACION_RF57` con la
   severidad declarada.
3. **Severidad por valor** (CA-1, Restricción 7). La severidad se toma de las bandas base, no de
   `severidad_edge`:
   - La severidad declarada se conserva en `severidad_edge_original` (cuando difiere) y en
     `metadato_evento.evaluacion_rf57`.
   - El SLA (5, 30 o 120 min) sale de la severidad evaluada.
   - La resolución Edge vs IA (E12/E13) se aplica después, sobre la severidad evaluada.
4. **ESTRES_TERMICO** (temperatura ambiental o humedad):
   - Si `correlacion_variables` trae `THI`, la severidad es la **mayor** entre la banda simple y la
     banda THI (`<72` NORMAL, `72` LEVE, `79` MODERADO, `84` CRITICO).
   - **Escalada:** si el THI está en LEVE o más **y** la temperatura corporal es mayor que 40 °C **o** la
     frecuencia respiratoria está en rango MODERADO o superior, la severidad **sube un nivel**. CRITICO
     no sube más.

Los eventos con `origen_evento = IA` no pasan por las bandas (PREDICCION_PATOLOGIA usa la probabilidad).
El flujo interno RF-17 → RF-57 (DEV-41) y los eventos Edge de RF-56 no inyectan el adaptador, así que
**no cambian**: DEV-41 ya clasifica con los umbrales de M09 por especie.

### Bandas base (RF-57 Fase 5)

`src/telemetry/domain/entities/reglas_base_rf57.py`, de la más severa a la menos severa. Si el valor
no cae en ninguna banda, es NORMAL:

| Variable | LEVE | MODERADO | CRITICO |
|---|---|---|---|
| TEMPERATURA_AMBIENTAL | > 30 o < 20 | > 33 o < 17 | > 36 o < 14 |
| HUMEDAD_RELATIVA | < 50 o > 70 | < 40 o > 80 | < 30 o > 90 |
| PH_AGUA | < 6.5 o > 8.5 | < 6.0 o > 9.0 | < 5.5 o > 9.5 |
| NH3 | ≥ 25 | ≥ 35 | ≥ 45 |
| CO2 | ≥ 3000 | ≥ 3500 | ≥ 4000 |
| TEMPERATURA_CORPORAL / TEMP_CORPORAL | > 40.0 o < 36.5 | > 40.5 o < 36.0 | > 41.0 o < 35.5 |
| FRECUENCIA_CARDIACA | > 100 o < 45 | > 110 o < 42 | > 120 o < 40 |
| OXIGENO_DISUELTO | < 5 | < 3 | < 2 |
| TDS | > 1000 | > 1500 | ≥ 2000 |

**No se evalúan con un solo valor** y conservan la severidad declarada:
- `FRECUENCIA_RESPIRATORIA`: su banda es un porcentaje sobre el rango de la especie.
- `ACTIVIDAD`: su banda compara contra una media móvil de 2 h.

## Formato de `correlacion_variables` (provisional)

El RF solo dice "estructura opcional con múltiples variables relacionadas (ej. THI…)". Se acepta un
objeto indexado por código de variable, sin distinguir mayúsculas:

```json
{
  "THI": 79.14,
  "TEMPERATURA_CORPORAL": 40.5,
  "FRECUENCIA_RESPIRATORIA": {"severidad": "MODERADO"}
}
```

- Un valor puede ser un número, un texto numérico o `{"valor": n}`.
- La temperatura corporal acepta `TEMPERATURA_CORPORAL` o `TEMP_CORPORAL`.
- La frecuencia respiratoria se declara por **nivel** (`severidad` o `nivel`), porque su rango depende de
  la especie y el emisor es quien lo conoce.

## Decisiones y puntos para Análisis

1. **Fórmula de THI inconsistente en el RF.** La fórmula de RF-57
   (`T − (0.55 − 0.0055·HR)·(T − 14.5)`) está en °C y da valores cercanos a T: con 32 °C y 60 % da 28,15,
   así que **nunca alcanza 72**. Los umbrales 72/79/84 son de la escala NRC en °F. Por eso el backend
   **no recalcula** el THI: usa el que deriva el Edge (RF-55, "indicadores derivados (ej. THI)") y llega
   en `correlacion_variables`. QA envió THI en escala NRC (72,12 y 79,14). Hay que confirmar la fórmula.
2. **Valores configurables.** RF-57 dice que los valores base "pueden ser modificados por el
   administrador o el ingeniero de campo", pero no hay dónde configurarlos: `modulo3.reglas_alertas` en
   DEV tiene datos de prueba inconsistentes (claves ALTA/MEDIA/BAJA/CRITICA y variables cruzadas). Por
   ahora rigen los valores base del RF. Hacerlos editables (tabla o almacén de DEV-14) es otra tarea.
3. **Ventana de confirmación** ("2 lecturas consecutivas en ≤ 20 min"). Un evento de `POST /iot/alertas`
   es una desviación ya detectada (Edge o backend) y no trae la serie, así que la confirmación le toca a
   quien detecta (RF-55). No se aplica aquí.
4. **Reglas compuestas SINDROME_RESPIRATORIO, RIESGO_HIDRICO, FIEBRE e INACTIVIDAD_ANORMAL.** El ticket
   pide la escalada de ESTRES_TERMICO (TC-M03-G72). Las demás quedan con el mismo mecanismo disponible y
   fuera de alcance.
5. **`tipo_alerta` en la respuesta de FALLO_AMBIENTAL.** Devuelve `TECNICA`, lo que está en la fila;
   el subtipo `FALLO_AMBIENTAL` va en `tipo_variable` y en `motivo_descarte`.

## Evidencia

**Pruebas unitarias.** `tests/telemetry/test_inc_m03_162_g68_reglas_base_rf57.py`: 59 casos con los
bordes exactos de cada banda, el THI y la escalada (incluido "> 40", no "≥ 40"), la lectura de la
correlación y el rango físico.

**Pruebas de integración.** `tests/integration/test_inc_m03_162_g68_severidad_alertas_rf57.py`: router
real, adaptadores de M09 y PostgreSQL real.

| Caso de QA | Prueba | Resultado |
|---|---|---|
| G68: 200 °C con CRITICO y 250 °C con MODERADO | `test_valor_fuera_del_rango_absoluto_genera_fallo_ambiental_tecnico` | `TECNICA` / `FALLO_AMBIENTAL` MODERADO; aparece en `/iot/alertas-tecnicas` y no en `/iot/alertas` |
| G68: variable crítica | `test_fallo_ambiental_de_variable_critica_es_critico` | CRITICO |
| G68: ERROR_CALIBRACION | `test_error_de_calibracion_genera_fallo_ambiental_tecnico` | Alerta técnica, causa `ERROR_CALIBRACION` |
| G68: repetición | `test_fallo_ambiental_repetido_se_consolida` | Duplicado, `frecuencia_evento = 2` |
| G69: 36.1 °C con LEVE, 33.1 °C con CRITICO, bordes 36.0, 30.1 y 13.9, HR 95 y OD 2.5 | `test_severidad_sale_del_valor_no_de_la_declarada` | CRITICO, MODERADO, MODERADO, LEVE, CRITICO, CRITICO, MODERADO; SLA según la severidad evaluada; la declarada queda en `severidad_edge_original` |
| G69: 25.0 °C con CRITICO, 30.0 °C, HR 60 % con MODERADO y OD 8.0 con CRITICO | `test_valor_en_banda_normal_no_genera_alerta` | Sin alerta; `EVENTO_SIN_DESVIACION_RF57` en la bitácora |
| Frecuencia respiratoria | `test_variable_con_banda_por_especie_conserva_la_severidad_declarada` | Se conserva |
| G72: THI 72.12 con temperatura corporal 40.5 (declarada LEVE) | `test_estres_termico_escala_con_variables_complementarias` | **MODERADO** |
| G72: THI 79.14 con temperatura corporal > 40 o frecuencia respiratoria MODERADO | ídem | **CRITICO** |
| G72: sin complementarias, o con temperatura corporal de 39.9 | ídem | LEVE (sin escalada) |

**Prueba de DEV-49 actualizada.**
`test_calidad_no_valida_conserva_lectura_y_registro_tecnico[ERROR_CALIBRACION]` afirmaba "sin alerta",
que es justo el defecto de G68. Ahora exige la alerta técnica FALLO_AMBIENTAL. El caso `FUERA_DE_RANGO`,
con un valor dentro del rango físico, sigue sin generar alerta.

### Ejecución (2026-10-28)

- **BD efímera:** `pruebas_g68_test` en el PostgreSQL 18 local, con `alembic upgrade head` hasta
  `ebbb160365e5`, en un contenedor con la imagen del backend. Se borró al terminar, junto con los roles
  temporales.
- **Resultados:**

```
tests/telemetry/test_inc_m03_162_g68_reglas_base_rf57.py                 59 passed
tests/integration: G68 + DEV-04, DEV-30, DEV-41, DEV-43, DEV-49, DEV-17  117 passed, 6 skipped
Suite completa (sin red): 2323 passed; mismos 4 failed / 25 errors preexistentes que la base
```

**Intermitencia que ya existía.**
`test_dev41_alertas_telemetria.py::test_dos_workers_concurrentes_no_duplican_condicion_ni_frecuencia`
falla a veces con `frecuencia_evento == 1`. **En `dev` falla igual: 3 de 15 corridas**, con la misma
aserción. No pasa por el código de este cambio (sin `variable_port`), así que queda fuera de alcance.

## Para QA

- **Volver a ejecutar TC-M03-G68, G69 y G72** con `POST /iot/alertas`. Para G72, enviar el THI en
  `correlacion_variables` con el formato de arriba.
- **FALLO_AMBIENTAL** se consulta en `GET /iot/alertas-tecnicas` con el ingeniero o el administrador.
