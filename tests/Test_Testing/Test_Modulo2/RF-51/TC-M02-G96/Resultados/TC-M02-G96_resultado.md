# RESULTADO — TC-M02-G96

## 0. RESUMEN EJECUTIVO

| Dimensión | Resultado |
|---|---|
| **VEREDICTO** | **RECHAZADO** |
| Subtipo | 3 defectos de producto confirmados + 1 sub-caso BLOQUEADO (CONSUMO CERO NO DISPONIBLE) |
| TC-M02-160 | **RECHAZADO** |
| TC-M02-161 | **RECHAZADO** |
| TC-M02-162 | **BLOQUEADO** |
| TC-M02-163 | **RECHAZADO** |
| SOLICITUDES OFICIALES | **3/4** (TC-M02-162 no ejecutable: precondición inexistente) |
| ESCRITURAS TOTALES (QA) | **0** |
| Assertions | 51 ejecutadas · 45 correctas · **6 fallidas** |
| Equipo responsable | **Desarrollo Backend** (defectos) · **DBA / Implementación** (desbloqueo TC-M02-162) |

**Justificación.** Las tres precondiciones ejecutables existían preexistentes en TEST y fueron verificadas por `SELECT` antes de emitir cualquier solicitud: el activo **285 (QAJE-IND-1MED)** tiene exactamente una medición de peso, el **299 (QAJE-IND-MACHO)** es bovino macho y el **280 (QAJE-IND-OUTLIER)** contiene un crecimiento de **+500 kg/día** calculado independientemente por QA. Ninguna fue fabricada.

RF-51 **no rechaza ninguno de los tres escenarios**. El endpoint responde `HTTP 200` en los tres casos. En dos de ellos la información entregada es correcta y explícita (indicador `disponible:false`, sin valor numérico), de modo que la integridad analítica se preserva y la desviación es de código HTTP. En el tercero —el outlier— el sistema **publica `ganancia_peso = 500.0000 kg/día` con `disponible: true`**, es decir, entrega como válido un indicador biológicamente imposible. Ese es el hallazgo determinante del caso.

TC-M02-162 queda **BLOQUEADO**: en TEST no existe ni un solo registro de consumo de alimento igual a `0`, y §7.7 prohíbe crearlo o modificar registros de alimentación.

---

## 1. Identificación

- **Caso:** TC-M02-G96
- **RF:** RF-51 — Generación de Indicadores Zootécnicos
- **CU:** CU12
- **Sub-casos:** TC-M02-160, TC-M02-161, TC-M02-162, TC-M02-163
- **Responsable:** Juan Esteban
- **Rama:** `qa/juan-esteban-m02`
- **HEAD:** `41369ea4ab3948eacb1ab9b2d0549310e285eeae`
- **Fecha/hora de ejecución:** 2026-09-10, 21:08Z (gate) — 21:28Z (ejecución Newman)
- **Ambiente:** TEST HTTPS `https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test/`
- **Consumidor:** `m2m.nuevo@ejemplo.com` (usuario **35**), propietario de la finca 57
- **Herramienta:** Postman + Newman (reporters `cli,json,htmlextra`)

---

## 2. Gate

| Verificación | Resultado |
|---|---|
| Repositorio | ✅ `https://github.com/Arekkazu/sgpmp-backend.git` |
| Rama | ✅ `qa/juan-esteban-m02` (exacta, no se cambió de rama) |
| HEAD | ✅ `41369ea` — "Agrega variables jwt y cookie a enviroments de back" |
| `git status` | ✅ Sin modificaciones a archivos versionados (solo artefactos QA sin seguimiento) |
| Backend TEST HTTPS | ✅ `GET /openapi.json` → **HTTP 200** |
| PostgreSQL solo lectura | ✅ `SELECT 1` → 1. Sesión abierta con `set_session(readonly=True)` |
| OpenAPI `/indicadores` | ✅ Ruta declarada, método **único `get`** |
| Consumidor autorizado | ✅ Control positivo A1: `GET /activos-biologicos/279/indicadores` → **200** |

### 2.1 Contrato vigente de `GET /activos-biologicos/{id_activo}/indicadores`

| Elemento | Valor real en OpenAPI |
|---|---|
| Métodos | **`get` únicamente** |
| `tipo_indicador` | `string`, default `TODOS`, descripción: `CRECIMIENTO \| PRODUCCION \| SANITARIO \| EFICIENCIA \| TODOS` |
| `fecha_inicio` / `fecha_fin` | `string` opcional, formato `YYYY-MM-DD` |
| Respuesta 200 | `IndicadoresActivoResponse` → `{id_activo_biologico, tipo_activo, indicadores[], advertencias[]}` |
| Respuestas declaradas | `200, 400, 401, 403, 404, 422` |
| **No declaradas** | **`409`** (exigido por TC-M02-162) y **`500`** (exigido por TC-M02-163) |
| `securitySchemes` | Ninguno |

**D12 — valores de indicador que acepta OpenAPI.** El contrato **no expone un enum por indicador individual**. No existen los valores `Ganancia Diaria de Peso`, `Producción de leche` ni `Conversión Alimenticia` como tales. La única vía de solicitud es la familia `tipo_indicador`, que el producto traduce internamente así:

