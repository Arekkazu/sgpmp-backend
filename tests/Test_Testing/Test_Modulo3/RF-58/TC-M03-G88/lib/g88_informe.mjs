import fs from 'node:fs';
import path from 'node:path';
import { CASOS, IDS_CASOS, resultadoOficial } from './g88_catalogo.mjs';
import { generarPresentacionG88 } from './g88_presentacion.mjs';

const EQUIPOS = new Set(['Desarrollo', 'AIoT', 'DBA', 'Implementación']);
const SEVERIDADES = new Set(['CRÍTICA', 'ALTA', 'MEDIA', 'BAJA']);
const limpio = (v) => String(v ?? '—').replace(/[\r\n|]+/g, ' ').slice(0, 600);
const enlace = (ruta) => `[${ruta}](./${ruta})`;

export function validarResultadoLocal(r, baseDir, informe = null) {
  const errores = [];
  if (r.grupo !== 'TC-M03-G88' || !/^RUN-G88-V\d+-\d{8}-\d{6}$/.test(r.run_id ?? '')
    || r.version !== Number(/-V(\d+)-/.exec(r.run_id ?? '')?.[1])) errores.push('Identificación RUN incoherente.');
  if (path.basename(baseDir) !== r.run_id) errores.push('Carpeta y RUN no coinciden.');
  if (fs.existsSync(baseDir) && (!fs.existsSync(path.join(baseDir, 'resultado.json'))
    || !(r.evidencias ?? []).includes('resultado.json'))) errores.push('resultado.json sin referencia o inexistente.');
  if (Object.keys(r.casos ?? {}).sort().join('|') !== [...IDS_CASOS].sort().join('|')) errores.push('Casos incompletos.');
  for (const id of IDS_CASOS) {
    const esperado = resultadoOficial(id, r.comprobaciones ?? [], r.bloqueos?.[id] ?? [],
      r.cypress?.casos?.[id]?.total_pruebas ?? r.cypress?.total_pruebas ?? 0,
      (r.hallazgos_producto ?? []).filter((x) => x.caso === id), r.evidencias ?? []);
    if (r.casos?.[id]?.veredicto_funcional !== esperado.veredicto_funcional
      || r.casos?.[id]?.estado_tecnico !== esperado.estado_tecnico
      || r.casos?.[id]?.estado !== esperado.estado
      || JSON.stringify(r.casos?.[id]?.evidencia_veredicto) !== JSON.stringify(esperado.evidencia_veredicto))
      errores.push(`${id}: veredicto/estado técnico/evidencia distintos a comprobaciones.`);
    if (r.casos?.[id]?.estado_tecnico !== 'OK' && r.casos?.[id]?.veredicto_funcional !== null)
      errores.push(`${id}: estado técnico con veredicto oficial.`);
    if (CASOS[id].ui.length && r.casos?.[id]?.estado === 'APROBADO'
      && !(r.cypress?.casos?.[id]?.total_pruebas ?? r.cypress?.total_pruebas ?? 0)) errores.push(`${id} aprobado sin UI.`);
    if (r.casos?.[id]?.estado === 'APROBADO' && !(r.evidencias ?? []).some((x) => /^newman\/[^/]+\.json$/.test(x)))
      errores.push(`${id}: aprobado sin reporte Newman.`);
    if (r.casos?.[id]?.estado === 'APROBADO' && !(r.evidencias ?? []).some((x) => /^newman\/[^/]+\.html$/.test(x)))
      errores.push(`${id}: aprobado sin HTML Newman.`);
    if (CASOS[id].ui.length && r.cypress?.casos?.[id]) {
      const fase = r.cypress.casos[id];
      if (!['EJECUTADO_CON_COMPROBACIONES', 'EJECUTADO_CON_ERROR', 'NO_EJECUTADO'].includes(fase.estado)
        || fase.estado === 'EJECUTADO_CON_COMPROBACIONES' && !(fase.total_pruebas > 0)
        || fase.estado === 'EJECUTADO_CON_ERROR' && !fase.error
        || fase.estado === 'NO_EJECUTADO' && (!fase.causa || fase.total_pruebas !== 0))
        errores.push(`${id}: estado Cypress incoherente.`);
    }
  }
  if (r.casos?.['TC-M03-180']?.estado === 'APROBADO' && !(r.evidencias ?? []).some((x) => /^cypress\/.*TC-M03-180.*\.png$/.test(x)))
    errores.push('180 aprobado sin captura UI real.');
  for (const ruta of r.evidencias ?? []) {
    if (!ruta || path.isAbsolute(ruta) || ruta.split(/[\\/]/).includes('..') || !fs.existsSync(path.join(baseDir, ruta)))
      errores.push(`Evidencia inexistente o fuera del RUN: ${ruta}`);
  }
  for (const i of r.incidencias ?? []) {
    if (i.equipo !== 'POR DETERMINAR' && !EQUIPOS.has(i.equipo)) errores.push('Equipo de producto no permitido.');
    if (!SEVERIDADES.has(i.severidad) || !i.justificacion_severidad) errores.push('Severidad sin fundamento.');
    if (i.equipo === 'POR DETERMINAR' && !(i.escalamiento?.responsable && i.escalamiento?.evidencia_faltante))
      errores.push('POR DETERMINAR sin escalamiento QA.');
    if (!['CONFIRMADA', 'PROBABLE', 'NO DETERMINADA'].includes(i.certeza)) errores.push('Certeza inválida.');
  }
  const oficiales = fs.existsSync(baseDir) ? fs.readdirSync(baseDir).filter((x) => /^(?:TC-M03-G88_(?:resultado|reevaluacion_V\d+)\.md|informe\.md)$/.test(x)) : [];
  if (oficiales.length > 1 || oficiales.includes('informe.md')) errores.push('Markdown oficial duplicado o informe.md heredado dentro del RUN.');
  if (fs.existsSync(path.join(path.dirname(baseDir), r.version === 1 ? 'TC-M03-G88_resultado.md'
    : `TC-M03-G88_reevaluacion_V${r.version}.md`))) errores.push('Copia vigente del informe fuera del RUN.');
  if (informe && (!informe.includes(r.run_id) || IDS_CASOS.some((id) => !informe.includes(id)))) errores.push('Informe y resultado.json incoherentes.');
  if (r.parada_seguridad && (r.estado === 'CONCLUIDA'
    || !Array.isArray(r.parada_seguridad.casos_pendientes)))
    errores.push('Parada de seguridad sin lista de casos o RUN declarado concluido.');
  if (r.cierre?.rollback?.umbral_run_266?.estado === 'PRESENTE_ROLLBACK_NO_CONFIRMADO' && r.cierre.rollback.verificado)
    errores.push('Umbral 266 presente o ilegible tras cierre con rollback declarado verificado.');
  return errores;
}

