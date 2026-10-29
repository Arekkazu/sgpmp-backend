# DEV-43 — RF-62: gaps, inactividad, límites físicos y alertas técnicas

Fecha: 2026-10-21. Historia #3699. Tareas #3792, #3793 y #3794. Épica #3667.

Rama: `codex/dev43-calidad-temporal-alertas`, creada desde `origin/dev`
(`6113a3883f7ca3a9b2991148414451323f6f9a81`). DEV-41 permanece en su PR
independiente; no se mezclaron ramas de otras tareas.

## 1. Diagnóstico y fuentes contrastadas

Se revisaron el requerimiento de DEV-43, los RF actualizados de M03/M09 y
`Especificacion-Requerimientos-Modulo3.md`, compartido durante el desarrollo.
De esta última fuente se contrastaron RF-60 y RF-62: fases 1, 3, 5 y 8,
restricción 8, E5, salidas y reglas de visibilidad técnica.
Los documentos se utilizaron como referencias funcionales; sus ejemplos no
constituyen autorización para modificar bases compartidas.

| Componente | Hecho confirmado | Corrección / límite |
|---|---|---|
| Fase 5 RF-62 | Solo contenía comentarios; la serie devolvía valores sin fechas | Agregar contexto temporal real y comparación estricta |
| Frecuencia | DEV-14 consulta M09; cada telemetría puede conservar `frecuencia_muestreo_min` | Reutilizar snapshots disponibles y configuración existente |
| Inactividad | Existe `modulo3.periodos_inactividad`, con dispositivo, sensores, inicio, fin y estado | Consultar esa fuente; no inferir inactividad con otro algoritmo |
| E5 | No se registraba la omisión explícita | Evento RF-63, sin evaluación APTO/INDETERMINADA ficticia |
| Límites físicos | Diccionario `_RANGOS_FISICOS` en Python | Retirarlo; separar snapshot verificado de valores actuales sin versión |
| Versión aplicada | El campo existe en entidad, modelo, repositorio y respuesta | Transportar el identificador junto con el snapshot; no requiere columna nueva |
| M09 versionado | En esquema/migraciones inspeccionados, `variables_ambientales` solo expone límites actuales | Integración histórica por variable/especie/fecha pendiente |
| Alertas RF-62 | Había auditoría, sin generación técnica | Reutilizar tabla/repositorio RF-57 y tipo TECNICA |
| Permisos | Recurso 36 para alertas técnicas; Productor no tiene acceso en la semilla real | Conservar RBAC y separación de endpoints |
| Ámbito técnico | El listado técnico no pasaba el alcance por finca | Aplicar el adaptador compartido también a consulta y actualización técnica |
| Auditoría | El mecanismo existente es best-effort | Para el nuevo flujo, exigir ID persistido y confirmar con evaluación/alerta |

La nueva especificación confirma:

- `gap_real > 2 × intervalo_esperado`, sin anomalía en la igualdad.
- Exclusión de periodos reconocidos por RF-60.
- E5 cancela la evaluación y registra `EVALUACION_OMITIDA_POR_INACTIVIDAD`, sin flags ni índice.
- Límites vigentes en `timestamp_captura`, no valores actuales atribuidos al pasado.
- Congelamiento de cualquier severidad y drift significativo requieren alerta TECNICA al Ingeniero.

No se encontró una regla adicional para solapamiento parcial ni una severidad
de alerta de drift. Los descuentos del índice de calidad no se interpretaron
como severidades RF-57. Tampoco se reutilizó la auditoría DML genérica como si
fuera un catálogo formal de vigencias físicas: su timestamp sin zona y su
identificador de log no establecen por sí solos esa semántica.

### Inspección de la base oficial

Se intentó una consulta de esquema con `default_transaction_read_only=on`
contra `sgpmp_dev` en `127.0.0.1:5447`, usando la configuración disponible.
La conexión devolvió `OperationalError`; no se pudo verificar si existen cambios
fuera de migraciones. No se realizaron escrituras en esa base ni se atribuye
el estado del baseline al despliegue oficial.

## 2. Implementación de #3792

### Contexto temporal

