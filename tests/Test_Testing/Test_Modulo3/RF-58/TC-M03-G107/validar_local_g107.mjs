// Pruebas unitarias locales de G107: funciones puras y scripts de la colección con respuestas
// sintéticas (sin red). Los datos sintéticos solo validan la lógica de las aserciones.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { CASOS, REQUERIDAS, tieneLectura, valores, registroCoincide, evaluarBitacora } from './ejecutar_tc_m03_g107.mjs';
import { veredictoCasos } from './monitoreo_lib.mjs';

const col = JSON.parse(fs.readFileSync(new URL('./TC-M03-G107.postman_collection.json', import.meta.url), 'utf8'));
const env = { run_id: 'R', id_a: '10', id_b: '20', finca_a: '1', finca_b: '2', sensor_a: '100', sensor_b: '200', alerta_b: '900', nombres_a: JSON.stringify(['Granja Alfa', 'Unidad A', 'Sensor A']), nombres_b: JSON.stringify(['Granja Beta', 'Unidad B', 'Sensor B']), token_sin_permiso: 'x' };

function correr(nombre, { code, body, variables = env }) {
  const it = col.item.find(i => i.name === nombre);
  const tests = []; let saltada = false;
  const pm = {
    response: { code, text: () => body === undefined ? '' : JSON.stringify(body), json: () => { if (body === undefined) throw Error('sin JSON'); return body; } },
    environment: { get: k => variables[k] },
    execution: { skipRequest: () => { saltada = true; } },
    test: (n, f) => { try { f(); tests.push({ n, ok: true }); } catch (e) { tests.push({ n, ok: false }); } },
    expect: (x, m) => ({ to: { eql: y => { if (JSON.stringify(x) !== JSON.stringify(y)) throw Error(m); } } }),
  };
  const pre = it.event.find(e => e.listen === 'prerequest');
  if (pre) new Function('pm', pre.script.exec.join('\n'))(pm);
  if (saltada) return { saltada, tests };
  new Function('pm', it.event.find(e => e.listen === 'test').script.exec.join('\n'))(pm);
  return { saltada, tests };
}
const ok = (tests, id) => tests.some(t => t.n.includes(id)) && tests.filter(t => t.n.includes(id)).every(t => t.ok);
const Q207 = '[TC-M03-207][V:QUERY] granja ajena, ruta con id_infraestructura', R207 = '[TC-M03-207][V:RUTA] granja ajena, ruta /dashboard/{id}';
const Q208 = '[TC-M03-208][V:QUERY] rol sin permiso, ruta con id_infraestructura', R208 = '[TC-M03-208][V:RUTA] rol sin permiso, ruta /dashboard/{id}';
const denegado = { error_code: 'ACCESO_DENEGADO', message: 'Acceso denegado.', fields: [] };

