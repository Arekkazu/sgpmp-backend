import crypto from 'node:crypto';

export const CASOS = ['TC-M04-114', 'TC-M04-115', 'TC-M04-116', 'TC-M04-117'];
export const IDS = ['API-114-01', 'API-115-01', 'API-116-01', 'API-117-01'];
export const PRESUPUESTO = Object.freeze({ logins: 2, catalogos: 1, posts: 3,
  versiones_get: 3, auditorias_get: 3, cierres: 1, total: 13,
  duracion_segundos: 600, timeout_ms: 30000, inactividad_maxima_segundos: 180 });
export const CAPACIDADES = Object.freeze({ contrato: 'sigab-qa-ejecutor/1', grupo: 'G049',
  casos: CASOS, operaciones: ['evaluar', 'reintentar', 'reevaluar'],
  versiones: { min: 1, max: 99 }, comprobaciones_obligatorias:
    Object.fromEntries(CASOS.map((c, i) => [c, { API: [IDS[i]] }])),
  limite: { solicitudes_directas: PRESUPUESTO.logins + PRESUPUESTO.catalogos + PRESUPUESTO.cierres,
    solicitudes_newman: PRESUPUESTO.posts + PRESUPUESTO.versiones_get + PRESUPUESTO.auditorias_get,
    duracion_segundos: PRESUPUESTO.duracion_segundos,
    inactividad_maxima_segundos: PRESUPUESTO.inactividad_maxima_segundos } });

const v = n => { const out = []; do { let b = n & 127; n >>>= 7; if (n) b |= 128; out.push(b); } while (n); return out; };
const field = (n, wire, bytes) => [n * 8 + wire, ...bytes];
const str = (n, s) => { const b = Buffer.from(s); return field(n, 2, [...v(b.length), ...b]); };
const msg = (n, b) => field(n, 2, [...v(b.length), ...b]);
const valueInfo = name => {
  const dim = msg(1, field(1, 0, v(1)));
  const tensor = [...field(1, 0, v(1)), ...msg(2, dim)];
  return [...str(1, name), ...msg(2, msg(1, tensor))];
};
// ModelProto ONNX: grafo Identity FLOAT[1], opset 19. No depende de un paquete ni de red.
export function onnxMinimo() {
  const node = [...str(1, 'x'), ...str(2, 'y'), ...str(4, 'Identity')];
  const graph = [...msg(1, node), ...str(2, 'g049_identity'),
    ...msg(11, valueInfo('x')), ...msg(12, valueInfo('y'))];
  return Buffer.from([...field(1, 0, v(9)), ...str(2, 'qa-g049'),
    ...msg(7, graph), ...msg(8, field(2, 0, v(19)))]);
}
export const sha256 = b => crypto.createHash('sha256').update(b).digest('hex');
export const uuid = () => crypto.randomUUID();
export const METRICAS = Object.freeze({ f1_score_global: 0.91, recall_clase_riesgo_alto: 0.93,
  precision_global: 0.92, accuracy: 0.94, roc_auc_score: 0.95,
  recall_por_clase: { riesgo_alto: 0.93, riesgo_bajo: 0.92 }, matriz_confusion: [[9, 1], [1, 9]] });
export const esIdEntero = x => (typeof x === 'number' && Number.isInteger(x) && x > 0)
  || (typeof x === 'string' && /^[1-9][0-9]*$/.test(x));
export const idCanonico = x => esIdEntero(x) ? String(x) : null;
export const idsValidosUnicos = ids => ids.length === 3 && ids.every(esIdEntero)
  && new Set(ids.map(idCanonico)).size === 3;
export const referenciaValida = (idV2, referenciaV3, referenciaV1) => referenciaV1 == null
  && esIdEntero(idV2) && esIdEntero(referenciaV3)
  && idCanonico(idV2) === idCanonico(referenciaV3);
export const idVersion = x => x?.id_version ?? x?.id_version_modelo ?? null;
export const estado = x => x?.estado ?? x?.estado_version ?? null;
export const primera = (...xs) => xs.find(x => x !== undefined && x !== null);

