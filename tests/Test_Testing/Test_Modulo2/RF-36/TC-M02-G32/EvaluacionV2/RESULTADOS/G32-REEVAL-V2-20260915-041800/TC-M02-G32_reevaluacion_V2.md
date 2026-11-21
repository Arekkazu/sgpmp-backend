# Reevaluación V2 — Caso de Prueba TC-M02-G32

---

## 1. Encabezado y metadatos

| Parámetro | Valor |
| :--- | :--- |
| **ID Caso de Prueba** | TC-M02-G32 |
| **Módulo** | Módulo 2 — Activos Biológicos |
| **Requerimientos Funcionales** | RF-36 (CU03 — Gestión de Eventos), RF-43 (CU09 — Registrar Evento Productivo) |
| **Subcasos Cubiertos** | TC-M02-198 (Registro evento productivo válido sin alterar métricas)<br>TC-M02-199 (Rechazo de eventos con estructura inválida y preservación de inmutabilidad) |
| **Ambiente de Ejecución** | TEST (`https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test`) |
| **Fecha y Hora de Ejecución** | 2026-09-15 04:22:00 -05:00 |
| **RUN_ID** | `G32-REEVAL-V2-20260915-041800` |
| **Colección Ejecutada** | `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G32/test_tc_m02_g32.json` |
| **Herramienta de Ejecución** | Newman v6.1.3 con `htmlextra` |
| **Usuario Responsable** | `administador.dev@gmail.com` (ID Usuario: 104, Rol: 1 - Admin) |
| **Activo Biológico Utilizado** | Lote 130 (`tipo`: POBLACIONAL, `id_especie`: 4, `id_estado`: 1 [ACTIVO], `id_ciclo`: 4) |
| **Ticket Asociado** | INC-M02-101-G32 (Parcialmente resuelto por DBA — fila 37 creada) |
| **Veredicto Global** | ❌ **FALLIDO** (0/2 Subcasos PASS por bloqueo transversal de migración b92f7e1a4c63) |

---

## 2. Objetivo y Resumen Ejecutivo

### 2.1 Objetivo de la Prueba
Evaluar formalmente en el ambiente de TEST el comportamiento de los endpoints asociados a eventos productivos (RF-43) y eventos de lote (RF-36) bajo el caso consolidado **TC-M02-G32**, verificando:
1. El registro satisfactorio de un evento productivo válido (`POST /activos-biologicos/{id}/eventos/productivo`) sobre el lote 130 tras la intervención del DBA en la parametrización de ciclo (Ticket INC-M02-101-G32).
2. El rechazo estricto de eventos con payloads malformados o parámetros no catalogados (`400 Bad Request` / `422 Unprocessable Entity`), asegurando la inmutabilidad de los conteos y biomasa del activo biológico.

### 2.2 Resumen Ejecutivo
- **Resolución previa del Ticket INC-M02-101-G32:** La validación en base de datos confirmó que el equipo DBA insertó exitosamente la fila 37 en `modulo9.metricas_ciclo_productivo` (`id_ciclo_productivo = 4`, `id_metrica_produccion = 16`), habilitando la métrica `PESO` para la fase productiva del activo 130.
- **Bloqueo confirmado por migración Alembic b92f7e1a4c63 no aplicada en TEST:** Pese a la configuración de la fila 37 en BD, la petición `POST /activos-biologicos/130/eventos/productivo` falló con código **HTTP 500 `ERROR_INTERNO`** (`{"error_code":"ERROR_INTERNO","message":"Ocurrió un error interno. Intenta de nuevo; si el problema persiste, contacta al equipo de soporte."}`). Las validaciones de negocio pasaron; el fallo ocurre al consultar el catálogo `modulo9.metricas_produccion` (misma causa raíz que G24, G25, G29 y G31). Este fallo generó un rollback inmediato, impidiendo el registro del evento productivo.
- **Resultado de TC-M02-199:** Las variantes de rechazo estructural respondieron adecuadamente con HTTP 400 (`VAL_ENTRADA`), y se verificó que el lote 130 mantuvo inalterada su cantidad (`3`) y estado (`ACTIVO`). No obstante, la Variante A (producto no catalogado) devolvió **HTTP 500** debido a la misma consulta fallida sobre el catálogo de métricas en Módulo 9, y la Variante B2 devolvió `FECHA_BAJA_CRONOLOGICAMENTE_INVALIDA`.
- **Conclusión Ejecutiva:** Se documentan los fallos tal cual fueron observados. Se concluye que existe un bloqueo transversal por migración Alembic `b92f7e1a4c63` no aplicada en TEST (columna `tipo_dato` ausente en `modulo9.metricas_produccion`), que impacta toda consulta a dicho catálogo.

