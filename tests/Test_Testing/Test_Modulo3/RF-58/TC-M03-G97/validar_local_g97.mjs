import test from 'node:test';
import assert from 'node:assert/strict';
import { autorizar, ASERCIONES, CASOS, CASOS_POR_ROL, leerEnv, veredictoCasos, planAsignacion, conservaExactamente, casoDeId, casoDeTexto, cuerpoDispositivo, serialQa, leerConteo, filas, consultaTestigoDispositivo } from './ejecutar_tc_m03_g97.mjs';

test('parser de entorno compartido', () => {
  assert.deepEqual(leerEnv('QA_AUTORIZADO=NO\nQA_ENG_EMAIL="qa@example.test"'), { QA_AUTORIZADO: 'NO', QA_ENG_EMAIL: 'qa@example.test' });
});
test('barrera requiere TEST, cuenta de preparación y tres roles, referencia y aceptación', () => {
  const v = { QA_AUTORIZADO: 'SI', QA_SETUP_EMAIL: 's', QA_PROD_EMAIL: 'p', QA_ENG_EMAIL: 'e', QA_VETERINARIO_EMAIL: 'v', QA_COMMON_PASSWORD: 'x', QA_SANDBOX_SECRET: 'y', SIGAB_API_TEST_BASE: 'https://www.api.inmero.co/api-sgpmp-test', SIGAB_FRONT_TEST_URL: 'https://api.inmero.co/sigab-test' };
  const a = { ambiente: 'TEST', autorizacion: 'DEV-REF-123', efectos: ['notificacion-login'] };
  assert.equal(autorizar(v, a).ok, true);
  assert.equal(autorizar({ ...v, QA_AUTORIZADO: 'NO' }, a).ok, false);
  assert.equal(autorizar({ ...v, QA_VETERINARIO_EMAIL: '' }, a).ok, false);
  assert.equal(autorizar({ ...v, QA_SETUP_EMAIL: '' }, a).ok, false);
  assert.equal(autorizar(v, { ...a, ambiente: 'DEV' }).ok, false);
  assert.equal(autorizar(v, { ...a, efectos: [] }).ok, false);
});
test('catálogo exacto de cuatro casos y aserciones asignadas a su caso', () => {
  assert.deepEqual(CASOS, ['TC-M03-188', 'TC-M03-189', 'TC-M03-190', 'TC-M03-210']);
  assert.ok(ASERCIONES.every(id => CASOS.includes(casoDeId(id))));
  assert.equal(casoDeTexto('[TC-M03-190][ASSERT][API-190-03] x'), 'TC-M03-190');
  assert.deepEqual(CASOS_POR_ROL.VETERINARIO, ['TC-M03-190']);
});
test('asignación aditiva: solo con visibles = asignadas, y debe conservar exactamente las previas', () => {
  assert.deepEqual(planAsignacion([3, 1], [1, 3], 9), { aplicar: true, ids: [1, 3, 9] });
  assert.equal(planAsignacion([1, 3], [1], 9).aplicar, false);
  assert.equal(planAsignacion([1, 9], [1, 9], 9).ya, true);
  assert.equal(conservaExactamente([1, 3], [3, 1, 9], 9), true);
  assert.equal(conservaExactamente([1, 3], [1, 9], 9), false);
  assert.equal(conservaExactamente([1, 3], [1, 3, 9, 5], 9), false);
});
test('identidad del dispositivo concentrada en un punto (DEV-06) y serial QA automático', () => {
  assert.deepEqual(cuerpoDispositivo({ idDispositivo: 1, idSensor: 2, serial: 'S' }), { device_id: 1, sensor_id: 2, access_key: 'S' });
  assert.equal(serialQa({}, '20261017000000'), 'QAAUTO-G97-20261017000000');
});
test('testigo sin RLS y lectura de {data:[...]} sin convertir fallos en 0', () => {
  assert.match(consultaTestigoDispositivo('QAAUTO-G97-1'), /FROM auditoria\.logs_dml/);
  assert.equal(leerConteo({ status: 200, data: { data: [{ n: 1 }] } }), 1);
  assert.equal(leerConteo({ status: 403, data: null }), null);
  assert.equal(filas({ status: 200, data: [{ n: 1 }] }), null);
});
const ok = (caso, id, tipo = 'ASSERT') => ({ caso, id, tipo, ok: true, evidencia: true });
const completas = ASERCIONES.map(id => ok(casoDeId(id), id));
const base = { estado: 'CONCLUIDA', rollback: true, aserciones: completas, bloqueos: {} };
test('veredicto por caso: APROBADO con todas las aserciones de cada caso', () => {
  const r = veredictoCasos(base);
  assert.ok(CASOS.every(c => r.casos[c] === 'APROBADO'));
  assert.equal(r.grupo, 'APROBADO');
});
test('veredicto: un ASSERT con evidencia rechaza solo su caso', () => {
  const r = veredictoCasos({ ...base, aserciones: completas.map(a => a.id === 'API-210-01' ? { ...a, ok: false } : a) });
  assert.equal(r.casos['TC-M03-210'], 'RECHAZADO');
  assert.equal(r.casos['TC-M03-188'], 'APROBADO');
  assert.equal(r.grupo, 'RECHAZADO');
});
test('veredicto: PRE, hooks, bloqueos, aserciones faltantes o rollback bloquean (no rechazan)', () => {
  assert.equal(veredictoCasos({ ...base, aserciones: [...completas, { caso: 'TC-M03-189', tipo: 'PRE', id: null, ok: false }] }).casos['TC-M03-189'], 'BLOQUEADO');
  assert.equal(veredictoCasos({ ...base, aserciones: completas.map(a => a.id === 'UI-190-01' ? { ...a, ok: false, tipo: 'PRE', evidencia: false } : a) }).casos['TC-M03-190'], 'BLOQUEADO');
  assert.equal(veredictoCasos({ ...base, bloqueos: { 'TC-M03-190': ['sin alcance'] } }).casos['TC-M03-190'], 'BLOQUEADO');
  assert.equal(veredictoCasos({ ...base, aserciones: completas.filter(a => a.id !== 'API-189-01') }).casos['TC-M03-189'], 'BLOQUEADO');
  assert.equal(veredictoCasos({ ...base, rollback: false }).grupo, 'BLOQUEADO');
  assert.equal(veredictoCasos({ ...base, aserciones: completas.map(a => a.id === 'API-188-01' ? { ...a, ok: false, evidencia: false } : a) }).casos['TC-M03-188'], 'BLOQUEADO');
});