| Indicador de la ficha | Vía real en el contrato | Indicador devuelto |
|---|---|---|
| Ganancia Diaria de Peso | `tipo_indicador=CRECIMIENTO` | `ganancia_peso` (kg/dia) |
| Producción de leche | `tipo_indicador=PRODUCCION` | `produccion_promedio` (unidades/dia) |
| Conversión Alimenticia | `tipo_indicador=EFICIENCIA` | `conversion_alimenticia` (kg_alimento/kg_ganancia) |
| Indicador de crecimiento | `tipo_indicador=CRECIMIENTO` | `ganancia_peso` (kg/dia) |

Conforme a §6.3 y A7, **no se inventó ningún valor de enum**: cada solicitud usa el identificador que el contrato realmente publica. La discrepancia entre la granularidad de la ficha y la del contrato queda registrada como **OBS-G96-02**.

---

## 3. SETUP — SOLO LECTURA

**Escrituras SETUP: 0.** Todo el inventario se obtuvo con `SELECT` (sesión `readonly`) y con peticiones `GET`. Ningún dato fue creado, eliminado ni modificado.

### 3.0 Inventario de datos (§10)

| # | Pregunta | Resultado |
|---|---|---|
| D1 | Consumidor autorizado RF-51 | `m2m.nuevo@ejemplo.com` (id 35), dueño de la finca 57; control positivo 200 |
| D2 | Activo con exactamente 1 PESO en rango (TC-160) | **285** `QAJE-IND-1MED`, rango 2026-07-01 → 2026-07-31 |
| D3 | Esa medición / fecha | `210.00 kg`, 2026-07-20 10:00:00+00 |
| D4 | Activo bovino macho (TC-161) | **299** `QAJE-IND-MACHO`, especie 40 `Bovino Qa Je` |
| D5 | Cómo representa BD el sexo | `modulo2.detalles_activos_individuales.sexo`, valores `Macho` / `Hembra` |
| D6 | Activo/periodo con consumo = 0 | **NINGUNO** — no existe |
| D7 | Registros que demuestran consumo 0 | **No existen**: 16 registros en `modulo5.registros_consumo_alimentos`, **0** con `cantidad_suministrada = 0` |
| D8 | Activo/rango con el outlier (TC-163) | **280** `QAJE-IND-OUTLIER`, rango 2026-08-01 → 2026-08-02 |
| D9 | Pesos y fechas | 10.00 kg (2026-08-01) → 510.00 kg (2026-08-02) |
| D10 | GDP calculada por QA | **+500 kg/día** |
| D11 | ¿Otra condición inválida en cada escenario? | No: los tres activos existen, `id_estado = 1 (ACTIVO)`, fase activa, accesibles por el consumidor, rangos válidos |
| D12 | Valores de indicador que acepta OpenAPI | `CRECIMIENTO, PRODUCCION, SANITARIO, EFICIENCIA, TODOS` (ver §2.1) |

### 3.1 TC-M02-160 — muestra insuficiente

- **Activo:** 285 (`QAJE-IND-1MED`), INDIVIDUAL, especie 40, `id_estado = 1` (ACTIVO), finca 57
- **Rango solicitado:** 2026-07-01 → 2026-07-31
- **Número de mediciones de PESO en rango:** **1**
- **Medición disponible:** `210.00 kg` el 2026-07-20 10:00:00+00

```sql
SELECT ea.id_activo_biologico, ec.tipo_medicion, ec.valor_medicion, ec.unidad_medida, ea.fecha
  FROM modulo2.eventos_crecimeinto ec
  JOIN modulo2.eventos_activos ea ON ec.id_evento = ea.id_eventos
 WHERE ea.id_activo_biologico = 285;
-- 285 | PESO | 210.00 | kg | 2026-07-20 10:00:00+00      (1 fila)

SELECT lower(ec.tipo_medicion) AS medicion, count(*) AS n
  FROM modulo2.eventos_crecimeinto ec
  JOIN modulo2.eventos_activos ea ON ec.id_evento = ea.id_eventos
 WHERE ea.id_activo_biologico = 285 GROUP BY 1;
-- peso | 1
```

**§5.3 — regla de rango.** El activo tiene una sola medición **global** y una sola **dentro del rango**; ambas cifras coinciden, así que el escenario es válido con independencia de si RF-51 filtra por rango. Se confirmó además por API en el SETUP: el historial devuelve exactamente 1 registro `CRECIMIENTO` en el intervalo (A3/A4 descartados).

### 3.2 TC-M02-161 — incompatibilidad biológica

- **Activo:** 299 (`QAJE-IND-MACHO`), INDIVIDUAL, `id_estado = 1` (ACTIVO), finca 57
- **Especie:** 40 — `Bovino Qa Je` (bovina)
- **Sexo/género:** **`Macho`**
- **Indicador solicitado:** `tipo_indicador=PRODUCCION` → `produccion_promedio` (la vía contractual de "Producción de leche")

