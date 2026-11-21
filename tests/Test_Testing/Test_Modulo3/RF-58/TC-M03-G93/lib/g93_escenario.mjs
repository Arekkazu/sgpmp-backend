export const CASO = 'TC-M03-184';
export const ORACULO = 'La unidad se muestra con estado GRIS y el mensaje "Sin datos disponibles", junto con la fecha del último dato histórico si existe; la unidad no desaparece del panel y no se devuelven errores 5xx ni valores fabricados.';
export const IDS = ['API-184-01', 'API-184-02', 'API-184-03', 'UI-184-01', 'UI-184-02'];
// Decisiones QA: INACTIVO (2026-10-25) y BUFFER_ACTIVO (2026-10-31) acreditan ausencia de señal.
export const ESTADOS_SIN_COMUNICACION = Object.freeze(['SIN_SEÑAL', 'INACTIVO', 'BUFFER_ACTIVO']);
export const IDS_PREFERIDOS_V2 = Object.freeze([1, 2, 3]);
export const IDS_DIAGNOSTICO = Object.freeze([349, 3, 390, 1, 2, 389, 268, 399, 337]);
export const CONSULTAS_DIAGNOSTICO = Object.freeze(['POST /sesiones/',
  ...IDS_DIAGNOSTICO.map(id => `GET /iot/monitoreo/dashboard?id_infraestructura=${id}&por_pagina=50`)]);
export const LIMITE = Object.freeze({ candidatas: 10, paginas_adicionales_v2: 12,
  solicitudes_directas: 56, margen_cierre: 5, ui_api: 25, newman: 1 });
export const CAPACIDADES = Object.freeze({
  contrato: 'sigab-qa-ejecutor/1', grupo: 'G93', casos: [CASO],
  operaciones: ['evaluar', 'reintentar', 'reevaluar', 'diagnostico'], versiones: { min: 1, max: 99 },
  solo_lectura: false, consultas: CONSULTAS_DIAGNOSTICO, max_peticiones: 30,
  comprobaciones_obligatorias: { [CASO]: { API: IDS.filter(x => x.startsWith('API-')), UI: IDS.filter(x => x.startsWith('UI-')) } },
  limite: LIMITE,
});

export function evaluarApi(variante, respuesta, id) {
  const j = respuesta?.cuerpo ?? {};
  const sensores = Array.isArray(j.sensores) ? j.sensores : [];
  const unidad = Array.isArray(j.resumen_unidades) ? j.resumen_unidades.find(x => Number(x.id_infraestructura) === Number(id)) : null;
  if (respuesta?.http == null) return { estado: 'NO_EJECUTADA', motivo: 'Sin respuesta API' };
  if (respuesta.http >= 500) return { estado: 'RECHAZADO', motivo: `HTTP ${respuesta.http}; la matriz prohíbe 5xx` };
  if (respuesta.http !== 200) return { estado: 'RECHAZADO', motivo: `HTTP ${respuesta.http}; esperado 200` };
  if (!unidad) return { estado: 'RECHAZADO', motivo: 'La unidad no figura en resumen_unidades' };
  if (unidad.estado_general !== 'GRIS') return { estado: 'RECHAZADO', motivo: `estado_general ${unidad.estado_general}; esperado GRIS` };
  if (variante === 'V1') {
    if (sensores.some(s => Number(s.id_infraestructura) === Number(id)) || Number(unidad.total_sensores) !== 0
      || unidad.mensaje_estado !== 'Sin datos disponibles')
      return { estado: 'RECHAZADO', motivo: 'Unidad nueva incumple cero sensores o mensaje de ausencia' };
    if (unidad.ultimo_dato_recibido != null && !Number.isFinite(Date.parse(unidad.ultimo_dato_recibido)))
      return { estado: 'RECHAZADO', motivo: 'Fecha histórica inválida en la unidad nueva' };
    return { estado: 'APROBADO', motivo: 'Unidad nueva presente, GRIS y sin valores actuales; fecha histórica válida si existe' };
  }
  const propios = sensores.filter(s => Number(s.id_infraestructura) === Number(id));
  if (!propios.length || propios.length !== Number(unidad.total_sensores)
    || propios.some(s => !ESTADOS_SIN_COMUNICACION.includes(s.estado_conectividad) || s.dato_desactualizado !== true))
    return { estado: 'NO_CONCLUYENTE', motivo: 'Los datos dejaron de acreditar que todos los sensores estén sin comunicación y desactualizados' };
  if (unidad.ultimo_dato_recibido != null && !Number.isFinite(Date.parse(unidad.ultimo_dato_recibido)))
    return { estado: 'RECHAZADO', motivo: 'Fecha histórica inválida en la unidad sin señal' };
  if (unidad.ultimo_dato_recibido && propios.some(s => s.ultimo_timestamp_captura && new Date(s.ultimo_timestamp_captura) > new Date(unidad.ultimo_dato_recibido)))
    return { estado: 'RECHAZADO', motivo: 'Un sensor presenta dato posterior al último histórico de la unidad' };
  return { estado: 'APROBADO', motivo: 'Unidad presente, GRIS, sin valores actuales fabricados; fecha histórica comprobada si existe' };
}

