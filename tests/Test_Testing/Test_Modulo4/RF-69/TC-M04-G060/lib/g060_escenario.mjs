import crypto from 'node:crypto';

export const CASOS = Object.freeze([166, 167, 168, 169].map(n => `TC-M04-${n}`));
export const IDS = Object.freeze([166, 167, 168, 169].map(n => `API-${n}-01`));
export const LLAVES = Object.freeze({
  166: { tipo: 'MODELO_PORCINOS', componente: 'DETECTOR' },
  167: { tipo: 'MODELO_ACUICULTURA', componente: 'DETECTOR' },
  168: { tipo: 'MODELO_AVES', componente: 'ANOMALIAS' },
  169: [
    { tipo: 'MODELO_ESPECIES_GRANDES', componente: null },
    { tipo: 'MODELO_ESPECIES_MEDIANAS', componente: null },
    { tipo: 'MODELO_RIESGO_CONTAGIO', componente: null },
    { tipo: 'MODELO_AVES', componente: 'DETECTOR' }
  ]
});
// Línea base histórica exclusiva del intento 1: no sustituye una lectura inicial
// guardada por otro RUN. G056 confirma los tipos 57/43/42, pero su proyección no
// incluye componente; G057 aporta el componente null y el listado global completo.
export const LINEA_BASE_RECUPERACION = Object.freeze({
  run: 'RUN-G060-V1-20261028-162607',
  por_llave: Object.freeze({
    'MODELO_ESPECIES_GRANDES/SIN_COMPONENTE': Object.freeze({ ids: Object.freeze([]),
      fuente: 'G059/RUN-G059-V1-20261028-153353/resultado.json: solicitudes GET inicial y poscierre, total 0 (15:34 UTC)' }),
    'MODELO_ESPECIES_MEDIANAS/SIN_COMPONENTE': Object.freeze({ ids: Object.freeze([43]),
      fuente: 'G057/RUN-G057-V1-20261028-064235/resultado.json: listado ACTIVO global, id 43, componente null; G056/RUN-G056-V1-20261028-051318/resultado.json: tipo y estado del id 43' }),
    'MODELO_RIESGO_CONTAGIO/SIN_COMPONENTE': Object.freeze({ ids: Object.freeze([57]),
      fuente: 'G057/RUN-G057-V1-20261028-064235/resultado.json: listado ACTIVO global, id 57, componente null; G056/RUN-G056-V1-20261028-051318/resultado.json: tipo y estado del id 57' }),
    'MODELO_AVES/DETECTOR': Object.freeze({ ids: Object.freeze([]),
      fuente: 'G057/RUN-G057-V1-20261028-064235/resultado.json: listado ACTIVO global completo (57, 56, 43, 42), sin AVES/DETECTOR; id 42 tiene componente null; G056/RUN-G056-V1-20261028-051318/resultado.json: tipo y estado del id 42' })
  })
});
export const INDIVIDUAL = Object.freeze({ f1_score_global: 0.91, recall_clase_riesgo_alto: 0.93,
  precision_global: 0.92, accuracy: 0.94, roc_auc_score: 0.95,
  recall_por_clase: { riesgo_alto: 0.93, riesgo_bajo: 0.92 }, matriz_confusion: [[9, 1], [1, 9]] });
export const POBLACIONAL = Object.freeze({ calibracion_completada: true,
  tasa_falsos_positivos_rutina: 0.02, tasa_deteccion_eventos_clinicos: 0.96,
  f1_score_global: 0.91, recall_clase_riesgo_alto: 0.93 });
export const PRESUPUESTO = Object.freeze({ versiones_normales: 22, versiones_maximas: 58,
  solicitudes_normales: 377, solicitudes_maximas: 503, timeout_login_registro_ms: 120000,
  timeout_ms: 30000, duracion_segundos: 900 });
export const CAPACIDADES = Object.freeze({ contrato: 'sigab-qa-ejecutor/1', grupo: 'G060',
  casos: CASOS, operaciones: ['evaluar', 'reintentar', 'reevaluar', 'recuperar'], versiones: { min: 1, max: 99 },
  comprobaciones_obligatorias: Object.fromEntries(CASOS.map((c, i) => [c, { API: [IDS[i]] }])),
  limite: { solicitudes_totales: PRESUPUESTO.solicitudes_maximas, duracion_segundos: 900 } });
