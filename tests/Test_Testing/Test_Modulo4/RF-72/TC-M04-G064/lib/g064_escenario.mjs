export const CASOS = Object.freeze([194, 195, 196, 197].map(n => `TC-M04-${n}`));
export const ESTADOS = Object.freeze(['CORRECTO', 'SIN_EVENTO', 'PARCIAL', 'INCORRECTO']);
export const IDS = Object.freeze([194, 195, 196, 197].map(n => `API-${n}-01`));
// 1 login + 4 páginas de activos + 128 páginas de historial + 8 versiones + 1 catálogo + 8 POST
// + 12 páginas de persistencia (3 por caso) + 4 auditorías + 1 login admin
// + 4 relecturas de auditoría + 1 DELETE + 12 páginas de rollback = 184.
export const PRESUPUESTO = Object.freeze({ solicitudes_totales: 184, descubrimiento_maximo: 142,
  paginas_activos: 4, historiales_descubrimiento: 32, paginas_historial_descubrimiento: 4,
  versiones_maximas: 8, paginas_historial_verificacion: 3,
  dias_busqueda: 88, timeout_login_ms: 120000,
  timeout_ms: 30000, duracion_segundos: 900 });
export const CAPACIDADES = Object.freeze({ contrato: 'sigab-qa-ejecutor/1', grupo: 'G064',
  casos: CASOS, operaciones: ['evaluar', 'reintentar', 'reevaluar', 'recuperar'],
  versiones: { min: 1, max: 99 },
  comprobaciones_obligatorias: Object.fromEntries(CASOS.map((c, i) => [c, { API: [IDS[i]] }])),
  limite: { solicitudes_totales: PRESUPUESTO.solicitudes_totales,
    duracion_segundos: PRESUPUESTO.duracion_segundos } });
const TIPOS_INDIVIDUALES = ['MODELO_ESPECIES_MEDIANAS', 'MODELO_ESPECIES_GRANDES'];
export const tipoEfectivo = (x, versiones = {}) => x?.payload?.tipo_modelo
  ?? versiones[String(x?.payload?.id_version_modelo)] ?? null;
