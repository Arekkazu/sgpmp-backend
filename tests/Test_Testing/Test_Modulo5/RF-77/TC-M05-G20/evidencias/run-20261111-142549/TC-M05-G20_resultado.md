# TC-M05-G20 — Resultado de reevaluación (Reintento 1, `run-20261111-142549`)

| Campo | Valor |
|---|---|
| Caso | TC-M05-G20 — Consolidado y promedio por individuo (TC-M05-014 y TC-M05-015) |
| Requerimiento | RF-77 (Reporte de gastos acumulados por activo, CU04) |
| Endpoints | `POST /suministros/reportes-gastos`, `GET /suministros/reportes-gastos/{id}`, `/historial`, `/{id}/regenerar` |
| Ambiente | TEST (`TEST_BASE_URL` de `.env.test`) |
| Fecha | 2026-11-11 (corrida `run-20261111-142549`) |
| Scripts oficiales | `test_tc_m05_g20.py` (`064297A758AEFC5DD429A7E289ACB836595E1AE98ED4FED13617BBFEDFA08471`), `ejecutar_tc_m05_g20.ps1` (`EC8A453B911A11B87949E0D8985D28E8F6BD4A65C42339B155BA2526A2866EBB`), sin cambios |
| Reportes promovidos | `resultados/resultado_TC-M05-G20_reintento1.html` y `resultados/resultado_TC-M05-G20_reintento1.json` |

---

## 1. Contexto

Reevaluación de **INC-M05-277-G20** (fallo detectado en ronda 1 `run-20261107-204727` en `B02`, donde `gasto_promedio_individuo` retornó `null` en lugar de `"NO_CALCULABLE"`) tras la corrección aplicada en **Dev #963**:

- Respuesta HTTP (`ReporteGastoResponse`): devuelve el literal `"NO_CALCULABLE"` cuando `cantidad_actual = 0`, conservando `causa_no_calculable_promedio`.
- Snapshot persistido (`json_parametros["resumen_promedio"]`): almacena tanto el promedio calculado/no calculable como la causa, sin requerir migración de base de datos.

---

## 2. Control de despliegue

Se separa lo observado directamente en **TEST** frente a la lectura del código fuente local.

### 2.1 Hecho observado en TEST (`GET /openapi.json`)

- `GET {TEST_BASE_URL}/openapi.json` con cabeceras sandbox -> HTTP **200** (`X-Request-ID: 5832b33a-6c81-4fd7-9c68-3a1d7a8c11fe`).
- `components.schemas.ReporteGastoResponse.properties.gasto_promedio_individuo`:
  `{"anyOf": [{"type": "string", "pattern": "^(?!^[-+.]*$)[+-]?0*\\d*\\.?\\d*$"}, {"type": "string", "const": "NO_CALCULABLE"}, {"type": "null"}], "title": "Gasto Promedio Individuo"}`
- `causa_no_calculable_promedio`:
  `{"anyOf": [{"type": "string"}, {"type": "null"}], "title": "Causa No Calculable Promedio"}`
- Cierre sandbox `DELETE /test-control/runs/{run_id}` -> HTTP `404 {"detail":"Run ID no encontrado."}` (`X-Request-ID: 23376cc7-da34-441c-a6cb-7ac553af1829`), dado que `/openapi.json` no abre transacción en BD.
- **Gate aprobado**: `const: "NO_CALCULABLE"` desplegado en TEST.

### 2.2 Lectura de código local (no constituye prueba de despliegue)

- `ReporteGastoResponse` (`src/supplies/infrastructure/schema/reporte_gasto_schema.py`, líneas 49-78): define `gasto_promedio_individuo: Decimal | Literal["NO_CALCULABLE"] | None` y el `@model_validator(mode="after") def representar_promedio_no_calculable`.
- `SqlAlchemyReporteGastoRepository` (`src/supplies/infrastructure/repositories/reporte_gasto_repository.py`, líneas 105-156): persiste y reconstruye `json_parametros["resumen_promedio"]` (`gasto_promedio_individuo` y `causa_no_calculable_promedio`).
- Endpoints en `src/supplies/infrastructure/routers/reporte_gastos_router.py`:
  - `GET /suministros/reportes-gastos/{id_reporte_gasto_acumulado}`
  - `GET /suministros/reportes-gastos/historial` (`limite: int = 20`, `[1..100]`)
  - `GET /suministros/reportes-gastos/{id_reporte_gasto_acumulado}/regenerar`

