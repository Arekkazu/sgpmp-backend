#!/usr/bin/env node
// TC-M03-184. Construcción local: node ejecutar_tc_m03_g93.mjs --validar-local
// Ejecución futura: --ejecutar --ambiente TEST --autorizacion REF --tipo evaluacion --aceptar-efectos notificacion-login
import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

export const GRUPO = 'TC-M03-G93';
export const CASOS = ['TC-M03-184'];
export const ASERCIONES = ['API-184-01', 'API-184-02', 'API-184-03', 'UI-184-01', 'UI-184-02'];
const DIR = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(DIR, '../../../../..');
const COLLECTION = path.join(DIR, `${GRUPO}.postman_collection.json`);
const SPEC = path.join(DIR, 'tc_m03_g93.cy.js');
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
export function candidatoSinSenal(dashboard) {
  const unidades = dashboard?.resumen_unidades ?? [];
  const sensores = dashboard?.sensores ?? [];
  return unidades.find(u => {
    const propios = sensores.filter(s => Number(s.id_infraestructura) === Number(u.id_infraestructura));
    return propios.length > 0 && propios.length === Number(u.total_sensores) && propios.every(s => s.estado_conectividad === 'SIN_SEÑAL');
  }) ?? null;
}
/** Consulta del testigo: INSERT del área en auditoria.logs_dml, identificado por id y nombre del RUN. */
export function consultaTestigoArea(id, nombre) {
  const n = Number(id);
  if (!Number.isSafeInteger(n) || n <= 0) throw Error('ID de área inválido para el testigo');
  if (!/^[A-Za-z0-9 _.:-]{1,80}$/.test(String(nombre))) throw Error('Nombre de área no apto para el testigo');
  return `SELECT count(*) AS n FROM auditoria.logs_dml WHERE esquema_afectado = 'modulo9' AND tabla_afectada = 'infraestructuras' AND tipo_operacion = 'INSERT' AND datos_nuevos->>'id_infraestructura' = '${n}' AND datos_nuevos->>'nombre' = '${nombre}'`;
}
/** /test-control/query responde {"data": [filas]}; null si no hubo respuesta válida (nunca se interpreta como 0). */
export function leerConteo(r) {
  if (r?.status !== 200 || !Array.isArray(r?.data?.data) || !r.data.data[0]) return null;
  const n = Number(r.data.data[0].n);
  return Number.isFinite(n) ? n : null;
}
/** Aislamiento demostrado solo con testigo visible dentro del RUN (1) e invisible fuera (0). */
export function evaluarAislamiento(dentro, fuera) {
  if (dentro === null || fuera === null) return { demostrado: false, motivo: `testigo no consultable (dentro=${dentro}, fuera=${fuera})` };
  if (dentro !== 1) return { demostrado: false, motivo: `el INSERT del área no consta dentro del RUN (n=${dentro})` };
  if (fuera !== 0) return { demostrado: false, motivo: `FUGA: el INSERT del área es visible fuera del RUN (n=${fuera})` };
  return { demostrado: true, motivo: 'visible dentro del RUN (1) e invisible desde otra transacción (0)' };
}
const secretos = (v, tokens=[]) => [v.QA_SANDBOX_SECRET, v.QA_COMMON_PASSWORD, v.QA_SETUP_PASSWORD, v.QA_PROD_PASSWORD, ...tokens].filter(Boolean);
export function limpiarTexto(x, valores=[]) {
  let t = String(x).replace(/eyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}/g, '[JWT]');
  for (const s of valores.filter(x => x.length >= 4)) t = t.split(s).join('[REDACTADO]');
  return t;
}
/**
 * Veredicto propuesto. Un fallo de entorno, de rollback, de precondición [PRE] o de un hook
 * de Cypress (login/sesión) bloquea; solo un criterio [ASSERT] incumplido con evidencia rechaza.
 */