```sql
SELECT ab.id_activo_biologico, ab.identificador, e.nombre AS especie, d.sexo, ab.id_estado
  FROM modulo2.activos_biologicos ab
  JOIN modulo9.especies e ON e.id_especie = ab.id_especie
  LEFT JOIN modulo2.detalles_activos_individuales d ON d.id_activo_biologico = ab.id_activo_biologico
 WHERE ab.id_activo_biologico = 299;
-- 299 | QAJE-IND-MACHO | Bovino Qa Je | Macho | 1
```

Confirmado también por API (`GET /activos-biologicos/299/ficha-integral`): `{"identificador":"QAJE-IND-MACHO","especie":"Bovino Qa Je","sexo":"Macho","estado_actual":"ACTIVO"}`. **A5 y A6 descartados.**

> **Nota de aislamiento.** El activo 299 no tiene eventos productivos registrados —consecuencia natural de ser macho, no una condición introducida por QA—. La precondición que fija §6.2 (activo existente, bovino, macho, consumidor autorizado, parámetros válidos) se cumple íntegramente. Como se demuestra en §5, el producto **no evalúa en ningún punto la compatibilidad especie/sexo–indicador**, de modo que esa regla nunca llega a ejecutarse: el resultado no depende de si existen o no eventos productivos.

### 3.3 TC-M02-162 — división por cero

- **Activo/periodo con consumo 0:** **no existe en TEST**
- **Consumo de alimento:** ningún registro con valor `0`

```sql
SELECT count(*) AS total, count(*) FILTER (WHERE cantidad_suministrada = 0) AS con_cero
  FROM modulo5.registros_consumo_alimentos;
-- total = 16 | con_cero = 0

SELECT count(*) FROM modulo5.registros_consumo_alimentos
 WHERE id_activo_biologico BETWEEN 279 AND 340;
-- 0   (ningún fixture del caso tiene consumo registrado)
```

Los 16 registros existentes pertenecen a los activos **1, 5, 8 y 57**, con cantidades `400.000, 5.000, 3.000, 7.000, 5.000, 5.000, 5.000, 10.000, 5.000, -9.000, 4.000, 10.500, 4.250, 5.000, 76.500, 10.000` kg. Ninguna es `0`. El único valor no positivo es `-9.000` (registro 23, estado `ANULADO`), que no es `0` y además está anulado, por lo que no satisface la precondición oficial de §7.2.

**Conclusión:** la precondición no existe y §7.7 prohíbe fabricarla. **Sub-caso BLOQUEADO.**

### 3.4 TC-M02-163 — outlier crítico

- **Activo:** 280 (`QAJE-IND-OUTLIER`), INDIVIDUAL, `id_estado = 1` (ACTIVO), finca 57
- **Rango:** 2026-08-01 → 2026-08-02

```sql
SELECT ec.valor_medicion, ec.unidad_medida, ea.fecha
  FROM modulo2.eventos_crecimeinto ec
  JOIN modulo2.eventos_activos ea ON ec.id_evento = ea.id_eventos
 WHERE ea.id_activo_biologico = 280 ORDER BY ea.fecha;
-- 10.00  | kg | 2026-08-01 10:00:00+00
-- 510.00 | kg | 2026-08-02 10:00:00+00
```

#### Cálculo independiente de QA (§8.3)

| Variable | Valor |
|---|---|
| Peso inicial | **10.00 kg** |
| Fecha inicial | 2026-08-01 10:00:00+00 |
| Peso final | **510.00 kg** |
| Fecha final | 2026-08-02 10:00:00+00 |
| Días | **1** |
| Ganancia | **+500.00 kg** |
| **GDP calculada por QA** | **+500.0000 kg/día** |

```text
GDP_QA = (510.00 - 10.00) / 1 = +500 kg/día
```

Coincide exactamente con el ejemplo explícito de la ficha (`+500 kg/día`), de modo que **no fue necesario sustituir el criterio del caso** por ningún umbral alternativo. **A11 y A12 descartados**: el propio producto reporta en `variables_usadas` los mismos `peso_inicial_kg: 10.0`, `peso_final_kg: 510.0` y `dias: 1` que QA leyó en BD. **A13 descartado**: ambas mediciones están en `kg`, sin necesidad de normalización.

---

## 4. TC-M02-160 — muestra insuficiente

- **Endpoint:** `GET /activos-biologicos/285/indicadores?tipo_indicador=CRECIMIENTO&fecha_inicio=2026-07-01&fecha_fin=2026-07-31`
- **Indicador:** Ganancia Diaria de Peso (`ganancia_peso`)
- **HTTP esperado:** `422`
- **HTTP obtenido:** **`200`** ❌
- **¿Retornó valor numérico de GDP?:** **NO** ✅

```json
{"id_activo_biologico":285,"tipo_activo":"INDIVIDUAL",
 "indicadores":[{"tipo":"ganancia_peso","valor":null,"unidad":"kg/dia",
   "periodo_inicio":null,"periodo_fin":null,
   "variables_usadas":{"registros_disponibles":1},
   "fecha_calculo":"2026-09-10T21:13:13.962445Z","disponible":false}],
 "advertencias":["DATOS_INSUFICIENTES: ganancia_peso requiere al menos 2 mediciones de peso."]}
```

