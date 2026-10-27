#!/usr/bin/env node
// Ejecutor canónico G88. El lanzador reserva el RUN; este módulo solo actúa con contrato válido.
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';
import vm from 'node:vm';
import { contextoEjecucion } from './lib/contrato_ejecutor.mjs';
import { sanearArtefacto } from './lib/g88_seguridad.mjs';
import { cerrarYVerificar, cierreUnico } from './lib/g88_cierre.mjs';
import { chromeLocal, ejecutarCypressControlado, TIMEOUT_UI_MS } from './lib/g88_cypress_runner.mjs';
import { CAPACIDADES, CASOS, IDS_CASOS, PLAN_266, bloqueosEscenario, resultadoOficial, umbralesActivos180 } from './lib/g88_catalogo.mjs';
import { derivarIncidencias, generarInforme, validarResultadoLocal } from './lib/g88_informe.mjs';
import { derivarEntradas, invertirCalibracion, camposUmbral, ausenciaT,
  activoUnicoVinculable, lecturaVinculada, lecturaVinculadaHistorial,
  conservarAnterior, asociacionVigente, rangoHistorial } from './lib/g88_entradas.mjs';
import { autorizacion266, autorizarEscritura266, verificarSemillaPreexistente266, ejecutar266 } from './lib/g88_266_plan.mjs';
import { construirCuerpoIngesta, cuerpoOpcionalNewman, planTemporalIngestas } from './lib/g88_ingesta.mjs';
import { respuestaSaneada, lecturaDelRun } from './lib/g88_respuestas.mjs';

const DIR = path.dirname(fileURLToPath(import.meta.url));
const RAIZ = path.resolve(DIR, '..', '..', '..', '..', '..');
const COLECCION = path.join(DIR, 'G88.postman_collection.json');
const respaldosHtmlNewman = new Map();
const escaparHtml = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
export function consolidarNewman(dir, r, respaldos = respaldosHtmlNewman.get(dir) ?? []) {
  const archivos = r.evidencias.filter((x) => /^newman\/[^/]+\.json$/.test(x));
  if (!archivos.length) return null;
  const partes = ['<!doctype html><html lang="es"><meta charset="utf-8"><title>G88 Newman consolidado</title>',
    '<style>body{font:14px system-ui;margin:2em;max-width:1000px}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f5f5f5;padding:1em}section{border-top:2px solid #555;margin:2em 0}li.error{color:#a00}</style>',
    '<h1>G88 Newman: solicitudes, respuestas y assertions</h1>'];
  let solicitudes = 0, assertions = 0;
  try {
    for (const archivo of archivos) {
      const reporte = JSON.parse(fs.readFileSync(path.join(dir, archivo), 'utf8'));
      const caso = /newman-(TC-M03-\d+)-/.exec(archivo)?.[1] ?? 'CASO_DESCONOCIDO';
      partes.push(`<section><h2>${escaparHtml(caso)} · ${escaparHtml(archivo)}</h2>`);
      for (const ex of reporte.run?.executions ?? []) {
        solicitudes++;
        const ruta = '/' + (ex.request?.url?.path ?? []).join('/');
        const cuerpoReq = ex.request?.body?.raw ?? '';
        const respuesta = Buffer.from(ex.response?.stream?.data ?? []).toString('utf8');
        partes.push(`<h3>${escaparHtml(ex.request?.method)} ${escaparHtml(ruta)} → HTTP ${escaparHtml(ex.response?.code)}</h3>`,
          `<details><summary>Solicitud saneada</summary><pre>${escaparHtml(cuerpoReq)}</pre></details>`,
          `<details open><summary>Respuesta saneada</summary><pre>${escaparHtml(respuesta)}</pre></details><ul>`);
        for (const a of ex.assertions ?? []) {
          assertions++;
          partes.push(`<li${a.error ? ' class="error"' : ''}>${escaparHtml(a.assertion)}: ${a.error ? 'FALLÓ ' + escaparHtml(a.error.message) : 'APROBÓ'}</li>`);
        }
        partes.push('</ul>');
      }
      partes.push('</section>');
    }
    partes.splice(3, 0, `<p>${solicitudes} solicitudes; ${assertions} assertions; ${archivos.length} JSON por ejecución.</p>`);
    fs.writeFileSync(path.join(dir, 'newman', 'newman-G88-consolidado.html'), partes.join('\n') + '</html>');
    r.evidencias.push('newman/newman-G88-consolidado.html');
    r.bitacora.push({ etapa: 'NEWMAN_CONSOLIDADO', solicitudes, assertions, json: archivos.length, html: 1 });
    return { solicitudes, assertions, json: archivos.length, html: 1 };
  } catch (e) {
    for (const [nombre, html] of respaldos) {
      fs.writeFileSync(path.join(dir, 'newman', nombre), html);
      r.evidencias.push(`newman/${nombre}`);
    }
    r.problemas_tecnicos.push(`Consolidación Newman falló: ${e.message}; HTML individuales conservados.`);
    return null;
  } finally { respaldosHtmlNewman.delete(dir); }
}
const ESCENARIO = path.join(DIR, 'lib', 'g88_escenario.json');
const API = 'https://www.api.inmero.co/api-sgpmp-test';
const API_FRONT = 'https://api.inmero.co/api-sgpmp-test';
const FRONT = 'https://api.inmero.co/sigab-test';
const MAX_API_DIRECTAS_V1 = 170; // Límite vigente; 266 solo verifica por GET su semilla previa.
const NOMBRE_INFORME = (v) => v === 1 ? 'TC-M03-G88_resultado.md' : `TC-M03-G88_reevaluacion_V${v}.md`;
const rutaRun = (base, version, runId) => version === 1
  ? path.join(base, 'Resultados', runId)
  : path.join(base, `EvaluacionV${version}`, 'Resultados', runId);
