import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {CASOS,LIMITE,hoyBogota,porId,ids,iguales,evaluar,criterio,listaFaltantes,rolEnMensaje,contiene,horaBogota,fechaBogota} from './lib/g44_core.mjs';
import {contrato,validarLecturas,validarError,esquema} from './lib/contrato.mjs';
import {informe} from './lib/informe.mjs';
import {sha256,clasificarFallo,validarFormaResultado,crearSolicitante,lanzarHijo,listarEvidencias,guardarResultado,contexto as contextoInfra,leerEnv as leerEnvInfra,preflight as preflightInfra} from './lib/infra.mjs';

const DIR=path.dirname(fileURLToPath(import.meta.url));
const ROOT=path.resolve(DIR,'../../../../..');
const API='https://www.api.inmero.co/api-sgpmp-test';
const FRONT='https://api.inmero.co/sigab-test';
const archivos=['g44.mjs','lib/g44_core.mjs','lib/infra.mjs','lib/contrato.mjs','lib/informe.mjs','pruebas/contrato_g44.json','pruebas/escenarios_g44.json','G44.postman_collection.json','pruebas/newman_hijo.mjs','pruebas/simulador_base.mjs','pruebas/verificar.mjs','pruebas/g44_escenarios.test.mjs','pruebas/g44_cli.test.mjs','pruebas/g44_dto.test.py','README.md'];
let nombresPrivados=new Set(),nitsPrivados=new Set();
const clean=x=>{let s=String(x??'').replace(/eyJ[\w-]+\.[\w-]+\.[\w-]+|[\w.+-]+@[\w.-]+/g,'[RESERVADO]');for(const n of nombresPrivados)if(n)s=s.replaceAll(n,'nombre del ejecutor presente');for(const n of nitsPrivados)if(n)s=s.replaceAll(n,'[RESERVADO]');return s.slice(0,500);};
const guardar=(p,v)=>fs.writeFileSync(p,JSON.stringify(v,null,2));
const caso=n=>`TC-M06-${n}`;
const obs=(id,z,extra='')=>`${id}: HTTP ${z?.http??'sin respuesta'}, error ${clean(z?.data?.error_code??'ausente')}, mensaje ${clean(z?.data?.message??'ausente')}${extra}`;
export const CAPACIDADES={contrato:'sigab-qa-ejecutor/1',grupo:'G44',casos:CASOS,operaciones:['evaluar','reintentar','reevaluar'],versiones:{min:3,max:3},comprobaciones_obligatorias:{'TC-M06-028':{API:['028_a','028_b','028_c']},'TC-M06-029':{API:['029_acceso','029_mensaje','029_admin']},'TC-M06-030':{API:['030_cerrado','030_concurrencia','030_sin_segundo']}},limite:LIMITE,baja_automatizada:true};
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
  const p=preflightInfra(c,e,{grupo:'G44',api:API,front:FRONT,efectos:['Cuatro logins','Cancelación del cierre 67 y del cierre creado en 8','DELETE y restauración de asignaciones 34 y 49','Un costo MANO_OBRA_PROPIA en 220','PUT y restauración de titular finca 467','POST de cierre 7, 219, 8 dos veces, 220 y 260','DELETE del RUN y lecturas sin cabeceras']});
  p.barreras.push(...['QA_ADMIN_EMAIL','QA_ADMIN_PASSWORD','QA_PROD_EMAIL','QA_PROD_PASSWORD','QA_VETERINARIO_EMAIL','QA_VETERINARIO_PASSWORD'].filter(k=>!String(e[k]??'').trim()));
  p.ok=p.barreras.length===0;return p;
};

