import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { leerEnv } from '../g057.mjs';
import { CAPACIDADES, PRESUPUESTO, escenarios } from '../lib/g057_escenario.mjs';

const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'g057-env-'));
try {
  const archivo = path.join(dir, '.env.qa');
  assert.equal(leerEnv({ QA_AUTORIZADO: 'SI' }, archivo).RF71_INTERNAL_KEY, undefined);
  fs.writeFileSync(archivo, 'RF71_INTERNAL_KEY=valor-local\nQA_ADMIN_EMAIL=qa@example.test\n', 'utf8');
  const env = leerEnv({ QA_AUTORIZADO: 'SI' }, archivo);
  assert.equal(env.RF71_INTERNAL_KEY, 'valor-local');
  assert.equal(env.QA_ADMIN_EMAIL, 'qa@example.test');
  assert.equal(leerEnv({ QA_AUTORIZADO: 'SI', RF71_INTERNAL_KEY: 'override' }, archivo).RF71_INTERNAL_KEY, 'override');
  assert.equal(PRESUPUESTO.total, 35);
  assert.equal(PRESUPUESTO.contingencia_maxima, 40);
  assert.equal(CAPACIDADES.limite.solicitudes_totales, 40);
  const datosE = escenarios({ tipo: 'MODELO_ESPECIES_GRANDES', variable: 7,
    hash: 'hash-local', dataset: 'dataset-local', archivo: 'archivo-local', nombres: ['E'] });
  assert.equal(datosE.length, 1);
  assert.equal(datosE[0].dato, 'E');
  assert.ok(datosE[0].id_proceso_rf71);
  console.log('OK G057 env: ausente, presente, prioridad del proceso; contingencia E y presupuestos 35/40; sin valores impresos');
} finally { fs.rmSync(dir, { recursive: true, force: true }); }