`ContextoCalidadPort` transporta lecturas fechadas, periodos RF-60, frecuencia y
snapshot de límites. La entidad no ejecuta SQL.

El adaptador real consulta lecturas del mismo sensor **y variable**, anteriores
a la captura, con estado `LECTURA_VALIDA`, en orden determinista por captura e ID.
No utiliza la fecha de recepción o procesamiento para medir gaps.

La comparación utiliza segundos antes de convertir a minutos; no trunca el
resultado ni pierde un exceso fraccional sobre el doble del intervalo. Se
normalizan fechas con zona a UTC. Los timestamps repetidos no producen gaps.
Un snapshot de frecuencia en la lectura que abre el intervalo se utiliza para
ese segmento; en su ausencia se conserva el contexto de frecuencia configurado.
Frecuencias inválidas o simultáneas contradictorias producen error explícito.

Se conservan por separado la ventana temporal original y las últimas N muestras
estadísticas válidas después de excluir inactividad. Así no se declara serie
insuficiente cuando existen antecedentes activos suficientes.

### Inactividad y solapamientos

Se consultan exclusivamente periodos `SIN_SEÑAL` o `INACTIVO` registrados por
RF-60 para el dispositivo y sensor. El arreglo vacío de sensores representa el
periodo del dispositivo completo, como en el productor RF-60 existente.
`BUFFER_ACTIVO` no se reclasifica como inactividad.

Los periodos superpuestos/consecutivos se unen; un periodo abierto se limita
a la captura evaluada. Un historial sin fecha de inicio o con intervalos
invertidos no se convierte en una evaluación normal.

Un gap completamente cubierto queda excluido, conservando su evidencia en
`parametros_aplicados.consistencia_temporal`. Un gap anómalo parcialmente
cubierto produce `SOLAPAMIENTO_INACTIVIDAD_PENDIENTE` (503 recuperable), hasta
que Análisis defina si se descuenta el segmento o se excluye el gap completo.
No se adoptó una interpretación unilateral.

### E5

Si la ventana original con antecedentes queda completamente cubierta por
inactividad, se registra el evento RF-63 y se cancela la evaluación:

```text
EVALUACION_OMITIDA_POR_INACTIVIDAD
flags = {}
índice = no calculado
nueva fila telemetria_calidad = no
alerta = no
```

La omisión conserva contexto temporal y hash de integridad, y no se duplica al
reintentar la misma lectura. Una lectura sin antecedentes conserva el tratamiento
de serie insuficiente, sin deducir una serie inactiva inexistente.

El worker reconoce una omisión persistida y completa su etapa RF62 sin exigir
una evaluación ficticia. La evaluación manual conserva 201 cuando crea una
evaluación y responde 200 al omitirla, con `id_telemetria` y `resultado` explícito.
La nueva respuesta 200 queda documentada en OpenAPI.

## 3. Implementación disponible de #3793

Se eliminó el catálogo físico fijo y se preparó el transporte/persistencia de
`version_limites_fisicos_aplicada` desde un snapshot oficial del puerto.
Cuando el proveedor entrega versión verificable, valores y versión se usan
juntos y se conservan en la evaluación. Una sustitución crea otra fila,
enlaza la anterior y la marca SUPERADA; no sobrescribe sus valores históricos.

**El proveedor histórico M09 todavía no está disponible en la base de esta rama.**
El adaptador real consulta la estructura existente y registra:

```json
{
  "limites_fisicos": {
    "estado": "PENDIENTE_VERSIONADO_M09",
    "aplicados": false,
    "fuente": "modulo9.variables_ambientales"
  }
}
```

La versión permanece `null`. Los valores actuales no se aplican como límites
históricos ni se convierten en una versión artificial. Se conserva el análisis
estadístico disponible, pero falta el refuerzo físico histórico de fase 3.
La evidencia RF-63 de estas evaluaciones declara resultado `PARCIAL`.

Las pruebas V1/V2 utilizan un proveedor versionado **de prueba** y persistencia
PostgreSQL real. Verifican el contrato y la conservación histórica, no una
integración M09 versionada ya desplegada.

### Dependencia concreta M09/BD

Se necesita una fuente aprobada que resuelva, en una lectura consistente:

