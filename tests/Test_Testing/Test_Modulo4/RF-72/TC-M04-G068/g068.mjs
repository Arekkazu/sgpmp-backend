#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import { randomUUID } from 'node:crypto';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { CASOS, IDS, PRESUPUESTO, CAPACIDADES, usuarioDelToken, tipoModelo, seleccionar, decidir } from './lib/g068_core.mjs';

const DIR = path.dirname(fileURLToPath(import.meta.url));
const RAIZ = path.resolve(DIR, '../../../../..');
const require = createRequire(import.meta.url);
const API = 'https://www.api.inmero.co/api-sgpmp-test';
const COLECCION_RUTA = path.join(DIR, 'G068.postman_collection.json');
const COLECCION = (() => { try { return JSON.parse(fs.readFileSync(COLECCION_RUTA, 'utf8')); } catch { return null; } })();
const POST = '/prediccion/retroalimentacion';
const INFORME = v => v === 1 ? 'TC-M04-G068_resultado.md' : `TC-M04-G068_reevaluacion_V${v}.md`;
const corto = x => String(x ?? '').replace(/[\r\n|]/g, ' ');
const fecha = d => new Intl.DateTimeFormat('en-CA', { timeZone:'America/Bogota', year:'numeric', month:'2-digit', day:'2-digit' }).format(new Date(d));
const rutaHistorial = (id, inicio, fin, cursor) => `/prediccion/historial/${id}?fecha_inicio=${inicio}&fecha_fin=${fin}${cursor ? `&cursor_paginacion=${encodeURIComponent(cursor)}` : ''}`;
const guardar = (f,x) => fs.writeFileSync(f, JSON.stringify(x,null,2),'utf8');
const NOMBRES=['G068-210','G068-211','G068-211-REEMPLAZO','G068-BAJA-VET','G068-BAJA-ADMIN','G068-ESTADO-BAJA','G068-BITACORA-BAJA','G068-245'];
const coleccionValida = c => c?.item?.length === NOMBRES.length
  && c.item.every((x,i)=>x.name===NOMBRES[i]&&x.request?.method===(i===5||i===6?'GET':'POST'))
  && c.item[3].request.url.includes('/activos-biologicos/885/eventos/baja')
  && c.item[6].request.url.includes('tipo_evento=BAJA_REGISTRADA');
