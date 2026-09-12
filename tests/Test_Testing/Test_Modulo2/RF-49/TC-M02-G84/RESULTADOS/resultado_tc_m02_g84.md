# INFORME DE RESULTADOS DE PRUEBAS DE ASOCIACIÓN DE SENSORES IOT
## CASO AGRUPADO: TC-M02-G84 (RF-49: Asociación de Sensores IoT a Activos Biológicos)

- **Fecha de Ejecución:** 2026-09-10
- **Entorno Objetivo:** TEST (`https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test`)
- **Base de Datos TEST:** `postgresql://member_qa:qaSGP2026@158.69.200.27:5448/sgpmp_test`
- **Herramientas Utilizadas:**
  - **Newman:** v6.2.2 + `newman-reporter-htmlextra` v1.23.1
- **Suites Ejecutadas:**
  - Colección Newman: `sgpmp-backend/tests/Test_Testing/Test_Modulo2/RF-49/TC-M02-G84/test_tc_m02_g84.json`
    - Folder `TC-M02-143` (Asociación DIRECTA)
    - Folder `TC-M02-144` (Asociación AMBIENTAL)
    - Folder `TC-M02-145` (Asociación POBLACIONAL)
    - Folder `TC-M02-150` (Dispositivo Desconectado)
- **Reportes HTML Generados:**
  - `sgpmp-backend/tests/Test_Testing/Test_Modulo2/RF-49/TC-M02-G84/RESULTADOS/reporte_TC-M02-143.html` (68 KB)
  - `sgpmp-backend/tests/Test_Testing/Test_Modulo2/RF-49/TC-M02-G84/RESULTADOS/reporte_TC-M02-144.html` (68 KB)
  - `sgpmp-backend/tests/Test_Testing/Test_Modulo2/RF-49/TC-M02-G84/RESULTADOS/reporte_TC-M02-145.html` (68 KB)
  - `sgpmp-backend/tests/Test_Testing/Test_Modulo2/RF-49/TC-M02-G84/RESULTADOS/reporte_TC-M02-150.html` (72 KB)
- **Documentos y Scripts de Gestión Asociados:**
  - **Script de Re-test Diferido:** `sgpmp-backend/tests/Test_Testing/Test_Modulo2/RF-49/TC-M02-G84/retest_tc_m02_150.ps1`
  - **Script de Contingencia y Limpieza:** `sgpmp-backend/tests/Test_Testing/Test_Modulo2/RF-49/TC-M02-G84/RESULTADOS/cleanup_tc_m02_g84.sql`
- **Veredicto Global:** **PASS PARCIAL POR BLOQUEO EXTERNO (3 PASSED, 1 BLOCKED)**

---

## 1. Resumen Ejecutivo de Resultados

El caso agrupado **TC-M02-G84** evalúa la funcionalidad de vinculación de sensores IoT a activos biológicos (`POST /activos-biologicos/{id_activo}/sensores`) conforme al **RF-49 (CU11)**, analizando las modalidades de monitoreo zootécnico (DIRECTA, AMBIENTAL, POBLACIONAL) y la respuesta del sistema ante dispositivos IoT desconectados:

