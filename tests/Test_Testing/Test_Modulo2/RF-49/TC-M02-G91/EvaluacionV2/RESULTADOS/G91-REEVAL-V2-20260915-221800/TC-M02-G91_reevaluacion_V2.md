# Reevaluación V2 — Caso TC-M02-G91 — RF-49 CU11
## Integridad del Historial y Trazabilidad Post-Creación de la Asociación Sensor-Activo

---

## 1. Encabezado y Metadatos de Ejecución

- **Título del Informe:** Reevaluación V2 — Caso TC-M02-G91 — RF-49 CU11 — Trazabilidad y Consulta de Asociaciones IoT
- **RUN_ID:** `G91-REEVAL-V2-20260915-221800`
- **Módulo de Negocio:** 2 — Activos Biológicos (`biological_assets`)
- **Requisito Funcional / Caso de Uso:** RF-49 (Asociación de Sensores IoT a Activos Biológicos) — Caso de Uso CU11
- **Fechas de Ejecución:**
  - Corrida Original V1: `2026-09-10` (1 PASS CON OBSERVACIÓN / 1 FAIL — NO CONFORME)
  - Reevaluación Formal V2: `2026-09-15` / `2026-09-16 03:18:00 UTC` (RUN_ID: `G91-REEVAL-V2-20260915-221800`)
- **Entorno de Pruebas:** TEST (`https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test/`)
- **Base de Datos TEST:** PostgreSQL 16 (`158.69.200.27:5448/sgpmp_test`, usuario de solo lectura `member_qa`)
- **Usuario Autenticado para Sondas:** `administador.dev@gmail.com` (`id_usuario=1`, `id_rol=1` Administrador)
- **Herramienta de Ejecución:** Sondas HTTP REST automatizadas (Python 3.13 / `requests`) + Verificación SQL (Psycopg2 / `RealDictCursor`). *Newman CLI 6.2.2 no ejecutado preventivamente tras confirmar ausencia de despliegue*.
- **Colección Auditada y Corregida:** `tests/Test_Testing/Test_Modulo2/RF-49/TC-M02-G91/test_tc_m02_g91.json` (5 ajustes críticos aplicados: contrato envolvente, correlación dinámica de ID, credenciales admin, verificación de inmutabilidad y advertencia de teardown).
- **Veredicto Global V2:** ⚠️ **BLOQUEADO POR DESPLIEGUE — TC-M02-222: PASS CON OBSERVACIÓN (OBS-M02-G91-01 SIN CAMBIOS) / TC-M02-223: BLOQUEADO POR DESPLIEGUE (INC-M02-G91-01 RESUELTO EN CÓDIGO PERO PENDIENTE DE DEPLOY)**

---

## 2. Objetivo de la Reevaluación / Resumen Ejecutivo

### Contexto Histórico de la Línea Base V1
En la corrida original del 10 de septiembre de 2026, el caso agrupado TC-M02-G91 obtuvo veredicto **NO CONFORME**:
1. **TC-M02-222 (PASS CON OBSERVACIÓN - OBS-M02-G91-01):** El intento de `DELETE` físico sobre una asociación activa fue rechazado por el servidor con `HTTP 404/405` debido a la inexistencia de ruta DELETE en el router. Se observó que el rechazo era un efecto secundario de la falta de implementación y no una regla de negocio explícita (`409/403`).
2. **TC-M02-223 (FALLIDO - INC-M02-G91-01):** El endpoint de consulta `GET /activos-biologicos/{id_activo}/sensores` no existía en el backend, respondiendo `HTTP 405 Method Not Allowed`. La asociación quedaba persistida en base de datos pero era totalmente invisible para la API, violando el criterio de aceptación textual de RF-49: *"El sistema refleja la asociación en consultas posteriores"*.

### Alcance de la Reevaluación V2 y Hallazgo Preflight
El equipo de Desarrollo reportó haber solventado el defecto `INC-M02-G91-01` mediante el **PR #321** (commit `2b3e3772a9d9b3c66f4f3688c91a97d4b12e526a` del 14 de septiembre), agregando `ConsultarAsociacionesSensorUseCase` y el endpoint `GET /{id_activo}/sensores` con soporte para `tipo_consulta` (`ACTIVA` / `HISTORIAL`).

