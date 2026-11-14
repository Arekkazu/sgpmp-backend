// ORD-G87-005: decisiones locales, sin acceso a TEST ni artefactos de RUN.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import { valoresS1, uiHabilitada, indicadorCalibracion } from '../lib/g87_preparacion.mjs';

test('T1: S1 usa el umbral del dispositivo y evita ERROR_SENSOR', () => {
  assert.deepEqual(valoresS1({ id: 8, min: 15, max: 30 }, [-50, 100]),
    { v_a1: 23, v_a2: 24, v_a3: 25, v_fuera: 31 });
  assert.deepEqual(valoresS1({ id: 9, min: 24.5, max: 100 }, [-50, 100]),
    { v_a1: 24.5, v_a2: 24.5, v_a3: 25, v_fuera: 23.5 });
  assert.equal(valoresS1({ id: 12, min: 24, max: 25.2 }, [20, 25.5]).v_fuera, 25.5);
  assert.throws(() => valoresS1({ id: 10, min: 26, max: 30 }, [-50, 100]), /BLOQUEO_DATOS.*25/);
  assert.throws(() => valoresS1({ id: 11, min: -50, max: 100 }, [-50, 100]), /BLOQUEO_DATOS.*FUERA_DE_RANGO/);
  const runner = fs.readFileSync(new URL('../g87.mjs', import.meta.url), 'utf8');
  const lecturas = [
    '/configuracion/dispositivos-iot/${s1.dev}',
    '/configuracion/infraestructuras/${idInfraDev}',
    '/configuracion/umbrales?id_especie=${idEspecieDev}',
  ];
  const apertura = runner.indexOf("const disp = await api('DELETE'");
  assert.ok(lecturas.every((ruta) => runner.indexOf(ruta) > 0 && runner.indexOf(ruta) < apertura));
});

test('T2: API-178-06 acepta un indicador real y rechaza el estado válido previo', () => {
  const coleccion = JSON.parse(fs.readFileSync(new URL('../G87.postman_collection.json', import.meta.url), 'utf8'));
  const ingeniero = coleccion.item.find((x) => x.name === 'Dashboard del Ingeniero de Campo');
  const script = ingeniero.event[0].script.exec;
  const definicion = script.find((x) => x.startsWith('const indicaCalibracion ='));
  assert.ok(definicion);
  const indica = (s2) => vm.runInNewContext(`${definicion}\nindicaCalibracion(s2)`, { s2 });
  assert.equal(indica({ estado_calidad: 'ERROR_CALIBRACION' }), true);
  assert.equal(indica({ estado_calidad: 'LECTURA_VALIDA', diagnostico: 'Requiere calibración' }), true);
  assert.equal(indica({ lectura_reciente: { condicion: 'ERROR_CALIBRACION' } }), true);
  assert.equal(indica({ estado_calidad: 'LECTURA_VALIDA', nombre: 'ERROR_CALIBRACION' }), false);
  assert.equal(indica({ estado_calidad: 'LECTURA_VALIDA', ultimo_valor: 25 }), false);
  assert.deepEqual(indicadorCalibracion({ lectura_reciente: { condicion: 'ERROR_CALIBRACION' } }),
    { campo: 'lectura_reciente.condicion', valor: 'ERROR_CALIBRACION' });
  assert.equal(indicadorCalibracion({ estado_calidad: 'LECTURA_VALIDA', ultimo_valor: 25 }), null);
  assert.match(script.find((x) => x.includes('API-178-06')), /indicaCalibracion\(s2\)/);
});

test('T3: UI 178 puede ejecutarse aunque PRE-177 falle', () => {
  const cs = [
    ...['PRE-177-01', 'PRE-177-02', 'PRE-177-03'].map((id) => ({ caso: 'TC-M03-177', tipo: 'PRE', fuente: 'API', id, ok: id !== 'PRE-177-02' })),
    ...['PRE-178-01', 'PRE-178-01', 'PRE-178-02', 'PRE-178-03'].map((id) => ({ caso: 'TC-M03-178', tipo: 'PRE', fuente: 'API', id, ok: true })),
    { caso: 'TC-M03-177', tipo: 'SETUP', fuente: 'API', id: 'SETUP', ok: false },
  ];
  assert.equal(uiHabilitada(cs, 'TC-M03-177', ['PRE-177-01', 'PRE-177-02', 'PRE-177-03'], true, true), false);
  assert.equal(uiHabilitada(cs, 'TC-M03-178', ['PRE-178-01', 'PRE-178-02', 'PRE-178-03'], true, true), true);
  assert.equal(uiHabilitada(cs, 'TC-M03-178', ['PRE-178-01', 'PRE-178-02', 'PRE-178-03'], false, true), false);
  const spec = fs.readFileSync(new URL('../g87.cy.js', import.meta.url), 'utf8');
  const titulos = [];
  const contexto = { Cypress: { env: (k) => ({ UI_177: false, UI_178_PROD: true, UI_178_ENG: true })[k], config: () => 'https://front.test' },
    describe: (_n, o, f) => (typeof o === 'function' ? o() : f()), it: (n) => titulos.push(n), before: () => {}, beforeEach: () => {}, Promise };
  vm.runInNewContext(spec, contexto);
  assert.equal(titulos.some((x) => x.includes('[TC-M03-177]')), false);
  assert.equal(titulos.filter((x) => x.includes('[TC-M03-178]')).length, 7);
  const runner = fs.readFileSync(new URL('../g87.mjs', import.meta.url), 'utf8');
  assert.match(runner, /const contexto = `\$\{s\[1\]\} \$\{peticion \?\? ''\}`/);
});
