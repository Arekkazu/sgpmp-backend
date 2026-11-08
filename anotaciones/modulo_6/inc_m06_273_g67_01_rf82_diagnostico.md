# INC-M06-273-G67-01 · RF-82 · Diagnóstico de #957

Fecha: 2026-11-07. Responsable de la revisión: identidad Git verificada `Leandro`.

## Resultado

Las cinco estructuras reportadas están implementadas en la migración existente `c4d81e6f2a95_m06_nic41_esquema_rfc018.py`. Al probar el flujo con el rol real de la API se reprodujo una brecha de permisos: el esquema y las tablas heredadas que usa el reconocimiento no tienen las ACL necesarias en una base migrada desde cero. Se implementa una revisión aditiva de permisos, sin duplicar las tablas. El estado actual de la base que utiliza la API TEST requiere verificación directa con su conexión autorizada; no se dispone de esa conexión en este entorno.

## Versiones contrastadas

| Referencia remota, actualizada antes de revisar | SHA |
|---|---|
| dev | 3251d78d2c5822624dde988a94a37331610d1cef |
| test | e5d6934d3e68a20c26a8fdfea759f71d7c2828b6 |
| laura | 4d7f337dad6c8fe462aaaf9fa8016f47c74a7627 |

La rama `codex/inc-m06-273-g67-01-rf82-acceso-contable` parte del `dev` actualizado indicado arriba. Se añade la migración `e957a82c1107`, hija de `b7e2d94c1a68`.

La migración contable está en `dev` y `test`; no está en el árbol actual de `origin/laura`. El caso de uso unificado `reconocimiento/confirmar_reconocimiento_use_case.py` tiene el mismo blob en `dev` y `test`: `55016f65b1d6f38a945af1c9163303156022a41f`. La versión actual de `laura` no contiene ese archivo. Esto caracteriza las referencias actuales; no permite reconstruir qué SHA revisó QA.

## Estructuras existentes

| Tabla en modulo6 | Migración c4d81e6f2a95 |
|---|---|
| configuraciones_contables | Creación y configuración inicial con ID 1 |
| parametros_contables_especies | Clasificación, categoría de precio y vida útil por especie |
| asignaciones_cuentas_contables | Matriz de cuentas vigente |
| comprobantes_nic41 | Comprobantes del proceso de consolidación/cierre |
| lineas_asiento_nic41 | Hechos contables y trazabilidad de origen |

La migración también incluye restricciones, índices, permisos de las tablas nuevas y RBAC del módulo. Los parámetros por especie y la matriz de cuentas son configuración funcional, no valores que deban inventarse para completar una prueba.

## Flujo revisado

1. Router `m06_router.py`: POST de confirmación, JWT y permiso de crear sobre `reconocimiento_inicial`.
2. DTO `ConfirmarReconocimientoDTO`: estructura de la solicitud.
3. Adaptador M02: activo, especie, finca, titular y costo documentado, sujeto al RLS de la petición.
4. Proponedor/valorador: configuración general, parámetros de especie y precios vigentes. Ante ausencia de mercado y costo documentado, propone `VALORACION_POR_COSTO`; exige vida útil configurada.
5. Caso de uso: obtiene/crea período, persiste valoración `INICIAL_RF82`, reconocimiento, líneas cuando exista un hecho y auditoría.
6. Contabilizador/repositorios: resolución de cuentas mediante matriz y persistencia SQL.
7. El caso de uso controla commit/rollback de la operación completa.

RF-82 actualizado por RFC-018 remite la compra a la factura del proceso contable correspondiente. Cuando el valor reconocido por costo coincide con el costo de adquisición, la diferencia es cero y no se genera una línea de ajuste por reconocimiento. Una respuesta `lineas=[]` en ese escenario no demuestra un defecto. La donación por costo sí origina un hecho contable; se incluye para verificar matriz y persistencia de líneas. No se exige crear un comprobante de cierre en cada reconocimiento individual.

## Evidencia del despliegue TEST

