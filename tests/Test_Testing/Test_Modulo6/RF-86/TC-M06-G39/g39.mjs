import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import {spawn} from 'node:child_process';
import {createHash} from 'node:crypto';
import {createRequire} from 'node:module';
import {AsyncLocalStorage} from 'node:async_hooks';
import {fileURLToPath} from 'node:url';
import {CASOS,IDS,CONTRATO,DIR,PRESUPUESTO,entrada,validarActor,validarDecimales,
  periodoDestino,vigente,idsNuevos,igual,truncar2,resolverMatriz} from './lib/g39_core.mjs';

const require=createRequire(import.meta.url), control=new AsyncLocalStorage();
const ROOT=path.resolve(DIR,'../../../../..');
const API='https://www.api.inmero.co/api-sgpmp-test';
const COL=path.join(DIR,'G39.postman_collection.json');
const CONTRACT=path.join(DIR,'pruebas','contrato_g39.json');
const SHA={coleccion:'566cc7849414ee570cf86fa9936f164e97a6254de07808684bda16bd6b5b009e',
  contrato:'8919febe5aa10fca29b3a1920183585fb12175484cb3eed6d3a0b2191ad6934e'};
export const CAPACIDADES={contrato:'sigab-qa-ejecutor/1',grupo:'G39',casos:CASOS,
  operaciones:['evaluar','reintentar','reevaluar'],versiones:{min:1,max:99},
  comprobaciones_obligatorias:Object.fromEntries(CASOS.map((c,i)=>[c,{API:[IDS[i]]}])),
  limite:{solicitudes_totales:150,duracion_segundos:1800,timeout_post_ms:120000},baja_automatizada:false};
