import crypto from 'node:crypto';

export const CASOS = Object.freeze([146, 147, 148, 149].map(n => `TC-M04-${n}`));
export const IDS = Object.freeze([146, 147, 148, 149].map(n => `API-${n}-01`));
export const METRICAS = Object.freeze({ f1_score_global: 0.91, recall_clase_riesgo_alto: 0.93,
  precision_global: 0.92, accuracy: 0.94, roc_auc_score: 0.95,
  recall_por_clase: { riesgo_alto: 0.93, riesgo_bajo: 0.92 }, matriz_confusion: [[9, 1], [1, 9]] });
// 2 login, 1 catálogo, 4 POST, 4 solicitudes de notas/lectura, 20 de rechazo/historial,
// 1 GET de permanencia, 8 listados (4 por rol), 1 cierre.
export const PRESUPUESTO = Object.freeze({ logins: 2, catalogos: 1, posts: 4,
  notas_y_lecturas: 4, rechazo_historial: 20, permanencia: 1, listados: 8,
  cierre: 1, total: 41, duracion_segundos: 900, timeout_post_ms: 120000,
  timeout_ms: 30000 });
export const CAPACIDADES = Object.freeze({ contrato: 'sigab-qa-ejecutor/1', grupo: 'G056',
  casos: CASOS, operaciones: ['evaluar', 'reintentar', 'reevaluar'], versiones: { min: 1, max: 99 },
  comprobaciones_obligatorias: Object.fromEntries(CASOS.map((x, i) => [x, { API: [IDS[i]] }])),
  limite: { solicitudes_totales: PRESUPUESTO.total, duracion_segundos: PRESUPUESTO.duracion_segundos } });
export function escenarios({ variable, hash, dataset, archivo, ahora = Date.now() }) {
  return [['V1', 0.91, 0.93], ['V1b', 0.91, 0.93], ['V2', 0.72, 0.95], ['V3', 0.91, 0.93]].map(([dato, f1, recall]) => ({
    dato, id_proceso_rf71: crypto.randomUUID(), tipo_modelo: 'MODELO_ESPECIES_GRANDES',
    hash_artefacto_sha256: hash, dataset_entrenamiento_hash: dataset,
    metricas_validacion: { ...METRICAS, f1_score_global: f1, recall_clase_riesgo_alto: recall,
      recall_por_clase: { riesgo_alto: recall, riesgo_bajo: 0.92 } },
    fecha_entrenamiento: new Date(ahora - 86400000).toISOString(),
    compatibilidad_variables: [variable], archivo_modelo: archivo
  }));
}
export const idVersion = x => x?.id_version_modelo ?? x?.id_version ?? null;
export function metricasCompletas(x) {
  return ['f1_score', 'recall_clase_riesgo_alto', 'precision_modelo', 'accuracy',
    'roc_auc_score', 'recall_por_clase', 'matriz_confusion'].every(k => x?.[k] != null);
}