const cargarEscenario = () => JSON.parse(fs.readFileSync(ESCENARIO, 'utf8'));
const valor = (argv, nombre) => argv.includes(nombre) ? argv[argv.indexOf(nombre) + 1] : undefined;
const json = (x) => JSON.stringify(x, null, 2);
const idNum = (x) => Number.isInteger(Number(x)) && Number(x) > 0;
const huella = (x) => createHash('sha256').update(JSON.stringify(x)).digest('hex');
// Misma lectura de .env.qa que G87; la autorización siempre procede del proceso.
export function leerEnv({ raiz = RAIZ, proceso = process.env } = {}) {
  const archivo = path.join(raiz, '.env.qa');
  const archivoExiste = fs.existsSync(archivo);
  const valores = {};
  const fuentes = {};
  if (archivoExiste) for (const linea of fs.readFileSync(archivo, 'utf8').split(/\r?\n/)) {
    const m = linea.match(/^\s*([A-Z0-9_]+)\s*=(.*)$/);
    if (m) { valores[m[1]] = m[2].trim().replace(/^(['"])(.*)\1$/, '$2'); fuentes[m[1]] = '.env.qa'; }
  }
  for (const [nombre, valor] of Object.entries(proceso)) {
    if (valor) { valores[nombre] = valor; fuentes[nombre] = 'proceso'; }
  }
  if (proceso.BROKER_SERVICE_TOKEN !== undefined) {
    valores.BROKER_SERVICE_TOKEN = proceso.BROKER_SERVICE_TOKEN;
    fuentes.BROKER_SERVICE_TOKEN = 'proceso';
  }
  delete valores.QA_AUTORIZADO;
  delete fuentes.QA_AUTORIZADO;
  if (proceso.QA_AUTORIZADO) {
    valores.QA_AUTORIZADO = proceso.QA_AUTORIZADO;
    fuentes.QA_AUTORIZADO = 'proceso';
  }
  return { valores, fuentes, archivoExiste };
}
function persistirFalloContrato(a, motivo) {
  const archivo = valor(a, '--contexto');
  if (!archivo || !path.isAbsolute(archivo)) return;
  const padre = path.dirname(path.resolve(archivo));
  const run = path.basename(padre);
  const version = /^RUN-G88-V(\d+)-\d{8}-\d{6}$/.exec(run);
  if (!version || path.basename(archivo) !== 'contexto_operacion.json') return;
  const esperado = rutaRun(DIR, Number(version[1]), run);
  if (padre !== esperado || !fs.existsSync(archivo) || fs.lstatSync(archivo).isSymbolicLink()) return;
  fs.writeFileSync(path.join(padre, 'preflight.json'), json({ fase: 'CONTRATO', ok: false,
    motivos: [String(motivo).slice(0, 300)] }));
}
const TEMPERATURA = new Set(['TC-M03-169', 'TC-M03-170', 'TC-M03-171']);
export function sensor180Acreditado(sensorId, escenario) {
  return idNum(sensorId) && Number(sensorId) === escenario?.semilla_180?.sensor;
}
function cadenaEfectiva(id, caso, escenario, V) {
  if (id === 'TC-M03-172') return { ...caso, cadena: {
    especie_id: escenario.semilla_candidata.especie,
    variable_id: 1, umbral_id: escenario.semilla_candidata.umbral,
    variable_nombre: 'Temperatura Ambiental', artefactos_sin_datos_privados: true } };
  if (id === 'TC-M03-180') return { ...caso, cadena: {
    sensor_id: Number(V.QA_G88_180_SENSOR_ID), dispositivo_id: escenario.semilla_180.dispositivo,
    infraestructura_id: escenario.semilla_180.area, dashboard_infraestructura_id: escenario.semilla_180.area,
    especie_id: escenario.semilla_180.especie, variable_id: escenario.semilla_180.variable,
    asociacion_id: escenario.semilla_180.asociacion, calibracion_id: escenario.semilla_180.calibracion,
    serial: V.QA_G88_180_SERIAL,
    sensor_nombre: escenario.semilla_180.nombre_sensor, unidad: escenario.semilla_180.unidad,
    artefactos_sin_datos_privados: true } };
  if (!TEMPERATURA.has(id)) return caso;
  const semilla = escenario.semilla_169_171;
  return { ...caso, cadena: { sensor_id: semilla.sensor, dispositivo_id: semilla.dispositivo,
    infraestructura_id: semilla.area, dashboard_infraestructura_id: semilla.area,
    especie_id: semilla.especie, variable_id: 1, umbral_id: 70, calibracion_id: 68,
    serial: V.QA_G88_169_171_SERIAL, sensor_nombre: 'Temperatura Ambiental',
    unidad: '°C', artefactos_sin_datos_privados: true } };
}

function comprobar() {
  globalThis.fetch = () => { throw new Error('BLOQUEO_RED_LOCAL'); };
  const checks = [];
  const agregar = (nombre, ok) => { checks.push({ nombre, ok }); console.log(`${ok ? '[OK]' : '[FALLA]'} ${nombre}`); };
  let escenario;
  try { escenario = cargarEscenario(); agregar('Escenario JSON legible y seis casos', IDS_CASOS.every((id) => !!escenario.casos[id])); }
  catch { agregar('Escenario JSON legible y seis casos', false); }
  let coleccion;
  try { coleccion = JSON.parse(fs.readFileSync(COLECCION, 'utf8')); agregar('Colección Newman única y legible', coleccion.item.length === 3); }
  catch { agregar('Colección Newman única y legible', false); }
  const archivos = ['g88.mjs', 'g88.cy.js', 'g88.cypress.config.cjs', 'lib/contrato_ejecutor.mjs',
    'lib/g88_cierre.mjs', 'lib/g88_informe.mjs', 'lib/g88_presentacion.mjs', 'lib/g88_seguridad.mjs',
    'lib/g88_cypress_runner.mjs', 'lib/g88_cypress_worker.mjs', 'lib/g88_catalogo.mjs',
    'lib/g88_266_plan.mjs', 'lib/g88_ingesta.mjs', 'lib/g88_respuestas.mjs'];
  for (const archivo of archivos) {
    try {
      const texto = fs.readFileSync(path.join(DIR, archivo), 'utf8');
      if (/\.(?:cjs|cy\.js)$/.test(archivo)) new vm.Script(texto, { filename: archivo });
      agregar(`Archivo ${archivo} legible`, texto.length > 0);
    } catch { agregar(`Archivo ${archivo} legible`, false); }
  }
  const activos = archivos.map((f) => fs.readFileSync(path.join(DIR, f), 'utf8')).join('\n') + fs.readFileSync(COLECCION, 'utf8');
  agregar('Sin invocaciones de control SQL ni procesos de control de versiones en rutas activas',
    !/test-control\/query|execFileSync\(['"]git|spawnSync\(['"]git|\bfrom ['"](?:.*\/)?g88_(?:lib|casos)\.mjs/.test(activos));
  agregar('172 solo GET y M09 sujeto a lista blanca 266',
    coleccion?.item?.every((x) => !/\/configuracion\/umbrales/.test(JSON.stringify(x)) || x.request?.method === 'GET')
    && /autorizarEscritura266/.test(fs.readFileSync(path.join(DIR, 'g88.mjs'), 'utf8')));
  agregar('266 parametrizado y desactivado', !PLAN_266.habilitado
    && PLAN_266.pasos[0] === 'semilla_preexistente'
    && !PLAN_266.pasos.includes('compuerta_humana')
    && PLAN_266.pasos.indexOf('auditoria_propagacion_alta') < PLAN_266.pasos.indexOf('ingesta_unica_15')
    && PLAN_266.pasos.indexOf('auditoria_propagacion_edicion') < PLAN_266.pasos.indexOf('dashboard_e_historial_sin_ingesta')
    && coleccion?.item?.[0]?.request?.body?.raw === '{{cuerpo_ingesta}}');
  agregar('180 acreditado y 266 sin altas estructurales en RUN',
    escenario?.semilla_180?.sensor === 737 && escenario.semilla_180.asociacion === 522
    && escenario.semilla_180.calibracion === 69 && escenario.semilla_180.variable === 11
    && escenario?.casos['TC-M03-266']?.modo_semilla === 'SEMILLA_PREEXISTENTE'
    && !/prepararSemilla266|fase === 'SEMILLA'/.test(fs.readFileSync(path.join(DIR, 'lib/g88_266_plan.mjs'), 'utf8')));
  agregar('266 acreditado con IDs de semilla registrados',
    escenario?.semilla_266?.estado === 'ACREDITADA_POR_RESPONSABLE_QA_EN_TEST_2026-10-24'
    && JSON.stringify([escenario.semilla_266.especie, escenario.semilla_266.area,
      escenario.semilla_266.activo_vinculable_unico, escenario.semilla_266.dispositivo,
      escenario.semilla_266.sensor, escenario.semilla_266.asociacion,
      escenario.semilla_266.calibracion]) === JSON.stringify([220, 504, 885, 520, 738, 523, 70]));
  const worker = fs.readFileSync(path.join(DIR, 'lib/g88_cypress_worker.mjs'), 'utf8');
  agregar('Cypress Chrome headless y timeout', /browser: 'chrome'/.test(worker) && /headed: false/.test(worker)
    && /TIMEOUT_UI_MS/.test(activos) && !/browser: 'electron'/.test(worker));
  agregar('Contrato y capacidades', CAPACIDADES.contrato === 'sigab-qa-ejecutor/1'
    && IDS_CASOS.every((id) => CAPACIDADES.comprobaciones_obligatorias[id].API.length === CASOS[id].api.length));
  agregar('Ruta oficial V1 y V2', path.join(DIR, 'Resultados', 'RUN-G88-V1-20261023-000000').includes('Resultados')
    && NOMBRE_INFORME(2) === 'TC-M03-G88_reevaluacion_V2.md');
  agregar('T por defecto, 172 candidato y activo 169-171 resuelto', escenario?.representacion_T.estado === 'POR_DEFECTO_SIN_CONFIGURACION_ESPECIFICA'
    && escenario?.casos['TC-M03-172'].clasificacion_preparacion === 'DEFECTO_FUNCIONAL_CANDIDATO'
    && escenario?.semilla_169_171?.estado === 'PRECONDICION_ACTIVO_RESUELTA_POR_RESPONSABLE_QA_2026-10-24'
    && escenario.semilla_169_171.activo_vinculable?.id === 884);
  console.log(`Resultado local: ${checks.filter((x) => x.ok).length}/${checks.length} comprobaciones.`);
  return checks.every((x) => x.ok) ? 0 : 1;
}

export function regenerarInforme(nombre, salidaSolicitada) {
  globalThis.fetch = () => { throw new Error('BLOQUEO_RED_LOCAL'); };
  const m = /^RUN-G88-V(\d+)-\d{8}-\d{6}$/.exec(nombre ?? '');
  if (!m || !salidaSolicitada) throw new Error('Indique RUN válido y --salida externa.');
  const salida = path.resolve(salidaSolicitada);
  if (path.dirname(salida) !== DIR) throw new Error('La salida debe estar fuera de Resultados/ y EvaluacionVn/, en la raíz del grupo.');
  const padre = fs.realpathSync(path.dirname(salida));
  if (padre !== fs.realpathSync(DIR) || path.extname(salida).toLowerCase() !== '.md'
    || fs.existsSync(salida)) throw new Error('La salida debe ser un Markdown nuevo en la raíz del grupo, fuera de Resultados/ y EvaluacionVn/.');
  const v = Number(m[1]);
  const dir = rutaRun(DIR, v, nombre);
  const real = fs.realpathSync(dir);
  if (real !== dir || fs.lstatSync(dir).isSymbolicLink()) throw new Error('RUN no canónico.');
  const resultado = JSON.parse(fs.readFileSync(path.join(dir, 'resultado.json'), 'utf8'));
  const informe = generarInforme(resultado);
  const errores = validarResultadoLocal(resultado, dir, informe);
  if (errores.length) throw new Error(errores.join('; '));
  fs.writeFileSync(salida, informe, { flag: 'wx' });
  return salida;
}

function requerirAmbiente(c, V, { recuperar = false, casos = IDS_CASOS } = {}) {
  const errores = [];
  const ingesta = !recuperar && casos.some((id) => ['TC-M03-169', 'TC-M03-170', 'TC-M03-171', 'TC-M03-180', 'TC-M03-266'].includes(id));
  const ui = !recuperar && casos.some((id) => ['TC-M03-172', 'TC-M03-180'].includes(id));
  if (V.QA_AUTORIZADO !== 'SI') errores.push('QA_AUTORIZADO debe ser SI.');
  if (String(V.SIGAB_API_TEST_BASE ?? '').replace(/\/+$/, '') !== API) errores.push('API TEST no coincide con destino autorizado.');
  if (!V.QA_SANDBOX_SECRET || (ingesta && !V.BROKER_SERVICE_TOKEN)) errores.push('Faltan credenciales del sandbox o ingesta.');
  if (casos.some((id) => TEMPERATURA.has(id)) && !/^[A-Za-z0-9._-]{1,100}$/.test(V.QA_G88_169_171_SERIAL ?? ''))
    errores.push('Falta QA_G88_169_171_SERIAL privado para 169-171.');
  if (casos.includes('TC-M03-180') && (!idNum(V.QA_G88_180_SENSOR_ID)
    || !/^[A-Za-z0-9._-]{1,100}$/.test(V.QA_G88_180_SERIAL ?? '')))
    errores.push('Faltan QA_G88_180_SENSOR_ID real y QA_G88_180_SERIAL privado.');
  const claves = ['QA_ADMIN_EMAIL', 'QA_ADMIN_PASSWORD',
    ...(ingesta ? ['QA_PROD_EMAIL', 'QA_PROD_PASSWORD'] : []),
    ...(!recuperar && casos.includes('TC-M03-180') ? ['QA_PROD_UI_EMAIL', 'QA_PROD_UI_PASSWORD'] : [])];
  for (const k of claves) if (!V[k]) errores.push(`Falta ${k}.`);
  if (ui && String(V.SIGAB_FRONT_TEST_URL ?? '').replace(/\/+$/, '') !== FRONT)
    errores.push('Frontend TEST no coincide con destino autorizado.');
  if (!c.referencia || c.referencia.length < 8) errores.push('Referencia de autorización incompleta.');
  if (casos.includes('TC-M03-266') && !/^[A-Za-z0-9._-]{1,50}$/.test(V.QA_G88_266_SERIAL ?? ''))
    errores.push('Falta QA_G88_266_SERIAL privado.');
  if (casos.includes('TC-M03-266') && V.QA_G88_266_CONSERVAR_SEMILLA === 'NO')
    errores.push('266: conservar_semilla=false requiere desactivaciones estructurales fuera de la lista blanca de esta orden.');
  return errores;
}

function cadenaLista(caso) {
  const s = caso.cadena;
  if (caso.clasificacion_preparacion === 'DEFECTO_FUNCIONAL_CANDIDATO')
    return !!s && ['especie_id', 'variable_id'].every((k) => idNum(s[k]))
      && !!s.variable_nombre && s.artefactos_sin_datos_privados === true;
  if (!s || !['sensor_id', 'dispositivo_id', 'infraestructura_id', 'especie_id',
    'variable_id', 'dashboard_infraestructura_id'].every((k) => idNum(s[k]))
    || (caso.variable !== 'NH3' && !idNum(s.calibracion_id))
    || !/^[A-Za-z0-9._-]{1,100}$/.test(String(s.serial ?? '')) || !s.sensor_nombre
    || s.artefactos_sin_datos_privados !== true)
    return false;
  if (caso.variable !== 'TEMPERATURA_AMBIENTAL' && caso.variable !== 'NH3'
    && s.sin_alertas_confirmado !== true) return false;
  if (caso.variable === 'TEMPERATURA_AMBIENTAL' && (!idNum(s.umbral_id)
    || (caso.clasificacion_preparacion === 'BLOQUEADO' && (caso.seguridad_m09?.estado !== 'CONFIRMADO_SIN_EDGE_NI_AFECTACION_EXTERNA'
    || !caso.seguridad_m09?.evidencia_lectura)))) return false;
  if (caso.variable === 'NH3' && (s.variable_id !== 11 || s.especie_id !== 126
    || s.dispositivo_id !== 357 || s.infraestructura_id !== 349 || s.umbral_id != null)) return false;
  return true;
}

export function preflightLocal(contrato, { ambiente = leerEnv() } = {}) {
  const { valores: V, fuentes, archivoExiste } = ambiente;
  const escenario = cargarEscenario();
  const bloques = bloqueosEscenario(escenario);
  if (sensor180Acreditado(V.QA_G88_180_SENSOR_ID, escenario)) bloques['TC-M03-180'] = [];
  else bloques['TC-M03-180'].push({ tipo: 'DATOS', motivo: 'QA_G88_180_SENSOR_ID debe ser el sensor 737 acreditado.' });
  const habilitar266 = autorizacion266(contrato.contexto);
  if (habilitar266) bloques['TC-M03-266'] = [];
  const ids266 = ['ESPECIE', 'AREA', 'ACTIVO', 'DISPOSITIVO', 'SENSOR', 'ASOCIACION', 'CALIBRACION'];
  const esperados266 = [220, 504, 885, 520, 738, 523, 70];
  const faltas266 = ids266.filter((nombre, i) => Number(V[`QA_G88_266_${nombre}_ID`]) !== esperados266[i]);
  if (habilitar266 && faltas266.length) bloques['TC-M03-266'].push({ tipo: 'DATOS',
    motivo: `IDs 266 ausentes o distintos: ${faltas266.map((x) => `QA_G88_266_${x}_ID`).join(', ')}` });
  const casos = IDS_CASOS.map((id) => {
    const privadas = ['QA_SANDBOX_SECRET', 'QA_ADMIN_EMAIL', 'QA_ADMIN_PASSWORD',
      ...(TEMPERATURA.has(id) || ['TC-M03-180', 'TC-M03-266'].includes(id)
        ? ['BROKER_SERVICE_TOKEN', 'QA_PROD_EMAIL', 'QA_PROD_PASSWORD'] : []),
      ...(TEMPERATURA.has(id) ? ['QA_G88_169_171_SERIAL'] : []),
      ...(id === 'TC-M03-180' ? ['QA_G88_180_SERIAL', 'QA_PROD_UI_EMAIL', 'QA_PROD_UI_PASSWORD'] : []),
      ...(id === 'TC-M03-266' ? ['QA_G88_266_SERIAL'] : [])];
    const c = cadenaEfectiva(id, escenario.casos[id], escenario, V);
    const motivos = [...bloques[id].map((x) => x.motivo)];
    if (id === 'TC-M03-266') {
      if (!habilitar266) motivos.push('266 sin habilitación explícita en el contexto.');
    } else {
      const estadoAdmitido = c.estado_datos === 'CONFIRMADO_EN_TEST'
        || (id === 'TC-M03-180' && c.estado_datos === 'SEMILLA_ACREDITADA_REVALIDAR_EN_RUN')
        || (id === 'TC-M03-172' && c.clasificacion_preparacion === 'DEFECTO_FUNCIONAL_CANDIDATO')
        || (TEMPERATURA.has(id) && c.estado_datos === 'PRECONDICION_ACTIVO_RESUELTA_POR_RESPONSABLE_QA_2026-10-24');
      if (!estadoAdmitido) motivos.push(`estado_datos ${c.estado_datos} no habilita el caso.`);
      if (!cadenaLista(c)) motivos.push('Cadena local incompleta.');
    }
    return { id, ejecutable: motivos.length === 0, motivos,
      variables_privadas_ausentes: privadas.filter((x) => !V[x]) };
  });
  const ejecutables = casos.filter((x) => x.ejecutable).map((x) => x.id);
  const erroresAmbiente = requerirAmbiente(contrato, V, { casos: ejecutables });
  const nombres = ['QA_AUTORIZADO', 'SIGAB_API_TEST_BASE', 'QA_SANDBOX_SECRET',
    'QA_ADMIN_EMAIL', 'QA_ADMIN_PASSWORD',
    ...(ejecutables.some((id) => TEMPERATURA.has(id) || ['TC-M03-180', 'TC-M03-266'].includes(id))
      ? ['BROKER_SERVICE_TOKEN', 'QA_PROD_EMAIL', 'QA_PROD_PASSWORD'] : []),
    ...(ejecutables.some((id) => TEMPERATURA.has(id)) ? ['QA_G88_169_171_SERIAL'] : []),
    ...(ejecutables.some((id) => ['TC-M03-172', 'TC-M03-180'].includes(id)) ? ['SIGAB_FRONT_TEST_URL'] : []),
    ...(ejecutables.includes('TC-M03-180') ? ['QA_G88_180_SENSOR_ID', 'QA_G88_180_SERIAL', 'QA_PROD_UI_EMAIL', 'QA_PROD_UI_PASSWORD'] : []),
    ...(ejecutables.includes('TC-M03-266') ? ['QA_G88_266_SERIAL', ...ids266.map((x) => `QA_G88_266_${x}_ID`)] : [])];
  const faltantes = nombres.filter((x) => !V[x]);
  const variables = nombres.map((nombre) => ({ nombre, fuente: V[nombre] ? fuentes[nombre] : 'ausente' }));
  const semillas = { '169_171': escenario.semilla_169_171.estado === 'PRECONDICION_ACTIVO_RESUELTA_POR_RESPONSABLE_QA_2026-10-24'
      && escenario.semilla_169_171.activo_vinculable?.id === 884
      && escenario.semilla_169_171.sensor === 552 && escenario.semilla_candidata.umbral === 70
      && escenario.semilla_candidata.calibracion === 68,
    '180': escenario.semilla_180.estado === 'ACREDITADA_POR_RESPONSABLE_QA_EN_TEST_2026-10-24'
      && escenario.semilla_180.sensor === 737 && escenario.semilla_180.asociacion === 522
      && escenario.semilla_180.calibracion === 69,
    '266': escenario.semilla_266.estado === 'ACREDITADA_POR_RESPONSABLE_QA_EN_TEST_2026-10-24'
      && escenario.semilla_266.sin_gateway === true
      && JSON.stringify([escenario.semilla_266.especie, escenario.semilla_266.area,
      escenario.semilla_266.activo_vinculable_unico, escenario.semilla_266.dispositivo,
      escenario.semilla_266.sensor, escenario.semilla_266.asociacion,
      escenario.semilla_266.calibracion]) === JSON.stringify(esperados266) };
  const motivosGlobales = [
    ...(!ejecutables.length ? ['Ningún caso localmente ejecutable.'] : []),
    ...(erroresAmbiente.length ? ['Variables o destinos de ambiente incompletos.'] : []),
    ...(!Object.values(semillas).every(Boolean) ? ['Semillas registradas incoherentes.'] : [])];
  return { fase: 'PREFLIGHT_LOCAL', grupo: 'G88', run_id: contrato.runId,
    casos, ejecutables, variables, archivo_env_qa_existe: archivoExiste,
    variables_ausentes: faltantes, barreras_ambiente: erroresAmbiente,
    motivos_globales: motivosGlobales,
    semillas_registradas_coherentes: semillas,
    verificaciones_pendientes_en_run: ['169-171: umbral y calibración por GET',
      '180: calibración y ausencia de umbral NH3 por GET; asociación 522 como diagnóstico posterior no bloqueante',
      '266: siete IDs y relaciones por GET; auditoría de propagación tras cada escritura M09'],
    ok: motivosGlobales.length === 0 };
}

export function contextoSolicitudRun({ abierto, token, enRun }) {
  if (abierto && token) {
    if (enRun === false) throw new Error('CONTEXTO_MIXTO: cuenta autenticada fuera del RUN abierto.');
    return true;
  }
  return enRun ?? false;
}

export async function evaluar(contrato, { soloPreflight = false, ambiente = leerEnv() } = {}) {
  const V = ambiente.valores;
  const diagnostico = preflightLocal(contrato, { ambiente });
  if (!soloPreflight) fs.writeFileSync(path.join(contrato.directorio, 'preflight.json'), json(diagnostico));
  if (!diagnostico.ok) return 2;
  if (soloPreflight) return 0;
  const escenario = cargarEscenario();
  const bloques = bloqueosEscenario(escenario);
  if (sensor180Acreditado(V.QA_G88_180_SENSOR_ID, escenario)) bloques['TC-M03-180'] = [];
  else bloques['TC-M03-180'].push({ tipo: 'DATOS',
    motivo: 'Sensor 180 de contexto ausente o distinto del ID 737 acreditado; sin ingesta.' });
  const habilitar266 = autorizacion266(contrato.contexto);
  if (habilitar266) bloques['TC-M03-266'] = [];
  const ejecutables = IDS_CASOS.filter((id) => {
    if (!diagnostico.ejecutables.includes(id)) return false;
    if (id === 'TC-M03-266') return habilitar266;
    const c = cadenaEfectiva(id, escenario.casos[id], escenario, V);
    if (c.estado_datos !== 'CONFIRMADO_EN_TEST' && id !== 'TC-M03-180'
      && !(id === 'TC-M03-172' && c.clasificacion_preparacion === 'DEFECTO_FUNCIONAL_CANDIDATO')
      && !(TEMPERATURA.has(id)
      && c.estado_datos === 'PRECONDICION_ACTIVO_RESUELTA_POR_RESPONSABLE_QA_2026-10-24')) return false;
    if (!cadenaLista(c)) {
      bloques[id].push({ tipo: 'DATOS', motivo: `${id}: cadena, alertas o seguridad M09 incompletas.` });
      return false;
    }
    return !bloques[id].length;
  });
  if (!ejecutables.length) {
    console.error('BLOQUEO_DATOS: ninguna cadena de semilla está CONFIRMADA_EN_TEST; no se abre RUN ni se consulta TEST.');
    return 2;
  }
  const erroresAmbiente = requerirAmbiente(contrato, V, { casos: ejecutables });
  if (erroresAmbiente.length) { console.error(`Barrera local: ${erroresAmbiente.join(' ')}`); return 2; }
  const dir = contrato.directorio;
  if (!fs.existsSync(path.join(dir, 'contexto_operacion.json'))
    || fs.existsSync(path.join(dir, 'resultado.json'))) throw new Error('RUN reservado incoherente o usado.');
  const secretos = [V.QA_SANDBOX_SECRET, V.BROKER_SERVICE_TOKEN, V.QA_G88_169_171_SERIAL,
    V.QA_G88_266_SERIAL, V.QA_G88_180_SERIAL,
    V.QA_ADMIN_PASSWORD, V.QA_PROD_PASSWORD,
    V.QA_PROD_UI_PASSWORD, V.QA_ADMIN_EMAIL, V.QA_PROD_EMAIL, V.QA_PROD_UI_EMAIL,
    ...Object.entries(V).filter(([nombre]) => /^QA_G88_/.test(nombre)).map(([, valor]) => valor)].filter(Boolean);
  const runId = contrato.runId.slice(4);
  const r = { grupo: 'TC-M03-G88', rf: 'RF-58', version: contrato.version, intento: contrato.intento,
    run_id: contrato.runId, operacion: contrato.operacion.toUpperCase(), referencia: contrato.referencia,
    ambiente: 'TEST', inicio: new Date().toISOString(), fin: null, estado: 'EN_CURSO',
    commit: 'NO VERIFICADO', herramientas: { node: process.version, newman: 'pendiente', cypress: 'pendiente' },
    comprobaciones: [], casos: {}, bloqueos: bloques, evidencias: ['resultado.json'], incidencias: [],
    incidencias_automatizacion: [], hallazgos_producto: [],
    problemas_tecnicos: [], cierre: null, cypress: { total_pruebas: 0,
      casos: Object.fromEntries(['TC-M03-172', 'TC-M03-180'].map((id) => [id,
        { estado: 'NO_EJECUTADO', total_pruebas: 0, causa: 'Fase Cypress pendiente.' }])) }, bitacora: [],
     respuestas: [], alertas_activas_observadas: [], plan_temporal: null,
     umbral_run_266: null, parada_seguridad: null };
  const tokens = {};
  const previos = [];
  const lecturas = [];
  const faseUi = { ingesta180Acreditada: false, motivo180: 'Ingesta NH3 no acreditada (HTTP 201 y lectura válida pendientes).' };
  let casoActual = null;
  let sensorActual = null;
  const guardar = () => {
    r.datos_rollback = { anteriores: previos.map((p) => ({ caso: p.caso,
      ...(p.ruta_asociaciones ? { ruta_asociaciones: p.ruta_asociaciones, asociaciones_sha256: huella(p.asociaciones) } : {}),
      ...(p.ruta_dashboard ? { ruta_dashboard: p.ruta_dashboard, dashboard_sha256: huella(p.dashboard) } : {}),
      ...(p.ruta_umbral ? { ruta_umbral: p.ruta_umbral, umbral_sha256: huella(p.umbral) } : {}) })),
      lecturas };
    Object.assign(r, datosRegistro(r.cierre, lecturas));
    fs.writeFileSync(path.join(dir, 'resultado.json'), sanearArtefacto(json(r), secretos));
  };
  let abierto = false;
  let peticionCancelada = false;
  const run = { id: runId, secreto: V.QA_SANDBOX_SECRET };
  let peticionesDirectas = 0;
  async function solicitar(metodo, ruta, { token, secreto, enRun, cuerpo, base = API, control266 } = {}) {
    const cierreRun = metodo === 'DELETE' && ruta === `/test-control/runs/${runId}`;
    if (peticionCancelada && abierto && !cierreRun)
      throw new Error('SOLICITUD_CANCELADA: se detienen las peticiones del RUN hasta su cierre.');
    enRun = contextoSolicitudRun({ abierto, token, enRun });
    if (++peticionesDirectas > MAX_API_DIRECTAS_V1) throw new Error('LIMITE_API_DIRECTAS_V1: 170 peticiones.');
    const escrituraControlada = metodo !== 'GET' && (/^\/configuracion\//.test(ruta)
      || /^\/activos-biologicos(?:\/|$)/.test(ruta) || (control266 && ruta === '/iot/telemetria'));
    if (escrituraControlada && (!habilitar266 || !control266 || !autorizarEscritura266({
      metodo, ruta, cuerpo, fase: control266.fase, semilla: control266.semilla,
      umbralId: control266.umbralId, serial: control266.serial }))) throw new Error('SEGURIDAD_266: escritura fuera de lista blanca.');
    if (escrituraControlada && control266) {
      control266.conteos ??= {};
      const clave = `${metodo} ${ruta}`;
      if ((control266.conteos[clave] ?? 0) >= 1) throw new Error('SEGURIDAD_266: escritura repetida.');
      control266.conteos[clave] = 1;
    }
    const h = { Accept: 'application/json' };
    if (token) h.Authorization = `Bearer ${token}`;
    if (secreto) h['X-Sandbox-Secret'] = secreto;
    if (enRun) { h['X-Test-Run-Id'] = run.id; h['X-Sandbox-Secret'] = run.secreto; }
    if (cuerpo !== undefined) h['Content-Type'] = 'application/json';
    let x, t;
    const inicioSolicitud = Date.now();
    try {
      x = await fetch(base + ruta, { method: metodo, headers: h,
        body: cuerpo === undefined ? undefined : JSON.stringify(cuerpo), redirect: 'manual', signal: AbortSignal.timeout(30000) });
      t = await x.text();
    } catch (error) {
       if (error.name === 'TimeoutError' || error.name === 'AbortError') {
         peticionCancelada = true;
         r.parada_seguridad ??= { causa: 'PARADA_SEGURIDAD_SESION_COMPARTIDA', caso: casoActual,
           peticion: metodo, ruta: ruta.split('?')[0], latencia_ms: Date.now() - inicioSolicitud,
           motivo: sanearArtefacto(String(error.message), secretos), casos_pendientes: [] };
       }
      r.bitacora.push({ caso: casoActual, metodo, ruta: ruta.split('?')[0], en_run: enRun,
        latencia_ms: Date.now() - inicioSolicitud, error: sanearArtefacto(String(error.message), secretos) });
      throw new Error(`${metodo} ${ruta}: ${error.message} (timeout 30000 ms)`, { cause: error });
    }
    let j; try { j = JSON.parse(t); } catch { j = t.slice(0, 200); }
    r.bitacora.push({ caso: casoActual, metodo, ruta: ruta.split('?')[0], en_run: enRun,
      latencia_ms: Date.now() - inicioSolicitud, status: x.status,
      eco_run: enRun ? x.headers.get('x-test-run-id') === run.id : null });
    if (cierreRun && [200, 404].includes(x.status)) { abierto = false; peticionCancelada = false; }
    if (metodo === 'GET' && (/^\/iot\/(?:vinculaciones|monitoreo\/(?:historial|dashboard))\?/.test(ruta)
      || /^\/configuracion\/sensores\/\d+\/asociaciones$/.test(ruta)
      || ruta === '/configuracion/variables-ambientales'
      || ruta === '/configuracion/sensores/rangos-calibracion'
      || ruta === '/configuracion/dispositivos-iot/520/sensores')) {
      const ids = sensorActual ? [sensorActual] : [...new Set(lecturas.map((l) => l.sensor_id))];
      const cuerpoSaneado = respuestaSaneada(ruta, j, ids);
      r.respuestas.push({ caso: casoActual, ruta, http: x.status, cuerpo: cuerpoSaneado });
    }
    return { status: x.status, json: j, eco: x.headers.get('x-test-run-id') };
  }
  const autenticar = async (rol) => {
    const correo = V[rol === 'admin' ? 'QA_ADMIN_EMAIL' : 'QA_PROD_EMAIL'];
    const clave = V[rol === 'admin' ? 'QA_ADMIN_PASSWORD' : 'QA_PROD_PASSWORD'];
    const x = await solicitar('POST', '/sesiones/', { cuerpo: { correo_electronico: correo, contrasena: clave } });
    if (x.status !== 200 || !x.json?.token) throw new Error(`Login ${rol} HTTP ${x.status}`);
    tokens[rol] = x.json.token; secretos.push(x.json.token);
    return x.json.token;
  };
  const cerrar = cierreUnico(async () => {
    if (!abierto) return;
    r.cierre = await cerrarYVerificar({ runId, secreto: run.secreto, solicitar,
       autenticar: () => autenticar('admin'), anteriores: previos, lecturas,
       umbralRun266: r.umbral_run_266 });
     if (!r.cierre.rollback.verificado)
       r.problemas_tecnicos.push(...(r.cierre.errores.length
         ? r.cierre.errores : ['Rollback no confirmado por API e historial oficial.']));
    guardar();
  });
  const interrupcion = () => { void cerrar(); process.exitCode = 130; };
  process.on('SIGINT', interrupcion); process.on('SIGTERM', interrupcion);
  try {
    await autenticar('admin');
    if (ejecutables.some((id) => ['TC-M03-169', 'TC-M03-170', 'TC-M03-171', 'TC-M03-180', 'TC-M03-266'].includes(id)))
      await autenticar('prod');
    const disponibilidad = await solicitar('DELETE', `/test-control/runs/${runId}-NO-EXISTE`, { secreto: run.secreto });
    if (disponibilidad.status !== 404) throw new Error(`Sandbox no disponible: HTTP ${disponibilidad.status}`);
    // Cada cadena se comprueba por separado antes de la primera escritura.
    const listos = [];
    const cadenasPreparadas = {};
    for (const id of ejecutables) {
      casoActual = id;
      sensorActual = Number(cadenaEfectiva(id, escenario.casos[id], escenario, V).cadena?.sensor_id ?? 0) || null;
      if (id === 'TC-M03-266') { listos.push(id); continue; }
      const preparada = cadenaEfectiva(id, escenario.casos[id], escenario, V);
      const fallo = await verificarCadena(id, preparada, solicitar, tokens.admin);
      if (fallo) r.bloqueos[id].push({ tipo: 'DATOS', motivo: fallo });
      else { cadenasPreparadas[id] = preparada; listos.push(id); }
    }
    if (!listos.length) throw new Error('Ningún subcaso conserva una cadena válida.');
    // Primera petición con X-Test-Run-Id: el ancla precede el NOW() fijo de su transacción.
    r.plan_temporal = planTemporalIngestas(listos);
    abierto = true;
    const apertura = await solicitar('GET', '/usuarios/me', { token: tokens.prod, enRun: true });
    if (apertura.status !== 200 || apertura.eco !== runId) throw new Error('El RUN no devolvió su cabecera de aislamiento.');
    guardar();
    await ejecutarCasosYFaseUi({ r, listos, cadenasPreparadas, faseUi,
      ctx: { r, solicitar, tokens, run, dir, secretos, previos, lecturas, V, contrato,
        planTemporal: r.plan_temporal, detenerSolicitudes: () => { peticionCancelada = true; } },
      seleccionarCaso: (id, c) => { casoActual = id;
        sensorActual = Number(c?.cadena?.sensor_id ?? (id === 'TC-M03-266' ? V.QA_G88_266_SENSOR_ID : 0)) || null; },
      guardar, interrumpido: () => peticionCancelada,
      antesDeCypress: async () => {
        if (!faseUi.ingesta180Acreditada) return;
        casoActual = 'TC-M03-180';
        sensorActual = 737;
        const ruta = '/configuracion/sensores/737/asociaciones';
        const inicioDiagnostico = Date.now();
        try {
          const x = await solicitar('GET', ruta, { token: tokens.admin });
          r.bitacora.push({ caso: 'TC-M03-180', etapa: 'DIAGNOSTICO_ASOCIACION_NO_BLOQUEANTE',
            ruta, latencia_ms: Date.now() - inicioDiagnostico, http: x.status,
            asociacion_522_vigente: x.status === 200
              ? asociacionVigente(x.json, 522, 349) : null });
        } catch (e) {
          r.bitacora.push({ caso: 'TC-M03-180', etapa: 'DIAGNOSTICO_ASOCIACION_NO_BLOQUEANTE',
            ruta, latencia_ms: Date.now() - inicioDiagnostico, error: sanearArtefacto(String(e.message), secretos) });
        }
      } });
  } catch (e) { r.problemas_tecnicos.push(e.message); }
  finally {
     if (peticionCancelada && !r.parada_seguridad) r.parada_seguridad = {
       causa: 'PARADA_SEGURIDAD_SESION_COMPARTIDA', caso: casoActual,
       peticion: 'NO_IDENTIFICADA', ruta: 'NO_IDENTIFICADA', latencia_ms: null,
       motivo: 'Petición o proceso cancelado; la sesión compartida puede seguir ocupada.', casos_pendientes: [] };
    casoActual = null;
    sensorActual = null;
    try { consolidarNewman(dir, r); } catch (e) { r.problemas_tecnicos.push(`Newman consolidado: ${e.message}`); }
    try { await cerrar(); } catch (e) { r.problemas_tecnicos.push(`Cierre: ${e.message}`); }
    process.off('SIGINT', interrupcion); process.off('SIGTERM', interrupcion);
    r.fin = new Date().toISOString();
    r.evidencias = r.evidencias.filter((x) => {
      if (x === 'resultado.json') return true;
      const presente = fs.existsSync(path.join(dir, x));
      if (!presente) r.problemas_tecnicos.push(`Evidencia anunciada no encontrada: ${x}`);
      return presente;
    });
    for (const id of ['TC-M03-172', 'TC-M03-180']) {
      const fase = r.cypress.casos[id];
      if (fase?.causa === 'Fase Cypress pendiente.') fase.causa =
        `Fase Cypress no iniciada: ${sanearArtefacto(String(r.problemas_tecnicos.at(-1) ?? 'apertura no completada'), secretos)}`;
    }
     if (r.parada_seguridad) {
       registrarPendientesParada(r, ejecutables);
       r.problemas_tecnicos.push(`PARADA_SEGURIDAD_SESION_COMPARTIDA: ${r.parada_seguridad.caso ?? 'sin caso'} `
         + `${r.parada_seguridad.peticion} ${r.parada_seguridad.ruta}; latencia ${r.parada_seguridad.latencia_ms ?? 'no medida'} ms; ${r.parada_seguridad.motivo}`);
     }
    for (const id of IDS_CASOS) {
      if (!(r.comprobaciones ?? []).some((x) => x.caso === id)) continue;
      if (id === 'TC-M03-266' && !['APROBADO', 'RECHAZADO'].includes(r.resultado266)) continue;
      if (!r.evidencias.some((x) => /^newman\/[^/]+\.json$/.test(x))
        || !r.evidencias.some((x) => /^newman\/[^/]+\.html$/.test(x)))
        r.bloqueos[id].push({ tipo: 'AUTOMATIZACION', motivo: 'Evidencia Newman JSON/HTML incompleta.' });
    }
    for (const id of IDS_CASOS) r.casos[id] = resultadoOficial(id, r.comprobaciones, r.bloqueos[id],
      r.cypress.casos?.[id]?.total_pruebas ?? 0,
      r.hallazgos_producto.filter((x) => x.caso === id), r.evidencias);
    r.incidencias_automatizacion = r.problemas_tecnicos.map((x) => ({ descripcion: x }));
    r.incidencias = derivarIncidencias(r);
     r.estado = r.parada_seguridad || !r.cierre?.rollback?.verificado
       || Object.values(r.casos).some((x) => ['NO_EJECUTADA', 'NO_CONCLUYENTE'].includes(x.estado_tecnico))
       ? 'INTERRUMPIDA' : 'CONCLUIDA';
    r.analisis = r.incidencias.length
      ? `La primera discrepancia se documenta por caso; causa raíz pendiente de investigación con E1-E3/UI.`
      : 'No hay discrepancia funcional comprobada con precondiciones completas.';
    r.accion = [
      Object.values(r.bloqueos).some((xs) => xs.some((x) => x.tipo === 'DATOS')) ? 'Confirmar por GET las cadenas, rangos, calibraciones y nombres UI de cada caso condicionado.' : null,
      !r.cierre?.rollback?.verificado ? 'Escalar la verificación de cierre con asociaciones, dashboard, M09 e historial.' : null,
      r.incidencias.length ? 'Atender las incidencias con su primer equipo y evidencia indicada.' : null,
    ].filter(Boolean).join(' ') || 'Comunicar veredictos y conservar las evidencias del RUN para revisión QA.';
    guardar();
    let texto = generarInforme(r);
    const errores = validarResultadoLocal(r, dir, texto);
    if (errores.length) {
      r.problemas_tecnicos.push(...errores);
      r.incidencias_automatizacion = r.problemas_tecnicos.map((x) => ({ descripcion: x }));
      r.estado = 'INTERRUMPIDA';
      guardar();
      texto = generarInforme(r);
    }
    fs.writeFileSync(path.join(dir, NOMBRE_INFORME(r.version)), texto, { flag: 'wx' });
  }
  return r.estado === 'CONCLUIDA' ? 0 : 5;
}

export async function ejecutarCaso266({ r, solicitar, tokens, run, dir, secretos, lecturas, V, contrato, planTemporal }) {
  const control = { fase: 'SEMILLA_PREEXISTENTE', semilla: {}, umbralId: null, conteos: {} };
  let s;
  try {
    s = await verificarSemillaPreexistente266({ solicitar, token: tokens.admin,
      parametros: { especie_id: V.QA_G88_266_ESPECIE_ID, area_id: V.QA_G88_266_AREA_ID,
        activo_id: V.QA_G88_266_ACTIVO_ID, dispositivo_id: V.QA_G88_266_DISPOSITIVO_ID,
        sensor_id: V.QA_G88_266_SENSOR_ID, asociacion_id: V.QA_G88_266_ASOCIACION_ID,
        calibracion_id: V.QA_G88_266_CALIBRACION_ID, serial: V.QA_G88_266_SERIAL },
      semilla: cargarEscenario().semilla_266, control });
  } catch (e) {
    r.bloqueos['TC-M03-266'].push({ tipo: 'DATOS', motivo: `Semilla preexistente no acreditada: ${e.message}; sin escritura.` });
    return;
  }
  r.bitacora.push({ caso: 'TC-M03-266', semilla_preexistente: 'VERIFICADA_POR_GET', especie_id: s.especie_id,
    area_id: s.area_id, dispositivo_id: s.dispositivo_id, sensor_id: s.sensor_id,
    activo_id: s.activo_id, asociacion_id: s.asociacion_id, calibracion_id: s.calibracion_id });
  await ejecutar266({ solicitar, admin: tokens.admin, productor: tokens.prod,
    broker: V.BROKER_SERVICE_TOKEN, serial: V.QA_G88_266_SERIAL, s, control, r, lecturas, secretos,
    timestampCaptura: planTemporal?.por_ingesta['TC-M03-266:0'], planTemporal,
    conservarSemilla: V.QA_G88_266_CONSERVAR_SEMILLA !== 'NO',
    newmanLectura: ({ esperado }) => {
      const sn = { ...s, serial: V.QA_G88_266_SERIAL, dashboard_infraestructura_id: s.area_id };
      const rep = ejecutarNewman({ id: 'TC-M03-266', checkId: 'API-266-02',
        entrada: { valor: 15, unidad: s.unidad }, s: sn,
        variable: 'TEMPERATURA_AMBIENTAL', run, V, dir, secretos, token: tokens.prod,
        indice: 'lectura-final', esperado, skipIngesta: true });
      r.evidencias.push(...rep.archivos);
      r.herramientas.newman = 'reporte JSON/HTML generado para lectura final 266';
    } });
}

export function datosRegistro(cierre, lecturas) {
  return { cierre: cierre ? { ...cierre, run: { cierre_http: cierre.cierre_http } } : null,
    datos: { ids_telemetria: [...new Set(lecturas.map((x) => Number(x.id_telemetria))
      .filter((x) => Number.isInteger(x) && x > 0))] } };
}

export function registrarPendientesParada(r, ejecutables) {
  if (!r.parada_seguridad) return;
  r.parada_seguridad.casos_pendientes = [];
  for (const id of ejecutables) {
    if (r.bloqueos[id].some((x) => x.tipo === 'DATOS')) continue;
    const pendientes = [...CASOS[id].api, ...CASOS[id].ui].filter((clave) =>
      !r.comprobaciones.some((x) => x.caso === id && x.id === clave
        && ['APROBADO', 'RECHAZADO'].includes(x.estado)));
    if (!pendientes.length && id !== r.parada_seguridad.caso) continue;
    r.parada_seguridad.casos_pendientes.push({ caso: id, comprobaciones: pendientes });
    r.bloqueos[id].push({ tipo: 'PARADA_SEGURIDAD_SESION_COMPARTIDA',
      motivo: `PARADA_SEGURIDAD_SESION_COMPARTIDA; comprobaciones pendientes: ${pendientes.join(', ') || 'cierre del caso'}` });
  }
}

export async function verificarCadena(id, caso, solicitar, token) {
  const s = caso.cadena;
  if (!s || !cadenaLista(caso)) return `${id}: cadena local incompleta.`;
  const leer = (ruta) => solicitar('GET', ruta, { token });
  if (id === 'TC-M03-172') return null;
  const d = await leer(`/configuracion/dispositivos-iot/${s.dispositivo_id}`);
  const dev = d.json?.data ?? d.json;
  if (d.status !== 200 || Number(dev?.id_infraestructura) !== Number(s.infraestructura_id)
    || dev?.serial !== s.serial || dev?.es_activo === false) return 'Dispositivo, serial e infraestructura no coinciden.';
  if (id === 'TC-M03-180' && (dev?.id_dispositivo_gateway != null || dev?.categoria !== 'SENSOR'))
    return 'Dispositivo 357 debe ser de categoría SENSOR y no tener gateway.';
  const i = await leer(`/configuracion/infraestructuras/${s.infraestructura_id}`);
  const infra = i.json?.data ?? i.json;
  if (i.status !== 200 || Number(infra?.especie_id) !== Number(s.especie_id)) return 'Infraestructura y especie no coinciden.';
  const sensores = await leer(`/configuracion/dispositivos-iot/${s.dispositivo_id}/sensores`);
  if (sensores.status !== 200 || !(sensores.json?.items ?? []).some((x) => Number(x.id_sensores) === Number(s.sensor_id)
    && (TEMPERATURA.has(id) ? x.categoria === 'TEMPERATURA'
      : id === 'TC-M03-180' ? x.categoria === 'AMONIACO' && x.nombre === s.sensor_nombre
        : Number(x.id_variable_ambiental) === Number(s.variable_id)) && x.es_activo !== false))
    return 'Sensor no pertenece al dispositivo.';
  const cal = await leer(`/configuracion/sensores/${s.sensor_id}/calibraciones`);
  const calibracion = (cal.json?.items ?? []).filter((x) => Number(x.id_dispositivo_iot) === Number(s.dispositivo_id))
    .sort((a, b) => String(b.fecha_calibracion ?? '').localeCompare(String(a.fecha_calibracion ?? '')))[0];
  if (!TEMPERATURA.has(id) && id !== 'TC-M03-180' && calibracion
    && Number(calibracion.id_calibracion) !== Number(s.calibracion_id))
    return 'Calibracion vigente distinta a la semilla.';
  if (cal.status !== 200 || !calibracion || !Number.isFinite(Number(calibracion.ganancia))
    || !Number.isFinite(Number(calibracion.offset ?? calibracion.offset_calibracion)))
    return 'Calibración no acreditada.';
  if (id === 'TC-M03-180' && (Number(calibracion.id_calibracion) !== Number(s.calibracion_id)
    || Number(calibracion.valor_referencia) !== 5 || Number(calibracion.ganancia) !== 1
    || Number(calibracion.offset ?? calibracion.offset_calibracion) !== 0))
    return 'Calibración NH3 debe ser identidad (ganancia 1, offset 0).';
  if (TEMPERATURA.has(id)) s.calibracion_id = calibracion.id_calibracion;
  const variables = await leer('/configuracion/variables-ambientales');
  const candidatas = (variables.json?.items ?? []).filter((x) => x.es_activo !== false
    && String(x.tipo_variable ?? x.nombre ?? '').toUpperCase().replace(/\s+/g, '_') === 'TEMPERATURA_AMBIENTAL');
  if (TEMPERATURA.has(id) && candidatas.length !== 1) return 'Variable Temperatura Ambiental única no acreditada.';
  if (TEMPERATURA.has(id)) { s.variable_id = candidatas[0].id_variable_ambiental; s.unidad = candidatas[0].unidad; }
  const variable = (variables.json?.items ?? []).find((x) => Number(x.id_variable_ambiental) === Number(s.variable_id) && x.es_activo !== false);
  if (variables.status !== 200 || !variable || (id === 'TC-M03-180' && (
    variable.unidad !== 'ppm' || variable.valor_fisico_min == null
    || variable.valor_fisico_max == null || !Number.isFinite(Number(variable.valor_fisico_min))
    || !Number.isFinite(Number(variable.valor_fisico_max)) || caso.entradas.some((x) => {
    const ajustado = x.valor * Number(calibracion.ganancia)
      + Number(calibracion.offset ?? calibracion.offset_calibracion);
    return !Number.isFinite(ajustado) || ajustado < Number(variable.valor_fisico_min) || ajustado > Number(variable.valor_fisico_max);
  })))) return 'Variable o rango físico incompatible con las lecturas y calibración.';
  const as = id === 'TC-M03-180' ? null : await leer(`/configuracion/sensores/${s.sensor_id}/asociaciones`);
  if (id !== 'TC-M03-180' && (as.status !== 200 || !(as.json?.items ?? []).some((x) =>
    x.tiene_estado === true && !x.fecha_finalizacion
      && Number(x.id_infraestructura) === Number(s.dashboard_infraestructura_id))))
    return 'Asociación activa/ID no acreditados.';
  if (id === 'TC-M03-180') {
    const dashboard = await leer(`/iot/monitoreo/dashboard?id_infraestructura=${s.dashboard_infraestructura_id}&por_pagina=50`);
    const previo = (dashboard.json?.sensores ?? []).find((x) => Number(x.id_sensor) === Number(s.sensor_id));
    if (dashboard.status !== 200 || previo?.alertas_activas?.length || previo?.id_alerta)
      return 'Dashboard previo o ausencia de alertas activas no acreditados.';
    // La misma respuesta validada sirve como estado anterior de 180.
    s.dashboard_previo = dashboard.json;
    for (const ruta of [`/iot/alertas?estado=ACTIVA&id_sensor=${s.sensor_id}`,
      '/iot/alertas?estado=ACTIVA&id_activo_biologico=884']) {
      const alertas = await leer(ruta);
      if (alertas.status !== 200 || Number(alertas.json?.total) !== 0)
        return `Alertas activas o consulta no evaluable: ${ruta}.`;
    }
  }
  const u = await leer(`/configuracion/umbrales?id_especie=${s.especie_id}`);
  if (u.status !== 200) return 'Umbrales M09 no consultables.';
  const encontrados = (u.json?.items ?? []).filter((x) => x.es_activo && Number(x.id_variable_ambiental) === Number(s.variable_id));
  if (id === 'TC-M03-180' ? encontrados.length !== 0 : encontrados.length !== 1
      || (!TEMPERATURA.has(id) && Number(encontrados[0].id_umbral_ambiental) !== Number(s.umbral_id)))
    return 'Ausencia/presencia del umbral M09 no coincide con el caso.';
  if (['TC-M03-169', 'TC-M03-170', 'TC-M03-171'].includes(id)
      && !['normal', 'precaucion', 'critico'].every((nivel) => encontrados[0].niveles?.some((x) => x.nivel === nivel)))
    return 'Niveles RF-17 incompletos en umbral existente.';
  if (TEMPERATURA.has(id)) s.umbral_id = encontrados[0].id_umbral_ambiental;
  return null;
}

export async function ejecutarCasosYFaseUi({ r, listos, cadenasPreparadas, faseUi, ctx,
  seleccionarCaso = () => {}, guardar = () => {}, antesDeCypress = async () => {},
  interrumpido = () => false,
  ejecutarCasoFn = ejecutarCaso, ejecutarCaso266Fn = ejecutarCaso266,
  ejecutar172 = ejecutarUi172, ejecutar180 = ejecutarUi180 }) {
  for (const id of listos) {
    const c = cadenasPreparadas[id];
    seleccionarCaso(id, c);
    try {
      if (id === 'TC-M03-266') await ejecutarCaso266Fn(ctx);
      else await ejecutarCasoFn(id, c, { ...ctx, faseUi });
    } catch (e) {
      const error = sanearArtefacto(String(e.message ?? e), ctx.secretos ?? []);
      const tipo = /aborted due to timeout/i.test(error) ? 'ORIGEN_INDETERMINADO' : 'AUTOMATIZACION';
      if (/timeout|aborted|cancelad/i.test(error)) ctx.detenerSolicitudes?.();
      r.bloqueos[id].push({ tipo, motivo: `Error del subcaso: ${error}` });
      r.problemas_tecnicos.push(`${id}: ${error}`);
      if (id === 'TC-M03-180' && !faseUi.ingesta180Acreditada)
        faseUi.motivo180 = `Ingesta NH3 no acreditada: ${error}`;
    }
    guardar();
    if (interrumpido()) throw new Error('Petición cancelada: se omiten solicitudes posteriores hasta cerrar el RUN.');
  }
  await antesDeCypress();
  if (interrumpido()) throw new Error('Petición cancelada antes de Cypress: se cierra el RUN.');
  await ejecutarFaseCypress({ r, listos, cadenasPreparadas, faseUi, ctx, ejecutar172, ejecutar180 });
  guardar();
}

async function ejecutarCaso(id, c, ctx) {
  const { r, solicitar, tokens, run, dir, secretos, previos, lecturas, V, planTemporal } = ctx;
  const s = c.cadena;
  secretos.push(s.serial, s.sensor_nombre);
  if (id === 'TC-M03-172') {
    const rep = ejecutarNewman({ id, checkId: 'API-172-A', entrada: {}, s, variable: c.variable,
        run, V, dir, secretos, token: tokens.prod, tokenAdmin: tokens.admin, soloUmbrales: true,
        indice: 'consulta', esperado: '' });
      r.evidencias.push(...rep.archivos);
      r.herramientas.newman = 'reporte JSON/HTML generado';
      const ex = rep.bruto.run?.executions?.find((x) => x.request?.method === 'GET');
      let umbrales = [];
      try { umbrales = JSON.parse(Buffer.from(ex.response?.stream?.data ?? []).toString('utf8')).items ?? []; }
      catch { /* respuesta no evaluable */ }
      const sinT = ex?.response?.code === 200 && ausenciaT(umbrales);
      r.comprobaciones.push({ caso: id, id: 'API-172-A', fuente: 'API', tipo: 'ASSERT',
        estado: sinT ? 'RECHAZADO' : 'NO_CONCLUYENTE', naturaleza: sinT ? 'PRODUCTO' : null,
        observado: `HTTP ${ex?.response?.code ?? 'sin respuesta'}; campos umbral/niveles=${JSON.stringify(camposUmbral(umbrales))}; ausencia T=${sinT}` });
    return;
  }
  const anterior = { caso: id,
    ruta_asociaciones: `/configuracion/sensores/${s.sensor_id}/asociaciones`,
    ruta_dashboard: `/iot/monitoreo/dashboard?id_infraestructura=${s.dashboard_infraestructura_id}&por_pagina=50`,
    ruta_umbral: `/configuracion/umbrales?id_especie=${s.especie_id}` };
  for (const [campo, ruta] of [['asociaciones', anterior.ruta_asociaciones], ['dashboard', anterior.ruta_dashboard], ['umbral', anterior.ruta_umbral]]) {
    if (id === 'TC-M03-180' && campo === 'asociaciones') continue;
    const x = id === 'TC-M03-180' && campo === 'dashboard' && s.dashboard_previo
      ? { status: 200, json: s.dashboard_previo }
      : await solicitar('GET', ruta, { token: tokens.admin });
    if (x.status !== 200) throw new Error(`Estado anterior ${campo} HTTP ${x.status}`);
    anterior[campo] = x.json;
  }
  if (id === 'TC-M03-180') delete anterior.ruta_asociaciones;
  // El rollback devuelve el estado previo al RUN, no los estados intermedios de otros subcasos.
  const { umbral: umbralParaEntradas, dashboard: dashboardActual } = conservarAnterior(previos, anterior);
  if (id === 'TC-M03-266') throw new Error('SEGURIDAD_M09: 266 bloqueado por propagacion Edge.');
  let notificacionesAntes = null;
  if (id === 'TC-M03-180') notificacionesAntes = await solicitar('GET', '/notificaciones?tamano=50', { token: tokens.admin, enRun: true });
  let entradas = c.entradas;
  if (['TC-M03-169', 'TC-M03-170', 'TC-M03-171'].includes(id)) {
    const u = (umbralParaEntradas?.items ?? []).find((x) => x.es_activo && Number(x.id_variable_ambiental) === Number(s.variable_id));
    if (u && !ausenciaT([u])) {
      r.bloqueos[id].push({ tipo: 'DATOS', motivo: 'TEST expone T configurable; nueva preparacion requerida para 169-171.' });
      return;
    }
    const vr = await solicitar('GET', '/configuracion/variables-ambientales', { token: tokens.admin });
    const v = (vr.json?.items ?? []).find((x) => Number(x.id_variable_ambiental) === Number(s.variable_id));
    const cr = await solicitar('GET', `/configuracion/sensores/${s.sensor_id}/calibraciones`, { token: tokens.admin });
    const cal = (cr.json?.items ?? []).filter((x) => Number(x.id_dispositivo_iot) === Number(s.dispositivo_id))
      .sort((a, b) => String(b.fecha_calibracion ?? '').localeCompare(String(a.fecha_calibracion ?? '')))[0];
    if (!u || !v || !cal || vr.status !== 200 || cr.status !== 200) throw new Error('Configuracion existente incompleta.');
    const derivadas = derivarEntradas(Number(u.valor_min), Number(u.valor_max), Number(v.valor_fisico_min), Number(v.valor_fisico_max), Number(v.precision_decimal ?? 2));
    const gain = Number(cal.ganancia), offset = Number(cal.offset);
    entradas = derivadas.entradas.filter((e) => e.clave.startsWith(id.slice(-3))).map((e) => {
      const ajuste = invertirCalibracion(e.valor, gain, offset, Number(v.valor_fisico_min),
        Number(v.valor_fisico_max), derivadas.decimales);
      return { ...e, valor_enviado: ajuste.valor_enviado, preparable: e.preparable && ajuste.preparable,
        motivo: !ajuste.preparable ? 'Calibracion, rango fisico o precision impide el valor objetivo.' : e.motivo };
    });
    r.bitacora.push({ caso: id, sustitucion_datos: 'Umbral M09 existente', min: derivadas.min, max: derivadas.max,
      T: derivadas.T, calibracion: 'valor_objetivo = entrada * ganancia + offset',
      niveles: (u.niveles ?? []).map((n) => ({ nivel: n.nivel, limite_inferior: n.limite_inferior,
        limite_superior: n.limite_superior })),
      alertas_activas_antes: (dashboardActual?.sensores ?? [])
        .find((x) => Number(x.id_sensor) === Number(s.sensor_id))?.alertas_activas
        ?.map((a) => ({ id_alerta: a.id_alerta ?? null, severidad: a.severidad ?? null,
          estado: a.estado ?? null })) ?? [], entradas });
  }
  const check = { 'TC-M03-169': ['API-169-02', 'API-169-03', 'API-169-04'],
    'TC-M03-170': ['API-170-02', 'API-170-03', 'API-170-04', 'API-170-05'],
    'TC-M03-171': ['API-171-02', 'API-171-03'],
    'TC-M03-180': ['API-180-02'], 'TC-M03-266': ['API-266-01'] }[id];
  const temperatura = ['TC-M03-169', 'TC-M03-170', 'TC-M03-171'].includes(id);
  const semilla = temperatura ? cargarEscenario().semilla_169_171 : null;
  if (temperatura) {
    const activos = await solicitar('GET', `/activos-biologicos?id_infraestructura=${semilla.area}&page_size=100`, { token: tokens.admin });
    const unico = activos.status === 200
      ? activoUnicoVinculable(activos.json, semilla.area, semilla.activo_vinculable.id)
      : { ok: false, motivo: `GET activos del área HTTP ${activos.status}.` };
    if (!unico.ok) r.hallazgos_producto.push({ caso: id, tipo: 'HALLAZGO_PRODUCTO',
      descripcion: 'Unicidad del activo RF-61-A no acreditada', evidencia: 'GET /activos-biologicos',
      observado: unico.motivo, certeza: 'NO DETERMINADA', nota: 'No condiciona el veredicto RF-58.' });
    r.bitacora.push({ caso: id, precomprobacion_activo: 'UNICO_VINCULABLE',
      area_id: semilla.area, activo_id: semilla.activo_vinculable.id });
  }
  if (id === 'TC-M03-180') {
    if (notificacionesAntes.status !== 200 || !Array.isArray(notificacionesAntes.json?.items)) {
      r.bloqueos[id].push({ tipo: 'AUTOMATIZACION', motivo: 'Línea base de notificaciones del Administrador no consultable.' });
      return;
    }
    const activos = await solicitar('GET', '/activos-biologicos?id_infraestructura=349&page_size=100', { token: tokens.admin });
    const unico = activos.status === 200
      ? activoUnicoVinculable(activos.json, 349, 884)
      : { ok: false, motivo: `GET activos del área HTTP ${activos.status}.` };
    if (!unico.ok) r.hallazgos_producto.push({ caso: id, tipo: 'HALLAZGO_PRODUCTO',
      descripcion: 'Unicidad del activo RF-61-A no acreditada', evidencia: 'GET /activos-biologicos',
      observado: unico.motivo, certeza: 'NO DETERMINADA', nota: 'No condiciona el veredicto RF-58.' });
    // Última compuerta, inmediatamente antes del único POST oficial.
    const umbrales = await solicitar('GET', '/configuracion/umbrales?id_especie=126', { token: tokens.admin });
    if (umbrales.status !== 200 || !Array.isArray(umbrales.json?.items)) {
      r.bloqueos[id].push({ tipo: 'AUTOMATIZACION', motivo: 'GET umbrales previo a ingesta no evaluable.' });
      return;
    }
    const activosNh3 = umbralesActivos180(umbrales.json.items);
    r.bitacora.push({ caso: id, pre_ingesta_umbrales_activos_nh3: activosNh3.length,
      especie_id: 126, variable_id: 11 });
    if (activosNh3.length) {
      r.bloqueos[id].push({ tipo: 'DATOS', motivo: `Sin ingesta NH3: ${activosNh3.length} umbral(es) activo(s) para especie 126, variable 11.` });
      return;
    }
  }
  for (let n = 0; n < entradas.length; n++) {
    const e = entradas[n];
    if (!e.preparable && id !== 'TC-M03-180') {
      r.comprobaciones.push({ caso: id, id: check[n], fuente: 'API', tipo: 'PRE', estado: 'NO_EJECUTADO',
        observado: e.motivo });
      continue;
    }
    const rep = ejecutarNewman({ id, checkId: check[n], entrada: e, s, variable: c.variable, run, V, dir, secretos, token: tokens.prod,
      indice: n, timestampCaptura: planTemporal?.por_ingesta[`${id}:${n}`],
      esperado: id === 'TC-M03-266' ? e.esperado_inicial : id === 'TC-M03-180' ? '' : e.esperado });
    if (id === 'TC-M03-180') {
      const post = rep.bruto.run?.executions?.find((x) => x.request?.method === 'POST');
      let cuerpo = {};
      try { cuerpo = JSON.parse(Buffer.from(post?.response?.stream?.data ?? []).toString('utf8')); } catch { /* respuesta no evaluable */ }
      ctx.faseUi.ingesta180Acreditada = post?.response?.code === 201
        && Number.isInteger(cuerpo.id_telemetria) && cuerpo.estado_calidad === 'LECTURA_VALIDA';
      ctx.faseUi.motivo180 = ctx.faseUi.ingesta180Acreditada ? null
        : `Ingesta NH3 no acreditada: HTTP ${post?.response?.code ?? 'sin respuesta'}; lectura válida=${cuerpo.estado_calidad === 'LECTURA_VALIDA'}.`;
    }
    r.herramientas.newman = 'reporte JSON generado';
    registrarNewman(rep, id, r, lecturas, s.sensor_id);
    if (id === 'TC-M03-180') {
      if (rep.observado?.id_alerta || rep.observado?.alertas_activas?.length
        || rep.observado?.dato_desactualizado) {
        const motivo = 'Lectura NH3 contaminada por alerta activa o dato desactualizado.';
        for (const comprobacion of r.comprobaciones.filter((x) => x.caso === id
          && ['API-180-01', 'API-180-02', 'API-180-03'].includes(x.id))) {
          comprobacion.estado = 'NO_CONCLUYENTE';
          comprobacion.naturaleza = 'DATOS';
          comprobacion.observado = motivo;
        }
        r.bitacora.push({ caso: id, motivo });
        return;
      }
      const post = rep.bruto.run?.executions?.find((x) => x.request?.method === 'POST');
      let telemetriaId = null;
      try { telemetriaId = JSON.parse(Buffer.from(post.response?.stream?.data ?? []).toString('utf8')).id_telemetria; }
      catch { /* La aserción PRE de Newman conserva el error real. */ }
      let vinculo = { ok: false, motivo: 'Ingesta NH3 sin id_telemetria comprobable.' };
      if (Number.isInteger(telemetriaId)) {
        const res = await solicitar('GET', `/iot/vinculaciones?id_telemetria=${telemetriaId}`, { token: tokens.admin });
        vinculo = res.status === 200
          ? lecturaVinculada(res.json, telemetriaId, 884, 349)
          : { ok: false, motivo: `GET vinculación HTTP ${res.status}.` };
        if (res.status === 404 || res.status === 405) {
          const { inicio, fin } = rangoHistorial();
          const hist = await solicitar('GET', `/iot/monitoreo/historial?sensor_id=${s.sensor_id}&fecha_inicio=${inicio}&fecha_fin=${fin}`, { token: tokens.admin });
          vinculo = hist.status === 200
            ? lecturaVinculadaHistorial(hist.json, telemetriaId, 884, s.sensor_id)
            : { ok: false, motivo: `GET historial HTTP ${hist.status}.` };
        }
      }
      r.bitacora.push({ caso: id, id_telemetria: telemetriaId,
        vinculo_884: vinculo.ok ? 'VINCULADA' : 'NO_CONCLUYENTE', motivo: vinculo.motivo });
      if (!vinculo.ok) r.hallazgos_producto.push({ caso: id, tipo: 'HALLAZGO_PRODUCTO',
        descripcion: 'Lectura sin vinculación RF-61-A pese a activo único vinculable',
        evidencia: 'GET /iot/vinculaciones', observado: vinculo.motivo,
        certeza: 'PROBABLE', nota: 'Posible defecto sujeto a RF-61-A; no condiciona el veredicto RF-58.' });
    }
    if (temperatura) {
      const post = rep.bruto.run?.executions?.find((x) => x.request?.method === 'POST');
      let telemetriaId = null;
      try { telemetriaId = JSON.parse(Buffer.from(post.response?.stream?.data ?? []).toString('utf8')).id_telemetria; }
      catch { /* ingesta sin ID: su PRE Newman conserva el fallo */ }
      let vinculo = { ok: false, motivo: 'Ingesta sin id_telemetria comprobable.' };
      let fuenteVinculo = 'GET /iot/vinculaciones';
      if (Number.isInteger(telemetriaId)) {
        const res = await solicitar('GET', `/iot/vinculaciones?id_telemetria=${telemetriaId}`, { token: tokens.admin });
        vinculo = res.status === 200
          ? lecturaVinculada(res.json, telemetriaId, semilla.activo_vinculable.id, semilla.area)
          : { ok: false, motivo: `GET vinculación HTTP ${res.status}; lectura ${telemetriaId} no acreditada.` };
        if (res.status === 404 || res.status === 405) {
          const { inicio, fin } = rangoHistorial();
          const ruta = `/iot/monitoreo/historial?sensor_id=${s.sensor_id}&fecha_inicio=${inicio}&fecha_fin=${fin}`;
          const hist = await solicitar('GET', ruta, { token: tokens.admin });
          fuenteVinculo = 'GET historial por lectura (ruta de vinculaciones no disponible)';
          vinculo = hist.status === 200
            ? lecturaVinculadaHistorial(hist.json, telemetriaId, semilla.activo_vinculable.id, s.sensor_id)
            : { ok: false, motivo: `GET historial HTTP ${hist.status}; lectura ${telemetriaId} no acreditada.` };
        }
      }
      r.bitacora.push({ caso: id, entrada: e.clave, id_telemetria: telemetriaId,
        vinculo_884: vinculo.ok ? 'VINCULADA' : 'NO_CONCLUYENTE', fuente: fuenteVinculo, motivo: vinculo.motivo });
      if (!vinculo.ok) r.hallazgos_producto.push({ caso: id, entrada: e.clave,
        tipo: 'HALLAZGO_PRODUCTO', descripcion: 'Lectura sin vinculación RF-61-A pese a activo único vinculable',
        evidencia: fuenteVinculo, observado: vinculo.motivo, certeza: 'PROBABLE',
        nota: 'Posible defecto sujeto al requisito RF-61-A; no condiciona el veredicto RF-58.' });
    }
    r.alertas_activas_observadas.push({ caso: id, sensor_id: s.sensor_id, entrada: n,
      id_alerta: rep.observado?.id_alerta ?? null, severidad_alerta: rep.observado?.severidad_alerta ?? null,
      alertas_activas: (rep.observado?.alertas_activas ?? []).map((a) => typeof a === 'object'
        ? { id_alerta: a.id_alerta ?? null, severidad: a.severidad ?? null, estado: a.estado ?? null } : a) });
    if (!rep.htmlGenerado) {
      r.bloqueos[id].push({ tipo: 'AUTOMATIZACION', motivo: 'Newman no produjo HTML real.' });
      r.problemas_tecnicos.push(`${id}: reporte HTML de Newman ausente.`);
    }
    if (rep.calidad && rep.calidad !== 'LECTURA_VALIDA')
      r.bitacora.push({ caso: id, indice: n, estado_calidad: rep.calidad,
        nota: 'REF-G87-01: discrepancia observable frente al oráculo; conservar lectura anterior y semáforo observado.' });
  }
  if (id === 'TC-M03-180') {
    const despues = await solicitar('GET', '/notificaciones?tamano=50', { token: tokens.admin, enRun: true });
    if (despues.status !== 200 || !Array.isArray(despues.json?.items)) {
      r.bloqueos[id].push({ tipo: 'AUTOMATIZACION', motivo: 'GET notificaciones posterior no evaluable.' });
      return;
    }
    const anteriores = new Set((notificacionesAntes.json?.items ?? []).map((x) => x.id_notificacion));
    const nuevasUmbral = (despues.json?.items ?? []).filter((x) => !anteriores.has(x.id_notificacion)
      && /umbral/i.test(String(x.mensaje ?? ''))
      && (/nh3|amon[ií]aco/i.test(String(x.mensaje ?? ''))
        || Number(x.id_sensor) === Number(s.sensor_id) || Number(x.id_variable_ambiental) === 11));
    r.comprobaciones.push({ caso: id, id: 'API-180-04', fuente: 'API', tipo: 'ASSERT',
      estado: nuevasUmbral.length > 0 ? 'APROBADO' : 'RECHAZADO', naturaleza: 'PRODUCTO',
      observado: `Nuevas notificaciones sobre umbral=${nuevasUmbral.length}; HTTP ${despues.status}` });
  }
}

function ejecutarNewman({ id, checkId, entrada, s, variable, run, V, dir, secretos, token, tokenAdmin,
                         indice, esperado, timestampCaptura, skipIngesta = false, soloUmbrales = false }) {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'g88-newman-'));
  try {
    const variables = { qa_autorizado: 'SI', base_url: API, run_id: run.id, sandbox_secret: run.secreto,
      broker_service_token: V.BROKER_SERVICE_TOKEN, tok_prod: token, tok_admin: tokenAdmin ?? '',
      especie_id: s.especie_id, solo_umbrales: soloUmbrales ? 'SI' : 'NO', caso: id, check_id: checkId,
      skip_ingesta: skipIngesta ? 'SI' : 'NO', device_id: s.dispositivo_id, sensor_id: s.sensor_id,
      id_infraestructura: s.dashboard_infraestructura_id, tipo_variable: variable,
      valor: entrada.valor_enviado ?? entrada.valor, esperado_valor: entrada.valor, esperado_estado: esperado,
      esperado_unidad: entrada.unidad ?? s.unidad ?? '', unidad: entrada.unidad ?? s.unidad,
      timestamp_captura_ingesta: timestampCaptura ?? '',
      cuerpo_ingesta: cuerpoOpcionalNewman({ soloUmbrales, skipIngesta, parametros: { deviceId: s.dispositivo_id,
        sensorId: s.sensor_id, tipoVariable: variable, valor: entrada.valor_enviado ?? entrada.valor,
        unidad: entrada.unidad ?? s.unidad,
        timestampCaptura,
        serial: s.serial } }) };
    const env = path.join(tmp, 'env.json');
    fs.writeFileSync(env, json({ values: Object.entries(variables).map(([key, value]) => ({ key, value: String(value ?? ''), enabled: true })) }), { mode: 0o600 });
    const rep = path.join(tmp, 'report.json'); const html = path.join(tmp, 'report.html');
    const cmd = spawnSync('newman', ['run', COLECCION, '-e', env, '--reporters', 'json,htmlextra',
      '--reporter-json-export', rep, '--reporter-htmlextra-export', html,
      '--reporter-htmlextra-skipHeaders', 'Authorization,X-Sandbox-Secret',
      '--reporter-htmlextra-skipEnvironmentVars', 'sandbox_secret,broker_service_token,tok_prod,cuerpo_ingesta',
      '--timeout-request', '30000', '--color', 'off'], { encoding: 'utf8', shell: process.platform === 'win32', timeout: 120000 });
    if (!fs.existsSync(rep)) throw new Error(`Newman sin reporte: ${cmd.status ?? 'sin salida'}`);
    const bruto = JSON.parse(fs.readFileSync(rep, 'utf8'));
    const destino = path.join(dir, 'newman'); fs.mkdirSync(destino, { recursive: true });
    const base = `newman-${id}-${indice}`;
    fs.writeFileSync(path.join(destino, `${base}.json`), sanearArtefacto(fs.readFileSync(rep, 'utf8'), secretos));
    const htmlGenerado = fs.existsSync(html);
    if (htmlGenerado) {
      const respaldos = respaldosHtmlNewman.get(dir) ?? [];
      respaldos.push([`${base}.html`, sanearArtefacto(fs.readFileSync(html, 'utf8'), secretos)]);
      respaldosHtmlNewman.set(dir, respaldos);
    }
    let calidad = null;
    let observado = null;
    for (const ex of bruto.run?.executions ?? []) if (ex.request?.method === 'POST') {
      try { calidad = JSON.parse(Buffer.from(ex.response?.stream?.data ?? []).toString('utf8')).estado_calidad; } catch { /* incompleto */ }
    }
    for (const ex of bruto.run?.executions ?? []) if (ex.request?.method === 'GET') {
      try { observado = JSON.parse(Buffer.from(ex.response?.stream?.data ?? []).toString('utf8')).sensores
        ?.find((x) => Number(x.id_sensor) === Number(s.sensor_id)) ?? null; } catch { /* incompleto */ }
    }
    const post = bruto.run?.executions?.find((x) => x.request?.method === 'POST');
    let timestampEnviado = null;
    if (post) try { timestampEnviado = JSON.parse(post.request?.body?.raw).timestamp_captura ?? null; }
    catch { /* El reporte no permite acreditar el cuerpo efectivamente enviado. */ }
    return { bruto, calidad, observado, checkId, infraestructuraId: s.dashboard_infraestructura_id,
      lecturaEnviada: { id_sensor: s.sensor_id, valor: entrada.valor,
        timestamp_captura: timestampEnviado },
      htmlGenerado, archivos: [`newman/${base}.json`] };
  } finally { fs.rmSync(tmp, { recursive: true, force: true }); }
}

function registrarNewman(rep, id, r, lecturas, sensorId) {
  r.evidencias.push(...rep.archivos);
  if (rep.bruto.run?.executions?.some((x) => x.request?.method === 'POST')) {
    r.bitacora.push({ caso: id, comprobacion: rep.checkId,
      timestamp_captura_enviado: rep.lecturaEnviada.timestamp_captura,
      ancla_temporal: r.plan_temporal?.ancla ?? null,
      inicio_run: r.plan_temporal?.inicio_run ?? null });
    if (!rep.lecturaEnviada.timestamp_captura) {
      const motivo = 'Newman no expuso el timestamp del POST enviado.';
      r.problemas_tecnicos.push(`${id}: ${motivo}`);
      r.bloqueos[id].push({ tipo: 'AUTOMATIZACION', motivo });
    }
  }
  let idTelemetria = null;
  for (const ex of rep.bruto.run?.executions ?? []) if (ex.request?.method === 'POST') {
    try { idTelemetria = JSON.parse(Buffer.from(ex.response?.stream?.data ?? []).toString('utf8')).id_telemetria; }
    catch { /* PRE Newman conserva la respuesta no evaluable. */ }
  }
  for (const ex of rep.bruto.run?.executions ?? []) {
    const cuerpo = (() => { try { return JSON.parse(Buffer.from(ex.response?.stream?.data ?? []).toString('utf8')); } catch { return {}; } })();
    if (ex.request?.method === 'GET' && !r.comprobaciones.some((x) => x.caso === id && x.id === `API-${id.slice(-3)}-01`)
      && id !== 'TC-M03-266') {
      const sensor = cuerpo.sensores?.find((x) => Number(x.id_sensor) === Number(sensorId));
      r.respuestas.push({ caso: id, ruta: `/iot/monitoreo/dashboard?id_infraestructura=${rep.infraestructuraId}&por_pagina=50`,
        http: ex.response?.code ?? null, id_telemetria_run: idTelemetria,
        cuerpo: respuestaSaneada('/iot/monitoreo/dashboard?', cuerpo, [sensorId]) });
      const etiqueta180 = sensor?.etiqueta ?? sensor?.etiqueta_estado ?? sensor?.etiqueta_semaforo;
      const etiqueta180Expuesta = sensor && ['etiqueta', 'etiqueta_estado', 'etiqueta_semaforo']
        .some((campo) => Object.hasOwn(sensor, campo));
      const sinRespuesta = ex.response?.code == null;
      if (sinRespuesta) r.problemas_tecnicos.push(`${id}: GET dashboard de Newman sin respuesta; no acredita defecto funcional.`);
      r.comprobaciones.push({ caso: id, id: `API-${id.slice(-3)}-01`, fuente: 'API', tipo: 'ASSERT',
        estado: sinRespuesta ? 'ERROR_QA' : ex.response?.code === 200 && sensor ? 'APROBADO' : 'RECHAZADO',
        naturaleza: sinRespuesta ? null : 'PRODUCTO',
        observado: `HTTP ${ex.response?.code ?? 'sin respuesta'}; sensor presente=${!!sensor}` });
      if (id === 'TC-M03-180') r.comprobaciones.push({ caso: id, id: 'API-180-03', fuente: 'API', tipo: 'ASSERT',
        estado: sinRespuesta ? 'ERROR_QA' : sensor?.estado_semaforo === 'GRIS'
          && (!etiqueta180Expuesta || etiqueta180 === 'Sin umbral configurado')
          ? 'APROBADO' : 'RECHAZADO', naturaleza: sinRespuesta ? null : 'PRODUCTO',
        observado: `estado_semaforo=${sensor?.estado_semaforo ?? 'ausente'}; etiqueta=${etiqueta180 ?? 'no expuesta por API'}` });
    }
    if (ex.request?.method === 'POST' && Number.isInteger(cuerpo.id_telemetria)) {
      const { inicio, fin } = rangoHistorial();
      lecturas.push({ caso: id, sensor_id: sensorId, id_telemetria: cuerpo.id_telemetria, fecha_inicio: inicio, fecha_fin: fin });
    }
    for (const a of ex.assertions ?? []) {
      const m = /^\[(TC-M03-\d+)\]\[(PRE|ASSERT)\]\[([\w-]+)\]/.exec(a.assertion ?? '');
      if (!m) continue;
      r.comprobaciones.push({ caso: m[1], tipo: m[2], id: m[3], fuente: 'API',
        estado: a.error ? (ex.response?.code == null ? 'ERROR_QA' : m[2] === 'PRE' ? 'BLOQUEADO' : 'RECHAZADO') : 'APROBADO',
        naturaleza: a.error ? (ex.response?.code == null ? null : m[2] === 'PRE' ? 'DATOS' : 'PRODUCTO') : null,
        observado: a.error?.message ?? `HTTP ${ex.response?.code ?? 'sin respuesta'}; ${JSON.stringify({ ultimo_valor: cuerpo.sensores?.find((x) => Number(x.id_sensor) === Number(sensorId))?.ultimo_valor,
          estado_semaforo: cuerpo.sensores?.find((x) => Number(x.id_sensor) === Number(sensorId))?.estado_semaforo })}` });
    }
  }
  if (idTelemetria && id !== 'TC-M03-266') {
    const lectura = { ...rep.lecturaEnviada, id_telemetria: idTelemetria };
    const coincide = lecturaDelRun(rep.observado, lectura);
    r.bitacora.push({ caso: id, id_telemetria: idTelemetria, dashboard_lectura_del_run: coincide,
      timestamp_captura: lectura.timestamp_captura, valor: lectura.valor });
    if (!coincide) r.bitacora.push({ caso: id, id_telemetria: idTelemetria,
      nota: 'La falta de correspondencia exacta del dashboard es evidencia contextual; evaluar el estado observado contra el oráculo.' });
  }
}

export function conservarCypress(r, dir, id, res, secretos = []) {
  const carpeta = path.join(dir, 'cypress');
  fs.mkdirSync(carpeta, { recursive: true });
  const base = id.replace('TC-M03-', 'UI-');
  const resumen = { caso: id, status: res.status, exit_code: res.exit_code,
    total_pruebas: res.total_pruebas, fallidas: res.fallidas, timeout: res.timeout,
    motivo: res.motivo, duracion_ms: res.duracion_ms, runs: res.runs };
  fs.writeFileSync(path.join(carpeta, `${base}.json`), sanearArtefacto(json(resumen), secretos));
  const lineas = [`${id} Cypress ${res.status ?? 'sin estado'}`, `exit=${res.exit_code ?? 'sin código'}; pruebas=${res.total_pruebas ?? 0}; fallidas=${res.fallidas ?? 0}`,
    ...((res.runs ?? []).flatMap((x) => x.tests ?? []).map((t) => `${(t.title ?? []).join(' > ')}: ${t.state}; ${t.displayError ?? ''}`)),
    res.motivo ?? ''];
  fs.writeFileSync(path.join(carpeta, `${base}.log`), sanearArtefacto(lineas.join('\n'), secretos));
  for (const ext of ['json', 'log']) r.evidencias.push(`cypress/${base}.${ext}`);
  for (const archivo of fs.readdirSync(carpeta, { recursive: true }))
    if (archivo.endsWith('.png') || /^UI-(?:172|180)-(?:operaciones|solicitudes|login-error|excepciones)\.json$/.test(archivo)) {
      const ruta = `cypress/${archivo.replaceAll('\\', '/')}`;
      if (!r.evidencias.includes(ruta)) r.evidencias.push(ruta);
    }
}

async function ejecutarUi180(ctx, s) {
  const { r, dir, V, run, secretos } = ctx;
  const chrome = (ctx.chromeLocalFn ?? chromeLocal)();
  if (!chrome.disponible) { r.problemas_tecnicos.push(`Cypress: ${chrome.motivo}`); return { noEjecutado: true, motivo: chrome.motivo }; }
  const capturas = path.join(dir, 'cypress');
  const res = await (ctx.ejecutarCypressFn ?? ejecutarCypressControlado)({ timeoutMs: TIMEOUT_UI_MS, opciones: {
    config: { baseUrl: FRONT, specPattern: 'g88.cy.js', screenshotsFolder: capturas,
      downloadsFolder: capturas,
      screenshotOnRunFailure: true, trashAssetsBeforeRuns: false, retries: 0, defaultCommandTimeout: 15000, responseTimeout: 30000 },
    env: { AUTORIZADO_RUN: 'SI', RUN_ID: run.id, SANDBOX_SECRET: V.QA_SANDBOX_SECRET, API_BASE: API_FRONT,
      ARTIFACTS_DIR: capturas,
      SENSOR_180_NOMBRE: s.sensor_nombre, ID_INFRA: s.dashboard_infraestructura_id,
      VALOR_180: 5, UNIDAD_180: 'ppm', PROD_EMAIL: V.QA_PROD_UI_EMAIL, PROD_PASSWORD: V.QA_PROD_UI_PASSWORD,
      CHECK_180: 'SI', CHECK_172: 'NO' } } });
  conservarCypress(r, dir, 'TC-M03-180', res, secretos);
  const rutaLogin = path.join(capturas, 'UI-180-login-error.json');
  if (fs.existsSync(rutaLogin)) {
    try {
      const erroresLogin = JSON.parse(fs.readFileSync(rutaLogin, 'utf8'));
      const fallo = erroresLogin.find((x) => x.http && x.http !== 200);
      if (fallo) r.bloqueos['TC-M03-180'].push({ tipo: 'ORIGEN_INDETERMINADO',
        motivo: `Login Productor UI HTTP ${fallo.http} en RUN; cuerpo saneado en cypress/UI-180-login-error.json. Origen QA/sandbox/backend sin confirmar.` });
    } catch (e) { r.problemas_tecnicos.push(`UI-180: login-error.json ilegible: ${e.message}`); }
  }
  if (!r.evidencias.some((x) => /^cypress\/.*TC-M03-180.*\.png$/.test(x)))
    r.bloqueos['TC-M03-180'].push({ tipo: 'AUTOMATIZACION', motivo: 'Cypress no produjo captura real.' });
  const pruebasUi180 = res.runs?.flatMap((x) => x.tests ?? []) ?? [];
  const preUiAprobada = pruebasUi180.some((x) => (x.title?.at(-1) ?? '').includes('[PRE-UI-01]') && x.state === 'passed');
  for (const t of pruebasUi180) {
    const m = /^\[(TC-M03-180)\]\[(PRE|ASSERT)\]\[([\w-]+)\]/.exec(t.title?.at(-1) ?? '');
    if (m) r.comprobaciones.push({ caso: m[1], tipo: m[2], id: m[3], fuente: 'UI',
      estado: t.state === 'passed' ? 'APROBADO' : t.state === 'failed' ? 'RECHAZADO' : 'NO_EJECUTADO',
      naturaleza: t.state === 'failed' && m[2] === 'ASSERT' && preUiAprobada
        && !/HTTP login|expected \d+ to equal 200/i.test(t.displayError ?? '') ? 'PRODUCTO' : null,
      observado: t.displayError ?? t.state });
  }
  return res;
}

async function ejecutarUi172(ctx, s) {
  const { r, dir, V, run, secretos } = ctx;
  if (!s.variable_nombre) {
    r.bloqueos['TC-M03-172'].push({ tipo: 'DATOS', motivo: 'Falta nombre de variable para localizar el formulario M09.' });
    return { noEjecutado: true, motivo: 'Falta nombre de variable para localizar el formulario M09.' };
  }
  const chrome = (ctx.chromeLocalFn ?? chromeLocal)();
  if (!chrome.disponible) { r.problemas_tecnicos.push(`UI-172: ${chrome.motivo}`); return { noEjecutado: true, motivo: chrome.motivo }; }
  const capturas = path.join(dir, 'cypress');
  const res = await (ctx.ejecutarCypressFn ?? ejecutarCypressControlado)({ timeoutMs: TIMEOUT_UI_MS, opciones: {
    config: { baseUrl: FRONT, specPattern: 'g88.cy.js', screenshotsFolder: capturas,
      downloadsFolder: capturas,
      screenshotOnRunFailure: true, trashAssetsBeforeRuns: false, retries: 0, defaultCommandTimeout: 15000, responseTimeout: 30000 },
    env: { AUTORIZADO_RUN: 'SI', RUN_ID: run.id, SANDBOX_SECRET: V.QA_SANDBOX_SECRET, API_BASE: API_FRONT,
      ARTIFACTS_DIR: capturas,
      ADMIN_EMAIL: V.QA_ADMIN_EMAIL, ADMIN_PASSWORD: V.QA_ADMIN_PASSWORD,
      ID_ESPECIE: s.especie_id, VARIABLE_NOMBRE: s.variable_nombre,
      CHECK_172: 'SI', CHECK_180: 'NO' } } });
  conservarCypress(r, dir, 'TC-M03-172', res, secretos);
  const rutaExcepciones = path.join(capturas, 'UI-172-excepciones.json');
  if (fs.existsSync(rutaExcepciones)) {
    try {
      const excepciones = JSON.parse(fs.readFileSync(rutaExcepciones, 'utf8'));
      for (const e of excepciones.filter((x) => x.tipo === 'PROMESA_RECHAZADA_DASHBOARD')) {
        r.hallazgos_producto.push({ caso: 'TC-M03-172', tipo: 'HALLAZGO_PRODUCTO',
          descripcion: 'Promesa rechazada al cargar dashboard inicial RF-28; origen aplicación/intercept sin confirmar, ajena al oráculo T de RF-58',
          observado: `GET ${e.ruta_api}; HTTP ${e.http ?? 'no registrado'}; ruta ${e.ruta_pagina}; navegación M09 ${e.navegacion_m09_verificada ? 'verificada' : 'no verificada'}`,
          nota: 'Excepción registrada en cypress/UI-172-excepciones.json; no decide el veredicto de UI-172.' });
      }
    } catch (e) { r.problemas_tecnicos.push(`UI-172: excepciones.json ilegible: ${e.message}`); }
  }
  const t = res.runs?.flatMap((x) => x.tests ?? []).find((x) => (x.title?.at(-1) ?? '').includes('[UI-172]'));
  const error = t?.displayError ?? '';
  const ausenciaAcreditada = t?.state === 'failed' && /control de T o tolerancia/i.test(error)
    && r.evidencias.some((x) => /TC-M03-172.*\.png$/.test(x));
  r.comprobaciones.push({ caso: 'TC-M03-172', id: 'UI-172', fuente: 'UI', tipo: 'ASSERT',
    estado: ausenciaAcreditada ? 'RECHAZADO' : t?.state === 'passed' ? 'APROBADO' : 'ERROR_QA',
    naturaleza: ausenciaAcreditada ? 'PRODUCTO' : null,
    observado: ausenciaAcreditada ? 'Formulario sin control T/tolerancia; captura real.' : error || t?.state || 'sin prueba' });
  return res;
}

// Fase posterior a todos los casos API: un fallo o timeout de un caso no omite la UI de otro.
export async function ejecutarFaseCypress({ r, listos, cadenasPreparadas, faseUi, ctx,
  ejecutar172 = ejecutarUi172, ejecutar180 = ejecutarUi180 }) {
  r.cypress ??= { total_pruebas: 0 };
  r.cypress.casos ??= {};
  let sesionUiCancelada = false;
  for (const id of ['TC-M03-172', 'TC-M03-180']) {
    if (sesionUiCancelada) {
      r.cypress.casos[id] = { estado: 'NO_EJECUTADO', total_pruebas: 0,
        causa: 'Cypress anterior cancelado por timeout; no se inicia otra sesión antes del cierre.' };
      continue;
    }
    const c = cadenasPreparadas[id];
    const causaCaso = r.bloqueos?.[id]?.map((x) => x.motivo).join('; ');
    const motivo = !listos.includes(id) || !c?.cadena
      ? causaCaso || 'Cadena del caso no acreditada; UI no elegible.'
      : id === 'TC-M03-180' && !faseUi.ingesta180Acreditada
        ? causaCaso || faseUi.motivo180 || 'Ingesta NH3 no acreditada.' : null;
    if (motivo) {
      r.cypress.casos[id] = { estado: 'NO_EJECUTADO', total_pruebas: 0, causa: motivo };
      continue;
    }
    try {
      const inicioUi = Date.now();
      const res = await (id === 'TC-M03-172' ? ejecutar172(ctx, c.cadena) : ejecutar180(ctx, c.cadena));
      if (res?.timeout) {
        sesionUiCancelada = true;
        ctx.detenerSolicitudes?.();
        r.parada_seguridad ??= { causa: 'PARADA_SEGURIDAD_SESION_COMPARTIDA', caso: id,
          peticion: 'CYPRESS', ruta: 'NO_IDENTIFICADA_POR_CYPRESS', latencia_ms: Date.now() - inicioUi,
          motivo: sanearArtefacto(String(res.motivo ?? 'Timeout Cypress'), ctx.secretos ?? []), casos_pendientes: [] };
      }
      if (res?.noEjecutado) {
        r.cypress.casos[id] = { estado: 'NO_EJECUTADO', total_pruebas: 0,
          causa: sanearArtefacto(String(res.motivo), ctx.secretos ?? []) };
        continue;
      }
      const pruebas = res?.runs?.flatMap((x) => x.tests ?? []);
      const total = pruebas?.length
        ? pruebas.filter((x) => (x.title?.at(-1) ?? '').startsWith(`[${id}]`)
          && ['passed', 'failed'].includes(x.state)).length
        : Number(res?.total_pruebas ?? 0);
      r.cypress.total_pruebas += total;
      r.cypress.casos[id] = total > 0 && !res?.timeout && !res?.motivo
        ? { estado: 'EJECUTADO_CON_COMPROBACIONES', total_pruebas: total,
          fallidas: res.fallidas ?? 0 }
        : { estado: 'EJECUTADO_CON_ERROR', total_pruebas: total,
          error: sanearArtefacto(String(res?.motivo ?? 'Cypress no produjo pruebas.'), ctx.secretos ?? []) };
      r.herramientas.cypress = `Chrome headless; ${r.cypress.total_pruebas} pruebas`;
      if (r.cypress.casos[id].estado === 'EJECUTADO_CON_ERROR') {
        r.problemas_tecnicos.push(`${id}: ${r.cypress.casos[id].error}`);
        r.bloqueos[id].push({ tipo: 'AUTOMATIZACION', motivo: `Cypress: ${r.cypress.casos[id].error}` });
      }
    } catch (e) {
      const error = sanearArtefacto(String(e.message ?? e), ctx.secretos ?? []);
      r.cypress.casos[id] = { estado: 'EJECUTADO_CON_ERROR', total_pruebas: 0, error };
      r.problemas_tecnicos.push(`${id}: Cypress ${error}`);
      r.bloqueos[id].push({ tipo: 'AUTOMATIZACION', motivo: `Cypress: ${error}` });
    }
  }
}

async function recuperar(contrato) {
  const V = leerEnv().valores;
  const errores = requerirAmbiente(contrato, V, { recuperar: true });
  if (errores.length) { console.error(`Barrera de recuperación: ${errores.join(' ')}`); return 2; }
  const dir = contrato.directorio;
  const ruta = path.join(dir, 'resultado.json');
  if (!fs.existsSync(ruta)) { console.error('RUN sin resultado.json verificable; no se solicita cierre.'); return 2; }
  const r = JSON.parse(fs.readFileSync(ruta, 'utf8'));
  if (r.run_id !== contrato.runId || r.grupo !== 'TC-M03-G88' || r.version !== contrato.version) return 2;
  const secretos = [V.QA_SANDBOX_SECRET, V.QA_ADMIN_PASSWORD, V.QA_ADMIN_EMAIL,
    ...Object.entries(V).filter(([nombre]) => /^QA_G88_/.test(nombre)).map(([, valor]) => valor)].filter(Boolean);
  let token = null;
  async function solicitar(metodo, rutaApi, { token: t, secreto } = {}) {
    const headers = { Accept: 'application/json' };
    if (t) headers.Authorization = `Bearer ${t}`;
    if (secreto) headers['X-Sandbox-Secret'] = secreto;
    const x = await fetch(API + rutaApi, { method: metodo, headers, redirect: 'manual', signal: AbortSignal.timeout(30000) });
    let body; try { body = await x.json(); } catch { body = null; }
    return { status: x.status, json: body };
  }
  const autenticar = async () => {
    const x = await fetch(API + '/sesiones/', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ correo_electronico: V.QA_ADMIN_EMAIL, contrasena: V.QA_ADMIN_PASSWORD }),
      signal: AbortSignal.timeout(30000) });
    const b = await x.json();
    if (x.status !== 200 || !b.token) throw new Error('Re-login Administrador falló.');
    token = b.token; secretos.push(token); return token;
  };
  const pendiente = ![200, 404].includes(r.cierre?.cierre_http);
  if (!pendiente && r.cierre?.rollback?.verificado) return 0;
  const cierre = await cerrarYVerificar({ runId: contrato.runId.slice(4), secreto: V.QA_SANDBOX_SECRET,
    solicitar, autenticar, anteriores: r.datos_rollback?.anteriores ?? [], lecturas: r.datos_rollback?.lecturas ?? [],
    umbralRun266: r.umbral_run_266,
    solicitarCierre: pendiente, cierrePrevioHttp: r.cierre?.cierre_http ?? null });
  const evidencia = { run_id: contrato.runId, operacion: 'RECUPERAR', referencia: contrato.referencia,
    fecha: new Date().toISOString(), cierre };
  const nombre = `recuperacion-${Date.now()}.json`;
  fs.writeFileSync(path.join(dir, nombre), sanearArtefacto(json(evidencia), secretos), { flag: 'wx' });
  r.cierre = cierre; r.fin = evidencia.fecha;
  if (!cierre.rollback.verificado) {
    r.problemas_tecnicos ??= [];
    r.problemas_tecnicos.push(...(cierre.errores.length
      ? cierre.errores : ['Rollback no confirmado por API e historial oficial.']));
    r.incidencias_automatizacion = r.problemas_tecnicos.map((x) => ({ descripcion: x }));
  }
  r.estado = cierre.rollback.verificado && !r.parada_seguridad
    && !Object.values(r.casos ?? {}).some((x) => ['NO_EJECUTADA', 'NO_CONCLUYENTE'].includes(x.estado_tecnico))
    ? 'CONCLUIDA' : 'INTERRUMPIDA';
  (r.evidencias ??= []).push(nombre);
  fs.writeFileSync(ruta, sanearArtefacto(json(r), secretos));
  const informe = generarInforme(r);
  const validacion = validarResultadoLocal(r, dir, informe);
  if (!validacion.length) fs.writeFileSync(path.join(dir, NOMBRE_INFORME(r.version)), informe);
  return cierre.rollback.verificado && !validacion.length ? 0 : 5;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const a = process.argv.slice(2);
  if (a.includes('--capacidades')) { console.log(json(CAPACIDADES)); process.exit(0); }
  if (a.includes('--comprobar')) process.exit(comprobar());
  if (a.includes('--preflight')) {
    try {
      const archivo = valor(a, '--contexto');
      if (!archivo) throw new Error('Falta --contexto.');
      const c = JSON.parse(fs.readFileSync(archivo, 'utf8'));
      const args = ['--operacion', String(c.operacion ?? '').toLowerCase(), '--version', String(c.version),
        '--intento', String(c.intento), '--run-id', c.run_id, '--contexto', path.resolve(archivo),
        '--autorizacion', c.referencia];
      if (c.operacion === 'RECUPERAR') args.push('--run-objetivo', c.run_objetivo);
      const contrato = contextoEjecucion(args, { grupo: 'G88', casos: IDS_CASOS, directorio: DIR });
      const diagnostico = preflightLocal(contrato);
      console.log(json(diagnostico));
      process.exit(diagnostico.ok ? 0 : 2);
    } catch (e) {
      console.log(json({ fase: 'CONTRATO', ok: false, motivos: [e.message] }));
      process.exit(2);
    }
  }
  if (a.includes('--regenerar-informe')) {
    try { console.log(regenerarInforme(valor(a, '--regenerar-informe'), valor(a, '--salida'))); process.exit(0); }
    catch (e) { console.error(e.message); process.exit(2); }
  }
  if (!a.includes('--operacion')) {
    persistirFalloContrato(a, 'Falta --operacion.');
    console.error('Solo se acepta contrato del lanzador (--operacion, --version, --intento, --run-id, --contexto, --autorizacion).');
    process.exit(2);
  }
  try {
    const c = contextoEjecucion(a, { grupo: 'G88', casos: IDS_CASOS, directorio: DIR });
    if (c.operacion === 'recuperar') process.exit(await recuperar(c));
    process.exit(await evaluar(c));
  } catch (e) {
    persistirFalloContrato(a, e.message);
    console.error(`Contrato o ejecución inválida: ${e.message}`);
    process.exit(2);
  }
}
