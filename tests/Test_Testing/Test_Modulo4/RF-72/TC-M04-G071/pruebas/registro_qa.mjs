import path from 'node:path';
export function clasificarRegistro(capacidades,r,presentes,contexto){
  const nombre=r.version===1?'TC-M04-G071_resultado.md':`TC-M04-G071_reevaluacion_V${r.version}.md`;
  const valida=x=>typeof x==='string'&&x&&!path.isAbsolute(x)&&!path.win32.isAbsolute(x)
    &&!x.split(/[\\/]/).includes('..')&&presentes.has(x);
  return r.run_id===contexto.runId&&r.version===contexto.version&&r.oficial===true
    &&r.consume_version===true&&r.cierre?.run?.cierre_http===200&&r.cierre?.rollback?.verificado===true
    &&JSON.stringify(Object.keys(r.casos).sort())===JSON.stringify([...capacidades.casos].sort())
    &&capacidades.casos.every(c=>['APROBADO','RECHAZADO'].includes(r.casos[c].estado))
    &&r.herramientas?.newman?.iteraciones===1&&r.herramientas?.newman?.solicitudes===23
    &&r.cypress?.total_pruebas===0
    &&['newman/newman-G071.json','newman/newman-G071.html'].every(x=>presentes.has(x))
    &&Object.entries(capacidades.comprobaciones_obligatorias).every(([caso,fuentes])=>
      fuentes.API.every(id=>r.comprobaciones.some(x=>x.caso===caso&&x.fuente==='API'
        &&x.id===id&&x.tipo==='ASSERT'&&x.estado===r.casos[caso].estado&&valida(x.evidencia))))
    &&valida(nombre)&&r.evidencias.every(valida);
}
