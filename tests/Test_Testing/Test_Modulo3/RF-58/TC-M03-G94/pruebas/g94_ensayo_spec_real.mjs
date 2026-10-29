import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { iniciarLocal } from './g94_arranque_local.mjs';
import { evaluarResultadoCypress } from '../lib/g94_escenario.mjs';

const DIR = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const require = createRequire(import.meta.url);
const cli = path.join(path.dirname(require.resolve('cypress/package.json', { paths: [DIR] })), 'bin', 'cypress');

async function ensayo(modo) {
  const temp = fs.mkdtempSync(path.join(os.tmpdir(), `g94-spec-${modo}-`));
  assert.ok(path.resolve(temp).startsWith(path.resolve(os.tmpdir()) + path.sep));
  const { servidor, base } = await iniciarLocal(modo);
  try {
    const run = `ENSAYO-G94-${modo.toUpperCase()}`;
    const env = { ...process.env, CYPRESS_AUTORIZADO_RUN: 'SI', CYPRESS_ENSAYO_LOCAL: 'SI',
      CYPRESS_API_BASE: `${base}/api-sgpmp-test`, CYPRESS_FRONT_BASE: `${base}/sigab-test`,
      CYPRESS_RUN_ID: run, CYPRESS_SANDBOX_SECRET: 'SINTETICO',
      CYPRESS_REFRESH_COOKIE: 'SINTETICO', CYPRESS_ARTIFACTS_DIR: temp };
    const args = [cli, 'run', '--project', DIR, '--spec', path.join(DIR, 'g94.cy.js'),
      '--config-file', path.join(DIR, 'g94.cypress.config.cjs'),
      '--config', `screenshotsFolder=${temp},videosFolder=${temp},downloadsFolder=${temp}`,
      '--browser', 'chrome', '--headless'];
    const { codigo, salida } = await new Promise((resolve, reject) => {
      const p = spawn(process.execPath, args, { cwd: DIR, env, shell: false,
        stdio: ['ignore', 'pipe', 'pipe'] });
      let log = '';
      for (const flujo of [p.stdout, p.stderr]) flujo.on('data', x => { log = (log + x.toString()).slice(-4000); });
      p.once('error', reject); p.once('close', code => resolve({ codigo: code, salida: log }));
    });
    const archivo = path.join(temp, 'UI-185-01.json');
    assert.ok(fs.existsSync(archivo), `Acta ausente en ensayo ${modo}; Cypress ${codigo}; ${salida}`);
    const acta = JSON.parse(fs.readFileSync(archivo, 'utf8'));
    const resumenArchivo = path.join(temp, 'UI-185-01-cypress.json');
    assert.ok(fs.existsSync(resumenArchivo), `Conteo Cypress ausente en ensayo ${modo}; Cypress ${codigo}; ${salida}`);
    const resumen = JSON.parse(fs.readFileSync(resumenArchivo, 'utf8'));
    const esperado = { ok: 'APROBADO', texto: 'RECHAZADO', sesion500: 'BLOQUEADO',
      lento: 'NO_CONCLUYENTE', sin_eco_dashboard: 'NO_CONCLUYENTE' }[modo];
    assert.equal(evaluarResultadoCypress({ acta, rel: 'cypress/UI-185-01.json',
      resumen, proceso: codigo, error: null }).estado, esperado,
    `Clasificación errónea en ${modo}; Cypress ${codigo}; ${salida}`);
    assert.equal(acta.estado, esperado, `Acta errónea en ${modo}; Cypress ${codigo}; ${salida}`);
    assert.deepEqual(acta.rutas_fuera_sandbox,
      ['POST /sesiones/refresh', 'GET /usuarios/me', 'GET /sesiones/me/permisos']);
    assert.equal(acta.fincas_perfil, modo === 'sesion500' ? null : 2);
    for (const p of acta.peticiones) {
      assert.equal(p.en_sandbox, !acta.rutas_fuera_sandbox.includes(`${p.metodo} ${p.ruta}`));
      if (p.http != null && modo !== 'sin_eco_dashboard') assert.equal(p.eco_run, p.en_sandbox);
    }
    if (!['sesion500', 'lento'].includes(modo)) {
      for (const ruta of ['/configuracion/interfaz/contexto', '/iot/monitoreo/dashboard'])
        assert.ok(acta.peticiones.some(p => p.ruta === ruta && p.en_sandbox), ruta);
    }
    if (modo === 'sin_eco_dashboard') assert.equal(acta.dashboard?.eco_run, false);
    assert.ok(fs.readdirSync(temp, { recursive: true }).some(x => /UI-185-01.*\.png$/i.test(x)),
      `PNG ausente en ${modo}; Cypress ${codigo}; ${salida}`);
    assert.equal(acta.captura, true, `Captura no confirmada en ${modo}; Cypress ${codigo}; ${salida}`);
    console.log(`ENSAYO ${modo}: ${esperado}`);
  } finally {
    await new Promise(resolve => servidor.close(resolve));
    assert.ok(path.resolve(temp).startsWith(path.resolve(os.tmpdir()) + path.sep));
    fs.rmSync(temp, { recursive: true, force: true });
  }
}

for (const modo of ['ok', 'texto', 'sesion500', 'lento', 'sin_eco_dashboard']) await ensayo(modo);
