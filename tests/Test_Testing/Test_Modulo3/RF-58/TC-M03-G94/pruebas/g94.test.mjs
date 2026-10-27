import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';
import { leerEnv, preflight, crearTransporte, prevalidarHerramientas,
  mismoConjuntoFincas, variablesCypress } from '../g94.mjs';
import { CAPACIDADES, IDS, SESION_FUERA, idsFincas, evaluarApi, clasificarUi,
  evaluarResultadoCypress } from '../lib/g94_escenario.mjs';
import { sanearArtefacto } from '../lib/seguridad.mjs';
import { iniciarLocal } from './g94_arranque_local.mjs';

const DIR = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const env = { QA_AUTORIZADO: 'SI', SIGAB_API_TEST_BASE: 'https://www.api.inmero.co/api-sgpmp-test',
  SIGAB_FRONT_TEST_URL: 'https://api.inmero.co/sigab-test', QA_SANDBOX_SECRET: 'SINTETICO',
  QA_ADMIN_EMAIL: 'admin@example.invalid', QA_ADMIN_PASSWORD: 'SINTETICO',
  QA_PROD_EMAIL: 'productor@example.invalid', QA_PROD_PASSWORD: 'SINTETICO' };
const contexto = { runId: 'ENSAYO-G94-LOCAL', version: 1, operacion: 'evaluar' };

test('contrato publica solo las tres comprobaciones y operaciones autorizadas', () => {
  assert.equal(CAPACIDADES.contrato, 'sigab-qa-ejecutor/1');
  assert.deepEqual(CAPACIDADES.comprobaciones_obligatorias['TC-M03-185'],
    { API: ['API-185-01', 'API-185-02'], UI: ['UI-185-01'] });
  assert.deepEqual(IDS, ['API-185-01', 'API-185-02', 'UI-185-01']);
  assert.equal(preflight(contexto, env).ok, true);
  assert.ok(preflight({ ...contexto, version: 2 }, env).barreras.includes('REEVALUACION_SIN_DECISION'));
  assert.ok(preflight(contexto, { ...env, QA_AUTORIZADO: 'NO' }).barreras.includes('QA_AUTORIZADO'));
});

test('carga .env sintético en temporal sin consultar el real', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'g94-env-'));
  assert.ok(path.resolve(dir).startsWith(path.resolve(os.tmpdir()) + path.sep));
  try {
    const archivo = path.join(dir, '.env.qa');
    fs.writeFileSync(archivo, "QA_PROD_EMAIL='archivo@example.invalid'\nQA_AUTORIZADO=SI\n");
    const datos = leerEnv({ QA_PROD_EMAIL: 'proceso@example.invalid', QA_AUTORIZADO: 'NO' }, archivo);
    assert.equal(datos.QA_PROD_EMAIL, 'proceso@example.invalid');
    assert.equal(datos.QA_AUTORIZADO, 'NO');
  } finally { fs.rmSync(dir, { recursive: true, force: true }); }
});

test('Newman tiene 30 s para --version y diagnóstico estructurado', () => {
  const tiempos = [];
  const h = prevalidarHerramientas({ cliNewman: () => 'newman-local.js', cliCypress: () => 'cypress-local.js', chromeDisponible: () => true,
    spawn: (_exe, _args, opts) => { tiempos.push(opts.timeout); return { status: 0, stdout: '6.2.2' }; } });
  assert.deepEqual(tiempos, [30000, 30000]);
  assert.equal(h.valido, true);
  const fallo = prevalidarHerramientas({ cliNewman: () => 'newman-local.js', cliCypress: () => 'cypress-local.js', chromeDisponible: () => true,
    spawn: () => ({ status: null, error: { code: 'ETIMEDOUT' } }) });
  assert.equal(fallo.diagnostico.newman.vencio_tiempo, true);
  assert.equal(fallo.valido, false);
});

