# INC-M05-272-G25 · RF-77 · Diagnóstico y validación de #958

Fecha: 2026-11-07 (America/Bogota). Identidad Git consultada en el repositorio: Leandro.

## Resultado

El defecto sigue presente en la base dev revisada y se corrigió en la rama fix/inc-m05-272-g25-auditoria-reportes-rf77, creada desde dev actualizado 3251d78d2c5822624dde988a94a37331610d1cef.

La generación, regeneración y exportación exitosa registran ahora un evento mediante AuditoriaSuministroPort, en modulo5.auditorias_suministros. La operación y su evento se confirman en la misma transacción. Si la auditoría falla, no se devuelve éxito ni queda persistido el nuevo reporte/archivo de esa acción.

No se necesita migración: se reutilizan tablas, tipos, columnas JSON, índices y triggers existentes. El trabajo no incluye commit, push, merge ni publicación de PR.

## Referencias y evidencia recibida

- Issue #958: INC-M05-272-G25, RF-77 CA-11 y postcondición 3; TC-M05-025 dentro de TC-M05-G25.
- Especificacion-Requerimientos-Modulo5.md: RF-77, historial de reportes, exportación y RF-80.
- resultado_TC-M05-G25.json: 18 checkpoints, 17 aprobados y 1 fallido; C02 identifica ausencia de auditoría de generación/exportación.
- resultado_TC-M05-G25.html: evidencia complementaria de la misma corrida.

Los documentos se trataron como evidencia y especificación, no como autorización para escrituras oficiales o cambios ajenos al alcance.

## Causa raíz y flujo previo

1. El router de RF-77 orquesta generación y exportación y conserva los códigos 200/202/201.
2. GenerarReporteGastosUseCase guardaba el snapshot y hacía commit sin conocer el puerto de auditoría.
3. ExportarReporteGastosUseCase guardaba el archivo y hacía commit sin registrar éxito. El puerto solo se usaba al fallar PDF.
4. ConsultarReporteGastosUseCase.regenerar recalculaba sin auditar la acción.
5. El trigger trg_auditoria de reporte_gastos_acumulados escribe en auditoria.logs_dml, no en la bitácora consultada por GET /suministros/auditoria.
6. El worker asíncrono usa generar_forzado y exportar; por ello también necesitaba el registro desde esos puntos compartidos.

Tres regresiones iniciales con fakes reprodujeron la ausencia de invocación del puerto: generación, exportación CSV y exportación PDF. Las tres fallaron antes del cambio por cero llamadas a registrar.

## Comprobación previa de BD y RBAC

Se creó sgpmp_inc958_test exclusivamente en PostgreSQL 18 local (127.0.0.1:55429), migrada desde cero hasta el único head b7e2d94c1a68. Se inspeccionaron columnas, enum, triggers y permisos de los recursos 51 y 57 en transacción de solo lectura.

- datos_nuevos ya existe como JSON en auditorias_suministros.
- INSERT y SELECT ya pertenecen al enum nativo de tipo_operacion.
- fecha_evento e id_usuario son obligatorios; fecha_emision y hash_integridad ya forman parte del contrato.
- trg_audit_hash calcula el hash; los eventos nuevos no lo calculan ni lo asignan en Python.
- La generación usa el recurso 51, acción 5; la bitácora usa el recurso 57, acción 2.
- Productor y Administrador pueden generar/exportar. La bitácora corresponde a Administrador, Contador y Revisor Fiscal.

**Decisión confirmada por el usuario:** conservar ese RBAC y verificar los eventos del Productor mediante un lector autorizado. No se concede acceso al Productor a la bitácora. Se verifican sus eventos mediante el filtro id_usuario; los lectores autorizados conservan su alcance de auditoría. El historial de reportes y las descargas permanecen privados.

No se realizaron consultas o escrituras sobre una base oficial en esta tarea. El catálogo local y las pruebas no acreditan el estado actual de TEST.

## Cambios implementados y contratos

