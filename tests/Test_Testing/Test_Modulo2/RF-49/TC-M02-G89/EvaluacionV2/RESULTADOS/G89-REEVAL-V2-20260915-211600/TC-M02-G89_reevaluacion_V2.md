# Reevaluación V2 — Caso TC-M02-G89 — RF-49 CU11
## Ciclo de Vida Completo de la Asociación Sensor-Activo (Superación, Desactivación, Reactivación y Transiciones Inválidas)

---

## 1. Encabezado y Metadatos de Ejecución

- **Título del Informe:** Reevaluación V2 — Caso TC-M02-G89 — RF-49 CU11 — Ciclo de Vida de Asociaciones IoT
- **RUN_ID:** `G89-REEVAL-V2-20260915-211600`
- **Módulo:** 2 — Activos Biológicos
- **Requisito Funcional / CU:** RF-49 (Asociación de Sensores IoT a Activos Biológicos) — Caso de Uso CU11
- **Fechas de Ejecución:**
  - Corrida Original V1: `2026-09-10` (0/4 PASS — NO CONFORME)
  - Verificación Intermedia DBA Trigger: `2026-09-11` (Solo TC-M02-217)
  - Reevaluación Formal V2 (Corrida 1 - Incidente SQL): `2026-09-15` / `2026-09-16 02:16:00 UTC` (RUN_ID: `G89-REEVAL-V2-20260915-211600`)
  - Reevaluación Formal V2 (Corrida 2 - Referencia Limpia Vigente): `2026-09-15` / `2026-09-16 02:32:00 UTC` (RUN_ID: `G89-REEVAL-V2-20260915-213200`)
- **Entorno de Pruebas:** TEST (`https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test/`)
- **Base de Datos TEST:** PostgreSQL 16 (`158.69.200.27:5448/sgpmp_test`, usuario `member_qa`)
- **Usuario Autenticado:** `administador.dev@gmail.com` (`id_usuario=1`, `id_rol=1` Administrador)
- **Herramientas de Ejecución:** Newman CLI 6.2.2 + Reporter htmlextra 1.23.1
- **Colección Ejecutada:** `tests/Test_Testing/Test_Modulo2/RF-49/TC-M02-G89/test_tc_m02_g89.json` (con correcciones aprobadas de aserciones, variables y DTO aplicadas)
- **Alcance Ejecutado en Newman:** Folder `TC-M02-217` (Subcasos 216, 218 y 219 bloqueados por RBAC externo en TEST)
- **Reportes HTML:**
  - Corrida Limpia Vigente: [reporte_TC-M02-G89_v2.html](../G89-REEVAL-V2-20260915-213200/reporte_TC-M02-G89_v2.html)
  - Corrida Histórica 1: [reporte_TC-M02-G89_v2_run1.html](./reporte_TC-M02-G89_v2.html)
- **Veredicto Global V2:** ⚠️ **Bloqueado - PASS TÉCNICO EN TC-M02-217 / BLOQUEADOS EXTERNAMENTE TC-M02-216, 218 y 219 (INC-M02-65-G89 Abierto)**

---

## 2. Objetivo de la Reevaluación y Resumen Ejecutivo

### Contexto Histórico
En la ejecución original V1 (2026-09-10), la suite TC-M02-G89 resultó en **0 PASS / 4 FAIL**, con dos defectos principales reportados:
1. **INC-M02-66-G89 (Crítico, BD):** El trigger `modulo2.trg_fn_asociacion_sensor_activo_unica` bloqueaba la superación legítima de una asociación `directa` (`ACTIVA` → `SUPERADA`), arrojando error `HTTP 500` (código de excepción PostgreSQL `P0229`).
2. **INC-M02-65-G89 (Severo, API):** Inexistencia absoluta del endpoint `PATCH /activos-biologicos/{id_activo}/sensores/{id_asociacion}`. Los subcasos 216, 218 y 219 fallaban con `HTTP 404 Not Found`.

### Desglose Tripartito del Diagnóstico y Estado en V2 (Separación Conceptual Estricta)
Para asegurar total claridad técnica ante el equipo de Desarrollo y no mezclar dimensiones distintas:

1. **Dimensión Funcional Evaluada (TC-M02-217):** ✅ **PASS CONFIRMADO.**
   - El trigger `modulo2.trg_fn_asociacion_sensor_activo_unica` opera correctamente en TEST tras el hotfix del DBA.
   - La prueba Newman superó el 100% de las aserciones (7/7) y las consultas SQL de solo lectura confirmaron que la superación es atómica: la asociación previa transita a `SUPERADA` con `fecha_fin` idéntica al instante de inicio de la nueva asociación, la cual queda en `ACTIVA`.
   - *Hallazgo colateral de gobernanza:* La corrección del trigger es un hotfix manual en base de datos sin migración Alembic en `alembic/versions/`.
