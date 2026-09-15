# TC-M02-G29 · RF-36 / RF-52 · Auditoría de Activos Biológicos
## Reporte Consolidado de Reevaluación V2 (Corrida Oficial Corregida)

---

## 1. Encabezado y Metadatos de Ejecución

- **Título Formal:** Caso de Prueba TC-M02-G29 · Verificación de Auditoría en Operaciones de Activos Biológicos (Crecimiento, Baja y Rechazos por Validación)
- **Identificador de Corrida (RUN_ID):** `G29-REEVAL-V2-20260915-000800`
- **Fecha de Reevaluación V2:** 2026-09-15 00:19:00 (UTC -5)
- **Iteración:** Corrida V2 — Ejecución Definitiva con Correcciones de Test y Lote Limpio (Intento 2).
  - *Nota:* El registro de consola del Intento 1 preliminar sobre lote 334 fue preservado en `console_v2_intento1.log`.
- **Historial de Ejecuciones Previas:**
  - Corrida Inicial V1: 2026-09-09 (`RESULTADOS/resultado_tc_m02_g29.md` — 1/3 PASS, fallo por trigger BD y rechazo sin auditar)
  - Primera Reevaluación: 2026-09-11 (`RESULTADOS/resultado_tc_m02_g29_reevaluacion.md` — 0/3 PASS, rechazo cronológico por fecha estática)
- **Entorno de Pruebas:** TEST
  - **URL Base API:** `https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test`
  - **Motor de Base de Datos:** PostgreSQL 15 en `158.69.200.27:5448/sgpmp_test` (Usuario: `member_qa`)
- **Herramientas de Ejecución:**
  - **Newman CLI:** versión `6.2.2`
  - **Newman Reporter HtmlExtra:** versión `1.23.1`
  - **Runtime:** Node.js v20.18.0 / Python 3.12 (virtualenv)
- **Colecciones Ejecutadas (Rutas Relativas):**
  - `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G29/TC-M02-203.json`
  - `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G29/TC-M02-204.json`
  - `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G29/TC-M02-205.json`
- **Reportes HTML Generados (Rutas Relativas):**
  - `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G29/EvaluacionV2/RESULTADOS/G29-REEVAL-V2-20260915-000800/TC-M02-203_report.html`
  - `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G29/EvaluacionV2/RESULTADOS/G29-REEVAL-V2-20260915-000800/TC-M02-204_report.html`
  - `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G29/EvaluacionV2/RESULTADOS/G29-REEVAL-V2-20260915-000800/TC-M02-205_report.html`
- **Log Consolidado de Consola (Ruta Relativa):**
  - `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G29/EvaluacionV2/RESULTADOS/G29-REEVAL-V2-20260915-000800/console_v2.log`
- **Veredicto Global:** ⚠️ **PASS PARCIAL (2/3 SUBCASOS 100% PASS) / 1 SUBCASO BLOQUEADO POR MIGRACIÓN ALeMBIC M09**

---

## 2. Objetivo de la Reevaluación y Resumen Ejecutivo

### 2.1 Contexto de Fallos Previos y Correcciones Validadas
El caso de prueba `TC-M02-G29` valida el cumplimiento de los requerimientos **RF-36** (Eventos y validación de activos biológicos) y **RF-52** (Bitácora de auditoría inmutable), exigiendo que cualquier evento agronómico exitoso o rechazado genere una traza auditable con usuario, timestamp y resultado en `modulo2.bitacora_auditoria_m02`.