---

## 3. Evaluación oficial (Reintento 1)

Ejecución del runner oficial [`ejecutar_tc_m05_g20.ps1`](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/tests/Test_Testing/Test_Modulo5/RF-77/TC-M05-G20/ejecutar_tc_m05_g20.ps1) con `-Reintento 1`:

- **Resultado global**: **7 passed / 0 failed / 0 errors / 0 skipped** (`7.23s` pytest / `7.212s` JUnit).
  - `test_00_setup_linea_base` (`1.315s`) -> PASSED
  - `test_a01_consolidado_y_anulacion` (`2.088s`) -> PASSED
  - `test_a02_filtro_categorias_incluidas` (`0.134s`) -> PASSED
  - `test_b01_lote_poblacional_promedio_y_bajas` (`1.036s`) -> PASSED
  - `test_b02_lote_poblacional_baja_total_no_calculable` (`0.894s`) -> PASSED
  - `test_98_cierre_sandbox` (`0.105s`) -> PASSED
  - `test_99_inocuidad_final` (`1.289s`) -> PASSED
- **Aserciones literales de B02 (`test_tc_m05_g20.py`, líneas 638-660)**:
  1. `assert r_rep.status_code == 200`
  2. `total_obtenido = Decimal(str(rep["gasto_total_acumulado"]))` y `assert total_obtenido == Decimal("50000.0000")`
  3. `assert promedio_obtenido == "NO_CALCULABLE"`
  4. `assert causa_obtenida == "La cantidad actual del lote es cero. No es posible calcular el promedio por individuo."` (bloque duplicado en ll. 650-654 y 656-660)
- **Campos observados en B02 (`POST /suministros/reportes-gastos`, reporte `id = 229`, lote P2 `id = 1821`)**:
  - `gasto_total_acumulado`: `"50000.0000"`
  - `cantidad_actual`: no forma parte de `ReporteGastoResponse` (ausente en la respuesta del reporte; en creación `POST /activos-biologicos` el lote registró `detalle_poblacional.cantidad_actual = 50` y la baja descontó `50`)
  - `gasto_promedio_individuo`: `"NO_CALCULABLE"`
  - `causa_no_calculable_promedio`: `"La cantidad actual del lote es cero. No es posible calcular el promedio por individuo."`
  - `nota_bajas`: `"El lote registró 50 bajas durante el período consultado. El gasto promedio por individuo usa la cantidad actual del lote y no la cantidad promedio del período."`
  - `X-Request-ID`: no capturado por `_trazar()` en `trazas_http.jsonl`.
- **Integridad SHA-256 (inicio y cierre)**:
  - `test_tc_m05_g20.py`: `064297A758AEFC5DD429A7E289ACB836595E1AE98ED4FED13617BBFEDFA08471` (sin cambios).
  - `ejecutar_tc_m05_g20.ps1`: `EC8A453B911A11B87949E0D8985D28E8F6BD4A65C42339B155BA2526A2866EBB` (sin cambios).

---

## 4. Diagnóstico del alcance (`P01`–`P09`)

> **Nota**: Ejecutado con `diagnostico_reintento1/diag_promedio.py` (**3/3 PASSED** en `7.79s`). **No constituye reporte oficial**. Lote 1 `id=1824` (50 ind., 50.000 COP), Lote 2 `id=1825` (100 ind., 1.000.000 COP), Activo 853 (10.000 COP medicamento, retiro=0).