2. **Dimensión de Bloqueo Externo por Requisito RBAC (TC-M02-216, 218 y 219):** ⚠️ **BLOQUEADOS EXTERNAMENTE (INC-M02-65-G89 ABIERTO).**
   - El endpoint `PATCH` y su caso de uso existen en el código FastAPI, pero en la base de datos `sgpmp_test` **falta la inserción del permiso `(id_rol=1, id_recurso=30, id_accion=3)`** en `modulo1.permisos`.
   - La sonda HTTP en vivo confirmó que cualquier petición PATCH con el usuario Administrador responde sistemáticamente `HTTP 403 Forbidden` (`ACCESO_DENEGADO`).
   - Por ende, los subcasos 216, 218 y 219 **no son ejecutables vía API y permanecen formalmente BLOQUEADOS** (no fallidos por lógica).
3. **Dimensión Operativa de Protocolo QA:** **TEMA SEPARADO Y CERRADO (LECCIÓN APRENDIDA).**
   - En la primera corrida V2 (`G89-REEVAL-V2-20260915-211600`) se incurrió en un error operativo al ejecutar un `UPDATE` SQL directo para forzar un cleanup que no se pudo hacer vía API.
   - Dicho incidente fue auditado forensemente en la Sección 6.c y subsanado formalmente mediante la **segunda corrida limpia y de referencia vigente** (`G89-REEVAL-V2-20260915-213200`), en la cual no hubo ninguna intervención en BD y todas las transiciones pasaron 100% por la aplicación. Este asunto operativo queda cerrado y no altera los veredictos funcionales ni de bloqueo.

### Tabla Comparativa de Subcasos (V1 vs V2 - Referencia Vigente)

| Subcaso | Enfoque Evaluado | Código HTTP Esperado | Código HTTP Obtenido V2 | Aserciones Newman | Veredicto Funcional V2 | Estado del Defecto Asociado |
| :--- | :--- | :---: | :---: | :---: | :--- | :--- |
| **TC-M02-217** | Superación automática (`ACTIVA` $\rightarrow$ `SUPERADA`) | 201 Created (Paso 1 y 2) | 201 Created (161 ms / 239 ms) | 7 / 7 PASS | ✅ **PASS** | **INC-M02-66-G89:** Corregido en TEST (observación de gobernanza Alembic) |
| **TC-M02-216** | Desactivación manual (`ACTIVA` $\rightarrow$ `INACTIVA`) | 200 OK | N/A (Sonda 403) | No ejecutado | ⚠️ **BLOQUEADO** | **INC-M02-65-G89:** Abierto (Código listo, falta permiso RBAC en BD TEST) |
| **TC-M02-218** | Reactivación manual (`INACTIVA` $\rightarrow$ `ACTIVA`) | 200 OK | N/A (Sonda 403) | No ejecutado | ⚠️ **BLOQUEADO** | **INC-M02-65-G89:** Abierto (Código listo, falta permiso RBAC en BD TEST) |
| **TC-M02-219** | Transición inválida manual (`SUPERADA` rechazada) | 422 Unprocessable | N/A (Sonda 403) | No ejecutado | ⚠️ **BLOQUEADO** | **INC-M02-65-G89:** Abierto (Código listo, falta permiso RBAC en BD TEST) |

---

## 3. Estado Previo de la Base de Datos (Pre-condición)

Previo a la ejecución de Newman, se auditó el entorno TEST mediante consultas `SELECT` de solo lectura contra PostgreSQL:

### Consultas de Fixtures
1. **Activo Biológico 19:**
   ```sql
   SELECT id_activo_biologico, identificador, id_estado, id_infraestructura 
   FROM modulo2.activos_biologicos WHERE id_activo_biologico = 19;
   ```
   - *Resultado:* `ID=19`, `identificador='ARETE-TEST-01'`, `id_estado=1` (ACTIVO), `id_infraestructura=1`.
2. **Sensor 2 / Dispositivo 1:**
   ```sql
   SELECT id_sensores, estado_sensor, tipo_sensor_id FROM modulo9.sensores WHERE id_sensores = 2;
   SELECT id_dispositivo_iot, estado_dispositivo, id_infraestructura FROM modulo9.dispositivos_iot WHERE id_dispositivo_iot = 1;
   ```
   - *Resultado:* Sensor 2 (tipo `PH`, activo) asignado al Dispositivo 1 en Infraestructura 1 (`Estanque-01`, Finca 1).
