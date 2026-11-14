# INFORME DE RESULTADOS DE PRUEBAS DE INTEGRIDAD Y TRANSACCIONALIDAD DE ASOCIACIONES
## CASO AGRUPADO: TC-M02-G86 (RF-49: Asociación de Sensores IoT a Activos Biológicos)

- **Fecha de Ejecución:** 2026-09-10
- **Entorno Objetivo:** TEST (`https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test`)
- **Base de Datos TEST:** `postgresql://member_qa:qaSGP2026@158.69.200.27:5448/sgpmp_test` (Acceso de solo lectura / verificación)
- **Herramientas Utilizadas:**
  - **Newman:** v6.2.2 + `newman-reporter-htmlextra` v1.23.1
  - **Pytest:** v9.0.3 + `pytest-html` v4.2.0 (Monkeypatch in-process)
- **Suites Ejecutadas:**
  - Newman: `sgpmp-backend/tests/Test_Testing/Test_Modulo2/RF-49/TC-M02-G86/test_tc_m02_g86.json` (Folder `TC-M02-149`)
  - Pytest: `sgpmp-backend/tests/integration/test_rf49_reversion_auditoria_integration.py` (Caso `TC-M02-151`)
- **Reportes HTML Generados:**
  - `sgpmp-backend/tests/Test_Testing/Test_Modulo2/RF-49/TC-M02-G86/RESULTADOS/reporte_TC-M02-149.html` (88 KB)
  - `sgpmp-backend/tests/Test_Testing/Test_Modulo2/RF-49/TC-M02-G86/RESULTADOS/reporte_TC-M02-151_pytest.html` (34 KB)
- **Documentos y Scripts de Gestión Asociados:**
  - **Script de Re-test / Ejecución:** `sgpmp-backend/tests/Test_Testing/Test_Modulo2/RF-49/TC-M02-G86/retest_tc_m02_151.ps1`
  - **Script de Limpieza DML:** `sgpmp-backend/tests/Test_Testing/Test_Modulo2/RF-49/TC-M02-G86/RESULTADOS/cleanup_tc_m02_g86.sql`
- **Veredicto Global:** ✅ **PASS COMPLETO (2/2)**

---

## 1. Resumen Ejecutivo de Resultados

El caso agrupado **TC-M02-G86** evalúa los mecanismos de exclusividad operativa y la garantía de atomicidad transaccional con reversión estricta (rollback) en la asociación de sensores IoT a activos biológicos conforme al **RF-49 (CU11)**:

| Subcaso | Enfoque Evaluado | Estrategia / Herramienta | Datos de Prueba | Resultado Esperado | Resultado Obtenido | Reporte HTML | Veredicto |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :---: |
| **TC-M02-149** | Rechazar asociación DIRECTA si el sensor ya está activo en otro animal | Newman (API REST) | Sensor 22 (Disp 38, Infra 3), Activo A: 108, Activo B: 109 | HTTP 409 Conflict, código `SENSOR_YA_VINCULADO`, asociación duplicada rechazada | HTTP 409 Conflict, `error_code: SENSOR_YA_VINCULADO`. Sensor mantenido exclusivo. | `reporte_TC-M02-149.html` | **PASS** |
| **TC-M02-151** | Reversión completa (Rollback) ante fallo de auditoría obligatoria | Pytest (In-process monkeypatch) | Activo 108, Sensor 22 (Disp 38, Infra 3), Usuario 1 | Excepción propagada, sesión SQLAlchemy revertida, 0 filas persistidas en BD | `RuntimeError` capturado en `registrar_auditoria`, rollback ejecutado, `SELECT COUNT(*) = 0` | `reporte_TC-M02-151_pytest.html` | **PASS** |

---

## 2. Métricas de Ejecución

