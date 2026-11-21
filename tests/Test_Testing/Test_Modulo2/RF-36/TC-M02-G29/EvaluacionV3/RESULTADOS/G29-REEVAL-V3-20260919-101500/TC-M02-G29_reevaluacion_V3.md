# Reevaluación V3 — TC-M02-G29

## 1. Metadata
- **Caso de Prueba:** TC-M02-G29 (RF-36 / RF-52: Auditoría y Trazabilidad de Activos Biológicos)
- **Identificador de Corrida (RUN_ID):** `G29-REEVAL-V3-20260919-101500`
- **Fecha de Ejecución:** 2026-09-19
- **Hora:** 10:12:50 COT (15:12:50 UTC)
- **Entorno:** TEST (`sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io`)
- **Motor de Base de Datos:** PostgreSQL 15 en `158.69.200.27:5448/sgpmp_test`
- **Evaluador:** Sebastian
- **Ronda:** V3
- **Reintento:** `_reintento2`
- **Herramienta:** Newman CLI v6.2.2 (Node.js v20.18.0)

---

## 2. Preflight Ejecutado
Previo a la ejecución oficial V3 se validaron de forma controlada y empírica las condiciones operativas de los servicios y bases de datos:
- **B.1 Health Check (`GET /health`):** HTTP 200 OK — `status: ok`.
- **B.2 Autenticación Admin (`POST /sesiones/`):** HTTP 200 OK — Token JWT emitido para cuenta `administador.dev@gmail.com` (`id_usuario=104`).
- **B.3 Precondición Lote 130 (`GET /activos-biologicos/130`):** HTTP 200 OK — Tipo: `POBLACIONAL`, Especie: Cachama Blanca (`id_especie=4`), Infraestructura: 1 (Estanque-01), Estado: 1 (ACTIVO), Cantidad actual: 3 individuos, Fase productiva activa: Fase 4.
- **B.4 Endpoint de Auditoría (`GET /activos-biologicos/auditoria`):** HTTP 200 OK — Operativo y accesible con parámetros de activo y paginación (171 registros históricos previos).

### Despliegue de Correcciones Confirmado:
1. **Fix Issue #346 (`tipo_evento` en consultas poblacionales):** `ConsultarActivoUseCase` emite `rf_origen='RF36'` y `tipo_evento='ACTIVO_POBLACIONAL_CONSULTA'` para lotes poblacionales (dejando de clasificar erróneamente como `RF35` / `ACTIVO_INDIVIDUAL_CONSULTA`).
2. **Fix PR #254 (Trigger de Baja):** `trg_fn_baja_cantidad_valida` evalúa correctamente `'POBLACIONAL'` con case-sensitivity sin arrojar excepción.
3. **Fix INC-M02-41-RF52 (Auditoría de Rechazos 400 - commit `9c5f3b63`):** Error handlers persisten en `modulo2.bitacora_auditoria_m02` los rechazos de validación con resultado `FALLIDO`.
4. **Migración Alembic M09 Resuelta:** La columna `tipo_dato` en `modulo9.metricas_produccion` fue aplicada exitosamente en PostgreSQL TEST, eliminando el fallo 500 que bloqueó el subcaso 203 en V2.

---

## 3. Contexto Histórico
- **V1 (2026-09-09):** Fallido (1 PASS, 2 FAIL). Fallo por excepción de trigger en baja (204) e intento rechazado sin persistencia en bitácora de auditoría (205).
- **V2 (2026-09-15):** Fallido (2 PASS, 1 FAIL). Los subcasos 204 y 205 aprobaron al 100%, pero el subcaso 203 (crecimiento) quedó bloqueado por excepción interna de base de datos (`UndefinedColumn: column metricas_produccion.tipo_dato does not exist` en módulo 9).
- **V3 (2026-09-19):** Verificación integral exitosa tras despliegue de migración M09, corrección de credenciales y unificación de la suite.

---

## 4. Cambios Aplicados al Spec
- **A.1 Credenciales Dinámicas:** Se eliminaron las credenciales hardcodeadas en texto plano en `TC-M02-203.json`, `TC-M02-204.json` y `TC-M02-205.json`, parametrizándolas vía variables `{{admin_email}}` y `{{admin_password}}`.
- **A.2 Cantidad Medida Dinámica:** Se implementó el paso setup `0.1` en el spec para consultar la `cantidad_actual` real del lote antes del evento de crecimiento, inyectando `{{cantidad_medida_dinamica}}` y evitando inconsistencias muestrales.
- **A.3 Consolidación en Suite Única:** Se integraron los 3 subcasos en el runner unificado [test_tc_m02_g29.json](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G29/test_tc_m02_g29.json) ejecutando de forma atómica: Login → Setup → Crecimiento + Audit → Baja + Audit → PATCH Rechazado + Audit → Check inmutabilidad → Checkpoint final.

---

## 5. Resultados por Subcaso

### 5.1 TC-M02-203: Auditoría tras Evento de Crecimiento Válido
- **Resultado Técnico:** ✅ **PASS COMPLETO**
- **HTTP Status:** 201 Created (159 ms)
- **Registro en Bitácora:** `id_bitacora=3038`
  - `rf_origen`: `RF40`
  - `tipo_evento`: `EVENTO_CRECIMIENTO_REGISTRADO`
  - `tipo_activo`: `POBLACIONAL`
  - `resultado`: `EXITOSO`
  - `id_usuario_responsable`: `104`
  - `descripcion`: `Evento de crecimiento: PESO = 58.0 gr`
- **Evidencia:** Aserciones aprobadas 4/4 (Código 201, Total registros > 0, Coincidencia de tipo_evento y rf_origen).

