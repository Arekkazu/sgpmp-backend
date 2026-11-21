# INFORME DE RESULTADOS DE PRUEBAS DE ACEPTACIÓN
## CASO AGRUPADO: TC-M02-G29 (RF-36: Gestión Poblacional & RF-52: Auditoría y Trazabilidad)

- **Fecha de Ejecución**: 2026-09-09
- **Entorno**: TEST (`https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test`)
- **Base de Datos**: PostgreSQL TEST (`158.69.200.27:5448/sgpmp_test`, usuario `member_qa`, **SOLO LECTURA**)
- **Herramienta**: Newman CLI v6.2.2 + Reporter `htmlextra`
- **Veredicto Global**: **FAIL PARCIAL (1 PASS, 2 FAIL — 2 DEFECTOS IDENTIFICADOS)**

---

## 1. Resumen Ejecutivo de Resultados

| Sub-caso | Enfoque de Prueba | Resultado Esperado | Resultado Obtenido | Aserciones Newman | Veredicto |
| :--- | :--- | :--- | :--- | :---: | :---: |
| **TC-M02-203** | Registro de auditoría tras evento CRECIMIENTO válido | `HTTP 200/201`. Auditoría registra `rf_origen: RF40`, `tipo_evento: EVENTO_CRECIMIENTO_REGISTRADO`, `resultado: EXITOSO`. | `HTTP 201 Created`. Auditoría en API y BD confirmó registro ID `295` con `resultado: EXITOSO`, `usuario: 1`. | 5 / 5 PASSED | **PASS** |
| **TC-M02-204** | Registro de auditoría tras evento BAJA válido | `HTTP 200/201`. Auditoría registra `rf_origen: RF45`, `tipo_evento: BAJA_REGISTRADA`, `resultado: EXITOSO`. | `HTTP 500 Internal Server Error` (`ERROR_INTERNO`). Trigger de PostgreSQL falló por inconsistencia de enum. Auditoría registró `BAJA_REGISTRO_FALLIDO`. | 2 / 5 (3 FAILED) | **FAIL (DEFECTO TRIGGER BD)** |
| **TC-M02-205** | Registro de auditoría tras intento rechazado de modificación | `HTTP 400 Bad Request` (`VAL_ENTRADA`). Registro obligatorio de auditoría con `resultado: RECHAZADO` o `FALLIDO`. | `HTTP 400 Bad Request` (`VAL_ENTRADA`). `biomasa_total` intacta, pero **NO se generó registro de auditoría del rechazo** en `modulo2.bitacora_auditoria_m02`. | 6 / 7 (1 FAILED) | **FAIL (DEFECTO TRAZABILIDAD)** |

---

## 2. Datos de Prueba Utilizados

### 🐟 Lote Poblacional en TEST:
- **ID Activo:** `130`
- **Especie:** `4` (*Cachama Blanca*)
- **Estado:** `1 (ACTIVO)`
- **Fase Productiva:** Activa (`id_gestion_fases = 35`, `id_ciclo_productiva = 4`, `es_activa = True`)
- **Infraestructura:** `1` (*Estanque-01*)
- **Cantidad Actual:** `5`
- **Peso Promedio:** `58.00` g
- **Biomasa Total:** `290.00` g

### 👤 Credenciales Utilizadas:
- **Usuario Administrador:** `admin@pecuaria.co` (`id_usuario = 1`)

---

## 3. Detalle de Ejecución por Sub-caso

### 3.1. Sub-caso TC-M02-203: Auditoría tras evento CRECIMIENTO válido

- **Colección Postman**: `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G29/TC-M02-203.json`
- **Reporte HTML Generado**: `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G29/RESULTADOS/reporte_TC-M02-203.html`
- **Petición 1 - Registrar Evento de Crecimiento**:
  - **Endpoint**: `POST /activos-biologicos/130/eventos/crecimiento`
  - **Payload Enviado**:
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
  - **Respuesta API**: `HTTP 201 Created`
