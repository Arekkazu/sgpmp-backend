#!/usr/bin/env node
// TC-M03-206 (RF-58): disponibilidad del servicio de monitoreo ≥ 99,0 % durante el periodo observado.
//
// La matriz no fija la duración: se exige explícitamente (--duracion) y queda registrada, junto con
// los intervalos de disponibilidad e indisponibilidad y el porcentaje obtenido.
//
// Sonda (Node, sin Newman ni Cypress; la matriz pide una herramienta de monitoreo):
// - una sola sesión del Ingeniero de Campo fuera del sandbox (efecto aceptado: sesion-persistente;
//   se renueva solo si el token deja de ser válido);
// - cada sondeo es un GET /iot/monitoreo/dashboard dentro de su propio RUN de sandbox, cerrado al
//   terminar: no persisten escrituras (ultimo_acceso) ni se mantiene una transacción abierta horas;
// - los sondeos son secuenciales, uno por intervalo.
// Clasificación de cada sondeo (cubre el tiempo hasta el siguiente):
// - DISPONIBLE: HTTP 200 con el contrato del dashboard dentro del tiempo límite;
// - NO_DISPONIBLE: 5xx, tiempo límite, conexión rechazada o reiniciada, o 200 sin el contrato;
// - NO_VERIFICABLE: 401/403/429, sandbox saturado o sin eco, o fallo de red del propio cliente.
// Resultado: disponibilidad mínima (lo no verificable cuenta como caído) y máxima (como disponible).
// APROBADO si la mínima ≥ 99,0 %; RECHAZADO si la máxima < 99,0 %; si no, BLOQUEADO (indeterminado).
import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { leerEnv, autorizar, version, carpetaResultados, runId, nombreInforme, argumentos, sello, redactor, informe, fetchReal } from './monitoreo_lib.mjs';

export const GRUPO = 'TC-M03-G106';
export const CASOS = ['TC-M03-206'];
export const OBJETIVO = 0.99;
export const INTERVALO_S = 60;
export const LIMITE_RESPUESTA_S = 10;
const RED_CLIENTE = /ENOTFOUND|EAI_AGAIN|ENETUNREACH|EHOSTUNREACH|ENETDOWN/;

const DIR = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(DIR, '../../../../..');
const ENV = path.join(ROOT, '.env.qa');

