-- =============================================================================
-- SCRIPT DE VERIFICACIÓN / INTEGRIDAD: TC-M02-G32
-- Requerimiento: RF-36 (Gestión Poblacional / CU03)
-- Subcasos: TC-M02-198, TC-M02-199
-- Política: Solo consultas SELECT para auditoría e integridad.
-- =============================================================================

-- 1. Verificar estado e inmutabilidad de métricas del lote 130
SELECT ab.id_activo_biologico,
       ab.tipo,
       e.nombre AS estado,
       d.cantidad_inicial,
       d.cantidad_actual,
       d.peso_promedio,
       d.biomasa_total,
       d.densidad
FROM modulo2.activos_biologicos ab
JOIN modulo2.estados_activos_biologicos e ON ab.id_estado = e.id_estado_activo_biologico
LEFT JOIN modulo2.detalles_activos_biologicos_poblacionales d ON ab.id_activo_biologico = d.id_activo_biologico
WHERE ab.id_activo_biologico = 130;

-- 2. Verificar eventos registrados asociados a TC-M02-G32
SELECT ea.id_eventos,
       ea.id_activo_biologico,
       ea.fecha,
       ea.descripcion,
       ea.id_usuario
FROM modulo2.eventos_activos ea
WHERE ea.id_activo_biologico = 130
  AND (ea.descripcion LIKE '%TC-M02-G32%' OR ea.descripcion LIKE '%TC-M02-198%' OR ea.descripcion LIKE '%TC-M02-199%')
ORDER BY ea.id_eventos DESC;

-- 3. Confirmar que no existen eventos productivos espurios en eventos_productivos
SELECT ep.id_evento,
       ep.cantidad,
       ep.condiciones,
       ep.id_metrica_produccion,
       ep.id_ciclo_productivo
FROM modulo2.eventos_productivos ep
JOIN modulo2.eventos_activos ea ON ea.id_eventos = ep.id_evento
WHERE ea.id_activo_biologico = 130
ORDER BY ep.id_evento DESC
LIMIT 5;

-- 4. Verificar registros en bitácora de auditoría M02 para TC-M02-G32
SELECT id_bitacora,
       rf_origen,
       tipo_evento,
       resultado,
       severidad_log,
       timestamp_evento,
       id_activo_biologico,
       detalle_tecnico
FROM modulo2.bitacora_auditoria_m02
WHERE id_activo_biologico = 130
ORDER BY id_bitacora DESC
LIMIT 5;
