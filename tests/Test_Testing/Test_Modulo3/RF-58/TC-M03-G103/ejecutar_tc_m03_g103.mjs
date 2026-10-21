#!/usr/bin/env node
// TC-M03-203 (RF-58 / RNF-04): tiempo de carga inicial de la vista con 50 sensores activos < 1 s.
//
// Escenario CONSTRUIDO en el sandbox con APIs oficiales: una unidad productiva QA con exactamente
// 50 sensores activos, cada uno con una lectura válida. La medición es la de la petición con la que
// la vista carga sus datos (GET /iot/monitoreo/dashboard filtrado por la unidad, por_pagina=50),
// ejecutada con Newman de forma secuencial.
//
// - La primera petición es la "carga inicial" y es la única decisoria (PERF-203-01).
// - Las repeticiones y sus estadísticos se registran como INFO para documentar la reproducibilidad.
// - Las condiciones (volumen, cliente, destino, sandbox, latencia de referencia) quedan en la evidencia.
//
// La matriz propone k6, que no está instalado ni forma parte de las herramientas del paquete QA.
// Newman mide el mismo tiempo de respuesta HTTP con un único cliente secuencial.
// REQUIERE DECISIÓN QA si se exige k6, un percentil en lugar de la primera carga, o el tiempo de
// renderizado del navegador.
import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import {
  leerEnv, autorizar, version, carpetaResultados, runId, nombreInforme, argumentos, newmanModulo, sello, serialQa, nombreSensor,
  sandbox, catalogos, fincaConAcceso, construirUnidad, estadosActualesCompletos, correrNewman, redactor, informe, estadisticos,
  veredictoCasos, sintaxisColeccion, nombresDeTests, casoDeTexto, varianteDeTexto, tipoDeTexto, consultaTestigoDispositivo, consultaEstadosActuales,
} from './monitoreo_lib.mjs';

export const GRUPO = 'TC-M03-G103';
export const CASOS = ['TC-M03-203'];
export const SENSORES = 50;
export const UMBRAL_MS = 1000;
/** Peticiones secuenciales: la primera es la carga inicial; el resto, repeticiones INFO. */
export const MUESTRAS = 10;
export const REQUERIDAS = { 'TC-M03-203': ['PERF-203-01@U50'] };

const DIR = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(DIR, '../../../../..');
const ENV = path.join(ROOT, '.env.qa');
const COLLECTION = path.join(DIR, `${GRUPO}.postman_collection.json`);

export const nombresUnidad = prefijo => Array.from({ length: SENSORES }, (_, i) => nombreSensor(prefijo, 'U50', i + 1));
/** Resumen de la medición: primera carga (decisoria) y estadísticos de todas las muestras. */
export function resumenMedicion(muestras) {
  const ordenadas = muestras.slice().sort((a, b) => a.iteracion - b.iteracion);
  const primera = ordenadas[0] ?? null;
  return { carga_inicial_ms: primera?.ms ?? null, http_inicial: primera?.http ?? null, bytes_respuesta: primera?.bytes ?? null, umbral_ms: UMBRAL_MS, muestras: ordenadas.map(m => m.ms), estadisticos: estadisticos(ordenadas.map(m => m.ms)) };
}

