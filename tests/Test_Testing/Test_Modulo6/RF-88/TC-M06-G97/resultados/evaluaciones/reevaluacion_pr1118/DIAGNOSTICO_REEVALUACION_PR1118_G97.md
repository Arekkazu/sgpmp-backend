# DIAGNÓSTICO DE REEVALUACIÓN — TC-M06-G97 (PR #1118)

**Caso:** Validación de la depreciación lineal según la vida útil configurada del activo  
**Escenarios:** TC-M06-08 · TC-M06-09  
**Antecedente:** incidencia [#1114](https://github.com/Arekkazu/sgpmp-backend/issues/1114)  
**PR reportado:** [#1118](https://github.com/Arekkazu/sgpmp-backend/pull/1118)  
**Fecha:** 2026-11-13 (reevaluación)  
**Alcance:** verificación de integración/despliegue + lectura OpenAPI/sonda GET · **sin POST de reconocimiento** · sin escrituras financieras · sin commit/push  

**Documento previo conservado:** `resultados/DIAGNOSTICO_PREVIO_G97.md` (no reemplazado).

---

## Dictamen de esta reevaluación

### G97: **BLOQUEADO** (despliegue / integración pendiente)

| Escenario | Resultado | Motivo |
|---|---|---|
| **TC-M06-09** | **BLOQUEADO** | `GET /finanzas/activos/{id}/depreciacion` **no existe** en TEST (OpenAPI sin path; sonda HTTP **404**). |
| **TC-M06-08** | **BLOQUEADO** (y **PENDIENTE DE AUTORIZACIÓN** para cualquier POST futuro) | Sin despliegue del lote en TEST no hay base para ejecutar el rechazo. Además, el `POST /finanzas/reconocimientos/{id}` **no se envió**: puede escribir un reconocimiento si las condiciones no son las del AC. |

G97 **no** queda APROBADO. No se ejecutaron los criterios de aceptación en el ambiente compartido.

---

## FASE 1 — Integración y despliegue

### PR #1118

| Campo | Valor |
|---|---|
| Estado | **open** (no mergeado) |
| Base / head | `dev` ← `fix/qa-m05-m06-lote-2026-11-13` |
| Head SHA | `16b990eea367ccfef9003e1e01330003637f124c` |
| Mergeable | true |
| Issue #1114 | **open** |

### Commit que aporta G97 (dentro del PR)

| Campo | Valor |
|---|---|
| SHA | `4f3d4962d5c03e329e8d16f86f6fb467071b0811` |
| Mensaje | `feat(rf88-mod6): consulta de la depreciacion lineal de un activo al costo a una fecha (INC-M06-90-G97)` |

Contenido relevante en el head del PR (código, **no** desplegado en TEST):

- Router: `GET /activos/{id_activo_biologico}/depreciacion` (prefijo finanzas) + query opcional `fecha`.
- Use case: `ConsultarDepreciacionUseCase` — calcula sin registrar; expone `depreciacion_anual`, `depreciacion_acumulada`, `valor_contable`, `depreciacion_registrada`, etc.
- FA-2: sin vida útil → `BusinessRuleError` **422** `VIDA_UTIL_NO_CONFIGURADA` también en la consulta.
- Test de integración: `tests/integration/test_inc_m06_90_g97_depreciacion.py` (12M / 72 meses → anual 2M; reconocimiento sin vida → 422).

### ¿Integrado a `dev` / `test`?

| Ref remota | SHA observado | ¿Contiene head del PR? |
|---|---|---|
| `origin/dev` | `08e65db4…` | **No** |
| `origin/test` | `2cd6ee14…` | **No** |

### ¿Desplegado en backend TEST?

Consulta: `GET https://api.inmero.co/api-sgpmp-test/openapi.json` → **200**, 364 paths.

- Paths con `depreci*`: **ninguno**.
- Rutas bajo `/finanzas/activos/...`: listado, detalle, simulación, eventos sanitarios, deterioros, valor-razonable. **Sin** `/depreciacion`.

Sondas GET (solo lectura):

| Ruta | HTTP |
|---|---|
| `/finanzas/activos/1/depreciacion?fecha=2025-01-01` | **404** `{"detail":"Not Found"}` |
| `/finanzas/activos/1/depreciacion` | **404** |

**Conclusión Fase 1:** el fix existe en la rama del PR, pero **no está integrado ni desplegado en TEST**. G97 **no** está listo para ejecución funcional en el ambiente compartido. Se detiene aquí la corrida de aceptación.

Evidencias:  
`resultados/reevaluacion_pr1118/estado_pr1118.json`  
`resultados/reevaluacion_pr1118/evidencia_openapi_pr1118.json`  
`resultados/reevaluacion_pr1118/evidencia_sonda_depreciacion_test.json`

---

## FASE 2 — Preparación de datos

**No iniciada en TEST** (bloqueo de Fase 1).

Cuando el endpoint esté desplegado, se requerirá (solo lectura / sin alterar config compartida):

### TC-M06-09

- Activo reconocido al costo con costo depreciable **$12.000.000** y vida útil **72 meses**.
- Fecha de adquisición/reconocimiento identificable.
- Fecha de cálculo = adquisición + **12 meses** (un año) para esperar:
  - `depreciacion_anual` = **2.000.000**
  - `depreciacion_acumulada` = **2.000.000**
  - `valor_contable` = **10.000.000**
  - campo `depreciacion_registrada` presente (en el test del PR, tras solo reconocer sin cierres, suele ser **0**).

### TC-M06-08

- Especie/configuración **sin** `vida_util_meses` **ya existente** (no modificar config compartida para forzar el error).
- Activo candidato a reconocimiento al costo.
- Validar de antemano (GET propuesta / lecturas) que el escenario tiende a **422** y no a un reconocimiento válido.

---

## FASE 3 — TC-M06-09

**No ejecutado** (ruta ausente en TEST → 404).  
No se inventaron montos ni fechas de cálculo sobre un activo real.

---

## FASE 4 — TC-M06-08 (preparación; sin POST)

Según desarrollo y el test del PR, el rechazo esperado vía reconocimiento es:

`confirmar_reconocimiento` → HTTP **422** · código **`VIDA_UTIL_NO_CONFIGURADA`**.

En el mismo PR, la **consulta** de depreciación también implementa FA-2 con el mismo código (útil cuando exista un registro al costo sin vida).

**Estado de esta fase:**

1. Endpoint de consulta **no** disponible en TEST.  
2. `POST /finanzas/reconocimientos/{id}` **no enviado**.  
3. Efecto potencial del POST: si el activo/especie sí tienen vida útil u otras reglas permiten el flujo, **se crearía un reconocimiento financiero** en TEST compartido.

### Solicitud de autorización (pendiente)

Cuando #1118 esté mergeado y desplegado en TEST, se pedirá autorización explícita antes de cualquier:

- `POST /finanzas/reconocimientos/{id}` (TC-M06-08), y  
- cualquier otra escritura (config especie, cierre, etc.).

La consulta `GET .../depreciacion` es de solo lectura y podrá ejecutarse sin esa autorización de escritura, **solo** tras confirmar despliegue.

---

## FASE 5 — Evidencias conservadas

| Archivo | Contenido |
|---|---|
| `DIAGNOSTICO_PREVIO_G97.md` | Diagnóstico anterior (BLOQUEADO pre-#1118) — **intact** |
| `evidencia_lectura_openapi_G97.json` | OpenAPI previo — **intact** |
| `reevaluacion_pr1118/estado_pr1118.json` | Estado PR/issue/commits/ancestría |
| `reevaluacion_pr1118/evidencia_openapi_pr1118.json` | OpenAPI TEST actual |
| `reevaluacion_pr1118/evidencia_sonda_depreciacion_test.json` | Sondas 404 |
| `DIAGNOSTICO_REEVALUACION_PR1118_G97.md` | Este documento |

---

## FASE 6 — Dictamen por escenario

| ID | Dictamen |
|---|---|
| TC-M06-08 | **BLOQUEADO** · además **PENDIENTE DE AUTORIZACIÓN** para el POST |
| TC-M06-09 | **BLOQUEADO** |
| **G97** | **BLOQUEADO** |

### Condición para retomar

1. Merge de **PR #1118** (o commit equivalente) en la rama que alimenta TEST.  
2. Despliegue verificado: OpenAPI con `GET /finanzas/activos/{id}/depreciacion` y sonda ≠ 404.  
3. Preparación de datos en solo lectura.  
4. Ejecutar TC-M06-09 (GET).  
5. Autorización explícita antes de TC-M06-08 (POST).

---

*Sin commits, push, cambios de rama ni modificación de archivos ajenos a G97. Sin escrituras financieras en TEST.*