- Variable y especie aplicables por RF-61.
- Mínimo y máximo físicos.
- Identificador verificable de versión y vigencia desde/hasta.
- Selección por `timestamp_captura` y conservación de versiones anteriores.

No hace falta agregar el campo de salida en M03: ya existe. Antes de solicitar
una migración debe verificarse si la base oficial ya proporciona esa fuente.
No se creó una tabla paralela ni una migración especulativa.

## 4. Implementación disponible de #3794

### Congelamiento

Se conecta `GenerarAlertaCalidadUseCase` al flujo productivo RF-62, tanto en el
worker como en la evaluación manual. Usa el repositorio RF-57 existente:

- `tipo_alerta = TECNICA`.
- `tipo_variable = SENSOR_FISICO_FALLIDO`, subtipo ya existente.
- `origen_evento = BACKEND`.
- Severidad obtenida del flag de congelamiento, sin un segundo clasificador.
- Sensor, dispositivo, infraestructura y telemetría reales.
- Metadatos de anomalía, evaluación, parámetros y versión aplicada disponible.

La alerta se relaciona con la finca mediante la infraestructura. Se conserva
la auditoría RF-63 y el trigger registra el historial inicial.

### Deduplicación, concurrencia y errores

La condición técnica se bloquea por sensor/anomalía con un advisory lock
transaccional. Se reutiliza una alerta ACTIVA/EN_ATENCION equivalente y no se
incrementa frecuencia por una reevaluación. La misma lectura tampoco reabre
una alerta resuelta. Una severidad de congelamiento mayor escala la alerta
abierta sin crear otra ni incrementar artificialmente su frecuencia.

El bloqueo de evaluación serializa la cadena de la misma telemetría. Evaluación,
alerta y evidencia se confirman juntas. Un fallo revierte todos esos efectos;
la lectura RF-53 permanece intacta. DEV-05 conserva su recuperación/reintento.

### Drift significativo

Se respeta el umbral significativo existente en `ParametrosCalidad`; no se
genera alerta técnica por una magnitud igual o inferior a dicho umbral.
La nueva especificación no proporciona la severidad RF-57 para el caso superior.
Sin esa decisión, el flujo devuelve `SEVERIDAD_DRIFT_NO_CONFIGURADA`, revierte
los efectos de la evaluación y permite recuperación por DEV-05. No se registra
una falsa alerta ni se afirma una notificación completada.

La condición de drift y su algoritmo previo no se sustituyeron por otra fórmula.
El cierre de esta parte requiere la regla aprobada de severidad y su integración;
no basta con elegir arbitrariamente LEVE/MODERADO/CRITICO.

### Seguridad

Se conservan JWT, RBAC recurso 36 y separación técnica/operativa de DEV-13.
La consulta y actualización técnicas ahora aplican `AlcanceFincaAdapter`, igual
que las consultas operativas. Una alerta de otra finca no puede modificarse
mediante su identificador conocido. No se comparan IDs o nombres de roles para
autorizar y no se cambian permisos para conseguir pruebas satisfactorias.

## 5. Archivos modificados