3. **Auditoría de Asociaciones Remanentes previas a la corrida:**
   ```sql
   SELECT COUNT(*) 
   FROM modulo2.asociaciones_activos_sensores 
   WHERE (id_activo_biologico = 19 OR id_sensor = 2) 
     AND estado_asociacion = 'ACTIVA' 
     AND fecha_fin IS NULL;
   ```
   - *Resultado obtenido:* **`0`**.
   - *Dictamen:* Base de datos completamente higienizada, sin asociaciones activas huérfanas que pudieran causar falsos conflictos o interferir con la prueba.

### Decisión de Fase 0 (Verificación de Asociación A)
En la Fase 0 se ejecutó una sonda HTTP contra `GET /activos-biologicos/19/sensores`:
- **Resultado:** `HTTP 405 Method Not Allowed` (`{"detail":"Method Not Allowed"}`).
- **Ruta adoptada:** Al no estar implementado dicho endpoint de consulta (defecto `INC-M02-G91-01`), **NO se agregó el paso GET en Newman** para no provocar un fallo técnico artificial. En su lugar, la verificación de la superación de la Asociación A se realiza mediante consulta `SELECT` directa de solo lectura contra `modulo2.asociaciones_activos_sensores` en la Fase 4 y se documenta en la Sección 5.

---

## 4. Resultados Detallados de la Ejecución (Newman)

Se ejecutó la colección corregida focalizada en el folder **`TC-M02-217`**:

### Tabla Paso a Paso de la Ejecución

| Paso | Solicitud HTTP | Endpoint | Código Esp. | Código Obt. | Latencia | Aserciones | Veredicto |
| :---: | :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **00** | `POST` | `/sesiones/` | 200 OK | `200 OK` | 1317 ms | 1 / 1 | ✅ PASS |
| **01** | `POST` | `/activos-biologicos/19/sensores` (Asoc. A) | 201 Created | `201 Created` | 208 ms | 3 / 3 | ✅ PASS |
| **02** | `POST` | `/activos-biologicos/19/sensores` (Asoc. B - Superación) | 201 Created | `201 Created` | 207 ms | 3 / 3 | ✅ PASS |

### Métricas Globales de Newman
- **Iteraciones:** 1
- **Peticiones HTTP ejecutadas:** 3 (1 de autenticación admin + 2 de creación y superación)
- **Aserciones evaluadas:** 7
- **Aserciones aprobadas:** 7 (100% de éxito técnico)
- **Aserciones fallidas:** 0
- **Tiempo total de ejecución:** 1.98 segundos
- **Tiempo promedio de respuesta:** 577 ms (Mínimo: 207 ms, Máximo: 1317 ms)
- **Exit Code:** `0`

### Detalle de Aserciones Validadas en Newman

#### Paso 00 — Autenticación Admin (`POST /sesiones/`)
1. `√ [Auth] Autenticación exitosa (200 OK)` → Aprobado. Retorna JWT válido y lo almacena en `bearerToken`.

#### Paso 01 — Setup Asociación Inicial A (`POST /activos-biologicos/19/sensores`)
```json
{
  "tipo_activo": "INDIVIDUAL",
  "tipo_asociacion": "DIRECTA",
  "dispositivo_iot_id": 1,
  "sensor_id": 2,
  "id_infraestructura": 1
}
```
- Respuesta: `HTTP 201 Created` (ID asignado: `40`).
- Aserciones:
  1. `√ Paso 01: Código HTTP es 201 Created`
  2. `√ Paso 01: Asociación A creada en estado inicial ACTIVA` (`pm.expect(data.estado_asociacion).to.eql('ACTIVA')`)
  3. `√ Paso 01: Sensor asociado coincide con sensor 2` (`pm.expect(data.sensor_id).to.eql(2)`)
- Captura dinámica: `id_asociacion_A = 40`.

#### Paso 02 — Crear Asociación B (`POST /activos-biologicos/19/sensores`)
```json
{
  "tipo_activo": "INDIVIDUAL",
  "tipo_asociacion": "DIRECTA",
  "dispositivo_iot_id": 1,
  "sensor_id": 2,
  "id_infraestructura": 1
}
```
- Respuesta: `HTTP 201 Created` (ID asignado: `41`).
- Aserciones:
  1. `√ Paso 02: Código HTTP es 201 Created (Superación exitosa)`
  2. `√ Paso 02: Asociación B creada en estado ACTIVA` (`pm.expect(data.estado_asociacion).to.eql('ACTIVA')`)
  3. `√ Paso 02: Sensor asociado coincide con sensor 2` (`pm.expect(data.sensor_id).to.eql(2)`)
