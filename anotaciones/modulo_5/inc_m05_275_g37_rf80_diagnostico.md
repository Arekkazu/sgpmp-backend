# INC-M05-275-G37 · RF-80 — Auditoría de rechazos de costeo directo

Fecha: 2026-11-08. Responsable Git consultado: Leandro.
Issue: [#960](https://github.com/Arekkazu/sgpmp-backend/issues/960).
Rama: `fix/inc-m05-275-g37-auditoria-rechazos-rf80`.
Base de dev actualizada antes de crear la rama: `3251d78d2c5822624dde988a94a37331610d1cef`.

## Diagnóstico confirmado

RF-80 CA-1 exige trazabilidad de operaciones exitosas y fallidas de RF-78/79/81. QA reporta específicamente el rechazo de POST /suministros/costeo-directo después del cierre del ciclo: HTTP 409 CICLO_NO_ACTIVO, sin evento RECHAZADO/FALLIDO en la bitácora de M05.

Se revisaron DTO, router, fábrica, caso de uso, puertos, adaptadores M02, repositorios, ORM, migraciones, enums, triggers, RBAC y fixture transaccional. En dev, las validaciones de negocio salen antes de la persistencia, sin invocar auditoría. Incluso dentro de la persistencia, AppError provoca rollback y propagación sin auditar el rechazo. El método _registrar_fallo solamente cubre agotamiento de reintentos técnicos.

La regresión inicial con fakes reprodujo tres omisiones: ciclo no activo, duplicado y justificación faltante. Las tres fallaban al comprobar la emisión del evento. Esto prueba la omisión en código; la persistencia se verificó posteriormente con PostgreSQL real.

## Corrección implementada

1. El caso de uso intercepta BusinessRuleError y ConflictError del registro directo, preservando la misma excepción y el contrato HTTP vigente.
2. Revierte la transacción del intento antes de registrar su rechazo. Los costos, ledger, acumulado, eventos de éxito y outbox parciales no se confirman.
3. Consulta el activo mediante ActivoConsultaPort/ActivoM02Adapter con la identidad existente de la sesión. Solo vincula una FK si el activo es visible. Para un objetivo oculto o inexistente conserva el ID solicitado en el detalle del intento, sin asociarle una FK ajena ni inventar una fase.
4. Registra REGISTRO_FALLIDO con resultado RECHAZADO, usuario, motivo legible, UUID de la solicitud y cero reintentos. Captura el contexto de ciclo/fase ya obtenido antes del rechazo; no busca una fase diferente tras el rollback. Cuando no hay fase acreditada, marca registro_incompleto y lo explica.
5. Confirma únicamente el evento de rechazo en una nueva transacción del caso de uso. Los repositorios mantienen flush(), y el hash, la retención y los timestamps siguen a cargo del mecanismo existente.
6. La fábrica inyecta el adaptador de consulta de activos. No se agrega SQL al caso de uso, ni lógica de negocio al router.

Se preservan la prioridad de idempotencia y las respuestas YA_PROCESADO/YA_ACUMULADO, los errores originales, las reglas de precio/fecha/costo y los reintentos técnicos existentes. No se amplía el alcance a otros incidentes de reintentos o a todos los rechazos de RF-79/81.

## Persistencia y seguridad

No se requiere migración. REGISTRO_FALLIDO y RECHAZADO ya existen en sus enums; el puerto y la tabla admiten el contexto opcional usado. No se cambian permisos, políticas, triggers, restricciones ni el traductor de errores.

La prueba usa sgpmp_app, sin superusuario ni BYPASSRLS durante HTTP. M02 activos/gestiones y M09 fincas/infraestructuras tienen RLS y FORCE RLS en la base migrada. Las tablas de M05 inspeccionadas no tienen RLS en esta revisión de dev; no se afirma que esta corrección agregue ese aislamiento. Se conserva el RBAC y se verifica que la nueva referencia al activo respete la visibilidad de M02.

GET /suministros/auditoria conserva sus lectores autorizados (Administrador, Contador y Revisor Fiscal). El Productor puede intentar un registro según su permiso de creación, pero no adquiere acceso a la bitácora. JWT, permisos y errores de formato rechazados antes del caso de uso no se convierten artificialmente en rechazos de negocio de RF-78.

## Pruebas finales

| Grupo distinto | Aprobadas | Fallidas | Omitidas |
|---|---:|---:|---:|
| tests/supplies, con fakes y dominio | 39 | 0 | 0 |
| Nueva integración HTTP/PostgreSQL de #960 | 14 | 0 | 0 |
| Total sin sumar repeticiones | 53 | 0 | 0 |

De las 39 pruebas unitarias, 21 son regresiones nuevas de este incidente y 18 pertenecían a la suite de suministros. Las corridas de reproducción y las repeticiones de verificación no se suman al total.

La integración verifica:

- Registro válido, cierre de fase, rechazo 409 CICLO_NO_ACTIVO y exactamente un evento RECHAZADO consultable inmediatamente por lista, filtros y detalle, con actor, fecha, motivo y hash.
- No modificación de costos, acumulado ni outbox por el rechazo; UUID de un intento rechazado disponible para un registro posterior válido.
- Reenvío idempotente de una operación ya procesada después del cierre, sin crear rechazo falso.
- Rechazos 422 por justificación, costo, tipo y fuente de medicamento; duplicado 409 y restricción UNIQUE real, manteniendo las restricciones activas.
- Conflicto controlado después de escribir ledger, auditoría positiva y outbox: rollback de todo lo parcial y persistencia de un único rechazo.
- Activo inexistente y activo de otra finca bajo el Productor; ninguna FK ajena en la evidencia de rechazo.
- JWT, RBAC, DTO y denegación del acceso del Productor a la auditoría.
- Fallo controlado de auditoría después de flush: conservación del 409, rollback de la fila incompleta y log seguro.
- Rollback exterior equivalente al sandbox: el commit interno de auditoría no impide revertir toda la corrida.
- Secuencia RF-78 → cierre/consolidado RF-79 → historial RF-81 → nuevo rechazo: se conservan los eventos exitosos y el consolidado.

La última medición local desde el POST hasta obtener el evento por lista fue de 0.876 s (< 2 s). Es una medición de esta ejecución local, no un benchmark del ambiente oficial.

La prueba UNIQUE omite únicamente la preconsulta de duplicados para alcanzar el constraint real; no es una prueba de concurrencia entre procesos. El cierre de fase se prepara mediante SQL local con triggers activos; el consolidado y el historial se ejecutan mediante HTTP.

## Entorno y evidencias

PostgreSQL 18 local en 127.0.0.1:55429; base exclusiva sgpmp_inc960_test, migrada desde cero hasta b7e2d94c1a68. TEST_DATABASE_URL apunta solamente a esa base y TEST_ROL_APP=sgpmp_app. Se conservaron las protecciones del fixture y use_insertmanyvalues=False.

La preparación local completa ACL de lectura/escritura para el rol de API. Al ampliar la regresión a RF-81 se detectó que faltaba SELECT sobre modulo9.ciclos_productivos en ese entorno recién preparado; se añadió únicamente al lanzador local, sin migración ni cambio de RLS. Ese resultado no acredita el estado de ACL de TEST o DEV.

El shim fcntl se usa solo en los lanzadores de pytest por la dependencia existente del SDK en Windows. No se modifica producción por esa limitación.

Evidencias temporales excluidas del commit:

- .pytest_cache/inc960_unit.xml
- .pytest_cache/inc960_integracion.xml (propiedad segundos_post_y_lectura para comprobar el límite local de 2 s)
- .pytest_cache/inc960_preflight.json
- .pytest_cache/inc960_bd_errores.jsonl (incluye fallos provocados durante la regresión)
- .pytest_cache/inc960_evidencia_final.json
- .pytest_cache/inc960_postgres.log y lanzadores inc960_*.py

Al terminar se eliminó exclusivamente sgpmp_inc960_test y se detuvo el clúster local iniciado para la validación. Se verificó que las demás bases locales permanecieran intactas; se conservaron logs, lanzadores y evidencias.

No se ejecutaron escrituras ni despliegues en TEST o DEV. La validación en el TEST oficial y la reejecución del checkpoint A02 de QA quedan pendientes tras integrar y desplegar.

## Límite ante indisponibilidad

Si no se puede consultar el contexto o persistir/confirmar la auditoría, se intenta rollback, se conserva el rechazo de negocio original y se registra un diagnóstico seguro con usuario, UUID y código, sin SQL ni secretos. En ese caso no hay garantía de evento consultable en la bitácora; no se agrega una cola durable ni se afirma cumplimiento de persistencia durante una caída de BD. Esa limitación está probada y no se disfraza como éxito.

## Archivos de la entrega

- src/supplies/application/use_cases/costeo_suministros/registrar_suministro_directo_use_case.py
- src/supplies/infrastructure/factories/costeo_suministros_factory.py
- tests/supplies/test_inc_m05_275_g37_auditoria_rechazos.py
- tests/integration/test_inc_m05_275_g37_auditoria_rechazos_integration.py
- anotaciones/modulo_5/inc_m05_275_g37_rf80_diagnostico.md
- anotaciones/modulo_5/inc_m05_275_g37_pr_preparado.md

Los cuatro archivos de código conservan la tabla de seguimiento con fecha real e identidad Git consultada. Los archivos locales ajenos se preservan. Commit, push y publicación de PR requieren la instrucción correspondiente del usuario para esta entrega.
