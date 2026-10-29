#!/usr/bin/env node
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import vm from 'node:vm';
import { spawnSync } from 'node:child_process';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { contextoEjecucion } from './lib/contrato_ejecutor.mjs';
import { sanearArtefacto } from './lib/seguridad.mjs';
import { CASO, ORACULO, IDS, LIMITE, CAPACIDADES, idsFincas, evaluarApi, evaluarResultadoCypress } from './lib/g94_escenario.mjs';

const require = createRequire(import.meta.url);
const DIR = path.dirname(fileURLToPath(import.meta.url));
const RAIZ = path.resolve(DIR, '../../../../..');
const COLECCION = path.join(DIR, 'G94.postman_collection.json');
const SPEC = path.join(DIR, 'g94.cy.js');
const CONFIG = path.join(DIR, 'g94.cypress.config.cjs');
const API = 'https://www.api.inmero.co/api-sgpmp-test';
const API_FRONT = 'https://api.inmero.co/api-sgpmp-test';
const FRONT = 'https://api.inmero.co/sigab-test';
const guardar = (p, obj) => fs.writeFileSync(p, JSON.stringify(obj, null, 2));
const exigir = (ok, mensaje) => { if (!ok) throw new Error(mensaje); };
const seguro = (texto, secretos = []) => sanearArtefacto(String(texto ?? ''), secretos).slice(0, 300);