/** "90m", "24h", "3600s", "2d" → segundos (null si no es válida). */
export function duracionS(texto) {
  const m = /^(\d+)(s|m|h|d)$/.exec(String(texto || '').trim());
  return m && Number(m[1]) > 0 ? Number(m[1]) * { s: 1, m: 60, h: 3600, d: 86400 }[m[2]] : null;
}
/** Contrato mínimo del dashboard (RF-58). */
export const contratoDashboard = b => !!b && Array.isArray(b.sensores) && Array.isArray(b.resumen_unidades) && Number.isFinite(b.total);
/** Clasifica un sondeo a partir de la respuesta HTTP o del error de red. */
export function clasificar({ status, cuerpo, eco, run, error }) {
  if (error) {
    const t = `${error.name || ''} ${error.code || ''} ${error.cause?.code || ''} ${error.message || ''}`;
    if (RED_CLIENTE.test(t)) return { clase: 'NO_VERIFICABLE', motivo: `red del cliente (${(t.match(RED_CLIENTE) || [])[0]})` };
    return { clase: 'NO_DISPONIBLE', motivo: /Timeout|abort/i.test(t) ? `sin respuesta en ${LIMITE_RESPUESTA_S} s` : `error de conexión (${(error.cause?.code || error.code || error.name || 'desconocido')})` };
  }
  if (status >= 500) {
    if (status === 503 && /concurrentes/i.test(JSON.stringify(cuerpo ?? ''))) return { clase: 'NO_VERIFICABLE', motivo: 'sandbox saturado (máximo de RUN concurrentes)' };
    return { clase: 'NO_DISPONIBLE', motivo: `HTTP ${status}` };
  }
  if ([401, 403, 429].includes(status)) return { clase: 'NO_VERIFICABLE', motivo: `HTTP ${status} (credencial, permiso o límite de tasa del cliente)` };
  if (eco !== run) return { clase: 'NO_VERIFICABLE', motivo: 'respuesta sin eco del sandbox' };
  if (status === 200) return contratoDashboard(cuerpo) ? { clase: 'DISPONIBLE', motivo: null } : { clase: 'NO_DISPONIBLE', motivo: 'HTTP 200 sin el contrato del dashboard' };
  return { clase: 'NO_VERIFICABLE', motivo: `HTTP ${status} inesperado para la sonda` };
}
/** Tiempo cubierto por cada clase: cada sondeo vale hasta el siguiente (el último, hasta el fin). */
export function disponibilidad(sondeos, finMs) {
  const t = { DISPONIBLE: 0, NO_DISPONIBLE: 0, NO_VERIFICABLE: 0 };
  sondeos.forEach((s, i) => { t[s.clase] += Math.max(0, (sondeos[i + 1]?.t ?? finMs) - s.t); });
  const total = t.DISPONIBLE + t.NO_DISPONIBLE + t.NO_VERIFICABLE;
  return { segundos: Object.fromEntries(Object.entries(t).map(([k, x]) => [k, Math.round(x / 1000)])), total_s: Math.round(total / 1000), minima: total ? t.DISPONIBLE / total : null, maxima: total ? (t.DISPONIBLE + t.NO_VERIFICABLE) / total : null };
}
/** Intervalos consecutivos de una misma clase distinta de DISPONIBLE. */
export function intervalos(sondeos, finMs) {
  const out = [];
  sondeos.forEach((s, i) => {
    const hasta = sondeos[i + 1]?.t ?? finMs;
    const ultimo = out.at(-1);
    if (s.clase === 'DISPONIBLE') return;
    if (ultimo && ultimo.clase === s.clase && ultimo.hastaMs === s.t) { ultimo.hastaMs = hasta; ultimo.motivos.add(s.motivo); }
    else out.push({ clase: s.clase, desdeMs: s.t, hastaMs: hasta, motivos: new Set([s.motivo]) });
  });
  return out.map(x => ({ clase: x.clase, desde: new Date(x.desdeMs).toISOString(), hasta: new Date(x.hastaMs).toISOString(), duracion_s: Math.round((x.hastaMs - x.desdeMs) / 1000), motivos: [...x.motivos] }));
}
/** Veredicto propuesto con cotas: solo concluye si lo no verificable no puede cambiar el resultado. */
export function veredicto({ estado, d }) {
  if (estado !== 'CONCLUIDA' || d?.minima == null) return 'BLOQUEADO';
  if (d.minima >= OBJETIVO) return 'APROBADO';
  if (d.maxima < OBJETIVO) return 'RECHAZADO';
  return 'BLOQUEADO';
}