const num=x=>Number.isInteger(Number(x))&&Number(x)>0?Number(x):null;
const hoy=()=>new Intl.DateTimeFormat('en-CA',{timeZone:'America/Bogota',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
const limpio=x=>String(x??'').replace(/[\r\n|]/g,' ').slice(0,300);
const guardar=(p,x)=>fs.writeFileSync(p,JSON.stringify(x,null,2),'utf8');
const sha=p=>createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const versionNewman=()=>{try{return require(require.resolve('newman/package.json',{paths:[ROOT]})).version;}
  catch{const p=path.join(path.dirname(process.execPath),'node_modules','newman','package.json');
    return fs.existsSync(p)?JSON.parse(fs.readFileSync(p,'utf8')).version:null;}};
export async function fetchEnContexto(...args){
  const c=control.getStore();if(!c)return globalThis.fetch(...args);
  if(c.enCurso||c.newmanActivo)throw Error('PETICION_CONCURRENTE');
  c.enCurso++;try{const res=await c.fetcher(...args),data=await res.json().catch(()=>null);
    return{status:res.status,headers:res.headers,json:async()=>data};}finally{c.enCurso--;}
}
export const conPeticiones=(fetcher,task)=>control.run({fetcher,enCurso:0,newmanActivo:false},task);
export function leerEnv(proceso=process.env,archivo=path.join(ROOT,'.env.qa')){
  const e={};if(proceso.QA_AUTORIZADO==='SI'&&fs.existsSync(archivo))
    for(const line of fs.readFileSync(archivo,'utf8').split(/\r?\n/)){
      const m=line.match(/^\s*([A-Z][A-Z0-9_]*)\s*=(.*)$/);
      if(m)e[m[1]]=m[2].trim().replace(/^(['"])(.*)\1$/,'$2');}
  Object.assign(e,proceso);e.QA_AUTORIZADO=proceso.QA_AUTORIZADO;return e;
}
export function contexto(argv,ensayo=false){
  const v=k=>argv.includes(k)?argv[argv.indexOf(k)+1]:null;
  const operacion=v('--operacion'),version=Number(v('--version')),intento=Number(v('--intento'));
  const runId=v('--run-id'),referencia=v('--autorizacion'),archivo=path.resolve(v('--contexto')??'.');
  if(!CAPACIDADES.operaciones.includes(operacion)||!Number.isInteger(version)||version<1||
    !Number.isInteger(intento)||intento<1||!referencia||!new RegExp(`^RUN-G39-V${version}-\\d{8}-\\d{6}$`).test(runId??''))
    throw Error('Contexto de RUN incompleto');
  const directorio=ensayo?path.dirname(archivo):path.join(DIR,...(version===1?['Resultados',runId]:[`EvaluacionV${version}`,'Resultados',runId]));
  if(ensayo&&(path.basename(directorio)!==runId||!directorio.startsWith(path.resolve(os.tmpdir())+path.sep)))
    throw Error('Ensayo fuera del directorio temporal');
  if(path.dirname(archivo)!==directorio||path.basename(archivo)!=='contexto_operacion.json')throw Error('Contexto fuera del RUN');
  const c=JSON.parse(fs.readFileSync(archivo,'utf8'));
  if(c.grupo!=='G39'||c.run_id!==runId||c.version!==version||c.intento!==intento||c.operacion!==operacion.toUpperCase()||
    c.referencia!==referencia||JSON.stringify(c.casos)!==JSON.stringify(CASOS))throw Error('Contexto incoherente');
  return{operacion,version,intento,runId,referencia,directorio,ensayo};
}
export function preflight(c,e,newman=versionNewman()){
  const barreras=['SIGAB_API_TEST_BASE','QA_SANDBOX_SECRET','QA_CONTADOR_EMAIL','QA_CONTADOR_PASSWORD',
    'QA_ADMIN_EMAIL','QA_ADMIN_PASSWORD'].filter(k=>!String(e[k]??'').trim());
  if(e.QA_AUTORIZADO!=='SI')barreras.push('QA_AUTORIZADO');
  const base=String(e.SIGAB_API_TEST_BASE??'').replace(/\/+$/,'');
  if(c.ensayo?!/^http:\/\/(127\.0\.0\.1|localhost):\d+$/.test(base):base!==API)barreras.push('API_NO_CANONICA');
  if(!newman)barreras.push('NEWMAN_NO_DISPONIBLE');
  if(sha(COL)!==SHA.coleccion||sha(CONTRACT)!==SHA.contrato)barreras.push('HUELLA_ARCHIVO');
  return{grupo:'G39',run_id:c.runId,ok:!barreras.length,fase:'PREFLIGHT',barreras,presupuesto:PRESUPUESTO,
    herramientas:{node:process.version,newman},efectos_externos:['Dos logins y su auditoría persisten.',
      'Procesamiento M06 puede atender eventos pendientes ajenos.']};
}
export function comprobar(){
  const faltan=['g39.mjs','lib/g39_core.mjs','G39.postman_collection.json','pruebas/contrato_g39.json',
    'pruebas/newman_hijo.mjs','pruebas/registro_qa.mjs','README.md'].filter(p=>!fs.existsSync(path.join(DIR,p)));
  const items=JSON.parse(fs.readFileSync(COL,'utf8')).item??[];
  const actores=items.every(x=>validarActor(x.name,entrada(x.name).actor)&&
    x.request.header.some(h=>h.key==='Authorization'&&h.value===`Bearer {{${entrada(x.name).actor}_token}}`));
  const superior=fs.existsSync(path.join(DIR,'Resultados'))&&fs.readdirSync(path.join(DIR,'Resultados')).some(x=>x.endsWith('.md'));
  const ok=!faltan.length&&items.length===3&&actores&&!superior&&sha(COL)===SHA.coleccion&&sha(CONTRACT)===SHA.contrato;
  console.log(JSON.stringify({grupo:'G39',ok,faltan,newman_local:versionNewman(),items:items.length,
    actores_correctos:actores,markdown_superior:!!superior,presupuesto:PRESUPUESTO}));return ok?0:2;
}
export function contrastarRespuesta(r,id,actor,http,data,ruta){
  let motivo=null;try{const p=entrada(id);
    const check=(t,v,k)=>{if(typeof t==='string'){
      const real=v===null?'null':Array.isArray(v)?'array':typeof v;
      if(v===undefined||!t.split('|').includes(real)&&!(t.includes('decimal')&&real==='string'&&/^-?\d+(\.\d+)?$/.test(v)))
        throw Error(`Esquema discordante: ${k}; esperado ${t}, llegó ${real}`);
    }else if(Array.isArray(t)){if(!Array.isArray(v))throw Error(`Esquema discordante: ${k}; esperado array`);
      v.forEach((x,i)=>check(t[0],x,`${k}[${i}]`));}
    else{if(!v||typeof v!=='object'||Array.isArray(v))throw Error(`Esquema discordante: ${k}; esperado objeto`);
      for(const [campo,valor] of Object.entries(t))check(valor,v[campo],`${k}.${campo}`);}};
    check(p.tipo==='array'?[p.campos]:p.campos,data,id);validarDecimales(id,data);
  }catch(e){motivo=e.message;}
  const fila={id,ruta:ruta??entrada(id).ruta,actor,http,resultado:motivo?'discrepa':'coincide',...(motivo?{motivo}:{})};
  r.contraste_contrato.push(fila);if(motivo){r.discrepancias_contrato.push(fila);r.problemas_tecnicos.push(`Contrato ${id}: ${motivo}`);}return !motivo;
}
export function verificarPermisos(data,actor){
  if(!Array.isArray(data?.permisos))throw Error(`Permisos ${actor}: esquema inválido`);
  for(const p of CONTRATO.peticiones.filter(x=>x.actor===actor)){
    const [recurso,accion]=p.permiso.split(':');
    if(!data.permisos.some(x=>x.nombre_recurso===recurso&&Number(x.id_accion)===Number(accion)))
      throw Error(`Permisos ${actor}: falta ${p.permiso}`);
  }return true;
}
function resultado(c){return{grupo:'G39',run_id:c.runId,autorizacion_referencia:c.referencia,version:c.version,intento:c.intento,
  casos:{},comprobaciones:[],solicitudes:[],evidencias:[],incidencias:[],problemas_tecnicos:[],contraste_contrato:[],
  discrepancias_contrato:[],observaciones:{},herramientas:{node:process.version,newman:null},cypress:{total_pruebas:0},
  cierre:{run:{cierre_http:null},rollback:{verificado:false}},oficial:false,consume_version:false};}
function registrar(r,caso,estado,motivo,observado={}){
  r.casos[caso]={caso:`TC-M06-G39 / ${caso}`,estado,motivo:limpio(motivo),observado};
  r.comprobaciones.push({caso,fuente:'API',id:IDS[CASOS.indexOf(caso)],tipo:'ASSERT',estado,motivo:limpio(motivo),evidencia:'resultado.json'});
}
async function login(api,correo,clave){
  const res=await fetchEnContexto(`${api}/sesiones/`,{method:'POST',redirect:'manual',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({correo_electronico:correo,contrasena:clave}),signal:AbortSignal.timeout(120000)});
  const d=await res.json();return res.status===200?d?.token:null;
}
async function pedir(r,api,id,ruta,actor,tokens,c,body){
  validarActor(id,actor);const p=entrada(id);if(r.solicitudes.length>=120||Date.now()>r._limite)throw Error('PRESUPUESTO_AGOTADO');
  const fila={id,metodo:p.metodo,ruta:ruta.split('?')[0],actor,http:null};r.solicitudes.push(fila);
  try{const res=await fetchEnContexto(api+ruta,{method:p.metodo,redirect:'manual',headers:{Authorization:`Bearer ${tokens[actor]}`,
    'X-Test-Run-Id':c.runId,'X-Sandbox-Secret':tokens.secreto,...(body===undefined?{}:{'Content-Type':'application/json'})},
    body:body===undefined?undefined:JSON.stringify(body),signal:AbortSignal.timeout(p.metodo==='GET'?30000:120000)});
    const data=await res.json();fila.http=res.status;fila.eco=res.headers.get('x-test-run-id')===c.runId;
    fila.codigo=res.status>=400?limpio(data?.error_code??data?.code):null;
    const valido=res.status===(p.http??200)?contrastarRespuesta(r,id,actor,res.status,data,ruta):false;
    fila.contrato=valido?'coincide':'no_contrastable';return{http:res.status,data,eco:fila.eco,valido,codigo:fila.codigo};
  }catch(e){if(e.message==='PETICION_CONCURRENTE')throw e;fila.fallo=e.name==='TimeoutError'?'TIMEOUT':'SIN_RESPUESTA';
    return{http:null,data:null,eco:false,valido:false,codigo:fila.fallo};}
}
const bien=(x,http=200)=>x.http===http&&x.eco&&x.valido;
export function oraculoMano({registro,lineas,matriz,especie,activo,monto}){
  const id=num(registro?.id_registro_costo),l=lineas.filter(x=>x.tabla_origen==='registros_costos'&&num(x.id_origen)===id);
  const par=resolverMatriz(matriz,'MANO_OBRA_PROPIA','UNICO',especie,'MANO_OBRA');
  const fallos=[];
  if(registro?.vehiculo_contable!=='ASIENTO_NIC41'||!num(registro?.id_linea_asiento))fallos.push('vehículo o ID de línea de mano de obra');
  if(l.length!==1)fallos.push(`líneas de mano de obra: ${l.length}`);
  const x=l[0];if(x&&(!par||x.tipo_hecho!=='MANO_OBRA_PROPIA'||x.sentido!=='UNICO'||x.estado!=='REGISTRADA'||
    num(x.id_activo_biologico)!==activo||num(x.id_linea_asiento_nic41)!==num(registro.id_linea_asiento)||
    !igual(x.valor,monto)||x.cuenta_debito!==par.cuenta_debito||x.cuenta_credito!==par.cuenta_credito))fallos.push('tipo, valor, cuentas, estado o vínculo de mano de obra');
  return{estado:fallos.length?'RECHAZADO':'APROBADO',motivo:fallos.join('; ')||`Línea MANO_OBRA_PROPIA/UNICO ${monto} conforme.`};
}
export function oraculoBaja({evento,activo,valor,lineas,matriz,especie,tipo}){
  const id=num(evento),sentido=tipo==='venta'?'UNICO':'PERDIDA',par=resolverMatriz(matriz,'BAJA_ACTIVO',sentido,especie);
  const propias=lineas.filter(x=>x.tabla_origen==='procesamientos_eventos_m02'&&num(x.id_origen)===id);
  const baja=propias.filter(x=>x.tipo_hecho==='BAJA_ACTIVO'),fallos=[];
  if(baja.length!==1)fallos.push(`líneas BAJA_ACTIVO: ${baja.length}`);
  const x=baja[0];if(x&&(!par||num(x.id_activo_biologico)!==activo||x.sentido!==sentido||x.estado!=='REGISTRADA'||
    !igual(x.valor,truncar2(valor))||x.cuenta_debito!==par.cuenta_debito||x.cuenta_credito!==par.cuenta_credito))
    fallos.push('valor en libros truncado, sentido, cuentas, estado o vínculo de baja');
  if(tipo==='venta'&&lineas.some(x=>num(x.id_activo_biologico)===activo&&x.tipo_hecho!=='BAJA_ACTIVO'))
    fallos.push('línea adicional de ingreso u otro hecho en venta');
  return{estado:fallos.length?'RECHAZADO':'APROBADO',motivo:fallos.join('; ')||`BAJA_ACTIVO/${sentido} ${truncar2(valor)} conforme.`};
}
async function newman(r,c,api,tokens,periodo,activo){
  const state=control.getStore();if(state?.enCurso||state?.newmanActivo)throw Error('PETICION_CONCURRENTE');
  const env={values:Object.entries({base_url:api,run_id:c.runId,sandbox_secret:tokens.secreto,
    contador_token:tokens.contador,periodo:String(periodo),activo:String(activo)}).map(([key,value])=>({key,value,enabled:true}))};
  const sub=path.join(c.directorio,'newman');fs.mkdirSync(sub,{recursive:true});if(state)state.newmanActivo=true;
  let out;try{out=await new Promise(resolve=>{
    let hijo;try{hijo=spawn(process.execPath,[path.join(DIR,'pruebas','newman_hijo.mjs')],
      {stdio:['pipe','pipe','pipe'],timeout:160000,windowsHide:true});}
    catch(error){resolve({code:null,stdout:'',error});return;}
    let stdout='',error=null;hijo.stdout.setEncoding('utf8').on('data',x=>{stdout+=x;if(stdout.length>1048576)hijo.kill();});
    hijo.stderr.resume();hijo.on('error',e=>error=e);hijo.on('close',code=>resolve({code,stdout,error}));
    hijo.stdin.on('error',()=>{});hijo.stdin.end(JSON.stringify({coleccion:JSON.parse(fs.readFileSync(COL,'utf8')),
      environment:env,timeout:30000,salida:sub}));
  });if(c.ensayo&&out.error?.code==='EPERM'){
    const {ejecutarNewman}=await import('./pruebas/newman_hijo.mjs');
    const x=await ejecutarNewman({coleccion:JSON.parse(fs.readFileSync(COL,'utf8')),environment:env,timeout:30000,salida:sub});
    out={code:x.fallido?2:0,stdout:JSON.stringify(x),error:null};
  }}finally{if(state)state.newmanActivo=false;}
  let resumen={};try{resumen=JSON.parse(out.stdout);}catch{resumen={error:'SALIDA_INVALIDA'};}
  for(const s of resumen.solicitudes??[])if(s.contraste){r.contraste_contrato.push({...s.contraste,fuente:'Newman'});
    if(s.contraste.resultado==='discrepa')r.discrepancias_contrato.push(s.contraste);}
  r.herramientas.newman={version:versionNewman(),iteraciones:resumen.solicitudes?.length===3?1:0,
    fallos:resumen.solicitudes?.flatMap(x=>x.aserciones??[]).filter(x=>x.error).length??3,
    codigo:out.code,error:out.error?.code??resumen.error??null};
  if(fs.existsSync(path.join(sub,'newman-G39.json'))&&fs.existsSync(path.join(sub,'newman-G39.html')))
    r.evidencias.push('newman/newman-G39.json','newman/newman-G39.html');
  if(out.code!==0||r.herramientas.newman.fallos)r.problemas_tecnicos.push('Newman no completó tres lecturas.');
}
async function cerrar(r,c,api,tokens,h){
  const res=await fetchEnContexto(`${api}/test-control/runs/${c.runId}`,{method:'DELETE',headers:{
    Authorization:`Bearer ${tokens.contador}`,'X-Sandbox-Secret':tokens.secreto},signal:AbortSignal.timeout(120000)});
  r.cierre.run.cierre_http=res.status;
  if(res.status!==200){r.cierre.rollback={verificado:false,motivo:`DELETE HTTP ${res.status}`};return;}
  if(!h.escrituras){r.cierre.rollback={verificado:!h.inciertas,
    motivo:h.inciertas?'Escritura incierta; rollback no demostrable.':'Sin escrituras; DELETE 200.'};return;}
  const lecturas=[],presentes=[];
  for(const [ruta,actor,tipo,ids] of [
    [`/finanzas/costos?id_activo_biologico=${h.activoCosto}`,'contador','id_registro_costo',h.costos],
    [`/finanzas/lineas?id_periodo_contable=${h.periodo}`,'contador','id_linea_asiento_nic41',h.lineas],
    ...h.eventos.map(x=>[`/activos-biologicos/${x.activo}/eventos`,'admin','id_eventos',[x.id]])]){
    const res=await fetchEnContexto(api+ruta,{method:'GET',headers:{Authorization:`Bearer ${tokens[actor]}`},
      signal:AbortSignal.timeout(30000)}),data=await res.json().catch(()=>null);
    lecturas.push({ruta,http:res.status});const xs=Array.isArray(data)?data:data?.eventos;
    if(res.status!==200||!Array.isArray(xs)){presentes.push(`${ruta}: lectura incompleta`);continue;}
    for(const x of xs)if(ids.includes(num(x[tipo])))presentes.push(`${ruta}:${x[tipo]}`);
  }
  for(const x of h.eventos){
    const ruta=`/activos-biologicos/${x.activo}/ficha-integral`;
    const res=await fetchEnContexto(api+ruta,{method:'GET',headers:{Authorization:`Bearer ${tokens.admin}`},
      signal:AbortSignal.timeout(30000)}),data=await res.json().catch(()=>null);
    lecturas.push({ruta,http:res.status});
    if(res.status!==200||data?.estado_actual!=='ACTIVO')presentes.push(`${ruta}: estado no restaurado`);
  }
  r.cierre.lecturas_poscierre=lecturas;
  r.cierre.rollback={verificado:!presentes.length&&!h.inciertas,motivo:presentes.join('; ')||
    (h.inciertas?'Escritura incierta.':'IDs del RUN ausentes en lecturas públicas.')};
}
export function informe(c,r){
  const v=x=>limpio(x??'sin dato');
  const estados=CASOS.map(k=>r.casos[k]?.estado??'NO_CONCLUYENTE');
  const titulo=new Set(estados).size===1?estados[0]:'RESULTADO MIXTO';
  const filas=CASOS.map(k=>`| ${k} | ${v(r.casos[k]?.estado)} | ${v(r.casos[k]?.motivo)} |`).join('\n');
  const detalle=CASOS.map(k=>`### ${k}\n\n- Esperado: ${k.endsWith('016')?
    'CONSUMO_INVENTARIO manual → 422 sin costo ni línea; MANO_OBRA_PROPIA → una línea según RF-109; COMPRA_PROVEEDOR y SERVICIO_TERCERO → sin línea.':
    'Venta y muerte → una BAJA_ACTIVO por valor en libros truncado, sentidos y cuentas RF-109; venta sin línea de ingreso.'}\n- Observado (valores, cuentas e IDs de la API):\n\n\`\`\`json\n${JSON.stringify(r.casos[k]?.observado??{},null,2)}\n\`\`\`\n\n- Comparación y decisión: **${v(r.casos[k]?.estado)}**. ${v(r.casos[k]?.motivo)}\n`).join('\n');
  const contraste=[...new Map(r.contraste_contrato.map(x=>[`${x.ruta}|${x.fuente??'ejecutor'}`,x])).values()]
    .map(x=>`- \`${v(x.ruta)}\` (${v(x.fuente??'ejecutor')}): ${v(x.resultado)}, HTTP ${v(x.http)}${x.motivo?`; ${v(x.motivo)}`:''}.`).join('\n')||'- Sin contraste registrado.';
  const incidencias=r.incidencias.map(x=>`- ${v(x.caso)}: ${v(x.titulo)}. ${v(x.equipo_inicial)}; ${v(x.severidad)}; ${v(x.certeza)}. ${v(x.justificacion_severidad)}. Causa raíz: ${v(x.causa_raiz)}.`).join('\n')||'Ninguna incidencia de producto.';
  return `# TC-M06-G39 — ${titulo}\n\n## Identificación\n\nGrupo G39; casos TC-M06-016 y TC-M06-017; RF-86 v2.0; RUN ${c.runId}; versión ${c.version}; intento ${c.intento}; autorización ${c.referencia}; ambiente ${c.ensayo?'loopback local':'TEST'}; commit no consultado. Node ${process.version}; Newman ${v(r.herramientas.newman?.version)}. Oficial ${r.oficial}.\n\n## Veredictos\n\n| Caso | Estado | Fundamento |\n| --- | --- | --- |\n${filas}\n\n## Detalle por caso\n\n${detalle}\nComprobaciones API ${r.comprobaciones.length}; UI 0 (solo API); solicitudes del ejecutor ${r.solicitudes.length}/150.\n\n## Contraste de contrato\n\n${contraste}\n\nDiscrepancias: ${r.discrepancias_contrato.length}.\n\n## Evidencias reales\n\n${r.evidencias.map(x=>`- ${x}`).join('\n')}\n\n## Incidencias\n\n${incidencias}\n\nProblemas técnicos: ${r.problemas_tecnicos.join('; ')||'ninguno'}. La primera discrepancia pública orienta la atención; la causa raíz requiere investigación.\n\n## Observación de configuración\n\nCon política GASTO, la matriz de TEST conocida asigna 158405 como débito de MANO_OBRA_PROPIA/UNICO, cuenta del activo biológico en TB/PM. El oráculo usa la matriz leída. QA debe decidir si reporta la configuración.\n\n## Cierre y rollback\n\nDELETE HTTP ${v(r.cierre.run.cierre_http)}; rollback ${r.cierre.rollback.verificado?'verificado':'no verificado'}: ${v(r.cierre.rollback.motivo)}. Lecturas poscierre: ${(r.cierre.lecturas_poscierre??[]).map(x=>`${v(x.ruta)} HTTP ${v(x.http)}`).join('; ')||'ninguna'}.\n\n## Conclusión\n\nRegistro ${r.oficial?'OFICIAL':'NO OFICIAL'}. ${r.incidencias.length?'Derivar las incidencias según evidencia y revisar la configuración observada.':'Revisar la observación de configuración; sin acción correctiva de producto acreditada.'}\n`;
}
export async function evaluar(c,e){
  if(e.QA_AUTORIZADO!=='SI'||!fs.existsSync(c.directorio))throw Error('RUN no autorizado o no preparado');
  const api=String(e.SIGAB_API_TEST_BASE).replace(/\/+$/,'');
  const r=resultado(c),h={periodo:null,activoCosto:null,escrituras:false,inciertas:false,costos:[],lineas:[],eventos:[]};
  r._limite=Date.now()+1800000;let tokens=null;
  try{
    const contador=await login(api,e.QA_CONTADOR_EMAIL,e.QA_CONTADOR_PASSWORD);
    const admin=await login(api,e.QA_ADMIN_EMAIL,e.QA_ADMIN_PASSWORD);
    if(!contador||!admin)throw Error('Login no confirmado');tokens={contador,admin,secreto:e.QA_SANDBOX_SECRET};
    for(const actor of ['contador','admin']){
      const res=await fetchEnContexto(api+CONTRATO.lectura_permisos.ruta,{method:'GET',headers:{
        Authorization:`Bearer ${tokens[actor]}`,'X-Test-Run-Id':c.runId,'X-Sandbox-Secret':tokens.secreto},
        signal:AbortSignal.timeout(30000)}),data=await res.json();
      r.solicitudes.push({id:'permisos',actor,metodo:'GET',http:res.status});
      if(res.status!==200||res.headers.get('x-test-run-id')!==c.runId)throw Error(`Permisos ${actor}: HTTP o eco`);
      verificarPermisos(data,actor);
    }
    const q=async(id,ruta,actor='contador',body)=>{
      const x=await pedir(r,api,id,ruta,actor,tokens,c,body);
      if(entrada(id).metodo!=='GET'&&x.http===null)h.inciertas=true;
      if(['costo_post','costo_reservado','baja'].includes(id)&&x.http===201){
        h.escrituras=true;if(!x.valido)h.inciertas=true;
      }
      return x;
    };
    const activos=await q('activos','/finanzas/activos'),periodos=await q('periodos','/finanzas/periodos');
    if(!bien(activos)||!bien(periodos))throw Error('Catálogo o períodos ilegibles');
    const precios=new Map();for(const especie of new Set(activos.data.map(x=>x.id_especie))){
      const x=await q('precios_get',`/finanzas/precios?id_especie=${especie}`);
      if(!bien(x))throw Error('Precios ilegibles');precios.set(especie,x.data);}
    const candidatos=[];for(const x of activos.data){
      if(!/bovin/i.test(x.especie??'')||x.tipo!=='INDIVIDUAL'||x.estado!=='ACTIVO')continue;
      const id=num(x.id_activo_biologico),d=await q('activo_detalle',`/finanzas/activos/${id}`);
      const f=await q('ficha',`/activos-biologicos/${id}/ficha-integral`,'admin');
      if(!bien(d)||!bien(f))throw Error('Detalle o ficha ilegible');
      const calculo=d.data.calculos.filter(z=>z.estado==='CALCULADO'&&z.json_metodo_costo?.es_producto!==true)
        .sort((a,b)=>String(b.fecha_calculo).localeCompare(String(a.fecha_calculo)||b.id_calculo_valor_razonable-a.id_calculo_valor_razonable))[0];
      const periodo=periodoDestino(periodos.data,d.data.activo.numero_id_tributaria,hoy());
      const precio=vigente(precios.get(x.id_especie)??[],x.id_especie,hoy());
      const valor=x.valorado_por_costo?x.valor_contable_por_costo:calculo?.valor_neto;
      candidatos.push({...x,calculo,periodo,precio,valor,apto:!!periodo&&periodo.fecha_inicio<=hoy()&&
        periodo.fecha_fin>=hoy()&&!!precio&&(x.valorado_por_costo||!!calculo)&&
        Number(valor)>0&&f.data.estado_actual==='ACTIVO'});
    }
    r.observaciones.candidatos=candidatos.map(x=>({activo:x.id_activo_biologico,apto:x.apto,
      valorado_por_costo:x.valorado_por_costo,valor_libros:x.valor??null}));
    const porPeriodo=new Map();for(const x of candidatos.filter(z=>z.apto)){
      const pid=num(x.periodo.id_periodo_contable);if(!porPeriodo.has(pid))porPeriodo.set(pid,[]);porPeriodo.get(pid).push(x);}
    const grupo=[...porPeriodo.values()].find(xs=>xs.length>=3&&xs.some(x=>!x.valorado_por_costo))??[];
    const seleccion=[grupo.find(x=>!x.valorado_por_costo),...grupo.filter(x=>!x.valorado_por_costo).slice(1,3)]
      .filter((x,i,a)=>x&&a.indexOf(x)===i);
    const s16=seleccion[0]??null,otros=grupo.filter(x=>x!==s16).slice(0,2);
    if(!s16)registrar(r,CASOS[0],'BLOQUEADO','Sin bovino individual ACTIVO a valor razonable, reconocido, con precio y período abierto.');
    if(otros.length<2)registrar(r,CASOS[1],'BLOQUEADO','Sin dos bovinos distintos aptos para las bajas; datos imprescindibles no preparables.');
    const pid=num((s16??otros[0])?.periodo?.id_periodo_contable);
    if(!pid)return r;h.periodo=pid;h.activoCosto=num(s16?.id_activo_biologico);
    const cfg=await q('configuracion','/finanzas/configuracion');
    const baseLineas=await q('lineas',`/finanzas/lineas?id_periodo_contable=${pid}`);
    const costosPrevios=s16?await q('costos_get',`/finanzas/costos?id_activo_biologico=${h.activoCosto}`):null;
    if(!bien(cfg)||!bien(baseLineas)||costosPrevios&&!bien(costosPrevios)||r.discrepancias_contrato.length)
      throw Error('Lecturas previas o contrato discordantes; sin escrituras');
    let lineas=baseLineas.data,costos=costosPrevios?.data??[];
    const par=(tipo,sentido,especie,subtipo)=>resolverMatriz(cfg.data.matriz,tipo,sentido,especie,subtipo);
    if(s16&&(!par('MANO_OBRA_PROPIA','UNICO',s16.id_especie,'MANO_OBRA')||
      !par('CONSUMO_INSUMO','UNICO',s16.id_especie,'ALIMENTO')||
      !par('CONSUMO_INSUMO','UNICO',s16.id_especie,'VETERINARIO'))){
      registrar(r,CASOS[0],'BLOQUEADO','Matriz RF-109 sin MANO_OBRA_PROPIA/UNICO o CONSUMO_INSUMO/UNICO; precondición de costos no preparable.');}
    if(otros.length===2&&(!par('BAJA_ACTIVO','UNICO',otros[0].id_especie)||!par('BAJA_ACTIVO','PERDIDA',otros[1].id_especie)))
      registrar(r,CASOS[1],'BLOQUEADO','Matriz RF-109 sin BAJA_ACTIVO/UNICO o BAJA_ACTIVO/PERDIDA; precondición de bajas no preparable.');
    const leerLineas=async()=>{const x=await q('lineas',`/finanzas/lineas?id_periodo_contable=${pid}`);
      if(!bien(x)){h.inciertas=true;throw Error('Líneas ilegibles');}const nuevas=idsNuevos(lineas,x.data,'id_linea_asiento_nic41');
      h.lineas.push(...nuevas.map(z=>num(z.id_linea_asiento_nic41)));lineas=x.data;return nuevas;};
    const leerCostos=async()=>{const x=await q('costos_get',`/finanzas/costos?id_activo_biologico=${h.activoCosto}`);
      if(!bien(x)){h.inciertas=true;throw Error('Costos ilegibles');}const nuevos=idsNuevos(costos,x.data,'id_registro_costo');
      h.costos.push(...nuevos.map(z=>num(z.id_registro_costo)));costos=x.data;return nuevos;};
    if(s16&&!r.casos[CASOS[0]]){
      const aid=h.activoCosto,fecha=hoy(),observado={activo:aid,periodo:pid,operaciones:[]},fallos=[];
      let bloqueoCosto=null;
      const base={id_activo_biologico:aid,fecha_costo:fecha,monto_costo:'123.45',justificacion:`QA ${c.runId}`};
      const reservar=await q('costo_reservado','/finanzas/costos','contador',
        {...base,subtipo_costo:'ALIMENTO',origen_costo:'CONSUMO_INVENTARIO'});
      const trasReserva=await leerCostos(),lineasReserva=await leerLineas();
      if(trasReserva.length||lineasReserva.length)h.escrituras=true;
      observado.operaciones.push({origen:'CONSUMO_INVENTARIO',http:reservar.http,codigo:reservar.codigo,
        costos_nuevos:trasReserva.length,lineas_nuevas:lineasReserva.length});
      if(!bien(reservar,422)||reservar.codigo!=='ORIGEN_RESERVADO_M05')fallos.push(`CONSUMO_INVENTARIO: HTTP ${reservar.http}, código ${reservar.codigo}`);
      if(trasReserva.length||lineasReserva.length)fallos.push('CONSUMO_INVENTARIO creó costo o línea');
      const flujos=[['MANO_OBRA_PROPIA','MANO_OBRA'],['COMPRA_PROVEEDOR','ALIMENTO'],['SERVICIO_TERCERO','VETERINARIO']];
      for(const [origen,subtipo] of flujos){
        const factura=origen==='MANO_OBRA_PROPIA'?{}:{tercero_nit:'900000123',tercero_dv:'4',
          tercero_razon_social:'Proveedor ficticio QA',factura_prefijo:'QA',
          factura_numero:`${c.runId.slice(-15)}${origen==='COMPRA_PROVEEDOR'?'C':'S'}`,
          fecha_factura:fecha,fecha_vencimiento_factura:fecha};
        const x=await q('costo_post','/finanzas/costos','contador',{...base,subtipo_costo:subtipo,origen_costo:origen,...factura});
        if(bien(x,201))h.escrituras=true;
        const nuevosCostos=await leerCostos(),nuevasLineas=await leerLineas();
        const reg=x.data?.registros?.[0],id=num(reg?.id_registro_costo);
        observado.operaciones.push({origen,http:x.http,codigo:x.codigo,id_costo:id,vehiculo:reg?.vehiculo_contable??null,
          id_linea:reg?.id_linea_asiento??null,costos_nuevos:nuevosCostos.map(z=>z.id_registro_costo),
          lineas_nuevas:nuevasLineas.map(z=>({id:z.id_linea_asiento_nic41,tipo:z.tipo_hecho,sentido:z.sentido,
            valor:z.valor,debito:z.cuenta_debito,credito:z.cuenta_credito,estado:z.estado,
            tabla_origen:z.tabla_origen,origen:z.id_origen}))});
        if(!bien(x,201)||!id){
          if(origen!=='MANO_OBRA_PROPIA'&&x.http===422&&['CUENTA_NO_CONFIGURADA','DATOS_PROVEEDOR_INCOMPLETOS','FACTURA_DUPLICADA'].includes(x.codigo))
            bloqueoCosto=`${origen}: precondición de factura/cuenta no satisfecha (HTTP 422 ${x.codigo}); revisar datos antes de repetir.`;
          else fallos.push(`${origen}: HTTP ${x.http}, código ${x.codigo}`);
          continue;}
        if(nuevosCostos.length!==1||num(nuevosCostos[0]?.id_registro_costo)!==id)fallos.push(`${origen}: costo no encontrado por GET`);
        if(origen==='MANO_OBRA_PROPIA'){
          const o=oraculoMano({registro:reg,lineas:nuevasLineas,matriz:cfg.data.matriz,especie:s16.id_especie,activo:aid,monto:base.monto_costo});
          if(o.estado!=='APROBADO')fallos.push(o.motivo);
          if(nuevasLineas.length!==1)fallos.push(`MANO_OBRA_PROPIA generó ${nuevasLineas.length} líneas nuevas`);
        }else if(reg.vehiculo_contable!=='FACTURA_COMPRA'||reg.id_linea_asiento!==null||
          nuevasLineas.length!==0)fallos.push(`${origen}: factura generó línea o vehículo incorrecto`);
      }
      registrar(r,CASOS[0],fallos.length?'RECHAZADO':bloqueoCosto?'BLOQUEADO':'APROBADO',
        fallos[0]??bloqueoCosto??'Cuatro operaciones RF-90 conformes; una línea de mano de obra, ninguna de factura.',observado);
    }
    if(otros.length===2&&!r.casos[CASOS[1]]){
      const observado={bajas:[]},fallos=[];
      for(const [i,tipo] of ['venta','muerte'].entries()){
        const activo=otros[i],aid=num(activo.id_activo_biologico),antes=lineas;
        const x=await q('baja',`/activos-biologicos/${aid}/eventos/baja`,'admin',
          {tipo_baja:tipo,fecha_baja:hoy(),motivo_baja:`Baja QA ${c.runId}`});
        if(bien(x,201))h.escrituras=true;
        const evento=num(x.data?.id_eventos);if(evento)h.eventos.push({id:evento,activo:aid});
        let proc=null;if(bien(x,201)&&evento)proc=await q('procesar','/finanzas/eventos/procesar','contador',{});
        const nuevas=await leerLineas();const relevantes=nuevas.filter(z=>num(z.id_activo_biologico)===aid);
        observado.bajas.push({tipo,activo:aid,valor_libros:String(activo.valor),http_baja:x.http,codigo_baja:x.codigo,
          evento,http_procesar:proc?.http??null,lineas:relevantes.map(z=>({id:z.id_linea_asiento_nic41,
            tipo:z.tipo_hecho,sentido:z.sentido,valor:z.valor,debito:z.cuenta_debito,credito:z.cuenta_credito,
            estado:z.estado,tabla_origen:z.tabla_origen,origen:z.id_origen}))});
        if(!bien(x,201)||!evento){fallos.push(`${tipo}: baja HTTP ${x.http}, código ${x.codigo}`);continue;}
        if(!bien(proc)){fallos.push(`${tipo}: procesar HTTP ${proc?.http}`);continue;}
        const o=oraculoBaja({evento,activo:aid,valor:activo.valor,lineas:relevantes,matriz:cfg.data.matriz,
          especie:activo.id_especie,tipo});
        if(o.estado!=='APROBADO')fallos.push(`${tipo}: ${o.motivo}`);
        if(relevantes.length!==1)fallos.push(`${tipo}: ${relevantes.length} líneas nuevas del activo`);
        if(antes.length+nuevas.length!==lineas.length)throw Error('Inventario de líneas incoherente');
      }
      registrar(r,CASOS[1],fallos.length?'RECHAZADO':'APROBADO',fallos[0]??'Venta y muerte con BAJA_ACTIVO por valor en libros; venta sin ingreso.',observado);
    }
    if(!c.sinNewman)await newman(r,c,api,tokens,pid,h.activoCosto??num(otros[0]?.id_activo_biologico));
  }catch(error){r.problemas_tecnicos.push(limpio(error.message));for(const caso of CASOS)if(!r.casos[caso])
    registrar(r,caso,'NO_CONCLUYENTE',`Automatización o datos: ${error.message}`);}
  finally{
    if(tokens)try{await cerrar(r,c,api,tokens,h);}catch(error){r.cierre.rollback={verificado:false,motivo:limpio(error.message)};}
    for(const caso of CASOS)if(!r.casos[caso])registrar(r,caso,'NO_CONCLUYENTE','Sin comprobación completa.');
    if(r.discrepancias_contrato.length)for(const caso of CASOS){r.casos[caso].estado='NO_CONCLUYENTE';r.casos[caso].motivo='Contrato de API discordante; revisar automatización.';}
    for(const x of r.comprobaciones){x.estado=r.casos[x.caso].estado;x.motivo=r.casos[x.caso].motivo;}
    for(const caso of CASOS)if(r.casos[caso].estado==='RECHAZADO')r.incidencias.push({caso,
      titulo:caso===CASOS[0]?'Costos incumplen RF-86':'Bajas incumplen RF-86',severidad:'ALTA',
      justificacion_severidad:'Registro contable relevante ausente o indebido, sin alternativa documentada.',
      equipo_inicial:'Desarrollo',fundamento_equipo:'Primera discrepancia comprobada en API pública de M06.',
      certeza:c.ensayo?'NO DETERMINADA':'CONFIRMADA',causa_raiz:'NO DETERMINADA',evidencias:['resultado.json']});
    r.oficial=!r.discrepancias_contrato.length&&r.cierre.rollback.verificado&&r.herramientas.newman?.codigo===0&&
      r.herramientas.newman.fallos===0&&CASOS.every(k=>['APROBADO','RECHAZADO'].includes(r.casos[k].estado));
    r.consume_version=r.oficial;
    r.evidencias.unshift('resultado.json',c.version===1?'TC-M06-G39_resultado.md':`TC-M06-G39_reevaluacion_V${c.version}.md`);
    guardar(path.join(c.directorio,'resultado.json'),r);
    fs.writeFileSync(path.join(c.directorio,c.version===1?'TC-M06-G39_resultado.md':`TC-M06-G39_reevaluacion_V${c.version}.md`),informe(c,r));
  }return r;
}
export async function principal(args,{proceso=process.env,archivoEnv=path.join(ROOT,'.env.qa'),fetcher=globalThis.fetch,
  ensayo=false,sinNewman=false}={}){
  const c={...contexto(args,ensayo),sinNewman:ensayo&&sinNewman},env=leerEnv(proceso,archivoEnv),p=preflight(c,env);
  guardar(path.join(c.directorio,'preflight.json'),p);if(!p.ok)return{exitCode:2,preflight:p,resultado:null};
  const r=await conPeticiones(fetcher,()=>evaluar(c,env));return{exitCode:r.oficial?0:2,preflight:p,resultado:r};
}
if(process.argv.includes('--capacidades'))console.log(JSON.stringify(CAPACIDADES,null,2));
else if(process.argv.includes('--comprobar'))process.exitCode=comprobar();
else if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
  try{const {exitCode,preflight:p,resultado:r}=await principal(process.argv.slice(2));
    console.log(JSON.stringify({grupo:'G39',run_id:p.run_id,preflight_ok:p.ok,
      ...(r?{oficial:r.oficial,estados:Object.fromEntries(CASOS.map(k=>[k,r.casos[k].estado]))}:{barreras:p.barreras})}));
    process.exitCode=exitCode;
  }catch(error){console.error(limpio(error.message));process.exitCode=2;}
}
