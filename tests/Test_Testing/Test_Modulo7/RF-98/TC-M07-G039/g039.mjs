import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import {spawn} from 'node:child_process';
import {esquema,validarLecturas,validarError} from './lib/contrato.mjs';

const DIR=path.dirname(fileURLToPath(import.meta.url)),ROOT=path.resolve(DIR,'../../../../..');
const API='https://www.api.inmero.co/api-sgpmp-test';
const CASOS=['TC-M07-13','TC-M07-14','TC-M07-15','TC-M07-16'];
const IDS={'TC-M07-13':['deprecacion','gracia_90','auditoria'],'TC-M07-14':['repeticion','salto','retroceso','aviso_administrador'],'TC-M07-15':['patch','put','inmutabilidad'],'TC-M07-16':['activar','deprecar','inmutable']};
export const CAPACIDADES={contrato:'sigab-qa-ejecutor/1',grupo:'G039',casos:CASOS,operaciones:['reevaluar','reintentar'],versiones:{min:2,max:2},comprobaciones_obligatorias:Object.fromEntries(CASOS.map(k=>[k,{API:IDS[k]}])),limite:{solicitudes_totales:70,duracion_segundos:600}};
const sha=p=>createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const seguro=x=>String(x??'').replace(/eyJ[\w-]+\.[\w-]+\.[\w-]+/g,'[JWT]').replace(/[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}/g,'[CORREO]');
export const sanitize=x=>Array.isArray(x)?x.map(sanitize):x&&typeof x==='object'?Object.fromEntries(Object.entries(x).map(([k,v])=>[k,/^(nombre_usuario|nombre|nombres|apellidos|nombre_completo)$/i.test(k)?'[NOMBRE]':/correo_electronico|correo|email/i.test(k)?'[CORREO]':/token|secret|password|cookie|authorization|sha256_documento|contrasena|contraseña|clave|access_key|refresh/i.test(k)?'[RESERVADO]':sanitize(v)])):typeof x==='string'?seguro(x):x;
const guardar=(p,x)=>fs.writeFileSync(p,JSON.stringify(sanitize(x),null,2));
const vigentes=xs=>xs.filter(x=>['ACTIVO','DEPRECADO'].includes(x.estado));
const primera=(xs,estado)=>xs.filter(x=>x.estado===estado).sort((a,b)=>a.id_version_contrato_aaef-b.id_version_contrato_aaef)[0]??null;
const firma=xs=>JSON.stringify([...xs].sort((a,b)=>a.id_version_contrato_aaef-b.id_version_contrato_aaef).map(x=>[x.id_version_contrato_aaef,x.contrato_version,x.tipo_cambio,x.estado,x.id_mapeo_anexo_aaef,x.mapeadores,x.endpoint_asociado,x.fecha_vigencia,x.periodo_gracia_dias,x.descripcion,x.fecha_activacion,x.fecha_deprecacion,x.fecha_inactivacion]));
const iguales=(a,b)=>firma(a)===firma(b),combinar=xs=>xs.includes('RECHAZADO')?'RECHAZADO':xs.every(x=>x==='APROBADO')?'APROBADO':'NO_CONCLUYENTE';
const legible=z=>z.http<500&&![401,403].includes(z.http);
const runPattern=/^RUN-G039-V2-\d{8}-\d{6}$/;
export function dirRun(c){const dir=path.resolve(c.dir);if(!c.ensayo&&dir!==path.join(DIR,'EvaluacionV2','Resultados',c.runId))throw Error('CONTEXTO_FUERA_RUN');return dir;}
const loopback=x=>{try{const u=new URL(x);return u.protocol==='http:'&&['127.0.0.1','localhost'].includes(u.hostname)&&!!u.port;}catch{return false;}};

