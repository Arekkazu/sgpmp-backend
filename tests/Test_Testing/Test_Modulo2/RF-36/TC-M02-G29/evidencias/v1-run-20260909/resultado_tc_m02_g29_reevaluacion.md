# INFORME DE RESULTADOS DE PRUEBAS DE ACEPTACIÓN — REEVALUACIÓN
## CASO AGRUPADO: TC-M02-G29 (RF-36: Gestión Poblacional & RF-52: Auditoría y Trazabilidad)

- **Fecha de Reevaluación**: 2026-09-11
- **Fecha de Evaluación Anterior**: 2026-09-09
- **Entorno**: TEST (`https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test`)
- **Base de Datos**: PostgreSQL TEST (`158.69.200.27:5448/sgpmp_test`, usuario `member_qa`, **SOLO LECTURA**)
- **Herramienta**: Newman CLI v6.2.2 + Reporter `htmlextra`
- **Veredicto Global**: **FALLIDO (0 PASSED, 3 FALLIDOS — REEVALUACIÓN)**

---

## 1. Resumen Ejecutivo de Resultados

| Sub-caso | Enfoque de Prueba | Resultado Esperado | Resultado Obtenido | Aserciones Newman | Veredicto Reevaluación |
| :--- | :--- | :--- | :--- | :---: | :---: |
| **TC-M02-203** | Registro de auditoría tras evento CRECIMIENTO válido | `HTTP 200/201`. Auditoría registra `rf_origen: RF40`, `tipo_evento: EVENTO_CRECIMIENTO_REGISTRADO`, `resultado: EXITOSO`. | `HTTP 422 Unprocessable Entity` (`FECHA_INCOHERENTE`). La fecha fijada en la colección (`2026-09-09`) es cronológicamente anterior a la actividad más reciente del lote. | 4 / 5 (1 FAILED) | **FALLIDO (DESFASE CRONOLÓGICO FIXTURE)** |
| **TC-M02-204** | Registro de auditoría tras evento BAJA válido | `HTTP 200/201`. Auditoría registra `rf_origen: RF45`, `tipo_evento: BAJA_REGISTRADA`, `resultado: EXITOSO`. | `HTTP 400 Bad Request` (`FECHA_BAJA_CRONOLOGICAMENTE_INVALIDA`). Rechazo a nivel de aplicación por fecha `2026-09-09`. En BD TEST, el trigger `trg_fn_baja_actualizar_cantidad_lote` mantiene el defecto de enum minúscula. | 2 / 5 (3 FAILED) | **FALLIDO (DEFECTO PERSISTENTE TRIGGER BD)** |
| **TC-M02-205** | Registro de auditoría tras intento rechazado de modificación | `HTTP 400 Bad Request` (`VAL_ENTRADA`). Registro obligatorio de auditoría con `resultado: RECHAZADO` o `FALLIDO`. | `HTTP 400 Bad Request` (`VAL_ENTRADA`). Biomasa inalterada, pero **persiste la ausencia total de registro de auditoría del rechazo** en `modulo2.bitacora_auditoria_m02`. | 6 / 7 (1 FAILED) | **FALLIDO (DEFECTO NO CORREGIDO INC-M02-41-RF52)** |

---

## 2. Datos de Prueba y Verificación Previa de Integridad

Antes de ejecutar las suites de prueba, se verificó el estado de solo lectura del lote fixture en PostgreSQL TEST:

### 🐟 Estado Inicial de Lote 130 (2026-09-11 18:30 UTC):
```sql
SELECT a.id_activo_biologico, a.tipo, a.id_estado, d.cantidad_actual, d.peso_promedio, d.biomasa_total, d.densidad 
FROM modulo2.activos_biologicos a 
LEFT JOIN modulo2.detalles_activos_biologicos_poblacionales d ON a.id_activo_biologico = d.id_activo_biologico 
WHERE a.id_activo_biologico = 130;
```
- **ID Activo**: `130`
- **Tipo**: `POBLACIONAL`
- **ID Estado**: `1 (ACTIVO)`
- **Cantidad Actual**: `5`
- **Peso Promedio**: `2.50` kg
- **Biomasa Total**: `12.50` kg
- **Densidad**: `0.0020`
- **Fase Productiva**: Activa (`id_gestion_fases = 35`, `id_ciclo_productiva = 4`, `es_activa = True`)
- **Conclusión Previa**: Fixture 100% operativo y en condiciones nominales.

---

## 3. Detalle de Reevaluación por Sub-caso