test('API exige vacío sin 5xx ni datos de otras fincas', () => {
  assert.deepEqual(idsFincas({ http: 200, cuerpo: { total: 2, items: [{ id_finca: 4 }, { id_finca: 1 }] } }), [1, 4]);
  assert.throws(() => idsFincas({ http: 200, cuerpo: { total: 2, items: [] } }));
  const vacio = { http: 200, cuerpo: { total: 0, resumen_unidades: [], sensores: [] } };
  assert.equal(evaluarApi('API-185-01', vacio).estado, 'APROBADO');
  assert.equal(evaluarApi('API-185-01', { ...vacio, cuerpo: { ...vacio.cuerpo, sensores: [{}] } }).estado, 'RECHAZADO');
  for (const http of [403, 404]) assert.equal(evaluarApi('API-185-02', { http }).estado, 'APROBADO');
  assert.equal(evaluarApi('API-185-02', { http: 500 }).estado, 'RECHAZADO');
});

test('rollback compara el conjunto exacto y la evidencia sanea identificadores privados', () => {
  assert.equal(mismoConjuntoFincas([4, 1], [1, 4]), true);
  assert.equal(mismoConjuntoFincas([4, 1], [4]), false);
  assert.equal(mismoConjuntoFincas([], []), true);
  const limpio = sanearArtefacto(JSON.stringify({ email: 'privado@example.invalid', token: 'SINTETICO' }), ['SINTETICO']);
  assert.doesNotMatch(limpio, /privado@example\.invalid|SINTETICO/);
});

test('UI separa sesión 5xx, pantalla con texto distinto y aprobación completa', () => {
  const base = { peticiones: [{ metodo: 'POST', ruta: '/sesiones/refresh', http: 200,
    en_sandbox: false, eco_run: false }],
    dashboard: { http: 200, eco_run: true }, mensaje_exacto: true, contacto_admin: true,
    sin_tarjetas: true, sin_error_interno: true };
  assert.equal(clasificarUi(base).estado, 'APROBADO');
  assert.equal(clasificarUi({ ...base, mensaje_exacto: false }).estado, 'RECHAZADO');
  assert.equal(clasificarUi({ ...base, peticiones: [{ metodo: 'GET', ruta: '/usuarios/me', http: 500,
    en_sandbox: false, eco_run: false }] }).estado, 'BLOQUEADO');
  assert.equal(clasificarUi({ ...base, dashboard: { http: 500, eco_run: true } }).estado, 'RECHAZADO');
});

test('cinco modos clasifican la UI y capturan la página completa', () => {
  const base = { peticiones: [{ metodo: 'GET', ruta: '/usuarios/me', http: 200,
    en_sandbox: false, eco_run: false }],
    dashboard: { http: 200, eco_run: true }, mensaje_exacto: true, contacto_admin: true,
    sin_tarjetas: true, sin_error_interno: true };
  const matriz = [
    ['ok', base, 'APROBADO'],
    ['texto', { ...base, mensaje_exacto: false }, 'RECHAZADO'],
    ['sesion500', { ...base, dashboard: null,
      peticiones: [{ metodo: 'GET', ruta: '/usuarios/me', http: 500,
        en_sandbox: false, eco_run: false }] }, 'BLOQUEADO'],
    ['lento', { ...base, dashboard: null }, 'NO_CONCLUYENTE'],
    ['sin_eco_dashboard', { ...base, dashboard: { http: 200, eco_run: false },
      peticiones: [...base.peticiones, { metodo: 'GET', ruta: '/iot/monitoreo/dashboard',
        http: 200, en_sandbox: true, eco_run: false }] }, 'NO_CONCLUYENTE'],
  ];
  for (const [modo, acta, esperado] of matriz)
    assert.equal(clasificarUi(acta).estado, esperado, modo);
  const spec = fs.readFileSync(path.join(DIR, 'g94.cy.js'), 'utf8');
  assert.match(spec, /estado: 'NO_CONCLUYENTE'/);
  assert.match(spec, /motivo: 'dashboard no recibido en el plazo'/);
  assert.match(spec, /cy\.screenshot\('UI-185-01', \{ capture: 'fullPage', overwrite: true \}\)/);
  assert.doesNotMatch(spec, /cy\.get\('main'\)\.screenshot/);
  assert.match(spec, /motivo_captura/);
});

