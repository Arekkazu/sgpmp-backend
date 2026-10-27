export const CASOS = ['TC-M03-249', 'TC-M03-250', 'TC-M03-254'];
export const IDS = ['API-249-01', 'API-250-01', 'API-254-01'];
// Login + 2 historiales iniciales + dashboard global + 8 unidades + 12 historiales + DELETE = 25.
export const PRESUPUESTO = Object.freeze({ solicitudes_directas: 25, solicitudes_newman: 3,
  margen_cierre: 1, duracion_segundos: 720, inactividad_maxima_segundos: 120,
  timeout_ms: 30000, timeout_seleccion_ms: 20000, unidades_dashboard: 8,
  unidades_conocidas: Object.freeze([1, 268, 337]), historiales_descubrimiento: 12,
  max_bytes_respuesta: 20_000_000 });
export const CAPACIDADES = Object.freeze({ contrato: 'sigab-qa-ejecutor/1', grupo: 'G124', casos: CASOS,
  operaciones: ['evaluar', 'reintentar', 'reevaluar'], versiones: { min: 1, max: 99 },
  comprobaciones_obligatorias: {
    'TC-M03-249': { API: ['API-249-01'] },
    'TC-M03-250': { API: ['API-250-01'] },
    'TC-M03-254': { API: ['API-254-01'] },
  },
  limite: { solicitudes_directas: PRESUPUESTO.solicitudes_directas,
    margen_cierre: PRESUPUESTO.margen_cierre, duracion_segundos: PRESUPUESTO.duracion_segundos,
    inactividad_maxima_segundos: PRESUPUESTO.inactividad_maxima_segundos },
});
export const ORACULOS = {
  'TC-M03-249': 'PDF con encabezado de metadatos (granja, periodo, filtros aplicados, usuario), gráfica de tendencia, tabla de registros con estado de semáforo, resumen estadístico y pie de página con timestamp de generación.',
  'TC-M03-250': 'Excel con hoja 1 de datos crudos con todos los campos, hoja 2 de resumen estadístico por variable y hoja 3 de alertas correlacionadas, con metadatos en el encabezado de cada hoja.',
  'TC-M03-254': 'PDF de 5.000 y Excel de 50.000 registros se procesan; a 5.001 y 50.001 se fragmenta la exportación y se informa al usuario.',
};
export const ruta = (tipo, { inicio, fin, sensorId }) => {
  const base = tipo === 'historial' ? '/iot/monitoreo/historial' : '/iot/monitoreo/historial/exportar';
  const q = new URLSearchParams({ ...(tipo !== 'historial' ? { formato: tipo } : {}),
    fecha_inicio: inicio, fecha_fin: fin, sensor_id: String(sensorId),
    ...(tipo === 'EXCEL' ? { incluir_alertas: 'true' } : {}),
    ...(tipo === 'historial' ? { pagina: '1', por_pagina: '20', orden: 'DESC' } : {}) });
  return `${base}?${q}`;
};

export function clasificarExportacion({ http, eco, error, bytes, validacion }, formato) {
  if (http == null) return { estado: 'NO_CONCLUYENTE', motivo: 'Sin respuesta de exportación' };
  if (!eco) return { estado: 'NO_CONCLUYENTE', motivo: `Exportación ${formato} sin eco de RUN` };
  if (http === 503 && error?.codigo === 'M08_NO_DISPONIBLE') return { estado: 'BLOQUEADO', subtipo: 'REQUISITO_DEPENDIENTE',
    motivo: 'M08 RF-10 no disponible: no se puede comprobar la estructura del archivo exigida por RF-59 CA-10/CA-11' };
  if (http === 200) {
    if (!bytes?.length) return { estado: 'RECHAZADO', motivo: `HTTP 200 sin archivo ${formato}` };
    const firma = formato === 'PDF' ? bytes.subarray(0, 5).toString() === '%PDF-'
      : bytes.subarray(0, 2).toString() === 'PK';
    if (!firma || /inválido|incompleto|sin directorio ZIP/i.test(validacion?.motivo ?? ''))
      return { estado: 'RECHAZADO', motivo: `HTTP 200 sin archivo ${formato} íntegro` };
    if (!validacion?.verificable) return { estado: 'NO_CONCLUYENTE', motivo: `${formato} no inspeccionable: ${validacion?.motivo ?? 'sin validador'}` };
    const faltan = Object.entries(validacion.checks).filter(([, ok]) => !ok).map(([k]) => k);
    return faltan.length ? { estado: 'RECHAZADO', motivo: `${formato} incumple ${faltan.join(', ')}` }
      : { estado: 'APROBADO', motivo: `Archivo ${formato} inspeccionado con estructura exigida` };
  }
  if (http >= 500 && (!error?.mensaje || !/redu(c|z)|rango|filtro/i.test(error.mensaje)))
    return { estado: 'RECHAZADO', motivo: `HTTP ${http} sin orientación E5 para reducir rango o filtros; código ${error?.codigo ?? 'ausente'}` };
  if (http >= 500) return { estado: 'NO_CONCLUYENTE', motivo: `HTTP ${http}; E5 requiere comprobar aviso, bitácora y datos visibles` };
  if (http === 400 && error?.codigo === 'EXPORTAR_SIN_FILTROS')
    return { estado: 'RECHAZADO', motivo: 'HTTP 400 EXPORTAR_SIN_FILTROS pese a sensor_id y periodo validados por historial público' };
  return { estado: 'NO_CONCLUYENTE', motivo: `HTTP ${http}; revisar petición/permisos antes de atribuir defecto al producto` };
}

export function clasificarVolumen(pdf, excel, total) {
  if (!Number.isSafeInteger(total) || total < 1) return { estado: 'BLOQUEADO',
    motivo: 'No hay resultados comprobados para preparar una consulta de exportación válida' };
  if ([pdf, excel].some(x => x.estado === 'BLOQUEADO' && x.subtipo === 'REQUISITO_DEPENDIENTE'))
    return { estado: 'BLOQUEADO', subtipo: 'REQUISITO_DEPENDIENTE',
      motivo: 'M08 RF-10 no genera archivos; no se pueden comprobar los umbrales 5.000/5.001 PDF y 50.000/50.001 Excel' };
  return { estado: 'NO_CONCLUYENTE', motivo: 'No se ejecutaron los cuatro volúmenes exactos; se requieren conjuntos reales acotados y M08 disponible' };
}
