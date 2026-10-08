# Reporte de Reevaluación V2: TC-M02-G25

## 1. Encabezado y Metadatos de Ejecución

- **Título Formal:** TC-M02-G25 · RF-36 / RF-40 · INC-M02-38-G25 (Gestión Poblacional de Activos Biológicos)
- **Fecha de Reevaluación V2:** 2026-09-14 23:25:55 UTC-5 (2026-09-15 04:25:55 UTC)
- **Fecha de Corrida Previa V1:** 2026-09-09 02:05:42 UTC
- **Entorno de Pruebas:** TEST (`https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test`)
- **Base de Datos:** PostgreSQL TEST (`158.69.200.27:5448/sgpmp_test`, usuario `member_qa`)
- **Herramienta de Ejecución:** Newman CLI v6.2.2 con plugin `htmlextra`
- **Script Ejecutado:** `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G25/test_tc_m02_g25.json`
- **Reporte HTML Generado:** `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G25/EvaluacionV2/RESULTADOS/G25-REEVAL-V2-20260914-231500/reporte_g25_v2.html`
- **Veredicto Global:** ⚠️ **PASS PARCIAL (1/2 PASS, 1/2 INCUMPLIMIENTO CONTRACTUAL PENDIENTE DE IMPLEMENTACIÓN + DEFECTO DEL TEST)**

---

## 2. Objetivo de la Reevaluación y Resumen Ejecutivo

### 2.1 Contexto del Fallo Original (INC-M02-38-G25)
En la corrida inicial V1 (2026-09-09), el caso compuesto TC-M02-G25 fue calificado como **RECHAZADO** debido a la apertura del incidente severo `INC-M02-38-G25`. Dicho caso agrupaba dos subcasos destinados a validar reglas zootécnicas y de balance poblacional bajo el RF-36 (CU03):
1. **TC-M02-051 (Baja excesiva):** Validación de que una baja no supere la existencia actual del lote.
2. **TC-M02-052 (Densidad máxima por especie):** Validación de que un evento no eleve la densidad del lote por encima del límite biológico permitido para la especie.

El ticket original INC-M02-38-G25 tenía razón en el fondo (existe un incumplimiento contractual del RF-36 en el backend), aunque erró en la forma (fórmula de densidad y mecanismo de mutación).

### 2.2 Análisis Causal Tripartito Basado en el Contrato Literal del RF-36
A partir de la revisión minuciosa del texto formal del requerimiento funcional RF-36 y su contrastación con la ejecución en vivo contra PostgreSQL TEST y el código fuente, se identificaron tres causas técnicas independientes que explican el comportamiento observado:

#### Citas Literales Obligatorias del RF-36:
> **Fórmula de densidad (Sección "Proceso"):**  
> *"densidad = cantidad_actual / superficie"*  
> *"La densidad es un valor calculado automáticamente por el sistema y no puede ser modificada manualmente por el usuario."*

> **Validación obligatoria (Sección "Proceso"):**  
> *"Validación de densidad: densidad no debe superar la densidad_maxima_por_especie definida en M09."*

> **Flujo Alterno 4 (Sección "Flujos Alternos"):**  
> *"Exceso de densidad:*  
> *Precondición no cumplida: La densidad calculada supera la densidad_maxima_por_especie.*  
> *Mensaje de error: 409 CONFLICT - 'La densidad del lote supera el máximo permitido para la especie'*  
> *Estado final de excepción: Operación rechazada."*

> **Criterios de Aceptación Relacionados:**  
> *"El sistema calcula correctamente la densidad del lote."*  
> *"El sistema valida coherencia entre métricas calculadas."*

> **Mecanismo de modificación de cantidad_actual (Sección "Entradas"):**  
> *"Se modifica únicamente mediante eventos de tipo BAJA o mediante registros de ingresos asociados a eventos."*

> **Precondiciones Formales (Sección "Precondiciones"):**  
> *"El usuario debe estar autenticado (RF-02). Debe existir al menos una especie productiva configurada (RF-15). Debe existir infraestructura productiva registrada (RF-20). El activo biológico debe haber sido registrado como tipo lote (RF-33). El usuario debe tener permisos para gestionar activos (RF-04)."*  
> *(Nota contractual: El RF-36 NO incluye "fase activa" entre sus precondiciones).*