| Acción | entidad_afectada | tipo_operacion existente | datos_nuevos.accion | Momento |
|---|---|---|---|---|
| Generación síncrona o completada por worker | reporte_gastos_acumulados | INSERT | GENERACION | Después de guardar el reporte y antes del commit |
| Regeneración desde historial | reporte_gastos_acumulados | SELECT | REGENERACION | Tras recalcular, antes de responder |
| Exportación CSV/PDF | archivos_exportacion_suministros | INSERT | EXPORTACION | Después de guardar el archivo y antes del commit |

Los eventos incluyen actor, resultado EXITOSO, activo cuando corresponde y contexto estructurado. La generación/regeneración conserva la referencia al reporte, parámetros y total; la exportación conserva ID de reporte, UUID de archivo, formato y cantidad de registros. El repositorio agrega fecha_emision UTC y PostgreSQL asigna fecha_evento y hash con los mecanismos existentes.

Se usan descripciones legibles sin códigos internos en el texto nuevo. No se reutiliza REPORTE_COSTOS_GENERADO, que corresponde al reporte de provisión de RF-79. Los tipos genéricos existentes mantienen la clasificación conservadora NIC41/5 años del clasificador vigente.

El nuevo campo opcional datos_nuevos del evento de dominio se añade al final y se mapea a la columna existente. Los productores anteriores del puerto conservan el comportamiento por defecto.

La consulta simple, el historial, la descarga y la reconstrucción interna para exportar no generan eventos falsos de generación. Encolar un trabajo no significa haber generado un reporte: el evento aparece al persistir el resultado. La regeneración no crea ni modifica el snapshot original. El fallo PDF conserva su evento FALLIDO y no crea un evento de exportación exitosa.

Se preserva la separación de transacciones del flujo existente: una generación exitosa seguida por una exportación fallida conserva el reporte y su auditoría de generación.

## Archivos del cambio

### Producción (6)

- src/supplies/application/use_cases/reporte_gastos/generar_reporte_gastos_use_case.py
- src/supplies/application/use_cases/reporte_gastos/consultar_reporte_gastos_use_case.py
- src/supplies/application/use_cases/reporte_gastos/exportar_reporte_gastos_use_case.py
- src/supplies/domain/repositories/auditoria_suministro_port.py
- src/supplies/infrastructure/repositories/auditoria_suministro_repository.py
- src/supplies/infrastructure/factories/reporte_gastos_factory.py

### Pruebas (2)

- tests/supplies/test_inc_m05_272_g25_auditoria_reportes.py
- tests/integration/test_inc_m05_272_g25_auditoria_reportes_integration.py

Se agregan este informe y la descripción preparada del PR: total 10 archivos propios. Cada archivo de código conserva sus filas previas y tiene una sola fila de seguimiento para esta incidencia, con la identidad Git verificada y la fecha real del cambio. Los archivos locales de otras tareas permanecen fuera.

## Validación final

| Grupo | Aprobadas | Fallidas | Errores | Omitidas |
|---|---:|---:|---:|---:|
| tests/supplies, unitarias con fakes y dominio | 36 | 0 | 0 | 0 |
| Integración HTTP/BD de #958 | 15 | 0 | 0 | 0 |
| **Total distinto final** | **51** | **0** | **0** | **0** |

La integración cubre:

1. Generación, exportación real CSV/PDF, consulta inmediata de eventos y descarga como Productor y Administrador.
2. Exportación incluida en el POST de generación, con un evento por acción y un solo reporte.
3. Regeneración con evento propio, advertencia existente y snapshot original intacto.
4. Fallo controlado después de insertar el evento de generación, exportación o regeneración: rollback sin falso éxito ni registros parciales.
5. Fallo del motor PDF: reporte disponible, evento FALLIDO conservado, ningún archivo o evento exitoso de exportación.
6. JWT, rol de solo lectura, rechazo del Productor a la bitácora, historial propio, descarga de archivo ajeno rechazada y generación sin finca denegada.
7. Rollback exterior de la corrida: revierte reportes, archivos y eventos pese a los commits internos, sin borrar las precondiciones del escenario.
8. Trabajo asíncrono real de aplicación y repositorios: cola sin evento prematuro; worker con identidad de servicio existente; resultado COMPLETADO y actor solicitante conservado en los dos eventos.

