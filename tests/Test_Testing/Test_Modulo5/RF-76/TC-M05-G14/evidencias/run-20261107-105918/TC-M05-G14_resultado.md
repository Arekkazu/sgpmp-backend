# TC-M05-G14 — Resultado de ejecución (evaluación oficial 20261107-105918)

| Campo | Valor |
|---|---|
| Caso | TC-M05-G14 — Rechazo de campos obligatorios y valores límite en el registro de medicamentos |
| Requerimiento | RF-76 (Registro de aplicación de medicamentos) |
| Caso de uso | CU03 |
| Endpoint | `POST /suministros/medicamentos` |
| Ambiente | TEST (`TEST_BASE_URL` de `.env.test`) |
| Fecha | 2026-11-07 (corrida `run-20261107-105918`) |
| Evaluador | Sebastian |
| Activo | 853 (INDIVIDUAL, ACTIVO, `fecha_inicio_ciclo` 2026-10-22; fase abierta dentro del sandbox) |
| Herramienta | pytest + sandbox transaccional (`X-Test-Run-Id` / `X-Sandbox-Secret`, rollback por corrida) |
| Script / runner | `test_tc_m05_g14.py` (SHA-256 `a693e2df…680d`), `ejecutar_tc_m05_g14.ps1` (`01eea075…d536`), sin cambios |
| Reportes computables | `resultados/resultado_TC-M05-G14.html` y `resultados/resultado_TC-M05-G14.json` |
| Contexto | Primera evaluación después de la corrección del 500 `ERROR_INTERNO` en los POST válidos. Sustituye a la corrida `run-20261107-095931`. |

## Resultado

**30 tests: 29 passed / 1 failed / 0 error / 0 skipped.** Se ejecutaron en el orden de diseño: línea base → preparación → A → B → cierre de la corrida principal → B03 → inocuidad final. La salida del runner fue `SEGURIDAD OK`.

### Subcaso (a) — rechazo por campos obligatorios ausentes o inválidos

| Id | Variación | Esperado | Obtenido | Estado |
|---|---|---|---|---|
| A01 | sin `id_activo_biologico` | 400, campo en `fields[]` | 400 `VAL_ENTRADA` [id_activo_biologico] | OK |
| A02 | sin `nombre_medicamento` | 400, campo en `fields[]` | 400 `VAL_ENTRADA` [nombre_medicamento] | OK |
| A03 | sin `fecha_aplicacion` | 400, campo en `fields[]` | 400 `VAL_ENTRADA` [fecha_aplicacion] | OK |
| A04 | sin `hora_aplicacion` | 400, campo en `fields[]` | 400 `VAL_ENTRADA` [hora_aplicacion] | OK |
| A05 | sin `via_administracion` | 400, campo en `fields[]` | 400 `VAL_ENTRADA` [via_administracion] | OK |
| A06 | sin `dosis_aplicada` | 400, campo en `fields[]` | 400 `VAL_ENTRADA` [dosis_aplicada] | OK |
| A07 | sin `unidad_dosis` | 400, campo en `fields[]` | 400 `VAL_ENTRADA` [unidad_dosis] | OK |
| A08 | sin `motivo_aplicacion` | 400, campo en `fields[]` | 400 `VAL_ENTRADA` [motivo_aplicacion] | OK |
| A09 | sin `costo_unitario` | 400, campo en `fields[]` | 400 `VAL_ENTRADA` [costo_unitario] | OK |
| A10 | sin `nombre_veterinario` | 400, campo en `fields[]` | 400 `VAL_ENTRADA` [nombre_veterinario] | OK |
| A11 | `via_administracion='ORAL2'` | 400 `VIA_ADMINISTRACION_INVALIDA` | 400 `VIA_ADMINISTRACION_INVALIDA` [via_administracion] | OK |
| A12 | `nombre_veterinario=null` | 400, campo en `fields[]` | 400 `VAL_ENTRADA` [nombre_veterinario] | OK |
| A13 | `unidad_dosis=''` | 400, campo en `fields[]` | 400 `VAL_ENTRADA` [unidad_dosis] | OK |
| A14 | `hora_aplicacion='25:99'` | 400, campo en `fields[]` | 400 `VAL_ENTRADA` [hora_aplicacion] | OK |
| A15 | `fecha_aplicacion='15-09-2026'` | 400, campo en `fields[]` | 400 `VAL_ENTRADA` [fecha_aplicacion] | OK |
| A16 | `nombre_medicamento` de 51 caracteres | 400, campo en `fields[]` | 400 `VAL_ENTRADA` [nombre_medicamento] | OK |