#### Las Tres Causas Identificadas:
1. **(a) Incumplimiento Contractual del RF-36 (Defecto Activo de Backend):**
   El backend no implementa la validación de densidad máxima exigida contractualmente en el Flujo Alterno 4 y en los criterios de aceptación del RF-36. Ningún use case de eventos poblacionales contrasta la densidad resultante contra el límite zootécnico de la especie ni retorna el código `HTTP 409 CONFLICT`.
2. **(b) Defecto Conceptual del Test TC-M02-052:**
   El test original V1 pretendió provocar el rechazo por densidad enviando un payload a `POST /activos-biologicos/{id}/eventos/crecimiento` con `cantidad_medida: 250`. En el backend (`src/biological_assets/application/use_cases/gestion/registrar_evento_crecimiento_use_case.py`), `cantidad_medida` es estrictamente el tamaño muestral de individuos evaluados en un muestreo de peso (RF-40), no un ingreso poblacional. No existe endpoint de ingreso poblacional a lote.
3. **(c) Precondición no Satisfecha en Runtime (`SIN_FASE_ACTIVA`):**
   Al ejecutarse la prueba sobre un lote sin fase productiva activa asignada (como el lote 345), el backend detonó la guarda previa `HTTP 422 SIN_FASE_ACTIVA`, abortando la petición antes de cualquier cálculo biométrico. Dicha precondición no está contemplada en el contrato del RF-36.

### 2.3 Tabla Resumen Comparativa de Subcasos

| Sub-caso | Código Esperado | Código Obtenido | Aserciones | Veredicto | Causa Raíz |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **TC-M02-051** | 400 / 422 | **422 Unprocessable Entity** | 2/2 PASS | ✅ **PASS** | N/A (regla implementada conforme, backend rechaza bajas superiores a existencia). |
| **TC-M02-052** | 409 Conflict | **422 Unprocessable Entity** | 0/2 FAIL | ⚠️ **INCUMPLIMIENTO CONTRACTUAL + DEFECTO DEL TEST** | RF-36 no implementado en backend. |

---

## 3. Estado Previo de la Base de Datos (Pre-condición)

### 3.1 Justificación Técnica de Aislamiento (No reutilización de Lote 130)
El lote 130 utilizado en la corrida V1 se encuentra severamente contaminado:
- Presenta 26 eventos acumulados en su bitácora histórica hasta el 2026-09-13.
- Su infraestructura fue reasignada a Estanque-01 con un área masiva de 2500 m².
- Su existencia fue decrementada a `cantidad_actual = 3`.
- Cualquier validación de fechas o densidad en lote 130 colisiona con el historial previo.

### 3.2 Intento de Creación de Lote Dinámico vs. Selección de Lote Candidato Aislado
Durante el pre-flight de esta fase se ejecutó un intento de creación de un lote nuevo vía API (`POST /activos-biologicos`). Dicho llamado retornó **HTTP 500 (ERROR_INTERNO)**. La causa raíz identificada fue que el backend desplegado en TEST consulta `modulo9.metricas_produccion.tipo_dato`, una columna introducida en el commit `fa249d76` mediante la migración Alembic `b92f7e1a4c63`, la cual **nunca fue aplicada en la base de datos PostgreSQL TEST**.

**Nota de Trazabilidad del Pivot Técnico:**
Ante el fallo de `POST /activos-biologicos` por la migración pendiente `b92f7e1a4c63`, y en estricto apego a las directivas del QA Lead y a las Reglas de Base de Datos (**PROHIBIDO aplicar DDL, alterar esquemas o ejecutar migraciones Alembic**), se tomó la decisión técnica de pivotar hacia la selección del lote preexistente **ID 345**. Se verificó formalmente su aislamiento previo (0 eventos registrados en `modulo2.eventos_activos`, sin historial previo colateral), cumpliendo plenamente con los criterios de aislamiento estipulados en la directiva D4 para no bloquear la reevaluación:
- **ID Activo:** 345
- **Tipo:** POBLACIONAL
- **Especie:** 4 (Cachama Blanca)
- **Infraestructura:** 3 (Jaula Flotante, superficie de 10.0 m², ideal para pruebas zootécnicas de densidad)
- **Existencia Inicial:** 10 individuos (`cantidad_actual = 10`)
- **Historial previo:** 0 eventos (lote completamente limpio e incontaminado)

