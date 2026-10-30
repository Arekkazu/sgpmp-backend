import crypto from 'node:crypto';

export const CASOS = Object.freeze(Array.from({ length: 7 }, (_, i) => `TC-M04-${121 + i}`));
export const IDS = Object.freeze(CASOS.map((_, i) => `API-${121 + i}-01`));
export const METRICAS = Object.freeze({ f1_score_global: 0.91, recall_clase_riesgo_alto: 0.93,
  precision_global: 0.92, accuracy: 0.94, roc_auc_score: 0.95,
  recall_por_clase: { riesgo_alto: 0.93, riesgo_bajo: 0.92 }, matriz_confusion: [[9, 1], [1, 9]] });
export const PRESUPUESTO = Object.freeze({ logins_antes_run: 2, catalogos: 1, listados: 2,
  posts: 23, get_aceptados: 4, delete_run: 1, total: 33,
  duracion_segundos: 900, timeout_ms: 30000, inactividad_maxima_segundos: 180 });
export const CAPACIDADES = Object.freeze({ contrato: 'sigab-qa-ejecutor/1', grupo: 'G051', casos: CASOS,
  operaciones: ['evaluar', 'reintentar', 'reevaluar'], versiones: { min: 1, max: 99 },
  comprobaciones_obligatorias: Object.fromEntries(CASOS.map((caso, i) => [caso, { API: [IDS[i]] }])),
  limite: { solicitudes_directas: 10, solicitudes_newman: 23,
    duracion_segundos: 900, inactividad_maxima_segundos: 180 } });

export function escenarios({ variable, inexistente, hash, dataset, ahora = Date.now(), archivo }) {
  const base = { tipo_modelo: 'MODELO_ESPECIES_GRANDES', hash_artefacto_sha256: hash,
    dataset_entrenamiento_hash: dataset, metricas_validacion: METRICAS,
    fecha_entrenamiento: new Date(ahora - 86400000).toISOString(),
    compatibilidad_variables: [variable], archivo_modelo: archivo };
  const out = [];
  const agregar = (caso, dato, cambio = {}, omitir = [], aceptado = false) => out.push({
    caso, dato, aceptado, id_proceso_rf71: crypto.randomUUID(), ...structuredClone(base),
    ...cambio, omitir });
  agregar(CASOS[0], 'variables existentes / ayer', {}, [], true);
  agregar(CASOS[0], 'variable inexistente', { compatibilidad_variables: [variable, inexistente] });
  agregar(CASOS[1], 'ahora menos 10 s', { fecha_entrenamiento: new Date(ahora - 10000).toISOString() }, [], true);
  agregar(CASOS[1], 'mañana', { fecha_entrenamiento: new Date(ahora + 86400000).toISOString() });
  agregar(CASOS[2], 'tipo inexistente', { tipo_modelo: 'MODELO_QA_INEXISTENTE' });
  agregar(CASOS[2], 'tipo vacío', { tipo_modelo: '' });
  agregar(CASOS[2], 'tipo eliminado RFC-009', { tipo_modelo: 'MODELO_ESPECIES_PEQUEÑAS' });
  for (const campo of ['f1_score_global', 'recall_clase_riesgo_alto', 'matriz_confusion']) {
    const m = structuredClone(METRICAS); delete m[campo];
    agregar(CASOS[3], `sin ${campo}`, { metricas_validacion: m });
  }
  for (const v of [0, 1, -0.01, 1.01]) agregar(CASOS[4], `f1=${v.toFixed(v === 0 || v === 1 ? 1 : 2)}`,
    { metricas_validacion: { ...METRICAS, f1_score_global: v } }, [], v === 0 || v === 1);
  for (const campo of ['hash_artefacto_sha256', 'dataset_entrenamiento_hash']) {
    for (const [dato, valor] of [['63 caracteres', 'a'.repeat(63)], ['65 caracteres', 'a'.repeat(65)],
      ['64 no hexadecimal', `${'a'.repeat(63)}g`]]) agregar(CASOS[5], `${campo}: ${dato}`, { [campo]: valor });
  }
  agregar(CASOS[6], 'sin hash_artefacto_sha256', {}, ['hash_artefacto_sha256']);
  agregar(CASOS[6], 'sin dataset_entrenamiento_hash', {}, ['dataset_entrenamiento_hash']);
  agregar(CASOS[6], 'sin ambos hashes', {}, ['hash_artefacto_sha256', 'dataset_entrenamiento_hash']);
  if (out.length !== 23 || out.filter(x => x.aceptado).length !== 4) throw Error('ESCENARIOS_INCOHERENTES');
  return out;
}
