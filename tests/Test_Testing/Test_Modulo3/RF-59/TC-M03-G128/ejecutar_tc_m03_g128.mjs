#!/usr/bin/env node
// TC-M03-257 (RF-59 Precondición 7, OWASP API2): historial y exportación exigen un token válido.
// Seis combinaciones, todas HTTP 401 y sin exponer lecturas, estadísticas, alertas, metadatos ni archivos:
//   GET /iot/monitoreo/historial           sin token · token expirado · firma manipulada
//   GET /iot/monitoreo/historial/exportar  sin token · token expirado · firma manipulada
//
// Tokens:
// - Sin token: la petición no lleva cabecera Authorization.
// - Firma manipulada: un token VÁLIDO del propio RUN (login oficial del Ingeniero) al que se le cambia un bit
//   de la firma; cabecera y contenido quedan intactos, así que es estructuralmente válido.
// - Expirado: un JWT EMITIDO POR EL SISTEMA (login oficial), nunca fabricado ni con el reloj alterado.
//   `--preparar-token-expirable` (ejecución autorizada) inicia sesión dentro de un RUN de sandbox y guarda el
//   token FUERA del repositorio (~/.sigab-qa/TC-M03-G128/), con su huella, RUN y claims. El rollback del RUN
//   elimina la sesión, así que el token nunca es utilizable. `--ejecutar` lo usa solo cuando su `exp`
//   (más la tolerancia JWT_LEEWAY) ya pasó; si aún no expiró, esa variante queda BLOQUEADA hasta la fecha
//   indicada (la duración por defecto es JWT_EXPIRE_HOURS = 8 h). Válido para V1, V2, ...
// Controles [PRE]: con el token válido el historial responde 200 con lecturas del escenario (los 401 se
// deben a la autenticación, no a otra causa).
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import crypto from 'node:crypto';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import {
  leerEnv, autorizar, version, carpetaResultados, runId, nombreInforme, argumentos, newmanModulo, sello, serialQa, nombreSensor,
  sandbox, catalogos, fincaConAcceso, construirUnidad, correrNewman, redactor, informe,
  veredictoCasos, sintaxisColeccion, nombresDeTests, casoDeTexto, varianteDeTexto, tipoDeTexto, consultaTestigoDispositivo,
} from './monitoreo_lib.mjs';

export const GRUPO = 'TC-M03-G128';
export const CASOS = ['TC-M03-257'];
export const VARIANTES = ['HISTORIAL_SIN_TOKEN', 'HISTORIAL_EXPIRADO', 'HISTORIAL_FIRMA', 'EXPORTAR_SIN_TOKEN', 'EXPORTAR_EXPIRADO', 'EXPORTAR_FIRMA'];
export const REQUERIDAS = { 'TC-M03-257': VARIANTES.flatMap(x => [`API-257-01@${x}`, `API-257-02@${x}`]) };
export const LEEWAY_S = 30, MARGEN_S = 120;
export const ALMACEN = path.join(os.homedir(), '.sigab-qa', GRUPO, 'token_emitido.json');

const DIR = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(DIR, '../../../../..');
const ENV = path.join(ROOT, '.env.qa');
const COLLECTION = path.join(DIR, `${GRUPO}.postman_collection.json`);

