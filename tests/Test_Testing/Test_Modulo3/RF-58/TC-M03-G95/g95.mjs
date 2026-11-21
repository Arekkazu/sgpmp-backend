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
import { CASO, ORACULO, IDS, CAPACIDADES, DECISION_METODOLOGICA, LIMITE_LECTURAS_DASHBOARD, clasificarApi, evaluarResultadoCypress, decidir } from './lib/g95_escenario.mjs';

const require = createRequire(import.meta.url);
const DIR = path.dirname(fileURLToPath(import.meta.url));
const RAIZ = path.resolve(DIR, '../../../../..');
const API = 'https://www.api.inmero.co/api-sgpmp-test';
const API_UI = 'https://api.inmero.co/api-sgpmp-test';
const FRONT = 'https://api.inmero.co/sigab-test';
const SPEC = path.join(DIR, 'g95.cy.js');
const CONFIG = path.join(DIR, 'g95.cypress.config.cjs');
const COLECCION = path.join(DIR, 'G95.postman_collection.json');
const escribir = (p, x) => fs.writeFileSync(p, JSON.stringify(x, null, 2));
const exigir = (x, m) => { if (!x) throw Error(m); };
const limpiar = (x, secretos = []) => sanearArtefacto(typeof x === 'string' ? x : JSON.stringify(x), secretos);

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
  if (String(env.SIGAB_API_TEST_BASE ?? '').replace(/\/+$/, '') !== API) barreras.push('API_TEST_NO_CANONICA');
  if (String(env.SIGAB_FRONT_TEST_URL ?? '').replace(/\/+$/, '') !== FRONT) barreras.push('FRONT_TEST_NO_CANONICO');
  if (c.version > 1 && c.operacion !== 'reevaluar') barreras.push('REEVALUACION_SIN_DECISION');
  return { fase: 'PREFLIGHT_LOCAL', grupo: 'G95', run_id: c.runId, version: c.version,
    variables: claves.map(nombre => ({ nombre, presente: !!env[nombre] })), barreras,
    efectos_declarados: ['login_y_auditoria_fuera_run', 'lecturas_dashboard_y_posible_correo_E7'],
    plan: ['login Administrador fuera del RUN',
      'Cypress Productor fuera del RUN: login, segundo login, UI', 'Newman Productor fuera del RUN: token y cookie anteriores',
      'GET /usuarios/me Administrador dentro del RUN con eco', 'DELETE RUN y verificar HTTP'],
    ok: barreras.length === 0 };
}

export function resolverCli(nombre) {
  let pkg;
  try { pkg = require.resolve(`${nombre}/package.json`, { paths: [RAIZ] }); }
  catch {
    const carpeta = String(process.env.PATH ?? '').split(path.delimiter)
      .find(p => fs.existsSync(path.join(p, 'node_modules', nombre, 'package.json')));
    exigir(carpeta, `HERRAMIENTA_${nombre.toUpperCase()}_NO_RESUELTA`);
    pkg = path.join(carpeta, 'node_modules', nombre, 'package.json');
  }
  return path.join(path.dirname(pkg), 'bin', nombre === 'newman' ? 'newman.js' : 'cypress');
}

export function prevalidarHerramientas(spawn = spawnSync) {
  const diagnostico = {};
  for (const nombre of ['newman', 'cypress']) {
    try {
      const p = spawn(process.execPath, [resolverCli(nombre), '--version'],
        { encoding: 'utf8', shell: false, timeout: 30000 });
      diagnostico[nombre] = { status: p.status, error: p.error?.code ?? null,
        version: String(p.stdout ?? '').match(/\b\d+\.\d+\.\d+\b/)?.[0] ?? null };
    } catch (e) { diagnostico[nombre] = { status: null, error: e.code ?? 'NO_RESUELTO' }; }
  }
  return { diagnostico, ok: Object.values(diagnostico).every(x => x.status === 0 && !x.error) };
}

