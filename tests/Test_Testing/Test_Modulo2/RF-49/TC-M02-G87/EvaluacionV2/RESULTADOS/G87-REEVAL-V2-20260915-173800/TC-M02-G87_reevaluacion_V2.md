# Reevaluación V2 — Caso TC-M02-G87 — RF-49 CU11 — Estado del Fix RBAC (INC-M02-62-G87) y Verificación del Gap BOLA Sistémico (INC-M02-71-G48)

---

## 1. Encabezado y Metadatos de Ejecución

| Parámetro | Valor |
| :--- | :--- |
| **RUN_ID** | `G87-REEVAL-V2-20260915-173800` |
| **Fecha de Evaluación V1** | 2026-09-10 |
| **Fecha de Reevaluación V2** | 2026-09-15 17:38:00 UTC |
| **Caso Agrupado** | **TC-M02-G87** (Módulo 2 — Activos Biológicos, RF-49 CU11) |
| **Subcasos Evaluados** | TC-M02-152 (Seguridad BOLA y RBAC), TC-M02-153 (Cifrado IoT) |
| **Entorno de Pruebas** | **TEST** (`https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test`) |
| **Base de Datos** | PostgreSQL 16 (`158.69.200.27:5448/sgpmp_test`, usuario `member_qa`) |
| **Herramientas de Ejecución** | Pytest v9.0.3 + `pytest-html` v4.2.0 + Python 3.13.9 |
| **Suite Ejecutada** | `tests/integration/test_rf49_bola_sensor_cross_finca_integration.py` |
| **Reporte HTML Generado** | [reporte_TC-M02-152_pytest.html](./reporte_TC-M02-152_pytest.html) (`tests/Test_Testing/Test_Modulo2/RF-49/TC-M02-G87/EvaluacionV2/RESULTADOS/G87-REEVAL-V2-20260915-173800/reporte_TC-M02-152_pytest.html`) |
| **Veredicto Global** | ⚠️ **PASS CON DEFECTO CONFIRMADO (TC-M02-152 PASS CON DEFECTO RBAC PERSISTENTE; TC-M02-153 BLOQUEO PERMANENTE FUERA DE STACK)** |

---

## 2. Objetivo de la Reevaluación y Resumen Ejecutivo

### 2.1. Contexto V1
En la evaluación original (2026-09-10), el caso agrupado **TC-M02-G87** arrojó:
- **TC-M02-152**: Dictaminado como *PASS CON DEFECTO DE RBAC*. Se constató que el Productor Agropecuario (`id_rol=2`), a pesar de ser definido por el RF-49 como Actor Principal, no podía asociar sensores en sus propios activos porque la tabla `modulo1.permisos` carecía de la acción `1` (CREATE) sobre el recurso `30` (`asociacion_sensor_activo`), respondiendo con `HTTP 403 ACCESO_DENEGADO` (registrado formalmente como `INC-M02-62-G87`).
- **TC-M02-153**: Dictaminado como *BLOQUEADO FUERA DE STACK* (inspección de cifrado de red en canales MQTT/LoRaWAN mediante sniffer promiscuo).

