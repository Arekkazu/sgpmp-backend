#!/usr/bin/env node
// TC-M03-201, 202 y 213 (RF-58 CA-17 / FA-07 / Restricción 9): límite de 50 sensores por vista,
// soporte de hasta 200 sensores por unidad mediante segmentación y resistencia del límite ante
// tamaños excesivos (OWASP API4).
//
// Escenario CONSTRUIDO en el sandbox con APIs oficiales: tres unidades productivas QA con 50, 51 y
// 200 sensores activos (cada sensor registrado, asociado, calibrado y con una lectura válida, que
// es lo que lo hace aparecer en el dashboard). Un dispositivo sin gateway por unidad: sin MQTT y
// dentro del límite de registro de dispositivos (10/min).
//
// Actor del dashboard: Ingeniero de Campo (CU04). La matriz no fija actor y el Productor no tiene
// lectura sobre modulo9.sensores por RLS, por lo que no vería sensores en ninguna vista.
import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import {
  leerEnv, autorizar, version, carpetaResultados, runId, nombreInforme, argumentos, newmanModulo, cypressModulo, sello, serialQa, nombreSensor,
  sandbox, catalogos, fincaConAcceso, construirUnidad, estadosActualesCompletos, correrNewman, correrCypress, redactor, informe,
  veredictoCasos, sintaxisColeccion, nombresDeTests, casoDeTexto, idDeTexto, varianteDeTexto, tipoDeTexto, consultaTestigoDispositivo, consultaEstadosActuales, POR_VISTA,
  opcionesCypress, aislamientoVerificacion, verificarDescubrimiento,
} from './monitoreo_lib.mjs';

export const GRUPO = 'TC-M03-G102';
export const CASOS = ['TC-M03-201', 'TC-M03-202', 'TC-M03-213'];
/** Unidades del escenario: variante → número de sensores activos. */
export const UNIDADES = { U50: 50, U51: 51, U200: 200 };
/** Aserciones requeridas por caso (id@variante). */
export const REQUERIDAS = {
  'TC-M03-201': ['API-201-01@U50', 'API-201-02@U50', 'API-201-03@U51', 'API-201-04@U51', 'API-201-05@U51', 'UI-201-01@U50', 'UI-201-02@U51', 'UI-201-03@U51'],
  'TC-M03-202': ['API-202-01@U200', 'API-202-02@U200', 'API-202-03@U200', 'UI-202-01@U200', 'UI-202-02@U200'],
  'TC-M03-213': ['API-213-01@U200', 'API-213-02@U200', 'API-213-03@U200'],
};
/** Casos que dependen de cada unidad (para invalidar solo lo afectado si su preparación falla). */
export const CASOS_POR_UNIDAD = { U50: ['TC-M03-201'], U51: ['TC-M03-201'], U200: ['TC-M03-202', 'TC-M03-213'] };
export const TAMANOS_EXCESIVOS = [51, 500, 100000];

const DIR = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(DIR, '../../../../..');
const ENV = path.join(ROOT, '.env.qa');
const COLLECTION = path.join(DIR, `${GRUPO}.postman_collection.json`);
const SPEC = path.join(DIR, 'tc_m03_g102.cy.js');
const VERIFICACION = path.join(DIR, 'cypress.verificacion.config.cjs');

/** Nombres de los sensores de una unidad (también es el patrón que Cypress busca en pantalla). */
export const nombresUnidad = (prefijo, u) => Array.from({ length: UNIDADES[u] }, (_, i) => nombreSensor(prefijo, u, i + 1));

