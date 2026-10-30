import crypto from 'node:crypto';

export const CASOS = Object.freeze([150, 151, 152, 153].map(n => `TC-M04-${n}`));
export const IDS = Object.freeze([150, 151, 152, 153].map(n => `API-${n}-01`));
// Flujo normal: 30 solicitudes hasta DELETE, más 4 GET de versiones y
// 1 listado para comprobar el rollback fuera del RUN.
export const PRESUPUESTO = Object.freeze({ logins: 2, catalogos: 1, eleccion: 1,
  registros: 4, notas: 2, activaciones: 2, versiones: 6, listados: 5,
  auditorias: 3, ca13: 3, cierre: 1, comprobacion_rollback: 5, total: 35,
  contingencia_maxima: 40, timeout_post_ms: 120000, timeout_ms: 30000, duracion_segundos: 900 });
export const CAPACIDADES = Object.freeze({ contrato: 'sigab-qa-ejecutor/1', grupo: 'G057',
  casos: CASOS, operaciones: ['evaluar', 'reintentar', 'reevaluar'],
  versiones: { min: 1, max: 99 },
  comprobaciones_obligatorias: Object.fromEntries(CASOS.map((c, i) => [c, { API: [IDS[i]] }])),
  limite: { solicitudes_totales: PRESUPUESTO.contingencia_maxima,
    duracion_segundos: PRESUPUESTO.duracion_segundos } });
export const TIPOS = Object.freeze(['MODELO_ESPECIES_GRANDES', 'MODELO_ESPECIES_MEDIANAS']);
export const idVersion = x => x?.id_version_modelo ?? x?.id_version ?? null;
export const llave = x => `${x?.tipo_modelo ?? ''}|${x?.componente ?? '<NULL>'}`;
export function escenarios({ tipo, variable, hash, dataset, archivo, ahora = Date.now(), nombres = ['A', 'B', 'C', 'D'] }) {
  return nombres.map(dato => ({ dato, tipo_modelo: tipo,
    id_proceso_rf71: crypto.randomUUID(), hash_artefacto_sha256: hash,
    dataset_entrenamiento_hash: dataset,
    metricas_validacion: { f1_score_global: 0.91, recall_clase_riesgo_alto: 0.93,
      precision_global: 0.92, accuracy: 0.94, roc_auc_score: 0.95,
      recall_por_clase: { riesgo_alto: 0.93, riesgo_bajo: 0.92 },
      matriz_confusion: [[9, 1], [1, 9]] },
    fecha_entrenamiento: new Date(ahora - 86400000).toISOString(),
    compatibilidad_variables: [variable], archivo_modelo: archivo }));
}

const http4 = x => x?.http >= 400 && x?.http < 500;
const ok2 = x => x?.http >= 200 && x?.http < 300 && x?.eco;
const estado = (x, valor, prod) => x?.http === 200 && x?.eco
  && x?.cuerpo?.estado_version === valor && x?.cuerpo?.esta_produccion === prod;
const lista = (x, tipo, id) => x?.http === 200 && x?.eco
  && Array.isArray(x?.cuerpo?.items) && x.cuerpo.items.length === 1
  && x.cuerpo.total === 1 && x.cuerpo.items[0].tipo_modelo === tipo
  && x.cuerpo.items[0].componente == null
  && String(idVersion(x.cuerpo.items[0])) === String(id);
const evento = (x, tipo) => (x?.cuerpo?.items ?? []).find(y => y.tipo_evento === tipo);
const diagnostico = (nombre, x) => `${nombre} HTTP ${x?.http ?? 'sin respuesta'}, estado ${x?.cuerpo?.estado_version ?? 'nulo'}`;
function decidir(errores, conforme) {
  const e = errores.filter(Boolean);
  if (!e.length) return { estado: 'APROBADO', motivo: conforme };
  const prioridad = ['BLOQUEADO', 'NO_CONCLUYENTE', 'RECHAZADO'];
  const x = prioridad.map(p => e.find(y => y.estado === p)).find(Boolean);
  return x;
}
const fallo = (ok, motivo) => ok ? null : { estado: 'RECHAZADO', motivo };
const sin = (x, nombre) => x?.http == null
  ? { estado: 'NO_CONCLUYENTE', motivo: `${nombre} sin respuesta; requiere conciliación GET/listado` }
  : x.http >= 500 ? { estado: 'NO_CONCLUYENTE', motivo: `${nombre} HTTP ${x.http}; conciliación GET/listado necesaria` } : null;
