# REEVALUACIÓN V2 — TC-M02-G97 (reejecución final con automatización corregida)

**Proyecto:** SGPMP / SIGAB · **Módulo:** M02 · **RF:** RF-51 — Generación de Indicadores Zootécnicos · **CU:** CU12
**Subcasos:** TC-M02-312, TC-M02-313-A, TC-M02-313-B, TC-M02-314
**Responsable QA:** Juan Esteban · **Ambiente:** TEST · **Fecha:** 2026-09-19
**Corrección de producto evaluada:** INC-M02-99-G97 · Issue #247 · PR #270 (merge `befb3e77a6d2531f95fa0472f7f42f0e55eafb92`)

> Esta reejecución sustituye la ejecución V2 anterior del mismo día (19:35Z). El usuario eliminó los resultados anteriores y se regeneró `EvaluacionV2/` desde cero. Se corrigieron dos problemas de automatización QA: la aserción literal V12 de Newman y la dependencia de `DATABASE_URL` en Pytest. El criterio funcional no cambió.

---

## 1. Resumen ejecutivo

| Dimensión | Resultado |
|---|---|
| **VEREDICTO** | **APROBADO — CORREGIDO / SIN REGRESIÓN** |
| TC-M02-312 | 404 `ACTIVO_NO_ENCONTRADO` → APROBADO — SIN REGRESIÓN |
| TC-M02-313-A | 400 `RANGO_FUERA_DE_CICLO_VIDA`, `field=fecha_inicio` → APROBADO — DEF-G97-01 CORREGIDO |
| TC-M02-313-B | 400 `RANGO_FUERA_DE_CICLO_VIDA`, `field=fecha_fin` → APROBADO — DEF-G97-01 CORREGIDO |
| TC-M02-314 | 403 `ACCESO_DENEGADO` con falta real de READ (29,2) → APROBADO — SIN REGRESIÓN |
| Newman | 13 requests · **50 assertions · 50 passed · 0 failed** (una sola ejecución) |
| Pytest | **7 passed · 0 failed** (una sola ejecución, sin `DATABASE_URL`) |
| DEF-G97-01 | **CORREGIDO** |
| OBS-G97-01 | **RESUELTA**: producto, OpenAPI y matriz vigente coinciden en GET |
| Harness Newman V12 | **RESUELTO** |
| Harness Pytest (`DATABASE_URL`) | **RESUELTO** |
| Δ dominio | **0** |
| Hallazgos formales abiertos | **NINGUNO** |

---

## 2. Rama / HEAD / sincronización con test

| Verificación | Resultado |
|---|---|
| Rama | `qa/juan-esteban-re-evaluacion-m02` ✅ |
| HEAD | `a6220fc82e8d92eae1bb16f5cf01fca76b1c8a0c` ✅ |
| `git fetch origin` + `HEAD...origin/test` | `0 0` ✅ |
| PR #270 ancestro de HEAD | ✅ (verificado en la ejecución anterior; HEAD no cambió) |
| `git status --short` | solo carpetas `EvaluacionV2/` no versionadas (esta y otras reevaluaciones) |
| Validación en código | `ConsultarIndicadoresUseCase._validar_rango_dentro_del_ciclo_de_vida` (nacimiento → inicio de ciclo → último cambio de estado si BAJA/CERRADO) |

---

## 3. OpenAPI y confirmación GET

`GET /api-sgpmp-test/openapi.json` → 200 (2026-09-19 ~20:08Z).

| Ruta `/activos-biologicos/{id_activo}/indicadores` | Resultado |
|---|---|
| Métodos | **solo `get`** |
| POST | no existe en esta ruta ni en ninguna otra ruta de indicadores |
| Respuestas GET | `200, 400, 401, 403, 404, 422` (400/403/404 declaradas) |
| Summary | "Consultar indicadores zootécnicos del activo biológico (CU12 - RF-51)" |

Las aserciones de SETUP de Newman (D2/V30, V31, respuestas declaradas, CRECIMIENTO válido) pasaron.

---

## 4. OBS-G97-01 — RESUELTA por actualización de la matriz

