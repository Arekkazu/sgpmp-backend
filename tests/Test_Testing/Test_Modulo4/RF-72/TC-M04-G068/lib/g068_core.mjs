export const CASOS = ['TC-M04-210', 'TC-M04-211', 'TC-M04-245'];
export const IDS = CASOS.map(c => `API-${c.slice(-3)}-01`);
// 2 logins (veterinario y administrador opcional) + 8 páginas de activos
// + 2 lecturas iniciales del 885 + 4 páginas de historial del 885 + 8 versiones
// + 8 solicitudes Newman
// (210, 211, reemplazo, baja veterinario, baja administrador, estado, bitácora, 245)
// + 1 lectura de fases durante la baja + 9 páginas de historial de verificación
// + 3 auditorías + 1 DELETE + 9 páginas de historial poscierre + 2 lecturas poscierre = 57.
export const PRESUPUESTO = Object.freeze({ solicitudes_totales: 57, paginas_activos: 4,
  paginas_descubrimiento: 4, versiones_maximas: 8,
  paginas_verificacion: 3, reemplazos_por_caso: 1, dias_busqueda: 88,
  timeout_login_ms: 120000, timeout_ms: 30000, duracion_segundos: 900 });
export const CAPACIDADES = Object.freeze({ contrato: 'sigab-qa-ejecutor/1', grupo: 'G068',
  casos: CASOS, operaciones: ['evaluar','reintentar','reevaluar','recuperar'],
  versiones: { min: 1, max: 99 },
  comprobaciones_obligatorias: Object.fromEntries(CASOS.map((c,i) => [c,{ API:[IDS[i]] }])),
  limite: { solicitudes_totales: PRESUPUESTO.solicitudes_totales, duracion_segundos: 900 },
  baja_automatizada: true });
export function usuarioDelToken(token) {
  try { const sub = JSON.parse(Buffer.from(String(token).split('.')[1], 'base64url')).sub;
    return /^\d+$/.test(String(sub)) ? String(sub) : null; } catch { return null; }
}
export const tipoModelo = (e, versiones={}) => e?.payload?.tipo_modelo
  ?? versiones[String(e?.payload?.id_version_modelo)] ?? null;
export function seleccionar(eventos, usuarioId, versiones, inicio) {
  const propias = new Set(eventos.filter(e => e.tipo_evento === 'RETROALIMENTACION'
    && String(e.payload?.id_usuario_veterinario) === String(usuarioId))
    .map(e => String(e.id_resultado_inferencia)));
  return eventos.filter(e => e.tipo_evento === 'INFERENCIA'
    && e.id_activo_biologico === 885
    && ['MODELO_ESPECIES_MEDIANAS','MODELO_ESPECIES_GRANDES'].includes(tipoModelo(e, versiones))
    && !propias.has(String(e.id_resultado_inferencia))
    && Date.parse(e.fecha_evento) >= Date.parse(inicio)
    && Date.parse(e.fecha_evento) <= Date.now())
    .sort((a,b) => Date.parse(b.fecha_evento) - Date.parse(a.fecha_evento));
}
const texto = b => `${b?.message ?? ''} ${(b?.fields ?? []).map(f => `${f.field ?? ''} ${f.message ?? ''}`).join(' ')}`.toLowerCase();
export function decidir(caso, post, historial, auditoria, resultado, usuarioId) {
  if (!post || post.http == null) return { estado: 'NO_CONCLUYENTE', motivo: 'POST sin respuesta; conciliación requerida' };
  const fallos = [], dudas = [], t = texto(post.cuerpo);
  if (post.eco !== true) dudas.push('sin eco de X-Test-Run-Id');
  if (caso === CASOS[0]) {
    if (post.http !== 404) fallos.push(`HTTP ${post.http}; E1 exige 404`);
    if (!/resultado de inferencia no existe o no est[aá] disponible/.test(t))
      fallos.push('mensaje distinto de E1');
  } else if (caso === CASOS[1]) {
    if (!(post.http >= 400 && post.http < 500)) fallos.push(`HTTP ${post.http}; se exige rechazo 4xx`);
    if (!/activo biol[oó]gico no corresponde al resultado/.test(t))
      fallos.push('rechazo sin significado de activo distinto');
  } else if (caso === CASOS[2]) {
    if (!(post.http >= 400 && post.http < 500)) fallos.push(`HTTP ${post.http}; se exige rechazo 4xx`);
    if (post.http >= 400 && post.http < 500 && !/baja|inv[aá]lido|estado|activo biol[oó]gico/.test(t))
      fallos.push('rechazo sin significado de activo dado de baja o inválido');
  }
  const eventos = (historial?.eventos ?? []).filter(e => e.tipo_evento === 'RETROALIMENTACION'
    && String(e.id_resultado_inferencia) === String(resultado)
    && String(e.payload?.id_usuario_veterinario) === String(usuarioId));
  const audits = (auditoria?.items ?? []).filter(e => e.tipo_evento === 'RETROALIMENTACION_REGISTRADA'
    && String(e.payload_evento?.id_resultado_inferencia) === String(resultado));
  if (historial?.http !== 200 || historial.eco !== true || !historial.completo) dudas.push('historial incompleto');
  else if (eventos.length) fallos.push('retroalimentación persistida');
  if (auditoria?.http !== 200 || auditoria.eco !== true || !auditoria.completo) dudas.push('auditoría incompleta');
  else if (audits.length) fallos.push('evento RETROALIMENTACION_REGISTRADA');
  const conforme = caso === CASOS[0]
    ? `HTTP ${post.http} ${post.cuerpo?.error_code ?? 'sin código'} con el mensaje «${post.cuerpo?.message ?? 'sin mensaje'}»; sin retroalimentación ni RETROALIMENTACION_REGISTRADA en historial y auditoría`
    : caso === CASOS[1]
      ? `rechazo HTTP ${post.http} ${post.cuerpo?.error_code ?? 'sin código'} con el mensaje «${post.cuerpo?.message ?? 'sin mensaje'}»; sin registro; RF-72 no fija código`
      : `rechazo HTTP ${post.http} ${post.cuerpo?.error_code ?? 'sin código'} con el mensaje «${post.cuerpo?.message ?? 'sin mensaje'}»; sin registro en historial ni auditoría`;
  return { estado: fallos.length ? 'RECHAZADO' : dudas.length ? 'NO_CONCLUYENTE' : 'APROBADO',
    motivo: fallos.join('; ') || dudas.join('; ') || conforme };
}
