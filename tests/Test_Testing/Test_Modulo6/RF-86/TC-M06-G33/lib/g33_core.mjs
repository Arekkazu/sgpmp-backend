export const CASOS = ['TC-M06-005'];
export const IDS = ['G33-API-005-01', 'G33-API-005-02'];
export const PRESUPUESTO = Object.freeze({ solicitudes_totales: 60, logins_fuera_run: 2, eventos_m02: 2,
  precios: 0, disparos: 2, deletes: 1, timeout_login_ms: 120000,
  timeout_post_ms: 120000, timeout_ms: 30000, duracion_segundos: 900 });
export const CAPACIDADES = Object.freeze({ contrato: 'sigab-qa-ejecutor/1', grupo: 'G33', casos: CASOS,
  operaciones: ['evaluar', 'reintentar', 'reevaluar'], versiones: { min: 1, max: 99 },
  comprobaciones_obligatorias: { 'TC-M06-005': { API: IDS } },
  limite: { solicitudes_totales: 60, duracion_segundos: 900, timeout_post_ms: 120000 }, baja_automatizada: false });
export const casoCompleto = c => 'TC-M06-G33 / ' + c;
export const decimal = x => x == null || x === '' ? NaN : Number(x);
export const igualMonto = (a, b) => Number.isFinite(decimal(a)) && Number.isFinite(decimal(b)) && Math.abs(decimal(a) - decimal(b)) < 0.005;
const menciona = (texto, etiqueta, valor) => valor != null &&
  new RegExp('\\b' + etiqueta + '\\s*(?:#|id[:=]?\\s*)?' + String(valor) + '\\b', 'i').test(texto);
