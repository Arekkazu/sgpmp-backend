export const CASOS = ['TC-M06-001', 'TC-M06-002', 'TC-M06-003', 'TC-M06-004'];
export const IDS = CASOS.map((_, i) => `G32-API-${String(i + 1).padStart(3, '0')}-01`);
export const PRESUPUESTO = Object.freeze({
  solicitudes_totales: 150, logins_fuera_run: 2, escrituras_preparacion: 1,
  eventos_m02: 6, precios: 2, disparos: 6, trazabilidades: 2,
  lecturas: 130, deletes: 1, timeout_login_ms: 120000,
  timeout_post_ms: 120000, timeout_ms: 30000, duracion_segundos: 2400,
});
export const CAPACIDADES = Object.freeze({
  contrato: 'sigab-qa-ejecutor/1', grupo: 'G32', casos: CASOS,
  operaciones: ['evaluar', 'reintentar', 'reevaluar'], versiones: { min: 1, max: 99 },
  comprobaciones_obligatorias: Object.fromEntries(CASOS.map((c, i) => [c, { API: [IDS[i]] }])),
  limite: { solicitudes_totales: PRESUPUESTO.solicitudes_totales,
    duracion_segundos: PRESUPUESTO.duracion_segundos,
    timeout_post_ms: PRESUPUESTO.timeout_post_ms }, baja_automatizada: false,
});
export const casoCompleto = c => `TC-M06-G32 / ${c}`;
export const decimal = x => x === null || x === undefined || x === '' ? NaN : Number(x);
export const igualMonto = (a, b) => Number.isFinite(decimal(a)) && Number.isFinite(decimal(b))
  && Math.abs(decimal(a) - decimal(b)) < 0.005;