- **V1:** la matriz indicaba `POST /activos-biologicos/{id_activo}/indicadores`; el contrato solo declaraba GET y el POST devolvía 405.
- **V2:** el paquete de instrucciones de esta reejecución, emitido por el responsable QA, informa que **la matriz oficial ya se corrigió a `GET /activos-biologicos/{id_activo}/indicadores`**. La matriz no forma parte del repositorio, así que su contenido no se verificó localmente. El producto (ejecución 100 % GET) y el OpenAPI vivo (solo `get`) coinciden con ella.
- Como la discrepancia documental quedó corregida, se omitió el POST de diagnóstico (405). No se ejecutó ningún POST contra `/indicadores`.

**Evolución: OBS-G97-01 → RESUELTA** (matriz + OpenAPI + producto alineados en GET).

---

## 5. Gate de fixtures

BD TEST: `SET default_transaction_read_only = on` → `member_qa | sgpmp_test | on`. Solo `SELECT`.

| Fixture | Esperado | TEST (20:08Z) | Gate |
|---|---|---|---|
| 99999 | inexistente | `count(*) = 0` | ✅ |
| 279 | QAJE-CREC-OK, INDIVIDUAL, ACTIVO | QAJE-CREC-OK, INDIVIDUAL, `id_estado=1` | ✅ |
| 279 nacimiento / ciclo | 2026-01-15 / 2026-06-01 | 2026-01-15 / 2026-06-01 | ✅ |
| 279 estado terminal previo | ninguno | 0 filas de histórico | ✅ |
| 313-A rango | 2025-12-01 → 2026-09-10 | inicio < nacimiento y < ciclo; no invertido | ✅ |
| 286 | QAJE-IND-BAJA, BAJA | `id_estado=6` | ✅ |
| 286 último cambio terminal | 2026-08-31 | histórico 163, 1 → 6, 2026-08-31 12:00Z (único) | ✅ |
| 313-B rango | 2026-07-01 → 2026-09-05 | inicio dentro del ciclo; fin > baja; no futuro | ✅ |
| `contador@pecuaria.co` | usuario 5, rol 5, Activa, sin (29,2) | usuario 5, Contador, `id_estado_cuenta=2`, 0 filas (29,2) | ✅ |
| Herencia de rol | inexistente | sin tabla `usuarios_roles` | ✅ |
| `m2m.nuevo@ejemplo.com` | usuario 35, (29,2) activo | usuario 35, Productor, permiso 166 activo | ✅ |

Los hashes de fixtures son idénticos a los de la ejecución anterior. No hubo drift y no se cambiaron fixtures, credenciales ni rangos.

---

## 6. TC-M02-312

`GET /activos-biologicos/99999/indicadores?tipo_indicador=CRECIMIENTO&fecha_inicio=2026-06-01&fecha_fin=2026-08-31` (AUTH_OK)

```json
{"error_code":"ACTIVO_NO_ENCONTRADO",
 "message":"El activo biológico con ID 99999 no existe en los registros del sistema.",
 "fields":[],"timestamp":"2026-09-19T20:08:59.570064+00:00"}
```

HTTP **404**. El mensaje identifica 99999; no hay indicador, variables, traza ni SQL. Newman 6/6. **APROBADO — SIN REGRESIÓN** (V1 404 → V2 404).

---

## 7. TC-M02-313-A

Activo 279: nacimiento 2026-01-15, ciclo 2026-06-01, ACTIVO.
`GET /activos-biologicos/279/indicadores?tipo_indicador=CRECIMIENTO&fecha_inicio=2025-12-01&fecha_fin=2026-09-10` (AUTH_OK)

```json
{"error_code":"RANGO_FUERA_DE_CICLO_VIDA",
 "message":"La fecha de inicio (2025-12-01) es anterior a la fecha de nacimiento del activo (2026-01-15).",
 "fields":[{"field":"fecha_inicio","message":"La fecha de inicio (2025-12-01) es anterior a la fecha de nacimiento del activo (2026-01-15)."}],
 "timestamp":"2026-09-19T20:08:59.784536+00:00"}
```

