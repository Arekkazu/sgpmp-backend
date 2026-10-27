import path from 'node:path';

// Emulación local del contrato de registro_qa.py, patrón G98.
function validarObligatorias(capacidades) {
  const requeridas = capacidades.comprobaciones_obligatorias;
  if (!Array.isArray(capacidades.casos) || !capacidades.casos.length || !requeridas
    || typeof requeridas !== 'object' || Array.isArray(requeridas)
    || JSON.stringify(Object.keys(requeridas).sort()) !== JSON.stringify([...capacidades.casos].sort())) throw Error('Casos incoherentes');
  const ids = new Set();
  for (const fuentes of Object.values(requeridas)) {
    if (!fuentes || typeof fuentes !== 'object' || Array.isArray(fuentes)
      || !Object.keys(fuentes).length || Object.keys(fuentes).some(f => !['API', 'UI'].includes(f))) throw Error('Fuentes obligatorias invalidas');
    for (const lista of Object.values(fuentes)) {
      if (!Array.isArray(lista) || !lista.length) throw Error('IDs obligatorios invalidos');
      for (const id of lista) {
        if (typeof id !== 'string' || !/^[A-Za-z0-9_-]{1,100}$/.test(id) || ids.has(id)) throw Error('IDs obligatorios invalidos');
        ids.add(id);
      }
    }
  }
  return requeridas;
}
export { validarObligatorias };
export function clasificarRegistro(capacidades, r, presentes, contexto) {
  const requeridas = validarObligatorias(capacidades);
  const requiereUI = Object.values(requeridas).some(fuentes => 'UI' in fuentes);
  const nombre = r.version === 1 ? 'TC-M03-G120_resultado.md' : `TC-M03-G120_reevaluacion_V${r.version}.md`;
  const evidenciaValida = x => typeof x === 'string' && x.length > 0
    && !path.isAbsolute(x) && !path.win32.isAbsolute(x)
    && !x.split(/[\\/]/).includes('..') && presentes.has(x);
  return r.run_id === contexto.runId && r.version === contexto.version
    && r.cierre?.run?.cierre_http === 200 && r.cierre?.rollback?.verificado === true
    && typeof r.consume_version === 'boolean'
    && r.casos && JSON.stringify(Object.keys(r.casos).sort()) === JSON.stringify([...capacidades.casos].sort())
    && Object.values(r.casos).every(x => ['APROBADO', 'RECHAZADO'].includes(x?.estado))
    && Array.isArray(r.comprobaciones)
    && Object.entries(requeridas).every(([caso, fuentes]) => Object.entries(fuentes).every(([fuente, ids]) =>
      ids.every(id => r.comprobaciones.some(x => x.caso === caso && x.fuente === fuente && x.id === id
        && x.tipo === 'ASSERT' && ['APROBADO', 'RECHAZADO'].includes(x.estado)))))
    && (!requiereUI || r.cypress?.total_pruebas > 0)
    && evidenciaValida(nombre) && Array.isArray(r.evidencias)
    && r.evidencias.every(evidenciaValida) && r.oficial === true;
}
