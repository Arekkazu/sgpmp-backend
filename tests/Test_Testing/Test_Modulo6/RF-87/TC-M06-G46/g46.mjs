import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {esquema,validarLecturas,validarError} from './lib/contrato.mjs';
import {informe} from './lib/informe.mjs';
import {sha256,clasificarFallo,validarFormaResultado,crearSolicitante,lanzarHijo,listarEvidencias,guardarResultado,contexto as contextoInfra,leerEnv as leerEnvInfra,preflight as preflightInfra} from './lib/infra.mjs';

const DIR=path.dirname(fileURLToPath(import.meta.url));
const ROOT=path.resolve(DIR,'../../../../..');
const API='https://www.api.inmero.co/api-sgpmp-test';
const FRONT='https://api.inmero.co/sigab-test';
const CASO='TC-M06-034';
export const IDS=['034_iniciado','034_completado','034_hash_verificable','034_hash_eventos','034_referencias'];
const LIMITE={solicitudes_totales:100,segundos:1800};
const archivos=['g46.mjs','lib/infra.mjs','lib/contrato.mjs','lib/informe.mjs','pruebas/contrato_g46.json','pruebas/newman_hijo.mjs','pruebas/verificar.mjs','pruebas/g46_hash.test.py','pruebas/g46_cli.test.mjs','pruebas/g46_dto.test.py','pruebas/g46_escenarios.test.mjs','pruebas/simulador_g46.mjs','pruebas/escenarios_g46.json','G46.postman_collection.json','README.md'];
const reservada=/token|password|contrasena|cookie|secret|jwt|serial|numero_id_tributaria|correo|email|authorization/i;
const sanear=(x,k='')=>reservada.test(k)?'[RESERVADO]':Array.isArray(x)?x.map(v=>sanear(v)):x&&typeof x==='object'?Object.fromEntries(Object.entries(x).map(([a,v])=>[a,sanear(v,a)])):typeof x==='string'?x.replace(/eyJ[\w-]+\.[\w-]+\.[\w-]+|[\w.+-]+@[\w.-]+|\bQA-[A-Z0-9-]{4,}\b|\b\d{8,12}\b/g,'[RESERVADO]'):x;
const clean=x=>String(sanear(x)??'').slice(0,500);
const iguales=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
const porId=(ps,id)=>ps.find(p=>Number(p.id_periodo_contable)===id);
const costoRollback=x=>Object.fromEntries(['id_valoracion_por_costo','es_activa','depreciacion_acumulada','valor_contable_por_costo'].map(k=>[k,x?.[k]??null]));
const hex=x=>typeof x==='string'&&/^[0-9a-f]{64}$/.test(x);
const canon=x=>JSON.stringify(x,(_k,v)=>v&&typeof v==='object'&&!Array.isArray(v)?Object.fromEntries(Object.keys(v).sort().map(k=>[k,v[k]])):v);
export const hashCanonico=x=>createHash('sha256').update(canon(x),'utf8').digest('hex');
const prueba=(id,esperado,estado,observado,detalle={})=>({id,esperado,estado,observado:clean(observado),...detalle});
const veredicto=xs=>xs.some(x=>x.estado==='RECHAZADO')?'RECHAZADO':xs.some(x=>x.estado==='NO_CONCLUYENTE')?'NO_CONCLUYENTE':'APROBADO';
export const CAPACIDADES={contrato:'sigab-qa-ejecutor/1',grupo:'G46',casos:[CASO],operaciones:['evaluar','reintentar','reevaluar'],versiones:{min:1,max:99},comprobaciones_obligatorias:{[CASO]:{API:IDS}},limite:LIMITE,baja_automatizada:true};
export function comprobar(){const faltan=archivos.filter(x=>!fs.existsSync(path.join(DIR,x)));let col;try{col=JSON.parse(fs.readFileSync(path.join(DIR,'G46.postman_collection.json'),'utf8'));}catch{}const superior=fs.existsSync(path.join(DIR,'Resultados'))&&fs.readdirSync(path.join(DIR,'Resultados')).some(x=>x.endsWith('.md'));const ok=!faltan.length&&col?.item?.length>=4&&col.item.every(x=>x.request?.method==='GET')&&!superior;console.log(JSON.stringify({grupo:'G46',ok,faltan,items:col?.item?.length??0,sha256:Object.fromEntries(archivos.filter(x=>fs.existsSync(path.join(DIR,x))).map(x=>[x,sha256(path.join(DIR,x))]))}));return ok?0:2;}
export const contexto=(a,pruebaLocal=false)=>contextoInfra(a,{capacidades:CAPACIDADES,grupo:'G46',casos:[CASO],dir:DIR,prueba:pruebaLocal});
export const leerEnv=(p=process.env,archivo=path.join(ROOT,'.env.qa'))=>leerEnvInfra(p,archivo);
export const preflight=(c,e=process.env)=>preflightInfra(c,e,{grupo:'G46',api:API,front:FRONT,efectos:['1 login Contador','1 POST cierre del 220 dentro del sandbox sin exclusiones','lecturas API y Newman','DELETE del RUN siempre','lecturas de rollback sin cabeceras']});

