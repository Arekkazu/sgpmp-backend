import fs from 'node:fs';
import path from 'node:path';
import { CASOS, COMPROBACIONES_OBLIGATORIAS } from './g89_escenario.mjs';

const escapar = (x) => String(x ?? 'NO CONSTA').replaceAll('|', '\\|').replaceAll('\n', ' ');
const linea = (campos) => `| ${campos.map(escapar).join(' | ')} |`;
const EXPECTATIVAS = {
  'TC-M03-173': 'HTTP 200. estado_semaforo="ROJO" pese a que el valor está en rango VERDE, y se devuelve el id_alerta asociado.',
  'TC-M03-174': 'Con alerta activa: estado_semaforo="AMARILLO". Con alerta resuelta o descartada: estado_semaforo="VERDE", sin elevación indebida.',
};

function evidenciaEnRun(dir, archivo) {
  if (typeof archivo !== 'string' || !archivo || path.isAbsolute(archivo)) return false;
  const destino = path.resolve(dir, archivo);
  return !archivo.split(/[\\/]/).includes('..') && destino.startsWith(path.resolve(dir) + path.sep)
    && fs.existsSync(destino) && fs.statSync(destino).isFile();
}

export function registroOficial(r, { evidenciasValidas, jsonNewmanValidos } = {}) {
  const completas = CASOS.every((caso) => Object.entries(COMPROBACIONES_OBLIGATORIAS[caso])
    .every(([fuente, ids]) => ids.every((id) => r.comprobaciones?.some((c) =>
      c.caso === caso && c.fuente === fuente && c.id === id && c.tipo === 'ASSERT'
      && ['APROBADO', 'RECHAZADO'].includes(c.estado)))));
  return JSON.stringify(Object.keys(r.casos ?? {})) === JSON.stringify(CASOS)
    && completas && CASOS.every((caso) => r.casos[caso].estado_tecnico === 'OK'
      && ['APROBADO', 'RECHAZADO'].includes(r.casos[caso].estado))
    && r.cierre.run?.cierre_http === 200 && r.cierre.rollback?.verificado === true
    && r.newman?.length === 1 && r.newman[0].archivo === 'newman/newman-TC-M03-G89.json'
    && r.evidencias?.includes('newman/newman-TC-M03-G89.html')
    && evidenciasValidas === true && jsonNewmanValidos === true;
}

export function completarResultado(r, dir) {
  r.run_id = r.ejecucion.run_id;
  r.version = r.ejecucion.version;
  r.datos = { ...(r.datos ?? {}), ids_telemetria: [...r.telemetrias_creadas] };
  r.consume_version = r.telemetrias_creadas.length > 0 || r.alertas_creadas.length > 0;
  r.cypress = { total_pruebas: 0, motivo: 'G89 solo API según matriz' };
  r.cierre.run = { ...(r.cierre.run ?? {}), cierre_http: r.cierre.http };
  r.cierre.rollback = { ...(r.cierre.rollback ?? {}), verificado: r.cierre.rollback_verificado === true };
  r.comprobaciones = CASOS.flatMap((caso) => r.casos[caso].comprobaciones.map((c) => {
    const evidenciaValida = evidenciaEnRun(dir, c.evidencia);
    const tipo = c.id_comprobacion.startsWith('PRE-') ? 'PRE' : 'ASSERT';
    const estado = evidenciaValida && c.http === 200
      ? (c.cumple ? 'APROBADO' : 'RECHAZADO')
      : r.casos[caso].estado_tecnico === 'ERROR_QA' ? 'ERROR_QA' : 'NO_CONCLUYENTE';
    return { caso, fuente: 'API', id: c.id_comprobacion, tipo, estado,
      evidencia: c.evidencia, http: c.http, observado: c.observado };
  }));
  for (const caso of CASOS) {
    const c = r.casos[caso];
    c.veredicto_funcional = c.veredicto;
    c.estado = c.estado_tecnico === 'OK' ? (c.veredicto ?? 'NO_CONCLUYENTE') : c.estado_tecnico;
  }
  const newmanDir = path.join(dir, 'newman');
  const jsonNewman = fs.existsSync(newmanDir)
    ? fs.readdirSync(newmanDir).filter((x) => x.toLowerCase().endsWith('.json')) : [];
  r.oficial = registroOficial(r, {
    jsonNewmanValidos: jsonNewman.length === 1 && jsonNewman[0] === 'newman-TC-M03-G89.json',
    evidenciasValidas: r.evidencias.every((archivo) => archivo === 'resultado.json' || evidenciaEnRun(dir, archivo))
  });
  return r;
}

