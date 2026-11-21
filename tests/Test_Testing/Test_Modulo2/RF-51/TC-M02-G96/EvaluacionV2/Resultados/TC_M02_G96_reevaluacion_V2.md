# REEVALUACIÓN V2 — TC-M02-G96

## 0. Resumen ejecutivo

| Elemento | Resultado |
|---|---|
| RF / CU | RF-51 — Generación de Indicadores Zootécnicos / CU12 |
| Subcasos | TC-M02-160, TC-M02-161, TC-M02-162 (reformulado), TC-M02-163 |
| Rama / HEAD | `qa/juan-esteban-re-evaluacion-m02` / `a6220fc82e8d92eae1bb16f5cf01fca76b1c8a0c`. Tras `git fetch origin`, `HEAD...origin/test` = `0 0` |
| Ambiente | TEST |
| Ejecutable | Variante V2 `EvaluacionV2/test_tc_m02_g96_v2.json` con los criterios V2 (§1 y §2.4) |
| Newman | 1 ejecución · 14 peticiones · **71 aserciones · 71 correctas · 0 fallidas** (V1: 51 aserciones, 45 correctas y 6 fallidas) |
| TC-M02-160 | ✅ 422 `INDICADOR_NO_DISPONIBLE`, `DATOS_INSUFICIENTES`. **CORREGIDO** |
| TC-M02-161 | ✅ 400 `INDICADOR_NO_APLICABLE_SEXO`. **CORREGIDO** |
| TC-M02-162 | ✅ 422 `INDICADOR_NO_DISPONIBLE`, sin consumo VALIDADO en kg en M05. **BLOQUEO RESUELTO + APROBADO** |
| TC-M02-163 | ✅ 422 `INDICADOR_NO_DISPONIBLE` + `OUTLIER_CRITICO`, sin publicar +500 kg/día. **CORREGIDO** |
| Hallazgos V1 | DEF-G96-01, 02 y 03: **CORREGIDOS** · Bloqueo TC-162: **RESUELTO** · OBS-G96-01, 02 y 03: **RESUELTAS** |
| Persistencia de dominio | **NO**: Δ = 0 en los fixtures y en las tablas globales |
| Auditoría RF-51 | +2 `INDICADOR_CALCULADO`, de las consultas exitosas del activo 279. Los rechazos no generan registro |
| Regresiones | Ninguna |
| **Veredicto** | ✅ **APROBADO — CORREGIDO / SIN REGRESIÓN** (V1: RECHAZADO) |

---

## 1. Ajuste formal de criterio V2

