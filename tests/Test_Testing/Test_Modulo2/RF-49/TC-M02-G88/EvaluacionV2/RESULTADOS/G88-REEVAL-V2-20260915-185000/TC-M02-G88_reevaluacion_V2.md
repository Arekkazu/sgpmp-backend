# Reevaluación V2 — Caso TC-M02-G88 — RF-49 CU11
## Verificación de Fixes (INC-M02-63-G88 y INC-M02-64-G88) con Ajuste Autorizado de Aserción (Opción B)

---

## 1. Encabezado y Metadatos de Ejecución

- **Título:** Reevaluación V2 — Caso Agrupado TC-M02-G88 — RF-49 CU11 (*Validaciones Ampliadas de Existencia y Exclusividad por Tipo de Asociación*)
- **RUN_ID:** `G88-REEVAL-V2-20260915-185000`
- **Fechas de Evaluación:**
  - **V1 (Original):** 2026-09-10
  - **V2 (Reevaluación actual):** 2026-09-15
- **Entorno de Pruebas:** **TEST** (`https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test`)
- **Base de Datos TEST:** PostgreSQL 16 (`158.69.200.27:5448/sgpmp_test`, usuario `member_qa`)
- **Herramientas de Automatización:** Newman CLI v6.2.2 + newman-reporter-htmlextra v1.23.1, Python 3.13.9, psycopg2
- **Colección Ejecutada:** `tests/Test_Testing/Test_Modulo2/RF-49/TC-M02-G88/test_tc_m02_g88.json` (con ajuste autorizado en la aserción de error_code en `TC-M02-214`)
- **Reporte HTML Generado:** [reporte_TC-M02-G88_v2.html](./reporte_TC-M02-G88_v2.html)
- **Veredicto Global V2:** **✅ CONFORME / PASS COMPLETO (3/3 SUBCASOS APROBADOS — 13/13 ASERCIONES CONFORMES)**

---

## 2. Objetivo de la Reevaluación y Resumen Ejecutivo

### 2.1 Contexto V1 y Defectos Abiertos
En la corrida original del caso **TC-M02-G88** (2026-09-10), el resultado global fue **NO CONFORME** con 2 defectos críticos registrados:
1. **INC-M02-63-G88 (Medio / Conformidad de API):** Al intentar asociar un sensor a un activo biológico inexistente (`POST /activos-biologicos/99999/sensores`), el backend respondía con `HTTP 404 Not Found` en lugar de `HTTP 422 Unprocessable Entity`, violando el contrato contractual estipulado en el Flujo Alterno E1 del RF-49 ("Activo Biológico No Válido").
2. **INC-M02-64-G88 (Severo / Integridad de Negocio):** El backend permitía asociar un mismo sensor de tipo `POBLACIONAL` a dos lotes distintos simultáneamente (creó la asociación activa 105 en Lote 20 y la asociación activa 106 en Lote 53 con `HTTP 201 Created`), violando taxativamente la Restricción 4 del RF-49 (*"Tipo POBLACIONAL: un sensor se asocia a un único lote activo a la vez"*).
3. **TC-M02-215:** Demostró la capacidad del sistema para soportar múltiples sensores de tipo `DIRECTA` en un mismo animal individual (`Activo 19`), resultando en `PASS`.

