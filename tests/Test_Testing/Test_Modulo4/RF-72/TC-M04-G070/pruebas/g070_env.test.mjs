import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {leerEnv,preflight,contexto,evaluar} from '../g070.mjs';
import {CASOS} from '../lib/g070_core.mjs';
const base={SIGAB_API_TEST_BASE:'http://127.0.0.1:3333',QA_SANDBOX_SECRET:'secreto-local',
  QA_VETERINARIO_EMAIL:'a@local.test',QA_ADMIN_EMAIL:'admin@local.test',
  QA_COMMON_PASSWORD:'clave-local',QA_ADMIN_PASSWORD:'clave-admin-local',QA_AUTORIZADO:'SI'};
const c={ensayo:true,runId:'RUN-G070-V1-20261029-000000'},newman={ok:true,version:'local'};
const tmp=fs.mkdtempSync(path.join(os.tmpdir(),'g070-env-'));
try{
  const archivo=path.join(tmp,'.env.qa');
  assert.equal(preflight(c,leerEnv(base,archivo),newman).ok,true);
  fs.writeFileSync(archivo,Object.entries(base).filter(([k])=>k!=='QA_AUTORIZADO').map(([k,v])=>`${k}=${v}`).join('\n'));
  assert.equal(preflight(c,leerEnv({QA_AUTORIZADO:'SI'},archivo),newman).ok,true);
  fs.writeFileSync(archivo,Object.entries(base).filter(([k])=>!['QA_AUTORIZADO','QA_ADMIN_PASSWORD'].includes(k))
    .map(([k,v])=>`${k}=${v}`).join('\n'));
  const falta=preflight(c,leerEnv({QA_AUTORIZADO:'SI'},archivo),newman);
  assert.equal(falta.ok,false);assert.ok(falta.barreras.includes('QA_ADMIN_PASSWORD'));
  const runId='RUN-G070-V2-20261101-050000',directorio=path.join(tmp,'EvaluacionV2','Resultados',runId);
  fs.mkdirSync(directorio,{recursive:true});
  const ruta=path.join(directorio,'contexto_operacion.json');
  const alcance={semilla_commit:'2026-11-01T04:30:40.915Z',alembic_test:'c31f8a6d920e'};
  const datos={grupo:'G070',version:2,intento:3,run_id:runId,operacion:'REINTENTAR',
    referencia:'ensayo local',casos:CASOS,alcance_reevaluacion:alcance,version_anterior:1};
  fs.writeFileSync(ruta,JSON.stringify(datos));
  const args=['--operacion','reintentar','--version','2','--intento','3','--run-id',runId,
    '--autorizacion','ensayo local','--contexto',ruta];
  const c2=contexto(args,tmp);
  assert.equal(c2.semillaCommit,alcance.semilla_commit);
  assert.equal(c2.commit,null);assert.equal(c2.alembicTest,alcance.alembic_test);
  fs.writeFileSync(ruta,JSON.stringify({...datos,semilla_commit:'2026-11-01T04:31:00Z',commit:'codigo-actual',
    alcance_reevaluacion:{...alcance,commit_despliegue:'codigo-alcance'}}));
  const prioritario=contexto(args,tmp);
  assert.equal(prioritario.semillaCommit,'2026-11-01T04:31:00Z');
  assert.equal(prioritario.commit,'codigo-actual');
  fs.writeFileSync(ruta,JSON.stringify({...datos,alcance_reevaluacion:{...alcance,commit_despliegue:'codigo-alcance'}}));
  assert.equal(contexto(args,tmp).commit,'codigo-alcance');
  fs.writeFileSync(ruta,JSON.stringify(datos));
  const envV2={...base,SIGAB_API_TEST_BASE:'https://www.api.inmero.co/api-sgpmp-test'};
  const ahora=Date.parse('2026-11-01T05:00:00Z');
  assert.deepEqual(preflight(c2,envV2,newman,ahora).barreras,[]);
  assert.ok(preflight({...c2,semillaCommit:null},envV2,newman,ahora).barreras.includes('SEMILLA_COMMIT_FALTANTE'));
  assert.ok(preflight({...c2,semillaCommit:'2026-11-01'},envV2,newman,ahora).barreras.includes('SEMILLA_COMMIT_FALTANTE'));
  assert.ok(preflight({...c2,semillaCommit:'2026-02-30T04:30:40Z'},envV2,newman,ahora).barreras.includes('SEMILLA_COMMIT_FALTANTE'));
  assert.ok(preflight(c2,envV2,newman,Date.parse('2026-11-01T14:30:41Z')).barreras.includes('SEMILLA_CADUCADA'));
  fs.writeFileSync(ruta,JSON.stringify({...datos,version_anterior:0}));
  assert.throws(()=>contexto(args,tmp),/Contexto incoherente/);
  fs.writeFileSync(ruta,JSON.stringify(datos));
  const runV1='RUN-G070-V1-20261101-050000',dirV1=path.join(tmp,'Resultados',runV1);
  fs.mkdirSync(dirV1,{recursive:true});
  const rutaV1=path.join(dirV1,'contexto_operacion.json');
  fs.writeFileSync(rutaV1,JSON.stringify({...datos,version:1,run_id:runV1,operacion:'REINTENTAR',
    version_anterior:undefined,alcance_reevaluacion:undefined}));
  assert.equal(contexto(['--operacion','reintentar','--version','1','--intento','3','--run-id',runV1,
    '--autorizacion','ensayo local','--contexto',rutaV1],tmp).version,1);
  const fallo=await evaluar({...c2,semillaCommit:null},{env:envV2,newmanVersion:newman});
  assert.equal(fallo.oficial,false);assert.equal(fallo.solicitudes.length,0);
  const pre=JSON.parse(fs.readFileSync(path.join(directorio,'preflight.json'),'utf8'));
  const resultado=JSON.parse(fs.readFileSync(path.join(directorio,'resultado.json'),'utf8'));
  assert.ok(pre.barreras.includes('SEMILLA_COMMIT_FALTANTE'));
  assert.equal(resultado.oficial,false);assert.equal(resultado.run_id,runId);
  assert.equal(resultado.cierre.rollback.verificado,false);
  assert.match(resultado.cierre.rollback.motivo,/No solicitado/);
  assert.ok(resultado.problemas_tecnicos.some(x=>x.includes('SEMILLA_COMMIT_FALTANTE')));
  assert.equal(resultado.solicitudes.length,0);
  assert.ok(!fs.existsSync(path.join(directorio,'TC-M04-G070_reevaluacion_V2.md')));
  console.log('OK G070 env: contexto REINTENTAR V2, caducidad y preflight con evidencia sin peticiones');
}finally{fs.rmSync(tmp,{recursive:true,force:true});}
