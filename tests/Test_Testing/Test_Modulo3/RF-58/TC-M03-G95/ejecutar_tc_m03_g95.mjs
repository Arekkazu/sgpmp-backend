#!/usr/bin/env node
// TC-M03-186. Construcción local: node ejecutar_tc_m03_g95.mjs --validar-local
// Ejecución futura: --ejecutar --ambiente TEST --autorizacion REF --tipo evaluacion --aceptar-efectos notificacion-login
import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

export const GRUPO = 'TC-M03-G95';
export const CASOS = ['TC-M03-186'];
export const ASERCIONES = ['UI-186-01', 'UI-186-02', 'UI-186-03', 'UI-186-04'];
const DIR = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(DIR, '../../../../..');
const SPEC = path.join(DIR, 'tc_m03_g95.cy.js');
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
  for (const k of ['QA_PROD_EMAIL', 'QA_SANDBOX_SECRET']) if (!v[k]) motivos.push(`Falta ${k}`);
  if (!(v.QA_PROD_PASSWORD || v.QA_COMMON_PASSWORD)) motivos.push('Falta contraseña PROD');
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
export function capacidadExpiracion(expiraJwtSeg, setCookie, maxEsperaMin) {
  const cookie=String(setCookie||'').split(/,(?=\s*[^;,=]+=)/).find(x=>/^\s*refresh_token=/.test(x))||'';
  const match=/(?:^|;\s*)Max-Age=(\d+)/i.exec(cookie);
  const jwt=Number(expiraJwtSeg), refresco=Number(match?.[1]), max=Number(maxEsperaMin)*60;
  const espera=Math.max(jwt,refresco)+90;
  return {verificable:Number.isFinite(jwt)&&jwt>0&&Number.isFinite(refresco)&&refresco>0&&refresco<=jwt&&Number.isFinite(max)&&max>=2&&espera<=max,
    jwt_seg:Number.isFinite(jwt)?jwt:null,refresco_seg:Number.isFinite(refresco)?refresco:null,espera_seg:Number.isFinite(espera)?espera:null};
}
const secretos = (v, tokens=[]) => [v.QA_SANDBOX_SECRET, v.QA_COMMON_PASSWORD, v.QA_SETUP_PASSWORD, v.QA_PROD_PASSWORD, ...tokens].filter(Boolean);
export function limpiarTexto(x, valores=[]) {
  let t = String(x).replace(/eyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}/g, '[JWT]');
  for (const s of valores.filter(x => x.length >= 4)) t = t.split(s).join('[REDACTADO]');
  return t;
}
export function veredicto(ev) {
  const cy=ev.resultados.find(x=>x.herramienta==='Cypress');
  if(cy?.failed>0)return 'RECHAZADO';
  if(ev.estado!=='CONCLUIDA'||ev.bloqueos.length||!ev.sandbox.rollback||!cy||!cy.total||cy.skipped>0)return 'BLOQUEADO';
  return 'APROBADO';
}
function argumentos(argv) {
  const a = { modo: 'local', efectos: [], maxEsperaMin:20 };
  for(let i=0;i<argv.length;i++) { const x=argv[i]; if(x==='--ejecutar') a.modo='ejecutar'; else if(x==='--validar-local') a.modo='local'; else if(x==='--ambiente') a.ambiente=argv[++i]; else if(x==='--autorizacion') a.autorizacion=argv[++i]; else if(x==='--tipo') a.tipo=argv[++i]; else if(x==='--version') a.version=argv[++i]; else if(x==='--max-espera-min') a.maxEsperaMin=Number(argv[++i]); else if(x==='--aceptar-efectos') a.efectos.push(...String(argv[++i]||'').split(',')); else throw Error(`Argumento desconocido ${x}`); }
  return a;
}
function comprobarLocal() {
  const checks=[]; const check=(n,x)=>checks.push([n,Boolean(x)]);
  const v=fs.existsSync(ENV)?leerEnv(fs.readFileSync(ENV,'utf8'),process.env):{};
  check('matriz: TC-M03-186',CASOS.length===1&&CASOS[0]==='TC-M03-186');
  check('configuración compartida',fs.existsSync(ENV));
  check('barrera sin autorización',!autorizacion(v,{ambiente:'TEST',autorizacion:'',efectos:[]}).ok);
  for(const k of ['QA_PROD_EMAIL','QA_SANDBOX_SECRET'])check(`variable ${k}`,!!v[k]);
  check('contraseña QA definida',!!(v.QA_PROD_PASSWORD||v.QA_COMMON_PASSWORD));
  check('destinos TEST coherentes',autorizacion({...v,QA_AUTORIZADO:'SI'},{ambiente:'TEST',autorizacion:'DEV-REFERENCIA',efectos:['notificacion-login']}).ok);
  check('QA_AUTORIZADO permanece NO en preparación',v.QA_AUTORIZADO==='NO');
  check('.env.qa ignorado por Git',spawnSync('git',['check-ignore','-q','.env.qa'],{cwd:ROOT}).status===0);
  for(const f of [fileURLToPath(import.meta.url),SPEC,path.join(DIR,'validar_local_g95.mjs')]) check(`archivo ${path.basename(f)}`,fs.existsSync(f));
  for(const f of [fileURLToPath(import.meta.url),SPEC,path.join(DIR,'validar_local_g95.mjs')]) check(`sintaxis ${path.basename(f)}`,spawnSync(process.execPath,['--check',f]).status===0);
  for(const id of ASERCIONES) check(`aserción ${id}`,fs.readFileSync(SPEC,'utf8').includes(id));
  check('comprobación real de expiración',capacidadExpiracion(40,'refresh_token=x; Max-Age=30',3).verificable&&!capacidadExpiracion(30,'refresh_token=x; Max-Age=40',3).verificable);
  try{createRequire(path.join(ROOT,'package.json'))('cypress');check('Cypress disponible',true);}catch{check('Cypress disponible',false);}
  check('sin secretos en scripts',[SPEC,fileURLToPath(import.meta.url)].every(f=>limpiarTexto(fs.readFileSync(f,'utf8'),secretos(v))===fs.readFileSync(f,'utf8')));
  check('sin RESULTADOS durante construcción',!fs.existsSync(path.join(DIR,'RESULTADOS')));
  for(const [n,ok] of checks) console.log(`${ok?'OK':'FALLO'} ${n}`);
  console.log(`G95 local: ${checks.filter(x=>x[1]).length}/${checks.length}`);
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
  const sello=new Date().toISOString().replace(/[-:TZ.]/g,'').slice(0,14);
  const runId=`G95-${version===1?'EVAL':'REEVAL'}-V${version}-${sello}`;
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
    return {status:resp.status,data,eco,setCookie:resp.headers.get('set-cookie')};
  }
  const need=(r,s,label)=>{if(r.status!==s)throw Error(`${label}: HTTP ${r.status}`);return r.data;};
  const get=async(r,t)=>need(await req('GET',r,{token:t}),200,r);
  async function cerrar(){if(!abierto)return;abierto=false;const r=await req('DELETE',`/test-control/runs/${runId}`,{control:true});ev.sandbox.cierre=r.status;const r2=await req('DELETE',`/test-control/runs/${runId}`,{control:true});ev.sandbox.rollback=r.status===200&&r2.status===404;}
  try{
    const health=await req('GET','/health',{externo:true});need(health,200,'health');
    const openapi=need(await req('GET','/openapi.json',{externo:true}),200,'OpenAPI');
    const paths=openapi.paths??{};
    for(const p of ['/sesiones/','/sesiones/refresh','/usuarios/me','/iot/monitoreo/dashboard','/test-control/runs/{run_id}'])if(!paths[p])throw Error(`Falta contrato ${p}`);
    const probe=await req('DELETE',`/test-control/runs/${runId}-PREFLIGHT`,{control:true});if(probe.status!==404)throw Error(`Sandbox no verificable: HTTP ${probe.status}`);
    abierto=true;
    const lr=await req('POST','/sesiones/',{cuerpo:{correo_electronico:v.QA_PROD_EMAIL,contrasena:v.QA_PROD_PASSWORD||v.QA_COMMON_PASSWORD}});
    const login=need(lr,200,'login QA Productor');if(!login.token)throw Error('Sin token QA');tok.push(login.token);
    const me=await get('/usuarios/me',login.token);if(!/productor/i.test(me.nombre_rol??''))throw Error('QA_PROD_EMAIL no es Productor');
    const inicial=await get('/iot/monitoreo/dashboard?por_pagina=50',login.token);
    const sensor=(inicial.sensores??[]).find(s=>s.ultimo_valor!==null);
    if(!(inicial.resumen_unidades??[]).length||!sensor)throw Error('No hay unidad con lectura visible para mantener monitoreo activo');
    ev.datos={unidad_inicial:sensor.id_infraestructura,sensor_inicial:sensor.id_sensor,sensores_iniciales:inicial.total};
    const cap=capacidadExpiracion(login.expira_en,lr.setCookie,a.maxEsperaMin);
    ev.preflight_expiracion=cap;guardar();
    if(!cap.verificable){ev.estado='ABORTADA_PREFLIGHT';ev.bloqueos.push(`La expiración natural no es verificable en ${a.maxEsperaMin} min (JWT ${cap.jwt_seg??'?'} s, refresh ${cap.refresco_seg??'?'} s). La cookie debe vencer antes que el JWT: si sigue vigente al vencer el JWT, el frontend renueva ambos. No existe reloj ni disparador oficial aislado; no se sustituye por logout/revocación.`);return 4;}
    ev.fase='ESCENARIOS';guardar();
    delete process.env.ELECTRON_RUN_AS_NODE;
    const cy=await cypress.run({project:DIR,configFile:path.join(DIR,'cypress.config.cjs'),testingType:'e2e',browser:'electron',headless:true,quiet:true,reporter:'spec',config:{e2e:{baseUrl:aut.front,supportFile:false,fixturesFolder:false,video:false,screenshotOnRunFailure:false,screenshotsFolder:path.join(out,'capturas'),downloadsFolder:path.join(out,'descargas'),trashAssetsBeforeRuns:false,specPattern:path.basename(SPEC),testIsolation:false,retries:0,defaultCommandTimeout:15000,reporter:'spec'}},spec:SPEC,env:{AUTORIZADO_RUN:'SI',API_BASE:api,RUN_ID:runId,SANDBOX_SECRET:v.QA_SANDBOX_SECRET,PROD_EMAIL:v.QA_PROD_EMAIL,PROD_PASSWORD:v.QA_PROD_PASSWORD||v.QA_COMMON_PASSWORD,MAX_ESPERA_MS:a.maxEsperaMin*60000,ID_UNIDAD:sensor.id_infraestructura,ID_SENSOR:sensor.id_sensor}});
    ev.resultados.push({herramienta:'Cypress',total:cy.totalTests,passed:cy.totalPassed,failed:cy.totalFailed,skipped:cy.totalSkipped,errores:(cy.runs??[]).flatMap(r=>(r.tests??[]).flatMap(t=>(t.attempts??[]).flatMap(a=>(a.errors??[]).map(e=>limpiarTexto(e.message,sec())))))});
    ev.estado='CONCLUIDA';
  }catch(e){ev.estado=ev.fase==='ESCENARIOS'?'INTERRUMPIDA':'ABORTADA_PREFLIGHT';ev.bloqueos.push(limpiarTexto(e.stack??e.message,sec()));}
  finally{try{await cerrar();}catch(e){ev.bloqueos.push(`Cierre sandbox: ${limpiarTexto(e.message,sec())}`);}ev.fin=new Date().toISOString();ev.veredicto=veredicto(ev);guardar();fs.writeFileSync(path.join(out,version===1?`${GRUPO}_resultado.md`:`${GRUPO}_reevaluacion_V${version}.md`),limpiarTexto(`# ${GRUPO} — ${CASOS[0]}\n\nEstado técnico: ${ev.estado}. Resultado: ${ev.veredicto}.\n\nSandbox: ${ev.sandbox.rollback?'rollback confirmado':'rollback NO confirmado'}\n\nAserciones: ${JSON.stringify(ev.resultados)}\n\nBloqueos: ${ev.bloqueos.join('; ')||'ninguno'}\n`,sec()));globalThis.fetch=async()=>{throw Error('BLOQUEO_RED');};}
  console.log(`G95 ${ev.estado}; ${out}`);return ev.estado==='CONCLUIDA'?0:4;
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
  let code;try{const a=argumentos(process.argv.slice(2));code=a.modo==='local'?comprobarLocal():await ejecutar(a);}catch(e){console.error(e.message);code=2;}process.exitCode=code;
}
