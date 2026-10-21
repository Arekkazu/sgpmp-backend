import test from 'node:test';
import assert from 'node:assert/strict';
import { rafagas, aceptarBatch } from './ejecutar_tc_m03_g100.mjs';
import { clasificar, conteo, lectura } from './qa_lote5_base.mjs';

test('ráfaga construye 10 lecturas distintas por sensor con contrato oficial', () => {
  const b = rafagas([{ id: 11 }, { id: 12 }, { id: 13 }], 7, 'QA-G100', Date.UTC(2026, 1, 1));
  assert.equal(b.registros.length, 30);
  assert.equal(new Set(b.registros.map(x => `${x.sensor_id}:${x.timestamp_captura}`)).size, 30);
  assert.equal(new Set(b.registros.map(x => x.sensor_id)).size, 3);
  assert.equal(b.registros[29].valor, 35);
  assert.equal(b.registros[0].origen, 'BUFFER_LOCAL');
});
test('un batch parcial o fallido no es precondición cumplida', () => {
  assert.equal(aceptarBatch({ status: 200, data: { total: 30, aceptados: 29, rechazados: 1 } }, 30), false);
  assert.equal(aceptarBatch({ status: 200, data: { total: 30, aceptados: 30, rechazados: 0, duplicados: 0 } }, 30), true);
});
test('consulta sin permiso no equivale a cero; PRE bloquea y ASSERT rechaza', () => {
  assert.equal(conteo({ status: 403, data: { data: [] } }), null);
  assert.equal(conteo({ status: 200, data: { data: [{ n: '0' }] } }), 0);
  assert.equal(clasificar('CONCLUIDA', [{ ok: false }], [{ ok: false, observado: true }], true), 'BLOQUEADO');
  assert.equal(clasificar('CONCLUIDA', [{ ok: true }], [{ ok: false, observado: true }], true), 'RECHAZADO');
});
test('lectura RF-53 conserva identidad del sensor y timestamp', () => {
  const d = lectura({ dispositivo: 1, sensor: 2, serial: 'QA', valor: 30, fecha: '2026-01-01T00:00:00Z' });
  assert.equal(d.sensor_id, 2);
  assert.equal(d.access_key, 'QA');
  assert.equal(d.timestamp_captura, '2026-01-01T00:00:00Z');
});
