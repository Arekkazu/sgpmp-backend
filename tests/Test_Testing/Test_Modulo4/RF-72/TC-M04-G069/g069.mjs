#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import {CASOS,IDS,PRESUPUESTO,CAPACIDADES,usuarioDelToken,tipoModelo,seleccionar,retroEventos,foto,igual,duplicado} from './lib/g069_core.mjs';

const DIR=path.dirname(fileURLToPath(import.meta.url));
const RAIZ=path.resolve(DIR,'../../../../..');
const require=createRequire(import.meta.url);
const API='https://www.api.inmero.co/api-sgpmp-test';
const POST='/prediccion/retroalimentacion';
const NOMBRES=['G069-212-A','G069-212-REEMPLAZO','G069-212-IGUAL','G069-212-DISTINTO','G069-213-A','G069-213-REEMPLAZO','G069-213-B'];
const COLECCION=(()=>{try{return JSON.parse(fs.readFileSync(path.join(DIR,'G069.postman_collection.json'),'utf8'));}catch{return null;}})();
const nombreInforme=v=>v===1?'TC-M04-G069_resultado.md':`TC-M04-G069_reevaluacion_V${v}.md`;
const limpio=x=>String(x??'').replace(/[\r\n|]/g,' ');
const fecha=d=>new Intl.DateTimeFormat('en-CA',{timeZone:'America/Bogota',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(d));
const rutaHistorial=(inicio,fin,cursor)=>`/prediccion/historial/885?fecha_inicio=${inicio}&fecha_fin=${fin}${cursor?`&cursor_paginacion=${encodeURIComponent(cursor)}`:''}`;
const guardar=(f,x)=>fs.writeFileSync(f,JSON.stringify(x,null,2),'utf8');
function newmanDir(){try{return path.dirname(require.resolve('newman/package.json',{paths:[RAIZ]}));}
  catch{const rutas=[process.execPath,...String(process.env.PATH??'').split(path.delimiter)];
    return rutas.map(x=>path.join(path.dirname(x),'node_modules','newman','package.json'))
      .find(fs.existsSync)?.replace(/[\\/]package\.json$/,'')??null;}}
function versionNewman(){try{const dir=newmanDir(),version=require(path.join(dir,'package.json')).version;
  return {ok:true,version};}catch{return {ok:false,error:'NEWMAN_NO_DISPONIBLE'};}}
const coleccionValida=c=>c?.item?.length===7&&c.item.every((x,i)=>x.name===NOMBRES[i]
  &&x.request?.method==='POST'&&String(x.request.url).endsWith(POST));
const sanear=(v,secretos)=>{let s=String(v);for(const v of secretos.filter(x=>typeof x==='string'&&x.length>=4))s=s.split(v).join('[REDACTADO]');
  return s.replace(/eyJ[\w-]{5,}\.[\w-]{5,}\.[\w-]{5,}/g,'[JWT_REDACTADO]')
    .replace(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/gi,'[CORREO_REDACTADO]');};
const html=x=>String(x).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export function leerEnv(proceso=process.env,archivo=path.join(RAIZ,'.env.qa')){
  const env={};if(fs.existsSync(archivo))for(const linea of fs.readFileSync(archivo,'utf8').split(/\r?\n/)){
    const m=linea.match(/^\s*([A-Z][A-Z0-9_]*)\s*=(.*)$/);
    if(m)env[m[1]]=m[2].trim().replace(/^(['"])(.*)\1$/,'$2');}
  Object.assign(env,proceso);env.QA_AUTORIZADO=proceso.QA_AUTORIZADO;return env;
}
export function preflight(c,env=leerEnv(),newman=versionNewman()){
  const base=String(env.SIGAB_API_TEST_BASE??'').replace(/\/+$/,'');
  const barreras=['SIGAB_API_TEST_BASE','QA_SANDBOX_SECRET','QA_VETERINARIO_EMAIL',
    'QA_VETERINARIO_B_EMAIL','QA_COMMON_PASSWORD'].filter(k=>!String(env[k]??'').trim());
  if(env.QA_AUTORIZADO!=='SI')barreras.push('QA_AUTORIZADO');
  if(!coleccionValida(COLECCION))barreras.push('COLECCION_INVALIDA');
  if(!newman.ok)barreras.push('NEWMAN_NO_DISPONIBLE');
  if(c.ensayo?!/^http:\/\/(127\.0\.0\.1|localhost):\d+$/.test(base):base!==API)barreras.push('API_NO_CANONICA');
  return {grupo:'G069',run_id:c.runId,ok:barreras.length===0,barreras,presupuesto:PRESUPUESTO,herramientas:{newman},
    efectos:['login Veterinario A y B una vez por cuenta; último acceso y auditoría de autenticación',
      'lecturas de activo, historial, versiones y auditoría',
      'tres retroalimentaciones esperadas y dos rechazos 409; reemplazos condicionales de precondición',
      'DELETE del sandbox siempre tras iniciar peticiones','lecturas poscierre con posible HISTORIAL_CONSULTADO fuera del sandbox']};
}
export function comprobar(){const archivos=['g069.mjs','lib/g069_core.mjs','G069.postman_collection.json',
  'pruebas/g069_ensayo.mjs','pruebas/g069_env.test.mjs','pruebas/registro_qa.mjs','README.md'];
  const faltantes=archivos.filter(x=>!fs.existsSync(path.join(DIR,x)));
  const markdownSuperior=fs.existsSync(path.join(DIR,'Resultados'))&&fs.readdirSync(path.join(DIR,'Resultados')).some(x=>x.endsWith('.md'));
  const newman=versionNewman(),coleccion=coleccionValida(COLECCION),ok=!faltantes.length&&!markdownSuperior&&newman.ok&&coleccion;
  console.log(JSON.stringify({grupo:'G069',ok,faltantes,coleccion,markdownSuperior,presupuesto:PRESUPUESTO,newman}));return ok?0:2;
}
function contexto(args){const v=k=>args.includes(k)?args[args.indexOf(k)+1]:undefined;
  const operacion=v('--operacion'),version=Number(v('--version')),intento=Number(v('--intento')),
    runId=v('--run-id'),referencia=v('--autorizacion'),archivo=v('--contexto');
  if(!CAPACIDADES.operaciones.includes(operacion)||!Number.isInteger(version)||version<1
    ||!Number.isInteger(intento)||intento<1||!referencia||!archivo
    ||!new RegExp(`^RUN-G069-V${version}-\\d{8}-\\d{6}$`).test(runId??''))throw Error('Contexto de ejecución incompleto');
  const destino=path.join(DIR,...(version===1?['Resultados',runId]:[`EvaluacionV${version}`,'Resultados',runId]));
  const ruta=path.resolve(archivo);
  if(path.dirname(ruta)!==destino||!(operacion==='recuperar'?/^recuperacion-\d{14}\.contexto\.json$/.test(path.basename(ruta)):path.basename(ruta)==='contexto_operacion.json'))throw Error('Contexto fuera del RUN canónico');
  const c=JSON.parse(fs.readFileSync(ruta,'utf8'));
  if(c.grupo!=='G069'||c.run_id!==runId||c.version!==version||c.intento!==intento
    ||c.operacion!==operacion.toUpperCase()||c.referencia!==referencia
    ||JSON.stringify(c.casos)!==JSON.stringify(CASOS)
    ||operacion==='reevaluar'&&(version<2||c.version_anterior!==version-1||!c.alcance_reevaluacion)
    ||operacion==='recuperar'&&v('--run-objetivo')!==runId)throw Error('Contexto incoherente');
  return {operacion,version,intento,runId,referencia,directorio:destino,ensayo:false};
}
async function pedir(r,api,metodo,ruta,{token,secreto,runId,cuerpo,caso,timeout=PRESUPUESTO.timeout_ms}={}){
  if(r.solicitudes.length>=PRESUPUESTO.solicitudes_totales&&metodo!=='DELETE')throw Error('PRESUPUESTO_AGOTADO');
  const fila={caso:caso??null,metodo,ruta:ruta.split('?')[0],http:null};r.solicitudes.push(fila);
  const inicio=Date.now();try{
    if(inicio>=r._limite&&metodo!=='DELETE')throw Error('DURACION_EXCEDIDA');
    const res=await fetch(api+ruta,{method:metodo,redirect:'manual',headers:{
      ...(cuerpo?{'Content-Type':'application/json'}:{}),...(token?{Authorization:`Bearer ${token}`}:{}) ,
      ...(secreto?{'X-Sandbox-Secret':secreto}:{}),...(runId?{'X-Test-Run-Id':runId,'X-Zona-Horaria':'UTC'}:{})},
      body:cuerpo?JSON.stringify(cuerpo):undefined,
      signal:AbortSignal.timeout(metodo==='DELETE'?timeout:Math.max(1,Math.min(timeout,r._limite-inicio)))});
    const b=await res.json().catch(()=>null);
    Object.assign(fila,{http:res.status,eco:runId?res.headers.get('x-test-run-id')===runId:null,
      duracion_ms:Date.now()-inicio,respuesta:ruta==='/sesiones/'?{token_recibido:!!b?.token}:b&&typeof b==='object'?
        {error_code:b.error_code??null,message:limpio(b.message??''),total:b.total??null,eventos:b.eventos?.length??null,items:b.items?.length??null}:null});
    return {http:res.status,cuerpo:b,eco:fila.eco};
  }catch(e){Object.assign(fila,{tipo_fallo:['TimeoutError','AbortError'].includes(e.name)?'TIMEOUT':'SIN_RED',
    duracion_ms:Date.now()-inicio});return {http:null,cuerpo:null,eco:false};}
}
async function historial(r,api,token,secreto,runId,inicio,fin,caso,limite=PRESUPUESTO.paginas_verificacion){
  const eventos=[];let cursor=null,http=null,eco=true,paginas=0;
  for(;paginas<limite;paginas++){
    const x=await pedir(r,api,'GET',rutaHistorial(inicio,fin,cursor),{token,secreto,runId,caso});
    http=x.http;eco=eco&&x.eco===true;
    if(http!==200||!Array.isArray(x.cuerpo?.eventos))return {http,eco:false,eventos,completo:false,paginas:paginas+1};
    eventos.push(...x.cuerpo.eventos);cursor=x.cuerpo.cursor_siguiente;
    if(!cursor)return {http,eco,eventos,completo:true,paginas:paginas+1};
  }
  return {http,eco,eventos,completo:false,paginas,cursor_pendiente:!!cursor};
}
async function newmanUnico(r,c,api,env,tokens,cuerpos){
  const coleccion=structuredClone(COLECCION);
  const siguiente={
    'G069-212-A':`let b={};try{b=pm.response.json()}catch{};const reemplazo=['RETROALIMENTACION_DUPLICADA','FUERA_DE_VENTANA_TEMPORAL'].includes(b.error_code)&&pm.environment.get('hay_r1_reemplazo')==='SI';postman.setNextRequest(reemplazo?'G069-212-REEMPLAZO':pm.response.code===201?'G069-212-IGUAL':pm.environment.get('hay_r2')==='SI'?'G069-213-A':null);`,
    'G069-212-REEMPLAZO':`if(pm.response.code===201){const b=JSON.parse(pm.environment.get('cuerpo_r1_reemplazo'));pm.environment.set('cuerpo_r1',JSON.stringify(b));const d=JSON.parse(pm.environment.get('cuerpo_r1_distinto'));d.id_resultado_inferencia=b.id_resultado_inferencia;pm.environment.set('cuerpo_r1_distinto',JSON.stringify(d));}postman.setNextRequest(pm.response.code===201?'G069-212-IGUAL':pm.environment.get('hay_r2')==='SI'?'G069-213-A':null);`,
    'G069-212-IGUAL':`postman.setNextRequest('G069-212-DISTINTO');`,
    'G069-212-DISTINTO':`postman.setNextRequest(pm.environment.get('hay_r2')==='SI'?'G069-213-A':null);`,
    'G069-213-A':`let b={};try{b=pm.response.json()}catch{};const reemplazo=['RETROALIMENTACION_DUPLICADA','FUERA_DE_VENTANA_TEMPORAL'].includes(b.error_code)&&pm.environment.get('hay_r2_reemplazo')==='SI';postman.setNextRequest(reemplazo?'G069-213-REEMPLAZO':pm.response.code===201?'G069-213-B':null);`,
    'G069-213-REEMPLAZO':`if(pm.response.code===201)pm.environment.set('cuerpo_r2',pm.environment.get('cuerpo_r2_reemplazo'));postman.setNextRequest(pm.response.code===201?'G069-213-B':null);`,
    'G069-213-B':`postman.setNextRequest(null);`};
  for(const item of coleccion.item){
    item.request.header=[{key:'Authorization',value:`Bearer {{${item.name==='G069-213-B'?'token_b':'token_a'}}}`},
      {key:'X-Test-Run-Id',value:'{{run_id}}'},{key:'X-Sandbox-Secret',value:'{{sandbox_secret}}'},
      {key:'X-Zona-Horaria',value:'UTC'},{key:'Content-Type',value:'application/json'}];
    item.event=[{listen:'test',script:{type:'text/javascript',exec:[siguiente[item.name],
      `const n=pm.response.code>=500?Number(pm.environment.get('consecutivos_5xx')||0)+1:0;pm.environment.set('consecutivos_5xx',String(n));`,
      `if((pm.response.code===403&&/clave|secreto|sandbox/i.test(pm.response.text()))||n>=3)postman.setNextRequest(null);`,
      `pm.test('HTTP recibido',()=>pm.expect(pm.response.code).to.be.above(0));`,
      `pm.test('Eco de RUN',()=>pm.expect(pm.response.headers.get('X-Test-Run-Id')).to.eql(pm.environment.get('run_id')));`]}}];
  }
  const valores={base_url:api,token_a:tokens.a,token_b:tokens.b??'',run_id:c.runId,
    sandbox_secret:env.QA_SANDBOX_SECRET,cuerpo_r1:JSON.stringify(cuerpos.r1),
    cuerpo_r1_reemplazo:JSON.stringify(cuerpos.r1b??cuerpos.r1),
    cuerpo_r1_distinto:JSON.stringify(cuerpos.r1distinto),cuerpo_r2:JSON.stringify(cuerpos.r2??cuerpos.r1),
    cuerpo_r2_reemplazo:JSON.stringify(cuerpos.r2b??cuerpos.r2??cuerpos.r1),
    hay_r1_reemplazo:cuerpos.r1b?'SI':'NO',hay_r2:cuerpos.r2&&tokens.b?'SI':'NO',
    hay_r2_reemplazo:cuerpos.r2b?'SI':'NO',consecutivos_5xx:'0'};
  const environment={values:Object.entries(valores).map(([key,value])=>({key,value,enabled:true}))};
  let error,summary;try{[error,summary]=await new Promise(resolve=>require(newmanDir()).run({collection:coleccion,
    environment,reporters:['cli'],silent:true,timeoutRequest:PRESUPUESTO.timeout_ms,
    timeout:Math.max(1,r._limite-Date.now()),ignoreRedirects:true,color:'off'},(e,s)=>resolve([e,s])));}catch(e){error=e;}
  const ejecuciones={},reporte={herramienta:'Newman',version:r.herramientas.newman.version,
    error:error?.message??null,solicitudes:[],fallos:(summary?.run?.failures??[]).map(f=>({tipo:f.error?.name??'Error',mensaje:f.error?.message??null}))};
  let consecutivos5xx=0;
  for(const ex of summary?.run?.executions??[]){
    const nombre=ex.item?.name??'DESCONOCIDO',http=ex.response?.code??null,
      caso=nombre.includes('212')?CASOS[0]:CASOS[1],cuenta=nombre==='G069-213-B'?'B':'A';
    let cuerpo=null,enviado=null;try{cuerpo=JSON.parse(ex.response.stream.toString('utf8'));}catch{}
    try{enviado=JSON.parse(ex.request.body.raw);}catch{}
    const eco=ex.response?.headers?.get?.('x-test-run-id')===c.runId
      ||ex.response?.header?.find?.(h=>String(h.key).toLowerCase()==='x-test-run-id')?.value===c.runId;
    const fila={caso,cuenta,nombre,metodo:'POST',ruta:POST,http,eco,herramienta:'Newman',
      resultado:enviado?.id_resultado_inferencia??null,estado_enviado:enviado?.estado_retroalimentacion??null,
      respuesta:{id_retroalimentacion:cuerpo?.id_retroalimentacion??null,error_code:cuerpo?.error_code??null,
        message:limpio(cuerpo?.message??''),id_resultado_inferencia:cuerpo?.id_resultado_inferencia??null},
      duracion_ms:ex.response?.responseTime??null};
    r.solicitudes.push(fila);
    const post={nombre,caso,cuenta,http,cuerpo,eco,enviado,duracion_ms:fila.duracion_ms};
    (ejecuciones[nombre]??=[]).push(post);
    reporte.solicitudes.push({...fila,aserciones:(ex.assertions??[]).map(a=>({nombre:a.assertion,error:a.error?.message??null}))});
    consecutivos5xx=http>=500?consecutivos5xx+1:0;
    if(consecutivos5xx>=3&&!r.problemas_tecnicos.includes('TRES_5XX_CONSECUTIVOS'))r.problemas_tecnicos.push('TRES_5XX_CONSECUTIVOS');
    if(http===403&&/clave|secreto|sandbox/i.test(String(cuerpo?.message??cuerpo?.detail??'')))r.problemas_tecnicos.push('CLAVE_403');
  }
  r.herramientas.newman.iteraciones=summary?.run?.stats?.iterations?.total??(summary?1:0);
  r.herramientas.newman.solicitudes=reporte.solicitudes.length;
  r.herramientas.newman.aserciones=reporte.solicitudes.reduce((n,x)=>n+x.aserciones.length,0);
  if(error)r.problemas_tecnicos.push(`Newman: ${limpio(error.message)}`);
  const secretos=[tokens.a,tokens.b,env.QA_SANDBOX_SECRET,env.QA_COMMON_PASSWORD,
    env.QA_VETERINARIO_EMAIL,env.QA_VETERINARIO_B_EMAIL];
  const json=sanear(JSON.stringify(reporte,null,2),secretos),sub=path.join(c.directorio,'newman');
  fs.mkdirSync(sub,{recursive:true});fs.writeFileSync(path.join(sub,'newman-G069.json'),json,'utf8');
  fs.writeFileSync(path.join(sub,'newman-G069.html'),`<!doctype html><html lang="es"><meta charset="utf-8"><title>Newman G069</title><pre>${html(json)}</pre></html>`,'utf8');
  r.evidencias.push('newman/newman-G069.json','newman/newman-G069.html');
  return ejecuciones;
}
function verificar(caso,posts,h,a,usuarios){
  const es212=caso===CASOS[0],primero=posts[0],fallos=[],dudas=[];
  if(!primero)return {estado:'NO_CONCLUYENTE',motivo:'No hubo POST de precondición; datos o ejecución faltantes'};
  if(primero.http==null)return {estado:'NO_CONCLUYENTE',motivo:'POST sin respuesta; conciliación requerida'};
  if(primero.http!==201)return {estado:'NO_CONCLUYENTE',motivo:`Precondición ${caso} HTTP ${primero.http}; no se montó el primer registro`};
  const resultado=primero.enviado?.id_resultado_inferencia;
  if(!resultado)return {estado:'NO_CONCLUYENTE',motivo:'Cuerpo enviado no recuperado del reporte Newman'};
  if(primero.eco!==true)dudas.push('sin eco de RUN en primer registro');
  if(!h?.completo||h.http!==200||h.eco!==true)dudas.push('historial público incompleto');
  if(!a?.completo||a.http!==200||a.eco!==true)dudas.push('auditoría pública incompleta');
  const historial=retroEventos(h?.eventos??[],resultado).map(foto);
  const deA=historial.filter(x=>x.usuario===usuarios.a),deB=historial.filter(x=>x.usuario===usuarios.b);
  const base=primero.cuerpo,original=deA.find(x=>x.id===String(base?.id_retroalimentacion));
  if(h?.completo){
    if(deA.length!==1||!original)fallos.push(`se esperó un registro de A intacto; historial muestra ${deA.length}`);
    if(original&&(original.estado!=='CORRECTO'||!igual(original.diagnosticos,null)
      ||!Number.isFinite(Date.parse(original.fecha))
      ||Date.parse(original.fecha)!==Date.parse(base?.fecha_retroalimentacion)
      ||original.resultado!==String(base?.id_resultado_inferencia)))fallos.push('registro original de A modificado');
  }
  const audits=(a?.items??[]).filter(x=>x.tipo_evento==='RETROALIMENTACION_REGISTRADA'
    &&String(x.payload_evento?.id_resultado_inferencia)===String(resultado)
    &&x.resultado_operacion==='EXITOSO');
  if(es212){
    if(posts.length<3)dudas.push('faltan los dos intentos duplicados');
    for(const [i,p] of posts.slice(1,3).entries()){
      if(p.http==null){dudas.push(`intento ${i+2} sin respuesta; conciliación requerida`);continue;}
      if(p.eco!==true)dudas.push(`intento ${i+2} sin eco de RUN`);
      if(p.http!==409)fallos.push(`intento ${i+2} HTTP ${p.http}; E2/CA-6 exige 409`);
      if(!duplicado(p.cuerpo))fallos.push(`intento ${i+2} sin mensaje de E2`);
      if(p.cuerpo?.id_retroalimentacion)fallos.push(`intento ${i+2} propuso un registro nuevo`);
      if(/editar|edici[oó]n|actualizar|reemplazar|eliminar|\bpatch\b|\bput\b|\bdelete\b/i.test(
        String(p.cuerpo?.message??'')))fallos.push(`intento ${i+2} propuso edición o reemplazo`);
    }
    if(a?.completo&&audits.filter(x=>String(x.id_usuario)===usuarios.a).length!==1)
      fallos.push('auditoría RF-73 no muestra exactamente un RETROALIMENTACION_REGISTRADA de A');
  }else{
    const p=posts[1];if(!p)dudas.push('falta POST de B');
    else if(p.http==null)dudas.push('POST de B sin respuesta; conciliación requerida');
    else{
      if(p.eco!==true)dudas.push('POST de B sin eco de RUN');
      if(p.http!==201)fallos.push(`B HTTP ${p.http}; salida RF-72 exige 201`);
    }
    if(h?.completo&&p?.http===201){
      if(deB.length!==1||String(deB[0]?.id)!==String(p.cuerpo?.id_retroalimentacion))fallos.push('B no coexiste como entidad independiente');
      if(deB[0]?.id===original?.id)fallos.push('B sobrescribió el registro de A');
    }
    if(a?.completo&&p?.http===201&&audits.filter(x=>[usuarios.a,usuarios.b].includes(String(x.id_usuario))).length!==2)
      fallos.push('auditoría RF-73 no muestra dos registros independientes');
  }
  return {estado:fallos.length?'RECHAZADO':dudas.length?'NO_CONCLUYENTE':'APROBADO',
    motivo:fallos.join('; ')||dudas.join('; ')||(es212?'201, 409, 409 con mensaje E2; original y auditoría intactos':
      'A y B recibieron 201; historial y auditoría muestran dos registros independientes'),
    resultado,observado:{registros_a:deA.length,registros_b:deB.length,auditoria_registros:audits.length}};
}
function incidencias(c,r){if(c.ensayo)return [];
  return CASOS.filter(x=>r.casos[x].estado==='RECHAZADO').map((caso,i)=>({
    id:`INC-M04-G069-${caso.slice(-3)}-${String(i+1).padStart(2,'0')}`,caso,
    descripcion:r.casos[caso].motivo,equipo_responsable:'Desarrollo',
    fundamento_derivacion:'Primera discrepancia comprobada por API pública en TEST; causa raíz no determinada',
    severidad:'ALTA',justificacion_severidad:caso===CASOS[0]?
      'La unicidad definitiva de una funcionalidad relevante falla sin alternativa de corrección':
      'La segunda perspectiva clínica no puede coexistir como exige RF-72',certeza:'CONFIRMADA'}));
}
export function informe(c,r){
  const decision=r.oficial?(CASOS.some(x=>r.casos[x].estado==='RECHAZADO')?'RECHAZADO':'APROBADO'):'NO OFICIAL';
  const tabla=CASOS.map(x=>`| ${x} | ${r.casos[x].estado} | ${limpio(r.casos[x].motivo)} |`).join('\n');
  const esperado={
    'TC-M04-212':'«El primer registro HTTP 201; ambos intentos posteriores HTTP 409 con el mensaje de retroalimentación ya registrada por este usuario. El original permanece intacto y no se ofrece edición ni reemplazo» (matriz G069, TC-M04-212). RF-72, líneas 4018-4019; E2, líneas 4241-4246; CA-6, líneas 4369-4374.',
    'TC-M04-213':'«El registro del veterinario B responde HTTP 201 y coexiste como entidad independiente asociada al mismo resultado» (matriz G069, TC-M04-213). RF-72, línea 4065; salida, línea 4301.'};
  const porCaso=x=>r.intentos.filter(i=>i.caso===x);
  const idPost=nombre=>r.solicitudes.find(s=>s.nombre===nombre)?.respuesta?.id_retroalimentacion??'—';
  const intentoTexto=i=>`${i.cuenta}/${i.resultado??'—'} ${i.estado_enviado??'—'} → HTTP ${i.http??'—'}, código ${limpio(i.codigo??'—')}`;
  const detalle=CASOS.map(x=>{
    const filas=porCaso(x),estado=r.casos[x].estado,obs=r.casos[x].observado??{};
    const hecho=x===CASOS[0]?
      `Cuenta A sobre R1 ${r.casos[x].resultado??r.datos_elegidos.r1??'—'}, en orden: ${filas.map(i=>`${i.estado_enviado??'—'} (HTTP ${i.http??'—'})`).join(', ')||'sin POST registrado'}.`:
      `Cuentas A y B sobre R2 ${r.casos[x].resultado??r.datos_elegidos.r2??'—'}, en orden: ${filas.map(i=>`${i.cuenta} ${i.estado_enviado??'—'} (HTTP ${i.http??'—'})`).join(', ')||'sin POST registrado'}.`;
    const observado=x===CASOS[0]?
      `${filas.map(intentoTexto).join('; ')||'Sin intentos registrados'}; id_retroalimentacion inicial de A: ${idPost('G069-212-A')}; historial tras los intentos: ${obs.registros_a??'—'} ${obs.registros_a===1?'registro':'registros'} de A${estado==='APROBADO'?` con estado CORRECTO y el mismo id ${idPost('G069-212-A')}`:''}; RETROALIMENTACION_REGISTRADA antes de los dos 409: ${filas[0]?.http===201?'1 (derivado del 201 inicial)':'—'}, después de ambos 409: ${obs.auditoria_registros??'—'} (auditoría verificada).`:
      `${filas.map(intentoTexto).join('; ')||'Sin intentos registrados'}; id_retroalimentacion de A: ${idPost('G069-213-A')}; de B: ${idPost('G069-213-B')}; historial: A ${obs.registros_a??'—'} y B ${obs.registros_b??'—'} ${obs.registros_a===1&&obs.registros_b===1?'registro cada uno':'registros'}; RETROALIMENTACION_REGISTRADA: ${obs.auditoria_registros??'—'} ${obs.auditoria_registros===1?'evento':'eventos'}.`;
    const razon=estado==='APROBADO'?(x===CASOS[0]?
      'El primer 201 creó el registro; cada repetición, con el mismo estado y con uno distinto, devolvió 409 RETROALIMENTACION_DUPLICADA y «Ya existe una retroalimentación registrada por este usuario para este resultado.», como exigen E2 y CA-6. El original conservó su id y estado; no aparecieron registros ni eventos nuevos por los rechazos.':
      'A obtuvo 201 y B también obtuvo 201 sobre R2; sus id_retroalimentacion son distintos y coexisten dos registros y dos eventos de auditoría. La unicidad se aplica por usuario, no por resultado.'):
      `La decisión ${estado} se fundamenta en: ${limpio(r.casos[x].motivo)}.`;
    return `### ${x} — ${estado}\n\n- **Qué se hizo:** ${hecho}\n- **Qué se esperaba:** ${esperado[x]}\n- **Qué se observó:** ${observado}\n- **Por qué ${estado}:** ${razon}\n`;
  }).join('\n');
  const intentos=r.intentos.map(x=>`| ${x.caso} | ${x.cuenta} | ${x.resultado??'—'} | ${x.estado_enviado??'—'} | ${x.http??'—'} | ${x.codigo||x.mensaje?`${limpio(x.codigo??'—')}: ${limpio(x.mensaje??'—')}`:'—'} | ${x.persistio==null?'no comprobado':x.persistio?'sí':'no'} |`).join('\n');
  const inc=r.incidencias.map(x=>`- ${x.id}: ${limpio(x.descripcion)}; severidad ${x.severidad} (${x.justificacion_severidad}); certeza ${x.certeza}; atención inicial ${x.equipo_responsable}. ${x.fundamento_derivacion}.`).join('\n')||'Ninguna confirmada.';
  const conclusion=decision==='APROBADO'?'G069 APROBADO: RF-72 cumple la unicidad por usuario y admite la segunda perspectiva clínica. Sin incidencias; sin acciones para Desarrollo.':
    decision==='RECHAZADO'?'Desarrollo debe revisar las discrepancias comprobadas; repetir los casos afectados en RUN autorizado.':
    'Conservar la evidencia y atender los impedimentos o casos sin conclusión indicados arriba.';
  const evidencias=[...new Set([...r.evidencias,'resultado.json',nombreInforme(c.version)])];
  return `# TC-M04-G069 — ${decision}\n\n## Identificación\n\nGrupo G069; ${CASOS.join(', ')}; RF-72; versión ${c.version}; RUN ${c.runId}; ambiente ${c.ensayo?'loopback local':'TEST'}; autorización ${c.referencia}; código revisado origin/test daefc3a5; Node.js y Newman verificados. Solo API.\n\n## Decisión del caso\n\n| Caso | Decisión | Motivo |\n|---|---|---|\n${tabla}\n\nRUN oficial: ${r.oficial?'sí':'no'}. Qué falta: ${r.oficial?'nada':limpio(r.problemas_tecnicos.join('; ')||CASOS.filter(x=>!['APROBADO','RECHAZADO'].includes(r.casos[x].estado)).map(x=>`${x}: ${r.casos[x].motivo}`).join('; ')||r.cierre.rollback.motivo)}. El ensayo local no acredita TEST.\n\n## Precondición de datos\n\nActivo 885; resultados INDIVIDUAL libres hallados ${r.datos_elegidos.resultados_libres??0}; páginas de descubrimiento ${r.datos_elegidos.paginas??0}; cursor pendiente ${r.datos_elegidos.cursor_pendiente?'sí':'no'}. R1 ${r.datos_elegidos.r1??'—'}; R2 ${r.datos_elegidos.r2??'—'}; reemplazos solo ante duplicado previo o ventana vencida.\n\n## Detalle por caso\n\n${detalle}\n## Tabla de intentos\n\n| Caso | Cuenta | Resultado | Estado enviado | HTTP | Código y mensaje | Persistió |\n|---|---|---|---|---|---|---|\n${intentos}\n\n## Observaciones\n\n${r.observaciones.map(limpio).join('; ')||'Ninguna.'}\n\n## Incidencias de producto\n\n${inc}\n\n## Problemas técnicos y análisis de causas\n\n${r.problemas_tecnicos.map(limpio).join('; ')||'Ninguno.'} La derivación inicial no atribuye causa raíz.\n\n## Historial de intentos, cierre y rollback\n\nIntento ${c.intento}; ${r.solicitudes.length} solicitudes. DELETE HTTP ${r.cierre.run.cierre_http??'—'}; rollback ${r.cierre.rollback.verificado?'verificado':'no verificado'}: ${limpio(r.cierre.rollback.motivo)}. Lecturas poscierre pueden generar HISTORIAL_CONSULTADO fuera del sandbox.\n\n## Conclusión y acciones\n\n${conclusion}\n\n## Herramientas y evidencias\n\nNewman ${r.herramientas.newman.version??'no disponible'}: ${r.herramientas.newman.iteraciones} iteración, ${r.herramientas.newman.solicitudes} solicitudes, ${r.herramientas.newman.aserciones} aserciones. Login, descubrimiento, verificaciones y cierre con fetch. Sin UI obligatoria.\n\n${evidencias.map(x=>`- ${x}`).join('\n')}\n`;
}
export async function evaluar(c,{env=leerEnv(),newmanVersion=versionNewman()}={}){
  const r={grupo:'G069',run_id:c.runId,version:c.version,intento:c.intento,referencia:c.referencia,
    ambiente:c.ensayo?'loopback local':'TEST',casos:Object.fromEntries(CASOS.map(x=>[x,{estado:'NO_CONCLUYENTE',motivo:'No ejecutado'}])),
    comprobaciones:[],solicitudes:[],intentos:[],incidencias:[],observaciones:[],problemas_tecnicos:[],
    datos_elegidos:{},herramientas:{newman:{...newmanVersion,iteraciones:0,solicitudes:0,aserciones:0}},
    cypress:{total_pruebas:0},cierre:{run:{cierre_http:null},rollback:{verificado:false,motivo:'No comprobado'}},
    evidencias:[],oficial:false,consume_version:false,_limite:Date.now()+PRESUPUESTO.duracion_segundos*1000};
  const pre=preflight(c,env,newmanVersion);
  if(!pre.ok){r.problemas_tecnicos.push(`PREFLIGHT: ${pre.barreras.join(', ')}`);
    if(pre.barreras.includes('NEWMAN_NO_DISPONIBLE'))for(const caso of CASOS)
      r.casos[caso]={estado:'BLOQUEADO',motivo:'Newman no disponible; impedimento técnico previo a cualquier petición'};
    return r;}
  fs.mkdirSync(c.directorio,{recursive:true});guardar(path.join(c.directorio,'preflight.json'),pre);r.evidencias.push('preflight.json');
  const api=String(env.SIGAB_API_TEST_BASE).replace(/\/+$/,'');
  const inicio=fecha(Date.now()-PRESUPUESTO.dias_busqueda*86400000),fin=fecha(Date.now());
  const inicioAuditoria=new Date(Date.now()-60000).toISOString();
  let iniciado=false,tokenA=null,tokenB=null,usuarios={a:null,b:null},ids={};
  try{
    iniciado=true;
    const a=await pedir(r,api,'POST','/sesiones/',{cuerpo:{correo_electronico:env.QA_VETERINARIO_EMAIL,
      contrasena:env.QA_COMMON_PASSWORD},timeout:PRESUPUESTO.timeout_login_ms});
    if(a.http!==200||!a.cuerpo?.token)throw Error(`LOGIN_A_${a.http??'SIN_RESPUESTA'}`);
    tokenA=a.cuerpo.token;usuarios.a=usuarioDelToken(tokenA);
    if(!usuarios.a)throw Error('LOGIN_A_SIN_USUARIO');
    const b=await pedir(r,api,'POST','/sesiones/',{cuerpo:{correo_electronico:env.QA_VETERINARIO_B_EMAIL,
      contrasena:env.QA_COMMON_PASSWORD},timeout:PRESUPUESTO.timeout_login_ms});
    if(b.http===200&&b.cuerpo?.token){tokenB=b.cuerpo.token;usuarios.b=usuarioDelToken(tokenB);}
    else r.problemas_tecnicos.push(`LOGIN_B_${b.http??'SIN_RESPUESTA'}`);
    if(!usuarios.b){tokenB=null;r.casos[CASOS[1]]={estado:'NO_CONCLUYENTE',motivo:'Login de B fallido; no se probó multiplicidad'};}
    const activo=await pedir(r,api,'GET','/activos-biologicos/885',{token:tokenA,secreto:env.QA_SANDBOX_SECRET,runId:c.runId});
    if(activo.http!==200||activo.eco!==true||String(activo.cuerpo?.nombre_estado??'').toUpperCase()!=='ACTIVO')
      throw Error('ACTIVO_885_NO_CONFIRMADO');
    const eventos=[];let cursor=null,paginas=0,descubrimientoOk=true;
    for(;paginas<PRESUPUESTO.paginas_descubrimiento;paginas++){
      const x=await pedir(r,api,'GET',rutaHistorial(inicio,fin,cursor),{token:tokenA,secreto:env.QA_SANDBOX_SECRET,runId:c.runId});
      if(x.http!==200||x.eco!==true||!Array.isArray(x.cuerpo?.eventos)){descubrimientoOk=false;break;}
      eventos.push(...x.cuerpo.eventos);cursor=x.cuerpo.cursor_siguiente;if(!cursor){paginas++;break;}
    }
    r.datos_elegidos.paginas=paginas;r.datos_elegidos.cursor_pendiente=!!cursor;
    if(!descubrimientoOk)throw Error('HISTORIAL_DESCUBRIMIENTO_INCOMPLETO');
    const versiones={},versionIds=[...new Set(eventos.filter(e=>e.tipo_evento==='INFERENCIA'&&e.payload?.tipo_modelo==null)
      .map(e=>Number(e.payload?.id_version_modelo)).filter(Number.isSafeInteger))];
    for(const id of versionIds.slice(0,PRESUPUESTO.versiones_maximas)){
      const x=await pedir(r,api,'GET',`/prediccion/modelos/${id}`,{token:tokenA,secreto:env.QA_SANDBOX_SECRET,runId:c.runId});
      if(x.http===200&&x.eco===true&&Number(x.cuerpo?.id_version_modelo)===id)versiones[String(id)]=x.cuerpo.tipo_modelo;
    }
    const candidatos=seleccionar(eventos,[usuarios.a,usuarios.b].filter(Boolean),versiones,inicio);
    r.datos_elegidos.resultados_libres=candidatos.length;
    const cuerpo=(dato,estado='CORRECTO')=>({id_resultado_inferencia:dato.id_resultado_inferencia,
      id_activo_biologico:885,estado_retroalimentacion:estado,
      ...(estado==='INCORRECTO'?{diagnosticos_reales:[8]}:{})});
    const r1=candidatos[0],r2=tokenB?candidatos[1]:null,r1b=candidatos[2],r2b=candidatos[3];
    r.datos_elegidos.r1=r1?.id_resultado_inferencia??null;r.datos_elegidos.r2=r2?.id_resultado_inferencia??null;
    if(!r1){r.casos[CASOS[0]]={estado:'NO_CONCLUYENTE',motivo:'Sin resultado INDIVIDUAL libre para R1'};}
    if(tokenB&&!r2)r.casos[CASOS[1]]={estado:'NO_CONCLUYENTE',motivo:'Sin segundo resultado INDIVIDUAL libre para R2'};
    if(r1){
      const ejec=await newmanUnico(r,c,api,env,{a:tokenA,b:tokenB},{r1:cuerpo(r1),r1b:r1b?cuerpo(r1b):null,
        r1distinto:cuerpo(r1,'INCORRECTO'),r2:r2?cuerpo(r2):null,r2b:r2b?cuerpo(r2b):null});
      const primero=ejec['G069-212-REEMPLAZO']?.[0]?.http===201?ejec['G069-212-REEMPLAZO'][0]:ejec['G069-212-A']?.[0];
      const primero2=ejec['G069-213-REEMPLAZO']?.[0]?.http===201?ejec['G069-213-REEMPLAZO'][0]:ejec['G069-213-A']?.[0];
      const series=[[primero,ejec['G069-212-IGUAL']?.[0],ejec['G069-212-DISTINTO']?.[0]],
        [primero2,ejec['G069-213-B']?.[0]]];
      for(let i=0;i<2;i++){
        const caso=CASOS[i],posts=series[i].filter(Boolean),base=posts[0];
        if(!base||base.http!==201){
          if(r.casos[caso].motivo==='No ejecutado')r.casos[caso]={estado:'NO_CONCLUYENTE',
            motivo:base?`Precondición HTTP ${base.http??'sin respuesta'}; no se montó el primer registro`:'POST no ejecutado'};
          continue;
        }
        const resultado=base.enviado?.id_resultado_inferencia;
        if(!resultado){r.casos[caso]={estado:'NO_CONCLUYENTE',motivo:'No se recuperó resultado enviado'};continue;}
        ids[caso]=resultado;
        const h=await historial(r,api,tokenA,env.QA_SANDBOX_SECRET,c.runId,inicio,fin,caso);
        const q=`/prediccion/auditoria?tipo_evento=RETROALIMENTACION_REGISTRADA&fecha_desde=${encodeURIComponent(inicioAuditoria)}&por_pagina=200`;
        const x=await pedir(r,api,'GET',q,{token:tokenA,secreto:env.QA_SANDBOX_SECRET,runId:c.runId,caso});
        const audit={http:x.http,eco:x.eco,items:x.cuerpo?.items??[],
          completo:x.http===200&&Number(x.cuerpo?.total??Infinity)<=(x.cuerpo?.items?.length??0)};
        r.casos[caso]=verificar(caso,posts,h,audit,usuarios);
        for(const p of posts){const id=p.cuerpo?.id_retroalimentacion;
          const propios=h.completo?retroEventos(h.eventos,p.enviado?.id_resultado_inferencia).filter(e=>
            String(e.payload?.id_usuario_veterinario)===String(p.cuenta==='B'?usuarios.b:usuarios.a)):[];
          const persistio=h.completo?(id?propios.some(e=>
            String(e.payload?.id_retroalimentacion??e.id_evento)===String(id)):
            propios.length>(p.cuenta==='A'?1:0)):null;
          r.intentos.push({caso,cuenta:p.cuenta,resultado:p.enviado?.id_resultado_inferencia,
            estado_enviado:p.enviado?.estado_retroalimentacion,http:p.http,codigo:p.cuerpo?.error_code??null,
            mensaje:p.cuerpo?.message??null,persistio});}
      }
      for(const p of r.solicitudes.filter(x=>x.herramienta==='Newman'))if(!r.intentos.some(x=>x.caso===p.caso&&x.resultado===p.resultado&&x.http===p.http&&x.estado_enviado===p.estado_enviado))
        r.intentos.push({caso:p.caso,cuenta:p.cuenta,resultado:p.resultado,estado_enviado:p.estado_enviado,
          http:p.http,codigo:p.respuesta?.error_code,mensaje:p.respuesta?.message,persistio:null});
      if(r.problemas_tecnicos.includes('TRES_5XX_CONSECUTIVOS')||r.problemas_tecnicos.includes('CLAVE_403')){
        for(const caso of CASOS)
          r.casos[caso]={estado:'BLOQUEADO',motivo:r.problemas_tecnicos.includes('CLAVE_403')?
            '403 de clave del sandbox; no es un defecto del producto':'Tres 5xx consecutivos; ambiente no apto'};
      }
    }
  }catch(e){r.problemas_tecnicos.push(`Interrupción: ${limpio(e.message)}`);
    for(const caso of CASOS)if(r.casos[caso].motivo==='No ejecutado')r.casos[caso]={estado:/LOGIN_A|ACTIVO_885/.test(e.message)?'BLOQUEADO':'NO_CONCLUYENTE',
      motivo:`Interrupción técnica: ${limpio(e.message)}`};
  }finally{
    if(iniciado){
      const cierre=await pedir(r,api,'DELETE',`/test-control/runs/${encodeURIComponent(c.runId)}`,{secreto:env.QA_SANDBOX_SECRET});
      r.cierre.run.cierre_http=cierre.http;let ausentes=cierre.http===200,consultados=0;
      for(const caso of CASOS)if(ids[caso]&&tokenA){
        const h=await historial(r,api,tokenA,env.QA_SANDBOX_SECRET,c.runId,inicio,fin,caso);
        consultados++;
        if(!h.completo||h.http!==200||retroEventos(h.eventos,ids[caso]).length)ausentes=false;
      }
      r.cierre.rollback={verificado:ausentes&&consultados===Object.keys(ids).length&&consultados>0,
        motivo:ausentes&&consultados===Object.keys(ids).length&&consultados>0?
          'DELETE 200 y ausencia de retroalimentaciones de R1/R2 en historial poscierre':
          'DELETE o ausencia de retroalimentaciones poscierre sin confirmar'};
    }
    r.comprobaciones=CASOS.map((caso,i)=>({caso,fuente:'API',id:IDS[i],tipo:'ASSERT',
      estado:r.casos[caso].estado,motivo:r.casos[caso].motivo,evidencia:'resultado.json'}));
    r.incidencias=incidencias(c,r);
    const newman=r.solicitudes.filter(x=>x.herramienta==='Newman');
    r.oficial=CASOS.every(x=>['APROBADO','RECHAZADO'].includes(r.casos[x].estado))
      &&r.herramientas.newman.iteraciones===1&&newman.length>=5
      &&r.herramientas.newman.solicitudes===newman.length
      &&r.herramientas.newman.aserciones>=2*newman.length
      &&r.evidencias.filter(x=>x.startsWith('newman/')).length===2
      &&!newman.some(x=>x.http==null||x.eco!==true)
      &&!r.problemas_tecnicos.some(x=>/TRES_5XX|CLAVE_403|Newman:|LOGIN_B/.test(x))
      &&r.cierre.rollback.verificado&&r.solicitudes.length<=PRESUPUESTO.solicitudes_totales;
    r.consume_version=r.oficial;delete r._limite;
    if(fs.existsSync(c.directorio)){
      const secretos=[tokenA,tokenB,env.QA_SANDBOX_SECRET,env.QA_COMMON_PASSWORD,
        env.QA_VETERINARIO_EMAIL,env.QA_VETERINARIO_B_EMAIL];
      guardar(path.join(c.directorio,'resultado.json'),JSON.parse(sanear(JSON.stringify(r),secretos)));
      fs.writeFileSync(path.join(c.directorio,nombreInforme(c.version)),sanear(informe(c,r),secretos),'utf8');
    }
  }
  return r;
}
export async function recuperar(c,{env=leerEnv()}={}){
  const pre=preflight(c,env);if(!pre.ok)throw Error(`PREFLIGHT:${pre.barreras.join(',')}`);
  const previo=JSON.parse(fs.readFileSync(path.join(c.directorio,'resultado.json'),'utf8'));
  if(previo.run_id!==c.runId||previo.version!==c.version)throw Error('RUN previo incoherente');
  const r={solicitudes:[],_limite:Date.now()+900000};
  const x=await pedir(r,String(env.SIGAB_API_TEST_BASE).replace(/\/+$/,''),'DELETE',
    `/test-control/runs/${encodeURIComponent(c.runId)}`,{secreto:env.QA_SANDBOX_SECRET});
  const salida={run_id:c.runId,cierre_http:x.http,rollback_verificado:false,
    motivo:'Recuperación DELETE sin comprobación pública de ausencia; requiere conciliación'};
  guardar(path.join(c.directorio,`recuperacion-${Date.now()}.json`),salida);return salida;
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
  if(process.argv.includes('--capacidades'))console.log(JSON.stringify(CAPACIDADES,null,2));
  else if(process.argv.includes('--comprobar'))process.exitCode=comprobar();
  else{try{const c=contexto(process.argv.slice(2));const r=await(c.operacion==='recuperar'?recuperar(c):evaluar(c));
    console.log(JSON.stringify({grupo:'G069',run_id:c.runId,oficial:r.oficial??false,casos:r.casos??null}));
    if(!r.oficial)process.exitCode=2;}catch(e){console.error(limpio(e.message));process.exitCode=2;}}
}