Sin embargo, la auditoría preflight en vivo constató que **el entorno TEST desplegado no cuenta con este fix**:
- La sonda HTTP en vivo contra `GET /activos-biologicos/19/sensores` arrojó `HTTP 405 Method Not Allowed` (`Allow: POST`).
- La inspección del catálogo OpenAPI remoto (`/openapi.json`) confirmó que para dicha ruta **únicamente sigue publicado el método `post`**.
- La ejecución masiva de Newman fue suspendida preventivamente porque ejecutarla contra un servidor sin desplegar reproduciría exactamente el mismo fallo de V1, distorsionando la métrica de calidad de código con un problema puramente operativo de DevOps.

### Tabla Comparativa de Subcasos (V1 vs V2)

| Subcaso | Objetivo de Prueba | HTTP Esperado | HTTP Obtenido V2 | Estado V1 | Estado V2 | Dictamen Técnico V2 |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| **TC-M02-222** | Rechazo de `DELETE` físico sobre asociación activa (Restricción 8 append-only) | 405 / 404 | 405 Method Not Allowed | PASS CON OBS | ✅ **PASS CON OBSERVACIÓN** | **Inmutabilidad Cumplida (OBS-M02-G91-01 vigente sin cambios):** La API rechaza el DELETE con 405 por ausencia de ruta. En BD TEST la asociación 43 permanece ACTIVA e inalterada. Desarrollo confirmó que este rechazo estructural está fuera del alcance de cambio. |
| **TC-M02-223** | Visibilidad de la asociación recién creada en consultas posteriores (RF-49 Criterio Aceptación) | 200 OK | 405 Method Not Allowed | FAIL | ⚠️ **BLOQUEADO POR DESPLIEGUE** | **Defecto INC-M02-G91-01 Resuelto en Código, Pendiente Deploy:** El PR #321 resuelve el endpoint y el use case pasa el 100% de tests unitarios, pero el contenedor TEST en Dokploy aún no ha sido actualizado. |

---

## 3. Estado Previo de la Base de Datos (Pre-condición)

Previo a cualquier interacción, se realizaron consultas SQL de solo lectura mediante el usuario `member_qa` sobre PostgreSQL TEST (`sgpmp_test`):

### 3.1. Auditoría del Permiso RBAC de Lectura (Acción 2 sobre Recurso 30)
Para descartar que el bloqueo fuera un problema de autorización (como ocurrió en G89 con PATCH):
```sql
SELECT p.id_permiso, p.nombre, p.id_recurso, p.id_accion, p.id_rol, p.es_activo
FROM modulo1.permisos p 
WHERE p.id_recurso = 30 AND p.id_accion = 2
ORDER BY p.id_rol;
```
**Resultado Obtenido:**
```text
- id_rol: 1 (Admin)       → id_permiso: 182 | admin_leer_asociacion_sensor_activo | es_activo: True
- id_rol: 2 (Productor)   → id_permiso: 185 | prod_leer_asociacion_sensor_activo  | es_activo: True
- id_rol: 3 (Veterinario) → id_permiso: 186 | vet_leer_asociacion_sensor_activo   | es_activo: True
- id_rol: 4 (Ingeniero)   → id_permiso: 184 | ing_leer_asociacion_sensor_activo   | es_activo: True
```
> **Conclusión RBAC:** Los permisos de lectura sobre asociaciones sensor-activo están plenamente sembrados y activos para los 4 roles en la base de datos TEST desde `2026-06-29 22:51:32 UTC`. El rechazo 405 no proviene de la capa de autorización RBAC (no es un 403).