export function validarResultado(r, dir) {
  if (r.grupo !== 'G89' || JSON.stringify(Object.keys(r.casos)) !== JSON.stringify(CASOS))
    throw new Error('RESULTADO_CASOS_INCOHERENTES');
  if (path.basename(dir) !== r.ejecucion.run_id || r.run_id !== r.ejecucion.run_id
    || r.version !== r.ejecucion.version) throw new Error('RESULTADO_RUN_INCOHERENTE');
  for (const [id, c] of Object.entries(r.casos)) {
    if (c.estado !== (c.estado_tecnico === 'OK' ? (c.veredicto ?? 'NO_CONCLUYENTE') : c.estado_tecnico)
      || c.veredicto_funcional !== c.veredicto) throw new Error(`ESTADO_INCOHERENTE_${id}`);
    if (c.veredicto === 'APROBADO' && (!c.comprobaciones.length
      || c.comprobaciones.some((x) => !x.cumple || !evidenciaEnRun(dir, x.evidencia))))
      throw new Error(`APROBACION_SIN_EVIDENCIA_${id}`);
    if (c.veredicto === 'RECHAZADO' && !c.comprobaciones.some((x) => !x.cumple && x.http === 200
      && evidenciaEnRun(dir, x.evidencia)))
      throw new Error(`RECHAZO_SIN_PRODUCTO_${id}`);
    if (['BLOQUEADO', 'REQUISITO_DEPENDIENTE', 'DEFECTO_FUNCIONAL_CANDIDATO'].includes(c.veredicto))
      throw new Error(`VEREDICTO_INVALIDO_${id}`);
  }
  if (r.cierre.run?.cierre_http !== r.cierre.http
    || r.cierre.rollback?.verificado !== r.cierre.rollback_verificado) throw new Error('CIERRE_INCOHERENTE');
  if (r.cierre.rollback_verificado && (r.cierre.http !== 200
    || !r.cierre.comprobaciones.some((x) => x.tipo === 'dashboard_previo'
      && x.previo_completo && x.posterior_completo && x.coincide)
    || r.alertas_creadas.some((id) => !r.cierre.comprobaciones.some((x) =>
      x.tipo === 'alerta_ausente' && x.id_alerta === id && x.http === 404 && x.coincide))
    || (r.telemetrias_creadas.length > 0 && !r.cierre.comprobaciones.some((x) =>
      x.tipo === 'telemetrias_ausentes' && x.http === 200 && x.completo
      && x.coincide && x.total_ids === r.telemetrias_creadas.length))
    || r.cierre.comprobaciones.some((x) => !x.coincide)))
    throw new Error('ROLLBACK_SIN_COMPROBACION');
  for (const archivo of r.evidencias) if (!evidenciaEnRun(dir, archivo))
    throw new Error(`EVIDENCIA_AUSENTE_${archivo}`);
  const copia = structuredClone(r);
  completarResultado(copia, dir);
  if (JSON.stringify(copia.comprobaciones) !== JSON.stringify(r.comprobaciones)
    || JSON.stringify(copia.casos) !== JSON.stringify(r.casos)
     || r.oficial !== copia.oficial) throw new Error('REGISTRO_INCOHERENTE');
  const oficial = fs.readdirSync(dir).filter((x) => x.endsWith('.md'));
  const esperado = r.version === 1 ? 'TC-M03-G89_resultado.md'
    : `TC-M03-G89_reevaluacion_V${r.version}.md`;
  if (oficial.length !== 1 || oficial[0] !== esperado) throw new Error('INFORMES_OFICIALES_INCOHERENTES');
  const newmanDir = path.join(dir, 'newman');
  if (fs.existsSync(newmanDir) && fs.readdirSync(newmanDir)
    .filter((x) => x.toLowerCase().endsWith('.json')).length > 1)
    throw new Error('NEWMAN_MULTIPLES_JSON');
}

