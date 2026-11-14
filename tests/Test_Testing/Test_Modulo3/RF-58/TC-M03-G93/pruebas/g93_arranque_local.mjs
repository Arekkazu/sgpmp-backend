#!/usr/bin/env node
// Arranque real y fallo deliberado, solo en os.tmpdir() y sin destinos de red.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { invocarCypressLocal } from '../g93.mjs';

const temporal = fs.mkdtempSync(path.join(os.tmpdir(), 'g93-cypress-local-'));
const env = Object.fromEntries(Object.entries(process.env)
  .filter(([clave]) => !/^CYPRESS_|^QA_|^SIGAB_/i.test(clave)));
const resultados = [];
try {
  const casos = [
    ['arranque', "it('arranque local', () => { cy.document().then(d => { d.body.innerHTML = '<h1>G93 local</h1>'; }); cy.contains('G93 local'); cy.screenshot('arranque-local'); });", true],
    ['fallo', "it('fallo deliberado local', () => { cy.document(); expect(1).to.equal(2); });", false],
  ];
  for (const [nombre, contenido, correcto] of casos) {
    const proyecto = path.join(temporal, nombre);
    const carpeta = path.join(proyecto, 'artefactos');
    fs.mkdirSync(proyecto);
    const spec = path.join(proyecto, `${nombre}.cy.js`);
    fs.writeFileSync(spec, contenido);
    const { proceso, diagnostico } = invocarCypressLocal({ proyecto, spec, carpeta,
      env, prefijo: nombre });
    const salida = fs.readFileSync(path.join(carpeta, `${nombre}.diagnostico.log`), 'utf8');
    const capturas = fs.existsSync(carpeta) ? fs.readdirSync(carpeta, { recursive: true })
      .filter(x => String(x).endsWith('.png')) : [];
    const ejecutoUna = /1 passing|1 failing/i.test(salida);
    resultados.push({ escenario: nombre, version: diagnostico.version_cypress,
      navegador: diagnostico.navegador, codigo_salida: diagnostico.codigo_salida,
      error_spawn: diagnostico.error_spawn?.codigo ?? null, pruebas_ejecutadas: ejecutoUna ? 1 : 0,
      estado_tecnico: correcto && proceso.status === 0 && ejecutoUna && capturas.length > 0
        ? 'OK' : 'ERROR_QA',
      diagnostico: path.join(carpeta, `${nombre}.diagnostico.json`),
      log: path.join(carpeta, `${nombre}.diagnostico.log`),
      capturas: capturas.map(x => path.join(carpeta, String(x))) });
    if (proceso.error?.code === 'EPERM') throw new Error('CYPRESS_EPERM_SANDBOX');
    assert.equal(ejecutoUna, true, `${nombre}: Cypress no ejecutó una prueba; revisar diagnóstico temporal`);
    if (correcto) {
      assert.equal(proceso.status, 0, 'El arranque local falló');
      assert.ok(capturas.length > 0, 'El arranque no dejó captura real');
    } else {
      assert.notEqual(proceso.status, 0, 'El fallo deliberado no se propagó');
      assert.match(salida, /expected 1 to equal 2|1 to equal 2/i);
    }
  }
  console.log(JSON.stringify({ valido: true, resultados, temporal_eliminado_al_final: true }, null, 2));
} catch (error) {
  console.log(JSON.stringify({ valido: false, motivo: error.message, resultados,
    comando_para_qa: 'node pruebas/g93_arranque_local.mjs',
    temporal_eliminado_al_final: true }, null, 2));
  process.exitCode = 2;
} finally {
  fs.rmSync(temporal, { recursive: true, force: true });
}
