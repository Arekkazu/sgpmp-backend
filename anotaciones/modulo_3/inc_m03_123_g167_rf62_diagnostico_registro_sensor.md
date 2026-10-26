# RF-62 / RF-22 — Revisión del alta de sensores · INC-M03-123-G167

Fecha: 2026-10-26. Referencia: [issue #626](https://github.com/Arekkazu/sgpmp-backend/issues/626), TC-M03-G167 y precondición de sensores de RF-22.

## Resultado de la revisión

El alta de sensor con el payload reportado **no reproduce el 500 en dev actualizado**. Devuelve 201, conserva la categoría, asigna un identificador y persiste `es_activo=True`. También funciona sin categoría, que continúa siendo opcional.

La causa propuesta por la issue no describe el flujo completo: `Sensor.crear()` ya asigna `es_activo=True`, y `SqlAlchemySensorRepository.guardar()` lo transfiere explícitamente a `SensorModel`. No hace falta que el cliente envíe ese estado ni que el DTO lo exponga.

La revisión del flujo posterior sí detectó **un problema distinto de RF-53/RF-62**: la ingesta aplica la calibración, pero no conserva su snapshot en `telemetrias.parametros_calibracion`. La evaluación puntual recibe `None` y no dispone de los parámetros que requiere su fase de drift. Las pruebas mantienen ese fallo visible; no se rellenó el JSON desde la configuración actual para hacerlas pasar.

## Base de trabajo

- Se actualizaron `dev` y `origin/dev` antes de reconstruir esta rama.
- Base: `18b4ce67e8d23ed57fdfd108d44e0c2601e66604`.
- Rama: `fix/inc-m03-123-g167-alta-sensor-rf62`.
- La corrección anterior #625 se trasladó por separado a esa misma base y se publicó como `c1401d5a`. No es un commit propio ni una dependencia añadida a esta rama.

## Flujo comprobado

| Capa | Comportamiento existente |
|---|---|
| Router | POST `/configuracion/dispositivos-iot/{id}/sensores`, respuesta 201 y RBAC sobre `dispositivos_iot`, acción Crear |
| DTO | Valida nombre y categoría; no requiere `es_activo` |
| Caso de uso | Comprueba dispositivo y tipo, llama a `Sensor.crear()`, guarda y controla commit/rollback |
| Dominio | La fábrica crea un sensor activo |
| Puerto/repositorio | Recibe una entidad y mapea `es_activo=sensor.es_activo`; utiliza flush/refresh |
| ORM/BD | Boolean obligatorio; el valor explícito satisface NOT NULL sin necesitar un default |

Archivos de producción revisados: entidad `sensor.py`, DTO `registrar_sensor_dto.py`, caso de uso `dispositivos_iot/registrar_sensor_use_case.py`, puerto y repositorio `sensor_repository.py`, modelo `sensor_model.py`, schema y router de dispositivos. No se modificaron.

## BD y RBAC

La base oficial `sgpmp_dev` se consultó en una transacción con `transaction_read_only=on`. No se ejecutaron DDL/DML ni se reprodujo el POST contra ella.

Se verificaron la secuencia, PK, FK, columnas, índices, triggers y políticas de `modulo9.sensores`. `es_activo` es boolean NOT NULL sin default; esto es compatible con el valor explícito enviado por el repositorio. La columna real `nombre` es varchar(60), mientras el ORM/DTO admite hasta 100; el nombre de 17 caracteres del escenario no alcanza ese límite y no se cambió ese contrato en esta revisión.

RLS y FORCE ROW LEVEL SECURITY están activos. Las políticas SELECT/UPDATE observadas derivan el alcance del dispositivo, criterio compatible con la corrección existente `f62b120bb13f_fix_rls_sensores.py`. Esa migración ya está en dev y corrige un 500 anterior al insertar sensores por visibilidad circular de RLS. No se duplica ni se atribuye como una corrección nueva de #626.

La lectura de `alembic_version` y de permisos oficiales fue rechazada por privilegios. Por tanto, la observación del esquema efectivo no se presenta como certificación de una revisión desplegada ni como ausencia de registros RBAC.

## Pruebas de PostgreSQL real

Se utilizó PostgreSQL 18.4 local, base exclusiva `sgpmp_g167_test`, construida desde cero con las migraciones de dev hasta la head `30168ab97bd4`. Se conservaron las protecciones de `TEST_DATABASE_URL`, la transacción exterior y los savepoints del fixture común.

Los HTTP se ejecutaron con JWT y `TEST_ROL_APP=sgpmp_app`, sin superusuario ni BYPASSRLS. La preparación y las aserciones administrativas usaron la conexión del fixture. La ingesta utilizó el token de broker de pruebas y la identidad de servicio existente.

| Grupo | Aprobadas | Fallidas | Omitidas |
|---|---:|---:|---:|
| Nuevas: alta con/sin categoría, rollback de flush/commit, Ingeniero por finca, JWT/RBAC, dispositivo inexistente y categoría inválida | 8 | 0 | 0 |
| Existentes: repositorio de sensor bajo RLS, Administrador y Productor asignado | 2 | 0 | 0 |
| Nuevas: continuidad hasta calidad, escenarios con offset 0 y offset 2 | 0 | 2 | 0 |
| **Total distinto** | **10** | **2** | **0** |

Las pruebas del repositorio no otorgan al Productor permiso HTTP de creación: el caso HTTP sin permiso conserva 403. Se verificó además que el Ingeniero sin acceso a la finca recibe 404 y que, una vez asignado, puede crear el sensor.

Las pruebas de rollback observan un INSERT real antes de inducir el fallo de flush o commit, comprueban que no queda una fila parcial y que el reintento puede crear el sensor. No sustituyen entidades, casos de uso ni repositorios del alta por fakes.

Los padres (finca, área y dispositivo) se preparan mediante SQL del fixture. Desde el alta de sensor, asociación, calibración, ingesta y evaluación se invocan por HTTP. Se simula el paso del tiempo únicamente en el reloj de creación de la asociación para que las 21 capturas históricas queden dentro de su vigencia: `now()` de PostgreSQL permanece fijo por la transacción exterior de pruebas. No se desactivan validaciones temporales ni se reescriben auditorías después de la operación.

## Preparación local y repeticiones

Las primeras corridas detectaron privilegios de infraestructura pendientes en el rol del clúster recién creado: lectura de `configuraciones_remotas`, dependencias de ingesta, actualización de contacto de RF-60 y escritura de la caché de estados de sensores. Se provisionaron exclusivamente los privilegios necesarios en la base desechable, manteniendo las políticas y triggers reales. No son permisos RBAC nuevos ni cambios aplicados a la base oficial.

Otro intento rechazó correctamente lecturas anteriores a la asociación (`SENSOR_SIN_ASOCIACION`). Se corrigió la cronología del fixture, no la regla de RF-53. Los intentos interrumpidos anteriores a actualizar dev no se consideran pruebas aprobadas.

Cada ID se cuenta una vez, con su último resultado. Las repeticiones no se suman al total. Las evidencias temporales permanecen en `.pytest_cache/g167_*.xml`, los scripts de preparación/lanzamiento y el log del clúster. El shim de `fcntl` de Windows se limita al lanzador de pruebas. No se incorpora a producción.

El consolidado verificable está en `.pytest_cache/g167_resultados_consolidados.json`: 12 IDs distintos, 10 aprobados, 2 fallidos y ninguno omitido. La ejecución final de los dos escenarios está en `.pytest_cache/g167_hallazgo_drift.xml`. `git diff --no-index --check` sobre el archivo de pruebas y `git diff --check` terminaron sin errores de whitespace.

## Hallazgo distinto: snapshot de calibración perdido

1. RF-24 guarda la ganancia y el offset mediante el endpoint de calibración.
2. La función existente `modulo3.fn_obtener_calibracion` recupera ambos valores reales (DB-02, revisión `e5a3c9b17d42`).
3. `fn_ingesta_telemetria` los utiliza para calcular `valor_ajustado` y marca la lectura como calibrada.
4. Su INSERT final no incluye `parametros_calibracion`, por lo que la columna queda NULL.
5. El endpoint de evaluación selecciona esa columna y la pasa a `EvaluarCalidadTelemetriaUseCase`.
6. La fase de drift requiere `parametros_calibracion`; con `None` carece de esa entrada.

En ambos escenarios los 21 POST de ingesta y el POST de evaluación respondieron 201. La última lectura tiene valor crudo 22, valor ajustado 22 u 24 según el offset, y `calibrado=True`. La aserción que falla exige un snapshot de calibración no nulo en la evaluación; no es un fallo de creación del sensor ni de autenticación.

La columna y su mapeo ORM ya existen. El defecto no se resuelve añadiendo un default a `SensorModel`, exponiendo `es_activo` al cliente o convirtiendo una violación de un estado interno en un 4xx.

Se consultó al usuario si desea incorporar esta corrección distinta en la entrega o documentarla por separado. Mientras se define ese alcance, no se modifica el cálculo, la función de ingesta ni su migración. Una eventual corrección debe conservar los valores realmente utilizados durante el INSERT; leer la calibración actual al consultar una evaluación no reconstruye de forma fiable un snapshot histórico.

## Límites de la evidencia

Los adjuntos de TC-M03-G167 documentan el 500 observado en QA y 44 comprobaciones (8 aprobadas, 36 fallidas en cascada), pero no aportan el error SQL del servidor que pruebe un NOT NULL sobre `es_activo`. Esta revisión no demuestra que aquel despliegue ejecutara el mismo código y esquema que dev actual.

No se ejecutó la colección original de sus siete escenarios ni se certificó TEST desplegado. Los dos escenarios añadidos comprueban el flujo real disponible y mantienen visible la pérdida del snapshot. No se declara validado el drift ni se presenta la revisión como una reparación funcional del alta.

## Alcance de los archivos

Se añaden únicamente `tests/integration/test_inc_m03_123_g167_registro_sensor.py` y este informe. El usuario autorizó el commit y el push de las pruebas y este diagnóstico para #626, sin crear PR. No se modificaron archivos de producción ni migraciones, ni los archivos locales ajenos `AGENTS.md`, `pendientes_integracion_aiot_por_tarea_y_pr.md` y `pendientes_por_area/`.
