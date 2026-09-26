# INFORME CONSOLIDADO DE EJECUCIÓN DE PRUEBAS DE BACKEND
## Caso de Prueba Agrupado: TC-M02-G91
**Módulo 2: Activos Biológicos | Requerimiento: RF-49 (Asociación de Sensores IoT a Activos Biológicos)**
**Caso de Uso: CU11 | Prioridad: Media | Entorno: TEST**
**Fecha de Ejecución:** 2026-09-10 | **Ejecutor:** Ingeniero de Pruebas QA Backend

---

## 1. RESUMEN EJECUTIVO Y TABLA DE VEREDICTOS

Se ejecutó la suite automatizada del caso agrupado **TC-M02-G91** (*"Integridad del historial y trazabilidad post-creación de la asociación"*), orientada a validar la inmutabilidad física del historial (Restricción 8 append-only) y la visibilidad de las asociaciones entre sensores IoT y activos biológicos en consultas posteriores.

El estado global del caso agrupado es **NO CONFORME** (1 PASS CON OBSERVACIÓN / 1 FAIL). Se identificó un defecto de severidad **SEVERA** (`INC-M02-G91-01`) por ausencia de implementación del endpoint `GET` para consultar sensores vinculados a activos biológicos.

### Tabla de Veredictos

| Subcaso ID | ID Trazabilidad | Nombre del Subcaso | Tipo | Endpoint Objetivo | Verbo | HTTP Obtenido | Veredicto | Defecto / Observación |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **TC-M02-222** | TC-M02-163-A | Rechazar eliminación (DELETE) de una asociación existente | Validación | `/activos-biologicos/19/sensores/17`<br>`/activos-biologicos/19/sensores` | `DELETE` | `404 Not Found`<br>`405 Method Not Allowed` | **PASS CON OBSERVACIÓN** | `OBS-M02-G91-01` |
| **TC-M02-223** | TC-M02-164-A | Verificar visibilidad de la asociación creada en consultas posteriores | Funcional (+) | `/activos-biologicos/19/sensores` | `POST`<br>`GET` | `201 Created`<br>`405 Method Not Allowed` | **FAIL** | `INC-M02-G91-01` |

**Resultado Global:** **NO CONFORME** (50% Conforme con Observación, 50% No Conforme).

---

## 2. MÉTRICAS DE EJECUCIÓN

| Métrica | Subcaso TC-M02-222 | Subcaso TC-M02-223 | Total Consolidado |
| :--- | :--- | :--- | :--- |
| **Iteraciones** | 1 | 1 | 2 |
| **Peticiones HTTP Ejecutadas** | 3 | 3 | 6 |
| **Aserciones Evaluadas** | 5 | 6 | 11 |
| **Aserciones Exitosas** | 5 (100%) | 4 (66.7%) | 9 (81.8%) |
| **Aserciones Fallidas** | 0 (0%) | 2 (33.3%) | 2 (18.2%) |
| **Tiempo de Ejecución Newman** | 1,612 ms | 1,827 ms | 3,439 ms |
| **Tiempo Promedio Respuesta** | 455 ms | 518 ms | 486 ms |
| **Reporte HTML Generado** | `reporte_TC-M02-222.html` (82,628 bytes) | `reporte_TC-M02-223.html` (92,260 bytes) | 2 reportes HTML |

---

## 3. DETALLE TÉCNICO POR SUBCASO

### 3.1. Subcaso TC-M02-222 (TC-M02-163-A) — Rechazar eliminación (DELETE) de una asociación existente

- **Objetivo:** Enviar `DELETE` sobre una asociación existente y verificar que el sistema rechaza la operación, preservando el registro histórico intacto conforme a la Restricción 8 (Inmutabilidad del Historial Append-Only) y Restricción 5 del RF-49.
- **Fixture Evaluado:** Asociación ID `17` (`id_activo_biologico = 19`, `id_sensor = 2`, `tipo = 'directa'`, `estado_asociacion = 'INACTIVA'`).
- **Flujo Ejecutado:**
  1. `POST /sesiones/` → Autenticación como `admin@pecuaria.co` (`HTTP 200 OK`).
  2. `DELETE /activos-biologicos/19/sensores/17` con Bearer token.
     - **Respuesta:** `HTTP 404 Not Found` (`{"detail": "Not Found"}`).
     - **Aserción:** `pm.expect([404, 405]).to.include(pm.response.code)` → **Aprobada**.
     - **Aserción:** Respuesta no es 200 ni 204 (sin borrado físico) → **Aprobada**.
  3. `DELETE /activos-biologicos/19/sensores` (Ruta base sin ID) con Bearer token.
     - **Respuesta:** `HTTP 405 Method Not Allowed` (`{"detail": "Method Not Allowed"}`).
     - **Aserción:** `pm.response.code === 405` → **Aprobada**.