### 3.3 Query SELECT del Estado Previo del Lote de Prueba (ID 345)
```sql
SELECT a.id_activo_biologico, a.tipo, a.id_especie, a.id_infraestructura, a.id_estado, 
       e.nombre AS nombre_estado, d.cantidad_inicial, d.cantidad_actual, d.densidad, d.peso_promedio
FROM modulo2.activos_biologicos a
LEFT JOIN modulo2.detalles_activos_biologicos_poblacionales d 
  ON a.id_activo_biologico = d.id_activo_biologico
LEFT JOIN modulo2.estados_activos_biologicos e
  ON a.id_estado = e.id_estado_activo_biologico
WHERE a.id_activo_biologico = 345;
```
**Resultado previo en vivo:**
```text
(345, 'POBLACIONAL', 4, 3, 1, 'ACTIVO', 10, 10, None, None)
```

### 3.4 Query SELECT de Columnas Reales de `modulo9.especies` y Ausencia de Densidad
Para verificar la estructura exacta del catálogo de especies, se ejecutó en vivo contra PostgreSQL TEST:
```sql
SELECT column_name, data_type, ordinal_position
FROM information_schema.columns
WHERE table_schema='modulo9' AND table_name='especies'
ORDER BY ordinal_position;
```
**Salida LITERAL de la consulta en vivo:**
```text
('id_especie', 'integer', 1)
('nombre', 'character varying', 2)
('descripcion', 'character varying', 3)
('fecha_actualizacion', 'timestamp with time zone', 4)
('fecha_creacion', 'timestamp with time zone', 5)
('es_activo', 'boolean', 6)
```

Adicionalmente, se confirmó la ausencia absoluta de columnas de densidad máxima en `modulo9`:
```sql
SELECT table_schema, table_name, column_name, data_type
FROM information_schema.columns
WHERE (column_name ILIKE '%densidad%' OR column_name ILIKE '%maxim%')
  AND table_schema NOT IN ('pg_catalog', 'information_schema')
ORDER BY table_schema, table_name, column_name;
```
**Resultado en vivo:**
- `modulo2.detalles_activos_biologicos_poblacionales.densidad` (numeric)
- `modulo4.*` (tablas de predicción analítica)
- **Total columnas de densidad máxima en `modulo9`:** **0 columnas** (evidencia en vivo de la falta de soporte en base de datos).

---

## 4. Resultados Detallados de la Ejecución (Newman)

La ejecución automatizada se llevó a cabo utilizando Newman v6.2.2 sobre la colección unificada `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G25/test_tc_m02_g25.json`.

### 4.1 Tabla Petición a Petición

| Paso | Método | Endpoint | Código Esperado | Código Obtenido | Tiempo (ms) | Estado |
| :---: | :---: | :--- | :---: | :---: | :---: | :---: |
| **0** | `POST` | `/sesiones/` | 200 OK | **200 OK** | 905 ms | ✅ PASS |
| **1** | `POST` | `/activos-biologicos/345/eventos/baja` | 400 / 422 | **422 Unprocessable Entity** | 126 ms | ✅ PASS |
| **2** | `POST` | `/activos-biologicos/345/eventos/crecimiento` | 409 Conflict | **422 Unprocessable Entity** | 137 ms | ⚠️ INCUMPLIMIENTO / DEFECTO TEST |
| **3** | `PATCH`| `/activos-biologicos/345/estado` | 200 OK | **200 OK** | 157 ms | ✅ PASS |

### 4.2 Métricas Globales de la Corrida
- **Total Peticiones Ejecutadas:** 4 / 4
- **Total Aserciones:** 6
- **Aserciones PASS:** 4
- **Aserciones FAIL:** 2 (100% asociadas al subcaso TC-M02-052)
- **Tiempo Total de Ejecución:** 1,711 ms
- **Tiempo de Respuesta Promedio:** 331 ms (Mínimo: 126 ms, Máximo: 905 ms)
- **Exit Code:** 0 (ejecutado con `--suppress-exit-code` para permitir exporte íntegro de reportes bajo bloqueo contractual)

