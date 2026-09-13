# Informe de Ejecución Consolidado: TC-M02-G88

**Módulo:** Módulo 2 — Activos Biológicos  
**Requerimiento:** RF-49 — Asociación de sensores IoT a activos biológicos (CU11)  
**Caso de Prueba Agrupado:** TC-M02-G88 (Validaciones Ampliadas de Existencia y Exclusividad por Tipo de Asociación)  
**Entorno de Pruebas:** TEST (`https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test`)  
**Base de Datos TEST:** PostgreSQL (`sgpmp_test` @ `158.69.200.27:5448`)  
**Fecha y Hora de Ejecución:** 2026-09-10T03:21:00-05:00  
**Herramienta de Automatización:** Newman v6.2.1 + newman-reporter-htmlextra  
**Estrategia de Integridad de Datos:** Estrategia A (Append-only conforme a RF-49 Restricción 8; UPDATE de estado sin borrado físico ni de auditorías, ejecutado bajo autorización QA)  

---

## 1. Resumen Ejecutivo

Se ejecutó la suite de pruebas agrupada **TC-M02-G88**, diseñada para validar las reglas de negocio críticas del RF-49 relativas a la validación de existencia de activos biológicos (CU11 Flujo Alterno), la regla de exclusividad de sensores con asociación de tipo `POBLACIONAL` (Restricción 4) y la capacidad de admitir múltiples sensores con asociación de tipo `DIRECTA` en un mismo activo individual (Restricción 3).

El resultado global del caso agrupado es **NO CONFORME / PASS PARCIAL CON 2 DEFECTOS DOCUMENTADOS**, dado que el sistema permite la concurrencia indebida de un mismo sensor poblacional en múltiples lotes (incumplimiento crítico de regla de negocio) y retorna el código de estado REST genérico HTTP 404 en lugar del código especificado textualmente por el requerimiento (HTTP 422).

### Tabla Resumen de Veredictos

| Subcaso | Nombre del Escenario | Estado Esperado (RF-49) | Código HTTP Real | Veredicto | Defecto / Observación Asociada |
| :--- | :--- | :---: | :---: | :---: | :--- |
| **TC-M02-213** | Asociación con Activo Biológico Inexistente (`id_activo=99999`) | HTTP 422 (Unprocessable Entity) | **404 Not Found** | **FAIL** | **INC-M02-G88-01**: Retorna 404 en vez de 422 exigido por el RF. |
| **TC-M02-214** | Exclusividad de Sensor `POBLACIONAL` entre Lotes (Sensor 1 en Lotes 20 y 53) | HTTP 409 (Conflict) | **201 Created** | **FAIL** | **INC-M02-G88-02**: Permite duplicidad de sensor poblacional activo en 2 lotes simultáneos. |
| **TC-M02-215** | Múltiples Sensores de Tipo `DIRECTA` en un Mismo Activo (Sensores 2 y 3 en Activo 19) | HTTP 201 (Created) en ambos | **201 Created** | **PASS** | Cumple Restricción 3 (soporte multi-sensor directo sin conflicto). |
| **GLOBAL** | **Caso Agrupado TC-M02-G88** | **3 PASS** | **1 PASS / 2 FAIL** | **NO CONFORME** | 2 defectos identificados (1 crítico de integridad de negocio, 1 moderado de conformidad de API). |

---

## 2. Métricas de Ejecución

| Subcaso | Solicitudes HTTP | Aserciones Totales | Aserciones Exitosas | Aserciones Fallidas | Tiempo de Respuesta Promedio | Duración Total Suite |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **TC-M02-213** | 2 (1 Auth, 1 Test) | 2 | 1 | 1 | 772 ms | 2.1 s |
| **TC-M02-214** | 3 (1 Auth, 2 Test) | 4 | 3 | 1 | 704 ms | 2.3 s |
| **TC-M02-215** | 3 (1 Auth, 2 Test) | 5 | 5 | 0 | 700 ms | 2.3 s |
| **TOTALES** | **8** | **11** | **9** | **2** | **725 ms** | **6.7 s** |

---

## 3. Detalle Técnico por Subcaso

