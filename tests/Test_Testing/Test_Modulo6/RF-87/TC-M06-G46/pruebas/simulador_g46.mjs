import http from 'node:http';
import {hashCanonico} from '../g46.mjs';

export async function simuladorG46(modo='conforme',inyectados=false){
  const peticiones=[];let cerrado=false,ultimo=null,deleteHecho=false;
  const hash64='a'.repeat(64),fecha='2026-11-30';
  const lineas=[{cuenta_debito:'1',cuenta_credito:'2',valor:'12.00'}];
  const comprobante={id_comprobante_nic41:5,codigo:'NIC-NIT-C-202611-DEPRECIACION_ACTIVO_COSTO-1',numero_id_tributaria:'NIT-C',tipo_hecho:'DEPRECIACION_ACTIVO_COSTO',id_especie:1,especie:'Especie local',fecha_comprobante:fecha,lineas,valor_total:'12.00',fecha_creacion:'2026-11-30T00:00:00Z'};
  comprobante.hash_integridad=hashCanonico({codigo:comprobante.codigo,fecha,lineas});
  const codigos=[{codigo:comprobante.codigo,hash:comprobante.hash_integridad,valor_total:'12.00'}];
  const payload={comprobantes:codigos,activos_procesados:5,excluidos:[],hash_cierre:hashCanonico({periodo:220,comprobantes:codigos,excluidos:[]}),reportes:{estado_resultados:{},informe_revelaciones:{}}};
  const idCierre=88;
  const valoracion_costo={id_valoracion_por_costo:7,escenario_activacion:'SIN_MERCADO',costos_adquisicion:'120.00',vida_util_meses:60,depreciacion_acumulada:'12.00',deterioro_acumulado:'0.00',valor_contable_por_costo:'108.00',razon_sin_mercado:'Sin cotización',es_activa:true,fecha_marcacion:'2026-11-01T00:00:00Z'};
  const asignaciones=[[34,'MANO_OBRA_PROPIA','158405','250505'],[49,'DEPRECIACION_ACTIVO_COSTO','516005','159205']].filter(([id])=>modo!=='matriz_49_inactiva'||id!==49).map(([id_asignacion_cuenta_contable,tipo_hecho,cuenta_debito,cuenta_credito])=>({id_asignacion_cuenta_contable,tipo_hecho,sentido:'UNICO',id_especie:null,subtipo_costo:null,cuenta_debito,cuenta_credito}));
  const event=(id,tipo,p,idref=idCierre)=>({id_evento:id,tipo_evento:tipo,modulo:'M06',timestamp_evento:'2026-11-10T07:05:00Z',tipo_actor:'USUARIO',id_usuario:141,nombre_usuario:'Usuario local',id_sistema:null,id_activo_biologico:null,id_periodo_contable:220,id_referencia:idref,payload_evento:p,datos_anteriores:null,severidad_evento:'INFORMATIVA',hash_integridad:hash64,payload_truncado:false,origen_registro:'REPOSITORIO',monto_afectado:null,identificador_activo:null});
  const inicios=()=>modo==='sin_iniciado'?[]:[event(101,'CIERRE_PERIODO_INICIADO',{autorizar_exclusiones:false,incluir_activos_sin_precio:false,advertencias:{bloqueos:[],activos_sin_precio:[],lineas_sin_trazabilidad:[],puede_cerrar:true,requiere_autorizacion:false}})];
  const completos=()=>[event(104,'CIERRE_PERIODO_COMPLETADO',{...payload,excluidos:modo==='hash_recalculo_distinto'?[{motivo:'local'}]:[],hash_cierre:modo==='hash_publicados_distintos'?'b'.repeat(64):payload.hash_cierre})];
  const send=(res,status,data,eco={})=>{res.writeHead(status,{'content-type':'application/json',...eco});res.end(JSON.stringify(data));};
  const server=http.createServer(async(req,res)=>{
    let raw='';for await(const x of req)raw+=x;const body=raw?JSON.parse(raw):{};
    const ruta=req.url.replace(/^\/api/,'');peticiones.push({metodo:req.method,ruta,body,conRun:Boolean(req.headers['x-test-run-id'])});
    const eco=req.headers['x-test-run-id']?{'x-test-run-id':req.headers['x-test-run-id']}:{};
    const extra=x=>inyectados&&x&&typeof x==='object'&&!Array.isArray(x)?{...x,campo_nuevo_inocuo:'ok'}:x;
    if(req.method==='POST'&&ruta==='/sesiones/')return send(res,200,extra({token:'LOCAL_SIMULADO'}),eco);
    if(req.method==='GET'&&ruta==='/sesiones/me/permisos')return send(res,200,{permisos:[['cierre_periodo',5],['cierre_periodo',2],['auditoria_financiera',2]].map(([nombre_recurso,id_accion])=>({nombre_recurso,id_accion}))},eco);
    if(req.method==='DELETE'&&ruta.startsWith('/test-control/runs/')){deleteHecho=true;if(modo==='delete_fallido')return send(res,500,{error_code:'SIM_DELETE',message:'Falló DELETE',fields:[],timestamp:new Date().toISOString()},eco);cerrado=false;ultimo=null;return send(res,200,{},eco);}
    if(req.method==='GET'&&ruta==='/finanzas/periodos')return send(res,200,[{id_periodo_contable:220,numero_id_tributaria:'NIT-C',tipo_cierre:'MENSUAL',fecha_inicio:'2026-11-01',fecha_fin:fecha,fecha_cierre:cerrado?'2026-11-30T00:00:00Z':null,estado:modo==='220_cerrado_tercero'?'CERRADO':cerrado?'CERRADO':'ABIERTO',ultimo_cierre:ultimo},{id_periodo_contable:7,numero_id_tributaria:'NIT-A',tipo_cierre:'MENSUAL',fecha_inicio:'2026-10-01',fecha_fin:'2026-10-31',fecha_cierre:'2026-10-31T00:00:00Z',estado:'CERRADO',ultimo_cierre:{id_cierre:1,id_usuario_ejecutor:141,hash_cierre:hash64}},{id_periodo_contable:219,numero_id_tributaria:'NIT-B',tipo_cierre:'MENSUAL',fecha_inicio:'2026-10-01',fecha_fin:'2026-10-31',fecha_cierre:'2026-10-31T00:00:00Z',estado:'CERRADO',ultimo_cierre:{id_cierre:43,id_usuario_ejecutor:141,hash_cierre:hash64}},...(cerrado?[{id_periodo_contable:221,numero_id_tributaria:'NIT-C',tipo_cierre:'MENSUAL',fecha_inicio:'2026-12-01',fecha_fin:'2026-12-31',fecha_cierre:null,estado:'ABIERTO',ultimo_cierre:null}]:[])],eco);
    if(req.method==='GET'&&ruta==='/finanzas/periodos/220/prevalidacion')return send(res,200,extra({bloqueos:[],lineas_sin_trazabilidad:[],activos_sin_precio:[],puede_cerrar:true,requiere_autorizacion:false}),eco);
    if(req.method==='GET'&&ruta==='/finanzas/configuracion')return send(res,200,extra({general:{},especies:[],costos_venta:[],matriz:asignaciones,lineas_pendientes_cuenta:0}),eco);
    if(req.method==='GET'&&ruta==='/finanzas/lineas?id_periodo_contable=220')return send(res,200,[],eco);
    if(req.method==='GET'&&ruta==='/finanzas/periodos/220/comprobantes')return send(res,200,cerrado?[extra(comprobante)]:[],eco);
    if(req.method==='GET'&&ruta==='/finanzas/periodos/220/variaciones')return send(res,200,[],eco);
    if(req.method==='GET'&&ruta==='/finanzas/activos/1573')return send(res,200,extra({activo:{id_activo_biologico:1573,estado:'ACTIVO',id_finca:466},reconocimientos:[],calculos:[],mediciones:[],productos:[],valoracion_costo,lineas:[]}),eco);
    if(req.method==='POST'&&ruta==='/finanzas/periodos/220/cierre'){if(modo==='cierre_409')return send(res,409,{error_code:'SIM_409',message:'No cerró',fields:[],timestamp:new Date().toISOString()},eco);cerrado=true;ultimo={id_cierre:idCierre,estado:'COMPLETADO',paso_actual:9,activos_procesados:5,activos_pendientes:0,activos_excluidos:[],precios_congelados:[],error_detalle:null,fecha_inicio:'2026-11-30T00:00:00Z',fecha_fin:'2026-11-30T00:00:01Z',tiempo_ejecucion_ms:1000,id_usuario_ejecutor:141,hash_cierre:payload.hash_cierre};return send(res,200,extra({id_cierre:idCierre,id_periodo_contable:220,periodo:'2026-11',estado:'CERRADO',activos_procesados:5,activos_excluidos:[],lineas_excluidas:[],comprobantes:codigos,hash_cierre:payload.hash_cierre,reportes:{estado_resultados:{},informe_revelaciones:{}},id_periodo_siguiente:221}),eco);}
    if(req.method==='GET'&&ruta.startsWith('/finanzas/auditoria?')){
      const q=new URL('http://localhost'+ruta).searchParams,id=Number(q.get('id_periodo_contable'));
      if(id!==220)return send(res,200,{total_registros:2,pagina_actual:1,registros_por_pagina:500,resumen_severidad:{},eventos:[event(20,'CIERRE_PERIODO_INICIADO',{},id===7?1:43),event(21,'CIERRE_PERIODO_COMPLETADO',{hash_cierre:hash64},id===7?1:43)]},eco);
      let ev=[];if(cerrado){ev=[...inicios(),event(102,'VARIACION_REGISTRADA',{id_evento:null,id_cierre:modo==='variacion_sin_id_cierre'?null:idCierre}),event(103,'DEPRECIACION_REGISTRADA',{}) ,...completos()];if(modo==='sin_variaciones_ni_depreciacion')ev=ev.filter(x=>!['VARIACION_REGISTRADA','DEPRECIACION_REGISTRADA'].includes(x.tipo_evento));if(modo==='payload_truncado'){const completo=ev.find(x=>x.tipo_evento==='CIERRE_PERIODO_COMPLETADO');completo.payload_truncado=true;completo.payload_evento={resumen:JSON.stringify(completo.payload_evento).slice(0,100),payload_truncado:true};}}
      ev.reverse();const pagina=Number(q.get('pagina')??1),tamano=Number(q.get('tamano')??100);return send(res,200,{total_registros:ev.length,pagina_actual:pagina,registros_por_pagina:tamano,resumen_severidad:{},eventos:ev.slice((pagina-1)*tamano,pagina*tamano)},eco);
    }
    return send(res,404,{error_code:'NO_ENCONTRADO',message:ruta,fields:[],timestamp:new Date().toISOString()},eco);
  });
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  return {url:`http://127.0.0.1:${server.address().port}/api`,peticiones,get deleteHecho(){return deleteHecho;},cerrar:()=>new Promise(resolve=>server.close(resolve))};
}