function avisoDelCaso(x, activoId, eventoId, identificadorActivo) {
  const texto = String(x.mensaje ?? '');
  const identificador = String(identificadorActivo ?? '');
  const patronIdentificador = identificador.length >= 3 &&
    new RegExp('(?:^|\\W)' + identificador.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '(?:$|\\W)', 'i').test(texto);
  return String(x.id_activo_biologico ?? '') === String(activoId) ||
    String(x.id_evento_productivo ?? x.id_referencia ?? '') === String(eventoId) ||
    (identificador && String(x.identificador_activo ?? '') === identificador) || patronIdentificador ||
    menciona(texto, 'activo', activoId) || menciona(texto, 'evento', eventoId);
}
function avisoDeError(x) {
  const texto = [x.mensaje, x.descripcion, x.tipo, x.tipo_notificacion, x.categoria, x.severidad]
    .filter(Boolean).join(' ');
  // MEDICION_PENDIENTE es un tipo real de M06; el id_evento de M01 pertenece a otra taxonomia.
  return /MEDICION_PENDIENTE|error|fallo|pendiente|critical|warning/i.test(texto);
}
export function oficialidadLocal(r, sinArtefactos = false) {
  return r.cierre?.rollback?.verificado === true && CASOS.every(k => ['APROBADO', 'RECHAZADO'].includes(r.casos?.[k]?.estado)) &&
    (sinArtefactos || (r.herramientas?.newman?.iteraciones === 1 && r.herramientas.newman.codigo === 0 &&
      (r.casos?.[CASOS[0]]?.estado === 'RECHAZADO' || r.herramientas.newman.fallos === 0)));
}
export function evaluarOraculo({ anterior, posterior, eventoId, activoId, identificadorActivo, periodoId }) {
  if (!anterior || !posterior || !Number.isInteger(Number(eventoId)))
    return { estado: 'NO_CONCLUYENTE', motivo: 'Falta lectura pública completa del caso.' };
  const claves = ['variaciones', 'lineas', 'mediciones', 'calculos', 'auditoria', 'bandeja'];
  if (claves.some(k => !Array.isArray(anterior[k]) || !Array.isArray(posterior[k])) || !posterior.auditoriaCompleta || !anterior.auditoriaCompleta || !posterior.bandejaCompleta || !anterior.bandejaCompleta)
    return { estado: 'NO_CONCLUYENTE', motivo: 'Falta lectura paginada completa de alguna línea base o resultado.' };
  const nuevos = (k, campo) => { const ids = new Set(anterior[k].map(x => String(x[campo]))); return posterior[k].filter(x => !ids.has(String(x[campo]))); };
  const hallazgos = [];
  const variaciones = nuevos('variaciones', 'id_variacion_valor_razonable').filter(x => Number(x.id_activo_biologico) === Number(activoId));
  const lineas = nuevos('lineas', 'id_linea_asiento_nic41').filter(x => Number(x.id_activo_biologico) === Number(activoId));
  const mediciones = nuevos('mediciones', 'id_medicion_posterior').filter(x => Number(x.id_activo_biologico) === Number(activoId));
  const calculos = nuevos('calculos', 'id_calculo_valor_razonable');
  const auditoria = nuevos('auditoria', 'id_evento');
  const sinVariacionObservadas = auditoria.filter(x => x.tipo_evento === 'MEDICION_SIN_VARIACION');
  const sinVariacion = sinVariacionObservadas.filter(x => String(x.id_referencia) === String(eventoId) && Number(x.id_activo_biologico) === Number(activoId) && Number(x.id_periodo_contable) === Number(periodoId) && x.severidad_evento === 'INFO');
  const alertas = auditoria.filter(x => ['WARNING', 'ERROR', 'CRITICAL'].includes(x.severidad_evento) || /PENDIENTE|FALLO|ERROR/.test(String(x.tipo_evento)));
  const avisosNuevos = posterior.bandeja;
  const avisos = avisosNuevos.filter(x => avisoDelCaso(x, activoId, eventoId, identificadorActivo) && avisoDeError(x));
  const avisosAjenos = avisosNuevos.filter(x => !avisoDelCaso(x, activoId, eventoId, identificadorActivo));
  const previo = anterior.calculoUltimo;
  const posteriorUltimo = posterior.calculoUltimo;
  const valorAuditoria = sinVariacion[0]?.payload_evento?.valor_neto;
  if (variaciones.length) hallazgos.push('Se creó variación del activo.');
  if (lineas.length) hallazgos.push('Se creó línea de asiento del activo.');
  if (mediciones.length || calculos.length || String(previo?.id_calculo_valor_razonable) !== String(posteriorUltimo?.id_calculo_valor_razonable)) hallazgos.push('Se creó medición o cálculo nuevo, o cambió el último cálculo.');
  if (!previo || !(decimal(previo.valor_neto) > 0) || !igualMonto(previo.valor_neto, posteriorUltimo?.valor_neto)) hallazgos.push('No se confirmó valor razonable anterior = nuevo > 0.');
  if (sinVariacion.length !== 1) hallazgos.push('Se esperó exactamente una auditoría MEDICION_SIN_VARIACION con referencia, período e INFO correctos.');
  if (sinVariacion.length === 1 && !igualMonto(valorAuditoria, previo.valor_neto)) hallazgos.push('El valor neto de la auditoría no coincide con el cálculo previo positivo.');
  if (alertas.length || avisos.length) hallazgos.push('Se emitió alerta de error en auditoría o bandeja.');
  return { estado: hallazgos.length ? 'RECHAZADO' : 'APROBADO', motivo: hallazgos.join(' ') || 'Ausencias y auditoría RF-94 conformes.',
    observados: { variaciones: variaciones.length, lineas: lineas.length, mediciones: mediciones.length, calculos: calculos.length,
      auditorias_sin_variacion: sinVariacion.length,
      auditorias_sin_variacion_detalle: sinVariacionObservadas.map(x => ({ id: x.id_evento,
        severidad: x.severidad_evento, referencia: x.id_referencia, periodo: x.id_periodo_contable })),
      alertas_auditoria: alertas.length, avisos_error: avisos.length,
      avisos_ajenos: avisosAjenos.length,
      avisos_relacionados_sin_error: avisosNuevos.length - avisosAjenos.length - avisos.length,
      valor_anterior: previo?.valor_neto, valor_nuevo: valorAuditoria ?? posteriorUltimo?.valor_neto,
      calculo_ultimo_antes: previo?.id_calculo_valor_razonable, calculo_ultimo_despues: posteriorUltimo?.id_calculo_valor_razonable } };
}