/** Claims del JWT sin verificar la firma (solo para leer exp/sub/jti; la verificación es del servidor). */
export function claims(jwt) {
  const p = String(jwt || '').split('.');
  if (p.length !== 3) return null;
  try { return JSON.parse(Buffer.from(p[1], 'base64url').toString('utf8')); } catch { return null; }
}
/** Expirado con margen: exp + tolerancia del servidor + margen < ahora. */
export function expirado(jwt, ahoraMs = Date.now()) {
  const c = claims(jwt);
  return Number.isFinite(c?.exp) && c.exp * 1000 + (LEEWAY_S + MARGEN_S) * 1000 < ahoraMs;
}
export const disponibleDesde = jwt => { const c = claims(jwt); return Number.isFinite(c?.exp) ? new Date(c.exp * 1000 + (LEEWAY_S + MARGEN_S) * 1000).toISOString() : null; };
/** Firma manipulada: se invierte un bit del primer byte de la firma; cabecera y contenido no cambian. */
export function manipularFirma(jwt) {
  const [h, p, s] = String(jwt).split('.');
  const firma = Buffer.from(s || '', 'base64url');
  if (!h || !p || !firma.length) throw Error('JWT sin estructura para manipular la firma');
  firma[0] ^= 0x01;
  return `${h}.${p}.${firma.toString('base64url')}`;
}
export const huella = jwt => crypto.createHash('sha256').update(String(jwt)).digest('hex');
/** Token emitido guardado: procedencia (login oficial del Ingeniero), huella coherente y sub esperado. */
export function tokenUtilizable(guardado, idUsuario, ahoraMs = Date.now()) {
  const motivos = [];
  if (!guardado?.token) return { ok: false, motivos: ['no hay un token emitido guardado: ejecute --preparar-token-expirable'] };
  if (guardado.origen !== 'POST /sesiones/ (login oficial) dentro de un RUN de sandbox') motivos.push('procedencia no registrada como login oficial');
  if (huella(guardado.token) !== guardado.huella) motivos.push('la huella no corresponde al token guardado');
  const c = claims(guardado.token);
  if (!c?.jti || !Number.isFinite(c?.exp)) motivos.push('el token no tiene los claims del sistema (jti, exp)');
  if (Number(c?.sub) !== Number(idUsuario)) motivos.push('el token no pertenece a la cuenta QA del Ingeniero');
  if (!expirado(guardado.token, ahoraMs)) motivos.push(`el token aún no ha expirado: disponible desde ${disponibleDesde(guardado.token)}`);
  return { ok: !motivos.length, motivos };
}