### 4.3 Detalle de Aserciones Fallidas en TC-M02-052 y Análisis Técnico Tripartito
```text
1. AssertionError: Código HTTP esperado: 409 Conflict
   expected response to have status code 409 but got 422
   at assertion:0 in test-script
   inside "2. TC-M02-052: Registrar evento de crecimiento que excede densidad (RF-36 - Bloqueado)"

2. AssertionError: Mensaje de error contiene rechazo por superación de densidad
   expected false to be true
   at assertion:1 in test-script
   inside "2. TC-M02-052: Registrar evento de crecimiento que excede densidad (RF-36 - Bloqueado)"
```

**Análisis Técnico Tripartito del Fallo:**
La respuesta obtenida del backend fue `HTTP 422 {"error_code":"SIN_FASE_ACTIVA","message":"El activo no tiene una fase productiva activa. Asocie el activo a un ciclo productivo antes de registrar eventos de crecimiento."}`. El análisis riguroso distingue tres factores técnicos independientes que coexisten:

1. **Defecto Conceptual del Test (Preexistente en V1):**
   El diseño original de la prueba TC-M02-052 asumió erróneamente que enviar `cantidad_medida: 250` a `/eventos/crecimiento` representaba un "ingreso masivo de 250 individuos" para saturar la densidad del lote. En la arquitectura DDD del backend (`src/biological_assets/application/use_cases/gestion/registrar_evento_crecimiento_use_case.py`), dicho campo corresponde estrictamente al tamaño de muestra de individuos evaluados en un muestreo biométrico de peso (RF-40), no a un incremento de stock poblacional. El backend no posee endpoints de ingreso de stock poblacional a lotes existentes.
2. **Precondición no Satisfecha en Tiempo de Ejecución (`SIN_FASE_ACTIVA`):**
   El lote sintético aislado 345 no contaba con una fase productiva activa asignada. En la implementación de `RegistrarEventoCrecimientoUseCase` (líneas 66-71), la validación de fase productiva activa (`SIN_FASE_ACTIVA`) se ejecuta de manera temprana (guarda previa), deteniendo el flujo con `HTTP 422` **antes de cualquier evaluación posterior de parámetros biométricos, zootécnicos o de densidad**. Esta precondición no está contemplada en el contrato del RF-36.
3. **Incumplimiento Contractual Activo del RF-36 (Causa Raíz del Defecto):**
   Aun si el lote hubiese contado con fase productiva activa, el código HTTP esperado `409 Conflict` y el mensaje de rechazo por superación de densidad no habrían sido emitidos: el Flujo Alterno 4 del RF-36 exige expresamente rechazar con `409 CONFLICT` y el mensaje *"La densidad del lote supera el máximo permitido para la especie"*, regla que **no está implementada en el backend**, sustentada técnicamente por la inexistencia de la columna `densidad_maxima_por_especie` en `modulo9.especies`.

---

## 5. Evidencia de Estado en BD PostgreSQL TEST (Post-condición y Auditoría)

Tras la ejecución de Newman, se verificó el estado físico en la base de datos PostgreSQL TEST mediante consultas directas en modo solo lectura.

### 5.1 Query SELECT del Estado Posterior del Lote Sintético (ID 345)
```sql
SELECT a.id_activo_biologico, a.tipo, a.id_especie, a.id_infraestructura, a.id_estado, 
       e.nombre AS nombre_estado, d.cantidad_inicial, d.cantidad_actual, d.densidad, d.peso_promedio
FROM modulo2.activos_biologicos a
LEFT JOIN modulo2.detalles_activos_biologicos_poblacionales d 
  ON a.id_activo_biologico = d.id_activo_biologico
LEFT JOIN modulo2.estados_activos_biologicos e
  ON a.id_estado = e.id_estado_activo_biologico
WHERE a.id_activo_biologico = 345;
```
**Resultado obtenido en vivo:**
```text
(345, 'POBLACIONAL', 4, 3, 2, 'INACTIVO', 10, 10, None, None)
```

