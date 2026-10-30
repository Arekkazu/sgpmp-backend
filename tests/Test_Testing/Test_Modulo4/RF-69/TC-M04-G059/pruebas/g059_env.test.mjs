import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { leerEnv } from '../g059.mjs';
import { CAPACIDADES, COMBINACIONES, PRESUPUESTO, escenarios, registroValido } from '../lib/g059_escenario.mjs';

const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'g059-env-'));
try {
  const archivo = path.join(dir, '.env.qa');
  assert.equal(leerEnv({ QA_AUTORIZADO: 'SI' }, archivo).RF71_INTERNAL_KEY, undefined);
  fs.writeFileSync(archivo, 'RF71_INTERNAL_KEY=valor-local\nQA_ADMIN_EMAIL=qa@example.test\n', 'utf8');
  const env = leerEnv({ QA_AUTORIZADO: 'SI' }, archivo);
  assert.equal(env.RF71_INTERNAL_KEY, 'valor-local');
  assert.equal(env.QA_ADMIN_EMAIL, 'qa@example.test');
  assert.equal(leerEnv({ QA_AUTORIZADO: 'SI', RF71_INTERNAL_KEY: 'override' }, archivo).RF71_INTERNAL_KEY, 'override');
  assert.equal(PRESUPUESTO.total, 100);
  assert.equal(CAPACIDADES.limite.solicitudes_totales, 102);
  assert.equal(COMBINACIONES.length, 14);
  const datos = escenarios({ variable: 7, hash: 'hash-local', dataset: 'dataset-local', archivo: 'archivo-local' });
  assert.deepEqual(datos.map(x => x.dato), ['V1', 'V2', 'V3', 'R']);
  assert.equal(datos[3].metricas_validacion.f1_score_global, 0.72);
  assert.equal(new Set(datos.map(x => x.id_proceso_rf71)).size, 4);
  const registro = (http, estado_version) => ({ http, eco: true, cuerpo: { estado_version, id_version_modelo: 101 } });
  assert.equal(registroValido(registro(201, 'APROBADO'), 'APROBADO'), true);
  assert.equal(registroValido(registro(200, 'RECHAZADO'), 'RECHAZADO'), true);
  assert.equal(registroValido(registro(201, 'RECHAZADO'), 'RECHAZADO'), false);
  console.log('OK G059 env: ausente, presente y prioridad; cuatro registros; 14 combinaciones; sin valores impresos');
} finally { fs.rmSync(dir, { recursive: true, force: true }); }