| Verificación | Resultado |
|---|---|
| V1 — activo existe | ✅ |
| V2 — exactamente 1 PESO en rango | ✅ (`registros_disponibles: 1`, coincide con BD) |
| V3 — HTTP 422 | ❌ **obtenido 200** |
| V4 — motivo = muestra insuficiente | ✅ (`DATOS_INSUFICIENTES: ... requiere al menos 2 mediciones de peso`) |
| §5.6.8 — no retorna GDP válido | ✅ (`valor: null`, `disponible: false`) |
| Sin Infinity / NaN | ✅ |
| Sin stack trace ni detalles técnicos | ✅ |
| V18 — cero escrituras de QA | ✅ |

**Resultado: RECHAZADO** por incumplimiento del código HTTP. La causa funcional se identifica correctamente y **no se publica ningún indicador inválido**, por lo que la integridad analítica se preserva: la desviación es de contrato HTTP, no de cálculo.

---

## 5. TC-M02-161 — incompatibilidad biológica

- **Activo:** 299 `QAJE-IND-MACHO`
- **Especie:** Bovino Qa Je (bovina) · **Sexo:** Macho
- **Indicador:** Producción de leche → `tipo_indicador=PRODUCCION`
- **Endpoint:** `GET /activos-biologicos/299/indicadores?tipo_indicador=PRODUCCION`
- **HTTP esperado:** `400`
- **HTTP obtenido:** **`200`** ❌
- **¿Retornó indicador?:** NO (`valor: null`, `disponible: false`)

```json
{"id_activo_biologico":299,"tipo_activo":"INDIVIDUAL",
 "indicadores":[{"tipo":"produccion_promedio","valor":null,"unidad":"unidades/dia",
   "variables_usadas":{"registros_disponibles":0},
   "fecha_calculo":"2026-09-10T21:13:14.412991Z","disponible":false}],
 "advertencias":["DATOS_INSUFICIENTES: no hay eventos productivos en el período solicitado."]}
```

| Verificación | Resultado |
|---|---|
| V5 — activo bovino macho | ✅ (BD + ficha integral) |
| V6 — indicador = Producción de leche | ✅ vía `tipo_indicador=PRODUCCION`, único camino contractual |
| V7 — HTTP 400 | ❌ **obtenido 200** |
| V8 — motivo = incompatibilidad biológica | ❌ **el motivo declarado es falta de datos** |
| §6.5.8 — no se calcula el indicador | ✅ |
| Sin Infinity / NaN | ✅ |
| V18 — cero escrituras de QA | ✅ |

**El motivo reportado es incorrecto y ese es el núcleo del defecto.** El sistema no rechaza la solicitud por incompatibilidad, sino que la acepta y la atribuye a ausencia de datos. La distinción no es cosmética: implica que **la regla de compatibilidad especie/sexo–indicador no existe**. Si el mismo bovino macho tuviera eventos productivos registrados, el sistema calcularía y publicaría un indicador de producción sobre un animal que biológicamente no puede producirlo.

**Resultado: RECHAZADO.**

---

## 6. TC-M02-162 — división por cero

- **Activo/periodo:** ninguno disponible
- **Consumo confirmado = 0:** **NO EXISTE en TEST**
- **HTTP esperado:** `409`
- **HTTP obtenido:** **solicitud oficial NO EJECUTADA**
- **Resultado: BLOQUEADO — CONSUMO CERO NO DISPONIBLE**

**Por qué no se ejecutó la solicitud oficial.** §2.B y §7.7 son explícitos: si la precondición no está preexistente, el sub-caso se bloquea y no se fabrica. Emitir un `GET ...&tipo_indicador=EFICIENCIA` sobre un activo **sin** consumo cero no probaría la regla de división por cero, sino un escenario distinto (ausencia de datos). Conforme a §2.C y §18-A8, eso habría sido un sub-caso no aislado, no una aprobación ni un rechazo válidos.

**Evidencia adicional (diagnóstico, no oficial).** Se ejecutó una consulta de diagnóstico para documentar el comportamiento real del indicador de eficiencia:

```json
{"tipo":"conversion_alimenticia","valor":null,"unidad":"kg_alimento/kg_ganancia",
 "variables_usadas":{},"disponible":false}
"advertencias":["REQUIERE_M05: El indicador conversion_alimenticia requiere datos de consumo
 de alimento del módulo M05, que aún no está implementado."]
```

`conversion_alimenticia` se devuelve **siempre** como no disponible, con independencia del activo y del periodo: el cálculo nunca se intenta. Existe en BD la tabla `modulo5.registros_consumo_alimentos` con 16 registros, pero el repositorio de indicadores no la consulta en ningún punto. En consecuencia, aunque el fixture de consumo `0` llegara a crearse, **la regla de división por cero seguiría sin poder demostrarse** mientras el indicador no se calcule. Queda registrado como **OBS-G96-03**.

**Equipo responsable de desbloquear:** DBA / Implementación (provisión del fixture) y Desarrollo Backend (implementación del cálculo).

