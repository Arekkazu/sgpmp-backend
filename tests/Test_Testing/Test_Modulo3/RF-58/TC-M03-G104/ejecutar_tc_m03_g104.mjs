#!/usr/bin/env node
// TC-M03-204 (RF-58 / RNF-06): la vista de monitoreo permanece usable a 360 px de ancho mínimo,
// con sensores en VERDE, AMARILLO, ROJO y GRIS (valor, unidad, semáforo, alertas y controles
// principales visibles y utilizables, sin superposición ni recorte de información crítica).
//
// Preparación de los cuatro estados:
// - VERDE: CONSTRUIDO. Sensor con una lectura válida (el trigger de ingesta lo deja en VERDE).
// - AMARILLO: CONSTRUIDO. Lectura válida + alerta activa MODERADO por POST /iot/alertas (RF-57).
// - ROJO: CONSTRUIDO. Lectura válida + alerta activa CRITICO por POST /iot/alertas (RF-57).
//   (El trigger fn_sincronizar_alerta_en_sensor lleva el semáforo a AMARILLO/ROJO; además la vista
//   muestra la alerta, que también es criterio del caso.)
// - GRIS: DESCUBIERTO en solo lectura. Solo lo produce la transición de RF-60 por ausencia de
//   reportes (tarea periódica global sin disparador aislado). No se simula ni se escribe SQL: se
//   busca, con el propio dashboard del Ingeniero, un sensor en GRIS con valor y unidad.
// Cada estado se verifica por API antes de la interfaz ([PRE] por variante): si un estado no
// queda preparado, esa variante se bloquea y el caso no puede aprobarse.
//
// Actor: Ingeniero de Campo (CU04). El Productor no lee modulo9.sensores por RLS.
import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import {
  leerEnv, autorizar, version, carpetaResultados, runId, nombreInforme, argumentos, cypressModulo, sello, serialQa,
  sandbox, catalogos, fincaConAcceso, construirUnidad, estadosActualesCompletos, correrCypress, redactor, informe, cuerpoAlerta,
  veredictoCasos, consultaTestigoDispositivo, consultaEstadosActuales, casoDeTexto,
  opcionesCypress, aislamientoVerificacion, verificarDescubrimiento,
} from './monitoreo_lib.mjs';

export const GRUPO = 'TC-M03-G104';
export const CASOS = ['TC-M03-204'];
export const VARIANTES = ['VERDE', 'AMARILLO', 'ROJO', 'GRIS'];
export const CONSTRUIBLES = ['VERDE', 'AMARILLO', 'ROJO'];
/** Severidad de la alerta activa que lleva cada sensor a su estado (contrato RF-57). */
export const SEVERIDAD = { AMARILLO: 'MODERADO', ROJO: 'CRITICO' };
export const ANCHO_MINIMO = 360;
export const REQUERIDAS = {
  'TC-M03-204': [
    ...VARIANTES.flatMap(x => [`UI-204-01@${x}`, `UI-204-02@${x}`]),
    'UI-204-03@AMARILLO', 'UI-204-03@ROJO', 'UI-204-04@VERDE',
  ],
};

const DIR = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(DIR, '../../../../..');
const ENV = path.join(ROOT, '.env.qa');
const SPEC = path.join(DIR, 'tc_m03_g104.cy.js');
const VERIFICACION = path.join(DIR, 'cypress.verificacion.config.cjs');
/** Variante local ficticia: solo para que el spec registre pruebas y ejecute su before en --verificar-spec. */
const VARIANTE_LOCAL = JSON.stringify({ VERDE: { id: 1, unidad: 'LOCAL', sensor: 'LOCAL', medida: '°C', alerta: false } });

/**
 * Comprueba que el sensor construido quedó en el estado de su variante, con valor, unidad y
 * (si corresponde) alerta activa, según el dashboard del actor. Devuelve los motivos de fallo.
 */