En el ciclo previo se detectaron:
1. **Defecto del Trigger en BD (TC-M02-204):** `trg_fn_baja_cantidad_valida` comparaba contra `'poblacional'` en minúsculas arrojando HTTP 500. → **CORREGIDO EN BD TEST:** compara ahora con `'POBLACIONAL'::modulo2.enum_activo_biologico_tipo`.
2. **Defecto de Auditoría de Rechazos (TC-M02-205 / INC-M02-41-RF52):** Las peticiones rechazadas con HTTP 400 no escribían en bitácora. → **CORREGIDO EN BACKEND:** implementado vía `_auditar_validacion_rechazada_m02` en `src/shared/error_handlers.py` (commit `9c5f3b63`).
3. **Defectos del Test (Identificados en Intento 1 y Corregidos en Intento 2):**
   - **Clock Skew (TC-M02-203):** El cliente local generaba `new Date().toISOString()` con 2.18s de adelanto respecto al servidor, detonando `FECHA_FUTURA`. → **CORREGIDO EN TEST:** se aplicó margen de seguridad de 60s hacia atrás (`Date.now() - 60000`).
   - **Scope de Variable Postman (TC-M02-204):** Aserción usaba `pm.collectionVariables.get('id_lote')` (hardcodeado en 130) en vez de `pm.variables.get('id_lote')`. → **CORREGIDO EN TEST:** evalúa ahora la variable runtime inyectada en Newman.

### 2.2 Tabla Resumen Comparativa (Resultados de Corrida Corregida)

| Sub-caso | Enfoque de Prueba | Código Esperado | Código Obtenido | Aserciones | Veredicto Técnico | Veredicto Backend |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: |
| **TC-M02-203** | Auditoría tras registro de CRECIMIENTO válido | 200 / 201 | **500 Internal Server Error** | 2 / 5 PASS | ❌ FAIL | ⚠️ BLOQUEO MIGRACIÓN M09 |
| **TC-M02-204** | Auditoría tras registro de BAJA válida | 200 / 201 | **201 Created** | **5 / 5 PASS** | ✅ **PASS COMPLETO** | ✅ **PASS COMPLETO** |
| **TC-M02-205** | Auditoría tras rechazo de edición directa de biomasa | 400 Bad Request | **400 Bad Request** | **7 / 7 PASS** | ✅ **PASS COMPLETO** | ✅ **PASS COMPLETO** |

---

## 3. Estado Previo de la Base de Datos (Pre-condición)

### 3.1 Justificación de Selección de Lote Limpio (Decisión P6)
- **Lote 334 (Consumido en Intento 1):** Tras las ejecuciones preliminares quedó en estado `INACTIVO` con 98 unidades y 12 registros de auditoría.
- **Lote 300 (Seleccionado para Corrida Oficial Corregida):**
  - Tipo: `POBLACIONAL`
  - Especie: ID `40` (Bovino Qa Je)
  - Infraestructura: ID `48`
  - Estado: `ACTIVO` (`id_estado = 1`)
  - Cantidad inicial y actual: `100` individuos
  - Total eventos agronómicos previos: **0**
  - Fases activas: **1** (Fase 79)
  - Registros de auditoría previos: 3 (exclusivamente consultas históricas de solo lectura `RF35` de días anteriores).

### 3.2 Consulta SQL Literal de Pre-condición sobre Lote 300
```sql
SELECT a.id_activo_biologico, a.tipo, a.id_especie, a.id_infraestructura,
       a.id_estado, d.cantidad_inicial, d.cantidad_actual, d.peso_promedio,
       (SELECT COUNT(*) FROM modulo2.eventos_activos ea
        WHERE ea.id_activo_biologico = 300) AS total_eventos,
       (SELECT COUNT(*) FROM modulo2.bitacora_auditoria_m02 b
        WHERE b.id_activo_biologico = 300) AS total_auditoria,
       (SELECT COUNT(*) FROM modulo2.gestiones_fases gf
        WHERE gf.id_activo_biologico = 300 AND gf.es_activa = TRUE) AS fases_activas
FROM modulo2.activos_biologicos a
LEFT JOIN modulo2.detalles_activos_biologicos_poblacionales d
  ON a.id_activo_biologico = d.id_activo_biologico
WHERE a.id_activo_biologico = 300;
```

**Salida Literal Obtenida de PostgreSQL TEST:**
```text
(300, 'POBLACIONAL', 40, 48, 1, 100, 100, None, 0, 3, 1)
```

---

## 4. Resultados Detallados de la Ejecución (Newman)