- **Petición 2 - Consultar Bitácora de Auditoría (RF-52)**:
  - **Endpoint**: `GET /activos-biologicos/auditoria?id_activo_biologico=130&rf_origen=RF40&resultado=EXITOSO`
  - **Respuesta API**: `HTTP 200 OK`
  - **Datos del Registro Obtenido**:
    ```json
    {
      "id_bitacora": 295,
      "id_evento": "5a5f8c13-...",
      "rf_origen": "RF40",
      "tipo_evento": "EVENTO_CRECIMIENTO_REGISTRADO",
      "clasificacion_biologica": "TRANSFORMACION_BIOLOGICA",
      "id_activo_biologico": 130,
      "resultado": "EXITOSO",
      "descripcion": "Evento de crecimiento: PESO = 58.0 gr",
      "id_usuario_responsable": 1,
      "severidad_log": "INFO"
    }
    ```
- **Aserciones Newman**:
  - `[PASS]` Checkpoint 0 - Autenticación exitosa (HTTP 200 OK)
  - `[PASS]` Código HTTP esperado: 200 OK o 201 Created (Evento de crecimiento registrado)
  - `[PASS]` Código HTTP esperado: 200 OK al consultar auditoría
  - `[PASS]` Existe al menos un registro de auditoría para el evento de crecimiento
  - `[PASS]` El registro de auditoría contiene rf_origen RF40, tipo_evento CRECIMIENTO y resultado EXITOSO
- **Veredicto**: **PASS**.

---

### 3.2. Sub-caso TC-M02-204: Auditoría tras evento BAJA válido

- **Colección Postman**: `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G29/TC-M02-204.json`
- **Reporte HTML Generado**: `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G29/RESULTADOS/reporte_TC-M02-204.html`
- **Petición 1 - Registrar Evento de Baja**:
  - **Endpoint**: `POST /activos-biologicos/130/eventos/baja`
  - **Payload Enviado**:
    ```json
    {
      "tipo_baja": "VENTA",
      "cantidad_afectada": 1,
      "motivo_baja": "Prueba de auditoria TC-M02-204",
      "fecha_baja": "2026-09-09"
    }
    ```
  - **Respuesta Obtenida**: `HTTP 500 Internal Server Error` ❌
    ```json
    {
      "error_code": "ERROR_INTERNO",
      "message": "Error inesperado en base de datos",
      "fields": [],
      "timestamp": "2026-09-09T05:29:33.451917+00:00"
    }
    ```
  - **Causa Raíz Diagnosticada**: La función trigger `modulo2.trg_fn_baja_cantidad_valida()` en PostgreSQL compara el enum de tipo de activo biológico de forma errónea:
    `IF v_tipo_activo = 'poblacional' THEN`
    Sin embargo, el tipo enum PostgreSQL `modulo2.enum_activo_biologico_tipo` define los valores en mayúsculas (`'POBLACIONAL'`, `'INDIVIDUAL'`), abortando la transacción por fallo de tipo enum.
- **Petición 2 - Consulta de Auditoría**:
  - El caso de uso capturó el error interno y registró un evento fallido `BAJA_REGISTRO_FALLIDO` (ID 297), pero no se pudo completar la baja exitosa esperada.
- **Aserciones Newman**:
  - `[PASS]` Checkpoint 0 - Autenticación exitosa (HTTP 200 OK)
  - `[FAIL]` Código HTTP esperado: 200 OK o 201 Created: `expected [ 200, 201 ] to include 500`
  - `[PASS]` Código HTTP esperado: 200 OK al consultar auditoría
  - `[FAIL]` Existe al menos un registro de auditoría para el evento de baja (resultado EXITOSO): `expected +0 to be above +0`
- **Veredicto**: **FAIL (DEFECTO EN TRIGGER DE BASE DE DATOS INC-M02-42-DB-TRIGGER)**.

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
  - **Respuesta API**: `HTTP 400 Bad Request`
  - **Cuerpo JSON**:
    ```json
    {
      "error_code": "VAL_ENTRADA",
      "message": "Errores de validacion en la solicitud",
      "fields": [
        {
          "field": "biomasa_total",
          "message": "Extra inputs are not permitted"
        }
      ],
      "timestamp": "2026-09-09T05:31:38.257321+00:00"
    }
    ```