export function metadatosIguales(get, enviado) {
  const m = get?.metricas_validacion ?? {};
  const valores = { f1_score_global: primera(m.f1_score_global, get?.f1_score),
    recall_clase_riesgo_alto: primera(m.recall_clase_riesgo_alto, get?.recall_clase_riesgo_alto),
    precision_global: primera(m.precision_global, get?.precision_modelo),
    accuracy: primera(m.accuracy, get?.accuracy), roc_auc_score: primera(m.roc_auc_score, get?.roc_auc_score),
    recall_por_clase: primera(m.recall_por_clase, get?.recall_por_clase),
    matriz_confusion: primera(m.matriz_confusion, get?.matriz_confusion) };
  const campos = Object.entries(enviado.metricas_validacion).map(([k, x]) => [k,
    typeof x === 'number' ? Number(valores[k]) === x : JSON.stringify(valores[k]) === JSON.stringify(x)]);
  const fecha = primera(get?.fecha_entrenamiento, get?.fecha_de_entrenamiento);
  const registro = primera(get?.timestamp_registro, get?.fecha_registro);
  const faltantes = campos.filter(([, ok]) => !ok).map(([k]) => `metricas_validacion.${k}`);
  if (get?.tipo_modelo !== enviado.tipo_modelo) faltantes.push('tipo_modelo');
  if (estado(get) !== 'APROBADO') faltantes.push('estado');
  if (get?.dataset_entrenamiento_hash !== enviado.dataset_entrenamiento_hash) faltantes.push('dataset_entrenamiento_hash');
  if (primera(get?.hash_artefacto_modelo, get?.hash_artefacto_sha256) !== enviado.hash_artefacto_sha256) faltantes.push('hash_artefacto_modelo');
  if (!fecha || Date.parse(fecha) !== Date.parse(enviado.fecha_entrenamiento)) faltantes.push('fecha_entrenamiento');
  if (!registro || !Number.isFinite(Date.parse(registro))) faltantes.push('timestamp_registro');
  if (String(get?.id_proceso_rf71) !== enviado.id_proceso_rf71) faltantes.push('id_proceso_rf71');
  if (get?.notas_validacion !== null) faltantes.push('notas_validacion');
  return { faltantes, observados: { ...valores, tipo_modelo: get?.tipo_modelo, estado: estado(get),
    dataset_entrenamiento_hash: get?.dataset_entrenamiento_hash,
    hash_artefacto_modelo: primera(get?.hash_artefacto_modelo, get?.hash_artefacto_sha256),
    fecha_entrenamiento: fecha, timestamp_registro: registro,
    id_proceso_rf71: get?.id_proceso_rf71, notas_validacion: get?.notas_validacion } };
}

export function evaluarAuditoria(items, id, proceso) {
  const propios = (items ?? []).filter(e => String(e.id_referencia ?? e.payload_evento?.id_version) === String(id));
  const eventos = propios.filter(e => ['VERSION_REGISTRADA', 'VERSION_APROBADA', 'VERSION_RECHAZADA'].includes(e.tipo_evento));
  const registro = eventos.find(e => e.tipo_evento === 'VERSION_REGISTRADA');
  const resultado = eventos.find(e => ['VERSION_APROBADA', 'VERSION_RECHAZADA'].includes(e.tipo_evento));
  const ok = !!registro && !!resultado && eventos.every(e => e.tipo_actor === 'SISTEMA'
    && e.id_usuario == null && String(e.id_sistema) === String(proceso));
  const snapshot = registro?.payload_evento?.estado_version ?? registro?.payload_evento?.estado;
  const estadoResultado = resultado?.payload_evento?.estado_version ?? resultado?.payload_evento?.estado;
  const esperadoResultado = resultado?.tipo_evento === 'VERSION_APROBADA' ? 'APROBADO' : 'RECHAZADO';
  const notas = [];
  if (ok && snapshot !== undefined && snapshot !== 'EN_VALIDACION')
    notas.push(`payload_evento de VERSION_REGISTRADA refleja ${snapshot}; es una foto del estado final, no la transición. El historial de transiciones no se expone por API pública.`);
  if (ok && estadoResultado !== undefined && estadoResultado !== esperadoResultado)
    notas.push(`payload_evento de ${resultado.tipo_evento} refleja ${estadoResultado}, distinto de ${esperadoResultado}.`);
  const observacion = notas.join(' ') || null;
  return { ok, observacion };
}
export const auditoriaValida = (items, id, proceso) => evaluarAuditoria(items, id, proceso).ok;