// ---- Correcciones A.1 / A.2 -------------------------------------------------------------------
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { opcionesCypress, entornoCypress } from './ejecutar_tc_m03_g97.mjs';
const DIR = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(DIR, '../../../../..');
const SPEC = fs.readFileSync(path.join(DIR, 'tc_m03_g97.cy.js'), 'utf8');
const ETIQUETAS = new Function(`${SPEC.match(/const ETIQUETAS = \{[^\n]+\};/)[0]} return ETIQUETAS;`)();

test('Cypress: el proyecto es la raíz y specPattern resuelve exactamente al spec de G97', () => {
  const o = opcionesCypress({ front: 'https://front.test.example', out: DIR, env: { ROLE: 'PROD' } });
  assert.equal(o.project, ROOT);
  assert.equal(path.resolve(ROOT, o.config.e2e.specPattern), path.join(DIR, 'tc_m03_g97.cy.js'));
  assert.equal(o.config.e2e.baseUrl, 'https://front.test.example');
  assert.equal(o.config.e2e.reporter, 'spec');
  assert.equal(o.spec, path.join(DIR, 'tc_m03_g97.cy.js'));
  assert.equal(o.reporter, 'spec');
  assert.equal(o.config.e2e.screenshotOnRunFailure, false);
  // Las anulaciones deben ir en e2e: el bloque e2e del archivo raíz prevalece sobre las de nivel superior.
  assert.equal(o.config.baseUrl, undefined);
  assert.equal(opcionesCypress({ front: null, out: null, env: {} }).config.e2e.baseUrl, null);
});
test('Cypress: el proceso hijo no hereda ELECTRON_RUN_AS_NODE', () => {
  const previo = process.env.ELECTRON_RUN_AS_NODE;
  process.env.ELECTRON_RUN_AS_NODE = '1';
  entornoCypress();
  assert.equal(process.env.ELECTRON_RUN_AS_NODE, undefined);
  if (previo !== undefined) process.env.ELECTRON_RUN_AS_NODE = previo;
});
test('UI-188-01: cada estado admite su etiqueta real y su nombre, sin solaparse con otros estados', () => {
  assert.deepEqual(Object.keys(ETIQUETAS), ['VERDE', 'AMARILLO', 'ROJO', 'GRIS']);
  const todas = Object.values(ETIQUETAS).flat();
  assert.equal(new Set(todas).size, todas.length);
  for (const [k, v] of Object.entries(ETIQUETAS)) assert.ok(v.includes(k.toLowerCase()));
  assert.ok(!/cy\.contains\(\/\(VERDE/.test(SPEC), 'ya no basta una palabra en cualquier parte');
});
const PILL = path.resolve(ROOT, '../SGPMP-FRONT-END-PWA/src/telemetry/components/SemaforoPill.tsx');
test('UI-188-01: las etiquetas coinciden con el componente SemaforoPill del frontend', { skip: !fs.existsSync(PILL) && 'frontend no disponible localmente' }, () => {
  const meta = [...fs.readFileSync(PILL, 'utf8').matchAll(/(VERDE|AMARILLO|ROJO|GRIS): \{ label: '([^']+)'/g)];
  assert.equal(meta.length, 4);
  for (const [, estado, label] of meta) assert.ok(ETIQUETAS[estado].includes(label.toLowerCase()), `${estado} → ${label}`);
});

// ---- --verificar-spec aislado de la red -----------------------------------------------------------
import { aislamientoVerificacion, urls } from './ejecutar_tc_m03_g97.mjs';
import { createRequire as crearRequire97 } from 'node:module';
const VERIF97 = path.join(DIR, 'cypress.verificacion.config.cjs');
const PROXY97 = { HTTP_PROXY: 'http://127.0.0.1:9', HTTPS_PROXY: 'http://127.0.0.1:9' };
test('--verificar-spec: configuración de loopback (nunca la raíz) y detección de destinos remotos', () => {
  assert.ok(urls(crearRequire97(import.meta.url)(VERIF97)).every(u => u.startsWith('http://127.0.0.1')));
  const ok = opcionesCypress({ front: null, out: null, env: { ROLE: 'PROD' }, configFile: path.relative(ROOT, VERIF97).split(path.sep).join('/') });
  assert.deepEqual(aislamientoVerificacion({ opciones: ok, entorno: PROXY97 }), []);
  const m = (o, e = PROXY97) => aislamientoVerificacion({ opciones: o, entorno: e }).join(' | ');
  assert.match(m({ ...ok, configFile: undefined }), /configuración de verificación/);
  assert.match(m({ ...ok, config: { e2e: { ...ok.config.e2e, baseUrl: 'https://api.inmero.co' } } }), /no loopback|baseUrl/);
  assert.match(m(ok, {}), /PROXY/);
  assert.match(m(ok, { ...PROXY97, CYPRESS_BASE_URL: 'https://api.inmero.co' }), /CYPRESS_BASE_URL/);
  assert.match(m(ok, { ...PROXY97, ELECTRON_RUN_AS_NODE: '1' }), /ELECTRON_RUN_AS_NODE/);
  // La ejecución autorizada usa la configuración aislada del grupo y frontend como baseUrl.
  const real = opcionesCypress({ front: 'https://front.test.example', out: DIR, env: {} });
  assert.equal(path.resolve(ROOT, real.configFile), VERIF97);
  assert.equal(real.config.e2e.baseUrl, 'https://front.test.example');
});