- **Verificación SQL Post-Ejecución:**
  ```sql
  SELECT id_asociacion_activo_sensor, id_activo_biologico, id_sensor, estado_asociacion, fecha_inicio, fecha_fin
  FROM modulo2.asociaciones_activos_sensores WHERE id_asociacion_activo_sensor = 17;
  ```
  - **Resultado:** La fila `17` permanece 100% inalterada (`id_activo_biologico = 19`, `id_sensor = 2`, `estado_asociacion = 'INACTIVA'`, `fecha_inicio = 2026-09-10 09:13:35`, `fecha_fin = 2026-09-10 09:22:27`).
- **Veredicto:** **PASS CON OBSERVACIÓN** (`OBS-M02-G91-01`).
- **Análisis de Observación 3 del QA:** El rechazo del borrado aplica de forma homogénea tanto para asociaciones ACTIVAS como INACTIVAS debido a que el backend no expone la ruta ni el método DELETE en su arquitectura de controladores, respetando el principio append-only a nivel de contrato HTTP.

---

### 3.2. Subcaso TC-M02-223 (TC-M02-164-A) — Verificar visibilidad de la asociación creada en consultas posteriores

- **Objetivo:** Crear una asociación válida vía API y consultar posteriormente los sensores del activo biológico para constatar que la asociación aparece reflejada con sus atributos completos según el criterio de aceptación del RF-49: *"El sistema refleja la asociación en consultas posteriores"*.
- **Fixtures Evaluados:** Activo `19` (INDIVIDUAL, libre de asociaciones vigentes) y Sensor `2` (DIRECTA, libre de asociaciones vigentes).
- **Flujo Ejecutado:**
  1. `POST /sesiones/` → Autenticación como `admin@pecuaria.co` (`HTTP 200 OK`).
  2. `POST /activos-biologicos/19/sensores` con payload:
     ```json
     {
       "tipo_activo": "INDIVIDUAL",
       "tipo_asociacion": "DIRECTA",
       "dispositivo_iot_id": 1,
       "sensor_id": 2,
       "id_infraestructura": 1,
       "motivo": "Verificacion funcional visibilidad post-creacion TC-M02-223"
     }
     ```
     - **Respuesta:** `HTTP 201 Created` (`id_asociacion_activo_sensor: 26`, `estado_asociacion: "ACTIVA"`, `sensor_id: 2`).
     - **Aserciones:** Código 201 y atributos de asociación presentes → **Aprobadas**.
  3. `GET /activos-biologicos/19/sensores` con Bearer token.
     - **Respuesta:** `HTTP 405 Method Not Allowed` (`{"detail": "Method Not Allowed"}`).
     - **Aserción 1:** `pm.response.to.have.status(200)` → **FALLIDA** (esperaba 200, obtuvo 405).
     - **Aserción 2:** Cuerpo es un array y contiene el sensor asociado → **FALLIDA** (obtuvo objeto `detail: Method Not Allowed`).
- **Verificación SQL Post-Ejecución:**
  ```sql
  SELECT id_asociacion_activo_sensor, id_activo_biologico, id_sensor, tipo, estado_asociacion, fecha_inicio, fecha_fin, motivo
  FROM modulo2.asociaciones_activos_sensores
  WHERE id_activo_biologico=19 AND id_sensor=2 AND estado_asociacion='ACTIVA';
  ```
  - **Resultado en BD:** 1 fila activa generada con éxito (ID `26`, `tipo = 'directa'`, `estado_asociacion = 'ACTIVA'`, `fecha_fin = NULL`).
- **Veredicto:** **FAIL** (Defecto `INC-M02-G91-01`).
- **Causa Raíz:** La asociación se persiste correctamente a nivel de base de datos, pero la API carece por completo de un endpoint de consulta para recuperar los sensores vinculados a un activo biológico.

---

## 4. REGISTRO FORMAL DE DEFECTOS Y OBSERVACIONES

### Defecto INC-M02-G91-01

- **ID:** `INC-M02-G91-01`
- **Título:** El backend no expone ningún endpoint para consultar las asociaciones sensor↔activo.
- **Subcaso de Origen:** TC-M02-223 (TC-M02-164-A).
- **Categoría:** HTTP_COM / Funcionalidad No Implementada.
- **Severidad:** **SEVERO**.
- **Prioridad:** **ALTA**.
- **Equipo Responsable:** Desarrollo Backend.
- **Tiempo Máximo de Solución:** 1 día hábil.
- **Impacto:** Un usuario o cliente del frontend no tiene forma de consultar qué sensores se encuentran asociados a un activo biológico a través de la API REST. Aunque la asociación física existe en `modulo2.asociaciones_activos_sensores`, los datos son completamente invisibles para los consumidores externos, violando directamente el criterio de aceptación del RF-49: *"El sistema refleja la asociación en consultas posteriores"*.
- **Evidencia Técnica:**
  - Petición: `GET /activos-biologicos/19/sensores` → Servidor responde `HTTP 405 Method Not Allowed`.
  - En `activo_biologico_router.py` (L1114-1155) únicamente está definido `@router.post('/{id_activo}/sensores')`. No existe `@router.get` registrado.
  - Los esquemas de consulta general (`DetalleIndividualResponse`, `FichaIntegralResponse` y `PaginaHistorial`) no contienen propiedades ni relaciones para exponer sensores.
