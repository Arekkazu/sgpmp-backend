import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {leerEnv,preflight} from '../g072.mjs';
const base={SIGAB_API_TEST_BASE:'http://127.0.0.1:3333',QA_SANDBOX_SECRET:'secreto-local',QA_VETERINARIO_EMAIL:'a@local.test',
  QA_VETERINARIO_B_EMAIL:'b@local.test',QA_VETERINARIO_C_EMAIL:'c@local.test',QA_ADMIN_EMAIL:'admin@local.test',
  QA_COMMON_PASSWORD:'clave-local',QA_AUTORIZADO:'SI'};
const c={ensayo:true,runId:'RUN-G072-V1-20261029-000000'},newman={ok:true,version:'local'};
const tmp=fs.mkdtempSync(path.join(os.tmpdir(),'g072-env-'));
try{
  const archivo=path.join(tmp,'.env.qa');
  assert.equal(preflight(c,leerEnv(base,archivo),newman).ok,true);
  fs.writeFileSync(archivo,Object.entries(base).filter(([k])=>k!=='QA_AUTORIZADO').map(([k,v])=>`${k}=${v}`).join('\n'));
  assert.equal(preflight(c,leerEnv({QA_AUTORIZADO:'SI'},archivo),newman).ok,true);
  for(const key of ['QA_VETERINARIO_B_EMAIL','QA_VETERINARIO_C_EMAIL','QA_ADMIN_EMAIL']){
    const e=leerEnv({QA_AUTORIZADO:'SI'},archivo);delete e[key];
    const falta=preflight(c,e,newman);assert.equal(falta.ok,false);assert.ok(falta.barreras.includes(key));
  }
  console.log('OK G072 env: archivo presente, ausente y B/C faltantes sin peticiones');
}finally{fs.rmSync(tmp,{recursive:true,force:true});}