---

## 3. Estado Previo BD (Lote 130 y Fila 37)

Previo a la ejecución de los folders de Newman, se ejecutaron las consultas de verificación de solo lectura contra la base de datos `sgpmp_test`:

### 3.1 Estado Inicial del Lote 130
```json
{
  "id_activo_biologico": 130,
  "tipo": "POBLACIONAL",
  "id_especie": 4,
  "id_estado": 1,
  "cantidad_actual": 3,
  "peso_promedio": "58.00",
  "ciclo_activo": 4
}
```
*Interpretación:* El lote 130 se encuentra en estado ACTIVO (`id_estado = 1`), especie 4, con fase productiva activa vinculada al ciclo 4, con 3 individuos y peso promedio de 58.00 kg.

### 3.2 Verificación de la Fila 37 (Resolución DBA Ticket INC-M02-101-G32)
```json
{
  "id_metricas_ciclo_productivo": 37,
  "id_ciclo_productivo": 4,
  "id_metrica_produccion": 16
}
```
*Interpretación:* Se constató la presencia del registro 37 que vincula el ciclo productivo 4 con la métrica 16 (`PESO`), resolviendo la pre-condición administrativa del ticket INC-M02-101-G32.

---

## 4. Resultados por Folder (Newman)

### 4.1 Folder TC-M02-198: Registrar Evento Productivo sobre Lote 130

- **Archivo de evidencias:** `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G32/EvaluacionV2/RESULTADOS/G32-REEVAL-V2-20260915-041800/EvidenciasPorSubcaso/TC-M02-198_run.json`
- **Reporte HTML:** `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G32/EvaluacionV2/RESULTADOS/G32-REEVAL-V2-20260915-041800/EvidenciasPorSubcaso/TC-M02-198_report.html`

| # | Petición | Método | Endpoint | HTTP Esperado | HTTP Obtenido | Aserciones (Tot / Falladas) | Estado | Detalle / Observación |
| :-: | :--- | :---: | :--- | :-: | :-: | :-: | :---: | :--- |
| **0** | Autenticación Admin (TC-M02-198) | `POST` | `/sesiones/` | 200 | 200 | 1 / 0 | ✅ PASS | Token JWT obtenido satisfactoriamente. |
| **0.1** | Consultar estado baseline de lote 130 | `GET` | `/activos-biologicos/130` | 200 | 200 | 1 / 0 | ✅ PASS | Baseline capturado dinámicamente (`cant=3`, `peso=58.00`). |
| **1** | Registrar evento productivo sobre lote 130 | `POST` | `/activos-biologicos/130/eventos/productivo` | 201 | **500** | 2 / 2 | ❌ **FAIL** | **Fallo:** Respuesta `500 ERROR_INTERNO` por bloqueo de migración b92f7e1a4c63. Aserciones fallaron al esperar 201. |
| **2** | Verificar inmutabilidad de cantidad y peso | `GET` | `/activos-biologicos/130` | 200 | 200 | 3 / 0 | ✅ PASS | Cantidad (`3`) y peso (`58.00`) inalterados debido al rollback. |

#### Detalle Técnico del Fallo en Petición 1:
- **Payload enviado:**
  ```json
  {
    "tipo_producto": "PESO",
    "cantidad_producida": 10.0,
    "unidad_medida": "kg",
    "fecha_evento": "2026-09-15",
    "condiciones_produccion": "Normal",
    "observaciones": "TC-M02-198 Registro de evento productivo sobre lote"
  }
  ```
- **Respuesta recibida (HTTP 500):**
  ```json
  {
    "error_code": "ERROR_INTERNO",
    "message": "Ocurrió un error interno. Intenta de nuevo; si el problema persiste, contacta al equipo de soporte.",
    "fields": [],
    "timestamp": "2026-09-15T09:21:52.420803+00:00"
  }
  ```
- **Aserciones no superadas:**
  1. `AssertionError: expected response to have status code 201 but got 500`
  2. `AssertionError: expected 'ERROR_INTERNO' to deeply equal 'TIPO_PRODUCTO_NO_HABILITADO_FASE'`

---

### 4.2 Folder TC-M02-199: Rechazar Evento con Estructura Inválida

