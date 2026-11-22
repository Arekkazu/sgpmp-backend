# INC-M03-133-G170 · RF-62 — Reevaluación explícita completa (#688)

Fecha: 2026-10-27. Identidad Git consultada: Leandro.
Rama: fix/inc-m03-133-g170-reevaluacion-rf62.
Base: dev/origin/dev actualizado al iniciar, 5691096b8497b9fc445abf0a7579409c8de6550f.

## Diagnóstico y evidencia QA

La incidencia pertenece a Desarrollo Backend y se reproduce en la base de esta rama. SolicitarReevaluacionUseCase únicamente recorría las vigentes para marcarlas SUPERADA, confirmaba esa transacción y devolvía evaluaciones_creadas=0. Sus dependencias de telemetría, parámetros y motor no se utilizaban. La auditoría se ejecutaba después del commit, sin parámetros completos y silenciando errores. No existía regeneración asíncrona que completara el trabajo.

Se leyeron los adjuntos resultado_TC-M03-G170.md/.json/.html. El resumen documenta seis superadas y cero creadas. El HTML presenta dos fallos de preflight y una aserción de reevaluación que solo documenta el cero; no acredita por sí mismo la corrección funcional. Su referencia a nuevas ACTIVA es legacy: el catálogo del modelo es VIGENTE/SUPERADA. Las pruebas nuevas verifican esos valores oficiales.

Referencias funcionales: RF-62 Restricción 9, CA-15/CA-16, RNF-07/RNF-08; TC-324/325/326 de G170; acuerdo AIOT-DEV-03 DEV-02, aptitud oficial en telemetria_calidad e inmutabilidad del original. No se modifica telemetrias.

## Decisiones confirmadas

El usuario confirmó conservar HTTP 200 con los contadores finales y resolver el lote completo de forma atómica. El procesamiento asíncrono de RNF-08 queda como pendiente separado: esta entrega no acredita 1.000 lecturas/minuto ni trabajo diferido.

No hay un canal implementado de aviso de reevaluación hacia M04/M06. El usuario confirmó guardar calidad y auditar los avisos pendientes con los IDs de las evaluaciones nuevas, sin afirmar una notificación efectiva. El evento global queda PARCIAL por ese pendiente; los contadores HTTP representan evaluaciones realmente persistidas.

## Gaps previos de BD y RBAC

| Comprobación | Hallazgo / decisión |
|---|---|
| Columnas de calidad y auditoría | Existen motivo_reevaluacion, id_evaluacion_superada, version_evaluacion y snapshots; no hace falta migración |
| Restricciones e índices reales | FK de sustitución y lectura; índices de lectura/sensor/clasificación; sin índice único parcial de VIGENTE |
| Concurrencia | Reutilizar pg_advisory_xact_lock con clave rf62:evaluacion:{id}, igual al motor manual/postcommit |
| Inmutabilidad | Los triggers de telemetría se conservan; sin UPDATE del original |
| RLS/FORCE RLS | No se cambian políticas ni roles; sensores conserva su aislamiento |
| RBAC local de recurso 38 | Administrador e Ingeniero comparten ejecución para evaluación individual; el lote exige además el Administrador protegido, resuelto dinámicamente con el adaptador existente |
| Auditoría | El repositorio best-effort no basta: el caso de uso exige ID persistido y revierte el lote si falta |

La inspección oficial fue de solo lectura (transaction_read_only=on, sgpmp_dev/member_dev), con columnas, restricciones, índices, triggers, políticas y privilegios. Las consultas de permisos y alembic_version fueron denegadas con 42501; no se eludieron. Los roles de aplicación inspeccionados disponían de SELECT/INSERT/UPDATE de calidad y de INSERT de auditoría. El RBAC se verificó además en el entorno local migrado; no se certifica la tabla oficial que no pudo consultarse.

El perfil local sgpmp_app requirió SELECT de estados_cuentas para el detalle del usuario que ya consultaba la ruta. En la base independiente de concurrencia se concedió USAGE de modulo1 para resolver la identidad de servicio existente. Son preparación de pruebas locales, sin alterar permisos oficiales ni desactivar RLS. El propietario se reservó a preparar migraciones y datos; las operaciones HTTP y los lotes concurrentes usan sgpmp_app.

## Flujo resultante

1. El router exige JWT, permiso dinámico 38/E y Administrador protegido; inyecta contexto y alertas reales.
2. Se validan las correcciones locales y se seleccionan las vigentes del sensor/rango con el contrato existente: timestamp_evaluacion inclusivo.
3. Se bloquean todos los IDs de lectura en orden ascendente. Tras esperar un bloqueo, se relee la vigente; no se conserva una versión obsoleta seleccionada antes de esperar.
4. Por cada lectura, el motor existente recalcula con sus datos originales y los parámetros corregidos, sin commit individual. Guarda una nueva VIGENTE enlazada y supera la anterior.
5. Se guarda la evidencia individual y el evento completo del lote en RF-63 con usuario, causa, rango, parámetros anteriores/nuevos, sustituciones, conteos y avisos pendientes.
6. Se realiza un solo commit del lote. Un fallo de cálculo, persistencia, auditoría o commit revierte todas las sustituciones. Si RF-60 obliga a omitir una lectura, se rechaza el lote con 422 y se conservan las vigentes anteriores.

Los caminos manual y postcommit ordinarios mantienen su confirmación existente. No se copian evaluaciones anteriores para simular un recálculo. El caso de seis lecturas con drift falso recalcula el índice con offset=0/ganancia=1, crea seis versiones nuevas y conserva las lecturas originales completas.

## Parámetros, historia y versión

