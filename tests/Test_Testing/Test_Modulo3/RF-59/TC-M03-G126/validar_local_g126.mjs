// Pruebas unitarias locales de G126 con snapshots y respuestas sintéticas (sin red). Los datos
// sintéticos solo validan que el comparador y la colección detectan alteraciones; no son evidencia funcional.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { CASOS, REQUERIDAS, TABLAS, consultaSnapshot, canonico, snapshotTabla, compararTabla } from './ejecutar_tc_m03_g126.mjs';
import { veredictoCasos } from './monitoreo_lib.mjs';

const col = JSON.parse(fs.readFileSync(new URL('./TC-M03-G126.postman_collection.json', import.meta.url), 'utf8'));
const lectura = (id, extra = {}) => ({ id_telemetria: id, id_sensor: 7, valor_crudo: 25.1, valor_ajustado: 25.1, timestamp_captura: '2026-10-17T05:00:00+00:00', estado_calidad: 'LECTURA_VALIDA', metadatos: { a: 1, b: [1, 2] }, ...extra });
const respuesta = rows => ({ status: 200, data: { data: rows.map(r => ({ fila: JSON.stringify(r) })) } });
const snap = rows => snapshotTabla(respuesta(rows), 'id_telemetria');
const base = [lectura(1), lectura(2), lectura(3)];

