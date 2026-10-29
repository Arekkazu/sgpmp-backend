#!/usr/bin/env node
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import vm from 'node:vm';
import { spawn, spawnSync } from 'node:child_process';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { contextoEjecucion } from './lib/contrato_ejecutor.mjs';
import { sanearArtefacto } from './lib/seguridad.mjs';
import { PRESUPUESTO, CASO, ORACULO, CATALOGO, CAPACIDADES, canonico, clasificar } from './lib/g96_escenario.mjs';

const require = createRequire(import.meta.url);
const DIR = path.dirname(fileURLToPath(import.meta.url));
const RAIZ = path.resolve(DIR, '../../../../..');
const API = 'https://www.api.inmero.co/api-sgpmp-test';
const COLECCION = path.join(DIR, 'G96.postman_collection.json');
const COMMIT_BACKEND = 'origin/test 5b46ca00a0ba92774f8e3d4b9eeaeec169344f17';
const escribir = (p, o) => fs.writeFileSync(p, JSON.stringify(o, null, 2));

export function leerEnv(proceso = process.env, archivo = path.join(RAIZ, '.env.qa')) {
  const v = {};
  if (archivo && fs.existsSync(archivo)) for (const linea of fs.readFileSync(archivo, 'utf8').split(/\r?\n/)) {
    const m = linea.match(/^\s*([A-Z][A-Z0-9_]*)\s*=(.*)$/);
    if (m) v[m[1]] = m[2].trim().replace(/^(['"])(.*)\1$/, '$2');
  }
  Object.assign(v, proceso);
  v.QA_AUTORIZADO = proceso.QA_AUTORIZADO;
  return v;
}
export function preflight(c, env, ensayo = false) {
  const claves = ['SIGAB_API_TEST_BASE', 'QA_SANDBOX_SECRET', 'QA_PROD_EMAIL', 'QA_PROD_PASSWORD'];
  const barreras = claves.filter(k => !String(env[k] ?? '').trim());
  const base = String(env.SIGAB_API_TEST_BASE ?? '').replace(/\/+$/, '');
  if (env.QA_AUTORIZADO !== 'SI') barreras.push('QA_AUTORIZADO');
  if (ensayo ? !/^http:\/\/(127\.0\.0\.1|localhost):\d+$/.test(base) : base !== API) barreras.push('API_NO_CANONICA');
  if (c.version > 1 && c.operacion !== 'reevaluar') barreras.push('REEVALUACION_SIN_DECISION');
  return { fase: 'PREFLIGHT_LOCAL', grupo: 'G96', run_id: c.runId, version: c.version, barreras,
    variables: claves.map(nombre => ({ nombre, presente: !!env[nombre] })),
    efectos_declarados: ['login_productor_y_auditoria_fuera_run', 'lecturas_dashboard_y_posible_correo_E7'],
    presupuesto: PRESUPUESTO, ok: barreras.length === 0 };
}
export function resolverNewman() {
  let pkg;
  try { pkg = require.resolve('newman/package.json', { paths: [RAIZ] }); }
  catch {
    const carpeta = String(process.env.PATH ?? '').split(path.delimiter)
      .find(p => fs.existsSync(path.join(p, 'node_modules', 'newman', 'package.json')));
    if (!carpeta) throw Error('NEWMAN_NO_RESUELTO');
    pkg = path.join(carpeta, 'node_modules', 'newman', 'package.json');
  }
  return path.join(path.dirname(pkg), 'bin', 'newman.js');
}
export function prevalidarNewman() {
  try {
    const p = spawnSync(process.execPath, [resolverNewman(), '--version'],
      { encoding: 'utf8', shell: false, timeout: 30000 });
    return { ok: p.status === 0 && !p.error, version: String(p.stdout ?? '').trim().match(/\d+\.\d+\.\d+/)?.[0] ?? null,
      error: p.error?.code ?? null };
  } catch (e) { return { ok: false, version: null, error: e.code ?? e.message }; }
}
export function comprobar() {
  const archivos = ['README.md', 'g96.mjs', 'G96.postman_collection.json', 'lib/contrato_ejecutor.mjs',
    'lib/seguridad.mjs', 'lib/g96_escenario.mjs', 'lib/g96_presupuesto.cjs', 'pruebas/g96.test.mjs', 'pruebas/g96_ensayo.mjs'];
  const presentes = fs.readdirSync(DIR).filter(x => !['lib', 'pruebas', 'Resultados'].includes(x))
    .concat(...['lib', 'pruebas'].map(d => fs.readdirSync(path.join(DIR, d)).map(x => `${d}/${x}`)));
  const faltantes = archivos.filter(x => !fs.existsSync(path.join(DIR, x)));
  const inesperados = presentes.filter(x => !archivos.includes(x));
  let sintaxis = false;
  try {
    const col = JSON.parse(fs.readFileSync(COLECCION, 'utf8'));
    for (const e of col.item.flatMap(i => i.event ?? [])) new vm.Script((e.script?.exec ?? []).join('\n'));
    sintaxis = col.item.length === 1 && JSON.stringify(col).includes('API-187-01');
  } catch { /* se informa abajo */ }
  const ok = !faltantes.length && !inesperados.length && sintaxis && CAPACIDADES.contrato === 'sigab-qa-ejecutor/1'
    && !fs.existsSync(path.join(DIR, 'informe.md')) && (!fs.existsSync(path.join(DIR, 'Resultados'))
      || !fs.readdirSync(path.join(DIR, 'Resultados')).some(x => x.endsWith('.md')));
  console.log(JSON.stringify({ grupo: 'G96', ok, faltantes, inesperados, sintaxis, presupuesto: PRESUPUESTO }));
  return ok ? 0 : 2;
}

async function pedir(api, metodo, ruta, { token, secreto, runId, cuerpo, bitacora, timeout = 30000 } = {}) {
  const headers = { Accept: 'application/json' };
  if (token) headers.Authorization = `Bearer ${token}`;
  if (secreto) headers['X-Sandbox-Secret'] = secreto;
  if (runId) headers['X-Test-Run-Id'] = runId;
  if (cuerpo) headers['Content-Type'] = 'application/json';
  let http = null, eco = false;
  try {
    const r = await fetch(api + ruta, { method: metodo, headers, body: cuerpo ? JSON.stringify(cuerpo) : undefined,
      redirect: 'manual', signal: AbortSignal.timeout(timeout) });
    http = r.status; eco = r.headers.get('X-Test-Run-Id') === runId;
    return { http, eco, cuerpo: await r.json().catch(() => null) };
  } finally { bitacora?.push({ metodo, ruta, http, en_run: !!runId, eco: runId ? eco : null }); }
}
function soloIds(items, clave) { return Array.isArray(items) ? items.map(x => Number(x?.[clave])).filter(x => Number.isInteger(x) && x > 0) : []; }
export async function descubrir(api, token, env, c, r) {
  const unidades = [...PRESUPUESTO.unidades_conocidas];
  const h = { token, secreto: env.QA_SANDBOX_SECRET, runId: c.runId, bitacora: r.bitacora };
  const fincas = await pedir(api, 'GET', '/configuracion/fincas?solo_activas=true', h);
  if (fincas.http === 200 && fincas.eco) {
    const ids = soloIds(fincas.cuerpo?.items, 'id_finca').slice(0, PRESUPUESTO.fincas_descubrimiento);
    for (const id of ids) {
      const inf = await pedir(api, 'GET', `/configuracion/infraestructuras?finca_id=${id}&solo_activas=true`, h);
      if (inf.http === 200 && inf.eco) for (const unidad of soloIds(inf.cuerpo?.items, 'id_infraestructura')) {
        if (!unidades.includes(unidad) && unidades.length < PRESUPUESTO.unidades_conocidas.length + PRESUPUESTO.unidades_adicionales) unidades.push(unidad);
      }
      else r.observaciones.push(`Descubrimiento finca ${id}: HTTP ${inf.http ?? 'sin respuesta'}; eco ${inf.eco}`);
    }
  } else r.observaciones.push(`Descubrimiento fincas: HTTP ${fincas.http ?? 'sin respuesta'}; eco ${fincas.eco}`);
  return unidades;
}
function runProceso(comando, argumentos, opciones) {
  return new Promise(resolve => {
    const p = spawn(comando, argumentos, { ...opciones, shell: false, windowsHide: true });
    let salida = '', error = '', agotado = false;
    const reloj = setTimeout(() => { agotado = true; p.kill(); }, PRESUPUESTO.paginas_dashboard * 30000 + 30000);
    p.stdout.on('data', x => { salida += x.toString().slice(0, 10000); });
    p.stderr.on('data', x => { error += x.toString().slice(0, 10000); });
    p.on('error', e => { clearTimeout(reloj); resolve({ status: null, error: e.code ?? e.message, salida, stderr: error }); });
    p.on('close', code => { clearTimeout(reloj); resolve({ status: code, error: agotado ? 'TIMEOUT' : null, salida, stderr: error }); });
  });
}
function leerPagina(ex, runId) {
  const url = ex.request?.url;
  const u = String(url?.raw ?? url ?? '');
  const m = u.match(/\/dashboard\/(\d+)\?pagina=(\d+)/);
  const partes = Array.isArray(url?.path) ? url.path.map(String) : [];
  const id = m ? Number(m[1]) : Number(partes.at(-1));
  const q = Array.isArray(url?.query) ? url.query.find(x => x.key === 'pagina')?.value : null;
  const numPagina = m ? Number(m[2]) : Number(q);
  const headers = ex.response?.header ?? ex.response?.headers ?? [];
  const eco = headers.some(h => String(h.key ?? '').toLowerCase() === 'x-test-run-id' && h.value === runId);
  let body = null;
  try { body = JSON.parse(Buffer.from(ex.response?.stream?.data ?? []).toString('utf8')); } catch { /* sin JSON */ }
  return { unidad: Number.isInteger(id) && id > 0 ? id : null,
    pagina: Number.isInteger(numPagina) && numPagina > 0 ? numPagina : null,
    http: ex.response?.code ?? null, eco, total: body?.total ?? null,
    sensores: Array.isArray(body?.sensores) ? body.sensores.map(s => ({
      ...(Object.hasOwn(s, 'estado_conectividad') ? { estado_conectividad: s.estado_conectividad } : {}),
    })) : null };
}
export async function ejecutarNewman(c, { api, token, env, unidades, secretos, ensayo = false }) {
  const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'g96-newman-'));
  try {
    const salida = path.join(c.directorio, 'newman'); fs.mkdirSync(salida, { recursive: true });
    const variables = { autorizado_run: 'SI', base_url: api, run_id: c.runId, sandbox_secret: env.QA_SANDBOX_SECRET,
      token, unidades: JSON.stringify(unidades), unidad: String(unidades[0]), indice: '0', pagina: '1',
      por_pagina: String(PRESUPUESTO.por_pagina),
      paginas_usadas: '0', limite_paginas: String(PRESUPUESTO.paginas_dashboard), vistos: '[]',
      ensayo_loopback: ensayo ? 'SI' : 'NO' };
    const envPath = path.join(temp, 'env.json');
    escribir(envPath, { values: Object.entries(variables).map(([key, value]) => ({ key, value, enabled: true })) });
    const reporte = path.join(temp, 'reporte.json');
    const p = await runProceso(process.execPath, [resolverNewman(), 'run', COLECCION, '-e', envPath,
      '--reporters', 'json', '--reporter-json-export', reporte, '--timeout-request', '30000', '--color', 'off'],
    { cwd: DIR, env: process.env, stdio: ['ignore', 'pipe', 'pipe'] });
    if (!fs.existsSync(reporte)) return { proceso: p, paginas: [], fallos: [], artefactos: [], error: 'SIN_REPORTE' };
    const raw = fs.readFileSync(reporte, 'utf8');
    fs.writeFileSync(path.join(salida, 'newman-G96.json'), sanearArtefacto(raw, secretos));
    const report = JSON.parse(raw);
    const paginas = (report.run?.executions ?? []).map(x => leerPagina(x, c.runId));
    const fallos = fallosNewman(report);
    const filas = paginas.map(x => `<tr><td>${x.unidad ?? '?'}</td><td>${x.pagina ?? '?'}</td><td>${x.http ?? 'sin respuesta'}</td><td>${x.eco ? 'sí' : 'no'}</td></tr>`).join('');
    fs.writeFileSync(path.join(salida, 'newman-G96.html'),
      `<!doctype html><html lang="es"><meta charset="utf-8"><title>Newman G96</title><h1>Newman G96</h1><table><tr><th>Unidad</th><th>Página</th><th>HTTP</th><th>Eco</th></tr>${filas}</table></html>`);
    return { proceso: p, paginas, fallos, artefactos: ['newman/newman-G96.json', 'newman/newman-G96.html'] };
  } finally {
    if (!path.resolve(temp).startsWith(path.resolve(os.tmpdir()) + path.sep)) throw Error('TEMP_FUERA_RAIZ');
    fs.rmSync(temp, { recursive: true, force: true });
  }
}
export function fallosNewman(reporte) {
  return (reporte.run?.failures ?? []).map(f => ({
    tipo: String(f?.error?.name ?? '').slice(0, 120),
    test: String(f?.error?.test ?? '').slice(0, 200),
    item: String(f?.source?.name ?? '').slice(0, 120),
    mensaje: String(f?.error?.message ?? '').slice(0, 200),
    at: String(f?.at ?? '').slice(0, 120),
  }));
}
export function evaluarNewman(n) {
  const paginas = n.paginas ?? [];
  const ultimo = paginas.at(-1);
  const transporte = (n.fallos ?? []).some(f => /ECONN|socket|timeout|network|request failed/i.test(`${f.tipo} ${f.mensaje}`));
  let datos = clasificar({ paginas, paginasCompletas: paginasCompletas(paginas),
    agotado: paginas.length >= PRESUPUESTO.paginas_dashboard
      && !resumenValores(paginas).some(x => !canonico(x.valor)),
    error: n.error ?? (transporte || ultimo?.http == null ? 'SIN_RESPUESTA' : null) });
  // La colección vigente tiene una aserción funcional: [TC-M03-187][ASSERT][API-187-01].
  // HTTP 5xx, respuesta ausente, eco y formato ya tienen veredicto en clasificar().
  const falloEnum = (n.fallos ?? []).some(f => f.tipo === 'AssertionError'
    && f.test.startsWith('[TC-M03-187][ASSERT][API-187-01]'));
  if (falloEnum && datos.estado === 'APROBADO'
    && paginas.some(p => p.http === 200 && p.eco && Array.isArray(p.sensores)))
    datos = { estado: 'RECHAZADO', motivo: 'Falló la aserción funcional API-187-01 en respuesta 200 con eco' };
  const problemasTecnicos = [];
  if (paginas.length > PRESUPUESTO.paginas_dashboard) problemasTecnicos.push('PRESUPUESTO_PAGINAS_SUPERADO');
  if ((n.fallos ?? []).some(f => /^(TypeError|ReferenceError|SyntaxError)$/.test(f.tipo)
    || (f.tipo === 'AssertionError' && /\[(?:PRE|INFO)\]/.test(f.test)
      && !/\b(?:HTTP|eco)\b/i.test(f.test))))
    problemasTecnicos.push('NEWMAN_ERROR_SCRIPT_O_TRANSPORTE');
  if (n.proceso?.error) problemasTecnicos.push(`NEWMAN_${n.proceso.error}`);
  if (!paginas.length && !n.error && !transporte) problemasTecnicos.push('NEWMAN_SIN_EJECUCIONES');
  return { datos, problemasTecnicos };
}
function resumenValores(paginas) {
  const filas = new Map();
  for (const p of paginas.filter(x => x.http === 200 && x.eco && Array.isArray(x.sensores))) {
    const unidad = p.unidad ?? 'SIN_ID';
    if (!filas.has(unidad)) filas.set(unidad, new Map());
    for (const s of p.sensores) {
      const valor = Object.hasOwn(s, 'estado_conectividad') ? s.estado_conectividad : '[AUSENTE]';
      const k = valor === null ? 'null' : String(valor);
      filas.get(unidad).set(k, (filas.get(unidad).get(k) ?? 0) + 1);
    }
  }
  return [...filas].flatMap(([unidad, valores]) => [...valores].map(([valor, cantidad]) => ({ unidad, valor, cantidad })));
}
function paginasCompletas(paginas) {
  const grupos = new Map();
  for (const p of paginas.filter(x => x.http === 200 && x.eco)) {
    if (!Number.isInteger(p.unidad) || !Number.isInteger(p.pagina)
      || !Number.isInteger(p.total) || p.total < 0) return false;
    if (!grupos.has(p.unidad)) grupos.set(p.unidad, []);
    grupos.get(p.unidad).push(p);
  }
  for (const lote of grupos.values()) {
    const total = lote[0].total;
    if (lote.some(x => x.total !== total) || lote.length !== Math.max(1, Math.ceil(total / PRESUPUESTO.por_pagina))) return false;
    for (let pagina = 1; pagina <= lote.length; pagina++) {
      const p = lote.find(x => x.pagina === pagina);
      if (!p || !Array.isArray(p.sensores)
        || p.sensores.length !== Math.min(PRESUPUESTO.por_pagina, Math.max(0, total - (pagina - 1) * PRESUPUESTO.por_pagina))) return false;
    }
  }
  return true;
}
export function informe(r) {
  const estado = r.casos[CASO].estado;
  const comp = r.comprobaciones[0];
  const filas = r.valores.map(x => `| ${x.unidad} | ${JSON.stringify(x.valor)} | ${x.cantidad} |`).join('\n') || '| — | Sin valores observados | 0 |';
  const fuera = r.valores.filter(x => !canonico(x.valor) && x.valor !== 'null' && x.valor !== '[AUSENTE]');
  const variantes = r.valores.filter(x => canonico(x.valor) && canonico(x.valor) !== x.valor);
  return `# TC-M03-G96 — ${estado}\n\n## Decisión del caso\n\nCaso agrupado TC-M03-G96; caso original ${CASO}. Decisión: **${estado}**. Motivo: ${r.casos[CASO].motivo}.\n\n| Comprobación | Fuente | Estado | Motivo | Evidencia |\n| --- | --- | --- | --- | --- |\n| ${comp.id} | API | ${comp.estado} | ${comp.motivo} | ${comp.evidencia ?? 'Sin evidencia'} |\n\n¿RUN oficial? ${r.oficial ? 'Sí' : 'No'}. Qué falta: ${r.oficial ? 'nada' : r.problemas_tecnicos.join('; ') || r.casos[CASO].motivo}.\n\n## Identificación\n\nGrupo G96; RF-58 / CU04; versión V${r.version}; RUN ${r.run_id}; ambiente ${r.ambiente}; autorización ${r.autorizacion}; referencia backend ${COMMIT_BACKEND}. Newman ${r.preflight_herramientas.newman?.version ?? 'no verificado'}. Sin UI obligatoria.\n\n## Esperado y requisito\n\nMatriz TC-M03-187: «${ORACULO}» RF-58, Especificacion-Requerimientos-Modulo3.md:4923: «Submódulo de Conectividad: encargado de determinar el estado ONLINE / OFFLINE / SIN_SEÑAL y antigüedad del dato.» Línea 5160: «estado_conectividad | Enum | Estado del dispositivo: ONLINE, OFFLINE, SIN_SEÑAL. Proveniente de RF-60.»\n\n## Observado por unidad\n\n| Unidad | Valor exacto | Cantidad |\n| --- | --- | ---: |\n${filas}\n\nPáginas Newman: ${r.paginas.length}; límite ${PRESUPUESTO.paginas_dashboard}; candidatas ${r.unidades.join(', ')}. Valores ausentes y null se contabilizan aparte. Variantes ortográficas reconocidas: ${variantes.map(x => `${x.valor} (${x.cantidad})`).join(', ') || 'ninguna'}.\n\n## Incidencias de producto\n\n${estado === 'RECHAZADO' ? `DEFECTO FUNCIONAL CONFIRMADO en TEST: valor(es) fuera del catálogo ${fuera.map(x => x.valor).join(', ') || 'null/ausente'}. Primer contacto: Desarrollo, porque la discrepancia se observa en la respuesta pública del dashboard; causa raíz NO DETERMINADA. Severidad MEDIA: contrato de datos RF-58 incumplido en parte de los sensores observados; no hay evidencia de daño generalizado.` : 'Ninguna confirmada. La divergencia observada en código local sigue como DEFECTO_FUNCIONAL_CANDIDATO hasta una respuesta pública de TEST.'}\n\n## Incidencias técnicas QA\n\n${r.problemas_tecnicos.join('; ') || 'Ninguna.'}\n\n## Análisis de causas y observaciones documentales\n\nRF-60, línea 6336, define ACTIVO, SIN_SEÑAL, BUFFER_ACTIVO, INACTIVO y EN_MANTENIMIENTO; RF-58 no especifica la correspondencia entre ambos catálogos. Esta observación no cambia el oráculo. Código de referencia ${COMMIT_BACKEND}: monitoreo_repository.py:30 entrega estado_conectividad::text; monitoreo.py:27 documenta estados internos; monitoreo_repository.py:99-101 cuenta ACTIVO e INACTIVO. No atribuye causa raíz del despliegue. ${r.observaciones.join(' ')}\n\n## Evidencias y efectos\n\n${r.evidencias.join(', ')}. Efectos: login del Productor previo al RUN (último acceso, auditoría, notificaciones y posible cierre de sesiones previas); lecturas del dashboard dentro del RUN pueden generar correo RF-58 E7 por sensores GRIS sin umbral no desactualizados. Se priorizan unidades 1, 268 y 337; sin ingesta ni escrituras de escenario.\n\n## Cierre y rollback\n\nDELETE RUN HTTP ${r.cierre.run.cierre_http ?? 'sin respuesta'}. Rollback ${r.cierre.rollback.verificado ? 'verificado' : 'NO verificado'}: ${r.cierre.rollback.motivo}. Los efectos externos no se declaran revertidos.\n\n## Conclusión y acción\n\n${estado}: ${r.casos[CASO].motivo}. ${estado === 'RECHAZADO' ? 'Derivar a Desarrollo con los valores exactos y respuestas saneadas.' : estado === 'APROBADO' ? 'Registrar el contrato observado y conservar evidencias.' : 'Resolver el impedimento documentado y reintentar con autorización particular.'}\n`;
}
function finalizar(c, r, secretos) {
  const estado = r.comprobaciones[0].estado;
  r.casos[CASO] = { estado, motivo: r.comprobaciones[0].motivo };
  const nombre = c.version === 1 ? 'TC-M03-G96_resultado.md' : `TC-M03-G96_reevaluacion_V${c.version}.md`;
  r.evidencias = [...new Set([...r.evidencias, 'resultado.json', nombre])];
  const evidenciasOk = r.evidencias.every(x => typeof x === 'string' && !x.includes('..') && !path.isAbsolute(x)
    && (x === nombre || x === 'resultado.json' || fs.existsSync(path.join(c.directorio, x))));
  r.oficial = esOficial(estado, r, evidenciasOk);
  r.fin = new Date().toISOString();
  escribir(path.join(c.directorio, 'resultado.json'), r);
  fs.writeFileSync(path.join(c.directorio, nombre), sanearArtefacto(informe(r), secretos));
}
export function esOficial(estado, r, evidenciasOk) {
  return ['APROBADO', 'RECHAZADO'].includes(estado) && r.cierre.run.cierre_http === 200
    && r.cierre.rollback.verificado && evidenciasOk && r.problemas_tecnicos.length === 0;
}
export async function evaluar(c, { env = leerEnv(), ensayo = false } = {}) {
  if (!fs.existsSync(c.directorio)) throw Error('RUN_NO_CREADO_POR_LANZADOR');
  const api = String(env.SIGAB_API_TEST_BASE ?? '').replace(/\/+$/, '');
  const r = { grupo: 'G96', run_id: c.runId, version: c.version, operacion: c.operacion,
    autorizacion: c.referencia, ambiente: ensayo ? 'LOOPBACK_LOCAL' : 'TEST', oficial: false,
    consume_version: false, casos: { [CASO]: { estado: 'NO_CONCLUYENTE', motivo: 'Sin ejecución' } },
    comprobaciones: [{ caso: CASO, fuente: 'API', id: 'API-187-01', tipo: 'ASSERT', estado: 'NO_CONCLUYENTE', motivo: 'Sin respuesta', evidencia: null }],
    cypress: { total_pruebas: 0 }, preflight_herramientas: {}, evidencias: [], bitacora: [],
    paginas: [], valores: [], unidades: [], observaciones: [], problemas_tecnicos: [],
    cierre: { run: { cierre_http: null }, rollback: { verificado: false, motivo: 'RUN no cerrado' } },
    inicio: new Date().toISOString() };
  const secretos = [env.QA_SANDBOX_SECRET, env.QA_PROD_PASSWORD, env.QA_PROD_EMAIL].filter(Boolean);
  let abierto = false;
  try {
    const pre = preflight(c, env, ensayo); escribir(path.join(c.directorio, 'preflight.json'), pre);
    r.evidencias.push('preflight.json');
    if (!pre.ok) throw Error(`PREFLIGHT:${pre.barreras.join(',')}`);
    r.preflight_herramientas.newman = prevalidarNewman();
    if (!r.preflight_herramientas.newman.ok) throw Error('NEWMAN_NO_DISPONIBLE');
    const login = await pedir(api, 'POST', '/sesiones/', { cuerpo: {
      correo_electronico: env.QA_PROD_EMAIL, contrasena: env.QA_PROD_PASSWORD }, bitacora: r.bitacora });
    if (login.http !== 200 || !login.cuerpo?.token) throw Error(`LOGIN_PRODUCTOR_HTTP_${login.http}`);
    secretos.push(login.cuerpo.token);
    abierto = true; r.consume_version = true;
    r.unidades = await descubrir(api, login.cuerpo.token, env, c, r);
    const n = await ejecutarNewman(c, { api, token: login.cuerpo.token, env, unidades: r.unidades, secretos, ensayo });
    r.evidencias.push(...n.artefactos);
    r.paginas = n.paginas.map(({ sensores, ...p }) => ({ ...p, cantidad: sensores?.length ?? null }));
    r.valores = resumenValores(n.paginas);
    for (const p of n.paginas) r.bitacora.push({ metodo: 'GET',
      ruta: `/iot/monitoreo/dashboard/${p.unidad}?pagina=${p.pagina}&por_pagina=${PRESUPUESTO.por_pagina}`,
      http: p.http, en_run: true, eco: p.eco });
    const { datos, problemasTecnicos } = evaluarNewman(n);
    r.comprobaciones[0] = { ...r.comprobaciones[0], ...datos,
      evidencia: n.artefactos[0] ?? null };
    r.problemas_tecnicos.push(...problemasTecnicos);
  } catch (e) {
    const motivo = String(e.message).slice(0, 180);
    r.problemas_tecnicos.push(motivo);
    if (r.comprobaciones[0].motivo === 'Sin respuesta') r.comprobaciones[0].motivo = `Ejecución no completada: ${motivo}`;
  }
  finally {
    if (abierto) try {
      const cierre = await pedir(api, 'DELETE', `/test-control/runs/${c.runId}`,
        { secreto: env.QA_SANDBOX_SECRET, bitacora: r.bitacora });
      r.cierre.run.cierre_http = cierre.http;
      const dentro = r.bitacora.filter(x => x.en_run);
      const soloLectura = dentro.length > 0 && dentro.every(x => x.metodo === 'GET' && x.eco === true);
      r.cierre.rollback.verificado = cierre.http === 200 && soloLectura;
      r.cierre.rollback.motivo = r.cierre.rollback.verificado
        ? `Bitácora: ${dentro.length} GET con eco, ninguna escritura de escenario; DELETE 200`
        : `Sin verificación conjunta: GET con eco=${soloLectura}; DELETE HTTP ${cierre.http}`;
    } catch (e) { r.cierre.rollback.motivo = `Cierre sin respuesta: ${String(e.message).slice(0, 100)}`;
      r.problemas_tecnicos.push('CIERRE_NO_ACREDITADO'); }
    finalizar(c, r, secretos);
  }
  return r;
}
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  if (process.argv.includes('--capacidades')) console.log(JSON.stringify(CAPACIDADES, null, 2));
  else if (process.argv.includes('--comprobar')) process.exitCode = comprobar();
  else {
    try {
      const ensayo = process.argv.includes('--ensayo-loopback');
      const c = contextoEjecucion(process.argv.slice(2), { grupo: 'G96', casos: [CASO], directorio: DIR, modoEnsayo: ensayo });
      const env = ensayo ? { QA_AUTORIZADO: 'SI', SIGAB_API_TEST_BASE: process.env.G96_ENSAYO_BASE,
        QA_SANDBOX_SECRET: 'ENSAYO_SECRET', QA_PROD_EMAIL: 'productor@example.test', QA_PROD_PASSWORD: 'ENSAYO_PASS' }
        : leerEnv();
      const r = await evaluar(c, { env, ensayo });
      console.log(JSON.stringify({ run_id: r.run_id, estado: r.casos[CASO].estado, oficial: r.oficial }));
      if (r.problemas_tecnicos.length) process.exitCode = 2;
    } catch (e) { console.error(`G96: ${e.message}`); process.exitCode = 2; }
  }
}
