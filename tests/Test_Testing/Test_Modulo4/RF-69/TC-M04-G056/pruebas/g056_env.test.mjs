import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { leerEnv } from '../g056.mjs';
const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'g056-env-'));
try {
  const p = path.join(dir, '.env.qa');
  assert.equal(leerEnv({ QA_AUTORIZADO: 'SI' }, p).RF71_INTERNAL_KEY, undefined);
  fs.writeFileSync(p, 'RF71_INTERNAL_KEY=valor-local\nQA_ADMIN_EMAIL=qa@example.test\n', 'utf8');
  const env = leerEnv({ QA_AUTORIZADO: 'SI' }, p);
  assert.equal(env.RF71_INTERNAL_KEY, 'valor-local');
  assert.equal(env.QA_ADMIN_EMAIL, 'qa@example.test');
  assert.equal(leerEnv({ QA_AUTORIZADO: 'SI', RF71_INTERNAL_KEY: 'override' }, p).RF71_INTERNAL_KEY, 'override');
  console.log('OK G056 env: ausente, presente, prioridad del proceso; sin valores impresos');
} finally { fs.rmSync(dir, { recursive: true, force: true }); }