export const idVersion = x => x?.id_version_modelo ?? x?.id_version ?? null;
export const llaveId = k => `${k.tipo}/${k.componente ?? 'SIN_COMPONENTE'}`;
export const clave = k => ({ tipo_modelo: k.tipo, componente: k.componente });
export const version = (k, variable, hash, archivo, ahora = Date.now()) => ({
  tipo_modelo: k.tipo, componente: k.componente,
  id_proceso_rf71: crypto.randomUUID(), hash_artefacto_sha256: hash,
  dataset_entrenamiento_hash: crypto.createHash('sha256').update('G060 dataset QA RF-71').digest('hex'),
  metricas_validacion: k.componente ? POBLACIONAL : INDIVIDUAL,
  fecha_entrenamiento: new Date(ahora - 86400000).toISOString(),
  compatibilidad_variables: [variable], archivo_modelo: archivo
});
export const resumenVersion = x => ({ id: idVersion(x), estado: x?.estado_version ?? null,
  produccion: x?.esta_produccion ?? null, tipo: x?.tipo_modelo ?? null,
  componente: x?.componente ?? null });
export const eventosVersion = x => (x?.items ?? []).filter(e =>
  ['VERSION_ACTIVADA', 'VERSION_DEPRECADA'].includes(e.tipo_evento))
  .map(e => ({ tipo: e.tipo_evento, ref: String(e.id_referencia),
    correlacion: String(e.correlacion_id ?? '') }));
export const sinDuplicados = eventos => {
  const llaves = eventos.map(e => `${e.tipo}/${e.ref}`);
  return llaves.length === new Set(llaves).size;
};
export const solapadas = respuestas => respuestas.length > 1 && respuestas.every(x =>
  Number.isFinite(x.envio_ms) && Number.isFinite(x.respuesta_ms))
  && Math.max(...respuestas.map(x => x.envio_ms)) < Math.min(...respuestas.map(x => x.respuesta_ms));

