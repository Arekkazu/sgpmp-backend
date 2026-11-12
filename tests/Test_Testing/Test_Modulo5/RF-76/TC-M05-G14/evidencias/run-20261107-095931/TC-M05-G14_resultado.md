> Corrida previa a la corrección del 500; sustituida por la evaluación 20261107-105918.

# TC-M05-G14 — Resultado de ejecución

| Campo | Valor |
|---|---|
| Caso | TC-M05-G14 — Rechazo de campos obligatorios y valores límite en el registro de medicamentos |
| Requerimiento | RF-76 (Registro de aplicación de medicamentos) |
| Caso de uso | CU03 |
| Endpoint | `POST /suministros/medicamentos` |
| Ambiente | TEST (`TEST_BASE_URL` de `.env.test`) |
| Fecha | 2026-11-07 |
| Evaluador | Sebastian |
| Activo de la corrida | 853 (INDIVIDUAL, ACTIVO, `fecha_inicio_ciclo` 2026-10-22; fase abierta dentro del sandbox) |
| Activo del diagnóstico R3 | 5 (INDIVIDUAL, ACTIVO, fase real abierta 36) |
| Herramienta | pytest + sandbox transaccional (`X-Test-Run-Id` / `X-Sandbox-Secret`, rollback por corrida) |
| Reporte computable | `resultados/resultado_TC-M05-G14.html` (pytest-html) |

## Resultado

**30 tests: 26 passed / 4 failed / 0 error / 0 skipped.** Se ejecutaron en el orden de diseño: línea base → preparación → A → B → cierre de la corrida principal → B03 → inocuidad final.

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

En todos los casos del subcaso (a) el conteo de registros del activo no cambió (no se persistió nada) y el activo siguió en `id_estado=1`: no se invocó RF-44.

### Subcaso (b) — valores límite

| Id | Variación | Esperado | Obtenido | Estado |
|---|---|---|---|---|
| B01 | `dosis_aplicada=0` | 400, mensaje «mayor a cero» (E4) | 400 `VAL_ENTRADA`, mensaje correcto, `fields=[null]` | OK |
| B02 | `dosis_aplicada=-1` | 400, mensaje «mayor a cero» (E4) | 400 `VAL_ENTRADA`, mensaje correcto, `fields=[null]` | OK |
| B03 | `dosis_aplicada=0.0001` | 201 y persistido | 500 `ERROR_INTERNO` | FALLA — NO EVALUABLE (depende de R3) |
| B04 | motivo `'Preventiv'` (9 caracteres) | 400 (E6) | 400 `VAL_ENTRADA` [motivo_aplicacion] | OK |
| B05 | motivo `'Preventiva'` (10 caracteres) | 201, conteo +1 | 500 `ERROR_INTERNO` | FALLA (R3) |
| B06 | fecha = hoy | 201, conteo +1 | 500 `ERROR_INTERNO` | FALLA (R3) |
| B07 | fecha = hoy + 1 | 400 `FECHA_FUTURA` (E2) | 400 `FECHA_FUTURA` [fecha_aplicacion] | OK |
| B08 | fecha = fecha_inicio_ciclo − 1 | 400 `FECHA_ANTERIOR_A_CICLO` (E3) | 400 `FECHA_ANTERIOR_A_CICLO` [fecha_aplicacion] | OK |
| B09 | fecha = fecha_inicio_ciclo | 201, conteo +1 | 500 `ERROR_INTERNO` | FALLA (R3) |

## Veredicto

**RECHAZADO**, por el defecto R3: ningún registro válido de medicamento se persiste.

**B03 queda NO EVALUABLE.** Para aislar la precisión de la dosis hace falta que un registro válido responda 201, y eso depende de que se corrija R3.

## Defectos

### R3 — 500 `ERROR_INTERNO` en todo POST válido
- **INC-M05-NN-G14: pendiente de crear en Taiga.**
- **Síntoma:** todo `POST /suministros/medicamentos` válido responde 500 `ERROR_INTERNO`. Todos los rechazos anteriores a la persistencia sí responden según la especificación.
- **Reproducción: 13 de 13.**
  - Corrida: B05, B06, B09 y B03.
  - Repetición: B05, B06, B09 y B03.
  - Diagnóstico R3 sobre el activo 5: E1, E3i, E3ii, E3iii y E3iv.
- **Correlación del diagnóstico R3** (`X-Request-ID` y hora UTC del servidor):

  | Experimento | X-Request-ID | Hora UTC (servidor) |
  |---|---|---|
  | E1 | `g14r3-e1-d6035287029e` | 2026-11-07T15:15:24.544Z |
  | E3i | `g14r3-e3i-a318e72a9afc` | 2026-11-07T15:15:27.896Z |
  | E3ii | `g14r3-e3ii-7fffc05aab51` | 2026-11-07T15:15:29.615Z |
  | E3iii | `g14r3-e3iii-f5c1b03e92b7` | 2026-11-07T15:15:31.454Z |
  | E3iv | `g14r3-e3iv-bc54aafeae5d` | 2026-11-07T15:15:33.337Z |

  Horas del servidor de la corrida principal: B05 14:59:46.72Z, B06 14:59:47.35Z, B09 14:59:48.60Z y B03 14:59:54.20Z.
