// Reevaluación RF-87 v1.2. El módulo solo se invoca desde g43.mjs con un contexto V2 válido.
import fs from 'node:fs';
import path from 'node:path';
import {CASOS,LIMITE,porId,precioVigente,sinCambios,cierre8CoincideG32,hoyBogota} from './g43_core.mjs';
import {esquema,validarLecturas,validarError} from './contrato.mjs';
import {crearSolicitante,lanzarHijo,listarEvidencias,guardarResultado,validarFormaResultado,clasificarFallo} from './infra.mjs';
import {informe} from './informe.mjs';
import {evaluarEstimacion1644} from './evidencia_estimacion.mjs';

const caso=n=>`TC-M06-${n}`;
const ids=['024','025','026','027'];
const hallado=(xs,key,id)=>Array.isArray(xs)&&xs.some(x=>Number(x[key])===id);
const lista=x=>Array.isArray(x)?x:[];
const mensajeTecnico=x=>String(x??'').replace(/eyJ[\w-]+\.[\w-]+\.[\w-]+|[\w.+-]+@[\w.-]+/g,'[RESERVADO]');
const especieCongelada=x=>Array.isArray(x)?x[0]:x;
const compacto=x=>({id_periodo_contable:x?.id_periodo_contable??null,estado:x?.estado??null,ultimo_cierre:x?.ultimo_cierre?{id_cierre:x.ultimo_cierre.id_cierre,estado:x.ultimo_cierre.estado,paso_actual:x.ultimo_cierre.paso_actual,precios_congelados:x.ultimo_cierre.precios_congelados}:null});
const preciosSeguros=xs=>lista(xs).map(x=>({id_precio_mercado:x.id_precio_mercado,id_especie:x.id_especie,categoria:x.categoria,id_metrica_produccion:x.id_metrica_produccion,precio_unitario:x.precio_unitario,fuente:x.fuente,fecha_vigencia:x.fecha_vigencia,fecha_vencimiento:x.fecha_vencimiento}));
const snap=(p,id,lineas,comprobantes,variaciones)=>({periodo:{id_periodo_contable:id,estado:porId(p,'id_periodo_contable',id)?.estado},lineas:lineas.map(x=>({id_linea_asiento_nic41:x.id_linea_asiento_nic41,id_activo_biologico:x.id_activo_biologico,estado:x.estado,estado_trazabilidad:x.estado_trazabilidad,id_periodo_contable:x.id_periodo_contable,tipo_evidencia:x.tipo_evidencia,tipo_hecho:x.tipo_hecho,valor:x.valor,cuenta_debito:x.cuenta_debito,cuenta_credito:x.cuenta_credito})),comprobantes:comprobantes.map(x=>({id_comprobante_nic41:x.id_comprobante_nic41})),variaciones:variaciones.map(x=>({id_variacion_valor_razonable:x.id_variacion_valor_razonable,tipo_evidencia:x.tipo_evidencia}))});
const baseIgual=(a,b)=>sinCambios({...a,periodo:{...a.periodo,estado:'ABIERTO'}},{...b,periodo:{...b.periodo,estado:'ABIERTO'}})&&JSON.stringify(a.lineas)===JSON.stringify(b.lineas)&&JSON.stringify(a.comprobantes)===JSON.stringify(b.comprobantes)&&JSON.stringify(a.variaciones)===JSON.stringify(b.variaciones);