| ID | Origen | Esperado | HTTP | `id_rep` | Obtenido | `X-Request-ID` | Estado |
|---|---|---|---|---:|---|---|---|
| `P01` | [especificación] | 200, total 50000, prom 1000 | 200 | 234 | total `"50000.0000"`, prom `"1000.0000"` (`str` Decimal FastAPI), `cant=50` | `0bbacae6-a9bc-4668-80aa-7b7086a5414e` | OK |
| `P02` | [especificación] | 201, `cantidad_actual = 0` | 201 | - | `cantidad_actual = 0`, `id_estado = 6` | `ffc56711-81be-49f2-89ea-651da80593c8` | OK |
| `P03` | [especificación R6] | 200, `"NO_CALCULABLE"`, causa y nota 50 bajas | 200 | 235 | `"NO_CALCULABLE"`, causa spec, nota `"50 bajas"` | `280453eb-3543-47bf-aa74-e0e96512ac4a` | OK |
| `P04` | [contrato Dev] | Snapshot R2 `"NO_CALCULABLE"` + causa | 200 | 235 | `"NO_CALCULABLE"` + causa conservados | `b6652b8b-0095-4ce3-84e2-f114dd2d4404` | OK |
| `P05` | [contrato Dev] | Snapshot R1 prom 1000, sin causa | 200 | 234 | `"1000.0000"`, `causa = null` | `90f64361-0784-46c1-9035-aa1c85db5fce` | OK |
| `P06` | [contrato Dev] | Historial con R1 y R2 de P05/P04 | 200 | 234, 235 | R1 `"1000.0000"` (`null`), R2 `"NO_CALCULABLE"` + causa | `ae6d7010-6682-483d-9faa-9bb43486357e` | OK |
| `P07` | [especificación RNF + Dev] | Regenerar R1: `"NO_CALCULABLE"` + advertencia | 200 | `null` | `"NO_CALCULABLE"` + causa + `advertencia` RNF | `3b3cf5c5-eb38-4304-b4e3-8e136adf62fe` | OK |
| `P08` | [contrato Dev] | Activo INDIVIDUAL 853 -> prom `null` | 200 | 236 | total `"10000.0000"`, prom `null`, `causa = null` | `132d9c54-641d-4c3e-80b7-29db9e72f2ce` | OK |
| `P09` | [caso G20 subcaso 2] | 200, total 1000000, prom 10000 | 200 | 237 | total `"1000000.0000"`, prom `"10000.0000"` (`str` Decimal), `cant=100` | `d1cd5836-1b26-487b-8296-354db56fc35a` | OK |

- **Async/polling (> 12 meses)**: fuera de alcance de este caso (ver `TC-M05-G24`).

---

## 5. Inocuidad y verificación por identificadores

- **Rollback por corrida**:
  - Corrida oficial `tc-m05-g20-adm-20fa8c4f8132`: `DELETE` HTTP **200** `"Rollback exitoso"`; historial `T00` = `20`, `T99` = `20`.
  - Diagnóstico `diag_promedio.py` (3 corridas: base, alcance, final): todas cerradas con `DELETE` HTTP **200** `"Rollback exitoso"`; historial base = `100`, final = `100`.
- **Verificación directa por identificadores (Paso 1 de promoción, corrida `inoc-g20-ids-6c6284201c`, teardown HTTP 200 `"Rollback exitoso"`, `X-Request-ID: c0cd8e22-7fa0-4ff2-a90b-1c6418085e53`)**:
  - Activos `1819`–`1825` (`GET /activos-biologicos/{id}`): todos **HTTP 404** `ACTIVO_NO_ENCONTRADO`:
    - `1819`: `436dbd4c-c132-4b59-a466-c9aa054cee16`
    - `1820`: `7f7bf4d0-b744-40b7-a75b-5b16f8f75629`
    - `1821`: `7e8da218-5b5c-4eb0-9cd8-654f141430ce`
    - `1822`: `32e15eba-113f-4171-91ed-531dde1b516b`
    - `1823`: `00bf3811-5178-44b2-926b-89254f638b05`
    - `1824`: `4c85a44e-a897-4ca0-9e31-79651d5aaaf3`
    - `1825`: `da5927ac-4a27-45ae-b33b-7decfd69a575`
  - Reportes `226`–`237` (`GET /suministros/reportes-gastos/{id}`): todos **HTTP 404** `REPORTE_NO_ENCONTRADO`:
    - `226`: `530d28b7-5bda-4e63-a869-fd796b1f753f`
    - `227`: `03d25bb3-d7b1-4ab0-ac04-c5d70ddb1758`
    - `228`: `5b3ecbd8-b856-46e8-87a9-41356f7b8ec0`
    - `229`: `516cafbd-d179-423d-adbd-301e09a69ea7`
    - `230`: `132095ff-76d6-4396-9cc4-ffef89437df3`
    - `231`: `0b2f71a1-0a38-4451-9270-c5f287a7f0de`
    - `232`: `37a64a86-9e93-46a8-b9ac-8af8aca29067`
    - `233`: `0918b132-2469-402b-8e73-c5ddda3577d5`
    - `234`: `462d19c1-fd46-4fd5-8d83-7934aa7df900`
    - `235`: `f4f6caa4-9e8b-46e7-b313-7ec78c511405`
    - `236`: `ba1c473e-e1ee-41a3-9069-42dd5966333b`
    - `237`: `d825c1ed-8912-4d3c-a7ca-bf4d183dbd8c`
  - Medicamentos del activo `853` (`GET /suministros/medicamentos?id_activo_biologico=853`): **HTTP 200**, `total = 0`, `len = 0` (`X-Request-ID: bab3e5ce-fefe-4838-9d39-daa9f01ccc16`), coincidente con la línea base de G14.
