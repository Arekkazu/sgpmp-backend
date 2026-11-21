import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { preflight, variablesCypress, mismoConjuntoFincas, crearTransporte, informePorCaso } from '../g94.mjs';
import { CAPACIDADES, IDS, ORACULO, evaluarApi, clasificarUi, evaluarResultadoCypress } from '../lib/g94_escenario.mjs';

const dir = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const leer = x => fs.readFileSync(path.join(dir, x), 'utf8');
const runId = 'RUN-G94-V1-20261031-123456';

test('matriz literal, tres comprobaciones y entorno cerrado', () => {
  assert.equal(ORACULO, 'HTTP 200 con arreglos vacíos. La interfaz muestra "No tiene unidades productivas asignadas" y sugiere contactar al administrador; no se devuelve ningún dato de otras granjas ni error interno.');
  assert.deepEqual(IDS, ['API-185-01', 'API-185-02', 'UI-185-01']);
  assert.deepEqual(CAPACIDADES.casos, ['TC-M03-185']);
  const vars = variablesCypress({ runId }, { token: 'LOCAL_FICTICIO', secreto: 'LOCAL', dir: 'TEMP' });
  assert.equal(vars.PROD_LOGIN_TOKEN, 'LOCAL_FICTICIO');
  assert.equal(vars.REFRESH_COOKIE, undefined);
  assert.equal(vars.API_BASE, 'https://api.inmero.co/api-sgpmp-test');
  assert.equal(vars.RUN_ID, runId);
});

test('preflight no ejecuta TEST y enumera orden y escritura única', () => {
  const env = Object.fromEntries(['SIGAB_API_TEST_BASE', 'SIGAB_FRONT_TEST_URL', 'QA_SANDBOX_SECRET',
    'QA_ADMIN_EMAIL', 'QA_ADMIN_PASSWORD', 'QA_PROD_EMAIL', 'QA_PROD_PASSWORD'].map(x => [x, 'LOCAL']));
  env.SIGAB_API_TEST_BASE = 'https://www.api.inmero.co/api-sgpmp-test';
  env.SIGAB_FRONT_TEST_URL = 'https://api.inmero.co/sigab-test';
  env.QA_AUTORIZADO = 'SI';
  const p = preflight({ runId, version: 1, operacion: 'reintentar' }, env);
  assert.equal(p.ok, true);
  assert.match(p.plan.escrituras.join(' '), /PUT \/usuarios/);
  assert.ok(p.plan.orden.indexOf('Newman API') < p.plan.orden.indexOf('GET /usuarios/me sin fincas'));
  assert.ok(p.plan.orden.indexOf('GET /usuarios/me sin fincas') < p.plan.orden.indexOf('Cypress UI'));
});

test('API, UI y Cypress distinguen rechazo, sesión inconclusa y cero pruebas', () => {
  assert.equal(evaluarApi('API-185-01', { http: 200, cuerpo: { total: 0, resumen_unidades: [], sensores: [] } }).estado, 'APROBADO');
  assert.equal(evaluarApi('API-185-01', { http: 200, cuerpo: { total: 1, resumen_unidades: [{}], sensores: [] } }).estado, 'RECHAZADO');
  const base = { peticiones: [{ metodo: 'GET', ruta: '/usuarios/me', en_sandbox: true, http: 200, eco_run: true }],
    dashboard: { http: 200, eco_run: true }, mensaje_exacto: true, contacto_admin: true,
    sin_tarjetas: true, sin_error_interno: true };
  assert.equal(clasificarUi(base).estado, 'APROBADO');
  assert.equal(clasificarUi({ ...base, mensaje_exacto: false }).estado, 'RECHAZADO');
  assert.equal(clasificarUi({ ...base, peticiones: [{ ...base.peticiones[0], http: 503 }] }).estado, 'NO_CONCLUYENTE');
  assert.equal(clasificarUi({ ...base, carga_sin_terminar: true }).estado, 'NO_CONCLUYENTE');
  assert.equal(evaluarResultadoCypress({ acta: { ...base, caso: 'TC-M03-185', id: 'UI-185-01' },
    rel: 'cypress/UI-185-01.json', proceso: 0, error: null,
    resumen: { totalTests: 0, totalPassed: 0, totalFailed: 0, totalPending: 0, totalSkipped: 0, specs: 1 } }).estado, 'ERROR_QA');
});

