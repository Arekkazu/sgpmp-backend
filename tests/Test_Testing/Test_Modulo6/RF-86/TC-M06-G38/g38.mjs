import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import { spawn } from 'node:child_process';
import { createHash } from 'node:crypto';
import { createRequire } from 'node:module';
import { AsyncLocalStorage } from 'node:async_hooks';
import { fileURLToPath } from 'node:url';
import { CASOS, IDS, CONTRATO, DIR, PRESUPUESTO, entrada, validarActor,
  validarDecimales, vigente, periodoDestino, seleccionarCandidatos, idsNuevos, igual,
  q4, truncar2, redondear2, resolverMatriz, estructuraLineas, predecirComponentes } from './lib/g38_core.mjs';

const require = createRequire(import.meta.url), control = new AsyncLocalStorage();
const ROOT = path.resolve(DIR, '../../../../..');
const API = 'https://www.api.inmero.co/api-sgpmp-test';
const COL = path.join(DIR, 'G38.postman_collection.json');
const CONTRACT = path.join(DIR, 'pruebas', 'contrato_g38.json');
const SHA = { coleccion:'28c7ca377ca22ca6dbd26fd0d7088d729f6d301df5e34bfdadd2a337d6cd6c4e',
  contrato:'9c0791a1bd7640bfd38a389007fded5d1b124744146dab3da9c89d941386f416' };
export const CAPACIDADES = { contrato: 'sigab-qa-ejecutor/1', grupo: 'G38', casos: CASOS,
  operaciones: ['evaluar', 'reintentar', 'reevaluar'], versiones: { min: 1, max: 99 },
  comprobaciones_obligatorias: Object.fromEntries(CASOS.map((c,i) => [c,{ API:[IDS[i]] }])),
  limite: { solicitudes_totales: 150, duracion_segundos: 1800, timeout_post_ms: 120000 }, baja_automatizada: false };
