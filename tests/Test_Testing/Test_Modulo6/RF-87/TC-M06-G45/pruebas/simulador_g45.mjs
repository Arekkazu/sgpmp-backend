import http from 'node:http';

export async function simuladorG45(modo='conforme',inyectados=false){
  const peticiones=[];
  const estado={266:'ABIERTO',241:'ABIERTO',220:'ABIERTO',7:'CERRADO',8:'EN_CIERRE',219:'CERRADO',260:'ABIERTO'};
  let cierre31=0,ajuste=false,costoPausa=false,costoCerrado=false,rev=false,otroPeriodo=false,admin=false,siguienteCreado=false,ultimoEvento=9000;
  const eventos=[],mediciones=[];
  const finca={266:472,241:468,220:467};
  const linea=(id,periodo,activo,tipo,extra={})=>({id_linea_asiento_nic41:id,id_activo_biologico:activo,estado:[266,241,220].includes(periodo)?'VERIFICACION_PENDIENTE':'REGISTRADA',tipo_hecho:tipo,sentido:'UNICO',id_especie:1,subtipo_costo:null,valor:'100.00',tipo_evidencia:null,cuenta_debito:'1',cuenta_credito:'2',numero_id_tributaria:'SIMULADO',id_periodo_contable:periodo,estado_trazabilidad:'VERIFICADO',...extra});
  const lineas={266:[],7:[linea(101,7,944,'RECONOCIMIENTO_DIFERENCIA')],8:[],219:[linea(893,219,1568,'RECONOCIMIENTO_DIFERENCIA'),linea(2625,219,1568,'MANO_OBRA_PROPIA'),linea(2628,219,1567,'DEPRECIACION_ACTIVO_COSTO')],220:[linea(2001,220,1569,'VARIACION_VR_TB')],241:[linea(2401,241,1831,'VARIACION_VR_TB')],260:[],270:[]};
  const periodo=id=>({id_periodo_contable:id,numero_id_tributaria:'SIMULADO',fecha_inicio:id===260?'2026-12-01':'2026-11-01',fecha_fin:id===260?'2026-12-31':'2026-11-30',fecha_cierre:estado[id]==='CERRADO'?'2026-11-07T00:00:00Z':null,estado:estado[id],ultimo_cierre:id===8?{id_cierre:67,estado:'EN_PROCESO',paso_actual:3,fecha_fin:null,precios_congelados:modo==='266_pausable'?[{id_especie:39,id_precio_mercado:44}]:null}:cierre31&&[266,241,220].includes(id)?{id_cierre:91,estado:estado[id]==='CERRADO'?'COMPLETADO':'EN_PROCESO',paso_actual:estado[id]==='EN_CIERRE'?3:9,fecha_fin:null,precios_congelados:modo==='266_pausable'?[{id_especie:39,id_precio_mercado:44}]:null}:null});
  const error=(code,message='Error')=>({error_code:code,message,fields:[],timestamp:new Date().toISOString()});
  const send=(res,http,data,headers={})=>{res.writeHead(http,{'content-type':'application/json',...headers});res.end(JSON.stringify(data));};
  const server=http.createServer(async(req,res)=>{
    const body=await new Promise(resolve=>{let raw='';req.on('data',x=>raw+=x);req.on('end',()=>resolve(raw?JSON.parse(raw):{}));});
    const ruta=req.url.replace(/^\/api/,'');
    peticiones.push({metodo:req.method,ruta,actor:req.headers.authorization==='Bearer ADMIN_LOCAL'?'ADMIN':'CONTADOR'});
    const eco=req.headers['x-test-run-id']?{'x-test-run-id':req.headers['x-test-run-id']}:{};
    const extra=x=>inyectados&&x&&typeof x==='object'&&!Array.isArray(x)?{...x,campo_nuevo_inocuo:1}:x;
    if(req.method==='POST'&&ruta==='/sesiones/'){admin=String(body.correo_electronico).includes('admin');return send(res,200,extra({token:admin?'ADMIN_LOCAL':'CONTADOR_LOCAL'}),eco);}
    if(req.method==='GET'&&ruta==='/sesiones/me/permisos'){
      const esAdmin=req.headers.authorization==='Bearer ADMIN_LOCAL';const permisos=modo==='permisos'?[]:(esAdmin?(modo==='admin_sin_permiso'?[]:[['activos_biologicos',1]]):[['cierre_periodo',5],['cierre_periodo',2],['costos_activos',1],['reconocimiento_inicial',4],['valoracion_activos',5],['valoracion_activos',2],['auditoria_financiera',2]]).map(([nombre_recurso,id_accion])=>({nombre_recurso,id_accion}));
      return send(res,200,extra({permisos}),eco);
    }
    if(req.method==='DELETE'&&ruta.startsWith('/test-control/runs/')){
      if(modo==='delete_fallido')return send(res,500,error('SIM_DELETE'),eco);
      Object.assign(estado,{266:'ABIERTO',241:'ABIERTO',220:'ABIERTO',7:'CERRADO',8:'EN_CIERRE',219:'CERRADO',260:'ABIERTO'});cierre31=0;ajuste=false;costoPausa=false;costoCerrado=false;rev=false;otroPeriodo=false;siguienteCreado=false;eventos.length=0;mediciones.length=0;
      return send(res,200,{},eco);
    }
    if(req.method==='GET'&&ruta==='/finanzas/configuracion')return send(res,200,extra({general:{},especies:[{id_especie:39,categoria_precio:modo==='categorias_null'?null:'PESO_KG'},{id_especie:422,categoria_precio:modo==='categorias_null'?null:'POR_CABEZA'},{id_especie:544,categoria_precio:'POR_CABEZA'}],costos_venta:[],matriz:[]}),eco);
    if(req.method==='GET'&&ruta==='/finanzas/periodos')return send(res,200,[7,8,219,220,241,260,266,...(otroPeriodo?[261]:[]),...(siguienteCreado?[270]:[])].map(periodo),eco);
    const previa=ruta.match(/^\/finanzas\/periodos\/(266|241|220)\/prevalidacion$/);
    if(req.method==='GET'&&previa){const id=Number(previa[1]),caso266=modo.startsWith('266_'),caso220=modo.startsWith('220_'),pausable=caso266?id===266:caso220?(modo==='220_no_price'?id===266:id===220):modo==='sin_pausa'?false:modo==='241_no_pausable'?id===220:id!==266;
      return send(res,200,extra({bloqueos:pausable?[]:[{codigo:'BLOQUEO',mensaje:'No pausable'}],activos_sin_precio:pausable&&((caso266&&id===266)||(modo==='220_no_price'&&id===266))?[{id_activo_biologico:1644,id_especie:544}]:pausable&&id===220&&(caso220||modo==='241_no_pausable')&&modo!=='220_no_price'?[{id_activo_biologico:1569,id_especie:422},{id_activo_biologico:1570,id_especie:422},{id_activo_biologico:1571,id_especie:422}]:[],lineas_sin_trazabilidad:pausable&&id!==266?[{id_linea:lineas[id][0].id_linea_asiento_nic41,tipo_hecho:'VARIACION_VR_TB',id_activo_biologico:lineas[id][0].id_activo_biologico,faltantes:['M02'],nivel_fallo:'ALTO'}]:[],puede_cerrar:true,requiere_autorizacion:true}),eco);
    }
    const mLineas=ruta.match(/^\/finanzas\/lineas\?id_periodo_contable=(\d+)$/);
    if(req.method==='GET'&&mLineas){const id=Number(mLineas[1]);let out=[...(lineas[id]??[])];if(id===260&&ajuste)out.push(linea(3000,260,1568,'AJUSTE_PERIODO_ANTERIOR',{id_linea_corregida:2625,justificacion:'Ajuste QA autorizado por error del per\u00edodo anterior'}));if(id===261&&ajuste)out.push(linea(3000,261,1568,'AJUSTE_PERIODO_ANTERIOR',{id_linea_corregida:2625,justificacion:'Ajuste QA autorizado por error del per\u00edodo anterior'}));if(id===7&&costoCerrado)out.push(linea(4000,7,944,'MANO_OBRA_PROPIA'));if([266,241,220].includes(id)&&costoPausa)out.push(linea(4001,id,lineas[id][0].id_activo_biologico,'MANO_OBRA_PROPIA'));if(modo==='266_lineas')out.push(...mediciones.filter(x=>x.id_periodo_contable===id).map(x=>linea(90000+x.id_evento,id,1644,'VARIACION_VR_TB',{id_origen:70000+x.id_evento,fecha_hecho:x.fecha_medicion.slice(0,10)})));return send(res,200,out.map(extra),eco);}
    if(req.method==='GET'&&/^\/finanzas\/periodos\/\d+\/(comprobantes|variaciones)$/.test(ruta)){const m=ruta.match(/^\/finanzas\/periodos\/(\d+)\/variaciones$/);return send(res,200,modo==='266_lineas'&&m?mediciones.filter(x=>x.id_periodo_contable===Number(m[1])).map(x=>({id_variacion_valor_razonable:70000+x.id_evento,id_activo_biologico:1644,id_evento:x.id_evento,id_periodo_contable:x.id_periodo_contable})):[],eco);}
    const mMed=ruta.match(/^\/finanzas\/periodos\/(\d+)\/mediciones\?id_evento=(\d+)$/);
    if(req.method==='GET'&&mMed)return send(res,200,mediciones.filter(x=>x.id_periodo_contable===Number(mMed[1])&&x.id_evento===Number(mMed[2])),eco);
    if(req.method==='GET'&&ruta.startsWith('/finanzas/costos?')){const id=Number(new URL('http://local'+ruta).searchParams.get('id_activo_biologico'));return send(res,200,[...(costoPausa&&[1644,3001,3002].includes(id)?[{id_registro_costo:4001,subtipo_costo:'MANO_OBRA',naturaleza_costo:'MANTENIMIENTO',monto_costo:'50.00',fecha_costo:'2026-11-13',id_periodo_contable:id===1644?266:id===3001?241:220,id_activo_biologico:id}]:[]),...(costoCerrado&&id===944?[{id_registro_costo:4000,subtipo_costo:'MANO_OBRA',naturaleza_costo:'MANTENIMIENTO',monto_costo:'50.00',fecha_costo:'2026-11-05',id_periodo_contable:7,id_activo_biologico:id}]:[])],eco);}
    const activo=ruta.match(/^\/finanzas\/activos\/(\d+)$/);
    if(req.method==='GET'&&activo){const id=Number(activo[1]);if(id===1644&&modo==='266_no_access')return send(res,404,error('SIN_ACCESO'),eco);const hist=[1644,944,949,1831,1832,1833,1627,1569,1570,1571].includes(id)?[{id_reconocimiento_inicial:id===944?15:id===949?20:30,id_activo_biologico:id,estado:'CONFIRMADO',id_periodo_contable:7,fecha_reversion:null,justificacion_reversion:null}]:[];return send(res,200,extra({activo:{id_activo_biologico:id,estado:modo==='1831_no_apto'&&id===1831?'BAJA':'ACTIVO',id_especie:id===1644?544:[1569,1570,1571].includes(id)?422:39,id_finca:id===1644?472:[1831,1832,1833,1627].includes(id)?468:[1569,1570,1571].includes(id)?467:463},reconocimientos:hist,calculos:[],mediciones:[],productos:[],valoracion_costo:null,lineas:[]}),eco);}
    const ficha=ruta.match(/^\/activos-biologicos\/(\d+)\/ficha-integral$/);
    if(req.method==='GET'&&ficha)return send(res,200,{estado_actual:'ACTIVO',tipo:Number(ficha[1])===1644?'POBLACIONAL':'INDIVIDUAL',cantidad_actual:Number(ficha[1])===1644?1:null,fase_activa:Number(ficha[1])===1644?995:null,peso_actual:modo.startsWith('266_')&&Number(ficha[1])===1644?null:Number(ficha[1])===1831?360:100,fecha_ultimo_peso:'2026-11-11',unidad_peso:'kg'},eco);
    const histM=ruta.match(/^\/activos-biologicos\/(\d+)\/eventos$/);
    if(req.method==='GET'&&histM)return send(res,200,{id_activo_biologico:Number(histM[1]),total:eventos.filter(x=>x.id_activo_biologico===Number(histM[1])).length,eventos:eventos.filter(x=>x.id_activo_biologico===Number(histM[1]))},eco);
    const crecimiento=ruta.match(/^\/activos-biologicos\/(\d+)\/eventos\/crecimiento$/);
    if(req.method==='POST'&&crecimiento){if(req.headers.authorization!=='Bearer ADMIN_LOCAL')return send(res,403,error('PERMISO'),eco);if(modo==='220_growth_422'&&Number(crecimiento[1])===1569)return send(res,422,error('SIN_FASE_ACTIVA','No hay fase activa para registrar crecimiento.'),eco);if(Number(crecimiento[1])===1644&&!(body.tipo_medicion==='PESO'&&body.unidad_medida==='kg'&&Number(body.valor_medicion)===Number(body.nuevo_peso_promedio)&&body.cantidad_medida===1&&body.tipo_agregacion==='PROMEDIO'))return send(res,422,error('LOTE_INCOMPLETO'),eco);if(Number(crecimiento[1])!==1644&&body.tipo_agregacion!=null)return send(res,422,error('AGREGACION_NO_PERMITIDA'),eco);const evento={id_eventos:++ultimoEvento,id_activo_biologico:Number(crecimiento[1]),fecha:body.fecha,crecimiento:{valor_medicion:body.valor_medicion}};eventos.push(evento);return send(res,201,{evento,fase_avanzada:false},eco);}
    if(req.method==='POST'&&ruta==='/finanzas/eventos/procesar'){
      let encolados=0,procesados=0;
      for(const ev of eventos.filter(x=>!x.procesado)){
        const id=ev.id_activo_biologico===1644?266:[1831,1832,1833,1627].includes(ev.id_activo_biologico)?241:220;
        if(estado[id]==='EN_CIERRE'&&!['m02_durante_cierre','266_pause_med','220_pause_med'].includes(modo)){encolados++;continue;}
        let destino=estado[id]==='CERRADO'?270:id;
        if(modo==='b_otro_periodo'&&estado[id]==='ABIERTO')destino=270;
        if(['m02_durante_cierre','266_pause_med','220_pause_med'].includes(modo)&&estado[id]==='EN_CIERRE')destino=id;
        if(['a_mismo_periodo','266_a_closed'].includes(modo)&&estado[id]==='CERRADO')destino=id;
        if(modo!=='266_no_audit')mediciones.push({id_evento:ev.id_eventos,id_periodo_contable:destino,id_activo_biologico:ev.id_activo_biologico,fecha_medicion:ev.fecha,variacion_total:'5.00'});ev.procesado=true;procesados++;
      }
      return send(res,200,modo==='cola_no_visible'?{eventos:{},provisiones_m05:{}}:{eventos:{ENCOLADO_CIERRE:encolados,PROCESADO:procesados},provisiones_m05:{}},eco);
    }
    const cierre=ruta.match(/^\/finanzas\/periodos\/(266|241|220)\/cierre$/);
    if(req.method==='POST'&&cierre){const id=Number(cierre[1]);cierre31++;
      if(body.autorizar_exclusiones){if(modo==='a_no_cerrado')return send(res,409,error('CIERRE_NO_TERMINADO'),eco);estado[id]='CERRADO';estado[270]='ABIERTO';siguienteCreado=true;return send(res,200,extra({id_cierre:91,id_periodo_contable:id,periodo:'2026-11',estado:'CERRADO',activos_procesados:0,activos_excluidos:id===266?[{id_activo_biologico:1644,estado:'PENDIENTE_PRECIO'}]:id===220?[1569,1570,1571].map(id_activo_biologico=>({id_activo_biologico,estado:'PENDIENTE_PRECIO'})):[],lineas_excluidas:[],comprobantes:[],hash_cierre:'sim',id_periodo_siguiente:270,reportes:{estado_resultados:{},informe_revelaciones:{}}}),eco);}
      estado[id]='EN_CIERRE';return send(res,409,error('EXCLUSION_REQUIERE_AUTORIZACION'),eco);
    }
    const cancel=ruta.match(/^\/finanzas\/periodos\/(266|241|220)\/cierre\/cancelacion$/);
    if(req.method==='POST'&&cancel){estado[Number(cancel[1])]='ABIERTO';return send(res,200,{},eco);}
    if(req.method==='POST'&&ruta==='/finanzas/costos'){
      if(Number(body.id_activo_biologico)===944){if(modo==='costo_422')return send(res,422,error('PERIODO_CONTABLE_CERRADO'),eco);if(modo==='costo_cerrado_201'){costoCerrado=true;return send(res,201,{registros:[{id_registro_costo:4000}]},eco);}return send(res,409,error('PERIODO_CONTABLE_CERRADO'),eco);}
      if(modo==='costo_pausa_201'){costoPausa=true;return send(res,201,{registros:[{id_registro_costo:4001}]},eco);}
      return send(res,409,error('PERIODO_EN_CIERRE'),eco);
    }
    if(req.method==='POST'&&ruta==='/finanzas/reconocimientos/949/reversion')return send(res,409,error('REVERSION_BLOQUEADA'),eco);
    if(req.method==='POST'&&ruta==='/finanzas/lineas-asiento/2625/ajustes'){ajuste=true;if(modo==='ajuste_nuevo_periodo')otroPeriodo=true;return send(res,201,extra({id_linea_asiento_nic41:3000,id_linea_corregida:2625,id_periodo_contable:otroPeriodo?261:260,periodo_corregido:'2026-11'}),eco);}
    if(req.method==='GET'&&ruta.startsWith('/finanzas/auditoria?')){const q=new URL('http://local'+ruta).searchParams;const id=Number(q.get('id_activo_biologico'));const propios=modo==='266_lineas'?[]:mediciones.filter(x=>x.id_activo_biologico===id).map((x,i)=>({id_evento:80000+i,tipo_evento:modo.startsWith('266_')?'MEDICION_PENDIENTE':'MEDICION_SIN_VARIACION',id_activo_biologico:id,id_periodo_contable:x.id_periodo_contable,id_referencia:x.id_evento,payload_evento:{id_evento:x.id_evento}}));const otros=ajuste?[{tipo_evento:'LINEA_ASIENTO_REGISTRADA',payload_evento:{ajuste_periodo_anterior:true,id_linea_corregida:2625,justificacion:'Ajuste QA autorizado por error del per\u00edodo anterior'}}]:[];const todos=id?propios:otros;return send(res,200,extra({total_registros:todos.length,eventos:todos}),eco);}
    return send(res,404,error('NO_ENCONTRADO',ruta),eco);
  });
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  return {url:'http://127.0.0.1:'+server.address().port+'/api',peticiones,cerrar:()=>new Promise(resolve=>server.close(resolve))};
}

