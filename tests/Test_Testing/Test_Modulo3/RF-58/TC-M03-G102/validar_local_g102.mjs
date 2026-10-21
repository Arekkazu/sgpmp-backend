// Pruebas unitarias locales de G102: funciones puras y scripts de la colección con respuestas
// sintéticas (sin red). Los datos sintéticos solo validan la lógica de las aserciones.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { CASOS, REQUERIDAS, UNIDADES, nombresUnidad } from './ejecutar_tc_m03_g102.mjs';
import { autorizar, leerEnv, serialQa, cuerpoLectura, cuerpoAlerta, leerConteo, consultaTestigoDispositivo, consultaEstadosActuales, idDeTexto, varianteDeTexto, tipoDeTexto, casoDeTexto, veredictoCasos, redactor } from './monitoreo_lib.mjs';

const col = JSON.parse(fs.readFileSync(new URL('./TC-M03-G102.postman_collection.json', import.meta.url), 'utf8'));

/** pm mínimo: ejecuta los scripts de test de un ítem y devuelve los tests con su resultado. */
function pmFalso({ code, body, env, colVars, nombre }) {
  const tests = []; let siguiente = null;
  const expect = (x, m = '') => {
    const fallo = msg => { throw Error(`${m} ${msg}`.trim()); };
    return { to: {
      eql: y => { if (JSON.stringify(x) !== JSON.stringify(y)) fallo(`esperado ${JSON.stringify(y)}, obtenido ${JSON.stringify(x)}`); },
      be: { within: (a, b) => { if (!(x >= a && x <= b)) fallo(`${x} fuera de [${a}, ${b}]`); }, at: { most: n => { if (!(x <= n)) fallo(`${x} > ${n}`); } } },
    } };
  };
  const pm = {
    response: { code, responseTime: 10, json: () => { if (body === undefined) throw Error('sin JSON'); return body; }, headers: { get: () => env.run_id } },
    environment: { get: k => env[k], set: (k, v) => { env[k] = v; } },
    collectionVariables: { get: k => colVars[k], set: (k, v) => { colVars[k] = v; } },
    info: { requestName: nombre },
    execution: { setNextRequest: n => { siguiente = n; } },
    test: (n, f) => { try { f(); tests.push({ n, ok: true }); } catch (e) { tests.push({ n, ok: false, e: e.message }); } },
    expect,
  };
  return { pm, tests, siguiente: () => siguiente };
}
function correr(nombreItem, { code = 200, body, env, colVars = {} }) {
  const it = col.item.find(i => i.name === nombreItem);
  const f = pmFalso({ code, body, env, colVars, nombre: it.name });
  new Function('pm', 'postman', it.event.find(e => e.listen === 'test').script.exec.join('\n'))(f.pm, {});
  return { tests: f.tests, siguiente: f.siguiente() };
}
const rango = (a, n) => Array.from({ length: n }, (_, i) => a + i);
const respuesta = (ids, unidad, total = ids.length) => ({ total, sensores: ids.map(id => ({ id_sensor: id, id_infraestructura: unidad })) });
const ok = (tests, id) => tests.filter(t => t.n.includes(id)).every(t => t.ok) && tests.some(t => t.n.includes(id));

