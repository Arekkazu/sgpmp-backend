import http from 'node:http';

export async function simuladorG45(modo='conforme',inyectados=false){
  const peticiones=[];
  const cambios={costo:false,reversion:false,cierre:false};
  const linea=(id,activo,tipo,extra={})=>({id_linea_asiento_nic41:id,id_activo_biologico:activo,estado:'REGISTRADA',tipo_hecho:tipo,sentido:'UNICO',id_especie:1,subtipo_costo:null,valor:'100.00',tipo_evidencia:null,cuenta_debito:'1',cuenta_credito:'2',numero_id_tributaria:'NIT-A',id_periodo_contable:7,estado_trazabilidad:'COMPLETA',...extra});
  const lineas7=[linea(15,944,'RECONOCIMIENTO_DIFERENCIA'),linea(20,949,'VARIACION_VR_PM')];
  const linea8=linea(9,944,'VARIACION_VR_TB',{id_periodo_contable:8});
  const periodo=(id,estado)=>({id_periodo_contable:id,numero_id_tributaria:id===219?'NIT-B':'NIT-A',fecha_inicio:'2026-11-01',fecha_fin:'2026-11-30',fecha_cierre:estado==='CERRADO'?'2026-11-07T00:00:00Z':null,estado,ultimo_cierre:estado==='CERRADO'?{id_cierre:id,id_usuario_ejecutor:1,fecha_fin:'2026-11-07T00:00:00Z',precios_congelados:[]}:null});
  const send=(res,status,data,headers={})=>{res.writeHead(status,{'content-type':'application/json',...headers});res.end(JSON.stringify(data));};
  const server=http.createServer(async(req,res)=>{
    const body=await new Promise(resolve=>{let x='';req.on('data',d=>x+=d);req.on('end',()=>resolve(x?JSON.parse(x):{}));});
    const ruta=req.url.replace(/^\/api/,'');
    peticiones.push({metodo:req.method,ruta,body});
    const eco=req.headers['x-test-run-id']?{'x-test-run-id':req.headers['x-test-run-id']}:{};
    const datos=(x)=>inyectados&&x&&typeof x==='object'&&!Array.isArray(x)?{...x,campo_nuevo_inocuo:1}:x;
    if(req.method==='POST'&&ruta==='/sesiones/')return send(res,200,datos({token:'LOCAL_SIMULADO'}),eco);
    if(req.method==='GET'&&ruta==='/sesiones/me/permisos')return send(res,200,datos({permisos:[['cierre_periodo',5],['cierre_periodo',2],['costos_activos',1],['reconocimiento_inicial',4]].map(([nombre_recurso,id_accion])=>({nombre_recurso,id_accion}))}),eco);
    if(req.method==='DELETE'&&ruta.startsWith('/test-control/runs/')){if(modo==='delete_fallido')return send(res,500,{error_code:'SIM_DELETE',message:'Falló DELETE',fields:[],timestamp:new Date().toISOString()},eco);Object.keys(cambios).forEach(k=>cambios[k]=false);return send(res,200,{},eco);}
    if(req.method==='GET'&&ruta==='/finanzas/periodos')return send(res,200,[periodo(7,modo==='7_abierto'?'ABIERTO':'CERRADO'),periodo(8,cambios.cierre?(modo==='cierre_200'?'CERRADO':'EN_CIERRE'):'ABIERTO'),periodo(219,'CERRADO')],eco);
    if(req.method==='GET'&&ruta==='/finanzas/periodos/8/prevalidacion')return send(res,200,datos({bloqueos:[],activos_sin_precio:[],lineas_sin_trazabilidad:modo==='8_sin_trazabilidad'?[]:[{id_linea:9,tipo_hecho:'VARIACION_VR_TB',id_activo_biologico:944,faltantes:['M02'],nivel_fallo:'ALTO'}],puede_cerrar:true,requiere_autorizacion:true}),eco);
    const mLineas=ruta.match(/^\/finanzas\/lineas\?id_periodo_contable=(\d+)$/);
    if(req.method==='GET'&&mLineas){const id=Number(mLineas[1]);let out=id===7?[...lineas7]:id===8?[linea8]:[];if(id===8&&cambios.reversion&&modo==='conforme')out=[...out,linea(30,949,'AJUSTE_PERIODO_ANTERIOR',{id_periodo_contable:8,id_linea_corregida:20,justificacion:'Corrección contable registrada'})];if(id===7&&cambios.costo&&modo==='costo_201')out=[...out,linea(31,944,'MANO_OBRA_PROPIA')];return send(res,200,out.map(datos),eco);}
    if(req.method==='GET'&&/^\/finanzas\/periodos\/(7|8|219)\/comprobantes$/.test(ruta))return send(res,200,[],eco);
    if(req.method==='GET'&&/^\/finanzas\/periodos\/(7|8|219)\/variaciones$/.test(ruta))return send(res,200,[],eco);
    if(req.method==='GET'&&ruta.startsWith('/finanzas/costos?'))return send(res,200,cambios.costo&&modo==='costo_201'?[{id_registro_costo:99,subtipo_costo:'MANO_OBRA',naturaleza_costo:'MANTENIMIENTO',monto_costo:'50.00',fecha_costo:'2026-11-05',id_periodo_contable:7,id_activo_biologico:944}]:[],eco);
    const activo=ruta.match(/^\/finanzas\/activos\/(944|949)$/);
    if(req.method==='GET'&&activo){
      const id=Number(activo[1]);
      const reconocimientos=modo==='949_sin_reconocimiento'&&id===949?[]:[{id_reconocimiento_inicial:id===944?15:20,id_activo_biologico:id,estado:'CONFIRMADO',id_periodo_contable:modo==='944_otro_periodo'&&id===944?8:7,fecha_reversion:null,justificacion_reversion:null}];
      return send(res,200,datos({activo:{id_activo_biologico:id,identificador:'SIMULADO',tipo:'INDIVIDUAL',id_especie:1,especie:'Simulada',estado:'ACTIVO',id_infraestructura:1,id_finca:463,finca:'Simulada',numero_id_tributaria:'SIMULADO',razon_social:'Simulada',fecha_ingreso:'2026-11-01',origen_financiero:'compra',costo_adquisicion:'100.00',soporte_documental:null,cantidad_actual:null,peso_kg:null,id_evento_peso:null,id_dispositivo_iot:null},reconocimientos,calculos:[],mediciones:[],productos:[],valoracion_costo:null,lineas:[]}),eco);
    }
    if(req.method==='POST'&&ruta==='/finanzas/periodos/8/cierre'){if(modo==='cierre_200'){cambios.cierre=true;return send(res,200,datos({id_cierre:88,id_periodo_contable:8,periodo:'2026-12',estado:'CERRADO',activos_procesados:0,activos_excluidos:[],lineas_excluidas:[],comprobantes:[],hash_cierre:'x',id_periodo_siguiente:9,reportes:{estado_resultados:{},informe_revelaciones:{}}}),eco);}if(modo==='conforme')cambios.cierre=true;return send(res,409,{error_code:'EXCLUSION_REQUIERE_AUTORIZACION',message:'Autorice exclusión',fields:[],timestamp:new Date().toISOString()},eco);}
    if(req.method==='POST'&&ruta==='/finanzas/costos'){if(modo==='costo_201'){cambios.costo=true;return send(res,201,datos({registros:[{id_registro_costo:99}]}),eco);}if(modo==='costo_422_validacion')return send(res,422,{error_code:'VALIDACION_DTO',message:'Solicitud de costo inválida',fields:[],timestamp:new Date().toISOString()},eco);return send(res,modo==='codigo_actual'?422:409,{error_code:'PERIODO_CONTABLE_CERRADO',message:'El período está cerrado',fields:[],timestamp:new Date().toISOString()},eco);}
    if(req.method==='POST'&&ruta==='/finanzas/reconocimientos/949/reversion'){if(modo==='reversion_400_motivo')return send(res,400,{error_code:'MOTIVO_INVALIDO',message:'Motivo de reversión inválido',fields:[],timestamp:new Date().toISOString()},eco);if(modo==='conforme')cambios.reversion=true;return send(res,409,{error_code:'REVERSION_BLOQUEADA',message:'El cierre es dependiente',fields:[],timestamp:new Date().toISOString()},eco);}
    if(req.method==='GET'&&ruta==='/openapi.json')return send(res,modo==='openapi_404'?404:200,modo==='openapi_404'?{error_code:'NO_ENCONTRADO',message:'No existe',fields:[],timestamp:new Date().toISOString()}:{paths:{'/finanzas/ajuste':{post:{}}}},eco);
    if(req.method==='GET'&&ruta==='/docs/openapi.json')return send(res,404,{error_code:'NO_ENCONTRADO',message:'No existe',fields:[],timestamp:new Date().toISOString()},eco);
    return send(res,404,{error_code:'NO_ENCONTRADO',message:ruta,fields:[],timestamp:new Date().toISOString()},eco);
  });
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  return {url:`http://127.0.0.1:${server.address().port}/api`,peticiones,cerrar:()=>new Promise(resolve=>server.close(resolve))};
}