| Subcaso | Enfoque Evaluado | Datos Utilizados | Resultado Esperado | Resultado Obtenido | Reporte HTML | Veredicto |
| :--- | :--- | :--- | :--- | :--- | :--- | :---: |
| **TC-M02-143** | Asociación DIRECTA a activo individual válido | Activo 108 (`INDIVIDUAL`), Sensor 22 (Disp 38, Infra 3) | HTTP 201 Created, `estado_asociacion: ACTIVA`, `tipo: directa`, activo vinculado exitosamente. | HTTP 201 Created, `estado_asociacion: ACTIVA`, `tipo_asociacion: directa`. Asociación persistida. | `reporte_TC-M02-143.html` | **PASS** |
| **TC-M02-144** | Asociación AMBIENTAL compartida a infraestructura | Activo 109 (`INDIVIDUAL`), Sensor 23 (Disp 39, Infra 3) | HTTP 201 Created, `estado_asociacion: ACTIVA`, `tipo: ambiental`, vinculado a infraestructura 3. | HTTP 201 Created, `estado_asociacion: ACTIVA`, `tipo_asociacion: ambiental`. Asociación persistida. | `reporte_TC-M02-144.html` | **PASS** |
| **TC-M02-145** | Asociación POBLACIONAL a lote | Activo 83 (`LOTE`), Sensor 24 (Disp 40, Infra 3) | HTTP 201 Created, `estado_asociacion: ACTIVA`, `tipo: poblacional`, tipo activo LOTE. | HTTP 201 Created, `estado_asociacion: ACTIVA`, `tipo_asociacion: poblacional`. Asociación persistida. | `reporte_TC-M02-145.html` | **PASS** |
| **TC-M02-150** | Advertencia por dispositivo IoT desconectado | Activo 110 (`INDIVIDUAL`), Sensor 6 (Disp 3) | HTTP 201 Created, asociación ACTIVA, advertencia presente informando dispositivo desconectado. | HTTP 201 Created, asociación registrada correctamente. El campo `advertencia` retorna `null` porque el Módulo 3 (Telemetría) no está implementado, por lo que no es posible verificar el heartbeat del dispositivo. | `reporte_TC-M02-150.html` | **BLOQUEADO (Módulo 3 no disponible)** |

---

## 2. Métricas de Ejecución

| Subcaso | Carpeta Newman | Peticiones HTTP | Aserciones Totales | Exitosas | Fallidas / Pendientes | Duración | Estado |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **TC-M02-143** | `TC-M02-143` | 2 | 4 | 4 | 0 | 3.4 s | **PASSED** |
| **TC-M02-144** | `TC-M02-144` | 2 | 3 | 3 | 0 | 1.4 s | **PASSED** |
| **TC-M02-145** | `TC-M02-145` | 2 | 3 | 3 | 0 | 1.9 s | **PASSED** |
| **TC-M02-150** | `TC-M02-150` | 2 | 4 | 3 | 1 (bloqueo M03) | 2.3 s | **BLOCKED** |
| **Total Suite** | **Colección Completa** | **8 requests** | **14 aserciones** | **13** | **1** | **9.0 s** | **3 PASSED, 0 FAILED, 1 BLOCKED** |

---

## 3. Detalle Técnico por Subcaso

### 3.1. Subcaso TC-M02-143: Asociar sensor DIRECTA a activo individual válido

- **Objetivo:** Registrar una vinculación biométrica unívoca entre sensor y activo individual (`tipo_asociacion=DIRECTA`).
- **Petición HTTP:** `POST /activos-biologicos/108/sensores`
- **Payload Enviado:**
  ```json
  {
    "tipo_activo": "INDIVIDUAL",
    "tipo_asociacion": "DIRECTA",
    "dispositivo_iot_id": 38,
    "sensor_id": 22,
    "id_infraestructura": 3,
    "motivo": "Monitoreo biometrico individual TC-M02-143"
  }
  ```
- **Respuesta Recibida (201 Created):**
  ```json
  {
    "id_asociacion_activo_sensor": 5,
    "id_activo_biologico": 108,
    "tipo_activo": "INDIVIDUAL",
    "tipo_asociacion": "directa",
    "dispositivo_iot_id": 38,
    "sensor_id": 22,
    "id_infraestructura": 3,
    "fecha_inicio": "2026-09-10T06:15:00.326100Z",
    "fecha_fin": null,
    "estado_asociacion": "ACTIVA",
    "motivo": "Monitoreo biometrico individual TC-M02-143",
    "advertencia": null
  }
  ```
- **Aserciones Evaluadas:**
  - `[Auth] Autenticación exitosa (200 OK)`: **PASS**
  - `Código HTTP es 201 Created`: **PASS**
  - `Estructura de respuesta contiene identificadores correctos`: **PASS**
  - `Estado de asociación es ACTIVA y tipo es directa`: **PASS**