- **Limitación del conteo de historial**: tanto `T00`/`T99` (`limite` por defecto `20`) como el diagnóstico (`limite=100`) devuelven un conteo topado y no discriminan identidades si existen más registros previos; por ello se complementó con la verificación directa por IDs.

---

## 6. Veredicto

- **Veredicto oficial**: **Aprobado** (`7/7` en Reintento 1, `run-20261111-142549`).
- **INC-M05-277-G20**: **corregido y verificado en TEST el 2026-11-11**.

---

## 7. Notas y deuda técnica

- La **observación 8** de `INFORME_FASE234_TC-M05-G20.txt` (*"`gasto_promedio_individuo` está tipado como Decimal nullable... imposibilitando `NO_CALCULABLE`"* ) quedó **RESUELTA** por **Dev #963**.
- El anexo del script en `INFORME_FASE234_TC-M05-G20.txt` fue alterado por el sanitizador del runner (reemplazando el prefijo JWT de 3 caracteres por `'***REDACTED***'`); la copia fiel es `test_tc_m05_g20.py` del repositorio (`064297A758AEFC5DD429A7E289ACB836595E1AE98ED4FED13617BBFEDFA08471`).
- **Deuda técnica del script/runner (no corregida en este reintento)**:
  1. `ejecutar_tc_m05_g20.ps1` promueve automáticamente reportes a `resultados/` al terminar.
  2. El sanitizador del runner reescribe artefactos en staging (incluido el código anexado).
  3. `test_99_inocuidad_final` inicia sesión fuera del sandbox y compara un listado de historial topado (`limite` por defecto 20).
  4. `test_b02_lote_poblacional_baja_total_no_calculable` tiene duplicado el bloque `assert causa_obtenida == causa_esperada` (ll. 650-660) y un docstring desactualizado (`None/'NO_CALCULABLE'`).

---

## 8. Archivos resultantes

Rutas relativas a `tests/Test_Testing/Test_Modulo5/RF-77/TC-M05-G20/`:

- **`resultados/`**:
  - `resultados/.gitkeep`
  - `resultados/resultado_TC-M05-G20.html` — histórico ronda 1 (`Rechazado`), sin cambios.
  - `resultados/resultado_TC-M05-G20.json` — histórico ronda 1 (`6 OK / 1 FALLA`), sin cambios.
  - `resultados/resultado_TC-M05-G20_reintento1.html` — reporte oficial promovido (`7/7 Passed`).
  - `resultados/resultado_TC-M05-G20_reintento1.json` — reporte oficial regenerado desde JUnit y trazas (`7/7 OK`, `Aprobado`).
- **`evidencias/run-20261111-142549/`**:
  - `resultado_TC-M05-G20_reintento1.html`, `resultado_TC-M05-G20_reintento1.json`, `resultado_TC-M05-G20_reintento1.xml` (JUnit XML conservado en evidencias).
  - `console_execution.log`, `trazas_http.jsonl`, `repro`, `INFORME_FASE234_TC-M05-G20.txt`.
  - `gen_json_resultado.py` — regenerador del JSON promovido.
  - `TC-M05-G20_resultado_generado.md` — respaldo del narrativo generado por el runner.
  - `TC-M05-G20_resultado.md` — este narrativo reescrito.
  - `INFORME_REEVALUACION_G20.txt` e `INFORME_PROMOCION_G20.txt`.
  - `diagnostico_reintento1/` (`diag_promedio.py`, `diag_resultados.json`, `console_diag.log`).