const sinActivacion = (x, nombre) => x?.http == null ? sin(x, nombre) : null;
const bloqueo = (x, nombre) => x?.http === 403 ? { estado: 'BLOQUEADO', motivo: `${nombre} HTTP 403; clave o permiso no verificado` } : null;

export function evaluarInstantanea(s) {
  const { tipo, ids, respuesta, get, listas, aud, notas, heredada } = s;
  const [A, B, C, D] = ids;
  const anterior = s.contingencia?.anterior ?? A;
  const nueva = s.contingencia?.nueva ?? B;
  const previo151 = s.contingencia?.getPrevia ?? get.A150;
  const res = [];
  const c150 = [sinActivacion(respuesta.A, 'Activar A'), bloqueo(respuesta.A, 'Activar A'),
    fallo(ok2(respuesta.A), diagnostico('Activar A', respuesta.A)),
    fallo(estado(get.A150, 'ACTIVO', true), diagnostico('GET A', get.A150)),
    fallo(respuesta.A?.http >= 500 || lista(listas.A, tipo, A), `Lista tras A: ${listas.A?.cuerpo?.total ?? 'nulo'} ACTIVO; se esperaba solo A`),
    fallo(listas.deprecAntes?.http === 200 && listas.deprecDespues?.http === 200
      && (heredada || JSON.stringify((listas.deprecAntes?.cuerpo?.items ?? []).map(idVersion).sort())
      === JSON.stringify((listas.deprecDespues?.cuerpo?.items ?? []).map(idVersion).sort())),
      'Otra versión del tipo pasó a DEPRECADO durante la primera activación'),
    fallo(!!heredada || !Object.hasOwn(respuesta.A?.cuerpo ?? {}, 'version_deprecada')
      || respuesta.A.cuerpo.version_deprecada == null, 'Respuesta de A reporta versión deprecada')];
  if (heredada) {
    const provisional = decidir(c150, '');
    res.push(provisional.estado === 'APROBADO'
      ? { estado: 'NO_CONCLUYENTE', motivo: `Tipo ${tipo} tenía ACTIVO heredada ${heredada}; sin tipo libre no se comprueba ausencia de deprecación` }
      : provisional);
  }
  else res.push(decidir(c150, `A ${A} ACTIVO; lista ACTIVO={A}; respuesta sin versión deprecada`));
  const c151 = [sinActivacion(respuesta.B, 'Activar B'), bloqueo(respuesta.B, 'Activar B'),
    fallo(ok2(respuesta.B), diagnostico('Activar B', respuesta.B)),
    fallo(estado(get.A151, 'DEPRECADO', false), diagnostico('GET A tras B', get.A151)),
    fallo(estado(get.B151, 'ACTIVO', true), diagnostico('GET B tras B', get.B151)),
    fallo(lista(listas.B, tipo, nueva), `Lista tras B: ${listas.B?.cuerpo?.total ?? 'nulo'} ACTIVO; se esperaba solo ${nueva}`)];
  if (respuesta.B?.http >= 500) {
    c151.push(fallo(estado(get.A151, 'ACTIVO', true), diagnostico('GET previa tras 5xx', get.A151)));
    c151.push(fallo(estado(get.B151, 'APROBADO', false), diagnostico('GET nueva tras 5xx', get.B151)));
  }
  res.push(s.contingencia?.falloInicial5xx
    ? decidir([sin(get.A151, 'GET A'), sin(get.B151, 'GET B'),
      fallo(estado(get.A151, 'APROBADO', false) && estado(get.B151, 'APROBADO', false),
        'A/B no conservaron APROBADO tras ambos 5xx'),
      fallo(false, `Activar B HTTP ${s.contingencia.falloInicial5xx}; sin transición atómica`) ], '')
    : !estado(previo151, 'ACTIVO', true)
    ? { estado: 'NO_CONCLUYENTE', motivo: 'Falta precondición comprobada: A ACTIVO antes de activar B' }
    : decidir(c151, `${anterior} DEPRECADO, ${nueva} ACTIVO; una ACTIVO en ${tipo}|<NULL>`));
  const evA150 = evento(aud.A150, 'VERSION_ACTIVADA');
  const evA151 = evento(aud.A151, 'VERSION_DEPRECADA');
  const evB151 = evento(aud.B151, 'VERSION_ACTIVADA');
  const corrA = evA150?.correlacion_id, corrDep = evA151?.correlacion_id,
    corrB = evB151?.correlacion_id;
  const c152 = [sin(aud.A151, 'Auditoría A'), sin(aud.B151, 'Auditoría B'),
    fallo(aud.A151?.http === 200 && aud.B151?.http === 200,
      `Auditoría A/B HTTP ${aud.A151?.http}/${aud.B151?.http}`),
    fallo(!!evA151 && !!evB151, 'Faltan VERSION_DEPRECADA(A) o VERSION_ACTIVADA(B)'),
    fallo(!!corrDep && !!corrB && corrDep === corrB, `Correlación deprecación/activación ${corrDep ?? 'nula'}/${corrB ?? 'nula'}`),
    fallo(!corrA || corrA !== corrB, 'Correlación de B igual a activación anterior de A')];
  if (s.contingencia?.falloInicial5xx) res.push(decidir([sin(aud.A151, 'Auditoría A'), sin(aud.B151, 'Auditoría B'),
    fallo(false, `Activar A/B HTTP 5xx; no hay par VERSION_DEPRECADA/VERSION_ACTIVADA correlacionado`)], ''));
  else if (!estado(previo151, 'ACTIVO', true)) res.push({ estado: 'NO_CONCLUYENTE', motivo: 'La previa no estaba ACTIVO antes de activar la nueva; no hay deprecación comparable' });
  else if (respuesta.B?.http >= 500) res.push(decidir([sin(aud.A151, 'Auditoría previa'), sin(aud.B151, 'Auditoría nueva'),
    fallo(false, `Activación HTTP ${respuesta.B.http}; auditoría previa/nueva sin par VERSION_DEPRECADA/VERSION_ACTIVADA correlacionado`)], ''));
  else if (!ok2(respuesta.B) && !evA151 && !evB151) res.push({ estado: 'NO_CONCLUYENTE', motivo: 'B no se activó y no hay eventos comparables' });
  else res.push(decidir(c152, `VERSION_DEPRECADA(${anterior}) y VERSION_ACTIVADA(${nueva}) correlacion_id=${corrB}; previa inicial=${corrA ?? 'no expuesto'}`));
  const c153 = [sinActivacion(respuesta.C, 'Activar C'), sinActivacion(respuesta.D, 'Activar D'),
    bloqueo(respuesta.C, 'Activar C'), bloqueo(respuesta.D, 'Activar D'),
    fallo(http4(respuesta.C), `C sin notas: activar HTTP ${respuesta.C?.http}`),
    fallo(http4(respuesta.D), `D con espacios: activar HTTP ${respuesta.D?.http}`),
    fallo(estado(get.C153, 'APROBADO', false) && !get.C153.cuerpo.notas_validacion,
      diagnostico('GET C', get.C153)),
    fallo(estado(get.D153, 'APROBADO', false) && !String(get.D153.cuerpo.notas_validacion ?? '').trim(),
      diagnostico('GET D', get.D153)),
    fallo(get.B153?.http === 200 && get.B153?.eco
      && get.B153.cuerpo?.estado_version === get.B151?.cuerpo?.estado_version
      && get.B153.cuerpo?.esta_produccion === get.B151?.cuerpo?.esta_produccion,
    diagnostico('GET B final', get.B153)),
    fallo(listas.B?.http === 200 && listas.final?.http === 200
      && listas.B?.eco && listas.final?.eco
      && listas.B.cuerpo?.total === listas.final.cuerpo?.total
      && JSON.stringify((listas.B.cuerpo?.items ?? []).map(idVersion).sort((a, b) => a - b))
        === JSON.stringify((listas.final.cuerpo?.items ?? []).map(idVersion).sort((a, b) => a - b)),
    'Lista ACTIVO cambió tras intentos C/D')];
  c153.push(sin(notas.D, 'PATCH D espacios'));
  c153.push(fallo(http4(notas.D) || ok2(notas.D), `PATCH D espacios HTTP ${notas.D?.http}`));
  res.push(decidir(c153, 'C/D APROBADO sin notas; activar C/D 4xx; activa previa intacta'));
  return res;
}
