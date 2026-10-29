// Generación y validación local del informe; sin solicitudes ni creación de RUN.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { estadoMarcador } from './g87_cierre.mjs';

export const CASOS_G87 = ['TC-M03-168', 'TC-M03-177', 'TC-M03-178'];
const UI = new Set(['TC-M03-177', 'TC-M03-178']);
const REQUERIDAS = {
  'TC-M03-168': { API: [1, 2, 3, 4, 5].map((n) => `API-168-0${n}`) },
  'TC-M03-177': { API: [1, 2, 3].map((n) => `API-177-0${n}`), UI: [1, 2, 3].map((n) => `UI-177-0${n}`) },
  'TC-M03-178': { API: [1, 2, 3, 4, 5, 6, 7].map((n) => `API-178-0${n}`),
    UI: [1, 2, 3, 4, 5].map((n) => `UI-178-0${n}`) },
};
const EQUIPOS = new Set(['Desarrollo', 'AIoT', 'DBA', 'Implementación']);
const DIR = path.dirname(fileURLToPath(import.meta.url));
export function cargarTriaje(ruta = path.join(DIR, 'g87_triaje.json')) {
  return fs.existsSync(ruta) ? JSON.parse(fs.readFileSync(ruta, 'utf8')) : { casos: {} };
}
function ingestas(r, estado) {
  return (r.bitacora ?? []).flatMap((entrada) => {
    try { const x = JSON.parse(entrada.respuesta); return x.estado_calidad === estado && Number.isInteger(x.id_telemetria) ? [x.id_telemetria] : []; }
    catch { return []; }
  });
}
function describirIngestas(ids, estado, conVerbo = false) {
  const lista = ids.length === 1 ? String(ids[0]) : `${ids.slice(0, -1).join(', ')} y ${ids.at(-1)}`;
  const sujeto = ids.length === 1 ? 'ingesta' : 'ingestas';
  const participio = ids.length === 1 ? 'clasificada' : 'clasificadas';
  return `${conVerbo ? (ids.length === 1 ? 'la ' : 'las ') : ''}${sujeto} ${lista} ${conVerbo ? (ids.length === 1 ? 'fue ' : 'fueron ') : ''}${participio} ${estado}`;
}
function rutaEvidencia(r, ruta, opciones = {}) {
  if (typeof ruta !== 'string' || !ruta || path.isAbsolute(ruta) || ruta.split(/[\\/]/).includes('..')) return false;
  const base = opciones.baseDir ?? (r.run_id && Number.isInteger(r.version)
    ? path.join(DIR, '..', r.version === 1 ? 'Resultados' : `EvaluacionV${r.version}/Resultados`, r.run_id) : null);
  if (!base || !fs.existsSync(base)) return false;
  const destino = path.resolve(base, ruta);
  if (!destino.startsWith(path.resolve(base) + path.sep) || !fs.existsSync(destino)) return false;
  return fs.realpathSync(destino).startsWith(fs.realpathSync(base) + path.sep);
}
function valoresObservados(x) {
  const bruto = String(x?.obtenido ?? '');
  const inicio = bruto.indexOf('{');
  if (inicio < 0) return null;
  try {
    const obj = JSON.parse(bruto.slice(inicio, bruto.indexOf('}', inicio) + 1));
    const campos = Object.entries(obj).filter(([k, v]) => /^[\w]+$/.test(k) && v !== undefined).slice(0, 8);
    return campos.length ? campos.map(([k, v]) => `${k}=${limpiar(JSON.stringify(v))}`).join(', ') : null;
  } catch { return null; }
}
function escalamiento(faltantes) {
  return { responsable_qa: 'responsable QA', evidencia_requerida: faltantes.join('; '), faltantes };
}
function evidenciaComponente(r, x, opciones) {
  const e = x?.evidencia_componente;
  if (!e || typeof e.ruta !== 'string' || typeof e.registro !== 'string' || e.registro.length < 8
    || !rutaEvidencia(r, e.ruta, opciones)) return false;
  const base = opciones.baseDir ?? path.join(DIR, '..', r.version === 1 ? 'Resultados' : `EvaluacionV${r.version}/Resultados`, r.run_id);
  try { return fs.readFileSync(path.join(base, e.ruta), 'utf8').includes(e.registro); } catch { return false; }
}
export function asignarAtencion(r, caso, opciones = {}) {
  const rechazos = (r.comprobaciones ?? []).filter((x) => x.caso === caso && x.tipo === 'ASSERT' && x.estado === 'RECHAZADO' && !x.naturaleza);
  const api = rechazos.find((x) => x.fuente === 'API');
  const ui = rechazos.find((x) => x.fuente === 'UI');
  const triaje = opciones.triaje ?? cargarTriaje();
  const componente = triaje?.casos?.[caso];
  if (['AIoT', 'DBA', 'Implementación'].includes(componente?.componente_confirmado)
    && componente?.estado_verificacion === 'VERIFICADO'
    && evidenciaComponente(r, componente, opciones)) {
    const e = componente.evidencia_componente;
    const fundamento = `Componente ${componente.componente_confirmado} VERIFICADO; evidencia: ${limpiar(e.ruta)}; registro: ${limpiar(e.registro)}.`;
    return { equipo: componente.componente_confirmado, primera: fundamento, fundamento, evidencia: { componente: e }, api, ui };
  }
  if (api) {
    const pre = (r.comprobaciones ?? []).filter((x) => x.caso === caso && x.tipo === 'PRE' && x.fuente === 'API');
    const estado = triaje?.casos?.[caso]?.estadoIngesta;
    const numero = caso.split('-').at(-1);
    const ingestaPre = pre.filter((x) => x.descripcion?.includes(estado ?? '\u0000'));
    const ids = (r.bitacora ?? []).flatMap((entrada) => {
      if (entrada.en_run !== true || entrada.status !== 201
        || !new RegExp(`(^|\\D)${numero}(\\D|$)`).test(entrada.etiqueta ?? '')) return [];
      try { const v = JSON.parse(entrada.respuesta); return Number.isInteger(v.id_telemetria) && v.estado_calidad === estado
        ? [`${v.id_telemetria} ${v.estado_calidad}`] : []; } catch { return []; }
    });
    const valores = valoresObservados(api);
    const reporte = (r.evidencias ?? []).find((x) => /^newman\/[^/]+\.json$/.test(x));
    const rutas = ['resultado.json', reporte].filter(Boolean);
    const faltantes = [];
    if (!ingestaPre.length || pre.some((x) => x.estado !== 'APROBADO')) faltantes.push('E1: PRE API de clasificación aprobadas');
    if (!ids.length) faltantes.push('E1: IDs de telemetría del RUN con estado_calidad observado');
    if (!valores) faltantes.push('E2: ASSERT API rechazado con campos y valores observados');
    let reporteVerificado = false;
    if (reporte && rutaEvidencia(r, reporte, opciones)) {
      try {
        const base = opciones.baseDir ?? path.join(DIR, '..', r.version === 1 ? 'Resultados' : `EvaluacionV${r.version}/Resultados`, r.run_id);
        const n = JSON.parse(fs.readFileSync(path.join(base, reporte), 'utf8'));
        const aserciones = (n.run?.executions ?? []).flatMap((e) => e.assertions ?? []).map((a) => a.assertion ?? '');
        reporteVerificado = [...new Set(ingestaPre.map((x) => x.id)), api.id].every((id) => aserciones.some((a) => a.includes(id)));
      } catch { /* evidencia no verificable */ }
    }
    if (!reporte || !reporteVerificado || rutas.some((x) => !(r.evidencias ?? []).includes(x) || !rutaEvidencia(r, x, opciones)))
      faltantes.push('E3: resultado.json y reporte Newman existentes y referidos');
    if (!faltantes.length) {
      const fundamento = `E1: ${[...new Set(ingestaPre.map((x) => x.id))].join(', ')} APROBADOS; telemetría ${ids.join(', ')}. E2: ${api.id} RECHAZADO; ${valores}. E3: ${rutas.join('; ')}.`;
      return { equipo: 'Desarrollo', primera: `API (${api.id})`, fundamento, evidencia: { E1: ids, E2: api.id, E3: rutas }, api, ui };
    }
    return { equipo: 'POR DETERMINAR', primera: `API (${api.id}); evidencia insuficiente`, fundamento: `Faltan ${faltantes.join('; ')}`, escalamiento: escalamiento(faltantes), api, ui };
  }
  if (ui) {
    const equivalentes = (r.comprobaciones ?? []).filter((x) => x.caso === caso && x.tipo === 'ASSERT' && x.fuente === 'API');
    const captura = (r.evidencias ?? []).find((x) => x.startsWith('cypress/') && x.includes(caso.slice(-3)) && rutaEvidencia(r, x, opciones));
    const detalle = String(ui.obtenido ?? '').includes('detalle=') && rutaEvidencia(r, 'resultado.json', opciones) ? 'resultado.json' : null;
    const observado = String(ui.observado_pantalla ?? (/detalle=([^:]+)/.exec(String(ui.obtenido ?? ''))?.[1] ?? '')).slice(0, 300);
    const faltantes = [];
    if (!equivalentes.length || equivalentes.some((x) => x.estado !== 'APROBADO')) faltantes.push('UI: ASSERT API equivalentes APROBADOS');
    if (!observado.trim()) faltantes.push('UI: observado concreto en pantalla');
    if (!captura && !detalle) faltantes.push('UI: captura real o detalle textual conservado');
    if (!faltantes.length) {
      const fundamento = `UI: API ${equivalentes.map((x) => x.id).join(', ')} APROBADOS; ${ui.id} RECHAZADO, observado ${limpiar(observado)}; evidencia ${captura ?? detalle}.`;
      return { equipo: 'Desarrollo', primera: `UI (${ui.id})`, fundamento, evidencia: { UI: captura ?? detalle }, api, ui };
    }
    return { equipo: 'POR DETERMINAR', primera: `UI (${ui.id}); evidencia insuficiente`, fundamento: `Faltan ${faltantes.join('; ')}`, escalamiento: escalamiento(faltantes), api, ui };
  }
  const faltantes = ['E2/UI: comprobación ASSERT rechazada localizable'];
  return { equipo: 'POR DETERMINAR', primera: 'sin comprobación localizable', fundamento: `Faltan ${faltantes[0]}`, escalamiento: escalamiento(faltantes), api, ui };
}
export function validarIncidencia(x) {
  const errores = [];
  if (x.responsable !== 'POR DETERMINAR' && !EQUIPOS.has(x.responsable)) errores.push('equipo no permitido');
  if (x.confirmada && x.responsable === 'POR DETERMINAR' && !(x.escalamiento?.responsable_qa && x.escalamiento?.evidencia_requerida && x.escalamiento?.faltantes?.length))
    errores.push('incidencia funcional confirmada sin equipo inicial: requiere escalamiento explícito');
  if (x.confirmada && !x.responsable) errores.push('incidencia funcional confirmada sin responsable');
  if (x.confirmada && x.responsable !== 'POR DETERMINAR' && (!x.fundamento || !x.verificacion || !x.evidencia_asignacion || !x.contexto)) errores.push('derivación sin fundamento verificable o verificación');
  if (x.confirmada && x.responsable !== 'POR DETERMINAR' && x.contexto) {
    const comprobada = asignarAtencion(x.contexto.resultado, x.contexto.caso, x.contexto.opciones);
    if (comprobada.equipo !== x.responsable || comprobada.fundamento !== x.fundamento
      || JSON.stringify(comprobada.evidencia) !== JSON.stringify(x.evidencia_asignacion))
      errores.push('responsable sin fundamento verificable en el RUN');
  }
  if (x.hipotesis && !/^HIPÓTESIS:/u.test(x.hipotesis)) errores.push('hipótesis sin rótulo');
  return errores;
}
const limpiar = (x) => String(x ?? 'sin determinar').replace(/[\r\n|]+/g, ' ').slice(0, 500);
const criterio = {
  'TC-M03-168': 'HTTP 200. Por cada sensor se devuelven ultimo_valor, ultima_unidad y ultimo_timestamp_captura correspondientes a la última lectura LECTURA_VALIDA, no a la posterior inválida.',
  'TC-M03-177': 'La lectura FUERA_DE_RANGO no se utiliza como lectura operativa activa; el dashboard conserva la última LECTURA_VALIDA como referencia, y la anomalía permanece visible mediante un indicador claro (ROJO/ícono), sin ocultarse ni descartarse.',
  'TC-M03-178': 'Productor: ERROR_CALIBRACION no se presenta como lectura operativa ni genera alerta operativa, sin exponer información técnica reservada al Ingeniero. Ingeniero de Campo: identifica el sensor con condición de error técnico y visualiza el detalle necesario para reconocer que requiere calibración. El sensor permanece visible y la lectura inválida no se trata como operacional normal.',
};
const fallo = (r, id) => r.comprobaciones?.find((x) => x.id === id && x.estado === 'RECHAZADO');
function jsonFallo(r, id) {
  try { return JSON.parse(fallo(r, id)?.obtenido?.match(/^\{.*?\}(?=:|$)/)?.[0] ?? '{}'); } catch { return {}; }
}
const fin = (x) => String(x ?? '').replace(/[.!?]+$/, '');
const enlace = (ruta, prefijo = '') => `[${ruta}](${prefijo}${ruta})`;
function ultimaValidaAnteriorS2(r) {
  const sensor = r.datos?.s2?.id;
  const vistas = (r.bitacora ?? []).flatMap((entrada) => {
    try {
      const respuesta = JSON.parse(entrada.respuesta);
      return Array.isArray(respuesta) ? respuesta : [];
    } catch { return []; }
  });
  return vistas.filter((x) => x.id_sensor === sensor && x.estado_calidad === 'LECTURA_VALIDA'
    && x.ultimo_valor != null && x.ultimo_timestamp_captura)
    .sort((a, b) => b.ultimo_timestamp_captura.localeCompare(a.ultimo_timestamp_captura))[0];
}