### 3.1. Sub-caso TC-M02-203: Auditoría tras evento CRECIMIENTO válido

- **Colección Postman**: `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G29/TC-M02-203.json`
- **Reporte HTML Generado**: `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G29/RESULTADOS/reporte_TC-M02-203.html`
- **Petición 1 - Registrar Evento de Crecimiento**:
  - **Endpoint**: `POST /activos-biologicos/130/eventos/crecimiento`
  - **Payload Enviado (Original)**:
    ```json
    {
      "tipo_medicion": "PESO",
      "valor_medicion": 58.0,
      "unidad_medida": "gr",
      "nuevo_peso_promedio": 58.0,
      "cantidad_medida": 5,
      "tipo_agregacion": "PROMEDIO",
      "fecha": "2026-09-09T03:00:00Z"
    }
    ```
  - **Respuesta API**: `HTTP 422 Unprocessable Entity` ❌
    ```json
    {
      "error_code": "FECHA_INCOHERENTE",
      "message": "La fecha del evento es inválida o inconsistente con el historial.",
      "fields": [],
      "timestamp": "2026-09-11T23:31:10.226200+00:00"
    }
    ```
  - **Causa**: Al ejecutarse pruebas posteriores (TC-M02-G31, G32) con fechas del 10 y 11 de septiembre, la regla de dominio de eventos zootécnicos rechaza registrar un crecimiento con fecha anterior (`2026-09-09`).
- **Petición 2 - Consultar Bitácora de Auditoría (RF-52)**:
  - **Endpoint**: `GET /activos-biologicos/auditoria?id_activo_biologico=130&rf_origen=RF40&resultado=EXITOSO&pagina=1&page_size=10`
  - **Respuesta API**: `HTTP 200 OK` (retornó registros históricos del 2026-09-09).
- **Aserciones Newman**:
  - `[PASS]` Checkpoint 0 - Autenticación exitosa (HTTP 200 OK)
  - `[FAIL]` Código HTTP esperado: 200 OK o 201 Created: `expected [ 200, 201 ] to include 422`
  - `[PASS]` Código HTTP esperado: 200 OK al consultar auditoría
  - `[PASS]` Existe al menos un registro de auditoría para el evento de crecimiento
  - `[PASS]` El registro de auditoría contiene rf_origen RF40, tipo_evento CRECIMIENTO y resultado EXITOSO
- **Veredicto Reevaluación**: **FALLIDO (1/5 aserciones fallidas por validación cronológica)**.

---

### 3.2. Sub-caso TC-M02-204: Auditoría tras evento BAJA válido

- **Colección Postman**: `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G29/TC-M02-204.json`
- **Reporte HTML Generado**: `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G29/RESULTADOS/reporte_TC-M02-204.html`
- **Petición 1 - Registrar Evento de Baja**:
  - **Endpoint**: `POST /activos-biologicos/130/eventos/baja`
  - **Payload Enviado (Original)**:
    ```json
    {
      "tipo_baja": "VENTA",
      "cantidad_afectada": 1,
      "motivo_baja": "Prueba de auditoria TC-M02-204",
      "fecha_baja": "2026-09-09"
    }
    ```
  - **Respuesta Obtenida**: `HTTP 400 Bad Request` ❌
    ```json
    {
      "error_code": "FECHA_BAJA_CRONOLOGICAMENTE_INVALIDA",
      "message": "La fecha de baja no puede ser anterior al último registro de actividad registrado el 2026-09-11.",
      "fields": [
        {
          "field": "fecha_baja",
          "message": "La fecha de baja no puede ser anterior al último registro de actividad registrado el 2026-09-11."
        }
      ],
      "timestamp": "2026-09-11T23:31:43.197537+00:00"
    }
    ```
- **Petición 2 - Consultar Bitácora de Auditoría**:
  - **Endpoint**: `GET /activos-biologicos/auditoria?id_activo_biologico=130&rf_origen=RF45&resultado=EXITOSO&pagina=1&page_size=10`
  - **Respuesta API**: `HTTP 200 OK`, `total_registros: 0`.
- **Aserciones Newman**:
  - `[PASS]` Checkpoint 0 - Autenticación exitosa (HTTP 200 OK)
  - `[FAIL]` Código HTTP esperado: 200 OK o 201 Created: `expected [ 200, 201 ] to include 400`
  - `[PASS]` Código HTTP esperado: 200 OK al consultar auditoría
  - `[FAIL]` Existe al menos un registro de auditoría para el evento de baja: `expected +0 to be above +0`
  - `[FAIL]` El registro de auditoría contiene rf_origen RF45, tipo_evento BAJA y resultado EXITOSO: `Cannot read properties of undefined (reading 'rf_origen')`
