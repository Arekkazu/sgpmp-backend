export const CASOS = ['TC-M04-118', 'TC-M04-119', 'TC-M04-120'];
export const IDS = ['API-118-01', 'API-119-01', 'API-120-01'];
export const TIPOS = [
  { tipo: 'MODELO_ESPECIES_GRANDES', paradigma: 'INDIVIDUAL', formato: 'ONNX' },
  { tipo: 'MODELO_ESPECIES_MEDIANAS', paradigma: 'INDIVIDUAL', formato: 'TENSORFLOW_SAVED_MODEL' },
  { tipo: 'MODELO_RIESGO_CONTAGIO', paradigma: 'META', formato: 'ONNX' },
  { tipo: 'MODELO_AVES', paradigma: 'POBLACIONAL', formato: 'ONNX', componente: 'DETECTOR' },
  { tipo: 'MODELO_PORCINOS', paradigma: 'POBLACIONAL', formato: 'ONNX', componente: 'SEGUIMIENTO' },
  { tipo: 'MODELO_ACUICULTURA', paradigma: 'POBLACIONAL', formato: 'ONNX', componente: 'ANOMALIAS' }
];
export const INDIVIDUAL = Object.freeze({ f1_score_global: 0.91, recall_clase_riesgo_alto: 0.93,
  precision_global: 0.92, accuracy: 0.94, roc_auc_score: 0.95,
  recall_por_clase: { riesgo_alto: 0.93, riesgo_bajo: 0.92 }, matriz_confusion: [[9, 1], [1, 9]] });
export const POBLACIONAL = Object.freeze({ calibracion_completada: true,
  tasa_falsos_positivos_rutina: 0.02, tasa_deteccion_eventos_clinicos: 0.96,
  f1_score_global: 0.91, recall_clase_riesgo_alto: 0.93 });
export const PRESUPUESTO = Object.freeze({ logins: 2, catalogos: 1, posts: 7,
  versiones_get: 7, cierres: 1, total: 18, duracion_segundos: 600,
  timeout_ms: 30000, inactividad_maxima_segundos: 180 });
export const CAPACIDADES = Object.freeze({ contrato: 'sigab-qa-ejecutor/1', grupo: 'G050',
  casos: CASOS, operaciones: ['evaluar', 'reintentar', 'reevaluar'],
  versiones: { min: 1, max: 99 }, comprobaciones_obligatorias:
    Object.fromEntries(CASOS.map((c, i) => [c, { API: [IDS[i]] }])),
  limite: { solicitudes_directas: 4, solicitudes_newman: 14,
    duracion_segundos: 600, inactividad_maxima_segundos: 180 } });
export const idVersion = x => x?.id_version_modelo ?? x?.id_version ?? null;
export const estado = x => x?.estado_version ?? x?.estado ?? null;