- **Petición 2 - Consultar Bitácora de Auditoría para Registro de Rechazo**:
  - **Endpoint**: `GET /activos-biologicos/auditoria?id_activo_biologico=130&pagina=1&page_size=20`
  - **Resultado**: La API y la tabla `modulo2.bitacora_auditoria_m02` **no contienen ninguna entrada de auditoría** asociada a este intento de modificación rechazado.
- **Petición 3 - Consultar Activo Biológico (Verificación de Integridad)**:
  - **Endpoint**: `GET /activos-biologicos/130`
  - **Respuesta**: `HTTP 200 OK`. `biomasa_total = 290.00` (inmutable, no se modificó).
- **Aserciones Newman**:
  - `[PASS]` Checkpoint 0 - Autenticación exitosa (HTTP 200 OK)
  - `[PASS]` Código HTTP esperado: 400 Bad Request (Rechazo de edición directa)
  - `[PASS]` El error retornado es de validación de entrada (VAL_ENTRADA)
  - `[PASS]` Código HTTP esperado: 200 OK al consultar auditoría
  - `[FAIL]` Existe registro de auditoría para el intento fallido/rechazado (INC-M02-41-RF52): `DEFECTO INC-M02-41-RF52: El backend rechazó la petición con HTTP 400 pero no generó el registro de auditoría para la operación rechazada.`
  - `[PASS]` Código HTTP esperado: 200 OK al consultar activo
  - `[PASS]` La biomasa_total permanece inalterada (no es 999.99)
- **Veredicto**: **FAIL (DEFECTO DE TRAZABILIDAD INC-M02-41-RF52)**.

---

## 4. Verificación en Base de Datos PostgreSQL (`sgpmp_test`, Solo Lectura)

Se ejecutaron consultas SQL de solo lectura sobre `modulo2.bitacora_auditoria_m02`:

### Consulta 1: Evidencia de CRECIMIENTO (TC-M02-203)
```sql
SELECT id_bitacora, rf_origen, tipo_evento, clasificacion_biologica, resultado, id_usuario_responsable, timestamp_evento, descripcion
FROM modulo2.bitacora_auditoria_m02
WHERE id_activo_biologico = 130 
  AND rf_origen = 'RF40'
  AND timestamp_registro > NOW() - INTERVAL '30 minutes'
ORDER BY id_bitacora DESC
LIMIT 1;
```
**Resultado obtenido**:
```
id_bitacora:            295
rf_origen:              RF40
tipo_evento:            EVENTO_CRECIMIENTO_REGISTRADO
clasificacion_biologica: TRANSFORMACION_BIOLOGICA
resultado:              EXITOSO
id_usuario_responsable: 1
descripcion:            Evento de crecimiento: PESO = 58.0 gr
```

### Consulta 2: Evidencia de BAJA (TC-M02-204)
```sql
SELECT id_bitacora, rf_origen, tipo_evento, clasificacion_biologica, resultado, id_usuario_responsable, timestamp_evento, descripcion, detalle_tecnico
FROM modulo2.bitacora_auditoria_m02
WHERE id_activo_biologico = 130 
  AND rf_origen = 'RF45'
  AND timestamp_registro > NOW() - INTERVAL '30 minutes'
ORDER BY id_bitacora DESC
LIMIT 1;
```
**Resultado obtenido**:
```
id_bitacora:            297
rf_origen:              RF45
tipo_evento:            BAJA_REGISTRO_FALLIDO
resultado:              FALLIDO
id_usuario_responsable: 1
detalle_tecnico:        {"error": "Error inesperado en base de datos", "tipo_baja": "venta"}
```