export function comprobar() {
  const anterior = globalThis.fetch;
  globalThis.fetch = () => { throw Error('RED_PROHIBIDA_EN_COMPROBAR'); };
  try {
    const archivos = ['README.md', 'g95.mjs', 'g95.cy.js', 'g95.cypress.config.cjs',
      'G95.postman_collection.json', 'lib/contrato_ejecutor.mjs', 'lib/seguridad.mjs',
      'lib/g95_escenario.mjs', 'lib/g95_unidad.cjs', 'lib/g95_presupuesto.cjs',
      'pruebas/g95.test.mjs', 'pruebas/g95_ensayo_spec_real.mjs'];
    const faltantes = archivos.filter(x => !fs.existsSync(path.join(DIR, x)));
    const presentes = ['README.md', 'g95.mjs', 'g95.cy.js', 'g95.cypress.config.cjs',
      'G95.postman_collection.json', ...['lib', 'pruebas'].flatMap(carpeta =>
        fs.existsSync(path.join(DIR, carpeta))
          ? fs.readdirSync(path.join(DIR, carpeta)).map(nombre => `${carpeta}/${nombre}`) : [])];
    const inesperados = [...fs.readdirSync(DIR).filter(x => !['lib', 'pruebas', 'Resultados'].includes(x)),
      ...presentes.filter(x => x.includes('/'))].filter(x => !archivos.includes(x));
    const col = JSON.parse(fs.readFileSync(COLECCION, 'utf8'));
    for (const ev of [...(col.event ?? []), ...col.item.flatMap(item => item.event ?? [])])
      new vm.Script((ev.script?.exec ?? []).join('\n'));
    const spec = fs.readFileSync(SPEC, 'utf8');
    const archivosRaiz = fs.readdirSync(DIR);
    const canonicos = archivosRaiz.filter(x => /\.postman_collection\.json$|\.cy\.js$|\.cypress\.config\.cjs$|^g95\.mjs$/.test(x));
    const ok = !faltantes.length && !inesperados.length && col.item.length === 2 && CAPACIDADES.contrato === 'sigab-qa-ejecutor/1'
      && canonicos.length === 4 && !archivosRaiz.some(x => /^ejecutar_tc_|^validar_local_|^informe\.md$|^informes$/.test(x))
      && IDS.every(id => JSON.stringify(col).includes(id) || spec.includes(id))
      && spec.includes('req.continue') && !/req\.reply\s*\(/.test(spec)
      && !/describe\.skip|it\.skip/.test(spec)
      && (!fs.existsSync(path.join(DIR, 'Resultados'))
        || !fs.readdirSync(path.join(DIR, 'Resultados')).some(x => x.endsWith('.md')));
    console.log(JSON.stringify({ grupo: 'G95', ok, faltantes, inesperados, contrato: CAPACIDADES.contrato }));
    return ok ? 0 : 2;
  } finally { globalThis.fetch = anterior; }
}

export function informe(r) {
  const estado = r.casos[CASO].estado;
  const filas = r.comprobaciones.map(x => `| ${x.id} | ${x.fuente} | ${x.estado} | ${x.motivo} | ${x.evidencia ?? 'Sin evidencia'} |`).join('\n');
  const pendientes = r.comprobaciones.filter(x => !['APROBADO', 'RECHAZADO'].includes(x.estado)).map(x => x.id);
  const discrepancias = r.comprobaciones.filter(x => x.estado === 'RECHAZADO');
  const inc = discrepancias.length ? discrepancias.map(x => {
    const datosVencidos = x.fuente === 'API' && r.newman?.some(n => n.id === 'API-186-01-DASHBOARD' && n.http === 200);
    const severidad = datosVencidos ? 'CRÍTICA' : 'ALTA';
    const motivoSeveridad = datosVencidos ? 'el token anterior permite datos tras el cierre'
      : 'el fallo impide la experiencia de expiración exigida';
    return `- ${x.id}: primer contacto **Desarrollo** por discrepancia pública de ${x.fuente} comprobada en TEST. Severidad ${severidad}: ${motivoSeveridad}; certeza CONFIRMADA para lo observado, causa raíz NO DETERMINADA. Evidencia: ${x.evidencia}. Responsable QA: decidir ticket.`;
  }).join('\n')
    : 'Sin discrepancias funcionales acreditadas en TEST.';
  return `# TC-M03-G95 — ${estado}\n\n## Decisión del caso\n\n` +
    `Caso agrupado G95; original ${CASO}. **Decisión:** **${estado}**. Motivo: ${r.casos[CASO].motivo}. ` +
    `¿RUN oficial? ${r.oficial ? 'Sí' : 'No'}. Falta: ${pendientes.join(', ') || 'ninguna comprobación'}.\n\n` +
    `| ID | Fuente | Estado | Observado | Evidencia |\n|---|---|---|---|---|\n${filas}\n\n` +
    `## Decisiones metodológicas\n\nMecanismo, decisión del responsable QA (${DECISION_METODOLOGICA.fecha}): «${DECISION_METODOLOGICA.texto}» Segundo login real: el JWT anterior recibe 401 y el refresh previo 401/410; \`src/shared/jwt.py:100-131\` explica la respuesta al vencimiento. Frontend de referencia origin/test 81058af5: \`src/shared/api/http.ts:203-243\` intenta refresh y, ante rechazo 401/410, guarda motivo y ruta antes de redirigir; \`src/shared/auth/AuthContext.tsx:162-189,224-234\` gestiona la restauración; \`src/auth/pages/LoginPage.tsx:29-45,74-80\` y \`src/shared/i18n/locales/es-CO/auth.json:52-63\` muestran el aviso. ${DECISION_METODOLOGICA.limite}\n\n` +
    `Mensaje, decisión del responsable QA (${DECISION_METODOLOGICA.fecha_mensaje}): «${DECISION_METODOLOGICA.texto_mensaje}» ${DECISION_METODOLOGICA.mensaje} Aviso visible exacto observado en /login: ${JSON.stringify(r.observado?.ui?.aviso_texto ?? null)}. Sin aviso visible, UI-186-01 no cumple.\n\n` +
    `Recarga, decisión del responsable QA (${DECISION_METODOLOGICA.fecha_recarga}): «${DECISION_METODOLOGICA.texto_recarga}» Fuente: \`${DECISION_METODOLOGICA.fuente_recarga}\`. RF-58 E5: «Al reingresar, el dashboard se recarga con el estado más reciente»; postcondición 1: «El dashboard refleja el estado más reciente de todas las variables activas del usuario».\n\n` +
    `## Identificación\n\nG95; ${CASO}; RF-58/CU04 E5; V${r.version}; RUN ${r.run_id}; TEST; autorización ${r.autorizacion}; frontend de referencia ${r.frontend_referencia ?? 'NO VERIFICADO'}; commit backend NO VERIFICADO; Node ${process.version}; herramientas ${JSON.stringify(r.preflight_herramientas)}.\n\n` +
    `## Resumen de veredictos\n\n${CASO}: ${estado}. Estado técnico ${r.casos[CASO].estado_tecnico}; consume versión ${r.consume_version}.\n\n` +
    `## Esperado y observado\n\nEsperado literal de la matriz: ${ORACULO}\n\n` +
    `Observado: ${limpiar(r.observado)}. Aviso visible exacto en /login: ${JSON.stringify(r.observado?.ui?.aviso_texto ?? null)}.\n\n` +
    `## Observaciones\n\n${r.comprobaciones.find(x => x.id === 'UI-186-02')?.observaciones?.map(x => `- ${x}`).join('\n') || 'Sin observaciones UX acreditadas.'}\n\n` +
    `## Comprobaciones API/UI\n\n${filas}\n\n` +
    `## Evidencias reales\n\n${r.evidencias.map(x => `- ${x}`).join('\n') || 'Sin artefactos de herramientas.'}\n\n` +
    `## Incidencias de producto\n\n${inc}\n\n` +
    `## Incidencias técnicas QA\n\n${r.problemas_tecnicos.map(x => `- ${x}`).join('\n') || 'Ninguna acreditada.'}\n\n` +
    `## Análisis de causas\n\nLa primera discrepancia pública orienta la atención inicial; la causa raíz no se atribuye por inferencia del código local.\n\n` +
    `## Efectos fuera del RUN\n\nLogins del Productor y Administrador, reemplazo y rotación de sesión, último acceso, auditoría, notificaciones y lecturas del dashboard pueden persistir. La primera carga global puede activar correo E7; DELETE no revierte estos efectos. Riesgo E7 de la unidad filtrada: ${r.observado?.ui?.e7_riesgo ?? 'NO CONSTA'}; motivo: ${r.observado?.ui?.e7_motivo ?? 'NO CONSTA'}. Lecturas del dashboard: ${r.observado?.ui?.lecturas_dashboard ?? 'NO CONSTA'} (límite autorizado ${LIMITE_LECTURAS_DASHBOARD}, según SOL-G95-013). Productor: cero peticiones dentro del sandbox.\n\n` +
    `## Cierre y rollback\n\nDELETE HTTP ${r.cierre.run.cierre_http ?? 'NO CONSTA'}. Rollback ${r.cierre.rollback.estado}: ${r.cierre.rollback.motivo}. ${r.cierre.motivo}. No se declaran revertidos los efectos externos.\n\n` +
    `Peticiones directas (sin credenciales): ${JSON.stringify(r.bitacora ?? [])}.\n\n` +
    `## Conclusión y acción concreta\n\n${estado}. Responsable QA: revisar la evidencia pública y derivar las discrepancias confirmadas.\n`;
}

function registrar(r, id, estado, motivo, evidencia = null, observaciones = []) {
  const fuente = id.startsWith('UI') ? 'UI' : 'API';
  r.comprobaciones.push({ caso: CASO, fuente, id, herramienta: fuente === 'UI' ? 'Cypress' : 'Newman',
    tipo: 'ASSERT', estado, motivo, evidencia, observaciones });
}

export function finalizar(c, r) {
  for (const id of IDS) if (!r.comprobaciones.some(x => x.id === id)) registrar(r, id, 'NO_EJECUTADA', 'Sin ejecución acreditada');
  const informeNombre = c.version === 1 ? 'TC-M03-G95_resultado.md' : `TC-M03-G95_reevaluacion_V${c.version}.md`;
  r.evidencias = [...new Set([...r.evidencias, 'resultado.json', informeNombre])];
  const evidenciasValidas = r.evidencias.every(x => typeof x === 'string' && !path.isAbsolute(x)
    && !x.includes('..') && path.resolve(c.directorio, x).startsWith(path.resolve(c.directorio) + path.sep)
    && (x === 'resultado.json' || x === informeNombre || fs.existsSync(path.join(c.directorio, x))));
  const captura = r.evidencias.some(x => /\.png$/i.test(x));
  r.casos[CASO].estado = decidir(r.comprobaciones, { uiPruebas: r.cypress.total_pruebas,
    captura, cierreHttp: r.cierre.run.cierre_http });
  r.casos[CASO].estado_tecnico = r.comprobaciones.some(x => x.estado === 'ERROR_QA') ? 'ERROR_QA'
    : r.problemas_tecnicos.length ? 'NO_CONCLUYENTE' : 'OK';
  const pendiente = r.comprobaciones.find(x => !['APROBADO', 'RECHAZADO'].includes(x.estado));
  r.casos[CASO].motivo = r.casos[CASO].estado === 'RECHAZADO' ? 'Discrepancia pública acreditada'
    : r.casos[CASO].estado === 'APROBADO' ? 'Oráculo completo y equivalencia aprobada'
      : r.problemas_tecnicos[0] ?? (pendiente ? `${pendiente.id}: ${pendiente.motivo}; no se pudo comprobar el oráculo completo`
        : r.cierre.run.cierre_http !== 200 ? `DELETE RUN HTTP ${r.cierre.run.cierre_http ?? 'sin respuesta'}; cierre no acreditado`
          : 'Falta evidencia UI o captura real');
  r.oficial = r.comprobaciones.every(x => ['APROBADO', 'RECHAZADO'].includes(x.estado))
    && r.cypress.total_pruebas === 1 && captura && r.cierre.run.cierre_http === 200
    && r.cierre.rollback.verificado && evidenciasValidas && r.problemas_tecnicos.length === 0;
  r.codigo_salida = r.problemas_tecnicos.length || r.cierre.run.cierre_http !== 200 ? 2 : 0;
  fs.writeFileSync(path.join(c.directorio, informeNombre), informe(r));
  escribir(path.join(c.directorio, 'resultado.json'), r);
  return r;
}

async function pedir(base, metodo, ruta, { token, headers = {}, cuerpo, bitacora, en_run = false } = {}) {
  const h = { Accept: 'application/json', ...headers };
  if (token) h.Authorization = `Bearer ${token}`;
  if (cuerpo) h['Content-Type'] = 'application/json';
  let http = null; let eco = null;
  try {
    const resp = await fetch(base + ruta, { method: metodo, headers: h,
      body: cuerpo ? JSON.stringify(cuerpo) : undefined, redirect: 'manual', signal: AbortSignal.timeout(30000) });
    http = resp.status; eco = resp.headers.get('X-Test-Run-Id');
    return { http, cuerpo: await resp.json().catch(() => null), eco };
  } finally { bitacora?.push({ metodo, ruta, http, en_run,
    eco: en_run ? eco === headers['X-Test-Run-Id'] : null }); }
}

export function ejecutarCypress(c, { env, handoff, secretos, spawn = spawnSync }) {
  const dir = path.join(c.directorio, 'cypress'); fs.mkdirSync(dir, { recursive: true });
  const vars = { CYPRESS_AUTORIZADO_RUN: 'SI', CYPRESS_API_BASE: API_UI,
    CYPRESS_API_BASE_CONTROL: API, CYPRESS_FRONT_BASE: FRONT, CYPRESS_RUN_ID: c.runId,
    CYPRESS_ARTIFACTS_DIR: dir, CYPRESS_HANDOFF: handoff,
    CYPRESS_PROD_EMAIL: env.QA_PROD_EMAIL, CYPRESS_PROD_PASSWORD: env.QA_PROD_PASSWORD };
  const entornoHijo = { ...process.env, ...vars };
  delete entornoHijo.ELECTRON_RUN_AS_NODE;
  const p = spawn(process.execPath, [resolverCli('cypress'), 'run', '--project', DIR,
    '--spec', SPEC, '--config-file', CONFIG, '--config', `screenshotsFolder=${dir},videosFolder=${dir},downloadsFolder=${dir}`,
    '--browser', 'chrome', '--headless'], { cwd: DIR, env: entornoHijo,
    encoding: 'utf8', shell: false, timeout: 300000, maxBuffer: 8 * 1024 * 1024 });
  fs.writeFileSync(path.join(dir, 'UI-186-01.log'), limpiar(`STDOUT\n${p.stdout ?? ''}\nSTDERR\n${p.stderr ?? ''}`, secretos));
  const leer = n => fs.existsSync(path.join(dir, n)) ? JSON.parse(fs.readFileSync(path.join(dir, n), 'utf8')) : null;
  const capturas = fs.readdirSync(dir, { recursive: true }).filter(x => /\.png$/i.test(String(x)))
    .map(x => `cypress/${String(x).replaceAll('\\', '/')}`);
  return { acta: leer('UI-186-01.json'), resumen: leer('UI-186-01-cypress.json'),
    capturas, error: p.error?.code ?? null, proceso: p.status };
}

export function ejecutarNewman(c, { token, cookie, secretos, spawn = spawnSync }) {
  const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'g95-newman-'));
  try {
    const out = path.join(c.directorio, 'newman'); fs.mkdirSync(out, { recursive: true });
    const envPath = path.join(temp, 'env.json');
    escribir(envPath, { values: Object.entries({ qa_autorizado: 'SI', base_url: API,
      token_anterior: token, cookie_anterior: cookie }).map(([key, value]) => ({ key, value, enabled: true })) });
    const jsonPath = path.join(temp, 'reporte.json');
    const p = spawn(process.execPath, [resolverCli('newman'), 'run', COLECCION, '-e', envPath,
      '--reporters', 'json', '--reporter-json-export', jsonPath,
      '--timeout-request', '30000', '--color', 'off'],
    { cwd: DIR, shell: false, encoding: 'utf8', timeout: 90000, maxBuffer: 8 * 1024 * 1024 });
    exigir(fs.existsSync(jsonPath), `NEWMAN_SIN_REPORTE_${p.error?.code ?? p.status}`);
    const report = JSON.parse(fs.readFileSync(jsonPath, 'utf8'));
    fs.writeFileSync(path.join(out, 'newman-G95.json'), limpiar(report, secretos));
    const respuestas = (report.run?.executions ?? []).map(ex => ({
      id: ex.item?.name?.match(/API-186-01-(DASHBOARD|REFRESH)/)?.[0] ?? null,
      http: ex.response?.code ?? null,
      code: (() => { try { return JSON.parse(Buffer.from(ex.response?.stream?.data ?? []).toString()).error_code ?? null; } catch { return null; } })(),
    }));
    const filas = respuestas.map(x => `<tr><td>${x.id ?? 'SIN_ID'}</td><td>${x.http ?? 'SIN_RESPUESTA'}</td></tr>`).join('');
    fs.writeFileSync(path.join(out, 'newman-G95.html'),
      `<!doctype html><html lang="es"><meta charset="utf-8"><title>Newman G95</title><h1>Newman G95</h1><table><tr><th>ID</th><th>HTTP</th></tr>${filas}</table></html>`);
    return { respuestas, proceso: p.status, fallos: report.run?.failures?.length ?? 0,
      artefactos: ['newman/newman-G95.json', 'newman/newman-G95.html'] };
  } finally {
    exigir(path.resolve(temp).startsWith(path.resolve(os.tmpdir()) + path.sep), 'TEMP_FUERA_RAIZ');
    fs.rmSync(temp, { recursive: true, force: true });
  }
}