| Assertion Newman | Resultado |
|---|---|
| V7 activo existe y ACTIVO | ✅ |
| V8/V9/A6 inicio anterior al nacimiento y al ingreso | ✅ |
| V10/A5 fin dentro del ciclo, rango no invertido | ✅ |
| V11 HTTP 400 | ✅ |
| V12-A `error_code = RANGO_FUERA_DE_CICLO_VIDA` | ✅ |
| V12-B `fields[0].field = fecha_inicio` | ✅ |
| V12-C mensaje: "anterior" + "nacimiento" | ✅ |
| No se expone ningún indicador calculado | ✅ |

8/8. Sin `variables_usadas` ni `ganancia_peso`; no hay `INDICADOR_CALCULADO` para esta petición (§15), así que no se calculó. **APROBADO — DEF-G97-01 (A) CORREGIDO** (V1 200 con `ganancia_peso=0.0000 disponible=true` → V2 400).

---

## 8. TC-M02-313-B

Activo 286: BAJA, último cambio 2026-08-31.
`GET /activos-biologicos/286/indicadores?tipo_indicador=CRECIMIENTO&fecha_inicio=2026-07-01&fecha_fin=2026-09-05` (AUTH_OK)

```json
{"error_code":"RANGO_FUERA_DE_CICLO_VIDA",
 "message":"La fecha de fin (2026-09-05) es posterior a la fecha de baja del activo (2026-08-31).",
 "fields":[{"field":"fecha_fin","message":"La fecha de fin (2026-09-05) es posterior a la fecha de baja del activo (2026-08-31)."}],
 "timestamp":"2026-09-19T20:09:00.000634+00:00"}
```

| Assertion Newman | Resultado |
|---|---|
| V14/V15 activo en BAJA | ✅ |
| V16 inicio dentro del ciclo | ✅ |
| V17/A8 fin posterior a la baja | ✅ |
| V18/A9 fin no futuro | ✅ |
| V19 HTTP 400 | ✅ |
| V20 motivo (regex V1, se conserva) | ✅ |
| TC-313-B `error_code` correcto | ✅ |
| TC-313-B `field = fecha_fin` | ✅ |
| TC-313-B mensaje: "posterior" + "baja" | ✅ |
| No se expone ningún indicador calculado | ✅ |

10/10. `DATOS_INSUFICIENTES` no aparece. **APROBADO — DEF-G97-01 (B) CORREGIDO** (V1 200 → V2 400).

---

## 9. TC-M02-314

- **Usuario:** `contador@pecuaria.co` (id 5, Contador), cuenta Activa. El login devolvió 200 con JWT `sub=5`, `rol=5`.
- **READ (29,2):** ausente (SQL: 0 filas, sin herencia). Por API, `GET /activos-biologicos/279` → 403 `ACCESO_DENEGADO`.
- **Control positivo:** AUTH_OK sobre 279 → 200 (Newman A3 y Pytest).

`GET /activos-biologicos/279/indicadores?tipo_indicador=CRECIMIENTO&fecha_inicio=2026-06-01&fecha_fin=2026-09-10`

```json
{"error_code":"ACCESO_DENEGADO",
 "message":"Acceso denegado. Su rol no tiene permisos para realizar esta operación.",
 "fields":[],"timestamp":"2026-09-19T20:09:00.207740+00:00"}
```

HTTP **403**, no 401. No expone `indicadores`, `variables_usadas`, `ganancia_peso`, `peso_inicial`, `total_mediciones` ni `eventos_sanitarios`. Newman 7/7; Pytest `test_tc_m02_314_usuario_sin_read_recibe_403` PASSED. **APROBADO — SIN REGRESIÓN.** La falta de READ es real y preexistente; no se tocaron permisos, roles ni cuentas.

---

## 10. Corrección del harness Newman

La assertion histórica V12 dependía de una expresión textual `"ciclo de vida|fuera del ciclo|vida:"`.

La automatización V2 se corrigió para validar el contrato estructurado: `error_code = RANGO_FUERA_DE_CICLO_VIDA`, `field = fecha_inicio/fecha_fin` y semántica temporal del mensaje.