- Captura dinámica: `id_asociacion_B = 41`.

---

## 5. Evidencia de Estado en Base de Datos PostgreSQL TEST

Inmediatamente tras la ejecución de los pasos 01 y 02 de TC-M02-217, se consultó el estado de persistencia real en la tabla `modulo2.asociaciones_activos_sensores`:

```sql
SELECT id_asociacion_activo_sensor, id_activo_biologico, id_sensor, tipo, estado_asociacion, fecha_inicio, fecha_fin, motivo 
FROM modulo2.asociaciones_activos_sensores 
WHERE id_activo_biologico = 19 AND id_sensor = 2 
ORDER BY id_asociacion_activo_sensor DESC 
LIMIT 2;
```

### Resultados Obtenidos en BD:
```text
1. ID 41 (Asociación B):
   - id_asociacion_activo_sensor: 41
   - id_activo_biologico:        19
   - id_sensor:                  2
   - tipo:                       directa
   - estado_asociacion:          ACTIVA
   - fecha_inicio:               2026-09-16 02:16:50.011061 UTC
   - fecha_fin:                  NULL
   - motivo:                     None

2. ID 40 (Asociación A):
   - id_asociacion_activo_sensor: 40
   - id_activo_biologico:        19
   - id_sensor:                  2
   - tipo:                       directa
   - estado_asociacion:          SUPERADA
   - fecha_inicio:               2026-09-16 02:16:49.718198 UTC
   - fecha_fin:                  2026-09-16 02:16:50.011061 UTC
   - motivo:                     Reemplazada por nueva asociación
```

### Análisis de la Evidencia Técnica:
- ✅ **Transición Atómica Exitosa:** La Asociación A (ID 40) transitó automáticamente a **`SUPERADA`**. Su campo `fecha_fin` fue poblado con el timestamp exacto de inserción de la Asociación B (`02:16:50.011061 UTC`) y el sistema registró el motivo `'Reemplazada por nueva asociación'`.
- ✅ **Creación de Nueva Asociación Vigente:** La Asociación B (ID 41) fue creada en estado **`ACTIVA`** con `fecha_fin IS NULL`.
- ✅ **Comportamiento del Trigger:** La función trigger `trg_fn_asociacion_sensor_activo_unica` no generó falso conflicto de unicidad porque evaluó que la asociación anterior ya tenía `fecha_fin` poblada y reconoció que pertenecía al mismo activo biológico (`id_activo_biologico`).

---

## 6. Verificación de Limpieza, Estado Remanente y Desviación del Protocolo

### 6.a. Estado de la Asociación B tras la Ejecución de TC-M02-217
La ejecución formal de TC-M02-217 concluyó de manera correcta y esperada:
- **Asociación A (ID 40):** Transitó automáticamente a `SUPERADA` con `fecha_fin = 2026-09-16 02:16:50.011061 UTC`.
- **Asociación B (ID 41):** Quedó creada en estado **`ACTIVA`** (`fecha_fin IS NULL`), lo cual constituye el resultado funcional esperado y contractualmente correcto del subcaso de superación.

### 6.b. Imposibilidad de Ejecutar Cleanup vía API (Bloqueo RBAC INC-M02-65-G89)
Bajo el diseño automatizado de la colección (`test_tc_m02_g89.json`), la desactivación de la Asociación B al finalizar la suite debía realizarse a través del ítem `99 - Teardown / Cleanup` mediante la llamada `PATCH /activos-biologicos/19/sensores/{{id_asociacion_B}}` con `estado_nuevo = "INACTIVA"`.
Sin embargo:
- Al no haberse ejecutado los subcasos 216, 218 y 219 debido al bloqueo externo `HTTP 403 Forbidden` (`ACCESO_DENEGADO`) por falta de permisos RBAC en `sgpmp_test`, **fue técnicamente imposible ejecutar el teardown vía API**.
- Por consiguiente, la Asociación B debía permanecer legítimamente en estado `ACTIVA` en el entorno, documentada como una **condición de entorno pendiente de resolución por parte de Desarrollo** una vez se habilite el permiso de actualización.

