import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {contrato} from './lib/contrato.mjs';
import {ejecutarV2} from './lib/flujo_v2.mjs';
import {sha256, contexto as contextoInfra, leerEnv as leerEnvInfra, preflight as preflightInfra} from './lib/infra.mjs';

const DIR=path.dirname(fileURLToPath(import.meta.url));
const ROOT=path.resolve(DIR,'../../../../..');
const API='https://www.api.inmero.co/api-sgpmp-test';
const FRONT='https://api.inmero.co/sigab-test';
const CASOS=['TC-M06-031','TC-M06-032','TC-M06-033'];
const LIMITE={solicitudes_totales:240,segundos:1800};
const archivos=['g45.mjs','lib/flujo_v2.mjs','lib/infra.mjs','lib/contrato.mjs','lib/informe.mjs','pruebas/contrato_g45.json','pruebas/escenarios_g45.json','pruebas/g45_escenarios.test.mjs','pruebas/simulador_g45.mjs','pruebas/newman_hijo.mjs','pruebas/verificar.mjs','G45.postman_collection.json','README.md'];
const clean=x=>String(x??'').replace(/eyJ[\w-]+\.[\w-]+\.[\w-]+|[\w.+-]+@[\w.-]+|\bQA-[A-Z0-9-]{4,}\b|\b\d{8,12}\b/g,'[RESERVADO]').slice(0,300);
export const CAPACIDADES={contrato:'sigab-qa-ejecutor/1',grupo:'G45',casos:CASOS,operaciones:['reevaluar','reintentar'],versiones:{min:2,max:2},comprobaciones_obligatorias:{'TC-M06-031':{API:['031_en_cierre','031_costo','031_m02','031_escenario_b','031_escenario_a']},'TC-M06-032':{API:['032_alta_costo','032_eliminar_reconocimiento','032_integridad']},'TC-M06-033':{API:['033_ajuste','033_cerrado_intacto']}},limite:LIMITE,baja_automatizada:true};
export function comprobar(){
  const faltan=archivos.filter(x=>!fs.existsSync(path.join(DIR,x)));
  let col;try{col=JSON.parse(fs.readFileSync(path.join(DIR,'G45.postman_collection.json'),'utf8'));}catch{}
  const superior=fs.existsSync(path.join(DIR,'Resultados'))&&fs.readdirSync(path.join(DIR,'Resultados')).some(x=>x.endsWith('.md'));
  const imports=fs.readFileSync(path.join(DIR,'g45.mjs'),'utf8').match(/from ['"]([^'"]+)['"]/g)??[];
  const ok=!faltan.length&&col?.item?.length>=4&&col.item.every(x=>x.request?.method==='GET')&&contrato.rutas.length>0&&!superior&&imports.every(x=>!x.includes('../TC-M06-'));
  console.log(JSON.stringify({grupo:'G45',ok,faltan,items:col?.item?.length??0,sha256:Object.fromEntries(archivos.filter(x=>fs.existsSync(path.join(DIR,x))).map(x=>[x,sha256(path.join(DIR,x))]))}));
  return ok?0:2;
}
export const contexto=(a,prueba=false)=>contextoInfra(a,{capacidades:CAPACIDADES,grupo:'G45',casos:CASOS,dir:DIR,prueba});
export const leerEnv=(p=process.env,archivo=path.join(ROOT,'.env.qa'))=>leerEnvInfra(p,archivo);
export const preflight=(c,e=process.env)=>{const p=preflightInfra(c,e,{grupo:'G45',api:API,front:FRONT,efectos:['inicios de sesión Contador y Administrador','2 POST cierre del período 266, 241 o 220 sin autorizar','1 POST cancelación del cierre','1 POST cierre autorizado con exclusiones y posible creación del período siguiente','2 POST crecimiento M02 por Administrador','3 POST procesamiento M02/M05 por Contador','1 POST costo durante EN_CIERRE','1 POST costo cerrado y 1 POST reversión (rechazos esperados)','1 POST ajuste de línea 2625','lecturas API, auditoria y Newman','DELETE del RUN y lecturas poscierre sin cabeceras']});for(const k of ['QA_ADMIN_EMAIL','QA_ADMIN_PASSWORD'])if(!String(e[k]??'').trim()){p.ok=false;p.barreras.push(k);}return p;};

export async function ejecutar(c,e=process.env,opciones={}){
  const local=opciones.ensayo===true&&/^http:\/\/127\.0\.0\.1:\d+\/api$/.test(opciones.api??'');
  const api=local?opciones.api:API;
  const pf=local?{ok:true,barreras:[],efectos:preflight(c,e).efectos}:preflight(c,e);
  if(!pf.ok)throw Error(`PREFLIGHT_${pf.barreras.join('_')}`);
  return ejecutarV2({c,e,api,local,dir:DIR,capacidades:CAPACIDADES,limite:LIMITE,pf,hijo:opciones.hijo});
}

if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
  try{if(process.argv.includes('--capacidades'))console.log(JSON.stringify(CAPACIDADES));
    else if(process.argv.includes('--comprobar'))process.exitCode=comprobar();
    else{const prueba=process.env.NODE_ENV==='test'&&process.argv.includes('--prueba-cli-local');const archivo=prueba?path.resolve(process.env.G45_PRUEBA_ENV_FILE??'.'):path.join(ROOT,'.env.qa');if(prueba&&!archivo.startsWith(path.resolve(os.tmpdir())+path.sep))throw Error('ENV_PRUEBA_FUERA_TEMPORAL');const c=contexto(process.argv.slice(2),prueba),e=leerEnv(process.env,archivo),p=preflight(c,e);fs.writeFileSync(path.join(c.dir,'preflight.json'),JSON.stringify(p,null,2));if(!p.ok){console.error(`PREFLIGHT_${p.barreras.join('_')}`);process.exitCode=2;}else{const r=await ejecutar(c,e);console.log(JSON.stringify({grupo:'G45',oficial:r.oficial,estados:Object.fromEntries(CASOS.map(k=>[k,r.casos[k].estado])),solicitudes:r.total_solicitudes_api}));}}
  }catch(err){console.error(clean(err.message));process.exitCode=2;}
}
