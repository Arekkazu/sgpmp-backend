export const CASOS = Object.freeze([198, 199, 223, 224].map(n => `TC-M04-${n}`));
export const IDS = Object.freeze([198, 199, 223, 224].map(n => `API-${n}-01`));
export const FUENTES = Object.freeze(['OBSERVACION_DIRECTA', 'LABORATORIO', 'HISTORIAL_CLINICO', 'OTRO']);
export const OBSERVACION = 'Evaluación clínica: ñandú, pulmón y corazón; ¿sí? ¡Sí!\nSin datos personales.';
// 1 login + 4 activos + 128 historial descubrimiento + 8 versiones + 1 catálogo
// + 20 POST (10 iniciales, 10 reemplazos) + 30 historial verificación
// + 10 auditoría + 1 login administrador + 10 relecturas auditoría
// + 1 DELETE + 30 historial poscierre = 244 solicitudes máximas.
export const PRESUPUESTO = Object.freeze({ solicitudes_totales: 244, paginas_activos: 4,
  activos_maximos: 32, paginas_historial_descubrimiento: 4, versiones_maximas: 8,
  paginas_historial_verificacion: 3, reemplazos_por_registro: 1, dias_busqueda: 88,
  timeout_login_ms: 120000, timeout_ms: 30000, duracion_segundos: 900 });
export const CAPACIDADES = Object.freeze({ contrato: 'sigab-qa-ejecutor/1', grupo: 'G065',
  casos: CASOS, operaciones: ['evaluar', 'reintentar', 'reevaluar', 'recuperar'],
  versiones: { min: 1, max: 99 },
  comprobaciones_obligatorias: Object.fromEntries(CASOS.map((c, i) => [c, { API: [IDS[i]] }])),
  limite: { solicitudes_totales: PRESUPUESTO.solicitudes_totales,
    duracion_segundos: PRESUPUESTO.duracion_segundos } });
