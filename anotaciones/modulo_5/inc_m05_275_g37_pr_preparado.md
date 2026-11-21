# RF-80 — Auditar rechazos de costeo directo · INC-M05-275-G37

## Desvío identificado

| RF exige | Antes | Ahora |
|---|---|---|
| RF-80 CA-1: trazabilidad de operaciones fallidas | POST /suministros/costeo-directo devolvía 409 CICLO_NO_ACTIVO sin evento | Conserva el 409 y registra un evento REGISTRO_FALLIDO / RECHAZADO con usuario, fecha y motivo |
| Consultar el intento rechazado | El conteo de auditoría no cambiaba | El evento aparece por lista, filtros y detalle mediante el lector autorizado |
| Un rechazo no confirma costos | Rollback sin evidencia del rechazo | Rollback del intento y confirmación separada de su auditoría |

Referencias: issue #960, INC-M05-275-G37, RF-78, RF-80 CA-1 y TC-M05-G37 / TC-M05-026.1 / checkpoint A02.

Closes #960

## Causa raíz

Las validaciones de negocio salían sin invocar AuditoriaSuministroPort. _registrar_fallo solo cubría el agotamiento de reintentos técnicos; tampoco se auditaban los conflictos de negocio que ocurrían después de iniciar la persistencia.

## Cambios implementados

- Interceptar BusinessRuleError/ConflictError del registro directo, revertir el intento y emitir un único evento RECHAZADO sin reintentos de negocio.
- Conservar el error y los códigos HTTP existentes, así como el registro válido y la prioridad de idempotencia.
- Añadir motivo legible y UUID de la solicitud. Asociar activo y ciclo/fase únicamente cuando se hayan acreditado; consultar el activo mediante el puerto existente y la identidad RLS de la sesión.
- Inyectar ActivoM02Adapter en la fábrica; mantener commits/rollbacks en el caso de uso y flush() en los repositorios.
- Registrar un diagnóstico seguro si falla la auditoría, sin reemplazar el rechazo original ni afirmar que se persistió.

## Migración

No requiere migración. Se reutilizan REGISTRO_FALLIDO, RECHAZADO, columnas, hash y política de retención existentes. No se modifican RBAC, RLS ni triggers.

## Contrato resultante

POST /suministros/costeo-directo mantiene 200 en registro/idempotencia y sus errores 409/422 vigentes. Un rechazo de negocio genera un evento consultable sin confirmar ledger, acumulado ni outbox parcial. Si no hay fase abierta o el activo no es visible, no se inventan referencias: el evento indica contexto incompleto.

GET /suministros/auditoria mantiene su RBAC. El Productor no obtiene acceso nuevo a la bitácora. No cambian los schemas HTTP ni se exponen SQL o mensajes internos en el nuevo detalle.

## Pruebas realizadas

| Grupo | Aprobadas | Fallidas | Omitidas |
|---|---:|---:|---:|
| tests/supplies (21 nuevas y 18 existentes; fakes/dominio) | 39 | 0 | 0 |
| Integración HTTP con PostgreSQL 18 real | 14 | 0 | 0 |
| Total distinto | 53 | 0 | 0 |

La integración usa sgpmp_app sin superusuario/BYPASSRLS, restricciones y triggers activos. Cubre lista/detalle/filtros del rechazo en menos de 2 s en la medición local, idempotencia, rechazo 422, duplicado previo y UNIQUE real, rollback de escrituras parciales, aislamiento del activo por finca, JWT/RBAC, fallo de auditoría, rollback exterior del sandbox y conservación del consolidado e historial RF-79/81.

El conflicto tardío y la indisponibilidad de auditoría se provocan de forma controlada, con PostgreSQL real. No se afirma haber probado concurrencia entre procesos ni dispositivos/despliegue.

## Integración con sgpmp_dev

Base: dev actualizada a 3251d78d2c5822624dde988a94a37331610d1cef antes de crear fix/inc-m05-275-g37-auditoria-rechazos-rf80. Validación en base local exclusiva, migrada desde cero a b7e2d94c1a68. No se ejecutó DDL/DML ni se desplegó en DEV o TEST oficiales.

## Dependencias y pendientes

- Reejecutar A02 de TC-M05-G37 en TEST tras integrar y desplegar; no se presenta la prueba local como validación oficial.
- La integración local completa las ACL del rol API, incluida la lectura del catálogo de ciclos para RF-81; no acredita las ACL desplegadas.
- Si la BD/auditoría no está disponible, se preserva el rechazo y queda un diagnóstico en log; no se incorpora resguardo durable en esta incidencia.
- Alcance: rechazos de negocio del registro directo RF-78. No se amplían las reglas de RF-79/81 ni se cambian los reintentos técnicos existentes.
- No depende de ramas de correcciones previas pendientes de integrar.

## Alcance del commit

Entrega prevista: dos archivos de producción, dos archivos de pruebas y dos informes Markdown. Excluir evidencias temporales .pytest_cache y archivos locales ajenos. Descripción preparada; no implica commit, push ni PR publicado.

## Revisión contra dev

La rama nace de dev actualizada, sin arrastrar correcciones de otra rama. Conserva las capas hexagonales, los contratos HTTP, la prioridad de idempotencia, las restricciones de persistencia y la autorización existente.
