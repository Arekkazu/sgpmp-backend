# TC-M05-G14 — Resultado de reevaluación (Reintento 1, `run-20261111-140320`)

| Campo | Valor |
|---|---|
| Caso | TC-M05-G14 — Rechazo de campos obligatorios y valores límite en el registro de medicamentos |
| Requerimiento | RF-76 (Registro de aplicación de medicamentos) |
| Caso de uso | CU03 |
| Endpoint | `POST /suministros/medicamentos` |
| Ambiente | TEST (`TEST_BASE_URL` de `.env.test`) |
| Fecha | 2026-11-11 (corrida `run-20261111-140320`) |
| Activo | 853 (`INDIVIDUAL`, `id_estado=1`, `periodo_retiro_dias=0` en todos los POST) |
| Scripts oficiales | `test_tc_m05_g14.py` (`A693E2DF2229EB52501079E9BC9365B39E084C52C2C87699067DB2F8079B680D`), `ejecutar_tc_m05_g14.ps1` (`01EEA075BAEC9150E3683F18BCF84161C14DCF1E8497D3732E0E83045829D536`), sin cambios |
| Reportes promovidos | `resultados/resultado_TC-M05-G14_reintento1.html` y `resultados/resultado_TC-M05-G14_reintento1.json` |

---

## 1. Contexto

Reevaluación de **INC-M05-270-G14** (registrado en ronda 1 `run-20261107-105918` por fallo HTTP 500 `ERROR_INTERNO` en B03 `dosis_aplicada=0.0001`) tras la corrección aplicada en **Dev #954**:

- **Migración `d2e71a4c980b`**: amplía `modulo5.registros_medicamentos.cantidad` de `numeric(10,3)` a `numeric(10,4)` (recreando la vista `modulo5.vw_m05_aplicacion_medicamentos`).
- **DTO (`RegistrarMedicamentoDTO`)**: `dosis_aplicada` con `max_digits=10` y `decimal_places=4`.
- **Traductor de errores (`src/shared/db_error_translator.py`)**: mapea el `P0001` del trigger `modulo5.fn_trg_calcular_costo_total_medicamento` (`CANTIDAD_INVALIDA` / `COSTO_INVALIDO`) a HTTP **400** `VAL_ENTRADA`.

---

## 2. Control de despliegue

Se separa estrictamente lo observado en el ambiente **TEST** (consultas `SELECT` de solo lectura vía `POST /test-control/query` dentro de corrida sandbox cerrada con `DELETE` 200) de la lectura del código fuente local.

### 2.1 Hechos observados en TEST

- **Columna objetivo** (`X-Request-ID: 152df084-0762-4a02-a9f3-00f2c4957706`):
  - `modulo5.registros_medicamentos.cantidad`: `data_type=numeric`, `numeric_precision=10`, `numeric_scale=4` (**Gate aprobado**).
- **Versión Alembic en TEST** (`X-Request-ID: cf854b29-e5c5-45b6-aad3-9f31ea9e3d22`, `0396fa0d-6855-4675-b492-2ce6dbdc82ed`):
  - `public.alembic_version.version_num = "143fa2eda4fc"`.
- **Precisión y escala de columnas relacionadas en `modulo5`** (`X-Request-ID: b9c0ab96-537f-48fd-90b8-c1e963d68e88`):
  - `registros_medicamentos.cantidad`: `numeric(10, 4)`
  - `registros_medicamentos.costo_unitario_medicamento`: `numeric(10, 4)`
  - `registros_medicamentos.costo_total_medicamento`: `numeric(12, 4)`
  - `registros_medicamentos.dosis_por_individuo`: `numeric(10, 4)`
  - `registro_suministro.cantidad`: `numeric(10, 4)`
  - `registro_suministro.precio_unitario_resuelto`: `numeric(10, 2)`
  - `registro_suministro.costo_registro`: `numeric(14, 4)`
  - `acumulado_ciclo.acumulado_total_ciclo`: `numeric(16, 4)`
  - `auditorias_suministros.costo_afectado`: `numeric(16, 4)`
  - `reporte_gastos_acumulados.{total_costo_alimento, total_costo_medicamento, total_costo_directo}`: `numeric(16, 4)`

### 2.2 Lectura de código local (no constituye prueba de despliegue)

- `alembic/versions/d2e71a4c980b_rf76_precision_dosis_cuatro_decimales.py` existe y es ancestro de `143fa2eda4fc` (head local).
- `src/supplies/infrastructure/models/registro_medicamento_model.py` (línea 60) define `cantidad` como `Numeric(10, 4)`.
- `src/supplies/infrastructure/dto/registrar_medicamento_dto.py` define `dosis_aplicada: Decimal = Field(max_digits=10, decimal_places=4, ...)`.
- `src/shared/db_error_translator.py` (líneas 92-100) traduce `(P0001, modulo5.fn_trg_calcular_costo_total_medicamento)` (`CANTIDAD_INVALIDA` y `COSTO_INVALIDO`) a `ValidationError` 400 `VAL_ENTRADA`.