export function valoresEsperados(calculoPrevio, medicion, magnitudNueva) {
  const previo = decimal(calculoPrevio?.valor_neto), magnitudPrevia = decimal(calculoPrevio?.magnitud);
  const nueva = decimal(medicion?.valor_razonable_actual), magnitud = decimal(magnitudNueva);
  if (![previo, magnitudPrevia, nueva, magnitud].every(Number.isFinite) || magnitudPrevia <= 0 || magnitud <= 0)
    return null;
  const total = Number((nueva - previo).toFixed(4));
  const pm = calculoPrevio.unidad_magnitud === 'kg' ?
    Number((Number((nueva * magnitudPrevia / magnitud).toFixed(4)) - previo).toFixed(4)) : 0;
  return { transformacion: Number((total - pm).toFixed(4)), precio_mercado: pm, total,
    valor_razonable_anterior: previo, valor_razonable_nuevo: nueva, magnitud_anterior: magnitudPrevia,
    magnitud_nueva: magnitud };
}
export function oficialidadLocal(r, sinArtefactos = false) {
  return r.cierre?.rollback?.verificado === true &&
    CASOS.every(k => ['APROBADO', 'RECHAZADO'].includes(r.casos?.[k]?.estado)) &&
    (sinArtefactos || (r.herramientas?.newman?.iteraciones === 1 && r.herramientas.newman.fallos === 0));
}
export function evaluarOraculo(indice, { variaciones, medicion, evento, precio, cadenas, auditorias, periodoAbierto,
  estadoActivo, lineaPorVariacion, calculoPrevio, magnitudNueva, comprobarOrigen = true } = {}) {
  if (!Array.isArray(variaciones) || !medicion || !Number.isInteger(Number(evento)))
    return { estado: 'NO_CONCLUYENTE', motivo: 'Falta lectura pública completa de variaciones, medición o evento.' };
  const esperados = [
    ['GANANCIA_TRANSFORMACION_BIOLOGICA'], ['PERDIDA_TRANSFORMACION_BIOLOGICA'],
    ['GANANCIA_TRANSFORMACION_BIOLOGICA', 'PERDIDA_PRECIO_MERCADO'], ['GANANCIA_PRECIO_MERCADO'],
  ][indice].slice();
  const t = variaciones.map(v => v.tipo);
  const hallazgos = [];
  const tb = decimal(medicion.ganancia_perdida_transformacion), pm = decimal(medicion.ganancia_perdida_precio_mercado);
  const total = decimal(medicion.variacion_total);
  if (medicion.estado !== 'COMPLETADO')
    return { estado: medicion.estado ? 'RECHAZADO' : 'NO_CONCLUYENTE',
      motivo: `RF-83 no consta COMPLETADO para el evento; estado ${medicion.estado ?? 'sin lectura'}.` };
  if (![tb, pm, total].every(Number.isFinite))
    return { estado: hallazgos.length ? 'RECHAZADO' : 'NO_CONCLUYENTE', motivo: hallazgos.join(' ') || 'La medición no expone los componentes y el total.' };
  const calculados = valoresEsperados(calculoPrevio, medicion, magnitudNueva);
  if (!calculados)
    return { estado: 'NO_CONCLUYENTE', motivo: 'No se puede descomponer la variación con el cálculo previo y la magnitud nueva.' };
  const { total: totalCalculado, precio_mercado: pmCalculado, transformacion: tbCalculado } = calculados;
  if (Math.abs(tb - tbCalculado) > 0.005 || Math.abs(pm - pmCalculado) > 0.005 || Math.abs(total - totalCalculado) > 0.005)
    hallazgos.push(`Descomposición RF-83 distinta del cálculo previo: TB ${tbCalculado}, PM ${pmCalculado}, total ${totalCalculado}.`);
  const cambioPrecio = String(calculoPrevio.id_precio_mercado) !== String(precio);
  if (t.length !== esperados.length || [...t].sort().join('|') !== [...esperados].sort().join('|'))
    hallazgos.push(`Se esperaban ${esperados.join(' y ')}; se observaron ${t.join(' y ') || 'ninguna variación'}.`);
  const signos = [[tb > 0, pm === 0 && !cambioPrecio],
    [tb < 0, pm === 0 && !cambioPrecio],
    [tb > 0, pm < 0], [tb === 0, pm > 0]][indice];
  if (!signos.every(Boolean)) hallazgos.push(`Componentes inesperados: transformación ${tb}; precio ${pm}.`);
  if (!igualMonto(tb + pm, total)) hallazgos.push('La suma de componentes no coincide con el total entregado por RF-83.');
  for (const v of variaciones) {
    const esperado = v.tipo.includes('TRANSFORMACION') ? tb : pm;
    if (!igualMonto(v.monto_variacion, esperado))
      hallazgos.push(`Monto ${v.tipo} ${v.monto_variacion} distinto del componente ${esperado}.`);
    if (!(decimal(v.valor_razonable_anterior) > 0 && decimal(v.valor_razonable_nuevo) > 0))
      hallazgos.push(`VR anterior o nuevo inválido en variación ${v.id_variacion_valor_razonable}.`);
    if (!v.fecha_registro) hallazgos.push(`Sin timestamp en variación ${v.id_variacion_valor_razonable}.`);
    if (v.estado_trazabilidad !== 'VERIFICACION_PENDIENTE' && v.estado_inicial !== 'VERIFICACION_PENDIENTE')
      hallazgos.push(`Estado inicial no demostrado como VERIFICACION_PENDIENTE en ${v.id_variacion_valor_razonable}.`);
  }
  if (periodoAbierto !== true) hallazgos.push('El período no consta ABIERTO.');
  if (indice === 1 && estadoActivo !== 'EN_TRATAMIENTO') hallazgos.push('El activo no consta EN_TRATAMIENTO.');
  if (hallazgos.length) return { estado: 'RECHAZADO', motivo: hallazgos.join(' ') };
  if (!comprobarOrigen) return { estado: 'APROBADO', motivo: 'Tipos, montos, período y estado inicial conformes; origen pendiente de cadena RF-91.' };
  for (const v of variaciones) {
    const id = v.id_variacion_valor_razonable;
    const c = (cadenas ?? []).find(x => String(x.id_origen) === String(id));
    const ids = c?.eslabones?.ids ?? null;
    if (!ids) return { estado: 'RECHAZADO', motivo: `Origen no consultable por cadena RF-91 para la variación ${id}.` };
    if (v.tipo.includes('TRANSFORMACION')) {
      if (String(ids.id_evento) !== String(evento))
        return { estado: 'RECHAZADO', motivo: `La transformación ${id} no traza al evento M02 ${evento}.` };
    } else {
      if (precio == null) return { estado: 'NO_CONCLUYENTE', motivo: 'No hay id de precio RF-89 para confrontar el origen.' };
      if (String(ids.id_precio_mercado) !== String(precio))
        return { estado: 'RECHAZADO', motivo: `La variación de precio ${id} no traza al precio RF-89 ${precio}.` };
    }
    if (lineaPorVariacion?.[String(id)] !== true)
      return { estado: 'NO_CONCLUYENTE', motivo: `No se verificó línea de asiento de ${id}.` };
  }
  if (!Array.isArray(auditorias)) return { estado: 'NO_CONCLUYENTE', motivo: 'No se obtuvo auditoría pública de responsable.' };
  for (const v of variaciones) {
    const a = auditorias.find(x => String(x.id_referencia) === String(v.id_variacion_valor_razonable)
      && x.tipo_evento === 'VARIACION_REGISTRADA');
    if (!a) return { estado: 'NO_CONCLUYENTE', motivo: `Sin auditoría de la variación ${v.id_variacion_valor_razonable}.` };
    if (a.tipo_actor !== 'SISTEMA' || a.id_usuario != null || !a.id_sistema)
      return { estado: 'RECHAZADO', motivo: `La auditoría de ${v.id_variacion_valor_razonable} no identifica al proceso.` };
  }
  return { estado: 'APROBADO', motivo: `Se observaron ${variaciones.length} registros con tipos, montos, componentes, origen y responsable esperados.` };
}