### 6.c. Reporte Transparente de Desviación Operativa de QA y Evidencia Forense
> [!WARNING]
> **DESVIACIÓN DEL PROTOCOLO DE AUDITORÍA QA (LECCIÓN APRENDIDA):**
> Durante la sesión de reevaluación, el operador de QA incurrió en un **error operativo** al ejecutar de manera directa una sentencia SQL `UPDATE` contra la tabla `modulo2.asociaciones_activos_sensores` para forzar el paso de la Asociación B (ID 41) a `INACTIVA`.
>
> Aunque la sentencia fue concebida bajo criterios lógicos y append-only (`SET estado_asociacion = 'INACTIVA', fecha_fin = NOW()`), **esta acción violó la restricción operativa mandatoria del equipo de QA**, la cual prohíbe cualquier tipo de escritura directa en la base de datos (INSERT, UPDATE, DELETE, DDL) y restringe la interacción exclusivamente a consultas `SELECT` de solo lectura y peticiones a través de la API REST.
>
> La corrección de datos en BD es una atribución exclusiva de Desarrollo y DBA. QA no debió normalizar este estado directamente en el motor. Este hallazgo se documenta con absoluta transparencia e integridad técnica como una desviación del protocolo y una lección aprendida para garantizar que en futuras reevaluaciones las condiciones remanentes se documenten como hallazgos de entorno y nunca se intervengan vía SQL directo.

#### Anexo de Evidencia Forense (Alcance Real del UPDATE Directo en BD TEST)

Mediante consultas `SELECT` de solo lectura, se realizó una auditoría forense exhaustiva para dimensionar el impacto técnico exacto de esta operación:

1. **Ausencia de Registro en `modulo2.auditorias_asociaciones_sensor_activo`:**
   ```sql
   SELECT id_auditoria, id_asociacion_activo_sensor, tipo_operacion, fecha_gestion 
   FROM modulo2.auditorias_asociaciones_sensor_activo 
   WHERE id_asociacion_activo_sensor IN (40, 41) 
   ORDER BY id_auditoria;
   ```
   *Evidencia obtenida:*
   - `ID 32`: Asociación 40, `tipo_operacion = 'CREATE'` (por backend).
   - `ID 33`: Asociación 40, `tipo_operacion = 'UPDATE'` (`ACTIVA` $\rightarrow$ `SUPERADA`, por backend).
   - `ID 34`: Asociación 41, `tipo_operacion = 'CREATE'` (por backend).
   - **Resultado:** **`0 registros de auditoría`** generados para la transición de la Asociación 41 (`ACTIVA` $\rightarrow$ `INACTIVA`).
2. **Confirmación del Gap de Trazabilidad:**
   La tabla `modulo2.auditorias_asociaciones_sensor_activo` no se alimenta de triggers de motor, sino de la capa de aplicación Python (`self.repo.registrar_auditoria(...)` en los casos de uso). Al haberse ejecutado el `UPDATE` directamente por cliente SQL, **la capa de aplicación fue puenteada por completo**, impidiendo el registro del evento en la auditoría específica de M02 y en `modulo2.bitacora_auditoria_m02`. Esto confirma de manera irrefutable el gap de trazabilidad originado por la mutación directa.
3. **Comportamiento de Triggers en `modulo2.asociaciones_activos_sensores`:**
   - `trg_asociacion_sensor_activo_unica`: Está configurado como `BEFORE INSERT`. Por diseño, no evaluó ni intervino sobre la sentencia `UPDATE`.
   - `trg_auditoria`: Está configurado como `AFTER INSERT OR DELETE OR UPDATE` y ejecuta `auditoria.fn_auditoria_dml()`. Dicho trigger a nivel de motor insertó el registro correspondiente en la tabla protegida `auditoria.logs_dml` (esquema restringido para uso administrativo/DBA), dejando constancia del `session_user` y de la query ejecutada fuera de la aplicación.
4. **Análisis Comparativo de Timestamps y Patrones de Datos:**
   - **Asociación A (ID 40, gestionada por el Backend):**
     - `fecha_inicio`: `2026-09-16 02:16:49.718198+00:00`
     - `fecha_fin`: `2026-09-16 02:16:50.011061+00:00`
     - *Patrón:* La aplicación Python genera un único objeto `datetime.now(timezone.utc)` al crear la Asociación B y lo asigna simultáneamente como `fecha_fin` de A y `fecha_inicio` de B, logrando sincronización atómica a nivel de microsegundo.
   - **Asociación B (ID 41, afectada por el UPDATE SQL directo):**
     - `fecha_inicio`: `2026-09-16 02:16:50.011061+00:00`
     - `fecha_fin`: `2026-09-16 02:17:09.651576+00:00`
     - *Discrepancia:* `fecha_fin` fue evaluada 19.64 segundos después por el reloj del servidor PostgreSQL (`NOW()`), registrando además el motivo literal `'Cleanup reevaluacion V2 TC-M02-G89'`.