En el subcaso (a) no se persistió nada (el conteo del activo no cambió en ningún caso) y el activo siguió en `id_estado=1` (A17 OK): no se invocó RF-44.

### Subcaso (b) — valores límite

| Id | Variación | Esperado | Obtenido | Estado |
|---|---|---|---|---|
| B01 | `dosis_aplicada=0` | 400, mensaje «mayor a cero» (E4) | 400 `VAL_ENTRADA`, mensaje correcto, `fields=[null]` | OK |
| B02 | `dosis_aplicada=-1` | 400, mensaje «mayor a cero» (E4) | 400 `VAL_ENTRADA`, mensaje correcto, `fields=[null]` | OK |
| B03 | `dosis_aplicada=0.0001` | 201, persistido y `cantidad` = 0.0001 (decimal 10,4) | **500 `ERROR_INTERNO`**, sin `cantidad` devuelta | **FALLA** |
| B04 | motivo `'Preventiv'` (9 caracteres) | 400 (E6) | 400 `VAL_ENTRADA` [motivo_aplicacion] | OK |
| B05 | motivo `'Preventiva'` (10 caracteres) | 201 VALIDADO, sin `fecha_fin_retiro`, conteo +1 | 201 VALIDADO, conteo +1, activo en estado 1 | OK |
| B06 | fecha = hoy | 201 VALIDADO, sin `fecha_fin_retiro`, conteo +1 | 201 VALIDADO, conteo +1, activo en estado 1 | OK |
| B07 | fecha = hoy + 1 | 400 `FECHA_FUTURA` (E2) | 400 `FECHA_FUTURA` [fecha_aplicacion] | OK |
| B08 | fecha = fecha_inicio_ciclo − 1 | 400 `FECHA_ANTERIOR_A_CICLO` (E3) | 400 `FECHA_ANTERIOR_A_CICLO` [fecha_aplicacion] | OK |
| B09 | fecha = fecha_inicio_ciclo | 201 VALIDADO, sin `fecha_fin_retiro`, conteo +1 | 201 VALIDADO, conteo +1, activo en estado 1 | OK |

## Veredicto

**RECHAZADO**, por un único fallo genuino: **B03**.

El 500 general de la corrida anterior ya no aparece: B05, B06 y B09 responden 201 y persisten dentro del sandbox. B03 es un **fallo nuevo y distinto**; antes no era evaluable porque el 500 general lo tapaba.

## Defectos

### B03 — una dosis de 4 decimales provoca 500 en lugar de persistirse (NUEVO)
- **INC-M05-NN-G14: pendiente de crear en Taiga.**
- **Esperado (especificación):** `dosis_aplicada` decimal(10,4) > 0. Con 0.0001, HTTP 201, registro VALIDADO, conteo +1 y `cantidad` = 0.0001.
- **Obtenido:** HTTP **500**, `error_code` **`ERROR_INTERNO`**. No se devuelve `cantidad`, así que no hay valor que comparar como Decimal.
- **Causa probable (inferencia apoyada en el esquema de TEST, consultado en solo lectura después de esta corrida):**
  - La columna `modulo5.registros_medicamentos.cantidad` sigue siendo **numeric(10,3)**, frente a decimal(10,4) en la especificación. 0.0001 se redondea a 0.000.
  - El trigger `fn_trg_calcular_costo_total_medicamento` sigue lanzando P0001 cuando `cantidad <= 0`.
  - El traductor de errores no mapea ese P0001 de `modulo5` (`_RECHAZOS_TRIGGER`, `src/shared/db_error_translator.py:36`), así que termina en `InfrastructureError` `ERROR_INTERNO` (`:438`).
  - La única diferencia con B05, B06 y B09 (que dan 201) es la dosis. La causa exacta está en el log del servidor.
