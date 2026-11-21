# Reevaluación V2 — Caso TC-M02-G84 — RF-49 CU11 — Confirmación de Bloqueo de TC-M02-150 por Gap Funcional del Backend

---

## 1. Encabezado y Metadatos

| Parámetro | Valor |
| :--- | :--- |
| **RUN_ID** | `G84-REEVAL-V2-20260915-161500` |
| **Fecha de Evaluación V1** | 2026-09-10 |
| **Fecha de Reevaluación V2** | 2026-09-15 |
| **Caso Agrupado** | **TC-M02-G84** (Módulo 2 — Activos Biológicos, RF-49 CU11) |
| **Subcasos Evaluados** | TC-M02-143, TC-M02-144, TC-M02-145, TC-M02-150 |
| **Entorno de Pruebas** | **TEST** (`https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test`) |
| **Acceso a Base de Datos** | PostgreSQL 16 (`158.69.200.27:5448/sgpmp_test`) + API REST HTTPS |
| **Herramienta de Ejecución** | Newman CLI v6.2.2 + `newman-reporter-htmlextra` v1.23.1 |
| **Colección Ejecutada** | `tests/Test_Testing/Test_Modulo2/RF-49/TC-M02-G84/test_tc_m02_g84.json` |
| **Reporte HTML Generado** | `tests/Test_Testing/Test_Modulo2/RF-49/TC-M02-G84/EvaluacionV2/RESULTADOS/G84-REEVAL-V2-20260915-161500/reporte_v2.html` |
| **Resumen JSON Newman** | `tests/Test_Testing/Test_Modulo2/RF-49/TC-M02-G84/EvaluacionV2/RESULTADOS/G84-REEVAL-V2-20260915-161500/newman_summary_v2.json` |
| **Veredicto Global** | ⚠️ **PASS PARCIAL CONFIRMADO (3/4 PASS, 1 BLOQUEADO POR GAP BACKEND)** |

---

## 2. Objetivo de la Reevaluación y Resumen Ejecutivo

### 2.1. Contexto V1 y Descarte de Hipótesis Original
En la evaluación original (V1) del 2026-09-10, el caso agrupado **TC-M02-G84** quedó categorizado como **PASS PARCIAL POR BLOQUEO EXTERNO**. La justificación asentada en el informe V1 establecía la hipótesis de que:
> *"El campo `advertencia` retorna `null` porque el Módulo 3 (Telemetría) no está implementado ni desplegado en TEST, por lo que no es posible verificar el heartbeat del dispositivo."*

Bajo esta premisa, se planteó originalmente migrar la prueba al entorno DEV donde se presumía que M03 estaba operativo.