No se modificó ningún criterio funcional del producto.

`EvaluacionV2/test_tc_m02_g97_v2.json` (blob `--no-filters` `95a62395ed9b3b23c47f404691170099d1596e12`) es una copia de la colección V1 con estos cambios:

| # | Cambio | Motivo |
|---|---|---|
| 1 | 313-A: V12 literal sustituida por V12-A (`error_code`), V12-B (`field=fecha_inicio`), V12-C (mensaje con "anterior" y "nacimiento\|inicio de ciclo") | §3.3 del paquete |
| 2 | 313-B: se añaden `error_code`, `field=fecha_fin` y mensaje con "posterior" y "baja"; V20 se conserva | §4 del paquete |
| 3 | Se elimina `DIAG - el POST de la matriz devuelve 405` (2 assertions) | §8: matriz ya en GET; no ejecutar POST |
| 4 | Etiqueta de V31 en SETUP: "OpenAPI y matriz vigente alineadas en GET (no existe POST de indicadores)". La lógica no cambia | La etiqueta V1 hablaba de "discrepancia documentada", que ya no aplica |
| 5 | `info` V2; variable `password` vacía (se inyecta con `--env-var`) | No dejar secretos en el artefacto |

Endpoints, activos, rangos, usuarios, HTTP esperados y el resto de assertions son idénticos a V1. Total: 47 − 1 (V12) + 3 (V12-A/B/C) + 3 (313-B) − 2 (DIAG POST) = **50**.

---

## 11. Corrección del harness Pytest

La inspección del router dejó de importar el módulo FastAPI completo.

Ahora el test lee `activo_biologico_router.py` directamente con `pathlib` y verifica estáticamente:
`_RECURSO = 29`
y
`require_permission_m02(_RECURSO, 2, rf_origen='RF51')`.

Esto elimina la dependencia artificial de `DATABASE_URL` para una prueba que solo inspecciona código fuente.

No se modificó TC-M02-314 ni su criterio funcional.

`EvaluacionV2/test_tc_m02_g97_v2.py` (blob `--no-filters` `6e599ac9b0241baa910d574b0da8049805dc2a1b`) es una copia de V1. Cambios: `from pathlib import Path`; la función `test_el_endpoint_de_indicadores_exige_read_sobre_activos_biologicos` sustituida por la implementación de §5.3 del paquete; docstring y comando del encabezado apuntando a V2. Los otros seis tests son idénticos a V1. Las dos credenciales de TEST escritas en el archivo se heredan de V1 y no se cambiaron (§6 del paquete: "No cambiar credenciales").

---

## 12. Newman final

| Métrica | Valor |
|---|---|
| Colección | `EvaluacionV2/test_tc_m02_g97_v2.json` |
| Ventana | 2026-09-19 20:08:54.669Z – 20:09:00.098Z (una sola ejecución) |
| Requests | **13** (0 fallidas) |
| Assertions | **50** |
| Passed | **50** |
| Failed | **0** |
| Por subcaso | TC-312 6/6 · TC-313-A 8/8 · TC-313-B 10/10 · TC-314 7/7 · SETUP 17/17 · DIAG 2/2 |

La contraseña se pasó con `--env-var`. Reportes: `reporte_tc_m02_g97_v2_newman.json` y `.html`, con secretos redactados (§20).

---

## 13. Pytest final

| Métrica | Valor |
|---|---|
| Ejecución | una sola, 2026-09-19 ~20:09:10Z; `DATABASE_URL` no definida (`env -u DATABASE_URL`) |
| Tests | 7 |
| Passed | **7** |
| Failed | **0** |
| `DATABASE_URL` requerida para la inspección estática | **NO** |

Reporte: `reporte_tc_m02_g97_v2_pytest.xml`.

---

## 14. Persistencia PRE/POST

PRE 20:08:41Z (antes de Newman) · POST después de Pytest. SHA-256 (16 hex) de la tabla completa ordenada por PK:

