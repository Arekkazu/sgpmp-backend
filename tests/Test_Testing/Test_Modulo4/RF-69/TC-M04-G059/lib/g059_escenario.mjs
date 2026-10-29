import crypto from 'node:crypto';

export const CASOS = Object.freeze([161, 162, 163, 164, 165].map(n => `TC-M04-${n}`));
export const IDS = Object.freeze([161, 162, 163, 164, 165].map(n => `API-${n}-01`));
export const TIPO = 'MODELO_ESPECIES_GRANDES';
export const COMBINACIONES = Object.freeze([
  ['161', 'V3', 'APROBADO', 'RECHAZADO'], ['161', 'V3', 'APROBADO', 'DEPRECADO'],
  ['161', 'V3', 'APROBADO', 'EN_VALIDACION'],
  ['162', 'V1', 'ACTIVO', 'APROBADO'], ['162', 'V1', 'ACTIVO', 'RECHAZADO'],
  ['162', 'V1', 'ACTIVO', 'EN_VALIDACION'],
  ['163', 'V1', 'DEPRECADO', 'APROBADO'], ['163', 'V1', 'DEPRECADO', 'ACTIVO'],
  ['163', 'V1', 'DEPRECADO', 'RECHAZADO'], ['163', 'V1', 'DEPRECADO', 'EN_VALIDACION'],
  ['164', 'R', 'RECHAZADO', 'APROBADO'], ['164', 'R', 'RECHAZADO', 'ACTIVO'],
  ['164', 'R', 'RECHAZADO', 'DEPRECADO'], ['164', 'R', 'RECHAZADO', 'EN_VALIDACION']
]);
// Camino completo verificado por el ensayo local; el reenvío puede crear
// una versión adicional y elevar la conciliación poscierre a 101 solicitudes.
// Si el primer PATCH de notas V1 rechaza el campo extra, hay un reintento
// sin ese campo; ambos caminos juntos consumen 102 solicitudes.
export const PRESUPUESTO = Object.freeze({ total: 100, timeout_login_registro_ms: 120000,
  timeout_ms: 30000, duracion_segundos: 900 });
export const CAPACIDADES = Object.freeze({ contrato: 'sigab-qa-ejecutor/1', grupo: 'G059',
  casos: CASOS, operaciones: ['evaluar', 'reintentar', 'reevaluar'], versiones: { min: 1, max: 99 },
  comprobaciones_obligatorias: Object.fromEntries(CASOS.map((c, i) => [c, { API: [IDS[i]] }])),
  limite: { solicitudes_totales: 102, duracion_segundos: 900 } });
export const idVersion = x => x?.id_version_modelo ?? x?.id_version ?? null;
export const registroValido = (x, esperado) => x?.eco === true && idVersion(x.cuerpo) != null
  && x.cuerpo?.estado_version === esperado && (esperado === 'APROBADO'
    ? x.http === 201 : esperado === 'RECHAZADO' && x.http === 200);
export function escenarios({ variable, hash, dataset, archivo, ahora = Date.now() }) {
  return ['V1', 'V2', 'V3', 'R'].map((dato, i) => ({ dato, tipo_modelo: TIPO,
    id_proceso_rf71: crypto.randomUUID(), hash_artefacto_sha256: hash,
    dataset_entrenamiento_hash: dataset,
    metricas_validacion: { f1_score_global: i === 3 ? 0.72 : 0.91,
      recall_clase_riesgo_alto: i === 3 ? 0.95 : 0.93,
      precision_global: 0.92, accuracy: 0.94, roc_auc_score: 0.95,
      recall_por_clase: { riesgo_alto: 0.93, riesgo_bajo: 0.92 },
      matriz_confusion: [[9, 1], [1, 9]] },
    fecha_entrenamiento: new Date(ahora - (4 - i) * 86400000).toISOString(),
    compatibilidad_variables: [variable], archivo_modelo: archivo }));
}
export const estado = (x, valor, produccion) => x?.http === 200 && x.eco === true
  && x.cuerpo?.estado_version === valor && (produccion == null || x.cuerpo?.esta_produccion === produccion);
export const listaUnica = (x, id) => x?.http === 200 && x.eco === true
  && x.cuerpo?.total === 1 && x.cuerpo?.items?.length === 1
  && String(idVersion(x.cuerpo.items[0])) === String(id)
  && x.cuerpo.items[0].estado_version === 'ACTIVO'
  && x.cuerpo.items[0].tipo_modelo === TIPO;
export const eventosEstado = x => x?.http === 200 && x.eco === true && Array.isArray(x.cuerpo?.items)
  ? x.cuerpo.items.filter(y => String(y.tipo_evento ?? '').startsWith('VERSION_'))
    .map(y => [y.tipo_evento, String(y.id_referencia ?? ''), String(y.correlacion_id ?? '')])
    .sort((a, b) => JSON.stringify(a).localeCompare(JSON.stringify(b))) : null;
export const mismosEventos = (a, b) => eventosEstado(a) != null && eventosEstado(b) != null
  && JSON.stringify(eventosEstado(a)) === JSON.stringify(eventosEstado(b));
