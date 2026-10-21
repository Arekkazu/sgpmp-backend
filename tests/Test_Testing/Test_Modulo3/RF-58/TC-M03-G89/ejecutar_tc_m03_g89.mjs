#!/usr/bin/env node
// Ejecutor oficial y reutilizable de TC-M03-G89 (V1, V2, V3, ...). El comportamiento
// específico del grupo vive en g89_casos.mjs (casos, aserciones y plan de datos).
//
// Uso:
//   node ejecutar_tc_m03_g89.mjs --validar-local
//   node ejecutar_tc_m03_g89.mjs --ejecutar --ambiente TEST --autorizacion "<referencia>" \
//        --tipo evaluacion|reintento --aceptar-efectos notificacion-login [--version N]
//
// La ejecución remota exige QA_AUTORIZADO=SI (en .env.qa o en el entorno), la
// referencia verificable de la autorización de Desarrollo y la aceptación expresa
// de los efectos que el rollback no revierte. Sin ellas el proceso termina antes
// de cualquier solicitud de red y sin crear carpetas de resultados.

import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync, execFileSync } from 'node:child_process';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

import { GRUPO, CASOS, PLAN, ARCHIVOS_AUTOMATIZACION } from './g89_casos.mjs';
import {
  ESTADOS_RUN,
  rutasGrupo,
  cargarConfiguracion,
  claveDe,
  resumenConfiguracion,
  evaluarAutorizacion,
  resolverDestinos,
  prefijoSeriales,
  serialDispositivo,
  bloquearRed,
  habilitarRed,
  ClienteSigab,
  literalSql,
  sanitizar,
  redactarTexto,
  escanearYRedactarDirectorio,
  inspeccionarHistorial,
  resolverVersion,
  generarRunId,
  crearDirectorioRun,
  escribirNuevo,
  nombreInforme,
  resultadosDesdeNewman,
  resultadosDesdeCypress,
  incidenciasNewman,
  resumenNewman,
  veredictoCaso,
  estadoGrupo,
  huellaScripts,
  generarInforme,
  enmascararClaveIot,
} from './g89_lib.mjs';

// La red queda bloqueada desde el primer momento.
bloquearRed();

const ARCHIVO = path.basename(fileURLToPath(import.meta.url));
const RUTAS = rutasGrupo(GRUPO, path.dirname(fileURLToPath(import.meta.url)));
const USA_UI = PLAN.casosUI.length > 0;
const NOMBRE_ROL = { setup: 'Preparación de datos', prod: 'Productor', eng: 'Ingeniero de Campo' };
const PERFIL_NEWMAN = { setup: 'Perfil Administrador', prod: 'Perfil Productor', eng: 'Perfil Ingeniero' };

// ---------------------------------------------------------------------------
// Archivos temporales: se eliminan siempre (fin normal, error o interrupción).
// ---------------------------------------------------------------------------

const TEMPORALES = new Set();
const temporal = (nombre) => {
  const p = path.join(os.tmpdir(), `${GRUPO.corto.toLowerCase()}-${process.pid}-${Date.now()}-${nombre}`);
  TEMPORALES.add(p);
  return p;
};
function limpiarTemporales() {
  for (const p of TEMPORALES) {
    try { fs.rmSync(p, { recursive: true, force: true }); } catch { /* se reintenta al salir */ }
  }
  TEMPORALES.clear();
}
process.on('exit', limpiarTemporales);

/** Configuración Cypress en línea (no hay archivo de configuración propio del grupo). */
function configuracionCypress({ baseUrl, capturas, descargas }) {
  return {
    baseUrl,
    specPattern: path.basename(RUTAS.cypressSpec),
    supportFile: false,
    fixturesFolder: false,
    video: false,
    screenshotOnRunFailure: false, // solo capturas explícitas del spec
    trashAssetsBeforeRuns: false,
    testIsolation: false,
    retries: 0,
    defaultCommandTimeout: 15000,
    requestTimeout: 20000,
    responseTimeout: 30000,
    viewportWidth: 1366,
    viewportHeight: 900,
    screenshotsFolder: capturas,
    downloadsFolder: descargas,
  };
}

// ---------------------------------------------------------------------------
// Argumentos
// ---------------------------------------------------------------------------

function leerArgumentos(argv) {
  const a = { modo: 'local', efectos: [] };
  for (let i = 0; i < argv.length; i += 1) {
    const x = argv[i];
    const sig = () => argv[++i];
    if (x === '--validar-local') a.modo = 'local';
    else if (x === '--ejecutar') a.modo = 'ejecutar';
    else if (x === '--ambiente') a.ambiente = sig();
    else if (x === '--autorizacion') a.autorizacion = sig();
    else if (x === '--tipo') a.tipo = sig();
    else if (x === '--version') a.version = sig();
    else if (x === '--aceptar-efectos') a.efectos.push(...String(sig() || '').split(',').map((e) => e.trim()).filter(Boolean));
    else if (x === '--ayuda' || x === '-h' || x === '--help') a.modo = 'ayuda';
    else a.error = `Argumento no reconocido: ${x}`;
  }
  return a;
}

const AYUDA = `
${GRUPO.id} — ejecutor reutilizable (${GRUPO.rf})

  node ${ARCHIVO} --validar-local
      Validación local: sintaxis, catálogo, colección, spec, configuración, barreras e historial.
      No realiza solicitudes de red ni crea carpetas de resultados.

  node ${ARCHIVO} --ejecutar --ambiente TEST --autorizacion "<referencia>" --tipo evaluacion|reintento \\
       --aceptar-efectos ${PLAN.efectosPersistentes.map((e) => e.id).join(',')} [--version N]
      Ejecución oficial. Requiere QA_AUTORIZADO=SI y la autorización expresa de Desarrollo.
      --tipo evaluacion  primera evaluación (V1) o reevaluación autorizada (V2, V3, ...)
      --tipo reintento   reintento técnico dentro de la evaluación vigente (nuevo RUN_ID, misma versión)
      --version N        solo para confirmar la versión cuando el historial es ambiguo
      --aceptar-efectos  aceptación expresa de los efectos que el rollback no revierte:
${PLAN.efectosPersistentes.map((e) => `                         ${e.id}: ${e.descripcion}`).join('\n')}
`;

// ---------------------------------------------------------------------------
// Utilidades locales (sin red)
// ---------------------------------------------------------------------------

function git(args) {
  try {
    return execFileSync('git', ['-C', RUTAS.raizBackend, ...args], { encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] }).trim();
  } catch {
    return null;
  }
}

function infoCodigo() {
  const relGrupo = path.relative(RUTAS.raizBackend, RUTAS.dirGrupo).split(path.sep).join('/');
  const cuenta = git(['rev-list', '--left-right', '--count', 'HEAD...origin/test']);
  const cambios = git(['status', '--porcelain', '--', relGrupo]);
  return {
    rama: git(['rev-parse', '--abbrev-ref', 'HEAD']),
    head: git(['rev-parse', 'HEAD']),
    vs_origin_test: cuenta ? `adelante/atrás = ${cuenta.replace(/\s+/, ' / ')} (referencia local, sin fetch)` : null,
    cambios_locales_grupo: cambios === null ? null : cambios === '' ? 'ninguno' : `${cambios.split('\n').length} archivo(s) con cambios sin confirmar`,
    huella: huellaScripts(RUTAS.dirGrupo, ARCHIVOS_AUTOMATIZACION),
  };
}

function localizarNewman() {
  const r = spawnSync('newman', ['--version'], { encoding: 'utf8', shell: process.platform === 'win32' });
  return r.status === 0 ? { ok: true, version: r.stdout.trim() } : { ok: false, motivo: 'newman no está disponible en PATH.' };
}

function htmlextraDisponible() {
  const r = spawnSync('npm', ['root', '-g'], { encoding: 'utf8', shell: process.platform === 'win32' });
  return r.status === 0 && fs.existsSync(path.join(r.stdout.trim(), 'newman-reporter-htmlextra'));
}