### 4.1 Subcaso TC-M02-203 (Auditoría tras Crecimiento)

| Paso | Método | Endpoint | Código Esperado | Código Obtenido | Tiempo (ms) | Estado |
| :---: | :---: | :--- | :---: | :---: | :---: | :---: |
| **0** | `POST` | `/sesiones/` | 200 OK | **200 OK** | 879 ms | ✅ PASS |
| **1** | `POST` | `/activos-biologicos/300/eventos/crecimiento` | 200 / 201 | **500 Internal Server Error** | 151 ms | ❌ FAIL |
| **2** | `GET` | `/activos-biologicos/auditoria?id_activo_biologico=300&rf_origen=RF40&resultado=EXITOSO` | 200 OK | **200 OK** | 115 ms | ⚠️ FAIL ASERCIÓN |

- **Aserciones:** 2 PASS / 3 FAIL (Total: 5).
- **Diagnóstico del Fallo:**
  1. La corrección del clock skew con margen de 60s superó con éxito la validación cronológica (`validar_fecha_evento`), eliminando el error `FECHA_FUTURA`.
  2. Al avanzar el flujo, el caso de uso invocó la validación de parámetros de crecimiento para la especie (`ParametrosEspecieM09Adapter` -> `MetricaProduccionModel`), produciendo una excepción interna de PostgreSQL:
     ```text
     UndefinedColumn: column metricas_produccion.tipo_dato does not exist
     ```
  3. Esto confirma de manera empírica e irrefutable que el endpoint de crecimiento se encuentra contractualmente bloqueado en backend por la falta de aplicación de la migración Alembic `b92f7e1a4c63` en PostgreSQL TEST.

### 4.2 Subcaso TC-M02-204 (Auditoría tras Baja)

| Paso | Método | Endpoint | Código Esperado | Código Obtenido | Tiempo (ms) | Estado |
| :---: | :---: | :--- | :---: | :---: | :---: | :---: |
| **0** | `POST` | `/sesiones/` | 200 OK | **200 OK** | 667 ms | ✅ PASS |
| **1** | `POST` | `/activos-biologicos/300/eventos/baja` | 200 / 201 | **201 Created** | 158 ms | ✅ PASS |
| **2** | `GET` | `/activos-biologicos/auditoria?id_activo_biologico=300&rf_origen=RF45&resultado=EXITOSO` | 200 OK | **200 OK** | 110 ms | ✅ PASS |

- **Aserciones:** **5 PASS / 0 FAIL (100% PASS)**.
- **Validación Exitosa:**
  - El trigger `trg_fn_baja_cantidad_valida` descontó 1 unidad sin errores.
  - La corrección de `pm.variables.get('id_lote')` resolvió el ID dinámico `300`, haciendo que la aserción 3 aprobara de forma impecable (`audit.id_activo_biologico == 300`).
  - La bitácora contiene la traza con `rf_origen = 'RF45'`, `tipo_evento = 'BAJA_REGISTRADA'`, `resultado = 'EXITOSO'` y usuario `104`.

### 4.3 Subcaso TC-M02-205 (Auditoría tras Rechazo de PATCH Biomasa)

| Paso | Método | Endpoint | Código Esperado | Código Obtenido | Tiempo (ms) | Estado |
| :---: | :---: | :--- | :---: | :---: | :---: | :---: |
| **0** | `POST` | `/sesiones/` | 200 OK | **200 OK** | 835 ms | ✅ PASS |
| **1** | `PATCH`| `/activos-biologicos/300` (Body: `{"biomasa_total": 999.99}`) | 400 Bad Request | **400 Bad Request** | 166 ms | ✅ PASS |
| **2** | `GET` | `/activos-biologicos/auditoria?id_activo_biologico=300&pagina=1&page_size=20` | 200 OK | **200 OK** | 121 ms | ✅ PASS |
| **3** | `GET` | `/activos-biologicos/300` | 200 OK | **200 OK** | 119 ms | ✅ PASS |

