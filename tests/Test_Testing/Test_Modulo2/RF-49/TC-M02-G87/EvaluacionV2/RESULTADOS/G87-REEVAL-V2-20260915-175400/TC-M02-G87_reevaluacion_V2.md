# Reevaluación V2 — Caso TC-M02-G87 — RF-49 CU11
## Estado del Fix RBAC (INC-M02-62-G87) y Verificación del Gap BOLA Sistémico (INC-M02-71-G48)

---

## 1. Encabezado y Metadatos de Ejecución

- **Título:** Reevaluación V2 — Caso Agrupado TC-M02-G87 — RF-49 CU11 (*Seguridad BOLA, Autorización RBAC del Productor y Cifrado IoT*)
- **RUN_ID:** `G87-REEVAL-V2-20260915-175400`
- **Fechas de Evaluación:**
  - **V1 (Original):** 2026-09-10
  - **V2 (Reevaluación actual):** 2026-09-15
- **Entorno de Pruebas:** **TEST** (`https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test`)
- **Base de Datos:** PostgreSQL 16 remoto (`158.69.200.27:5448/sgpmp_test`, usuario `member_qa`)
- **Herramientas de Ejecución:** Pytest 9.0.3, pytest-html 4.2.0, Python 3.13.9, psycopg2 / SQLAlchemy
- **Suite Ejecutada:** `tests/integration/test_rf49_bola_sensor_cross_finca_integration.py`
- **Reporte HTML Generado:** [reporte_TC-M02-152_pytest.html](./reporte_TC-M02-152_pytest.html)
- **Veredicto Global V2:** **RECHAZADO (PERSISTE DEFECTO RBAC EN TEST; BLOQUEO PERMANENTE FUERA DE STACK PARA CIFRADO IoT)**

> **Nota de consolidación:** Esta reevaluación V2 tuvo dos ejecuciones internas (2026-09-15). Por aplicación de la regla del .md único (ver testing/ESTANDAR-CASOS-Y-REPORTES.md, sección 5.1), los artefactos se consolidaron bajo un único RUN_ID (`G87-REEVAL-V2-20260915-175400`), conservando la corrida más reciente como fuente canónica.

---

## 2. Objetivo de la Reevaluación y Resumen Ejecutivo

### 2.1 Contexto V1 y Hallazgos Previos
En la corrida V1, el caso agrupado **TC-M02-G87** arrojó un estado disyuntivo:
1. **TC-M02-152:** Clasificado en `PASS CON DEFECTO RBAC` documentado bajo el ticket `INC-M02-62-G87`. El Productor Agropecuario (`id_rol=2`), siendo el Actor Principal definido formalmente en el RF-49 (CU11), no podía asociar sensores a sus activos biológicos porque carecía del permiso `CREATE` (`id_accion=1`) sobre el recurso `asociacion_sensor_activo` (`id_recurso=30`).
2. **TC-M02-153:** Clasificado como `BLOQUEADO FUERA DE STACK`. La validación del cifrado TLS/AES en brokers IoT MQTT/LoRaWAN requiere analizadores físicos de paquetes de red (Wireshark/sniffer), herramientas ajenas al alcance del stack QA backend/API REST.

