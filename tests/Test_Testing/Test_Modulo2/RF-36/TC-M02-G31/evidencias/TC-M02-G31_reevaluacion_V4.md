# Reporte de Ejecución de Pruebas — SGPMP

## 1. Metadatos de la Ejecución

| Parámetro | Valor |
|---|---|
| **Caso / Grupo de Prueba** | TC-M02-G31 (Valores Límite en la Gestión de Lotes) |
| **Módulo / Requerimiento Funcional** | Módulo 2 (Activos Biológicos) · RF-36 / RF-40 / RF-45 (CU03) |
| **Versión de Evaluación** | V4 (Tercera Reevaluación / Fase 3.3 Newman Canónico) |
| **RUN_ID** | `G31-REEVAL-V4-20260925-175552` |
| **Fecha de Evaluación** | 2026-09-25 |
| **Evaluador / Responsable** | Antigravity — QA Lead Senior SGPMP |
| **Entorno de Prueba** | TEST (`https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test`) |
| **Base de Datos TEST** | PostgreSQL TEST (`158.69.200.27:5448/sgpmp_test`, usuario `member_qa`) |
| **Colección de Prueba** | `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G31/test_tc_m02_g31.json` |
| **Reporte HTML Canónico** | `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G31/resultados/resultado_TC-M02-G31_reintento3.html` |
| **Reporte JSON Canónico** | `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G31/resultados/resultado_TC-M02-G31_reintento3.json` |
| **Veredicto Global** | 🟢 **Aprobado** |
| **Incidente Asociado** | INC-M02-100-G31 |
| **Nota Global** | Reevaluación V4 completada con éxito. Intento 1 (lote 296) falló con HTTP 500 por dato contaminado histórico que disparó trigger P0212 no mapeado en db_error_translator. Intento 2 con lote virgen 281 aprobó 7/7 assertions (100% OK), confirmando la validez del diseño del backend para igualdad de densidad límite y baja total con cierre automático. Hallazgo separado P0212 reportado a Desarrollo. |

---

## 2. Resumen Ejecutivo de la Corrida V4 (2 Intentos)

### 2.1. Intento 1 (Lote 296) — Diagnóstico de Falla
- **TC-M02-196:** Aprobado al 100% (`HTTP 201 Created` en `POST /activos-biologicos/130/eventos/crecimiento`).
- **TC-M02-197:** Falló con `HTTP 500 ERROR_INTERNO` en `POST /activos-biologicos/296/eventos/baja`.
- **Diagnóstico:** El lote 296 tenía datos adulterados de una prueba previa (2026-09-19) en `modulo2.historicos_estados_activos` donde el último registro tenía `id_estado_nuevo = 2` (INACTIVO), desincronizado con la tabla principal (`id_estado = 1` ACTIVO). El trigger `trg_fn_estado_activo_unico_vigente` detonó la excepción `STATE_INCONSISTENCY` con `ERRCODE = P0212`. Dado que `P0212` no está mapeado en `src/shared/db_error_translator.py`, el backend generó un `HTTP 500` genérico.

### 2.2. Intento 2 (Lote Virgen 281) — Aprobación Total
- **Decisión Fase 3.3:** Descartar lote 296 y reintentar con lote virgen sin histórico previo para evaluar la lógica pura de la aplicación.
- **Lote Seleccionado:** Lote 281 (especie 40, `cantidad_actual = 100`, 0 históricos de estados previos, 0 eventos previos, 1 fase activa).
- **Resultado:**
  - **TC-M02-196:** ✅ **APROBADO** (`HTTP 201 Created`, id_eventos=386). Validación exitosa de densidad límite exacto (`densidad_actual == densidad_maxima = 0.0008`).
  - **TC-M02-197:** ✅ **APROBADO** (`HTTP 201 Created`, id_eventos=387). Baja total aceptada; lote 281 transicionó automáticamente a estado `6 (BAJA)`, `cantidad_actual` quedó en 0 y la fase activa fue cerrada (`es_activa = FALSE`).
- **Aserciones Newman:** 7/7 aprobadas (0 fallas, 0 omitidas).

---

## 3. Selección y Análisis de Lote Virgen (SELECT)