- **Aserciones:** **7 PASS / 0 FAIL (100% PASS)**.
- **Validación Exitosa:**
  - El backend rechazó con HTTP 400 `VAL_ENTRADA` (`extra fields not permitted`).
  - Se verificó en bitácora el registro con `rf_origen = 'RF36'`, `resultado = 'FALLIDO'` y `severidad_log = 'WARNING'`.
  - La biomasa del lote no fue modificada.
  - **Incidente INC-M02-41-RF52 queda 100% RESUELTO Y CERRADO.**

### 4.4 Explicación de la Doble BAJA en Bitácora del Lote 334 (P5)
En la corrida preliminar (Intento 1) sobre el lote 334 se observaron dos registros de baja en bitácora (IDs `1293` a las `05:08:13 UTC` e ID `1296` a las `05:11:12 UTC`, separados por 2 minutos y 59 segundos):
- **Causa Técnica:** Para validar en vivo la respuesta del trigger en PostgreSQL TEST sin esperar el reporte completo, se ejecutó una corrida interactiva exploratoria de `TC-M02-204` (generando el registro `1293`). Posteriormente, se ejecutó el script batch completo de Newman para generar los reportes exportables consolidados, ejecutando nuevamente `TC-M02-204` (generando el registro `1296`).
- **Conclusión de QA:** Ambas peticiones resultaron en `HTTP 201 Created` y decrementaron la cantidad de forma consistente, demostrando que el trigger de baja es totalmente determinista y resiliente ante ejecuciones sucesivas.

### 4.5 Métricas Globales Consolidadas (Corrida Definitiva Lote 300)

| Métrica | TC-M02-203 | TC-M02-204 | TC-M02-205 | Total Consolidado |
| :--- | :---: | :---: | :---: | :---: |
| **Peticiones HTTP Ejecutadas** | 3 | 3 | 4 | **10** |
| **Aserciones Totales** | 5 | 5 | 7 | **17** |
| **Aserciones PASS** | 2 | 5 | 7 | **14 (82.4%)** |
| **Aserciones FAIL** | 3 | 0 | 0 | **3 (17.6%)** |
| **Tiempo Total de Ejecución** | 1,145 ms | 935 ms | 1,241 ms | **3,321 ms** |
| **Subcasos con Aprobación Total** | 0 / 1 | **1 / 1 (100%)** | **1 / 1 (100%)** | **2 / 3 (66.7%)** |

---

## 5. Evidencia de Estado en BD PostgreSQL TEST (Post-condición y Auditoría)

### 5.1 Estado Posterior del Lote 300 tras Ejecución de Pruebas
```sql
SELECT a.id_activo_biologico, a.tipo, a.id_especie, a.id_infraestructura,
       a.id_estado, d.cantidad_inicial, d.cantidad_actual, d.peso_promedio,
       (SELECT COUNT(*) FROM modulo2.eventos_activos ea
        WHERE ea.id_activo_biologico = 300) AS total_eventos,
       (SELECT COUNT(*) FROM modulo2.bitacora_auditoria_m02 b
        WHERE b.id_activo_biologico = 300) AS total_auditoria
FROM modulo2.activos_biologicos a
LEFT JOIN modulo2.detalles_activos_biologicos_poblacionales d
  ON a.id_activo_biologico = d.id_activo_biologico
WHERE a.id_activo_biologico = 300;
```
**Salida Literal:**
```text
(300, 'POBLACIONAL', 40, 48, 1, 100, 99, None, 1, 6)
```
*Constataciones:*
- La baja descontó 1 individuo de forma atómica (`cantidad_actual = 99`).
- `total_eventos` pasó de 0 a 1.
- `total_auditoria` pasó de 3 a 6 registros.

### 5.2 Registros Literales Generados en `modulo2.bitacora_auditoria_m02`
```sql
SELECT id_bitacora, rf_origen, tipo_evento, resultado, severidad_log,
       id_usuario_responsable, timestamp_evento, timestamp_registro
FROM modulo2.bitacora_auditoria_m02
WHERE id_activo_biologico = 300
ORDER BY id_bitacora ASC;
```