---

## 7. TC-M02-163 — outlier crítico

### Cálculo independiente QA

```text
(peso_final - peso_inicial) / días = (510.00 - 10.00) / 1 = +500.0000 kg/día
```

- **Outlier esperado:** +500 kg/día — coincide con el ejemplo explícito de la ficha
- **Endpoint:** `GET /activos-biologicos/280/indicadores?tipo_indicador=CRECIMIENTO&fecha_inicio=2026-08-01&fecha_fin=2026-08-02`
- **HTTP esperado:** `500` controlado
- **HTTP obtenido:** **`200`** ❌

```json
{"id_activo_biologico":280,"tipo_activo":"INDIVIDUAL",
 "indicadores":[{"tipo":"ganancia_peso","valor":"500.0000","unidad":"kg/dia",
   "periodo_inicio":"2026-08-01","periodo_fin":"2026-08-02",
   "variables_usadas":{"peso_inicial_kg":10.0,"peso_final_kg":510.0,"dias":1,"total_mediciones":2},
   "fecha_calculo":"2026-09-10T21:13:14.863651Z","disponible":true}],
 "advertencias":[]}
```

| Verificación | Resultado |
|---|---|
| V13 — mediciones/rango producen outlier | ✅ |
| V14 — outlier calculado independientemente | ✅ **+500 kg/día**, idéntico al del producto |
| V15 — HTTP 500 | ❌ **obtenido 200** |
| V16 — mensaje identifica outlier / imposibilidad biológica | ❌ **`advertencias` está vacío** |
| V17 — no se expone indicador como válido | ❌ **`valor: "500.0000"`, `disponible: true`** |
| Error estructurado | N/A — no hubo error |
| Stack trace | ✅ NO |
| Secretos / rutas internas | ✅ NO |
| Infinity / NaN | ✅ NO |
| Indicador parcial | ❌ se entrega el indicador **completo** y marcado como válido |
| V18 — cero escrituras de QA | ✅ |

**Este es el hallazgo más grave del caso.** No se trata de un código HTTP discrepante: el sistema **calcula, marca como disponible y publica** una ganancia diaria de 500 kg/día en un bovino. Ningún animal gana 500 kg en un día. El indicador se entrega sin una sola advertencia que alerte al consumidor, con `disponible: true`, que es precisamente la bandera que un módulo analítico usaría para decidir si el dato es utilizable.

**Resultado: RECHAZADO.**

---

## 8. Confirmación de solo lectura

| Operación | Cantidad |
|---|---|
| SQL writes | **0** |
| POST (oficiales) | **0** |
| PUT | **0** |
| PATCH | **0** |
| DELETE | **0** |

El único `POST` emitido en toda la ejecución es `POST /sesiones/` (autenticación del consumidor), que no crea ni modifica datos de negocio. Las 4 solicitudes de indicadores y las lecturas de apoyo son `GET`.

### 8.1 Integridad verificada antes y después

| Tabla | Antes | Después | Δ |
|---|---|---|---|
| `modulo2.eventos_crecimeinto` | 50 | 50 | **0** |
| `modulo2.eventos_activos` | 106 | 106 | **0** |
| `modulo5.registros_consumo_alimentos` | 16 | 16 | **0** |
| `modulo2.detalles_activos_individuales` | 172 | 172 | **0** |
| `modulo2.activos_biologicos` | 259 | 259 | **0** |

Las mediciones de los fixtures son idénticas tras la ejecución (280: `10.00` y `510.00 kg`; 285: `210.00 kg`), igual que especie, sexo y estado de los tres activos (280 Hembra, 285 Hembra, 299 Macho; `id_estado = 1`).

**Cambios observados: 0.** No se crearon ni eliminaron mediciones, no se modificó sexo ni especie, no se puso ningún consumo en `0` y no se fabricó ningún outlier.

### 8.2 Escrituras del producto (no de QA)

`modulo2.bitacora_auditoria_m02` pasó de **1107 a 1128** filas (+21), de las cuales **+14 son `rf_origen = 'RF51'`**. Son escrituras que **realiza el propio producto**: `ConsultarIndicadoresUseCase` registra un evento `INDICADOR_CALCULADO` y hace `commit` en cada consulta exitosa. Las 14 filas corresponden exactamente a los 14 `GET /indicadores` emitidos por el consumidor 35 (10 de sondeo y verificación + 4 de la corrida Newman sobre 279, 280, 285 y 299); las 7 restantes provienen de las lecturas de apoyo (`RF46` historial ×4, `RF47` ficha integral ×3). Ninguna fue provocada por una operación de escritura de QA.

---

## 9. Diagnóstico

**¿Fue necesario? SÍ** — hubo desviación en los tres sub-casos ejecutables.

### 9.1 Hipótesis de error de prueba descartadas (§17)