- **Impacto:** las dosis con cuatro decimales no se pueden registrar. Las de tres o menos no se ven afectadas, salvo que el cuarto decimal se trunca en silencio.

### R2 — login bloqueado si otra corrida sandbox con la misma cuenta sigue abierta (vigente, de ambiente)
- **INC-M05-NN-G14: pendiente de crear en Taiga** (registrado en la corrida previa).
- No afectó a esta corrida: todas las corridas se cerraron antes del siguiente login.

## Observaciones para Análisis (no son defectos)
- **E4 sin campo:** en B01/B02 el 400 trae `fields=[null]`. El detalle no señala `dosis_aplicada`.
- **`periodo_retiro_dias=0`:** se acepta como «sin retiro», aunque la especificación dice mínimo 1.
- **`fields[].type`:** el cuerpo de error no lo incluye.
- **Permisos del Productor:** no tiene permiso C sobre el recurso 48 (medicamentos); solo lo tienen Administrador y Veterinario.
- **Duplicados:** el código considera duplicado un registro VALIDADO con el mismo activo + nombre (sin distinguir mayúsculas) + fecha + hora. Falta contrastarlo con la especificación.
- **Precondición RF-37:** RF-76 exige un ciclo productivo abierto, y crear un activo no abre ninguno. Hay que asignar la fase con RF-37 antes.
- **E3 y la fecha de la fase:** E3 usa la `fecha_inicio_ciclo` del activo (2026-10-22), no la fecha de la fase. B09 se acepta con una fecha anterior a la apertura de la fase en el sandbox.

## Inocuidad
| Activo | Conteo base | Conteo final |
|---|---|---|
| 853 | 0 | 0 |

Hubo escrituras reales dentro del sandbox: 3 registros con 201 (B05, B06 y B09) y 2 aperturas de fase. Aun así, el conteo final es igual al base: **el rollback revirtió todo, sin contaminación.**

Teardown: las 4 corridas (inocuidad inicial, principal, B03 e inocuidad final) se cerraron con `DELETE /test-control/runs/{run_id}` → **200 «Rollback exitoso»**.

## Archivos
Rutas relativas a `tests/Test_Testing/Test_Modulo5/RF-76/TC-M05-G14/`:
- `resultados/resultado_TC-M05-G14.html` — reporte computable de esta corrida (pytest-html).
- `resultados/resultado_TC-M05-G14.json` — reporte computable con checkpoints (30: 29 OK / 1 FALLA).
- `evidencias/run-20261107-105918/resultado_TC-M05-G14.html` — original del reporte.
- `evidencias/run-20261107-105918/resultado_TC-M05-G14.xml` — JUnit XML.
- `evidencias/run-20261107-105918/console_execution.log` — consola de la corrida.
- `evidencias/run-20261107-105918/trazas_http.jsonl` — traza HTTP y registros de conteo.
- `evidencias/run-20261107-105918/generar_resultado_json.py` — generador del JSON de esta corrida.
- `evidencias/run-20261107-105918/TC-M05-G14_resultado.md` — este informe.
- `evidencias/run-20261107-095931/` — corrida previa a la corrección (HTML, XML, JSON, narrativo y repeticiones).
- `evidencias/diagnostico_R3/` — diagnóstico del 500 anterior.
- `evidencias/run-20261107-093850/` — corrida bloqueada por ambiente (activo 930).