### 3.1. TC-M02-213: Rechazo ante Activo Inexistente

* **Objetivo:** Verificar que el endpoint rechaza la asociación si el activo biológico no existe en la base de datos, retornando HTTP 422 de acuerdo con el Flujo Alterno del CU11 ("Activo Biológico No Válido").
* **Pre-condición:** Activo biológico con ID `99999` inexistente en el sistema.
* **Petición HTTP:**
  * **Método y URL:** `POST https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test/activos-biologicos/99999/sensores`
  * **Headers:** `Authorization: Bearer <JWT_ADMIN>`, `Content-Type: application/json`
  * **Payload Aprobado y Ejecutado:**
    ```json
    {
      "tipo_activo": "INDIVIDUAL",
      "tipo_asociacion": "DIRECTA",
      "dispositivo_iot_id": 1,
      "sensor_id": 1,
      "id_infraestructura": 1
    }
    ```
* **Respuesta Obtenida:**
  * **Código de Estado:** `HTTP 404 Not Found` (Duración: 347 ms)
  * **Cuerpo de Respuesta:**
    ```json
    {
      "error_code": "ACTIVO_NO_ENCONTRADO",
      "message": "No existe un activo biológico con id 99999."
    }
    ```
* **Análisis del Fallo:**
  El requerimiento funcional RF-49 establece en su sección de *Flujos Alternos*:
  > *"Activo Biológico No Válido (Inexistente o Baja) — Condición: El ID no existe o el campo estado es 'BAJA'. Respuesta del Sistema: HTTP 422 Unprocessable Entity"*.  
  El backend implementa un manejo estándar REST (`HTTP 404 Not Found` generado por `NotFoundError` en capa de aplicación), lo que genera una no conformidad frente a la especificación contractual del requerimiento. Se registra el defecto formal **INC-M02-G88-01**.

---

### 3.2. TC-M02-214: Exclusividad de Sensor POBLACIONAL

* **Objetivo:** Validar que un sensor configurado para monitoreo poblacional solo pueda estar asociado activamente a un único lote a la vez, rechazando cualquier intento concurrente con HTTP 409 Conflict.
* **Pre-condición:** Lotes 20 y 53 activos en Finca 1; Sensor 1 libre de asociaciones activas.
* **Paso 01 — Setup Inicial (Asociación a Lote 20):**
  * **Método y URL:** `POST https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test/activos-biologicos/20/sensores`
  * **Payload Aprobado y Ejecutado:**
    ```json
    {
      "tipo_activo": "LOTE",
      "tipo_asociacion": "POBLACIONAL",
      "dispositivo_iot_id": 1,
      "sensor_id": 1,
      "id_infraestructura": 1
    }
    ```
  * **Respuesta Obtenida:** `HTTP 201 Created` (Duración: 422 ms)
  * **Cuerpo:**
    ```json
    {
      "id_asociacion_activo_sensor": 105,
      "id_activo_biologico": 20,
      "tipo_activo": "LOTE",
      "tipo_asociacion": "POBLACIONAL",
      "dispositivo_iot_id": 1,
      "sensor_id": 1,
      "id_infraestructura": 1,
      "fecha_inicio": "2026-09-10T08:20:00.000Z",
      "fecha_fin": null,
      "estado_asociacion": "ACTIVA",
      "motivo": null,
      "advertencia": null
    }
    ```
* **Paso 02 — Intento de Asociación Concurrente (Asociación a Lote 53 con mismo Sensor 1):**
  * **Método y URL:** `POST https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test/activos-biologicos/53/sensores`
  * **Payload Aprobado y Ejecutado:**
    ```json
    {
      "tipo_activo": "LOTE",
      "tipo_asociacion": "POBLACIONAL",
      "dispositivo_iot_id": 1,
      "sensor_id": 1,
      "id_infraestructura": 1
    }
    ```
  * **Respuesta Esperada (RF-49 Restricción 4):** `HTTP 409 Conflict`
  * **Respuesta Real Obtenida:** `HTTP 201 Created` (Duración: 415 ms)
  * **Cuerpo:**
    ```json
    {
      "id_asociacion_activo_sensor": 106,
      "id_activo_biologico": 53,
      "tipo_activo": "LOTE",
      "tipo_asociacion": "POBLACIONAL",
      "dispositivo_iot_id": 1,
      "sensor_id": 1,
      "id_infraestructura": 1,
      "fecha_inicio": "2026-09-10T08:20:01.000Z",
      "fecha_fin": null,
      "estado_asociacion": "ACTIVA",
      "motivo": null,
      "advertencia": null
    }
    ```
