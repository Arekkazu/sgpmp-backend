import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {createRequire} from 'node:module';
import {ejecutar} from '../g46.mjs';
import {simuladorG46} from './simulador_g46.mjs';

const modos=['conforme','sin_iniciado','hash_publicados_distintos','variacion_sin_id_cierre','hash_recalculo_distinto','payload_truncado','cierre_409','220_cerrado_tercero','sin_variaciones_ni_depreciacion','delete_fallido','matriz_49_inactiva'];
const salidas=process.env.QA_VERIFICAR_SALIDAS??fs.mkdtempSync(path.join(os.tmpdir(),'g46-escenarios-'));
fs.mkdirSync(salidas,{recursive:true});
try{
  for(const [modo,inyectados] of [...modos.map(x=>[x,false]),['conforme',true],['hash_recalculo_distinto',true]]){
    const nombre=`${modo}_${inyectados?'inyectado':'normal'}`,dir=path.join(salidas,nombre);fs.mkdirSync(dir,{recursive:true});
    const sim=await simuladorG46(modo,inyectados);
    try{
      const c={dir,runId:'RUN-G46-V1-20261110-000000',version:1,ref:'LOCAL'};
      const e={QA_SANDBOX_SECRET:'LOCAL'};
      const hijo=async(_script,input)=>{
        const nd=input.salida;fs.mkdirSync(nd,{recursive:true});
        const require=createRequire(import.meta.url);
        const newman=require(path.join(path.dirname(process.execPath),'node_modules','newman'));
        const json=path.join(nd,'newman-G46.json'),html=path.join(nd,'newman-G46.html');
        const {error,summary}=await new Promise(resolve=>newman.run({collection:input.coleccion,environment:input.environment,reporters:['json','htmlextra'],reporter:{json:{export:json},htmlextra:{export:html,skipSensitiveData:true}},silent:true,timeoutRequest:10000,timeout:30000,ignoreRedirects:true},(error,summary)=>resolve({error,summary})));
        for(const file of [json,html])if(fs.existsSync(file))fs.writeFileSync(file,fs.readFileSync(file,'utf8').replaceAll('LOCAL_SIMULADO','[REDACTADO]').replaceAll('LOCAL','[REDACTADO]'));
        return {code:error?2:0,data:{codigo:error?2:0,fallos:summary?.run?.failures?.length??-1,reportes:fs.existsSync(json)&&fs.existsSync(html),solicitudes:summary?.run?.executions?.length??0}};
      };
      const r=await ejecutar(c,e,{ensayo:true,api:sim.url,hijo});
      assert(sim.deleteHecho,`${nombre}: sin DELETE`);
      const checks=Object.fromEntries(r.casos['TC-M06-034'].comprobaciones.map(x=>[x.id,x.estado]));
      if(modo==='conforme'){assert.deepEqual(Object.values(checks),Array(5).fill('APROBADO'),nombre);assert(r.oficial,nombre);}
      if(modo==='sin_iniciado')assert.equal(checks['034_iniciado'],'RECHAZADO');
      if(modo==='hash_publicados_distintos')assert.equal(checks['034_hash_verificable'],'RECHAZADO');
      if(modo==='variacion_sin_id_cierre')assert.equal(checks['034_referencias'],'RECHAZADO');
      if(modo==='hash_recalculo_distinto'){assert.equal(checks['034_hash_verificable'],'NO_CONCLUYENTE');assert.equal(r.incidencias.length,0);}
      if(modo==='payload_truncado')assert.equal(checks['034_hash_verificable'],'NO_CONCLUYENTE');
      if(modo==='cierre_409')assert(Object.values(checks).every(x=>x==='NO_CONCLUYENTE'));
      if(modo==='220_cerrado_tercero'){assert(!sim.peticiones.some(x=>x.metodo==='POST'&&x.ruta.includes('/cierre')));assert(r.preflight_datos.some(x=>x.requisito==='periodo_220_abierto'&&!x.cumple));}
      if(modo==='matriz_49_inactiva'){assert(!sim.peticiones.some(x=>x.metodo==='POST'&&x.ruta.includes('/cierre')));assert(r.preflight_datos.some(x=>x.requisito==='matriz_49_generica_activa'&&!x.cumple));assert(Object.values(checks).every(x=>x==='NO_CONCLUYENTE'));}
      if(modo==='sin_variaciones_ni_depreciacion')assert.equal(checks['034_referencias'],'NO_CONCLUYENTE');
      if(modo==='delete_fallido')assert(!r.oficial);
      fs.writeFileSync(path.join(dir,'resultado.json'),JSON.stringify(r,null,2));
    }finally{await sim.cerrar();}
  }
  console.log('OK 13 escenarios locales G46');
}finally{if(!process.env.QA_VERIFICAR_SALIDAS)fs.rmSync(salidas,{recursive:true,force:true});}