- **Inspección de Triggers en PostgreSQL TEST**:
  1. El trigger `modulo2.trg_fn_baja_cantidad_valida()` fue verificado en `pg_proc` y ya contiene la corrección a mayúsculas:
     ```sql
     IF v_tipo_activo = 'POBLACIONAL' THEN
     ```
  2. Sin embargo, el trigger hermano `modulo2.trg_fn_baja_actualizar_cantidad_lote()` **AÚN CONTIENE EL DEFECTO DE ENUM EN MINÚSCULAS**:
     ```sql
     -- Extraído directamente de pg_proc en BD TEST (2026-09-11):
     CREATE OR REPLACE FUNCTION modulo2.trg_fn_baja_actualizar_cantidad_lote()
     ...
     IF v_tipo_activo <> 'poblacional' THEN  -- <-- PERSISTE COMPARACIÓN INVÁLIDA CON 'poblacional'
         RETURN NEW;
     END IF;
     ```
  - **Conclusión de BD**: El PR #254 corrigió parcialmente solo una de las dos funciones trigger de baja. El defecto `INC-M02-42-DB-TRIGGER` **persiste activo en la BD TEST** dentro de `trg_fn_baja_actualizar_cantidad_lote`.
- **Veredicto Reevaluación**: **FALLIDO (DEFECTO EN TRIGGER DE BASE DE DATOS PERSISTE)**.

---

### 3.3. Sub-caso TC-M02-205: Auditoría tras intento rechazado de modificación

- **Colección Postman**: `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G29/TC-M02-205.json`
- **Reporte HTML Generado**: `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G29/RESULTADOS/reporte_TC-M02-205.html`
- **Petición 1 - Intento de Modificación Directa de Métrica**:
  - **Endpoint**: `PATCH /activos-biologicos/130`
  - **Payload Enviado**:
    ```json
    {
      "biomasa_total": 999.99
    }
    ```
  - **Respuesta API**: `HTTP 400 Bad Request` (`VAL_ENTRADA` - *"Extra inputs are not permitted"*).
- **Petición 2 - Consultar Bitácora de Auditoría para Registro de Rechazo**:
  - **Endpoint**: `GET /activos-biologicos/auditoria?id_activo_biologico=130&pagina=1&page_size=20`
  - **Respuesta API**: `HTTP 200 OK`.
  - **Resultado**: La bitácora retornó registros históricos, pero **ninguno correspondiente al rechazo HTTP 400** del intento actual.
- **Petición 3 - Consultar Activo Biológico (Inmutabilidad)**:
  - **Endpoint**: `GET /activos-biologicos/130`
  - **Respuesta API**: `HTTP 200 OK`. `biomasa_total = 12.50` (inmutable, no se modificó a 999.99).
- **Aserciones Newman**:
  - `[PASS]` Checkpoint 0 - Autenticación exitosa (HTTP 200 OK)
  - `[PASS]` Código HTTP esperado: 400 Bad Request (Rechazo de edición directa)
  - `[PASS]` El error retornado es de validación de entrada (VAL_ENTRADA)
  - `[PASS]` Código HTTP esperado: 200 OK al consultar auditoría
  - `[FAIL]` Existe registro de auditoría para el intento fallido/rechazado (INC-M02-41-RF52): `DEFECTO INC-M02-41-RF52: El backend rechazó la petición con HTTP 400 pero no generó el registro de auditoría para la operación rechazada.`
  - `[PASS]` Código HTTP esperado: 200 OK al consultar activo
  - `[PASS]` La biomasa_total permanece inalterada (no es 999.99)
- **Veredicto Reevaluación**: **FALLIDO (DEFECTO DE TRAZABILIDAD INC-M02-41-RF52 PERSISTE COMO NO CORREGIDO)**.

---

## 4. Verificación Directa en Base de Datos PostgreSQL (`sgpmp_test`)

Se ejecutó la consulta SQL de solo lectura sobre `modulo2.bitacora_auditoria_m02` para auditar la ventana de tiempo de la reevaluación (últimos 15 minutos):

```sql
SELECT id_bitacora, rf_origen, tipo_evento, clasificacion_biologica, resultado, id_usuario_responsable, timestamp_registro, descripcion, detalle_tecnico 
FROM modulo2.bitacora_auditoria_m02 
WHERE id_activo_biologico = 130 
  AND timestamp_registro >= NOW() - INTERVAL '15 minutes'
ORDER BY id_bitacora DESC;
```