---

## 3. Evaluación oficial (Reintento 1)

Ejecución sin cambios del runner oficial `ejecutar_tc_m05_g14.ps1 -Reintento 1 -ActivoId 853`:

- **Resultado global**: **30 tests ejecutados: 30 passed / 0 failed / 0 errors / 0 skipped** (duración `18.042s` JUnit / `18.11s` pytest).
  - Infraestructura: **5/5 PASSED** (`test_00_inocuidad_linea_base`, `test_01_preparacion`, `test_a17_estado_activo_tras_grupo_a`, `test_zz_cierre_corrida_principal`, `test_zz_inocuidad_final`).
  - Subcaso A (`A01`–`A16`): **16/16 PASSED**.
  - Subcaso B (`B01`–`B09`): **9/9 PASSED**.
- **Aserciones verificadas en B03 (`test_zz_b03_dosis_minima[B03-dosis_0.0001]`)**:
  B03 no verifica únicamente HTTP 201; en `_assert_registro_valido` y `test_zz_b03_dosis_minima` valida:
  1. `resp.status_code == 201`
  2. `medicamento.get("estado_registro") == "VALIDADO"`
  3. `medicamento.get("fecha_fin_retiro") is None`
  4. `despues == antes + 1` (incremento de conteo de medicamentos del activo 853)
  5. `estado == 1` (`ESTADO_ACTIVO`)
  6. `recibido is not None` (`cantidad` presente en la respuesta) y parseable como `Decimal`
  7. `cantidad == Decimal("0.0001")`
  8. Teardown de corrida `DELETE /test-control/runs/{run_id}` con HTTP `200` y `"Rollback exitoso"`.
- **Inocuidad**: conteo base en activo 853 = **0**; conteo final tras rollback de todas las corridas = **0** (`0/0`, sin contaminación).
- **Integridad SHA-256 (antes y después)**:
  - `test_tc_m05_g14.py`: `A693E2DF2229EB52501079E9BC9365B39E084C52C2C87699067DB2F8079B680D` (sin cambios).
  - `ejecutar_tc_m05_g14.ps1`: `01EEA075BAEC9150E3683F18BCF84161C14DCF1E8497D3732E0E83045829D536` (sin cambios).

---

## 4. Diagnóstico del criterio de re-prueba (`D01`–`D12`)

> **Nota**: Esta sección corresponde al script auxiliar `diagnostico_reintento1/diag_precision.py` (3/3 tests PASSED en corrida sandbox única con un solo login, inocuidad `0/0`). **NO constituye un reporte oficial**; complementa la evaluación oficial verificando los límites de `numeric(10,4)` y su impacto en el costeo.

| ID | Dosis JSON | CU | Origen | Esperado | HTTP | `error_code` | Resp `cantidad` | Resp `costo_total` | `X-Request-ID` | Resultado |
|---|---|---|---|---|---:|---|---|---|---|---|
| D01 | `0.0001` | 500 | [especificación + Dev] | 201, cant `0.0001`, costo `0.0500` | 201 | `null` | `0.0001` | `0.0500` | `3765a21a-9f65-495a-af61-ba27ec16b000` | OK |
| D02 | `0.0004` | 500 | [contrato Dev] | 201, cant `0.0004`, costo `0.2000` | 201 | `null` | `0.0004` | `0.2000` | `cf0c3f80-07bb-45f4-9e62-6b23af7268c7` | OK |
| D03 | `0.0005` | 500 | [criterio INC] | 201, cant `0.0005`, costo `0.2500` | 201 | `null` | `0.0005` | `0.2500` | `54b6776f-3379-4d3e-9162-55aba9b73c3b` | OK |
| D04 | `0.0015` | 500 | [criterio INC] | 201, cant `0.0015`, costo `0.7500` | 201 | `null` | `0.0015` | `0.7500` | `03f943e8-010a-4981-bbfc-96c6cac87fed` | OK |
| D05 | `0.001` | 500 | [control] | 201, cant `0.001` | 201 | `null` | `0.0010` | `0.5000` | `9b4c81c4-fe82-4a7f-9edd-308cee5d94e9` | OK |
| D06 | `0.00001` | 500 | [contrato Dev] | 400 `VAL_ENTRADA`, sin persistencia | 400 | `VAL_ENTRADA` | `null` | `null` | `701a02f5-9373-49d6-a671-ee403ecf16df` | OK |
| D07 | `1.23456` | 500 | [contrato Dev] | 400, sin persistencia | 400 | `VAL_ENTRADA` | `null` | `null` | `017c619a-7248-4d8f-94e9-c2035c190c0a` | OK |
| D08 | `0.00010` | 500 | [contrato Dev] | 201, cant `0.0001` | 201 | `null` | `0.0001` | `0.0500` | `c3a99b2f-72e3-4285-8aa0-6b69850c3395` | OK |
| D09 | `0` | 500 | [especificación E4] | 400, sin persistencia | 400 | `VAL_ENTRADA` | `null` | `null` | `ad25fa54-ee0f-44c1-ac64-88ee2e23fa40` | OK |
| D10 | `999999.9999` | 1 | [contrato Dev / máx 10,4] | 201, cant `999999.9999` | 201 | `null` | `999999.9999` | `999999.9999` | `3fccd3fe-260a-4a2b-b2b6-fd2328c1e625` | OK |
| D11 | `1000000` | 1 | [contrato Dev] | 400, sin persistencia | 400 | `VAL_ENTRADA` | `null` | `null` | `8e8a82f6-c2bd-47ef-ad42-217abfd327bf` | OK |
| D12 | `10` | 500 | [control post-400] | 201 (corrida sana tras 400) | 201 | `null` | `10.0000` | `5000.0000` | `3878e939-ea7b-4f18-9437-44434dae1e0a` | OK |

