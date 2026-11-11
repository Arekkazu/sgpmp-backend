import path from 'node:path';
export function clasificarRegistro(cap,r,presentes,ctx){
  const informe=r.version===1?'TC-M06-G42_resultado.md':`TC-M06-G42_reevaluacion_V${r.version}.md`;
  const existe=x=>typeof x==='string'&&x.length>0&&!path.isAbsolute(x)&&!path.win32.isAbsolute(x)&&!x.split(/[\\/]/).includes('..')&&presentes.has(x);
  return r.grupo==='G42'&&r.run_id===ctx.runId&&r.autorizacion_referencia===ctx.referencia&&r.version===ctx.version&&r.oficial===true&&r.consume_version===true&&
    r.cierre?.run?.cierre_http===200&&r.cierre?.rollback?.verificado===true&&r.herramientas?.newman?.codigo===0&&r.herramientas.newman.fallos===0&&
    r.total_solicitudes_api<=cap.limite.solicitudes_totales&&JSON.stringify(Object.keys(r.casos).sort())===JSON.stringify([...cap.casos].sort())&&
    cap.casos.every(id=>['APROBADO','RECHAZADO'].includes(r.casos[id].estado))&&
    Object.entries(cap.comprobaciones_obligatorias).every(([caso,fuentes])=>fuentes.API.every(id=>r.comprobaciones.some(x=>x.caso===caso&&x.id===id&&x.fuente==='API'&&x.tipo==='ASSERT'&&['APROBADO','RECHAZADO'].includes(x.estado)&&existe(x.evidencia))))&&
    ['resultado.json',informe,'newman/newman-G42.json','newman/newman-G42.html'].every(existe)&&r.evidencias.every(existe);
}