export function informe(r) {
  if (r.ejecucion.version >= 2) return informeV2(r);
  const resumen = CASOS.map((id) => linea([id, r.casos[id].veredicto ?? 'SIN VEREDICTO',
    r.casos[id].estado_tecnico, r.casos[id].motivo ?? '—'])).join('\n');
  const casos = CASOS.map((id) => {
    const c = r.casos[id];
    const comprobaciones = c.comprobaciones.length ? c.comprobaciones.map((x) =>
      linea([x.id_comprobacion, x.etapa,
        `${x.esperado}${x.id_alerta_esperado ? `; id_alerta=${x.id_alerta_esperado}` : ''}`,
        `${x.observado?.estado_semaforo ?? 'SIN RESPUESTA'}; id_alerta=${x.observado?.id_alerta ?? 'null'}`,
        x.http, x.cumple ? 'Cumple' : 'Difiere', x.evidencia])).join('\n') :
      linea(['—', 'Sin ejecución', '—', '—', '—', '—', '—']);
    return `### ${id}\n\n**Esperado:** ${EXPECTATIVAS[id]}\n\n**Observado:** ${c.comprobaciones.length
      ? c.comprobaciones.map((x) => `${x.id_comprobacion}: ${x.observado?.estado_semaforo ?? 'sin sensor'}, id_alerta=${x.observado?.id_alerta ?? 'null'} (HTTP ${x.http})`).join('; ')
      : 'No se obtuvo comprobación API.'}\n\n| ID | Etapa | Estado esperado | Estado observado | HTTP | Evaluación | Evidencia |\n|---|---|---|---|---:|---|---|\n${comprobaciones}\n\n**Veredicto funcional:** ${c.veredicto ?? 'SIN VEREDICTO'}. **Estado técnico:** ${c.estado_tecnico}. ${c.prerequisitos?.length ? `Precondiciones: ${c.prerequisitos.join('; ')}.` : ''}`;
  }).join('\n\n');
  const cs = r.casos['TC-M03-174'].comprobaciones;
  const etapa = (e) => cs.find((x) => x.etapa === e);
  const fallos = CASOS.flatMap((caso) => r.casos[caso].comprobaciones
    .filter((x) => x.http === 200 && !x.cumple && !x.id_comprobacion.startsWith('PRE-'))
    .map((x) => ({ caso, x })));
  const terminales = fallos.filter(({ caso, x }) => caso === 'TC-M03-174'
    && ['resuelta', 'descartada'].includes(x.etapa));
  const ver = (x) => x ? x.id_comprobacion + ': GET HTTP ' + x.http
    + ', estado_semaforo=' + (x.observado?.estado_semaforo ?? 'sin sensor')
    + ', id_alerta=' + (x.observado?.id_alerta ?? 'null')
    + '; [' + x.evidencia + '](' + x.evidencia + ')' : 'NO CONSTA';
  const campo = (k, v) => '- **' + k + ':** ' + v;
  const productos = [];
  if (terminales.length) {
    const escenarios = terminales.map(({ x }) => {
      const res = x.etapa === 'resuelta';
      const a = etapa(res ? 'noCriticaActiva' : 'noCriticaDescarte');
      const id = a?.observado?.id_alerta ?? 'NO CONSTA';
      const ruta = '/iot/alertas/' + id + '/estado';
      const patch = r.bitacora.filter((b) => b.metodo === 'PATCH' && b.ruta === ruta)
        .map((b) => b.http).join(', ') || 'NO CONSTA';
      const indiceAlerta = r.alertas_creadas.indexOf(Number(id));
      const postAlerta = r.bitacora.filter((b) => b.metodo === 'POST'
        && b.ruta === '/iot/alertas')[indiceAlerta]?.http ?? 'NO CONSTA';
      const indiceTelemetria = res ? 1 : 2;
      const idTelemetria = r.telemetrias_creadas[indiceTelemetria] ?? 'NO CONSTA';
      const postTelemetria = r.bitacora.filter((b) => b.metodo === 'POST'
        && b.ruta === '/iot/telemetria')[indiceTelemetria]?.http ?? 'NO CONSTA';
      return (res ? 'LEVE a RESUELTA' : 'MODERADO a DESCARTADA') + ' (alerta ' + id
        + '): POST ingesta 25 \u00b0C HTTP ' + postTelemetria + ', id_telemetria=' + idTelemetria
        + '; ' + ver(etapa(res ? 'base174' : 'baseDescarte'))
        + '; POST alerta ' + (res ? 'LEVE' : 'MODERADO') + ' HTTP ' + postAlerta + ', id_alerta=' + id
        + '; ' + ver(a) + '; PATCH ' + ruta + ' '
        + (res ? 'EN_ATENCION a RESUELTA' : 'DESCARTADA') + ' HTTP ' + patch
        + '; GET inmediato sin nueva ingesta ' + ver(x) + '.';
    });
    const ids = terminales.map(({ x }) => x.id_comprobacion).join(', ');
    const evidencias = terminales.map(({ x }) => '[' + x.evidencia + '](' + x.evidencia + ')').join('; ');
    const rango = r.semilla?.umbral_normal
      ? r.semilla.umbral_normal.minimo + '-' + r.semilla.umbral_normal.maximo + ' \u00b0C'
      : 'NO CONSTA en resultado.json';
    productos.push('### INC-G89-174-01: AMARILLO persistente tras alerta terminal\n\n'
      + [
        campo('Identificaci\u00f3n y t\u00edtulo', 'INC-G89-174-01; TC-M03-174; elevación persistente tras RESUELTA/DESCARTADA; ' + r.ejecucion.run_id + '.'),
        campo('Contexto funcional', 'RF-58 fase 3 combina lectura y alertas ACTIVA; CA-4 exige ROJO con CRITICO activa. Una no crítica ACTIVA eleva a AMARILLO. El caso 174 exige cesar esa elevación al resolver o descartar.'),
        campo('Precondiciones', 'Sensor ' + (r.semilla?.sensor ?? 'NO CONSTA') + ', área ' + (r.semilla?.area ?? 'NO CONSTA') + ', especie ' + (r.semilla?.especie ?? 'NO CONSTA') + '; lectura ' + (cs[0]?.observado?.ultimo_valor ?? 'NO CONSTA') + ' \u00b0C, umbral normal ' + rango + '; base VERDE sin alerta; alertas ' + (etapa('noCriticaActiva')?.observado?.id_alerta ?? 'NO CONSTA') + ' LEVE y ' + (etapa('noCriticaDescarte')?.observado?.id_alerta ?? 'NO CONSTA') + ' MODERADO.'),
        campo('Pasos y escenarios', escenarios.join(' ')),
        campo('Esperado y fundamento', 'GET dashboard HTTP 200 debe devolver VERDE tras RESUELTA o DESCARTADA, sin nueva telemetría, si la lectura vigente está en rango y no hay otra condición activa.'),
        campo('Observado', ids + ': GET HTTP 200 devolvió AMARILLO con id_alerta=null tras los PATCH terminales.'),
        campo('Requisito incumplido', 'RF-58 fase 3: «Si hay una alerta ACTIVA asociada → al menos AMARILLO»; matriz G89: «Con alerta resuelta o descartada: estado_semaforo="VERDE", sin elevación indebida.»'),
        campo('Evidencia', ids + '; ' + evidencias + '; HTTP de POST/PATCH en bitácora; evidencias de base y alerta activa enlazadas en cada escenario.'),
        campo('Impacto', 'Monitoreo indica precaución con lectura normal y sin alerta activa asociada; altera la interpretación operativa del semáforo.'),
        campo('Severidad', 'MEDIA: afecta dos transiciones de este sensor; no hay evidencia de bloqueo general ni pérdida de datos.'),
        campo('Certeza', 'CONFIRMADA para las respuestas de producto en TEST; causa raíz NO DETERMINADA.'),
        campo('Equipo inicial', 'Desarrollo, backend de monitoreo/alertas: primera discrepancia en GET dashboard tras PATCH; derivación inicial, no causa raíz.'),
        campo('An\u00e1lisis t\u00e9cnico', 'Hipótesis de código local, sin confirmar en despliegue TEST: alembic/baseline/esquema_baseline.sql:7478-7482 limpia id_alerta sin recalcular estado_semaforo; src/telemetry/infrastructure/repositories/monitoreo_repository.py:70 consulta alerta ACTIVA; src/telemetry/application/use_cases/monitoreo/obtener_dashboard_use_case.py:73-78 parte del estado persistido.'),
        campo('Acci\u00f3n correctiva', 'Recalcular semáforo al pasar una alerta a RESUELTA o DESCARTADA con lectura vigente y demás alertas activas; no asignar VERDE incondicionalmente.'),
        campo('Criterio de aceptaci\u00f3n', 'Lectura normal sin alerta VERDE; LEVE activa AMARILLO; LEVE resuelta VERDE si no hay otra condición; MODERADO activa AMARILLO; MODERADO descartada VERDE si no hay otra condición; sin nueva telemetría; considerar otras alertas activas.'),
        campo('Estado actual', 'Hallazgo funcional confirmado en TEST en este RUN; pendiente de corrección y reevaluación autorizada.')
      ].join('\n'));
  }
  for (const { caso, x } of fallos.filter(({ caso, x }) => caso !== 'TC-M03-174'
    || !['resuelta', 'descartada'].includes(x.etapa))) {
    productos.push('### INC-G89-' + x.id_comprobacion + ': discrepancia en ' + x.etapa + '\n\n'
      + [
        campo('Identificaci\u00f3n y contexto', caso + ', RF-58 fase 3, ' + x.id_comprobacion + ', ' + r.ejecucion.run_id),
        campo('Precondiciones y reproduccion', 'Etapa ' + x.etapa + '; secuencia previa en bitacora; datos ausentes: NO CONSTA.'),
        campo('Esperado', 'GET dashboard HTTP 200, estado_semaforo=' + x.esperado + (x.id_alerta_esperado ? ', id_alerta=' + x.id_alerta_esperado : '')),
        campo('Observado y evidencia', ver(x)),
        campo('Impacto y severidad', 'Indicacion discrepante de monitoreo; MEDIA provisional hasta medir alcance.'),
        campo('Certeza y causa', 'Respuesta CONFIRMADA en TEST; causa raiz NO DETERMINADA.'),
        campo('Equipo inicial', 'Desarrollo: primera discrepancia en GET publico del dashboard.'),
        campo('Acci\u00f3n y aceptaci\u00f3n', 'Investigar etapa ' + x.etapa + ' y repetir hasta obtener ' + x.esperado + ' con iguales precondiciones.'),
        campo('Estado', 'Pendiente de correccion y reevaluacion.')
      ].join('\n'));
  }
  const incidencias = productos.join('\n\n') || 'No se acredito discrepancia funcional con HTTP 200 en este RUN.';
  const qa = [];
  if (!r.cierre.rollback_verificado) qa.push('- **Rollback no concluyente:** DELETE HTTP '
    + (r.cierre.http ?? 'NO CONSTA') + '; ' + r.cierre.motivo + ' '
    + (r.cierre.comprobaciones.map((x) => x.tipo + ': HTTP ' + (x.http ?? 'NO CONSTA')
      + ', coincide=' + x.coincide
      + (x.completo !== undefined ? ', completo=' + x.completo : '')
      + (x.posterior_completo !== undefined ? ', dashboard_completo=' + x.posterior_completo : '')).join('; ') || 'Sin comprobaciones.')
    + (r.cierre.http === 200 && r.cierre.comprobaciones.length
      && r.cierre.comprobaciones.every((x) => x.coincide)
      ? ' Todas las lecturas registradas coinciden; el verificador anterior exigía un sensor previo presente. Cuando estaba ausente antes y después, marcaba false aunque ambas consultas concordaran.'
      : ' Una lectura incompleta o discrepante impide confirmar la reversión.')
    + ' Responsable: automatización QA.');
  if (!r.evidencias.includes('preflight.json')) qa.push('- **Preflight ausente:** preflight.json no figura en el RUN; el lanzador no puede clasificar el fallo. Responsable: automatización QA.');
  else if (r.preflight?.ok === false) qa.push('- **Preflight fallido:** '
    + (r.preflight.barreras?.join(', ') || 'barrera NO CONSTA') + '. Responsable: automatización QA.');
  if (r.parada_seguridad) qa.push('- **Parada de seguridad:** ' + JSON.stringify(r.parada_seguridad));
  for (const problema of r.problemas_tecnicos) qa.push('- **Ejecucion o contrato:** ' + problema);
  const incidenciasQa = qa.join('\n') || 'Sin incidencias tecnicas registradas.';
  const bitacora = r.bitacora.map((x) => linea([x.metodo, x.ruta, x.en_run ? 'Sí' : 'No',
    x.latencia_ms, x.http ?? 'ERROR', x.eco_run == null ? 'N/A' : x.eco_run ? 'Sí' : 'No',
    x.error ?? '—'])).join('\n');
  const evidencia = r.evidencias.map((x) => `- [${x}](${x})`).join('\n');
  const rollback = r.cierre.comprobaciones.map((x) => linea([x.tipo, x.http, x.coincide ? 'Sí' : 'No'])).join('\n');
  return `# TC-M03-G89 — resultado ${r.ejecucion.run_id}\n\n## Identificación\n\nGrupo G89; casos TC-M03-173 y TC-M03-174; RF-58; versión V${r.ejecucion.version}; RUN ${r.ejecucion.run_id}; ambiente ${r.ejecucion.ambiente}; autorización ${r.ejecucion.autorizacion}; operación ${r.ejecucion.operacion}; commit ${r.ejecucion.commit}; inicio ${r.ejecucion.inicio}; fin ${r.ejecucion.fin}. Herramientas: Node ${process.version}, Newman con ${r.newman.length} ejecuciones JSON; Cypress no exigido por la matriz.\n\n## Alcance y oráculo\n\nFuente: Casos_Prueba(Modulo3 Agrupado).csv, fila G89, RF-58. Herramienta API Postman/Newman. GET /iot/monitoreo/dashboard. La semilla se revalidó por GET: ${r.semilla ? 'sí' : 'no'}. Las marcas de ingesta se calcularon antes de abrir el RUN: ${r.plan_temporal ? 'sí' : 'no'}.\n\n## Resumen de veredictos\n\n| Caso | Veredicto funcional | Estado técnico | Motivo |\n|---|---|---|---|\n${resumen}\n\n## Esperado y observado por caso\n\n${casos}\n\n## Comprobaciones API/UI\n\nLas tablas anteriores detallan los GET del dashboard. UI: cero comprobaciones porque la matriz no exige UI. POST /iot/telemetria, POST /iot/alertas, PATCH /iot/alertas/{id}/estado y GET de alertas acreditan precondiciones cuando sus respuestas figuran en la bitácora.\n\n## Incidencias\n\n### Producto\n\n${incidencias}\n\n### Automatizaci\u00f3n QA\n\n${incidenciasQa}\n\n### Casos sin veredicto\n\n${CASOS.filter((id) => !r.casos[id].veredicto).map((id) => `- ${id}: ${r.casos[id].prerequisitos?.join('; ') || r.casos[id].motivo || 'sin comprobación completa'}`).join('\n') || 'Ninguno.'}\n\n## Hallazgos y análisis de causas\n\n${r.hallazgos.length ? r.hallazgos.map((x) => `- ${x}`).join('\n') : 'El código local puede diferir del despliegue TEST; no se atribuye causa raíz sin evidencia de TEST.'}\n\n## Bitácora de solicitudes\n\n| Método | Ruta | En RUN | Latencia ms | HTTP | Eco RUN | Error saneado |\n|---|---|---|---:|---:|---|---|\n${bitacora}\n\n## Evidencias reales\n\n${evidencia}\n\n## Cierre y rollback\n\nDELETE /test-control/runs/{id}: HTTP ${r.cierre.http ?? 'NO CONSTA'}. Rollback: ${r.cierre.rollback_verificado ? 'VERIFICADO por GET posteriores' : 'NO CONFIRMADO'}. ${r.cierre.motivo}\n\n| Comprobación | HTTP | Coincide |\n|---|---:|---|\n${rollback}\n\n## Conclusión y acción concreta\n\nEstado final ${r.estado}. ${r.cierre.rollback_verificado ? 'Revisar las incidencias funcionales documentadas y decidir cierre de QA.' : 'Responsable QA debe revisar el cierre y la evidencia faltante antes de cualquier conclusión de persistencia.'}\n`;
}

