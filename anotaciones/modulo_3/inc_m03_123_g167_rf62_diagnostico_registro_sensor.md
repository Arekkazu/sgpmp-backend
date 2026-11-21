# RF-62 / RF-53 — Snapshot de calibración y revisión del alta · INC-M03-123-G167

Fecha: 2026-10-26. Referencias: [issue #626](https://github.com/Arekkazu/sgpmp-backend/issues/626), TC-M03-G167, RF-22, RF-24, RF-53 y RF-62.

## Resultado final

El alta con el payload reportado no reproduce el 500 en dev actualizado: responde 201, asigna identificador y persiste es_activo=True. También funciona sin categoría. La causa propuesta en #626 no describe el flujo actual: Sensor.crear() ya asigna True y el repositorio lo transfiere explícitamente al ORM.

La revisión encontró un fallo distinto en la continuidad del flujo: la ingesta aplicaba la calibración, pero omitía su snapshot en telemetrias.parametros_calibracion. El usuario autorizó incluir esta corrección en la misma rama. Se incorpora una migración que guarda ganancia y offset realmente utilizados, en el mismo INSERT de la lectura.

**Validación final: 32 pruebas distintas aprobadas, 0 fallidas y 0 omitidas.** Son 29 casos con PostgreSQL real y 3 pruebas de comprobación de migraciones. El alta no requirió un cambio de producción; la corrección funcional afecta a la persistencia del snapshot de ingesta.

## Base de trabajo

- dev y origin/dev se actualizaron antes de crear la rama.
- Base: 18b4ce67e8d23ed57fdfd108d44e0c2601e66604.
- Rama: fix/inc-m03-123-g167-alta-sensor-rf62.
- El primer commit, 85ed5ce3, contiene la investigación inicial y las pruebas que mostraban dos fallos pendientes de snapshot. Este informe se actualiza con la corrección y su validación final; aquel resultado de 10 aprobadas y 2 fallidas es histórico.
- La corrección de #625 se entregó en otra rama; no es un commit propio ni una dependencia nueva de esta entrega.

## Causa raíz y cambio mínimo

1. RF-24 persiste ganancia y offset_calibracion.
2. modulo3.fn_obtener_calibracion devuelve esos valores reales (DB-02, revisión e5a3c9b17d42).
3. fn_ingesta_telemetria calcula valor_ajustado con v_ganancia y v_offset y marca v_calibrado=True.
4. Su INSERT omitía parametros_calibracion; PostgreSQL guardaba NULL.
5. El endpoint de calidad y el procesamiento posterior transportan esa columna a RF-62, cuya fase de drift necesita los parámetros.

La migración añade la columna al INSERT y el valor:

~~~sql
CASE WHEN v_calibrado
     THEN jsonb_build_object('ganancia', v_ganancia, 'offset', v_offset)
     ELSE NULL
END
~~~

No se consulta de nuevo la calibración durante la escritura del snapshot: se reutilizan las mismas variables que intervinieron en el cálculo. Las lecturas sin calibración conservan snapshot NULL, valor ajustado NULL y ERROR_CALIBRACION. No se reconstruyen snapshots históricos desde la calibración actual.

La evaluación y la consulta de detalle utilizan el snapshot almacenado en la lectura aunque el sensor haya sido recalibrado posteriormente. Las nuevas lecturas sí capturan la nueva calibración. No se cambian fórmulas de drift, descuentos del índice, routers, DTO, permisos ni contratos HTTP.

## Flujo del alta comprobado

| Capa | Comportamiento existente |
|---|---|
| Router | POST /configuracion/dispositivos-iot/{id}/sensores; 201 y RBAC sobre dispositivos_iot, acción Crear |
| DTO | Valida nombre y categoría; no exige es_activo |
| Caso de uso | Comprueba dispositivo y tipo, crea la entidad y controla commit/rollback |
| Dominio | Sensor.crear() produce un sensor activo |
| Repositorio | Mapea es_activo=sensor.es_activo y utiliza flush/refresh |
| ORM/BD | El boolean obligatorio recibe el valor explícito, sin necesitar default |

No se modifican esas capas para solucionar un fallo que no se reproduce en dev actual.

## Migración y BD

Archivo: alembic/versions/8d13c7e9a624_conservar_snapshot_calibracion_ingesta.py.

- Revisión: 8d13c7e9a624; padre: 30168ab97bd4; una sola head en el código.
- Comprueba que la columna existente sea JSONB y modifica la definición vigente obtenida con pg_get_functiondef.
- Solo añade una columna y un valor al INSERT final; si la forma esperada no coincide o ya hay otra implementación del snapshot, falla de forma explícita para revisión.
- CREATE OR REPLACE conserva firma, propietario y privilegios. No crea tablas, columnas alternativas, roles ni permisos.
- Downgrade retira únicamente esas dos líneas, conservando el resto de la función y los datos ya almacenados.
- No se editan migraciones históricas ni se hace backfill de telemetrías inmutables.

Se aplicó mediante Alembic únicamente en la base local exclusiva sgpmp_g167_test, construida previamente desde cero hasta la head de dev. Se verificó la nueva revisión y la igualdad exacta del resto de la función. Las pruebas ejecutan downgrade/upgrade real de la función y comprueban definición, propietario, ACL, SECURITY DEFINER, configuración, volatilidad y paralelismo.

## Inspección de sgpmp_dev

La base oficial se inspeccionó en una transacción de solo lectura. No se ejecutaron DDL/DML ni solicitudes POST contra ella.

En sensores se comprobaron secuencia, PK, FK, columnas, índices, triggers y políticas. es_activo es boolean NOT NULL sin default, compatible con el valor explícito de la entidad. RLS y FORCE ROW LEVEL SECURITY están activos en sensores; las políticas observadas derivan el alcance del dispositivo, como la migración existente f62b120bb13f_fix_rls_sensores.py. No se duplica esa corrección.

La lectura de alembic_version y de permisos oficiales fue rechazada por privilegios; no se certifica la revisión desplegada ni la equivalencia con QA. También se observó nombre varchar(60) en sensores frente al máximo 100 del ORM/DTO; el payload reportado no alcanza ese límite y no se amplió esta corrección a ese contrato.

La inspección local del nuevo cambio confirmó que parametros_calibracion ya existe como JSONB nullable. Las políticas y triggers existentes se mantienen; no se añade RLS a tablas que actualmente no lo tienen ni se atribuye esa garantía a telemetrias.

## Pruebas realizadas

Entorno: PostgreSQL 18.4 local, 127.0.0.1:55427, base sgpmp_g167_test. Se mantienen las protecciones de TEST_DATABASE_URL, la transacción exterior y los savepoints del fixture. La API del grupo principal utiliza JWT y TEST_ROL_APP=sgpmp_app, sin superusuario ni BYPASSRLS. La preparación y las aserciones administrativas emplean la conexión del fixture.

| Grupo | Aprobadas | Fallidas | Omitidas |
|---|---:|---:|---:|
| Nuevas: alta con/sin categoría, rollback flush/commit, Ingeniero por finca, JWT/RBAC y validaciones | 8 | 0 | 0 |
| Flujo HTTP: sin drift, drift con offset, ganancia/offset decimales y sin calibración | 4 | 0 | 0 |
| Reversibilidad y preservación de la función/privilegios | 1 | 0 | 0 |
| Existentes: repositorio de sensores bajo RLS, Administrador y Productor asignado | 2 | 0 | 0 |
| Regresión: ingesta HTTP/SQL, calibración DB-02, rechazos, batch, inmutabilidad, postcommit RF-62 y multiespecie | 14 | 0 | 0 |
| Comprobación de migraciones (sin PostgreSQL real) | 3 | 0 | 0 |
| **Total distinto** | **32** | **0** | **0** |

Las pruebas de repositorio no conceden permiso HTTP de alta al Productor: la solicitud sin permiso sigue devolviendo 403. El Ingeniero ajeno a la finca recibe 404 y, asignado a ella, puede registrar el sensor.

Las pruebas de rollback observan un INSERT real antes de inducir el fallo de flush o commit. Verifican ausencia de filas parciales y reintento exitoso; no sustituyen la persistencia por fakes.

Los padres (finca, área y dispositivo) se preparan mediante SQL. Desde el alta del sensor, asociación, calibración, 21 ingestas y evaluación se usan endpoints HTTP reales. Se controla únicamente el reloj del dominio de asociación para situar esa asociación antes de las capturas históricas: now() de PostgreSQL queda fijo por la transacción exterior. No se desactivan restricciones temporales ni se reescriben auditorías.

En cada escenario se registra otra calibración antes de evaluar la última lectura. Se comprueba que evaluación y detalle devuelven el snapshot original, que ninguna operación cambia la telemetría previa y que una ingesta batch posterior guarda los nuevos parámetros. Sin calibración original, RF-62 mantiene el snapshot NULL y clasifica INDETERMINADA por serie válida insuficiente, incluso si luego existe una calibración.

Los escenarios con drift verifican la bandera y el índice 90: su magnitud es menor al 10 %, para la cual el dominio existente descuenta 10 puntos. La expectativa inicial de 70 se corrigió en la prueba, sin alterar la fórmula de producción.

Las regresiones existentes de la función compartida usan sus fixtures administrativos; no se presentan como pruebas adicionales de RBAC bajo el rol de API. El canal MQTT se representa mediante la función SQL común, sin broker real.

## Evidencias y repeticiones

- .pytest_cache/g167_snapshot_principal.xml: 14 aprobadas y una expectativa inicial fallida del nuevo caso sin calibración.
- .pytest_cache/g167_snapshot_regresion.xml: 18 aprobadas, incluida la repetición corregida de ese caso.
- .pytest_cache/g167_snapshot_resultados_consolidados.json: 32 IDs distintos, tomando el último resultado de cada ID; 29 con PostgreSQL y 3 de comprobación de migraciones.
- .pytest_cache/g167_snapshot_funcion_antes.sql y g167_snapshot_funcion_despues.sql: comparación del cambio aplicado.

Las corridas previas reprodujeron los dos snapshots nulos y detectaron datos de prueba con offsets fuera del rango permitido; se corrigieron los datos del fixture, conservando la validación. La preparación de privilegios mínimos de infraestructura de la base desechable corresponde a la investigación inicial; no se modifica la base oficial. El shim fcntl de Windows permanece limitado al lanzador de pruebas.

Los logs, XML, consolidado y scripts temporales están ignorados en .pytest_cache y no forman parte del commit. Los resultados se cuentan una vez por ID; no se suman corridas históricas ni repeticiones.

## Alcance y pendientes

La entrega acumulada contiene tres archivos: migración, pruebas de integración e informe. Se preservan AGENTS.md, pendientes_integracion_aiot_por_tarea_y_pr.md y pendientes_por_area/ como archivos locales ajenos.

La migración no se ha aplicado a sgpmp_dev ni a TEST desplegado. Su despliegue requiere el procedimiento autorizado habitual de Alembic. Las lecturas históricas con snapshot NULL siguen sin parámetros verificables; no se rellenan con información actual.

Los adjuntos originales documentan 44 comprobaciones (8 aprobadas, 36 fallidas en cascada), pero no prueban el error SQL del servidor que causó el 500 del alta. No se ejecutó la colección original completa de siete escenarios ni se certificó el despliegue de QA. El snapshot queda corregido y validado localmente; la atribución del 500 original requiere comprobar la versión y los logs de ese entorno.
