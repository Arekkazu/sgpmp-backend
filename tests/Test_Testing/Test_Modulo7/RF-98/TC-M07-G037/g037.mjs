import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import {spawn} from 'node:child_process';
import {contrato,esquema,validarSolicitud,validarLecturas,validarError} from './lib/contrato.mjs';

const DIR=path.dirname(fileURLToPath(import.meta.url));
const ROOT=path.resolve(DIR,'../../../../..');
const API='https://www.api.inmero.co/api-sgpmp-test';
const M09='/configuracion/parametros-integracion-contable';
const CASOS=['TC-M07-06','TC-M07-07','TC-M07-08'];
const INVALIDOS=['4','4.0.1','v4.0','4.x','4.','.4',''];
const LIMITE={solicitudes_totales:60,duracion_segundos:600};
const IDS={
  'TC-M07-06':INVALIDOS.map((_,i)=>`formato_${i+1}`).concat('registro_valido'),
  'TC-M07-07':['gracia_inicial_baja','gracia_inicial_minima','gracia_inicial_defecto','m09_configurable','gracia_configurada_baja','gracia_configurada_minima','gracia_configurada_defecto','patch_invalido'],
  'TC-M07-08':['deprecar_baja','deprecar_minima','inactivacion_exacta']
};
export const CAPACIDADES={contrato:'sigab-qa-ejecutor/1',grupo:'G037',casos:CASOS,operaciones:['reevaluar','reintentar'],versiones:{min:3,max:3},comprobaciones_obligatorias:Object.fromEntries(CASOS.map(k=>[k,{API:IDS[k]}])),limite:LIMITE};
const sha=p=>createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const seguro=x=>String(x??'').replace(/eyJ[\w-]+\.[\w-]+\.[\w-]+/g,'[JWT]').replace(/[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}/g,'[CORREO]');
export const sanitize=x=>Array.isArray(x)?x.map(sanitize):x&&typeof x==='object'?Object.fromEntries(Object.entries(x).map(([k,v])=>[k,/^(nombre_usuario|nombre_cliente|nombre|nombres|apellidos|nombre_completo)$/i.test(k)?'[NOMBRE]':/correo_electronico|correo|email/i.test(k)?'[CORREO]':/token|secret|password|cookie|authorization|sha256_documento|contrasena|contraseña|clave|access_key|refresh/i.test(k)?'[RESERVADO]':sanitize(v)])):typeof x==='string'?seguro(x):x;
const guardar=(p,x)=>fs.writeFileSync(p,JSON.stringify(sanitize(x),null,2));
const estado=xs=>new Map(xs.map(x=>[x.id_version_contrato_aaef,x.estado]));
const iguales=(a,b)=>a.size===b.size&&[...a].every(([k,v])=>b.get(k)===v);
const version=(xs,v)=>xs.find(x=>x.contrato_version===v);
const combinar=xs=>xs.includes('RECHAZADO')?'RECHAZADO':xs.every(x=>x==='APROBADO')?'APROBADO':'NO_CONCLUYENTE';
const loopback=x=>{try{const u=new URL(x);return u.protocol==='http:'&&['127.0.0.1','localhost'].includes(u.hostname)&&!!u.port;}catch{return false;}};
export const mismoInstante=(a,b)=>Number.isFinite(Date.parse(a))&&Date.parse(a)===Date.parse(b);
export const dirRun=c=>c.ensayo?path.resolve(c.dir):path.join(DIR,'EvaluacionV3','Resultados',c.runId);
const firmaGracia=x=>JSON.stringify(x?.map(p=>[p.nombre,p.valor,p.valor_configurado,p.fuente]).sort((a,b)=>a[0].localeCompare(b[0])));
export function leerGracia(raw){
  if(!Array.isArray(raw))return null;
  const a=raw.find(x=>x.nombre==='aaef_gracia_minima_dias');
  const b=raw.find(x=>x.nombre==='aaef_gracia_defecto_dias');
  const entero=v=>typeof v==='string'&&/^\d+$/.test(v)?Number(v):v;
  const min=entero(a?.valor),def=entero(b?.valor);
  return Number.isSafeInteger(min)&&Number.isSafeInteger(def)&&min>=1&&def>=min?
    {min,def,fuentes:{min:a.fuente,def:b.fuente}}:null;
}
const fechaFutura=()=>{const d=new Date();d.setUTCDate(d.getUTCDate()+400);return d.toISOString().slice(0,10);};
const cuerpo=(v,id,gracia)=>({contrato_version:v,tipo_cambio:'MAJOR',fecha_vigencia:fechaFutura(),id_mapeo_anexo_aaef:id,mapeadores:['COMPRAS'],...(gracia===undefined?{}:{periodo_gracia_dias:gracia})});
export function versionesLibres(xs,n=8){
  const ocupadas=new Set(xs.map(x=>x.contrato_version)),salida=[];
  for(let major=6;salida.length<n&&major<=999;major++)for(let minor=0;salida.length<n&&minor<=999;minor++){
    const v=`${major}.${minor}`;if(!ocupadas.has(v))salida.push(v);
  }
  return salida;
}
const rechazo=(z,antes,despues)=>z.http>=200&&z.http<300||!iguales(estado(antes),estado(despues))?'RECHAZADO':z.http>=400&&z.http<500&&z.http!==401&&z.http!==403?'APROBADO':'NO_CONCLUYENTE';
const alta=(z,v,lista,gracia,comprobarGracia=true)=>z.http===201&&z.data?.contrato_version===v&&z.data?.estado==='PENDIENTE'&&(!comprobarGracia||z.data?.periodo_gracia_dias===gracia)&&version(lista,v)?.id_version_contrato_aaef===z.data.id_version_contrato_aaef&&version(lista,v)?.estado==='PENDIENTE'?'APROBADO':z.http===201||z.http>=400&&z.http<500&&z.http!==401&&z.http!==403?'RECHAZADO':'NO_CONCLUYENTE';
export function verificarRollback(antes,despues,graciaAntes=null,graciaDespues=null){
  return iguales(estado(antes),estado(despues))&&(!graciaAntes||firmaGracia(graciaAntes)===firmaGracia(graciaDespues));
}
export function comprobar(){
  const archivos=['g037.mjs','lib/contrato.mjs','pruebas/contrato_g037.json','G037.postman_collection.json','pruebas/newman_hijo.mjs','pruebas/verificar.mjs','pruebas/simulador_g037.mjs','pruebas/escenarios_g037.mjs','pruebas/escenarios_g037.json','pruebas/g037_local.test.mjs','pruebas/g037_dto_test.py','pruebas/contrato_cruzado.test.mjs','README.md'];
  const faltan=archivos.filter(x=>!fs.existsSync(path.join(DIR,x)));
  const col=JSON.parse(fs.readFileSync(path.join(DIR,'G037.postman_collection.json'),'utf8'));
  const ok=!faltan.length&&col.item.length===2&&contrato.version==='ORD-G037-009'&&contrato.version_ejecucion===3&&contrato.rutas.every(x=>x.cita?.startsWith('src/'))&&!fs.existsSync(path.join(DIR,'Resultados','TC-M07-G037_resultado.md'))&&(!fs.existsSync(path.join(DIR,'EvaluacionV3','Resultados'))||fs.readdirSync(path.join(DIR,'EvaluacionV3','Resultados')).every(x=>/^RUN-G037-V3-\d{8}-\d{6}$/.test(x)));
  console.log(JSON.stringify({grupo:'G037',ok,faltan,coleccion:col.item.length,sha256:Object.fromEntries(archivos.filter(x=>fs.existsSync(path.join(DIR,x))).map(x=>[x,sha(path.join(DIR,x))]))}));
  return ok?0:2;
}
export function leerEnv(proceso=process.env,archivo=path.join(ROOT,'.env.qa')){
  const e={};if(proceso.QA_AUTORIZADO==='SI'&&fs.existsSync(archivo))for(const line of fs.readFileSync(archivo,'utf8').split(/\r?\n/)){
    const m=line.match(/^\s*([A-Z][A-Z0-9_]*)\s*=(.*)$/);if(m)e[m[1]]=m[2].trim().replace(/^(['"])(.*)\1$/,'$2');
  }Object.assign(e,proceso);e.QA_AUTORIZADO=proceso.QA_AUTORIZADO;return e;
}
export function contexto(args,prueba=false){
  const arg=k=>args.includes(k)?args[args.indexOf(k)+1]:null;
  const operacion=arg('--operacion'),versionN=Number(arg('--version')),intento=Number(arg('--intento')),runId=arg('--run-id'),referencia=arg('--autorizacion'),archivo=arg('--contexto');
  if(!CAPACIDADES.operaciones.includes(operacion)||versionN!==3||!Number.isInteger(intento)||intento<1||!referencia||!/^RUN-G037-V3-\d{8}-\d{6}$/.test(runId??''))throw Error('CONTEXTO_INCOMPLETO');
  const c={runId,version:3,intento,operacion,referencia,ensayo:prueba,estricto:prueba};
  c.dir=prueba?path.dirname(path.resolve(archivo??'.')):dirRun(c);
  if(prueba&&(path.basename(c.dir)!==runId||!c.dir.startsWith(path.resolve(os.tmpdir())+path.sep)))throw Error('PRUEBA_FUERA_TEMPORAL');
  if(!archivo||path.resolve(archivo)!==path.join(c.dir,'contexto_operacion.json'))throw Error('CONTEXTO_FUERA_RUN');
  const d=JSON.parse(fs.readFileSync(archivo,'utf8'));
  if(d.grupo!=='G037'||d.run_id!==runId||d.version!==3||d.intento!==intento||d.operacion!==operacion.toUpperCase()||d.referencia!==referencia||JSON.stringify(d.casos)!==JSON.stringify(CASOS))throw Error('CONTEXTO_INCOHERENTE');
  if(operacion==='reevaluar'&&(!d.alcance_reevaluacion||d.version_anterior!==2))throw Error('REEVALUACION_SIN_DECISION');
  return c;
}
export function preflight(c,e){
  const faltan=[];for(const k of ['QA_ADMIN_EMAIL','QA_ADMIN_PASSWORD','QA_SANDBOX_SECRET','SIGAB_API_TEST_BASE'])if(!String(e[k]??'').trim())faltan.push(k);
  if(e.QA_AUTORIZADO!=='SI')faltan.push('QA_AUTORIZADO');
  const api=String(e.SIGAB_API_TEST_BASE??'').replace(/\/+$/,'');
  if(c.ensayo?!loopback(api):api!==API)faltan.push('API_NO_CANONICA');
  if(!/^RUN-G037-V3-\d{8}-\d{6}$/.test(c.runId??''))faltan.push('RUN_ID');
  if(!c.referencia)faltan.push('AUTORIZACION');
  return{ok:!faltan.length,faltan,grupo:'G037',run_id:c.runId,version:3,referencia:c.referencia,presupuesto:LIMITE};
}
function requisitos(anexos,contratos,permisos){
  const permiso=(r,a)=>permisos.some(x=>x.nombre_recurso===r&&x.id_accion===a);
  const aprobado=anexos.filter(x=>x.estado==='APROBADO').sort((a,b)=>b.id_mapeo_anexo_aaef-a.id_mapeo_anexo_aaef)[0];
  const activo=contratos.filter(x=>x.estado==='ACTIVO').sort((a,b)=>b.id_version_contrato_aaef-a.id_version_contrato_aaef)[0];
  const filas=[...([['contratos_aaef',1,false],['contratos_aaef',2,true],['contratos_aaef',3,false],['configuraciones_globales',2,false],['configuraciones_globales',3,false]].map(([r,a,b])=>({requisito:`PERMISO_${r}_${a}`,esperado:'presente',observado:permiso(r,a)?'presente':'ausente',cumple:permiso(r,a),bloqueante:b}))),{requisito:'ANEXO_APROBADO',esperado:'presente',observado:aprobado?.id_mapeo_anexo_aaef??null,cumple:!!aprobado,bloqueante:false},{requisito:'VERSION_ACTIVO',esperado:'presente',observado:activo?.id_version_contrato_aaef??null,cumple:!!activo,bloqueante:false}];
  return{filas,aprobado,activo,permisoCrear:permiso('contratos_aaef',1),permisoDeprecar:permiso('contratos_aaef',3),permisoM09R:permiso('configuraciones_globales',2),permisoM09U:permiso('configuraciones_globales',3),bloqueado:filas.some(x=>x.bloqueante&&!x.cumple)};
}
async function lanzarNewman(input){
  return new Promise(resolve=>{let h;try{h=spawn(process.execPath,[path.join(DIR,'pruebas/newman_hijo.mjs')],{cwd:DIR,stdio:['pipe','pipe','pipe'],windowsHide:true});}catch(error){resolve({codigo:2,error:error.code??error.message});return;}
    let out='',error=null;const timer=setTimeout(()=>{error='ETIMEDOUT';h.kill();},240000);h.stdout.on('data',x=>out+=x);h.stderr.on('data',()=>{});h.on('error',e=>error=e.code??e.message);h.on('close',code=>{clearTimeout(timer);let z;try{z=JSON.parse(out);}catch{z={codigo:code??2,error:error??'NEWMAN_SIN_JSON'};}resolve(z);});h.stdin.on('error',()=>{});h.stdin.end(JSON.stringify(input));});
}
export function esOficial(r,deadline){
  return Object.values(r.veredictos??{}).length===3&&Object.values(r.veredictos).every(x=>['APROBADO','RECHAZADO'].includes(x))&&r.comprobaciones?.every(x=>['APROBADO','RECHAZADO'].includes(x.estado))&&r.newman?.codigo===0&&r.newman?.fallos===0&&r.newman?.reportes===true&&r.cierre.run.cierre_http===200&&r.cierre.rollback.verificado&&r.solicitudes_total<=60&&Date.now()<=deadline;
}
function armarResultado(r,c){
  r.autorizacion_referencia=c.referencia;r.consume_version=r.solicitudes.some(x=>x.metodo==='POST'&&x.ruta==='/integracion/contratos');
  r.cierre.run={cierre_http:r.cierre.http??null};r.cypress={codigo:null,total_pruebas:0,no_aplica:true};
  r.veredictos=Object.fromEntries(CASOS.map((id,i)=>[String(i+6).padStart(2,'0'),combinar(r.pruebas[id])]));
  r.casos=Object.fromEntries(CASOS.map((id,i)=>[id,{estado:r.veredictos[String(i+6).padStart(2,'0')],comprobaciones:IDS[id]}]));
  r.comprobaciones=CASOS.flatMap(id=>IDS[id].map((clave,i)=>({caso:id,fuente:'API',id:clave,tipo:'ASSERT',estado:r.pruebas[id][i],evidencia:'resultado.json'})));
  const reglas={formato_1:['FORMATO_ACEPTADO','ALTA'],formato_2:['FORMATO_ACEPTADO','ALTA'],formato_3:['FORMATO_ACEPTADO','ALTA'],formato_4:['FORMATO_ACEPTADO','ALTA'],formato_5:['FORMATO_ACEPTADO','ALTA'],formato_6:['FORMATO_ACEPTADO','ALTA'],formato_7:['FORMATO_ACEPTADO','ALTA'],registro_valido:['REGISTRO_NO_CREADO','ALTA'],gracia_inicial_baja:['GRACIA_BAJA_ACEPTADA','ALTA'],gracia_inicial_minima:['GRACIA_MINIMA_RECHAZADA','ALTA'],gracia_inicial_defecto:['GRACIA_DEFECTO_DISTINTA','MEDIA'],m09_configurable:['M09_NO_CONFIGURABLE','MEDIA'],gracia_configurada_baja:['GRACIA_CONFIGURADA_BAJA_ACEPTADA','MEDIA'],gracia_configurada_minima:['GRACIA_CONFIGURADA_MINIMA_RECHAZADA','MEDIA'],gracia_configurada_defecto:['GRACIA_CONFIGURADA_DEFECTO_DISTINTA','MEDIA'],patch_invalido:['PATCH_INVALIDO_SIN_RECHAZO','MEDIA'],deprecar_baja:['DEPRECAR_BAJA_ACEPTADO','ALTA'],deprecar_minima:['DEPRECAR_MINIMA_RECHAZADO','ALTA'],inactivacion_exacta:['INACTIVACION_INCORRECTA','MEDIA']};
  const vistos=new Set();for(const x of r.comprobaciones.filter(x=>x.estado==='RECHAZADO')){const [regla,severidad]=x.id==='patch_invalido'?[r.regla_patch_invalido??'PATCH_INVALIDO_SIN_RECHAZO','MEDIA']:reglas[x.id];if(vistos.has(regla))continue;vistos.add(regla);r.incidencias.push({caso:x.caso,regla,severidad,certeza:c.ensayo?'PROBABLE':'CONFIRMADA',equipo_inicial:'Desarrollo',fundamento:'Primera discrepancia en API pública; causa raíz no determinada'});}
  r.solicitudes_total=r.solicitudes.length+(r.newman?.solicitudes??0);r.oficial=esOficial(r,Date.now()+1)&&r.plazo_ok===true;delete r.plazo_ok;
}
export function informe(c,r){
  const resumen=CASOS.map(id=>`- ${id}: **${r.casos[id].estado}**; ${r.casos[id].comprobaciones.map(k=>`${k}=${r.comprobaciones.find(x=>x.caso===id&&x.id===k)?.estado}`).join(', ')}.`).join('\n');
  const esperado={'TC-M07-06':'Siete formatos inválidos de V1: 4xx sin crear; una versión libre MAJOR.MINOR: 201 PENDIENTE.','TC-M07-07':'Gracia efectiva m/d leída de M09: m-1 rechazado, m aceptado y omisión usa d. PATCH de mínimo y defecto: GET CONFIGURADO; nuevo mínimo-1 rechazado, mínimo aceptado, omisión usa nuevo defecto; PATCH inválido 400 sin cambios.','TC-M07-08':'Versión ACTIVO actual: mínimo-1 rechazado y sigue ACTIVO; mínimo aceptado, DEPRECADO e inactivación exactamente +mínimo días.'};
  const casos=CASOS.map(id=>`### ${id}\n\n**Esperado:** ${esperado[id]}\n\n**Observado:** ${r.solicitudes.filter(x=>x.caso===id).map(x=>`${x.id}: ${x.metodo} ${x.ruta}, actor ${x.actor}, momento ${x.momento}, HTTP ${x.http}, respuesta ${JSON.stringify(x.cuerpo_respuesta??x.cuerpo_error??x.cuerpo_lectura??null)}.`).join('\n\n')||'Sin peticiones por preflight o error técnico.'}\n\n**Decisión:** ${r.casos[id].estado}.`).join('\n\n');
  return `# TC-M07-G037 — reevaluación V3, RF-98 v1.2\n\nGrupo G037; casos ${CASOS.join(', ')}; versión ${c.version}; RUN ${c.runId}; ambiente ${c.ensayo?'SIMULACIÓN LOCAL':'TEST'}; autorización ${c.referencia}; commit desplegado no consultado (corrección informada 0553cefd). Herramientas: Node ${process.version}, Newman código ${r.newman?.codigo??'no ejecutado'}; Cypress NO_APLICA. Oficial: ${r.oficial}. Solicitudes ${r.solicitudes_total}/60.\n\n## Resumen de veredictos\n\n${resumen}\n\n## Preflight y datos en vivo\n\n${r.preflight_datos.map(x=>`- ${x.requisito}: esperado ${x.esperado}, observado ${x.observado??'ausente'}, cumple ${x.cumple}, bloqueante ${x.bloqueante}.`).join('\n')}\n\nVersiones elegidas: ${JSON.stringify(r.datos?.versiones??[])}. Anexo: ${r.datos?.anexo??'no disponible'}; ACTIVO: ${r.datos?.activo??'no disponible'}. Gracia antes: ${JSON.stringify(r.gracia?.antes??null)}; después del PATCH: ${JSON.stringify(r.gracia?.despues??null)}. Orden: el PATCH y los registros preceden a la deprecación para comprobar también el valor configurado; si el PATCH no es posible, 08 usa el valor inicial.\n\n## Comprobaciones API por caso\n\n${casos}\n\n## Eventos M07\n\nConsulta HTTP ${r.eventos?.consulta_http??'no realizada'}; registros ${JSON.stringify(r.eventos?.registrados??[])}; deprecaciones ${JSON.stringify(r.eventos?.deprecados??[])}. Evidencia: resultado.json.\n\n## Evidencias reales\n\n${r.evidencias.map(x=>`- ${x}`).join('\n')}\n\n## Incidencias de producto y análisis de causas\n\n${r.incidencias.map(x=>`- ${x.regla}: ${x.severidad}, certeza ${x.certeza}; atención inicial ${x.equipo_inicial}, porque ${x.fundamento}. Causa raíz por investigar.`).join('\n')||'Sin incidencia de producto demostrada.'}\n\n## Observaciones\n\n${r.observaciones.join('; ')||'Ninguna.'}\n\n## Problemas técnicos de automatización\n\n${r.problemas_tecnicos.join('; ')||'Ninguno registrado.'}\n\n## Conclusión y acciones\n\n${r.oficial?'Reevaluación concluida; remitir las discrepancias observadas al equipo inicial.':'Reevaluación no oficial; resolver comprobaciones no concluyentes o problemas técnicos antes del cierre QA.'}\n\n## Cierre y rollback\n\nDELETE del RUN: HTTP ${r.cierre.run.cierre_http??'no consta'}. Rollback de ids, estados y parámetros M09: ${r.cierre.rollback.verificado?'verificado':'no verificado'}; ${r.cierre.rollback.motivo}. Login previo al RUN: efecto persistente fuera del sandbox (último acceso, auditoría de sesión y notificación).\n`;
}
export async function ejecutar(c,e,fetcher=fetch,dobles={}){
  const pf=preflight(c,e);if(!pf.ok)throw Error(`PREFLIGHT_${pf.faltan.join('_')}`);
  if(!c.ensayo&&Object.keys(dobles).length)throw Error('DOBLES_SOLO_ENSAYO');
  const dir=dirRun(c);if(c.ensayo&&(path.basename(dir)!==c.runId||!dir.startsWith(path.resolve(os.tmpdir())+path.sep)))throw Error('ENSAYO_FUERA_TEMPORAL');
  if(!fs.existsSync(dir))throw Error('RUN_NO_PRECREADO');
  const informeArchivo=path.join(dir,'TC-M07-G037_reevaluacion_V3.md');
  if(fs.existsSync(path.join(dir,'resultado.json'))||fs.existsSync(informeArchivo))throw Error('RUN_EXISTENTE');
  guardar(path.join(dir,'preflight.json'),pf);const deadline=Date.now()+600000;
  const r={grupo:'G037',run_id:c.runId,version:3,solicitudes:[],pruebas:Object.fromEntries(CASOS.map(id=>[id,IDS[id].map(()=> 'NO_CONCLUYENTE')])),incidencias:[],evidencias:['preflight.json','resultado.json'],problemas_tecnicos:[],preflight_datos:[],datos:{},gracia:{},eventos:{consulta_http:null,registrados:[],deprecados:[],evidencia:'resultado.json'},cierre:{rollback:{verificado:false,motivo:'No ejecutado'}},newman:null,observaciones:[],oficial:false};
  let token=null,serial=false,cerrado=false,runAbierto=false,loginIntentado=false,base=null,seleccion=null,m09Antes=null;const api=String(e.SIGAB_API_TEST_BASE).replace(/\/+$/,'');
  async function pedir(metodo,ruta,body,caso){
    if(serial)throw Error('PETICION_CONCURRENTE');
    if(r.solicitudes.length+(r.newman?.solicitudes??0)>=60||Date.now()>deadline)throw Error('PRESUPUESTO_AGOTADO');
    if(!esquema(metodo,ruta))throw Error(`RUTA_FUERA_CONTRATO_${metodo}_${ruta}`);
    validarSolicitud(metodo,ruta,body);
    const login=metodo==='POST'&&ruta==='/sesiones/';
    if(login){if(loginIntentado||runAbierto)throw Error('LOGIN_REPETIDO_O_DENTRO_RUN');loginIntentado=true;}else if(!token)throw Error('LOGIN_REQUERIDO');
    serial=true;const row={id:`G037-${String(r.solicitudes.length+1).padStart(3,'0')}`,metodo,ruta,caso:caso??null,http:null,actor:'Administrador QA',momento:login?'ANTES_DEL_RUN':cerrado?'DESPUES_DEL_RUN':'DENTRO_DEL_RUN',...(login?{efecto_persistente:'último acceso, auditoría de sesión y notificación de login con escritura independiente'}:{})};
    if(body!==undefined)row.cuerpo_solicitud=sanitize(body);r.solicitudes.push(row);
    try{
      const headers={...(login?{}:{Authorization:`Bearer ${token}`}),...(login||cerrado?{}:{'X-Test-Run-Id':c.runId,'X-Sandbox-Secret':e.QA_SANDBOX_SECRET}),...(body===undefined?{}:{'Content-Type':'application/json'})};
      if(!login&&!cerrado)runAbierto=true;
      const z=await fetcher(api+ruta,{method:metodo,headers,redirect:'manual',...(body===undefined?{}:{body:JSON.stringify(body)}),signal:AbortSignal.timeout(120000)});
      row.http=z.status;const raw=await z.json().catch(()=>null);row.eco=z.headers.get('x-test-run-id')===c.runId;
      if(!login&&!cerrado&&(!row.eco||z.status>=500))throw Error(`SANDBOX_O_INFRA_${row.id}_${z.status}`);
      if(z.status>=400){row.cuerpo_error=sanitize(raw);row.error_estandar=validarError(raw);}
      else if(metodo==='POST'||metodo==='PATCH')row.cuerpo_respuesta=sanitize(raw);
      else if(ruta===M09)row.cuerpo_lectura=sanitize(raw);
      const data=z.status>=200&&z.status<300?validarLecturas(raw,metodo,ruta,{estricto:!!c.estricto}):raw;
      return{http:z.status,data,raw,row};
    }finally{serial=false;}
  }
  const get=async(ruta,caso)=>{const z=await pedir('GET',ruta,undefined,caso);if(z.http!==200)throw Error(`LECTURA_${ruta}_${z.http}`);return z.data;};
  const listar=async(caso)=>{const v=await get('/integracion/contratos',caso);if(!Array.isArray(v))throw Error('LISTA_INVALIDA');return v;};
  const check=async(z,antes,caso)=>rechazo(z,antes,await listar(caso));
  const altaCaso=async(id,indice,v,anexo,g,esperado=g)=>{const z=await pedir('POST','/integracion/contratos',cuerpo(v,anexo,g),id);const lista=await listar(id);r.pruebas[id][indice]=alta(z,v,lista,esperado,esperado!==undefined);return lista;};
  try{
    const sesion=await pedir('POST','/sesiones/',{correo_electronico:e.QA_ADMIN_EMAIL,contrasena:e.QA_ADMIN_PASSWORD});
    if(sesion.http!==200)throw Error('LOGIN_FALLIDO');token=sesion.data.token;
    const permisos=(await get('/sesiones/me/permisos')).permisos;
    if(!permisos.some(x=>x.nombre_recurso==='contratos_aaef'&&x.id_accion===2)){
      r.preflight_datos=[{requisito:'PERMISO_contratos_aaef_2',esperado:'presente',observado:'ausente',cumple:false,bloqueante:true}];
      r.observaciones.push('Sin permiso R de contratos_aaef: los tres casos NO_CONCLUYENTE; no se puede obtener línea base');
      return r;
    }
    const anexos=await get('/integracion/anexos');
    base=await listar();seleccion=requisitos(anexos,base,permisos);r.preflight_datos=seleccion.filas;
    const libres=versionesLibres(base);r.datos={versiones:libres,anexo:seleccion.aprobado?.id_mapeo_anexo_aaef??null,activo:seleccion.activo?.id_version_contrato_aaef??null};
    let inicial=null,actual=null;
    if(seleccion.permisoM09R){
      const z=await pedir('GET',M09,undefined,'TC-M07-07');
      if(z.http===200){m09Antes=z.raw;inicial=leerGracia(z.data);r.gracia.antes=sanitize(z.raw);if(!inicial)r.pruebas['TC-M07-07'][3]='RECHAZADO';}
      else{r.observaciones.push(`GET M09 HTTP ${z.http}; gracia efectiva no legible`);if(z.http===404)r.pruebas['TC-M07-07'][3]='RECHAZADO';}
    }else r.observaciones.push('Falta permiso R de M09: 07 y 08 no pueden comprobar límites efectivos');
    actual=inicial;
    if(!seleccion.bloqueado&&seleccion.permisoCrear&&seleccion.aprobado&&libres.length===8){
      const anexo=seleccion.aprobado.id_mapeo_anexo_aaef;
      const antes=await listar('TC-M07-06');
      for(let i=0;i<INVALIDOS.length;i++){
        const z=await pedir('POST','/integracion/contratos',cuerpo(INVALIDOS[i],anexo),'TC-M07-06');
        r.pruebas['TC-M07-06'][i]=z.http>=200&&z.http<300?'RECHAZADO':z.http>=400&&z.http<500&&z.http!==401&&z.http!==403?'APROBADO':'NO_CONCLUYENTE';
      }
      const despues=await listar('TC-M07-06');if(!iguales(estado(antes),estado(despues)))for(let i=0;i<7;i++)r.pruebas['TC-M07-06'][i]='RECHAZADO';
      await altaCaso('TC-M07-06',7,libres[0],anexo);
      if(inicial){
        const caso='TC-M07-07';
        let previa=await listar(caso),z=await pedir('POST','/integracion/contratos',cuerpo(libres[1],anexo,inicial.min-1),caso);
        r.pruebas[caso][0]=await check(z,previa,caso);
        await altaCaso(caso,1,r.pruebas[caso][0]==='APROBADO'?libres[1]:libres[2],anexo,inicial.min);
        await altaCaso(caso,2,libres[3],anexo,undefined,inicial.def);
        if(seleccion.permisoM09U){
          const nuevoMin=inicial.min===45?46:45,nuevoDef=inicial.def===120?121:120;
          const valores={aaef_gracia_minima_dias:nuevoMin,aaef_gracia_defecto_dias:nuevoDef};
          const p=await pedir('PATCH',M09,{parametros:valores},caso);
          if(p.http===200){
            const lectura=await pedir('GET',M09,undefined,caso);r.gracia.despues=sanitize(lectura.raw);
            actual=lectura.http===200?leerGracia(lectura.data):null;
            const configurado=actual?.min===nuevoMin&&actual?.def===nuevoDef&&actual.fuentes.min==='CONFIGURADO'&&actual.fuentes.def==='CONFIGURADO';
            if(configurado){
              previa=await listar(caso);z=await pedir('POST','/integracion/contratos',cuerpo(libres[4],anexo,nuevoMin-1),caso);
              r.pruebas[caso][4]=await check(z,previa,caso);
              await altaCaso(caso,5,r.pruebas[caso][4]==='APROBADO'?libres[4]:libres[5],anexo,nuevoMin);
              await altaCaso(caso,6,libres[6],anexo,undefined,nuevoDef);
              const invalido=await pedir('PATCH',M09,{parametros:{aaef_gracia_defecto_dias:nuevoMin-1}},caso);
              const sinCambio=await pedir('GET',M09,undefined,caso);
              const graciaCambio=sinCambio.http===200&&firmaGracia(lectura.raw)!==firmaGracia(sinCambio.raw);
              r.pruebas[caso][7]=invalido.http>=200&&invalido.http<300||graciaCambio?'RECHAZADO':invalido.http===400&&sinCambio.http===200?'APROBADO':'NO_CONCLUYENTE';
              if(r.pruebas[caso][7]==='RECHAZADO')r.regla_patch_invalido=graciaCambio?'GRACIA_MODIFICADA_POR_PATCH_INVALIDO':'PATCH_INVALIDO_SIN_RECHAZO';
              if(invalido.http===400&&(invalido.raw?.error_code!=='PARAMETRO_INTEGRACION_CONTABLE_INVALIDO'||invalido.raw?.field==null))r.observaciones.push(`PATCH inválido: HTTP 400, error_code=${invalido.raw?.error_code??null}, field=${invalido.raw?.field??null}; gracia ${graciaCambio?'modificada':'sin cambio observado'}`);
              const registros=r.pruebas[caso].slice(4,7).every(x=>x==='APROBADO');
              r.pruebas[caso][3]=registros?'APROBADO':'RECHAZADO';
            }else{r.pruebas[caso][3]='RECHAZADO';r.observaciones.push('GET M09 no devolvió los dos valores CONFIGURADO tras PATCH');}
          }else if(p.http===403){r.observaciones.push('PATCH M09 HTTP 403: D3 NO_CONCLUYENTE por permiso U');}
          else if(p.http===404){r.pruebas[caso][3]='RECHAZADO';}
          else{r.pruebas[caso][3]='RECHAZADO';r.observaciones.push(`PATCH M09 HTTP ${p.http}`);}
        }else r.observaciones.push('Sin permiso U M09: D3 NO_CONCLUYENTE');
      }
    }else if(!seleccion.aprobado)r.observaciones.push('Sin anexo APROBADO: 06 y 07 NO_CONCLUYENTE');
    else if(!seleccion.permisoCrear)r.observaciones.push('Sin permiso C de contratos_aaef: 06 y 07 NO_CONCLUYENTE');
    if(!seleccion.bloqueado&&seleccion.permisoDeprecar&&seleccion.activo&&actual){
      const caso='TC-M07-08',id=seleccion.activo.id_version_contrato_aaef,ruta=`/integracion/contratos/${id}/deprecar`,m=actual.min;
      const previa=await listar(caso),z=await pedir('POST',ruta,{dias_gracia:m-1},caso),tras=await listar(caso);
      r.pruebas[caso][0]=rechazo(z,previa,tras)==='APROBADO'&&tras.find(x=>x.id_version_contrato_aaef===id)?.estado!=='ACTIVO'?'RECHAZADO':rechazo(z,previa,tras);
      if(tras.find(x=>x.id_version_contrato_aaef===id)?.estado==='ACTIVO'){
        const d=await pedir('POST',ruta,{dias_gracia:m},caso),lista=await listar(caso),v=lista.find(x=>x.id_version_contrato_aaef===id);
        r.pruebas[caso][1]=d.http===200&&d.data?.estado==='DEPRECADO'&&v?.estado==='DEPRECADO'?'APROBADO':d.http===200||d.http>=400&&d.http<500&&d.http!==401&&d.http!==403?'RECHAZADO':'NO_CONCLUYENTE';
        if(r.pruebas[caso][1]==='APROBADO'){
          const a=Date.parse(d.data.fecha_deprecacion),b=Date.parse(d.data.fecha_inactivacion);
          r.pruebas[caso][2]=Number.isFinite(a)&&Number.isFinite(b)&&b-a===m*86400000&&mismoInstante(v.fecha_inactivacion,d.data.fecha_inactivacion)?'APROBADO':'RECHAZADO';
        }
      }else r.observaciones.push('08: segunda deprecación NO_CONCLUYENTE; la ACTIVO cambió tras el primer intento');
    }else if(!seleccion.activo)r.observaciones.push('08 NO_CONCLUYENTE: no existe ACTIVO');
    else if(!seleccion.permisoDeprecar)r.observaciones.push('Sin permiso U de contratos_aaef: 08 NO_CONCLUYENTE');
    if(runAbierto&&permisos.some(x=>x.nombre_recurso==='auditoria_integracion'&&x.id_accion===2)){
      const z=await pedir('GET','/integracion/auditoria?pagina=1&tamano=100',undefined,'TC-M07-08');
      r.eventos.consulta_http=z.http;
      if(z.http===200){
        const items=z.data.items;
        r.eventos.registrados=items.filter(x=>x.tipo_evento==='CONTRATO_REGISTRADO'&&libres.includes(x.version_contrato)).map(x=>({id:x.id_evento_integracion,version:x.version_contrato,fecha:x.fecha_evento}));
        r.eventos.deprecados=items.filter(x=>x.tipo_evento==='CONTRATO_DEPRECADO'&&x.version_contrato===seleccion.activo?.contrato_version).map(x=>({id:x.id_evento_integracion,version:x.version_contrato,fecha:x.fecha_evento}));
      }else r.observaciones.push(`Eventos M07 no consultables: HTTP ${z.http}`);
    }else if(runAbierto)r.observaciones.push('Sin permiso R de auditoria_integracion: evidencia de eventos NO_CONCLUYENTE');
    if(runAbierto){
      const salida=path.join(dir,'newman'),collection=JSON.parse(fs.readFileSync(path.join(DIR,'G037.postman_collection.json'),'utf8'));
      if(!seleccion?.permisoM09R){collection.item=collection.item.filter(x=>!x.request.url.includes(M09));r.observaciones.push('Newman: GET M09 omitido por falta de permiso R');}
      const input={salida,coleccion:collection,environment:{values:[{key:'base_url',value:api},{key:'admin_token',value:token},{key:'run_id',value:c.runId},{key:'sandbox_secret',value:e.QA_SANDBOX_SECRET}]}};
      r.newman=await(dobles.newman??lanzarNewman)(input);
      for(const f of ['newman-G037.json','newman-G037.html'])if(fs.existsSync(path.join(salida,f)))r.evidencias.push(`newman/${f}`);
    }
  }catch(err){r.problemas_tecnicos.push(seguro(err.message));}
  finally{
    if(runAbierto){
      try{
        const z=await fetcher(`${api}/test-control/runs/${c.runId}`,{method:'DELETE',headers:{'X-Sandbox-Secret':e.QA_SANDBOX_SECRET},signal:AbortSignal.timeout(120000)});
        r.cierre.http=z.status;cerrado=z.status===200;
        if(cerrado&&base){
          const posterior=await listar();
          let m09Despues=null;if(m09Antes){const q=await pedir('GET',M09);if(q.http===200)m09Despues=q.raw;}
          r.cierre.rollback={verificado:verificarRollback(base,posterior,m09Antes,m09Despues),motivo:'Lectura pública poscierre sin cabeceras RUN: ids, estados y parámetros M09'};
        }else r.cierre.rollback={verificado:false,motivo:cerrado?'Línea base incompleta':'DELETE no confirmó 200'};
      }catch(err){r.cierre.rollback={verificado:false,motivo:seguro(err.message)};}
    }
    r.solicitudes=sanitize(r.solicitudes);r.plazo_ok=Date.now()<=deadline;armarResultado(r,c);
    guardar(path.join(dir,'resultado.json'),r);fs.writeFileSync(informeArchivo,informe(c,sanitize(r)),'utf8');
  }
  return r;
}
export async function principal(argv,{proceso=process.env,archivo=path.join(ROOT,'.env.qa'),prueba=false,fetcher=fetch,dobles={}}={}){
  const c=contexto(argv,prueba),e=leerEnv(proceso,archivo),p=preflight(c,e);
  fs.writeFileSync(path.join(c.dir,'preflight.json'),JSON.stringify(sanitize(p),null,2));
  if(!p.ok)return{preflight:p,codigo:2};const resultado=await ejecutar(c,e,fetcher,dobles);return{preflight:p,codigo:0,resultado};
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
  try{
    if(process.argv.includes('--capacidades'))console.log(JSON.stringify(CAPACIDADES));
    else if(process.argv.includes('--comprobar'))process.exitCode=comprobar();
    else{
      const prueba=process.env.NODE_ENV==='test'&&process.argv.includes('--prueba-cli-local');
      const archivo=prueba?path.resolve(process.env.G037_PRUEBA_ENV_FILE??'.'):path.join(ROOT,'.env.qa');
      if(prueba&&!archivo.startsWith(path.resolve(os.tmpdir())+path.sep))throw Error('ENV_PRUEBA_FUERA_TEMPORAL');
      const z=await principal(process.argv.slice(2),{archivo,prueba});
      if(z.codigo===2){console.error(`PREFLIGHT_${z.preflight.faltan.join('_')}`);process.exitCode=2;}
      else console.log(JSON.stringify({grupo:'G037',oficial:z.resultado.oficial,casos:z.resultado.casos,solicitudes:z.resultado.solicitudes_total}));
    }
  }catch(err){console.error(seguro(err.message));process.exitCode=2;}
}