| # | Hipótesis | Cómo se descartó |
|---|---|---|
| A1 | Consumidor no autorizado | Control positivo en SETUP: `GET /activos-biologicos/279/indicadores` → **200**. Ningún sub-caso devolvió 401/403 |
| A2 | Activo inexistente | `SELECT` previo de los tres activos + ficha integral 200. Ningún 404 |
| A3 | TC-160 tiene 2+ pesos en rango | `count(*) = 1` en BD **y** `registros_disponibles: 1` reportado por el propio producto |
| A4 | Rango no incluye la medición esperada | La medición (2026-07-20) cae dentro de 2026-07-01→2026-07-31; el producto la contabilizó |
| A5 | Activo TC-161 no es macho | `detalles_activos_individuales.sexo = 'Macho'` en BD y `"sexo":"Macho"` en ficha integral |
| A6 | Especie TC-161 no es bovina | `id_especie = 40` → `Bovino Qa Je` |
| A7 | Enum de "Producción de leche" incorrecto | El contrato no expone tal enum; `PRODUCCION` es la única vía y devuelve `produccion_promedio` (§2.1) |
| A8 | Consumo TC-162 no es exactamente 0 | No hay ningún registro con `cantidad_suministrada = 0` → sub-caso bloqueado, no ejecutado |
| A9 | Faltan otras variables en TC-162 | No aplica: no se ejecutó la solicitud oficial |
| A10 | Indicador TC-162 solicitado incorrecto | No aplica; el diagnóstico usó `EFICIENCIA`, la vía contractual de conversión alimenticia |
| A11 | TC-163 no produce realmente el outlier | QA calculó +500 kg/día de forma independiente y el producto reporta las mismas variables |
| A12 | Días calculados incorrectamente | Diferencia temporal real = 1 día; el producto reporta `dias: 1` |
| A13 | Unidades de peso distintas sin normalizar | Ambas mediciones en `kg` |
| A14 | TC-163 contiene además una métrica corrupta | Solo 2 mediciones en el rango, ambas `PESO` en `kg`, coherentes |
| A15 | Variable Postman incorrecta | Cada test verifica la URL final emitida (`tipo_indicador`, `fecha_inicio`, `fecha_fin`) |
| A16 | El resultado proviene de infraestructura | No hubo 5xx; todas las respuestas son `200` con cuerpo de negocio bien formado |
| A17 | Un 500 expone stack trace | No hubo 500; las respuestas no contienen trazas, SQL ni rutas internas |
| A18 | Assertion espera mensaje distinto al contrato vivo | Las assertions de motivo son semánticas (regex amplia), no literales |

**Control negativo del diagnóstico.** Para descartar que los `200` provinieran de un endpoint inerte, se consultó el activo 279 (`QAJE-CREC-OK`, datos normales): el indicador `ganancia_peso` se calcula y se publica con `disponible: true`. **El endpoint funciona; lo que falta son las reglas de rechazo.**

### 9.2 Causa raíz

Confirmada por lectura de código (sin modificarlo):

- `src/biological_assets/application/use_cases/gestion/consultar_indicadores_use_case.py` — la **única** excepción que el caso de uso puede lanzar es `NotFoundError` cuando el activo no existe. No hay ninguna otra validación.
- `src/biological_assets/infrastructure/repositories/indicadores_repository.py:104` — con menos de 2 mediciones devuelve un indicador `disponible=False` más una advertencia; **nunca lanza error**.
- `.../indicadores_repository.py:142-202` — `_calcular_produccion_promedio` **no consulta especie ni sexo**. La única comprobación de aplicabilidad en todo el archivo es `tipo_activo != 'POBLACIONAL'` para morbilidad y mortalidad. **No existe catálogo ni regla de compatibilidad especie/sexo–indicador.**
- `.../indicadores_repository.py:116-140` — `_calcular_ganancia_peso` calcula `(peso_final - peso_inicial) / días` y devuelve el resultado sin ninguna comprobación de rango biológico. **No existe detección de outliers**: ni umbral configurable, ni constante, ni validación posterior.
- `.../indicadores_repository.py:64-75` — `conversion_alimenticia` se construye siempre con `disponible=False` y la advertencia `REQUIERE_M05`; el cálculo no se intenta y la tabla `modulo5.registros_consumo_alimentos` nunca se consulta.

**Causa raíz:** RF-51 está implementado con una estrategia uniforme de *degradación elegante* — responder siempre `200` con `disponible: false` y una advertencia— en lugar de la estrategia de *rechazo explícito* que define la matriz de pruebas. Esa decisión es defendible para los casos de datos faltantes, donde la información entregada es correcta, pero **no cubre el caso del outlier**, en el que no existe ninguna validación y el resultado imposible se publica como válido.

**Atribución: DEFECTO DEL PRODUCTO** en los tres sub-casos ejecutables.

---

## 10. VEREDICTO FINAL

# ❌ RECHAZADO

Con **TC-M02-162 BLOQUEADO** por ausencia de fixture. *BLOQUEADO no equivale a APROBADO.*

---

### DEF-G96-01 — El outlier crítico se publica como indicador válido

