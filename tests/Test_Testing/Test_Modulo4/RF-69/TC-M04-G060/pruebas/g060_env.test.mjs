import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { leerEnv, preflight } from '../g060.mjs';

const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'g060-env-'));
try {
  const presente = path.join(tmp, '.env.qa');
  fs.writeFileSync(presente, 'QA_ADMIN_EMAIL="archivo@ejemplo.test"\nRF71_INTERNAL_KEY=valor_oculto\nQA_AUTORIZADO=SI\n');
  const conArchivo = leerEnv({ QA_AUTORIZADO: 'NO', QA_ADMIN_EMAIL: 'proceso@ejemplo.test' }, presente);
  assert.equal(conArchivo.QA_ADMIN_EMAIL, 'proceso@ejemplo.test');
  assert.equal(conArchivo.QA_AUTORIZADO, 'NO');
  assert.equal(conArchivo.RF71_INTERNAL_KEY, 'valor_oculto');
  const sinArchivo = leerEnv({ QA_AUTORIZADO: 'NO' }, path.join(tmp, 'ausente'));
  assert.equal(sinArchivo.RF71_INTERNAL_KEY, undefined);
  const pf = preflight({ runId: 'ENSAYO-G060-20261028-000000-env', version: 1 }, sinArchivo, true);
  assert(pf.barreras.includes('RF71_INTERNAL_KEY'));
  assert(pf.barreras.includes('QA_AUTORIZADO'));
  console.log('OK G060 env: archivo presente y ausente; prioridad del proceso; sin valores en salida');
} finally { fs.rmSync(tmp, { recursive: true, force: true }); }
