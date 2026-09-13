-- Todas las consultas de TC-M02-G43 son estrictamente SELECT.
SELECT count(*) AS d1_total_activos,
       count(*) FILTER (WHERE upper(e.nombre) = 'ACTIVO') AS d2_activos_activos,
       count(DISTINCT a.id_activo_biologico) FILTER (WHERE upper(e.nombre) = 'ACTIVO' AND g.es_activa) AS d3_activos_activos_con_fase
FROM modulo2.activos_biologicos a
JOIN modulo2.estados_activos_biologicos e ON e.id_estado_activo_biologico = a.id_estado
LEFT JOIN modulo2.gestiones_fases g ON g.id_activo_biologico = a.id_activo_biologico;

SELECT a.id_activo_biologico, a.descripcion, a.tipo, e.nombre AS estado, s.nombre AS especie,
       f.id_finca, f.nombre AS finca, f.id_usuario AS propietario_finca,
       g.id_gestion_fases, g.id_ciclo_productiva, g.fecha_inicio AS fase_inicio,
       m.id_metrica_produccion, m.tipo_medicion, m.unidad_medida, m.valor_min, m.valor_max,
       count(ec.id_evento) AS crecimiento_antes, max(ea.fecha) FILTER (WHERE ec.id_evento IS NOT NULL) AS ultimo_evento_antes
FROM modulo2.activos_biologicos a
JOIN modulo2.estados_activos_biologicos e ON e.id_estado_activo_biologico = a.id_estado
JOIN modulo9.especies s ON s.id_especie = a.id_especie
JOIN modulo9.infraestructuras i ON i.id_infraestructura = a.id_infraestructura
JOIN modulo9.fincas f ON f.id_finca = i.id_finca
JOIN modulo2.gestiones_fases g ON g.id_activo_biologico = a.id_activo_biologico AND g.es_activa
JOIN modulo9.metricas_produccion m ON m.id_especie = a.id_especie AND m.es_activo AND upper(m.tipo_medicion) = 'PESO' AND lower(m.unidad_medida) = 'kg'
LEFT JOIN modulo2.eventos_activos ea ON ea.id_activo_biologico = a.id_activo_biologico
LEFT JOIN modulo2.eventos_crecimeinto ec ON ec.id_evento = ea.id_eventos
WHERE a.id_activo_biologico IN (279, 311, 312)
GROUP BY a.id_activo_biologico, a.descripcion, a.tipo, e.nombre, s.nombre, f.id_finca, f.nombre, f.id_usuario,
         g.id_gestion_fases, g.id_ciclo_productiva, g.fecha_inicio,
         m.id_metrica_produccion, m.tipo_medicion, m.unidad_medida, m.valor_min, m.valor_max
ORDER BY a.id_activo_biologico;

SELECT u.id_usuario, u.correo_electronico, r.nombre_rol, ec.nombre AS estado_cuenta,
       f.id_finca, f.nombre AS finca,
       array_agg(DISTINCT p.id_accion ORDER BY p.id_accion) FILTER (WHERE p.id_recurso = 29 AND p.es_activo) AS acciones_recurso_29
FROM modulo1.usuarios u
JOIN modulo1.roles r ON r.id_rol = u.id_rol
LEFT JOIN modulo1.cuentas_usuarios cu ON cu.id_usuario = u.id_usuario
LEFT JOIN modulo1.estados_cuentas ec ON ec.id_estado_cuenta = cu.id_estado_cuenta
LEFT JOIN modulo9.fincas f ON f.id_usuario = u.id_usuario
LEFT JOIN modulo1.permisos p ON p.id_rol = u.id_rol
WHERE u.id_usuario IN (35, 3, 4)
GROUP BY u.id_usuario, u.correo_electronico, r.nombre_rol, ec.nombre, f.id_finca, f.nombre
ORDER BY u.id_usuario, f.id_finca;