| Archivo | Cambio / justificación | Tarea |
|---|---|---|
| `src/telemetry/domain/repositories/contexto_calidad_port.py` | Contexto temporal y snapshot físico independientes de infraestructura | #3792/#3793 |
| `src/telemetry/domain/entities/consistencia_temporal_calidad.py` | Comparación estricta y exclusiones RF-60; ambigüedad explícita | #3792 |
| `src/telemetry/infrastructure/adapters/contexto_calidad_m09_rf60_adapter.py` | Consulta real de captura, frecuencia, periodos y catálogo M09 | #3792/#3793 |
| `src/telemetry/application/use_cases/calidad/evaluar_calidad_telemetria_use_case.py` | Fase 5, E5, versión, auditoría y transacción con alerta | Todas |
| `src/telemetry/application/use_cases/calidad/generar_alerta_calidad_use_case.py` | Generación/deduplicación técnica con severidad verificable | #3794 |
| `src/telemetry/domain/repositories/alerta_repository.py` | Contrato técnico por sensor/anomalía | #3794 |
| `src/telemetry/infrastructure/repositories/alerta_repository.py` | Bloqueo, búsqueda idempotente, ámbito y escalamiento | #3794 |
| `src/telemetry/infrastructure/repositories/lectura_postcommit_repository.py` | Verificación de omisión RF-63 persistida | #3792 |
| `src/telemetry/application/use_cases/ingesta/procesar_lectura_confirmada_use_case.py` | Acepta omisión E5 sin fabricar una evaluación | #3792 |
| `src/telemetry/infrastructure/workers/postcommit_worker.py` | Inyección de contexto y alertas reales | Todas |
| `src/telemetry/infrastructure/routers/calidad_router.py` | Conecta flujo manual y documenta respuesta E5 | Todas |
| `src/telemetry/infrastructure/routers/infraestructura_iot_router.py` | Ámbito por finca de consultas y actualizaciones técnicas | #3794 |
| `tests/telemetry/test_dev43_calidad_temporal.py` | Casos temporales, snapshots, omisión y notificaciones con dobles | Todas |
| `tests/integration/test_dev43_calidad_temporal.py` | Persistencia, omisiones, alertas, concurrencia y JWT/RBAC reales | Todas |
| `anotaciones/modulo_3/dev43_rf62_gap_inactividad_limites_alertas.md` | Diagnóstico, decisiones, evidencia y pendientes | Todas |

## 6. Verificación

Se utilizó PostgreSQL 18 efímero en `127.0.0.1:55443`, base
`sgpmp_dev43_test`, con las migraciones existentes hasta `e5a3c9b17d42`.
Se prepararon los roles técnicos que las migraciones presuponen en el clúster
aislado; no se relajaron triggers, permisos de aplicación ni políticas RLS.

Las pruebas HTTP utilizan JWT y permisos reales sembrados. La conexión de
fixtures PostgreSQL es administrativa: esto no equivale a una validación completa
del despliegue usando el login `sgpmp_app` bajo todas sus políticas RLS.

### Comando final

`DATABASE_URL` y `TEST_DATABASE_URL` apuntan exclusivamente a la base aislada.

```powershell
.venv/Scripts/python.exe -c "import sys,types; sys.modules['fcntl']=types.SimpleNamespace(LOCK_EX=2,LOCK_NB=4,LOCK_UN=8,flock=lambda *a:None); import pytest; sys.exit(pytest.main(['tests/telemetry','tests/configuration','tests/integration/test_dev43_calidad_temporal.py','tests/integration/test_rf62_dev02_aptitud_telemetria.py','tests/integration/test_dev05_ingesta_bplus_postcommit.py','tests/integration/test_dev12_heartbeat_extendido.py','tests/integration/test_dev14_parametros_dinamicos.py','--import-mode=importlib','-q','--tb=short','--basetemp=.pytest_cache/dev43_cierre_tmp','--junitxml=.pytest_cache/dev43_cierre.xml']))"
```

El puente `fcntl` permite importar el conftest compartido en Windows. No valida
los bloqueos de archivos de M02 ni modifica ese módulo. Una primera ejecución
sin acceso de red del sandbox quedó detenida y fue cancelada; no se contabiliza
como regresión aprobada ni como defecto del código. Una ejecución intermedia
detectó dos fallos por contaminación entre pruebas: las 21 lecturas confirmadas
de la prueba concurrente alimentaban el lote del worker de casos posteriores.
Se corrigió el fixture para usar otra base efímera, se recreó la base principal
y se repitió la suite sin modificar assertions ni límites del worker.

Evidencia local ignorada por Git: `.pytest_cache/dev43_cierre.xml`,
`.pytest_cache/dev43_archivos.json`, `.pytest_cache/dev43_bandit.txt` y
`.pytest_cache/dev43_migrations.log`.

### Resultados finales, sin duplicar ejecuciones

| Suite | Aprobadas | Fallidas | Omitidas |
|---|---:|---:|---:|
| Telemetría | 264 | 0 | 0 |
| Configuración | 616 | 0 | 0 |
| Integraciones PostgreSQL seleccionadas | 101 | 0 | 0 |
| **Total** | **981** | **0** | **0** |

Incluye **30 unitarias y 21 integraciones propias de DEV-43**, ya contabilizadas.
Duración de la ejecución final: 153.79 s. No se suman las ejecuciones previas.

