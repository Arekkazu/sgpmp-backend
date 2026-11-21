-- Semilla de laboratorio G43. NO ejecutar en esta fase.
-- Destino obligatorio: sgpmp_g43_test (puerto 5439).
-- Prohibido: sgpmp, sgpmp_pr14_test.
-- Serial: G43-LAB-001 (no Raspberry / G38 / G41).
-- Ajustar id_tipo_dispositivo al catálogo restaurado (consultar SELECT antes).

-- 1) Comprobar destino
-- SELECT current_database();  -- debe ser sgpmp_g43_test
-- SELECT inet_server_port();  -- 5432 dentro del contenedor; host 5439

-- 2) Consultar catálogo (solo lectura) antes de insertar
-- SELECT id_tipo_dispositivo, nombre FROM modulo9.tipos_dispositivo LIMIT 20;
-- SELECT id_variable_ambiental, nombre FROM modulo9.variables_ambientales
--   WHERE nombre ILIKE '%temp%' OR codigo ILIKE '%TEMPERATURA%';

-- 3) Inserción prevista (autorización expresa; no correr ahora)
/*
WITH finca AS (
  INSERT INTO modulo9.fincas (nombre, ubicacion, tamano_h, fecha_actualizacion, fecha_creacion, es_activo)
  VALUES ('G43 LAB FINCA', '{}'::jsonb, 1, now(), now(), true)
  RETURNING id_finca
),
area AS (
  INSERT INTO modulo9.infraestructuras (nombre, id_finca, superficie, es_activo, tipo)
  SELECT 'G43 LAB AREA', id_finca, 10, true, 'Estanque' FROM finca
  RETURNING id_infraestructura
),
dev AS (
  INSERT INTO modulo9.dispositivos_iot (serial, descripcion, es_activo, fecha_creacion, id_infraestructura, id_tipo_dispositivo)
  SELECT 'G43-LAB-001', 'Laboratorio G43 oficial', true, now(), id_infraestructura, :id_tipo
  FROM area
  RETURNING id_dispositivo_iot
)
INSERT INTO modulo9.sensores (id_dispositivo_iot, es_activo, nombre)
SELECT id_dispositivo_iot, true, 'G43-LAB-SENSOR-TEMP'
FROM dev;
*/

-- 4) El puente resuelve device_id por serial y sensor_id por nombre o primer sensor activo.
--    FakeLoraSource no envía `sensor`; el fallback de reenvio_nodo.evento_edge usa
--    resolve_sensor_id(dispositivo). Hace falta al menos un sensor activo.

-- 5) GRANT previstos para g43_app (después de crear el rol; no ahora):
-- GRANT USAGE ON SCHEMA modulo3, modulo9, modulo1 TO g43_app;
-- GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA modulo3 TO g43_app;
-- GRANT SELECT ON ALL TABLES IN SCHEMA modulo9 TO g43_app;
-- (Ajustar a sgpmp_app del dump si se reutilizan roles restaurados.)
