# INC-M03-130-G16 / #685 — Frecuencia de ingesta y drift de RF-62

Fecha: 2026-10-27. Rama: `fix/inc-m03-130-g16-marcas-calidad-rf53`.
Base: `dev` actualizado, `5691096b8497b9fc445abf0a7579409c8de6550f`.

## Alcance confirmado y referencias

El usuario confirmó conservar el drift en RF-62 y la lectura original inmutable, validar ambos flujos y corregir los defectos de frecuencia reproducidos. No se agrega otro motor estadístico en SQL ni se actualiza telemetrias desde RF-62.

Referencias: [#685](https://github.com/Arekkazu/sgpmp-backend/issues/685), TC-M03-034, TC-M03-068, RF-53 E13/E17, RF-62 Fases 1/4/5/7 y AIOT-DEV-03 DEV-02. RF-53 E13 incluye enviar cada minuto o cada hora con muestreo de 10 minutos.

## Diagnóstico y causa raíz

| Punto | Estado comprobado en dev | Resolución |
|---|---|---|
| frecuencia_anomala siempre FALSE | 15cb081c4835 ya calcula frecuencia rápida: 1 minuto con configuración 10 sí se marca | Conservar y probar HTTP/batch/SQL |
| Frecuencia lenta | Solo se buscan vecinos a menos de 0,5 intervalos; 60 minutos no se marca | Ampliar la regla de frecuencia |
| Muestreo aplicado | El INSERT guarda NULL en frecuencia_muestreo_min | Conservar el valor M09 aplicado |
| posible_drift inicial FALSE | RF-62 sí calcula la marca en telemetria_calidad | Validar ingesta → snapshot → postcommit → GET calidad sin mutar origen |

Antes del cambio, los 12 casos rápidos/normales aprobaron; los tres de 60 minutos y el snapshot fallaron como se esperaba. Dos fixtures de drift requirieron corregir el nombre SQL a offset_calibracion. El flujo completo posteriormente aprobó sin modificar el motor de drift.

La afirmación literal de que ambas marcas nunca se calculan no describe el checkout actual. Si QA sigue observando FALSE cada minuto, debe contrastar 15cb081c4835 y pg_get_functiondef en su entorno. La función desplegada oficial no pudo inspeccionarse por timeout.

## Flujo y cambio mínimo

HTTP/batch → DTO/router → caso de uso → puerto/repositorio → fn_ingesta_telemetria → commit RF-53 → evaluación postcommit RF-62 → telemetria_calidad vigente → GET /iot/calidad/{id_telemetria}.

La única modificación de producción es una migración reversible de la función vigente:

- Intervalo al vecino cronológico más cercano del mismo sensor/variable, mediante anterior/posterior con LIMIT 1 e índice existente. Contempla BUFFER_LOCAL fuera de orden.
- Conserva el límite inferior existente de 0,5 intervalos y utiliza el superior de 2 intervalos de RF-62. Los límites exactos no se marcan. No se agrega un parámetro ni un rechazo funcional.
- Primera lectura sin vecino: FALSE. Sin configuración aplicable conserva el comportamiento previo, sin inventar muestreo. EVENTO_EDGE no se evalúa como muestra periódica ni participa como vecino.
- Inserta marca y frecuencia aplicada en la nueva lectura. No reescribe lecturas previas al recibir un backfill.
- Conserva latencia, rangos, calibración, bitácora, unicidad y contexto multiespecie.
- Mantiene firma de 19 entradas, retorno, propietario, ACL y atributos de la función. No cambia tablas, índices, políticas, DTO, respuesta, puertos ni permisos.

El valor de frecuencia enviado por el cliente no sustituye M09. El snapshot registra la configuración aplicada en la ingesta; no reconstruye una configuración histórica de captura que el catálogo no versiona. Los commits/rollbacks siguen en los casos de uso existentes.

## Drift y consulta

RF-62 usa N lecturas válidas, parámetros configurados y snapshot de calibración RF-53. Si supera el umbral y cumple P lecturas consistentes, persiste flags_detectados.posible_drift con magnitud, media y trazabilidad. Sin calibración no inventa drift; sin serie suficiente conserva INDETERMINADA.

El 201 de ingesta confirma la lectura original, no la finalización de RF-62. La marca estadística se obtiene de la evaluación vigente: un FALSE inicial en telemetrias no demuestra ausencia de drift. Las pruebas verifican la fórmula existente con calibración disponible; no certifican hardware ni cualquier patrón de sesgo arbitrario.

## Migración y dependencias

Revisión c685130a0260, padre ebbb160365e5. Requiere el árbol integrado de dev, incluidos 15cb081c4835 y el snapshot 8d13c7e9a624. No incorpora ramas independientes #681, #682 o #684.

upgrade/downgrade sustituyen solo el bloque de frecuencia y el valor del snapshot en la definición vigente; fallan si falta o se duplica el bloque esperado. Downgrade restituye la regla anterior para futuras ingestas y conserva datos ya insertados. No se edita una migración histórica ni se hace DML sobre lecturas.

Una única head inicial ebbb160365e5 y final c685130a0260. La prueba PostgreSQL comprueba round-trip exacto y conservación de propietario, ACL, SECURITY DEFINER, configuración, volatilidad y paralelismo. La regresión #626 comprueba convivencia con su snapshot de calibración.

## Base de datos y seguridad

La protección del preflight abortó al comprobar que .env no apuntaba al destino oficial; luego se intentó la conexión suministrada por el usuario en solo lectura y agotó el tiempo de espera. No se contrastaron función, migraciones ni RBAC oficiales ni se realizaron escrituras allí.

Se creó sgpmp_g31_test en PostgreSQL 18 local, puerto 55429, con Alembic desde cero. Se inspeccionaron columnas, índices, restricciones, triggers, políticas, RLS y permisos del esquema resultante: g31_inspeccion_local.log. Se mantienen la inmutabilidad y RLS/FORCE de configuraciones_globales.

La siembra/DDL utiliza el propietario local. Las nuevas operaciones HTTP y SQL equivalentes al broker utilizan sgpmp_app, sin superusuario/BYPASSRLS, con la identidad de servicio existente. Se aprovisionaron privilegios SQL solo en la base exclusiva, sin cambiar RBAC ni desactivar restricciones. Las regresiones conservan JWT/RBAC y acceso a sensores por finca.

## Pruebas y evidencias

| Grupo | Aprobadas | Fallidas | Omitidas |
|---|---:|---:|---:|
| tests/telemetry: fakes y contratos HTTP | 715 | 0 | 0 |
| PostgreSQL real: específicas #685 | 35 | 0 | 0 |
| PostgreSQL real: regresión motor #632 | 8 | 0 | 0 |
| PostgreSQL real: regresión alta/snapshot #626 | 13 | 0 | 0 |
| **Total distinto final** | **771** | **0** | **0** |

Evidencias finales: .pytest_cache/g31_unit_cierre.xml, g31_pg_core_final.xml, g31_pg_snapshot_cierre.xml y g31_resumen_final.json, con sus logs. Las ejecuciones unitarias iniciales interrumpidas por espera prolongada no se cuentan; la corrida final completa aprobó 715/715.

Casos específicos: 1/4,99/5/10/20/20,01/60 minutos con muestreo 10 por HTTP, batch y SQL; primera lectura; latencia independiente; buffer desordenado; origen inmutable; cambio posterior de M09; frecuencia declarada por cliente; eventos no periódicos; drift con/sin calibración; consulta vigente; reversibilidad y atributos de la función.

Exploratorias conservadas: g31_antes/g31_antes_real detectaron privilegios faltantes de fixtures; g31_baseline reprodujo frecuencia lenta y snapshot y detectó el identificador incorrecto de calibración; g31_drift_antes confirmó ese ajuste pendiente; g31_foco aprobó 19 casos iniciales. Las ampliaciones corrigieron un fixture que no respetaba heartbeat ≥ muestreo y completaron secuencias/auditoría de asociación locales. No se suman corridas repetidas al total final.

XML/logs/inspección/lanzadores se conservan ignorados en .pytest_cache. Shim fcntl solo en el lanzador Windows. Advertencias preexistentes de Starlette/httpx y Operation ID de auditoría, cuando corresponda.

## Despliegue y pendientes

Aplicar la migración por el procedimiento autorizado del entorno y comprobar su función efectiva. No se desplegó desde este trabajo. QA debe consultar drift en la evaluación vigente después de RF-62 y preparar N/P/umbrales/calibración verificables. No se modifica MQTT ni se requiere ampliar firmware; la función SQL representa el punto compartido de persistencia, no una certificación de broker/Edge reales.

Al terminar se eliminó exclusivamente sgpmp_g31_test, se comprobó que las otras bases locales se conservaron y se detuvo el clúster. Evidencias: .pytest_cache/g31_cierre_bd.log y g31_cierre_cluster.log.

## Archivos y Git

Cinco archivos: una migración, un archivo de integración y tres documentos (este informe, descripción de PR y referencia API). Se preservan AGENTS.md, notas ajenas, frontend y evidencias ignoradas. El usuario autorizó commit y push de esta corrección. La publicación del PR queda pendiente.