**Resultado obtenido de BD TEST**:
```text
Filas encontradas (1):
- id_bitacora:            1207
- rf_origen:              RF35
- tipo_evento:            ACTIVO_INDIVIDUAL_CONSULTA
- clasificacion:          ACCESO_DATOS
- resultado:              EXITOSO
- id_usuario_responsable: 1
- timestamp_registro:     2026-09-11 23:32:22 UTC
- descripcion:            None
```

### Hallazgos de la Verificación en BD:
1. **TC-M02-203**: Al haber sido rechazado con `HTTP 422 FECHA_INCOHERENTE`, no se generó ninguna entrada nueva de crecimiento en la bitácora durante la sesión.
2. **TC-M02-204**: Al haber sido rechazado por la regla de validación de fecha de baja (`HTTP 400`), no se insertó ninguna fila en `eventos_activos` ni se produjo el evento exitoso esperado.
3. **TC-M02-205**: Confirmado al 100%: **CERO entradas de resultado `RECHAZADO` o `FALLIDO`** asociadas al intento de `PATCH`. El validador de FastAPI descarta la petición antes de interactuar con el caso de uso y el repositorio de bitácora.
4. La única entrada generada fue `id_bitacora = 1207`, correspondiente a la consulta de lectura (`GET /activos-biologicos/130`) de verificación de inmutabilidad.

---

## 5. Comparativo con Evaluación Anterior (2026-09-09 vs 2026-09-11)

| Sub-caso | Resultado 2026-09-09 | Resultado Reevaluación 2026-09-11 | Estado del Defecto / Diagnóstico Comparativo |
| :--- | :--- | :--- | :--- |
| **TC-M02-203** | **PASS** (5/5 assertions)<br>HTTP 201 Created | **FAIL** (4/5 assertions)<br>HTTP 422 `FECHA_INCOHERENTE` | **CAMBIÓ DE COMPORTAMIENTO**: La prueba original usó `fecha = 2026-09-09`. Al existir actividad posterior registrada en el lote (10 y 11 de septiembre), la regla de integridad cronológica de la API rechazó el evento. Requiere usar fecha dinámica o timestamp actual para volver a PASS. |
| **TC-M02-204** | **FAIL** (2/5 assertions)<br>HTTP 500 Error Interno en BD | **FAIL** (2/5 assertions)<br>HTTP 400 `FECHA_BAJA_CRONOLOGICAMENTE_INVALIDA` | **DEFECTO PERSISTE EN BD**: La fecha estática `2026-09-09` fue interceptada por el validador de la API antes de llegar a la BD. En el motor PostgreSQL se comprobó que `trg_fn_baja_cantidad_valida` fue corregido, pero el trigger `trg_fn_baja_actualizar_cantidad_lote` mantiene la comparación defectuosa `IF v_tipo_activo <> 'poblacional' THEN`. El PR #254 está incompleto en TEST. |
| **TC-M02-205** | **FAIL** (6/7 assertions)<br>HTTP 400 Bad Request, sin auditoría | **FAIL** (6/7 assertions)<br>HTTP 400 Bad Request, sin auditoría | **DEFECTO PERSISTE IDÉNTICO (`INC-M02-41-RF52`)**: El validador sintáctico Pydantic de FastAPI rechaza la entrada pero no emite el registro de auditoría hacia `modulo2.bitacora_auditoria_m02`. Cero registros en BD para la operación rechazada. |

---

## 6. Estado de los Defectos Identificados

### 🐛 Defecto 1: INC-M02-42-DB-TRIGGER (Severidad Alta)
- **Estado**: **NO CORREGIDO / PARCIALMENTE ATENDIDO**.
- **Evidencia Técnica**:
  - En `modulo2.trg_fn_baja_cantidad_valida()`, la comparación ya usa `'POBLACIONAL'`.
  - Sin embargo, en `modulo2.trg_fn_baja_actualizar_cantidad_lote()`, se constató en línea 14:
    ```sql
    IF v_tipo_activo <> 'poblacional' THEN
    ```
    lo que provocará aborto de transacción (`invalid input value for enum`) ante cualquier baja válida sobre lotes poblacionales.

