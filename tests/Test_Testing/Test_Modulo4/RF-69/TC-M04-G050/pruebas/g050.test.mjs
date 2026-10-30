import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { onnxMinimo, savedModelMinimo, validarSavedModel, camposProto, sha256 } from '../lib/artefactos.mjs';
import { CAPACIDADES, CASOS, TIPOS, PRESUPUESTO } from '../lib/g050_escenario.mjs';
import { validarObligatorias } from './registro_qa.mjs';

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
console.log('OK G050: protobuf SavedModel/ONNX, SHA-256, tipos, contrato y presupuesto');
