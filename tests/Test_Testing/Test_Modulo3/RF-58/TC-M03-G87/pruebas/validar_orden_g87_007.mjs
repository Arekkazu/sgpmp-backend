import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import { estadoGrupoG87, uiHabilitada } from '../lib/g87_preparacion.mjs';

const leer = (nombre) => fs.readFileSync(new URL(nombre, import.meta.url), 'utf8');

test('S1 bloqueado y S2 válido: Newman prepara y consulta 178; Cypress registra solo 178; grupo parcial', () => {
  const coleccion = JSON.parse(leer('../G87.postman_collection.json'));
  const ejecutadas = [];
  for (const item of coleccion.item) {
    let omitida = false;
    const pm = { environment: { get: (k) => ({ s1_ejecutar: 'NO' })[k] }, execution: { skipRequest: () => { omitida = true; } } };
    for (const evento of item.event ?? []) if (evento.listen === 'prerequest') {
      vm.runInNewContext(`(function () { ${evento.script.exec.join('\n')} })()`, { pm });
      if (omitida) break;
    }
    if (!omitida) ejecutadas.push(item.name);
  }
  assert.deepEqual(ejecutadas, [
    'SETUP Reasignar S2 al área del escenario',
    '178 Lectura 1 de S2 (sin calibración)',
    '178 Lectura 2 de S2 (sin calibración)',
    'Dashboard del Productor', 'Dashboard del Ingeniero de Campo',
  ]);
  for (const item of coleccion.item.filter((x) => x.name.startsWith('Dashboard'))) {
    const lineas = item.event.find((x) => x.listen === 'test').script.exec;
    assert.ok(lineas.some((x) => x.includes('[TC-M03-178]')));
    assert.ok(lineas.filter((x) => /\[TC-M03-(168|177)\]/.test(x)).every((x) => x.startsWith("if (pm.environment.get('s1_ejecutar') === 'SI')")));
  }
  const comprobaciones = [
    ...['TC-M03-168', 'TC-M03-177'].map((caso) => ({ caso, tipo: 'PRE', fuente: 'API', id: `PRE-${caso.slice(-3)}-DATOS`, ok: false })),
    ...['PRE-178-01', 'PRE-178-01', 'PRE-178-02', 'PRE-178-03'].map((id) => ({ caso: 'TC-M03-178', tipo: 'PRE', fuente: 'API', id, ok: true })),
  ];
  const ui177 = uiHabilitada(comprobaciones, 'TC-M03-177', ['PRE-177-01', 'PRE-177-02', 'PRE-177-03'], true, false);
  const ui178 = uiHabilitada(comprobaciones, 'TC-M03-178', ['PRE-178-01', 'PRE-178-02', 'PRE-178-03'], true, true);
  assert.equal(ui177, false);
  assert.equal(ui178, true);
  const titulos = [];
  vm.runInNewContext(leer('../g87.cy.js'), {
    Cypress: { env: (k) => ({ UI_177: ui177, UI_178: ui178 })[k], config: () => 'https://front.test' },
    describe: (_n, o, f) => (typeof o === 'function' ? o() : f()), it: (n) => titulos.push(n),
    before: () => {}, beforeEach: () => {}, Promise,
  });
  assert.equal(titulos.some((x) => x.includes('[TC-M03-177]')), false);
  assert.equal(titulos.filter((x) => x.includes('[TC-M03-178]')).length, 7);
  assert.equal(estadoGrupoG87({
    'TC-M03-168': { estado: 'BLOQUEADO' }, 'TC-M03-177': { estado: 'BLOQUEADO' },
    'TC-M03-178': { estado: 'APROBADO' },
  }), 'PARCIAL');
  const runner = leer('../g87.mjs');
  assert.match(runner, /r\.estado = bloqueoS1 \? 'PARCIAL' : 'CONCLUIDA'/);
  assert.match(runner, /obtenido: `NO_EJECUTADA: \$\{motivosUi\[caso\]\}`/);
});