### 🐛 Defecto 2: INC-M02-41-RF52 (Severidad Media)
- **Estado**: **NO CORREGIDO**.
- **Evidencia Técnica**:
  - La petición `PATCH /activos-biologicos/130` con campos no permitidos es rechazada con `HTTP 400 Bad Request`, pero la bitácora `modulo2.bitacora_auditoria_m02` no registra el intento fallido. Se requiere un middleware o handler en FastAPI que capture excepciones `RequestValidationError` sobre rutas de activos biológicos y registre el evento de rechazo en auditoría.

---

## 7. Verificación Final de Inocuidad del Fixture

```sql
SELECT cantidad_actual, peso_promedio, biomasa_total, id_estado 
FROM modulo2.activos_biologicos a 
JOIN modulo2.detalles_activos_biologicos_poblacionales d ON a.id_activo_biologico = d.id_activo_biologico 
WHERE a.id_activo_biologico = 130;
```
- `cantidad_actual = 5` (Inalterado)
- `peso_promedio = 2.50` (Inalterado)
- `biomasa_total = 12.50` (Inalterado)
- `id_estado = 1 (ACTIVO)` (Inalterado)
- **Residuos en BD**: 0 filas residuales introducidas.

---

## 8. Segunda reevaluación — corrección de fecha dinámica (2026-09-11)

### 8.1. Cambios Aplicados a los Artefactos de Prueba
Para resolver el bloqueo sintáctico por desfasamiento temporal del lote 130, se actualizaron las colecciones Postman sin alterar aserciones, headers ni autenticación:
1. **`TC-M02-203.json`**:
   - Se añadió un *Pre-request Script* en la Petición 1 (`POST /activos-biologicos/130/eventos/crecimiento`):
     ```javascript
     // Corrección 2026-09-11: se reemplaza fecha estática por fecha dinámica para evitar rechazo por validación cronológica del historial del lote (ver resultado_tc_m02_g29_reevaluacion.md).
     pm.collectionVariables.set('fecha_evento_actual', new Date().toISOString());
     ```
   - Se reemplazó `"fecha": "2026-09-09T03:00:00Z"` por `"fecha": "{{fecha_evento_actual}}"`.
2. **`TC-M02-204.json`**:
   - Se añadió un *Pre-request Script* en la Petición 1 (`POST /activos-biologicos/130/eventos/baja`):
     ```javascript
     // Corrección 2026-09-11: se reemplaza fecha estática por fecha dinámica para evitar rechazo por validación cronológica del historial del lote (ver resultado_tc_m02_g29_reevaluacion.md).
     var hoy = new Date().toISOString().split('T')[0];
     pm.collectionVariables.set('fecha_baja_actual', hoy);
     ```
   - Se reemplazó `"fecha_baja": "2026-09-09"` por `"fecha_baja": "{{fecha_baja_actual}}"`.

---

### 8.2. Resultados Newman de la Segunda Reevaluación

| Sub-caso | Peticiones HTTP | Aserciones Totales | Exitosas | Fallidas | Código HTTP Recibido | Veredicto Actualizado |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **TC-M02-203** | 3 | 5 | 5 | 0 | `HTTP 201 Created` | **PASS (100%)** |
| **TC-M02-204** | 3 | 5 | 2 | 3 | `HTTP 400 Bad Request` | **FALLIDO (DEFECTO EN TRIGGER BD)** |

#### Detalle de Aserciones TC-M02-203 (PASS):
- `[PASS]` Checkpoint 0 - Autenticación exitosa (HTTP 200 OK)
- `[PASS]` Código HTTP esperado: 200 OK o 201 Created (Evento de crecimiento registrado) $\rightarrow$ `HTTP 201 Created` (166 ms).
- `[PASS]` Código HTTP esperado: 200 OK al consultar auditoría $\rightarrow$ `HTTP 200 OK` (121 ms).
- `[PASS]` Existe al menos un registro de auditoría para el evento de crecimiento.
- `[PASS]` El registro de auditoría contiene `rf_origen: RF40`, `tipo_evento: CRECIMIENTO` y `resultado: EXITOSO`.

#### Detalle de Aserciones TC-M02-204 (FALLIDO):
- `[PASS]` Checkpoint 0 - Autenticación exitosa (HTTP 200 OK)
- `[FAIL]` Código HTTP esperado: 200 OK o 201 Created (Baja registrada exitosamente): `expected [ 200, 201 ] to include 400`.
- `[PASS]` Código HTTP esperado: 200 OK al consultar auditoría.
- `[FAIL]` Existe al menos un registro de auditoría para el evento de baja: `expected +0 to be above +0`.
- `[FAIL]` El registro de auditoría contiene `rf_origen: RF45`, `tipo_evento: BAJA` y `resultado: EXITOSO`: `Cannot read properties of undefined (reading 'rf_origen')`.

