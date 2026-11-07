# Gaps de BD — ajustes de frontend M02/M03/M04 (AJF-01 a AJF-14)

Fecha: 2026-11-02 · Autor: Arekkazu.

Paso 0 del CLAUDE.md hecho contra el baseline (`alembic/baseline/esquema_baseline.sql`) y todas las
migraciones del repo, porque desde el entorno de trabajo no había red hacia `sgpmp_dev`. **Al aplicar,
correr las consultas de verificación del final en DEV.**

Migraciones nuevas, en orden (cabeza única: `bb5526687aae`). Ninguna está aplicada; las dos
necesitan la autorización de SamuelPR21. SQL completo para revisión: `ajustes_m02_m03_m04_migraciones.sql`.

| Revisión | Contenido |
|----------|-----------|
| `21fe51f2aea1` | AJF-14: tabla `modulo4.procesos_reentrenamiento`, 3 ENUM, índices, grants y RLS |
| `bb5526687aae` | AJF-07 y AJF-04: RLS de `bitacora_ingest`, índice por fecha y lectura de parámetros IoT |

## Gaps por ítem

| Ítem | Objeto | Gap | Decisión | Dónde |
|------|--------|-----|----------|-------|
| AJF-14 | `modulo4.procesos_reentrenamiento` | No existía dónde seguir un reentrenamiento | Tabla nueva + `enum_proceso_reentrenamiento_{disparador,modo_generacion,estado}` | `21fe51f2aea1` |
| AJF-14 | idem | Dos procesos abiertos para el mismo animal | `uq_proceso_reentrenamiento_id_activo_biologico` parcial (PENDIENTE, EN_CURSO) | `21fe51f2aea1` |
| AJF-14 | idem | Cola del motor y listado | `idx_proceso_reentrenamiento_estado_fecha_solicitud` | `21fe51f2aea1` |
| AJF-14 | idem | Grants y RLS | SELECT/INSERT/UPDATE a los roles de la app; `pol_proceso_reentrenamiento_select` (animal en sus infraestructuras), `_insert` (43·E y a su nombre), `_servicio` (motor) | `21fe51f2aea1` |
| AJF-14 | `enum_tipo_evento_auditoria_m04` | Eventos INICIADO/COMPLETADO/FALLIDO/INTERRUMPIDO | **Ya existen** en el baseline: sin DDL | — |
| AJF-14 | `modulo3.telemetrias` (RLS) | Contar los días de lecturas con la sesión del usuario exigía permiso de monitoreo/historial: "lecturas insuficientes" falsas | **En código, sin DDL**: el conteo va con una sesión de sistema aparte (`horas_de_lecturas`) | `version_modelo_router.py` |
| AJF-07 | `modulo3.bitacora_ingest` (RLS) | Lectura solo con `bitacora_auditoria_iot` R (39); la pestaña usa `alertas_tecnicas_iot` R (36): lista vacía sin error para el Ingeniero | `pol_bitacora_ingest_select` acepta 39·R o 36·R; el alcance por dispositivos no cambia | `bb5526687aae` |
| AJF-07 | `modulo3.bitacora_ingest` (índice) | Los índices existentes empiezan por dispositivo o tipo de evento; el monitor filtra solo por fechas | `idx_bitacora_ingest_fecha_evento (fecha_evento DESC)` | `bb5526687aae` |
| AJF-07 | `modulo3.bitacora_ingest` | Los eventos sin dispositivo (rechazos de autenticación) no los ve ningún usuario | Se mantiene: no se pueden acotar por finca. Quedan para el DBA o una vista de seguridad aparte | — |
| AJF-04 | `modulo4.parametros_mlops` (RLS) | Lectura solo con `version_modelo` R (43): el Ingeniero veía todo "Sin configurar" | `pol_parametro_mlops_select_operacion_iot`: 36·R, solo las 7 claves de heartbeat y visión | `bb5526687aae` |
| AJF-04 | `modulo9.configuraciones_globales`, `tipos_dispositivo_iot` | — | Lectura `USING (true)`: sin gap | — |
| AJF-04 | `modulo3.observaciones_vision` | — | Lectura por infraestructuras del usuario: sin gap | — |
| AJF-01 | `modulo3.alertas`, `modulo4.resultados_*`, `retroalimentaciones_clinicas`, `modulo2.movimientos` | — | Leídos con la sesión del usuario: cada uno ve lo que su RLS permite (correcto). Sin columnas ni índices nuevos (`LAG` por animal usa el índice por activo existente) | — |
| AJF-10 | `modulo4.resultados_inferencia` | — | Filtros y conteo sobre columnas existentes; sin gap | — |
| AJF-13 | `modulo4.eventos_auditoria_m04` | — | `entidad_referencia` ya existe (varchar 50, sin CHECK); sin gap | — |
| AJF-02, 03, 05, 06, 08, 09, 11, 12 | — | Solo frontend o lectura de endpoints existentes | Sin gap | — |

## RBAC

Ningún recurso ni permiso nuevo: `GET /iot/ingesta*` y los dos GET de AJF-04 usan 36·R (Administrador
e Ingeniero); los procesos de reentrenamiento, 43·R para leer y 43·E para solicitar (Administrador y
Veterinario); el monitor paginado, 42·R; la bitácora, 46·R.

## Verificación en DEV después de aplicar

```sql
SELECT version_num FROM alembic_version;                                   -- bb5526687aae
SELECT polname FROM pg_policies WHERE tablename = 'procesos_reentrenamiento';  -- select, insert, servicio
SELECT pg_get_expr(polqual, polrelid) FROM pg_policy WHERE polname = 'pol_bitacora_ingest_select';
SELECT polname FROM pg_policies WHERE polname = 'pol_parametro_mlops_select_operacion_iot';
SELECT indexname FROM pg_indexes WHERE indexname IN ('idx_bitacora_ingest_fecha_evento',
  'uq_proceso_reentrenamiento_id_activo_biologico', 'idx_proceso_reentrenamiento_estado_fecha_solicitud');
-- Permisos que usan los endpoints (deben existir y estar activos):
SELECT r.nombre AS rol, re.nombre AS recurso, a.codigo
FROM modulo1.permisos p JOIN modulo1.roles r USING (id_rol) JOIN modulo1.recursos re USING (id_recurso)
JOIN modulo1.acciones a USING (id_accion)
WHERE (p.id_recurso, p.id_accion) IN ((36,2),(42,2),(43,2),(43,5),(46,2)) ORDER BY 2, 1;
```
