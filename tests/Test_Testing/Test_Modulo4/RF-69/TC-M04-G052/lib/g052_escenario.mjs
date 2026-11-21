import crypto from 'node:crypto';

export const CASOS = Object.freeze(Array.from({ length: 6 }, (_, i) => `TC-M04-${129 + i}`));
export const IDS = Object.freeze(CASOS.map((_, i) => `API-${129 + i}-01`));
export const METRICAS = Object.freeze({ f1_score_global: 0.91, recall_clase_riesgo_alto: 0.93,
  precision_global: 0.92, accuracy: 0.94, roc_auc_score: 0.95,
  recall_por_clase: { riesgo_alto: 0.93, riesgo_bajo: 0.92 }, matriz_confusion: [[9, 1], [1, 9]] });
// Dos logins previos; dentro del RUN: catálogo, siete POST, un listado, siete GET, auditoría,
// seis intentos por rol y seis GET de comprobación por rol, cierre.
export const PRESUPUESTO = Object.freeze({ logins_antes_run: 2, catalogos: 1, posts: 7,
  listados: 1, gets: 7, auditorias: 1, intentos_estado: 12, gets_verificacion: 12, delete_run: 1,
  total: 44, total_sin_veterinario: 31, duracion_segundos: 1200,
  timeout_ms: 30000, timeout_post_ms: 120000, inactividad_maxima_segundos: 180 });
export const CAPACIDADES = Object.freeze({ contrato: 'sigab-qa-ejecutor/1', grupo: 'G052', casos: CASOS,
  operaciones: ['evaluar', 'reintentar', 'reevaluar'], versiones: { min: 1, max: 99 },
  comprobaciones_obligatorias: Object.fromEntries(CASOS.map((caso, i) => [caso, { API: [IDS[i]] }])),
  limite: { solicitudes_totales: PRESUPUESTO.total, duracion_segundos: PRESUPUESTO.duracion_segundos,
    inactividad_maxima_segundos: PRESUPUESTO.inactividad_maxima_segundos } });

export function escenarios({ variable, hash, dataset, archivo, ahora = Date.now() }) {
  const pares = [
    ['129', 0.91, 0.93], ['130', 0.72, 0.95], ['131', 0.95, 0.70],
    ['132-a', 0.80, 0.85], ['132-b', 0.7999, 0.85],
    ['132-c', 0.80, 0.8499], ['132-d', 0.7999, 0.8499]
  ];
  return pares.map(([dato, f1, recall]) => ({
    dato, caso: dato.startsWith('132') ? CASOS[3] : `TC-M04-${dato}`,
    id_proceso_rf71: crypto.randomUUID(), tipo_modelo: 'MODELO_ESPECIES_GRANDES',
    hash_artefacto_sha256: hash, dataset_entrenamiento_hash: dataset,
    metricas_validacion: { ...METRICAS, f1_score_global: f1, recall_clase_riesgo_alto: recall,
      recall_por_clase: { riesgo_alto: recall, riesgo_bajo: METRICAS.recall_por_clase.riesgo_bajo } },
    fecha_entrenamiento: new Date(ahora - 86400000).toISOString(),
    compatibilidad_variables: [variable], archivo_modelo: archivo
  }));
}

export function detalleCubre(detalle, faltan) {
  const s = String(detalle ?? '').toLowerCase();
  const segmentos = s.split(/[;\n]+/);
  return faltan.every(x => segmentos.some(parte =>
    (x === 'f1' ? /f1|f-?score/.test(parte) : /recall/.test(parte))
    && /<|umbral|m[ií]nim|requerid|no alcanz|inferior|debajo/.test(parte)));
}

export function auditoriaValida(items, id, proceso) {
  const propios = (items ?? []).filter(x => String(x.id_referencia ?? x.payload_evento?.id_version) === String(id));
  return ['VERSION_REGISTRADA', 'VERSION_APROBADA'].every(tipo => propios.some(x =>
    x.tipo_evento === tipo && x.tipo_actor === 'SISTEMA' && x.id_usuario == null
    && String(x.id_sistema) === String(proceso)));
}
