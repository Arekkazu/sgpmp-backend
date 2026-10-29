import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import { CAPACIDADES, CASO, PRESUPUESTO, evaluarPanel, hayAlertas } from '../lib/g98_escenario.mjs';
import { comprobar, evaluarNewman, fallosNewman, esOficial } from '../g98.mjs';
import { clasificarRegistro, validarObligatorias } from './registro_qa.mjs';

const alerta = severidad => ({ tipo_alerta: 'UMBRAL', tipo_variable: 'TEMPERATURA_AMBIENTAL',
  tiempo_transcurrido: '5 min', id_activo_biologico: 42, severidad });
const panel = xs => ({ total_alertas_activas: xs.length, alertas_activas: xs });
test('oráculo: estructura, escala RF-57 y equivalentes de la matriz', () => {
  assert.equal(evaluarPanel(panel(['CRITICO','MODERADO','LEVE'].map(alerta))).estado, 'APROBADO');
  assert.equal(evaluarPanel({ panel_alertas: { total_alertas: 3, alertas: ['CRITICO','ALTA','MEDIA'].map(alerta) } }).estado, 'APROBADO');
  assert.equal(evaluarPanel(panel(['LEVE','CRITICO'].map(alerta))).estado, 'RECHAZADO');
  assert.equal(evaluarPanel(panel([alerta('CRITICO')])).estado, 'BLOQUEADO');
  assert.equal(evaluarPanel(panel(['CRITICO','CRITICA'].map(alerta))).estado, 'BLOQUEADO');
  assert.equal(evaluarPanel({ total_alertas_activas: 2, alertas_activas: [] }).estado, 'RECHAZADO');
  assert.equal(evaluarPanel({ total: 1, resumen_unidades: [{ alertas_activas_count: 1 }], sensores: [{ id_alerta: 1 }] }).estado, 'RECHAZADO');
  assert.equal(evaluarPanel(panel([{ ...alerta('CRITICO'), tiempo_transcurrido: null }, alerta('LEVE')])).estado, 'RECHAZADO');
  assert.equal(hayAlertas({ resumen_unidades: [{ alertas_activas_count: 1 }] }), true);
});
test('clasificación Newman distingue ASSERT funcional, script, 5xx y transporte', () => {
  const base = { http: 200, eco: true, panel: evaluarPanel({ sensores: [], resumen_unidades: [] }), alertas_detectadas: false };
  const fallo = (name, testName, item = 'API-191-01') => ({ error: { name, test: testName, message: 'simulado' }, source: { name: item } });
  const asercion = fallosNewman({ run: { failures: [fallo('AssertionError','[TC-M03-191][ASSERT][API-191-01] panel')] } });
  assert.equal(evaluarNewman({ paginas: [base], fallos: asercion, artefactos: ['x'], proceso: {} }).datos.estado, 'RECHAZADO');
  assert.deepEqual(evaluarNewman({ paginas: [base], fallos: asercion, artefactos: ['x'], proceso: {} }).problemasTecnicos, []);
  const script = fallosNewman({ run: { failures: [fallo('TypeError','', 'API-191-01')] } });
  assert.deepEqual(evaluarNewman({ paginas: [base], fallos: script, artefactos: ['x'], proceso: {} }).problemasTecnicos, ['NEWMAN_ERROR_SCRIPT_O_TRANSPORTE']);
  assert.equal(evaluarNewman({ paginas: [{ http: 503, eco: true }], fallos: [], artefactos: ['x'], proceso: {} }).datos.estado, 'BLOQUEADO');
  assert.equal(evaluarNewman({ paginas: [], fallos: [], artefactos: ['x'], proceso: {} }).datos.estado, 'NO_CONCLUYENTE');
});
test('registro QA admite RECHAZADO oficial sin UI y exige evidencias/cierre', () => {
  const presentes = new Set(['TC-M03-G98_resultado.md','resultado.json','newman/newman-G98.json','newman/newman-G98.html']);
  const c = { runId: 'RUN-G98-V1-20261026-120000', version: 1 };
  const base = { run_id: c.runId, version: 1, oficial: true, consume_version: true,
    cierre: { run: { cierre_http: 200 }, rollback: { verificado: true } },
    casos: { [CASO]: { estado: 'RECHAZADO' } },
    comprobaciones: [{ caso: CASO, fuente: 'API', id: 'API-191-01', tipo: 'ASSERT', estado: 'RECHAZADO' }],
    cypress: { total_pruebas: 0 }, evidencias: [...presentes] };
  assert.deepEqual(CAPACIDADES.comprobaciones_obligatorias, { [CASO]: { API: ['API-191-01'] } });
  assert.equal(clasificarRegistro(CAPACIDADES, base, presentes, c), true);
  assert.equal(clasificarRegistro(CAPACIDADES, { ...base, evidencias: ['../fuera'] }, presentes, c), false);
  assert.equal(clasificarRegistro(CAPACIDADES, { ...base, cierre: { run: { cierre_http: 500 }, rollback: { verificado: true } } }, presentes, c), false);
  assert.equal(clasificarRegistro(CAPACIDADES, { ...base, comprobaciones: [] }, presentes, c), false);
  assert.equal(esOficial('RECHAZADO', { cierre: base.cierre, problemas_tecnicos: [] }, true), true);
  assert.throws(() => validarObligatorias({ ...CAPACIDADES, comprobaciones_obligatorias: { [CASO]: { API: ['API-191-01'], UI: [] } } }));
});
test('colección única GET, presupuesto y sintaxis', () => {
  const col = JSON.parse(fs.readFileSync(new URL('../G98.postman_collection.json', import.meta.url), 'utf8'));
  assert.equal(col.item.length, 1);
  assert.equal(col.item[0].request.method, 'GET');
  for (const e of col.item[0].event) new vm.Script(e.script.exec.join('\n'));
  assert.equal(PRESUPUESTO.solicitudes_en_run, PRESUPUESTO.lecturas_descubrimiento + PRESUPUESTO.paginas_dashboard);
  assert.doesNotMatch(JSON.stringify(col), /\/test-control\/query|POST|DELETE/);
  assert.equal(comprobar(), 0);
});
test('script Newman marca ausencia y orden como ASSERT sin confundirlos con transporte', () => {
  const col = JSON.parse(fs.readFileSync(new URL('../G98.postman_collection.json', import.meta.url), 'utf8'));
  const codigo = col.item[0].event.find(e => e.listen === 'test').script.exec.join('\n');
  const evaluar = body => {
    const vars = new Map(Object.entries({ run_id: 'RUN-LOCAL', unidades: '[1,268]', indice: '0', pagina: '1',
      por_pagina: '50', paginas_usadas: '0', limite_paginas: '12' }));
    let fallos = 0, siguiente;
    const expect = valor => ({ to: { eql: esperado => { if (valor !== esperado) throw Error('ASSERT'); } } });
    const pm = { environment: { get: k => vars.get(k), set: (k,v) => vars.set(k,v) },
      response: { code: 200, headers: { get: () => 'RUN-LOCAL' }, json: () => body },
      test: (_nombre, f) => { try { f(); } catch { fallos++; } }, expect,
      execution: { setNextRequest: x => { siguiente = x; } }, info: { requestName: 'API-191-01' } };
    vm.runInNewContext(codigo, { pm });
    return { fallos, siguiente };
  };
  const base = { total: 1, resumen_unidades: [{ alertas_activas_count: 1 }], sensores: [{ id_alerta: 2 }] };
  assert.equal(evaluar(base).fallos, 1);
  assert.equal(evaluar({ ...base, ...panel(['CRITICO','MODERADO'].map(alerta)) }).fallos, 0);
  assert.equal(evaluar({ ...base, ...panel(['LEVE','CRITICO'].map(alerta)) }).fallos, 1);
});
