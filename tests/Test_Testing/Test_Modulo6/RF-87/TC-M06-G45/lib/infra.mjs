// Infraestructura: leerEnv/preflight de TC-M06-G43/g43.mjs (ORD-G43-008);
// forma de resultado contrastada con TC-M06-G40/Resultados/RUN-G40-V1-20261109-132609/resultado.json.
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {spawn} from 'node:child_process';

export const grupoDesdeCarpeta=carpeta=>path.basename(carpeta).match(/^TC-M06-(G\d+)$/)?.[1]??null;
export const sha256=archivo=>createHash('sha256').update(fs.readFileSync(archivo)).digest('hex');
export const categorias=new Set(['NINGUNO','PREFLIGHT_ENTORNO','AUTENTICACION','PERMISO','DATOS_PRECONDICION','CONTRATO','HERRAMIENTA_NEWMAN','HERRAMIENTA_CYPRESS_COMPILACION','HERRAMIENTA_CYPRESS_EJECUCION','SANDBOX','ROLLBACK','PRESUPUESTO','PRODUCTO']);

export function leerEnv(proceso,archivo){
  const e={};
  if(proceso.QA_AUTORIZADO==='SI'&&fs.existsSync(archivo)){
    for(const line of fs.readFileSync(archivo,'utf8').split(/\r?\n/)){
      const m=line.match(/^\s*([A-Z][A-Z0-9_]*)\s*=(.*)$/);
      if(m)e[m[1]]=m[2].trim().replace(/^(['"])(.*)\1$/,'$2');
    }
  }
  Object.assign(e,proceso);
  e.QA_AUTORIZADO=proceso.QA_AUTORIZADO;
  return e;
}

export function contexto(args,{capacidades,grupo,casos,dir,prueba=false}){
  const arg=k=>args.includes(k)?args[args.indexOf(k)+1]:null;
  const operacion=arg('--operacion');
  const version=Number(arg('--version'));
  const intento=Number(arg('--intento'));
  const runId=arg('--run-id');
  const ref=arg('--autorizacion');
  if(!capacidades.operaciones.includes(operacion)||!Number.isInteger(version)||version<capacidades.versiones.min||version>capacidades.versiones.max||!Number.isInteger(intento)||intento<1||!ref||!new RegExp(`^RUN-${grupo}-V${version}-\\d{8}-\\d{6}$`).test(runId??''))throw Error('CONTEXTO_INCOMPLETO');
  const archivo=arg('--contexto');
  const salida=prueba?path.dirname(path.resolve(archivo??'.')):path.join(dir,...(version===1?['Resultados',runId]:[`EvaluacionV${version}`,'Resultados',runId]));
  if(prueba&&(path.basename(salida)!==runId||!salida.startsWith(path.resolve(os.tmpdir())+path.sep)))throw Error('PRUEBA_FUERA_TEMPORAL');
  if(!archivo||path.resolve(archivo)!==path.join(salida,'contexto_operacion.json'))throw Error('CONTEXTO_FUERA_RUN');
  const c=JSON.parse(fs.readFileSync(archivo));
  if(c.grupo!==grupo||c.run_id!==runId||c.version!==version||c.intento!==intento||c.operacion!==operacion.toUpperCase()||c.referencia!==ref||JSON.stringify(c.casos)!==JSON.stringify(casos))throw Error('CONTEXTO_INCOHERENTE');
  if(operacion==='reintentar'&&c.version_anterior!=null)throw Error('CONTEXTO_INCOHERENTE');
  return{dir:salida,runId,version,intento,operacion,ref};
}

export function preflight(c,e,{grupo,api,front,efectos}){
  const falta=['QA_AUTORIZADO','SIGAB_API_TEST_BASE','QA_SANDBOX_SECRET','QA_CONTADOR_EMAIL','QA_CONTADOR_PASSWORD'].filter(k=>!String(e[k]??'').trim());
  if(e.QA_AUTORIZADO!=='SI'&&!falta.includes('QA_AUTORIZADO'))falta.push('QA_AUTORIZADO');
  if(String(e.SIGAB_API_TEST_BASE??'').replace(/\/+$/,'')!==api&&!falta.includes('SIGAB_API_TEST_BASE'))falta.push('SIGAB_API_TEST_BASE');
  if(String(e.SIGAB_FRONT_TEST_BASE??front).replace(/\/+$/,'')!==front)falta.push('SIGAB_FRONT_TEST_BASE');
  return{grupo,run_id:c.runId,version:c.version,referencia:c.ref,ok:falta.length===0,barreras:falta,efectos};
}

export function crearSolicitante({api,runId,secret,limite,solicitudes,esquema,validarLecturas,validarError,clean,id,token,inicio}){
  let ocupado=false;
  let cuenta=0;
  let escrituras=0;
  async function req(metodo,ruta,cuerpo,sinRun=false){
    if(ocupado)throw Error('PETICION_CONCURRENTE');
      ++cuenta;
      if(metodo!=='DELETE'&&!(sinRun&&metodo==='GET')&&(cuenta>limite.solicitudes_totales||Date.now()-inicio>1800000))throw Error('PRESUPUESTO_AGOTADO');
    if(!esquema(metodo,ruta)&&!(metodo==='GET'&&ruta==='/sesiones/me/permisos'))throw Error(`RUTA_FUERA_CONTRATO_${metodo}_${ruta}`);
    ocupado=true;
    const fila={id:id(cuenta),metodo,ruta:ruta.split('?')[0],http:null};
    solicitudes.push(fila);
    try{
      const headers={...(token()?{Authorization:`Bearer ${token()}`}:{})};
      if(!sinRun){headers['X-Test-Run-Id']=runId;headers['X-Sandbox-Secret']=secret;}
      if(cuerpo!==undefined)headers['Content-Type']='application/json';
      fila.hora_utc=new Date().toISOString();
      if(!sinRun&&['POST','PUT','PATCH'].includes(metodo))escrituras++;
      const respuesta=await fetch(api+ruta,{method:metodo,headers,...(cuerpo===undefined?{}:{body:JSON.stringify(cuerpo)}),signal:AbortSignal.timeout(120000)});
      fila.http=respuesta.status;
      fila.eco=respuesta.headers.get('x-test-run-id')===runId;
      const raw=respuesta.status===204?{}:await respuesta.json().catch(()=>null);
      if(respuesta.status>=400){
        fila.error=clean(raw?.error_code);
        fila.error_contrato=validarError(raw);
        return{http:respuesta.status,data:raw,hora_utc:fila.hora_utc};
      }
      const data=metodo==='DELETE'?raw:validarLecturas(raw,metodo,ruta,{estricto:false,camposExtra:new Set()});
      return{http:respuesta.status,data,hora_utc:fila.hora_utc};
    }finally{ocupado=false;}
  }
  return{req,total:()=>cuenta,escrituras:()=>escrituras};
}

export async function lanzarHijo({base,script,input,timeout=300000,env=process.env,clean}){
  return new Promise((resolve,reject)=>{
    const p=spawn(process.execPath,[path.join(base,'pruebas',script)],{stdio:['pipe','pipe','pipe'],windowsHide:true,timeout,env});
    let out='',err='';
    p.stdout.on('data',d=>out+=d);
    p.stderr.on('data',d=>err+=d);
    p.on('error',reject);
    p.on('close',code=>{
      try{resolve({code,data:JSON.parse(out),error:clean(err)});}
      catch{resolve({code,data:null,error:clean(err||out)});}
    });
    p.stdin.end(JSON.stringify(input));
  });
}

export function listarEvidencias(dir,rel=''){
  if(!fs.existsSync(dir))return [];
  const out=[];
  for(const e of fs.readdirSync(dir,{withFileTypes:true})){
    const archivo=path.join(dir,e.name);
    const nombre=rel?rel+'/'+e.name:e.name;
    if(e.isDirectory())out.push(...listarEvidencias(archivo,nombre));
    else out.push(nombre);
  }
  return out;
}

export function guardarResultado(c,r,informe){
  const nombre=c.version===1?`TC-M06-${r.grupo}_resultado.md`:`TC-M06-${r.grupo}_reevaluacion_V${c.version}.md`;
  const texto=informe(r);
  fs.writeFileSync(path.join(c.dir,'resultado.json'),JSON.stringify(r,null,2));
  fs.writeFileSync(path.join(c.dir,nombre),texto);
}

export function clasificarFallo(resultado){
  if(!resultado.cierre?.rollback?.verificado)return 'ROLLBACK';
  const tecnicos=resultado.problemas_tecnicos??[];
  if(tecnicos.some(x=>/CYPRESS.*(?:Compilation|compile|Webpack)/i.test(x)))return 'HERRAMIENTA_CYPRESS_COMPILACION';
  if(tecnicos.some(x=>/CYPRESS/i.test(x)))return 'HERRAMIENTA_CYPRESS_EJECUCION';
  if(tecnicos.some(x=>/NEWMAN/i.test(x)))return 'HERRAMIENTA_NEWMAN';
  if(tecnicos.some(x=>/PRESUPUESTO/i.test(x)))return 'PRESUPUESTO';
  if(tecnicos.some(x=>/SANDBOX|DELETE/i.test(x)))return 'SANDBOX';
  if(tecnicos.some(x=>/LOGIN/i.test(x)))return 'AUTENTICACION';
  if(tecnicos.some(x=>/PERMISO/i.test(x)))return 'PERMISO';
  if(tecnicos.some(x=>/PREFLIGHT|ACTIVO_|PRECIO_BASE|MATRIZ_SIN_PAR/i.test(x)))return 'DATOS_PRECONDICION';
  if(tecnicos.length)return 'CONTRATO';
  if(Object.values(resultado.casos??{}).some(x=>x.estado==='RECHAZADO'))return 'PRODUCTO';
  return 'NINGUNO';
}

export function validarFormaResultado(resultado,capacidades,runDir){
  const errores=[];
  const grupo=grupoDesdeCarpeta(path.resolve(runDir,'..','..'))??capacidades.grupo;
  if(resultado.grupo!==grupo||(/^RUN-G\d+-V/.test(path.basename(runDir))&&resultado.run_id!==path.basename(runDir)))errores.push('identidad');
  if(!categorias.has(resultado.clasificacion_fallo))errores.push('clasificacion_fallo');
  if(typeof resultado.cierre?.run?.cierre_http!=='number'&&resultado.cierre?.run?.cierre_http!==null)errores.push('cierre.run.cierre_http');
  if(typeof resultado.cierre?.rollback?.verificado!=='boolean')errores.push('cierre.rollback.verificado');
  if(!Number.isInteger(resultado.cypress?.total_pruebas))errores.push('cypress.total_pruebas');
  if(typeof resultado.oficial!=='boolean'||typeof resultado.consume_version!=='boolean')errores.push('oficial/consume_version');
  if(!resultado.casos||JSON.stringify(Object.keys(resultado.casos).sort())!==JSON.stringify([...capacidades.casos].sort()))errores.push('casos');
  if(!Array.isArray(resultado.evidencias)||resultado.evidencias.some(x=>path.isAbsolute(x)||x.includes('..')||!fs.existsSync(path.join(runDir,x))))errores.push('evidencias');
  for(const [caso,fuentes] of Object.entries(capacidades.comprobaciones_obligatorias)){
    for(const [fuente,ids] of Object.entries(fuentes))for(const id of ids){
      const z=resultado.comprobaciones?.find(x=>x.caso===caso&&x.fuente===fuente&&x.id===id&&x.tipo==='ASSERT'&&['APROBADO','RECHAZADO'].includes(x.estado));
      if(resultado.oficial&&!z)errores.push(`comprobacion:${id}`);
    }
  }
  const requiereUI=Object.values(capacidades.comprobaciones_obligatorias??{}).some(f=>Array.isArray(f.UI)&&f.UI.length>0);
  if(resultado.oficial&&(!resultado.cierre.rollback.verificado||resultado.cierre.run.cierre_http!==200||(requiereUI&&resultado.cypress.total_pruebas===0)))errores.push('oficial_incompleto');
  return errores;
}

export function clasificarRegistro(cap,r,presentes,ctx){
  const grupo=cap.grupo;
  const informe=r.version===1?`TC-M06-${grupo}_resultado.md`:`TC-M06-${grupo}_reevaluacion_V${r.version}.md`;
  const existe=x=>typeof x==='string'&&x.length>0&&!path.isAbsolute(x)&&!path.win32.isAbsolute(x)&&!x.split(/[\\/]/).includes('..')&&presentes.has(x);
  const paneles=Object.keys(r.cypress?.paneles??{});
  const requiereUI=Object.values(cap.comprobaciones_obligatorias??{}).some(f=>Array.isArray(f.UI)&&f.UI.length>0);
  const ui=!requiereUI||(paneles.length>0&&paneles.every(n=>{
    const p=r.cypress.paneles[n];
    return p?.totalTests>0&&p.codigo===0&&['APROBADO','RECHAZADO'].includes(p.estado)&&existe(p.evidencia)&&[...presentes].some(x=>x.startsWith(`cypress/${n}/screenshots/`)&&x.endsWith('.png'));
  }));
  return r.grupo===grupo&&r.run_id===ctx.runId&&r.autorizacion_referencia===ctx.referencia&&r.version===ctx.version&&r.oficial===true&&r.consume_version===true&&r.cierre?.run?.cierre_http===200&&r.cierre?.rollback?.verificado===true&&r.rollback?.verificado===true&&r.herramientas?.newman?.codigo===0&&r.herramientas.newman.fallos===0&&r.herramientas.newman.reportes===true&&r.total_solicitudes_api<=cap.limite.solicitudes_totales&&JSON.stringify(Object.keys(r.casos).sort())===JSON.stringify([...cap.casos].sort())&&cap.casos.every(c=>['APROBADO','RECHAZADO'].includes(r.casos[c].estado)&&r.casos[c].comprobaciones?.length>0)&&Object.entries(cap.comprobaciones_obligatorias).every(([caso,fuentes])=>Object.entries(fuentes).every(([fuente,ids])=>ids.every(id=>r.comprobaciones?.some(x=>x.caso===caso&&x.id===id&&x.fuente===fuente&&x.tipo==='ASSERT'&&['APROBADO','RECHAZADO'].includes(x.estado)&&existe(x.evidencia)))))&&ui&&[...presentes].filter(x=>x.toLowerCase().endsWith('.md')).length===1&&['resultado.json',informe,`newman/newman-${grupo}.json`,`newman/newman-${grupo}.html`].every(existe)&&r.evidencias?.every(existe);
}
