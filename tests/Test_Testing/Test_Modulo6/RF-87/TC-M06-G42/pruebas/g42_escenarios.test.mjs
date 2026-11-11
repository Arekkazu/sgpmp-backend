import http from 'node:http';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import assert from 'node:assert/strict';
import {principal,CAPACIDADES} from '../g42.mjs';
import {validarError} from '../lib/contrato.mjs';
const error=(error_code,message)=>({error_code,message,fields:[],timestamp:'2026-11-09T18:00:00+00:00'});
import {clasificarRegistro} from './registro_qa.mjs';
const RUN='RUN-G42-V1-20261109-180000',CASOS=['TC-M06-021','TC-M06-022','TC-M06-023'];
const clone=x=>JSON.parse(JSON.stringify(x));
const token=id=>`a.${Buffer.from(JSON.stringify({sub:String(id)})).toString('base64url')}.b`;
const matrix=[['VARIACION_VR_TB','GANANCIA'],['VARIACION_VR_TB','PERDIDA'],['VARIACION_VR_PM','GANANCIA'],['VARIACION_VR_PM','PERDIDA'],['DEPRECIACION_ACTIVO_COSTO','UNICO'],['MANO_OBRA_PROPIA','UNICO'],['CONSUMO_INSUMO','UNICO']].map(([tipo_hecho,sentido],i)=>({id_asignacion_cuenta_contable:i+1,tipo_hecho,sentido,id_especie:null,subtipo_costo:null,cuenta_debito:String(100+i),cuenta_credito:String(200+i)}));
const activos=[943,944,945,946,947,948,1568,1569,1570,1571,1572,1573].map((id,i)=>({id_activo_biologico:id,id_especie:id>=943&&id<=948?1:id===1568||id>=1572?2:3,id_finca:id>=943&&id<=948?463:1,estado:id===948?'BAJA':'ACTIVO',valorado_por_costo:id>=1572,identificador:`QA-${i}`}));
const periodos0=[{id_periodo_contable:7,numero_id_tributaria:'111111111',fecha_inicio:'2026-11-01',fecha_fin:'2026-11-30',estado:'CERRADO'},{id_periodo_contable:8,numero_id_tributaria:'111111111',fecha_inicio:'2026-12-01',fecha_fin:'2026-12-31',estado:'ABIERTO'},{id_periodo_contable:219,numero_id_tributaria:'222222222',fecha_inicio:'2026-11-01',fecha_fin:'2026-11-30',estado:'ABIERTO'},{id_periodo_contable:220,numero_id_tributaria:'333333333',fecha_inicio:'2026-11-01',fecha_fin:'2026-11-30',estado:'ABIERTO'}];
const line=(id,tipo,sentido,esp,nit,valor='10')=>({id_linea_asiento_nic41:id,id_activo_biologico:esp===1?943:esp===2?1572:1569,estado:'REGISTRADA',tipo_hecho:tipo,sentido,id_especie:esp,subtipo_costo:null,cuenta_debito:String(100+matrix.findIndex(x=>x.tipo_hecho===tipo&&x.sentido===sentido)),cuenta_credito:String(200+matrix.findIndex(x=>x.tipo_hecho===tipo&&x.sentido===sentido)),numero_id_tributaria:nit,id_periodo_contable:nit==='111111111'?8:nit==='222222222'?219:220,valor});
const v=(id,tipo,linea)=>({id_variacion_valor_razonable:id,id_activo_biologico:943,tipo,monto_variacion:'10',id_linea:linea,tipo_evidencia:'EVENTO_BIOLOGICO',estado_trazabilidad:'VERIFICADO'});
function comprobantes(lineas,nit){const groups=new Map();for(const l of lineas.filter(x=>x.estado==='REGISTRADA')){const k=`${l.tipo_hecho}|${l.id_especie}`;if(!groups.has(k))groups.set(k,[]);groups.get(k).push(l);}return [...groups].map(([k,ls],i)=>{const [tipo,especie]=k.split('|'),pares=new Map();for(const l of ls){const p=`${l.cuenta_debito}|${l.cuenta_credito}`;pares.set(p,(pares.get(p)??0)+Number(l.valor));}return{id_comprobante_nic41:1000+i,codigo:`NIC-${nit}-202611-${tipo}-${especie}`,numero_id_tributaria:nit,tipo_hecho:tipo,id_especie:Number(especie),fecha_comprobante:'2026-11-30',lineas:[...pares].map(([p,val])=>({cuenta_debito:p.split('|')[0],cuenta_credito:p.split('|')[1],valor:String(val)})),hash_integridad:`HASH-${nit}-${k}`};});}
// Columnas de los SELECT y dataclasses revisados; valores únicamente para loopback.
function respuestaRealista(ruta,dato){
  const completar=base=>Array.isArray(dato)?dato.map(x=>({...base,...x})):dato;
  if(ruta==='/finanzas/periodos')return completar({tipo_cierre:'MENSUAL',fecha_fin:'2026-11-30',fecha_cierre:null,ultimo_cierre:null});
  if(/^\/finanzas\/activos\/\d+$/.test(ruta))return dato;
  if(ruta==='/finanzas/activos')return completar({tipo:'BOVINO',especie:'Bovino',finca:'Finca QA',clasificacion:'PRODUCTOR',fecha_reconocimiento:'2026-01-01',indicador_reconocimiento:'VALOR_RAZONABLE',es_apertura:false,valor_contable_por_costo:null,costo_base:null,depreciacion_acumulada:null,deterioro_acumulado:null,vida_util_meses:null,razon_sin_mercado:null,fecha_marcacion:null,escenario_costo:null,id_finca:1,id_infraestructura:1,infraestructura:'Corral',costo_adquisicion:'0',origen_financiero:'COMPRA',valor_inicial:'100',valor_razonable_neto:'100',fecha_calculo:null,tiene_valor_estimado:false});
  if(ruta==='/finanzas/precios')return completar({unidad_medida:'kg',fecha_vencimiento:null,evidencia:'QA fixture',justificacion:null,id_precio_corregido:null,estado:'ACTIVO'});
  if(ruta==='/finanzas/lineas')return completar({fecha_hecho:'2026-11-30',id_finca:1,tabla_origen:'variaciones_valor_razonable',id_origen:1,tipo_evidencia:'EVENTO_BIOLOGICO',es_estimacion:false,es_reverso:false,tipo_hecho_corregido:null,id_linea_corregida:null,justificacion:null,id_usuario:1});
  if(/^\/finanzas\/periodos\/\d+\/variaciones$/.test(ruta))return completar({identificador:'QA',tipo_activo:'BOVINO',id_especie:3,especie:'Bovino',finca:'Finca QA',clasificacion:'PRODUCTOR',valor_razonable_anterior:'100',valor_razonable_nuevo:'110',tiene_estimacion:false,fecha_registro:'2026-11-30T12:00:00Z'});
  if(/^\/finanzas\/periodos\/\d+\/mediciones$/.test(ruta))return completar({identificador:'QA',tipo_activo:'BOVINO',id_especie:3,especie:'Bovino',finca:'Finca QA',clasificacion:'PRODUCTOR',valor_razonable_anterior:'4200000.00',variacion_total:'0',ganancia_perdida_transformacion:'0',ganancia_perdida_precio_mercado:'0',tiene_valor_estimado:false,estado:'REGISTRADA',fecha_medicion:'2026-11-30T12:00:00Z'});
  if(/^\/finanzas\/periodos\/\d+\/calculos$/.test(ruta))return completar({identificador:'QA',tipo_activo:'BOVINO',id_especie:3,especie:'Bovino',finca:'Finca QA',clasificacion:'PRODUCTOR',magnitud:'1',unidad_magnitud:'kg',precio_unitario:'1000',valor_razonable_bruto:'1000',costos_venta:'0',valor_neto:'1000',metodo_costo:'MERCADO',estado:'REGISTRADO',tiene_valor_estimado:false,es_producto:false,fecha_calculo:'2026-11-30T12:00:00Z'});
  if(ruta==='/finanzas/costos')return completar({origen_costo:'COMPRA_PROVEEDOR',vehiculo_contable:'GASTO',activo:'QA',estado:'REGISTRADO',politica_capitalizacion:null,justificacion:null,id_origen_m05:null,tercero_nit:null,tercero_dv:null,tercero_razon_social:null,factura_prefijo:null,factura_numero:null,fecha_factura:null,fecha_vencimiento_factura:null,id_grupo_reparto:null,metodo_reparto:null,cuenta_debito:'5100',cuenta_credito:'2200',es_cuenta_manual:false,es_reverso:false,id_usuario:1,fecha_registro:'2026-11-30T12:00:00Z',id_especie:3,id_infraestructura:1,id_finca:1,especie:'Bovino',finca:'Finca QA'});
  if(/^\/finanzas\/periodos\/\d+\/comprobantes$/.test(ruta))return completar({especie:'Bovino',valor_total:'10',fecha_creacion:'2026-11-30T12:00:00Z'});
  if(/^\/finanzas\/periodos\/\d+\/cierre$/.test(ruta))return{periodo:'2026-11',estado:'CERRADO',activos_procesados:7,activos_excluidos:[],comprobantes:[],hash_cierre:'HASH',id_periodo_contable:Number(ruta.split('/')[3]),...dato,reportes:{estado_resultados:{resultado_neto:'0',...dato.reportes.estado_resultados},informe_revelaciones:{id_informe:1,version:1}}};
  if(/^\/activos-biologicos\/\d+\/eventos\/crecimiento$/.test(ruta))return{fase_avanzada:false,...dato};
  if(ruta==='/finanzas/auditoria')return{...dato,eventos:dato.eventos.map(x=>({id_evento:1,modulo:'M06',timestamp_evento:'2026-11-30T12:00:00Z',tipo_actor:'USUARIO',id_usuario:1,nombre_usuario:'QA',id_sistema:null,id_activo_biologico:943,id_periodo_contable:8,datos_anteriores:null,severidad_evento:'INFO',hash_integridad:'HASH',payload_truncado:false,origen_registro:'QA',monto_afectado:null,identificador_activo:'QA',...x}))};
  return dato;
}
function inyectarAjenos(ruta,dato){
  if(!Array.isArray(dato))return dato;
  if(ruta==='/finanzas/periodos')return [...dato,{id_periodo_contable:9999,numero_id_tributaria:null,fecha_inicio:42,fecha_fin:{ajeno:true},estado:null,ultimo_cierre:{fecha_fin:null}}];
  if(ruta==='/finanzas/activos')return [...dato,{id_activo_biologico:9999,id_especie:null,estado:'BAJA',valorado_por_costo:null,depreciacion_acumulada:null}];
  if(ruta==='/finanzas/precios')return [...dato,{id_precio_mercado:9999,id_especie:9999,categoria:null,id_metrica_produccion:null,precio_unitario:{ajeno:true},fecha_vencimiento:null}];
  return dato;
}
function inyectarExtras(dato){if(Array.isArray(dato))return dato.map(inyectarExtras);if(dato&&typeof dato==='object')return Object.fromEntries([...Object.entries(dato).map(([k,v])=>[k,inyectarExtras(v)]),['extra_qa_uno','IGNORAR'],['extra_qa_dos','IGNORAR']]);return dato;}
function fixture(nombre,conExtras=false){let closed=new Set(),costos=[],eventos=[],precios=[{id_precio_mercado:400,id_especie:1,categoria:'PESO_KG',id_metrica_produccion:null,es_aplicado:true,precio_unitario:'1000.00',fuente:'MERCADO_ACTIVO',fecha_vigencia:'2026-11-01'},{id_precio_mercado:435,id_especie:3,categoria:'POR_CABEZA',id_metrica_produccion:null,es_aplicado:true,precio_unitario:'4000000.00',fuente:'MERCADO_ACTIVO',fecha_vigencia:'2026-11-01'}],nextPrice=500,periodos=clone(periodos0),avisos=[],overlap=false,busy=false,requests=0,sandboxDeleted=false,postDeleteHeadersOk=true,postDeleteRequests=0;
const lineas8=[line(17,'VARIACION_VR_TB','GANANCIA',1,'111111111')],lineas219=[],lineas220=[];
const variaciones8=[],preVariaciones=[v(99,'GANANCIA_TRANSFORMACION_BIOLOGICA',17)],med220=[];
const getLineas=id=>id===8?(closed.has(8)?lineas8.filter(x=>x.id_linea_asiento_nic41!==17&&(nombre!=='linea_run_excluida'||x.id_linea_asiento_nic41!==10)):lineas8):id===219?lineas219:id===220?lineas220:[];
const getComp=id=>comprobantes(getLineas(id),id===8?'111111111':id===219?'222222222':'333333333');
const server=http.createServer(async(req,res)=>{if(busy)overlap=true;busy=true;requests++;const u=new URL(req.url,'http://localhost'),p=u.pathname,m=req.method;let body={};for await(const chunk of req){try{body=JSON.parse(chunk.toString());}catch{}}let status=200,data=null,type='application/json';if(sandboxDeleted){postDeleteRequests++;if(req.headers['x-test-run-id']||req.headers['x-sandbox-secret'])postDeleteHeadersOk=false;}try{
if(p==='/sesiones/'&&m==='POST')data={token:token(body.correo_electronico?.startsWith('admin')?2:1)};
else if(p==='/sesiones/me/permisos')data={permisos:(req.headers.authorization?.includes(token(2))?['activos_biologicos:1','activos_biologicos:2']:['cierre_periodo:2','cierre_periodo:5','configuracion_contable:2','configuracion_contable:1','precios_mercado:2','precios_mercado:1','valoracion_activos:2','valoracion_activos:5','costos_activos:2','costos_activos:1','estado_resultados:2','auditoria_financiera:2']).map(x=>({nombre_recurso:x.split(':')[0],id_accion:Number(x.split(':')[1])}))};
else if(p==='/finanzas/periodos')data=nombre==='orden_distinto'?[...periodos].reverse():periodos;
else if(p==='/finanzas/activos')data=nombre==='orden_distinto'?[...activos].reverse():activos;
else if(p==='/finanzas/configuracion')data={general:{pct_umbral_desviacion_precio:'50'},especies:[{id_especie:1,categoria_precio:'PESO_KG'},{id_especie:3,categoria_precio:'POR_CABEZA'}],matriz:matrix};
else if(p==='/finanzas/precios'&&m==='GET')data=precios.filter(x=>Number(x.id_especie)===Number(u.searchParams.get('id_especie')));
else if(p==='/finanzas/precios'&&m==='POST'){status=201;const id=nextPrice++;precios.push({...body,id_precio_mercado:id,id_metrica_produccion:null,es_aplicado:true});data={id_precio_mercado:id};}
else if(/^\/finanzas\/activos\/\d+$/.test(p)){const id=Number(p.split('/')[3]),a=activos.find(x=>x.id_activo_biologico===id);data={activo:{id_activo_biologico:id,id_especie:a.id_especie,id_finca:a.id_finca,numero_id_tributaria:id<1000?'111111111':'222222222',estado:a.estado,id_dispositivo_iot:id===943||id===944||id===946||nombre==='sin_bovino_sin_iot'&&[945,947].includes(id)?849:null}};}
else if(/^\/finanzas\/activos\/\d+\/simulacion$/.test(p))data={es_valido:true,precio:{id_precio_mercado:Number(p.split('/')[3])<1000?400:435}};
else if(/^\/activos-biologicos\/\d+\/ficha-integral$/.test(p))data={peso_actual:'250.00',unidad_peso:'kg'};
else if(/^\/activos-biologicos\/\d+\/metricas$/.test(p))data={items:nombre==='bovino_947_alternativa'&&Number(p.split('/')[2])===945?[]:[{tipo_medicion:'PESO',unidad_medida:'kg',valor_min:'100',valor_max:'400'}]};
else if(/^\/activos-biologicos\/\d+\/eventos$/.test(p)&&m==='GET')data={eventos};
else if(/^\/activos-biologicos\/\d+\/eventos\/crecimiento$/.test(p)&&m==='POST'){status=201;const id=eventos.length+1;eventos.push({id_eventos:id});data={evento:{id_eventos:id}};}
else if(p==='/finanzas/eventos/procesar'){const batch=variaciones8.length===0?[['VARIACION_VR_TB','GANANCIA','GANANCIA_TRANSFORMACION_BIOLOGICA'],['VARIACION_VR_PM','GANANCIA','GANANCIA_PRECIO_MERCADO']]:[['VARIACION_VR_TB','PERDIDA','PERDIDA_TRANSFORMACION_BIOLOGICA'],['VARIACION_VR_PM','PERDIDA','PERDIDA_PRECIO_MERCADO']];for(const [t,s,vtype] of batch){const id=variaciones8.length+1,lineId=id+9;lineas8.push(line(lineId,t,s,1,'111111111'));variaciones8.push(v(id,vtype,lineId));if(nombre==='redondeo_monto'&&variaciones8.length===1)variaciones8[0].monto_variacion='10.01';}data={eventos:1,provisiones_m05:0};}
else if(p==='/finanzas/lineas')data=getLineas(Number(u.searchParams.get('id_periodo_contable')));
else if(/^\/finanzas\/periodos\/\d+\/prevalidacion$/.test(p)){const id=Number(p.split('/')[3]);data={puede_cerrar:true,requiere_autorizacion:id===8&&!closed.has(8),bloqueos:nombre==='prevalidacion_bloqueada'&&id===219?[{codigo:'BLOQUEO'}]:[],activos_sin_precio:[],lineas_sin_trazabilidad:id===8&&!closed.has(8)?[{id_linea:nombre==='pre8_linea_no_preexistente'?999:17,tipo_hecho:'VARIACION_VR_TB'},...(nombre==='linea_tb_run_pendiente'&&variaciones8.length?[{id_linea:10,tipo_hecho:'VARIACION_VR_TB'}]:[])]:[]};}
else if(/^\/finanzas\/periodos\/\d+\/variaciones$/.test(p))data=Number(p.split('/')[3])===8?[...preVariaciones,...variaciones8]:[];
else if(/^\/finanzas\/periodos\/\d+\/mediciones$/.test(p))data=Number(p.split('/')[3])===220?med220:[];
else if(/^\/finanzas\/periodos\/\d+\/calculos$/.test(p))data=[];
else if(/^\/finanzas\/periodos\/\d+\/comprobantes$/.test(p)){const id=Number(p.split('/')[3]);if(m==='GET')data=closed.has(id)?getComp(id):[];else{status=405;data=error('METHOD_NOT_ALLOWED','Method Not Allowed');}}
else if(/^\/finanzas\/periodos\/\d+\/comprobantes\/descarga$/.test(p)){const id=Number(p.split('/')[3]),format=u.searchParams.get('formato');if(format==='csv'){type='text/csv';data=getComp(id).map(x=>x.codigo).join('\n');}else{type='application/pdf';data='%PDF-1.4 LOCAL';}}
else if(p==='/finanzas/costos'&&m==='GET')data=costos.filter(x=>Number(x.id_periodo_contable)===Number(u.searchParams.get('id_periodo_contable')));
else if(p==='/finanzas/costos'&&m==='POST'){status=201;const id=costos.length+1,c={...body,id_registro_costo:id,id_periodo_contable:220};costos.push(c);data={registros:[{id_registro_costo:id}]};}
else if(/^\/finanzas\/periodos\/\d+\/cierre$/.test(p)&&m==='POST'){const id=Number(p.split('/')[3]);if(id===8&&['cierre8_coincide_G32','cierre8_otro_error','cierre8_error_interno_g32'].includes(nombre)||id===219&&nombre==='cierre219_fallido'){status=500;data=error(nombre==='cierre8_error_interno_g32'?'ERROR_INTERNO':'CIERRE_PERIODO_FALLIDO',nombre==='cierre8_otro_error'?'El proceso de cierre fall\u00f3 en el paso 2. FALLO_DISTINTO':'El proceso de cierre fall\u00f3 en el paso 3. TGR-M06-26');}else{closed.add(id);const idNext=id===8?301:id===219?302:id===220?303:304,idCierre=id===8?88:id===219?2190:id===220?2200:3030;periodos.find(x=>x.id_periodo_contable===id).estado='CERRADO';periodos.find(x=>x.id_periodo_contable===id).ultimo_cierre={id_cierre:idCierre,id_usuario_ejecutor:1,fecha_fin:'2026-11-30T12:00:00Z'};periodos.push({id_periodo_contable:idNext,numero_id_tributaria:periodos.find(x=>x.id_periodo_contable===id).numero_id_tributaria,fecha_inicio:'2026-12-01',estado:'ABIERTO'});avisos.push({id_notificacion:avisos.length+1,mensaje:'Cierre'});if(id===8){lineas8.push(line(14,'VARIACION_VR_PM','GANANCIA',1,'111111111'));variaciones8.push(v(5,'GANANCIA_PRECIO_MERCADO',14));}if(id===219){lineas219.push(line(30,'VARIACION_VR_PM','GANANCIA',3,'222222222'),line(31,'DEPRECIACION_ACTIVO_COSTO','UNICO',2,'222222222'));}if(id===220){lineas220.push(line(40,'VARIACION_VR_PM','GANANCIA',3,'333333333'),line(41,'VARIACION_VR_PM','GANANCIA',3,'333333333'),line(42,'VARIACION_VR_PM','GANANCIA',3,'333333333'),line(43,'DEPRECIACION_ACTIVO_COSTO','UNICO',2,'333333333'));for(const aid of [1569,1570])med220.push({id_medicion_posterior:aid,id_activo_biologico:aid,origen_medicion:'CIERRE_PERIODO',valor_razonable_actual:'4200000.00'});}data={id_cierre:idCierre,id_periodo_siguiente:idNext,lineas_excluidas:id===8?[{id_linea:17,tipo_hecho:'VARIACION_VR_TB'},...(nombre==='linea_run_excluida'?[{id_linea:10,tipo_hecho:'VARIACION_VR_TB'}]:[])]:[],reportes:{estado_resultados:{id_estado:id===220?10:id===303?11:12}}};}}
else if(p==='/finanzas/auditoria'){const id=Number(u.searchParams.get('id_periodo_contable'));data={eventos:id===8&&closed.has(8)?[{tipo_evento:'VARIACION_REGISTRADA',id_referencia:4,payload_evento:{id_cierre:null}},{tipo_evento:'MEDICION_POSTERIOR',id_referencia:null,payload_evento:{paso:null,error:null}},{tipo_evento:'VARIACION_REGISTRADA',id_referencia:5,payload_evento:{id_cierre:88}}]:id===8&&['cierre8_coincide_G32','cierre8_otro_error','cierre8_error_interno_g32'].includes(nombre)?[{tipo_evento:'CIERRE_PERIODO_FALLIDO',id_referencia:88,payload_evento:{paso:3,error:nombre==='cierre8_otro_error'?'FALLO_DISTINTO':'TGR-M06-26'}},{tipo_evento:'MEDICION_POSTERIOR',id_referencia:null,payload_evento:{paso:null,error:null}}]:[],total_registros:0};}
else if(p==='/notificaciones')data={items:avisos,total:avisos.length};
else if(/^\/finanzas\/periodos\/\d+\/estados-resultados$/.test(p)){if(nombre==='newman_fallido'&&/PostmanRuntime/.test(req.headers['user-agent']??'')){status=500;data=error('ERROR_INTERNO','fallo Newman local');}else data=closed.has(Number(p.split('/')[3]))?[{id_estado:Number(p.split('/')[3])===220?10:11,resultado_neto:'0'}]:[];}
else if(/^\/finanzas\/estados-resultados\/\d+$/.test(p)){const id=Number(p.split('/')[3]);data={id_estado:id,resultado_neto:'0',componentes:id===10?{costos_mantenimiento:'410.00',...(nombre==='rf93_sin_desglose'?{}:{detalle_costos:{ALIMENTO:'101',MEDICAMENTO:'102',MANO_OBRA:'103',VETERINARIO:'104'}})}:{costos_mantenimiento:'0'}};}
else if(/^\/test-control\/runs\//.test(p)&&m==='DELETE'){sandboxDeleted=true;if(nombre!=='rollback_fallido'){closed=new Set();costos=[];eventos=[];precios=precios.filter(x=>x.id_precio_mercado<500);periodos=clone(periodos0);avisos=[];lineas8.splice(1);lineas219.length=0;lineas220.length=0;variaciones8.length=0;med220.length=0;}data={ok:true};}
else{status=404;data=error('RUTA_NO_ENCONTRADA','fixture route');}
}catch(err){status=500;data=error('ERROR_INTERNO',err.message);}if(status>=400)assert.ok(validarError(data),`fixture HTTP ${status} sin error_respuesta`);if(type==='application/json'){if(status<400)data=respuestaRealista(p,data);if(status<400&&(conExtras||nombre==='datos_ajenos_irregulares'))data=inyectarAjenos(p,data);if(conExtras)data=inyectarExtras(data);}res.writeHead(status,{'Content-Type':type,'X-Test-Run-Id':RUN});res.end(type==='application/json'?JSON.stringify(data):data);busy=false;});
return{server,estado:()=>({overlap,requests,postDeleteHeadersOk,postDeleteRequests})};}
const escenarios=[['exclusion_linea_17',['APROBADO','APROBADO','APROBADO'],true],['pre8_linea_preexistente_distinta_de_9',['APROBADO','APROBADO','APROBADO'],true],['pre8_linea_no_preexistente',['NO_CONCLUYENTE','NO_CONCLUYENTE','NO_CONCLUYENTE'],false],['bovino_sin_iot_elegido',['APROBADO','APROBADO','APROBADO'],true],['bovino_947_alternativa',['APROBADO','APROBADO','APROBADO'],true],['sin_bovino_sin_iot',['NO_CONCLUYENTE','NO_CONCLUYENTE','NO_CONCLUYENTE'],false],['linea_tb_run_pendiente',['NO_CONCLUYENTE','APROBADO','APROBADO'],false],['linea_run_excluida',['RECHAZADO','APROBADO','APROBADO'],true],['conforme',['APROBADO','APROBADO','APROBADO'],true],['campos_extra_reales',['APROBADO','APROBADO','APROBADO'],true],['datos_ajenos_irregulares',['APROBADO','APROBADO','APROBADO'],true],['cierre8_coincide_G32',['RECHAZADO','APROBADO','APROBADO'],true],['cierre8_error_interno_g32',['RECHAZADO','APROBADO','APROBADO'],true],['cierre8_otro_error',['RECHAZADO','APROBADO','APROBADO'],true],['cierre219_fallido',['APROBADO','RECHAZADO','APROBADO'],true],['rf93_sin_desglose',['APROBADO','APROBADO','RECHAZADO'],true],['rf93_clave_alterna',['APROBADO','APROBADO','APROBADO'],true],['redondeo_monto',['APROBADO','APROBADO','APROBADO'],true],['orden_distinto',['APROBADO','APROBADO','APROBADO'],true],['fecha_distinta_9',['APROBADO','APROBADO','APROBADO'],true],['fecha_fuera_periodo',['NO_CONCLUYENTE','NO_CONCLUYENTE','NO_CONCLUYENTE'],false],['prevalidacion_bloqueada',['NO_CONCLUYENTE','NO_CONCLUYENTE','NO_CONCLUYENTE'],false],['rollback_fallido',['APROBADO','APROBADO','APROBADO'],false],['newman_fallido',['APROBADO','APROBADO','APROBADO'],false]];

for(const [nombre,esperados,oficial] of escenarios)for(const conExtras of [false,true]){
  const tmp=fs.mkdtempSync(path.join(os.tmpdir(),'g42-')),dir=path.join(tmp,RUN);
  fs.mkdirSync(dir);
  const archivo=path.join(dir,'contexto_operacion.json');
  fs.writeFileSync(archivo,JSON.stringify({grupo:'G42',run_id:RUN,version:1,intento:1,operacion:'EVALUAR',referencia:'AUT-LOCAL',casos:CASOS}));
  const f=fixture(nombre,conExtras);
  try{
    await new Promise(resolve=>f.server.listen(0,'127.0.0.1',resolve));
    const base=`http://127.0.0.1:${f.server.address().port}`;
    const args=['--operacion','evaluar','--version','1','--intento','1','--run-id',RUN,'--autorizacion','AUT-LOCAL','--contexto',archivo];
    const r=await principal(args,{ensayo:true,fechaEnsayo:nombre==='fecha_distinta_9'?'2026-11-10':nombre==='fecha_fuera_periodo'?'2026-12-01':null,proceso:{QA_AUTORIZADO:'SI',SIGAB_API_TEST_BASE:base,QA_SANDBOX_SECRET:'LOCAL_FAKE',QA_CONTADOR_EMAIL:'local@example.com',QA_CONTADOR_PASSWORD:'local',QA_ADMIN_EMAIL:'admin@example.com',QA_ADMIN_PASSWORD:'local'}});
    assert.deepEqual(CASOS.map(x=>r.casos[x].estado),esperados,JSON.stringify({problemas:r.problemas_tecnicos,casos:r.casos}));
    if(conExtras&&r.contraste_contrato.length)assert(r.campos_extra_observados.some(x=>x.campo.endsWith('.extra_qa_uno')));
    assert.equal(r.oficial,oficial,JSON.stringify({problemas:r.problemas_tecnicos,casos:r.casos,newman:r.newman,cierre:r.cierre}));
    assert.ok(r.contraste_contrato.filter(x=>x.http>=400).every(x=>x.esquema==='error_respuesta'&&x.resultado==='coincide'));
    if(['cierre8_coincide_G32','cierre8_error_interno_g32'].includes(nombre))assert.equal(r.incidencias.find(x=>x.caso===CASOS[0])?.id,'INC-M06-G32-01');
    if(nombre==='cierre8_otro_error')assert.equal(r.incidencias.find(x=>x.caso===CASOS[0])?.id,'INC-M06-G42-021');if(nombre==='rf93_sin_desglose'){const inc=r.incidencias.find(x=>x.caso===CASOS[2]);assert.equal(inc?.id,'INC-M06-G42-01');assert.equal(inc?.severidad,'MEDIA');assert.match(inc?.observado??'',/costos_mantenimiento/);}
    if(nombre==='conforme'){
      assert(!('precondicionCostoAnterior' in r));
      assert(!r.evidencias.some(x=>x.endsWith('.pdf')));
      assert.equal(r.observado['022'].descargas.B.cabecera_pdf,'%PDF');
    }
    assert.equal(f.estado().overlap,false);assert.equal(f.estado().postDeleteHeadersOk,true,'Lecturas posteriores al DELETE enviaron cabeceras de sandbox');if(r.cierre.run.cierre_http===200)assert(f.estado().postDeleteRequests>0);
    assert(r.total_solicitudes_api<=260);
    if(nombre==='redondeo_monto')assert(r.observado['021'].observaciones.some(x=>x.sumaMonto==='10.01'));
    if(nombre==='fecha_fuera_periodo'||nombre==='sin_bovino_sin_iot')assert.equal(r.escrituras.length,0);
    if(nombre==='bovino_sin_iot_elegido'){assert.equal(r.observado.seleccion_bovino.elegido,945);assert.equal(r.observado.peso_semilla.bovino_id,945);assert(r.solicitudes.some(x=>x.ruta==='/activos-biologicos/945/eventos/crecimiento'));assert(r.solicitudes.findIndex(x=>x.ruta==='/finanzas/activos/945')<r.solicitudes.findIndex(x=>x.metodo==='POST'&&x.ruta!=='/sesiones/'));}
    if(nombre==='bovino_947_alternativa'){assert.equal(r.observado.seleccion_bovino.elegido,947);assert(r.solicitudes.some(x=>x.ruta==='/activos-biologicos/947/eventos/crecimiento'));}
    if(nombre==='sin_bovino_sin_iot')assert.match(r.casos[CASOS[0]].motivo,/SIN_BOVINO_SIN_IOT/);
    if(nombre==='linea_tb_run_pendiente'){assert.match(r.casos[CASOS[0]].motivo,/PREVALIDACION_8/);assert(!r.solicitudes.some(x=>x.metodo==='POST'&&x.ruta==='/finanzas/periodos/8/cierre'));}
    if(['pre8_linea_no_preexistente','prevalidacion_bloqueada'].includes(nombre)){
      assert.equal(r.escrituras.length,0);
      assert.equal(r.cierre.rollback.motivo,'SIN_ESCRITURAS');
      assert.equal(r.cierre.rollback.verificado,true);
    }
    if(nombre==='exclusion_linea_17'){
      assert.deepEqual(r.prevalidaciones[8].inicial.lineas_sin_trazabilidad,[{id_linea:17,tipo_hecho:'VARIACION_VR_TB'}]);
      assert.deepEqual(r.prevalidaciones[8].antes_cierre.lineas_sin_trazabilidad,[{id_linea:17,tipo_hecho:'VARIACION_VR_TB'}]);
      assert.deepEqual(r.observado['021'].lineas_excluidas,[{id_linea:17,tipo_hecho:'VARIACION_VR_TB'}]);
      assert(r.observado['021'].variaciones_excluidas.some(x=>x.id_linea===17));
    }
    if(nombre==='linea_run_excluida')assert.match(r.casos[CASOS[0]].motivo,/linea_run_excluida/);
    const presentes=new Set(['resultado.json','TC-M06-G42_resultado.md',...r.evidencias]);
    assert.equal(clasificarRegistro(CAPACIDADES,r,presentes,{runId:RUN,version:1,referencia:'AUT-LOCAL'}),oficial);
    if(oficial){assert.equal(r.newman.codigo,0);assert.equal(r.newman.fallos,0);assert(r.evidencias.includes('newman/newman-G42.json'));}
    console.log(`OK escenario_${nombre}${conExtras?'_extras':''}: 021=${esperados[0]} 022=${esperados[1]} 023=${esperados[2]} oficial=${oficial?'si':'no'} solicitudes=${r.total_solicitudes_api}/260`);
  }finally{await new Promise(resolve=>f.server.close(resolve));fs.rmSync(tmp,{recursive:true,force:true});}
}
