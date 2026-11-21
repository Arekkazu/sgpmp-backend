# Reevaluación V2 — Caso TC-M02-G85 — RF-49 CU11 — Confirmación de Bloqueo de TC-M02-148 por Incumplimiento de Requisito Explícito (Restricción 3 / FA-04)

---

## 1. Encabezado y Metadatos de Ejecución

| Parámetro | Valor |
| :--- | :--- |
| **RUN_ID** | `G85-REEVAL-V2-20260915-165000` |
| **Fecha de Evaluación V1** | 2026-09-10 |
| **Fecha de Reevaluación V2** | 2026-09-15 16:50:00 UTC |
| **Caso Agrupado** | **TC-M02-G85** (Módulo 2 — Activos Biológicos, RF-49 CU11) |
| **Subcasos Evaluados** | TC-M02-146, TC-M02-147, TC-M02-148 |
| **Entorno de Pruebas** | **TEST** (`https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test`) |
| **Acceso a Base de Datos** | PostgreSQL 16 (`158.69.200.27:5448/sgpmp_test`, usuario `member_qa`) + API REST HTTPS |
| **Herramienta de Ejecución** | Newman CLI v6.2.2 + `newman-reporter-htmlextra` v1.23.1 |
| **Colección Ejecutada** | `tests/Test_Testing/Test_Modulo2/RF-49/TC-M02-G85/test_tc_m02_g85.json` |
| **Reporte HTML Generado** | [reporte_v2.html](./reporte_v2.html) (`tests/Test_Testing/Test_Modulo2/RF-49/TC-M02-G85/EvaluacionV2/RESULTADOS/G85-REEVAL-V2-20260915-165000/reporte_v2.html`) |
| **Resumen JSON Newman** | `tests/Test_Testing/Test_Modulo2/RF-49/TC-M02-G85/EvaluacionV2/RESULTADOS/G85-REEVAL-V2-20260915-165000/newman_summary_v2.json` |
| **Veredicto Global** | ⚠️ **BLOQUEADO (2/3 PASS, 1 BLOQUEADO POR INCUMPLIMIENTO DE REQUISITO EXPLÍCITO)** |

---

## 2. Objetivo de la Reevaluación y Resumen Ejecutivo

### 2.1. Contexto V1 y Descarte de la Hipótesis Vaga Original
En la corrida V1 del 2026-09-10, el caso agrupado **TC-M02-G85** quedó asentado con veredicto **BLOQUEADO (2 PASSED, 1 BLOCKED)**, justificando el bloqueo de TC-M02-148 con la siguiente hipótesis vaga:
> *"Subcaso bloqueado por dependencia externa no implementada: en el sistema actual el catálogo I3P-1 no aplica a especies, los sensores no tienen atributo de especie en M09 y el backend no valida especie."*

### 2.2. Hallazgos V2: Evidencia Contractual y Conflicto Arquitectónico
Contrastando los requisitos formales de **RF-49 (CU11 — Asociar sensor IoT a un activo biológico)** con el código fuente real, se identificaron discrepancias profundas:

1. **Requisito Contractual Explícito Incumplido**:
   - **Precondición 5**: Exige la disponibilidad del catálogo I3P-1 para verificar la compatibilidad entre el sensor y la especie zootécnica del activo.
   - **Restricción 3**: Establece textualmente: *"El sensor debe ser compatible con la especie del activo biológico según el catálogo I3P-1 (M09)"*.
   - **Flujo Alterno FA-04**: Define que ante una incompatibilidad biológica, el sistema debe responder `HTTP 400 Bad Request` indicando `"Incompatibilidad biológica"`.
2. **Decisión Documentada de Omitir la Implementación (Commit 893048287, 2026-06-29)**:
   En `anotaciones/modulo_2/cu11_gaps_bd_rf49.md` (líneas 92-96), el equipo de desarrollo documentó textualmente al construir el endpoint:
   > *"El catálogo I3P-1 (M09) que define compatibilidad entre `sensor.categoria` y `especie` no tiene tabla en la DB actual. Decisión: La validación de compatibilidad no se implementa en este CU. Se documenta como gap. Cuando la tabla de catálogo exista, agregar validación en el use case antes de V8."*