function local() {
  const checks = []; const ck = (n, x) => checks.push([n, !!x]);
  const v = fs.existsSync(ENV) ? leerEnv(fs.readFileSync(ENV, 'utf8')) : {};
  const col = JSON.parse(fs.readFileSync(COLLECTION, 'utf8'));
  const texto = JSON.stringify(col);
  const spec = fs.readFileSync(SPEC, 'utf8');
  const fuente = fs.readFileSync(fileURLToPath(import.meta.url), 'utf8');
  const futuras = { ambiente: 'TEST', autorizacion: 'REF-DESARROLLO', efectos: ['notificacion-login'] };
  ck('Matriz: TC-M03-201, 202 y 213', CASOS.join() === 'TC-M03-201,TC-M03-202,TC-M03-213');
  ck('Cada aserción requerida pertenece a su caso', Object.entries(REQUERIDAS).every(([c, ids]) => ids.every(k => `TC-M03-${k.slice(k.indexOf('-') + 1, k.indexOf('-') + 4)}` === c)));
  ck('Configuración compartida y QA_AUTORIZADO=NO', fs.existsSync(ENV) && v.QA_AUTORIZADO === 'NO');
  ck('Barrera rechaza la ejecución actual', !autorizar(v, { ambiente: 'TEST', autorizacion: '', efectos: [] }, { frontend: true }).ok);
  ck('Barrera acepta condiciones futuras válidas', autorizar({ ...v, QA_AUTORIZADO: 'SI' }, futuras, { frontend: true }).ok);
  ck('Barrera rechaza DEV', !autorizar({ ...v, QA_AUTORIZADO: 'SI' }, { ...futuras, ambiente: 'DEV' }, { frontend: true }).ok);
  ck('Cuentas de preparación (Administrador) e Ingeniero resueltas', ['SETUP', 'ENG'].every(r => !!v[`QA_${r}_EMAIL`] && !!(v[`QA_${r}_PASSWORD`] || v.QA_COMMON_PASSWORD)) && !!v.QA_SANDBOX_SECRET);
  ck('Seriales QA dentro del formato (prefijo automático si falta)', Object.keys(UNIDADES).every(u => /-G102-/.test(serialQa(v, 'G102', '20261017000000', u))));
  ck('Escenario: 50, 51 y 200 sensores con nombres únicos', Object.keys(UNIDADES).every(u => new Set(nombresUnidad('QA G102 X', u)).size === UNIDADES[u]));
  ck('Colección Postman v2.1', /v2\.1\.0/.test(col.info?.schema || '') && col.item?.length === 8);
  ck('Aserciones API requeridas en la colección y UI en el spec', Object.values(REQUERIDAS).flat().every(k => { const id = k.split('@')[0]; return id.startsWith('UI') ? spec.includes(`[${id}]`) : texto.includes(`[${id}]`); }));
  ck('Cada petición declara caso y unidad', col.item.every(i => casoDeTexto(i.name) && varianteDeTexto(i.name)));
  ck('Cada test de la colección declara PRE, ASSERT o INFO', nombresDeTests(col).every(n => tipoDeTexto(n) !== null));
  ck('Tamaños excesivos de la matriz (51, 500, 100000)', TAMANOS_EXCESIVOS.every(t => texto.includes(`por_pagina=${t}`)) && texto.includes('por_pagina=50'));
  const vars = new Set([...texto.matchAll(/\{\{([a-z0-9_]+)\}\}/g)].map(x => x[1]));
  ck('Variables Newman resueltas por el ejecutor', [...vars].every(x => ['base_url', 'run_id', 'sandbox_secret', 'token', 'id_u50', 'id_u51', 'id_u200', 'pagina_u200'].includes(x)));
  const envCypress = new Set([...spec.matchAll(/env\('([A-Z_]+)'\)/g)].map(x => x[1]));
  ck('Variables Cypress resueltas por el ejecutor', [...envCypress].every(x => ['AUTORIZADO_RUN', 'API_BASE', 'RUN_ID', 'SANDBOX_SECRET', 'EMAIL', 'PASSWORD', 'UNIDADES'].includes(x)));
  ck('Barrera propia de Newman (nivel colección)', (col.event || []).some(e => e.listen === 'prerequest' && e.script.exec.join('\n').includes('BLOQUEO_G102')));
  try { sintaxisColeccion(col); ck('Sintaxis Postman (colección e ítems)', true); } catch { ck('Sintaxis Postman (colección e ítems)', false); }
  ck('Sintaxis ejecutor', spawnSync(process.execPath, ['--check', fileURLToPath(import.meta.url)]).status === 0);
  ck('Sintaxis librería', spawnSync(process.execPath, ['--check', path.join(DIR, 'monitoreo_lib.mjs')]).status === 0);
  ck('Sintaxis Cypress', spawnSync(process.execPath, ['--check', SPEC]).status === 0);
  const oc = opcionesCypress({ root: ROOT, spec: SPEC, front: 'https://front.test.example', out: DIR, env: { API_BASE: 'https://api.test.example' } });
  ck('Cypress: anulaciones en e2e, baseUrl = frontend (distinto del API), spec relativo a la raíz y sin reporter de archivos', oc.config.baseUrl === undefined && oc.config.e2e.baseUrl === 'https://front.test.example' && oc.env.API_BASE !== oc.config.e2e.baseUrl && path.resolve(ROOT, oc.config.e2e.specPattern) === SPEC && oc.reporter === 'spec' && oc.config.e2e.reporter === 'spec');
  ck('Barrera: frontend y API no pueden ser el mismo destino', !autorizar({ ...v, QA_AUTORIZADO: 'SI', SIGAB_FRONT_TEST_URL: v.SIGAB_API_TEST_BASE, SIGAB_FRONT_URL: '' }, futuras, { frontend: true }).ok);
  const ov = opcionesCypress({ root: ROOT, spec: SPEC, front: null, out: null, env: {}, configFile: path.relative(ROOT, VERIFICACION).split(path.sep).join('/') });
  ck('Verificación local aislada: configuración de loopback y salida bloqueada (sin el cypress.config.cjs raíz)', aislamientoVerificacion({ root: ROOT, configVerificacion: VERIFICACION, opciones: ov, entorno: { HTTP_PROXY: 'http://127.0.0.1:9', HTTPS_PROXY: 'http://127.0.0.1:9' } }).length === 0
    && aislamientoVerificacion({ root: ROOT, configVerificacion: VERIFICACION, opciones: { ...ov, configFile: undefined }, entorno: { HTTP_PROXY: 'http://127.0.0.1:9', HTTPS_PROXY: 'http://127.0.0.1:9' } }).length > 0);
  ck('Barrera propia de Cypress y sin respuestas simuladas', spec.includes('BLOQUEO_G102') && !/req\.reply|cy\.stub|cy\.fixture|cy\.clock/.test(spec));
  ck('Testigo de aislamiento sin RLS', /FROM auditoria\.logs_dml/.test(consultaTestigoDispositivo('QAAUTO-G102-1')) && /FROM modulo3\.estados_actuales_sensores/.test(consultaEstadosActuales([1])));
  ck('Sin peticiones concurrentes al sandbox', !/Promise\.all/.test(fuente));
  ck('Veredicto: ASSERT con evidencia rechaza; PRE de la unidad lo invalida', veredictoCasos({ casos: CASOS, requeridas: REQUERIDAS, estado: 'CONCLUIDA', rollback: true, aserciones: [{ caso: 'TC-M03-213', tipo: 'ASSERT', id: 'API-213-01', variante: 'U200', ok: false, evidencia: true }] }).casos['TC-M03-213'] === 'RECHAZADO'
    && veredictoCasos({ casos: CASOS, requeridas: REQUERIDAS, estado: 'CONCLUIDA', rollback: true, aserciones: [{ caso: 'TC-M03-213', tipo: 'PRE', variante: 'U200', ok: false }, { caso: 'TC-M03-213', tipo: 'ASSERT', id: 'API-213-01', variante: 'U200', ok: false, evidencia: true }] }).casos['TC-M03-213'] === 'BLOQUEADO');
  ck('Sin carpetas RESULTADOS de construcción', !fs.existsSync(path.join(DIR, 'RESULTADOS')) && !fs.readdirSync(DIR).some(x => /^EvaluacionV\d+$/.test(x)));
  const secretos = [v.QA_SANDBOX_SECRET, v.QA_COMMON_PASSWORD, v.QA_SETUP_PASSWORD, v.QA_ENG_PASSWORD].filter(x => x?.length > 4);
  ck('Sin secretos literales', [fileURLToPath(import.meta.url), COLLECTION, SPEC, path.join(DIR, 'monitoreo_lib.mjs')].every(f => !secretos.some(s => fs.readFileSync(f, 'utf8').includes(s))));
  ck('Pruebas unitarias locales', spawnSync(process.execPath, ['--test', path.join(DIR, 'validar_local_g102.mjs')], { encoding: 'utf8' }).status === 0);
  try { newmanModulo(ROOT); ck('Newman disponible', true); } catch { ck('Newman disponible', false); }
  try { cypressModulo(ROOT); ck('Cypress disponible', true); } catch { ck('Cypress disponible', false); }
  for (const [n, ok] of checks) console.log(`${ok ? 'OK' : 'FALLO'} ${n}`);
  console.log(`G102 local ${checks.filter(x => x[1]).length}/${checks.length}`);
  return checks.every(x => x[1]) ? 0 : 1;
}