test('guarda acepta bases loopback con rutas y contrato exacto del RUN real', () => {
  const spec = fs.readFileSync(path.join(DIR, 'g94.cy.js'), 'utf8');
  const runId = 'RUN-G94-V1-20261026-123456';
  const vars = variablesCypress({ runId }, { cookie: 'SINTETICO', secreto: 'SINTETICO', dir: 'TEMPORAL' });
  assert.deepEqual(Object.keys(vars).sort(), ['API_BASE', 'ARTIFACTS_DIR', 'AUTORIZADO_RUN',
    'FRONT_BASE', 'REFRESH_COOKIE', 'RUN_ID', 'SANDBOX_SECRET'].sort());
  assert.equal(vars.API_BASE, 'https://api.inmero.co/api-sgpmp-test');
  assert.equal(vars.FRONT_BASE, 'https://api.inmero.co/sigab-test');
  assert.equal(vars.RUN_ID, runId);
  assert.equal(vars.AUTORIZADO_RUN, 'SI');
  assert.equal(vars.ARTIFACTS_DIR, 'TEMPORAL');
  const guarda = v => vm.runInNewContext(`${spec}\n;({ ensayo, autorizado })`,
    { Cypress: { env: key => v[key] }, describe: () => {} });
  assert.equal(guarda(vars).autorizado, true);
  assert.equal(guarda({ ...vars, RUN_ID: 'RUN-G94-V1-INVALIDO' }).autorizado, false);
  for (const clave of Object.keys(vars)) assert.equal(guarda({ ...vars, [clave]: '' }).autorizado, false, clave);
  const local = { ...vars, ENSAYO_LOCAL: 'SI', RUN_ID: 'ENSAYO-G94-OK',
    API_BASE: 'http://127.0.0.1:42871/api-sgpmp-test',
    FRONT_BASE: 'http://127.0.0.1:42871/sigab-test' };
  assert.equal(guarda(local).ensayo, true);
  assert.equal(guarda(local).autorizado, true);
  assert.equal(guarda({ ...local, RUN_ID: 'ENSAYO-G94-LENTO' }).autorizado, true);
  assert.equal(guarda({ ...local, RUN_ID: 'ENSAYO-G94-SIN_ECO_DASHBOARD' }).autorizado, true);
  assert.equal(guarda({ ...local, API_BASE: 'http://127.0.0.1:42871' }).autorizado, false);
  assert.equal(guarda({ ...local, FRONT_BASE: 'http://localhost:42871/sigab-test' }).autorizado, false);
});

