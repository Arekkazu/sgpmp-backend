import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import {spawn} from 'node:child_process';
import os from 'node:os';
import {contrato,validarLecturas,validarError,esquema} from './lib/contrato.mjs';
import {CASOS,LIMITE,precondiciones,porVersion,estados,iguales,cuerpo,fechaFutura,clasificarRechazo,evaluarRegistro,evaluarAuditoria,clasificarUI,veredictos,severidadRegla} from './lib/g036_core.mjs';
const DIR=path.dirname(fileURLToPath(import.meta.url));
const ROOT=path.resolve(DIR,'../../../../..');
const API='https://www.api.inmero.co/api-sgpmp-test';
const FRONT='https://api.inmero.co/sigab-test';
export const CAPACIDADES={contrato:'sigab-qa-ejecutor/1',grupo:'G036',casos:CASOS,operaciones:['evaluar','reintentar'],versiones:{min:1,max:1},comprobaciones_obligatorias:{'TC-M07-01':{API:['registro_v4_0','auditoria']},'TC-M07-02':{API:['duplicado']},'TC-M07-03':{API:['anexo_inexistente','anexo_borrador','anexo_revision']},'TC-M07-04':{API:['mappers_vacios','mapper_invalido']},'TC-M07-05':{API:['registro_v4_2'],UI:['tabla_acciones']}},limite:LIMITE};
const sha=p=>createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const guardar=(p,x)=>fs.writeFileSync(p,JSON.stringify(sanitize(x),null,2));
const seguro=x=>String(x??'').replace(/eyJ[\w-]+\.[\w-]+\.[\w-]+/g,'[JWT]').replace(/[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}/g,'[CORREO]');
export const sanitize=x=>Array.isArray(x)?x.map(sanitize):x&&typeof x==='object'?Object.fromEntries(Object.entries(x).map(([k,v])=>[k,/correo_electronico|correo|email/i.test(k)?'[CORREO]':/token|secret|password|cookie|authorization|sha256_documento|contrasena|contraseña|clave|access_key|refresh/i.test(k)?'[RESERVADO]':sanitize(v)])):typeof x==='string'?seguro(x):x;
function lanzarCypress(input){return new Promise(resolve=>{let hijo;try{hijo=spawn(process.execPath,[path.join(DIR,'pruebas/cypress_hijo.mjs')],{cwd:DIR,stdio:['pipe','pipe','pipe'],windowsHide:true});}catch(error){resolve({status:null,error,stdout:''});return;}let stdout='',error=null;const timer=setTimeout(()=>{error??=Object.assign(new Error('CYPRESS_TIMEOUT'),{code:'ETIMEDOUT'});hijo.kill();},240000);hijo.stdout.on('data',x=>stdout+=x);hijo.stderr.on('data',()=>{});hijo.on('error',e=>{error=e;});hijo.on('close',status=>{clearTimeout(timer);resolve({status,error,stdout});});hijo.stdin.on('error',()=>{});hijo.stdin.end(JSON.stringify(input));});}
export function comprobar(){const archivos=['g036.mjs','lib/contrato.mjs','lib/g036_core.mjs','pruebas/contrato_g036.json','pruebas/fixture_g036.json','G036.postman_collection.json','g036.cy.js','g036.cypress.config.cjs','pruebas/newman_hijo.mjs','pruebas/g036_local.test.mjs','pruebas/g036_dto.test.py','pruebas/verificar.mjs','pruebas/simulador_g036.mjs','pruebas/escenarios_g036.mjs','pruebas/escenarios_g036.json','pruebas/cypress_hijo.mjs','lib/intercepcion.cjs','README.md'];const faltan=archivos.filter(x=>!fs.existsSync(path.join(DIR,x)));const col=JSON.parse(fs.readFileSync(path.join(DIR,'G036.postman_collection.json'),'utf8'));const ok=!faltan.length&&col.item.length>0&&contrato.rutas.every(x=>x.cita?.startsWith('src/'))&&(!fs.existsSync(path.join(DIR,'Resultados'))||fs.readdirSync(path.join(DIR,'Resultados')).every(x=>['RUN-G036-V1-20261118-034446','RUN-G036-V1-20261118-040435'].includes(x)));console.log(JSON.stringify({grupo:'G036',ok,faltan,coleccion:col.item.length,sha256:Object.fromEntries(archivos.filter(x=>fs.existsSync(path.join(DIR,x))).map(x=>[x,sha(path.join(DIR,x))]))}));return ok?0:2;}
export function leerEnv(proceso=process.env,archivo=path.join(ROOT,'.env.qa')){const e={};if(proceso.QA_AUTORIZADO==='SI'&&fs.existsSync(archivo))for(const line of fs.readFileSync(archivo,'utf8').split(/\r?\n/)){const m=line.match(/^\s*([A-Z][A-Z0-9_]*)\s*=(.*)$/);if(m)e[m[1]]=m[2].trim().replace(/^(['"])(.*)\1$/,'$2');}Object.assign(e,proceso);e.QA_AUTORIZADO=proceso.QA_AUTORIZADO;return e;}
const loopback=x=>{try{const u=new URL(x);return u.protocol==='http:'&&['127.0.0.1','localhost'].includes(u.hostname)&&!!u.port&&!u.pathname.match(/\/\/$/);}catch{return false;}};
export function contexto(args,prueba=false){
  const arg=k=>args.includes(k)?args[args.indexOf(k)+1]:null;
  const operacion=arg('--operacion'),version=Number(arg('--version')),intento=Number(arg('--intento'));
  const runId=arg('--run-id'),referencia=arg('--autorizacion'),archivo=arg('--contexto');
  if(!CAPACIDADES.operaciones.includes(operacion)||version!==1||!Number.isInteger(intento)||intento<1||!referencia||!/^RUN-G036-V1-\d{8}-\d{6}$/.test(runId??''))throw Error('CONTEXTO_INCOMPLETO');
  const dir=prueba?path.dirname(path.resolve(archivo??'.')):path.join(DIR,'Resultados',runId);
  if(prueba&&(path.basename(dir)!==runId||!dir.startsWith(path.resolve(os.tmpdir())+path.sep)))throw Error('PRUEBA_FUERA_TEMPORAL');
  if(!archivo||path.resolve(archivo)!==path.join(dir,'contexto_operacion.json'))throw Error('CONTEXTO_FUERA_RUN');
  const dato=JSON.parse(fs.readFileSync(archivo,'utf8'));
  if(dato.grupo!=='G036'||dato.run_id!==runId||dato.version!==version||dato.intento!==intento||dato.operacion!==operacion.toUpperCase()||dato.referencia!==referencia||JSON.stringify(dato.casos)!==JSON.stringify(CASOS))throw Error('CONTEXTO_INCOHERENTE');
  return{dir,runId,version,intento,operacion,referencia,ensayo:prueba,estricto:prueba};
}
export function preflight(c,e){const faltan=[];for(const k of ['QA_ADMIN_EMAIL','QA_ADMIN_PASSWORD','QA_SANDBOX_SECRET','SIGAB_API_TEST_BASE'])if(!String(e[k]??'').trim())faltan.push(k);if(e.QA_AUTORIZADO!=='SI')faltan.push('QA_AUTORIZADO');const api=String(e.SIGAB_API_TEST_BASE??'').replace(/\/+$/,'');const front=String(e.SIGAB_FRONT_TEST_BASE??FRONT).replace(/\/+$/,'');if(c.ensayo?!loopback(api):api!==API)faltan.push('API_NO_CANONICA');if(c.ensayo?!loopback(front):front!==FRONT)faltan.push('FRONT_NO_CANONICO');if(!/^RUN-G036-V1-\d{8}-\d{6}$/.test(c.runId??''))faltan.push('RUN_ID');if(!c.referencia)faltan.push('AUTORIZACION');return{ok:!faltan.length,faltan,grupo:'G036',run_id:c.runId,version:c.version??1,referencia:c.referencia,presupuesto:LIMITE};}
const hoy=()=>new Intl.DateTimeFormat('en-CA',{timeZone:'America/Bogota',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
export function decisionLogin({runAbierto=false,loginIntentado=false,loginFallido=false}={}){if(loginFallido)return 'LOGIN_FALLIDO_SIN_REINTENTO';if(runAbierto)return 'LOGIN_DENTRO_RUN';if(loginIntentado)return 'SEGUNDO_LOGIN';return 'PERMITIDO';}
export async function ejecutar(c,e,fetcher=fetch,ensayoLocal={}){const pf=preflight(c,e);if(!pf.ok)throw Error(`PREFLIGHT_${pf.faltan.join('_')}`);if(!c.ensayo&&Object.keys(ensayoLocal).length)throw Error('DOBLES_SOLO_ENSAYO');const dir=c.ensayo?path.resolve(c.dir??''):path.join(DIR,'Resultados',c.runId);if(c.ensayo&&(path.basename(dir)!==c.runId||!dir.startsWith(path.resolve(os.tmpdir())+path.sep)))throw Error('ENSAYO_FUERA_TEMPORAL');if(fs.existsSync(path.join(dir,'resultado.json'))||fs.existsSync(path.join(dir,'TC-M07-G036_resultado.md')))throw Error('RUN_EXISTENTE');const r={grupo:'G036',run_id:c.runId,version:1,casos:CASOS,autorizacion:c.referencia,solicitudes:[],pruebas:{},seleccion:{},incidencias:[],oficial:false,cierre:{rollback:{verificado:false,motivo:'No ejecutado'}},evidencias:[],problemas_tecnicos:[]};const deadline=Date.now()+LIMITE.duracion_segundos*1000;let token=null,serial=false,cerrado=false,runAbierto=false,loginIntentado=false,base=null,anexos=null;const apiBase=String(e.SIGAB_API_TEST_BASE).replace(/\/+$/,'');
  async function pedir(metodo,ruta,body,autenticado=true){if(serial)throw Error('PETICION_CONCURRENTE');if(r.solicitudes.length+(r.newman?.solicitudes??0)>=80||Date.now()>deadline)throw Error('PRESUPUESTO_AGOTADO');if(!esquema(metodo,ruta)||ruta==='/sesiones/refresh')throw Error(`RUTA_FUERA_CONTRATO_${metodo}_${ruta}`);const login=metodo==='POST'&&ruta==='/sesiones/';if(login){const d=decisionLogin({runAbierto,loginIntentado});if(d!=='PERMITIDO')throw Error(d);loginIntentado=true;}else if(!token)throw Error('LOGIN_REQUERIDO');serial=true;const row={id:`G036-${String(r.solicitudes.length+1).padStart(3,'0')}`,metodo,ruta:ruta.split('?')[0],http:null,...(login?{actor:'Administrador',momento:'ANTES_DEL_RUN',efecto_persistente:'último acceso, auditoría de sesión y notificación de login con escritura independiente'}:{})};if(metodo==='POST')row.cuerpo_solicitud=sanitize(body);r.solicitudes.push(row);try{const headers={...(autenticado?{Authorization:`Bearer ${token}`}:{}) ,...(login||cerrado?{}:{'X-Test-Run-Id':c.runId,'X-Sandbox-Secret':e.QA_SANDBOX_SECRET}),...(body===undefined?{}:{'Content-Type':'application/json'})};if(!login&&!cerrado)runAbierto=true;const z=await fetcher(apiBase+ruta,{method:metodo,headers,redirect:'manual',...(body===undefined?{}:{body:JSON.stringify(body)}),signal:AbortSignal.timeout(120000)});row.http=z.status;const raw=await z.json().catch(()=>null);if(metodo==='POST')row.cuerpo_respuesta=sanitize(raw);row.eco=z.headers.get('x-test-run-id')===c.runId;if(!login&&!cerrado&&(!row.eco||z.status>=500))throw Error(`SANDBOX_O_INFRA_${row.id}_${z.status}`);let data=raw;if(z.status>=200&&z.status<300)data=validarLecturas(raw,metodo,ruta,{estricto:!!c.estricto});if(z.status>=400){row.error=raw?.error_code??null;row.cuerpo_error=sanitize(raw);row.error_estandar=validarError(raw);}return{http:z.status,data,raw};}finally{serial=false;}}
  const get=async ruta=>{const z=await pedir('GET',ruta);if(z.http!==200)throw Error(`LECTURA_${ruta}_${z.http}`);return z.data;};
  const listar=async ruta=>{const v=await get(ruta);if(!Array.isArray(v))throw Error('LISTA_INVALIDA');return v;};
  const auditar=async()=>{let pagina=1,items=[],total=0;do{const x=await get(`/integracion/auditoria?tipo_evento=CONTRATO_REGISTRADO&desde=${hoy()}&pagina=${pagina}&tamano=100`);items.push(...x.items);total=x.total;if(++pagina>20||items.length>total)throw Error('AUDITORIA_PAGINACION');}while(items.length<total);return items;};
  const verificar=async(z,esperado,baseline,version)=>clasificarRechazo(z,esperado,baseline,await listar('/integracion/contratos'),version);
  try{
    const sesion=await pedir('POST','/sesiones/',{correo_electronico:e.QA_ADMIN_EMAIL,contrasena:e.QA_ADMIN_PASSWORD},false);if(sesion.http!==200)throw Error('LOGIN_FALLIDO');token=sesion.data.token;fs.mkdirSync(dir,{recursive:true});
    const permisos=(await get('/sesiones/me/permisos')).permisos;anexos=await listar('/integracion/anexos');base=await listar('/integracion/contratos');const auditBase=await auditar();const p=precondiciones(anexos,base,permisos);r.preflight_datos=p.preflight_datos;r.seleccion={aprobado:p.aprobado?.id_mapeo_anexo_aaef??null,revision:p.revision?.id_mapeo_anexo_aaef??null,duplicado:p.existente?.contrato_version??null,criterio:'mayor id por estado; duplicado ACTIVO o mayor id'};if(p.faltan.length){r.bloqueos=p.faltan;r.veredictos=veredictos({preflight:true});return r;}
    const fecha=fechaFutura(),baseEstado=estados(base),anexo=p.aprobado.id_mapeo_anexo_aaef;const z02=await pedir('POST','/integracion/contratos',cuerpo(p.existente.contrato_version,anexo,fecha));r.pruebas['02']=await verificar(z02,'VERSION_DUPLICADA',baseEstado,'4.0');
    const z03a=await pedir('POST','/integracion/contratos',cuerpo('4.0',999999,fecha));r.pruebas['03a']=await verificar(z03a,'ANEXO_MAPEO_INVALIDO',baseEstado,'4.0');
    const anexoBody={codigo_anexo:'QA-G036-BORRADOR',version_anexo:'4.0',ruta_documento:'docs/qa/QA-G036-BORRADOR.md',sha256_documento:createHash('sha256').update('QA-G036-BORRADOR').digest('hex')};const nuevoAnexo=await pedir('POST','/integracion/anexos',anexoBody);if(nuevoAnexo.http===201&&nuevoAnexo.data.estado==='BORRADOR'){const z03b=await pedir('POST','/integracion/contratos',cuerpo('4.0',nuevoAnexo.data.id_mapeo_anexo_aaef,fecha));r.pruebas['03b']=await verificar(z03b,'ANEXO_MAPEO_INVALIDO',baseEstado,'4.0');}else r.pruebas['03b']='NO_CONCLUYENTE';
    const z04a=await pedir('POST','/integracion/contratos',cuerpo('4.0',anexo,fecha,[]));r.pruebas['04a']=await verificar(z04a,'MAPPERS_INVALIDOS',baseEstado,'4.0');const z04b=await pedir('POST','/integracion/contratos',cuerpo('4.0',anexo,fecha,['MAPPER_X']));r.pruebas['04b']=await verificar(z04b,'MAPPERS_INVALIDOS',baseEstado,'4.0');
    const body01=cuerpo('4.0',anexo,fecha),z01=await pedir('POST','/integracion/contratos',body01),despues01=await listar('/integracion/contratos'),audit01=await auditar();const usuario=Number(JSON.parse(Buffer.from(token.split('.')[1],'base64url').toString('utf8')).sub);r.pruebas['01_registro']=evaluarRegistro(z01,despues01,body01);r.pruebas['01_auditoria']=evaluarAuditoria(auditBase,audit01,'4.0',usuario);r.pruebas['01']=r.pruebas['01_registro']&&r.pruebas['01_auditoria'];
    if(p.revision){const body03c=cuerpo('4.1',p.revision.id_mapeo_anexo_aaef,fecha),z03c=await pedir('POST','/integracion/contratos',body03c);r.pruebas['03c']=z03c.http===201?evaluarRegistro(z03c,await listar('/integracion/contratos'),body03c):z03c.data?.error_code==='ANEXO_MAPEO_INVALIDO'?'RECHAZADO':'NO_CONCLUYENTE';}else r.pruebas['03c']='NO_CONCLUYENTE';
    const newmanInput={coleccion:JSON.parse(fs.readFileSync(path.join(DIR,'G036.postman_collection.json'),'utf8')),environment:{values:[['base_url',apiBase],['run_id',c.runId],['sandbox_secret',e.QA_SANDBOX_SECRET],['admin_token',token]].map(([key,value])=>({key,value,enabled:true}))},salida:path.join(dir,'newman')};try{r.newman=await(ensayoLocal.newman?ensayoLocal.newman(newmanInput): (await import('./pruebas/newman_hijo.mjs')).ejecutar(newmanInput));r.evidencias.push(...['newman/newman-G036.json','newman/newman-G036.html'].filter(x=>fs.existsSync(path.join(dir,x))));}catch(err){r.newman={codigo:2,error:seguro(err.message)};}
    const cypDir=path.join(dir,'cypress');fs.mkdirSync(cypDir,{recursive:true});const versiones=Object.fromEntries(['ACTIVO','DEPRECADO','INACTIVO'].map(estado=>[estado,base.filter(x=>x.estado===estado).sort((a,b)=>b.id_version_contrato_aaef-a.id_version_contrato_aaef)[0]?.contrato_version??null]));const childInput={api:c.ensayo?apiBase:API,front:c.ensayo?e.SIGAB_FRONT_TEST_BASE:FRONT,dir:cypDir,runId:c.runId,token,secret:e.QA_SANDBOX_SECRET,fecha,anexoId:anexo,anexoCodigo:p.aprobado.codigo_anexo,versiones,localSmoke:!!c.ensayo};const cr=ensayoLocal.cypress?null:await(ensayoLocal.lanzarCypress??lanzarCypress)(childInput);let child=null;if(ensayoLocal.cypress)child=await ensayoLocal.cypress(childInput);else try{child=JSON.parse(cr.stdout);}catch{}r.cypress={codigo:child?.codigo??cr?.status??2,error:cr?.error?.code??null,total_pruebas:child?.totalTests??0};if(fs.existsSync(path.join(cypDir,'G036-cypress.json')))r.evidencias.push('cypress/G036-cypress.json');if(fs.existsSync(path.join(cypDir,'G036-cypress-salida.log')))r.evidencias.push('cypress/G036-cypress-salida.log');const actaPath=path.join(cypDir,'G036-UI-05.json');const video=path.join(cypDir,'videos','g036.cy.js.mp4');if(child?.acta||fs.existsSync(actaPath)){const acta=sanitize(child?.acta??JSON.parse(fs.readFileSync(actaPath,'utf8')));acta.error??=sanitize(child?.error??null);acta.video=fs.existsSync(video)&&fs.statSync(video).size>0;fs.writeFileSync(actaPath,JSON.stringify(sanitize(acta),null,2));const evaluacion=clasificarUI(acta,r.cypress.codigo);r.pruebas['05_ui']=evaluacion.ui;r.pruebas['05']=evaluacion.ui;r.cypress.fallo_producto=evaluacion.ui===false&&!evaluacion.problema;r.registro_ui_enviado=acta.hitos?.registro_enviado===true;if(evaluacion.problema)r.problemas_tecnicos.push(seguro(evaluacion.problema));r.evidencias.push('cypress/G036-UI-05.json');}else {r.pruebas['05_ui']='NO_CONCLUYENTE';r.pruebas['05']='NO_CONCLUYENTE';r.problemas_tecnicos.push(seguro(child?.error||cr?.error?.message||'Cypress no genero acta UI'));}if(fs.existsSync(video))r.evidencias.push('cypress/videos/g036.cy.js.mp4');const capturas=path.join(cypDir,'screenshots');if(fs.existsSync(capturas)){const recorrer=(d,rel)=>{for(const x of fs.readdirSync(d,{withFileTypes:true})){const q=path.join(d,x.name),n=rel+'/'+x.name;if(x.isDirectory())recorrer(q,n);else if(n.endsWith('.png'))r.evidencias.push(n);}};recorrer(capturas,'cypress/screenshots');}
    if(r.registro_ui_enviado){const uiContrato=await listar('/integracion/contratos');r.pruebas['05_api']=porVersion(uiContrato,'4.2')?.estado==='PENDIENTE';}
    else r.pruebas['05_api']='NO_CONCLUYENTE';
    r.pruebas['05']=r.pruebas['05_ui']==='NO_CONCLUYENTE'?'NO_CONCLUYENTE':r.pruebas['05_ui']&&r.pruebas['05_api'];r.veredictos=veredictos({r01:r.pruebas['01'],r02:r.pruebas['02'],r03a:r.pruebas['03a'],r03b:r.pruebas['03b'],r03c:r.pruebas['03c'],sinRevision:!p.revision,r04a:r.pruebas['04a'],r04b:r.pruebas['04b'],r05:r.pruebas['05']});r.estado='PRUEBAS_COMPLETADAS';return r;
  }catch(err){r.problemas_tecnicos.push(seguro(err.message));r.veredictos??=veredictos({preflight:true});return r;}finally{if(runAbierto){try{const z=await fetcher(`${apiBase}/test-control/runs/${c.runId}`,{method:'DELETE',headers:{'X-Sandbox-Secret':e.QA_SANDBOX_SECRET},signal:AbortSignal.timeout(120000)});r.cierre.http=z.status;cerrado=z.status===200;if(cerrado&&base&&anexos){const posteriorC=await listar('/integracion/contratos'),posteriorA=await listar('/integracion/anexos');r.cierre.rollback={verificado:verificarRollback(base,posteriorC,anexos,posteriorA),motivo:'Lecturas públicas poscierre sin cabeceras de RUN'};}else r.cierre.rollback={verificado:false,motivo:cerrado?'Línea base incompleta':'DELETE no confirmó 200'};}catch(err){r.cierre.rollback={verificado:false,motivo:seguro(err.message)};}}r.solicitudes=sanitize(r.solicitudes);r.oficial=esOficial(r,deadline);r.solicitudes_total=r.solicitudes.length+(r.newman?.solicitudes??0);completarResultado(r,c);if(token){guardar(path.join(dir,'resultado.json'),r);fs.writeFileSync(path.join(dir,'TC-M07-G036_resultado.md'),informe(c,sanitize(r)));}}
}
function mismosIdsYEstados(antes,despues,campoId){
  if(antes.length!==despues.length)return false;
  const estados=new Map();
  for(const item of antes){const id=item[campoId];if(estados.has(id))return false;estados.set(id,item.estado);}
  const vistos=new Set();
  for(const item of despues){const id=item[campoId];if(vistos.has(id)||!estados.has(id)||estados.get(id)!==item.estado)return false;vistos.add(id);}
  return true;
}
export function verificarRollback(base,posteriorC,anexos,posteriorA){
  return mismosIdsYEstados(base,posteriorC,'id_version_contrato_aaef')&&mismosIdsYEstados(anexos,posteriorA,'id_mapeo_anexo_aaef')&&!posteriorC.some(item=>['4.0','4.1','4.2'].includes(item.contrato_version))&&!posteriorA.some(item=>item.codigo_anexo==='QA-G036-BORRADOR');
}
export function esOficial(r,deadline){return Object.values(r.veredictos??{}).length===5&&Object.values(r.veredictos).every(v=>['APROBADO','RECHAZADO'].includes(v))&&r.newman?.codigo===0&&r.newman?.fallos===0&&r.newman?.reportes===true&&(r.cypress?.codigo===0||r.cypress?.fallo_producto===true)&&r.cierre.rollback.verificado&&r.solicitudes.length+(r.newman?.solicitudes??0)<=80&&Date.now()<=deadline;}
export function informe(c,r){
  const solicitud=id=>r.solicitudes.find(x=>x.id===id);
  const post=(version,pred=()=>true)=>r.solicitudes.find(x=>x.metodo==='POST'&&x.ruta==='/integracion/contratos'&&x.cuerpo_solicitud?.contrato_version===version&&pred(x));
  const registro=version=>post(version,x=>x.http===201);
  const error=id=>{const x=solicitud(id),e=x?.cuerpo_error??x?.cuerpo_respuesta??{},f=e.fields?.[0];return x?`HTTP ${x.http}; ${e.error_code??'sin código'}; campo ${f?.field??'no consta'}; «${f?.message??e.message??'sin mensaje'}»`:'petición no registrada';};
  const dato=(x,k)=>x?.cuerpo_respuesta?.[k]??'no consta';
  const fila=(paso,peticion,esperado,observado,cumple)=>`| ${paso} | ${peticion} | ${esperado} | ${observado} | ${cumple===null?'Sin dato':cumple?'Cumple':'Falla'} |`;
  const tabla=rows=>`| Paso | Petición | Esperado | Observado | Resultado |\n|---|---|---|---|---|\n${rows.join('\n')}`;
  const estado=id=>r.casos?.[id]?.estado??'NO_CONCLUYENTE';
  const p01=registro('4.0'),p03=registro('4.1');
  const inc04=r.incidencias?.filter(x=>x.caso==='TC-M07-04')??[];
  const uiFile=path.join(c.dir??path.join(DIR,'Resultados',c.runId),'cypress','G036-UI-05.json');
  let ui=null;try{ui=JSON.parse(fs.readFileSync(uiFile,'utf8'));}catch{}
  let cypressVersion='no consta';try{cypressVersion=fs.readFileSync(path.join(path.dirname(uiFile),'G036-cypress-salida.log'),'utf8').match(/Cypress:\s*(\d+\.\d+\.\d+)/)?.[1]??'no consta';}catch{}
  const titulo=Object.values(r.casos??{}).some(x=>x.estado==='RECHAZADO')?'RECHAZADO':r.oficial?'APROBADO':'NO_CONCLUYENTE';
  const motivos=[
    '4.0 registrada PENDIENTE y visible; auditoría CONTRATO_REGISTRADO comprobada.',
    '2.1 duplicada rechazada con VERSION_DUPLICADA y contratos sin cambio.',
    'Anexos inexistente y BORRADOR rechazados; EN_REVISION aceptado en TEST según RFC-030.',
    'Ambos Mappers inválidos se rechazaron sin crear versión, pero faltó MAPPERS_INVALIDOS.',
    'Cypress comprobó formulario, fila 4.2 PENDIENTE y acciones por estado.'
  ];
  const resumen=CASOS.map((id,i)=>`| ${id} | ${estado(id)} | ${estado(id)==='NO_CONCLUYENTE'?'Comprobación incompleta; revisar preflight, evidencias o entorno.':motivos[i]} |`).join('\n');
  const preflight=(r.preflight_datos??[]).map(x=>`| ${x.requisito} | ${x.esperado} | ${x.observado??'no consta'} | ${x.cumple} |`).join('\n');
  const detalles=[
`### TC-M07-01 — registro válido

**Preparación:** Administrador QA; anexo APROBADO ${r.seleccion?.aprobado??'no consta'} elegido en vivo; versión 4.0 ausente. Vigencia 2027-12-22, tipo MAJOR, mapeador COMPRAS y gracia 90 días.

**Esperado (RF-98 CA-1, CA-19 y CU04 FA-1):** POST 201 PENDIENTE con los campos del contrato; GET con la versión nueva y auditoría CONTRATO_REGISTRADO con versión, estado, usuario y fecha.

${tabla([fila('1','POST /integracion/contratos 4.0','201; PENDIENTE; fecha_activacion nula; versión, vigencia, endpoint, anexo, mapeadores, tipo y gracia',`G036-017: HTTP ${p01?.http??'no consta'}; id ${dato(p01,'id_version_contrato_aaef')}; ${dato(p01,'estado')}; fecha_activacion ${p01?.cuerpo_respuesta?.fecha_activacion===null?'nula':'no consta'}; versión ${dato(p01,'contrato_version')}; vigencia ${dato(p01,'fecha_vigencia')}; endpoint ${dato(p01,'endpoint_asociado')}; anexo ${dato(p01,'id_mapeo_anexo_aaef')}; mapeadores ${(p01?.cuerpo_respuesta?.mapeadores??[]).join(', ')||'no consta'}; tipo ${dato(p01,'tipo_cambio')}; gracia ${dato(p01,'periodo_gracia_dias')}`,r.pruebas?.['01_registro']===true),fila('2','GET /integracion/contratos','4.0 presente',solicitud('G036-018')?'G036-018: HTTP 200; comprobación de presencia aprobada en resultado.json':'Lectura no registrada',solicitud('G036-018')?r.pruebas?.['01_registro']===true:null),fila('3','GET /integracion/auditoria','Evento nuevo CONTRATO_REGISTRADO: 4.0 PENDIENTE, usuario y fecha',solicitud('G036-019')?'G036-019: HTTP 200; aserción de auditoría aprobada. ID, usuario y fecha del evento no constan en resultado.json; la respuesta Newman está redactada.':'Lectura no registrada',solicitud('G036-019')?r.pruebas?.['01_auditoria']===true:null)])}

**Decisión de TC-M07-01: ${estado('TC-M07-01')}** por registro y comprobación de auditoría conformes según las aserciones guardadas; los datos no persistidos del evento quedan identificados como no disponibles.`,
`### TC-M07-02 — versión duplicada

**Preparación:** versión ${r.seleccion?.duplicado??'no consta'} ACTIVO elegida en vivo; cuerpo válido con anexo ${r.seleccion?.aprobado??'no consta'}, COMPRAS, MAJOR, 2027-12-22 y gracia 90.

**Esperado (RF-98 FA-1 y CA-2):** 409 VERSION_DUPLICADA y contratos iguales a la línea base.

${tabla([fila('1','POST /integracion/contratos 2.1','409 VERSION_DUPLICADA',`G036-006: ${error('G036-006')}`,r.pruebas?.['02']==='APROBADO'),fila('2','GET /integracion/contratos','Sin nueva versión ni cambios de estado','G036-007: HTTP 200; comparación con línea base aprobada',r.pruebas?.['02']==='APROBADO')])}

**Decisión de TC-M07-02: ${estado('TC-M07-02')}** porque el duplicado tuvo el código exigido y no alteró los contratos.`,
`### TC-M07-03 — anexos no aprobados

**Preparación:** id 999999 ausente según preflight; anexo QA-G036-BORRADOR creado en el RUN con id ${dato(solicitud('G036-010'),'id_mapeo_anexo_aaef')} y estado ${dato(solicitud('G036-010'),'estado')}; anexo EN_REVISION ${r.seleccion?.revision??'no consta'} elegido en vivo. Cuerpo con COMPRAS, MAJOR, 2027-12-22 y gracia 90.

**Esperado (RF-98 FA-2, CA-3 y RFC-030):** 999999 y BORRADOR rechazados con ANEXO_MAPEO_INVALIDO y sin 4.0; EN_REVISION aceptado en TEST como 4.1 PENDIENTE.

${tabla([fila('a','POST 4.0, anexo 999999','422 ANEXO_MAPEO_INVALIDO; sin 4.0',`G036-008: ${error('G036-008')}; GET G036-009 sin 4.0`,r.pruebas?.['03a']==='APROBADO'),fila('b','POST 4.0, anexo BORRADOR 5','422 ANEXO_MAPEO_INVALIDO; sin 4.0',`G036-011: ${error('G036-011')}; GET G036-012 sin 4.0`,r.pruebas?.['03b']==='APROBADO'),fila('c','POST 4.1, anexo EN_REVISION 3','201 PENDIENTE en TEST',`G036-020: HTTP ${p03?.http??'no consta'}; id ${dato(p03,'id_version_contrato_aaef')}; ${dato(p03,'estado')}; GET G036-021 HTTP 200`,r.pruebas?.['03c']===true)])}

**Decisión de TC-M07-03: ${estado('TC-M07-03')}** por los tres resultados esperados para TEST. La restricción de producción queda sin verificar.`,
`### TC-M07-04 — Mappers inválidos

**Preparación:** anexo APROBADO ${r.seleccion?.aprobado??'no consta'}; versión 4.0 aún ausente; cuerpo válido salvo Mappers [] o [MAPPER_X], con vigencia 2027-12-22, MAJOR y gracia 90.

**Esperado (RF-98 FA-3 y matriz TC-M07-04):** ambas variantes rechazadas con MAPPERS_INVALIDOS, sin crear 4.0.

${tabla([fila('a','POST 4.0, mapeadores []','MAPPERS_INVALIDOS; sin 4.0',`G036-013: ${error('G036-013')}; GET G036-014 ${solicitud('G036-014')?'sin 4.0':'no registrado'}`,solicitud('G036-013')?r.pruebas?.['04a']==='APROBADO':null),fila('b','POST 4.0, mapeadores [MAPPER_X]','MAPPERS_INVALIDOS; sin 4.0',`G036-015: ${error('G036-015')}; GET G036-016 ${solicitud('G036-016')?'sin 4.0':'no registrado'}`,solicitud('G036-015')?r.pruebas?.['04b']==='APROBADO':null)])}

**Decisión de TC-M07-04: ${estado('TC-M07-04')}** ${inc04.length?'por INC-M07-G036-01: se rechazó cada entrada y no se creó versión, pero se devolvió VAL_ENTRADA en vez del código exigido.':'según las comprobaciones disponibles; no se registra incidencia de producto para este caso.'}`,
`### TC-M07-05 — registro y acciones en pantalla

**Preparación:** Administrador QA; anexo APROBADO ${r.seleccion?.aprobado??'no consta'}, 4.2 ausente; formulario con vigencia 2027-12-22, MAJOR, COMPRAS y gracia 90. Login interceptado en Cypress.

**Esperado (RF-98 CA-19, CU04 y matriz TC-M07-05):** fila 4.2 PENDIENTE con tipo, Mappers y anexo; PENDIENTE ofrece Activar, ACTIVO Retirar con plazo; DEPRECADO e INACTIVO sin acción.

${tabla([fila('1','Cypress: frontal, login, pantalla y modal','Hitos completos',ui?`frontal ${ui.hitos?.frontal_cargado}; login interceptado ${ui.hitos?.login_interceptado}; pantalla ${ui.hitos?.pantalla_contrato}; modal ${ui.hitos?.modal_abierto}`:'Acta UI no disponible',ui?!!ui.hitos?.modal_abierto:null),fila('2','Guardar 4.2 desde formulario','POST 201 y fila PENDIENTE con MAJOR, Facturas de compra y anexo',ui?`registro enviado ${ui.hitos?.registro_enviado}; POST HTTP ${ui.http_registro}; fila visible ${ui.version_4_2_visible}; acta Cypress y captura`:'Acta UI no disponible',ui?r.pruebas?.['05_ui']===true:null),fila('3','Acciones por estado','PENDIENTE→Activar; ACTIVO 2.1→Retirar con plazo; DEPRECADO 2.0 e INACTIVO 1.0 sin acción',ui?`activar ${ui.pendiente_activar}; retirar ${ui.activo_deprecar}; deprecado sin acción ${ui.deprecado_sin_accion}; inactivo sin acción ${ui.inactivo_sin_accion}`:'Acta UI no disponible',ui?r.pruebas?.['05_ui']===true:null),fila('4','GET /integracion/contratos posterior','4.2 PENDIENTE',solicitud('G036-022')?'G036-022: HTTP 200; comprobación API de 4.2 en resultado.json':'Lectura posterior no registrada',solicitud('G036-022')?r.pruebas?.['05_api']===true:null)])}

**Decisión de TC-M07-05: ${estado('TC-M07-05')}** por comprobaciones API y UI aprobadas. Hay captura y archivo de vídeo; el acta marca video=false, por lo que no se usa como prueba de la aserción.`
  ];
  const incidencia=inc04.length?`### INC-M07-G036-01 — El registro con Mappers vacíos o inexistentes no devuelve MAPPERS_INVALIDOS

**Requisito:** RF-98 FA-3 y CA de la matriz TC-M07-04: error MAPPERS_INVALIDOS.

**Pasos para reproducir:** como Administrador, POST /integracion/contratos con cuerpo válido y mapeadores []; repetir con [MAPPER_X]; consultar GET /integracion/contratos después de cada intento.

**Esperado:** rechazo con MAPPERS_INVALIDOS y ninguna versión creada.

**Obtenido:** G036-013: ${error('G036-013')}. G036-015: ${error('G036-015')}. G036-014 y G036-016 no muestran 4.0.

**Apoyo de código leído, sin atribución causal:** src/accounting_integration/infrastructure/dto/m07_dto.py:16 define Mapper como Literal y :100 exige min_length=1; src/accounting_integration/application/use_cases/contratos/gestionar_contratos_use_case.py:79-81 contiene MAPPERS_INVALIDOS. El DTO puede validar antes del caso de uso; este código local no prueba la versión desplegada ni la causa raíz.

**Impacto y severidad:** BAJA. El registro inválido se rechaza sin crear versión, pero el cliente recibe VAL_ENTRADA en lugar del código de negocio especificado.

**Certeza:** CONFIRMADA para la discrepancia observada en TEST. **Causa raíz:** NO DETERMINADA.

**Primera atención:** Desarrollo, por discrepancia de la API pública; no atribuye causa técnica.

**Evidencias:** resultado.json solicitudes G036-013 a G036-016; newman/newman-G036.json y newman/newman-G036.html (lecturas de contraste).`: 'Ninguna incidencia funcional concluyente.';
  return `# TC-M07-G036 — ${titulo}

## Identificación

Grupo G036; casos originales agrupados ${CASOS.join(', ')}; RF-98 v1.2 (RFC-030), CU04; CA-1, CA-2, CA-3, CA-19, FA-1, FA-2 y FA-3. RUN ${c.runId}; V1 intento ${c.intento??'no consta'}; ambiente ${c.ensayo?'LOCAL_SIMULADO':'TEST'}; autorización ${c.ensayo?'LOCAL':c.referencia}; actor Administrador QA; commit TEST no consultado. Node ${process.version}; Newman versión no consta en evidencia, código ${r.newman?.codigo??'no consta'}, fallos ${r.newman?.fallos??'no consta'}; Cypress ${cypressVersion}, código ${r.cypress?.codigo??'no consta'}, pruebas ${r.cypress?.total_pruebas??0}. Informe oficial: ${r.oficial}; solicitudes ${r.solicitudes_total??'no consta'}/80.

## Resumen de veredictos

| Caso | Estado | Motivo |
|---|---|---|
${resumen}

## Detalle por caso

${detalles.join('\n\n')}

## Preflight de datos públicos

| Requisito | Esperado | Observado | Cumple |
|---|---|---|---|
${preflight||'| Sin datos | — | No consta | false |'}

## Comprobaciones API y UI

${(r.comprobaciones??[]).map(x=>`- ${x.caso} / ${x.fuente} / ${x.id}: ${x.estado}; ${x.estado==='RECHAZADO'?'código de error distinto al exigido':'aserción conforme'}; evidencia ${x.evidencia}.`).join('\n')}

## Evidencias reales

- resultado.json
- TC-M07-G036_resultado.md
- preflight.json
- contexto_operacion.json
${(r.evidencias??[]).map(x=>`- ${x}`).join('\n')}

## Incidencias de producto

${incidencia}

## Observaciones

- TC-M07-03c: en TEST se acepta el anexo EN_REVISION por RFC-030; la exigencia de anexo APROBADO en producción queda sin verificar. Sin incidencia.

## Problemas técnicos y análisis de causas

${r.problemas_tecnicos?.length?r.problemas_tecnicos.join('; '):'Ninguno en este RUN.'} El intento 1 fue técnico por la URL del frontal y se corrigió en ORD-G036-011; no afecta los veredictos de este intento.

## Cierre y rollback

DELETE HTTP ${r.cierre?.http??'no consta'}; lecturas poscierre sin cabeceras de RUN. Rollback verificado: ${r.cierre?.rollback?.verificado??false}. Se compararon IDs y estados de contratos y anexos con la línea base y la ausencia de 4.0, 4.1, 4.2 y QA-G036-BORRADOR.

## Conclusión y acciones

${CASOS.map(id=>`${id}: ${estado(id)}`).join('; ')}. ${inc04.length?'TC-M07-04 falla por el código de error de negocio, con severidad BAJA y sin versión creada. Derivar INC-M07-G036-01 a Desarrollo; reevaluar TC-M07-04 con nueva autorización cuando informen la corrección.':'Revisar las comprobaciones inconclusas o las incidencias registradas antes de solicitar una nueva evaluación.'}
`;
}
export function completarResultado(r,c){
  r.cierre.run={cierre_http:r.cierre.http??null};
  r.autorizacion_referencia=c.referencia;
  r.consume_version=r.solicitudes.some(x=>x.metodo==='POST'&&x.ruta==='/integracion/contratos');
  r.cypress??={codigo:2,total_pruebas:0};
  r.cypress.total_pruebas??=0;
  r.preflight_datos??=[];
  const pruebas={
    'TC-M07-01':[['API','registro_v4_0','01_registro'],['API','auditoria','01_auditoria']],
    'TC-M07-02':[['API','duplicado','02']],
    'TC-M07-03':[['API','anexo_inexistente','03a'],['API','anexo_borrador','03b'],['API','anexo_revision','03c']],
    'TC-M07-04':[['API','mappers_vacios','04a'],['API','mapper_invalido','04b']],
    'TC-M07-05':[['API','registro_v4_2','05_api'],['UI','tabla_acciones','05_ui']]
  };
  r.casos=Object.fromEntries(CASOS.map((caso,i)=>[caso,{estado:r.veredictos?.[String(i+1).padStart(2,'0')]??'NO_CONCLUYENTE',comprobaciones:pruebas[caso].map(([,id])=>id)}]));
  r.comprobaciones=Object.entries(pruebas).flatMap(([caso,lista])=>lista.map(([fuente,id,clave])=>({caso,fuente,id,tipo:'ASSERT',estado:r.pruebas[clave]===true||r.pruebas[clave]==='APROBADO'?'APROBADO':r.pruebas[clave]===false||r.pruebas[clave]==='RECHAZADO'?'RECHAZADO':'NO_CONCLUYENTE',evidencia:fuente==='UI'?'cypress/G036-UI-05.json':'resultado.json',clave})));
  for(const comprobacion of r.comprobaciones.filter(x=>x.estado==='RECHAZADO')){
    const {caso,clave}=comprobacion;
    const versionCreada=caso==='TC-M07-04'&&r.solicitudes.some(x=>x.metodo==='POST'&&x.ruta==='/integracion/contratos'&&x.http===201&&Array.isArray(x.cuerpo_solicitud?.mapeadores)&&((clave==='04a'&&x.cuerpo_solicitud.mapeadores.length===0)||(clave==='04b'&&x.cuerpo_solicitud.mapeadores.includes('MAPPER_X'))));
    const regla=({'01_registro':'REGISTRO_NO_CREADO','01_auditoria':'AUDITORIA_AUSENTE','02':'RECHAZO_CREO_VERSION','03a':'RECHAZO_CREO_VERSION','03b':'RECHAZO_CREO_VERSION','03c':'REVISION_RECHAZADA','04a':versionCreada?'RECHAZO_CREO_VERSION':'CODIGO_DISTINTO_SIN_CREACION','04b':versionCreada?'RECHAZO_CREO_VERSION':'CODIGO_DISTINTO_SIN_CREACION','05_api':'UI_VERSION_AUSENTE','05_ui':'UI_ACCIONES_INCORRECTAS'})[clave];
    r.incidencias.push({caso,regla,severidad:severidadRegla(regla),certeza:c.ensayo?'PROBABLE':'CONFIRMADA',equipo_inicial:'Desarrollo',fundamento:'Discrepancia observada en API/UI pública; causa raíz no determinada'});
  }
  r.comprobaciones.forEach(x=>delete x.clave);
  r.oficial=r.oficial&&r.cypress.total_pruebas>0&&r.evidencias.some(x=>x.startsWith('cypress/screenshots/')&&x.endsWith('.png'))&&r.comprobaciones.every(x=>['APROBADO','RECHAZADO'].includes(x.estado));
}
export async function principal(argv,{proceso=process.env,archivo=path.join(ROOT,'.env.qa'),prueba=false,fetcher=fetch,dobles={}}={}){
  const c=contexto(argv,prueba),e=leerEnv(proceso,archivo),p=preflight(c,e);
  fs.writeFileSync(path.join(c.dir,'preflight.json'),JSON.stringify(sanitize(p),null,2));
  if(!p.ok)return{preflight:p,codigo:2};
  e.SIGAB_API_TEST_BASE=String(e.SIGAB_API_TEST_BASE).replace(/\/+$/,'');
  e.SIGAB_FRONT_TEST_BASE=String(e.SIGAB_FRONT_TEST_BASE??FRONT).replace(/\/+$/,'');
  const resultado=await ejecutar(c,e,fetcher,dobles);
  return{preflight:p,codigo:0,resultado};
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){try{
  if(process.argv.includes('--capacidades'))console.log(JSON.stringify(CAPACIDADES));
  else if(process.argv.includes('--comprobar'))process.exitCode=comprobar();
  else{const prueba=process.env.NODE_ENV==='test'&&process.argv.includes('--prueba-cli-local');const archivo=prueba?path.resolve(process.env.G036_PRUEBA_ENV_FILE??'.'):path.join(ROOT,'.env.qa');if(prueba&&!archivo.startsWith(path.resolve(os.tmpdir())+path.sep))throw Error('ENV_PRUEBA_FUERA_TEMPORAL');const z=await principal(process.argv.slice(2),{archivo,prueba});if(z.codigo===2){console.error(`PREFLIGHT_${z.preflight.faltan.join('_')}`);process.exitCode=2;}else console.log(JSON.stringify({grupo:'G036',oficial:z.resultado.oficial,casos:z.resultado.casos,solicitudes:z.resultado.solicitudes_total}));}
}catch(err){console.error(seguro(err.message));process.exitCode=2;}}
