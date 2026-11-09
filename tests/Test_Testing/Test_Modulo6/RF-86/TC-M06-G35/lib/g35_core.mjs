export const CASO = 'TC-M06-008';
export const IDS = ['G35-API-008-01', 'G35-API-008-02', 'G35-API-008-03'];
export const PRESUPUESTO = Object.freeze({ solicitudes_totales: 80, duracion_segundos: 900,
  logins_fuera_run: 2, bajas: 1, procesamientos: 1, intentos_crecimiento: 2,
  timeout_login_ms: 120000, timeout_post_ms: 120000, timeout_ms: 30000 });
export const CAPACIDADES = Object.freeze({ contrato: 'sigab-qa-ejecutor/1', grupo: 'G35', casos: [CASO],
  operaciones: ['evaluar', 'reintentar', 'reevaluar'], versiones: { min: 1, max: 99 },
  comprobaciones_obligatorias: { [CASO]: { API: IDS } }, limite: PRESUPUESTO, baja_automatizada: true });
export const id = x => Number.isSafeInteger(Number(x)) && Number(x) > 0 ? Number(x) : null;
export const hoy = () => new Intl.DateTimeFormat('en-CA', { timeZone: 'America/Bogota', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date());
export const nuevos = (a, b, campo) => {
  if (!Array.isArray(a) || !Array.isArray(b)) return null;
  const base = new Set(a.map(x => String(x[campo])));
  return b.filter(x => !base.has(String(x[campo])));
};
export function periodoDestino(periodos, nit, dia = hoy()) {
  if (!nit) return null;
  const propios = periodos.filter(x => String(x.numero_id_tributaria) === String(nit));
  const actual = propios.find(x => x.fecha_inicio <= dia && x.fecha_fin >= dia);
  if (actual?.estado === 'ABIERTO') return actual;
  if (actual?.estado === 'EN_CIERRE') return null;
  const desde = actual?.fecha_fin ?? dia;
  return propios.filter(x => x.estado === 'ABIERTO' && x.fecha_inicio > desde)
    .sort((a, b) => String(a.fecha_inicio).localeCompare(String(b.fecha_inicio)))[0] ?? null;
}
export function calculoVigente(detalle) {
  const ultimo = (detalle?.calculos ?? []).filter(x => x.estado === 'CALCULADO' && x.json_metodo_costo?.es_producto !== true)
    .sort((a, b) => String(b.fecha_calculo).localeCompare(String(a.fecha_calculo)) ||
      id(b.id_calculo_valor_razonable) - id(a.id_calculo_valor_razonable))[0] ?? null;
  return Number(ultimo?.valor_neto) > 0 ? ultimo : null;
}
const asociado = (x, aid) => id(x.id_activo_biologico) === id(aid);
const errorTexto = x => [x?.codigo, x?.mensaje].filter(Boolean).join(' ');
export function evaluarPaso(paso, antes, despues, respuesta, aid, eventoBaja, valorBajaEsperado) {
  if (!antes?.completa || !despues?.completa || !respuesta || !Number.isSafeInteger(id(aid)))
    return { estado: 'NO_CONCLUYENTE', motivo: 'Lectura o respuesta incompleta.' };
  if (respuesta.http == null || respuesta.http >= 500)
    return { estado: 'NO_CONCLUYENTE', motivo: 'Solicitud sin respuesta o con 5xx; se conserva la conciliación sin atribuir defecto.' };
  const e = nuevos(antes.eventos, despues.eventos, 'id_eventos');
  const v = nuevos(antes.variaciones, despues.variaciones, 'id_variacion_valor_razonable')?.filter(x => asociado(x, aid));
  const l = nuevos(antes.lineas, despues.lineas, 'id_linea_asiento_nic41')?.filter(x => asociado(x, aid));
  const m = nuevos(antes.mediciones, despues.mediciones, 'id_medicion_posterior')?.filter(x => asociado(x, aid));
  if ([e, v, l, m].some(x => x === null)) return { estado: 'NO_CONCLUYENTE', motivo: 'Ausencias no comprobables.' };
  const fallas = [];
  if (paso === 'baja') {
    if (respuesta.http !== 201 || !eventoBaja || !e.some(x => id(x.id_eventos) === id(eventoBaja))) fallas.push('RF-45 no creó el evento de baja esperado.');
    if (despues.estado !== 'BAJA') fallas.push('El activo no quedó en BAJA.');
    if (v.length) fallas.push('La baja creó variación posterior.');
    if (!l.some(x => x.tipo_hecho === 'BAJA_ACTIVO' && id(x.id_origen) === id(eventoBaja))) fallas.push('Falta línea BAJA_ACTIVO ligada al evento RF-45.');
    if (!Number.isFinite(valorBajaEsperado) || valorBajaEsperado <= 0 ||
        !l.some(x => x.tipo_hecho === 'BAJA_ACTIVO' && id(x.id_origen) === id(eventoBaja) &&
          Number.isFinite(Number(x.valor)) && Math.abs(Number(x.valor) - valorBajaEsperado) < 0.005))
      fallas.push('La línea BAJA_ACTIVO no coincide con el valor en libros de la baja.');
    if (m.length) fallas.push('La baja creó medición posterior.');
  } else {
    const texto = errorTexto(respuesta);
    if (!(respuesta.http >= 400 && respuesta.http < 500)) fallas.push('El crecimiento no recibió rechazo 4xx.');
    if (!respuesta.codigo || !respuesta.mensaje) fallas.push('El rechazo carece de código o mensaje.');
    const patron = paso === 'baja_rechazo' ? /baja|estado.*(?:no permitido|inv[aá]lido)|no.*activo|terminal/i :
      /no existe|no encontrado|inexistente/i;
    if (!patron.test(texto)) fallas.push(paso === 'baja_rechazo' ? 'El rechazo no indica activo dado de baja o estado no permitido.' : 'El rechazo no indica activo inexistente.');
    if (e.length || v.length || l.length || m.length) fallas.push('El intento creó evento, variación, línea o medición.');
    if (paso === 'baja_rechazo' && despues.estado !== 'BAJA') fallas.push('Cambió el estado BAJA.');
  }
  return { estado: fallas.length ? 'RECHAZADO' : 'APROBADO', motivo: fallas.join(' ') || 'Se cumplen estado, vínculo, rechazo específico y ausencias.',
    observados: { activo_id: id(aid), evento_baja_id: id(eventoBaja), http: respuesta.http, codigo_error: respuesta.codigo ?? null,
      mensaje_saneado: respuesta.mensaje ?? null, eventos_nuevos: e.map(x => id(x.id_eventos)),
      variaciones_nuevas: v.map(x => id(x.id_variacion_valor_razonable)), lineas_nuevas: l.map(x => id(x.id_linea_asiento_nic41)),
      mediciones_nuevas: m.map(x => id(x.id_medicion_posterior)), estado_antes: antes.estado, estado_despues: despues.estado } };
}
export function resultadoFinal(pasos) {
  const estados = Object.values(pasos).map(x => x?.estado ?? 'NO_CONCLUYENTE');
  return estados.includes('RECHAZADO') ? 'RECHAZADO' : estados.every(x => x === 'APROBADO') ? 'APROBADO' : 'NO_CONCLUYENTE';
}
export function rollback(base, final, eventoBaja) {
  if (!base?.completa || !final?.completa) return { verificado: false, motivo: 'Lectura poscierre incompleta.' };
  const campos = [['eventos', 'id_eventos'], ['variaciones', 'id_variacion_valor_razonable'],
    ['lineas', 'id_linea_asiento_nic41'], ['mediciones', 'id_medicion_posterior'],
    ['calculos', 'id_calculo_valor_razonable'], ['auditoria', 'id_evento']];
  const residuos = campos.flatMap(([campo, clave]) => (nuevos(base[campo], final[campo], clave) ?? []).map(x => ({ tipo: campo, id: id(x[clave]) })));
  const verificado = base.estado === 'ACTIVO' && final.estado === 'ACTIVO' && !residuos.length &&
    !final.eventos.some(x => id(x.id_eventos) === id(eventoBaja)) &&
    !final.lineas.some(x => id(x.id_origen) === id(eventoBaja) && x.tipo_hecho === 'BAJA_ACTIVO');
  return { verificado, estado_original: base.estado, estado_final: final.estado, residuos,
    motivo: verificado ? 'ACTIVO restaurado; evento RF-45, línea y datos del RUN ausentes.' : 'Estado o registros del RUN persisten tras DELETE.' };
}
export function oficialidad(r) {
  return r.cierre?.rollback?.verificado === true && ['APROBADO', 'RECHAZADO'].includes(r.casos?.[CASO]?.estado) &&
    ['baja', 'baja_rechazo', 'inexistente'].every(k => ['APROBADO', 'RECHAZADO'].includes(r.casos?.[CASO]?.subcasos?.[k]?.estado)) &&
    IDS.every(id => r.comprobaciones.some(x => x.caso === CASO && x.id === id && ['APROBADO', 'RECHAZADO'].includes(x.estado))) &&
    r.herramientas?.newman?.iteraciones === 1;
}
