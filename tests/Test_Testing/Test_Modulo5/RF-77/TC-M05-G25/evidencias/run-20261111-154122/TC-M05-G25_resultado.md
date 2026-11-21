# TC-M05-G25 (RF-77) — Reintento 1: Reporte de Ejecución y Promoción

## 1. Identificación y Alcance
- **Caso de prueba**: `TC-M05-G25` (Cobertura de `RF-77`, casos `TC-M05-024` y `TC-M05-025`; verificación RBAC de bitácora bajo `RF-80`).
- **Incidente corregido**: `INC-M05-272-G25` (Dev #958, commit `293786267f`: registro de auditoría en generación, exportación exitosa CSV/PDF y regeneración de reportes de gastos en la bitácora de M05; sin migración de base de datos).
- **Ambiente evaluado**: `TEST` (`TEST_BASE_URL` desde `.env.test`), aislamiento por sandbox (`X-Test-Run-Id` + `X-Sandbox-Secret` en toda petición, máximo un login por cuenta por `run_id`, sin corridas simultáneas con la misma cuenta).
- **Staging oficial**: `tests/Test_Testing/Test_Modulo5/RF-77/TC-M05-G25/evidencias/run-20261111-154122/`
- **Corrida previa (archivada)**: `tests/Test_Testing/Test_Modulo5/RF-77/TC-M05-G25/evidencias/run-20261111-150413/` (ver `LEEME_ARCHIVADA.md`).
- **Ronda 1 original (baseline histórico)**: `tests/Test_Testing/Test_Modulo5/RF-77/TC-M05-G25/evidencias/run-20261107-170026/`.

## 2. Veredicto Oficial
- **Veredicto**: **Aprobado**
- **Resumen cuantitativo**: **23/23 checkpoints OK** (`0 FALLA`, `0 skipped`, `0 errors`).
- **Coherencia entre artefactos**:
  - `resultado_TC-M05-G25_reintento1.html` (`data-jsonblob`): `total=23`, `passed=23`, `failed_or_err=0`, `skipped=0`.
  - `resultado_TC-M05-G25_reintento1.xml` (JUnit XML): `tests="23"`, `errors="0"`, `failures="0"`, `skipped="0"`, `time="16.317"`.
  - `resultado_TC-M05-G25_reintento1.json`: `total=23`, `ok=23`, `falla=0`, `veredicto="Aprobado"`, `checkpoints=23`.

## 3. Control de Despliegue y Validación del Parche (Dev #958)
- `GET /health` respondió `HTTP 200` (`X-Request-Id: 8d8758c0-432d-44d7-a831-a388b03f1ee7` registrado en la validación de despliegue de `INFORME_REEVALUACION_G25.txt`); el backend no expone `/version` ni `/info`.
- La presencia activa de la corrección de `INC-M05-272-G25` quedó demostrada funcionalmente desde el Gate Paso 1 (`evidencias/run-20261111-150413`, evento `72111` registrado en `<= 0.384 s`) y confirmada íntegramente en la corrida oficial `run-20261111-154122`:
  - **`C01` + `C02` (Administrador, `id_usuario=104`)**: generación de reporte `id_reporte_gasto_acumulado=246` (`HTTP 200`) y exportación CSV `id_archivo=119f3c2e-b105-40b7-931a-f707d7d0196d` (`HTTP 201`) generaron exactamente 2 eventos en `GET /suministros/auditoria`:
    - `id_evento=72140`: tipo `GENERACION`, reporte `246`, actor `104`, resultado `EXITOSO`, `fecha_evento=2026-11-11T20:41:30.919938Z`, latencia cliente `0.49 s` (`<= 2.0 s`).
    - `id_evento=72141`: tipo `EXPORTACION` (`CSV`), reporte `246`, archivo `119f3c2e-b105-40b7-931a-f707d7d0196d`, actor `104`, resultado `EXITOSO`, latencia cliente `0.348 s` (`<= 2.0 s`).
  - **`C03` (Productor, `id_usuario=2`)**: generación de reporte `id_reporte_gasto_acumulado=247` y exportación CSV `id_archivo=f70ce7d4-1b86-4c83-878a-2bd84476b488` generaron exactamente 2 eventos:
    - `id_evento=72142`: tipo `GENERACION`, reporte `247`, actor `2`, resultado `EXITOSO`, `fecha_evento=2026-11-11T20:41:30.919938Z`, latencia cliente `0.591 s` (`<= 2.0 s`).
    - `id_evento=72143`: tipo `EXPORTACION` (`CSV`), reporte `247`, archivo `f70ce7d4-1b86-4c83-878a-2bd84476b488`, actor `2`, resultado `EXITOSO`, latencia cliente `0.442 s` (`<= 2.0 s`).

## 4. Resumen de Cobertura Funcional, RBAC y Seguridad
1. **Flujo completo Productor (`A01`–`A05`)**:
   - `A01`: generación sincrónica `HTTP 200` (`id_reporte_gasto_acumulado=244`, `gasto_total_acumulado=10.0000`).
   - `A02` / `A03`: exportación CSV (`HTTP 201`, `id_archivo=62f64d67-3f84-4814-a419-734d2aafa4b9`) y PDF (`HTTP 201`, `id_archivo=d9fecbd0-acb8-4fda-ac2b-6acc60c9b2b7`).
   - `A04`: descarga CSV propia `HTTP 200`.
   - `A05`: acceso a `GET /suministros/auditoria` rechazado con `HTTP 403 ACCESO_DENEGADO`.
2. **Restricciones RBAC Veterinario (`B01`–`B04`)**:
   - Rechazado con `HTTP 403 ACCESO_DENEGADO` en generación (`B01`), exportación (`B02`), descarga real de archivo exportado por Administrador (`B03`, `id_reporte=245`, `id_archivo=c9d0b296-6ed7-4274-a21e-125dcdf23caf`, sin `text/csv` ni contenido) y auditoría (`B04`).
3. **Autenticación, Robustez y Anti-IDOR (`D01`–`D05c`)**:
   - `D01`: `5/5` endpoints sin cabecera `Authorization` respondieron `HTTP 401 TOKEN_REQUERIDO`.
   - `D02`: intento de Productor de descargar CSV real de Administrador (`id_reporte=248`, `id_archivo=78cd718e-b4a9-492d-a6f1-761f1cdc8994`) rechazado con `HTTP 404 ARCHIVO_NO_ENCONTRADO` por RLS de `modulo5` (aceptado dentro de `{403, 404}` conforme a `RF-77 RNF Seguridad / TC-M05-024`, sin `text/csv`, `attachment` ni fuga de contenido).
   - `D03`: `5/5` rutas con IDs inexistentes o inválidos respondieron `404`/`400` sin `HTTP 500`.
   - `D04`: historial estrictamente aislado por usuario (`id_reporte=249`; Productor `total=56`, Administrador `total=100`, conjuntos disjuntos).
   - `D05a`, `D05b`, `D05c`: intento de Productor sobre reporte ajeno de Administrador (`id_reporte=250`, sobre activo `id_activo=1839`) al consultar, regenerar y exportar respondido con `HTTP 404 REPORTE_NO_ENCONTRADO` y `0` eventos atribuibles en auditoría.

## 5. Aislamiento Sandbox e Inocuidad en `TEST`
- **Cierres secuenciales verificados (`A98`, `B98`, `C98`, `D98`)**:
  - `tc-m05-g25-prod-7ec72c86` -> `DELETE /test-control/runs/...` `HTTP 200` (`Rollback exitoso`).
  - `tc-m05-g25-vet-8bfaa938` -> `DELETE /test-control/runs/...` `HTTP 200` (`Rollback exitoso`).
  - `tc-m05-g25-adm-7dfa7199` -> `DELETE /test-control/runs/...` `HTTP 200` (`Rollback exitoso`).
  - `tc-m05-g25-idor-fad42743` -> `DELETE /test-control/runs/...` `HTTP 200` (`Rollback exitoso`).
- **Inocuidad Base vs. Final en bitácora de auditoría**:
  - Base (`tc-m05-g25-inobase-cbd8bd1f`, `GET /suministros/auditoria` `X-Request-Id: 0ab32bce-217e-4d52-b22d-463b5ebb6391`, `DELETE` `X-Request-Id: d53faa6e-93ab-446e-9c73-96eb1a15762e`): `total=65967`, `ultimo_id=72129`.
  - Final (`tc-m05-g25-inofin-a048d127`, `GET /suministros/auditoria` `X-Request-Id: 27a52212-abfc-431a-add3-5970ad0399a2`, `DELETE` `X-Request-Id: 753ae589-2868-47ae-9a1f-0dd7d5741b65`): `total=65967`, `ultimo_id=72129`.
- **No persistencia de recursos creados**: `14/14` recursos creados durante las corridas (`1` activo `1839`, `7` reportes `244`–`250` y `6` archivos exportados) devolvieron `HTTP 404` tras el rollback.

## 6. Evolución de Scripts, Integridad y Promoción
- Los scripts oficiales quedaron validados sin alteraciones posteriores a la etapa 1c (SHA-256 verificados):
  - `test_tc_m05_g25.py`: `42086B9D4F936A59E17CDA1F166025CA63D8032E8AA19FEFAB69F53E6D617D3A`
  - `ejecutar_tc_m05_g25.ps1`: `BDE400B8EA336171822F1201F4642FEE342CABDA8D0B11393FC8136875556D31`
  - `generar_artefactos_run_g25.py`: `22AEDEB8FD6EA410CF887430BFE9B668A674A55AC2FB680ABA55884455B1E29D`
- **Promoción realizada en `resultados/`**:
  - Agregados por copia: `resultado_TC-M05-G25_reintento1.html` y `resultado_TC-M05-G25_reintento1.json`.
  - Conservados intactos: `.gitkeep`, `resultado_TC-M05-G25.html` y `resultado_TC-M05-G25.json` (Ronda 1). El archivo `resultado_TC-M05-G25_reintento1.xml` permanece en `evidencias/run-20261111-154122/`.
  - Escaneo de secretos en todos los artefactos promovidos y generados: limpio (`no encontrado`).