**Salida Literal Obtenida:**
```text
(921,  'RF35', 'ACTIVO_INDIVIDUAL_CONSULTA', 'EXITOSO', 'INFO',    35,  2026-09-10 09:08:47.847738+00, 2026-09-10 09:08:47.847753+00)
(1217, 'RF35', 'ACTIVO_INDIVIDUAL_CONSULTA', 'EXITOSO', 'INFO',    35,  2026-09-12 01:20:14.624385+00, 2026-09-12 01:20:14.624413+00)
(1222, 'RF35', 'ACTIVO_INDIVIDUAL_CONSULTA', 'EXITOSO', 'INFO',    35,  2026-09-12 01:29:20.005139+00, 2026-09-12 01:29:20.005160+00)
(1300, 'RF45', 'BAJA_REGISTRADA',            'EXITOSO', 'INFO',    104, 2026-09-15 05:18:49.593526+00, 2026-09-15 05:18:49.593563+00)
(1301, 'RF36', 'VALIDACION_RECHAZADA',       'FALLIDO', 'WARNING', 104, 2026-09-15 05:18:53.619158+00, 2026-09-15 05:18:53.619424+00)
(1302, 'RF35', 'ACTIVO_INDIVIDUAL_CONSULTA', 'EXITOSO', 'INFO',    104, 2026-09-15 05:18:54.058825+00, 2026-09-15 05:18:54.058839+00)
```

**Verificaciones de Integridad:**
- Registro `1300`: `RF45`, `BAJA_REGISTRADA`, `EXITOSO`, usuario `104` (Admin) → Verificación TC-M02-204.
- Registro `1301`: `RF36`, `VALIDACION_RECHAZADA`, `FALLIDO`, severidad `WARNING`, usuario `104` → Verificación TC-M02-205.
- Registro `1302`: `RF35`, `ACTIVO_INDIVIDUAL_CONSULTA`, `EXITOSO` → Verificación de lectura de inmutabilidad.

---

## 6. Verificación de Limpieza (Cleanup e Inocuidad de Datos)

### 6.1 Inactivación Lógica vía API Oficial
Conforme a la regla de inocuidad de datos, el lote 300 fue inactivado inmediatamente después de finalizar las pruebas mediante la API oficial:

- **Petición:** `PATCH /api-sgpmp-test/activos-biologicos/300/estado`
- **Payload:**
  ```json
  {
    "estado_nuevo": "INACTIVO",
    "fecha_cambio_estado": "2026-09-15",
    "motivo_cambio": "Cleanup prueba TC-M02-G29 reevaluacion V2 corrida 2"
  }
  ```
- **Respuesta API:** `HTTP 200 OK` (Transición de estado 1 -> 2, histórico ID `186` generado).

### 6.2 Comprobación en PostgreSQL TEST tras Cleanup
```sql
SELECT id_activo_biologico, id_estado, tipo,
       (SELECT COUNT(*) FROM modulo2.bitacora_auditoria_m02 WHERE id_activo_biologico = 300) AS total_auditoria
FROM modulo2.activos_biologicos
WHERE id_activo_biologico = 300;
```
**Salida Literal:**
```text
(300, 2, 'POBLACIONAL', 7)
```
- El lote 300 quedó en `id_estado = 2` (`INACTIVO`).
- El registro `1303` fue añadido a la bitácora con `rf_origen = 'RF44'`, `tipo_evento = 'ESTADO_CAMBIADO'`, garantizando la inmutabilidad de la bitácora (total registros: 7).
- No se ejecutó ninguna operación destructiva (cero DDL, cero DELETE).

---

## 7. Conclusiones, Diagnóstico Técnico y Dictamen Final

