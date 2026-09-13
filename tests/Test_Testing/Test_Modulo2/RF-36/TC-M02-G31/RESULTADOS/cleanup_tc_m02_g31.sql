-- ====================================================================
-- Script de Verificación de Integridad: TC-M02-G31 (RF-36)
-- Entorno: TEST (Base de Datos: sgpmp_test)
-- Modo: Solo lectura (SELECT)
-- Objetivo: Verificar el estado real de los lotes 344 y 345 tras la
--           ejecución de las pruebas de baja total, y confirmar la
--           ausencia de eventos huérfanos o inconsistencias.
-- ====================================================================

-- 1. Estado del lote 344
SELECT a.id_activo_biologico, a.tipo, e.nombre AS estado,
       d.cantidad_inicial, d.cantidad_actual, d.peso_promedio, d.biomasa_total,
       a.detalles_procedencia
FROM modulo2.activos_biologicos a
JOIN modulo2.estados_activos_biologicos e ON a.id_estado = e.id_estado_activo_biologico
JOIN modulo2.detalles_activos_biologicos_poblacionales d ON a.id_activo_biologico = d.id_activo_biologico
WHERE a.id_activo_biologico = 344;

-- 2. Estado del lote 345
SELECT a.id_activo_biologico, a.tipo, e.nombre AS estado,
       d.cantidad_inicial, d.cantidad_actual, d.peso_promedio, d.biomasa_total,
       a.detalles_procedencia
FROM modulo2.activos_biologicos a
JOIN modulo2.estados_activos_biologicos e ON a.id_estado = e.id_estado_activo_biologico
JOIN modulo2.detalles_activos_biologicos_poblacionales d ON a.id_activo_biologico = d.id_activo_biologico
WHERE a.id_activo_biologico = 345;

-- 3. Eventos de baja registrados asociados a la prueba
SELECT eb.id_evento, eb.cantidad_afectada, eb.tipo, eb.detalles, ea.fecha
FROM modulo2.eventos_bajas eb
JOIN modulo2.eventos_activos ea ON eb.id_evento = ea.id_eventos
WHERE eb.detalles LIKE '%TC-M02-197%' OR ea.descripcion LIKE '%TC-M02-197%';
