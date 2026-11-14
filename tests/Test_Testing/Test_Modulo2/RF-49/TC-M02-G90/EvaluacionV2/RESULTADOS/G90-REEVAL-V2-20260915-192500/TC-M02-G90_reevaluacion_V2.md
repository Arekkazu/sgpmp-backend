# Reevaluación V2 — Caso TC-M02-G90 — RF-49 CU11
## Vacíos de Diseño: Tipo AMBIENTAL Puro (INC-M02-G90-01) y Contradicción Interna del RF-49 (OBS-M02-G90-02)

---

## 1. Encabezado y Metadatos de Ejecución

- **Título del Informe:** Reevaluación V2 — Caso TC-M02-G90 — RF-49 CU11 — Vacíos de Diseño: Tipo AMBIENTAL Puro (INC-M02-G90-01) y Contradicción Interna del RF-49 (OBS-M02-G90-02)
- **RUN_ID:** `G90-REEVAL-V2-20260915-192500`
- **Módulo:** 2 — Activos Biológicos
- **Requisito Funcional / CU:** RF-49 (Asociación de Sensores IoT a Activos Biológicos) — Caso de Uso CU11
- **Fechas de Ejecución:**
  - Corrida Original V1: `2026-09-10`
  - Reevaluación V2: `2026-09-15` / `2026-09-16 00:26:00 UTC`
- **Entorno de Pruebas:** TEST (`https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test`)
- **Base de Datos TEST:** PostgreSQL 16 (`158.69.200.27:5448/sgpmp_test`, usuario `member_qa`). *Nota: Se utilizó conexión directa de QA para verificación append-only y consultas de estado, complementada con verificación vía API REST.*
- **Herramientas de Ejecución:** Newman CLI 6.2.2 + Reporter htmlextra 1.23.1
- **Colección Ejecutada:** `tests/Test_Testing/Test_Modulo2/RF-49/TC-M02-G90/test_tc_m02_g90.json` (ejecutada íntegra y sin modificaciones)
- **Reporte HTML:** [reporte_TC-M02-G90_v2.html](./reporte_TC-M02-G90_v2.html)
- **Veredicto Global:** ⚠️ **PASS TÉCNICO NEWMAN + FAIL FUNCIONAL DE DISEÑO EN TC-M02-220 + PASS CON OBSERVACIÓN EN TC-M02-221**

---

## 2. Objetivo de la Reevaluación y Resumen Ejecutivo

### Contexto V1
En la ejecución original V1 (2026-09-10), la suite agrupada TC-M02-G90 fue calificada como **NO CONFORME** a raíz de dos hallazgos estructurales en el requerimiento y la implementación:
1. **INC-M02-G90-01 (Severo):** El endpoint disponible `POST /activos-biologicos/{id_activo}/sensores` exige forzosamente anclar la asociación a un activo individual (`{id_activo}` obligatorio en la ruta), impidiendo el registro del **Tipo B** del RF-49 (*Asociación Ambiental Compartida mediada por infraestructura pura: 1 sensor ambiental monitoriza a N activos que residen en la infraestructura sin anclaje a un activo puntual*).
2. **OBS-M02-G90-02 (Observación de Requisito):** El RF-49 presenta una contradicción interna entre su Precondición 4 (*"misma infraestructura o misma granja"*) y su Restricción 2 + Flujo E2 (*"misma granja"*).