> **AJUSTE DE CRITERIO V2**
>
> TC-M02-162 y TC-M02-163 fueron reformulados para alinearse con el contrato real de RF-51 y con la corrección documentada por Desarrollo (INC-M02-98-G96 / Issue #246 / PR #271).
>
> V1 se conserva intacta.
>
> TC-M02-162 ya no se formula como "consumo = 0 / división por cero", porque M05 exige cantidad > 0 y la fórmula FCR utiliza el consumo como numerador. V2 verifica la ausencia de consumo VALIDADO en kg dentro del periodo sobre un activo con crecimiento suficiente y válido.
>
> TC-M02-163 adopta 422 INDICADOR_NO_DISPONIBLE + OUTLIER_CRITICO como respuesta esperada, preservando como criterio esencial que el valor atípico nunca sea publicado como válido.

### TC-162

- **Criterio histórico:** `409` por "consumo = 0 / división por cero".
- **Por qué se sustituye:** `FCR = kg alimento / kg ganancia`. El consumo es el **numerador**, así que un consumo de 0 no produce división por cero. Además, M05 impide registrar cantidades ≤ 0: el trigger `trg_calcular_costo_total_consumo` (BEFORE INSERT) está habilitado en TEST (`tgenabled = 'O'`) y el DTO exige `cantidad_alimento > 0`.
- **Criterio V2:** en un activo con crecimiento válido y sin consumos VALIDADO en kg en el periodo, la respuesta es `422 INDICADOR_NO_DISPONIBLE`.

### TC-163

- **Criterio histórico:** `500`, heredado del prototipo funcional.
- **Criterio V2:** `422 INDICADOR_NO_DISPONIBLE` + `OUTLIER_CRITICO` y **no publicación** del valor atípico. El `422` no es un defecto.

### Preservación de V1

`test_tc_m02_g96.json`, `construir_coleccion.cjs` y `Resultados/` de V1 no se modificaron: `git diff HEAD` sobre la carpeta está vacío y las fechas de modificación son del 2026-09-12. El generador V1 no se ejecutó. En el repositorio los archivos se llaman `construir_coleccion.cjs` y `TC-M02-G96_resultado.md`; los nombres "(7)" y "(2)" del paquete corresponden a las copias adjuntadas.

---

## 2. Gate

### Rama

| Verificación | Resultado |
|---|---|
| `git branch --show-current` | `qa/juan-esteban-re-evaluacion-m02` ✅ |
| `git rev-parse HEAD` | `a6220fc82e8d92eae1bb16f5cf01fca76b1c8a0c` ✅ |
| `git fetch origin` · `HEAD...origin/test` | `origin/test` = `a6220fc8` · `0 0` ✅ |
| `git status --short` | Sin cambios en archivos versionados. Solo aparecen carpetas `EvaluacionV2/` sin seguimiento |

### OpenAPI

`GET /openapi.json` → 200. `GET /activos-biologicos/{id_activo}/indicadores`:

- **Respuestas declaradas:** `200, 400, 401, 403, 404, 422` ✅
- **`tipo_indicador`:** `CRECIMIENTO | PRODUCCION | SANITARIO | EFICIENCIA | TODOS` ✅
- No hay enumeración por indicador individual. Único método: GET.

### Principal autorizado

`m2m.nuevo@ejemplo.com` (usuario 35, propietario de la finca 57), igual que en V1. Se obtuvo un JWT nuevo en el login de la colección (`sub` = 35, afirmado). El **control positivo** `GET /activos-biologicos/279/indicadores?tipo_indicador=CRECIMIENTO` devolvió **200** antes del grupo. La contraseña se inyectó con `--env-var password` y la variable de la colección V2 quedó vacía. Los reportes se redactaron (§14).

### Fixtures (BD solo lectura, `transaction_read_only = on`, 2026-09-19 17:48 UTC)

| Activo | Identificador | Tipo | Especie | Sexo | Estado | Infra / finca | Nacimiento / inicio de ciclo |
|---:|---|---|---|---|---|---|---|
| 285 | QAJE-IND-1MED | INDIVIDUAL | Bovino Qa Je | Hembra | ACTIVO | 52 / 57 | 2026-01-15 / 2026-06-01 |
| 299 | QAJE-IND-MACHO | INDIVIDUAL | Bovino Qa Je | **Macho** | ACTIVO | 48 / 57 | 2026-01-15 / 2026-06-01 |
| 295 | QAJE-DAT-COMPL | INDIVIDUAL | Bovino Qa Je | Hembra | ACTIVO | 48 / 57 | 2026-01-15 / 2026-06-01 |
| 280 | QAJE-IND-OUTLIER | INDIVIDUAL | Bovino Qa Je | Hembra | ACTIVO | 52 / 57 | 2026-01-15 / 2026-06-01 |

Todos los rangos son posteriores al nacimiento y al inicio de ciclo, así que la validación `RANGO_FUERA_DE_CICLO_VIDA` no interfiere. Los cuatro fixtures son los mismos de V1 y no se sustituyó ninguno.

### Integridad V1

Ver §1 (preservación de V1).

### Variante V2 (diff V1 → V2)

`EvaluacionV2/test_tc_m02_g96_v2.json` (`--no-filters` `d3d687457b3c3af6e6a3cd38d6941e564025cd23`) se generó desde la V1 (`5cf76c05…`) con un script externo. Cambios lógicos, comparados petición por petición:

| Ubicación | Cambio |
|---|---|
| `info` | Nombre y descripción V2 con los criterios nuevos |
| Variable `password` | Se vacía (`''`); se inyecta con `--env-var` |
| SETUP · OpenAPI | Las 2 aserciones "el contrato **no** declara 409/500" se sustituyen por "el contrato **declara** 422" (TC-160/162/163) y "declara 400" (TC-161) — OBS-G96-01 |
| SETUP · nuevo | `Datos TC-M02-162 - activo 295 …`: GET `/295/ficha-integral` (ACTIVO, accesible) |
| SETUP · nuevo | `Datos TC-M02-162 - historial …`: GET `/295/historial` (2 eventos de crecimiento en el rango) y cálculo QA de GDP = 0.9677 kg/día |
| TC-M02-160 | Sin cambios en lo existente (ya esperaba 422). Se añaden `error_code = INDICADOR_NO_DISPONIBLE`, mensaje `DATOS_INSUFICIENTES` con "al menos 2 mediciones" y ningún indicador publicado |
| TC-M02-161 | Sin cambios en lo existente (ya esperaba 400). Se añaden `error_code = INDICADOR_NO_APLICABLE_SEXO`, `field = tipo_indicador`, mensaje con `PRODUCCION` y `Macho` (sin `DATOS_INSUFICIENTES`) y ningún indicador publicado |
| TC-M02-162 · **nuevo oficial** | `GET /295/indicadores?tipo_indicador=EFICIENCIA&fecha_inicio=2026-07-15&fecha_fin=2026-08-15`, con las aserciones V1–V9 de §30 del paquete |
| TC-M02-163 | `V15: HTTP 500` pasa a `V15 (V2): HTTP 422`. La aserción A11/A12, que leía `variables_usadas` de un indicador que el 422 ya no devuelve, se sustituye por la trazabilidad del mensaje (`500.0000 kg/dia`). Se añaden `error_code`, `OUTLIER_CRITICO` y la ausencia de indicadores `disponible = true` |
| DIAGNÓSTICO | Se **retira** `DIAG TC-M02-162` (esperaba `REQUIERE_M05`, obsoleto). Se conserva el control positivo del activo 279 |

No cambian los endpoints, los fixtures ni los rangos de 160, 161 y 163, las aserciones de rango, ID ni autorización, ni los controles anti-NaN, anti-Infinity y anti-traza.

---

## 3. TC-M02-160

### Fixture

Activo 285, con **1** PESO en 2026-07-01 → 2026-07-31: evento 222, 210.00 kg, 2026-07-20. El SETUP de la colección lo confirma por historial (1 evento en rango).

### Respuesta

`GET /activos-biologicos/285/indicadores?tipo_indicador=CRECIMIENTO&fecha_inicio=2026-07-01&fecha_fin=2026-07-31` → **HTTP 422** (142 ms):

```json
{"error_code":"INDICADOR_NO_DISPONIBLE",
 "message":"DATOS_INSUFICIENTES: ganancia_peso requiere al menos 2 mediciones de peso.","fields":[]}
```

Aserciones V1–V8: **10/10**. No se publica ningún valor ni hay NaN, Infinity ni traza.

### DEF-G96-03

- **V1:** HTTP 200 con `disponible = false`.
- **V2:** HTTP 422 `INDICADOR_NO_DISPONIBLE`.
- **CORREGIDO.**

---

## 4. TC-M02-161

### Fixture

Activo 299: INDIVIDUAL, **Macho**, Bovino Qa Je, ACTIVO y accesible (SETUP `ficha-integral`: especie bovina, sexo Macho, ACTIVO).

### Respuesta

`GET /activos-biologicos/299/indicadores?tipo_indicador=PRODUCCION` → **HTTP 400** (140 ms):

```json
{"error_code":"INDICADOR_NO_APLICABLE_SEXO",
 "message":"El indicador 'PRODUCCION' no aplica biológicamente a un activo de sexo Macho.",
 "fields":[{"field":"tipo_indicador","message":"..."}]}
```

Aserciones V1–V6: **11/11**. La causa ya no es `DATOS_INSUFICIENTES` sino la incompatibilidad biológica.

### DEF-G96-02

- **V1:** HTTP 200, `DATOS_INSUFICIENTES`.
- **V2:** HTTP 400 `INDICADOR_NO_APLICABLE_SEXO`.
- **CORREGIDO.**

---

## 5. TC-M02-162

### Fixture 295

`QAJE-DAT-COMPL`: ACTIVO, infraestructura 48 (`Corral QA JE Origen`), finca 57 (`Finca QA Juan Esteban`), propietario el usuario 35.

### Pesos

| Evento | Fecha | Peso |
|---:|---|---:|
| 224 | 2026-07-15 10:00:00+00 | 200.00 kg |
| 225 | 2026-08-15 10:00:00+00 | 230.00 kg |

### Ganancia

Cálculo independiente de QA: ganancia neta = 230 − 200 = **+30 kg** en **31 días**, así que la GDP es 30/31 = **0.9677 kg/día**. Hay 2 mediciones, la ganancia es positiva, la GDP es plausible (< 10 kg/día) y no hay outlier.

### Consumos M05

Misma consulta que usa RF-51: `estado_registro = 'VALIDADO'`, `tipo_unidad` en kg y `fecha_consumo` entre 2026-07-15 y 2026-08-15, para el activo 295.

```sql
SELECT count(*), COALESCE(sum(cantidad_suministrada),0) FROM modulo5.registros_consumo_alimentos
 WHERE id_activo_biologico=295 AND estado_registro='VALIDADO' AND lower(tipo_unidad) IN ('kg','kilogramo','kilogramos')
   AND fecha_consumo >= '2026-07-15' AND fecha_consumo <= '2026-08-15';   -- 0 | 0
```

El activo 295 no tiene **ningún** registro de consumo, de ningún tipo. El único consumo no positivo de la tabla es el id 23 (activo 1, −9.000, `ANULADO`, `fecha_consumo NULL`), que no participa en RF-51. No se insertó nada.

### Respuesta RF-51

`GET /activos-biologicos/295/indicadores?tipo_indicador=EFICIENCIA&fecha_inicio=2026-07-15&fecha_fin=2026-08-15` → **HTTP 422** (142 ms):

```json
{"error_code":"INDICADOR_NO_DISPONIBLE",
 "message":"DATOS_INSUFICIENTES: no hay consumo de alimento (kg) validado en el modulo M05 para el periodo solicitado.",
 "fields":[]}
```

| Verificación | Resultado |
|---|---|
| V1 · HTTP 422 | ✅ |
| V2 · `INDICADOR_NO_DISPONIBLE` | ✅ |
| V3 · ausencia de consumo validado | ✅ |
| V4 · referencia a M05 o al consumo de alimento | ✅ (no `REQUIERE_M05` ni "no implementado") |
| V5 · ningún FCR válido publicado | ✅ |
| V6/V7 · sin Infinity ni NaN | ✅ |
| V8 · no es 500 | ✅ |
| V9 · sin traza interna | ✅ |

Aserciones: **9/9**.

**Interpretación:** RF-51 **sí consulta** los datos de M05. Para el activo 295 no existen consumos VALIDADO en kg en el periodo, así que RF-51 no puede publicar un FCR y responde correctamente `422 INDICADOR_NO_DISPONIBLE`. Este 422 es el resultado esperado: **TC-M02-162 APROBADO**.

### Evolución del bloqueo

- **V1:** BLOQUEADO (no existía consumo = 0 y `conversion_alimenticia` devolvía `REQUIERE_M05`).
- **V2:** con el criterio reformulado y el fixture 295, el subcaso es ejecutable.
- **BLOQUEO RESUELTO**, y el resultado funcional es **APROBADO**.

### OBS-G96-03

- **V1:** `conversion_alimenticia` devolvía siempre `REQUIERE_M05` y no consultaba `modulo5.registros_consumo_alimentos`.
- **V2:** la respuesta real identifica la ausencia de consumo VALIDADO en kg en M05, y no aparece `REQUIERE_M05`. El código actual calcula `FCR = kg alimento VALIDADO / kg ganancia neta` consultando esa tabla con los mismos filtros usados en el gate.
- **OBSERVACIÓN RESUELTA.** No se ejecutó el control positivo de FCR (opcional, §26). Los únicos activos con consumo VALIDADO > 0 son el 1, 5, 8 y 57, de fincas ajenas al usuario 35 y sin pesos en los mismos periodos, y no se insertó consumo para fabricarlo.

---

## 6. TC-M02-163

### Fixture

Activo 280: 10.00 kg (evento 220, 2026-08-01 10:00Z) → 510.00 kg (evento 221, 2026-08-02 10:00Z), con 2 mediciones en el rango (confirmado en SETUP).

### Cálculo QA

(510 − 10) / 1 = **+500 kg/día**, muy por encima del umbral de plausibilidad de la implementación (10 kg/día). G96 no evalúa el umbral exacto, solo que +500 se detecte y no se publique.

### Respuesta

`GET /activos-biologicos/280/indicadores?tipo_indicador=CRECIMIENTO&fecha_inicio=2026-08-01&fecha_fin=2026-08-02` → **HTTP 422** (139 ms):

```json
{"error_code":"INDICADOR_NO_DISPONIBLE",
 "message":"OUTLIER_CRITICO: el valor calculado (500.0000 kg/dia) excede el umbral de plausibilidad biologica y no se publica como valido. Requiere revision manual de las mediciones de peso registradas.",
 "fields":[]}
```

### OUTLIER_CRITICO

| Verificación | Resultado |
|---|---|
| V1 · HTTP 422 | ✅ |
| V2 · `INDICADOR_NO_DISPONIBLE` | ✅ |
| V3 · `OUTLIER_CRITICO` presente | ✅ |
| V4 · +500 no publicado como indicador válido | ✅ (no hay array `indicadores`; el valor solo aparece como trazabilidad dentro del mensaje de error) |
| V5 · ningún `disponible = true` | ✅ |
| V6/V7 · sin NaN ni Infinity | ✅ |
| V8 · sin traza | ✅ |

La trazabilidad del mensaje (`500.0000 kg/dia`) coincide con el cálculo independiente de QA. Aserciones: **12/12**.

### DEF-G96-01

- **V1:** HTTP 200, `valor = 500.0000`, `disponible = true`, `advertencias = []`.
- **V2:** HTTP 422 `OUTLIER_CRITICO`, sin publicación.
- **CORREGIDO.**

---

## 7. OBS-G96-01

- **V1:** el OpenAPI no declaraba 409 ni 500, los códigos que exigía la matriz histórica para TC-162 y TC-163.
- **V2:** los criterios ya no exigen esos códigos (§1). El contrato vivo declara **422** (TC-160/162/163) y **400** (TC-161), y lo afirma el SETUP de la colección V2.
- **OBSERVACIÓN RESUELTA POR ALINEACIÓN DEL CRITERIO.**

## 8. OBS-G96-02

- **V1:** la matriz nombraba indicadores individuales ("Ganancia Diaria de Peso", "Producción de leche", "Conversión Alimenticia"), mientras que la API expone familias.
- **V2:** la colección y este informe usan exclusivamente los valores reales del contrato, con esta equivalencia:

| Indicador (matriz) | `tipo_indicador` (contrato) | Indicador devuelto |
|---|---|---|
| Ganancia Diaria de Peso | `CRECIMIENTO` | `ganancia_peso` |
| Producción de leche | `PRODUCCION` | `produccion_promedio` |
| Conversión Alimenticia | `EFICIENCIA` | `conversion_alimenticia` |

- **OBSERVACIÓN RESUELTA en la documentación V2.** Si la matriz externa conserva los nombres antiguos, la equivalencia anterior es la referencia.

---

## 9. Persistencia de dominio

Snapshot en solo lectura antes (17:48:11Z) y después (17:50:44Z) de Newman (17:50:23–17:50:27Z), con el SHA-256 de las filas completas:

| Conjunto | Filas | Hash PRE | Hash POST | Δ |
|---|---:|---|---|---|
| Fixtures · `activos_biologicos` (279, 280, 285, 295, 299) | 5 | `0e9edb00930c21b6` | `0e9edb00930c21b6` | **0** |
| Fixtures · `eventos_activos` | 10 | `3baf3cd5ce215367` | `3baf3cd5ce215367` | **0** |
| Fixtures · `eventos_crecimeinto` | 10 | `4848a63977a9674e` | `4848a63977a9674e` | **0** |
| Fixtures · `detalles_activos_individuales` (sexo, especie) | 5 | `3a4430e0ff6746df` | `3a4430e0ff6746df` | **0** |
| Fixtures · `registros_consumo_alimentos` | 0 | `4f53cda18c2baa0c` | `4f53cda18c2baa0c` | **0** |
| Global · `eventos_crecimeinto` | 72 | `174fb9b7fa7c2168` | `174fb9b7fa7c2168` | **0** |
| Global · `eventos_activos` | 183 | `80b6707107f578d6` | `80b6707107f578d6` | **0** |
| Global · `modulo5.registros_consumo_alimentos` | 16 | `e35cbdc51fcb4db8` | `e35cbdc51fcb4db8` | **0** |
| Global · `activos_biologicos` | 379 | `50d530b598399d6e` | `50d530b598399d6e` | **0** |
| Global · `detalles_activos_individuales` | 260 | `7fb2b35dd7333ca7` | `7fb2b35dd7333ca7` | **0** |

**Δ dominio = 0.** No se insertaron, actualizaron ni borraron pesos, consumos, sexo, especie ni estados.

## 10. Auditoría

`modulo2.bitacora_auditoria_m02` con `rf_origen='RF51'`: **45 → 47 (+2)**.

| id_bitacora | tipo_evento | resultado | activo | usuario | detalle |
|---:|---|---|---:|---:|---|
| 3100 | `INDICADOR_CALCULADO` | EXITOSO | 279 | 35 | `{"tipo_indicador": "CRECIMIENTO"}` (control positivo A1) |
| 3107 | `INDICADOR_CALCULADO` | EXITOSO | 279 | 35 | `{"tipo_indicador": "CRECIMIENTO"}` (diagnóstico de control) |

Las cuatro solicitudes oficiales (422/400/422/422) **no generan** registro RF-51: el caso de uso lanza el error antes del registro de auditoría, que solo se hace en cálculos exitosos. El login actualiza `ultimo_acceso`. Todo esto es escritura técnica y **no persistencia funcional**.

---

## 11. Comparación V1 ↔ V2

| Subcaso | V1 | V2 | Evolución |
|---|---|---|---|
| TC-M02-160 | 200, `disponible = false` — RECHAZADO | 422 `INDICADOR_NO_DISPONIBLE` (`DATOS_INSUFICIENTES`) — APROBADO | **CORREGIDO** |
| TC-M02-161 | 200, `DATOS_INSUFICIENTES` — RECHAZADO | 400 `INDICADOR_NO_APLICABLE_SEXO` — APROBADO | **CORREGIDO** |
| TC-M02-162 | BLOQUEADO (sin consumo = 0; `REQUIERE_M05`) | 422 `INDICADOR_NO_DISPONIBLE` por ausencia de consumo VALIDADO en kg en M05 — APROBADO | **BLOQUEO RESUELTO + APROBADO** |
| TC-M02-163 | 200 + outlier publicado como válido — RECHAZADO | 422 `INDICADOR_NO_DISPONIBLE` + `OUTLIER_CRITICO`, sin publicación — APROBADO | **CORREGIDO** |

| Hallazgo | Relación | V1 | V2 | Evolución |
|---|---|---|---|---|
| DEF-G96-01 | DIRECTO TC-163 | Abierto | 422 + `OUTLIER_CRITICO`, no publicado | **CORREGIDO** |
| DEF-G96-02 | DIRECTO TC-161 | Abierto | 400 `INDICADOR_NO_APLICABLE_SEXO` | **CORREGIDO** |
| DEF-G96-03 | DIRECTO TC-160 | Abierto | 422 `INDICADOR_NO_DISPONIBLE` | **CORREGIDO** |
| Bloqueo TC-162 | DIRECTO | Bloqueado | Criterio reformulado + fixture 295 → ejecutado y aprobado | **BLOQUEO RESUELTO** |
| OBS-G96-01 | COLATERAL contractual | Abierta | El contrato declara 422/400; V2 ya no exige 409/500 | **RESUELTA POR ALINEACIÓN** |
| OBS-G96-02 | COLATERAL documental | Abierta | V2 usa los valores del contrato y documenta la equivalencia | **RESUELTA** |
| OBS-G96-03 | COMPLEMENTARIA TC-162 | Abierta | RF-51 consulta M05; mensaje real de ausencia de consumo, sin `REQUIERE_M05` | **RESUELTA** |

| Ejecución | V1 | V2 |
|---|---|---|
| Newman | 12 peticiones · 51 aserciones · 45 correctas / 6 fallidas · 3/4 solicitudes oficiales | 14 peticiones · 71 aserciones · **71 / 0** · **4/4 solicitudes oficiales** |

---

## 12. Regresiones

No se identificaron regresiones. El control positivo del activo 279 sigue calculando y publicando `ganancia_peso` con `disponible = true` (A1 y diagnóstico: 200).

---

## 13. Veredicto final

# ✅ APROBADO — CORREGIDO / SIN REGRESIÓN

- TC-M02-160 → 422 `INDICADOR_NO_DISPONIBLE` (**CORREGIDO**, DEF-G96-03)
- TC-M02-161 → 400 `INDICADOR_NO_APLICABLE_SEXO` (**CORREGIDO**, DEF-G96-02)
- TC-M02-162 → 422 `INDICADOR_NO_DISPONIBLE`, sin consumo VALIDADO en M05 (**APROBADO**, bloqueo V1 **RESUELTO**)
- TC-M02-163 → 422 `INDICADOR_NO_DISPONIBLE` + `OUTLIER_CRITICO`, sin publicación (**CORREGIDO**, DEF-G96-01)
- Δ dominio = 0. OBS-G96-01, 02 y 03 **RESUELTAS**.

Evolución del caso: **RECHAZADO (V1) → APROBADO (V2)**, bajo los criterios V2 formalmente ajustados (§1).

---

## 14. Integridad

- ✅ **V1 intacta:** `git diff HEAD` vacío sobre la carpeta G96. `construir_coleccion.cjs`, `test_tc_m02_g96.json` y `Resultados/` no se modificaron, y el generador V1 no se ejecutó.
- ✅ **Newman se ejecutó una sola vez** (2026-09-19, 17:50:23–17:50:27 UTC). Solo GET, más el `POST /sesiones/` de autenticación.
- ✅ **Secretos protegidos:** la contraseña se inyectó con `--env-var` (vacía en la colección V2). En el HTML se ocultaron la cabecera `Authorization` y los cuerpos del login. En el JSON se redactaron 12 JWT y 2 apariciones de la contraseña, sin que quede ninguna.
- ✅ **BD TEST solo en lectura** (`transaction_read_only = on`): únicamente `SELECT`.
- ✅ **Sin inserts:** no se creó consumo cero ni negativo, no se modificaron M02 ni M05, pesos, sexo, especie ni estados.
- ✅ No se exigió 409 en TC-162 ni 500 en TC-163, y no se aceptó `REQUIERE_M05` como correcto.
- ✅ DEV no se usó. No se modificó código productivo, no se hizo commit, push, merge, rebase ni deploy, y no se crearon tickets.
- ✅ Artefactos V2:
  - `EvaluacionV2/test_tc_m02_g96_v2.json`;
  - `EvaluacionV2/Resultados/reporte_tc_m02_g96_v2.json`, redactado;
  - `EvaluacionV2/Resultados/reporte_tc_m02_g96_v2.html`;
  - este informe.
