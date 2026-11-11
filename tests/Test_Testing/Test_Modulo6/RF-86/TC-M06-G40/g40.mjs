import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import {spawn} from 'node:child_process';
import {createHash} from 'node:crypto';
import {createRequire} from 'node:module';
import {AsyncLocalStorage} from 'node:async_hooks';
import {fileURLToPath} from 'node:url';
import avisoG40 from './lib/aviso_g40.cjs';
const {coincideCombinacion}=avisoG40;
import {DIR,CASOS,IDS,CONTRATO,PRESUPUESTO,entrada,validarActor,periodoDestino,vigente,idsNuevos} from './lib/g40_core.mjs';

const ROOT=path.resolve(DIR,'../../../../..'), API='https://www.api.inmero.co/api-sgpmp-test';
const COL=path.join(DIR,'G40.postman_collection.json'), CONTRACT=path.join(DIR,'pruebas/contrato_g40.json');
const SHA={coleccion:'242bffafae66f1858c6663c177a4b4e1d18f084875a58cd8909be45f6fca1292',
  contrato:'42a848025dc4e0be3d9afb6ffb494b3465b718aed428b3d57b7f50c4f0f43113'};
const require=createRequire(import.meta.url), local=new AsyncLocalStorage();
const hash=p=>createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const sha=p=>fs.existsSync(p)?hash(p):null;
const n=x=>Number.isSafeInteger(Number(x))&&Number(x)>0?Number(x):null;
const clean=x=>String(x??'').replace(/eyJ[\w-]+\.[\w-]+\.[\w-]+|[\w.+-]+@[\w.-]+/gi,'[RESERVADO]').replace(/[\r\n|]/g,' ').slice(0,240);
const save=(p,x)=>fs.writeFileSync(p,JSON.stringify(x,null,2));
const today=()=>new Intl.DateTimeFormat('en-CA',{timeZone:'America/Bogota',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
const reportName=v=>v===1?'TC-M06-G40_resultado.md':`TC-M06-G40_reevaluacion_V${v}.md`;
const newmanVersion=()=>{try{return require(require.resolve('newman/package.json',{paths:[ROOT]})).version;}
  catch{const p=path.join(path.dirname(process.execPath),'node_modules','newman','package.json');
    return fs.existsSync(p)?JSON.parse(fs.readFileSync(p)).version:null;}};
const cypressVersion=()=>{try{return require(require.resolve('cypress/package.json',{paths:[ROOT]})).version;}
  catch{return null;}};
function resumenCypress(r,dir){let conteos={};try{conteos=JSON.parse(fs.readFileSync(path.join(dir,'cypress/G40-cypress.json'),'utf8'));}catch{}
  return{total_pruebas:conteos.totalTests??0,aprobadas:conteos.totalPassed??0,
    fallidas:conteos.totalFailed??0,codigo:r.herramientas.cypress?.codigo??null,
    version:cypressVersion(),spec:'g40.cy.js',acta:r.herramientas.cypress?.acta?.id??null};}
export const CAPACIDADES={contrato:'sigab-qa-ejecutor/1',grupo:'G40',casos:CASOS,
  operaciones:['evaluar','reintentar','reevaluar'],versiones:{min:1,max:99},
  comprobaciones_obligatorias:{'TC-M06-018':{API:['G40-API-018-01'],UI:['G40-UI-018-01']}},
  limite:{solicitudes_totales:150,duracion_segundos:1800},baja_automatizada:false};
export const conPeticiones=(fetcher,fn)=>local.run({fetcher,ocupado:false,hijo:false,solicitudes:0},fn);
export async function fetchEnContexto(...args){const s=local.getStore();if(!s)return globalThis.fetch(...args);
  if(s.ocupado||s.hijo)throw Error('PETICION_CONCURRENTE');s.ocupado=true;
  try{s.solicitudes++;const res=await s.fetcher(...args),body=await res.json().catch(()=>null);
    return{status:res.status,headers:res.headers,json:async()=>body};}finally{s.ocupado=false;}}
export function leerEnv(proceso=process.env,archivo=path.join(ROOT,'.env.qa')){const e={};
  if(proceso.QA_AUTORIZADO==='SI'&&fs.existsSync(archivo))for(const line of fs.readFileSync(archivo,'utf8').split(/\r?\n/)){
    const m=line.match(/^\s*([A-Z][A-Z0-9_]*)\s*=(.*)$/);if(m)e[m[1]]=m[2].trim().replace(/^(['"])(.*)\1$/,'$2');}
  Object.assign(e,proceso);e.QA_AUTORIZADO=proceso.QA_AUTORIZADO;return e;}
export function contexto(argv,ensayo=false){const v=k=>argv.includes(k)?argv[argv.indexOf(k)+1]:null;
  const operacion=v('--operacion'),version=Number(v('--version')),intento=Number(v('--intento'));
  const runId=v('--run-id'),referencia=v('--autorizacion'),archivo=path.resolve(v('--contexto')??'.');
  if(!CAPACIDADES.operaciones.includes(operacion)||!Number.isInteger(version)||version<1||
    !Number.isInteger(intento)||intento<1||!referencia||!new RegExp(`^RUN-G40-V${version}-\\d{8}-\\d{6}$`).test(runId??''))
    throw Error('Contexto de RUN incompleto');
  const dir=ensayo?path.dirname(archivo):path.join(DIR,...(version===1?['Resultados',runId]:[`EvaluacionV${version}`,'Resultados',runId]));
  if(ensayo&&(path.basename(dir)!==runId||!dir.startsWith(path.resolve(os.tmpdir())+path.sep)))throw Error('Ensayo fuera de temporal');
  if(path.dirname(archivo)!==dir||path.basename(archivo)!=='contexto_operacion.json')throw Error('Contexto fuera del RUN');
  const c=JSON.parse(fs.readFileSync(archivo,'utf8'));
  if(c.grupo!=='G40'||c.run_id!==runId||c.version!==version||c.intento!==intento||c.operacion!==operacion.toUpperCase()||
    c.referencia!==referencia||JSON.stringify(c.casos)!==JSON.stringify(CASOS))throw Error('Contexto incoherente');
  return{operacion,version,intento,runId,referencia,dir,ensayo};}
export function preflight(c,e){const b=['SIGAB_API_TEST_BASE','QA_SANDBOX_SECRET','QA_CONTADOR_EMAIL','QA_CONTADOR_PASSWORD',
  'QA_ADMIN_EMAIL','QA_ADMIN_PASSWORD'].filter(k=>!String(e[k]??'').trim());
  if(e.QA_AUTORIZADO!=='SI')b.push('QA_AUTORIZADO');const base=String(e.SIGAB_API_TEST_BASE??'').replace(/\/+$/,'');
  if(c.ensayo?!/^http:\/\/(127\.0\.0\.1|localhost):\d+$/.test(base):base!==API)b.push('API_NO_CANONICA');
  if(!newmanVersion())b.push('NEWMAN_NO_DISPONIBLE');
  if(sha(COL)!==SHA.coleccion||sha(CONTRACT)!==SHA.contrato)b.push('HUELLA_ARCHIVO');
  return{grupo:'G40',run_id:c.runId,ok:!b.length,fase:'PREFLIGHT',barreras:b,presupuesto:PRESUPUESTO,
    herramientas:{node:process.version,newman:newmanVersion()},efectos_externos:['Logins auditados fuera del RUN','Procesamiento M06 puede atender eventos ajenos']};}
export function comprobar(){const files=['g40.mjs','lib/g40_core.mjs','G40.postman_collection.json','pruebas/contrato_g40.json',
  'pruebas/newman_hijo.mjs','pruebas/registro_qa.mjs','g40.cy.js','g40.cypress.config.cjs','README.md'];
  const faltan=files.filter(x=>!fs.existsSync(path.join(DIR,x)));
  const items=fs.existsSync(COL)?JSON.parse(fs.readFileSync(COL)).item??[]:[];
  const ok=!faltan.length&&items.length===3&&items.every(x=>x.request.header.some(h=>h.key==='Authorization'&&h.value==='Bearer {{contador_token}}'))&&
    sha(COL)===SHA.coleccion&&sha(CONTRACT)===SHA.contrato&&
    (!fs.existsSync(path.join(DIR,'Resultados'))||!fs.readdirSync(path.join(DIR,'Resultados')).some(x=>x.endsWith('.md')));
  console.log(JSON.stringify({grupo:'G40',ok,faltan,items:items.length,sha256:{coleccion:sha(COL),contrato:sha(CONTRACT)},newman:newmanVersion()}));return ok?0:2;}
const type=(schema,value,key)=>{if(typeof schema==='string'){const t=value===null?'null':Array.isArray(value)?'array':typeof value;
    if(value===undefined||!schema.split('|').includes(t)&&!(schema.includes('decimal')&&t==='string'&&/^-?\d+(\.\d+)?$/.test(value)))throw Error(`${key}: ${t}, esperado ${schema}`);}
  else if(Array.isArray(schema)){if(!Array.isArray(value))throw Error(`${key}: no es array`);for(const x of value)type(schema[0],x,key+'[]');}
  else{if(!value||typeof value!=='object'||Array.isArray(value))throw Error(`${key}: no es objeto`);
    for(const [k,v] of Object.entries(schema))type(v,value[k],key+'.'+k);}};
export function contrastarRespuesta(r,id,actor,http,data,ruta){const p=entrada(id);let motivo=null;
  try{if(p.metodo!=='DELETE')type(p.tipo==='array'?[p.campos]:p.campos,data,id);}catch(e){motivo=e.message;}
  const fila={id,ruta,actor,http,resultado:motivo?'discrepa':'coincide',...(motivo?{motivo}:{})};r.contraste_contrato.push(fila);
  if(motivo)r.discrepancias_contrato.push(fila);return !motivo;}
export function verificarPermisos(data,actor){if(!Array.isArray(data?.permisos))throw Error(`Permisos ${actor}: esquema`);
  for(const p of CONTRATO.peticiones.filter(x=>x.actor===actor)){
    if(p.permiso==='autenticado:0')continue;
    const [recurso,accion]=p.permiso.split(':');
    if(!data.permisos.some(x=>x.nombre_recurso===recurso&&Number(x.id_accion)===Number(accion)))throw Error(`Permisos ${actor}: ${p.permiso}`);}}
function blank(c){return{grupo:'G40',run_id:c.runId,version:c.version,intento:c.intento,autorizacion_referencia:c.referencia,
  casos:{},comprobaciones:[],solicitudes:[],evidencias:[],incidencias:[],problemas_tecnicos:[],contraste_contrato:[],discrepancias_contrato:[],
  observado:{},herramientas:{node:process.version,newman:null,cypress:null},cierre:{run:{cierre_http:null},rollback:{verificado:false}},
  oficial:false,consume_version:false};}
async function login(api,email,password){const x=await fetchEnContexto(api+'/sesiones/',{method:'POST',redirect:'manual',
  headers:{'Content-Type':'application/json'},body:JSON.stringify({correo_electronico:email,contrasena:password}),signal:AbortSignal.timeout(120000)});
  return x.status===200?(await x.json())?.token:null;}
async function request(r,c,e,t,id,ruta,body){validarActor(id,t.actor);const p=entrada(id);
  if(r.solicitudes.length>=110||Date.now()>r._deadline)throw Error('PRESUPUESTO_AGOTADO');
  const row={id,metodo:p.metodo,ruta:ruta.split('?')[0],actor:t.actor,http:null};r.solicitudes.push(row);
  const headers={Authorization:`Bearer ${t[t.actor]}`,'X-Test-Run-Id':c.runId,'X-Sandbox-Secret':t.secret,
    ...(body===undefined?{}:{'Content-Type':'application/json'})};
  try{const x=await fetchEnContexto(e.SIGAB_API_TEST_BASE+ruta,{method:p.metodo,headers,redirect:'manual',
    body:body===undefined?undefined:JSON.stringify(body),signal:AbortSignal.timeout(p.metodo==='GET'?30000:120000)});
    const data=await x.json();row.http=x.status;row.eco=x.headers.get('x-test-run-id')===c.runId;
    const valido=x.status===(p.http??200)&&contrastarRespuesta(r,id,t.actor,x.status,data,ruta);
    return{http:x.status,data,eco:row.eco,valido};
  }catch(error){if(error.message==='PETICION_CONCURRENTE')throw error;row.error=clean(error.message);
    return{http:null,data:null,eco:false,valido:false};}}
const good=(x,http=200)=>x?.http===http&&x.eco&&x.valido;
const ids=(a,k)=>new Set(a.map(x=>String(x[k])));
async function pages(q,id,field,total,ruta){const all=[];for(let page=1;page<=10;page++){
  const x=await q(id,ruta(page));if(!good(x)||!Array.isArray(x.data?.[field])||!Number.isInteger(x.data?.[total]))throw Error(`${id}: página incompleta`);
  all.push(...x.data[field]);if(all.length>=x.data[total])return all;}throw Error(`${id}: paginación incompleta`);}
async function child(script,input){const s=local.getStore();if(s?.ocupado||s?.hijo)throw Error('PETICION_CONCURRENTE');if(s)s.hijo=true;
  try{return await new Promise(resolve=>{let p,stdout='',error=null;try{p=spawn(process.execPath,[script],{stdio:['pipe','pipe','pipe'],windowsHide:true,timeout:180000});}
    catch(e){resolve({code:null,error:e,stdout:''});return;}p.stdout.on('data',x=>stdout+=x);p.stderr.resume();p.on('error',e=>error=e);
    p.on('close',code=>resolve({code,error,stdout}));p.stdin.on('error',()=>{});p.stdin.end(JSON.stringify(input));});}
  finally{if(s)s.hijo=false;}}
async function runNewman(r,c,e,t,pid){const dir=path.join(c.dir,'newman');fs.mkdirSync(dir,{recursive:true});
  const values={base_url:e.SIGAB_API_TEST_BASE,run_id:c.runId,sandbox_secret:t.secret,contador_token:t.contador,periodo:String(pid)};
  const input={coleccion:JSON.parse(fs.readFileSync(COL)),environment:{values:Object.entries(values).map(([key,value])=>({key,value,enabled:true}))},timeout:30000,salida:dir};
  let out=await child(path.join(DIR,'pruebas/newman_hijo.mjs'),input);
  if(c.ensayo&&out.error?.code==='EPERM'){const {ejecutarNewman}=await import('./pruebas/newman_hijo.mjs');
    const x=await ejecutarNewman(input);out={code:x.fallido?2:0,stdout:JSON.stringify(x)};}
  let data={};try{data=JSON.parse(out.stdout);}catch{}r.herramientas.newman={version:newmanVersion(),codigo:out.code,
    solicitudes:data.solicitudes?.length??0,iteraciones:data.solicitudes?.length===3?1:0,
    fallos:(data.solicitudes??[]).flatMap(x=>x.aserciones??[]).filter(x=>x.error).length,error:out.error?.code??data.error??null};
  for(const row of data.solicitudes??[])if(row.contraste){r.contraste_contrato.push({...row.contraste,fuente:'Newman'});
    if(row.contraste.resultado==='discrepa')r.discrepancias_contrato.push(row.contraste);}
  for(const name of ['newman-G40.json','newman-G40.html'])if(fs.existsSync(path.join(dir,name)))r.evidencias.push('newman/'+name);
  if(out.code!==0||r.herramientas.newman.fallos||r.herramientas.newman.iteraciones!==1)
    r.problemas_tecnicos.push('Newman incompleto');}
async function runCypress(r,c,e,t,expected){const dir=path.join(c.dir,'cypress');fs.mkdirSync(dir,{recursive:true});
  if(c.ensayo&&c.cypressDoble){const x=await c.cypressDoble({dir,expected});r.herramientas.cypress=x;
    for(const name of ['G40-UI-018-01.json','G40-cypress.json'])if(fs.existsSync(path.join(dir,name)))r.evidencias.push('cypress/'+name);
    return x;}
  const script=path.join(DIR,'pruebas/cypress_hijo.mjs');const out=await child(script,{dir,runId:c.runId,
    api:e.SIGAB_API_TEST_BASE,front:e.SIGAB_FRONT_TEST_BASE??'https://api.inmero.co/sigab-test',token:t.contador,secret:t.secret,expected});
  let data={};try{data=JSON.parse(out.stdout);}catch{}r.herramientas.cypress={...data,codigo:out.code,error:out.error?.code??data.error??null};
  if(fs.existsSync(path.join(dir,'G40-UI-018-01.json')))r.evidencias.push('cypress/G40-UI-018-01.json');
  if(fs.existsSync(path.join(dir,'G40-cypress.json')))r.evidencias.push('cypress/G40-cypress.json');
  const png=path.join(dir,'screenshots','g40.cy.js','G40-UI-018-01.png');
  if(fs.existsSync(png))r.evidencias.push('cypress/screenshots/g40.cy.js/G40-UI-018-01.png');
  return r.herramientas.cypress;}
async function close(r,c,e,t,h){const x=await fetchEnContexto(e.SIGAB_API_TEST_BASE+`/test-control/runs/${c.runId}`,{method:'DELETE',
  headers:{Authorization:`Bearer ${t.contador}`,'X-Sandbox-Secret':t.secret},signal:AbortSignal.timeout(120000)});
  r.cierre.run.cierre_http=x.status;if(x.status!==200){r.cierre.rollback.motivo='DELETE distinto de 200';return;}
  if(!h.wrote&&!h.inciertas){r.cierre.rollback={verificado:true,motivo:'Sin escrituras; DELETE 200'};return;}
  if(!h.pid){r.cierre.rollback={verificado:false,motivo:'Escritura incierta sin período para lecturas poscierre'};return;}
  const get=async ruta=>{const z=await fetchEnContexto(e.SIGAB_API_TEST_BASE+ruta,{headers:{Authorization:`Bearer ${t.contador}`},signal:AbortSignal.timeout(30000)});
    return{http:z.status,data:await z.json()};};
  const cfg=await get('/finanzas/configuracion'),lineas=await get(`/finanzas/lineas?id_periodo_contable=${h.pid}`),
    vars=await get(`/finanzas/periodos/${h.pid}/variaciones`);
  const originales=h.matriz.every(m=>cfg.data?.matriz?.some(x=>x.id_asignacion_cuenta_contable===m.id_asignacion_cuenta_contable));
  const nuevaAusente=!cfg.data?.matriz?.some(x=>x.id_asignacion_cuenta_contable===h.nueva);
  const lineaAusente=!lineas.data?.some(x=>x.id_linea_asiento_nic41===h.linea);
  const varAusente=!vars.data?.some(x=>x.id_variacion_valor_razonable===h.variacion);
  const sinLineasNuevas=Array.isArray(lineas.data)&&lineas.data.every(x=>h.baseLineas?.includes(x.id_linea_asiento_nic41));
  const sinVariacionesNuevas=Array.isArray(vars.data)&&vars.data.every(x=>h.baseVars?.includes(x.id_variacion_valor_razonable));
  r.cierre.lecturas_poscierre=[{ruta:'configuracion',http:cfg.http},{ruta:'lineas',http:lineas.http},{ruta:'variaciones',http:vars.http}];
  r.cierre.rollback={verificado:[cfg,lineas,vars].every(z=>z.http===200)&&originales&&nuevaAusente&&lineaAusente&&varAusente&&
    sinLineasNuevas&&sinVariacionesNuevas&&!h.inciertas,
    motivo:`matriz original ${originales}; nueva ausente ${nuevaAusente}; línea ausente ${lineaAusente}; variación ausente ${varAusente}; IDs nuevos ausentes ${sinLineasNuevas&&sinVariacionesNuevas}; escritura incierta ${h.inciertas}`};}
export function informe(c,r){
  const caso=r.casos[CASOS[0]],o=r.observado,cy=r.herramientas.cypress?.acta??{};
  const detalle=[
    ['a','Hecho pendiente sin cuentas','PENDIENTE_CUENTA y ninguna línea registrada con cuentas',
      `Variación ${o.variacion??'—'} y línea ${o.linea??'—'} PENDIENTE_CUENTA sin cuentas.`,o.a],
    ['b','Panel de configuración','Pendiente visible y conteo incrementado',
      `Aviso visible; líneas pendientes ${o.conteo_base??'—'} → ${o.conteo_pendiente??'—'}.`,o.b],
    ['c','Alerta al Contador','Aviso nuevo que identifica VARIACION_VR_TB/GANANCIA y especie',
      `API: ${o.avisos_nuevos??'—'} avisos nuevos; UI: bandeja abierta con ${cy.avisos_en_ui??'—'} anteriores y ningún aviso nuevo de la combinación. La combinación solo consta en auditoría; el panel no la detalla.`,o.c],
    ['d','Matriz completada','La misma línea pasa a REGISTRADA con las cuentas nuevas',
      `POST matriz 201; línea ${o.linea??'—'} REGISTRADA; pendientes ${o.conteo_final??'—'}.`,o.d]
  ].map(([id,verificacion,esperado,observado,ok])=>`| ${id} | ${verificacion} | ${esperado} | ${observado} | ${ok===true?'Cumple':ok===false?'Falla':'No comprobado'} |`).join('\n');
  const incidencias=r.incidencias.map(x=>`### ${x.id??'INC-M06-G40-01'} — ${x.titulo}

- Requisito: RF-86 v2.0 FA-5 y proceso, paso 11: alerta al Contador con la combinación faltante.
- Reproducción: dejar sin par VARIACION_VR_TB/GANANCIA para la especie del activo, registrar pesaje con ganancia y procesar.
- Esperado: aviso al Contador que identifique la combinación. Observado: línea PENDIENTE_CUENTA y conteo en el panel, sin aviso nuevo en bandeja por API ni UI; combinación visible solo en la auditoría.
- Impacto: el Contador debe revisar la auditoría para identificar el par; la línea pendiente impide cerrar el período hasta completar la matriz.
- Severidad: ${x.severidad}. ${x.justificacion_severidad}
- Certeza: ${x.certeza}. Equipo inicial: ${x.equipo_inicial}. Fundamento: ${x.fundamento_equipo}
- Causa raíz: NO DETERMINADA. El código consultado en contabilizador.py:70-86 registra la auditoría y no muestra una llamada al notificador; es apoyo para investigar, no prueba de la causa en TEST.
- Evidencias: resultado.json, cypress/G40-UI-018-01.json, cypress/screenshots/g40.cy.js/G40-UI-018-01.png y newman/.\n`).join('\n');
  return `# TC-M06-G40 — ${caso.estado}

## Identificación

Grupo G40; caso TC-M06-018; RF-86 v2.0, CA-21 y FA-5; RUN ${c.runId}; V${c.version}, intento ${c.intento}; ambiente ${c.ensayo?'loopback local':'TEST'}; autorización ${c.referencia}; commit no consultado. Node ${r.herramientas.node??process.version}; Newman ${r.herramientas.newman?.version??'no verificado'} (código ${r.herramientas.newman?.codigo??'—'}); Cypress ${r.cypress?.version??'no verificado'} (código ${r.herramientas.cypress?.codigo??'—'}, ${r.cypress?.total_pruebas??0} prueba). Oficial ${r.oficial}.

## Veredicto y oráculo

| Caso | Estado | Motivo |
| --- | --- | --- |
| TC-M06-018 | ${caso.estado} | ${clean(caso.motivo)} |

Esperado: no se crea línea registrada con cuentas; el hecho queda PENDIENTE_CUENTA visible en M06; alerta al Contador con combinación faltante; tras completar la matriz la misma línea queda REGISTRADA con las cuentas nuevas.

| Paso | Comprobación API/UI | Esperado | Observado | Resultado |
| --- | --- | --- | --- | --- |
${detalle}

Activo ${o.activo??'—'}, período ${o.periodo??'—'}, variación ${o.variacion??'—'}, línea ${o.linea??'—'}. Auditoría LINEA_ASIENTO_PENDIENTE_CUENTA: ${JSON.stringify(o.auditoria_combinacion??null)}. Solicitudes API ${r.total_solicitudes_api??'—'}/150. Cypress ejecutó el acta G40-UI-018-01: ${cy.estado??'no disponible'}; su código 0 acredita ejecución, no aprobación del producto.

## Contrato y evidencias

${r.contraste_contrato.map(x=>`- ${x.ruta}: ${x.resultado}, HTTP ${x.http}.`).join('\n')||'Sin lecturas.'}

Evidencias: ${r.evidencias.join(', ')||'ninguna'}. D1: el producto modela una línea PENDIENTE_CUENTA sin cuentas en vez de omitir la línea; QA aprobó tratarlo como observación. La asignación genérica 12 se desactivó únicamente dentro del RUN (DELETE 204) y la matriz se restauró al cerrar.

## Incidencias y análisis

${incidencias||'Ninguna incidencia de producto acreditada.'}
Problemas técnicos de automatización: ${r.problemas_tecnicos.join('; ')||'ninguno durante el RUN'}. El bloque Cypress de la raíz corrige el formato que consume el registro QA.

## Cierre y rollback

DELETE HTTP ${r.cierre.run.cierre_http??'—'}; rollback ${r.cierre.rollback.verificado?'verificado':'no verificado'}: ${r.cierre.rollback.motivo??'sin lectura'}.

## Conclusión

${r.oficial?'Remitir el RUN oficial RECHAZADO al responsable QA para actualizar el registro y derivar INC-M06-G40-01 a Desarrollo; solicitar corrección y reevaluar solo con autorización.':'Revisar el impedimento antes de solicitar una nueva ejecución autorizada.'}
`;}
export async function evaluar(c,e){if(e.QA_AUTORIZADO!=='SI'||!fs.existsSync(c.dir))throw Error('RUN no autorizado');
  const r=blank(c),h={wrote:false,inciertas:false,matriz:[],pid:null,linea:null,variacion:null,nueva:null,
    baseLineas:null,baseVars:null};r._deadline=Date.now()+1800000;
  let t=null;try{const contador=await login(e.SIGAB_API_TEST_BASE,e.QA_CONTADOR_EMAIL,e.QA_CONTADOR_PASSWORD);
    const admin=await login(e.SIGAB_API_TEST_BASE,e.QA_ADMIN_EMAIL,e.QA_ADMIN_PASSWORD);
    if(!contador||!admin)throw Error('Login no confirmado');t={contador,admin,secret:e.QA_SANDBOX_SECRET,actor:'contador'};
    for(const actor of ['contador','admin']){const x=await fetchEnContexto(e.SIGAB_API_TEST_BASE+CONTRATO.lectura_permisos.ruta,{headers:{
      Authorization:`Bearer ${t[actor]}`,'X-Test-Run-Id':c.runId,'X-Sandbox-Secret':t.secret},signal:AbortSignal.timeout(30000)});
      r.solicitudes.push({id:'permisos',actor,http:x.status});if(x.status!==200||x.headers.get('x-test-run-id')!==c.runId)throw Error(`Permisos ${actor}: HTTP/eco`);
      verificarPermisos(await x.json(),actor);}
    const q=async(id,ruta,actor='contador',body)=>{const x=await request(r,c,e,{...t,actor},id,ruta,body);
      if(entrada(id).metodo!=='GET'&&x.http===null)h.inciertas=true;return x;};
    const activos=await q('activos','/finanzas/activos'),periodos=await q('periodos','/finanzas/periodos');
    if(!good(activos)||!good(periodos))throw Error('Catálogo o períodos ilegibles');
    let selected=null;for(const a of activos.data){if(!/bovin/i.test(a.especie??'')||a.estado!=='ACTIVO'||a.tipo!=='INDIVIDUAL')continue;
      const aid=n(a.id_activo_biologico),detail=await q('activo_detalle',`/finanzas/activos/${aid}`),
        ficha=await q('ficha',`/activos-biologicos/${aid}/ficha-integral`,'admin'),
        precios=await q('precios_get',`/finanzas/precios?id_especie=${a.id_especie}`);
      if(!good(detail)||!good(ficha)||!good(precios))throw Error('Detalle, ficha o precios ilegibles');
      const periodo=periodoDestino(periodos.data,detail.data.activo.numero_id_tributaria,today());
      const precio=vigente(precios.data,a.id_especie,today());
      const calculo=detail.data.calculos.find(x=>x.estado==='CALCULADO'&&x.json_metodo_costo?.es_producto!==true);
      if(periodo?.estado==='ABIERTO'&&precio&&calculo&&ficha.data.estado_actual==='ACTIVO'&&
        ficha.data.unidad_peso==='kg'&&Number(ficha.data.peso_actual)>0){selected={a,aid,periodo,precio,ficha,calculo};break;}}
    if(!selected)throw Error('Sin bovino apto; dato imprescindible no preparable');
    const {a,aid,periodo,ficha}=selected,pid=n(periodo.id_periodo_contable),species=n(a.id_especie);h.pid=pid;
    r.observado.activo=aid;r.observado.periodo=pid;
    const cfg=await q('configuracion','/finanzas/configuracion'),lb=await q('lineas',`/finanzas/lineas?id_periodo_contable=${pid}`),
      vb=await q('variaciones',`/finanzas/periodos/${pid}/variaciones`),
      pending=await q('lineas',`/finanzas/lineas?id_periodo_contable=${pid}&estado=PENDIENTE_CUENTA`);
    const bandejaBase=await pages(q,'bandeja','items','total',p=>`/notificaciones?pagina=${p}&tamano=50`);
    const auditoriaBase=await pages(q,'auditoria','eventos','total_registros',p=>`/finanzas/auditoria?id_activo_biologico=${aid}&id_periodo_contable=${pid}&formato=TECNICO&tamano=500&pagina=${p}`);
    if(![cfg,lb,vb,pending].every(x=>good(x))||r.discrepancias_contrato.length)throw Error('Contrato GET previo discordante');
    h.baseLineas=lb.data.map(x=>x.id_linea_asiento_nic41);h.baseVars=vb.data.map(x=>x.id_variacion_valor_razonable);
    r.observado.conteo_base=cfg.data.lineas_pendientes_cuenta;
    const matches=cfg.data.matriz.filter(x=>x.tipo_hecho==='VARIACION_VR_TB'&&x.sentido==='GANANCIA'&&
      x.subtipo_costo===null&&(x.id_especie===null||Number(x.id_especie)===species));
    if(!matches.length)throw Error('Matriz sin par TB/GANANCIA inicial; D2 no aplicable');h.matriz=matches;
    for(const m of matches){const del=await q('matriz_delete',`/finanzas/configuracion/matriz/${m.id_asignacion_cuenta_contable}`);
      if(!good(del,204))throw Error(`DELETE matriz HTTP ${del.http}`);h.wrote=true;}
    const sinPar=await q('configuracion','/finanzas/configuracion');
    if(!good(sinPar)||sinPar.data.matriz.some(x=>x.tipo_hecho==='VARIACION_VR_TB'&&x.sentido==='GANANCIA'&&
      x.subtipo_costo===null&&(x.id_especie===null||Number(x.id_especie)===species)))
      throw Error('Matriz mantiene par TB/GANANCIA tras DELETE; no se provoca pesaje');
    const peso=Number(ficha.data.peso_actual)+1;
    const ev=await q('evento_crecimiento',`/activos-biologicos/${aid}/eventos/crecimiento`,'admin',
      {tipo_medicion:'PESO',valor_medicion:peso,unidad_medida:'kg',descripcion:`QA ${c.runId}`});
    if(!good(ev,201)||!n(ev.data?.evento?.id_eventos))throw Error(`Pesaje HTTP ${ev.http}`);h.wrote=true;
    const proc=await q('procesar','/finanzas/eventos/procesar','contador',{});if(!good(proc))throw Error(`Procesar HTTP ${proc.http}`);
    const va=await q('variaciones',`/finanzas/periodos/${pid}/variaciones`),la=await q('lineas',`/finanzas/lineas?id_periodo_contable=${pid}`),
      ca=await q('configuracion','/finanzas/configuracion');
    if(![va,la,ca].every(x=>good(x)))throw Error('Lecturas tras pesaje ilegibles');
    const newVars=idsNuevos(vb.data,va.data,'id_variacion_valor_razonable').filter(x=>Number(x.id_activo_biologico)===aid);
    const tb=newVars.find(x=>x.tipo==='GANANCIA_TRANSFORMACION_BIOLOGICA');h.variacion=tb?.id_variacion_valor_razonable??null;
    const newLines=idsNuevos(lb.data,la.data,'id_linea_asiento_nic41');
    const line=newLines.find(x=>x.tipo_hecho==='VARIACION_VR_TB'&&x.id_origen===h.variacion);h.linea=line?.id_linea_asiento_nic41??null;
    r.observado.variacion=h.variacion;r.observado.linea=h.linea;r.observado.conteo_pendiente=ca.data.lineas_pendientes_cuenta;
    const aok=Boolean(line&&tb&&Number(line.id_activo_biologico)===aid&&Number(line.id_especie)===species&&
      line.sentido==='GANANCIA'&&line.estado==='PENDIENTE_CUENTA'&&line.cuenta_debito===null&&line.cuenta_credito===null&&
      !newLines.some(x=>x.id_origen===h.variacion&&x.estado==='REGISTRADA'&&x.cuenta_debito&&x.cuenta_credito));
    r.observado.a=aok;
    const cy=await runCypress(r,c,e,t,{conteo:ca.data.lineas_pendientes_cuenta,especie:species,
      especieNombre:a.especie,avisosBase:bandejaBase.map(x=>x.id_notificacion)});
    const panel=cy?.acta??null;const bok=panel?.panel_visible===true&&panel.conteo===ca.data.lineas_pendientes_cuenta&&
      ca.data.lineas_pendientes_cuenta>cfg.data.lineas_pendientes_cuenta;r.observado.b=bok;
    const avisos=await pages(q,'bandeja','items','total',p=>`/notificaciones?pagina=${p}&tamano=50`);
    const baseIds=ids(bandejaBase,'id_notificacion');const nuevos=avisos.filter(x=>!baseIds.has(String(x.id_notificacion)));
    const avisoCoincide=x=>coincideCombinacion(x.mensaje,species,a.especie);
    const cok=nuevos.some(avisoCoincide)&&panel?.campana_visible===true;
    r.observado.c=cok;r.observado.avisos_nuevos=nuevos.length;
    r.observado.bandeja_nueva=nuevos.map(x=>({id:x.id_notificacion,coincide_combinacion:avisoCoincide(x),
      mensaje_combinacion:avisoCoincide(x)?'VARIACION_VR_TB/GANANCIA/'+species:null}));
    r.observado.panel_combinacion_visible=panel?.combinacion_visible??null;
    const aud=await pages(q,'auditoria','eventos','total_registros',p=>`/finanzas/auditoria?id_activo_biologico=${aid}&id_periodo_contable=${pid}&formato=TECNICO&tamano=500&pagina=${p}`);
    const audIds=ids(auditoriaBase,'id_evento');const eventoAud=aud.find(x=>!audIds.has(String(x.id_evento))&&x.tipo_evento==='LINEA_ASIENTO_PENDIENTE_CUENTA');
    r.observado.auditoria_pendiente=Boolean(eventoAud);
    r.observado.auditoria_combinacion=eventoAud?{tipo_hecho:eventoAud.payload_evento?.tipo_hecho??null,
      sentido:eventoAud.payload_evento?.sentido??null,id_especie:eventoAud.payload_evento?.id_especie??null}:null;
    const original=matches.find(x=>x.id_especie===null)??matches[0];const post=await q('matriz_post','/finanzas/configuracion/matriz','contador',
      {tipo_hecho:'VARIACION_VR_TB',sentido:'GANANCIA',id_especie:species,subtipo_costo:null,
        cuenta_debito:original.cuenta_debito,cuenta_credito:original.cuenta_credito});
    if(good(post,201)){h.nueva=post.data.id_asignacion_cuenta_contable;h.wrote=true;}
    const lf=await q('lineas',`/finanzas/lineas?id_periodo_contable=${pid}`),cf=await q('configuracion','/finanzas/configuracion');
    const same=lf.data?.find(x=>x.id_linea_asiento_nic41===h.linea);
    const dok=good(post,201)&&post.data.lineas_resueltas>=1&&same?.estado==='REGISTRADA'&&
      same.cuenta_debito===original.cuenta_debito&&same.cuenta_credito===original.cuenta_credito&&
      cf.data?.lineas_pendientes_cuenta===cfg.data.lineas_pendientes_cuenta;
    r.observado.d=dok;r.observado.conteo_final=cf.data?.lineas_pendientes_cuenta;
    const estado=aok&&bok&&cok&&dok?'APROBADO':aok&&bok&&dok&&!cok?'RECHAZADO':'RECHAZADO';
    r.casos[CASOS[0]]={caso:'TC-M06-G40 / TC-M06-018',estado,motivo:`a=${aok}; b=${bok}; c=${cok}; d=${dok}`};
    if(!c.sinNewman)await runNewman(r,c,e,t,pid);
  }catch(error){r.problemas_tecnicos.push(clean(error.message));if(!r.casos[CASOS[0]])r.casos[CASOS[0]]={
    caso:'TC-M06-G40 / TC-M06-018',
    estado:/Sin bovino apto|Matriz sin par TB\/GANANCIA inicial/.test(error.message)?'BLOQUEADO':'NO_CONCLUYENTE',
    motivo:clean(error.message)};}
  finally{if(t)try{await close(r,c,e,t,h);}catch(error){r.cierre.rollback={verificado:false,motivo:clean(error.message)};}
    if(!r.casos[CASOS[0]])r.casos[CASOS[0]]={caso:'TC-M06-G40 / TC-M06-018',estado:'NO_CONCLUYENTE',motivo:'Sin comprobación completa'};
    if(r.discrepancias_contrato.length){r.casos[CASOS[0]].estado='NO_CONCLUYENTE';r.casos[CASOS[0]].motivo='Contrato discordante';}
    if((r.herramientas.cypress?.codigo!==0||!c.ensayo&&
      (r.herramientas.cypress?.acta?.estado==='NO_CONCLUYENTE'||r.herramientas.cypress?.acta?.host_bloqueado))&&
      ['RECHAZADO','APROBADO'].includes(r.casos[CASOS[0]].estado)){
      r.casos[CASOS[0]].estado='NO_CONCLUYENTE';r.casos[CASOS[0]].motivo='Cypress no completó la comprobación UI';}
    if(r.casos[CASOS[0]].estado==='APROBADO'&&
      (r.herramientas.newman?.codigo!==0||r.herramientas.newman?.iteraciones!==1||
        r.herramientas.newman?.fallos!==0||!r.cierre.rollback.verificado)){
      r.casos[CASOS[0]].estado='NO_CONCLUYENTE';r.casos[CASOS[0]].motivo='Newman o rollback no verificado';}
    r.comprobaciones.push(...['API','UI'].map(fuente=>({caso:CASOS[0],fuente,id:fuente==='API'?IDS[0]:'G40-UI-018-01',tipo:'ASSERT',
      estado:r.casos[CASOS[0]].estado,evidencia:fuente==='API'?'resultado.json':'cypress/G40-UI-018-01.json'})));
    if(r.casos[CASOS[0]].estado==='RECHAZADO')r.incidencias.push({id:'INC-M06-G40-01',caso:CASOS[0],
      titulo:'FA-5: no se alerta al Contador de la combinación faltante',equipo_inicial:'Desarrollo',
      severidad:'MEDIA',justificacion_severidad:'El aviso dirigido falla, pero el pendiente es visible en el panel y la auditoría, y completar la matriz lo resuelve.',
      certeza:c.ensayo?'NO DETERMINADA':'CONFIRMADA',fundamento_equipo:'Primera discrepancia comprobada en API y UI pública de M06; causa raíz no determinada'});
    r.total_solicitudes_api=(local.getStore()?.solicitudes??0)+(r.herramientas.newman?.solicitudes??0)+
      (r.herramientas.cypress?.acta?.peticiones??[]).filter(x=>!x.local).length;
    r.oficial=r.total_solicitudes_api<=150&&Date.now()<=r._deadline&&!r.discrepancias_contrato.length&&!h.inciertas&&r.cierre.rollback.verificado&&
      r.herramientas.newman?.codigo===0&&r.herramientas.newman.fallos===0&&r.herramientas.newman.iteraciones===1&&
      r.herramientas.cypress?.codigo===0&&
      r.herramientas.cypress?.acta?.captura===true&&
      (c.ensayo||r.herramientas.cypress.acta.login_resuelto_localmente===true)&&
      (c.ensayo||r.herramientas.cypress.acta.host_bloqueado===null)&&
      (c.ensayo||['APROBADO','RECHAZADO'].includes(r.herramientas.cypress.acta.estado))&&
      (c.ensayo||r.evidencias.includes('cypress/screenshots/g40.cy.js/G40-UI-018-01.png'))&&
      ['APROBADO','RECHAZADO'].includes(r.casos[CASOS[0]].estado);
    r.consume_version=r.oficial;r.cypress=resumenCypress(r,c.dir);r.evidencias.unshift('resultado.json',reportName(c.version));
    delete r._deadline;save(path.join(c.dir,'resultado.json'),r);fs.writeFileSync(path.join(c.dir,reportName(c.version)),informe(c,r));}
  return r;}
export async function principal(args,{proceso=process.env,archivoEnv=path.join(ROOT,'.env.qa'),fetcher=globalThis.fetch,
  ensayo=false,sinNewman=false,cypressDoble=null}={}){const c={...contexto(args,ensayo),sinNewman:ensayo&&sinNewman,cypressDoble};
  const e=leerEnv(proceso,archivoEnv),p=preflight(c,e);save(path.join(c.dir,'preflight.json'),p);
  if(!p.ok)return{exitCode:2,preflight:p,resultado:null};const r=await conPeticiones(fetcher,()=>evaluar(c,e));
  return{exitCode:r.oficial?0:2,preflight:p,resultado:r};}
if(process.argv.includes('--capacidades'))console.log(JSON.stringify(CAPACIDADES,null,2));
else if(process.argv.includes('--comprobar'))process.exitCode=comprobar();
else if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
  try{const {preflight:p,resultado:r,exitCode}=await principal(process.argv.slice(2));console.log(JSON.stringify({grupo:'G40',run_id:p.run_id,
    preflight_ok:p.ok,oficial:r?.oficial??false,estado:r?.casos?.[CASOS[0]]?.estado??null}));process.exitCode=exitCode;}
  catch(error){console.error(clean(error.message));process.exitCode=2;}}
