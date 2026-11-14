import path from 'node:path';
export function clasificarRegistro(cap, r, presentes, ctx) {
  const nombre = r.version === 1 ? 'TC-M06-G34_resultado.md' : `TC-M06-G34_reevaluacion_V${r.version}.md`;
  const valida = x => typeof x === 'string' && x && !path.isAbsolute(x) && !path.win32.isAbsolute(x)
    && !x.split(/[\\/]/).includes('..') && presentes.has(x);
  return r.run_id === ctx.runId && r.version === ctx.version && r.oficial === true &&
    r.consume_version === true && r.cierre?.run?.cierre_http === 200 &&
    r.cierre?.rollback?.verificado === true && r.cierre?.costos?.restaurados === true &&
    r.cierre?.costos?.poscierre_original === true &&
    JSON.stringify(Object.keys(r.casos).sort()) === JSON.stringify([...cap.casos].sort()) &&
    cap.casos.every(c => ['APROBADO', 'RECHAZADO'].includes(r.casos[c].estado)) &&
    r.herramientas?.newman?.iteraciones === 1 &&
    (r.casos?.[cap.casos[0]]?.estado === 'RECHAZADO' || r.herramientas.newman.fallos === 0) &&
    r.cypress?.total_pruebas > 0 &&
    r.cypress?.total_failed === 0 && r.cypress?.captura === true &&
    ['newman/newman-G34.json', 'newman/newman-G34.html', 'cypress/G34-UI-006-01.json',
      'cypress/G34-cypress.json', 'cypress/screenshots/g34.cy.js/G34-UI-006-01.png'].every(x => presentes.has(x)) &&
    Object.entries(cap.comprobaciones_obligatorias).every(([caso, fuentes]) =>
      [...fuentes.API, ...fuentes.UI].every(id => r.comprobaciones.some(x => x.caso === caso &&
        x.fuente === (fuentes.UI.includes(id) ? 'UI' : 'API') && x.id === id && x.tipo === 'ASSERT' &&
        ['APROBADO', 'RECHAZADO'].includes(x.estado) && valida(x.evidencia)))) &&
    valida(nombre) && r.evidencias.every(valida);
}