| Campo | Valor |
|---|---|
| Sub-caso | TC-M02-163 |
| Consumidor | `m2m.nuevo@ejemplo.com` (usuario 35), autorizado |
| Activo | 280 `QAJE-IND-OUTLIER` |
| Indicador | Crecimiento (`ganancia_peso`) |
| Rango | 2026-08-01 → 2026-08-02 |
| Precondición | 10.00 kg → 510.00 kg en 1 día (preexistente, no fabricada) |
| Esperado | `HTTP 500` controlado: "Se detectaron valores atípicos (Outliers)… el indicador resultante es biológicamente imposible" |
| Obtenido | `HTTP 200` con `ganancia_peso = "500.0000" kg/dia`, `disponible: true`, `advertencias: []` |
| Evidencia API | `Resultados/reporte_tc_m02_g96.html` · assertions V15, V16, V17 fallidas |
| Evidencia BD | 2 mediciones `PESO` en `kg`: 10.00 (2026-08-01) y 510.00 (2026-08-02) |
| Cálculo independiente | `(510.00 − 10.00) / 1 = +500.0000 kg/día` |
| ¿Infinity/NaN? | No |
| ¿Stack trace? | No |
| Categoría | `CALCULO` / Integridad analítica |
| **Severidad** | **Severo** |
| Tiempo máximo | 1 día hábil |
| **Fecha límite** | **2026-09-11** |
| **Equipo responsable** | **Desarrollo Backend** |
| Causa raíz | `_calcular_ganancia_peso` no aplica ninguna validación de rango biológico sobre el resultado |
| Impacto | RF-51 publica como válido un indicador biológicamente imposible. Cualquier módulo analítico que consuma RF-51 y confíe en `disponible: true` incorporará el valor en promedios, proyecciones y alertas, contaminando la analítica derivada sin ninguna señal de advertencia |
| Reproducibilidad | 100 % — 3/3 ejecuciones sobre el activo 280 |

---

### DEF-G96-02 — No existe validación de compatibilidad biológica especie/sexo–indicador

| Campo | Valor |
|---|---|
| Sub-caso | TC-M02-161 |
| Consumidor | `m2m.nuevo@ejemplo.com` (usuario 35), autorizado |
| Activo | 299 `QAJE-IND-MACHO` — bovino, **macho**, ACTIVO |
| Indicador | Producción de leche → `tipo_indicador=PRODUCCION` |
| Rango | Sin filtro (todos los parámetros válidos) |
| Precondición | Bovino macho preexistente, no modificado |
| Esperado | `HTTP 400`: "Incompatibilidad biológica: el indicador no es aplicable a la especie/género del activo" |
| Obtenido | `HTTP 200`, `produccion_promedio` con `disponible: false` y advertencia **`DATOS_INSUFICIENTES: no hay eventos productivos`** |
| Evidencia API | assertions V7 y V8 fallidas |
| Evidencia BD | `especie = Bovino Qa Je`, `sexo = Macho`, `id_estado = 1` |
| ¿Infinity/NaN? | No |
| Categoría | `REGLA_NEGOCIO` / `CALCULO` |
| **Severidad** | **Severo** |
| Tiempo máximo | 1 día hábil |
| **Fecha límite** | **2026-09-11** |
| **Equipo responsable** | **Desarrollo Backend** |
| Causa raíz | `_calcular_produccion_promedio` no consulta especie ni sexo; no existe catálogo de compatibilidad indicador–especie/género |
| Impacto | El sistema no distingue entre "no aplica biológicamente" y "faltan datos". Un bovino macho con eventos productivos registrados obtendría un indicador de producción calculado y publicado. Además, el motivo comunicado induce al consumidor a creer que basta con registrar datos para obtener el indicador |
| Reproducibilidad | 100 % — 3/3 ejecuciones sobre el activo 299 |

---

### DEF-G96-03 — La muestra insuficiente responde 200 en lugar de 422

| Campo | Valor |
|---|---|
| Sub-caso | TC-M02-160 |
| Consumidor | `m2m.nuevo@ejemplo.com` (usuario 35), autorizado |
| Activo | 285 `QAJE-IND-1MED` |
| Indicador | Ganancia Diaria de Peso (`ganancia_peso`) |
| Rango | 2026-07-01 → 2026-07-31 |
| Precondición | Exactamente 1 medición de peso en el rango (`210.00 kg`, 2026-07-20) |
| Esperado | `HTTP 422`: "El indicador requiere al menos dos mediciones temporales" |
| Obtenido | `HTTP 200` con `valor: null`, `disponible: false` y advertencia `DATOS_INSUFICIENTES: ganancia_peso requiere al menos 2 mediciones de peso` |
| Evidencia API | assertion V3 fallida (V4 correcta) |
| Evidencia BD | `count(*) = 1` medición `PESO` para el activo 285 |
| ¿Retornó indicador válido? | **No** — la integridad analítica se preserva |
| Categoría | `HTTP_COM` |
| **Severidad** | **Medio** |
| Tiempo máximo | 2 días hábiles |
| **Fecha límite** | **2026-09-14** |
| **Equipo responsable** | **Desarrollo Backend** |
| Causa raíz | `_calcular_ganancia_peso` devuelve `disponible=False` + advertencia en vez de lanzar el error correspondiente |
| Impacto | Un consumidor que se guíe por el código HTTP interpretará la respuesta como un cálculo exitoso. Se mitiga porque el cuerpo señala la causa correctamente y no publica ningún valor, de modo que un consumidor que inspeccione `disponible` no queda expuesto a datos erróneos |
| Reproducibilidad | 100 % — 3/3 ejecuciones sobre el activo 285 |

