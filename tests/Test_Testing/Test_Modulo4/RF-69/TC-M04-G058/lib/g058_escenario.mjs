import crypto from 'node:crypto';

export const CASOS = Object.freeze([157, 158, 159].map(n => `TC-M04-${n}`));
export const IDS = Object.freeze([157, 158, 159].map(n => `API-${n}-01`));
export const PRESUPUESTO = Object.freeze({ logins: 2, catalogo: 1, activos_iniciales: 1, registros: 3,
  notas: 2, activaciones_validas: 2, estados_preparados: 2, auditorias_antes: 3, intentos_invalidos: 4,
  comprobacion_159: 2, comprobacion_158: 2, activa_antes_157: 1, comprobacion_157: 3,
  auditorias_intentos: 4, cierre: 1, comprobacion_rollback: 4,
  total: 37, timeout_post_ms: 120000, timeout_ms: 30000, duracion_segundos: 900 });
export const CAPACIDADES = Object.freeze({ contrato: 'sigab-qa-ejecutor/1', grupo: 'G058',
  casos: CASOS, operaciones: ['evaluar', 'reintentar', 'reevaluar'], versiones: { min: 1, max: 99 },
  comprobaciones_obligatorias: Object.fromEntries(CASOS.map((c, i) => [c, { API: [IDS[i]] }])),
  limite: { solicitudes_totales: PRESUPUESTO.total, duracion_segundos: PRESUPUESTO.duracion_segundos } });
export const TIPO = 'MODELO_ESPECIES_GRANDES';
export const idVersion = x => x?.id_version_modelo ?? x?.id_version ?? null;
export const registroValido = (x, esperado) => x?.eco === true
  && idVersion(x.cuerpo) != null && x.cuerpo?.estado_version === esperado
  && (esperado === 'APROBADO' ? x.http === 201
    : esperado === 'RECHAZADO' && (x.http === 200 || x.http === 201));
export function escenarios({ variable, hash, dataset, archivo, ahora = Date.now() }) {
  return ['A', 'B', 'R'].map((dato, i) => ({ dato, tipo_modelo: TIPO,
    id_proceso_rf71: crypto.randomUUID(), hash_artefacto_sha256: hash,
    dataset_entrenamiento_hash: dataset,
    metricas_validacion: { f1_score_global: i === 2 ? 0.72 : 0.91,
      recall_clase_riesgo_alto: 0.95, precision_global: 0.92, accuracy: 0.94,
      roc_auc_score: 0.95, recall_por_clase: { riesgo_alto: 0.95, riesgo_bajo: 0.92 },
      matriz_confusion: [[9, 1], [1, 9]] },
    fecha_entrenamiento: new Date(ahora - (3 - i) * 86400000).toISOString(),
    compatibilidad_variables: [variable], archivo_modelo: archivo }));
}
const visible = x => x?.http === 200 && x.eco;
const estado = (x, valor, produccion) => visible(x) && x.cuerpo?.estado_version === valor
  && x.cuerpo?.esta_produccion === produccion;
const lista = (x, id) => visible(x) && x.cuerpo?.total === 1
  && x.cuerpo?.items?.length === 1 && String(idVersion(x.cuerpo.items[0])) === String(id)
  && x.cuerpo.items[0].tipo_modelo === TIPO && x.cuerpo.items[0].componente == null;
const contieneActiva = (x, id) => visible(x) && Array.isArray(x.cuerpo?.items)
  && x.cuerpo.total === x.cuerpo.items.length
  && x.cuerpo.items.some(y => String(idVersion(y)) === String(id) && y.estado_version === 'ACTIVO');
const mismoEstado = (a, b) => visible(a) && visible(b)
  && a.cuerpo?.estado_version === b.cuerpo?.estado_version
  && a.cuerpo?.esta_produccion === b.cuerpo?.esta_produccion;
export const eventosEstado = x => visible(x) && Array.isArray(x.cuerpo?.items)
  ? x.cuerpo.items.filter(y => String(y.tipo_evento ?? '').startsWith('VERSION_'))
    .map(y => [y.tipo_evento, String(y.id_referencia ?? ''), String(y.correlacion_id ?? '')])
    .sort((a, b) => JSON.stringify(a).localeCompare(JSON.stringify(b))) : null;
export const mismosEventos = (a, b) => eventosEstado(a) !== null && eventosEstado(b) !== null
  && JSON.stringify(eventosEstado(a)) === JSON.stringify(eventosEstado(b));
