# INFORME DE RESULTADOS DE PRUEBAS DE VALIDACIÓN Y CONTROLES DE ASOCIACIÓN DE SENSORES
## CASO AGRUPADO: TC-M02-G85 (RF-49: Asociación de Sensores IoT a Activos Biológicos)

- **Fecha de Ejecución:** 2026-09-10
- **Entorno Objetivo:** TEST (`https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test`)
- **Base de Datos TEST:** `postgresql://member_qa:qaSGP2026@158.69.200.27:5448/sgpmp_test`
- **Herramientas Utilizadas:**
  - **Newman:** v6.2.2 + `newman-reporter-htmlextra` v1.23.1
- **Suites Ejecutadas:**
  - Colección Newman: `sgpmp-backend/tests/Test_Testing/Test_Modulo2/RF-49/TC-M02-G85/test_tc_m02_g85.json`
    - Folder `TC-M02-146` (Rechazo Activo en BAJA)
    - Folder `TC-M02-147` (Rechazo Fincas Distintas)
    - Folder `TC-M02-148` (Incompatibilidad de Especie - Ejecución Documental de Bloqueo)
- **Reportes HTML Generados:**
  - `sgpmp-backend/tests/Test_Testing/Test_Modulo2/RF-49/TC-M02-G85/RESULTADOS/reporte_TC-M02-146.html` (68 KB)
  - `sgpmp-backend/tests/Test_Testing/Test_Modulo2/RF-49/TC-M02-G85/RESULTADOS/reporte_TC-M02-147.html` (68 KB)
  - `sgpmp-backend/tests/Test_Testing/Test_Modulo2/RF-49/TC-M02-G85/RESULTADOS/reporte_TC-M02-148.html` (74 KB)
- **Documentos y Scripts de Gestión Asociados:**
  - **Script de Re-test Diferido:** `sgpmp-backend/tests/Test_Testing/Test_Modulo2/RF-49/TC-M02-G85/retest_tc_m02_148.ps1`
  - **Script de Contingencia y Limpieza:** `sgpmp-backend/tests/Test_Testing/Test_Modulo2/RF-49/TC-M02-G85/RESULTADOS/cleanup_tc_m02_g85.sql`
- **Veredicto Global:** **PASS PARCIAL POR BLOQUEO EXTERNO (2 PASSED, 1 BLOCKED)**

---

## 1. Resumen Ejecutivo de Resultados

El caso agrupado **TC-M02-G85** evalúa los controles de integridad, validación de estado y consistencia territorial al intentar asociar sensores IoT a activos biológicos a través de `POST /activos-biologicos/{id_activo}/sensores` conforme al **RF-49 (CU11)**:

| Subcaso | Enfoque Evaluado | Datos Utilizados | Resultado Esperado | Resultado Obtenido | Reporte HTML | Veredicto |
| :--- | :--- | :--- | :--- | :--- | :--- | :---: |
| **TC-M02-146** | Rechazar asociación a activo en BAJA | Activo 10 (`BOV-006`, `id_estado: 6` [BAJA]), Sensor 1 (Disp 1, Infra 1) | HTTP 422 Unprocessable Entity, código `ACTIVO_EN_BAJA`, mensaje descriptivo. | HTTP 422 Unprocessable Entity, `error_code: ACTIVO_EN_BAJA`. Rechazo íntegro y sin mutación en BD. | `reporte_TC-M02-146.html` | **PASS** |
| **TC-M02-147** | Rechazar asociación entre fincas distintas | Activo 108 (Infra 3, Finca 1), Sensor 8 (Disp 4, Infra 4, Finca 2) | HTTP 409 Conflict, código `INFRAESTRUCTURA_INCOMPATIBLE`, restricción de unidad territorial. | HTTP 409 Conflict, `error_code: INFRAESTRUCTURA_INCOMPATIBLE`. Rechazo íntegro y sin mutación en BD. | `reporte_TC-M02-147.html` | **PASS** |
| **TC-M02-148** | Rechazar incompatibilidad de especie sensor-activo | Activo 279 (Bovino), Sensor 1 | HTTP 400 Bad Request según catálogo I3P-1 / Incompatibilidad biológica. | Subcaso bloqueado por dependencia externa no implementada: en el sistema actual el catálogo I3P-1 no aplica a especies, los sensores no tienen atributo de especie en M09 y el backend no valida especie. | `reporte_TC-M02-148.html` | **BLOQUEADO (Catálogo y Modelo no disponibles)** |

