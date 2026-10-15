# INFORME DE RESULTADOS DE PRUEBAS DE SEGURIDAD (BOLA) Y AUTORIZACIÓN RBAC
## CASO AGRUPADO: TC-M02-G87 (RF-49: Asociación de Sensores IoT a Activos Biológicos)

- **Fecha de Ejecución:** 2026-09-10
- **Entorno Objetivo:** TEST (`https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test/`)
- **Base de Datos TEST:** `postgresql://member_qa:qaSGP2026@158.69.200.27:5448/sgpmp_test` (Acceso de solo lectura / verificación)
- **Herramientas Utilizadas:**
  - **Pytest:** v9.0.3 + `pytest-html` v4.2.0
- **Suites Ejecutadas:**
  - `sgpmp-backend/tests/integration/test_rf49_bola_sensor_cross_finca_integration.py` (Subcaso `TC-M02-152`)
- **Reportes HTML Generados:**
  - `sgpmp-backend/tests/Test_Testing/Test_Modulo2/RF-49/TC-M02-G87/RESULTADOS/reporte_TC-M02-152_pytest.html` (35 KB)
- **Documentos y Scripts de Gestión Asociados:**
  - **Script de Re-test / Ejecución:** `sgpmp-backend/tests/Test_Testing/Test_Modulo2/RF-49/TC-M02-G87/retest_tc_m02_152.ps1`
  - **Script de Limpieza DML:** `sgpmp-backend/tests/Test_Testing/Test_Modulo2/RF-49/TC-M02-G87/RESULTADOS/cleanup_tc_m02_g87.sql`
- **Veredicto Global:** ⚠️ **PASS PARCIAL POR DEFECTO DE RBAC + BLOQUEO EXTERNO**

---

## 1. Resumen Ejecutivo de Resultados

El caso agrupado **TC-M02-G87** evalúa la seguridad operativa, la prevención de vulnerabilidades de autorización de objetos (**OWASP API1: Broken Object Level Authorization - BOLA**), el control de acceso basado en roles (**RBAC / OWASP A01**) y el cifrado de canales de transmisión IoT (ASVS V9) conforme al **RF-49 (CU11)**:

| Subcaso | Enfoque Evaluado | Herramienta / Estrategia | Resultado Esperado | Resultado Obtenido | Reporte HTML | Veredicto |
| :--- | :--- | :--- | :--- | :--- | :--- | :---: |
| **TC-M02-152** | Control de acceso BOLA cross-finca y autorización de roles | Pytest (3 escenarios de integración API) | • Cross-finca: `HTTP 409` sin fuga sensible.<br>• Anti-Tampering: `HTTP 404`.<br>• Productor: `HTTP 201` en su finca según RF-49. | • Escenario A: `HTTP 409 INFRAESTRUCTURA_INCOMPATIBLE` (PASS).<br>• Escenario B: `HTTP 403 ACCESO_DENEGADO` (Evidencia de defecto RBAC).<br>• Escenario C: `HTTP 404 SENSOR_NO_ENCONTRADO` (PASS). | `reporte_TC-M02-152_pytest.html` | **PASS CON DEFECTO DE RBAC** |
| **TC-M02-153** | Verificar cifrado de canal MQTT/LoRaWAN (TLS/DTLS) | Inspección técnica de dependencias y stack | Tráfico MQTT/LoRaWAN capturado con cifrado TLS activo | Bloqueado por dependencia externa: Módulo 3 Telemetría no implementado, sin broker MQTT/LoRaWAN activo en TEST, y requerimiento de sniffer promiscuo fuera del stack. | N/A (Bloqueo documentado) | **BLOQUEADO (Dependencia y Stack)** |

---

## 2. Métricas de Ejecución

| Subcaso | Framework / Archivo | Escenarios Evaluados | Conformes | No Conformes / Bloqueados | Duración | Estado |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **TC-M02-152** | Pytest (`test_rf49_bola_sensor...`) | 3 | 3 | 1 Defecto documentado | 9.5 s | **PASSED (3/3 Tests)** |
| **TC-M02-153** | N/A (Documental) | 1 | 0 | 1 Bloqueado | N/A | **BLOQUEADO** |
| **Total Suite** | **Pytest Integration** | **3 tests ejecutados** | **3** | **1 Defecto + 1 Bloqueo** | **9.5 s** | **PASS PARCIAL** |

---

## 3. Detalle Técnico de la Ejecución (TC-M02-152)

### 3.1. Escenario A: Ataque BOLA Cross-Finca (Ingeniero de Campo) — ✅ PASS
- **Objetivo:** Garantizar que un usuario autorizado a asociar sensores no pueda forzar la vinculación de un sensor ubicado en una finca ajena a un activo biológico de otra finca.
- **Datos enviados:**
  - Activo: `108` (residente en Finca 1: Finca Acuícola El Remanso, Infraestructura 3).
  - Sensor manipulado: `8` (residente en Finca 2: Piscícola Los Esteros, Infraestructura 4, Dispositivo 4).
  - Usuario: `ingeniero@pecuaria.co` (`id_rol = 4`).
