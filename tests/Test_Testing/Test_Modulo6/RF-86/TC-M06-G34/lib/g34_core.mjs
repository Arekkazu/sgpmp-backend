export const CASOS = ['TC-M06-006'];
export const IDS = ['G34-API-006-A', 'G34-API-006-B', 'G34-UI-006-01'];
export const PRESUPUESTO = Object.freeze({ solicitudes_totales: 90, logins_fuera_run: 2, eventos_m02: 3,
  disparos: 3, put_costos: 3, timeout_login_ms: 120000, timeout_post_ms: 120000,
  timeout_ms: 30000, duracion_segundos: 1200 });
export const CAPACIDADES = Object.freeze({ contrato: 'sigab-qa-ejecutor/1', grupo: 'G34', casos: CASOS,
  operaciones: ['evaluar', 'reintentar', 'reevaluar'], versiones: { min: 1, max: 99 },
  comprobaciones_obligatorias: { 'TC-M06-006': { API: IDS.slice(0, 2), UI: [IDS[2]] } },
  limite: { solicitudes_totales: 90, duracion_segundos: 1200, timeout_post_ms: 120000 }, baja_automatizada: false });
export const casoCompleto = c => 'TC-M06-G34 / ' + c;
export const numero = x => x == null || x === '' ? NaN : Number(x);
export const igualMonto = (a,b) => Number.isFinite(numero(a)) && Number.isFinite(numero(b)) && Math.abs(numero(a)-numero(b)) < .005;
export const soloNuevo = (a,b,k) => { const ids = new Set(a.map(x => String(x[k]))); return b.filter(x => !ids.has(String(x[k]))); };
export function medicionesConEstado(historial, periodo, activo) {
  const estados = new Map(periodo.map(x => [String(x.id_medicion_posterior), x.estado]));
  // El historial está acotado por /finanzas/activos/{id}; sus filas omiten id_activo_biologico.
  return historial.filter(x => x.id_activo_biologico == null || String(x.id_activo_biologico) === String(activo))
    .map(x => ({ ...x, id_activo_biologico: activo,
      estado: estados.get(String(x.id_medicion_posterior)) ?? null }));
}
export function costosDe(config, especie) {
  const x = config?.costos_venta?.find(v => String(v.id_especie) === String(especie) &&
    v.es_activo === true && String(v.region).toUpperCase() === 'GENERAL');
  if (!x || !['pct_transporte','pct_comisiones','pct_impuestos'].every(k => Number.isFinite(numero(x[k])))) return null;
  return Object.fromEntries(['pct_transporte','pct_comisiones','pct_impuestos'].map(k => [k, String(x[k])]));
}
export const mismosCostos = (a,b) => !!a && !!b && Object.keys(a).every(k => igualMonto(a[k],b[k]));
const causaAviso = x => /RF_83_NO_COMPLETADO|medici[oó]n\s+(?:no\s+completada|sin\s+completar|pendiente)|no\s+se\s+complet[oó]\s+la\s+medici[oó]n/i
  .test(String(x.mensaje ?? ''));