### 2.2 Fixes Aplicados en Backend y Desplegados en TEST
El equipo de desarrollo implementó las siguientes correcciones en la rama principal, ya integradas y desplegadas en el entorno TEST:
- **Commit `7da605cc` (PR #285):** Corrige `INC-M02-63-G88`. En la regla V1 de `AsociarSensorActivoUseCase`, reemplaza el lanzamiento de `NotFoundError` (404) por `BusinessRuleError` (422) con el código de error `ACTIVO_NO_ENCONTRADO`, alineando la inexistencia con el caso "BAJA" según el flujo alterno del RF-49.
- **Commit `2f9ed7c8`:** Corrige `INC-M02-64-G88`. Incorpora la regla **V8c** en `AsociarSensorActivoUseCase`, la cual consulta `listar_activas_por_sensor(dto.sensor_id, 'poblacional')` y rechaza cualquier solicitud concurrente para un lote distinto con `ConflictError(code='SENSOR_YA_ASOCIADO_A_OTRO_LOTE')` (HTTP 409 Conflict).

### 2.3 Decisión Estratégica: Opción B (Ajuste Autorizado de Aserción)
La aserción original de QA en `TC-M02-214` esperaba textualmente `jsonData.error_code === "SENSOR_YA_VINCULADO"` (el código genérico de colisión directa en V8). El backend implementó el código específico `SENSOR_YA_ASOCIADO_A_OTRO_LOTE` para distinguir claramente la colisión poblacional (V8c) de la directa (V8). Bajo autorización expresa de QA Lead (Opción B), se modificó la aserción de la colección para aceptar ambos códigos:
`pm.expect(jsonData.error_code).to.be.oneOf(["SENSOR_YA_VINCULADO", "SENSOR_YA_ASOCIADO_A_OTRO_LOTE"]);`
El código HTTP 409 y la regla de negocio de exclusividad se validan de manera irrefutable.

### 2.4 Tabla Comparativa de Resultados
| Sub-caso | Enfoque / Regla Evaluada | Comportamiento Esperado | Obtenido V2 | Aserciones | Veredicto V2 |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **TC-M02-213** | Activo inexistente (`id=99999`) | `HTTP 422` + `ACTIVO_NO_ENCONTRADO` | `HTTP 422` + `ACTIVO_NO_ENCONTRADO` | 2/2 | ✅ **PASS** |
| **TC-M02-214** | Exclusividad POBLACIONAL (Sensor 1 en Lote 20 y Lote 53) | `HTTP 409` + Código exclusividad (V8/V8c) | `HTTP 409` + `SENSOR_YA_ASOCIADO_A_OTRO_LOTE` | 4/4 | ✅ **PASS** |
| **TC-M02-215** | Múltiples sensores DIRECTA en Activo 19 (Sensores 2 y 3) | `HTTP 201` + `ACTIVA` en ambos | `HTTP 201` + `ACTIVA` (x2) | 4/4 | ✅ **PASS** |
| **TOTAL** | **Suite TC-M02-G88 Consolidada** | **3 Subcasos Aprobados** | **8 Requests / 0 Fallos** | **13/13** | ✅ **PASS COMPLETO** |

---

## 3. Estado Previo de la Base de Datos (Pre-condición vía API REST)

Se ejecutó la verificación previa de precondiciones y del estado de la base de datos TEST, cuyos resultados quedaron consignados en `precondicion_api.log`:

```text
=== PRECONDICIONES REGISTRADAS EN precondicion_api.log ===
Target baseUrl: https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test
1. Login Admin: POST /sesiones/ -> HTTP 200 (Token JWT emitido).
2. GET /activos-biologicos/19 -> HTTP 200 (ID=19, Tipo=INDIVIDUAL, Estado=ACTIVO, Infra=1)
   GET /activos-biologicos/20 -> HTTP 200 (ID=20, Tipo=POBLACIONAL, Estado=ACTIVO, Infra=1)
   GET /activos-biologicos/53 -> HTTP 200 (ID=53, Tipo=POBLACIONAL, Estado=ACTIVO, Infra=1)
3. GET /activos-biologicos/99999 -> HTTP 404 (Confirmación de inexistencia para subcaso 213).
4. GET /configuracion/dispositivos-iot/{1, 2, 3} -> HTTP 200 en todos los dispositivos.
5. Sensor 1: Asociaciones POBLACIONALES ACTIVAS en BD = 0 (Esperado: 0).
6. Activos 19, 20, 53: Total asociaciones ACTIVAS en BD = 0 (Esperado: 0).
7. Verificación de fixtures residuales V1:
   - Asoc 12 (Activo 20, Sensor 1): Estado=INACTIVA, Motivo='Cleanup tecnico de pruebas TC-M02-G88'
   - Asoc 13 (Activo 53, Sensor 1): Estado=INACTIVA, Motivo='Cleanup tecnico de pruebas TC-M02-G88'
```
> **Conclusión de Precondición:** Los activos biológicos 19, 20 y 53 se encuentran activos y sin colisiones de telemetría previa. El sensor 1 no cuenta con ninguna vinculación poblacional activa. La base de datos TEST se encontraba en estado base limpio antes de iniciar la corrida.

---

## 4. Resultados Detallados de la Ejecución (Newman)

### 4.1 Métricas Globales de Ejecución
- **Iteraciones:** 1 ejecutada / 0 fallidas
- **Solicitudes HTTP Totales:** 8 ejecutadas / 0 fallidas
- **Scripts de Prueba:** 8 ejecutados / 0 fallidos
- **Aserciones Evaluadas:** 13 evaluadas / 13 exitosas / 0 fallidas (100% de éxito)
- **Tiempo Promedio de Respuesta:** 429 ms
- **Duración Total de Suite:** 4.0 segundos
- **Exit Code Newman:** `0`

### 4.2 Tabla Detallada Paso a Paso por Subcaso

| Subcaso | Paso | Método y Endpoint | HTTP Esperado | HTTP Obtenido | Tiempo | Aserciones | Estado |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **TC-M02-213** | 00 | `POST /sesiones/` (Login Admin) | 200 | 200 OK | 1148 ms | 1/1 | ✅ PASS |
| **TC-M02-213** | 01 | `POST /activos-biologicos/99999/sensores` | 422 | 422 Unproc. Entity | 223 ms | 2/2 | ✅ PASS |
| **TC-M02-214** | 00 | `POST /sesiones/` (Login Admin) | 200 | 200 OK | 370 ms | 1/1 | ✅ PASS |
| **TC-M02-214** | 01 | `POST /activos-biologicos/20/sensores` (Setup) | 201 | 201 Created | 189 ms | 2/2 | ✅ PASS |
| **TC-M02-214** | 02 | `POST /activos-biologicos/53/sensores` (Duplicado) | 409 | 409 Conflict | 222 ms | 2/2 | ✅ PASS |
| **TC-M02-215** | 00 | `POST /sesiones/` (Login Admin) | 200 | 200 OK | 425 ms | 1/1 | ✅ PASS |
| **TC-M02-215** | 01 | `POST /activos-biologicos/19/sensores` (Sensor 2) | 201 | 201 Created | 251 ms | 2/2 | ✅ PASS |
| **TC-M02-215** | 02 | `POST /activos-biologicos/19/sensores` (Sensor 3) | 201 | 201 Created | 607 ms | 2/2 | ✅ PASS |

---

### 4.3 Evidencia Textual de Respuestas Clave

#### Evidencia TC-M02-213: Activo Inexistente
- **Solicitud:** `POST /activos-biologicos/99999/sensores`
- **Código Obtenido:** `HTTP 422 Unprocessable Entity`
- **Cuerpo JSON:**
  ```json
  {
    "error_code": "ACTIVO_NO_ENCONTRADO",
    "message": "No existe un activo biológico con id 99999.",
    "fields": [],
    "timestamp": "2026-09-15T23:50:02.155792+00:00"
  }
  ```

#### Evidencia TC-M02-214: Exclusividad Poblacional Rechaza Duplicidad
- **Solicitud Paso 02:** `POST /activos-biologicos/53/sensores` (intentando asociar el Sensor 1 que ya estaba activo en Lote 20)
- **Código Obtenido:** `HTTP 409 Conflict`
- **Cuerpo JSON:**
  ```json
  {
    "error_code": "SENSOR_YA_ASOCIADO_A_OTRO_LOTE",
    "message": "El sensor 1 ya está asociado con tipo POBLACIONAL al activo 20. Un sensor solo puede estar activo en un único lote a la vez. Desactive esa asociación primero.",
    "fields": [],
    "timestamp": "2026-09-15T23:50:03.882415+00:00"
  }
  ```

#### Evidencia TC-M02-215: Soporte Multi-Sensor DIRECTA
- **Solicitud Paso 01 (Sensor 2):** `HTTP 201 Created`
  ```json
  {
    "id_asociacion_activo_sensor": 36,
    "id_activo_biologico": 19,
    "tipo_activo": "INDIVIDUAL",
    "tipo_asociacion": "DIRECTA",
    "sensor_id": 2,
    "estado_asociacion": "ACTIVA"
  }
  ```
- **Solicitud Paso 02 (Sensor 3 en el mismo Activo 19):** `HTTP 201 Created`
  ```json
  {
    "id_asociacion_activo_sensor": 37,
    "id_activo_biologico": 19,
    "tipo_activo": "INDIVIDUAL",
    "tipo_asociacion": "DIRECTA",
    "sensor_id": 3,
    "estado_asociacion": "ACTIVA"
  }
  ```

---

### 4.4 Diff Textual del Ajuste Autorizado en la Colección Newman
En cumplimiento de la **Opción B** autorizada expresamente por el QA Lead, se modificó única y exclusivamente el bloque de aserción en `TC-M02-214` (Líneas 204-207 de `test_tc_m02_g88.json`):

```diff
-                  "pm.test(\"Código de error es SENSOR_YA_VINCULADO\", function () {",
-                  "    var jsonData = pm.response.json();",
-                  "    pm.expect(jsonData.error_code).to.eql(\"SENSOR_YA_VINCULADO\");",
-                  "});"
+                  "pm.test(\"Código de error corresponde a exclusividad POBLACIONAL (V8 o V8c)\", function () {",
+                  "    var jsonData = pm.response.json();",
+                  "    pm.expect(jsonData.error_code).to.be.oneOf([",
+                  "        \"SENSOR_YA_VINCULADO\",",
+                  "        \"SENSOR_YA_ASOCIADO_A_OTRO_LOTE\"",
+                  "    ]);",
+                  "});"
```
*Justificación del cambio:* El requerimiento RF-49 Restricción 4 y Flujo Alterno E3 estipulan que el rechazo debe ser `HTTP 409 Conflict`. El backend diferenció a nivel de capa de aplicación el error de colisión directa (`SENSOR_YA_VINCULADO`) del error de colisión poblacional (`SENSOR_YA_ASOCIADO_A_OTRO_LOTE`). Aceptar ambos códigos garantiza la total observabilidad y apego a la regla de negocio.

---

## 5. Evidencia Post-condición y Diagnóstico Técnico

### 5.1 Trazabilidad de Código Fuente
1. **Regla V1 (Activo Inexistente):**  
   Ubicación: `src/biological_assets/application/use_cases/gestion/asociar_sensor_activo_use_case.py` (líneas 52-63):
   ```python
   activo = self.activo_repo.obtener_por_id(id_activo)
   if activo is None:
       raise BusinessRuleError(
           code='ACTIVO_NO_ENCONTRADO',
           message=f'No existe un activo biológico con id {id_activo}.',
       )
   ```
   En `src/shared/errors.py`, `BusinessRuleError` tiene definido `status_code = 422`. Esto resuelve formalmente el defecto `INC-M02-63-G88`.

2. **Regla V8c (Exclusividad POBLACIONAL Simétrica):**  
   Ubicación: `src/biological_assets/application/use_cases/gestion/asociar_sensor_activo_use_case.py` (líneas 185-202):
   ```python
   activas_sensor_pob = self.repo.listar_activas_por_sensor(dto.sensor_id, 'poblacional')
   conflicto_sensor = next(
       (a for a in activas_sensor_pob if a.id_activo_biologico != id_activo),
       None,
   )
   if conflicto_sensor:
       raise ConflictError(
           code='SENSOR_YA_ASOCIADO_A_OTRO_LOTE',
           message=(
               f'El sensor {dto.sensor_id} ya está asociado con tipo POBLACIONAL '
               f'al activo {conflicto_sensor.id_activo_biologico}. Un sensor solo puede '
               'estar activo en un único lote a la vez. Desactive esa asociación primero.'
           ),
       )
   ```
   En `src/shared/errors.py`, `ConflictError` tiene definido `status_code = 409`. Esto resuelve formalmente el defecto `INC-M02-64-G88`.

---

## 6. Verificación de Limpieza (Cleanup e Inocuidad)

De acuerdo con la Restricción 8 del RF-49 (*"El historial de asociaciones es append-only. No se permite modificar ni eliminar registros históricos; solo añadir nuevas entradas o cambiar el estado de las existentes"*), se ejecutó la limpieza estricta mediante actualización de estado sin borrado físico:

### 6.1 Asociaciones Creadas en la Corrida
- Asociación ID `35`: Sensor 1 vinculado a Lote 20 (`POBLACIONAL`).
- Asociación ID `36`: Sensor 2 vinculado a Activo 19 (`DIRECTA`).
- Asociación ID `37`: Sensor 3 vinculado a Activo 19 (`DIRECTA`).

### 6.2 Sentencia Append-Only Ejecutada
```sql
UPDATE modulo2.asociaciones_activos_sensores
SET estado_asociacion = 'INACTIVA',
    fecha_fin = NOW(),
    motivo = 'Cleanup reevaluacion V2 TC-M02-G88'
WHERE (
    (id_sensor = 1 AND id_activo_biologico = 20)
    OR (id_sensor IN (2, 3) AND id_activo_biologico = 19)
)
  AND estado_asociacion = 'ACTIVA'
  AND fecha_fin IS NULL;
```
- **Resultado textual de ejecución:** `UPDATE 3` (3 filas actualizadas a `INACTIVA`).

### 6.3 Verificación de Cero Residuos
```sql
SELECT COUNT(*) AS asociaciones_activas_remanentes
FROM modulo2.asociaciones_activos_sensores
WHERE estado_asociacion = 'ACTIVA'
  AND fecha_fin IS NULL
  AND (
      (id_sensor = 1 AND id_activo_biologico = 20)
      OR (id_sensor IN (2, 3) AND id_activo_biologico = 19)
  );
```
- **Conteo obtenido:** `0`. Base de datos TEST restaurada a su estado limpio.

### 6.4 Inmutabilidad de Bitácoras de Auditoría
- Conteo total en `modulo2.bitacora_auditoria_m02`: `2065` registros.
- Se verificó la inserción append-only de los eventos `ASOCIACION_IOT_CREADA` con sus respectivos hashes SHA-256 de integridad:
  - Evento `2065`: Hash `6035a842e9c7b87e...`
  - Evento `2064`: Hash `cd6c637c3b531594...`
  - Evento `2063`: Hash `caf98143bfefdbde...`
- Cero registros de auditoría fueron modificados o eliminados.

---

## 7. Conclusiones, Diagnóstico Técnico y Dictamen Final

### 7.1 Estado de Defectos Previamente Registrados

1. **INC-M02-63-G88: ✅ RESUELTO Y VERIFICADO**  
   El backend responde rigurosamente `HTTP 422 Unprocessable Entity` ante solicitudes con IDs de activos inexistentes, satisfaciendo el contrato del Flujo Alterno E1 del RF-49.
2. **INC-M02-64-G88: ✅ RESUELTO Y VERIFICADO**  
   La regla V8c impide exitosamente que un sensor configurado para monitoreo poblacional sea asignado concurrentemente a dos lotes distintos, respondiendo `HTTP 409 Conflict` conforme a la Restricción 4 del RF-49.

### 7.2 Registro del Ajuste Autorizado de la Colección (Transparencia QA)
- **Alcance:** Modificación exclusiva de la aserción de `error_code` en `TC-M02-214` dentro de `test_tc_m02_g88.json`.
- **Justificación Técnica:** El backend emite `SENSOR_YA_ASOCIADO_A_OTRO_LOTE` como una especialización semántica de `SENSOR_YA_VINCULADO`. Mantener la aserción rígida a un solo string habría ocultado el cumplimiento del código HTTP 409 y la protección de datos entre lotes.
- **Aprobación:** Opción B formalmente autorizada por QA Lead.

### 7.3 Hallazgos Secundarios No Bloqueantes
- **Deuda Técnica en Colección:** Los identificadores de activos y sensores están hardcodeados en el JSON de la colección. Se recomienda parametrizarlos mediante variables de entorno para futuras iteraciones.
- **Catálogo de Errores M02:** Se sugiere actualizar la documentación formal de API para reflejar la coexistencia de `SENSOR_YA_VINCULADO` (DIRECTA) y `SENSOR_YA_ASOCIADO_A_OTRO_LOTE` (POBLACIONAL).

### 7.4 Dictamen Final
> **DICTAMEN DE QA:** **APROBADO / CONFORME (PASS COMPLETO)**  
> La suite de pruebas **TC-M02-G88** supera el 100% de las aserciones (13/13) en el entorno **TEST**, validando tanto la robustez de las reglas de cardinalidad y existencia como la integridad de los datos de telemetría IoT. Se autoriza el cierre definitivo de los incidentes **INC-M02-63-G88** y **INC-M02-64-G88**.
