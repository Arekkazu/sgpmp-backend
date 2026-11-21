import path from 'node:path';
export function clasificarRegistro(cap, r, presentes, ctx) {
  const nombre = r.version === 1 ? 'TC-M06-G40_resultado.md' : `TC-M06-G40_reevaluacion_V${r.version}.md`;
  const valida = x => typeof x === 'string' && x && !path.isAbsolute(x) && !path.win32.isAbsolute(x) &&
    !x.split(/[\\/]/).includes('..') && presentes.has(x);
  return r.run_id === ctx.runId && r.autorizacion_referencia === ctx.referencia &&
    r.version === ctx.version && r.oficial === true &&
    r.consume_version === true && r.cierre?.run?.cierre_http === 200 && r.cierre?.rollback?.verificado === true &&
    JSON.stringify(Object.keys(r.casos).sort()) === JSON.stringify([...cap.casos].sort()) &&
    cap.casos.every(c => ['APROBADO', 'RECHAZADO'].includes(r.casos[c].estado)) &&
    r.herramientas?.newman?.codigo === 0 && r.herramientas?.cypress?.codigo === 0 &&
    r.herramientas?.cypress?.acta?.captura === true &&
    ['cypress/G40-UI-018-01.json','cypress/G40-cypress.json',
      'cypress/screenshots/g40.cy.js/G40-UI-018-01.png'].every(x => presentes.has(x)) &&
    ['newman/newman-G40.json', 'newman/newman-G40.html'].every(x => presentes.has(x)) &&
    Object.entries(cap.comprobaciones_obligatorias).every(([caso, fuentes]) =>
      [...fuentes.API.map(id => ['API',id]),...fuentes.UI.map(id => ['UI',id])].every(([fuente,id]) =>
        r.comprobaciones.some(x => x.caso === caso && x.fuente === fuente &&
        x.id === id && x.tipo === 'ASSERT' && ['APROBADO', 'RECHAZADO'].includes(x.estado) && valida(x.evidencia)))) &&
    valida(nombre) && r.evidencias.every(valida);
}