export function revisarEstado(variante, s) {
  const m = [];
  if (!s) return ['el sensor no aparece en el dashboard de su unidad'];
  if (s.estado_semaforo !== variante) m.push(`semáforo ${s.estado_semaforo} (se esperaba ${variante})`);
  if (s.ultimo_valor === null || s.ultimo_valor === undefined) m.push('sin valor');
  if (!s.ultima_unidad) m.push('sin unidad de medida');
  if (SEVERIDAD[variante] && s.id_alerta == null) m.push('sin alerta activa');
  return m;
}
/** Candidato GRIS apto para la vista: con valor y unidad, asociado a una unidad productiva. */
export const grisApto = s => s?.estado_semaforo === 'GRIS' && s.id_infraestructura != null && s.ultimo_valor !== null && s.ultimo_valor !== undefined && !!s.ultima_unidad && !!s.nombre_sensor;

function local() {
  const checks = []; const ck = (n, x) => checks.push([n, !!x]);
  const v = fs.existsSync(ENV) ? leerEnv(fs.readFileSync(ENV, 'utf8')) : {};
  const spec = fs.readFileSync(SPEC, 'utf8');
  const fuente = fs.readFileSync(fileURLToPath(import.meta.url), 'utf8');
  const futuras = { ambiente: 'TEST', autorizacion: 'REF-DESARROLLO', efectos: ['notificacion-login'] };
  ck('Matriz: TC-M03-204', CASOS.join() === 'TC-M03-204');
  ck('Cuatro estados de semáforo; GRIS no se construye (RF-60)', VARIANTES.join() === 'VERDE,AMARILLO,ROJO,GRIS' && CONSTRUIBLES.join() === 'VERDE,AMARILLO,ROJO');
  ck('Severidades dentro del contrato RF-57', Object.values(SEVERIDAD).every(s => ['LEVE', 'MODERADO', 'CRITICO'].includes(s)));
  ck('Configuración compartida y QA_AUTORIZADO=NO', fs.existsSync(ENV) && v.QA_AUTORIZADO === 'NO');
  ck('Barrera rechaza la ejecución actual', !autorizar(v, { ambiente: 'TEST', autorizacion: '', efectos: [] }, { frontend: true }).ok);
  ck('Barrera acepta condiciones futuras válidas', autorizar({ ...v, QA_AUTORIZADO: 'SI' }, futuras, { frontend: true }).ok);
  ck('Barrera rechaza DEV', !autorizar({ ...v, QA_AUTORIZADO: 'SI' }, { ...futuras, ambiente: 'DEV' }, { frontend: true }).ok);
  ck('Cuentas de preparación (Administrador) e Ingeniero resueltas', ['SETUP', 'ENG'].every(r => !!v[`QA_${r}_EMAIL`] && !!(v[`QA_${r}_PASSWORD`] || v.QA_COMMON_PASSWORD)) && !!v.QA_SANDBOX_SECRET);
  ck('Serial QA dentro del formato (prefijo automático si falta)', /-G104-/.test(serialQa(v, 'G104', '20261017000000', 'U')));
  ck('Aserciones UI requeridas presentes en el spec', [...new Set(REQUERIDAS['TC-M03-204'].map(k => k.split('@')[0]))].every(id => spec.includes(`[${id}]`)));
  ck('Viewport mínimo de 360 px decisorio y resoluciones superiores INFO', spec.includes('ancho: 360') && /tipo: 'ASSERT'/.test(spec) && /tipo: 'INFO'/.test(spec));
  ck('Cada test del spec declara caso y PRE, ASSERT o INFO', [...spec.matchAll(/it\(`([^`]+)`/g)].map(m => m[1]).every(n => casoDeTexto(n) && /\[(PRE|ASSERT|INFO)\]/.test(n)));
  const envCypress = new Set([...spec.matchAll(/env\('([A-Z_]+)'\)/g)].map(x => x[1]));
  ck('Variables Cypress resueltas por el ejecutor', [...envCypress].every(x => ['AUTORIZADO_RUN', 'API_BASE', 'RUN_ID', 'SANDBOX_SECRET', 'EMAIL', 'PASSWORD', 'VARIANTES'].includes(x)));
  ck('Sintaxis ejecutor', spawnSync(process.execPath, ['--check', fileURLToPath(import.meta.url)]).status === 0);
  ck('Sintaxis librería', spawnSync(process.execPath, ['--check', path.join(DIR, 'monitoreo_lib.mjs')]).status === 0);
  ck('Sintaxis Cypress', spawnSync(process.execPath, ['--check', SPEC]).status === 0);
  const oc = opcionesCypress({ root: ROOT, spec: SPEC, front: 'https://front.test.example', out: DIR, env: { API_BASE: 'https://api.test.example' } });
  ck('Cypress: anulaciones en e2e, baseUrl = frontend (distinto del API), spec relativo a la raíz y sin reporter de archivos', oc.config.baseUrl === undefined && oc.config.e2e.baseUrl === 'https://front.test.example' && oc.env.API_BASE !== oc.config.e2e.baseUrl && path.resolve(ROOT, oc.config.e2e.specPattern) === SPEC && oc.reporter === 'spec' && oc.config.e2e.reporter === 'spec');
  ck('Barrera: frontend y API no pueden ser el mismo destino', !autorizar({ ...v, QA_AUTORIZADO: 'SI', SIGAB_FRONT_TEST_URL: v.SIGAB_API_TEST_BASE, SIGAB_FRONT_URL: '' }, futuras, { frontend: true }).ok);
  const ov = opcionesCypress({ root: ROOT, spec: SPEC, front: null, out: null, env: { VARIANTES: VARIANTE_LOCAL }, configFile: path.relative(ROOT, VERIFICACION).split(path.sep).join('/') });
  ck('Verificación local aislada: configuración de loopback y salida bloqueada (sin el cypress.config.cjs raíz)', aislamientoVerificacion({ root: ROOT, configVerificacion: VERIFICACION, opciones: ov, entorno: { HTTP_PROXY: 'http://127.0.0.1:9', HTTPS_PROXY: 'http://127.0.0.1:9' } }).length === 0
    && aislamientoVerificacion({ root: ROOT, configVerificacion: VERIFICACION, opciones: { ...ov, configFile: undefined }, entorno: { HTTP_PROXY: 'http://127.0.0.1:9', HTTPS_PROXY: 'http://127.0.0.1:9' } }).length > 0);
  ck('Barrera propia de Cypress y sin respuestas simuladas ni relojes falsos', spec.includes('BLOQUEO_G104') && !new RegExp(['req\\.reply', 'cy\\.stub', 'cy\\.fixture', 'cy\\.clock'].join('|')).test(spec));
  ck('Sin colección Newman (la matriz solo pide interfaz)', !fs.readdirSync(DIR).some(f => f.endsWith('.postman_collection.json')));
  ck('Testigo de aislamiento sin RLS', /FROM auditoria\.logs_dml/.test(consultaTestigoDispositivo('QAAUTO-G104-1')) && /FROM modulo3\.estados_actuales_sensores/.test(consultaEstadosActuales([1])));
  ck('Sin peticiones concurrentes al sandbox', !/Promise\.all/.test(fuente));
  ck('GRIS sin SQL de escritura ni simulación', !/(UPDATE|INSERT INTO|DELETE FROM)\s+modulo3/i.test(fuente) && !/dato_desactualizado\s*=/.test(fuente));
  ck('Veredicto: sin GRIS no hay APROBADO; ASSERT con evidencia rechaza', (() => {
    const todas = REQUERIDAS['TC-M03-204'].map(k => ({ caso: 'TC-M03-204', tipo: 'ASSERT', id: k.split('@')[0], variante: k.split('@')[1], ok: true, evidencia: true }));
    const base = { casos: CASOS, requeridas: REQUERIDAS, estado: 'CONCLUIDA', rollback: true };
    return veredictoCasos({ ...base, aserciones: todas }).grupo === 'APROBADO'
      && veredictoCasos({ ...base, aserciones: todas.filter(a => a.variante !== 'GRIS') }).grupo === 'BLOQUEADO'
      && veredictoCasos({ ...base, aserciones: todas.map(a => a.id === 'UI-204-02' && a.variante === 'ROJO' ? { ...a, ok: false } : a) }).grupo === 'RECHAZADO';
  })());
  ck('Sin carpetas RESULTADOS de construcción', !fs.existsSync(path.join(DIR, 'RESULTADOS')) && !fs.readdirSync(DIR).some(x => /^EvaluacionV\d+$/.test(x)));
  const secretos = [v.QA_SANDBOX_SECRET, v.QA_COMMON_PASSWORD, v.QA_SETUP_PASSWORD, v.QA_ENG_PASSWORD].filter(x => x?.length > 4);
  ck('Sin secretos literales', [fileURLToPath(import.meta.url), SPEC, path.join(DIR, 'monitoreo_lib.mjs')].every(f => !secretos.some(s => fs.readFileSync(f, 'utf8').includes(s))));
  ck('Pruebas unitarias locales', spawnSync(process.execPath, ['--test', path.join(DIR, 'validar_local_g104.mjs')], { encoding: 'utf8' }).status === 0);
  try { cypressModulo(ROOT); ck('Cypress disponible', true); } catch { ck('Cypress disponible', false); }
  for (const [n, ok] of checks) console.log(`${ok ? 'OK' : 'FALLO'} ${n}`);
  console.log(`G104 local ${checks.filter(x => x[1]).length}/${checks.length}`);
  return checks.every(x => x[1]) ? 0 : 1;
}

async function ejecutar(a) {
  const v = fs.existsSync(ENV) ? leerEnv(fs.readFileSync(ENV, 'utf8')) : {};
  const gate = autorizar(v, a, { frontend: true });
  if (!gate.ok) { console.error(`EJECUCIÓN NO AUTORIZADA: ${gate.motivos.join('; ')}`); return 2; }
  if (!['evaluacion', 'reintento'].includes(a.tipo)) { console.error('Indique --tipo evaluacion|reintento'); return 2; }
  const n = version(DIR, a.tipo, a.version), cypress = cypressModulo(ROOT);
  const marca = sello(), run = runId(GRUPO, n, marca);
  const base = carpetaResultados(DIR, n), out = path.join(base, run);
  fs.mkdirSync(base, { recursive: true }); fs.mkdirSync(out);
  const serial = serialQa(v, 'G104', marca, 'U');
  const prefijo = `QA G104 ${marca}`;
  const ev = { grupo: GRUPO, rf: 'RF-58', rnf: 'RNF-06', cu: 'CU04', casos: CASOS, version: n, run_id: run, estado: 'EN_CURSO', fase: 'PREFLIGHT', autorizacion: a.autorizacion, actor_dashboard: 'Ingeniero de Campo', dependencias: [], bloqueos: {}, aserciones: [], sandbox: {}, datos: { variantes: {} }, inicio: new Date().toISOString() };
  const secretos = [v.QA_SANDBOX_SECRET, v.QA_COMMON_PASSWORD, v.QA_SETUP_PASSWORD, v.QA_ENG_PASSWORD, serial];
  let limpiar = redactor(secretos);
  const guardar = () => fs.writeFileSync(path.join(out, 'evidencia.json'), limpiar(JSON.stringify(ev, null, 2)));
  const pre = (variante, nombre, ok, detalle) => ev.aserciones.push({ herramienta: 'Ejecutor', caso: 'TC-M03-204', tipo: 'PRE', id: null, variante, nombre: `[TC-M03-204][PRE]${variante ? `[V:${variante}]` : ''} ${nombre}`, ok, evidencia: false, error: ok ? undefined : detalle });
  const sb = sandbox({ api: gate.api, run, secreto: v.QA_SANDBOX_SECRET });
  let abierto = false, dispositivo = false;
  try {
    await sb.abrir(); abierto = true;
    const setup = await sb.login(v.QA_SETUP_EMAIL, v.QA_SETUP_PASSWORD || v.QA_COMMON_PASSWORD, 'preparación', /administrador/i);
    const eng = await sb.login(v.QA_ENG_EMAIL, v.QA_ENG_PASSWORD || v.QA_COMMON_PASSWORD, 'Ingeniero', /ingeniero/i);
    secretos.push(setup.token, eng.token); limpiar = redactor(secretos);
    const dashboard = async q => sb.req('GET', `/iot/monitoreo/dashboard?${q}`, { token: eng.token });

    // ---- PREPARACIÓN: VERDE, AMARILLO y ROJO construidos en una unidad QA ------------------
    ev.fase = 'PREPARACION';
    const cat = await catalogos(sb, setup.token);
    const finca = await fincaConAcceso(sb, { tokSetup: setup.token, tokActor: eng.token, idActor: eng.id, nombre: `QA Monitoreo G Ciento Cuatro ${marca}` });
    ev.datos.finca = finca;
    const unidad = await construirUnidad(sb, {
      tok: setup.token, cat, finca: finca.id, run, nombreUnidad: `${prefijo} U`, serial, nombres: CONSTRUIBLES.map(x => `${prefijo} ${x}`),
      alCrearDispositivo: async () => { dispositivo = true; ev.sandbox.aislamiento = await sb.aislamiento(serial); },
    });
    const porVariante = Object.fromEntries(CONSTRUIBLES.map((x, i) => [x, unidad.sensores[i]]));
    for (const [x, severidad] of Object.entries(SEVERIDAD)) {
      const s = porVariante[x];
      const r = await sb.req('POST', '/iot/alertas', { body: cuerpoAlerta({ idDispositivo: unidad.id_dispositivo, idSensor: s.id, serial, idTelemetria: s.id_telemetria, severidad }) });
      s.alerta = { http: r.status, id_alerta: r.data?.id_alerta ?? null, duplicada: r.data?.es_duplicado ?? null };
    }
    const alcance = await sb.req('GET', `/configuracion/infraestructuras/${unidad.id}`, { token: eng.token });
    pre(null, 'el Ingeniero tiene alcance sobre la unidad QA', alcance.status === 200, `HTTP ${alcance.status}`);
    const e = await estadosActualesCompletos(sb, unidad);
    pre(null, 'los sensores construidos tienen estado actual en el sandbox', e.ok, e.encontrados === null ? 'no verificable (consulta fallida)' : `encontrados ${e.encontrados} de ${e.esperados} (posible efecto de DEV-05)`);
    // Estado de cada sensor según el dashboard del Ingeniero.
    const vistaQa = await dashboard(`id_infraestructura=${unidad.id}&pagina=1&por_pagina=50`);
    pre(null, 'el Ingeniero accede al dashboard de la unidad QA', vistaQa.status === 200, `HTTP ${vistaQa.status}`);
    const preparadas = {};
    for (const x of CONSTRUIBLES) {
      const s = porVariante[x];
      const fila = (vistaQa.data?.sensores || []).find(y => Number(y.id_sensor) === Number(s.id));
      const motivos = [...(SEVERIDAD[x] && (s.alerta?.http !== 201 || !s.alerta?.id_alerta || s.alerta?.duplicada) ? [`alerta ${SEVERIDAD[x]} no registrada (HTTP ${s.alerta?.http})`] : []), ...revisarEstado(x, fila)];
      pre(x, `sensor construido en ${x}${SEVERIDAD[x] ? ` (alerta activa ${SEVERIDAD[x]})` : ''}`, !motivos.length, motivos.join('; '));
      ev.datos.variantes[x] = { origen: 'construido en el RUN', id_infraestructura: unidad.id, id_sensor: s.id, id_alerta: s.alerta?.id_alerta ?? null, semaforo_api: fila?.estado_semaforo ?? null, preparado: !motivos.length };
      if (!motivos.length) preparadas[x] = { id: unidad.id, unidad: unidad.nombre, sensor: s.nombre, medida: fila.ultima_unidad, alerta: !!SEVERIDAD[x] };
    }

    // ---- DESCUBRIMIENTO: GRIS en solo lectura (dashboard del Ingeniero) ---------------------
    ev.fase = 'DESCUBRIMIENTO';
    let gris = null;
    for (let pagina = 1; pagina <= 20 && !gris; pagina++) {
      const r = await dashboard(`pagina=${pagina}&por_pagina=50`);
      if (r.status !== 200) break;
      for (const c of (r.data?.sensores || []).filter(grisApto)) {
        // La vista filtrada por unidad muestra su primer segmento: el sensor debe estar en él.
        const u = await dashboard(`id_infraestructura=${Number(c.id_infraestructura)}&pagina=1&por_pagina=50`);
        const f = u.status === 200 ? (u.data?.sensores || []).find(y => Number(y.id_sensor) === Number(c.id_sensor)) : null;
        const homonimos = u.status === 200 ? (u.data?.sensores || []).filter(y => y.nombre_sensor === c.nombre_sensor).length : 0;
        if (grisApto(f) && homonimos === 1) { gris = f; break; }
      }
      if ((r.data?.sensores || []).length < 50) break;
    }
    if (gris) {
      preparadas.GRIS = { id: Number(gris.id_infraestructura), unidad: gris.nombre_infraestructura, sensor: gris.nombre_sensor, medida: gris.ultima_unidad, alerta: false };
      ev.datos.variantes.GRIS = { origen: 'descubierto en solo lectura (dashboard del Ingeniero)', id_infraestructura: Number(gris.id_infraestructura), id_sensor: Number(gris.id_sensor), semaforo_api: gris.estado_semaforo, preparado: true };
    } else {
      const msg = 'GRIS: no se descubrió un sensor en GRIS con valor y unidad entre las unidades del Ingeniero. Depende de la transición RF-60 por ausencia de reportes (tarea periódica global, sin disparador aislado); no se simula ni se escribe SQL.';
      ev.dependencias.push(msg); pre('GRIS', 'sensor en GRIS disponible para la vista', false, msg);
      ev.datos.variantes.GRIS = { origen: 'no disponible', preparado: false };
    }

    // ---- ESCENARIOS: Cypress a 360 px (decisorio) y resoluciones superiores (INFO) ----------
    ev.fase = 'ESCENARIOS'; guardar();
    if (!Object.keys(preparadas).length) throw Error('Ninguna variante preparada: no hay vista que evaluar');
    const env = { AUTORIZADO_RUN: 'SI', API_BASE: gate.api, RUN_ID: run, SANDBOX_SECRET: v.QA_SANDBOX_SECRET, EMAIL: v.QA_ENG_EMAIL, PASSWORD: v.QA_ENG_PASSWORD || v.QA_COMMON_PASSWORD, VARIANTES: JSON.stringify(preparadas) };
    const cy = await correrCypress(cypress, { root: ROOT, spec: SPEC, front: gate.front, out, env, etiqueta: 'Ingeniero', limpiar });
    if (!cy.lanzado) { ev.dependencias.push(cy.mensaje); (ev.bloqueos['TC-M03-204'] ??= []).push(cy.mensaje); }
    ev.aserciones.push(...cy.aserciones); ev.cypress = cy.resumen;
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
    fs.writeFileSync(path.join(out, nombreInforme(GRUPO, n)), limpiar(informe({ grupo: GRUPO, n, run, ev, casos: CASOS, extra: `\nAncho mínimo decisorio: ${ANCHO_MINIMO} px (768 y 1366 px se registran como INFO). Estados: ${JSON.stringify(ev.datos.variantes)}.\n` })));
  }
  console.log(`${GRUPO}: ${ev.estado} — ${out}`); return ev.estado === 'CONCLUIDA' ? 0 : 4;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  let code; try { const a = argumentos(process.argv.slice(2)); code = a.modo === 'local' ? local() : a.modo === 'spec' ? await verificarDescubrimiento({ root: ROOT, spec: SPEC, configVerificacion: VERIFICACION, env: { VARIANTES: VARIANTE_LOCAL }, bloqueo: 'BLOQUEO_G104' }) : await ejecutar(a); } catch (e) { console.error(e.message); code = 2; } process.exitCode = code;
}
