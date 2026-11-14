import fs from 'node:fs';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';
import { createHash } from 'node:crypto';
import { AsyncLocalStorage } from 'node:async_hooks';
import os from 'node:os';
import { CASOS, IDS, CONTRATO, DIR, PRESUPUESTO, entrada, validarActor, idsNuevos,
  vigente, periodoDestino, seleccionarCandidatos, oraculo011, oraculo012, oraculo013, decidirVerificacion,
  validarDecimales, igual } from './lib/g37_core.mjs';

const require = createRequire(import.meta.url);
const COL = path.join(DIR, 'G37.postman_collection.json');
const RAIZ = path.resolve(DIR, '../../../../..');
const API = 'https://www.api.inmero.co/api-sgpmp-test';
const CONTRATO_ARCHIVO = path.join(DIR, 'pruebas', 'contrato_g37.json');
const PRECONDICION_IOT = path.join(DIR, 'pruebas', 'precondicion_iot.json');
const HUELLAS = {
  coleccion: '7328ca2bf779428203e0518556a86a24ec0cf33d7b5558c6ce10edb57c3753e3',
  contrato: '342643d3ab3f95a0ac79d5b6c38eee7df73fa242558e33178956fed9bad590fa'
};
const peticiones = new AsyncLocalStorage();
export async function fetchEnContexto(...args) {
  const control = peticiones.getStore();
  if (!control) return globalThis.fetch(...args);
  if (control.enCurso || control.newmanActivo) throw Error('PETICION_CONCURRENTE');
  control.enCurso++;
  try {
    const res = await control.fetcher(...args);
    const data = await res.json().catch(() => null);
    return { status: res.status, headers: res.headers, json: async () => data };
  }
  finally { control.enCurso--; }
}
export const conPeticiones = (fetcher, tarea) => peticiones.run({ fetcher, enCurso: 0, newmanActivo: false }, tarea);
export const CAPACIDADES = { contrato: 'sigab-qa-ejecutor/1', grupo: 'G37', casos: CASOS,
  operaciones: ['evaluar', 'reintentar', 'reevaluar'], versiones: { min: 1, max: 99 },
  comprobaciones_obligatorias: Object.fromEntries(CASOS.map((c, i) => [c, { API: [IDS[i]] }])),
  limite: { solicitudes_totales: 150, duracion_segundos: 1800, timeout_post_ms: 120000 },
  baja_automatizada: false };