export function veredicto(ev) {
  const nw=ev.resultados.find(x=>x.herramienta==='Newman');
  const cy=ev.resultados.find(x=>x.herramienta==='Cypress');
  if(ev.estado!=='CONCLUIDA'||!ev.sandbox.rollback)return 'BLOQUEADO';
  const asercionesApi=nw?.assertions??[];
  if(asercionesApi.some(x=>/\[PRE\]/.test(x.nombre)&&!x.ok))return 'BLOQUEADO';
  if(cy?.tests?.some(t=>t.estado==='failed'&&t.hook))return 'BLOQUEADO';
  const apiIncumplida=asercionesApi.some(x=>/\[ASSERT\]/.test(x.nombre)&&!x.ok);
  const uiIncumplida=(cy?.tests??[]).some(t=>t.estado==='failed'&&!t.hook&&/\[ASSERT\]/.test(t.titulo));
  if(apiIncumplida||uiIncumplida)return 'RECHAZADO';
  if(ev.bloqueos.length||!nw||!cy||nw.exit!==0||!cy.total||cy.skipped>0||!ASERCIONES.filter(x=>x.startsWith('API')).every(id=>asercionesApi.some(a=>a.nombre.includes(id))))return 'BLOQUEADO';
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
  check('matriz: TC-M03-184',CASOS.length===1&&CASOS[0]==='TC-M03-184');
  check('configuración compartida',fs.existsSync(ENV));
  check('barrera sin autorización',!autorizacion(v,{ambiente:'TEST',autorizacion:'',efectos:[]}).ok);
  for(const k of ['QA_SETUP_EMAIL','QA_PROD_EMAIL','QA_SANDBOX_SECRET'])check(`variable ${k}`,!!v[k]);
  check('contraseñas QA definidas',!!(v.QA_SETUP_PASSWORD||v.QA_COMMON_PASSWORD)&&!!(v.QA_PROD_PASSWORD||v.QA_COMMON_PASSWORD));
  check('destinos TEST coherentes',autorizacion({...v,QA_AUTORIZADO:'SI'},{ambiente:'TEST',autorizacion:'DEV-REFERENCIA',efectos:['notificacion-login']}).ok);
  check('QA_AUTORIZADO permanece NO en preparación',v.QA_AUTORIZADO==='NO');
  check('.env.qa ignorado por Git',spawnSync('git',['check-ignore','-q','.env.qa'],{cwd:ROOT}).status===0);
  for(const f of [fileURLToPath(import.meta.url),COLLECTION,SPEC,path.join(DIR,'validar_local_g93.mjs')]) check(`archivo ${path.basename(f)}`,fs.existsSync(f));
  for(const f of [fileURLToPath(import.meta.url),SPEC,path.join(DIR,'validar_local_g93.mjs')]) check(`sintaxis ${path.basename(f)}`,spawnSync(process.execPath,['--check',f]).status===0);
  let c;try{c=JSON.parse(fs.readFileSync(COLLECTION,'utf8'));}catch{};
  check('colección JSON válida',!!c?.item?.length);
  check('barrera propia de la colección Newman',JSON.stringify(c?.event??[]).includes('BLOQUEO_G93')&&JSON.stringify(c?.event??[]).includes('skipRequest'));
  check('testigo de aislamiento sin RLS (auditoria.logs_dml)',/auditoria\.logs_dml/.test(consultaTestigoArea(1,'QA G93 X'))&&!fs.readFileSync(fileURLToPath(import.meta.url),'utf8').includes(['FROM','modulo9.infraestructuras','WHERE'].join(' ')));
  check('pruebas unitarias locales',spawnSync(process.execPath,['--test',path.join(DIR,'validar_local_g93.mjs')]).status===0);
  // Incluye los scripts de nivel colección: una barrera con error de sintaxis dejaría pasar la petición.
  try{for(const event of [...(c.event??[]),...c.item.flatMap(item=>item.event??[])])new Function('pm',(event.script?.exec??[]).join('\n'));check('scripts Postman con sintaxis válida (colección y peticiones)',true);}catch{check('scripts Postman con sintaxis válida',false);}
  for(const id of ASERCIONES) check(`aserción ${id}`,JSON.stringify(c).includes(id)||fs.readFileSync(SPEC,'utf8').includes(id));
  try{moduloNewman();check('Newman API disponible',true);}catch{check('Newman API disponible',false);}
  try{createRequire(path.join(ROOT,'package.json'))('cypress');check('Cypress disponible',true);}catch{check('Cypress disponible',false);}
  check('sin secretos en scripts',[COLLECTION,SPEC,fileURLToPath(import.meta.url)].every(f=>limpiarTexto(fs.readFileSync(f,'utf8'),secretos(v))===fs.readFileSync(f,'utf8')));
  check('sin RESULTADOS durante construcción',!fs.existsSync(path.join(DIR,'RESULTADOS')));
  for(const [n,ok] of checks) console.log(`${ok?'OK':'FALLO'} ${n}`);
  console.log(`G93 local: ${checks.filter(x=>x[1]).length}/${checks.length}`);
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
  const runId=`G93-${version===1?'EVAL':'REEVAL'}-V${version}-${sello}`;
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
  // Testigo de aislamiento: el INSERT del área en auditoria.logs_dml (trigger trg_auditoria,
  // fn_auditoria_dml SECURITY DEFINER, sin condiciones; el esquema auditoria no tiene RLS).
  // modulo9.infraestructuras tiene RLS y desde una transacción sin identidad devolvería 0
  // siempre, sin probar nada. null = no verificable (HTTP != 200 o respuesta sin fila).
  async function testigoArea(run,id,nombre){
    const r=await req('POST','/test-control/query',{run,cuerpo:{query:consultaTestigoArea(id,nombre)}});
    return {n:leerConteo(r),http:r.status};
  }
  async function cerrar(){if(!abierto)return;abierto=false;const r=await req('DELETE',`/test-control/runs/${runId}`,{control:true});ev.sandbox.cierre=r.status;const r2=await req('DELETE',`/test-control/runs/${runId}`,{control:true});ev.sandbox.rollback=r.status===200&&r2.status===404;
    if(ev.datos?.id_infraestructura){const s=`${runId}-POST`;try{const t=await testigoArea(s,ev.datos.id_infraestructura,ev.datos.nombre_infraestructura);ev.sandbox.sonda_posterior=t;ev.sandbox.rollback=ev.sandbox.rollback&&t.n===0;if(t.n===null)ev.bloqueos.push(`Rollback no confirmable: el testigo auditoria.logs_dml no fue consultable (HTTP ${t.http}).`);}finally{await req('DELETE',`/test-control/runs/${s}`,{control:true});}}
  }
  try{
    const health=await req('GET','/health',{externo:true});need(health,200,'health');
    const openapi=need(await req('GET','/openapi.json',{externo:true}),200,'OpenAPI');
    const paths=openapi.paths??{};
    for(const p of ['/sesiones/','/usuarios/me','/configuracion/infraestructuras','/iot/monitoreo/dashboard/{id_infraestructura}','/test-control/query','/test-control/runs/{run_id}'])if(!paths[p])throw Error(`Falta contrato ${p}`);
    const probe=await req('DELETE',`/test-control/runs/${runId}-PREFLIGHT`,{control:true});if(probe.status!==404)throw Error(`Sandbox no verificable: HTTP ${probe.status}`);
    abierto=true;
    async function login(rol){const email=v[`QA_${rol}_EMAIL`];const pass=v[`QA_${rol}_PASSWORD`]||v.QA_COMMON_PASSWORD;const d=need(await req('POST','/sesiones/',{cuerpo:{correo_electronico:email,contrasena:pass}}),200,`login ${rol}`);if(!d.token)throw Error(`Sin token ${rol}`);tok.push(d.token);return {token:d.token,me:await get('/usuarios/me',d.token)};}
    const setup=await login('SETUP');const prod=await login('PROD');if(!/productor/i.test(prod.me.nombre_rol??''))throw Error('QA_PROD_EMAIL no es Productor');
    ev.fase='PREPARACION';
    const fincasS=await get('/configuracion/fincas',setup.token),fincasP=await get('/configuracion/fincas',prod.token);
    const comunes=(fincasS.items??[]).filter(f=>(fincasP.items??[]).some(p=>p.id_finca===f.id_finca));
    let finca=comunes[0]?.id_finca;
    if(!finca){const nueva=await post('/configuracion/fincas',{nombre:`QA Monitoreo G93 ${sello}`.replace(/\d/g,d=>'abcdefghij'[Number(d)]),ubicacion:{departamento:'Huila',municipio:'Neiva',vereda:'QA',latitud:2.9273,longitud:-75.2819},tamano_h:1,id_usuario:prod.me.id_usuario},setup.token);finca=nueva.id_finca;}
    const tipos=await get('/configuracion/tipos-area?solo_activos=true',setup.token);
    const tipo=(tipos.items??[]).find(x=>x.es_activo);if(!tipo)throw Error('Sin tipo de área activo');
    const especies=await get('/configuracion/especies?solo_activas=true',setup.token);const especie=(especies.items??[]).find(x=>x.es_activo);if(!especie)throw Error('Sin especie activa');
    const nombre=`QA G93 ${runId}`;
    const area=await post('/configuracion/infraestructuras',{nombre_infraestructura:nombre,tipo_area:tipo.nombre,superficie:25,finca_id:finca,descripcion_infraestructura:`QA ${runId}`,especie_id:especie.id_especie},setup.token);
    const id=area.id_infraestructura;if(!Number.isInteger(Number(id)))throw Error('Área sin ID');
    need(await req('GET',`/configuracion/infraestructuras/${id}`,{token:prod.token}),200,'Acceso Productor al área');
    ev.datos={id_infraestructura:id,nombre_infraestructura:nombre};
    const dentro=await testigoArea(runId,id,nombre);const fueraRun=`${runId}-SONDA`;let fuera;try{fuera=await testigoArea(fueraRun,id,nombre);}finally{await req('DELETE',`/test-control/runs/${fueraRun}`,{control:true});}
    ev.sandbox.aislamiento={testigo:'auditoria.logs_dml (INSERT del área)',dentro,fuera};
    const ais=evaluarAislamiento(dentro.n,fuera.n);if(!ais.demostrado)throw Error(`Aislamiento no demostrado: ${ais.motivo}`);
    // Segunda variante de la fila: descubrimiento de unidad accesible cuyos TODOS los sensores están SIN_SEÑAL.
    // Se consulta en todas las páginas; no se altera ninguna entidad ajena.
    const primero=await get('/iot/monitoreo/dashboard?pagina=1&por_pagina=50',prod.token);
    const pages=Math.max(1,Math.ceil(Number(primero.total||0)/50));const sensores=[...(primero.sensores??[])];
    for(let p=2;p<=pages;p++)sensores.push(...((await get(`/iot/monitoreo/dashboard?pagina=${p}&por_pagina=50`,prod.token)).sensores??[]));
    const segunda=candidatoSinSenal({...primero,sensores});
    if(!segunda)ev.bloqueos.push('Variante de unidad con todos los sensores SIN_SEÑAL: no se descubrió un fixture accesible; el contrato no ofrece transición aislada ni se fuerza por SQL.');
    ev.datos.segunda_unidad=segunda?.id_infraestructura??null;
    ev.fase='ESCENARIOS';guardar();
    const vars={autorizado_run:'SI',base_url:api,run_id:runId,sandbox_secret:v.QA_SANDBOX_SECRET,token:prod.token,id_unidad:String(id),nombre_unidad:nombre,id_segunda:String(segunda?.id_infraestructura??'')};
    const resultado=await new Promise(resolve=>newman.run({ ignoreRedirects: true, collection:JSON.parse(fs.readFileSync(COLLECTION,'utf8')),environment:{values:Object.entries(vars).map(([key,value])=>({key,value}))},reporters:[],silent:true},(error,summary)=>resolve({error,summary})));
    const rep=resultado.summary;
    ev.resultados.push({herramienta:'Newman',exit:resultado.error||rep?.run?.failures?.length?1:0,assertions:(rep?.run?.executions??[]).flatMap(e=>(e.assertions??[]).map(x=>({nombre:x.assertion,ok:!x.error,error:x.error?.message}))),error:resultado.error?limpiarTexto(resultado.error.message,sec()):null});
    delete process.env.ELECTRON_RUN_AS_NODE;
    const cy=await cypress.run({project:DIR,configFile:path.join(DIR,'cypress.config.cjs'),testingType:'e2e',browser:'electron',headless:true,quiet:true,reporter:'spec',config:{e2e:{baseUrl:aut.front,supportFile:false,fixturesFolder:false,video:false,screenshotOnRunFailure:false,screenshotsFolder:path.join(out,'capturas'),downloadsFolder:path.join(out,'descargas'),trashAssetsBeforeRuns:false,specPattern:path.basename(SPEC),testIsolation:false,retries:0,reporter:'spec'}},spec:SPEC,env:{AUTORIZADO_RUN:'SI',API_BASE:api,RUN_ID:runId,SANDBOX_SECRET:v.QA_SANDBOX_SECRET,PROD_EMAIL:v.QA_PROD_EMAIL,PROD_PASSWORD:v.QA_PROD_PASSWORD||v.QA_COMMON_PASSWORD,ID_UNIDAD:id,NOMBRE_UNIDAD:nombre,ID_SEGUNDA:segunda?.id_infraestructura??''}});
    if(cy?.status==='failed')throw Error(`Cypress no pudo ejecutarse: ${limpiarTexto(cy.message??'',sec())}`);
    // Un fallo en el hook before (login/sesión) no es evidencia del producto: se marca para bloquear.
    const pruebas=(cy.runs??[]).flatMap(r=>r.tests??[]).map(t=>{const err=String(t.displayError??'');return {titulo:Array.isArray(t.title)?t.title.at(-1):String(t.title),estado:t.state,hook:/before all|before each|after all|after each/i.test(err),error:err?limpiarTexto(err.split(/\r?\n/)[0],sec()):undefined};});
    ev.resultados.push({herramienta:'Cypress',total:cy.totalTests,passed:cy.totalPassed,failed:cy.totalFailed,skipped:cy.totalSkipped,tests:pruebas});
    ev.estado='CONCLUIDA';
  }catch(e){ev.estado=ev.fase==='ESCENARIOS'?'INTERRUMPIDA':'ABORTADA_PREFLIGHT';ev.bloqueos.push(limpiarTexto(e.stack??e.message,sec()));}
  finally{try{await cerrar();}catch(e){ev.bloqueos.push(`Cierre sandbox: ${limpiarTexto(e.message,sec())}`);}ev.fin=new Date().toISOString();ev.veredicto=veredicto(ev);guardar();fs.writeFileSync(path.join(out,version===1?`${GRUPO}_resultado.md`:`${GRUPO}_reevaluacion_V${version}.md`),limpiarTexto(`# ${GRUPO} — ${CASOS[0]}\n\nEstado técnico: ${ev.estado}. Resultado: ${ev.veredicto}.\n\nSandbox: ${ev.sandbox.rollback?'rollback confirmado':'rollback NO confirmado'}\n\nAserciones: ${JSON.stringify(ev.resultados)}\n\nBloqueos: ${ev.bloqueos.join('; ')||'ninguno'}\n`,sec()));globalThis.fetch=async()=>{throw Error('BLOQUEO_RED');};}
  console.log(`G93 ${ev.estado}; ${out}`);return ev.estado==='CONCLUIDA'?0:4;
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
  let code;try{const a=argumentos(process.argv.slice(2));code=a.modo==='local'?comprobarLocal():await ejecutar(a);}catch(e){console.error(e.message);code=2;}process.exitCode=code;
}