- **Hipótesis:**
  - **H1 (abrir la fase dentro del sandbox): descartada.** El activo 5, con fase real, también falla.
  - **H2 (datos del activo 853): descartada.** Otro activo, de otra especie, falla igual.
  - **H3 (forma del payload): descartada.** Fallan el payload mínimo, los valores clonados de un registro real, otra fecha y hora, y dosis/costo = 1.
  - **H4 (error en la capa de BD, ledger o triggers durante la persistencia): probable, sin confirmar.** El 500 sale por la rama de errores de BD no traducidos. El último medicamento guardado en TEST es del 2026-07-31, anterior a la entrada del acumulado de ciclo y del ledger/outbox M06.
- **Pendiente de Dev:** buscar en el log del backend de TEST los `X-Request-ID` anteriores para obtener la excepción original. No se pudo descartar que el fallo sea exclusivo del sandbox.

### R2 — Login bloqueado mientras otra corrida sandbox usa la misma cuenta
- **INC-M05-NN-G14: pendiente de crear en Taiga.**
- **Síntoma:** si sigue abierta otra corrida sandbox con la misma cuenta, el login espera hasta 180 s (lo que tarda en expirar esa corrida).
- **Experimento controlado:**
  - Login con la misma cuenta y una corrida abierta: ReadTimeout a los 30,6 s.
  - Login con otra cuenta (control): 200 en 1,4 s.
  - Login con la misma cuenta, con la corrida ya cerrada: 200 en 1,1 s.
- **Causa probable:** el UPDATE de invalidación de la sesión previa se queda sin confirmar dentro de la corrida abierta y retiene el lock de la fila.

## Observaciones para Análisis (no son defectos)
- **E4 sin campo:** en B01/B02 el 400 trae `fields=[null]`. El detalle no señala `dosis_aplicada`.
- **`periodo_retiro_dias=0`:** se acepta como «sin retiro», aunque la especificación dice mínimo 1.
- **`fields[].type`:** el cuerpo de error no lo incluye.
- **Precisión de la dosis:** `registros_medicamentos.cantidad` es `numeric(10,3)` y la especificación pide decimal(10,4). Se verificó solo leyendo el esquema; por ejecución no es evaluable mientras siga R3.
- **Permisos del Productor:** no tiene permiso C sobre el recurso 48 (medicamentos); solo lo tienen Administrador y Veterinario.
- **Duplicados:** el código considera duplicado un registro VALIDADO con el mismo activo + nombre de medicamento (sin distinguir mayúsculas) + fecha + hora. Falta contrastarlo con la regla de la especificación.
- **Precondición RF-37:** registrar un medicamento exige un ciclo productivo abierto, y crear un activo no abre ninguno. Hace falta asignar la fase con RF-37 antes de RF-76.

## Inocuidad
| Activo | Conteo base | Conteo final |
|---|---|---|
| 853 | 0 | 0 |
| 5 | 5 | 5 |

Todas las corridas (la principal, la de B03, las de inocuidad, las repeticiones y las del diagnóstico R3) se cerraron con `DELETE /test-control/runs/{run_id}` → **200 «Rollback exitoso»**. No quedó ninguna escritura persistida en TEST.

## Archivos
Rutas relativas a `tests/Test_Testing/Test_Modulo5/RF-76/TC-M05-G14/`:
- `resultados/resultado_TC-M05-G14.html` — reporte computable (pytest-html).
- `resultados/resultado_TC-M05-G14.json` — reporte computable con checkpoints (30: 26 OK / 4 FALLA).
- `evidencias/run-20261107-095931/generar_resultado_json.py` — script que genera el JSON a partir del JUnit y de la traza.
- `evidencias/run-20261107-095931/resultado_TC-M05-G14.html` — original del reporte.
- `evidencias/run-20261107-095931/resultado_TC-M05-G14.xml` — JUnit XML.
- `evidencias/run-20261107-095931/console_execution.log` — consola de la corrida.
- `evidencias/run-20261107-095931/trazas_http.jsonl` — traza HTTP y registros de conteo.
- `evidencias/run-20261107-095931/repro/B05_B06_B09/` y `repro/B03/` — repeticiones.
- `evidencias/run-20261107-095931/TC-M05-G14_resultado.md` — este informe.
- `evidencias/diagnostico_R3/` — `diagnostico_r3.py`, `trazas_diagnostico_R3.jsonl`, `informe_fase4b_R3.txt`.
- `evidencias/run-20261107-093850/` — corrida previa bloqueada por ambiente (activo 930); quedan solo la traza y las repeticiones, porque los artefactos con secretos se borraron.
- `test_tc_m05_g14.py`, `ejecutar_tc_m05_g14.ps1` — script y runner del caso.