function paqueteNewman() {
  try { return path.dirname(require.resolve('newman/package.json', { paths: [RAIZ] })); }
  catch { const rutas = [process.execPath, ...String(process.env.PATH ?? '').split(path.delimiter)];
    return rutas.map(x => path.join(path.dirname(x),'node_modules','newman','package.json'))
      .find(fs.existsSync)?.replace(/[\\/]package\.json$/,'') ?? null; }
}
function versionNewman() {
  const inicio=Date.now();
  try { const dir=paqueteNewman(); const version=require(path.join(dir,'package.json')).version;
    if (!/^\d+\.\d+\.\d+/.test(version) || Date.now()-inicio>30000) throw Error('VERSION_INVALIDA');
    return {ok:true,version,duracion_ms:Date.now()-inicio,limite_ms:30000}; }
  catch { return {ok:false,error:'NEWMAN_NO_DISPONIBLE',limite_ms:30000}; }
}
const sanear = (v, secretos) => {
  let s=String(v); for (const secreto of secretos.filter(x => typeof x === 'string' && x.length>=4)) s=s.split(secreto).join('[REDACTADO]');
  return s.replace(/eyJ[\w-]{5,}\.[\w-]{5,}\.[\w-]{5,}/g,'[JWT_REDACTADO]')
    .replace(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/gi,'[CORREO_REDACTADO]');
};
const escaparHtml = x => String(x).replace(/[&<>"']/g,y=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[y]));
export function leerEnv(proceso=process.env,archivo=path.join(RAIZ,'.env.qa')) {
  const env={};
  if(fs.existsSync(archivo)) for(const linea of fs.readFileSync(archivo,'utf8').split(/\r?\n/)) {
    const m=linea.match(/^\s*([A-Z][A-Z0-9_]*)\s*=(.*)$/);
    if(m) env[m[1]]=m[2].trim().replace(/^(['"])(.*)\1$/,'$2');
  }
  Object.assign(env,proceso); env.QA_AUTORIZADO=proceso.QA_AUTORIZADO; return env;
}
export function comprobar() {
  const archivos=['g068.mjs','lib/g068_core.mjs','G068.postman_collection.json','pruebas/g068_ensayo.mjs','pruebas/g068_env.test.mjs','pruebas/registro_qa.mjs','README.md'];
  const faltantes=archivos.filter(x=>!fs.existsSync(path.join(DIR,x)));
  const markdownSuperior=fs.existsSync(path.join(DIR,'Resultados')) && fs.readdirSync(path.join(DIR,'Resultados')).some(x=>x.endsWith('.md'));
  const newman=versionNewman(), coleccion=coleccionValida(COLECCION);
  const ok=!faltantes.length && !markdownSuperior && newman.ok && coleccion;
  console.log(JSON.stringify({grupo:'G068',ok,faltantes,coleccion,markdownSuperior,presupuesto:PRESUPUESTO,newman}));
  return ok?0:2;
}
function contexto(args) {
  const v=k=>args.includes(k)?args[args.indexOf(k)+1]:undefined;
  const operacion=v('--operacion'),version=Number(v('--version')),intento=Number(v('--intento'));
  const runId=v('--run-id'),referencia=v('--autorizacion'),archivo=v('--contexto');
  if(!CAPACIDADES.operaciones.includes(operacion)||!Number.isInteger(version)||version<1
    ||!Number.isInteger(intento)||intento<1||!referencia||!archivo
    ||!new RegExp(`^RUN-G068-V${version}-\\d{8}-\\d{6}$`).test(runId??'')) throw Error('Contexto de ejecución incompleto');
  const destino=path.join(DIR,...(version===1?['Resultados',runId]:[`EvaluacionV${version}`,'Resultados',runId]));
  const ruta=path.resolve(archivo);
  if(path.dirname(ruta)!==destino||!(operacion==='recuperar'?/^recuperacion-\d{14}\.contexto\.json$/.test(path.basename(ruta)):path.basename(ruta)==='contexto_operacion.json')) throw Error('Contexto fuera del RUN canónico');
  const c=JSON.parse(fs.readFileSync(ruta,'utf8'));
  if(c.grupo!=='G068'||c.run_id!==runId||c.version!==version||c.intento!==intento||c.operacion!==operacion.toUpperCase()
    ||c.referencia!==referencia||JSON.stringify(c.casos)!==JSON.stringify(CASOS)
    ||(operacion==='reevaluar'&&(version<2||c.version_anterior!==version-1||!c.alcance_reevaluacion))
    ||(operacion==='recuperar'&&v('--run-objetivo')!==runId)) throw Error('Contexto incoherente');
  return {operacion,version,intento,runId,referencia,directorio:destino,ensayo:false};
}
function preflight(c,env,newman=versionNewman()) {
  const base=String(env.SIGAB_API_TEST_BASE??'').replace(/\/+$/,'');
  const barreras=['SIGAB_API_TEST_BASE','QA_SANDBOX_SECRET','QA_VETERINARIO_EMAIL','QA_COMMON_PASSWORD'].filter(k=>!String(env[k]??'').trim());
  if(env.QA_AUTORIZADO!=='SI') barreras.push('QA_AUTORIZADO');
  if(!coleccionValida(COLECCION)) barreras.push('COLECCION_INVALIDA');
  if(!newman.ok) barreras.push('NEWMAN_NO_DISPONIBLE');
  if(c.ensayo?!/^http:\/\/(127\.0\.0\.1|localhost):\d+$/.test(base):base!==API) barreras.push('API_NO_CANONICA');
  return {grupo:'G068',run_id:c.runId,ok:!barreras.length,barreras,presupuesto:PRESUPUESTO,
    herramientas:{newman},efectos:['login Veterinario y, si está configurado, Administrador',
      'lecturas de descubrimiento, historial y auditoría','tres intentos de retroalimentación y posible reemplazo de 211',
      'baja temporal RF-45 del activo 885: evento, cierre de fase, histórico BAJA y BAJA_REGISTRADA',
      'DELETE sandbox siempre','copia condicional de BAJA_REGISTRADA en buffer local RF-52 si falla BD o hay alta carga',
      'lecturas poscierre, posible HISTORIAL_CONSULTADO fuera del sandbox']};
}
function resumenCuerpo(p,b) {
  if(!b||typeof b!=='object') return null;
  if(p.startsWith('/sesiones/')) return {token_recibido:!!b.token};
  if(p===POST) return {id_retroalimentacion:b.id_retroalimentacion??null,id_resultado_inferencia:b.id_resultado_inferencia??null,
    error_code:b.error_code??null,mensaje:corto(b.message??''),detalle_campo:corto(b.fields?.[0]?.message??'')};
  if(p.startsWith('/activos-biologicos/')) return {id_activo_biologico:b.id_activo_biologico??null,id_estado:b.id_estado??null,
    fase:b.fase_actual??b.id_fase_actual??null,error_code:b.error_code??null};
  return {total:b.total??b.total_registros??null,registros:b.registros?.length??null,eventos:b.eventos?.length??null,items:b.items?.length??null,error_code:b.error_code??null};
}
async function pedir(r,api,metodo,endpoint,{token,secreto,runId,cuerpo,caso,timeout=PRESUPUESTO.timeout_ms}={}) {
  if(r.solicitudes.length>=PRESUPUESTO.solicitudes_totales&&metodo!=='DELETE') throw Error('PRESUPUESTO_AGOTADO');
  const fila={caso:caso??null,metodo,ruta:endpoint.split('?')[0],http:null};r.solicitudes.push(fila);
  const inicio=Date.now();
  try {
    if(inicio>=r._limite&&metodo!=='DELETE') throw Error('DURACION_EXCEDIDA');
    const x=await fetch(api+endpoint,{method:metodo,redirect:'manual',headers:{
      ...(cuerpo?{'Content-Type':'application/json'}:{}),...(token?{Authorization:`Bearer ${token}`}:{}),
      ...(secreto?{'X-Sandbox-Secret':secreto}:{}),...(runId?{'X-Test-Run-Id':runId,'X-Zona-Horaria':'UTC'}:{})},
      body:cuerpo?JSON.stringify(cuerpo):undefined,
      signal:AbortSignal.timeout(metodo==='DELETE'?timeout:Math.max(1,Math.min(timeout,r._limite-inicio)))});
    const b=await x.json().catch(()=>null);
    Object.assign(fila,{http:x.status,eco:runId?x.headers.get('x-test-run-id')===runId:null,duracion_ms:Date.now()-inicio,
      respuesta:resumenCuerpo(endpoint.split('?')[0],b)});
    r._consecutivos5xx=x.status>=500?r._consecutivos5xx+1:0;
    return {http:x.status,cuerpo:b,eco:fila.eco};
  } catch(e) { Object.assign(fila,{tipo_fallo:['TimeoutError','AbortError'].includes(e.name)?'TIMEOUT':'SIN_RED',duracion_ms:Date.now()-inicio});
    return {http:null,cuerpo:null,eco:false}; }
}
async function pedirNewmanUnico(r,c,api,env,token,adminToken,cuerpos) {
  const coleccion=structuredClone(COLECCION);
  const comun=(admin=false, baja=false)=>[
    {key:'Authorization',value:`Bearer {{${admin?'token_admin':'token_veterinario'}}}`},
    {key:'X-Test-Run-Id',value:'{{run_id}}'},{key:'X-Sandbox-Secret',value:'{{sandbox_secret}}'},
    {key:'X-Zona-Horaria',value:baja?'America/Bogota':'UTC'},
    {key:'Content-Type',value:'application/json'}];
  const proximo={
    'G068-210':`postman.setNextRequest(pm.environment.get('hay_211')==='SI'?'G068-211':pm.environment.get('hay_245')==='SI'?'G068-BAJA-VET':null);`,
    'G068-211':`let b={};try{b=pm.response.json()}catch{};const reemplazar=['RETROALIMENTACION_DUPLICADA','FUERA_DE_VENTANA_TEMPORAL'].includes(b.error_code)&&pm.environment.get('hay_reemplazo')==='SI';postman.setNextRequest(reemplazar?'G068-211-REEMPLAZO':pm.environment.get('hay_245')==='SI'?'G068-BAJA-VET':null);`,
    'G068-211-REEMPLAZO':`postman.setNextRequest(pm.environment.get('hay_245')==='SI'?'G068-BAJA-VET':null);`,
    'G068-BAJA-VET':`postman.setNextRequest(pm.response.code===201?'G068-ESTADO-BAJA':pm.response.code===403&&pm.environment.get('token_admin')?'G068-BAJA-ADMIN':null);`,
    'G068-BAJA-ADMIN':`postman.setNextRequest(pm.response.code===201?'G068-ESTADO-BAJA':null);`,
    'G068-ESTADO-BAJA':`let b={};try{b=pm.response.json()}catch{};postman.setNextRequest(pm.response.code===200&&String(b.nombre_estado||b.estado_actual||b.id_estado).toUpperCase()==='BAJA'?'G068-BITACORA-BAJA':null);`,
    'G068-BITACORA-BAJA':`postman.setNextRequest('G068-245');`,
    'G068-245':`postman.setNextRequest(null);`};
  for(const item of coleccion.item) {
    const baja=item.name.startsWith('G068-BAJA');
    item.request.header=comun(item.name==='G068-BAJA-ADMIN'||item.name==='G068-BITACORA-BAJA'&&!!adminToken,baja);
    item.event=[{listen:'test',script:{type:'text/javascript',exec:[
      proximo[item.name],
      `const n=pm.response.code>=500?Number(pm.environment.get('consecutivos_5xx')||0)+1:0;pm.environment.set('consecutivos_5xx',String(n));`,
      `if((pm.response.code===403&&/clave|secreto|sandbox/i.test(pm.response.text()))||n>=3)postman.setNextRequest(null);`,
      `pm.test('HTTP recibido',()=>pm.expect(pm.response.code).to.be.above(0));`,
      `pm.test('Eco de RUN',()=>pm.expect(pm.response.headers.get('X-Test-Run-Id')).to.eql(pm.environment.get('run_id')));`
    ]}}];
  }
  const values=Object.entries({base_url:api,token_veterinario:token,token_admin:adminToken??'',run_id:c.runId,
    sandbox_secret:env.QA_SANDBOX_SECRET,cuerpo_210:JSON.stringify(cuerpos.c210),
    cuerpo_211:JSON.stringify(cuerpos.c211),cuerpo_211_reemplazo:JSON.stringify(cuerpos.reemplazo??cuerpos.c211),
    cuerpo_baja:JSON.stringify(cuerpos.baja),cuerpo_245:JSON.stringify(cuerpos.c245??cuerpos.c211),
    inicio_baja:cuerpos.inicioBaja,
    hay_211:cuerpos.c211?'SI':'NO',hay_reemplazo:cuerpos.reemplazo?'SI':'NO',
    hay_245:cuerpos.c245?'SI':'NO',consecutivos_5xx:'0'})
    .map(([key,value])=>({key,value,enabled:true}));
  const plazo=Math.max(1,r._limite-Date.now());
  let error,summary;
  try {[error,summary]=await new Promise(resolve=>require(paqueteNewman()).run({collection:coleccion,
    environment:{values},reporters:['cli'],silent:true,timeoutRequest:PRESUPUESTO.timeout_ms,
    timeout:plazo,ignoreRedirects:true,color:'off'},(e,s)=>resolve([e,s])));}
  catch(e){error=e;}
  const ejecuciones={};const reporte={herramienta:'Newman',version:r.herramientas.newman.version,
    solicitudes:[],error:error?.message??null,fallos:(summary?.run?.failures??[]).map(f=>({tipo:f.error?.name??'Error',mensaje:f.error?.message??null}))};
  let consecutivos5xx=0;
  for(const ex of summary?.run?.executions??[]) {
    const nombre=ex.item?.name??'DESCONOCIDO';const metodo=ex.request?.method??null;
    const ruta=nombre.startsWith('G068-BAJA')?'/activos-biologicos/885/eventos/baja':
      nombre==='G068-ESTADO-BAJA'?'/activos-biologicos/885':nombre==='G068-BITACORA-BAJA'?'/activos-biologicos/auditoria':POST;
    let cuerpo=null;try{cuerpo=JSON.parse(ex.response.stream.toString('utf8'))}catch{}
    const http=ex.response?.code??null;
    consecutivos5xx=http>=500?consecutivos5xx+1:0;
    if(consecutivos5xx===3) r.problemas_tecnicos.push('TRES_5XX_CONSECUTIVOS en Newman');
    if(http===403&&/clave|secreto|sandbox/i.test(String(cuerpo?.message??cuerpo?.detail??'')))
      r.problemas_tecnicos.push('CLAVE_403 en Newman');
    const eco=ex.response?.headers?.get?.('x-test-run-id')===c.runId
      ||ex.response?.header?.find?.(h=>String(h.key).toLowerCase()==='x-test-run-id')?.value===c.runId;
    const caso=nombre.includes('210')?CASOS[0]:nombre.includes('211')?CASOS[1]:CASOS[2];
    const fila={caso,metodo,ruta,http,eco:!!eco,duracion_ms:ex.response?.responseTime??null,
      respuesta:resumenCuerpo(ruta,cuerpo),herramienta:'Newman',nombre};
    if(http==null) fila.tipo_fallo='SIN_RED_O_TIMEOUT';
    r.solicitudes.push(fila);ejecuciones[nombre]={http,cuerpo,eco:!!eco,tiempo_ms:fila.duracion_ms};
    reporte.solicitudes.push({...fila,aserciones:(ex.assertions??[]).map(a=>({nombre:a.assertion,aprobada:!a.error,error:a.error?.message??null}))});
  }
  r.herramientas.newman.iteraciones=summary?.run?.stats?.iterations?.total??(summary?1:0);
  r.herramientas.newman.solicitudes=reporte.solicitudes.length;
  r.herramientas.newman.aserciones=reporte.solicitudes.reduce((n,x)=>n+x.aserciones.length,0);
  const limpio=sanear(JSON.stringify(reporte,null,2),[token,adminToken,env.QA_SANDBOX_SECRET,
    env.QA_VETERINARIO_EMAIL,env.QA_ADMIN_EMAIL,env.QA_COMMON_PASSWORD,env.QA_ADMIN_PASSWORD]);
  const sub=path.join(c.directorio,'newman');fs.mkdirSync(sub,{recursive:true});
  fs.writeFileSync(path.join(sub,'newman-G068.json'),limpio,'utf8');
  fs.writeFileSync(path.join(sub,'newman-G068.html'),`<!doctype html><html lang="es"><meta charset="utf-8"><title>Newman G068</title><h1>Newman G068</h1><pre>${escaparHtml(limpio)}</pre></html>`,'utf8');
  r.evidencias.push('newman/newman-G068.json','newman/newman-G068.html');
  if(error) r.problemas_tecnicos.push(`Newman: ${error.message}`);
  return ejecuciones;
}
async function historial(pedirPagina,inicio,fin,buscado=null) {
  let eventos=[],cursor=null,ultima=null,completo=false;
  for(let i=0;i<PRESUPUESTO.paginas_verificacion;i++) {
    ultima=await pedirPagina(rutaHistorial(885,inicio,fin,cursor));
    if(ultima.http!==200||ultima.eco===false) break;
    eventos.push(...(ultima.cuerpo?.eventos??[]));cursor=ultima.cuerpo?.cursor_siguiente??null;
    if(!cursor||(buscado&&eventos.some(e=>String(e.id_evento)===String(buscado)))) {completo=true;break;}
  }
  return {http:ultima?.http??null,eco:ultima?.eco,eventos,completo,cursor_pendiente:!!cursor};
}
const estadoActivo = b => String(b?.nombre_estado??b?.estado?.nombre_estado??b?.estado_actual??b?.id_estado??'').toUpperCase();
const faseActivo = b => (b?.fases??[]).filter(f=>f.es_activa===true).map(f=>({id:f.id_gestion_fases,fase:f.nombre_fase_actual}));
const descripcionFase = fases => fases===null?'no comprobada':fases.length?JSON.stringify(fases):'sin fase activa';
const oraculos={
  'TC-M04-210':'Matriz G068 y RF-72 E1 4234-4239: HTTP 404, "El resultado de inferencia no existe o no está disponible."; se cancela sin registro ni evento.',
  'TC-M04-211':'Matriz G068 y RF-72 4161: rechazo indicando que el activo no corresponde al resultado, sin persistir. RF-72 no fija HTTP.',
  'TC-M04-245':'Matriz G068 y RF-72 4112-4113: activo dado de baja o inconsistente, registro rechazado y sin persistencia. RF-72 no fija HTTP; incidente administrativo fuera del oráculo.'};
function incidenciasDe(registros) {
  const numeros=new Map();
  return registros.filter(x=>x.veredicto?.estado==='RECHAZADO').map(x=>{
    const n=(numeros.get(x.caso)??0)+1;numeros.set(x.caso,n);return {
    id:`INC-M04-G068-${x.caso.slice(-3)}-${String(n).padStart(2,'0')}`,casos:[x.caso],
    severidad:x.caso===CASOS[2]&&x.http>=200&&x.http<300?'MEDIA':x.http>=200&&x.http<300?'ALTA':'MEDIA',certeza:'CONFIRMADA',equipo_inicial:'Desarrollo',
    fundamento:'primera discrepancia en API pública',motivo:x.veredicto.motivo,
    justificacion:x.caso===CASOS[2]&&x.http>=200&&x.http<300
      ?'Incumple RF-72 4112-4113: una retroalimentación sobre el activo dado de baja quedó persistida y puede ser consumida por RF-71 como etiqueta. El resultado de inferencia precede a la baja y su diagnóstico sigue siendo clínicamente coherente; no se observó alteración de otros datos.'
      :x.http>=200&&x.http<300?'Aceptación de dato inválido o vínculo incorrecto':'Respuesta de rechazo incompatible con el oráculo',
    causa_raiz:'NO DETERMINADA'};});
}
function motivoInforme(caso,r) {
  const estado=r.casos[caso].estado, z=r.registros.find(x=>x.caso===caso);
  if(caso===CASOS[2]&&estado==='RECHAZADO'&&z?.http===201&&z.persistio===true
    &&r.datos_elegidos.baja_885?.estado==='BAJA')
    return `con el 885 en BAJA (baja ${r.datos_elegidos.baja_885.http}, estado BAJA leído, BAJA_REGISTRADA en el sandbox ${r.datos_elegidos.baja_885.evento_rf52_en_sandbox?'sí':'no confirmado'}) la retroalimentación sobre ${String(z.resultado).slice(0,8)} se aceptó con HTTP 201 y quedó registrada con RETROALIMENTACION_REGISTRADA, cuando RF-72 4112-4113 exige que solo pueda registrarse si el activo existe y es válido`;
  return r.casos[caso].motivo;
}
export function informe(c,r) {
  const estados=CASOS.map(x=>r.casos[x].estado);
  const decision=!r.oficial?'TÉCNICO':estados.includes('RECHAZADO')?'RECHAZADO':estados.every(x=>x==='APROBADO')?'APROBADO':'NO_CONCLUYENTE';
  const faltantes=CASOS.filter(x=>!['APROBADO','RECHAZADO'].includes(r.casos[x].estado))
    .map(x=>`${x} (${x===CASOS[2]&&r.casos[x].motivo.startsWith('Precondición no montada:')?'precondición de baja no montada: '+r.casos[x].motivo.slice('Precondición no montada:'.length).trim():corto(r.casos[x].motivo)})`);
  const tabla=CASOS.map(x=>`| ${x} | ${r.casos[x].estado} | ${corto(motivoInforme(x,r))} |`).join('\n');
  const detalle=CASOS.map(x=>{
    const z=r.registros.find(y=>y.caso===x);return `### ${x} — ${r.casos[x].estado}\n\n- Qué se hizo: ${x===CASOS[2]?'Baja temporal del 885, lectura de estado y bitácora, y POST condicional en una ejecución Newman.':`POST Newman con ${x===CASOS[0]?'UUID v4 inexistente':'resultado libre del 885 y otro activo existente'}.`}\n- Qué se esperaba: ${oraculos[x]}\n- Qué se observó: ${z?`HTTP ${z.http??'sin respuesta'}; ${corto(z.codigo??'—')}; ${corto(z.mensaje??'sin mensaje')}; persistió ${z.persistio===null?'no determinado':z.persistio?'sí':'no'}.`:'Sin respuesta de producto para este caso.'}\n- Por qué ${r.casos[x].estado}: ${corto(motivoInforme(x,r))}. Evidencia: ${IDS[CASOS.indexOf(x)]} en resultado.json.`;
  }).join('\n\n');
  const intentos=r.registros.map(z=>`| ${z.caso} | ${String(z.resultado??'—').slice(0,8)} | CORRECTO sin diagnóstico; activo ${z.activo_enviado} | ${z.http??'—'} | ${corto(z.codigo??'—')}; ${corto(z.mensaje??'—')} | ${z.persistio===null?'no determinado':z.persistio?'sí':'no'} |`).join('\n');
  const inc=r.incidencias.length?r.incidencias.map(x=>`- ${x.id}: ${x.severidad}, certeza ${x.certeza}; atención inicial ${x.equipo_inicial} por ${x.fundamento}. ${x.motivo}. ${x.justificacion}. ${x.casos.includes(CASOS[2])?'Hipótesis probable: el caso de uso no consulta el estado del activo (registrar_retroalimentacion_use_case.py:55-107 y resultado_inferencia_adapter.py:16-23, origin/test daefc3a5). ':''}Causa raíz no confirmada.`).join('\n'):'Sin incidencias de producto.';
  return `# TC-M04-G068 — ${decision}\n\n## Identificación\n\nGrupo G068; casos ${CASOS.join(', ')}; RF-72; versión ${c.version}; RUN ${c.runId}; ambiente ${c.ensayo?'loopback local':'TEST'}; autorización ${c.referencia}; código revisado origin/test daefc3a5; Node.js y Newman. Solo API.\n\n## Decisión del caso\n\n| Caso | Decisión | Motivo |\n|---|---|---|\n${tabla}\n\nRUN oficial: ${r.oficial?'sí':'no'}. ${r.oficial?'Cada caso tuvo POST y comprobación de historial y auditoría; los veredictos se basan en las respuestas y la persistencia observadas.':faltantes.length?'Hay casos obligatorios sin evaluación conclusiva.':corto(r.problemas_tecnicos.join('; ')||r.cierre.rollback.motivo)} El ensayo local no acredita TEST.\n\nQué falta: ${faltantes.join('; ')||(!r.cierre.rollback.verificado?corto(r.cierre.rollback.motivo):r.oficial?'ninguno':corto(r.problemas_tecnicos.join('; ')||'revisar condición de oficialidad'))}.\n\n## Precondición de datos (semilla y baja temporal)\n\nActivo 885, modelo INDIVIDUAL; otro activo ${r.datos_elegidos.otro_activo?.id??'no encontrado'} (${corto(r.datos_elegidos.otro_activo?.nombre??'sin nombre')}). Resultados libres ${r.datos_elegidos.resultados_libres??0}; eventos examinados ${r.datos_elegidos.descubrimiento_885?.eventos_examinados??0}; páginas ${r.datos_elegidos.descubrimiento_885?.paginas??0}; cursor pendiente ${r.datos_elegidos.descubrimiento_885?.cursor_pendiente?'sí':'no'}. Fase antes: ${descripcionFase(r.datos_elegidos.activo_885_antes?.fase??null)}; ${Array.isArray(r.datos_elegidos.activo_885_antes?.fase)&&r.datos_elegidos.activo_885_antes.fase.length===0?'Activo 885 sin fase activa antes de la baja. ':''}durante: ${descripcionFase(r.datos_elegidos.baja_885?.fase??null)}. Baja HTTP ${r.datos_elegidos.baja_885?.http??'—'}; estado durante baja ${r.datos_elegidos.baja_885?.estado??'no leído'}; BAJA_REGISTRADA en sandbox ${r.datos_elegidos.baja_885?.evento_rf52_en_sandbox?'sí':'no confirmado'}. El buffer local RF-52 puede conservar una copia fuera del sandbox si falla la BD o hay alta carga.\n\n## Detalle por caso\n\n${detalle}\n\n## Tabla de intentos\n\n| Caso | Resultado | Cuerpo resumido | HTTP | Código y mensaje | Persistió |\n|---|---|---|---|---|---|\n${intentos}\n\n## Observaciones\n\n${r.observaciones.map(corto).join('; ')||'Ninguna.'}\n\n## Incidencias de producto\n\n${inc}\n\n## Problemas técnicos y análisis de causas\n\n${r.problemas_tecnicos.map(corto).join('; ')||'Ninguno.'} La derivación inicial se basa en la primera discrepancia pública; causa raíz no determinada.\n\n## Historial, cierre y rollback\n\n${r.solicitudes.length} solicitudes. DELETE HTTP ${r.cierre.run.cierre_http??'sin respuesta'}; rollback ${r.cierre.rollback.verificado?'verificado':'no verificado'}: ${corto(r.cierre.rollback.motivo)}. Activo 885 poscierre ${r.cierre.activo_885?.estado??'no leído'}, fase ${descripcionFase(r.cierre.activo_885?.fase??null)}. Lecturas poscierre pueden crear HISTORIAL_CONSULTADO fuera del sandbox.\n\n## Conclusión y acciones\n\n${decision==='RECHAZADO'?'Desarrollo debe revisar las discrepancias confirmadas en TEST; repetir los casos afectados en un RUN autorizado.':'Conservar evidencias y revisar los casos pendientes o BLOQUEADOS con el responsable QA.'}\n\n## Herramientas\n\n${r.herramientas.newman.iteraciones===0?'Newman no se ejecutó (0 iteraciones).':`Newman ${r.herramientas.newman.version??'no disponible'}: ${r.herramientas.newman.iteraciones} iteración, ${r.herramientas.newman.solicitudes} solicitudes y ${r.herramientas.newman.aserciones} aserciones. ${r.evidencias.some(x=>x.startsWith('newman/'))?'Reportes JSON y HTML generados en newman/.':'Sin reportes Newman.'}`} Login, descubrimiento, lecturas de verificación y cierre por fetch.\n\n## Evidencias\n\n${r.evidencias.map(x=>`- ${x}`).join('\n')}\n`;
}
export async function evaluar(c,{env=leerEnv(),newmanVersion=versionNewman()}={}) {
  const api=String(env.SIGAB_API_TEST_BASE??'').replace(/\/+$/,'');
  const r={grupo:'G068',version:c.version,run_id:c.runId,operacion:c.operacion,ambiente:c.ensayo?'LOOPBACK_LOCAL':'TEST',
    casos:Object.fromEntries(CASOS.map(x=>[x,{estado:'NO_CONCLUYENTE',motivo:'No ejecutado'}])),
    comprobaciones:[],registros:[],datos_elegidos:{},solicitudes:[],observaciones:[],problemas_tecnicos:[],incidencias:[],
    cypress:{total_pruebas:0},herramientas:{newman:{...newmanVersion,iteraciones:0,solicitudes:0,aserciones:0}},
    evidencias:['preflight.json','resultado.json',INFORME(c.version)],cierre:{run:{cierre_http:null},rollback:{verificado:false,motivo:'Sin cierre'},activo_885:null},
    oficial:false,consume_version:false,_limite:Date.now()+900000,_consecutivos5xx:0};
  fs.mkdirSync(c.directorio,{recursive:true});const pre=preflight(c,env,newmanVersion);guardar(path.join(c.directorio,'preflight.json'),pre);
  let token=null,adminToken=null,iniciado=false,usuarioId=null,antes=null;
  const pedirRun=async(m,p,opts={})=>{const x=await pedir(r,api,m,p,{...opts,token:opts.token??token,secreto:env.QA_SANDBOX_SECRET,runId:c.runId});
    if(x.http===403) throw Error('CLAVE_O_PERMISO_403');
    if(r._consecutivos5xx>=3) throw Error('TRES_5XX_CONSECUTIVOS');return x;};
  const inicio=fecha(Date.now()-PRESUPUESTO.dias_busqueda*86400000),fin=fecha(Date.now());
  try {
    if(!pre.ok) throw Error(`PREFLIGHT:${pre.barreras.join(',')}`);
    const login=await pedir(r,api,'POST','/sesiones/',{cuerpo:{correo_electronico:env.QA_VETERINARIO_EMAIL,contrasena:env.QA_COMMON_PASSWORD},timeout:PRESUPUESTO.timeout_login_ms});
    if(login.http!==200||!login.cuerpo?.token) throw Error(`LOGIN_${login.http??'SIN_RESPUESTA'}`);
    token=login.cuerpo.token;usuarioId=usuarioDelToken(token);
    if(env.QA_ADMIN_EMAIL) {
      const admin=await pedir(r,api,'POST','/sesiones/',{cuerpo:{correo_electronico:env.QA_ADMIN_EMAIL,
        contrasena:env.QA_ADMIN_PASSWORD??env.QA_COMMON_PASSWORD},timeout:PRESUPUESTO.timeout_login_ms});
      if(admin.http===200&&admin.cuerpo?.token) adminToken=admin.cuerpo.token;
      else r.observaciones.push(`Login Administrador QA no disponible: HTTP ${admin.http??'sin respuesta'}`);
    }
    iniciado=true;
    const activos=[];
    for(let pagina=1;pagina<=PRESUPUESTO.paginas_activos;pagina++) {
      const x=await pedirRun('GET',`/activos-biologicos?tipo=INDIVIDUAL&pagina=${pagina}&page_size=8`);
      if(x.http!==200||x.eco!==true) break;
      activos.push(...(x.cuerpo?.registros??[]));if(pagina>=Number(x.cuerpo?.total_paginas??1)) break;
    }
    let otro=activos.find(a=>Number(a.id_activo_biologico)!==885&&a.tipo==='INDIVIDUAL'&&estadoActivo(a)==='ACTIVO')
      ??activos.find(a=>Number(a.id_activo_biologico)!==885&&a.tipo==='INDIVIDUAL')
      ??activos.find(a=>Number(a.id_activo_biologico)!==885);
    if(!otro) for(let pagina=1;pagina<=PRESUPUESTO.paginas_activos;pagina++) {
      const x=await pedirRun('GET',`/activos-biologicos?pagina=${pagina}&page_size=8`);
      if(x.http!==200||x.eco!==true) break;
      otro=(x.cuerpo?.registros??[]).find(a=>Number(a.id_activo_biologico)!==885);
      if(otro||pagina>=Number(x.cuerpo?.total_paginas??1)) break;
    }
    if(otro) r.datos_elegidos.otro_activo={id:otro.id_activo_biologico,nombre:otro.nombre??otro.nombre_activo??otro.identificador??'sin nombre'};
    antes=await pedir(r,api,'GET','/activos-biologicos/885',{token,secreto:env.QA_SANDBOX_SECRET,runId:c.runId});
    const faseAntes=await pedir(r,api,'GET','/activos-biologicos/885/fases',{token,secreto:env.QA_SANDBOX_SECRET,runId:c.runId});
    r.datos_elegidos.activo_885_antes={http:antes.http,estado:estadoActivo(antes.cuerpo),fase:faseAntes.http===200?faseActivo(faseAntes.cuerpo):null};
    if(antes.http!==200||estadoActivo(antes.cuerpo)!=='ACTIVO'||faseAntes.http!==200)
      r.problemas_tecnicos.push('Estado o historial de fases inicial del 885 no confirmado; 245 depende de esta precondición');
    const eventos=[];
    r.datos_elegidos.descubrimiento_885={eventos_examinados:0,resultados_libres:0,paginas:0,cursor_pendiente:false};
    for(const activo of [{id_activo_biologico:885}]) {
      let cursor=null;
      for(let n=0;n<PRESUPUESTO.paginas_descubrimiento;n++) {
        const x=await pedirRun('GET',rutaHistorial(activo.id_activo_biologico,inicio,fin,cursor));
        r.datos_elegidos.descubrimiento_885.paginas++;
        if(x.http!==200||x.eco!==true) break;
        eventos.push(...(x.cuerpo?.eventos??[]).map(e=>({...e,id_activo_biologico:activo.id_activo_biologico})));
        r.datos_elegidos.descubrimiento_885.eventos_examinados=eventos.length;
        cursor=x.cuerpo?.cursor_siguiente??null;if(!cursor) break;
      }
      r.datos_elegidos.descubrimiento_885.cursor_pendiente=!!cursor;
    }
    const versiones={},ids=[...new Set(eventos.filter(e=>e.tipo_evento==='INFERENCIA'&&e.payload?.tipo_modelo==null)
      .map(e=>Number(e.payload?.id_version_modelo)).filter(Number.isSafeInteger))];
    for(const id of ids.slice(0,PRESUPUESTO.versiones_maximas)) {
      const x=await pedirRun('GET',`/prediccion/modelos/${id}`);
      if(x.http===200&&x.eco&&Number(x.cuerpo?.id_version_modelo)===id) versiones[String(id)]=x.cuerpo.tipo_modelo;
    }
    const candidatos=seleccionar(eventos,usuarioId,versiones,inicio);
    r.datos_elegidos.resultados_libres=candidatos.length;
    r.datos_elegidos.descubrimiento_885.eventos_examinados=eventos.length;
    r.datos_elegidos.descubrimiento_885.resultados_libres=candidatos.length;
    const cuerpo=(caso,resultado,activo)=>({id_resultado_inferencia:resultado,id_activo_biologico:activo,
      estado_retroalimentacion:'CORRECTO',observaciones_clinicas:`QA G068 ${caso}`});
    const dato211=otro?candidatos[0]:null;
    const dato245=otro?candidatos[1]:candidatos[0];
    const reemplazo=otro?candidatos[2]:null;
    const inicioBaja=new Date(Date.now()-60000).toISOString();
    const cuerpos={c210:cuerpo(CASOS[0],randomUUID(),885),
      c211:dato211?cuerpo(CASOS[1],dato211.id_resultado_inferencia,otro.id_activo_biologico):null,
      reemplazo:reemplazo?cuerpo(CASOS[1],reemplazo.id_resultado_inferencia,otro.id_activo_biologico):null,
      c245:dato245&&antes.http===200&&estadoActivo(antes.cuerpo)==='ACTIVO'&&faseAntes.http===200
        ?cuerpo(CASOS[2],dato245.id_resultado_inferencia,885):null,
      baja:{tipo_baja:'descarte_sanitario',fecha_baja:fecha(Date.now()),
        motivo_baja:'QA G068 precondición de 245, revertida por el DELETE'},inicioBaja};
    const ex=await pedirNewmanUnico(r,c,api,env,token,adminToken,cuerpos);
    const faseDurante=ex['G068-ESTADO-BAJA']?.http===200
      ?await pedir(r,api,'GET','/activos-biologicos/885/fases',{token,secreto:env.QA_SANDBOX_SECRET,runId:c.runId}):null;
    const baja=ex['G068-BAJA-ADMIN']??ex['G068-BAJA-VET'];
    const estadoBaja=ex['G068-ESTADO-BAJA'];
    const bitacora=ex['G068-BITACORA-BAJA'];
    const bajaValida=baja?.http===201&&baja.eco===true&&estadoBaja?.http===200
      &&estadoBaja.eco===true&&estadoActivo(estadoBaja.cuerpo)==='BAJA';
    const eventoBitacora=bitacora?.http===200&&bitacora.eco===true
      &&(bitacora.cuerpo?.registros??[]).some(x=>x.rf_origen==='RF45'&&x.tipo_evento==='BAJA_REGISTRADA'
        &&Number(x.id_activo_biologico)===885);
    r.datos_elegidos.baja_885={http:baja?.http??null,estado_http:estadoBaja?.http??null,
      estado:estadoActivo(estadoBaja?.cuerpo),bitacora_http:bitacora?.http??null,
       fase:faseDurante?.http===200?faseActivo(faseDurante.cuerpo):null,
       fase_http:faseDurante?.http??null,evento_rf52_en_sandbox:!!eventoBitacora};
    if(bajaValida&&faseDurante?.http!==200)
      r.problemas_tecnicos.push('Fase durante la baja no comprobada');
    if(bajaValida&&faseDurante?.http===200&&faseActivo(faseDurante.cuerpo).length)
      r.problemas_tecnicos.push('ALERTA PRIORITARIA: fase del activo 885 siguió activa durante la baja');
    if(bajaValida&&!eventoBitacora)
      r.observaciones.push('posible evento RF-52 en buffer local fuera del sandbox; revisar con responsable QA');
    for(const caso of CASOS) {
      const nombre=caso===CASOS[0]?'G068-210':caso===CASOS[1]?
        (ex['G068-211-REEMPLAZO']?'G068-211-REEMPLAZO':'G068-211'):'G068-245';
      const post=ex[nombre];
      const enviado=caso===CASOS[0]?cuerpos.c210:caso===CASOS[1]?
        (nombre==='G068-211-REEMPLAZO'?cuerpos.reemplazo:cuerpos.c211):cuerpos.c245;
      if(caso===CASOS[2]&&!bajaValida) {
        r.casos[caso]={estado:'NO_CONCLUYENTE',motivo:!cuerpos.c245?'Sin segundo resultado de inferencia INDIVIDUAL libre':
          `Precondición no montada: baja HTTP ${baja?.http??'sin respuesta'}, estado 885 ${estadoActivo(estadoBaja?.cuerpo)||'no confirmado'}`};continue;
      }
      if(!post||!enviado) {
        r.casos[caso]={estado:r.problemas_tecnicos.includes('CLAVE_403 en Newman')&&caso!==CASOS[2]?'BLOQUEADO':'NO_CONCLUYENTE',motivo:caso===CASOS[1]&&!otro?'No se descubrió otro activo existente':
          caso===CASOS[2]?'Sin segundo resultado de inferencia INDIVIDUAL libre':'POST no ejecutado o sin resultado libre'};continue;
      }
      if(post.http===403&&/clave|secreto|sandbox/i.test(String(post.cuerpo?.message??post.cuerpo?.detail??''))) {
        r.casos[caso]={estado:'BLOQUEADO',motivo:'403 de clave del sandbox; solicitud detenida'};continue;
      }
      if(caso===CASOS[1]&&['RETROALIMENTACION_DUPLICADA','FUERA_DE_VENTANA_TEMPORAL'].includes(post.cuerpo?.error_code)) {
        r.casos[caso]={estado:'NO_CONCLUYENTE',motivo:`Resultado no apto (${post.cuerpo.error_code}); reemplazos agotados`};continue;
      }
      const resultado=enviado.id_resultado_inferencia;
      const h=await historial(p=>pedir(r,api,'GET',p,{token,secreto:env.QA_SANDBOX_SECRET,runId:c.runId,caso}),inicio,fin,post.cuerpo?.id_retroalimentacion);
      const q=post.http===201&&post.cuerpo?.id_retroalimentacion?`id_referencia=${post.cuerpo.id_retroalimentacion}`:
        `fecha_desde=${encodeURIComponent(inicioBaja)}&id_usuario=${usuarioId}`;
      const x=await pedir(r,api,'GET',`/prediccion/auditoria?tipo_evento=RETROALIMENTACION_REGISTRADA&${q}&por_pagina=200`,
        {token,secreto:env.QA_SANDBOX_SECRET,runId:c.runId,caso});
      const a={http:x.http,eco:x.eco,items:x.cuerpo?.items??[],
        completo:x.http===200&&Number(x.cuerpo?.total??Infinity)<=(x.cuerpo?.items?.length??0)};
      const veredicto=decidir(caso,post,h,a,resultado,usuarioId);
      const registro={caso,resultado,activo_enviado:enviado.id_activo_biologico,
        tipo_modelo:caso===CASOS[0]?null:tipoModelo(caso===CASOS[1]?
          (nombre==='G068-211-REEMPLAZO'?reemplazo:dato211):dato245,versiones),
        http:post.http,codigo:post.cuerpo?.error_code??null,mensaje:post.cuerpo?.message??null,
        persistio:h.completo?!!h.eventos.some(e=>e.tipo_evento==='RETROALIMENTACION'&&String(e.id_resultado_inferencia)===String(resultado)
          &&String(e.payload?.id_usuario_veterinario)===String(usuarioId)):null,
        historial_http:h.http,auditoria_http:a.http,veredicto};
      r.registros.push(registro);r.casos[caso]=veredicto;
    }
    if(r.problemas_tecnicos.includes('TRES_5XX_CONSECUTIVOS en Newman')) {
      const newman=r.solicitudes.filter(x=>x.herramienta==='Newman');
      const serie=new Set(newman.slice(-3).map(x=>x.caso));
      const ejecutados=new Set(newman.filter(x=>x.ruta===POST&&x.metodo==='POST').map(x=>x.caso));
      for(const caso of CASOS) if(serie.has(caso)||!ejecutados.has(caso)) {
        const veredicto={estado:'BLOQUEADO',motivo:'Fallo de ambiente: tres respuestas 5xx consecutivas en Newman; evaluación técnica pendiente'};
        r.casos[caso]=veredicto;
        for(const registro of r.registros.filter(x=>x.caso===caso)) registro.veredicto=veredicto;
      }
    }
  } catch(e) {
    r.problemas_tecnicos.push(`Interrupción: ${corto(e.message)}`);
    const bloqueo=/LOGIN|CLAVE_O_PERMISO_403|TRES_5XX|PREFLIGHT/.test(e.message);
    for(const caso of CASOS.slice(0,2)) if(r.casos[caso].motivo==='No ejecutado')
      r.casos[caso]={estado:bloqueo?'BLOQUEADO':'NO_CONCLUYENTE',motivo:`Interrupción técnica: ${corto(e.message)}`};
    if(r.casos[CASOS[2]].motivo==='No ejecutado')
      r.casos[CASOS[2]]={estado:'NO_CONCLUYENTE',motivo:`Precondición o evaluación interrumpida: ${e.message}`};
  } finally {
    if(iniciado) {
      const cierre=await pedir(r,api,'DELETE',`/test-control/runs/${encodeURIComponent(c.runId)}`,{secreto:env.QA_SANDBOX_SECRET});
      r.cierre.run.cierre_http=cierre.http;
      let ausentes=cierre.http===200;
      for(const z of r.registros) {
        const h=await historial(p=>pedir(r,api,'GET',p,{token,caso:z.caso}),inicio,fin);
        if(h.http!==200||!h.completo||h.eventos.some(e=>e.tipo_evento==='RETROALIMENTACION'
          &&String(e.id_resultado_inferencia)===String(z.resultado)
          &&String(e.payload?.id_usuario_veterinario)===String(usuarioId))) ausentes=false;
      }
      const activo=await pedir(r,api,'GET','/activos-biologicos/885',{token});
      const fases=await pedir(r,api,'GET','/activos-biologicos/885/fases',{token});
      r.cierre.activo_885={http:activo.http,estado:estadoActivo(activo.cuerpo),fase:fases.http===200?faseActivo(fases.cuerpo):null};
      const mismo=activo.http===200&&antes?.http===200&&r.cierre.activo_885.estado==='ACTIVO'
        &&estadoActivo(antes.cuerpo)==='ACTIVO'
        &&r.cierre.activo_885.fase!==null&&r.datos_elegidos.activo_885_antes?.fase!==null
        &&JSON.stringify(r.cierre.activo_885.fase)===JSON.stringify(r.datos_elegidos.activo_885_antes.fase);
      r.cierre.rollback={verificado:ausentes&&mismo,motivo:ausentes&&mismo?'Ausencia de registros y estado/fase 885 concordantes poscierre':'DELETE, registros o estado/fase 885 sin confirmar'};
      if(!mismo) r.problemas_tecnicos.push('ALERTA PRIORITARIA: estado o fase del activo 885 no restaurados o no comprobados');
    }
    r.comprobaciones=CASOS.map((caso,i)=>({caso,fuente:'API',id:IDS[i],tipo:'ASSERT',estado:r.casos[caso].estado,
      motivo:r.casos[caso].motivo,evidencia:'resultado.json'}));
    r.incidencias=incidenciasDe(r.registros);
    const posts=r.solicitudes.filter(x=>x.ruta===POST&&x.metodo==='POST');
    const reportesNewman=r.evidencias.filter(x=>x.startsWith('newman/'));
    r.oficial=posts.length>=2&&posts.every(x=>x.herramienta==='Newman')
      &&r.herramientas.newman.iteraciones===1&&r.herramientas.newman.solicitudes===r.solicitudes.filter(x=>x.herramienta==='Newman').length
      &&r.herramientas.newman.aserciones>=2*r.herramientas.newman.solicitudes
      &&reportesNewman.length===2
      &&!r.solicitudes.some(x=>x.herramienta==='Newman'&&x.http==null)
      &&!r.problemas_tecnicos.some(x=>x.startsWith('Newman:'))
      &&!r.problemas_tecnicos.includes('Fase durante la baja no comprobada')
      &&!r.problemas_tecnicos.some(x=>x.startsWith('ALERTA PRIORITARIA'))
      &&!r.problemas_tecnicos.some(x=>x==='CLAVE_403 en Newman'||x==='TRES_5XX_CONSECUTIVOS en Newman')
      &&CASOS.slice(0,2).every(x=>['APROBADO','RECHAZADO'].includes(r.casos[x].estado))
      &&['APROBADO','RECHAZADO'].includes(r.casos[CASOS[2]].estado)&&r.cierre.rollback.verificado
      &&r.solicitudes.length<=PRESUPUESTO.solicitudes_totales;
    r.consume_version=r.oficial;delete r._limite;delete r._consecutivos5xx;
    guardar(path.join(c.directorio,'resultado.json'),r);
    fs.writeFileSync(path.join(c.directorio,INFORME(c.version)),informe(c,r),'utf8');
  }
  return r;
}
export async function recuperar(c,{env=leerEnv()}={}) {
  const pre=preflight(c,env);if(!pre.ok) throw Error(`PREFLIGHT:${pre.barreras.join(',')}`);
  const previo=JSON.parse(fs.readFileSync(path.join(c.directorio,'resultado.json'),'utf8'));
  if(previo.run_id!==c.runId||previo.version!==c.version) throw Error('RUN previo incoherente');
  const api=String(env.SIGAB_API_TEST_BASE).replace(/\/+$/,'');
  const r={solicitudes:[],_limite:Date.now()+900000,_consecutivos5xx:0};
  const cierre=await pedir(r,api,'DELETE',`/test-control/runs/${encodeURIComponent(c.runId)}`,{secreto:env.QA_SANDBOX_SECRET});
  const login=await pedir(r,api,'POST','/sesiones/',{cuerpo:{correo_electronico:env.QA_VETERINARIO_EMAIL,contrasena:env.QA_COMMON_PASSWORD},timeout:PRESUPUESTO.timeout_login_ms});
  const token=login.http===200?login.cuerpo?.token:null,usuarioId=usuarioDelToken(token);
  let ausentes=!!token&&[200,404].includes(cierre.http);
  const inicio=fecha(Date.now()-PRESUPUESTO.dias_busqueda*86400000),fin=fecha(Date.now());
  for(const z of previo.registros.filter(x=>x.resultado)) {
    const h=await historial(p=>pedir(r,api,'GET',p,{token,caso:z.caso}),inicio,fin);
    if(h.http!==200||!h.completo||h.eventos.some(e=>e.tipo_evento==='RETROALIMENTACION'
      &&String(e.id_resultado_inferencia)===String(z.resultado)
      &&String(e.payload?.id_usuario_veterinario)===String(usuarioId))) ausentes=false;
  }
  const activo=token?await pedir(r,api,'GET','/activos-biologicos/885',{token}):null;
  const fases=token?await pedir(r,api,'GET','/activos-biologicos/885/fases',{token}):null;
  const mismo=activo?.http===200&&estadoActivo(activo.cuerpo)===previo.datos_elegidos.activo_885_antes?.estado
    &&fases?.http===200&&JSON.stringify(faseActivo(fases.cuerpo))===JSON.stringify(previo.datos_elegidos.activo_885_antes?.fase);
  const salida={grupo:'G068',run_objetivo:c.runId,operacion:'recuperar',cierre_http:cierre.http,
    rollback_verificado:ausentes&&mismo,activo_885:{estado:estadoActivo(activo?.cuerpo),fase:faseActivo(fases?.cuerpo)},solicitudes:r.solicitudes};
  guardar(path.join(c.directorio,`recuperacion-${new Date().toISOString().replace(/[-:TZ.]/g,'').slice(0,14)}.json`),salida);
  return salida;
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)) {
  if(process.argv.includes('--capacidades')) console.log(JSON.stringify(CAPACIDADES,null,2));
  else if(process.argv.includes('--comprobar')) process.exitCode=comprobar();
  else try { const c=contexto(process.argv.slice(2));
    if(c.operacion==='recuperar') {const r=await recuperar(c);console.log(JSON.stringify({grupo:'G068',rollback_verificado:r.rollback_verificado}));if(!r.rollback_verificado)process.exitCode=2;}
    else {const r=await evaluar(c);console.log(JSON.stringify({grupo:'G068',run_id:r.run_id,oficial:r.oficial,casos:Object.fromEntries(CASOS.map(x=>[x,r.casos[x].estado]))}));if(!r.oficial)process.exitCode=2;}
  } catch(e){console.error(corto(e.message));process.exitCode=2;}
}