test('guarda inválida falla dentro de it y nunca usa describe.skip', () => {
  const spec = fs.readFileSync(path.join(DIR, 'g94.cy.js'), 'utf8');
  assert.doesNotMatch(spec, /describe\.skip|it\.skip|\.pending\(/);
  assert.match(spec, /if \(!autorizado\)\s*\{[\s\S]*?BLOQUEO_G94:[\s\S]*?throw new Error\(acta\.motivo\)/);
});

test('ejecutor convierte pending, cero pruebas y acta ausente en ERROR_QA', () => {
  const acta = { caso: 'TC-M03-185', id: 'UI-185-01',
    peticiones: [{ metodo: 'POST', ruta: '/sesiones/refresh', http: 200,
      en_sandbox: false, eco_run: false }],
    dashboard: { http: 200, eco_run: true }, mensaje_exacto: true,
    contacto_admin: true, sin_tarjetas: true, sin_error_interno: true };
  const resumen = { totalTests: 1, totalPassed: 1, totalFailed: 0,
    totalPending: 0, totalSkipped: 0, specs: 1 };
  const ui = { acta, rel: 'cypress/UI-185-01.json', resumen, proceso: 0, error: null };
  assert.equal(evaluarResultadoCypress(ui).estado, 'APROBADO');
  assert.equal(evaluarResultadoCypress({ ...ui, resumen: { ...resumen,
    totalPassed: 0, totalPending: 1 }, acta: null }).estado, 'ERROR_QA');
  assert.equal(evaluarResultadoCypress({ ...ui, resumen: { ...resumen,
    totalTests: 0, totalPassed: 0 } }).estado, 'ERROR_QA');
  assert.equal(evaluarResultadoCypress({ ...ui, acta: null, rel: null }).estado, 'ERROR_QA');
  assert.equal(evaluarResultadoCypress({ ...ui, resumen: { ...resumen,
    totalPassed: 0, totalFailed: 1 }, proceso: 1, acta: { ...acta,
    peticiones: [{ metodo: 'GET', ruta: '/usuarios/me', http: 500,
      en_sandbox: false, eco_run: false }] } }).estado, 'BLOQUEADO');
});

test('transporte exige login fuera, cabeceras RUN, PUT único e impide Productor tras UI', async () => {
  const llamadas = [];
  const fetcher = async (url, opts) => {
    llamadas.push({ ruta: new URL(url).pathname, ...opts });
    return { status: opts.method === 'DELETE' ? 200 : 200,
      headers: { get: key => key === 'X-Test-Run-Id' ? 'ENSAYO-G94-LOCAL' : null },
      json: async () => ({}) };
  };
  const t = crearTransporte({ base: 'http://127.0.0.1:1', runId: contexto.runId, secreto: 'SINTETICO', fetcher });
  await t.pedir('POST', '/sesiones/', { login: true, cuerpo: {} });
  t.abrir(); t.idProductor(7);
  await assert.rejects(t.pedir('POST', '/sesiones/', { login: true, cuerpo: {} }), /LOGIN_DENTRO_RUN_PROHIBIDO/);
  await assert.rejects(t.pedir('PUT', '/usuarios/8/fincas', { token: 'ADMIN', cuerpo: { ids_fincas: [] } }), /ESCRITURA_FUERA_LISTA_BLANCA/);
  await t.pedir('PUT', '/usuarios/7/fincas', { token: 'ADMIN', cuerpo: { ids_fincas: [] } });
  assert.equal(llamadas.at(-1).headers['X-Test-Run-Id'], contexto.runId);
  t.iniciarUi();
  await assert.rejects(t.pedir('GET', '/usuarios/me', { token: 'PRODUCTOR' }), /PETICION_DURANTE_CYPRESS/);
  t.terminarUi();
  await t.pedir('DELETE', `/test-control/runs/${contexto.runId}`, { cierre: true });
  await t.pedir('GET', '/usuarios/7/detalle', { token: 'ADMIN' });
  assert.equal(llamadas.at(-1).headers.Authorization, 'Bearer ADMIN');
  assert.equal(t.estado().cerrado, true);
});

test('fuentes mantienen API antes de UI, Cypress propio y sin stubs ni SQL', () => {
  const runner = fs.readFileSync(path.join(DIR, 'g94.mjs'), 'utf8');
  const spec = fs.readFileSync(path.join(DIR, 'g94.cy.js'), 'utf8');
  const coleccion = fs.readFileSync(path.join(DIR, 'G94.postman_collection.json'), 'utf8');
  assert.ok(runner.indexOf('runNewman(c,') < runner.indexOf('runCypress(c,'));
  assert.ok(runner.indexOf('runCypress(c,') < runner.indexOf("t.pedir('DELETE'"));
  assert.match(runner, /'--config-file', CONFIG/);
  assert.doesNotMatch(runner + spec, /configFile:\s*false|req\.reply\(|\/test-control\/query|SELECT\s+count\(/i);
  assert.match(spec, /req\.continue\(/);
  assert.doesNotMatch(spec, /req\.alias\s*===/);
  assert.match(coleccion, /X-Test-Run-Id/);
  assert.match(coleccion, /X-Sandbox-Secret/);
});

test('interceptación deja fuera solo la lista cerrada y exige eco al resto', () => {
  const spec = fs.readFileSync(path.join(DIR, 'g94.cy.js'), 'utf8');
  let preparar;
  let interceptar;
  const baseApi = 'http://127.0.0.1:42871/api-sgpmp-test';
  const variables = { API_BASE: baseApi, FRONT_BASE: 'http://127.0.0.1:42871/sigab-test',
    RUN_ID: 'ENSAYO-G94-OK', ENSAYO_LOCAL: 'SI', SANDBOX_SECRET: 'SINTETICO',
    REFRESH_COOKIE: 'SINTETICO', ARTIFACTS_DIR: 'TEMPORAL', AUTORIZADO_RUN: 'SI' };
  const { acta } = vm.runInNewContext(`${spec}\n;({ acta })`, {
    Cypress: { env: key => variables[key] }, URL,
    describe: (_nombre, cb) => cb(), beforeEach: cb => { preparar = cb; },
    afterEach: () => {}, it: () => {},
    cy: { intercept: (_regla, cb) => { interceptar = cb; } },
  });
  preparar();
  const pedir = (metodo, ruta, body) => {
    const req = { method: metodo, url: `${baseApi}${ruta}`, headers: {},
      continue: cb => cb({ statusCode: 200,
        headers: { 'x-test-run-id': req.headers['X-Test-Run-Id'] ?? undefined }, body }) };
    interceptar(req);
    return req;
  };
  for (const clave of SESION_FUERA) {
    const [metodo, ruta] = clave.split(' ');
    const req = pedir(metodo, ruta, ruta === '/usuarios/me' ? { fincas: [{}, {}] } : {});
    assert.equal(req.headers['X-Test-Run-Id'], undefined);
    assert.equal(req.headers['X-Sandbox-Secret'], undefined);
  }
  for (const ruta of ['/configuracion/interfaz/contexto', '/iot/monitoreo/dashboard',
    '/usuarios/me/', '/sesiones/me/permisos/']) {
    const req = pedir('GET', ruta, {});
    assert.equal(req.headers['X-Test-Run-Id'], variables.RUN_ID);
    assert.equal(req.headers['X-Sandbox-Secret'], variables.SANDBOX_SECRET);
  }
  assert.deepEqual(Array.from(acta.rutas_fuera_sandbox), SESION_FUERA);
  assert.equal(acta.fincas_perfil, 2);
  assert.equal(acta.peticiones.length, 7);
  assert.equal(clasificarUi({ peticiones: [{ metodo: 'GET', ruta: '/usuarios/me/',
    http: 200, en_sandbox: false, eco_run: false }], dashboard: null }).estado, 'ERROR_QA');
});

test('informe conserva decisión, evidencia histórica y V1 reintentar', () => {
  const runner = fs.readFileSync(path.join(DIR, 'g94.mjs'), 'utf8');
  const contrato = fs.readFileSync(path.join(DIR, 'lib/contrato_ejecutor.mjs'), 'utf8');
  const informe = fs.readFileSync(path.join(DIR, 'Resultados',
    'RUN-G94-V1-20261026-043704', 'TC-M03-G94_resultado.md'), 'utf8');
  assert.match(runner, /## Decisión metodológica de la UI/);
  assert.match(runner, /INC-M03-184-G93-02 \(abierta, primer contacto DBA\)/);
  assert.match(runner, /intento 1 documentado en el informe consolidado V1/);
  assert.match(runner, /rutas_fuera_sandbox/);
  assert.match(runner, /fincas_perfil/);
  assert.match(contrato, /version === 1 \? path\.join\(directorio, 'Resultados'\)/);
  assert.match(informe, /RUN-G94-V1-20261026-041954 \(eliminado por decisión QA\)/);
  assert.match(informe, /La evidencia nativa del intento 1 se eliminó/);
  assert.doesNotMatch(informe, /\]\([^)]*RUN-G94-V1-20261026-041954/);
});

test('servidor local reproduce sesión 500 con cabeceras y dashboard sin eco', async () => {
  for (const modo of ['ok', 'texto', 'sesion500', 'lento', 'sin_eco_dashboard']) {
    const { servidor, base } = await iniciarLocal(modo);
    try {
      for (const ruta of ['/sesiones/refresh', '/usuarios/me', '/sesiones/me/permisos']) {
        const metodo = ruta === '/sesiones/refresh' ? 'POST' : 'GET';
        const fuera = await fetch(`${base}/api-sgpmp-test${ruta}`, { method: metodo });
        const dentro = await fetch(`${base}/api-sgpmp-test${ruta}`, { method: metodo,
          headers: { 'X-Test-Run-Id': 'ENSAYO-G94-OK' } });
        assert.equal(fuera.status, modo === 'sesion500' ? 500 : 200);
        assert.equal(fuera.headers.get('x-test-run-id'), null);
        assert.equal(dentro.status, 500);
      }
      for (const ruta of ['/configuracion/interfaz/contexto', '/iot/monitoreo/dashboard']) {
        const fuera = await fetch(`${base}/api-sgpmp-test${ruta}`);
        const dentro = await fetch(`${base}/api-sgpmp-test${ruta}`, {
          headers: { 'X-Test-Run-Id': 'ENSAYO-G94-OK' } });
        assert.equal(fuera.status, 400);
        assert.equal(dentro.status, 200);
        assert.equal(dentro.headers.get('x-test-run-id'),
          modo === 'sin_eco_dashboard' && ruta.endsWith('/dashboard') ? null : 'ENSAYO-G94-OK');
      }
    } finally { await new Promise(resolve => servidor.close(resolve)); }
  }
});
