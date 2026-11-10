import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {CAPACIDADES,contexto,leerEnv,preflight} from '../g44.mjs';
const raiz=fs.mkdtempSync(path.join(os.tmpdir(),'g44-cli-'));
try{
  const runId='RUN-G44-V1-20261110-000000',dir=path.join(raiz,runId);fs.mkdirSync(dir);
  const archivo=path.join(dir,'contexto_operacion.json');
  fs.writeFileSync(archivo,JSON.stringify({grupo:'G44',run_id:runId,version:1,intento:1,operacion:'EVALUAR',referencia:'LOCAL',casos:CAPACIDADES.casos}));
  const args=['--operacion','evaluar','--version','1','--intento','1','--run-id',runId,'--autorizacion','LOCAL','--contexto',archivo];
  assert.equal(contexto(args,true).dir,dir);
  assert.throws(()=>contexto([...args.slice(0,-1),path.join(raiz,'otro.json')],true));
  const e=leerEnv({QA_AUTORIZADO:'NO'},path.join(raiz,'inexistente.env'));
  assert(!preflight(contexto(args,true),e).ok);
  assert(!fs.existsSync(path.join(dir,'resultado.json')));
  const v2='RUN-G44-V2-20261110-000001',dirV2=path.join(raiz,v2);fs.mkdirSync(dirV2);
  const archivoV2=path.join(dirV2,'contexto_operacion.json');
  fs.writeFileSync(archivoV2,JSON.stringify({grupo:'G44',run_id:v2,version:2,intento:1,operacion:'REEVALUAR',referencia:'LOCAL-V2',casos:CAPACIDADES.casos}));
  const argsV2=['--operacion','reevaluar','--version','2','--intento','1','--run-id',v2,'--autorizacion','LOCAL-V2','--contexto',archivoV2];
  assert.equal(contexto(argsV2,true).version,2);
  assert.throws(()=>contexto(argsV2.map(x=>x==='LOCAL-V2'?'OTRA':x),true));
  assert(!fs.existsSync(path.join(dirV2,'resultado.json')));
  console.log('OK CLI y preflight local');
}finally{fs.rmSync(raiz,{recursive:true,force:true});}