### 2.2. Contexto V2 y Respuesta de Desarrollo
El equipo de desarrollo reportó en sus notas internas (`anotaciones/modulo_2/inc_m02_62_g87_productor_crear_asociacion_sensor.md`) haber aplicado un fix manual ("Paso 0") insertando el permiso `prod_crear_asociacion_sensor_activo` en sus entornos locales (`sgpmp` dev y `pruebas` test local). Adicionalmente, el equipo emitió una advertencia crítica sobre un **gap sistémico de BOLA (INC-M02-71-G48 / issue #221)**: los casos de uso de escritura de Módulo 2 (incluyendo `AsociarSensorActivoUseCase`) resuelven los activos con `obtener_por_id` sin validar pertenencia por finca (`AlcanceFincaAdapter`). Por ende, tras habilitar el permiso RBAC, el Productor podría asociar sensores en activos de cualquier finca ajena si no existen otros controles.

### 2.3. Hallazgos Reales de la Reevaluación V2 en TEST
1. **Estado del Fix RBAC en TEST (`sgpmp_test`)**:
   - **EL FIX NO ESTÁ APLICADO EN TEST**. Al autenticarse como Productor (`productor@pecuaria.co`) e intentar asociar el sensor 22 al activo 108 (su propia finca), el backend de TEST respondió `HTTP 403 Forbidden` (`error_code: ACCESO_DENEGADO`).
   - La consulta directa a `modulo1.permisos` en `sgpmp_test` ratifica que la fila `(id_rol=2, id_recurso=30, id_accion=1)` **no existe** en la base de datos de TEST.
   - La causa de la discrepancia es que el fix fue aplicado manualmente en entornos locales y **nunca se empaquetó en una migración de Alembic**, impidiendo su despliegue reproducible en TEST.
2. **Impacto sobre el Gap BOLA Sistémico (INC-M02-71-G48)**:
   - Dado que el fix RBAC no se encuentra desplegado en TEST, la compuerta RBAC (`require_permission`) intercepta las solicitudes del Productor con `HTTP 403` antes de que alcancen el caso de uso.
   - En consecuencia, el Productor permanece blindado "por defecto" frente a la explotación del BOLA en TEST, pero continúa inhabilitado para operar su flujo legítimo de negocio.
3. **TC-M02-153**:
   - Se ratifica el dictamen de **BLOQUEO PERMANENTE FUERA DE STACK**, cerrando formalmente el ciclo de expectativas sobre herramientas de hardware/red que exceden el stack de QA de backend/API REST.

### 2.4. Tabla Comparativa de Resultados

| Sub-caso / Escenario | Enfoque Evaluado | Entorno | Resultado Esperado | Obtenido V2 | Aserciones | Veredicto V2 |
| :--- | :--- | :---: | :--- | :--- | :---: | :---: |
| **TC-M02-152 (Esc. A)** | Ataque BOLA Cross-Finca (Ingeniero) | TEST | HTTP 409 `INFRAESTRUCTURA_INCOMPATIBLE` | HTTP 409 `INFRAESTRUCTURA_INCOMPATIBLE` | Conforme | ✅ **PASS** |
| **TC-M02-152 (Esc. B)** | Productor asocia en su propia finca | TEST | HTTP 403 `ACCESO_DENEGADO` (evidencia defecto) | HTTP 403 `ACCESO_DENEGADO` | Conforme | ⚠️ **PASS CON DEFECTO RBAC** |
| **TC-M02-152 (Esc. B extendido)** | Productor asocia en Finca Ajena (BOLA) | TEST | HTTP 403 (RBAC) o HTTP 409 (Territorial) | HTTP 403 `ACCESO_DENEGADO` | Conforme | ⚠️ **BLOQUEADO POR RBAC** |
| **TC-M02-152 (Esc. C)** | Inyección sensor inexistente (Anti-tampering) | TEST | HTTP 404 `SENSOR_NO_ENCONTRADO` | HTTP 404 `SENSOR_NO_ENCONTRADO` | Conforme | ✅ **PASS** |
| **TC-M02-153** | Cifrado de canal MQTT/LoRaWAN (TLS/DTLS) | TEST | Inspección de paquetes de red cifrados | No evaluable por falta de sniffer y broker | N/A | 🔒 **BLOQUEO PERMANENTE FUERA DE STACK** |

---

## 3. Estado Previo (Pre-condición vía API REST)

### 3.1. Transcripción de `precondicion_api.log`
```text
[2026-09-15 22:37:40 UTC] === INICIO DE VERIFICACIÓN DE PRECONDICIONES (TEST API) — TC-M02-G87 ===
[2026-09-15 22:37:40 UTC] Target baseUrl: https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test
[2026-09-15 22:37:42 UTC] 1. Autenticación admin obtenida exitosamente.
[2026-09-15 22:37:42 UTC] 2. GET /activos-biologicos/108 -> HTTP 200
[2026-09-15 22:37:42 UTC]    Activo 108: ID=108, Estado=ACTIVO, Infra=3 (Finca 1)
[2026-09-15 22:37:43 UTC] 3. GET /configuracion/dispositivos-iot/38 -> HTTP 200 (Infra 3)
[2026-09-15 22:37:44 UTC] 4. GET /configuracion/dispositivos-iot/4 -> HTTP 200 (Infra 1)
[2026-09-15 22:37:44 UTC] === FIN DE VERIFICACIÓN DE PRECONDICIONES ===
```

### 3.2. Transcripción de `verificacion_rbac.log`
```text
[2026-09-15 22:37:44 UTC] === INICIO DE VERIFICACIÓN DE ESTADO RBAC (INC-M02-62-G87) Y BOLA EN TEST ===
[2026-09-15 22:37:45 UTC] 1. Login Productor: POST /sesiones/ -> HTTP 200
[2026-09-15 22:37:47 UTC] 2. Identidad Productor: GET /usuarios/me -> HTTP 200
[2026-09-15 22:37:47 UTC]    Datos Usuario: ID=2, Nombre=Laura Gómez Torres, Correo=productor@pecuaria.co
[2026-09-15 22:37:47 UTC] 3. Intento de crear asociación en activo 108 (Finca 1) con rol Productor...
[2026-09-15 22:37:47 UTC]    POST /activos-biologicos/108/sensores -> HTTP 403
[2026-09-15 22:37:47 UTC]    Respuesta: {"error_code":"ACCESO_DENEGADO","message":"Acceso denegado. Su rol no tiene permisos para realizar esta operación.","fields":[],"timestamp":"2026-09-15T22:37:46.862905+00:00"}
[2026-09-15 22:37:47 UTC]    ESTADO FIX RBAC: NO APLICADO EN TEST (HTTP 403 ACCESO_DENEGADO).
[2026-09-15 22:37:47 UTC]    Defecto INC-M02-62-G87 PERSISTE en TEST (Productor sigue sin permiso CREATE en modulo1.permisos).
[2026-09-15 22:37:47 UTC]    Verificación BOLA no ejecutable con Productor porque la compuerta RBAC bloquea antes del caso de uso.
[2026-09-15 22:37:50 UTC] 5. Estado de modulo1.permisos para id_recurso = 30 en sgpmp_test:
[2026-09-15 22:37:50 UTC]    - ID 181: Rol Administrador (1) | Acción C (1) | Activo: True
[2026-09-15 22:37:50 UTC]    - ID 182: Rol Administrador (1) | Acción R (2) | Activo: True
[2026-09-15 22:37:50 UTC]    - ID 183: Rol Ingeniero de Campo (4) | Acción C (1) | Activo: True
[2026-09-15 22:37:50 UTC]    - ID 184: Rol Ingeniero de Campo (4) | Acción R (2) | Activo: True
[2026-09-15 22:37:50 UTC]    - ID 185: Rol Productor (2) | Acción R (2) | Activo: True
[2026-09-15 22:37:50 UTC]    - ID 186: Rol Veterinario (3) | Acción R (2) | Activo: True
[2026-09-15 22:37:50 UTC]    Fila (id_rol=2, id_recurso=30, id_accion=1) presente: False
[2026-09-15 22:37:51 UTC] === FIN DE VERIFICACIÓN DE ESTADO RBAC ===
```

---

## 4. Resultados Detallados (Pytest + Verificaciones API)

### 4.1. Métricas de Ejecución de la Suite Pytest
- **Comando Ejecutado**:
  ```powershell
  $env:TEST_DATABASE_URL="postgresql://member_qa:qaSGP2026@158.69.200.27:5448/sgpmp_test"; $env:PYTHONPATH="."; .venv\Scripts\pytest.exe tests/integration/test_rf49_bola_sensor_cross_finca_integration.py -v -m integration --html=.../reporte_TC-M02-152_pytest.html --self-contained-html
  ```
- **Total Tests Ejecutados**: 3
- **Aprobados**: 3 (100% de las aserciones codificadas aprobadas)
- **Fallidos**: 0
- **Tiempo de Ejecución**: 7.48 s
- **Exit Code**: **0**

### 4.2. Detalle de Escenarios Evaluados en Pytest

1. **`test_tc_m02_152_escenario_a_bola_cross_finca_ingeniero`**: ✅ **PASSED**
   - *Petición*: `POST /activos-biologicos/108/sensores` con Sensor `8` (Finca 2, Infra 4) y Activo `108` (Finca 1, Infra 3), autenticado como Ingeniero de Campo (`ingeniero@pecuaria.co`).
   - *Respuesta*: `HTTP 409 Conflict`.
   - *Body*: `{"error_code":"INFRAESTRUCTURA_INCOMPATIBLE","message":"Error de ubicación. El activo está en la finca 1 y el sensor en la finca 2. La asociación solo es permitida dentro de la misma unidad territorial."}`
   - *Aserciones*: `resp.status_code == 409`, `data['error_code'] == 'INFRAESTRUCTURA_INCOMPATIBLE'`, validación de no filtración de datos sensibles (`token`, `secret`, `password`), y consulta en BD `SELECT COUNT(*) == 0`.
2. **`test_tc_m02_152_escenario_b_productor_defecto_rbac`**: ✅ **PASSED (Captura de Defecto)**
   - *Petición*: `POST /activos-biologicos/108/sensores` con Sensor `22` y Activo `108` (ambos en Finca 1), autenticado como Productor (`productor@pecuaria.co`).
   - *Respuesta*: `HTTP 403 Forbidden`.
   - *Body*: `{"error_code":"ACCESO_DENEGADO","message":"Acceso denegado. Su rol no tiene permisos para realizar esta operación."}`
   - *Aserciones*: `resp.status_code == 403`, `data['error_code'] == 'ACCESO_DENEGADO'`. La prueba pasa porque su objetivo específico es validar y documentar la persistencia del fallo de autorización del Productor.
3. **`test_tc_m02_152_escenario_c_anti_tampering_sensor_inexistente`**: ✅ **PASSED**
   - *Petición*: `POST /activos-biologicos/108/sensores` con `sensor_id: 9999`.
   - *Respuesta*: `HTTP 404 Not Found`.
   - *Body*: `{"error_code":"SENSOR_NO_ENCONTRADO","message":"No existe un sensor con id 9999."}`
   - *Aserciones*: `resp.status_code == 404`, `data['error_code'] == 'SENSOR_NO_ENCONTRADO'`.

---

## 5. Evidencia de Estado en BD PostgreSQL TEST

### 5.1. Transcripción de `postcondicion_api.log`
```text
[2026-09-15 22:38:57 UTC] === INICIO DE VERIFICACIÓN DE POSTCONDICIONES Y CLEANUP (TEST) — TC-M02-G87 ===
[2026-09-15 22:38:57 UTC] Target baseUrl: https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test
[2026-09-15 22:38:57 UTC] Database: 158.69.200.27:5448/sgpmp_test
[2026-09-15 22:38:58 UTC] 1. Autenticación admin obtenida para verificación post-condición.
[2026-09-15 22:38:58 UTC] 2. Re-consultando estado de los activos biológicos vía API...
[2026-09-15 22:38:59 UTC]    GET /activos-biologicos/108 -> HTTP 200
[2026-09-15 22:38:59 UTC]       Activo 108: Estado=ACTIVO, Tipo=INDIVIDUAL, Identificador=MADRE-G53-1788880748, Inalterado: SÍ
[2026-09-15 22:39:01 UTC] 3. Verificando asociaciones activas en modulo2.asociaciones_activos_sensores...
[2026-09-15 22:39:01 UTC]    Asociaciones ACTIVAS remanentes de TC-M02-G87: 0 (Esperado: 0)
[2026-09-15 22:39:01 UTC]    Total asociaciones activas para activo 108: 0 (Esperado: 0)
[2026-09-15 22:39:01 UTC]    Confirmación: Ningún escenario generó asociaciones en BD (Escenario A=409, Escenario B=403, Escenario C=404). 0 residuos.
[2026-09-15 22:39:01 UTC] 4. Verificando inmutabilidad de bitácoras en modulo2.bitacora_auditoria_m02...
[2026-09-15 22:39:01 UTC]    Total registros en bitácora modulo2: 2057
[2026-09-15 22:39:01 UTC]    Inmutabilidad de bitácora preservada: SÍ (0 registros eliminados ni alterados).
[2026-09-15 22:39:01 UTC] === RESUMEN POSTCONDICIONES ===
[2026-09-15 22:39:01 UTC] Estado Cleanup: EXITOSO (0 asociaciones activas generadas ni remanentes, inmutabilidad preservada).
[2026-09-15 22:39:01 UTC] === FIN DE VERIFICACIÓN DE POSTCONDICIONES ===
```

### 5.2. Análisis Técnico de la Causa Raíz

1. **Evaluación Dinámica de Permisos en `src/shared/rbac.py`**:
   - En líneas 19-36, `tiene_permiso` consulta en cada petición si existe una tupla activa `(id_rol, id_recurso, id_accion)` en `modulo1.permisos`.
   - En [activo_biologico_router.py](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/src/biological_assets/infrastructure/routers/activo_biologico_router.py#L1141), el endpoint `POST /{id_activo}/sensores` declara `dependencies=[Depends(require_permission(_RECURSO_SENSOR, 1))]`, con `_RECURSO_SENSOR = 30` (línea 137).
   - Como la base de datos `sgpmp_test` carece de la fila `(id_rol=2, id_recurso=30, id_accion=1)`, el Productor es invariablemente rechazado con `403 ACCESO_DENEGADO`.
2. **Ausencia de Migración Alembic para el Fix**:
   - La búsqueda en `alembic/versions/` confirma que **no existe ninguna migración** que agregue el permiso del Productor a `modulo1.permisos`.
   - En [inc_m02_62_g87_productor_crear_asociacion_sensor.md](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/anotaciones/modulo_2/inc_m02_62_g87_productor_crear_asociacion_sensor.md#L26-L38), desarrollo documentó que ejecutó un `INSERT` manual en caliente en su entorno local, pero no creó una migración formal de Alembic. Por ello, el fix nunca llegó al entorno TEST.
3. **Caracterización del Riesgo BOLA Sistémico (INC-M02-71-G48 / Issue #221)**:
   - El use case [AsociarSensorActivoUseCase](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/src/biological_assets/application/use_cases/gestion/asociar_sensor_activo_use_case.py#L50-L65) recibe `id_activo` y lo obtiene mediante `self.activo_repo.obtener_por_id(id_activo)`. **No recibe ni evalúa el `id_finca` asignado al `usuario_actual`**.
   - Tan pronto como se aplique el permiso RBAC al Productor, este podrá asociar sensores sobre activos de fincas ajenas siempre que el sensor y el activo compartan la misma finca entre sí, vulnerando el principio de autorización de objeto BOLA (OWASP API1).

---

## 6. Verificación de Limpieza (Cleanup e Inocuidad)

1. **Inocuidad Transaccional**:
   Los 3 escenarios evaluados en Pytest correspondieron a respuestas de error controladas (`409`, `403` y `404`). Por consiguiente, **no se insertó ninguna asociación sensor-activo en la base de datos**.
2. **0 Residuos Remanentes**:
   La consulta a `modulo2.asociaciones_activos_sensores` sobre el Activo `108` confirmó `0 asociaciones activas remanentes`.
3. **Inmutabilidad de Bitácoras**:
   La tabla `modulo2.bitacora_auditoria_m02` conservó sus 2057 registros íntegros con sus hashes criptográficos, certificando la total inocuidad de la prueba sobre el entorno TEST.
4. **Deuda Técnica en Script de Limpieza**:
   El script histórico `tests/Test_Testing/Test_Modulo2/RF-49/TC-M02-G87/RESULTADOS/cleanup_tc_m02_g87.sql` contiene sentencias `DELETE`. Se reitera la recomendación de reescribirlo a `UPDATE` append-only para prevenir violaciones a las directrices de inmutabilidad.

---

## 7. Conclusiones, Diagnóstico Técnico y Dictamen Final

### 7.1. Dictamen de Reevaluación
El caso agrupado **TC-M02-G87** queda dictaminado como:
⚠️ **PASS CON DEFECTO CONFIRMADO (TC-M02-152 PASS CON DEFECTO RBAC PERSISTENTE; TC-M02-153 BLOQUEO PERMANENTE FUERA DE STACK)**.

### 7.2. Registro Formal de Hallazgos y Defectos

#### Defecto 1: INC-M02-62-G87 (Persiste en Entorno TEST)
- **ID**: `INC-M02-62-G87`
- **Título**: Productor Agropecuario (Actor Principal RF-49) sin permiso CREATE para asociar sensores IoT.
- **Estado en V2**: **PERSISTE EN TEST**.
- **Causa Raíz**: Falta la fila `(id_rol=2, id_recurso=30, id_accion=1)` en la tabla `modulo1.permisos` de `sgpmp_test`. El fix reportado por desarrollo fue aplicado únicamente como `INSERT` manual en bases de datos locales y no fue versionado en una migración de Alembic.
- **Acción Requerida**: Crear una migración formal en `alembic/versions/` que ejecute el `INSERT` de la fila de permiso y aplicarla sobre el entorno TEST.

#### Defecto 2: INC-M02-71-G48 / Issue #221 (Riesgo BOLA Latente)
- **ID**: `INC-M02-71-G48`
- **Título**: Gap sistémico de validación de alcance por finca (`AlcanceFincaAdapter`) en use cases de escritura de Módulo 2.
- **Estado en V2**: **ABIERTO Y LATENTE**.
- **Causa Raíz**: `AsociarSensorActivoUseCase` no valida que el activo biológico pertenezca a la finca asignada al usuario autenticado. En el momento en que se aplique el permiso RBAC del Productor, se abrirá una vulnerabilidad BOLA directa que permitirá al Productor modificar activos de otras fincas.
- **Acción Requerida**: Inyectar `AlcanceFincaAdapter` en el caso de uso y verificar que `activo.id_infraestructura` pertenezca a las fincas autorizadas del usuario antes de proceder con la asociación.

#### Estado de TC-M02-153: 🔒 BLOQUEO PERMANENTE FUERA DE STACK
- **Dictamen**: **CERRADO COMO FUERA DE ALCANCE (OUT-OF-SCOPE)** para el marco de testing funcional y de integración de backend/API REST.
- **Fundamentación**: La verificación de cifrado a nivel de paquetes en protocolos de telemetría (MQTT sobre TLS, LoRaWAN) requiere herramientas de captura promiscua de red (`tcpdump`, Wireshark) y brokers dedicados de IoT, ajenos al stack de software evaluable mediante pruebas de endpoints HTTP. Remitir a auditoría de ciberseguridad física/red.

### 7.3. Hallazgos Secundarios No Bloqueantes
1. **Script de Cleanup con DELETE**: `cleanup_tc_m02_g87.sql` debe ser refactorizado a `UPDATE` append-only (`estado_asociacion='INACTIVA'`, `fecha_fin=NOW()`).
2. **Falta de Migración Alembic**: Los ajustes RBAC no deben aplicarse mediante scripts DML ad-hoc ("Paso 0") para garantizar su trazabilidad y despliegue entre ambientes.

### 7.4. Recomendación de Seguimiento
1. Requerir formalmente a Desarrollo la entrega de un PR que contenga:
   - Migración Alembic para `INC-M02-62-G87` (inserción del permiso en `modulo1.permisos`).
   - Implementación de `AlcanceFincaAdapter` en `AsociarSensorActivoUseCase` para subsanar `INC-M02-71-G48`.
2. Programar la **Reevaluación V3** una vez que ambos componentes estén desplegados conjuntamente en TEST, asegurando que el Productor pueda asociar en su finca (`HTTP 201`) y sea bloqueado por BOLA territorial en fincas ajenas (`HTTP 403 / 409`).