test('transporte bloquea escrituras ajenas, producto durante Cypress y verifica rollback exacto', async () => {
  const llamadas = [];
  const t = crearTransporte({ base: 'http://127.0.0.1:1', runId: 'ENSAYO-G94-LOCAL', secreto: 'LOCAL',
    fetcher: async (url, opts) => {
      llamadas.push({ url, opts });
      return { status: 200, headers: { get: k => k === 'X-Test-Run-Id' ? 'ENSAYO-G94-LOCAL' : null }, json: async () => ({}) };
    } });
  await t.pedir('POST', '/sesiones/', { login: true, cuerpo: {} });
  t.abrir(); t.idProductor(7);
  await assert.rejects(t.pedir('PUT', '/usuarios/8/fincas', { token: 'A', cuerpo: { ids_fincas: [] } }), /ESCRITURA_FUERA_LISTA_BLANCA/);
  await t.pedir('PUT', '/usuarios/7/fincas', { token: 'A', cuerpo: { ids_fincas: [] } });
  assert.equal(llamadas.at(-1).opts.headers['X-Test-Run-Id'], 'ENSAYO-G94-LOCAL');
  t.iniciarUi();
  await assert.rejects(t.pedir('GET', '/usuarios/me', { token: 'P' }), /PETICION_DURANTE_CYPRESS/);
  t.terminarUi();
  assert.equal(mismoConjuntoFincas([1, 57, 80, 184], [184, 80, 57, 1]), true);
  assert.equal(mismoConjuntoFincas([1, 57], [1]), false);
});

test('rutas canónicas y antecedentes conservados en el RUN oficial', () => {
  const runner = leer('g94.mjs'); const spec = leer('g94.cy.js');
  const coleccion = JSON.parse(leer('G94.postman_collection.json'));
  assert.equal(coleccion.item.length, 2);
  assert.ok(runner.indexOf('runNewman(c,') < runner.indexOf('runCypress(c,'));
  assert.ok(runner.indexOf('runCypress(c,') < runner.indexOf("t.pedir('DELETE'"));
  assert.match(runner, /const perfilUi = await t\.pedir\('GET', '\/usuarios\/me'/);
  assert.match(runner, /### \$\{CASO\}/);
  assert.match(spec, /req\.reply/); assert.match(spec, /req\.continue/);
  assert.doesNotMatch(spec, /SESION_FUERA|describe\.skip/);
  const base = 'Resultados/RUN-G94-V1-20261031-090629/';
  const informe = leer(base + 'TC-M03-G94_resultado.md');
  const indice = JSON.parse(leer(base + 'api/antecedentes/indice.json'));
  assert.equal(indice.run_destino, 'RUN-G94-V1-20261031-090629');
  for (const entrada of indice.archivos) {
    assert.ok(fs.existsSync(path.join(dir, base, 'api/antecedentes', entrada.destino)));
    assert.ok(informe.includes(`(api/antecedentes/${entrada.destino})`));
  }
  assert.match(informe, /RUN de origen del intento 2 fue eliminado/);
});

test('informe oficial identifica la incidencia y desglosa comprobaciones con HTTP y evidencia', () => {
  const ruta = 'Resultados/RUN-G94-V1-20261031-090629/';
  const r = JSON.parse(leer(ruta + 'resultado.json'));
  const informe = leer(ruta + 'TC-M03-G94_resultado.md');
  assert.equal(r.casos['TC-M03-185'].estado, 'RECHAZADO');
  assert.match(informe, /### INC-M03-185-G94-01 — /);
  assert.match(informe, /\| Comprobación \| Tipo \| Esperado \| Observado \| HTTP \| Estado \| Evidencia \|/);
  for (const id of IDS) assert.match(informe, new RegExp(`\\| ${id} \\|`));
  assert.match(informe, /\| UI-185-01 \| UI \|[^\n]*\| 200 \| RECHAZADO \|/);
  assert.match(informe, /\[captura real\]\(cypress\/g94\.cy\.js\/UI-185-01\.png\)/);
  assert.match(informe, /\*\*Impacto y severidad:\*\* MEDIA:/);
  assert.match(informe, /\*\*Equipo inicial:\*\* Desarrollo/);
  assert.match(informePorCaso(r), /### INC-M03-185-G94-01 — /);
});