### 7.1 Estado Real de los Tres Subcasos
1. **TC-M02-205 (Auditoría tras Rechazo PATCH):** ✅ **PASS COMPLETO (100% — 7/7 aserciones).**
   - El incidente **INC-M02-41-RF52** ha sido resuelto y verificado en vivo. Las peticiones rechazadas con HTTP 400 generan su registro correspondiente en `bitacora_auditoria_m02` con `rf_origen = 'RF36'` y `resultado = 'FALLIDO'`.
2. **TC-M02-204 (Auditoría tras Evento BAJA):** ✅ **PASS COMPLETO (100% — 5/5 aserciones).**
   - El trigger PL/pgSQL `trg_fn_baja_cantidad_valida` en base de datos está completamente corregido en PostgreSQL TEST. Al corregir el scope de variable en el test (`pm.variables.get`), el subcaso aprobó de forma limpia y transparente.
3. **TC-M02-203 (Auditoría tras Evento CRECIMIENTO):** ⚠️ **BLOQUEO ESTRUCTURAL EN BACKEND (2/5 aserciones).**
   - La corrección de clock skew eliminó el error `FECHA_FUTURA`. Sin embargo, el subcaso fue rechazado con `HTTP 500 Internal Server Error` debido a una dependencia de esquema no aplicada en Módulo 9.

### 7.2 Evidencia y Trazabilidad Arquitectural del Bloqueo M09 (P4)
Se verificó la cadena de llamadas desde el endpoint hasta el fallo en base de datos:
1. **Router:** En `src/biological_assets/infrastructure/routers/activo_biologico_router.py` (Línea 703), se inyecta el adaptador:
   ```python
   parametros_port=ParametrosEspecieM09Adapter(db)
   ```
2. **Caso de Uso:** En `src/biological_assets/application/use_cases/gestion/registrar_evento_crecimiento_use_case.py` (Línea 85), se ejecuta:
   ```python
   parametro = self.parametros_port.obtener_por_tipo_medicion(
       activo.id_especie, dto.tipo_medicion, activo.tipo
   )
   ```
3. **Adaptador M09:** En `src/biological_assets/infrastructure/adapters/parametros_especie_m09_adapter.py` (Línea 53), se consulta el modelo SQLAlchemy `MetricaProduccionModel`.
4. **Modelo de Datos:** En `src/configuration/infrastructure/models/metrica_produccion_model.py` (Línea 67), `MetricaProduccionModel` mapea la columna `tipo_dato: Mapped[str] = mapped_column(String(10), ...)`, introducida por la migración Alembic `b92f7e1a4c63`.
5. **Fallo en PostgreSQL TEST:** La tabla física `modulo9.metricas_produccion` no contiene la columna `tipo_dato` porque la migración `b92f7e1a4c63` no ha sido ejecutada en el servidor, provocando `UndefinedColumn` y `HTTP 500`.

### 7.3 Veredicto Global y Recomendaciones
- **Veredicto Global:** ⚠️ **PASS PARCIAL (2 de 3 subcasos aprobados al 100%)**
- **Acciones Inmediatas:**
  1. **Cerrar INC-M02-41-RF52:** El defecto de auditoría en rechazos queda oficialmente resuelto y verificado.
  2. **Consolidar Corrección en Tests:** Mantener `pm.variables.get('id_lote')` y el margen de 60 segundos en las colecciones oficiales.
  3. **Escalar a DBA / DevOps:** Aplicar la migración Alembic `b92f7e1a4c63` en PostgreSQL TEST para desbloquear el subcaso TC-M02-203 y permitir el registro de eventos de crecimiento.

### 7.3.1 Bloqueo Recurrente por Migración b92f7e1a4c63
- **Descripción:** La migración Alembic `b92f7e1a4c63` (columna `modulo9.metricas_produccion.tipo_dato`) NO está aplicada en PostgreSQL TEST.
- **Impacto Confirmado:** Bloquea `POST /activos-biologicos` (caso G25) y `POST /activos-biologicos/{id}/eventos/crecimiento` (caso G29, subcaso TC-M02-203).
- **Evidencia en Vivo:** Excepción `HTTP 500 UndefinedColumn: column metricas_produccion.tipo_dato does not exist` verificada empíricamente en tiempo de ejecución.
- **Recomendación:** Escalar como issue de infraestructura consolidado (no como defecto puntual de un caso aislado). Requiere intervención de DevOps/DBA para aplicar la migración pendiente en la base de datos de pruebas.