| Tabla | PRE | POST | Δ |
|---|---|---|---|
| `modulo2.activos_biologicos` | 380 / `fe6bd77a26c58744` | 380 / `fe6bd77a26c58744` | **0** |
| `modulo2.eventos_activos` | 185 / `3a5302ef21974304` | 185 / `3a5302ef21974304` | **0** |
| `modulo2.eventos_sanitarios` | 50 / `a6a55b8b660a208f` | 50 / `a6a55b8b660a208f` | **0** |
| `modulo2.historicos_estados_activos` | 129 / `5e073b742df02a92` | 129 / `5e073b742df02a92` | **0** |
| `modulo2.detalles_activos_individuales` | 261 / `ce36ede1e46cf619` | 261 / `ce36ede1e46cf619` | **0** |
| `modulo1.permisos` | 371 / `4582f11347041fa4` | 371 / `4582f11347041fa4` | **0** |
| `modulo1.recursos` | 57 / `d9661c9db41f7f02` | 57 / `d9661c9db41f7f02` | **0** |

Hashes de fixtures (279/286, sus eventos, histórico y detalle; permisos de roles 2 y 5; usuarios 5 y 35): PRE = POST.

**Δ dominio = 0. SQL writes QA = 0.** Frente a la ejecución anterior (379 activos, 184 eventos, 260 detalles) hay una fila más en cada una de esas tablas. Son de otros equipos, anteriores al PRE y ajenas a los fixtures.

---

## 15. Auditoría técnica

Escrituras automáticas del producto en `modulo2.bitacora_auditoria_m02` (RF51: 52 → 57, +5). No son persistencia funcional de dominio:

| id | rf_origen | tipo_evento | activo | usuario | Origen |
|---|---|---|---|---|---|
| 3297 | RF51 | INDICADOR_CALCULADO | 279 | 35 | Newman A3 (control positivo) |
| 3298 | RF35 | ACCESO_NO_AUTORIZADO | 279 | 5 | Newman V24 (`GET /activos-biologicos/279`) |
| 3299 | RF47 | FICHA_CONSULTADA | 279 | 35 | Newman ficha integral |
| 3300 | RF47 | FICHA_CONSULTADA | 286 | 35 | Newman ficha integral |
| 3301 | RF51 | ACCESO_NO_AUTORIZADO | 279 | 5 | Newman **TC-M02-314** |
| 3302 | RF51 | INDICADOR_CALCULADO | 279 | 35 | Newman DIAG (rango válido) |
| 3304 | RF51 | ACCESO_NO_AUTORIZADO | 279 | 5 | Pytest TC-314 |
| 3305 | RF51 | INDICADOR_CALCULADO | 279 | 35 | Pytest control positivo |

- TC-312 (404) y TC-313-A/B (400) **no generan registro**. El rango se rechaza antes del cálculo.
- Los 403 se auditan como `ACCESO_NO_AUTORIZADO` (RF-52, vía `require_permission_m02`).
- Los registros 3296 y 3303 (RF49, usuario 104) caen en la ventana, pero pertenecen a otro equipo.
- Los 4 `POST /sesiones/` (2 Newman, 2 Pytest) actualizan `ultimo_acceso` de los usuarios 5 y 35 (escritura técnica de M01).
- No hubo tráfico POST distinto del login.

---

## 16. Comparación V1 ↔ nueva V2

| Subcaso | V1 | V2 | Evolución |
|---|---|---|---|
| TC-M02-312 | 404 — APROBADO | 404 `ACTIVO_NO_ENCONTRADO` — APROBADO | **SIN REGRESIÓN** |
| TC-M02-313-A | 200 — RECHAZADO | 400 `RANGO_FUERA_DE_CICLO_VIDA` (`fecha_inicio`) — APROBADO | **CORREGIDO** |
| TC-M02-313-B | 200 — RECHAZADO | 400 `RANGO_FUERA_DE_CICLO_VIDA` (`fecha_fin`) — APROBADO | **CORREGIDO** |
| TC-M02-314 | 403 — APROBADO | 403 `ACCESO_DENEGADO` — APROBADO | **SIN REGRESIÓN** |