function local() {
  const checks = []; const ck = (n, x) => checks.push([n, !!x]);
  const v = fs.existsSync(ENV) ? leerEnv(fs.readFileSync(ENV, 'utf8')) : {};
  const fuente = fs.readFileSync(fileURLToPath(import.meta.url), 'utf8');
  const futuras = { ambiente: 'TEST', autorizacion: 'REF-DESARROLLO', efectos: ['notificacion-login', 'sesion-persistente'] };
  ck('Matriz: TC-M03-206 con objetivo ≥ 99,0 %', CASOS.join() === 'TC-M03-206' && OBJETIVO === 0.99);
  ck('Duración obligatoria y explícita', duracionS('24h') === 86400 && duracionS('') === null && duracionS('0h') === null);
  ck('Configuración compartida y QA_AUTORIZADO=NO', fs.existsSync(ENV) && v.QA_AUTORIZADO === 'NO');
  ck('Barrera rechaza la ejecución actual', !autorizar(v, { ambiente: 'TEST', autorizacion: '', efectos: [] }, { roles: ['ENG'] }).ok);
  ck('Barrera acepta condiciones futuras válidas', autorizar({ ...v, QA_AUTORIZADO: 'SI' }, futuras, { roles: ['ENG'] }).ok);
  ck('Barrera rechaza DEV', !autorizar({ ...v, QA_AUTORIZADO: 'SI' }, { ...futuras, ambiente: 'DEV' }, { roles: ['ENG'] }).ok);
  ck('Cuenta del Ingeniero resuelta', !!v.QA_ENG_EMAIL && !!(v.QA_ENG_PASSWORD || v.QA_COMMON_PASSWORD) && !!v.QA_SANDBOX_SECRET);
  ck('Cada sondeo en su propio RUN de sandbox y cerrado', /X-Test-Run-Id/.test(fuente) && /test-control\/runs\//.test(fuente));
  ck('Sondeos secuenciales (sin lanzamientos en paralelo)', !new RegExp(['Promise', 'all'].join('\\.')).test(fuente));
  ck('Veredicto por cotas: indeterminado → BLOQUEADO', veredicto({ estado: 'CONCLUIDA', d: { minima: 0.985, maxima: 0.995 } }) === 'BLOQUEADO' && veredicto({ estado: 'CONCLUIDA', d: { minima: 0.99, maxima: 1 } }) === 'APROBADO' && veredicto({ estado: 'CONCLUIDA', d: { minima: 0.9, maxima: 0.98 } }) === 'RECHAZADO' && veredicto({ estado: 'INTERRUMPIDA', d: { minima: 1, maxima: 1 } }) === 'BLOQUEADO');
  ck('Sintaxis ejecutor', spawnSync(process.execPath, ['--check', fileURLToPath(import.meta.url)]).status === 0);
  ck('Sintaxis librería', spawnSync(process.execPath, ['--check', path.join(DIR, 'monitoreo_lib.mjs')]).status === 0);
  ck('Sin carpetas RESULTADOS de construcción', !fs.existsSync(path.join(DIR, 'RESULTADOS')) && !fs.readdirSync(DIR).some(x => /^EvaluacionV\d+$/.test(x)));
  const secretos = [v.QA_SANDBOX_SECRET, v.QA_COMMON_PASSWORD, v.QA_ENG_PASSWORD].filter(x => x?.length > 4);
  ck('Sin secretos literales', [fileURLToPath(import.meta.url), path.join(DIR, 'monitoreo_lib.mjs')].every(f => !secretos.some(s => fs.readFileSync(f, 'utf8').includes(s))));
  ck('Pruebas unitarias locales', spawnSync(process.execPath, ['--test', path.join(DIR, 'validar_local_g106.mjs')], { encoding: 'utf8' }).status === 0);
  for (const [n, ok] of checks) console.log(`${ok ? 'OK' : 'FALLO'} ${n}`);
  console.log(`G106 local ${checks.filter(x => x[1]).length}/${checks.length}`);
  return checks.every(x => x[1]) ? 0 : 1;
}

async function ejecutar(a) {
  const v = fs.existsSync(ENV) ? leerEnv(fs.readFileSync(ENV, 'utf8')) : {};
  const gate = autorizar(v, a, { roles: ['ENG'] });
  const motivos = [...gate.motivos];
  if (!a.efectos.includes('sesion-persistente')) motivos.push('Falta aceptar sesion-persistente (una sesión del Ingeniero fuera del sandbox durante el periodo)');
  const total = duracionS(a.duracion), paso = a.intervalo ? duracionS(a.intervalo) : INTERVALO_S;
  if (!total) motivos.push('Indique --duracion explícita (p. ej. 24h): la matriz no fija el periodo');
  if (!paso || paso < LIMITE_RESPUESTA_S) motivos.push(`--intervalo debe ser de al menos ${LIMITE_RESPUESTA_S}s`);
  if (motivos.length) { console.error(`EJECUCIÓN NO AUTORIZADA: ${motivos.join('; ')}`); return 2; }
  if (!['evaluacion', 'reintento'].includes(a.tipo)) { console.error('Indique --tipo evaluacion|reintento'); return 2; }
  const n = version(DIR, a.tipo, a.version);
  const run = runId(GRUPO, n, sello());
  const base = carpetaResultados(DIR, n), out = path.join(base, run);
  fs.mkdirSync(base, { recursive: true }); fs.mkdirSync(out);
  const secretos = [v.QA_SANDBOX_SECRET, v.QA_COMMON_PASSWORD, v.QA_ENG_PASSWORD];
  let limpiar = redactor(secretos);
  const inicio = Date.now(), fin = inicio + total * 1000;
  const ev = { grupo: GRUPO, rf: 'RF-58', cu: 'CU04', casos: CASOS, version: n, run_id: run, estado: 'EN_CURSO', autorizacion: a.autorizacion, periodo: { inicio: new Date(inicio).toISOString(), fin_previsto: new Date(fin).toISOString(), duracion_s: total, intervalo_s: paso, limite_respuesta_s: LIMITE_RESPUESTA_S }, objetivo: OBJETIVO, datos: { actor: 'Ingeniero de Campo', sonda: 'GET /iot/monitoreo/dashboard?pagina=1&por_pagina=1, un RUN de sandbox por sondeo', clasificacion: 'DISPONIBLE / NO_DISPONIBLE / NO_VERIFICABLE' }, sondeos: [], renovaciones_sesion: 0, dependencias: [], bloqueos: {}, aserciones: [], sandbox: {} };
  const guardar = () => fs.writeFileSync(path.join(out, 'evidencia.json'), limpiar(JSON.stringify(ev, null, 2)));
  let detener = false; process.once('SIGINT', () => { detener = true; });
  let token = null;
  async function login() {
    const r = await fetchReal(`${gate.api}/sesiones/`, { method: 'POST', headers: { 'Content-Type': 'application/json', Accept: 'application/json' }, body: JSON.stringify({ correo_electronico: v.QA_ENG_EMAIL, contrasena: v.QA_ENG_PASSWORD || v.QA_COMMON_PASSWORD }), redirect: 'manual', signal: AbortSignal.timeout(LIMITE_RESPUESTA_S * 1000) });
    const d = await r.json().catch(() => null);
    token = r.status === 200 && d?.token ? d.token : null;
    if (token) { secretos.push(token); limpiar = redactor(secretos); }
    return r.status;
  }
  try {
    if (await login() !== 200 || !token) throw Error('No se pudo iniciar la sesión del Ingeniero para la sonda');
    for (let k = 0; !detener; k++) {
      const objetivoMs = inicio + k * paso * 1000;
      if (objetivoMs >= fin) break;
      await new Promise(r => setTimeout(r, Math.max(0, objetivoMs - Date.now())));
      const rid = `${run}-S${k}`, t = Date.now();
      let s;
      try {
        const r = await fetchReal(`${gate.api}/iot/monitoreo/dashboard?pagina=1&por_pagina=1`, { headers: { Accept: 'application/json', Authorization: `Bearer ${token}`, 'X-Test-Run-Id': rid, 'X-Sandbox-Secret': v.QA_SANDBOX_SECRET }, redirect: 'manual', signal: AbortSignal.timeout(LIMITE_RESPUESTA_S * 1000) });
        const cuerpo = await r.json().catch(() => null);
        s = { ...clasificar({ status: r.status, cuerpo, eco: r.headers.get('x-test-run-id'), run: rid }), http: r.status };
      } catch (error) { s = { ...clasificar({ error }), http: null }; }
      s.t = t; s.ms = Date.now() - t;
      try { const c = await fetchReal(`${gate.api}/test-control/runs/${rid}`, { method: 'DELETE', headers: { 'X-Sandbox-Secret': v.QA_SANDBOX_SECRET }, redirect: 'manual', signal: AbortSignal.timeout(LIMITE_RESPUESTA_S * 1000) }); s.cierre = c.status; } catch { s.cierre = null; }
      ev.sondeos.push({ ...s, fecha: new Date(t).toISOString() });
      if (s.http === 401) { ev.renovaciones_sesion++; await login().catch(() => null); }
      if (k % 10 === 0) guardar();
    }
    ev.estado = detener ? 'INTERRUMPIDA' : 'CONCLUIDA';
  } catch (e) { ev.estado = ev.sondeos.length ? 'INTERRUMPIDA' : 'ABORTADA_PREFLIGHT'; ev.dependencias.push(limpiar(e.message)); }
  finally {
    const finReal = Math.min(Date.now(), fin);
    const sondeos = ev.sondeos.map(s => ({ ...s }));
    const d = disponibilidad(sondeos, finReal);
    ev.periodo.fin_real = new Date(finReal).toISOString();
    ev.resultado = { ...d, minima_pct: d.minima == null ? null : Math.round(d.minima * 10000) / 100, maxima_pct: d.maxima == null ? null : Math.round(d.maxima * 10000) / 100, intervalos_no_disponibles: intervalos(sondeos, finReal).filter(x => x.clase === 'NO_DISPONIBLE'), intervalos_no_verificables: intervalos(sondeos, finReal).filter(x => x.clase === 'NO_VERIFICABLE') };
    ev.sandbox.rollback = ev.sondeos.every(s => s.cierre === 200);
    if (!ev.sandbox.rollback) ev.dependencias.push('Algún RUN de sondeo no confirmó su cierre: revisar que no haya quedado ninguna escritura (solo ultimo_acceso de la cuenta QA).');
    const propuesto = veredicto({ estado: ev.estado, d });
    ev.aserciones = [{ caso: 'TC-M03-206', tipo: propuesto === 'BLOQUEADO' ? 'PRE' : 'ASSERT', id: 'PERF-206-01', variante: null, nombre: `[TC-M03-206][ASSERT][PERF-206-01] disponibilidad ≥ 99,0 % (mínima ${ev.resultado.minima_pct} %, máxima ${ev.resultado.maxima_pct} %)`, ok: propuesto === 'APROBADO', evidencia: propuesto !== 'BLOQUEADO' }];
    ev.veredicto = { casos: { 'TC-M03-206': propuesto }, grupo: propuesto };
    ev.fin = new Date().toISOString(); guardar();
    fs.writeFileSync(path.join(out, nombreInforme(GRUPO, n)), limpiar(informe({ grupo: GRUPO, n, run, ev, casos: CASOS, extra: `\n## Disponibilidad\nPeriodo observado: ${ev.periodo.inicio} → ${ev.periodo.fin_real} (${d.total_s} s; previsto ${total} s) · ${ev.sondeos.length} sondeos cada ${paso} s.\n\nDisponible ${d.segundos.DISPONIBLE} s · No disponible ${d.segundos.NO_DISPONIBLE} s · No verificable ${d.segundos.NO_VERIFICABLE} s → disponibilidad entre **${ev.resultado.minima_pct} %** y **${ev.resultado.maxima_pct} %** (objetivo ≥ 99,0 %).\n\nIntervalos de indisponibilidad: ${JSON.stringify(ev.resultado.intervalos_no_disponibles)}\n\nIntervalos no verificables: ${JSON.stringify(ev.resultado.intervalos_no_verificables)}\n` })));
  }
  console.log(`${GRUPO}: ${ev.estado} — ${out}`); return ev.estado === 'CONCLUIDA' ? 0 : 4;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  let code; try { const a = argumentos(process.argv.slice(2)); code = a.modo === 'local' ? local() : await ejecutar(a); } catch (e) { console.error(e.message); code = 2; } process.exitCode = code;
}