export function derivarIncidencias(r) {
  const salida = [];
  const gateway266 = (r.bitacora ?? []).find((x) => x.caso === 'TC-M03-266'
    && x.gateway_observado === true);
  if (gateway266) salida.push({ caso: 'TC-M03-266', comprobacion: gateway266.etapa,
    equipo: 'AIoT', fundamento: `Primera propagación observada con gateway tras ${gateway266.etapa}; auditoría M09 del umbral ${gateway266.umbral_id}. Derivación inicial por efecto externo; causa raíz no determinada.`,
    escalamiento: null, severidad: 'ALTA',
    justificacion_severidad: 'La auditoría observó al menos un gateway fuera de las entidades QA; se detuvieron las escrituras siguientes de 266.',
    certeza: 'CONFIRMADA', causa_raiz: 'NO DETERMINADA' });
  for (const id of IDS_CASOS) {
    if (id === 'TC-M03-266' && r.casos?.[id]?.estado !== 'RECHAZADO') continue;
    const fallos = (r.comprobaciones ?? []).filter((x) => x.caso === id && x.estado === 'RECHAZADO' && x.naturaleza === 'PRODUCTO');
    if (!fallos.length) continue;
    const primera = fallos[0];
    const pre = (r.comprobaciones ?? []).filter((x) => x.caso === id && x.tipo === 'PRE');
    if (r.casos?.[id]?.veredicto_funcional !== 'RECHAZADO') continue;
    const newman = (r.evidencias ?? []).find((x) => id === 'TC-M03-266'
      ? /^newman\/newman-TC-M03-266-lectura-final\.json$/.test(x)
      : new RegExp(`^newman/newman-${id}-[^/]+\\.json$`).test(x));
    const captura = (r.evidencias ?? []).find((x) => id === 'TC-M03-172'
      ? /TC-M03-172.*\.png$/.test(x) : /^cypress\/.*\.png$/.test(x));
    const newman172 = (r.evidencias ?? []).find((x) => /^newman\/newman-TC-M03-172-consulta\.json$/.test(x));
    const captura172 = (r.evidencias ?? []).find((x) => /TC-M03-172.*\.png$/.test(x));
    const respuestaInicial266 = (r.respuestas ?? []).some((x) => x.caso === id && x.http === 200
      && /^\/iot\/monitoreo\/dashboard\?/.test(x.ruta)
      && x.cuerpo?.sensores?.some((sensor) => Number(sensor.ultimo_valor) === 15
        && ['VERDE', 'AMARILLO', 'ROJO'].includes(sensor.estado_semaforo)));
    const suficiente = id === 'TC-M03-172'
      ? r.casos?.[id]?.estado === 'RECHAZADO' && !!newman172 && !!captura172
        && fallos.some((x) => x.id === 'API-172-A') && fallos.some((x) => x.id === 'UI-172')
      : id === 'TC-M03-266' ? r.casos?.[id]?.estado === 'RECHAZADO'
        && (r.comprobaciones ?? []).some((x) => x.caso === id && x.id === 'API-266-01'
          && ['APROBADO', 'RECHAZADO'].includes(x.estado))
        && respuestaInicial266 && !!newman && !!primera.observado
      : pre.length > 0 && pre.every((x) => x.estado === 'APROBADO')
        && !!primera.observado && !!newman && (primera.fuente !== 'UI' || !!captura);
    const equipo = suficiente ? 'Desarrollo' : 'POR DETERMINAR';
    salida.push({ caso: id, comprobacion: primera.id, equipo,
      fundamento: suficiente ? `Primera discrepancia ${primera.fuente} ${primera.id}; E1: ${id === 'TC-M03-172' ? 'GET y UI concordantes' : id === 'TC-M03-266' ? 'semilla API y lectura inicial acreditadas' : 'PRE aprobadas'}; E2: observado ${limpio(primera.observado)}; E3: ${id === 'TC-M03-172' ? 'resultado.json' : newman}${id === 'TC-M03-266' ? ', GET dashboard inicial saneado en resultado.json' : ''}${captura ? `, ${captura}` : ''}. Derivación inicial; causa raíz no determinada.`
        : `Evidencia insuficiente para primer contacto: ${primera.id}.`,
      escalamiento: suficiente ? null : { responsable: 'responsable QA', evidencia_faltante: 'PRE aprobadas, observado concreto y reporte Newman; captura si es UI' },
      severidad: id === 'TC-M03-172' ? 'MEDIA' : id === 'TC-M03-266' || fallos.length > 1 ? 'ALTA' : 'MEDIA',
      justificacion_severidad: `${fallos.length} comprobación(es) funcional(es) discrepante(s) en ${id}; primera ${primera.id}, observado ${limpio(primera.observado)}. ${id === 'TC-M03-266' ? 'Bloquea el recálculo dinámico exigido.' : id === 'TC-M03-172' ? 'Falta la configurabilidad T exigida; la T por defecto sigue operativa, impacto parcial.' : 'Impacto parcial del semáforo o su presentación.'}`,
      certeza: 'CONFIRMADA', causa_raiz: 'NO DETERMINADA' });
  }
  return salida;
}

export function generarInforme(r) {
  return generarPresentacionG88(r);
}
