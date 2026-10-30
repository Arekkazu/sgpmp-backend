import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { leerEnv } from '../g065.mjs';

const temporal = fs.mkdtempSync(path.join(os.tmpdir(), 'g065-env-'));
try {
  const archivo = path.join(temporal, '.env.qa');
  fs.writeFileSync(archivo, 'QA_VETERINARIO_EMAIL=local@example.invalid\nQA_COMMON_PASSWORD=local\n', 'utf8');
  const conArchivo = leerEnv({ QA_AUTORIZADO: 'NO' }, archivo);
  assert.deepEqual(['QA_VETERINARIO_EMAIL', 'QA_COMMON_PASSWORD'].map(k => !!conArchivo[k]), [true, true]);
  assert.equal(conArchivo.QA_AUTORIZADO, 'NO');
  const sinArchivo = leerEnv({ QA_AUTORIZADO: 'NO' }, path.join(temporal, 'ausente'));
  assert.equal(sinArchivo.QA_COMMON_PASSWORD, undefined);
  console.log('OK G065 env: presente y ausente');
} finally { fs.rmSync(temporal, { recursive: true, force: true }); }