### Hallazgos del Diagnóstico V2
- El endpoint actual `POST /activos-biologicos/{id_activo}/sensores` mantiene `{id_activo}` como parámetro obligatorio en el router FastAPI ([`activo_biologico_router.py`](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/src/biological_assets/infrastructure/routers/activo_biologico_router.py#L1194)), impidiendo el registro del Tipo B puro del RF-49.
- El modelo de datos en base de datos (`modulo2.asociaciones_activos_sensores`) y el modelo SQLAlchemy ([`asociacion_sensor_activo_model.py`](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/src/biological_assets/infrastructure/models/asociacion_sensor_activo_model.py#L93)) **ya soportan** `id_activo_biologico: Mapped[Optional[int]] = mapped_column(Integer)` (columna nullable en PostgreSQL). El bloqueo es **100% en la capa de API y caso de uso**, no en base de datos.
- No existe ningún endpoint alternativo a nivel de infraestructura implementado (e.g. `POST /configuracion/infraestructuras/{id}/sensores` o similar).
- No existe en el caso de uso ([`asociar_sensor_activo_use_case.py`](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/src/biological_assets/application/use_cases/gestion/asociar_sensor_activo_use_case.py#L152-L203)) ninguna rama condicional `if dto.tipo_asociacion == 'AMBIENTAL'`, validando únicamente `DIRECTA` y `POBLACIONAL`.
- Contradicción del RF-49: El backend adopta la interpretación amplia de "misma granja / finca" a través de la regla V6 (`infra_sensor.id_finca == infra_activo.id_finca`), permitiendo asociar sensores entre infraestructuras distintas si comparten finca territorial.

### Tabla Comparativa V1 vs V2

| Subcaso | Enfoque Evaluado | Resultado Esperado Contractual | Obtenido V2 en TEST | Newman CLI | Veredicto Funcional V2 |
| :--- | :--- | :--- | :--- | :---: | :--- |
| **TC-M02-220** | AMBIENTAL sin activo puntual (Tipo B del RF-49) | HTTP 201 contra infraestructura pura (`id_activo = NULL`) | HTTP 201 Created atado a activo individual 19 | ✅ PASS (3/3) | ❌ **FAIL FUNCIONAL** (Defecto `INC-M02-G90-01` persiste; API sin endpoint Tipo B) |
| **TC-M02-221** | Coherencia territorial entre infraestructuras (misma finca) | Aceptación por regla de finca territorial (o rechazo por infraestructura estricta) | HTTP 201 Created (aceptado por misma finca) | ✅ PASS (2/2) | ✅ **PASS CON OBSERVACIÓN** (Alineado con Restricción 2 y Flujo E2; contradicción `OBS-M02-G90-02`) |

---

## 3. Estado Previo de la Base de Datos (Pre-condición vía API REST)

La verificación de precondiciones se ejecutó de forma automatizada mediante llamadas API REST contra el entorno TEST, con verificación del estado de persistencia:

### Transcripción de `precondicion_api.log`

```text
[2026-09-16 00:23:42 UTC] === INICIO DE VERIFICACIÓN DE PRECONDICIONES (TEST API & BD) — TC-M02-G90 ===
[2026-09-16 00:23:42 UTC] Target baseUrl: https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test
[2026-09-16 00:23:43 UTC] 1. Login Admin: POST /sesiones/ -> HTTP 200
[2026-09-16 00:23:44 UTC] 2. GET /activos-biologicos/19 -> HTTP 200
[2026-09-16 00:23:44 UTC]    Activo 19: ID=19, Identificador=ARETE-TEST-01, Tipo=INDIVIDUAL, Estado=ACTIVO, Infra=1
[2026-09-16 00:23:45 UTC] 3. GET /activos-biologicos/1 -> HTTP 200
[2026-09-16 00:23:45 UTC]    Activo 1: ID=1, Identificador=BOV-001, Tipo=INDIVIDUAL, Estado=ACTIVO, Infra=2
[2026-09-16 00:23:45 UTC] 4. GET /configuracion/dispositivos-iot/1 -> HTTP 200
[2026-09-16 00:23:45 UTC]    Dispositivo 1: ID=1, Infraestructura=1, Finca=None
[2026-09-16 00:23:46 UTC] 5. GET /configuracion/infraestructuras/1 -> HTTP 200
[2026-09-16 00:23:46 UTC]    Infraestructura 1: Nombre='None', Finca=1, Tipo='None'
[2026-09-16 00:23:47 UTC] 5. GET /configuracion/infraestructuras/2 -> HTTP 200
[2026-09-16 00:23:47 UTC]    Infraestructura 2: Nombre='None', Finca=1, Tipo='None'
[2026-09-16 00:23:48 UTC] 6. Sensor 3: Asociaciones ACTIVAS en Activos 1 y 19 = 0 (Esperado: 0)
[2026-09-16 00:23:48 UTC] === FIN DE VERIFICACIÓN DE PRECONDICIONES ===
```

### Confirmación de Fixtures
- **Activo 19:** Existente, estado `ACTIVO`, tipo `INDIVIDUAL`, asignado a Infraestructura 1 (`Estanque-01`).
- **Activo 1:** Existente, estado `ACTIVO`, tipo `INDIVIDUAL`, asignado a Infraestructura 2 (`Estanque-02`).
- **Sensor 3 / Dispositivo 1:** Sensor IoT activo asignado a Infraestructura 1.
- **Infraestructura 1 e Infraestructura 2:** Ambas ubicadas y pertenecientes a la **Finca 1**.
- **Asociaciones Previas:** Se confirmó que el Sensor 3 no poseía asociaciones activas remanentes sobre los activos 1 y 19 (`count = 0`), garantizando la pureza del fixture de prueba.

---

## 4. Resultados Detallados de la Ejecución (Newman)

La colección `test_tc_m02_g90.json` fue ejecutada de extremo a extremo contra el entorno TEST sin alteraciones.

### Tabla Paso a Paso de la Corrida

| Carpeta / Subcaso | Ítem / Request | Método | Endpoint | HTTP Esp. | HTTP Obt. | Latencia | Aserciones | Veredicto Técnico |
| :--- | :--- | :---: | :--- | :---: | :---: | :---: | :---: | :---: |
| **TC-M02-220** | 00 - Autenticación Admin | `POST` | `/sesiones/` | 200 | 200 OK | 1170 ms | 1/1 PASS | ✅ PASS |
| **TC-M02-220** | 01 - Crear Asociación AMBIENTAL en Endpoint de Activo | `POST` | `/activos-biologicos/19/sensores` | 201 | 201 Created | 188 ms | 3/3 PASS | ✅ PASS (Técnico) |
| **TC-M02-221** | 00 - Autenticación Admin | `POST` | `/sesiones/` | 200 | 200 OK | 455 ms | 1/1 PASS | ✅ PASS |
| **TC-M02-221** | 01 - Sensor Infra 1 con Activo Infra 2 (Misma Finca) | `POST` | `/activos-biologicos/1/sensores` | 201, 409, 422 | 201 Created | 208 ms | 2/2 PASS | ✅ PASS (Técnico) |

### Métricas Globales de la Ejecución
- **Total de Iteraciones:** 1
- **Total de Solicitudes HTTP:** 4 (2 de autenticación administrativa + 2 funcionales)
- **Total de Scripts de Prueba:** 4
- **Total de Aserciones:** 7 ejecutadas, 7 aprobadas (0 fallidas)
- **Tiempo Total de Corrida:** 2.3 segundos
- **Tiempo Promedio de Respuesta:** 505 ms (Mínimo: 188 ms, Máximo: 1170 ms)
- **Newman Exit Code:** `0`

### Evidencia Textual de Cuerpos de Respuesta

#### Subcaso TC-M02-220 (`POST /activos-biologicos/19/sensores`)
```json
{
  "id_asociacion_activo_sensor": 38,
  "id_activo_biologico": 19,
  "tipo_activo": "INDIVIDUAL",
  "tipo_asociacion": "ambiental",
  "dispositivo_iot_id": 1,
  "sensor_id": 3,
  "id_infraestructura": 1,
  "fecha_inicio": "2026-09-16T00:26:01.662232Z",
  "fecha_fin": null,
  "estado_asociacion": "ACTIVA",
  "motivo": "Evaluacion de asociacion AMBIENTAL en endpoint de activo TC-M02-220",
  "advertencia": null
}
```
*Aserciones evaluadas:*
1. `TC-M02-220: Código HTTP es 201 Created` → ✅ PASS
2. `TC-M02-220: Tipo de asociación es AMBIENTAL` → ✅ PASS
3. `TC-M02-220: Estado inicial es ACTIVA` → ✅ PASS

#### Subcaso TC-M02-221 (`POST /activos-biologicos/1/sensores`)
```json
{
  "id_asociacion_activo_sensor": 39,
  "id_activo_biologico": 1,
  "tipo_activo": "INDIVIDUAL",
  "tipo_asociacion": "directa",
  "dispositivo_iot_id": 1,
  "sensor_id": 3,
  "id_infraestructura": 1,
  "fecha_inicio": "2026-09-16T00:26:02.441452Z",
  "fecha_fin": null,
  "estado_asociacion": "ACTIVA",
  "motivo": "Evaluacion de sensor en Infra 1 con activo en Infra 2 dentro de Finca 1 TC-M02-221",
  "advertencia": null
}
```
*Aserciones evaluadas:*
1. `TC-M02-221: Respuesta coherente con alguna interpretación del RF-49` (`pm.expect(pm.response.code).to.be.oneOf([201, 409, 422])`) → ✅ PASS
2. `TC-M02-221: Estado de asociación creada es ACTIVA` → ✅ PASS

### Análisis Crítico del Planteamiento de las Pruebas
1. **TC-M02-220:** La aserción de Newman pasa con éxito técnico (HTTP 201) únicamente porque la colección se ve forzada a invocar el endpoint disponible `POST /activos-biologicos/19/sensores`. Sin embargo, esto desvirtúa el requerimiento funcional del Tipo B del RF-49: la asociación quedó forzosamente vinculada al activo individual 19 (`id_activo_biologico = 19`), impidiendo evaluar una asociación ambiental pura sobre la infraestructura que cubra a múltiples activos sin atarse a uno en específico.
2. **TC-M02-221:** La aserción fue diseñada deliberadamente de forma agnóstica (`to.be.oneOf([201, 409, 422])`), reflejando con exactitud la ambigüedad textual del RF-49 entre la Precondición 4 (que admite infraestructuras distintas en la misma granja) y la Restricción 2 / Flujo E2 (que limita el rechazo a granjas diferentes). El test valida qué rama adopta el backend en tiempo de ejecución.

---

## 5. Evidencia Post-condición y Diagnóstico Técnico

### Transcripción de `postcondicion_api.log`

```text
[2026-09-16 00:26:45 UTC] === INICIO DE POST-CONDICIÓN Y CLEANUP — TC-M02-G90 ===
[2026-09-16 00:26:45 UTC] Asociaciones activas detectadas tras la corrida (2 encontradas):
   -> ID: 38, Sensor: 3, Activo: 19, Tipo: ambiental, Estado: ACTIVA, Inicio: 2026-09-16 00:26:01.662232+00:00, Fin: None, Motivo: Evaluacion de asociacion AMBIENTAL en endpoint de activo TC-M02-220
   -> ID: 39, Sensor: 3, Activo: 1, Tipo: directa, Estado: ACTIVA, Inicio: 2026-09-16 00:26:02.441452+00:00, Fin: None, Motivo: Evaluacion de sensor en Infra 1 con activo en Infra 2 dentro de Finca 1 TC-M02-221
[2026-09-16 00:26:45 UTC] Ejecución de Cleanup Append-Only (UPDATE):
   Comando SQL ejecutado:
UPDATE modulo2.asociaciones_activos_sensores
SET estado_asociacion = 'INACTIVA',
    fecha_fin = NOW(),
    motivo = 'Cleanup reevaluacion V2 TC-M02-G90'
WHERE id_activo_biologico IN (1, 19)
  AND id_sensor = 3
  AND estado_asociacion = 'ACTIVA'
  AND fecha_fin IS NULL;
   Filas actualizadas: 2
[2026-09-16 00:26:45 UTC] Verificación de residuos:
   SELECT COUNT(*) -> 0 (Esperado: 0)
   -> VERIFICACIÓN EXITOSA: 0 residuos activos.
[2026-09-16 00:26:45 UTC] Inmutabilidad de modulo2.bitacora_auditoria_m02:
   Total registros de auditoría registrados: 2069 (Inmutables, sin borrado)
[2026-09-16 00:26:45 UTC] === FIN DE POST-CONDICIÓN Y CLEANUP ===
```

### Referencias de Código Fuente del Backend

1. **Ruta y Contrato en Router ([`activo_biologico_router.py:1193-1210`](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/src/biological_assets/infrastructure/routers/activo_biologico_router.py#L1193-L1210)):**
   ```python
   @router.post(
       '/{id_activo}/sensores',
       status_code=201,
       response_model=AsociacionSensorActivoResponse,
       ...
   )
   def asociar_sensor_iot(
       id_activo: int,
       dto: AsociarSensorActivoDTO,
       ...
   ):
   ```
   *Diagnóstico:* El path parameter `{id_activo}` es forzoso en la firma. No existe ruta para asociar un sensor directamente a una infraestructura sin un activo biológico.

2. **Caso de Uso y Validaciones ([`asociar_sensor_activo_use_case.py:53-87, 152-203`](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/src/biological_assets/application/use_cases/gestion/asociar_sensor_activo_use_case.py#L53-L87)):**
   - La firma `execute(self, id_activo: int, dto: AsociarSensorActivoDTO, ...)` recibe obligatoriamente `id_activo`.
   - La regla **V1** ([L81-86](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/src/biological_assets/application/use_cases/gestion/asociar_sensor_activo_use_case.py#L81-L86)) valida inmediatamente que el activo exista en la base de datos (`self.activo_repo.obtener_por_id(id_activo)`), lanzando `ACTIVO_NO_ENCONTRADO` si no existe o si es nulo.
   - En las líneas 152 a 203, el caso de uso contiene ramas específicas para:
     - `if dto.tipo_asociacion == 'DIRECTA':` (valida unicidad de sensor respecto a otros activos).
     - `if dto.tipo_asociacion == 'POBLACIONAL':` (valida cardinalidad de lote y sensor simétrico V8c).
     - **Ausencia absoluta:** **No existe ninguna rama `if dto.tipo_asociacion == 'AMBIENTAL':`**. El tipo ambiental simplemente pasa sin validaciones ni lógica de desacoplamiento de activo.

3. **Soporte en Base de Datos y Modelo ORM ([`asociacion_sensor_activo_model.py:93`](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/src/biological_assets/infrastructure/models/asociacion_sensor_activo_model.py#L93)):**
   ```python
   id_activo_biologico: Mapped[Optional[int]] = mapped_column(Integer)
   ```
   *Diagnóstico:* El modelo de persistencia SQLAlchemy y la tabla PostgreSQL `modulo2.asociaciones_activos_sensores` **ya declaran `id_activo_biologico` como nullable (`Optional[int]`)**. El esquema de base de datos no requiere cambios DDL ni migraciones; el cuello de botella radica exclusivamente en la arquitectura de API y la lógica de aplicación del caso de uso.

4. **Regla de Coherencia Territorial V6 ([`asociar_sensor_activo_use_case.py:130-148`](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/src/biological_assets/application/use_cases/gestion/asociar_sensor_activo_use_case.py#L130-L148)):**
   ```python
   # V6 — Coherencia de infraestructura (misma finca)
   infra_sensor = self.infra_port.obtener_activa(sensor.id_infraestructura_area)
   infra_activo = self.infra_port.obtener_activa(activo.id_infraestructura)
   ...
   if infra_sensor.id_finca != infra_activo.id_finca:
       raise ConflictError(
           code='INFRAESTRUCTURA_INCOMPATIBLE',
           message='La asociación solo es permitida dentro de la misma unidad territorial.'
       )
   ```
   *Diagnóstico:* La regla compara `id_finca`, no `id_infraestructura`. Al estar tanto el Sensor 3 (en Infra 1) como el Activo 1 (en Infra 2) ubicados dentro de la Finca 1, la validación aprueba la solicitud y emite HTTP 201 Created.

### Referencia Contractual del RF-49
- **Definición del Tipo B (Asociación Ambiental Compartida):** *"1 sensor ambiental → N activos que residen en la infraestructura mediada"*. El propósito funcional es permitir la supervisión de condiciones de habitabilidad o ambiente (e.g. temperatura o humedad en un galpón o estanque) sin asociar el sensor a un animal o lote en particular.
- **Contradicción Documental:**
  - *Precondición 4:* Plantea permisividad: *"El activo biológico debe estar asignado a la misma infraestructura productiva a la que pertenece el sensor, o a una infraestructura dentro de la misma granja..."*.
  - *Restricción 2 y Flujo E2:* Restringen estrictamente a nivel de granja (*"El sensor y el activo biológico deben pertenecer a la misma granja"* / Flujo E2 lanza HTTP 409 solo por conflicto entre granjas).

### Nota de Trazabilidad con Respecto al Diagnóstico Previo
> *El diagnóstico read-only previo anticipó que TC-M02-220 obtendría HTTP 201 técnico pero mantendría el fallo funcional INC-M02-G90-01 por ausencia de endpoint para Tipo B puro, y que TC-M02-221 obtendría HTTP 201 pasando con observación OBS-M02-G90-02 por la regla territorial V6. La observación de la ejecución confirma exactamente dicha expectativa, conforme se documenta en la sección 5 del .md.*

---

## 6. Verificación de Limpieza (Cleanup e Inocuidad)

En estricta observancia del principio de inmutabilidad y auditoría append-only (Restricción 8 del RF-49):
1. **Asociaciones Creadas:** Se identificaron las 2 asociaciones originadas por la corrida:
   - ID 38: Sensor 3 → Activo 19 (tipo `ambiental`, creada en TC-M02-220).
   - ID 39: Sensor 3 → Activo 1 (tipo `directa`, creada en TC-M02-221).
2. **Sentencia de Cleanup Append-Only Ejecutada:**
   ```sql
   UPDATE modulo2.asociaciones_activos_sensores
   SET estado_asociacion = 'INACTIVA',
       fecha_fin = NOW(),
       motivo = 'Cleanup reevaluacion V2 TC-M02-G90'
   WHERE id_activo_biologico IN (1, 19)
     AND id_sensor = 3
     AND estado_asociacion = 'ACTIVA'
     AND fecha_fin IS NULL;
   ```
   *Salida:* `2 filas actualizadas`. Prohibido el uso de sentencias `DELETE`.
3. **Comprobación de Residuos:**
   ```sql
   SELECT COUNT(*) AS asociaciones_activas_remanentes
   FROM modulo2.asociaciones_activos_sensores
   WHERE id_activo_biologico IN (1, 19)
     AND id_sensor = 3
     AND estado_asociacion = 'ACTIVA'
     AND fecha_fin IS NULL;
   ```
   *Resultado obtenido:* **`0`**. Se garantiza 0 contaminación en el entorno de pruebas.
4. **Inmutabilidad de Auditoría:** La tabla `modulo2.bitacora_auditoria_m02` contabilizó 2069 registros íntegros, sin alteraciones destructivas ni truncamientos.

---

## 7. Conclusiones, Diagnóstico Técnico y Dictamen Final

### Estado de Defectos y Observaciones

#### 1. Defecto INC-M02-G90-01 (Asociación AMBIENTAL Pura no Implementada)
- **Estado:** ⚠️ **CONFIRMADO COMO GAP ARQUITECTÓNICO DE LA API (PERSISTE)**.
- **Descripción:** El endpoint `POST /activos-biologicos/{id_activo}/sensores` exige forzosamente el parámetro de ruta `{id_activo}`, imposibilitando registrar asociaciones de tipo `AMBIENTAL` directas a una infraestructura productiva pura (Tipo B del RF-49). En el caso de uso no existe rama condicional para el tipo ambiental. La base de datos ya soporta `id_activo_biologico = NULL`.
- **Clasificación:** FLUJO / HTTP_COM (Contrato de API incompleto frente al requerimiento funcional).
- **Severidad:** **Severo (S2)**.
- **Acciones Requeridas para Escalamiento:**
  1. **Análisis Funcional:** Confirmar formalmente si el Tipo B (*1 sensor ambiental → infraestructura → N activos*) se mantiene como requerimiento mandatorio del RF-49.
  2. **Arquitectura de Software:** Si se mantiene, definir el contrato del nuevo endpoint. Alternativas viables:
     - *Opción 1 (Recomendada):* `POST /configuracion/infraestructuras/{id_infraestructura}/sensores`.
     - *Opción 2:* `POST /activos-biologicos/sensores/ambiental` con payload `{ "sensor_id": X, "id_infraestructura": Y }`.
     - *Opción 3:* Modificar el endpoint actual haciendo `{id_activo}` opcional o permitir un valor neutro.
  3. **Desarrollo Backend:** Implementar el endpoint acordado, su DTO de entrada, la rama en el caso de uso y el mapeo al repositorio existente (el cual ya soporta `id_activo_biologico = NULL`).
  4. **QA / Automatización:** Actualizar el subcaso TC-M02-220 de Newman para apuntar al nuevo endpoint de infraestructura pura en cuanto sea desplegado.

#### 2. Observación OBS-M02-G90-02 (Contradicción Interna del RF-49)
- **Estado:** ⚠️ **CONFIRMADO COMO HALLAZGO DE CALIDAD DEL REQUISITO (DOCUMENTAL)**.
- **Descripción:** Existe discrepancia formal entre la Precondición 4 (*"misma infraestructura o misma granja"*) y la Restricción 2 / Flujo E2 (*"misma granja"*). El backend implementa fielmente el criterio de "misma finca" en la regla V6.
- **Veredicto Técnico Backend:** ✅ **PASS CON OBSERVACIÓN**. El comportamiento del backend es consistente y coherente con la Restricción 2 y el Flujo E2.
- **Acción Requerida:** Análisis Funcional debe armonizar la redacción de la Precondición 4 del RF-49 para reflejar con precisión si se permite interoperabilidad entre infraestructuras de la misma finca o si debe ser estricto a nivel de infraestructura.

### Subcasos Colaterales
- No se registraron fallos ni regresiones colaterales en las entidades asociadas.

### Hallazgos Secundarios no Bloqueantes
- **Fixtures Hardcodeados en Colección:** El test Newman utiliza identificadores fijos (Activos 1 y 19, Sensor 3, Dispositivo 1) sin parametrización dinámica mediante variables de entorno.
- **Desacoplamiento de BD vs API:** El esquema de base de datos se encuentra preparado con anticipación (`nullable=True`), minimizando sustancialmente el costo técnico de resolución una vez se diseñe el endpoint.

### Recomendación Estratégica y de Seguimiento
- **NO programar una Reevaluación V3** hasta tanto:
  1. Análisis Funcional defina el futuro del Tipo B del RF-49 y la regla territorial unificada.
  2. Arquitectura y Desarrollo entreguen el endpoint para asociaciones a nivel de infraestructura.
- **Escalamiento Inmediato:** Escalar el presente informe y el defecto `INC-M02-G90-01` a las mesas de Análisis Funcional, Arquitectura y Desarrollo Backend.