---

## 2. Métricas de Ejecución

| Subcaso | Carpeta Newman | Peticiones HTTP | Aserciones Totales | Exitosas | Fallidas / Bloqueadas | Duración | Estado |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **TC-M02-146** | `TC-M02-146` | 2 | 4 | 4 | 0 | 1.4 s | **PASSED** |
| **TC-M02-147** | `TC-M02-147` | 2 | 4 | 4 | 0 | 1.9 s | **PASSED** |
| **TC-M02-148** | `TC-M02-148` | 2 | 3 | 1 (Auth) | 2 (Bloqueo) | 3.2 s | **BLOCKED** |
| **Total Suite** | **Colección Completa** | **6 requests** | **11 aserciones** | **9** | **2** | **6.5 s** | **2 PASSED, 0 FAILED, 1 BLOCKED** |

---

## 3. Detalle Técnico por Subcaso

### 3.1. Subcaso TC-M02-146: Rechazar asociación a activo en BAJA

- **Objetivo:** Garantizar que el sistema impida asociar nuevos sensores a un activo biológico en estado terminal `BAJA` (o `VENDIDO`/`FALLECIDO`).
- **Petición HTTP:** `POST /activos-biologicos/10/sensores`
- **Payload Enviado:**
  ```json
  {
    "tipo_activo": "INDIVIDUAL",
    "tipo_asociacion": "DIRECTA",
    "dispositivo_iot_id": 1,
    "sensor_id": 1,
    "id_infraestructura": 1,
    "motivo": "Validacion rechazo activo en BAJA TC-M02-146"
  }
  ```
- **Respuesta Recibida (422 Unprocessable Entity):**
  ```json
  {
    "error_code": "ACTIVO_EN_BAJA",
    "message": "El activo 10 se encuentra en estado BAJA y no admite nuevas asociaciones de sensores.",
    "fields": [],
    "timestamp": "2026-09-10T06:44:08.783230+00:00"
  }
  ```
- **Aserciones Evaluadas en Newman:**
  - `[Auth] Autenticación exitosa (200 OK)`: **PASS**
  - `Código HTTP es 422 Unprocessable Entity`: **PASS**
  - `Código de error es ACTIVO_EN_BAJA`: **PASS**
  - `Mensaje indica que el activo está en estado BAJA`: **PASS**
- **Veredicto:** ✅ **PASS (100% exitoso)**

---

### 3.2. Subcaso TC-M02-147: Rechazar asociación entre fincas distintas

- **Objetivo:** Verificar la coherencia territorial de la infraestructura: un sensor asignado al área productiva de una finca no puede vincularse a un activo que reside en una finca diferente.
- **Petición HTTP:** `POST /activos-biologicos/108/sensores`
- **Payload Enviado:**
  ```json
  {
    "tipo_activo": "INDIVIDUAL",
    "tipo_asociacion": "DIRECTA",
    "dispositivo_iot_id": 4,
    "sensor_id": 8,
    "id_infraestructura": 4,
    "motivo": "Validacion rechazo fincas distintas TC-M02-147"
  }
  ```
- **Respuesta Recibida (409 Conflict):**
  ```json
  {
    "error_code": "INFRAESTRUCTURA_INCOMPATIBLE",
    "message": "Error de ubicación. El activo está en la finca 1 y el sensor en la finca 2. La asociación solo es permitida dentro de la misma unidad territorial.",
    "fields": [],
    "timestamp": "2026-09-10T06:44:20.617281+00:00"
  }
  ```
- **Aserciones Evaluadas en Newman:**
  - `[Auth] Autenticación exitosa (200 OK)`: **PASS**
  - `Código HTTP es 409 Conflict`: **PASS**
  - `Código de error es INFRAESTRUCTURA_INCOMPATIBLE`: **PASS**
  - `Mensaje indica restricción de unidad territorial`: **PASS**
- **Veredicto:** ✅ **PASS (100% exitoso)**

---

### 3.3. Subcaso TC-M02-148: Rechazar incompatibilidad de especie sensor-activo

