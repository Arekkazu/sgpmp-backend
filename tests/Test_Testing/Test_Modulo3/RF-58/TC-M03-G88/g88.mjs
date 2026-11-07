#!/usr/bin/env node
// Ejecutor canónico G88. El lanzador reserva el RUN; este módulo solo actúa con contrato válido.
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';
import { createRequire } from 'node:module';
import vm from 'node:vm';
import { contextoEjecucion } from './lib/contrato_ejecutor.mjs';
import { sanearArtefacto } from './lib/g88_seguridad.mjs';
import { cerrarYVerificar, cierreUnico, sinEscriturasQueRevertir } from './lib/g88_cierre.mjs';
import { chromeLocal, ejecutarCypressControlado, TIMEOUT_UI_MS } from './lib/g88_cypress_runner.mjs';
import { CAPACIDADES, CASOS, IDS_CASOS, PLAN_266, evaluar266, bloqueosEscenario, resultadoOficial, umbralesActivos180 } from './lib/g88_catalogo.mjs';
import { derivarIncidencias, generarInforme, validarResultadoLocal } from './lib/g88_informe.mjs';
import { evaluarOficialidad } from './lib/g88_oficial.mjs';
import { derivarEntradas, invertirCalibracion, camposUmbral, ausenciaT,
  activoUnicoVinculable, lecturaVinculada, lecturaVinculadaHistorial,
  conservarAnterior, asociacionVigente, rangoHistorial } from './lib/g88_entradas.mjs';
import { autorizacion266, autorizarEscritura266, verificarSemillaPreexistente266,
  barreraPublicacion266, compuertaDispositivos266, niveles } from './lib/g88_266_plan.mjs';
import { construirCuerpoIngesta, cuerpoOpcionalNewman, planTemporalIngestas } from './lib/g88_ingesta.mjs';
import { respuestaSaneada, lecturaDelRun } from './lib/g88_respuestas.mjs';
import { ensayoOficialidad } from './pruebas/g88_oficial_local.mjs';