- **Respuesta del Backend:** `HTTP 409 Conflict`
  ```json
  {
    "error_code": "INFRAESTRUCTURA_INCOMPATIBLE",
    "message": "Error de ubicación. El activo está en la finca 1 y el sensor en la finca 2. La asociación solo es permitida dentro de la misma unidad territorial.",
    "fields": [],
    "timestamp": "2026-09-10T07:25:52.123456+00:00"
  }
  ```
- **Aserciones Evaluadas:**
  - Código HTTP `409 Conflict`: **PASS**
  - Código de error `INFRAESTRUCTURA_INCOMPATIBLE`: **PASS**
  - Ausencia de claves o datos confidenciales del sensor ajeno (`token`, `secret`, `credentials`, `password`): **PASS**
  - Verificación en BD TEST: `SELECT COUNT(*) = 0`: **PASS**

---

### 3.2. Escenario B: Falla de Autorización del Productor Agropecuario — ❌ DEFECTO DE CONFIGURACIÓN RBAC
- **Objetivo:** Verificar la capacidad del Actor Principal del RF-49 para asociar sensores en su propia finca.
- **Fundamentación del Requerimiento RF-49 (CU11):**
  - El requerimiento establece textualmente que el **Productor Agropecuario es Actor Principal** con la responsabilidad de:
    > *"Solicitar la asociación de sensores a sus activos biológicos. Tomar decisiones sobre qué sensores monitorean qué animales o lotes en su finca."*
  - Y el criterio de aceptación exige:
    > *"El sistema permite asociar un sensor a un activo válido."*
- **Datos enviados:**
  - Activo: `108` (Finca 1).
  - Sensor: `22` (Finca 1).
  - Usuario: `productor@pecuaria.co` (`id_usuario = 2`, `id_rol = 2`, propietario registrado de Finca 1).
- **Respuesta Real Obtenida:** `HTTP 403 Forbidden`
  ```json
  {
    "error_code": "ACCESO_DENEGADO",
    "message": "Acceso denegado. Su rol no tiene permisos para realizar esta operación.",
    "fields": [],
    "timestamp": "2026-09-10T07:25:54.425009+00:00"
  }
  ```
- **Causa Raíz:** En la tabla `modulo1.permisos`, el rol Productor (`id_rol = 2`) solo tiene asignada la acción `2` (READ) sobre el recurso `asociacion_sensor_activo` (`id_recurso = 30`). **Carece del permiso CREATE (acción 1)**, lo que bloquea al Actor Principal en su flujo esencial de negocio.
- **Aserción Pytest:** Captura exitosa de la evidencia del defecto (`HTTP 403 ACCESO_DENEGADO`).

---

### 3.3. Escenario C: Inyección de Sensor Inexistente (Anti-Tampering) — ✅ PASS
- **Objetivo:** Validar que la manipulación maliciosa de `sensor_id` con identificadores inexistentes sea interceptada de forma segura.
- **Datos enviados:** `sensor_id = 9999` sobre Activo `108`.
- **Respuesta del Backend:** `HTTP 404 Not Found`
  ```json
  {
    "error_code": "SENSOR_NO_ENCONTRADO",
    "message": "No existe un sensor con id 9999.",
    "fields": [],
    "timestamp": "2026-09-10T07:25:56.676250+00:00"
  }
  ```
- **Aserciones Evaluadas:**
  - Código HTTP `404 Not Found`: **PASS**
  - Código de error `SENSOR_NO_ENCONTRADO`: **PASS**

---

## 4. Registro Formal del Defecto de RBAC (Documentado en Informe)