export async function ejecutar(c,e=process.env,opciones={}){
  if(c.version!==3)throw Error('VERSION_3_REQUERIDA');
  const local=opciones.ensayo===true&&/^http:\/\/127\.0\.0\.1:\d+\/api$/.test(opciones.api??'');
  const api=local?opciones.api:API;
  const pf=local?{ok:true,barreras:[],efectos:preflight(c,e).efectos}:preflight(c,e);
  if(!pf.ok)throw Error(`PREFLIGHT_${pf.barreras.join('_')}`);
  nombresPrivados=new Set();nitsPrivados=new Set();
  const r={grupo:'G44',rf:'RF-87',run_id:c.runId,version:c.version,autorizacion_referencia:c.ref,casos:Object.fromEntries(CASOS.map(k=>[k,{estado:'NO_CONCLUYENTE',motivo:'No ejecutado',comprobaciones:[]}])),preflight:pf,solicitudes:[],comprobaciones:[],precios:[],activos:[],lineas:[],incidencias:[],evidencias:[],problemas_tecnicos:[],cypress:{paneles:{},total_pruebas:0},rollback:{verificado:false},herramientas:{node:process.version},oficial:false,consume_version:false};
  let token=null,escrituras=false,bases=new Map(),periodosBase=[],titularesBase=new Map(),costoNuevo=null,permitirNewman=false,eleccion=null;
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
    const sanear=(x)=>Array.isArray(x)?x.map(sanear):x&&typeof x==='object'?Object.fromEntries(Object.entries(x).map(([k,v])=>[k,/token|password|contrasena|cookie|secret|jwt|serial|identificador|numero_id_tributaria|nombre_usuario/i.test(k)?'[RESERVADO]':sanear(v)])):typeof x==='string'?clean(x):x;
    r.respuestas_cierre??={};r.respuestas_cierre[criterio]={periodo:id,http:z.http,solicitud:r.solicitudes.at(-1)?.id,cuerpo:sanear(z.data)};
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
    return{estado:p?.estado,fecha_cierre:p?.fecha_cierre??null,ultimo_cierre_id:p?.ultimo_cierre?.id_cierre??null,ultimo_cierre_estado:p?.ultimo_cierre?.estado??null,ultimo_cierre_paso:p?.ultimo_cierre?.paso_actual??null,lineas:ids(lineas),comprobantes:ids(comprobantes),variaciones:ids(variaciones)};
  };
  const marca=(id,esperado,cumple,observado,noConcluyente=false)=>criterio(id,esperado,cumple,observado,noConcluyente);
  const sinArtefactos=(id,s)=>s.estado==='ABIERTO'&&iguales(s.comprobantes,bases.get(id).comprobantes)&&iguales(s.variaciones,bases.get(id).variaciones);
  const apiCriterios={'TC-M06-028':[],'TC-M06-029':[],'TC-M06-030':[]};
  const incidente=(numero,clave,esperado,obtenido,impacto,severidad,relacion='')=>{const claves={'01':['029_admin','029_veterinario','029_productor'],'02':['030_cerrado'],'03':['030_segundo'],'04':['028_a'],'05':['028_b'],'06':['028_c']}[clave];const ids=claves.map(k=>r.respuestas_cierre?.[k]?.solicitud).filter(Boolean);r.incidencias.push({id:`INC-M06-G44-${clave}`,casos:[caso(numero)],esperado,obtenido,evidencia:`resultado.json; solicitudes ${ids.join(', ')}`,impacto,severidad,justificacion_severidad:severidad==='ALTA'?'La discrepancia bloquea un control relevante del cierre sin alternativa demostrada.':'La discrepancia afecta parcialmente el control o la explicación al usuario.',certeza:'CONFIRMADA',equipo:'Desarrollo',fundamento:'Primera discrepancia comprobada en la API pública de cierre.',hipotesis:'Causa raíz por determinar.',accion:'Desarrollo revisa el comportamiento y QA repite en RUN autorizado.',relacion});};
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
    for(const p of ps){if(p.ultimo_cierre?.nombre_usuario_ejecutor)nombresPrivados.add(p.ultimo_cierre.nombre_usuario_ejecutor);if(p.numero_id_tributaria)nitsPrivados.add(p.numero_id_tributaria);}
    const cfg=await get('/finanzas/configuracion');const m34=cfg.matriz.find(x=>Number(x.id_asignacion_cuenta_contable)===34),m49=cfg.matriz.find(x=>Number(x.id_asignacion_cuenta_contable)===49);
    const asignacion=(m,tipo,debito,credito)=>m&&m.tipo_hecho===tipo&&m.sentido==='UNICO'&&m.id_especie===null&&m.subtipo_costo===null&&m.cuenta_debito===debito&&m.cuenta_credito===credito;
    const p8=await pre(8),p220=await pre(220),p260=await pre(260);
    for(const id of [7,8,219,220,260])bases.set(id,await estado(id));
    usar('admin');for(const id of [466,467]){const t=await get(`/configuracion/fincas/${id}/titular`);titularesBase.set(id,t);if(t.numero_id_tributaria)nitsPrivados.add(t.numero_id_tributaria);if(t.razon_social)nombresPrivados.add(t.razon_social);}
    const checks=[];
    const check=(requisito,esperado,observado,cumple,bloqueante=true)=>checks.push({requisito,esperado,observado,cumple:Boolean(cumple),bloqueante});
    for(const [id,esperado] of [[7,'CERRADO'],[219,'CERRADO'],[220,'ABIERTO'],[260,'ABIERTO']])check(`periodo_${id}_estado`,esperado,bases.get(id).estado,bases.get(id).estado===esperado);
    const cierre8=porId(ps,8)?.ultimo_cierre;
    const ochoValido=bases.get(8).estado==='ABIERTO'||bases.get(8).estado==='EN_CIERRE'&&Number(cierre8?.id_cierre)===67&&cierre8?.estado==='EN_PROCESO'&&Number(cierre8?.paso_actual)===3;
    check('periodo_8_estado','ABIERTO o EN_CIERRE con cierre 67 EN_PROCESO paso 3',bases.get(8).estado,ochoValido);
    check('periodo_260_titular_466','Mismo titular tributario',Boolean(porId(ps,260)?.numero_id_tributaria&&porId(ps,260)?.numero_id_tributaria===titularesBase.get(466)?.numero_id_tributaria),Boolean(porId(ps,260)?.numero_id_tributaria&&porId(ps,260)?.numero_id_tributaria===titularesBase.get(466)?.numero_id_tributaria));
    check('periodo_220_titular_467','Mismo titular tributario',Boolean(porId(ps,220)?.numero_id_tributaria&&porId(ps,220)?.numero_id_tributaria===titularesBase.get(467)?.numero_id_tributaria),Boolean(porId(ps,220)?.numero_id_tributaria&&porId(ps,220)?.numero_id_tributaria===titularesBase.get(467)?.numero_id_tributaria));
    const lineas220Base=await get('/finanzas/lineas?id_periodo_contable=220');
    const hay467=lineas220Base.some(l=>Number(l.id_finca)===467);
    check('periodo_220_lineas_finca_467','Líneas de finca 467 presentes',hay467,hay467);
    check('periodo_260_sin_lineas','Sin líneas previas',bases.get(260).lineas.length,bases.get(260).lineas.length===0);
    for(const [id,p] of [[220,p220],[260,p260]])check(`prevalidacion_${id}_sin_bloqueos`,'[]',p.bloqueos.map(x=>x.codigo),p.bloqueos.length===0);
    for(const [id,t] of titularesBase)check(`titular_${id}_completo`,'cuatro campos tributarios completos',Object.fromEntries(['tipo_id_tributaria','numero_id_tributaria','dv','razon_social'].map(k=>[k,Boolean(t[k])])),['tipo_id_tributaria','numero_id_tributaria','dv','razon_social'].every(k=>Boolean(t[k])));
    check('matriz_34_generica_activa','MANO_OBRA_PROPIA/UNICO 158405/250505',Boolean(asignacion(m34,'MANO_OBRA_PROPIA','158405','250505')),Boolean(asignacion(m34,'MANO_OBRA_PROPIA','158405','250505')));
    check('matriz_49_generica_activa','DEPRECIACION_ACTIVO_COSTO/UNICO 516005/159205',Boolean(asignacion(m49,'DEPRECIACION_ACTIVO_COSTO','516005','159205')),Boolean(asignacion(m49,'DEPRECIACION_ACTIVO_COSTO','516005','159205')));
    for(const [id,finca] of [[1567,466],[1573,467]]){
      const activo=activos.find(x=>Number(x.id_activo_biologico)===id);
      check(`activo_${id}_valorado_por_costo`,'Activo al costo de la finca y vida útil positiva',activo?{finca_correcta:Number(activo.id_finca)===finca,valorado_por_costo:activo.valorado_por_costo,vida_util_meses:activo.vida_util_meses}:null,Boolean(activo&&Number(activo.id_finca)===finca&&activo.valorado_por_costo===true&&activo.vida_util_meses>0));
    }
    const candidatos=activos.filter(x=>Number(x.id_finca)===467&&x.estado!=='INACTIVO');
    eleccion=candidatos.find(x=>Number(x.id_activo_biologico)===1569)??candidatos[0];
    check('finca_467_activo_para_costo','Activo activo de finca 467',eleccion?.id_activo_biologico??null,Boolean(eleccion));
    r.preflight_datos=checks;
    const fallidos=checks.filter(x=>x.bloqueante&&!x.cumple).map(x=>x.requisito);
    if(fallidos.length)throw Error(`PREFLIGHT_DATOS_NO_CONCLUYENTE_${fallidos.join('_')}`);
    // 029: cada rol se observa por separado; también se verifica que 220 permanezca intacto.
    const acceso=[],mensajes=[];
    for(const [rol,etiqueta] of [['admin','Administrador'],['veterinario','Veterinario'],['productor','Productor']]){
      usar(rol);const z=await cierre(220,`029_${rol}`);usar('contador');const s=await estado(220);
      acceso.push(z.http===403&&iguales(s,bases.get(220)));
      mensajes.push(z.http===403&&rolEnMensaje(z.data?.message,etiqueta)&&/exclusiv[oa]/i.test(String(z.data?.message??''))&&/Contador/i.test(String(z.data?.message??'')));
      r[`observado_029_${rol}`]=obs(`029.${rol}`,z,`; sin cambios ${iguales(s,bases.get(220))}; rol en mensaje ${rolEnMensaje(z.data?.message,etiqueta)}`);
    }
    usar('admin');const adminP=await req('GET','/finanzas/periodos');const adminPre=await req('GET','/finanzas/periodos/220/prevalidacion');
    apiCriterios[caso('029')].push(marca('029_acceso','403 y 220 sin cambios para tres roles',acceso.every(Boolean),`029.acceso: ${acceso.join(',')}`),marca('029_mensaje','403, rol explícito y cierre exclusivo del Contador',mensajes.every(Boolean),`029.mensaje: ${mensajes.join(',')}`),marca('029_admin','Administrador consulta estado y prevalidación con 200',adminP.http===200&&adminPre.http===200,`029.admin: HTTP ${adminP.http}/${adminPre.http}`));
    const literal029='Acceso denegado: El proceso de cierre del periodo contable es competencia exclusiva del Contador del sistema. Su rol actual ([ROL_USUARIO]) no tiene permisos de cierre contable bajo la política RBAC del módulo M06.';
    for(const [rol,etiqueta] of [['admin','Administrador'],['veterinario','Veterinario'],['productor','Productor']]){const x=r.respuestas_cierre[`029_${rol}`];if(x?.http===403&&String(x.cuerpo?.message??'')!==literal029.replace('[ROL_USUARIO]',etiqueta))r.observaciones=[...(r.observaciones??[]),`OBS-G44-01: 029_${rol}: recibido «${clean(x.cuerpo?.message)}»; especificado FA-4 «${literal029}».`];}
    usar('contador');const periodo7=porId(await periodos(),7),ej7=periodo7?.ultimo_cierre?.nombre_usuario_ejecutor||periodo7?.ultimo_cierre?.id_usuario_ejecutor;const z7=await cierre(7,'030_cerrado'),s7=await estado(7);
    const cerrado=z7.http===409&&['PERIODO_CERRADO','PERIODO_INMUTABLE'].includes(z7.data?.error_code)&&contiene(z7.data?.message,String(periodo7.fecha_cierre??'').slice(0,10))&&contiene(z7.data?.message,ej7)&&iguales(s7,bases.get(7));
    apiCriterios[caso('030')].push(marca('030_cerrado','409 Periodo inmutable con fecha y Contador ejecutor; 7 CERRADO',cerrado,obs('030_cerrado',z7,`; 7 sin cambios ${iguales(s7,bases.get(7))}`)));
    if(cerrado&&!/Periodo inmutable.*Los periodos cerrados no pueden reabrirse/is.test(String(z7.data?.message??'')))r.observaciones=[...(r.observaciones??[]),`OBS-G44-01: 030_cerrado: recibido «${clean(z7.data?.message)}»; especificado FA-5 «Periodo inmutable: El periodo contable [ID_PERIODO] ya fue cerrado el [FECHA_CIERRE] por el Contador [ID_USUARIO_EJECUTOR]. Los periodos cerrados no pueden reabrirse.».`];
    const z219=await cierre(219,'030_cerrado_219'),s219=await estado(219);
    r.observacion_030_219=obs('030_cerrado_219',z219,`; 219 sin cambios ${iguales(s219,bases.get(219))}`);r.observaciones=[...(r.observaciones??[]),r.observacion_030_219];
    if(bases.get(8).estado==='EN_CIERRE'){
      const cancel67=await req('POST','/finanzas/periodos/8/cierre/cancelacion',{});escrituras=true;
      if(cancel67.http!==200||cancel67.data?.estado!=='ABIERTO'||(await estado(8)).estado!=='ABIERTO')throw Error('CANCELACION_67_NO_CONCLUYENTE');
      r.cancelacion_inicial={http:cancel67.http,id_cierre:cancel67.data?.id_cierre,estado:cancel67.data?.estado};
    }
    const p8libre=await pre(8),base8libre=await estado(8);
    if(!p8libre.lineas_sin_trazabilidad.some(x=>Number(x.id_linea)===17)){
      apiCriterios[caso('030')].push(marca('030_concurrencia','409 con hora y usuario del cierre activo',false,'Línea 17 ausente en prevalidación de 8',true),marca('030_sin_segundo','No se inicia segundo cierre',false,'No se inició cierre: falta línea 17',true));
    }else{
      const primero=await cierre(8,'030_primero'),p8primero=porId(await periodos(),8),x=p8primero?.ultimo_cierre;
      if(x?.nombre_usuario_ejecutor)nombresPrivados.add(x.nombre_usuario_ejecutor);
      const segundo=await cierre(8,'030_segundo'),s8=await estado(8);
      const hora=x?.fecha_inicio?`${fechaBogota(x.fecha_inicio)} ${horaBogota(x.fecha_inicio)}`:null;
      const quien=x?.nombre_usuario_ejecutor||x?.id_usuario_ejecutor;
      const concurrencia=primero.http===409&&primero.data?.error_code==='EXCLUSION_REQUIERE_AUTORIZACION'&&p8primero?.estado==='EN_CIERRE'&&x?.estado==='EN_PROCESO'&&Number(x?.paso_actual)===3&&segundo.http===409&&['CIERRE_EN_EJECUCION','CONFLICTO_CONCURRENCIA'].includes(segundo.data?.error_code)&&contiene(segundo.data?.message,hora)&&contiene(segundo.data?.message,quien);
      const sinSegundo=Number(s8.ultimo_cierre_id)===Number(x?.id_cierre)&&s8.estado==='EN_CIERRE'&&iguales(s8.comprobantes,base8libre.comprobantes)&&iguales(s8.variaciones,base8libre.variaciones);
      const cancelX=await req('POST','/finanzas/periodos/8/cierre/cancelacion',{});
      const final8=await estado(8);
      const cancelado=cancelX.http===200&&cancelX.data?.estado==='ABIERTO'&&final8.estado==='ABIERTO'&&iguales(final8.lineas,base8libre.lineas)&&iguales(final8.comprobantes,base8libre.comprobantes)&&iguales(final8.variaciones,base8libre.variaciones);
      apiCriterios[caso('030')].push(marca('030_concurrencia','Segundo POST: 409 con hora de inicio y ejecutor del cierre activo',concurrencia,obs('030_concurrencia',segundo,`; primer cierre ${x?.id_cierre??'ausente'}; hora y usuario presentes ${Boolean(hora&&quien)}`)),marca('030_sin_segundo','Mismo cierre activo, sin artefactos nuevos; cancelación vuelve a ABIERTO',sinSegundo&&cancelado,`030.sin_segundo: cierre igual ${sinSegundo}; cancelación ${cancelX.http}; restauración ${cancelado}`));
      if(concurrencia&&!/Conflicto de concurrencia.*Espere a que el proceso actual finalice/is.test(String(segundo.data?.message??'')))r.observaciones=[...(r.observaciones??[]),`OBS-G44-01: 030_concurrencia: recibido «${clean(segundo.data?.message)}»; especificado FA-5 «Conflicto de concurrencia: El periodo [ID_PERIODO] está siendo procesado por otro proceso de cierre activo iniciado el [TIMESTAMP_INICIO] por [ID_USUARIO]. Espere a que el proceso actual finalice antes de intentar un nuevo cierre.».`];
    }
    // 028-a: costo del mes actual en la finca 467, periodo 220.
    let a=false,z220a=null,del34ok=false;
    try{
    const del34=await req('DELETE','/finanzas/configuracion/matriz/34');if(del34.http!==204)throw Error(`MATRIZ_34_DELETE_${del34.http}`);escrituras=true;del34ok=true;
    const costo=await req('POST','/finanzas/costos',{subtipo_costo:'MANO_OBRA',origen_costo:'MANO_OBRA_PROPIA',monto_costo:'103.00',fecha_costo:hoyBogota(),id_activo_biologico:eleccion.id_activo_biologico,naturaleza_costo:'MANTENIMIENTO'});
    if(costo.http!==201||!Array.isArray(costo.data?.registros)||costo.data.registros.length!==1)throw Error(`COSTO_POST_${costo.http}`);
    costoNuevo=Number(costo.data.registros[0].id_registro_costo);
    const lineas220=await get('/finanzas/lineas?id_periodo_contable=220');const p220a=await pre(220);z220a=await cierre(220,'028_a');const s220a=await estado(220);
    const lineaPendiente=lineas220.some(x=>x.estado==='PENDIENTE_CUENTA'&&x.tipo_hecho==='MANO_OBRA_PROPIA'&&Number(x.id_activo_biologico)===Number(eleccion.id_activo_biologico));
    a=lineaPendiente&&p220a.bloqueos.some(x=>x.codigo==='LINEAS_PENDIENTE_CUENTA'&&/mano|obra|costo/i.test(x.mensaje??''))&&z220a.http!==200&&listaFaltantes(z220a,/cuenta|matriz|mano|obra/i)&&sinArtefactos(220,s220a);
    apiCriterios[caso('028')].push(marca('028_a','PENDIENTE_CUENTA y lista de faltantes; 220 ABIERTO sin cierre',a,obs('028_a',z220a,`; linea pendiente ${lineaPendiente}; bloqueo ${p220a.bloqueos.map(x=>x.codigo).join(',')}; estado ${s220a.estado}`)));
    const restaurar=await req('POST','/finanzas/configuracion/matriz',{tipo_hecho:'MANO_OBRA_PROPIA',sentido:'UNICO',id_especie:null,subtipo_costo:null,cuenta_debito:'158405',cuenta_credito:'250505'});
    if(restaurar.http!==201&&restaurar.http!==200)throw Error(`MATRIZ_34_RESTAURAR_${restaurar.http}`);del34ok=false;
    const lineasLimpias=await get('/finanzas/lineas?id_periodo_contable=220');const preLimpia=await pre(220);
    const limpio=!lineasLimpias.some(x=>x.tipo_hecho==='MANO_OBRA_PROPIA'&&Number(x.id_activo_biologico)===Number(eleccion.id_activo_biologico)&&x.estado==='PENDIENTE_CUENTA')&&preLimpia.bloqueos.length===0;
    if(!limpio){r.problemas_tecnicos.push('MATRIZ_34_RESTAURACION_NO_LIMPIA');const q=apiCriterios[caso('028')].find(x=>x.id==='028_a');if(q.cumple)q.noConcluyente=true;q.observado+='; restauración no limpia';}
    }catch(err){
      r.problemas_tecnicos.push(clean(err.message));
      if(!apiCriterios[caso('028')].some(q=>q.id==='028_a'))apiCriterios[caso('028')].push(marca('028_a','PENDIENTE_CUENTA y lista de faltantes; 220 ABIERTO sin cierre',false,`Preparación inconclusa: ${clean(err.message)}`,true));
      if(del34ok){const rep=await req('POST','/finanzas/configuracion/matriz',{tipo_hecho:'MANO_OBRA_PROPIA',sentido:'UNICO',id_especie:null,subtipo_costo:null,cuenta_debito:'158405',cuenta_credito:'250505'});if(![200,201].includes(rep.http))r.problemas_tecnicos.push(`MATRIZ_34_RESTAURAR_${rep.http}`);}
    }
    let b=false,z260b=null,put=null,c028=false,z220c=null,del49ok=false;
    if((await estado(260)).estado!=='ABIERTO')apiCriterios[caso('028')].push(marca('028_b','Matriz incompleta informada; 260 ABIERTO sin cierre',false,'260 dejó de estar ABIERTO',true));
    else{
      try{
      const del49=await req('DELETE','/finanzas/configuracion/matriz/49');if(del49.http!==204)throw Error(`MATRIZ_49_DELETE_${del49.http}`);del49ok=true;
      const preB=await pre(260);z260b=await cierre(260,'028_b');const s260b=await estado(260);
      b=preB.bloqueos.some(x=>x.codigo==='MATRIZ_CONTABLE_INCOMPLETA'&&/depreciaci.n|DEPRECIACION_ACTIVO_COSTO/i.test(x.mensaje??''))&&z260b.http!==200&&listaFaltantes(z260b,/depreciaci.n|DEPRECIACION_ACTIVO_COSTO|cuenta.*matriz/i)&&sinArtefactos(260,s260b);
      apiCriterios[caso('028')].push(marca('028_b','Matriz incompleta y lista de faltantes; 260 ABIERTO sin cierre',b,obs('028_b',z260b,`; bloqueo ${preB.bloqueos.map(x=>x.codigo).join(',')}; estado ${s260b.estado}`)));
      const rep49=await req('POST','/finanzas/configuracion/matriz',{tipo_hecho:'DEPRECIACION_ACTIVO_COSTO',sentido:'UNICO',id_especie:null,subtipo_costo:null,cuenta_debito:'516005',cuenta_credito:'159205'});
      if(![200,201].includes(rep49.http))throw Error(`MATRIZ_49_RESTAURAR_${rep49.http}`);del49ok=false;
      const p220rep=await pre(220),p260rep=await pre(260);
      if(p220rep.bloqueos.length||p260rep.bloqueos.length){r.problemas_tecnicos.push('MATRIZ_49_RESTAURACION_NO_LIMPIA');const q=apiCriterios[caso('028')].find(x=>x.id==='028_b');if(q.cumple)q.noConcluyente=true;q.observado+='; restauración no limpia';}
      }catch(err){r.problemas_tecnicos.push(clean(err.message));if(!apiCriterios[caso('028')].some(q=>q.id==='028_b'))apiCriterios[caso('028')].push(marca('028_b','Matriz incompleta informada; 260 ABIERTO sin cierre',false,`Preparación inconclusa: ${clean(err.message)}`,true));if(del49ok){const rep=await req('POST','/finanzas/configuracion/matriz',{tipo_hecho:'DEPRECIACION_ACTIVO_COSTO',sentido:'UNICO',id_especie:null,subtipo_costo:null,cuenta_debito:'516005',cuenta_credito:'159205'});if(![200,201].includes(rep.http))r.problemas_tecnicos.push(`MATRIZ_49_RESTAURAR_${rep.http}`);}}
    }
    // 028-c usa 220 y debe ejecutarse aunque 028-b falle en 260.
    if((await estado(220)).estado!=='ABIERTO')apiCriterios[caso('028')].push(marca('028_c','Finca sin titular informada; 220 ABIERTO sin cierre',false,'220 quedó CERRADO en escenario anterior',true));
    else{
      usar('admin');put=await req('PUT','/configuracion/fincas/467/titular',{tipo_id_tributaria:null,numero_id_tributaria:null,dv:null,razon_social:null});usar('contador');
      if(put.http>=400&&put.http<500)apiCriterios[caso('028')].push(marca('028_c','Finca sin titular informada; 220 ABIERTO sin cierre',false,obs('028_c_put',put),true));
      else{if(put.http!==200)throw Error(`TITULAR_PUT_${put.http}`);const preC=await pre(220);z220c=await cierre(220,'028_c');const s220c=await estado(220);c028=preC.bloqueos.some(x=>x.codigo==='FINCA_SIN_TITULAR')&&z220c.http!==200&&listaFaltantes(z220c,/finca.*titular|titular.*finca/i)&&sinArtefactos(220,s220c);apiCriterios[caso('028')].push(marca('028_c','Finca 467 sin titular y lista de faltantes; 220 ABIERTO sin cierre',c028,obs('028_c',z220c,`; prevalidacion ${preC.bloqueos.map(x=>x.codigo).join(',')}; estado ${s220c.estado}`)));}
      if(put.http===200){usar('admin');const rep=await req('PUT','/configuracion/fincas/467/titular',Object.fromEntries(['tipo_id_tributaria','numero_id_tributaria','dv','razon_social'].map(k=>[k,titularesBase.get(467)[k]])));usar('contador');if(rep.http!==200){r.problemas_tecnicos.push(`TITULAR_467_RESTAURAR_${rep.http}`);const q=apiCriterios[caso('028')].find(x=>x.id==='028_c');if(q?.cumple)q.noConcluyente=true;}}
    }
    for(const [numero,criterios] of Object.entries(apiCriterios)){r.casos[numero]=evaluar({[numero]:criterios})[numero];for(const q of r.casos[numero].comprobaciones)r.comprobaciones.push({caso:numero,id:q.id,fuente:'API',tipo:'ASSERT',estado:q.estado,evidencia:'resultado.json'});}
    if(r.casos[caso('029')].estado==='RECHAZADO')incidente('029','01','403 FA-4 con rol y sin cambios',r.observado_029_admin,'Control de acceso o explicación al rol incorrectos.','MEDIA');
    if(!cerrado)incidente('030','02','409 Periodo inmutable con fecha y ejecutor',obs('030_cerrado',z7),'El 409 omite información de auditoría requerida.','MEDIA');
    if(apiCriterios[caso('030')].some(q=>['030_concurrencia','030_sin_segundo'].includes(q.id)&&!q.cumple&&!q.noConcluyente))incidente('030','03','Segundo cierre rechazado por concurrencia con hora y usuario',apiCriterios[caso('030')].filter(q=>['030_concurrencia','030_sin_segundo'].includes(q.id)).map(q=>q.observado).join('; '),'El estado de cierre activo no se representa como exige RF-87.','MEDIA','INC-M06-G43-01');
    if(!a&&z220a)incidente('028','04','Bloqueo por PENDIENTE_CUENTA con lista',obs('028_a',z220a),'Cierre con cuenta faltante sin explicación suficiente.','ALTA');
    if(z260b&&!b)incidente('028','05','Bloqueo por matriz incompleta con lista',obs('028_b',z260b),'Cierre con depreciación sin cuenta no informado como exige RF-87.','ALTA');
    if(put?.http===200&&!c028)incidente('028','06','Bloqueo por finca sin titular',obs('028_c',z220c),'Cierre puede completarse o fallar sin informar titular ausente.','ALTA');
    const previasV1=[['INC-M06-G44-01','029','403 sin mensaje FA-4 ni rol'],['INC-M06-G44-02','030','409 de período CERRADO sin Periodo inmutable ni ejecutor'],['INC-M06-G44-03','030','segundo POST en EN_CIERRE sin 409 de concurrencia (relacionada con INC-M06-G43-01)'],['INC-M06-G44-05','028','cierre completado con la matriz de depreciación incompleta']];
    const actuales=new Set(r.incidencias.map(x=>x.id));
    const criterioInc={'01':'029_mensaje','02':'030_cerrado','03':'030_concurrencia','05':'028_b','06':'028_c'};
    r.seguimiento_incidencias_v2=[...previasV1,['INC-M06-G44-06','028','finca sin titular']].map(([id,c,desc])=>{const q=apiCriterios[caso(c)].find(x=>x.id===criterioInc[id.slice(-2)]);return{id,caso:caso(c),descripcion_v2:desc,estado_v3:q?.noConcluyente?'NO_CONCLUYENTE':actuales.has(id)?'REPRODUCIDA':'CORREGIDA'};});
    r.observaciones=[...(r.observaciones??[]),...r.seguimiento_incidencias_v2.map(x=>`Incidencia de V2 ${x.id} (${x.caso}): ${x.estado_v3}.`)];
    permitirNewman=CASOS.every(x=>['APROBADO','RECHAZADO'].includes(r.casos[x].estado)&&r.casos[x].comprobaciones.every(q=>q.estado!=='NO_CONCLUYENTE'));
    if(permitirNewman){const lanzar=local&&typeof opciones.hijo==='function'?opciones.hijo:(script,input,timeout)=>lanzarHijo({base:DIR,script,input,timeout,env:e,clean});const n=await lanzar('newman_hijo.mjs',{salida:path.join(c.dir,'newman'),coleccion:path.join(DIR,'G44.postman_collection.json'),environment:{values:[{key:'base_url',value:api},{key:'contador_token',value:tokens.contador},{key:'run_id',value:c.runId},{key:'sandbox_secret',value:e.QA_SANDBOX_SECRET}]}},300000);r.herramientas.newman=n.data??{codigo:2};if(n.code||n.data?.codigo!==0)r.problemas_tecnicos.push(`NEWMAN_${clean(n.error??n.code)}`);}
  }catch(err){r.problemas_tecnicos.push(clean(err.message));for(const numero of CASOS)if(r.casos[numero].motivo==='No ejecutado')r.casos[numero]={estado:'NO_CONCLUYENTE',motivo:clean(err.message),comprobaciones:[]};}
  finally{
    r.cierre={run:{cierre_http:null},rollback:r.rollback};
    if(Object.keys(tokens).length){try{
      usar('contador');const d=await req('DELETE',`/test-control/runs/${c.runId}`);r.cierre.run.cierre_http=d.http;if(d.http!==200)throw Error(`DELETE_${d.http}`);
      const despues=[];for(const id of [7,8,219,220,260])despues.push(await estado(id,true));
      const ps=await periodos(true),cfg=await get('/finanzas/configuracion',true),costos=await get('/finanzas/costos?id_periodo_contable=220',true);
      usar('admin');const titulares=new Map();for(const id of [466,467])titulares.set(id,await get(`/configuracion/fincas/${id}/titular`,true));
      const matriz=[34,49].every(id=>cfg.matriz.some(x=>Number(x.id_asignacion_cuenta_contable)===id));
      const costoAusente=!costos.some(x=>Number(x.id_registro_costo)===costoNuevo);
      const titularIgual=[466,467].every(id=>['tipo_id_tributaria','numero_id_tributaria','dv','razon_social'].every(k=>titulares.get(id)?.[k]===titularesBase.get(id)?.[k]));
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
