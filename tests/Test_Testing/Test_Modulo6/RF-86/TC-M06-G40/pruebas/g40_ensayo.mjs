import {escenario} from './fixture_g40.mjs';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {spawn} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {CAPACIDADES} from '../g40.mjs';
const ejemplo=path.join(os.tmpdir(),'g40-verificar-ejemplo');
if(process.argv.includes('--ejemplo-hijo')){
  const x=await escenario('ejemplo_v2',{operacion:'reintentar',modoAuto:true,
    avisosPrevios:['GANANCIA'],copiarEjemplo:ejemplo});
  fs.writeFileSync(path.join(ejemplo,'capacidades.json'),JSON.stringify(CAPACIDADES,null,2));
  const run=path.join(ejemplo,x.resultado.run_id);
  if(!x.resultado.oficial||x.resultado.casos['TC-M06-018'].estado!=='APROBADO'||
    x.postBody?.sentido!=='PERDIDA'||x.resultado.observado.sentido_modo!=='AUTO'||
    x.resultado.observado.sentidos_descartados?.[0]?.id_aviso!==12796||
    x.resultado.seguimiento.estado_v2!=='CORREGIDA')
    throw Error(`Ejemplo V2 PERDIDA no conforme: ${x.resultado.no_oficial_motivos.join('; ')}`);
  console.log(`RUN local: ${run}`);
  console.log(`resultado.json: ${path.join(run,'resultado.json')}`);
  console.log(`informe: ${path.join(run,'TC-M06-G40_reevaluacion_V2.md')}`);
  console.log(`capacidades.json: ${path.join(ejemplo,'capacidades.json')}`);
}else{
for(const [name,options] of [['conforme',{alerta:true}],['perdida',{sentido:'PERDIDA'}],['sin_alerta',{alerta:false}],
  ['cypress_fallido',{cypressFail:true}],['matriz_no_restaurada',{matrizNoRestaurada:true}]]){
  const x=await escenario(name,options);const r=x.resultado;
  console.log(`OK escenario_${name}: 018=${r.casos['TC-M06-018'].estado} oficial=${r.oficial?'sí':'no'} solicitudes=${x.requests}/150`);
  if(x.overlaps||x.requests>150)process.exitCode=2;
}
if(path.resolve(ejemplo)!==path.resolve(os.tmpdir(),'g40-verificar-ejemplo'))throw Error('Directorio temporal inesperado');
fs.rmSync(ejemplo,{recursive:true,force:true});
await new Promise((resolve,reject)=>{let p;try{p=spawn(process.execPath,[fileURLToPath(import.meta.url),'--ejemplo-hijo'],
  {stdio:['ignore','pipe','pipe'],windowsHide:true,timeout:180000});}catch(error){reject(error);return;}
  let out='',err='';
  p.stdout.on('data',x=>out+=x);p.stderr.on('data',x=>err+=x);
  p.on('error',reject);p.on('close',code=>code===0?(process.stdout.write(out),resolve()):reject(Error(`Ejemplo V2: ${err||out||code}`)));})
  .catch(error=>{if(error?.code==='EPERM')process.stderr.write('PENDIENTE ejemplo V2 en proceso hijo: spawn EPERM; repetir en Windows.\n');
    else throw error;});
}