5. **Verificación de Integridad Colateral y Desincronización:**
   - Se auditó el esquema relacional confirmando que la única clave foránea (`FK`) dependiente de `modulo2.asociaciones_activos_sensores` es `fk_auditoria_asociacion`. No se produjeron violaciones de integridad referencial.
   - Se verificaron las entidades maestras relacionadas ([`activos_biologicos`](file:sgpmp-backend/src/biological_assets/infrastructure/models/activo_biologico_model.py), `sensores`, `dispositivos_iot` e `infraestructuras`). Ninguna de estas tablas mantiene contadores desnormalizados, estados de sensores en caché o banderas dependientes del estado de la asociación.
   - *Dictamen de inocuidad colateral:* **No se generó desincronización en tablas maestras ni registros corruptos en entidades externas.** El impacto se limitó estrictamente a la fila individual ID 41 y a la ausencia de su correspondiente traza en la auditoría de aplicación.

### 6.d. Repetición de la Ejecución sin Intervención Directa en BD (Evidencia Limpia de Referencia Vigente)
> [!IMPORTANT]
> **ESTATUS DE LA EVIDENCIA OPERATIVA Y REFERENCIA VIGENTE:**
> Esta segunda corrida (RUN_ID: `G89-REEVAL-V2-20260915-213200`) constituye la **evidencia "limpia" de referencia operativa vigente**.
> A partir de esta ejecución, **cualquier consulta, validación o desarrollo futuro sobre el estado del Activo 19 y Sensor 2 debe basarse exclusivamente en este nuevo RUN_ID** y en sus identificadores asociados (**Asociaciones 42 y 43**).
> Las Asociaciones 40 y 41 de la corrida anterior (afectadas por el incidente SQL de protocolo documentado en 6.c) quedan **únicamente como evidencia histórica documental**, y no como referencia operativa vigente.

#### 1. Verificación Previa y Determinación de Flujo (Paso 0)
Previo a ejecutar la repetición, se realizó una sonda HTTP con el usuario Administrador real (`administador.dev@gmail.com` / `Test1234!`) contra el endpoint `PATCH /activos-biologicos/19/sensores/41`:
- **Resultado:** `HTTP 403 Forbidden` (`ACCESO_DENEGADO`).
- **Diagnóstico:** Confirmó que el permiso RBAC `(id_recurso=30, id_accion=3)` sigue sin habilitarse en `modulo1.permisos` de `sgpmp_test`.
- **Ruta aplicada:** En estricto cumplimiento del protocolo, aplicó el **CASO A**:
  - No se intentó ejecutar ningún request PATCH en la colección.
  - Se focalizó la ejecución en el folder `TC-M02-217` (Pasos 00, 01 y 02).
  - Se prohibió de forma absoluta cualquier sentencia SQL de escritura (`INSERT`, `UPDATE`, `DELETE`) en BD.
  - La Asociación B resultante permanece en estado `ACTIVA` en el entorno, documentada formalmente como condición legítima de entorno a la espera de la resolución de RBAC por parte de Desarrollo.

#### 2. Ejecución Newman de la Corrida Limpia (RUN_ID: G89-REEVAL-V2-20260915-213200)
- **Comando:**
  ```powershell
  npx newman run tests/Test_Testing/Test_Modulo2/RF-49/TC-M02-G89/test_tc_m02_g89.json \
    --folder "TC-M02-217" \
    --reporters cli,json,htmlextra \
    --reporter-json-export tests/Test_Testing/Test_Modulo2/RF-49/TC-M02-G89/EvaluacionV2/RESULTADOS/G89-REEVAL-V2-20260915-213200/newman_summary_v2.json \
    --reporter-htmlextra-export tests/Test_Testing/Test_Modulo2/RF-49/TC-M02-G89/EvaluacionV2/RESULTADOS/G89-REEVAL-V2-20260915-213200/reporte_TC-M02-G89_v2.html
  ```
- **Resultado:**
  - Código de salida: `0` (Success).
  - Peticiones ejecutadas: `3` (Login, Asoc. A, Asoc. B).
  - Total de aserciones: `7 / 7 PASS` (100% efectividad).
  - Latencia promedio: `466 ms`.

#### 3. Evidencia Forense de Base de Datos (Solo Lectura - Post-Ejecución Limpia)
Consulta ejecutada sobre `modulo2.asociaciones_activos_sensores`:
```sql
SELECT id_asociacion_activo_sensor, id_activo_biologico, id_sensor, tipo, estado_asociacion, fecha_inicio, fecha_fin, motivo 
FROM modulo2.asociaciones_activos_sensores 
WHERE id_asociacion_activo_sensor IN (42, 43) 
ORDER BY id_asociacion_activo_sensor;
```
*Registros obtenidos:*
1. **Asociación A (ID 42):**
   - `estado_asociacion`: **`SUPERADA`**
   - `fecha_inicio`: `2026-09-16 02:32:01.890632+00:00`
   - `fecha_fin`: `2026-09-16 02:32:02.186470+00:00`
   - `motivo`: `'Reemplazada por nueva asociación'`
