import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {CASOS,LIMITE,hoyBogota,porId,ids,iguales,evaluar,criterio,listaFaltantes,rolEnMensaje,fechaEnMensaje,horaEnMensaje} from './lib/g44_core.mjs';
import {contrato,validarLecturas,validarError,esquema} from './lib/contrato.mjs';
import {informe} from './lib/informe.mjs';
import {sha256,clasificarFallo,validarFormaResultado,crearSolicitante,lanzarHijo,listarEvidencias,guardarResultado,contexto as contextoInfra,leerEnv as leerEnvInfra,preflight as preflightInfra} from './lib/infra.mjs';

const DIR=path.dirname(fileURLToPath(import.meta.url));
const ROOT=path.resolve(DIR,'../../../../..');
const API='https://www.api.inmero.co/api-sgpmp-test';
const FRONT='https://api.inmero.co/sigab-test';
const archivos=['g44.mjs','lib/g44_core.mjs','lib/infra.mjs','lib/contrato.mjs','lib/informe.mjs','pruebas/contrato_g44.json','pruebas/escenarios_g44.json','G44.postman_collection.json','pruebas/newman_hijo.mjs','pruebas/simulador_base.mjs','pruebas/verificar.mjs','pruebas/g44_escenarios.test.mjs','pruebas/g44_cli.test.mjs','pruebas/g44_dto.test.py','README.md'];
const clean=x=>String(x??'').replace(/eyJ[\w-]+\.[\w-]+\.[\w-]+|[\w.+-]+@[\w.-]+/g,'[RESERVADO]').slice(0,240);
const guardar=(p,v)=>fs.writeFileSync(p,JSON.stringify(v,null,2));
const caso=n=>`TC-M06-${n}`;
const obs=(id,z,extra='')=>`${id}: HTTP ${z?.http??'sin respuesta'}, error ${clean(z?.data?.error_code??'ausente')}, mensaje ${clean(z?.data?.message??'ausente')}${extra}`;
export const CAPACIDADES={contrato:'sigab-qa-ejecutor/1',grupo:'G44',casos:CASOS,operaciones:['evaluar','reintentar','reevaluar'],versiones:{min:1,max:99},comprobaciones_obligatorias:{'TC-M06-028':{API:['028_a','028_b','028_c']},'TC-M06-029':{API:['029_acceso','029_mensaje','029_admin']},'TC-M06-030':{API:['030_cerrado','030_concurrencia','030_sin_segundo']}},limite:LIMITE,baja_automatizada:true};
export function comprobar(){
  const faltan=archivos.filter(x=>!fs.existsSync(path.join(DIR,x)));
  let col=null;try{col=JSON.parse(fs.readFileSync(path.join(DIR,'G44.postman_collection.json')));}catch{}
  const superior=fs.existsSync(path.join(DIR,'Resultados'))&&fs.readdirSync(path.join(DIR,'Resultados')).some(x=>x.endsWith('.md'));
  const imports=fs.readFileSync(path.join(DIR,'g44.mjs'),'utf8').match(/from ['"]([^'"]+)['"]/g)??[];
  const ok=!faltan.length&&col?.item?.length>=4&&contrato.rutas.every(x=>x.cita?.startsWith('src/'))&&!superior&&imports.every(x=>!x.includes('../TC-M06-'));
  console.log(JSON.stringify({grupo:'G44',ok,faltan,items:col?.item?.length??0,sha256:Object.fromEntries(archivos.filter(x=>fs.existsSync(path.join(DIR,x))).map(x=>[x,sha256(path.join(DIR,x))]))}));
  return ok?0:2;
}
export const contexto=(a,prueba=false)=>contextoInfra(a,{capacidades:CAPACIDADES,grupo:'G44',casos:CASOS,dir:DIR,prueba});
export const leerEnv=(p=process.env,archivo=path.join(ROOT,'.env.qa'))=>leerEnvInfra(p,archivo);
export const preflight=(c,e=process.env)=>{
  const p=preflightInfra(c,e,{grupo:'G44',api:API,front:FRONT,efectos:['Cuatro logins','DELETE de asignaciones 34 y 49','Un costo MANO_OBRA_PROPIA sobre 1569 en 220','POST restauración matriz MANO_OBRA_PROPIA','PUT titular finca 466','POST cierre 7, 219, 8 dos veces, 220 cinco veces y 260 una vez','DELETE del RUN y lecturas sin cabeceras']});
  p.barreras.push(...['QA_ADMIN_EMAIL','QA_ADMIN_PASSWORD','QA_PROD_EMAIL','QA_PROD_PASSWORD','QA_VETERINARIO_EMAIL','QA_VETERINARIO_PASSWORD'].filter(k=>!String(e[k]??'').trim()));
  p.ok=p.barreras.length===0;return p;
};

