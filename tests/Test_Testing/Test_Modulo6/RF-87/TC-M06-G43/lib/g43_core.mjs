export const CASOS=['TC-M06-024','TC-M06-025','TC-M06-026','TC-M06-027'];
export const LIMITE={solicitudes_totales:230,cypress_solicitudes:120,duracion_segundos:1800};
export const hoyBogota=()=>new Intl.DateTimeFormat('en-CA',{timeZone:'America/Bogota',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
export const porId=(xs,campo,id)=>xs.find(x=>{try{return Number(x[campo])===Number(id);}catch{return false;}});
// Origen del patrón: TC-M06-G42/lib/g42_core.mjs; aquí solo se compara evidencia observable en este RUN.
export function cierre8CoincideG32(respuesta,auditoria,inicioRun){
  const inicio=Date.parse(inicioRun);
  const instante=x=>{if(typeof x!=='string')return NaN;const fecha=/[zZ]$|[+-]\d\d:?\d\d$/.test(x)?x:`${x.replace(' ','T')}-05:00`;return Date.parse(fecha);};
  return respuesta?.http===500&&Number.isFinite(inicio)&&Array.isArray(auditoria)&&auditoria.some(x=>
    x.tipo_evento==='CIERRE_PERIODO_FALLIDO'&&Number(x.payload_evento?.paso)===3&&
    Number.isFinite(instante(x.timestamp_evento))&&instante(x.timestamp_evento)>=inicio);
}
export const numeroAislado=(mensaje,n)=>new RegExp(`(^|[^\\d])${Number(n)}([^\\d]|$)`).test(String(mensaje??''));
export const calculosUsanPrecio=(calculos,ids,inicial,nuevo)=>ids.every(id=>calculos.some(x=>Number(x.id_activo_biologico)===id&&Number(x.precio_unitario)===Number(inicial)&&Number(x.precio_unitario)!==Number(nuevo)));
export function paresMatrizFaltantes(matriz){
  const necesarios=[['DEPRECIACION_ACTIVO_COSTO','UNICO',423],['VARIACION_VR_PM','GANANCIA',39],['VARIACION_VR_TB','GANANCIA',39],['VARIACION_VR_TB','PERDIDA',39]];
  return necesarios.filter(([tipo,sentido,especie])=>!matriz.some(x=>x.tipo_hecho===tipo&&x.sentido===sentido&&(x.id_especie==null||Number(x.id_especie)===especie)&&x.subtipo_costo==null));
}
export function cuerpoParMatriz(matriz,[tipo_hecho,sentido]){
  // Misma selección de cuentas genéricas de TC-M06-G42/g42.mjs:40.
  const origen=matriz.find(x=>x.sentido===sentido&&x.id_especie==null&&x.subtipo_costo==null&&x.cuenta_debito&&x.cuenta_credito);
  return origen?{tipo_hecho,sentido,id_especie:null,subtipo_costo:null,cuenta_debito:origen.cuenta_debito,cuenta_credito:origen.cuenta_credito}:null;
}
export function precioVigente(xs,especie,categoria,dia){
  const lista=xs.filter(x=>{try{return Number(x.id_especie)===Number(especie)&&x.categoria===categoria&&x.id_metrica_produccion==null;}catch{return false;}});
  for(const fuente of ['MERCADO_ACTIVO','UPRA','ESTIMADA']){
    const orden=lista.filter(x=>x.fuente===fuente&&x.fecha_vigencia<=dia).sort((a,b)=>b.fecha_vigencia.localeCompare(a.fecha_vigencia)||Number(b.id_precio_mercado)-Number(a.id_precio_mercado));
    if(orden[0]&&(!orden[0].fecha_vencimiento||orden[0].fecha_vencimiento>=dia))return orden[0];
  }return null;
}
export const fechaApta=(h,periodos)=>h<'2026-12-01'&&[219,220].every(id=>{const p=porId(periodos,'id_periodo_contable',id);return p&&p.estado==='ABIERTO'&&p.fecha_inicio<=h&&p.fecha_fin>=h;});
export const preInicial=(a,b,c)=>a?.puede_cerrar===true&&a.bloqueos?.length===0&&a.activos_sin_precio?.length===0&&a.lineas_sin_trazabilidad?.some(x=>Number(x.id_linea)===17)&&b?.puede_cerrar===true&&c?.puede_cerrar===true&&[b,c].every(x=>['bloqueos','activos_sin_precio','lineas_sin_trazabilidad'].every(k=>Array.isArray(x[k])&&x[k].length===0));
export function sinCambios(base,actual){
  const iguales=(a,b,k,campos)=>a.every(x=>{const y=porId(b,k,x[k]);return y&&campos.every(c=>String(x[c])===String(y[c]));});
  return base.periodo.estado==='ABIERTO'&&actual.periodo.estado==='ABIERTO'&&
    iguales(base.lineas,actual.lineas,'id_linea_asiento_nic41',['estado','estado_trazabilidad','id_periodo_contable'])&&
    actual.lineas.filter(x=>!porId(base.lineas,'id_linea_asiento_nic41',x.id_linea_asiento_nic41)).every(x=>x.tipo_evidencia!=='CIERRE_PERIODO')&&
    base.comprobantes.length===actual.comprobantes.length&&iguales(base.comprobantes,actual.comprobantes,'id_comprobante_nic41',[])&&
    iguales(base.variaciones,actual.variaciones,'id_variacion_valor_razonable',[])&&
    actual.variaciones.filter(x=>!porId(base.variaciones,'id_variacion_valor_razonable',x.id_variacion_valor_razonable)).every(x=>x.tipo_evidencia!=='CIERRE_PERIODO');
}
export function evaluar(x){
  const esperado={pausa_EN_CIERRE:'EN_CIERRE durante la solicitud de autorización',precio_congelado_ini:'id y fecha_vigencia de P_ini, nunca P_nuevo',mediciones_ini:'cálculos del cierre con P_ini',cierre_autorizado:'HTTP 200',aviso_api:'N y lista completa de activos y especies',no_rollback:'ABIERTO y línea base intacta',si_exclusion:'CERRADO y exclusión PENDIENTE_PRECIO',ui_lista:'lista completa visible',confirmacion_individual:'confirmación del párrafo 30 por activo',costo_revelacion:'método COSTO y revelación RF-92',sin_estimacion_indebida:'activos sin condiciones PENDIENTE_PRECIO',ui_confirmacion:'controles por activo',lista_api:'id de asiento, activo y eslabón incompleto',si_exclusion_027:'línea excluida y trasladada'};
  const falla={};const test=(caso,id,ok)=>{(falla[caso]??=[]).push({id,esperado:esperado[id]??'Conforme al RF-87',observado:x.observados?.[`${caso}.${id}`]??x.observados?.[id]??`Valor observado: ${String(x[id]??ok)}`,estado:ok?'APROBADO':'RECHAZADO'});};
  test('024','pausa_EN_CIERRE',x.pausaEstado==='EN_CIERRE');
  if(x.cierre8?.http===200){test('024','precio_congelado_ini',Number(x.congelado?.id_precio_mercado)===Number(x.pIni?.id_precio_mercado)&&x.congelado?.fecha_vigencia===x.pIni?.fecha_vigencia&&Number(x.congelado?.id_precio_mercado)!==Number(x.pNuevo?.id_precio_mercado));test('024','mediciones_ini',x.medicionesIni===true);}
  else test('024','cierre_autorizado',false);
  test('025','aviso_api',x.aviso25===true);test('025','no_rollback',x.no25===true);test('025','si_exclusion',x.si25===true);test('025','ui_lista',x.ui25===true);
  test('026','confirmacion_individual',x.confirmacion26===true);test('026','costo_revelacion',x.costo26===true);test('026','sin_estimacion_indebida',x.sinEstimacion26===true);test('026','ui_confirmacion',x.ui26===true);
  test('027','lista_api',x.lista27===true);test('027','pausa_EN_CIERRE',x.pausaEstado==='EN_CIERRE');test('027','no_rollback',x.no27===true);test('027','si_exclusion',x.si27===true);test('027','ui_lista',x.ui27===true);
  return Object.fromEntries(Object.entries(falla).map(([c,items])=>[c,{estado:items.every(v=>v.estado==='APROBADO')?'APROBADO':'RECHAZADO',comprobaciones:items}]));
}