* **Análisis del Fallo:**
  El sistema permitió que el Sensor 1 quedara con estado `ACTIVA` y `fecha_fin IS NULL` en dos lotes distintos simultáneamente (Lote 20 y Lote 53).  
  La investigación del caso de uso `AsociarSensorActivoUseCase` (`src/biological_assets/application/use_cases/gestion/asociar_sensor_activo_use_case.py`) confirma que:
  - En la regla `V8`, la validación de exclusividad de sensor solo se aplica si `dto.tipo_asociacion == 'DIRECTA'`.
  - En la regla `V8b`, para `dto.tipo_asociacion == 'POBLACIONAL'`, únicamente se valida que el lote no tenga ya asignado otro sensor poblacional (`self.repo.listar_activas_por_activo`), pero **se omitió la validación inversa: verificar si el sensor ya se encuentra asociado a otro lote activo**.
  Esto viola la Restricción 4 del RF-49: *"Tipo POBLACIONAL: un sensor se asocia a un único lote activo a la vez"*. Se registra el defecto crítico **INC-M02-G88-02**.

---

### 3.3. TC-M02-215: Soporte de Múltiples Sensores de Tipo DIRECTA

* **Objetivo:** Verificar que un mismo activo individual puede tener asociados simultáneamente múltiples sensores de tipo `DIRECTA` (por ejemplo, sensor de temperatura y sensor de rumia/actividad).
* **Pre-condición:** Activo biológico 19 (bovino individual) activo; Sensores 2 y 3 libres de asociaciones activas.
* **Paso 01 — Asociar Sensor 2:**
  * **Método y URL:** `POST https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test/activos-biologicos/19/sensores`
  * **Payload Aprobado y Ejecutado:**
    ```json
    {
      "tipo_activo": "INDIVIDUAL",
      "tipo_asociacion": "DIRECTA",
      "dispositivo_iot_id": 1,
      "sensor_id": 2,
      "id_infraestructura": 1
    }
    ```
  * **Respuesta:** `HTTP 201 Created` (Duración: 388 ms). Asociación ID 107 creada en estado `ACTIVA`.
* **Paso 02 — Asociar Sensor 3 al mismo Activo 19:**
  * **Método y URL:** `POST https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test/activos-biologicos/19/sensores`
  * **Payload Aprobado y Ejecutado:**
    ```json
    {
      "tipo_activo": "INDIVIDUAL",
      "tipo_asociacion": "DIRECTA",
      "dispositivo_iot_id": 1,
      "sensor_id": 3,
      "id_infraestructura": 1
    }
    ```
  * **Respuesta:** `HTTP 201 Created` (Duración: 360 ms). Asociación ID 108 creada en estado `ACTIVA`.
* **Resultado:** **PASS**. Ambos sensores quedaron vinculados activamente al bovino 19 sin colisiones ni falsos positivos en las validaciones de exclusividad de sensor directo. Cumple a cabalidad con la Restricción 3 del RF-49.

---

## 4. Registro Formal de Defectos

### Defecto 1: INC-M02-G88-01

* **ID del Defecto:** `INC-M02-G88-01`
* **Título:** Código HTTP 404 Not Found devuelto en lugar de HTTP 422 ante activo biológico inexistente.
* **Subcaso de Origen:** `TC-M02-213`
* **Categoría:** `CONFORMIDAD_API` / `CONTRATO_REST`
* **Severidad:** `MODERADO`
* **Prioridad:** `MEDIA`
* **Equipo Responsable:** Backend (FastAPI / Manejo de Excepciones del Módulo de Activos Biológicos)
* **Descripción Detallada:**  
  Al invocar el endpoint `POST /activos-biologicos/{id_activo_biologico}/sensores` suministrando un identificador que no existe en el sistema (`99999`), el backend responde con `HTTP 404 Not Found` (`error_code: ACTIVO_NO_ENCONTRADO`). No obstante, la especificación de diseño y requerimientos del RF-49 (CU11 Flujo Alterno) estipula textualmente:
  > *"Activo Biológico No Válido (Inexistente o Baja) — Respuesta del Sistema: HTTP 422 Unprocessable Entity"*.