### 7.4 Veredicto Global Final por Subcaso
1. **TC-M02-205 (Auditoría de Rechazo PATCH biomasa):**  
   ✅ **PASS COMPLETO (7/7 aserciones — 100%).** Defecto INC-M02-41-RF52 cerrado exitosamente.
2. **TC-M02-204 (Auditoría tras Evento de Baja):**  
   ✅ **PASS COMPLETO (5/5 aserciones — 100%).** Defecto del trigger PL/pgSQL corregido en BD TEST y defecto del test resuelto con `pm.variables.get('id_lote')`.
3. **TC-M02-203 (Auditoría tras Evento de Crecimiento):**  
   ⚠️ **BLOQUEO ESTRUCTURAL EN BACKEND (2/5 aserciones).** Defecto del test (clock skew) resuelto con margen de 60s; bloqueado en backend por la migración Alembic `b92f7e1a4c63` no aplicada en M09 (`UndefinedColumn: metricas_produccion.tipo_dato`).
4. **Dictamen Final Consolidado:**  
   ⚠️ **PASS PARCIAL (2/3 subcasos aprobados al 100% — Cumplimiento sustantivo de auditoría verificado en BAJA y RECHAZOS con escalamiento del bloqueo M09).**

---

### Referencias de Artefactos de Ejecución (Rutas Relativas)

- **Artefactos Consolidados (Raíz del RUN_ID):**
  - `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G29/EvaluacionV2/RESULTADOS/G29-REEVAL-V2-20260915-000800/newman_summary_v2.json`
  - `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G29/EvaluacionV2/RESULTADOS/G29-REEVAL-V2-20260915-000800/reporte_v2.html`
  - `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G29/EvaluacionV2/RESULTADOS/G29-REEVAL-V2-20260915-000800/console_v2.log` (Corrida definitiva lote 300)
- **Evidencias y Sub-reportes por Subcaso (`EvidenciasPorSubcaso/`):**
  - `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G29/EvaluacionV2/RESULTADOS/G29-REEVAL-V2-20260915-000800/EvidenciasPorSubcaso/snapshot_TC-M02-203.json`
  - `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G29/EvaluacionV2/RESULTADOS/G29-REEVAL-V2-20260915-000800/EvidenciasPorSubcaso/snapshot_TC-M02-204.json`
  - `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G29/EvaluacionV2/RESULTADOS/G29-REEVAL-V2-20260915-000800/EvidenciasPorSubcaso/snapshot_TC-M02-205.json`
  - `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G29/EvaluacionV2/RESULTADOS/G29-REEVAL-V2-20260915-000800/EvidenciasPorSubcaso/TC-M02-203_run.json`
  - `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G29/EvaluacionV2/RESULTADOS/G29-REEVAL-V2-20260915-000800/EvidenciasPorSubcaso/TC-M02-203_report.html`
  - `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G29/EvaluacionV2/RESULTADOS/G29-REEVAL-V2-20260915-000800/EvidenciasPorSubcaso/TC-M02-204_run.json`
  - `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G29/EvaluacionV2/RESULTADOS/G29-REEVAL-V2-20260915-000800/EvidenciasPorSubcaso/TC-M02-204_report.html`
  - `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G29/EvaluacionV2/RESULTADOS/G29-REEVAL-V2-20260915-000800/EvidenciasPorSubcaso/TC-M02-205_run.json`
  - `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G29/EvaluacionV2/RESULTADOS/G29-REEVAL-V2-20260915-000800/EvidenciasPorSubcaso/TC-M02-205_report.html`
  - `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G29/EvaluacionV2/RESULTADOS/G29-REEVAL-V2-20260915-000800/EvidenciasPorSubcaso/console_v2_intento1.log` (Corrida preliminar lote 334)
