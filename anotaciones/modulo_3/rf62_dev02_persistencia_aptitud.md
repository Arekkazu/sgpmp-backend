# RF-62 DEV-02 — Aptitud escalar en la evaluación vigente

Fecha: 2026-10-15. Épica Desarrollo M03 — integración AIoT #3503.
Tareas: #3560, #3561 y #3562. Rama `fix/rf62-dev02-aptitud-telemetria`,
creada desde `origin/dev` (`cd06a257`).

## Diagnóstico

### Hechos confirmados

- `EvaluarCalidadTelemetriaUseCase` guardaba una evaluación y después llamaba
  a `actualizar_flags_aptitud` antes del commit.
- El puerto `TelemetriaRepository` declaraba esa operación y su implementación
  SQLAlchemy ejecutaba `UPDATE modulo3.telemetrias` sobre las dos aptitudes.
- La inspección de solo lectura en DEV confirmó el trigger
  `trg_rf53_02_no_update` activo. Su función rechaza UPDATE con SQLSTATE P0002,
  como también consta en el baseline. El rollback del caso de uso descartaba
  la evaluación pendiente junto con el UPDATE fallido.
- Las ramas FUERA_DE_RANGO y serie insuficiente guardaban mediante flush,
  pero no confirmaban explícitamente. Su persistencia dependía accidentalmente
  del commit posterior de auditoría, si esta estaba configurada y funcionaba.
- El mapeo de `SqlAlchemyTelemetriaRepository` consumía las aptitudes legadas
  del ORM. No se encontraron otros lectores escalares de esas columnas en src.
- El esquema existente de `telemetria_calidad` ya contiene las dos aptitudes,
  `estado_evaluacion`, `id_evaluacion_superada`, timestamps e índices por lectura
  y sensor. No impone unicidad de VIGENTE por lectura: la consulta anterior
  podía devolver varios registros al listar o desempatar de forma inestable.

### Referencias y discrepancias

No se localizaron en el repositorio los archivos
`AIOT-DEV-03_Acuerdo_Consolidado_Desarrollo_AIoT.md` ni
`gaps_rf_m03_telemetria.md`, incluso buscando archivos ignorados fuera de .venv
y .git. Se siguieron la instrucción DEV-02 del usuario, los modelos, el esquema
real y los contratos existentes de RF-62.

La ficha funcional compartida anteriormente permitía actualizar flags de
consulta rápida en RF-53. La instrucción DEV-02 sustituye expresamente esa
regla: **la única fuente oficial de aptitud escalar es telemetria_calidad**.
No se debilita el trigger para acomodar la excepción anterior.

### Flujo corregido

```text
RF-53: lectura inmutable
    → cálculo RF-62, con las reglas existentes
    → INSERT de evaluación en telemetria_calidad
    → referencia a la evaluación anterior y marca SUPERADA, si existe
    → COMMIT conjunto de la evaluación y su sustitución
    → auditoría existente

Error de persistencia, sustitución o commit
    → ROLLBACK conjunto
    → se conserva la evaluación previamente confirmada
```

## Cambios por archivo

| Archivo | Responsabilidad y cambio |
| --- | --- |
| `src/telemetry/application/use_cases/calidad/evaluar_calidad_telemetria_use_case.py` | Elimina la llamada obsoleta y centraliza commit/rollback en `_persistir` para todas las ramas. Enlaza y supera la evaluación anterior en la misma transacción. Conserva el cálculo y la auditoría posterior. |
| `src/telemetry/domain/repositories/telemetria_repository.py` | Retira la operación de UPDATE y documenta que la aptitud de una lectura se proyecta desde su evaluación vigente. |
| `src/telemetry/infrastructure/repositories/telemetria_repository.py` | Elimina el UPDATE y el consumo de flags legados. `obtener_por_id` obtiene la calidad vigente; el mapeo recibe esa evaluación. Una lectura recién insertada, aún sin evaluación, conserva aptitud falsa sin consulta adicional. |
| `src/telemetry/infrastructure/repositories/telemetria_calidad_repository.py` | Centraliza la selección de una evaluación vigente por lectura. Aplica esa selección antes de filtros de clasificación o fechas, evita duplicados y conserva acceso explícito al histórico SUPERADA. |
| `src/telemetry/domain/repositories/telemetria_calidad_repository.py` | Documenta la fuente oficial y la semántica de vigencia e histórico. Mantiene las firmas. |
| `src/telemetry/infrastructure/models/telemetria_model.py` | Conserva las columnas físicas legadas, pero las difiere con raiseload: las consultas ORM ordinarias no las seleccionan y un acceso accidental no dispara su lectura. No modifica el esquema. |
| `src/telemetry/domain/entities/telemetria.py` | Documenta las aptitudes como una proyección de calidad vigente, manteniendo los campos existentes. |
| `tests/telemetry/test_rf62_dev02_persistencia_aptitud.py` | Prueba las ramas APTO, APTO_CON_RESERVA, NO_APTO e INDETERMINADA, la confirmación independiente de auditoría y el rollback. |
| `tests/integration/test_rf62_dev02_aptitud_telemetria.py` | Prueba PostgreSQL real, 20 lecturas previas más la lectura objetivo, trigger activo, consumidores, sustitución, empates y fallos transaccionales. |
| `anotaciones/modulo_3/api_reference_m03_telemetria_iot.md` | Documenta la aptitud oficial y el listado ordinario de vigentes. |
| `anotaciones/modulo_3/curls_m03_cu06_calidad_auditoria.md` | Actualiza el contrato de consulta y el acceso al histórico SUPERADA. |
| `anotaciones/modulo_3/cu06_gaps_bd_rf62_rf63.md` | Señala la obsolescencia del DDL histórico de flags en telemetrias, sin reescribir ni aplicar ese DDL. |
| Este documento | Registra diagnóstico, decisiones, cobertura y límites de la entrega. |

