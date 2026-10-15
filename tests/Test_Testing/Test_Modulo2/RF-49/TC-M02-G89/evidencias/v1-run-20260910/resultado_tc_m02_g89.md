# INFORME DE EJECUCIÓN: CASO AGRUPADO TC-M02-G89
**Módulo:** 2 — Activos Biológicos  
**Requisito Funcional:** RF-49: Asociación de sensores IoT a activos biológicos (Ciclo de Vida Formal: Superación, Desactivación, Reactivación y Transiciones Inválidas)  
**Entorno de Pruebas:** TEST (`https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test/`)  
**Base de Datos TEST:** PostgreSQL 16 (`158.69.200.27:5448/sgpmp_test`)  
**Fecha de Ejecución:** 2026-09-10  
**Herramienta de Ejecución:** Newman v6.2.1 + newman-reporter-htmlextra  
**Estado Global:** **NO CONFORME (0 PASS / 4 FAIL)**

---

## 1. RESUMEN EJECUTIVO Y TABLA DE VEREDICTOS

Se ejecutó la suite de pruebas agrupada **TC-M02-G89**, diseñada para verificar las transiciones formales del ciclo de vida de asociaciones IoT contempladas en el estándar del RF-49:
- **TC-M02-217:** Transición automática `ACTIVA` → `SUPERADA` al registrar una nueva asociación directa para el mismo activo y sensor.
- **TC-M02-216:** Transición de desactivación manual `ACTIVA` → `INACTIVA` vía `PATCH`.
- **TC-M02-218:** Transición de reactivación `INACTIVA` → `ACTIVA` vía `PATCH`.
- **TC-M02-219:** Rechazo de transición inválida `INACTIVA` → `SUPERADA` vía `PATCH` (esperado HTTP 409 Conflict).

### Tabla de Veredictos

