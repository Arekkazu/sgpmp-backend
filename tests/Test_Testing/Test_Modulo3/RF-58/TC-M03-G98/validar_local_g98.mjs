import test from 'node:test';
import assert from 'node:assert/strict';
import { autorizar, cobertura, resultado, SEVERIDADES, leerEnv } from './ejecutar_tc_m03_g98.mjs';

const v = { QA_AUTORIZADO: 'SI', QA_PROD_EMAIL: 'qa@example.test', QA_COMMON_PASSWORD: 'x', QA_SANDBOX_SECRET: 'y', SIGAB_API_TEST_BASE: 'https://www.api.inmero.co/api-sgpmp-test' };
const a = { ambiente: 'TEST', autorizacion: 'DEV-REF-123', efectos: ['notificacion-login'] };
const alertas = SEVERIDADES.map((severidad, i) => ({ id_alerta: i + 1, estado_alerta: 'ACTIVA', id_infraestructura: 20, id_sensor: i + 10, id_activo_biologico: 30, severidad }));
test('parser de configuración', () => assert.deepEqual(leerEnv('QA_AUTORIZADO=NO\nQA_PROD_EMAIL="qa@example.test"'), { QA_AUTORIZADO: 'NO', QA_PROD_EMAIL: 'qa@example.test' }));
test('barrera niega ausencia de autorización y DEV', () => {
  assert.equal(autorizar(v, a).ok, true);
  assert.equal(autorizar({ ...v, QA_AUTORIZADO: 'NO' }, a).ok, false);
  assert.equal(autorizar(v, { ...a, ambiente: 'DEV' }).ok, false);
});
test('fixture exige tres severidades, misma unidad y sensores distintos', () => {
  assert.equal(cobertura(alertas)?.[0], 20);
  assert.equal(cobertura(alertas.slice(1)), null);
  assert.equal(cobertura(alertas.map(x => ({ ...x, id_sensor: 10 }))), null);
  assert.equal(cobertura(alertas.map((x, i) => ({ ...x, id_infraestructura: i + 1 }))), null);
  assert.equal(cobertura([...alertas, { ...alertas[0], id_alerta: 5 }]), null);
});
test('veredicto exige cada aserción', () => {
  const xs = ['API-191-01', 'API-191-02', 'API-191-03', 'API-191-04'].map(nombre => ({ nombre, ok: true }));
  assert.equal(resultado(xs), true);
  assert.equal(resultado(xs.slice(1)), false);
  assert.equal(resultado(xs.map((x, i) => ({ ...x, ok: i !== 2 }))), false);
});
