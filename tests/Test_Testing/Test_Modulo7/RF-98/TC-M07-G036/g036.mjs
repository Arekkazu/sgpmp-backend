import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import {spawn} from 'node:child_process';
import os from 'node:os';
import {sanearError} from './lib/privacidad.cjs';
import {contrato,validarLecturas,validarError,validarSolicitud,esquema} from './lib/contrato.mjs';
import {CASOS,LIMITE,precondiciones,porVersion,estados,iguales,cuerpo,fechaFutura,clasificarRechazo,evaluarRegistro,evaluarAuditoria,clasificarUI,veredictos,severidadRegla} from './lib/g036_core.mjs';
const DIR=path.dirname(fileURLToPath(import.meta.url));
const ROOT=path.resolve(DIR,'../../../../..');
const API='https://www.api.inmero.co/api-sgpmp-test';
const FRONT='https://api.inmero.co/sigab-test';
export const CAPACIDADES={contrato:'sigab-qa-ejecutor/1',grupo:'G036',casos:CASOS,operaciones:['reevaluar','reintentar'],versiones:{min:2,max:2},comprobaciones_obligatorias:{'TC-M07-01':{API:['registro_version_libre','auditoria']},'TC-M07-02':{API:['duplicado']},'TC-M07-03':{API:['anexo_inexistente','anexo_borrador','anexo_revision']},'TC-M07-04':{API:['mappers_vacios','mapper_invalido']},'TC-M07-05':{API:['registro_ui_version_libre'],UI:['tabla_acciones']}},limite:LIMITE};
const RUN=/^RUN-G036-V2-\d{8}-\d{6}$/;
const INFORME='TC-M07-G036_reevaluacion_V2.md';
const sha=p=>createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const guardar=(p,x)=>fs.writeFileSync(p,JSON.stringify(sanitize(x),null,2));
const seguro=x=>sanearError(x);
export const sanitize=x=>Array.isArray(x)?x.map(sanitize):x&&typeof x==='object'?Object.fromEntries(Object.entries(x).filter(([k])=>!/nombre_usuario|correo_usuario|nombre_cliente/i.test(k)).map(([k,v])=>[k,/correo_electronico|correo|email/i.test(k)?'[CORREO]':/token|secret|password|cookie|authorization|sha256_documento|contrasena|contraseña|clave|access_key|refresh/i.test(k)?'[RESERVADO]':sanitize(v)])):typeof x==='string'?seguro(x):x;
function lanzarCypress(input){return new Promise(resolve=>{let hijo;try{hijo=spawn(process.execPath,[path.join(DIR,'pruebas/cypress_hijo.mjs')],{cwd:DIR,stdio:['pipe','pipe','pipe'],windowsHide:true});}catch(error){resolve({status:null,error,stdout:''});return;}let stdout='',error=null;const timer=setTimeout(()=>{error??=Object.assign(new Error('CYPRESS_TIMEOUT'),{code:'ETIMEDOUT'});hijo.kill();},240000);hijo.stdout.on('data',x=>stdout+=x);hijo.stderr.on('data',()=>{});hijo.on('error',e=>{error=e;});hijo.on('close',status=>{clearTimeout(timer);resolve({status,error,stdout});});hijo.stdin.on('error',()=>{});hijo.stdin.end(JSON.stringify(input));});}
export function comprobar(){const archivos=['g036.mjs','lib/contrato.mjs','lib/g036_core.mjs','pruebas/contrato_g036.json','pruebas/fixture_g036.json','G036.postman_collection.json','g036.cy.js','g036.cypress.config.cjs','pruebas/newman_hijo.mjs','pruebas/g036_local.test.mjs','pruebas/g036_dto.test.py','pruebas/verificar.mjs','pruebas/simulador_g036.mjs','pruebas/escenarios_g036.mjs','pruebas/escenarios_g036.json','pruebas/cypress_hijo.mjs','lib/intercepcion.cjs','lib/privacidad.cjs','pruebas/contrato_cruzado.test.mjs','README.md'];const faltan=archivos.filter(x=>!fs.existsSync(path.join(DIR,x)));const col=JSON.parse(fs.readFileSync(path.join(DIR,'G036.postman_collection.json'),'utf8'));const ok=!faltan.length&&col.item.length>0&&contrato.rutas.every(x=>x.cita?.startsWith('src/'))&&!fs.existsSync(path.join(DIR,INFORME));console.log(JSON.stringify({grupo:'G036',ok,faltan,coleccion:col.item.length,sha256:Object.fromEntries(archivos.filter(x=>fs.existsSync(path.join(DIR,x))).map(x=>[x,sha(path.join(DIR,x))]))}));return ok?0:2;}
export function leerEnv(proceso=process.env,archivo=path.join(ROOT,'.env.qa')){const e={};if(proceso.QA_AUTORIZADO==='SI'&&fs.existsSync(archivo))for(const line of fs.readFileSync(archivo,'utf8').split(/\r?\n/)){const m=line.match(/^\s*([A-Z][A-Z0-9_]*)\s*=(.*)$/);if(m)e[m[1]]=m[2].trim().replace(/^(['"])(.*)\1$/,'$2');}Object.assign(e,proceso);e.QA_AUTORIZADO=proceso.QA_AUTORIZADO;return e;}
const loopback=x=>{try{const u=new URL(x);return u.protocol==='http:'&&['127.0.0.1','localhost'].includes(u.hostname)&&!!u.port&&!u.pathname.match(/\/\/$/);}catch{return false;}};
export function contexto(args,prueba=false){
  const arg=k=>args.includes(k)?args[args.indexOf(k)+1]:null;
  const operacion=arg('--operacion'),version=Number(arg('--version')),intento=Number(arg('--intento'));
  const runId=arg('--run-id'),referencia=arg('--autorizacion'),archivo=arg('--contexto');
  if(!CAPACIDADES.operaciones.includes(operacion)||version!==2||!Number.isInteger(intento)||intento<1||!referencia||!RUN.test(runId??''))throw Error('CONTEXTO_INCOMPLETO');
  const dir=prueba?path.dirname(path.resolve(archivo??'.')):path.join(DIR,'EvaluacionV2','Resultados',runId);
  if(prueba&&(path.basename(dir)!==runId||!dir.startsWith(path.resolve(os.tmpdir())+path.sep)))throw Error('PRUEBA_FUERA_TEMPORAL');
  if(!archivo||path.resolve(archivo)!==path.join(dir,'contexto_operacion.json'))throw Error('CONTEXTO_FUERA_RUN');
  const dato=JSON.parse(fs.readFileSync(archivo,'utf8'));
  if(dato.grupo!=='G036'||dato.run_id!==runId||dato.version!==version||dato.intento!==intento||dato.operacion!==operacion.toUpperCase()||dato.referencia!==referencia||JSON.stringify(dato.casos)!==JSON.stringify(CASOS))throw Error('CONTEXTO_INCOHERENTE');
  return{dir,runId,version,intento,operacion,referencia,ensayo:prueba,estricto:prueba};
}
export function dirRun(c){const dir=path.resolve(c.dir);if(!c.ensayo&&dir!==path.join(DIR,'EvaluacionV2','Resultados',c.runId))throw Error('CONTEXTO_FUERA_RUN');return dir;}
export function preflight(c,e){const faltan=[];for(const k of ['QA_ADMIN_EMAIL','QA_ADMIN_PASSWORD','QA_SANDBOX_SECRET','SIGAB_API_TEST_BASE'])if(!String(e[k]??'').trim())faltan.push(k);if(e.QA_AUTORIZADO!=='SI')faltan.push('QA_AUTORIZADO');const api=String(e.SIGAB_API_TEST_BASE??'').replace(/\/+$/,'');const front=String(e.SIGAB_FRONT_TEST_BASE??FRONT).replace(/\/+$/,'');if(c.ensayo?!loopback(api):api!==API)faltan.push('API_NO_CANONICA');if(c.ensayo?!loopback(front):front!==FRONT)faltan.push('FRONT_NO_CANONICO');if(!RUN.test(c.runId??'')||c.version!==2)faltan.push('RUN_ID');if(!c.referencia)faltan.push('AUTORIZACION');return{ok:!faltan.length,faltan,grupo:'G036',run_id:c.runId,version:2,referencia:c.referencia,presupuesto:LIMITE};}
const hoy=()=>new Intl.DateTimeFormat('en-CA',{timeZone:'America/Bogota',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
export function decisionLogin({runAbierto=false,loginIntentado=false,loginFallido=false}={}){if(loginFallido)return 'LOGIN_FALLIDO_SIN_REINTENTO';if(runAbierto)return 'LOGIN_DENTRO_RUN';if(loginIntentado)return 'SEGUNDO_LOGIN';return 'PERMITIDO';}
export async function ejecutar(c,e,fetcher=fetch,ensayoLocal={}){const pf=preflight(c,e);if(!pf.ok)throw Error(`PREFLIGHT_${pf.faltan.join('_')}`);if(!c.ensayo&&Object.keys(ensayoLocal).length)throw Error('DOBLES_SOLO_ENSAYO');const dir=dirRun(c);if(c.ensayo&&(path.basename(dir)!==c.runId||!dir.startsWith(path.resolve(os.tmpdir())+path.sep)))throw Error('ENSAYO_FUERA_TEMPORAL');if(!fs.existsSync(dir))throw Error('RUN_NO_PRECREADO');if(fs.existsSync(path.join(dir,'resultado.json'))||fs.existsSync(path.join(dir,INFORME)))throw Error('RUN_EXISTENTE');const r={grupo:'G036',run_id:c.runId,version:2,casos:CASOS,autorizacion:c.referencia,solicitudes:[],pruebas:{},seleccion:{},incidencias:[],oficial:false,cierre:{rollback:{verificado:false,motivo:'No ejecutado'}},evidencias:[],problemas_tecnicos:[]};const deadline=Date.now()+LIMITE.duracion_segundos*1000;let token=null,serial=false,cerrado=false,runAbierto=false,loginIntentado=false,base=null,anexos=null;const apiBase=String(e.SIGAB_API_TEST_BASE).replace(/\/+$/,'');
  async function pedir(metodo,ruta,body,autenticado=true){if(serial)throw Error('PETICION_CONCURRENTE');if(r.solicitudes.length+(r.newman?.solicitudes??0)>=80||Date.now()>deadline)throw Error('PRESUPUESTO_AGOTADO');if(!esquema(metodo,ruta)||ruta==='/sesiones/refresh')throw Error(`RUTA_FUERA_CONTRATO_${metodo}_${ruta}`);if(body!==undefined&&!validarSolicitud(metodo,ruta,body))throw Error('SOLICITUD_FUERA_CONTRATO');const login=metodo==='POST'&&ruta==='/sesiones/';if(login){const d=decisionLogin({runAbierto,loginIntentado});if(d!=='PERMITIDO')throw Error(d);loginIntentado=true;}else if(!token)throw Error('LOGIN_REQUERIDO');serial=true;const row={id:`G036-${String(r.solicitudes.length+1).padStart(3,'0')}`,metodo,ruta:ruta.split('?')[0],http:null,actor:'administrador',...(login?{momento:'ANTES_DEL_RUN',efecto_persistente:'último acceso, auditoría de sesión y notificación de login con escritura independiente'}:{})};if(metodo==='POST')row.cuerpo_solicitud=sanitize(body);r.solicitudes.push(row);try{const headers={...(autenticado?{Authorization:`Bearer ${token}`}:{}) ,...(login||cerrado?{}:{'X-Test-Run-Id':c.runId,'X-Sandbox-Secret':e.QA_SANDBOX_SECRET}),...(body===undefined?{}:{'Content-Type':'application/json'})};if(!login&&!cerrado)runAbierto=true;const z=await fetcher(apiBase+ruta,{method:metodo,headers,redirect:'manual',...(body===undefined?{}:{body:JSON.stringify(body)}),signal:AbortSignal.timeout(120000)});row.http=z.status;const raw=await z.json().catch(()=>null);if(metodo==='POST')row.cuerpo_respuesta=sanitize(raw);row.eco=z.headers.get('x-test-run-id')===c.runId;if(!login&&!cerrado&&(!row.eco||z.status>=500))throw Error(`SANDBOX_O_INFRA_${row.id}_${z.status}`);let data=raw;if(z.status>=200&&z.status<300)data=validarLecturas(raw,metodo,ruta,{estricto:!!c.estricto});if(z.status>=400){row.error=raw?.error_code??null;row.cuerpo_error=sanitize(raw);row.error_estandar=validarError(raw);}return{http:z.status,data,raw};}finally{serial=false;}}
  const get=async ruta=>{const z=await pedir('GET',ruta);if(z.http!==200)throw Error(`LECTURA_${ruta}_${z.http}`);return z.data;};
  const listar=async ruta=>{const v=await get(ruta);if(!Array.isArray(v))throw Error('LISTA_INVALIDA');return v;};
  const auditar=async()=>{let pagina=1,items=[],total=0;do{const x=await get(`/integracion/auditoria?tipo_evento=CONTRATO_REGISTRADO&desde=${hoy()}&pagina=${pagina}&tamano=100`);items.push(...x.items);total=x.total;if(++pagina>20||items.length>total)throw Error('AUDITORIA_PAGINACION');}while(items.length<total);return items;};
  const verificar=async(z,esperado,baseline,version)=>clasificarRechazo(z,esperado,baseline,await listar('/integracion/contratos'),version);
  try{
    const sesion=await pedir('POST','/sesiones/',{correo_electronico:e.QA_ADMIN_EMAIL,contrasena:e.QA_ADMIN_PASSWORD},false);if(sesion.http!==200)throw Error('LOGIN_FALLIDO');token=sesion.data.token;fs.mkdirSync(dir,{recursive:true});
    const permisos=(await get('/sesiones/me/permisos')).permisos;anexos=await listar('/integracion/anexos');base=await listar('/integracion/contratos');const auditBase=await auditar();const p=precondiciones(anexos,base,permisos);r.preflight_datos=p.preflight_datos;const cupo=base.filter(x=>['ACTIVO','DEPRECADO'].includes(x.estado)).length;r.preflight_datos.push({requisito:'CUPO_VIGENTES_OBSERVADO',observado:cupo,bloqueante:false});r.seleccion={aprobado:p.aprobado?.id_mapeo_anexo_aaef??null,revision:p.revision?.id_mapeo_anexo_aaef??null,borrador:p.borrador?.id_mapeo_anexo_aaef??null,duplicado:p.existente?.contrato_version??null,versiones:p.libres,criterio:'versiones libres desde 6.0; anexos por mayor id del estado; duplicado ACTIVO'};if(p.faltan.length){r.bloqueos=p.faltan;r.veredictos=veredictos({preflight:true});return r;}
    const fecha=fechaFutura(),baseEstado=estados(base),anexo=p.aprobado.id_mapeo_anexo_aaef,[v01,v03,v05]=p.libres;
    let borrador=p.borrador;
    if(!borrador){const marca=c.runId.replaceAll('-','').slice(-20);const alta=await pedir('POST','/integracion/anexos',{codigo_anexo:`QA-G036-${marca}`,version_anexo:v01,ruta_documento:`docs/qa/G036-${marca}.md`,sha256_documento:createHash('sha256').update(`G036-${marca}`).digest('hex')});if(alta.http===201&&alta.data?.estado==='BORRADOR')borrador=alta.data;}
    if(!borrador){r.bloqueos=['ANEXO_BORRADOR'];r.preflight_datos.push({requisito:'ANEXO_BORRADOR',esperado:'presente o creable',observado:null,bloqueante:true,cumple:false});r.veredictos=veredictos({preflight:true});return r;}
    r.seleccion.borrador=borrador.id_mapeo_anexo_aaef;r.preflight_datos.push({requisito:'ANEXO_BORRADOR',esperado:'presente o creable',observado:borrador.id_mapeo_anexo_aaef,bloqueante:true,cumple:true});
    const inexistente=Math.max(...anexos.map(x=>x.id_mapeo_anexo_aaef),borrador.id_mapeo_anexo_aaef)+1;r.seleccion.inexistente=inexistente;
    const z02=await pedir('POST','/integracion/contratos',cuerpo(p.existente.contrato_version,anexo,fecha));r.pruebas['02']=await verificar(z02,'VERSION_DUPLICADA',baseEstado,p.existente.contrato_version);
    const z03a=await pedir('POST','/integracion/contratos',cuerpo(v01,inexistente,fecha));r.pruebas['03a']=await verificar(z03a,'ANEXO_MAPEO_INVALIDO',baseEstado,v01);
    const z03b=await pedir('POST','/integracion/contratos',cuerpo(v01,borrador.id_mapeo_anexo_aaef,fecha));r.pruebas['03b']=await verificar(z03b,'ANEXO_MAPEO_INVALIDO',baseEstado,v01);
    const z04a=await pedir('POST','/integracion/contratos',cuerpo(v01,anexo,fecha,[]));r.pruebas['04a']=await verificar(z04a,'MAPPERS_INVALIDOS',baseEstado,v01);const z04b=await pedir('POST','/integracion/contratos',cuerpo(v01,anexo,fecha,['MAPPER_X']));r.pruebas['04b']=await verificar(z04b,'MAPPERS_INVALIDOS',baseEstado,v01);
    const body01=cuerpo(v01,anexo,fecha),z01=await pedir('POST','/integracion/contratos',body01),despues01=await listar('/integracion/contratos'),audit01=await auditar();const usuario=Number(JSON.parse(Buffer.from(token.split('.')[1],'base64url').toString('utf8')).sub);r.pruebas['01_registro']=evaluarRegistro(z01,despues01,body01);const evento01=audit01.find(x=>!auditBase.some(a=>a.id_evento_integracion===x.id_evento_integracion)&&x.tipo_evento==='CONTRATO_REGISTRADO'&&x.version_contrato===v01);r.auditoria=[{comprobacion:'01',id:evento01?.id_evento_integracion??null,tipo:evento01?.tipo_evento??null,version:evento01?.version_contrato??null,estado:evento01?.json_detalle?.estado??null,fecha:evento01?.fecha_evento??null,actor:'administrador'}];r.pruebas['01_auditoria']=evaluarAuditoria(auditBase,audit01,v01,usuario);r.pruebas['01']=r.pruebas['01_registro']&&r.pruebas['01_auditoria'];
    if(p.revision){const body03c=cuerpo(v03,p.revision.id_mapeo_anexo_aaef,fecha),z03c=await pedir('POST','/integracion/contratos',body03c);r.pruebas['03c']=z03c.http===201?evaluarRegistro(z03c,await listar('/integracion/contratos'),body03c):z03c.data?.error_code==='ANEXO_MAPEO_INVALIDO'?'RECHAZADO':'NO_CONCLUYENTE';}else {r.pruebas['03c']='NO_CONCLUYENTE';r.bloqueos=['ANEXO_EN_REVISION: solo variante 03c sin dato; los otros casos continúan'];}
    const newmanInput={coleccion:JSON.parse(fs.readFileSync(path.join(DIR,'G036.postman_collection.json'),'utf8')),environment:{values:[['base_url',apiBase],['run_id',c.runId],['sandbox_secret',e.QA_SANDBOX_SECRET],['admin_token',token]].map(([key,value])=>({key,value,enabled:true}))},salida:path.join(dir,'newman')};try{r.newman=await(ensayoLocal.newman?ensayoLocal.newman(newmanInput): (await import('./pruebas/newman_hijo.mjs')).ejecutar(newmanInput));r.evidencias.push(...['newman/newman-G036.json','newman/newman-G036.html'].filter(x=>fs.existsSync(path.join(dir,x))));}catch(err){r.newman={codigo:2,error:seguro(err.message)};}
    const cypDir=path.join(dir,'cypress');fs.mkdirSync(cypDir,{recursive:true});const versiones=Object.fromEntries(['ACTIVO','DEPRECADO','INACTIVO'].map(estado=>[estado,base.filter(x=>x.estado===estado).sort((a,b)=>b.id_version_contrato_aaef-a.id_version_contrato_aaef)[0]?.contrato_version??null]));const childInput={api:c.ensayo?apiBase:API,front:c.ensayo?e.SIGAB_FRONT_TEST_BASE:FRONT,dir:cypDir,runId:c.runId,token,secret:e.QA_SANDBOX_SECRET,fecha,anexoId:anexo,anexoCodigo:p.aprobado.codigo_anexo,versionLibre:v05,versiones,localSmoke:!!c.ensayo};const cr=ensayoLocal.cypress?null:await(ensayoLocal.lanzarCypress??lanzarCypress)(childInput);let child=null;if(ensayoLocal.cypress)child=await ensayoLocal.cypress(childInput);else try{child=JSON.parse(cr.stdout);}catch{}r.cypress={codigo:child?.codigo??cr?.status??2,error:cr?.error?.code??null,total_pruebas:child?.totalTests??0};if(fs.existsSync(path.join(cypDir,'G036-cypress.json')))r.evidencias.push('cypress/G036-cypress.json');if(fs.existsSync(path.join(cypDir,'G036-cypress-salida.log')))r.evidencias.push('cypress/G036-cypress-salida.log');const actaPath=path.join(cypDir,'G036-UI-05.json');if(child?.acta||fs.existsSync(actaPath)){const acta=sanitize(child?.acta??JSON.parse(fs.readFileSync(actaPath,'utf8')));acta.error??=sanitize(child?.error??null);fs.writeFileSync(actaPath,JSON.stringify(sanitize(acta),null,2));const evaluacion=clasificarUI(acta,r.cypress.codigo);r.pruebas['05_ui']=evaluacion.ui;r.pruebas['05']=evaluacion.ui;r.cypress.fallo_producto=evaluacion.ui===false&&!evaluacion.problema;r.registro_ui_enviado=acta.hitos?.registro_enviado===true;r.cypress.solicitudes=acta.peticiones?.length??0;r.ui={activar_visible:acta.activar_visible,activar_deshabilitado:acta.activar_deshabilitado,motivo_servidor_visible:acta.motivo_servidor_visible,activo_deprecar:acta.activo_deprecar,deprecado_sin_accion:acta.deprecado_sin_accion,inactivo_sin_accion:acta.inactivo_sin_accion};if(evaluacion.problema)r.problemas_tecnicos.push(seguro(evaluacion.problema));r.evidencias.push('cypress/G036-UI-05.json');}else {r.pruebas['05_ui']='NO_CONCLUYENTE';r.pruebas['05']='NO_CONCLUYENTE';r.problemas_tecnicos.push(seguro(child?.error||cr?.error?.message||'Cypress no genero acta UI'));}const capturas=path.join(cypDir,'screenshots');if(fs.existsSync(capturas)){const recorrer=(d,rel)=>{for(const x of fs.readdirSync(d,{withFileTypes:true})){const q=path.join(d,x.name),n=rel+'/'+x.name;if(x.isDirectory())recorrer(q,n);else if(n.endsWith('.png'))r.evidencias.push(n);}};recorrer(capturas,'cypress/screenshots');}
    if(r.registro_ui_enviado){const uiContrato=await listar('/integracion/contratos');r.pruebas['05_api']=porVersion(uiContrato,v05)?.estado==='PENDIENTE';}
    else r.pruebas['05_api']='NO_CONCLUYENTE';
    r.pruebas['05']=r.pruebas['05_ui']==='NO_CONCLUYENTE'?'NO_CONCLUYENTE':r.pruebas['05_ui']&&r.pruebas['05_api'];r.veredictos=veredictos({r01:r.pruebas['01'],r02:r.pruebas['02'],r03a:r.pruebas['03a'],r03b:r.pruebas['03b'],r03c:r.pruebas['03c'],sinRevision:!p.revision,r04a:r.pruebas['04a'],r04b:r.pruebas['04b'],r05:r.pruebas['05']});r.estado='PRUEBAS_COMPLETADAS';return r;
  }catch(err){r.problemas_tecnicos.push(seguro(err.message));r.veredictos??=veredictos({preflight:true});return r;}finally{if(runAbierto){try{const z=await fetcher(`${apiBase}/test-control/runs/${c.runId}`,{method:'DELETE',headers:{'X-Sandbox-Secret':e.QA_SANDBOX_SECRET},signal:AbortSignal.timeout(120000)});r.cierre.http=z.status;cerrado=z.status===200;if(cerrado&&base&&anexos){const posteriorC=await listar('/integracion/contratos'),posteriorA=await listar('/integracion/anexos');r.cierre.rollback={verificado:verificarRollback(base,posteriorC,anexos,posteriorA),motivo:'Lecturas públicas poscierre sin cabeceras de RUN'};}else r.cierre.rollback={verificado:false,motivo:cerrado?'Línea base incompleta':'DELETE no confirmó 200'};}catch(err){r.cierre.rollback={verificado:false,motivo:seguro(err.message)};}}r.solicitudes=sanitize(r.solicitudes);r.oficial=esOficial(r,deadline);r.solicitudes_total=r.solicitudes.length+(r.newman?.solicitudes??0)+(r.cypress?.solicitudes??0);completarResultado(r,c);guardar(path.join(dir,'resultado.json'),r);fs.writeFileSync(path.join(dir,INFORME),informe(c,sanitize(r)));}
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
  return mismosIdsYEstados(base,posteriorC,'id_version_contrato_aaef')&&mismosIdsYEstados(anexos,posteriorA,'id_mapeo_anexo_aaef');
}
export function esOficial(r,deadline){return Object.values(r.veredictos??{}).length===5&&Object.values(r.veredictos).every(v=>['APROBADO','RECHAZADO'].includes(v))&&r.newman?.codigo===0&&r.newman?.fallos===0&&r.newman?.reportes===true&&(r.cypress?.codigo===0||r.cypress?.fallo_producto===true)&&r.cierre.rollback.verificado&&r.solicitudes.length+(r.newman?.solicitudes??0)+(r.cypress?.solicitudes??0)<=80&&Date.now()<=deadline;}
export function informe(c,r){
  const versiones=r.seleccion?.versiones??[],posts=r.solicitudes?.filter(x=>x.metodo==='POST'&&x.ruta==='/integracion/contratos')??[];
  const post=fn=>posts.find(fn),respuesta=x=>x?'HTTP '+x.http+', '+(x.error??x.cuerpo_respuesta?.estado??'sin código'):'sin petición';
  const p01=post(x=>x.cuerpo_solicitud?.contrato_version===versiones[0]&&x.http===201);
  const p02=post(x=>x.cuerpo_solicitud?.contrato_version===r.seleccion?.duplicado&&x.http>=400);
  const p03a=post(x=>x.cuerpo_solicitud?.id_mapeo_anexo_aaef===r.seleccion?.inexistente);
  const p03b=post(x=>x.cuerpo_solicitud?.id_mapeo_anexo_aaef===r.seleccion?.borrador&&x.http>=400);
  const p03c=post(x=>x.cuerpo_solicitud?.contrato_version===versiones[1]);
  const p04a=post(x=>Array.isArray(x.cuerpo_solicitud?.mapeadores)&&x.cuerpo_solicitud.mapeadores.length===0);
  const p04b=post(x=>x.cuerpo_solicitud?.mapeadores?.includes('MAPPER_X'));
  const lineas=[
    '# TC-M07-G036 - reevaluación V2',
    '',
    '## Identificación',
    '',
    'Grupo G036; casos TC-M07-01 a TC-M07-05; RF-98 v1.2; RUN '+c.runId+'; ambiente TEST; autorización '+c.referencia+'.',
    'Código local informado: backend 5baa6e1f, 20b5f701, 756a04d9; frontend b42b421d. El despliegue no se verificó.',
    'Herramientas: Newman código '+(r.newman?.codigo??'sin ejecución')+'; Cypress código '+(r.cypress?.codigo??'sin ejecución')+', pruebas '+(r.cypress?.total_pruebas??0)+'.',
    '',
    '## Datos y oráculos',
    '',
    'Versiones libres elegidas en vivo: '+(r.seleccion?.versiones?.join(', ')||'sin selección')+'. Duplicada ACTIVO: '+(r.seleccion?.duplicado??'sin dato')+'. Anexos APROBADO '+(r.seleccion?.aprobado??'sin dato')+', BORRADOR '+(r.seleccion?.borrador??'sin dato')+', EN_REVISION '+(r.seleccion?.revision??'sin dato')+'.',
    'Fuente de esperados: matriz TC-M07-G036, RF-98 v1.2 FA-1 a FA-3, CA-1, CA-3, CA-19, CA-29 y RFC-030.',
    '',
    '| Caso | Esperado | Observado | Estado |',
    '| --- | --- | --- | --- |'
  ];
  const esperado=[
    '201 PENDIENTE con campos completos; evento CONTRATO_REGISTRADO con versión, estado, usuario y fecha',
    'VERSION_DUPLICADA; ninguna alta ni transición',
    'Inexistente y BORRADOR: ANEXO_MAPEO_INVALIDO sin alta; EN_REVISION: 201 PENDIENTE en TEST',
    'Ambas variantes: HTTP 400/422 MAPPERS_INVALIDOS sin alta',
    'Registro UI PENDIENTE; Activar visible y estado acorde con motivo_no_activable del servidor; ACTIVO Retirar con plazo; DEPRECADO e INACTIVO sin acciones'
  ];
  for(let i=0;i<CASOS.length;i++){
    const caso=CASOS[i],n=String(i+1).padStart(2,'0');
    const obs=i===0?respuesta(p01)+', versión '+(p01?.cuerpo_respuesta?.contrato_version??'ausente')+', vigencia '+(p01?.cuerpo_respuesta?.fecha_vigencia??'ausente')+', anexo '+(p01?.cuerpo_respuesta?.id_mapeo_anexo_aaef??'ausente')+', mapeadores '+(p01?.cuerpo_respuesta?.mapeadores?.join(',')??'ausentes')+', tipo '+(p01?.cuerpo_respuesta?.tipo_cambio??'ausente')+', gracia '+(p01?.cuerpo_respuesta?.periodo_gracia_dias??'ausente')+', endpoint '+(p01?.cuerpo_respuesta?.endpoint_asociado??'ausente')+', auditoría '+r.pruebas?.['01_auditoria']+', evento '+(r.auditoria?.[0]?.id??'ausente'):
      i===1?respuesta(p02)+', duplicado '+r.pruebas?.['02']:
      i===2?'inexistente '+respuesta(p03a)+' / '+r.pruebas?.['03a']+', borrador '+respuesta(p03b)+' / '+r.pruebas?.['03b']+', revisión '+respuesta(p03c)+' / '+r.pruebas?.['03c']:
      i===3?'vacíos '+respuesta(p04a)+' / '+r.pruebas?.['04a']+', fuera de catálogo '+respuesta(p04b)+' / '+r.pruebas?.['04b']:
      'versi?n '+(versiones[2]??'sin dato')+', UI '+r.pruebas?.['05_ui']+', API '+r.pruebas?.['05_api']+', Cypress '+(r.cypress?.total_pruebas??0)+', Activar visible '+(r.ui?.activar_visible??'sin dato')+', deshabilitado '+(r.ui?.activar_deshabilitado??'sin dato')+', motivo servidor '+(r.ui?.motivo_servidor_visible??'sin dato')+', ACTIVO Retirar '+(r.ui?.activo_deprecar??'sin dato')+', DEPRECADO sin acci?n '+(r.ui?.deprecado_sin_accion??'sin dato')+', INACTIVO sin acci?n '+(r.ui?.inactivo_sin_accion??'sin dato');
    lineas.push('| '+caso+' | '+esperado[i]+' | '+obs+' | '+(r.veredictos?.[n]??'NO_CONCLUYENTE')+' |');
  }
  lineas.push('','## Comprobaciones API y UI','');
  for(const x of r.comprobaciones??[])lineas.push('- '+x.caso+' '+x.fuente+'/'+x.id+': '+x.estado+'; '+x.evidencia+'.');
  lineas.push('','## Auditoría comparada y privacidad','');
  for(const x of r.auditoria??[])lineas.push('- '+(x.id??'sin evento')+', '+(x.tipo??'sin tipo')+', versión '+(x.version??'sin versión')+', '+(x.estado??'sin estado')+', fecha '+(x.fecha??'sin fecha')+', actor '+x.actor+'.');
  lineas.push('Se omiten nombres y correos personales de auditoría.','', '## Evidencias reales','');
  for(const x of r.evidencias??[])lineas.push('- '+x);
  if(!r.evidencias?.length)lineas.push('- Ninguna generada.');
  lineas.push('','## Incidencias de producto','');
  for(const x of r.incidencias??[])lineas.push('- '+x.caso+': '+x.regla+', '+x.severidad+', certeza '+x.certeza+', atención inicial '+x.equipo_inicial+'. '+x.fundamento);
  if(!r.incidencias?.length)lineas.push('- Ninguna confirmada.');
  lineas.push('La causa raíz no se atribuye sin evidencia.','', '## Incidencias técnicas y bloqueos','');
  for(const x of r.problemas_tecnicos??[])lineas.push('- '+x);
  for(const x of r.bloqueos??[])lineas.push('- Preflight: '+x+'; sin dato indispensable no puede comprobarse el producto.');
  if(!r.problemas_tecnicos?.length&&!r.bloqueos?.length)lineas.push('- Ninguno.');
  lineas.push('','## Cierre, rollback y acciones','');
  lineas.push('DELETE HTTP '+(r.cierre?.http??'no consta')+'; rollback '+(r.cierre?.rollback?.verificado===true?'verificado':'no verificado')+' ('+(r.cierre?.rollback?.motivo??'sin motivo')+'). Consumo de versión: '+(r.consume_version===true)+'.');
  lineas.push('Veredictos: '+CASOS.map((x,i)=>x+' '+(r.veredictos?.[String(i+1).padStart(2,'0')]??'NO_CONCLUYENTE')).join('; ')+'. Revisar incidencias y comprobaciones no concluyentes antes de otra ejecución.');
  return lineas.join('\n')+'\n';
}
export function completarResultado(r,c){
  r.cierre.run={cierre_http:r.cierre.http??null};
  r.autorizacion_referencia=c.referencia;
  r.consume_version=r.solicitudes.some(x=>x.metodo==='POST'&&x.ruta!=='/sesiones/')||r.registro_ui_enviado===true;
  r.cypress??={codigo:2,total_pruebas:0};
  r.cypress.total_pruebas??=0;
  r.preflight_datos??=[];
  const pruebas={
    'TC-M07-01':[['API','registro_version_libre','01_registro'],['API','auditoria','01_auditoria']],
    'TC-M07-02':[['API','duplicado','02']],
    'TC-M07-03':[['API','anexo_inexistente','03a'],['API','anexo_borrador','03b'],['API','anexo_revision','03c']],
    'TC-M07-04':[['API','mappers_vacios','04a'],['API','mapper_invalido','04b']],
    'TC-M07-05':[['API','registro_ui_version_libre','05_api'],['UI','tabla_acciones','05_ui']]
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