### Consulta 3: Evidencia de Intento Rechazado (TC-M02-205)
```sql
SELECT id_bitacora, rf_origen, tipo_evento, clasificacion_biologica, resultado, id_usuario_responsable, timestamp_evento, detalle_tecnico
FROM modulo2.bitacora_auditoria_m02
WHERE id_activo_biologico = 130 
  AND rf_origen IN ('RF35', 'RF36') 
  AND resultado IN ('FALLIDO', 'RECHAZADO')
  AND timestamp_registro > NOW() - INTERVAL '30 minutes'
ORDER BY id_bitacora DESC
LIMIT 1;
```
**Resultado obtenido**:
```
(0 rows returned)
```
*Evidencia confirmada*: No existe ningún registro de auditoría en la base de datos para la operación rechazada con HTTP 400.

---

## 5. Fichas de Defectos Identificados

### 🐛 Defecto 1: INC-M02-42-DB-TRIGGER (Severidad Alta)
- **Componente**: PostgreSQL Database (`modulo2.trg_fn_baja_cantidad_valida`)
- **Descripción**: La función trigger `modulo2.trg_fn_baja_cantidad_valida()` evalúa la condición:
  ```sql
  IF v_tipo_activo = 'poblacional' THEN
  ```
  Sin embargo, el tipo enum `modulo2.enum_activo_biologico_tipo` tiene definidos los valores en mayúsculas: `'POBLACIONAL'` e `'INDIVIDUAL'`.
  Al ejecutarse cualquier inserción en `modulo2.eventos_bajas` para un lote poblacional, PostgreSQL aborta con error:
  `invalid input value for enum modulo2.enum_activo_biologico_tipo: "poblacional"`, bloqueando la funcionalidad de baja del lote (HTTP 500).
- **Corrección Propuesta (en migración SQL/Alembic)**:
  ```sql
  CREATE OR REPLACE FUNCTION modulo2.trg_fn_baja_cantidad_valida()
  RETURNS trigger AS $$
  ...
  IF v_tipo_activo = 'POBLACIONAL' THEN  -- Corregir a mayúsculas
  ...
  $$ LANGUAGE plpgsql;
  ```

---

### 🐛 Defecto 2: INC-M02-41-RF52 (Severidad Media)
- **Componente**: FastAPI / Middleware de Auditoría (`src/shared/error_handlers.py` / `AuditContextMiddleware`)
- **Descripción**: Cuando un usuario intenta enviar un payload inválido o con campos no permitidos (ej. `PATCH /activos-biologicos/130` con `{"biomasa_total": 999.99}`), FastAPI rechaza la solicitud en la capa Pydantic (`RequestValidationError` $\rightarrow$ `HTTP 400 Bad Request`).
  Debido a que el fallo se produce antes de ingresar al caso de uso (`ActualizarActivoIndividualUseCase`), la llamada nunca alcanza a `bitacora_repo.registrar()`, y el handler global de errores no emite eventos hacia `modulo2.bitacora_auditoria_m02`. Esto infringe el criterio de auditoría de operaciones rechazadas de los requisitos RF-36 y RF-52.
- **Corrección Propuesta**: Incorporar en el manejador `request_validation_error_handler` o en un middleware de auditoría el registro de intentos fallidos hacia la bitácora cuando la petición afecte un recurso de activo biológico autenticado.

---

## 6. Conclusión y Dictamen de Calidad

1. **TC-M02-203**: **PASS**. El flujo de auditoría zootécnica para eventos de crecimiento opera de forma óptima, registrando de forma inmutable el evento en `modulo2.bitacora_auditoria_m02` con todos los metadatos requeridos por RF-52.
2. **TC-M02-204**: **FAIL**. Se descubrió un defecto crítico a nivel de trigger de base de datos (`INC-M02-42-DB-TRIGGER`) que impide el registro de eventos de baja para lotes poblacionales.
3. **TC-M02-205**: **FAIL**. La regla de inmutabilidad y rechazo directo de `biomasa_total` funciona a nivel de contrato API (`HTTP 400 Bad Request` / `VAL_ENTRADA`), pero adolece de un defecto de trazabilidad (`INC-M02-41-RF52`) al no persistir el intento fallido en la bitácora de auditoría.