export const REGISTROS = Object.freeze([
  { caso: CASOS[3], clave: '224-invalida', estado: 'INCORRECTO', fuente: 'RESONANCIA_MAGNETICA' },
  { caso: CASOS[2], clave: '223-incorrecto', estado: 'INCORRECTO' },
  { caso: CASOS[2], clave: '223-parcial', estado: 'PARCIAL' },
  { caso: CASOS[2], clave: '223-contraste', estado: 'PARCIAL', fuente: 'LABORATORIO' },
  ...FUENTES.map((fuente, i) => ({ caso: CASOS[1], clave: `199-${i + 1}`, estado: 'INCORRECTO', fuente })),
  { caso: CASOS[0], clave: '198-con', estado: 'CORRECTO', observaciones: OBSERVACION },
  { caso: CASOS[0], clave: '198-sin', estado: 'CORRECTO' }
]);
export function usuarioDelToken(token) {
  try { const sub = JSON.parse(Buffer.from(String(token).split('.')[1], 'base64url')).sub;
    return /^\d+$/.test(String(sub)) ? String(sub) : null; } catch { return null; }
}
export function tipoModelo(e, versiones = {}) {
  return e?.payload?.tipo_modelo ?? versiones[String(e?.payload?.id_version_modelo)] ?? null;
}
export function diagnosticar(eventos, usuarioId, versiones = {}) {
  const propias = new Set(eventos.filter(e => e.tipo_evento === 'RETROALIMENTACION'
    && usuarioId != null && String(e.payload?.id_usuario_veterinario) === usuarioId)
    .map(e => String(e.id_resultado_inferencia)));
  const porTipo = {}, porModelo = {};
  for (const e of eventos) { porTipo[e.tipo_evento] = (porTipo[e.tipo_evento] ?? 0) + 1;
    if (e.tipo_evento === 'INFERENCIA') {
      const t = tipoModelo(e, versiones) ?? 'sin_tipo'; porModelo[t] = (porModelo[t] ?? 0) + 1;
    } }
  return { eventos: eventos.length, por_tipo: porTipo, por_modelo: porModelo,
    retroalimentadas_por_usuario: propias.size };
}
export function seleccionar(eventos, patologias, usados, usuarioId, versiones, inicio, fin) {
  const propias = new Set(eventos.filter(e => e.tipo_evento === 'RETROALIMENTACION'
    && usuarioId != null && String(e.payload?.id_usuario_veterinario) === usuarioId)
    .map(e => String(e.id_resultado_inferencia)));
  const modelos = new Set(['MODELO_ESPECIES_MEDIANAS', 'MODELO_ESPECIES_GRANDES']);
  return eventos.filter(e => e.tipo_evento === 'INFERENCIA' && modelos.has(tipoModelo(e, versiones))
    && !propias.has(String(e.id_resultado_inferencia)) && !usados.has(String(e.id_resultado_inferencia))
    && Number.isFinite(Date.parse(e.fecha_evento)) && Date.parse(e.fecha_evento) <= Date.now()
    && Date.parse(e.fecha_evento) >= Date.parse(inicio)
    && Date.parse(e.fecha_evento) <= Date.parse(fin + 'T23:59:59.999Z')
    && patologias.some(p => p.es_activo && ['TODAS', String(e.id_especie)].includes(String(p.especie_aplicable))))
    .sort((a, b) => Date.parse(b.fecha_evento) - Date.parse(a.fecha_evento));
}
export function verificarRegistro(reg, post, historial, auditoria, usuarioId) {
  if (post?.http == null) return { estado: 'NO_CONCLUYENTE', motivo: 'POST sin respuesta; conciliar antes de reintentar' };
  if (post.http === 403) return { estado: 'BLOQUEADO', motivo: 'HTTP 403 de clave o permiso' };
  if (post.http === 409 && post.cuerpo?.error_code === 'RETROALIMENTACION_DUPLICADA')
    return { estado: 'NO_CONCLUYENTE', motivo: 'Resultado ocupado por el mismo Veterinario' };
  if (post.http === 422 && post.cuerpo?.error_code === 'FUERA_DE_VENTANA_TEMPORAL')
    return { estado: 'NO_CONCLUYENTE', motivo: 'Resultado fuera de la ventana configurada' };
  const fallos = [], dudas = [], b = post.cuerpo ?? {};
  const invalid = reg.clave === '224-invalida';
  if (post.eco !== true) dudas.push('POST sin eco del RUN');
  if (invalid ? ![400, 422].includes(post.http) : post.http !== 201)
    fallos.push(`HTTP ${post.http}; esperado ${invalid ? 'rechazo 400 o 422' : 201}`);
  if (invalid) {
    if ([400, 422].includes(post.http)) {
      const texto = `${b.message ?? ''} ${JSON.stringify(b.fields ?? [])}`;
      if (!texto.includes('fuente_diagnostico') || !FUENTES.every(f => texto.includes(f)))
        fallos.push('rechazo sin campo y catálogo admitido');
    }
    if (historial?.http === 200 && historial.eco === true && historial.completo)
      { if (historial.eventos.some(e => e.tipo_evento === 'RETROALIMENTACION'
        && String(e.id_resultado_inferencia) === String(reg.dato.id_resultado_inferencia)
        && String(e.payload?.id_usuario_veterinario) === String(usuarioId))) fallos.push('persistió registro inválido'); }
    else dudas.push('historial no concluyente para ausencia');
    if (auditoria?.http === 200 && auditoria.eco === true && auditoria.completo) {
      if (auditoria.items.some(e => e.tipo_evento === 'RETROALIMENTACION_REGISTRADA'
        && String(e.payload_evento?.id_resultado_inferencia) === String(reg.dato.id_resultado_inferencia)))
        fallos.push('se auditó registro inválido');
    } else dudas.push('auditoría no concluyente para ausencia');
  } else if (post.http === 201) {
    if (!b.id_retroalimentacion || String(b.id_resultado_inferencia) !== String(reg.dato.id_resultado_inferencia))
      fallos.push('identidad de retroalimentación incorrecta');
    if (b.estado_retroalimentacion !== reg.estado) fallos.push('estado distinto');
    const evento = historial?.eventos?.find(e => e.tipo_evento === 'RETROALIMENTACION'
      && String(e.id_evento) === String(b.id_retroalimentacion));
    const audit = auditoria?.items?.find(e => e.tipo_evento === 'RETROALIMENTACION_REGISTRADA'
      && String(e.id_referencia) === String(b.id_retroalimentacion));
    if (historial?.http !== 200 || historial.eco !== true || !historial.completo) dudas.push('historial incompleto');
    else if (!evento) fallos.push('retroalimentación ausente del historial');
    if (auditoria?.http !== 200 || auditoria.eco !== true || !auditoria.completo) dudas.push('auditoría incompleta');
    else if (!audit) fallos.push('retroalimentación ausente de auditoría');
    if (reg.caso === CASOS[0]) {
      if (evento && (evento.payload?.observaciones_clinicas ?? null) !== (reg.observaciones ?? null))
        fallos.push('observaciones no persistidas íntegras');
    } else {
      if (b.fuente_diagnostico !== (reg.fuente ?? null)) fallos.push('fuente distinta en respuesta');
      if (audit && audit.payload_evento?.fuente_diagnostico !== (reg.fuente ?? null))
        fallos.push('fuente no persistida en auditoría');
      const marca = !reg.fuente;
      if (b.es_fuente_desconocida !== marca) fallos.push('marca distinta en respuesta');
      if (audit && !Object.hasOwn(audit.payload_evento ?? {}, 'es_fuente_desconocida'))
        dudas.push('marca ausente en auditoría');
      else if (audit && audit.payload_evento?.es_fuente_desconocida !== marca)
        fallos.push('marca distinta en auditoría');
    }
  }
  return { estado: fallos.length ? 'RECHAZADO' : dudas.length ? 'NO_CONCLUYENTE' : 'APROBADO',
    motivo: fallos.join('; ') || dudas.join('; ') || (invalid && post.http === 400
      ? 'Rechazo completo sin persistencia; observación: HTTP 400 en lugar del 422 recomendado'
      : 'HTTP, historial y auditoría concordantes') };
}
