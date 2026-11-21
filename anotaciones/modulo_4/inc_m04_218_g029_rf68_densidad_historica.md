# INC-M04-218-G029 · RF-68 — Recuperación histórica de densidad

Fecha: 2026-10-30. Identidad Git consultada: Leandro.
Issue: [#853](https://github.com/Arekkazu/sgpmp-backend/issues/853).
Rama: fix/inc-m04-218-g029-densidad-historica-rf68.
Base: dev actualizado por fast-forward a e94232b5086bc1232a77a9f1a625225165eb9a49.

## Diagnóstico y fuente verificada

RF-68 E2 exige el histórico promedio de ocupación del lote de los últimos 30 días ante un error del sensor de densidad. El DTO imponía ge=0 y rechazaba -5 antes de ejecutar el caso de uso. El motor no tenía un puerto de lectura histórica y, si se llamaba directamente con un negativo, saturaba Fd en cero. Se reprodujo el rechazo original mediante una prueba que falló por greater_than_equal antes de cambiar producción.

RF-68 distingue ese error de la densidad desconocida/nula: la restricción de dependencia de datos pide capacidad máxima preventiva para el nulo. Se conservan ambos caminos separados.

No existe en el código una serie dedicada de ocupación de 30 días. historial_activos se escribe como snapshot inicial RF-33, no como una serie completa de cambios poblacionales. La fuente reutilizada es auditoria.logs_dml: el trigger existente de detalles_activos_biologicos_poblacionales registra automáticamente los estados anteriores y nuevos, incluida densidad calculada en M02. No se crea una tabla alternativa ni se reconstruye un valor fijo 9.5.

Se inspeccionaron metadatos oficiales exclusivamente con SET TRANSACTION READ ONLY y rollback. Los logs técnicos y el trigger existen; sgpmp_app y rol_app tienen SELECT sobre la fuente. member_dev no tiene SELECT sobre historial_activos: su omisión en information_schema no demuestra que falte la tabla; sus políticas sí son visibles. Se verificaron CHECK, FK, RLS y triggers relacionados. La consulta de modulo1.permisos y alembic_version fue denegada (42501); no se presume una revisión desplegada.

## Definiciones confirmadas

El usuario confirmó:

1. Promedio ponderado por el tiempo de vigencia de cada densidad registrada del mismo lote, dentro de los últimos 30 días.
2. Si una densidad negativa no tiene histórico utilizable: capacidad máxima preventiva, confianza baja y ausencia de alertas automáticas. La densidad nula conserva su comportamiento anterior.

La fórmula es suma(densidad × duración válida) / suma(duración válida). El último registro previo a la ventana establece el estado al inicio. Los períodos anteriores al primer dato conocido o con estados inválidos no se rellenan. La cobertura real queda registrada; un histórico parcial no se presenta como cobertura completa de 30 días.

A igual instante prevalece el registro de mayor id. Se excluye el futuro; un cambio justo en el instante final no aporta duración. Un valor nulo, negativo, no finito o malformado interrumpe el período conocido. DELETE también termina ese estado. Densidad cero es válida; el cociente por densidad máxima conserva su saturación en [0,1].

La fuente representa densidades registradas por M02 y sus instantes de auditoría, no mediciones físicas retrospectivas ni las fechas de captura de un sensor. Los timestamp sin zona de auditoría se interpretan en UTC, conforme al contrato de src/shared/database.py. E2 constituye la excepción explícita que permite utilizar este histórico como factor auxiliar; no se mezcla con los timestamps de las inferencias RF-66.

## Flujo implementado

HTTP → DTO finito → validación de acceso al lote → configuración/caché existentes → puerto OcupacionLotePort si densidad<0 → adaptador M02 → promedio temporal puro en dominio → Fd y modelo existentes → resultado/snapshot → auditoría RF-73 → commit del caso de uso.

El adaptador selecciona solo id_log, fecha y densidad, con parámetros y nombres de tabla fijos. El EXISTS sobre activos_biologicos exige el mismo lote POBLACIONAL visible bajo RLS. No utiliza como_sistema ni amplía el alcance del solicitante para leer la auditoría. No devuelve SQL, parámetros ni datos personales del registro técnico.

La consulta histórica no ocurre para densidades nulas, omitidas, cero o positivas; tampoco antes de verificar acceso ni al reutilizar un resultado válido de caché. Los errores de BD se traducen con raise_from_db_error; no se interpretan como histórico vacío.

## Contrato y trazabilidad

- El campo densidad_poblacional admite negativos finitos para procesar el error de sensor en E2. Tipos malformados, NaN e infinitos siguen rechazados.
- Con histórico medio 9.5 y densidad máxima 15, Fd=0.6333. El 9.5 procede de los estados usados, nunca de una constante del motor.
- Sin cobertura histórica útil para un negativo: Fd=1 cuando hay densidad máxima, densidad_asumida=true, confianza_baja=true y motivo SIN_HISTORICO_OCUPACION.
- Con nulo: se conserva el preventivo existente, sin añadir el motivo anterior ni consultar historia.
- Se conserva el esquema público de respuesta, la fórmula, los pesos y los códigos HTTP existentes, salvo que un negativo finito ahora ejecuta E2 y puede responder 201 en vez del rechazo previo 400.
- contexto_densidad se conserva en variables_ambientales_snap y RF-73: entrada solicitada, densidad aplicada, fuente, ventana, segundos cubiertos, cantidad y extremos de registros utilizados. La lectura admite snapshots previos sin esa clave.
- La huella conserva la entrada original y config_version. Un resultado en caché conserva la resolución histórica del ciclo original.

## BD, seguridad y migración

Sin migración nueva ni DDL/DML en la BD oficial. Se reutilizan el trigger de M02, los registros técnicos existentes y el JSONB de resultados M04. No se cambian políticas, permisos de negocio, restricciones o identidades de servicio.

La integración usa PostgreSQL 18 local, una base exclusiva sgpmp_g42_test, migrada desde cero, y TEST_ROL_APP=sgpmp_app sin superusuario/BYPASSRLS en los requests. Se aprovisionan solo privilegios SQL locales de los objetos utilizados; la lectura de auditoría se limita a las columnas consultadas. La preparación de fixtures corre como propietario y los requests como el rol real.

Los históricos de 8 y 11 durante 15 días cada uno son fixtures sintéticas identificadas como fixture-inc853, insertadas solo en la base desechable. No se modifican logs existentes ni se desactivan triggers. Una prueba independiente comprueba la generación de la fuente por el trigger real de M02.

## Pruebas y evidencia

| Grupo | Aprobadas | Fallidas | Omitidas |
|---|---:|---:|---:|
| Unitarias y contrato RF-68/RFC-009 (3 archivos) | 79 | 0 | 0 |
| HTTP con PostgreSQL 18 real, JWT/RBAC/RLS | 17 | 0 | 0 |
| **Total distinto** | **96** | **0** | **0** |

No se suman ejecuciones repetidas ni la reproducción fallida previa a la corrección. Advertencia preexistente de TestClient/httpx en integración; las corridas finales no tienen fallos ni omisiones.

Evidencias ignoradas: .pytest_cache/g42_antes.xml/log, g42_unit.xml/log, g42_pg.xml/log, g42_preflight.json, g42_migraciones.log y g42_verificacion.json. Los lanzadores contienen el shim fcntl exclusivamente de pruebas para Windows.

Las pruebas de contrato y unitarias usan fakes. Las de integración comprueban HTTP, persistencia, auditoría, rollback, UTC, JWT/RBAC y aislamiento con PostgreSQL real. La falla del puerto y el fallo posterior al flush se inyectan de forma controlada; no representan una caída física del servidor.

## Dependencias y límites

La rama parte de dev actualizado y no incorpora el commit 831ea427 de #852, aún fuera de esa base al iniciar. La corrección de umbrales y del contexto RF-57/RF-63 de #852 es independiente: debe integrarse también para obtener ambos arreglos. Los cambios concurrentes en cabeceras, snapshot, dominio y router deben conservarse de ambas ramas al integrar.

Queda desplegar y reejecutar TC-M04-G029 en un sandbox autorizado. La validación local no demuestra el estado de un despliegue TEST/DEV compartido. No se cambian los umbrales, las reglas sanitarias ni el flujo de alertas en esta tarea.

## Cierre del entorno local

Se eliminó exclusivamente sgpmp_g42_test y se detuvo el clúster iniciado para esta tarea. Se verificó que las demás bases locales permanecieron intactas; evidencia en .pytest_cache/g42_cierre_bd.log. Los logs y scripts se conservan.

## Entrega

Código, pruebas e informes con cabeceras de seguimiento. Se preservan AGENTS.md y los documentos ajenos sin seguimiento. Los artefactos temporales .pytest_cache/g42_* no forman parte del commit. Commit y push autorizados por el usuario para #853; no se solicitó publicar un PR.