export function candidataV2(respuesta, id, opciones) {
  return revisarCandidataV2(respuesta, id, opciones).motivo === 'aceptada';
}

export function revisarCandidataV2(respuesta, id, { fincasVisibles = [], idAreaV1 = null,
  diagnostico = false } = {}) {
  const resultado = { id_infraestructura: Number(id), id_finca: null, total_sensores: null,
    estados_conectividad: {}, estados_originales: [], ultimo_dato_recibido: null, dato_desactualizado: {},
    tiempo_sin_reporte_min: {}, motivo: null };
  if (idAreaV1 != null && Number(id) === Number(idAreaV1)) resultado.motivo = 'area_v1';
  else if (respuesta?.http !== 200) resultado.motivo = `http_${respuesta?.http ?? 'sin_respuesta'}`;
  else {
    const j = respuesta.cuerpo ?? {};
    const sensores = Array.isArray(j.sensores) ? j.sensores.filter(x => Number(x.id_infraestructura) === Number(id)) : [];
    resultado.estados_originales = sensores.map(s => s.estado_conectividad);
    const u = (Array.isArray(j.resumen_unidades) ? j.resumen_unidades : [])
      .find(x => Number(x.id_infraestructura) === Number(id));
    if (!u) resultado.motivo = 'sin_resumen';
    else {
      resultado.id_finca = Number(u.id_finca);
      resultado.total_sensores = Number(u.total_sensores);
      resultado.ultimo_dato_recibido = u.ultimo_dato_recibido ?? null;
      for (const s of sensores) {
        const estado = s.estado_conectividad == null ? 'null' : String(s.estado_conectividad);
        resultado.estados_conectividad[estado] = (resultado.estados_conectividad[estado] ?? 0) + 1;
        const desactualizado = String(s.dato_desactualizado ?? 'NO_INFORMADO');
        resultado.dato_desactualizado[desactualizado] = (resultado.dato_desactualizado[desactualizado] ?? 0) + 1;
        const tiempo = String(s.tiempo_sin_reporte_min ?? 'NO_INFORMADO');
        resultado.tiempo_sin_reporte_min[tiempo] = (resultado.tiempo_sin_reporte_min[tiempo] ?? 0) + 1;
      }
      if (!Number.isSafeInteger(resultado.id_finca) || resultado.id_finca < 1
        || !diagnostico && !fincasVisibles.includes(resultado.id_finca)) resultado.motivo = 'finca_no_visible';
      else if (!Number.isSafeInteger(resultado.total_sensores) || resultado.total_sensores < 1) resultado.motivo = 'sin_sensores';
      else if (diagnostico && resultado.total_sensores > 50) resultado.motivo = 'paginacion_no_verificable_en_diagnostico';
      else if (sensores.length !== resultado.total_sensores) resultado.motivo = 'paginacion_incompleta';
      else if (sensores.some(s => !ESTADOS_SIN_COMUNICACION.includes(s.estado_conectividad))) resultado.motivo = 'sensor_fuera_estados_sin_comunicacion';
      else resultado.motivo = 'aceptada';
    }
  }
  return resultado;
}

export function clasificar(comprobaciones, { candidata, cierreVerificado }) {
  if (!cierreVerificado) return { estado: 'BLOQUEADO', motivo: 'Rollback no acreditado por lecturas públicas' };
  if (comprobaciones.some(x => x.tipo === 'ASSERT' && x.estado === 'RECHAZADO'))
    return { estado: 'RECHAZADO', motivo: 'Discrepancia del oráculo comprobada por API/UI pública' };
  if (!candidata) return { estado: 'BLOQUEADO', motivo: 'No hubo unidad existente con todos los sensores SIN_SEÑAL, INACTIVO o BUFFER_ACTIVO entre las candidatas acotadas; RF-60 depende de tarea periódica no forzable aquí' };
  if (comprobaciones.some(x => x.id.startsWith('UI') && x.estado === 'NO_CONCLUYENTE'))
    return { estado: 'NO_CONCLUYENTE', motivo: 'Carga UI sin respuesta acreditada o error de red; diagnóstico pendiente' };
  if (IDS.every(id => comprobaciones.some(x => x.id === id && x.estado === 'APROBADO')))
    return { estado: 'APROBADO', motivo: 'API y UI de ambas variantes verificadas' };
  return { estado: 'BLOQUEADO', motivo: 'Falta comprobación obligatoria API/UI o hubo error técnico' };
}
