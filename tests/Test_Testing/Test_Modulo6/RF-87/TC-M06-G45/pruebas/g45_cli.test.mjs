import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {CAPACIDADES,contexto,leerEnv,preflight} from '../g45.mjs';
const raiz=fs.mkdtempSync(path.join(os.tmpdir(),'g45-cli-'));
try{
  const v2='RUN-G45-V2-20261110-000001',dirV2=path.join(raiz,v2);fs.mkdirSync(dirV2);
  const archivoV2=path.join(dirV2,'contexto_operacion.json');
  fs.writeFileSync(archivoV2,JSON.stringify({grupo:'G45',run_id:v2,version:2,intento:1,operacion:'REEVALUAR',referencia:'LOCAL-V2',casos:CAPACIDADES.casos}));
  const argsV2=['--operacion','reevaluar','--version','2','--intento','1','--run-id',v2,'--autorizacion','LOCAL-V2','--contexto',archivoV2];
  assert.equal(contexto(argsV2,true).version,2);
  const e=leerEnv({QA_AUTORIZADO:'NO'},path.join(raiz,'inexistente.env'));
  assert(!preflight(contexto(argsV2,true),e).ok);
  assert.throws(()=>contexto(argsV2.map(x=>x==='LOCAL-V2'?'OTRA':x),true));
  const reintento='RUN-G45-V2-20261110-000002',dirReintento=path.join(raiz,reintento);fs.mkdirSync(dirReintento);
  const archivoReintento=path.join(dirReintento,'contexto_operacion.json');
  const argsReintento=['--operacion','reintentar','--version','2','--intento','2','--run-id',reintento,'--autorizacion','LOCAL-V2','--contexto',archivoReintento];
  const datosReintento={grupo:'G45',run_id:reintento,version:2,intento:2,operacion:'REINTENTAR',referencia:'LOCAL-V2',casos:CAPACIDADES.casos,version_anterior:null};
  fs.writeFileSync(archivoReintento,JSON.stringify(datosReintento));
  assert.equal(contexto(argsReintento,true).dir,dirReintento);
  const cli=spawnSync(process.execPath,[fileURLToPath(new URL('../g45.mjs',import.meta.url)),'--prueba-cli-local',...argsReintento],{encoding:'utf8',env:{...process.env,NODE_ENV:'test',QA_AUTORIZADO:'NO',G45_PRUEBA_ENV_FILE:path.join(raiz,'inexistente.env')}});
  if(cli.error?.code==='EPERM')assert.equal(contexto(argsReintento,true).operacion,'reintentar');
  else{
    assert.ifError(cli.error);
    assert.equal(cli.status,2,cli.stderr);
    assert.match(cli.stderr,/PREFLIGHT_\S*QA_AUTORIZADO/);
    assert(fs.existsSync(path.join(dirReintento,'preflight.json')));
  }
  delete datosReintento.version_anterior;
  fs.writeFileSync(archivoReintento,JSON.stringify(datosReintento));
  assert.equal(contexto(argsReintento,true).operacion,'reintentar');
  for(const version of [1,3]){
    const invalido=`RUN-G45-V${version}-20261110-000002`,dirInvalido=path.join(raiz,invalido);fs.mkdirSync(dirInvalido);
    const archivoInvalido=path.join(dirInvalido,'contexto_operacion.json');
    fs.writeFileSync(archivoInvalido,JSON.stringify({...datosReintento,run_id:invalido,version}));
    const argsInvalidos=['--operacion','reintentar','--version',String(version),'--intento','2','--run-id',invalido,'--autorizacion','LOCAL-V2','--contexto',archivoInvalido];
    assert.throws(()=>contexto(argsInvalidos,true),/CONTEXTO_INCOMPLETO/);
  }
  fs.writeFileSync(archivoReintento,JSON.stringify({...datosReintento,version_anterior:1}));
  assert.throws(()=>contexto(argsReintento,true),/CONTEXTO_INCOHERENTE/);
  assert(!fs.existsSync(path.join(dirV2,'resultado.json')));
  console.log('OK CLI y preflight local');
}finally{fs.rmSync(raiz,{recursive:true,force:true});}
