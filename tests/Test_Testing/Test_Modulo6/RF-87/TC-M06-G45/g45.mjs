import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {contrato, validarLecturas, validarError, esquema} from './lib/contrato.mjs';
import {informe} from './lib/informe.mjs';
import {sha256, clasificarFallo, validarFormaResultado, crearSolicitante, lanzarHijo, listarEvidencias, guardarResultado, contexto as contextoInfra, leerEnv as leerEnvInfra, preflight as preflightInfra} from './lib/infra.mjs';

const DIR=path.dirname(fileURLToPath(import.meta.url));
const ROOT=path.resolve(DIR,'../../../../..');
const API='https://www.api.inmero.co/api-sgpmp-test';
const FRONT='https://api.inmero.co/sigab-test';
const CASOS=['TC-M06-031','TC-M06-032','TC-M06-033'];
const LIMITE={solicitudes_totales:100,segundos:1800};
const archivos=['g45.mjs','lib/infra.mjs','lib/contrato.mjs','lib/informe.mjs','pruebas/contrato_g45.json','pruebas/escenarios_g45.json','pruebas/g45_escenarios.test.mjs','pruebas/simulador_g45.mjs','pruebas/newman_hijo.mjs','pruebas/verificar.mjs','G45.postman_collection.json','README.md'];
const reservada=/token|password|contrasena|cookie|secret|jwt|serial|identificador|numero_id_tributaria|correo|email|authorization/i;
const sanear=(x,k='')=>reservada.test(k)?'[RESERVADO]':Array.isArray(x)?x.map(v=>sanear(v)):x&&typeof x==='object'?Object.fromEntries(Object.entries(x).map(([key,v])=>[key,sanear(v,key)])):typeof x==='string'?x.replace(/eyJ[\w-]+\.[\w-]+\.[\w-]+|[\w.+-]+@[\w.-]+|\bQA-[A-Z0-9-]{4,}\b|\b\d{8,12}\b/g,'[RESERVADO]'):x;
const clean=x=>String(sanear(x)??'').slice(0,300);
const iguales=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
const porId=(ps,id)=>ps.find(x=>Number(x.id_periodo_contable)===id);
const reconocimiento=(historial,id)=>historial.reconocimientos.find(x=>Number(x.id_reconocimiento_inicial)===id);
const resumenReconocimiento=x=>x&&({estado:x.estado,fecha_reversion:x.fecha_reversion??null,justificacion_reversion:x.justificacion_reversion??null});
const idsReconocimientos=historial=>historial.reconocimientos.map(x=>Number(x.id_reconocimiento_inicial)).sort((a,b)=>a-b);
import {createHash} from 'node:crypto';
const digest=x=>createHash('sha256').update(JSON.stringify(x)).digest('hex');
const comprobarC=(id,esperado,estado,observado)=>({id,esperado,estado,observado:clean(observado)});
const veredicto=checks=>checks.some(x=>x.estado==='RECHAZADO')?'RECHAZADO':checks.some(x=>x.estado==='NO_CONCLUYENTE')?'NO_CONCLUYENTE':'APROBADO';
export const CAPACIDADES={contrato:'sigab-qa-ejecutor/1',grupo:'G45',casos:CASOS,operaciones:['evaluar','reintentar','reevaluar'],versiones:{min:1,max:99},comprobaciones_obligatorias:{'TC-M06-031':{API:['031_en_cierre']},'TC-M06-032':{API:['032_alta_costo','032_eliminar_reconocimiento','032_integridad']},'TC-M06-033':{API:['033_ajuste','033_cerrado_intacto']}},limite:LIMITE,baja_automatizada:true};
export function comprobar(){
  const faltan=archivos.filter(x=>!fs.existsSync(path.join(DIR,x)));
  let col;try{col=JSON.parse(fs.readFileSync(path.join(DIR,'G45.postman_collection.json'),'utf8'));}catch{}
  const superior=fs.existsSync(path.join(DIR,'Resultados'))&&fs.readdirSync(path.join(DIR,'Resultados')).some(x=>x.endsWith('.md'));
  const imports=fs.readFileSync(path.join(DIR,'g45.mjs'),'utf8').match(/from ['"]([^'"]+)['"]/g)??[];
  const ok=!faltan.length&&col?.item?.length>=4&&col.item.every(x=>x.request?.method==='GET')&&contrato.rutas.length>0&&!superior&&imports.every(x=>!x.includes('../TC-M06-'));
  console.log(JSON.stringify({grupo:'G45',ok,faltan,items:col?.item?.length??0,sha256:Object.fromEntries(archivos.filter(x=>fs.existsSync(path.join(DIR,x))).map(x=>[x,sha256(path.join(DIR,x))]))}));
  return ok?0:2;
}
export const contexto=(a,prueba=false)=>contextoInfra(a,{capacidades:CAPACIDADES,grupo:'G45',casos:CASOS,dir:DIR,prueba});
export const leerEnv=(p=process.env,archivo=path.join(ROOT,'.env.qa'))=>leerEnvInfra(p,archivo);
export const preflight=(c,e=process.env)=>preflightInfra(c,e,{grupo:'G45',api:API,front:FRONT,efectos:['1 inicio de sesión Contador','1 POST cierre del 8 sin autorizar','1 POST costo sobre 944 (rechazo esperado)','1 POST reversión de 949 (409 esperado)','hasta 2 GET OpenAPI','lecturas API y Newman','DELETE del RUN siempre y lecturas poscierre sin cabeceras']});