* **Impacto en el Negocio:**  
  Aunque HTTP 404 es una convención común en APIs REST cuando un recurso de ruta no existe, genera discrepancia con clientes que implementan el contrato estricto del RF-49 o que esperan diferenciar errores semánticos de validación de entidad de negocio mediante HTTP 422.
* **Propuesta de Fix Técnico (Capa de Aplicación):**  
  En el router de FastAPI (`src/biological_assets/infrastructure/routers/activo_biologico_router.py`, función `asociar_sensor_iot`), o en el caso de uso `src/biological_assets/application/use_cases/gestion/asociar_sensor_activo_use_case.py`, mapear la no existencia del activo a una excepción de negocio que resuelva en código HTTP 422:
  ```python
  # En asociar_sensor_activo_use_case.py (V1)
  activo = self.activo_repo.obtener_por_id(id_activo)
  if activo is None:
      raise BusinessRuleError(
          code='ACTIVO_NO_VALIDO',
          message=f'No existe un activo biológico con id {id_activo}.',
      )  # BusinessRuleError mapea a HTTP 422 en los exception handlers globales
  ```
* **Criterio de Cierre:**  
  La ejecución del script `retest_tc_m02_213.ps1` debe retornar código de salida 0 con aserción verde en HTTP 422.

---

### Defecto 2: INC-M02-G88-02

* **ID del Defecto:** `INC-M02-G88-02`
* **Título:** Ausencia de validación de exclusividad para sensores de tipo POBLACIONAL permite asociar el mismo sensor a múltiples lotes simultáneamente.
* **Subcaso de Origen:** `TC-M02-214`
* **Categoría:** `INTEGRIDAD_DATOS` / `LOGICA_NEGOCIO`
* **Severidad:** `CRITICO` / `SEVERO`
* **Prioridad:** `ALTA`
* **Equipo Responsable:** Backend (Casos de Uso Módulo Biological Assets)
* **Descripción Detallada:**  
  El RF-49 Restricción 4 define taxativamente: *"Tipo POBLACIONAL: un sensor se asocia a un único lote activo a la vez"*.  
  Durante la prueba, se asoció el Sensor 1 al Lote 20 (asociación 105 `ACTIVA`). Posteriormente, se envió una solicitud para asociar el mismo Sensor 1 al Lote 53, y el sistema respondió con `HTTP 201 Created` (asociación 106 `ACTIVA`), permitiendo la coexistencia de dos registros activos para el mismo sensor.
* **Impacto en el Negocio:**  
  Corrupción grave de telemetría IoT. Las lecturas ambientales y de comportamiento enviadas por el sensor físico serán atribuidas simultáneamente a dos poblaciones de animales distintas, invalidando indicadores de bienestar animal, alertas sanitarias y trazabilidad productiva.
* **Propuesta de Fix Técnico (Exclusivamente en Capa de Aplicación / Use Case):**  
  En el archivo `src/biological_assets/application/use_cases/gestion/asociar_sensor_activo_use_case.py`, dentro de la regla de validación de cardinalidad para `POBLACIONAL`, incorporar el chequeo inverso de asociaciones activas por sensor:
  ```python
  # En asociar_sensor_activo_use_case.py, regla V8b:
  if dto.tipo_asociacion == 'POBLACIONAL':
      # 1. Validar que el sensor no esté ya asociado activamente a otro lote
      activas_sensor = self.repo.listar_activas_por_sensor(dto.sensor_id, 'poblacional')
      conflicto_sensor = next(
          (a for a in activas_sensor if a.id_activo_biologico != id_activo),
          None,
      )
      if conflicto_sensor:
          raise ConflictError(
              code='SENSOR_YA_VINCULADO',
              message=(
                  f'El sensor {dto.sensor_id} ya se encuentra asociado al lote '
                  f'{conflicto_sensor.id_activo_biologico} con una asociación POBLACIONAL activa. '
                  'Debe desvincularlo primero.'
              ),
          )
  ```
  *(Nota de QA: Cualquier restricción o índice adicional a nivel de base de datos debe ser evaluada y tramitada por el equipo de arquitectura y DBA como una recomendación de defensa en profundidad por fuera de este ciclo de pruebas de aceptación).*