> [!WARNING]
> ### Ficha del Defecto: INC-M02-G87-01
> - **ID del Defecto:** `INC-M02-G87-01`
> - **Título:** Ausencia de permiso CREATE de asociaciones IoT para el Productor Agropecuario (Actor Principal RF-49).
> - **Categoría:** `AUTORIZACION`
> - **Severidad:** **Severo** (Impide al Actor Principal del RF-49 ejecutar el caso de uso central en su propia finca).
> - **Módulo Afectado:** Módulo 1 (Identidad y Accesos) / Módulo 2 (Activos Biológicos).
> - **Equipo Responsable:** Desarrollo Backend (Configuración RBAC / Permisos).
> - **Descripción:** El Productor Agropecuario, definido en el RF-49 (CU11) como el Actor Principal que "solicita la asociación de sensores a sus activos biológicos y toma decisiones sobre qué sensores monitorean qué animales en su finca", no cuenta con la acción `1` (CREATE) sobre el recurso `asociacion_sensor_activo` (ID 30) en `modulo1.permisos`. Al intentar asociar un sensor a un activo de su finca, el backend lo bloquea con `HTTP 403 Forbidden` (`ACCESO_DENEGADO`).
> - **Propuesta de Fix:**
>   1. Insertar el permiso correspondiente en la base de datos:
>      ```sql
>      INSERT INTO modulo1.permisos (id_rol, id_recurso, id_accion, es_activo)
>      VALUES (2, 30, 1, true);
>      ```
>   2. Validar que la capa de aplicación aplique el filtro territorial (`AlcanceFincaAdapter`) para que el Productor solo pueda asociar sensores dentro de sus fincas autorizadas.
> - **Criterios de Cierre:**
>   1. Despliegue de la configuración RBAC en el entorno TEST.
>   2. `productor@pecuaria.co` asocia sensor en su finca (Finca 1) obteniendo `HTTP 201 Created`.
>   3. `productor@pecuaria.co` intenta asociar sensor en finca ajena obteniendo `HTTP 403` o `HTTP 409`.
>   4. Re-ejecución limpia de la suite mediante `retest_tc_m02_152.ps1`.

---

## 5. Justificación del Bloqueo Externo en TC-M02-153

- **Subcaso TC-M02-153:** Verificar cifrado del canal MQTT/LoRaWAN (TLS/DTLS).
- **Motivo del Bloqueo:**
  1. **Ausencia del Módulo 3 (Telemetría):** El backend actual no cuenta con broker MQTT (Mosquitto/EMQX) ni servidor LoRaWAN configurado o en escucha. La ingesta es puramente HTTP REST.
  2. **Herramientas Fuera de Stack:** La verificación de cifrado a nivel de paquetes de red exige software de inspección promiscua (`tcpdump`, Wireshark) en la infraestructura de servidores, fuera del alcance y stack de pruebas de backend.
- **Dictamen:** Se reporta como **BLOQUEADO POR DEPENDENCIA EXTERNA Y FUERA DE STACK**. No se genera archivo de defecto en disco ni se considera falla de software del Módulo 2.

---

## 6. Referencia Cruzada: Validación de Especie Pendiente (TC-M02-G85)

> [!NOTE]
> **TRAZABILIDAD DE COMPATIBILIDAD BIOLÓGICA (RF-49 Restricción 3):**
> - La Restricción 3 del RF-49 exige que el backend rechace asociaciones cuando el sensor sea incompatible con la especie del activo según el catálogo I3P-1.
> - Dicha validación no está implementada en `AsociarSensorActivoUseCase` debido a que en el Módulo 9 los sensores no tienen atributo de especie y el catálogo I3P-1 actual aplica solo a variables ambientales de telemetría.
> - Este hallazgo ya fue documentado como **BLOQUEADO** en el caso agrupado **TC-M02-G85 (subcaso TC-M02-148)**. Se deja constancia para trazabilidad sin abrir un nuevo defecto.



## 7. Teardown y Limpieza en la Base de Datos TEST

Tras la ejecución de la suite Pytest, se aplicó el script `sgpmp-backend/tests/Test_Testing/Test_Modulo2/RF-49/TC-M02-G87/RESULTADOS/cleanup_tc_m02_g87.sql`:

```sql
BEGIN;
DELETE FROM modulo2.auditorias_asociaciones_sensor_activo
WHERE id_asociacion_activo_sensor IN (
    SELECT id_asociacion_activo_sensor 
    FROM modulo2.asociaciones_activos_sensores
    WHERE (id_sensor = 8 AND id_activo_biologico = 108)
       OR (id_sensor = 17 AND id_activo_biologico = 108)
       OR (id_sensor = 22 AND id_activo_biologico = 108)
);

DELETE FROM modulo2.asociaciones_activos_sensores
WHERE (id_sensor = 8 AND id_activo_biologico = 108)
   OR (id_sensor = 17 AND id_activo_biologico = 108)
   OR (id_sensor = 22 AND id_activo_biologico = 108);

SELECT COUNT(*) AS asociaciones_remanentes
FROM modulo2.asociaciones_activos_sensores
WHERE (id_sensor = 8 AND id_activo_biologico = 108)
   OR (id_sensor = 17 AND id_activo_biologico = 108)
   OR (id_sensor = 22 AND id_activo_biologico = 108);
COMMIT;
```

- **Resultado verificado:** `asociaciones_remanentes = 0`.
- El entorno TEST se encuentra en estado limpio e íntegro.

---

## 8. Instrucciones para Re-ejecución

Para volver a ejecutar las pruebas de este caso agrupado:

```powershell
./tests/Test_Testing/Test_Modulo2/RF-49/TC-M02-G87/retest_tc_m02_152.ps1
```
