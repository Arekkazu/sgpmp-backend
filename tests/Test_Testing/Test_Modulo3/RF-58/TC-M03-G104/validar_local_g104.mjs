// Pruebas unitarias locales de G104: preparación de estados, descubrimiento de GRIS y veredicto,
// con datos sintéticos (sin red).
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { CASOS, VARIANTES, CONSTRUIBLES, SEVERIDAD, REQUERIDAS, revisarEstado, grisApto } from './ejecutar_tc_m03_g104.mjs';
import { autorizar, cuerpoAlerta, veredictoCasos } from './monitoreo_lib.mjs';

const spec = fs.readFileSync(new URL('./tc_m03_g104.cy.js', import.meta.url), 'utf8');
const sensor = (semaforo, extra = {}) => ({ estado_semaforo: semaforo, ultimo_valor: '25.0000', ultima_unidad: '°C', id_alerta: null, id_infraestructura: 7, nombre_sensor: 'S', ...extra });

test('cuatro estados; GRIS depende de RF-60 y no se construye', () => {
  assert.deepEqual(VARIANTES, ['VERDE', 'AMARILLO', 'ROJO', 'GRIS']);
  assert.deepEqual(CONSTRUIBLES, ['VERDE', 'AMARILLO', 'ROJO']);
  assert.deepEqual(SEVERIDAD, { AMARILLO: 'MODERADO', ROJO: 'CRITICO' });
  for (const s of Object.values(SEVERIDAD)) assert.equal(cuerpoAlerta({ idDispositivo: 1, idSensor: 2, serial: 'x', idTelemetria: 3, severidad: s }).severidad_edge, s);
});
test('precondición por variante: semáforo esperado, valor, unidad y alerta cuando corresponde', () => {
  assert.deepEqual(revisarEstado('VERDE', sensor('VERDE')), []);
  assert.deepEqual(revisarEstado('ROJO', sensor('ROJO', { id_alerta: 9 })), []);
  assert.match(revisarEstado('AMARILLO', sensor('VERDE', { id_alerta: 9 })).join(), /semáforo VERDE/);
  assert.match(revisarEstado('ROJO', sensor('ROJO')).join(), /sin alerta activa/);
  assert.match(revisarEstado('VERDE', sensor('VERDE', { ultimo_valor: null })).join(), /sin valor/);
  assert.deepEqual(revisarEstado('VERDE', undefined), ['el sensor no aparece en el dashboard de su unidad']);
});
test('descubrimiento GRIS: solo sensores en GRIS con valor, unidad y unidad productiva', () => {
  assert.equal(grisApto(sensor('GRIS')), true);
  assert.equal(grisApto(sensor('VERDE')), false);
  assert.equal(grisApto(sensor('GRIS', { ultimo_valor: null })), false);
  assert.equal(grisApto(sensor('GRIS', { id_infraestructura: null })), false);
  assert.equal(grisApto(undefined), false);
});
test('requeridas: página y sensor en los cuatro estados, alerta en AMARILLO y ROJO, detalle una vez', () => {
  const r = REQUERIDAS['TC-M03-204'];
  for (const x of VARIANTES) { assert.ok(r.includes(`UI-204-01@${x}`)); assert.ok(r.includes(`UI-204-02@${x}`)); }
  assert.deepEqual(r.filter(k => k.startsWith('UI-204-03')), ['UI-204-03@AMARILLO', 'UI-204-03@ROJO']);
  assert.deepEqual(r.filter(k => k.startsWith('UI-204-04')), ['UI-204-04@VERDE']);
});
test('veredicto: GRIS ausente bloquea; fallo a 360 px rechaza; fallo en 768/1366 (INFO) no decide; PRE de la variante invalida', () => {
  const base = { casos: CASOS, requeridas: REQUERIDAS, estado: 'CONCLUIDA', rollback: true };
  const todas = REQUERIDAS['TC-M03-204'].map(k => ({ caso: 'TC-M03-204', tipo: 'ASSERT', id: k.split('@')[0], variante: k.split('@')[1], ok: true, evidencia: true }));
  assert.equal(veredictoCasos({ ...base, aserciones: todas }).grupo, 'APROBADO');
  assert.equal(veredictoCasos({ ...base, aserciones: [...todas.filter(a => a.variante !== 'GRIS'), { caso: 'TC-M03-204', tipo: 'PRE', variante: 'GRIS', ok: false }] }).grupo, 'BLOQUEADO');
  const falla = todas.map(a => a.id === 'UI-204-03' && a.variante === 'ROJO' ? { ...a, ok: false } : a);
  assert.equal(veredictoCasos({ ...base, aserciones: falla }).grupo, 'RECHAZADO');
  assert.equal(veredictoCasos({ ...base, aserciones: [...falla, { caso: 'TC-M03-204', tipo: 'PRE', variante: 'ROJO', ok: false }] }).grupo, 'BLOQUEADO');
  assert.equal(veredictoCasos({ ...base, aserciones: [...todas, { caso: 'TC-M03-204', tipo: 'INFO', variante: 'VERDE', ok: false, evidencia: true }] }).grupo, 'APROBADO');
  // Fallo real a 360 px en VERDE aunque GRIS no esté disponible: se conserva el rechazo.
  const sinGris = todas.filter(a => a.variante !== 'GRIS').map(a => a.id === 'UI-204-02' && a.variante === 'VERDE' ? { ...a, ok: false } : a);
  assert.equal(veredictoCasos({ ...base, aserciones: [...sinGris, { caso: 'TC-M03-204', tipo: 'PRE', variante: 'GRIS', ok: false }] }).grupo, 'RECHAZADO');
});
test('spec: 360 px decisorio, superiores INFO, barrera propia y sin simulaciones', () => {
  assert.match(spec, /\{ ancho: 360, alto: 740, tipo: 'ASSERT' \}/);
  assert.match(spec, /\{ ancho: 768, alto: 1024, tipo: 'INFO' \}/);
  assert.match(spec, /BLOQUEO_G104/);
  assert.match(spec, /elementFromPoint/);
  assert.match(spec, /scrollWidth/);
  assert.doesNotMatch(spec, new RegExp(['req\\.reply', 'cy\\.stub', 'cy\\.clock'].join('|')));
});
test('barrera del ejecutor: exige autorización, TEST y frontend HTTPS de TEST', () => {
  const v = { QA_AUTORIZADO: 'SI', QA_SETUP_EMAIL: 'a@x.test', QA_ENG_EMAIL: 'e@x.test', QA_COMMON_PASSWORD: 'x', QA_SANDBOX_SECRET: 'y', SIGAB_API_TEST_BASE: 'https://www.api.inmero.co/api-sgpmp-test', SIGAB_FRONT_TEST_URL: 'https://api.inmero.co/sigab-test' };
  const a = { ambiente: 'TEST', autorizacion: 'DEV-REF-123', efectos: ['notificacion-login'] };
  assert.equal(autorizar(v, a, { frontend: true }).ok, true);
  assert.equal(autorizar({ ...v, QA_AUTORIZADO: 'NO' }, a, { frontend: true }).ok, false);
  assert.equal(autorizar({ ...v, SIGAB_FRONT_TEST_URL: '' }, a, { frontend: true }).ok, false);
  assert.equal(autorizar({ ...v, SIGAB_FRONT_TEST_URL: 'https://front-dev.example' }, a, { frontend: true }).ok, false);
});
test('barrera propia de Cypress: el before del spec se detiene sin autorización ni API HTTPS, antes de usar cy', () => {
  const src = fs.readFileSync(new URL('./tc_m03_g104.cy.js', import.meta.url), 'utf8');
  for (const valores of [{}, { AUTORIZADO_RUN: 'NO', RUN_ID: 'R', API_BASE: 'https://api.test.example' }, { AUTORIZADO_RUN: 'SI', RUN_ID: 'R', API_BASE: 'http://127.0.0.1:9' }]) {
    const ganchos = [];
    const cy = new Proxy({}, { get: () => () => { throw Error('cy usado antes de la barrera'); } });
    const g = { Cypress: { env: k => valores[k] }, describe: (n, f) => f(), before: f => ganchos.push(f), it: () => {}, cy, expect: () => {} };
    new Function(...Object.keys(g), src)(...Object.values(g));
    assert.equal(ganchos.length, 1);
    assert.throws(() => ganchos[0](), /BLOQUEO_G104/);
  }
});