---

### 8.3. Verificación de Auditoría en `modulo2.bitacora_auditoria_m02` y Reproducción de Defecto

Tras la re-ejecución, se consultaron directamente las entradas en PostgreSQL TEST:

```sql
SELECT id_bitacora, rf_origen, tipo_evento, clasificacion_biologica, resultado, id_usuario_responsable, timestamp_registro, descripcion, detalle_tecnico 
FROM modulo2.bitacora_auditoria_m02 
WHERE id_activo_biologico = 130 
  AND timestamp_registro >= '2026-09-11 23:45:00+00'
ORDER BY id_bitacora DESC;
```

**Registros obtenidos en BD TEST**:
```text
1. ID 1209 | RF45 | BAJA_REGISTRO_FALLIDO | CONTROL_ESTADO | FALLIDO | Usuario 1
   Timestamp: 2026-09-11 23:48:26 UTC
   Detalle Técnico: {"error": "El valor excede el tamaño o formato permitido por la base de datos", "tipo_baja": "venta"}

2. ID 1208 | RF40 | EVENTO_CRECIMIENTO_REGISTRADO | TRANSFORMACION_BIOLOGICA | EXITOSO | Usuario 1
   Timestamp: 2026-09-11 23:48:16 UTC
   Descripción: Evento de crecimiento: PESO = 58.0 gr
   Detalle Técnico: {"valor": "58.0", "tipo_medicion": "PESO"}
```

#### Diagnóstico Técnico del Defecto `INC-M02-42-DB-TRIGGER`:
1. **Superación del bloqueo cronológico**: Al enviar `fecha_baja` dinámica (`2026-09-11`), la petición superó la compuerta de validación de fechas de la aplicación.
2. **Activación del trigger de base de datos**: La solicitud ingresó a la transacción de persistencia en `modulo2.eventos_bajas`, donde se disparó el trigger `modulo2.trg_fn_baja_actualizar_cantidad_lote()`.
3. **Causa Raíz Reconfirmada en BD**: En la línea 14 de dicha función:
   ```sql
   IF v_tipo_activo <> 'poblacional' THEN
   ```
   PostgreSQL falla con código SQLSTATE `22P02` (*Invalid Text Representation / DataError*): `invalid input value for enum modulo2.enum_activo_biologico_tipo: "poblacional"`, debido a que el enum en PostgreSQL solo admite `'POBLACIONAL'` e `'INDIVIDUAL'` en mayúsculas.
4. **Mapeo de Error**: `src/shared/db_error_translator.py` (L174-L178) traduce excepciones `DataError` de SQLAlchemy/psycopg2 a:
   ```json
   {
     "error_code": "VALOR_FUERA_DE_RANGO",
     "message": "El valor excede el tamaño o formato permitido por la base de datos"
   }
   ```
   retornando `HTTP 400 Bad Request` al cliente.
5. **Registro de Auditoría de Fallo**: El caso de uso `RegistrarEventoBajaUseCase` capturó la excepción y persistió en `modulo2.bitacora_auditoria_m02` el evento fallido `BAJA_REGISTRO_FALLIDO` (`id_bitacora = 1209`).
6. **Conclusión**: El defecto **`INC-M02-42-DB-TRIGGER` SE REPRODUCE DIRECTAMENTE EN LA BASE DE DATOS** al fallar el trigger `trg_fn_baja_actualizar_cantidad_lote()`. La prueba ya no está bloqueada por fechas estáticas.

---

### 8.4. Estado Consolidado del Caso Agrupado TC-M02-G29

| Sub-caso | Resultado Final | Estado de Conformidad |
| :--- | :---: | :--- |
| **TC-M02-203** | **PASS (5/5)** | **CONFORME**. Evento de crecimiento persistido y auditado exitosamente con fecha dinámica. Lote 130 actualizado a peso promedio 58.00 g y biomasa 290.00 g. |
| **TC-M02-204** | **FALLIDO (2/5)** | **NO CONFORME**. Falla en BD TEST por bug de enum en trigger `modulo2.trg_fn_baja_actualizar_cantidad_lote()` (`INC-M02-42-DB-TRIGGER`). Persiste activo. |
| **TC-M02-205** | **FALLIDO (6/7)** | **NO CONFORME**. Rechazo `HTTP 400` de edición directa no genera entrada en bitácora de auditoría (`INC-M02-41-RF52`). Persiste activo. |

---