test('barrera: niega sin autorización, DEV o frontend no TEST; acepta condiciones futuras válidas', () => {
  const v = { QA_AUTORIZADO: 'SI', QA_SETUP_EMAIL: 'a@x.test', QA_ENG_EMAIL: 'e@x.test', QA_COMMON_PASSWORD: 'x', QA_SANDBOX_SECRET: 'y', SIGAB_API_TEST_BASE: 'https://www.api.inmero.co/api-sgpmp-test', SIGAB_FRONT_TEST_URL: 'https://api.inmero.co/sigab-test' };
  const a = { ambiente: 'TEST', autorizacion: 'DEV-REF-123', efectos: ['notificacion-login'] };
  assert.equal(autorizar(v, a, { frontend: true }).ok, true);
  assert.equal(autorizar({ ...v, QA_AUTORIZADO: 'NO' }, a, { frontend: true }).ok, false);
  assert.equal(autorizar(v, { ...a, ambiente: 'DEV' }, { frontend: true }).ok, false);
  assert.equal(autorizar({ ...v, SIGAB_FRONT_TEST_URL: 'https://dev.example' }, a, { frontend: true }).ok, false);
  assert.equal(autorizar({ ...v, SIGAB_API_TEST_BASE: 'http://api.test.example' }, a, { frontend: true }).ok, false);
  assert.equal(autorizar(v, { ...a, efectos: [] }, { frontend: true }).ok, false);
  assert.deepEqual(leerEnv('QA_AUTORIZADO=NO\n# c\nQA_ENG_EMAIL="e@x.test"'), { QA_AUTORIZADO: 'NO', QA_ENG_EMAIL: 'e@x.test' });
});
test('escenario: 50, 51 y 200 sensores con nombres únicos y seriales QA válidos', () => {
  assert.deepEqual(UNIDADES, { U50: 50, U51: 51, U200: 200 });
  for (const u of Object.keys(UNIDADES)) assert.equal(new Set(nombresUnidad('QA G102 20261017000000', u)).size, UNIDADES[u]);
  assert.equal(serialQa({}, 'G102', '20261017000000', 'U200'), 'QAAUTO-G102-20261017000000-U200');
  assert.throws(() => serialQa({ QA_DEVICE_PREFIX: 'X'.repeat(40) }, 'G102', '20261017000000', 'U200'));
});
test('contratos del dispositivo: punto único de credencial (DEV-06) y severidades RF-57', () => {
  const l = cuerpoLectura({ idDispositivo: 1, idSensor: 2, serial: 'QAAUTO-1', timestamp: 't' });
  assert.equal(l.access_key, 'QAAUTO-1'); assert.equal(l.estado_conectividad, true); assert.equal(l.origen, 'TIEMPO_REAL');
  assert.equal(cuerpoAlerta({ idDispositivo: 1, idSensor: 2, serial: 's', idTelemetria: 3, severidad: 'CRITICO' }).severidad_edge, 'CRITICO');
  assert.throws(() => cuerpoAlerta({ idDispositivo: 1, idSensor: 2, serial: 's', idTelemetria: 3, severidad: 'ALTA' }));
});
test('testigos sin RLS; una consulta fallida es no verificable (null), nunca 0', () => {
  assert.match(consultaTestigoDispositivo('QAAUTO-G102-1'), /FROM auditoria\.logs_dml .*'dispositivos_iot'/);
  assert.throws(() => consultaTestigoDispositivo("x' OR '1'='1"));
  assert.throws(() => consultaEstadosActuales([1, '2; DROP']));
  assert.equal(leerConteo({ status: 200, data: { data: [{ n: '0' }] } }), 0);
  assert.equal(leerConteo({ status: 400, data: { detail: 'permiso denegado' } }), null);
  assert.equal(leerConteo({ status: 200, data: { data: [] } }), null);
});
test('clasificación de aserciones por nombre', () => {
  const n = '[TC-M03-202][ASSERT][API-202-02][V:U200] x';
  assert.deepEqual([casoDeTexto(n), tipoDeTexto(n), idDeTexto(n), varianteDeTexto(n)], ['TC-M03-202', 'ASSERT', 'API-202-02', 'U200']);
  assert.equal(tipoDeTexto('[TC-M03-213][INFO][V:U200] y'), 'INFO');
  assert.equal(tipoDeTexto('sin etiqueta'), null);
});
test('veredicto: APROBADO solo con todo lo requerido; PRE invalida su unidad; INFO no decide', () => {
  const todas = Object.entries(REQUERIDAS).flatMap(([caso, ks]) => ks.map(k => ({ caso, tipo: 'ASSERT', id: k.split('@')[0], variante: k.split('@')[1], ok: true, evidencia: true })));
  const base = { casos: CASOS, requeridas: REQUERIDAS, estado: 'CONCLUIDA', rollback: true };
  assert.equal(veredictoCasos({ ...base, aserciones: [...todas, { caso: 'TC-M03-213', tipo: 'INFO', ok: false }] }).grupo, 'APROBADO');
  assert.equal(veredictoCasos({ ...base, rollback: false, aserciones: todas }).grupo, 'BLOQUEADO');
  const falla201 = todas.map(a => a.id === 'UI-201-03' ? { ...a, ok: false } : a);
  assert.deepEqual(veredictoCasos({ ...base, aserciones: falla201 }).casos, { 'TC-M03-201': 'RECHAZADO', 'TC-M03-202': 'APROBADO', 'TC-M03-213': 'APROBADO' });
  // La precondición de U51 falló: su ASSERT no puede rechazar; U50 no se ve afectada.
  const preU51 = [...falla201, { caso: 'TC-M03-201', tipo: 'PRE', variante: 'U51', ok: false }];
  assert.equal(veredictoCasos({ ...base, aserciones: preU51 }).casos['TC-M03-201'], 'BLOQUEADO');
  // Un hook de Cypress (PRE sin variante) invalida todo el caso.
  assert.equal(veredictoCasos({ ...base, aserciones: [...falla201, { caso: 'TC-M03-201', tipo: 'PRE', variante: null, ok: false }] }).casos['TC-M03-201'], 'BLOQUEADO');
  // Falta cobertura (la interfaz no se ejecutó): BLOQUEADO, nunca APROBADO.
  assert.equal(veredictoCasos({ ...base, aserciones: todas.filter(a => !a.id.startsWith('UI')) }).casos['TC-M03-202'], 'BLOQUEADO');
  // Una aserción sin etiqueta que falla es automatización: no rechaza.
  assert.equal(veredictoCasos({ ...base, aserciones: [...todas, { caso: 'TC-M03-213', tipo: null, ok: false, evidencia: true }] }).casos['TC-M03-213'], 'BLOQUEADO');
});
test('colección 201: 50 exactos, segmento siguiente con el restante y 422 para por_pagina=51', () => {
  const env = { run_id: 'R', id_u50: '10', id_u51: '11', ids_u50: JSON.stringify(rango(1, 50)), ids_u51: JSON.stringify(rango(101, 51)) };
  assert.ok(ok(correr('[TC-M03-201][V:U50] por_pagina=50 en la unidad con 50 sensores', { env, body: respuesta(rango(1, 50), 10) }).tests, 'API-201-02'));
  assert.ok(!ok(correr('[TC-M03-201][V:U50] por_pagina=50 en la unidad con 50 sensores', { env, body: respuesta(rango(1, 49), 10) }).tests, 'API-201-02'));
  const cv = {};
  assert.ok(ok(correr('[TC-M03-201][V:U51] por_pagina=50 en la unidad con 51 sensores (segmento 1)', { env, colVars: cv, body: respuesta(rango(101, 50), 11, 51) }).tests, 'API-201-03'));
  assert.ok(ok(correr('[TC-M03-201][V:U51] segmento 2 de la unidad con 51 sensores', { env, colVars: cv, body: respuesta([151], 11, 51) }).tests, 'API-201-04'));
  assert.ok(!ok(correr('[TC-M03-201][V:U51] segmento 2 de la unidad con 51 sensores', { env, colVars: cv, body: respuesta([150], 11, 51) }).tests, 'API-201-04'), 'duplicado y omisión');
  assert.ok(!ok(correr('[TC-M03-201][V:U51] por_pagina=50 en la unidad con 51 sensores (segmento 1)', { env, colVars: {}, body: respuesta(rango(101, 51), 11, 51) }).tests, 'API-201-03'), 'más de 50 en la vista');
  assert.ok(ok(correr('[TC-M03-201][V:U51] por_pagina=51 en la unidad con 51 sensores', { env, code: 422, body: { detail: [] } }).tests, 'API-201-05'));
  assert.ok(!ok(correr('[TC-M03-201][V:U51] por_pagina=51 en la unidad con 51 sensores', { env, code: 200, body: respuesta(rango(101, 51), 11) }).tests, 'API-201-05'));
});
function recorrer200(paginas) {
  const env = { run_id: 'R', id_u200: '12', pagina_u200: '1', ids_u200: JSON.stringify(rango(1, 200)) }, cv = {};
  let tests = [];
  for (let i = 0; i < 12; i++) {
    const r = correr('[TC-M03-202][V:U200] segmento de la unidad con 200 sensores', { env, colVars: cv, body: paginas(Number(env.pagina_u200)) });
    tests = tests.concat(r.tests);
    if (!r.siguiente) break;
  }
  return tests;
}
test('colección 202: recorre segmentos y exige 200 sin duplicados, omisiones ni ajenos', () => {
  const correcto = p => respuesta(rango(1 + (p - 1) * 50, p <= 4 ? 50 : 0), 12, 200);
  const t = recorrer200(correcto);
  assert.ok(['API-202-01', 'API-202-02', 'API-202-03'].every(id => ok(t, id)));
  assert.ok(!ok(recorrer200(p => respuesta(p <= 4 ? rango(1, 50) : [], 12)), 'API-202-02'), 'la API ignora la página');
  assert.ok(!ok(recorrer200(p => p === 1 ? { sensores: [...respuesta(rango(1, 50), 12).sensores.slice(1), { id_sensor: 999, id_infraestructura: 99 }] } : correcto(p)), 'API-202-03'), 'sensor ajeno');
  assert.ok(!ok(recorrer200(p => p === 1 ? respuesta(rango(1, 60), 12) : correcto(p)), 'API-202-01'), 'segmento con más de 50');
});
test('colección 213: ningún tamaño excesivo entrega más de 50 sensores; la respuesta queda registrada', () => {
  const env = { run_id: 'R', id_u200: '12' };
  for (const [t, id] of [[51, 'API-213-01'], [500, 'API-213-02'], [100000, 'API-213-03']]) {
    const nombre = `[TC-M03-213][V:U200] por_pagina=${t} en la unidad con 200 sensores`;
    assert.ok(ok(correr(nombre, { env, code: 422, body: { detail: [] } }).tests, id));
    assert.ok(!ok(correr(nombre, { env, code: 200, body: respuesta(rango(1, 51), 12) }).tests, id));
    assert.ok(correr(nombre, { env, code: 422, body: { detail: [] } }).tests.some(x => /\[INFO\].*HTTP 422/.test(x.n)));
  }
});
test('barrera de la colección: sin autorización vigente no se envía ninguna petición', () => {
  const pre = col.event.find(e => e.listen === 'prerequest').script.exec.join('\n');
  let saltada = false;
  const pm = v => ({ environment: { get: k => v[k] }, execution: { skipRequest: () => { saltada = true; } } });
  assert.throws(() => new Function('pm', pre)(pm({ autorizado_run: 'NO', run_id: 'R', base_url: 'https://x' })), /BLOQUEO_G102/);
  assert.equal(saltada, true);
  assert.throws(() => new Function('pm', pre)(pm({ autorizado_run: 'SI', run_id: 'R', base_url: 'http://127.0.0.1:9' })), /BLOQUEO_G102/);
  assert.doesNotThrow(() => new Function('pm', pre)(pm({ autorizado_run: 'SI', run_id: 'R', base_url: 'https://api.test.example' })));
});
test('la evidencia redacta secretos, seriales y JWT', () => {
  const limpiar = redactor(['secreto-sandbox', 'QAAUTO-G102-1-U50']);
  const jwt = ['eyJ', 'hbGciOiJIUzI1NiJ9', '.', 'eyJzdWIiOiIxIn0', '.', 'abcdefghijk'].join('');
  assert.equal(limpiar(`x secreto-sandbox QAAUTO-G102-1-U50 ${jwt}`), 'x [REDACTADO] [REDACTADO] [JWT]');
});
test('barrera propia de Cypress: el before del spec se detiene sin autorización ni API HTTPS, antes de usar cy', () => {
  const src = fs.readFileSync(new URL('./tc_m03_g102.cy.js', import.meta.url), 'utf8');
  for (const valores of [{}, { AUTORIZADO_RUN: 'NO', RUN_ID: 'R', API_BASE: 'https://api.test.example' }, { AUTORIZADO_RUN: 'SI', RUN_ID: 'R', API_BASE: 'http://127.0.0.1:9' }]) {
    const ganchos = [];
    const cy = new Proxy({}, { get: () => () => { throw Error('cy usado antes de la barrera'); } });
    const g = { Cypress: { env: k => valores[k] }, describe: (n, f) => f(), before: f => ganchos.push(f), it: () => {}, cy, expect: () => {} };
    new Function(...Object.keys(g), src)(...Object.values(g));
    assert.equal(ganchos.length, 1);
    assert.throws(() => ganchos[0](), /BLOQUEO_G102/);
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