export function comprobar(){const archivos=['g039.mjs','lib/contrato.mjs','pruebas/contrato_g039.json','G039.postman_collection.json','pruebas/newman_hijo.mjs','pruebas/verificar.mjs','pruebas/simulador_g039.mjs','pruebas/escenarios_g039.mjs','pruebas/escenarios_g039.json','pruebas/g039_local.test.mjs','pruebas/contrato_cruzado.test.mjs','pruebas/g039_dto_test.py','README.md'];const faltan=archivos.filter(x=>!fs.existsSync(path.join(DIR,x)));const col=JSON.parse(fs.readFileSync(path.join(DIR,'G039.postman_collection.json'),'utf8'));const v1=path.join(DIR,'Resultados');const v2=path.join(DIR,'EvaluacionV2','Resultados');const ok=!faltan.length&&col.item.length===3&&(!fs.existsSync(v1)||fs.readdirSync(v1).every(x=>/^RUN-G039-V1-\d{8}-\d{6}$/.test(x)))&&(!fs.existsSync(v2)||fs.readdirSync(v2).every(x=>runPattern.test(x)))&&!fs.existsSync(path.join(v1,'TC-M07-G039_resultado.md'))&&!fs.existsSync(path.join(v2,'TC-M07-G039_reevaluacion_V2.md'));console.log(JSON.stringify({grupo:'G039',ok,faltan,coleccion:col.item.length,sha256:Object.fromEntries(archivos.filter(x=>fs.existsSync(path.join(DIR,x))).map(x=>[x,sha(path.join(DIR,x))]))}));return ok?0:2;}
export function leerEnv(proceso=process.env,archivo=path.join(ROOT,'.env.qa')){const e={};if(proceso.QA_AUTORIZADO==='SI'&&fs.existsSync(archivo))for(const line of fs.readFileSync(archivo,'utf8').split(/\r?\n/)){const m=line.match(/^\s*([A-Z][A-Z0-9_]*)\s*=(.*)$/);if(m)e[m[1]]=m[2].trim().replace(/^(['"])(.*)\1$/,'$2');}Object.assign(e,proceso);e.QA_AUTORIZADO=proceso.QA_AUTORIZADO;return e;}
export function contexto(args,prueba=false){const arg=k=>args.includes(k)?args[args.indexOf(k)+1]:null;const operacion=arg('--operacion'),versionN=Number(arg('--version')),intento=Number(arg('--intento')),runId=arg('--run-id'),referencia=arg('--autorizacion'),archivo=arg('--contexto');if(!CAPACIDADES.operaciones.includes(operacion)||versionN!==2||!Number.isInteger(intento)||intento<1||!referencia||!runPattern.test(runId??''))throw Error('CONTEXTO_INCOMPLETO');const dir=prueba?path.dirname(path.resolve(archivo??'.')):path.join(DIR,'EvaluacionV2','Resultados',runId);if(prueba&&(path.basename(dir)!==runId||!dir.startsWith(path.resolve(os.tmpdir())+path.sep)))throw Error('PRUEBA_FUERA_TEMPORAL');if(!archivo||path.resolve(archivo)!==path.join(dir,'contexto_operacion.json'))throw Error('CONTEXTO_FUERA_RUN');const d=JSON.parse(fs.readFileSync(archivo,'utf8'));if(d.grupo!=='G039'||d.run_id!==runId||d.version!==versionN||d.version_anterior!==1||d.intento!==intento||d.operacion!==operacion.toUpperCase()||d.referencia!==referencia||JSON.stringify(d.casos)!==JSON.stringify(CASOS))throw Error('CONTEXTO_INCOHERENTE');return{dir,runId,version:versionN,intento,operacion,referencia,ensayo:prueba,estricto:prueba};}
export function preflight(c,e){const faltan=[];for(const k of ['QA_ADMIN_EMAIL','QA_ADMIN_PASSWORD','QA_SANDBOX_SECRET','SIGAB_API_TEST_BASE'])if(!String(e[k]??'').trim())faltan.push(k);if(e.QA_AUTORIZADO!=='SI')faltan.push('QA_AUTORIZADO');const api=String(e.SIGAB_API_TEST_BASE??'').replace(/\/+$/,'');if(c.ensayo?!loopback(api):api!==API)faltan.push('API_NO_CANONICA');if(!runPattern.test(c.runId??''))faltan.push('RUN_ID');if(!c.referencia)faltan.push('AUTORIZACION');return{ok:!faltan.length,faltan,grupo:'G039',run_id:c.runId,version:c.version??2,referencia:c.referencia,presupuesto:CAPACIDADES.limite};}
async function lanzarNewman(input){return new Promise(resolve=>{let h;try{h=spawn(process.execPath,[path.join(DIR,'pruebas/newman_hijo.mjs')],{cwd:DIR,stdio:['pipe','pipe','pipe'],windowsHide:true});}catch(error){resolve({codigo:2,error:error.code??error.message});return;}let out='',error=null;const timer=setTimeout(()=>{error='ETIMEDOUT';h.kill();},240000);h.stdout.on('data',x=>out+=x);h.stderr.on('data',()=>{});h.on('error',e=>error=e.code??e.message);h.on('close',code=>{clearTimeout(timer);let z;try{z=JSON.parse(out);}catch{z={codigo:code??2,error:error??'NEWMAN_SIN_JSON'};}resolve(z);});h.stdin.on('error',()=>{});h.stdin.end(JSON.stringify(input));});}
export function verificarRollback(a,b){return iguales(a,b);}
function requisitos(anexos,contratos,permisos,parametros,avisos){
 const permiso=(r,a)=>permisos.some(x=>x.nombre_recurso===r&&x.id_accion===a);
 const vig=vigentes(contratos),activo=primera(contratos,'ACTIVO'),pendiente=primera(contratos,'PENDIENTE'),inactivo=primera(contratos,'INACTIVO');
 const min=Number(parametros.find(x=>x.nombre==='aaef_gracia_minima_dias')?.valor);
 const hoy=new Date().toISOString().slice(0,10),anexosUsables=new Set(anexos.filter(x=>['APROBADO','EN_REVISION'].includes(x.estado)).map(x=>x.id_mapeo_anexo_aaef));
 const vencidas=contratos.filter(x=>x.estado==='PENDIENTE'&&x.fecha_vigencia<=hoy&&anexosUsables.has(x.id_mapeo_anexo_aaef)&&x.mapeadores?.length);
 const ultimo=avisos.filter(x=>x.tipo_evento===41).sort((a,b)=>Date.parse(b.fecha_envio)-Date.parse(a.fecha_envio))[0];
 const edad=ultimo?(Date.now()-Date.parse(ultimo.fecha_envio))/60000:null;
 const filas=[...[[2,'contratos_aaef'],[3,'contratos_aaef'],[2,'auditoria_integracion']].map(([a,r])=>({requisito:'PERMISO_'+r+'_'+a,esperado:true,observado:permiso(r,a),cumple:permiso(r,a),bloqueante:true})),
 {requisito:'UNICA_VIGENTE_ACTIVO',esperado:{vigentes:1,activos:1},observado:{vigentes:vig.length,activos:contratos.filter(x=>x.estado==='ACTIVO').length},cumple:vig.length===1&&activo!==null,bloqueante:true},
 ...[['PENDIENTE',pendiente],['INACTIVO',inactivo]].map(([k,x])=>({requisito:k+'_EXISTENTE',esperado:'presente',observado:x?.id_version_contrato_aaef??null,cumple:!!x,bloqueante:true})),
 {requisito:'GRACIA_MINIMA_M09',esperado:'<=90',observado:min,cumple:Number.isInteger(min)&&min>=1&&min<=90,bloqueante:true},
 {requisito:'PENDIENTE_VENCIDA_ACTIVABLE',esperado:[],observado:vencidas.map(x=>x.id_version_contrato_aaef),cumple:!vencidas.length,bloqueante:true},
 {requisito:'ANTISPAM_11_MIN',esperado:'sin aviso o >=11 minutos',observado:edad,cumple:edad===null||Number.isFinite(edad)&&edad>=11,bloqueante:true}];
 return{filas,activo,pendiente,inactivo,bloqueado:filas.some(x=>!x.cumple)};
}
const nueva=(antes,despues,predicado)=>despues.some(x=>!antes.has(x.id_evento_integracion)&&predicado(x));
function armarResultado(r,c,deadline){r.autorizacion_referencia=c.referencia;r.consume_version=r.solicitudes.some(x=>x.metodo!=='GET'&&x.ruta!=='/sesiones/');r.cypress={codigo:null,total_pruebas:0,no_aplica:true};r.cierre.http=r.cierre.fases[0]?.http??null;r.cierre.run={cierre_http:r.cierre.http};r.cierre.rollback=r.cierre.fases[0]?.rollback??{verificado:false,motivo:'DELETE no ejecutado'};r.veredictos=Object.fromEntries(CASOS.map(k=>[k.slice(-2),combinar(r.pruebas[k])]));r.casos=Object.fromEntries(CASOS.map(k=>[k,{estado:r.veredictos[k.slice(-2)],comprobaciones:IDS[k]}]));r.comprobaciones=CASOS.flatMap(k=>IDS[k].map((id,i)=>({caso:k,fuente:'API',id,tipo:'ASSERT',estado:r.pruebas[k][i],evidencia:'resultado.json'})));const reglas={deprecacion:['DEPRECACION_NO_APLICADA','ALTA'],gracia_90:['GRACIA_INCORRECTA','MEDIA'],auditoria:['AUDITORIA_DEPRECACION_AUSENTE','MEDIA'],aviso_administrador:['AVISO_ADMINISTRADOR_AUSENTE','MEDIA'],retroceso:['TRANSICION_INVALIDA','MEDIA'],repeticion:['TRANSICION_INVALIDA','MEDIA'],salto:['TRANSICION_INVALIDA','MEDIA'],patch:['CODIGO_MODIFICACION_INCORRECTO','BAJA'],put:['CODIGO_MODIFICACION_INCORRECTO','BAJA'],inmutabilidad:['VERSION_MODIFICADA','ALTA'],activar:['REACTIVACION_CODIGO_INCORRECTO','BAJA'],deprecar:['REACTIVACION_CODIGO_INCORRECTO','BAJA'],inmutable:['INACTIVO_MODIFICADO','ALTA']};const vistos=new Set();for(const x of r.comprobaciones.filter(x=>x.estado==='RECHAZADO')){const [regla,defecto]=reglas[x.id];if(vistos.has(regla))continue;vistos.add(regla);const severidad=r.graves.includes(x.id)?'ALTA':defecto;r.incidencias.push({caso:x.caso,regla,severidad,certeza:c.ensayo?'PROBABLE':'CONFIRMADA',equipo_inicial:'Desarrollo',fundamento:'Primera discrepancia comprobada por API pública; causa raíz por determinar'});}r.solicitudes_total=r.solicitudes.length+(r.newman?.solicitudes??0)+r.cierre.fases.length;r.oficial=Object.values(r.veredictos).every(x=>['APROBADO','RECHAZADO'].includes(x))&&r.newman?.codigo===0&&r.newman?.fallos===0&&r.newman?.reportes===true&&r.evidencias.includes('newman/newman-G039.json')&&r.evidencias.includes('newman/newman-G039.html')&&r.problemas_tecnicos.length===0&&[200,404].includes(r.cierre.http)&&r.cierre.rollback.verificado&&r.solicitudes_total<=70&&Date.now()<=deadline;}
export function informe(c,r){const esperado={'TC-M07-13':'POST /deprecar 200 DEPRECADO; gracia 90 días por instante; CONTRATO_DEPRECADO nuevo con versión, estado, usuario y fecha.','TC-M07-14':'Tres transiciones rechazadas 422 TRANSICION_NO_PERMITIDA, listados intactos, un evento CONTRATO_TRANSICION_RECHAZADA WARNING nuevo por intento y aviso del primer rechazo al Administrador.','TC-M07-15':'PATCH y PUT rechazados con MODIFICACION_NO_PERMITIDA; versión idéntica antes y después.','TC-M07-16':'Activar y deprecar INACTIVO rechazados 4xx con REACTIVACION_NO_PERMITIDA; version INACTIVO y un evento WARNING nuevo por intento.'};return `# TC-M07-G039 — RF-98 v1.2\n\nGrupo G039; casos ${CASOS.join(', ')}; versión ${c.version} (anterior 1); RUN ${c.runId}; ambiente ${c.ensayo?'SIMULACIÓN LOCAL':'TEST'}; autorización ${c.referencia}; commit de TEST no consultado. Herramientas: Node ${process.version}, Newman código ${r.newman?.codigo??'no ejecutado'}; Cypress NO_APLICA. Oficial: ${r.oficial}. Solicitudes ${r.solicitudes_total}/70.\n\n## Resumen de veredictos\n\n${CASOS.map(k=>`- ${k}: **${r.casos[k].estado}**; ${IDS[k].map((id,i)=>`${id}=${r.pruebas[k][i]}`).join(', ')}.`).join('\n')}\n\n## Preflight\n\n${r.preflight_datos.map(x=>`- ${x.requisito}: esperado ${JSON.stringify(x.esperado)}, observado ${JSON.stringify(x.observado)}, cumple ${x.cumple}, bloqueante ${x.bloqueante}.`).join('\n')}\n\n## Comprobaciones API\n\n${CASOS.map(k=>`### ${k}\n\n**Esperado:** ${esperado[k]}\n\n**Observado:** ${r.solicitudes.filter(x=>x.caso===k).map(x=>`${x.id}: ${x.metodo} ${x.ruta}, HTTP ${x.http}, respuesta ${JSON.stringify(x.cuerpo_respuesta??x.cuerpo_error??x.cuerpo_lectura??null)}.`).join(' ')||'Sin peticiones por preflight o dependencia real.'}\n\n**Decisión:** ${r.casos[k].estado}.`).join('\n\n')}\n\n## Comparaciones API y auditoria\n\n${Object.entries(r.comparaciones??{}).map(([k,v])=>'- '+k+': '+JSON.stringify(v)).join('\n')||'Sin comparaciones por preflight o error tecnico.'}\n\n## Evidencias\n\n${r.evidencias.map(x=>`- ${x}`).join('\n')}\n\n## Incidencias y análisis de causas\n\n${r.incidencias.map(x=>`- ${x.regla}: ${x.severidad}, ${x.certeza}; atención inicial ${x.equipo_inicial}: ${x.fundamento}.`).join('\n')||'Sin incidencia de producto demostrada.'}\n\n## Problemas técnicos y observaciones\n\n${r.problemas_tecnicos.join('; ')||'Ninguno registrado.'} ${r.observaciones.join('; ')}\n\n## Conclusión y acciones\n\n${r.oficial?'Evaluacion concluida; revisar los casos rechazados y derivar incidencias observadas a Desarrollo. Sin rechazos, archivar evidencia.':'Evaluación técnica no oficial; resolver los casos no concluyentes o el cierre antes de decidir.'}\n\n## Cierre y rollback\n\nDELETE HTTP ${r.cierre.http??'no consta'}; rollback ${r.cierre.rollback.verificado?'verificado':'no verificado'} (${r.cierre.rollback.motivo}). El login previo al RUN persiste fuera del sandbox. Los eventos WARNING y los avisos CA-27 persisten fuera del sandbox.\n`;}
function lecturaResumida(ruta,raw){if(ruta==='/configuracion/parametros-integracion-contable')return raw.map(x=>({nombre:x.nombre,valor:x.valor,fuente:x.fuente}));if(ruta==='/integracion/contratos'&&Array.isArray(raw))return raw.map(x=>Object.fromEntries(['id_version_contrato_aaef','contrato_version','tipo_cambio','id_mapeo_anexo_aaef','periodo_gracia_dias','descripcion','fecha_vigencia','estado','fecha_activacion','fecha_deprecacion','fecha_inactivacion','mapeadores','endpoint_asociado'].map(k=>[k,x[k]??null])));if(ruta.startsWith('/integracion/auditoria')&&raw?.items)return{total:raw.total,items:raw.items.map(x=>({id_evento_integracion:x.id_evento_integracion,tipo_evento:x.tipo_evento,severidad:x.severidad,version_contrato:x.version_contrato,estado_resultante:x.estado_resultante,id_usuario:x.id_usuario,fecha_evento:x.fecha_evento,codigo_resultado:x.codigo_resultado,json_detalle:sanitize(x.json_detalle)}))};if(ruta.startsWith('/notificaciones')&&raw?.items)return{total:raw.total,items:raw.items.map(x=>({id_notificacion:x.id_notificacion,tipo_evento:x.tipo_evento,mensaje:sanitize(x.mensaje),nivel:x.nivel,modulo:x.modulo,ocurrencias:x.ocurrencias,fecha_envio:x.fecha_envio,fecha_ultima_ocurrencia:x.fecha_ultima_ocurrencia}))};if(ruta==='/integracion/anexos'&&Array.isArray(raw))return raw.map(x=>({id_mapeo_anexo_aaef:x.id_mapeo_anexo_aaef,estado:x.estado}));if(ruta==='/sesiones/me/permisos')return{permisos:raw?.permisos?.map(x=>({nombre_recurso:x.nombre_recurso,id_accion:x.id_accion}))??[]};return null;}
export async function ejecutar(c,e,fetcher=fetch,dobles={}){
 const pf=preflight(c,e);if(!pf.ok)throw Error('PREFLIGHT_'+pf.faltan.join('_'));
 if(!c.ensayo&&Object.keys(dobles).length)throw Error('DOBLES_SOLO_ENSAYO');
 const dir=dirRun(c),nombre='TC-M07-G039_reevaluacion_V2.md';
 if(!fs.existsSync(dir))throw Error('RUN_NO_PRECREADO');
 if(fs.existsSync(path.join(dir,'resultado.json'))||fs.existsSync(path.join(dir,nombre)))throw Error('RUN_EXISTENTE');
 guardar(path.join(dir,'preflight.json'),pf);
 const deadline=Date.now()+600000,api=String(e.SIGAB_API_TEST_BASE).replace(/\/+$/,'');
 const r={grupo:'G039',run_id:c.runId,version:2,solicitudes:[],pruebas:Object.fromEntries(CASOS.map(k=>[k,IDS[k].map(()=>'NO_CONCLUYENTE')])),graves:[],incidencias:[],evidencias:['preflight.json','resultado.json'],problemas_tecnicos:[],preflight_datos:[],cierre:{fases:[]},newman:null,observaciones:[],versiones_elegidas:{},comparaciones:{},oficial:false};
 let token=null,serial=false,abierto=false,loginIntentado=false,base=null;
 async function pedir(metodo,ruta,body,caso,publica=false){
  if(serial)throw Error('PETICION_CONCURRENTE');
  if(r.solicitudes.length+(r.newman?.solicitudes??0)+1>=70||Date.now()>deadline)throw Error('PRESUPUESTO_AGOTADO');
  if(!esquema(metodo,ruta))throw Error('RUTA_FUERA_CONTRATO_'+metodo+'_'+ruta);
  const login=metodo==='POST'&&ruta==='/sesiones/';
  if(login){if(loginIntentado||abierto)throw Error('LOGIN_REPETIDO');loginIntentado=true;}else if(!token)throw Error('LOGIN_REQUERIDO');
  serial=true;const row={id:'G039-'+String(r.solicitudes.length+1).padStart(3,'0'),metodo,ruta,caso:caso??null,http:null};
  if(body!==undefined)row.cuerpo_solicitud=sanitize(body);r.solicitudes.push(row);
  try{
   const headers={...(login?{}:{Authorization:'Bearer '+token}),...(login||publica?{}:{'X-Test-Run-Id':c.runId,'X-Sandbox-Secret':e.QA_SANDBOX_SECRET}),...(body===undefined?{}:{'Content-Type':'application/json'})};
   if(!login&&!publica)abierto=true;
   const z=await fetcher(api+ruta,{method:metodo,headers,redirect:'manual',...(body===undefined?{}:{body:JSON.stringify(body)}),signal:AbortSignal.timeout(120000)});
   row.http=z.status;const raw=await z.json().catch(()=>null);row.eco=z.headers.get('x-test-run-id')===c.runId;
   if(!login&&!publica&&(!row.eco||z.status>=500))throw Error('SANDBOX_O_INFRA_'+row.id+'_'+z.status);
   if(z.status===403)throw Error('PERMISO_403');
   if(z.status>=400){row.cuerpo_error=sanitize(raw);row.error_estandar=validarError(raw);}
   else if(metodo!=='GET')row.cuerpo_respuesta=sanitize(raw);
   else row.cuerpo_lectura=sanitize(lecturaResumida(ruta,raw));
   return{http:z.status,data:z.status<400?validarLecturas(raw,metodo,ruta,{estricto:!!c.estricto}):raw,row};
  }finally{serial=false;}
 }
 const get=async(ruta,caso,publica=false)=>{const z=await pedir('GET',ruta,undefined,caso,publica);if(z.http!==200)throw Error('LECTURA_'+ruta+'_'+z.http);return z.data;};
 const listar=(caso=null,publica=false)=>get('/integracion/contratos',caso,publica);
 async function paginas(ruta,caso){let p=1,total=0,items=[];do{const z=await get(ruta+(ruta.includes('?')?'&':'?')+'pagina='+p+'&tamano=50',caso);if(p===1)total=z.total;items.push(...z.items);p++;if(p>30&&items.length<total)throw Error('PAGINACION_EXCESIVA');}while(items.length<total);return items;}
 // El repositorio ordena por fecha_evento DESC; el evento nuevo debe estar en la primera pagina.
 const auditoria=async(tipo,caso)=>(await get('/integracion/auditoria?tipo_evento='+tipo+'&pagina=1&tamano=100',caso)).items;
 const bandeja=caso=>paginas('/notificaciones?modulo=integracion&nivel=CRITICA',caso);
 const idset=xs=>new Set(xs.map(x=>x.id_evento_integracion));
 const nuevos=(antes,despues)=>despues.filter(x=>!antes.has(x.id_evento_integracion));
 const evento=x=>({id:x.id_evento_integracion,tipo:x.tipo_evento,severidad:x.severidad,version:x.version_contrato,codigo_resultado:x.codigo_resultado,json_detalle:sanitize(x.json_detalle),actor:x.id_usuario,fecha:x.fecha_evento});
 const decidir=(caso,id,v)=>r.pruebas[caso][IDS[caso].indexOf(id)]=v;
 async function cerrar(){
  if(!abierto)return;const f={fase:'UNICA',http:null,rollback:{verificado:false,motivo:'DELETE no confirmado'}};r.cierre.fases.push(f);
  try{const z=await fetcher(api+'/test-control/runs/'+c.runId,{method:'DELETE',headers:{'X-Sandbox-Secret':e.QA_SANDBOX_SECRET},signal:AbortSignal.timeout(120000)});f.http=z.status;abierto=false;
   if([200,404].includes(z.status)&&base){const posterior=await listar(null,true);f.rollback={verificado:verificarRollback(base,posterior),motivo:'Comparaci?n p?blica completa tras DELETE'};}
  }catch(err){f.rollback.motivo=seguro(err.message);abierto=false;}
 }
 async function intento(caso,id,metodo,ruta,body,codigo,version){
  const antes=await listar(caso),a0=idset(await auditoria('CONTRATO_TRANSICION_RECHAZADA',caso));
  const z=await pedir(metodo,ruta,body,caso),despues=await listar(caso),ev=nuevos(a0,await auditoria('CONTRATO_TRANSICION_RECHAZADA',caso));
  const warnings=ev.filter(x=>x.tipo_evento==='CONTRATO_TRANSICION_RECHAZADA'&&x.severidad==='WARNING'&&x.version_contrato===version&&x.codigo_resultado===codigo);
  const estable=iguales(antes,despues),correcto=z.http===422&&z.row.error_estandar&&z.data?.error_code===codigo;
  decidir(caso,id,legible(z)?correcto&&estable&&warnings.length===1?'APROBADO':'RECHAZADO':'NO_CONCLUYENTE');
  r.comparaciones[id]={http:z.http,error:z.http>=400?z.data?.error_code??null:null,estable,eventos:ev.map(evento)};
  if(!estable)r.graves.push(id);return z;
 }
 try{
  const sesion=await pedir('POST','/sesiones/',{correo_electronico:e.QA_ADMIN_EMAIL,contrasena:e.QA_ADMIN_PASSWORD});if(sesion.http!==200)throw Error('LOGIN_FALLIDO');token=sesion.data.token;
  const permisos=(await get('/sesiones/me/permisos')).permisos,anexos=await get('/integracion/anexos');base=await listar();
  const parametros=await get('/configuracion/parametros-integracion-contable'),avisosBase=await bandeja();
  const rechazosBase=await auditoria('CONTRATO_TRANSICION_RECHAZADA'),deprecadosBase=await auditoria('CONTRATO_DEPRECADO');r.comparaciones.linea_base_auditoria={rechazos:rechazosBase.map(x=>x.id_evento_integracion),deprecados:deprecadosBase.map(x=>x.id_evento_integracion)};
  const s=requisitos(anexos,base,permisos,parametros,avisosBase);r.preflight_datos=s.filas;
  r.versiones_elegidas=Object.fromEntries([['ACTIVO',s.activo],['PENDIENTE',s.pendiente],['INACTIVO',s.inactivo]].map(([k,x])=>[k,x?{id:x.id_version_contrato_aaef,version:x.contrato_version,estado:x.estado}:null]));
  if(!s.bloqueado){
   const activo=s.activo,pendiente=s.pendiente,inactivo=s.inactivo;
   const primero=await intento('TC-M07-14','repeticion','POST','/integracion/contratos/'+activo.id_version_contrato_aaef+'/activar',undefined,'TRANSICION_NO_PERMITIDA',activo.contrato_version);
   const avisosPrimeros=await bandeja('TC-M07-14'),maxId=Math.max(0,...avisosBase.map(x=>x.id_notificacion)),previos=new Map(avisosBase.map(x=>[x.id_notificacion,x]));
   const candidato=avisosPrimeros.filter(x=>x.tipo_evento===41&&x.mensaje.includes(activo.contrato_version)&&/rechaz|transici[oó]n|activar/i.test(x.mensaje)).map(x=>{const previo=previos.get(x.id_notificacion);return{via:x.id_notificacion>maxId?'nuevo':previo&&(x.ocurrencias>previo.ocurrencias||Date.parse(x.fecha_ultima_ocurrencia)>Date.parse(previo.fecha_ultima_ocurrencia||previo.fecha_envio))?'agrupado':null,id:x.id_notificacion,ocurrencias:x.ocurrencias};}).find(x=>x.via);
   decidir('TC-M07-14','aviso_administrador',legible(primero)?candidato?'APROBADO':'RECHAZADO':'NO_CONCLUYENTE');
   r.comparaciones.aviso_administrador={base:avisosBase.map(x=>({id:x.id_notificacion,tipo:x.tipo_evento,modulo:x.modulo,fecha_envio:x.fecha_envio,ocurrencias:x.ocurrencias,fecha_ultima_ocurrencia:x.fecha_ultima_ocurrencia})),posterior:avisosPrimeros.map(x=>({id:x.id_notificacion,tipo:x.tipo_evento,modulo:x.modulo,fecha_envio:x.fecha_envio,ocurrencias:x.ocurrencias,fecha_ultima_ocurrencia:x.fecha_ultima_ocurrencia,mensaje:sanitize(x.mensaje)})),candidato:candidato??null};
   let avisosPrevios=avisosPrimeros;
   async function observarAviso(caso,etapa){const actuales=await bandeja(caso);const antes=new Map(avisosPrevios.map(x=>[x.id_notificacion,x]));const cambios=actuales.filter(x=>x.tipo_evento===41&&(!antes.has(x.id_notificacion)||x.ocurrencias>antes.get(x.id_notificacion).ocurrencias));r.observaciones.push(etapa+': avisos tipo 41 nuevos o agrupados '+cambios.length+(cambios.length?'':' (antispam o ausencia de aviso)'));avisosPrevios=actuales;}
   await intento('TC-M07-14','salto','POST','/integracion/contratos/'+pendiente.id_version_contrato_aaef+'/deprecar',{dias_gracia:90},'TRANSICION_NO_PERMITIDA',pendiente.contrato_version);await observarAviso('TC-M07-14','14 salto');
   for(const metodo of ['PATCH','PUT']){
    const caso='TC-M07-15',antes=await listar(caso),z=await pedir(metodo,'/integracion/contratos/'+activo.id_version_contrato_aaef,{descripcion:'QA G039 V2'},caso),despues=await listar(caso),estable=iguales(antes,despues);
    const correcto=z.http>=400&&z.http<500&&z.row.error_estandar&&z.data?.error_code==='MODIFICACION_NO_PERMITIDA';
    decidir(caso,metodo.toLowerCase(),legible(z)?correcto&&estable?'APROBADO':'RECHAZADO':'NO_CONCLUYENTE');
    if(!estable)r.graves.push(metodo.toLowerCase());r.comparaciones[metodo.toLowerCase()]={http:z.http,error:z.http>=400?z.data?.error_code??null:null,estable};await observarAviso(caso,'15 '+metodo);
   }
   decidir('TC-M07-15','inmutabilidad',r.graves.some(x=>['patch','put'].includes(x))?'RECHAZADO':'APROBADO');
   const antes13=await listar('TC-M07-13');
   if(antes13.find(x=>x.id_version_contrato_aaef===activo.id_version_contrato_aaef)?.estado==='ACTIVO'){
    const a0=idset(await auditoria('CONTRATO_DEPRECADO','TC-M07-13')),z=await pedir('POST','/integracion/contratos/'+activo.id_version_contrato_aaef+'/deprecar',{dias_gracia:90},'TC-M07-13');
    const despues=await listar('TC-M07-13'),v=despues.find(x=>x.id_version_contrato_aaef===activo.id_version_contrato_aaef),ev=nuevos(a0,await auditoria('CONTRATO_DEPRECADO','TC-M07-13'));
    decidir('TC-M07-13','deprecacion',legible(z)?z.http===200&&v?.estado==='DEPRECADO'?'APROBADO':'RECHAZADO':'NO_CONCLUYENTE');
    const delta=Date.parse(v?.fecha_inactivacion)-Date.parse(v?.fecha_deprecacion);
    decidir('TC-M07-13','gracia_90',Number.isFinite(delta)?delta===90*86400000?'APROBADO':'RECHAZADO':'NO_CONCLUYENTE');
    decidir('TC-M07-13','auditoria',ev.some(x=>x.version_contrato===activo.contrato_version&&x.json_detalle?.estado==='DEPRECADO'&&x.id_usuario!=null&&x.fecha_evento)?'APROBADO':'RECHAZADO');
    r.comparaciones.deprecacion={eventos:ev.map(evento),estado:v?.estado??null,delta};
    if(v?.estado==='DEPRECADO'){await intento('TC-M07-14','retroceso','POST','/integracion/contratos/'+activo.id_version_contrato_aaef+'/activar',undefined,'TRANSICION_NO_PERMITIDA',activo.contrato_version);await observarAviso('TC-M07-14','14 retroceso');}
    else r.observaciones.push('Retroceso NO_CONCLUYENTE: no hay DEPRECADO tras caso 13');
   }else r.observaciones.push('13 NO_CONCLUYENTE: ACTIVO cambi? antes de deprecar');
   for(const accion of ['activar','deprecar']){await intento('TC-M07-16',accion,'POST','/integracion/contratos/'+inactivo.id_version_contrato_aaef+'/'+accion,accion==='deprecar'?{dias_gracia:90}:undefined,'REACTIVACION_NO_PERMITIDA',inactivo.contrato_version);await observarAviso('TC-M07-16','16 '+accion);}
   const final=await listar('TC-M07-16');decidir('TC-M07-16','inmutable',final.find(x=>x.id_version_contrato_aaef===inactivo.id_version_contrato_aaef)?.estado==='INACTIVO'&&!r.graves.includes('activar')&&!r.graves.includes('deprecar')?'APROBADO':'RECHAZADO');
   const avisosFinal=await bandeja();r.observaciones.push('Avisos tipo 41 posteriores: '+avisosFinal.filter(x=>x.tipo_evento===41).length+'; antispam de 10 minutos aplicable');
   const salida=path.join(dir,'newman'),coleccion=JSON.parse(fs.readFileSync(path.join(DIR,'G039.postman_collection.json'),'utf8'));
   r.newman=await(dobles.newman??lanzarNewman)({salida,coleccion,environment:{values:[{key:'base_url',value:api},{key:'admin_token',value:token},{key:'run_id',value:c.runId},{key:'sandbox_secret',value:e.QA_SANDBOX_SECRET}]}});if(r.newman.codigo!==0||r.newman.fallos!==0||!r.newman.reportes)r.problemas_tecnicos.push('NEWMAN_NO_VALIDADO_'+String(r.newman.error??r.newman.codigo));
   for(const f of ['newman-G039.json','newman-G039.html'])if(fs.existsSync(path.join(salida,f)))r.evidencias.push('newman/'+f);
  }else r.observaciones.push('Preflight bloqueante: DELETE sin escrituras');
 }catch(err){r.problemas_tecnicos.push(seguro(err.message));}
 finally{await cerrar();r.solicitudes=sanitize(r.solicitudes);armarResultado(r,c,deadline);guardar(path.join(dir,'resultado.json'),r);fs.writeFileSync(path.join(dir,nombre),informe(c,sanitize(r)),'utf8');}
 return r;
}
export async function principal(argv,{proceso=process.env,archivo=path.join(ROOT,'.env.qa'),prueba=false,fetcher=fetch,dobles={}}={}){const c=contexto(argv,prueba),e=leerEnv(proceso,archivo),p=preflight(c,e);fs.writeFileSync(path.join(c.dir,'preflight.json'),JSON.stringify(sanitize(p),null,2));if(!p.ok)return{preflight:p,codigo:2};const resultado=await ejecutar(c,e,fetcher,dobles);return{preflight:p,codigo:0,resultado};}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){try{if(process.argv.includes('--capacidades'))console.log(JSON.stringify(CAPACIDADES));else if(process.argv.includes('--comprobar'))process.exitCode=comprobar();else{const prueba=process.env.NODE_ENV==='test'&&process.argv.includes('--prueba-cli-local');const archivo=prueba?path.resolve(process.env.G039_PRUEBA_ENV_FILE??'.'):path.join(ROOT,'.env.qa');if(prueba&&!archivo.startsWith(path.resolve(os.tmpdir())+path.sep))throw Error('ENV_PRUEBA_FUERA_TEMPORAL');const z=await principal(process.argv.slice(2),{archivo,prueba});if(z.codigo===2){console.error(`PREFLIGHT_${z.preflight.faltan.join('_')}`);process.exitCode=2;}else console.log(JSON.stringify({grupo:'G039',oficial:z.resultado.oficial,casos:z.resultado.casos,solicitudes:z.resultado.solicitudes_total}));}}catch(err){console.error(seguro(err.message));process.exitCode=2;}}



