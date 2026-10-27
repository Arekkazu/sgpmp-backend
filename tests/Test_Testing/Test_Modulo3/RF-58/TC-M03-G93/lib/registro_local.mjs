import fs from 'node:fs';
import path from 'node:path';
import { CAPACIDADES } from './g93_escenario.mjs';

// Espejo de las condiciones publicadas para registro_qa.py; no escribe el registro.
export function evaluarRegistro(r, directorio, esperado = {}) {
  const estructura = r && typeof r === 'object' && !Array.isArray(r)
    && r.run_id === (esperado.runId ?? r.run_id) && r.version === (esperado.version ?? r.version)
    && r.cypress && typeof r.cypress === 'object' && !Array.isArray(r.cypress)
    && Number.isInteger(r.cypress.total_pruebas) && r.cypress.total_pruebas >= 0
    && r.casos && typeof r.casos === 'object' && !Array.isArray(r.casos)
    && Array.isArray(r.comprobaciones)
    && r.comprobaciones.every(x => ['API', 'UI'].includes(x.fuente));
  if (!estructura) return { estructura: false, completo: false, estado_run: 'DESCONOCIDO',
    oficialPosible: false, clasificacion: 'INCIERTO', evidencias: false };
  const casos = Object.keys(r.casos ?? {});
  const requeridas = CAPACIDADES.comprobaciones_obligatorias;
  const hechas = new Set((r.comprobaciones ?? [])
    .filter(x => x.tipo === 'ASSERT' && ['APROBADO', 'RECHAZADO'].includes(x.estado))
    .map(x => `${x.caso}|${x.fuente}|${x.id}`));
  const completo = casos.length === Object.keys(requeridas).length
    && casos.every(caso => Object.hasOwn(requeridas, caso)
      && ['APROBADO', 'RECHAZADO'].includes(r.casos[caso]?.estado)
      && ['API', 'UI'].every(fuente => (requeridas[caso][fuente] ?? [])
        .every(id => hechas.has(`${caso}|${fuente}|${id}`)))
      && (!(requeridas[caso].UI ?? []).length || Number.isInteger(r.cypress?.total_pruebas)
        && r.cypress.total_pruebas > 0));
  const cierre = r.cierre?.run?.cierre_http;
  const rollback = r.cierre?.rollback?.verificado === true;
  const efectos = Boolean(r.consume_version || r.datos?.ids_telemetria?.length);
  const estado_run = cierre === 200 || cierre === 404 && rollback ? 'CERRADO'
    : cierre == null ? efectos ? 'ABIERTO_PENDIENTE' : 'PREPARADO' : 'DESCONOCIDO';
  const evidencias = Array.isArray(r.evidencias) && r.evidencias.every(rel =>
    typeof rel === 'string' && !path.isAbsolute(rel) && !rel.split(/[\\/]/).includes('..')
    && fs.existsSync(path.join(directorio, rel)));
  const informe = path.join(directorio, r.version === 1 ? 'TC-M03-G93_resultado.md'
    : `TC-M03-G93_reevaluacion_V${r.version}.md`);
  const oficialPosible = completo && rollback && cierre === 200 && evidencias && fs.existsSync(informe);
  const clasificacion = r.oficial === true && oficialPosible ? 'OFICIAL'
    : r.oficial === false && ['CERRADO', 'PREPARADO'].includes(estado_run) ? 'TECNICO' : 'INCIERTO';
  return { estructura, completo, estado_run, oficialPosible, clasificacion, evidencias };
}