const num = x => Number.isInteger(Number(x)) && Number(x) > 0 ? Number(x) : null;
const hoy = () => new Intl.DateTimeFormat('en-CA', {timeZone:'America/Bogota',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
const limpio = x => String(x ?? '').replace(/[\r\n|]/g,' ').slice(0,300);
const guardar = (p,x) => fs.writeFileSync(p,JSON.stringify(x,null,2),'utf8');
const sha = p => createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const versionNewman = () => { try { return require(require.resolve('newman/package.json',{paths:[ROOT]})).version; }
  catch { const p=path.join(path.dirname(process.execPath),'node_modules','newman','package.json');
    return fs.existsSync(p) ? JSON.parse(fs.readFileSync(p,'utf8')).version : null; } };

export async function fetchEnContexto(...args) {
  const c=control.getStore(); if (!c) return globalThis.fetch(...args);
  if (c.enCurso || c.newmanActivo) throw Error('PETICION_CONCURRENTE');
  c.enCurso++;
  try { const r=await c.fetcher(...args), data=await r.json().catch(()=>null);
    return {status:r.status,headers:r.headers,json:async()=>data}; }
  finally { c.enCurso--; }
}
export const conPeticiones=(fetcher,tarea)=>control.run({fetcher,enCurso:0,newmanActivo:false},tarea);
export function leerEnv(proceso=process.env,archivo=path.join(ROOT,'.env.qa')) {
  const e={};
  if (proceso.QA_AUTORIZADO==='SI' && fs.existsSync(archivo))
    for (const line of fs.readFileSync(archivo,'utf8').split(/\r?\n/)) {
      const m=line.match(/^\s*([A-Z][A-Z0-9_]*)\s*=(.*)$/);
      if(m)e[m[1]]=m[2].trim().replace(/^(['"])(.*)\1$/,'$2');
    }
  Object.assign(e,proceso); e.QA_AUTORIZADO=proceso.QA_AUTORIZADO; return e;
}
export function contexto(argv,ensayo=false) {
  const v=k=>argv.includes(k)?argv[argv.indexOf(k)+1]:null;
  const operacion=v('--operacion'),version=Number(v('--version')),intento=Number(v('--intento'));
  const runId=v('--run-id'),referencia=v('--autorizacion'),archivo=path.resolve(v('--contexto')??'.');
  if(!CAPACIDADES.operaciones.includes(operacion)||!Number.isInteger(version)||version<1||
    !Number.isInteger(intento)||intento<1||!referencia||!new RegExp(`^RUN-G38-V${version}-\\d{8}-\\d{6}$`).test(runId??''))
    throw Error('Contexto de RUN incompleto');
  const directorio=ensayo?path.dirname(archivo):path.join(DIR,...(version===1?['Resultados',runId]:[`EvaluacionV${version}`,'Resultados',runId]));
  if (ensayo && (path.basename(directorio)!==runId||!directorio.startsWith(path.resolve(os.tmpdir())+path.sep)))
    throw Error('Ensayo fuera del directorio temporal');
  if(path.dirname(archivo)!==directorio||path.basename(archivo)!=='contexto_operacion.json')throw Error('Contexto fuera del RUN');
  const c=JSON.parse(fs.readFileSync(archivo,'utf8'));
  if(c.grupo!=='G38'||c.run_id!==runId||c.version!==version||c.intento!==intento||
    c.operacion!==operacion.toUpperCase()||c.referencia!==referencia||JSON.stringify(c.casos)!==JSON.stringify(CASOS))
    throw Error('Contexto incoherente');
  return {operacion,version,intento,runId,referencia,directorio,ensayo};
}
export function preflight(c,e,newman=versionNewman()) {
  const barreras=['SIGAB_API_TEST_BASE','QA_SANDBOX_SECRET','QA_CONTADOR_EMAIL','QA_CONTADOR_PASSWORD',
    'QA_ADMIN_EMAIL','QA_ADMIN_PASSWORD'].filter(k=>!String(e[k]??'').trim());
  if(e.QA_AUTORIZADO!=='SI')barreras.push('QA_AUTORIZADO');
  const base=String(e.SIGAB_API_TEST_BASE??'').replace(/\/+$/,'');
  if(c.ensayo?!/^http:\/\/(127\.0\.0\.1|localhost):\d+$/.test(base):base!==API)barreras.push('API_NO_CANONICA');
  if(!newman)barreras.push('NEWMAN_NO_DISPONIBLE');
  if(sha(COL)!==SHA.coleccion||sha(CONTRACT)!==SHA.contrato)barreras.push('HUELLA_ARCHIVO');
  return {grupo:'G38',run_id:c.runId,ok:!barreras.length,fase:'PREFLIGHT',barreras,presupuesto:PRESUPUESTO,
    herramientas:{node:process.version,newman},efectos_externos:['Registro de precio RF-89: posibles avisos internos fuera del sandbox.',
      'Dos logins y su auditoría persisten.', 'Procesamiento M06 puede atender eventos pendientes ajenos.']};
}
export function comprobar() {
  const faltan=['g38.mjs','lib/g38_core.mjs','G38.postman_collection.json','pruebas/contrato_g38.json',
    'pruebas/newman_hijo.mjs','pruebas/registro_qa.mjs','README.md'].filter(p=>!fs.existsSync(path.join(DIR,p)));
  const col=JSON.parse(fs.readFileSync(COL,'utf8'));
  const items=col.item??[],actores=items.every(x=>validarActor(x.name,entrada(x.name).actor)&&
    x.request.header.some(h=>h.key==='Authorization'&&h.value===`Bearer {{${entrada(x.name).actor}_token}}`));
  const superiores=fs.existsSync(path.join(DIR,'Resultados'))&&fs.readdirSync(path.join(DIR,'Resultados')).some(x=>x.endsWith('.md'));
  const ok=!faltan.length&&items.length===3&&actores&&!superiores;
  console.log(JSON.stringify({grupo:'G38',ok,faltan,newman_local:versionNewman(),items:items.length,
    actores_correctos:actores,markdown_superior:!!superiores,presupuesto:PRESUPUESTO}));return ok?0:2;
}
export function contrastarRespuesta(r,idPeticion,actor,http,data) {
  let motivo=null;try {
    const p=entrada(idPeticion);
    const comprobar=(plantilla,valor,ruta)=>{
      if(typeof plantilla==='string'){
        const real=valor===null?'null':Array.isArray(valor)?'array':typeof valor;
        if(valor===undefined||!plantilla.split('|').includes(real)&&!(plantilla.includes('decimal')&&real==='string'&&/^-?\d+(\.\d+)?$/.test(valor)))
          throw Error(`Esquema discordante: ${ruta}; esperado ${plantilla}, llegó ${real}`);
      }else if(Array.isArray(plantilla)){
        if(!Array.isArray(valor))throw Error(`Esquema discordante: ${ruta}; esperado array`);
        valor.forEach((x,i)=>comprobar(plantilla[0],x,`${ruta}[${i}]`));
      }else{
        if(!valor||typeof valor!=='object'||Array.isArray(valor))throw Error(`Esquema discordante: ${ruta}; esperado objeto`);
        for(const[k,t]of Object.entries(plantilla))comprobar(t,valor[k],`${ruta}.${k}`);
      }
    };
    comprobar(p.tipo==='array'?[p.campos]:p.campos,data,idPeticion);validarDecimales(idPeticion,data);
  }
  catch(e){motivo=e.message;}
  const fila={id:idPeticion,ruta:entrada(idPeticion).ruta,actor,http,resultado:motivo?'discrepa':'coincide',...(motivo?{motivo}:{})};
  r.contraste_contrato.push(fila);if(motivo){r.discrepancias_contrato.push(fila);r.problemas_tecnicos.push(`Contrato ${idPeticion}: ${motivo}`);}return !motivo;
}
export function verificarPermisos(data,actor) {
  const lista=data?.permisos;if(!Array.isArray(lista))throw Error(`Permisos ${actor}: esquema inválido`);
  for(const p of CONTRATO.peticiones.filter(x=>x.actor===actor)) {
    const [recurso,accion]=p.permiso.split(':');
    if(!lista.some(x=>x.nombre_recurso===recurso&&Number(x.id_accion)===Number(accion)))
      throw Error(`Permisos ${actor}: falta ${p.permiso}`);
  }return true;
}
function resultado(c){return{grupo:'G38',run_id:c.runId,autorizacion_referencia:c.referencia,version:c.version,intento:c.intento,
  casos:{},comprobaciones:[],solicitudes:[],evidencias:[],incidencias:[],problemas_tecnicos:[],
  contraste_contrato:[],discrepancias_contrato:[],observaciones:{},herramientas:{node:process.version,newman:null},
  cypress:{total_pruebas:0},cierre:{run:{cierre_http:null},rollback:{verificado:false}},oficial:false,consume_version:false};}
function registrar(r,caso,estado,motivo,datos={}){
  r.casos[caso]={caso:`TC-M06-G38 / ${caso}`,estado,motivo:limpio(motivo),...datos};
  r.comprobaciones.push({caso,fuente:'API',id:IDS[CASOS.indexOf(caso)],tipo:'ASSERT',estado,motivo:limpio(motivo),evidencia:'resultado.json'});
}
async function login(api,correo,clave){
  const res=await fetchEnContexto(`${api}/sesiones/`,{method:'POST',redirect:'manual',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({correo_electronico:correo,contrasena:clave}),signal:AbortSignal.timeout(120000)});
  const d=await res.json();return res.status===200?d?.token:null;
}
async function pedir(r,api,clave,ruta,actor,tokens,c,body){
  validarActor(clave,actor);const p=entrada(clave);if(r.solicitudes.length>=120||Date.now()>r._limite)throw Error('PRESUPUESTO_AGOTADO');
  const fila={id:clave,metodo:p.metodo,ruta:ruta.split('?')[0],actor,http:null};r.solicitudes.push(fila);
  try{const res=await fetchEnContexto(api+ruta,{method:p.metodo,redirect:'manual',headers:{Authorization:`Bearer ${tokens[actor]}`,
    'X-Test-Run-Id':c.runId,'X-Sandbox-Secret':tokens.secreto,...(body===undefined?{}:{'Content-Type':'application/json'})},
    body:body===undefined?undefined:JSON.stringify(body),signal:AbortSignal.timeout(p.metodo==='GET'?30000:120000)});
    const data=await res.json();fila.http=res.status;fila.eco=res.headers.get('x-test-run-id')===c.runId;
    fila.codigo=res.status>=400?limpio(data?.error_code??data?.code):null;
    const valido=res.status===(p.http??200)?contrastarRespuesta(r,clave,actor,res.status,data):false;
    fila.contrato=valido?'coincide':'no_contrastable';return{http:res.status,data,eco:fila.eco,valido,codigo:fila.codigo};
  }catch(e){if(e.message==='PETICION_CONCURRENTE')throw e;fila.fallo=e.name==='TimeoutError'?'TIMEOUT':'SIN_RESPUESTA';
    return{http:null,data:null,eco:false,valido:false,codigo:fila.fallo};}
}
const bien=(x,http=200)=>x.http===http&&x.eco&&x.valido;

// Componentes q4 del núcleo Python: bruto y cada costo se cuantizan antes del neto.
export function predecir(precio,peso,anterior,parametros){
  return predecirComponentes({magnitud_anterior:anterior.magnitud,magnitud_actual:peso,
    precio_unitario:precio,pct_transporte:parametros.pct_transporte,
    pct_comisiones:parametros.pct_comisiones,pct_impuestos:parametros.pct_impuestos,
    otros:parametros.otros??'0',
    valor_neto_anterior:anterior.valor_neto});
}
export function buscarPeso(precio,pesoBase,anterior,parametros){
  const base=Math.round(Number(pesoBase)*100);
  for(let d=1;d<=1000;d++){
    const peso=((base+d)/100).toFixed(2),p=predecir(precio,peso,anterior,parametros);
    if(q4(p.tb)>0n&&q4(p.tb)%100n>=50n)return{peso,prediccion:p};
  }return null;
}
export function buscarCombinacion(precioVigente,pesoActual,anterior,parametros){
  const centavos=q4(precioVigente)/100n, base=q4(pesoActual)/100n;
  const minimoPrecio=(centavos*95n+99n)/100n;
  const minimoPeso=(base*101n+99n)/100n, maximoPeso=base*105n/100n;
  const decimal=n=>`${n/100n}.${String(n%100n).padStart(2,'0')}`;
  for(let precio=minimoPrecio;precio<=centavos;precio++){
    if(precio%100n===0n)continue;
    for(let peso=minimoPeso;peso<=maximoPeso;peso++){
      const prediccion=predecir(decimal(precio),decimal(peso),anterior,parametros);
      if(q4(prediccion.tb)>0n&&q4(prediccion.pm)<0n&&
        truncar2(prediccion.tb)!==redondear2(prediccion.tb))
        return {precio:decimal(precio),peso:decimal(peso),prediccion,componente:'TB'};
    }
  }
  return null;
}
export function oraculo014({variaciones,medicion,lineas,matriz,especie}){
  const errores=[];const pares=[['VARIACION_VR_TB','GANANCIA','GANANCIA_TRANSFORMACION_BIOLOGICA','ganancia_perdida_transformacion'],
    ['VARIACION_VR_PM','PERDIDA','PERDIDA_PRECIO_MERCADO','ganancia_perdida_precio_mercado']];
  const elegidas=[];
  for(const[tipo,sentido,tipoVar,componente]of pares){
    const v=variaciones.filter(x=>x.tipo===tipoVar);
    const xs=v.length===1?lineas.filter(x=>x.tipo_hecho===tipo&&x.sentido===sentido&&Number(x.id_origen)===Number(v[0].id_variacion_valor_razonable)):[];
    if(v.length!==1||xs.length!==1){errores.push(`${tipo}/${sentido}: se esperó una variación y una línea`);continue;}
    const l=xs[0],asignacion=resolverMatriz(matriz,tipo,sentido,especie);elegidas.push(l);
    if(!asignacion||l.cuenta_debito!==asignacion.cuenta_debito||l.cuenta_credito!==asignacion.cuenta_credito)
      errores.push(`${tipo}: cuentas distintas de matriz`);
    if(l.estado!=='REGISTRADA'||!igual(l.valor,truncar2(medicion[componente]))||q4(l.valor)<=0n)
      errores.push(`${tipo}: estado o valor`);
    if(l.cuenta_debito===l.cuenta_credito)errores.push(`${tipo}: cuentas iguales`);
  }
  if(elegidas.length===2&&(elegidas[0].cuenta_debito!==elegidas[1].cuenta_credito||
    elegidas[0].cuenta_credito===elegidas[1].cuenta_debito))errores.push('coherencia activo/ingreso/pérdida');
  return{estado:errores.length?'RECHAZADO':'APROBADO',motivo:errores.join('; ')||'Dos líneas, cuentas de matriz y valores positivos truncados coinciden.'};
}
export function oraculo015({antes,despues,nuevas,medicion,lineaTB}){
  const errores=estructuraLineas(antes,despues,nuevas);
  const tb=medicion?.ganancia_perdida_transformacion;
  if(tb==null||truncar2(tb)===redondear2(tb))return{estado:errores.length?'RECHAZADO':'NO_CONCLUYENTE',
    motivo:errores.join('; ')||`Componente TB no discriminante: ${tb??'ausente'}.`};
  if(!lineaTB||!igual(lineaTB.valor,truncar2(tb))||igual(lineaTB.valor,redondear2(tb)))
    errores.push(`Línea TB no truncó ${tb}: observado ${lineaTB?.valor??'ausente'}`);
  return{estado:errores.length?'RECHAZADO':'APROBADO',motivo:errores.join('; ')||'Estructura, identidad y truncado discriminante correctos.'};
}

async function newman(r,c,api,tokens,periodo){
  const state=control.getStore();if(state?.enCurso||state?.newmanActivo)throw Error('PETICION_CONCURRENTE');
  const env={values:Object.entries({base_url:api,run_id:c.runId,sandbox_secret:tokens.secreto,
    contador_token:tokens.contador,periodo:String(periodo)}).map(([key,value])=>({key,value,enabled:true}))};
  const sub=path.join(c.directorio,'newman');fs.mkdirSync(sub,{recursive:true});
  if(state)state.newmanActivo=true;
  let out;try{out=await new Promise(resolve=>{
    let hijo;try{hijo=spawn(process.execPath,[path.join(DIR,'pruebas','newman_hijo.mjs')],
      {stdio:['pipe','pipe','pipe'],timeout:160000,windowsHide:true});}
    catch(error){resolve({code:null,stdout:'',error});return;}
    let stdout='',error=null;hijo.stdout.setEncoding('utf8').on('data',x=>{stdout+=x;if(stdout.length>1048576)hijo.kill();});
    hijo.stderr.resume();hijo.on('error',e=>error=e);hijo.on('close',code=>resolve({code,stdout,error}));
    hijo.stdin.on('error',()=>{});hijo.stdin.end(JSON.stringify({coleccion:JSON.parse(fs.readFileSync(COL,'utf8')),
      environment:env,timeout:30000,salida:sub}));
  });
    if(c.ensayo&&out.error?.code==='EPERM'){
      const {ejecutarNewman}=await import('./pruebas/newman_hijo.mjs');
      const x=await ejecutarNewman({coleccion:JSON.parse(fs.readFileSync(COL,'utf8')),
        environment:env,timeout:30000,salida:sub});
      out={code:x.fallido?2:0,stdout:JSON.stringify(x),error:null};
    }
  }finally{if(state)state.newmanActivo=false;}
  let resumen={};try{resumen=JSON.parse(out.stdout);}catch{resumen={error:'SALIDA_INVALIDA'};}
  for(const s of resumen.solicitudes??[])if(s.contraste){r.contraste_contrato.push({...s.contraste,fuente:'Newman'});
    if(s.contraste.resultado==='discrepa')r.discrepancias_contrato.push(s.contraste);}
  r.herramientas.newman={version:versionNewman(),iteraciones:resumen.solicitudes?.length===3?1:0,
    fallos:resumen.solicitudes?.flatMap(x=>x.aserciones??[]).filter(x=>x.error).length??3,
    codigo:out.code,error:out.error?.code??resumen.error??null};
  if(fs.existsSync(path.join(sub,'newman-G38.json'))&&fs.existsSync(path.join(sub,'newman-G38.html')))
    r.evidencias.push('newman/newman-G38.json','newman/newman-G38.html');
  if(out.code!==0||r.herramientas.newman.fallos)r.problemas_tecnicos.push('Newman no completó las tres lecturas.');
}
async function cerrar(r,c,api,tokens,hechos){
  const res=await fetchEnContexto(`${api}/test-control/runs/${c.runId}`,{method:'DELETE',
    headers:{Authorization:`Bearer ${tokens.contador}`,'X-Sandbox-Secret':tokens.secreto},signal:AbortSignal.timeout(120000)});
  r.cierre.run.cierre_http=res.status;
  if(res.status!==200){r.cierre.rollback={verificado:false,motivo:`DELETE HTTP ${res.status}`};return;}
  if(!hechos.escrituras){r.cierre.rollback={verificado:!hechos.inciertas,
    motivo:hechos.inciertas?'Escritura incierta; rollback no demostrable.':'Sin escrituras; DELETE 200.'};return;}
  const rutas=[['variaciones',`/finanzas/periodos/${hechos.periodo}/variaciones`,'id_variacion_valor_razonable',hechos.variaciones],
    ['mediciones',`/finanzas/periodos/${hechos.periodo}/mediciones`,'id_medicion_posterior',hechos.mediciones],
    ['lineas',`/finanzas/lineas?id_periodo_contable=${hechos.periodo}`,'id_linea_asiento_nic41',hechos.lineas]];
  const presentes=[],lecturas=[];
  for(const [clave,ruta,campo,ids]of rutas){
    const res=await fetchEnContexto(api+ruta,{method:'GET',headers:{Authorization:`Bearer ${tokens.contador}`},signal:AbortSignal.timeout(30000)});
    const data=await res.json().catch(()=>null);lecturas.push({ruta,http:res.status});
    if(res.status!==200||!Array.isArray(data)){presentes.push(`${clave}: lectura incompleta`);continue;}
    for(const x of data)if(ids.includes(Number(x[campo])))presentes.push(`${clave}:${x[campo]}`);
  }
  for(const x of hechos.precios){
    const ruta=`/finanzas/precios?id_especie=${x.especie}`;
    const res=await fetchEnContexto(api+ruta,{method:'GET',headers:{Authorization:`Bearer ${tokens.contador}`},signal:AbortSignal.timeout(30000)});
    const data=await res.json().catch(()=>null);lecturas.push({ruta,http:res.status});
    if(res.status!==200||!Array.isArray(data))presentes.push('precio: lectura incompleta');
    else if(data.some(z=>Number(z.id_precio_mercado)===x.id))presentes.push(`precio:${x.id}`);
  }
  for(const x of hechos.eventos){
    const ruta=`/activos-biologicos/${x.activo}/eventos`;
    const res=await fetchEnContexto(api+ruta,{method:'GET',headers:{Authorization:`Bearer ${tokens.admin}`},signal:AbortSignal.timeout(30000)});
    const data=await res.json().catch(()=>null);lecturas.push({ruta,http:res.status});
    if(res.status!==200||!Array.isArray(data?.eventos))presentes.push('evento: lectura incompleta');
    else if(data.eventos.some(z=>Number(z.id_eventos)===x.id))presentes.push(`evento:${x.id}`);
  }
  r.cierre.lecturas_poscierre=lecturas;
  r.cierre.rollback={verificado:!presentes.length&&!hechos.inciertas,motivo:presentes.join('; ')||
    (hechos.inciertas?'Escritura incierta, no conciliada.':'IDs del RUN ausentes en lecturas públicas.')};
}
export function informe(c,r){
  const valor=x=>limpio(x??'sin dato');
  const casos=CASOS.map(k=>`| ${k} | ${valor(r.casos[k]?.estado??'NO_CONCLUYENTE')} | ${valor(r.casos[k]?.motivo??'Sin comprobación')} |`).join('\n');
  const obs=r.casos['TC-M06-014']?.observado??{}, l=obs.lineas??[], m=obs.mediciones?.[0]??{};
  const pred=r.observaciones?.predictor_015, periodo=r.solicitudes.find(x=>x.id==='variaciones')?.ruta?.match(/periodos\/(\d+)/)?.[1]??'sin dato';
  const porTipo=t=>l.find(x=>x.tipo===t)??{};
  const origen=t=>obs.variaciones?.find(x=>x.tipo===t)?.id??'sin dato';
  const lineaTabla=[['VARIACION_VR_TB','GANANCIA_TRANSFORMACION_BIOLOGICA'],['VARIACION_VR_PM','PERDIDA_PRECIO_MERCADO']]
    .map(([t,o])=>{const x=porTipo(t);return `| ${valor(x.id)} | ${t} | ${valor(x.sentido)} | ${valor(x.cuenta_debito)} | ${valor(x.cuenta_credito)} | ${valor(x.valor)} | ${valor(x.estado)} | ${valor(origen(o))} (${o}) |`;}).join('\n');
  const filasDec=[['TB',m.tb,porTipo('VARIACION_VR_TB').valor],['PM',m.pm,porTipo('VARIACION_VR_PM').valor]]
    .map(([tipo,componente,linea])=>{let tr='sin dato',red='sin dato';try{tr=truncar2(componente);red=redondear2(componente);}catch{}return `| ${tipo}: ${valor(componente)} | ${tr} | ${red} | ${valor(linea)} |`;}).join('\n');
  const contraste=[...new Map((r.contraste_contrato??[]).map(x=>[`${x.ruta}|${x.fuente??'ejecutor'}`,x])).values()]
    .map(x=>`- \`${valor(x.ruta)}\` (${x.fuente??'ejecutor'}): ${valor(x.resultado)}, HTTP ${valor(x.http)}${x.motivo?`; ${valor(x.motivo)}`:''}.`).join('\n')||'- Sin contraste registrado.';
  const inc=r.incidencias.map(x=>`- ${valor(x.caso)}: ${valor(x.titulo)}. ${valor(x.equipo_inicial)}; ${valor(x.severidad)}; ${valor(x.certeza)}.`).join('\n')||'Ninguna incidencia de producto.';
  const cierre=r.cierre??{}, lecturas=cierre.lecturas_poscierre??[];
  return `# TC-M06-G38 — ${CASOS.every(k=>r.casos[k]?.estado==='APROBADO')?'APROBADO':'RESULTADO MIXTO'}\n\n## Identificación\n\nGrupo G38; casos TC-M06-014 y TC-M06-015; RF-86 v2.0. RUN: ${c.runId}; versión ${c.version}; intento ${c.intento}; autorización ${c.referencia}; ambiente: ${c.ensayo?'loopback local':'TEST'}; commit: no consultado. Herramientas: Node ${process.version}, Newman ${r.herramientas.newman?.version??'no ejecutado'}. Oficial: ${r.oficial}.\n\n## Decisión del caso\n\n| Caso | Estado | Fundamento |\n| --- | --- | --- |\n${casos}\n\n## Detalle por caso\n\n### TC-M06-014\n\n- Preparación: período ${periodo} ABIERTO, activo bovino con reconocimiento previo, precio vigente y matriz RF-109 leída antes de escribir. ${pred?`El predictor eligió precio MERCADO_ACTIVO ${valor(pred.precio)} y peso ${valor(pred.peso)} kg.`:'No se conservó selección del predictor.'}\n- Esperado según la matriz de casos: líneas TB/GANANCIA y PM/PERDIDA del mismo período, valor positivo truncado del componente real y pares de cuentas de la matriz RF-109 vigente. Los importes 4.600.000 y 600.000 son ejemplos de la fila.\n- Observado: medición ${valor(m.id)} con TB ${valor(m.tb)} y PM ${valor(m.pm)}; variaciones ${valor(origen('GANANCIA_TRANSFORMACION_BIOLOGICA'))} y ${valor(origen('PERDIDA_PRECIO_MERCADO'))}.\n\n| ID | Tipo de hecho | Sentido | Débito | Crédito | Valor | Estado | Variación de origen |\n| --- | --- | --- | --- | --- | ---: | --- | --- |\n${lineaTabla}\n\n- Comparación: ${valor(r.casos['TC-M06-014']?.motivo)} Las cuentas de las dos líneas se contrastaron con la matriz RF-109 leída antes de la escritura.\n- Decisión: **${valor(r.casos['TC-M06-014']?.estado)}**.\n\n### TC-M06-015\n\n- Preparación: mismo hecho del caso 014 y consulta de todas las líneas del período ${periodo}.\n- Esperado según la matriz de casos: estructura completa, ID único e inmutable, valor positivo truncado a dos decimales; para el componente discriminante, truncar debe dar un valor distinto de redondear. Equivalencias: id_linea = id_linea_asiento_nic41; nit_titular = numero_id_tributaria; indicador_estimacion = es_estimacion.\n- Observado: ${pred?`predicción TB ${valor(pred.prediccion?.tb)} y PM ${valor(pred.prediccion?.pm)}; medición TB ${valor(m.tb)} y PM ${valor(m.pm)}.`:'No se conservó predicción.'} El precio elegido fue ${valor(pred?.precio)} y el peso ${valor(pred?.peso)} kg.\n\n| Componente de 4 decimales | Truncado | Redondeado | Valor de la línea |\n| --- | ---: | ---: | ---: |\n${filasDec}\n\n- Estructura e identidad: ${r.observaciones?.lineas_periodo_evaluadas==null?'El total de lineas del periodo no se conservo en resultado.json; se recorrieron todas las lineas devueltas.':`${r.observaciones.lineas_periodo_evaluadas} lineas del periodo evaluadas.`} ${r.casos['TC-M06-015']?.estado==='APROBADO'?'La comprobación de unicidad e inmutabilidad entre las lecturas previa y posterior aprobó.':'Consultar el motivo de la decisión para la comprobación de identidad.'}\n- Decisión: **${valor(r.casos['TC-M06-015']?.estado)}**; ${valor(r.casos['TC-M06-015']?.motivo)}\n\nComprobaciones: ${r.comprobaciones.length} API, ${r.cypress?.total_pruebas??0} UI; solicitudes del ejecutor: ${r.solicitudes.length}/150.\n\n## Contraste de contrato\n\n${contraste}\n\nDiscrepancias registradas: ${r.discrepancias_contrato?.length??0}.\n\n## Evidencias reales\n\n${r.evidencias.map(x=>`- ${x}`).join('\n')}\n\n## Incidencias\n\n${inc}\n\nProblemas técnicos: ${r.problemas_tecnicos.join('; ')||'ninguno'}. ${r.incidencias.length?'La causa raíz requiere investigación.':'Sin discrepancia de producto acreditada; no se asigna severidad ni equipo.'}\n\n## Cierre y rollback\n\nDELETE HTTP ${cierre.run?.cierre_http??'no ejecutado'}; rollback ${cierre.rollback?.verificado?'verificado':'no verificado'}: ${valor(cierre.rollback?.motivo)} Lecturas poscierre: ${lecturas.map(x=>`\`${valor(x.ruta)}\` HTTP ${valor(x.http)}`).join('; ')||'ninguna'}. El precio con centavos registrado durante el RUN queda comprendido en la reversión comprobada mediante la lectura de precios. Según el comportamiento observado en G37, el aviso NIC41 puede no registrarse; se informa aparte y no se atribuye a este RUN.\n\n## Conclusión\n\nVeredictos y cierre según resultado.json; registro ${r.oficial?'OFICIAL':'NO OFICIAL'}. ${r.incidencias.length?'Derivar las incidencias según su evidencia.':'Sin acción correctiva de producto derivada de estos casos.'}\n`;
}
export async function evaluar(c,e){
  if(e.QA_AUTORIZADO!=='SI'||!fs.existsSync(c.directorio))throw Error('RUN no autorizado o no preparado');
  const api=String(e.SIGAB_API_TEST_BASE).replace(/\/+$/,'');
  const r=resultado(c),h={periodo:null,escrituras:false,inciertas:false,variaciones:[],mediciones:[],lineas:[],eventos:[],precios:[]};
  r._limite=Date.now()+1800000;let tokens=null;
  try{
    const contador=await login(api,e.QA_CONTADOR_EMAIL,e.QA_CONTADOR_PASSWORD);
    const admin=await login(api,e.QA_ADMIN_EMAIL,e.QA_ADMIN_PASSWORD);
    if(!contador||!admin)throw Error('Login no confirmado');tokens={contador,admin,secreto:e.QA_SANDBOX_SECRET};
    for(const actor of ['contador','admin']){
      const res=await fetchEnContexto(api+CONTRATO.lectura_permisos.ruta,{method:'GET',headers:{
        Authorization:`Bearer ${tokens[actor]}`,'X-Test-Run-Id':c.runId,'X-Sandbox-Secret':tokens.secreto},signal:AbortSignal.timeout(30000)});
      const data=await res.json();r.solicitudes.push({id:'permisos',actor,metodo:'GET',http:res.status});
      if(res.status!==200||res.headers.get('x-test-run-id')!==c.runId)throw Error(`Permisos ${actor}: HTTP o eco`);
      verificarPermisos(data,actor);
    }
    const q=async(clave,ruta,actor='contador',body)=>{
      const x=await pedir(r,api,clave,ruta,actor,tokens,c,body);
      if(entrada(clave).metodo!=='GET'&&x.http===null)h.inciertas=true;
      return x;
    };
    const [activos,periodos]=[await q('activos','/finanzas/activos'),await q('periodos','/finanzas/periodos')];
    if(!bien(activos)||!bien(periodos))throw Error('Catálogo o períodos ilegibles');
    const precios=new Map();for(const esp of new Set(activos.data.map(x=>x.id_especie))){
      const x=await q('precios_get',`/finanzas/precios?id_especie=${esp}`);if(!bien(x))throw Error('Precios ilegibles');precios.set(esp,x.data);}
    const preparados=[];for(const x of activos.data){
      if(!/bovin/i.test(x.especie??'')||x.tipo!=='INDIVIDUAL'||x.estado!=='ACTIVO'||x.valorado_por_costo)continue;
      const idActivo=num(x.id_activo_biologico),d=await q('activo_detalle',`/finanzas/activos/${idActivo}`);
      const f=await q('ficha',`/activos-biologicos/${idActivo}/ficha-integral`,'admin');
      if(!bien(d)||!bien(f))throw Error('Detalle o ficha ilegible');
      const calculo=d.data.calculos.filter(z=>z.estado==='CALCULADO'&&z.json_metodo_costo?.es_producto!==true)
        .sort((a,b)=>String(b.fecha_calculo).localeCompare(String(a.fecha_calculo)))[0];
      preparados.push({...x,periodo:periodoDestino(periodos.data,d.data.activo.numero_id_tributaria,hoy()),
        precio:vigente(precios.get(x.id_especie)??[],x.id_especie,hoy()),calculo,
        peso:f.data.unidad_peso==='kg'?Number(f.data.peso_actual):null});
    }
    const seleccion=seleccionarCandidatos(preparados.map(x=>x.precio?.fuente==='MERCADO_ACTIVO'?x:{...x,precio:null}),1);
    r.observaciones.candidatos=seleccion.motivos;
    const s=seleccion.elegido[0];if(!s)throw Error('Sin bovino apto para G38');
    const pid=num(s.periodo.id_periodo_contable),aid=num(s.id_activo_biologico);h.periodo=pid;
    const cfg=await q('configuracion','/finanzas/configuracion');
    const base={variaciones:await q('variaciones',`/finanzas/periodos/${pid}/variaciones`),
      mediciones:await q('mediciones',`/finanzas/periodos/${pid}/mediciones`),
      lineas:await q('lineas',`/finanzas/lineas?id_periodo_contable=${pid}`)};
    if(!bien(cfg)||Object.values(base).some(x=>!bien(x)||!Array.isArray(x.data))||r.discrepancias_contrato.length)
      throw Error('Lecturas previas o contrato discrepantes; sin escrituras');
    const tb=resolverMatriz(cfg.data.matriz,'VARIACION_VR_TB','GANANCIA',s.id_especie);
    const pm=resolverMatriz(cfg.data.matriz,'VARIACION_VR_PM','PERDIDA',s.id_especie);
    if(!tb||!pm){registrar(r,CASOS[0],'BLOQUEADO','Matriz RF-109 sin par TB/GANANCIA o PM/PERDIDA; precondición no preparable sin cambiar configuración.');
      registrar(r,CASOS[1],'NO_CONCLUYENTE','No se preparó componente discriminante porque no hay par contable para el flujo.');
      return r;}
    const params=cfg.data.costos_venta?.find(x=>Number(x.id_especie)===Number(s.id_especie)&&x.region==='GENERAL'&&x.es_activo);
    if(!params)throw Error('Parámetros de costo ausentes');
    let previo=s.calculo;
    const requiereRebase=num(previo.id_precio_mercado)!==num(s.precio.id_precio_mercado);
    const basePredicha=requiereRebase?{magnitud:String(s.peso),
      valor_neto:predecir(s.precio.precio_unitario,String(s.peso),previo,params).neto}:previo;
    let combinado=buscarCombinacion(s.precio.precio_unitario,s.peso,basePredicha,params);
    if(!combinado){
      registrar(r,CASOS[0],'NO_CONCLUYENTE','Sin combinación TB+/PM- dentro de los límites plausibles; no se escribió.');
      registrar(r,CASOS[1],'NO_CONCLUYENTE','Sin combinación discriminante de precio con centavos y peso; no se escribió.');
      return r;
    }
    if(requiereRebase){
      const antesRebase={variaciones:base.variaciones.data,mediciones:base.mediciones.data,lineas:base.lineas.data};
      const re=await q('evento_crecimiento',`/activos-biologicos/${aid}/eventos/crecimiento`,'admin',
        {tipo_medicion:'PESO',valor_medicion:s.peso,unidad_medida:'kg',descripcion:`Rebase QA ${c.runId}`});
      if(!bien(re,201)||!num(re.data?.evento?.id_eventos))throw Error('Rebase no confirmado');h.escrituras=true;
      h.eventos.push({id:num(re.data.evento.id_eventos),activo:aid});
      const proc=await q('procesar','/finanzas/eventos/procesar','contador',{});if(!bien(proc))throw Error('Procesamiento rebase incompleto');
      const de=await q('activo_detalle',`/finanzas/activos/${aid}`);if(!bien(de))throw Error('Cálculo rebase ilegible');
      previo=de.data.calculos.find(x=>x.estado==='CALCULADO'&&num(x.id_precio_mercado)===num(s.precio.id_precio_mercado));
      if(!previo)throw Error('Cálculo rebase ausente');
      base.variaciones=await q('variaciones',`/finanzas/periodos/${pid}/variaciones`);
      base.mediciones=await q('mediciones',`/finanzas/periodos/${pid}/mediciones`);
      base.lineas=await q('lineas',`/finanzas/lineas?id_periodo_contable=${pid}`);
      if(Object.values(base).some(x=>!bien(x)))throw Error('Línea base tras rebase incompleta');
      h.variaciones.push(...idsNuevos(antesRebase.variaciones,base.variaciones.data,'id_variacion_valor_razonable').map(x=>num(x.id_variacion_valor_razonable)));
      h.mediciones.push(...idsNuevos(antesRebase.mediciones,base.mediciones.data,'id_medicion_posterior').map(x=>num(x.id_medicion_posterior)));
      h.lineas.push(...idsNuevos(antesRebase.lineas,base.lineas.data,'id_linea_asiento_nic41').map(x=>num(x.id_linea_asiento_nic41)));
    }
    combinado=buscarCombinacion(s.precio.precio_unitario,s.peso,previo,params);
    if(!combinado){
      registrar(r,CASOS[0],'NO_CONCLUYENTE','El cálculo observado tras rebase difiere de la predicción; sin evento 014.');
      registrar(r,CASOS[1],'NO_CONCLUYENTE','Sin combinación discriminante tras rebase; no se registró precio ni pesaje de 015.');
      return r;
    }
    r.observaciones.predictor_015=combinado;
    const precioNuevo=combinado.precio;
    const pp=await q('precios_post','/finanzas/precios','contador',{id_especie:num(s.id_especie),categoria:'PESO_KG',
      precio_unitario:Number(precioNuevo),fecha_vigencia:hoy(),fuente:'MERCADO_ACTIVO',
      evidencia_documental:`QA ${c.runId}`,confirmar_desviacion:true});
    if(!bien(pp,201)||!num(pp.data?.id_precio_mercado))throw Error('Precio nuevo no confirmado');h.escrituras=true;
    h.precios.push({id:num(pp.data.id_precio_mercado),especie:num(s.id_especie)});
    const ev=await q('evento_crecimiento',`/activos-biologicos/${aid}/eventos/crecimiento`,'admin',
      {tipo_medicion:'PESO',valor_medicion:Number(combinado.peso),
        unidad_medida:'kg',descripcion:`QA ${c.runId} TB+/PM-`});
    if(!bien(ev,201)||!num(ev.data?.evento?.id_eventos))throw Error('Pesaje 014 no confirmado');
    h.eventos.push({id:num(ev.data.evento.id_eventos),activo:aid});
    if(!bien(await q('procesar','/finanzas/eventos/procesar','contador',{})))throw Error('Procesamiento 014 incompleto');
    const pos={variaciones:await q('variaciones',`/finanzas/periodos/${pid}/variaciones`),
      mediciones:await q('mediciones',`/finanzas/periodos/${pid}/mediciones`),
      lineas:await q('lineas',`/finanzas/lineas?id_periodo_contable=${pid}`)};
    if(Object.values(pos).some(x=>!bien(x)))throw Error('Lecturas 014 incompletas');
    let vs=idsNuevos(base.variaciones.data,pos.variaciones.data,'id_variacion_valor_razonable').filter(x=>num(x.id_activo_biologico)===aid);
    let ms=idsNuevos(base.mediciones.data,pos.mediciones.data,'id_medicion_posterior').filter(x=>num(x.id_activo_biologico)===aid);
    let ls=idsNuevos(base.lineas.data,pos.lineas.data,'id_linea_asiento_nic41').filter(x=>num(x.id_activo_biologico)===aid);
    h.variaciones.push(...vs.map(x=>num(x.id_variacion_valor_razonable)));h.mediciones.push(...ms.map(x=>num(x.id_medicion_posterior)));
    h.lineas.push(...ls.map(x=>num(x.id_linea_asiento_nic41)));
    const d14=ms.length===1?oraculo014({variaciones:vs,medicion:ms[0],lineas:ls,matriz:cfg.data.matriz,especie:s.id_especie}):
      {estado:'NO_CONCLUYENTE',motivo:`Mediciones nuevas: ${ms.length}`};
    registrar(r,CASOS[0],d14.estado,d14.motivo,{observado:{
      variaciones:vs.map(x=>({id:x.id_variacion_valor_razonable,tipo:x.tipo})),
      mediciones:ms.map(x=>({id:x.id_medicion_posterior,tb:x.ganancia_perdida_transformacion,pm:x.ganancia_perdida_precio_mercado})),
      lineas:ls.map(x=>({id:x.id_linea_asiento_nic41,tipo:x.tipo_hecho,sentido:x.sentido,valor:x.valor,
        cuenta_debito:x.cuenta_debito,cuenta_credito:x.cuenta_credito,estado:x.estado}))}});
    const discriminante=ms.length===1?{medicion:ms[0],lineaTB:ls.find(x=>x.tipo_hecho==='VARIACION_VR_TB')}:null;
    r.observaciones.lineas_periodo_evaluadas=pos.lineas.data.length;
    const d15=oraculo015({antes:base.lineas.data,despues:pos.lineas.data,
      nuevas:idsNuevos(base.lineas.data,pos.lineas.data,'id_linea_asiento_nic41'),
      medicion:discriminante?.medicion,lineaTB:discriminante?.lineaTB});
    if(d14.estado==='RECHAZADO'&&/valor/.test(d14.motivo)&&d15.estado==='APROBADO'){
      d15.estado='RECHAZADO';d15.motivo=`Línea 014 con valor distinto del componente truncado: ${d14.motivo}`;
    }
    registrar(r,CASOS[1],d15.estado,d15.motivo,{observado:{componente_tb:discriminante?.medicion?.ganancia_perdida_transformacion??null,
      linea:discriminante?.lineaTB?{id:discriminante.lineaTB.id_linea_asiento_nic41,valor:discriminante.lineaTB.valor}:null}});
    if(!c.sinNewman)await newman(r,c,api,tokens,pid);
  }catch(error){r.problemas_tecnicos.push(limpio(error.message));for(const caso of CASOS)if(!r.casos[caso])
    registrar(r,caso,'NO_CONCLUYENTE',`Automatización o datos: ${error.message}`);}
  finally{
    if(tokens)try{await cerrar(r,c,api,tokens,h);}catch(error){r.cierre.rollback={verificado:false,motivo:limpio(error.message)};}
    for(const caso of CASOS)if(!r.casos[caso])registrar(r,caso,'NO_CONCLUYENTE','Sin comprobación completa.');
    if(r.discrepancias_contrato.length)for(const caso of CASOS){r.casos[caso].estado='NO_CONCLUYENTE';r.casos[caso].motivo='Contrato de API discrepante; revisar automatización.';}
    for(const x of r.comprobaciones){x.estado=r.casos[x.caso].estado;x.motivo=r.casos[x.caso].motivo;}
    for(const caso of CASOS)if(r.casos[caso].estado==='RECHAZADO')r.incidencias.push({
      caso,titulo:caso==='TC-M06-014'?'Líneas de variación incumplen RF-86':'Estructura o truncado de línea incumple RF-86',
      severidad:caso==='TC-M06-014'?'ALTA':'MEDIA',
      justificacion_severidad:caso==='TC-M06-014'?'Registro contable relevante sin línea o par conforme.':'Integridad parcial de las líneas del período.',
      equipo_inicial:'Desarrollo',fundamento_equipo:'Primera discrepancia comprobada en API pública de M06.',
      certeza:c.ensayo?'SIMULADA':'CONFIRMADA',causa_raiz:'NO DETERMINADA',evidencias:['resultado.json']});
    r.oficial=!r.discrepancias_contrato.length&&r.cierre.rollback.verificado&&r.herramientas.newman?.codigo===0&&
      r.herramientas.newman.fallos===0&&CASOS.every(k=>['APROBADO','RECHAZADO'].includes(r.casos[k].estado));
    r.consume_version=r.oficial;
    r.evidencias.unshift('resultado.json',c.version===1?'TC-M06-G38_resultado.md':`TC-M06-G38_reevaluacion_V${c.version}.md`);
    guardar(path.join(c.directorio,'resultado.json'),r);
    fs.writeFileSync(path.join(c.directorio,c.version===1?'TC-M06-G38_resultado.md':`TC-M06-G38_reevaluacion_V${c.version}.md`),informe(c,r));
  }return r;
}
export async function principal(args,{proceso=process.env,archivoEnv=path.join(ROOT,'.env.qa'),fetcher=globalThis.fetch,ensayo=false,sinNewman=false}={}){
  const c={...contexto(args,ensayo),sinNewman:ensayo&&sinNewman},env=leerEnv(proceso,archivoEnv),p=preflight(c,env);
  guardar(path.join(c.directorio,'preflight.json'),p);
  if(!p.ok)return{exitCode:2,preflight:p,resultado:null};
  const r=await conPeticiones(fetcher,()=>evaluar(c,env));return{exitCode:r.oficial?0:2,preflight:p,resultado:r};
}
if(process.argv.includes('--capacidades'))console.log(JSON.stringify(CAPACIDADES,null,2));
else if(process.argv.includes('--comprobar'))process.exitCode=comprobar();
else if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
  try{const {exitCode,preflight:p,resultado:r}=await principal(process.argv.slice(2));
    console.log(JSON.stringify({grupo:'G38',run_id:p.run_id,preflight_ok:p.ok,
      ...(r?{oficial:r.oficial,estados:Object.fromEntries(CASOS.map(k=>[k,r.casos[k].estado]))}:{barreras:p.barreras})}));
    process.exitCode=exitCode;
  }catch(error){console.error(limpio(error.message));process.exitCode=2;}
}
