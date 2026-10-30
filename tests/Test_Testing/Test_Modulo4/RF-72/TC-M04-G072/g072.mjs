#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import {CASOS,IDS,PRESUPUESTO,CAPACIDADES,iguales,seleccionar,retro,retrosDe,decision} from './lib/g072_core.mjs';

const DIR=path.dirname(fileURLToPath(import.meta.url)),RAIZ=path.resolve(DIR,'../../../../..'),require=createRequire(import.meta.url);
const API='https://www.api.inmero.co/api-sgpmp-test';
const COL=JSON.parse(fs.readFileSync(path.join(DIR,'G072.postman_collection.json'),'utf8'));
const NOMBRES=COL.item.map(x=>x.name);
const fecha=x=>new Intl.DateTimeFormat('en-CA',{timeZone:'America/Bogota',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(x));
const nombreInforme=v=>v===1?'TC-M04-G072_resultado.md':`TC-M04-G072_reevaluacion_V${v}.md`;
const limpio=x=>String(x??'').replace(/[\r\n|]/g,' ');
const guardar=(p,x)=>fs.writeFileSync(p,JSON.stringify(x,null,2),'utf8');
const esc=x=>String(x).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function sanear(x,secretos=[]){let s=String(x);for(const v of secretos.filter(v=>typeof v==='string'&&v.length>3))s=s.split(v).join('[REDACTADO]');
  return s.replace(/eyJ[\w-]{5,}\.[\w-]{5,}\.[\w-]{5,}/g,'[JWT_REDACTADO]')
    .replace(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/gi,'[CORREO_REDACTADO]');}
function newmanDir(){try{return path.dirname(require.resolve('newman/package.json',{paths:[RAIZ]}));}
  catch{return [process.execPath,...String(process.env.PATH??'').split(path.delimiter)]
    .map(x=>path.join(path.dirname(x),'node_modules','newman','package.json')).find(fs.existsSync)?.replace(/[\\/]package\.json$/,'')??null;}}
function versionNewman(){try{return {ok:true,version:require(path.join(newmanDir(),'package.json')).version};}catch{return {ok:false,error:'NEWMAN_NO_DISPONIBLE'};}}
export function leerEnv(proceso=process.env,archivo=path.join(RAIZ,'.env.qa')){
  const e={};if(fs.existsSync(archivo))for(const linea of fs.readFileSync(archivo,'utf8').split(/\r?\n/)){
    const m=linea.match(/^\s*([A-Z][A-Z0-9_]*)\s*=(.*)$/);if(m)e[m[1]]=m[2].trim().replace(/^(['"])(.*)\1$/,'$2');}
  Object.assign(e,proceso);e.QA_AUTORIZADO=proceso.QA_AUTORIZADO;return e;
}
export function preflight(c,env=leerEnv(),newman=versionNewman()){
  const barreras=['SIGAB_API_TEST_BASE','QA_SANDBOX_SECRET','QA_VETERINARIO_EMAIL','QA_VETERINARIO_B_EMAIL','QA_VETERINARIO_C_EMAIL','QA_COMMON_PASSWORD']
    .filter(k=>!String(env[k]??'').trim());
  if(env.QA_AUTORIZADO!=='SI')barreras.push('QA_AUTORIZADO');if(!newman.ok)barreras.push('NEWMAN_NO_DISPONIBLE');
  const base=String(env.SIGAB_API_TEST_BASE??'').replace(/\/+$/,'');
  if(c.ensayo?!/^http:\/\/(127\.0\.0\.1|localhost):\d+$/.test(base):base!==API)barreras.push('API_NO_CANONICA');
  if(COL.item.length!==14||new Set(NOMBRES).size!==14||COL.item.filter(x=>x.request.method==='POST').length!==9||
    COL.item.filter(x=>x.request.method==='GET').length!==5)barreras.push('COLECCION_INVALIDA');
  return {grupo:'G072',run_id:c.runId,ok:!barreras.length,barreras,presupuesto:PRESUPUESTO,herramientas:{newman},
    efectos:['Tres logins Veterinario A, B y C; último acceso y auditoría de autenticación',
      'Lecturas de historial, patologías, modelo y auditoría RF-73',
      'Nueve retroalimentaciones y eventos de auditoría, revertidos mediante DELETE',
      'Lecturas poscierre pueden crear HISTORIAL_CONSULTADO fuera del sandbox; sin correos ni archivos externos']};
}
export function comprobar(){const archivos=['g072.mjs','G072.postman_collection.json','lib/g072_core.mjs','pruebas/g072_ensayo.mjs','pruebas/g072_env.test.mjs','pruebas/registro_qa.mjs','README.md'];
  const faltantes=archivos.filter(x=>!fs.existsSync(path.join(DIR,x)));
  const superior=fs.existsSync(path.join(DIR,'Resultados'))&&fs.readdirSync(path.join(DIR,'Resultados')).some(x=>x.endsWith('.md'));
  const n=versionNewman(),ok=!faltantes.length&&!superior&&n.ok&&COL.item.length===14;
  console.log(JSON.stringify({grupo:'G072',ok,faltantes,markdown_superior:superior,newman:n,presupuesto:PRESUPUESTO}));return ok?0:2;}
function contexto(args){const v=k=>args.includes(k)?args[args.indexOf(k)+1]:undefined;
  const operacion=v('--operacion'),version=Number(v('--version')),intento=Number(v('--intento')),runId=v('--run-id'),referencia=v('--autorizacion'),archivo=v('--contexto');
  if(!CAPACIDADES.operaciones.includes(operacion)||!Number.isInteger(version)||version<1||!Number.isInteger(intento)||intento<1||!referencia||!archivo||
    !new RegExp(`^RUN-G072-V${version}-\\d{8}-\\d{6}$`).test(runId??''))throw Error('Contexto incompleto');
  const destino=path.join(DIR,...(version===1?['Resultados',runId]:[`EvaluacionV${version}`,'Resultados',runId]));
  const ruta=path.resolve(archivo);
  if(path.dirname(ruta)!==destino||!(operacion==='recuperar'?/^recuperacion-\d{14}\.contexto\.json$/.test(path.basename(ruta)):path.basename(ruta)==='contexto_operacion.json'))throw Error('Contexto fuera del RUN canónico');
  const c=JSON.parse(fs.readFileSync(ruta,'utf8'));
  if(c.grupo!=='G072'||c.run_id!==runId||c.version!==version||c.intento!==intento||c.operacion!==operacion.toUpperCase()||c.referencia!==referencia||
    JSON.stringify(c.casos)!==JSON.stringify(CASOS)||operacion==='reevaluar'&&(version<2||c.version_anterior!==version-1||!c.alcance_reevaluacion)||
    operacion==='recuperar'&&v('--run-objetivo')!==runId)throw Error('Contexto incoherente');
  return {operacion,version,intento,runId,referencia,directorio:destino,ensayo:false};}
async function pedir(r,api,metodo,ruta,{token,secreto,runId,cuerpo,timeout=PRESUPUESTO.timeout_ms,caso}={}){
  if(r.solicitudes.length>=PRESUPUESTO.solicitudes_totales&&metodo!=='DELETE')throw Error('PRESUPUESTO_AGOTADO');
  const fila={caso:caso??null,metodo,ruta:ruta.split('?')[0],http:null};r.solicitudes.push(fila);
  try{const inicio=Date.now();if(inicio>=r._limite&&metodo!=='DELETE')throw Error('DURACION_EXCEDIDA');
    const res=await fetch(api+ruta,{method:metodo,redirect:'manual',headers:{...(cuerpo?{'Content-Type':'application/json'}:{}),
      ...(token?{Authorization:`Bearer ${token}`}:{}) ,...(secreto?{'X-Sandbox-Secret':secreto}:{}),
      ...(runId?{'X-Test-Run-Id':runId,'X-Zona-Horaria':'America/Bogota'}:{})},body:cuerpo?JSON.stringify(cuerpo):undefined,
      signal:AbortSignal.timeout(Math.max(1,Math.min(timeout,metodo==='DELETE'?timeout:r._limite-inicio)))});
    const b=await res.json().catch(()=>null);Object.assign(fila,{http:res.status,eco:runId?res.headers.get('x-test-run-id')===runId:null,
      duracion_ms:Date.now()-inicio,respuesta:ruta==='/sesiones/'?{token_recibido:!!b?.token}:
        {error_code:b?.error_code??null,message:limpio(b?.message??''),total:b?.total??null}});
    r._seguidos5xx=res.status>=500?(r._seguidos5xx??0)+1:0;
    if(r._seguidos5xx>=3&&!r.problemas_tecnicos?.includes('TRES_5XX_CONSECUTIVOS'))r.problemas_tecnicos?.push('TRES_5XX_CONSECUTIVOS');
    return {http:res.status,cuerpo:b,eco:fila.eco};
  }catch(e){fila.tipo_fallo=['TimeoutError','AbortError'].includes(e.name)?'TIMEOUT':'SIN_RED';return {http:null,cuerpo:null,eco:false};}}
const rutaHist=(inicio,fin,cursor)=>`/prediccion/historial/885?fecha_inicio=${inicio}&fecha_fin=${fin}&incluir_alertas=false${cursor?`&cursor_paginacion=${encodeURIComponent(cursor)}`:''}`;
async function historial(r,api,token,secreto,runId,inicio,fin){const eventos=[];let cursor=null;
  for(let i=0;i<40;i++){const x=await pedir(r,api,'GET',rutaHist(inicio,fin,cursor),{token,secreto,runId});
    if(x.http!==200||x.eco!==true||!Array.isArray(x.cuerpo?.eventos))return {eventos,completo:false,http:x.http};
    eventos.push(...x.cuerpo.eventos);cursor=x.cuerpo.cursor_siguiente;if(!cursor)return {eventos,completo:true,http:200};}
  return {eventos,completo:false,http:200,cursor_pendiente:true};}
function usuarioToken(t){try{return String(JSON.parse(Buffer.from(String(t).split('.')[1],'base64url')).sub);}catch{return null;}}
const casoDe=n=>n.startsWith('226')?CASOS[0]:n.startsWith('227')?CASOS[1]:CASOS[2];
const referencia=x=>encodeURIComponent(String(x));
async function auditoria(r,api,token,secreto,runId,id){const x=await pedir(r,api,'GET',`/prediccion/auditoria?id_referencia=${referencia(id)}&por_pagina=200`,{token,secreto,runId});
  return {http:x.http,completo:x.http===200&&x.eco===true&&Array.isArray(x.cuerpo?.items)&&Number(x.cuerpo?.total)<=200,items:x.cuerpo?.items??[]};}
async function newmanUnico(r,c,api,env,tokens,sel,diag,inicio,fin){
  const col=structuredClone(COL),valores={base_url:api,run_id:c.runId,sandbox_secret:env.QA_SANDBOX_SECRET,
    historial_url:api+rutaHist(inicio,fin),consecutivos_5xx:String(r._seguidos5xx??0)};
  const datos={'226-A':[0,'A','CORRECTO'],'226-B':[0,'B','INCORRECTO'],
    '227-A':[1,'A','CORRECTO'],'227-B':[1,'B','PARCIAL'],'227-C':[1,'C','INCORRECTO'],
    '230a-A':[2,'A','CORRECTO'],'230a-B':[2,'B','CORRECTO'],
    '230b-A':[3,'A','INCORRECTO'],'230b-B':[3,'B','INCORRECTO']};
  for(const item of col.item){
    const esGet=item.request.method==='GET',u=esGet?'A':datos[item.name][1],estado=esGet?null:datos[item.name][2];
    item.request.header=[{key:'Authorization',value:`Bearer {{token_${u}}}`},{key:'X-Test-Run-Id',value:'{{run_id}}'},
      {key:'X-Sandbox-Secret',value:'{{sandbox_secret}}'},{key:'X-Zona-Horaria',value:'America/Bogota'},{key:'Content-Type',value:'application/json'}];
    if(!esGet){const cuerpo={id_resultado_inferencia:sel[datos[item.name][0]].id_resultado_inferencia,id_activo_biologico:885,estado_retroalimentacion:estado};
      if(estado!=='CORRECTO')cuerpo.diagnosticos_reales=[diag];
      valores[`body_${item.name.replace('-','_')}`]=JSON.stringify(cuerpo);}
    item.event=[{listen:'test',script:{type:'text/javascript',exec:[
      "const key='consecutivos_5xx';const n=pm.response.code>=500?Number(pm.environment.get(key)||0)+1:0;pm.environment.set(key,String(n));",
      ...(esGet?["let b={};try{b=pm.response.json()}catch{};const base=pm.environment.get('historial_url').split('&cursor_paginacion=')[0];const p=Number(pm.environment.get('paginas_actuales')||0)+1;if(pm.response.code===200&&b.cursor_siguiente&&p<40){pm.environment.set('paginas_actuales',String(p));pm.environment.set('historial_url',base+'&cursor_paginacion='+encodeURIComponent(b.cursor_siguiente));postman.setNextRequest(pm.info.requestName)}else{pm.environment.set('paginas_actuales','0');pm.environment.set('historial_url',base)}"]:[]),
      "if((pm.response.code===403&&/clave|secreto|sandbox/i.test(pm.response.text()))||n>=3)postman.setNextRequest(null);",
      "pm.test('HTTP recibido',()=>pm.expect(pm.response.code).to.be.above(0));",
      "pm.test('Eco de RUN',()=>pm.expect(pm.response.headers.get('X-Test-Run-Id')).to.eql(pm.environment.get('run_id')));"
    ]}}];
  }
  for(const [u,t] of Object.entries(tokens))valores[`token_${u}`]=t;
  if(!tokens.C)col.item=col.item.filter(x=>!['227-C','historial_tras_227_final'].includes(x.name));
  const environment={values:Object.entries(valores).map(([key,value])=>({key,value,enabled:true}))};
  let error,summary;try{[error,summary]=await new Promise(ok=>require(newmanDir()).run({collection:col,environment,
    reporters:['cli'],silent:true,timeoutRequest:30000,timeout:Math.max(1,r._limite-Date.now()),ignoreRedirects:true,color:'off'},(e,s)=>ok([e,s])));}catch(e){error=e;}
  const ejec={},lecturas={},reporte={herramienta:'Newman',version:r.herramientas.newman.version,error:error?limpio(error.message):null,
    solicitudes:[],fallos:(summary?.run?.failures??[]).map(f=>({tipo:f.error?.name??'Error',mensaje:limpio(f.error?.message)}))};
  let seguidos=r._seguidos5xx??0;
  for(const ex of summary?.run?.executions??[]){let b=null;try{b=JSON.parse(ex.response?.stream?.toString('utf8')??'');}catch{}
    const n=ex.item?.name,http=ex.response?.code??null,eco=ex.response?.headers?.get?.('x-test-run-id')===c.runId||
      ex.response?.header?.find?.(h=>String(h.key).toLowerCase()==='x-test-run-id')?.value===c.runId;
    if(!n)continue;
    const esGet=n.startsWith('historial_'),momento=n.replace('historial_tras_','');
    const fila={caso:esGet?momento.startsWith('230')?CASOS[2]:momento==='226'?CASOS[0]:CASOS[1]:casoDe(n),nombre:n,
      metodo:esGet?'GET':'POST',ruta:esGet?'/prediccion/historial/885':'/prediccion/retroalimentacion',http,eco,herramienta:'Newman',duracion_ms:ex.response?.responseTime??null,
      respuesta:{id_retroalimentacion:b?.id_retroalimentacion??null,es_conflicto_retroalimentacion:b?.es_conflicto_retroalimentacion??null,
        error_code:b?.error_code??null,message:limpio(b?.message??'')}};
    r.solicitudes.push(fila);reporte.solicitudes.push({...fila,aserciones:(ex.assertions??[]).map(a=>({nombre:a.assertion,error:a.error?.message??null}))});
    if(esGet){const z=lecturas[momento]??={momento,tras_post:{'230a':'230a-B','230b':'230b-B','226':'226-B','227_parcial':'227-B','227_final':'227-C'}[momento],
        http:null,codigo:null,mensaje:'',eventos:[],paginas:0,completo:false};
      z.http=http;z.codigo=b?.error_code??null;z.mensaje=limpio(b?.message??'');z.paginas++;
      if(http===200&&eco&&Array.isArray(b?.eventos)){z.eventos.push(...b.eventos);z.completo=!b.cursor_siguiente;}
      else z.completo=false;
      z.registros_por_resultado=sel.map(s=>({id_resultado_inferencia:s.id_resultado_inferencia,
        registros:retrosDe(z.eventos,s.id_resultado_inferencia).map(e=>({id_retroalimentacion:e.payload?.id_retroalimentacion??null,
          id_usuario_veterinario:e.payload?.id_usuario_veterinario??null,estado:e.payload?.estado_retroalimentacion??null}))}));
    }else{ejec[n]={http,cuerpo:b,eco};}
    seguidos=http>=500?seguidos+1:0;
    if(seguidos>=3&&!r.problemas_tecnicos.includes('TRES_5XX_CONSECUTIVOS'))r.problemas_tecnicos.push('TRES_5XX_CONSECUTIVOS');
    if(http===403&&/clave|secreto|sandbox/i.test(String(b?.message??b?.detail??'')))r.problemas_tecnicos.push('CLAVE_403');
  }
  r._seguidos5xx=seguidos;
  r.lecturas_historial=['230a','230b','226','227_parcial','227_final'].map(x=>lecturas[x]).filter(Boolean);
  r.herramientas.newman.iteraciones=summary?.run?.stats?.iterations?.total??(summary?1:0);
  r.herramientas.newman.solicitudes=reporte.solicitudes.length;
  r.herramientas.newman.posts=reporte.solicitudes.filter(x=>x.metodo==='POST').length;
  r.herramientas.newman.lecturas=reporte.solicitudes.filter(x=>x.metodo==='GET').length;
  r.herramientas.newman.aserciones=reporte.solicitudes.reduce((v,x)=>v+x.aserciones.length,0);
  if(error)r.problemas_tecnicos.push(`Newman: ${limpio(error.message)}`);
  const sub=path.join(c.directorio,'newman');fs.mkdirSync(sub,{recursive:true});
  const secretos=[...Object.values(tokens),env.QA_SANDBOX_SECRET,env.QA_COMMON_PASSWORD,env.QA_VETERINARIO_EMAIL,env.QA_VETERINARIO_B_EMAIL,env.QA_VETERINARIO_C_EMAIL];
  const json=sanear(JSON.stringify(reporte,null,2),secretos);fs.writeFileSync(path.join(sub,'newman-G072.json'),json);
  fs.writeFileSync(path.join(sub,'newman-G072.html'),`<!doctype html><html lang="es"><meta charset="utf-8"><title>Newman G072</title><pre>${esc(json)}</pre></html>`);
  r.evidencias.push('newman/newman-G072.json','newman/newman-G072.html');return ejec;
}
function evaluarCasos(r,ejec,sel,audAntes,audDespues,audReg,usuarios,diag){
  const de=n=>ejec[n]??null,ok=n=>de(n)?.http==null?null:de(n).http===201&&de(n).eco===true;
  const nombres=[['226-A','226-B'],['227-A','227-B','227-C'],['230a-A','230a-B','230b-A','230b-B']];
  const auditNew=i=>audAntes[i]?.completo&&audDespues[i]?.completo?
    audDespues[i].items.filter(x=>!new Set(audAntes[i].items.map(y=>String(y.id_evento))).has(String(x.id_evento))):null;
  const lecturas=Object.fromEntries(r.lecturas_historial.map(x=>[x.momento,x]));
  const orden=['230a','230b','226','227_parcial','227_final'];
  const primera=r.lecturas_historial.find(x=>x.http===500),indice500=primera?orden.indexOf(primera.momento):-1;
  const lecturaCaso=['226','227_final','230b'].map(x=>lecturas[x]);
  const sinHist=i=>indice500>=0&&orden.indexOf(lecturaCaso[i]?.momento)>=indice500&&lecturaCaso[i]?.completo!==true;
  const historiales=lecturaCaso.map(x=>x?.completo?x.eventos:null);
  const eventos=nombres.map((ns,i)=>ns.map(n=>retro(historiales[i]??[],de(n)?.cuerpo?.id_retroalimentacion)));
  const cuenta=i=>{const h=historiales[i<2?i:2];return h?retrosDe(h,sel[i].id_resultado_inferencia).length:null;};
  const identidad=(n,e)=>{if(!e)return null;const b=de(n)?.cuerpo,p=e.payload??{};
    return String(p.id_retroalimentacion)===String(b?.id_retroalimentacion)&&
      String(e.id_resultado_inferencia)===String(b?.id_resultado_inferencia)&&
      String(p.id_usuario_veterinario)===String(b?.id_usuario_veterinario)&&
      p.estado_retroalimentacion===b?.estado_retroalimentacion&&iguales(p.diagnosticos_reales??null,b?.diagnosticos_reales??null);};
  const envio=(n)=>{const b=de(n)?.cuerpo;if(!b)return null;
    const indice=n.startsWith('226')?0:n.startsWith('227')?1:n.startsWith('230a')?2:3;
    const estado=n==='226-B'||n==='227-C'||n.startsWith('230b')?'INCORRECTO':n==='227-B'?'PARCIAL':'CORRECTO';
    const esperadoDiag=estado==='CORRECTO'?null:[diag];
    const u=n.endsWith('-A')?'A':n.endsWith('-B')?'B':'C';
    return String(b.id_resultado_inferencia)===String(sel[indice].id_resultado_inferencia)&&
      String(b.id_usuario_veterinario)===String(usuarios[u])&&b.estado_retroalimentacion===estado&&
      iguales(b.diagnosticos_reales??null,esperadoDiag);};
  const refOk=(n)=>{const id=de(n)?.cuerpo?.id_retroalimentacion,a=audReg[n];return a?.completo?
    a.items.filter(x=>x.tipo_evento==='RETROALIMENTACION_REGISTRADA'&&String(x.id_referencia)===String(id)).length===1:null;};
  const conf=i=>auditNew(i)?.filter(x=>x.tipo_evento==='CONFLICTO_RETROALIMENTACION')??null;
  const conf226=conf(0),payload226=conf226?.[0]?.payload_evento??conf226?.[0]?.payload??null;
  const c226=decision([...nombres[0].map(ok),...nombres[0].map(envio),de('226-A')?.cuerpo?.es_conflicto_retroalimentacion===false,
    de('226-B')?.cuerpo?.es_conflicto_retroalimentacion===true,
     historiales[0]?cuenta(0)===2:sinHist(0)?true:null,...eventos[0].map((e,i)=>historiales[0]?identidad(nombres[0][i],e):sinHist(0)?true:null),...nombres[0].map(refOk),
    conf226?conf226.length===1:null,conf226?.length===1?String(conf226[0].id_referencia)===String(sel[0].id_resultado_inferencia):null,
    payload226?payload226.id_resultado_inferencia===String(sel[0].id_resultado_inferencia)&&
      ['CORRECTO','INCORRECTO'].every(x=>payload226.estados_registrados?.includes(x)):null]);
  const c227=decision([...nombres[1].map(ok),...nombres[1].map(envio),historiales[1]?cuenta(1)===3:sinHist(1)?true:null,...eventos[1].map((e,i)=>historiales[1]?identidad(nombres[1][i],e):sinHist(1)?true:null),
    ...nombres[1].map(refOk),auditNew(1)?auditNew(1).every(x=>['CONFLICTO_RETROALIMENTACION'].includes(x.tipo_evento)):null]);
  const c230=decision([...nombres[2].map(ok),...nombres[2].map(envio),...nombres[2].map(n=>de(n)?.cuerpo?.es_conflicto_retroalimentacion===false),
     historiales[2]?cuenta(2)===2&&cuenta(3)===2:sinHist(2)?true:null,...eventos[2].map((e,i)=>historiales[2]?identidad(nombres[2][i],e):sinHist(2)?true:null),...nombres[2].map(refOk),
    conf(2)?conf(2).length===0:null,conf(3)?conf(3).length===0:null]);
  const estados=[c226,c227,c230];
  const bloquea=r.problemas_tecnicos.some(x=>/TRES_5XX|CLAVE_403/.test(x));
  const referencias=[
    'Dos HTTP 201; B con conflicto y un evento CONFLICTO_RETROALIMENTACION que referencia R1; A intacto (matriz G072, TC-M04-226; RF-72, líneas 4053-4061 y CA-14, 4393-4394).',
    'Tres registros independientes, íntegros y sin consolidado ni etiqueta ganadora (matriz G072, TC-M04-227; RF-72, líneas 4043-4051 y 4065).',
    'Dos evaluaciones iguales por resultado coexisten, sin flag ni evento de conflicto (matriz G072, TC-M04-230; RF-72, líneas 4024 y 4053-4061).'];
  const hechos=[
    `Se enviaron CORRECTO por A e INCORRECTO con patología ${diag} por B sobre ${sel[0].id_resultado_inferencia}; se leyeron historial y auditoría.`,
    `Se enviaron CORRECTO, PARCIAL e INCORRECTO por A, B y C sobre ${sel[1].id_resultado_inferencia}; se leyó historial y auditoría.`,
    `A y B enviaron CORRECTO sobre ${sel[2].id_resultado_inferencia} e INCORRECTO con la misma patología ${diag} sobre ${sel[3].id_resultado_inferencia}; se leyeron historial y auditoría.`];
  const observados=nombres.map((ns,i)=>`HTTP ${ns.map(n=>`${n}=${de(n)?.http??'sin respuesta'}`).join(', ')}; registros ${ns.map(n=>{
    const b=de(n)?.cuerpo;return `${n}: id ${b?.id_retroalimentacion??'ausente'}, usuario ${b?.id_usuario_veterinario??'ausente'}, estado ${b?.estado_retroalimentacion??'ausente'}, diagnósticos ${JSON.stringify(b?.diagnosticos_reales??null)}, conflicto ${b?.es_conflicto_retroalimentacion==null?'sin dato':b.es_conflicto_retroalimentacion?'sí':'no'}`;}).join('; ')}; historial ${i===2?`${cuenta(2)??'sin lectura'}/${cuenta(3)??'sin lectura'}`:cuenta(i)??'sin lectura'} registros; eventos de conflicto ${i===2?`${conf(2)?.length??'sin lectura'}/${conf(3)?.length??'sin lectura'}`:conf(i)?.length??'sin lectura'}; referencias de auditoría ${i===2?[2,3].flatMap(j=>conf(j)?.map(x=>`${x.id_evento}:${x.id_referencia}`)??[]).join(', ')||'ninguna':conf(i)?.map(x=>`${x.id_evento}:${x.id_referencia}`).join(', ')||'ninguna'}.`);
  const razones=['El segundo registro contradice al primero; el indicador, el evento y la conservación de A se cotejan en respuestas y lecturas públicas.',
    'Cada respuesta se coteja por identificador, usuario, estado y diagnóstico con un registro de historial; no hay cuarto registro ni evento de consolidación.',
    'Cada par conserva sus dos registros y las respuestas y auditoría no señalan conflicto.'];
  for(let i=0;i<3;i++){
    const ns=nombres[i],cinco=r.solicitudes.some(x=>x.caso===CASOS[i]&&x.herramienta==='Newman'&&x.metodo==='POST'&&x.http>=500);
    const sinRespuesta=ns.some(n=>de(n)?.http==null);
     const disparador=primera&&(i===2&&primera.momento.startsWith('230')||i===0&&primera.momento==='226'||i===1&&primera.momento.startsWith('227'));
     const estado=bloquea?'BLOQUEADO':i===1&&!usuarios.C||sinRespuesta?'NO_CONCLUYENTE':disparador||cinco?'RECHAZADO':estados[i];
    const motivo=bloquea?'Corte técnico por clave 403 o tres respuestas 5xx consecutivas':i===1&&!usuarios.C?'No inició sesión la cuenta C; falta su evaluación independiente':
       sinRespuesta?'Una solicitud obligatoria no recibió respuesta HTTP':disparador?`Primer HTTP 500 del historial tras ${primera.tras_post}: ${primera.codigo??'sin código'}; ${primera.mensaje||'sin mensaje'}`:cinco?'Una escritura obligatoria respondió 5xx':
      estado==='APROBADO'?razones[i]:estado==='RECHAZADO'?
        [`La contradicción de R1 no quedó confirmada con dos registros, indicador y evento íntegros`,
          `La coexistencia de los tres registros de R2 no quedó confirmada sin alteración ni consolidación`,
          `Alguno de los dos pares iguales mostró conflicto o no conservó ambos registros`][i]:
      'Falta lectura pública completa para concluir';
    r.casos[CASOS[i]]={estado,motivo,que_se_hizo:hechos[i],esperado_referencia:referencias[i],observado_prosa:observados[i],por_que_prosa:razones[i]};
    r.comprobaciones.push({caso:CASOS[i],fuente:'API',id:IDS[i],tipo:'ASSERT',estado,evidencia:'newman/newman-G072.json'});
     if(estado==='RECHAZADO')r.incidencias.push({id:`INC-M04-G072-${CASOS[i].slice(-3)}-01`,caso:CASOS[i],equipo:'Desarrollo',
       fundamento_derivacion:disparador?`Primera discrepancia comprobada en GET /prediccion/historial/885 tras ${primera.tras_post}, HTTP 500 ${primera.codigo??'sin código'}: ${primera.mensaje||'sin mensaje'}`:'Primera discrepancia comprobada en la API pública de RF-72',
       causa_raiz:'NO DETERMINADA',causa_probable:disparador?'Antecedente documentado por el responsable QA: el log TEST del intento 1 registra un INSERT en historial_diagnostico_eventos rechazado por RLS. Contrastar el log de este RUN antes de atribuirle la misma causa.':null,
       certeza:'CONFIRMADA',severidad:'ALTA',justificacion_severidad:disparador?'La retroalimentación deja de ser consultable en historial (RF-72 CA-8, línea 4378; Regla 3, líneas 4043-4051).':'El escenario clínico exigido pierde detección, integridad o ausencia de falso conflicto; la funcionalidad relevante queda afectada.'});
  }
  for(let i=0;i<3;i++)if(sinHist(i)&&r.casos[CASOS[i]].estado==='APROBADO'){
    r.casos[CASOS[i]].por_que_prosa='Las respuestas POST y la auditoria RF-73 acreditan flags, conflictos y registros por usuario; la conservacion visible solo en historial no estuvo disponible por la incidencia del primer HTTP 500.';
    r.casos[CASOS[i]].observado_prosa+=' La parte visible solo en historial no estuvo disponible por la incidencia.';
  }
  const tercero=de('227-C')?.cuerpo?.es_conflicto_retroalimentacion;
  r.observaciones.push(`OBS-M04-G072-227: la tercera respuesta para ${sel[1].id_resultado_inferencia} indicó conflicto ${tercero==null?'no disponible':tercero?'sí':'no'} al añadirse INCORRECTO tras PARCIAL y CORRECTO. Es una observación; el oráculo de conflicto se decide en TC-M04-226.`);
  if(!primera)r.observaciones.push('OBS-M04-G072-HIST: el HTTP 500 del intento 1 no se reprodujo.');
  else if(r.lecturas_historial.some((x,j)=>j>indice500&&x.http===200))r.observaciones.push(`OBS-M04-G072-HIST: HTTP 500 transitorio tras ${primera.tras_post}; una lectura posterior respondió 200.`);
  else if(r.lecturas_historial.length===indice500+1)r.observaciones.push(`OBS-M04-G072-HIST: HTTP 500 en la última lectura tras ${primera.tras_post}; no hubo otra lectura antes del DELETE para confirmar persistencia.`);
  else if(r.lecturas_historial.slice(indice500).every(x=>x.http===500))r.observaciones.push(`OBS-M04-G072-HIST: HTTP 500 persistente desde ${primera.tras_post} hasta el DELETE en todas las lecturas posteriores.`);
}
function informe(r,c){const estados=CASOS.map(x=>r.casos[x].estado),veredicto=r.oficial?(estados.includes('RECHAZADO')?'RECHAZADO':'APROBADO'):'NO OFICIAL';
  const tabla=CASOS.map(x=>`| ${x} | ${r.casos[x].estado} | ${limpio(r.casos[x].motivo)} |`).join('\n');
  const detalle=CASOS.map((x,i)=>{const z=r.casos[x],e=z.estado;
    return `### ${x} — ${e}\n\n- **Qué se hizo:** ${limpio(z.que_se_hizo??'La evaluación se interrumpió antes de las peticiones del caso.')}\n- **Qué se esperaba:** ${limpio(z.esperado_referencia??['Matriz G072, caso 226; RF-72, líneas 4053-4061.','Matriz G072, caso 227; RF-72, líneas 4043-4051.','Matriz G072, caso 230; RF-72, líneas 4024 y 4053-4061.'][i])}\n- **Qué se observó:** ${limpio(z.observado_prosa??'No hubo respuestas o lecturas suficientes para confirmar el caso.')}\n- **Por qué ${e}:** ${limpio(e==='APROBADO'?z.por_que_prosa:z.motivo)}\n\nComprobación ${IDS[i]}: ${e}; evidencia ${r.comprobaciones.find(y=>y.caso===x)?.evidencia??'preflight.json'} y resultado.json.\n`;}).join('\n');
  const incidencias=r.incidencias.map(x=>`- ${x.id}: ${x.caso}; ${x.severidad} (${x.certeza}); atención inicial ${x.equipo}. ${x.justificacion_severidad} Derivación con momento y código observados: ${x.fundamento_derivacion}. ${x.causa_probable??''}`).join('\n')||'Ninguna.';
  const evidencias=[...new Set([...r.evidencias,'resultado.json',nombreInforme(c.version)])];
  const intentos=r.solicitudes.filter(x=>x.herramienta==='Newman'&&x.metodo==='POST').map(x=>`| ${x.nombre} | ${x.http??'—'} | ${x.respuesta?.id_retroalimentacion??'—'} | ${x.respuesta?.es_conflicto_retroalimentacion??'—'} |`).join('\n');
  const lecturasTabla=r.lecturas_historial.map(x=>`| ${x.momento} (tras ${x.tras_post}) | ${x.http??'—'} | ${x.codigo??'—'}: ${limpio(x.mensaje)} | ${x.completo?x.registros_por_resultado.map(y=>`${y.id_resultado_inferencia}: ${y.registros.map(z=>`${z.id_retroalimentacion}/${z.id_usuario_veterinario}/${z.estado}`).join(', ')||'0'}`).join('; '):'no disponibles'} |`).join('\n')||'| Sin lecturas | — | — | — |';
  const historialIntentos=`## Historial de intentos\n\n- Intento 1, RUN-G072-V1-20261029-161515: TÉCNICO, nueve POST 201 y GET posterior 500 ERROR_INTERNO. Log TEST aportado por responsable QA: inserción en historial_diagnostico_eventos rechazada por RLS; disparador no aislado. DELETE 200 y rollback confirmado en la evidencia del intento 1.\n- Intento ${c.intento}, ${c.runId}: ${r.oficial?'oficial':'técnico'}; clasificación según las lecturas registradas en este RUN.\n\n`;
  const primera500=r.lecturas_historial.find(x=>x.http===500);
  const posteriores=primera500?r.lecturas_historial.slice(r.lecturas_historial.indexOf(primera500)+1):[];
  const persistencia=posteriores.length===0?'Fue la última lectura antes del DELETE; la persistencia no se confirmó con otra lectura':
    posteriores.every(x=>x.http===500)?'El HTTP 500 persistió en todas las lecturas siguientes hasta el DELETE':'El HTTP 500 no persistió en todas las lecturas siguientes';
  const tablaLecturas=`## Lecturas del historial\n\n| Momento | HTTP | Código y mensaje | Registros visibles por resultado (id/usuario/estado) |\n|---|---:|---|---|\n${lecturasTabla}\n\n${primera500?`Primera lectura HTTP 500: ${primera500.momento}, tras ${primera500.tras_post}; disparador de ${primera500.momento.startsWith('230')?'TC-M04-230':primera500.momento==='226'?'TC-M04-226':'TC-M04-227'}. ${persistencia}.`:'No hubo lectura HTTP 500.'}\n\n`;
  return `# TC-M04-G072 — ${veredicto}\n\n## Identificación\n\nGrupo G072; casos ${CASOS.join(', ')}; RF-72; versión ${c.version}; RUN ${c.runId}; ambiente ${r.ambiente}; autorización ${c.referencia}; referencia de codigo origin/test daefc3a5c62771c8952706ae7a7fe128e66b0b02 aportada en la orden, sin verificacion Git local. Node.js y Newman ${r.herramientas.newman.version??'no disponible'}; solo API.\n\n## Decisión del caso\n\n| Caso | Veredicto | Motivo |\n|---|---|---|\n${tabla}\n\nRUN oficial: ${r.oficial?'sí':'no'}. Qué falta: ${r.oficial?'nada':'completar respuestas y lecturas públicas, y verificar el rollback'}.\n\n## Datos y método\n\nActivo 885; resultados ${r.semilla?.resultados?.map(x=>x.id).join(', ')||'no disponibles'}; patología activa ${r.semilla?.patologia??'no disponible'}. Verificación por historial y auditoría RF-73 de API pública; la matriz sugería BD y no se usó SQL.\n\n## Detalle por caso\n\n${detalle}\n## Intentos Newman\n\n| Intento | HTTP | Registro | Conflicto |\n|---|---:|---|---|\n${intentos}\n\n${tablaLecturas}${historialIntentos}## Observaciones\n\n${r.observaciones.map(limpio).join('\n\n')||'Ninguna.'}\n\n## Incidencias de producto\n\n${incidencias}\n\n## Problemas técnicos y análisis de causas\n\n${r.problemas_tecnicos.map(limpio).join('; ')||'Ninguno.'} Un HTTP 500 del producto no demuestra un fallo del ejecutor ni del sandbox. El log TEST del intento 1 y la revisión posterior de la política se documentan en la incidencia del RUN oficial.\n\n## Cierre y rollback\n\nIntento ${c.intento}; solicitudes ${r.solicitudes.length}/${PRESUPUESTO.solicitudes_totales}. DELETE HTTP ${r.cierre.run.cierre_http??'—'}. Rollback ${r.cierre.rollback.verificado?'verificado':'no verificado'}: ${r.cierre.rollback.motivo}. Las lecturas poscierre pueden generar HISTORIAL_CONSULTADO fuera del sandbox.\n\n## Conclusión y acciones\n\n${veredicto==='APROBADO'?'Los tres casos cumplen; archivar evidencia.':veredicto==='RECHAZADO'?'Derivar las incidencias comprobadas a Desarrollo y repetir tras corrección autorizada.':'Resolver los impedimentos técnicos o lecturas pendientes y repetir con autorización particular.'}\n\n## Herramientas y evidencias\n\nNewman: ${r.herramientas.newman.iteraciones} iteración; ${r.herramientas.newman.solicitudes} solicitudes; ${r.herramientas.newman.aserciones} aserciones. Sin UI obligatoria.\n\n${evidencias.map(x=>`- ${x}`).join('\n')}\n`.replace(/\.\./g,'.');
}
export async function evaluar(c,{env=leerEnv(),newmanVersion=versionNewman()}={}){
  const r={grupo:'G072',run_id:c.runId,version:c.version,intento:c.intento,referencia:c.referencia,ambiente:c.ensayo?'loopback local':'TEST',
    casos:Object.fromEntries(CASOS.map(x=>[x,{estado:'NO_CONCLUYENTE',motivo:'No evaluado'}])),comprobaciones:[],solicitudes:[],incidencias:[],observaciones:[],problemas_tecnicos:[],semilla:{},
    herramientas:{newman:{...newmanVersion,iteraciones:0,solicitudes:0,posts:0,lecturas:0,aserciones:0}},cypress:{total_pruebas:0},lecturas_historial:[],
    cierre:{run:{cierre_http:null},rollback:{verificado:false,motivo:'No comprobado'}},evidencias:[],oficial:false,consume_version:false,
    _limite:Date.now()+(PRESUPUESTO.duracion_segundos-30)*1000};
  const pre=preflight(c,env,newmanVersion);
  if(!pre.ok){r.problemas_tecnicos.push(`PREFLIGHT: ${pre.barreras.join(', ')}`);
    if(pre.barreras.includes('NEWMAN_NO_DISPONIBLE'))for(const x of CASOS)r.casos[x]={estado:'BLOQUEADO',motivo:'Newman no disponible antes de cualquier petición'};
    delete r._limite;return r;}
  fs.mkdirSync(c.directorio,{recursive:true});guardar(path.join(c.directorio,'preflight.json'),pre);r.evidencias.push('preflight.json');
  const api=String(env.SIGAB_API_TEST_BASE).replace(/\/+$/,''),inicio=fecha(Date.now()-88*86400000),fin=fecha(Date.now());
  const tokens={},usuarios={};let iniciado=false,base=null,ejec={},sel=[],diag=null;
  try{
    for(const [u,nombre] of [['A','QA_VETERINARIO_EMAIL'],['B','QA_VETERINARIO_B_EMAIL'],['C','QA_VETERINARIO_C_EMAIL']]){
      const x=await pedir(r,api,'POST','/sesiones/',{cuerpo:{correo_electronico:env[nombre],contrasena:env.QA_COMMON_PASSWORD},timeout:120000});
      if(x.http!==200||!x.cuerpo?.token){r.problemas_tecnicos.push(`LOGIN_${u}_${x.http??'SIN_RED'}`);continue;}
      tokens[u]=x.cuerpo.token;usuarios[u]=usuarioToken(tokens[u]);if(!usuarios[u])r.problemas_tecnicos.push(`LOGIN_${u}_SIN_USUARIO`);
    }
    if(!tokens.A||!tokens.B||!usuarios.A||!usuarios.B){
      for(const [i,x] of CASOS.entries())r.casos[x]={estado:!tokens.A||r.problemas_tecnicos.some(z=>z==='LOGIN_A_SIN_RED')?'BLOQUEADO':'NO_CONCLUYENTE',
        motivo:`Falta login de ${!tokens.A?'A':!tokens.B?'B':'C'}; no se inició el RUN`};
      throw Error('LOGIN_INCOMPLETO');
    }
    if(new Set(Object.values(usuarios)).size!==Object.keys(usuarios).length)throw Error('USUARIOS_NO_DISTINTOS');
    iniciado=true;base=await historial(r,api,tokens.A,env.QA_SANDBOX_SECRET,c.runId,inicio,fin);
    if(!base.completo)throw Error(base.http===403?'CLAVE_403':`HISTORIAL_DESCUBRIMIENTO_${base.http??'SIN_RED'}`);
    sel=seleccionar(base.eventos);r.semilla={id_activo_biologico:885,resultados:sel.map(x=>({id:x.id_resultado_inferencia,fecha:x.fecha_evento,modelo:x.payload?.tipo_modelo,version:x.payload?.id_version_modelo}))};
    if(sel.length<4)throw Error(`DATOS_INSUFICIENTES_${sel.length}_DE_4`);
    const cat=await pedir(r,api,'GET','/prediccion/patologias?solo_activas=true',{token:tokens.A,secreto:env.QA_SANDBOX_SECRET,runId:c.runId});
    if(cat.http!==200||!Array.isArray(cat.cuerpo?.items))throw Error(`CATALOGO_${cat.http??'SIN_RED'}`);
    diag=cat.cuerpo.items.find(x=>x.es_activo===true&&x.id_patologia>=8&&x.id_patologia<=14)?.id_patologia??null;
    if(diag==null)throw Error('PATOLOGIA_ACTIVA_NO_DISPONIBLE');r.semilla.patologia=diag;
    const modelo=await pedir(r,api,'GET',`/prediccion/modelos/${sel[0].payload.id_version_modelo}`,{token:tokens.A,secreto:env.QA_SANDBOX_SECRET,runId:c.runId});
    if(modelo.http!==200||modelo.cuerpo?.paradigma!=='INDIVIDUAL')throw Error(`MODELO_INDIVIDUAL_NO_CONFIRMADO_${modelo.http??'SIN_RED'}`);
    const audAntes=[];for(let i=0;i<4;i++)audAntes.push(await auditoria(r,api,tokens.A,env.QA_SANDBOX_SECRET,c.runId,sel[i].id_resultado_inferencia));
    ejec=await newmanUnico(r,c,api,env,tokens,sel,diag,inicio,fin);
    const audDespues=[];for(let i=0;i<4;i++)audDespues.push(await auditoria(r,api,tokens.A,env.QA_SANDBOX_SECRET,c.runId,sel[i].id_resultado_inferencia));
    const audReg={};for(const n of NOMBRES)if(ejec[n]?.http===201&&ejec[n]?.cuerpo?.id_retroalimentacion)
      audReg[n]=await auditoria(r,api,tokens.A,env.QA_SANDBOX_SECRET,c.runId,ejec[n].cuerpo.id_retroalimentacion);
    evaluarCasos(r,ejec,sel,audAntes,audDespues,audReg,usuarios,diag);
  }catch(e){const motivo=limpio(e.message);r.problemas_tecnicos.push(motivo);
    for(const x of CASOS)if(r.casos[x].motivo==='No evaluado')r.casos[x]={estado:/CLAVE_403|LOGIN_A_SIN_RED/.test(motivo)?'BLOQUEADO':'NO_CONCLUYENTE',motivo:`Evaluación incompleta: ${motivo}`};
  }finally{
    if(iniciado){const cierre=await pedir(r,api,'DELETE',`/test-control/runs/${encodeURIComponent(c.runId)}`,{secreto:env.QA_SANDBOX_SECRET});r.cierre.run.cierre_http=cierre.http;
      let pos=null;try{pos=base?.completo?await historial(r,api,tokens.A,env.QA_SANDBOX_SECRET,c.runId,inicio,fin):null;}catch(e){r.problemas_tecnicos.push(`POSCIERRE: ${limpio(e.message)}`);}
      const ids=Object.values(ejec).filter(x=>x.http===201).map(x=>x.cuerpo?.id_retroalimentacion).filter(Boolean);
      const ausentes=pos?.completo&&ids.every(id=>!retro(pos.eventos,id));
      const resumen=x=>x.filter(e=>['RETROALIMENTACION','INFERENCIA','ALERTA'].includes(e.tipo_evento));
      const igual=pos?.completo&&base?.completo&&iguales(resumen(pos.eventos),resumen(base.eventos));
      r.cierre.rollback={verificado:cierre.http===200&&!!ausentes&&!!igual,motivo:cierre.http===200&&ausentes&&igual?
        'DELETE 200; identificadores nuevos ausentes e historial inicial restaurado':'DELETE o lectura poscierre sin confirmar restauración del historial inicial'};
    }
    for(const [i,x] of CASOS.entries())if(!r.comprobaciones.some(z=>z.caso===x))r.comprobaciones.push({caso:x,fuente:'API',id:IDS[i],tipo:'ASSERT',estado:r.casos[x].estado,
      evidencia:r.evidencias.includes('newman/newman-G072.json')?'newman/newman-G072.json':'preflight.json'});
    r.oficial=CASOS.every(x=>['APROBADO','RECHAZADO'].includes(r.casos[x].estado))&&r.herramientas.newman.iteraciones===1&&
      r.herramientas.newman.posts===9&&r.lecturas_historial.length===5&&r.cierre.rollback.verificado;r.consume_version=r.oficial;
    for(const lectura of r.lecturas_historial)delete lectura.eventos;
    delete r._limite;delete r._seguidos5xx;
    if(fs.existsSync(c.directorio)){const secretos=[...Object.values(tokens),env.QA_SANDBOX_SECRET,env.QA_COMMON_PASSWORD,
      env.QA_VETERINARIO_EMAIL,env.QA_VETERINARIO_B_EMAIL,env.QA_VETERINARIO_C_EMAIL];
      r.evidencias.push('resultado.json',nombreInforme(c.version));guardar(path.join(c.directorio,'resultado.json'),JSON.parse(sanear(JSON.stringify(r),secretos)));
      fs.writeFileSync(path.join(c.directorio,nombreInforme(c.version)),sanear(informe(r,c),secretos),'utf8');}
  }return r;
}
async function recuperar(c){const env=leerEnv(),r={solicitudes:[],_limite:Date.now()+30000},prev=JSON.parse(fs.readFileSync(path.join(c.directorio,'resultado.json'),'utf8'));
  if(prev.run_id!==c.runId||prev.version!==c.version)throw Error('RUN previo incoherente');
  const x=await pedir(r,String(env.SIGAB_API_TEST_BASE).replace(/\/+$/,''),'DELETE',`/test-control/runs/${encodeURIComponent(c.runId)}`,{secreto:env.QA_SANDBOX_SECRET});
  const salida={run_id:c.runId,cierre_http:x.http,rollback_verificado:false,motivo:'DELETE de recuperación sin verificación pública de ausencia; requiere conciliación'};
  guardar(path.join(c.directorio,`recuperacion-${Date.now()}.json`),salida);return salida;}
if(process.argv.includes('--capacidades'))console.log(JSON.stringify(CAPACIDADES,null,2));
else if(process.argv.includes('--comprobar'))process.exitCode=comprobar();
else if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
  try{const c=contexto(process.argv.slice(2)),r=c.operacion==='recuperar'?await recuperar(c):await evaluar(c);
    console.log(JSON.stringify({grupo:'G072',run_id:c.runId,oficial:r.oficial??false,casos:r.casos??null}));if(!r.oficial)process.exitCode=2;
  }catch(e){console.error(limpio(e.message));process.exitCode=2;}}