- **Veredicto:** ✅ **PASS (100% exitoso)**

---

### 3.2. Subcaso TC-M02-144: Asociar sensor AMBIENTAL compartido a infraestructura

- **Objetivo:** Vincular un sensor ambiental a nivel de infraestructura para contextualizar a los activos residentes (`1 sensor → N activos`).
- **Petición HTTP:** `POST /activos-biologicos/109/sensores`
- **Payload Enviado:**
  ```json
  {
    "tipo_activo": "INDIVIDUAL",
    "tipo_asociacion": "AMBIENTAL",
    "dispositivo_iot_id": 39,
    "sensor_id": 23,
    "id_infraestructura": 3,
    "motivo": "Monitoreo ambiental compartido infraestructura TC-M02-144"
  }
  ```
- **Respuesta Recibida (201 Created):**
  ```json
  {
    "id_asociacion_activo_sensor": 6,
    "id_activo_biologico": 109,
    "tipo_activo": "INDIVIDUAL",
    "tipo_asociacion": "ambiental",
    "dispositivo_iot_id": 39,
    "sensor_id": 23,
    "id_infraestructura": 3,
    "fecha_inicio": "2026-09-10T06:15:19.780314Z",
    "fecha_fin": null,
    "estado_asociacion": "ACTIVA",
    "motivo": "Monitoreo ambiental compartido infraestructura TC-M02-144",
    "advertencia": null
  }
  ```
- **Aserciones Evaluadas:**
  - `[Auth] Autenticación exitosa (200 OK)`: **PASS**
  - `Código HTTP es 201 Created`: **PASS**
  - `Asociación ambiental vinculada a infraestructura correctamente`: **PASS**
- **Veredicto:** ✅ **PASS (100% exitoso)**

---

### 3.3. Subcaso TC-M02-145: Asociar sensor POBLACIONAL a lote

- **Objetivo:** Registrar una vinculación exclusiva entre un sensor y un activo biológico de tipo `POBLACIONAL` / `LOTE`.
- **Petición HTTP:** `POST /activos-biologicos/83/sensores`
- **Payload Enviado:**
  ```json
  {
    "tipo_activo": "LOTE",
    "tipo_asociacion": "POBLACIONAL",
    "dispositivo_iot_id": 40,
    "sensor_id": 24,
    "id_infraestructura": 3,
    "motivo": "Monitoreo poblacional lote TC-M02-145"
  }
  ```
- **Respuesta Recibida (201 Created):**
  ```json
  {
    "id_asociacion_activo_sensor": 7,
    "id_activo_biologico": 83,
    "tipo_activo": "LOTE",
    "tipo_asociacion": "poblacional",
    "dispositivo_iot_id": 40,
    "sensor_id": 24,
    "id_infraestructura": 3,
    "fecha_inicio": "2026-09-10T06:15:32.893717Z",
    "fecha_fin": null,
    "estado_asociacion": "ACTIVA",
    "motivo": "Monitoreo poblacional lote TC-M02-145",
    "advertencia": null
  }
  ```
- **Aserciones Evaluadas:**
  - `[Auth] Autenticación exitosa (200 OK)`: **PASS**
  - `Código HTTP es 201 Created`: **PASS**
  - `Asociación POBLACIONAL vinculada a lote correctamente`: **PASS**
- **Veredicto:** ✅ **PASS (100% exitoso)**

---

### 3.4. Subcaso TC-M02-150: Advertencia por dispositivo IoT desconectado

- **Objetivo:** Verificar que el sistema permita registrar la asociación de un sensor cuando su dispositivo IoT no reporta heartbeat reciente (>30 minutos), retornando `HTTP 201 Created` con una advertencia informativa no bloqueante.
- **Petición HTTP:** `POST /activos-biologicos/110/sensores`
- **Payload Enviado:**
  ```json
  {
    "tipo_activo": "INDIVIDUAL",
    "tipo_asociacion": "DIRECTA",
    "dispositivo_iot_id": 3,
    "sensor_id": 6,
    "id_infraestructura": 3,
    "motivo": "Verificacion advertencia dispositivo desconectado TC-M02-150"
  }
  ```