function informeV2(r) {
  const estado = (id) => r.casos[id].estado ?? 'NO_CONCLUYENTE';
  const decision = r.oficial ? CASOS.every((id) => estado(id) === 'APROBADO')
    ? 'APROBADO' : 'RECHAZADO' : 'INCIERTO';
  const alcance = r.alcance_reevaluacion ?? {};
  const anterior = { 'TC-M03-173': 'APROBADO', 'TC-M03-174': 'RECHAZADO' };
  const resumen = CASOS.map((id) => linea([id, anterior[id], estado(id), r.casos[id].motivo ?? '—'])).join('\n');
  const detalle = CASOS.map((id) => {
    const c = r.casos[id];
    const obs = c.comprobaciones.map((x) => `${x.id_comprobacion}: HTTP ${x.http}, ${x.observado?.estado_semaforo ?? 'sin sensor'}, id_alerta=${x.observado?.id_alerta ?? 'null'}, lectura=${x.observado?.ultimo_valor ?? 'null'}, vigente=${x.lectura_vigente ? 'sí' : 'no'}, en_rango=${x.lectura_en_rango ? 'sí' : 'no'}`).join('; ') || 'Sin respuesta concluyente.';
    const filas = c.comprobaciones.map((x) => linea([x.id_comprobacion,
      x.id_comprobacion.startsWith('PRE-') ? 'PRE' : 'ASSERT', x.esperado,
      `${x.observado?.estado_semaforo ?? 'sin sensor'}; id_alerta=${x.observado?.id_alerta ?? 'null'}`,
      x.http, x.cumple ? 'APROBADO' : 'RECHAZADO', `[${x.evidencia}](${x.evidencia})`])).join('\n');
    return `### ${id}\n\n**Esperado:** ${EXPECTATIVAS[id]}\n**Observado por API pública:** ${obs}\n**Decisión del caso:** ${estado(id)}; V1 ${anterior[id]} → V2 ${estado(id)}.\n**Qué falta o cambió:** ${estado(id) === 'APROBADO' ? 'Se cumplieron las comprobaciones obligatorias; sin pendientes del caso.' : c.prerequisitos?.join('; ') || 'Revisar la discrepancia y su evidencia enlazada.'}\n\n| Comprobación | Tipo | Esperado | Observado | HTTP | Estado | Evidencia |\n|---|---|---|---|---:|---|---|\n${filas || linea(['—', '—', '—', 'Sin ejecución', '—', 'NO_CONCLUYENTE', '—'])}`;
  }).join('\n\n');
  const terminales174 = ['API-174-02', 'API-174-04'].map((id) =>
    r.casos['TC-M03-174'].comprobaciones.find((c) => c.id_comprobacion === id));
  const cierre174 = r.oficial && terminales174.every((c) => c?.http === 200 && c.cumple)
    ? 'CORREGIDA' : r.oficial && terminales174.some((c) => c?.http === 200 && !c.cumple)
      ? 'PERSISTENTE' : 'NO DETERMINADA';
  const incidencias = r.incidencias.map((i) => {
    const puntos = i.comprobaciones.map((x) => {
      const c = r.casos[i.caso].comprobaciones.find((y) => y.id_comprobacion === x.comprobacion);
      return `${x.comprobacion}: esperado ${c?.esperado ?? 'NO CONSTA'}, observado ${c?.observado?.estado_semaforo ?? 'sin sensor'} e id_alerta=${c?.observado?.id_alerta ?? 'null'}, GET HTTP ${c?.http ?? 'NO CONSTA'} ([evidencia](${x.evidencia}))`;
    }).join('; ');
    return `### ${i.id}\n\n- **Caso y requisito:** ${i.caso}; RF-58 fase 3, alertas activas y semáforo del dashboard.\n- **Precondiciones y pasos:** sensor ${r.semilla?.sensor ?? 'NO CONSTA'}; ingesta válida de 25 °C, alerta del RUN y ${i.id === 'INC-G89-174-01' ? 'PATCH terminal seguido de GET sin nueva ingesta' : 'GET con alerta activa'} según bitácora.\n- **Discrepancia comprobada:** ${puntos}.\n- **Impacto y severidad:** semáforo operativo incorrecto para el escenario observado; ${i.severidad}, ${i.caso === 'TC-M03-173' ? 'la alerta crítica pierde su indicación ROJO sin alternativa en este escenario' : 'afectación parcial de la indicación de alertas'}.\n- **Certeza:** CONFIRMADA para la respuesta del producto en este RUN; causa raíz NO DETERMINADA.\n- **Equipo inicial:** Desarrollo, por la primera discrepancia del GET público tras las acciones del caso; es derivación inicial, no causa raíz.\n- **Acción:** revisar la transición y repetir el escenario con las mismas precondiciones; aceptación según el esperado de la matriz.\n- **Estado:** ${i.estado}.`;
  }).join('\n\n') || 'Sin discrepancias funcionales acreditadas en este RUN.';
  const bitacora = r.bitacora.map((x) => linea([x.metodo, x.ruta, x.http ?? 'SIN RESPUESTA', x.eco_run == null ? 'N/A' : x.eco_run ? 'Sí' : 'No', x.error ?? '—'])).join('\n');
  const rollback = r.cierre.comprobaciones.map((x) => linea([x.tipo, x.http ?? '—', x.coincide ? 'Sí' : 'No'])).join('\n');
  const evidencias = r.evidencias.map((x) => `- [${x}](${x})`).join('\n');
  const altas = (r.altas_alerta ?? []).map((a) => linea([a.caso, a.severidad_esperada,
    a.http, String(a.es_duplicado), a.id_alerta ?? 'null', a.severidad ?? 'null',
    a.motivo_descarte ?? '—', a.error_code ?? '—', a.message ?? '—',
    JSON.stringify(a.fields ?? []), `[${a.evidencia}](${a.evidencia})`])).join('\n');
  const reporte = `# TC-M03-G89 — ${decision}\n\n## Identificación\n\nGrupo G89; casos ${CASOS.join(', ')}; RF-58; V${r.version}; RUN ${r.run_id}; ambiente ${r.ejecucion.ambiente}; autorización ${r.ejecucion.autorizacion}; operación ${r.ejecucion.operacion}; commit ${r.ejecucion.commit}. Inicio ${r.ejecucion.inicio}; fin ${r.ejecucion.fin}. Herramientas: Node ${process.version}; Newman ${r.newman.length} ejecución JSON, versión no verificada; Cypress no exigido (0 pruebas).\n\n## Decisión del caso\n\n${decision}. Oficialidad ${r.oficial ? 'OFICIAL' : 'INCIERTA'}; cierre HTTP ${r.cierre.run?.cierre_http ?? 'NO CONSTA'}; rollback ${r.cierre.rollback?.verificado ? 'VERIFICADO' : 'NO CONFIRMADO'}.\n\n## Alcance de reevaluación\n\nV${alcance.version_anterior ?? 'NO CONSTA'} → V${r.version}; casos ${Array.isArray(alcance.casos) ? alcance.casos.join(', ') : 'NO CONSTA'}. Motivo: ${alcance.motivo ?? 'NO CONSTA'}. Incumplimientos previos: ${alcance.incumplimientos_previos ?? 'NO CONSTA'}. Correcciones informadas: ${alcance.correcciones_informadas ?? 'NO CONSTA'}; su despliegue exacto no se deduce del código local. Resultado esperado: ${alcance.resultado_esperado ?? 'NO CONSTA'}. V1 oficial: Resultados/RUN-G89-V1-20261025-045219/TC-M03-G89_resultado.md; 173 APROBADO, 174 RECHAZADO (INC-G89-174-01).\n\n## Resumen de veredictos y comparación V1 → V2\n\n| Caso | V1 | V2 | Motivo |\n|---|---|---|---|\n${resumen}\n\n## Detalle por caso\n\n${detalle}\n\n## Comprobaciones API/UI\n\nGET /iot/monitoreo/dashboard con Productor; IDs PRE y API conservados. Los GET previos tienen evidencia JSON saneada en api/; API-174-04 usa la única ejecución Newman. UI no requerida por la matriz. Acceso: Productor con rol, identidad y finca 184 ${r.acceso?.productor_finca_184 ? 'acreditados' : 'no acreditados'}; Administrador con rol, identidad y lectura del área 349 ${r.acceso?.admin_area_349 ? 'acreditados' : 'no acreditados'}.\n\n## Estado de la incidencia V1\n\nINC-G89-174-01: ${cierre174}. ${cierre174 === 'CORREGIDA' ? 'Los GET tras RESUELTA y DESCARTADA devolvieron VERDE e id_alerta=null sin nueva ingesta entre PATCH y GET.' : 'La evidencia del caso determina el alcance comprobado; no se da por corregida sin las dos respuestas terminales.'}\n\n## Incidencias de producto\n\n${incidencias}\n\n## Automatización y entorno\n\n${r.problemas_tecnicos.length ? r.problemas_tecnicos.map((x) => `- ${x}`).join('\n') : 'Sin problemas técnicos registrados.'} ${r.parada_seguridad ? `Parada de seguridad: ${JSON.stringify(r.parada_seguridad)}.` : ''}\n\n## Análisis de causas\n\nHecho: ${r.incidencias.length ? 'las respuestas públicas señaladas difieren del oráculo' : 'no se registró discrepancia funcional concluyente en las comprobaciones ejecutadas'}. Hipótesis: el recálculo informado por Desarrollo puede explicar un cambio de V1 a V2; no demuestra la causa raíz ni el despliegue en TEST.\n\n## Evidencias reales\n\n${evidencias}\n\n## Bitácora de solicitudes\n\n| Método | Ruta | HTTP | Eco RUN | Error saneado |\n|---|---|---:|---|---|\n${bitacora}\n\n## Cierre y rollback\n\nDELETE /test-control/runs/{id}: HTTP ${r.cierre.http ?? 'NO CONSTA'}. Rollback ${r.cierre.rollback_verificado ? 'VERIFICADO por lecturas posteriores' : 'NO CONFIRMADO'}. ${r.cierre.motivo}\n\n| Comprobación | HTTP | Coincide |\n|---|---:|---|\n${rollback}\n\n## Conclusión y acciones concretas\n\n${decision}. ${r.oficial ? 'Responsable QA: registrar la comparación V1 → V2 y decidir cierre o derivación de las incidencias acreditadas.' : 'Responsable QA: revisar la evidencia técnica faltante antes de asignar veredicto funcional definitivo.'}\n`;
  return reporte.replace('## Estado de la incidencia V1', `## Altas RF-57 y respuestas POST\n\nVia EDGE: 37 C (CRITICO), 31 C (LEVE) y 34 C (MODERADO), vinculadas a sus telemetrias reales, con HUMEDAD_RELATIVA=40 en correlacion_variables. El THI calculado cumple la condicion minima de ESTRES_TERMICO y conserva la severidad esperada. Cada alta va seguida de 25 C y comprobacion de lectura vigente en rango por dashboard. Fuentes: reglas_base_rf57.py:49-75,92-112,131-148 y generar_alerta_use_case.py:155-175,377-387,429-466. Un HTTP 201 sin id_alerta deja el caso sin veredicto y conserva motivo_descarte.\n\n| Caso | Severidad esperada | HTTP | Duplicado | ID | Severidad POST | Motivo de descarte | Error code | Message | Fields | Evidencia |\n|---|---|---:|---|---:|---|---|---|---|---|---|\n${altas || linea(['-', '-', '-', '-', '-', '-', 'Sin POST', '-', '-', '-', '-'])}\n\n## Estado de la incidencia V1`);
}
