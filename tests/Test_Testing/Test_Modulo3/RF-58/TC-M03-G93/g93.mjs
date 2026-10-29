#!/usr/bin/env node
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import vm from 'node:vm';
import { spawnSync } from 'node:child_process';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { contextoEjecucion } from './lib/contrato_ejecutor.mjs';
import { evaluarRegistro } from './lib/registro_local.mjs';
import { sanearArtefacto } from './lib/seguridad.mjs';
import { CASO, ORACULO, IDS, LIMITE, CAPACIDADES, CONSULTAS_DIAGNOSTICO, IDS_PREFERIDOS_V2,
  evaluarApi, revisarCandidataV2, clasificar } from './lib/g93_escenario.mjs';
const require = createRequire(import.meta.url);

const DIR = path.dirname(fileURLToPath(import.meta.url));
const RAIZ = path.resolve(DIR, '../../../../..');
const COLECCION = path.join(DIR, 'G93.postman_collection.json');
const SPEC = path.join(DIR, 'g93.cy.js');
const CONFIG_CYPRESS = path.join(DIR, 'g93.cypress.config.cjs');
const guardar = (p, v) => fs.writeFileSync(p, JSON.stringify(v, null, 2));
const fallo = (mensaje) => { throw new Error(mensaje); };
const exigir = (condicion, mensaje) => { if (!condicion) fallo(mensaje); };
const limpio = (texto, secretos) => sanearArtefacto(String(texto), secretos).slice(0, 300);
// Solo para comprobar versiones; no modifica los límites de la evaluación.
const LIMITE_VERSION_HERRAMIENTA_MS = 30000;

export function resolverCliNewman(pathEnv = process.env.PATH, raiz = RAIZ) {
  for (const carpeta of String(pathEnv ?? '').split(path.delimiter).filter(Boolean)) {
    if (!['newman', 'newman.cmd'].some(nombre => fs.existsSync(path.join(carpeta, nombre)))) continue;
    const cli = path.join(carpeta, 'node_modules', 'newman', 'bin', 'newman.js');
    if (fs.existsSync(cli)) return cli;
  }
  try {
    const paquete = require.resolve('newman/package.json', { paths: [raiz] });
    const cli = path.join(path.dirname(paquete), 'bin', 'newman.js');
    if (fs.existsSync(cli)) return cli;
  } catch { /* dependencia no instalada en el backend */ }
  fallo('NEWMAN_CLI_NO_RESUELTO');
}

export function invocarNewman(args, timeout, { cli = resolverCliNewman(), spawn = spawnSync } = {}) {
  return spawn(process.execPath, [cli, ...args], { encoding: 'utf8', shell: false, timeout });
}