export const modeloIndividual = (x, versiones = {}) => TIPOS_INDIVIDUALES.includes(tipoEfectivo(x, versiones));
export function diagnosticar(eventos, patologias, usados = new Set(), usuarioId = null,
  versiones = {}, inicio = null, fin = null) {
  const tipos = { INFERENCIA: 0, ALERTA: 0, RETROALIMENTACION: 0, OTRO: 0 };
  const modelos = {}, riesgos = {}, descarte = { no_inferencia: 0, modelo_no_individual_o_nulo: 0,
    fuera_fecha: 0, sin_patologia_197: 0, ya_retroalimentada_usuario: 0, duplicada_otro_caso: 0 };
  const retroUsuario = new Set(eventos.filter(x => x.tipo_evento === 'RETROALIMENTACION'
    && usuarioId != null && String(x.payload?.id_usuario_veterinario) === String(usuarioId))
    .map(x => String(x.id_resultado_inferencia)));
  const fechas = eventos.map(x => Date.parse(x.fecha_evento)).filter(Number.isFinite);
  let conPatologia = 0, retroPropia = 0;
  for (const x of eventos) {
    tipos[x.tipo_evento in tipos ? x.tipo_evento : 'OTRO']++;
    if (x.tipo_evento !== 'INFERENCIA') { descarte.no_inferencia++; continue; }
    const modelo = x.payload?.tipo_modelo ?? null;
    modelos[modelo ?? 'null'] = (modelos[modelo ?? 'null'] ?? 0) + 1;
    const riesgo = x.payload?.nivel_riesgo ?? 'null';
    riesgos[String(riesgo)] = (riesgos[String(riesgo)] ?? 0) + 1;
    if (x.payload?.id_patologia != null) conPatologia++;
    if (retroUsuario.has(String(x.id_resultado_inferencia))) retroPropia++;
    if (!modeloIndividual(x, versiones)) descarte.modelo_no_individual_o_nulo++;
    if (!Number.isFinite(Date.parse(x.fecha_evento)) || Date.parse(x.fecha_evento) > Date.now()
      || (inicio && Date.parse(x.fecha_evento) < Date.parse(inicio))
      || (fin && Date.parse(x.fecha_evento) > Date.parse(fin + 'T23:59:59.999Z'))) descarte.fuera_fecha++;
    if (x.payload?.id_patologia == null || !patologias.some(p => p.es_activo
      && ['TODAS', String(x.id_especie)].includes(String(p.especie_aplicable))
      && String(p.id_patologia) !== String(x.payload.id_patologia))) descarte.sin_patologia_197++;
    if (retroUsuario.has(String(x.id_resultado_inferencia))) descarte.ya_retroalimentada_usuario++;
    if (usados.has(String(x.id_resultado_inferencia))) descarte.duplicada_otro_caso++;
  }
  return { eventos: eventos.length, por_tipo_evento: tipos, inferencias_por_tipo_modelo: modelos,
    fecha_evento_desde: fechas.length ? new Date(Math.min(...fechas)).toISOString() : null,
    fecha_evento_hasta: fechas.length ? new Date(Math.max(...fechas)).toISOString() : null,
    nivel_riesgo: riesgos, inferencias_con_patologia: conPatologia,
    inferencias_retroalimentadas_usuario: usuarioId == null ? null : retroPropia,
    descarte, criterios_no_excluyentes: true };
}
export function seleccionar(eventos, patologias, usados = new Set(), orden = [194, 195, 196, 197],
  versiones = {}, usuarioId = null, inicio = null, fin = null) {
  const retroUsuario = new Set(eventos.filter(x => x.tipo_evento === 'RETROALIMENTACION'
    && usuarioId != null && String(x.payload?.id_usuario_veterinario) === String(usuarioId))
    .map(x => String(x.id_resultado_inferencia)));
  const inferencias = eventos.filter(x => x.tipo_evento === 'INFERENCIA' && modeloIndividual(x, versiones)
    && !retroUsuario.has(String(x.id_resultado_inferencia))
    && !usados.has(String(x.id_resultado_inferencia)) && Number.isFinite(Date.parse(x.fecha_evento))
    && Date.parse(x.fecha_evento) <= Date.now()
    && (!inicio || Date.parse(x.fecha_evento) >= Date.parse(inicio))
    && (!fin || Date.parse(x.fecha_evento) <= Date.parse(fin + 'T23:59:59.999Z')));
  const libres = inferencias.sort((a, b) => Date.parse(b.fecha_evento) - Date.parse(a.fecha_evento));
  const salida = {};
  for (const n of orden) {
    const candidatos = libres.filter(x => !usados.has(String(x.id_resultado_inferencia)));
    const aptas = x => patologias.filter(p => p.es_activo
      && ['TODAS', String(x.id_especie)].includes(String(p.especie_aplicable)));
    const elegible = n === 195 ? candidatos.find(x => Number(x.payload.nivel_riesgo) > 0) ?? candidatos[0]
      : n === 197 ? candidatos.find(x => x.payload.id_patologia != null
        && aptas(x).some(p => String(p.id_patologia) !== String(x.payload.id_patologia)))
        : n === 196 ? candidatos.find(x => aptas(x).length) : candidatos[0];
    if (!elegible) continue;
    const patologia = [196, 197].includes(n) ? aptas(elegible).find(p => p.es_activo
      && (n !== 197 || String(p.id_patologia) !== String(elegible.payload.id_patologia))) : null;
    if ([196, 197].includes(n) && !patologia) continue;
    salida[n] = { id_resultado_inferencia: elegible.id_resultado_inferencia,
      id_activo_biologico: elegible.id_activo_biologico, fecha_inferencia: elegible.fecha_evento,
      nivel_riesgo: elegible.payload.nivel_riesgo, id_patologia_estimada: elegible.payload.id_patologia,
      tipo_modelo: tipoEfectivo(elegible, versiones), id_patologia_real: patologia?.id_patologia ?? null,
      observacion: n === 195 && !(Number(elegible.payload.nivel_riesgo) > 0)
        ? 'No hubo resultado con riesgo mayor que cero; se ejecutó con otro resultado' : null };
    usados.add(String(elegible.id_resultado_inferencia));
  }
  return salida;
}
export function decidirCaso(n, dato, post, lectura, auditoria) {
  if (!dato) return { estado: 'NO_CONCLUYENTE', motivo: 'No se encontró un resultado o patología apta' };
  if (post?.http == null) return { estado: 'NO_CONCLUYENTE', motivo: 'POST sin respuesta; requiere conciliación' };
  if (post.http === 403) return { estado: 'BLOQUEADO', motivo: 'HTTP 403 al registrar' };
  if (post.http === 409 && post.cuerpo?.error_code === 'RETROALIMENTACION_DUPLICADA')
    return { estado: 'NO_CONCLUYENTE', motivo: 'Resultado ocupado por el mismo Veterinario fuera del RUN' };
  if (post.http === 422 && post.cuerpo?.error_code === 'FUERA_DE_VENTANA_TEMPORAL') {
    const dias = String(post.cuerpo?.message ?? '').match(/más de (\d+) días/i)?.[1];
    return { estado: 'NO_CONCLUYENTE', motivo: `Dato no apto: resultado fuera de la ventana real${dias ? ` de ${dias} días` : ''}; ${post.cuerpo?.message ?? 'sin detalle del servidor'}` };
  }
  const fallos = [];
  const dudas = [];
  const b = post.cuerpo ?? {};
  if (post.eco !== true) fallos.push('sin eco del RUN en POST');
  if (post.http !== 201) fallos.push(`HTTP ${post.http}; esperado 201`);
  if (post.http === 201) {
    if (b.estado_retroalimentacion !== ESTADOS[n - 194]) fallos.push('estado de retroalimentación distinto');
    if (String(b.id_resultado_inferencia) !== String(dato.id_resultado_inferencia)) fallos.push('resultado distinto');
    if (Number(b.id_activo_biologico) !== Number(dato.id_activo_biologico)) fallos.push('activo distinto');
    if (n === 194) {
      if (Array.isArray(b.diagnosticos_reales) ? b.diagnosticos_reales.length > 0 : b.diagnosticos_reales != null)
        fallos.push('diagnósticos no nulos');
      if (b.estado_registro !== 'ACTIVO') fallos.push('estado_registro no ACTIVO');
      if (!Number.isFinite(Date.parse(b.fecha_retroalimentacion))
        || Date.parse(b.fecha_retroalimentacion) <= Date.parse(dato.fecha_inferencia))
        fallos.push('timestamp ausente o anterior a inferencia');
    }
    if ([196, 197].includes(n) && Number(b.diagnosticos_reales?.[0]) !== Number(dato.id_patologia_real))
      fallos.push('diagnóstico principal distinto');
    if (lectura?.http === 200 && lectura.eco === true) {
      const e = lectura.cuerpo?.eventos?.find(x => x.tipo_evento === 'RETROALIMENTACION'
        && String(x.id_evento) === String(b.id_retroalimentacion));
      if (!e && lectura.cuerpo?.cursor_siguiente) dudas.push('retroalimentación fuera de la primera página del historial');
      else if (!e || e.payload?.estado_retroalimentacion !== ESTADOS[n - 194]) fallos.push('sin persistencia pública del estado');
    } else dudas.push('lectura de persistencia no verificable');
    if (auditoria?.http === 200 && auditoria.eco === true) {
      if (!auditoria.cuerpo?.items?.some(x => x.tipo_evento === 'RETROALIMENTACION_REGISTRADA'
        && String(x.id_referencia) === String(b.id_retroalimentacion)
        && x.id_usuario != null)) fallos.push('sin auditoría de registro');
    } else dudas.push('lectura de auditoría no verificable');
  }
  return { estado: fallos.length ? 'RECHAZADO' : dudas.length ? 'NO_CONCLUYENTE' : 'APROBADO',
    motivo: fallos.length ? fallos.join('; ') : dudas.length ? dudas.join('; ')
      : `HTTP 201, estado ${ESTADOS[n - 194]}, persistencia y auditoría verificadas` };
}
