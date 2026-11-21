# INC-M05-276-G38 · RF-80 — Rango temporal de auditoría

Fecha: 2026-11-08. Identidad Git consultada: Leandro.
Issue: [#961](https://github.com/Arekkazu/sgpmp-backend/issues/961).
Rama: `fix/inc-m05-276-g38-rango-auditoria-rf80`.
Base: dev actualizada mediante fetch y fast-forward antes de crear la rama, en `3251d78d2c5822624dde988a94a37331610d1cef`.

## Evidencia y alcance

Se leyeron resultado_TC-M05-G38.json y resultado_TC-M05-G38.html de Downloads. El JSON reporta 11 checkpoints, 8 correctos y 3 fallidos. #961 corresponde a B01 / TC-M05-044.1 / CU06 FA-01: rango invertido aceptado como consulta válida vacía.

El mismo adjunto reporta B02 (autoauditoría de consultas sin resultados) y C02 (evento de acceso denegado). Son hallazgos diferentes y no se incorporan a esta corrección. No se afirma que todo G38 quede aprobado con este cambio.

No había comentarios adicionales en la issue al revisarla. La propuesta del reporte se trató como evidencia y se contrastó con el código; no como una instrucción para modificar scripts de QA o escribir en TEST.

## Diagnóstico confirmado

Se revisó el flujo router → FiltrosAuditoriaSuministro → casos de uso de consulta/exportación → puerto de lectura → repositorio SQLAlchemy → modelo/tabla de auditoría.

En dev, los parámetros FechaHoraUtc normalizaban correctamente cada fecha, pero no validaban su relación. El objeto de filtros tampoco imponía el orden y ambos casos de uso consultaban el repositorio. Este aplicaba condiciones AND inclusivas (fecha_evento >= inicio y <= fin): un rango invertido producía cero filas y total cero.

La regresión HTTP con un puerto falso reprodujo el resultado 200 con items=[] y total=0 antes de modificar producción. La evidencia de esa corrida se conserva en .pytest_cache/inc961_reproduccion.xml. La reproducción con fakes demuestra el contrato y la llamada al puerto; la validación real de filtros/persistencia se hizo posteriormente en PostgreSQL.

## Corrección

La coherencia temporal se valida en __post_init__ del objeto de filtros de dominio, compartido por listado y exportación. Esto evita duplicar la regla en routers o permitir que otro consumidor construya un filtro inválido.

- Con ambos extremos presentes, compara los instantes en UTC y rechaza únicamente inicio > final.
- Los extremos iguales y los límites omitidos siguen admitidos.
- Un datetime sin zona representa UTC, conservando la política de fechas existente. La comparación no modifica los valores del objeto congelado.
- Un rango invertido produce ValidationError compartido, HTTP 400, error_code VAL_ENTRADA y field fecha_hasta. Mensaje: “El inicio del rango no puede ser posterior al final. Corrige las fechas e intenta de nuevo.”
- El rechazo ocurre al construir filtros, antes de construir/ejecutar el caso de uso y antes de consultar el repositorio de auditoría o generar archivos.
- El router documenta 400 en OpenAPI del listado. La exportación ya lo documentaba.

Se mantienen las validaciones de formato de FastAPI/Pydantic y su handler existente, que también devuelve 400 VAL_ENTRADA. No se cambian los schemas exitosos, campos, ordenamiento, paginación, detalles ni filtros restantes. Los límites SQL continúan siendo inclusivos.

La autorización ocurre antes de construir los filtros. Las consultas a autenticación/RBAC siguen siendo necesarias; “sin consultar repositorio” se refiere al repositorio de la bitácora, no a eliminar las consultas de seguridad.

## BD, RBAC y arquitectura

No requiere migración, tabla, columna, índice, permiso o trigger nuevos. El defecto es de validación previa, no de SQL o de datos.

Se verificaron versión de migración, tabla de auditoría, enums y permisos del recurso 57 en PostgreSQL local migrado desde cero. La tabla de auditoría de M05 no tiene RLS en esta revisión de dev; no se atribuye a esta corrección una protección de filas inexistente. Se conservan los permisos de Administrador, Contador y Revisor Fiscal para lectura/exportación y la denegación para Productor/Veterinario.

El dominio usa datetime y el error compartido; no importa FastAPI, Pydantic, SQLAlchemy ni infraestructura. No se introduce lógica de negocio en el router, ni SQL fuera de repositorios. No hay commits/rollbacks nuevos, escrituras de negocio ni cambios en auditoría.

## Pruebas finales

| Grupo distinto | Aprobadas | Fallidas | Omitidas |
|---|---:|---:|---:|
| tests/supplies: dominio y HTTP con fakes | 40 | 0 | 0 |
| Integración HTTP con PostgreSQL 18 real | 24 | 0 | 0 |
| Total sin repetir corridas | 64 | 0 | 0 |

Las 40 incluyen 22 regresiones nuevas y 18 pruebas existentes. Las corridas de reproducción y las repeticiones no se suman al total.

Cobertura relevante:

- Rango invertido rechazado sin invocar el puerto de auditoría ni generar CSV/XLSX/PDF.
- Fechas malformadas probadas por separado en ambos extremos de consulta y exportación.
- Rango válido sin coincidencias: 200, total cero/lista vacía o CSV vacío con cabecera.
- Igualdad de extremos, filtros abiertos, offsets distintos, fechas sin zona y una hora repetida por cambio de horario: comparación por instante UTC.
- Eventos reales en los límites inferior/superior, inclusión de ambos, exclusión del posterior, orden descendente y paginación.
- CSV con los mismos eventos filtrados y detalle de evento conservado.
- JWT real y permisos de Administrador, Contador y Revisor Fiscal; Productor/Veterinario siguen recibiendo 403 y JWT ausente 401, sin consulta a la bitácora.
- Documentación OpenAPI del 400.

La integración registra las llamadas al repositorio y delega al método SQLAlchemy real, sin sustituir sus resultados. Los eventos y usuarios se siembran en el fixture, con constraints y triggers activos; las solicitudes HTTP usan sgpmp_app (sin superusuario ni BYPASSRLS). No se trata de una prueba de concurrencia ni de rendimiento; esta modificación de lectura no altera garantías transaccionales.

## Entorno y límites

Base local exclusiva sgpmp_inc961_test, PostgreSQL 18 en 127.0.0.1:55429, migración b7e2d94c1a68. TEST_DATABASE_URL y TEST_ROL_APP apuntan al entorno aislado/sgpmp_app. Las ACL locales necesarias para el fixture se preparan fuera de producción; no acreditan el estado de ACL de TEST o DEV. Se conservan las protecciones del fixture y use_insertmanyvalues=False.

El shim fcntl está únicamente en los lanzadores temporales de pytest por la dependencia existente del SDK en Windows. TestClient requiere un socket loopback interno; las corridas sin ese acceso quedaron detenidas al iniciar su event loop, antes de ejecutar HTTP, y se terminaron. Se ejecutaron con el acceso local permitido, sin modificar producción para solucionar esa limitación.

La suite emite un aviso existente de deprecación Starlette/httpx. No representa una prueba fallida. No se modificaron dependencias para ocultarlo.

Al terminar se eliminó únicamente sgpmp_inc961_test y se detuvo el clúster local iniciado para estas pruebas. Se verificó que las otras bases locales permanecieran intactas y se conservaron logs, lanzadores y evidencias.

No se ejecutó DDL/DML, ni se desplegó código, en TEST o DEV oficiales. Queda pendiente reejecutar B01 en TEST después de integrar/desplegar. La corrección de #960 y otras ramas anteriores no se arrastró a esta rama.

## Entrega y evidencias

Archivos:

- src/supplies/domain/repositories/auditoria_suministro_read_port.py
- src/supplies/infrastructure/routers/auditoria_suministros_router.py
- tests/supplies/test_inc_m05_276_g38_rango_auditoria.py
- tests/integration/test_inc_m05_276_g38_rango_auditoria_integration.py
- anotaciones/modulo_5/inc_m05_276_g38_rf80_diagnostico.md
- anotaciones/modulo_5/inc_m05_276_g38_pr_preparado.md

Los cuatro archivos de código incluyen la tabla de seguimiento con fecha real, identidad Git y tarea/RF. Se preservan filas anteriores y archivos locales ajenos.

Evidencias temporales excluidas del commit: .pytest_cache/inc961_reproduccion.xml, inc961_unit.xml, inc961_integracion.xml, inc961_preflight.json, inc961_evidencia_final.json, inc961_postgres.log y lanzadores inc961_*.py.

Commit, push y PR no se realizan sin la instrucción correspondiente del usuario para esta entrega.