parametros_correctos conserva su formato dict opcional. Admite offset/ganancia y los campos del motor: k, M, N, P, umbral_drift, umbral_drift_significativo y frecuencia_muestreo_min. Se rechazan claves desconocidas, booleanos/cadenas numéricas, no finitos, ganancia/k no positivos, ventanas inválidas y M/P mayores que N. La corrección es local a la solicitud; no escribe M09. Una calibración parcial requiere que el otro componente sea conocido en el snapshot original. Sin correcciones se usa la configuración vigente y el snapshot original.

Cada nueva evaluación lleva causa, ID de la superada y version_evaluacion. Se conserva la causa de creación de reevaluaciones históricas al superarlas de nuevo. La versión es una huella rf62:<sha256> de componentes persistidos en parametros_aplicados.version_evaluacion_componentes (versiones conocidas de límites/calibración, snapshot de calibración y parámetros estadísticos aplicados). Identifica componentes, no un número consecutivo de ejecuciones. No se inventan versiones históricas de límites o calibración ausentes: se registran null. Esto no resuelve el proveedor histórico de límites M09 ni el versionado general de evaluaciones fuera de la solicitud explícita.

La corrección de calibración afecta el cálculo y snapshot de RF-62. No recalibra el sensor ni sobrescribe valor_ajustado, estado_calidad o parametros_calibracion del original; se conservan las reglas heredadas de RF-53.

## Pruebas

| Grupo final | Aprobadas | Fallidas | Omitidas |
|---|---:|---:|---:|
| Unitarias y contrato HTTP de telemetría | 731 | 0 | 0 |
| Integración PostgreSQL 18 real | 42 | 0 | 0 |
| Total distinto | 773 | 0 | 0 |

Incluye 16 unitarias y 21 reales nuevas de #688. PostgreSQL añade 8 regresiones del motor #632, 12 de aptitud DEV-02 y una de omisión normal por inactividad. Los XML finales de 41 casos y el independiente de concurrencia se combinan sin duplicados. Las repeticiones focalizadas para comprobar reintento se verifican aparte sin sumarlas otra vez.

Se demostró antes de corregir el caso de una superada y cero creadas. La ejecución inicial en sandbox tuvo un error de directorio temporal de Windows; se utilizó un basetemp exclusivo local para la reproducción funcional. En pruebas reales se corrigieron problemas de preparación: JSON SQL literal interpretado como parámetros enlazados, permisos locales de lectura del detalle de usuario y USAGE del esquema de identidad en concurrencia. La prueba de FK usa el 400 REFERENCIA_INVALIDA del traductor existente; no se cambió producción para forzar otro código. Al añadir el reintento, se acotó la restauración del fallo simulado con monkeypatch.context() para conservar la clave JWT del fixture; el undo global de la preparación inicial invalidaba el segundo token.

Cobertura: seis sustituciones reales, índice/flags corregidos, fuente inmutable, consulta de vigentes, parámetros locales sin cambios M09, snapshots y evento completo con hash, JWT/RBAC, causa incompleta, rangos, cadena sucesiva con causas distintas, fallo inducido después de la segunda escritura, violación real de FK, auditoría sin ID, fallo de commit e inactividad. Concurrencia real mediante dos conexiones y commits en una base independiente; M09 aporta parámetros de prueba en ese caso específico, mientras motor, locks y repositorios son reales. Las pruebas HTTP usan adaptadores M09 reales.

No se ejecutó Newman ni se certifica toda G170 como aprobada: los adjuntos son evidencia de entrada. El rechazo de preferencias de TC-325d fue un falso positivo de la evidencia original: devolvió SIN_EVALUACIONES_EN_RANGO después de vaciar las vigentes, no una validación de preferencias. Se documenta la ausencia de una regla formal para interpretar texto libre; no se introduce una heurística nueva ni se atribuye esa validación a esta corrección. Los extremos iguales no tienen una prohibición implementada: una coincidencia exacta puede reevaluarse, conservando la consulta inclusiva existente.

Evidencias ignoradas en .pytest_cache: g34_antes_unit.xml/.log, g34_unit_final.xml/.log, g34_pg_final.xml/.log, g34_pg_concurrencia.xml/.log, g34_pg_reintento.xml/.log, g34_resumen_final.json y scripts/logs de preparación e inspección. El shim fcntl permanece solo en los lanzadores Windows. Las advertencias existentes de Starlette/httpx y OperationID duplicado se informan sin contarlas como fallos.

## Entrega y pendientes

No hay migración nueva ni DDL/DML oficial. La base independiente de concurrencia fue eliminada por su fixture. Se retiró exclusivamente sgpmp_g34_test comprobando que las otras bases locales se conservaran, y se detuvo el clúster. Evidencia: g34_cierre_bd.log, g34_cierre_cluster.log, g34_estado_cluster_final.log y g34_cierre_completo.

Alcance previsto: 10 archivos — cinco de producción, dos de pruebas y tres Markdown. Cabeceras de tarea en los siete Python, preservando otras filas. No hay cambios de frontend, firmware o broker. No se incorporan otras ramas de corrección; revisar los cambios superpuestos del motor al integrar, especialmente la propagación de reloj de #687 si se integra junto con esta rama.

Pendientes: despliegue autorizado; integración efectiva de avisos M04/M06; diseño asíncrono RNF-08; proveedor histórico de límites M09 y validación formal de preferencias CA-17. Esta entrega no repara automáticamente evaluaciones ya huérfanas de una ejecución antigua: selecciona las vigentes existentes. Una reparación histórica necesita inventario y operación autorizada, conservando trazabilidad.

El usuario autorizó commit y push de esta corrección. La publicación del PR queda fuera de esta entrega. Ver [PR preparado](inc_m03_133_g170_rf62_pr_preparado.md) y referencia API actualizada.