async function ejecutar(a) {
  const v = fs.existsSync(ENV) ? leerEnv(fs.readFileSync(ENV, 'utf8')) : {};
  const gate = autorizar(v, a, { frontend: true });
  if (!gate.ok) { console.error(`EJECUCIÓN NO AUTORIZADA: ${gate.motivos.join('; ')}`); return 2; }
  if (!['evaluacion', 'reintento'].includes(a.tipo)) { console.error('Indique --tipo evaluacion|reintento'); return 2; }
  const n = version(DIR, a.tipo, a.version), newman = newmanModulo(ROOT), cypress = cypressModulo(ROOT);
  const marca = sello(), run = runId(GRUPO, n, marca);
  const base = carpetaResultados(DIR, n), out = path.join(base, run);
  fs.mkdirSync(base, { recursive: true }); fs.mkdirSync(out);
  const seriales = Object.fromEntries(Object.keys(UNIDADES).map(u => [u, serialQa(v, 'G102', marca, u)]));
  const prefijo = `QA G102 ${marca}`;
  const ev = { grupo: GRUPO, rf: 'RF-58', cu: 'CU04', casos: CASOS, version: n, run_id: run, estado: 'EN_CURSO', fase: 'PREFLIGHT', autorizacion: a.autorizacion, actor_dashboard: 'Ingeniero de Campo', dependencias: [], bloqueos: {}, aserciones: [], sandbox: {}, datos: {}, inicio: new Date().toISOString() };
  const secretos = [v.QA_SANDBOX_SECRET, v.QA_COMMON_PASSWORD, v.QA_SETUP_PASSWORD, v.QA_ENG_PASSWORD, ...Object.values(seriales)];
  let limpiar = redactor(secretos);
  const guardar = () => fs.writeFileSync(path.join(out, 'evidencia.json'), limpiar(JSON.stringify(ev, null, 2)));
  const bloquear = (casos, motivo) => { for (const c of casos) (ev.bloqueos[c] ??= []).push(motivo); };
  const pre = (casos, variante, nombre, ok, detalle) => { for (const caso of casos) ev.aserciones.push({ herramienta: 'Ejecutor', caso, tipo: 'PRE', id: null, variante, nombre: `[${caso}][PRE]${variante ? `[V:${variante}]` : ''} ${nombre}`, ok, evidencia: false, error: ok ? undefined : detalle }); };
  const sb = sandbox({ api: gate.api, run, secreto: v.QA_SANDBOX_SECRET });
  let abierto = false, serialTestigo = null;
  try {
    await sb.abrir(); abierto = true;
    const setup = await sb.login(v.QA_SETUP_EMAIL, v.QA_SETUP_PASSWORD || v.QA_COMMON_PASSWORD, 'preparación', /administrador/i);
    const eng = await sb.login(v.QA_ENG_EMAIL, v.QA_ENG_PASSWORD || v.QA_COMMON_PASSWORD, 'Ingeniero', /ingeniero/i);
    secretos.push(setup.token, eng.token); limpiar = redactor(secretos);

    // ---- PREPARACIÓN: tres unidades QA construidas con APIs oficiales ----------------------
    ev.fase = 'PREPARACION';
    const cat = await catalogos(sb, setup.token);
    const finca = await fincaConAcceso(sb, { tokSetup: setup.token, tokActor: eng.token, idActor: eng.id, nombre: `QA Monitoreo G Ciento Dos ${marca}` });
    ev.datos.finca = finca;
    const unidades = {};
    for (const u of Object.keys(UNIDADES)) {
      unidades[u] = await construirUnidad(sb, {
        tok: setup.token, cat, finca: finca.id, run, nombreUnidad: `${prefijo} ${u}`, serial: seriales[u], nombres: nombresUnidad(prefijo, u),
        // Aislamiento demostrado con el primer dispositivo, antes de enviar lecturas.
        alCrearDispositivo: serialTestigo ? null : async () => { serialTestigo = seriales[u]; ev.sandbox.aislamiento = await sb.aislamiento(seriales[u]); },
      });
      ev.datos[u] = { id_infraestructura: unidades[u].id, nombre: unidades[u].nombre, sensores: unidades[u].sensores.length, origen: 'construida en el RUN' };
    }
    // Alcance del actor y acceso al dashboard (precondición general de los tres casos).
    for (const u of Object.keys(UNIDADES)) {
      const r = await sb.req('GET', `/configuracion/infraestructuras/${unidades[u].id}`, { token: eng.token });
      pre(CASOS_POR_UNIDAD[u], u, `el Ingeniero tiene alcance sobre la unidad ${u}`, r.status === 200, `HTTP ${r.status}`);
    }
    const acceso = await sb.req('GET', `/iot/monitoreo/dashboard?id_infraestructura=${unidades.U50.id}&pagina=1&por_pagina=1`, { token: eng.token });
    pre(CASOS, null, 'el Ingeniero accede al dashboard de monitoreo', acceso.status === 200, `HTTP ${acceso.status}`);
    // Cada sensor construido debe tener estado actual (lo que lista el dashboard). Si la ingesta
    // pasa a post-commit (DEV-05) esto deja de ocurrir dentro del sandbox: BLOQUEADO, no RECHAZADO.
    for (const u of Object.keys(UNIDADES)) {
      const e = await estadosActualesCompletos(sb, unidades[u]);
      ev.datos[u].estados_actuales = e;
      pre(CASOS_POR_UNIDAD[u], u, `los ${UNIDADES[u]} sensores de ${u} tienen estado actual en el sandbox`, e.ok, e.encontrados === null ? 'no verificable (consulta fallida)' : `encontrados ${e.encontrados} de ${e.esperados} (posible efecto de DEV-05: estado actual fuera de la transacción del RUN)`);
    }

    // ---- ESCENARIOS: Newman (API) y Cypress (interfaz) --------------------------------------
    ev.fase = 'ESCENARIOS'; guardar();
    const ids = u => JSON.stringify(unidades[u].sensores.map(s => Number(s.id)));
    const vars = { base_url: gate.api, run_id: run, sandbox_secret: v.QA_SANDBOX_SECRET, autorizado_run: 'SI', token: eng.token, pagina_u200: '1' };
    for (const u of Object.keys(UNIDADES)) { vars[`id_${u.toLowerCase()}`] = unidades[u].id; vars[`ids_${u.toLowerCase()}`] = ids(u); }
    const nw = await correrNewman(newman, JSON.parse(fs.readFileSync(COLLECTION, 'utf8')), vars, { limpiar });
    ev.aserciones.push(...nw.aserciones);
    ev.respuestas = nw.muestras;
    for (const e of nw.errores) { ev.dependencias.push(e.mensaje); bloquear(e.caso ? [e.caso] : CASOS, e.mensaje); }
    // Cypress inicia su propia sesión de interfaz (sesión única: invalida el token anterior del Ingeniero).
    const env = { AUTORIZADO_RUN: 'SI', API_BASE: gate.api, RUN_ID: run, SANDBOX_SECRET: v.QA_SANDBOX_SECRET, EMAIL: v.QA_ENG_EMAIL, PASSWORD: v.QA_ENG_PASSWORD || v.QA_COMMON_PASSWORD, UNIDADES: JSON.stringify(Object.fromEntries(Object.keys(UNIDADES).map(u => [u, { id: unidades[u].id, nombre: unidades[u].nombre, prefijo: `${prefijo} ${u} S`, esperados: UNIDADES[u] }]))) };
    const cy = await correrCypress(cypress, { root: ROOT, spec: SPEC, front: gate.front, out, env, etiqueta: 'Ingeniero', limpiar });
    if (!cy.lanzado) { ev.dependencias.push(cy.mensaje); bloquear(['TC-M03-201', 'TC-M03-202'], cy.mensaje); }
    ev.aserciones.push(...cy.aserciones); ev.cypress = cy.resumen;
    ev.estado = 'CONCLUIDA';
  } catch (e) { ev.estado = ev.fase === 'ESCENARIOS' ? 'INTERRUMPIDA' : 'ABORTADA_PREFLIGHT'; ev.dependencias.push(limpiar(e.message)); }
  finally {
    try {
      if (abierto) {
        const c = await sb.cerrar(serialTestigo);
        ev.sandbox.cierre = c; ev.sandbox.rollback = c.rollback;
        if (serialTestigo && c.sonda_posterior === null) ev.dependencias.push('Rollback no confirmable: testigo auditoria.logs_dml no consultable.');
      }
    } catch (e) { ev.sandbox.rollback = false; ev.dependencias.push(limpiar(e.message)); }
    ev.veredicto = veredictoCasos({ casos: CASOS, requeridas: REQUERIDAS, estado: ev.estado, rollback: !!ev.sandbox.rollback, aserciones: ev.aserciones, bloqueos: ev.bloqueos });
    ev.fin = new Date().toISOString(); guardar();
    fs.writeFileSync(path.join(out, nombreInforme(GRUPO, n)), limpiar(informe({ grupo: GRUPO, n, run, ev, casos: CASOS, extra: `\nLímite por vista exigido: ${POR_VISTA}. Tamaños excesivos probados: ${TAMANOS_EXCESIVOS.join(', ')} (la respuesta de cada uno queda en la sección de información).\n` })));
  }
  console.log(`${GRUPO}: ${ev.estado} — ${out}`); return ev.estado === 'CONCLUIDA' ? 0 : 4;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  let code; try { const a = argumentos(process.argv.slice(2)); code = a.modo === 'local' ? local() : a.modo === 'spec' ? await verificarDescubrimiento({ root: ROOT, spec: SPEC, configVerificacion: VERIFICACION, env: {}, bloqueo: 'BLOQUEO_G102' }) : await ejecutar(a); } catch (e) { console.error(e.message); code = 2; } process.exitCode = code;
}