// ---- Corrección de la ejecución de Cypress ------------------------------------------------------
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { opcionesCypress, correrCypress, aislamientoVerificacion, urls } from './monitoreo_lib.mjs';
const AQUI = path.dirname(fileURLToPath(import.meta.url));
const RAIZ = path.resolve(AQUI, '../../../../..');
const SPEC_G = fs.readdirSync(AQUI).find(f => f.endsWith('.cy.js'));
const VERIF = path.join(AQUI, 'cypress.verificacion.config.cjs');
const PROXY = { HTTP_PROXY: 'http://127.0.0.1:9', HTTPS_PROXY: 'http://127.0.0.1:9' };

test('Cypress: anulaciones dentro de e2e; baseUrl es el frontend y el API va aparte', () => {
  const o = opcionesCypress({ root: RAIZ, spec: path.join(AQUI, SPEC_G), front: 'https://front.test.example', out: AQUI, env: { API_BASE: 'https://api.test.example' } });
  assert.equal(o.config.baseUrl, undefined);
  assert.equal(o.config.e2e.baseUrl, 'https://front.test.example');
  assert.equal(o.config.e2e.reporter, 'spec'); assert.equal(o.reporter, 'spec');
  assert.equal(path.resolve(RAIZ, o.config.e2e.specPattern), path.join(AQUI, SPEC_G));
  assert.equal(path.resolve(RAIZ, o.configFile), VERIF, 'la ejecución autorizada usa la configuración aislada del grupo');
});
test('Cypress: no se lanza si el frontend falta, no es HTTPS o coincide con el API', async () => {
  let lanzado = false;
  const falso = { run: async () => { lanzado = true; return {}; } };
  for (const front of [null, 'http://front.test.example', 'https://api.test.example']) {
    await assert.rejects(correrCypress(falso, { root: RAIZ, spec: path.join(AQUI, SPEC_G), front, out: AQUI, env: { API_BASE: 'https://api.test.example' } }), /frontend HTTPS/);
  }
  assert.equal(lanzado, false);
});
test('Verificación local: solo loopback, salida bloqueada y nunca el cypress.config.cjs raíz', () => {
  const ok = opcionesCypress({ root: RAIZ, spec: path.join(AQUI, SPEC_G), front: null, out: null, env: {}, configFile: path.relative(RAIZ, VERIF).split(path.sep).join('/') });
  assert.deepEqual(aislamientoVerificacion({ root: RAIZ, configVerificacion: VERIF, opciones: ok, entorno: PROXY }), []);
  assert.ok(urls(require_(VERIF)).every(u => u.startsWith('http://127.0.0.1')));
  const motivos = (o, e = PROXY) => aislamientoVerificacion({ root: RAIZ, configVerificacion: VERIF, opciones: o, entorno: e }).join(' | ');
  assert.match(motivos({ ...ok, configFile: undefined }), /configuración de verificación/);
  assert.match(motivos({ ...ok, config: { e2e: { ...ok.config.e2e, baseUrl: 'https://api.inmero.co' } } }), /no loopback|baseUrl/);
  assert.match(motivos(ok, {}), /PROXY/);
  assert.match(motivos(ok, { ...PROXY, CYPRESS_BASE_URL: 'https://api.inmero.co' }), /CYPRESS_BASE_URL/);
  assert.match(motivos(ok, { ...PROXY, ELECTRON_RUN_AS_NODE: '1' }), /ELECTRON_RUN_AS_NODE/);
});
import { createRequire } from 'node:module';
const require_ = createRequire(import.meta.url);