### 3.1. Candidatos Evaluados en PostgreSQL TEST
Consulta ejecutada sobre lotes poblacionales en estado `ACTIVO (1)` con cantidad > 0, fecha previa y sin múltiples históricos:

| ID Lote | Especie | Infra | Creación | Cantidad | Históricos Estados | Último Estado Histórico | Eventos Previos | Fases Activas |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **130** | 4 | 1 | 2026-09-09 | 2 | 0 | NULL | 1 (reservado TC-196) | 1 |
| **281** | 40 | 48 | 2026-06-01 | 100 | 0 | NULL | 0 | 1 |
| **283** | 40 | 47 | 2026-06-01 | 48 | 0 | NULL | 0 | 1 |
| **328** | 40 | 60 | 2026-06-01 | 100 | 0 | NULL | 0 | 1 |

### 3.2. Justificación de Selección: Lote 281
Se seleccionó el **Lote 281** debido a:
1. **Aislamiento Histórico Total:** Posee 0 registros previos en `modulo2.historicos_estados_activos` (`ultimo_estado_historico = NULL`), eliminando cualquier riesgo de desincronización en el trigger `trg_fn_estado_activo_unico_vigente`.
2. **Sin Eventos Previos:** 0 eventos en `modulo2.eventos_activos`, garantizando que la fecha del evento no colisione cronológicamente.
3. **Fase Activa Válida:** Cuenta con 1 gestión de fase activa (`modulo2.gestiones_fases.es_activa = TRUE`), permitiendo validar el cierre automático de la fase al pasar a BAJA.
4. **Cantidad Limpia:** 100 individuos para baja total exacta.

---

## 4. Configuración de Precondición y Teardown (Especie 4)

- **Precondición (TC-M02-196):**
  Configuración vía API `PATCH /configuracion/especies/4`:
  - `densidad_maxima_por_especie`: `0.0008` (igualdad exacta con Lote 130: 2 individuos / 2500 m² = 0.0008).
  - Verificación SQL: `densidad_maxima_por_especie = 0.0008`.
- **Teardown (Post-Ejecución):**
  Restauración vía API `PATCH /configuracion/especies/4`:
  - `densidad_maxima_por_especie`: `null`.
  - Verificación SQL: `densidad_maxima_por_especie = NULL` (restaurado formalmente).
- **Consumo de Lote:**
  El Lote 281 pasó legítima e irreversiblemente a estado `BAJA (6)` como parte del flujo de prueba.

---

## 5. Métricas de Ejecución Newman CLI (Intento Final)

```bash
npx newman run tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G31/test_tc_m02_g31.json \
  --env-var "baseUrl=https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test" \
  --env-var "admin_email=administador.dev@gmail.com" \
  --env-var "admin_password=Test1234!" \
  --env-var "id_lote=130" \
  --env-var "id_especie=4" \
  --env-var "id_lote_197=281" \
  --env-var "cantidad_baja_197=100" \
  --env-var "fecha_baja_dinamica=2026-09-25" \
  -r cli,htmlextra \
  --reporter-htmlextra-export tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G31/resultados/resultado_TC-M02-G31_reintento3.html
```

| Métrica | Valor |
|---|---|
| **Total Peticiones (Requests)** | 7 |
| **Peticiones Fallidas** | 0 |
| **Total Aserciones (Assertions)** | 7 |
| **Aserciones Aprobadas** | 7 (100%) |
| **Aserciones Fallidas** | 0 (0%) |
| **Aserciones Omitidas** | 0 |
| **Tiempo Total de Ejecución** | 2.4s |
| **Tiempo de Respuesta Promedio** | 268ms |
| **Datos Totales Recibidos** | 3.69 KB |

### Detalle de Aserciones por Carpeta:
1. `0. Autenticación Administrador`:
   - `Autenticación exitosa (HTTP 200 OK)`: ✅ PASS
2. `TC-M02-196`:
   - `TC-M02-196: Evento crecimiento en límite de densidad aceptado (HTTP 201 Created)`: ✅ PASS
   - `TC-M02-196: Consulta de lote tras crecimiento completada (HTTP 200 OK)`: ✅ PASS
   - `Teardown TC-M02-196: Confirmar lote en estado ACTIVO`: ✅ PASS
