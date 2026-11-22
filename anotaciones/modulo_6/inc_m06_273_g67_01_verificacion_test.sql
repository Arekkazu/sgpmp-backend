-- | Fecha | Nombre | Que se hizo |
-- |-------|--------|-------------|
-- | 2026-11-07 | Leandro | INC-M06-273-G67-01 RF-82: inspeccionar la identidad, las tablas y las ACL de la conexión real de la API, sin escrituras. |
-- Ejecutar con acceso autorizado a LA MISMA conexión que usa la API TEST.
-- No copiar contraseñas ni publicar DATABASE_URL. Este script no aplica migraciones.
BEGIN TRANSACTION READ ONLY;
SET LOCAL statement_timeout = '5s';
SELECT current_database() AS base, current_user AS rol,
       current_schema() AS esquema_actual, current_setting('search_path') AS search_path;
SELECT schemaname, tablename FROM pg_catalog.pg_tables
WHERE schemaname = 'modulo6' AND tablename IN
 ('configuraciones_contables', 'parametros_contables_especies',
  'asignaciones_cuentas_contables', 'comprobantes_nic41', 'lineas_asiento_nic41')
ORDER BY tablename;
WITH requeridas(tabla) AS (VALUES ('configuraciones_contables'), ('parametros_contables_especies'),
 ('asignaciones_cuentas_contables'), ('comprobantes_nic41'), ('lineas_asiento_nic41'))
SELECT tabla, to_regclass(format('modulo6.%I', tabla)) AS objeto,
       has_schema_privilege(current_user, 'modulo6', 'USAGE') AS acceso_esquema,
       CASE WHEN to_regclass(format('modulo6.%I', tabla)) IS NOT NULL
            THEN has_table_privilege(current_user, to_regclass(format('modulo6.%I', tabla)), 'SELECT') END AS puede_leer,
       CASE WHEN to_regclass(format('modulo6.%I', tabla)) IS NOT NULL
            THEN has_table_privilege(current_user, to_regclass(format('modulo6.%I', tabla)), 'INSERT') END AS puede_insertar
FROM requeridas ORDER BY tabla;
COMMIT;
-- Con el usuario de migración, también en sesión de solo lectura:
-- SELECT version_num FROM public.alembic_version;
-- Contrastar además el destino (sin divulgar secretos) de TEST_DATABASE_URL del workflow
-- con DATABASE_URL del servicio y el SHA efectivamente desplegado.