function local() {
  const checks = []; const ck = (n, x) => checks.push([n, !!x]);
  const v = fs.existsSync(ENV) ? leerEnv(fs.readFileSync(ENV, 'utf8')) : {};
  const col = JSON.parse(fs.readFileSync(COLLECTION, 'utf8'));
  const texto = JSON.stringify(col);
  const fuente = fs.readFileSync(fileURLToPath(import.meta.url), 'utf8');
  const futuras = { ambiente: 'TEST', autorizacion: 'REF-DESARROLLO', efectos: ['notificacion-login'] };
  const pruebas = col.item.filter(i => varianteDeTexto(i.name));
  ck('Matriz: TC-M03-257 con seis combinaciones exactas', CASOS.join() === 'TC-M03-257' && pruebas.length === 6 && VARIANTES.every(x => pruebas.some(i => varianteDeTexto(i.name) === x)));
  ck('Ambos endpoints: historial y exportación, tres por cada uno', pruebas.filter(i => i.request.url.path.join('/') === 'iot/monitoreo/historial').length === 3 && pruebas.filter(i => i.request.url.path.join('/') === 'iot/monitoreo/historial/exportar').length === 3);
  ck('Sin token: sin cabecera Authorization', pruebas.filter(i => /SIN_TOKEN/.test(i.name)).every(i => !i.request.header.some(h => /authorization/i.test(h.key))));
  ck('Expirado y firma: token del RUN en la cabecera', pruebas.filter(i => /EXPIRADO/.test(i.name)).every(i => i.request.header.some(h => h.value === 'Bearer {{token_expirado}}')) && pruebas.filter(i => /FIRMA/.test(i.name)).every(i => i.request.header.some(h => h.value === 'Bearer {{token_firma}}')));
  ck('Aserciones 401 y sin exposición en las seis', pruebas.every(i => JSON.stringify(i).includes('[API-257-01]') && JSON.stringify(i).includes('[API-257-02]')));
  ck('Token expirado: emitido por el sistema y guardado fuera del repositorio (sin reloj alterado)', !ALMACEN.startsWith(ROOT) && /POST \/sesiones\//.test(fuente) && !new RegExp(['use', 'FakeTimers|cy\\.', 'clock|jwt\\.', 'sign'].join('')).test(fuente));
  ck('Configuración compartida y QA_AUTORIZADO=NO', fs.existsSync(ENV) && v.QA_AUTORIZADO === 'NO');
  ck('Barrera rechaza la ejecución actual', !autorizar(v, { ambiente: 'TEST', autorizacion: '', efectos: [] }).ok);
  ck('Barrera acepta condiciones futuras válidas', autorizar({ ...v, QA_AUTORIZADO: 'SI' }, futuras).ok);
  ck('Barrera rechaza DEV', !autorizar({ ...v, QA_AUTORIZADO: 'SI' }, { ...futuras, ambiente: 'DEV' }).ok);
  ck('Cuentas de preparación (Administrador) e Ingeniero resueltas', ['SETUP', 'ENG'].every(r => !!v[`QA_${r}_EMAIL`] && !!(v[`QA_${r}_PASSWORD`] || v.QA_COMMON_PASSWORD)) && !!v.QA_SANDBOX_SECRET);
  ck('Cada petición declara su caso', col.item.every(i => casoDeTexto(i.name)));
  ck('Cada test de la colección declara PRE, ASSERT o INFO', nombresDeTests(col).every(n => tipoDeTexto(n) !== null));
  const vars = new Set([...texto.matchAll(/\{\{([a-z0-9_]+)\}\}/g)].map(x => x[1]));
  ck('Variables Newman resueltas por el ejecutor', [...vars].every(x => ['base_url', 'run_id', 'sandbox_secret', 'token_valido', 'token_expirado', 'token_firma', 'fecha_inicio', 'fecha_fin', 'id_area', 'id_sensor'].includes(x)));
  ck('Barrera propia de Newman (nivel colección)', (col.event || []).some(e => e.listen === 'prerequest' && e.script.exec.join('\n').includes('BLOQUEO_G128')));
  try { sintaxisColeccion(col); ck('Sintaxis Postman (colección e ítems)', true); } catch { ck('Sintaxis Postman (colección e ítems)', false); }
  ck('Sintaxis ejecutor', spawnSync(process.execPath, ['--check', fileURLToPath(import.meta.url)]).status === 0);
  ck('Sintaxis librería', spawnSync(process.execPath, ['--check', path.join(DIR, 'monitoreo_lib.mjs')]).status === 0);
  ck('Testigo de aislamiento sin RLS', /FROM auditoria\.logs_dml/.test(consultaTestigoDispositivo('QAAUTO-G128-1')));
  ck('Sin peticiones concurrentes al sandbox', !new RegExp(['Promise', 'all'].join('\\.')).test(fuente));
  ck('Sin carpetas RESULTADOS de construcción', !fs.existsSync(path.join(DIR, 'RESULTADOS')) && !fs.readdirSync(DIR).some(x => /^EvaluacionV\d+$/.test(x)));
  const secretos = [v.QA_SANDBOX_SECRET, v.QA_COMMON_PASSWORD].filter(x => x?.length > 4);
  ck('Sin secretos ni JWT literales', [fileURLToPath(import.meta.url), COLLECTION, path.join(DIR, 'monitoreo_lib.mjs')].every(f => { const t = fs.readFileSync(f, 'utf8'); return !secretos.some(s => t.includes(s)) && !/eyJ[A-Za-z0-9_-]{10,}\.eyJ/.test(t); }));
  ck('Pruebas unitarias locales', spawnSync(process.execPath, ['--test', path.join(DIR, 'validar_local_g128.mjs')], { encoding: 'utf8' }).status === 0);
  try { newmanModulo(ROOT); ck('Newman disponible', true); } catch { ck('Newman disponible', false); }
  for (const [n, ok] of checks) console.log(`${ok ? 'OK' : 'FALLO'} ${n}`);
  console.log(`G128 local ${checks.filter(x => x[1]).length}/${checks.length}`);
  return checks.every(x => x[1]) ? 0 : 1;
}

function preparar(v, a) {
  const gate = autorizar(v, a);
  if (!gate.ok) return { gate, codigo: 2 };
  return { gate, codigo: 0 };
}
/** Emite y guarda (fuera del repositorio) un JWT oficial del Ingeniero que expirará por sí solo. */
async function prepararToken(a) {
  const v = fs.existsSync(ENV) ? leerEnv(fs.readFileSync(ENV, 'utf8')) : {};
  const { gate, codigo } = preparar(v, a);
  if (codigo) { console.error(`EJECUCIÓN NO AUTORIZADA: ${gate.motivos.join('; ')}`); return 2; }
  const run = `G128-TOKEN-${sello()}`;
  const sb = sandbox({ api: gate.api, run, secreto: v.QA_SANDBOX_SECRET });
  await sb.abrir();
  try {
    const eng = await sb.login(v.QA_ENG_EMAIL, v.QA_ENG_PASSWORD || v.QA_COMMON_PASSWORD, 'Ingeniero', /ingeniero/i);
    const c = claims(eng.token);
    fs.mkdirSync(path.dirname(ALMACEN), { recursive: true });
    fs.writeFileSync(ALMACEN, JSON.stringify({ token: eng.token, huella: huella(eng.token), origen: 'POST /sesiones/ (login oficial) dentro de un RUN de sandbox', run, emitido: new Date().toISOString(), claims: { sub: c?.sub, jti: c?.jti, iat: c?.iat, exp: c?.exp } }, null, 2), { mode: 0o600 });
    console.log(`Token emitido guardado fuera del repositorio (huella ${huella(eng.token).slice(0, 12)}…). Expira ${c?.exp ? new Date(c.exp * 1000).toISOString() : '—'}; utilizable para TC-M03-257 desde ${disponibleDesde(eng.token)}.`);
  } finally { await sb.req('DELETE', `/test-control/runs/${run}`, { control: true }); }
  return 0;
}

async function ejecutar(a) {
  const v = fs.existsSync(ENV) ? leerEnv(fs.readFileSync(ENV, 'utf8')) : {};
  const gate = autorizar(v, a);
  if (!gate.ok) { console.error(`EJECUCIÓN NO AUTORIZADA: ${gate.motivos.join('; ')}`); return 2; }
  if (!['evaluacion', 'reintento'].includes(a.tipo)) { console.error('Indique --tipo evaluacion|reintento'); return 2; }
  const n = version(DIR, a.tipo, a.version), newman = newmanModulo(ROOT);
  const marca = sello(), run = runId(GRUPO, n, marca);
  const base = carpetaResultados(DIR, n), out = path.join(base, run);
  fs.mkdirSync(base, { recursive: true }); fs.mkdirSync(out);
  const serial = serialQa(v, 'G128', marca, 'U');
  const ev = { grupo: GRUPO, rf: 'RF-59', cu: 'CU04', casos: CASOS, version: n, run_id: run, estado: 'EN_CURSO', fase: 'PREFLIGHT', autorizacion: a.autorizacion, dependencias: [], bloqueos: {}, aserciones: [], sandbox: {}, datos: {}, inicio: new Date().toISOString() };
  const secretos = [v.QA_SANDBOX_SECRET, v.QA_COMMON_PASSWORD, v.QA_SETUP_PASSWORD, v.QA_ENG_PASSWORD, serial];
  let limpiar = redactor(secretos);
  const guardar = () => fs.writeFileSync(path.join(out, 'evidencia.json'), limpiar(JSON.stringify(ev, null, 2)));
  const pre = (variante, nombre, ok, detalle) => ev.aserciones.push({ herramienta: 'Ejecutor', caso: 'TC-M03-257', tipo: 'PRE', id: null, variante, nombre: `[TC-M03-257][PRE]${variante ? `[V:${variante}]` : ''} ${nombre}`, ok: !!ok, evidencia: false, error: ok ? undefined : detalle });
  const sb = sandbox({ api: gate.api, run, secreto: v.QA_SANDBOX_SECRET });
  let abierto = false, dispositivo = false;
  try {
    await sb.abrir(); abierto = true;
    const setup = await sb.login(v.QA_SETUP_EMAIL, v.QA_SETUP_PASSWORD || v.QA_COMMON_PASSWORD, 'preparación', /administrador/i);
    const eng = await sb.login(v.QA_ENG_EMAIL, v.QA_ENG_PASSWORD || v.QA_COMMON_PASSWORD, 'Ingeniero', /ingeniero/i);
    secretos.push(setup.token, eng.token); limpiar = redactor(secretos);

    // ---- PREPARACIÓN: lecturas que no deben exponerse ---------------------------------------------
    ev.fase = 'PREPARACION';
    const cat = await catalogos(sb, setup.token);
    const finca = await fincaConAcceso(sb, { tokSetup: setup.token, tokActor: eng.token, idActor: eng.id, nombre: `QA Historial G Ciento Veintiocho ${marca}` });
    const unidad = await construirUnidad(sb, { tok: setup.token, cat, finca: finca.id, run, nombreUnidad: `QA G128 ${marca} U`, serial, nombres: [nombreSensor(`QA G128 ${marca}`, 'U', 1)], alCrearDispositivo: async () => { dispositivo = true; ev.sandbox.aislamiento = await sb.aislamiento(serial); } });
    const hoyUtc = new Date().toISOString().slice(0, 10);
    const s = unidad.sensores[0];
    const prueba = await sb.req('GET', `/iot/monitoreo/historial?fecha_inicio=${hoyUtc}&fecha_fin=${hoyUtc}&sensor_id=${s.id}`, { token: eng.token });
    const fechaFin = prueba.status !== 200 && /FECHA_FIN_FUTURA/.test(JSON.stringify(prueba.data ?? '')) ? new Date(Date.now() - 86400000).toISOString().slice(0, 10) : hoyUtc;
    const fechaInicio = new Date(Date.parse(fechaFin) - 2 * 86400000).toISOString().slice(0, 10);

    // ---- TOKENS -----------------------------------------------------------------------------------
    const tokenFirma = manipularFirma(eng.token);
    let guardado = null; try { guardado = JSON.parse(fs.readFileSync(ALMACEN, 'utf8')); } catch { /* sin token preparado */ }
    if (guardado?.token) { secretos.push(guardado.token); limpiar = redactor(secretos); }
    const util = tokenUtilizable(guardado, eng.id);
    for (const x of ['HISTORIAL_EXPIRADO', 'EXPORTAR_EXPIRADO']) pre(x, 'token JWT emitido por el sistema (login oficial) y ya expirado', util.ok, util.motivos.join('; '));
    if (!util.ok) ev.dependencias.push(`Token expirado no disponible: ${util.motivos.join('; ')}. Las variantes con token expirado quedan BLOQUEADAS; las demás se evalúan.`);
    secretos.push(tokenFirma); limpiar = redactor(secretos);
    ev.datos = { finca, id_infraestructura: unidad.id, id_sensor: s.id, periodo: { fecha_inicio: fechaInicio, fecha_fin: fechaFin }, token_firma: { derivado_de: 'token válido del Ingeniero en este RUN', cambio: 'un bit del primer byte de la firma', huella: huella(tokenFirma).slice(0, 16) }, token_expirado: guardado?.token ? { huella: huella(guardado.token).slice(0, 16), emitido: guardado.emitido, run_emision: guardado.run, exp: guardado.claims?.exp ? new Date(guardado.claims.exp * 1000).toISOString() : null, utilizable: util.ok } : null };

    // ---- SEIS COMBINACIONES (Newman) ------------------------------------------------------------------
    ev.fase = 'ESCENARIOS'; guardar();
    const vars = { base_url: gate.api, run_id: run, sandbox_secret: v.QA_SANDBOX_SECRET, autorizado_run: 'SI', token_valido: eng.token, token_expirado: util.ok ? guardado.token : '', token_firma: tokenFirma, fecha_inicio: fechaInicio, fecha_fin: fechaFin, id_area: unidad.id, id_sensor: s.id, nombre_sensor: s.nombre, nombre_unidad: unidad.nombre };
    const nw = await correrNewman(newman, JSON.parse(fs.readFileSync(COLLECTION, 'utf8')), vars, { limpiar });
    ev.aserciones.push(...nw.aserciones); ev.respuestas = nw.muestras;
    for (const e of nw.errores) { ev.dependencias.push(e.mensaje); (ev.bloqueos['TC-M03-257'] ??= []).push(e.mensaje); }
    ev.estado = 'CONCLUIDA';
  } catch (e) { ev.estado = ev.fase === 'ESCENARIOS' ? 'INTERRUMPIDA' : 'ABORTADA_PREFLIGHT'; ev.dependencias.push(limpiar(e.message)); }
  finally {
    try {
      if (abierto) {
        const c = await sb.cerrar(dispositivo ? serial : null);
        ev.sandbox.cierre = c; ev.sandbox.rollback = c.rollback;
        if (dispositivo && c.sonda_posterior === null) ev.dependencias.push('Rollback no confirmable: testigo auditoria.logs_dml no consultable.');
      }
    } catch (e) { ev.sandbox.rollback = false; ev.dependencias.push(limpiar(e.message)); }
    ev.veredicto = veredictoCasos({ casos: CASOS, requeridas: REQUERIDAS, estado: ev.estado, rollback: !!ev.sandbox.rollback, aserciones: ev.aserciones, bloqueos: ev.bloqueos });
    ev.fin = new Date().toISOString(); guardar();
    fs.writeFileSync(path.join(out, nombreInforme(GRUPO, n)), limpiar(informe({ grupo: GRUPO, n, run, ev, casos: CASOS, extra: `\nLos tokens no se registran: solo huellas SHA-256 parciales y claims de fecha.\n` })));
  }
  console.log(`${GRUPO}: ${ev.estado} — ${out}`); return ev.estado === 'CONCLUIDA' ? 0 : 4;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  let code;
  try {
    const argv = process.argv.slice(2);
    const prep = argv.includes('--preparar-token-expirable');
    const a = argumentos(argv.filter(x => x !== '--preparar-token-expirable'));
    code = prep ? await prepararToken(a) : a.modo === 'local' ? local() : await ejecutar(a);
  } catch (e) { console.error(e.message); code = 2; }
  process.exitCode = code;
}