- **Criterio de Cierre:** Implementar el endpoint `GET /activos-biologicos/{id_activo}/sensores` (con autenticación, RBAC y paginación/filtros) o incorporar la lista de sensores activos dentro de `GET /activos-biologicos/{id}/ficha-integral`, seguido de un retest exitoso.

### Observación OBS-M02-G91-01

- **ID:** `OBS-M02-G91-01`
- **Título:** El rechazo a la eliminación (DELETE) se produce por ruta no encontrada (404) o método no implementado (405) sin mensaje funcional explícito.
- **Subcaso de Origen:** TC-M02-222 (TC-M02-163-A).
- **Severidad:** **BAJA** (Calidad de Contrato de API).
- **Detalle:** Si bien el backend cumple efectivamente con la Restricción 8 de inmutabilidad física al no permitir el borrado de filas, la API rechaza con `404 Not Found` en rutas con ID o `405 Method Not Allowed` en ruta base. Sería una buena práctica arquitectónica disponer de un endpoint formal que retorne `405` o `400/409` con un código de error de negocio explícito (ej. `OPERACION_NO_PERMITIDA_HISTORIAL_INMUTABLE`).

---

## 5. BLOQUEOS EXTERNOS

- **Bloqueos Externos:** **Ninguno**. El entorno de TEST (backend FastAPI y PostgreSQL 16) respondió con normalidad y estabilidad técnica durante todas las fases de preflight, ejecución de suites y verificación.

---

## 6. CONFIRMACIÓN DE LIMPIEZA DE BASE DE DATOS

En cumplimiento estricto del RF-49 Restricción 8 (Historial Append-Only), no se utilizaron sentencias `DELETE`. Se aplicó la **Estrategia A (Cierre Lógico Append-Only con UPDATE de estado)** mediante el script `cleanup_tc_m02_g91.sql`:

### 6.1. Cleanup Intermedio en Preflight (Observación 1)
- Asociación de prueba exploratoria (ID `25`) desactivada:
  ```sql
  UPDATE modulo2.asociaciones_activos_sensores
  SET estado_asociacion='INACTIVA', fecha_fin = NOW(),
      motivo='Cleanup intermedio preflight TC-M02-G91'
  WHERE id_activo_biologico=19 AND id_sensor=2
    AND estado_asociacion='ACTIVA' AND fecha_fin IS NULL;
  ```
  - Filas afectadas: `1`. Remanentes: `0`.

### 6.2. Cleanup Final Post-Ejecución
- Asociación creada en TC-M02-223 (ID `26`) desactivada limpiamente mediante `cleanup_tc_m02_g91.sql`:
  - Filas actualizadas: `1`.
  - Motivo asignado: `'Cleanup tecnico de pruebas TC-M02-G91'`.
  - Fecha de finalización establecida respetando la coherencia temporal.

### 6.3. Verificación SQL Final:
```sql
SELECT COUNT(*) AS asociaciones_activas_remanentes
FROM modulo2.asociaciones_activos_sensores
WHERE id_activo_biologico = 19 AND id_sensor = 2
  AND estado_asociacion = 'ACTIVA' AND fecha_fin IS NULL;
```
- **Resultado:** `0`.
- **Conclusión:** La base de datos de TEST quedó limpia de asociaciones activas vigentes sobre los fixtures de prueba.

---

## 7. CRITERIOS DE CIERRE

El caso agrupado **TC-M02-G91** se declara **NO CONFORME**.

Para dar el caso por cerrado satisfactoriamente se requiere:
1. **Resolución del defecto INC-M02-G91-01:** Implementación por parte del equipo de desarrollo del endpoint `GET /activos-biologicos/{id_activo}/sensores` que liste las asociaciones del activo con su detalle (`sensor_id`, `tipo`, `fecha_inicio`, `estado_asociacion`).
2. **Ejecución y aprobación del retest automatizado del defecto:**
   - Ejecución de `retest_tc_m02_223.ps1` con exit code `0` (100% de aserciones aprobadas).
3. **Verificación de no regresión del rechazo al DELETE:**
   - Ejecución de `retest_tc_m02_222.ps1` con exit code `0` confirmando que la inmutabilidad física e imposibilidad de borrado se mantienen intactas.

---

## 8. INSTRUCCIONES DE RE-EJECUCIÓN (SCRIPTS DE RETEST)

Los scripts de retest permiten verificar cada subcaso de forma independiente:

1. **Retest Subcaso TC-M02-222 (Rechazar DELETE):**
   ```powershell
   .\tests\Test_Testing\Test_Modulo2\RF-49\TC-M02-G91\retest_tc_m02_222.ps1
   ```
2. **Retest Subcaso TC-M02-223 (Visibilidad de asociación):**
   ```powershell
   .\tests\Test_Testing\Test_Modulo2\RF-49\TC-M02-G91\retest_tc_m02_223.ps1
   ```
3. **Limpieza manual de BD (en caso de requerirse):**
   ```bash
   psql -h 158.69.200.27 -p 5448 -U member_qa -d sgpmp_test -f tests/Test_Testing/Test_Modulo2/RF-49/TC-M02-G91/RESULTADOS/cleanup_tc_m02_g91.sql
   ```
