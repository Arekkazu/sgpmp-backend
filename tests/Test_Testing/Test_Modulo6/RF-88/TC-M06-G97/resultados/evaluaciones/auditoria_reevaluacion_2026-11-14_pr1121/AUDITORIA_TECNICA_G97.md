# Auditoría técnica — TC-M06-G97 (post PR #1121)

**Fecha:** 2026-11-14  
**Caso:** TC-M06-G97 (RF-88 / CU07) — TC-M06-08 · TC-M06-09  
**Incidencia:** INC-M06-90-G97 (#1114) — reportada cerrada por Backend  
**Alcance:** auditoría de código en `origin/dev` / commits del lote + lectura OpenAPI TEST  
**Sin:** POST/PUT/PATCH/DELETE · reconocimientos · cierres · commit/push  
**Históricos conservados:** `DIAGNOSTICO_PREVIO_G97.md`, `DIAGNOSTICO_REEVALUACION_PR1118_G97.md`, `reevaluacion_pr1118/`

---

## 1. Qué se encontró de #1118 / #1121 en el repositorio

| Ref | Hallazgo |
|---|---|
| Commit funcional G97 | `4f3d4962` — `feat(rf88-mod6): consulta de la depreciacion lineal… (INC-M06-90-G97)` |
| Archivos del commit | `consultar_depreciacion_use_case.py` (nuevo), `m06_factory.py`, `m06_router.py`, `tests/integration/test_inc_m06_90_g97_depreciacion.py` |
| PR #1121 | Merge `e45d5fa8` (2026-11-13) — lote M05/M06 que incorpora `4f3d4962` |
| `origin/dev` | **Contiene** `4f3d4962` |
| `origin/test` | **Contiene** `4f3d4962` |
| Rama local `laura` (HEAD `1b68169d`) | **No** contiene `4f3d4962`; el workspace **no** tiene el archivo `consultar_depreciacion_use_case.py` |
| `vida_util_meses or 1` | Presente en **HEAD/`origin/laura`** (`ejecutar_cierre_periodo_use_case.py`); **ausente** en `origin/dev` (reemplazado por `_vida_util` + bloqueo) |

El lote #1121 también trae otros cambios (RF-87/92, etc.); para G97 el delta relevante es el commit `4f3d4962` más la lógica de cierre sin `or 1` ya presente en `origin/dev`.

---

## 2. Endpoint TC-M06-09 — implementación en código (`origin/dev`)

| Ítem | Valor confirmado en código |
|---|---|
| Ruta | `GET /finanzas/activos/{id_activo_biologico}/depreciacion` |
| Query | `fecha` opcional (`AAAA-MM-DD`); por omisión `hoy_usuario()` |
| Permiso | `valoracion_por_costo` **R** (lectura) |
| Use case | `ConsultarDepreciacionUseCase` — **calcula sin registrar** |
| Campos de respuesta | `depreciacion_anual`, `depreciacion_mensual`, `depreciacion_acumulada`, `depreciacion_registrada`, `valor_contable`, `costo_adquisicion`, `vida_util_meses`, `fecha_adquisicion`, `fecha_calculo`, `meses_transcurridos`, … |
| Vida útil | `costo.vida_util_meses` o, si falta, parámetro de especie; si ninguna → **422** `VIDA_UTIL_NO_CONFIGURADA` |
| No valorado al costo | **404** `VALORACION_COSTO_NO_ENCONTRADA` |

Fórmula alineada a `valor_por_costo` / `meses_transcurridos` (NIC 41 dominio).

**Aserciones del test de integración del PR (no son datos de TEST compartido):**

- Costo 12.000.000 / vida 72 → `depreciacion_anual=2.000.000`, a +12 meses `depreciacion_acumulada=2.000.000`, `valor_contable=10.000.000`, `depreciacion_registrada=0` (sin cierres).

---

## 3. Validaciones TC-M06-08 / cierre

| Validación | ¿Implementada en `origin/dev`? | Cómo |
|---|---|---|
| Reconocer al costo sin vida útil → 422 `VIDA_UTIL_NO_CONFIGURADA` | **Sí** | `propuesta_reconocimiento` bloquea; test integración confirma vía `confirmar_reconocimiento` |
| GET depreciación con registro histórico sin vida (ni especie) → 422 | **Sí** | Use case FA-2; test fuerza `vida_util_meses=NULL` + especie sin vida |
| Cierre con activos sin vida → prevalidación `VIDA_UTIL_NO_CONFIGURADA` y execute **422** `CIERRE_BLOQUEADO` | **Sí** | `prevalidar` + `_depreciar` sin `or 1` |
| Eliminación de `vida_util_meses or 1` | **Sí en `origin/dev`** | **No** en workspace `laura` |

---

## 4. Disponibilidad en TEST (solo lectura)

Evidencia: `evidencia_openapi_sonda_readonly.json`

| Comprobación | Resultado 2026-11-14 |
|---|---|
| OpenAPI path `/finanzas/activos/{id}/depreciacion` | **Presente** (`get`) |
| Sonda sin token | **401** `TOKEN_REQUERIDO` (ya **no** 404 como en `reevaluacion_pr1118`) |

**Interpretación:** el contrato del endpoint **parece desplegado** en el API TEST.  
**No** se ejecutaron aserciones funcionales autenticadas ni los AC de 08/09 en TEST.  
Por política de esta tarea: el estado formal sigue marcando **confirmación funcional / despliegue operativo pendiente de validación QA**, aunque el path ya no esté ausente.

---

## 5. Caso de prueba G97 en el repo QA

Carpeta: `tests/Test_Testing/Test_Modulo6/RF-88/TC-M06-G97/`

| Contenido | Notas |
|---|---|
| Solo documentación/evidencias de diagnóstico | Sin script ejecutor propio tipo G112 |
| `DIAGNOSTICO_PREVIO_G97.md` | BLOQUEADO (sin endpoint) |
| `DIAGNOSTICO_REEVALUACION_PR1118_G97.md` | BLOQUEADO (PR abierto / no en TEST) — **histórico**, no sobrescrito |
| Test backend | `tests/integration/test_inc_m06_90_g97_depreciacion.py` (en `origin/dev`, no en `laura`) |

---

## 6. Datos de prueba — qué hay y qué falta

| Dato | Estado |
|---|---|
| Activo TEST con costo **exacto** 12.000.000 y vida **72** meses | **No verificado** en esta auditoría (sin inventario autenticado; no se inventan IDs) |
| Especie TEST sin `vida_util_meses` para TC-M06-08 | **No inventada**; alterar config compartida requiere autorización |
| Registro histórico al costo sin vida útil | Solo reproducido en test de integración con SQL; en TEST compartido **requiere preparación autorizada** |
| Período / Contador con permiso `valoracion_por_costo` R | Credencial QA Contador habitual; no ejercida aquí para AC |

---

## 7. Dictamen de auditoría

| Escenario | Estado |
|---|---|
| Código en `origin/dev` / lote #1121 | **Integrado** |
| Endpoint en OpenAPI TEST | **Expuesto** (401 sin token) |
| TC-M06-08 / TC-M06-09 en TEST | **NO EJECUTADOS** |
| G97 APROBADO | **No** |
| Listo para reevaluar funcionalmente | **Casi** — falta confirmar activo/datos aptos + autorización de escrituras (08) y GET autenticado (09); rama `laura` debe actualizarse desde `dev`/`test` para tener el código local |

**G97 no se declara desbloqueado/aprobado** solo por el cierre de #1114.
