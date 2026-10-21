// Pruebas unitarias locales de G103: funciones puras y script de la colección con respuestas y
// tiempos sintéticos (sin red). Los datos sintéticos solo validan la lógica de las aserciones.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { CASOS, REQUERIDAS, SENSORES, UMBRAL_MS, MUESTRAS, nombresUnidad, resumenMedicion } from './ejecutar_tc_m03_g103.mjs';
import { autorizar, estadisticos, veredictoCasos, leerConteo, serialQa } from './monitoreo_lib.mjs';

const col = JSON.parse(fs.readFileSync(new URL('./TC-M03-G103.postman_collection.json', import.meta.url), 'utf8'));
const script = col.item[0].event.find(e => e.listen === 'test').script.exec.join('\n');
const ids = Array.from({ length: 50 }, (_, i) => i + 1);

function correr({ iteracion, ms, code = 200, sensores }) {
  const tests = [];
  const pm = {
    response: { code, responseTime: ms, json: () => ({ sensores }) },
    environment: { get: k => ({ ids_u50: JSON.stringify(ids), umbral_ms: String(UMBRAL_MS) })[k] },
    info: { iteration: iteracion },
    test: (n, f) => { try { f(); tests.push({ n, ok: true }); } catch (e) { tests.push({ n, ok: false }); } },
    expect: (x, m) => ({ to: { eql: y => { if (JSON.stringify(x) !== JSON.stringify(y)) throw Error(m); } } }),
  };
  new Function('pm', script)(pm);
  return tests;
}
const conLectura = xs => xs.map(id => ({ id_sensor: id, ultimo_valor: 25 }));

test('criterio de la matriz: 50 sensores, < 1000 ms, primera carga decisoria y repeticiones INFO', () => {
  assert.deepEqual(CASOS, ['TC-M03-203']);
  assert.equal(SENSORES, 50); assert.equal(UMBRAL_MS, 1000); assert.ok(MUESTRAS >= 2);
  assert.deepEqual(REQUERIDAS, { 'TC-M03-203': ['PERF-203-01@U50'] });
  assert.equal(new Set(nombresUnidad('QA G103 X')).size, 50);
  assert.equal(serialQa({}, 'G103', '20261017000000', 'U50'), 'QAAUTO-G103-20261017000000-U50');
});
test('colección: la carga inicial decide; 999 ms aprueba y 1000 ms no (estrictamente inferior)', () => {
  const a = correr({ iteracion: 0, ms: 999, sensores: conLectura(ids) });
  assert.ok(a.every(t => t.ok) && a.some(t => /\[ASSERT\]\[PERF-203-01\].*999 ms/.test(t.n)));
  const b = correr({ iteracion: 0, ms: 1000, sensores: conLectura(ids) });
  assert.ok(b.some(t => /PERF-203-01/.test(t.n) && !t.ok));
});
test('colección: la precondición exige exactamente los 50 sensores de la unidad con lectura', () => {
  assert.ok(correr({ iteracion: 0, ms: 100, sensores: conLectura(ids.slice(1)) }).some(t => /\[PRE\]/.test(t.n) && !t.ok));
  assert.ok(correr({ iteracion: 0, ms: 100, sensores: [...conLectura(ids.slice(1)), { id_sensor: 1, ultimo_valor: null }] }).some(t => /\[PRE\]/.test(t.n) && !t.ok));
  assert.ok(correr({ iteracion: 0, ms: 100, code: 500, sensores: [] }).some(t => /\[PRE\]/.test(t.n) && !t.ok));
});
test('colección: las repeticiones solo registran INFO, aunque superen el umbral', () => {
  const t = correr({ iteracion: 3, ms: 5000, sensores: conLectura(ids) });
  assert.equal(t.length, 1); assert.match(t[0].n, /\[INFO\].*repetición 3.*5000 ms/); assert.ok(t[0].ok);
});
test('resumen de la medición: primera muestra y estadísticos', () => {
  const r = resumenMedicion([{ iteracion: 1, ms: 300, http: 200 }, { iteracion: 0, ms: 800, http: 200, bytes: 1234 }, { iteracion: 2, ms: 200, http: 200 }]);
  assert.equal(r.carga_inicial_ms, 800); assert.equal(r.bytes_respuesta, 1234);
  assert.deepEqual(r.estadisticos, { n: 3, min: 200, mediana: 300, p95: 800, max: 800 });
  assert.equal(estadisticos([]), null);
});
test('veredicto: PRE fallido bloquea; tiempo superado con vista correcta rechaza; sin medición bloquea', () => {
  const base = { casos: CASOS, requeridas: REQUERIDAS, estado: 'CONCLUIDA', rollback: true };
  const asercion = ok => ({ caso: 'TC-M03-203', tipo: 'ASSERT', id: 'PERF-203-01', variante: 'U50', ok, evidencia: true });
  assert.equal(veredictoCasos({ ...base, aserciones: [asercion(true)] }).grupo, 'APROBADO');
  assert.equal(veredictoCasos({ ...base, aserciones: [asercion(false)] }).grupo, 'RECHAZADO');
  assert.equal(veredictoCasos({ ...base, aserciones: [{ caso: 'TC-M03-203', tipo: 'PRE', variante: 'U50', ok: false }, asercion(false)] }).grupo, 'BLOQUEADO');
  assert.equal(veredictoCasos({ ...base, aserciones: [] }).grupo, 'BLOQUEADO');
  assert.equal(veredictoCasos({ ...base, rollback: false, aserciones: [asercion(true)] }).grupo, 'BLOQUEADO');
});
test('barreras: ejecutor y colección no permiten ejecutar sin autorización', () => {
  assert.equal(autorizar({ QA_AUTORIZADO: 'NO' }, { ambiente: 'TEST', autorizacion: 'DEV-REF-123', efectos: ['notificacion-login'] }).ok, false);
  const pre = col.event.find(e => e.listen === 'prerequest').script.exec.join('\n');
  const pm = v => ({ environment: { get: k => v[k] }, execution: { skipRequest() {} } });
  assert.throws(() => new Function('pm', pre)(pm({ autorizado_run: 'NO', run_id: 'R', base_url: 'https://x' })), /BLOQUEO_G103/);
  assert.throws(() => new Function('pm', pre)(pm({ autorizado_run: 'SI', run_id: 'R', base_url: 'http://127.0.0.1:9' })), /BLOQUEO_G103/);
  assert.equal(leerConteo({ status: 403, data: null }), null);
});