export async function evaluar(c, { env = leerEnv(), fetcher = null } = {}) {
  exigir(fs.existsSync(c.directorio), 'RUN_NO_CREADO_POR_LANZADOR');
  const r = { grupo: 'G95', run_id: c.runId, version: c.version, operacion: c.operacion,
    frontend_referencia: 'SGPMP-FRONT-END-PWA origin/test 81058af57d5d80d523fb5225f8eab48e0307ba85',
    autorizacion: c.referencia, oficial: false, consume_version: false,
    equivalencia_aprobada: true, decision_metodologica: DECISION_METODOLOGICA,
    casos: { [CASO]: { estado: 'BLOQUEADO', estado_tecnico: 'NO_CONCLUYENTE', motivo: 'Sin evaluación' } },
    comprobaciones: [], evidencias: [], bitacora: [], observado: {}, problemas_tecnicos: [],
    cypress: { total_pruebas: 0 }, newman: [], cierre: { run: { cierre_http: null },
      rollback: { verificado: false, estado: 'NO_VERIFICADO', motivo: 'RUN no cerrado', comprobaciones: [] },
      motivo: 'RUN no abierto' },
    preflight_herramientas: {}, inicio: new Date().toISOString() };
  const secretos = [env.QA_SANDBOX_SECRET, env.QA_ADMIN_PASSWORD, env.QA_PROD_PASSWORD].filter(Boolean);
  const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'g95-handoff-'));
  const handoff = path.join(temp, 'auth.json');
  let aperturaIntentada = false;
  try {
    const pre = preflight(c, env); escribir(path.join(c.directorio, 'preflight.json'), pre);
    r.evidencias.push('preflight.json'); exigir(pre.ok, `PREFLIGHT:${pre.barreras.join(',')}`);
    const herramientas = prevalidarHerramientas(); r.preflight_herramientas = herramientas.diagnostico;
    exigir(herramientas.ok, 'HERRAMIENTAS_NO_DISPONIBLES');
    const login = await pedir(API, 'POST', '/sesiones/', { bitacora: r.bitacora, cuerpo: {
      correo_electronico: env.QA_ADMIN_EMAIL, contrasena: env.QA_ADMIN_PASSWORD } });
    exigir(login.http === 200 && login.cuerpo?.token, `ADMIN_LOGIN_HTTP_${login.http}`);
    try {
    const ui = ejecutarCypress(c, { env, handoff, secretos });
    r.cypress = { total_pruebas: ui.resumen?.totalTests ?? 0, resumen: ui.resumen,
      capturas: ui.capturas, acta: ui.acta ? 'cypress/UI-186-01.json' : null };
    r.observado.ui = ui.acta ?? {};
    r.evidencias.push('cypress/UI-186-01.log', ...ui.capturas);
    if (ui.acta) r.evidencias.push('cypress/UI-186-01.json');
    if (ui.resumen) r.evidencias.push('cypress/UI-186-01-cypress.json');
    const evUi = evaluarResultadoCypress(ui);
    for (const id of ['UI-186-01', 'UI-186-02']) registrar(r, id, evUi[id].estado, evUi[id].motivo,
      ui.acta ? 'cypress/UI-186-01.json' : null, evUi[id].observaciones ?? []);
    for (const id of ['UI-186-01', 'UI-186-02']) if (evUi[id].estado === 'ERROR_QA') r.problemas_tecnicos.push(evUi[id].motivo);
    } catch (e) { r.problemas_tecnicos.push(`CYPRESS:${limpiar(e.message, secretos)}`); }
    try {
    if (fs.existsSync(handoff)) {
      const { token, cookie } = JSON.parse(fs.readFileSync(handoff, 'utf8'));
      exigir(token && cookie, 'HANDOFF_INCOMPLETO');
      const n = ejecutarNewman(c, { token, cookie, secretos: [...secretos, token, cookie] });
      r.newman = n.respuestas; r.evidencias.push(...n.artefactos);
      const api = clasificarApi(n.respuestas);
      registrar(r, 'API-186-01', api.estado, api.motivo, n.artefactos[0]);
      if (n.proceso !== 0 && api.estado === 'APROBADO') r.problemas_tecnicos.push('NEWMAN_SALIDA_INCOHERENTE');
    } else registrar(r, 'API-186-01', 'NO_EJECUTADA', 'Cypress no entregó token/cookie anteriores');
    } catch (e) { r.problemas_tecnicos.push(`NEWMAN:${limpiar(e.message, secretos)}`); }
    aperturaIntentada = true; r.consume_version = true;
    const admin = await pedir(API, 'GET', '/usuarios/me', { token: login.cuerpo.token,
      headers: { 'X-Test-Run-Id': c.runId, 'X-Sandbox-Secret': env.QA_SANDBOX_SECRET },
      bitacora: r.bitacora, en_run: true });
    r.observado.admin = { http: admin.http, eco: admin.eco === c.runId };
    exigir(admin.http === 200 && admin.eco === c.runId, `ADMIN_RUN_HTTP_${admin.http}_ECO_${!!admin.eco}`);
  } catch (e) { r.problemas_tecnicos.push(limpiar(e.message, secretos)); }
  finally {
    if (aperturaIntentada) {
      try {
        const cierre = await pedir(API, 'DELETE', `/test-control/runs/${c.runId}`,
          { headers: { 'X-Sandbox-Secret': env.QA_SANDBOX_SECRET }, bitacora: r.bitacora });
        r.cierre.run.cierre_http = cierre.http;
        const dentro = r.bitacora.filter(x => x.en_run);
        const soloLectura = dentro.length === 1 && dentro[0].metodo === 'GET'
          && dentro[0].ruta === '/usuarios/me' && dentro[0].http === 200 && dentro[0].eco === true;
        r.cierre.rollback.verificado = cierre.http === 200 && soloLectura;
        r.cierre.rollback.estado = r.cierre.rollback.verificado ? 'CONFIRMADO' : 'NO_VERIFICADO';
        r.cierre.rollback.motivo = r.cierre.rollback.verificado
          ? 'Sin escrituras de escenario dentro del RUN; DELETE 200'
          : 'DELETE 200 y lectura única GET /usuarios/me con eco no acreditados conjuntamente';
        r.cierre.rollback.comprobaciones.push({ fuente: 'bitacora', solo_lectura_en_run: soloLectura,
          peticiones_en_run: dentro.length, cierre_http: cierre.http });
        r.cierre.motivo = r.cierre.rollback.motivo;
      } catch (e) { r.cierre.motivo = `Cierre no acreditado: ${limpiar(e.message, secretos)}`;
        r.cierre.rollback.motivo = r.cierre.motivo;
        r.problemas_tecnicos.push(`CIERRE:${limpiar(e.message, secretos)}`); }
    } else r.cierre.motivo = 'RUN_NO_ABIERTO';
    exigir(path.resolve(temp).startsWith(path.resolve(os.tmpdir()) + path.sep), 'TEMP_FUERA_RAIZ');
    fs.rmSync(temp, { recursive: true, force: true });
    r.consume_version = r.bitacora.length > 0;
    r.fin = new Date().toISOString();
    finalizar(c, r);
  }
  return r;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  if (process.argv.includes('--capacidades')) console.log(JSON.stringify(CAPACIDADES, null, 2));
  else if (process.argv.includes('--comprobar')) process.exitCode = comprobar();
  else {
    try {
      const c = contextoEjecucion(process.argv.slice(2), { grupo: 'G95', casos: [CASO], directorio: DIR });
      evaluar(c).then(r => { console.log(JSON.stringify({ run_id: r.run_id,
        estado: r.casos[CASO].estado, oficial: r.oficial, consume_version: r.consume_version }));
      process.exitCode = r.codigo_salida; }).catch(e => { console.error(e.message); process.exitCode = 2; });
    } catch (e) { console.error(e.message); process.exitCode = 2; }
  }
}