## 9. Tercera reevaluación: corrección del trigger por DBA (2026-09-13)

### 9.1. Contexto y Verificación Previa de la Corrección
El DBA del proyecto reportó haber corregido la función trigger `modulo2.trg_fn_baja_actualizar_cantidad_lote()`, sustituyendo la comparación en minúsculas `IF v_tipo_activo <> 'poblacional' THEN` por el valor en mayúsculas `IF v_tipo_activo <> 'POBLACIONAL' THEN`, correspondiente al tipo enum `modulo2.enum_activo_biologico_tipo`.

Previamente a la ejecución, se verificó mediante consulta directa al catálogo del sistema (`pg_proc`) en PostgreSQL TEST que la función contiene efectivamente:
```sql
IF v_tipo_activo <> 'POBLACIONAL' THEN
    RETURN NEW;
END IF;
```

Asimismo, se ajustó la credencial de autenticación en las colecciones Newman a `administador.dev@gmail.com` / `Test1234!` (debido al error 500 conocido de `admin@pecuaria.co`) y se flexibilizó la aserción de usuario responsable para admitir tanto `1` como `104` (ID dinámico del administrador en TEST).

---

### 9.2. Resultados Newman de la Tercera Reevaluación

#### Sub-caso TC-M02-204 (Verificación del Trigger de Baja)
* **Colección**: `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G29/TC-M02-204.json`
* **Reporte HTML**: `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G29/RESULTADOS/reporte_TC-M02-204.html`
* **Resultado de Ejecución**: **5 / 5 Aserciones PASSED (100%) — Exit Code 0**
* **Detalle de Peticiones y Aserciones**:
  - `POST /sesiones/`: `HTTP 200 OK` (831 ms) $\rightarrow$ `[PASS]` Checkpoint 0 - Autenticación exitosa.
  - `POST /activos-biologicos/130/eventos/baja`: **`HTTP 201 Created`** (143 ms) $\rightarrow$ `[PASS]` Código HTTP esperado: 200 OK o 201 Created (Baja registrada exitosamente).
  - `GET /activos-biologicos/auditoria?id_activo_biologico=130&rf_origen=RF45&resultado=EXITOSO`: `HTTP 200 OK` (126 ms):
    - `[PASS]` Código HTTP esperado: 200 OK al consultar auditoría.
    - `[PASS]` Existe al menos un registro de auditoría para el evento de baja.
    - `[PASS]` El registro de auditoría contiene rf_origen RF45, tipo_evento BAJA y resultado EXITOSO.

#### Sub-caso TC-M02-205 (Auditoría de Rechazo HTTP 400)
* **Colección**: `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G29/TC-M02-205.json`
* **Reporte HTML**: `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G29/RESULTADOS/reporte_TC-M02-205.html`
* **Resultado de Ejecución**: **6 / 7 Aserciones Conformes (85.7%) — 1 Fallida (INC-M02-41-RF52)**
* **Detalle de la Falla**:
  - `PATCH /activos-biologicos/130`: `HTTP 400 Bad Request` (`VAL_ENTRADA` — *"Extra inputs are not permitted"*).
  - `GET /activos-biologicos/auditoria`: Retorna `total_registros: 0` para eventos con `resultado: RECHAZADO` o `FALLIDO` y `rf_origen: RF35/RF36`.
  - `AssertionError`: `DEFECTO INC-M02-41-RF52: El backend rechazó la petición con HTTP 400 pero no generó el registro de auditoría para la operación rechazada.`

---

### 9.3. Verificación Directa en Base de Datos PostgreSQL TEST

#### A. Efecto de la Baja en Lote Poblacional 130 (`modulo2.detalles_activos_biologicos_poblacionales`):
```sql
SELECT id_activo_biologico, cantidad_actual, peso_promedio, biomasa_total, densidad
FROM modulo2.detalles_activos_biologicos_poblacionales
WHERE id_activo_biologico = 130;
```
* **Estado en BD**:
  - `id_activo_biologico`: `130`
  - `cantidad_actual`: **`4`** (descontada exactamente en 1 unidad desde 5 nominales tras la baja exitosa de TC-M02-204)
  - `peso_promedio`: `58.00`
  - `biomasa_total`: **`232.00`** (calculada automáticamente por el trigger: $4 \times 58.00 = 232.00$)
  - `densidad`: `0.0016` (calculada automáticamente sobre la superficie de la infraestructura 1)