export async function ejecutarV2(c,e,opciones,{DIR,API,FRONT,CAPACIDADES,preflight,permitidos,clean,id,sha}){
  const local=opciones.ensayo===true&&/^http:\/\/127\.0\.0\.1:\d+\/api$/.test(opciones.api??'');
  const api=local?opciones.api:API,front=local?(opciones.front??api):FRONT;
  const lanzar=local&&typeof opciones.hijo==='function'?opciones.hijo:(script,input,timeout)=>lanzarHijo({base:DIR,script,input,timeout,env:e,clean});
  const pf=local?{grupo:'G43',run_id:c.runId,version:2,ok:true,barreras:[],efectos:['Avisos de cierre y alertas NIC 41 persisten fuera del rollback']} :preflight(c,e);
  fs.mkdirSync(c.dir,{recursive:true});
  fs.writeFileSync(path.join(c.dir,'preflight.json'),JSON.stringify(pf,null,2));
  if(!pf.ok)throw Error(`PREFLIGHT_${pf.barreras.join('_')}`);
  const r={grupo:'G43',run_id:c.runId,version:2,rf:'RF-87 v1.2 (026); RF-87 (024, 025, 027)',autorizacion_referencia:c.ref,casos:Object.fromEntries(CASOS.map(x=>[x,{estado:'NO_CONCLUYENTE',motivo:'Sin ejecución',comprobaciones:[]}])),preflight:pf,diagnostico:{periodos:{},prevalidaciones:{},precios:{},activos:[],calculos:{},incidencias_previas:{}},solicitudes:[],comprobaciones:[],precios:[],activos:[],lineas:[],incidencias:[],evidencias:[],observaciones:[],problemas_tecnicos:[],cypress:{paneles:{}},rollback:{verificado:false},herramientas:{node:process.version},efectos_persistentes:[],cierres:[],oficial:false};
  const inicio=Date.now(),creados=[],nuevos=[],bases=new Map();let token=null,escenarios=false,pfValido=false,deleteIntentado=false;
  const solicitante=crearSolicitante({api,runId:c.runId,secret:e.QA_SANDBOX_SECRET,limite:LIMITE,solicitudes:r.solicitudes,esquema,validarLecturas,validarError,clean,id,token:()=>token,inicio,validarCompleto:true});
  const req=solicitante.req;
  const get=async ruta=>{const z=await req('GET',ruta);if(z.http!==200)throw Error(`LECTURA_${z.http}_${ruta}`);return z.data;};
  const ps=()=>get('/finanzas/periodos');
  const pre=n=>get(`/finanzas/periodos/${n}/prevalidacion`);
  const estado=async n=>snap(await ps(),n,await get(`/finanzas/lineas?id_periodo_contable=${n}`),await get(`/finanzas/periodos/${n}/comprobantes`),await get(`/finanzas/periodos/${n}/variaciones`));
  const cierre=(n,body)=>req('POST',`/finanzas/periodos/${n}/cierre`,body);
  const pagina=async n=>{const z=await get(`/notificaciones?pagina=${n}&tamano=50`);if(!Array.isArray(z.items)||!Number.isInteger(Number(z.total)))throw Error('BANDEJA_INCOMPLETA');return z.items;};
  const cierreAvisado=async(n,body)=>{const antes=await pagina(1),z=await cierre(n,body),primera=await pagina(1),prev=new Set(antes.map(x=>x.id_notificacion));let nuevos=primera.filter(x=>!prev.has(x.id_notificacion));if(primera.length===50&&nuevos.length===50)nuevos.push(...(await pagina(2)).filter(x=>!prev.has(x.id_notificacion)));const avisos=[...new Map(nuevos.map(x=>[x.id_notificacion,{id:x.id_notificacion,texto:clean(x.mensaje)}])).values()];r.cierres.push({periodo:n,http:z.http,avisos});r.efectos_persistentes.push(...avisos.map(x=>({...x,periodo:n})));return z;};
  const ui=async(panel,esperado,periodo,numeroIdTributaria)=>{const actual=porId(await ps(),'id_periodo_contable',periodo),pv=await pre(periodo);const valido=actual?.estado==='ABIERTO'&&(panel==='027'?lista(pv.lineas_sin_trazabilidad).some(x=>Number(x.id_linea)===17&&Number(x.id_activo_biologico)===944):lista(pv.activos_sin_precio).some(x=>Number(x.id_activo_biologico)===1644));if(!valido){const motivo=`PANEL_${panel}_PRECONDICION: periodo ${periodo} estado ${actual?.estado??'ausente'}; prevalidacion sin ${panel==='027'?'linea 17 y activo 944':'activo 1644'}`;r.cypress.paneles[panel]={codigo:0,totalTests:0,estado:'NO_CONCLUYENTE',diagnostico:motivo,capturas_tramos:[]};return {estado:'NO_CONCLUYENTE',motivo};}const z=await lanzar('cypress_hijo.mjs',{dir:path.join(c.dir,'cypress',panel),api,front,runId:c.runId,token,secret:e.QA_SANDBOX_SECRET,panel,periodo,numeroIdTributaria,esperado,localSmoke:local},180000);const a=z.data?.acta??{};r.cypress.paneles[panel]={codigo:z.code,totalTests:z.data?.totalTests??0,estado:a.estado??'NO_CONCLUYENTE',evidencia:`cypress/${panel}/G43-UI-${panel}.json`,solicitudes:a.peticiones?.length??0,capturas_tramos:a.capturas_tramos??[],controles_citados:a.controles_citados??[],diagnostico:a.diagnostico??null,resumen_dom:Boolean(a.resumen_dom?.encabezados?.length&&a.resumen_dom?.controles?.length)};if(z.code||!z.data?.totalTests||a.estado==='NO_CONCLUYENTE')r.problemas_tecnicos.push(`CYPRESS_${panel}_${mensajeTecnico(a.motivo||z.error||'SIN_ACTA_O_MENSAJE')}`);return a;};
  const set=(n,items)=>{r.casos[caso(n)]={estado:items.every(x=>x.ok)?'APROBADO':'RECHAZADO',motivo:items.filter(x=>!x.ok).map(x=>x.id).join(', ')||'Criterios conformes',comprobaciones:items.map(x=>({id:x.id,esperado:x.esperado,observado:clean(x.observado),estado:x.ok?'APROBADO':'RECHAZADO'}))};};
  const chk=(id,esperado,observado,ok)=>({id,esperado,observado,ok:Boolean(ok)});
  const inc=(clave,casos,esperado,obtenido,severidad,impacto)=>r.incidencias.push({id:clave,casos,esperado,obtenido:clean(obtenido),evidencia:'resultado.json',impacto,severidad,justificacion_severidad:impacto,certeza:'CONFIRMADA',equipo:'Desarrollo',fundamento:'Primera discrepancia comprobada en API o UI pública de cierre',hipotesis:'Causa raíz por determinar',accion:'Desarrollo revisa la discrepancia; QA repite con autorización'});
  try{
    const login=await req('POST','/sesiones/',{correo_electronico:e.QA_CONTADOR_EMAIL,contrasena:e.QA_CONTADOR_PASSWORD},true);if(login.http!==200)throw Error('LOGIN_CONTADOR');token=login.data.token;
    const permisos=await get('/sesiones/me/permisos');if(permitidos.some(([n,a])=>!lista(permisos.permisos).some(p=>p.nombre_recurso===n&&Number(p.id_accion)===a)))throw Error('PERMISOS_INSUFICIENTES');
    const periodos=await ps(),activos=await get('/finanzas/activos'),cfg=await get('/finanzas/configuracion');
    const p8=porId(periodos,'id_periodo_contable',8),p266=porId(periodos,'id_periodo_contable',266);
    r.diagnostico.periodos['8']=compacto(p8);r.diagnostico.periodos['266']=compacto(p266);
    const pre8=await pre(8),pre266=await pre(266);r.diagnostico.prevalidaciones['8']=pre8;r.diagnostico.prevalidaciones['266']=pre266;
    r.diagnostico.precios['39']=preciosSeguros(await get('/finanzas/precios?id_especie=39'));r.diagnostico.precios['544']=preciosSeguros(await get('/finanzas/precios?id_especie=544'));
    r.diagnostico.activos=activos.filter(x=>[943,944,1643,1644].includes(Number(x.id_activo_biologico)));
    const hist1644Base=await get('/finanzas/activos/1644');r.diagnostico.activo_1644={id_activo_biologico:hist1644Base.activo?.id_activo_biologico,valoracion_costo_activa:hist1644Base.valoracion_costo?.es_activa??false};
    for(const n of [8,266])bases.set(n,await estado(n));
    const a1643=porId(activos,'id_activo_biologico',1643),a1644=porId(activos,'id_activo_biologico',1644);
    const linea17=lista(pre8.lineas_sin_trazabilidad).find(x=>Number(x.id_linea)===17),sinPrecio=lista(pre266.activos_sin_precio).find(x=>Number(x.id_activo_biologico)===1644);
    const base8ok=p8?.estado==='ABIERTO'||p8?.estado==='EN_CIERRE'&&Number(p8.ultimo_cierre?.id_cierre)===67&&p8.ultimo_cierre?.estado==='EN_PROCESO'&&Number(p8.ultimo_cierre?.paso_actual)===3;
    const dia=hoyBogota(),ultimo492=lista(r.diagnostico.precios['544']).find(x=>Number(x.id_precio_mercado)===492);
    pfValido=Boolean(base8ok&&p266?.estado==='ABIERTO'&&linea17&&Number(linea17.id_activo_biologico)===944&&lista(linea17.faltantes).length>0&&sinPrecio&&a1644?.valorado_por_costo===false&&a1643?.valorado_por_costo===true&&Number(a1643.id_especie)===544&&Number(a1644.id_especie)===544&&Number(a1643.id_finca)===472&&Number(a1644.id_finca)===472&&ultimo492&&ultimo492.fecha_vencimiento<dia&&lista(pre266.bloqueos).length===0);
    if(!pfValido)throw Error('PREFLIGHT_DATOS_NO_CONCLUYENTE');
    const categoria=lista(cfg.especies).find(x=>Number(x.id_especie)===39)?.categoria_precio??'PESO_KG';
    const diaCierre=p8.fecha_fin&&p8.fecha_fin<dia?p8.fecha_fin:dia;
    const precioIni=precioVigente(lista(r.diagnostico.precios['39']),39,categoria,diaCierre);
    if(!precioIni)throw Error('PRECIO_39_SIN_VIGENCIA');
    if(!(precioIni.fecha_vigencia<dia&&dia<=p8.fecha_fin))throw Error('PRECIO_NUEVO_NO_COMPITE_EN_DIA_CIERRE');
    escenarios=true;
    if(p8.estado==='EN_CIERRE'){const cancel=await req('POST','/finanzas/periodos/8/cierre/cancelacion',{});if(cancel.http!==200||cancel.data?.estado!=='ABIERTO'||(await ps()).find(x=>Number(x.id_periodo_contable)===8)?.estado!=='ABIERTO'||!baseIgual(bases.get(8),await estado(8)))throw Error('CANCELACION_67_NO_CONCLUYENTE');r.cancelacion_inicial={http:cancel.http,id_cierre:cancel.data.id_cierre,estado:cancel.data.estado};}
    try{const base8=await estado(8),antes8=new Set(periodos.map(x=>Number(x.id_periodo_contable)));
    const u27=await ui('027',{linea:17,activos:[944],identificador:linea17.identificador,eslabones:linea17.faltantes},8,p8.numero_id_tributaria);
    const n8=await cierreAvisado(8,{}),pausa8Periodo=porId(await ps(),'id_periodo_contable',8),pausa8=pausa8Periodo?.estado;
    const congeladoPrimero=lista(pausa8Periodo?.ultimo_cierre?.precios_congelados).find(x=>Number(especieCongelada(x.id_especie))===39);
    const no27=n8.http===409&&n8.data?.error_code==='EXCLUSION_REQUIERE_AUTORIZACION'&&pausa8==='EN_CIERRE';
    const cancel8=await req('POST','/finanzas/periodos/8/cierre/cancelacion',{}),no8=cancel8.http===200&&cancel8.data?.estado==='ABIERTO'&&baseIgual(base8,await estado(8));
    const n8b=await cierreAvisado(8,{}),pausa8bPeriodo=porId(await ps(),'id_periodo_contable',8),pausa8b=pausa8bPeriodo?.estado;
    const congeladoSegundo=lista(pausa8bPeriodo?.ultimo_cierre?.precios_congelados).find(x=>Number(especieCongelada(x.id_especie))===39);
    const origenReferencia=`valorador.precio_para: especie 39, categoria ${categoria}, fuente ${precioIni.fuente}, vigencia mas reciente hasta ${diaCierre}, desempate por id; configuracion.especies o PESO_KG por defecto`;
    const nuevoPrecio=Math.round(Number(precioIni.precio_unitario)*1.05),umbral=Number(cfg.general?.pct_umbral_desviacion_precio);
    if(!(umbral>5&&nuevoPrecio>0&&nuevoPrecio!==Number(precioIni.precio_unitario)))throw Error('PRECIO_NUEVO_SUPERA_UMBRAL');
    const alta=await req('POST','/finanzas/precios',{id_especie:39,categoria,id_metrica_produccion:null,precio_unitario:String(nuevoPrecio),fecha_vigencia:dia,fuente:precioIni.fuente,evidencia_documental:`QA ${c.runId} precio durante pausa`,confirmar_desviacion:false});
    if(alta.http!==201)throw Error(`PRECIO_NUEVO_HTTP_${alta.http}`);creados.push(Number(alta.data.id_precio_mercado));
    const s8=await cierreAvisado(8,{autorizar_exclusiones:true,activos_estimados:[]});if(s8.http===200&&!antes8.has(Number(s8.data.id_periodo_siguiente)))nuevos.push(Number(s8.data.id_periodo_siguiente));
    const post8=porId(await ps(),'id_periodo_contable',8),congelados=lista(post8?.ultimo_cierre?.precios_congelados),congelado=congelados.find(x=>Number(especieCongelada(x.id_especie))===39),cal8=await get('/finanzas/periodos/8/calculos');
    if(congelados.some(x=>Array.isArray(x.id_especie)))r.observaciones.push('precios_congelados.id_especie se recibió como [id_especie, estima]; forma anómala del dato, sin alterar el oráculo del precio congelado.');
    const calCorrectos=cal8.some(x=>Number(x.id_activo_biologico)===943&&Number(x.precio_unitario)===Number(precioIni.precio_unitario));
    const destino8=s8.http===200?await get(`/finanzas/lineas?id_periodo_contable=${s8.data.id_periodo_siguiente}`):[];
    const si27=s8.http===200&&s8.data.estado==='CERRADO'&&hallado(s8.data.lineas_excluidas,'id_linea',17)&&destino8.some(x=>Number(x.id_linea_asiento_nic41)===17&&x.estado_trazabilidad==='PENDIENTE_TRAZABILIDAD');
    r.precios.push({especie:39,categoria,fuente:precioIni.fuente,p_ini:precioIni.id_precio_mercado,p_ini_fecha:precioIni.fecha_vigencia,p_ini_origen:origenReferencia,p_nuevo:alta.data.id_precio_mercado,p_nuevo_fecha:dia,p_nuevo_categoria:categoria,p_nuevo_fuente:precioIni.fuente,congelado_pausa_primero:congeladoPrimero??null,congelado_pausa_segundo:congeladoSegundo??null,congelado:congelado?.id_precio_mercado,congelado_fecha:congelado?.fecha_vigencia});
    r.lineas.push({id:17,id_activo:944,faltantes:lista(linea17.faltantes).join(', '),excluida:si27,destino:s8.data?.id_periodo_siguiente??null});
    const precioOk=Number(congelado?.id_precio_mercado)===Number(precioIni.id_precio_mercado)&&congelado?.fecha_vigencia===precioIni.fecha_vigencia&&Number(congelado?.id_precio_mercado)!==Number(alta.data.id_precio_mercado)&&calCorrectos;
    set('024',[chk('pausa_EN_CIERRE','Pausa EN_CIERRE',`${n8.http}/${pausa8}; ${n8b.http}/${pausa8b}`,no27&&n8b.http===409&&pausa8b==='EN_CIERRE'),chk('precio_congelado_ini','Precio inicial por id y fecha',`${congelado?.id_precio_mercado}/${congelado?.fecha_vigencia}`,precioOk),chk('cierre_autorizado','Cierre 8 CERRADO',`${s8.http}/${s8.data?.estado}`,s8.http===200&&s8.data?.estado==='CERRADO')]);
    set('027',[chk('lista_api','Asiento 17, activo 944 y eslabón',`línea ${linea17.id_linea}; activo ${linea17.id_activo_biologico}; faltan ${lista(linea17.faltantes).join(', ')}`,Boolean(linea17.identificador&&lista(linea17.faltantes).length)),chk('pausa_EN_CIERRE','Pausa EN_CIERRE',`${n8.http}/${pausa8}; ${n8b.http}/${pausa8b}`,no27&&n8b.http===409&&pausa8b==='EN_CIERRE'),chk('no_rollback','Cancelación deja 8 ABIERTO e intacto',`${cancel8.http}; ${no8}`,no8),chk('si_exclusion_027','Línea 17 pendiente en período siguiente',`${s8.http}; ${si27}`,si27),chk('ui_lista','Lista completa visible en UI',u27.estado,u27.lista_completa===true&&u27.estado==='APROBADO')]);
    if(!no27||!no8)inc('INC-M06-G43-01',[caso('024'),caso('027')],'Pausa y cancelación con estado correcto',`${n8.http}/${pausa8}; cancelación ${cancel8.http}`,'MEDIA','La decisión y el rollback del cierre se afectan.');
    if(u27.estado==='RECHAZADO')inc('INC-M06-G43-02',[caso('027')],'Lista UI con asiento, activo y eslabón',u27.diagnostico??`${u27.estado}; controles: ${lista(u27.controles_citados).join('; ')}`,'MEDIA','La lista limita la decisión informada.');
    if(s8.http===200&&!precioOk)inc('INC-M06-G43-05',[caso('024')],'Precio 39 congelado al inicio y usado en la medición',`congelado ${congelado?.id_precio_mercado}; inicial ${precioIni.id_precio_mercado}; nuevo ${alta.data.id_precio_mercado}`,'ALTA','La valoración del cierre puede usar un precio posterior.');
    if(s8.http===200&&!si27)inc('INC-M06-G43-06',[caso('027')],'Línea 17 excluida y pendiente en el período siguiente',`HTTP ${s8.http}; destino ${s8.data?.id_periodo_siguiente}`,'ALTA','La exclusión autorizada no conserva la trazabilidad pendiente.');
    if(s8.http===500){const aud=await get('/finanzas/auditoria?id_periodo_contable=8&tipo_evento=CIERRE_PERIODO_FALLIDO&formato=TECNICO&pagina=1&tamano=500');r.diagnostico.auditoria_g32=lista(aud.eventos).map(x=>({tipo_evento:x.tipo_evento,timestamp_evento:x.timestamp_evento,paso:x.payload_evento?.paso}));if(cierre8CoincideG32(s8,lista(aud.eventos),new Date(inicio).toISOString()))inc('INC-M06-G32-01',[caso('024'),caso('027')],'Cierre autorizado completo',`HTTP 500 en ${s8.hora_utc}`,'ALTA','El cierre autorizado queda bloqueado.');else inc('INC-M06-G43-07',[caso('024'),caso('027')],'Cierre 8 autorizado completo',`HTTP 500 en ${s8.hora_utc}; patrón G32 no demostrado`,'ALTA','El cierre autorizado queda bloqueado.');}
    else if(s8.http!==200)inc('INC-M06-G43-07',[caso('024'),caso('027')],'Cierre 8 autorizado completo',`HTTP ${s8.http}`,'ALTA','El cierre autorizado queda bloqueado.');
    }catch(err){r.problemas_tecnicos.push(`SECUENCIA_8_${clean(err.message)}`);for(const n of ['024','027'])if(r.casos[caso(n)].motivo==='Sin ejecución')r.casos[caso(n)].motivo=clean(err.message);}
    // 025 es una secuencia independiente del cierre 8.
    const u25=await ui('025',{activos:[{id:1644,identificador:sinPrecio.identificador,especie:sinPrecio.especie}],conteo:1},266,p266.numero_id_tributaria);
    const n25=await cierreAvisado(266,{}),pausa25=porId(await ps(),'id_periodo_contable',266)?.estado;
    const can25=await req('POST','/finanzas/periodos/266/cierre/cancelacion',{}),no25=n25.http===409&&pausa25==='EN_CIERRE'&&can25.http===200&&can25.data?.estado==='ABIERTO'&&baseIgual(bases.get(266),await estado(266));
    const n25b=await cierreAvisado(266,{});const s25=await cierreAvisado(266,{autorizar_exclusiones:true,activos_estimados:[]});const next=Number(s25.data?.id_periodo_siguiente);
    if(s25.http===200&&next&&!periodos.some(x=>Number(x.id_periodo_contable)===next))nuevos.push(next);
    const cal266=await get('/finanzas/periodos/266/calculos'),costo163=cal266.some(x=>Number(x.id_activo_biologico)===1643)||Number(s25.data?.activos_procesados)>0;
    const si25=s25.http===200&&s25.data.estado==='CERRADO'&&lista(s25.data.activos_excluidos).some(x=>Number(x.id_activo_biologico)===1644&&x.motivo==='PENDIENTE_PRECIO')&&costo163;
    r.activos.push({periodo:266,prevalidacion:'1644',excluidos:lista(s25.data?.activos_excluidos).map(x=>x.id_activo_biologico).join(','),procesados:s25.data?.activos_procesados??null});
    set('025',[chk('aviso_api','Número, activo y especie',`1 activo: ${sinPrecio.identificador}, ${sinPrecio.especie}`,Boolean(sinPrecio.identificador&&sinPrecio.especie)),chk('no_rollback','No deja 266 ABIERTO e intacto',`${n25.http}; ${can25.http}; ${no25}`,no25),chk('si_exclusion','Sí cierra excluyendo 1644 y procesa 1643',`${s25.http}; ${si25}`,si25),chk('ui_lista','Advertencia y decisión por activo en UI',u25.estado,u25.lista_completa===true&&u25.decision_por_activo===true&&u25.estado==='APROBADO')]);
    if(r.casos[caso('025')].estado==='RECHAZADO')inc('INC-M06-G43-04',[caso('025')],'FA-2 conforme',r.casos[caso('025')].motivo,'ALTA','La exclusión o la decisión informada falla.');
    if(s25.http!==200||!next)throw Error('PERIODO_SIGUIENTE_266_NO_DISPONIBLE');
    const pNext=porId(await ps(),'id_periodo_contable',next),preNext=await pre(next);r.diagnostico.periodos[String(next)]=compacto(pNext);r.diagnostico.prevalidaciones[String(next)]=preNext;r.diagnostico.periodo_siguiente_base=await estado(next);
    if(pNext?.estado!=='ABIERTO'||!hallado(preNext.activos_sin_precio,'id_activo_biologico',1644))throw Error('PREFLIGHT_026_NO_CONCLUYENTE');
    const u26=await ui('026',{activos:[1644],sinPrecio:[1644]},next,pNext.numero_id_tributaria);
    const invalido=await cierreAvisado(next,{activos_estimados:[1643]}),noDecision=await cierreAvisado(next,{}),noDecisionEstado=porId(await ps(),'id_periodo_contable',next)?.estado;
    const s26=await cierreAvisado(next,{activos_estimados:[1644]});if(s26.http===200&&Number(s26.data.id_periodo_siguiente))nuevos.push(Number(s26.data.id_periodo_siguiente));
    const calNext=await get(`/finanzas/periodos/${next}/calculos`);
    const auditNext=await get(`/finanzas/auditoria?id_periodo_contable=${next}&id_activo_biologico=1644&formato=TECNICO&pagina=1&tamano=500`);
    const periodoCerrado=porId(await ps(),'id_periodo_contable',next);
    const avisosCierre=lista(r.cierres.findLast(x=>x.periodo===next)?.avisos);
    const eventosAuditoria=lista(JSON.parse(JSON.stringify(auditNext)).eventos),respuestaCierre=JSON.parse(JSON.stringify(s26.data));
    const evidenciaEst=evaluarEstimacion1644({calculos:calNext,auditoria:eventosAuditoria,avisos:avisosCierre,cierre:respuestaCierre,congelados:lista(periodoCerrado?.ultimo_cierre?.precios_congelados),precio492:ultimo492.precio_unitario});
    r.diagnostico.estimacion_1644={periodo:next,precio_ultimo_conocido:492,calculos:calNext.filter(x=>Number(x.id_activo_biologico)===1644).map(x=>({id_calculo:x.id_calculo_valor_razonable,precio_unitario:x.precio_unitario,tiene_valor_estimado:x.tiene_valor_estimado})),auditoria:eventosAuditoria.map(x=>({tipo_evento:x.tipo_evento,id_referencia:x.id_referencia,id_activo_biologico:x.id_activo_biologico,precio_usado:x.payload_evento?.precio_usado??null})),alertas:avisosCierre.filter(x=>/PRECIO_ESTIMADO|precio estimado/i.test(x.texto??'')).map(x=>({id:x.id,texto:x.texto})),respuesta:{id_cierre:respuestaCierre?.id_cierre,activos_procesados:respuestaCierre?.activos_procesados,activos_estimados:respuestaCierre?.activos_estimados??null},...evidenciaEst};
    const hist1644=await get('/finanzas/activos/1644');const sinCostoNuevo=hist1644.valoracion_costo?.es_activa!==true&&JSON.stringify(hist1644.valoracion_costo??null)===JSON.stringify(hist1644Base.valoracion_costo??null);const estima=s26.http===200&&s26.data.estado==='CERRADO'&&evidenciaEst.acreditada&&sinCostoNuevo;
    if(!evidenciaEst.acreditada&&evidenciaEst.auditoria_sin_variacion)r.observaciones.push('026: variación cero del 1644: MEDICION_SIN_VARIACION sin marca de estimación acreditada; consultar a la líder de requisito, como en G41.');
    r.activos.push({periodo:next,prevalidacion:'1644',excluidos:lista(s26.data?.activos_excluidos).map(x=>x.id_activo_biologico).join(','),procesados:s26.data?.activos_procesados??null});
    set('026',[chk('estimado_no_aplica','1643 devuelve 400 ACTIVO_ESTIMADO_NO_APLICA',`${invalido.http}/${invalido.data?.error_code}`,invalido.http===400&&invalido.data?.error_code==='ACTIVO_ESTIMADO_NO_APLICA'),chk('sin_decision','Sin decisión devuelve 409 y el período no cierra',`${noDecision.http}/${noDecision.data?.error_code}; ${noDecisionEstado}`,noDecision.http===409&&noDecision.data?.error_code==='EXCLUSION_REQUIERE_AUTORIZACION'&&noDecisionEstado==='EN_CIERRE'),chk('estimacion_1644','1644 estimado con precio 492, sin COSTO nuevo',`${s26.http}; vías ${JSON.stringify(evidenciaEst.vias)}; sin variación ${evidenciaEst.auditoria_sin_variacion}; costo nuevo ${!sinCostoNuevo}`,estima),chk('ui_decision','UI permite excluir o estimar por activo',u26.estado,u26.decision_por_activo===true&&u26.estado==='APROBADO')]);
    if(r.casos[caso('026')].estado==='RECHAZADO')inc('INC-M06-G43-03',[caso('026')],'RF-87 v1.2: decisión y estimación por activo',`${r.casos[caso('026')].motivo}; UI: ${u26.diagnostico??lista(u26.controles_citados).join('; ')}`,'ALTA','La valoración por activo puede ser incorrecta.');
    for(const n of ids){const cazo=caso(n),panel=n==='024'?'027':n,p=r.cypress.paneles[panel];if(['APROBADO','RECHAZADO'].includes(r.casos[cazo].estado)&&p?.totalTests>0){r.comprobaciones.push({caso:cazo,id:`G43-API-${n}-01`,fuente:'API',tipo:'ASSERT',estado:r.casos[cazo].estado,evidencia:'resultado.json'});r.comprobaciones.push({caso:cazo,id:`G43-UI-${panel}-01`,fuente:'UI',tipo:'ASSERT',estado:p.estado,evidencia:p.evidencia});}}
    if(ids.every(n=>['APROBADO','RECHAZADO'].includes(r.casos[caso(n)].estado))){const env={values:[{key:'base_url',value:api},{key:'contador_token',value:token},{key:'run_id',value:c.runId},{key:'sandbox_secret',value:e.QA_SANDBOX_SECRET},{key:'periodo_sin_precio',value:'266'},{key:'periodo_siguiente',value:String(next)}]};const n=await lanzar('newman_hijo.mjs',{salida:path.join(c.dir,'newman'),coleccion:path.join(DIR,'G43.postman_collection.json'),environment:env});r.herramientas.newman=n.data??{codigo:2};if(n.code)r.problemas_tecnicos.push(`NEWMAN_${clean(n.error)}`);}
    const cumple=(n,k)=>r.casos[caso(n)].comprobaciones.some(x=>x.id===k&&x.estado==='APROBADO');
    const seguimiento=[['INC-M06-G43-01',cumple('024','pausa_EN_CIERRE')&&cumple('027','no_rollback')],['INC-M06-G43-02',cumple('027','ui_lista')],['INC-M06-G43-03',r.casos[caso('026')].estado==='APROBADO'],['INC-M06-G32-01',r.cierres.filter(x=>x.periodo===8).at(-1)?.http===200]];
    r.seguimiento=Object.fromEntries(seguimiento.map(([k,ok])=>[k,r.incidencias.some(x=>x.id===k)?'REPRODUCIDA':ok?'CORREGIDA':'NO_CONCLUYENTE']));
  }catch(err){r.problemas_tecnicos.push(clean(err.message));for(const n of ids)if(r.casos[caso(n)].motivo==='Sin ejecución')r.casos[caso(n)].motivo=clean(err.message);}
  finally{try{
    if(local&&opciones.falloLocal==='finally')throw Error('FALLO_LOCAL_FINALLY');
    r.seguimiento??=Object.fromEntries(['INC-M06-G43-01','INC-M06-G43-02','INC-M06-G43-03','INC-M06-G32-01'].map(k=>[k,r.incidencias.some(x=>x.id===k)?'REPRODUCIDA':'NO_CONCLUYENTE']));
    for(const n of ['025','026','027']){const p=r.cypress.paneles[n];if(!p||!p.totalTests||p.codigo!==0||p.estado==='NO_CONCLUYENTE'){for(const afectado of n==='027'?['024','027']:[n]){const anterior=r.casos[caso(afectado)];const causaApi=anterior.estado==='NO_CONCLUYENTE'&&!['Sin ejecución','Criterios conformes'].includes(anterior.motivo);const causaCypress=r.problemas_tecnicos.find(x=>x.startsWith(`CYPRESS_${n}_`));r.casos[caso(afectado)]={estado:'NO_CONCLUYENTE',motivo:causaApi?anterior.motivo:causaCypress??p?.diagnostico??`CYPRESS_${n}_SIN_ACTA_O_MENSAJE`,comprobaciones:[]};r.comprobaciones=r.comprobaciones.filter(x=>x.caso!==caso(afectado));}}}
    r.incidencias=r.incidencias.filter(x=>!x.casos.every(c=>r.casos[c].estado==='NO_CONCLUYENTE'));
    for(const clave of Object.keys(r.seguimiento??{}))if(r.seguimiento[clave]==='REPRODUCIDA'&&!r.incidencias.some(x=>x.id===clave))r.seguimiento[clave]='NO_CONCLUYENTE';
    r.cierre={run:{cierre_http:null},rollback:r.rollback};
    if(token)try{deleteIntentado=true;const d=await req('DELETE',`/test-control/runs/${c.runId}`);r.cierre.run.cierre_http=d.http;if(d.http!==200)throw Error(`DELETE_${d.http}`);
      const post=async ruta=>{const z=await req('GET',ruta,undefined,true);if(z.http!==200)throw Error(`POSCIERRE_${z.http}_${ruta}`);return z.data;};
      const periodos=await post('/finanzas/periodos'),actuales=new Set(periodos.map(x=>Number(x.id_periodo_contable)));
      let iguales=true;for(const [n,b] of bases){const now=snap(periodos,n,await post(`/finanzas/lineas?id_periodo_contable=${n}`),await post(`/finanzas/periodos/${n}/comprobantes`),await post(`/finanzas/periodos/${n}/variaciones`));iguales&&=now.periodo.estado===b.periodo.estado&&baseIgual(b,now);}
      if(r.diagnostico.periodos['8']?.estado==='EN_CIERRE'){const cierre=porId(periodos,'id_periodo_contable',8)?.ultimo_cierre;iguales&&=Number(cierre?.id_cierre)===67&&cierre?.estado==='EN_PROCESO'&&Number(cierre?.paso_actual)===3;}
      const precios=await post('/finanzas/precios?id_especie=39'),sinAlta=creados.every(n=>!hallado(precios,'id_precio_mercado',n));
      r.rollback={verificado:iguales&&sinAlta&&nuevos.every(n=>!actuales.has(n)),motivo:`Bases ${iguales?'intactas':'distintas'}; precio nuevo ${sinAlta?'ausente':'presente'}; períodos nuevos ${nuevos.every(n=>!actuales.has(n))?'ausentes':'presentes'}. Lecturas sin cabeceras del RUN.`};
    }catch(err){r.rollback={verificado:false,motivo:clean(err.message)};}
    r.cierre.rollback=r.rollback;
    r.cypress.total_pruebas=Object.values(r.cypress.paneles).reduce((a,x)=>a+(x.totalTests??0),0);r.cypress.codigo=Object.values(r.cypress.paneles).every(x=>x.codigo===0)?0:2;
    r.herramientas.cypress={codigo:r.cypress.codigo,totalTests:r.cypress.total_pruebas};
    r.total_solicitudes_api=solicitante.total()+(r.herramientas.newman?.solicitudes??0);
    r.total_solicitudes_cypress=Object.values(r.cypress.paneles).reduce((a,x)=>a+(x.solicitudes??0),0);
    r.duracion_segundos=Math.ceil((Date.now()-inicio)/1000);
    r.evidencias=['preflight.json',...listarEvidencias(c.dir).filter(x=>x.startsWith('newman/')||x.startsWith('cypress/'))];
    const requeridos=['newman/newman-G43.json','newman/newman-G43.html',...['025','026','027'].map(x=>`cypress/${x}/G43-UI-${x}.json`)];
    const artefactos=requeridos.every(x=>r.evidencias.includes(x))&&['025','026','027'].every(x=>{const p=r.cypress.paneles[x];return p?.resumen_dom===true&&p.capturas_tramos.length>0&&p.capturas_tramos.every(n=>r.evidencias.some(y=>y.startsWith(`cypress/${x}/screenshots/`)&&y.endsWith(`/${n}`)));});
    r.condiciones_oficialidad={cuatro_casos:ids.every(n=>['APROBADO','RECHAZADO'].includes(r.casos[caso(n)].estado)),rollback:r.rollback.verificado,newman:r.herramientas.newman?.codigo===0&&r.herramientas.newman?.fallos===0&&r.herramientas.newman?.reportes===true,cypress:r.cypress.total_pruebas===3&&Object.values(r.cypress.paneles).every(x=>x.codigo===0&&['APROBADO','RECHAZADO'].includes(x.estado)),artefactos,presupuesto:r.total_solicitudes_api<=LIMITE.solicitudes_totales&&r.total_solicitudes_cypress<=LIMITE.cypress_solicitudes&&r.duracion_segundos<=LIMITE.duracion_segundos,sin_error_tecnico:r.problemas_tecnicos.length===0};
    r.oficial=Object.values(r.condiciones_oficialidad).every(Boolean);r.consume_version=solicitante.escrituras()>0;r.clasificacion_fallo=!pfValido?'DATOS_PRECONDICION':clasificarFallo(r);
    r.sha256={ejecutor:sha(path.join(DIR,'g43.mjs'))};
    const forma=validarFormaResultado(r,CAPACIDADES,c.dir);if(forma.length){r.problemas_tecnicos.push(`RESULTADO_FORMA_${forma.join('_')}`);r.oficial=false;r.clasificacion_fallo='CONTRATO';}
    if(local&&opciones.falloLocal==='informe')throw Error('FALLO_LOCAL_INFORME');
    guardarResultado(c,r,informe);
  }catch(err){
    r.problemas_tecnicos.push(`FINALIZACION_${clean(err.message)}`);
    r.oficial=false;
    if(token&&!deleteIntentado){
      deleteIntentado=true;
      try{const d=await req('DELETE',`/test-control/runs/${c.runId}`);r.cierre??={run:{},rollback:r.rollback};r.cierre.run.cierre_http=d.http;if(d.http!==200)throw Error(`DELETE_${d.http}`);}
      catch(e){r.problemas_tecnicos.push(`DELETE_${clean(e.message)}`);}
    }
    r.cierre??={run:{cierre_http:null},rollback:r.rollback};
    r.cierre.run??={cierre_http:null};
    r.rollback={verificado:false,motivo:'La finalización falló; rollback no verificado.'};
    r.cierre.rollback=r.rollback;
    r.seguimiento??=Object.fromEntries(['INC-M06-G43-01','INC-M06-G43-02','INC-M06-G43-03','INC-M06-G32-01'].map(k=>[k,'NO_CONCLUYENTE']));
    for(const n of ids)if(!['APROBADO','RECHAZADO'].includes(r.casos[caso(n)].estado))r.casos[caso(n)]={estado:'NO_CONCLUYENTE',motivo:clean(err.message),comprobaciones:[]};
    r.cypress.total_pruebas??=Object.values(r.cypress.paneles).reduce((a,x)=>a+(x.totalTests??0),0);
    r.herramientas.cypress??={codigo:2,totalTests:r.cypress.total_pruebas};
    r.total_solicitudes_api??=solicitante.total();
    r.total_solicitudes_cypress??=0;
    r.duracion_segundos??=Math.ceil((Date.now()-inicio)/1000);
    r.consume_version=solicitante.escrituras()>0;
    r.clasificacion_fallo='CONTRATO';
    r.condiciones_oficialidad={...(r.condiciones_oficialidad??{}),sin_error_tecnico:false,rollback:false};
    // Una respuesta instrumentada puede lanzar también durante JSON.stringify.
    try{JSON.stringify(r);}catch(e){r.problemas_tecnicos.push(`DIAGNOSTICO_NO_SERIALIZABLE_${clean(e.message)}`);r.diagnostico={error_serializacion:clean(e.message)};}
    const nombre=`TC-M06-${r.grupo}_reevaluacion_V${c.version}.md`;
    const resumen=[
      `# TC-M06-${r.grupo} — reevaluación V${c.version} NO OFICIAL`,
      '',`${r.grupo} | ${r.rf} | ${ids.map(caso).join(', ')} | V${c.version} | ${r.run_id} | ${local?'LOCAL':'TEST'} | autorización ${clean(r.autorizacion_referencia)}.`,
      '','## Resumen de casos','',...ids.map(n=>`- ${caso(n)}: ${r.casos[caso(n)].estado}; ${clean(r.casos[caso(n)].motivo)}`),
      '','## Esperado y observado por caso','',...ids.map(n=>`- ${caso(n)}: esperado ${r.casos[caso(n)].comprobaciones.map(x=>clean(x.esperado)).join('; ')||'oráculos del caso'}; observado ${r.casos[caso(n)].comprobaciones.map(x=>clean(x.observado)).join('; ')||'sin comprobación concluyente'}.`),
      '','## Comprobaciones API y UI','',...r.comprobaciones.map(x=>`- ${x.caso} ${x.fuente} ${x.id}: ${x.estado}; ${clean(x.evidencia)}.`),
      '','## Evidencias reales','',...r.evidencias.map(x=>`- ${x}`),
      '','## Incidencias de producto','',...r.incidencias.map(x=>`- ${x.id}: ${clean(x.obtenido)}; severidad ${x.severidad}; certeza ${x.certeza}; equipo inicial ${x.equipo}.`),
      '','## Problemas técnicos y análisis','',...r.problemas_tecnicos.map(x=>`- ${mensajeTecnico(x)}`),
      '','## Conclusión, cierre y rollback','',`Finalización con error: ${clean(err.message)}. DELETE intentado: ${deleteIntentado}. HTTP ${r.cierre.run.cierre_http??'desconocido'}. Rollback NO_VERIFICADO. Revisar resultado.json y autorizar un reintento si corresponde.`,''].join('\n');
    fs.writeFileSync(path.join(c.dir,'resultado.json'),JSON.stringify(r,null,2));
    fs.writeFileSync(path.join(c.dir,nombre),resumen);
  }
  }
  return r;
}