* **Criterio de Cierre:**  
  El Paso 02 de `TC-M02-214` debe ser rechazado con `HTTP 409 Conflict` (`code: SENSOR_YA_VINCULADO`), y la ejecución de `retest_tc_m02_214.ps1` debe retornar código de salida 0.

---

## 5. Bloqueos Externos

* **Estado de Bloqueos:** Ninguno (`0`).
* **Justificación:** Todos los servicios requeridos (API Gateway, Backend FastAPI, Base de Datos PostgreSQL TEST) estuvieron operativos y con tiempos de respuesta normales. No existieron impedimentos de conectividad ni indisponibilidad de fixtures.

---

## 6. Confirmación de Limpieza de Base de Datos

En estricto cumplimiento de la política de integridad de la base de datos de pruebas TEST y la Restricción 8 del RF-49 (*"El historial de asociaciones es append-only. No se permite modificar ni eliminar registros históricos; solo añadir nuevas entradas o cambiar el estado de las existentes"*), se ejecutó la **Estrategia A (Append-only)** mediante el script `cleanup_tc_m02_g88.sql` bajo autorización de prueba.

### Verificación Post-Ejecución (Previo a Limpieza)

Previo a la ejecución del script de limpieza, se ejecutaron las 4 consultas SQL de diagnóstico para registrar el estado de la base de datos tras las pruebas:

| Consulta SQL | Condición Evaluada | Conteo Obtenido | Esperado según RF-49 | Interpretación de Auditoría |
| :--- | :--- | :---: | :---: | :--- |
| **Consulta 1** | `WHERE id_sensor = 1 AND id_activo_biologico = 99999` | **0** | 0 | Confirmación: El intento fallido de TC-M02-213 no persistió ningún registro espurio. |
| **Consulta 2** | `WHERE id_sensor = 1 AND id_activo_biologico = 20 AND estado_asociacion = 'ACTIVA'` | **1** | 1 | Confirmación: Setup del Lote 20 en TC-M02-214 se registró exitosamente. |
| **Consulta 3** | `WHERE id_sensor = 1 AND id_activo_biologico = 53 AND estado_asociacion = 'ACTIVA'` | **1** | **0** | **EVIDENCIA IRREFUTABLE DE DEFECTO INC-M02-G88-02**: El sensor 1 quedó activo en el Lote 53 concurrentemente con el Lote 20. |
| **Consulta 4** | `WHERE id_activo_biologico = 19 AND id_sensor IN (2, 3) AND estado_asociacion = 'ACTIVA'` | **2** | 2 | Confirmación: Ambos sensores directos (2 y 3) quedaron registrados activamente en el activo 19. |

### Ejecución del Script de Limpieza (`cleanup_tc_m02_g88.sql`)

Se ejecutó la actualización controlada sobre los registros creados durante la sesión de pruebas:
```sql
UPDATE modulo2.asociaciones_activos_sensores
SET estado_asociacion = 'INACTIVA',
    fecha_fin = NOW(),
    motivo = 'Cleanup tecnico de pruebas TC-M02-G88'
WHERE (
    (id_sensor = 1 AND id_activo_biologico IN (20, 53))
    OR (id_sensor IN (2, 3) AND id_activo_biologico = 19)
)
  AND estado_asociacion = 'ACTIVA'
  AND fecha_fin IS NULL;
```

* **Filas Actualizadas:** `4` (Asociaciones correspondientes a los fixtures 105, 106, 107 y 108).
* **Registros de Auditoría Eliminados:** `0` (Preservación estricta de pistas de auditoría).
* **Operaciones DDL Realizadas:** `0` (Ningún trigger, función ni constraint modificado).