const id = x => Number.isInteger(Number(x)) && Number(x) > 0 ? Number(x) : null;
const hoy = () => new Intl.DateTimeFormat('en-CA', { timeZone: 'America/Bogota', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date());
const texto = x => String(x ?? '').replace(/[\r\n|]/g, ' ').slice(0, 350);
const nombreInforme = v => v === 1 ? 'TC-M06-G37_resultado.md' : `TC-M06-G37_reevaluacion_V${v}.md`;
const guardar = (p, v) => fs.writeFileSync(p, JSON.stringify(v, null, 2), 'utf8');
function versionNewman() {
  try { return require(require.resolve('newman/package.json', { paths: [path.resolve(DIR, '../../../../..')] })).version; }
  catch { const p = path.join(path.dirname(process.execPath), 'node_modules', 'newman', 'package.json');
    return fs.existsSync(p) ? JSON.parse(fs.readFileSync(p, 'utf8')).version : null; }
}
export function leerEnv(proceso = process.env, archivo = path.join(RAIZ, '.env.qa')) {
  const env = {};
  // Sin autorización del proceso no se consulta ni siquiera el archivo real.
  if (proceso.QA_AUTORIZADO === 'SI' && fs.existsSync(archivo))
    for (const linea of fs.readFileSync(archivo, 'utf8').split(/\r?\n/)) {
      const m = linea.match(/^\s*([A-Z][A-Z0-9_]*)\s*=(.*)$/);
      if (m) env[m[1]] = m[2].trim().replace(/^(['"])(.*)\1$/, '$2');
    }
  Object.assign(env, proceso);
  env.QA_AUTORIZADO = proceso.QA_AUTORIZADO;
  return env;
}
export function preflight(c, env, newman = versionNewman()) {
  const barreras = ['SIGAB_API_TEST_BASE', 'QA_SANDBOX_SECRET', 'QA_CONTADOR_EMAIL',
    'QA_CONTADOR_PASSWORD', 'QA_ADMIN_EMAIL', 'QA_ADMIN_PASSWORD']
    .filter(k => !String(env[k] ?? '').trim());
  if (env.QA_AUTORIZADO !== 'SI') barreras.push('QA_AUTORIZADO');
  const base = String(env.SIGAB_API_TEST_BASE ?? '').replace(/\/+$/, '');
  if (c.ensayo ? !/^http:\/\/(127\.0\.0\.1|localhost):\d+$/.test(base) : base !== API)
    barreras.push('API_NO_CANONICA');
  if (!newman) barreras.push('NEWMAN_NO_DISPONIBLE');
  for (const [nombre, archivo, huella] of [
    ['COLECCION_SHA256', COL, HUELLAS.coleccion],
    ['CONTRATO_SHA256', CONTRATO_ARCHIVO, HUELLAS.contrato]]) {
    try {
      if (createHash('sha256').update(fs.readFileSync(archivo)).digest('hex') !== huella)
        barreras.push(nombre);
    } catch { barreras.push(nombre); }
  }
  let precondicion_iot_sha256 = null;
  try {
    const contenido = fs.readFileSync(c.ensayo && c.precondicionIoTArchivo || PRECONDICION_IOT);
    precondicion_iot_sha256 = createHash('sha256').update(contenido).digest('hex');
    validarPrecondicionIoT(JSON.parse(contenido.toString('utf8')));
  } catch (e) { barreras.push(`PRECONDICION_IOT: ${texto(e.message)}`); }
  return { grupo: 'G37', run_id: c.runId, ok: barreras.length === 0, fase: 'PREFLIGHT',
    barreras, precondicion_iot_sha256, presupuesto: PRESUPUESTO, herramientas: { node: process.version, newman },
    efectos_externos: [
      'Cada precio RF-89 vigente puede enviar fuera del sandbox un aviso ALERTA_FINANCIERA_NIC41 a la bandeja interna de cada Contador: hasta 2 avisos por Contador, con referencia a precios que DELETE revierte; se informa aparte y no altera la oficialidad.',
      'Los 2 logins y su auditoría son efectos persistentes previstos.',
      'La bitácora RF-52 de eventos M02 puede escribir en logs/audit_buffer_M02.jsonl del servidor TEST si falla o hay carga, fuera del rollback; puede existir bitácora de consulta M02.',
      'Procesar eventos M06 puede atender eventos pendientes ajenos dentro del sandbox. DELETE y lecturas poscierre verifican solo los datos del sandbox; no se esperan correos.'
    ] };
}
export function comprobar() {
  const faltan = ['g37.mjs', 'lib/g37_core.mjs', 'G37.postman_collection.json', 'pruebas/contrato_g37.json',
    'pruebas/g37_env.test.mjs', 'pruebas/g37_ensayo.mjs', 'pruebas/newman_hijo.mjs',
    'pruebas/precondicion_iot.json', 'README.md']
    .filter(p => !fs.existsSync(path.join(DIR, p)));
  const coleccion = fs.existsSync(COL) ? JSON.parse(fs.readFileSync(COL, 'utf8')) : { item: [] };
  const items = coleccion.item ?? [];
  const actores = items.every(x => { const p = entrada(x.name); return validarActor(p.id, p.actor) &&
    x.request.header.some(h => h.key === 'Authorization' && h.value === `Bearer {{${p.actor}_token}}`); });
  const marcas = fs.existsSync(path.join(DIR, 'Resultados')) && fs.readdirSync(path.join(DIR, 'Resultados')).some(x => x.endsWith('.md'));
  const ok = !faltan.length && items.length === 2 && actores && !marcas;
  console.log(JSON.stringify({ grupo: 'G37', ok, faltan, newman_local: versionNewman(), items: items.length,
    actores_correctos: actores, markdown_superior: !!marcas, presupuesto: PRESUPUESTO }));
  return ok ? 0 : 2;
}
export function contexto(argv, ensayo = false) {
  const valor = k => argv.includes(k) ? argv[argv.indexOf(k) + 1] : null;
  const operacion = valor('--operacion'), version = Number(valor('--version')), intento = Number(valor('--intento'));
  const runId = valor('--run-id'), referencia = valor('--autorizacion'), ruta = valor('--contexto');
  if (!CAPACIDADES.operaciones.includes(operacion) || !Number.isInteger(version) || version < 1 ||
    !Number.isInteger(intento) || intento < 1 || !referencia || !ruta ||
    !new RegExp(`^RUN-G37-V${version}-\\d{8}-\\d{6}$`).test(runId ?? '')) throw Error('Contexto de RUN incompleto');
  const directorio = ensayo ? path.join(path.dirname(path.resolve(ruta)), '') :
    path.join(DIR, ...(version === 1 ? ['Resultados', runId] : [`EvaluacionV${version}`, 'Resultados', runId]));
  const archivo = path.resolve(ruta);
  if (ensayo && (path.basename(directorio) !== runId ||
    !path.resolve(directorio).startsWith(path.resolve(os.tmpdir()) + path.sep))) throw Error('Ensayo fuera del directorio temporal');
  if (path.dirname(archivo) !== directorio || path.basename(archivo) !== 'contexto_operacion.json') throw Error('Contexto fuera del RUN');
  const c = JSON.parse(fs.readFileSync(archivo, 'utf8'));
  if (c.grupo !== 'G37' || c.run_id !== runId || c.version !== version || c.intento !== intento ||
    c.operacion !== operacion.toUpperCase() || c.referencia !== referencia ||
    JSON.stringify(c.casos) !== JSON.stringify(CASOS) ||
    (version > 1 && !(operacion === 'reevaluar' && c.version_anterior === version - 1 && c.alcance_reevaluacion ||
      operacion === 'reintentar' && (c.version_anterior === null || c.version_anterior === version - 1) &&
      typeof c.alcance_reevaluacion?.motivo === 'string' && c.alcance_reevaluacion.motivo.trim())) ||
    (version === 1 && operacion === 'reevaluar')) throw Error('Contexto incoherente');
  return { operacion, version, intento, runId, referencia, directorio };
}
export function esquema(v, profundidad = 0) {
  if (v === null) return 'null';
  if (Array.isArray(v)) {
    const items = profundidad < 10 ? v.map(x => esquema(x, profundidad + 1)) : [];
    return { tipo: 'array', longitud: v.length,
      items: [...new Map(items.map(x => [JSON.stringify(x), x])).values()] };
  }
  if (typeof v === 'object') return profundidad >= 10 ? 'object' :
    Object.fromEntries(Object.entries(v).map(([k, x]) => [k, esquema(x, profundidad + 1)]));
  return typeof v;
}
export function compararEsquema(id, observado, soloCamposEscenario = false) {
  const plantilla = entrada(id);
  const comparar = (esperado, real, ruta) => {
    if (typeof esperado === 'string') {
      const tipo = real?.tipo === 'array' ? 'array' : real && typeof real === 'object' ? 'object' : real;
      if (real === undefined || !(esperado.split('|').includes(tipo) ||
        esperado.split('|').includes('decimal') && tipo === 'string'))
        throw Error(`Esquema discordante: ${ruta}; esperado ${esperado}, llegó ${tipo ?? 'ausente'}`);
      return;
    }
    if (Array.isArray(esperado)) {
      if (real?.tipo !== 'array') throw Error(`Esquema discordante: ${ruta}; esperado array, llegó ${real ?? 'ausente'}`);
      for (const item of real.items ?? []) comparar(esperado[0], item, `${ruta}[]`);
      return;
    }
    if (!real || typeof real !== 'object' || real.tipo === 'array')
      throw Error(`Esquema discordante: ${ruta}; esperado object, llegó ${real?.tipo ?? real ?? 'ausente'}`);
    for (const [k, t] of Object.entries(esperado)) {
      if (!(k in real)) throw Error(`Esquema sin campo: ${ruta}.${k}; esperado ${typeof t === 'string' ? t : Array.isArray(t) ? 'array' : 'object'}, llegó ausente`);
      comparar(t, real[k], `${ruta}.${k}`);
    }
  };
  const campos = id === 'periodos' && soloCamposEscenario
    ? Object.fromEntries(['id_periodo_contable', 'numero_id_tributaria', 'fecha_inicio', 'fecha_fin', 'estado']
      .map(k => [k, plantilla.campos[k]])) : plantilla.campos;
  comparar(plantilla.tipo === 'array' ? [campos] : campos, observado, id);
  if (id === 'cadena' && observado.eslabones !== 'null')
    comparar(plantilla.subcampos_eslabones, observado.eslabones, 'cadena.eslabones');
  if (id === 'periodos' && !soloCamposEscenario) for (const item of observado.items ?? []) {
    const cierre = item.ultimo_cierre;
    if (cierre === 'null') continue;
    comparar(plantilla.subcampos_ultimo_cierre, cierre, 'periodos[].ultimo_cierre');
    const precios = cierre?.precios_congelados;
    for (const precio of precios?.items ?? [])
      comparar(plantilla.subcampos_precios_congelados[0], precio,
        'periodos[].ultimo_cierre.precios_congelados[]');
  }
  return true;
}
const CASOS_POR_RESPUESTA = {
  acumulado: [CASOS[0]], m03_historial: [CASOS[1]], cadena: [CASOS[1]], trazabilidad: [CASOS[1]],
};
export function contrastarRespuesta(r, idPeticion, actor, http, data, ruta = entrada(idPeticion).ruta) {
  const p = entrada(idPeticion), real = esquema(data);
  let motivo = null;
  try {
    if (idPeticion === 'periodos') {
      compararEsquema(idPeticion, real, true);
      try {
        compararEsquema(idPeticion, real);
        validarDecimales(idPeticion, data);
      } catch (e) {
        const observacion = { id: idPeticion, ruta: p.ruta, actor, http,
          resultado: 'observacion', motivo: e.message, esquema_real: real };
        r.contraste_contrato.push(observacion);
        (r.observaciones.contrato_periodos ??= []).push(e.message);
      }
    } else {
      compararEsquema(idPeticion, real);
      validarDecimales(idPeticion, data);
    }
    if (idPeticion === 'auditoria' || idPeticion === 'm03_historial') {
      const pagina = idPeticion === 'auditoria' ? data.pagina_actual : data.pagina;
      const tamano = idPeticion === 'auditoria' ? data.registros_por_pagina : data.por_pagina;
      const items = idPeticion === 'auditoria' ? data.eventos : data.items;
      const total = idPeticion === 'auditoria' ? data.total_registros : data.total;
      const url = new URL(ruta, 'https://contrato.local');
      const solicitada = Number(url.searchParams.get('pagina'));
      const pedido = Number(url.searchParams.get(idPeticion === 'auditoria' ? 'tamano' : 'por_pagina'));
      if (!Number.isInteger(pagina) || pagina !== solicitada || !Number.isInteger(tamano) ||
        tamano !== pedido || !Number.isInteger(total) || total < 0 || items.length > tamano ||
        (idPeticion === 'm03_historial' && (!Number.isInteger(data.paginas_totales) || data.paginas_totales < 1)))
        throw Error('Paginación distinta del contrato');
    }
  } catch (e) { motivo = e.message; }
  const registro = { id: idPeticion, ruta: p.ruta, actor, http,
    resultado: motivo ? 'discrepa' : 'coincide',
    ...(motivo ? { motivo, esquema_real: real } : {}) };
  r.contraste_contrato.push(registro);
  if (motivo) {
    r.discrepancias_contrato.push(registro);
    r.problemas_tecnicos.push(`Contrato ${idPeticion}: ${motivo}`);
  }
  return !motivo;
}
function motivoDiscrepanciaPrevia(registro) {
  const detalle = String(registro.motivo ?? 'sin diagnóstico');
  const m = detalle.match(/^Esquema (?:discordante|sin campo): (.+); esperado (.+), llegó (.+)$/);
  return m ? `Lectura previa ${registro.ruta}: campo ${m[1]} esperado ${m[2]}, recibido ${m[3]}; sin escrituras.` :
    `Lectura previa ${registro.ruta}: ${detalle}; sin escrituras.`;
}
export async function lecturasPrevias(q, pid, aid, fecha, r = null, fechaInicio = fecha, sensor = 1318) {
  const rutas = [
    ['acumulado', `/finanzas/periodos/${pid}/estado-resultados/acumulado`],
    ['auditoria', `/finanzas/auditoria?id_periodo_contable=${pid}&tipo_evento=VARIACION_REGISTRADA&formato=TECNICO&pagina=1&tamano=500`],
    ['m03_historial', `/iot/monitoreo/historial?fecha_inicio=${fechaInicio}&fecha_fin=${fecha}&sensor_id=${sensor}&pagina=1&por_pagina=100`],
    ['variaciones', `/finanzas/periodos/${pid}/variaciones`],
    ['mediciones', `/finanzas/periodos/${pid}/mediciones`],
    ['lineas', `/finanzas/lineas?id_periodo_contable=${pid}`],
    ['ficha', `/activos-biologicos/${aid}/ficha-integral`, 'admin'],
    ['eventos_get', `/activos-biologicos/${aid}/eventos`, 'admin'],
  ];
  const respuestas = {};
  const leer = async (peticion, ruta, actor = 'contador') => {
    const desde = r?.contraste_contrato.length ?? 0;
    const x = await q(peticion, ruta, actor);
    for (const registro of r?.contraste_contrato.slice(desde) ?? []) registro.fase = 'previa';
    if (x.http !== 200 && r && peticion !== 'acumulado') {
      const registro = { id: peticion, ruta, actor, http: x.http, codigo: x.codigo,
        fase: 'previa', resultado: 'discrepa', motivo: `respuesta no esperada en ${ruta} (HTTP ${x.http ?? 'sin respuesta'}, ${x.codigo ?? 'sin código'})` };
      r.contraste_contrato.push(registro);
      r.discrepancias_contrato.push(registro);
      r.problemas_tecnicos.push(`Contrato ${peticion}: ${registro.motivo}`);
    }
    if (peticion === 'acumulado' && x.http !== 200) { respuestas[peticion] = x; return x; }
    if (x.http !== 200 || x.esquema_valido === false || !x.eco) {
      const campo = x.http !== 200 ? 'HTTP' : x.esquema_valido === false ? 'esquema' : 'X-Test-Run-Id';
      const esperado = campo === 'HTTP' ? '200' : campo === 'esquema' ? 'contrato' : 'eco del RUN';
      const recibido = campo === 'HTTP' ? String(x.http ?? 'sin respuesta') : campo === 'esquema' ? 'discordante' : 'ausente o distinto';
      if (campo === 'HTTP') throw Error(`respuesta no esperada en ${ruta} (HTTP ${recibido}, ${x.codigo ?? 'sin código'}); sin escrituras`);
      if (campo === 'esquema') {
        const discrepancia = r?.discrepancias_contrato.findLast(x => x.id === peticion && x.resultado === 'discrepa');
        if (discrepancia) throw Error(motivoDiscrepanciaPrevia(discrepancia));
      }
      throw Error(`Lectura previa ${ruta}: campo ${campo} esperado ${esperado}, recibido ${recibido}; sin escrituras`);
    }
    respuestas[peticion] = x;
    if (r) {
      const items = Array.isArray(x.data) ? x.data :
        peticion === 'auditoria' ? x.data?.eventos : peticion === 'm03_historial' ? x.data?.items :
          peticion === 'eventos_get' ? x.data?.eventos : null;
      if (Array.isArray(items) && items.length === 0) r.contraste_contrato.push({ id: peticion,
        ruta: entrada(peticion).ruta, actor, http: 200, fase: 'previa', resultado: 'sin elementos para contrastar' });
    }
    return x;
  };
  for (const [peticion, ruta, actor] of rutas) await leer(peticion, ruta, actor);
  const linea = respuestas.lineas.data[0]?.id_linea_asiento_nic41;
  if (linea != null) await leer('cadena', `/finanzas/lineas/${linea}/cadena`);
  else { respuestas.cadena = null; r?.contraste_contrato.push({ id: 'cadena',
    ruta: entrada('cadena').ruta, actor: 'contador', http: null, fase: 'previa', resultado: 'sin elementos para contrastar' }); }
  return respuestas;
}
function resultado(c) {
  return { grupo: 'G37', run_id: c.runId, autorizacion_referencia: c.referencia, version: c.version,
    intento: c.intento, casos: {}, comprobaciones: [], solicitudes: [], evidencias: [], incidencias: [],
    problemas_tecnicos: [], contraste_contrato: [], discrepancias_contrato: [], observaciones: {},
    herramientas: { node: process.version, newman: null },
    efectos_persistentes_declarados: { tipo: 'ALERTA_FINANCIERA_NIC41', precios_registrados: 0,
      id_precio_mercado: [], alcance: 'Evento M01 y aviso interno por Contador; fuera del sandbox.',
      registros_sin_id: 0,
      bandeja_contador_qa: { estado: 'NO_VERIFICABLE', avisos_observados: null } },
    cypress: { total_pruebas: 0 }, cierre: { run: { cierre_http: null }, rollback: { verificado: false } },
    oficial: false, consume_version: false };
}
function registrar(r, caso, decision, datos = {}) {
  r.casos[caso] = { caso: `TC-M06-G37 / ${caso}`, estado: decision.estado, motivo: texto(decision.motivo), ...datos };
  r.comprobaciones.push({ caso, fuente: 'API', id: IDS[CASOS.indexOf(caso)], tipo: 'ASSERT',
    estado: decision.estado, motivo: texto(decision.motivo), evidencia: 'resultado.json' });
}
export function aplicarDiscrepancias(r) {
  const afectados = new Set(r.discrepancias_contrato.flatMap(x =>
    x.fase === 'previa' ? CASOS : CASOS_POR_RESPUESTA[x.id] ?? CASOS));
  for (const k of afectados) {
    const inesperada = r.discrepancias_contrato.find(x =>
      (CASOS_POR_RESPUESTA[x.id] ?? CASOS).includes(k) && String(x.motivo ?? '').startsWith('respuesta no esperada en '));
    const esquemaPrevio = r.discrepancias_contrato.find(x => x.fase === 'previa' &&
      /^Esquema (?:discordante|sin campo): /.test(String(x.motivo ?? '')));
    const otra = r.discrepancias_contrato.find(x => (CASOS_POR_RESPUESTA[x.id] ?? CASOS).includes(k));
    const motivo = inesperada?.motivo ?? (esquemaPrevio ? motivoDiscrepanciaPrevia(esquemaPrevio) :
      otra ? `Contraste ${otra.ruta}: ${otra.motivo ?? 'respuesta discordante'}.` :
        'Respuesta necesaria con esquema discordante; contraste técnico QA pendiente.');
    r.casos[k] = { ...(r.casos[k] ?? { caso: `TC-M06-G37 / ${k}` }), estado: 'NO_CONCLUYENTE', motivo };
    r.comprobaciones = r.comprobaciones.filter(x => x.caso !== k);
    r.comprobaciones.push({ caso: k, fuente: 'API', id: IDS[CASOS.indexOf(k)], tipo: 'ASSERT',
      estado: 'NO_CONCLUYENTE', motivo, evidencia: 'resultado.json' });
  }
  r.incidencias = r.incidencias.filter(x => !afectados.has(x.caso));
  return afectados;
}
function incidencia(r, caso, titulo, requisito, pasos, esperado, obtenido, apoyo, impacto, severidad = 'ALTA', existente = null) {
  r.incidencias.push({ id: existente ?? `INC-M06-G37-${String(r.incidencias.length + 1).padStart(2, '0')}`,
    caso, titulo, requisito, pasos, esperado, obtenido, apoyo_codigo: apoyo, impacto, severidad,
    clasificacion_v2: existente ? 'SEGUIMIENTO_V2' : 'NUEVA_EN_V2',
    justificacion_severidad: severidad === 'ALTA' ? 'Funcionalidad relevante sin alternativa pública comprobada.' : 'Impacto parcial en una integración.',
    equipo_inicial: 'Desarrollo', fundamento_equipo: 'Primera discrepancia observada en API pública de M06.',
    certeza: 'CONFIRMADA', causa_raiz: 'NO DETERMINADA', evidencias: ['resultado.json'] });
}
async function pedir(r, api, idPeticion, ruta, actor, tokens, c, body = undefined) {
  validarActor(idPeticion, actor);
  // Reservar 30 solicitudes para Newman, DELETE, bandeja y lecturas públicas poscierre.
  if (r.solicitudes.length >= PRESUPUESTO.solicitudes_totales - 30 || Date.now() > r._limite) throw Error('PRESUPUESTO_AGOTADO');
  const p = entrada(idPeticion);
  if (p.metodo === 'GET' && body !== undefined) throw Error('GET con cuerpo');
  const fila = { id: idPeticion, caso: null, metodo: p.metodo, ruta: ruta.split('?')[0], actor, http: null };
  r.solicitudes.push(fila);
  try {
    const res = await fetchEnContexto(api + ruta, { method: p.metodo, redirect: 'manual',
      headers: { Authorization: `Bearer ${tokens[actor]}`, 'X-Test-Run-Id': c.runId,
        'X-Sandbox-Secret': tokens.secreto, ...(body === undefined ? {} : { 'Content-Type': 'application/json' }) },
      body: body === undefined ? undefined : JSON.stringify(body), signal: AbortSignal.timeout(p.metodo === 'GET' ? 30000 : 120000) });
    const data = await res.json().catch(() => null);
    fila.http = res.status; fila.eco = res.headers.get('x-test-run-id') === c.runId;
    fila.codigo = res.status >= 400 ? texto(data?.error_code ?? data?.code ?? '') : null;
    const esperado = p.http ?? 200;
    if (res.status !== esperado) r.contraste_contrato.push({ id: idPeticion, ruta: p.ruta,
      actor, http: res.status, resultado: 'no_contrastable' });
    const valido = res.status !== esperado || contrastarRespuesta(r, idPeticion, actor, res.status, data, ruta);
    fila.contrato = res.status === esperado ? (valido ? 'coincide' : 'discrepa') : 'sin_cuerpo_esperado';
    const idNecesario = idPeticion === 'precios_post' ? id(data?.id_precio_mercado) :
      idPeticion === 'evento_crecimiento' ? id(data?.evento?.id_eventos) :
        idPeticion === 'estado_post' ? id(data?.id_estado) : null;
    return { http: res.status, data: valido ? data : null, id_necesario: idNecesario,
      eco: fila.eco, codigo: fila.codigo,
      esquema_valido: valido };
  } catch (e) { if (e.message === 'PETICION_CONCURRENTE') throw e;
    fila.fallo = e.name === 'TimeoutError' ? 'TIMEOUT' : 'SIN_RESPUESTA';
    return { http: null, data: null, eco: false, codigo: fila.fallo }; }
}
function bueno(x, http = 200) { return x.http === http && x.eco && x.esquema_valido !== false; }
export function verificarPermisos(data, actor) {
  const declarado = CONTRATO.lectura_permisos;
  if (declarado?.campos?.permisos?.[0]?.id_recurso !== 'number' ||
    declarado.campos.permisos[0].id_accion !== 'number' ||
    declarado.campos.permisos[0].nombre_recurso !== 'string|null' ||
    !declarado.actores.includes(actor)) throw Error('Contrato de permisos inválido');
  if (!data || !Array.isArray(data.permisos) || data.permisos.some(p =>
    !Number.isInteger(p.id_recurso) || !Number.isInteger(p.id_accion) ||
    !(typeof p.nombre_recurso === 'string' || p.nombre_recurso === null)))
    throw Error(`Esquema de permisos discordante para ${actor}`);
  for (const p of CONTRATO.peticiones.filter(x => x.actor === actor)) {
    const [recurso, accion] = p.permiso.split(':');
    if (!data.permisos.some(x => x.nombre_recurso === recurso && x.id_accion === Number(accion)))
      throw Error(`Permiso ausente ${actor}: ${recurso}:${accion} para ${p.id}`);
  }
  return true;
}
export function validarPrecondicionIoT(p, ahora = new Date()) {
  if (!Number.isInteger(p?.id_activo_biologico) || !Number.isInteger(p.id_dispositivo_iot) ||
      !Number.isInteger(p.id_telemetria_apta) || !Number.isInteger(p.id_sensor) ||
      !Number.isInteger(p.id_periodo_contable) || !Array.isArray(p.bovinos) ||
      p.bovinos.length !== 4 || new Set(p.bovinos).size !== 4 ||
      !p.bovinos.includes(p.id_activo_biologico) || !Number.isFinite(Date.parse(p.timestamp_lectura)))
    throw Error('Precondición IoT incompleta');
  return p;
}
export function leerPrecondicionIoT(archivo = PRECONDICION_IOT) {
  return validarPrecondicionIoT(JSON.parse(fs.readFileSync(archivo, 'utf8')));
}
function valores(x) { return Array.isArray(x?.data) ? x.data : null; }
async function auditoriaTodas(r, api, pid, tokens, c, primera = null) {
  let pagina = 1, total = Infinity; const salida = [];
  while (salida.length < total && pagina <= 10) {
    const ruta = `/finanzas/auditoria?id_periodo_contable=${pid}&tipo_evento=VARIACION_REGISTRADA&formato=TECNICO&pagina=${pagina}&tamano=500`;
    const x = primera ?? await pedir(r, api, 'auditoria', ruta, 'contador', tokens, c);
    primera = null;
    if (x.http !== 200) throw Error(`respuesta no esperada en ${ruta} (HTTP ${x.http ?? 'sin respuesta'}, ${x.codigo ?? 'sin código'})`);
    if (!bueno(x) || !Array.isArray(x.data?.eventos)) return null;
    total = Number(x.data.total_registros); salida.push(...x.data.eventos); pagina++;
    if (x.data.eventos.length === 0) break;
  }
  return salida.length === total ? salida : null;
}
function estadoNuevo(antes, despues, campo) { return idsNuevos(antes, despues, campo); }
async function newman(r, c, api, tokens, periodo, linea) {
  if (!id(linea)) { r.problemas_tecnicos.push('Newman omitido: no hay id_linea válido'); return; }
  const control = peticiones.getStore();
  if (control?.enCurso || control?.newmanActivo) throw Error('PETICION_CONCURRENTE');
  const col = JSON.parse(fs.readFileSync(COL, 'utf8'));
  const env = { values: Object.entries({ base_url: api, run_id: c.runId, sandbox_secret: tokens.secreto,
    contador_token: tokens.contador, admin_token: tokens.admin, periodo: String(periodo), linea: String(linea) })
    .map(([key, value]) => ({ key, value, enabled: true })) };
  const sub = path.join(c.directorio, 'newman'); fs.mkdirSync(sub, { recursive: true });
  if (control) control.newmanActivo = true;
  let out;
  try {
    out = await new Promise(resolve => {
      let hijo;
      try { hijo = spawn(process.execPath, [path.join(DIR, 'pruebas', 'newman_hijo.mjs')], {
        stdio: ['pipe', 'pipe', 'pipe'], timeout: 160000, windowsHide: true }); }
      catch (e) { resolve({ status: null, stdout: '', error: e }); return; }
      let stdout = '', error = null;
      hijo.stdout.setEncoding('utf8').on('data', chunk => {
        stdout += chunk;
        if (stdout.length > 1024 * 1024) { error = Error('SALIDA_NEWMAN_EXCESIVA'); hijo.kill(); }
      });
      hijo.stderr.resume();
      hijo.once('error', e => { error = e; });
      hijo.once('close', code => resolve({ status: code, stdout, error }));
      hijo.stdin.on('error', () => {});
      hijo.stdin.end(JSON.stringify({ coleccion: col, environment: env, timeout: 30000, salida: sub }));
    });
    if (c.ensayo && out.error?.code === 'EPERM') {
      const { ejecutarNewman } = await import('./pruebas/newman_hijo.mjs');
      const resumenLocal = await ejecutarNewman({ coleccion: col, environment: env, timeout: 30000, salida: sub });
      out = { status: resumenLocal.fallido ? 2 : 0,
        stdout: JSON.stringify(resumenLocal), error: null };
    }
  } finally { if (control) control.newmanActivo = false; }
  let resumen = {}; try { resumen = JSON.parse(out.stdout); } catch { resumen = { error: 'SALIDA_INVALIDA' }; }
  for (const s of resumen.solicitudes ?? []) if (s.contraste) {
    // El hijo ya aplicó compararEsquema al cuerpo original; solo cruza nombres y tipos.
    const registro = { ...s.contraste, fuente: 'Newman' };
    r.contraste_contrato.push(registro);
    if (registro.resultado === 'discrepa') {
      r.discrepancias_contrato.push(registro);
      r.problemas_tecnicos.push(`Contrato Newman ${s.nombre}: ${registro.motivo}`);
    }
  }
  r.herramientas.newman = { version: versionNewman(), iteraciones: resumen.solicitudes?.length === 2 ? 1 : 0,
    solicitudes: resumen.solicitudes?.length ?? 0,
    fallos: resumen.solicitudes?.flatMap(x => x.aserciones ?? []).filter(x => x.error).length ?? 2,
    codigo: out.status, error: out.error?.code ?? resumen.error ?? null };
  if (fs.existsSync(path.join(sub, 'newman-G37.json')) && fs.existsSync(path.join(sub, 'newman-G37.html')))
    r.evidencias.push('newman/newman-G37.json', 'newman/newman-G37.html');
  if (out.status !== 0) r.problemas_tecnicos.push('Newman no completó todas las lecturas; revisar reporte generado.');
}
export function informe(c, r) {
  const casos = CASOS.map(k => r.casos[k]);
  const agregado = casos.some(x => x.estado === 'RECHAZADO') ? 'RECHAZADO' :
    casos.every(x => x.estado === 'APROBADO') ? 'APROBADO' : 'NO_CONCLUYENTE';
  const decisiones = CASOS.map(k => `| ${k} | ${r.casos[k].estado} | ${texto(r.casos[k].motivo)} |`).join('\n');
  const a = r.observaciones?.acumulados ?? {};
  const suma = o => o ? `ingresos ${o.total_ingresos}, gastos ${o.total_gastos}; TB+ ${o.componentes?.ganancia_transformacion_biologica}, TB- ${o.componentes?.perdida_transformacion_biologica}, PM+ ${o.componentes?.ganancia_precio_mercado}, PM- ${o.componentes?.perdida_precio_mercado}` : 'sin lectura comparable';
  const variaciones = (r.observaciones?.variaciones ?? []).map(x =>
    `| ${x.id} | ${x.activo} | ${x.tipo} | ${x.monto} | ${x.linea} |`).join('\n');
  const cadena = r.observaciones?.cadena_013?.final;
  const eslabones = cadena?.eslabones;
  const detalles = {
    'TC-M06-011': `### TC-M06-011

**Qué se verifica.** El acumulado del período abierto cambia por componente y total exactamente con las variaciones del RUN; el de otro período abierto permanece igual.

**Preparación.** Período ${a.periodo ?? 'sin confirmar'} y control ${a.otro_periodo ?? 'sin confirmar'}; cuatro bovinos y precio vigente.

**Qué se hizo.** GET del acumulado antes y después de procesar, sin POST de RF-93 ni recálculo manual.

**Esperado.** Ganancias en ingresos; pérdidas en gastos por valor absoluto; otro período sin cambios.

**Observado.** Período antes: ${suma(a.antes)}. Después: ${suma(a.despues)}. Otro período antes: ${suma(a.otro_antes)}. Después: ${suma(a.otro_despues)}.

| Variación | Activo | Tipo | Monto | Línea |
|---|---:|---|---:|---:|
${variaciones || '| Sin variaciones acreditadas | | | | |'}

**Por qué se decide.** ${texto(r.casos['TC-M06-011'].motivo)} Estado: ${r.casos['TC-M06-011'].estado}.`,
    'TC-M06-013': `### TC-M06-013

**Qué se verifica.** La variación TB+ inicia VERIFICACION_PENDIENTE, RF-91 recibe la verificación y la cadena llega a VERIFICADO con navegación a M02 y M03.

**Preparación.** Bovino ${r.observaciones?.paso_1?.activo ?? 'sin confirmar'}; dispositivo 856; lectura 120035 apta dentro de la ventana de 24 h.

**Qué se hizo.** Se consultó la variación y la cadena inicial, se invocó POST RF-91 y se consultaron variación y cadena finales.

**Esperado.** HTTP 200 con verificadas y pendientes; VERIFICADO, evento M02 del paso y lectura M03 120035 en ids_lectura_iot.

**Observado.** Evento M02 ${r.observaciones?.paso_1?.evento ?? 'no observado'}; estado final ${cadena?.estado_verificacion ?? 'no observado'}; nivel_fallo ${cadena?.nivel_fallo ?? eslabones?.nivel_fallo ?? 'sin dato'}; evento en cadena ${eslabones?.ids?.id_evento ?? 'faltante'}; lecturas en cadena ${(eslabones?.ids?.ids_lectura_iot ?? []).join(', ') || 'ninguna'}; verificadas RF-91 ${r.observaciones?.cadena_013?.respuesta_rf91?.verificadas ?? 'sin respuesta'}.

**Por qué se decide.** ${texto(r.casos['TC-M06-013'].motivo)} Estado: ${r.casos['TC-M06-013'].estado}.`
  };
  const comprobaciones = r.comprobaciones.map(x =>
    `| ${x.id} | ${x.caso} | ${x.estado} | ${texto(x.motivo)} | ${x.evidencia} |`).join('\n');
  const incidencias = r.incidencias.length ? r.incidencias.map(x =>
    `### ${x.id}: ${x.titulo}

Caso ${x.caso}. Requisito: ${x.requisito}. Pasos: ${x.pasos}. Esperado: ${x.esperado}. Observado: ${x.obtenido}. Impacto: ${x.impacto}. Severidad ${x.severidad}: ${x.justificacion_severidad}. Primer contacto: ${x.equipo_inicial}, por ${x.fundamento_equipo}. Certeza ${x.certeza}; causa raíz ${x.causa_raiz}. Evidencia: ${x.evidencias.join(', ')}.`).join('\n\n') : 'Sin incidencia de producto nueva comprobada.';
  const fallasOficialidad = Object.entries(r.condiciones_oficialidad ?? {}).filter(([, ok]) => !ok).map(([k]) => k);
  const abortoContratoPrevio = r.discrepancias_contrato.some(x => x.fase === 'previa');
  return `# TC-M06-G37 — ${agregado}

## Identificación

Casos V2: ${CASOS.join(', ')}. TC-M06-012: APROBADO en V1, RUN-G37-V1-20261108-233956; fuera de V2. RF-86, versión ${c.version}, intento ${c.intento}, RUN ${c.runId}. Ambiente TEST. Autorización ${c.referencia}. Commit de backend indicado para la reevaluación: 453277e4; no verificado por el ejecutor. Node ${process.version}; Newman ${r.herramientas.newman?.version ?? 'no ejecutado'}.

## Precondiciones preparadas

Con autorización del responsable QA se vinculó por SQL el dispositivo 856 al bovino 1831 porque no hay API. Se insertó por SQL la lectura 120035 con apto_para_nic41=true; telemetria_calidad figura INDETERMINADA. Se aceptó la desviación TEMP_CORPORAL frente al pesaje IoT de la matriz porque el producto no ofrece variable de peso. Son precondiciones persistentes fuera del rollback del RUN; el preflight vivo comprueba dispositivo y ventana antes de escribir.

## Resumen de veredictos

| Caso | Estado | Motivo |
|---|---|---|
${decisiones}

## Detalle por caso

${detalles['TC-M06-011']}

${detalles['TC-M06-013']}

## Comprobaciones API/UI

| ID | Caso | Estado | Observación | Evidencia |
|---|---|---|---|---|
${comprobaciones}

UI no exigida por estos casos de la matriz.

## Evidencias reales

${r.evidencias.join(', ') || 'Sin evidencias completas'}. Los montos, cuatro acumulados y la cadena completa están en resultado.json. Solicitudes del ejecutor y Newman: ${r.solicitudes_totales ?? 'sin conteo'} / ${PRESUPUESTO.solicitudes_totales}.

## Seguimiento e incidencias

INC-M06-G37-01: ${r.seguimiento?.['INC-M06-G37-01'] ?? 'NO_CONCLUYENTE'}. INC-M06-G32-01: ${r.seguimiento?.['INC-M06-G32-01'] ?? 'NO_CONCLUYENTE'}. Cualquier otra discrepancia acreditada en V2 se registra como nueva en V2.

${incidencias}

## Análisis de causas y problemas técnicos

La derivación inicial usa la primera respuesta pública discrepante. Causa raíz solo donde exista evidencia independiente. Problemas internos de automatización o datos: ${r.problemas_tecnicos.map(texto).join('; ') || 'ninguno observado'}. ${abortoContratoPrevio ? 'El preflight abortó por contrato: Problema técnico de automatización (ERROR_QA), no incidencia del producto; el contraste impidió comprobar los oráculos.' : ''}

## Conclusión y acciones

${CASOS.map(k => `${k}: ${r.casos[k].estado}`).join('; ')}. ${r.oficial ? 'Ejecución oficial.' : `No oficial: fallan ${fallasOficialidad.join(', ') || 'condiciones no determinadas'}.`} Desarrollo revisará las incidencias reproducidas; QA decidirá la siguiente evaluación con nueva autorización.

## Cierre y rollback

DELETE del RUN HTTP ${r.cierre.run.cierre_http ?? 'no observado'}. Rollback ${r.cierre.rollback.verificado ? 'verificado' : 'no verificado'}: ${r.cierre.rollback.motivo ?? 'sin comprobación suficiente'}. Lecturas poscierre sin cabeceras del RUN: ${r.cierre.lecturas_poscierre?.length ?? 0}. La lectura M03 y el vínculo del dispositivo persisten como precondiciones.
`;
}
async function login(api, correo, clave) {
  const res = await fetchEnContexto(api + '/sesiones/', { method: 'POST', redirect: 'manual',
    headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ correo_electronico: correo, contrasena: clave }),
    signal: AbortSignal.timeout(120000) });
  const b = await res.json().catch(() => null);
  return res.status === 200 ? b?.token ?? null : null;
}
async function bandejaContador(api, token) {
  try {
    const res = await fetchEnContexto(api + '/notificaciones?pagina=1&tamano=50', { method: 'GET',
      headers: { Authorization: `Bearer ${token}` }, signal: AbortSignal.timeout(30000) });
    const b = await res.json().catch(() => null);
    return res.status === 200 && Array.isArray(b?.items) ? b.items : null;
  } catch (e) { if (e.message === 'PETICION_CONCURRENTE') throw e; return null; }
}
export function evaluarRollbackSandbox({ deleteHttp, lecturasCompletas, registrosPresentes = [], inciertas, conciliadas, escrituras = true }) {
  const fallos = [...registrosPresentes];
  const sinEscrituras = !escrituras && !inciertas;
  return { verificado: deleteHttp === 200 && (sinEscrituras || lecturasCompletas && !fallos.length && !inciertas && conciliadas),
    motivo: deleteHttp !== 200 ? `DELETE HTTP ${deleteHttp ?? 'sin respuesta'}; rollback no comprobado.` :
      sinEscrituras ? 'Sin POST/PATCH: DELETE 200 verifica datos del sandbox; lecturas poscierre ejecutadas registradas.' :
      !lecturasCompletas ? 'No se completaron lecturas poscierre.' :
        fallos.length ? `Persisten registros del RUN: ${fallos.join(', ')}` :
          inciertas || !conciliadas ? 'Hay escrituras sin respuesta o registros del RUN sin conciliar.' :
            'IDs del RUN ausentes y estado M02 restaurado en lecturas públicas poscierre.' };
}
async function cierre(r, c, api, tokens, hechos) {
  if (!hechos.iniciado) return;
  try {
    const res = await fetchEnContexto(api + `/test-control/runs/${encodeURIComponent(c.runId)}`, { method: 'DELETE',
      headers: { Authorization: `Bearer ${tokens.contador}`, 'X-Sandbox-Secret': tokens.secreto,
        'X-Test-Run-Id': c.runId }, signal: AbortSignal.timeout(30000) });
    r.cierre.run.cierre_http = res.status;
    if (res.status !== 200) { r.cierre.rollback = evaluarRollbackSandbox({ deleteHttp: res.status,
      lecturasCompletas: false, registrosPresentes: [], inciertas: hechos.inciertas, conciliadas: hechos.conciliadas }); return; }
    const huboEscrituras = r.solicitudes.some(x => ['POST', 'PATCH'].includes(x.metodo));
    if (!huboEscrituras && !hechos.inciertas && !hechos.periodo) {
      r.cierre.rollback = evaluarRollbackSandbox({ deleteHttp: res.status, escrituras: false,
        lecturasCompletas: false, inciertas: false, conciliadas: true });
      r.cierre.lecturas_poscierre = [];
      return;
    }
    const lecturas = [
      ['variaciones', '/finanzas/periodos/' + hechos.periodo + '/variaciones', 'contador', 'id_variacion_valor_razonable', hechos.variaciones],
      ['lineas', '/finanzas/lineas?id_periodo_contable=' + hechos.periodo, 'contador', 'id_linea_asiento_nic41', hechos.lineas],
      ['mediciones', '/finanzas/periodos/' + hechos.periodo + '/mediciones', 'contador', 'id_medicion_posterior', hechos.mediciones],
    ];
    const fallos = []; let lecturasCompletas = true;
    r.cierre.lecturas_poscierre = [];
    for (const [peticion, ruta, actor, campo, ids] of lecturas) {
      const res = await fetchEnContexto(api + ruta, { method: 'GET', headers: { Authorization: `Bearer ${tokens[actor]}` },
        signal: AbortSignal.timeout(30000) });
      const b = await res.json().catch(() => null);
      r.cierre.lecturas_poscierre.push({ ruta, http: res.status });
      if (res.status !== 200 || !contrastarRespuesta(r, peticion, actor, res.status, b, ruta)) {
        lecturasCompletas = false; fallos.push(ruta.split('?')[0]); }
      else if (b.some(x => ids.includes(Number(x[campo])))) fallos.push(ruta.split('?')[0]);
    }
    for (const e of hechos.eventos) {
      validarActor('eventos_get', 'admin');
      const res = await fetchEnContexto(api + `/activos-biologicos/${e.activo}/eventos`, { method: 'GET',
        headers: { Authorization: `Bearer ${tokens.admin}` }, signal: AbortSignal.timeout(30000) });
      const b = await res.json().catch(() => null);
      r.cierre.lecturas_poscierre.push({ ruta: `/activos-biologicos/${e.activo}/eventos`, http: res.status });
      if (res.status !== 200 || !contrastarRespuesta(r, 'eventos_get', 'admin', res.status, b)) {
        lecturasCompletas = false; fallos.push('evento M02'); }
      else if (b.eventos.some(x => Number(x.id_eventos) === e.id)) fallos.push('evento M02');
    }
    for (const precio of hechos.precios) {
      const res = await fetchEnContexto(api + `/finanzas/precios?id_especie=${precio.especie}`, { method: 'GET',
        headers: { Authorization: `Bearer ${tokens.contador}` }, signal: AbortSignal.timeout(30000) });
      const b = await res.json().catch(() => null);
      r.cierre.lecturas_poscierre.push({ ruta: `/finanzas/precios?id_especie=${precio.especie}`, http: res.status });
      if (res.status !== 200 || !contrastarRespuesta(r, 'precios_get', 'contador', res.status, b)) {
        lecturasCompletas = false; fallos.push('precio RF-89'); }
      else if (b.some(x => Number(x.id_precio_mercado) === precio.id)) fallos.push('precio RF-89');
    }
    let pagina = 1, total = Infinity; const auditorias = [];
    while (auditorias.length < total && pagina <= 10) {
      const res = await fetchEnContexto(api + `/finanzas/auditoria?id_periodo_contable=${hechos.periodo}&tipo_evento=VARIACION_REGISTRADA&formato=TECNICO&pagina=${pagina}&tamano=500`,
        { method: 'GET', headers: { Authorization: `Bearer ${tokens.contador}` }, signal: AbortSignal.timeout(30000) });
      const b = await res.json().catch(() => null);
      r.cierre.lecturas_poscierre.push({ ruta: `/finanzas/auditoria?id_periodo_contable=${hechos.periodo}&pagina=${pagina}`, http: res.status });
      if (res.status !== 200 || !contrastarRespuesta(r, 'auditoria', 'contador', res.status, b,
        `/finanzas/auditoria?id_periodo_contable=${hechos.periodo}&tipo_evento=VARIACION_REGISTRADA&formato=TECNICO&pagina=${pagina}&tamano=500`) ||
        !Number.isInteger(b.total_registros) || b.total_registros < 0) {
        lecturasCompletas = false; fallos.push('auditoría RF-94: lectura incompleta'); break;
      }
      total = Number(b.total_registros); auditorias.push(...b.eventos); pagina++;
      if (!b.eventos.length) break;
    }
    if (auditorias.length !== total) { lecturasCompletas = false; fallos.push('auditoría RF-94: paginación incompleta'); }
    if (auditorias.some(x => hechos.auditorias.includes(Number(x.id_evento)))) fallos.push('auditoría RF-94');
    for (const activo of hechos.estadosActivos) {
      const res = await fetchEnContexto(api + `/activos-biologicos/${activo.id}/ficha-integral`, { method: 'GET',
        headers: { Authorization: `Bearer ${tokens.admin}` }, signal: AbortSignal.timeout(30000) });
      const b = await res.json().catch(() => null);
      r.cierre.lecturas_poscierre.push({ ruta: `/activos-biologicos/${activo.id}/ficha-integral`, http: res.status });
      if (res.status !== 200 || !contrastarRespuesta(r, 'ficha', 'admin', res.status, b)) {
        lecturasCompletas = false; fallos.push('estado M02: lectura incompleta');
      } else if (b.estado_actual !== activo.estado) fallos.push('estado M02');
    }
    const periodoCierre = await fetchEnContexto(api + '/finanzas/periodos', { method: 'GET',
      headers: { Authorization: `Bearer ${tokens.contador}` }, signal: AbortSignal.timeout(30000) });
    const periodosCierre = await periodoCierre.json().catch(() => null);
    r.cierre.lecturas_poscierre.push({ ruta: '/finanzas/periodos', http: periodoCierre.status });
    if (periodoCierre.status !== 200 || !Array.isArray(periodosCierre) ||
        !contrastarRespuesta(r, 'periodos', 'contador', periodoCierre.status, periodosCierre) ||
        periodosCierre.find(x => Number(x.id_periodo_contable) === 241)?.estado !== 'ABIERTO') {
      lecturasCompletas = false; fallos.push('período 241 ABIERTO');
    }
    for (const activo of hechos.activosIniciales ?? []) {
      const ruta = `/activos-biologicos/${activo.id}/ficha-integral`;
      const respuesta = await fetchEnContexto(api + ruta, { method: 'GET',
        headers: { Authorization: `Bearer ${tokens.admin}` }, signal: AbortSignal.timeout(30000) });
      const ficha = await respuesta.json().catch(() => null);
      r.cierre.lecturas_poscierre.push({ ruta, http: respuesta.status });
      if (respuesta.status !== 200 || !contrastarRespuesta(r, 'ficha', 'admin', respuesta.status, ficha) ||
          ficha.estado_actual !== activo.estado || !igual(ficha.peso_actual, activo.peso)) {
        lecturasCompletas = false; fallos.push(`activo ${activo.id} estado/peso`);
      }
    }
    r.cierre.rollback = evaluarRollbackSandbox({ deleteHttp: res.status, lecturasCompletas,
      registrosPresentes: fallos, inciertas: hechos.inciertas, conciliadas: hechos.conciliadas,
      escrituras: huboEscrituras });
    const efecto = r.efectos_persistentes_declarados;
    if (hechos.bandejaInicial) {
      const posterior = await bandejaContador(api, tokens.contador);
      const ultimo = Math.max(0, ...hechos.bandejaInicial.map(x => id(x.id_notificacion) ?? 0));
      if (posterior && (posterior.some(x => id(x.id_notificacion) === ultimo) || (ultimo === 0 && posterior.length < 50)))
        efecto.bandeja_contador_qa = { estado: 'OBSERVADO',
          avisos_observados: posterior.filter(x => id(x.id_notificacion) > ultimo &&
            String(x.mensaje ?? '').startsWith('Hay un nuevo precio de mercado vigente.')).length };
    }
  } catch (e) { r.problemas_tecnicos.push(`Cierre: ${texto(e.message)}`);
    r.cierre.rollback = { verificado: false, motivo: 'No se completaron lecturas poscierre.' }; }
}
export async function evaluar(c, env) {
  if (env.QA_AUTORIZADO !== 'SI' || !fs.existsSync(c.directorio)) throw Error('RUN no autorizado o no preparado por el lanzador');
  if (c.ensayo ? !/^http:\/\/(127\.0\.0\.1|localhost):\d+$/.test(String(env.SIGAB_API_TEST_BASE ?? '').replace(/\/+$/, '')) :
    String(env.SIGAB_API_TEST_BASE ?? '').replace(/\/+$/, '') !== API) throw Error('Base no canónica');
  const r = resultado(c), api = c.ensayo ? String(env.SIGAB_API_TEST_BASE).replace(/\/+$/, '') : API;
  r._limite = Date.now() + 1800000;
  const hechos = { iniciado: false, periodo: null, eventos: [], precios: [], variaciones: [], lineas: [],
    estados: [], mediciones: [], auditorias: [], estadosActivos: [], inciertas: false, conciliadas: false,
    bandejaInicial: null, activosIniciales: [] };
  let tokens = null;
  try {
    if (!versionNewman()) throw Error('NEWMAN_NO_DISPONIBLE');
    const contador = await login(api, env.QA_CONTADOR_EMAIL, env.QA_CONTADOR_PASSWORD);
    const admin = await login(api, env.QA_ADMIN_EMAIL, env.QA_ADMIN_PASSWORD);
    if (!contador || !admin) throw Error('Fallo de login fuera del RUN');
    tokens = { contador, admin, secreto: env.QA_SANDBOX_SECRET };
    if (!tokens.secreto) throw Error('Falta secreto sandbox');
    hechos.iniciado = true;
    for (const actor of ['contador', 'admin']) {
      const rutaPermisos = CONTRATO.lectura_permisos.ruta;
      const fila = { id: 'permisos', metodo: 'GET', ruta: rutaPermisos, actor, http: null };
      r.solicitudes.push(fila);
      let res, data;
      try {
        res = await fetchEnContexto(`${api}${rutaPermisos}`, { method: 'GET', redirect: 'manual',
          headers: { Authorization: `Bearer ${tokens[actor]}`, 'X-Test-Run-Id': c.runId,
            'X-Sandbox-Secret': tokens.secreto }, signal: AbortSignal.timeout(30000) });
        data = await res.json().catch(() => null); fila.http = res.status;
        fila.eco = res.headers.get('x-test-run-id') === c.runId;
      } catch { throw Error(`Permisos ${actor}: sin respuesta`); }
      if (fila.http !== CONTRATO.lectura_permisos.http || !fila.eco)
        throw Error(`Permisos ${actor}: HTTP ${fila.http}, eco ${fila.eco}`);
      verificarPermisos(data, actor);
      r.contraste_contrato.push({ id: 'permisos', actor, ruta: rutaPermisos, http: 200, resultado: 'coincide' });
    }
    hechos.bandejaInicial = await bandejaContador(api, tokens.contador);
    const q = async (peticion, ruta, actor = 'contador', body) => {
      const x = await pedir(r, api, peticion, ruta, actor, tokens, c, body);
      if (x.http == null && ['POST', 'PATCH'].includes(entrada(peticion).metodo)) hechos.inciertas = true;
      return x;
    };
    const a = await q('activos', '/finanzas/activos');
    const p = await q('periodos', '/finanzas/periodos');
    hechos.iniciado = true;
    for (const [x, ruta] of [[a, '/finanzas/activos'], [p, '/finanzas/periodos']])
      if (!bueno(x) || !valores(x)) throw Error(`respuesta no esperada en ${ruta} (HTTP ${x.http ?? 'sin respuesta'}, ${x.codigo ?? 'sin código'})`);
    const candidatos = a.data;
    const precondicion = leerPrecondicionIoT(c.precondicionIoTArchivo);
    let bloqueoIoT = null;
    if (Date.now() >= Date.parse(precondicion.timestamp_lectura) + 86400000) {
      registrar(r, 'TC-M06-013', { estado: 'NO_CONCLUYENTE', motivo: 'Ventana de 24 h de la lectura M03 vencida; sin escrituras.' });
      throw Error('Ventana de 24 h de M03 vencida; sin escrituras');
    }
    const precios = new Map(), preparados = [];
    for (const especie of [...new Set(candidatos.map(x => x.id_especie))]) {
      const ruta = `/finanzas/precios?id_especie=${especie}`;
      const px = await q('precios_get', ruta);
      if (!bueno(px) || !valores(px)) throw Error(`respuesta no esperada en ${ruta} (HTTP ${px.http ?? 'sin respuesta'}, ${px.codigo ?? 'sin código'})`);
      precios.set(especie, px.data);
    }
    for (const x of candidatos.filter(x => precondicion.bovinos.includes(Number(x.id_activo_biologico)))) {
      if (r.solicitudes.length > 75) throw Error('Presupuesto de selección agotado antes de revisar todo el catálogo');
      if (!/bovin/i.test(x.especie ?? '') || x.tipo !== 'INDIVIDUAL' || x.estado !== 'ACTIVO' || x.valorado_por_costo) {
        preparados.push({ ...x, periodo: null, precio: null, calculo: null, peso: null });
        continue;
      }
      const aid = id(x.id_activo_biologico);
      const rutaDetalle = `/finanzas/activos/${aid}`;
      const d = await q('activo_detalle', rutaDetalle);
      if (!bueno(d)) { r.observaciones.candidatos = seleccionarCandidatos(preparados).motivos
        .concat({ activo: aid, motivos: [`detalle no legible: HTTP ${d.http ?? 'sin respuesta'}`] });
        throw Error(`respuesta no esperada en ${rutaDetalle} (HTTP ${d.http ?? 'sin respuesta'}, ${d.codigo ?? 'sin código'})`); }
      const rutaFicha = `/activos-biologicos/${aid}/ficha-integral`;
      const f = await q('ficha', rutaFicha, 'admin');
      if (!bueno(f)) { r.observaciones.candidatos = seleccionarCandidatos(preparados).motivos
        .concat({ activo: aid, motivos: [`ficha no legible: HTTP ${f.http ?? 'sin respuesta'}`] });
        throw Error(`respuesta no esperada en ${rutaFicha} (HTTP ${f.http ?? 'sin respuesta'}, ${f.codigo ?? 'sin código'})`); }
      const calculo = bueno(d) ? (d.data?.calculos ?? []).filter(z => z.estado === 'CALCULADO' && z.json_metodo_costo?.es_producto !== true)
        .sort((u, v) => String(v.fecha_calculo).localeCompare(String(u.fecha_calculo)))[0] : null;
      const diaHecho = hoy();
      preparados.push({ ...x, periodo: periodoDestino(p.data, d.data?.activo?.numero_id_tributaria, diaHecho),
        precio: vigente(precios.get(x.id_especie) ?? [], x.id_especie, diaHecho), calculo,
        peso: f.data?.unidad_peso === 'kg' ? Number(f.data.peso_actual) : null,
        dispositivo: d.data?.activo?.id_dispositivo_iot ?? null });
    }
    let seleccion = seleccionarCandidatos(preparados, 4, precondicion);
    if (Number(seleccion.elegido[0]?.id_activo_biologico) !== precondicion.id_activo_biologico ||
      Number(seleccion.elegido[0]?.dispositivo) !== precondicion.id_dispositivo_iot ||
      seleccion.elegido.some(x => Number(x.periodo?.id_periodo_contable) !== precondicion.id_periodo_contable)) {
      registrar(r, 'TC-M06-013', { estado: 'NO_CONCLUYENTE',
        motivo: '1831 sin dispositivo 856, período 241 abierto actual o cuatro bovinos aptos; sin escrituras.' });
      throw Error('Preflight vivo de 1831 y período 241 incumplido; sin escrituras');
    }
    r.observaciones.candidatos = seleccion.motivos;
    hechos.activosIniciales = seleccion.elegido.map(x => ({ id: id(x.id_activo_biologico), estado: x.estado, peso: x.peso }));
    const primerPeriodo = seleccion.elegido[0]?.periodo?.id_periodo_contable;
    let elegidos = seleccion.elegido;
    if (elegidos.length < 4) {
      r.impedimento_datos = 'No hay cuatro bovinos individuales del mismo período ABIERTO con reconocimiento, peso, precio y cálculo previo';
      throw Error(r.impedimento_datos); }
    const pid = id(primerPeriodo); hechos.periodo = pid;
    if (r.discrepancias_contrato.length) throw Error('Selección: esquema discordante; sin escrituras');
    const previas = await lecturasPrevias(q, pid, id(elegidos[0].id_activo_biologico),
      hoy(), r, precondicion.timestamp_lectura.slice(0, 10), precondicion.id_sensor);
    const historial = previas.m03_historial?.data;
    if (!Array.isArray(historial?.items) || !historial.items.some(x =>
      Number(x.id_telemetria) === precondicion.id_telemetria_apta)) {
      registrar(r, 'TC-M06-013', { estado: 'NO_CONCLUYENTE',
        motivo: `La lectura M03 ${precondicion.id_telemetria_apta} no está en historial público del sensor; sin escrituras.` });
      throw Error('Preflight M03 sin lectura esperada; sin escrituras');
    }
    const otra = p.data.find(x => Number(x.id_periodo_contable) !== pid && x.estado === 'ABIERTO');
    if (!otra) throw Error('No hay otro período ABIERTO comparable sin actividad del RUN');
    const otroId = id(otra.id_periodo_contable);
    const otroAntes = await q('acumulado', `/finanzas/periodos/${otroId}/estado-resultados/acumulado`);

    r.observaciones.m03 = `Lectura ${precondicion.id_telemetria_apta} y dispositivo ${precondicion.id_dispositivo_iot} preparados; aptitud NIC41 se comprobar? por cadena RF-91.`;
    const { acumulado: acumuladoAntes, auditoria: auPrevia, m03_historial: m03Base,
      variaciones: v0, lineas: l0, mediciones: m0 } = previas;
    if (r.discrepancias_contrato.length) throw Error('Lecturas previas: esquema discordante; sin escrituras');
    const au0 = await auditoriaTodas(r, api, pid, tokens, c, auPrevia);
    if (r.discrepancias_contrato.length) throw Error('Auditoría previa: esquema discordante; sin escrituras');
    if (![v0, l0, m0].every(x => bueno(x)) || [v0, l0, m0].some(x => !Array.isArray(x.data)) || !au0)
      throw Error('Línea base del período incompleta');
    r.observaciones.periodo_destino = pid;

    r.observaciones.linea_base = { variaciones: v0.data.map(x => x.id_variacion_valor_razonable),
      lineas: l0.data.map(x => x.id_linea_asiento_nic41),
      mediciones: m0.data.map(x => x.id_medicion_posterior), auditorias: au0.map(x => x.id_evento) };
    for (const registro of r.contraste_contrato) registro.fase ??= 'previa';
    r.observaciones.acumulados = { periodo: pid, otro_periodo: otroId,
      antes: acumuladoAntes.data, otro_antes: otroAntes.data };
    const nuevas = [];
    let ultimoPostVariaciones = null;
    for (let i = 0; i < 4; i++) {
      ultimoPostVariaciones = null;
      const s = elegidos[i];
      if (!s) continue;
      const aid = id(s.id_activo_biologico);
      const paso = r.observaciones[`paso_${i + 1}`] = { activo: aid, estado: 'INCOMPLETO' };
      let previo = s.calculo;
      if (i < 2 && id(previo.id_precio_mercado) !== id(s.precio.id_precio_mercado)) {
        const re = await q('evento_crecimiento', `/activos-biologicos/${aid}/eventos/crecimiento`, 'admin',
          { tipo_medicion: 'PESO', valor_medicion: s.peso, unidad_medida: 'kg', descripcion: `Rebase QA ${c.runId}`,
             });
        if (!bueno(re, 201) || !id(re.data?.evento?.id_eventos)) {
          hechos.inciertas ||= re.http == null || (re.http === 201 && !re.id_necesario); paso.motivo = 'Rebase M02 sin confirmación'; continue; }
        hechos.eventos.push({ id: id(re.data.evento.id_eventos), activo: aid });
        const pr = await q('procesar', '/finanzas/eventos/procesar', 'contador', {});
        if (!bueno(pr)) { hechos.inciertas ||= pr.http == null; paso.motivo = 'Procesamiento de rebase incompleto'; continue; }
        const de = await q('activo_detalle', `/finanzas/activos/${aid}`);
        previo = de.data?.calculos?.find(x => x.estado === 'CALCULADO' && id(x.id_precio_mercado) === id(s.precio.id_precio_mercado));
        if (!previo) { paso.motivo = 'No apareció el cálculo de rebase'; continue; }
      }
      const base = await q('variaciones', `/finanzas/periodos/${pid}/variaciones`);
      if (!bueno(base) || !valores(base)) { paso.motivo = 'Línea base de variaciones no disponible'; continue; }
      let precio = s.precio;
      if (i >= 2) {
        if (precio.fuente !== 'MERCADO_ACTIVO') { paso.motivo = 'Fuente de precio no apta'; continue; }
        const pp = await q('precios_post', '/finanzas/precios', 'contador', { id_especie: id(s.id_especie),
          categoria: 'PESO_KG', precio_unitario: Number((Number(precio.precio_unitario) * (i === 2 ? 0.95 : 1.05)).toFixed(2)),
          fecha_vigencia: hoy(), fuente: 'MERCADO_ACTIVO', evidencia_documental: `QA ${c.runId}`,
          confirmar_desviacion: true });
        if (!bueno(pp, 201) || !id(pp.data?.id_precio_mercado)) {
          hechos.inciertas ||= pp.http == null || (pp.http === 201 && !pp.id_necesario);
          if (pp.http == null || (pp.http === 201 && !pp.id_necesario)) r.efectos_persistentes_declarados.registros_sin_id++;
          paso.motivo = 'Precio nuevo no confirmado'; continue;
        }
        hechos.precios.push({ id: id(pp.data.id_precio_mercado), especie: id(s.id_especie) });
        r.efectos_persistentes_declarados.precios_registrados = hechos.precios.length;
        r.efectos_persistentes_declarados.id_precio_mercado = hechos.precios.map(x => x.id);
        precio = { ...precio, id_precio_mercado: pp.data.id_precio_mercado };
      }
      const pesoNuevo = Number((s.peso * [1.02, 0.98, 1.1, 1][i]).toFixed(2));
      const ev = await q('evento_crecimiento', `/activos-biologicos/${aid}/eventos/crecimiento`, 'admin',
        { tipo_medicion: 'PESO', valor_medicion: pesoNuevo, unidad_medida: 'kg', descripcion: `QA ${c.runId} tipo ${i}`,
           });
      if (!bueno(ev, 201) || !id(ev.data?.evento?.id_eventos)) {
        hechos.inciertas ||= ev.http == null || (ev.http === 201 && !ev.id_necesario); paso.motivo = 'Evento M02 no confirmado'; continue; }
      const eid = id(ev.data.evento.id_eventos); hechos.eventos.push({ id: eid, activo: aid });
      if (i === 1) {
        const ca = await q('estado_patch', `/activos-biologicos/${aid}/estado`, 'admin',
          { estado_nuevo: 'EN_TRATAMIENTO', fecha_cambio_estado: hoy(), motivo_cambio: `QA ${c.runId}` });
        if (!bueno(ca)) { hechos.inciertas ||= ca.http == null; paso.motivo = 'Cambio EN_TRATAMIENTO incompleto'; continue; }
        hechos.estadosActivos.push({ id: aid, estado: s.estado });
      }
      const pr = await q('procesar', '/finanzas/eventos/procesar', 'contador', {});
      if (!bueno(pr)) { hechos.inciertas ||= pr.http == null; paso.motivo = 'Procesamiento M06 incompleto'; continue; }
      const post = await q('variaciones', `/finanzas/periodos/${pid}/variaciones`);
      if (!bueno(post) || !valores(post)) { paso.motivo = 'Variaciones posteriores no disponibles'; continue; }
      ultimoPostVariaciones = post;
      const vs = idsNuevos(base.data, post.data, 'id_variacion_valor_razonable')
        .filter(x => id(x.id_activo_biologico) === aid).map(x => ({ ...x, _periodo: pid }));
      nuevas.push(...vs);
      hechos.variaciones.push(...vs.map(x => id(x.id_variacion_valor_razonable)));
      Object.assign(paso, { estado: vs.length ? 'REGISTRADO' : 'SIN_VARIACION', evento: eid,
        precio: id(precio.id_precio_mercado), variaciones: vs.map(x => ({ id: id(x.id_variacion_valor_razonable),
          tipo: x.tipo, monto: x.monto_variacion, estado: x.estado_trazabilidad, linea: id(x.id_linea) })) });
    }
    const vF = ultimoPostVariaciones ?? await q('variaciones', `/finanzas/periodos/${pid}/variaciones`);
    const lF = await q('lineas', `/finanzas/lineas?id_periodo_contable=${pid}`);
    const acumuladoDespues = await q('acumulado', `/finanzas/periodos/${pid}/estado-resultados/acumulado`);
    const otroDespues = await q('acumulado', `/finanzas/periodos/${otroId}/estado-resultados/acumulado`);
    r.observaciones.acumulados.despues = acumuladoDespues.data;
    r.observaciones.acumulados.otro_despues = otroDespues.data;
    r.observaciones.variaciones = nuevas.map(x => ({
      id: x.id_variacion_valor_razonable, activo: x.id_activo_biologico,
      tipo: x.tipo, monto: x.monto_variacion, linea: x.id_linea }));
    const mF = await q('mediciones', `/finanzas/periodos/${pid}/mediciones`);
    const auF = await auditoriaTodas(r, api, pid, tokens, c);
    const final = Object.fromEntries([['variaciones', vF], ['lineas', lF], ['mediciones', mF]]
      .map(([k, x]) => [k, bueno(x) && Array.isArray(x.data) ? x.data : null]));
    final.auditorias = auF;
    const campos = { variaciones: ['id_variacion_valor_razonable', v0.data], lineas: ['id_linea_asiento_nic41', l0.data],
      mediciones: ['id_medicion_posterior', m0.data], auditorias: ['id_evento', au0] };
    r.observaciones.nuevos = Object.fromEntries(Object.entries(campos).map(([k, [campo, antes]]) =>
      [k, final[k] ? idsNuevos(antes, final[k], campo).map(x => id(x[campo])) : null]));
    for (const k of Object.keys(campos)) if (r.observaciones.nuevos[k]) hechos[k] = r.observaciones.nuevos[k];
    hechos.conciliadas = Object.values(r.observaciones.nuevos).every(xs => xs && xs.every(Boolean));
    if (!hechos.conciliadas) r.problemas_tecnicos.push('Lecturas posteriores incompletas; conciliación del RUN pendiente.');
    const faltanAcumulados = [acumuladoAntes, acumuladoDespues, otroAntes, otroDespues].filter(x => !bueno(x));
    const falloConocido = faltanAcumulados.every(x => x.http == null || x.http >= 500 ||
      x.http === 422 && x.codigo === 'PERIODO_NO_CERRADO');
    const d11 = faltanAcumulados.length ?
      falloConocido ? { estado: 'RECHAZADO', severidad: 'ALTA',
        motivo: 'El acumulado público del período ABIERTO no responde o no está disponible.' } :
      { estado: 'NO_CONCLUYENTE', motivo: `Acumulado HTTP/código ajeno: ${faltanAcumulados.map(x => `${x.http}/${x.codigo}`).join(', ')}.` } :
      !final.variaciones || !nuevas.length ? { estado: 'NO_CONCLUYENTE', motivo: 'No se acreditaron las cuatro variaciones.' } :
      oraculo011({ antes: acumuladoAntes.data, despues: acumuladoDespues.data,
        otroAntes: otroAntes.data, otroDespues: otroDespues.data, variaciones: nuevas });
    registrar(r, 'TC-M06-011', d11, { preparacion: `período ${pid} ABIERTO, otro ${otroId}; ${nuevas.length} variaciones`,
      observado: d11.motivo, cumplido: 'Acumulados públicos antes y después, sin regeneración.' });
    if (d11.estado === 'RECHAZADO') incidencia(r, 'TC-M06-011', 'Acumulado discordante',
      'RF-86 CA-3, CA-9', 'Leer acumulados antes y después sin RF-93 versionado.',
      'Componentes y totales exactos; otro período sin cambios.', d11.motivo,
      'm06_router.py:587-591; application/services/reportes.py:31-43', 'Resultado del período incorrecto.',
      d11.severidad, 'INC-M06-G37-01');
    const primera = r.observaciones.paso_1, variacion = nuevas.find(x => x.id_activo_biologico === primera?.activo &&
      x.tipo === 'GANANCIA_TRANSFORMACION_BIOLOGICA');
    if (bloqueoIoT) {
      // El bloqueo ya quedó registrado; los otros casos siguen independientes.
    } else if (!variacion) {
      registrar(r, 'TC-M06-013',
        { estado: 'NO_CONCLUYENTE', motivo: 'No se observó variación TB+ nueva; revisar el procesamiento M06 antes de evaluar RF-91.' },
        { preparacion: `período ${pid}`, observado: 'Sin variación TB+ nueva.', cumplido: 'Se consultó la variación.' });
    } else {
      const ini = { ...variacion };
      const chInicial = await q('cadena', `/finanzas/lineas/${id(variacion.id_linea)}/cadena`);
      const ver = await q('trazabilidad', `/finanzas/periodos/${pid}/trazabilidad`, 'contador', {});
      if (ver.http >= 500) {
        const decision = { estado: 'RECHAZADO', motivo: `RF-91 HTTP ${ver.http} (${ver.codigo ?? 'sin código'}); verificación abortada.` };
        registrar(r, 'TC-M06-013', decision,
          { preparacion: `variación ${variacion.id_variacion_valor_razonable}, período ${pid}`,
            observado: 'Verificación del período abortada con HTTP 500.', cumplido: 'Estado inicial consultado.' });
        incidencia(r, 'TC-M06-013', 'Verificación RF-91 del período abortada', 'RF-86 CA-2, CA-11',
          'Crear TB+ y verificar período.', 'CADENA_COMPLETA y VERIFICADO.', 'POST RF-91 HTTP 500.',
          'trazabilidad_repository.py:106-117; síntoma similar a INC-M06-G32-01, causa no confirmada',
          'No se navega al evento M02 y lectura M03.', 'ALTA', 'INC-M06-G32-01');
      } else if (bueno(ver)) {
        const vf = await q('variaciones', `/finanzas/periodos/${pid}/variaciones`);
        const ch = await q('cadena', `/finanzas/lineas/${id(variacion.id_linea)}/cadena`);
        const final = Array.isArray(vf.data) ? vf.data.find(x => x.id_variacion_valor_razonable === variacion.id_variacion_valor_razonable) : null;
        r.observaciones.cadena_013 = { inicial: chInicial.data, final: ch.data, respuesta_rf91: ver.data };
        let d13 = bueno(chInicial) && bueno(vf) && bueno(ch) ? oraculo013({ inicial: ini,
          cadenaInicial: chInicial.data, final, cadena: ch.data,
          evento: primera.evento, lecturaApta: precondicion.id_telemetria_apta,
          verificadas: ver.data?.verificadas }) :
          { estado: 'NO_CONCLUYENTE', motivo: 'No se completaron las lecturas públicas de variación y cadena antes o después de RF-91.' };
        registrar(r, 'TC-M06-013', d13, { preparacion: `variación ${variacion.id_variacion_valor_razonable}, evento ${primera.evento}`,
          observado: `RF-91 HTTP ${ver.http}; cadena HTTP ${ch.http}`, cumplido: 'Se consultaron estado inicial, final y cadena.' });
        if (d13.estado === 'RECHAZADO') incidencia(r, 'TC-M06-013', 'Cadena RF-91 incompleta', 'RF-86 CA-11',
          'Verificar período y consultar cadena de la variación.', 'Estado VERIFICADO, M02 y M03 navegables.', d13.motivo,
          'trazabilidad_repository.py:37-87,106-117', 'Origen no navegable.', 'ALTA', 'INC-M06-G32-01');
      } else registrar(r, 'TC-M06-013', decidirVerificacion(ver.http, ver.codigo) ??
        { estado: 'NO_CONCLUYENTE', motivo: 'RF-91 respondió con esquema discordante; contraste técnico pendiente.' });
    }
    if (!c.sinNewman) await newman(r, c, api, tokens, pid, variacion?.id_linea);
  } catch (e) { r.problemas_tecnicos.push(texto(e.message)); }
  finally {
    if (!r.solicitudes.some(x => ['POST', 'PATCH'].includes(x.metodo)))
      for (const registro of r.contraste_contrato) registro.fase ??= 'previa';
    if (tokens) await cierre(r, c, api, tokens, hechos);
    aplicarDiscrepancias(r);
    for (const k of CASOS) if (!r.casos[k]) registrar(r, k,
      { estado: 'NO_CONCLUYENTE',
        motivo: r.impedimento_datos ?? `Preparación o automatización incompleta: ${r.problemas_tecnicos.at(-1) ?? 'sin diagnóstico'}.` });
    r.solicitudes_totales = r.solicitudes.length + (r.herramientas.newman?.solicitudes ?? 0);
    r.oficial = r.solicitudes_totales <= PRESUPUESTO.solicitudes_totales && !r.discrepancias_contrato.length && r.cierre.run.cierre_http === 200 && r.cierre.rollback.verificado &&
      CASOS.every(k => ['APROBADO', 'RECHAZADO'].includes(r.casos[k].estado)) &&
      r.herramientas.newman?.iteraciones === 1 && r.herramientas.newman?.fallos === 0 &&
      r.herramientas.newman?.codigo === 0;
    r.consume_version = r.oficial;
    r.condiciones_oficialidad = { presupuesto: r.solicitudes_totales <= PRESUPUESTO.solicitudes_totales,
      contrato: !r.discrepancias_contrato.length, delete_200: r.cierre.run.cierre_http === 200,
      rollback: r.cierre.rollback.verificado, casos: CASOS.every(k => ['APROBADO','RECHAZADO'].includes(r.casos[k].estado)),
      newman: r.herramientas.newman?.iteraciones === 1 && r.herramientas.newman?.fallos === 0 &&
        r.herramientas.newman?.codigo === 0 };
    r.seguimiento = { 'INC-M06-G37-01': r.casos['TC-M06-011'].estado === 'APROBADO' ? 'CORREGIDA' :
      r.casos['TC-M06-011'].estado === 'RECHAZADO' ? 'REPRODUCIDA' : 'NO_CONCLUYENTE',
      'INC-M06-G32-01': r.casos['TC-M06-013'].estado === 'APROBADO' ? 'CORREGIDA' :
      r.casos['TC-M06-013'].estado === 'RECHAZADO' ? 'REPRODUCIDA' : 'NO_CONCLUYENTE' };
    r.estado_ejecucion = r.oficial ? 'OFICIAL' : 'NO_OFICIAL';
    r.evidencias.push('preflight.json', 'resultado.json', nombreInforme(c.version));
    delete r._limite;
    guardar(path.join(c.directorio, 'resultado.json'), r);
    fs.writeFileSync(path.join(c.directorio, nombreInforme(c.version)), informe(c, r), 'utf8');
  }
  return r;
}
export async function principal(args, { proceso = process.env, archivoEnv = path.join(RAIZ, '.env.qa'),
  fetcher = globalThis.fetch, ensayo = false, sinNewman = false, precondicionIoTArchivo = null } = {}) {
  const c = { ...contexto(args, ensayo), ensayo, sinNewman: ensayo && sinNewman,
    precondicionIoTArchivo: ensayo && precondicionIoTArchivo || PRECONDICION_IOT };
  const env = leerEnv(proceso, archivoEnv);
  const p = preflight(c, env);
  guardar(path.join(c.directorio, 'preflight.json'), p);
  if (!p.ok) return { exitCode: 2, preflight: p, resultado: null };
  const r = await conPeticiones(fetcher, () => evaluar(c, env));
  return { exitCode: r.oficial ? 0 : 2, preflight: p, resultado: r };
}
if (process.argv.includes('--capacidades')) console.log(JSON.stringify(CAPACIDADES, null, 2));
else if (process.argv.includes('--comprobar')) process.exitCode = comprobar();
else if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try {
    const { exitCode, preflight: p, resultado: r } = await principal(process.argv.slice(2), { proceso: process.env });
    console.log(JSON.stringify({ grupo: 'G37', run_id: p.run_id, preflight_ok: p.ok,
      ...(r ? { oficial: r.oficial, estados: Object.fromEntries(CASOS.map(k => [k, r.casos[k].estado])) } :
        { barreras: p.barreras }) }));
    process.exitCode = exitCode;
  } catch (e) { console.error(texto(e.message)); process.exitCode = 2; }
}
