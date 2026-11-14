export const CASOS=['TC-M06-019'];
export const IDS={a:'G41-API-019-01'};
export const PRESUPUESTO={solicitudes_totales:130,duracion_segundos:1800};
export const normalizar=x=>String(x??'').replace(/\.$/,'');
export function prevalidacionLimpia(p){return !!p&&p.puede_cerrar===true&&p.requiere_autorizacion===false&&['bloqueos','activos_sin_precio','lineas_sin_trazabilidad'].every(k=>Array.isArray(p[k])&&p[k].length===0);}
export function evaluar019(d,clasificacion){const f=[];const check=(ok,msg)=>{if(!ok)f.push(msg);};const c=d.cierre??{},p=d.periodo??{},mes=d.mes;
  check(d.http===200&&c.estado==='CERRADO'&&p.estado==='CERRADO'&&!!p.fecha_cierre,'transicion');
  const ev=d.auditoria?.eventos??[];for(const tipo of ['CIERRE_PERIODO_INICIADO','CIERRE_PERIODO_COMPLETADO'])check(ev.some(x=>x.tipo_evento===tipo&&Number(x.id_referencia)===Number(c.id_cierre)),'auditoria_'+tipo);
  const med=d.mediciones??[],vari=d.variaciones??[],lineas=d.lineas??[];
  const vr=clasificacion?.VR??[1569,1570],costo=clasificacion?.COSTO??[1572,1573];
  for(const id of vr){const m=med.find(x=>Number(x.id_activo_biologico)===id&&x.origen_medicion==='CIERRE_PERIODO');check(!!m,'medicion_'+id);if(m)for(const k of ['valor_razonable_anterior','valor_razonable_actual','variacion_total','ganancia_perdida_transformacion','ganancia_perdida_precio_mercado'])check(m[k]!==null&&m[k]!==undefined,'campo_'+id+'_'+k);check(d.activos?.find(x=>Number(x.id_activo_biologico)===id)?.valorado_por_costo===false,'metodo_'+id);}
  check(!med.some(x=>Number(x.id_activo_biologico)===1571&&x.origen_medicion==='CIERRE_PERIODO')&&!vari.some(x=>Number(x.id_activo_biologico)===1571&&(Number(x.id_cierre)===Number(c.id_cierre)||x.tipo_evidencia==='CIERRE_PERIODO'))&&!lineas.some(x=>Number(x.id_activo_biologico)===1571&&(Number(x.id_cierre)===Number(c.id_cierre)||x.tipo_evidencia==='CIERRE_PERIODO')),'baja_sin_revaluacion_cierre');
  check(Number(c.activos_procesados)>=vr.length+costo.length&&Array.isArray(c.activos_excluidos)&&c.activos_excluidos.length===0,'universo');
  for(const id of costo){const a=d.activos?.find(x=>Number(x.id_activo_biologico)===id);check(a?.valorado_por_costo===true,'costo_'+id);check(!med.some(x=>Number(x.id_activo_biologico)===id&&x.origen_medicion==='CIERRE_PERIODO'),'costo_sin_medicion_'+id);}
  check(Number(c.id_periodo_siguiente)===Number(d.siguiente?.id_periodo_contable)&&d.siguiente?.estado==='ABIERTO'&&String(d.siguiente?.fecha_inicio).startsWith('2026-12'),'siguiente');
  const antes=new Set((d.avisosAntes??[]).map(x=>x.id_notificacion));check((d.avisosDespues??[]).some(x=>!antes.has(x.id_notificacion)&&normalizar(x.mensaje)===normalizar(`Período ${mes} cerrado: listo para transferir desde Agrofusión`)),'notificacion');
  check(Number(c.reportes?.estado_resultados?.id_estado)>0&&Number(c.reportes?.informe_revelaciones?.id_informe)>0,'reportes_ids');
  check(d.estado?.resultado_neto!==undefined&&d.estado?.resultado_neto!==null&&!!d.revelacion,'reportes_api');return f;}