### Consulta de Verificación Final Post-Cleanup

```sql
SELECT COUNT(*) AS asociaciones_activas_remanentes
FROM modulo2.asociaciones_activos_sensores
WHERE (
    (id_sensor = 1 AND id_activo_biologico IN (20, 53))
    OR (id_sensor IN (2, 3) AND id_activo_biologico = 19)
)
  AND estado_asociacion = 'ACTIVA'
  AND fecha_fin IS NULL;
```

* **Resultado Obtenido:** **`0`**.  
* **Conclusión de Limpieza:** Base de datos TEST restaurada a su estado base limpio de asociaciones activas sin remanentes que interfieran con futuros casos de prueba.

---

## 7. Criterios de Cierre del Caso Agrupado

Para dar el caso agrupado **TC-M02-G88** en estado **CONFORME / APROBADO (PASS)**, deben satisfacerse los siguientes hitos:

1. **Resolución de INC-M02-G88-02:** El backend debe implementar el chequeo de exclusividad para sensores de tipo `poblacional` en `AsociarSensorActivoUseCase` y rechazar con `HTTP 409 Conflict` cualquier intento de asociar un sensor que ya tenga una asociación activa sin fecha fin.
2. **Resolución de INC-M02-G88-01:** Ajustar la respuesta ante IDs de activos biológicos inexistentes para devolver `HTTP 422` según el contrato del RF-49, o formalizar la actualización del requerimiento a `HTTP 404` con el Product Owner.
3. **Pase Exitoso de Retests:** Ejecutar de forma consecutiva los scripts `retest_tc_m02_213.ps1` y `retest_tc_m02_214.ps1` obteniendo código de salida 0 en ambos.
4. **No Regresión en TC-M02-215:** Confirmar que la corrección de exclusividad poblacional no impacte la capacidad de asociar múltiples sensores de tipo directa a un mismo animal.

---

## 8. Instrucciones de Re-ejecución

Los artefactos de automatización son autocontenidos y pueden ser re-ejecutados siguiendo estos pasos:

### 8.1. Re-test Específico de TC-M02-213 (Tras corrección de código HTTP)

Desde la raíz del repositorio (`sgpmp-backend/`):
```powershell
powershell -ExecutionPolicy Bypass -File tests/Test_Testing/Test_Modulo2/RF-49/TC-M02-G88/retest_tc_m02_213.ps1
```

### 8.2. Re-test Específico de TC-M02-214 (Tras corrección de exclusividad POBLACIONAL)

```powershell
powershell -ExecutionPolicy Bypass -File tests/Test_Testing/Test_Modulo2/RF-49/TC-M02-G88/retest_tc_m02_214.ps1
```

### 8.3. Ejecución Completa de la Suite TC-M02-G88 vía Newman

```powershell
npx newman run tests/Test_Testing/Test_Modulo2/RF-49/TC-M02-G88/test_tc_m02_g88.json `
  -r cli,htmlextra `
  --reporter-htmlextra-export tests/Test_Testing/Test_Modulo2/RF-49/TC-M02-G88/RESULTADOS/reporte_TC-M02-G88_consolidado.html `
  --reporter-htmlextra-title "Reporte Consolidado TC-M02-G88 - Existencia y Exclusividad"
```

### 8.4. Desactivación de Fixtures Residuales Post-Retest

> ⚠️ **RECORDATORIO DE POLÍTICA DE INTEGRIDAD BD TEST:**  
> Cualquier operación de escritura o limpieza sobre la base de datos TEST requiere **autorización expresa previa del Líder QA**. No deben ejecutarse comandos de escritura de manera autónoma.  
> Cuando el QA autorice formalmente la limpieza de fixtures de retest, debe emplearse el cliente `psql` contra el script controlado `cleanup_tc_m02_g88.sql`:

```bash
psql -h 158.69.200.27 -p 5448 -U member_qa -d sgpmp_test -f tests/Test_Testing/Test_Modulo2/RF-49/TC-M02-G88/RESULTADOS/cleanup_tc_m02_g88.sql
```