### 2.2. Hallazgo del Diagnóstico Read-Only V2
El análisis de diagnóstico previo a la ejecución V2 reveló que **dicha hipótesis era técnicamente errónea**:
1. **Módulo 3 SÍ está desplegado en TEST**: El endpoint `GET /iot/dispositivos/3/estado` existe y responde `HTTP 200` confirmando que el dispositivo IoT 3 se encuentra en estado `INACTIVO` (`fecha_ultimo_contacto: 2024...`).
2. **Causa Raíz Real (Gap Funcional del Backend)**:
   - En el archivo [activo_biologico_router.py](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/src/biological_assets/infrastructure/routers/activo_biologico_router.py#L1170), línea 1170 y línea 1210, la respuesta expone literalmente:
     ```python
     advertencia=None,
     ```
   - El caso de uso [AsociarSensorActivoUseCase](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/src/biological_assets/application/use_cases/gestion/asociar_sensor_activo_use_case.py#L31-L48) no inyecta ningún puerto de consulta de telemetría (M03), no consulta el estado ni heartbeat del dispositivo IoT, y la entidad de dominio `AsociacionSensorActivo` ni siquiera posee un atributo `advertencia`.
   - **Commit origen**: `8930482871117a2ce6a517fd5308d6949bd093a8` (2026-06-29), donde se implementó el router devolviendo `advertencia=None` hardcodeado.
3. **Decisión de QA**:
   - Se descartó rotundamente ejecutar en DEV debido a que dicho entorno comparte exactamente la misma base de código defectuosa y además carece de los fixtures de activos biológicos requeridos (IDs 108, 109, 83, 110 retornan 404 Not Found en DEV).
   - Se procedió a reevaluar exclusivamente en **TEST** para reconfirmar la estabilidad de los 3 subcasos PASS (TC-M02-143, 144, 145) y documentar con precisión forense el bloqueo de TC-M02-150 por gap funcional del backend.

### 2.3. Tabla Comparativa de Resultados

| Sub-caso | Enfoque Evaluado | Entorno | Resultado Esperado | Obtenido V2 | Aserciones | Veredicto V2 |
| :--- | :--- | :---: | :--- | :--- | :---: | :---: |
| **TC-M02-143** | Asociación DIRECTA a activo individual válido | TEST | HTTP 201 Created + `estado_asociacion: ACTIVA` + `tipo: directa` | HTTP 201 Created, `id_asociacion: 31`, `ACTIVA`, `directa` | 4/4 | ✅ **PASS** |
| **TC-M02-144** | Asociación AMBIENTAL compartida a infraestructura | TEST | HTTP 201 Created + `estado_asociacion: ACTIVA` + `tipo: ambiental` | HTTP 201 Created, `id_asociacion: 32`, `ACTIVA`, `ambiental` | 3/3 | ✅ **PASS** |
| **TC-M02-145** | Asociación POBLACIONAL a lote | TEST | HTTP 201 Created + `estado_asociacion: ACTIVA` + `tipo: poblacional` | HTTP 201 Created, `id_asociacion: 33`, `ACTIVA`, `poblacional` | 3/3 | ✅ **PASS** |
| **TC-M02-150** | Advertencia informativa por dispositivo IoT desconectado | TEST | HTTP 201 Created + `advertencia` conteniendo "desconectado" / heartbeat | HTTP 201 Created, `id_asociacion: 34`, `advertencia: null` | 3/4 | ❌ **BLOQUEADO (GAP BACKEND)** |

---

## 3. Estado Previo (Pre-condición vía API REST)

Antes de iniciar la suite Newman, se verificó el estado de todos los fixtures en el entorno TEST mediante la API REST y se registró en [precondicion_api.log](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/tests/Test_Testing/Test_Modulo2/RF-49/TC-M02-G84/EvaluacionV2/RESULTADOS/G84-REEVAL-V2-20260915-161500/precondicion_api.log).

### Transcripción de `precondicion_api.log`:
```text
[2026-09-15 21:16:39 UTC] === INICIO DE VERIFICACIÓN DE PRECONDICIONES (TEST API) ===
[2026-09-15 21:16:39 UTC] Target baseUrl: https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test
[2026-09-15 21:16:39 UTC] 1. Solicitando autenticación admin: POST https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test/sesiones/
[2026-09-15 21:16:41 UTC]    Respuesta Auth HTTP 200
[2026-09-15 21:16:41 UTC]    Token JWT obtenido exitosamente.
[2026-09-15 21:16:41 UTC] 2. Verificando existencia y estado de activos biológicos...
[2026-09-15 21:16:42 UTC]    GET /activos-biologicos/108 -> HTTP 200
[2026-09-15 21:16:42 UTC]       Data: {"id_activo_biologico": 108, "id_especie": 10, "tipo": "INDIVIDUAL", "identificador": "MADRE-G53-1788880748", "fecha_inicio_ciclo": "2026-01-15", "detalles_procedencia": null, "origen_financiero": "compra", "costo_adquisicion": "50000.0000", "soporte_documental": "factura-madre-1788880748", "descripcion": null, "id_infraestructura": 3, "atributos_dinamicos": null, "id_estado": 1, "nombre_estado": "ACTIVO", "id_usuario": 1, "fecha_creacion": "2026-09-08T15:19:08.721292Z", "detalle_individual": {"id_detalle": 30, "raza": "Tilapia Nilotica", "sexo": "Hembra", "fecha_nacimiento": "2025-01-01T00:00:00Z", "peso_inicial": "0.500", "fecha_creacion": "2026-09-08T15:19:08.721292Z"}, "detalle_poblacional": null}
[2026-09-15 21:16:42 UTC]    GET /activos-biologicos/109 -> HTTP 200
[2026-09-15 21:16:42 UTC]       Data: {"id_activo_biologico": 109, "id_especie": 10, "tipo": "INDIVIDUAL", "identificador": "PADRE-G53-1788880748", "fecha_inicio_ciclo": "2026-01-15", "detalles_procedencia": null, "origen_financiero": "compra", "costo_adquisicion": "50000.0000", "soporte_documental": "factura-padre-1788880748", "descripcion": null, "id_infraestructura": 3, "atributos_dinamicos": null, "id_estado": 1, "nombre_estado": "ACTIVO", "id_usuario": 1, "fecha_creacion": "2026-09-08T15:19:09.264434Z", "detalle_individual": {"id_detalle": 31, "raza": "Tilapia Nilotica", "sexo": "Macho", "fecha_nacimiento": "2025-01-01T00:00:00Z", "peso_inicial": "0.600", "fecha_creacion": "2026-09-08T15:19:09.264434Z"}, "detalle_poblacional": null}
[2026-09-15 21:16:43 UTC]    GET /activos-biologicos/83 -> HTTP 200
[2026-09-15 21:16:43 UTC]       Data: {"id_activo_biologico": 83, "id_especie": 4, "tipo": "POBLACIONAL", "identificador": null, "fecha_inicio_ciclo": "2026-09-08", "detalles_procedencia": "TEST-BAJA-CORRECTO", "origen_financiero": "compra", "costo_adquisicion": "50000.0000", "soporte_documental": "FAC-TEST-BAJA2", "descripcion": null, "id_infraestructura": 3, "atributos_dinamicos": null, "id_estado": 1, "nombre_estado": "ACTIVO", "id_usuario": 1, "fecha_creacion": "2026-09-08T05:10:00.077247Z", "detalle_individual": null, "detalle_poblacional": {"id_detalle": 35, "cantidad_inicial": 100, "cantidad_actual": 100, "peso_promedio_inicial": "10.0000", "peso_promedio": null, "biomasa_total": null, "densidad": null}}
[2026-09-15 21:16:44 UTC]    GET /activos-biologicos/110 -> HTTP 200
[2026-09-15 21:16:44 UTC]       Data: {"id_activo_biologico": 110, "id_especie": 10, "tipo": "INDIVIDUAL", "identificador": "MADRE-G53-1788883766399", "fecha_inicio_ciclo": "2026-01-15", "detalles_procedencia": null, "origen_financiero": "compra", "costo_adquisicion": "50000.0000", "soporte_documental": "factura-madre-1788883766399", "descripcion": null, "id_infraestructura": 3, "atributos_dinamicos": null, "id_estado": 1, "nombre_estado": "ACTIVO", "id_usuario": 1, "fecha_creacion": "2026-09-08T16:09:26.700770Z", "detalle_individual": {"id_detalle": 32, "raza": "Tilapia Nilotica", "sexo": "Hembra", "fecha_nacimiento": "2025-01-01T00:00:00Z", "peso_inicial": "0.500", "fecha_creacion": "2026-09-08T16:09:26.700770Z"}, "detalle_poblacional": null}
[2026-09-15 21:16:44 UTC] 3. Verificando catálogo M09: Dispositivo IoT 3 y Sensor 6...
[2026-09-15 21:16:45 UTC]    GET /configuracion/dispositivos-iot/3 -> HTTP 200
[2026-09-15 21:16:45 UTC]       Dispositivo 3 Data: {"id_dispositivo_iot": 3, "serial": "IOT-ALE01-HLA-003", "descripcion": "Nodo IoT alevinera, módulo compacto de bajo consumo", "id_infraestructura": 1, "id_tipo_dispositivo": 1, "es_activo": true, "fecha_creacion": "2026-04-28T14:42:28.213141Z"}
[2026-09-15 21:16:46 UTC]    GET /configuracion/dispositivos-iot/3/sensores -> HTTP 200
[2026-09-15 21:16:46 UTC]       Sensores disp 3: {"total": 2, "items": [{"id_sensores": 7, "nombre": "Sensor oxígeno disuelto alevinera-01", "id_dispositivo_iot": 3, "es_activo": true, "categoria": "OXIGENO"}, {"id_sensores": 6, "nombre": "Sensor temperatura alevinera-01", "id_dispositivo_iot": 3, "es_activo": true, "categoria": "TEMPERATURA"}]}
[2026-09-15 21:16:46 UTC]    Verificando dispositivos adicionales (38, 39, 40)...
[2026-09-15 21:16:46 UTC]    GET /configuracion/dispositivos-iot/38 -> HTTP 200
[2026-09-15 21:16:46 UTC]       Disp 38: {"id_dispositivo_iot": 38, "serial": "TC-M09-G61-1788611738279", "descripcion": "Dispositivo de prueba TC-M09-G61 (precondicion RF-21)", "id_infraestructura": 3, "id_tipo_dispositivo": 1, "es_activo": true, "fecha_creacion": "2026-09-05T12:35:38.864280Z"}
[2026-09-15 21:16:47 UTC]    GET /configuracion/dispositivos-iot/39 -> HTTP 200
[2026-09-15 21:16:47 UTC]       Disp 39: {"id_dispositivo_iot": 39, "serial": "TC-M09-G61-1788611758511", "descripcion": "Dispositivo de prueba TC-M09-G61 (precondicion RF-21)", "id_infraestructura": 3, "id_tipo_dispositivo": 1, "es_activo": true, "fecha_creacion": "2026-09-05T12:35:59.100135Z"}
[2026-09-15 21:16:48 UTC]    GET /configuracion/dispositivos-iot/40 -> HTTP 200
[2026-09-15 21:16:48 UTC]       Disp 40: {"id_dispositivo_iot": 40, "serial": "TC-M09-G62-A-1788611961689", "descripcion": "Dispositivo A (dueno del sensor de prueba) - TC-M09-G62", "id_infraestructura": 3, "id_tipo_dispositivo": 1, "es_activo": true, "fecha_creacion": "2026-09-05T12:39:22.805413Z"}
[2026-09-15 21:16:48 UTC] 4. Verificando estado Heartbeat del dispositivo 3 en M03 / API...
[2026-09-15 21:16:49 UTC]    GET /iot/dispositivos/3/estado -> HTTP 200 ({"estado":{"id_estado_dispositivo_iot":4,"id_dispositivo_iot":3,"estado_actual":"INACTIVO","fecha_ultimo_contacto":"2024...)
[2026-09-15 21:16:50 UTC]    GET /iot/dispositivos/3/historial -> HTTP 200 ([{"id_transaccion":3,"id_dispositivo_iot":3,"estado_anterior":"SIN_SEÑAL","estado_nuevo":"ACTIVO","causa_primaria":null,)
[2026-09-15 21:16:51 UTC]    GET /iot/heartbeat -> HTTP 405 ({"detail":"Method Not Allowed"})
[2026-09-15 21:16:51 UTC] 5. Verificando asociaciones existentes en los 4 activos biológicos...
[2026-09-15 21:16:51 UTC]    GET /activos-biologicos/108/sensores -> HTTP 405 ({"detail":"Method Not Allowed"})
[2026-09-15 21:16:52 UTC]    GET /activos-biologicos/109/sensores -> HTTP 405 ({"detail":"Method Not Allowed"})
[2026-09-15 21:16:53 UTC]    GET /activos-biologicos/83/sensores -> HTTP 405 ({"detail":"Method Not Allowed"})
[2026-09-15 21:16:54 UTC]    GET /activos-biologicos/110/sensores -> HTTP 405 ({"detail":"Method Not Allowed"})
[2026-09-15 21:16:54 UTC] === RESUMEN PRECONDICIONES ===
[2026-09-15 21:16:54 UTC] Estado Precondición Activos: CUMPLIDA (Los 4 activos existen y están en estado activo en TEST).
[2026-09-15 21:16:54 UTC] === FIN DE VERIFICACIÓN DE PRECONDICIONES ===
```

### Síntesis de Precondiciones
- **Autenticación Admin**: Exitosa con credenciales `admin@pecuaria.co` / `Test1234!`.
- **Activos Biológicos**:
  - Activo 108: `INDIVIDUAL`, `ACTIVO`, infra 3 (`MADRE-G53-1788880748`).
  - Activo 109: `INDIVIDUAL`, `ACTIVO`, infra 3 (`PADRE-G53-1788880748`).
  - Activo 83: `POBLACIONAL`, `ACTIVO`, infra 3.
  - Activo 110: `INDIVIDUAL`, `ACTIVO`, infra 3 (`MADRE-G53-1788883766399`).
- **Dispositivos y Sensores M09**:
  - Dispositivo 3 (`IOT-ALE01-HLA-003`) activo, con sensor 6 (`id_sensores: 6`, TEMPERATURA) y sensor 7 (OXÍGENO).
  - Dispositivos 38, 39 y 40 activos y listos para los subcasos 143, 144 y 145.
- **Heartbeat M03 en TEST**: `GET /iot/dispositivos/3/estado` responde `200 OK` con `estado_actual: "INACTIVO"`.

---

## 4. Resultados Detallados (Newman TEST)

### 4.1. Ejecución Paso a Paso

| Carpeta / Subcaso | Paso | Método | Endpoint | Esperado | Obtenido | Latencia | Estado |
| :--- | :--- | :---: | :--- | :--- | :--- | :---: | :---: |
| **TC-M02-143** | 00 - Auth Admin | POST | `/sesiones/` | HTTP 200 + token | HTTP 200 OK | 1011 ms | ✅ PASS |
| **TC-M02-143** | 01 - Asociar sensor DIRECTA | POST | `/activos-biologicos/108/sensores` | HTTP 201 + `ACTIVA` + `directa` | HTTP 201 Created (`id_asociacion: 31`) | 164 ms | ✅ PASS |
| **TC-M02-144** | 00 - Auth Admin | POST | `/sesiones/` | HTTP 200 + token | HTTP 200 OK | 431 ms | ✅ PASS |
| **TC-M02-144** | 01 - Asociar sensor AMBIENTAL | POST | `/activos-biologicos/109/sensores` | HTTP 201 + `ACTIVA` + `ambiental` | HTTP 201 Created (`id_asociacion: 32`) | 223 ms | ✅ PASS |
| **TC-M02-145** | 00 - Auth Admin | POST | `/sesiones/` | HTTP 200 + token | HTTP 200 OK | 440 ms | ✅ PASS |
| **TC-M02-145** | 01 - Asociar sensor POBLACIONAL | POST | `/activos-biologicos/83/sensores` | HTTP 201 + `ACTIVA` + `poblacional` | HTTP 201 Created (`id_asociacion: 33`) | 207 ms | ✅ PASS |
| **TC-M02-150** | 00 - Auth Admin | POST | `/sesiones/` | HTTP 200 + token | HTTP 200 OK | 453 ms | ✅ PASS |
| **TC-M02-150** | 01 - Asociar sensor disp. desc. | POST | `/activos-biologicos/110/sensores` | HTTP 201 + advertencia informativa | HTTP 201 Created, `advertencia: null` | 134 ms | ❌ FAIL (Aserción 2) |

### 4.2. Métricas Globales de la Corrida Newman
- **Iteraciones**: 1
- **Peticiones HTTP**: 8 ejecutadas (0 fallidas a nivel de transporte).
- **Scripts de Prueba**: 8 ejecutados.
- **Aserciones Evaluadas**: 14 en total (13 exitosas, 1 fallida).
- **Duración Total**: 3.7 segundos.
- **Tiempo Promedio de Respuesta**: 382 ms (mín: 134 ms, máx: 1011 ms).
- **Exit Code**: **1** (debido al fallo de aserción esperado en TC-M02-150).

### 4.3. Evidencias Textuales de Respuesta

#### Subcaso TC-M02-143 (PASS):
```json
{
  "id_asociacion_activo_sensor": 31,
  "id_activo_biologico": 108,
  "tipo_activo": "INDIVIDUAL",
  "tipo_asociacion": "directa",
  "dispositivo_iot_id": 38,
  "sensor_id": 22,
  "id_infraestructura": 3,
  "fecha_inicio": "2026-09-15T21:17:09.417640Z",
  "fecha_fin": null,
  "estado_asociacion": "ACTIVA",
  "motivo": "Monitoreo biometrico individual TC-M02-143",
  "advertencia": null
}
```

#### Subcaso TC-M02-144 (PASS):
```json
{
  "id_asociacion_activo_sensor": 32,
  "id_activo_biologico": 109,
  "tipo_activo": "INDIVIDUAL",
  "tipo_asociacion": "ambiental",
  "dispositivo_iot_id": 39,
  "sensor_id": 23,
  "id_infraestructura": 3,
  "fecha_inicio": "2026-09-15T21:17:10.151938Z",
  "fecha_fin": null,
  "estado_asociacion": "ACTIVA",
  "motivo": "Monitoreo ambiental compartido infraestructura TC-M02-144",
  "advertencia": null
}
```

#### Subcaso TC-M02-145 (PASS):
```json
{
  "id_asociacion_activo_sensor": 33,
  "id_activo_biologico": 83,
  "tipo_activo": "LOTE",
  "tipo_asociacion": "poblacional",
  "dispositivo_iot_id": 40,
  "sensor_id": 24,
  "id_infraestructura": 3,
  "fecha_inicio": "2026-09-15T21:17:10.987131Z",
  "fecha_fin": null,
  "estado_asociacion": "ACTIVA",
  "motivo": "Monitoreo poblacional lote TC-M02-145",
  "advertencia": null
}
```

#### Subcaso TC-M02-150 (FALLO POR GAP - BLOQUEO REFINADO):
```json
{
  "id_asociacion_activo_sensor": 34,
  "id_activo_biologico": 110,
  "tipo_activo": "INDIVIDUAL",
  "tipo_asociacion": "directa",
  "dispositivo_iot_id": 3,
  "sensor_id": 6,
  "id_infraestructura": 3,
  "fecha_inicio": "2026-09-15T21:17:11.811743Z",
  "fecha_fin": null,
  "estado_asociacion": "ACTIVA",
  "motivo": "Verificacion advertencia dispositivo desconectado TC-M02-150",
  "advertencia": null
}
```
**Fallo exacto reportado por Newman**:
```text
#  failure         detail
1. AssertionError  [TC-M02-150] Respuesta incluye advertencia informativa de dispositivo desconectado
                   expected null not to be null
                   at assertion:2 in test-script
                   inside "TC-M02-150 / 01 - Asociar sensor con dispositivo desconectado"
```

---

## 5. Evidencia Post-condición y Diagnóstico Técnico

### 5.1. Transcripción de `postcondicion_api.log`
```text
[2026-09-15 21:18:59 UTC] === INICIO DE VERIFICACIÓN DE POSTCONDICIONES Y CLEANUP (TEST) ===
[2026-09-15 21:18:59 UTC] Target baseUrl: https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test
[2026-09-15 21:18:59 UTC] Database: 158.69.200.27:5448/sgpmp_test
[2026-09-15 21:19:00 UTC] 1. Autenticación admin obtenida para verificación post-condición.
[2026-09-15 21:19:00 UTC] 2. Re-consultando estado de los 4 activos biológicos vía API...
[2026-09-15 21:19:01 UTC]    GET /activos-biologicos/108 -> HTTP 200
[2026-09-15 21:19:01 UTC]       Activo 108: Estado=ACTIVO, Tipo=INDIVIDUAL, Identificador=MADRE-G53-1788880748, Inalterado: SÍ
[2026-09-15 21:19:02 UTC]    GET /activos-biologicos/109 -> HTTP 200
[2026-09-15 21:19:02 UTC]       Activo 109: Estado=ACTIVO, Tipo=INDIVIDUAL, Identificador=PADRE-G53-1788880748, Inalterado: SÍ
[2026-09-15 21:19:03 UTC]    GET /activos-biologicos/83 -> HTTP 200
[2026-09-15 21:19:03 UTC]       Activo 83: Estado=ACTIVO, Tipo=POBLACIONAL, Identificador=None, Inalterado: SÍ
[2026-09-15 21:19:03 UTC]    GET /activos-biologicos/110 -> HTTP 200
[2026-09-15 21:19:03 UTC]       Activo 110: Estado=ACTIVO, Tipo=INDIVIDUAL, Identificador=MADRE-G53-1788883766399, Inalterado: SÍ
[2026-09-15 21:19:05 UTC] 3. Verificando asociaciones activas creadas durante la corrida Newman...
[2026-09-15 21:19:05 UTC]    Asociaciones ACTIVAS detectadas a desactivar: 4
[2026-09-15 21:19:05 UTC]       ID 31: Activo=108, Sensor=22, Estado=ACTIVA
[2026-09-15 21:19:05 UTC]       ID 32: Activo=109, Sensor=23, Estado=ACTIVA
[2026-09-15 21:19:05 UTC]       ID 33: Activo=83, Sensor=24, Estado=ACTIVA
[2026-09-15 21:19:05 UTC]       ID 34: Activo=110, Sensor=6, Estado=ACTIVA
[2026-09-15 21:19:05 UTC] 4. Ejecutando cleanup_tc_m02_g84 en modalidad append-only (UPDATE fecha_fin y estado_asociacion='INACTIVA')...
[2026-09-15 21:19:06 UTC]    Filas actualizadas a INACTIVA: 4
[2026-09-15 21:19:06 UTC] 5. Confirmando asociaciones activas remanentes...
[2026-09-15 21:19:06 UTC]    Asociaciones ACTIVAS remanentes del Sensor 6 (TC-M02-150): 0 (Esperado: 0)
[2026-09-15 21:19:06 UTC]    Asociaciones ACTIVAS remanentes totales (143, 144, 145, 150): 0 (Esperado: 0)
[2026-09-15 21:19:06 UTC] 6. Verificando inmutabilidad de bitácoras en modulo2.bitacora_auditoria_m02...
[2026-09-15 21:19:06 UTC]    Total registros en bitácora M02: 2045
[2026-09-15 21:19:06 UTC]    Total registros de RF49 en bitácora M02: 25
[2026-09-15 21:19:06 UTC]    Inmutabilidad de bitácora preservada: SÍ (0 registros eliminados ni alterados).
[2026-09-15 21:19:06 UTC] === RESUMEN POSTCONDICIONES ===
[2026-09-15 21:19:06 UTC] Estado Cleanup: EXITOSO (0 asociaciones activas remanentes, preservación append-only).
[2026-09-15 21:19:06 UTC] === FIN DE VERIFICACIÓN DE POSTCONDICIONES ===
```

### 5.2. Diagnóstico Técnico y Referencias de Código
1. **Hardcoding de `advertencia=None`**:
   En [activo_biologico_router.py](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/src/biological_assets/infrastructure/routers/activo_biologico_router.py#L1158-L1171):
   ```python
   resultado = use_case.execute(id_activo, dto, usuario_actual)
   return AsociacionSensorActivoResponse(
       id_asociacion_activo_sensor=resultado.id_asociacion_activo_sensor,
       id_activo_biologico=resultado.id_activo_biologico,
       tipo_activo=resultado.tipo_activo,
       tipo_asociacion=resultado.tipo_asociacion,
       dispositivo_iot_id=resultado.dispositivo_iot_id,
       sensor_id=resultado.sensor_id,
       id_infraestructura=resultado.id_infraestructura,
       fecha_inicio=resultado.fecha_inicio,
       fecha_fin=resultado.fecha_fin,
       estado_asociacion=resultado.estado_asociacion,
       motivo=resultado.motivo,
       advertencia=None,  # <-- GAP FUNCIONAL DE BACKEND
   )
   ```
2. **Ausencia de Puerto e Integración de Telemetría (M03)**:
   En [asociar_sensor_activo_use_case.py](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/src/biological_assets/application/use_cases/gestion/asociar_sensor_activo_use_case.py#L31-L48):
   ```python
   class AsociarSensorActivoUseCase:
       def __init__(
           self,
           db: Session,
           repo: AsociacionSensorActivoRepository,
           activo_repo: ActivoBiologicoRepository,
           sensor_port: SensorConsultaPort,
           infra_port: InfraestructuraConsultaPort,
           bitacora_repo: BitacoraAuditoriaRepository | None = None,
       ) -> None:
           # No existe telemetria_port ni consulta de heartbeat
   ```
3. **Commit de Origen**:
   - `8930482871117a2ce6a517fd5308d6949bd093a8` (fecha: 2026-06-29).
4. **Conclusión Técnica**:
   El fallo no responde a una falta de despliegue de microservicios ni a indisponibilidad de datos en el entorno TEST. Es un **defecto de desarrollo en el código backend de Módulo 2** que no implementó el puerto ni la lógica de advertencia estipulada en RF-49 CU11.

---

## 6. Verificación de Limpieza (Cleanup e Inocuidad)

En cumplimiento de las restricciones estrictas del proyecto:
1. **Creación durante la Prueba**:
   La suite Newman registró cuatro vinculaciones activas en `modulo2.asociaciones_activos_sensores`:
   - ID 31 (Activo 108, Sensor 22)
   - ID 32 (Activo 109, Sensor 23)
   - ID 33 (Activo 83, Sensor 24)
   - ID 34 (Activo 110, Sensor 6)
2. **Desactivación Append-Only**:
   En lugar del `DELETE` que realizaba el script V1, se ejecutó una sentencia `UPDATE` que actualizó `estado_asociacion = 'INACTIVA'`, fijó `fecha_fin = NOW()`, y anexó trazabilidad en el campo `motivo`.
3. **Confirmación de 0 Asociaciones Activas Remanentes**:
   - Para el Sensor 6 (TC-M02-150): **0 asociaciones activas**.
   - Para la totalidad de sensores de la suite (22, 23, 24, 6): **0 asociaciones activas**.
4. **Inmutabilidad de Bitácoras**:
   - Se verificó que `modulo2.bitacora_auditoria_m02` contiene 2045 registros íntegros.
   - Las 4 transacciones de inserción generadas por la corrida quedaron registradas de forma inmutable con sus respectivos hashes criptográficos (registros 2038, 2039, 2040, 2041).
   - Ningún registro de auditoría fue eliminado ni truncado.
5. **Inalterabilidad de Activos Biológicos**:
   Los 4 activos biológicos (108, 109, 83, 110) conservan su estado `ACTIVO`, su infraestructura asignada y sus identificadores originales intactos.

---

## 7. Conclusiones, Diagnóstico Técnico y Dictamen Final

### 7.1. Dictamen de Reevaluación
El estado de **TC-M02-150** se define formalmente como:
⚠️ **BLOQUEO CONFIRMADO POR GAP FUNCIONAL DE BACKEND (NO POR ENTORNO)**.

Los subcasos colaterales **TC-M02-143, 144 y 145** quedan **100% reconfirmados en PASS**.

### 7.2. Registro Formal del Defecto
- **ID Defecto**: `INC-M02-G84-01`
- **Componente**: Módulo 2 — Activos Biológicos / Gestión de Sensores IoT
- **Requisito Funcional**: RF-49 (CU11 — Asociar sensor IoT a un activo biológico)
- **Subcaso Asociado**: TC-M02-150
- **Descripción del Defecto**:
  El endpoint `POST /activos-biologicos/{id_activo}/sensores` retorna sistemáticamente `"advertencia": null` en su payload de respuesta HTTP 201 Created. La causa raíz reside en que `activo_biologico_router.py` (línea 1170) asigna estáticamente `advertencia=None` en el modelo Pydantic `AsociacionSensorActivoResponse`, y `AsociarSensorActivoUseCase` no implementa ni inyecta ningún puerto hacia Módulo 3 (Telemetría) para consultar el estado del heartbeat del dispositivo IoT asociado.
- **Impacto de Negocio**:
  RF-49 se encuentra satisfecho parcialmente (3 de 4 subcasos operativos). Se omite la advertencia de dispositivo desconectado al operador ganadero, impidiendo que el usuario sea alertado oportunamente si un sensor no está transmitiendo datos biométricos o ambientales.
- **Severidad**: Media-Alta (Gap funcional que no bloquea la persistencia pero incumple regla de negocio de notificación).
- **Acción Requerida para Desarrollo**:
  1. Diseñar e inyectar en `AsociarSensorActivoUseCase` un puerto secundario de consulta de telemetría hacia M03 (e.g., `TelemetriaConsultaPort` o consulta al repositorio/servicio de estados de dispositivos).
  2. Evaluar si la última lectura / heartbeat del dispositivo supera el umbral de 30 minutos sin señal.
  3. En caso afirmativo, generar el mensaje de advertencia respectivo (`"Dispositivo IoT desconectado..."`) y propagarlo a la respuesta del router.

### 7.3. Hallazgos Secundarios No Bloqueantes
1. **Fixtures Hardcodeados**:
   La colección Postman `test_tc_m02_g84.json` tiene fijos en las URLs los identificadores de activos (108, 109, 83, 110) y en los bodies los sensores (22, 23, 24, 6) y dispositivos (38, 39, 40, 3). No permite parametrización flexible mediante variables de entorno para otros ambientes sin fixtures coincidentes.
2. **Discordancia entre TEST y DEV**:
   El entorno DEV no cuenta con los registros de activos biológicos 108, 109, 83, 110, lo que imposibilitaría correr esta colección en DEV sin crear previamente los fixtures.
3. **RBAC de Desactivación de Sensores**:
   El endpoint `PATCH /activos-biologicos/{id_activo}/sensores/{id_asociacion}` exige permiso 3 (UPDATE) sobre el recurso 30 (`asociacion_sensor_activo`), el cual actualmente no está asignado al rol `admin` en el entorno TEST (retornando HTTP 403). Se sugiere revisar la matriz de permisos de roles para dicho recurso.

### 7.4. Recomendación
Programar la **Reevaluación V3** una vez que el equipo de desarrollo entregue el Pull Request con la inyección del puerto M03 y el cálculo dinámico del campo `advertencia` en el backend de Módulo 2.
