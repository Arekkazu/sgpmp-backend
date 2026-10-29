import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {leerEnv,preflight} from '../g069.mjs';
const base={SIGAB_API_TEST_BASE:'http://127.0.0.1:3333',QA_SANDBOX_SECRET:'secreto-local',
  QA_VETERINARIO_EMAIL:'a@local.test',QA_VETERINARIO_B_EMAIL:'b@local.test',
  QA_COMMON_PASSWORD:'clave-local',QA_AUTORIZADO:'SI'};
const c={ensayo:true,runId:'RUN-G069-V1-20261029-000000'};
const newman={ok:true,version:'local'};
const temporal=fs.mkdtempSync(path.join(os.tmpdir(),'g069-env-'));
try{
  const archivo=path.join(temporal,'.env.qa');
  assert.equal(preflight(c,leerEnv(base,archivo),newman).ok,true);
  fs.writeFileSync(archivo,Object.entries(base).filter(([k])=>k!=='QA_AUTORIZADO').map(([k,v])=>`${k}=${v}`).join('\n'));
  assert.equal(preflight(c,leerEnv({QA_AUTORIZADO:'SI'},archivo),newman).ok,true);
  fs.writeFileSync(archivo,Object.entries(base).filter(([k])=>!['QA_AUTORIZADO','QA_VETERINARIO_B_EMAIL'].includes(k))
    .map(([k,v])=>`${k}=${v}`).join('\n'));
  const ausente=preflight(c,leerEnv({QA_AUTORIZADO:'SI'},archivo),newman);
  assert.equal(ausente.ok,false);assert.ok(ausente.barreras.includes('QA_VETERINARIO_B_EMAIL'));
  console.log('OK G069 env: archivo presente, ausente y B ausente sin peticiones');
}finally{fs.rmSync(temporal,{recursive:true,force:true});}
