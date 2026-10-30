import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { leerEnv } from '../g058.mjs';
import { CAPACIDADES, PRESUPUESTO, escenarios, registroValido } from '../lib/g058_escenario.mjs';

const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'g058-env-'));
try {
  const archivo = path.join(dir, '.env.qa');
  assert.equal(leerEnv({ QA_AUTORIZADO: 'SI' }, archivo).RF71_INTERNAL_KEY, undefined);
  fs.writeFileSync(archivo, 'RF71_INTERNAL_KEY=valor-local\nQA_ADMIN_EMAIL=qa@example.test\n', 'utf8');
  const env = leerEnv({ QA_AUTORIZADO: 'SI' }, archivo);
  assert.equal(env.RF71_INTERNAL_KEY, 'valor-local');
  assert.equal(env.QA_ADMIN_EMAIL, 'qa@example.test');
  assert.equal(leerEnv({ QA_AUTORIZADO: 'SI', RF71_INTERNAL_KEY: 'override' }, archivo).RF71_INTERNAL_KEY, 'override');
  assert.equal(PRESUPUESTO.total, 37);
  assert.equal(CAPACIDADES.limite.solicitudes_totales, 37);
  assert.equal(PRESUPUESTO.activa_antes_157, 1);
  assert.equal(PRESUPUESTO.auditorias_intentos, 4);
  const datos = escenarios({ variable: 7, hash: 'hash-local', dataset: 'dataset-local', archivo: 'archivo-local' });
  assert.deepEqual(datos.map(x => x.dato), ['A', 'B', 'R']);
  assert.equal(datos[2].metricas_validacion.f1_score_global, 0.72);
  assert.equal(datos[2].metricas_validacion.recall_clase_riesgo_alto, 0.95);
  assert.equal(new Set(datos.map(x => x.id_proceso_rf71)).size, 3);
  const registro = (http, estado_version, eco = true, id_version_modelo = 103) =>
    ({ http, eco, cuerpo: { estado_version, id_version_modelo } });
  assert.equal(registroValido(registro(201, 'APROBADO'), 'APROBADO'), true);
  assert.equal(registroValido(registro(200, 'APROBADO'), 'APROBADO'), false);
  assert.equal(registroValido(registro(200, 'RECHAZADO'), 'RECHAZADO'), true);
  assert.equal(registroValido(registro(201, 'RECHAZADO'), 'RECHAZADO'), true);
  assert.equal(registroValido(registro(202, 'RECHAZADO'), 'RECHAZADO'), false);
  assert.equal(registroValido(registro(200, 'APROBADO'), 'RECHAZADO'), false);
  assert.equal(registroValido(registro(200, 'RECHAZADO', false), 'RECHAZADO'), false);
  assert.equal(registroValido(registro(200, 'RECHAZADO', true, null), 'RECHAZADO'), false);
  console.log('OK G058 env: ausente, presente, prioridad del proceso; métricas y UUID; registro 200/201; presupuesto 37; sin valores impresos');
} finally { fs.rmSync(dir, { recursive: true, force: true }); }