function resultado(fallos, conforme) {
  if (!fallos.length) return { estado: 'APROBADO', motivo: conforme };
  return fallos.find(x => x.estado === 'BLOQUEADO')
    ?? fallos.find(x => x.estado === 'NO_CONCLUYENTE') ?? fallos[0];
}
const fallo = (cond, motivo) => cond ? null : { estado: 'RECHAZADO', motivo };
const sin = (x, nombre) => x?.http == null ? { estado: 'NO_CONCLUYENTE', motivo: `${nombre} sin respuesta` } : null;
const bloqueado = (x, nombre) => x?.http === 403 ? { estado: 'BLOQUEADO', motivo: `${nombre} HTTP 403; acceso no verificable` } : null;
const reunir = xs => xs.filter(Boolean);
export function evaluarInstantanea(s) {
  const { ids, intentos, get, listaActiva, aud, preparada, observaciones } = s;
  const [A, B, R] = ids;
  const base = { estado: 'NO_CONCLUYENTE', motivo: 'No se construyó la precondición' };
  const rPreparada = preparada.R;
  const bActiva = preparada.B;
  const aDeprecada = preparada.A;
  const bActiva159 = bActiva;
  const activaAntes = get.ActivaAntes157;
  const activaDespues = get.ActivaDespues157;
  const idActiva = idVersion(activaAntes?.cuerpo);
  const c157 = !rPreparada ? { ...base, motivo: 'R no quedó RECHAZADA antes de los intentos' }
    : resultado(reunir([
      sin(intentos.Rvet, 'Activar R como Veterinario'), sin(intentos.Radmin, 'Activar R como Administrador'),
      bloqueado(intentos.Rvet, 'Activar R'), bloqueado(intentos.Radmin, 'Activar R'),
      fallo(intentos.Rvet?.http === 409 && intentos.Rvet?.eco,
        `R Veterinario HTTP ${intentos.Rvet?.http ?? 'sin respuesta'}; esperado 409`),
      fallo(intentos.Radmin?.http === 409 && intentos.Radmin?.eco,
        `R Administrador HTTP ${intentos.Radmin?.http ?? 'sin respuesta'}; esperado 409`),
      fallo(estado(get.R157, 'RECHAZADO', false), `R tras intentos: ${get.R157?.cuerpo?.estado_version ?? 'no verificado'}`),
      activaAntes && fallo(estado(activaAntes, 'ACTIVO', true),
        'La versión ACTIVO inmediatamente antes de 157 no se verificó'),
      activaAntes && fallo(estado(activaDespues, 'ACTIVO', true)
        && String(idVersion(activaDespues?.cuerpo)) === String(idActiva),
        `Versión ACTIVO ${idActiva} tras intentos sobre R: ${activaDespues?.cuerpo?.estado_version ?? 'no verificada'}`),
      activaAntes && fallo(contieneActiva(listaActiva.R, idActiva),
        `Listado ACTIVO tras intentos sobre R no contiene la versión ${idActiva}`),
      fallo(mismosEventos(aud.Rantes, aud.Rdespues), 'Auditoría de R añadió eventos de estado')
    ]), `R ${R} RECHAZADA; ambos roles HTTP 409; ${activaAntes ? `versión ${idActiva} sigue ACTIVO; ` : 'sin ACTIVO comparable; '}sin transiciones nuevas`);
  const c158 = !aDeprecada ? { ...base, motivo: 'A no quedó DEPRECADA tras activar B; falta precondición de 158' }
    : resultado(reunir([
      sin(intentos.A, 'Activar A'), bloqueado(intentos.A, 'Activar A'),
      fallo(intentos.A?.http === 409 && intentos.A?.eco,
        `A DEPRECADA: activar HTTP ${intentos.A?.http ?? 'sin respuesta'}; esperado 409`),
      fallo(estado(get.A158, 'DEPRECADO', false), `A tras intento: ${get.A158?.cuerpo?.estado_version ?? 'no verificado'}`),
      fallo(mismoEstado(get.B159, get.B158),
        `B cambió durante el intento sobre A: ${get.B159?.cuerpo?.estado_version ?? 'no verificado'} → ${get.B158?.cuerpo?.estado_version ?? 'no verificado'}`),
      fallo(mismosEventos(aud.Aantes, aud.Aintermedia), 'Auditoría de A añadió transición de estado'),
      fallo(mismosEventos(aud.B159, aud.B158), 'Auditoría de B añadió transición de estado')
    ]), `A ${A} DEPRECADA; HTTP 409; B ${B} no se alteró; sin transiciones nuevas`);
  const c159 = !bActiva159 ? { ...base, motivo: 'B no está ACTIVO antes del autointento; falta precondición de 159' }
    : resultado(reunir([
      sin(intentos.B, 'Activar B'), bloqueado(intentos.B, 'Activar B'),
      fallo(intentos.B?.http === 409 && intentos.B?.eco,
        `B ACTIVO: activar HTTP ${intentos.B?.http ?? 'sin respuesta'}; esperado 409`),
      fallo(estado(get.B159, 'ACTIVO', true), `B tras autointento: ${get.B159?.cuerpo?.estado_version ?? 'no verificado'}, producción ${get.B159?.cuerpo?.esta_produccion ?? 'no verificada'}`),
      fallo(lista(listaActiva.B, B), 'Listado ACTIVO tras autointento no contiene solo B'),
      fallo(mismosEventos(aud.Bantes, aud.B159), 'Auditoría de B añadió eventos de estado')
    ]), `B ${B} ACTIVO y en producción; HTTP 409; listado={B}; sin eventos nuevos`);
  const otros = x => x?.cuerpo?.items?.filter(y => !String(y.tipo_evento ?? '').startsWith('VERSION_')
    && y.tipo_evento !== 'HISTORIAL_CONSULTADO').map(y => `${y.tipo_evento}:${y.id_referencia}`) ?? [];
  const previos = otros(aud.Aantes);
  const extrasA = otros(aud.Aintermedia).filter(y => !previos.includes(y));
  if (aDeprecada && intentos.A?.http != null
    && eventosEstado(aud.Aantes) !== null && eventosEstado(aud.Aintermedia) !== null)
    observaciones.push(extrasA.length
    ? `158: auditoría mostró ${extrasA.length} evento(s) del intento no transicional(es): ${extrasA.join(', ')}`
    : '158: no se genera evento de auditoría para el intento rechazado; sin requisito normativo localizado');
  return [c157, c158, c159];
}