export function leerEnv(proceso = process.env, archivo = path.join(RAIZ, '.env.qa')) {
  const env = {};
  if (archivo && fs.existsSync(archivo)) for (const linea of fs.readFileSync(archivo, 'utf8').split(/\r?\n/)) {
    const m = linea.match(/^\s*([A-Z][A-Z0-9_]*)\s*=(.*)$/);
    if (m) env[m[1]] = m[2].trim().replace(/^(['"])(.*)\1$/, '$2');
  }
  Object.assign(env, proceso);
  env.QA_AUTORIZADO = proceso.QA_AUTORIZADO;
  return env;
}

export function preflight(c, env) {
  const claves = ['SIGAB_API_TEST_BASE', 'SIGAB_FRONT_TEST_URL', 'QA_SANDBOX_SECRET',
    'QA_ADMIN_EMAIL', 'QA_ADMIN_PASSWORD', 'QA_PROD_EMAIL', 'QA_PROD_PASSWORD'];
  const barreras = claves.filter(k => !String(env[k] ?? '').trim());
  if (env.QA_AUTORIZADO !== 'SI') barreras.push('QA_AUTORIZADO');
  if (String(env.SIGAB_API_TEST_BASE ?? '').replace(/\/+$/, '') !== API) barreras.push('API_NO_ES_TEST_OFICIAL');
  if (String(env.SIGAB_FRONT_TEST_URL ?? '').replace(/\/+$/, '') !== FRONT) barreras.push('FRONT_NO_ES_TEST_OFICIAL');
  if (c.version > 1 && c.operacion !== 'reevaluar') barreras.push('REEVALUACION_SIN_DECISION');
  if (!CAPACIDADES.operaciones.includes(c.operacion)) barreras.push('OPERACION_NO_PUBLICADA');
  return { fase: 'PREFLIGHT_LOCAL', grupo: 'G94', run_id: c.runId, version: c.version,
    operacion: c.operacion, variables: claves.map(nombre => ({ nombre, presente: Boolean(env[nombre]) })),
    plan: { escrituras: ['PUT /usuarios/{id_usuario}/fincas con ids_fincas=[] si había fincas'],
      lectura_origen: 'GET /usuarios/{id_usuario}/detalle por Administrador',
      orden: ['login fuera RUN', 'lecturas y PUT dentro RUN', 'Newman API', 'Cypress UI', 'DELETE RUN', 'GET detalle por Administrador'] },
    limite: LIMITE, barreras, ok: barreras.length === 0 };
}

export function resolverCliNewman(pathEnv = process.env.PATH) {
  for (const carpeta of String(pathEnv ?? '').split(path.delimiter).filter(Boolean)) {
    if (!['newman', 'newman.cmd'].some(n => fs.existsSync(path.join(carpeta, n)))) continue;
    const cli = path.join(carpeta, 'node_modules', 'newman', 'bin', 'newman.js');
    if (fs.existsSync(cli)) return cli;
  }
  const pkg = require.resolve('newman/package.json', { paths: [RAIZ] });
  return path.join(path.dirname(pkg), 'bin', 'newman.js');
}

export function prevalidarHerramientas({ spawn = spawnSync, cliNewman = resolverCliNewman,
  cliCypress = () => path.join(path.dirname(require.resolve('cypress/package.json', { paths: [RAIZ] })), 'bin', 'cypress'),
  chromeDisponible = () => (process.platform === 'win32'
    ? [path.join(process.env.PROGRAMFILES ?? '', 'Google/Chrome/Application/chrome.exe'),
      path.join(process.env['PROGRAMFILES(X86)'] ?? '', 'Google/Chrome/Application/chrome.exe'),
      path.join(process.env.LOCALAPPDATA ?? '', 'Google/Chrome/Application/chrome.exe')]
    : ['/usr/bin/google-chrome', '/usr/bin/chromium', '/usr/bin/chromium-browser'])
    .some(x => fs.existsSync(x)) } = {}) {
  const diagnostico = {};
  for (const [nombre, resolver] of [['newman', cliNewman], ['cypress', cliCypress]]) {
    try {
      const inicio = Date.now();
      const p = spawn(process.execPath, [resolver(), '--version'], { encoding: 'utf8', shell: false, timeout: 30000 });
      diagnostico[nombre] = { status: p.status, codigo: p.error?.code ?? null,
        vencio_tiempo: p.error?.code === 'ETIMEDOUT', duracion_ms: Date.now() - inicio,
        version: String(p.stdout ?? '').match(/\b\d+\.\d+\.\d+\b/)?.[0] ?? null };
    } catch (e) { diagnostico[nombre] = { status: null, codigo: e.code ?? 'NO_RESUELTO' }; }
  }
  const barreras = Object.entries(diagnostico).filter(([, d]) => d.status !== 0 || d.codigo)
    .map(([k, d]) => `HERRAMIENTA_${k.toUpperCase()}_${d.codigo ?? d.status}`);
  diagnostico.chrome = { disponible: chromeDisponible() };
  if (!diagnostico.chrome.disponible) barreras.push('HERRAMIENTA_CHROME_AUSENTE');
  return { valido: barreras.length === 0, barreras, diagnostico };
}

export function comprobar() {
  const fetchAnterior = globalThis.fetch;
  globalThis.fetch = () => { throw Error('RED_PROHIBIDA_EN_COMPROBAR'); };
  try {
    const requeridos = ['g94.mjs', 'G94.postman_collection.json', 'g94.cy.js',
      'g94.cypress.config.cjs', 'lib/contrato_ejecutor.mjs', 'lib/seguridad.mjs',
      'lib/g94_escenario.mjs', 'pruebas/g94.test.mjs', 'README.md'];
    const faltantes = requeridos.filter(x => !fs.existsSync(path.join(DIR, x)));
    const c = JSON.parse(fs.readFileSync(COLECCION, 'utf8'));
    for (const event of [...(c.event ?? []), ...c.item.flatMap(x => x.event ?? [])])
      new vm.Script((event.script?.exec ?? []).join('\n'));
    const spec = fs.readFileSync(SPEC, 'utf8');
    const coleccion = JSON.stringify(c);
    const muestra = { run_id: 'RUN-G94-V1-PRUEBA', version: 1, autorizacion: 'LOCAL',
      oficial: false, consume_version: false, preflight_herramientas: {},
      casos: { [CASO]: { estado: 'NO_CONCLUYENTE', estado_tecnico: 'NO_CONCLUYENTE',
        motivo: 'UI sin respuesta' } }, comprobaciones: IDS.map(id => ({ id,
        fuente: id.startsWith('UI') ? 'UI' : 'API',
        estado: id.startsWith('UI') ? 'NO_CONCLUYENTE' : 'APROBADO',
        motivo: id.startsWith('UI') ? 'UI sin respuesta' : 'HTTP 200', evidencia: null })),
      evidencias: [], observado: { ui: {} }, problemas_tecnicos: [],
      cierre: { run: {}, rollback: { verificado: false, ids_fincas_posteriores: [] }, motivo: '' },
      datos: { ids_fincas_originales: [] } };
    const informeMuestra = informe(muestra);
    const decisionesValidas = informeMuestra.startsWith('# TC-M03-G94 — BLOQUEADO\n\n## Decisión del caso\n')
      && informeMuestra.indexOf('## Decisión del caso') < informeMuestra.indexOf('## Identificación')
      && !informeMuestra.slice(0, informeMuestra.indexOf('## Identificación')).includes('**Decisión:** **APROBADO**')
      && encabezadoDecision({ ...muestra, comprobaciones: muestra.comprobaciones.map(x =>
        x.id === 'UI-185-01' ? { ...x, estado: 'ERROR_QA' } : x) }).startsWith('# TC-M03-G94 — BLOQUEADO')
      && encabezadoDecision({ ...muestra, casos: { [CASO]: { estado: 'RECHAZADO', motivo: 'texto distinto' } } })
        .startsWith('# TC-M03-G94 — RECHAZADO')
      && encabezadoDecision({ ...muestra, oficial: true,
        comprobaciones: muestra.comprobaciones.map(x => ({ ...x, estado: 'APROBADO' })),
        casos: { [CASO]: { estado: 'APROBADO', motivo: 'Oráculo completo' } } })
        .startsWith('# TC-M03-G94 — APROBADO');
    const ok = decisionesValidas && faltantes.length === 0 && c.item.length === 2
      && IDS.every(id => (coleccion + spec).includes(`[${id}]`))
      && CAPACIDADES.comprobaciones_obligatorias[CASO].API.length === 2
      && CAPACIDADES.comprobaciones_obligatorias[CASO].UI.length === 1
      && spec.includes('req.continue') && !/req\.reply\s*\(/.test(spec)
      && spec.includes("API === 'https://api.inmero.co/api-sgpmp-test'")
      && coleccion.includes('X-Test-Run-Id') && coleccion.includes('X-Sandbox-Secret');
    console.log(JSON.stringify({ grupo: 'G94', ok, faltantes, contrato: CAPACIDADES.contrato }));
    return ok ? 0 : 2;
  } finally { globalThis.fetch = fetchAnterior; }
}

export function crearTransporte({ base = API, runId, secreto, bitacora = [], fetcher = fetch }) {
  let abierto = false, cerrado = false, solicitudes = 0, dentro = 0, ui = false;
  let idProductor = null;
  async function pedir(metodo, ruta, { token, cuerpo, login = false, cierre = false } = {}) {
    exigir(!ui, 'PETICION_DURANTE_CYPRESS');
    exigir(solicitudes < LIMITE.solicitudes_directas, 'LIMITE_TOTAL');
    if (login) exigir(!abierto && !cerrado && metodo === 'POST' && ruta === '/sesiones/', 'LOGIN_DENTRO_RUN_PROHIBIDO');
    else if (cierre) exigir(abierto && metodo === 'DELETE' && ruta === `/test-control/runs/${runId}`, 'CIERRE_INVALIDO');
    else {
      exigir(abierto || cerrado && metodo === 'GET', 'PETICION_FUERA_RUN');
      if (abierto) exigir(solicitudes < LIMITE.solicitudes_directas - LIMITE.margen_cierre,
        'LIMITE_FUNCIONAL_RESERVA_CIERRE');
      const lectura = ruta === '/usuarios/me' || ruta === '/configuracion/fincas'
        || /^\/usuarios\/\d+\/detalle$/.test(ruta)
        || /^\/configuracion\/infraestructuras\?finca_id=\d+&solo_activas=true$/.test(ruta);
      if (metodo === 'GET') exigir(lectura, 'LECTURA_FUERA_LISTA_BLANCA');
      else exigir(metodo === 'PUT' && ruta === `/usuarios/${idProductor}/fincas`
        && JSON.stringify(cuerpo) === '{"ids_fincas":[]}', 'ESCRITURA_FUERA_LISTA_BLANCA');
    }
    solicitudes++;
    if (abierto && !cierre) dentro++;
    const headers = { Accept: 'application/json' };
    if (token) headers.Authorization = `Bearer ${token}`;
    if (abierto && !cierre) { headers['X-Test-Run-Id'] = runId; headers['X-Sandbox-Secret'] = secreto; }
    if (cierre) headers['X-Sandbox-Secret'] = secreto;
    if (cuerpo) headers['Content-Type'] = 'application/json';
    const inicio = Date.now();
    const response = await fetcher(base + ruta, { method: metodo, headers,
      body: cuerpo ? JSON.stringify(cuerpo) : undefined, redirect: 'manual',
      signal: AbortSignal.timeout(30000) });
    let json = null; try { json = await response.json(); } catch { /* vacío */ }
    const eco = response.headers.get('X-Test-Run-Id');
    bitacora.push({ metodo, ruta, http: response.status, en_run: abierto && !cierre,
      eco_correcto: abierto && !cierre ? eco === runId : null, ms: Date.now() - inicio });
    if (abierto && !cierre) exigir(eco === runId, 'ECO_RUN_AUSENTE');
    if (cierre && response.status === 200) { abierto = false; cerrado = true; }
    return { http: response.status, cuerpo: json, cookie: login ? response.headers.get('set-cookie') : null };
  }
  return { pedir, abrir: () => { abierto = true; }, idProductor: id => {
    exigir(Number.isSafeInteger(id) && id > 0, 'ID_PRODUCTOR_INVALIDO'); idProductor = id;
  }, iniciarUi: () => { exigir(abierto, 'UI_FUERA_RUN'); ui = true; },
  terminarUi: () => { ui = false; },
  estado: () => ({ abierto, cerrado, solicitudes, remotas_en_run: dentro }) };
}

function idsDetalle(respuesta, id, correo) {
  exigir(respuesta.http === 200 && Number(respuesta.cuerpo?.id_usuario) === id
    && String(respuesta.cuerpo?.correo_electronico).toLowerCase() === String(correo).toLowerCase()
    && Array.isArray(respuesta.cuerpo?.fincas), 'PRE_IDENTIDAD_PRODUCTOR_NO_ACREDITADA');
  const ids = respuesta.cuerpo.fincas.map(x => Number(x.id_finca));
  exigir(ids.every(x => Number.isSafeInteger(x) && x > 0) && new Set(ids).size === ids.length,
    'PRE_FINCAS_DETALLE_INVALIDAS');
  return ids.sort((a, b) => a - b);
}

export function mismoConjuntoFincas(antes, despues) {
  return Array.isArray(antes) && Array.isArray(despues)
    && JSON.stringify([...antes].sort((a, b) => a - b))
      === JSON.stringify([...despues].sort((a, b) => a - b));
}

function cookieRefresco(cabecera) {
  const m = /(?:^|[,\s])refresh_token=([^;\s,]+)/.exec(cabecera ?? '');
  exigir(m?.[1], 'COOKIE_REFRESH_AUSENTE');
  return m[1];
}

export function ejecutarNewman(c, { base = API, token, secreto, idArea, secretos, spawn = spawnSync }) {
  const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'g94-newman-'));
  try {
    const envPath = path.join(temp, 'env.json');
    const reporte = path.join(temp, 'reporte.json');
    const vars = { qa_autorizado: 'SI', base_url: base, token_productor: token,
      run_id: c.runId, sandbox_secret: secreto, id_area_previa: idArea ?? '' };
    guardar(envPath, { values: Object.entries(vars).map(([key, value]) => ({ key, value: String(value), enabled: true })) });
    const p = spawn(process.execPath, [resolverCliNewman(), 'run', COLECCION, '-e', envPath,
      '--reporters', 'json', '--reporter-json-export', reporte, '--timeout-request', '30000',
      '--color', 'off'], { encoding: 'utf8', shell: false, timeout: 75000, maxBuffer: 8 * 1024 * 1024 });
    exigir(fs.existsSync(reporte), `NEWMAN_SIN_REPORTE_${p.error?.code ?? p.status}`);
    const rep = JSON.parse(fs.readFileSync(reporte, 'utf8'));
    const dir = path.join(c.directorio, 'newman'); fs.mkdirSync(dir, { recursive: true });
    const rel = 'newman/newman-G94.json';
    fs.writeFileSync(path.join(c.directorio, rel), sanearArtefacto(JSON.stringify(rep), secretos));
    const respuestas = rep.run?.executions?.map(ex => ({
      id: /\[(API-185-0[12])\]/.exec(ex.item?.name ?? '')?.[1] ?? null,
      http: ex.response?.code ?? null,
      eco: (ex.response?.header ?? []).some(x => x.key?.toLowerCase() === 'x-test-run-id' && x.value === c.runId),
      cuerpo: (() => { try { return JSON.parse(Buffer.from(ex.response?.stream?.data ?? []).toString('utf8')); } catch { return null; } })(),
    })) ?? [];
    const htmlRel = 'newman/newman-G94.html';
    const filas = respuestas.map(x => `<tr><td>${x.id}</td><td>${x.http}</td><td>${x.eco}</td></tr>`).join('');
    fs.writeFileSync(path.join(c.directorio, htmlRel), `<!doctype html><html lang="es"><meta charset="utf-8"><title>Newman G94</title><h1>Newman G94</h1><table><tr><th>ID</th><th>HTTP</th><th>Eco RUN</th></tr>${filas}</table></html>`);
    return { respuestas, rel, htmlRel, proceso: p.status, fallos: rep.run?.failures?.length ?? 0 };
  } finally { fs.rmSync(temp, { recursive: true, force: true }); }
}

export function variablesCypress(c, { cookie, secreto, dir }) {
  return { AUTORIZADO_RUN: 'SI', API_BASE: API_FRONT, FRONT_BASE: FRONT,
    RUN_ID: c.runId, SANDBOX_SECRET: secreto, REFRESH_COOKIE: cookie, ARTIFACTS_DIR: dir };
}

export function ejecutarCypress(c, { cookie, secreto, secretos, spawn = spawnSync }) {
  const dir = path.join(c.directorio, 'cypress'); fs.mkdirSync(dir, { recursive: true });
  const vars = variablesCypress(c, { cookie, secreto, dir });
  const env = { ...process.env, ...Object.fromEntries(Object.entries(vars).map(([k, v]) => [`CYPRESS_${k}`, v])) };
  const cli = path.join(path.dirname(require.resolve('cypress/package.json', { paths: [RAIZ] })), 'bin', 'cypress');
  const args = ['run', '--project', DIR, '--spec', SPEC, '--config-file', CONFIG,
    '--config', `screenshotsFolder=${dir},videosFolder=${dir},downloadsFolder=${dir}`,
    '--browser', 'chrome', '--headless'];
  const inicio = Date.now();
  const p = spawn(process.execPath, [cli, ...args], { cwd: DIR, shell: false, env,
    encoding: 'utf8', timeout: 90000, maxBuffer: 8 * 1024 * 1024 });
  const logRel = 'cypress/UI-185-01.log';
  fs.writeFileSync(path.join(c.directorio, logRel), sanearArtefacto(
    `STDOUT\n${p.stdout ?? ''}\nSTDERR\n${p.stderr ?? ''}\n`, [...secretos, cookie]));
  const reciente = rel => {
    const archivo = path.join(c.directorio, rel);
    return fs.existsSync(archivo) && fs.statSync(archivo).mtimeMs >= inicio;
  };
  const rel = 'cypress/UI-185-01.json';
  const acta = reciente(rel)
    ? JSON.parse(fs.readFileSync(path.join(c.directorio, rel), 'utf8')) : null;
  const resumenRel = 'cypress/UI-185-01-cypress.json';
  const resumen = reciente(resumenRel)
    ? JSON.parse(fs.readFileSync(path.join(c.directorio, resumenRel), 'utf8')) : null;
  const capturas = fs.readdirSync(dir, { recursive: true }).filter(x =>
    /UI-185-01.*\.png$/i.test(x) && fs.statSync(path.join(dir, String(x))).mtimeMs >= inicio)
    .map(x => `cypress/${String(x).replaceAll('\\', '/')}`);
  return { acta, rel: acta ? rel : null, resumen, resumenRel: resumen ? resumenRel : null,
    logRel, capturas, proceso: p.status, error: p.error?.code ?? null };
}

function registrar(r, id, estado, motivo, evidencia = null) {
  const fuente = id.startsWith('UI') ? 'UI' : 'API';
  const actual = r.comprobaciones.find(x => x.id === id);
  const dato = { caso: CASO, id, fuente, herramienta: fuente === 'UI' ? 'Cypress' : 'Newman',
    tipo: 'ASSERT', estado, motivo, evidencia };
  if (actual) Object.assign(actual, dato); else r.comprobaciones.push(dato);
}

export function encabezadoDecision(r) {
  const comprobaciones = r.comprobaciones ?? [];
  const estado = r.casos?.[CASO]?.estado;
  const hayRechazo = comprobaciones.some(x => x.estado === 'RECHAZADO');
  const todoAprobado = IDS.every(id => comprobaciones.some(x => x.id === id && x.estado === 'APROBADO'));
  const decision = hayRechazo || estado === 'RECHAZADO' ? 'RECHAZADO'
    : estado === 'APROBADO' && todoAprobado && r.oficial ? 'APROBADO' : 'BLOQUEADO';
  const noConcluyente = comprobaciones.some(x => ['NO_CONCLUYENTE', 'ERROR_QA'].includes(x.estado))
    || estado === 'NO_CONCLUYENTE';
  const motivo = decision === 'APROBADO' ? 'Las comprobaciones obligatorias y el cierre constan conformes.'
    : decision === 'RECHAZADO' ? r.casos?.[CASO]?.motivo ?? 'Discrepancia pública acreditada.'
      : `No se puede aprobar: ${r.casos?.[CASO]?.motivo ?? 'falta una comprobación concluyente'}${noConcluyente ? ' (resultado no concluyente).' : '.'}`;
  const filas = IDS.map(id => {
    const x = comprobaciones.find(y => y.id === id);
    return `| ${id} | ${x?.estado ?? 'NO_EJECUTADA'}${x?.motivo ? ` — ${x.motivo}` : ''} |`;
  }).join('\n');
  const pendiente = decision === 'APROBADO' ? 'Nada para cerrar este RUN.'
    : decision === 'RECHAZADO' ? 'Revisar la discrepancia acreditada y decidir la corrección y reevaluación.'
      : 'Resolver la causa del bloqueo o la falta de evidencia y reevaluar las comprobaciones pendientes.';
  return `# TC-M03-G94 — ${decision}\n\n## Decisión del caso\n\n`
    + `- **Caso agrupado:** TC-M03-G94\n- **Caso original:** ${CASO} (RF-58 / CU04 E4) — usuario sin unidades productivas asignadas.\n`
    + `- **Decisión:** **${decision}**\n- **Motivo:** ${motivo}\n\n`
    + `| Comprobación | Resultado |\n|---|---|\n${filas}\n\n`
    + `- **¿RUN oficial?:** ${r.oficial ? 'Sí' : 'No'}${r.oficial ? '.' : ' (falta un veredicto completo y conforme de UI/cierre).'}\n`
    + `- **Qué falta para cerrar:** ${pendiente}\n\n`;
}

function informe(r) {
  const fila = x => `| ${x.id} | ${x.fuente} | ${x.estado} | ${x.motivo} | ${x.evidencia ?? 'Sin evidencia'} |`;
  const rechazadas = r.comprobaciones.filter(x => x.estado === 'RECHAZADO');
  const incidencias = rechazadas.length ? rechazadas.map(x => {
    const fuga = x.id.startsWith('API') && r.newman.some(n =>
      n.respuestas?.some(y => y.id === x.id && y.datos_presentes === true));
    const severidad = fuga ? 'CRÍTICA' : 'ALTA';
    return `- ${x.id}: primer contacto **Desarrollo**, por discrepancia pública de ${x.fuente} en TEST. `
      + `Severidad ${severidad}; certeza CONFIRMADA para la respuesta observada, causa raíz NO DETERMINADA. `
      + `Esperado: ${ORACULO} Observado: ${x.motivo}. Evidencia: ${x.evidencia ?? 'sin artefacto'}. `
      + 'Responsable QA: decidir ticket tras revisar el artefacto.';
  }).join('\n') : 'Sin discrepancias funcionales acreditadas en este RUN.';
  const entorno = '\n- **INC-M03-184-G93-02 (abierta, primer contacto DBA):** en '
    + 'el intento 1 documentado en el informe consolidado V1, con cabeceras del sandbox, POST /sesiones/refresh fue 200 '
    + 'y GET /usuarios/me y GET /sesiones/me/permisos fueron 500; la UI no pidió el dashboard. '
    + 'Severidad ALTA para la evaluación UI de ese intento; certeza CONFIRMADA del HTTP, '
    + 'causa raíz NO DETERMINADA. El GET /usuarios/me con el token previo al RUN fue 200. '
    + 'La decisión metodológica permite evaluar esta UI, pero no cierra la incidencia. '
    + 'Responsable QA: mantener seguimiento con DBA y verificar la corrección por separado.\n';
  const evidencias = r.evidencias.filter(x => x !== 'resultado.json').map(x => `- ${x}`).join('\n') || '- Sin artefactos de herramientas.';
  return encabezadoDecision(r) + `## Identificación\n\nGrupo G94; caso ${CASO}; RF-58/CU04 E4; `
    + `V${r.version}; RUN ${r.run_id}; ambiente TEST; autorización ${r.autorizacion}; `
    + `commit NO VERIFICADO (Git prohibido); Node ${process.version}; herramientas: `
    + `${JSON.stringify(r.preflight_herramientas)}. Oficial: ${r.oficial}. Consume versión: ${r.consume_version}.\n\n`
    + `## Resumen de veredictos\n\n${CASO}: funcional ${r.casos[CASO].estado}; técnico ${r.casos[CASO].estado_tecnico}. `
    + `${r.casos[CASO].motivo}\n\n## Esperado y observado por caso\n\nEsperado literal de la matriz: ${ORACULO}\n\n`
    + `Observado: ${JSON.stringify(r.observado)}. No se infiere veredicto de código local.\n\n`
    + `## Decisión metodológica de la UI\n\nEl responsable QA aprobó el 2026-10-26 `
    + `enviar fuera del sandbox solo POST /sesiones/refresh, GET /usuarios/me y `
    + `GET /sesiones/me/permisos del navegador. Ninguna lleva cabeceras RUN y ninguna `
    + `debe recibir eco. El resto, incluidos GET /configuracion/interfaz/contexto y `
    + `GET /iot/monitoreo/dashboard, lleva las cabeceras y exige eco; dashboard sin eco `
    + `es NO_CONCLUYENTE. MonitoreoView.tsx:46,152-172 usa useMonitoreo.ts:21; `
    + `monitoreoApi.ts:43-44 solicita el dashboard. App.tsx:95-100,247-252,303 `
    + `limita el bloqueo sin finca a /dashboard. AuthContext.tsx:244-263 restaura perfil `
    + `y permisos de sesión; los permisos dependen del rol y no de las fincas. `
    + `La rotación real de la sesión del Productor por /sesiones/refresh persiste tras DELETE. `
    + `El perfil fuera del sandbox puede mostrar sus fincas reales; se registra solo su número `
    + `y esa discrepancia no alimenta la vista de monitoreo, que usa el dashboard en el RUN. `
    + `Rutas observadas fuera: ${JSON.stringify(r.observado.ui?.rutas_fuera_sandbox ?? [])}; `
    + `número de fincas del perfil: ${r.observado.ui?.fincas_perfil ?? 'NO CONSTA'}.\n\n`
    + `## Comprobaciones API/UI\n\n| ID | Fuente | Estado | Observado | Evidencia |\n|---|---|---|---|---|\n`
    + `${r.comprobaciones.map(fila).join('\n')}\n\n## Evidencias reales\n\n${evidencias}\n\n`
    + `## Incidencias de producto\n\n${incidencias}${entorno}\n\n## Incidencias técnicas QA\n\n`
    + `${r.problemas_tecnicos.map(x => `- ${x}`).join('\n') || 'Sin incidencias técnicas acreditadas.'}\n\n`
    + `## Análisis de causas\n\nLa derivación inicial se basa en la primera discrepancia pública; no demuestra causa raíz. `
    + `El código local solo origina un candidato funcional hasta la comprobación autorizada.\n\n`
    + `## Efectos externos\n\nLa evaluación puede emitir eventos de login fuera del RUN y auditoría de lecturas. `
    + `La única escritura de escenario es PUT de fincas dentro del sandbox. Sin sensores visibles, `
    + `el caso de uso no llama al aviso E7; una fuga que devuelva sensores podría activarlo. `
    + `No se verificó ausencia de efectos externos fuera del rollback.\n\n`
    + `## Cierre y rollback\n\nDELETE HTTP ${r.cierre.run.cierre_http ?? 'NO CONSTA'}; `
    + `fincas originales ${JSON.stringify(r.datos.ids_fincas_originales)}; `
    + `fincas posteriores ${JSON.stringify(r.cierre.rollback.ids_fincas_posteriores)}; `
    + `rollback ${r.cierre.rollback.verificado ? 'CONFIRMADO por lectura pública' : 'NO VERIFICADO'}. `
    + `${r.cierre.motivo}. No se declara reversible la auditoría ni los login.\n\n`
    + `## Conclusión y acción concreta\n\n${r.casos[CASO].estado}. `
    + `Responsable QA: revisar evidencias, incidencias y cierre antes de decidir el siguiente RUN.\n`;
}

export function serializarResultado(c, r) {
  for (const id of IDS) if (!r.comprobaciones.some(x => x.id === id))
    registrar(r, id, 'NO_EJECUTADA', 'Sin ejecución acreditada');
  r.evidencias = [...new Set(r.evidencias.filter(x => x === 'resultado.json'
    || fs.existsSync(path.join(c.directorio, x))))];
  const estados = r.comprobaciones.map(x => x.estado);
  const rechazado = estados.includes('RECHAZADO');
  const bloqueado = estados.includes('BLOQUEADO');
  const noConcluyente = estados.includes('NO_CONCLUYENTE');
  const capturaUi = r.observado.ui?.captura === true
    && r.evidencias.some(x => x.toLowerCase().endsWith('.png'));
  const completo = IDS.every(id => r.comprobaciones.some(x => x.id === id
    && ['APROBADO', 'RECHAZADO'].includes(x.estado))) && r.cypress.total_pruebas === 1
    && capturaUi;
  r.casos[CASO].estado = rechazado ? 'RECHAZADO'
    : completo && r.cierre.rollback.verificado ? 'APROBADO'
      : bloqueado ? 'BLOQUEADO' : 'NO_CONCLUYENTE';
  r.casos[CASO].estado_tecnico = r.problemas_tecnicos.length || bloqueado || noConcluyente
    ? 'NO_CONCLUYENTE' : 'OK';
  r.casos[CASO].motivo = rechazado ? 'Discrepancia pública acreditada'
    : bloqueado ? r.comprobaciones.find(x => x.estado === 'BLOQUEADO')?.motivo
      : noConcluyente ? r.comprobaciones.find(x => x.estado === 'NO_CONCLUYENTE')?.motivo
        : !capturaUi ? 'Captura UI no acreditada'
      : !completo ? 'Falta comprobación obligatoria concluyente'
      : !r.cierre.rollback.verificado ? 'Rollback sin lectura pública conforme' : 'Oráculo completo';
  r.oficial = completo && r.problemas_tecnicos.length === 0
    && r.cierre.rollback.verificado && r.cierre.run.cierre_http === 200
    && r.evidencias.some(x => x.toLowerCase().endsWith('.png'))
    && r.evidencias.every(x => x === 'resultado.json' || fs.existsSync(path.join(c.directorio, x)));
  r.codigo_salida = r.problemas_tecnicos.length || !r.cierre.rollback.verificado ? 2 : 0;
  const archivo = c.version === 1 ? 'TC-M03-G94_resultado.md'
    : `TC-M03-G94_reevaluacion_V${c.version}.md`;
  guardar(path.join(c.directorio, 'resultado.json'), r);
  fs.writeFileSync(path.join(c.directorio, archivo), informe(r));
  return r;
}

export async function evaluar(c, { env = leerEnv(), fetcher = fetch,
  runNewman = ejecutarNewman, runCypress = ejecutarCypress,
  validarHerramientas = true, prevalidar = prevalidarHerramientas } = {}) {
  exigir(!fs.existsSync(path.join(c.directorio, 'resultado.json')), 'RUN_CON_RESULTADO_EXISTENTE');
  const previo = preflight(c, env);
  if (validarHerramientas) {
    const h = prevalidar();
    previo.herramientas = h.diagnostico;
    previo.barreras.push(...h.barreras);
    previo.ok = previo.barreras.length === 0;
  }
  fs.mkdirSync(c.directorio, { recursive: true });
  guardar(path.join(c.directorio, 'preflight.json'), previo);
  const r = { grupo: 'G94', run_id: c.runId, version: c.version,
    operacion: c.operacion, autorizacion: c.referencia, oficial: false, consume_version: false,
    preflight_herramientas: previo.herramientas ?? null,
    casos: { [CASO]: { id: CASO, estado: 'NO_EJECUTADA', estado_tecnico: 'NO_EJECUTADA', motivo: 'Sin iniciar' } },
    datos: { id_usuario: null, ids_fincas_originales: [], id_area_previa: null, retiro_realizado: false },
    observado: {}, comprobaciones: [], bitacora: [], newman: [],
    cypress: { total_pruebas: 0, detalle: [] }, evidencias: ['preflight.json', 'resultado.json'],
    problemas_tecnicos: [], cierre: { run: { cierre_http: null },
      rollback: { verificado: false, estado: 'NO_APLICA', ids_fincas_posteriores: null,
        comprobaciones: [] }, motivo: 'No iniciado' } };
  const secretos = [env.QA_SANDBOX_SECRET, env.QA_ADMIN_EMAIL, env.QA_PROD_EMAIL,
    env.QA_ADMIN_PASSWORD, env.QA_PROD_PASSWORD].filter(Boolean);
  const t = crearTransporte({ runId: c.runId, secreto: env.QA_SANDBOX_SECRET,
    bitacora: r.bitacora, fetcher });
  let admin, productor, cookie;
  try {
    exigir(previo.ok, `PREFLIGHT_LOCAL_${previo.barreras.join('_')}`);
    // Ambos login terminan antes de abrir el sandbox. Un fallo aborta sin PUT.
    const a = await t.pedir('POST', '/sesiones/', { login: true,
      cuerpo: { correo_electronico: env.QA_ADMIN_EMAIL, contrasena: env.QA_ADMIN_PASSWORD } });
    exigir(a.http === 200 && a.cuerpo?.token, 'LOGIN_ADMIN_PRE_RUN_FALLIDO');
    const p = await t.pedir('POST', '/sesiones/', { login: true,
      cuerpo: { correo_electronico: env.QA_PROD_EMAIL, contrasena: env.QA_PROD_PASSWORD } });
    exigir(p.http === 200 && p.cuerpo?.token, 'LOGIN_PRODUCTOR_PRE_RUN_FALLIDO');
    admin = a.cuerpo.token; productor = p.cuerpo.token; cookie = cookieRefresco(p.cookie);
    secretos.push(admin, productor, cookie);
    t.abrir();
    const perfil = await t.pedir('GET', '/usuarios/me', { token: productor });
    const id = Number(perfil.cuerpo?.id_usuario);
    exigir(perfil.http === 200 && Number.isSafeInteger(id) && id > 0
      && String(perfil.cuerpo?.correo_electronico).toLowerCase() === env.QA_PROD_EMAIL.toLowerCase(),
    'PRE_PRODUCTOR_NO_IDENTIFICADO');
    t.idProductor(id); r.datos.id_usuario = id;
    const detalle = await t.pedir('GET', `/usuarios/${id}/detalle`, { token: admin });
    const originales = idsDetalle(detalle, id, env.QA_PROD_EMAIL);
    r.datos.ids_fincas_originales = originales;
    const visibles = idsFincas(await t.pedir('GET', '/configuracion/fincas', { token: productor }));
    exigir(JSON.stringify(originales) === JSON.stringify(visibles), 'PRE_ALCANCE_INCOHERENTE');
    // Se elige un área real que el Productor podía ver antes de retirar sus fincas.
    for (const finca of originales.slice(0, 9)) {
      try {
        const areas = await t.pedir('GET', `/configuracion/infraestructuras?finca_id=${finca}&solo_activas=true`,
          { token: productor });
        exigir(areas.http === 200 && Array.isArray(areas.cuerpo?.items), 'PRE_AREAS_NO_VERIFICABLES');
        const idArea = Number(areas.cuerpo.items[0]?.id_infraestructura);
        if (Number.isSafeInteger(idArea) && idArea > 0) { r.datos.id_area_previa = idArea; break; }
      } catch (e) { (r.observado.areas_no_consultables ??= []).push(seguro(e.message, secretos)); }
    }
    if (originales.length) {
      const retiro = await t.pedir('PUT', `/usuarios/${id}/fincas`, { token: admin, cuerpo: { ids_fincas: [] } });
      exigir(retiro.http === 200, 'PRE_RETIRO_FINCAS_FALLIDO');
      r.datos.retiro_realizado = true;
    }
    const despues = await t.pedir('GET', `/usuarios/${id}/detalle`, { token: admin });
    exigir(idsDetalle(despues, id, env.QA_PROD_EMAIL).length === 0, 'PRE_RETIRO_NO_ACREDITADO');
    exigir(idsFincas(await t.pedir('GET', '/configuracion/fincas', { token: productor })).length === 0,
      'PRE_PRODUCTOR_SIGUE_CON_FINCAS');
    // Toda la API se ejecuta antes de iniciar Cypress.
    try {
      const n = runNewman(c, { token: productor, secreto: env.QA_SANDBOX_SECRET,
        idArea: r.datos.id_area_previa, secretos });
      r.newman.push({ archivo: n.rel, proceso: n.proceso, fallos: n.fallos,
        respuestas: n.respuestas.map(x => ({ id: x.id, http: x.http, eco_run: x.eco,
          datos_presentes: Boolean(x.cuerpo?.resumen_unidades?.length || x.cuerpo?.sensores?.length) })) });
      r.evidencias.push(n.rel, n.htmlRel);
      for (const idApi of IDS.filter(x => x.startsWith('API'))) {
        const x = n.respuestas.find(y => y.id === idApi);
        if (idApi === 'API-185-02' && !r.datos.id_area_previa) {
          registrar(r, idApi, 'BLOQUEADO', r.observado.areas_no_consultables?.length
            ? 'Lecturas públicas de áreas incompletas; no se obtuvo área previa sin exceder presupuesto'
            : 'No hay área previamente asignada entre las fincas acotadas; no se crea una por restricción de la orden');
          continue;
        }
        if (!x || !x.eco) { registrar(r, idApi, 'BLOQUEADO', 'Newman sin respuesta o eco RUN', n.rel); continue; }
        const evaluacion = evaluarApi(idApi, { http: x.http, cuerpo: x.cuerpo });
        registrar(r, idApi, evaluacion.estado, evaluacion.motivo, n.rel);
      }
    } catch (e) { r.problemas_tecnicos.push(`NEWMAN: ${seguro(e.message, secretos)}`); }
    // La UI es la última actividad funcional. Después solo Admin cierra y verifica.
    try {
      t.iniciarUi();
      const ui = runCypress(c, { cookie, secreto: env.QA_SANDBOX_SECRET, secretos });
      const evaluacion = evaluarResultadoCypress(ui);
      r.cypress.total_pruebas = Number.isInteger(ui.resumen?.totalPassed)
        && Number.isInteger(ui.resumen?.totalFailed)
        ? ui.resumen.totalPassed + ui.resumen.totalFailed : 0;
      r.cypress.resumen = ui.resumen;
      r.cypress.detalle.push({ estado: evaluacion.estado, motivo: evaluacion.motivo,
        proceso: ui.proceso, error: ui.error, archivo: ui.rel, resumen: ui.resumenRel });
      r.evidencias.push(ui.logRel, ...(ui.rel ? [ui.rel] : []),
        ...(ui.resumenRel ? [ui.resumenRel] : []), ...ui.capturas);
      if (ui.acta?.captura === false || ui.capturas.length === 0)
        r.problemas_tecnicos.push(`CAPTURA_UI_185_01: ${seguro(ui.acta?.motivo_captura || 'PNG ausente', secretos)}`);
      registrar(r, 'UI-185-01', evaluacion.estado, evaluacion.motivo, ui.rel);
      r.observado.ui = ui.acta ? { dashboard: ui.acta.dashboard,
        peticiones: ui.acta.peticiones, rutas_fuera_sandbox: ui.acta.rutas_fuera_sandbox,
        fincas_perfil: ui.acta.fincas_perfil,
        captura: ui.acta.captura, motivo_captura: ui.acta.motivo_captura,
        mensaje_exacto: ui.acta.mensaje_exacto, contacto_admin: ui.acta.contacto_admin,
        sin_tarjetas: ui.acta.sin_tarjetas, texto_observado: ui.acta.texto_observado } : null;
      if (evaluacion.estado === 'ERROR_QA') r.problemas_tecnicos.push(evaluacion.motivo);
    } catch (e) {
      const motivo = `CYPRESS_ERROR_QA: ${seguro(e.message, secretos)}`;
      r.problemas_tecnicos.push(motivo);
      registrar(r, 'UI-185-01', 'ERROR_QA', motivo);
    }
    finally { t.terminarUi(); }
  } catch (e) { r.problemas_tecnicos.push(seguro(e.message, secretos)); }
  finally {
    if (t.estado().abierto) {
      // Nunca se usa el token Productor tras Cypress.
      try {
        let fin;
        for (let intento = 0; intento < 2; intento++) {
          try {
            fin = await t.pedir('DELETE', `/test-control/runs/${c.runId}`, { cierre: true });
            if (fin.http === 200) break;
          } catch (e) { if (intento === 1) throw e; }
        }
        r.cierre.run.cierre_http = fin.http;
        if (fin.http === 200 && admin && r.datos.id_usuario) {
          const detalleFinal = await t.pedir('GET', `/usuarios/${r.datos.id_usuario}/detalle`, { token: admin });
          const ids = idsDetalle(detalleFinal, r.datos.id_usuario, env.QA_PROD_EMAIL);
          r.cierre.rollback.ids_fincas_posteriores = ids;
          r.cierre.rollback.verificado = mismoConjuntoFincas(ids, r.datos.ids_fincas_originales);
          r.cierre.rollback.estado = r.cierre.rollback.verificado ? 'CONFIRMADO' : 'NO_VERIFICADO';
          r.cierre.rollback.comprobaciones.push({ recurso: 'fincas_productor', http: detalleFinal.http,
            ok: r.cierre.rollback.verificado });
          r.cierre.motivo = r.cierre.rollback.verificado ? 'Conjunto exacto de fincas restituido por DELETE'
            : 'Conjunto de fincas diferente al original';
        } else { r.cierre.motivo = 'DELETE o lectura pública posterior incompletos';
          r.cierre.rollback.estado = 'NO_VERIFICADO'; }
      } catch (e) { r.cierre.motivo = `Cierre no verificado: ${seguro(e.message, secretos)}`;
        r.cierre.rollback.estado = 'NO_VERIFICADO';
        r.problemas_tecnicos.push(r.cierre.motivo); }
    } else if (!t.estado().cerrado) r.cierre.motivo = 'RUN no abierto; sin efectos de negocio';
    r.consume_version = t.estado().remotas_en_run > 0 || r.newman.length > 0 || r.cypress.total_pruebas > 0;
    r.observado.api = r.comprobaciones.filter(x => x.fuente === 'API')
      .map(x => ({ id: x.id, estado: x.estado, motivo: x.motivo,
        http: r.newman.flatMap(n => n.respuestas ?? []).find(y => y.id === x.id)?.http ?? null }));
    serializarResultado(c, r);
  }
  return r;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  if (process.argv.includes('--capacidades')) console.log(JSON.stringify(CAPACIDADES, null, 2));
  else if (process.argv.includes('--comprobar')) process.exitCode = comprobar();
  else {
    try {
      const c = contextoEjecucion(process.argv.slice(2), { grupo: 'G94', casos: [CASO], directorio: DIR });
      evaluar(c).then(r => { console.log(JSON.stringify({ run_id: r.run_id,
        estado: r.casos[CASO].estado, oficial: r.oficial, consume_version: r.consume_version }));
        process.exitCode = r.codigo_salida; })
        .catch(e => { console.error(e.message); process.exitCode = 2; });
    } catch (e) { console.error(e.message); process.exitCode = 2; }
  }
}