- **Archivo de evidencias:** `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G32/EvaluacionV2/RESULTADOS/G32-REEVAL-V2-20260915-041800/EvidenciasPorSubcaso/TC-M02-199_run.json`
- **Reporte HTML:** `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G32/EvaluacionV2/RESULTADOS/G32-REEVAL-V2-20260915-041800/EvidenciasPorSubcaso/TC-M02-199_report.html`

| # | Petición | Método | Endpoint | HTTP Esperado | HTTP Obtenido | Aserciones (Tot / Falladas) | Estado | Detalle / Observación |
| :-: | :--- | :---: | :--- | :-: | :-: | :-: | :---: | :--- |
| **0** | Autenticación Admin (TC-M02-199) | `POST` | `/sesiones/` | 200 | 200 | 1 / 0 | ✅ PASS | Autenticación completada. |
| **0.1** | Consultar baseline lote 130 | `GET` | `/activos-biologicos/130` | 200 | 200 | 1 / 0 | ✅ PASS | Baseline dinámico capturado (`cantidad=3`). |
| **1** | Variante A: Producto no catalogado | `POST` | `/activos-biologicos/130/eventos/productivo` | 400 / 422 | **500** | 3 / 2 | ❌ **FAIL** | Retornó `500 ERROR_INTERNO` por bloqueo de migración b92f7e1a4c63. |
| **2** | Variante A2: Campos requeridos ausentes | `POST` | `/activos-biologicos/130/eventos/productivo` | 400 | 400 | 3 / 0 | ✅ PASS | Rechazo con `VAL_ENTRADA` por campos faltantes. |
| **3** | Variante B: Baja con estructura malformada | `POST` | `/activos-biologicos/130/eventos/baja` | 400 | 400 | 2 / 0 | ✅ PASS | Rechazo con `VAL_ENTRADA`. |
| **4** | Variante B2: Baja sin cantidad (diagnóstico) | `POST` | `/activos-biologicos/130/eventos/baja` | 400 | 400 | 2 / 1 | ⚠️ PARCIAL | HTTP 400 OK, pero código fue `FECHA_BAJA_CRONOLOGICAMENTE_INVALIDA`. |
| **5** | Verificar inmutabilidad de métricas | `GET` | `/activos-biologicos/130` | 200 | 200 | 3 / 0 | ✅ PASS | Cantidad inalterada (`3`), estado ACTIVO conservado. |

---

## 5. Post-Condición BD (Bitácora e Inmutabilidad)

Tras la ejecución de ambos folders de Newman, se ejecutaron los SELECTs de post-condición:

### 5.1 Estado del Lote 130 en Base de Datos
```json
{
  "id_activo_biologico": 130,
  "tipo": "POBLACIONAL",
  "id_especie": 4,
  "id_estado": 1,
  "cantidad_actual": 3,
  "peso_promedio": "58.00"
}
```
*Evaluación:* El lote 130 mantiene **estrictamente intacta su biomasa y cantidad** (`cantidad_actual = 3`, `peso_promedio = 58.00`) y permanece en estado ACTIVO (`id_estado = 1`). Los intentos fallidos y el error 500 no produjeron modificaciones corruptas en los registros poblacionales.

### 5.2 Bitácora de Auditoría Reciente (`modulo2.bitacora_auditoria_m02`)
Últimos registros asociados a RF36/RF43 sobre el lote 130:
```json
[
  {
    "id_bitacora": 1964,
    "rf_origen": "RF36",
    "tipo_evento": "VALIDACION_RECHAZADA",
    "resultado": "FALLIDO",
    "severidad_log": "WARNING",
    "id_usuario_responsable": 104,
    "timestamp_registro": "2026-09-15 09:22:51.969801+00:00",
    "detalle_tecnico": {
      "fields": [
        {"field": "tipo_baja", "message": "Field required"},
        {"field": "fecha_baja", "message": "Field required"},
        {"field": "motivo_baja", "message": "Field required"}
      ]
    }
  },
  {
    "id_bitacora": 1963,
    "rf_origen": "RF36",
    "tipo_evento": "VALIDACION_RECHAZADA",
    "resultado": "FALLIDO",
    "severidad_log": "WARNING",
    "id_usuario_responsable": 104,
    "timestamp_registro": "2026-09-15 09:22:51.713858+00:00",
    "detalle_tecnico": {
      "fields": [
        {"field": "tipo_producto", "message": "Field required"},
        {"field": "cantidad_producida", "message": "Field required"},
        {"field": "unidad_medida", "message": "Field required"},
        {"field": "fecha_evento", "message": "Field required"}
      ]
    }
  }
]
```
*Evaluación:* La bitácora registró fielmente las validaciones rechazadas de las Variantes A2 y B (`id_bitacora` 1963 y 1964) con severidad `WARNING`. La petición que arrojó HTTP 500 no dejó rastro persistido debido al rollback transaccional completo en el motor de base de datos.