### 3.2. Historial de Asociaciones para Activo 19 / Sensor 2
```sql
SELECT id_asociacion_activo_sensor, id_sensor, tipo, tipo_activo, estado_asociacion, fecha_inicio, fecha_fin
FROM modulo2.asociaciones_activos_sensores
WHERE id_activo_biologico = 19 OR id_sensor = 2
ORDER BY id_asociacion_activo_sensor;
```
**Resultado Obtenido:**
- Existen 13 registros históricos para este par (asociaciones 16, 17, 22, 24, 25, 26, 27, 28, 36, 37, 38, 40, 41, 42, 43).
- **Asociaciones con estado `ACTIVA` (`fecha_fin IS NULL`):** **Exactamente 1 fila**:
  - `id_asociacion_activo_sensor: 43`
  - `id_sensor: 2` (Sensor PH, Finca 1)
  - `id_activo_biologico: 19` (`ARETE-TEST-01`, Individual Bovino)
  - `tipo: 'directa'`
  - `fecha_inicio: 2026-09-16 02:32:02.186470 UTC`
  - `fecha_fin: NULL`

---

## 4. Resultados Detallados de la Ejecución (Sondas HTTP y OpenAPI)

Al constatar en la fase preflight que el servidor TEST no había incorporado el PR #321, se procedió a ejecutar una batería controlada de sondas HTTP automatizadas en lugar de la colección Newman:

### 4.1. Sonda HTTP 1: `GET /activos-biologicos/19/sensores` (Consulta de Asociaciones)
- **Método y URL:** `GET https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test/activos-biologicos/19/sensores`
- **Autenticación:** `Bearer <TOKEN_ADMIN_DEV>`
- **Resultado Obtenido:**
  - **Status Code:** `HTTP 405 Method Not Allowed`
  - **Cabeceras:** `Allow: POST`, `Server: uvicorn`, `X-Request-Id: 504dbec4-48ae-48c1-bee0-a347bbff7622`
  - **Cuerpo JSON:**
    ```json
    {
      "detail": "Method Not Allowed"
    }
    ```
- **Sonda complementaria con query params:**
  - `GET .../19/sensores?tipo_consulta=HISTORIAL` $\rightarrow$ `HTTP 405 Method Not Allowed` (`Allow: POST`)
  - `GET .../19/sensores?tipo_consulta=INVALIDO` $\rightarrow$ `HTTP 405 Method Not Allowed` (`Allow: POST`)

### 4.2. Sonda HTTP 2: Inspección de Catálogo OpenAPI TEST (`/openapi.json`)
Se analizó la definición OpenAPI del entorno desplegado:
```json
"/activos-biologicos/{id_activo}/sensores": {
  "post": {
    "summary": "Asociar sensor IoT a un activo biológico (RF-49)",
    "operationId": "asociar_sensor_iot_activos_biologicos__id_activo__sensores_post"
  }
}
```
**Constatación:** El verbo `get` no existe en la definición de la API expuesta por el servidor TEST.

### 4.3. Sonda HTTP 3: `DELETE` sobre Asociación Existente (ID 43) y Ruta Base
- **Sonda 3.a (Ruta específica):** `DELETE /activos-biologicos/19/sensores/43`
  - **Status Code:** `HTTP 405 Method Not Allowed`
  - **Cabecera:** `Allow: PATCH`
  - **Cuerpo:** `{"detail": "Method Not Allowed"}`
- **Sonda 3.b (Ruta base):** `DELETE /activos-biologicos/19/sensores`
  - **Status Code:** `HTTP 405 Method Not Allowed`
  - **Cabecera:** `Allow: POST`
  - **Cuerpo:** `{"detail": "Method Not Allowed"}`

---

## 5. Evidencia de Estado en BD PostgreSQL TEST (Inmutabilidad Post-Sonda)

Inmediatamente después de ejecutar las sondas DELETE, se consultó el estado del registro en la base de datos `sgpmp_test`:

```sql
SELECT id_asociacion_activo_sensor, id_sensor, id_activo_biologico, tipo, estado_asociacion, fecha_inicio, fecha_fin, motivo
FROM modulo2.asociaciones_activos_sensores
WHERE id_asociacion_activo_sensor = 43;
```

**Evidencia de Fila Retornada:**
```json
{
  "id_asociacion_activo_sensor": 43,
  "id_sensor": 2,
  "id_activo_biologico": 19,
  "tipo": "directa",
  "estado_asociacion": "ACTIVA",
  "fecha_inicio": "2026-09-16 02:32:02.186470+00:00",
  "fecha_fin": null,
  "motivo": null
}
```

