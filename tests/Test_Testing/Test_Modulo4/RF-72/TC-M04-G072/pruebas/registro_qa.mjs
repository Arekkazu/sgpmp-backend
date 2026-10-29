import path from 'node:path';
export function clasificarRegistro(cap,r,presentes,ctx){
  const nombre=r.version===1?'TC-M04-G072_resultado.md':`TC-M04-G072_reevaluacion_V${r.version}.md`;
  const valida=x=>typeof x==='string'&&x&&!path.isAbsolute(x)&&!path.win32.isAbsolute(x)&&!x.split(/[\\/]/).includes('..')&&presentes.has(x);
  return r.run_id===ctx.runId&&r.version===ctx.version&&r.oficial===true&&r.consume_version===true&&
    r.cierre?.run?.cierre_http===200&&r.cierre?.rollback?.verificado===true&&
    JSON.stringify(Object.keys(r.casos).sort())===JSON.stringify([...cap.casos].sort())&&
    cap.casos.every(c=>['APROBADO','RECHAZADO'].includes(r.casos[c].estado))&&
    r.herramientas?.newman?.iteraciones===1&&r.herramientas?.newman?.posts===9&&r.herramientas?.newman?.lecturas>=5&&r.cypress?.total_pruebas===0&&
    ['newman/newman-G072.json','newman/newman-G072.html'].every(x=>presentes.has(x))&&
    Object.entries(cap.comprobaciones_obligatorias).every(([caso,f])=>f.API.every(id=>r.comprobaciones.some(x=>x.caso===caso&&x.fuente==='API'&&x.id===id&&x.tipo==='ASSERT'&&x.estado===r.casos[caso].estado&&valida(x.evidencia))))&&
    valida(nombre)&&r.evidencias.every(valida);
}
