import test from 'node:test';
import assert from 'node:assert/strict';
import { autorizar, clasificar, clienteSoloRenderiza, decidirVersion, envQa, huella, sqlTestigo, tipoFallo } from './ejecutar_tc_m03_g99.mjs';

test('parser QA no interpreta comentarios ni pierde valores citados', () => {
  assert.deepEqual(envQa('# X=1\nQA_AUTORIZADO="NO"\nQA_DEVICE_PREFIX=QAAUTO'), { QA_AUTORIZADO: 'NO', QA_DEVICE_PREFIX: 'QAAUTO' });
});
test('autorización bloquea NO y DEV antes de red', () => {
  const v = { QA_AUTORIZADO: 'SI', QA_SETUP_EMAIL: 'a', QA_PROD_EMAIL: 'b', QA_SANDBOX_SECRET: 's', QA_COMMON_PASSWORD: 'p', SIGAB_API_TEST_BASE: 'https://www.api.inmero.co/api-sgpmp-test', SIGAB_FRONT_TEST_URL: 'https://api.inmero.co/sigab-test' };
  const a = { ambiente: 'TEST', autorizacion: 'DEV-123456', efectos: ['notificacion-login'] };
  assert.equal(autorizar({ ...v, QA_AUTORIZADO: 'NO' }, a).ok, false);
  assert.equal(autorizar(v, { ...a, ambiente: 'DEV' }).ok, false);
  assert.equal(autorizar(v, a).ok, true);
});
test('snapshot fallido no equivale a huella vacía', () => {
  assert.equal(huella({ status: 403, data: { data: [] } }), null);
  assert.equal(huella({ status: 200, data: { data: [{ n: 0, huella: 'd41d8cd98f00b204e9800998ecf8427e' }] } }).n, 0);
  assert.throws(() => sqlTestigo("x';DROP"));
});
test('precondición o rollback fallido bloquea; aserción observada puede rechazar', () => {
  assert.equal(clasificar([{ ok: false }], [{ ok: false, observado: true }], true), 'BLOQUEADO');
  assert.equal(clasificar([{ ok: true }], [{ ok: false, observado: true }], true), 'RECHAZADO');
  assert.equal(clasificar([{ ok: true }], [{ ok: true }], false), 'BLOQUEADO');
});
test('V1, V2 y reintento siguen el historial sin crear RESULTADOS', () => {
  assert.equal(decidirVersion(1, [], 'evaluacion'), 1);
  assert.equal(decidirVersion(1, ['CONCLUIDA'], 'evaluacion'), 2);
  assert.equal(decidirVersion(2, ['CONCLUIDA'], 'reintento'), 2);
  assert.equal(decidirVersion(2, ['INCIERTO'], 'evaluacion'), null);
});
test('fallos técnicos se etiquetan sin convertirlos en incumplimiento funcional', () => {
  assert.equal(tipoFallo('ETIMEDOUT'), 'INFRAESTRUCTURA');
  assert.equal(tipoFallo('Cypress no completó'), 'AUTOMATIZACION');
  assert.equal(tipoFallo('PRE: evento no observable'), 'PRECONDICION_O_CAPACIDAD');
});
test('inspección del cliente exige paso directo del semáforo backend', () => {
  const x = { hook: 'estado_semaforo: x.estado_semaforo', card: 'semaforoToGauge(sensor.estado_semaforo); <SemaforoPill estado={sensor.estado_semaforo}', escala: "export function semaforoToGauge(estado) { switch ((estado ?? '').toUpperCase()) {}\n}", pill: 'META[normalizar(estado)]' };
  assert.equal(clienteSoloRenderiza(x), true);
  assert.equal(clienteSoloRenderiza({ ...x, escala: x.escala.replace('}', ' valor > 20; }') }), false);
});