### 5.2 Verificación de Inmutabilidad ante TC-M02-051
- La existencia actual (`cantidad_actual`) permanece exactamente en **10 individuos**.
- El rechazo por regla de negocio (`CANTIDAD_BAJA_SUPERIOR_EXISTENCIA`, 15 > 10) detuvo la transacción antes de cualquier persistencia.
- Verificación de eventos de baja en lote 345:
  ```sql
  SELECT COUNT(*) FROM modulo2.eventos_bajas eb
  JOIN modulo2.eventos_activos ea ON eb.id_evento = ea.id_eventos
  WHERE ea.id_activo_biologico = 345;
  ```
  **Total registros encontrados:** `0` (Cero bajas registradas, inmutabilidad garantizada).

### 5.3 Verificación de Inmutabilidad ante TC-M02-052
Al consultar la tabla de eventos de crecimiento mediante:
```sql
SELECT COUNT(*) FROM modulo2.eventos_crecimiento ec
JOIN modulo2.eventos_activos ea ON ec.id_evento = ea.id_eventos
WHERE ea.id_activo_biologico = 345;
```
**Salida LITERAL de PostgreSQL TEST:**
```text
relation "modulo2.eventos_crecimiento" does not exist
```
*Diagnóstico técnico de esquema:* En el esquema físico de PostgreSQL TEST, la tabla base fue creada con un error tipográfico en su DDL: `modulo2.eventos_crecimeinto` (`BASE TABLE`), existiendo paralelamente la vista canónica `modulo2.vw_rf46_eventos_crecimiento` (`VIEW`).

Al ejecutar la verificación contra la tabla base física y contra la vista oficial del sistema:
```sql
-- Consulta contra tabla física base:
SELECT COUNT(*) FROM modulo2.eventos_crecimeinto ec
JOIN modulo2.eventos_activos ea ON ec.id_evento = ea.id_eventos
WHERE ea.id_activo_biologico = 345;

-- Consulta contra vista canónica:
SELECT COUNT(*) FROM modulo2.vw_rf46_eventos_crecimiento
WHERE id_activo_biologico = 345;
```
**Salida LITERAL:**
- Conteo en `modulo2.eventos_crecimeinto`: `(0,)`
- Conteo en `modulo2.vw_rf46_eventos_crecimiento`: `(0,)`

**Resultado:** Cero registros espurios persistidos; inmutabilidad total garantizada.

### 5.4 Auditoría de Históricos de Cambio de Estado (RF-44)
Se comprobó la inserción del evento de auditoría de estado generado por el paso de Cleanup:
```sql
SELECT id_historico_estado_activo, id_activo_biologico, id_estado_anterior, id_estado_nuevo, 
       fecha_cambio, motivo_cambio, modulo_origen, id_usuario
FROM modulo2.historicos_estados_activos
WHERE id_activo_biologico = 345
ORDER BY id_historico_estado_activo DESC LIMIT 1;
```
**Resultado obtenido en vivo:**
```text
(184, 345, 1, 2, '2026-09-14 00:00:00+00', 'Inactivación lógica de cleanup post-reevaluación V2 TC-M02-G25', 'MANUAL', 104)
```

---

## 6. Verificación de Limpieza (Cleanup e Inocuidad de Datos)

En estricto cumplimiento de las políticas de testing del proyecto SGPMP:
1. **Inactivación Lógica:** El lote de prueba ID 345 fue transitado al estado `INACTIVO` (`id_estado = 2`) vía API oficial (`PATCH /activos-biologicos/345/estado`), disparando los triggers y bitácoras de auditoría de negocio correspondientes.
2. **Cero Datos Residuales:** No existen lotes activos de esta prueba en el sistema ni registros huérfanos.
3. **Cero DDL:** En ninguna etapa de la reevaluación se ejecutaron comandos `CREATE`, `ALTER`, `DROP`, `TRUNCATE`, `DELETE`, creación de triggers ni migraciones Alembic.
4. **Script de Verificación:** El script `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G25/cleanup_tc_m02_g25.sql` fue ejecutado y validó que todos los conteos de registros residuales se encuentran en `0`.

---

## 7. Conclusiones, Diagnóstico Técnico y Dictamen Final