#### B. Registro Exitoso en Bitácora de Auditoría (`modulo2.bitacora_auditoria_m02`):
```sql
SELECT id_bitacora, rf_origen, tipo_evento, resultado, timestamp_registro, id_usuario_responsable, descripcion
FROM modulo2.bitacora_auditoria_m02
WHERE id_activo_biologico = 130
ORDER BY id_bitacora DESC LIMIT 3;
```
* **Registros Confirmados**:
  - `id_bitacora: 1241` | `rf_origen: RF45` | `tipo_evento: BAJA_REGISTRADA` | `resultado: EXITOSO` | `id_usuario_responsable: 104` | `timestamp: 2026-09-13 20:46:15 UTC` | `descripcion: Baja registrada: venta — Prueba de auditoria TC-M02-204`

#### C. Constatación del Fallo de Auditoría en TC-M02-205:
```sql
SELECT count(*)
FROM modulo2.bitacora_auditoria_m02
WHERE id_activo_biologico = 130 
  AND (tipo_evento = 'VALIDACION_RECHAZADA' OR (resultado IN ('RECHAZADO', 'FALLIDO') AND rf_origen IN ('RF35', 'RF36')));
```
* **Resultado**: `0` registros. Confirmado que el rechazo HTTP 400 sigue sin persistir en la bitácora de auditoría.

---

### 9.4. Análisis Técnico Actualizado de `INC-M02-41-RF52` (Bug de Prefijo de Ruta)

A diferencia del diagnóstico preliminar histórico (que presumía ausencia total de código), la investigación técnica del commit `9c5f3b63` (`fix(rf36-m02): auditar en bitacora_auditoria_m02 los 400 de validacion`) reveló lo siguiente:

1. **Intento de Corrección Implementado**: En `src/shared/error_handlers.py`, se implementó la función `_auditar_validacion_rechazada_m02(request, fields)` invocada desde `request_validation_error_handler`.
2. **Causa Raíz del Fallo en TEST (Bug de Prefijo)**:
   - La función contiene la compuerta de validación:
     ```python
     if not request.url.path.startswith("/activos-biologicos"):
         return
     ```
   - En el entorno TEST desplegado tras el reverse proxy / ingress, la URL de las peticiones es `https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test/activos-biologicos/130`.
   - Por tanto, `request.url.path` es **`/api-sgpmp-test/activos-biologicos/130`**.
   - Como dicha cadena **no inicia con `"/activos-biologicos"`**, la condición evalúa a `False` y retorna de forma silenciosa e inmediata sin ejecutar la inserción en `modulo2.bitacora_auditoria_m02`.
3. **Acción Correctiva Requerida**:
   Ajustar la validación en `src/shared/error_handlers.py` para normalizar la ruta o evaluar:
   ```python
   path = request.url.path.removeprefix(request.scope.get("root_path", ""))
   if not ("/activos-biologicos" in request.url.path):
       return
   ```

---

### 9.5. Estado Consolidado y Dictamen Final del Caso Agrupado TC-M02-G29

| Sub-caso | Resultado Anterior (2026-09-11) | Resultado Actual (2026-09-13) | Estado de Conformidad |
| :--- | :---: | :---: | :--- |
| **TC-M02-203** | **PASS (5/5)** | **PASS (5/5)** | ✅ **CONFORME**. Evento de crecimiento persistido y auditado exitosamente con fecha dinámica. |
| **TC-M02-204** | **FAIL (2/5)** | **PASS (5/5)** | ✅ **CONFORME**. **DEFECTO INC-M02-42-DB-TRIGGER CORREGIDO**. Trigger `trg_fn_baja_actualizar_cantidad_lote` ejecuta sin error con `'POBLACIONAL'`. Descuento de lote y auditoría RF-45 exitosos. |
| **TC-M02-205** | **FAIL (6/7)** | **FAIL (6/7)** | ❌ **NO CONFORME**. Rechazo `HTTP 400` no genera auditoría. **INC-M02-41-RF52**: Parcialmente corregido en código (`9c5f3b63`) / no efectivo en TEST por bug de prefijo de ruta (`/api-sgpmp-test/`). |

#### Dictamen de Defectos:
* **`INC-M02-42-DB-TRIGGER`**: **CORREGIDO Y VERIFICADO EN REEVALUACIÓN 2026-09-13**. El trigger en PostgreSQL TEST opera nominalmente.
* **`INC-M02-41-RF52`**: **PARCIALMENTE CORREGIDO EN CÓDIGO / NO EFECTIVO EN TEST**. Requiere ajuste del prefijo de ruta en `_auditar_validacion_rechazada_m02()`.


