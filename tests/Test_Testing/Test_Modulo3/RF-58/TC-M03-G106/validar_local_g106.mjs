// Pruebas unitarias locales de G106 con sondeos sintéticos (sin red).
import test from 'node:test';
import assert from 'node:assert/strict';
import { duracionS, clasificar, disponibilidad, intervalos, veredicto, contratoDashboard, OBJETIVO } from './ejecutar_tc_m03_g106.mjs';
import { autorizar } from './monitoreo_lib.mjs';

const ok = { total: 0, sensores: [], resumen_unidades: [] };
const s = (t, clase, motivo = null) => ({ t: t * 1000, clase, motivo });

test('duración explícita y válida', () => {
  assert.equal(duracionS('90m'), 5400); assert.equal(duracionS('2d'), 172800); assert.equal(duracionS('3600s'), 3600);
  for (const x of ['', '0h', '1.5h', '24', 'h']) assert.equal(duracionS(x), null);
});
test('clasificación: solo 200 con el contrato es disponible; 5xx, tiempo límite y conexión caída no lo son', () => {
  assert.equal(clasificar({ status: 200, cuerpo: ok, eco: 'R', run: 'R' }).clase, 'DISPONIBLE');
  assert.equal(clasificar({ status: 200, cuerpo: { detail: 'x' }, eco: 'R', run: 'R' }).clase, 'NO_DISPONIBLE');
  assert.equal(clasificar({ status: 502, cuerpo: null }).clase, 'NO_DISPONIBLE');
  assert.equal(clasificar({ error: Object.assign(new Error('The operation was aborted due to timeout'), { name: 'TimeoutError' }) }).clase, 'NO_DISPONIBLE');
  assert.equal(clasificar({ error: Object.assign(new TypeError('fetch failed'), { cause: { code: 'ECONNREFUSED' } }) }).clase, 'NO_DISPONIBLE');
  assert.ok(contratoDashboard(ok)); assert.ok(!contratoDashboard(null));
});
test('clasificación: lo que no depende del servicio es no verificable', () => {
  for (const status of [401, 403, 429]) assert.equal(clasificar({ status, cuerpo: null, eco: 'R', run: 'R' }).clase, 'NO_VERIFICABLE');
  assert.equal(clasificar({ status: 503, cuerpo: { message: 'Se ha alcanzado el máximo de pruebas concurrentes (5).' } }).clase, 'NO_VERIFICABLE');
  assert.equal(clasificar({ status: 200, cuerpo: ok, eco: null, run: 'R' }).clase, 'NO_VERIFICABLE');
  assert.equal(clasificar({ error: Object.assign(new TypeError('fetch failed'), { cause: { code: 'ENOTFOUND' } }) }).clase, 'NO_VERIFICABLE');
});
test('disponibilidad ponderada por tiempo con cotas mínima y máxima', () => {
  const sondeos = [s(0, 'DISPONIBLE'), s(60, 'NO_DISPONIBLE', 'HTTP 502'), s(120, 'NO_VERIFICABLE', 'HTTP 401'), s(180, 'DISPONIBLE')];
  const d = disponibilidad(sondeos, 400 * 1000);
  assert.deepEqual(d.segundos, { DISPONIBLE: 280, NO_DISPONIBLE: 60, NO_VERIFICABLE: 60 });
  assert.equal(d.total_s, 400); assert.equal(d.minima, 280 / 400); assert.equal(d.maxima, 340 / 400);
  assert.equal(disponibilidad([], 1000).minima, null);
});
test('intervalos: une sondeos consecutivos de la misma clase y conserva sus motivos', () => {
  const r = intervalos([s(0, 'DISPONIBLE'), s(60, 'NO_DISPONIBLE', 'HTTP 502'), s(120, 'NO_DISPONIBLE', 'HTTP 504'), s(180, 'DISPONIBLE'), s(240, 'NO_VERIFICABLE', 'HTTP 401')], 300 * 1000);
  assert.equal(r.length, 2);
  assert.deepEqual([r[0].clase, r[0].duracion_s, r[0].motivos], ['NO_DISPONIBLE', 120, ['HTTP 502', 'HTTP 504']]);
  assert.deepEqual([r[1].clase, r[1].duracion_s], ['NO_VERIFICABLE', 60]);
});
test('veredicto por cotas: solo concluye cuando lo no verificable no puede cambiar el resultado', () => {
  assert.equal(OBJETIVO, 0.99);
  assert.equal(veredicto({ estado: 'CONCLUIDA', d: { minima: 0.99, maxima: 0.99 } }), 'APROBADO');
  assert.equal(veredicto({ estado: 'CONCLUIDA', d: { minima: 0.95, maxima: 0.989 } }), 'RECHAZADO');
  assert.equal(veredicto({ estado: 'CONCLUIDA', d: { minima: 0.98, maxima: 1 } }), 'BLOQUEADO');
  assert.equal(veredicto({ estado: 'INTERRUMPIDA', d: { minima: 1, maxima: 1 } }), 'BLOQUEADO');
  assert.equal(veredicto({ estado: 'CONCLUIDA', d: { minima: null, maxima: null } }), 'BLOQUEADO');
});
test('barrera: sin autorización, sin TEST o con API DEV no se ejecuta', () => {
  const v = { QA_AUTORIZADO: 'SI', QA_ENG_EMAIL: 'e@x.test', QA_COMMON_PASSWORD: 'x', QA_SANDBOX_SECRET: 'y', SIGAB_API_TEST_BASE: 'https://www.api.inmero.co/api-sgpmp-test' };
  const a = { ambiente: 'TEST', autorizacion: 'DEV-REF-123', efectos: ['notificacion-login', 'sesion-persistente'] };
  assert.equal(autorizar(v, a, { roles: ['ENG'] }).ok, true);
  assert.equal(autorizar({ ...v, QA_AUTORIZADO: 'NO' }, a, { roles: ['ENG'] }).ok, false);
  assert.equal(autorizar(v, { ...a, ambiente: 'DEV' }, { roles: ['ENG'] }).ok, false);
  assert.equal(autorizar({ ...v, SIGAB_API_TEST_BASE: 'https://api-dev.example' }, a, { roles: ['ENG'] }).ok, false);
});