test('snapshot: SELECT de solo lectura, ordenado por clave primaria y con ids validados', () => {
  for (const t of Object.keys(TABLAS)) {
    const q = consultaSnapshot(t, [10, 11]);
    assert.match(q, /^SELECT row_to_json\(x\)::text AS fila FROM modulo3\.\w+ x WHERE .* ORDER BY x\.\w+$/);
    assert.doesNotMatch(q, /\b(UPDATE|INSERT|DELETE|DROP|ALTER)\b/i);
  }
  assert.throws(() => consultaSnapshot('telemetrias', [1, '2) OR (1=1']));
  assert.throws(() => consultaSnapshot('otra_tabla', [1]));
  assert.throws(() => consultaSnapshot('telemetrias', []));
});
test('forma canónica: el orden de filas y de claves no altera el hash (sin falsos positivos)', () => {
  const reordenado = [lectura(3), lectura(1), { ...lectura(2) }].map(r => Object.fromEntries(Object.entries(r).reverse()));
  assert.equal(snap(base).hash, snap(reordenado).hash);
  assert.equal(canonico({ b: 1, a: { d: 2, c: 3 } }), canonico({ a: { c: 3, d: 2 }, b: 1 }));
  assert.equal(compararTabla(snap(base), snap(reordenado)).identicas, true);
});
test('detecta lecturas creadas, eliminadas y modificadas (valor, atributo, estado o metadato)', () => {
  const a = snap(base);
  assert.deepEqual(compararTabla(a, snap([...base, lectura(4)])).creadas, ['4']);
  assert.deepEqual(compararTabla(a, snap(base.slice(0, 2))).eliminadas, ['3']);
  for (const [cambio, campo] of [[{ valor_ajustado: 25.2 }, 'valor_ajustado'], [{ estado_calidad: 'FUERA_DE_RANGO' }, 'estado_calidad'], [{ timestamp_captura: '2026-10-17T05:00:01+00:00' }, 'timestamp_captura'], [{ metadatos: { a: 1, b: [2, 1] } }, 'metadatos'], [{ apto_para_ia: true }, 'apto_para_ia']]) {
    const c = compararTabla(a, snap([base[0], lectura(2, cambio), base[2]]));
    assert.equal(c.identicas, false);
    assert.deepEqual(c.modificadas, [{ id: '2', campos: [campo] }]);
  }
  // Mismo número de filas pero contenido distinto: no basta contar.
  const mismoConteo = compararTabla(a, snap([base[0], base[1], lectura(9)]));
  assert.equal(mismoConteo.identicas, false); assert.deepEqual([mismoConteo.creadas, mismoConteo.eliminadas], [['9'], ['3']]);
});
test('una consulta fallida o ilegible es no verificable (null), nunca un snapshot vacío', () => {
  assert.equal(snapshotTabla({ status: 400, data: { detail: 'x' } }, 'id_telemetria'), null);
  assert.equal(snapshotTabla({ status: 200, data: { data: [{ fila: '{no json' }] } }, 'id_telemetria'), null);
  assert.equal(snapshotTabla(respuesta([lectura(1), lectura(1)]), 'id_telemetria'), null, 'clave duplicada');
  assert.equal(snapshotTabla(respuesta([]), 'id_telemetria').n, 0);
});
test('veredicto: snapshot alterado rechaza; precondición fallida bloquea; todo idéntico aprueba', () => {
  const ok = id => ({ caso: 'TC-M03-255', tipo: 'ASSERT', id, variante: null, ok: true, evidencia: true });
  const todas = REQUERIDAS['TC-M03-255'].map(ok);
  const b = { casos: CASOS, requeridas: REQUERIDAS, estado: 'CONCLUIDA', rollback: true };
  assert.equal(veredictoCasos({ ...b, aserciones: todas }).grupo, 'APROBADO');
  const mod = todas.map(a => a.id === 'API-255-03' ? { ...a, ok: false } : a);
  assert.equal(veredictoCasos({ ...b, aserciones: mod }).grupo, 'RECHAZADO');
  assert.equal(veredictoCasos({ ...b, aserciones: [...mod, { caso: 'TC-M03-255', tipo: 'PRE', variante: null, ok: false }] }).grupo, 'BLOQUEADO');
  assert.equal(veredictoCasos({ ...b, aserciones: todas.slice(0, 3) }).grupo, 'BLOQUEADO', 'sin comparación de asociadas');
});
function correr(nombre, { code = 200, body, env }) {
  const it = col.item.find(i => i.name === nombre);
  const tests = []; let siguiente = null;
  const pm = {
    response: { code, json: () => body },
    environment: { get: k => env[k], set: (k, v) => { env[k] = v; } },
    info: { requestName: nombre },
    execution: { setNextRequest: n => { siguiente = n; } },
    test: (n, f) => { try { f(); tests.push({ n, ok: true }); } catch { tests.push({ n, ok: false }); } },
    expect: (x, m) => ({ to: { eql: y => { if (JSON.stringify(x) !== JSON.stringify(y)) throw Error(m); } } }),
  };
  new Function('pm', 'postman', it.event[0].script.exec.join('\n'))(pm, {});
  return { tests, siguiente };
}
test('colección: recorre las páginas del historial y exige al menos dos', () => {
  const nombre = '[TC-M03-255] historial por unidad productiva, recorrido de páginas';
  const env = { pagina: '1', ids_sensores: '[7]' }; let tests = [];
  for (let i = 0; i < 6; i++) { const r = correr(nombre, { body: { total: 18, paginas_totales: 4, items: [] }, env }); tests = tests.concat(r.tests); if (!r.siguiente) break; }
  assert.equal(env.pagina, '4');
  assert.ok(tests.some(t => /varias páginas/.test(t.n) && t.ok));
  const una = correr(nombre, { body: { total: 3, paginas_totales: 1, items: [] }, env: { pagina: '1', ids_sensores: '[7]' } }).tests;
  assert.ok(una.some(t => /varias páginas/.test(t.n) && !t.ok), 'una sola página no cumple la precondición');
  assert.ok(correr('[TC-M03-255] historial por variable', { code: 500, body: null, env: { ids_sensores: '[]' } }).tests.some(t => /\[PRE\]/.test(t.n) && !t.ok));
});
test('barrera de la colección: sin autorización vigente no se envía ninguna petición', () => {
  const pre = col.event.find(e => e.listen === 'prerequest').script.exec.join('\n');
  const pm = v => ({ environment: { get: k => v[k] }, execution: { skipRequest() {} } });
  assert.throws(() => new Function('pm', pre)(pm({ autorizado_run: 'NO', run_id: 'R', base_url: 'https://x' })), /BLOQUEO_G126/);
  assert.throws(() => new Function('pm', pre)(pm({ autorizado_run: 'SI', run_id: 'R', base_url: 'http://127.0.0.1:9' })), /BLOQUEO_G126/);
});