[Deploy Migrations - test, ejecución 42388424297](https://github.com/Arekkazu/sgpmp-backend/actions/runs/42388424297), SHA `e5d6934d...`, terminó con éxito. El job `128450657248` registra:

- 2026-11-07 15:52:19 UTC: revisión inicial `94b14a6931d6`.
- 15:52:21 UTC: upgrade a `b7e2d94c1a68`.
- 15:52:23 UTC (10:52:23 America/Bogota): revisión final `b7e2d94c1a68 (head)`.

La cadena del repositorio es `eab9814cd751 → c4d81e6f2a95 → 94b14a6931d6 → b7e2d94c1a68`. Por tanto el destino de ese workflow reportaba una revisión posterior a la contable. El resultado NO acredita que `DATABASE_URL` de la API sea el mismo destino que `TEST_DATABASE_URL` del workflow, ni comprueba las tablas actuales de la base reportada por QA.

## Causa raíz reproducida y corrección

La migración contable concede ACL a las tablas nuevas, pero omite USAGE sobre modulo6 y las ACL de las tablas heredadas del baseline. Bajo sgpmp_app, PUT de parámetros por especie respondió 500 con SQLSTATE 42501: permission denied for schema modulo6. La prueba previa terminó con 1 aprobada y 1 error de preparación; no se atribuye ese fallo a TEST.

La inspección del catálogo local confirmó permisos de tabla en las estructuras nuevas pero ausencia de acceso al esquema, y ausencia de lectura/inserción en las dependencias heredadas. No se añadieron esos permisos al lanzador para ocultar el fallo: se corrigen mediante una migración versionada.

La revisión e957a82c1107 agrega, exclusivamente a los roles existentes del mismo catálogo que c4d81e6f2a95:

- USAGE del esquema modulo6.
- SELECT de precios_mercado y parametros_costos_venta.
- SELECT/INSERT en periodos_contables, calculos_valor_razonable, valoraciones_por_costos, reconocimientos_iniciales y auditorias_financieras.
- USAGE/SELECT de las secuencias de esas cinco tablas.

No concede CREATE, DELETE o UPDATE en las tablas heredadas, no crea roles ni usa PUBLIC como destinatario. Los permisos de las tablas nuevas ya están en c4d81e6f2a95. Conserva grants anteriores, triggers, RBAC y RLS. El downgrade no revoca ACL porque algunos ambientes podían tenerlas antes de esta revisión; sigue el criterio conservador de b7e2d94c1a68.

## Pruebas locales

| Grupo | Aprobadas | Fallidas | Errores | Omitidas |
|---|---:|---:|---:|---:|
| tests/financial_valuation (unitarias sin BD) | 14 | 0 | 0 | 0 |
| Integración HTTP/BD de esta incidencia | 9 | 0 | 0 | 0 |
| **Total distinto final** | **23** | **0** | **0** | **0** |

La base local sgpmp_inc957_test fue creada desde cero, migrada hasta b7e2d94c1a68 y actualizada incrementalmente con e957a82c1107. Se verificó un único head final e957a82c1107.

Las nueve regresiones cubren las cinco estructuras/configuración inicial, reconocimiento por costo de compra, donación con matriz y línea contable, rechazo de confirmación duplicada, JWT/rol, rollback tras insertar la auditoría, recuperación del 500 al reaplicar la migración de forma idempotente, reconocimiento con valor razonable y rechazo del Contador sin acceso a la finca.

La prueba de ACL reproduce el rechazo anterior mediante REVOKE únicamente dentro de la base local exclusiva, aplica la migración y comprueba HTTP 201. También comprueba que no se concede CREATE ni DELETE y que el downgrade conservador no elimina permisos anteriores.

Evidencia final: .pytest_cache/inc957_unit.xml, inc957_pg_final.xml e inc957_resultado_final.json. Las corridas previas detectaron la brecha original y dos defectos de preparación de las pruebas nuevas (intento de cambiar el origen financiero inmutable y propagación de RuntimeError del TestClient). Se corrigió la preparación sin deshabilitar controles. Esos intentos no se suman como pruebas aprobadas adicionales.

Comandos ejecutados con los lanzadores locales aislados:

- Unidad: inc957_run_unit.py tests/financial_valuation -q --tb=short --basetemp=.pytest_cache/inc957_unit_tmp --junitxml=.pytest_cache/inc957_unit.xml.
- Integración: inc957_run_tests.py tests/integration/test_inc_m06_273_g67_01_reconocimiento_costo_integration.py -q --tb=line --basetemp=.pytest_cache/inc957_pg_tmp_v4 --junitxml=.pytest_cache/inc957_pg_final.xml.

No se ejecutaron G67-01 ni escrituras en la API TEST oficial.

Las pruebas HTTP utilizan `TEST_ROL_APP=sgpmp_app`, rol sin superusuario ni BYPASSRLS. La siembra y las consultas de comprobación se ejecutan con la conexión administradora de la base local exclusiva; las solicitudes no. Se mantienen triggers y restricciones activos. Se complementan únicamente permisos de las dependencias preexistentes del entorno local, sin modificar las políticas ni atribuir esas ACL a TEST.

Al finalizar se eliminó exclusivamente sgpmp_inc957_test y se detuvo el clúster local iniciado para esta revisión. Se comprobó que las demás bases locales permanecen; se conservan logs, lanzadores y JUnit.

El shim de fcntl existe únicamente en los lanzadores temporales. No se modificó producción para ejecutar en Windows. Las evidencias temporales permanecen en `.pytest_cache`.

## Acción necesaria en TEST

1. Con acceso autorizado, contrastar el SHA del backend desplegado, la conexión efectiva del servicio y el destino del workflow, sin publicar secretos.
2. Ejecutar `inc_m06_273_g67_01_verificacion_test.sql` con la misma base/rol que utiliza la API. Es solo lectura: identifica la base, el rol, las cinco tablas y permisos efectivos.
3. Con acceso de lectura a la tabla de versión, consultar `public.alembic_version`.
4. Si faltan las tablas, actualizar el destino correcto con c4d81e6f2a95 y sus dependencias mediante el procedimiento autorizado. Si las tablas ya existen, desplegar además e957a82c1107 para subsanar las ACL reproducidas. No se ejecutaron esas acciones en bases oficiales.
5. Si Alembic reporta una revisión posterior a c4d81e6f2a95 pero faltan objetos, investigar divergencia, destino incorrecto o eliminación manual. No usar stamp, downgrade ni una segunda migración de creación como reparación automática.
6. Configurar los parámetros de especie, vida útil y matriz aplicables con el Contador; ejecutar G67-01 en sandbox autorizado y conservar respuesta, reconocimiento, valoración, auditoría y líneas que correspondan al origen.

## Alcance y límites

Se añaden una migración de permisos, una prueba de integración, este informe, una descripción de PR y una consulta SQL de solo lectura. No se modificaron contratos HTTP ni datos oficiales; tampoco se hizo commit, push ni publicación en GitHub.

Existe una corrección de desarrollo reproducida para las ACL del flujo actual. La ausencia de tablas reportada requiere comprobar el destino y despliegue con BD/infraestructura. La validación oficial de G67-01 permanece pendiente hasta desplegar y repetir el caso sobre la API TEST.