const DIR = path.dirname(fileURLToPath(import.meta.url));
const RAIZ = path.resolve(DIR, '..', '..', '..', '..', '..');
const requireRaiz = createRequire(path.join(RAIZ, 'package.json'));
const versionCypressInstalada = () => {
  try { return requireRaiz('cypress/package.json').version; }
  catch { return null; }
};
const COLECCION = path.join(DIR, 'G88.postman_collection.json');
const REPORTE_NEWMAN = 'newman/newman-TC-M03-G88';
export function evidenciasNewman(dir) {
  const carpeta = path.join(dir, 'newman');
  if (!fs.existsSync(carpeta)) return [];
  const archivos = fs.readdirSync(carpeta).sort();
  const esperados = ['newman-TC-M03-G88.html', 'newman-TC-M03-G88.json'];
  if (JSON.stringify(archivos) !== JSON.stringify(esperados))
    throw new Error(`Newman requiere exactamente un JSON y un HTML: ${archivos.length} archivos.`);
  return esperados.map((nombre) => `newman/${nombre}`);
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
function completarComprobacionesApi(r) {
  for (const c of r.comprobaciones.filter((x) => x.fuente === 'API')) {
    c.motivo ??= c.estado === 'APROBADO' ? 'Comprobación conforme.' : c.observado;
    c.evidencia ??= c.id === 'API-180-04' ? 'resultado.json' : 'newman/newman-TC-M03-G88.json';
  }
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
  try {
    coleccion = JSON.parse(fs.readFileSync(COLECCION, 'utf8'));
    for (const evento of [...(coleccion.event ?? []), ...(coleccion.item ?? []).flatMap((x) => x.event ?? [])])
      new vm.Script(`(function(){${evento.script.exec.join('\n')}\n})()`, { filename: 'G88.postman_collection.json' });
    agregar('Colección Newman única, legible y scripts válidos', coleccion.item.length === 3);
  }
  catch { agregar('Colección Newman única, legible y scripts válidos', false); }
  const archivos = ['g88.mjs', 'g88.cy.js', 'g88.cypress.config.cjs', 'lib/contrato_ejecutor.mjs',
    'lib/g88_cierre.mjs', 'lib/g88_informe.mjs', 'lib/g88_oficial.mjs',
    'lib/g88_presentacion.mjs', 'lib/g88_presentacion_actual.mjs', 'lib/g88_seguridad.mjs',
    'lib/g88_cypress_runner.mjs', 'lib/g88_cypress_worker.mjs', 'lib/g88_catalogo.mjs',
    'lib/g88_266_plan.mjs', 'lib/g88_ingesta.mjs', 'lib/g88_respuestas.mjs'];
  for (const archivo of archivos) {
    try {
      const texto = fs.readFileSync(path.join(DIR, archivo), 'utf8');
      if (/\.(?:cjs|cy\.js)$/.test(archivo)) new vm.Script(texto, { filename: archivo });
      agregar(`Archivo ${archivo} legible`, texto.length > 0);
    } catch { agregar(`Archivo ${archivo} legible`, false); }
  }
  agregar('Sin mojibake en archivos canónicos', [...archivos, 'G88.postman_collection.json',
    'README.md', 'lib/g88_entradas.mjs', 'lib/g88_escenario.json',
    'pruebas/g88_ui_local.mjs', 'pruebas/g88_ui_fixtures.json', 'pruebas/g88_oficial_local.mjs']
    .every((archivo) => !/[\u00c3\u00c2]/.test(fs.readFileSync(path.join(DIR, archivo), 'utf8'))));
  const activos = archivos.map((f) => fs.readFileSync(path.join(DIR, f), 'utf8')).join('\n') + fs.readFileSync(COLECCION, 'utf8');
  agregar('Sin invocaciones de control SQL ni procesos de control de versiones en rutas activas',
    !/test-control\/query|execFileSync\(['"]git|spawnSync\(['"]git|\bfrom ['"](?:.*\/)?g88_(?:lib|casos)\.mjs/.test(activos));
  const candidatos = /RUN-G88-V1-(?:20261025-020636|20261030-(?:191447|192500|193401|194838|201041))/;
  const fuentes = ['g88.mjs', 'README.md', ...['lib', 'pruebas'].flatMap((dir) =>
    fs.readdirSync(path.join(DIR, dir)).filter((nombre) => fs.statSync(path.join(DIR, dir, nombre)).isFile())
      .map((nombre) => `${dir}/${nombre}`))];
  agregar('Sin dependencias de RUN técnicos 9-14 fuera del historial de README', fuentes.every((archivo) => {
    const contenido = fs.readFileSync(path.join(DIR, archivo), 'utf8');
    return archivo === 'README.md'
      ? !contenido.split(/\r?\n/).some((linea) => candidatos.test(linea)
        && /Resultados[/\\]|\]\([^)]*RUN-G88-V1-/.test(linea))
      : !candidatos.test(contenido);
  }));
  agregar('172 solo GET y M09 sujeto a lista blanca 266',
    coleccion?.item?.every((x) => !/\/configuracion\/umbrales/.test(JSON.stringify(x)) || x.request?.method === 'GET')
    && /autorizarEscritura266/.test(fs.readFileSync(path.join(DIR, 'g88.mjs'), 'utf8')));
  agregar('266 parametrizado y habilitado con contrato', PLAN_266.habilitado
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
  const codigo266 = fs.readFileSync(path.join(DIR, 'g88.mjs'), 'utf8');
  const ruta266 = codigo266.slice(codigo266.lastIndexOf('export async function ejecutarCaso266('))
    .split('export function datosRegistro')[0];
  agregar('266 con compuerta pública y escritura en Newman único',
    /verificarSemillaPreexistente266/.test(ruta266)
    && /COMP-GATEWAY/.test(ruta266) && /COMP-UMBRALES/.test(ruta266)
    && /planNewman\.push/.test(ruta266) && /BARRERA-alta/.test(ruta266.replace('BARRERA-${fase}', 'BARRERA-alta')));
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
  try {
    const ensayo = ensayoOficialidad();
    agregar('Contrato del registro QA y presentación vigente con RUN oficial de solo lectura',
      ensayo.oficial === true && ensayo.incidencias === 3);
  } catch (e) {
    console.error(`Ensayo de oficialidad: ${e.message}`);
    agregar('Contrato del registro QA y presentación vigente con RUN oficial de solo lectura', false);
  }
  try {
    const ensayo = ensayoMemoriaNewman();
    agregar('Newman único: seis casos, barreras 266 y exceso rechazado',
      ensayo.invocaciones === 1 && ensayo.json === 1 && ensayo.html === 1
      && ensayo.casos === 6 && ensayo.extras_rechazados && ensayo.modos === 4);
    agregar('ORD-G88-051: seis modos de alcance, identidad y cierre', ensayo.modos_orden051 === 6);
    const fixture = ensayoFixtureOrden053();
    agregar('ORD-G88-053: fixture real saneada, seis casos, umbral decimal e ids',
      fixture.casos === 6 && fixture.ids_telemetria === 10
      && fixture.pre_inicial_decimal === 'APROBADO' && fixture.pre_final_decimal === 'APROBADO');
    agregar('ORD-G88-055: null en PATCH, ERROR_QA, barreras reales e informe DEV',
      fixture.pre_invalida === 'ERROR_QA' && fixture.secuencia_266 === 'PATCH_CON_NULL_Y_LECTURA_FINAL'
      && fixture.barreras_reales === 'BLOQUEADO' && fixture.incidencias_dev === 'SEIS_LECTURAS');
  } catch { agregar('Newman único: seis casos, barreras 266 y exceso rechazado', false); }
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
    ];
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
      ...(id === 'TC-M03-180' ? ['QA_G88_180_SERIAL'] : []),
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
    ...(ejecutables.includes('TC-M03-180') ? ['QA_G88_180_SENSOR_ID', 'QA_G88_180_SERIAL'] : []),
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

export function comprobarPerfilCuenta(respuesta, rol, idEsperado = null, idOtraCuenta = null) {
  const p = respuesta.json?.data ?? respuesta.json;
  const id = Number(p?.id_usuario);
  const rolCorrecto = respuesta.status === 200 && String(p?.nombre_rol ?? '').toUpperCase() ===
    (rol === 'admin' ? 'ADMINISTRADOR' : 'PRODUCTOR');
  const identidadCorrecta = Number.isSafeInteger(id) && id > 0
    && (idEsperado == null || id === idEsperado) && (idOtraCuenta == null || id !== idOtraCuenta);
  const alcance = Array.isArray(p?.fincas) && p.fincas.some((f) => Number(f.id_finca) === 184);
  return { ok: rolCorrecto && identidadCorrecta && (rol === 'admin' || alcance),
    id, rolCorrecto, identidadCorrecta, alcance };
}

export function loginDbaCorrecto(respuesta) {
  return [200, 201].includes(respuesta.status) && !!respuesta.json?.token;
}

export function validarAccesoAdministrador(respuestas) {
  const esperado = [
    { ruta: '/configuracion/infraestructuras/349', tipo: 'area', id: 349, especie: 126 },
    { ruta: '/configuracion/infraestructuras/504', tipo: 'area', id: 504, especie: 220 },
    { ruta: '/configuracion/umbrales?id_especie=126', tipo: 'umbral', especie: 126 },
    { ruta: '/configuracion/umbrales?id_especie=220', tipo: 'umbral', especie: 220 },
  ];
  const comprobaciones = esperado.map((e, i) => {
    const x = respuestas[i];
    const p = x?.json?.data ?? x?.json;
    const ok = e.tipo === 'area'
      ? x?.status === 200 && Number(p?.id_infraestructura) === e.id && Number(p?.id_finca) === 184
        && p.es_activo !== false && ((Array.isArray(p.especies) && p.especies.map(Number).includes(e.especie))
          || Number(p?.especie_id) === e.especie)
      : x?.status === 200 && Array.isArray(p?.items) && Number(p?.total) === p.items.length
        && (e.especie === 126
          ? p.items.some((u) => Number(u.id_umbral_ambiental) === 70
            && Number(u.id_especie) === 126 && u.es_activo !== false)
          : p.items.length === 0);
    return { ruta: e.ruta, http: x?.status ?? null, datos_esperados: ok };
  });
  return { ok: comprobaciones.every((x) => x.datos_esperados), comprobaciones,
    fallos: comprobaciones.filter((x) => !x.datos_esperados).map((x) => `${x.ruta} HTTP ${x.http}; datos esperados ausentes`) };
}

export async function comprobarAccesoAdministrador(leer) {
  const rutas = ['/configuracion/infraestructuras/349', '/configuracion/infraestructuras/504',
    '/configuracion/umbrales?id_especie=126', '/configuracion/umbrales?id_especie=220'];
  const respuestas = [];
  for (const ruta of rutas) respuestas.push(await leer(ruta));
  return validarAccesoAdministrador(respuestas);
}

export function comprobarCierreDba(cierreApi, cierreHttp, timeoutEnRun) {
  return cierreApi?.status === 200 && cierreHttp === 200
    && Number.isFinite(cierreApi.latencia_ms) && cierreApi.latencia_ms < 30000 && !timeoutEnRun;
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
    V.QA_ADMIN_EMAIL, V.QA_PROD_EMAIL,
    ...Object.entries(V).filter(([nombre]) => /^QA_G88_/.test(nombre)).map(([, valor]) => valor)].filter(Boolean);
  const runId = contrato.runId.slice(4);
  const r = { grupo: 'TC-M03-G88', rf: 'RF-58', version: contrato.version, intento: contrato.intento,
    run_id: contrato.runId, operacion: contrato.operacion.toUpperCase(), referencia: contrato.referencia,
    ambiente: 'TEST', inicio: new Date().toISOString(), fin: null, estado: 'EN_CURSO',
    commit: 'NO VERIFICADO', herramientas: { node: process.version,
      newman: '6.2.2 (versión local verificada; ejecución pendiente)',
      cypress: versionCypressInstalada() ? `Cypress ${versionCypressInstalada()} instalado; ejecución pendiente` : 'no disponible' },
    comprobaciones: [], comprobaciones_tecnicas: [1, 2, 3, 4, 5].map((n) => ({
      id: `DBA-01-0${n}`, estado: 'NO_EJECUTADO', observado: 'Secuencia técnica pendiente.',
      naturaleza: 'DBA-01', veredicto_rf58: false })), cuentas: [], casos: {}, bloqueos: bloques, evidencias: ['resultado.json'], incidencias: [],
    incidencias_automatizacion: [], hallazgos_producto: [], oficial: false,
    motivo_no_oficial: 'RUN en curso.', clasificacion_prevista: 'TECNICO',
    problemas_tecnicos: [], cierre: null, cypress: { total_pruebas: 0,
      casos: Object.fromEntries(['TC-M03-172', 'TC-M03-180'].map((id) => [id,
        { estado: 'NO_EJECUTADO', total_pruebas: 0, causa: 'Fase Cypress pendiente.' }])) }, bitacora: [],
     respuestas: [], alertas_activas_observadas: [], plan_temporal: null,
     umbral_run_266: null, parada_seguridad: null, timeout_en_run: false };
  const tokens = {};
  const idsCuenta = {};
  const previos = [];
  const lecturas = [];
  const faseUi = { ingesta180Acreditada: false, motivo180: 'Ingesta NH3 no acreditada (HTTP 201 y lectura válida pendientes).' };
  let casoActual = null;
  let sensorActual = null;
  const guardar = () => {
    completarComprobacionesApi(r);
    r.datos_rollback = { escrituras_intentadas: r.escrituras_intentadas === true,
      anteriores: previos.map((p) => ({ caso: p.caso,
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
         if (abierto) r.timeout_en_run = true;
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
  const autenticar = async (rol, checkId = null) => {
    const correo = V[rol === 'admin' ? 'QA_ADMIN_EMAIL' : 'QA_PROD_EMAIL'];
    const clave = V[rol === 'admin' ? 'QA_ADMIN_PASSWORD' : 'QA_PROD_PASSWORD'];
    const x = await solicitar('POST', '/sesiones/', { cuerpo: { correo_electronico: correo, contrasena: clave }, enRun: abierto });
    if (!loginDbaCorrecto(x)) {
      if (checkId) tecnica(checkId, false, `Login ${rol} HTTP ${x.status}; token no acreditado.`);
      r.comprobaciones_tecnicas.push({ id: 'DBA-01-LOGIN', estado: 'ERROR_QA',
        observado: `Login ${rol} HTTP ${x.status}`, naturaleza: 'DBA-01', veredicto_rf58: false });
      if (x.status === 500) r.incidencia_dba_01 = { estado: 'OBSERVADA_EN_RUN',
        evidencia: `Login ${rol} HTTP 500 en RUN autorizado`, equipo_inicial: 'DBA',
        causa_raiz: 'NO DETERMINADA' };
      throw new Error(`DBA-01: Login ${rol} HTTP ${x.status}`);
    }
    tokens[rol] = x.json.token; secretos.push(x.json.token);
    return { token: x.json.token, http: x.status };
  };
  const perfil = async (rol, etapa, checkId) => {
    let x;
    try { x = await solicitar('GET', '/usuarios/me', { token: tokens[rol] }); }
    catch (e) { if (checkId) tecnica(checkId, false, `GET /usuarios/me ${rol} sin respuesta.`); throw e; }
    const comprobado = comprobarPerfilCuenta(x, rol, idsCuenta[rol], idsCuenta[rol === 'admin' ? 'prod' : 'admin']);
    if (comprobado.ok && idsCuenta[rol] == null) idsCuenta[rol] = comprobado.id;
    r.cuentas.push({ etapa, rol_esperado: rol, http: x.status,
      rol_correcto: comprobado.rolCorrecto, identidad_correcta: comprobado.identidadCorrecta,
      finca_184_asignada: comprobado.alcance });
    return { ...comprobado, http: x.status };
  };
  const tecnica = (id, ok, observado) => {
    const registro = r.comprobaciones_tecnicas.find((x) => x.id === id);
    Object.assign(registro, { estado: ok ? 'APROBADO' : 'ERROR_QA', observado });
  };
  const cerrar = cierreUnico(async () => {
    if (!abierto) return;
    r.cierre = await cerrarYVerificar({ runId, secreto: run.secreto, solicitar,
       autenticar: async () => (await autenticar('admin')).token, anteriores: previos, lecturas,
       umbralRun266: r.umbral_run_266, escriturasIntentadas: r.escrituras_intentadas === true });
    const cierreApi = r.bitacora.findLast((x) => x.metodo === 'DELETE' && x.ruta === `/test-control/runs/${runId}`);
    tecnica('DBA-01-05', comprobarCierreDba(cierreApi, r.cierre.cierre_http, r.timeout_en_run),
      `DELETE ${cierreApi?.latencia_ms ?? 'sin medición'} ms; HTTP ${r.cierre.cierre_http}; timeout en RUN=${r.timeout_en_run}`);
     if (!r.cierre.rollback.verificado && (r.cierre.rollback.conclusion !== 'SIN_ESCRITURAS_QUE_REVERTIR'
       || r.cierre.errores.length))
       r.problemas_tecnicos.push(...(r.cierre.errores.length
         ? r.cierre.errores : ['Rollback no confirmado por API e historial oficial.']));
    guardar();
  });
  const interrupcion = () => { void cerrar(); process.exitCode = 130; };
  process.on('SIGINT', interrupcion); process.on('SIGTERM', interrupcion);
  try {
    const disponibilidad = await solicitar('DELETE', `/test-control/runs/${runId}-NO-EXISTE`, { secreto: run.secreto });
    if (disponibilidad.status !== 404) throw new Error(`Sandbox no disponible: HTTP ${disponibilidad.status}`);
    abierto = true;
    const adminInicial = await autenticar('admin', 'DBA-01-01');
    const perfilAdmin = await perfil('admin', 'ADMIN_INICIAL', 'DBA-01-01');
    tecnica('DBA-01-01', [200, 201].includes(adminInicial.http) && perfilAdmin.ok,
      `Login Administrador HTTP ${adminInicial.http}; /usuarios/me HTTP ${perfilAdmin.http}; rol e identidad=${perfilAdmin.ok}`);
    const prodInicial = await autenticar('prod', 'DBA-01-02');
    const perfilProd = await perfil('prod', 'ADMIN_A_PRODUCTOR', 'DBA-01-02');
    tecnica('DBA-01-02', [200, 201].includes(prodInicial.http)
      && perfilProd.rolCorrecto && perfilProd.identidadCorrecta,
      `Login Productor HTTP ${prodInicial.http}; /usuarios/me HTTP ${perfilProd.http}; rol e identidad=${perfilProd.rolCorrecto && perfilProd.identidadCorrecta}`);
    const adminInverso = await autenticar('admin', 'DBA-01-03');
    const perfilInverso = await perfil('admin', 'PRODUCTOR_A_ADMIN', 'DBA-01-03');
    tecnica('DBA-01-03', [200, 201].includes(adminInverso.http) && perfilInverso.ok,
      `Login Administrador HTTP ${adminInverso.http}; /usuarios/me HTTP ${perfilInverso.http}; rol e identidad=${perfilInverso.ok}`);
    const adminRepetido = await autenticar('admin', 'DBA-01-04');
    const perfilRepetido = await perfil('admin', 'ADMIN_REPETIDO', 'DBA-01-04');
    tecnica('DBA-01-04', [200, 201].includes(adminRepetido.http) && perfilRepetido.ok,
      `Segundo login Administrador HTTP ${adminRepetido.http}; /usuarios/me HTTP ${perfilRepetido.http}; rol e identidad=${perfilRepetido.ok}`);
    const prodVigente = await autenticar('prod', 'DBA-01-02');
    const perfilVigente = await perfil('prod', 'PRODUCTOR_VIGENTE', 'DBA-01-02');
    tecnica('DBA-01-02', [200, 201].includes(prodInicial.http) && [200, 201].includes(prodVigente.http)
      && perfilProd.rolCorrecto && perfilProd.identidadCorrecta
      && perfilVigente.rolCorrecto && perfilVigente.identidadCorrecta,
      `Dos logins Productor HTTP ${prodInicial.http}/${prodVigente.http}; /usuarios/me HTTP ${perfilProd.http}/${perfilVigente.http}; identidad sin herencia=${perfilProd.identidadCorrecta && perfilVigente.identidadCorrecta}`);
    if (!perfilProd.rolCorrecto || !perfilVigente.rolCorrecto || !perfilProd.identidadCorrecta || !perfilVigente.identidadCorrecta)
      throw new Error('ERROR_QA_RLS: Productor con rol o identidad incorrecta en /usuarios/me.');
    if (!perfilProd.alcance || !perfilVigente.alcance)
      throw new Error('ERROR_QA_RLS: Productor sin finca 184 asignada; no se evalúan los sensores 552, 737 ni 738.');
    if (!perfilAdmin.ok || !perfilInverso.ok || !perfilRepetido.ok)
      throw new Error('ERROR_QA_RLS: Administrador con rol o identidad incorrecta en /usuarios/me.');
    const accesoAdmin = await comprobarAccesoAdministrador((ruta) => solicitar('GET', ruta,
      { token: tokens.admin, enRun: true }));
    r.acceso_administrador = accesoAdmin.comprobaciones;
    if (!accesoAdmin.ok) throw new Error(`ERROR_QA_RLS: Administrador sin acceso efectivo: ${accesoAdmin.fallos.join('; ')}`);
    if (ejecutables.includes('TC-M03-180')) {
      r.efectos_irreversibles = ['Posible correo SMTP E7 a administradores activos al consultar dashboard; DELETE del RUN no lo revierte. Entrega no acreditada.'];
      const rutaAviso = '/iot/auditoria?tipo_evento=VARIABLE_SIN_UMBRAL&entidad_afectada_id=737&por_pagina=50';
      const x = await solicitar('GET', rutaAviso, { token: tokens.admin, enRun: true });
      r.aviso180_baseline = { http: x.status, items: Array.isArray(x.json?.items) ? x.json.items.map((e) => ({
        id_evento: e.id_evento, fecha_hora: e.fecha_hora,
        administradores_avisados: e.accion_detallada?.administradores_avisados ?? null })) : null };
    }
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
    const apertura = await solicitar('GET', '/usuarios/me', { token: tokens.prod, enRun: true });
    if (apertura.status !== 200 || apertura.eco !== runId) throw new Error('El RUN no devolvió su cabecera de aislamiento.');
    guardar();
    await ejecutarCasosYFaseUi({ r, listos, cadenasPreparadas, faseUi,
      ctx: { r, solicitar, tokens, run, dir, secretos, previos, lecturas, V, contrato,
        planTemporal: r.plan_temporal, detenerSolicitudes: () => { peticionCancelada = true; r.timeout_en_run = true; } },
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
    try {
      if (r.evidencias.some((x) => x.startsWith('newman/'))) evidenciasNewman(dir);
    } catch (e) { r.problemas_tecnicos.push(`Newman: ${e.message}`); }
    try { await cerrar(); } catch (e) { r.problemas_tecnicos.push(`Cierre: ${e.message}`); }
    process.off('SIGINT', interrupcion); process.off('SIGTERM', interrupcion);
    r.fin = new Date().toISOString();
    r.evidencias = r.evidencias.filter((x) => {
      if (x === 'resultado.json') return true;
      const presente = fs.existsSync(path.join(dir, x));
      if (!presente) r.problemas_tecnicos.push(`Evidencia anunciada no encontrada: ${x}`);
      return presente;
    });
    r.evidencias = [...new Set(r.evidencias)];
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
      !r.cierre?.rollback?.verificado && r.cierre?.rollback?.conclusion !== 'SIN_ESCRITURAS_QUE_REVERTIR'
        ? 'Escalar la verificación de cierre con asociaciones, dashboard, M09 e historial.' : null,
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
    const rutaInforme = path.join(dir, NOMBRE_INFORME(r.version));
    fs.writeFileSync(rutaInforme, texto, { flag: 'wx' });
    Object.assign(r, evaluarOficialidad(r, dir));
    guardar();
    texto = generarInforme(r);
    fs.writeFileSync(rutaInforme, texto);
    const validacionFinal = validarResultadoLocal(r, dir, texto);
    if (validacionFinal.length) {
      r.oficial = false;
      r.motivo_no_oficial = validacionFinal.join('; ');
      r.clasificacion_prevista = 'TECNICO';
      guardar();
      fs.writeFileSync(rutaInforme, generarInforme(r));
    }
  }
  return r.estado === 'CONCLUIDA' && r.oficial === true ? 0 : 5;
}

export async function ejecutarCaso266(ctx) {
  const { r, solicitar, tokens, V, run, planTemporal, secretos, lecturas } = ctx;
  const id = 'TC-M03-266';
  r.efectos_irreversibles ??= [];
  r.efectos_irreversibles.push('M09 POST/PATCH intentan sincronización Edge tras commit; solo la compuerta pública y auditoría pueden acreditar que no hubo publicación. DELETE del RUN no revierte MQTT.');
  const semilla = cargarEscenario().semilla_266;
  const control = {};
  let s;
  try {
    s = await verificarSemillaPreexistente266({ solicitar, token: tokens.admin,
      semilla, control, parametros: { especie_id: Number(V.QA_G88_266_ESPECIE_ID),
        area_id: Number(V.QA_G88_266_AREA_ID), activo_id: Number(V.QA_G88_266_ACTIVO_ID),
        dispositivo_id: Number(V.QA_G88_266_DISPOSITIVO_ID), sensor_id: Number(V.QA_G88_266_SENSOR_ID),
        asociacion_id: Number(V.QA_G88_266_ASOCIACION_ID), calibracion_id: Number(V.QA_G88_266_CALIBRACION_ID),
        serial: V.QA_G88_266_SERIAL } });
  } catch (e) {
    r.resultado266 = 'NO_CONCLUYENTE';
    r.bloqueos[id].push({ tipo: 'SEGURIDAD', motivo: `Compuerta pública 266: ${sanearArtefacto(e.message, secretos)}; sin escrituras M09.` });
    return;
  }
  r.bitacora.push({ caso: id, etapa: 'COMPUERTA_PUBLICA', especie_id: s.especie_id,
    area_id: s.area_id, dispositivo_id: s.dispositivo_id, gateways: 0, umbrales: 0,
    resultado: 'ACREDITADA_EN_RUN' });
  const rutaUmbral = `/configuracion/umbrales?id_especie=${s.especie_id}`;
  const antes = await solicitar('GET', rutaUmbral, { token: tokens.admin, enRun: true });
  if (antes.status !== 200 || !Array.isArray(antes.json?.items) || antes.json.items.length) {
    r.bloqueos[id].push({ tipo: 'SEGURIDAD', motivo: 'Compuerta M09 cambió antes de Newman; sin escritura.' });
    return;
  }
  conservarAnterior(ctx.previos, { caso: id, ruta_umbral: rutaUmbral, umbral: antes.json });
  const timestamp = planTemporal?.por_ingesta?.['TC-M03-266:0'];
  const ingreso = construirCuerpoIngesta({ deviceId: s.dispositivo_id, sensorId: s.sensor_id,
    tipoVariable: 'TEMPERATURA_AMBIENTAL', valor: 15, unidad: s.unidad,
    serial: V.QA_G88_266_SERIAL, timestampCaptura: timestamp });
  const items = construirItems266();
  ctx.planNewman.push({ id, clave: id, items, s,
    variables: { qa_autorizado: 'SI', base_url: API, run_id: run.id,
      sandbox_secret: run.secreto, tok_admin: tokens.admin, tok_prod: tokens.prod,
      broker_service_token: V.BROKER_SERVICE_TOKEN, especie_id: s.especie_id,
      area_id: s.area_id, device_id: s.dispositivo_id, sensor_id: s.sensor_id,
      cuerpo_ingesta: JSON.stringify(ingreso),
      cuerpo_alta: JSON.stringify({ id_especie: s.especie_id,
        id_variable_ambiental: s.variable_id, valor_min: 10, valor_max: 20, niveles: niveles(10) }),
      niveles_edicion: JSON.stringify(niveles(20)) },
    procesar: async (rep) => procesar266(rep, { r, s, lecturas }) });
}

function construirItems266() {
  const { inicio, fin } = rangoHistorial();
  const url = (ruta) => `{{base_url}}${ruta}`;
  const mk = (nombre, metodo, ruta, script, { guard, body, auth = 'tok_admin' } = {}) => ({
    name: `TC-M03-266-${nombre}`,
    request: { method: metodo, url: url(ruta), header: [
      { key: 'Authorization', value: `Bearer {{${auth}}}` },
      ...(body ? [{ key: 'Content-Type', value: 'application/json' }] : []) ],
      ...(body ? { body: { mode: 'raw', raw: body } } : {}) },
    event: [
      { listen: 'prerequest', script: { type: 'text/javascript', exec: [
        ...(guard ? [`if(pm.environment.get('${guard}')!=='SI'){pm.execution.skipRequest();return;}`] : []),
        ...(body ? [`pm.request.body.update(pm.variables.replaceIn(${JSON.stringify(body)}));`] : []) ] } },
      { listen: 'test', script: { type: 'text/javascript', exec: [script] } } ] });
  const umbral = "const b=pm.response.code===200?pm.response.json():{};const u=(b.items||[]).find(x=>String(x.id_umbral_ambiental)===pm.environment.get('g88_266_umbral_id'));";
  const auditoria = (fase, siguiente) => `const b=pm.response.code===200?pm.response.json():{};const version=pm.environment.get('g88_266_version_${fase}');const ev=(b.items||[]).filter(x=>x.tipo_evento==='PROPAGACION_UMBRAL_EDGE'&&(version==null?x.accion_detallada?.version==null:Date.parse(x.accion_detallada?.version)===Date.parse(version)));const d=ev.length===1?ev[0].accion_detallada:null;const ok=pm.response.code===200&&d?.estado==='PENDIENTE'&&Array.isArray(d?.gateways)&&d.gateways.length===0&&pm.environment.get('g88_266_estado_${fase}')==='PENDIENTE';pm.test('[TC-M03-266][PRE][BARRERA-${fase}] Sin publicación Edge',()=>pm.expect(ok).to.eql(true));if(ok)pm.environment.set('${siguiente}','SI');`;
  return [
    mk('00-AREAS','GET','/configuracion/infraestructuras?finca_id=184',"const b=pm.response.code===200?pm.response.json():{};const xs=b.items||[];const ys=xs.filter(x=>Number(x.especie_id)===Number(pm.environment.get('especie_id')));const ok=pm.response.code===200&&Number(b.total)===xs.length&&ys.length===1&&Number(ys[0].id_infraestructura)===Number(pm.environment.get('area_id'));pm.test('[TC-M03-266][PRE][COMP-AREAS] Especie solo área 504',()=>pm.expect(ok).to.eql(true));if(ok)pm.environment.set('g88_266_areas_ok','SI');"),
    mk('00-DISPOSITIVOS','GET','/configuracion/dispositivos-iot',"const b=pm.response.code===200?pm.response.json():{};const xs=b.items||[];const ys=xs.filter(x=>Number(x.id_infraestructura)===Number(pm.environment.get('area_id')));const ok=pm.response.code===200&&(b.total==null||Number(b.total)===xs.length)&&ys.length===1&&Number(ys[0].id_dispositivo_iot)===Number(pm.environment.get('device_id'))&&ys.every(x=>x.categoria!=='GATEWAY_EDGE'&&x.id_dispositivo_gateway==null);pm.test('[TC-M03-266][PRE][COMP-GATEWAY] Sin Edge ni gateway',()=>pm.expect(ok).to.eql(true));if(ok)pm.environment.set('g88_266_devices_ok','SI');",{guard:'g88_266_areas_ok'}),
    mk('00-UMBRALES','GET','/configuracion/umbrales?id_especie={{especie_id}}',"const b=pm.response.code===200?pm.response.json():{};const ok=pm.response.code===200&&Array.isArray(b.items)&&b.items.length===0&&Number(b.total)===0;pm.test('[TC-M03-266][PRE][COMP-UMBRALES] Sin umbrales previos',()=>pm.expect(ok).to.eql(true));if(ok)pm.environment.set('g88_266_write_ok','SI');",{guard:'g88_266_devices_ok'}),
    mk('01-ALTA','POST','/configuracion/umbrales',"const b=pm.response.code===201?pm.response.json():{};const u=b.data||b;const tieneId=Number.isInteger(u.id_umbral_ambiental);const ok=pm.response.code===201&&tieneId&&u.estado_sincronizacion==='PENDIENTE';pm.test('[TC-M03-266][PRE][ALTA-M09] Pendiente',()=>pm.expect(ok).to.eql(true));if(tieneId){pm.environment.set('g88_266_umbral_id',String(u.id_umbral_ambiental));pm.environment.set('g88_266_alta_ok','SI');}",{ guard:'g88_266_write_ok', body:'{{cuerpo_alta}}' }),
    mk('02-UMBRAL-INICIAL','GET','/configuracion/umbrales?id_especie={{especie_id}}',`${umbral}const ok=pm.response.code===200&&u&&Number(u.valor_min)===10&&Number(u.valor_max)===20&&u.estado_sincronizacion==='PENDIENTE'&&Object.hasOwn(u,'fecha_actualizacion');pm.test('[TC-M03-266][PRE][UMBRAL-INICIAL] 10-20 pendiente',()=>pm.expect(!!ok).to.eql(true));if(ok){pm.environment.set('g88_266_estado_alta',u.estado_sincronizacion);pm.environment.set('g88_266_version_alta',u.fecha_actualizacion);pm.environment.set('g88_266_version_alta_json',JSON.stringify(u.fecha_actualizacion));pm.environment.set('g88_266_umbral_alta_ok','SI');}`,{guard:'g88_266_alta_ok'}),
    mk('03-AUDITORIA-ALTA','GET','/iot/auditoria?tipo_evento=PROPAGACION_UMBRAL_EDGE&entidad_afectada_id={{g88_266_umbral_id}}&por_pagina=200',auditoria('alta','g88_266_ingesta_ok'),{guard:'g88_266_umbral_alta_ok'}),
    mk('04-INGESTA','POST','/iot/telemetria',"const b=pm.response.code===201?pm.response.json():{};const ok=pm.response.code===201&&Number.isInteger(b.id_telemetria)&&b.estado_calidad==='LECTURA_VALIDA';pm.test('[TC-M03-266][PRE][INGESTA] Valor 15 válido',()=>pm.expect(ok).to.eql(true));if(ok){pm.environment.set('g88_266_tele_id',String(b.id_telemetria));pm.environment.set('g88_266_lectura_ok','SI');}",{guard:'g88_266_ingesta_ok',body:'{{cuerpo_ingesta}}',auth:'broker_service_token'}),
    mk('05-DASHBOARD-INICIAL','GET','/iot/monitoreo/dashboard?id_infraestructura={{area_id}}&por_pagina=50',"const b=pm.response.code===200?pm.response.json():{};const s=(b.sensores||[]).find(x=>String(x.id_sensor)===pm.environment.get('sensor_id'));const ok=pm.response.code===200&&s&&Number(s.ultimo_valor)===15&&s.estado_semaforo==='VERDE'&&!s.dato_desactualizado&&!s.id_alerta&&!(s.alertas_activas||[]).length;pm.test('[TC-M03-266][ASSERT][API-266-01] 15 VERDE',()=>pm.expect(ok).to.eql(true));if(ok){pm.environment.set('g88_266_verde_ok','SI');pm.environment.set('g88_266_patch_body',JSON.stringify({valor_min:20,valor_max:30,niveles:JSON.parse(pm.environment.get('niveles_edicion')),fecha_actualizacion:JSON.parse(pm.environment.get('g88_266_version_alta_json'))}));pm.environment.set('g88_266_patch_ok','SI');}",{guard:'g88_266_lectura_ok',auth:'tok_prod'}),
    mk('06-HISTORIAL-INICIAL','GET',`/iot/monitoreo/historial?sensor_id={{sensor_id}}&fecha_inicio=${inicio}&fecha_fin=${fin}`,'',{guard:'g88_266_verde_ok',auth:'tok_prod'}),
    mk('07-EDICION','PATCH','/configuracion/umbrales/{{g88_266_umbral_id}}',"const b=pm.response.code===200?pm.response.json():{};const u=b.data||b;const ok=pm.response.code===200&&u.estado_sincronizacion==='PENDIENTE';pm.test('[TC-M03-266][PRE][EDICION-M09] Pendiente',()=>pm.expect(ok).to.eql(true));pm.environment.set('g88_266_edicion_ok','SI');",{guard:'g88_266_patch_ok',body:'{{g88_266_patch_body}}'}),
    mk('08-UMBRAL-FINAL','GET','/configuracion/umbrales?id_especie={{especie_id}}',`${umbral}const previa=pm.environment.get('g88_266_version_alta');const ok=pm.response.code===200&&u&&Number(u.valor_min)===20&&Number(u.valor_max)===30&&u.estado_sincronizacion==='PENDIENTE'&&Object.hasOwn(u,'fecha_actualizacion')&&(previa==null||u.fecha_actualizacion!==previa);pm.test('[TC-M03-266][PRE][UMBRAL-FINAL] 20-30 pendiente',()=>pm.expect(!!ok).to.eql(true));if(ok){pm.environment.set('g88_266_estado_edicion',u.estado_sincronizacion);pm.environment.set('g88_266_version_edicion',u.fecha_actualizacion);pm.environment.set('g88_266_umbral_edicion_ok','SI');}`,{guard:'g88_266_edicion_ok'}),
    mk('09-AUDITORIA-EDICION','GET','/iot/auditoria?tipo_evento=PROPAGACION_UMBRAL_EDGE&entidad_afectada_id={{g88_266_umbral_id}}&por_pagina=200',auditoria('edicion','g88_266_final_ok'),{guard:'g88_266_umbral_edicion_ok'}),
    mk('10-DASHBOARD-FINAL','GET','/iot/monitoreo/dashboard?id_infraestructura={{area_id}}&por_pagina=50',"const b=pm.response.code===200?pm.response.json():{};const s=(b.sensores||[]).find(x=>String(x.id_sensor)===pm.environment.get('sensor_id'));const ok=pm.response.code===200&&s&&Number(s.ultimo_valor)===15&&['ROJO','AMARILLO'].includes(s.estado_semaforo)&&!s.dato_desactualizado&&!s.id_alerta&&!(s.alertas_activas||[]).length;pm.test('[TC-M03-266][ASSERT][API-266-02] Misma lectura recalculada',()=>pm.expect(ok).to.eql(true));",{guard:'g88_266_final_ok',auth:'tok_prod'}),
    mk('11-HISTORIAL-FINAL','GET',`/iot/monitoreo/historial?sensor_id={{sensor_id}}&fecha_inicio=${inicio}&fecha_fin=${fin}`,'',{guard:'g88_266_final_ok',auth:'tok_prod'})
  ];
}

function procesar266(rep, { r, s, lecturas }) {
  const xs = rep.bruto.run.executions;
  registrarAsercionesNewman(rep, 'TC-M03-266', r, s.sensor_id);
  const body = (ex) => { try { return JSON.parse(Buffer.from(ex?.response?.stream?.data ?? []).toString('utf8')); }
    catch { return {}; } };
  const ex = (n) => xs.find((x) => x.item?.name?.startsWith(`TC-M03-266-${n}-`));
  const preFallida = r.comprobaciones.find((x) => x.caso === 'TC-M03-266'
    && x.tipo === 'PRE' && x.estado !== 'APROBADO');
  if (preFallida) {
    const dispositivos = body(xs.find((x) => x.item?.name === 'TC-M03-266-00-DISPOSITIVOS'))?.items ?? [];
    const gateway = preFallida.id === 'COMP-GATEWAY' && Array.isArray(dispositivos)
      && dispositivos.some((x) => x.categoria === 'GATEWAY_EDGE' || x.id_dispositivo_gateway != null);
    const fase = preFallida.id === 'BARRERA-alta' ? '03' : preFallida.id === 'BARRERA-edicion' ? '09' : null;
    const umbralFase = preFallida.id === 'ALTA-M09' ? '01'
      : preFallida.id === 'UMBRAL-INICIAL' ? '02'
        : preFallida.id === 'EDICION-M09' ? '07'
          : preFallida.id === 'UMBRAL-FINAL' ? '08' : null;
    const umbralRespuesta = umbralFase ? body(ex(umbralFase)) : null;
    const estadoUmbral = umbralRespuesta?.items?.[0]?.estado_sincronizacion
      ?? umbralRespuesta?.data?.estado_sincronizacion ?? umbralRespuesta?.estado_sincronizacion;
    const audit = fase ? body(ex(fase)) : null;
    const detalles = Array.isArray(audit?.items) ? audit.items
      .filter((x) => x.tipo_evento === 'PROPAGACION_UMBRAL_EDGE').map((x) => x.accion_detallada) : [];
    const sincronizacion = fase === '03' ? body(ex('02'))?.items?.[0]?.estado_sincronizacion
      : fase === '09' ? body(ex('08'))?.items?.[0]?.estado_sincronizacion : null;
    const barreraReal = gateway || estadoUmbral != null && estadoUmbral !== 'PENDIENTE'
      || (fase && (sincronizacion != null && sincronizacion !== 'PENDIENTE'
      || detalles.some((x) => x?.estado != null && x.estado !== 'PENDIENTE'
        || Array.isArray(x?.gateways) && x.gateways.length > 0)));
    const forma = fase ? `; auditoría HTTP ${ex(fase)?.response?.code ?? 'sin respuesta'}, forma=${Array.isArray(audit?.items) ? `items[${audit.items.length}]` : Object.keys(audit ?? {}).join(',') || 'sin cuerpo'}, detalles=${JSON.stringify(detalles.map((x) => ({ estado: x?.estado ?? null, gateways: Array.isArray(x?.gateways) ? x.gateways.length : null, version: x?.version ?? null })))}` : '';
    r.bloqueos['TC-M03-266'].push({ tipo: barreraReal ? 'SEGURIDAD' : 'AUTOMATIZACION',
      motivo: `Precondición ${preFallida.id} falló: ${preFallida.observado}${forma}` });
  }
  if (!ex('01')?.response) {
    r.resultado266 = 'NO_CONCLUYENTE';
    if (!preFallida) r.bloqueos['TC-M03-266'].push({ tipo: 'AUTOMATIZACION',
      motivo: 'POST M09 omitido sin PRE fallida identificable en Newman.' });
    return;
  }
  const alta = body(ex('01')).data ?? body(ex('01'));
  const umbralId = Number(alta.id_umbral_ambiental);
  r.umbral_run_266 = { alta_intentada: true, id: Number.isSafeInteger(umbralId) && umbralId > 0 ? umbralId : null,
    especie_id: s.especie_id };
  const u = (n) => (body(ex(n)).items ?? []).find((x) => Number(x.id_umbral_ambiental) === umbralId);
  const aud = (n, version) => barreraPublicacion266({
    umbral: u(n === '03' ? '02' : '08') ?? (n === '03' ? alta : (body(ex('07')).data ?? body(ex('07')))),
    eventos: body(ex(n)).items, version });
  const a1 = aud('03', u('02')?.fecha_actualizacion);
  const a2 = aud('09', u('08')?.fecha_actualizacion);
  for (const [etapa, a] of [['ALTA_M09',a1],['EDICION_M09',a2]]) {
    if (etapa === 'EDICION_M09' && !ex('07')?.response) continue;
    if (!ex(etapa === 'ALTA_M09' ? '03' : '09')?.response) continue;
    r.bitacora.push({ caso: 'TC-M03-266', etapa, umbral_id: r.umbral_run_266.id,
      estado: a.estado_auditoria, estado_sincronizacion: a.estado_umbral,
      gateways_count: a.gateways, gateway_observado: a.gateways > 0,
      barrera_segura: a.segura, eventos: a.eventos });
    if (!a.segura && !preFallida) r.bloqueos['TC-M03-266'].push({
      tipo: a.gateways > 0 || a.estado_umbral != null && a.estado_umbral !== 'PENDIENTE'
        || a.estado_auditoria != null && a.estado_auditoria !== 'PENDIENTE' ? 'SEGURIDAD' : 'AUTOMATIZACION',
      motivo: `Barrera M09→Edge ${etapa}: sincronización=${a.estado_umbral ?? 'no informada'}, auditoría=${a.estado_auditoria ?? 'no informada'}, gateways=${a.gateways ?? 'no informados'}; HTTP ${ex(etapa === 'ALTA_M09' ? '03' : '09')?.response?.code}; eventos=${a.eventos}.` });
  }
  const ingesta = body(ex('04'));
  const teleId = Number(ingesta.id_telemetria);
  if (ex('04')?.response?.code === 201 && Number.isSafeInteger(teleId) && teleId > 0) {
    const { inicio, fin } = rangoHistorial();
    lecturas.push({ caso: 'TC-M03-266', sensor_id: s.sensor_id,
      id_telemetria: teleId, fecha_inicio: inicio, fecha_fin: fin });
  }
  const h1 = body(ex('06')), h2 = body(ex('11'));
  const l1 = (h1.items ?? []).find((x) => Number(x.id_telemetria) === teleId);
  const l2 = (h2.items ?? []).find((x) => Number(x.id_telemetria) === teleId);
  const d1 = (body(ex('05')).sensores ?? []).find((x) => Number(x.id_sensor) === s.sensor_id);
  const d2 = (body(ex('10')).sensores ?? []).find((x) => Number(x.id_sensor) === s.sensor_id);
  let timestampIngesta = null;
  try { timestampIngesta = JSON.parse(ex('04')?.request?.body?.raw ?? '{}').timestamp_captura ?? null; }
  catch { /* La identidad queda sin acreditar. */ }
  const origen = !!timestampIngesta && !!d1?.ultimo_timestamp_captura
    && Date.parse(timestampIngesta) === Date.parse(d1.ultimo_timestamp_captura);
  for (const [fase, numero, historial, lectura] of [['inicial', '06', h1, l1], ['final', '11', h2, l2]]) {
    const respuesta = ex(numero)?.response;
    const errorCode = historial.error_code ?? null;
    const conforme = respuesta?.code === 200 && lectura
      && Number(lectura.valor_ajustado ?? lectura.valor) === 15
      && lectura.estado_calidad === 'LECTURA_VALIDA';
    r.comprobaciones.push({ caso: 'TC-M03-266', id: `HIST-${fase}`, tipo: 'APOYO', fuente: 'API',
      estado: conforme ? 'APROBADO' : 'NO_CONCLUYENTE', naturaleza: null,
      observado: `HTTP ${respuesta?.code ?? 'sin respuesta'}; error_code=${errorCode ?? 'ausente'}; lectura=${lectura?.id_telemetria ?? 'ausente'}`,
      motivo: conforme ? 'Lectura identificada en historial.' : 'Historial de apoyo no concluyente.',
      evidencia: 'newman/newman-TC-M03-G88.json' });
  }
  const misma = origen && !!d2 && Number(d1.ultimo_valor) === 15 && Number(d2.ultimo_valor) === 15
    && !!d1.ultimo_timestamp_captura && d1.ultimo_timestamp_captura === d2.ultimo_timestamp_captura
    && (d1.id_telemetria == null || Number(d1.id_telemetria) === teleId)
    && (d2.id_telemetria == null || Number(d2.id_telemetria) === teleId)
    && xs.filter((x) => x.item?.name === 'TC-M03-266-04-INGESTA' && x.response?.code === 201).length === 1;
  const inicial = ex('05')?.response?.code === 200 && d1 && a1.segura
    && ex('04')?.response?.code === 201 && ingesta.estado_calidad === 'LECTURA_VALIDA' && origen
    && !d1.dato_desactualizado
    && !d1.id_alerta && !(d1.alertas_activas ?? []).length;
  const final = ex('10')?.response?.code === 200 && d2 && a2.segura && misma
    && !d2.dato_desactualizado && !d2.id_alerta && !(d2.alertas_activas ?? []).length;
  const estado1 = !inicial ? 'NO_CONCLUYENTE' : d1.estado_semaforo === 'VERDE' ? 'APROBADO' : 'RECHAZADO';
  const estado2 = !final ? 'NO_CONCLUYENTE' : ['ROJO','AMARILLO'].includes(d2.estado_semaforo) ? 'APROBADO' : 'RECHAZADO';
  r.resultado266 = estado2;
  r.comprobaciones.push({ caso: 'TC-M03-266', id: 'API-266-01', tipo: 'ASSERT', fuente: 'API',
    estado: estado1, naturaleza: estado1 === 'RECHAZADO' ? 'PRODUCTO' : null,
    observado: `HTTP ${ex('05')?.response?.code ?? 'sin respuesta'}; valor=${d1?.ultimo_valor ?? 'ausente'}; semáforo=${d1?.estado_semaforo ?? 'ausente'}; lectura=${teleId || 'ausente'}; barrera=${a1.segura}` });
  r.comprobaciones.push({ caso: 'TC-M03-266', id: 'API-266-02', tipo: 'ASSERT', fuente: 'API',
    estado: estado2, naturaleza: estado2 === 'RECHAZADO' ? 'PRODUCTO' : null,
    observado: `HTTP ${ex('10')?.response?.code ?? 'sin respuesta'}; valor=${d2?.ultimo_valor ?? 'ausente'}; semáforo=${d2?.estado_semaforo ?? 'ausente'}; misma_lectura=${misma}; barrera=${a2.segura}` });
}

function registrarAsercionesNewman(rep, id, r, sensorId) {
  const ejecuciones = rep.bruto.run?.executions ?? [];
  for (const ex of ejecuciones) {
    let cuerpo = {};
    try { cuerpo = JSON.parse(Buffer.from(ex.response?.stream?.data ?? []).toString('utf8')); } catch { /* Sin cuerpo evaluable. */ }
    const sensor = cuerpo.sensores?.find((x) => Number(x.id_sensor) === Number(sensorId));
    for (const a of ex.assertions ?? []) {
      const m = /^\[(TC-M03-\d+)\]\[(PRE|ASSERT)\]\[([\w-]+)\]/.exec(a.assertion ?? '');
      if (!m || m[1] !== id || (id === 'TC-M03-266' && m[2] === 'ASSERT')) continue;
      const ingesta = ejecuciones.find((x) => x.item?.name === `${ex.item?.name?.split('/')[0]}/INGESTA`);
      let entrada = null; let calidad = null;
      try { entrada = JSON.parse(ingesta?.request?.body?.raw ?? '{}').valor ?? null;
        calidad = JSON.parse(Buffer.from(ingesta?.response?.stream?.data ?? []).toString('utf8')).estado_calidad ?? null;
      } catch { /* Conserva la observación disponible. */ }
      const observado = id === 'TC-M03-266' && m[2] === 'PRE' && a.error
        ? `HTTP ${ex.response?.code ?? 'sin respuesta'}; ${JSON.stringify({ valor_min: cuerpo.items?.[0]?.valor_min ?? null,
          valor_max: cuerpo.items?.[0]?.valor_max ?? null,
          estado_sincronizacion: cuerpo.items?.[0]?.estado_sincronizacion ?? null,
          fecha_actualizacion: cuerpo.items?.[0]?.fecha_actualizacion ?? null,
          total: cuerpo.total ?? null, items: Array.isArray(cuerpo.items) ? cuerpo.items.length : null })}; aserción=${a.error.message}`
        : m[2] === 'ASSERT' && ['TC-M03-170', 'TC-M03-171'].includes(id)
        ? `HTTP ${ex.response?.code ?? 'sin respuesta'}; entrada=${entrada ?? rep.lecturaEnviada?.valor ?? 'no registrada'}; valor=${sensor?.ultimo_valor ?? 'ausente'}; semáforo=${sensor?.estado_semaforo ?? 'ausente'}; estado_calidad=${sensor?.estado_calidad ?? calidad ?? 'no informado'}; indicador_anomalia=${sensor?.indicador_anomalia ?? 'no informado'}; etiqueta=${sensor?.etiqueta_estado ?? 'no informada'}${a.error ? `; aserción=${a.error.message}` : ''}`
        : a.error?.message ?? `HTTP ${ex.response?.code ?? 'sin respuesta'}; ${JSON.stringify({
        ultimo_valor: sensor?.ultimo_valor, estado_semaforo: sensor?.estado_semaforo,
        valor_min: cuerpo.items?.[0]?.valor_min, valor_max: cuerpo.items?.[0]?.valor_max,
        estado_sincronizacion: cuerpo.items?.[0]?.estado_sincronizacion })}`;
      r.comprobaciones.push({ caso: id, tipo: m[2], id: m[3], fuente: 'API',
        estado: a.error ? (id === 'TC-M03-266' && m[2] === 'PRE' ? 'NO_CONCLUYENTE'
          : ex.response?.code == null ? 'ERROR_QA' : m[2] === 'PRE' ? 'BLOQUEADO' : 'RECHAZADO') : 'APROBADO',
        naturaleza: a.error ? (id === 'TC-M03-266' ? null : ex.response?.code == null ? null : m[2] === 'PRE' ? 'DATOS' : 'PRODUCTO') : null,
        observado, motivo: a.error ? observado : 'Comprobación conforme.',
        evidencia: 'newman/newman-TC-M03-G88.json' });
    }
  }
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
  const planNewman = [];
  const postNewman = [];
  const contexto = { ...ctx, planNewman, postNewman };
  for (const id of listos) {
    const c = cadenasPreparadas[id];
    seleccionarCaso(id, c);
    try {
      if (id === 'TC-M03-266') await ejecutarCaso266Fn(contexto);
      else await ejecutarCasoFn(id, c, { ...contexto, faseUi });
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
  if (planNewman.length || postNewman.length) {
    try {
      if (planNewman.length) {
        r.escrituras_intentadas = true;
        const reportes = ejecutarNewmanUnico(planNewman, ctx);
        if (reportes.some((rep) => rep.bruto.run?.executions?.some((ex) =>
          /timeout|timed out|ETIMEDOUT/i.test(String(ex.requestError?.message ?? ex.requestError ?? '')))))
          r.timeout_en_run = true;
        r.evidencias.push(...evidenciasNewman(ctx.dir));
        r.newman_casos = [...new Set(planNewman.map((p) => p.id))];
        r.bitacora.push({ etapa: 'NEWMAN_UNICO', invocaciones: 1,
          solicitudes: reportes.reduce((n, x) => n + (x.bruto.run?.executions?.length ?? 0), 0),
          casos: r.newman_casos, json: 1, html: 1 });
        r.herramientas.newman = '6.2.2; una ejecución; JSON y HTML reales';
        const ordenProcesamiento = planNewman.map((_, i) => i)
          .sort((a, b) => Number(planNewman[b].id === 'TC-M03-266') - Number(planNewman[a].id === 'TC-M03-266'));
        for (const i of ordenProcesamiento) await planNewman[i].procesar(reportes[i]);
      }
    } catch (e) {
      const error = sanearArtefacto(String(e.message ?? e), ctx.secretos ?? []);
      if (/timeout|timed out|ETIMEDOUT/i.test(error)) ctx.detenerSolicitudes?.();
      if (planNewman.some((p) => p.id === 'TC-M03-266') && !r.umbral_run_266) {
        try {
          const bruto = JSON.parse(fs.readFileSync(path.join(ctx.dir, `${REPORTE_NEWMAN}.json`), 'utf8'));
          const alta = bruto.run?.executions?.find((x) => x.item?.name === 'TC-M03-266-01-ALTA');
          if (alta?.response) {
            const b = JSON.parse(Buffer.from(alta.response.stream?.data ?? []).toString('utf8'));
            const idUmbral = Number((b.data ?? b).id_umbral_ambiental);
            r.umbral_run_266 = { alta_intentada: true,
              id: Number.isSafeInteger(idUmbral) && idUmbral > 0 ? idUmbral : null, especie_id: 220 };
          }
        } catch { r.problemas_tecnicos.push('266: no se pudo recuperar el ID M09 del reporte Newman.'); }
      }
      r.problemas_tecnicos.push(`Newman único: ${error}`);
      if (fs.existsSync(path.join(ctx.dir, 'newman'))) {
        try { r.evidencias.push(...evidenciasNewman(ctx.dir)); } catch { /* El validador registra el exceso. */ }
      }
      for (const id of new Set(planNewman.map((p) => p.id)))
        r.bloqueos[id].push({ tipo: 'AUTOMATIZACION', motivo: `Newman único no evaluable: ${error}` });
      throw e;
    } finally {
      for (const procesar of postNewman) {
        try { await procesar(); }
        catch (e) { r.problemas_tecnicos.push(`Posprocesamiento Newman: ${sanearArtefacto(String(e.message ?? e), ctx.secretos ?? [])}`); }
      }
      guardar();
    }
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
    ctx.planNewman.push({ ...prepararNewman({ id, checkId: 'API-172-A', entrada: {}, s, variable: c.variable,
      run, V, token: tokens.prod, tokenAdmin: tokens.admin, soloUmbrales: true,
      indice: 'consulta', esperado: '' }), procesar: async (rep) => {
      const ex = rep.bruto.run?.executions?.find((x) => x.request?.method === 'GET');
      let umbrales = [];
      try { umbrales = JSON.parse(Buffer.from(ex.response?.stream?.data ?? []).toString('utf8')).items ?? []; }
      catch { /* respuesta no evaluable */ }
      const sinT = ex?.response?.code === 200 && ausenciaT(umbrales);
      const forma = camposUmbral(umbrales)[0] ?? { campos: [], niveles: [] };
      r.comprobaciones.push({ caso: id, id: 'API-172-A', fuente: 'API', tipo: 'ASSERT',
        estado: sinT ? 'RECHAZADO' : 'NO_CONCLUYENTE', naturaleza: sinT ? 'PRODUCTO' : null,
        observado: `HTTP ${ex?.response?.code ?? 'sin respuesta'}; ${umbrales.length} umbrales; campos umbral=${forma.campos.join(',')}; campos niveles=${(forma.niveles ?? []).map((x) => x.join(',')).join(' / ')}; ausencia T=${sinT}` });
    } });
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
  const avisoAntes = id === 'TC-M03-180' ? r.aviso180_baseline : null;
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
    if (avisoAntes?.http !== 200 || !Array.isArray(avisoAntes?.items)) {
      r.bloqueos[id].push({ tipo: 'AUTOMATIZACION', motivo: 'Línea base de bitácora IoT E7 no consultable por API pública.' });
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
    ctx.planNewman.push({ ...prepararNewman({ id, checkId: check[n], entrada: e, s, variable: c.variable, run, V, token: tokens.prod,
      indice: n, timestampCaptura: planTemporal?.por_ingesta[`${id}:${n}`],
      esperado: id === 'TC-M03-266' ? e.esperado_inicial : id === 'TC-M03-180' ? '' : e.esperado }),
      procesar: async (rep) => {
    if (id === 'TC-M03-180') {
      const post = rep.bruto.run?.executions?.find((x) => x.request?.method === 'POST');
      let cuerpo = {};
      try { cuerpo = JSON.parse(Buffer.from(post?.response?.stream?.data ?? []).toString('utf8')); } catch { /* respuesta no evaluable */ }
      ctx.faseUi.ingesta180Acreditada = post?.response?.code === 201
        && Number.isInteger(cuerpo.id_telemetria) && cuerpo.estado_calidad === 'LECTURA_VALIDA';
      ctx.faseUi.motivo180 = ctx.faseUi.ingesta180Acreditada ? null
        : `Ingesta NH3 no acreditada: HTTP ${post?.response?.code ?? 'sin respuesta'}; lectura válida=${cuerpo.estado_calidad === 'LECTURA_VALIDA'}.`;
    }
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
      } });
  }
  if (id === 'TC-M03-180') {
    ctx.postNewman.push(async () => {
    if (!ctx.faseUi.ingesta180Acreditada) return;
    const rutaAviso = '/iot/auditoria?tipo_evento=VARIABLE_SIN_UMBRAL&entidad_afectada_id=737&por_pagina=50';
    const anteriores = new Set(avisoAntes.items.map((x) => x.id_evento));
    let despues;
    let nuevasUmbral = [];
    const inicioEspera = Date.now();
    do {
      despues = await solicitar('GET', rutaAviso, { token: tokens.admin, enRun: true });
      if (despues.status !== 200 || !Array.isArray(despues.json?.items)) break;
      nuevasUmbral = despues.json.items.filter((x) => !anteriores.has(x.id_evento)
        && x.tipo_evento === 'VARIABLE_SIN_UMBRAL' && String(x.entidad_afectada_id) === '737');
      if (nuevasUmbral.length) break;
      if (Date.now() - inicioEspera < 15000) await new Promise((resolver) => setTimeout(resolver, 1000));
    } while (Date.now() - inicioEspera < 15000);
    const avisosRecientes = avisoAntes.items.filter((x) => {
      const edad = Date.now() - Date.parse(x.fecha_hora);
      return Number.isFinite(edad) && edad >= 0 && edad < 86400000
        && Number(x.administradores_avisados) > 0;
    });
    const avisoReciente = avisosRecientes.length > 0;
    const avisoNuevo = nuevasUmbral.some((x) => Number(x.accion_detallada?.administradores_avisados) > 0);
    const previo = avisosRecientes.at(-1);
    const observacion = `Bitácora E7 nueva=${nuevasUmbral.length}; aviso previo=${previo ? `${previo.fecha_hora}, sensor 737, variable NH3, administradores_avisados=${previo.administradores_avisados}` : 'no consta'}; ${avisoReciente && !nuevasUmbral.length ? 'deduplicación de 24 h impidió observar un aviso nuevo en este RUN; ' : ''}HTTP ${despues?.status ?? 'sin respuesta'}; espera ${Date.now() - inicioEspera} ms; correo SMTP irreversible, entrega no verificable por API.`;
    r.comprobaciones.push({ caso: id, id: 'API-180-04', fuente: 'API', tipo: 'ASSERT',
      estado: despues?.status !== 200 ? 'ERROR_QA' : avisoNuevo || (avisoReciente && !nuevasUmbral.length)
        ? 'APROBADO' : 'NO_CONCLUYENTE',
      naturaleza: null,
      observado: observacion });
    });
  }
}

function prepararNewman({ id, checkId, entrada, s, variable, run, V, token, tokenAdmin,
                         indice, esperado, timestampCaptura, skipIngesta = false, soloUmbrales = false }) {
  const clave = `${id}-${indice}`;
  const variables = { qa_autorizado: 'SI', base_url: API, run_id: run.id, sandbox_secret: run.secreto,
    broker_service_token: V.BROKER_SERVICE_TOKEN, tok_prod: token, tok_admin: tokenAdmin ?? '',
    especie_id: s.especie_id, caso: id, check_id: checkId,
    device_id: s.dispositivo_id, sensor_id: s.sensor_id,
    id_infraestructura: s.dashboard_infraestructura_id, tipo_variable: variable,
    valor: entrada.valor_enviado ?? entrada.valor, esperado_valor: entrada.valor ?? '', esperado_estado: esperado,
    esperado_unidad: entrada.unidad ?? s.unidad ?? '', unidad: entrada.unidad ?? s.unidad,
    timestamp_captura_ingesta: timestampCaptura ?? '',
    cuerpo_ingesta: cuerpoOpcionalNewman({ soloUmbrales, skipIngesta, parametros: { deviceId: s.dispositivo_id,
      sensorId: s.sensor_id, tipoVariable: variable, valor: entrada.valor_enviado ?? entrada.valor,
      unidad: entrada.unidad ?? s.unidad, timestampCaptura, serial: s.serial } }) };
  return { clave, id, checkId, entrada, s, variables, skipIngesta, soloUmbrales };
}

export function ejecutarNewmanUnico(plan, { run, dir, secretos, spawn = spawnSync }) {
  if (!plan.length) return [];
  const plantilla = JSON.parse(fs.readFileSync(COLECCION, 'utf8'));
  const items = [];
  for (const p of plan) {
    if (p.items) {
      p.nombres = [];
      for (const original of p.items) {
        const item = structuredClone(original);
        p.nombres.push(item.name);
        item.event.unshift({ listen: 'prerequest', script: { type: 'text/javascript', exec:
          Object.entries(p.variables).map(([k, v]) =>
            `pm.environment.set(${JSON.stringify(k)},${JSON.stringify(String(v ?? ''))});`) } });
        items.push(item);
      }
      continue;
    }
    const indices = p.soloUmbrales ? [2] : p.skipIngesta ? [1] : [0, 1];
    p.nombres = [];
    for (const indice of indices) {
      const item = structuredClone(plantilla.item[indice]);
      item.name = `${p.clave}/${indice === 0 ? 'INGESTA' : indice === 1 ? 'DASHBOARD' : 'UMBRALES'}`;
      p.nombres.push(item.name);
      const asignar = Object.entries(p.variables).map(([k, v]) =>
        `pm.environment.set(${JSON.stringify(k)},${JSON.stringify(String(v ?? ''))});`);
      if (indice === 0) asignar.push("pm.request.headers.upsert({key:'Authorization',value:'Bearer '+pm.environment.get('broker_service_token')});",
        "pm.request.body.update(pm.environment.get('cuerpo_ingesta'));");
      item.event.unshift({ listen: 'prerequest', script: { type: 'text/javascript', exec: asignar } });
      items.push(item);
    }
  }
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'g88-newman-'));
  try {
    const coleccion = path.join(tmp, 'collection.json');
    plantilla.item = items;
    fs.writeFileSync(coleccion, json(plantilla), { mode: 0o600 });
    const env = path.join(tmp, 'env.json');
    fs.writeFileSync(env, json({ values: Object.entries({ qa_autorizado: 'SI', run_id: run.id,
      sandbox_secret: run.secreto }).map(([key, value]) => ({ key, value, enabled: true })) }), { mode: 0o600 });
    const rep = path.join(tmp, 'report.json'); const html = path.join(tmp, 'report.html');
    const cmd = spawn('newman', ['run', coleccion, '-e', env, '--reporters', 'json,htmlextra',
      '--reporter-json-export', rep, '--reporter-htmlextra-export', html,
      '--reporter-htmlextra-skipHeaders', 'Authorization,X-Sandbox-Secret',
      '--reporter-htmlextra-skipEnvironmentVars', 'sandbox_secret,broker_service_token,tok_prod,tok_admin,cuerpo_ingesta',
      '--timeout-request', '30000', '--color', 'off'], { encoding: 'utf8', shell: process.platform === 'win32', timeout: 600000 });
    if (!fs.existsSync(rep) || !fs.existsSync(html))
      throw new Error(`Newman no produjo JSON y HTML reales: ${cmd.status ?? 'sin salida'}`);
    const destino = path.join(dir, 'newman');
    if (fs.existsSync(destino) && fs.readdirSync(destino).length)
      throw new Error('Carpeta newman/ no vacía antes de la ejecución única.');
    fs.mkdirSync(destino, { recursive: true });
    const bruto = JSON.parse(fs.readFileSync(rep, 'utf8'));
    const serialesReporte = new Set();
    const visitarSeriales = (v) => {
      if (Array.isArray(v)) { for (const x of v) visitarSeriales(x); return; }
      if (!v || typeof v !== 'object') return;
      for (const [k, x] of Object.entries(v)) {
        if (k === 'serial' && typeof x === 'string' && x.length >= 4) serialesReporte.add(x);
        else if (k === 'data' && Array.isArray(x) && x.every((n) => Number.isInteger(n) && n >= 0 && n <= 255)) {
          try { visitarSeriales(JSON.parse(Buffer.from(x).toString('utf8'))); } catch { /* No es JSON. */ }
        } else visitarSeriales(x);
      }
    };
    visitarSeriales(bruto);
    secretos.push(...serialesReporte);
    fs.writeFileSync(path.join(dir, `${REPORTE_NEWMAN}.json`), sanearArtefacto(fs.readFileSync(rep, 'utf8'), secretos), { flag: 'wx' });
    fs.writeFileSync(path.join(dir, `${REPORTE_NEWMAN}.html`), sanearArtefacto(fs.readFileSync(html, 'utf8'), secretos), { flag: 'wx' });
    evidenciasNewman(dir);
    const ejecuciones = bruto.run?.executions ?? [];
    if (cmd.error) throw new Error(`Newman interrumpido: ${cmd.error.code ?? cmd.error.message}`);
    let cursor = 0;
    for (const ejecucion of ejecuciones) {
      while (cursor < items.length && items[cursor].name !== ejecucion.item?.name
        && items[cursor].name.startsWith('TC-M03-266-')) cursor++;
      if (cursor >= items.length || items[cursor].name !== ejecucion.item?.name)
        throw new Error('Newman omitió o reordenó solicitudes no opcionales; reporte no evaluable.');
      cursor++;
    }
    if (items.slice(cursor).some((x) => !x.name.startsWith('TC-M03-266-'))
      || !ejecuciones.some((x) => x.item?.name === 'TC-M03-266-01-ALTA') && plan.some((p) => p.id === 'TC-M03-266'))
      throw new Error('Newman omitió solicitudes obligatorias.');
    return plan.map((p) => {
      const xs = ejecuciones.filter((x) => p.nombres.includes(x.item?.name));
      let calidad = null, observado = null;
      for (const ex of xs) {
        let cuerpo = {};
        try { cuerpo = JSON.parse(Buffer.from(ex.response?.stream?.data ?? []).toString('utf8')); } catch { /* respuesta no evaluable */ }
        if (ex.request?.method === 'POST') calidad = cuerpo.estado_calidad ?? null;
        if (ex.request?.method === 'GET') observado = cuerpo.sensores?.find((x) => Number(x.id_sensor) === Number(p.s.sensor_id)) ?? null;
      }
      const post = xs.find((x) => x.request?.method === 'POST');
      let timestampEnviado = null;
      if (post) try { timestampEnviado = JSON.parse(post.request?.body?.raw).timestamp_captura ?? null; }
      catch { /* El reporte no permite acreditar el cuerpo enviado. */ }
      return { bruto: { run: { executions: xs } }, calidad, observado, checkId: p.checkId,
        infraestructuraId: p.s.dashboard_infraestructura_id ?? p.s.area_id,
        lecturaEnviada: { id_sensor: p.s.sensor_id, valor: p.entrada?.valor ?? null,
          timestamp_captura: timestampEnviado }, htmlGenerado: true,
        archivos: [`${REPORTE_NEWMAN}.json`, `${REPORTE_NEWMAN}.html`] };
    });
  } finally {
    if (path.dirname(path.resolve(tmp)) === path.resolve(os.tmpdir()) && path.basename(tmp).startsWith('g88-newman-'))
      fs.rmSync(tmp, { recursive: true, force: true });
  }
}

export function ensayoMemoriaNewman() {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'g88-ensayo-'));
  let invocaciones = 0;
  try {
    const admin = { status: 200, json: { id_usuario: 10, nombre_rol: 'Administrador', fincas: [] } };
    const prod = { status: 200, json: { id_usuario: 20, nombre_rol: 'Productor', fincas: [{ id_finca: 184 }] } };
    const accesos = [
      { status: 200, json: { id_infraestructura: 349, id_finca: 184, especies: [126], es_activo: true } },
      { status: 200, json: { id_infraestructura: 504, id_finca: 184, especies: [220], es_activo: true } },
      { status: 200, json: { total: 1, items: [{ id_umbral_ambiental: 70, id_especie: 126, es_activo: true }] } },
      { status: 200, json: { total: 0, items: [] } },
    ];
    const modosOrden051 = [
      comprobarPerfilCuenta(admin, 'admin', null, 20).ok && validarAccesoAdministrador(accesos).ok,
      !validarAccesoAdministrador([{ status: 403, json: {} }, ...accesos.slice(1)]).ok,
      !comprobarPerfilCuenta({ ...prod, json: { ...prod.json, fincas: [] } }, 'prod', null, 10).ok,
      !loginDbaCorrecto({ status: 500, json: {} }),
      !comprobarPerfilCuenta(admin, 'prod', 20, 10).ok,
      sinEscriturasQueRevertir({ escriturasIntentadas: false, lecturas: [], umbralRun266: null })
        && !sinEscriturasQueRevertir({ escriturasIntentadas: true, lecturas: [], umbralRun266: null })
        && comprobarCierreDba({ status: 200, latencia_ms: 129 }, 200, null)
        && !comprobarCierreDba({ status: 200, latencia_ms: 30000 }, 200, null),
    ].filter(Boolean).length;
    if (modosOrden051 !== 6) throw new Error('Ensayo ORD-G88-051: alcance, identidad o cierre incorrectos.');
    const run = { id: 'ENSAYO-LOCAL', secreto: 'CLAVE_SIMULADA' };
    const V = { BROKER_SERVICE_TOKEN: 'TOKEN_SIMULADO' };
    const s = { especie_id: 126, dispositivo_id: 1, sensor_id: 2,
      dashboard_infraestructura_id: 3, unidad: 'ppm', serial: 'SERIAL_SIMULADO' };
    const ids = ['169', '170', '171', '172', '180', '266'];
    const plan = ids.map((n, i) => ({ ...prepararNewman({ id: `TC-M03-${n}`,
      checkId: n === '172' ? 'API-172-A' : `API-${n}-02`,
      entrada: { valor: 15, unidad: 'ppm' }, s, variable: 'TEMPERATURA_AMBIENTAL',
      run, V, token: 'PRODUCTOR_SIMULADO', tokenAdmin: 'ADMIN_SIMULADO', indice: i,
      esperado: 'VERDE', timestampCaptura: '2026-01-01T00:00:00.000Z',
       soloUmbrales: n === '172', skipIngesta: n === '266' }) }));
    plan[5].items = construirItems266();
    const dispositivo = { id_infraestructura: 504, id_dispositivo_iot: 520,
      es_activo: true, categoria: 'SENSOR_AMBIENTAL', id_dispositivo_gateway: null };
    const sinGateway = compuertaDispositivos266({ items: [dispositivo], total: 1,
      areaId: 504, dispositivoId: 520 });
    const conGateway = compuertaDispositivos266({ items: [dispositivo,
      { ...dispositivo, id_dispositivo_iot: 521, categoria: 'GATEWAY_EDGE' }], total: 2,
      areaId: 504, dispositivoId: 520 });
    const estado = new Map([['area_id','504'],['device_id','520']]);
    let escriturasSimuladas = 0, saltos = 0;
    const pm = { environment: { get: (k) => estado.get(k), set: (k,v) => estado.set(k,v) },
      response: { code: 200, json: () => ({ total: 2, items: [dispositivo,
        { ...dispositivo, id_dispositivo_iot: 521, categoria: 'GATEWAY_EDGE' }] }) },
      test: (_nombre, fn) => { try { fn(); } catch { /* falla esperada */ } },
      expect: (x) => ({ to: { eql: (y) => { if (x !== y) throw new Error('Aserción fallida'); } } }),
      execution: { skipRequest: () => { saltos++; } },
      request: { body: { update: () => { escriturasSimuladas++; } } } };
    const ejecutarScript = (codigo) => new vm.Script(`(function(){${codigo.join('\n')}\n})()`).runInNewContext({ pm });
    ejecutarScript(plan[5].items.find((x) => x.name === 'TC-M03-266-00-DISPOSITIVOS').event[1].script.exec);
    ejecutarScript(plan[5].items.find((x) => x.name === 'TC-M03-266-01-ALTA').event[0].script.exec);
    const version = '2026-01-01T00:00:00Z';
    const evento = (estado) => [{ tipo_evento: 'PROPAGACION_UMBRAL_EDGE',
      accion_detallada: { version, estado, gateways: [] } }];
    const pendiente = barreraPublicacion266({ umbral: { estado_sincronizacion: 'PENDIENTE' },
      eventos: evento('PENDIENTE'), version });
    const aplicada = barreraPublicacion266({ umbral: { estado_sincronizacion: 'APLICADA' },
      eventos: evento('APLICADA'), version });
    const base266 = { precondicionesValidas: true, calidad: 'LECTURA_VALIDA', inicial: 'VERDE',
      mismaLectura: true, sinNuevaLectura: true, alerta: false, gris: false };
    const modos = !conGateway && sinGateway && saltos === 1 && escriturasSimuladas === 0
      && pendiente.segura && !aplicada.segura
      && evaluar266({ ...base266, final: 'ROJO' }) === 'APROBADO'
      && evaluar266({ ...base266, final: 'AMARILLO' }) === 'APROBADO'
      && evaluar266({ ...base266, final: 'VERDE' }) === 'RECHAZADO' ? 4 : 0;
    if (modos !== 4) throw new Error('Ensayo 266: compuerta, sincronización o recálculo incorrectos.');
    const spawn = (_comando, args) => {
      invocaciones++;
      const coleccion = JSON.parse(fs.readFileSync(args[1], 'utf8'));
      for (const item of coleccion.item) for (const evento of item.event ?? [])
        new vm.Script(`(function(){${evento.script.exec.join('\n')}\n})()`, { filename: item.name });
      const orden = coleccion.item.map((x) => x.name);
      const esperado = plan.flatMap((p) => p.nombres);
       if (coleccion.item.length !== 23 || JSON.stringify(orden) !== JSON.stringify(esperado)
        || JSON.stringify(orden.map((x) => /^TC-M03-\d+/.exec(x)?.[0]).filter((x, i, a) => i === 0 || x !== a[i - 1]))
          !== JSON.stringify(ids.map((n) => `TC-M03-${n}`))
        || !args.includes('json,htmlextra')) throw new Error('Orden o reporteros Newman incorrectos.');
      const executions = coleccion.item.map((item) => ({ item: { name: item.name },
        request: { method: item.request.method, body: { raw: '{}' } },
        response: { code: item.request.method === 'POST' ? 201 : 200,
          stream: { data: [...Buffer.from('{}')] } }, assertions: [] }));
      fs.writeFileSync(args[args.indexOf('--reporter-json-export') + 1], json({ run: { executions } }));
      fs.writeFileSync(args[args.indexOf('--reporter-htmlextra-export') + 1], '<html>Newman real simulado CLAVE_SIMULADA</html>');
      return { status: 0 };
    };
    const reportes = ejecutarNewmanUnico(plan, { run, dir, secretos: [run.secreto], spawn });
    if (invocaciones !== 1 || reportes.length !== 6 || evidenciasNewman(dir).length !== 2
      || fs.readFileSync(path.join(dir, `${REPORTE_NEWMAN}.html`), 'utf8').includes(run.secreto))
      throw new Error('Ensayo: ejecución, artefactos o saneamiento incorrectos.');
    fs.writeFileSync(path.join(dir, 'newman', 'extra.json'), '{}');
    let detectoExtra = false;
    try { evidenciasNewman(dir); } catch { detectoExtra = true; }
    if (!detectoExtra) throw new Error('Ensayo: múltiples JSON aceptados.');
    return { invocaciones, json: 1, html: 1, casos: ids.length, extras_rechazados: detectoExtra,
      modos, modos_orden051: modosOrden051 };
  } finally {
    if (path.dirname(path.resolve(dir)) === path.resolve(os.tmpdir()) && path.basename(dir).startsWith('g88-ensayo-'))
      fs.rmSync(dir, { recursive: true, force: true });
  }
}

export function ensayoFixtureOrden053() {
  const fixture = JSON.parse(fs.readFileSync(path.join(DIR, 'pruebas', 'g88_orden053_fixture.json'), 'utf8'));
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'g88-orden053-'));
  let invocaciones = 0;
  try {
    const run = { id: 'ENSAYO-LOCAL', secreto: 'CLAVE_SIMULADA' };
    const V = { BROKER_SERVICE_TOKEN: 'TOKEN_SIMULADO' };
    const s = { especie_id: 126, dispositivo_id: 1, sensor_id: 552,
      dashboard_infraestructura_id: 349, unidad: '°C', serial: 'SERIAL_SIMULADO' };
    const plan = [];
    for (const [n, cantidad] of [['169', 3], ['170', 4], ['171', 2], ['172', 1], ['180', 1]]) {
      for (let i = 0; i < cantidad; i++) {
        const id = `TC-M03-${n}`;
        plan.push(prepararNewman({ id, checkId: n === '172' ? 'API-172-A' : `API-${n}-${String(i + 2).padStart(2, '0')}`,
          entrada: { valor: 15, unidad: n === '180' ? 'ppm' : '°C' },
          s: n === '180' ? { ...s, sensor_id: 737, unidad: 'ppm' } : s,
          variable: 'TEMPERATURA_AMBIENTAL', run, V, token: 'PRODUCTOR_SIMULADO',
          tokenAdmin: 'ADMIN_SIMULADO', indice: n === '172' ? 'consulta' : i,
          esperado: 'VERDE', timestampCaptura: '2026-01-01T00:00:00Z', soloUmbrales: n === '172' }));
      }
    }
    // El plan 266 carece de entrada: reproduce la forma que causó reading 'valor'.
    plan.push({ id: 'TC-M03-266', clave: 'TC-M03-266', items: construirItems266(),
      s: { especie_id: 220, area_id: 504, sensor_id: 738 }, variables: {} });
    const spawn = (_cmd, args) => {
      invocaciones++;
      const ejecuciones = fixture.run.executions.map((x) => ({ ...x,
        response: { code: x.response.code,
          stream: { data: [...Buffer.from(JSON.stringify(x.response.body))] } } }));
      fs.writeFileSync(args[args.indexOf('--reporter-json-export') + 1], json({ run: { executions: ejecuciones } }));
      fs.writeFileSync(args[args.indexOf('--reporter-htmlextra-export') + 1], '<html>Ensayo local</html>');
      return { status: 1 };
    };
    const reportes = ejecutarNewmanUnico(plan, { run, dir, secretos: [run.secreto], spawn });
    const ids = new Set(); const lecturas = [];
    const r = { evidencias: [], comprobaciones: [], respuestas: [], bitacora: [], problemas_tecnicos: [],
      bloqueos: Object.fromEntries(IDS_CASOS.map((id) => [id, []])) };
    for (let i = 0; i < plan.length; i++) {
      const id = plan[i].id;
      ids.add(id);
      if (id === 'TC-M03-266') procesar266(reportes[i], { r, s: plan[i].s, lecturas });
      else if (id === 'TC-M03-172') registrarAsercionesNewman(reportes[i], id, r, s.sensor_id);
      else registrarNewman(reportes[i], id, r, lecturas, plan[i].s.sensor_id);
    }
    completarComprobacionesApi(r);
    const telemetrias = datosRegistro(null, lecturas).datos.ids_telemetria;
    if (invocaciones !== 1 || ids.size !== 6 || r.comprobaciones.length === 0
      || !IDS_CASOS.every((id) => r.comprobaciones.some((x) => x.caso === id))
      || !r.comprobaciones.every((x) => x.caso && x.id && x.estado && x.motivo && x.evidencia)
      || telemetrias.length !== 10 || r.umbral_run_266?.id !== 131
      || !r.bloqueos['TC-M03-266'].some((x) => x.motivo.includes('UMBRAL-INICIAL')))
      throw new Error('Fixture ORD-G88-053: interpretación, seis casos, PRE o ids de telemetría incorrectos.');
    const estado266 = resultadoOficial('TC-M03-266', r.comprobaciones, r.bloqueos['TC-M03-266']);
    if (estado266.estado !== null || estado266.estado_tecnico !== 'ERROR_QA'
      || r.bloqueos['TC-M03-266'].some((x) => x.tipo !== 'AUTOMATIZACION'))
      throw new Error('Fixture 266: una PRE fallida de automatización no produce ERROR_QA.');
    const probarBarrera = (modificar) => {
      const copia = structuredClone(reportes.at(-1));
      modificar(copia.bruto.run.executions);
      const salida = { comprobaciones: [], bloqueos: { 'TC-M03-266': [] }, bitacora: [] };
      procesar266(copia, { r: salida, s: plan.at(-1).s, lecturas: [] });
      return resultadoOficial('TC-M03-266', salida.comprobaciones, salida.bloqueos['TC-M03-266']);
    };
    const gatewayReal = probarBarrera((xs) => {
      const x = xs.find((e) => e.item?.name === 'TC-M03-266-00-DISPOSITIVOS');
      x.response.stream.data = [...Buffer.from(JSON.stringify({ items: [{ categoria: 'GATEWAY_EDGE' }] }))];
      x.assertions.find((a) => a.assertion?.includes('COMP-GATEWAY')).error = { message: 'gateway presente' };
      xs.splice(xs.findIndex((e) => e.item?.name === 'TC-M03-266-01-ALTA'));
    });
    const sincronizacionReal = probarBarrera((xs) => {
      const x = xs.find((e) => e.item?.name === 'TC-M03-266-02-UMBRAL-INICIAL');
      const b = JSON.parse(Buffer.from(x.response.stream.data).toString('utf8'));
      b.items[0].estado_sincronizacion = 'APLICADA';
      x.response.stream.data = [...Buffer.from(JSON.stringify(b))];
    });
    const auditoriaNoInterpretable = probarBarrera((xs) => {
      xs.find((e) => e.item?.name === 'TC-M03-266-02-UMBRAL-INICIAL')
        .assertions.find((a) => a.assertion?.includes('UMBRAL-INICIAL')).error = null;
      xs.push({ item: { name: 'TC-M03-266-03-AUDITORIA-ALTA' }, request: { method: 'GET' },
        response: { code: 200, stream: { data: [...Buffer.from(JSON.stringify({ detail: 'forma inesperada' }))] } },
        assertions: [{ assertion: '[TC-M03-266][PRE][BARRERA-alta] Sin publicación Edge',
          error: { message: 'expected false to deeply equal true' } }] });
    });
    if (gatewayReal.estado !== 'BLOQUEADO' || sincronizacionReal.estado !== 'BLOQUEADO')
      throw new Error('Fixture 266: Gateway o sincronización no PENDIENTE no producen BLOQUEADO.');
    if (auditoriaNoInterpretable.estado_tecnico !== 'ERROR_QA'
      || !auditoriaNoInterpretable.motivo.includes('auditoría HTTP 200, forma=detail'))
      throw new Error('Fixture 266: auditoría no interpretable sin HTTP y forma o sin ERROR_QA.');
    const rep266ConIngesta = structuredClone(reportes.at(-1));
    rep266ConIngesta.bruto.run.executions.push({ item: { name: 'TC-M03-266-04-INGESTA' },
      request: { method: 'POST' }, response: { code: 201,
        stream: { data: [...Buffer.from(JSON.stringify({ id_telemetria: 200001, estado_calidad: 'LECTURA_VALIDA' }))] } },
      assertions: [] });
    const lecturas266 = [];
    const r266 = { comprobaciones: [], bloqueos: { 'TC-M03-266': [] }, bitacora: [] };
    procesar266(rep266ConIngesta, { r: r266, s: plan.at(-1).s, lecturas: lecturas266 });
    if (lecturas266.length !== 1 || datosRegistro(null, lecturas266).datos.ids_telemetria[0] !== 200001)
      throw new Error('Fixture ORD-G88-053: id de ingesta 266 no capturado para poscierre.');
    const probarUmbral = (nombre, cuerpo, previo = null) => {
      const item = construirItems266().find((x) => x.name === `TC-M03-266-${nombre}`);
      const estado = new Map([['g88_266_umbral_id', '131'], ['g88_266_version_alta', previo]]);
      let fallo = null;
      const pm = { response: { code: 200, json: () => ({ items: [cuerpo] }) },
        environment: { get: (k) => estado.get(k), set: (k, v) => estado.set(k, v) },
        test: (_nombre, fn) => { try { fn(); } catch (e) { fallo = e; } },
        expect: (x) => ({ to: { eql: (y) => { if (x !== y) throw new Error('PRE fallida'); } } }) };
      new vm.Script(`(function(){${item.event[1].script.exec.join('\n')}\n})()`).runInNewContext({ pm });
      return { fallo, estado };
    };
    const altaReal = fixture.run.executions.find((x) => x.item?.name === 'TC-M03-266-01-ALTA')?.response?.body;
    const umbralReal = fixture.run.executions.find((x) => x.item?.name === 'TC-M03-266-02-UMBRAL-INICIAL')?.response?.body?.items?.[0];
    if (altaReal?.fecha_actualizacion !== null || umbralReal?.fecha_actualizacion !== null
      || altaReal?.estado_sincronizacion !== 'PENDIENTE')
      throw new Error('Fixture 266: falta la respuesta saneada real con fecha_actualizacion null.');
    const inicial = probarUmbral('02-UMBRAL-INICIAL', umbralReal);
    const final = probarUmbral('08-UMBRAL-FINAL', { id_umbral_ambiental: 131,
      valor_min: '20.00', valor_max: '30.00', estado_sincronizacion: 'PENDIENTE',
      fecha_actualizacion: '2026-10-30T19:26:00Z' }, null);
    const falloReal = probarUmbral('02-UMBRAL-INICIAL', { id_umbral_ambiental: 131,
      valor_min: '11.00', valor_max: '20.00', estado_sincronizacion: 'PENDIENTE',
      fecha_actualizacion: '2026-10-30T19:25:00Z' });
    if (inicial.fallo || final.fallo || inicial.estado.get('g88_266_umbral_alta_ok') !== 'SI'
      || inicial.estado.get('g88_266_version_alta') !== null
      || final.estado.get('g88_266_umbral_edicion_ok') !== 'SI'
      || !falloReal.fallo || falloReal.estado.get('g88_266_umbral_alta_ok'))
      throw new Error('Fixture ORD-G88-053: secuencia PENDIENTE o bloqueo de PRE real incorrectos.');
    const estado = new Map([['g88_266_umbral_id','131'], ['g88_266_version_alta', null],
      ['g88_266_version_alta_json','null'],
      ['g88_266_estado_alta','PENDIENTE'], ['sensor_id','738'],
      ['niveles_edicion', JSON.stringify(niveles(20))]]);
    const paso = (nombre, code, respuesta) => {
      const item = construirItems266().find((x) => x.name === `TC-M03-266-${nombre}`);
      let fallo = null;
      const pm = { response: { code, json: () => respuesta },
        environment: { get: (k) => estado.get(k), set: (k, v) => estado.set(k, v) },
        test: (_nombre, fn) => { try { fn(); } catch (e) { fallo = e; } },
        expect: (x) => ({ to: { eql: (y) => { if (x !== y) throw new Error('PRE/ASSERT fallida'); } } }) };
      new vm.Script(`(function(){${item.event[1].script.exec.join('\n')}\n})()`).runInNewContext({ pm });
      if (fallo) throw new Error(`Fixture 266: ${nombre} no continuó: ${fallo.message}`);
    };
    const audit = (version) => ({ items: [{ tipo_evento: 'PROPAGACION_UMBRAL_EDGE',
      accion_detallada: { version, estado: 'PENDIENTE', gateways: [] } }] });
    if (!barreraPublicacion266({ umbral: umbralReal, eventos: audit(null).items, version: null }).segura)
      throw new Error('Fixture 266: auditoría PENDIENTE con versión null no interpretada.');
    const sensor = (semaforo) => ({ sensores: [{ id_sensor: 738, ultimo_valor: '15.0000',
      ultimo_timestamp_captura: '2026-10-30T19:25:00Z',
      estado_semaforo: semaforo, dato_desactualizado: false, id_alerta: null,
      alertas_activas: [] }] });
    paso('03-AUDITORIA-ALTA', 200, audit(null));
    paso('04-INGESTA', 201, { id_telemetria: 200001, estado_calidad: 'LECTURA_VALIDA' });
    paso('05-DASHBOARD-INICIAL', 200, sensor('VERDE'));
    paso('06-HISTORIAL-INICIAL', fixture.historial_422_real.http, fixture.historial_422_real.body);
    if (fixture.historial_422_real.body.error_code !== 'FECHA_FIN_FUTURA')
      throw new Error('Fixture 266: falta el 422 real del intento 13.');
    const parche = JSON.parse(estado.get('g88_266_patch_body') ?? '{}');
    if (estado.get('g88_266_patch_ok') !== 'SI' || !Object.hasOwn(parche, 'fecha_actualizacion')
      || parche.fecha_actualizacion !== null || parche.valor_min !== 20 || parche.valor_max !== 30)
      throw new Error('Fixture 266: PATCH no envía fecha_actualizacion null leída del GET.');
    paso('07-EDICION', 200, { estado_sincronizacion: 'PENDIENTE' });
    paso('08-UMBRAL-FINAL', 200, { items: [{ id_umbral_ambiental: 131,
      valor_min: '20.00', valor_max: '30.00', estado_sincronizacion: 'PENDIENTE',
      fecha_actualizacion: '2026-10-30T19:26:00Z' }] });
    paso('09-AUDITORIA-EDICION', 200, audit('2026-10-30T19:26:00Z'));
    paso('10-DASHBOARD-FINAL', 200, sensor('ROJO'));
    paso('11-HISTORIAL-FINAL', fixture.historial_422_real.http, fixture.historial_422_real.body);
    if (estado.get('g88_266_final_ok') !== 'SI' || estado.get('g88_266_tele_id') !== '200001')
      throw new Error('Fixture 266: lectura final no acreditada tras PATCH.');
    const urlsHistorial = construirItems266().filter((x) => x.name.includes('HISTORIAL-'));
    const rango = rangoHistorial();
    if (urlsHistorial.length !== 2 || urlsHistorial.some((x) => {
      const q = new URL(x.request.url.replace('{{base_url}}', 'http://local')).searchParams;
      return q.get('fecha_fin') !== rango.fin || q.get('fecha_inicio') !== rango.inicio
        || q.get('fecha_fin') > new Date().toISOString().slice(0, 10);
    })) throw new Error('Fixture 266: URL de historial futura o fuera del rango corto.');
    const simular = (nombre, code, cuerpo) => ({ item: { name: `TC-M03-266-${nombre}` },
      response: { code, stream: { data: [...Buffer.from(JSON.stringify(cuerpo))] } }, assertions: [] });
    const umbralInicial = { id_umbral_ambiental: 131, valor_min: '10.00', valor_max: '20.00',
      estado_sincronizacion: 'PENDIENTE', fecha_actualizacion: null };
    const umbralFinal = { ...umbralInicial, valor_min: '20.00', valor_max: '30.00',
      fecha_actualizacion: '2026-10-30T19:26:00Z' };
    const ejecuciones422 = [simular('01-ALTA', 201, { ...umbralInicial }),
      simular('02-UMBRAL-INICIAL', 200, { items: [umbralInicial] }),
      simular('03-AUDITORIA-ALTA', 200, audit(null)),
      simular('04-INGESTA', 201, { id_telemetria: 200001, estado_calidad: 'LECTURA_VALIDA' }),
      simular('05-DASHBOARD-INICIAL', 200, sensor('VERDE')),
      simular('06-HISTORIAL-INICIAL', fixture.historial_422_real.http, fixture.historial_422_real.body),
      simular('07-EDICION', 200, { estado_sincronizacion: 'PENDIENTE' }),
      simular('08-UMBRAL-FINAL', 200, { items: [umbralFinal] }),
      simular('09-AUDITORIA-EDICION', 200, audit(umbralFinal.fecha_actualizacion)),
      simular('10-DASHBOARD-FINAL', 200, sensor('ROJO')),
      simular('11-HISTORIAL-FINAL', fixture.historial_422_real.http, fixture.historial_422_real.body)];
    ejecuciones422[3].request = { body: { raw: JSON.stringify({ timestamp_captura: '2026-10-30T19:25:00Z' }) } };
    const salida422 = { comprobaciones: [], bloqueos: { 'TC-M03-266': [] }, bitacora: [] };
    procesar266({ bruto: { run: { executions: ejecuciones422 } } },
      { r: salida422, s: { sensor_id: 738, especie_id: 220 }, lecturas: [] });
    const caso422 = resultadoOficial('TC-M03-266', salida422.comprobaciones,
      salida422.bloqueos['TC-M03-266']);
    if (caso422.estado !== 'APROBADO' || caso422.estado_tecnico !== 'OK'
      || salida422.comprobaciones.filter((x) => x.tipo === 'APOYO'
        && x.estado === 'NO_CONCLUYENTE' && x.observado.includes('HTTP 422')
        && x.observado.includes('FECHA_FIN_FUTURA')).length !== 2)
      throw new Error('Fixture 266: historial 422 bloqueó el PATCH o el oráculo final.');
    const presentacion = { ...r, grupo: 'TC-M03-G88', rf: 'RF-58', version: 1,
      run_id: 'RUN-G88-V1-20261030-000000',
      casos: Object.fromEntries(IDS_CASOS.map((id) => [id,
        resultadoOficial(id, r.comprobaciones, r.bloqueos[id])])),
      evidencias: ['newman/newman-TC-M03-G88.json'] };
    const informe = generarInforme(presentacion);
    const incidencias = informe.split('## Incidencias de producto')[1]?.split('## Comprobaciones técnicas DBA-01')[0] ?? '';
    if (!Object.entries({ 'API-170-02':13.65, 'API-170-03':14.85, 'API-170-04':30.15,
      'API-170-05':31.35, 'API-171-02':13.35, 'API-171-03':31.65 })
      .every(([id, valor]) => incidencias.includes(`${id} RECHAZADO: HTTP 200; entrada=${valor}; valor=30.0000; semáforo=VERDE; estado_calidad=FUERA_DE_RANGO; indicador_anomalia=true; etiqueta=Lectura fuera de rango`)))
      throw new Error('Fixture: incidencia DEV omite lecturas fallidas.');
    return { invocaciones, casos: ids.size, comprobaciones: r.comprobaciones.length,
      ids_telemetria: telemetrias.length, id_266_ingesta_simulada: lecturas266.length,
      umbral_266: r.umbral_run_266.id,
      pre_inicial_decimal: 'APROBADO', pre_final_decimal: 'APROBADO', pre_invalida: 'ERROR_QA',
      secuencia_266: 'PATCH_CON_NULL_Y_LECTURA_FINAL', barreras_reales: 'BLOQUEADO',
      incidencias_dev: 'SEIS_LECTURAS' };
  } finally {
    if (path.dirname(path.resolve(dir)) === path.resolve(os.tmpdir()) && path.basename(dir).startsWith('g88-orden053-'))
      fs.rmSync(dir, { recursive: true, force: true });
  }
}

function registrarNewman(rep, id, r, lecturas, sensorId) {
  for (const archivo of rep.archivos) if (!r.evidencias.includes(archivo)) r.evidencias.push(archivo);
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
          && etiqueta180Expuesta && etiqueta180 === 'Sin umbral configurado'
          ? 'APROBADO' : 'RECHAZADO', naturaleza: sinRespuesta ? null : 'PRODUCTO',
        observado: `estado_semaforo=${sensor?.estado_semaforo ?? 'ausente'}; etiqueta=${etiqueta180 ?? 'no expuesta por API'}` });
    }
    if (ex.request?.method === 'POST' && ex.response?.code === 201
      && Number.isSafeInteger(cuerpo.id_telemetria) && cuerpo.id_telemetria > 0) {
      const { inicio, fin } = rangoHistorial();
      if (!lecturas.some((x) => x.id_telemetria === cuerpo.id_telemetria))
        lecturas.push({ caso: id, sensor_id: sensorId, id_telemetria: cuerpo.id_telemetria, fecha_inicio: inicio, fecha_fin: fin });
    }
  }
  registrarAsercionesNewman(rep, id, r, sensorId);
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
      screenshotOnRunFailure: true, trashAssetsBeforeRuns: false, retries: 0, defaultCommandTimeout: 15000,
      viewportWidth: 1440, viewportHeight: 900, requestTimeout: 90000, responseTimeout: 90000 },
    env: { AUTORIZADO_RUN: 'SI', RUN_ID: run.id, SANDBOX_SECRET: V.QA_SANDBOX_SECRET, API_BASE: API_FRONT,
      ARTIFACTS_DIR: capturas,
      PROD_LOGIN: { token: ctx.tokens.prod, tipo: 'bearer', expira_en: 3600, message: 'Sesion reutilizada' },
      SENSOR_180_NOMBRE: s.sensor_nombre, ID_INFRA: s.dashboard_infraestructura_id,
      VALOR_180: 5, UNIDAD_180: 'ppm', PROD_EMAIL: V.QA_PROD_EMAIL, PROD_PASSWORD: V.QA_PROD_PASSWORD,
      CHECK_180: 'SI', CHECK_172: 'NO' } } });
  if (res.token_refresco) { ctx.tokens.prod = res.token_refresco; secretos.push(res.token_refresco); }
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
    const defecto = t.state === 'failed' && m?.[2] === 'ASSERT' && preUiAprobada
      && !/ERROR_QA_EVIDENCIA|HTTP login|GET dashboard|network error|request failed/i.test(t.displayError ?? '')
      && r.evidencias.some((x) => /cypress\/.*TC-M03-180.*\.png$/.test(x));
    const captura = (r.evidencias ?? []).find((x) => /cypress\/.*TC-M03-180_productor_sensor_sin_umbral\.png$/.test(x));
    const visto = m?.[3] === 'UI-180-01' ? `tarjeta del sensor NH3 visible; captura ${captura ?? 'ausente'}`
      : m?.[3] === 'UI-180-02' ? `tarjeta del sensor NH3: valor 5 ppm visible; captura ${captura ?? 'ausente'}`
        : m?.[3] === 'UI-180-03' ? `etiqueta "Sin umbral configurado" y píldora GRIS visibles; captura ${captura ?? 'ausente'}` : null;
    if (m) r.comprobaciones.push({ caso: m[1], tipo: m[2], id: m[3], fuente: 'UI',
      estado: t.state === 'passed' ? 'APROBADO' : defecto ? 'RECHAZADO' : t.state === 'failed' ? 'ERROR_QA' : 'NO_EJECUTADO',
      naturaleza: defecto ? 'PRODUCTO' : null,
      observado: t.state === 'passed' && visto ? visto : t.displayError || t.state });
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
      screenshotOnRunFailure: true, trashAssetsBeforeRuns: false, retries: 0, defaultCommandTimeout: 15000,
      viewportWidth: 1440, viewportHeight: 900, requestTimeout: 90000, responseTimeout: 90000 },
    env: { AUTORIZADO_RUN: 'SI', RUN_ID: run.id, SANDBOX_SECRET: V.QA_SANDBOX_SECRET, API_BASE: API_FRONT,
      ARTIFACTS_DIR: capturas,
      ADMIN_LOGIN: { token: ctx.tokens.admin, tipo: 'bearer', expira_en: 3600, message: 'Sesion reutilizada' },
      ADMIN_EMAIL: V.QA_ADMIN_EMAIL, ADMIN_PASSWORD: V.QA_ADMIN_PASSWORD,
      ID_ESPECIE: s.especie_id, VARIABLE_NOMBRE: s.variable_nombre,
      CHECK_172: 'SI', CHECK_180: 'NO' } } });
  if (res.token_refresco) { ctx.tokens.admin = res.token_refresco; secretos.push(res.token_refresco); }
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
      r.herramientas.cypress = `Cypress ${res.cypress_version ?? versionCypressInstalada() ?? 'versión no acreditada'}; Chrome headless ${res.version ?? 'versión no acreditada'}; ${r.cypress.total_pruebas} pruebas`;
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
    escriturasIntentadas: r.datos_rollback?.escrituras_intentadas !== false,
    solicitarCierre: pendiente, cierrePrevioHttp: r.cierre?.cierre_http ?? null });
  const evidencia = { run_id: contrato.runId, operacion: 'RECUPERAR', referencia: contrato.referencia,
    fecha: new Date().toISOString(), cierre };
  const nombre = `recuperacion-${Date.now()}.json`;
  fs.writeFileSync(path.join(dir, nombre), sanearArtefacto(json(evidencia), secretos), { flag: 'wx' });
  r.cierre = cierre; r.fin = evidencia.fecha;
  if (!cierre.rollback.verificado && (cierre.rollback.conclusion !== 'SIN_ESCRITURAS_QUE_REVERTIR'
    || cierre.errores.length)) {
    r.problemas_tecnicos ??= [];
    r.problemas_tecnicos.push(...(cierre.errores.length
      ? cierre.errores : ['Rollback no confirmado por API e historial oficial.']));
    r.incidencias_automatizacion = r.problemas_tecnicos.map((x) => ({ descripcion: x }));
  }
  r.estado = cierre.rollback.verificado && !r.parada_seguridad
    && !Object.values(r.casos ?? {}).some((x) => ['NO_EJECUTADA', 'NO_CONCLUYENTE'].includes(x.estado_tecnico))
    ? 'CONCLUIDA' : 'INTERRUMPIDA';
  (r.evidencias ??= []).push(nombre);
  Object.assign(r, evaluarOficialidad(r, dir));
  fs.writeFileSync(ruta, sanearArtefacto(json(r), secretos));
  const informe = generarInforme(r);
  const validacion = validarResultadoLocal(r, dir, informe);
  if (!validacion.length) fs.writeFileSync(path.join(dir, NOMBRE_INFORME(r.version)), informe);
  return cierre.rollback.verificado && !validacion.length && r.oficial === true ? 0 : 5;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const a = process.argv.slice(2);
  if (a.includes('--capacidades')) { console.log(json(CAPACIDADES)); process.exit(0); }
  if (a.includes('--comprobar')) process.exit(comprobar());
  if (a.includes('--ensayo-memoria')) {
    globalThis.fetch = () => { throw new Error('BLOQUEO_RED_LOCAL'); };
    try { console.log(json({ ...ensayoMemoriaNewman(), fixture_orden053: ensayoFixtureOrden053() })); process.exit(0); }
    catch (e) { console.error(e.message); process.exit(1); }
  }
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