| Subcaso | Nombre / Objetivo | Método / Endpoint | HTTP Esp. | HTTP Obt. | Aserciones | Veredicto | Defecto Asociado |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| **TC-M02-217** | Superación automática (`ACTIVA` → `SUPERADA`) | `POST /activos-biologicos/19/sensores` | 201 | 500 | 2/4 | **FAIL** | [INC-M02-G89-02](#defecto-inc-m02-g89-02-crítico) |
| **TC-M02-216** | Desactivación manual (`ACTIVA` → `INACTIVA`) | `PATCH /activos-biologicos/19/sensores/17` | 200 | 404 | 1/2 | **FAIL** | [INC-M02-G89-01](#defecto-inc-m02-g89-01-severo) (Manif. 1) |
| **TC-M02-218** | Reactivación manual (`INACTIVA` → `ACTIVA`) | `PATCH /activos-biologicos/19/sensores/17` | 200 | 404 | 1/2 | **FAIL** | [INC-M02-G89-01](#defecto-inc-m02-g89-01-severo) (Manif. 2) |
| **TC-M02-219** | Transición inválida (`INACTIVA` → `SUPERADA`) | `PATCH /activos-biologicos/19/sensores/17` | 409 | 404 | 1/2 | **FAIL** | [INC-M02-G89-01](#defecto-inc-m02-g89-01-severo) (Manif. 3) |

**Resultado Consolidado:** 0 de 4 subcasos aprobados. Veredicto global: **NO CONFORME**.

---

## 2. MÉTRICAS DE EJECUCIÓN

| Métrica | Valor |
| :--- | :--- |
| **Total Subcasos Ejecutados** | 4 |
| **Subcasos PASS** | 0 (0%) |
| **Subcasos FAIL** | 4 (100%) |
| **Total Solicitudes HTTP (incluyendo Auth)** | 9 |
| **Total Aserciones Evaluadas** | 10 |
| **Aserciones Superadas** | 5 |
| **Aserciones Fallidas** | 5 |
| **Tiempo Promedio de Respuesta Backend** | ~240 ms (excluyendo latencia de red inicial) |
| **Defectos Críticos Detectados** | 1 (`INC-M02-G89-02` en trigger de unicidad de BD) |
| **Defectos Severos Detectados** | 1 (`INC-M02-G89-01` endpoints de ciclo de vida inexistentes) |
| **Estado de BD al Finalizar** | Limpia (0 asociaciones remanentes, histórico íntegro) |

---

## 3. DETALLE TÉCNICO POR SUBCASO

### 3.1 TC-M02-217 — Superación Automática (`ACTIVA` → `SUPERADA`)
- **Paso 01 (Setup Asociación A):**
  - **Solicitud:** `POST /activos-biologicos/19/sensores`
  - **Payload Aprobado y Ejecutado:**
    ```json
    {
      "tipo_activo": "INDIVIDUAL",
      "tipo_asociacion": "DIRECTA",
      "dispositivo_iot_id": 1,
      "sensor_id": 2,
      "id_infraestructura": 1
    }
    ```
  - **Respuesta:** `HTTP 201 Created`
  - **Cuerpo:**
    ```json
    {
      "id_asociacion_activo_sensor": 17,
      "id_activo_biologico": 19,
      "id_sensor": 2,
      "tipo": "directa",
      "estado_asociacion": "ACTIVA",
      "fecha_inicio": "2026-09-10T09:13:35.509751Z",
      "fecha_fin": null,
      "motivo": null
    }
    ```
  - **Aserciones:** 2/2 PASS (`[217] Creacion exitosa de Asociacion A`, `[217] Asociacion A en estado ACTIVA`).
- **Paso 02 (Superación con Asociación B):**
  - **Solicitud:** `POST /activos-biologicos/19/sensores`
  - **Payload Aprobado y Ejecutado:**
    ```json
    {
      "tipo_activo": "INDIVIDUAL",
      "tipo_asociacion": "DIRECTA",
      "dispositivo_iot_id": 1,
      "sensor_id": 2,
      "id_infraestructura": 1
    }
    ```
  - **Respuesta:** `HTTP 500 Internal Server Error`
  - **Cuerpo:**
    ```json
    {
      "detail": "Error interno al procesar la solicitud"
    }
    ```
  - **Aserciones:** 0/2 PASS (Fallo por status code 500 en vez de 201).
  - **Diagnóstico Transaccional:** La transacción de aplicación intentó actualizar la asociación 17 a `SUPERADA` con `fecha_fin = clock_timestamp()` y luego insertar la nueva fila. Sin embargo, el trigger `modulo2.trg_fn_asociacion_sensor_activo_unica` bloqueó el `INSERT` al evaluar `fecha_fin > now()` arrojando conflicto `P0229` y provocando rollback íntegro.
  - **Veredicto:** **FAIL** (Defecto `INC-M02-G89-02`).

### 3.2 TC-M02-216 — Desactivación Manual (`ACTIVA` → `INACTIVA`)
- **Paso 01:**
  - **Solicitud:** `PATCH /activos-biologicos/19/sensores/17`
  - **Payload Aprobado y Ejecutado:**
    ```json
    {
      "estado_asociacion": "INACTIVA",
      "motivo_cambio": "Desactivacion manual de sensor por mantenimiento TC-M02-216"
    }
    ```
  - **Respuesta:** `HTTP 404 Not Found`
  - **Cuerpo:**
    ```json
    {
      "detail": "Not Found"
    }
    ```
  - **Aserciones:** 0/1 PASS (`expected response to have status code 200 but got 404`).
  - **Veredicto:** **FAIL** (Defecto `INC-M02-G89-01`, Manifestación 1).

### 3.3 TC-M02-218 — Reactivación (`INACTIVA` → `ACTIVA`)
- **Paso 01:**
  - **Solicitud:** `PATCH /activos-biologicos/19/sensores/17`
  - **Payload Aprobado y Ejecutado:**
    ```json
    {
      "estado_asociacion": "ACTIVA",
      "motivo_cambio": "Reactivacion de sensor tras mantenimiento TC-M02-218"
    }
    ```
  - **Respuesta:** `HTTP 404 Not Found`
  - **Cuerpo:**
    ```json
    {
      "detail": "Not Found"
    }
    ```
  - **Aserciones:** 0/1 PASS (`expected response to have status code 200 but got 404`).
  - **Veredicto:** **FAIL** (Defecto `INC-M02-G89-01`, Manifestación 2).

### 3.4 TC-M02-219 — Transición Inválida (`INACTIVA` → `SUPERADA`)
- **Paso 01:**
  - **Solicitud:** `PATCH /activos-biologicos/19/sensores/17`
  - **Payload Aprobado y Ejecutado:**
    ```json
    {
      "estado_asociacion": "SUPERADA",
      "motivo_cambio": "Intento no permitido de superacion directa desde inactiva TC-M02-219"
    }
    ```
  - **Respuesta:** `HTTP 404 Not Found`
  - **Cuerpo:**
    ```json
    {
      "detail": "Not Found"
    }
    ```
  - **Aserciones:** 0/1 PASS (`expected response to have status code 409 but got 404`).
  - **Veredicto:** **FAIL** (Defecto `INC-M02-G89-01`, Manifestación 3).

---

## 4. REGISTRO FORMAL DE DEFECTOS

### DEFECTO INC-M02-G89-01 (Severo)
- **Título:** Inexistencia de endpoints HTTP para la gestión de ciclo de vida (PATCH /activos-biologicos/{id}/sensores/{id_asoc}).
- **Subcasos de Origen:** TC-M02-216, TC-M02-218, TC-M02-219.
- **Categoría:** COMUNICACIÓN HTTP / ENDPOINT INEXISTENTE (`HTTP_COM`).
- **Severidad:** SEVERO (S2).
- **Prioridad:** MEDIA.
- **Equipo Responsable:** Backend / Desarrollo API.
- **Tiempo Máximo de Solución:** 8 horas.
- **Impacto:** Imposibilidad funcional de desactivar o reactivar asociaciones desde la API sin recurrir a manipulaciones manuales en base de datos.
- **Manifestaciones:**
  1. *Manifestación 1 (TC-M02-216):* Desactivación manual responde `404 Not Found`.
  2. *Manifestación 2 (TC-M02-218):* Reactivación responde `404 Not Found`.
  3. *Manifestación 3 (TC-M02-219):* Transición inválida responde `404 Not Found` en lugar de `409 Conflict`.
- **Criterio de Cierre:** Implementación del router en FastAPI con sus casos de uso correspondientes que atiendan peticiones PATCH respetando las transiciones válidas del RF-49 y retornando `409 Conflict` ante transiciones no permitidas.

---

### DEFECTO INC-M02-G89-02 (Crítico)
- **Título:** El trigger `modulo2.trg_fn_asociacion_sensor_activo_unica` bloquea la transición `ACTIVA` → `SUPERADA` por comparar `fecha_fin > now()` en lugar de `fecha_fin IS NULL`.
- **Subcaso de Origen:** TC-M02-217.
- **Categoría:** UNICIDAD / INTEGRIDAD DE ESTADO (`UNICIDAD / ESTADO`).
- **Severidad:** **CRÍTICO (S1)**.
- **Prioridad:** **ALTA**.
- **Equipo Responsable:** Desarrollo Backend + DBA.
- **Tiempo Máximo de Solución:** 4 horas.
- **Impacto:** Ningún usuario o proceso del sistema puede reemplazar o superponer un sensor de tipo `directa` sobre un activo biológico vía API, provocando error no controlado `HTTP 500 Internal Server Error`.
- **Causa Raíz (3 dimensiones analíticas):**
  1. **Dimensión Temporal / Timestamp Congelado:** El trigger evalúa `fecha_fin > now()`. En PostgreSQL, `now()` corresponde a `transaction_timestamp()`, el cual se congela al inicio de la transacción (`T0`). Al ejecutarse el caso de uso, la asociación previa se actualiza con `fecha_fin = clock_timestamp()` (`T1`), donde `T1 > T0`. La condición `fecha_fin > now()` evalúa matemáticamente a `TRUE`, considerando erróneamente la asociación anterior como un conflicto vigente.
  2. **Ausencia de Exclusión de Propio Activo:** No filtra por `id_activo_biologico != NEW.id_activo_biologico`, bloqueando la auto-superación dentro del mismo activo.
  3. **Inexistencia de Filtro de Estado:** No excluye registros con `estado_asociacion = 'SUPERADA'` o `estado_asociacion = 'INACTIVA'`, por lo que una fila recién marcada como `SUPERADA` dentro de la transacción es contabilizada en `v_count`.
- **Evidencia Matemática Irrefutable (SQL):**
  Al ejecutar una transacción con `UPDATE` a `SUPERADA` y evaluar la condición del trigger:
  ```sql
  BEGIN;
  UPDATE modulo2.asociaciones_activos_sensores
  SET fecha_fin = clock_timestamp(), estado_asociacion = 'SUPERADA'
  WHERE id_asociacion_activo_sensor = 17;

  SELECT id_asociacion_activo_sensor, id_sensor, id_activo_biologico,
         tipo, estado_asociacion, fecha_inicio, fecha_fin,
         (fecha_fin > now()) AS evalua_verdadero
  FROM modulo2.asociaciones_activos_sensores
  WHERE id_sensor = 2 AND tipo = 'directa'
  ORDER BY id_asociacion_activo_sensor DESC
  LIMIT 5;
  ```
  **Resultado Obtenido:**
  ```json
  [
    {
      "id_asociacion_activo_sensor": "17",
      "id_sensor": "2",
      "id_activo_biologico": "19",
      "tipo": "directa",
      "estado_asociacion": "SUPERADA",
      "fecha_inicio": "2026-09-10 09:13:35.509751+00:00",
      "fecha_fin": "2026-09-10 09:22:08.574635+00:00",
      "evalua_verdadero": "True"
    }
  ]
  ```
  El campo `evalua_verdadero` devuelve **`True`**, confirmando que el trigger detecta un conflicto ficticio y aborta el `INSERT` con excepción `P0229`.
- **Integración de Observaciones:** Se promueve formalmente la observación previa `OBS-M02-G89-01` a formar parte integral de este defecto.
- **Descripción Conceptual del Fix (Sin DDL ni código PL/pgSQL — a cargo de Desarrollo + DBA):**
  Conceptualmente, la verificación de conflicto ejecutada por el trigger debe modificarse para satisfacer tres reglas de negocio esenciales:
  1. Evaluar vigencia por ausencia de fecha de finalización (`fecha_fin IS NULL`), en lugar de realizar comparaciones de tiempo relativo respecto a `now()`, evitando la trampa de sincronización de timestamps transaccionales.
  2. Discriminar la pertenencia del activo biológico: el conflicto solo debe existir si el sensor ya se encuentra activo en **otro** activo biológico distinto (`id_activo_biologico != NEW.id_activo_biologico`). Si se trata del mismo activo, la asociación previa está siendo superada transaccionalmente.
  3. Excluir explícitamente cualquier asociación cuyo estado ya haya sido actualizado a `SUPERADA` o `INACTIVA`, asegurando que solo los registros en estado `ACTIVA` participen del cómputo de unicidad.
- **Criterio de Cierre:** La ejecución de `retest_tc_m02_217.ps1` retorna exit code 0 con veredicto **PASS**.

---

## 5. BLOQUEOS EXTERNOS

- **Bloqueos Externos:** Ninguno. El entorno TEST, la infraestructura de base de datos y la red respondieron con normalidad.

---

## 6. CONFIRMACIÓN DE LIMPIEZA DE BASE DE DATOS

En estricto apego al RF-49 (Restricción 8: *Diseño Append-Only*), se aplicó la **Estrategia A** mediante el script `cleanup_tc_m02_g89.sql`. No se ejecutó ningún `DELETE` ni modificación de esquema DDL.

### Resultado de Ejecución de Limpieza:
```text
Filas actualizadas por cleanup: 1
asociaciones_activas_remanentes: 0
```

### Comprobación Post-Limpieza:
```sql
SELECT COUNT(*) AS asociaciones_activas_remanentes
FROM modulo2.asociaciones_activos_sensores
WHERE id_activo_biologico = 19
  AND id_sensor = 2
  AND estado_asociacion = 'ACTIVA'
  AND fecha_fin IS NULL;
```
**Resultado:** `0`. Base de datos completamente limpia y lista para siguientes ejecuciones.

---

## 7. CRITERIOS DE CIERRE DE DEFECTOS

1. **INC-M02-G89-01:**
   - Despliegue en TEST de los endpoints `PATCH /activos-biologicos/{id}/sensores/{id_asociacion}`.
   - Ejecución exitosa (`exit code 0`) de `retest_tc_m02_216.ps1`, `retest_tc_m02_218.ps1` y `retest_tc_m02_219.ps1`.
2. **INC-M02-G89-02:**
   - Despliegue de la corrección del trigger `modulo2.trg_fn_asociacion_sensor_activo_unica` en TEST.
   - Ejecución exitosa (`exit code 0`) de `retest_tc_m02_217.ps1` con creación de la nueva asociación en estado `ACTIVA` y transición de la previa a `SUPERADA` con `HTTP 201 Created`.

---

## 8. INSTRUCCIONES DE RE-EJECUCIÓN (SCRIPTS DE RETEST)

Se dejan configurados 4 scripts automatizados en PowerShell para re-test individual una vez que los equipos de Desarrollo y DBA apliquen las correcciones:

1. **Retest Superación Automática (TC-M02-217):**
   ```powershell
   .\tests\Test_Testing\Test_Modulo2\RF-49\TC-M02-G89\retest_tc_m02_217.ps1
   ```
2. **Retest Desactivación Manual (TC-M02-216):**
   ```powershell
   .\tests\Test_Testing\Test_Modulo2\RF-49\TC-M02-G89\retest_tc_m02_216.ps1
   ```
3. **Retest Reactivación (TC-M02-218):**
   ```powershell
   .\tests\Test_Testing\Test_Modulo2\RF-49\TC-M02-G89\retest_tc_m02_218.ps1
   ```
4. **Retest Transición Inválida (TC-M02-219):**
   ```powershell
   .\tests\Test_Testing\Test_Modulo2\RF-49\TC-M02-G89\retest_tc_m02_219.ps1
   ```

*Nota: Los scripts 216, 218 y 219 permanecen congelados hasta la implementación del endpoint PATCH. El script 217 permanece congelado hasta la corrección del trigger de base de datos.*