## Fuente oficial y vigencia

Una evaluación candidata debe cumplir:

1. `estado_evaluacion = 'VIGENTE'`.
2. No estar referenciada como `id_evaluacion_superada` por otra evaluación de
   la misma lectura.
3. Si hay varios candidatos legados sin enlace, se selecciona uno por lectura
   en orden descendente de `timestamp_evaluacion`, `fecha_creacion` e
   `id_evaluacion`. El UUID es únicamente el desempate estable final.

La selección ocurre **antes** de filtrar la clasificación. Por ejemplo, una
evaluación antigua APTO no reaparece al filtrar APTO si la vigente es NO_APTO.
El ranking no modifica ni elimina registros históricos.

`GET /iot/calidad` devuelve vigentes por defecto y conserva su estructura JSON,
parámetros y paginación. Esta modificación del contenido por defecto es
intencional: evita tratar evaluaciones superadas como aptitud actual.
`estado_evaluacion=SUPERADA` permite consultar el histórico marcado como tal.

`Telemetria.apto_para_ia` y `apto_para_nic41` se conservan como campos de dominio
para compatibilidad, pero se obtienen exclusivamente de la calidad vigente.
Sin evaluación vigente, ambos son False. Nunca se recurre a las columnas legadas
de telemetrias como fallback.

## Consumidores y RF-71

Inventario revisado: repositorios de telemetría, calidad, historial y monitoreo;
rutas de calidad; src/prediction; scripts SQL y migraciones; vistas y rutinas
visibles en DEV.

- Se corrigió el lector escalar identificado en el repositorio de telemetría.
- Las consultas de calidad vigentes usan el mismo criterio centralizado.
- Historial y monitoreo seleccionan columnas explícitas sin leer los flags
  obsoletos, por lo que no requieren modificación.
- No se encontraron vistas consumidoras de esas aptitudes en la inspección DEV.
- La rutina legada `modulo3.sp_evaluar_calidad_dato` contiene salidas de aptitud
  y escrituras de metadatos, pero no lee las columnas obsoletas ni tiene un
  invocador en src. No se cambia el baseline ni esa rutina en DEV-02.
- La aptitud de observaciones de visión pertenece a su propio contrato; no se
  modifica como parte de la corrección escalar.
- RF-71 no tiene un consumidor de dataset implementado en este checkout.
  DEV-02 confirma que existe aptitud persistida y consultable para que lo use,
  pero no demuestra una ejecución real de reentrenamiento.

Para un consumidor SQL externo, el filtrado de `apto_para_ia` debe aplicarse
después de resolver la vigencia, como hace el repositorio:

```sql
WITH vigentes AS (
    SELECT c.*,
           row_number() OVER (
               PARTITION BY c.id_telemetria
               ORDER BY c.timestamp_evaluacion DESC,
                        c.fecha_creacion DESC, c.id_evaluacion DESC
           ) AS posicion
    FROM modulo3.telemetria_calidad c
    WHERE c.estado_evaluacion = 'VIGENTE'
      AND NOT EXISTS (
          SELECT 1
          FROM modulo3.telemetria_calidad posterior
          WHERE posterior.id_evaluacion_superada = c.id_evaluacion
            AND posterior.id_telemetria = c.id_telemetria
      )
)
SELECT t.id_telemetria, t.id_sensor, t.id_variable,
       t.valor_crudo, t.valor_ajustado, t.timestamp_captura,
       q.id_evaluacion, q.apto_para_ia, q.apto_para_nic41
FROM modulo3.telemetrias t
JOIN vigentes q ON q.id_telemetria = t.id_telemetria AND q.posicion = 1
WHERE q.apto_para_ia = true;
```

Esta consulta es una referencia para integración; no crea una vista ni cambia
autorizaciones o filtros territoriales que deba aplicar el consumidor.

## Pruebas ejecutadas

### Entorno

DEV se inspeccionó exclusivamente en una transacción de solo lectura y rollback
final. No se ejecutó DDL ni DML allí, ni en TEST compartido.

La integración se ejecutó en PostgreSQL 18.6 temporal de Windows, disponible
solo en localhost, con base `sgpmp_test_rf62_dev02`. Se aplicaron las migraciones
existentes hasta `3a9d5e7c1b24`; no se agregó una migración de producto. Se
prepararon los roles que requiere el baseline únicamente en ese cluster local.

