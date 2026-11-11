export const CASOS=['TC-M06-019','TC-M06-020'];
export const IDS={a:'G41-API-019-01',b:'G41-API-020-01'};
export const PRESUPUESTO={solicitudes_totales:200,duracion_segundos:1800};
const valor=x=>{if(x===null||x===undefined||!/^-?\d+(\.\d+)?$/.test(String(x)))throw Error('DECIMAL_INVALIDO');const s=String(x),neg=s[0]==='-',partes=s.replace('-','').split('.');return{n:BigInt(partes.join(''))*(neg?-1n:1n),e:partes[1]?.length??0};};
const escala=(x,e)=>x.n*10n**BigInt(e-x.e);
export const suma=(...xs)=>{const a=xs.map(valor),e=Math.max(...a.map(x=>x.e));return{n:a.reduce((n,x)=>n+escala(x,e),0n),e};};
export const igual=(a,b)=>{try{const x=typeof a==='object'?a:valor(a),y=typeof b==='object'?b:valor(b),e=Math.max(x.e,y.e);return escala(x,e)===escala(y,e);}catch{return false;}};
export const resta=(a,b)=>{const x=valor(a),y=valor(b),e=Math.max(x.e,y.e);return{n:escala(x,e)-escala(y,e),e};};
export const normalizar=x=>String(x??'').replace(/\s+/g,' ').trim().replace(/\.$/,'');
export function prevalidacionLimpia(p){return !!p&&p.puede_cerrar===true&&p.requiere_autorizacion===false&&['bloqueos','activos_sin_precio','lineas_sin_trazabilidad'].every(k=>Array.isArray(p[k])&&p[k].length===0);}
export function evaluar019(d){const f=[];const check=(ok,msg)=>{if(!ok)f.push(msg);};const c=d.cierre??{},p=d.periodo??{},mes=d.mes??'2026-11';
  check(d.http===200&&c.estado==='CERRADO'&&p.estado==='CERRADO'&&!!p.fecha_cierre,'transicion');
  const ev=d.auditoria?.eventos??[];for(const tipo of ['CIERRE_PERIODO_INICIADO','CIERRE_PERIODO_COMPLETADO'])check(ev.some(x=>x.tipo_evento===tipo&&Number(x.id_referencia)===Number(c.id_cierre)),'auditoria_'+tipo);
  const med=d.mediciones??[],vari=d.variaciones??[],lineas=d.lineas??[];
  for(const id of [1569,1570]){const m=med.find(x=>Number(x.id_activo_biologico)===id&&x.origen_medicion==='CIERRE_PERIODO');check(!!m,'medicion_'+id);if(m)for(const k of ['valor_razonable_anterior','valor_razonable_actual','variacion_total','ganancia_perdida_transformacion','ganancia_perdida_precio_mercado'])check(m[k]!==null&&m[k]!==undefined,'campo_'+id+'_'+k);check(d.activos?.find(x=>Number(x.id_activo_biologico)===id)?.valorado_por_costo===false,'metodo_'+id);}
  check(!med.some(x=>Number(x.id_activo_biologico)===1571&&x.origen_medicion==='CIERRE_PERIODO')&&!vari.some(x=>Number(x.id_activo_biologico)===1571&&(Number(x.id_cierre)===Number(c.id_cierre)||x.tipo_evidencia==='CIERRE_PERIODO'))&&!lineas.some(x=>Number(x.id_activo_biologico)===1571&&(Number(x.id_cierre)===Number(c.id_cierre)||x.tipo_evidencia==='CIERRE_PERIODO')),'baja_sin_revaluacion_cierre');
  check(Number(c.activos_procesados)>=4&&Array.isArray(c.activos_excluidos)&&c.activos_excluidos.length===0,'universo');
  for(const id of [1572,1573]){const a=d.activos?.find(x=>Number(x.id_activo_biologico)===id);check(a?.valorado_por_costo===true,'costo_'+id);}
  check(Number(c.id_periodo_siguiente)===Number(d.siguiente?.id_periodo_contable)&&d.siguiente?.estado==='ABIERTO'&&String(d.siguiente?.fecha_inicio).startsWith('2026-12'),'siguiente');
  const antes=new Set((d.avisosAntes??[]).map(x=>x.id_notificacion));check((d.avisosDespues??[]).some(x=>!antes.has(x.id_notificacion)&&normalizar(x.mensaje)===normalizar(`Período ${mes} cerrado: listo para transferir desde Agrofusión`)),'notificacion');
  check(Number(c.reportes?.estado_resultados?.id_estado)>0&&Number(c.reportes?.informe_revelaciones?.id_informe)>0,'reportes_ids');
  check(d.estado?.resultado_neto!==undefined&&d.estado?.resultado_neto!==null&&!!d.revelacion,'reportes_api');return f;}
export function detalle020(d){const f=[],ramas={},cumple=fn=>{try{return fn();}catch{return false;}};for(const id of [1569,1570]){const m=(d.mediciones??[]).find(x=>Number(x.id_activo_biologico)===id&&x.origen_medicion==='CIERRE_PERIODO');if(!m){f.push('medicion_'+id);continue;}const inicio=d.inicios?.[id];const previas=d.primerCierre?(d.previasPorActivo?.[id]??[]):[];ramas[id]={rama:d.primerCierre?(previas.length?'b_mediciones_intermedias':'a_sin_intermedias'):'segundo_cierre',id_medicion_cierre:m.id_medicion_posterior,ids_mediciones_previas:previas.map(x=>x.id_medicion_posterior),inicio_esperado:inicio};
  if(d.primerCierre&&previas.length){const primera=previas.reduce((min,x)=>!min||String(x.fecha_medicion)<String(min.fecha_medicion)||String(x.fecha_medicion)===String(min.fecha_medicion)&&Number(x.id_medicion_posterior)<Number(min.id_medicion_posterior)?x:min,null);if(!igual(primera.valor_razonable_anterior,inicio))f.push('inicio_primera_'+id);if(!cumple(()=>igual(suma(inicio,...previas.map(x=>x.variacion_total),m.variacion_total),m.valor_razonable_actual)))f.push('total_periodo_'+id);}
  else if(!igual(m.valor_razonable_anterior,inicio))f.push('inicio_'+id);
  if(!cumple(()=>igual(m.variacion_total,resta(m.valor_razonable_actual,m.valor_razonable_anterior))))f.push('total_'+id);
  if(!cumple(()=>igual(suma(m.ganancia_perdida_transformacion,m.ganancia_perdida_precio_mercado),m.variacion_total)))f.push('componentes_'+id);
}return{fallos:f,ramas};}
export const evaluar020=d=>detalle020(d).fallos;