---

### BLOQUEO — TC-M02-162

| Campo | Valor |
|---|---|
| **Subtipo** | **CONSUMO CERO NO DISPONIBLE** |
| Sub-caso | TC-M02-162 |
| Precondición faltante | Activo y periodo con consumo de alimento registrado igual a `0` |
| Evidencia | `SELECT count(*) FILTER (WHERE cantidad_suministrada = 0) FROM modulo5.registros_consumo_alimentos` → **0** de 16 registros. Ningún activo del rango 279–340 tiene consumo registrado |
| Por qué impide ejecutar | Sin denominador `0` demostrado, cualquier solicitud de `EFICIENCIA` mediría un escenario distinto (ausencia de datos), violando el aislamiento de causa única de §2.C. §7.7 prohíbe modificar registros de alimentación para fabricarlo |
| **Equipo responsable de desbloquear** | **DBA / Implementación** (fixture) · **Desarrollo Backend** (cálculo del indicador) |
| Acción necesaria | Provisionar en TEST un activo con consumo de alimento `0` en un periodo con el resto de variables válidas **y** implementar el cálculo de `conversion_alimenticia`, hoy inhabilitado por completo (ver OBS-G96-03) |

---

### Observaciones registradas

| ID | Descripción | Severidad | Tiempo máx. | Fecha límite | Equipo |
|---|---|---|---|---|---|
| **OBS-G96-01** | El contrato de `/indicadores` no declara `409` ni `500`, los dos códigos que la matriz exige para TC-M02-162 y TC-M02-163. Un cliente generado desde el contrato no contemplaría ninguna de las dos condiciones de rechazo | Medio | 2 días hábiles | **2026-09-14** | Desarrollo Backend |
| **OBS-G96-02** | El contrato expone los indicadores agrupados por familia (`CRECIMIENTO`, `PRODUCCION`, `EFICIENCIA`, `SANITARIO`), no individualmente. No existen los identificadores "Ganancia Diaria de Peso", "Producción de leche" ni "Conversión Alimenticia" que nombra la matriz. La correspondencia se documenta en §2.1, pero conviene alinear matriz y contrato | Bajo | 3 días hábiles | **2026-09-15** | Desarrollo Backend / responsable funcional |
| **OBS-G96-03** | `conversion_alimenticia` se devuelve **siempre** como no disponible (`REQUIERE_M05`). La tabla `modulo5.registros_consumo_alimentos` existe y tiene 16 registros, pero el repositorio de indicadores nunca la consulta. Mientras esto siga así, la regla de división por cero de RF-51 no es demostrable aunque exista el fixture | Medio | 2 días hábiles | **2026-09-14** | Desarrollo Backend |

---

## 11. Declaración de cumplimiento

- ✅ No se modificó código del producto.
- ✅ No hubo `commit`, `push`, `merge`, `rebase` ni cambio de rama.
- ✅ No hubo SQL de escritura: sesión PostgreSQL abierta con `readonly=True`; solo `SELECT`.
- ✅ SETUP = 0 escrituras.
- ✅ Caso principal = 0 escrituras.
- ✅ No se crearon ni eliminaron mediciones (`eventos_crecimeinto`: 50 → 50).
- ✅ No se modificó sexo ni especie de ningún activo.
- ✅ No se puso ningún consumo en `0` (`registros_consumo_alimentos`: 16 → 16, ninguno con valor 0).
- ✅ No se fabricaron outliers: el crecimiento de +500 kg/día del activo 280 era preexistente.
- ✅ Cada sub-caso aisló una única condición; el consumidor autorizado se validó con un control positivo previo.
- ✅ No se inventaron resultados ni evidencias: TC-M02-162 no se ejecutó y se reporta como BLOQUEADO, sin sustituirlo por un escenario aproximado.
- ✅ Las escrituras de `bitacora_auditoria_m02` son del producto, no de QA, y quedan atribuidas en §8.2.

---

## 12. Artefactos

```text
tests/Test_Testing/Test_Modulo2/RF-51/TC-M02-G96/
├── construir_coleccion.cjs          generador determinista de la colección
├── test_tc_m02_g96.json             colección Postman (12 peticiones, 51 assertions)
└── Resultados/
    ├── reporte_tc_m02_g96.html      Newman htmlextra
    ├── reporte_tc_m02_g96.json      Newman JSON
    └── TC-M02-G96_resultado.md      este informe
```

**Resumen Newman:** 12 peticiones · 51 assertions · **45 correctas / 6 fallidas** · duración 5.2 s.
Las 6 fallas son V3 (TC-160), V7 y V8 (TC-161), y V15, V16 y V17 (TC-163) — todas en `01-CASO-PRINCIPAL`. Las 22 assertions de `00-SETUP-LECTURA` y las 6 de `02-DIAGNOSTICO` pasaron íntegramente.
