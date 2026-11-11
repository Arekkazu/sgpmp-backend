export const CASOS = ['TC-M06-009', 'TC-M06-010'];
export const IDS = { 'TC-M06-009': ['G36-API-009-01', 'G36-API-009-02'],
  'TC-M06-010': ['G36-API-010-01', 'G36-API-010-02'] };
export const PRESUPUESTO = Object.freeze({ solicitudes_totales: 80, duracion_segundos: 900,
  logins_fuera_run: 2, eventos_m02: 2, procesamientos: 2, intentos_modificacion: 9,
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
  if (actual?.estado === 'ABIERTO') return actual;
  if (actual?.estado === 'EN_CIERRE') return null;
  const desde = actual?.fecha_fin ?? dia;
  return propios.filter(x => x.estado === 'ABIERTO' && x.fecha_inicio > desde)
    .sort((a, b) => String(a.fecha_inicio).localeCompare(String(b.fecha_inicio)))[0] ?? null;
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
export function operacionesCorrectivas(openapi) {
  if (!openapi || typeof openapi.paths !== 'object') return null;
  const ops = [];
  for (const [ruta, metodos] of Object.entries(openapi.paths)) for (const [metodo, spec] of Object.entries(metodos ?? {})) {
    if (!['post', 'put', 'patch'].includes(metodo)) continue;
    const texto = [ruta, spec?.operationId, spec?.summary, spec?.description, ...(spec?.tags ?? [])].join(' ').toLowerCase();
    if (!/(variaci|variac)/.test(texto) || !/(correctiv|correcci|corregid|reversi|aprobaci|aprobar)/.test(texto)) continue;
    ops.push({ ruta, metodo: metodo.toUpperCase(), operationId: spec?.operationId ?? null,
      nombre: [spec?.operationId, spec?.summary, spec?.description].filter(Boolean).join(' '),
      requestBody: spec?.requestBody ?? null, parameters: spec?.parameters ?? [] });
  }
  return ops;
}
export function evaluar009(intentos, antes, despues) {
  if (!antes || !despues || !Array.isArray(intentos) || !intentos.length)
    return { estado: 'NO_CONCLUYENTE', motivo: 'Faltan intentos o instantáneas públicas completas.' };
  const cambios = [...diferencias(antes.variacion, despues.variacion).map(x => 'variación' + x),
    ...diferencias(antes.linea, despues.linea).map(x => 'línea' + x)];
  const aceptados = intentos.filter(x => x.http >= 200 && x.http < 300);
  const tecnicos = intentos.filter(x => x.http == null || x.http >= 500 || x.http === 403);
  const orientados = intentos.filter(x => /correctiv|correcci|corregid/i.test([x.codigo, x.mensaje].join(' ')));
  const fallas = [];
  if (aceptados.length) fallas.push(`${aceptados.length} intento(s) devolvieron 2xx.`);
  if (cambios.length) fallas.push(`Campos alterados: ${cambios.join(', ')}.`);
  if (orientados.length !== intentos.length) fallas.push(`${intentos.length - orientados.length} respuesta(s) no orientaron al registro correctivo.`);
  const incierto = tecnicos.length > 0 || (intentos.length !== 9 && !aceptados.length && !cambios.length);
  return { estado: aceptados.length || cambios.length ? 'RECHAZADO' : incierto ? 'NO_CONCLUYENTE' :
      fallas.length ? 'RECHAZADO' : 'APROBADO',
    motivo: incierto && !aceptados.length && !cambios.length ?
      'Respuestas técnicas, corte o menos de nueve intentos impiden acreditar el bloqueo y la orientación completos.' :
      fallas.join(' ') || 'Todos los intentos bloqueados, instantáneas idénticas y orientación correctiva presente.',
    observados: { intentos, campos_alterados: cambios, bloqueados: intentos.length - aceptados.length - tecnicos.length,
      orientados: orientados.length } };
}
export function evaluar010({ contrato, original, previo, pendiente, aprobado, lineaOriginal, lineaCorrectiva, aprobacionHttp }) {
  if (contrato === null) return { estado: 'NO_CONCLUYENTE', motivo: 'OpenAPI público no se leyó completo.' };
  if (!contrato.length) return { estado: 'RECHAZADO', motivo: 'El contrato OpenAPI desplegado no expone crear ni aprobar correctivo de variación.' };
  if (!original || !previo || !pendiente || !aprobado || !lineaOriginal)
    return { estado: 'NO_CONCLUYENTE', motivo: 'El mecanismo existe, pero faltan lecturas o una operación segura para completar el oráculo.' };
  const cid = id(pendiente.id_variacion_valor_razonable), oid = id(original.id_variacion_valor_razonable);
  const uuidOriginal = original.uuid ?? original.id_variacion_uuid ?? original.id_variacion;
  const referencia = pendiente.id_variacion_corregida;
  const fallas = [];
  if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(String(uuidOriginal ?? '')) ||
      String(referencia) !== String(uuidOriginal) || !cid || cid === oid ||
      !igualMonto(pendiente.monto_variacion, -monto(original.monto_variacion)))
    fallas.push('El correctivo no tiene monto opuesto, ID nuevo y referencia explícita al UUID original.');
  if (previo.efectivo !== false) fallas.push('No se acreditó inefectividad antes de aprobación.');
  if (!(aprobacionHttp >= 200 && aprobacionHttp < 300) || aprobado.efectivo !== true) fallas.push('La aprobación del Contador no acreditó efectividad.');
  if (!aprobado.original_visible || !aprobado.correctivo_visible) fallas.push('Original o correctivo ausente del historial.');
  if (!lineaCorrectiva || !(monto(lineaCorrectiva.valor) > 0) || lineaCorrectiva.cuenta_debito !== lineaOriginal.cuenta_credito ||
      lineaCorrectiva.cuenta_credito !== lineaOriginal.cuenta_debito) fallas.push('La línea correctiva no invierte el par de cuentas con valor positivo.');
  return { estado: fallas.length ? 'RECHAZADO' : 'APROBADO', motivo: fallas.join(' ') || 'Correctivo opuesto, referencia, aprobación, historial y línea inversa acreditados.' };
}
export function unaIncidencia(casos, contexto = {}) {
  const rechazados = CASOS.filter(c => casos[c]?.estado === 'RECHAZADO');
  if (!rechazados.length) return [];
  const compartida = rechazados.length === 2 && /orientaci|orientaron|correctiv/i.test(casos[CASOS[0]].motivo) &&
    /mecanismo|crear|aprobar|correctiv/i.test(casos[CASOS[1]].motivo) &&
    !/2xx|alterad|desapareci/i.test(casos[CASOS[0]].motivo);
  const grupos = compartida ? [rechazados] : rechazados.map(c => [c]);
  const intentos = casos[CASOS[0]]?.observados?.intentos ?? [];
  const comparacion = casos[CASOS[0]]?.comparacion_campo_a_campo;
  const sinOrientacion = intentos.length > 0 && casos[CASOS[0]]?.observados?.orientados === 0;
  const resumen009 = intentos.length ? `${intentos.length} intentos PUT/PATCH/DELETE de modificación directa, HTTP ${[...new Set(intentos.map(x => x.http ?? 'sin respuesta'))].join('/')} ${[...new Set(intentos.map(x => x.mensaje).filter(Boolean))].join('/')}; ${sinOrientacion ? 'ninguno orientó al correctivo; ' : ''}variación (${comparacion?.variacion?.campos?.length ?? 'sin lectura'} campos) y línea (${comparacion?.linea?.campos?.length ?? 'sin lectura'} campos) con huellas antes/después ${comparacion?.variacion?.sha256_antes === comparacion?.variacion?.sha256_despues && comparacion?.linea?.sha256_antes === comparacion?.linea?.sha256_despues ? 'iguales' : 'no acreditadas como iguales'}` : casos[CASOS[0]]?.motivo;
  const resumen010 = contexto.contrato ? `GET ${contexto.contrato.ruta ?? '/openapi.json'} HTTP ${contexto.contrato.http ?? 'sin respuesta'}; ${contexto.contrato.operaciones_m06?.length ?? 'sin contar'} operaciones M06, ${contexto.contrato.correctivas?.length ?? 'sin contar'} correctivas; SHA-256 ${contexto.contrato.sha256 ?? 'sin huella'}` : casos[CASOS[1]]?.motivo;
  const sinOperacionesCorrectivas = Array.isArray(contexto.contrato?.correctivas) && contexto.contrato.correctivas.length === 0;
  return grupos.map((grupo, i) => ({ id: 'INC-M06-G36-0' + (i + 1), casos: grupo,
    titulo: grupo.length === 2 && sinOperacionesCorrectivas ? 'No existe el mecanismo de registro correctivo de variaciones y los intentos de modificación no orientan hacia él' :
      grupo.length === 2 ? 'La orientación y el mecanismo correctivo de variaciones no cumplen lo exigido' :
      grupo[0] === CASOS[0] ? 'Los intentos de modificación no orientan al registro correctivo' : 'No se acredita el mecanismo de registro correctivo de variaciones',
    requisito: grupo.length === 2 ? 'RF-86 CA-12, CA-13, Restricción 5 (append-only) y CU05 FA-6' :
      grupo[0] === CASOS[0] ? 'RF-86 CA-12 y Restricción 5' : 'RF-86 CA-13 y Restricción 5',
    pasos: `En un período ABIERTO, crear una variación GANANCIA_TRANSFORMACION_BIOLOGICA${contexto.preparacion?.variacion_id ? ` (${contexto.preparacion.variacion_id})` : ''} y su línea${contexto.preparacion?.linea_id ? ` (${contexto.preparacion.linea_id})` : ''}; intentar PUT, PATCH y DELETE sobre las rutas públicas de variación y línea; comparar ambos registros antes y después; consultar GET /openapi.json y comprobar si se ofrecen creación y aprobación del correctivo.`,
    esperado: 'Los intentos directos se bloquean y orientan al registro correctivo; variación y línea permanecen idénticas. El Contador puede crear un correctivo nuevo con monto opuesto y referencia al UUID original, aprobarlo y consultar ambos registros y la línea inversa de valor positivo.',
    obtenido: grupo.map(c => `${c}: ${c === CASOS[0] ? resumen009 : resumen010}. ${casos[c].motivo}`).join(' '),
    apoyo_codigo: 'En la preparación inicial se leyó src/financial_valuation/infrastructure/routers/m06_router.py:79-508 sin rutas de correctivo de variación; se buscaron referencias a correctivo en src/financial_valuation y SGPMP-FRONT-END-PWA/src/financial_valuation sin resultados. alembic/baseline/esquema_baseline.sql:12710-12739,43225-43235 y alembic/versions/c4d81e6f2a95_m06_nic41_esquema_rfc018.py:745-824 documentan protecciones de variaciones y líneas, y los campos id_linea_corregida y tipo_hecho_corregido. En reevaluaciones se debe revisar de nuevo el código local; esta lectura no acredita la versión desplegada ni la causa raíz.',
    impacto: /2xx|alterad|desapareci/i.test(grupo.map(c => casos[c].motivo).join(' ')) ?
      'Se observó cambio o eliminación de evidencia contable que debía permanecer inmutable.' :
      compartida && grupo.length === 2 ? 'El Contador no puede corregir una variación errónea dentro del período abierto ni recibe guía hacia el mecanismo correctivo. El append-only se cumple, pero sin vía pública de corrección el error queda sin tratamiento contable.' :
        'La corrección contable exigida queda impedida o incompleta para el escenario comprobado.',
    severidad: /2xx|alterad|desapareci/i.test(grupo.map(c => casos[c].motivo).join(' ')) ? 'CRÍTICA' : 'ALTA',
    justificacion_severidad: /2xx|alterad|desapareci/i.test(grupo.map(c => casos[c].motivo).join(' ')) ?
      'La discrepancia comprobada afecta integridad de datos contables.' :
      compartida && grupo.length === 2 ? 'La corrección contable exigida por CA-13 queda bloqueada y CA-12 no orienta; no se acreditó una alternativa pública.' :
        'Funcionalidad relevante de corrección sin alternativa acreditada.',
    certeza: 'CONFIRMADA', equipo_inicial: 'Desarrollo',
    fundamento_equipo: 'La primera discrepancia se observó mediante API pública de TEST; la derivación no atribuye causa técnica.',
    causa_raiz: 'NO DETERMINADA', defecto_compartido: compartida,
    evidencias: contexto.newman ? ['resultado.json', 'newman/newman-G36.json', 'newman/newman-G36.html'] : ['resultado.json'] }));
}
export function rollback(base, final, eventos, variacionId, lineaId) {
  if (!base?.completa || !final?.completa) return { verificado: false, motivo: 'Lectura poscierre incompleta.' };
  const campos = [['eventos', 'id_eventos'], ['variaciones', 'id_variacion_valor_razonable'],
    ['lineas', 'id_linea_asiento_nic41'], ['calculos', 'id_calculo_valor_razonable'], ['auditoria', 'id_evento']];
  const residuos = campos.flatMap(([k, clave]) => (nuevos(base[k], final[k], clave) ?? []).map(x => ({ tipo: k, id: id(x[clave]) })));
  const verificado = campos.every(([k]) => Array.isArray(base[k]) && Array.isArray(final[k])) &&
    base.estado === 'ACTIVO' && final.estado === base.estado && igualMonto(base.peso, final.peso) &&
    !residuos.length && eventos.every(e => !final.eventos.some(x => id(x.id_eventos) === id(e))) &&
    !final.variaciones.some(x => id(x.id_variacion_valor_razonable) === id(variacionId)) &&
    !final.lineas.some(x => id(x.id_linea_asiento_nic41) === id(lineaId));
  return { verificado, residuos, estado_original: base.estado, estado_final: final.estado,
    motivo: verificado ? 'ACTIVO y peso restaurados; eventos M02, variación, línea, cálculos y auditoría del RUN ausentes en lecturas poscierre.' :
    'Persisten datos del RUN tras DELETE.' };
}
