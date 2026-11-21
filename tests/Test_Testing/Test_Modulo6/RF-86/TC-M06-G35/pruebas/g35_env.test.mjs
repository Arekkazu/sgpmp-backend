import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import http from 'node:http';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { leerEnv, preflight, sanear, validarColeccionPermisos } from '../g35.mjs';
import { PRESUPUESTO } from '../lib/g35_core.mjs';
import { ejecutarNewman } from './newman_hijo.mjs';

const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'g35-env-'));
try {
  const coleccion = JSON.parse(fs.readFileSync(new URL('../G35.postman_collection.json', import.meta.url), 'utf8'));
  assert.equal(PRESUPUESTO.solicitudes_totales, 80);
  assert.equal(PRESUPUESTO.duracion_segundos, 900);
  assert.equal(validarColeccionPermisos(coleccion), true);
  const permisos = [
    ['valoracion_activos:Leer', 'token'],
    ['activos_biologicos:Leer', 'token_m02'],
    ['valoracion_activos:Leer', 'token'],
  ];
  for (const [i, [permiso, actor]] of permisos.entries()) {
    const item = coleccion.item[i];
    assert.equal(item.request.method, 'GET', `${item.name}: ${permiso}`);
    assert.equal(item.request.header.find(h => h.key === 'Authorization').value, `Bearer {{${actor}}}`,
      `${item.name}: ${permiso}`);
    const alterada = structuredClone(coleccion);
    alterada.item[i].request.header.find(h => h.key === 'Authorization').value = 'Bearer {{actor_incorrecto}}';
    assert.equal(validarColeccionPermisos(alterada), false, `${item.name}: debe detectar actor incorrecto`);
  }
  const archivo = path.join(tmp, 'falso.env');
  fs.writeFileSync(archivo, "QA_ADMIN_EMAIL='archivo@ejemplo.invalid'\nQA_AUTORIZADO=SI\nSIGAB_API_TEST_BASE=http://127.0.0.1:1234\n");
  const e = leerEnv({ QA_ADMIN_EMAIL: 'proceso@ejemplo.invalid' }, archivo);
  assert.equal(e.QA_ADMIN_EMAIL, 'proceso@ejemplo.invalid');
  assert.equal(e.QA_AUTORIZADO, undefined);
  assert.equal(e.SIGAB_API_TEST_BASE, 'http://127.0.0.1:1234');
  assert.equal(preflight({ ensayo: true, runId: 'RUN-G35-V1-20261108-000000' }, e, 'falso').ok, false);
  const respuesta = await ejecutarNewman({ coleccion: {}, environment: {}, timeout: 30000 }, {
    run(opciones, cb) {
      assert.match(opciones.reporter.json.export, /g35-newman-/);
      fs.writeFileSync(opciones.reporter.json.export, '{}');
      cb(null, { run: { executions: [{ item: { name: 'sonda' }, response: { code: 200, responseTime: 4 }, assertions: [] }], stats: {} } });
    },
  });
  assert.equal(respuesta.fallido, false);
  assert.equal(respuesta.solicitudes[0].http, 200);
  assert.equal(fs.readdirSync(os.tmpdir()).filter(x => x.startsWith('g35-newman-')).length, 0);
  const servidor = http.createServer((_, res) => { res.writeHead(200, { 'Content-Type': 'application/json' }); res.end('{"ok":true}'); });
  await new Promise(resolve => servidor.listen(0, '127.0.0.1', resolve));
  try {
    const base = `http://127.0.0.1:${servidor.address().port}`;
    const entrada = { coleccion: { info: { name: 'Sonda G35',
      schema: 'https://schema.getpostman.com/json/collection/v2.1.0/collection.json' },
      item: [{ name: 'sonda', request: { method: 'GET', url: base + '/ping' },
        event: [{ listen: 'test', script: { type: 'text/javascript', exec: [
          "pm.test('HTTP 200', () => pm.expect(pm.response.code).to.equal(200));" ] } }] }] },
      environment: { values: [] }, timeout: 30000 };
    const directo = await ejecutarNewman(entrada);
    assert.equal(directo.fallido, false);
    assert.equal(directo.reporte_exportado, true);
    assert.equal(directo.solicitudes.length, 1);
    assert.equal(directo.solicitudes[0].http, 200);
    assert.equal(directo.solicitudes[0].aserciones[0].error, null);
    let hijo;
    try { hijo = spawn(process.execPath, [path.join(path.dirname(fileURLToPath(import.meta.url)), 'newman_hijo.mjs')],
      { stdio: ['pipe', 'pipe', 'pipe'], windowsHide: true }); }
    catch (e) { if (e.code !== 'EPERM') throw e; console.log('Sonda del proceso hijo Newman: EPERM del entorno local'); }
    if (hijo) {
      let salida = '', stderr = '';
      hijo.stdout.on('data', x => { salida += x.toString(); });
      hijo.stderr.on('data', x => { stderr += x.toString(); });
      hijo.stdin.end(JSON.stringify(entrada));
      const codigo = await new Promise(resolve => hijo.on('close', resolve));
      assert.equal(codigo, 0, `newman_hijo terminó con código ${codigo}: ${sanear(stderr)}`);
      const sonda = JSON.parse(salida); assert.equal(sonda.solicitudes[0].http, 200);
    }
  } finally { await new Promise(resolve => servidor.close(resolve)); }
  assert.equal(fs.readdirSync(os.tmpdir()).filter(x => x.startsWith('g35-newman-')).length, 0);
  console.log('OK G35 entorno: leerEnv y prueba del hijo Newman');
} finally { fs.rmSync(tmp, { recursive: true, force: true }); }