### 5.2 TC-M02-204: Auditoría tras Evento de Baja Válido
- **Resultado Técnico:** ✅ **PASS COMPLETO**
- **HTTP Status:** 201 Created (160 ms)
- **Impacto Biológico:** `cantidad_actual` decrementada en 1 unidad (3 → 2).
- **Registro en Bitácora:** `id_bitacora=3039`
  - `rf_origen`: `RF45`
  - `tipo_evento`: `BAJA_REGISTRADA`
  - `tipo_activo`: `POBLACIONAL`
  - `resultado`: `EXITOSO`
  - `id_usuario_responsable`: `104`
  - `descripcion`: `Baja registrada: venta — Prueba de auditoria TC-M02-204 suite V3`
- **Evidencia:** Aserciones aprobadas 4/4 (Código 201, Total registros > 0, Coincidencia de tipo_evento y rf_origen).

### 5.3 TC-M02-205: Auditoría tras Intento Rechazado (PATCH `biomasa_total`)
- **Resultado Técnico:** ✅ **PASS COMPLETO**
- **HTTP Status:** 400 Bad Request (124 ms)
- **Error Code:** `VAL_ENTRADA` (`"Al menos un campo debe estar presente para actualizar"`)
- **Registro en Bitácora:** `id_bitacora=3040`
  - `rf_origen`: `RF36`
  - `tipo_evento`: `VALIDACION_RECHAZADA`
  - `resultado`: `FALLIDO`
  - `id_usuario_responsable`: `104`
  - `descripcion`: `PATCH /activos-biologicos/130 rechazado por validación de entrada (400)`
- **Inmutabilidad:** `GET /activos-biologicos/130` confirmó que `biomasa_total` no fue alterada (no es 999.99).
- **Evidencia:** Aserciones aprobadas 6/6 (Rechazo 400 estricto, error_code VAL_ENTRADA, auditoría del rechazo localizada con resultado FALLIDO y biomasa inalterada).

---

## 6. Resumen de Checkpoints

| Paso | Esperado | Obtenido | Estado |
| :--- | :--- | :--- | :---: |
| **0. Autenticación admin** | HTTP 200 con JWT válido | HTTP 200 OK, token emitido correctamente | **OK** |
| **1. TC-M02-203 (Crecimiento + Audit)** | HTTP 201 Created, auditoría `RF40` / `EVENTO_CRECIMIENTO_REGISTRADO` EXITOSO | HTTP 201 Created, entrada de auditoría id 3038 persistida con resultado EXITOSO | **OK** |
| **2. TC-M02-204 (Baja + Audit)** | HTTP 201 Created, auditoría `RF45` / `BAJA_REGISTRADA` EXITOSO | HTTP 201 Created, población decrementada, entrada de auditoría id 3039 EXITOSO | **OK** |
| **3. TC-M02-205 (Rechazo + Audit)** | HTTP 400 Bad Request `VAL_ENTRADA`, auditoría `RF36` / `VALIDACION_RECHAZADA` FALLIDO | HTTP 400 Bad Request, biomasa intacta, entrada de auditoría id 3040 FALLIDO | **OK** |
| **4. Consulta de Auditoría General** | HTTP 200 OK, historial accesible y consistente | HTTP 200 OK, registros íntegros con hash criptográfico SHA-256 | **OK** |

---

## 7. Hallazgos Adicionales

### Discrepancia Documentada sobre el CHECK CONSTRAINT del DBA
- **Antecedente:** Se reportó que el DBA había añadido un `CHECK CONSTRAINT` en `modulo2.bitacora_auditoria_m02` para rechazar combinaciones de tipos de evento/activo no conformes.
- **Verificación Empírica:** La consulta a `pg_constraint` e `information_schema.check_constraints` demostró que **no existe tal CHECK CONSTRAINT** en la base de datos PostgreSQL de TEST.
- **Evaluación de Riesgo:** El hallazgo **NO es bloqueante**, ya que el backend a nivel de caso de uso (`ConsultarActivoUseCase`) envía y persiste los valores normalizados (`RF36` y `ACTIVO_POBLACIONAL_CONSULTA`) de manera consistente. Se documenta como observación técnica para alineación con el DBA.

---

## 8. Veredicto Final

**VEREDICTO:** ✅ **APROBADO**

**Justificación:**
1. Los 3 subcasos de auditoría de activos biológicos (TC-M02-203, TC-M02-204 y TC-M02-205) cumplieron el 100% de sus aserciones técnicas en la suite oficial consolidada (17/17 PASS, 0 FAIL).
2. Se verificó la generación estricta de trazas de auditoría inmutables para operaciones agronómicas exitosas y para intentos de modificación directa no autorizados.
3. El endpoint central de auditoría (`GET /activos-biologicos/auditoria`) responde en tiempo (<135 ms) con estructura normalizada y hashes de integridad válidos.

---

## 9. Recomendaciones
1. Proceder con el cierre formal de las incidencias históricas asociadas a este caso de prueba:
   - Defecto de trigger de baja (resuelto por PR #254).
   - Defecto de auditoría de peticiones 400 (INC-M02-41-RF52 / commit `9c5f3b63`).
   - Defecto de clasificación de eventos de consulta poblacional (Issue #346).
2. Coordinar con el DBA si se mantendrá el control de coherencia exclusivamente en la capa de negocio o si se creará formalmente una migración Alembic para el CHECK CONSTRAINT en la tabla `modulo2.bitacora_auditoria_m02`.
3. Para ciclos futuros de pruebas que consuman bajas en el Lote 130, considerar reabastecer o sembrar un lote virgen, dado que su población actual se ubica en 2 individuos.
