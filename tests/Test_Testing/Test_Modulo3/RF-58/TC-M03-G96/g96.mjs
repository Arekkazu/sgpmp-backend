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
  const claves = ['SIGAB_API_TEST_BASE', 'QA_SANDBOX_SECRET', 'QA_PROD_EMAIL', 'QA_PROD_PASSWORD', 'QA_ADMIN_EMAIL', 'QA_ADMIN_PASSWORD'];
  const barreras = claves.filter(k => !String(env[k] ?? '').trim());
  const base = String(env.SIGAB_API_TEST_BASE ?? '').replace(/\/+$/, '');
  if (env.QA_AUTORIZADO !== 'SI') barreras.push('QA_AUTORIZADO');
  if (ensayo ? !/^http:\/\/127\.0\.0\.1:\d+$/.test(base) : base !== API) barreras.push('API_NO_CANONICA');
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
  const presentes = fs.readdirSync(DIR).filter(x => !['lib', 'pruebas', 'Resultados', 'EvaluacionV2'].includes(x))
    .concat(...['lib', 'pruebas'].map(d => fs.readdirSync(path.join(DIR, d)).map(x => `${d}/${x}`)));
  const faltantes = archivos.filter(x => !fs.existsSync(path.join(DIR, x)));
  const inesperados = presentes.filter(x => !archivos.includes(x));
  let sintaxis = false;
  try {
    const col = JSON.parse(fs.readFileSync(COLECCION, 'utf8'));
    for (const e of col.item.flatMap(i => i.event ?? [])) new vm.Script((e.script?.exec ?? []).join('\n'));
    sintaxis = col.item.length === 1 && JSON.stringify(col).includes('API-187-01');
  } catch { /* se informa abajo */ }
  const runOficial = path.join(DIR, 'Resultados', 'RUN-G96-V1-20261031-153625');
  const informeOficial = path.join(runOficial, 'TC-M03-G96_resultado.md');
  const obsoletos = /(?:\.\.[\\/]|Resultados[\\/])RUN-G96-V1-20261031-(?:095744|150253|151856)(?:[\\/]|\b)/;
  const sinDependenciasTecnicas = archivos.filter(x => x !== 'G96.postman_collection.json')
    .every(x => !obsoletos.test(fs.readFileSync(path.join(DIR, x), 'utf8')));
  let antecedentesOk = false;
  let enlacesOk = false;
  try {
    const carpeta = path.join(runOficial, 'api', 'antecedentes');
    const indice = JSON.parse(fs.readFileSync(path.join(carpeta, 'indice.json'), 'utf8'));
    antecedentesOk = indice.run_oficial === path.basename(runOficial)
      && indice.antecedentes.length === 3
      && indice.antecedentes.every((x, i) => x.intento === i + 1
        && x.extracto === `intento-${i + 1}.json`
        && x.archivos_origen.every(a => /^[a-f0-9]{64}$/.test(a.sha256))
        && JSON.parse(fs.readFileSync(path.join(carpeta, x.extracto), 'utf8')).run_origen === x.run_origen);
    const informeTexto = fs.readFileSync(informeOficial, 'utf8');
    const enlaces = [...informeTexto.matchAll(/\]\(([^)]+)\)/g)].map(x => x[1]);
    enlacesOk = !obsoletos.test(informeTexto) && enlaces.length >= 4
      && enlaces.every(x => !path.isAbsolute(x) && !x.includes('..')
        && fs.existsSync(path.join(runOficial, x)));
  } catch { /* se informa abajo */ }
  const ok = !faltantes.length && !inesperados.length && sintaxis && CAPACIDADES.contrato === 'sigab-qa-ejecutor/1'
    && sinDependenciasTecnicas && antecedentesOk && enlacesOk
    && !fs.existsSync(path.join(DIR, 'informe.md')) && (!fs.existsSync(path.join(DIR, 'Resultados'))
      || !fs.readdirSync(path.join(DIR, 'Resultados')).some(x => x.endsWith('.md')));
  console.log(JSON.stringify({ grupo: 'G96', ok, faltantes, inesperados, sintaxis,
    sinDependenciasTecnicas, antecedentesOk, enlacesOk, presupuesto: PRESUPUESTO }));
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
export async function descubrir(api, adminToken, prodToken, env, c, r) {
  const dispositivos = Object.fromEntries(CATALOGO.map(e => [e, []]));
  const disponibles = Object.fromEntries(CATALOGO.map(e => [e, []]));
  const porArea = new Map();
  const productor = await pedir(api, 'GET', '/iot/dispositivos', { token: prodToken,
    secreto: env.QA_SANDBOX_SECRET, runId: c.runId, bitacora: r.bitacora });
  if (productor.http !== 200 || !productor.eco || !Array.isArray(productor.cuerpo))
    throw Error(`LISTADO_PRODUCTOR_HTTP_${productor.http ?? 'SIN_RESPUESTA'}_ECO_${productor.eco}`);
  const idsProductor = new Set(productor.cuerpo.map(d => Number(d?.id_dispositivo_iot)));
  r.listados.push({ estado: 'TODOS_PRODUCTOR', rol: 'Productor', http: productor.http,
    eco: productor.eco, cantidad: productor.cuerpo.length });
  for (const estado of CATALOGO) {
    const ruta = `/iot/dispositivos?estado=${encodeURIComponent(estado)}`;
    const q = await pedir(api, 'GET', ruta, { token: adminToken, secreto: env.QA_SANDBOX_SECRET,
      runId: c.runId, bitacora: r.bitacora });
    r.listados.push({ estado, rol: 'Administrador', http: q.http, eco: q.eco,
      cantidad: Array.isArray(q.cuerpo) ? q.cuerpo.length : null });
    if (q.http !== 200 || !q.eco || !Array.isArray(q.cuerpo)) {
      r.problemas_tecnicos.push(`LISTADO_${estado}_HTTP_${q.http ?? 'SIN_RESPUESTA'}_ECO_${q.eco}`);
      continue;
    }
    for (const d of q.cuerpo) {
      const id = Number(d?.id_dispositivo_iot), area = Number(d?.id_infraestructura);
      if (d?.estado_actual !== estado || !Number.isInteger(id) || id < 1 || !Number.isInteger(area) || area < 1) continue;
      const candidato = { id_dispositivo_iot: id, id_infraestructura: area };
      disponibles[estado].push(candidato);
      if (!porArea.has(area)) porArea.set(area, { Productor: [], Administrador: [] });
      porArea.get(area)[idsProductor.has(id) ? 'Productor' : 'Administrador'].push({ estado, ...candidato });
    }
  }
  const aptas = [];
  const probadas = new Set();
  const sondeos = new Map();
  r.descartadas = [];
  for (const rol of ['Productor', 'Administrador']) {
    let continuar = true;
    while (continuar && r.canarios.length < PRESUPUESTO.canarios_e7
      && aptas.length < PRESUPUESTO.areas_candidatas) {
      continuar = false;
      for (const estado of CATALOGO) {
        if (dispositivos[estado].length && estado !== 'EN_MANTENIMIENTO') continue;
        const d = disponibles[estado].find(x => !probadas.has(`${rol}:${x.id_dispositivo_iot}`)
          && !aptas.some(u => u.area === x.id_infraestructura && u.rol !== rol)
          && porArea.get(x.id_infraestructura)?.[rol].length);
        if (!d || r.canarios.length >= PRESUPUESTO.canarios_e7
          || aptas.length >= PRESUPUESTO.areas_candidatas) continue;
        continuar = true;
        const area = d.id_infraestructura;
        probadas.add(`${rol}:${d.id_dispositivo_iot}`);
        const clave = `${rol}:${area}`;
        if (!sondeos.has(clave)) {
          const ids = new Set();
          let motivo = null, total = null;
          const propios = new Set(porArea.get(area)[rol].map(x => x.id_dispositivo_iot));
          for (let pagina = 1; r.canarios.length < PRESUPUESTO.canarios_e7; pagina++) {
            const q = await pedir(api, 'GET', `/iot/monitoreo/dashboard?id_infraestructura=${area}&pagina=${pagina}&por_pagina=1`,
              { token: rol === 'Productor' ? prodToken : adminToken, secreto: env.QA_SANDBOX_SECRET,
                runId: c.runId, bitacora: r.bitacora });
            total = q.cuerpo?.total;
            const sensores = q.cuerpo?.sensores;
            const inseguro = Array.isArray(sensores) && sensores.some(s => s?.estado_semaforo === 'GRIS'
              && (s?.dato_desactualizado !== true || s?.sin_umbral === true));
            r.canarios.push({ area, rol, pagina, http: q.http, eco: q.eco, total: total ?? null,
              excluida_e7: inseguro, desconocido: Array.isArray(sensores)
                ? sensores.filter(s => s?.estado_conectividad === 'DESCONOCIDO').length : 0 });
            if (q.http !== 200 || !q.eco || !Number.isInteger(total) || total < 0 || !Array.isArray(sensores)) {
              r.problemas_tecnicos.push(`CANARIO_E7_AREA_${area}_HTTP_${q.http ?? 'SIN_RESPUESTA'}`);
              motivo = 'Canario incompleto'; break;
            }
            if (inseguro) { motivo = 'E7: GRIS no desactualizado o sin umbral'; break; }
            for (const s of sensores) if (propios.has(Number(s?.id_dispositivo_iot))) ids.add(Number(s.id_dispositivo_iot));
            if (pagina >= total || ids.size === propios.size) break;
          }
          if (!motivo && !ids.size) motivo = r.canarios.length >= PRESUPUESTO.canarios_e7
            ? 'Sin sensores propios visibles antes del límite de canarios'
            : 'Sin sensores propios en el área';
          sondeos.set(clave, { ids, motivo });
          if (motivo?.startsWith('E7:')) r.descartadas.push({ area, rol, motivo });
        }
        const sondeo = sondeos.get(clave);
        if (!sondeo.motivo?.startsWith('E7:') && sondeo.ids.has(d.id_dispositivo_iot)) {
          if (!aptas.some(u => u.area === area && u.rol === rol)) aptas.push({ area, rol });
          if (!dispositivos[estado].some(x => x.id_dispositivo_iot === d.id_dispositivo_iot))
            dispositivos[estado].push({ ...d, rol });
        } else if (!sondeo.motivo?.startsWith('E7:')) {
          r.descartadas.push({ area, rol, dispositivo: d.id_dispositivo_iot,
            estado, motivo: sondeo.motivo ?? 'Sin sensores propios visibles para el dispositivo' });
        }
      }
    }
  }
  r.dispositivos = dispositivos;
  r.disponibles = Object.fromEntries(CATALOGO.map(e => [e, disponibles[e].length]));
  return aptas;
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
export function leerPagina(ex, runId) {
  const url = ex.request?.url;
  const u = String(url?.raw ?? url ?? '');
  const m = u.match(/\/dashboard\?id_infraestructura=(\d+)&pagina=(\d+)/);
  const id = m ? Number(m[1]) : Number(Array.isArray(url?.query) ? url.query.find(x => x.key === 'id_infraestructura')?.value : null);
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
      id_dispositivo_iot: Number(s?.id_dispositivo_iot),
      ...(Object.hasOwn(s, 'estado_conectividad') ? { estado_conectividad: s.estado_conectividad } : {}),
    })) : null };
}
export async function ejecutarNewman(c, { api, prodToken, adminToken, env, unidades, secretos, ensayo = false }) {
  const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'g96-newman-'));
  try {
    const salida = path.join(c.directorio, 'newman'); fs.mkdirSync(salida, { recursive: true });
    const variables = { autorizado_run: 'SI', base_url: api, run_id: c.runId, sandbox_secret: env.QA_SANDBOX_SECRET,
      token_prod: prodToken, token_admin: adminToken, token: unidades[0].rol === 'Productor' ? prodToken : adminToken,
      unidades: JSON.stringify(unidades), unidad: String(unidades[0].area), indice: '0', pagina: '1',
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
    const paginas = (report.run?.executions ?? []).map(x => {
      const p = leerPagina(x, c.runId);
      return { ...p, rol: unidades.find(u => u.area === p.unidad)?.rol ?? null };
    });
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
  let datos = clasificar({ paginas, dispositivos: n.dispositivos ?? {}, disponibles: n.disponibles ?? {}, paginasCompletas: paginasCompletas(paginas),
    error: n.error ?? (transporte || ultimo?.http == null ? 'SIN_RESPUESTA' : null) });
  // La colección vigente tiene una aserción funcional: [TC-M03-187][ASSERT][API-187-01].
  // HTTP 5xx, respuesta ausente, eco y formato ya tienen veredicto en clasificar().
  const falloEnum = (n.fallos ?? []).some(f => f.tipo === 'AssertionError'
    && f.test.startsWith('[TC-M03-187][ASSERT][API-187-01]'));
  if (falloEnum && datos.catalogo.estado === 'APROBADO')
    datos.catalogo = { estado: 'RECHAZADO', motivo: 'Aserción funcional API-187-01 fallida en respuesta 200 con eco' };
  const problemasTecnicos = [];
  if (n.error || transporte) problemasTecnicos.push(`NEWMAN_${n.error ?? 'TRANSPORTE'}`);
  if (paginas.some(p => p.http >= 500)) problemasTecnicos.push('DASHBOARD_HTTP_5XX');
  if (paginas.some(p => p.http === 200 && !p.eco)) problemasTecnicos.push('ECO_RUN_AUSENTE');
  if (paginas.length > PRESUPUESTO.paginas_dashboard) problemasTecnicos.push('PRESUPUESTO_PAGINAS_SUPERADO');
  if ((n.fallos ?? []).some(f => /^(TypeError|ReferenceError|SyntaxError)$/.test(f.tipo)
    || (f.tipo === 'AssertionError' && /\[(?:PRE|INFO)\]/.test(f.test)
      && !/\b(?:HTTP|eco)\b/i.test(f.test))))
    problemasTecnicos.push('NEWMAN_ERROR_SCRIPT_O_TRANSPORTE');
  if (n.proceso?.error) problemasTecnicos.push(`NEWMAN_${n.proceso.error}`);
  if (n.proceso?.status != null && n.proceso.status !== 0 && !(n.fallos ?? []).some(f => f.tipo === 'AssertionError'))
    problemasTecnicos.push(`NEWMAN_EXIT_${n.proceso.status}`);
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
function desconocidosCanario(canarios, areasConPagina = []) {
  const consultadas = new Set(areasConPagina);
  const vistas = new Set();
  const filas = canarios.filter(x => {
    const clave = `${x.area}:${x.pagina}`;
    if (!x.desconocido || consultadas.has(x.area) || vistas.has(clave)) return false;
    vistas.add(clave); return true;
  });
  return { cantidad: filas.reduce((n, x) => n + x.desconocido, 0),
    areas: [...new Set(filas.map(x => x.area))] };
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
  const cierreOficial = r.run_id === 'RUN-G96-V1-20261031-153625';
  const comp = r.comprobaciones.map(x => `| ${x.id} | API | ${x.tipo} | ${x.estado} | ${x.motivo} | ${x.evidencia ?? 'Sin evidencia'} |`).join('\n');
  const cobertura = CATALOGO.map(x => {
    const c = r.cobertura[x] ?? { estado: 'NO_CONCLUYENTE', motivo: 'Sin ejecución' };
    return `| ${x} | ${(r.dispositivos[x] ?? []).length} | ${c.area ?? '—'} | ${c.dispositivo ?? '—'} | ${c.rol ?? '—'} | ${c.sensores_cotejados ?? 0} | ${c.estado} | ${c.motivo} |`;
  }).join('\n');
  const valores = r.valores.map(x => `| ${x.unidad} | ${x.valor} | ${x.cantidad} |`).join('\n') || '| — | Sin datos | 0 |';
  const cotejados = r.cobertura_detalle.map(x => `| ${x.estado} | ${x.dispositivo} | ${x.area} | ${x.rol} | ${x.sensores_cotejados} |`).join('\n') || '| — | — | — | — | 0 |';
  const descartadas = r.descartadas.map(x => `| ${x.area} | ${x.rol} | ${x.dispositivo ?? '—'} | ${x.estado ?? '—'} | ${x.motivo} |`).join('\n') || '| — | — | — | — | Ninguna |';
  const fallos = CATALOGO.filter(x => r.cobertura[x]?.estado === 'RECHAZADO');
  const incidencia = estado === 'RECHAZADO'
    ? `Discrepancia confirmada por API pública en este RUN: ${r.casos[CASO].motivo}. Equipo inicial: Desarrollo, porque el primer incumplimiento comprobado está en la respuesta del dashboard frente al estado público del dispositivo. RF-60 postcondición 3. Severidad MEDIA: afecta estados de conectividad observados, sin evidencia de alcance generalizado. Certeza CONFIRMADA del resultado observado; causa raíz NO DETERMINADA. Hipótesis por lectura local: la sincronización desde buffer puede dejar SIN_SEÑAL y el dashboard puede omitir BUFFER_ACTIVO/EN_MANTENIMIENTO; no se presume código desplegado. Reproducción: GET /iot/dispositivos?estado=<estado> como Administrador, identificar dispositivo y área; GET /iot/monitoreo/dashboard?id_infraestructura=<área> con el rol registrado en la cobertura y comparar sensores del mismo dispositivo. Acción: Desarrollo investiga ${fallos.join(', ') || 'el valor fuera de catálogo'} y solicita reevaluación autorizada.`
    : cierreOficial
      ? 'Ninguna incidencia funcional confirmada. El RUN acreditó en la respuesta pública del dashboard los cinco estados, incluidos BUFFER_ACTIVO y EN_MANTENIMIENTO; la divergencia señalada durante la lectura del código local quedó superada por RFC-020.'
      : 'Ninguna incidencia funcional confirmada. Las observaciones de código local requieren cotejo con la respuesta pública del RUN.';
  return `# TC-M03-G96 — ${estado}

## 1. Identificación

Grupo G96; caso TC-M03-187; RF-58/CU04 con catálogo vigente RF-60; versión V${r.version}; RUN ${r.run_id}; ambiente ${r.ambiente}; autorización ${r.autorizacion}; referencia backend ${COMMIT_BACKEND} (despliegue no verificado). Node ${process.version}; Newman ${r.preflight_herramientas.newman?.version ?? 'no verificado'}; Postman/Cypress no ejecutados. Contrato solo API.

## 2. Resumen ejecutivo y decisión del grupo

**${estado}**. ${r.casos[CASO].motivo}. Oficial: ${r.oficial ? 'SÍ' : 'NO'}. Newman: ${r.evidencias.some(x => x === 'newman/newman-G96.json') ? 'una ejecución con reporte' : 'sin reporte generado'}; ${r.paginas.length} páginas registradas.

## 3. Detalle por caso y comprobaciones API/UI

### TC-M03-187

**Objetivo:** comprobar el catálogo cerrado de conectividad y la correspondencia de cada estado del dispositivo con sus sensores visibles al Productor.

**Precondiciones:** Productor y Administrador acreditados; dispositivos con sensores asociados y área visible al rol consultado. La ausencia de datos deja esa cobertura NO_CONCLUYENTE sin escrituras.${cierreOficial ? ' El 2026-10-31, la IA de BD creó con autorización del responsable QA dos semillas persistentes fuera del RUN: SIN_SEÑAL en área 701, finca 184, dispositivo 787 y sensor 1208 (caché SIN_SEÑAL, semáforo GRIS, dato desactualizado); EN_MANTENIMIENTO en dispositivo 788 y sensor 1209 (caché EN_MANTENIMIENTO, semáforo VERDE, dato no desactualizado). Fueron necesarias porque en TEST no había dispositivos SIN_SEÑAL y los tres EN_MANTENIMIENTO existentes no permitían cobertura segura: uno carecía de sensores y los de áreas 664 y 665 tenían sensores DESCONOCIDO, GRIS y no desactualizados, excluidos por riesgo E7. Las semillas fijaron el estado del dispositivo; la propagación al dashboard correspondió al producto mediante RFC-020.' : ''}

**Pasos:** iniciar sesión con ambos roles; listar dispositivos por cada estado como Administrador y el alcance completo como Productor; recorrer los candidatos, priorizar áreas del Productor y aceptar solo dispositivos cuyos sensores propios aparecen en canarios; excluir áreas cuyo canario muestre GRIS no desactualizado o sin umbral; si falta un estado, probar áreas como Administrador; consultar hasta ocho áreas aptas y sus páginas con Newman; cotejar id_dispositivo_iot y estado_conectividad de todos los dispositivos de las áreas consultadas.

**Entradas:** GET /iot/dispositivos?estado=<E> (Administrador) para los cinco estados; GET /iot/dispositivos (Productor) para identificar sus dispositivos; GET /iot/monitoreo/dashboard?id_infraestructura=<ID>&pagina=<N>&por_pagina=1 (canario) y por_pagina=50 (Newman) con el rol indicado por área.

**Esperado:** ${ORACULO} Todo valor fuera del catálogo, incluidos ONLINE, OFFLINE, null y ausente, rechaza el catálogo. DESCONOCIDO se registra como observación de requisito pendiente sin rechazo por sí solo. Cada dispositivo con sensores visibles conserva su estado en el dashboard.

**Observado:** valores por área en tabla posterior; ${r.desconocido ?? 0} sensor(es) DESCONOCIDO en ${(r.desconocido_areas ?? []).length} área(s) (${(r.desconocido_areas ?? []).join(', ') || 'ninguna'}), contando páginas Newman y canarios de áreas sin página Newman, observación de requisito pendiente.${cierreOficial ? ' Las semillas 787 (SIN_SEÑAL) y 788 (EN_MANTENIMIENTO), ambas en área 701, aparecieron con un sensor propio concordante cada una en el dashboard.' : ''} ${r.casos[CASO].motivo}.

**Decisión del caso:** **${estado}**. ${r.casos[CASO].motivo}

| Comprobación | Fuente | Tipo | Estado | Motivo | Evidencia |
|---|---|---|---|---|---|
${comp}

**Cobertura por estado**

| Estado RF-60 | Candidatos | Área | Dispositivo | Rol dashboard | Sensores cotejados | Estado | Motivo |
|---|---:|---:|---:|---|---:|---|---|
${cobertura}

**Dispositivos cotejados**

| Estado RF-60 | Dispositivo | Área | Rol dashboard | Sensores cotejados |
|---|---:|---:|---|---:|
${cotejados}

**Áreas descartadas**

| Área | Rol | Dispositivo | Estado | Motivo |
|---:|---|---:|---|---|
${descartadas}

**Valores observados**

| Área | Estado exacto | Sensores |
|---|---|---:|
${valores}

## 4. Incidencias y observaciones

${incidencia}

Decisión del líder de análisis (2026-10-31): RF-60 rige con cinco estados; los tres de RF-58 son inconsistencia documental; ONLINE/OFFLINE solo RF-54. DESCONOCIDO sigue en revisión, sin correspondencia definida.

${cierreOficial ? `RFC-020: el RUN acreditó por API pública BUFFER_ACTIVO y EN_MANTENIMIENTO en el dashboard; la IA de BD confirmó la función desplegada y la revisión Alembic c31f8a6d920e. La evidencia funcional es la respuesta pública del RUN; la versión exacta del backend referida en la identificación no quedó verificada.

**Observaciones para Análisis, sin efecto en el veredicto:**

- Se observaron 10 sensores con estado_conectividad DESCONOCIDO en las áreas 347, 664 y 665. Ese estado no está definido en la ficha y sigue en revisión. Los sensores de 664 y 665 aparecen GRIS y no desactualizados, condición de aviso E7.
- En EN_MANTENIMIENTO, el sensor 1209 aparece VERDE con un dato de hace siete días. RFC-020 no cambia el semáforo ni la marca de desactualización en ese estado; revisar si RF-60 fase 7 exige otro color.
- En el intento 2 (RUN técnico 150253) se consultó completa el área 664, cuyos sensores estaban GRIS y no desactualizados. Pudo generarse un aviso E7 a Administradores de cuentas ficticias; el envío no quedó acreditado.

**Historial de intentos técnicos V1:** intento 1, [extracto saneado](api/antecedentes/intento-1.json): NO_CONCLUYENTE, faltaba SIN_SEÑAL y varios estados no tenían sensores visibles al Productor. Intento 2, [extracto saneado](api/antecedentes/intento-2.json): NO_CONCLUYENTE, cuatro estados cubiertos y EN_MANTENIMIENTO sin sensor propio visible; incluyó la consulta completa del área 664. Intento 3, [extracto saneado](api/antecedentes/intento-3.json): NO_CONCLUYENTE, EN_MANTENIMIENTO siguió sin sensor propio visible en las páginas inspeccionadas o se agotó el presupuesto de canarios; 664 y 665 se excluyeron por E7. El intento 4, presente RUN 153625, acredita los cinco estados. [Indice de origen y SHA-256](api/antecedentes/indice.json). Los RUN de origen fueron eliminados de los enlaces vigentes; la eliminacion fisica de sus carpetas corresponde al orquestador y sigue pendiente.` : 'Contexto local RFC-020 #794: la migración revisada describe la propagación de las transiciones del dispositivo a la caché de sus sensores. El despliegue requiere evidencia pública del RUN.'}

**Problemas técnicos QA:** ${r.problemas_tecnicos.join('; ') || 'Ninguno'}.

## 5. Análisis de fallos

Primera discrepancia y certeza: ${estado === 'RECHAZADO' ? 'respuesta API comprobada, causa raíz no determinada' : 'sin incumplimiento funcional concluyente'}. Código consultado en esta preparación: src/telemetry/infrastructure/schema/monitoreo_schema.py, src/telemetry/infrastructure/repositories/monitoreo_repository.py y alembic/versions/8a8f1dae36f1_rfc020_conectividad_dashboard_estado_dispositivo.py. ${cierreOficial ? 'La respuesta pública acredita el comportamiento de RFC-020 y la IA de BD confirmó su función desplegada; no se identificó causa de fallo funcional.' : 'No se verificó la versión desplegada.'}

## 6. Conclusiones y acciones

${estado}: ${r.casos[CASO].motivo}. ${estado === 'RECHAZADO' ? 'Derivar a Desarrollo con evidencia saneada del mismo RUN.' : estado === 'APROBADO' ? 'Conservar evidencia y cerrar el caso.' : 'El responsable QA debe decidir el veredicto global ante la cobertura parcial. SIN_SEÑAL sin dispositivos no puede construirse sin escrituras; no se crean datos. Acreditar estados y sensores faltantes con datos existentes en un nuevo RUN autorizado.'}

## 7. Herramientas, evidencias, bitácora y rollback

Newman: ${r.paginas.length} páginas, límite ${PRESUPUESTO.paginas_dashboard}; listados: ${r.listados.map(x => `${x.estado} (${x.rol}) HTTP ${x.http ?? 'sin respuesta'}, eco ${x.eco}, ${x.cantidad ?? 'sin lista'} dispositivo(s)`).join('; ') || 'ninguno'}; canarios ${r.canarios.length}/${PRESUPUESTO.canarios_e7}: ${r.canarios.map(x => `área ${x.area} (${x.rol}) total ${x.total ?? 'sin total'}`).join('; ') || 'ninguno'}; áreas aptas ${r.unidades.map(x => `${x.area} (${x.rol})`).join(', ') || 'ninguna'}. Máximo ${PRESUPUESTO.solicitudes_en_run} GET en RUN y ${PRESUPUESTO.duracion_segundos} segundos. Evidencias reales: ${r.evidencias.join(', ')}. Cierre DELETE RUN HTTP ${r.cierre.run.cierre_http ?? 'sin respuesta'}. Rollback: ${r.cierre.rollback.motivo}. Login previo puede registrar auditoría y las lecturas pueden activar correo E7; su reversión no se acredita.
`;
}
function finalizar(c, r, secretos) {
  const estados = r.comprobaciones.map(x => x.estado);
  const estado = estados.includes('RECHAZADO') ? 'RECHAZADO'
    : estados.every(x => x === 'APROBADO') ? 'APROBADO' : 'NO_CONCLUYENTE';
  r.casos[CASO] = { estado, motivo: r.comprobaciones.filter(x => x.estado !== 'APROBADO').map(x => x.motivo).join('; ') || 'Catálogo y cinco coberturas acreditadas' };
  const nombre = c.version === 1 ? 'TC-M03-G96_resultado.md' : `TC-M03-G96_reevaluacion_V${c.version}.md`;
  r.evidencias = [...new Set([...r.evidencias, 'resultado.json', nombre])];
  const evidenciasOk = r.evidencias.every(x => typeof x === 'string' && !x.includes('..') && !path.isAbsolute(x)
    && (x === nombre || x === 'resultado.json' || fs.existsSync(path.join(c.directorio, x))));
  r.oficial = r.ambiente === 'TEST' && esOficial(estado, r, evidenciasOk);
  r.fin = new Date().toISOString();
  escribir(path.join(c.directorio, 'resultado.json'), r);
  fs.writeFileSync(path.join(c.directorio, nombre), sanearArtefacto(informe(r), secretos));
}
export function esOficial(estado, r, evidenciasOk) {
  return ['APROBADO', 'RECHAZADO'].includes(estado) && r.cierre.run.cierre_http === 200
    && r.cierre.rollback.verificado && evidenciasOk && r.problemas_tecnicos.length === 0
    && r.comprobaciones?.length === 2
    && CAPACIDADES.comprobaciones_obligatorias[CASO].API.every(id => r.comprobaciones.some(x =>
      x.caso === CASO && x.fuente === 'API' && x.id === id && x.tipo === 'ASSERT'
      && ['APROBADO', 'RECHAZADO'].includes(x.estado)));
}
export async function evaluar(c, { env = leerEnv(), ensayo = false } = {}) {
  if (!fs.existsSync(c.directorio)) throw Error('RUN_NO_CREADO_POR_LANZADOR');
  const api = String(env.SIGAB_API_TEST_BASE ?? '').replace(/\/+$/, '');
  const r = { grupo: 'G96', run_id: c.runId, version: c.version, operacion: c.operacion,
    autorizacion: c.referencia, ambiente: ensayo ? 'LOOPBACK_LOCAL' : 'TEST', oficial: false,
    consume_version: false, casos: { [CASO]: { estado: 'NO_CONCLUYENTE', motivo: 'Sin ejecución' } },
    comprobaciones: ['API-187-01', 'API-187-02'].map(id => ({ caso: CASO, fuente: 'API', id, tipo: 'ASSERT', estado: 'NO_CONCLUYENTE', motivo: 'Sin respuesta', evidencia: null })),
    cypress: { total_pruebas: 0 }, preflight_herramientas: {}, evidencias: [], bitacora: [],
    paginas: [], valores: [], unidades: [], dispositivos: {}, disponibles: {}, listados: [], cobertura: {}, cobertura_detalle: [], canarios: [], descartadas: [], observaciones: [], problemas_tecnicos: [],
    cierre: { run: { cierre_http: null }, rollback: { verificado: false, motivo: 'RUN no cerrado' } },
    inicio: new Date().toISOString() };
  const secretos = [env.QA_SANDBOX_SECRET, env.QA_PROD_PASSWORD, env.QA_PROD_EMAIL,
    env.QA_ADMIN_PASSWORD, env.QA_ADMIN_EMAIL].filter(Boolean);
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
    const loginAdmin = await pedir(api, 'POST', '/sesiones/', { cuerpo: {
      correo_electronico: env.QA_ADMIN_EMAIL, contrasena: env.QA_ADMIN_PASSWORD }, bitacora: r.bitacora });
    if (loginAdmin.http !== 200 || !loginAdmin.cuerpo?.token) throw Error(`LOGIN_ADMIN_HTTP_${loginAdmin.http}`);
    secretos.push(loginAdmin.cuerpo.token);
    abierto = true; r.consume_version = true;
    r.unidades = await descubrir(api, loginAdmin.cuerpo.token, login.cuerpo.token, env, c, r);
    if (!r.unidades.length) {
      const datos = clasificar({ dispositivos: r.dispositivos, disponibles: r.disponibles });
      r.cobertura = datos.cobertura;
      r.cobertura_detalle = datos.cobertura_detalle;
      const obs = desconocidosCanario(r.canarios);
      r.desconocido = obs.cantidad;
      r.desconocido_areas = obs.areas;
      if (r.desconocido) r.observaciones.push({ tipo: 'REQUISITO_PENDIENTE', asunto: 'DESCONOCIDO',
        sensores: r.desconocido, areas: r.desconocido_areas });
      r.comprobaciones[0].motivo = 'Sin área apta para comprobar el catálogo';
      r.comprobaciones[1].motivo = CATALOGO.map(x => `${x}: ${datos.cobertura[x].motivo}`).join('; ');
      return r;
    }
    const n = await ejecutarNewman(c, { api, prodToken: login.cuerpo.token,
      adminToken: loginAdmin.cuerpo.token, env, unidades: r.unidades, secretos, ensayo });
    n.dispositivos = r.dispositivos; n.disponibles = r.disponibles;
    r.evidencias.push(...n.artefactos);
    r.paginas = n.paginas.map(({ sensores, ...p }) => ({ ...p, cantidad: sensores?.length ?? null }));
    r.valores = resumenValores(n.paginas);
    for (const p of n.paginas) r.bitacora.push({ metodo: 'GET',
      ruta: `/iot/monitoreo/dashboard?id_infraestructura=${p.unidad}&pagina=${p.pagina}&por_pagina=${PRESUPUESTO.por_pagina}`,
      http: p.http, en_run: true, eco: p.eco });
    const { datos, problemasTecnicos } = evaluarNewman(n);
    r.cobertura = datos.cobertura;
    r.cobertura_detalle = datos.cobertura_detalle;
    const obs = desconocidosCanario(r.canarios, n.paginas.map(x => x.unidad));
    r.desconocido = datos.desconocido + obs.cantidad;
    r.desconocido_areas = [...new Set([...datos.desconocido_areas, ...obs.areas])];
    if (r.desconocido) r.observaciones.push({ tipo: 'REQUISITO_PENDIENTE', asunto: 'DESCONOCIDO',
      sensores: r.desconocido, areas: r.desconocido_areas });
    r.comprobaciones[0] = { ...r.comprobaciones[0], ...datos.catalogo, evidencia: n.artefactos[0] ?? null };
    const estadosCobertura = Object.values(datos.cobertura).map(x => x.estado);
    r.comprobaciones[1] = { ...r.comprobaciones[1], estado: estadosCobertura.includes('RECHAZADO') ? 'RECHAZADO'
      : estadosCobertura.every(x => x === 'APROBADO') ? 'APROBADO' : 'NO_CONCLUYENTE',
    motivo: CATALOGO.map(x => `${x}: ${datos.cobertura[x].estado}`).join('; '), evidencia: n.artefactos[0] ?? null };
    r.problemas_tecnicos.push(...problemasTecnicos);
  } catch (e) {
    const motivo = String(e.message).slice(0, 180);
    r.problemas_tecnicos.push(motivo);
    for (const comp of r.comprobaciones) if (comp.motivo === 'Sin respuesta') comp.motivo = `Ejecución no completada: ${motivo}`;
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
        ? `SIN_ESCRITURAS_QUE_REVERTIR: ${dentro.length} GET con eco y DELETE 200; efectos externos de login/E7 no verificados`
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
        QA_SANDBOX_SECRET: 'ENSAYO_SECRET', QA_PROD_EMAIL: 'productor@example.test', QA_PROD_PASSWORD: 'ENSAYO_PASS',
        QA_ADMIN_EMAIL: 'administrador@example.test', QA_ADMIN_PASSWORD: 'ENSAYO_PASS' }
        : leerEnv();
      const r = await evaluar(c, { env, ensayo });
      console.log(JSON.stringify({ run_id: r.run_id, estado: r.casos[CASO].estado, oficial: r.oficial }));
      if (r.problemas_tecnicos.length) process.exitCode = 2;
    } catch (e) { console.error(`G96: ${e.message}`); process.exitCode = 2; }
  }
}