export function leerEnv(proceso = process.env, { cargarArchivo = true } = {}) {
  const env = {};
  const archivo = path.join(RAIZ, '.env.qa');
  if (cargarArchivo && fs.existsSync(archivo)) for (const linea of fs.readFileSync(archivo, 'utf8').split(/\r?\n/)) {
    const m = linea.match(/^\s*([A-Z0-9_]+)\s*=(.*)$/);
    if (m) env[m[1]] = m[2].trim().replace(/^(['"])(.*)\1$/, '$2');
  }
  Object.assign(env, proceso);
  env.QA_AUTORIZADO = proceso.QA_AUTORIZADO;
  return env;
}

export async function buscarCandidataV2({ dispositivos, fincasVisibles, idAreaV1, get, excluidos = [],
  maxCandidatas = LIMITE.candidatas, maxPaginasAdicionales = LIMITE.paginas_adicionales_v2 }) {
  const revisiones = [];
  const ids = [...new Set((Array.isArray(dispositivos) ? dispositivos : [])
    .map(x => Number(x.id_infraestructura)).filter(x => Number.isSafeInteger(x) && x > 0))];
  let paginasRestantes = maxPaginasAdicionales;
  let candidatasRevisadas = 0;
  for (const id of ids) {
    if (excluidos.includes(id)) continue;
    if (idAreaV1 != null && id === Number(idAreaV1)) {
      revisiones.push({ id_infraestructura: id, motivo: 'area_v1' });
      continue;
    }
    if (candidatasRevisadas >= maxCandidatas) break;
    candidatasRevisadas++;
    const primera = await get(`/iot/monitoreo/dashboard/${id}?pagina=1&por_pagina=50`);
    const cuerpo = primera.cuerpo ?? {};
    const unidad = (Array.isArray(cuerpo.resumen_unidades) ? cuerpo.resumen_unidades : [])
      .find(x => Number(x.id_infraestructura) === id);
    const total = Number(unidad?.total_sensores);
    const paginas = Number.isSafeInteger(total) && total > 0 ? Math.ceil(total / 50) : 1;
    const sensores = Array.isArray(cuerpo.sensores) ? [...cuerpo.sensores] : [];
    let completa = true;
    if (primera.http === 200 && unidad && fincasVisibles.includes(Number(unidad.id_finca))) {
      for (let pagina = 2; pagina <= paginas; pagina++) {
        if (paginasRestantes === 0) { completa = false; break; }
        paginasRestantes--;
        const siguiente = await get(`/iot/monitoreo/dashboard/${id}?pagina=${pagina}&por_pagina=50`);
        if (siguiente.http !== 200) { completa = false; break; }
        sensores.push(...(Array.isArray(siguiente.cuerpo?.sensores) ? siguiente.cuerpo.sensores : []));
      }
    }
    const revision = revisarCandidataV2({ http: primera.http,
      cuerpo: { ...cuerpo, sensores } }, id, { fincasVisibles, idAreaV1 });
    if (!completa && revision.motivo !== 'sensor_fuera_estados_sin_comunicacion') revision.motivo = 'paginacion_incompleta';
    revisiones.push(revision);
    if (revision.motivo === 'aceptada') return { encontrada: { id, pagina: primera }, revisiones,
      candidatasRevisadas, paginasUsadas: maxPaginasAdicionales - paginasRestantes };
  }
  return { encontrada: null, revisiones, candidatasRevisadas,
    paginasUsadas: maxPaginasAdicionales - paginasRestantes };
}

const BASE_FRONT_TEST_OBSERVADA = 'https://api.inmero.co/api-sgpmp-test';
// El frontend de TEST solicita este host sin www; Cypress debe interceptar esa URL real.
const API_FRONT_TEST = BASE_FRONT_TEST_OBSERVADA;
const BASES_API_TEST = new Set([BASE_FRONT_TEST_OBSERVADA,
  'https://www.api.inmero.co/api-sgpmp-test']);

export function baseAlternativaTest(base) {
  if (!BASES_API_TEST.has(base)) return null;
  const url = new URL(base);
  url.hostname = url.hostname.startsWith('www.') ? url.hostname.slice(4) : `www.${url.hostname}`;
  const alternativa = `${url.origin}${url.pathname}`;
  return BASES_API_TEST.has(alternativa) ? alternativa : null;
}

function comparacionBaseFrontend(base) {
  const principal = new URL(base);
  const observada = new URL(BASE_FRONT_TEST_OBSERVADA);
  return { coincide: base === BASE_FRONT_TEST_OBSERVADA,
    esquema: principal.protocol.slice(0, -1), host: principal.hostname,
    path_base: principal.pathname, base_frontend_observada: BASE_FRONT_TEST_OBSERVADA,
    diferencias: [principal.protocol !== observada.protocol ? 'esquema' : null,
      principal.hostname !== observada.hostname ? 'host_con_sin_www' : null,
      principal.pathname !== observada.pathname ? 'path' : null].filter(Boolean) };
}

function errorTransporteSeguro(error) {
  const codigo = [error?.code, error?.cause?.code, error?.name].find(x => typeof x === 'string');
  if (['TimeoutError', 'AbortError', 'ETIMEDOUT'].includes(codigo))
    return { codigo: 'TIMEOUT', mensaje: 'Tiempo de espera agotado', permite_alternativa: true };
  if (error instanceof TypeError || ['ENOTFOUND', 'EAI_AGAIN', 'ECONNREFUSED',
    'ECONNRESET', 'EHOSTUNREACH', 'ENETUNREACH'].includes(codigo))
    return { codigo: 'ERROR_RED', mensaje: 'Error de red', permite_alternativa: true };
  return { codigo: 'ERROR_TRANSPORTE', mensaje: 'Error de transporte no clasificado',
    permite_alternativa: false };
}

async function diagnosticoAutenticacion({ consultas, maxPeticiones, env, fetcher, directorio, ahora }) {
  const base = String(env.SIGAB_API_TEST_BASE ?? '').replace(/\/+$/, '');
  exigir(BASES_API_TEST.has(base) && env.QA_ADMIN_EMAIL && env.QA_ADMIN_PASSWORD
    && env.QA_PROD_EMAIL && env.QA_PROD_PASSWORD, 'DIAGNOSTICO_CONFIG_INVALIDA');
  exigir(maxPeticiones >= 4, 'DIAGNOSTICO_LIMITE_INVALIDO');
  const alternativa = baseAlternativaTest(base);
  const ts = `${ahora.getUTCFullYear()}${String(ahora.getUTCMonth() + 1).padStart(2, '0')}`
    + `${String(ahora.getUTCDate()).padStart(2, '0')}-${String(ahora.getUTCHours()).padStart(2, '0')}`
    + `${String(ahora.getUTCMinutes()).padStart(2, '0')}${String(ahora.getUTCSeconds()).padStart(2, '0')}`;
  const salida = `diagnostico/DIAG-G93-${ts}`;
  const carpeta = path.join(directorio, salida);
  fs.mkdirSync(path.dirname(carpeta), { recursive: true });
  fs.mkdirSync(carpeta, { recursive: false });
  const solicitudes = [];
  async function solicitar(rol, correo, contrasena, baseUsada, nombreBase) {
    exigir(solicitudes.length < 4 && solicitudes.length < maxPeticiones,
      'DIAGNOSTICO_LIMITE_EXCEDIDO');
    const url = new URL(baseUsada);
    exigir(BASES_API_TEST.has(baseUsada), 'DIAGNOSTICO_HOST_FUERA_TEST');
    const registro = { base: nombreBase, host: url.hostname, path_base: url.pathname,
      rol, http: null, duracion_ms: 0, error: null, con_token: false,
      con_cookie_refresco: false };
    solicitudes.push(registro);
    const inicio = Date.now();
    let respuesta;
    try {
      respuesta = await fetcher(baseUsada + '/sesiones/', { method: 'POST',
        headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
        body: JSON.stringify({ correo_electronico: correo, contrasena }),
        redirect: 'manual', signal: AbortSignal.timeout(30000) });
    } catch (error) {
      const seguro = errorTransporteSeguro(error);
      registro.duracion_ms = Date.now() - inicio;
      registro.error = { codigo: seguro.codigo, mensaje: seguro.mensaje };
      return seguro.permite_alternativa;
    }
    registro.http = respuesta.status;
    try {
      const cuerpo = await respuesta.json();
      registro.con_token = typeof cuerpo?.token === 'string' && cuerpo.token.length > 0;
    } catch { registro.error = { codigo: 'RESPUESTA_NO_JSON', mensaje: 'Respuesta no JSON' }; }
    try {
      registro.con_cookie_refresco = /(?:^|,\s*)refresh_token=/.test(
        respuesta.headers?.get('set-cookie') ?? '');
    } catch { /* No se conserva la cabecera */ }
    registro.duracion_ms = Date.now() - inicio;
    return false;
  }
  for (const [rol, correo, contrasena] of [
    ['Administrador', env.QA_ADMIN_EMAIL, env.QA_ADMIN_PASSWORD],
    ['Productor', env.QA_PROD_EMAIL, env.QA_PROD_PASSWORD]]) {
    const falloRed = await solicitar(rol, correo, contrasena, base, 'principal');
    if (falloRed && alternativa) await solicitar(rol, correo, contrasena,
      alternativa, 'alternativa');
  }
  const comparacion_frontend = comparacionBaseFrontend(base);
  const autenticacion = { grupo: 'G93', comparacion_frontend, solicitudes };
  const resumen = { salida, peticiones_realizadas: solicitudes.length,
    consultas: solicitudes.map(() => consultas[0]), comparacion_frontend, solicitudes };
  guardar(path.join(carpeta, 'autenticacion.json'), autenticacion);
  fs.writeFileSync(path.join(carpeta, 'bitacora_resumen.json'), JSON.stringify(resumen));
  return resumen;
}

export async function diagnostico({ referencia, consultas, maxPeticiones, env = leerEnv(),
  fetcher = fetch, directorio = DIR, ahora = new Date() }) {
  exigir(env.QA_AUTORIZADO === 'SI' && typeof referencia === 'string' && referencia.length > 0,
    'DIAGNOSTICO_SIN_AUTORIZACION');
  if (Array.isArray(consultas) && consultas.length === 1 && consultas[0] === 'POST /sesiones/') {
    exigir(Number.isSafeInteger(maxPeticiones) && maxPeticiones <= CAPACIDADES.max_peticiones,
      'DIAGNOSTICO_LIMITE_INVALIDO');
    return diagnosticoAutenticacion({ consultas, maxPeticiones, env, fetcher, directorio, ahora });
  }
  const base = String(env.SIGAB_API_TEST_BASE ?? '').replace(/\/+$/, '');
  exigir(base === 'https://www.api.inmero.co/api-sgpmp-test'
    && env.QA_PROD_EMAIL && env.QA_PROD_PASSWORD, 'DIAGNOSTICO_CONFIG_INVALIDA');
  exigir(Array.isArray(consultas) && consultas.length >= 1 && consultas[0] === 'POST /sesiones/'
    && consultas.slice(1).every(x => CONSULTAS_DIAGNOSTICO.includes(x) && x.startsWith('GET ')),
  'DIAGNOSTICO_CONSULTAS_INVALIDAS');
  exigir(Number.isSafeInteger(maxPeticiones) && maxPeticiones > 0
    && maxPeticiones <= CAPACIDADES.max_peticiones && consultas.length <= maxPeticiones,
  'DIAGNOSTICO_LIMITE_INVALIDO');
  const ts = `${ahora.getUTCFullYear()}${String(ahora.getUTCMonth() + 1).padStart(2, '0')}`
    + `${String(ahora.getUTCDate()).padStart(2, '0')}-${String(ahora.getUTCHours()).padStart(2, '0')}`
    + `${String(ahora.getUTCMinutes()).padStart(2, '0')}${String(ahora.getUTCSeconds()).padStart(2, '0')}`;
  const salida = `diagnostico/DIAG-G93-${ts}`;
  const carpeta = path.join(directorio, salida);
  fs.mkdirSync(path.dirname(carpeta), { recursive: true });
  fs.mkdirSync(carpeta, { recursive: false });
  const ejecutadas = [];
  const candidatas = [];
  let token = null;
  try {
    for (const consulta of consultas) {
      exigir(ejecutadas.length < maxPeticiones, 'DIAGNOSTICO_LIMITE_EXCEDIDO');
      const [metodo, ruta] = consulta.split(' ');
      const login = metodo === 'POST';
      const headers = { Accept: 'application/json' };
      if (login) headers['Content-Type'] = 'application/json';
      else headers.Authorization = `Bearer ${token}`;
      const respuesta = await fetcher(base + ruta, { method: metodo, headers,
        body: login ? JSON.stringify({ correo_electronico: env.QA_PROD_EMAIL,
          contrasena: env.QA_PROD_PASSWORD }) : undefined,
        redirect: 'manual', signal: AbortSignal.timeout(30000) });
      ejecutadas.push(consulta);
      let cuerpo = null;
      try { cuerpo = await respuesta.json(); } catch { /* Respuesta no JSON */ }
      if (login) {
        exigir(respuesta.status === 200 && typeof cuerpo?.token === 'string' && cuerpo.token,
          'DIAGNOSTICO_LOGIN_FALLIDO');
        token = cuerpo.token;
      } else {
        const id = Number(new URL(base + ruta).searchParams.get('id_infraestructura'));
        const revision = revisarCandidataV2({ http: respuesta.status, cuerpo }, id,
          { diagnostico: true });
        candidatas.push(revision);
      }
    }
    const resumen = { salida, peticiones_realizadas: ejecutadas.length, consultas: ejecutadas };
    guardar(path.join(carpeta, 'candidatas.json'), { grupo: 'G93', candidatas });
    fs.writeFileSync(path.join(carpeta, 'bitacora_resumen.json'), JSON.stringify(resumen));
    return resumen;
  } catch (e) {
    guardar(path.join(carpeta, 'error.json'), { grupo: 'G93',
      peticiones_realizadas: ejecutadas.length, consultas: ejecutadas,
      error: 'DIAGNOSTICO_FALLIDO' });
    throw new Error('DIAGNOSTICO_FALLIDO');
  }
}

export function comprobar() {
  const fetchAnterior = globalThis.fetch;
  globalThis.fetch = () => fallo('RED_PROHIBIDA_EN_COMPROBAR');
  try {
    const requeridos = ['g93.mjs', 'G93.postman_collection.json', 'g93.cy.js', 'g93.cypress.config.cjs', 'README.md',
      'lib/contrato_ejecutor.mjs', 'lib/seguridad.mjs', 'lib/registro_local.mjs', 'lib/g93_escenario.mjs',
      'lib/g93_ui.cjs', 'pruebas/g93.test.mjs', 'pruebas/g93_arranque_local.mjs'];
    const faltan = requeridos.filter(x => !fs.existsSync(path.join(DIR, x)));
    const c = JSON.parse(fs.readFileSync(COLECCION, 'utf8'));
    for (const e of [...(c.event ?? []), ...(c.item ?? []).flatMap(x => x.event ?? [])])
      new vm.Script((e.script?.exec ?? []).join('\n'));
    const texto = JSON.stringify(c);
    const spec = fs.readFileSync(SPEC, 'utf8');
    const resultadoSintetico = { casos: { [CASO]: { estado: 'APROBADO', motivo: 'API y UI verificadas' } },
      comprobaciones: IDS.map(id => ({ caso: CASO, id, tipo: 'ASSERT', estado: 'APROBADO' })),
      cypress: { total_pruebas: 2 }, cierre: { rollback: { verificado: true } }, oficial: true };
    const encabezado = informe({ ...resultadoSintetico, run_id: 'RUN-LOCAL-SINTETICO', version: 1,
      autorizacion: 'LOCAL_SINTETICO', newman: [],
      cypress: { total_pruebas: 2, detalle: [] }, variantes: { V1: 'APROBADO', V2: 'APROBADO' },
      evidencias: [], directorio: DIR, problemas_tecnicos: [], dependencias: [],
      hallazgos_rendimiento: [], observaciones_documentales: [], consume_version: false,
      cierre: { run: { cierre_http: 200 }, rollback: { verificado: true,
        estado: 'CONFIRMADO', comprobaciones: [] }, motivo: 'Cierre sintético' } });
    const decisionPrimero = encabezado.startsWith('# TC-M03-G93 — APROBADO\n\n## Decisión del caso\n')
      && encabezado.includes('**¿RUN oficial?** Sí') && encabezado.includes('| UI-184-02 | APROBADO |')
      && encabezado.indexOf('## Identificación') > encabezado.indexOf('## Decisión del caso');
    let aprobacionIncompletaBloqueada = false;
    try { bloqueDecisionCaso({ ...resultadoSintetico,
      comprobaciones: resultadoSintetico.comprobaciones.filter(x => x.id !== 'UI-184-02') }); }
    catch (e) { aprobacionIncompletaBloqueada = e.message === 'INFORME_APROBADO_CON_COMPROBACIONES_PENDIENTES'; }
    const valido = !faltan.length && CAPACIDADES.contrato === 'sigab-qa-ejecutor/1'
      && decisionPrimero && aprobacionIncompletaBloqueada
      && IDS.every(x => texto.includes(x) || spec.includes(x)) && CAPACIDADES.comprobaciones_obligatorias[CASO].UI.length === 2
      && c.item.length === 1 && texto.includes('X-Test-Run-Id') && texto.includes('X-Sandbox-Secret')
      && /dashboard\/\{\{id_infraestructura\}\}/.test(c.item[0].request?.url ?? '')
      && !/req\.url\s*=|req\.destroy\(|req\.reply|fixture\(|test-control\/query|--yolo/.test(spec + texto)
      && spec.includes("'dashboardGlobal'") && spec.includes("'dashboardFiltrado'")
      && spec.includes("? 2000 : 60000)") && spec.includes('crearEspera(40000)')
      && spec.includes("req.headers['X-Test-Run-Id'] = RUN");
    console.log(JSON.stringify({ comprobacion: 'G93_LOCAL_SIN_RED', valido, faltan,
      decision_primero: decisionPrimero, aprobacion_incompleta_bloqueada: aprobacionIncompletaBloqueada,
      comprobaciones_obligatorias: CAPACIDADES.comprobaciones_obligatorias, limite: LIMITE }, null, 2));
    return valido ? 0 : 2;
  } finally { globalThis.fetch = fetchAnterior; }
}

export function preflight(contrato, env) {
  const variables = ['SIGAB_API_TEST_BASE', 'SIGAB_FRONT_TEST_URL', 'QA_SANDBOX_SECRET',
    'QA_ADMIN_EMAIL', 'QA_ADMIN_PASSWORD', 'QA_PROD_EMAIL', 'QA_PROD_PASSWORD'];
  const barreras = variables.filter(x => !String(env[x] ?? '').trim());
  for (const x of ['QA_ADMIN_EMAIL', 'QA_PROD_EMAIL'])
    if (env[x] && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(env[x])) barreras.push(`${x}_INVALIDA`);
  if (env.QA_AUTORIZADO !== 'SI') barreras.push('QA_AUTORIZADO');
  if (!CAPACIDADES.operaciones.includes(contrato.operacion)) barreras.push('OPERACION_NO_PUBLICADA');
  if (contrato.version > 1 && contrato.operacion !== 'reevaluar') barreras.push('REEVALUACION_SIN_DECISION');
  for (const x of ['SIGAB_API_TEST_BASE', 'SIGAB_FRONT_TEST_URL'])
    if (!/^https:\/\//.test(env[x] ?? '') || /(^|[-/.])dev([-/.]|$)/i.test(env[x] ?? '')) barreras.push(`${x}_INVALIDA`);
  if (String(env.SIGAB_API_TEST_BASE ?? '').replace(/\/+$/, '') !== 'https://www.api.inmero.co/api-sgpmp-test')
    barreras.push('API_NO_ES_TEST_OFICIAL');
  if (String(env.SIGAB_FRONT_TEST_URL ?? '').replace(/\/+$/, '') !== 'https://api.inmero.co/sigab-test')
    barreras.push('FRONT_NO_ES_TEST_OFICIAL');
  return { fase: 'PREFLIGHT_LOCAL', grupo: 'G93', run_id: contrato.runId, version: contrato.version,
    operacion: contrato.operacion, variables: variables.map(nombre => ({ nombre, presente: Boolean(String(env[nombre] ?? '').trim()) })),
    plan: { finca_candidata: 184, area_referencia: 349, especie: 126, areas_nuevas: 1,
      sensores_nuevos: 0, dispositivos_nuevos: 0, candidatas_v2_max: LIMITE.candidatas,
      validacion: 'GET de alcance Productor, finca y área de referencia antes del POST' },
    limite: LIMITE, barreras, ok: barreras.length === 0 };
}

function resolverCliCypress() {
  const pkg = require('cypress/package.json');
  const binario = process.platform === 'win32' ? 'Cypress/Cypress.exe' : 'Cypress/Cypress';
  if (!fs.existsSync(path.join(process.env.LOCALAPPDATA ?? '', 'Cypress', 'Cache', pkg.version, binario)))
    fallo('CYPRESS_BINARIO_NO_INSTALADO');
  return path.join(path.dirname(require.resolve('cypress/package.json')), 'bin', 'cypress');
}

function salidaVersion(texto, secretos) {
  let salida = limpio(String(texto ?? '').split(/\r?\n/).slice(0, 3).join('\n'), secretos);
  for (const valor of secretos.filter(x => typeof x === 'string' && x.length > 0 && x.length < 4))
    salida = salida.split(valor).join('[REDACTADO]');
  return salida
    .replace(/[A-Za-z]:[\\/][^\s"'<>]*/g, '[RUTA_REDACTADA]')
    .replace(/\/(?:Users|home)\/[^\s"'<>]*/g, '[RUTA_REDACTADA]').slice(0, 300);
}

function comprobarVersion(nombre, ejecutar, secretos) {
  const inicio = Date.now();
  let proceso, error;
  try { proceso = ejecutar(); } catch (e) { error = e; }
  const codigo = proceso?.error?.code ?? error?.code
    ?? (['NEWMAN_CLI_NO_RESUELTO', 'CYPRESS_BINARIO_NO_INSTALADO'].includes(error?.message) ? error.message : null);
  const stdout = salidaVersion(proceso?.stdout, secretos);
  const stderr = salidaVersion(proceso?.stderr, secretos);
  const codigoSaneado = salidaVersion(codigo, secretos);
  const senalSaneada = salidaVersion(proceso?.signal, secretos);
  const diagnostico = {
    comando: `node ${process.version} ${nombre} --version`,
    status: Number.isInteger(proceso?.status) ? proceso.status : null,
    signal: /^[A-Z0-9_]+$/.test(senalSaneada) ? senalSaneada : null,
    error_code: /^[A-Z0-9_]+$/.test(codigoSaneado) ? codigoSaneado : null,
    duracion_ms: Date.now() - inicio,
    vencio_tiempo: codigo === 'ETIMEDOUT',
    stdout, stderr,
    version: (stdout + '\n' + stderr).match(/\b\d+\.\d+\.\d+(?:[-+][\w.-]+)?\b/)?.[0] ?? null,
  };
  return { disponible: diagnostico.status === 0 && !proceso?.error && !error, diagnostico };
}

export function prevalidar(proceso = process.env,
  { resolver = resolverCliNewman, invocar = invocarNewman,
    resolverCypress = resolverCliCypress, invocarCypress = spawnSync } = {}) {
  const env = leerEnv(proceso);
  const previo = preflight({ runId: 'VALIDACION_LOCAL', version: 1, operacion: 'evaluar' },
    { ...env, QA_AUTORIZADO: 'SI' });
  const herramientas = { coleccion: fs.existsSync(COLECCION), spec: fs.existsSync(SPEC),
    newman: false, cypress: false, navegador_chrome: false };
  const secretos = ['SIGAB_API_TEST_BASE', 'SIGAB_FRONT_TEST_URL', 'QA_SANDBOX_SECRET',
    'QA_ADMIN_EMAIL', 'QA_ADMIN_PASSWORD', 'QA_PROD_EMAIL', 'QA_PROD_PASSWORD', 'PATH']
    .map(clave => env[clave]).filter(Boolean);
  const newman = comprobarVersion('newman', () => invocar(['--version'], LIMITE_VERSION_HERRAMIENTA_MS,
    { cli: resolver(proceso.PATH ?? process.env.PATH) }), secretos);
  const cypress = comprobarVersion('cypress', () => invocarCypress(process.execPath,
    [resolverCypress(), '--version'], { encoding: 'utf8', timeout: LIMITE_VERSION_HERRAMIENTA_MS }), secretos);
  herramientas.newman = newman.disponible;
  herramientas.cypress = cypress.disponible;
  const diagnostico_herramientas = { newman: newman.diagnostico, cypress: cypress.diagnostico };
  const candidatos = process.platform === 'win32'
    ? [path.join(process.env.PROGRAMFILES ?? '', 'Google/Chrome/Application/chrome.exe'),
      path.join(process.env['PROGRAMFILES(X86)'] ?? '', 'Google/Chrome/Application/chrome.exe'),
      path.join(process.env.LOCALAPPDATA ?? '', 'Google/Chrome/Application/chrome.exe')]
    : ['/usr/bin/google-chrome', '/usr/bin/chromium', '/usr/bin/chromium-browser'];
  herramientas.navegador_chrome = candidatos.some(x => fs.existsSync(x));
  for (const [nombre, disponible] of Object.entries(herramientas)) if (!disponible) {
    const prefijo = `HERRAMIENTA_${nombre.toUpperCase()}`;
    previo.barreras.push(`${prefijo}_AUSENTE`);
    const d = diagnostico_herramientas[nombre];
    if (d?.vencio_tiempo) previo.barreras.push(`${prefijo}_TIMEOUT`);
    else if (d?.error_code) previo.barreras.push(d.error_code === 'NEWMAN_CLI_NO_RESUELTO'
      || d.error_code === 'CYPRESS_BINARIO_NO_INSTALADO' ? d.error_code : `${prefijo}_${d.error_code}`);
    else if (d?.status != null) previo.barreras.push(`${prefijo}_STATUS_${d.status}`);
  }
  const valido = previo.ok && Object.values(herramientas).every(Boolean);
  return { valido, fase: 'BARRERA_LOCAL', variables: previo.variables,
    barreras: previo.barreras, herramientas, diagnostico_herramientas };
}

export function transporte({ base, runId, secreto, bitacora, fetcher = fetch, limite = LIMITE.solicitudes_directas, local = false }) {
  let abierto = false, cerrado = false, cuenta = 0, remotasEnRun = 0, uiEnCurso = false;
  const permitidos = new Set();
  async function solicitar(metodo, ruta, { token, cuerpo, login = false, cierre = false } = {}) {
    exigir(!uiEnCurso, 'PETICION_DURANTE_CYPRESS');
    const pathname = ruta.split('?')[0];
    if (login) exigir(!abierto && metodo === 'POST' && pathname === '/sesiones/', 'LOGIN_DENTRO_RUN_PROHIBIDO');
    else if (cierre) exigir(abierto && metodo === 'DELETE' && pathname === `/test-control/runs/${runId}`, 'CIERRE_INVALIDO');
    else {
      exigir(abierto || (cerrado && metodo === 'GET'), 'PETICION_FUERA_RUN');
      if (!cerrado && cuenta >= limite - LIMITE.margen_cierre) fallo('LIMITE_SOLICITUDES_FUNCIONALES');
      if (metodo === 'GET') {
        exigir(/^\/configuracion\/fincas\/\d+$/.test(ruta)
          || ruta === '/configuracion/fincas?solo_activas=true'
          || /^\/configuracion\/infraestructuras\/\d+$/.test(ruta)
          || ['/iot/dispositivos?estado=SIN_SEÑAL', '/iot/dispositivos?estado=INACTIVO'].includes(ruta)
          || /^\/iot\/monitoreo\/dashboard\/\d+(?:\?pagina=\d+&por_pagina=50)?$/.test(ruta),
        'LECTURA_FUERA_LISTA_BLANCA');
      } else {
        exigir(metodo === 'POST' && pathname === '/configuracion/infraestructuras', 'ESCRITURA_FUERA_LISTA_BLANCA');
        exigir(Number(cuerpo?.finca_id) === 184 && JSON.stringify(cuerpo?.especies) === '[126]'
          && /^G93-RUN-G93-V\d+-\d{8}-\d{6}$/.test(cuerpo?.nombre_infraestructura ?? ''), 'ID_FUERA_LISTA_BLANCA');
        exigir(permitidos.size === 0, 'SEGUNDA_AREA_PROHIBIDA');
      }
    }
    cuenta++;
    if (abierto && !local) remotasEnRun++;
    const headers = { Accept: 'application/json' };
    if (token) headers.Authorization = `Bearer ${token}`;
    if (abierto && !login && !cierre) { headers['X-Test-Run-Id'] = runId; headers['X-Sandbox-Secret'] = secreto; }
    if (cierre) headers['X-Sandbox-Secret'] = secreto;
    if (cuerpo) headers['Content-Type'] = 'application/json';
    const inicio = Date.now();
    const response = await fetcher(base + ruta, { method: metodo, headers,
      body: cuerpo ? JSON.stringify(cuerpo) : undefined, redirect: 'manual', signal: AbortSignal.timeout(30000) });
    let json = null;
    try { json = await response.json(); } catch { /* Respuesta vacía */ }
    const eco = response.headers.get('X-Test-Run-Id');
    bitacora.push({ metodo, ruta, http: response.status, en_run: abierto && !cierre,
      eco_correcto: abierto && !cierre ? eco === runId : null, ms: Date.now() - inicio });
    if (abierto && !cierre) exigir(eco === runId, 'ECO_RUN_AUSENTE');
    if (cierre && response.status === 200) { abierto = false; cerrado = true; }
    return { http: response.status, cuerpo: json, cookie: login ? response.headers.get('set-cookie') : null };
  }
  return { solicitar, abrir: () => { abierto = true; }, permitir: id => permitidos.add(Number(id)),
    iniciarUi: () => { exigir(abierto && !uiEnCurso, 'CYPRESS_FUERA_RUN'); uiEnCurso = true; },
    terminarUi: () => { uiEnCurso = false; },
    estado: () => ({ abierto, cerrado, cuenta, remotas_en_run: remotasEnRun,
      ui_en_curso: uiEnCurso, areas: [...permitidos] }) };
}

export function extraerCookie(cabecera) {
  const m = /^refresh_token=([^;]+)/.exec(cabecera ?? '');
  exigir(m?.[1], 'COOKIE_REFRESH_AUSENTE');
  return m[1];
}

export function newman(contrato, { fase, id, base, token, secreto, secretos,
  invocar = invocarNewman, tempDir = os.tmpdir() }) {
  const tmp = fs.mkdtempSync(path.join(tempDir, 'g93-newman-'));
  try {
    const envPath = path.join(tmp, 'env.json'); const repPath = path.join(tmp, 'reporte.json');
    const vals = { qa_autorizado: 'SI', fase, id_infraestructura: id, base_url: base,
      token_productor: token, run_id: contrato.runId, sandbox_secret: secreto };
    guardar(envPath, { values: Object.entries(vals).map(([key, value]) => ({ key, value: String(value), enabled: true })) });
    const p = invocar(['run', COLECCION, '-e', envPath, '--reporters', 'json',
      '--reporter-json-export', repPath, '--timeout-request', '30000', '--color', 'off'],
      45000);
    exigir(fs.existsSync(repPath), `NEWMAN_SIN_REPORTE_${p.error?.code ?? p.status}`);
    const rep = JSON.parse(fs.readFileSync(repPath, 'utf8'));
    exigir(rep.run?.executions?.length === 1, 'NEWMAN_EJECUCIONES_INVALIDAS');
    exigir(rep.run.executions[0]?.response?.code != null, 'NEWMAN_SIN_RESPUESTA_API');
    const rel = `newman/newman-${fase}-${id}.json`;
    fs.mkdirSync(path.join(contrato.directorio, 'newman'), { recursive: true });
    fs.writeFileSync(path.join(contrato.directorio, rel), sanearArtefacto(JSON.stringify(rep), secretos));
    const ex = rep.run.executions[0]; let cuerpo = null;
    try { cuerpo = JSON.parse(Buffer.from(ex.response?.stream?.data ?? []).toString('utf8')); } catch { /* sin JSON */ }
    return { rel, http: ex.response?.code ?? null, cuerpo, fallos: (rep.run?.failures ?? [])
      .map(x => ({ id: /\[([^\]]+)\]$/.exec(x.source?.name ?? '')?.[1] ?? null,
        mensaje: limpio(x.error?.message ?? '', secretos) })),
      eco: (ex.response?.header ?? []).some(x => x.key?.toLowerCase() === 'x-test-run-id' && x.value === contrato.runId),
      proceso: p.status };
  } finally { fs.rmSync(tmp, { recursive: true, force: true }); }
}

function htmlNewman(r, dir) {
  if (!r.newman.length) return;
  const esc = x => String(x).replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;');
  const filas = r.newman.map(x => `<tr><td>${esc(x.fase)}</td><td>${esc(x.http)}</td><td>${esc(x.fallos.length)}</td><td>${esc(x.archivo)}</td></tr>`).join('');
  const rel = 'newman/newman-G93-consolidado.html';
  fs.writeFileSync(path.join(dir, rel), `<!doctype html><html lang="es"><meta charset="utf-8"><title>Newman G93</title><h1>Newman G93: ejecuciones reales</h1><table border="1"><tr><th>Variante</th><th>HTTP</th><th>Fallos</th><th>JSON</th></tr>${filas}</table></html>`);
  r.evidencias.push(rel);
}

export function invocarCypressLocal({ proyecto = DIR, spec = SPEC, carpeta, env = process.env,
  prefijo = 'UI-184-V1', secretos = [], spawn = spawnSync, timeout = 150000 } = {}) {
  if (env.CYPRESS_ENSAYO_G93_SPEC_REAL === 'SI') {
    const temporal = path.resolve(os.tmpdir()) + path.sep;
    const destino = path.resolve(carpeta) + path.sep;
    const contexto = path.resolve(env.CYPRESS_ENSAYO_CONTEXTO_RUTA ?? '');
    exigir(destino.startsWith(temporal) && path.resolve(env.CYPRESS_ARTIFACTS_DIR ?? '') === path.resolve(carpeta)
      && env.CYPRESS_ENSAYO_CONTEXTO_TEMPORAL === 'SI'
      && contexto.startsWith(temporal) && path.basename(contexto) === 'contexto_operacion.json'
      && fs.existsSync(contexto)
      && JSON.parse(fs.readFileSync(contexto, 'utf8')).run_id === env.CYPRESS_RUN_ID
      && /^ENSAYO-G93-\d{8}-\d{6}-[a-z0-9]+$/.test(env.CYPRESS_RUN_ID ?? '')
      && /^http:\/\/127\.0\.0\.1:\d+$/.test(env.CYPRESS_API_BASE ?? '')
      && /^http:\/\/127\.0\.0\.1:\d+$/.test(env.CYPRESS_FRONT_BASE ?? ''),
    'ENSAYO_SPEC_REAL_FUERA_DE_TEMPORAL');
  }
  fs.mkdirSync(carpeta, { recursive: true });
  const cli = path.join(path.dirname(require.resolve('cypress/package.json')), 'bin', 'cypress');
  const args = ['run', '--project', proyecto, '--spec', spec, '--config-file', CONFIG_CYPRESS,
    '--config', `screenshotsFolder=${carpeta},videosFolder=${carpeta},downloadsFolder=${carpeta}`,
    '--browser', 'chrome', '--headless'];
  const inicio = Date.now();
  let p;
  try {
    p = spawn(process.execPath, [cli, ...args], { cwd: proyecto, shell: false, env,
      encoding: 'utf8', maxBuffer: 8 * 1024 * 1024, timeout });
  } catch (error) { p = { status: null, signal: null, error, stdout: '', stderr: '' }; }
  const cookieTemporal = env.CYPRESS_REFRESH_COOKIE_FILE;
  if (cookieTemporal && fs.existsSync(cookieTemporal)) {
    const rotada = fs.readFileSync(cookieTemporal, 'utf8').trim();
    if (rotada) secretos.push(rotada);
  }
  const sanear = valor => sanearArtefacto(String(valor ?? ''), secretos);
  const diagnostico = {
    comando: { ejecutable: process.execPath, argumentos: [cli, ...args] }, cwd: proyecto,
    navegador: 'chrome', version_cypress: require('cypress/package.json').version,
    codigo_salida: p.status ?? null, senal: p.signal ?? null,
    error_spawn: p.error ? { codigo: p.error.code ?? null, mensaje: sanear(p.error.message) } : null,
    duracion_ms: Date.now() - inicio,
    stdout: `${prefijo}.diagnostico.log`, stderr: `${prefijo}.diagnostico.log`,
  };
  const log = `STDOUT\n${sanear(p.stdout)}\nSTDERR\n${sanear(p.stderr)}\n`;
  fs.writeFileSync(path.join(carpeta, `${prefijo}.diagnostico.log`), log);
  fs.writeFileSync(path.join(carpeta, `${prefijo}.diagnostico.json`),
    sanearArtefacto(JSON.stringify(diagnostico, null, 2), secretos));
  return { proceso: p, diagnostico, args, cli };
}

export function cypress(contrato, { fase, id, nombre, fecha, base, front, cookie, cookieFile, secreto,
  secretos = [], invocar = invocarCypressLocal }) {
  const dir = path.join(contrato.directorio, 'cypress'); fs.mkdirSync(dir, { recursive: true });
  const variables = { AUTORIZADO_RUN: 'SI', FASE: fase, ID_INFRA: String(id), NOMBRE_INFRA: nombre,
    FECHA_HISTORICA: fecha ?? '', API_BASE: base, RUN_ID: contrato.runId, SANDBOX_SECRET: secreto,
    FRONT_BASE: front, REFRESH_COOKIE: cookie, REFRESH_COOKIE_FILE: cookieFile ?? '', ARTIFACTS_DIR: dir };
  const env = { ...process.env, ...Object.fromEntries(Object.entries(variables).map(([k, v]) => [`CYPRESS_${k}`, String(v)])) };
  // Proceso Node directo: conserva el tope de 150 s y captura el error antes del acta.
  const { proceso: p } = invocar({ carpeta: dir, env, prefijo: `UI-184-${fase}`,
    secretos: [...secretos, cookie, secreto] });
  const diagnosticoRel = `cypress/UI-184-${fase}.diagnostico.json`;
  const logRel = `cypress/UI-184-${fase}.diagnostico.log`;
  const rel = `cypress/UI-184-${fase}.json`;
  if (!fs.existsSync(path.join(contrato.directorio, rel))) return { estado: 'ERROR_QA',
    motivo: `Cypress sin acta: ${p.error?.code ?? p.status}; ver ${diagnosticoRel}`,
    rel: diagnosticoRel, log_rel: logRel, ejecutadas: 0, proceso_fallido: true };
  const acta = JSON.parse(fs.readFileSync(path.join(contrato.directorio, rel), 'utf8'));
  const procesoOk = p.status === 0 && !p.error;
  return { estado: procesoOk ? acta.estado : 'ERROR_QA', ejecutadas: 1,
    proceso_fallido: !procesoOk,
    motivo: procesoOk ? acta.motivo : `${acta.motivo}; proceso Cypress ${p.error?.code ?? p.status}`,
    criterio: acta.criterio, rel, http: acta.http, error_red: acta.error_red, ui_inicial: acta.ui_inicial,
    ui_objetivo: acta.ui_objetivo, peticiones: acta.peticiones,
    incidencias_tecnicas: acta.incidencias_tecnicas ?? [],
    observaciones_documentales: acta.observaciones_documentales ?? [],
    pendiente_al_terminar: acta.pendiente_al_terminar, proceso: p.status,
    diagnostico_rel: diagnosticoRel, log_rel: logRel };
}

export function registrar(r, id, fuente, estado, motivo, evidencia, tipo = 'ASSERT') {
  r.comprobaciones.push({ caso: CASO, fuente, herramienta: fuente === 'UI' ? 'Cypress' : 'Newman',
    id, tipo, estado, motivo, evidencia: evidencia ?? null });
  if (evidencia && !r.evidencias.includes(evidencia)) r.evidencias.push(evidencia);
}

function bloqueDecisionCaso(r) {
  const requeridas = Object.values(CAPACIDADES.comprobaciones_obligatorias[CASO]).flat();
  const comprobacion = id => r.comprobaciones.find(x => x.id === id && x.caso === CASO && x.tipo === 'ASSERT');
  const pendientes = requeridas.filter(id => !['APROBADO', 'RECHAZADO'].includes(comprobacion(id)?.estado));
  const decision = r.casos[CASO].estado;
  exigir(decision !== 'APROBADO' || (!pendientes.length && r.cypress.total_pruebas > 0),
    'INFORME_APROBADO_CON_COMPROBACIONES_PENDIENTES');
  const limpioTabla = valor => String(valor).replaceAll('|', '\\|').replaceAll(/\r?\n/g, ' ');
  const tabla = requeridas.map(id => `| ${id} | ${limpioTabla(comprobacion(id)?.estado ?? 'NO_EJECUTADA')} |`).join('\n');
  const rechazos = r.comprobaciones.filter(x => x.caso === CASO && x.tipo === 'ASSERT'
    && x.estado === 'RECHAZADO');
  const motivo = rechazos.length
    ? `${r.casos[CASO].motivo}. ${rechazos.map(x => `${x.id}: ${x.motivo}`).join('; ')}.`
    : `${r.casos[CASO].motivo}.`;
  const faltan = [
    ...(rechazos.length ? [`Atender las discrepancias de ${rechazos.map(x => x.id).join(', ')}`] : []),
    ...(pendientes.length ? [`Emitir veredicto para ${pendientes.join(', ')}`] : []),
    ...(!r.cierre.rollback.verificado ? ['Acreditar cierre y rollback'] : []),
  ];
  if (!faltan.length && !r.oficial) faltan.push('Revisar las barreras de oficialidad del RUN');
  return `# TC-M03-G93 — ${decision}\n\n## Decisión del caso\n\n- **Caso agrupado:** TC-M03-G93.\n- **Caso original:** ${CASO} (RF-58 / CU04 E1) — unidad sin lecturas mostrada en GRIS con «Sin datos disponibles».\n- **Decisión:** **${decision}**.\n\n${motivo}\n\n| Comprobación | Resultado |\n|---|---|\n${tabla}\n\n**¿RUN oficial?** ${r.oficial ? 'Sí' : 'No'}${!r.oficial && pendientes.length ? `; faltan veredictos de ${pendientes.join(', ')}` : ''}.\n\n**Qué falta para cerrar:** ${faltan.length ? `${faltan.join('; ')}.` : 'Ninguna comprobación pendiente en este RUN.'}\n`;
}

function informe(r) {
  const tabla = r.comprobaciones.map(x => `| ${x.id} | ${x.fuente} | ${x.tipo} | ${x.estado} | ${x.motivo} | ${x.evidencia ?? 'sin evidencia'} |`).join('\n');
  const rechazos = r.comprobaciones.filter(x => x.tipo === 'ASSERT' && x.estado === 'RECHAZADO');
  const incidencias = rechazos.map(x => `- ${x.id}: requisito incumplido: ${x.id.startsWith('API') ? 'unidad visible y GRIS, histórico o ausencia de valores/5xx según la matriz' : 'unidad visible, GRIS y mensaje de ausencia de datos equivalente al esperado, además de fecha y ausencia de valores fabricados'}. Observado: ${x.motivo}. Evidencia: ${x.evidencia}. Equipo inicial: Desarrollo por primera discrepancia pública; severidad MEDIA (panel parcial); certeza CONFIRMADA para la respuesta observada, causa raíz NO DETERMINADA. Incidencia definitiva pendiente de triaje.`).join('\n') || 'Ninguna confirmada.';
  const tecnico = (r.problemas_tecnicos.map(x => `- ${x}`).join('\n') || 'Ninguno registrado.')
    + '\n\n## Dependencias de datos y entorno\n\n'
    + (r.dependencias.map(x => `- ${x}`).join('\n') || 'Ninguna registrada.')
    + '\n\n## Hallazgos de rendimiento pendientes de diagnóstico\n\n'
    + (r.hallazgos_rendimiento.map(x => `- ${x}`).join('\n') || 'Ninguno registrado.')
    + '\n\n## Criterio de carga inicial UI\n\nDecisión QA de 2026-10-25: se permite el GET global real con límite de 60 s, sin reescritura, simulación ni reintento del ejecutor. El acta Cypress registra ruta relativa, inicio, fin, duración, HTTP, error de red si consta, eco RUN, estado visible y posible petición pendiente. HTTP 200 permite evaluar el panel real y el filtro usado por el Productor; unidad ausente con respuesta válida, GRIS/texto/fecha/valores discordantes o HTTP 5xx son RECHAZADO. 401/403 o eco RUN ausente son técnicos de sesión. Sin respuesta o error de red se registra rendimiento pendiente de diagnóstico como UI NO_CONCLUYENTE salvo incumplimiento visual acreditado; nunca se aprueba. El ejecutor espera la salida del proceso Cypress antes de la siguiente petición propia o del DELETE.\n';
  const ev = r.evidencias.filter(x => fs.existsSync(path.join(r.directorio, x))).map(x => `- [${x}](${x})`).join('\n');
  return `${bloqueDecisionCaso(r)}\n## Identificación\n\nGrupo G93; caso ${CASO}; RF-58/CU04 E1; V${r.version}; RUN ${r.run_id}; ambiente TEST; autorización ${r.autorizacion}; commit ${r.commit ?? 'NO VERIFICADO (sin Git)'}; Node ${process.version}; Newman ${r.newman.length} ejecuciones; Cypress ${r.cypress.total_pruebas} pruebas.\n\n## Resumen de veredictos\n\n${CASO}: funcional ${r.casos[CASO].estado}; técnico ${r.casos[CASO].estado_tecnico}; motivo: ${r.casos[CASO].motivo}.\n\n## Esperado y observado por caso\n\nEsperado literal de la matriz: ${ORACULO}\n\nDecisión QA de 2026-10-25: «Sin datos» y «Sin datos disponibles» son equivalentes como mensaje visible de ausencia de información; la diferencia de redacción no afecta al veredicto.\n\nObservado: ${JSON.stringify(r.casos[CASO].observado)}. Variante V1: ${r.variantes.V1}; variante V2: ${r.variantes.V2}.\n\n## Comprobaciones API/UI\n\n| ID | Fuente | Tipo | Estado | Observado | Evidencia |\n|---|---|---|---|---|---|\n${tabla}\n\n## Observación de carga UI\n\n${JSON.stringify(r.cypress.detalle.map(({ fase, criterio, http, error_red, ui_inicial, ui_objetivo, pendiente_al_terminar, peticiones }) => ({ fase, criterio, http, error_red, ui_inicial, ui_objetivo, pendiente_al_terminar, peticiones })))}.\n\n## Evidencias reales\n\n${ev}\n\n## Incidencias de producto\n\n${incidencias}\n\n## Incidencias técnicas QA\n\n${tecnico}\n\n## Observaciones documentales\n\n${r.observaciones_documentales.map(x => `- ${x}`).join('\n') || 'Ninguna diferencia de redacción equivalente observada.'}\n\nEl código local sugiere ausencia de unidades sin sensores en el resumen; solo TEST autorizado decide el veredicto.\n\n## Análisis de causas\n\nLa causa raíz no se atribuye por inferencia de código. La primera discrepancia pública orienta el equipo inicial; los fallos de automatización se registran aparte.\n\n## Efectos externos\n\n${r.consume_version ? 'Solicitudes acreditadas: ver bitácora y evidencias; POST de área solo cuando figura datos.id_area_v1.' : 'No constan solicitudes remotas dentro del RUN; sin POST de área.'} RF-58 E7 puede auditar y enviar correo síncrono si aparece sensor GRIS no desactualizado; correos E7 aceptados por decisión QA, sin reversión por DELETE. Las lecturas de configuración pueden auditar GET. No se asume ausencia de propagación M09 ni reversión de efectos externos.\n\n## Cierre y rollback\n\nDELETE HTTP ${r.cierre.run.cierre_http ?? 'NO CONSTA'}; rollback verificado ${r.cierre.rollback.verificado}; estado ${r.cierre.rollback.estado}. ${r.cierre.motivo}. Comprobaciones: ${JSON.stringify(r.cierre.rollback.comprobaciones)}.\n\n## Conclusión y acción concreta\n\n${r.casos[CASO].estado}. ${r.cierre.rollback.verificado ? 'Responsable QA: revisar incidencias y decidir cierre del caso.' : 'Responsable QA: revisar cierre antes de otra ejecución.'}\n`;
}

// Punto único de serialización usado por el recorrido y por la regresión local.
export function serializarResultado(contrato, r, { previoOk = true, barreras = [], errorEjecutor = false,
  modoEnsayo = false, escribirInforme = true } = {}) {
  htmlNewman(r, contrato.directorio);
  const capturas = path.join(contrato.directorio, 'cypress');
  if (fs.existsSync(capturas)) {
    const recorrer = dir => { for (const d of fs.readdirSync(dir, { withFileTypes: true })) {
      const p = path.join(dir, d.name);
      if (d.isDirectory()) recorrer(p);
      else if (/\.(png|mp4)$/.test(d.name)) r.evidencias.push(path.relative(contrato.directorio, p).replaceAll('\\', '/'));
    } }; recorrer(capturas);
  }
  for (const id of IDS) if (!r.comprobaciones.some(x => x.id === id)) registrar(r, id,
    id.startsWith('UI') ? 'UI' : 'API', 'NO_EJECUTADA', 'Variante sin ejecución acreditada', null);
  for (const comprobacion of r.comprobaciones) {
    if (comprobacion.evidencia && !fs.existsSync(path.join(contrato.directorio, comprobacion.evidencia))) {
      r.problemas_tecnicos.push(`EVIDENCIA_AUSENTE ${comprobacion.id}: ${comprobacion.evidencia}`);
      comprobacion.evidencia = null;
    }
  }
  for (const rel of r.evidencias.filter(x => x !== 'resultado.json' && !fs.existsSync(path.join(contrato.directorio, x))))
    r.problemas_tecnicos.push(`EVIDENCIA_AUSENTE ${rel}`);
  r.evidencias = [...new Set(r.evidencias.filter(x => x === 'resultado.json'
    || fs.existsSync(path.join(contrato.directorio, x))))];
  if (r.problemas_tecnicos.some(x => x.startsWith('EVIDENCIA_AUSENTE'))) errorEjecutor = true;
  const decision = clasificar(r.comprobaciones, { candidata: Boolean(r.datos.id_area_v2),
    cierreVerificado: r.cierre.rollback.verificado });
  if (!previoOk) {
    r.casos[CASO].estado = 'NO_EJECUTADA';
    r.casos[CASO].motivo = `PREFLIGHT_LOCAL: ${barreras.join(', ')}`;
  } else if (!r.consume_version && r.problemas_tecnicos.length) {
    r.casos[CASO].estado = 'NO_EJECUTADA';
    r.casos[CASO].motivo = r.problemas_tecnicos[0];
  } else if (errorEjecutor && !r.comprobaciones.some(x => x.estado === 'RECHAZADO')) {
    r.casos[CASO].estado = 'NO_CONCLUYENTE';
    r.casos[CASO].motivo = 'Proceso hijo o ejecutor incompleto';
  } else { r.casos[CASO].estado = decision.estado; r.casos[CASO].motivo = decision.motivo; }
  if (r.casos[CASO].estado === 'APROBADO' && r.cypress.total_pruebas === 0) {
    r.casos[CASO].estado = 'NO_CONCLUYENTE';
    r.casos[CASO].motivo = 'UI obligatoria sin ejecuciones Cypress acreditadas';
    r.problemas_tecnicos.push('CYPRESS_SIN_PRUEBAS_ACREDITADAS');
    errorEjecutor = true;
  }
  r.casos[CASO].estado_tecnico = !previoOk ? 'NO_EJECUTADA' : r.cypress.detalle.some(x => x.estado === 'ERROR_QA')
    || r.problemas_tecnicos.some(x => /API V\d|NEWMAN|CYPRESS_SIN_PRUEBAS/.test(x))
    ? 'ERROR_QA' : r.problemas_tecnicos.length || r.hallazgos_rendimiento.length ? 'NO_CONCLUYENTE' : 'OK';
  r.codigo_salida = !previoOk || errorEjecutor ? 2 : 0;
  delete r.directorio;
  guardar(path.join(contrato.directorio, 'resultado.json'), r);
  const nombre = contrato.version === 1 ? 'TC-M03-G93_resultado.md' : `TC-M03-G93_reevaluacion_V${contrato.version}.md`;
  r.directorio = contrato.directorio;
  if (!modoEnsayo && escribirInforme) fs.writeFileSync(path.join(contrato.directorio, nombre), informe(r));
  const revision = evaluarRegistro(JSON.parse(fs.readFileSync(path.join(contrato.directorio,
    'resultado.json'), 'utf8')), contrato.directorio,
  { runId: contrato.runId, version: contrato.version });
  if (!revision.estructura) {
    r.codigo_salida = 2;
    r.problemas_tecnicos.push('RESULTADO_CONTRATO_INVALIDO');
    if (!modoEnsayo && escribirInforme) fs.writeFileSync(path.join(contrato.directorio, nombre), informe(r));
  }
  r.oficial = !modoEnsayo && r.codigo_salida === 0 && revision.oficialPosible;
  delete r.directorio;
  guardar(path.join(contrato.directorio, 'resultado.json'), r);
  r.directorio = contrato.directorio;
  if (!modoEnsayo && escribirInforme) fs.writeFileSync(path.join(contrato.directorio, nombre), informe(r));
  return r;
}

export async function evaluar(contrato, { env = leerEnv(), fetcher = fetch, runNewman = newman,
  runCypress = cypress, validarHerramientas = false, prevalidarHerramientas = prevalidar,
  modoEnsayo = null } = {}) {
  exigir(['evaluar', 'reintentar', 'reevaluar'].includes(contrato.operacion), 'OPERACION_NO_PUBLICADA');
  exigir(!fs.existsSync(path.join(contrato.directorio, 'resultado.json')), 'RUN_CON_RESULTADO_EXISTENTE');
  fs.mkdirSync(contrato.directorio, { recursive: true });
  const previo = preflight(contrato, env);
  if (validarHerramientas) {
    const barrera = prevalidarHerramientas(env);
    previo.barreras.push(...barrera.barreras.filter(x => !previo.barreras.includes(x)));
    previo.herramientas = barrera.herramientas;
    previo.diagnostico_herramientas = barrera.diagnostico_herramientas;
    previo.ok = previo.barreras.length === 0;
  }
  guardar(path.join(contrato.directorio, 'preflight.json'), previo);
  const r = { grupo: 'G93', run_id: contrato.runId, version: contrato.version, oficial: false,
    consume_version: false, operacion: contrato.operacion, autorizacion: contrato.referencia,
    commit: null, directorio: contrato.directorio, datos: { ids_telemetria: [], id_area_v1: null,
      id_area_v2: null, candidatas_v2: [], descubrimiento_v2: null },
    casos: { [CASO]: { id: CASO, estado: 'NO_EJECUTADA', estado_tecnico: 'NO_EJECUTADA', motivo: 'Sin iniciar', observado: {} } },
    variantes: { V1: 'NO_EJECUTADA', V2: 'NO_EJECUTADA' }, comprobaciones: [],
    bitacora: [], newman: [], cypress: { total_pruebas: 0, detalle: [] }, evidencias: ['preflight.json', 'resultado.json'], problemas_tecnicos: [], hallazgos_rendimiento: [], dependencias: [], observaciones_documentales: [],
    cierre: { run: { cierre_http: null }, rollback: { verificado: false, estado: 'NO_APLICA', comprobaciones: [] }, motivo: 'No iniciado' } };
  const secretos = [env.QA_SANDBOX_SECRET, env.QA_ADMIN_EMAIL, env.QA_PROD_EMAIL,
    env.QA_ADMIN_PASSWORD, env.QA_PROD_PASSWORD].filter(Boolean);
  const base = String(env.SIGAB_API_TEST_BASE ?? '').replace(/\/+$/, '');
  const t = transporte({ base, runId: contrato.runId, secreto: env.QA_SANDBOX_SECRET,
    bitacora: r.bitacora, fetcher, local: Boolean(modoEnsayo) });
  let errorEjecutor = false;
  const ejecutarUi = async opciones => {
    const temporalCookie = fs.mkdtempSync(path.join(os.tmpdir(), 'g93-cookie-'));
    const cookieFile = path.join(temporalCookie, 'refresh-cookie.txt');
    let iniciada = false;
    let ui;
    try {
      t.iniciarUi(); iniciada = true;
      ui = await runCypress(contrato, { ...opciones, cookieFile });
      return ui;
    }
    catch (e) { errorEjecutor = true; if (!fs.existsSync(cookieFile)) refreshCookie = null; throw e; }
    finally {
      try {
        if (fs.existsSync(cookieFile)) {
          const rotada = fs.readFileSync(cookieFile, 'utf8').trim();
          exigir(/^[A-Za-z0-9._~-]+$/.test(rotada), 'COOKIE_ROTADA_INVALIDA');
          secretos.push(rotada);
          refreshCookie = rotada;
        } else if (ui?.peticiones?.some(x => x.alias === 'refresh' && x.http === 200)
          || ui?.ejecutadas === 0 && ui?.proceso_fallido && !/EPERM/.test(ui.motivo ?? '')) {
          refreshCookie = null;
          errorEjecutor = true;
          fallo('COOKIE_ROTADA_NO_TRASPASADA');
        }
      } finally {
        fs.rmSync(temporalCookie, { recursive: true, force: true });
        if (iniciada) t.terminarUi();
      }
    }
  };
  let tokenAdmin, tokenProd, refreshCookie, snapshotV2;
  try {
    if (!previo.ok) fallo(`PREFLIGHT_LOCAL: ${previo.barreras.join(', ')}`);
    if (modoEnsayo === 'hijo') {
      const p = spawnSync('newman-g93-ensayo-ausente', ['--version'], { encoding: 'utf8', timeout: 1000 });
      if (p.error) { errorEjecutor = true; fallo('HIJO_NEWMAN_NO_DISPONIBLE'); }
      fallo('ENSAYO_HIJO_INESPERADO');
    }
    const a = await t.solicitar('POST', '/sesiones/', { login: true,
      cuerpo: { correo_electronico: env.QA_ADMIN_EMAIL, contrasena: env.QA_ADMIN_PASSWORD } });
    const p = await t.solicitar('POST', '/sesiones/', { login: true,
      cuerpo: { correo_electronico: env.QA_PROD_EMAIL, contrasena: env.QA_PROD_PASSWORD } });
    exigir(a.http === 200 && p.http === 200 && a.cuerpo?.token && p.cuerpo?.token, 'LOGIN_PRE_RUN_FALLIDO');
    tokenAdmin = a.cuerpo.token; tokenProd = p.cuerpo.token; refreshCookie = extraerCookie(p.cookie);
    secretos.push(tokenAdmin, tokenProd, refreshCookie);
    t.abrir();
    const get = (ruta, token = tokenProd) => t.solicitar('GET', ruta, { token });
    // V1 y V2 son independientes. Un fallo de preparación de V1 no impide el descubrimiento de V2.
    try {
      const fincaP = await get('/configuracion/fincas/184');
      const fincaA = await get('/configuracion/fincas/184', tokenAdmin);
      const ref = await get('/configuracion/infraestructuras/349', tokenAdmin);
      exigir(fincaP.http === 200 && fincaA.http === 200 && ref.http === 200
        && fincaP.cuerpo?.es_activo === true && fincaA.cuerpo?.es_activo === true
        && Number(ref.cuerpo?.id_finca) === 184 && ref.cuerpo?.es_activo === true
        && (ref.cuerpo?.especies ?? []).includes(126) && Number(ref.cuerpo?.superficie) > 0
        && typeof ref.cuerpo?.tipo_area === 'string' && ref.cuerpo.tipo_area.length > 0,
      'PRE_SEMILLA_V1_NO_ACREDITADA');
      const nombre = `G93-${contrato.runId}`;
      const alta = await t.solicitar('POST', '/configuracion/infraestructuras', { token: tokenAdmin,
        cuerpo: { nombre_infraestructura: nombre, tipo_area: ref.cuerpo.tipo_area,
          superficie: String(ref.cuerpo.superficie), finca_id: 184, especies: [126],
          descripcion_infraestructura: 'QA TC-M03-184 sin sensores' } });
      exigir(alta.http === 201 && Number.isSafeInteger(Number(alta.cuerpo?.id_infraestructura)), 'PRE_ALTA_AREA_FALLIDA');
      const id = Number(alta.cuerpo.id_infraestructura); t.permitir(id); r.datos.id_area_v1 = id;
      const alcance = await get(`/configuracion/infraestructuras/${id}`);
      exigir(alcance.http === 200 && Number(alcance.cuerpo?.id_infraestructura) === id, 'PRE_ALCANCE_PRODUCTOR_NO_ACREDITADO');
      try {
        const n = await runNewman(contrato, { fase: 'V1', id, base, token: tokenProd,
          secreto: env.QA_SANDBOX_SECRET, secretos });
        r.newman.push({ fase: 'V1', archivo: n.rel, http: n.http, fallos: n.fallos }); r.evidencias.push(n.rel);
        exigir(n.eco === true, 'NEWMAN_ECO_RUN_AUSENTE');
        const api = evaluarApi('V1', n, id);
        const visibleV1 = n.http === 200 && (n.cuerpo?.resumen_unidades ?? [])
          .some(x => Number(x.id_infraestructura) === id && x.estado_general === 'GRIS');
        registrar(r, 'API-184-01', 'API', visibleV1 ? 'APROBADO' : 'RECHAZADO',
          visibleV1 ? 'HTTP 200; unidad presente en resumen_unidades y GRIS' : api.motivo, n.rel);
        const unidadV1 = (n.cuerpo?.resumen_unidades ?? []).find(x => Number(x.id_infraestructura) === id);
        const limpioV1 = n.http === 200 && Boolean(unidadV1) && (n.cuerpo?.sensores ?? []).length === 0
          && unidadV1.ultimo_dato_recibido == null;
        registrar(r, 'API-184-02', 'API', limpioV1 ? 'APROBADO' : 'RECHAZADO',
          !unidadV1 ? 'La unidad no figura; imposible acreditar ausencia de valores fabricados en su resumen'
            : limpioV1 ? 'Cero sensores y último dato histórico nulo'
              : 'Se observaron sensores o una fecha histórica impropia de una unidad recién creada', n.rel);
        r.casos[CASO].observado.V1 = { http: n.http, id, api: api.motivo };
        r.variantes.V1 = api.estado;
      } catch (e) { errorEjecutor = true; r.problemas_tecnicos.push(`API V1: ${limpio(e.message, secretos)}`); r.variantes.V1 = 'NO_CONCLUYENTE'; }
      const ui = await ejecutarUi({ fase: 'V1', id, nombre, fecha: null, base: API_FRONT_TEST,
        front: env.SIGAB_FRONT_TEST_URL, cookie: refreshCookie, secreto: env.QA_SANDBOX_SECRET, secretos });
      r.cypress.detalle.push({ fase: 'V1', ...ui });
      r.cypress.total_pruebas += ui.ejecutadas ?? (ui.rel ? 1 : 0);
      if (ui.proceso_fallido || ui.estado === 'ERROR_QA' && !ui.rel) errorEjecutor = true;
      r.casos[CASO].observado.UI_V1 = { panel_global: ui.ui_inicial?.mensaje_ausencia ?? null,
        vista_filtrada: ui.ui_objetivo?.mensaje_ausencia ?? null,
        texto_estado_global: ui.ui_inicial?.texto_estado ?? null,
        texto_estado_filtrado: ui.ui_objetivo?.texto_estado ?? null };
      r.observaciones_documentales.push(...(ui.observaciones_documentales ?? []));
      for (const incidencia of ui.incidencias_tecnicas ?? []) r.problemas_tecnicos.push(`UI V1: ${incidencia}`);
      if (ui.estado === 'ERROR_QA' || ui.estado === 'NO_EJECUTADA') r.problemas_tecnicos.push(`UI V1: ${ui.motivo}`);
      if (ui.estado === 'NO_CONCLUYENTE') r.hallazgos_rendimiento.push(`UI V1: ${ui.motivo}; diagnóstico pendiente, sin atribuir causa raíz`);
      if (ui.pendiente_al_terminar) r.problemas_tecnicos.push('UI V1: petición sin respuesta observada al terminar el spec, posiblemente pendiente; DELETE posterior a la salida del proceso Cypress');
      registrar(r, 'UI-184-01', 'UI', ui.estado, ui.motivo, ui.rel);
      for (const rel of [ui.diagnostico_rel, ui.log_rel].filter(Boolean))
        if (fs.existsSync(path.join(contrato.directorio, rel)) && !r.evidencias.includes(rel)) r.evidencias.push(rel);
    } catch (e) { r.problemas_tecnicos.push(`V1: ${limpio(e.message, secretos)}`); r.variantes.V1 = 'NO_CONCLUYENTE'; }

    try {
      const fincas = await get('/configuracion/fincas?solo_activas=true');
      exigir(fincas.http === 200 && Array.isArray(fincas.cuerpo?.items), 'PRE_FINCAS_PRODUCTOR_NO_VISIBLES');
      const idsFinca = [...new Set(fincas.cuerpo.items.map(x => Number(x.id_finca))
        .filter(x => Number.isSafeInteger(x) && x > 0))];
      const excluidos = new Set();
      let revisadas = 0, paginasUsadas = 0, alternativas = null, ejecucionesV2 = 0;
      const buscar = async ids => {
        const b = await buscarCandidataV2({ dispositivos: ids.map(id => ({ id_infraestructura: id })),
          fincasVisibles: idsFinca, idAreaV1: r.datos.id_area_v1, get,
          excluidos: [...excluidos], maxCandidatas: LIMITE.candidatas - revisadas,
          maxPaginasAdicionales: LIMITE.paginas_adicionales_v2 - paginasUsadas });
        revisadas += b.candidatasRevisadas; paginasUsadas += b.paginasUsadas;
        r.datos.candidatas_v2.push(...b.revisiones);
        for (const revision of b.revisiones)
          if (revision.motivo !== 'aceptada') excluidos.add(revision.id_infraestructura);
        return b.encontrada;
      };
      const siguiente = async () => {
        let hallada = await buscar(IDS_PREFERIDOS_V2);
        if (hallada || revisadas >= LIMITE.candidatas) return hallada;
        if (!alternativas) {
          alternativas = [];
          r.datos.descubrimiento_v2 = [];
          for (const estado of ['SIN_SEÑAL', 'INACTIVO']) {
            const ruta = `/iot/dispositivos?estado=${estado}`;
            const d = await get(ruta, tokenAdmin);
            r.datos.descubrimiento_v2.push({ ruta, http: d.http,
              total_dispositivos: Array.isArray(d.cuerpo) ? d.cuerpo.length : null });
            exigir(d.http === 200 && Array.isArray(d.cuerpo), `PRE_DISPOSITIVOS_${estado}_NO_DISPONIBLES`);
            alternativas.push(...d.cuerpo.map(x => Number(x.id_infraestructura))
              .filter(x => Number.isSafeInteger(x) && x > 0));
          }
          alternativas = [...new Set(alternativas)].filter(id => !IDS_PREFERIDOS_V2.includes(id));
        }
        return buscar(alternativas);
      };
      const revalidar = async (id, momento) => {
        const b = await buscarCandidataV2({ dispositivos: [{ id_infraestructura: id }],
          fincasVisibles: idsFinca, idAreaV1: r.datos.id_area_v1, get,
          maxCandidatas: 1, maxPaginasAdicionales: LIMITE.paginas_adicionales_v2 - paginasUsadas });
        paginasUsadas += b.paginasUsadas;
        const revision = b.revisiones[0];
        r.datos.candidatas_v2.push({ ...revision, momento, evento: revision.motivo === 'aceptada'
          ? 'candidata_revalidada' : revision.motivo === 'sensor_fuera_estados_sin_comunicacion'
            ? 'candidata_cambio_estado' : 'candidata_no_elegible' });
        if (revision.motivo !== 'aceptada') { excluidos.add(id); return null; }
        return b.encontrada;
      };
      let encontrada = await siguiente();
      while (encontrada && ejecucionesV2 < LIMITE.newman - 1) {
        let { id } = encontrada;
        let vigente = await revalidar(id, 'antes_newman');
        if (!vigente) { encontrada = await siguiente(); continue; }
        r.datos.id_area_v2 = id;
        const detalle = await get(`/configuracion/infraestructuras/${id}`);
        exigir(detalle.http === 200, 'PRE_DETALLE_V2_NO_DISPONIBLE');
        snapshotV2 = Object.fromEntries(['id_infraestructura', 'nombre_infraestructura', 'id_finca', 'es_activo', 'especies']
          .map(k => [k, detalle.cuerpo[k]]));
        let n = null;
        try {
          n = await runNewman(contrato, { fase: 'V2', id, base, token: tokenProd,
            secreto: env.QA_SANDBOX_SECRET, secretos });
          ejecucionesV2++;
          r.newman.push({ fase: 'V2', id_infraestructura: id, archivo: n.rel, http: n.http, fallos: n.fallos });
          r.evidencias.push(n.rel);
          exigir(n.eco === true, 'NEWMAN_ECO_RUN_AUSENTE');
        } catch (e) { errorEjecutor = true; r.problemas_tecnicos.push(`API V2: ${limpio(e.message, secretos)}`); r.variantes.V2 = 'NO_CONCLUYENTE'; }
        vigente = await revalidar(id, 'antes_cypress');
        if (!vigente) {
          r.casos[CASO].observado.V2 = { id, motivo: r.datos.candidatas_v2.at(-1).evento };
          encontrada = await siguiente();
          continue;
        }
        if (n?.eco === true) {
          const api = evaluarApi('V2', n, id);
          registrar(r, 'API-184-03', 'API', api.estado, api.motivo, n.rel);
          r.casos[CASO].observado.V2 = { http: n.http, id, api: api.motivo };
          r.variantes.V2 = api.estado;
        }
        const unidad = vigente.pagina.cuerpo.resumen_unidades.find(x => Number(x.id_infraestructura) === id);
        exigir(refreshCookie, 'COOKIE_REFRESH_NO_DISPONIBLE');
        const ui = await ejecutarUi({ fase: 'V2', id, nombre: unidad.nombre_infraestructura,
          fecha: unidad.ultimo_dato_recibido, base: API_FRONT_TEST, front: env.SIGAB_FRONT_TEST_URL,
          cookie: refreshCookie, secreto: env.QA_SANDBOX_SECRET, secretos });
        r.cypress.detalle.push({ fase: 'V2', ...ui });
        r.cypress.total_pruebas += ui.ejecutadas ?? (ui.rel ? 1 : 0);
        if (ui.proceso_fallido || ui.estado === 'ERROR_QA' && !ui.rel) errorEjecutor = true;
        r.casos[CASO].observado.UI_V2 = { panel_global: ui.ui_inicial?.mensaje_ausencia ?? null,
          vista_filtrada: ui.ui_objetivo?.mensaje_ausencia ?? null,
          texto_estado_global: ui.ui_inicial?.texto_estado ?? null,
          texto_estado_filtrado: ui.ui_objetivo?.texto_estado ?? null };
        r.observaciones_documentales.push(...(ui.observaciones_documentales ?? []));
        for (const incidencia of ui.incidencias_tecnicas ?? []) r.problemas_tecnicos.push(`UI V2: ${incidencia}`);
        if (ui.estado === 'ERROR_QA' || ui.estado === 'NO_EJECUTADA') r.problemas_tecnicos.push(`UI V2: ${ui.motivo}`);
        if (ui.estado === 'NO_CONCLUYENTE') r.hallazgos_rendimiento.push(`UI V2: ${ui.motivo}; diagnóstico pendiente, sin atribuir causa raíz`);
        if (ui.pendiente_al_terminar) r.problemas_tecnicos.push('UI V2: petición sin respuesta observada al terminar el spec, posiblemente pendiente; DELETE posterior a la salida del proceso Cypress');
        registrar(r, 'UI-184-02', 'UI', ui.estado, ui.motivo, ui.rel);
        for (const rel of [ui.diagnostico_rel, ui.log_rel].filter(Boolean))
          if (fs.existsSync(path.join(contrato.directorio, rel)) && !r.evidencias.includes(rel)) r.evidencias.push(rel);
        break;
      }
      if (!r.comprobaciones.some(x => x.id === 'UI-184-02')) {
        r.variantes.V2 = 'BLOQUEADO';
        r.datos.id_area_v2 = null;
        snapshotV2 = null;
        r.dependencias.push('V2: ninguna candidata elegible o estable entre áreas 1, 2, 3 y hasta 10 áreas de dispositivos SIN_SEÑAL/INACTIVO; cambios de estado registrados; no se ejecuta UI sin elegibilidad revalidada.');
      }
    } catch (e) { r.problemas_tecnicos.push(`V2: ${limpio(e.message, secretos)}`); r.variantes.V2 = 'NO_CONCLUYENTE'; }
  } catch (e) { r.problemas_tecnicos.push(limpio(e.message, secretos)); }
  finally {
    if (t.estado().abierto) {
      try {
        const fin = await t.solicitar('DELETE', `/test-control/runs/${contrato.runId}`, { cierre: true });
        r.cierre.run.cierre_http = fin.http;
        const revisiones = [];
        if (fin.http === 200 && tokenAdmin && r.datos.id_area_v1) {
          const area = await t.solicitar('GET', `/configuracion/infraestructuras/${r.datos.id_area_v1}`, { token: tokenAdmin });
          revisiones.push({ recurso: 'area_v1', http: area.http, ok: area.http === 404 });
          if (area.http === 404) {
            const dashboard = await t.solicitar('GET', `/iot/monitoreo/dashboard/${r.datos.id_area_v1}?pagina=1&por_pagina=50`, { token: tokenProd });
            revisiones.push({ recurso: 'dashboard_area_v1', http: dashboard.http,
              ok: dashboard.http === 200 && dashboard.cuerpo?.total === 0
                && dashboard.cuerpo?.resumen_unidades?.length === 0 });
          }
        }
        if (fin.http === 200 && snapshotV2 && tokenProd) {
          const area = await t.solicitar('GET', `/configuracion/infraestructuras/${snapshotV2.id_infraestructura}`, { token: tokenProd });
          const actual = Object.fromEntries(Object.keys(snapshotV2).map(k => [k, area.cuerpo?.[k]]));
          revisiones.push({ recurso: 'semilla_v2_estable', http: area.http,
            ok: area.http === 200 && JSON.stringify(actual) === JSON.stringify(snapshotV2) });
        }
        r.cierre.rollback.comprobaciones = revisiones;
        r.cierre.rollback.verificado = fin.http === 200 && revisiones.length > 0 && revisiones.every(x => x.ok);
        r.cierre.rollback.estado = r.cierre.rollback.verificado ? 'CONFIRMADO' : 'NO_VERIFICADO';
        r.cierre.motivo = r.cierre.rollback.verificado ? 'DELETE y relaciones públicas acreditadas' : 'Cierre o lecturas públicas incompletas';
      } catch (e) { r.problemas_tecnicos.push(`CIERRE: ${limpio(e.message, secretos)}`); r.cierre.motivo = 'Error de cierre o verificación'; r.cierre.rollback.estado = 'NO_VERIFICADO'; }
    }
    r.presupuesto = t.estado();
    r.consume_version = t.estado().remotas_en_run > 0 || r.newman.length > 0
      || r.cypress.detalle.some(x => x.peticiones?.length > 0);
    if (r.datos.id_area_v1 && r.cierre.rollback.estado === 'NO_APLICA') r.cierre.rollback.estado = 'NO_VERIFICADO';
    if (!r.datos.id_area_v1) r.cierre.rollback.estado = 'NO_APLICA';
    serializarResultado(contrato, r, { previoOk: previo.ok, barreras: previo.barreras, errorEjecutor, modoEnsayo });
  }
  return r;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  if (process.argv.includes('--capacidades')) console.log(JSON.stringify(CAPACIDADES, null, 2));
  else if (process.argv.includes('--comprobar')) process.exitCode = comprobar();
  else if (process.argv.includes('--operacion')
    && process.argv[process.argv.indexOf('--operacion') + 1] === 'diagnostico') {
    try {
      const args = process.argv.slice(2);
      const valor = k => args.includes(k) ? args[args.indexOf(k) + 1] : undefined;
      exigir(!['--run-id', '--version', '--contexto', '--intento', '--run-objetivo']
        .some(k => args.includes(k)), 'DIAGNOSTICO_ARGUMENTOS_RUN_PROHIBIDOS');
      const archivo = valor('--consultas');
      exigir(archivo && path.isAbsolute(archivo) && fs.statSync(archivo).isFile()
        && !fs.lstatSync(archivo).isSymbolicLink(), 'DIAGNOSTICO_ARCHIVO_INVALIDO');
      const consultas = JSON.parse(fs.readFileSync(archivo, 'utf8'));
      diagnostico({ referencia: valor('--autorizacion'), consultas,
        maxPeticiones: Number(valor('--max-peticiones')) })
        .then(resumen => { console.log(JSON.stringify(resumen)); })
        .catch(() => { console.error('DIAGNOSTICO_FALLIDO'); process.exitCode = 2; });
    } catch { console.error('DIAGNOSTICO_CONFIG_INVALIDA'); process.exitCode = 2; }
  }
  else if (process.argv.includes('--prevalidar')) {
    const validacion = prevalidar();
    console.log(JSON.stringify(validacion, null, 2));
    process.exitCode = validacion.valido ? 0 : 2;
  }
  else if (process.argv.includes('--validar-resultado-local')) {
    try {
      const archivo = path.resolve(process.argv[process.argv.indexOf('--validar-resultado-local') + 1]);
      if (!archivo.startsWith(path.resolve(os.tmpdir()) + path.sep)
        || path.basename(archivo) !== 'resultado.json') fallo('RESULTADO_FUERA_DE_TEMPORAL');
      const r = JSON.parse(fs.readFileSync(archivo, 'utf8'));
      const revision = evaluarRegistro(r, path.dirname(archivo),
        { runId: process.argv[process.argv.indexOf('--run-id') + 1],
          version: Number(process.argv[process.argv.indexOf('--version') + 1]) });
      console.log(JSON.stringify(revision));
      process.exitCode = revision.estructura && revision.clasificacion !== 'INCIERTO' ? 0 : 2;
    } catch { console.error('VALIDACION_LOCAL_FALLIDA'); process.exitCode = 2; }
  }
  else {
    try {
      const modoEnsayo = process.env.G93_ENSAYO_LOCAL;
      if (modoEnsayo && !['ausentes', 'infra', 'hijo', 'tecnico'].includes(modoEnsayo))
        fallo('MODO_ENSAYO_INVALIDO');
      const c = contextoEjecucion(process.argv.slice(2), { grupo: 'G93', casos: [CASO],
        directorio: DIR, modoEnsayo: Boolean(modoEnsayo) });
      if (Boolean(modoEnsayo) !== Boolean(c.ensayo)) fallo('MODO_ENSAYO_REQUIERE_ID_Y_CONTEXTO_TEMPORAL');
      exigir(CAPACIDADES.operaciones.includes(c.operacion), 'OPERACION_NO_PUBLICADA');
      let opciones = { validarHerramientas: true };
      if (modoEnsayo) {
        const env = leerEnv(process.env, { cargarArchivo: modoEnsayo !== 'ausentes' });
        if (modoEnsayo === 'ausentes') for (const nombre of ['SIGAB_API_TEST_BASE', 'SIGAB_FRONT_TEST_URL',
          'QA_SANDBOX_SECRET', 'QA_ADMIN_EMAIL', 'QA_ADMIN_PASSWORD', 'QA_PROD_EMAIL', 'QA_PROD_PASSWORD']) delete env[nombre];
        const respuestaLocal = (status, cuerpo, cookie = null) => ({ status,
          headers: { get: k => k.toLowerCase() === 'set-cookie' ? cookie : null },
          json: async () => cuerpo });
        const fetcher = async (url) => {
          const ruta = new URL(url).pathname;
          if (ruta.endsWith('/sesiones/')) return modoEnsayo === 'tecnico'
            ? respuestaLocal(503, {}) : respuestaLocal(200, { token: 'TOKEN_LOCAL_FICTICIO' },
              'refresh_token=COOKIE_LOCAL_FICTICIA; HttpOnly');
          throw new Error('INFRA_LOCAL_RECHAZA_ANTES_DE_PRODUCTO');
        };
        opciones = { env, fetcher, modoEnsayo };
      }
      evaluar(c, opciones).then(r => { console.log(JSON.stringify({ run_id: r.run_id, estado: r.casos[CASO].estado }));
        process.exitCode = r.codigo_salida; })
        .catch(e => { console.error(e.message); process.exitCode = 2; });
    } catch (e) { console.error(e.message); process.exitCode = 2; }
  }
}
