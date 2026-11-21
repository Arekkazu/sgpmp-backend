export const CASOS = ['TC-M06-009', 'TC-M06-010'];
export const IDS = { 'TC-M06-009': ['G36-API-009-01', 'G36-API-009-02'],
  'TC-M06-010': ['G36-API-010-01', 'G36-API-010-02'] };
export const PRESUPUESTO = Object.freeze({ solicitudes_totales: 150, duracion_segundos: 900,
  logins_fuera_run: 3, eventos_m02: 2, procesamientos: 2, intentos_modificacion: 9,
  precios: 0, configuracion: 0, timeout_login_ms: 120000, timeout_post_ms: 120000, timeout_ms: 30000 });
export const CAPACIDADES = Object.freeze({ contrato: 'sigab-qa-ejecutor/1', grupo: 'G36', casos: CASOS,
  operaciones: ['evaluar', 'reintentar', 'reevaluar'], versiones: { min: 1, max: 99 },
  comprobaciones_obligatorias: Object.fromEntries(CASOS.map(c => [c, { API: IDS[c] }])),
  limite: PRESUPUESTO, baja_automatizada: false });
export const id = x => Number.isSafeInteger(Number(x)) && Number(x) > 0 ? Number(x) : null;
export const hoy = () => new Intl.DateTimeFormat('en-CA', { timeZone: 'America/Bogota', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date());
export const monto = x => x == null || x === '' ? NaN : Number(x);
export const igualMonto = (a, b) => Number.isFinite(monto(a)) && Number.isFinite(monto(b)) && Math.abs(monto(a) - monto(b)) < 0.005;
export const nuevos = (a, b, campo) => {
  if (!Array.isArray(a) || !Array.isArray(b)) return null;
  const base = new Set(a.map(x => String(x[campo])));
  return b.filter(x => !base.has(String(x[campo])));
};
export const requiereRebase = candidato =>
  id(candidato.calc.id_precio_mercado) !== id(candidato.precio.id_precio_mercado) ||
  !igualMonto(candidato.calc.magnitud, candidato.peso);
export function elegirCandidato(candidatos) {
  const elegido = candidatos.find(c => !requiereRebase(c)) ?? candidatos[0] ?? null;
  for (const c of candidatos) {
    c.fila.estado = c === elegido ? 'SELECCIONADO' : 'DESCARTADO';
    c.fila.motivo = c === elegido ?
      (requiereRebase(c) ? 'Elegible; requiere rebase porque ningún candidato usa precio y peso vigentes.' :
        'Elegible; cálculo previo usa precio y peso vigentes; sin rebase.') :
      (requiereRebase(c) ? 'Elegible con rebase; se prefirió candidato sin rebase.' :
        'Elegible sin rebase; se prefirió otro candidato sin rebase.');
  }
  return elegido;
}
export function datosPaso(actual, previo, aid, pid = null) {
  const campos = [
    ['variaciones', 'id_variacion_valor_razonable', x => ({ id: id(x.id_variacion_valor_razonable),
      tipo: x.tipo, monto: x.monto_variacion, periodo: id(x.id_periodo_contable) ?? pid,
      id_linea: id(x.id_linea), estado: x.estado_trazabilidad ?? x.estado ?? null })],
    ['lineas', 'id_linea_asiento_nic41', x => ({ id: id(x.id_linea_asiento_nic41),
      tipo: x.tipo_hecho, monto: x.valor, periodo: id(x.id_periodo_contable),
      id_linea: id(x.id_linea_asiento_nic41), estado: x.estado_trazabilidad ?? x.estado ?? null,
      id_origen: id(x.id_origen) })],
    ['mediciones', 'id_medicion_posterior', x => ({ id: id(x.id_medicion_posterior),
      tipo: x.origen_medicion, monto: x.variacion_total, periodo: id(x.id_periodo_contable),
      id_linea: null, estado: x.estado ?? null, id_evento: id(x.id_evento) })]
  ];
  return Object.fromEntries(campos.map(([nombre, clave, proyectar]) => [nombre,
    Array.isArray(actual?.[nombre]) && (!previo || Array.isArray(previo[nombre])) ?
      nuevos(previo?.[nombre] ?? [], actual[nombre], clave)
        .filter(x => id(x.id_activo_biologico) === aid ||
          (nombre === 'mediciones' && !('id_activo_biologico' in x)))
        .map(proyectar) : null]));
}
export function aislarTransformacion(pre, post, aid, eventoId) {
  if (!pre?.completa || !post?.completa) return { estado: 'NO_CONCLUYENTE', motivo: 'Lecturas incompletas.', variaciones: [] };
  const mediciones = nuevos(pre.mediciones, post.mediciones, 'id_medicion_posterior')
    .filter(x => id(x.id_evento) === eventoId);
  const variaciones = nuevos(pre.variaciones, post.variaciones, 'id_variacion_valor_razonable')
    .filter(x => id(x.id_activo_biologico) === aid && x.tipo === 'GANANCIA_TRANSFORMACION_BIOLOGICA');
  const vinculadas = variaciones.filter(x => post.lineas.some(l =>
    l.tabla_origen === 'variaciones_valor_razonable' &&
    id(l.id_origen) === id(x.id_variacion_valor_razonable) &&
    id(l.id_activo_biologico) === aid));
  if (mediciones.length !== 1 || variaciones.length !== 1 || vinculadas.length !== 1)
    return { estado: 'NO_CONCLUYENTE', motivo: `Tras pesaje: mediciones del evento ${mediciones.length}, ganancias TB nuevas ${variaciones.length}, con línea ${vinculadas.length}.`, variaciones };
  return { estado: 'AISLADA', variacion: vinculadas[0], variaciones };
}
export function igualCampos(a, b) {
  if (a === b) return true;
  if (!a || !b || typeof a !== 'object' || typeof b !== 'object' || Array.isArray(a) !== Array.isArray(b)) return false;
  const ka = Object.keys(a).sort(), kb = Object.keys(b).sort();
  return ka.length === kb.length && ka.every((k, i) => k === kb[i] && igualCampos(a[k], b[k]));
}
export function diferencias(a, b, ruta = '') {
  if (igualCampos(a, b)) return [];
  if (!a || !b || typeof a !== 'object' || typeof b !== 'object') return [ruta || '$'];
  return [...new Set([...Object.keys(a), ...Object.keys(b)])].flatMap(k => diferencias(a[k], b[k], `${ruta}.${k}`));
}
export function periodoDestino(periodos, nit, dia = hoy()) {
  if (!nit) return null;
  const propios = periodos.filter(x => String(x.numero_id_tributaria) === String(nit));
  const actual = propios.find(x => x.fecha_inicio <= dia && x.fecha_fin >= dia);
  return actual?.estado === 'ABIERTO' ? actual : null;
}
export function precioVigente(items, especie, dia = hoy()) {
  const lista = items.filter(p => id(p.id_especie) === id(especie) && p.categoria === 'PESO_KG' && p.fecha_vigencia <= dia);
  for (const fuente of ['MERCADO_ACTIVO', 'UPRA', 'ESTIMADA']) {
    const ultimo = lista.filter(p => p.fuente === fuente).sort((a, b) =>
      String(b.fecha_vigencia).localeCompare(String(a.fecha_vigencia)) || id(b.id_precio_mercado) - id(a.id_precio_mercado))[0];
    if (ultimo && (!ultimo.fecha_vencimiento || ultimo.fecha_vencimiento >= dia)) return ultimo;
  }
  return null;
}
export function calculoVigente(detalle) {
  const ultimo = (detalle?.calculos ?? []).filter(x => x.estado === 'CALCULADO' && x.json_metodo_costo?.es_producto !== true)
    .sort((a, b) => String(b.fecha_calculo).localeCompare(String(a.fecha_calculo)) ||
      id(b.id_calculo_valor_razonable) - id(a.id_calculo_valor_razonable))[0] ?? null;
  return monto(ultimo?.valor_neto) > 0 ? ultimo : null;
}
export function evaluar009(intentos, antes, despues) {
  if (!antes?.variacion || !antes?.linea || !Array.isArray(intentos))
    return { estado: 'NO_CONCLUYENTE', motivo: 'Lecturas base incompletas.' };
  if (!despues?.variacion || !despues?.linea)
    return { estado: 'RECHAZADO', severidad: 'ALTA', motivo: 'Variacion o linea desaparecio tras los intentos.',
      observados: { intentos, orientados: 0, bloqueados: 0, campos_alterados: ['registro ausente'] } };
  const cambios = !igualCampos(antes.variacion, despues.variacion) || !igualCampos(antes.linea, despues.linea);
  const aceptados = intentos.some(x => x.http >= 200 && x.http < 300);
  if (aceptados || cambios) return { estado: 'RECHAZADO', severidad: 'ALTA',
    motivo: aceptados ? 'Modificacion directa devolvio 2xx.' : 'Cambio la huella de variacion o linea.',
    observados: { intentos, orientados: intentos.filter(x => /correctivo/i.test(x.mensaje ?? '')).length, bloqueados: 0, campos_alterados: cambios ? ['huella'] : [] } };
  const ajenos = intentos.some(x => x.http == null || x.http >= 500 || x.http === 403 ||
    x.codigo && !['VARIACION_INMUTABLE','LINEA_ASIENTO_INMUTABLE'].includes(x.codigo));
  if (ajenos || intentos.length !== 9) return { estado: 'NO_CONCLUYENTE', motivo: 'Error ajeno o menos de nueve intentos.' };
  const validos = intentos.filter(x => x.http === 409 && x.codigo ===
    (x.ruta.includes('/lineas/') ? 'LINEA_ASIENTO_INMUTABLE' : 'VARIACION_INMUTABLE'));
  const orientados = intentos.filter(x => /correctivo/i.test(x.mensaje ?? ''));
  const conforme = validos.length === 9 && orientados.length === 9;
  return { estado: conforme ? 'APROBADO' : 'RECHAZADO', severidad: conforme ? null : 'MEDIA',
    motivo: conforme ? 'Nueve bloqueos 409 orientados al correctivo; huellas identicas.' :
      'Bloqueo sin 409, codigo esperado u orientacion al correctivo.',
    observados: { intentos, orientados: orientados.length, bloqueados: validos.length, campos_alterados: [] } };
}
export function evaluar010({ original, solicitud, previo, aprobacion, historial, lineas, lineaOriginal }) {
  if (!original || !solicitud || !previo || !aprobacion || !Array.isArray(historial) ||
      !Array.isArray(lineas) || !lineaOriginal)
    return { estado: 'NO_CONCLUYENTE', motivo: 'Faltan respuestas o lecturas del flujo correctivo.' };
  const oid = id(original.id_variacion_valor_razonable), cid = id(aprobacion.id_variacion_correctiva);
  const fallas = [];
  if (solicitud.estado !== 'PENDIENTE' || id(solicitud.id_variacion_valor_razonable) !== oid ||
      !igualMonto(solicitud.monto_correctivo, -monto(original.monto_variacion)))
    fallas.push('Solicitud pendiente o monto opuesto discrepante.');
  if (previo.efectivo !== false || previo.original_visible !== true)
    fallas.push('El correctivo era efectivo antes de aprobar o el original desaparecio.');
  if (aprobacion.estado !== 'APROBADA' || id(aprobacion.id_variacion_corregida) !== oid || !cid || cid === oid ||
      !igualMonto(aprobacion.monto_variacion, -monto(original.monto_variacion)))
    fallas.push('Aprobacion, referencia o monto discrepante.');
  const orig = historial.find(x => id(x.id_variacion_valor_razonable) === oid);
  const corr = historial.find(x => id(x.id_variacion_valor_razonable) === cid);
  if (!orig || !corr || corr.es_correctivo !== true || id(corr.id_variacion_corregida) !== oid ||
      !igualMonto(corr.monto_variacion, -monto(original.monto_variacion)))
    fallas.push('Historial original y correctivo incompleto.');
  const inversas = aprobacion.lineas_inversas;
  if (!Array.isArray(inversas) || inversas.length !== 1 || inversas.some(x =>
    !(monto(x.valor) > 0) || id(x.id_linea_corregida) !== id(lineaOriginal.id_linea_asiento_nic41) ||
    x.cuenta_debito !== lineaOriginal.cuenta_credito || x.cuenta_credito !== lineaOriginal.cuenta_debito ||
    !lineas.some(l => id(l.id_linea_asiento_nic41) === id(x.id_linea) &&
      id(l.id_origen) === cid && id(l.id_linea_corregida) === id(lineaOriginal.id_linea_asiento_nic41) &&
      monto(l.valor) > 0 && l.cuenta_debito === x.cuenta_debito && l.cuenta_credito === x.cuenta_credito)))
    fallas.push('Linea inversa ausente, negativa o con cuentas sin invertir.');
  return { estado: fallas.length ? 'RECHAZADO' : 'APROBADO', severidad: fallas.length ? 'ALTA' : null,
    motivo: fallas.join(' ') || 'Solicitud pendiente, aprobacion, historial y linea inversa acreditados.' };
}
export function unaIncidencia(casos) {
  return CASOS.filter(c => casos[c]?.estado === 'RECHAZADO').map((caso, i) => ({
    id: 'INC-M06-G36-V2-' + (i + 1), casos: [caso], titulo: caso === CASOS[0] ?
      'Inmutabilidad u orientacion correctiva incumplida' : 'Mecanismo correctivo incumplido',
    requisito: caso === CASOS[0] ? 'RF-86 CA-12 y restriccion 5' : 'RF-86 CA-13 y restriccion 5',
    esperado: caso === CASOS[0] ? 'Nueve bloqueos 409 orientados y registros identicos.' :
      'Solicitud pendiente, aprobacion por otro Contador, historial y linea inversa.',
    obtenido: casos[caso].motivo, severidad: casos[caso].severidad ?? 'ALTA',
    origen: (caso === CASOS[0] && casos[caso].severidad === 'MEDIA') ||
      (caso === CASOS[1] && /solicitud|aprobaci/i.test(casos[caso].motivo)) ?
      'seguimiento INC-M06-G36-01' : 'nueva en V2',
    justificacion_severidad: caso === CASOS[0] && casos[caso].severidad === 'MEDIA' ?
      'Falta orientacion, con bloqueo conservado.' : 'Funcion contable relevante impedida o datos alterados.',
    certeza: 'CONFIRMADA', equipo_inicial: 'Desarrollo',
    fundamento_equipo: 'Primera discrepancia en API publica de TEST; la causa raiz no esta demostrada.',
    causa_raiz: 'NO DETERMINADA', evidencias: ['resultado.json'] }));
}
export function rollback(base, final, eventos, variacionId, lineaId) {
  if (!base?.completa || !final?.completa) return { verificado: false, motivo: 'Lectura poscierre incompleta.' };
  const campos = [['eventos', 'id_eventos'], ['variaciones', 'id_variacion_valor_razonable'],
    ['correctivos', 'id_solicitud_correctivo_variacion'],
    ['lineas', 'id_linea_asiento_nic41'], ['calculos', 'id_calculo_valor_razonable'], ['auditoria', 'id_evento']];
  const residuos = campos.flatMap(([k, clave]) => (nuevos(base[k], final[k], clave) ?? []).map(x => ({ tipo: k, id: id(x[clave]) })));
  const verificado = campos.every(([k]) => Array.isArray(base[k]) && Array.isArray(final[k])) &&
    base.estado === 'ACTIVO' && final.estado === base.estado && igualMonto(base.peso, final.peso) &&
    !residuos.length && eventos.every(e => !final.eventos.some(x => id(x.id_eventos) === id(e))) &&
    !final.variaciones.some(x => id(x.id_variacion_valor_razonable) === id(variacionId)) &&
    !final.lineas.some(x => id(x.id_linea_asiento_nic41) === id(lineaId));
  return { verificado, residuos, estado_original: base.estado, estado_final: final.estado,
    motivo: verificado ? 'ACTIVO y peso restaurados; eventos M02, solicitudes correctivas, variaciones, lineas, calculos y auditoria del RUN ausentes en lecturas poscierre.' :
    'Persisten datos del RUN tras DELETE.' };
}
