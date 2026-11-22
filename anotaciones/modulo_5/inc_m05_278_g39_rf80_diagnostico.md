# INC-M05-278-G39 · RF-80 — Integridad e identidad de auditoría

Fecha: 2026-11-08. Identidad Git consultada: Leandro.
Issue: [#964](https://github.com/Arekkazu/sgpmp-backend/issues/964).
Rama: `fix/inc-m05-278-g39-integridad-auditoria-rf80`.
Base: dev actualizada mediante fetch y fast-forward a `3251d78d2c5822624dde988a94a37331610d1cef` antes de crear la rama.

## Evidencia y decisiones

Se leyeron resultado_TC-M05-G39.json y resultado_TC-M05-G39 (1).html. QA informa 8 checkpoints, 5 correctos y 3 fallidos: A02 (incompletos sin causa), B02 (405 sin evento de seguridad) y C01 (ausencia de id_evento_m05). B03, recálculo de hash sobre las columnas reales, figura APROBADO; no se incorpora un cuarto defecto por esa observación pendiente de la issue.

El usuario confirmó expresamente conservar el contenido y hashes históricos, corregir nuevos eventos y documentar los antiguos sin inventar causas. La migración respeta esa decisión: solo añade metadatos técnicos de identidad/versión a los registros anteriores; no cambia sus columnas originales, detalle ni sello.

## Diagnóstico confirmado

Se revisaron emisores RF-75/78/79, puerto/entidad, consolidación, router, fábricas, repositorios, ORM/schema, exportación, migraciones, triggers, hash, permisos y pruebas.

1. ConsolidarCicloUseCase copiaba es_reporte_potencialmente_incompleto a registro_incompleto sin causa. Son conceptos diferentes: una provisión puede estar pendiente de conciliación aun cuando el evento tenga todos sus datos. El puerto tampoco completaba una causa ausente en los eventos realmente marcados como incompletos.
2. PUT/PATCH/DELETE recibían el 405 de Starlette, fuera del flujo de auditoría del módulo.
3. No existía UUID de emisión en el puerto, tabla, ORM o respuesta. El entero serial identifica la fila, pero no sirve para reconocer la reentrega del mismo evento.

La reproducción unitaria anterior a los cambios falla por detalle_causa=None y por falta del UUID. Se conservó el JUnit de reproducción. No se ejecutaron escrituras en TEST/DEV oficiales.

## Corrección de incompletos

- EventoAuditoriaSuministro genera una causa para nuevos eventos marcados como incompletos. Lista únicamente ausencias acreditables del contexto disponible: activo, ciclo y, para los tipos financieros aplicables, costo afectado.
- Conserva una causa proporcionada por el emisor y agrega las ausencias verificadas. Si no hay otras ausencias identificables, informa que falta el detalle de la causa y que el emisor no identificó otros datos; no inventa valores.
- El consolidado devuelve las razones concretas de conciliación pendiente: diferencia con el acumulado, diferencia con lo provisionado o eventos retenidos tras intentos de entrega.
- La auditoría de consolidación conserva ese diagnóstico legible sin marcar falsamente campos ausentes. El indicador propio del reporte se mantiene.
- Una restricción CHECK protege nuevos INSERT incompletos sin causa, también fuera del puerto. Se agrega NOT VALID para respetar los registros antiguos que ya incumplían la regla. No equivale a desactivar la restricción para datos nuevos.

No se amplía esta incidencia a una reimplementación del catálogo completo de campos mínimos de todos los eventos de RF-80.

## Intentos de modificación

Una guarda interna para POST/PUT/PATCH/DELETE sobre /suministros/auditoria/{id} ejecuta un caso de uso de seguridad y devuelve 405 con Allow: GET. Está excluida de OpenAPI porque no ofrece operaciones de modificación; nunca consulta ni altera el objetivo y descarta el cuerpo recibido.

El caso de uso emite exactamente un evento RECHAZADO por intento autenticado, con UUID, actor y diagnóstico. Reutiliza tipos genéricos INSERT/UPDATE/DELETE existentes; no introduce enums ni permisos de edición. Un actor sin permiso para leer la bitácora puede recibir el rechazo y quedar trazado, pero su GET sigue denegado. Un ID inexistente recibe el mismo 405 sin revelar existencia. JWT ausente recibe 401.

La guarda se ubica después de las rutas de lectura para conservar Allow: GET también ante métodos no soportados, como OPTIONS. Los filtros, lectores autorizados y rutas GET existentes se mantienen.

Si falla la auditoría, intenta rollback, conserva el 405 y registra un diagnóstico seguro con usuario y UUID, sin SQL ni cuerpo de la petición. En esa condición no se garantiza un evento persistido. No se agrega un resguardo durable ni se afirma entrega externa durante una caída de BD.

## UUID y deduplicación

- Cada nuevo objeto de emisión recibe id_evento_m05 antes de persistirlo; el mismo objeto o una reentrega con ese UUID conserva su identidad.
- El repositorio usa INSERT ... ON CONFLICT DO NOTHING sobre la restricción única del UUID. No hace rollback por una reentrega, no sobrescribe el primer evento y mantiene las demás escrituras de la transacción.
- Los emisores SQL de M05 reciben UUID por DEFAULT de PostgreSQL antes del sellado del registro. Se verifica el flujo real de consumo RF-75 y los eventos Python RF-78/79.
- El UUID y version_hash_integridad se transportan por entidad de lectura, listado, detalle y exportación.
- La garantía probada es la deduplicación local de la bitácora M05. No se implementa ni acredita un transporte, ACK o tabla de eventos procesados en un repositorio M12 externo. No se inventa una tabla alternativa para afirmar esa integración.

La identidad generada para filas antiguas es un identificador técnico asignado al migrar; no se presenta como evidencia de un UUID emitido originalmente. No se eliminan ni se identifican automáticamente duplicados históricos.

## Migración e integridad

Nueva revisión: d96480a11e01. Dependencia: b7e2d94c1a68.

- UUID NOT NULL, DEFAULT gen_random_uuid() y restricción única.
- version_hash_integridad=1 para registros anteriores; DEFAULT y sellado de versión 2 para nuevas emisiones.
- Versión 1 verifica la proyección original, excluyendo los metadatos incorporados después. No se recalculan hashes antiguos.
- Versión 2 incorpora todas las columnas actuales excepto hash_integridad, con la serialización y orden alfabético existentes.
- La función de hash genérica usada por otras tablas no se altera; auditoría recibe su función de sellado propia.
- Trigger BEFORE UPDATE/DELETE impide alterar la bitácora. DELETE ya estaba denegado al rol de API por ACL; esa protección se conserva.
- El downgrade se detiene antes de retirar identidad si existen eventos de versión 2. Se prueba el rechazo sin pérdida de datos.

La migración y los emisores compatibles deben desplegarse de forma coordinada: el ORM necesita las nuevas columnas y los INSERT incompletos nuevos deben cumplir la causa. Revisar las heads de Alembic al integrar. No se ejecutó la migración sobre bases oficiales.

## Pruebas y resultados

| Grupo distinto | Aprobadas | Fallidas | Omitidas |
|---|---:|---:|---:|
| tests/supplies: dominio y fakes | 32 | 0 | 0 |
| Integración PostgreSQL/HTTP | 21 | 0 | 0 |
| Total sin sumar repeticiones | 53 | 0 | 0 |

Las 32 incluyen 14 regresiones nuevas y 18 existentes. La integración se verificó por grupos: 20 casos en la corrida completa y 19 en la validación HTTP final, con 18 compartidos; 21 casos distintos. Los grupos aislados de migración y concurrencia no se repiten por un cambio exclusivo de precedencia de rutas.

Cobertura real:

- Downgrade/upgrade en una base efímera: conservación exacta de todas las columnas originales y hash de un evento antiguo con causa desconocida; UUID/versión nuevos y verificación del sello legado.
- Rechazo de downgrade después de emitir versión 2, sin retirar columnas ni datos.
- Nuevo incompleto con causa, UUID y versión consultables por lista y detalle.
- PUT/PATCH/DELETE/POST autenticados: 405, un RECHAZADO, cuerpo sensible no registrado y objetivo/hash intactos.
- Actor sin lectura, objetivo inexistente, JWT ausente, OpenAPI solo GET y Allow: GET.
- Reentrega con el mismo UUID, incluso con contenido diferente: prevalece el primer registro y otras escrituras no se revierten.
- Dos transacciones concurrentes reales bajo sgpmp_app: exactamente una fila para el mismo UUID.
- Hash recalculado independientemente sobre todas las columnas nuevas y comprobación de que variar el UUID cambia el sello.
- UPDATE bloqueado por trigger bajo sgpmp_app; DELETE bloqueado por ACL de API y por trigger ante el propietario. Este último actor se usa solo para comprobar integridad de BD, nunca para representar HTTP.
- INSERT nuevo incompleto sin causa rechazado por CHECK.
- Exportación para Contador/Revisor, fallo controlado de auditoría y rollback exterior del sandbox.
- RF-78 → consolidación RF-79 con un intento retenido preparado de forma controlada: reporte pendiente conservado y evento de auditoría completo con diagnóstico concreto.
- Emisor de trigger RF-75: identidad y sello nuevos sin pasar UUID por el puerto Python.

## Entorno y límites

PostgreSQL 18 local, sgpmp_inc964_test en 127.0.0.1:55429, con TEST_DATABASE_URL exclusivo y TEST_ROL_APP=sgpmp_app. Migración y concurrencia usan dos bases efímeras independientes mediante el fixture existente; se eliminan al terminar cada caso. No se desactivan restricciones, RLS ni triggers. Se mantiene use_insertmanyvalues=False y el shim fcntl solo en los lanzadores temporales de pytest.

Las ACL locales preparan el rol API para las dependencias del fixture; no acreditan las desplegadas. Las tablas M05 inspeccionadas no tienen RLS en esta base de dev; no se atribuye al cambio un aislamiento por filas nuevo. Se conservan RBAC y alcance de los módulos consultados.

El caso de consolidación prepara por SQL local un intento de outbox pendiente; no prueba la entrega de red a M06. No se modifican esos criterios de entrega. No se valida una implementación externa de M12 ni un despliegue oficial. La suite mantiene el aviso existente de Starlette/httpx.

Al finalizar se eliminó únicamente sgpmp_inc964_test; las bases efímeras ya habían sido retiradas por sus fixtures. Se verificó que las demás bases locales permanecieran intactas y se detuvo el clúster iniciado para esta validación, conservando logs y evidencias.

Pendiente: migración y despliegue coordinado, reejecución de G39 en TEST y tratamiento separado de los registros históricos sin evidencia. La no remediación del contenido histórico fue confirmada por el usuario.

## Entrega

12 archivos de producción, una migración, dos archivos de pruebas y dos informes. Todos los archivos de código modificados incluyen la tabla de seguimiento con fecha real, identidad Git consultada y tarea/RF. Se preservan filas anteriores y archivos locales ajenos.

Evidencias temporales excluidas del commit: .pytest_cache/inc964_reproduccion.xml, inc964_unit.xml, inc964_integracion.xml, inc964_integracion_http_final.xml, inc964_preflight.json, inc964_evidencia_final.json, inc964_postgres.log y lanzadores inc964_*.py.

No se realiza commit, push, merge ni publicación de PR sin la instrucción correspondiente del usuario para esta entrega.