export async function ejecutar(c,e=process.env,opciones={}){
  const local=opciones.ensayo===true&&/^http:\/\/127\.0\.0\.1:\d+\/api$/.test(opciones.api??'');
  const api=local?opciones.api:API,pf=local?{ok:true,barreras:[],efectos:preflight(c,e).efectos}:preflight(c,e);
  if(!pf.ok)throw Error(`PREFLIGHT_${pf.barreras.join('_')}`);
  const r={grupo:'G46',rf:'RF-87',run_id:c.runId,version:c.version,autorizacion_referencia:c.ref,casos:{[CASO]:{estado:'NO_CONCLUYENTE',motivo:'No ejecutado',comprobaciones:[]}},preflight:pf,preflight_datos:[],solicitudes:[],comprobaciones:[],incidencias:[],evidencias:[],observaciones:['El hash_integridad de auditoría lo calcula un trigger sobre la fila completa; no se puede recalcular por API.','Las API de comprobantes y variaciones no exponen id_cierre.','Los eventos se delimitan por id_evento, porque now() dentro del sandbox es el inicio de la transacción.'],problemas_tecnicos:[],respuestas:{},cypress:{paneles:{},total_pruebas:0},rollback:{verificado:false},herramientas:{node:process.version},oficial:false,consume_version:false};
  let token=null,basal=null,periodosIds=[],maxEvento=null,permitirNewman=false,escrituras=0,idCierre=null;
  const inicio=Date.now();
  const solicitante=crearSolicitante({api,runId:c.runId,secret:e.QA_SANDBOX_SECRET,limite:LIMITE,solicitudes:r.solicitudes,esquema,validarLecturas,validarError,clean,id:n=>`G46-${String(n).padStart(3,'0')}`,token:()=>token,inicio});
  const req=solicitante.req;
  const get=async(ruta,sinRun=false)=>{const z=await req('GET',ruta,undefined,sinRun);if(z.http!==200)throw Error(`GET_${z.http}_${ruta}`);return z.data;};
  const periodos=(sinRun=false)=>get('/finanzas/periodos',sinRun);
  const auditoria=async(id,opts='',sinRun=false)=>{let pagina=1,out=[];let total=0;do{const q=`/finanzas/auditoria?id_periodo_contable=${id}&formato=TECNICO&tamano=500&pagina=${pagina}&orden=DESC${opts}`;const z=await get(q,sinRun);total=z.total_registros;out.push(...z.eventos);pagina++;if(pagina>20)throw Error('AUDITORIA_PAGINACION_EXCESIVA');}while(out.length<total);return out;};
  const estado=async(sinRun=false)=>({periodos:await periodos(sinRun),lineas:await get('/finanzas/lineas?id_periodo_contable=220',sinRun),comprobantes:await get('/finanzas/periodos/220/comprobantes',sinRun),variaciones:await get('/finanzas/periodos/220/variaciones',sinRun),activo:await get('/finanzas/activos/1573',sinRun)});
  const add=z=>{r.casos[CASO].comprobaciones.push(z);r.comprobaciones.push({caso:CASO,id:z.id,fuente:'API',tipo:'ASSERT',estado:z.estado,evidencia:'resultado.json'});};
  const noConcluyente=motivo=>{for(const id of IDS)if(!r.casos[CASO].comprobaciones.some(x=>x.id===id))add(prueba(id,'Oráculo de la orden ORD-G46-001','NO_CONCLUYENTE',motivo));};
  const checkDato=(requisito,esperado,observado,cumple,bloqueante=true)=>r.preflight_datos.push({requisito,esperado,observado:sanear(observado),cumple:Boolean(cumple),bloqueante});
  try{
    const login=await req('POST','/sesiones/',{correo_electronico:e.QA_CONTADOR_EMAIL,contrasena:e.QA_CONTADOR_PASSWORD},true);
    if(login.http!==200||!login.data?.token)throw Error(`LOGIN_CONTADOR_${login.http}`);token=login.data.token;
    const permisos=(await get('/sesiones/me/permisos')).permisos;
    if(![['cierre_periodo',5],['cierre_periodo',2],['auditoria_financiera',2]].every(([n,a])=>permisos.some(p=>p.nombre_recurso===n&&Number(p.id_accion)===a)))throw Error('PERMISOS_NO_COINCIDEN');
    const prev=await get('/finanzas/periodos/220/prevalidacion');
    const conf=await get('/finanzas/configuracion');
    basal=await estado();periodosIds=basal.periodos.map(x=>Number(x.id_periodo_contable)).sort((a,b)=>a-b);
    const baseAudit=await get('/finanzas/auditoria?id_periodo_contable=220&formato=TECNICO&orden=DESC&tamano=1&pagina=1');maxEvento=baseAudit.eventos.length?Number(baseAudit.eventos[0].id_evento):0;
    const p220=porId(basal.periodos,220);
    checkDato('periodo_220_abierto','ABIERTO',p220?.estado,p220?.estado==='ABIERTO');
    for(const campo of ['bloqueos','lineas_sin_trazabilidad','activos_sin_precio'])checkDato(`prevalidacion_220_${campo}_vacio`,'[]',prev[campo]?.length,Array.isArray(prev[campo])&&prev[campo].length===0);
    for(const [id,tipo,debito,credito] of [[34,'MANO_OBRA_PROPIA','158405','250505'],[49,'DEPRECIACION_ACTIVO_COSTO','516005','159205']]){const m=conf.matriz.find(x=>Number(x.id_asignacion_cuenta_contable)===id);checkDato(`matriz_${id}_generica_activa`,`${tipo}/UNICO ${debito}/${credito}`,m&&{id_asignacion_cuenta_contable:m.id_asignacion_cuenta_contable,tipo_hecho:m.tipo_hecho,sentido:m.sentido,id_especie:m.id_especie,subtipo_costo:m.subtipo_costo,cuenta_debito:m.cuenta_debito,cuenta_credito:m.cuenta_credito},Boolean(m&&m.tipo_hecho===tipo&&m.sentido==='UNICO'&&m.id_especie===null&&m.subtipo_costo===null&&m.cuenta_debito===debito&&m.cuenta_credito===credito));}
    const costo=basal.activo.valoracion_costo;
    checkDato('activo_1573_valoracion_costo_activa','valoración por costo activa',costo&&{es_activa:costo.es_activa,vida_util_meses:costo.vida_util_meses,depreciacion_acumulada:costo.depreciacion_acumulada},costo?.es_activa===true,false);
    if(r.preflight_datos.some(x=>x.bloqueante&&!x.cumple))throw Error('PREFLIGHT_DATOS_NO_CONCLUYENTE_'+r.preflight_datos.filter(x=>x.bloqueante&&!x.cumple).map(x=>x.requisito).join('_'));
    const cierre=await req('POST','/finanzas/periodos/220/cierre',{});escrituras++;
    r.respuestas.cierre={http:cierre.http,cuerpo:sanear(cierre.data)};
    if(cierre.http!==200){noConcluyente(`POST cierre HTTP ${cierre.http}; no se reintentó`);}
    else{
      idCierre=Number(cierre.data?.id_cierre);
      const posterior=await estado();const ultimo=porId(posterior.periodos,220)?.ultimo_cierre;
      const eventos=(await auditoria(220)).filter(x=>Number(x.id_evento)>maxEvento);
      r.auditoria_cierre=sanear(eventos);
      const iniciados=eventos.filter(x=>x.tipo_evento==='CIERRE_PERIODO_INICIADO');
      const completados=eventos.filter(x=>x.tipo_evento==='CIERRE_PERIODO_COMPLETADO');
      const usuario=ultimo?.id_usuario_ejecutor;
      const i=iniciados[0],f=completados[0],payload=f?.payload_evento;
      const iniciado=iniciados.length===1&&Number(i.id_referencia)===idCierre&&usuario!=null&&Number(i.id_usuario)===Number(usuario)&&Boolean(i.timestamp_evento);
      add(prueba('034_iniciado','Un INICIADO del 220 con id_cierre, ejecutor y timestamp',iniciado?'APROBADO':'RECHAZADO',`cantidad ${iniciados.length}; referencia ${i?.id_referencia}; usuario ${i?.id_usuario}; ejecutor ${usuario}; timestamp ${Boolean(i?.timestamp_evento)}`));
      const codigos=posterior.comprobantes.map(x=>x.codigo).sort();const codigosEvento=Array.isArray(payload?.comprobantes)?payload.comprobantes.map(x=>x.codigo).sort():null;
      const completo=completados.length===1&&Number(f.id_referencia)===idCierre&&usuario!=null&&Number(f.id_usuario)===Number(usuario)&&Array.isArray(payload?.comprobantes)&&payload.comprobantes.every(x=>typeof x.codigo==='string'&&hex(x.hash)&&x.valor_total!==undefined)&&payload.activos_procesados!==undefined&&hex(payload.hash_cierre)&&iguales(codigos,codigosEvento);
      add(prueba('034_completado','Un COMPLETADO con referencia, ejecutor, comprobantes, activos y hash',f?.payload_truncado?'NO_CONCLUYENTE':completo?'APROBADO':'RECHAZADO',`cantidad ${completados.length}; referencia ${f?.id_referencia}; usuario ${f?.id_usuario}; ejecutor ${usuario}; códigos coinciden ${iguales(codigos,codigosEvento)}; truncado ${Boolean(f?.payload_truncado)}`));
      const publicados=[payload?.hash_cierre,cierre.data?.hash_cierre,ultimo?.hash_cierre];
      const a=publicados.every(hex)&&publicados.every(x=>x===publicados[0]);
      let hashEstado='NO_CONCLUYENTE',detalles=[];
      if(i?.payload_truncado||f?.payload_truncado)detalles.push({motivo:'payload_truncado'});
      else if(!a)hashEstado='RECHAZADO';
      else if(!Array.isArray(payload?.comprobantes)||!Array.isArray(payload?.excluidos))detalles.push({motivo:'payload_incompleto'});
      else{
        const objeto={periodo:220,comprobantes:payload.comprobantes,excluidos:payload.excluidos};
        const h=hashCanonico(objeto);if(h!==publicados[0])detalles.push({tipo:'cierre',texto_canonico:canon(objeto),calculado:h,publicado:publicados[0]});
        for(const x of posterior.comprobantes){const obj={codigo:x.codigo,fecha:x.fecha_comprobante,lineas:x.lineas};const h2=hashCanonico(obj);const esperado=payload.comprobantes.find(y=>y.codigo===x.codigo)?.hash;if(h2!==x.hash_integridad||h2!==esperado)detalles.push({tipo:'comprobante',codigo:sanear(x.codigo),texto_canonico:canon(sanear(obj)),calculado:h2,publicado:x.hash_integridad,publicado_evento:esperado});}
        if(!detalles.length)hashEstado='APROBADO';
      }
      add(prueba('034_hash_verificable','Tres hash publicados iguales; recálculo canónico de cierre y comprobantes',hashEstado,`publicados iguales ${a}; discrepancias de recálculo ${detalles.length}; truncado ${Boolean(i?.payload_truncado||f?.payload_truncado)}`,{detalle_hash:sanear(detalles)}));
      const hashes=hex(i?.hash_integridad)&&hex(f?.hash_integridad);
      add(prueba('034_hash_eventos','INICIADO y COMPLETADO con hash_integridad SHA-256 hexadecimal',hashes?'APROBADO':'RECHAZADO',`iniciado ${hex(i?.hash_integridad)}; completado ${hex(f?.hash_integridad)}`));
      const vars=eventos.filter(x=>x.tipo_evento==='VARIACION_REGISTRADA'&&x.payload_evento?.id_evento==null);
      const deps=eventos.filter(x=>x.tipo_evento==='DEPRECIACION_REGISTRADA');
      const refs=vars.every(x=>Number(x.payload_evento?.id_cierre)===idCierre)&&deps.every(x=>Number(x.id_referencia)===idCierre);
      add(prueba('034_referencias','Variaciones masivas y depreciaciones referencian id_cierre; al menos una',vars.length+deps.length===0?'NO_CONCLUYENTE':refs?'APROBADO':'RECHAZADO',`variaciones ${vars.length}; depreciaciones ${deps.length}; referencias correctas ${refs}`));
      r.casos[CASO].estado=veredicto(r.casos[CASO].comprobaciones);r.casos[CASO].motivo=r.casos[CASO].comprobaciones.filter(x=>x.estado===r.casos[CASO].estado).map(x=>x.id).join(', ');
      let n=0;for(const z of r.casos[CASO].comprobaciones.filter(x=>x.estado==='RECHAZADO')){n++;const faltaEvento=(z.id==='034_iniciado'&&iniciados.length===0)||(z.id==='034_completado'&&completados.length===0);r.incidencias.push({id:`INC-M06-G46-${String(n).padStart(2,'0')}`,casos:[CASO],esperado:z.esperado,obtenido:z.observado,evidencia:'resultado.json',severidad:faltaEvento?'ALTA':'MEDIA',justificacion_severidad:faltaEvento?'Falta un evento completo del cierre.':'Dato del evento o hashes publicados incoherentes.',certeza:'CONFIRMADA',equipo:'Desarrollo',fundamento:'Primera discrepancia comprobada por la API pública en TEST.',causa_raiz:'Por determinar.',accion:'Desarrollo revisa la discrepancia; QA decide reevaluación autorizada.'});}
      const complementos=[];for(const id of [7,219]){const p=porId(posterior.periodos,id),ev=await auditoria(id,'&tipo_evento=CIERRE_PERIODO_INICIADO&tipo_evento=CIERRE_PERIODO_COMPLETADO');complementos.push({periodo:id,id_cierre:p?.ultimo_cierre?.id_cierre,eventos:sanear(ev.filter(x=>Number(x.id_referencia)===Number(p?.ultimo_cierre?.id_cierre)).map(x=>({tipo_evento:x.tipo_evento,id_referencia:x.id_referencia,id_usuario:x.id_usuario,hash_presente:hex(x.hash_integridad),hash_cierre_coincide:x.payload_evento?.hash_cierre===p?.ultimo_cierre?.hash_cierre})))});}r.complementario=complementos;
      permitirNewman=true;
      const lanzar=local&&typeof opciones.hijo==='function'?opciones.hijo:(script,input,timeout)=>lanzarHijo({base:DIR,script,input,timeout,env:e,clean});
      const reporte=await lanzar('newman_hijo.mjs',{salida:path.join(c.dir,'newman'),coleccion:path.join(DIR,'G46.postman_collection.json'),environment:{values:[{key:'base_url',value:api},{key:'contador_token',value:token},{key:'run_id',value:c.runId},{key:'sandbox_secret',value:e.QA_SANDBOX_SECRET}]}},300000);
      r.herramientas.newman=reporte.data??{codigo:2};if(reporte.code||reporte.data?.codigo!==0||reporte.data?.fallos)r.problemas_tecnicos.push(`NEWMAN_${clean(reporte.error??reporte.code)}`);
    }
  }catch(err){r.problemas_tecnicos.push(clean(err.message));noConcluyente(clean(err.message));}
  finally{
    noConcluyente('Ejecución incompleta');
    r.casos[CASO].estado=veredicto(r.casos[CASO].comprobaciones);
    r.casos[CASO].motivo=r.casos[CASO].comprobaciones.filter(x=>x.estado===r.casos[CASO].estado).map(x=>x.id).join(', ');
    r.cierre={run:{cierre_http:null},rollback:r.rollback};
    if(token)try{const d=await req('DELETE',`/test-control/runs/${c.runId}`);r.cierre.run.cierre_http=d.http;if(d.http!==200)throw Error(`DELETE_${d.http}`);if(!basal)throw Error('BASES_NO_DISPONIBLES');const after=await estado(true),ids=after.periodos.map(x=>Number(x.id_periodo_contable)).sort((a,b)=>a-b);const auditAfter=await auditoria(220,'',true);const sinEvento=idCierre==null?true:!auditAfter.some(x=>Number(x.id_referencia)===idCierre);const costoIgual=iguales(costoRollback(after.activo.valoracion_costo),costoRollback(basal.activo.valoracion_costo));const ok=porId(after.periodos,220)?.estado==='ABIERTO'&&iguales(after.lineas,basal.lineas)&&iguales(after.comprobantes,basal.comprobantes)&&iguales(after.variaciones,basal.variaciones)&&iguales(ids,periodosIds)&&sinEvento&&costoIgual;r.rollback={verificado:ok,motivo:`220 ABIERTO ${porId(after.periodos,220)?.estado==='ABIERTO'}; líneas ${iguales(after.lineas,basal.lineas)}; comprobantes ${iguales(after.comprobantes,basal.comprobantes)}; variaciones ${iguales(after.variaciones,basal.variaciones)}; períodos ${iguales(ids,periodosIds)}; sin eventos del cierre ${sinEvento}; costo 1573 ${costoIgual}`};}catch(err){r.rollback={verificado:false,motivo:clean(err.message)};r.problemas_tecnicos.push(`ROLLBACK_${clean(err.message)}`);}
    r.cierre.rollback=r.rollback;r.total_solicitudes_api=solicitante.total()+(r.herramientas.newman?.solicitudes??0);r.duracion_segundos=Math.ceil((Date.now()-inicio)/1000);r.evidencias=listarEvidencias(c.dir).filter(x=>x.startsWith('newman/'));
    r.oficial=permitirNewman&&r.rollback.verificado&&r.cierre.run.cierre_http===200&&r.herramientas.newman?.codigo===0&&r.herramientas.newman?.fallos===0&&r.herramientas.newman?.reportes===true&&['newman/newman-G46.json','newman/newman-G46.html'].every(x=>r.evidencias.includes(x))&&r.problemas_tecnicos.length===0&&r.casos[CASO].comprobaciones.every(x=>['APROBADO','RECHAZADO'].includes(x.estado))&&r.total_solicitudes_api<=LIMITE.solicitudes_totales&&r.duracion_segundos<=LIMITE.segundos;
    r.consume_version=escrituras>0;r.clasificacion_fallo=clasificarFallo(r);r.sha256={ejecutor:sha256(path.join(DIR,'g46.mjs')),infraestructura:Object.fromEntries(['lib/infra.mjs','lib/contrato.mjs','lib/informe.mjs','pruebas/newman_hijo.mjs','pruebas/verificar.mjs'].map(x=>[x,sha256(path.join(DIR,x))]))};
    const forma=validarFormaResultado(r,CAPACIDADES,c.dir);if(forma.length){r.problemas_tecnicos.push(`RESULTADO_FORMA_${forma.join('_')}`);r.oficial=false;r.clasificacion_fallo='CONTRATO';}guardarResultado(c,r,informe);
  }
  return r;
}

if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url))try{if(process.argv.includes('--capacidades'))console.log(JSON.stringify(CAPACIDADES));else if(process.argv.includes('--comprobar'))process.exitCode=comprobar();else{const pruebaLocal=process.env.NODE_ENV==='test'&&process.argv.includes('--prueba-cli-local');const archivo=pruebaLocal?path.resolve(process.env.G46_PRUEBA_ENV_FILE??'.'):path.join(ROOT,'.env.qa');if(pruebaLocal&&!archivo.startsWith(path.resolve(os.tmpdir())+path.sep))throw Error('ENV_PRUEBA_FUERA_TEMPORAL');const c=contexto(process.argv.slice(2),pruebaLocal),e=leerEnv(process.env,archivo),p=preflight(c,e);fs.writeFileSync(path.join(c.dir,'preflight.json'),JSON.stringify(p,null,2));if(!p.ok){console.error(`PREFLIGHT_${p.barreras.join('_')}`);process.exitCode=2;}else{const r=await ejecutar(c,e);console.log(JSON.stringify({grupo:'G46',oficial:r.oficial,estado:r.casos[CASO].estado,solicitudes:r.total_solicitudes_api}));}}}catch(err){console.error(clean(err.message));process.exitCode=2;}