export function problemaCypress(res) {
  return (res.total_pruebas ?? 0) > 0 ? null : res.motivo ?? '0 comprobaciones';
}

export function requeridasFaltantes(r, caso) {
  return Object.entries(REQUERIDAS[caso] ?? {}).flatMap(([fuente, ids]) => ids.filter((id) =>
    !r.comprobaciones.some((x) => x.caso === caso && x.fuente === fuente && x.tipo === 'ASSERT'
      && x.id === id && ['APROBADO', 'RECHAZADO'].includes(x.estado))));
}

export function oficialidad(r) {
  return CASOS_G87.every((caso) => requeridasFaltantes(r, caso).length === 0
    && (!UI.has(caso) || (r.cypress?.total_pruebas ?? 0) > 0))
    && r.cierre?.run?.cierre_http === 200 && r.cierre?.rollback?.verificado === true;
}

export function validarResultadoLocal(r, nombres = [], baseDir = null, markdown = null) {
  const errores = [];
  if (r.grupo !== 'TC-M03-G87' || !Number.isInteger(r.version) || r.version < 1
    || !new RegExp(`^RUN-G87-V${r.version}-\\d{8}-\\d{6}$`).test(r.run_id ?? '')) errores.push('RUN/grupo/versión incoherentes');
  if (Object.keys(r.casos ?? {}).sort().join() !== [...CASOS_G87].sort().join()) errores.push('casos incompletos');
  const oficial = r.version === 1 ? 'TC-M03-G87_resultado.md' : `TC-M03-G87_reevaluacion_V${r.version}.md`;
  if (nombres.filter((x) => x.endsWith('.md')).length !== 1 || !nombres.includes(oficial)) errores.push('se exige un único Markdown oficial');
  if (nombres.some((x) => x.startsWith('../'))) errores.push('evidencia fuera del RUN');
  if (Object.entries(r.casos ?? {}).some(([id, v]) => UI.has(id) && v.estado === 'APROBADO'
    && !(r.cypress?.total_pruebas > 0))) errores.push('UI aprobada con cero pruebas');
  if (r.oficial && !oficialidad(r)) errores.push('oficialidad inconsistente');
  for (const x of r.incidencias_funcionales ?? []) errores.push(...validarIncidencia({ ...x, confirmada: x.confirmada ?? r.oficial,
    contexto: { resultado: r, caso: x.caso, opciones: { baseDir } } }));
  if (r.oficial) for (const id of CASOS_G87.filter((caso) => (r.comprobaciones ?? []).some((x) => x.caso === caso && x.tipo === 'ASSERT' && x.estado === 'RECHAZADO' && !x.naturaleza))) {
    if (asignarAtencion(r, id, { baseDir }).equipo === 'POR DETERMINAR' && !(markdown?.includes('**Escalamiento de asignación:** a responsable QA; falta ')))
      errores.push(`incidencia ${id} sin equipo inicial ni escalamiento explícito`);
  }
  if (baseDir) for (const nombre of nombres) if (!fs.existsSync(`${baseDir}/${nombre}`)) errores.push(`evidencia inexistente: ${nombre}`);
  if (markdown) {
    if (!markdown.includes(r.run_id) || !markdown.includes(`V${r.version}`)) errores.push('informe no coincide con RUN/versión');
    for (const id of CASOS_G87) if (!markdown.includes(`${id} | ${r.casos?.[id]?.estado}`)) errores.push(`veredicto discordante: ${id}`);
    for (const [estado, etiqueta] of [['APROBADO', 'Aprobados'], ['RECHAZADO', 'rechazados'],
      ['BLOQUEADO', 'bloqueados'], ['ERROR_QA', 'ERROR_QA']]) {
      const total = Object.values(r.casos ?? {}).filter((x) => x.estado === estado).length;
      if (!markdown.includes(`${etiqueta} ${total}`)) errores.push(`contador discordante: ${estado}`);
    }
    if (!markdown.includes(`Oficialidad: ${r.oficial ? 'OFICIAL' : 'NO OFICIAL'}`)) errores.push('oficialidad discordante');
    if (!markdown.includes(`Cierre RUN HTTP ${r.cierre?.run?.cierre_http ?? 'no abierto'}`)) errores.push('cierre discordante');
    if (/eyJ[\w-]{5,}\.[\w-]{5,}\.[\w-]{5,}|[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/i.test(markdown))
      errores.push('posible secreto o dato privado en informe');
  }
  return errores;
}

function resumenCaso(r, id) {
  const estado = r.casos?.[id]?.estado;
  if (estado === 'APROBADO') return id === 'TC-M03-168'
    ? 'La API conservó valor, unidad y hora de la última lectura válida.' : 'Se cumplieron los criterios comprobados.';
  if (estado === 'RECHAZADO' && id === 'TC-M03-177') return 'La lectura válida siguió como referencia, pero la anomalía posterior quedó invisible para el Productor.';
  if (estado === 'RECHAZADO' && id === 'TC-M03-178') return 'El Productor recibió la vista prevista; el Ingeniero no vio la necesidad de calibración.';
  if (estado === 'RECHAZADO' && id === 'TC-M03-168') return 'La API no cumplió todos los campos exigidos para la última lectura válida.';
  return limpiar(r.casos?.[id]?.motivo);
}

function obtenido(r, x) {
  if (x.estado === 'APROBADO') return 'Criterio verificado en el RUN.';
  const v = jsonFallo(r, x.id);
  if (x.id === 'API-177-03') return `Valor ${v.ultimo_valor ?? 'sin dato'} ${v.ultima_unidad ?? ''}; calidad ${v.estado_calidad ?? 'sin dato'}; semáforo ${v.estado_semaforo ?? 'sin dato'}; alerta ${v.id_alerta ?? 'ninguna'}.`;
  if (x.id === 'UI-177-03') return 'Tarjeta en verde con «Normal»; no se encontró indicador ROJO ni ícono de anomalía.';
  if (x.id === 'API-178-06') return `Valor ${v.ultimo_valor ?? 'sin dato'}; calidad ${v.estado_calidad ?? 'sin dato'}; semáforo ${v.estado_semaforo ?? 'sin dato'}; batería ${v.nivel_bateria_pct ?? 'sin dato'} %; RSSI ${v.calidad_senal_rssi ?? 'sin dato'} dBm; sin indicador de calibración.`;
  if (x.id === 'UI-178-05') return 'Detalle con lectura válida y «Normal», batería y señal; no indica necesidad de calibración.';
  if (x.estado === 'RECHAZADO') return 'No se cumplió el criterio; mensaje original en el anexo técnico.';
  return limpiar(x.motivo ?? x.estado);
}

function narrativa(r, id, prefijo) {
  const d = r.datos ?? {}, lect = d.lecturas ?? {}, s = id === 'TC-M03-178' ? d.s2 : d.s1;
  const v177 = jsonFallo(r, 'API-177-03'), v178 = jsonFallo(r, 'API-178-06');
  const cap177 = 'cypress/g87.cy.js/TC-M03-177_productor_S1.png';
  const cap178 = 'cypress/g87.cy.js/TC-M03-178_ingeniero_S2.png';
  const capProd = 'cypress/g87.cy.js/TC-M03-178_productor_S2.png';
  const S = ['**Qué se quería comprobar.** ' + criterio[id]];
  if (id === 'TC-M03-168' || id === 'TC-M03-177') {
    S.push(`**Cómo se preparó.** Sensor ${s?.id ?? 'sin determinar'}, dispositivo ${s?.dispositivo ?? 'sin determinar'}, área ${d.area ?? 'sin determinar'}: lecturas ${[lect.v_a1, lect.v_a2, lect.v_a3].filter((x) => x != null).join(', ') || 'sin determinar'} °C clasificadas LECTURA_VALIDA y después ${lect.v_fuera ?? 'sin determinar'} °C FUERA_DE_RANGO; umbral ${d.umbral?.min ?? 'sin determinar'}–${d.umbral?.max ?? 'sin determinar'} °C. Consulta del Productor.`);
    S.push(`**Qué debía verse.** ${id === 'TC-M03-168' ? 'HTTP 200 y valor, unidad y hora de la última lectura válida, sin tomar la lectura posterior inválida.' : 'La lectura válida como referencia operativa y un indicador ROJO o ícono que avisara de la anomalía.'}`);
    if (id === 'TC-M03-168') S.push(r.casos?.[id]?.estado === 'APROBADO'
      ? `**Qué se vio realmente.** Las comprobaciones API aprobaron HTTP 200 y la correspondencia con la última válida${v177.ultimo_valor ? `: ${v177.ultimo_valor} ${v177.ultima_unidad ?? '°C'}, capturada a las ${v177.ultimo_timestamp_captura ?? 'hora sin determinar'}` : ''}. La lectura posterior no reemplazó esa referencia. No se exigía UI para este caso.`
      : '**Qué se vio realmente.** Hay comprobaciones API no aprobadas; los datos concretos constan en la tabla y en resultado.json. No se exigía UI para este caso.');
    else S.push(fallo(r, 'API-177-03') && fallo(r, 'UI-177-03')
      ? `**Qué se vio realmente.** La API entregó ${v177.ultimo_valor ?? 'sin dato'} ${v177.ultima_unidad ?? '°C'}, calidad ${v177.estado_calidad ?? 'sin dato'}, semáforo ${v177.estado_semaforo ?? 'sin dato'} y alerta ${v177.id_alerta ?? 'ninguna'}. La captura ${enlace(cap177, prefijo)} muestra ${v177.ultimo_valor ?? 'sin dato'} °C en verde con «Normal», sin ROJO ni ícono de anomalía.`
      : `**Qué se vio realmente.** Las comprobaciones API y UI quedaron ${r.casos?.[id]?.estado ?? 'sin determinar'}; los valores y capturas disponibles constan en la tabla y las evidencias.`);
    S.push(`**Conclusión.** ${r.casos?.[id]?.estado ?? 'Sin veredicto'}: ${resumenCaso(r, id)}`);
  } else {
    S.push(`**Cómo se preparó.** Sensor ${s?.id ?? 'sin determinar'}, dispositivo ${s?.dispositivo ?? 'sin determinar'}, sin calibración: lecturas ${[lect.v_c1, lect.v_c2].filter((x) => x != null).join(' y ') || 'sin determinar'} °C clasificadas ERROR_CALIBRACION. Se consultó como Productor y como Ingeniero de Campo.`);
    S.push('**Qué debía verse.** El Productor no debía recibir una lectura ni alerta operativa por el error, ni datos técnicos. El Ingeniero debía ver el sensor, el error técnico y el detalle que indicara que requiere calibración, sin tratar la lectura inválida como normal.');
    S.push(fallo(r, 'API-178-06') && fallo(r, 'UI-178-05')
      ? `**Qué se vio realmente.** Las comprobaciones del Productor aprobaron y su ${enlace(capProd, prefijo)} no muestra datos técnicos. Para el Ingeniero, la API devolvió ${v178.ultimo_valor ?? 'sin dato'} °C, calidad ${v178.estado_calidad ?? 'sin dato'}, semáforo ${v178.estado_semaforo ?? 'sin dato'}, batería ${v178.nivel_bateria_pct ?? 'sin dato'} % y RSSI ${v178.calidad_senal_rssi ?? 'sin dato'} dBm, sin indicador de calibración. El valor mostrado corresponde a la última lectura VÁLIDA anterior del sensor ${s?.id ?? 'sin determinar'}, capturada el ${ultimaValidaAnteriorS2(r)?.ultimo_timestamp_captura ?? 'momento sin determinar'}, según resultado.json. Las dos lecturas nuevas de ${[lect.v_c1, lect.v_c2].join(' y ')} °C, clasificadas ERROR_CALIBRACION, no aparecen en esa vista. La ${enlace(cap178, prefijo)} muestra la tarjeta verde «Normal»; el detalle textual conservado en resultado.json también muestra «Normal» y LECTURA_VALIDA, sin mencionar calibración.`
      : `**Qué se vio realmente.** Las comprobaciones API y UI quedaron ${r.casos?.[id]?.estado ?? 'sin determinar'}; los valores y capturas disponibles constan en la tabla y las evidencias.`);
    S.push(`**Conclusión.** ${r.casos?.[id]?.estado ?? 'Sin veredicto'}: el Ingeniero solo vio la lectura válida anterior de ${ultimaValidaAnteriorS2(r)?.ultimo_valor ?? 'valor sin determinar'} °C; las dos lecturas nuevas ERROR_CALIBRACION no aparecen y no puede reconocer la necesidad de calibración en esa vista.`);
  }
  return S;
}

function incidencia(r, id, indice, prefijo, triaje) {
  const d = r.datos ?? {}, l = d.lecturas ?? {}, s = id === 'TC-M03-177' ? d.s1 : d.s2;
  const t = triaje?.casos?.[id];
  const atencion = asignarAtencion(r, id, { triaje });
  if (id === 'TC-M03-168') return [
    `### REF-G87-${String(indice).padStart(2, '0')} — La API no conserva todos los campos de la última lectura válida`, '',
    '**ID:** provisional; no es un ticket.', `**Caso y requisito afectado:** ${id}. «${criterio[id]}»`,
    '**Descripción:** La consulta del Productor no satisface todas las comprobaciones API de valor, unidad y hora de la última lectura válida.',
    '**Pasos para reproducir:**',
    `1. Usar el RUN ${r.run_id}: sensor ${d.s1?.id ?? 'sin determinar'}, dispositivo ${d.s1?.dispositivo ?? 'sin determinar'}, área ${d.area ?? 'sin determinar'}.`,
    `2. Enviar ${l.v_a1}, ${l.v_a2} y ${l.v_a3} °C válidos y después ${l.v_fuera} °C FUERA_DE_RANGO.`,
    '3. Consultar GET /iot/monitoreo/dashboard como Productor y comparar valor, unidad y hora con la última lectura válida.',
    `**Resultado esperado:** ${criterio[id]}`,
    `**Resultado obtenido:** ${r.comprobaciones.filter((x) => x.caso === id && x.estado === 'RECHAZADO').map((x) => `${x.id}: ${obtenido(r, x)}`).join(' ')}`,
    `**Evidencia:** ${enlace('resultado.json', prefijo)}; ${enlace('newman/newman-TC-M03-G87.json', prefijo)}; ${enlace('newman/newman-TC-M03-G87.html', prefijo)}. UI no requerida para este caso.`,
    '**Impacto para el usuario:** La referencia operativa puede no corresponder a la última lectura válida.',
    '**Severidad:** MEDIA. Impacto demostrado en el escenario del RUN; alcance general sin determinar.',
    `**Responsable inicial de atención y diagnóstico:** **${atencion.equipo}**. La asignación orienta la investigación; no certifica la causa raíz.`,
    `**Fundamento de asignación:** ${atencion.fundamento}`,
    ...(atencion.escalamiento ? [`**Escalamiento de asignación:** a ${atencion.escalamiento.responsable_qa}; falta ${atencion.escalamiento.evidencia_requerida}.`] : []),
    '**Certeza:** incumplimiento funcional CONFIRMADO; causa raíz NO CONFIRMADA.',
    ...(t?.hipotesis ? [`**Causa probable — HIPÓTESIS:** ${t.hipotesis}`] : []),
    ...(t?.puntos ? [`**Puntos concretos de investigación:** ${t.puntos}`] : []),
    `**Verificación a cargo de ${atencion.equipo}:** ${t?.verificacion ?? 'Contrastar entrada, contrato y respuesta; localizar la causa con evidencia antes de reasignar.'}`,
    `**Acción correctiva esperada:** ${t?.accion ?? 'Corregir el componente acreditado y solicitar reevaluación con autorización QA.'}`,
  ];
  const v = jsonFallo(r, id === 'TC-M03-177' ? 'API-177-03' : 'API-178-06');
  const apiIncumple = Boolean(atencion.api);
  const uiIncumple = Boolean(atencion.ui);
  const ids = t?.estadoIngesta ? ingestas(r, t.estadoIngesta) : [];
  const cap = id === 'TC-M03-177' ? 'cypress/g87.cy.js/TC-M03-177_productor_S1.png'
    : 'cypress/g87.cy.js/TC-M03-178_ingeniero_S2.png';
  const titulo = id === 'TC-M03-177'
    ? 'El dashboard del Productor no muestra la lectura fuera de rango: el sensor aparece en verde como Normal'
    : 'El Ingeniero no ve que el sensor necesita calibración: aparece como Normal';
  const R = [`### REF-G87-${String(indice).padStart(2, '0')} — ${titulo}`, '',
    '**ID:** provisional; no es un ticket.', `**Caso y requisito afectado:** ${id}. «${criterio[id]}»`,
    `**Descripción:** ${id === 'TC-M03-177' ? 'El Productor ve la última lectura válida, pero no recibe una señal visual de la lectura posterior fuera de rango.' : `El Ingeniero ve la última lectura válida anterior del sensor ${s?.id ?? 'sin determinar'} (${ultimaValidaAnteriorS2(r)?.ultimo_valor ?? 'sin dato'} °C, ${ultimaValidaAnteriorS2(r)?.ultimo_timestamp_captura ?? 'fecha sin determinar'}), pero las dos lecturas nuevas ERROR_CALIBRACION no aparecen y el dashboard no comunica la necesidad de calibración.`}`,
    '**Pasos para reproducir:**',
    `1. Usar el RUN ${r.run_id}: sensor ${s?.id ?? 'sin determinar'}, dispositivo ${s?.dispositivo ?? 'sin determinar'}, área ${d.area ?? 'sin determinar'}${id === 'TC-M03-178' ? ', sin calibración' : `, umbral ${d.umbral?.min ?? 'sin determinar'}–${d.umbral?.max ?? 'sin determinar'} °C`}.`,
    `2. Enviar en orden ${id === 'TC-M03-177' ? `${l.v_a1}, ${l.v_a2} y ${l.v_a3} °C como LECTURA_VALIDA; después ${l.v_fuera} °C como FUERA_DE_RANGO` : `${l.v_c1} y ${l.v_c2} °C como ERROR_CALIBRACION`}.`,
    `3. Consultar GET /iot/monitoreo/dashboard y abrir Monitoreo como ${id === 'TC-M03-177' ? 'Productor' : 'Ingeniero de Campo'}; ver la tarjeta del sensor y${id === 'TC-M03-178' ? ' su detalle' : ' el indicador de anomalía'}.`,
    `**Resultado esperado:** ${criterio[id]}`,
    `**Resultado obtenido:** API: valor ${v.ultimo_valor ?? 'sin dato'} ${id === 'TC-M03-177' ? (v.ultima_unidad ?? '°C') : '°C'}, estado_calidad ${v.estado_calidad ?? 'sin dato'}, estado_semaforo ${v.estado_semaforo ?? 'sin dato'}, id_alerta ${v.id_alerta ?? 'ninguna'}${id === 'TC-M03-178' ? `, batería ${v.nivel_bateria_pct ?? 'sin dato'} %, RSSI ${v.calidad_senal_rssi ?? 'sin dato'} dBm; es la última lectura válida anterior del sensor ${s?.id ?? 'sin determinar'} (${ultimaValidaAnteriorS2(r)?.ultimo_timestamp_captura ?? 'fecha sin determinar'}). Las lecturas nuevas ${l.v_c1} y ${l.v_c2} °C ERROR_CALIBRACION no aparecen en la vista` : ''}. UI: tarjeta verde «Normal»${id === 'TC-M03-177' ? ', sin ROJO ni ícono' : '; el detalle textual tampoco menciona calibración'}. Captura: ${enlace(cap, prefijo)}.`,
    `**Evidencia:** ${enlace('resultado.json', prefijo)}; ${enlace('newman/newman-TC-M03-G87.json', prefijo)}; ${enlace('newman/newman-TC-M03-G87.html', prefijo)}; ${enlace(cap, prefijo)}.`,
    `**Impacto para el usuario:** ${id === 'TC-M03-177' ? 'El Productor puede pasar por alto una temperatura anómala porque el sensor parece normal.' : 'El Ingeniero no puede reconocer en esa vista que debe calibrar el sensor.'}`,
    '**Severidad:** MEDIA. El RUN demuestra un fallo funcional parcial en este escenario; el alcance general y la disponibilidad de otras vías de aviso no están determinados.',
    `**Responsable inicial de atención y diagnóstico:** **${atencion.equipo}**. La asignación orienta la investigación; no certifica la causa raíz.`,
    `**Fundamento de asignación:** ${atencion.fundamento}`,
    ...(atencion.escalamiento ? [`**Escalamiento de asignación:** a ${atencion.escalamiento.responsable_qa}; falta ${atencion.escalamiento.evidencia_requerida}.`] : []),
    `**Certeza:** incumplimiento funcional CONFIRMADO (${[apiIncumple ? 'API' : null, uiIncumple ? 'UI' : null].filter(Boolean).join(' y ') || 'comprobación registrada'}); causa raíz NO CONFIRMADA. El código exacto desplegado en TEST no se verificó.`,
    ...(t?.hipotesis ? [`**Causa probable — HIPÓTESIS:** ${t.hipotesis}`] : []),
    ...(t?.puntos ? [`**Puntos concretos de investigación:** ${t.puntos}`] : []),
    `**Verificación a cargo de ${atencion.equipo}:** ${t?.verificacion ?? 'Contrastar entradas, API y UI; ubicar la causa con evidencia antes de reasignar.'}`,
    `**Acción correctiva esperada:** ${t?.accion ?? 'Corregir el componente acreditado y solicitar reevaluación solo con autorización QA.'}`, ''];
  return R;
}

export function generarInforme(r, definiciones, opciones = {}) {
  const prefijo = opciones.prefijoEvidencia ?? '';
  const triaje = opciones.triaje ?? cargarTriaje();
  const estados = ['APROBADO', 'RECHAZADO', 'BLOQUEADO', 'ERROR_QA', 'NO EJECUTADO'];
  const totales = Object.fromEntries(estados.map((e) => [e, Object.values(r.casos ?? {}).filter((v) => v.estado === e).length]));
  const fallos = r.comprobaciones.filter((x) => x.tipo === 'ASSERT' && x.estado === 'RECHAZADO' && !x.naturaleza);
  const afectados = CASOS_G87.filter((id) => fallos.some((x) => x.caso === id));
  const qa = (r.incidencias ?? []).filter((x) => /ERROR_QA|automatizaci[oó]n/i.test(x)
    && !((r.cypress?.total_pruebas ?? 0) > 0 && /^ERROR_QA: Cypress: 0 comprobaciones$/.test(x)));
  const evidencias = r.evidencias ?? ['resultado.json'];
  const L = [`# RESULTADO DE EVALUACIÓN — TC-M03-G87 — V${r.version}`, '', '## Identificación', '',
    `Proyecto SIGAB/SGPMP; módulo 3; RF-58; G87; ${CASOS_G87.join(', ')}.`,
    `RUN ${r.run_id}; intento ${r.intento ?? 'sin determinar'}; operación ${r.operacion ?? r.tipo ?? 'sin determinar'}; ambiente ${r.ambiente ?? 'sin determinar'}; ${r.inicio ?? 'sin determinar'} → ${r.fin ?? 'sin determinar'}; autorización ${limpiar(r.referencia)}.`,
    `Responsable QA de la matriz: Juan Esteban. Rama local: ${opciones.gitLocal?.rama ?? 'sin determinar'}; commit local: ${opciones.gitLocal?.commit ?? 'sin determinar'}. Rama y commit desplegados en TEST: sin determinar.`,
    `Herramientas verificadas en el RUN: Node ${r.herramientas?.node ?? 'sin determinar'}; Newman ${r.herramientas?.newman ?? 'versión sin determinar'}; Cypress/Chrome ${r.cypress?.version ?? 'versión sin determinar'}.`,
    ...(opciones.hashOriginal ? [`Segunda regeneración documental ${triaje.documentacion?.fechaUTC ?? 'fecha sin determinar'} (${triaje.documentacion?.orden ?? 'orden sin determinar'}) a partir de las evidencias sin cambios del RUN; reemplazaría al informe vigente (SHA-256 ${opciones.hashOriginal}), previa conservación de su copia fuera del RUN. La primera regeneración fue ${triaje.documentacion?.primeraOrden ?? 'orden sin determinar'} y reemplazó el informe original (SHA-256 ${triaje.documentacion?.hashOriginalPrimero ?? 'sin determinar'}). resultado.json conserva un aviso QA erróneo ('Cypress: 0 comprobaciones') no aplicable: Cypress ejecutó ${r.cypress?.total_pruebas ?? 0} pruebas.`] : []),
    '', '## Resumen ejecutivo', '',
    `Aprobados ${totales.APROBADO}; rechazados ${totales.RECHAZADO}; bloqueados ${totales.BLOQUEADO}; ERROR_QA ${totales.ERROR_QA}; no ejecutados ${totales['NO EJECUTADO']}.`,
    `Incidencias funcionales observadas: ${afectados.length}. Veredicto grupal: ${r.veredicto_grupo ?? 'sin determinar'}. Estado ${r.estado}; Oficialidad: ${r.oficial ? 'OFICIAL' : 'NO OFICIAL'}.`,
    '', '| Caso | Veredicto | Motivo |', '| --- | --- | --- |'];
  for (const id of CASOS_G87) L.push(`| ${id} | ${r.casos?.[id]?.estado ?? 'sin determinar'} | ${resumenCaso(r, id)} |`);
  if (r.version >= 2) {
    const a = r.alcance_reevaluacion ?? {};
    L.push('', '## Alcance de reevaluación', '', `Versión anterior: V${a.version_anterior ?? 'sin determinar'}; casos reevaluados: ${Array.isArray(a.casos) ? a.casos.join(', ') : 'sin determinar'}.`,
      `Motivo: ${limpiar(a.motivo)}. Incumplimientos previos: ${limpiar(a.incumplimientos_previos)}.`,
      `Correcciones informadas por el responsable QA: ${String(a.correcciones_informadas ?? 'sin determinar')}.`,
      `Resultado esperado: ${limpiar(a.resultado_esperado)}. Resultado observado: ${limpiar(r.veredicto_grupo)}.`,
      'Incidencias resueltas: ' + (a.incidencias_resueltas == null ? 'no determinadas' : String(a.incidencias_resueltas)) + '.',
      'Incidencias persistentes: ' + (a.incidencias_persistentes == null ? 'no determinadas' : String(a.incidencias_persistentes)) + '.',
      'Incidencias no concluyentes: ' + (a.incidencias_no_concluyentes == null ? 'no determinadas' : String(a.incidencias_no_concluyentes)) + '.',
      'Incidencias nuevas: ' + (a.incidencias_nuevas == null ? 'no determinadas' : String(a.incidencias_nuevas)) + '.');
  }
  L.push('', '## Resultado por caso');
  for (const id of CASOS_G87) {
    L.push('', `### ${id} — ${definiciones[id]?.titulo ?? id}`, '', ...narrativa(r, id, prefijo), '',
      `Comprobaciones requeridas: API${UI.has(id) ? ' y UI' : ''}; pruebas Cypress del RUN: ${UI.has(id) ? r.cypress?.total_pruebas ?? 0 : 'no aplica'}.`,
      '', '| Comprobación | Fuente | Estado | Obtenido |', '| --- | --- | --- | --- |');
    for (const x of r.comprobaciones.filter((y) => y.caso === id))
      L.push(`| ${limpiar(x.id + ' ' + x.descripcion)} | ${x.fuente} | ${x.estado} | ${limpiar(obtenido(r, x))} |`);
    L.push('', `Evidencia: ${evidencias.filter((x) => x === 'resultado.json' || x.startsWith('newman/') || (UI.has(id) && x.startsWith('cypress/') && x.includes(id.slice(-3)))).map((x) => enlace(x, prefijo)).join(', ')}.`);
  }
  L.push('', '## Incidencias funcionales', '');
  if (!afectados.length) L.push('Ninguna confirmada en los criterios ejecutados.');
  for (const [i, id] of afectados.entries()) L.push(...incidencia(r, id, i + 1, prefijo, triaje));
  L.push('', '## Clasificación de bloqueos y discrepancias', '');
  const pendientes = r.comprobaciones.filter((x) => ['BLOQUEADO', 'ERROR_QA', 'NO EJECUTADO', 'NO_EJECUTADA'].includes(x.estado));
  if (!pendientes.length) L.push('Sin comprobaciones bloqueadas o incompletas.');
  for (const x of pendientes) L.push(`- ${x.caso} ${x.id}: ${x.naturaleza === 'AUTOMATIZACION' ? 'automatización QA' : x.naturaleza === 'PREPARACION' ? 'datos o preparación' : 'precondición o entorno'}; causa sin determinar. Detalle en resultado.json.`);
  L.push('', '## Problemas de automatización QA', '', ...(qa.length ? qa.map((x) => `- ${limpiar(x)}`) : ['Ninguno.']),
    '', '## Análisis de fallos', '',
    `**Hechos confirmados:** ${fallos.length} comprobaciones funcionales fallidas, agrupadas en ${afectados.length} incidencias. ${afectados.map((id) => { const t = triaje.casos?.[id]; const ids = t?.estadoIngesta ? ingestas(r, t.estadoIngesta) : []; return ids.length ? `${id}: ${describirIngestas(ids, t.estadoIngesta)}` : `${id}: clasificación de ingesta no constatada en este triaje`; }).join('; ')}. Primer punto comprobado de discrepancia: ${afectados.map((id) => `${id}: ${asignarAtencion(r, id).primera}`).join('; ') || 'ninguno'}. ${r.casos?.['TC-M03-168']?.estado === 'APROBADO' ? 'TC-M03-168 aprobó la conservación de la última lectura válida; debe preservarse ese comportamiento.' : ''}`,
    '', `**Diagnóstico preliminar y asignación:** ${afectados.map((id) => `${id}: ${asignarAtencion(r, id).equipo}`).join('; ') || 'sin incidencias funcionales'}. La causa raíz NO está confirmada. Los puntos de investigación específicos se indican en cada incidencia y provienen de ${triaje.origen ?? 'datos de triaje no disponibles'}. El código local no está acreditado como desplegado en TEST.`,
    '', '**Responsable de confirmar la causa:** el equipo inicial debe contrastar la revisión desplegada, la ingesta, persistencia, API y UI. Apoyos de AIoT, DBA o Implementación requieren señales propias de sus componentes; cualquier reasignación debe registrar evidencia y motivo.',
    '', '## Herramientas, evidencias y rollback', '',
    `Newman: ${r.newman?.solicitudes ?? 'sin determinar'} solicitudes, ${r.newman?.aserciones ?? 'sin determinar'} aserciones, ${r.newman?.fallidas ?? 'sin determinar'} fallidas. Cypress: ${r.cypress?.total_pruebas ?? 0} pruebas ejecutadas, ${r.comprobaciones.filter((x) => x.fuente === 'UI').length} comprobaciones registradas.`,
    `Archivos existentes: ${evidencias.map((x) => enlace(x, prefijo)).join(', ')}.`,
    `Cierre RUN HTTP ${r.cierre?.run?.cierre_http ?? 'no abierto'}; rollback ${r.cierre?.rollback?.verificado ? 'verificado por API e historial' : 'NO VERIFICADO'}; historial de ${Object.keys(r.cierre?.rollback?.historial ?? {}).length} sensores; sesiones HTTP ${Object.values(r.cierre?.sesiones ?? {}).join(', ') || 'sin determinar'}.`,
    ...(opciones.marcadorOriginal && (opciones.marcadorOriginal.run_id !== r.run_id || opciones.marcadorOriginal.estado !== estadoMarcador(r.cierre))
      ? [`El marcador histórico run-pendiente.json conserva run_id ${limpiar(opciones.marcadorOriginal.run_id)} y estado ${limpiar(opciones.marcadorOriginal.estado)}. Su formato no coincide con el cierre y rollback verificados en resultado.json; se preserva intacto como evidencia histórica.`] : []),
    '', '## Conclusión y acciones', '',
    `${r.veredicto_grupo ?? 'Sin veredicto grupal'}; oficialidad ${r.oficial ? 'confirmada' : 'pendiente'}. ${afectados.map((id, i) => `Asignar a ${asignarAtencion(r, id).equipo} la atención inicial de REF-G87-${String(i + 1).padStart(2, '0')} (${id})`).join('; ') || 'Sin incidencias funcionales confirmadas'}. El equipo inicial debe confirmar el punto causal y proponer la corrección sin alterar los veredictos históricos. Nueva evaluación solo con autorización QA. Cierre RUN HTTP ${r.cierre?.run?.cierre_http ?? 'no abierto'}; rollback ${r.cierre?.rollback?.verificado ? 'verificado por API e historial' : 'NO VERIFICADO'}.`,
    '', '## Anexo técnico — mensajes originales de las herramientas', '',
    'Los mensajes siguientes se conservan para trazabilidad; los campos JSON se recortan a lo observado en la comprobación.');
  if (!fallos.length) L.push('Sin mensajes de fallos funcionales.');
  for (const x of fallos) L.push('', `### ${x.caso} ${x.id} (${x.fuente})`, '', '```text', String(x.obtenido ?? x.motivo ?? 'sin detalle').slice(0, 1200), '```');
  return L.join('\n') + '\n';
}
