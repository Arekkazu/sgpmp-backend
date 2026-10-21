#!/usr/bin/env node
// TC-M03-185. Construcción local: node ejecutar_tc_m03_g94.mjs --validar-local
// Ejecución futura: --ejecutar --ambiente TEST --autorizacion REF --tipo evaluacion --aceptar-efectos notificacion-login
import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

export const GRUPO = 'TC-M03-G94';
export const CASOS = ['TC-M03-185'];
export const ASERCIONES = ['API-185-01', 'API-185-02', 'UI-185-01', 'UI-185-02'];
const DIR = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(DIR, '../../../../..');
const COLLECTION = path.join(DIR, `${GRUPO}.postman_collection.json`);
const SPEC = path.join(DIR, 'tc_m03_g94.cy.js');
const ENV = path.join(ROOT, '.env.qa');
const originalFetch = globalThis.fetch;
globalThis.fetch = async () => { throw Error('BLOQUEO_RED'); };

export function leerEnv(texto, entorno = {}) {
  const v = {};
  for (const linea of texto.split(/\r?\n/)) {
    const m = linea.match(/^\s*([A-Z][A-Z0-9_]*)\s*=\s*(.*)$/);
    if (m) v[m[1]] = m[2].trim().replace(/^(['"])(.*)\1$/, '$2');
  }
  return { ...v, ...Object.fromEntries(Object.entries(entorno).filter(([k, x]) => k in v && x !== '')) };
}
export function autorizacion(v, a) {
  const motivos = [];
  if (v.QA_AUTORIZADO !== 'SI') motivos.push('QA_AUTORIZADO debe ser SI');
  if (a.ambiente !== 'TEST') motivos.push('Solo TEST');
  if (!a.autorizacion || a.autorizacion.trim().length < 8) motivos.push('Falta referencia de autorización de Desarrollo');
  if (!a.efectos.includes('notificacion-login')) motivos.push('Falta aceptar notificacion-login');
  for (const k of ['QA_SETUP_EMAIL', 'QA_PROD_EMAIL', 'QA_SANDBOX_SECRET']) if (!v[k]) motivos.push(`Falta ${k}`);
  for (const r of ['SETUP', 'PROD']) if (!(v[`QA_${r}_PASSWORD`] || v.QA_COMMON_PASSWORD)) motivos.push(`Falta contraseña ${r}`);
  const api = v.SIGAB_API_TEST_BASE || v.SIGAB_API_BASE;
  const front = v.SIGAB_FRONT_TEST_URL || v.SIGAB_FRONT_URL;
  if(!v.SIGAB_API_TEST_BASE||!v.SIGAB_FRONT_TEST_URL)motivos.push('Se requieren destinos canónicos TEST en .env.qa');
  for (const [n, url, alias] of [['API', api, v.SIGAB_API_BASE], ['Front', front, v.SIGAB_FRONT_URL]]) {
    if (!/^https:\/\//i.test(url || '') || /(^|[-/.])dev([-/.]|$)/i.test(url || '')) motivos.push(`${n} debe ser HTTPS TEST`);
    if (alias && url?.replace(/\/+$/, '') !== alias.replace(/\/+$/, '')) motivos.push(`${n} canónica y alias difieren`);
  }
  if (api && api === v.SIGAB_API_DEV_BASE) motivos.push('API coincide con DEV');
  if (front && front === v.SIGAB_FRONT_DEV_URL) motivos.push('Front coincide con DEV');
  if (api?.replace(/\/+$/, '') !== 'https://www.api.inmero.co/api-sgpmp-test') motivos.push('API no coincide con la URL oficial de TEST');
  if (front?.replace(/\/+$/, '') !== 'https://api.inmero.co/sigab-test') motivos.push('Front no coincide con la URL oficial de TEST');
  return { ok: motivos.length === 0, motivos, api: api?.replace(/\/+$/, ''), front: front?.replace(/\/+$/, '') };
}
export function versionSiguiente(dir, tipo, confirmada) {
  const versiones = [1, ...fs.readdirSync(dir, { withFileTypes: true }).filter(x => x.isDirectory()).map(x => /^EvaluacionV(\d+)$/.exec(x.name)?.[1]).filter(Boolean).map(Number)].sort((a,b)=>a-b);
  const ultima = versiones.at(-1);
  const runs = (n) => { const d = n === 1 ? path.join(dir,'RESULTADOS') : path.join(dir,`EvaluacionV${n}`,'RESULTADOS'); return fs.existsSync(d) ? fs.readdirSync(d).filter(x => fs.statSync(path.join(d,x)).isDirectory()).map(x => { try { return JSON.parse(fs.readFileSync(path.join(d,x,'evidencia.json'),'utf8')).estado; } catch { return 'INCIERTO'; } }) : []; };
  const actual = runs(ultima);
  const candidato = tipo === 'reintento' ? (actual.length ? ultima : null) : !actual.length ? ultima : actual.includes('CONCLUIDA') ? ultima+1 : actual.every(x => x === 'ABORTADA_PREFLIGHT') ? ultima : null;
  if (!candidato || (confirmada && Number(confirmada) !== candidato)) throw Error('Historial ambiguo o versión solicitada incoherente; requiere decisión QA');
  return candidato;
}
export function ceroAsignaciones(rows, id) {
  return Array.isArray(rows) && rows.length === 1 && Number(rows[0].n) === 0 && Number.isInteger(Number(id)) && Number(id)>0;
}
const secretos = (v, tokens=[]) => [v.QA_SANDBOX_SECRET, v.QA_COMMON_PASSWORD, v.QA_SETUP_PASSWORD, v.QA_PROD_PASSWORD, ...tokens].filter(Boolean);
export function limpiarTexto(x, valores=[]) {
  let t = String(x).replace(/eyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}/g, '[JWT]');
  for (const s of valores.filter(x => x.length >= 4)) t = t.split(s).join('[REDACTADO]');
  return t;
}
export function veredicto(ev) {
  const nw=ev.resultados.find(x=>x.herramienta==='Newman');
  const cy=ev.resultados.find(x=>x.herramienta==='Cypress');
  if(nw?.assertions?.some(x=>!x.ok)||cy?.failed>0)return 'RECHAZADO';
  if(ev.estado!=='CONCLUIDA'||ev.bloqueos.length||!ev.sandbox.rollback||!nw||!cy||nw.exit!==0||!cy.total||cy.skipped>0||!ASERCIONES.filter(x=>x.startsWith('API')).every(id=>nw.assertions?.some(a=>a.nombre.includes(id))))return 'BLOQUEADO';
  return 'APROBADO';
}
function argumentos(argv) {
  const a = { modo: 'local', efectos: [] };
  for(let i=0;i<argv.length;i++) { const x=argv[i]; if(x==='--ejecutar') a.modo='ejecutar'; else if(x==='--validar-local') a.modo='local'; else if(x==='--ambiente') a.ambiente=argv[++i]; else if(x==='--autorizacion') a.autorizacion=argv[++i]; else if(x==='--tipo') a.tipo=argv[++i]; else if(x==='--version') a.version=argv[++i]; else if(x==='--aceptar-efectos') a.efectos.push(...String(argv[++i]||'').split(',')); else throw Error(`Argumento desconocido ${x}`); }
  return a;
}
function moduloNewman() {
  const root=spawnSync('npm',['root','-g'],{shell:process.platform==='win32',encoding:'utf8'});
  if(root.status!==0)throw Error('No se localizó npm global para Newman');
  const req=createRequire(path.join(ROOT,'package.json'));
  const modulo=req(path.join(root.stdout.trim(),'newman'));
  if(typeof modulo.run!=='function')throw Error('Módulo Newman sin API run');
  return modulo;
}
function comprobarLocal() {
  const checks=[]; const check=(n,x)=>checks.push([n,Boolean(x)]);
  const v=fs.existsSync(ENV)?leerEnv(fs.readFileSync(ENV,'utf8'),process.env):{};
  check('matriz: TC-M03-185',CASOS.length===1&&CASOS[0]==='TC-M03-185');
  check('configuración compartida',fs.existsSync(ENV));
  check('barrera sin autorización',!autorizacion(v,{ambiente:'TEST',autorizacion:'',efectos:[]}).ok);
  for(const k of ['QA_SETUP_EMAIL','QA_PROD_EMAIL','QA_SANDBOX_SECRET'])check(`variable ${k}`,!!v[k]);
  check('contraseñas QA definidas',!!(v.QA_SETUP_PASSWORD||v.QA_COMMON_PASSWORD)&&!!(v.QA_PROD_PASSWORD||v.QA_COMMON_PASSWORD));
  check('destinos TEST coherentes',autorizacion({...v,QA_AUTORIZADO:'SI'},{ambiente:'TEST',autorizacion:'DEV-REFERENCIA',efectos:['notificacion-login']}).ok);
  check('QA_AUTORIZADO permanece NO en preparación',v.QA_AUTORIZADO==='NO');
  check('.env.qa ignorado por Git',spawnSync('git',['check-ignore','-q','.env.qa'],{cwd:ROOT}).status===0);
  for(const f of [fileURLToPath(import.meta.url),COLLECTION,SPEC,path.join(DIR,'validar_local_g94.mjs')]) check(`archivo ${path.basename(f)}`,fs.existsSync(f));
  for(const f of [fileURLToPath(import.meta.url),SPEC,path.join(DIR,'validar_local_g94.mjs')]) check(`sintaxis ${path.basename(f)}`,spawnSync(process.execPath,['--check',f]).status===0);
  let c;try{c=JSON.parse(fs.readFileSync(COLLECTION,'utf8'));}catch{};
  check('colección JSON válida',!!c?.item?.length);
  try{for(const item of c.item)for(const event of item.event??[])new Function((event.script?.exec??[]).join('\n'));check('scripts Postman con sintaxis válida',true);}catch{check('scripts Postman con sintaxis válida',false);}
  for(const id of ASERCIONES) check(`aserción ${id}`,JSON.stringify(c).includes(id)||fs.readFileSync(SPEC,'utf8').includes(id));
  try{moduloNewman();check('Newman API disponible',true);}catch{check('Newman API disponible',false);}
  try{createRequire(path.join(ROOT,'package.json'))('cypress');check('Cypress disponible',true);}catch{check('Cypress disponible',false);}
  check('sin secretos en scripts',[COLLECTION,SPEC,fileURLToPath(import.meta.url)].every(f=>limpiarTexto(fs.readFileSync(f,'utf8'),secretos(v))===fs.readFileSync(f,'utf8')));
  check('sin RESULTADOS durante construcción',!fs.existsSync(path.join(DIR,'RESULTADOS')));
  for(const [n,ok] of checks) console.log(`${ok?'OK':'FALLO'} ${n}`);
  console.log(`G94 local: ${checks.filter(x=>x[1]).length}/${checks.length}`);
  return checks.every(x=>x[1])?0:1;
}
async function ejecutar(a) {
  const v=fs.existsSync(ENV)?leerEnv(fs.readFileSync(ENV,'utf8'),process.env):{};
  const aut=autorizacion(v,a);
  if(!aut.ok){console.error(`EJECUCIÓN NO AUTORIZADA: ${aut.motivos.join('; ')}`);return 2;}
  if(!['evaluacion','reintento'].includes(a.tipo)){console.error('Indique --tipo evaluacion|reintento');return 2;}
  let version;try{version=versionSiguiente(DIR,a.tipo,a.version);}catch(e){console.error(e.message);return 3;}
  const require=createRequire(path.join(ROOT,'package.json'));
  let cypress;try{cypress=require('cypress');}catch{console.error('Cypress no disponible');return 3;}
  let newman;try{newman=moduloNewman();}catch(e){console.error(e.message);return 3;}
  const sello=new Date().toISOString().replace(/[-:TZ.]/g,'').slice(0,14);
  const runId=`G94-${version===1?'EVAL':'REEVAL'}-V${version}-${sello}`;
  const base=version===1?path.join(DIR,'RESULTADOS'):path.join(DIR,`EvaluacionV${version}`,'RESULTADOS');
  const out=path.join(base,runId);fs.mkdirSync(base,{recursive:true});fs.mkdirSync(out);
  const ev={grupo:GRUPO,rf:'RF-58',cu:'CU04',casos:CASOS,run_id:runId,version,estado:'EN_CURSO',fase:'PREFLIGHT',autorizacion:a.autorizacion,resultados:[],bloqueos:[],sandbox:{},inicio:new Date().toISOString()};
  const tok=[];const sec=()=>secretos(v,tok); const guardar=()=>fs.writeFileSync(path.join(out,'evidencia.json'),limpiarTexto(JSON.stringify(ev,null,2),sec()));
  const api=aut.api;let abierto=false;globalThis.fetch=originalFetch;
  async function req(method,ruta,{token,cuerpo,run=runId,control=false,externo=false}={}){
    const headers={Accept:'application/json'};if(cuerpo!==undefined) headers['Content-Type']='application/json';if(token)headers.Authorization=`Bearer ${token}`;if(!externo){headers['X-Sandbox-Secret']=v.QA_SANDBOX_SECRET;if(!control)headers['X-Test-Run-Id']=run;}
    const resp=await originalFetch(`${api}${ruta}`,{method,headers,body:cuerpo===undefined?undefined:JSON.stringify(cuerpo),redirect: 'manual', signal:AbortSignal.timeout(30000)});
    const data=await resp.json().catch(()=>null);const eco=resp.headers.get('x-test-run-id');
    if(!externo&&!control&&eco!==run)throw Error(`Sandbox sin eco en ${method} ${ruta} (HTTP ${resp.status})`);
    return {status:resp.status,data,eco};
  }
  const need=(r,s,label)=>{if(r.status!==s)throw Error(`${label}: HTTP ${r.status}`);return r.data;};
  const get=async(r,t)=>need(await req('GET',r,{token:t}),200,r);
  const post=async(r,c,t)=>need(await req('POST',r,{token:t,cuerpo:c}),201,r);
  async function query(run,q){const r=await req('POST','/test-control/query',{run,cuerpo:{query:q}});return need(r,200,'consulta de aislamiento').data;}
  async function cerrar(){if(!abierto)return;abierto=false;const r=await req('DELETE',`/test-control/runs/${runId}`,{control:true});ev.sandbox.cierre=r.status;const r2=await req('DELETE',`/test-control/runs/${runId}`,{control:true});ev.sandbox.rollback=r.status===200&&r2.status===404;
    if(ev.datos?.id_usuario){const s=`${runId}-POST`;try{const rows=await query(s,`SELECT count(*) AS n FROM modulo9.usuarios_fincas WHERE id_usuario = ${Number(ev.datos.id_usuario)} AND es_activo IS TRUE`);ev.sandbox.rollback=ev.sandbox.rollback&&Number(rows?.[0]?.n)===Number(ev.datos.fincas_anteriores);ev.sandbox.sonda_posterior=Number(rows?.[0]?.n);}finally{await req('DELETE',`/test-control/runs/${s}`,{control:true});}}
  }
  try{
    const health=await req('GET','/health',{externo:true});need(health,200,'health');
    const openapi=need(await req('GET','/openapi.json',{externo:true}),200,'OpenAPI');
    const paths=openapi.paths??{};
    for(const p of ['/sesiones/','/usuarios/me','/usuarios/{id_usuario}/fincas','/configuracion/fincas','/iot/monitoreo/dashboard','/test-control/query','/test-control/runs/{run_id}'])if(!paths[p])throw Error(`Falta contrato ${p}`);
    const probe=await req('DELETE',`/test-control/runs/${runId}-PREFLIGHT`,{control:true});if(probe.status!==404)throw Error(`Sandbox no verificable: HTTP ${probe.status}`);
    abierto=true;
    async function login(rol){const email=v[`QA_${rol}_EMAIL`];const pass=v[`QA_${rol}_PASSWORD`]||v.QA_COMMON_PASSWORD;const d=need(await req('POST','/sesiones/',{cuerpo:{correo_electronico:email,contrasena:pass}}),200,`login ${rol}`);if(!d.token)throw Error(`Sin token ${rol}`);tok.push(d.token);return {token:d.token,me:await get('/usuarios/me',d.token)};}
    const setup=await login('SETUP');const prod=await login('PROD');if(!/productor/i.test(prod.me.nombre_rol??''))throw Error('QA_PROD_EMAIL no es Productor');
    ev.fase='PREPARACION';
    const id=Number(prod.me.id_usuario);
    if(!Number.isInteger(id)||id<=0)throw Error('ID del Productor QA inválido');
    const q=`SELECT count(*) AS n FROM modulo9.usuarios_fincas WHERE id_usuario = ${id} AND es_activo IS TRUE`;
    const antes=await query(runId,q);
    const fueraRun=`${runId}-SONDA`;
    const afueraAntes=await query(fueraRun,q);
    if(Number(antes?.[0]?.n)!==Number(afueraAntes?.[0]?.n))throw Error('Asignaciones iniciales no coinciden entre sandbox y sonda');
    const anteriores=await get('/configuracion/fincas',prod.token);
    if(!Array.isArray(anteriores.items))throw Error('No se puede verificar alcance de fincas del Productor QA');
    if(Number(antes[0].n)>0){
      need(await req('PUT',`/usuarios/${id}/fincas`,{token:setup.token,cuerpo:{ids_fincas:[]}}),200,'Preparar usuario QA sin fincas');
    }
    const dentro=await query(runId,q);
    const afuera=await query(fueraRun,q);
    if(!ceroAsignaciones(dentro,id)||Number(afuera?.[0]?.n)!==Number(afueraAntes?.[0]?.n))throw Error('No se demostró aislamiento de la desasignación QA');
    const fincasAhora=await get('/configuracion/fincas',prod.token);
    if(!Array.isArray(fincasAhora.items)||fincasAhora.items.length!==0)throw Error('La cuenta QA todavía tiene fincas visibles; precondición no preparada');
    const cierreSonda=await req('DELETE',`/test-control/runs/${fueraRun}`,{control:true});
    if(cierreSonda.status!==200)throw Error('No se cerró la sonda de aislamiento');
    ev.sandbox.aislamiento={antes:Number(antes[0].n),dentro:0,fuera:Number(afuera[0].n)};
    ev.datos={id_usuario:id,fincas_anteriores:Number(antes[0].n),fincas_durante_run:0};
    ev.fase='ESCENARIOS';guardar();
    const vars={base_url:api,run_id:runId,sandbox_secret:v.QA_SANDBOX_SECRET,token:prod.token};
    const resultado=await new Promise(resolve=>newman.run({ ignoreRedirects: true, collection:JSON.parse(fs.readFileSync(COLLECTION,'utf8')),environment:{values:Object.entries(vars).map(([key,value])=>({key,value}))},reporters:[],silent:true},(error,summary)=>resolve({error,summary})));
    const rep=resultado.summary;
    ev.resultados.push({herramienta:'Newman',exit:resultado.error||rep?.run?.failures?.length?1:0,assertions:(rep?.run?.executions??[]).flatMap(e=>(e.assertions??[]).map(x=>({nombre:x.assertion,ok:!x.error,error:x.error?.message}))),error:resultado.error?limpiarTexto(resultado.error.message,sec()):null});
    delete process.env.ELECTRON_RUN_AS_NODE;
    const cy=await cypress.run({project:DIR,configFile:path.join(DIR,'cypress.config.cjs'),testingType:'e2e',browser:'electron',headless:true,quiet:true,reporter:'spec',config:{e2e:{baseUrl:aut.front,supportFile:false,fixturesFolder:false,video:false,screenshotOnRunFailure:false,screenshotsFolder:path.join(out,'capturas'),downloadsFolder:path.join(out,'descargas'),trashAssetsBeforeRuns:false,specPattern:path.basename(SPEC),testIsolation:false,retries:0,reporter:'spec'}},spec:SPEC,env:{AUTORIZADO_RUN:'SI',API_BASE:api,RUN_ID:runId,SANDBOX_SECRET:v.QA_SANDBOX_SECRET,PROD_EMAIL:v.QA_PROD_EMAIL,PROD_PASSWORD:v.QA_PROD_PASSWORD||v.QA_COMMON_PASSWORD}});
    ev.resultados.push({herramienta:'Cypress',total:cy.totalTests,passed:cy.totalPassed,failed:cy.totalFailed,skipped:cy.totalSkipped,errores:(cy.runs??[]).flatMap(r=>(r.tests??[]).flatMap(t=>(t.attempts??[]).flatMap(a=>(a.errors??[]).map(e=>limpiarTexto(e.message,sec())))))});
    ev.estado='CONCLUIDA';
  }catch(e){ev.estado=ev.fase==='ESCENARIOS'?'INTERRUMPIDA':'ABORTADA_PREFLIGHT';ev.bloqueos.push(limpiarTexto(e.stack??e.message,sec()));}
  finally{try{await cerrar();}catch(e){ev.bloqueos.push(`Cierre sandbox: ${limpiarTexto(e.message,sec())}`);}ev.fin=new Date().toISOString();ev.veredicto=veredicto(ev);guardar();fs.writeFileSync(path.join(out,version===1?`${GRUPO}_resultado.md`:`${GRUPO}_reevaluacion_V${version}.md`),limpiarTexto(`# ${GRUPO} — ${CASOS[0]}\n\nEstado técnico: ${ev.estado}. Resultado: ${ev.veredicto}.\n\nSandbox: ${ev.sandbox.rollback?'rollback confirmado':'rollback NO confirmado'}\n\nAserciones: ${JSON.stringify(ev.resultados)}\n\nBloqueos: ${ev.bloqueos.join('; ')||'ninguno'}\n`,sec()));globalThis.fetch=async()=>{throw Error('BLOQUEO_RED');};}
  console.log(`G94 ${ev.estado}; ${out}`);return ev.estado==='CONCLUIDA'?0:4;
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
  let code;try{const a=argumentos(process.argv.slice(2));code=a.modo==='local'?comprobarLocal():await ejecutar(a);}catch(e){console.error(e.message);code=2;}process.exitCode=code;
}