export async function ejecutar(c,e=process.env,opciones={}){
  const local=opciones.ensayo===true&&/^http:\/\/127\.0\.0\.1:\d+\/api$/.test(opciones.api??'');
  const api=local?opciones.api:API;
  const pf=local?{ok:true,barreras:[],efectos:preflight(c,e).efectos}:preflight(c,e);
  if(!pf.ok)throw Error(`PREFLIGHT_${pf.barreras.join('_')}`);
  const r={grupo:'G45',rf:'RF-87 v1.1',run_id:c.runId,version:c.version,autorizacion_referencia:c.ref,casos:Object.fromEntries(CASOS.map(k=>[k,{estado:'NO_CONCLUYENTE',motivo:'No ejecutado',comprobaciones:[]}])),preflight:pf,preflight_datos:[],solicitudes:[],comprobaciones:[],incidencias:[],evidencias:[],observaciones:[
    '031: costo, variación, reconocimiento y medición durante la pausa, pesaje M02 y cola A/B no evaluables: la API pública M06 no crea hechos fechados dentro del 8 ni eventos M02; no existe EN_CIERRE previo.',
    '032: modificación/eliminación de costos y variaciones, altas fechadas en período cerrado y notificación de variaciones no aplican: no existe ruta pública M06 para fijar tales fechas o modificar esos registros; RF-86 prohíbe modificarlos.'
  ],problemas_tecnicos:[],respuestas:{},cypress:{paneles:{},total_pruebas:0},rollback:{verificado:false},herramientas:{node:process.version},oficial:false,consume_version:false};
  let token=null,permitirNewman=false,basales=null,periodosIds=[],costoIds=[],escrituras=0,activo949Base=null;
  const inicio=Date.now();
  const solicitante=crearSolicitante({api,runId:c.runId,secret:e.QA_SANDBOX_SECRET,limite:LIMITE,solicitudes:r.solicitudes,esquema,validarLecturas,validarError,clean,id:n=>`G45-${String(n).padStart(3,'0')}`,token:()=>token,inicio});
  const req=solicitante.req;
  const get=async(ruta,sinRun=false)=>{const z=await req('GET',ruta,undefined,sinRun);if(z.http!==200)throw Error(`GET_${z.http}_${ruta}`);return z.data;};
  const periodos=(sinRun=false)=>get('/finanzas/periodos',sinRun);
  const estado=async(id,sinRun=false)=>{
    const p=porId(await periodos(sinRun),id);
    if(!p)throw Error(`PERIODO_${id}_AUSENTE`);
    const lineas=await get(`/finanzas/lineas?id_periodo_contable=${id}`,sinRun);
    const comprobantes=await get(`/finanzas/periodos/${id}/comprobantes`,sinRun);
    const variaciones=await get(`/finanzas/periodos/${id}/variaciones`,sinRun);
    return {estado:p.estado,fecha_cierre:p.fecha_cierre??null,ultimo_cierre:p.ultimo_cierre??null,lineas,comprobantes,variaciones};
  };
  const resumen=s=>({estado:s.estado,fecha_cierre:s.fecha_cierre,ultimo_cierre:sanear(s.ultimo_cierre),hash_contenido:digest(s),lineas:s.lineas.length,comprobantes:s.comprobantes.length,variaciones:s.variaciones.length});
  const checkDato=(requisito,esperado,observado,cumple,bloqueante=true)=>r.preflight_datos.push({requisito,esperado,observado:sanear(observado),cumple:Boolean(cumple),bloqueante});
  const add=(caso,z)=>{r.casos[caso].comprobaciones.push(z);r.comprobaciones.push({caso,id:z.id,fuente:'API',tipo:'ASSERT',estado:z.estado,evidencia:'resultado.json'});};
  const cerrarCasos=()=>{for(const caso of CASOS){const x=r.casos[caso];if(x.comprobaciones.length){x.estado=veredicto(x.comprobaciones);x.motivo=x.estado==='APROBADO'?'Criterios conformes':x.comprobaciones.filter(z=>z.estado===x.estado).map(z=>z.id).join(', ')||x.comprobaciones.filter(z=>z.estado!=='APROBADO').map(z=>z.id).join(', ');}}};
  const incidencia=(id,casos,esperado,obtenido,severidad,justificacion,relacion='')=>r.incidencias.push({id:`INC-M06-G45-${id}`,casos,esperado,obtenido:clean(obtenido),evidencia:'resultado.json',severidad,justificacion_severidad:justificacion,certeza:'CONFIRMADA',equipo:'Desarrollo',fundamento:'Primera discrepancia comprobada por la API pública en TEST.',causa_raiz:'Por determinar.',accion:'Desarrollo revisa la discrepancia; QA repite con autorización.',...(relacion?{relacion}:{}),...(id==='03'?{clasificacion:'DEFECTO_FUNCIONAL_CANDIDATO'}:{})});
  try{
    const login=await req('POST','/sesiones/',{correo_electronico:e.QA_CONTADOR_EMAIL,contrasena:e.QA_CONTADOR_PASSWORD},true);
    if(login.http!==200||!login.data?.token)throw Error(`LOGIN_CONTADOR_${login.http}`);
    token=login.data.token;
    const permisos=(await get('/sesiones/me/permisos')).permisos;
    const tiene=(n,a)=>permisos.some(p=>p.nombre_recurso===n&&Number(p.id_accion)===a);
    if(![['cierre_periodo',5],['cierre_periodo',2],['costos_activos',1],['reconocimiento_inicial',4]].every(([n,a])=>tiene(n,a)))throw Error('PERMISOS_NO_COINCIDEN');
    const ps=await periodos();periodosIds=ps.map(x=>Number(x.id_periodo_contable)).sort((a,b)=>a-b);
    const p8=await get('/finanzas/periodos/8/prevalidacion');
    const s7=await estado(7),s8=await estado(8),s219=await estado(219);
    const a944=await get('/finanzas/activos/944'),a949=await get('/finanzas/activos/949');
    activo949Base={reconocimiento:resumenReconocimiento(reconocimiento(a949,20)),ids:idsReconocimientos(a949)};
    const costosAntes=await get('/finanzas/costos?id_activo_biologico=944');
    costoIds=costosAntes.map(x=>Number(x.id_registro_costo)).sort((a,b)=>a-b);
    basales={s7,s8,s219};r.bases={periodo_7:resumen(s7),periodo_8:resumen(s8),periodo_219:resumen(s219),costos_944_ids:costoIds};
    for(const [id,s,esperado] of [[7,s7,'CERRADO'],[8,s8,'ABIERTO'],[219,s219,'CERRADO']])checkDato(`periodo_${id}_estado`,esperado,s.estado,s.estado===esperado);
    checkDato('prevalidacion_8_sin_bloqueos','[]',p8.bloqueos?.map(x=>x.codigo),Array.isArray(p8.bloqueos)&&p8.bloqueos.length===0);
    checkDato('prevalidacion_8_linea_sin_trazabilidad','al menos una línea',p8.lineas_sin_trazabilidad?.length,Array.isArray(p8.lineas_sin_trazabilidad)&&p8.lineas_sin_trazabilidad.length>0);
    checkDato('activo_944_activo_finca_463','ACTIVO, finca 463', {estado:a944.activo.estado,id_finca:a944.activo.id_finca},a944.activo.estado==='ACTIVO'&&Number(a944.activo.id_finca)===463);
    const reconoc944=reconocimiento(a944,15);
    checkDato('activo_944_reconocimiento_vigente','reconocimiento 15 CONFIRMADO en período 7',reconoc944&&{id:reconoc944.id_reconocimiento_inicial,estado:reconoc944.estado,id_periodo_contable:reconoc944.id_periodo_contable},reconoc944?.estado==='CONFIRMADO'&&Number(reconoc944.id_periodo_contable)===7);
    const reconoc949=reconocimiento(a949,20);
    checkDato('activo_949_reconocimiento_vigente_periodo_7','reconocimiento 20 CONFIRMADO en período 7 y activo ACTIVO',{reconocimiento:reconoc949&&{id:reconoc949.id_reconocimiento_inicial,estado:reconoc949.estado,id_periodo_contable:reconoc949.id_periodo_contable},estado:a949.activo.estado},reconoc949?.estado==='CONFIRMADO'&&Number(reconoc949.id_periodo_contable)===7&&a949.activo.estado==='ACTIVO');
    const ajustesIniciales=s8.lineas.filter(x=>x.tipo_hecho==='AJUSTE_PERIODO_ANTERIOR');
    checkDato('periodo_8_sin_ajustes_previos',0,ajustesIniciales.length,ajustesIniciales.length===0);
    if(r.preflight_datos.some(x=>x.bloqueante&&!x.cumple))throw Error('PREFLIGHT_DATOS_NO_CONCLUYENTE_'+r.preflight_datos.filter(x=>x.bloqueante&&!x.cumple).map(x=>x.requisito).join('_'));
    const z31=await req('POST','/finanzas/periodos/8/cierre',{});escrituras++;
    r.respuestas.cierre={http:z31.http,cuerpo:sanear(z31.data)};
    const despues31=porId(await periodos(),8);
    const exclusion=z31.http===409&&z31.data?.error_code==='EXCLUSION_REQUIERE_AUTORIZACION';
    const est31=exclusion?(despues31?.estado==='EN_CIERRE'?'APROBADO':despues31?.estado==='ABIERTO'?'RECHAZADO':'NO_CONCLUYENTE'):'NO_CONCLUYENTE';
    add(CASOS[0],comprobarC('031_en_cierre','EN_CIERRE mientras se solicita autorización de exclusión',est31,`HTTP ${z31.http}; error ${z31.data?.error_code??'ausente'}; estado ${despues31?.estado??'ausente'}`));
    if(est31==='RECHAZADO')incidencia('01',[CASOS[0]],'EN_CIERRE durante la espera',`HTTP ${z31.http}; estado ${despues31?.estado}`,'MEDIA','El estado de espera del cierre no se representa como exige CA-7.','INC-M06-G43-01');
    if(z31.http===200)r.observaciones.push('El cierre respondió 200; no se reintentó ni se autorizó exclusión. 031 es NO_CONCLUYENTE.');
    const costo=await req('POST','/finanzas/costos',{subtipo_costo:'MANO_OBRA',origen_costo:'MANO_OBRA_PROPIA',monto_costo:'50.00',fecha_costo:'2026-11-05',id_activo_biologico:944,naturaleza_costo:'MANTENIMIENTO'});escrituras++;
    r.respuestas.costo={http:costo.http,cuerpo:sanear(costo.data)};
    const s7Costo=await estado(7);
    const costoCerrado=['PERIODO_CONTABLE_CERRADO','PERIODO_CERRADO'].includes(costo.data?.error_code);
    const costoIntacto=iguales(s7Costo,s7);
    const costoEstado=costo.http>=200&&costo.http<300?'RECHAZADO':!costoIntacto?'RECHAZADO':costoCerrado&&costo.http===409?'APROBADO':costoCerrado&&costo.http===422?'RECHAZADO':'NO_CONCLUYENTE';
    add(CASOS[1],comprobarC('032_alta_costo','HTTP 409 por período cerrado y período 7 idéntico',costoEstado,`HTTP ${costo.http}; error ${costo.data?.error_code??'ausente'}; mensaje ${costo.data?.message??'ausente'}; período 7 idéntico ${costoIntacto}`));
    const reversion=await req('POST','/finanzas/reconocimientos/949/reversion',{motivo_reversion:'Corrección contable de prueba autorizada'});escrituras++;
    r.respuestas.reversion={http:reversion.http,cuerpo:sanear(reversion.data)};
    const s7Reversion=await estado(7);
    const reversionIntacta=iguales(s7Reversion,s7);
    const reversionEstado=reversion.http>=200&&reversion.http<300?'RECHAZADO':!reversionIntacta?'RECHAZADO':reversion.http===409&&reversion.data?.error_code==='REVERSION_BLOQUEADA'?'APROBADO':'NO_CONCLUYENTE';
    add(CASOS[1],comprobarC('032_eliminar_reconocimiento','HTTP 409 con REVERSION_BLOQUEADA y período 7 idéntico',reversionEstado,`HTTP ${reversion.http}; error ${reversion.data?.error_code??'ausente'}; mensaje ${reversion.data?.message??'ausente'}; período 7 idéntico ${reversionIntacta}`));
    const lineas8=await get('/finanzas/lineas?id_periodo_contable=8');
    const ids7=new Set(s7.lineas.map(x=>Number(x.id_linea_asiento_nic41)));
    const ajuste=lineas8.find(x=>x.tipo_hecho==='AJUSTE_PERIODO_ANTERIOR'&&ids7.has(Number(x.id_linea_corregida??x.id_linea_original))&&Boolean(String(x.justificacion??'').trim()));
    add(CASOS[2],comprobarC('033_ajuste','AJUSTE_PERIODO_ANTERIOR en 8, referencia a línea de 7 y justificación',ajuste?'APROBADO':'RECHAZADO',`líneas de ajuste ${lineas8.filter(x=>x.tipo_hecho==='AJUSTE_PERIODO_ANTERIOR').length}; referencia y justificación ${Boolean(ajuste)}`));
    try{
      let o=await req('GET','/openapi.json');
      if(o.http===404)o=await req('GET','/docs/openapi.json');
      r.openapi={http:o.http,rutas_ajuste:o.http===200?Object.keys(o.data.paths??{}).filter(x=>x.includes('ajuste')&&x.includes('finanzas')):[]};
    }catch(err){r.openapi={error:clean(err.message)};}
    const s7Final=await estado(7),s219Final=await estado(219);
    const integridad=iguales(s7Final,s7)&&iguales(s219Final,s219);
    r.integridad={periodo_7:resumen(s7Final),periodo_219:resumen(s219Final),ambos_identicos:integridad};
    add(CASOS[1],comprobarC('032_integridad','líneas, comprobantes, variaciones, estado, fecha y último cierre de 7 y 219 idénticos',integridad?'APROBADO':'RECHAZADO',`7 ${iguales(s7Final,s7)}; 219 ${iguales(s219Final,s219)}`));
    const cerradoIntacto=s7Final.estado==='CERRADO'&&s7Final.fecha_cierre===s7.fecha_cierre&&iguales(s7Final.lineas,s7.lineas)&&iguales(s7Final.comprobantes,s7.comprobantes);
    add(CASOS[2],comprobarC('033_cerrado_intacto','7 CERRADO con fecha, líneas y comprobantes idénticos',cerradoIntacto?'APROBADO':'RECHAZADO',`estado ${s7Final.estado}; contenido idéntico ${cerradoIntacto}`));
    cerrarCasos();
    if(r.casos[CASOS[1]].estado==='RECHAZADO'){
      const cambio=!integridad||!costoIntacto||!reversionIntacta;
      const aceptada=[costo.http,reversion.http].some(x=>x>=200&&x<300);
      const severidad=cambio||aceptada?'ALTA':'MEDIA';
      incidencia('02',[CASOS[1]],'HTTP 409 por período cerrado y reversión bloqueada, con períodos cerrados intactos',`costo ${costo.http} ${clean(costo.data?.error_code)}; reversión ${reversion.http} ${clean(reversion.data?.error_code)}; integridad ${integridad}`,severidad,severidad==='ALTA'?'Se aceptó una escritura o cambió el período cerrado.':'El rechazo 422 por período cerrado incumple el HTTP 409 exigido por CA-3.');
    }
    if(r.casos[CASOS[2]].comprobaciones.find(x=>x.id==='033_ajuste')?.estado==='RECHAZADO')incidencia('03',[CASOS[2]],'Ajuste en período 8 con referencia y justificación','No se halló ajuste completo','ALTA','La vía de corrección de prioridad Must no se acreditó por API pública.');
    permitirNewman=CASOS.every(x=>['APROBADO','RECHAZADO'].includes(r.casos[x].estado));
    if(permitirNewman){
      const lanzar=local&&typeof opciones.hijo==='function'?opciones.hijo:(script,input,timeout)=>lanzarHijo({base:DIR,script,input,timeout,env:e,clean});
      const n=await lanzar('newman_hijo.mjs',{salida:path.join(c.dir,'newman'),coleccion:path.join(DIR,'G45.postman_collection.json'),environment:{values:[{key:'base_url',value:api},{key:'contador_token',value:token},{key:'run_id',value:c.runId},{key:'sandbox_secret',value:e.QA_SANDBOX_SECRET}]}},300000);
      r.herramientas.newman=n.data??{codigo:2};if(n.code||n.data?.codigo!==0||n.data?.fallos)r.problemas_tecnicos.push(`NEWMAN_${clean(n.error??n.code)}`);
    }
  }catch(err){r.problemas_tecnicos.push(clean(err.message));for(const caso of CASOS)if(r.casos[caso].motivo==='No ejecutado')r.casos[caso]={estado:'NO_CONCLUYENTE',motivo:clean(err.message),comprobaciones:[]};}
  finally{
    r.cierre={run:{cierre_http:null},rollback:r.rollback};
    if(token){try{
      const d=await req('DELETE',`/test-control/runs/${c.runId}`);r.cierre.run.cierre_http=d.http;
      if(d.http!==200)throw Error(`DELETE_${d.http}`);
      if(!basales)throw Error('BASES_NO_DISPONIBLES');
      const after7=await estado(7,true),after8=await estado(8,true),after219=await estado(219,true);
      const ps=await periodos(true),costos=await get('/finanzas/costos?id_activo_biologico=944',true),activo949=await get('/finanzas/activos/949',true);
      const ids=ps.map(x=>Number(x.id_periodo_contable)).sort((a,b)=>a-b);
      const cid=costos.map(x=>Number(x.id_registro_costo)).sort((a,b)=>a-b);
       const reconocimiento949=iguales(resumenReconocimiento(reconocimiento(activo949,20)),activo949Base.reconocimiento)&&iguales(idsReconocimientos(activo949),activo949Base.ids);
      const verificado=iguales(after7,basales.s7)&&after8.estado==='ABIERTO'&&iguales(after8,basales.s8)&&iguales(after219,basales.s219)&&iguales(ids,periodosIds)&&iguales(cid,costoIds)&&reconocimiento949;
      r.rollback={verificado,motivo:`Lecturas sin cabeceras: 7 ${iguales(after7,basales.s7)}; 8 ABIERTO e idéntico ${after8.estado==='ABIERTO'&&iguales(after8,basales.s8)}; 219 ${iguales(after219,basales.s219)}; reconocimiento de 949 vigente ${reconocimiento949}; costos 944 ${iguales(cid,costoIds)}; períodos nuevos ${!iguales(ids,periodosIds)}`};
    }catch(err){r.rollback={verificado:false,motivo:clean(err.message)};r.problemas_tecnicos.push(`ROLLBACK_${clean(err.message)}`);}}
    r.cierre.rollback=r.rollback;
    r.total_solicitudes_api=solicitante.total()+(r.herramientas.newman?.solicitudes??0);
    r.duracion_segundos=Math.ceil((Date.now()-inicio)/1000);
    r.evidencias=listarEvidencias(c.dir).filter(x=>x.startsWith('newman/'));
    r.oficial=permitirNewman&&r.rollback.verificado&&r.cierre.run.cierre_http===200&&r.herramientas.newman?.codigo===0&&r.herramientas.newman?.fallos===0&&r.herramientas.newman?.reportes===true&&['newman/newman-G45.json','newman/newman-G45.html'].every(x=>r.evidencias.includes(x))&&r.problemas_tecnicos.length===0&&r.total_solicitudes_api<=LIMITE.solicitudes_totales&&r.duracion_segundos<=LIMITE.segundos;
    r.consume_version=escrituras>0;
    r.clasificacion_fallo=clasificarFallo(r);
    r.sha256={ejecutor:sha256(path.join(DIR,'g45.mjs')),infraestructura:Object.fromEntries(['lib/infra.mjs','lib/contrato.mjs','lib/informe.mjs','pruebas/newman_hijo.mjs','pruebas/verificar.mjs'].map(x=>[x,sha256(path.join(DIR,x))]))};
    const forma=validarFormaResultado(r,CAPACIDADES,c.dir);if(forma.length){r.problemas_tecnicos.push(`RESULTADO_FORMA_${forma.join('_')}`);r.oficial=false;r.clasificacion_fallo='CONTRATO';}
    guardarResultado(c,r,informe);
  }
  return r;
}