3. **Conflicto de Nomenclatura del Catálogo I3P-1**:
   - En los requisitos de negocio (RF-49), "I3P-1" fue concebido conceptualmente como una matriz de compatibilidad sensor-especie.
   - En la arquitectura de software real (`src/telemetry/domain/entities/telemetria.py` y `src/prediction/infrastructure/adapters/variable_i3p1_m09_adapter.py`), "I3P-1" es el estándar de **variables físico-químicas ambientales** (`modulo9.variables_ambientales`: temperatura, pH, oxígeno, amoniaco).
   - Existen dos conceptos distintos designados bajo el mismo término ("I3P-1").
4. **Modelo de Datos Agnóstico en M09**:
   La tabla `modulo9.sensores` ([sensor_model.py](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/src/configuration/infrastructure/models/sensor_model.py#L17-L48)) modela sensores como hardware universal para variables físicas (`categoria: TEMPERATURA, OXIGENO, PH`). No tiene columna `id_especie` ni tabla intermedia de especies compatibles.
5. **Precondición Irreal de la Prueba y Enmascaramiento Territorial**:
   - La suite Newman en el subcaso TC-M02-148 envía `POST /activos-biologicos/279/sensores` con `sensor_id: 1` asumiendo que el sensor 1 es "de aves" y el activo 279 es "bovino".
   - En realidad, el sensor 1 es `"Sensor temperatura estanque-01"` (acuícola/ambiental).
   - Además, el activo 279 reside en la Infraestructura 48 (Finca 57) mientras el sensor 1 reside en la Infraestructura 1 (Finca 1). Al ejecutarse, el backend evalúa primero la coherencia territorial (validación `V6`) y rechaza con `HTTP 409 INFRAESTRUCTURA_INCOMPATIBLE`, impidiendo que el flujo alcance si quiera la capa donde debería validarse la especie.

### 2.3. Tabla Comparativa de Resultados

| Sub-caso | Enfoque Evaluado | Entorno | Resultado Esperado (RF-49) | Obtenido en Reevaluación V2 | Aserciones | Veredicto V2 |
| :--- | :--- | :---: | :--- | :--- | :---: | :---: |
| **TC-M02-146** | Rechazo activo en BAJA | TEST | HTTP 422 + `ACTIVO_EN_BAJA` | HTTP 422 Unprocessable Entity, `error_code: ACTIVO_EN_BAJA` | 4/4 | ✅ **PASS** |
| **TC-M02-147** | Rechazo territorial fincas distintas | TEST | HTTP 409 + `INFRAESTRUCTURA_INCOMPATIBLE` | HTTP 409 Conflict, `error_code: INFRAESTRUCTURA_INCOMPATIBLE` | 4/4 | ✅ **PASS** |
| **TC-M02-148** | Incompatibilidad de especie sensor-activo | TEST | HTTP 400 + "incompatibilidad" | HTTP 409 Conflict (Rechazo territorial antes de evaluar especie; regla de especie inexistente en backend) | 1/3 | ❌ **BLOQUEADO (INCUMPLIMIENTO REQUISITO EXPLÍCITO)** |

---

## 3. Estado Previo de la Base de Datos (Pre-condición vía API REST)

Previamente a la corrida Newman, se verificó el estado y configuración de todos los fixtures en TEST mediante la API REST y se registró íntegramente en [precondicion_api.log](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/tests/Test_Testing/Test_Modulo2/RF-49/TC-M02-G85/EvaluacionV2/RESULTADOS/G85-REEVAL-V2-20260915-165000/precondicion_api.log).

### Transcripción de `precondicion_api.log`:
```text
[2026-09-15 21:50:20 UTC] === INICIO DE VERIFICACIÓN DE PRECONDICIONES (TEST API) — TC-M02-G85 ===
[2026-09-15 21:50:20 UTC] Target baseUrl: https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test
[2026-09-15 21:50:20 UTC] 1. Solicitando autenticación admin: POST https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test/sesiones/
[2026-09-15 21:50:22 UTC]    Respuesta Auth HTTP 200
[2026-09-15 21:50:22 UTC]    Token JWT capturado exitosamente.
[2026-09-15 21:50:22 UTC] 2. Verificando Activo 10 (Precondición TC-M02-146: activo en estado BAJA)...
[2026-09-15 21:50:23 UTC]    GET /activos-biologicos/10 -> HTTP 200
[2026-09-15 21:50:23 UTC]       ID: 10, Identificador: BOV-006, Tipo: INDIVIDUAL, Estado: BAJA, id_estado: 6, Infra: 1
[2026-09-15 21:50:23 UTC]       Confirmación: Activo 10 está en estado BAJA (id_estado = 6). Precondición CUMPLIDA.
[2026-09-15 21:50:23 UTC] 3. Verificando Activo 108 (Precondición TC-M02-147: activo ACTIVO en Finca 1)...
[2026-09-15 21:50:24 UTC]    GET /activos-biologicos/108 -> HTTP 200
[2026-09-15 21:50:24 UTC]       ID: 108, Identificador: MADRE-G53-1788880748, Tipo: INDIVIDUAL, Estado: ACTIVO, Infra: 3
[2026-09-15 21:50:24 UTC]       Infraestructura 3: Nombre=Alevinera-01, Tipo=Estanque, Finca=1
[2026-09-15 21:50:24 UTC]       Confirmación: Activo 108 ACTIVO en Infraestructura 3 (Finca 1). Precondición CUMPLIDA.
[2026-09-15 21:50:24 UTC] 4. Verificando Sensor 8 y Dispositivo 4 (Precondición TC-M02-147: sensor en Finca 2)...
[2026-09-15 21:50:25 UTC]    GET /configuracion/dispositivos-iot/4 -> HTTP 200
[2026-09-15 21:50:25 UTC]       Dispositivo 4: Serial=IOT-TRU01-VLC-001, Estado Activo=True, Infra=1
[2026-09-15 21:50:26 UTC]    GET /configuracion/dispositivos-iot/4/sensores -> HTTP 200
[2026-09-15 21:50:26 UTC]       Sensores en Dispositivo 4: {"total": 2, "items": [{"id_sensores": 9, "nombre": "Sensor oxígeno disuelto canal-trucha-01", "id_dispositivo_iot": 4, "es_activo": true, "categoria": "OXIGENO"}, {"id_sensores": 8, "nombre": "Sensor temperatura canal-trucha-01", "id_dispositivo_iot": 4, "es_activo": true, "categoria": "TEMPERATURA"}]}
[2026-09-15 21:50:27 UTC]    GET /configuracion/infraestructuras/4 -> HTTP 200
[2026-09-15 21:50:27 UTC]       Infraestructura 4: Nombre=Canal-Trucha-01, Tipo=Estanque, Finca=2
[2026-09-15 21:50:27 UTC]       Confirmación: Sensor 8 en Infraestructura 4 (Finca 2) vs Activo 108 en Infraestructura 3 (Finca 1). Precondición CUMPLIDA.
[2026-09-15 21:50:27 UTC] 5. Verificando Activo 279 (Precondición TC-M02-148: activo ACTIVO, id_especie=40, infra=48)...
[2026-09-15 21:50:28 UTC]    GET /activos-biologicos/279 -> HTTP 200
[2026-09-15 21:50:28 UTC]       ID: 279, Identificador: QAJE-CREC-OK, Tipo: INDIVIDUAL, Estado: ACTIVO, id_especie: 40, Infra: 48
[2026-09-15 21:50:28 UTC]       Confirmación: Activo 279 ACTIVO con id_especie=40 en infra 48. Precondición CUMPLIDA.
[2026-09-15 21:50:28 UTC] 6. Verificando Sensor 1 y Dispositivo 1 en Catálogo M09...
[2026-09-15 21:50:28 UTC]    GET /configuracion/dispositivos-iot/1 -> HTTP 200
[2026-09-15 21:50:28 UTC]       Dispositivo 1: Serial=IOT-EST01-HLA-001, Estado Activo=True, Infra=1
[2026-09-15 21:50:29 UTC]    GET /configuracion/dispositivos-iot/1/sensores -> HTTP 200
[2026-09-15 21:50:29 UTC]       Sensores en Dispositivo 1: {"total": 3, "items": [{"id_sensores": 3, "nombre": "Sensor oxígeno disuelto estanque-01", "id_dispositivo_iot": 1, "es_activo": true, "categoria": "OXIGENO"}, {"id_sensores": 2, "nombre": "Sensor pH estanque-01", "id_dispositivo_iot": 1, "es_activo": true, "categoria": "PH"}, {"id_sensores": 1, "nombre": "Sensor temperatura estanque-01", "id_dispositivo_iot": 1, "es_activo": true, "categoria": "TEMPERATURA"}]}
[2026-09-15 21:50:29 UTC]       Sensor 1: id=1, nombre='Sensor temperatura estanque-01', categoria='TEMPERATURA', es_activo=True
[2026-09-15 21:50:29 UTC]       Confirmación: Sensor 1 tiene categoria=TEMPERATURA, carece de atributo de especie o compatibilidad biológica. Precondición CUMPLIDA.
[2026-09-15 21:50:29 UTC] === RESUMEN PRECONDICIONES ===
[2026-09-15 21:50:29 UTC] Todas las precondiciones de fixtures en TEST han sido verificadas y se encuentran conformes para la corrida.
[2026-09-15 21:50:29 UTC] === FIN DE VERIFICACIÓN DE PRECONDICIONES ===
```

---

## 4. Resultados Detallados de la Ejecución (Newman)

### 4.1. Desglose de Pasos por Subcaso

| Subcaso | Paso | Método | Endpoint | Código Esperado | Código Obtenido | Latencia | Estado |
| :--- | :--- | :---: | :--- | :---: | :---: | :---: | :---: |
| **TC-M02-146** | 00 - Auth Admin | POST | `/sesiones/` | 200 | 200 OK | 1071 ms | ✅ PASS |
| **TC-M02-146** | 01 - Rechazar activo en BAJA | POST | `/activos-biologicos/10/sensores` | 422 | 422 Unprocessable Entity | 159 ms | ✅ PASS |
| **TC-M02-147** | 00 - Auth Admin | POST | `/sesiones/` | 200 | 200 OK | 367 ms | ✅ PASS |
| **TC-M02-147** | 01 - Rechazar fincas distintas | POST | `/activos-biologicos/108/sensores` | 409 | 409 Conflict | 183 ms | ✅ PASS |
| **TC-M02-148** | 00 - Auth Admin | POST | `/sesiones/` | 200 | 200 OK | 476 ms | ✅ PASS |
| **TC-M02-148** | 01 - Rechazar incompatibilidad especie | POST | `/activos-biologicos/279/sensores` | 400 | 409 Conflict | 221 ms | ❌ FAIL |

### 4.2. Métricas Globales de la Corrida Newman
- **Iteraciones**: 1
- **Peticiones HTTP Ejecutadas**: 6 (todas completadas a nivel de red).
- **Scripts de Prueba**: 6 ejecutados.
- **Aserciones Evaluadas**: 11 totales (9 aprobadas, 2 fallidas).
- **Duración Total**: 2.9 segundos.
- **Tiempo Promedio de Respuesta**: 412 ms (mín: 159 ms, máx: 1071 ms).
- **Exit Code**: **1** (debido a las 2 aserciones fallidas de TC-M02-148).

### 4.3. Evidencias Textuales de Respuesta y Fallos

#### Subcaso TC-M02-146 (PASS):
```json
{
  "error_code": "ACTIVO_EN_BAJA",
  "message": "El activo 10 se encuentra en estado BAJA y no admite nuevas asociaciones de sensores.",
  "fields": [],
  "timestamp": "2026-09-15T21:50:44.132487+00:00"
}
```
*Aserciones evaluadas*: Status 422 (PASS), error_code `ACTIVO_EN_BAJA` (PASS), mensaje contiene 'baja' (PASS).

#### Subcaso TC-M02-147 (PASS):
```json
{
  "error_code": "INFRAESTRUCTURA_INCOMPATIBLE",
  "message": "Error de ubicación. El activo está en la finca 1 y el sensor en la finca 2. La asociación solo es permitida dentro de la misma unidad territorial.",
  "fields": [],
  "timestamp": "2026-09-15T21:50:44.779555+00:00"
}
```
*Aserciones evaluadas*: Status 409 (PASS), error_code `INFRAESTRUCTURA_INCOMPATIBLE` (PASS), mensaje contiene 'unidad territorial' (PASS).

#### Subcaso TC-M02-148 (BLOQUEADO / FAIL):
```json
{
  "error_code": "INFRAESTRUCTURA_INCOMPATIBLE",
  "message": "Error de ubicación. El activo está en la finca 57 y el sensor en la finca 1. La asociación solo es permitida dentro de la misma unidad territorial.",
  "fields": [],
  "timestamp": "2026-09-15T21:50:45.601564+00:00"
}
```
**Aserciones fallidas reportadas por Newman**:
```text
#  failure         detail
1. AssertionError  [TC-M02-148] Código HTTP es 400 Bad Request
                   expected response to have status code 400 but got 409
                   at assertion:0 in test-script
                   inside "TC-M02-148 / 01 - Rechazar incompatibilidad de especie sensor-activo"

2. AssertionError  [TC-M02-148] Mensaje indica incompatibilidad biológica de especie
                   expected 'error de ubicación. el activo está en…' to include 'incompatibilidad'
                   at assertion:1 in test-script
                   inside "TC-M02-148 / 01 - Rechazar incompatibilidad de especie sensor-activo"
```

*Análisis del fallo*: El backend respondió legítimamente con `HTTP 409 INFRAESTRUCTURA_INCOMPATIBLE` porque el activo 279 está registrado en la Finca 57 (Infraestructura 48) y el sensor 1 en la Finca 1 (Infraestructura 1). La validación territorial `V6` se ejecuta en la línea 109 de `AsociarSensorActivoUseCase`, deteniendo la ejecución antes de que cualquier otra regla pudiera evaluarse. No obstante, aun si ambas entidades estuviesen en la misma finca, el backend retornaría `HTTP 201 Created` puesto que **la validación de compatibilidad de especie no existe en el código**.

---

## 5. Evidencia de Estado en BD PostgreSQL TEST (Post-condición y Auditoría)

### 5.1. Transcripción de `postcondicion_api.log`
```text
[2026-09-15 21:51:20 UTC] === INICIO DE VERIFICACIÓN DE POSTCONDICIONES Y CLEANUP (TEST) — TC-M02-G85 ===
[2026-09-15 21:51:20 UTC] Target baseUrl: https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test
[2026-09-15 21:51:20 UTC] Database: 158.69.200.27:5448/sgpmp_test
[2026-09-15 21:51:22 UTC] 1. Autenticación admin obtenida para verificación post-condición.
[2026-09-15 21:51:22 UTC] 2. Re-consultando estado de los activos biológicos vía API...
[2026-09-15 21:51:22 UTC]    GET /activos-biologicos/10 -> HTTP 200
[2026-09-15 21:51:22 UTC]       Activo 10: Estado=BAJA, Tipo=INDIVIDUAL, Identificador=BOV-006, Inalterado: SÍ
[2026-09-15 21:51:23 UTC]    GET /activos-biologicos/108 -> HTTP 200
[2026-09-15 21:51:23 UTC]       Activo 108: Estado=ACTIVO, Tipo=INDIVIDUAL, Identificador=MADRE-G53-1788880748, Inalterado: SÍ
[2026-09-15 21:51:24 UTC]    GET /activos-biologicos/279 -> HTTP 200
[2026-09-15 21:51:24 UTC]       Activo 279: Estado=ACTIVO, Tipo=INDIVIDUAL, Identificador=QAJE-CREC-OK, Inalterado: SÍ
[2026-09-15 21:51:26 UTC] 3. Verificando asociaciones activas en modulo2.asociaciones_activos_sensores...
[2026-09-15 21:51:26 UTC]    Asociaciones ACTIVAS remanentes de TC-M02-G85: 0 (Esperado: 0)
[2026-09-15 21:51:26 UTC]    Total asociaciones activas para pares (1,10), (8,108), (1,279): 0 (Esperado: 0)
[2026-09-15 21:51:26 UTC]    Confirmación: Ningún subcaso generó registros de asociación en BD (todos fueron rechazos HTTP 422 y 409). 0 residuos.
[2026-09-15 21:51:26 UTC] 4. Verificando inmutabilidad de bitácoras en modulo2.bitacora_auditoria_m02...
[2026-09-15 21:51:26 UTC]    Total registros en bitácora modulo2: 2054
[2026-09-15 21:51:26 UTC]    Inmutabilidad de bitácora preservada: SÍ (0 registros eliminados ni alterados, transacciones íntegras).
[2026-09-15 21:51:27 UTC] === RESUMEN POSTCONDICIONES ===
[2026-09-15 21:51:27 UTC] Estado Cleanup: EXITOSO (0 asociaciones activas generadas ni remanentes, activos e infraestructura inalterados).
[2026-09-15 21:51:27 UTC] === FIN DE VERIFICACIÓN DE POSTCONDICIONES ===
```

### 5.2. Referencias Literales de Código y Causa Raíz Técnica

1. **Ausencia de Regla de Negocio de Especie en Caso de Uso**:
   En [asociar_sensor_activo_use_case.py](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/src/biological_assets/application/use_cases/gestion/asociar_sensor_activo_use_case.py#L50-L181), el método `execute` procesa 10 validaciones explícitas (`V1` a `V8c`), cubriendo existencia, estado del activo, estado del sensor, estado del dispositivo, asignación a infraestructura territorial y cardinalidades DIRECTA/POBLACIONAL. **No existe ninguna comparación entre la especie del activo (`activo.id_especie`) y el sensor.**
2. **Modelo de Sensores Agnóstico a Taxonomía Animal en M09**:
   En [sensor_model.py](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/src/configuration/infrastructure/models/sensor_model.py#L29-L38), la tabla `modulo9.sensores` contiene únicamente:
   ```python
   id_sensores: Mapped[int] = mapped_column(Integer, primary_key=True)
   id_dispositivo_iot: Mapped[int] = mapped_column(Integer, nullable=False)
   nombre: Mapped[str] = mapped_column(String(100), nullable=False)
   categoria: Mapped[Optional[str]] = mapped_column(String(30))
   es_activo: Mapped[bool] = mapped_column(Boolean, nullable=False)
   ```
   No existe relación con especies ni matriz de compatibilidad biológica.
3. **Catálogo I3P-1 Real en Código (Variables Ambientales)**:
   En [variable_i3p1_m09_adapter.py](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/src/prediction/infrastructure/adapters/variable_i3p1_m09_adapter.py#L18) y [telemetria.py](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/src/telemetry/domain/entities/telemetria.py#L46-L60), I3P-1 mapea a `modulo9.variables_ambientales` (temperatura, pH, oxígeno disuelto, etc.) para control metrológico de telemetría.
4. **Decisión Documental de Desarrollo**:
   En [cu11_gaps_bd_rf49.md](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/anotaciones/modulo_2/cu11_gaps_bd_rf49.md#L92-L96) (commit `893048287`, 2026-06-29), se documentó explícitamente:
   > *"El catálogo I3P-1 (M09) que define compatibilidad entre sensor.categoria y especie no tiene tabla en la DB actual. Decisión: La validación de compatibilidad no se implementa en este CU. Se documenta como gap."*

---

## 6. Verificación de Limpieza (Cleanup e Inocuidad)

1. **Inocuidad por Naturaleza de la Suite**:
   Los 3 subcasos de TC-M02-G85 son escenarios de validación negativa que culminaron en códigos de error HTTP de la familia 4xx (`422` en TC-M02-146, `409` en TC-M02-147, `409` en TC-M02-148).
2. **0 Inserciones Huérfanas**:
   Se consultó directamente `modulo2.asociaciones_activos_sensores` y se constató que existen **0 registros residuales o activos** asociados a los pares de prueba `(1, 10)`, `(8, 108)` y `(1, 279)`.
3. **Inalterabilidad de Activos Biológicos**:
   Los activos `10` (`BAJA`), `108` (`ACTIVO`, Finca 1) y `279` (`ACTIVO`, Finca 57) preservan inalterada su configuración, estado y atributos.
4. **Preservación Append-Only en Bitácoras**:
   La tabla `modulo2.bitacora_auditoria_m02` mantiene sus 2054 registros íntegros con sus hashes criptográficos, confirmando que ninguna transacción destructiva ni truncamiento tuvo lugar.

---

## 7. Conclusiones, Diagnóstico Técnico y Dictamen Final

### 7.1. Dictamen de Reevaluación
El subcaso **TC-M02-148** queda formalmente dictaminado como:
⚠️ **BLOQUEO CONFIRMADO POR INCUMPLIMIENTO DE REQUISITO EXPLÍCITO (RESTRICCIÓN 3 Y FA-04 DE RF-49)**.

Los subcasos colaterales **TC-M02-146** y **TC-M02-147** quedan **100% confirmados en PASS**.

### 7.2. Registro Formal del Defecto

- **ID Defecto Propuesto**: `INC-M02-G85-01`
- **Requisito Funcional**: RF-49 (CU11 — Asociar sensor IoT a un activo biológico).
- **Cláusulas Contractuales Incumplidas**:
  - **Precondición 5**: Exigencia del catálogo I3P-1 para validar compatibilidad.
  - **Restricción 3**: *"El sensor debe ser compatible con la especie del activo biológico según el catálogo I3P-1 (M09)"*.
  - **Flujo Alterno FA-04**: Rechazo con `HTTP 400 Bad Request` y mensaje descriptivo de *"Incompatibilidad biológica"*.
- **Descripción del Defecto**:
  El endpoint `POST /activos-biologicos/{id_activo}/sensores` no implementa ninguna verificación de compatibilidad entre la especie del activo biológico y el tipo/categoría del sensor asociado. El modelo de datos en M09 (`modulo9.sensores`) no cuenta con atributo ni relación de especie, y el caso de uso `AsociarSensorActivoUseCase` no contempla la regla en su flujo de validación. Como resultado, el backend nunca genera el `HTTP 400 Bad Request` estipulado ante incompatibilidad biológica.
- **Clasificación**: **No conformidad funcional mayor** (requisito formalmente especificado en RF-49 pero intencionalmente omitido en desarrollo durante el commit `893048287` sin actualizar el documento de requisitos).
- **Impacto de Negocio**:
  Permite que operadores asocien potencialmente sensores configurados para monitoreo de ciertas especies (o infraestructuras específicas) a activos zootécnicos taxonómicamente dispares si coinciden en la misma finca.
- **Plan de Acción Requerido Multi-Área**:
  1. **Análisis Funcional**: Resolver el conflicto de nomenclatura "I3P-1" (aclarar si debe existir un catálogo de compatibilidad zootécnica o si los sensores se declaran universales). Si se declara universal, modificar formalmente el RF-49 eliminando la Precondición 5, Restricción 3 y FA-04.
  2. **Arquitectura**: En caso de ratificarse el requisito, diseñar la migración Alembic en M09 para crear la tabla `modulo9.compatibilidad_sensores_especies` y exponer el puerto correspondiente hacia M02.
  3. **Desarrollo**: Incorporar la validación en `AsociarSensorActivoUseCase` retornando `HTTP 400 Bad Request` conforme a FA-04, e incluir dicho código de respuesta en el contrato OpenAPI del endpoint.
  4. **QA**: Ajustar la colección Newman `test_tc_m02_g85.json` para utilizar fixtures realistas dentro de la misma unidad territorial territorial una vez que el modelo esté operativo.

### 7.3. Hallazgos Secundarios No Bloqueantes
1. **Conflicto de Nomenclatura I3P-1**: El término I3P-1 está sobrecargado: para el negocio representaba compatibilidad especie-sensor, pero en arquitectura e implementación representa variables fisicoquímicas ambientales de telemetría.
2. **Precondición Irreal de la Prueba en V1**: El test asumió que el sensor 1 era "de aves", cuando en realidad es un sensor de temperatura de estanque acuícola sin taxonomía asignada.
3. **Enmascaramiento por Territorialidad**: La petición de TC-M02-148 utiliza activos e infraestructuras en fincas diferentes (Finca 57 vs Finca 1), provocando que falle en `V6` (`409 INFRAESTRUCTURA_INCOMPATIBLE`) antes de poder evaluar cualquier otra lógica.
4. **Contrato OpenAPI Desalineado**: El OpenAPI de TEST no documenta `HTTP 400` para `POST /activos-biologicos/{id_activo}/sensores`.
5. **Hardcoding de Identificadores**: Ausencia de parametrización mediante variables de entorno en la colección Postman.

### 7.4. Recomendación de Seguimiento
- **Escalar formalmente** a Análisis Funcional, Arquitectura y Desarrollo.
- **NO programar Reevaluación V3** hasta que se defina si el requisito se ratifica (con migración y código nuevo) o si se descarta formalmente del RF-49 por cambio de alcance.