| Herramienta | V1 | Ejecución V2 anterior (19:35Z, eliminada) | V2 final |
|---|---|---|---|
| Newman | 14 req · 42/47 (5 fallos en 313) | 14 req · 46/47 (V12 literal) | **13 req · 50/50** |
| Pytest | 7/7 | 6/7 + reejecución aislada con `DATABASE_URL` ficticia | **7/7 sin `DATABASE_URL`** |

---

## 17. Hallazgos formales

| Hallazgo | Relación | V1 | V2 | Evolución |
|---|---|---|---|---|
| DEF-G97-01 | DIRECTO TC-313 A/B | Abierto (200 en ambas variantes) | 400 `RANGO_FUERA_DE_CICLO_VIDA` en A y B, sin indicador ni cálculo | **CORREGIDO** |
| OBS-G97-01 | COLATERAL documental | Matriz POST / OpenAPI GET | Matriz vigente GET (informado en el paquete) + OpenAPI GET + producto GET | **RESUELTA** |
| Harness Newman V12 | Automatización QA | — | Validación estructurada (`error_code`, `field`, semántica) | **RESUELTO** |
| Harness Pytest `DATABASE_URL` | Automatización QA | — | Inspección estática con `pathlib`, sin importar el router | **RESUELTO** |

Hallazgos formales V1 sin reevaluar: **NINGUNO**. Hallazgos formales abiertos: **NINGUNO**.

---

## 18. Regresiones

**Ninguna.** TC-312 y TC-314 mantienen 404 y 403. El control positivo (279 sin rango) y el diagnóstico con rango dentro del ciclo (2026-06-01 → 2026-09-10) responden 200 con `ganancia_peso` disponible, así que la nueva validación no rechaza rangos válidos.

---

## 19. Veredicto final

# ✅ APROBADO — CORREGIDO / SIN REGRESIÓN

TC-M02-312 PASS · TC-M02-313-A PASS · TC-M02-313-B PASS · TC-M02-314 PASS. Además:

- documentación alineada (OBS-G97-01 RESUELTA);
- automatización Newman corregida;
- automatización Pytest corregida.

Evolución global: **RECHAZADO (V1) → APROBADO (V2)**.

---

## 20. Integridad

- V1 intacta: `git diff HEAD` vacío en la carpeta del caso. `construir_coleccion.cjs`, `test_tc_m02_g97.json`, `test_tc_m02_g97.py` y `Resultados/` sin cambios. `construir_coleccion.cjs` no se ejecutó.
- La limpieza de artefactos se limitó a `EvaluacionV2/`, que regeneró el usuario. Se eliminó `EvaluacionV2/__pycache__` generado por pytest.
- Newman y Pytest se ejecutaron una sola vez cada uno; no hubo reintentos.
- BD TEST: solo `SELECT`, en sesión `default_transaction_read_only = on`. Sin escrituras, DDL ni triggers. No se leyeron hashes de contraseñas.
- No se crearon ni alteraron activos, bajas, fechas de nacimiento o ciclo, usuarios, roles ni permisos. No se usó token inválido ni DEV. No se usó `DATABASE_URL` ficticia.
- Redacción de secretos. JSON de Newman: 10 JWT, 3 contraseñas y 2 buffers de respuesta de login. HTML: 12 JWT y 2 contraseñas. Verificación posterior: 0 restantes en ambos reportes, en el XML de Pytest y en la colección V2. El Pytest V2 conserva las credenciales de TEST heredadas de V1 (§11).
- Sin commit, push, merge, rebase ni deploy. Sin cambio de rama. No se crearon issues. No se modificó código del producto.

### Artefactos

```text
TC-M02-G97/EvaluacionV2/
├── test_tc_m02_g97_v2.json                    colección V2 (harness corregido)
├── test_tc_m02_g97_v2.py                      Pytest V2 (inspección estática)
└── Resultados/
    ├── reporte_tc_m02_g97_v2_newman.json      13 req · 50/50 (secretos redactados)
    ├── reporte_tc_m02_g97_v2_newman.html      htmlextra (secretos redactados)
    ├── reporte_tc_m02_g97_v2_pytest.xml       7/7
    └── TC_M02_G97_reevaluacion_V2.md          este informe
```