- **Respuesta Recibida (201 Created):**
  ```json
  {
    "id_asociacion_activo_sensor": 8,
    "id_activo_biologico": 110,
    "tipo_activo": "INDIVIDUAL",
    "tipo_asociacion": "directa",
    "dispositivo_iot_id": 3,
    "sensor_id": 6,
    "id_infraestructura": 3,
    "fecha_inicio": "2026-09-10T06:15:53.159334Z",
    "fecha_fin": null,
    "estado_asociacion": "ACTIVA",
    "motivo": "Verificacion advertencia dispositivo desconectado TC-M02-150",
    "advertencia": null
  }
  ```
- **Aserciones Evaluadas:**
  - `[Auth] Autenticación exitosa (200 OK)`: **PASS**
  - `Código HTTP es 201 Created`: **PASS**
  - `Asociación registrada exitosamente como ACTIVA`: **PASS**
  - `Respuesta incluye advertencia informativa de dispositivo desconectado`: **PENDIENTE POR BLOQUEO EXTERNO**
- **Bloqueo por dependencia:**
  - El subcaso requiere verificar el estado de heartbeat de los dispositivos IoT (servicio provisto por el Módulo 3 - Telemetría).
  - El Módulo 3 (Telemetría) aún no está implementado en el sistema actual ni disponible en el entorno TEST.
  - La asociación se registra correctamente en base de datos con `HTTP 201 Created` y `estado_asociacion: ACTIVA`.
  - El campo `advertencia` retorna `null` debido a que no existe fuente de datos de telemetría para construirla en esta fase.
  - **No es un defecto del backend**: se trata de una funcionalidad condicionada a una dependencia externa pendiente de integración.
- **Veredicto:** ⚠️ **BLOQUEADO (Módulo 3 no disponible)**

---

## 4. Teardown y Limpieza del Entorno TEST

Tras la ejecución de las pruebas y la obtención de las evidencias correspondientes, se procedió a ejecutar el script `sgpmp-backend/tests/Test_Testing/Test_Modulo2/RF-49/TC-M02-G84/RESULTADOS/cleanup_tc_m02_g84.sql`:
- Se eliminaron los registros de auditoría vinculados en `modulo2.auditorias_asociaciones_sensor_activo`.
- Se eliminaron las asociaciones generadas durante las pruebas en `modulo2.asociaciones_activos_sensores`.
- Verificación en base de datos:
  ```sql
  SELECT COUNT(*) FROM modulo2.asociaciones_activos_sensores
  WHERE id_sensor IN (22, 23, 24, 6) AND id_activo_biologico IN (108, 109, 83, 110);
  -- Resultado verificado: 0 asociaciones remanentes
  ```
El entorno TEST quedó en su estado original y limpio.

---

## 5. Criterios de Cierre del Caso Agrupado TC-M02-G84

El caso agrupado **TC-M02-G84** permanecerá en estado **PASS PARCIAL POR BLOQUEO EXTERNO** hasta que el Módulo 3 (Telemetría) se encuentre implementado y disponible en el entorno TEST.

Para proceder con el cierre definitivo se requiere:
1. Disponibilidad y despliegue del Módulo 3 (Telemetría / Heartbeats de dispositivos IoT) en el entorno TEST.
2. Ejecución del script de re-test diferido:
   ```powershell
   ./tests/Test_Testing/Test_Modulo2/RF-49/TC-M02-G84/retest_tc_m02_150.ps1
   ```
3. Obtención de veredicto conforme en `reporte_TC-M02-150.html` validando la presencia de la advertencia informativa.
4. Ejecución del script `cleanup_tc_m02_g84.sql`.
5. Actualización del veredicto global en este informe y en `GUIA_PRUEBAS_Y_ESTRUCTURA.md` a **PASS COMPLETO**.