Los binarios portables se obtuvieron del sitio oficial de EDB. No se instaló
un servicio del sistema. La configuración TEST_DATABASE_URL se limitó a los
procesos de prueba y se restauró al terminar cada comando.

Se reutilizan `integration_engine` y `db_session` del conftest del proyecto.
Cada prueba vive en una transacción exterior; los commits liberan savepoints.
La comprobación posterior encontró **0 sensores de fixture y 0 evaluaciones**
persistidos. Las secuencias pueden avanzar; no se afirma restauración de ellas.

Tras la regresión adicional también se verificaron 0 lecturas y 0 evaluaciones
persistidas, con el trigger RF-53 todavía activo (`tgenabled = O`). Se detuvo
el servidor y se eliminó el directorio temporal de esta tarea.

### Resultados confirmados

| Prueba | Objetivo | Resultado |
| --- | --- | --- |
| Unitarias RF-62 DEV-02 | Ramas, aptitud calculada, confirmación y rollback | 11 aprobadas |
| Integración RF-62 DEV-02 | Persistencia y consumidores en PostgreSQL | 12 aprobadas |
| Inmutabilidad RF-53 | Trigger activo, ausencia de UPDATE y snapshots de 21 lecturas sin cambios | Aprobada en integración |
| Serie de 20 lecturas previas | Persistencia APTO y APTO_CON_RESERVA; flags oficiales correctos | Aprobada en integración |
| Evaluación vigente | Enlaces de sustitución, estados, candidatos múltiples, empates y filtros sin resucitar aptitud | Aprobada en integración |
| Errores transaccionales | Fallos después de guardar, al superar y antes de commit; estado anterior conservado | Aprobada en integración |
| Regresión de telemetría compatible con Windows | Pruebas existentes más las nuevas unitarias | 41 aprobadas; incluye las 11 anteriores |
| Regresión PostgreSQL existente de ingesta/vinculación | Integración de lecturas con activos y resolución de vinculaciones | 6 aprobadas |
| Bandit, severidad ALTA y confianza ALTA | Control de bloqueo configurado en CI, sobre los 7 archivos de producción modificados | Aprobado, 0 hallazgos altos; el análisis contabiliza 1 hallazgo bajo |
| Sintaxis y diff | AST de los 9 archivos Python y git diff --check | Aprobados |

Total final: **59 pruebas distintas aprobadas** (41 + 12 + 6). No se suman otra
vez las 11 unitarias que ya están incluidas en las 41.

Comandos:

```powershell
.\.venv\Scripts\python.exe -m pytest --confcutdir=tests/telemetry tests/telemetry/test_rf62_dev02_persistencia_aptitud.py -q --tb=short --show-capture=no
.\.venv\Scripts\python.exe -m pytest --confcutdir=tests/telemetry tests/telemetry --ignore=tests/telemetry/test_inc_m09_77_g137_observaciones_vision.py -q --tb=short --show-capture=no
# TEST_DATABASE_URL debe apuntar a PostgreSQL exclusiva de pruebas, migrada.
.\.venv\Scripts\python.exe -m pytest --confcutdir=tests/integration tests/integration/test_rf62_dev02_aptitud_telemetria.py -q --tb=short --show-capture=no
.\.venv\Scripts\python.exe -m pytest --confcutdir=tests/integration tests/integration/test_inc_m09_64_g31_vinculacion_ingesta.py -q --tb=short --show-capture=no
```

### Incidencias de verificación y límites

La primera ejecución de integración falló en el fixture aislado porque faltaba
registrar los modelos M09 en el metadata del ORM. Se corrigió el fixture sin
cambiar producción por ese motivo; las 12 pruebas pasaron posteriormente.

La suite completa de tests/telemetry se intentó y se detuvo durante recolección:
el test de visión importa main, que importa `fcntl` de M02, incompatible con
Windows. No se simuló fcntl ni se modificó M02. La regresión ejecutable excluye
únicamente ese archivo y evita el conftest raíz mediante --confcutdir.
No se afirma que la suite completa haya pasado. La advertencia de
Starlette/httpx es preexistente.

Bandit se ejecutó en un entorno temporal de uv con el umbral de bloqueo
`-lll -iii` del workflow del proyecto. No se modificaron requirements ni se
instalaron herramientas en la .venv del backend. Semgrep no se ejecutó localmente.

## Estado de las tareas

- #3560: operación retirada del caso de uso, puerto e implementación; persiste
  calidad en su propia tabla sin modificar RF-53.
- #3561: lectura escalar oficial y selección única de evaluación vigente;
  columnas legadas bloqueadas, inventario de consumidores completado.
- #3562: nuevas pruebas unitarias y 12 escenarios de integración PostgreSQL
  ejecutados satisfactoriamente.

No requiere migración, cambio de RBAC, desactivación de triggers ni reparación
automática de datos históricos. El consumo final de RF-71 y la ejecución Linux
de la suite que importa main quedan para su entorno y alcance correspondientes.
