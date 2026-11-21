import fs from 'node:fs';
import path from 'node:path';
import { CAPACIDADES, IDS_CASOS } from './g88_catalogo.mjs';

export const nombreInforme = (version) => version === 1
  ? 'TC-M03-G88_resultado.md' : `TC-M03-G88_reevaluacion_V${version}.md`;
const archivoRegular = (ruta) => {
  try { return fs.lstatSync(ruta).isFile(); } catch { return false; }
};

// Emula las condiciones de cierre del registro QA con las rutas del RUN ya materializadas.
export function evaluarOficialidad(r, dir) {
  const motivos = [];
  const fallo = (condicion, motivo) => { if (!condicion) motivos.push(motivo); };
  fallo(r.parada_seguridad == null, 'Parada de seguridad registrada.');
  fallo(!r.secretos_detectados && !(r.problemas_tecnicos ?? []).some(x => /secreto|token|password|jwt|cookie/i.test(String(x))),
    'Posible exposición de secretos.');
  fallo(r.estado === 'CONCLUIDA', 'RUN sin cierre concluido.');
  fallo(Object.keys(r.casos ?? {}).sort().join('|') === [...IDS_CASOS].sort().join('|'), 'Conjunto de casos incompleto.');
  for (const id of IDS_CASOS) {
    fallo(['APROBADO', 'RECHAZADO'].includes(r.casos?.[id]?.estado), `${id}: estado sin veredicto final.`);
    for (const [fuente, ids] of Object.entries(CAPACIDADES.comprobaciones_obligatorias[id])) {
      for (const clave of ids) fallo((r.comprobaciones ?? []).some(x => x.caso === id && x.fuente === fuente
        && x.id === clave && x.tipo === 'ASSERT' && ['APROBADO', 'RECHAZADO'].includes(x.estado)),
      `${id}: falta ASSERT ${fuente} ${clave} con resultado.`);
    }
  }
  fallo((r.cypress?.total_pruebas ?? 0) > 0, 'Cypress sin pruebas para UI obligatoria.');
  fallo(r.cierre?.run?.cierre_http === 200, 'Cierre del RUN distinto de HTTP 200.');
  fallo(r.cierre?.rollback?.verificado === true, 'Rollback no verificado.');
  fallo(archivoRegular(path.join(dir, nombreInforme(r.version))), 'Informe oficial ausente del RUN.');
  fallo(Array.isArray(r.evidencias), 'Lista de evidencias ausente.');
  for (const ruta of r.evidencias ?? []) {
    const valida = typeof ruta === 'string' && ruta.length > 0 && !path.isAbsolute(ruta)
      && !ruta.split(/[\\/]/).includes('..') && !/^[A-Za-z]:/.test(ruta);
    fallo(valida && archivoRegular(path.join(dir, ruta)), `Evidencia inexistente o fuera del RUN: ${ruta}.`);
  }
  return { oficial: motivos.length === 0, motivo_no_oficial: motivos.length ? motivos.join(' ') : null,
    clasificacion_prevista: motivos.length ? 'TECNICO' : 'OFICIAL' };
}
