import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { leerEnv } from '../g068.mjs';

const temporal=fs.mkdtempSync(path.join(os.tmpdir(),'g068-env-'));
try {
  const archivo=path.join(temporal,'.env.qa');
  fs.writeFileSync(archivo,'QA_VETERINARIO_EMAIL=local@example.invalid\nQA_COMMON_PASSWORD=local\n','utf8');
  const con=leerEnv({QA_AUTORIZADO:'NO'},archivo);
  assert.deepEqual(['QA_VETERINARIO_EMAIL','QA_COMMON_PASSWORD'].map(k=>!!con[k]),[true,true]);
  assert.equal(con.QA_AUTORIZADO,'NO');
  const sin=leerEnv({QA_AUTORIZADO:'NO'},path.join(temporal,'ausente'));
  assert.equal(sin.QA_COMMON_PASSWORD,undefined);
  console.log('OK G068 env: presente y ausente; valores no impresos');
} finally {fs.rmSync(temporal,{recursive:true,force:true});}
