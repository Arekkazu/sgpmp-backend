import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {CAPACIDADES,contexto,dirRun,preflight,sanitize,verificarRollback} from '../g040.mjs';
import {servidorG040} from './simulador_g040.mjs';
const runId='RUN-G040-V2-20261118-000000';
const grupo=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const esperado=path.join(grupo,'EvaluacionV2','Resultados',runId);
const archivo=path.join(esperado,'contexto_operacion.json');
const args=['--operacion','reevaluar','--version','2','--intento','1','--run-id',runId,'--autorizacion','REF-LOCAL','--contexto',archivo];
const originalRead=fs.readFileSync;
fs.readFileSync=function(file,...options){
 if(path.resolve(file)===archivo)return JSON.stringify({grupo:'G040',run_id:runId,version:2,intento:1,operacion:'REEVALUAR',referencia:'REF-LOCAL',casos:CAPACIDADES.casos});
 return originalRead.call(this,file,...options);
};
let produccion;
try{produccion=contexto(args,false);}finally{fs.readFileSync=originalRead;}
assert.equal(produccion.dir,esperado);
assert.equal(dirRun(produccion),produccion.dir);
assert.throws(()=>dirRun({...produccion,dir:path.join(grupo,'Resultados',runId)}),/CONTEXTO_FUERA_RUN/);
assert.equal(CAPACIDADES.limite.solicitudes_totales,40);
assert.equal(CAPACIDADES.limite.duracion_segundos,600);
assert.equal(CAPACIDADES.casos.length,5);
assert.equal(preflight({ensayo:true,runId:'RUN-G040-V2-20261118-000000'},{QA_AUTORIZADO:'NO',SIGAB_API_TEST_BASE:'http://127.0.0.1:1'}).ok,false);
assert.equal(sanitize({client_id:'LOCAL_CLIENT',token:'LOCAL_TOKEN',ruta:'/integracion/aaef/productores/900123456?desde=2026-11-01'}).ruta,'/integracion/aaef/productores/***456?desde=2026-11-01');
assert.equal(verificarRollback([{id_version_contrato_aaef:1,estado:'ACTIVO'}],[{id_version_contrato_aaef:1,estado:'ACTIVO'}]),true);
assert.equal(verificarRollback([{id_version_contrato_aaef:1,estado:'ACTIVO'}],[{id_version_contrato_aaef:1,estado:'INACTIVO'}]),false);
const sim=await servidorG040();
try{
 const h={'X-Test-Run-Id':'RUN-G040-V2-20261118-000000'};
 await fetch(sim.api+'/sesiones/',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({correo_electronico:'local@example.invalid',contrasena:'LOCAL_PASSWORD'})});
 await fetch(sim.api+'/integraciones/agrofusion/token',{method:'POST',headers:{...h,'Content-Type':'application/json'},body:JSON.stringify({client_id:'LOCAL_CLIENT',client_secret:'LOCAL_SECRET',email:'local@example.invalid'})});
 const ruta=sim.api+'/integracion/aaef/productores/900123456?desde=2026-11-01&hasta=2026-11-30';
 for(let i=0;i<5;i++){const z=await fetch(ruta,{headers:{...h,Authorization:'Bearer LOCAL_CHANNEL_TOKEN'}});assert.equal(z.status,200);sim.avanzar(1000);}
 const sexto=await fetch(ruta,{headers:{...h,Authorization:'Bearer LOCAL_CHANNEL_TOKEN'}});assert.equal(sexto.status,429);
 sim.avanzar(300000);const vencido=await fetch(ruta,{headers:{...h,Authorization:'Bearer LOCAL_CHANNEL_TOKEN'}});assert.equal(vencido.status,401);
}finally{await sim.cerrar();}
console.log('OK local G040: preflight, saneamiento, rollback, ventana móvil y expiración');
