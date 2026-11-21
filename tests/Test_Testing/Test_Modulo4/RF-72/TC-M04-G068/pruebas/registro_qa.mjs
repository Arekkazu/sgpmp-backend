import path from 'node:path';

export function clasificarRegistro(capacidades,r,presentes,contexto) {
  const nombre=r.version===1?'TC-M04-G068_resultado.md':`TC-M04-G068_reevaluacion_V${r.version}.md`;
  const valida=x=>typeof x==='string'&&x&&!path.isAbsolute(x)&&!path.win32.isAbsolute(x)
    &&!x.split(/[\\/]/).includes('..')&&presentes.has(x);
  const casos=capacidades.casos;
  return r.run_id===contexto.runId&&r.version===contexto.version
    &&r.cierre?.run?.cierre_http===200&&r.cierre?.rollback?.verificado===true
    &&r.consume_version===true&&r.oficial===true
    &&JSON.stringify(Object.keys(r.casos).sort())===JSON.stringify([...casos].sort())
    &&casos.slice(0,2).every(c=>['APROBADO','RECHAZADO'].includes(r.casos[c].estado))
    &&['APROBADO','RECHAZADO'].includes(r.casos[casos[2]].estado)
    &&r.herramientas?.newman?.iteraciones===1
    &&r.evidencias.filter(x=>x.startsWith('newman/')).length===2
    &&['newman/newman-G068.json','newman/newman-G068.html'].every(x=>presentes.has(x))
    &&Object.entries(capacidades.comprobaciones_obligatorias).every(([caso,fuentes])=>
      fuentes.API.every(id=>r.comprobaciones.some(x=>x.caso===caso&&x.fuente==='API'
        &&x.id===id&&x.tipo==='ASSERT'&&x.estado===r.casos[caso].estado&&valida(x.evidencia))))
    &&r.cypress?.total_pruebas===0&&valida(nombre)
    &&Array.isArray(r.evidencias)&&r.evidencias.every(valida);
}