export function decidirDisparo({ caso, claveCaso, previos, candidatos, respuestas, posteriores,
  activos, eventosAntes, eventosDespues, eventoConflicto = false, repeticion = null }) {
  const observaciones = [], fallos = [];
  const nombre = repeticion ? `${caso} repetición ${repeticion}` : caso;
  if (respuestas.some(x => x.http == null) || !Array.isArray(activos)
    || posteriores.some(x => x.http !== 200) || !Array.isArray(eventosDespues))
    return { estado: 'NO_CONCLUYENTE', motivo: `${nombre}: respuesta o conciliación incompleta`, observaciones };
  const deClave = x => x.tipo === claveCaso.tipo && (x.componente ?? null) === claveCaso.componente;
  const enClave = activos.filter(deClave);
  if (enClave.length !== 1 || enClave[0].estado !== 'ACTIVO')
    fallos.push(`${enClave.length} ACTIVO para ${llaveId(claveCaso)}; se esperaba 1`);
  const ids = new Set(candidatos.map(String));
  for (const p of posteriores) {
    if (p.cuerpo && !['APROBADO', 'ACTIVO', 'DEPRECADO'].includes(p.cuerpo.estado_version))
      fallos.push(`versión ${idVersion(p.cuerpo)} en estado ${p.cuerpo.estado_version}`);
    if (p.cuerpo && (p.cuerpo.estado_version === 'ACTIVO') !== (p.cuerpo.esta_produccion === true))
      fallos.push(`versión ${idVersion(p.cuerpo)} con estado y esta_produccion inconsistentes`);
  }
  const nuevos = eventosDespues.filter(e => !eventosAntes.some(a =>
    a.tipo === e.tipo && a.ref === e.ref && a.correlacion === e.correlacion));
  if (!sinDuplicados(eventosDespues)) fallos.push('eventos VERSION_ACTIVADA o VERSION_DEPRECADA duplicados');
  const act = nuevos.filter(e => e.tipo === 'VERSION_ACTIVADA');
  const dep = nuevos.filter(e => e.tipo === 'VERSION_DEPRECADA');
  for (const p of posteriores) {
    const id = String(idVersion(p.cuerpo));
    if (p.cuerpo?.estado_version === 'ACTIVO' && ids.has(id)
      && !act.some(e => e.ref === id)) fallos.push(`versión ${id} ACTIVO sin VERSION_ACTIVADA`);
    if (p.cuerpo?.estado_version === 'DEPRECADO'
      && !dep.some(e => e.ref === id)) fallos.push(`versión ${id} DEPRECADO sin VERSION_DEPRECADA`);
  }
  for (const e of dep) if (!act.some(a => a.correlacion && a.correlacion === e.correlacion))
    fallos.push(`deprecación ${e.ref} sin activación con igual correlacion_id`);
  for (const e of act) if (!e.correlacion) fallos.push(`activación ${e.ref} sin correlacion_id`);
  if (caso === 'TC-M04-166') {
    const ok = respuestas.filter(x => x.http >= 200 && x.http < 300);
    if (ok.length === 2) {
      if (solapadas(respuestas)) fallos.push('ambas solicitudes 2xx con intervalos de servicio solapados');
      else observaciones.push('El servidor serializó las activaciones; no se observó rechazo por concurrencia');
    } else if (ok.length !== 1) fallos.push(`${ok.length} activaciones 2xx; se esperaba una`);
    const perdedor = respuestas.find(x => x.http >= 400);
    const ganador = respuestas.find(x => x.http >= 200 && x.http < 300);
    if (ganador && respuestas.filter(x => x.http >= 200 && x.http < 300).length === 1
      && posteriores[respuestas.indexOf(ganador)]?.cuerpo?.estado_version !== 'ACTIVO')
      fallos.push(`ganador ${candidatos[respuestas.indexOf(ganador)]} no quedó ACTIVO`);
    if (perdedor && respuestas.filter(x => x.http >= 200 && x.http < 300).length === 1) {
      const indice = respuestas.indexOf(perdedor);
      if (posteriores[indice]?.cuerpo?.estado_version !== 'APROBADO')
        fallos.push(`perdedor ${candidatos[indice]} no conservó APROBADO`);
    }
    if (perdedor?.http >= 500) observaciones.push('Perdedor HTTP 5xx con estado coherente; E6 permite rollback');
    if (!eventoConflicto)
      observaciones.push('No se observó evento propio del intento conflictivo; FA-09 no consta en RF-69 v2.1');
  }
  if (caso === 'TC-M04-167') {
    const x = String(candidatos[0]), p = String(previos[0]);
    if (act.filter(e => e.ref === x).length !== 1 || dep.filter(e => e.ref === p).length !== 1)
      fallos.push(`activaciones de X=${act.filter(e => e.ref === x).length}; deprecaciones de P=${dep.filter(e => e.ref === p).length}; se esperaba 1 de cada`);
    if (posteriores.find(y => String(idVersion(y.cuerpo)) === x)?.cuerpo?.estado_version !== 'ACTIVO'
      || posteriores.find(y => String(idVersion(y.cuerpo)) === p)?.cuerpo?.estado_version !== 'DEPRECADO')
      fallos.push('X no quedó ACTIVO o P no quedó DEPRECADO');
    if (respuestas.some(x => x.http >= 500)) fallos.push('respuesta 5xx en solicitud idéntica');
    if (respuestas.filter(x => x.http >= 200 && x.http < 300).length === 0)
      fallos.push('ninguna solicitud 2xx');
  }
  if (caso === 'TC-M04-168') {
    if (candidatos.length !== 5 || respuestas.length !== 5) fallos.push('no se dispararon cinco solicitudes');
    if (enClave.length === 1 && !ids.has(String(enClave[0].id))) fallos.push('ACTIVO final ajeno a las cinco versiones');
  }
  if (caso === 'TC-M04-169' && respuestas.some(x => !(x.http >= 200 && x.http < 300)))
    fallos.push('alguna llave distinta fue cancelada o revertida');
  return { estado: fallos.length ? 'RECHAZADO' : 'APROBADO',
    motivo: fallos.join('; ') || `${nombre}: estado y eventos coherentes; HTTP ${respuestas.map(x => x.http).join('/')}`,
    observaciones };
}
