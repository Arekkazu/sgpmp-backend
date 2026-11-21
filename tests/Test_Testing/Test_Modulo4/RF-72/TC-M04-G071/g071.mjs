#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import {CASOS,IDS,PRESUPUESTO,CAPACIDADES,uuid,iguales,snapshot,seleccionar,patologiaDistinta,eventosDe,retro,decision} from './lib/g071_core.mjs';

const DIR=path.dirname(fileURLToPath(import.meta.url));
const RAIZ=path.resolve(DIR,'../../../../..');
const require=createRequire(import.meta.url);
const API='https://www.api.inmero.co/api-sgpmp-test';
const COLECCION=JSON.parse(fs.readFileSync(path.join(DIR,'G071.postman_collection.json'),'utf8'));
const NOMBRES=COLECCION.item.map(x=>x.name);
const fecha=x=>new Intl.DateTimeFormat('en-CA',{timeZone:'America/Bogota',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(x));
const informeNombre=v=>v===1?'TC-M04-G071_resultado.md':`TC-M04-G071_reevaluacion_V${v}.md`;
const guardar=(p,x)=>fs.writeFileSync(p,JSON.stringify(x,null,2),'utf8');
const limpiar=x=>String(x??'').replace(/[\r\n|]/g,' ');
const html=x=>String(x).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function sanear(x,secretos=[]){let s=String(x);for(const v of secretos.filter(v=>typeof v==='string'&&v.length>3))s=s.split(v).join('[REDACTADO]');
  return s.replace(/eyJ[\w-]{5,}\.[\w-]{5,}\.[\w-]{5,}/g,'[JWT_REDACTADO]')
    .replace(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/gi,'[CORREO_REDACTADO]');}
function newmanDir(){try{return path.dirname(require.resolve('newman/package.json',{paths:[RAIZ]}));}
  catch{const rutas=[process.execPath,...String(process.env.PATH??'').split(path.delimiter)];
    return rutas.map(x=>path.join(path.dirname(x),'node_modules','newman','package.json'))
      .find(fs.existsSync)?.replace(/[\\/]package\.json$/,'')??null;}}
function versionNewman(){try{return {ok:true,version:require(path.join(newmanDir(),'package.json')).version};}
  catch{return {ok:false,error:'NEWMAN_NO_DISPONIBLE'};}}
export function leerEnv(proceso=process.env,archivo=path.join(RAIZ,'.env.qa')){
  const e={};if(fs.existsSync(archivo))for(const linea of fs.readFileSync(archivo,'utf8').split(/\r?\n/)){
    const m=linea.match(/^\s*([A-Z][A-Z0-9_]*)\s*=(.*)$/);if(m)e[m[1]]=m[2].trim().replace(/^(['"])(.*)\1$/,'$2');}
  Object.assign(e,proceso);e.QA_AUTORIZADO=proceso.QA_AUTORIZADO;return e;
}
export function preflight(c,env=leerEnv(),newman=versionNewman()){
  const barreras=['SIGAB_API_TEST_BASE','QA_SANDBOX_SECRET','QA_VETERINARIO_EMAIL','QA_COMMON_PASSWORD']
    .filter(k=>!String(env[k]??'').trim());
  if(env.QA_AUTORIZADO!=='SI')barreras.push('QA_AUTORIZADO');
  if(!newman.ok)barreras.push('NEWMAN_NO_DISPONIBLE');
  const base=String(env.SIGAB_API_TEST_BASE??'').replace(/\/+$/,'');
  if(c.ensayo?!/^http:\/\/(127\.0\.0\.1|localhost):\d+$/.test(base):base!==API)barreras.push('API_NO_CANONICA');
  if(COLECCION.item.length!==PRESUPUESTO.solicitudes_newman||new Set(NOMBRES).size!==NOMBRES.length)barreras.push('COLECCION_INVALIDA');
  return {grupo:'G071',run_id:c.runId,ok:!barreras.length,barreras,presupuesto:PRESUPUESTO,herramientas:{newman},
    efectos:['Un login Veterinario QA A; último acceso y auditoría de autenticación',
      'Lecturas de historial, catálogo, versión, OpenAPI y auditoría',
      'Cinco retroalimentaciones aceptadas y auditoría, revertidas mediante DELETE',
      'Intentos PUT/PATCH/DELETE y POST negativos; un efecto inesperado se revierte por DELETE',
      'Lecturas poscierre pueden crear HISTORIAL_CONSULTADO fuera del sandbox; sin correos ni archivos externos']};
}
export function comprobar(){const archivos=['g071.mjs','lib/g071_core.mjs','G071.postman_collection.json',
  'pruebas/g071_ensayo.mjs','pruebas/g071_env.test.mjs','pruebas/registro_qa.mjs','README.md'];
  const faltantes=archivos.filter(x=>!fs.existsSync(path.join(DIR,x)));
  const superior=fs.existsSync(path.join(DIR,'Resultados'))&&fs.readdirSync(path.join(DIR,'Resultados')).some(x=>x.endsWith('.md'));
  const n=versionNewman(),ok=!faltantes.length&&!superior&&n.ok&&COLECCION.item.length===23;
  console.log(JSON.stringify({grupo:'G071',ok,faltantes,markdown_superior:superior,newman:n,presupuesto:PRESUPUESTO}));return ok?0:2;}
function contexto(args){const v=k=>args.includes(k)?args[args.indexOf(k)+1]:undefined;
  const operacion=v('--operacion'),version=Number(v('--version')),intento=Number(v('--intento')),
    runId=v('--run-id'),referencia=v('--autorizacion'),archivo=v('--contexto');
  if(!CAPACIDADES.operaciones.includes(operacion)||!Number.isInteger(version)||version<1||
    !Number.isInteger(intento)||intento<1||!referencia||!archivo||
    !new RegExp(`^RUN-G071-V${version}-\\d{8}-\\d{6}$`).test(runId??''))throw Error('Contexto incompleto');
  const destino=path.join(DIR,...(version===1?['Resultados',runId]:[`EvaluacionV${version}`,'Resultados',runId]));
  const ruta=path.resolve(archivo);
  if(path.dirname(ruta)!==destino||!(operacion==='recuperar'?/^recuperacion-\d{14}\.contexto\.json$/.test(path.basename(ruta)):path.basename(ruta)==='contexto_operacion.json'))throw Error('Contexto fuera del RUN canónico');
  const c=JSON.parse(fs.readFileSync(ruta,'utf8'));
  if(c.grupo!=='G071'||c.run_id!==runId||c.version!==version||c.intento!==intento||
    c.operacion!==operacion.toUpperCase()||c.referencia!==referencia||
    JSON.stringify(c.casos)!==JSON.stringify(CASOS)||
    operacion==='reevaluar'&&(version<2||c.version_anterior!==version-1||!c.alcance_reevaluacion)||
    operacion==='recuperar'&&v('--run-objetivo')!==runId)throw Error('Contexto incoherente');
  return {operacion,version,intento,runId,referencia,directorio:destino,ensayo:false};}
async function pedir(r,api,metodo,ruta,{token,secreto,runId,cuerpo,timeout=PRESUPUESTO.timeout_ms,caso}={}){
  if(r.solicitudes.length>=PRESUPUESTO.solicitudes_totales&&metodo!=='DELETE')throw Error('PRESUPUESTO_AGOTADO');
  const fila={caso:caso??null,metodo,ruta:ruta.split('?')[0],http:null};r.solicitudes.push(fila);
  try{const inicio=Date.now();if(inicio>=r._limite&&metodo!=='DELETE')throw Error('DURACION_EXCEDIDA');
    const res=await fetch(api+ruta,{method:metodo,redirect:'manual',headers:{
      ...(cuerpo?{'Content-Type':'application/json'}:{}),...(token?{Authorization:`Bearer ${token}`}:{}) ,
      ...(secreto?{'X-Sandbox-Secret':secreto}:{}),...(runId?{'X-Test-Run-Id':runId,'X-Zona-Horaria':'America/Bogota'}:{})},
      body:cuerpo?JSON.stringify(cuerpo):undefined,
      signal:AbortSignal.timeout(Math.max(1,Math.min(timeout,metodo==='DELETE'?timeout:r._limite-inicio)))});
    const b=await res.json().catch(()=>null);
    Object.assign(fila,{http:res.status,eco:runId?res.headers.get('x-test-run-id')===runId:null,
      duracion_ms:Date.now()-inicio,respuesta:ruta==='/sesiones/'?{token_recibido:!!b?.token}:
        {error_code:b?.error_code??null,message:limpiar(b?.message??''),total:b?.total??null}});
    return {http:res.status,cuerpo:b,eco:fila.eco};
  }catch(e){fila.tipo_fallo=['TimeoutError','AbortError'].includes(e.name)?'TIMEOUT':'SIN_RED';return {http:null,cuerpo:null,eco:false};}}
function rutaHist(inicio,fin,cursor,alertas=true){return `/prediccion/historial/885?fecha_inicio=${inicio}&fecha_fin=${fin}&incluir_alertas=${alertas}${cursor?`&cursor_paginacion=${encodeURIComponent(cursor)}`:''}`;}
async function historial(r,api,token,secreto,runId,inicio,fin){const eventos=[];let cursor=null;
  for(let i=0;i<PRESUPUESTO.paginas_historial;i++){
    const x=await pedir(r,api,'GET',rutaHist(inicio,fin,cursor),{token,secreto,runId});
    if(x.http!==200||x.eco!==true||!Array.isArray(x.cuerpo?.eventos))return {eventos,completo:false,http:x.http,paginas:i+1};
    eventos.push(...x.cuerpo.eventos);cursor=x.cuerpo.cursor_siguiente;
    if(!cursor)return {eventos,completo:true,http:200,paginas:i+1};
  }return {eventos,completo:false,http:200,paginas:PRESUPUESTO.paginas_historial,cursor_pendiente:true};}
function usuarioDelToken(t){try{return String(JSON.parse(Buffer.from(String(t).split('.')[1],'base64url')).sub);}catch{return null;}}
function casoNombre(n){return n.startsWith('219-')?CASOS[0]:n.startsWith('220-')?CASOS[1]:n.startsWith('221-')?CASOS[2]:n.startsWith('222-')?CASOS[3]:CASOS[4];}
async function newmanUnico(r,c,api,env,token,seleccion,diag){
  const col=structuredClone(COLECCION);
  const headers=[{key:'Authorization',value:'Bearer {{token}}'},{key:'X-Test-Run-Id',value:'{{run_id}}'},
    {key:'X-Sandbox-Secret',value:'{{sandbox_secret}}'},{key:'X-Zona-Horaria',value:'America/Bogota'},
    {key:'Content-Type',value:'application/json'}];
  for(const item of col.item){item.request.header=item.name==='222-anon'?headers.filter(h=>h.key!=='Authorization'):headers;
    item.event=[{listen:'test',script:{type:'text/javascript',exec:[
      "const n=pm.response.code>=500?Number(pm.environment.get('consecutivos_5xx')||0)+1:0;pm.environment.set('consecutivos_5xx',String(n));",
      "if(pm.info.requestName==='219-3'&&pm.response.code===201){try{pm.environment.set('id_221_target',pm.response.json().id_retroalimentacion)}catch{}}",
      "if((pm.response.code===403&&/clave|secreto|sandbox/i.test(pm.response.text()))||n>=3)postman.setNextRequest(null);",
      "pm.test('HTTP recibido',()=>pm.expect(pm.response.code).to.be.above(0));",
      "pm.test('Eco de RUN',()=>pm.expect(pm.response.headers.get('X-Test-Run-Id')).to.eql(pm.environment.get('run_id')));"
    ]}}];}
  const body=e=>({id_resultado_inferencia:e.id_resultado_inferencia,id_activo_biologico:885,estado_retroalimentacion:'CORRECTO'});
  const errado=e=>({...body(e),estado_retroalimentacion:'INCORRECTO',diagnosticos_reales:[diag]});
  const h220=rutaHist(fecha(Date.parse(seleccion[3].fecha_evento)-86400000),fecha(Date.now()),null,false);
  const h246=rutaHist(fecha(Date.now()-88*86400000),fecha(Date.now()),null,true);
  const h219=rutaHist(fecha(Date.parse(seleccion[2].fecha_evento)-86400000),fecha(Date.now()),null,false);
  const valores={base_url:api,token,run_id:c.runId,sandbox_secret:env.QA_SANDBOX_SECRET,consecutivos_5xx:'0',
    id_221_target:'00000000-0000-4000-8000-000000000000',history_219:h219,history_220:h220,history_246:h246};
  for(let i=0;i<3;i++)valores[`body_219_${i+1}`]=JSON.stringify(body(seleccion[i]));
  valores.body_220=JSON.stringify(errado(seleccion[3]));valores.body_246=JSON.stringify(errado(seleccion[4]));
  valores.body_222=JSON.stringify(body(seleccion[5]??seleccion[0]));
  valores.body_222_no_asset=JSON.stringify({id_resultado_inferencia:(seleccion[6]??seleccion[1]).id_resultado_inferencia,estado_retroalimentacion:'CORRECTO'});
  valores.body_222_no_result=JSON.stringify({id_activo_biologico:885,estado_retroalimentacion:'CORRECTO'});
  valores.body_edit=JSON.stringify({...errado(seleccion[2]),id_retroalimentacion:'{{id_221_target}}'});
  const environment={values:Object.entries(valores).map(([key,value])=>({key,value,enabled:true}))};
  let error,summary;try{[error,summary]=await new Promise(ok=>require(newmanDir()).run({collection:col,environment,
    reporters:['cli'],silent:true,timeoutRequest:PRESUPUESTO.timeout_ms,timeout:Math.max(1,r._limite-Date.now()),
    ignoreRedirects:true,color:'off'},(e,s)=>ok([e,s])));}catch(e){error=e;}
  const ejec={};const reporte={herramienta:'Newman',version:r.herramientas.newman.version,error:error?limpiar(error.message):null,
    solicitudes:[],fallos:(summary?.run?.failures??[]).map(f=>({tipo:f.error?.name??'Error',mensaje:limpiar(f.error?.message)}))};
  let consecutivos=0;
  for(const ex of summary?.run?.executions??[]){let b=null;try{b=JSON.parse(ex.response.stream.toString('utf8'));}catch{}
    const n=ex.item?.name,http=ex.response?.code??null;
    const eco=ex.response?.headers?.get?.('x-test-run-id')===c.runId||
      ex.response?.header?.find?.(h=>String(h.key).toLowerCase()==='x-test-run-id')?.value===c.runId;
    const fila={caso:casoNombre(n),nombre:n,metodo:ex.request?.method,ruta:ex.request?.url?.getPath?.()?.split('?')[0]??null,
      http,eco,herramienta:'Newman',duracion_ms:ex.response?.responseTime??null,
      respuesta:{id_retroalimentacion:b?.id_retroalimentacion??null,error_code:b?.error_code??null,message:limpiar(b?.message??'')}};
    r.solicitudes.push(fila);reporte.solicitudes.push({...fila,aserciones:(ex.assertions??[]).map(a=>({nombre:a.assertion,error:a.error?.message??null}))});
    ejec[n]={http,cuerpo:b,eco,nombre:n};
    if(http===null)r.problemas_tecnicos.push(`SIN_RESPUESTA_NEWMAN_${n}`);
    consecutivos=http>=500?consecutivos+1:0;
    if(consecutivos>=3&&!r.problemas_tecnicos.includes('TRES_5XX_CONSECUTIVOS'))r.problemas_tecnicos.push('TRES_5XX_CONSECUTIVOS');
    if(http===403&&/clave|secreto|sandbox/i.test(String(b?.message??b?.detail??'')))r.problemas_tecnicos.push('CLAVE_403');
  }
  r.herramientas.newman.iteraciones=summary?.run?.stats?.iterations?.total??(summary?1:0);
  r.herramientas.newman.solicitudes=reporte.solicitudes.length;
  r.herramientas.newman.aserciones=reporte.solicitudes.reduce((v,x)=>v+x.aserciones.length,0);
  if(error)r.problemas_tecnicos.push(`Newman: ${limpiar(error.message)}`);
  const sub=path.join(c.directorio,'newman');fs.mkdirSync(sub,{recursive:true});
  const secretos=[token,env.QA_SANDBOX_SECRET,env.QA_COMMON_PASSWORD,env.QA_VETERINARIO_EMAIL];
  const json=sanear(JSON.stringify(reporte,null,2),secretos);
  fs.writeFileSync(path.join(sub,'newman-G071.json'),json);
  fs.writeFileSync(path.join(sub,'newman-G071.html'),`<!doctype html><html lang="es"><meta charset="utf-8"><title>Newman G071</title><pre>${html(json)}</pre></html>`);
  r.evidencias.push('newman/newman-G071.json','newman/newman-G071.html');return ejec;
}
function evaluarCasos(r,c,ejec,seleccion,posterior,usuario,diag){
  const de=n=>ejec[n]??null,exitos=n=>de(n)?.http===201&&de(n)?.eco===true;
  const ids=['219-1','219-2','219-3'].map(n=>de(n)?.cuerpo?.id_retroalimentacion);
  const verificable=posterior?.completo===true;
  const lectura219=de('219-read')?.cuerpo;
  const uno=decision([...[0,1,2].map(i=>de(`219-${i+1}`)?.http?exitos(`219-${i+1}`):null),
    ids.every(x=>x!=null)?ids.every(uuid):null,ids.every(x=>x!=null)?new Set(ids).size===3:null,
    lectura219?.cursor_siguiente===null?ids.every(id=>!!retro(lectura219.eventos,id)):null]);
  const antes220=de('220-before')?.cuerpo,despues220=de('220-after')?.cuerpo;
  const e220=x=>x?.eventos?.find(e=>e.tipo_evento==='INFERENCIA'&&e.id_resultado_inferencia===seleccion[3].id_resultado_inferencia);
  const snap220a=snapshot(e220(antes220)),snap220b=snapshot(e220(despues220));
  const dos=decision([exitos('220-post'),snap220a&&snap220b?iguales(snap220a,snap220b):null,
    verificable?!!retro(posterior.eventos,de('220-post')?.cuerpo?.id_retroalimentacion):null]);
  const m221=['221-put-id','221-patch-id','221-delete-id','221-patch-base','221-delete-base'];
  const op=de('221-openapi')?.cuerpo?.paths;
  const expuestas=op?Object.entries(op).flatMap(([ruta,metodos])=>
    /retroalimentacion/i.test(ruta)?Object.keys(metodos).filter(m=>['put','patch','delete'].includes(m)).map(m=>`${m.toUpperCase()} ${ruta}`):[]):null;
  const r219=retro(posterior?.eventos??[],ids[2]);
  const identico=r219?iguales({id:r219.payload?.id_retroalimentacion,resultado:r219.id_resultado_inferencia,
    estado:r219.payload?.estado_retroalimentacion,diagnosticos:r219.payload?.diagnosticos_reales,
    fecha:r219.fecha_evento,usuario:r219.payload?.id_usuario_veterinario,activo:r219.id_activo_biologico},
    {id:ids[2],resultado:de('219-3')?.cuerpo?.id_resultado_inferencia,
      estado:de('219-3')?.cuerpo?.estado_retroalimentacion,
      diagnosticos:de('219-3')?.cuerpo?.diagnosticos_reales,
      fecha:de('219-3')?.cuerpo?.fecha_retroalimentacion,
      usuario:de('219-3')?.cuerpo?.id_usuario_veterinario,activo:de('219-3')?.cuerpo?.id_activo_biologico}):null;
  const tres=decision([ids[2]?true:null,...m221.map(n=>de(n)?.http?de(n).http<200||de(n).http>=300:null),
    expuestas?expuestas.length===0:null,verificable?identico:null]);
  const campos=['id_resultado_inferencia','id_usuario_veterinario','fecha_retroalimentacion','id_activo_biologico'];
  const traza=de('219-1')?.cuerpo,lectura=retro(posterior?.eventos??[],ids[0]);
  const campoLectura={id_resultado_inferencia:lectura?.id_resultado_inferencia,
    id_usuario_veterinario:lectura?.payload?.id_usuario_veterinario,fecha_retroalimentacion:lectura?.fecha_evento,
    id_activo_biologico:lectura?.id_activo_biologico};
  const cuatro=decision([exitos('219-1'),campos.every(k=>traza?.[k]!=null),
    verificable?campos.every(k=>campoLectura[k]!=null):null,
    de('222-anon')?.http?de('222-anon').http===401:null,
    de('222-no-asset')?.http?de('222-no-asset').http>=400&&de('222-no-asset').http<500:null,
    de('222-no-result')?.http?de('222-no-result').http>=400&&de('222-no-result').http<500:null,
    verificable&&seleccion[5]?posterior.eventos.every(e=>!(e.tipo_evento==='RETROALIMENTACION'&&e.id_resultado_inferencia===seleccion[5].id_resultado_inferencia)):null,
    verificable&&seleccion[6]?posterior.eventos.every(e=>!(e.tipo_evento==='RETROALIMENTACION'&&e.id_resultado_inferencia===seleccion[6].id_resultado_inferencia)):null]);
  const hA=de('246-before-history')?.cuerpo,hB=de('246-after-history')?.cuerpo;
  const buscar=x=>x?.eventos?.find(e=>e.tipo_evento==='INFERENCIA'&&e.id_resultado_inferencia===seleccion[4].id_resultado_inferencia);
  const sA=snapshot(buscar(hA)),sB=snapshot(buscar(hB));
  const vA=de('246-before-versions')?.cuerpo,vB=de('246-after-versions')?.cuerpo;
  const motorA=de('246-before-motor')?.cuerpo,motorB=de('246-after-motor')?.cuerpo;
  const motorResumen=x=>x?{tipo_modelo:x.tipo_modelo,id_version_modelo_activa:x.id_version_modelo_activa,
    config_version:x.config_version,es_activa:x.es_activa}:null;
  const versiones=x=>x?.items?.map(v=>({id_version_modelo:v.id_version_modelo,tipo_modelo:v.tipo_modelo,
    estado_version:v.estado_version,esta_produccion:v.esta_produccion})).sort((a,b)=>a.id_version_modelo-b.id_version_modelo);
  const inf=x=>eventosDe(x?.eventos??[],'INFERENCIA');
  const alertas=x=>eventosDe(x?.eventos??[],'ALERTA');
  const cinco=decision([exitos('246-post'),sA&&sB?iguales(sA,sB):null,
    hA?.cursor_siguiente===null&&hB?.cursor_siguiente===null?iguales(alertas(hA),alertas(hB)):null,
    vA?.items&&vB?.items?iguales(versiones(vA),versiones(vB)):null,
    motorA&&motorB?iguales(motorA,motorB):null,
    vA?.items?.some(v=>v.id_version_modelo===43)&&vB?.items?.some(v=>v.id_version_modelo===43)||null,
    hA?.cursor_siguiente===null&&hB?.cursor_siguiente===null?iguales(inf(hA),inf(hB)):null,
    verificable?!!retro(posterior.eventos,de('246-post')?.cuerpo?.id_retroalimentacion):null]);
  const detalles=[
    {esperado:'Tres 201, UUID válidos y distintos, presentes en historial.',observado:`HTTP ${[1,2,3].map(i=>de(`219-${i}`)?.http??'sin respuesta').join('/')}; identificadores ${ids.join(', ')}; lectura posterior inmediata completa ${lectura219?.cursor_siguiente===null}.`,por_que:`UUID válidos ${ids.every(uuid)}; distintos ${new Set(ids).size===3}.`},
    {esperado:'Snapshot idéntico antes y después de INCORRECTO.',observado:`POST ${de('220-post')?.http??'sin respuesta'}; resultado ${seleccion[3].id_resultado_inferencia}; patología real ${diag}; antes ${JSON.stringify(snap220a)}; después ${JSON.stringify(snap220b)}.`,por_que:`Comparación de riesgo, patología, probabilidades, fecha y versión: ${snap220a&&snap220b?iguales(snap220a,snap220b):'no disponible'}.`},
    {esperado:'PUT, PATCH y DELETE rechazados, sin operación expuesta ni cambio del registro.',observado:`HTTP ${m221.map(n=>`${n}:${de(n)?.http??'sin respuesta'}`).join(', ')}; OpenAPI ${de('221-openapi')?.http??'sin respuesta'}; operaciones ${expuesasTexto(expuestas)}; registro ${ids[2]}.`,por_que:`Registro idéntico en historial ${identico??'no comprobado'}; ninguna operación 2xx ${m221.every(n=>de(n)?.http<200||de(n)?.http>=300)}.`},
    {esperado:'Cuatro campos no nulos; anónimo e incompletos sin registro.',observado:`POST ${de('219-1')?.http??'sin respuesta'}; anónimo ${de('222-anon')?.http??'sin respuesta'}; sin activo ${de('222-no-asset')?.http??'sin respuesta'}; sin resultado ${de('222-no-result')?.http??'sin respuesta'}; campos respuesta ${JSON.stringify(Object.fromEntries(campos.map(k=>[k,traza?.[k]??null])))}; campos historial ${JSON.stringify(campoLectura)}.`,por_que:`Cuatro campos presentes en ambas lecturas ${campos.every(k=>traza?.[k]!=null&&campoLectura[k]!=null)}; sin registros adicionales ${verificable}.`},
    {esperado:'Resultado, alertas, versiones, configuración del motor e historial de inferencias sin cambios.',observado:`POST ${de('246-post')?.http??'sin respuesta'}; resultado ${seleccion[4].id_resultado_inferencia}; patología real ${diag}; alertas ${alertas(hA).length}/${alertas(hB).length}; inferencias ${inf(hA).length}/${inf(hB).length}; versión 43 ${vA?.items?.find(v=>v.id_version_modelo===43)?.estado_version??'ausente'}/${vB?.items?.find(v=>v.id_version_modelo===43)?.estado_version??'ausente'}; motor antes ${JSON.stringify(motorResumen(motorA))}; después ${JSON.stringify(motorResumen(motorB))}.`,por_que:`Snapshot ${sA&&sB?iguales(sA,sB):'no disponible'}; alertas ${iguales(alertas(hA),alertas(hB))}; versiones ${iguales(versiones(vA),versiones(vB))}; motor ${iguales(motorA,motorB)}; inferencias ${iguales(inf(hA),inf(hB))}.`}
  ];
  const corto=x=>String(x??'no disponible').slice(0,8);
  const valor=x=>x==null?'no disponible':String(x);
  const probabilidades=x=>x&&typeof x==='object'?Object.entries(x).map(([k,v])=>`${k}: ${v}`).join(', '):valor(x);
  const documentacion=[
    {que_se_hizo:`Se registraron como CORRECTO los resultados ${seleccion.slice(0,3).map(e=>corto(e.id_resultado_inferencia)).join(', ')} mediante tres POST y se consultó el historial del activo 885.`,
      esperado_referencia:'Tres identificadores UUID únicos, válidos y distintos, conservados en historial (matriz G071, caso 219; RF-72, Salida, líneas 4301-4305).',
      observado_prosa:`Los tres POST devolvieron ${[1,2,3].map(i=>valor(de(`219-${i}`)?.http)).join(', ')}; se recibieron los UUID ${ids.map(valor).join(', ')}. El historial devolvió HTTP ${valor(de('219-read')?.http)} y ${lectura219?.cursor_siguiente===null&&ids.every(id=>!!retro(lectura219.eventos,id))?'contenía los tres registros en una página completa':'no confirmó una página completa con los tres registros'}.`,
      por_que_prosa:'Cada alta produjo un identificador con formato UUID y ninguno se repitió; los tres registros quedaron localizables en el historial.'},
    {que_se_hizo:`Se leyó el resultado ${corto(seleccion[3]?.id_resultado_inferencia)} antes y después de registrar INCORRECTO con patología real ${valor(diag)} mediante POST.`,
      esperado_referencia:'El resultado original conserva riesgo, enfermedad estimada, probabilidades, fecha y versión del modelo (matriz G071, caso 220; RF-72, inmutabilidad, líneas 4015-4016; CA-2, línea 4361).',
      observado_prosa:`El POST devolvió HTTP ${valor(de('220-post')?.http)}. Antes y después se leyó riesgo ${valor(snap220a?.nivel_riesgo)}/${valor(snap220b?.nivel_riesgo)}, patología estimada ${valor(snap220a?.id_patologia)}/${valor(snap220b?.id_patologia)} (${valor(snap220a?.nombre_patologia)}), probabilidades de riesgo ${probabilidades(snap220a?.probabilidad_riesgo)} / ${probabilidades(snap220b?.probabilidad_riesgo)}, probabilidad de enfermedad ${probabilidades(snap220a?.probabilidad_enfermedad)} / ${probabilidades(snap220b?.probabilidad_enfermedad)}, confianza ${valor(snap220a?.confianza_global)}/${valor(snap220b?.confianza_global)}, fecha ${valor(snap220a?.fecha_inferencia)}/${valor(snap220b?.fecha_inferencia)} y versión ${valor(snap220a?.id_version_modelo)}/${valor(snap220b?.id_version_modelo)}.`,
      por_que_prosa:'El diagnóstico real diferente quedó en la retroalimentación y la comparación de todos los campos exigidos del resultado no mostró alteración.'},
    {que_se_hizo:`Sobre el registro ${corto(ids[2])} se intentaron PUT, PATCH y DELETE por identificador, PATCH y DELETE en la ruta base; se consultaron OpenAPI y el historial posterior.`,
      esperado_referencia:'No se permite editar ni eliminar; el registro permanece idéntico (matriz G071, caso 221; RF-72, líneas 4018-4019; CA-6, líneas 4369-4374; RNF-04, líneas 4407-4408).',
      observado_prosa:`PUT, PATCH y DELETE por identificador devolvieron ${m221.slice(0,3).map(n=>valor(de(n)?.http)).join(', ')}; PATCH y DELETE en la ruta base devolvieron ${m221.slice(3).map(n=>valor(de(n)?.http)).join(', ')}. OpenAPI devolvió HTTP ${valor(de('221-openapi')?.http)} y ${expuestas?.length===0?'no publicó operaciones de edición ni eliminación':'la disponibilidad de operaciones de edición o eliminación no quedó descartada'}. El registro ${corto(ids[2])} ${identico?'conservó los mismos campos en el historial':'no quedó confirmado como idéntico en el historial'}.`,
      por_que_prosa:'Ningún intento de escritura obtuvo éxito, la API pública no ofreció una operación para alterar el registro y la lectura posterior conservó su contenido.'},
    {que_se_hizo:`Se contrastaron la respuesta del registro ${corto(traza?.id_resultado_inferencia)} y el historial; se intentaron tres POST: sin token, sin activo (${corto(seleccion[5]?.id_resultado_inferencia??seleccion[0]?.id_resultado_inferencia)}) y sin resultado (activo 885).`,
      esperado_referencia:'Resultado, usuario, fecha y activo son obligatorios; no se admiten registros anónimos ni incompletos (matriz G071, caso 222; RF-72, trazabilidad, líneas 4080-4085; CA-7, línea 4376; RNF-05, líneas 4410-4411).',
      observado_prosa:`La respuesta y el historial del alta HTTP ${valor(de('219-1')?.http)} mostraron resultado ${valor(traza?.id_resultado_inferencia)} / ${valor(campoLectura.id_resultado_inferencia)}, usuario ${valor(traza?.id_usuario_veterinario)} / ${valor(campoLectura.id_usuario_veterinario)}, fecha ${valor(traza?.fecha_retroalimentacion)} / ${valor(campoLectura.fecha_retroalimentacion)} y activo ${valor(traza?.id_activo_biologico)} / ${valor(campoLectura.id_activo_biologico)}. Sin token se obtuvo ${valor(de('222-anon')?.http)}; sin activo y sin resultado, ${valor(de('222-no-asset')?.http)} y ${valor(de('222-no-result')?.http)}; ${verificable&&seleccion[5]&&seleccion[6]&&[seleccion[5],seleccion[6]].every(e=>posterior.eventos.every(x=>!(x.tipo_evento==='RETROALIMENTACION'&&x.id_resultado_inferencia===e.id_resultado_inferencia)))?'el historial posterior no mostró registros nuevos de esos intentos':'la ausencia de registros nuevos no quedó confirmada en el historial'}.`,
      por_que_prosa:'Los cuatro datos exigidos acompañaron el registro en respuesta e historial, mientras que los intentos anónimo e incompletos fueron rechazados sin persistencia.'},
    {que_se_hizo:`Se compararon historial, alertas, versiones y configuración del motor antes y después de registrar INCORRECTO para ${corto(seleccion[4]?.id_resultado_inferencia)} con patología real ${valor(diag)}.`,
      esperado_referencia:'El registro se limita a análisis posterior y reentrenamiento; no recalcula el resultado ni altera alertas o comportamiento posterior (matriz G071, caso 246; RF-72, uso analítico, líneas 4115-4116).',
      observado_prosa:`El POST devolvió HTTP ${valor(de('246-post')?.http)}. El resultado ${corto(seleccion[4]?.id_resultado_inferencia)} ${sA&&sB&&iguales(sA,sB)?'conservó su snapshot':'no conservó un snapshot idéntico o faltó lectura'}; alertas del activo ${alertas(hA).length}/${alertas(hB).length}, inferencias ${inf(hA).length}/${inf(hB).length}, versión 43 ${valor(vA?.items?.find(v=>v.id_version_modelo===43)?.estado_version)}/${valor(vB?.items?.find(v=>v.id_version_modelo===43)?.estado_version)}, versión activa del motor ${valor(motorA?.id_version_modelo_activa)}/${valor(motorB?.id_version_modelo_activa)} y config_version ${valor(motorA?.config_version)}/${valor(motorB?.config_version)} antes/después.`,
      por_que_prosa:'El resultado y las alertas visibles conservaron sus datos; las versiones, la configuración del motor y la identidad de las inferencias permanecieron iguales tras el registro.',
      alertas_iniciales:alertas(hA).length}
  ];
  const motivosAprobados=[
    'Los tres registros recibieron identificadores UUID distintos y quedaron en el historial',
    'El resultado no cambió tras el registro INCORRECTO',
    'No existe forma de editar ni borrar: los intentos respondieron 404/405 y el registro siguió igual',
    'Resultado, usuario, fecha y activo presentes; sin token 401 e incompletos 400',
    'El registro no alteró resultado, alertas, versiones, configuración del motor ni inferencias'
  ];
  const estados=[uno,dos,tres,cuatro,cinco];
  const bloquea=r.problemas_tecnicos.some(x=>/TRES_5XX|CLAVE_403/.test(x));
  for(let i=0;i<CASOS.length;i++){
    const e=bloquea?'BLOQUEADO':estados[i];
    const un5xx=r.solicitudes.some(x=>x.caso===CASOS[i]&&x.http>=500&&x.metodo!=='GET');
    const sinRespuesta=r.solicitudes.some(x=>x.caso===CASOS[i]&&x.herramienta==='Newman'&&x.http===null);
    r.casos[CASOS[i]]={estado:!bloquea&&un5xx?'RECHAZADO':e,
      motivo:bloquea?'Corte por clave 403 o tres respuestas 5xx consecutivas':un5xx?'Respuesta 5xx aislada en petición obligatoria':
        e==='APROBADO'?motivosAprobados[i]:e==='RECHAZADO'?'Discrepancia observable en API':
          sinRespuesta?'Petición Newman sin respuesta HTTP; verificar transporte y repetir':
          'Falta una lectura pública completa o una petición obligatoria para concluir',...detalles[i],...documentacion[i]};
    r.comprobaciones.push({caso:CASOS[i],fuente:'API',id:IDS[i],tipo:'ASSERT',estado:r.casos[CASOS[i]].estado,evidencia:'newman/newman-G071.json'});
    if(r.casos[CASOS[i]].estado==='RECHAZADO')r.incidencias.push({id:`INC-M04-G071-${CASOS[i].slice(-3)}-01`,
      caso:CASOS[i],equipo:'Desarrollo',fundamento_derivacion:'Primera discrepancia confirmada en la API pública de RF-72',
      causa_raiz:'NO DETERMINADA',certeza:'CONFIRMADA',severidad:i===3?'ALTA':'MEDIA',
      justificacion_severidad:i===3?'La trazabilidad o el rechazo de anónimos afecta integridad del registro clínico.':
        'La discrepancia afecta una regla de integridad específica de la retroalimentación.',
      que_se_observo:detalles[i].observado,por_que:detalles[i].por_que});
  }
  r.observaciones.push('TC-M04-246 compara el estado observable de la versión activa y la versión 43; no ejecuta una inferencia nueva. La semilla puede no contener alertas derivadas: entonces se comprueba que ninguna aparece ni cambia en la página completa.');
  r.observaciones.push(`Selección: ${seleccion.slice(0,5).map(e=>e.id_resultado_inferencia).join(', ')}; reemplazos para negativos ${seleccion.slice(5).map(e=>e.id_resultado_inferencia).join(', ')||'ausentes'}.`);
}
const expuesasTexto=x=>x===null?'lectura no disponible':x.length?x.join(', '):'ninguna';
function informeNuevo(r,c){
  const veredicto=r.oficial?(CASOS.some(x=>r.casos[x].estado==='RECHAZADO')?'RECHAZADO':'APROBADO'):'NO OFICIAL';
  const semilla=r.semilla?.resultados??[];
  const breve=x=>String(x?.id??'no disponible').slice(0,8);
  const motivosTabla=CASOS.map(caso=>`| ${caso} | ${r.casos[caso].estado} | ${limpiar(r.casos[caso].motivo)} |`).join('\n');
  const precondicion=`Activo ${r.semilla?.id_activo_biologico??'no disponible'}; resultados ${semilla.slice(0,3).map(breve).join(', ')||'no disponibles'} para 219; ${breve(semilla[3])} para 220; el tercer registro de 219 para 221; el primero de 219 para traza de 222; ${breve(semilla[4])} para 246. Reemplazos para los intentos incompletos de 222: ${semilla.slice(5).map(breve).join(', ')||'no disponibles'}. Todos los resultados seleccionados constan en resultado.json con su fecha, modelo y versión.`;
  const detalles=CASOS.map((caso,i)=>{
    const z=r.casos[caso],estado=z.estado,comprobacion=r.comprobaciones.find(x=>x.caso===caso);
    const hecho=z.que_se_hizo??'La evaluación se interrumpió antes de ejecutar las peticiones del caso.';
    const esperado=z.esperado_referencia??z.esperado??'Oráculo pendiente de evaluación.';
    const observado=z.observado_prosa??'No se obtuvieron lecturas suficientes para describir la ejecución.';
    const razon=estado==='APROBADO'?z.por_que_prosa:(z.motivo??'No hay datos suficientes para concluir.');
    return `### ${caso} — ${estado}\n\n- **Qué se hizo:** ${limpiar(hecho)}\n- **Qué se esperaba:** ${limpiar(esperado)}\n- **Qué se observó:** ${limpiar(observado)}\n- **Por qué ${estado}:** ${limpiar(razon)}\n\nComprobación ${comprobacion?.id??IDS[i]}: ${estado}; evidencia ${comprobacion?.evidencia??'preflight.json'} y resultado.json.\n`;
  }).join('\n');
  const solicitudes=r.solicitudes.filter(x=>x.herramienta==='Newman');
  const intentos=solicitudes.map(x=>`| ${x.nombre??'—'} | ${x.http??'—'} | ${limpiar(x.respuesta?.error_code||'—')} | ${limpiar(x.respuesta?.message||'—')} |`).join('\n');
  const incidencias=r.incidencias.map(x=>`- ${x.id}: ${x.caso}; ${x.severidad} (${x.certeza}); atención inicial ${x.equipo}. ${x.justificacion_severidad} Derivación: ${x.fundamento_derivacion}. Causa raíz ${x.causa_raiz}.`).join('\n')||'Ninguna.';
  const evidencias=[...new Set([...r.evidencias,'resultado.json',informeNombre(c.version)])];
  const alcance246=r.casos[CASOS[4]].alertas_iniciales===0?
    'La semilla no tenía alertas derivadas; se comprobó que no se creó ni cambió ninguna alerta del activo, sin acreditar conservación de una alerta existente.':
    'Las alertas visibles del activo se compararon antes y después del registro.';
  const texto=`# TC-M04-G071 — ${veredicto}\n\n## Identificación\n\nGrupo G071; casos ${CASOS.join(', ')}; RF-72; versión ${c.version}; RUN ${c.runId}; ambiente ${r.ambiente}; autorización ${c.referencia}; commit revisado origin/test daefc3a5c62771c8952706ae7a7fe128e66b0b02. Node.js y Newman ${r.herramientas.newman.version??'no disponible'}; solo API.\n\n## Decisión del caso\n\n| Caso | Veredicto | Decisión en lenguaje llano |\n|---|---|---|\n${motivosTabla}\n\nRUN oficial: ${r.oficial?'sí':'no'}. Qué falta: ${r.oficial?'nada':'completar los casos y verificar el cierre mediante lectura pública'}.\n\n## Precondición de datos\n\n${precondicion}\n\n## Detalle por caso\n\n${detalles}\n## Intentos Newman\n\n| Intento | HTTP | Código | Mensaje |\n|---|---:|---|---|\n${intentos}\n\n## Observaciones\n\nOBS-M04-G071-246 — ${alcance246} Las inferencias posteriores se verifican mediante la versión activa, la configuración del motor y la ausencia de resultados nuevos, sin ejecutar una inferencia. La verificación se hizo por API dentro del sandbox; la matriz sugería BD y no se usó SQL.\n\n## Incidencias de producto\n\n${incidencias}\n\n## Problemas técnicos y análisis de causas\n\n${r.problemas_tecnicos.map(limpiar).join('; ')||'Ninguno.'} La revisión previa de código en origin/test orienta la prueba, sin demostrar por sí sola un defecto en TEST ni una causa raíz.\n\n## Cierre y rollback\n\nIntento ${c.intento}; solicitudes ${r.solicitudes.length}/${PRESUPUESTO.solicitudes_totales}. DELETE HTTP ${r.cierre.run.cierre_http??'—'}. Rollback ${r.cierre.rollback.verificado?'verificado':'no verificado'}: ${r.cierre.rollback.motivo}. Las lecturas posteriores pueden generar HISTORIAL_CONSULTADO fuera del sandbox.\n\n## Conclusión y acciones\n\n${veredicto==='APROBADO'?'Los cinco casos cumplen sus oráculos; archivar esta evidencia y mantener la observación de alcance del caso 246.':veredicto==='RECHAZADO'?'Derivar las discrepancias de producto y repetir tras corrección autorizada.':'Resolver las lecturas o el cierre pendientes y repetir con autorización particular.'}\n\n## Herramientas y evidencias\n\nNewman: ${r.herramientas.newman.iteraciones} iteración; ${r.herramientas.newman.solicitudes} solicitudes; ${r.herramientas.newman.aserciones} aserciones. Sin UI obligatoria.\n\n${evidencias.map(x=>`- ${x}`).join('\n')}\n`;
  return texto.replace(/\.\./g,'.');
}
export async function evaluar(c,{env=leerEnv(),newmanVersion=versionNewman()}={}){
  const r={grupo:'G071',run_id:c.runId,version:c.version,intento:c.intento,referencia:c.referencia,
    ambiente:c.ensayo?'loopback local':'TEST',casos:Object.fromEntries(CASOS.map(x=>[x,{estado:'NO_CONCLUYENTE',motivo:'No evaluado'}])),
    comprobaciones:[],solicitudes:[],incidencias:[],observaciones:[],problemas_tecnicos:[],semilla:{},
    herramientas:{newman:{...newmanVersion,iteraciones:0,solicitudes:0,aserciones:0}},cypress:{total_pruebas:0},
    cierre:{run:{cierre_http:null},rollback:{verificado:false,motivo:'No comprobado'}},
    evidencias:[],oficial:false,consume_version:false,_limite:Date.now()+(PRESUPUESTO.duracion_segundos-30)*1000};
  const pre=preflight(c,env,newmanVersion);
  if(!pre.ok){r.problemas_tecnicos.push(`PREFLIGHT: ${pre.barreras.join(', ')}`);
    if(pre.barreras.includes('NEWMAN_NO_DISPONIBLE'))for(const x of CASOS)r.casos[x]={estado:'BLOQUEADO',motivo:'Newman no disponible antes de cualquier petición'};
    delete r._limite;return r;}
  fs.mkdirSync(c.directorio,{recursive:true});guardar(path.join(c.directorio,'preflight.json'),pre);r.evidencias.push('preflight.json');
  const api=String(env.SIGAB_API_TEST_BASE).replace(/\/+$/,'');
  const inicio=fecha(Date.now()-88*86400000),fin=fecha(Date.now());
  let iniciado=false,token=null,usuario=null,base=null,posterior=null,ejec={},seleccion=[],diag=null;
  try{iniciado=true;
    const login=await pedir(r,api,'POST','/sesiones/',{cuerpo:{correo_electronico:env.QA_VETERINARIO_EMAIL,
      contrasena:env.QA_COMMON_PASSWORD},timeout:PRESUPUESTO.timeout_login_ms});
    if(login.http!==200||!login.cuerpo?.token)throw Error(`LOGIN_VETERINARIO_${login.http??'SIN_RED'}`);
    token=login.cuerpo.token;usuario=usuarioDelToken(token);if(!usuario)throw Error('LOGIN_SIN_USUARIO');
    base=await historial(r,api,token,env.QA_SANDBOX_SECRET,c.runId,inicio,fin);
    if(!base.completo)throw Error(base.http===403&&r.solicitudes.at(-1)?.respuesta?.error_code==='CLAVE_INVALIDA'?
      'CLAVE_403':`HISTORIAL_DESCUBRIMIENTO_${base.http??'SIN_RED'}`);
    seleccion=seleccionar(base.eventos,usuario,{},Date.now());
    r.semilla={id_activo_biologico:885,resultados:seleccion.map(e=>({id:e.id_resultado_inferencia,
      fecha:e.fecha_evento,tipo_modelo:e.payload?.tipo_modelo,id_version_modelo:e.payload?.id_version_modelo}))};
    if(seleccion.length<5)throw Error(`DATOS_INSUFICIENTES_${seleccion.length}_DE_5`);
    const catalogo=await pedir(r,api,'GET','/prediccion/patologias?solo_activas=true',{token,secreto:env.QA_SANDBOX_SECRET,runId:c.runId});
    if(catalogo.http!==200||!Array.isArray(catalogo.cuerpo?.items))throw Error(`CATALOGO_${catalogo.http??'SIN_RED'}`);
    diag=patologiaDistinta(catalogo.cuerpo.items,seleccion[3].payload?.id_patologia);
    if(diag==null||diag===seleccion[4].payload?.id_patologia){diag=catalogo.cuerpo.items.find(x=>x.es_activo===true&&
      x.id_patologia>=8&&x.id_patologia<=14&&x.id_patologia!==seleccion[3].payload?.id_patologia&&
      x.id_patologia!==seleccion[4].payload?.id_patologia)?.id_patologia??null;}
    if(diag==null)throw Error('PATOLOGIA_DISTINTA_NO_DISPONIBLE');
    const modelo=await pedir(r,api,'GET',`/prediccion/modelos/${seleccion[4].payload?.id_version_modelo??43}`,
      {token,secreto:env.QA_SANDBOX_SECRET,runId:c.runId});
    if(modelo.http!==200||modelo.cuerpo?.paradigma!=='INDIVIDUAL')throw Error(`MODELO_INDIVIDUAL_NO_CONFIRMADO_${modelo.http??'SIN_RED'}`);
    const openapi=await pedir(r,api,'GET','/openapi.json',{token,secreto:env.QA_SANDBOX_SECRET,runId:c.runId});
    if(openapi.http!==200)r.observaciones.push(`OpenAPI previo no disponible: HTTP ${openapi.http??'sin respuesta'}. La colección repite la lectura para TC-M04-221.`);
    ejec=await newmanUnico(r,c,api,env,token,seleccion,diag);
    posterior=await historial(r,api,token,env.QA_SANDBOX_SECRET,c.runId,inicio,fin);
    const aud=await pedir(r,api,'GET','/prediccion/auditoria?tipo_evento=RETROALIMENTACION_REGISTRADA&por_pagina=200',
      {token,secreto:env.QA_SANDBOX_SECRET,runId:c.runId});
    r.observaciones.push(`Auditoría HTTP ${aud.http??'sin respuesta'}; eventos de la página ${aud.cuerpo?.items?.length??'no disponible'}.`);
    evaluarCasos(r,c,ejec,seleccion,posterior,usuario,diag);
  }catch(e){r.problemas_tecnicos.push(limpiar(e.message));
    const motivo=limpiar(e.message);
    for(const x of CASOS)if(r.casos[x].estado==='NO_CONCLUYENTE')r.casos[x]={estado:/LOGIN|CLAVE|NEW[R]?MAN/.test(motivo)?'BLOQUEADO':'NO_CONCLUYENTE',
      motivo:`Evaluación incompleta: ${motivo}`};
  }finally{
    if(iniciado){const cierre=await pedir(r,api,'DELETE',`/test-control/runs/${encodeURIComponent(c.runId)}`,
      {secreto:env.QA_SANDBOX_SECRET});r.cierre.run.cierre_http=cierre.http;
      let pos=null;try{pos=token&&base?.completo?await historial(r,api,token,env.QA_SANDBOX_SECRET,c.runId,inicio,fin):null;}
      catch(e){r.problemas_tecnicos.push(`POSCIERRE: ${limpiar(e.message)}`);}
      const nuevos=Object.values(ejec).filter(x=>x.http===201).map(x=>x.cuerpo?.id_retroalimentacion).filter(uuid);
      const ausentes=pos?.completo&&nuevos.every(id=>!retro(pos.eventos,id));
      const estadoBase=pos?.completo&&base?.completo&&['RETROALIMENTACION','INFERENCIA','ALERTA'].every(tipo=>
        iguales(eventosDe(base.eventos,tipo),eventosDe(pos.eventos,tipo)));
      r.cierre.rollback={verificado:cierre.http===200&&!!ausentes&&!!estadoBase,
        motivo:cierre.http===200&&ausentes&&estadoBase?
          'DELETE 200; identificadores nuevos ausentes y eventos de retroalimentación, inferencia y alerta iguales al descubrimiento':
          'DELETE o lectura poscierre sin confirmar restauración del historial inicial'};
    }
    for(const [i,x] of CASOS.entries())if(!r.comprobaciones.some(z=>z.caso===x))r.comprobaciones.push({
      caso:x,fuente:'API',id:IDS[i],tipo:'ASSERT',estado:r.casos[x].estado,evidencia:r.evidencias.includes('newman/newman-G071.json')?'newman/newman-G071.json':'preflight.json'});
    r.oficial=CASOS.every(x=>['APROBADO','RECHAZADO'].includes(r.casos[x].estado))&&
      r.herramientas.newman.iteraciones===1&&r.herramientas.newman.solicitudes===23&&r.cierre.rollback.verificado;
    r.consume_version=r.oficial;delete r._limite;
    if(fs.existsSync(c.directorio)){
      const secretos=[token,env.QA_SANDBOX_SECRET,env.QA_COMMON_PASSWORD,env.QA_VETERINARIO_EMAIL];
      r.evidencias.push('resultado.json',informeNombre(c.version));
      guardar(path.join(c.directorio,'resultado.json'),JSON.parse(sanear(JSON.stringify(r),secretos)));
      fs.writeFileSync(path.join(c.directorio,informeNombre(c.version)),sanear(informeNuevo(r,c),secretos),'utf8');
    }
  }return r;
}
async function recuperar(c){const env=leerEnv(),r={solicitudes:[],_limite:Date.now()+PRESUPUESTO.timeout_ms};
  const previo=JSON.parse(fs.readFileSync(path.join(c.directorio,'resultado.json'),'utf8'));
  if(previo.run_id!==c.runId||previo.version!==c.version)throw Error('RUN previo incoherente');
  const x=await pedir(r,String(env.SIGAB_API_TEST_BASE).replace(/\/+$/,''),'DELETE',
    `/test-control/runs/${encodeURIComponent(c.runId)}`,{secreto:env.QA_SANDBOX_SECRET});
  const salida={run_id:c.runId,cierre_http:x.http,rollback_verificado:false,
    motivo:'DELETE de recuperación sin verificación pública de ausencia; requiere conciliación'};
  guardar(path.join(c.directorio,`recuperacion-${Date.now()}.json`),salida);return salida;}
if(process.argv.includes('--capacidades'))console.log(JSON.stringify(CAPACIDADES,null,2));
else if(process.argv.includes('--comprobar'))process.exitCode=comprobar();
else if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
  try{const c=contexto(process.argv.slice(2));const r=c.operacion==='recuperar'?await recuperar(c):await evaluar(c);
    console.log(JSON.stringify({grupo:'G071',run_id:c.runId,oficial:r.oficial??false,casos:r.casos??null}));
    if(!r.oficial)process.exitCode=2;}catch(e){console.error(limpiar(e.message));process.exitCode=2;}}
