import test from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import { onnxMinimo, sha256, esIdEntero, idsValidosUnicos, referenciaValida,
  metadatosIguales, auditoriaValida, METRICAS } from '../lib/g049_escenario.mjs';
import { rutaResultados, alcanceReevaluacionValido } from '../lib/contrato_ejecutor.mjs';
import { sanearArtefacto, contieneMojibake } from '../lib/seguridad.mjs';

test('ONNX mínimo determinista con hash real y cabecera ModelProto', () => {
  const a = onnxMinimo(), b = onnxMinimo();
  assert.deepEqual(a, b);
  assert.equal(a[0], 0x08);
  assert.equal(a[1], 9);
  assert.equal(sha256(a), sha256(b));
  assert.ok(a.includes(Buffer.from('Identity')));
});

test('oráculo de id entero positivo, único y referencia V3', () => {
  assert.equal(idsValidosUnicos([58, 59, 60]), true);
  assert.equal(idsValidosUnicos([58, 58, 60]), false);
  assert.equal(idsValidosUnicos(['aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa1', 59, 60]), false);
  for (const x of [null, 0, -1, 1.5, '0', '058', '1.5']) assert.equal(esIdEntero(x), false);
  assert.equal(idsValidosUnicos(['58', 59, 60]), true);
  assert.equal(referenciaValida(59, 59, null), true);
  assert.equal(referenciaValida(59, '59', undefined), true);
  assert.equal(referenciaValida(59, 60, null), false);
  assert.equal(referenciaValida(59, 59, 58), false);
});

test('contexto REEVALUAR V2 exige versión anterior 1 y ruta EvaluacionV2', () => {
  const run = 'RUN-G049-V2-20261031-120000';
  assert.equal(rutaResultados('grupo', 'G049', 2, run),
    path.join('grupo', 'EvaluacionV2', 'Resultados', run));
  assert.equal(alcanceReevaluacionValido({ alcance_reevaluacion: 'TC-M04-115', version_anterior: 1 }, 2), true);
  assert.equal(alcanceReevaluacionValido({ alcance_reevaluacion: 'TC-M04-115', version_anterior: 2 }, 2), false);
});

test('metadatos evalúa equivalencias de respuesta', () => {
  const enviado = { tipo_modelo: 'MODELO_ESPECIES_GRANDES', metricas_validacion: METRICAS,
    dataset_entrenamiento_hash: 'a'.repeat(64), hash_artefacto_sha256: 'b'.repeat(64),
    fecha_entrenamiento: '2026-10-25T00:00:00Z', id_proceso_rf71: 'p' };
  const obtenido = { tipo_modelo: enviado.tipo_modelo, estado_version: 'APROBADO',
    f1_score: '0.91', recall_clase_riesgo_alto: '0.93', precision_modelo: '0.92',
    accuracy: '0.94', roc_auc_score: '0.95', recall_por_clase: METRICAS.recall_por_clase,
    matriz_confusion: METRICAS.matriz_confusion, dataset_entrenamiento_hash: enviado.dataset_entrenamiento_hash,
    hash_artefacto_sha256: enviado.hash_artefacto_sha256,
    fecha_entrenamiento: enviado.fecha_entrenamiento, fecha_registro: '2026-10-27T00:00:00Z',
    id_proceso_rf71: 'p', notas_validacion: null };
  assert.deepEqual(metadatosIguales(obtenido, enviado).faltantes, []);
  delete obtenido.roc_auc_score;
  assert.deepEqual(metadatosIguales(obtenido, enviado).faltantes, ['metricas_validacion.roc_auc_score']);
});

test('auditoría exige eventos de sistema y origen RF-71; admite snapshot final', () => {
  const items = [
    { tipo_evento: 'VERSION_REGISTRADA', tipo_actor: 'SISTEMA', id_usuario: null,
      id_sistema: 'p', id_referencia: 'v', payload_evento: { estado_version: 'EN_VALIDACION' } },
    { tipo_evento: 'VERSION_APROBADA', tipo_actor: 'SISTEMA', id_usuario: null,
      id_sistema: 'p', id_referencia: 'v', payload_evento: { estado_version: 'APROBADO' } },
  ];
  assert.equal(auditoriaValida(items, 'v', 'p'), true);
  items[0].payload_evento.estado_version = 'APROBADO';
  assert.equal(auditoriaValida(items, 'v', 'p'), true);
  items[0].tipo_actor = 'USUARIO';
  assert.equal(auditoriaValida(items, 'v', 'p'), false);
  items[0].tipo_actor = 'SISTEMA';
  items[0].id_sistema = 'otro';
  assert.equal(auditoriaValida(items, 'v', 'p'), false);
  items[0].id_sistema = 'p';
  items.pop();
  assert.equal(auditoriaValida(items, 'v', 'p'), false);
});

test('clave interna y secretos se eliminan del resumen Newman', () => {
  const clave = 'CLAVE_QA_SECRETA_123456';
  const x = sanearArtefacto(JSON.stringify({ header: [{ key: 'X-RF71-Internal-Key', value: clave }],
    request: { raw: clave }, token: 'abc.def.ghi' }), [clave]);
  assert.ok(!x.includes(clave));
  assert.ok(!x.includes('abc.def.ghi'));
  assert.equal(contieneMojibake('Versión automática'), false);
});