| Subcaso | Suite / Framework | Peticiones / Aserciones | Exitosas | Fallidas | Duración | Estado |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **TC-M02-149** | Newman (`TC-M02-149`) | 3 requests / 6 aserciones | 6 | 0 | 2.5 s | **PASSED** |
| **TC-M02-151** | Pytest (`test_tc_m02_151...`) | 1 test / 4 aserciones internas | 4 | 0 | 6.4 s | **PASSED** |
| **Total Suite** | **Newman + Pytest** | **10 aserciones evaluadas** | **10** | **0** | **8.9 s** | **PASS COMPLETO (2/2)** |

---

## 3. Detalle Técnico por Subcaso

### 3.1. Subcaso TC-M02-149: Rechazo de Exclusividad en Tipo DIRECTA

- **Objetivo:** Garantizar que un sensor IoT físico (`tipo_asociacion: DIRECTA`) no pueda vincularse a un segundo activo biológico si ya mantiene un vínculo activo con otro activo.
- **Flujo Ejecutado (Newman):**
  1. `00 - Autenticación Admin`: Obtención de Bearer Token JWT para `admin@pecuaria.co` (`200 OK`).
  2. `01 - Setup Asociación Inicial`: Asociación exitosa de Sensor 22 al Activo 108 (`201 Created`).
  3. `02 - Intento de Vinculación Duplicada`: Intento de asociar el mismo Sensor 22 al Activo 109 con `tipo_asociacion: DIRECTA`.
- **Payload del Intento Duplicado:**
  ```json
  {
    "tipo_activo": "INDIVIDUAL",
    "tipo_asociacion": "DIRECTA",
    "dispositivo_iot_id": 38,
    "sensor_id": 22,
    "id_infraestructura": 3,
    "motivo": "Intento de asociacion duplicada sensor DIRECTA TC-M02-149"
  }
  ```
- **Respuesta Recibida (409 Conflict):**
  ```json
  {
    "error_code": "SENSOR_YA_VINCULADO",
    "message": "El sensor 22 ya se encuentra asociado activamente a otro activo biológico (ID 108).",
    "fields": [],
    "timestamp": "2026-09-10T06:55:07.123456+00:00"
  }
  ```
- **Aserciones Evaluadas en Newman:**
  - `[Setup] Código HTTP es 201 Created`: **PASS**
  - `[Setup] Asociación retornada está ACTIVA`: **PASS**
  - `[Setup] Sensor ID coincide con el solicitado`: **PASS**
  - `Código HTTP es 409 Conflict`: **PASS**
  - `Código de error es SENSOR_YA_VINCULADO`: **PASS**
  - `Mensaje indica que el sensor ya está asociado a otro activo`: **PASS**
- **Veredicto:** ✅ **PASS (100% exitoso)**

---

### 3.2. Subcaso TC-M02-151: Reversión Transaccional (Rollback) ante Fallo de Auditoría Obligatoria

- **Objetivo:** Demostrar que si la operación obligatoria de auditoría falla, la transacción de base de datos se revierte completamente (rollback), impidiendo que la asociación quede registrada o huérfana en la base de datos.
- **Estrategia Implementada:**
  - Se utilizó **Pytest con monkeypatch in-process** sobre el método `registrar_auditoria` de `SqlAlchemyAsociacionSensorActivoRepository`.
  - Esta estrategia simula fielmente la caída o error del subsistema de auditoría sin necesidad de tocar la base de datos con triggers, funciones ni privilegios DBA.
