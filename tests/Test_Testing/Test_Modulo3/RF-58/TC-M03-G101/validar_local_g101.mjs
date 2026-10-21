import test from 'node:test';
import assert from 'node:assert/strict';
import { rutaBitacora, eventosBitacora, crearVigenciaSandbox, esperaVigilada } from './ejecutar_tc_m03_g101.mjs';
import { clasificar, lectura, conteo } from '../TC-M03-G100/qa_lote5_base.mjs';

test('descubrimiento de bitácora exige contrato GET concreto y sin parámetros', () => {
  assert.equal(rutaBitacora({ '/iot/monitoreo/dashboard': { get: {} } }), null);
  assert.equal(rutaBitacora({ '/iot/monitoreo/bitacora': { post: {} } }), null);
  assert.equal(rutaBitacora({ '/iot/monitoreo/bitacora': { get: { parameters: [] } } }), '/iot/monitoreo/bitacora');
});
test('eventos se correlacionan con sensor y momento del RUN', () => {
  const desde = Date.parse('2026-01-01T00:00:00Z');
  const e = eventosBitacora({ items: [
    { id_sensor: 5, fecha_evento: '2026-01-01T00:00:01Z', tipo_evento: 'DEGRADACION_LEVE' },
    { id_sensor: 6, fecha_evento: '2026-01-01T00:00:01Z', tipo_evento: 'DEGRADACION_SEVERA' },
    { id_sensor: 5, fecha_evento: '2025-12-31T23:59:59Z', tipo_evento: 'DEGRADACION_MODERADA' },
  ] }, [5], desde);
  assert.deepEqual(e, ['DEGRADACION_LEVE']);
});
test('50 lecturas conservan IDs dinámicos; consultas denegadas no equivalen a vacío', () => {
  const xs = Array.from({ length: 50 }, (_, i) => lectura({ dispositivo: 1, sensor: i + 1, serial: 'QA', valor: 25, fecha: '2026-01-01T00:00:00Z' }));
  assert.equal(new Set(xs.map(x => x.sensor_id)).size, 50);
  assert.equal(conteo({ status: 403, data: { data: [] } }), null);
});
test('PRE de estímulo/bitácora bloquea sin ocultar aserción funcional', () => {
  assert.equal(clasificar('CONCLUIDA', [{ ok: false }], [{ ok: false, observado: true }], true), 'BLOQUEADO');
  assert.equal(clasificar('CONCLUIDA', [{ ok: true }], [{ ok: false, observado: true }], true), 'RECHAZADO');
});
test('vigencia: testigo del mismo RUN confirma continuidad', async () => {
  let actual = 1000;
  const vigencia = crearVigenciaSandbox({ ttlMs: 180000, ahora: () => actual });
  const testigo = { status: 200, data: { data: [{ n: 1 }] } };
  assert.equal(vigencia.confirmar(testigo), true);
  actual += 45000;
  assert.equal(vigencia.confirmar(testigo), true);
  assert.equal(vigencia.vigente(), true);
  const r = await esperaVigilada({ duracionMs: 35, intervaloMs: 10, sonda: async () => testigo, vigencia });
  assert.equal(r.ok, true);
});
test('vigencia: falla de mantenimiento interrumpe espera antes del plazo', async () => {
  const vigencia = crearVigenciaSandbox();
  let llamadas = 0;
  const inicio = Date.now();
  const r = await esperaVigilada({ duracionMs: 500, intervaloMs: 10, vigencia, sonda: async () => (++llamadas === 1 ? { status: 200, data: { data: [{ n: 1 }] } } : { status: 503, data: null }) });
  assert.equal(r.ok, false);
  assert.match(r.motivo, /testigo del RUN no verificable/);
  assert.ok(Date.now() - inicio < 400);
  assert.equal(vigencia.confirmar({ status: 200, data: { data: [{ n: 1 }] } }), false);
});
test('vigencia: TTL agotado bloquea aunque la siguiente respuesta parezca correcta', () => {
  let actual = 0;
  const vigencia = crearVigenciaSandbox({ ttlMs: 180000, ahora: () => actual });
  const testigo = { status: 200, data: { data: [{ n: 1 }] } };
  assert.equal(vigencia.confirmar(testigo), true);
  actual = 180000;
  assert.equal(vigencia.vigente(), false);
  assert.equal(vigencia.confirmar(testigo), false);
  assert.match(vigencia.fallo, /TTL/);
});