export async function ejecutar(c,e=process.env,opciones={}){
  const local=opciones.ensayo===true&&/^http:\/\/127\.0\.0\.1:\d+\/api$/.test(opciones.api??'');
  const api=local?opciones.api:API;
  const pf=local?{ok:true,barreras:[],efectos:preflight(c,e).efectos}:preflight(c,e);
  if(!pf.ok)throw Error(`PREFLIGHT_${pf.barreras.join('_')}`);
  const r={grupo:'G44',rf:'RF-87',run_id:c.runId,version:c.version,autorizacion_referencia:c.ref,casos:Object.fromEntries(CASOS.map(k=>[k,{estado:'NO_CONCLUYENTE',motivo:'No ejecutado',comprobaciones:[]}])),preflight:pf,solicitudes:[],comprobaciones:[],precios:[],activos:[],lineas:[],incidencias:[],evidencias:[],problemas_tecnicos:[],cypress:{paneles:{},total_pruebas:0},rollback:{verificado:false},herramientas:{node:process.version},oficial:false,consume_version:false};
  let token=null,escrituras=false,bases=new Map(),periodosBase=[],titularBase=null,costoNuevo=null,permitirNewman=false;
  const tokens={};const inicio=Date.now();
  const solicitante=crearSolicitante({api,runId:c.runId,secret:e.QA_SANDBOX_SECRET,limite:LIMITE,solicitudes:r.solicitudes,esquema,validarLecturas,validarError,clean,id:n=>`G44-${String(n).padStart(3,'0')}`,token:()=>token,inicio});
  const req=solicitante.req;
  const usar=rol=>{token=tokens[rol];};
  const get=async(ruta,sinRun=false)=>{const z=await req('GET',ruta,undefined,sinRun);if(z.http!==200)throw Error(`GET_${z.http}_${ruta}`);return z.data;};
  const periodos=(sinRun=false)=>get('/finanzas/periodos',sinRun);
  const pre=(id,sinRun=false)=>get(`/finanzas/periodos/${id}/prevalidacion`,sinRun);
  const cierre=async(id,criterio)=>{
    const z=await req('POST',`/finanzas/periodos/${id}/cierre`,{});
    // Se conserva el cuerpo íntegro de la respuesta, saneando campos sensibles.
    const sanear=(x)=>Array.isArray(x)?x.map(sanear):x&&typeof x==='object'?Object.fromEntries(Object.entries(x).map(([k,v])=>[k,/token|password|contrasena|cookie|secret|jwt|serial|identificador|numero_id_tributaria/i.test(k)?'[RESERVADO]':sanear(v)])):typeof x==='string'?x.replace(/eyJ[\w-]+\.[\w-]+\.[\w-]+|[\w.+-]+@[\w.-]+/g,'[RESERVADO]'):x;
    r.respuestas_cierre??={};r.respuestas_cierre[criterio]={periodo:id,http:z.http,cuerpo:sanear(z.data)};
    if(z.http===200){
      r.respuestas_cierre[criterio].comprobantes=sanear(await get(`/finanzas/periodos/${id}/comprobantes`));
      r.respuestas_cierre[criterio].lineas=sanear(await get(`/finanzas/lineas?id_periodo_contable=${id}`));
    }
    return z;
  };
  const estado=async(id,sinRun=false)=>{
    const ps=await periodos(sinRun),p=porId(ps,id);
    const lineas=await get(`/finanzas/lineas?id_periodo_contable=${id}`,sinRun);
    const comprobantes=await get(`/finanzas/periodos/${id}/comprobantes`,sinRun);
    const variaciones=await get(`/finanzas/periodos/${id}/variaciones`,sinRun);
    return{estado:p?.estado,fecha_cierre:p?.fecha_cierre??null,ultimo_cierre_id:p?.ultimo_cierre?.id_cierre??null,lineas:ids(lineas),comprobantes:ids(comprobantes),variaciones:ids(variaciones)};
  };
  const marca=(id,esperado,cumple,observado,noConcluyente=false)=>criterio(id,esperado,cumple,observado,noConcluyente);
  const sinArtefactos=(id,s)=>s.estado==='ABIERTO'&&iguales(s.comprobantes,bases.get(id).comprobantes)&&iguales(s.variaciones,bases.get(id).variaciones);
  const apiCriterios={'TC-M06-028':[],'TC-M06-029':[],'TC-M06-030':[]};
  const incidente=(numero,clave,esperado,obtenido,impacto,severidad,relacion='')=>r.incidencias.push({id:`INC-M06-G44-${clave}`,casos:[caso(numero)],esperado,obtenido,evidencia:'resultado.json',impacto,severidad,justificacion_severidad:severidad==='ALTA'?'La discrepancia bloquea un control relevante del cierre sin alternativa demostrada.':'La discrepancia afecta parcialmente el control o la explicación al usuario.',certeza:'CONFIRMADA',equipo:'Desarrollo',fundamento:'Primera discrepancia comprobada en la API pública de cierre.',hipotesis:'Causa raíz por determinar.',accion:'Desarrollo revisa el comportamiento y QA repite en RUN autorizado.',relacion});
  try{
    // Autenticación previa al RUN lógico: una solicitud por usuario, sin reintento.
    for(const [rol,prefijo] of [['contador','QA_CONTADOR'],['admin','QA_ADMIN'],['veterinario','QA_VETERINARIO'],['productor','QA_PROD']]){
      const z=await req('POST','/sesiones/',{correo_electronico:e[`${prefijo}_EMAIL`],contrasena:e[`${prefijo}_PASSWORD`]},true);
      if(z.http!==200||!z.data?.token)throw Error(`LOGIN_${rol.toUpperCase()}`);
      tokens[rol]=z.data.token;
    }
    const permisos={};for(const rol of Object.keys(tokens)){usar(rol);permisos[rol]=(await get('/sesiones/me/permisos')).permisos.map(p=>[p.nombre_recurso,Number(p.id_accion)]);}
    const tiene=(rol,recurso,accion)=>permisos[rol].some(([n,a])=>n===recurso&&a===accion);
    if(!tiene('contador','cierre_periodo',5)||!tiene('contador','cierre_periodo',2)||!tiene('contador','configuracion_contable',3)||!tiene('contador','costos_activos',1)||!tiene('admin','fincas',3)||!tiene('admin','cierre_periodo',2)||['admin','veterinario','productor'].some(x=>tiene(x,'cierre_periodo',5)))throw Error('PERMISOS_NO_COINCIDEN');
    usar('contador');const activos=await get('/finanzas/activos');const ps=await periodos();periodosBase=ps.map(x=>Number(x.id_periodo_contable));
    const cfg=await get('/finanzas/configuracion');const m34=cfg.matriz.find(x=>Number(x.id_asignacion_cuenta_contable)===34),m49=cfg.matriz.find(x=>Number(x.id_asignacion_cuenta_contable)===49);
    const asignacion=(m,tipo,debito,credito)=>m&&m.tipo_hecho===tipo&&m.sentido==='UNICO'&&m.id_especie===null&&m.subtipo_costo===null&&m.cuenta_debito===debito&&m.cuenta_credito===credito;
    const p8=await pre(8),p220=await pre(220),p260=await pre(260);
    for(const id of [7,8,219,220,260])bases.set(id,await estado(id));
    usar('admin');titularBase=await get('/configuracion/fincas/466/titular');
    const titular467=await get('/configuracion/fincas/467/titular');
    const checks=[];
    const check=(requisito,esperado,observado,cumple,bloqueante=true)=>checks.push({requisito,esperado,observado,cumple:Boolean(cumple),bloqueante});
    for(const [id,esperado] of [[7,'CERRADO'],[8,'ABIERTO'],[219,'CERRADO'],[220,'ABIERTO'],[260,'ABIERTO']])check(`periodo_${id}_estado`,esperado,bases.get(id).estado,bases.get(id).estado===esperado);
    const nits=[219,260].map(id=>porId(ps,id)?.numero_id_tributaria??null);
    check('periodo_260_mismo_nit_219','NIT-B en ambos',nits.join(' / '),nits[0]!=null&&nits[0]===nits[1]);
    check('linea_17_prevalidacion_8','id_linea 17',p8.lineas_sin_trazabilidad.map(x=>Number(x.id_linea)),p8.lineas_sin_trazabilidad.some(x=>Number(x.id_linea)===17));
    for(const [id,p] of [[220,p220],[260,p260]])check(`prevalidacion_${id}_sin_bloqueos`,'[]',p.bloqueos.map(x=>x.codigo),p.bloqueos.length===0);
    for(const [id,t] of [[466,titularBase],[467,titular467]])check(`titular_${id}_completo`,'cuatro campos tributarios completos',Object.fromEntries(['tipo_id_tributaria','numero_id_tributaria','dv','razon_social'].map(k=>[k,Boolean(t[k])])),['tipo_id_tributaria','numero_id_tributaria','dv','razon_social'].every(k=>Boolean(t[k])));
    check('matriz_34_generica_activa','MANO_OBRA_PROPIA/UNICO 158405/250505',Boolean(asignacion(m34,'MANO_OBRA_PROPIA','158405','250505')),Boolean(asignacion(m34,'MANO_OBRA_PROPIA','158405','250505')));
    check('matriz_49_generica_activa','DEPRECIACION_ACTIVO_COSTO/UNICO 516005/159205',Boolean(asignacion(m49,'DEPRECIACION_ACTIVO_COSTO','516005','159205')),Boolean(asignacion(m49,'DEPRECIACION_ACTIVO_COSTO','516005','159205')));
    for(const id of [1572,1573]){
      const activo=activos.find(x=>Number(x.id_activo_biologico)===id);
      check(`activo_${id}_valorado_por_costo`,'valorado_por_costo === true y vida_util_meses > 0',activo?{valorado_por_costo:activo.valorado_por_costo,vida_util_meses:activo.vida_util_meses}:null,Boolean(activo&&activo.valorado_por_costo===true&&activo.vida_util_meses>0),false);
    }
    r.activos_por_costo_467=activos.filter(x=>x.id_finca===467&&x.valorado_por_costo===true&&x.vida_util_meses>0).map(x=>x.id_activo_biologico);
    check('finca_467_activo_por_costo','Al menos un activo de finca 467 valorado por costo con vida útil > 0',r.activos_por_costo_467,r.activos_por_costo_467.length>0);
    r.preflight_datos=checks;
    const fallidos=checks.filter(x=>x.bloqueante&&!x.cumple).map(x=>x.requisito);
    if(fallidos.length)throw Error(`PREFLIGHT_DATOS_NO_CONCLUYENTE_${fallidos.join('_')}`);
    // 029: cada rol se observa por separado; también se verifica que 220 permanezca intacto.
    const acceso=[],mensajes=[];
    for(const [rol,etiqueta] of [['admin','Administrador'],['veterinario','Veterinario'],['productor','Productor']]){
      usar(rol);const z=await cierre(220,`029_${rol}`);usar('contador');const s=await estado(220);
      acceso.push(z.http===403&&iguales(s,bases.get(220)));
      mensajes.push(z.http===403&&String(z.data?.message??'').includes('Acceso denegado: El proceso de cierre del periodo contable es competencia exclusiva del Contador del sistema')&&rolEnMensaje(z.data?.message,etiqueta));
      r[`observado_029_${rol}`]=obs(`029.${rol}`,z,`; sin cambios ${iguales(s,bases.get(220))}; rol en mensaje ${rolEnMensaje(z.data?.message,etiqueta)}`);
    }
    usar('admin');const adminP=await req('GET','/finanzas/periodos');const adminPre=await req('GET','/finanzas/periodos/220/prevalidacion');
    apiCriterios[caso('029')].push(marca('029_acceso','403 y 220 sin cambios para tres roles',acceso.every(Boolean),`029.acceso: ${acceso.join(',')}`),marca('029_mensaje','FA-4 y rol explícito para cada 403',mensajes.every(Boolean),`029.mensaje: ${mensajes.join(',')}`),marca('029_admin','Administrador consulta estado y prevalidación con 200',adminP.http===200&&adminPre.http===200,`029.admin: HTTP ${adminP.http}/${adminPre.http}`));
    usar('contador');const ej7=porId(await periodos(),7)?.ultimo_cierre?.id_usuario_ejecutor??null;const z7=await cierre(7,'030_cerrado'),s7=await estado(7);
    const cerrado=z7.http===409&&String(z7.data?.message??'').includes('Periodo inmutable')&&fechaEnMensaje(z7.data?.message)&&/Contador/i.test(String(z7.data?.message??''))&&ej7!=null&&new RegExp('\\b'+ej7+'\\b').test(String(z7.data?.message??''))&&iguales(s7,bases.get(7));
    apiCriterios[caso('030')].push(marca('030_cerrado','409 Periodo inmutable con fecha y Contador ejecutor; 7 CERRADO',cerrado,obs('030_cerrado',z7,`; 7 sin cambios ${iguales(s7,bases.get(7))}`)));
    const ej219=porId(await periodos(),219)?.ultimo_cierre?.id_usuario_ejecutor??null;const z219=await cierre(219,'030_cerrado_219'),s219=await estado(219);
    r.observacion_030_219=obs('030_cerrado_219',z219,`; 219 sin cambios ${iguales(s219,bases.get(219))}; ejecutor ${ej219}`);r.observaciones=[...(r.observaciones??[]),r.observacion_030_219];
    const primero=await cierre(8,'030_primero'),segundo=await cierre(8,'030_segundo'),s8=await estado(8);
    const concurrencia=primero.http===409&&primero.data?.error_code==='EXCLUSION_REQUIERE_AUTORIZACION'&&segundo.http===409&&/Conflicto de concurrencia/i.test(String(segundo.data?.message??''))&&horaEnMensaje(segundo.data?.message)&&/usuario/i.test(String(segundo.data?.message??''))&&/\b\d+\b/.test(String(segundo.data?.message??''));
    const sinSegundo=sinArtefactos(8,s8)&&iguales(s8.lineas,bases.get(8).lineas);
    apiCriterios[caso('030')].push(marca('030_concurrencia','Segundo 409 de concurrencia con hora y usuario del primero',concurrencia,obs('030_concurrencia',segundo,`; primero ${obs('030.primero',primero)}`)),marca('030_sin_segundo','8 ABIERTO sin segundo cierre ni comprobantes nuevos',sinSegundo,`030.sin_segundo: estado ${s8.estado}; comprobantes ${s8.comprobantes.length}; líneas ${s8.lineas.length}`));
    // 028-a: costo del mes actual en NIT-C, periodo 220.
    const del34=await req('DELETE','/finanzas/configuracion/matriz/34');if(del34.http!==204)throw Error(`MATRIZ_34_DELETE_${del34.http}`);escrituras=true;
    const costo=await req('POST','/finanzas/costos',{subtipo_costo:'MANO_OBRA',origen_costo:'MANO_OBRA_PROPIA',monto_costo:'103.00',fecha_costo:hoyBogota(),id_activo_biologico:1569,naturaleza_costo:'MANTENIMIENTO'});
    if(costo.http!==201||!Array.isArray(costo.data?.registros)||costo.data.registros.length!==1)throw Error(`COSTO_POST_${costo.http}`);
    costoNuevo=Number(costo.data.registros[0].id_registro_costo);
    const lineas220=await get('/finanzas/lineas?id_periodo_contable=220');const p220a=await pre(220);const z220a=await cierre(220,'028_a'),s220a=await estado(220);
    const lineaPendiente=lineas220.some(x=>x.estado==='PENDIENTE_CUENTA'&&x.tipo_hecho==='MANO_OBRA_PROPIA'&&Number(x.id_activo_biologico)===1569);
    const a=lineaPendiente&&p220a.bloqueos.some(x=>x.codigo==='LINEAS_PENDIENTE_CUENTA'&&/mano|obra|costo/i.test(x.mensaje??''))&&z220a.http!==200&&listaFaltantes(z220a,/cuenta|matriz|mano|obra/i)&&sinArtefactos(220,s220a);
    apiCriterios[caso('028')].push(marca('028_a','PENDIENTE_CUENTA y lista de faltantes; 220 ABIERTO sin cierre',a,obs('028_a',z220a,`; linea pendiente ${lineaPendiente}; bloqueo ${p220a.bloqueos.map(x=>x.codigo).join(',')}; estado ${s220a.estado}`)));
    const restaurar=await req('POST','/finanzas/configuracion/matriz',{tipo_hecho:'MANO_OBRA_PROPIA',sentido:'UNICO',id_especie:null,subtipo_costo:null,cuenta_debito:'158405',cuenta_credito:'250505'});
    if(restaurar.http!==201&&restaurar.http!==200)throw Error(`MATRIZ_34_RESTAURAR_${restaurar.http}`);
    const lineasLimpias=await get('/finanzas/lineas?id_periodo_contable=220');const preLimpia=await pre(220);
    const limpio=s220a.estado==='ABIERTO'&&!lineasLimpias.some(x=>x.tipo_hecho==='MANO_OBRA_PROPIA'&&Number(x.id_activo_biologico)===1569&&x.estado==='PENDIENTE_CUENTA')&&preLimpia.bloqueos.length===0;
    let b=false,z220b=null;
    if(!limpio)apiCriterios[caso('028')].push(marca('028_b','Matriz incompleta informada; 220 ABIERTO sin cierre',false,`028_b: NO_CONCLUYENTE; restauracion no limpio 220; bloqueos ${preLimpia.bloqueos.map(x=>x.codigo).join(',')}`,true));
    else{
      const del49=await req('DELETE','/finanzas/configuracion/matriz/49');if(del49.http!==204)throw Error(`MATRIZ_49_DELETE_${del49.http}`);
      z220b=await cierre(220,'028_b');const s220b=await estado(220);
      b=z220b.http!==200&&listaFaltantes(z220b,/depreciaci.n|DEPRECIACION_ACTIVO_COSTO|cuenta.*matriz/i)&&sinArtefactos(220,s220b);
      apiCriterios[caso('028')].push(marca('028_b','Matriz incompleta informada; 220 ABIERTO sin cierre',b,obs('028_b',z220b,`; estado ${s220b.estado}`)));
    }
    // 028-c es independiente del resultado de 220 y usa 260.
    let put=null,c028=false,z260c=null;
    usar('admin');put=await req('PUT','/configuracion/fincas/466/titular',{tipo_id_tributaria:null,numero_id_tributaria:null,dv:null,razon_social:null});usar('contador');
    if(put.http>=400&&put.http<500)apiCriterios[caso('028')].push(marca('028_c','Finca sin titular informada; 260 ABIERTO sin cierre',false,obs('028_c_put',put),true));
    else{if(put.http!==200)throw Error(`TITULAR_PUT_${put.http}`);const preC=await pre(260);z260c=await cierre(260,'028_c');const s260c=await estado(260);c028=z260c.http!==200&&listaFaltantes(z260c,/finca.*titular|titular.*finca/i)&&sinArtefactos(260,s260c);apiCriterios[caso('028')].push(marca('028_c','Finca sin titular informada; 260 ABIERTO sin cierre',c028,obs('028_c',z260c,`; prevalidacion ${preC.bloqueos.map(x=>x.codigo).join(',')}; estado ${s260c.estado}`)));}
    for(const [numero,criterios] of Object.entries(apiCriterios)){r.casos[numero]=evaluar({[numero]:criterios})[numero];for(const q of r.casos[numero].comprobaciones)r.comprobaciones.push({caso:numero,id:q.id,fuente:'API',tipo:'ASSERT',estado:q.estado,evidencia:'resultado.json'});}
    if(r.casos[caso('029')].estado==='RECHAZADO')incidente('029','01','403 FA-4 con rol y sin cambios',r.observado_029_admin,'Control de acceso o explicación al rol incorrectos.','MEDIA');
    if(!cerrado)incidente('030','02','409 Periodo inmutable con fecha y ejecutor',obs('030_cerrado',z7),'El 409 omite información de auditoría requerida.','MEDIA');
    if(!concurrencia||!sinSegundo)incidente('030','03','Segundo cierre rechazado por concurrencia con hora y usuario',obs('030_concurrencia',segundo),'El estado de cierre activo no se representa como exige RF-87.','MEDIA','INC-M06-G43-01');
    if(!a)incidente('028','04','Bloqueo por PENDIENTE_CUENTA con lista',obs('028_a',z220a),'Cierre con cuenta faltante sin explicación suficiente.','ALTA');
    if(z220b&&!b)incidente('028','05','Bloqueo por matriz incompleta con lista',obs('028_b',z220b),'Cierre con depreciación sin cuenta no informado como exige RF-87.','ALTA');
    if(put?.http===200&&!c028)incidente('028','06','Bloqueo por finca sin titular',obs('028_c',z260c),'Cierre puede completarse o fallar sin informar titular ausente.','ALTA');
    const previasV1=[['INC-M06-G44-01','029','403 sin mensaje FA-4 ni rol'],['INC-M06-G44-02','030','409 de período CERRADO sin Periodo inmutable ni ejecutor'],['INC-M06-G44-03','030','segundo POST en EN_CIERRE sin 409 de concurrencia (relacionada con INC-M06-G43-01)'],['INC-M06-G44-05','028','cierre completado con la matriz de depreciación incompleta']];
    const actuales=new Set(r.incidencias.map(x=>x.id));
    r.seguimiento_incidencias_v1=previasV1.map(([id,c,desc])=>({id,caso:caso(c),descripcion_v1:desc,estado_v2:actuales.has(id)?'REPRODUCIDA':'NO_REPRODUCIDA'}));
    r.seguimiento_incidencias_v1.push({id:'INC-M06-G44-06',caso:caso('028'),descripcion_v1:'finca sin titular; retirada en V1 porque 028-c no se evaluó',estado_v2:actuales.has('INC-M06-G44-06')?'NUEVA_CONFIRMADA_EN_V2':'NO_CONFIRMADA_EN_V2'});
    r.observaciones=[...(r.observaciones??[]),...r.seguimiento_incidencias_v1.map(x=>`Incidencia de V1 ${x.id} (${x.caso}): ${x.estado_v2}.`),...r.incidencias.filter(x=>!previasV1.some(([id])=>id===x.id)&&x.id!=='INC-M06-G44-06').map(x=>`${x.id} (${x.casos.join(',')}): nueva en V2.`)];
    permitirNewman=CASOS.every(x=>['APROBADO','RECHAZADO'].includes(r.casos[x].estado)&&r.casos[x].comprobaciones.every(q=>q.estado!=='NO_CONCLUYENTE'));
    if(permitirNewman){const lanzar=local&&typeof opciones.hijo==='function'?opciones.hijo:(script,input,timeout)=>lanzarHijo({base:DIR,script,input,timeout,env:e,clean});const n=await lanzar('newman_hijo.mjs',{salida:path.join(c.dir,'newman'),coleccion:path.join(DIR,'G44.postman_collection.json'),environment:{values:[{key:'base_url',value:api},{key:'contador_token',value:tokens.contador},{key:'run_id',value:c.runId},{key:'sandbox_secret',value:e.QA_SANDBOX_SECRET}]}},300000);r.herramientas.newman=n.data??{codigo:2};if(n.code||n.data?.codigo!==0)r.problemas_tecnicos.push(`NEWMAN_${clean(n.error??n.code)}`);}
  }catch(err){r.problemas_tecnicos.push(clean(err.message));for(const numero of CASOS)if(r.casos[numero].motivo==='No ejecutado')r.casos[numero]={estado:'NO_CONCLUYENTE',motivo:clean(err.message),comprobaciones:[]};}
  finally{
    r.cierre={run:{cierre_http:null},rollback:r.rollback};
    if(Object.keys(tokens).length){try{
      usar('contador');const d=await req('DELETE',`/test-control/runs/${c.runId}`);r.cierre.run.cierre_http=d.http;if(d.http!==200)throw Error(`DELETE_${d.http}`);
      const despues=[];for(const id of [7,8,219,220,260])despues.push(await estado(id,true));
      const ps=await periodos(true),cfg=await get('/finanzas/configuracion',true),costos=await get('/finanzas/costos?id_periodo_contable=220',true);
      usar('admin');const titular=await get('/configuracion/fincas/466/titular',true);
      const matriz=[34,49].every(id=>cfg.matriz.some(x=>Number(x.id_asignacion_cuenta_contable)===id));
      const costoAusente=!costos.some(x=>Number(x.id_registro_costo)===costoNuevo);
      const titularIgual=titularBase&&['tipo_id_tributaria','numero_id_tributaria','dv','razon_social'].every(k=>titular[k]===titularBase[k]);
      const periodosIguales=iguales(ps.map(x=>Number(x.id_periodo_contable)).sort((a,b)=>a-b),[...periodosBase].sort((a,b)=>a-b));
      const basesIguales=[7,8,219,220,260].every((id,i)=>iguales(despues[i],bases.get(id)));
      r.rollback={verificado:Boolean(matriz&&costoAusente&&titularIgual&&periodosIguales&&basesIguales),motivo:`Lecturas poscierre sin cabeceras: matriz ${matriz}; costo ausente ${costoAusente}; titular ${titularIgual}; periodos ${periodosIguales}; líneas y artefactos ${basesIguales}`};
    }catch(err){r.rollback={verificado:false,motivo:clean(err.message)};r.problemas_tecnicos.push(`ROLLBACK_${clean(err.message)}`);}}
    r.cierre.rollback=r.rollback;
    r.total_solicitudes_api=solicitante.total()+(r.herramientas.newman?.solicitudes??0);
    r.duracion_segundos=Math.ceil((Date.now()-inicio)/1000);
    r.herramientas.cypress={codigo:0,totalTests:0};r.cypress.total_pruebas=0;r.cypress.codigo=0;r.cypress.aprobadas=0;r.cypress.fallidas=0;
    r.evidencias=listarEvidencias(c.dir).filter(x=>x.startsWith('newman/'));
    r.oficial=permitirNewman&&r.rollback.verificado&&r.cierre.run.cierre_http===200&&r.herramientas.newman?.codigo===0&&r.herramientas.newman?.fallos===0&&r.herramientas.newman?.reportes===true&&['newman/newman-G44.json','newman/newman-G44.html'].every(x=>r.evidencias.includes(x))&&r.problemas_tecnicos.length===0&&r.total_solicitudes_api<=200&&r.duracion_segundos<=1800;
    r.consume_version=escrituras;
    r.clasificacion_fallo=clasificarFallo(r);
    r.sha256={ejecutor:sha256(path.join(DIR,'g44.mjs')),infraestructura:Object.fromEntries(['lib/infra.mjs','lib/contrato.mjs','lib/informe.mjs','pruebas/newman_hijo.mjs','pruebas/simulador_base.mjs','pruebas/verificar.mjs'].map(x=>[x,sha256(path.join(DIR,x))]))};
    const forma=validarFormaResultado(r,CAPACIDADES,c.dir);if(forma.length){r.problemas_tecnicos.push(`RESULTADO_FORMA_${forma.join('_')}`);r.oficial=false;r.clasificacion_fallo='CONTRATO';}
    guardarResultado(c,r,informe);
  }
  return r;
}

if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
  try{if(process.argv.includes('--capacidades'))console.log(JSON.stringify(CAPACIDADES));
    else if(process.argv.includes('--comprobar'))process.exitCode=comprobar();
    else{const prueba=process.env.NODE_ENV==='test'&&process.argv.includes('--prueba-cli-local');const archivo=prueba?path.resolve(process.env.G44_PRUEBA_ENV_FILE??'.'):path.join(ROOT,'.env.qa');if(prueba&&!archivo.startsWith(path.resolve(os.tmpdir())+path.sep))throw Error('ENV_PRUEBA_FUERA_TEMPORAL');const c=contexto(process.argv.slice(2),prueba),e=leerEnv(process.env,archivo),p=preflight(c,e);guardar(path.join(c.dir,'preflight.json'),p);if(!p.ok){console.error(`PREFLIGHT_${p.barreras.join('_')}`);process.exitCode=2;}else{const r=await ejecutar(c,e);console.log(JSON.stringify({grupo:'G44',oficial:r.oficial,estados:Object.fromEntries(CASOS.map(k=>[k,r.casos[k].estado])),solicitudes:r.total_solicitudes_api}));}}
  }catch(err){console.error(clean(err.message));process.exitCode=2;}
}
