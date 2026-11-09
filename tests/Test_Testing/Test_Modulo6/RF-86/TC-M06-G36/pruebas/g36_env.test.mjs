import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import http from 'node:http';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { leerEnv, preflight, validarColeccionPermisos, sanear } from '../g36.mjs';
import { PRESUPUESTO } from '../lib/g36_core.mjs';
import { ejecutarNewman } from './newman_hijo.mjs';

const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'g36-env-'));
try {
  const col = JSON.parse(fs.readFileSync(new URL('../G36.postman_collection.json', import.meta.url), 'utf8'));
  assert.equal(PRESUPUESTO.solicitudes_totales, 80);
  assert.equal(PRESUPUESTO.duracion_segundos, 900);
  assert.equal(validarColeccionPermisos(col), true);
  for (let i = 0; i < col.item.length; i++) {
    const cambio = structuredClone(col);
    if (i < 2) cambio.item[i].request.header.find(h => h.key === 'Authorization').value = 'Bearer {{actor_incorrecto}}';
    else cambio.item[i].request.header.push({ key: 'Authorization', value: 'Bearer {{token}}' });
    assert.equal(validarColeccionPermisos(cambio), false, `Actor incorrecto en ${col.item[i].name}`);
  }
  const archivo = path.join(tmp, 'falso.env');
  fs.writeFileSync(archivo, "QA_ADMIN_EMAIL='archivo@ejemplo.invalid'\nQA_AUTORIZADO=SI\nSIGAB_API_TEST_BASE=http://127.0.0.1:1234\n");
  const e = leerEnv({ QA_ADMIN_EMAIL: 'proceso@ejemplo.invalid' }, archivo);
  assert.equal(e.QA_ADMIN_EMAIL, 'proceso@ejemplo.invalid');
  assert.equal(e.QA_AUTORIZADO, undefined);
  assert.equal(e.SIGAB_API_TEST_BASE, 'http://127.0.0.1:1234');
  assert.equal(preflight({ ensayo: true, runId: 'RUN-G36-V1-20261108-000000' }, e, 'falso').ok, false);
  const simulado = await ejecutarNewman({ coleccion: {}, environment: {}, timeout: 30000 }, {
    run(opciones, cb) {
      assert.match(opciones.reporter.json.export, /g36-newman-/);
      fs.writeFileSync(opciones.reporter.json.export, '{}');
      cb(null, { run: { executions: [{ item: { name: 'sonda' }, response: { code: 200, responseTime: 4 }, assertions: [] }], stats: {} } });
    },
  });
  assert.equal(simulado.fallido, false);
  assert.equal(simulado.solicitudes[0].http, 200);
  assert.equal(fs.readdirSync(os.tmpdir()).filter(x => x.startsWith('g36-newman-')).length, 0);
  const servidor = http.createServer((_, res) => { res.writeHead(200, { 'Content-Type': 'application/json' }); res.end('{"ok":true}'); });
  await new Promise(resolve => servidor.listen(0, '127.0.0.1', resolve));
  try {
    const base = `http://127.0.0.1:${servidor.address().port}`;
    const entrada = { coleccion: { info: { name: 'Sonda G36',
      schema: 'https://schema.getpostman.com/json/collection/v2.1.0/collection.json' },
      item: [{ name: 'sonda', request: { method: 'GET', url: base + '/ping' },
        event: [{ listen: 'test', script: { type: 'text/javascript', exec: [
          "pm.test('HTTP 200', () => pm.expect(pm.response.code).to.equal(200));" ] } }] }] },
      environment: { values: [] }, timeout: 30000 };
    const directo = await ejecutarNewman(entrada);
    assert.equal(directo.fallido, false);
    assert.equal(directo.reporte_exportado, true);
    assert.equal(directo.solicitudes[0].http, 200);
    let hijo;
    try { hijo = spawn(process.execPath, [path.join(path.dirname(fileURLToPath(import.meta.url)), 'newman_hijo.mjs')],
      { stdio: ['pipe', 'pipe', 'pipe'], windowsHide: true }); }
    catch (error) { if (error.code !== 'EPERM') throw error; console.log('OK newman_hijo: no ejecutable en este entorno (EPERM)'); }
    if (hijo) {
      let salida = '', stderr = '';
      hijo.stdout.on('data', x => { salida += x.toString(); });
      hijo.stderr.on('data', x => { stderr += x.toString(); });
      hijo.stdin.end(JSON.stringify(entrada));
      const codigo = await new Promise(resolve => hijo.on('close', resolve));
      assert.equal(codigo, 0, `newman_hijo terminó ${codigo}: ${sanear(stderr)}`);
      assert.equal(JSON.parse(salida).solicitudes[0].http, 200);
      console.log('OK newman_hijo: process.execPath, 1 lectura loopback HTTP 200');
    }
  } finally { await new Promise(resolve => servidor.close(resolve)); }
  assert.equal(fs.readdirSync(os.tmpdir()).filter(x => x.startsWith('g36-newman-')).length, 0);
  console.log('OK G36 entorno: leerEnv, actores y Newman local');
} finally { fs.rmSync(tmp, { recursive: true, force: true }); }
