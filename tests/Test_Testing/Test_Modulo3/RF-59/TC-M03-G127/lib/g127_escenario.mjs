export const CASOS = ['TC-M03-256'];
export const ID = 'API-256-01';
export const PRESUPUESTO = Object.freeze({ solicitudes_directas: 14, solicitudes_newman: 3,
  margen_cierre: 1, duracion_segundos: 720, inactividad_maxima_segundos: 120,
  timeout_ms: 30000, timeout_seleccion_ms: 20000, unidades_dashboard: 8,
  unidades_conocidas: [1, 268, 337], historiales_descubrimiento: 12 });
export const CAPACIDADES = Object.freeze({ contrato: 'sigab-qa-ejecutor/1', grupo: 'G127', casos: CASOS,
  operaciones: ['evaluar', 'reintentar', 'reevaluar'], versiones: { min: 1, max: 99 },
  comprobaciones_obligatorias: { 'TC-M03-256': { API: [ID] } },
  limite: { solicitudes_directas: PRESUPUESTO.solicitudes_directas,
    margen_cierre: PRESUPUESTO.margen_cierre, duracion_segundos: PRESUPUESTO.duracion_segundos,
    inactividad_maxima_segundos: PRESUPUESTO.inactividad_maxima_segundos } });

export const fecha = ms => new Date(ms).toISOString().slice(0, 10);
export const rango = (fin, dias) => ({ inicio: fecha(fin - dias * 86400000), fin: fecha(fin) });
export function rutaHistorial(s, porPagina = 20) {
  return `/iot/monitoreo/historial?${new URLSearchParams({ fecha_inicio: s.inicio, fecha_fin: s.fin,
    sensor_id: String(s.sensorId), pagina: '1', por_pagina: String(porPagina), orden: 'DESC' })}`;
}
export function rutaAuditoria(idUsuario, desde, hasta, tipo = 'HISTORIAL_CONSULTADO') {
  return `/iot/auditoria?${new URLSearchParams({ tipo_evento: tipo,
    id_usuario: String(idUsuario), rf_origen: 'RF59', fecha_desde: desde, fecha_hasta: hasta,
    pagina: '1', por_pagina: '200' })}`;
}
export function identidadJwt(token) {
  try {
    const p = JSON.parse(Buffer.from(token.split('.')[1], 'base64url').toString('utf8'));
    const id = Number(p.sub), rol = Number(p.id_rol ?? p.rol);
    return { id: Number.isSafeInteger(id) && id > 0 ? id : null,
      rol: Number.isSafeInteger(rol) && rol > 0 ? rol : null };
  } catch { return { id: null, rol: null }; }
}
const detalle = e => e?.accion_detallada ?? e?.detalle ?? {};
const filtros = e => detalle(e).filtros ?? detalle(e).filtros_aplicados
  ?? detalle(e).parametros_filtrado ?? e?.filtros_aplicados ?? {};
const primero = (...valores) => valores.find(v => v !== null && v !== undefined);
const sensor = e => primero(filtros(e).sensor_id, filtros(e).id_sensor, detalle(e).sensor_id);
const porPagina = e => primero(detalle(e).por_pagina, detalle(e).paginacion?.por_pagina,
  filtros(e).por_pagina);
const equiv = (a, b) => String(a ?? '') === String(b ?? '');
const fechaIgual = (a, b) => typeof a === 'string' && a.slice(0, 10) === b;
export function evaluarEvento(eventos, op) {
  const candidatos = (Array.isArray(eventos) ? eventos : []).filter(e =>
    e?.tipo_evento === 'HISTORIAL_CONSULTADO'
    && equiv(primero(e.id_usuario, detalle(e).id_usuario, detalle(e).usuario_id), op.idUsuario)
    && (!Number.isFinite(Date.parse(e.fecha_hora ?? e.timestamp ?? e.fecha_evento))
      || (Date.parse(e.fecha_hora ?? e.timestamp ?? e.fecha_evento) >= Date.parse(op.desde) - 5000
        && Date.parse(e.fecha_hora ?? e.timestamp ?? e.fecha_evento) <= Date.parse(op.hasta) + 30000))
    && (equiv(sensor(e), op.sensorId) || equiv(porPagina(e), op.porPagina)));
  const e = candidatos.find(x => equiv(porPagina(x), op.porPagina)
    && equiv(sensor(x), op.sensorId)) ?? candidatos[0];
  if (!e) return { estado: 'RECHAZADO', motivo: 'No existe evento correlacionable de la consulta del RUN tras búsqueda RF-63 válida', valores: null,
    faltantes: ['evento'] };
  const d = detalle(e), f = filtros(e);
  const valores = { id_evento: e.id_evento ?? null,
    id_usuario: primero(e.id_usuario, d.id_usuario, d.usuario_id),
    id_rol: primero(d.id_rol, d.rol, e.id_rol, e.rol), sensor_id: sensor(e) ?? null,
    fecha_inicio: primero(f.fecha_inicio, f.desde, f.rango?.fecha_inicio, f.rango?.desde,
      d.rango_temporal?.inicio),
    fecha_fin: primero(f.fecha_fin, f.hasta, f.rango?.fecha_fin, f.rango?.hasta,
      d.rango_temporal?.fin),
    por_pagina: porPagina(e) ?? null,
    registros_devueltos: primero(d.registros_devueltos, d.cantidad_registros,
      d.numero_registros_devueltos, d.numero_registros, d.cantidad),
    timestamp: e.fecha_hora ?? e.timestamp ?? e.fecha_evento ?? null,
    exportado: primero(d.exportado, d.se_exporto, e.exportado) ?? null };
  const faltantes = [];
  if (!equiv(valores.id_usuario, op.idUsuario)) faltantes.push('usuario');
  if (valores.id_rol == null || (op.idRol != null
    && !equiv(valores.id_rol, op.idRol)
    && String(valores.id_rol).toUpperCase() !== 'PRODUCTOR')) faltantes.push('rol');
  if (!equiv(valores.sensor_id, op.sensorId) || !equiv(valores.por_pagina, op.porPagina)) faltantes.push('filtros');
  if (!fechaIgual(valores.fecha_inicio, op.inicio) || !fechaIgual(valores.fecha_fin, op.fin)) faltantes.push('rango temporal');
  if (!equiv(valores.registros_devueltos, op.registros)) faltantes.push('cantidad de registros devueltos');
  if (!Number.isFinite(Date.parse(valores.timestamp))
    || Date.parse(valores.timestamp) < Date.parse(op.desde) - 5000
    || Date.parse(valores.timestamp) > Date.parse(op.hasta) + 30000) faltantes.push('timestamp');
  if (![false, 'false', 0, '0', 'no', 'NO'].includes(valores.exportado)) faltantes.push('si se exportó');
  return { estado: faltantes.length ? 'RECHAZADO' : 'APROBADO',
    motivo: faltantes.length ? `Evento ${valores.id_evento ?? 'sin id'}: falta o discrepa ${faltantes.join(', ')}`
      : `Evento ${valores.id_evento ?? 'sin id'} contiene los datos exigidos por CA-16`,
    valores, faltantes };
}
