#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import {CASOS,IDS,PRESUPUESTO,CAPACIDADES,DIAS,antiguedad,elegir,superficie,e9} from './lib/g070_core.mjs';

const DIR=path.dirname(fileURLToPath(import.meta.url));
const RAIZ=path.resolve(DIR,'../../../../..');
const require=createRequire(import.meta.url);
const API='https://www.api.inmero.co/api-sgpmp-test';
const COLECCION=JSON.parse(fs.readFileSync(path.join(DIR,'G070.postman_collection.json'),'utf8'));
const NOMBRES=['G070-214','G070-215-89','G070-215-90','G070-215-90H','G070-215-91','G070-217-120A','G070-218-120B'];
const CLAVES=['reciente','d89','d90','d90h','d91','d120a','d120b'];
const limpiar=x=>String(x??'').replace(/[\r\n|]/g,' ');
const guardar=(f,x)=>fs.writeFileSync(f,JSON.stringify(x,null,2),'utf8');
const fecha=d=>new Intl.DateTimeFormat('en-CA',{timeZone:'America/Bogota',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(d));
const informeNombre=v=>v===1?'TC-M04-G070_resultado.md':`TC-M04-G070_reevaluacion_V${v}.md`;
const html=x=>String(x).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function sanear(x,secretos=[]){let s=String(x);for(const v of secretos.filter(x=>typeof x==='string'&&x.length>3))s=s.split(v).join('[REDACTADO]');
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
const fechaIsoValida=x=>{
  const m=typeof x==='string'&&x.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/);
  if(!m||!Number.isFinite(Date.parse(x)))return false;
  const [ano,mes,dia,hora,minuto,segundo]=m.slice(1,7).map(Number);
  const calendario=new Date(Date.UTC(ano,mes-1,dia));
  return calendario.getUTCFullYear()===ano&&calendario.getUTCMonth()===mes-1
    &&calendario.getUTCDate()===dia&&hora<24&&minuto<60&&segundo<60;
};
export function preflight(c,env=leerEnv(),newman=versionNewman(),ahora=Date.now()){
  const barreras=['SIGAB_API_TEST_BASE','QA_SANDBOX_SECRET','QA_VETERINARIO_EMAIL',
    'QA_ADMIN_EMAIL','QA_COMMON_PASSWORD','QA_ADMIN_PASSWORD'].filter(k=>!String(env[k]??'').trim());
  if(env.QA_AUTORIZADO!=='SI')barreras.push('QA_AUTORIZADO');
  if(c.version>=2&&!c.ensayo){
    if(!fechaIsoValida(c.semillaCommit))barreras.push('SEMILLA_COMMIT_FALTANTE');
    else if(ahora-Date.parse(c.semillaCommit)>10*60*60*1000)barreras.push('SEMILLA_CADUCADA');}
  if(!newman.ok)barreras.push('NEWMAN_NO_DISPONIBLE');
  if(JSON.stringify(COLECCION.item.map(x=>x.name))!==JSON.stringify(NOMBRES)
    ||COLECCION.item.some(x=>x.request.method!=='POST'||!String(x.request.url).endsWith('/prediccion/retroalimentacion')))
    barreras.push('COLECCION_INVALIDA');
  const base=String(env.SIGAB_API_TEST_BASE??'').replace(/\/+$/,'');
  if(c.ensayo?!/^http:\/\/(127\.0\.0\.1|localhost):\d+$/.test(base):base!==API)barreras.push('API_NO_CANONICA');
  return {grupo:'G070',run_id:c.runId,ok:!barreras.length,barreras,presupuesto:PRESUPUESTO,
    herramientas:{newman},efectos:['Dos logins, Veterinario A y Administrador; último acceso y auditoría de autenticación',
      'Lecturas de activo, historial, modelos, OpenAPI, configuración y auditoría',
      'Retroalimentaciones aceptadas y auditoría, revertidas mediante DELETE',
      'PATCH global 7, 8, 365 y restauración a 90; ampliación puntual dentro del sandbox',
      'POST/PATCH sin respuesta: conciliación por GET/historial, sin reintento de la misma operación',
      'DELETE siempre; historial poscierre puede crear HISTORIAL_CONSULTADO fuera del sandbox']};
}
export function comprobar(){const archivos=['g070.mjs','lib/g070_core.mjs','G070.postman_collection.json',
  'pruebas/g070_ensayo.mjs','pruebas/g070_env.test.mjs','pruebas/g070_seleccion.test.mjs',
  'pruebas/semilla_observada_G070_V2.json','pruebas/registro_qa.mjs','README.md',
  'EvaluacionV2/Resultados/RUN-G070-V2-20261101-045537/api/antecedentes/indice.json',
  'EvaluacionV2/Resultados/RUN-G070-V2-20261101-045537/api/antecedentes/intento_1.json',
  'EvaluacionV2/Resultados/RUN-G070-V2-20261101-045537/api/antecedentes/intento_2.json'];
  const faltantes=archivos.filter(x=>!fs.existsSync(path.join(DIR,x)));
  const superior=fs.existsSync(path.join(DIR,'Resultados'))&&fs.readdirSync(path.join(DIR,'Resultados')).some(x=>x.endsWith('.md'));
  const activos=['g070.mjs','README.md',...['lib','pruebas'].flatMap(carpeta=>fs.readdirSync(path.join(DIR,carpeta))
    .filter(x=>/\.(?:mjs|json|md)$/.test(x)).map(x=>`${carpeta}/${x}`))];
  const rutaTecnica=/EvaluacionV2[\\/]Resultados[\\/]RUN-G070-V2-20261101-(?:043336|044513)(?:[\\/]|\b)/;
  const dependenciasTecnicas=activos.filter(x=>rutaTecnica.test(fs.readFileSync(path.join(DIR,x),'utf8')));
  const n=versionNewman();const ok=!faltantes.length&&!superior&&!dependenciasTecnicas.length&&n.ok&&COLECCION.item.length===7;
  console.log(JSON.stringify({grupo:'G070',ok,faltantes,markdown_superior:superior,dependencias_tecnicas:dependenciasTecnicas,newman:n,presupuesto:PRESUPUESTO,
    secuencia_v2:CAPACIDADES.secuencia_v2,conciliacion:CAPACIDADES.conciliacion}));return ok?0:2;}
export function contexto(args,base=DIR){const v=k=>args.includes(k)?args[args.indexOf(k)+1]:undefined;
  const operacion=v('--operacion'),version=Number(v('--version')),intento=Number(v('--intento')),
    runId=v('--run-id'),referencia=v('--autorizacion'),archivo=v('--contexto');
  if(!CAPACIDADES.operaciones.includes(operacion)||!Number.isInteger(version)||version<1
    ||!Number.isInteger(intento)||intento<1||!referencia||!archivo
    ||!new RegExp(`^RUN-G070-V${version}-\\d{8}-\\d{6}$`).test(runId??''))throw Error('Contexto incompleto');
  const destino=path.join(base,...(version===1?['Resultados',runId]:[`EvaluacionV${version}`,'Resultados',runId]));
  const ruta=path.resolve(archivo);
  if(path.dirname(ruta)!==destino||!(operacion==='recuperar'?/^recuperacion-\d{14}\.contexto\.json$/.test(path.basename(ruta)):path.basename(ruta)==='contexto_operacion.json'))throw Error('Contexto fuera del RUN canónico');
  const c=JSON.parse(fs.readFileSync(ruta,'utf8'));
  if(c.grupo!=='G070'||c.run_id!==runId||c.version!==version||c.intento!==intento
    ||c.operacion!==operacion.toUpperCase()||c.referencia!==referencia
    ||JSON.stringify(c.casos)!==JSON.stringify(CASOS)
    ||(operacion==='reevaluar'||operacion==='reintentar'&&version>=2)&&!validarReevaluacion(c,version)
    ||operacion==='recuperar'&&v('--run-objetivo')!==runId)throw Error('Contexto incoherente');
  return {operacion,version,intento,runId,referencia,directorio:destino,ensayo:false,
    semillaCommit:c.semilla_commit??c.alcance_reevaluacion?.semilla_commit??null,
    commit:c.commit??c.alcance_reevaluacion?.commit_despliegue??null,
    alembicTest:c.alcance_reevaluacion?.alembic_test??null};}
export const validarReevaluacion=(c,version)=>version>=2&&c.version_anterior===version-1
  &&!!c.alcance_reevaluacion&&(version!==2||c.version_anterior===1);
async function pedir(r,api,metodo,ruta,{token,secreto,runId,cuerpo,timeout=PRESUPUESTO.timeout_ms,caso}={}){
  if(['POST','PATCH'].includes(metodo)&&ruta!=='/sesiones/'&&timeout===PRESUPUESTO.timeout_ms)
    timeout=PRESUPUESTO.timeout_escritura_ms;
  if(r.solicitudes.length>=PRESUPUESTO.solicitudes_totales&&metodo!=='DELETE')throw Error('PRESUPUESTO_AGOTADO');
  const fila={caso:caso??null,metodo,ruta:ruta.split('?')[0],http:null};r.solicitudes.push(fila);
  try{const inicio=Date.now();if(inicio>=r._limite&&metodo!=='DELETE')throw Error('DURACION_EXCEDIDA');
    const res=await fetch(api+ruta,{method:metodo,redirect:'manual',headers:{
      ...(cuerpo?{'Content-Type':'application/json'}:{}),...(token?{Authorization:`Bearer ${token}`}:{}) ,
      ...(secreto?{'X-Sandbox-Secret':secreto}:{}),...(runId?{'X-Test-Run-Id':runId,'X-Zona-Horaria':'America/Bogota'}:{})},
      body:cuerpo?JSON.stringify(cuerpo):undefined,
      signal:AbortSignal.timeout(Math.max(1,Math.min(timeout,metodo==='DELETE'?timeout:r._limite-inicio)))});
    const b=await res.json().catch(()=>null);
    const fechaServidor=res.headers.get('date');
    Object.assign(fila,{http:res.status,eco:runId?res.headers.get('x-test-run-id')===runId:null,
      fecha_servidor:fechaServidor,
      duracion_ms:Date.now()-inicio,respuesta:ruta==='/sesiones/'?{token_recibido:!!b?.token}:
        {error_code:b?.error_code??null,message:limpiar(b?.message??b?.detail??''),total:b?.total??null,
          ...(res.status>=400?{cuerpo:b}:{} )}});
    return {http:res.status,cuerpo:b,eco:fila.eco,fecha_servidor:fechaServidor};
  }catch(e){fila.tipo_fallo=['TimeoutError','AbortError'].includes(e.name)?'TIMEOUT':'SIN_RED';
    return {http:null,cuerpo:null,eco:false};}}
function rutaHist(inicio,fin,cursor){return `/prediccion/historial/885?fecha_inicio=${inicio}&fecha_fin=${fin}${cursor?`&cursor_paginacion=${encodeURIComponent(cursor)}`:''}`;}
async function historial(r,api,token,secreto,runId,inicio,fin){
  const eventos=[];let cursor=null;
  for(let i=0;i<PRESUPUESTO.paginas_historial;i++){
    const x=await pedir(r,api,'GET',rutaHist(inicio,fin,cursor),{token,secreto,runId});
    if(x.http!==200||x.eco!==true||!Array.isArray(x.cuerpo?.eventos))return {eventos,completo:false,http:x.http,paginas:i+1};
    eventos.push(...x.cuerpo.eventos);cursor=x.cuerpo.cursor_siguiente;
    if(!cursor)return {eventos,completo:true,http:200,paginas:i+1};
  }return {eventos,completo:false,http:200,paginas:PRESUPUESTO.paginas_historial,cursor_pendiente:true};}
function usuarioDelToken(t){try{return String(JSON.parse(Buffer.from(String(t).split('.')[1],'base64url')).sub);}catch{return null;}}
async function newmanUnico(r,c,api,env,token,seleccion){
  const items=COLECCION.item.filter((_,i)=>!!seleccion[CLAVES[i]]&&!(c.version>=2&&i===5));
  if(!items.length)return {};
  const col={...COLECCION,item:structuredClone(items)};
  for(const item of col.item){item.request.header=[{key:'Authorization',value:'Bearer {{token}}'},
    {key:'X-Test-Run-Id',value:'{{run_id}}'},{key:'X-Sandbox-Secret',value:'{{sandbox_secret}}'},
    {key:'X-Zona-Horaria',value:'America/Bogota'},{key:'Content-Type',value:'application/json'}];
    item.event=[{listen:'test',script:{type:'text/javascript',exec:[
      "const n=pm.response.code>=500?Number(pm.environment.get('consecutivos_5xx')||0)+1:0;pm.environment.set('consecutivos_5xx',String(n));",
      "if((pm.response.code===403&&/clave|secreto|sandbox/i.test(pm.response.text()))||n>=3)postman.setNextRequest(null);",
      "pm.test('HTTP recibido',()=>pm.expect(pm.response.code).to.be.above(0));",
      "pm.test('Eco de RUN',()=>pm.expect(pm.response.headers.get('X-Test-Run-Id')).to.eql(pm.environment.get('run_id')));"
    ]}}];}
  const cuerpo=(e,i)=>({id_resultado_inferencia:e.id_resultado_inferencia,id_activo_biologico:885,
    estado_retroalimentacion:'CORRECTO',...(i===0?{timestamp_retroalimentacion:new Date(Date.parse(e.fecha_evento)-DIAS).toISOString()}:{} )});
  const valores={base_url:api,token,run_id:c.runId,sandbox_secret:env.QA_SANDBOX_SECRET,consecutivos_5xx:'0'};
  CLAVES.forEach((k,i)=>{if(seleccion[k])valores[`cuerpo_${['214','89','90','90h','91','120a','120b'][i]}`]=JSON.stringify(cuerpo(seleccion[k],i));});
  const environment={values:Object.entries(valores).map(([key,value])=>({key,value,enabled:true}))};
  let error,summary;try{[error,summary]=await new Promise(ok=>require(newmanDir()).run({collection:col,environment,
    reporters:['cli'],silent:true,timeoutRequest:PRESUPUESTO.timeout_escritura_ms,timeout:Math.max(1,r._limite-Date.now()),
    ignoreRedirects:true,color:'off'},(e,s)=>ok([e,s])));}catch(e){error=e;}
  const ejec={};const reporte={herramienta:'Newman',version:r.herramientas.newman.version,error:error?limpiar(error.message):null,
    solicitudes:[],fallos:(summary?.run?.failures??[]).map(f=>({tipo:f.error?.name??'Error',mensaje:limpiar(f.error?.message)}))};
  let consecutivos=0;
  for(const ex of summary?.run?.executions??[]){let b=null,enviado=null;
    try{b=JSON.parse(ex.response.stream.toString('utf8'));}catch{}
    try{enviado=JSON.parse(ex.request.body.raw);}catch{}
    const n=ex.item?.name,idx=NOMBRES.indexOf(n),caso=idx===0?CASOS[0]:idx<=4?CASOS[1]:idx===5?CASOS[3]:CASOS[4];
    const http=ex.response?.code??null;
    const eco=ex.response?.headers?.get?.('x-test-run-id')===c.runId||
      ex.response?.header?.find?.(h=>String(h.key).toLowerCase()==='x-test-run-id')?.value===c.runId;
    const fila={caso,nombre:n,metodo:'POST',ruta:'/prediccion/retroalimentacion',http,eco,
      herramienta:'Newman',resultado:enviado?.id_resultado_inferencia??null,
      respuesta:{id_retroalimentacion:b?.id_retroalimentacion??null,
        fecha_retroalimentacion:b?.fecha_retroalimentacion??null,error_code:b?.error_code??null,
        message:limpiar(b?.message??'')},duracion_ms:ex.response?.responseTime??null};
    r.solicitudes.push(fila);reporte.solicitudes.push({...fila,aserciones:(ex.assertions??[]).map(a=>({nombre:a.assertion,error:a.error?.message??null}))});
    ejec[n]={http,cuerpo:b,enviado,eco,nombre:n};
    consecutivos=http>=500?consecutivos+1:0;
    if(consecutivos>=3&&!r.problemas_tecnicos.includes('TRES_5XX_CONSECUTIVOS'))r.problemas_tecnicos.push('TRES_5XX_CONSECUTIVOS');
    if(http===403&&/clave|secreto|sandbox/i.test(String(b?.message??b?.detail??'')))r.problemas_tecnicos.push('CLAVE_403');
  }
  r.herramientas.newman.iteraciones=summary?.run?.stats?.iterations?.total??(summary?1:0);
  r.herramientas.newman.solicitudes=reporte.solicitudes.length;
  r.herramientas.newman.aserciones=reporte.solicitudes.reduce((v,x)=>v+x.aserciones.length,0);
  if(error)r.problemas_tecnicos.push(`Newman: ${limpiar(error.message)}`);
  const secretos=[token,env.QA_SANDBOX_SECRET,env.QA_COMMON_PASSWORD,env.QA_ADMIN_PASSWORD,env.QA_VETERINARIO_EMAIL,env.QA_ADMIN_EMAIL];
  const json=sanear(JSON.stringify(reporte,null,2),secretos),sub=path.join(c.directorio,'newman');
  fs.mkdirSync(sub,{recursive:true});fs.writeFileSync(path.join(sub,'newman-G070.json'),json);
  fs.writeFileSync(path.join(sub,'newman-G070.html'),`<!doctype html><html lang="es"><meta charset="utf-8"><title>Newman G070</title><pre>${html(json)}</pre></html>`);
  r.evidencias.push('newman/newman-G070.json','newman/newman-G070.html');return ejec;
}
const retro=(eventos,id,usuario)=>eventos.filter(e=>e.tipo_evento==='RETROALIMENTACION'
  &&String(e.id_resultado_inferencia)===String(id)
  &&String(e.payload?.id_usuario_veterinario)===String(usuario));
const respuestaE9=(p,e)=>e9(p,e?.id_resultado_inferencia,e?.fecha_evento);
function incidencia(caso,descripcion){const severidad=[CASOS[2],CASOS[3],CASOS[4]].includes(caso)?'MEDIA':'ALTA';
  return {id:`INC-M04-G070-${caso.slice(-3)}-01`,caso,descripcion,
    severidad,justificacion_severidad:caso===CASOS[2]?
      'Impacto parcial: el Administrador no puede configurar la ventana desde M09; los 90 días por defecto y los rechazos funcionan, pero cambiarla requiere un script con acceso directo a BD, fuera del producto; sin riesgo demostrado para los datos':
      caso===CASOS[3]?'Impacto parcial: el veterinario no puede registrar una retroalimentación justificada fuera de plazo; cambiar la ventana global por script afectaría a todos los resultados; sin riesgo demostrado para los datos':
      severidad==='ALTA'?'Funcionalidad relevante bloqueada sin alternativa pública':
      'Mensaje incompleto que dificulta identificar el vencimiento y solicitar asistencia',
    certeza:'CONFIRMADA',equipo_responsable:'Desarrollo',
    fundamento_derivacion:'Primera discrepancia comprobada en API pública de TEST; causa raíz no determinada'};}
function decidir(r,caso,estado,motivo){r.casos[caso]={estado,motivo};if(estado==='RECHAZADO')
  r.incidencias.push(incidencia(caso,motivo));}
function detallePost(p){return p?`HTTP ${p.http??'—'}, código ${p.cuerpo?.error_code??'—'}, mensaje ${limpiar(p.cuerpo?.message??'—')}`:'Sin POST';}
const RUTA_CONFIG='/configuracion/parametros-retroalimentacion';
const RUTA_AMPLIAR='/prediccion/retroalimentacion/ampliaciones';
const valorVentana=x=>Number((Array.isArray(x?.cuerpo)?x.cuerpo:[])
  .find(p=>p.nombre==='ventana_retroalimentacion_dias')?.valor);
const cuerpoRetro=e=>({id_resultado_inferencia:e.id_resultado_inferencia,
  id_activo_biologico:885,estado_retroalimentacion:'CORRECTO'});
async function adicionalesV2(r,c,api,env,token,admin,seleccion,base,inicio,fin,desde){
  const opts=(t,caso,cuerpo)=>({token:t,secreto:env.QA_SANDBOX_SECRET,runId:c.runId,caso,cuerpo});
  const c216=CASOS[2],c217=CASOS[3],pasos=[],fallas=[],tecnicos=[];
  const paso=async(nombre,metodo,ruta,t,caso,cuerpo)=>{
    const x=await pedir(r,api,metodo,ruta,opts(t,caso,cuerpo));
    if(r.solicitudes.at(-1)?.ruta===ruta.split('?')[0])r.solicitudes.at(-1).nombre=nombre;
    pasos.push({nombre,metodo,ruta,http:x.http,eco:x.eco,
      error_code:x.cuerpo?.error_code??null,valor:ruta===RUTA_CONFIG?valorVentana(x):null,
      cuerpo:x.http>=400?x.cuerpo:null});return x;};
  const config=()=>paso('GET configuración','GET',RUTA_CONFIG,admin,c216);
  const patch=(nombre,valor,t=admin)=>paso(nombre,'PATCH',RUTA_CONFIG,t,c216,
    {parametros:{ventana_retroalimentacion_dias:valor}});
  const validar=(nombre,x,esperado,valor)=>{
    if(x.http==null||x.eco!==true||x.http>=500){tecnicos.push(`${nombre}: sin respuesta, eco o servicio`);return;}
    if(x.http!==esperado||valor!==undefined&&valorVentana(x)!==valor)
      fallas.push(`${nombre}: HTTP ${x.http}, valor ${valorVentana(x)}`);};
  const inicial=await config();validar('GET inicial',inicial,200,90);
  for(const [nombre,valor] of [['6',6],['366',366],['decimal',7.5]]){
    const x=await patch(`PATCH ${nombre}`,valor);validar(`PATCH ${nombre}`,x,400);}
  const ajeno=await paso('PATCH ajeno','PATCH',RUTA_CONFIG,admin,c216,{parametros:{parametro_no_admitido:8}});
  validar('PATCH ajeno',ajeno,400);
  for(const valor of [7,8,365]){
    const x=await patch(`PATCH ${valor}`,valor);validar(`PATCH ${valor}`,x,200,valor);
    const g=await config();validar(`GET ${valor}`,g,200,valor);}
  const w91=seleccion.d91;
  if(w91){const x=await paso('RF-72 W91 con 365','POST','/prediccion/retroalimentacion',token,c216,cuerpoRetro(w91));
    validar('RF-72 W91 con 365',x,201);r.v2_registro_216={http:x.http,id:w91.id_resultado_inferencia};}
  else tecnicos.push('W91 libre ausente: no se puede verificar lectura dinámica de RF-72');
  // La restauración se intenta incluso cuando una comprobación anterior falla.
  const restaurar=await patch('PATCH restaurar 90',90);
  const confirmado=await config();
  if(restaurar.http!==200||restaurar.eco!==true||valorVentana(confirmado)!==90)
    tecnicos.push(`Restauración 90 sin confirmar: PATCH ${restaurar.http??'—'}, GET ${valorVentana(confirmado)}`);
  const vet=await patch('PATCH Veterinario 90',90,token);validar('PATCH Veterinario',vet,403);
  const final=await config();if(valorVentana(final)!==90)tecnicos.push('Ventana final distinta de 90');
  const huboCambio=pasos.some(x=>x.metodo==='PATCH'&&x.http===200&&x.nombre!=='PATCH Veterinario 90');
  r.v2_config={pasos,restaurada:valorVentana(final)===90&&(restaurar.http===200||!huboCambio)};
  if(fallas.length)decidir(r,c216,'RECHAZADO',fallas.join('; '));
  else if(tecnicos.length)decidir(r,c216,'NO_CONCLUYENTE',tecnicos.join('; '));
  else decidir(r,c216,'APROBADO','Rango, validaciones, RBAC, GET y lectura dinámica de RF-72 comprobados; ventana restaurada a 90');
  if(!r.v2_config.restaurada){decidir(r,c217,'NO_CONCLUYENTE','La ventana global no quedó confirmada en 90 antes de la ampliación');return;}
  const a=seleccion.d120a,b=seleccion.d120b;
  if(!a||!b){decidir(r,c217,'NO_CONCLUYENTE','Faltan dos resultados vencidos y libres de retroalimentación previa');return;}
  const pasos217=[],f217=[],t217=[];
  const p217=async(nombre,metodo,ruta,t,cuerpo)=>{
    const x=await pedir(r,api,metodo,ruta,opts(t,c217,cuerpo));
    if(r.solicitudes.at(-1)?.ruta===ruta.split('?')[0])r.solicitudes.at(-1).nombre=nombre;
    pasos217.push({nombre,metodo,ruta,http:x.http,eco:x.eco,error_code:x.cuerpo?.error_code??null,
      cuerpo:x.http>=400?x.cuerpo:null});return x;};
  const expect=(nombre,x,http,codigo)=>{
    if(x.http==null||x.eco!==true||x.http>=500)t217.push(`${nombre}: sin respuesta, eco o servicio`);
    else if(x.http!==http||codigo&&x.cuerpo?.error_code!==codigo)
      f217.push(`${nombre}: HTTP ${x.http}, código ${x.cuerpo?.error_code??'—'}`);};
  const previo=await p217('A antes','POST','/prediccion/retroalimentacion',token,cuerpoRetro(a));
  expect('A antes',previo,422,'FUERA_DE_VENTANA_TEMPORAL');
  const justificacion='Ampliación QA G070 para verificar excepción puntual RF-72';
  const solicitud={id_resultado_inferencia:a.id_resultado_inferencia,dias_habilitados:5,justificacion};
  const ampliacion=await p217('ampliar A','POST',RUTA_AMPLIAR,admin,solicitud);
  expect('ampliar A',ampliacion,201);
  const idAdmin=usuarioDelToken(admin);
  if(ampliacion.http===201){const v=ampliacion.cuerpo;
    if(String(v?.id_resultado_inferencia)!==String(a.id_resultado_inferencia)
      ||String(v?.id_usuario_autorizador)!==String(idAdmin)
      ||v?.justificacion!==justificacion||Date.parse(v?.fecha_limite)<=Date.now())
      f217.push('Respuesta de ampliación sin resultado, autor, justificación o fecha límite válidos');}
  const aud=await p217('auditoría ampliación','GET',
    `/prediccion/auditoria?tipo_evento=VENTANA_RETROALIMENTACION_AMPLIADA&fecha_desde=${encodeURIComponent(desde)}&id_referencia=${encodeURIComponent(a.id_resultado_inferencia)}&por_pagina=200`,admin);
  const eventos=aud.cuerpo?.items??[];
  const evento=eventos.find(e=>e.tipo_evento==='VENTANA_RETROALIMENTACION_AMPLIADA'
    &&String(e.id_referencia)===String(a.id_resultado_inferencia));
  if(aud.http!==200||aud.eco!==true||!Array.isArray(eventos)
    ||Number(aud.cuerpo?.total??Infinity)>eventos.length)t217.push('Auditoría de ampliación no comprobable');
  else if(!evento||String(evento.id_usuario)!==String(idAdmin)
    ||String(evento.payload_evento?.id_usuario_autorizador)!==String(idAdmin)
    ||evento.payload_evento?.justificacion!==justificacion
    ||String(evento.payload_evento?.id_resultado_inferencia)!==String(a.id_resultado_inferencia)
    ||Number(evento.payload_evento?.dias_habilitados)!==5)
    f217.push('Evento RF-73 sin autorizador, justificación o excepción puntual');
  else if(!evento.id_evento)t217.push('Evento RF-73 sin identificador para verificar rollback');
  // Una escritura sin respuesta no se repite. Las lecturas posteriores concilian su efecto.
  const pa=await p217('A después','POST','/prediccion/retroalimentacion',token,cuerpoRetro(a));
  expect('A después',pa,201);
  const pb=await p217('B después','POST','/prediccion/retroalimentacion',token,cuerpoRetro(b));
  expect('B después',pb,422,'FUERA_DE_VENTANA_TEMPORAL');
  const cfg=await p217('global después','GET',RUTA_CONFIG,admin);
  if(cfg.http==null||cfg.http>=500||cfg.eco!==true)t217.push('GET global posterior no comprobable');
  else if(cfg.http!==200||valorVentana(cfg)!==90)f217.push('La ampliación cambió la ventana global');
  for(const [nombre,cuerpo] of [
    ['justificación corta',{...solicitud,justificacion:'corta'}],
    ['días 0',{...solicitud,dias_habilitados:0}],
    ['días 366',{...solicitud,dias_habilitados:366}]]){
    const x=await p217(nombre,'POST',RUTA_AMPLIAR,admin,cuerpo);
    if(x.http==null||x.eco!==true||x.http>=500)t217.push(`${nombre}: sin respuesta, eco o servicio`);
    else if(x.http!==422)f217.push(`${nombre}: HTTP ${x.http}, se esperaba 422`);}
  const noAdmin=await p217('ampliación Veterinario','POST',RUTA_AMPLIAR,token,solicitud);
  expect('ampliación Veterinario',noAdmin,403);
  const posterior=await historial(r,api,token,env.QA_SANDBOX_SECRET,c.runId,inicio,fin);
  if(!posterior.completo){t217.push('Historial posterior incompleto');
    if(estado216(r)==='APROBADO')decidir(r,c216,'NO_CONCLUYENTE','No se comprobó persistencia de W91 con ventana 365');}
  else {const delta=id=>retro(posterior.eventos,id,usuarioDelToken(token)).length-
      retro(base.eventos,id,usuarioDelToken(token)).length;
    if(w91&&delta(w91.id_resultado_inferencia)!==1)
      decidir(r,c216,'RECHAZADO',`RF-72 con ventana 365 respondió 201 pero delta W91=${delta(w91.id_resultado_inferencia)}`);
    if(delta(a.id_resultado_inferencia)!==1||delta(b.id_resultado_inferencia)!==0)
      f217.push(`Persistencia puntual incorrecta: A ${delta(a.id_resultado_inferencia)}, B ${delta(b.id_resultado_inferencia)}`);}
  r.v2_ampliacion={pasos:pasos217,auditoria:{http:aud.http,evento:!!evento,id_evento:evento?.id_evento??null},
    persistencia:posterior.completo?{a:retro(posterior.eventos,a.id_resultado_inferencia,usuarioDelToken(token)).length-
      retro(base.eventos,a.id_resultado_inferencia,usuarioDelToken(token)).length,
      b:retro(posterior.eventos,b.id_resultado_inferencia,usuarioDelToken(token)).length-
      retro(base.eventos,b.id_resultado_inferencia,usuarioDelToken(token)).length}:null};
  if(f217.length)decidir(r,c217,'RECHAZADO',f217.join('; '));
  else if(t217.length)decidir(r,c217,'NO_CONCLUYENTE',t217.join('; '));
  else decidir(r,c217,'APROBADO','A ampliado aceptado; B vencido rechazado; global 90; RF-73, validaciones y RBAC comprobados');
}
const estado216=r=>r.casos[CASOS[2]]?.estado;
function informeV2(c,r){
  const estado=x=>r.casos[x]?.estado??'NO_CONCLUYENTE';
  const decision=r.oficial?(CASOS.some(x=>estado(x)==='RECHAZADO')?'RECHAZADO':'APROBADO'):'NO OFICIAL';
  const esperados=[
    'Fecha del servidor posterior a la inferencia; E7 422 sin persistencia si se admite timestamp anterior.',
    'W89 y W90: 201; W91: 422 FUERA_DE_VENTANA_TEMPORAL sin registro. W90H se observa aparte.',
    'M09 configura 7–365: 6 y 366 rechazados; 7, 8 y 365 aceptados y visibles en GET; decimales y nombres ajenos rechazados; RF-72 usa el nuevo valor; Veterinario no actualiza (403).',
    'Antes de ampliar, A vencido se rechaza. Tras ampliar A por el Administrador, A da 201, B sigue 422 E9, la ventana global sigue en 90, RF-73 registra autor y justificación; entradas inválidas se rechazan y Veterinario recibe 403.',
    'E9 contiene 90 días, id de resultado, fecha límite exacta y contacto al administrador.'
  ];
  const pasos216=r.v2_config?.pasos??[],pasos217=r.v2_ampliacion?.pasos??[];
  const grupos=[r.solicitudes.filter(x=>x.nombre==='G070-214'),
    r.solicitudes.filter(x=>/^G070-215/.test(x.nombre??'')),pasos216,pasos217,
    r.solicitudes.filter(x=>x.nombre==='G070-218-120B')];
  const nombreVencido=n=>n==='G070-217-120A'?`A (${r.semilla.d120a?.dias_backend??'—'} días completos)`:
    n==='G070-218-120B'?`B (${r.semilla.d120b?.dias_backend??'—'} días completos)`:n;
  const descripcion=x=>`${nombreVencido(x.nombre??x.metodo+' '+x.ruta)}: HTTP ${x.http??'sin respuesta'}${x.error_code||x.respuesta?.error_code?`, ${x.error_code??x.respuesta.error_code}`:''}${x.valor!=null&&!Number.isNaN(x.valor)?`, valor ${x.valor}`:''}`;
  const detalle=CASOS.map((x,i)=>`### ${x} — ${estado(x)}\n\n- **Qué se hizo:** ${grupos[i].length?grupos[i].map(descripcion).join('; '):'No hubo operación comprobable.'}\n- **Qué se esperaba:** ${esperados[i]}\n- **Qué se observó:** ${limpiar(r.casos[x]?.motivo??'Sin evaluación')}.\n- **Por qué ${estado(x)}:** ${estado(x)==='APROBADO'?'Las comprobaciones públicas y la persistencia observada satisfacen el oráculo indicado.':estado(x)==='RECHAZADO'?'La discrepancia pública indicada incumple el oráculo.':'La evidencia indicada no permite cerrar el caso.'}\n`).join('\n');
  const semilla=Object.entries(r.semilla).map(([k,v])=>`| ${k==='d120a'?'vencido A':k==='d120b'?'vencido B':k} | ${v.id??'—'} | ${v.fecha??'—'} | ${v.dias_backend??'—'} | ${v.horas??'—'} | ${v.en_tramo?'sí':'no'} |`).join('\n');
  const intentos=r.solicitudes.filter(x=>x.herramienta==='Newman'||['POST','PATCH'].includes(x.metodo)&&x.ruta!=='/sesiones/')
    .map(x=>`| ${x.caso??'—'} | ${nombreVencido(x.nombre??x.metodo+' '+x.ruta)} | ${x.http??'sin respuesta'} | ${limpiar(x.respuesta?.error_code??'—')} | ${limpiar(x.respuesta?.message??'—')} |`).join('\n');
  const incidencias=r.incidencias.map(x=>`- **${x.id} — ${x.severidad}, ${x.certeza}; atención inicial ${x.equipo_responsable}.** ${limpiar(x.descripcion)}. ${limpiar(x.justificacion_severidad)}. Derivación por la primera discrepancia pública, sin causa raíz atribuida.`).join('\n')||'Ninguna incidencia de producto nueva.';
  const cambio=CASOS.slice(2,4).map(x=>`| ${x} | RECHAZADO | ${estado(x)} | ${r.oficial&&estado(x)==='APROBADO'?'CORREGIDA':r.oficial&&estado(x)==='RECHAZADO'?'PERSISTE':'PENDIENTE'} |`).join('\n');
  const evidencias=[...new Set([...r.evidencias,'resultado.json',informeNombre(c.version)])];
  return `# TC-M04-G070 — reevaluación V2 ${decision}\n\n## Identificación\n\nGrupo G070; ${CASOS.join(', ')}; RF-72; versión ${c.version}; ${c.runId}; ambiente ${r.ambiente}; autorización ${c.referencia}. Reevaluación de V1 por issue #865 / PR #871; commit de código desplegado: ${c.commit??'no verificado'}; Alembic de TEST informado en contexto: ${c.alembicTest??'no informado'}. Node.js y Newman ${r.herramientas.newman.version??'no disponible'}; API pública.\n\n## Decisión del caso\n\n| Caso | Veredicto | Motivo |\n|---|---|---|\n${CASOS.map(x=>`| ${x} | ${estado(x)} | ${limpiar(r.casos[x]?.motivo??'Sin evaluación')} |`).join('\n')}\n\nRUN oficial: ${r.oficial?'sí':'no'}. Qué falta: ${r.oficial?'nada para la decisión de esta versión':'resolver los casos no concluyentes o el cierre técnico'}.\n\n## V1 → V2\n\n| Caso | V1 | V2 | Incidencia |\n|---|---|---|---|\n| TC-M04-214 | APROBADO | ${estado(CASOS[0])} | Regresión |\n| TC-M04-215 | APROBADO | ${estado(CASOS[1])} | Regresión |\n${cambio}\n| TC-M04-218 | APROBADO | ${estado(CASOS[4])} | Regresión |\n\nDos intentos técnicos anteriores V2: el primero quedó en preflight, sin peticiones; el segundo tuvo 214–216 APROBADO y 217–218 NO_CONCLUYENTE por selección de datos fuera del tramo, con DELETE 200 y configuración restaurada a 90. La reevaluación V2 continúa.\n\nINC-M04-G070-216-01 e INC-M04-G070-217-01 se consideran corregidas solo cuando sus respectivos casos quedan APROBADOS en un RUN oficial de TEST.\n\n## Precondición de datos\n\nCOMMIT de la semilla: ${c.semillaCommit??'no informado; verificar con responsable QA antes del RUN'}. Hora de descubrimiento: ${r.hora_descubrimiento??'no registrada'}. La antigüedad se calcula frente a la hora observada del servidor; el sandbox fija now() al inicio. A (${r.semilla.d120a?.dias_backend??'—'} días completos) y B (${r.semilla.d120b?.dias_backend??'—'} días completos) deben estar vencidos, libres de retroalimentación previa y ser distintos de los resultados de 215.\n\n| Tramo | Resultado | Inferencia | Días completos | Horas | Disponible |\n|---|---|---|---|---|---|\n${semilla}\n\n## Detalle por caso\n\n${detalle}\n## Tabla de intentos\n\n| Caso | Operación | HTTP | Código | Mensaje |\n|---|---|---|---|---|\n${intentos}\n\n## Observaciones y límites\n\nOBS-M04-G070-215: W90H (${r.semilla.d90h?.horas??'—'} h) recibió HTTP ${r.solicitudes.find(x=>x.nombre==='G070-215-90H')?.http??'—'}. La frontera de 90 días y 12 horas está pendiente de definición entre QA y Análisis; no cambia el veredicto de 215. La caducidad de la ampliación no puede verificarse en un único RUN de sandbox: now() está fijo y la API solo autoriza al menos un día desde el presente. No afecta el veredicto de 217. La semilla disponible no contiene resultados de 7/8 ni 365/366 días; los límites del parámetro se comprueban por PATCH/GET y el efecto en el registro con W91 al pasar de 90 a 365.\n\n## Incidencias de producto\n\n${incidencias}\n\n## Problemas técnicos y análisis de causas\n\n${r.problemas_tecnicos.map(limpiar).join('; ')||'Ninguno.'} La derivación inicial se basa en la primera discrepancia API comprobada; causa raíz no determinada. README documenta una revisión previa de src/configuration/infrastructure/routers/parametros_retroalimentacion_router.py, src/configuration/application/use_cases/configuracion_global/parametros_retroalimentacion_use_case.py, src/prediction/infrastructure/routers/retroalimentacion_clinica_router.py, src/prediction/application/use_cases/retroalimentacion/ampliar_ventana_retroalimentacion_use_case.py y alembic/versions/6bd01d026ac4_rf72_ampliacion_ventana_retroalimentacion.py. En ORD-G070-011 no se releyó código funcional.\n\n## Cierre y rollback\n\nIntento ${c.intento}; solicitudes ${r.solicitudes.length}/${PRESUPUESTO.solicitudes_totales}. DELETE HTTP ${r.cierre.run.cierre_http??'—'}. Rollback ${r.cierre.rollback.verificado?'verificado':'no verificado'}: ${r.cierre.rollback.motivo}. La configuración se restauró por PATCH y GET antes de 217: ${r.v2_config?.restaurada?'sí':'no confirmado'}.\n\n## Conclusión y acciones\n\n${decision==='APROBADO'?'Los cinco casos cumplen la reevaluación. Registrar como corregidas las incidencias 216 y 217 y acordar con Análisis la frontera observada en 215.':decision==='RECHAZADO'?'Derivar las discrepancias confirmadas a Desarrollo y conservar la evidencia del RUN; acordar la frontera de 215 con Análisis.':'Resolver los impedimentos técnicos y repetir la reevaluación con autorización particular.'}\n\n## Herramientas y evidencias\n\nNewman: ${r.herramientas.newman.iteraciones} iteración; ${r.herramientas.newman.solicitudes} solicitudes; ${r.herramientas.newman.aserciones} aserciones. Sin UI obligatoria según los casos originales.\n\n${evidencias.map(x=>`- ${x}`).join('\n')}\n`;
}
export function informe(c,r){
  if(c.version>=2)return informeV2(c,r);
  const decision=r.oficial?(CASOS.some(x=>r.casos[x].estado==='RECHAZADO')?'RECHAZADO':'APROBADO'):'NO OFICIAL';
  const post=k=>r.solicitudes.find(x=>x.nombre===`G070-${k}`);
  const id=k=>r.semilla[k]?.id??'resultado no disponible';
  const estado=i=>r.casos[CASOS[i]].estado;
  const observacionPost=k=>{const x=post(k);return x?`${id(({214:'reciente', '215-89':'d89','215-90':'d90','215-90H':'d90h','215-91':'d91','217-120A':'d120a','218-120B':'d120b'})[k])}: HTTP ${x.http??'—'}${x.respuesta?.error_code?` ${x.respuesta.error_code}`:''}`:'sin POST';};
  const detalles=[
    {hizo:`Se envió POST /prediccion/retroalimentacion para ${id('reciente')} con timestamp_retroalimentacion anterior a su inferencia (${r.semilla.reciente?.fecha??'—'}); se contrastó la respuesta con historial y auditoría.`,
      esperaba:'E7: HTTP 422 sin persistencia; si la API ignora el campo, HTTP 201 con fecha del servidor posterior a la inferencia y distinta de la enviada (RF-72, línea 4166; E7, líneas 4272–4276).',
      observo:`${observacionPost('214')}; fecha_retroalimentacion del servidor ${post('214')?.respuesta?.fecha_retroalimentacion??'—'}. ${estado(0)==='APROBADO'?'resultado.json confirma fecha distinta de la enviada y registro en historial y auditoría.':'La comprobación de fecha y registro depende del resultado de este caso.'}`,
      porque:'El campo anterior no alteró la fecha almacenada: la asignación del servidor satisface la consistencia temporal y la alternativa admitida por el oráculo.'},
    {hizo:`Se registraron resultados de 89 días (${id('d89')}; ${r.semilla.d89?.horas??'—'} h), 90 días (${id('d90')}; ${r.semilla.d90?.horas??'—'} h) y se intentó uno de 91 días (${id('d91')}; ${r.semilla.d91?.horas??'—'} h). Se observó aparte el de 90 días más 12 horas (${id('d90h')}; ${r.semilla.d90h?.horas??'—'} h).`,
      esperaba:'89 y 90 días: HTTP 201; 91 días: HTTP 422 E9 y sin registro. El de 90 días más 12 horas es observación, sin oráculo fijado (RF-72, líneas 4096–4108; E9, líneas 4285–4297; CA-13, líneas 4390–4391).',
      observo:`89 d: ${observacionPost('215-89')}; 90 d: ${observacionPost('215-90')}; 91 d: ${observacionPost('215-91')}, mensaje «${limpiar(post('215-91')?.respuesta?.message??'—')}». ${estado(1)==='APROBADO'?'Sin registro ni auditoría de registro para 91 días según resultado.json.':''} Observación 90 d + 12 h: ${observacionPost('215-90H')}.`,
      porque:'Los tres límites con oráculo dieron la respuesta exigida y el vencido no se persistió. RF-72 expresa la ventana en días calendario sin precisar la frontera de 90 días más 12 horas; ese intento se informa por separado. Desarrollo indicó en issue #865 que aún cuenta como 90 días completos; QA y Análisis definirán la frontera.'},
    {hizo:'El Administrador consultó GET /openapi.json y GET /configuracion/parametros para buscar lectura y cambio de ventana_retroalimentacion_dias desde M09.',
      esperaba:'M09 debe permitir al Administrador configurar de 7 a 365 días, con rechazos de 6 y 366 y comportamiento de 7/8 y 365/366; la ausencia de operación pública acredita la función ausente (RF-72, líneas 4102–4104).',
      observo:`GET /openapi.json: HTTP ${r.solicitudes.find(x=>x.ruta==='/openapi.json')?.http??'—'}; GET /configuracion/parametros: HTTP ${r.solicitudes.find(x=>x.ruta==='/configuracion/parametros')?.http??'—'}. ${estado(2)==='RECHAZADO'?'No se halló ruta de lectura o cambio de esa ventana ni el parámetro en la respuesta de configuración.':`Resultado de superficie: ${limpiar(r.observaciones.find(x=>x.startsWith('Superficie:'))??'no determinado')}.`}`,
      porque:'No hay control público para ejecutar los límites configurables. La lectura dinámica del parámetro por el backend no reemplaza la configuración administrativa: hoy solo consta un script fuera de línea con conexión directa a BD.'},
    {hizo:`Se intentó registrar el resultado vencido ${id('d120a')} y se revisó OpenAPI en busca de una ampliación justificada por resultado; ${id('d120b')} sirvió de segundo control vencido.`,
      esperaba:'Antes de la ampliación: 422 E9; después, solo el resultado ampliado debe aceptar 201, con justificación y auditoría, mientras el segundo sigue rechazado. Sin operación expuesta, se constata la funcionalidad ausente (RF-72, línea 4110).',
      observo:`Primer resultado: ${observacionPost('217-120A')}; segundo: ${observacionPost('218-120B')}. ${estado(3)==='RECHAZADO'?'resultado.json confirma ausencia de registro en ambos y falta de operación de ampliación por resultado en OpenAPI.':'La ausencia de registro y de ampliación depende del resultado de este caso.'}`,
      porque:'El rechazo inicial cumple el control previo, pero falta el mecanismo puntual que permitiría registrar una excepción justificada y auditable.'},
    {hizo:`Se inspeccionó el cuerpo del POST vencido para ${id('d120b')} y se comparó su fecha límite con fecha_inferencia ${r.semilla.d120b?.fecha??'—'} más 90 días en la zona del usuario.`,
      esperaba:'E9 debe indicar días de ventana, identificador del resultado, fecha exacta de vencimiento y contacto al administrador (E9, línea 4294).',
      observo:`${observacionPost('218-120B')}; mensaje «${limpiar(post('218-120B')?.respuesta?.message??'—')}».`,
      porque:`${estado(4)==='APROBADO'?'El mensaje contiene los 90 días, el identificador, la fecha de vencimiento y el contacto exigidos; 2026-09-29 coincide con fecha_inferencia más 90 días en America/Bogota.':'La aprobación exige que el mensaje reúna todos los datos y que la fecha coincida con el cálculo en America/Bogota.'}`}
  ];
  const porCaso=CASOS.map((x,i)=>{const d=detalles[i];return `### ${x} — ${estado(i)}\n\n- **Qué se hizo:** ${d.hizo}\n- **Qué se esperaba:** ${d.esperaba}\n- **Qué se observó:** ${d.observo}\n- **Por qué ${estado(i)}:** ${estado(i)===(i===2||i===3?'RECHAZADO':'APROBADO')?d.porque:`${d.porque} Resultado de esta ejecución: ${limpiar(r.casos[x].motivo)}.`}\n`;}).join('\n');
  const semilla=Object.entries(r.semilla).map(([k,x])=>`| ${k} | ${x.id??'—'} | ${x.fecha??'—'} | ${x.dias_backend??'—'} | ${x.horas??'—'} | ${x.en_tramo?'sí':'no'} |`).join('\n');
  const observada=(r.semilla_observada??[]).map(x=>`| ${x.id} | ${x.fecha} | ${x.dias_backend} | ${x.horas} |`).join('\n');
  const persistio={'G070-214':estado(0)==='APROBADO'?'sí':'no comprobado','G070-215-89':estado(1)==='APROBADO'?'sí':'no comprobado','G070-215-90':estado(1)==='APROBADO'?'sí':'no comprobado','G070-215-90H':'no comprobado','G070-215-91':estado(1)==='APROBADO'?'no':'no comprobado','G070-217-120A':estado(3)==='RECHAZADO'?'no':'no comprobado','G070-218-120B':estado(4)==='APROBADO'?'no':'no comprobado'};
  const intentos=r.solicitudes.filter(x=>x.herramienta==='Newman').map(x=>`| ${x.nombre} | ${x.resultado??'—'} | ${x.http??'—'} | ${limpiar(x.respuesta?.error_code||'—')} | ${limpiar(x.respuesta?.message||'—')} | ${persistio[x.nombre]??'no comprobado'} |`).join('\n');
  const observaciones=`OBS-M04-G070-215 — El resultado de 90 días y 12 horas (${r.semilla.d90h?.horas??'—'} h, más de 90×24 h) recibió HTTP ${post('215-90H')?.http??'—'}. Desarrollo indicó en issue #865 que este intervalo aún cuenta como 90 días completos. RF-72 expresa la ventana en días calendario sin precisar esta frontera; QA y Análisis definirán el criterio.\n\nEl backend lee el parámetro de ventana dinámicamente; hoy el cambio solo consta por script fuera de línea con acceso directo a BD. Esta lectura de código es hipótesis de implementación, no comprobación de configuración desde M09.`;
  const incidencias=r.incidencias.map(x=>{const razon=x.caso===CASOS[2]?'La ventana no se puede configurar desde M09 por el Administrador. Los 90 días por defecto y los rechazos funcionan, pero cambiarla exige un script técnico con acceso a BD fuera del producto; sin riesgo demostrado para los datos.':x.caso===CASOS[3]?'No existe la excepción por resultado: un veterinario no puede registrar retroalimentación justificada fuera de plazo; cambiar la ventana global por script afectaría a todos los resultados; sin riesgo demostrado para los datos.':limpiar(x.justificacion_severidad);const sev=[CASOS[2],CASOS[3]].includes(x.caso)?'MEDIA':x.severidad;return `- **${x.id} — ${sev}; certeza ${x.certeza} en la superficie pública de ${r.ambiente}; atención inicial ${x.equipo_responsable}.** ${razon} Primera discrepancia: ${limpiar(x.descripcion)}. La derivación atiende la API pública y no atribuye causa raíz.`;}).join('\n')||'Ninguna confirmada.';
  const evidencias=[...new Set([...r.evidencias,'resultado.json',informeNombre(c.version)])];
  return `# TC-M04-G070 — ${decision}\n\n## Identificación\n\nGrupo G070; casos ${CASOS.join(', ')}; RF-72; versión ${c.version}; RUN ${c.runId}; ambiente ${r.ambiente}; autorización ${c.referencia}; commit revisado origin/test daefc3a5. Node.js y Newman ${r.herramientas.newman.version??'no disponible'}; solo API.\n\n## Decisión del caso\n\n| Caso | Veredicto | Decisión en lenguaje llano |\n|---|---|---|\n${CASOS.map((x,i)=>`| ${x} | ${estado(i)} | ${['La fecha asignada por el servidor cumple la regla temporal.','Los límites de 89, 90 y 91 días cumplen la regla.','Falta configurar la ventana desde M09.','Falta ampliar la ventana para un resultado concreto.','El rechazo explica el vencimiento y cómo pedir asistencia.'][i]} |`).join('\n')}\n\nRUN oficial: ${r.oficial?'sí':'no'}.\n\nQué falta: ${r.oficial?'nada':'completar la evaluación autorizada y el cierre comprobable'}.\n\n## Precondición de datos (semilla de ventana)\n\nAntigüedad calculada al descubrimiento como floor((hora actual UTC − fecha_inferencia)/24 h), equivalente a .days del backend. ${c.revisionQa?'Según el contexto de la semilla, su COMMIT fue el 2026-10-29 13:34:38 UTC y el RUN comenzó a las 13:38 UTC. Las fechas sembradas son anteriores al alta del activo 885 (2026-10-24) y al registro de la versión 43 (2026-10-21); ningún caso de G070 verifica esa coherencia histórica.':'La semilla retroactiva debe insertarse el mismo dia y el RUN ocurrir antes de 10 horas; comprobar la coherencia historica con el alta del activo y la version del modelo.'}\n\n| Tramo | Resultado | Fecha inferencia | Días backend | Horas | En tramo |\n|---|---|---|---|---|---|\n${semilla}\n\nCandidatos observados de 88 a 121 días, incluidos los que quedaron fuera de tramo:\n\n| Resultado | Fecha inferencia | Días backend | Horas |\n|---|---|---|---|\n${observada}\n\n## Detalle por caso\n\n${porCaso}\n## Intentos Newman\n\n| Nombre | Resultado | HTTP | Código | Mensaje | Persistió |\n|---|---|---|---|---|---|\n${intentos}\n\n## Observaciones\n\n${observaciones}\n\n## Incidencias de producto\n\n${incidencias}\n\n## Problemas técnicos y análisis de causas\n\n${r.problemas_tecnicos.map(limpiar).join('; ')||'Ninguno.'} Hipótesis de causa, no confirmada: configurar_parametros_mlops_use_case.py:6 y scripts/configurar_parametros_dev14.py muestran configuración por script sin endpoint; en origin/test daefc3a5 no se identificó operación de ampliación. La revision de codigo previa, citada en README, incluye: src/configuration/application/use_cases/configuracion_global/configurar_parametros_mlops_use_case.py, scripts/configurar_parametros_dev14.py, src/configuration/infrastructure/routers/configuracion_global_router.py, src/prediction/application/use_cases/retroalimentacion/registrar_retroalimentacion_use_case.py. En este cierre no se releyeron esos archivos funcionales. La derivación inicial no atribuye causa raíz.\n\n## Cierre y rollback\n\nIntento ${c.intento}; solicitudes ${r.solicitudes.length}/${PRESUPUESTO.solicitudes_totales}. DELETE HTTP ${r.cierre.run.cierre_http??'—'}. Rollback ${r.cierre.rollback.verificado?'verificado':'no verificado'}: ${r.cierre.rollback.motivo}. Las lecturas posteriores pueden generar HISTORIAL_CONSULTADO fuera del sandbox.\n\n## Conclusión y acciones\n\n${decision==='RECHAZADO'?'G070 RECHAZADO por 216 y 217: faltan las funciones administrativas. 214, 215 y 218 cumplen. Desarrollo debe exponer la configuración de la ventana en M09 y la excepción por resultado auditada en RF-73. Desarrollo y el responsable QA deben confirmar la frontera observada en 215.':decision==='APROBADO'?'Los cinco casos cumplen sus oráculos.':'Resolver impedimentos y repetir solo la evaluación autorizada.'}\n\n## Herramientas y evidencias\n\nNewman: ${r.herramientas.newman.iteraciones} iteración; ${r.herramientas.newman.solicitudes} solicitudes; ${r.herramientas.newman.aserciones} aserciones. Sin UI obligatoria.\n\n${evidencias.map(x=>`- ${x}`).join('\n')}\n${c.revisionQa?'\n## Revisión QA (2026-10-29)\n\nSe ajustaron estructura, datos por caso, observación en lenguaje llano y severidades documentales ALTA → MEDIA con justificación de impacto. Los veredictos, resultado.json y newman/ no cambiaron. resultado.json conserva la severidad ALTA original como evidencia histórica; la valoración vigente para estas dos incidencias es MEDIA en este informe.\n':''}`;
}
export async function evaluar(c,{env=leerEnv(),newmanVersion=versionNewman()}={}){
  const r={grupo:'G070',run_id:c.runId,version:c.version,intento:c.intento,referencia:c.referencia,
    ambiente:c.ensayo?'loopback local':'TEST',casos:Object.fromEntries(CASOS.map(x=>[x,{estado:'NO_CONCLUYENTE',motivo:'No evaluado'}])),
    comprobaciones:[],solicitudes:[],incidencias:[],observaciones:[],problemas_tecnicos:[],semilla:{},
    semilla_observada:[],herramientas:{newman:{...newmanVersion,iteraciones:0,solicitudes:0,aserciones:0}},cypress:{total_pruebas:0},
    cierre:{run:{cierre_http:null},rollback:{verificado:false,motivo:'No comprobado'}},
    evidencias:[],oficial:false,consume_version:false,_limite:Date.now()+(PRESUPUESTO.duracion_segundos-30)*1000};
  const pre=preflight(c,env,newmanVersion);
  if(!pre.ok){r.problemas_tecnicos.push(`PREFLIGHT: ${pre.barreras.join(', ')}`);
    if(pre.barreras.includes('NEWMAN_NO_DISPONIBLE'))for(const x of CASOS)r.casos[x]={estado:'BLOQUEADO',motivo:'Newman no disponible antes de cualquier petición'};
    r.cierre.rollback.motivo='No solicitado: preflight fallido; sin peticiones';
    if(fs.existsSync(c.directorio)&&fs.statSync(c.directorio).isDirectory()){
      guardar(path.join(c.directorio,'preflight.json'),pre);r.evidencias.push('preflight.json');
      delete r._limite;guardar(path.join(c.directorio,'resultado.json'),r);}
    return r;}
  fs.mkdirSync(c.directorio,{recursive:true});guardar(path.join(c.directorio,'preflight.json'),pre);r.evidencias.push('preflight.json');
  const api=String(env.SIGAB_API_TEST_BASE).replace(/\/+$/,'');
  const inicio=fecha(Date.now()-PRESUPUESTO.dias_busqueda*DIAS),fin=fecha(Date.now());
  const desde=new Date(Date.now()-60000).toISOString();
  let iniciado=false,token=null,admin=null,usuario=null,seleccion={},base=null,posterior=null,ejec={},sup=null;
  try{iniciado=true;
    const a=await pedir(r,api,'POST','/sesiones/',{cuerpo:{correo_electronico:env.QA_VETERINARIO_EMAIL,
      contrasena:env.QA_COMMON_PASSWORD},timeout:PRESUPUESTO.timeout_login_ms});
    if(a.http!==200||!a.cuerpo?.token)throw Error(`LOGIN_VETERINARIO_${a.http??'SIN_RED'}`);
    token=a.cuerpo.token;usuario=usuarioDelToken(token);if(!usuario)throw Error('LOGIN_SIN_USUARIO');
    const b=await pedir(r,api,'POST','/sesiones/',{cuerpo:{correo_electronico:env.QA_ADMIN_EMAIL,
      contrasena:env.QA_ADMIN_PASSWORD},timeout:PRESUPUESTO.timeout_login_ms});
    if(b.http!==200||!b.cuerpo?.token)throw Error(`LOGIN_ADMIN_${b.http??'SIN_RED'}`);
    admin=b.cuerpo.token;
    const activo=await pedir(r,api,'GET','/activos-biologicos/885',{token,secreto:env.QA_SANDBOX_SECRET,runId:c.runId});
    if(activo.http!==200||activo.eco!==true||String(activo.cuerpo?.nombre_estado??'').toUpperCase()!=='ACTIVO')throw Error('ACTIVO_885_NO_CONFIRMADO');
    base=await historial(r,api,token,env.QA_SANDBOX_SECRET,c.runId,inicio,fin);
    if(!base.completo)throw Error(`HISTORIAL_INCOMPLETO_${base.http??'SIN_RED'}`);
    const versiones={},versionIds=[...new Set(base.eventos.filter(e=>e.tipo_evento==='INFERENCIA'&&e.payload?.tipo_modelo==null)
      .map(e=>Number(e.payload?.id_version_modelo)).filter(Number.isSafeInteger))];
    for(const id of versionIds.slice(0,PRESUPUESTO.versiones_maximas)){
      const x=await pedir(r,api,'GET',`/prediccion/modelos/${id}`,{token,secreto:env.QA_SANDBOX_SECRET,runId:c.runId});
      if(x.http===200&&x.eco===true&&Number(x.cuerpo?.id_version_modelo)===id)versiones[String(id)]=x.cuerpo.tipo_modelo;}
    if(versionIds.length>PRESUPUESTO.versiones_maximas)r.problemas_tecnicos.push('MODELOS_NO_RESUELTOS_POR_PRESUPUESTO');
    const momento=Date.parse(activo.fecha_servidor)||Date.now();
    r.hora_descubrimiento=new Date(momento).toISOString();
    if(!activo.fecha_servidor)r.problemas_tecnicos.push('Cabecera Date ausente; antigüedad calculada con reloj local');
    seleccion=elegir(base.eventos,usuario,versiones,momento);
    r.semilla_observada=base.eventos.filter(e=>e.tipo_evento==='INFERENCIA'&&
      ['MODELO_ESPECIES_MEDIANAS','MODELO_ESPECIES_GRANDES'].includes(e.payload?.tipo_modelo??versiones[String(e.payload?.id_version_modelo)]))
      .map(e=>({id:e.id_resultado_inferencia,fecha:e.fecha_evento,...antiguedad(e.fecha_evento,momento)}))
      .filter(e=>e.dias_backend>=88&&e.dias_backend<=PRESUPUESTO.dias_busqueda);
    for(const k of CLAVES){const x=seleccion[k];r.semilla[k]={id:x?.id_resultado_inferencia??null,
      fecha:x?.fecha_evento??null,dias_backend:x?.antiguedad?.dias_backend??null,
      horas:x?.antiguedad?.horas??null,en_tramo:!!x};}
    const o=await pedir(r,api,'GET','/openapi.json',{token:admin,secreto:env.QA_SANDBOX_SECRET,runId:c.runId,caso:CASOS[2]});
    const cfg=await pedir(r,api,'GET',c.version>=2?RUTA_CONFIG:'/configuracion/parametros',
      {token:admin,secreto:env.QA_SANDBOX_SECRET,runId:c.runId,caso:CASOS[2]});
    if(c.version>=2){r.v2_superficie={openapi_http:o.http,config_http:cfg.http,
      rutas:{config:!!o.cuerpo?.paths?.[RUTA_CONFIG],ampliacion:!!o.cuerpo?.paths?.[RUTA_AMPLIAR]}};}
    else if(o.http===200&&cfg.http===200&&o.eco===true&&cfg.eco===true&&o.cuerpo?.paths){sup=superficie(o.cuerpo,cfg.cuerpo);
      r.observaciones.push(`Superficie: lectura ventana ${sup.lectura}, escritura ${sup.escritura}, ampliación ${sup.ampliacion}`);
      if(sup.escritura)decidir(r,CASOS[2],'NO_CONCLUYENTE','Operación pública de configuración expuesta; no ejecutada por falta de SOL específica');
      else decidir(r,CASOS[2],'RECHAZADO','OpenAPI y GET /configuracion/parametros no ofrecen escritura pública de ventana_retroalimentacion_dias; M09 no puede configurarla');
    }else if(c.version<2)r.casos[CASOS[2]]={estado:'NO_CONCLUYENTE',motivo:`Superficie no comprobable: OpenAPI HTTP ${o.http??'—'}, configuración HTTP ${cfg.http??'—'}`};
    if(Object.keys(seleccion).length){ejec=await newmanUnico(r,c,api,env,token,seleccion);
      posterior=await historial(r,api,token,env.QA_SANDBOX_SECRET,c.runId,inicio,fin);
      const aud=await pedir(r,api,'GET',`/prediccion/auditoria?tipo_evento=RETROALIMENTACION_REGISTRADA&fecha_desde=${encodeURIComponent(desde)}&id_usuario=${encodeURIComponent(usuario)}&por_pagina=200`,
        {token:admin,secreto:env.QA_SANDBOX_SECRET,runId:c.runId});
      const auditOk=aud.http===200&&aud.eco===true&&Array.isArray(aud.cuerpo?.items)
        &&Number(aud.cuerpo?.total??Infinity)<=aud.cuerpo.items.length;
      const delta=k=>{const x=seleccion[k];if(!x||!posterior?.completo)return null;
        return retro(posterior.eventos,x.id_resultado_inferencia,usuario).length-
          retro(base.eventos,x.id_resultado_inferencia,usuario).length;};
      const audNuevo=k=>{const id=seleccion[k]?.id_resultado_inferencia;
        return (aud.cuerpo?.items??[]).filter(e=>String(e.payload_evento?.id_resultado_inferencia)===String(id));};
      const post=k=>ejec[NOMBRES[CLAVES.indexOf(k)]];
      const comprobable=posterior.completo&&auditOk;
      const p214=post('reciente');
      if(!seleccion.reciente)decidir(r,CASOS[0],'NO_CONCLUYENTE','Falta resultado reciente libre del modelo INDIVIDUAL');
      else if(!p214)decidir(r,CASOS[0],'NO_CONCLUYENTE','POST 214 no ejecutado');
      else if(p214.http===201){const f=p214.cuerpo?.fecha_retroalimentacion;
        const correcto=f&&Date.parse(f)>Date.parse(seleccion.reciente.fecha_evento)
          &&Date.parse(f)!==Date.parse(p214.enviado?.timestamp_retroalimentacion);
        if(!comprobable)decidir(r,CASOS[0],'NO_CONCLUYENTE','Lecturas públicas de historial o auditoría incompletas');
        else if(correcto&&delta('reciente')===1&&audNuevo('reciente').length===1)decidir(r,CASOS[0],'APROBADO','Campo anterior ignorado; 201 y timestamp del servidor posterior a inferencia y distinto del enviado; registro y auditoría comprobados');
        else decidir(r,CASOS[0],'RECHAZADO',`201 sin evidencia completa de fecha del servidor o persistencia: fecha ${f??'—'}, delta ${delta('reciente')}`);
      }else if(p214.http===422&&/fecha de retroalimentaci[oó]n es inv[aá]lida/i.test(p214.cuerpo?.message??'')){
        if(!comprobable)decidir(r,CASOS[0],'NO_CONCLUYENTE','E7 recibido; no se pudo comprobar ausencia pública');
        else if(delta('reciente')===0&&audNuevo('reciente').length===0)decidir(r,CASOS[0],'APROBADO','HTTP 422 E7; sin registro ni auditoría de registro');
        else decidir(r,CASOS[0],'RECHAZADO','E7 recibido pero apareció registro o auditoría');
      }else decidir(r,CASOS[0],p214.http==null?'NO_CONCLUYENTE':'RECHAZADO',`214: ${detallePost(p214)}`);
      const faltan=(c.version>=2?['d89','d90','d90h','d91']:['d89','d90','d91']).filter(k=>!seleccion[k]);
      const p89=post('d89'),p90=post('d90'),p91=post('d91'),p90h=post('d90h');
      if(p90h)r.observaciones.push(`90 días + 12 horas: ${detallePost(p90h)}; antigüedad ${seleccion.d90h.antiguedad.horas} h; más de 90×24 h`);
      if(faltan.length)decidir(r,CASOS[1],'NO_CONCLUYENTE',`Semilla fuera de tramo o ausente: ${faltan.join(', ')}`);
      else if([p89,p90,p91].some(x=>!x||x.http==null))decidir(r,CASOS[1],'NO_CONCLUYENTE','POST principal sin respuesta o no ejecutado');
      else if(p89.http!==201||p90.http!==201||!['http','codigo','dias','id'].every(k=>respuestaE9(p91,seleccion.d91)[k]))
        decidir(r,CASOS[1],'RECHAZADO',`89 ${detallePost(p89)}; 90 ${detallePost(p90)}; 91 ${detallePost(p91)}`);
      else if(!comprobable)decidir(r,CASOS[1],'NO_CONCLUYENTE','HTTP esperados; verificación de historial o auditoría incompleta');
      else if(delta('d89')!==1||delta('d90')!==1||delta('d91')!==0||audNuevo('d91').length)
        decidir(r,CASOS[1],'RECHAZADO',`Deltas historial 89=${delta('d89')}, 90=${delta('d90')}, 91=${delta('d91')}; auditoría 91=${audNuevo('d91').length}`);
      else decidir(r,CASOS[1],'APROBADO','89 y 90 HTTP 201; 91 HTTP 422 E9 sin persistencia ni auditoría de registro');
      const pa=post('d120a'),pb=post('d120b');
      if(c.version>=2){try{await adicionalesV2(r,c,api,env,token,admin,seleccion,base,inicio,fin,desde);}
        catch(e){r.problemas_tecnicos.push(`V2: ${limpiar(e.message)}`);
          for(const caso of [CASOS[2],CASOS[3]])if(r.casos[caso].motivo==='No evaluado')
            decidir(r,caso,'NO_CONCLUYENTE',`Interrupción técnica V2: ${limpiar(e.message)}`);}}
      else if(!seleccion.d120a||!seleccion.d120b)decidir(r,CASOS[3],'NO_CONCLUYENTE','Faltan dos resultados vencidos y libres');
      else if(!pa||!pb||pa.http==null||pb.http==null)decidir(r,CASOS[3],'NO_CONCLUYENTE','POST de resultados vencidos sin respuesta o no ejecutado');
      else if(!['http','codigo','dias','id'].every(k=>respuestaE9(pa,seleccion.d120a)[k])
        ||!['http','codigo','dias','id'].every(k=>respuestaE9(pb,seleccion.d120b)[k]))
        decidir(r,CASOS[3],'RECHAZADO',`Primer 120 ${detallePost(pa)}; segundo 120 ${detallePost(pb)}`);
      else if(!comprobable)decidir(r,CASOS[3],'NO_CONCLUYENTE','E9 recibido; falta verificación de ausencia pública');
      else if(delta('d120a')!==0||delta('d120b')!==0||audNuevo('d120a').length||audNuevo('d120b').length)
        decidir(r,CASOS[3],'RECHAZADO','Intento vencido generó registro o auditoría de registro');
      else if(!sup)decidir(r,CASOS[3],'NO_CONCLUYENTE','No se pudo inspeccionar la operación de ampliación en OpenAPI');
      else if(sup.ampliacion)decidir(r,CASOS[3],'NO_CONCLUYENTE','Operación de ampliación expuesta; no ejecutada sin orden y SOL específicas');
      else decidir(r,CASOS[3],'RECHAZADO','Ambos resultados vencidos rechazados con E9 y sin registro; OpenAPI no expone ampliación puntual por Administrador');
      if(!seleccion.d120b)decidir(r,CASOS[4],'NO_CONCLUYENTE','Falta segundo resultado vencido y libre');
      else if(!pb||pb.http==null)decidir(r,CASOS[4],'NO_CONCLUYENTE','POST 218 sin respuesta');
      else {const piezas=respuestaE9(pb,seleccion.d120b),fallas=Object.entries(piezas).filter(([k,v])=>k!=='limite'&&!v).map(([k])=>k);
        if(fallas.length)decidir(r,CASOS[4],'RECHAZADO',`E9 incompleto (${fallas.join(', ')}): ${detallePost(pb)}; límite esperado ${piezas.limite}`);
        else if(!comprobable||delta('d120b')!==0||audNuevo('d120b').length)
          decidir(r,CASOS[4],'NO_CONCLUYENTE','Mensaje completo; ausencia de persistencia no comprobada');
        else decidir(r,CASOS[4],'APROBADO',`E9 contiene 90 días, id, fecha límite ${piezas.limite} y contacto al administrador`);}
      if(r.problemas_tecnicos.includes('TRES_5XX_CONSECUTIVOS')||r.problemas_tecnicos.includes('CLAVE_403'))
        for(const caso of CASOS)r.casos[caso]={estado:'BLOQUEADO',motivo:r.problemas_tecnicos.includes('CLAVE_403')?'403 de clave del sandbox':'Tres 5xx consecutivos; ambiente no apto'};
    }else r.problemas_tecnicos.push('DATOS_INSUFICIENTES');
  }catch(e){r.problemas_tecnicos.push(`Interrupción: ${limpiar(e.message)}`);
    for(const caso of CASOS)if(r.casos[caso].motivo==='No evaluado')r.casos[caso]={estado:/LOGIN|ACTIVO_885/.test(e.message)?'BLOQUEADO':'NO_CONCLUYENTE',
      motivo:`Interrupción técnica: ${limpiar(e.message)}`};
  }finally{
    if(iniciado){const cierre=await pedir(r,api,'DELETE',`/test-control/runs/${encodeURIComponent(c.runId)}`,{secreto:env.QA_SANDBOX_SECRET});
      r.cierre.run.cierre_http=cierre.http;
      let pos=null;try{pos=token&&base?.completo?await historial(r,api,token,env.QA_SANDBOX_SECRET,c.runId,inicio,fin):null;}
      catch(e){r.problemas_tecnicos.push(`Poscierre: ${limpiar(e.message)}`);}
      const ids=Object.values(seleccion).map(e=>e.id_resultado_inferencia);
      const ausentes=pos?.completo&&ids.every(id=>retro(pos.eventos,id,usuario).length===retro(base.eventos,id,usuario).length);
      let configuracionRestaurada=true,auditoriaRevertida=true;
      if(c.version>=2){
        const cfgFinal=await pedir(r,api,'GET',RUTA_CONFIG,
          {token:admin,secreto:env.QA_SANDBOX_SECRET,runId:c.runId});
        configuracionRestaurada=cfgFinal.http===200&&valorVentana(cfgFinal)===90;
        const idEvento=r.v2_ampliacion?.auditoria?.id_evento;
        if(idEvento){const audFinal=await pedir(r,api,'GET',
          `/prediccion/auditoria?tipo_evento=VENTANA_RETROALIMENTACION_AMPLIADA&fecha_desde=${encodeURIComponent(desde)}&id_referencia=${encodeURIComponent(seleccion.d120a.id_resultado_inferencia)}&por_pagina=200`,
          {token:admin,secreto:env.QA_SANDBOX_SECRET,runId:c.runId});
          auditoriaRevertida=audFinal.http===200&&Array.isArray(audFinal.cuerpo?.items)
            &&Number(audFinal.cuerpo?.total??Infinity)<=audFinal.cuerpo.items.length
            &&!audFinal.cuerpo.items.some(e=>String(e.id_evento)===String(idEvento));}
      }
      r.cierre.rollback={verificado:cierre.http===200&&!!ausentes&&configuracionRestaurada&&auditoriaRevertida,
        motivo:cierre.http===200&&ausentes&&configuracionRestaurada&&auditoriaRevertida?
          'DELETE 200; sin nuevos registros, configuración en 90 y evento de ampliación ausente cuando fue identificable':
          'DELETE, historial, configuración o auditoría poscierre sin confirmar'};
    }
    r.comprobaciones=CASOS.map((caso,i)=>({caso,fuente:'API',id:IDS[i],tipo:'ASSERT',
      estado:r.casos[caso].estado,motivo:r.casos[caso].motivo,evidencia:'resultado.json'}));
    r.incidencias=CASOS.filter(x=>r.casos[x].estado==='RECHAZADO').map(x=>incidencia(x,r.casos[x].motivo));
    const posts=r.solicitudes.filter(x=>x.herramienta==='Newman');
    r.oficial=CASOS.every(x=>['APROBADO','RECHAZADO'].includes(r.casos[x].estado))
      &&r.herramientas.newman.iteraciones===1&&posts.length>=6
      &&r.herramientas.newman.solicitudes===posts.length&&r.herramientas.newman.aserciones>=2*posts.length
      &&r.evidencias.filter(x=>x.startsWith('newman/')).length===2
      &&!posts.some(x=>x.http==null||x.eco!==true)
      &&!r.problemas_tecnicos.some(x=>/TRES_5XX|CLAVE_403|Newman:/.test(x))
      &&r.cierre.rollback.verificado&&r.solicitudes.length<=PRESUPUESTO.solicitudes_totales;
    r.consume_version=r.oficial;delete r._limite;
    if(fs.existsSync(c.directorio)){
      const secretos=[token,admin,env.QA_SANDBOX_SECRET,env.QA_COMMON_PASSWORD,env.QA_ADMIN_PASSWORD,
        env.QA_VETERINARIO_EMAIL,env.QA_ADMIN_EMAIL];
      guardar(path.join(c.directorio,'resultado.json'),JSON.parse(sanear(JSON.stringify(r),secretos)));
      fs.writeFileSync(path.join(c.directorio,informeNombre(c.version)),sanear(informe(c,r),secretos));
    }
  }return r;
}
export async function recuperar(c,{env=leerEnv()}={}){
  const pre=preflight(c,env);if(!pre.ok)throw Error(`PREFLIGHT: ${pre.barreras.join(', ')}`);
  const previo=JSON.parse(fs.readFileSync(path.join(c.directorio,'resultado.json'),'utf8'));
  if(previo.run_id!==c.runId||previo.version!==c.version)throw Error('RUN previo incoherente');
  const r={solicitudes:[],_limite:Date.now()+PRESUPUESTO.duracion_segundos*1000};
  const x=await pedir(r,String(env.SIGAB_API_TEST_BASE).replace(/\/+$/,''),'DELETE',
    `/test-control/runs/${encodeURIComponent(c.runId)}`,{secreto:env.QA_SANDBOX_SECRET});
  const salida={run_id:c.runId,cierre_http:x.http,rollback_verificado:false,
    motivo:'DELETE de recuperación sin verificación pública de ausencia; requiere conciliación'};
  guardar(path.join(c.directorio,`recuperacion-${Date.now()}.json`),salida);return salida;
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
  if(process.argv.includes('--capacidades'))console.log(JSON.stringify(CAPACIDADES,null,2));
  else if(process.argv.includes('--comprobar'))process.exitCode=comprobar();
  else{try{const c=contexto(process.argv.slice(2));const r=await(c.operacion==='recuperar'?recuperar(c):evaluar(c));
    console.log(JSON.stringify({grupo:'G070',run_id:c.runId,oficial:r.oficial??false,casos:r.casos??null}));
    if(!r.oficial)process.exitCode=2;}catch(e){console.error(limpiar(e.message));process.exitCode=2;}}
}
