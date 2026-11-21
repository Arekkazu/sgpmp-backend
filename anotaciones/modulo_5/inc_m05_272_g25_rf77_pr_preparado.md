# RF-77 — Auditar la generación y exportación de reportes de gastos · INC-M05-272-G25

## Desvío identificado

| RF exige | Antes | Ahora |
|---|---|---|
| CA-11: generación registrada con usuario y timestamp | El reporte se guardaba sin evento en la bitácora de Suministros | Reporte y evento se confirman en la misma transacción |
| Trazabilidad de la exportación CSV/PDF | Solo se auditaba el fallo del motor PDF | Cada exportación exitosa registra actor, reporte, archivo y formato |
| Historial regenerable y trazable | Regenerar no dejaba evidencia de la acción | Se registra la regeneración sin modificar el snapshot original |

Referencias: #958, INC-M05-272-G25, RF-77 CA-11/postcondición 3, TC-M05-G25/TC-M05-025 y bitácora RF-80.

## Causa raíz

GenerarReporteGastosUseCase no recibía el puerto de auditoría. ExportarReporteGastosUseCase lo utilizaba únicamente ante fallo PDF; sus caminos exitosos no emitían eventos. La regeneración tampoco auditaba. El trigger del snapshot escribe el log técnico de BD, que no sustituye la bitácora de negocio consultada por GET /suministros/auditoria.

## Cambios implementados

- Auditoría de generación antes del commit, compartida por el camino síncrono y generar_forzado del worker.
- Auditoría de exportación exitosa junto con la persistencia del archivo.
- Auditoría de regeneración, conservando el snapshot original.
- Contexto opcional datos_nuevos en el evento de dominio y su mapeo a la columna JSON existente.
- Inyección del puerto existente mediante la fábrica de reportes.
- Conservación del evento de fallo PDF y rollback de la acción si falla su auditoría.

Se reutilizan INSERT/SELECT del catálogo actual, las entidades reporte_gastos_acumulados/archivos_exportacion_suministros y el clasificador de retención vigente. No se utiliza el evento de provisión de costos de RF-79 para representar estas acciones.

## Migración

No requiere migración. Se comprobaron las columnas, enums y triggers existentes sobre una base PostgreSQL migrada desde cero hasta b7e2d94c1a68. El hash continúa a cargo de trg_audit_hash.

## Contrato resultante

- POST /suministros/reportes-gastos conserva HTTP 200 síncrono y 202 asíncrono.
- POST /suministros/reportes-gastos/{id}/exportacion conserva HTTP 201.
- La regeneración conserva su respuesta y advertencia.
- Los eventos EXITOSO incluyen actor y timestamps; datos_nuevos distingue GENERACION, REGENERACION y EXPORTACION e identifica el reporte/archivo correspondiente.
- Encolar, consultar o descargar no crea un evento falso de generación; exportar no duplica ese evento.
- Si falla la exportación, el reporte previamente confirmado continúa disponible.

## Pruebas realizadas

| Grupo | Aprobadas | Fallidas | Errores | Omitidas |
|---|---:|---:|---:|---:|
| Unitarias de suministros | 36 | 0 | 0 | 0 |
| Integración HTTP/PostgreSQL real | 15 | 0 | 0 | 0 |
| **Total distinto** | **51** | **0** | **0** | **0** |

Cobertura: Productor/Administrador, generación, CSV/PDF reales y descarga, exportación combinada, regeneración sin alterar snapshot, eventos inmediatos y sin duplicados, rollback en tres acciones, fallo PDF, JWT/RBAC, finca, historial y archivos privados, rollback exterior y procesamiento por worker con identidad de servicio existente.

HTTP bajo sgpmp_app sin superusuario ni BYPASSRLS, restricciones y triggers activos. El worker se prueba secuencialmente dentro de una transacción de prueba; no se atribuye cobertura de concurrencia de procesos. La preparación complementa permisos locales del baseline, incluida lectura de identidad visual para PDF. Esos ajustes no son cambios productivos.

Las tres regresiones iniciales fallaron por ausencia de auditoría y se conservaron como evidencia previa; no se suman al total final. No se ejecutó la suite QA oficial ni se midió su SLA en TEST.

## Integración con sgpmp_dev

Rama fix/inc-m05-272-g25-auditoria-reportes-rf77 creada desde dev actualizado 3251d78d2c5822624dde988a94a37331610d1cef. Sin DDL/DML sobre sgpmp_dev o sgpmp_test. No incorpora la corrección de M06 #957.

## Dependencias y pendientes

- Esquema existente de M05 y acceso a pgcrypto previsto por b7e2d94c1a68.
- Decisión confirmada: Productor genera/exporta, pero la bitácora mantiene acceso exclusivo de Administrador/Contador/Revisor Fiscal. QA debe verificar las acciones del Productor mediante un lector autorizado y filtro por actor.
- Desplegar y repetir TC-M05-G25 en sandbox autorizado. La disponibilidad local inmediata no se presenta como aprobación del ambiente oficial.
- Se reutiliza la bitácora existente; no se afirma entrega a M12 ni se amplía esa integración.

## Alcance del commit

Diez archivos propios: seis de producción, dos de pruebas y dos informes. Cabeceras de seguimiento actualizadas sin alterar filas previas. Los archivos locales de otras tareas y .pytest_cache quedan fuera.

## Revisión contra dev

Comparar exclusivamente esta corrección contra origin/dev. Se conservan arquitectura, contratos HTTP, cálculos monetarios y permisos; no hay migraciones ni cambios de frontend. Commit y push pendientes de autorización del usuario.