### 7.1 Estado del Defecto INC-M02-38-G25
- **Subcaso TC-M02-051 (Baja Excesiva):** ✅ **PASS / RESUELTO**. El backend implementa correctamente la validación que impide decrementar una cantidad superior a la existencia actual del lote, respondiendo con `HTTP 422 Unprocessable Entity` y el código de error `CANTIDAD_BAJA_SUPERIOR_EXISTENCIA`. Conforme, sin cambios requeridos.
- **Subcaso TC-M02-052 (Densidad Máxima):** ⚠️ **INCUMPLIMIENTO CONTRACTUAL DEL RF-36 (defecto de backend pendiente) + PRECONDICIÓN NO SATISFECHA (SIN_FASE_ACTIVA, requiere aclaración de contrato).**

### 7.2 Impacto Contractual sobre RF-36
- El RF-36 exige taxativamente la validación de exceso de densidad con respuesta `HTTP 409 CONFLICT` (Flujo Alterno 4: *"La densidad del lote supera el máximo permitido para la especie"*).
- El backend **NO la implementa** en ningún caso de uso de gestión poblacional, lo que constituye un **incumplimiento contractual activo**.
- La ausencia de la columna `densidad_maxima_por_especie` en la tabla `modulo9.especies` es la causa técnica en base de datos, pero **NO elimina la obligación funcional del backend** frente a los criterios de aceptación y flujos alternos formalmente especificados en el RF-36.
- La resolución definitiva de este defecto requiere el desarrollo de un PR en backend junto con una migración de esquema en Módulo 9.

### 7.3 Recomendaciones Técnicas
1. **Módulo 9 (Configuración):** Diseñar y ejecutar la migración Alembic para incorporar la columna `densidad_maxima_por_especie` en `modulo9.especies` (previa autorización del equipo de Base de Datos y del Product Owner).
2. **Módulo 2 (Activos Biológicos):** Implementar la validación de densidad en `RegistrarEventoCrecimientoUseCase` (y en cualquier otro caso de uso donde se recalcule densidad o balance poblacional), emitiendo el código `HTTP 409 CONFLICT` y el mensaje contractual requerido cuando `densidad > densidad_maxima_por_especie`.
3. **QA / Testing:** Rediseñar la prueba automatizada TC-M02-052 con el endpoint y payload conceptualmente correctos para validar la regla de densidad una vez el backend implemente el cambio.
4. **Incidente INC-M02-38-G25:** **MANTENER ABIERTO** como defecto de backend pendiente de implementación. NO reclasificar a "bloqueo estructural" pasivo. NO cerrar el incidente hasta la entrega del PR correctivo y su verificación en TEST.

### 7.3.1 Primer Hallazgo Colateral: Migración Pendiente de Métricas en TEST
Durante la fase de pre-flight se identificó un defecto crítico independiente en el entorno TEST:
- **Descripción:** El endpoint `POST /activos-biologicos` retorna `HTTP 500 (ERROR_INTERNO)` de manera generalizada ante intentos de creación de nuevos activos biológicos.
- **Causa Raíz:** En la capa de infraestructura (`src/biological_assets/infrastructure/adapters/parametros_especie_m09_adapter.py`), el backend consulta el modelo `MetricaProduccionModel`, el cual referencia el atributo `tipo_dato`. Dicho campo fue incorporado en el commit `fa249d76` (`fix(rf16-rf33): agregar metadatos a atributos dinámicos`) mediante la migración Alembic `b92f7e1a4c63_agregar_tipo_dato_a_metricas_produccion.py`. No obstante, dicha migración **nunca fue aplicada en la base de datos PostgreSQL TEST**, provocando el error `UndefinedColumn: column metricas_produccion.tipo_dato does not exist`.
- **Evidencia:** Registro de error 500 documentado en `console_v2.log` y traza interna capturada durante pre-flight.
- **Recomendación:** Abrir un issue técnico independiente para que el equipo de DevOps / Base de Datos aplique la migración `b92f7e1a4c63` en PostgreSQL TEST.
- **Delimitación:** Este hallazgo **NO pertenece a INC-M02-38-G25** ni al alcance funcional de TC-M02-G25; constituye un incidente colateral de sincronización de esquema en el entorno TEST.