### 2.2 Contexto V2 y Notificación del Equipo de Desarrollo
El equipo de desarrollo notificó haber aplicado un fix manual ("Paso 0") insertando el permiso `prod_crear_asociacion_sensor_activo` en sus entornos locales `sgpmp` y `pruebas`. Adicionalmente, el propio equipo reconoció un gap arquitectónico sistémico documentado como **INC-M02-71-G48 (issue #221)**: *los use cases de escritura del Módulo 2 no validan alcance por finca (`AlcanceFincaAdapter`)*, lo cual implica que una vez que el Productor posea permisos para crear asociaciones, podría potencialmente asociar sensores en activos de fincas ajenas (fallo de autorización BOLA).

### 2.3 Resumen de Hallazgos en V2
1. **Estado del Fix RBAC en TEST:** El fix RBAC **NO está aplicado en TEST**. El Productor sigue recibiendo `HTTP 403 Forbidden` (`ACCESO_DENEGADO`). La fila `(id_rol=2, id_recurso=30, id_accion=1)` **no existe** en `modulo1.permisos` de `sgpmp_test`.
2. **Causa del desfasaje:** El fix nunca fue formalizado como una migración en `alembic/versions/`. Por tanto, el script manual aplicado en desarrollo local no llegó a la base de datos de TEST.
3. **Impacto sobre BOLA (INC-M02-71-G48):** Dado que la compuerta RBAC rechaza con `403` al Productor antes de ingresar a la lógica del caso de uso, el ataque BOLA por parte del Productor se encuentra **enmascarado / bloqueado en tiempo de ejecución**, pero **latente en la arquitectura del código fuente**.
4. **TC-M02-153:** Se formaliza el cierre como **bloqueo permanente fuera de stack QA**.

### 2.4 Tabla Comparativa de Resultados
| Sub-caso | Enfoque / Técnica | Comportamiento Esperado | Obtenido V2 | Veredicto V2 |
| :--- | :--- | :---: | :---: | :---: |
| **TC-M02-152 (Escenario A)** | BOLA cross-finca (Ingeniero de Campo) | `HTTP 409 INFRAESTRUCTURA_INCOMPATIBLE` | `HTTP 409` | ✅ **PASS** |
| **TC-M02-152 (Escenario B)** | Productor crea asociación en su finca | `HTTP 403` (Captura defecto V1) | `HTTP 403 ACCESO_DENEGADO` | ⚠️ **PASS CON DEFECTO RBAC PERSISTENTE** |
| **TC-M02-152 (Escenario B ext.)** | Productor crea en finca ajena (BOLA) | `HTTP 403` / `HTTP 409` | `HTTP 403 ACCESO_DENEGADO` | ⚠️ **BLOQUEADO POR RBAC (BOLA LATENTE)** |
| **TC-M02-152 (Escenario C)** | Anti-tampering (Sensor inexistente 9999) | `HTTP 404 SENSOR_NO_ENCONTRADO` | `HTTP 404` | ✅ **PASS** |
| **TC-M02-153** | Cifrado canal IoT MQTT / LoRaWAN | Inspección TLS / Paquetes cifrados | — | 🔒 **BLOQUEO PERMANENTE FUERA DE STACK** |

---

## 3. Estado Previo (Pre-condición vía API REST)

Se ejecutó la validación estricta de precondiciones contra la API REST del entorno TEST, volcando los resultados en `precondicion_api.log` y `verificacion_rbac.log`:

```text
=== PRECONDICIONES GENERALES REGISTRADAS EN precondicion_api.log ===
Target baseUrl: https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test
1. Autenticación admin: OK (HTTP 200).
2. GET /activos-biologicos/108 -> HTTP 200:
   - ID: 108 (LOTE-M02-TEST-001)
   - Estado: ACTIVO
   - id_infraestructura: 3 (Estanque Principal - Finca 1: El Remanso)
   - id_finca: 1
3. GET /configuracion/dispositivos-iot/38 -> HTTP 200:
   - Dispositivo 38 / Sensor 22 asignados a Infraestructura 3 (Finca 1)
4. GET /configuracion/dispositivos-iot/4 -> HTTP 200:
   - Dispositivo 4 / Sensor 8 asignados a Infraestructura 4 (Finca 2: Los Esteros)
```

```text
=== VERIFICACIÓN RBAC REGISTRADA EN verificacion_rbac.log ===
1. Login Productor: POST /sesiones/ con productor@pecuaria.co -> HTTP 200 (Token JWT emitido).
2. Identidad Productor: GET /usuarios/me -> HTTP 200:
   - id_usuario: 2
   - Nombre: Laura Gómez Torres
   - Rol: Productor Agropecuario (id_rol = 2)
3. Intento de crear asociación en activo 108 (Finca 1 - Propia):
   - POST /activos-biologicos/108/sensores
   - Payload: {"tipo_activo": "INDIVIDUAL", "tipo_asociacion": "DIRECTA", "dispositivo_iot_id": 38, "sensor_id": 22, "id_infraestructura": 3, "motivo": "Verificacion RBAC Productor TC-M02-152 corrida V2"}
   - Respuesta HTTP: 403 Forbidden
   - Body: {"error_code": "ACCESO_DENEGADO", "message": "Acceso denegado. Su rol no tiene permisos para realizar esta operación.", "fields": [], "timestamp": "..."}
   - DIAGNÓSTICO: Fix RBAC NO APLICADO en TEST. Defecto INC-M02-62-G87 PERSISTE.
4. Verificación en BD TEST (PostgreSQL 158.69.200.27:5448):
   - Consulta: SELECT id_permiso, id_rol, id_recurso, id_accion FROM modulo1.permisos WHERE id_rol=2 AND id_recurso=30 AND id_accion=1;
   - Resultado: 0 filas encontradas. Permiso ausente en BD.
```

---

## 4. Resultados Detallados (Pytest + Verificaciones API)

### 4.1 Métricas Globales de Pytest
- **Total de pruebas ejecutadas:** 3
- **Pruebas aprobadas (Passed):** 3
- **Pruebas fallidas (Failed):** 0
- **Tiempo de ejecución:** 6.58 segundos
- **Exit Code:** `0`

### 4.2 Desglose por Escenario de Prueba
| Escenario Pytest | Propósito de Seguridad | Código Esperado | Código Obtenido | Resultado |
| :--- | :--- | :---: | :---: | :---: |
| `test_tc_m02_152_escenario_a_bola_cross_finca_ingeniero` | Verificar que un Ingeniero (con permiso CREATE) no pueda asociar un sensor de Finca 2 (Sensor 8) a un activo de Finca 1 (Activo 108). | `HTTP 409` | `HTTP 409` | ✅ **PASSED** |
| `test_tc_m02_152_escenario_b_productor_defecto_rbac` | Capturar la evidencia ineludible del defecto RBAC: el Productor recibe 403 al carecer de permisos CREATE sobre recurso 30. | `HTTP 403` | `HTTP 403` | ✅ **PASSED (Captura Defecto)** |
| `test_tc_m02_152_escenario_c_anti_tampering_sensor_inexistente` | Verificar protección anti-manipulación inyectando sensor inexistente (ID 9999). | `HTTP 404` | `HTTP 404` | ✅ **PASSED** |

### 4.3 Cita Textual de Aserciones Relevantes
- **Escenario A (BOLA Ingeniero):**
  ```python
  assert resp.status_code == 409, f"Se esperaba 409 Conflict por incoherencia territorial, obtenido: {resp.status_code}"
  assert data.get("error_code") == "INFRAESTRUCTURA_INCOMPATIBLE"
  assert count == 0, f"Falla de integridad: se insertó asociación no autorizada en BD"
  ```
- **Escenario B (Productor RBAC):**
  ```python
  # El test original valida que el estado actual en TEST arroja 403 debido a INC-M02-62-G87:
  assert resp.status_code == 403, (
      f"DEFECTO RBAC CORREGIDO O COMPORTAMIENTO ALTERADO: Se esperaba 403 ACCESO_DENEGADO "
      f"para capturar el defecto del Productor, pero se obtuvo: {resp.status_code}"
  )
  assert data.get("error_code") == "ACCESO_DENEGADO"
  ```
- **Escenario C (Anti-Tampering):**
  ```python
  assert resp.status_code == 404, f"Se esperaba 404 Not Found para sensor inexistente, obtenido: {resp.status_code}"
  assert data.get("error_code") == "SENSOR_NO_ENCONTRADO"
  ```

---

## 5. Evidencia de Estado en BD PostgreSQL TEST

### 5.1 Estado de `modulo1.permisos` (Recurso 30: `asociacion_sensor_activo`)
Se ejecutó la inspección directa sobre la tabla de permisos en la base de datos de TEST (`sgpmp_test`):
```sql
SELECT p.id_permiso, p.nombre, p.id_recurso, p.id_accion, p.id_rol, p.es_activo, r.nombre_rol, a.codigo
FROM modulo1.permisos p
JOIN modulo1.roles r ON r.id_rol = p.id_rol
JOIN modulo1.acciones a ON a.id_accion = p.id_accion
WHERE p.id_recurso = 30;
```
**Resultado obtenido:**
```text
- ID 181: Rol Administrador (1)        | Acción C (1) | Activo: True
- ID 182: Rol Administrador (1)        | Acción R (2) | Activo: True
- ID 183: Rol Ingeniero de Campo (4)   | Acción C (1) | Activo: True
- ID 184: Rol Ingeniero de Campo (4)   | Acción R (2) | Activo: True
- ID 185: Rol Productor (2)           | Acción R (2) | Activo: True
- ID 186: Rol Veterinario (3)          | Acción R (2) | Activo: True
```
> **Conclusión técnica:** El rol **Productor** (`id_rol=2`) únicamente cuenta con la acción `R` (READ, `id_accion=2`). La acción `C` (CREATE, `id_accion=1`) no existe en el catálogo de permisos de TEST.

### 5.2 Análisis de Trazabilidad en Código y Alembic
1. **Controlador REST:** En `src/biological_assets/infrastructure/routers/activo_biologico_router.py` (líneas ~1141-1144), el endpoint `POST /{id}/sensores` requiere explícitamente el permiso `prod_crear_asociacion_sensor_activo`:
   ```python
   @router.post(
       "/{id}/sensores",
       status_code=status.HTTP_201_CREATED,
       dependencies=[Depends(requerir_permiso("prod_crear_asociacion_sensor_activo"))],
   )
   ```
2. **Evaluación de Permisos:** En `src/shared/rbac.py`, la función `requerir_permiso` busca en la base de datos si el rol del usuario autenticado posee el permiso activo asociado al recurso `asociacion_sensor_activo` y acción `CREATE`. Al no existir el registro en la base de datos de TEST, se dispara la excepción `HTTP 403 Forbidden` (`ACCESO_DENEGADO`).
3. **Auditoría de Versiones Alembic:** La revisión del directorio `alembic/versions/` reveló que **no existe ninguna migración** encargada de sembrar o insertar la fila `(id_rol=2, id_recurso=30, id_accion=1)`. El equipo de desarrollo aplicó el cambio mediante comandos SQL manuales en sus entornos locales, omitiendo el ciclo de integración continua hacia TEST.
4. **Diagnóstico del Gap BOLA Sistémico (INC-M02-71-G48 / Issue #221):** El caso de uso `AsociarSensorActivoUseCase` valida la compatibilidad de infraestructura entre el sensor y el activo biológico (por eso el Escenario A rechaza con `409 INFRAESTRUCTURA_INCOMPATIBLE`), pero **no valida si el usuario solicitante tiene asignada la finca donde reside el activo**. Si un Productor perteneciese a la Finca 1 e intentase asociar un sensor que físicamente está en la Finca 2 a un activo de la Finca 2, el backend permitiría la creación si contara con el permiso RBAC.

---

## 6. Verificación de Limpieza (Cleanup e Inocuidad)

Se verificó el estado final de la base de datos tras la ejecución de las pruebas automáticas y manuales vía API:
- **Asociaciones Creadas:** `0`. Dado que todas las pruebas fueron diseñadas con propósitos negativos de seguridad (rechazos `409`, `403` y `404`), ninguna transacción generó inserción en `modulo2.asociaciones_activos_sensores`.
- **Asociaciones Activas Remanentes:** Se confirmó mediante consulta SQL que el activo 108 tiene `0` asociaciones activas remanentes.
- **Inocuidad de Bitácora:** La tabla `modulo2.bitacora_auditoria_m02` cuenta con `2059` registros, manteniéndose completamente íntegra e inmutable.
- **Observación sobre scripts de cleanup:** El script `cleanup_tc_m02_g87.sql` provisto en V1 utiliza sentencias `DELETE` destructivas. Para mantener la política de inmutabilidad y auditoría de la plataforma, se ratifica la directiva de utilizar únicamente sentencias `UPDATE ... SET estado_asociacion = 'INACTIVA', fecha_fin = NOW()`.

---

## 7. Conclusiones, Diagnóstico Técnico y Dictamen Final

### 7.1 Registro Formal de Defectos y Hallazgos

#### 🔴 INC-M02-62-G87: Falta de Permiso CREATE para Rol Productor en Asociación Sensor-Activo
- **Módulo:** M02 — Activos Biológicos / M01 — Identity & Access
- **Requisito Afectado:** RF-49 (CU11)
- **Severidad:** Media (Bloqueo de funcionalidad al actor principal)
- **Estado en V2:** **⚠️ PERSISTE EN ENTORNO TEST**
- **Causa Raíz:** El equipo de desarrollo aplicó la inserción SQL de forma manual en desarrollo local (`sgpmp` y `pruebas`), pero no creó un archivo de migración Alembic. En consecuencia, el despliegue automático hacia TEST no incorporó el permiso en `modulo1.permisos`.
- **Acción Requerida:** Crear una migración Alembic idempotente (con verificación `WHERE NOT EXISTS`) que inserte la tupla `(id_rol=2, id_recurso=30, id_accion=1)` en `modulo1.permisos`, y desplegarla en TEST.

#### 🟠 INC-M02-71-G48 (Issue #221): Gap Sistémico de Control de Alcance Territorial (BOLA)
- **Módulo:** M02 — Activos Biológicos (Transversal a use cases de escritura)
- **Requisito Afectado:** RF-49 / Seguridad OWASP API1 (BOLA)
- **Severidad:** Alta (Riesgo de escalada horizontal de datos entre fincas)
- **Estado en V2:** **⚠️ RIESGO LATENTE CONFIRMADO EN ARQUITECTURA (ENMASCARADO EN TEST POR INC-M02-62-G87)**
- **Causa Raíz:** `AsociarSensorActivoUseCase` no implementa ni inyecta el validador de alcance `AlcanceFincaAdapter`. Aunque la validación física de infraestructura rechaza inconsistencias entre sensor y activo (`409`), no existe restricción que impida a un productor operar activos de otra finca si la infraestructura y el sensor pertenecen a dicha finca ajena.
- **Acción Requerida:** Inyectar la validación de alcance por finca del usuario autenticado en la capa de aplicación de M02 antes de persistir cualquier asociación.

#### 🔒 TC-M02-153: Validación de Cifrado IoT MQTT / LoRaWAN
- **Estado en V2:** **🔒 BLOQUEO PERMANENTE FUERA DE STACK**
- **Justificación:** Requiere analizador físico de paquetes (Wireshark / sniffer de radiofrecuencia) y brokers de telemetría activos. No es verificable a través del protocolo HTTP ni mediante pruebas unitarias/integración de API REST.
- **Acción Requerida:** Remitir a auditoría especializada de ciberseguridad e infraestructura IoT.

---

### 7.2 Dictamen Final de QA
1. Se valida que los controles territoriales de infraestructura (Escenario A) y anti-tampering (Escenario C) funcionan correctamente en el backend (`409` y `404`).
2. La suite Pytest finaliza con Exit Code `0` porque el Escenario B fue programado para capturar la persistencia del defecto RBAC (`403`).
3. El caso **TC-M02-G87** concluye en **⚠️ PASS CON DEFECTO CONFIRMADO**, condicionado a que el equipo de desarrollo formalice el permiso en Alembic para TEST y aborde la remediación transversal de BOLA antes del pase a producción.