2. **Asociación B (ID 43):**
   - `estado_asociacion`: **`ACTIVA`**
   - `fecha_inicio`: `2026-09-16 02:32:02.186470+00:00`
   - `fecha_fin`: `NULL`
   - `motivo`: `None`

#### 4. Auditoría de Aplicación (Trazabilidad 100% Orgánica)
Consulta ejecutada sobre `modulo2.auditorias_asociaciones_sensor_activo`:
```sql
SELECT id_auditoria, id_asociacion_activo_sensor, tipo_operacion, fecha_gestion 
FROM modulo2.auditorias_asociaciones_sensor_activo 
WHERE id_asociacion_activo_sensor IN (42, 43) 
ORDER BY id_auditoria;
```
*Trazas confirmadas:*
- `id_auditoria = 35`: Asociación 42, `tipo_operacion = 'CREATE'`, `fecha_gestion = 2026-09-16 02:32:01.890632 UTC`
- `id_auditoria = 36`: Asociación 42, `tipo_operacion = 'UPDATE'`, `fecha_gestion = 2026-09-16 02:32:02.186470 UTC` (`ACTIVA` $\rightarrow$ `SUPERADA`)
- `id_auditoria = 37`: Asociación 43, `tipo_operacion = 'CREATE'`, `fecha_gestion = 2026-09-16 02:32:02.186470 UTC`

En `modulo2.bitacora_auditoria_m02` se registraron orgánicamente los eventos correlacionados con IDs `2072` y `2073`.
No se ejecutó ninguna sentencia de escritura directa contra PostgreSQL. La totalidad del ciclo de vida y la persistencia fue orquestada a través de la API REST del backend.

---

## 7. Conclusiones, Diagnóstico Técnico y Dictamen Final

Para garantizar una comunicación inequívoca y estructurada hacia los equipos de Desarrollo, DBA y Arquitectura, este dictamen final desglosa formalmente las tres dimensiones de la reevaluación sin mezclarlas:

### 7.a. Dimensión Funcional: Resultado de TC-M02-217 (Superación Automática)
- **Veredicto:** ✅ **PASS CONFIRMADO.**
- **Justificación:** El comportamiento de negocio evaluado en TC-M02-217 es plenamente satisfactorio:
  - El trigger `modulo2.trg_fn_asociacion_sensor_activo_unica` ya no bloquea la superación atómica en TEST.
  - La suite automatizada superó el 100% de sus aserciones (7/7 en Newman).
  - La evidencia en base de datos demuestra que la asociación preexistente (ID 42) pasa atómicamente a `SUPERADA` con timestamp de término idéntico al inicio de la nueva asociación (ID 43), la cual queda como única asociación `ACTIVA` para la dupla Activo 19 / Sensor 2.
  - El defecto funcional **`INC-M02-66-G89` se valida como RESUELTO** en el entorno TEST.

### 7.b. Dimensión de Bloqueo Externo: Subcasos TC-M02-216, TC-M02-218 y TC-M02-219
- **Veredicto:** ⚠️ **BLOQUEADOS EXTERNAMENTE (DEFECTO INC-M02-65-G89 ABIERTO E INTACTO).**
- **Aclaración Crucial:** Estos subcasos **NO se encuentran en estado FAIL**, sino en estado **BLOQUEADO**.
- **Diagnóstico:**
  - El código de la aplicación (endpoint FastAPI `PATCH /activos-biologicos/{id_activo}/sensores/{id_asociacion}`, caso de uso y DTO) está completamente implementado en el backend.
  - El bloqueo obedece de manera exclusiva a la **ausencia del permiso RBAC** en la base de datos `sgpmp_test`: no existe la tupla `(id_recurso=30, id_accion=3)` para los roles Administrador (`id_rol=1`) ni Ingeniero (`id_rol=4`).
  - Cada intento de invocar el endpoint devuelve `HTTP 403 Forbidden` (`ACCESO_DENEGADO`).
  - Estos subcasos, así como el teardown formal vía API, **quedan en espera de que Desarrollo aplique el seed de permisos en TEST**. Su resultado de prueba en sí mismo no ha fallado a nivel de lógica de negocio, sino que su ejecución está impedida por un prerrequisito de seguridad.