---

## 5. Limitación de inspección directa en BD

- **Hecho observado**: Las consultas `SELECT` vía `POST /test-control/query` sobre `modulo5.registros_medicamentos` (ids `246`–`253`), `modulo5.registro_suministro` (`90de25a0-6a51-4820-a127-7261c9033c08`, `134dfbe8-f824-4551-9bee-21f272652a74`) y `modulo5.acumulado_ciclo` (`61563705-1b24-45f3-91c6-f6a0fe3b3020`) respondieron `HTTP 200` con `0` filas visibles (`{"data": []}`).
- **Inferencia**: Consistente con políticas RLS de `modulo5` cuando `/test-control/query` ejecuta sin variables de contexto de sesión de usuario.
- **Respaldo de persistencia a 4 decimales**: Dentro de la misma corrida sandbox de diagnóstico, la API autenticada `GET /suministros/costeo-directo/acumulado/activo/853` (`X-Request-ID: c97f35c6-0d5e-48b7-8481-6188554d3081`) devolvió `HTTP 200` con `acumulado_total_ciclo = "1005001.7999"`, que coincide exactamente con la suma aritmética a cuatro decimales de los 8 registros creados (`0.0500 + 0.2000 + 0.2500 + 0.7500 + 0.5000 + 0.0500 + 999999.9999 + 5000.0000 = 1005001.7999`).

---

## 6. Veredicto

- **Veredicto oficial**: **Aprobado** (`30/30` passed en Reintento 1, `run-20261111-140320`).
- **INC-M05-270-G14**: **corregido y verificado en TEST el 2026-11-11**.

---

## 7. Observaciones para Análisis (no son defectos de este caso)

1. **`costo_total_medicamento` en `numeric(12,4)`**: Con la dosis máxima permitida (`999999.9999`) y un `costo_unitario` alto (p. ej. `>= 1000`), el producto puede desbordar `numeric(12,4)` (máximo `99999999.9999`). No es exigido por la especificación actual de TC-M05-G14; por ello en D10/D11 se usó `costo_unitario = 1`.
2. **`registro_suministro.precio_unitario_resuelto` en `numeric(10,2)`**: En `information_schema.columns` de TEST se observó escala `2` frente a `costo_unitario_medicamento` con escala `4`. Corresponde al alcance de RF-78 y no fue probado en este caso.

---

## 8. Archivos resultantes

Rutas relativas a `tests/Test_Testing/Test_Modulo5/RF-76/TC-M05-G14/`:

- **`resultados/`**:
  - `resultados/resultado_TC-M05-G14_reintento1.html` — reporte oficial pytest-html promovido desde el staging validado.
  - `resultados/resultado_TC-M05-G14_reintento1.json` — reporte oficial con los 30 checkpoints (`Aprobado`, `30/30 OK`).
  - `resultados/resultado_TC-M05-G14.html` — reporte histórico de ronda 1 (`Rechazado`), conservado sin cambios.
  - `resultados/resultado_TC-M05-G14.json` — JSON histórico de ronda 1 (`29 OK / 1 FALLA`), conservado sin cambios.
  - `resultados/.gitkeep`
- **`evidencias/run-20261111-140320/`**:
  - `resultado_TC-M05-G14_reintento1.html` — copia original de la corrida.
  - `resultado_TC-M05-G14_reintento1.xml` — JUnit XML (conservado en evidencias).
  - `console_execution.log` — salida de consola de pytest.
  - `trazas_http.jsonl` — trazas HTTP y conteos de inocuidad.
  - `gen_json_resultado.py` — script generador de `resultados/resultado_TC-M05-G14_reintento1.json`.
  - `TC-M05-G14_resultado.md` — este informe narrativo.
  - `INFORME_PROMOCION_G14.txt` — informe técnico de promoción y anexos.
  - `INFORME_REEVALUACION_G14.txt` — informe técnico de reevaluación.
  - `diagnostico_reintento1/` — script `diag_precision.py`, `diag_resultados.json` y `console_diag.log`.
