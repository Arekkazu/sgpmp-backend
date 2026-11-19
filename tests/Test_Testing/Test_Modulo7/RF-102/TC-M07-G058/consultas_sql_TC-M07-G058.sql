-- TC-M07-G058 / RF-102 — consultas SQL de SOLO LECTURA
-- Objetivo: diagnosticar retención (5/10 años), archivado, hashes e histórico
-- en modulo7.eventos_integracion. No ejecutar DML/DDL sobre ambientes compartidos.
-- Fuente de esquema esperada: alembic/versions/94b14a6931d6_m07_integracion_aaef_rfc017.py

-- 1) Existencia de tabla y tablas/vistas relacionadas con archivo/retención/histórico
SELECT table_schema, table_name
FROM information_schema.tables
WHERE table_schema = 'modulo7'
  AND (
    table_name ILIKE '%evento%integr%'
    OR table_name ILIKE '%archiv%'
    OR table_name ILIKE '%reten%'
    OR table_name ILIKE '%histor%'
    OR table_name ILIKE '%rf102%'
  )
ORDER BY 1, 2;

-- 2) Columnas reales de eventos_integracion (si existe)
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_schema = 'modulo7' AND table_name = 'eventos_integracion'
ORDER BY ordinal_position;

-- 3) Triggers de inmutabilidad (RF-102 4.4) — no son retención/archivado
SELECT tgname, pg_get_triggerdef(t.oid) AS definicion
FROM pg_trigger t
WHERE NOT tgisinternal
  AND tgrelid = 'modulo7.eventos_integracion'::regclass;

-- 4) Funciones modulo7 relacionadas con archivo/retención/evento
SELECT n.nspname AS schema, p.proname AS funcion
FROM pg_proc p
JOIN pg_namespace n ON n.oid = p.pronamespace
WHERE n.nspname = 'modulo7'
  AND (
    p.proname ILIKE '%archiv%'
    OR p.proname ILIKE '%reten%'
    OR p.proname ILIKE '%evento%integr%'
  )
ORDER BY 1, 2;

-- 5) Extensión pg_cron (jobs programados)
SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_cron') AS tiene_pg_cron;

-- 6) Jobs pg_cron que mencionen modulo7 / auditoría / archivo (si existe extensión)
-- SELECT jobid, schedule, command FROM cron.job
-- WHERE command ILIKE '%modulo7%' OR command ILIKE '%eventos_integracion%' OR command ILIKE '%archiv%';

-- 7) Cobertura de hash e intervalos de fecha (antigüedad)
SELECT
  count(*)::int AS total,
  count(*) FILTER (
    WHERE hash_integridad IS NOT NULL AND hash_integridad ~ '^[0-9a-f]{64}$'
  )::int AS con_hash_sha256,
  min(fecha_evento) AS min_fecha_evento,
  max(fecha_evento) AS max_fecha_evento,
  count(*) FILTER (
    WHERE fecha_evento <= (now() AT INTERVAL '5 years')
  )::int AS generales_antiguedad_ge_5y,
  count(*) FILTER (
    WHERE tipo_evento::text IN ('PAQUETE_AAEF_CONSULTADO', 'VISTA_AAEF_GENERADA', 'CONTRATO_ACTIVADO')
      AND fecha_evento <= (now() AT INTERVAL '10 years')
  )::int AS aaef_antiguedad_ge_10y
FROM modulo7.eventos_integracion;

-- 8) ¿Existe tabla histórica dedicada de M07?
SELECT EXISTS (
  SELECT 1 FROM information_schema.tables
  WHERE table_schema = 'modulo7'
    AND table_name IN (
      'eventos_integracion_archivo',
      'eventos_integracion_historico',
      'eventos_integracion_archivados',
      'auditoria_integracion_archivo'
    )
) AS existe_tabla_historica_m07;