### 7.3.2 Segundo Hallazgo Colateral: Typo en DDL físico de tabla de crecimiento
- **Descripción:** En el esquema físico de PostgreSQL TEST existe una tabla base con nombre tipográficamente incorrecto: `modulo2.eventos_crecimeinto` (en lugar del canónico `eventos_crecimiento`). Adicionalmente existe la vista oficial `modulo2.vw_rf46_eventos_crecimiento`, que probablemente es el objeto efectivamente consultado por el backend.
- **Evidencia en vivo:** Al ejecutar `SELECT COUNT(*) FROM modulo2.eventos_crecimiento`, PostgreSQL respondió literalmente: `relation "modulo2.eventos_crecimiento" does not exist`. Al consultar la tabla física base `modulo2.eventos_crecimeinto` y la vista canónica `modulo2.vw_rf46_eventos_crecimiento`, ambas retornaron `(0,)` para el lote 345.
- **Impacto:** Potencial afectación a herramientas externas o consultas ad-hoc que referencien el nombre canónico directamente. La operación normal del backend no se ve comprometida en los flujos probados.
- **Recomendación:** Abrir issue técnico independiente para que el equipo de DevOps/BD evalúe la corrección del DDL físico (renombrado de tabla y ajuste de dependencias) en el próximo ciclo de mantenimiento de TEST.
- **Delimitación:** Este hallazgo NO pertenece a INC-M02-38-G25 ni al alcance funcional de TC-M02-G25; es un defecto de integridad de esquema del entorno.

### 7.3.3 Tercer Hallazgo Colateral: Validación SIN_FASE_ACTIVA no prevista en RF-36
- **Descripción:** El backend rechaza el registro de eventos de crecimiento con `HTTP 422 SIN_FASE_ACTIVA` cuando el lote no tiene una fase productiva activa asociada (`src/biological_assets/application/use_cases/gestion/registrar_evento_crecimiento_use_case.py`, líneas 66-71).
- **Evidencia:** Respuesta capturada en `console_v2.log` durante la ejecución de Newman en el Paso 2 (`HTTP 422 {"error_code":"SIN_FASE_ACTIVA"}`).
- **Contraste Contractual:** La sección de "Precondiciones" del RF-36 enumera taxativamente: autenticación (RF-02), especie configurada (RF-15), infraestructura registrada (RF-20), activo registrado como lote (RF-33) y permisos (RF-04). En ningún apartado se estipula la existencia de una "fase activa" como precondición de este requerimiento.
- **Recomendación:** Escalar al Product Owner y Arquitectura para definir si esta regla corresponde a una dependencia funcional no documentada del RF-37 o si constituye una sobre-validación restrictiva.

### 7.3.4 Cuarto Hallazgo Colateral: Ausencia de Endpoint para Ingreso de Individuos
- **Descripción:** La sección "Entradas" del RF-36 define que `cantidad_actual` *"se modifica únicamente mediante eventos de tipo BAJA o mediante registros de ingresos asociados a eventos"*. Sin embargo, no existe en la API ningún endpoint habilitado para registrar ingresos poblacionales a un lote (únicamente decrementos vía baja RF-45).
- **Evidencia:** Inspección exhaustiva de las rutas expuestas en `src/biological_assets/infrastructure/routers/activo_biologico_router.py` y en la especificación OpenAPI de TEST (`openapi-test.json`).
- **Recomendación:** Escalar al Product Owner para aclarar si el flujo de ingreso poblacional posterior a la siembra inicial fue diferido a otro requerimiento o si constituye una brecha funcional en la API.

---

### Referencias de Artefactos de Ejecución (Rutas Relativas)
- **Colección Postman/Newman V2:** `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G25/test_tc_m02_g25.json`
- **Script SQL de Verificación:** `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G25/cleanup_tc_m02_g25.sql`
- **Resumen Técnico Newman JSON:** `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G25/EvaluacionV2/RESULTADOS/G25-REEVAL-V2-20260914-231500/newman_summary_v2.json`
- **Reporte Visual HTML Newman Extra:** `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G25/EvaluacionV2/RESULTADOS/G25-REEVAL-V2-20260914-231500/reporte_g25_v2.html`
- **Registro Completo de Consola:** `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G25/EvaluacionV2/RESULTADOS/G25-REEVAL-V2-20260914-231500/console_v2.log`
- **Carpeta de Evidencias Auxiliares:** `tests/Test_Testing/Test_Modulo2/RF-36/TC-M02-G25/EvaluacionV2/RESULTADOS/G25-REEVAL-V2-20260914-231500/screenshots/`