export function evaluarA(base, post, { activo, periodo, evento, identificador }) {
  if (!base?.completa || !post?.completa) return { estado: 'NO_CONCLUYENTE', fallos: ['Lectura incompleta de A.'] };
  const campos = { variaciones:'id_variacion_valor_razonable', lineas:'id_linea_asiento_nic41',
    mediciones:'id_medicion_posterior', calculos:'id_calculo_valor_razonable' };
  const nuevos = Object.fromEntries(Object.entries(campos).map(([k,v]) => [k,
    soloNuevo(base[k],post[k],v).filter(x => k === 'calculos' || String(x.id_activo_biologico) === String(activo)).map(x => x[v])]));
  const auditorias = soloNuevo(base.auditoria,post.auditoria,'id_evento').map(x => ({
    id:x.id_evento,tipo:x.tipo_evento,severidad:x.severidad_evento,motivo:x.payload_evento?.motivo,
    referencia:x.id_referencia,evento_payload:x.payload_evento?.id_evento,activo:x.id_activo_biologico,periodo:x.id_periodo_contable }));
  const pendientes = auditorias.filter(x => x.tipo === 'MEDICION_PENDIENTE' && String(x.activo) === String(activo)
    && String(x.periodo) === String(periodo) && (String(x.referencia) === String(evento) ||
      String(x.evento_payload) === String(evento)) && x.motivo === 'VALOR_NETO_NO_POSITIVO');
  const vinculados = post.bandeja.filter(x => {
    const mensaje=String(x.mensaje ?? '');
    return (String(x.id_activo_biologico) === String(activo) ||
      (identificador != null && String(identificador).length>=3 && mensaje.includes(String(identificador))) ||
      new RegExp('activo\\s*#?\\s*'+String(activo)+'(?!\\d)','i').test(mensaje)) &&
      (String(x.id_referencia) === String(evento) || String(x.id_evento_productivo) === String(evento) ||
        new RegExp('evento\\s*#?\\s*'+String(evento)+'(?!\\d)','i').test(mensaje));
  });
  const validos = vinculados.filter(causaAviso);
  const avisos = post.bandeja.map(x=>({id:x.id_notificacion,
    causa_rf83:causaAviso(x),
    vinculado:vinculados.includes(x)}));
  const fallos = [];
  if (Object.values(nuevos).some(x => x.length)) fallos.push('A creó variación, línea, medición o cálculo.');
  if (pendientes.length !== 1) fallos.push('A sin auditoría MEDICION_PENDIENTE con motivo, activo, período y evento.');
  if (!validos.length) fallos.push('Falta aviso al Contador QA con causa, activo y evento.');
  return { estado: fallos.length ? 'RECHAZADO' : 'APROBADO', fallos,
    observado: { nuevos, auditorias, avisos, avisos_relacionados:vinculados.length, avisos_validos:validos.length,
      bandeja_linea_base:base.bandejaLineaBase } };
}
export function evaluarB(base, post, { activo, evento, periodo, calculoPrevio, pesoNuevo }) {
  if (!base?.completa || !post?.completa) return { estado:'NO_CONCLUYENTE', fallos:['Lectura incompleta de B.'] };
  if (String(base.activo ?? activo) !== String(activo) || String(post.activo ?? activo) !== String(activo))
    return { estado:'NO_CONCLUYENTE', fallos:['Instantánea B pertenece a otro activo.'] };
  const variaciones = soloNuevo(base.variaciones,post.variaciones,'id_variacion_valor_razonable')
    .filter(x => String(x.id_activo_biologico) === String(activo));
  const mediciones = soloNuevo(base.mediciones,post.mediciones,'id_medicion_posterior')
    .filter(x => String(x.id_activo_biologico) === String(activo) && String(x.id_evento) === String(evento));
  const lineas = soloNuevo(base.lineas,post.lineas,'id_linea_asiento_nic41')
    .filter(x => String(x.id_activo_biologico) === String(activo));
  const m = mediciones.find(x => String(x.id_evento) === String(evento));
  const v = variaciones.find(x => x.tipo === 'GANANCIA_TRANSFORMACION_BIOLOGICA');
  const previo = numero(calculoPrevio?.valor_neto), magnitud = numero(calculoPrevio?.magnitud);
  const esperado = Number.isFinite(previo) && magnitud > 0 ? Number((previo * (numero(pesoNuevo)/magnitud-1)).toFixed(4)) : NaN;
  const fallos = [];
  if (variaciones.length !== 1 || !v) fallos.push('B sin una GANANCIA_TRANSFORMACION_BIOLOGICA única y sin PM.');
  if (!m || m.estado !== 'COMPLETADO') fallos.push('Medición RF-83 de B no consta COMPLETADO para el evento.');
  if (!(esperado > 0) || !igualMonto(v?.monto_variacion,esperado) || !igualMonto(m?.ganancia_perdida_transformacion,esperado)
    || !igualMonto(m?.ganancia_perdida_precio_mercado,0)) fallos.push('Monto TB o componente PM de B discrepante.');
  if (!lineas.some(x => String(x.id_origen) === String(v?.id_variacion_valor_razonable) ||
    String(x.id_variacion_valor_razonable) === String(v?.id_variacion_valor_razonable))) fallos.push('B sin línea de asiento acreditada.');
  return { estado:fallos.length ? 'RECHAZADO':'APROBADO', fallos,
    observado:{ variaciones:variaciones.map(x=>({id:x.id_variacion_valor_razonable,tipo:x.tipo,monto:x.monto_variacion,
      id_linea:x.id_linea})),mediciones:mediciones.map(x=>({id:x.id_medicion_posterior,evento:x.id_evento,estado:x.estado,
      tb:x.ganancia_perdida_transformacion,pm:x.ganancia_perdida_precio_mercado})),
      lineas:lineas.map(x => x.id_linea_asiento_nic41),monto_esperado:esperado,evento } };
}
export function oficialidadLocal(r, sinArtefactos = false) {
  return r.cierre?.rollback?.verificado === true && r.cierre?.costos?.restaurados === true &&
    r.cypress?.total_pruebas > 0 && r.cypress?.total_failed === 0 && r.cypress?.captura === true &&
    ['APROBADO','RECHAZADO'].includes(r.casos?.[CASOS[0]]?.estado) &&
    (sinArtefactos || (r.herramientas?.newman?.iteraciones === 1 && r.herramientas.newman.codigo === 0 &&
      (r.casos?.[CASOS[0]]?.estado === 'RECHAZADO' || r.herramientas.newman.fallos === 0)));
}
