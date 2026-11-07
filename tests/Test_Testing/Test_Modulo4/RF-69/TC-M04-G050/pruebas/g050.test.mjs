import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { onnxMinimo, savedModelMinimo, validarSavedModel, camposProto, sha256 } from '../lib/artefactos.mjs';
import { CAPACIDADES, CASOS, TIPOS, PRESUPUESTO, INDIVIDUAL, POBLACIONAL } from '../lib/g050_escenario.mjs';
import { validarObligatorias } from './registro_qa.mjs';
import { contextoEjecucion } from '../lib/contrato_ejecutor.mjs';
import { informe, evaluarFormato, evaluarTipos } from '../g050.mjs';
import os from 'node:os';

const dir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const onnx = fs.readFileSync(path.join(dir, 'artefactos/g050.onnx'));
const pb = fs.readFileSync(path.join(dir, 'artefactos/saved_model.pb'));
assert.ok(onnx.equals(onnxMinimo()));
assert.ok(pb.equals(savedModelMinimo()));
assert.equal(onnx.subarray(0, 2).toString('hex'), '0809');
assert.equal(pb.subarray(0, 2).toString('hex'), '0801');
assert.ok(validarSavedModel(pb));
const root = camposProto(pb);
assert.equal(root[0].numero, 1); assert.equal(root[0].wire, 0); assert.equal(root[0].valor, 1);
assert.equal(root[1].numero, 2); assert.equal(root[1].wire, 2);
assert.equal(camposProto(root[1].valor).filter(x => x.numero === 5).length, 1);
// Réplica local de _es_saved_model y _detectar_formato (use case, líneas 88-93 y 303-327).
const detectarFormatoBackend = bytes => {
  let campos;
  try { campos = camposProto(bytes); } catch { campos = null; }
  const savedModel = campos?.length > 0 && campos.every(x => [1, 2].includes(x.numero))
    && campos.some(x => x.numero === 2 && x.wire === 2 && x.valor[0] === 0x0a);
  return savedModel ? 'TENSORFLOW_SAVED_MODEL' : bytes[0] === 0x08 ? 'ONNX' : 'FORMATO_ARTEFACTO_INVALIDO';
};
assert.equal(detectarFormatoBackend(pb), 'TENSORFLOW_SAVED_MODEL');
assert.equal(detectarFormatoBackend(onnx), 'ONNX');
assert.ok(camposProto(onnx).some(x => x.numero === 7));
assert.notEqual(sha256(onnx), sha256(pb));
assert.deepEqual(TIPOS.map(x => x.tipo), [
  'MODELO_ESPECIES_GRANDES', 'MODELO_ESPECIES_MEDIANAS', 'MODELO_RIESGO_CONTAGIO',
  'MODELO_AVES', 'MODELO_PORCINOS', 'MODELO_ACUICULTURA']);