Las solicitudes HTTP se ejecutaron bajo TEST_ROL_APP=sgpmp_app, sin superusuario ni BYPASSRLS. La siembra y las consultas de comprobación usan el administrador de la base local exclusiva. No se desactivaron restricciones, triggers ni políticas.

Para el worker, SessionLocal se enlaza a la conexión de la transacción exterior y mantiene declarar_identidad_sistema de producción. Se ejecuta _procesar secuencialmente con sesiones propias y rol sgpmp_app. Esto valida su flujo y persistencia, no concurrencia entre procesos. La notificación externa se sustituye en esa prueba; no se afirma entrega real de notificaciones.

El fixture local complementa ACL de dependencias M01/M02/M09 y M05 del baseline. En la primera corrida PG, PDF encontró ausente SELECT sobre modulo9.identidad_visuales; se completó solo esa dependencia local conservando RLS y se repitió la validación. No se modificaron permisos productivos ni migraciones por ese ajuste del entorno.

Los tres fallos iniciales de reproducción y la corrida intermedia no se suman como aprobaciones adicionales. Una advertencia de deprecación existente de Starlette/httpx no produjo fallos ni omisiones.

### Evidencia y comandos

- .pytest_cache/inc958_red_unit.xml: reproducción previa, 3 fallos esperados.
- .pytest_cache/inc958_unit.xml: resultado final de unidad.
- .pytest_cache/inc958_pg.xml: resultado final HTTP/PG.
- .pytest_cache/inc958_preflight.json: catálogo, triggers y RBAC local.
- .pytest_cache/inc958_resultado_final.json: conteos y hashes de los ocho archivos de código probados.

Lanzadores temporales, sin cambios de producción para Windows:

- inc958_run_unit.py tests/supplies -q --tb=short --maxfail=1 --basetemp=.pytest_cache/inc958_unit_tmp --junitxml=.pytest_cache/inc958_unit.xml.
- inc958_run_tests.py tests/integration/test_inc_m05_272_g25_auditoria_reportes_integration.py -q --tb=line --maxfail=1 --basetemp=.pytest_cache/inc958_pg_tmp_v2 --junitxml=.pytest_cache/inc958_pg.xml.

El shim de fcntl solo existe en los lanzadores. Las evidencias temporales no forman parte de la entrega Git.

## Dependencias, despliegue y límites

- No hay migración propia ni cambio en OpenAPI. Se necesitan el esquema existente de M05 y b7e2d94c1a68 para que el hash pueda resolver pgcrypto.
- El cambio no depende de la rama #957 de M06 ni incorpora sus commits.
- No se alteran los cálculos de gastos, estados de suministros, contratos de descarga, RBAC o políticas RLS.
- La visibilidad se comprobó inmediatamente después de la respuesta HTTP, sin esperas de sondeo. No se afirma una medición de SLA de dos segundos en TEST oficial.
- No se ejecutó la suite oficial TC-M05-G25 ni se validó un despliegue. Tras integrar/desplegar, QA debe repetirla, conservando el RBAC confirmado y consultando los eventos con un lector autorizado.
- La validación corresponde a la bitácora M05 existente; no acredita entrega a un repositorio transversal externo.

## Cierre del entorno local · 2026-11-08

Se eliminó exclusivamente sgpmp_inc958_test y se comprobó que las demás bases locales permanecen sin eliminaciones. El clúster iniciado para estas pruebas quedó detenido. Se conservaron los logs, JUnit, scripts y hashes temporales de evidencia. En la revisión final se confirmó que los ocho archivos de código coinciden con los hashes de la versión que aprobó las 51 pruebas; no se repitieron pruebas sin cambios funcionales.