Escenarios verificados: gaps menor/igual/mayor, frecuencia persistida, UTC y
repetidos, exclusión RF-60, ventana mixta y N activas recuperadas, omisión E5 sin
nueva evaluación, reintento sin duplicar auditoría, respuesta HTTP 200 de E5,
versiones V1/V2 con proveedor de prueba y conservación histórica, congelamiento,
alerta técnica única, rollback tras insertar alerta, concurrencia real, permisos
JWT/RBAC efectivos, Productor excluido y ámbito por finca. La severidad de drift
faltante se verifica como error recuperable, no como alerta implementada.

AST y seguimiento: 14 archivos Python correctos. `git diff --check`: correcto.
Bandit sobre los 12 archivos de producción: 0 hallazgos medios/altos; la métrica
registra un hallazgo bajo correspondiente al `except: pass` heredado de auditoría
best-effort, fuera de la nueva ruta obligatoria. Se conserva una advertencia
preexistente de deprecación httpx/TestClient. No se ejecutó la suite de todo el
backend ni pruebas desplegadas en DEV/TEST.

La concurrencia usa conexiones y commits reales en una segunda base temporal
`dev43_concurrency_test_<uuid>`, migrada con los scripts existentes y eliminada
al finalizar su fixture. No deja lecturas inmutables pendientes en otras suites.

## 7. Dependencias, pendientes y estado de cierre

| Elemento | Estado |
|---|---|
| #3792 | Implementados gaps definidos, exclusión completa y E5; pendiente decisión de solapamiento parcial |
| #3793 | Transporte y persistencia listos; falta proveedor histórico M09 verificable en la rama/entorno |
| #3794 | Congelamiento técnico, atomicidad y seguridad implementados; drift significativo pendiente de severidad aprobada |
| RF-60 | Se consumen periodos oficiales existentes; no se reconstruyen estados ni se implementa otro detector |
| DEV-27 | No integrado en el `origin/dev` usado; su parametrización permanece en rama independiente |
| DEV-40/DEV-49 | No integrados en esa base; no se duplican sus soluciones |
| DEV-41 | PR independiente; requiere regresión conjunta al integrar, especialmente para E5 sin evaluación |
| Re-evaluación masiva | El endpoint heredado solo marca SUPERADA y devuelve cero creadas; su orquestación completa no se implementa en DEV-43. La cadena puntual sí se verifica |
| #3699 | Parcial: no cerrar mientras falten las decisiones y la fuente histórica |

Para Análisis: definir solapamiento parcial y severidad RF-57 del drift
significativo. Para M09/BD: confirmar o proporcionar el contrato histórico de
límites por variable/especie/fecha; inspeccionar primero la BD oficial cuando
su conexión esté disponible.

No se creó migración. Los pendientes funcionales de integración se detallan arriba.
Los archivos de código conservan tabla de seguimiento del 2026-10-21 con
`Leandro`, obtenido de `git config user.name`. Los documentos y AGENTS.md
preexistentes sin seguimiento Git permanecen fuera del alcance.

## 8. Propuesta de Pull Request

**Título:** `RF-62 — Gaps temporales, omisión por inactividad y alertas técnicas de calidad (DEV-43)`

**Desvío:** la fase 5 no detectaba gaps y RF-62 no consumía los periodos RF-60;
la fase 8 solo auditaba, y los límites físicos provenían de una constante.

**Cambios:** contexto temporal persistente, comparación estricta, evento E5 sin
calificación ficticia, contrato de snapshot físico versionado, generación técnica
por congelamiento, deduplicación/concurrencia, auditoría atómica y alcance por finca.

**Contrato:** gap igual al doble no penaliza; gap superior activo sí penaliza;
inactividad completa omite; congelamiento genera TECNICA visible con recurso 36
y ámbito válido, nunca mediante el endpoint operativo de Productor.

**Pendientes:** proveedor histórico M09, regla de solapamiento parcial y severidad
de drift significativo. PostgreSQL y permisos reales se distinguen de los dobles
V1/V2. La historia no se declara cerrada.

Referencias: #3699, #3792, #3793 y #3794. Destino previsto: `dev`.
