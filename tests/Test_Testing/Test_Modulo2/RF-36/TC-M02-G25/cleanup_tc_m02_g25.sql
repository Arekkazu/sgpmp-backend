-- ====================================================================
-- Script de Verificación de Integridad y Contingencia: TC-M02-G25 (RF-36)
-- Entorno: TEST (Base de Datos: sgpmp_test)
-- Objetivo: Confirmar con SELECT la inocuidad en base de datos tras la
--           reevaluación V2 de los subcasos TC-M02-051 y TC-M02-052.
-- Reglas: CERO DDL, CERO triggers, CERO DELETE destructivo.
-- ====================================================================

-- 1. Verificar estado final del lote de prueba (id 345, debe quedar INACTIVO id_estado = 2)
SELECT a.id_activo_biologico, a.tipo, a.id_especie, a.id_infraestructura, a.id_estado, 
       e.nombre AS nombre_estado, d.cantidad_inicial, d.cantidad_actual, d.densidad, d.peso_promedio
FROM modulo2.activos_biologicos a
LEFT JOIN modulo2.detalles_activos_biologicos_poblacionales d 
  ON a.id_activo_biologico = d.id_activo_biologico
LEFT JOIN modulo2.estados_activos_biologicos e
  ON a.id_estado = e.id_estado_activo_biologico
WHERE a.id_activo_biologico = 345;

-- 2. Confirmar que TC-M02-051 (baja rechazada) no persistió ningún evento de baja espurio en lote 345
SELECT COUNT(*) AS total_bajas_espurias_lote_345
FROM modulo2.eventos_bajas eb
JOIN modulo2.eventos_activos ea ON eb.id_evento = ea.id_eventos
WHERE ea.id_activo_biologico = 345;

-- 3. Confirmar que TC-M02-052 (evento de crecimiento rechazado) no persistió eventos de crecimiento en lote 345
SELECT COUNT(*) AS total_crecimientos_espurios_lote_345
FROM modulo2.eventos_crecimeinto ec
JOIN modulo2.eventos_activos ea ON ec.id_evento = ea.id_eventos
WHERE ea.id_activo_biologico = 345;

-- 4. Confirmar ausencia de columnas %densidad% en modulo9 (verificación de brecha arquitectónica)
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'modulo9' AND column_name ILIKE '%densidad%';

-- ====================================================================
-- SECCIÓN DE CONTINGENCIA (INACTIVACIÓN LÓGICA - SOLO DML - COMENTADA)
-- NOTA: Si el lote de prueba quedó activo por interrupción de red:
--
-- UPDATE modulo2.activos_biologicos
-- SET id_estado = 2
-- WHERE id_activo_biologico = 345 AND id_estado = 1;
-- ====================================================================
