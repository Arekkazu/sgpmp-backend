import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import vm from 'node:vm';
import { CAPACIDADES, CASO, ORACULO, PRESUPUESTO, canonico, clasificar } from '../lib/g96_escenario.mjs';
import { preflight, comprobar, fallosNewman, evaluarNewman, esOficial } from '../g96.mjs';
import { contextoEjecucion } from '../lib/contrato_ejecutor.mjs';

const contexto = { version: 1, operacion: 'evaluar', runId: 'RUN-G96-V1-20261026-120000' };
const env = { QA_AUTORIZADO: 'SI', SIGAB_API_TEST_BASE: 'https://www.api.inmero.co/api-sgpmp-test',
  QA_SANDBOX_SECRET: 'sintetico', QA_PROD_EMAIL: 'prod@example.test', QA_PROD_PASSWORD: 'sintetico' };
const pagina = valores => ({ http: 200, eco: true, sensores: valores.map(estado_conectividad => ({ estado_conectividad })) });

test('oráculo, contrato y presupuesto', () => {
  assert.equal(CAPACIDADES.contrato, 'sigab-qa-ejecutor/1');
  assert.deepEqual(CAPACIDADES.comprobaciones_obligatorias[CASO], { API: ['API-187-01'] });
  assert.match(ORACULO, /exclusivamente uno de los valores definidos por RF-58/);
  assert.equal(CAPACIDADES.limite.solicitudes_directas, PRESUPUESTO.lecturas_descubrimiento + PRESUPUESTO.paginas_dashboard);
  assert.equal(preflight(contexto, env).ok, true);
  assert.equal(preflight(contexto, { ...env, QA_AUTORIZADO: 'NO' }).ok, false);
  assert.equal(preflight(contexto, { ...env, SIGAB_API_TEST_BASE: 'http://localhost:1' }).ok, false);
});
test('contexto real del lanzador: claves exactas y ensayo temporal', () => {
  const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'g96-contrato-'));
  try {
    const run = 'ENSAYO-G96-20261026-120000-contrato';
    const archivo = path.join(temp, 'contexto_operacion.json');
    const datos = { grupo: 'G96', version: 1, intento: 1, run_id: run, operacion: 'EVALUAR',
      referencia: 'AUT-LOCAL', casos: [CASO], alcance_reevaluacion: null, version_anterior: null };
    fs.writeFileSync(archivo, JSON.stringify(datos));
    const c = contextoEjecucion(['--operacion', 'evaluar', '--version', '1', '--intento', '1',
      '--run-id', run, '--autorizacion', 'AUT-LOCAL', '--contexto', archivo],
    { grupo: 'G96', casos: [CASO], directorio: path.resolve('..'), modoEnsayo: true });
    assert.deepEqual(Object.keys(c.contexto), Object.keys(datos));
    assert.equal(preflight(c, { ...env, SIGAB_API_TEST_BASE: 'http://127.0.0.1:12345' }, true).ok, true);
  } finally {
    if (!path.resolve(temp).startsWith(path.resolve(os.tmpdir()) + path.sep)) throw Error('TEMP_FUERA_RAIZ');
    fs.rmSync(temp, { recursive: true, force: true });
  }
});
test('enum semántico y veredictos', () => {
  assert.equal(canonico('sin_senal'), 'SIN_SEÑAL');
  assert.equal(canonico('ACTIVO'), null);
  assert.equal(clasificar({ paginas: [pagina(['ONLINE', 'OFFLINE', 'SIN_SEÑAL'])] }).estado, 'APROBADO');
  assert.equal(clasificar({ paginas: [pagina(['ONLINE', 'ACTIVO'])] }).estado, 'RECHAZADO');
  assert.equal(clasificar({ paginas: [pagina([null])] }).estado, 'RECHAZADO');
  assert.equal(clasificar({ paginas: [pagina(['ONLINE'])] }).estado, 'BLOQUEADO');
  assert.equal(clasificar({ paginas: [{ http: 503, eco: true, sensores: null }] }).estado, 'BLOQUEADO');
  assert.equal(clasificar({ paginas: [], error: 'SIN_RESPUESTA' }).estado, 'NO_CONCLUYENTE');
});
test('reporte Newman sintético: enum, script, transporte y HTTP 5xx', () => {
  const fallo = (name, testName, message, at = 'test-script') => ({
    error: { name, test: testName, message }, source: { name: 'API-187-01' }, at,
  });
  const evaluar = (failures, paginas) => {
    const report = { run: { failures } };
    const extraidos = fallosNewman(report);
    const { datos, problemasTecnicos } = evaluarNewman({ paginas, fallos: extraidos, proceso: { error: null } });
    const oficial = esOficial(datos.estado, { cierre: { run: { cierre_http: 200 }, rollback: { verificado: true } },
      problemas_tecnicos: problemasTecnicos }, true);
    return { extraidos, estado: datos.estado, problemasTecnicos, oficial };
  };
  const enumFallido = evaluar([fallo('AssertionError', '[TC-M03-187][ASSERT][API-187-01] enum RF-58 por sensor',
    'expected [ ONLINE, OFFLINE, SIN_SENAL ] to include ACTIVO')], [pagina(['ACTIVO'])]);
  assert.deepEqual(enumFallido.extraidos[0], { tipo: 'AssertionError',
    test: '[TC-M03-187][ASSERT][API-187-01] enum RF-58 por sensor', item: 'API-187-01',
    mensaje: 'expected [ ONLINE, OFFLINE, SIN_SENAL ] to include ACTIVO', at: 'test-script' });
  assert.equal(enumFallido.estado, 'RECHAZADO');
  assert.deepEqual(enumFallido.problemasTecnicos, []);
  assert.equal(enumFallido.oficial, true);
  const script = evaluar([fallo('TypeError', '', 'Cannot read properties of undefined')],
    [pagina(['ONLINE', 'OFFLINE', 'SIN_SEÑAL'])]);
  assert.deepEqual(script.problemasTecnicos, ['NEWMAN_ERROR_SCRIPT_O_TRANSPORTE']);
  assert.equal(script.oficial, false);
  const transporte = evaluar([fallo('Error', '', 'connect ECONNREFUSED 127.0.0.1:1', 'request')], []);
  assert.equal(transporte.estado, 'NO_CONCLUYENTE');
  assert.equal(transporte.oficial, false);
  const servidor = evaluar([], [{ http: 503, eco: true, sensores: null }]);
  assert.equal(servidor.estado, 'BLOQUEADO');
  assert.equal(servidor.oficial, false);
  const http = evaluar([fallo('AssertionError', '[TC-M03-187][PRE] HTTP 200', 'expected 503 to equal 200')],
    [{ http: 503, eco: true, sensores: null }]);
  assert.equal(http.estado, 'BLOQUEADO');
  assert.deepEqual(http.problemasTecnicos, []);
  const eco = evaluar([fallo('AssertionError', '[TC-M03-187][INFO] eco', 'expected false to equal true')],
    [{ http: 200, eco: false, sensores: [{ estado_conectividad: 'ONLINE' }] }]);
  assert.equal(eco.estado, 'NO_CONCLUYENTE');
  assert.deepEqual(eco.problemasTecnicos, []);
  const preflight = evaluar([fallo('AssertionError', '[TC-M03-187][PRE] autorización', 'precondición incumplida')],
    [pagina(['ONLINE', 'OFFLINE', 'SIN_SEÑAL'])]);
  assert.deepEqual(preflight.problemasTecnicos, ['NEWMAN_ERROR_SCRIPT_O_TRANSPORTE']);
});
test('colección única: GET, aserción enum y paginación', () => {
  const col = JSON.parse(fs.readFileSync(new URL('../G96.postman_collection.json', import.meta.url), 'utf8'));
  assert.equal(col.item.length, 1);
  assert.equal(col.item[0].request.method, 'GET');
  const s = col.item[0].event.map(e => e.script.exec.join('\n')).join('\n');
  new vm.Script(s);
  assert.match(s, /API-187-01/);
  assert.match(s, /setNextRequest/);
  assert.doesNotMatch(JSON.stringify(col), /\/test-control\/query|POST|DELETE/);
  assert.equal(comprobar(), 0);
});
test('script Postman recorre páginas y corta al hallar valor ajeno', () => {
  const col = JSON.parse(fs.readFileSync(new URL('../G96.postman_collection.json', import.meta.url), 'utf8'));
  const codigo = col.item[0].event.find(e => e.listen === 'test').script.exec.join('\n');
  const variables = new Map(Object.entries({ unidades: '[1,268]', indice: '0', unidad: '1', pagina: '1',
    limite_paginas: '12', paginas_usadas: '0', vistos: '[]', por_pagina: '50', run_id: 'RUN-LOCAL' }));
  const ejecutar = (valores, total, http = 200) => {
    let siguiente = undefined, fallos = 0;
    const pm = { environment: { get: k => variables.get(k), set: (k, v) => variables.set(k, v) },
      response: { code: http, headers: { get: () => 'RUN-LOCAL' }, json: () => ({ total,
        sensores: valores.map(estado_conectividad => ({ estado_conectividad })) }) },
      test: (_nombre, f) => { try { f(); } catch { fallos++; } },
      expect: permitidos => ({ to: { include: v => { if (!permitidos.includes(v)) throw Error('enum'); } } }),
      execution: { setNextRequest: x => { siguiente = x; } }, info: { requestName: 'API-187-01' } };
    vm.runInNewContext(codigo, { pm });
    return { siguiente, fallos };
  };
  assert.equal(ejecutar(['ONLINE'], 51).siguiente, 'API-187-01');
  assert.equal(variables.get('pagina'), '2');
  assert.equal(ejecutar(['OFFLINE', 'SIN_SEÑAL'], 51).siguiente, null);
  variables.set('pagina', '1'); variables.set('vistos', '[]');
  const fuera = ejecutar(['ACTIVO'], 1);
  assert.equal(fuera.fallos, 1);
  assert.equal(fuera.siguiente, null);
});
// Transcripción local del contrato comunicado para registro_qa.py; no accede al lanzador.
function validarObligatorias(capacidades) {
  const requeridas = capacidades.comprobaciones_obligatorias;
  if (!Array.isArray(capacidades.casos) || !capacidades.casos.length || !requeridas
    || typeof requeridas !== 'object' || Array.isArray(requeridas)
    || JSON.stringify(Object.keys(requeridas).sort()) !== JSON.stringify([...capacidades.casos].sort()))
    throw Error('Casos incoherentes');
  const ids = new Set();
  for (const fuentes of Object.values(requeridas)) {
    if (!fuentes || typeof fuentes !== 'object' || Array.isArray(fuentes)
      || !Object.keys(fuentes).length || Object.keys(fuentes).some(f => !['API', 'UI'].includes(f)))
      throw Error('Fuentes obligatorias invalidas');
    for (const lista of Object.values(fuentes)) {
      if (!Array.isArray(lista) || !lista.length) throw Error('IDs obligatorios invalidos');
      for (const id of lista) {
        if (typeof id !== 'string' || !/^[A-Za-z0-9_-]{1,100}$/.test(id) || ids.has(id))
          throw Error('IDs obligatorios invalidos');
        ids.add(id);
      }
    }
  }
  return requeridas;
}
function clasificarRegistro(capacidades, r, presentes) {
  const requeridas = validarObligatorias(capacidades);
  const requiereUI = Object.values(requeridas).some(fuentes => 'UI' in fuentes);
  const nombre = 'TC-M03-G96_resultado.md';
  const evidenciaValida = x => typeof x === 'string' && x.length > 0
    && !path.isAbsolute(x) && !path.win32.isAbsolute(x)
    && !x.split(/[\\/]/).includes('..') && presentes.has(x);
  return r.run_id === contexto.runId && r.version === contexto.version
    && r.cierre?.run?.cierre_http === 200 && r.cierre?.rollback?.verificado === true
    && typeof r.consume_version === 'boolean'
    && r.casos && JSON.stringify(Object.keys(r.casos).sort()) === JSON.stringify([...capacidades.casos].sort())
    && Object.values(r.casos).every(x => ['APROBADO', 'RECHAZADO'].includes(x?.estado))
    && Array.isArray(r.comprobaciones)
    && Object.entries(requeridas).every(([caso, fuentes]) => Object.entries(fuentes).every(([fuente, ids]) =>
      ids.every(id => r.comprobaciones.some(x => x.caso === caso && x.fuente === fuente && x.id === id
        && x.tipo === 'ASSERT' && ['APROBADO', 'RECHAZADO'].includes(x.estado)))))
    && (!requiereUI || r.cypress?.total_pruebas > 0)
    && evidenciaValida(nombre) && Array.isArray(r.evidencias)
    && r.evidencias.every(evidenciaValida) && r.oficial === true;
}
test('registro QA: RUN completo RECHAZADO oficial y faltantes no oficiales', () => {
  const nombre = 'TC-M03-G96_resultado.md';
  const presentes = new Set([nombre, 'resultado.json', 'newman/newman-G96.json', 'newman/newman-G96.html']);
  const base = { run_id: contexto.runId, version: 1, oficial: true, consume_version: true,
    cierre: { run: { cierre_http: 200 }, rollback: { verificado: true } },
    casos: { [CASO]: { estado: 'RECHAZADO' } },
    comprobaciones: [{ caso: CASO, fuente: 'API', id: 'API-187-01', tipo: 'ASSERT', estado: 'RECHAZADO',
      motivo: 'ACTIVO', evidencia: 'newman/newman-G96.json' }],
    cypress: { total_pruebas: 0 }, evidencias: [...presentes] };
  const conforme = r => clasificarRegistro(CAPACIDADES, r, presentes);
  assert.equal(conforme(base), true);
  assert.equal(conforme({ ...base, casos: { [CASO]: { estado: 'BLOQUEADO' } } }), false);
  assert.equal(conforme({ ...base, comprobaciones: [] }), false);
  assert.equal(conforme({ ...base, comprobaciones: [{ ...base.comprobaciones[0], tipo: 'INFO' }] }), false);
  assert.equal(conforme({ ...base, cierre: { run: { cierre_http: 500 }, rollback: { verificado: true } } }), false);
  assert.equal(conforme({ ...base, evidencias: ['../fuera.json'] }), false);
  assert.equal(conforme({ ...base, oficial: false }), false);
  assert.equal(clasificarRegistro(CAPACIDADES, base, new Set([...presentes].filter(x => x !== nombre))), false);
});
test('registro QA: UI vacía inválida y UI declarada exige Cypress', () => {
  const requeridas = CAPACIDADES.comprobaciones_obligatorias;
  const capacidades = fuentes => ({ ...CAPACIDADES, comprobaciones_obligatorias: { [CASO]: fuentes } });
  assert.deepEqual(validarObligatorias(CAPACIDADES), requeridas);
  assert.throws(() => validarObligatorias(capacidades({ API: ['API-187-01'], UI: [] })),
    /IDs obligatorios invalidos/);
  assert.throws(() => validarObligatorias(capacidades({ API: ['API-187-01', 'API-187-01'] })),
    /IDs obligatorios invalidos/);
  assert.throws(() => validarObligatorias(capacidades({ API: ['ID inválido'] })),
    /IDs obligatorios invalidos/);
  assert.throws(() => validarObligatorias({ ...CAPACIDADES, casos: ['TC-M03-999'] }),
    /Casos incoherentes/);
  const presentes = new Set(['TC-M03-G96_resultado.md', 'newman/newman-G96.json']);
  const base = { run_id: contexto.runId, version: 1, oficial: true, consume_version: true,
    cierre: { run: { cierre_http: 200 }, rollback: { verificado: true } },
    casos: { [CASO]: { estado: 'APROBADO' } },
    comprobaciones: [
      { caso: CASO, fuente: 'API', id: 'API-187-01', tipo: 'ASSERT', estado: 'APROBADO' },
      { caso: CASO, fuente: 'UI', id: 'UI-187-01', tipo: 'ASSERT', estado: 'APROBADO' },
    ], cypress: { total_pruebas: 0 }, evidencias: ['newman/newman-G96.json'] };
  const conUI = capacidades({ API: ['API-187-01'], UI: ['UI-187-01'] });
  assert.equal(clasificarRegistro(conUI, base, presentes), false);
  assert.equal(clasificarRegistro(conUI, { ...base, cypress: { total_pruebas: 1 } }, presentes), true);
});