3. `TC-M02-197`:
   - `TC-M02-197: Baja total aceptada exitosamente (HTTP 201 Created)`: ✅ PASS
   - `TC-M02-197: Consulta de lote tras baja total completada (HTTP 200 OK)`: ✅ PASS
   - `Teardown TC-M02-197: Confirmar estado terminal BAJA sin residuos activos`: ✅ PASS

---

## 6. Conteos e Inocuidad (SELECT Pre / Post)

| Tabla | Conteo Pre-Run | Conteo Post-Run | Delta | Justificación del Delta |
|---|:---:|:---:|:---:|---|
| `modulo2.activos_biologicos` | 386 | 386 | 0 | Inalterado (no se crearon ni eliminaron activos) |
| `modulo2.detalles_activos_biologicos_poblacionales` | 120 | 120 | 0 | Inalterado (actualización in-place de cantidad a 0) |
| `modulo2.eventos_productivos` | 7 | 7 | 0 | Inalterado |
| `modulo2.gestiones_fases` | 120 | 120 | 0 | Inalterado (la fase activa del lote 281 se cerró `es_activa = FALSE`) |
| `modulo2.historicos_estados_activos` | 134 | 135 | **+1** | **Legítimo**: registro de transición de estado `ACTIVO (1) → BAJA (6)` del Lote 281 |

### Estado Final de Lotes Auditados:
- **Lote 130 (TC-M02-196):**
  - `id_estado = 1 (ACTIVO)`
  - `cantidad_actual = 2`
  - `peso_promedio = 2.50 kg`
  - `biomasa_total = 5.00 kg`
- **Lote 281 (TC-M02-197):**
  - `id_estado = 6 (BAJA)`
  - `nombre_estado = 'BAJA'`
  - `cantidad_actual = 0`
  - `cant_he = 1` (registro de histórico de baja)
  - `ult_he = 6`
  - `gf_act = 0` (fase activa cerrada)

---

## 7. Diagnóstico Técnico y Recomendaciones al Equipo de Desarrollo

### 7.1. Causa Raíz de Falla en Lote 296
La falla en el Intento 1 no se debió a un defecto en la lógica de negocio de la baja total, sino a dos factores combinados:
1. **Dato corrupto en el Lote 296:** Registros contradictorios en `modulo2.historicos_estados_activos` dejaron el último estado histórico en `2 (INACTIVO)`, en discrepancia con `modulo2.activos_biologicos.id_estado = 1 (ACTIVO)`.
2. **Defecto en el Manejador de Errores de Base de Datos:** El trigger `trg_fn_estado_activo_unico_vigente` detectó la inconsistencia y lanzó una excepción con `ERRCODE = P0212` (`STATE_INCONSISTENCY`). En `src/shared/db_error_translator.py`, el código `P0212` no está contemplado, por lo que cae en la excepción genérica `InfrastructureError` y se transforma en `HTTP 500 ERROR_INTERNO` en lugar de un `HTTP 409 ConflictError`.

### 7.2. Recomendación de Issue a Desarrollo
Se recomienda abrir un **Defecto de Backend** para:
- Mapear el código PostgreSQL **`P0212`** (`STATE_INCONSISTENCY`) en `src/shared/db_error_translator.py` traduciéndolo a `ConflictError(code='ESTADO_ACTIVO_INCONSISTENTE')` (HTTP 409).
- Mapear de forma preventiva los códigos relacionados:
  - **`P0211`** (`INVALID_TRANSITION`) $\to$ `ValidationError` / `ConflictError` (HTTP 400 / 409).
  - **`P0224`** / **`P0225`** (validaciones de estados y fases) para evitar retornos de HTTP 500 no controlados.

---

## 8. Veredicto Final

**VEREDICTO:** 🟢 **APROBADO** (Con recomendación de mantenimiento en `db_error_translator.py`).  
Ambos subcasos han sido verificados de forma rigurosa y empírica en el entorno TEST:
- **TC-M02-196:** APROBADO (Igualdad exacta `densidad == densidad_maxima` es válida y aceptada con HTTP 201).
- **TC-M02-197:** APROBADO (Baja total hasta 0 aceptada con HTTP 201, transición a estado terminal BAJA y cierre de fase activa confirmados).