assert.deepEqual(Object.keys(validarObligatorias(CAPACIDADES)), CASOS);
assert.ok(Object.values(CAPACIDADES.comprobaciones_obligatorias).every(x => !('UI' in x)));
assert.equal(PRESUPUESTO.total, 18);
assert.equal(PRESUPUESTO.posts, 7);
assert.equal(PRESUPUESTO.versiones_get, 7);
assert.equal(CAPACIDADES.limite.solicitudes_newman, 14);
const hash = sha256(pb), esperado = { formato: 'TENSORFLOW_SAVED_MODEL', hash };
const aprobado = { estado: 'APROBADO' };
const post = formato => ({ cuerpo: { formato_artefacto: formato, hash_artefacto_sha256: hash } });
const get = formato => ({ cuerpo: { formato_artefacto: formato, hash_artefacto_sha256: hash } });
assert.equal(evaluarFormato(aprobado, post('TENSORFLOW_SAVED_MODEL'), get('TENSORFLOW_SAVED_MODEL'), esperado).estado, 'APROBADO');
assert.equal(evaluarFormato(aprobado, post('ONNX'), get('TENSORFLOW_SAVED_MODEL'), esperado).estado, 'RECHAZADO');
assert.equal(evaluarFormato(aprobado, post('TENSORFLOW_SAVED_MODEL'), get('ONNX'), esperado).estado, 'RECHAZADO');
assert.equal(evaluarFormato(aprobado, { cuerpo: {} }, get('TENSORFLOW_SAVED_MODEL'), esperado).estado, 'APROBADO');
// El formato ONNX de MEDIANAS pertenece al oráculo de 119; 120 conserva sus seis tipos.
const registros = TIPOS.map((d, i) => {
  const cuerpo = { id_version_modelo: i + 101, tipo_modelo: d.tipo, paradigma: d.paradigma,
    componente: d.componente ?? null, estado_version: 'APROBADO',
    formato_artefacto: i === 1 ? 'ONNX' : d.formato,
    ...(d.paradigma === 'POBLACIONAL'
      ? { metricas_poblacionales: POBLACIONAL }
      : { f1_score: INDIVIDUAL.f1_score_global,
        recall_clase_riesgo_alto: INDIVIDUAL.recall_clase_riesgo_alto,
        precision_modelo: INDIVIDUAL.precision_global, accuracy: INDIVIDUAL.accuracy,
        roc_auc_score: INDIVIDUAL.roc_auc_score, recall_por_clase: INDIVIDUAL.recall_por_clase,
        matriz_confusion: INDIVIDUAL.matriz_confusion }) };
  return { post: { http: 201, eco: true, cuerpo }, get: { http: 200, eco: true, cuerpo } };
});
assert.equal(evaluarTipos(registros.map(x => x.post), registros.map(x => x.get), TIPOS).estado120,
  'APROBADO', 'el formato ONNX de MEDIANAS no rechaza 120');
assert.equal(evaluarFormato(aprobado, registros[1].post, registros[1].get, esperado).estado,
  'RECHAZADO');
const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'g050-v2-contexto-'));
try {
  const runId = 'RUN-G050-V2-20261101-000000';
  const runDir = path.join(temp, 'EvaluacionV2', 'Resultados', runId);
  fs.mkdirSync(runDir, { recursive: true });
  const archivo = path.join(runDir, 'contexto_operacion.json');
  fs.writeFileSync(archivo, JSON.stringify({ grupo: 'G050', version: 2, version_anterior: 1,
    intento: 1, run_id: runId, operacion: 'REEVALUAR', referencia: 'ENSAYO_LOCAL',
    alcance_reevaluacion: 'TC-M04-119 y regresión de TC-M04-118 y TC-M04-120', casos: CASOS }));
  const c = contextoEjecucion(['--operacion', 'reevaluar', '--version', '2', '--intento', '1',
    '--run-id', runId, '--autorizacion', 'ENSAYO_LOCAL', '--contexto', archivo],
  { grupo: 'G050', casos: CASOS, directorio: temp });
  assert.equal(c.directorio, runDir);
  const r = JSON.parse(fs.readFileSync(path.join(dir, 'Resultados/RUN-G050-V1-20261028-005856/resultado.json'), 'utf8'));
  r.version = 2; r.run_id = runId; r.casos[CASOS[1]] = { estado: 'APROBADO', motivo: 'POST 201; GET TENSORFLOW_SAVED_MODEL y hash fiel' };
  r.comprobaciones[1].estado = 'APROBADO'; r.comprobaciones[1].motivo = r.casos[CASOS[1]].motivo;
  r.respuestas.posts[1].formato_artefacto = 'TENSORFLOW_SAVED_MODEL';
  r.respuestas.gets[1].formato_artefacto = 'TENSORFLOW_SAVED_MODEL';
  r.incidencias = [];
  const md = informe(r);
  assert.ok(md.includes('Comparación V1 → V2'));
  assert.ok(md.includes('INC-M04-G050-119 CORREGIDA'));
  assert.ok(md.includes('issue #819 / PR #864'));
  assert.equal(/matriz/i.test(md.replaceAll('matriz_confusion', '')), false);
  assert.ok(md.includes('saved_model.pb'));
  assert.ok(md.includes('runtime TensorFlow'));
  assert.ok(md.includes('el formato del artefacto se evalúa en TC-M04-119 y no afecta al veredicto de TC-M04-120'));
} finally { fs.rmSync(temp, { recursive: true, force: true }); }
console.log('OK G050: protobuf SavedModel/ONNX, SHA-256, tipos, contrato y presupuesto');
