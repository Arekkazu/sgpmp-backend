import test from 'node:test';
import assert from 'node:assert/strict';
import { GRUPO, CASOS, PLAN, comprobarSinSenal } from './g90_casos.mjs';
import { evaluarAutorizacion, inspeccionarHistorial, resolverVersion, sanitizar } from './g90_lib.mjs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

test('matriz y aserciones individuales', () => {
  assert.deepEqual(CASOS.map((c) => c.id), ["TC-M03-175","TC-M03-176"]);
  assert.deepEqual(GRUPO.casosMatriz, ["TC-M03-175","TC-M03-176"]);
  for (const caso of CASOS) {
    assert.ok(caso.esperado && caso.datos && caso.actor);
    assert.ok(caso.aserciones.some((a) => a.tipo === 'ASSERT'));
    assert.equal(new Set(caso.aserciones.map((a) => a.id)).size, caso.aserciones.length);
  }
  assert.equal(PLAN.casosUI.length, 2);
});

test('la barrera de autorización rechaza QA_AUTORIZADO=NO', () => {
  const v = { QA_AUTORIZADO: 'NO', SIGAB_API_TEST_BASE: 'https://api.test.invalid',
    SIGAB_FRONT_TEST_URL: 'https://front.test.invalid', QA_SANDBOX_SECRET: 'local',
    QA_SETUP_EMAIL: 'setup@example.invalid', QA_PROD_EMAIL: 'prod@example.invalid',
    QA_COMMON_PASSWORD: 'local', QA_DEVICE_PREFIX: '' };
  const r = evaluarAutorizacion(v, { ambiente: 'TEST', autorizacion: 'REFERENCIA-LOCAL',
    actores: PLAN.actores, efectosAceptados: PLAN.efectosPersistentes.map((e) => e.id) }, PLAN.efectosPersistentes);
  assert.equal(r.autorizado, false);
});

test('historial vacío mantiene V1 y no altera archivos', () => {
  const dir = path.dirname(fileURLToPath(import.meta.url));
  const h = inspeccionarHistorial(dir);
  assert.equal(h.anomalias.length, 0);
  assert.equal(resolverVersion(h, { tipo: 'evaluacion' }).version, 1);
});

test('reevaluación y reintento conservan la nomenclatura histórica', () => {
  const h = { versiones: [{ version: 1, runs: [{ estado: 'CONCLUIDA' }] }], maxima: 1, anomalias: [] };
  assert.equal(resolverVersion(h, { tipo: 'evaluacion' }).version, 2);
  assert.equal(resolverVersion(h, { tipo: 'reintento' }).version, 1);
  const h2 = { versiones: [{ version: 2, runs: [{ estado: 'ABORTADA_PREFLIGHT' }] }], maxima: 2, anomalias: [] };
  assert.equal(resolverVersion(h2, { tipo: 'evaluacion' }).version, 2);
});

test('sanitización elimina secretos', () => {
  const limpio = sanitizar({ token: 'abc', access_key: 'CLAVE-IOT-COMPLETA', valor: 25 }, ['CLAVE-IOT-COMPLETA']);
  assert.notEqual(limpio.token, 'abc');
  assert.ok(!JSON.stringify(limpio).includes('CLAVE-IOT-COMPLETA'));
});

test('capacidad temporal exige ambos sensores en SIN_SEÑAL tras el intervalo', () => {
  const ts = '2026-10-16T12:00:00Z';
  const s = (id, alerta) => ({ id_sensor: id, ultimo_valor: 25, ultimo_timestamp_captura: ts,
    estado_conectividad: 'SIN_SEÑAL', dato_desactualizado: true,
    tiempo_sin_reporte_min: 10, id_alerta: alerta, severidad_alerta: alerta ? 'CRITICO' : null });
  const d = { sensor175: 175, sensor176: 176, alerta175: 99,
    lecturas: { '175': { timestamp: ts }, '176': { timestamp: ts } },
    ahora: Date.parse('2026-10-16T12:10:00Z') };
  assert.equal(comprobarSinSenal({ sensores: [s(175, 99), s(176, null)] }, d).listo, true);
  const sinTransicion = s(176, null); sinTransicion.estado_conectividad = 'ACTIVO';
  assert.equal(comprobarSinSenal({ sensores: [s(175, 99), sinTransicion] }, d).listo, false);
  assert.equal(comprobarSinSenal({ sensores: [s(175, 99)] }, d).listo, false);
  assert.equal(comprobarSinSenal({ sensores: [s(175, 99), s(176, null)] }, { ...d, ahora: Date.parse('2026-10-16T12:04:00Z') }).listo, false);
  const sinAlerta = s(175, null); sinAlerta.ultimo_valor = null;
  sinAlerta.ultimo_timestamp_captura = null;
  assert.equal(comprobarSinSenal({ sensores: [sinAlerta, s(176, null)] }, d).listo, true,
    'valor, timestamp y alerta son resultados esperados, no barreras de capacidad');
});