if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
  try{if(process.argv.includes('--capacidades'))console.log(JSON.stringify(CAPACIDADES));
    else if(process.argv.includes('--comprobar'))process.exitCode=comprobar();
    else{const prueba=process.env.NODE_ENV==='test'&&process.argv.includes('--prueba-cli-local');const archivo=prueba?path.resolve(process.env.G45_PRUEBA_ENV_FILE??'.'):path.join(ROOT,'.env.qa');if(prueba&&!archivo.startsWith(path.resolve(os.tmpdir())+path.sep))throw Error('ENV_PRUEBA_FUERA_TEMPORAL');const c=contexto(process.argv.slice(2),prueba),e=leerEnv(process.env,archivo),p=preflight(c,e);fs.writeFileSync(path.join(c.dir,'preflight.json'),JSON.stringify(p,null,2));if(!p.ok){console.error(`PREFLIGHT_${p.barreras.join('_')}`);process.exitCode=2;}else{const r=await ejecutar(c,e);console.log(JSON.stringify({grupo:'G45',oficial:r.oficial,estados:Object.fromEntries(CASOS.map(k=>[k,r.casos[k].estado])),solicitudes:r.total_solicitudes_api}));}}
  }catch(err){console.error(clean(err.message));process.exitCode=2;}
}
