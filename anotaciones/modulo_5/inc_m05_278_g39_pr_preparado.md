# RF-80 — Corregir completitud, inmutabilidad e identidad de auditoría · INC-M05-278-G39

## Desvío identificado

| RF exige | Antes | Ahora |
|---|---|---|
| CA-12: explicar datos ausentes en eventos incompletos | registro_incompleto=true podía persistir sin causa | Nuevos eventos documentan ausencias verificadas; CHECK impide persistir un nuevo incompleto sin causa |
| Inmutabilidad con trazabilidad de intentos | PUT/PATCH/DELETE devolvían 405 sin auditoría | Intento autenticado devuelve 405 y genera un RECHAZADO sin alterar el objetivo |
| Restricción 9: identidad de emisión y deduplicación | Solo existía la PK serial de la fila | UUID de emisión, unicidad y reentrega sin duplicar ni sobrescribir |

Referencias: #964, INC-M05-278-G39, RF-80 CA-2/CA-12/CA-14 y TC-M05-G39 A02/B02/C01. B03 figura aprobado en el adjunto; no se incorpora como cuarto defecto.

Closes #964

## Causa raíz

La consolidación confundía un reporte pendiente de conciliación con un evento de auditoría al que le faltan campos. El puerto no completaba la causa ausente. El framework rechazaba los métodos de modificación antes del flujo de auditoría. Tampoco existía identidad de emisión distinta del entero serial.

## Cambios implementados

- Documentar ausencias acreditables en los nuevos eventos incompletos, preservando causas existentes.
- Conservar las razones de conciliación del reporte sin marcar falsamente su evento como incompleto.
- Agregar una guarda interna, fuera de OpenAPI, que registra intentos autenticados y devuelve 405/Allow: GET; no lee ni modifica el objetivo ni registra el cuerpo recibido.
- Emitir UUID desde el puerto; los emisores SQL reciben su identidad por DEFAULT de BD.
- Deduplicar con ON CONFLICT DO NOTHING, sin sobrescribir el primer evento ni revertir otras escrituras.
- Exponer UUID y versión de hash en consulta, detalle y exportación.

## Migración

Revisión d96480a11e01 sobre b7e2d94c1a68:

- UUID obligatorio/único y versión de hash.
- Sello versión 1 preservado para registros antiguos y versión 2 para nuevas emisiones, incluyendo las columnas actuales.
- CHECK de causa para nuevos incompletos, agregado NOT VALID para conservar el historial previo.
- Trigger de inmutabilidad ante UPDATE/DELETE.
- Downgrade protegido si ya existen emisiones versión 2.

No se modifican columnas originales ni hashes históricos. El usuario confirmó no inventar causas antiguas. Los UUID asignados al historial son metadatos técnicos de migración, no prueba de una emisión original.

## Contrato resultante

Listados y detalles agregan id_evento_m05 y version_hash_integridad. GET conserva permisos y comportamiento. POST/PUT/PATCH/DELETE sobre un ID reciben 405 y un evento RECHAZADO para un actor autenticado; no existe una operación pública para modificar la bitácora. JWT ausente recibe 401.

Un actor sin permiso de lectura no obtiene datos del objetivo. Un ID inexistente recibe el mismo rechazo. Si falla la auditoría, se conserva el 405 y queda un diagnóstico seguro en log; no se afirma persistencia durante la indisponibilidad.

## Pruebas realizadas

| Grupo | Aprobadas | Fallidas | Omitidas |
|---|---:|---:|---:|
| tests/supplies: 14 nuevas y 18 existentes | 32 | 0 | 0 |
| PostgreSQL/HTTP, casos distintos | 21 | 0 | 0 |
| Total distinto | 53 | 0 | 0 |

Incluye conservación del hash legado durante migración, downgrade protegido, causa/UUID en lista y detalle, 405 con un evento por intento, inmutabilidad de objetivo, OpenAPI/Allow, JWT/RBAC, reentrega sin pérdida de otras escrituras, dos transacciones concurrentes reales, recálculo independiente del hash, CHECK, exportación, fallos controlados y rollback exterior.

Se verifican emisores Python RF-78/79 y trigger RF-75. HTTP y concurrencia usan sgpmp_app sin superusuario/BYPASSRLS. El propietario se usa únicamente para comprobar el trigger de integridad de BD, no como actor normal de API.

## Integración con sgpmp_dev

Rama creada desde dev actualizada a 3251d78d2c5822624dde988a94a37331610d1cef:

`fix/inc-m05-278-g39-integridad-auditoria-rf80`

Validación en PostgreSQL 18 local exclusivo y bases efímeras independientes para migración/concurrencia. Sin DDL/DML ni despliegue en TEST/DEV oficiales. Las ACL locales no acreditan las desplegadas.

## Dependencias y pendientes

- Desplegar migración y emisores compatibles de forma coordinada y revisar heads de Alembic al integrar.
- Reejecutar G39 en TEST tras desplegar.
- Conservar históricos sin causa documentada, conforme a la decisión del usuario; no se fabrican datos ni se eliminan duplicados históricos.
- La deduplicación verificada es local en M05. No acredita transporte, ACK ni tabla de procesados en un M12 externo.
- No incorpora cambios de #958, #960, #961 o #963.

## Alcance del commit

Entrega prevista: 12 archivos de producción, una migración, dos archivos de pruebas y dos informes. Excluir .pytest_cache y archivos locales ajenos. Descripción preparada; no implica commit, push ni PR publicado.

## Revisión contra dev

Se conservan las capas: la guarda delega al caso de uso, los commits/rollbacks permanecen en aplicación y el repositorio usa flush sin commit. No se introducen permisos de edición ni se altera la función de hash genérica utilizada por otras tablas.
