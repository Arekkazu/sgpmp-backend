# RF-82 — Habilitar el reconocimiento inicial con los permisos contables requeridos · INC-M06-273-G67-01

## Desvío identificado

| RF exige | Antes | Ahora |
|---|---|---|
| Reconocer por costo cuando no existe precio y hay costo documentado | En una base migrada desde cero, el rol normal de la API carece de acceso al esquema contable y a tablas heredadas del flujo | Una migración aditiva concede exclusivamente los permisos requeridos por el reconocimiento |
| Conservar reconocimiento, valoración y auditoría en una transacción | El flujo se bloquea con 500 por SQLSTATE 42501 | Se verifica persistencia correcta y rollback ante fallo posterior |
| Asentar el hecho cuando corresponde al origen | Los permisos bloquean el acceso a la configuración | Se comprueba la matriz y la línea registrada para una donación por costo |

Referencias: #957, INC-M06-273-G67-01, RF-82, RF-88 escenario A y RFC-018. El reporte identifica cinco tablas ausentes en TEST; esas tablas ya están definidas en c4d81e6f2a95. La corrección reproducida aquí corresponde a ACL, no a una segunda creación de esas estructuras.

## Causa raíz

La migración c4d81e6f2a95 concede permisos sobre sus tablas nuevas, pero no concede USAGE sobre modulo6 ni ACL sobre las dependencias heredadas del baseline. Con sgpmp_app, la configuración por especie respondió 500 y el catálogo local confirmó permisos insuficientes. Esto no se detecta ejecutando el flujo como superusuario.

## Cambios implementados

- Nueva revisión e957a82c1107: USAGE en modulo6 para los roles ya contemplados por la migración contable.
- Lectura de precios_mercado y parametros_costos_venta.
- Lectura/inserción en periodos_contables, calculos_valor_razonable, valoraciones_por_costos, reconocimientos_iniciales y auditorias_financieras, con acceso a sus secuencias.
- Regresiones HTTP con JWT, RBAC, aislamiento por finca, auditoría y rollback; verificación de idempotencia y de recuperación del fallo anterior al aplicar la revisión.
- Diagnóstico y consulta de solo lectura para contrastar el destino real de TEST.

## Migración

`b7e2d94c1a68 → e957a82c1107`.

No crea tablas, roles o cuentas contables; no otorga CREATE, DELETE, nuevos permisos RBAC ni accesos a PUBLIC. Conserva RLS y triggers. El downgrade es conservador y no revoca grants que podían existir previamente en el ambiente, como en b7e2d94c1a68. El despliegue oficial necesita seguir el procedimiento autorizado de BD.

## Contrato resultante

POST /finanzas/reconocimientos/{id_activo_biologico} conserva su contrato y HTTP 201 al confirmar. La ausencia de precio activa VALORACION_POR_COSTO/INICIAL_RF82 cuando existen las precondiciones funcionales. Una compra al costo puede retornar lineas=[] porque no hay diferencia de valoración; RFC-018 registra la compra por factura. Los hechos que sí corresponden al reconocimiento resuelven la matriz y conservan sus líneas.

## Pruebas realizadas

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

PostgreSQL 18 aislado, rol HTTP sgpmp_app sin superusuario ni BYPASSRLS, triggers y restricciones activos. La preparación y las consultas de comprobación usan la conexión administradora local. Los lanzadores complementan permisos de dependencias M01/M02/M09 de ese entorno; los permisos de M06 proceden de la migración probada. No se presentan estas pruebas como validación del entorno oficial.

## Integración con sgpmp_dev

La rama parte de dev actualizado: 3251d78d2c5822624dde988a94a37331610d1cef. No se ejecutó DDL/DML en sgpmp_dev ni sgpmp_test. La API desplegada y su base efectiva requieren comprobación autorizada antes de cerrar la incidencia.

## Dependencias y pendientes

- Las cinco tablas de #957 pertenecen a c4d81e6f2a95, ya presente en dev y test.
- El workflow TEST 42388424297 terminó en b7e2d94c1a68 el 2026-11-07 a las 15:52:23 UTC. Ese registro no demuestra que la API use la misma conexión ni que las tablas reportadas sigan presentes.
- Contrastar la base/rol de la API con el destino de TEST_DATABASE_URL del workflow; comprobar versión y estructuras con la consulta de solo lectura adjunta.
- Desplegar e957a82c1107 y repetir G67-01 en sandbox autorizado. Si faltan tablas pese a una versión posterior a c4d81e6f2a95, investigar divergencia antes de intentar reparar.
- Configuración de especie, vida útil y cuentas a cargo del Contador; no se incorporan datos contables ficticios.

## Alcance del commit

Propuesta de cinco archivos: migración, pruebas de integración, diagnóstico, consulta SQL de solo lectura y esta descripción. Sin cambios en lógica financiera, DTO, routers o contratos. Los archivos locales de otras tareas quedan fuera.

## Revisión contra dev

Comparar exclusivamente los cinco archivos de esta corrección contra origin/dev. La migración parte del head b7e2d94c1a68; revisar posibles heads adicionales si dev cambia antes de integrar. No se publicó un PR ni se hizo commit/push durante la implementación.