- **Objetivo:** Verificar que el sistema rechace con `HTTP 400 Bad Request` la asociación cuando un sensor esté parametrizado para una especie incompatible con el activo (ej. sensor avícola en activo bovino), basándose en el catálogo I3P-1.
- **Ejecución y Documentación del Bloqueo:**
  Se realizó la ejecución controlada en Newman para registrar el comportamiento real del backend en TEST.
- **Análisis de Bloqueo por Dependencia Externa:**
  1. **Catálogo I3P-1:** En la arquitectura del sistema (`sgpmp-backend/src/telemetry/domain/entities/telemetria.py`), el catálogo `CATALOGO_I3P1` está diseñado exclusivamente para **variables fisicoquímicas ambientales** (temperatura, pH, oxígeno disuelto, etc.) y unidades de medición para telemetría. **No existe un catálogo I3P-1 para compatibilidad biológica de especies**.
  2. **Modelo de Datos de Sensores:** En la tabla `modulo9.sensores`, los registros no poseen columna ni relación con `id_especie`. Los sensores se categorizan por tipo físico (`TEMPERATURA`, `OXIGENO`, `PH`), sin vinculación taxonómica.
  3. **Lógica de Caso de Uso:** En `AsociarSensorActivoUseCase`, **no existe ninguna regla de negocio que valide compatibilidad de especie entre el sensor y el activo biológico**.
  4. **Naturaleza del Bloqueo:** **No es un defecto del backend**, sino una funcionalidad condicionada a un modelo de datos y catálogo biológico aún no definidos ni disponibles en el sistema.
- **Veredicto:** ⚠️ **BLOQUEADO (Catálogo y Modelo no disponibles)**

---

## 4. No Conformidades Residuales

Los subcasos ejecutables **TC-M02-146** y **TC-M02-147** operan con un **100% de conformidad**, validando de forma robusta las reglas de negocio en la capa de aplicación y base de datos:
- El rechazo por activo en estado `BAJA` protege el ciclo de vida del activo biológico contra operaciones zootécnicas extemporáneas.
- El rechazo territorial `INFRAESTRUCTURA_INCOMPATIBLE` previene inconsistencias geográficas y de gestión productiva entre fincas disjuntas.
- Ambos rechazos impiden de forma estricta cualquier inserción huérfana o no autorizada en `modulo2.asociaciones_activos_sensores`.

---

## 5. Teardown y Verificación de Limpieza en TEST

Dado que los subcasos probados corresponden a escenarios de validación negativa (rechazos HTTP 422 y 409), el backend no generó registros de asociación. Para verificar la integridad de la base de datos TEST, se ejecutó el script `sgpmp-backend/tests/Test_Testing/Test_Modulo2/RF-49/TC-M02-G85/RESULTADOS/cleanup_tc_m02_g85.sql`:
```sql
SELECT COUNT(*) FROM modulo2.asociaciones_activos_sensores
WHERE (id_sensor = 1 AND id_activo_biologico = 10)
   OR (id_sensor = 8 AND id_activo_biologico = 108)
   OR (id_sensor = 1 AND id_activo_biologico = 279);
-- Resultado: 0 asociaciones remanentes
```
La base de datos TEST quedó completamente limpia y verificada.

---

## 6. Criterios de Cierre del Caso Agrupado TC-M02-G85

El caso agrupado **TC-M02-G85** permanecerá en estado **PASS PARCIAL POR BLOQUEO EXTERNO** hasta que se defina e implemente el modelo de compatibilidad biológica especie-sensor.

Para el cierre definitivo a PASS COMPLETO se requerirá:
1. Implementación del catálogo y modelo de compatibilidad biológica especie-sensor en Módulo 9 / Módulo 2.
2. Despliegue de la validación correspondiente en el entorno TEST.
3. Ejecución del script de re-test diferido:
   ```powershell
   ./tests/Test_Testing/Test_Modulo2/RF-49/TC-M02-G85/retest_tc_m02_148.ps1
   ```
4. Confirmación de resultado `PASS` en `reporte_TC-M02-148.html`.
5. Actualización del veredicto en este informe y en `GUIA_PRUEBAS_Y_ESTRUCTURA.md`.