function local() {
  const checks = []; const ck = (n, x) => checks.push([n, !!x]);
  const v = fs.existsSync(ENV) ? leerEnv(fs.readFileSync(ENV, 'utf8')) : {};
  const col = JSON.parse(fs.readFileSync(COLLECTION, 'utf8'));
  const texto = JSON.stringify(col);
  const fuente = fs.readFileSync(fileURLToPath(import.meta.url), 'utf8');
  const futuras = { ambiente: 'TEST', autorizacion: 'REF-DESARROLLO', efectos: ['notificacion-login'] };
  ck('Matriz: TC-M03-203', CASOS.join() === 'TC-M03-203');
  ck('Criterio de la matriz: 50 sensores y menos de 1000 ms', SENSORES === 50 && UMBRAL_MS === 1000 && texto.includes('< umbral'));
  ck('Configuración compartida y QA_AUTORIZADO=NO', fs.existsSync(ENV) && v.QA_AUTORIZADO === 'NO');
  ck('Barrera rechaza la ejecución actual', !autorizar(v, { ambiente: 'TEST', autorizacion: '', efectos: [] }).ok);
  ck('Barrera acepta condiciones futuras válidas', autorizar({ ...v, QA_AUTORIZADO: 'SI' }, futuras).ok);
  ck('Barrera rechaza DEV', !autorizar({ ...v, QA_AUTORIZADO: 'SI' }, { ...futuras, ambiente: 'DEV' }).ok);
  ck('Cuentas de preparación (Administrador) e Ingeniero resueltas', ['SETUP', 'ENG'].every(r => !!v[`QA_${r}_EMAIL`] && !!(v[`QA_${r}_PASSWORD`] || v.QA_COMMON_PASSWORD)) && !!v.QA_SANDBOX_SECRET);
  ck('Serial QA dentro del formato (prefijo automático si falta)', /-G103-/.test(serialQa(v, 'G103', '20261017000000', 'U50')));
  ck('Escenario: exactamente 50 sensores con nombres únicos', new Set(nombresUnidad('QA G103 X')).size === 50);
  ck('Colección Postman v2.1 con una petición medida', /v2\.1\.0/.test(col.info?.schema || '') && col.item?.length === 1);
  ck('Aserción decisoria PERF-203-01 en la colección', texto.includes('[PERF-203-01]'));
  ck('Cada petición declara caso y unidad', col.item.every(i => casoDeTexto(i.name) && varianteDeTexto(i.name)));
  ck('Cada test de la colección declara PRE, ASSERT o INFO', nombresDeTests(col).every(n => tipoDeTexto(n) !== null));
  const vars = new Set([...texto.matchAll(/\{\{([a-z0-9_]+)\}\}/g)].map(x => x[1]));
  ck('Variables Newman resueltas por el ejecutor', [...vars].every(x => ['base_url', 'run_id', 'sandbox_secret', 'token', 'id_u50'].includes(x)));
  ck('Barrera propia de Newman (nivel colección)', (col.event || []).some(e => e.listen === 'prerequest' && e.script.exec.join('\n').includes('BLOQUEO_G103')));
  try { sintaxisColeccion(col); ck('Sintaxis Postman (colección e ítems)', true); } catch { ck('Sintaxis Postman (colección e ítems)', false); }
  ck('Sintaxis ejecutor', spawnSync(process.execPath, ['--check', fileURLToPath(import.meta.url)]).status === 0);
  ck('Sintaxis librería', spawnSync(process.execPath, ['--check', path.join(DIR, 'monitoreo_lib.mjs')]).status === 0);
  ck('Sin Cypress (la matriz no pide interfaz) ni relojes falsos', !fs.readdirSync(DIR).some(f => f.endsWith('.cy.js')) && !new RegExp(['cy', 'clock|use', 'FakeTimers'].join('.')).test(fuente));
  ck('Testigo de aislamiento sin RLS', /FROM auditoria\.logs_dml/.test(consultaTestigoDispositivo('QAAUTO-G103-1')) && /FROM modulo3\.estados_actuales_sensores/.test(consultaEstadosActuales([1])));
  ck('Sin peticiones concurrentes al sandbox', !/Promise\.all/.test(fuente));
  ck('Veredicto: ASSERT con evidencia rechaza; PRE de la vista lo invalida', veredictoCasos({ casos: CASOS, requeridas: REQUERIDAS, estado: 'CONCLUIDA', rollback: true, aserciones: [{ caso: 'TC-M03-203', tipo: 'ASSERT', id: 'PERF-203-01', variante: 'U50', ok: false, evidencia: true }] }).grupo === 'RECHAZADO'
    && veredictoCasos({ casos: CASOS, requeridas: REQUERIDAS, estado: 'CONCLUIDA', rollback: true, aserciones: [{ caso: 'TC-M03-203', tipo: 'PRE', variante: 'U50', ok: false }, { caso: 'TC-M03-203', tipo: 'ASSERT', id: 'PERF-203-01', variante: 'U50', ok: false, evidencia: true }] }).grupo === 'BLOQUEADO');
  ck('Sin carpetas RESULTADOS de construcción', !fs.existsSync(path.join(DIR, 'RESULTADOS')) && !fs.readdirSync(DIR).some(x => /^EvaluacionV\d+$/.test(x)));
  const secretos = [v.QA_SANDBOX_SECRET, v.QA_COMMON_PASSWORD, v.QA_SETUP_PASSWORD, v.QA_ENG_PASSWORD].filter(x => x?.length > 4);
  ck('Sin secretos literales', [fileURLToPath(import.meta.url), COLLECTION, path.join(DIR, 'monitoreo_lib.mjs')].every(f => !secretos.some(s => fs.readFileSync(f, 'utf8').includes(s))));
  ck('Pruebas unitarias locales', spawnSync(process.execPath, ['--test', path.join(DIR, 'validar_local_g103.mjs')], { encoding: 'utf8' }).status === 0);
  try { newmanModulo(ROOT); ck('Newman disponible', true); } catch { ck('Newman disponible', false); }
  for (const [n, ok] of checks) console.log(`${ok ? 'OK' : 'FALLO'} ${n}`);
  console.log(`G103 local ${checks.filter(x => x[1]).length}/${checks.length}`);
  return checks.every(x => x[1]) ? 0 : 1;
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
  const serial = serialQa(v, 'G103', marca, 'U50');
  const prefijo = `QA G103 ${marca}`;
  const ev = { grupo: GRUPO, rf: 'RF-58', rnf: 'RNF-04', cu: 'CU04', casos: CASOS, version: n, run_id: run, estado: 'EN_CURSO', fase: 'PREFLIGHT', autorizacion: a.autorizacion, actor_dashboard: 'Ingeniero de Campo', dependencias: [], bloqueos: {}, aserciones: [], sandbox: {}, datos: {}, inicio: new Date().toISOString() };
  const secretos = [v.QA_SANDBOX_SECRET, v.QA_COMMON_PASSWORD, v.QA_SETUP_PASSWORD, v.QA_ENG_PASSWORD, serial];
  let limpiar = redactor(secretos);
  const guardar = () => fs.writeFileSync(path.join(out, 'evidencia.json'), limpiar(JSON.stringify(ev, null, 2)));
  const pre = (nombre, ok, detalle, variante = 'U50') => ev.aserciones.push({ herramienta: 'Ejecutor', caso: 'TC-M03-203', tipo: 'PRE', id: null, variante, nombre: `[TC-M03-203][PRE]${variante ? `[V:${variante}]` : ''} ${nombre}`, ok, evidencia: false, error: ok ? undefined : detalle });
  const sb = sandbox({ api: gate.api, run, secreto: v.QA_SANDBOX_SECRET });
  let abierto = false, dispositivo = false;
  try {
    await sb.abrir(); abierto = true;
    const setup = await sb.login(v.QA_SETUP_EMAIL, v.QA_SETUP_PASSWORD || v.QA_COMMON_PASSWORD, 'preparación', /administrador/i);
    const eng = await sb.login(v.QA_ENG_EMAIL, v.QA_ENG_PASSWORD || v.QA_COMMON_PASSWORD, 'Ingeniero', /ingeniero/i);
    secretos.push(setup.token, eng.token); limpiar = redactor(secretos);

    // ---- PREPARACIÓN: unidad QA con exactamente 50 sensores activos -----------------------
    ev.fase = 'PREPARACION';
    const cat = await catalogos(sb, setup.token);
    const finca = await fincaConAcceso(sb, { tokSetup: setup.token, tokActor: eng.token, idActor: eng.id, nombre: `QA Monitoreo G Ciento Tres ${marca}` });
    ev.datos.finca = finca;
    const unidad = await construirUnidad(sb, {
      tok: setup.token, cat, finca: finca.id, run, nombreUnidad: `${prefijo} U50`, serial, nombres: nombresUnidad(prefijo),
      alCrearDispositivo: async () => { dispositivo = true; ev.sandbox.aislamiento = await sb.aislamiento(serial); },
    });
    ev.datos.U50 = { id_infraestructura: unidad.id, nombre: unidad.nombre, sensores: unidad.sensores.length, lecturas_por_sensor: 1, origen: 'construida en el RUN' };
    const alcance = await sb.req('GET', `/configuracion/infraestructuras/${unidad.id}`, { token: eng.token });
    pre('el Ingeniero tiene alcance sobre la unidad', alcance.status === 200, `HTTP ${alcance.status}`);
    const e = await estadosActualesCompletos(sb, unidad);
    ev.datos.U50.estados_actuales = e;
    pre('los 50 sensores tienen estado actual en el sandbox', e.ok, e.encontrados === null ? 'no verificable (consulta fallida)' : `encontrados ${e.encontrados} de 50 (posible efecto de DEV-05: estado actual fuera de la transacción del RUN)`);
    // Latencia de referencia de la red (petición mínima autenticada), para documentar condiciones.
    const t0 = performance.now(); const ref = await sb.req('GET', '/usuarios/me', { token: eng.token }); const latencia = Math.round(performance.now() - t0);

    // ---- MEDICIÓN: Newman, secuencial -------------------------------------------------------
    ev.fase = 'ESCENARIOS'; guardar();
    const vars = { base_url: gate.api, run_id: run, sandbox_secret: v.QA_SANDBOX_SECRET, autorizado_run: 'SI', token: eng.token, id_u50: unidad.id, ids_u50: JSON.stringify(unidad.sensores.map(s => Number(s.id))), umbral_ms: UMBRAL_MS };
    const nw = await correrNewman(newman, JSON.parse(fs.readFileSync(COLLECTION, 'utf8')), vars, { iteraciones: MUESTRAS, limpiar });
    ev.aserciones.push(...nw.aserciones);
    for (const x of nw.errores) { ev.dependencias.push(x.mensaje); (ev.bloqueos['TC-M03-203'] ??= []).push(x.mensaje); }
    ev.medicion = {
      ...resumenMedicion(nw.muestras),
      condiciones: {
        fecha: new Date().toISOString(), destino: new URL(gate.api).host, cliente: `Newman (${MUESTRAS} peticiones secuenciales, una por iteración); Node ${process.version}`,
        peticion: 'GET /iot/monitoreo/dashboard?id_infraestructura=<unidad>&pagina=1&por_pagina=50 (la misma que hace la vista al filtrar por la unidad)',
        volumen: '1 unidad, 50 sensores activos, 1 lectura válida por sensor', actor: 'Ingeniero de Campo',
        sandbox: 'activo: las peticiones del RUN se atienden en una sola sesión transaccional sin confirmar (condición de la medición, no del uso real)',
        conexion: 'la primera muestra incluye el establecimiento de la conexión del cliente Newman',
        latencia_referencia_ms: ref.status === 200 ? latencia : null,
      },
    };
    ev.estado = 'CONCLUIDA';
  } catch (x) { ev.estado = ev.fase === 'ESCENARIOS' ? 'INTERRUMPIDA' : 'ABORTADA_PREFLIGHT'; ev.dependencias.push(limpiar(x.message)); }
  finally {
    try {
      if (abierto) {
        const c = await sb.cerrar(dispositivo ? serial : null);
        ev.sandbox.cierre = c; ev.sandbox.rollback = c.rollback;
        if (dispositivo && c.sonda_posterior === null) ev.dependencias.push('Rollback no confirmable: testigo auditoria.logs_dml no consultable.');
      }
    } catch (x) { ev.sandbox.rollback = false; ev.dependencias.push(limpiar(x.message)); }
    ev.veredicto = veredictoCasos({ casos: CASOS, requeridas: REQUERIDAS, estado: ev.estado, rollback: !!ev.sandbox.rollback, aserciones: ev.aserciones, bloqueos: ev.bloqueos });
    ev.fin = new Date().toISOString(); guardar();
    const m = ev.medicion;
    fs.writeFileSync(path.join(out, nombreInforme(GRUPO, n)), limpiar(informe({ grupo: GRUPO, n, run, ev, casos: CASOS, extra: m ? `\n## Medición (RNF-04)\nCarga inicial: **${m.carga_inicial_ms} ms** (umbral < ${UMBRAL_MS} ms, HTTP ${m.http_inicial}, ${m.bytes_respuesta} bytes). Repeticiones (INFO): ${JSON.stringify(m.estadisticos)}.\n\nCondiciones: ${JSON.stringify(m.condiciones)}\n` : '' })));
  }
  console.log(`${GRUPO}: ${ev.estado} — ${out}`); return ev.estado === 'CONCLUIDA' ? 0 : 4;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  let code; try { const a = argumentos(process.argv.slice(2)); code = a.modo === 'local' ? local() : await ejecutar(a); } catch (e) { console.error(e.message); code = 2; } process.exitCode = code;
}