test('207: denegación sin exposición aprueba; 200 vacío no es denegación pero no expone', () => {
  for (const n of [Q207, R207]) {
    const t = correr(n, { code: 403, body: denegado }).tests;
    assert.ok(ok(t, 'API-207-01') && ok(t, 'API-207-02'));
  }
  const vacio = correr(Q207, { code: 200, body: { total: 0, sensores: [], resumen_unidades: [] } }).tests;
  assert.ok(ok(vacio, 'API-207-01')); assert.ok(!ok(vacio, 'API-207-02'));
});
test('207: detecta exposición por nombre, por identificador anidado o por la alerta de la granja B', () => {
  assert.ok(!ok(correr(R207, { code: 403, body: { message: 'La unidad Unidad B no le pertenece' } }).tests, 'API-207-01'));
  assert.ok(!ok(correr(Q207, { code: 200, body: { total: 1, sensores: [{ id_sensor: 7, id_infraestructura: 20 }], resumen_unidades: [] } }).tests, 'API-207-01'));
  assert.ok(!ok(correr(Q207, { code: 200, body: { total: 1, sensores: [], resumen_unidades: [{ detalle: { id_finca: 2 } }] } }).tests, 'API-207-01'));
  assert.ok(!ok(correr(Q207, { code: 200, body: { sensores: [{ id_sensor: 1, id_alerta: 900 }] } }).tests, 'API-207-01'));
  // Un número coincidente en otra clave (p. ej. total) no es exposición.
  assert.ok(ok(correr(Q207, { code: 403, body: { ...denegado, total: 20 } }).tests, 'API-207-01'));
});
test('208: 403 con mensaje y sin datos aprueba; 200 con lecturas o datos de granjas falla', () => {
  for (const n of [Q208, R208]) {
    const t = correr(n, { code: 403, body: denegado }).tests;
    assert.ok(ok(t, 'API-208-01') && ok(t, 'API-208-02'));
  }
  const t = correr(R208, { code: 200, body: { total: 1, sensores: [{ id_sensor: 100, id_infraestructura: 10 }] } }).tests;
  assert.ok(!ok(t, 'API-208-01') && !ok(t, 'API-208-02'));
  assert.ok(!ok(correr(Q208, { code: 403, body: { message: 'Sin permiso sobre Granja Alfa' } }).tests, 'API-208-02'));
  assert.ok(!ok(correr(Q208, { code: 403, body: {} }).tests, 'API-208-02'), 'sin mensaje');
});
test('208: sin cuenta con rol sin permiso la petición no se envía', () => {
  assert.equal(correr(Q208, { code: 403, body: denegado, variables: { ...env, token_sin_permiso: '' } }).saltada, true);
});
test('PRE de 207: el Ingeniero debe ver su propia unidad', () => {
  const n = '[TC-M03-207] el Ingeniero consulta su propia unidad (granja A)';
  assert.ok(correr(n, { code: 200, body: { sensores: [{ id_sensor: 100 }] } }).tests.every(t => t.ok));
  assert.ok(correr(n, { code: 200, body: { sensores: [] } }).tests.some(t => !t.ok));
});
test('rol sin permiso: se decide por los permisos reales del rol', () => {
  assert.equal(tieneLectura([{ id_recurso: 33, id_accion: 2, es_activo: true }]), true);
  assert.equal(tieneLectura([{ id_recurso: 33, id_accion: 2, es_activo: false }, { id_recurso: 34, id_accion: 2, es_activo: true }]), false);
  assert.equal(tieneLectura(null), null);
});
test('bitácora: un registro completo por intento (usuario, unidad, fecha y motivo) en RF-10 o IoT', () => {
  const i = { tipo: 'GRANJA', id_usuario: 5, id_unidad: 20 };
  const rf10 = { id_usuario: 5, fecha_evento: '2026-10-17T00:00:00Z', resultado: 'fallido', detalle: { id_infraestructura: 20, motivo: 'GRANJA_NO_AUTORIZADA' } };
  const iot = { id_usuario: 5, fecha_hora: '2026-10-17T00:00:00Z', entidad_afectada_id: '20', descripcion: 'Acceso denegado al monitoreo' };
  assert.equal(registroCoincide(rf10, i).completo, true);
  assert.equal(registroCoincide(iot, i).completo, true);
  assert.equal(registroCoincide({ ...rf10, detalle: { id_infraestructura: 20 } }, i).completo, false, 'sin motivo');
  assert.equal(registroCoincide({ ...rf10, id_usuario: 6 }, i).coincide, false);
  assert.deepEqual(valores({ a: { id_infraestructura: 20, b: [{ unidad: 3 }] } }, /infraestructura|unidad/), [20, 3]);
  const r = evaluarBitacora([rf10], [i, { ...i }]);
  assert.deepEqual(r.map(x => x.registrado), [true, false], 'cada intento necesita su propio registro');
  assert.match(evaluarBitacora([{ ...rf10, detalle: { id_infraestructura: 20 } }], [i])[0].incompleto, /sin fecha o sin motivo/);
});
test('veredicto: 209 no se aprueba sin el escenario «unidad no asignada»; 207 y 208 se conservan', () => {
  const todas = Object.entries(REQUERIDAS).flatMap(([caso, ks]) => ks.map(k => ({ caso, tipo: 'ASSERT', id: k.split('@')[0], variante: k.split('@')[1], ok: true, evidencia: true })));
  const base = { casos: CASOS, requeridas: REQUERIDAS, estado: 'CONCLUIDA', rollback: true };
  assert.equal(veredictoCasos({ ...base, aserciones: todas }).grupo, 'APROBADO');
  const sinUnidad = [...todas.filter(a => a.variante !== 'UNIDAD'), { caso: 'TC-M03-209', tipo: 'PRE', variante: 'UNIDAD', ok: false }];
  assert.deepEqual(veredictoCasos({ ...base, aserciones: sinUnidad }).casos, { 'TC-M03-207': 'APROBADO', 'TC-M03-208': 'APROBADO', 'TC-M03-209': 'BLOQUEADO' });
  // Rechazo real en granja ajena aunque falte el escenario de unidad.
  const falla = sinUnidad.map(a => a.id === 'API-209-02' ? { ...a, ok: false } : a);
  assert.equal(veredictoCasos({ ...base, aserciones: falla }).casos['TC-M03-209'], 'RECHAZADO');
  // Sin testigo positivo de la bitácora (PRE general) no se rechaza.
  assert.equal(veredictoCasos({ ...base, aserciones: [...falla, { caso: 'TC-M03-209', tipo: 'PRE', variante: null, ok: false }] }).casos['TC-M03-209'], 'BLOQUEADO');
});
test('barrera de la colección: sin autorización vigente no se envía ninguna petición', () => {
  const pre = col.event.find(e => e.listen === 'prerequest').script.exec.join('\n');
  const pm = v => ({ environment: { get: k => v[k] }, execution: { skipRequest() {} } });
  assert.throws(() => new Function('pm', pre)(pm({ autorizado_run: 'NO', run_id: 'R', base_url: 'https://x' })), /BLOQUEO_G107/);
  assert.throws(() => new Function('pm', pre)(pm({ autorizado_run: 'SI', run_id: 'R', base_url: 'http://127.0.0.1:9' })), /BLOQUEO_G107/);
});