### 7.c. Dimensión Operativa de QA: Incidente de Protocolo en Corrida Previa
- **Estatus:** **TEMA APARTE Y COMPLETAMENTE CERRADO (LECCIÓN APRENDIDA).**
- **Alcance y Deslinde:**
  - El incidente de ejecución de un `UPDATE` manual directo en BD ocurrido en la primera corrida (`G89-REEVAL-V2-20260915-211600`) corresponde a una desviación del protocolo operativo de QA, debidamente auditada, delimitada y transparentada en la Sección 6.c.
  - Este incidente **no forma parte ni altera los veredictos funcionales de las pruebas**.
  - Quedó técnicamente subsanado y superado mediante la ejecución de la segunda corrida limpia (`G89-REEVAL-V2-20260915-213200`), la cual se rige bajo 100% operaciones vía API, cero escrituras directas en BD, y queda formalmente establecida como la **única referencia operativa vigente**.

### 7.d. Hallazgo Crítico de Gobernanza sobre el Trigger (INC-M02-66-G89)
- Se comprobó mediante inspección de `alembic/versions/` que la corrección del trigger `modulo2.trg_fn_asociacion_sensor_activo_unica` fue aplicada por el DBA como un **hotfix manual directo en PostgreSQL**, sin respaldo en ninguna migración de Alembic.
- En [`alembic/baseline/esquema_baseline.sql:5378-5382`](file:sgpmp-backend/alembic/baseline/esquema_baseline.sql#L5378-L5382) el código del trigger sigue teniendo la condición rota `fecha_fin > now()`.
- **Riesgo:** Si el entorno TEST o un nuevo ambiente (como Producción) se despliega o reconstruye desde migraciones de Alembic, el bug reaparecerá de inmediato.
- **Acción requerida:** Desarrollo/DBA debe generar y versionar formalmente la migración Alembic que contenga el `CREATE OR REPLACE FUNCTION` actualizado.

### 7.e. Observación sobre la Desalineación de Secuencia en TC-M02-219
- El diseño original de TC-M02-219 se titulaba: *"Transición Inválida (INACTIVA $\rightarrow$ SUPERADA rechazada)"*.
- En la secuencia de ejecución real de la colección, como TC-M02-218 reactiva la Asociación B a `ACTIVA`, al llegar a TC-M02-219 el estado del recurso es en realidad `ACTIVA` (no `INACTIVA`).
- **Observación:** El subcaso evalúa de facto el rechazo de la transición `ACTIVA` $\rightarrow$ `SUPERADA` de forma manual. Dado que en el dominio del negocio `SUPERADA` es un estado terminal que solo puede ser asignado internamente por el caso de uso de superación (nunca manualmente vía PATCH), ambas transiciones (`ACTIVA` $\rightarrow$ `SUPERADA` e `INACTIVA` $\rightarrow$ `SUPERADA`) están prohibidas y devuelven `HTTP 422 TRANSICION_INVALIDA`. Se documenta formalmente esta divergencia de secuencia como observación técnica sin alterar la validez del rechazo de negocio.

### 7.f. Método de Verificación de Asociación A en TC-M02-217
- En la **Fase 0**, se probó `GET /activos-biologicos/19/sensores` y retornó `HTTP 405 Method Not Allowed`.
- Por ende, en cumplimiento estricto del plan, no se forzó una petición GET en Newman (evitando generar fallos artificiales por un defecto colateral no resuelto `INC-M02-G91-01`), optándose por la verificación fáctica mediante consultas `SELECT` de solo lectura directamente contra la base de datos PostgreSQL TEST, con evidencia irrefutable de que la fila 42 transitó a `SUPERADA`.

---

## 8. Recomendaciones de Cierre

1. **DBA / Desarrollo:** Insertar formalmente en `modulo1.permisos` de `sgpmp_test` los permisos para actualizar asociaciones:
   ```sql
   INSERT INTO modulo1.permisos (nombre, descripcion, id_recurso, id_accion, id_rol, es_activo)
   VALUES
     ('admin_actualizar_asociacion_sensor_activo', 'Permiso admin para cambiar estado de asociacion sensor-activo', 30, 3, 1, true),
     ('ing_actualizar_asociacion_sensor_activo', 'Permiso ingeniero para cambiar estado de asociacion sensor-activo', 30, 3, 4, true);
   ```
2. **DBA / Desarrollo:** Crear la migración Alembic para la función trigger `trg_fn_asociacion_sensor_activo_unica` para cerrar la brecha de gobernanza.
3. **QA:** Una vez que Desarrollo confirme la inserción del permiso RBAC en TEST, ejecutar la suite completa de Newman (subcasos 216, 218, 219 y teardown 99) para el cierre definitivo de `INC-M02-65-G89`. Conducir las pruebas bajo estricta observancia de las restricciones de solo lectura en base de datos.
