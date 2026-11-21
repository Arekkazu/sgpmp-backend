import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {CAPACIDADES,principal} from '../g039.mjs';
import {servidorG039} from './simulador_g039.mjs';
import {ejecutar as ejecutarNewman} from './newman_hijo.mjs';
const DIR=path.dirname(fileURLToPath(import.meta.url));
const RUN='RUN-G039-V2-20261117-000000';
const escenarios=JSON.parse(fs.readFileSync(path.join(DIR,'escenarios_g039.json'),'utf8')).escenarios;
export async function ejecutarEscenarios(salida=process.env.QA_VERIFICAR_SALIDAS??fs.mkdtempSync(path.join(os.tmpdir(),'g039-escenarios-'))){
 const resultados=[];
 for(const x of escenarios){
  const sim=await servidorG039(x.opciones);
  try{
   const dir=path.join(salida,x.id,RUN);fs.mkdirSync(dir,{recursive:true});
   const archivo=path.join(dir,'contexto_operacion.json');
   fs.writeFileSync(archivo,JSON.stringify({grupo:'G039',version:2,version_anterior:1,intento:1,run_id:RUN,operacion:'REEVALUAR',referencia:'LOCAL',casos:CAPACIDADES.casos}));
   const args=['--autorizacion','LOCAL','--operacion','reevaluar','--version','2','--intento','1','--run-id',RUN,'--contexto',archivo];
   const e={QA_AUTORIZADO:'SI',QA_ADMIN_EMAIL:'local@example.invalid',QA_ADMIN_PASSWORD:'LOCAL',QA_SANDBOX_SECRET:'LOCAL',SIGAB_API_TEST_BASE:sim.api};
   const z=await principal(args,{proceso:e,archivo:path.join(os.tmpdir(),'g039-sin-env'),prueba:true,dobles:{newman:ejecutarNewman}});
   assert.equal(z.codigo,0,x.id);const r=z.resultado,estados=['13','14','15','16'].map(k=>r.veredictos[k]);
   assert.deepEqual(estados,x.esperado,x.id+' '+JSON.stringify(r.problemas_tecnicos));
   assert.equal(r.oficial,x.oficial,x.id);
   assert(r.solicitudes_total<=70,x.id);
   assert.equal(sim.peticiones.filter(q=>q.ruta.startsWith('/test-control/runs/')).length,x.id==='login_invalido'?0:1,x.id);
   if(['antispam_previo','sin_permisos','dos_vigentes','login_invalido'].includes(x.id))assert.equal(r.consume_version,false,x.id);
   if(x.id==='conforme'){
    assert.equal(r.versiones_elegidas.ACTIVO.id,18);assert.equal(r.versiones_elegidas.PENDIENTE.id,4);assert.equal(r.versiones_elegidas.INACTIVO.id,1);
    assert.equal(r.comparaciones.repeticion.eventos.length,1);assert.equal(r.comparaciones.aviso_administrador.candidato.via,'nuevo');
   }
   if(x.id==='aviso_agrupado')assert.equal(r.comparaciones.aviso_administrador.candidato.via,'agrupado');
   if(x.id==='privacidad'){const text=fs.readFileSync(path.join(dir,'resultado.json'),'utf8')+fs.readFileSync(path.join(dir,'TC-M07-G039_reevaluacion_V2.md'),'utf8');assert(!text.includes('qa@example.invalid'));assert(!text.includes('eyJabc.def.ghi'));}
   const linea='OK escenario_'+x.id+': 13='+estados[0]+' 14='+estados[1]+' 15='+estados[2]+' 16='+estados[3]+' oficial='+r.oficial+' solicitudes='+r.solicitudes_total+'/70';
   console.log(linea);resultados.push({id:x.id,dir,veredictos:r.veredictos,oficial:r.oficial,solicitudes:r.solicitudes_total,linea});
  }finally{await sim.cerrar();}
 }
 fs.writeFileSync(path.join(salida,'resumen_escenarios.json'),JSON.stringify(resultados,null,2));
 return resultados;
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url))await ejecutarEscenarios();