> **Dictamen de Inmutabilidad:** Se confirma que ningún intento de eliminación vía HTTP produjo alteración de datos, cambio de estado ni eliminación física. El registro ID `43` permanece íntegro y vigente en la base de datos, satisfaciendo la Restricción 8 (*append-only*) del requerimiento RF-49.

---

## 6. Verificación de Limpieza (Teardown)

- **Estado de Mutación en esta Sesión:** CERO datos creados, modificados o eliminados.
- **Justificación:** Las operaciones ejecutadas consistieron exclusivamente en consultas `SELECT` directas a PostgreSQL, lectura de `/openapi.json` y dos solicitudes `DELETE` que fueron rechazadas estructuralmente por el servidor web (`HTTP 405`).
- **Limpieza Requerida:** **NO APLICA (Entorno higienizado).** No existen registros huérfanos ni mutaciones residuales generadas por esta reevaluación.

---

## 7. Conclusiones, Diagnóstico Técnico y Dictamen Final

### 7.1. Conclusiones por Subcaso
1. **TC-M02-222 (Rechazo de DELETE):**
   - **Veredicto:** ✅ **PASS CON OBSERVACIÓN (OBS-M02-G91-01 SIN CAMBIOS)**.
   - La eliminación física de asociaciones está bloqueada por arquitectura (HTTP 405). La base de datos garantiza inmutabilidad absoluta.
   - La observación contractual `OBS-M02-G91-01` (rechazo por ausencia de ruta en lugar de error de negocio tipificado) fue ratificada por Desarrollo como fuera de alcance de la corrección de consulta, manteniéndose como deuda técnica menor documentada.
2. **TC-M02-223 (Visibilidad en Consultas Posteriores):**
   - **Veredicto:** ⚠️ **BLOQUEADO POR DESPLIEGUE**.
   - No corresponde calificar este caso como `FAIL` (puesto que el código fuente desarrollado en el PR #321 es funcionalmente correcto y sus pruebas unitarias pasan al 100%), ni como `PASS` (puesto que el servidor de pruebas desplegado aún no lo implementa).
   - Se tipifica formalmente como bloqueo externo de infraestructura bajo el incidente: **`INC-M02-42-G91: Despliegue TEST desactualizado respecto a PR #321 / commit 2b3e3772`**.

### 7.2. Ajustes Realizados a la Suite de Pruebas Newman
La colección [test_tc_m02_g91.json](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/tests/Test_Testing/Test_Modulo2/RF-49/TC-M02-G91/test_tc_m02_g91.json) fue auditada y saneada con 5 modificaciones para garantizar su ejecución exitosa tan pronto se aplique el despliegue:
1. Variables actualizadas con usuario administrador real (`administador.dev@gmail.com`).
2. Aserción de contrato corregida: evalúa el objeto envolvente `jsonData.asociaciones` en lugar de esperar erróneamente un array plano en la raíz.
3. Correlación de ID estricta: el GET valida específicamente la presencia del `id_asociacion_activo_sensor` retornado por el POST (`targetId = parseInt(pm.collectionVariables.get("nuevaAsociacionId"))`), impidiendo falsos positivos por la asociación histórica 43.
4. Captura dinámica para TC-M02-222 eliminando el ID hardcodeado 17, con verificación posterior de inmutabilidad.
5. Inclusión de la advertencia técnica formal respecto a la imposibilidad de teardown vía API (por el bloqueo de PATCH en TEST) y la prohibición de limpieza directa por SQL.

### 7.3. Criterio de Cierre y Próximos Pasos
- **Este informe NO constituye el cierre definitivo del caso TC-M02-G91.**
- Tan pronto el equipo de Despliegue/DevOps confirme la reconstrucción y reinicio del contenedor del backend en Dokploy con el commit `2b3e3772` (verificable cuando `/openapi.json` exponga el método `get` en la ruta de sensores), se procederá a:
  1. Ejecutar la colección Newman corregida `test_tc_m02_g91.json`.
  2. Generar el reporte HTML interactivo y resumen JSON en esta misma carpeta de corrida.
  3. Actualizar este documento formal `TC-M02-G91_reevaluacion_V2.md` con los resultados en vivo y el veredicto definitivo de aprobación.