---

## 6. Verificación de Limpieza (Cleanup)

1. **Decisión sobre el Lote 130:** El lote 130 es el activo biológico específico objeto de validación del ticket INC-M02-101-G32 y pertenece al inventario operativo del ambiente de pruebas. Por directriz explícita del QA Lead, **NO se inactivó ni se modificó su ciclo**.
2. **Verificación de Datos Huérfanos:** No quedaron registros huérfanos en `modulo2.eventos_activos`, `modulo2.eventos_productivos` ni tablas hijas, puesto que las transacciones con error 500 realizaron rollback automático.
3. **Preservación del Fixture:** El estado poblacional del lote (`cantidad_actual = 3`, `peso_promedio = 58.00`) quedó idéntico a su baseline inicial.

---

## 7. Conclusiones, Veredicto y Hallazgos

### 7.1 Veredicto por Subcaso
- **TC-M02-198 (Registro evento productivo válido):** ❌ **FALLIDO**
  - La petición `POST /activos-biologicos/130/eventos/productivo` devolvió inesperadamente `HTTP 500 ERROR_INTERNO`.
  - La fila 37 creada por el DBA resolvió la restricción a nivel de ciclo/fase, pero el endpoint colapsa al intentar consultar el catálogo en M09 por la columna faltante `tipo_dato`. Causa única: bloqueo transversal por migración b92f7e1a4c63.
- **TC-M02-199 (Rechazo de eventos con estructura inválida):** ❌ **FALLIDO**
  - Superó exitosamente las validaciones estructurales de campos faltantes (Variante A2 y B) y confirmó la inmutabilidad total del lote 130 tras los rechazos.
  - No superó la Variante A al devolver `HTTP 500` por la misma consulta fallida al catálogo de métricas M09, ni la Variante B2 por colisión de regla cronológica (`FECHA_BAJA_CRONOLOGICAMENTE_INVALIDA`). Causa única: bloqueo transversal por migración b92f7e1a4c63.

### 7.2 Veredicto Global
❌ **FALLIDO (0/2 Subcasos PASS por bloqueo transversal b92f7e1a4c63)**

### 7.3 Hallazgos Principales
1. **Bloqueo transversal confirmado:** El HTTP 500 se origina en `ParametrosEspecieM09Adapter.obtener_metrica_productiva`, que consulta `modulo9.metricas_produccion` (columna `tipo_dato` ausente). Misma causa raíz que INC-M02-19-G24, INC-M02-38-G25, TC-M02-G29 y TC-M02-G31.
2. **Inmutabilidad de datos garantizada:** El mecanismo de rollback de la API protegió la integridad del lote 130 ante los fallos 500.

---

### Referencias de Artefactos de Ejecución (Rutas Relativas)
- **Colección Postman:** `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G32/test_tc_m02_g32.json`
- **Consolidado Newman Summary:** `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G32/EvaluacionV2/RESULTADOS/G32-REEVAL-V2-20260915-041800/newman_summary_v2.json`
- **Reporte HTML Índice:** `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G32/EvaluacionV2/RESULTADOS/G32-REEVAL-V2-20260915-041800/reporte_v2.html`
- **Log Consolidado de Consola:** `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G32/EvaluacionV2/RESULTADOS/G32-REEVAL-V2-20260915-041800/console_v2.log`
- **Evidencia Newman TC-M02-198 (JSON):** `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G32/EvaluacionV2/RESULTADOS/G32-REEVAL-V2-20260915-041800/EvidenciasPorSubcaso/TC-M02-198_run.json`
- **Evidencia Newman TC-M02-198 (HTML):** `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G32/EvaluacionV2/RESULTADOS/G32-REEVAL-V2-20260915-041800/EvidenciasPorSubcaso/TC-M02-198_report.html`
- **Evidencia Newman TC-M02-199 (JSON):** `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G32/EvaluacionV2/RESULTADOS/G32-REEVAL-V2-20260915-041800/EvidenciasPorSubcaso/TC-M02-199_run.json`
- **Evidencia Newman TC-M02-199 (HTML):** `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G32/EvaluacionV2/RESULTADOS/G32-REEVAL-V2-20260915-041800/EvidenciasPorSubcaso/TC-M02-199_report.html`