function cargarCypress() {
  if (!USA_UI) return { ok: true, version: 'no aplica (grupo sin escenarios UI)' };
  try {
    const req = createRequire(path.join(RUTAS.raizBackend, 'package.json'));
    return { ok: true, cypress: req('cypress'), version: req('cypress/package.json').version };
  } catch (e) {
    return { ok: false, motivo: `No se pudo cargar Cypress desde ${RUTAS.raizBackend}: ${e.message}` };
  }
}

const ahoraIso = () => new Date().toISOString();

function listarArchivos(dir) {
  const out = [];
  const pila = [dir];
  while (pila.length) {
    const d = pila.pop();
    for (const e of fs.readdirSync(d, { withFileTypes: true })) {
      const p = path.join(d, e.name);
      if (e.isDirectory()) pila.push(p); else out.push(path.relative(dir, p).split(path.sep).join('/'));
    }
  }
  return out.sort();
}

function fin(codigo, mensaje) {
  if (mensaje) (codigo === 0 ? console.log : console.error)(mensaje);
  return codigo;
}

// ---------------------------------------------------------------------------
// MODO LOCAL — sin red
// ---------------------------------------------------------------------------

async function validacionLocal() {
  const comprobaciones = [];
  const ok = (nombre, cumple, detalle = '') => comprobaciones.push({ nombre, cumple: !!cumple, detalle });

  const [mayor] = process.versions.node.split('.').map(Number);
  ok('Node.js >= 22', mayor >= 22, `v${process.versions.node}`);

  for (const f of ARCHIVOS_AUTOMATIZACION) ok(`Archivo presente: ${f}`, fs.existsSync(path.join(RUTAS.dirGrupo, f)));
  for (const f of ARCHIVOS_AUTOMATIZACION.filter((x) => /\.(m?js|cjs)$/.test(x))) {
    const r = spawnSync(process.execPath, ['--check', path.join(RUTAS.dirGrupo, f)], { encoding: 'utf8' });
    ok(`Sintaxis JavaScript: ${f}`, r.status === 0, r.stderr.trim().split('\n')[0] || '');
  }

  // Configuración compartida (solo lectura; nunca se modifica)
  const conf = cargarConfiguracion(RUTAS.envQa);
  ok('.env.qa existe en la raíz del backend', conf.ok, conf.motivo || '');
  ok('.env.qa excluido de Git (git check-ignore)', spawnSync('git', ['-C', RUTAS.raizBackend, 'check-ignore', '-q', '.env.qa']).status === 0);
  const rastreado = git(['ls-files', '.env.qa']);
  ok('.env.qa no está versionado', rastreado === '' || rastreado === null);
  if (conf.ok) {
    const v = conf.valores;
    const destinos = resolverDestinos(v);
    ok('Destinos TEST resueltos sin ambigüedad (canónicas y alias SIGAB_API_BASE / SIGAB_FRONT_URL)', destinos.motivos.length === 0,
      destinos.motivos.join(' ') || `API ${destinos.api} · Front ${destinos.front}`);
    for (const k of ['QA_SETUP_EMAIL', 'QA_PROD_EMAIL', 'QA_ENG_EMAIL']) ok(`Variable definida: ${k}`, !!v[k]);
    ok('Contraseñas QA definidas (sin mostrar)', PLAN.actores.every((rol) => !!claveDe(v, rol)));
    ok('QA_SANDBOX_SECRET definido (sin mostrar)', !!v.QA_SANDBOX_SECRET);
    const pref = prefijoSeriales(v);
    ok('Prefijo de seriales QA disponible', pref.valido, `${pref.prefijo} (${pref.origen}); ejemplo: ${serialDispositivo(pref.prefijo, GRUPO.corto, '20261016153000')}`);
    ok(`QA_AUTORIZADO actual = ${v.QA_AUTORIZADO || '(vacío)'}`, true, 'Informativo: la automatización nunca modifica este valor.');
    const aut = evaluarAutorizacion(v, { ambiente: 'TEST', autorizacion: '', actores: PLAN.actores }, PLAN.efectosPersistentes);
    ok('Barrera de autorización bloquea la ejecución sin autorización vigente', !aut.autorizado, aut.motivos.join(' | '));

    // Ningún archivo del grupo contiene secretos de .env.qa ni JWT.
    const secretos = [v.QA_COMMON_PASSWORD, v.QA_SETUP_PASSWORD, v.QA_PROD_PASSWORD, v.QA_ENG_PASSWORD, v.QA_SANDBOX_SECRET].filter((x) => x && x.length >= 4);
    const conSecretos = fs.readdirSync(RUTAS.dirGrupo)
      .filter((f) => fs.statSync(path.join(RUTAS.dirGrupo, f)).isFile())
      .filter((f) => { const t = fs.readFileSync(path.join(RUTAS.dirGrupo, f), 'utf8'); return redactarTexto(t, secretos) !== t; });
    ok('Ningún archivo del grupo contiene credenciales, secretos ni JWT', conSecretos.length === 0, conSecretos.join(', '));
  }

  // Bloqueo de red efectivo (la llamada falla localmente, sin resolver DNS)
  let bloqueada = false;
  await globalThis.fetch('https://example.invalid').then(() => {}, (e) => { bloqueada = /BLOQUEO_RED/.test(e.message); });
  ok('Bloqueo de red activo en modo local', bloqueada);

  // Colección, spec y catálogo
  let coleccion = null;
  try { coleccion = JSON.parse(fs.readFileSync(RUTAS.coleccion, 'utf8')); } catch (e) { ok('Colección Newman es JSON válido', false, e.message); }
  if (coleccion) {
    ok('Colección Newman es JSON válido con esquema Postman v2.1', /v2\.1\.0/.test(coleccion?.info?.schema ?? ''));
    const items = (coleccion.item ?? []).flatMap((f) => f.item ?? [f]);
    ok('Toda petición de la colección tiene método y URL basada en {{base_url}}', items.every((i) => i.request?.method && String(i.request?.url).startsWith('{{base_url}}')));
    ok('Todos los scripts de la colección son JavaScript sintácticamente válido', (() => {
      const scripts = [...(coleccion.event ?? []), ...items.flatMap((i) => i.event ?? [])].map((e) => (e.script?.exec ?? []).join('\n'));
      return scripts.every((s) => { try { new Function('pm', s); return true; } catch { return false; } });
    })());
    ok('La colección no inicia sesión (usa las sesiones del ejecutor)', !items.some((i) => /\/sesiones/.test(String(i.request?.url))));
  }
  const textoColeccion = coleccion ? JSON.stringify(coleccion) : '';
  const textoSpec = USA_UI ? fs.readFileSync(RUTAS.cypressSpec, 'utf8') : '';
  const idsCatalogo = new Set();
  for (const c of CASOS) {
    for (const a of c.aserciones) {
      idsCatalogo.add(`${c.id}|${a.id}`);
      const etiqueta = `[${c.id}][${a.tipo}][${a.id}]`;
      ok(`Cobertura ${etiqueta} en ${a.fuente === 'UI' ? 'Cypress' : 'Newman'}`, (a.fuente === 'UI' ? textoSpec : textoColeccion).includes(etiqueta));
    }
  }
  const huerfanas = [...`${textoColeccion}\n${textoSpec}`.matchAll(/\[(TC-M03-\d{3})\]\[(PRE|ASSERT|INFO)\]\[([A-Z0-9-]+)\]/g)]
    .filter((m) => !idsCatalogo.has(`${m[1]}|${m[3]}`)).map((m) => m[0]);
  ok('Toda prueba de Newman/Cypress corresponde a una aserción del catálogo', huerfanas.length === 0, [...new Set(huerfanas)].join(', '));
  ok('El catálogo cubre exactamente los casos originales de la matriz',
    JSON.stringify(CASOS.map((c) => c.id)) === JSON.stringify(GRUPO.casosMatriz), GRUPO.casosMatriz.join(', '));
  ok('La colección tiene barrera de autorización propia', /BLOQUEO_/.test(textoColeccion) && /skipRequest/.test(textoColeccion));
  if (USA_UI) {
    ok('El spec Cypress tiene barrera de autorización propia', /BLOQUEO_/.test(textoSpec));
    ok('El spec Cypress no simula respuestas (sin req.reply, fixtures ni stubs)', !/req\.reply|res\.send\(|cy\.fixture|fixture:|cy\.stub/.test(textoSpec));
    ok('El spec Cypress serializa las peticiones hacia el sandbox', /cola = new Promise/.test(textoSpec));
    const cfg = configuracionCypress({ baseUrl: 'https://local.invalid/', capturas: 'c', descargas: 'd' });
    ok('Configuración Cypress en línea coherente (sin video, sin capturas automáticas, sin soporte ni fixtures)',
      cfg.video === false && cfg.screenshotOnRunFailure === false && cfg.supportFile === false && cfg.fixturesFolder === false
      && cfg.specPattern === path.basename(RUTAS.cypressSpec) && fs.existsSync(RUTAS.cypressSpec));
  }

  // Toda variable usada por la colección y el spec debe tenerla el entorno que arma el ejecutor.
  const ctxFicticio = {
    runId: 'LOCAL', sello: '0', especie: 1, idArea: 1, idDisp: 1, idActivo: 1,
    variables: Object.fromEntries(PLAN.variables.map((id) => [id, { valor_fisico_min: -40, valor_fisico_max: 60 }])),
    sensores: Object.fromEntries(PLAN.sensores.map((s) => [s.clave, { id: 1, nombre: 'local' }])),
  };
  const derivados = PLAN.derivar(ctxFicticio);
  ok('Los valores del plan caben en los rangos físicos de referencia de las variables',
    derivados.bloqueos.length === 0, derivados.bloqueos.join(' '));
  ctxFicticio.derivados = derivados.valores;
  const envNewman = new Set([...Object.keys(entornoBaseNewman({ ctx: ctxFicticio, base: '', runId: '', secreto: '', serial: '', tokens: {} })),
    ...[...textoColeccion.matchAll(/collectionVariables\.set\(\\?'(\w+)\\?'/g)].map((m) => m[1])]);
  const faltanNewman = [...new Set([...textoColeccion.matchAll(/\{\{(\w+)\}\}/g)].map((m) => m[1]))].filter((k) => !envNewman.has(k));
  ok('Toda variable {{…}} de la colección la provee el ejecutor o la propia colección', faltanNewman.length === 0, faltanNewman.join(', '));
  if (USA_UI) {
    const envCy = new Set(Object.keys(entornoBaseCypress({ ctx: ctxFicticio, api: '', runId: '', secreto: '', correos: {}, claves: {} })));
    const faltanCy = [...new Set([...textoSpec.matchAll(/env\('(\w+)'\)/g)].map((m) => m[1]))].filter((k) => !envCy.has(k));
    ok('Toda variable env(…) del spec la provee el ejecutor', faltanCy.length === 0, faltanCy.join(', '));
  }

  // Herramientas (solo comprobaciones locales)
  const nw = localizarNewman();
  ok('Newman disponible', nw.ok, nw.version || nw.motivo);
  ok('Reporter newman-reporter-htmlextra disponible', htmlextraDisponible());
  const cy = cargarCypress();
  ok('Cypress resoluble desde sgpmp-backend/node_modules', cy.ok, cy.version || cy.motivo);

  // Estructura, reevaluaciones y resultados
  const entradas = fs.readdirSync(RUTAS.dirGrupo);
  ok('Sin scripts específicos de reevaluación (V2, V3, ...)', !entradas.some((f) => /(^|[_-])v\d+([_.-]|$)/i.test(f) && /\.(m?js|cjs|json|py|ps1)$/.test(f)));
  ok('Sin archivos .env propios del grupo', !entradas.some((f) => /^\.env/.test(f)));
  ok('Se conserva .gitkeep', entradas.includes('.gitkeep'));
  const extra = entradas.filter((f) => !ARCHIVOS_AUTOMATIZACION.includes(f) && !['.gitkeep', 'README.md', 'RESULTADOS'].includes(f) && !/^EvaluacionV\d+$/.test(f));
  ok('Sin archivos ajenos a la automatización en la carpeta del grupo', extra.length === 0, extra.join(', '));
  const hist = inspeccionarHistorial(RUTAS.dirGrupo);
  const proxima = resolverVersion(hist, { tipo: 'evaluacion' });
  ok('Historial oficial legible', hist.anomalias.length === 0, hist.anomalias.join(' '));
  ok(`Próxima evaluación oficial: ${proxima.ok ? `V${proxima.version}` : 'requiere confirmación'}`, true, proxima.motivo);

  // Pruebas unitarias locales de funciones puras
  const t = spawnSync(process.execPath, ['--test', RUTAS.pruebasLocales], { encoding: 'utf8' });
  const resumenTest = (t.stdout.match(/^# (tests|pass|fail) \d+$/gm) || []).join(', ');
  ok('Pruebas unitarias locales (node --test)', t.status === 0, resumenTest || t.stderr.split('\n')[0]);
  return comprobaciones;
}

// ---------------------------------------------------------------------------
// Entornos que reciben Newman y Cypress (los secretos solo viajan en memoria o
// en un archivo temporal que se elimina siempre)
// ---------------------------------------------------------------------------

function entornoBaseNewman({ ctx, base, runId, secreto, serial, tokens }) {
  return {
    qa_autorizado: 'SI',
    base_url: base,
    run_id: runId,
    sandbox_secret: secreto,
    device_id: String(ctx.idDisp),
    access_key: serial,
    id_infraestructura: String(ctx.idArea),
    id_especie: String(ctx.especie),
    id_activo: ctx.idActivo == null ? '' : String(ctx.idActivo),
    ...Object.fromEntries(Object.entries(ctx.sensores).map(([k, s]) => [`sensor_${k.toLowerCase()}`, String(s.id)])),
    ...Object.fromEntries(Object.keys(PERFIL_NEWMAN).filter((r) => PLAN.actores.includes(r)).map((r) => [`tok_${r}`, tokens[r] ?? ''])),
    ...PLAN.entornoNewman(ctx),
  };
}

function entornoBaseCypress({ ctx, api, runId, secreto, correos, claves }) {
  const env = {
    AUTORIZADO_RUN: 'SI',
    RUN_ID: runId,
    SANDBOX_SECRET: secreto,
    API_BASE: api,
    ID_INFRA: ctx.idArea,
    ...Object.fromEntries(Object.entries(ctx.sensores).flatMap(([k, s]) => [[`SENSOR_${k}_NOMBRE`, s.nombre], [`SENSOR_${k}_ID`, s.id]])),
    ...PLAN.entornoCypress(ctx),
  };
  for (const rol of PLAN.actores.filter((r) => r !== 'setup')) {
    env[`${rol.toUpperCase()}_EMAIL`] = correos[rol];
    env[`${rol.toUpperCase()}_PASSWORD`] = claves[rol];
  }
  return env;
}

// ---------------------------------------------------------------------------
// MODO EJECUCIÓN — solo con autorización
// ---------------------------------------------------------------------------

class AbortoPreflight extends Error {}

async function ejecucionOficial(args) {
  const conf = cargarConfiguracion(RUTAS.envQa);
  if (!conf.ok) return fin(2, `Configuración no disponible: ${conf.motivo}`);
  const V = conf.valores;

  // 1) Barrera de autorización (sin red, sin archivos)
  const aut = evaluarAutorizacion(V, { ambiente: args.ambiente, autorizacion: args.autorizacion, actores: PLAN.actores, efectosAceptados: args.efectos }, PLAN.efectosPersistentes);
  if (!aut.autorizado) {
    return fin(2, `EJECUCIÓN NO AUTORIZADA. No se realizó ninguna solicitud remota ni se crearon resultados.\n- ${aut.motivos.join('\n- ')}`);
  }
  const API = aut.destinos.api;
  const FRONT = aut.destinos.front;

  // 2) Versión de evaluación (sin red, sin archivos)
  if (!['evaluacion', 'reintento'].includes(args.tipo)) return fin(3, 'Indique --tipo evaluacion o --tipo reintento.');
  const ver = resolverVersion(inspeccionarHistorial(RUTAS.dirGrupo), { tipo: args.tipo, versionConfirmada: args.version });
  if (!ver.ok) return fin(3, `No se asigna versión de evaluación: ${ver.motivo}`);

  // 3) Herramientas locales
  const nw = localizarNewman();
  const cy = cargarCypress();
  if (!nw.ok || !cy.ok) return fin(4, `Herramientas no disponibles: ${[nw.motivo, cy.motivo].filter(Boolean).join(' ')}`);

  // 4) A partir de aquí se crea el RUN y se habilita la red.
  const inicio = new Date();
  let runId = generarRunId(GRUPO.corto, ver.version, inicio);
  let dirRun;
  for (let i = 2; !dirRun; i += 1) {
    try { dirRun = crearDirectorioRun(RUTAS.dirGrupo, ver.version, runId); }
    catch (e) { if (e.code !== 'EEXIST' || i > 9) throw e; runId = `${generarRunId(GRUPO.corto, ver.version, inicio)}-${i}`; }
  }
  const sello = runId.replace(/^.*-V\d+-/, '').replace(/-/g, '');
  const pref = prefijoSeriales(V);
  const serial = serialDispositivo(pref.prefijo, GRUPO.corto, sello);
  const secretos = [V.QA_COMMON_PASSWORD, V.QA_SETUP_PASSWORD, V.QA_PROD_PASSWORD, V.QA_ENG_PASSWORD, V.QA_SANDBOX_SECRET].filter(Boolean);
  const tokens = {};
  const masSecretos = () => [...secretos, serial, ...Object.values(tokens)].filter(Boolean);
  const bitacora = [];

  const ev = {
    grupo: GRUPO,
    casos_originales: CASOS.map((c) => c.id),
    ejecucion: {
      run_id: runId,
      version: ver.version,
      tipo: args.tipo,
      motivo_version: ver.motivo,
      autorizacion: aut.referencia,
      efectos_aceptados: args.efectos,
      estado: ESTADOS_RUN.EN_CURSO,
      fase: 'PREFLIGHT',
      inicio: inicio.toISOString(),
      fin: null,
      escenarios_iniciados: false,
    },
    entorno: {
      ambiente: 'TEST',
      api_base: API,
      front_url: FRONT,
      configuracion: resumenConfiguracion(V),
      prefijo_seriales: { prefijo: pref.prefijo, origen: pref.origen },
      node: process.versions.node,
      newman: nw.version,
      cypress: cy.version,
    },
    codigo: infoCodigo(),
    riesgos_conocidos: PLAN.riesgos,
    preflight: {},
    actores: [],
    datos: { entidades: [], dependencias: [], serial_enmascarado: enmascararClaveIot(serial) },
    sandbox: { run_id_sandbox: runId, efectos_externos: PLAN.efectosExternos },
    resultados: [],
    bloqueos: {},
    incidencias_ejecucion: { general: [], porCaso: {} },
    newman: null,
    cypress: null,
    resultado_propuesto: null,
    archivos: [],
    bitacora_http: bitacora,
  };
  const guardar = () => fs.writeFileSync(path.join(dirRun, 'evidencia.json'), JSON.stringify(sanitizar(ev, masSecretos()), null, 2), 'utf8');
  const bloquear = (casos, motivo) => { for (const id of casos) (ev.bloqueos[id] ??= []).push(motivo); };
  guardar();

  habilitarRed(aut);
  const cli = new ClienteSigab({ base: API, runId, sandboxSecret: V.QA_SANDBOX_SECRET, secretos: masSecretos(), bitacora });
  let sandboxAbierto = false;

  const sql = async (consulta, rid = runId) => {
    const r = await cli.solicitar('POST', '/test-control/query', { cuerpo: { query: consulta }, runId: rid, etiqueta: `SQL sandbox (${rid === runId ? 'RUN' : 'sonda'})` });
    return r.status === 200 ? r.json?.data ?? [] : null;
  };
  const cerrarRun = (rid, etiqueta) => cli.solicitar('DELETE', `/test-control/runs/${encodeURIComponent(rid)}`, { soloSecreto: true, etiqueta });

  // Testigos de aislamiento SIN RLS (las tablas de modulo9 filtran por rol y en una
  // transacción sin identidad devolverían 0 siempre, lo que no prueba nada):
  //  - auditoria.logs_dml: el trigger fn_auditoria_dml registra el INSERT del dispositivo con su serial.
  //  - modulo3.telemetrias: lecturas de los sensores del RUN (existen tras Newman).
  // null = no verificable (sin privilegio o consulta rechazada); nunca se interpreta como 0.
  const idsSensoresRun = [];
  let dispositivoCreado = false;
  async function sondear(rid) {
    const r = { auditoria_dispositivo: null, telemetrias: null };
    if (dispositivoCreado) {
      const f = await sql(
        `SELECT count(*) AS n FROM auditoria.logs_dml WHERE tabla_afectada = 'dispositivos_iot' ` +
        `AND tipo_operacion = 'INSERT' AND datos_nuevos->>'serial' = ${literalSql(serial)}`, rid);
      r.auditoria_dispositivo = f && f[0] ? Number(f[0].n) : null;
    }
    if (idsSensoresRun.length) {
      const f = await sql(`SELECT count(*) AS n FROM modulo3.telemetrias WHERE id_sensor IN (${idsSensoresRun.map(literalSql).join(', ')})`, rid);
      r.telemetrias = f && f[0] ? Number(f[0].n) : null;
    }
    return r;
  }
  const fixtureVivo = (s) => s.auditoria_dispositivo === 1 || (s.telemetrias ?? 0) > 0;
  const fuga = (s) => (s.auditoria_dispositivo ?? 0) > 0 || (s.telemetrias ?? 0) > 0;
  const verificable = (s) => s.auditoria_dispositivo !== null || s.telemetrias !== null;
  async function sondaExterna(sufijo, etiqueta) {
    const rid = `${runId}-${sufijo}`;
    const s = await sondear(rid);
    await cerrarRun(rid, etiqueta);
    return s;
  }

  async function cerrarSandbox() {
    if (!sandboxAbierto) return;
    sandboxAbierto = false;
    const r1 = await cerrarRun(runId, 'Cierre del sandbox');
    ev.sandbox.cierre = r1.status === 200
      ? 'HTTP 200 «Rollback exitoso»'
      : r1.status === 404
        ? 'HTTP 404: el RUN ya no estaba activo (posible rollback por inactividad de 180 s)'
        : `HTTP ${r1.status} ${r1.error ?? ''}`.trim();
    const r2 = await cerrarRun(runId, 'Confirmación de cierre');
    const restos = await sondaExterna('POST', 'Cierre de la sonda posterior');
    ev.sandbox.sonda_posterior = restos;
    const sinEscrituras = !dispositivoCreado && !idsSensoresRun.length;
    if (r2.status === 404 && (sinEscrituras || (verificable(restos) && !fuga(restos)))) {
      ev.sandbox.rollback_confirmado = `Sí: el RUN ya no existe (segundo DELETE 404) y una transacción nueva no ve rastros del fixture ${JSON.stringify(restos)}.`;
    } else if (r2.status === 404 && !verificable(restos)) {
      ev.sandbox.rollback_confirmado = 'PARCIAL: el RUN ya no existe (segundo DELETE 404), pero los testigos SQL no fueron consultables; confirmar con DBA.';
    } else {
      ev.sandbox.rollback_confirmado = `NO CONFIRMADO: segundo DELETE HTTP ${r2.status}; testigos fuera del RUN ${JSON.stringify(restos)}. Escalar a DBA.`;
    }
  }

  let interrumpido = false;
  const alInterrumpir = async (senal) => {
    if (interrumpido) return;
    interrumpido = true;
    ev.ejecucion.estado = ESTADOS_RUN.INTERRUMPIDA;
    ev.ejecucion.motivo_aborto = `Interrupción por ${senal}.`;
    console.error(`\n${senal} recibida: cerrando el sandbox y eliminando temporales…`);
    try { await cerrarSandbox(); } catch (e) { ev.sandbox.cierre = `Error al cerrar: ${e.message}`; }
    finally { ev.ejecucion.fin = ahoraIso(); guardar(); limpiarTemporales(); process.exit(130); }
  };
  const alSigint = () => alInterrumpir('SIGINT');
  const alSigterm = () => alInterrumpir('SIGTERM');
  process.once('SIGINT', alSigint);
  process.once('SIGTERM', alSigterm);

  try {
    // ---- PREFLIGHT remoto (sin escrituras) ---------------------------------
    const salud = await cli.solicitar('GET', '/health', { sandbox: false, etiqueta: 'Salud del backend' });
    ev.preflight.health = salud.status;
    const api = await cli.solicitar('GET', '/openapi.json', { sandbox: false, etiqueta: 'Contrato OpenAPI' });
    const rutas = Object.keys(api.json?.paths ?? {});
    ev.preflight.openapi = { http: api.status, version: api.json?.info?.version ?? null, rutas_faltantes: PLAN.rutasRequeridas.filter((r) => !rutas.includes(r)) };
    const bloqueoGlobal = [];
    if (salud.status !== 200) bloqueoGlobal.push(`El backend TEST no responde /health (HTTP ${salud.status}).`);
    if (ev.preflight.openapi.rutas_faltantes.length) bloqueoGlobal.push(`Contrato TEST sin rutas requeridas: ${ev.preflight.openapi.rutas_faltantes.join(', ')}.`);
    // Un DELETE sobre un RUN inexistente no crea transacción: distingue router montado + secreto válido.
    const ctrl = await cerrarRun(`${runId}-PREFLIGHT`, 'Disponibilidad del sandbox');
    const detalle = String(ctrl.json?.detail ?? '');
    ev.sandbox.preflight = ctrl.status === 404 && /Run ID no encontrado/i.test(detalle)
      ? 'Sandbox habilitado y secreto aceptado (404 «Run ID no encontrado» para un RUN inexistente).'
      : `Sandbox NO disponible: HTTP ${ctrl.status} ${detalle}`;
    if (!/^Sandbox habilitado/.test(ev.sandbox.preflight)) bloqueoGlobal.push(ev.sandbox.preflight);
    guardar();
    if (bloqueoGlobal.length) throw new AbortoPreflight(bloqueoGlobal.join(' '));

    // ---- Sesiones de los actores: UN login por actor, dentro del sandbox ----
    sandboxAbierto = true;
    const correos = { setup: V.QA_SETUP_EMAIL, prod: V.QA_PROD_EMAIL, eng: V.QA_ENG_EMAIL };
    const claves = Object.fromEntries(PLAN.actores.map((r) => [r, claveDe(V, r)]));
    const patrones = { setup: PLAN.patronSetup ?? /./, prod: /productor/i, eng: /ingeniero/i };
    const actores = {};
    for (const rol of PLAN.actores) {
      const r = await cli.solicitar('POST', '/sesiones/', { cuerpo: { correo_electronico: correos[rol], contrasena: claves[rol] }, etiqueta: `Login ${rol}` });
      // Antes de cualquier escritura de datos: el backend debe haber atendido la petición en el sandbox.
      if (r.eco !== runId) throw new AbortoPreflight(`El backend no atendió el login de ${NOMBRE_ROL[rol]} dentro del sandbox (X-Test-Run-Id devuelto: ${r.eco ?? 'ninguno'}). No se escriben datos.`);
      const token = r.status === 200 ? r.json?.token : null;
      if (token) tokens[rol] = token;
      cli.secretos = masSecretos();
      const me = token ? await cli.solicitar('GET', '/usuarios/me', { token, etiqueta: `Perfil ${rol}` }) : null;
      actores[rol] = { token, id: me?.json?.id_usuario ?? null, nombre_rol: me?.json?.nombre_rol ?? null };
      ev.actores.push({ rol: NOMBRE_ROL[rol], correo: correos[rol], nombre_rol: actores[rol].nombre_rol, login_http: r.status });
      if (!token) bloqueoGlobal.push(`Login de ${NOMBRE_ROL[rol]} (${correos[rol]}) respondió HTTP ${r.status}.`);
      else if (!patrones[rol].test(actores[rol].nombre_rol || '')) bloqueoGlobal.push(`La cuenta ${correos[rol]} tiene rol «${actores[rol].nombre_rol}», no el esperado (${patrones[rol]}).`);
    }
    guardar();
    if (bloqueoGlobal.length) throw new AbortoPreflight(bloqueoGlobal.join(' '));

    // ---- DESCUBRIMIENTO (solo lectura) ---------------------------------------
    ev.ejecucion.fase = 'DESCUBRIMIENTO';
    const S = actores.setup.token;
    const get = async (ruta, etiqueta, token = S) => (await cli.solicitar('GET', ruta, { token, etiqueta })).json;

    const catalogoVariables = (await get('/configuracion/variables-ambientales', 'Catálogo de variables'))?.items ?? [];
    const variables = {};
    for (const id of PLAN.variables) {
      const v = catalogoVariables.find((x) => Number(x.id_variable_ambiental) === id);
      if (v) variables[id] = v; else bloqueoGlobal.push(`No se encontró la variable ambiental ${id} activa.`);
    }
    const tipoSensor = ((await get('/configuracion/tipos-dispositivo-iot', 'Tipos de dispositivo'))?.items ?? [])
      .filter((x) => x.categoria === 'SENSOR').sort((a, b) => a.id_tipo_dispositivo - b.id_tipo_dispositivo)[0];
    const tipoArea = ((await get('/configuracion/tipos-area?solo_activos=true', 'Tipos de área'))?.items ?? [])
      .filter((x) => x.es_activo).sort((a, b) => a.id_tipo_area - b.id_tipo_area)[0];
    const rangos = (await get('/configuracion/sensores/rangos-calibracion', 'Rangos de calibración'))?.items ?? [];
    const valorReferencia = {};
    for (const cat of new Set(PLAN.sensores.filter((s) => s.calibrar).map((s) => s.categoria))) {
      const r = rangos.find((x) => x.categoria === cat);
      if (r) valorReferencia[cat] = Number(((Number(r.valor_min) + Number(r.valor_max)) / 2).toFixed(2));
      else bloqueoGlobal.push(`No hay rango de calibración para la categoría ${cat}.`);
    }
    if (!tipoSensor) bloqueoGlobal.push('No hay tipo de dispositivo de categoría SENSOR.');
    if (!tipoArea) bloqueoGlobal.push('No hay tipo de área activo.');
    const especies = ((await get('/configuracion/especies?solo_activas=true', 'Especies'))?.items ?? [])
      .filter((x) => x.es_activo).sort((a, b) => a.id_especie - b.id_especie);
    if (!especies.length) bloqueoGlobal.push('No hay especies activas.');
    if (bloqueoGlobal.length) throw new AbortoPreflight(bloqueoGlobal.join(' '));

    // Especie: la primera activa que cumple TODOS los requisitos del plan. Se consulta antes
    // de escribir nada: destinos Edge (SECURITY DEFINER, sin RLS), umbrales previos y métricas.
    const evaluadas = [];
    let especie = null;
    for (const e of especies.slice(0, 40)) {
      const motivos = [];
      for (const req of PLAN.especie.requisitos) {
        if (req === 'sin_gateway') {
          const f = await sql(`SELECT count(*) AS n FROM modulo9.fn_seriales_gateway_edge_por_especie(${literalSql(e.id_especie)})`);
          if (!f || !f[0]) motivos.push('destinos Edge no verificables');
          else if (Number(f[0].n) > 0) motivos.push(`${f[0].n} Gateway Edge destino (propagación MQTT)`);
        } else if (req.startsWith('sin_umbral:')) {
          const idVar = Number(req.split(':')[1]);
          const u = await get(`/configuracion/umbrales?id_especie=${e.id_especie}`, `Umbrales de la especie ${e.id_especie}`);
          if (!u) motivos.push('umbrales no consultables');
          else if ((u.items ?? []).some((x) => Number(x.id_variable_ambiental) === idVar)) motivos.push(`ya tiene umbral para la variable ${idVar}`);
        } else if (req === 'sin_metricas_obligatorias_individual') {
          const m = await get(`/configuracion/metricas?id_especie=${e.id_especie}&solo_activas=true`, `Métricas de la especie ${e.id_especie}`);
          if (!m) motivos.push('métricas no consultables');
          else if ((m.items ?? []).some((x) => x.es_obligatorio && ['INDIVIDUAL', 'AMBOS'].includes(x.aplica_a_tipo_activo))) motivos.push('métricas obligatorias para INDIVIDUAL');
        }
        if (motivos.length) break;
      }
      evaluadas.push({ id_especie: e.id_especie, nombre: e.nombre, descartada_por: motivos });
      if (!motivos.length) { especie = e; break; }
    }
    if (!especie) {
      ev.preflight.descubrimiento = { especies_evaluadas: evaluadas };
      throw new AbortoPreflight(`Ninguna especie activa cumple los requisitos del plan (${PLAN.especie.requisitos.join(', ')}); preparar el escenario exigiría escribir sobre configuraciones ajenas o publicar por MQTT.`);
    }

    const fincasDe = async (rol) => new Set(((await get('/configuracion/fincas', `Fincas visibles (${rol})`, actores[rol].token))?.items ?? []).map((f) => f.id_finca));
    const visibles = {};
    for (const rol of PLAN.actores) visibles[rol] = await fincasDe(rol);
    const compartidas = [...visibles.setup].filter((id) => PLAN.actores.every((rol) => visibles[rol].has(id))).sort((a, b) => a - b);

    const ctx = { runId, sello, variables, especie: especie.id_especie, sensores: {} };
    const derivados = PLAN.derivar(ctx);
    if (derivados.bloqueos.length) throw new AbortoPreflight(derivados.bloqueos.join(' '));
    ctx.derivados = derivados.valores;
    ev.preflight.descubrimiento = {
      tipo_dispositivo_sensor: tipoSensor.id_tipo_dispositivo,
      tipo_area: tipoArea.nombre,
      valor_referencia_calibracion: valorReferencia,
      especie_elegida: { id: especie.id_especie, nombre: especie.nombre },
      especies_evaluadas: evaluadas,
      fincas_visibles: { ...Object.fromEntries(Object.entries(visibles).map(([k, s]) => [k, s.size])), compartidas_por_todos: compartidas },
    };
    guardar();

    // ---- PREPARACIÓN (APIs oficiales, dentro del sandbox) --------------------
    ev.ejecucion.fase = 'PREPARACION';
    const crear = async (metodo, ruta, cuerpo, etiqueta, orden = ['setup', 'eng'].filter((r) => PLAN.actores.includes(r))) => {
      let ultimo;
      for (const rol of orden) {
        ultimo = await cli.solicitar(metodo, ruta, { token: actores[rol].token, cuerpo, etiqueta: `${etiqueta} (${rol})` });
        if (ultimo.status === 201 || ultimo.status === 200) return { ...ultimo, rol };
        if (ultimo.status !== 403) break;
      }
      throw new AbortoPreflight(`${etiqueta}: HTTP ${ultimo.status} ${JSON.stringify(sanitizar(ultimo.json, masSecretos()))}`);
    };
    const entidad = (nombre, id, origen) => ev.datos.entidades.push({ entidad: nombre, id, origen });

    // Finca: compartida por todos los actores; si no existe, se crea (solo el Administrador
    // puede) con acceso para el Productor y se agrega de forma aditiva al Ingeniero.
    let idFinca;
    if (compartidas.length) {
      idFinca = compartidas[0];
      ev.datos.estrategia_finca = `Finca existente ${idFinca}, visible para todos los actores; solo se le agrega un área nueva del RUN (la finca no se modifica).`;
      entidad('Finca', idFinca, 'Existente (reutilizada, solo lectura)');
    } else {
      const f = await crear('POST', '/configuracion/fincas', {
        // El nombre de finca solo admite letras y espacios: los dígitos se transcriben a letras.
        nombre: `QA Monitoreo ${GRUPO.corto} ${sello}`.replace(/\d/g, (d) => 'abcdefghij'[Number(d)]).slice(0, 55),
        ubicacion: { departamento: 'Huila', municipio: 'Neiva', vereda: 'QA', latitud: 2.9273, longitud: -75.2819 },
        tamano_h: 1,
        id_usuario: actores.prod.id,
      }, 'Crear finca QA (acceso del creador y del Productor)', ['setup']);
      idFinca = f.json.id_finca;
      entidad('Finca', idFinca, `Creada en el RUN (${f.rol})`);
      ev.datos.estrategia_finca = `Sin finca compartida por todos los actores: se creó la finca ${idFinca} con id_usuario = Productor.`;
      for (const rol of PLAN.actores.filter((r) => !['setup', 'prod'].includes(r))) {
        // Asignación ADITIVA: se reenvían todas las fincas que el actor ya ve más la nueva,
        // dentro del sandbox (se revierte con el rollback del RUN).
        const previas = [...visibles[rol]];
        const r = await cli.solicitar('PUT', `/usuarios/${actores[rol].id}/fincas`, { token: S, cuerpo: { ids_fincas: [...previas, idFinca] }, etiqueta: `Asignar la finca del RUN a ${NOMBRE_ROL[rol]} (aditivo)` });
        const despues = await fincasDe(rol);
        const conservadas = previas.every((id) => despues.has(id));
        if (r.status === 200 && despues.has(idFinca) && conservadas) {
          ev.datos.estrategia_finca += ` Se agregó la finca a ${NOMBRE_ROL[rol]} conservando sus ${previas.length} finca(s) previas (verificado).`;
        } else {
          const msg = `No fue posible dar a ${NOMBRE_ROL[rol]} acceso a la finca del RUN de forma aditiva (PUT HTTP ${r.status}; finca visible: ${despues.has(idFinca)}; previas conservadas: ${conservadas}).`;
          ev.datos.dependencias.push(msg);
          bloquear(PLAN.alcance[rol] ?? [], msg);
        }
      }
    }

    const area = await crear('POST', '/configuracion/infraestructuras', {
      nombre_infraestructura: `QA ${GRUPO.corto} ${sello}`,
      tipo_area: tipoArea.nombre,
      superficie: 25,
      finca_id: idFinca,
      descripcion_infraestructura: `QA ${runId}`,
      especie_id: especie.id_especie,
    }, 'Crear área QA', ['setup']);
    const idArea = area.json.id_infraestructura;
    entidad('Área productiva', `${idArea} (especie ${especie.id_especie})`, `Creada en el RUN (${area.rol})`);

    const disp = await crear('POST', '/configuracion/dispositivos-iot', {
      serial,
      descripcion: `QA ${GRUPO.corto} ${sello}`,
      id_infraestructura: idArea,
      id_tipo_dispositivo: tipoSensor.id_tipo_dispositivo,
      es_activo: true,
    }, 'Registrar dispositivo QA (sin gateway: no hay sincronización MQTT)');
    dispositivoCreado = true;
    const idDisp = disp.json.id_dispositivo_iot;
    entidad('Dispositivo IoT', `${idDisp} (serial ${enmascararClaveIot(serial)}, prefijo ${pref.origen})`, `Creado en el RUN (${disp.rol})`);

    for (const plan of PLAN.sensores) {
      const nombre = `QA ${GRUPO.corto} ${sello} ${plan.clave}`;
      const s = await crear('POST', `/configuracion/dispositivos-iot/${idDisp}/sensores`, { nombre, categoria: plan.categoria }, `Registrar sensor ${plan.clave}`);
      ctx.sensores[plan.clave] = { id: s.json.id_sensores, nombre };
      idsSensoresRun.push(s.json.id_sensores);
      await crear('POST', `/configuracion/sensores/${s.json.id_sensores}/asociar`, { id_dispositivo_iot: idDisp, id_infraestructura: idArea, punto_instalacion: `QA ${GRUPO.corto} ${plan.clave}` }, `Asociar sensor ${plan.clave} al área`);
      if (plan.calibrar) {
        const c = await crear('POST', `/configuracion/sensores/${s.json.id_sensores}/calibrar`, {
          id_dispositivo_iot: idDisp,
          id_infraestructura: idArea,
          valor_referencia: valorReferencia[plan.categoria],
          ganancia: 1.0,
          offset: 0,
          fecha_calibracion: new Date(Date.now() - 10 * 60000).toISOString(),
          observaciones: `QA ${runId}`,
          modo_calibracion: 'SENSOR',
        }, `Calibrar sensor ${plan.clave} (ganancia 1, offset 0)`);
        entidad(`Sensor ${plan.clave}`, s.json.id_sensores, `Creado, asociado y calibrado en el RUN (calibración ${c.json.id_calibracion})`);
      } else {
        entidad(`Sensor ${plan.clave}`, s.json.id_sensores, 'Creado y asociado en el RUN, SIN calibración');
      }
    }

    let idActivo = null;
    if (PLAN.activo) {
      const hoy = new Date();
      const fecha = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
      const a = await crear('POST', '/activos-biologicos', {
        tipo_activo: 'INDIVIDUAL',
        id_especie: especie.id_especie,
        fecha_inicio_ciclo: fecha(hoy),
        origen_financiero: 'nacimiento',
        id_infraestructura: idArea,
        identificador: `QA-${GRUPO.corto}-${sello}`,
        raza: 'QA',
        sexo: 'Macho',
        fecha_nacimiento: new Date(hoy.getTime() - 365 * 86400000).toISOString(),
      }, 'Registrar el único activo biológico del área (INDIVIDUAL)', ['setup']);
      idActivo = a.json?.id_activo_biologico ?? null;
      entidad('Activo biológico', idActivo, 'Creado en el RUN: único activo operativo del área (RF-61 exige uno para VINCULAR y clasificar)');
    }
    Object.assign(ctx, { idArea, idDisp, idActivo });

    // ---- VERIFICACIÓN de lo preparado ---------------------------------------
    const lista = await get(`/configuracion/dispositivos-iot/${idDisp}/sensores`, 'Verificar sensores del dispositivo');
    const activos = new Set((lista?.items ?? []).filter((x) => x.es_activo).map((x) => x.id_sensores));
    for (const plan of PLAN.sensores) {
      const s = ctx.sensores[plan.clave];
      if (!activos.has(s.id)) bloqueoGlobal.push(`El sensor ${plan.clave} no figura activo en el dispositivo.`);
      const cal = await get(`/configuracion/sensores/${s.id}/calibraciones`, `Verificar calibración del sensor ${plan.clave}`);
      if (plan.calibrar && !(cal?.total >= 1)) bloqueoGlobal.push(`El sensor ${plan.clave} no quedó calibrado.`);
      if (!plan.calibrar && cal?.total !== 0) bloqueoGlobal.push(`El sensor ${plan.clave} debía quedar sin calibración y tiene ${cal?.total}.`);
    }
    if (PLAN.activo) {
      const l = await get(`/activos-biologicos?id_infraestructura=${idArea}&page_size=100`, 'Verificar activos del área');
      if (l?.total !== 1) bloqueoGlobal.push(`El área debe tener exactamente un activo operativo y tiene ${l?.total}.`);
    }
    for (const [rol, casos] of Object.entries(PLAN.alcance)) {
      const r = await cli.solicitar('GET', `/configuracion/infraestructuras/${idArea}`, { token: actores[rol].token, etiqueta: `Alcance del área (${rol})` });
      if (r.status !== 200) {
        const msg = `${NOMBRE_ROL[rol]} no tiene alcance sobre el área del RUN (GET HTTP ${r.status}).`;
        ev.datos.dependencias.push(msg);
        bloquear(casos, msg);
      }
    }
    if (bloqueoGlobal.length) throw new AbortoPreflight(bloqueoGlobal.join(' '));

    // ---- AISLAMIENTO antes de los escenarios ---------------------------------
    const dentro = await sondear(runId);
    const fuera = await sondaExterna('SONDA', 'Cierre de la sonda de aislamiento');
    ev.sandbox.aislamiento_previo = { dentro_del_run: dentro, otra_transaccion: fuera };
    if (fuga(fuera)) throw new AbortoPreflight(`FUGA: el fixture es visible fuera del sandbox ${JSON.stringify(fuera)}. Posible escritura persistente en TEST: escalar a DBA.`);
    ev.sandbox.aislamiento = dentro.auditoria_dispositivo === 1 && fuera.auditoria_dispositivo === 0
      ? 'Demostrado antes de los escenarios: el INSERT del dispositivo consta en auditoria.logs_dml dentro del RUN (1) y no desde otra transacción (0).'
      : `No demostrable antes de los escenarios con auditoria.logs_dml (${JSON.stringify(dentro)} / ${JSON.stringify(fuera)}); se verifica con modulo3.telemetrias tras Newman.`;
    guardar();

    // ---- ESCENARIOS: Newman ---------------------------------------------------
    ev.ejecucion.fase = 'ESCENARIOS_API';
    ev.ejecucion.escenarios_iniciados = true;
    const archivoEnv = temporal('entorno.json');
    const jsonNewman = temporal('newman.json');
    const valoresEnv = entornoBaseNewman({ ctx, base: API, runId, secreto: V.QA_SANDBOX_SECRET, serial, tokens });
    fs.writeFileSync(archivoEnv, JSON.stringify({ name: `${GRUPO.id} ${runId}`, values: Object.entries(valoresEnv).map(([key, value]) => ({ key, value, enabled: true })) }), { encoding: 'utf8', mode: 0o600 });
    const reporters = htmlextraDisponible() ? 'json,htmlextra' : 'json';
    const argsNewman = ['run', RUTAS.coleccion, '-e', archivoEnv, '--reporters', reporters,
      '--reporter-json-export', jsonNewman, '--timeout-request', '30000', '--color', 'off', '--disable-unicode', '--ignore-redirects'];
    if (reporters.includes('htmlextra')) {
      const dirNewman = path.join(dirRun, 'newman');
      fs.mkdirSync(dirNewman);
      argsNewman.push('--reporter-htmlextra-export', path.join(dirNewman, `newman-${GRUPO.id}.html`),
        '--reporter-htmlextra-title', `${GRUPO.id} ${runId}`,
        '--reporter-htmlextra-skipHeaders', 'Authorization,X-Sandbox-Secret',
        '--reporter-htmlextra-skipEnvironmentVars', ['sandbox_secret', 'access_key', ...Object.keys(valoresEnv).filter((k) => k.startsWith('tok_'))].join(','));
    }
    const rNewman = spawnSync('newman', argsNewman, { encoding: 'utf8', shell: process.platform === 'win32', maxBuffer: 64 * 1024 * 1024 });
    fs.rmSync(archivoEnv, { force: true });
    let reporte = null;
    if (fs.existsSync(jsonNewman)) {
      try { reporte = JSON.parse(fs.readFileSync(jsonNewman, 'utf8')); } catch { reporte = null; }
    }
    fs.rmSync(jsonNewman, { force: true });
    if (!reporte) {
      ev.newman = { codigo_salida: rNewman.status, salida_error: redactarTexto(`${rNewman.stderr || ''}`.slice(-2000), masSecretos()) };
      bloquear(CASOS.map((c) => c.id), 'AUTOMATIZACION: Newman no produjo su reporte (ver evidencia.newman.salida_error).');
    } else {
      ev.newman = { codigo_salida: rNewman.status, ...resumenNewman(reporte, idsSensoresRun) };
      ev.resultados.push(...resultadosDesdeNewman(reporte));
      const inc = incidenciasNewman(reporte);
      ev.incidencias_ejecucion.general.push(...inc.general);
      Object.assign(ev.incidencias_ejecucion.porCaso, inc.porCaso);
      if (inc.general.length) bloquear(CASOS.map((c) => c.id), `Pasos de preparación de la colección fallidos: ${inc.general.join(' | ')}`);
      for (const [caso, lista2] of Object.entries(inc.porCaso)) bloquear([caso], lista2.join(' '));
    }
    const tras = await sondear(runId);
    const trasFuera = await sondaExterna('SONDA2', 'Cierre de la sonda tras Newman');
    ev.sandbox.aislamiento_tras_api = { dentro_del_run: tras, otra_transaccion: trasFuera };
    if (fuga(trasFuera)) throw new AbortoPreflight(`FUGA tras Newman: lecturas del RUN visibles fuera del sandbox ${JSON.stringify(trasFuera)}. Escalar a DBA.`);
    if (!fixtureVivo(tras)) {
      bloquear(CASOS.map((c) => c.id), `INFRAESTRUCTURA: el sandbox no contiene el fixture tras Newman (posible expiración por inactividad de 180 s): ${JSON.stringify(tras)}.`);
    } else if (!/^Demostrado/.test(ev.sandbox.aislamiento) && tras.telemetrias > 0 && trasFuera.telemetrias === 0) {
      ev.sandbox.aislamiento = `Demostrado tras Newman: ${tras.telemetrias} lecturas del RUN en modulo3.telemetrias dentro del RUN y 0 desde otra transacción.`;
    }
    guardar();

    // ---- ESCENARIOS: Cypress --------------------------------------------------
    if (USA_UI) {
      ev.ejecucion.fase = 'ESCENARIOS_UI';
      delete process.env.ELECTRON_RUN_AS_NODE;
      const dirCapturas = path.join(dirRun, 'capturas');
      fs.mkdirSync(dirCapturas);
      const descargas = temporal('descargas');
      let resCy;
      try {
        resCy = await cy.cypress.run({
          project: RUTAS.dirGrupo,
          configFile: false,
          testingType: 'e2e',
          spec: RUTAS.cypressSpec,
          browser: 'electron',
          headless: true,
          quiet: true,
          config: configuracionCypress({ baseUrl: FRONT, capturas: dirCapturas, descargas }),
          env: entornoBaseCypress({ ctx, api: API, runId, secreto: V.QA_SANDBOX_SECRET, correos, claves }),
        });
      } catch (e) {
        resCy = { status: 'failed', message: String(e.message || e) };
      }
      fs.rmSync(descargas, { recursive: true, force: true });
      if (!resCy || resCy.status === 'failed') {
        bloquear(PLAN.casosUI, `AUTOMATIZACION: Cypress no pudo ejecutarse: ${redactarTexto(resCy?.message ?? 'sin detalle', masSecretos())}`);
      } else {
        ev.resultados.push(...resultadosDesdeCypress(resCy));
        ev.cypress = {
          totales: { pruebas: resCy.totalTests, aprobadas: resCy.totalPassed, fallidas: resCy.totalFailed, pendientes: resCy.totalPending, omitidas: resCy.totalSkipped },
          duracion_ms: resCy.totalDuration,
          navegador: `${resCy.browserName} ${resCy.browserVersion}`,
          pruebas: (resCy.runs ?? []).flatMap((r) => r.tests ?? []).map((t) => ({
            titulo: Array.isArray(t.title) ? t.title[t.title.length - 1] : String(t.title),
            estado: t.state,
            error: t.state === 'failed' ? redactarTexto(String(t.displayError || '').split('\n')[0], masSecretos()) : undefined,
          })),
        };
      }
      if (fs.existsSync(dirCapturas) && fs.readdirSync(dirCapturas).length === 0) fs.rmdirSync(dirCapturas);
      const trasUi = await sondear(runId);
      ev.sandbox.tras_ui = trasUi;
      if (!fixtureVivo(trasUi)) bloquear(PLAN.casosUI, `INFRAESTRUCTURA: el sandbox no contiene el fixture tras Cypress: ${JSON.stringify(trasUi)}.`);
      ev.sandbox.ui = 'Peticiones de la UI con las cabeceras del sandbox, serializadas (la sesión de BD del sandbox es compartida); PRE-UI-01 exige el mismo X-Test-Run-Id en el dashboard.';
    }
    ev.ejecucion.fase = 'CIERRE';
    guardar();
  } catch (e) {
    if (e instanceof AbortoPreflight) {
      ev.ejecucion.estado = ev.ejecucion.escenarios_iniciados ? ESTADOS_RUN.INTERRUMPIDA : ESTADOS_RUN.ABORTADA_PREFLIGHT;
      ev.ejecucion.motivo_aborto = e.message;
    } else {
      ev.ejecucion.estado = ESTADOS_RUN.INTERRUMPIDA;
      ev.ejecucion.motivo_aborto = `Error no controlado del ejecutor: ${e.stack || e.message}`;
    }
  } finally {
    try { await cerrarSandbox(); } catch (e) { ev.sandbox.cierre = `Error al cerrar: ${e.message}`; }
    process.removeListener('SIGINT', alSigint);
    process.removeListener('SIGTERM', alSigterm);
    limpiarTemporales();
  }

  // ---- Veredictos y artefactos (informe + evidencia.json; HTML y capturas si existen) ----
  ev.ejecucion.fin = ahoraIso();
  const veredictos = CASOS.map((c) => veredictoCaso(c, ev.resultados, ev.bloqueos[c.id] ?? []));
  ev.resultado_propuesto = { casos: veredictos, grupo: estadoGrupo(veredictos), naturaleza: 'PROPUESTO — requiere revisión QA' };
  if (ev.ejecucion.estado === ESTADOS_RUN.EN_CURSO) ev.ejecucion.estado = ESTADOS_RUN.CONCLUIDA;
  ev.sanitizacion = escanearYRedactarDirectorio(dirRun, masSecretos());
  if (ev.ejecucion.estado === ESTADOS_RUN.CONCLUIDA) {
    const nombre = nombreInforme(GRUPO.id, ev.ejecucion.version);
    ev.archivos = [...new Set([...listarArchivos(dirRun), nombre])].sort();
    guardar();
    const informe = generarInforme(sanitizar(ev, masSecretos()), inspeccionarHistorial(RUTAS.dirGrupo), GRUPO, CASOS);
    escribirNuevo(path.join(dirRun, nombre), redactarTexto(informe, masSecretos()));
  } else {
    ev.archivos = listarArchivos(dirRun);
    guardar();
  }

  const resumen = [
    `RUN ${runId} — V${ev.ejecucion.version} — estado ${ev.ejecucion.estado}`,
    ev.ejecucion.motivo_aborto ? `Motivo: ${redactarTexto(ev.ejecucion.motivo_aborto, masSecretos())}` : null,
    ...veredictos.map((v) => `  ${v.caso}: ${v.estado} (propuesto) — ${v.motivo}`),
    `  Grupo: ${ev.resultado_propuesto.grupo} (propuesto)`,
    `  Sandbox: ${ev.sandbox.cierre ?? '—'} | Rollback: ${ev.sandbox.rollback_confirmado ?? '—'}`,
    `  Resultados: ${path.relative(RUTAS.dirGrupo, dirRun)}`,
  ].filter(Boolean).join('\n');
  return fin(ev.ejecucion.estado === ESTADOS_RUN.CONCLUIDA ? 0 : 5, resumen);
}

// ---------------------------------------------------------------------------
// Entrada
// ---------------------------------------------------------------------------

const args = leerArgumentos(process.argv.slice(2));
if (args.error) {
  console.error(`${args.error}\n${AYUDA}`);
  process.exit(1);
}
if (args.modo === 'ayuda') {
  console.log(AYUDA);
  process.exit(0);
}
if (args.modo === 'local') {
  const comprobaciones = await validacionLocal();
  const fallos = comprobaciones.filter((c) => !c.cumple).length;
  console.log(`${GRUPO.id} — VALIDACIÓN LOCAL (sin red, sin resultados oficiales)\n`);
  for (const c of comprobaciones) console.log(`${c.cumple ? '[OK]   ' : '[FALLA]'} ${c.nombre}${c.detalle ? ` — ${c.detalle}` : ''}`);
  console.log(`\n${comprobaciones.length - fallos}/${comprobaciones.length} comprobaciones superadas.`);
  process.exit(fallos ? 1 : 0);
}
process.exit(await ejecucionOficial(args));
