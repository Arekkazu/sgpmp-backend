SELECT current_database();
BEGIN;
WITH finca AS (
  INSERT INTO modulo9.fincas (nombre, ubicacion, tamano_h, fecha_actualizacion, fecha_creacion, es_activo)
  VALUES ('Finca Laboratorio', '{}'::jsonb, 1, now(), now(), true)
  RETURNING id_finca
),
area AS (
  INSERT INTO modulo9.infraestructuras (nombre, id_finca, superficie, es_activo, tipo)
  SELECT 'Area Laboratorio', id_finca, 10, true, 'Estanque' FROM finca
  RETURNING id_infraestructura
),
dev AS (
  INSERT INTO modulo9.dispositivos_iot (serial, descripcion, es_activo, fecha_creacion, id_infraestructura, id_tipo_dispositivo)
  SELECT 'G43-LAB-001', 'Laboratorio G43 oficial', true, now(), id_infraestructura, 3
  FROM area
  RETURNING id_dispositivo_iot
)
INSERT INTO modulo9.sensores (id_dispositivo_iot, es_activo, nombre, categoria)
SELECT id_dispositivo_iot, true, 'G43-LAB-SENSOR-TEMP', 'TEMPERATURA'
FROM dev;
COMMIT;
SELECT d.id_dispositivo_iot, d.serial, s.id_sensores, s.nombre, current_database()
FROM modulo9.dispositivos_iot d
JOIN modulo9.sensores s ON s.id_dispositivo_iot = d.id_dispositivo_iot
WHERE d.serial = 'G43-LAB-001';