- **Evidencia del Rollback Transaccional:**
  1. **Inyección y Captura de Excepción:**
     ```python
     def mock_registrar_auditoria_falla(*args, **kwargs):
         raise RuntimeError("SIMULATED_AUDIT_FAILURE_FOR_ROLLBACK_TEST: Servicio de auditoría no disponible.")
     ```
  2. **Payload de la Excepción Capturada:**
     - **Tipo:** `RuntimeError`
     - **Mensaje:** `SIMULATED_AUDIT_FAILURE_FOR_ROLLBACK_TEST: Servicio de auditoría no disponible.`
     - **Aserción Pytest:** `assert "SIMULATED_AUDIT_FAILURE_FOR_ROLLBACK_TEST" in str(exc_info.value)` → **PASS**.
  3. **Comportamiento del Caso de Uso (`AsociarSensorActivoUseCase`):**
     - El bloque `try / except` captura la falla de auditoría, ejecuta explícitamente `self.db.rollback()` y re-propaga la excepción.
  4. **Verificación de Base de Datos (Solo Lectura):**
     - Consulta ejecutada tras la excepción:
       ```sql
       SELECT COUNT(*) FROM modulo2.asociaciones_activos_sensores 
       WHERE id_sensor = 22 AND id_activo_biologico = 108;
       ```
     - **Resultado Obtenido:** `0`
     - **Aserción Pytest:** `assert count_final == 0` → **PASS**.
- **Veredicto:** ✅ **PASS (100% exitoso, atomicidad y rollback verificados)**

---

## 4. Confirmación Explícita de Política de Integridad de la Base de Datos TEST

> [!IMPORTANT]
> **CERTIFICACIÓN DE NO MODIFICACIÓN ESTRUCTURAL:**
> - ❌ **NO se crearon triggers** (ni permanentes ni temporales).
> - ❌ **NO se crearon funciones en PostgreSQL**.
> - ❌ **NO se ejecutó ninguna sentencia DDL** (`CREATE`, `ALTER`, `DROP`, `TRUNCATE`).
> - ❌ **NO se requirieron ni utilizaron permisos de DBA** (usuario utilizado: `member_qa` con privilegios mínimos).
> - ✅ Todas las validaciones de persistencia se realizaron mediante operaciones DML autorizadas (`DELETE` de datos temporales) y consultas de solo lectura (`SELECT`).

---

## 5. Limpieza y Estado Final de la Base de Datos TEST

Tras la ejecución de TC-M02-149, se aplicó el script de contingencia y limpieza DML `sgpmp-backend/tests/Test_Testing/Test_Modulo2/RF-49/TC-M02-G86/RESULTADOS/cleanup_tc_m02_g86.sql`:

```sql
BEGIN;
DELETE FROM modulo2.auditorias_asociaciones_sensor_activo
WHERE id_asociacion_activo_sensor IN (
    SELECT id_asociacion_activo_sensor 
    FROM modulo2.asociaciones_activos_sensores
    WHERE id_sensor = 22 AND id_activo_biologico IN (108, 109)
);

DELETE FROM modulo2.asociaciones_activos_sensores
WHERE id_sensor = 22 AND id_activo_biologico IN (108, 109);

SELECT COUNT(*) AS asociaciones_remanentes
FROM modulo2.asociaciones_activos_sensores
WHERE id_sensor = 22 AND id_activo_biologico IN (108, 109);
COMMIT;
```

- **Resultado de verificación:** `asociaciones_remanentes = 0`.
- El entorno TEST se encuentra en estado limpio e íntegro.

---

## 6. Instrucciones para Re-ejecución

Para volver a ejecutar las pruebas de este caso agrupado:

1. **Re-ejecución de TC-M02-149 (Newman):**
   ```powershell
   npx newman run tests/Test_Testing/Test_Modulo2/RF-49/TC-M02-G86/test_tc_m02_g86.json `
     --folder "TC-M02-149" `
     -r cli,htmlextra `
     --reporter-htmlextra-export tests/Test_Testing/Test_Modulo2/RF-49/TC-M02-G86/RESULTADOS/reporte_TC-M02-149.html `
     --reporter-htmlextra-title "Reporte TC-M02-149 - Exclusividad Sensor DIRECTA"
   ```

2. **Re-ejecución de TC-M02-151 (Pytest):**
   ```powershell
   ./tests/Test_Testing/Test_Modulo2/RF-49/TC-M02-G86/retest_tc_m02_151.ps1
   ```
