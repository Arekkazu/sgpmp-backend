// TC-M03-G88 — pruebas unitarias locales de las funciones puras del grupo.
// Ejecutar: node --test validar_local_g88.mjs
// No realizan solicitudes de red ni escriben en la carpeta del grupo: todo
// directorio de prueba se crea en el temporal del sistema y se elimina al final.

import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

import { GRUPO, CASOS, PLAN } from './g88_casos.mjs';
import {
  ESTADOS,
  ESTADOS_RUN,
  parsearEnv,
  cargarConfiguracion,
  evaluarAutorizacion,
  bloquearRed,
  sanitizar,
  redactarTexto,
  enmascararClaveIot,
  escanearYRedactarDirectorio,
  inspeccionarHistorial,
  resolverVersion,
  generarRunId,
  nombreInforme,
  dirResultadosVersion,
  crearDirectorioRun,
  escribirNuevo,
  parsearNombreAsercion,
  resultadosDesdeNewman,
  resultadosDesdeCypress,
  incidenciasNewman,
  resumenNewman,
  naturalezaErrorCypress,
  NATURALEZA,
  resolverDestinos,
  prefijoSeriales,
  serialDispositivo,
  PREFIJO_AUTOMATICO,
  veredictoCaso,
  estadoGrupo,
  literalSql,
  generarInforme,
} from './g88_lib.mjs';

bloquearRed();

const tmp = () => fs.mkdtempSync(path.join(os.tmpdir(), 'g88-test-'));
const limpiar = (d) => fs.rmSync(d, { recursive: true, force: true });

const VALIDO = {
  QA_AUTORIZADO: 'SI',
  SIGAB_API_TEST_BASE: 'https://www.api.inmero.co/api-sgpmp-test',
  SIGAB_FRONT_TEST_URL: 'https://api.inmero.co/sigab-test/',
  SIGAB_API_DEV_BASE: 'https://api.ejemplo.test/back-sigab-dev',
  SIGAB_API_BASE: 'https://www.api.inmero.co/api-sgpmp-test',
  QA_COMMON_PASSWORD: 'clave-ficticia-123',
  QA_SANDBOX_SECRET: 'secreto-ficticio-abcdef',
  QA_SETUP_EMAIL: 'a@x.test',
  QA_PROD_EMAIL: 'p@x.test',
  QA_ENG_EMAIL: 'i@x.test',
  QA_DEVICE_PREFIX: 'QATEST',
};
const EFECTOS = PLAN.efectosPersistentes;
const OPC = { ambiente: 'TEST', autorizacion: 'Autorizacion DEV 2026-10-20 #123', efectosAceptados: EFECTOS.map((e) => e.id) };
const autorizar = (valores, opc = OPC) => evaluarAutorizacion(valores, opc, EFECTOS);

function escribirRun(dirGrupo, version, runId, estado, casos) {
  const dir = path.join(dirResultadosVersion(dirGrupo, version), runId);
  fs.mkdirSync(dir, { recursive: true });
  if (estado !== undefined) {
    fs.writeFileSync(path.join(dir, 'evidencia.json'), JSON.stringify({
      ejecucion: { estado, version },
      resultado_propuesto: casos ? { casos: casos.map(([caso, e]) => ({ caso, estado: e })) } : null,
    }));
  }
  return dir;
}

// --- Configuración y barrera ------------------------------------------------

test('parsearEnv ignora comentarios y respeta comillas', () => {
  const v = parsearEnv('# c\nA=1\nB = "dos"\n  C=\'tres\'\nmal linea\n');
  assert.deepEqual(v, { A: '1', B: 'dos', C: 'tres' });
});

test('cargarConfiguracion da prioridad al entorno del proceso y no lo modifica', () => {
  const d = tmp();
  try {
    const f = path.join(d, '.env.qa');
    fs.writeFileSync(f, 'QA_AUTORIZADO=NO\nQA_PROD_EMAIL=p@x.test\n');
    // Solo se comparan las claves QA (nunca se vuelca el entorno completo).
    const claves = ['QA_AUTORIZADO', 'QA_PROD_EMAIL'];
    const antes = claves.map((k) => process.env[k]);
    const total = Object.keys(process.env).length;
    const r = cargarConfiguracion(f, { QA_PROD_EMAIL: 'otro@x.test' });
    assert.equal(r.valores.QA_AUTORIZADO, 'NO');
    assert.equal(r.valores.QA_PROD_EMAIL, 'otro@x.test');
    assert.ok(claves.every((k, i) => process.env[k] === antes[i]), 'process.env no debe cambiar');
    assert.ok(Object.keys(process.env).length === total, 'process.env no debe recibir claves nuevas');
  } finally { limpiar(d); }
});

test('la barrera bloquea con QA_AUTORIZADO=NO', () => {
  const r = autorizar({ ...VALIDO, QA_AUTORIZADO: 'NO' });
  assert.equal(r.autorizado, false);
  assert.match(r.motivos.join(' '), /QA_AUTORIZADO=NO/);
});

test('la barrera exige referencia de autorización y ambiente TEST', () => {
  assert.equal(autorizar(VALIDO, { ...OPC, autorizacion: '' }).autorizado, false);
  assert.equal(autorizar(VALIDO, { ...OPC, ambiente: 'DEV' }).autorizado, false);
});

test('la barrera rechaza destinos DEV, HTTP o alias incoherentes', () => {
  assert.equal(autorizar({ ...VALIDO, SIGAB_API_TEST_BASE: VALIDO.SIGAB_API_DEV_BASE, SIGAB_API_BASE: VALIDO.SIGAB_API_DEV_BASE }).autorizado, false);
  assert.equal(autorizar({ ...VALIDO, SIGAB_API_TEST_BASE: 'http://api.ejemplo.test/back-sigab-test', SIGAB_API_BASE: 'http://api.ejemplo.test/back-sigab-test' }).autorizado, false);
  assert.equal(autorizar({ ...VALIDO, SIGAB_API_BASE: 'https://otro.test' }).autorizado, false);
});

test('la barrera exige secretos; QA_DEVICE_PREFIX es opcional pero, si existe, debe ser válido', () => {
  assert.equal(autorizar({ ...VALIDO, QA_SANDBOX_SECRET: '' }).autorizado, false);
  assert.equal(autorizar({ ...VALIDO, QA_COMMON_PASSWORD: '' }).autorizado, false);
  assert.equal(autorizar({ ...VALIDO, QA_DEVICE_PREFIX: '' }).autorizado, true);
  assert.equal(autorizar({ ...VALIDO, QA_DEVICE_PREFIX: 'mal prefijo!' }).autorizado, false);
});

test('la barrera exige aceptar expresamente los efectos persistentes conocidos', () => {
  const r = autorizar(VALIDO, { ...OPC, efectosAceptados: [] });
  assert.equal(r.autorizado, false);
  assert.match(r.motivos.join(' '), /notificacion-login/);
});

test('resolverDestinos usa las canónicas, admite los alias y rechaza ambigüedad o DEV', () => {
  const base = { SIGAB_API_DEV_BASE: VALIDO.SIGAB_API_DEV_BASE, SIGAB_FRONT_DEV_URL: 'https://dev.ejemplo.test/' };
  const soloAlias = resolverDestinos({ ...base, SIGAB_API_BASE: 'https://www.api.inmero.co/api-sgpmp-test/', SIGAB_FRONT_URL: 'https://api.inmero.co/sigab-test/' });
  assert.deepEqual([soloAlias.api, soloAlias.front, soloAlias.motivos.length], ['https://www.api.inmero.co/api-sgpmp-test', 'https://api.inmero.co/sigab-test', 0]);
  assert.equal(resolverDestinos({ ...base, SIGAB_API_TEST_BASE: 'https://a.test/x', SIGAB_API_BASE: 'https://b.test/x', SIGAB_FRONT_TEST_URL: 'https://f.test' }).api, '');
  assert.ok(resolverDestinos({ ...base, SIGAB_API_TEST_BASE: VALIDO.SIGAB_API_DEV_BASE, SIGAB_FRONT_TEST_URL: 'https://f.test' }).motivos.length > 0);
  assert.ok(resolverDestinos({ ...base, SIGAB_API_TEST_BASE: 'https://a.test/x', SIGAB_FRONT_TEST_URL: 'https://dev.ejemplo.test/' }).motivos.length > 0);
});

test('prefijoSeriales genera un prefijo automático si QA_DEVICE_PREFIX está vacío', () => {
  assert.deepEqual(prefijoSeriales({ QA_DEVICE_PREFIX: '' }).prefijo, PREFIJO_AUTOMATICO);
  assert.equal(prefijoSeriales({ QA_DEVICE_PREFIX: 'QAREAL' }).prefijo, 'QAREAL');
  assert.equal(prefijoSeriales({ QA_DEVICE_PREFIX: 'con espacio' }).valido, false);
  const serial = serialDispositivo(PREFIJO_AUTOMATICO, GRUPO.corto, '20261016153000');
  assert.equal(serial, `QAAUTO-${GRUPO.corto}-20261016153000`);
  assert.ok(serial.length <= 50);
});

test('la barrera autoriza solo con todas las condiciones', () => {
  const r = autorizar(VALIDO);
  assert.equal(r.autorizado, true, r.motivos.join(' '));
});

test('el bloqueo de red impide fetch', async () => {
  await assert.rejects(() => fetch('https://example.invalid'), /BLOQUEO_RED/);
});

// --- Sanitización -----------------------------------------------------------

test('sanitizar redacta claves sensibles, JWT, secretos y enmascara claves IoT', () => {
  // JWT ficticio armado en ejecución para que el archivo no contenga un literal con forma de token.
  const jwt = ['eyJ' + 'hbGciOiJIUzI1NiJ9', 'eyJ' + 'zdWIiOiIxMjM0NSJ9', 'abcdefghijk'].join('.');
  const s = sanitizar({
    headers: { Authorization: `Bearer ${jwt}`, 'X-Sandbox-Secret': 'secreto-ficticio-abcdef' },
    body: { contrasena: 'x', access_key: 'QATEST-G88-20261015153000', nota: `token ${jwt} y clave-ficticia-123` },
  }, ['clave-ficticia-123']);
  assert.equal(s.headers.Authorization, '[REDACTADO]');
  assert.equal(s.headers['X-Sandbox-Secret'], '[REDACTADO]');
  assert.equal(s.body.contrasena, '[REDACTADO]');
  assert.equal(s.body.access_key, 'QATE…00');
  assert.equal(s.body.nota, 'token [JWT_REDACTADO] y [REDACTADO]');
});

test('enmascararClaveIot nunca devuelve la clave completa', () => {
  assert.equal(enmascararClaveIot('abc'), '***');
  assert.notEqual(enmascararClaveIot('QATEST-123456'), 'QATEST-123456');
});

test('escanearYRedactarDirectorio limpia archivos de texto del RUN', () => {
  const d = tmp();
  try {
    fs.mkdirSync(path.join(d, 'newman'));
    fs.writeFileSync(path.join(d, 'newman', 'r.html'), '<p>secreto-ficticio-abcdef</p>');
    fs.writeFileSync(path.join(d, 'ok.json'), '{"a":1}');
    const r = escanearYRedactarDirectorio(d, ['secreto-ficticio-abcdef']);
    assert.deepEqual(r.archivos_redactados, [path.join('newman', 'r.html')]);
    assert.equal(fs.readFileSync(path.join(d, 'newman', 'r.html'), 'utf8'), '<p>[REDACTADO]</p>');
  } finally { limpiar(d); }
});

test('redactarTexto prioriza el secreto más largo', () => {
  assert.equal(redactarTexto('abcd abcdef', ['abcd', 'abcdef']), '[REDACTADO] [REDACTADO]');
});

test('literalSql solo admite enteros y texto seguro', () => {
  assert.equal(literalSql(15), '15');
  assert.equal(literalSql('QATEST-G88-1'), "'QATEST-G88-1'");
  assert.throws(() => literalSql("x' OR '1'='1"));
});

// --- Numeración histórica de evaluaciones -----------------------------------

test('sin historial corresponde V1 y RUN_ID/rutas/informe con nomenclatura histórica', () => {
  const d = tmp();
  try {
    const h = inspeccionarHistorial(d);
    const r = resolverVersion(h, { tipo: 'evaluacion' });
    assert.equal(r.ok, true);
    assert.equal(r.version, 1);
    assert.match(generarRunId(GRUPO.corto, 1, new Date(2026, 9, 20, 8, 5, 9)), new RegExp(`^${GRUPO.corto}-EVAL-V1-20261020-080509$`));
    assert.match(generarRunId(GRUPO.corto, 3, new Date(2026, 9, 20, 8, 5, 9)), new RegExp(`^${GRUPO.corto}-REEVAL-V3-20261020-080509$`));
    assert.equal(nombreInforme(GRUPO.id, 1), `${GRUPO.id}_resultado.md`);
    assert.equal(nombreInforme(GRUPO.id, 2), `${GRUPO.id}_reevaluacion_V2.md`);
    assert.equal(dirResultadosVersion(d, 1), path.join(d, 'RESULTADOS'));
    assert.equal(dirResultadosVersion(d, 4), path.join(d, 'EvaluacionV4', 'RESULTADOS'));
    assert.equal(resolverVersion(h, { tipo: 'reintento' }).ok, false);
  } finally { limpiar(d); }
});

test('V1 concluida: una evaluación autorizada es V2 y un reintento sigue en V1', () => {
  const d = tmp();
  try {
    escribirRun(d, 1, 'G88-EVAL-V1-20261020-080000', ESTADOS_RUN.CONCLUIDA);
    const h = inspeccionarHistorial(d);
    assert.equal(resolverVersion(h, { tipo: 'evaluacion' }).version, 2);
    assert.equal(resolverVersion(h, { tipo: 'reintento' }).version, 1);
  } finally { limpiar(d); }
});

test('la numeración continúa sin límite (V5 concluida -> V6)', () => {
  const d = tmp();
  try {
    for (let n = 1; n <= 5; n += 1) escribirRun(d, n, `G88-R-V${n}`, ESTADOS_RUN.CONCLUIDA);
    assert.equal(resolverVersion(inspeccionarHistorial(d), { tipo: 'evaluacion' }).version, 6);
  } finally { limpiar(d); }
});

test('ejecuciones abortadas en preflight no consumen la versión', () => {
  const d = tmp();
  try {
    escribirRun(d, 1, 'G88-EVAL-V1-20261020-080000', ESTADOS_RUN.ABORTADA_PREFLIGHT);
    assert.equal(resolverVersion(inspeccionarHistorial(d), { tipo: 'evaluacion' }).version, 1);
  } finally { limpiar(d); }
});

test('una evaluación interrumpida sin concluir es ambigua y exige confirmación', () => {
  const d = tmp();
  try {
    escribirRun(d, 1, 'A', ESTADOS_RUN.CONCLUIDA);
    escribirRun(d, 2, 'B', ESTADOS_RUN.INTERRUMPIDA);
    const h = inspeccionarHistorial(d);
    const r = resolverVersion(h, { tipo: 'evaluacion' });
    assert.equal(r.ok, false);
    assert.equal(r.ambiguo, true);
    assert.equal(resolverVersion(h, { tipo: 'evaluacion', versionConfirmada: 2 }).version, 2);
    assert.equal(resolverVersion(h, { tipo: 'evaluacion', versionConfirmada: 3 }).version, 3);
    assert.equal(resolverVersion(h, { tipo: 'evaluacion', versionConfirmada: 7 }).ok, false);
  } finally { limpiar(d); }
});

test('RUN sin evidencia o huecos en el historial se tratan como ambigüedad', () => {
  const d = tmp();
  try {
    escribirRun(d, 1, 'legado', undefined);
    assert.equal(resolverVersion(inspeccionarHistorial(d), { tipo: 'evaluacion' }).ambiguo, true);
  } finally { limpiar(d); }
  const e = tmp();
  try {
    escribirRun(e, 3, 'C', ESTADOS_RUN.CONCLUIDA);
    const h = inspeccionarHistorial(e);
    assert.ok(h.anomalias.some((x) => /falta evidencia de V1/.test(x)));
    assert.equal(resolverVersion(h, { tipo: 'evaluacion' }).ok, false);
  } finally { limpiar(e); }
});

test('crearDirectorioRun y escribirNuevo nunca sobrescriben', () => {
  const d = tmp();
  try {
    const run = crearDirectorioRun(d, 2, 'G88-REEVAL-V2-X');
    assert.ok(run.endsWith(path.join('EvaluacionV2', 'RESULTADOS', 'G88-REEVAL-V2-X')));
    assert.throws(() => crearDirectorioRun(d, 2, 'G88-REEVAL-V2-X'), /EEXIST/);
    escribirNuevo(path.join(run, 'a.md'), 'uno');
    assert.throws(() => escribirNuevo(path.join(run, 'a.md'), 'dos'), /EEXIST/);
    assert.equal(fs.readFileSync(path.join(run, 'a.md'), 'utf8'), 'uno');
  } finally { limpiar(d); }
});

// --- Resultados y veredictos --------------------------------------------------

test('parsearNombreAsercion reconoce PRE, ASSERT e INFO', () => {
  assert.deepEqual(parsearNombreAsercion('[TC-M03-168][PRE][PRE-168-01] x'), { caso: 'TC-M03-168', tipo: 'PRE', id: 'PRE-168-01', texto: 'x' });
  assert.equal(parsearNombreAsercion('[TC-M03-178][INFO][INF-178-01] y').tipo, 'INFO');
  assert.equal(parsearNombreAsercion('[SETUP] login'), null);
});

test('resultadosDesdeNewman e incidenciasNewman separan evidencia del producto de fallos de ejecución', () => {
  const rep = { run: { executions: [
    { item: { name: 'Perfil Productor' }, response: { code: 401 }, assertions: [{ assertion: '[SETUP] Sesión del Productor vigente', error: { message: 'expected 401 to equal 200' } }] },
    { item: { name: '177 Dashboard Productor' }, requestError: { code: 'ECONNRESET' }, assertions: [] },
    { item: { name: '168 Dashboard Productor' }, response: { code: 200 }, assertions: [
      { assertion: '[TC-M03-168][ASSERT][API-168-01] ok' },
      { assertion: '[TC-M03-168][ASSERT][API-168-03] valor', error: { message: 'expected 58 to be close to 25.2' } },
    ] },
  ], failures: [] } };
  const r = resultadosDesdeNewman(rep);
  assert.equal(r.length, 2);
  assert.equal(r[1].ok, false);
  assert.match(r[1].detalle, /58/);
  assert.equal(r[1].naturaleza, NATURALEZA.PRODUCTO);
  rep.run.failures = [{ at: 'test-script', source: { name: '178 Dashboard Ingeniero' }, error: { name: 'TypeError', message: 'x is undefined' } }];
  const inc = incidenciasNewman(rep);
  assert.equal(inc.general.length, 1);
  assert.match(inc.general[0], /^INFRAESTRUCTURA/);
  assert.match(inc.porCaso['TC-M03-177'][0], /^INFRAESTRUCTURA/);
  assert.match(inc.porCaso['TC-M03-178'][0], /^AUTOMATIZACION/);
});

test('resumenNewman consolida peticiones y conserva solo los sensores del RUN', () => {
  const cuerpo = JSON.stringify({ total: 2, sensores: [{ id_sensor: 7, ultimo_valor: '25.2000', ultima_unidad: '°C' }, { id_sensor: 99, ultimo_valor: '1' }] });
  const r = resumenNewman({ run: { stats: { requests: { total: 1 }, assertions: { total: 1, failed: 0 } }, executions: [
    { item: { name: '168 Dashboard Productor' }, request: { method: 'GET', url: { path: ['iot', 'monitoreo', 'dashboard'], query: [{ key: 'por_pagina', value: '50' }] } },
      response: { code: 200, responseTime: 12, stream: { type: 'Buffer', data: [...Buffer.from(cuerpo)] } }, assertions: [{ assertion: '[TC-M03-168][ASSERT][API-168-01] ok' }] },
  ] } }, [7, 8]);
  assert.equal(r.peticiones[0].caso, 'TC-M03-168');
  assert.equal(r.peticiones[0].ruta, '/iot/monitoreo/dashboard?por_pagina=50');
  assert.deepEqual(r.peticiones[0].observado.sensores_del_run.map((x) => x.id_sensor), [7]);
  assert.deepEqual(r.peticiones[0].observado.sensores_del_run_ausentes, [8]);
});

test('naturalezaErrorCypress distingue infraestructura, automatización y producto', () => {
  assert.equal(naturalezaErrorCypress('CypressError: cy.visit() failed trying to load'), NATURALEZA.INFRAESTRUCTURA);
  assert.equal(naturalezaErrorCypress('TypeError: Cannot read properties of undefined'), NATURALEZA.AUTOMATIZACION);
  assert.equal(naturalezaErrorCypress('AssertionError: valor mostrado 45: expected false to equal true'), NATURALEZA.PRODUCTO);
});

test('resultadosDesdeCypress interpreta estados', () => {
  const r = resultadosDesdeCypress({ runs: [{ tests: [
    { title: ['TC-M03-G88', 'Productor', '[TC-M03-177][ASSERT][UI-177-01] a'], state: 'passed' },
    { title: ['x', '[TC-M03-177][ASSERT][UI-177-02] b'], state: 'failed', displayError: 'AssertionError: valor\n at' },
    { title: ['x', '[TC-M03-177][ASSERT][UI-177-03] c'], state: 'skipped' },
  ] }] });
  assert.deepEqual(r.map((x) => x.ok), [true, false, null]);
  assert.equal(r[1].detalle, 'AssertionError: valor');
});

const caso168 = CASOS[0];
const PRE1 = caso168.aserciones.find((a) => a.tipo === 'PRE').id;
const [A1, A2, A3] = caso168.aserciones.filter((a) => a.tipo === 'ASSERT').map((a) => a.id);
const todos = (caso, ok = true) => caso.aserciones.map((a) => ({ caso: caso.id, tipo: a.tipo, id: a.id, ok, naturaleza: ok ? null : NATURALEZA.PRODUCTO }));
const fallar = (r, id, naturaleza = NATURALEZA.PRODUCTO) => r.map((x) => (x.id === id ? { ...x, ok: false, naturaleza } : x));

test('veredicto APROBADO cuando todo se verifica', () => {
  assert.equal(veredictoCaso(caso168, todos(caso168)).estado, ESTADOS.APROBADO);
});

test('veredicto BLOQUEADO cuando falla una precondición (p. ej. FUERA_DE_RANGO no producido)', () => {
  const r = fallar(todos(caso168), PRE1).map((x) => (x.tipo === 'ASSERT' ? { ...x, ok: false, naturaleza: NATURALEZA.PRODUCTO } : x));
  const v = veredictoCaso(caso168, r);
  assert.equal(v.estado, ESTADOS.BLOQUEADO);
  assert.match(v.motivo, new RegExp(PRE1));
  // El incumplimiento de la dependencia queda registrado como hallazgo.
  assert.match(v.hallazgos.find((h) => h.asercion === PRE1).lectura, /dependa? el caso|depende el caso/);
});

test('veredicto RECHAZADO cuando falla un criterio con precondiciones cumplidas', () => {
  assert.equal(veredictoCaso(caso168, fallar(todos(caso168), A1)).estado, ESTADOS.RECHAZADO);
});

test('un fallo de automatización o infraestructura nunca produce RECHAZADO', () => {
  assert.equal(veredictoCaso(caso168, fallar(todos(caso168), A1, NATURALEZA.AUTOMATIZACION)).estado, ESTADOS.BLOQUEADO);
  assert.equal(veredictoCaso(caso168, fallar(todos(caso168), A1, NATURALEZA.INFRAESTRUCTURA)).estado, ESTADOS.BLOQUEADO);
  // Con evidencia de incumplimiento del producto en otra aserción, el caso sí es RECHAZADO.
  const mixto = fallar(fallar(todos(caso168), A1), A2, NATURALEZA.AUTOMATIZACION);
  assert.equal(veredictoCaso(caso168, mixto).estado, ESTADOS.RECHAZADO);
});

test('veredicto BLOQUEADO si falta una aserción obligatoria y NO EJECUTADO si no hay ninguna', () => {
  const r = todos(caso168).filter((x) => x.id !== A3);
  assert.equal(veredictoCaso(caso168, r).estado, ESTADOS.BLOQUEADO);
  assert.equal(veredictoCaso(caso168, []).estado, ESTADOS.NO_EJECUTADO);
});

test('las aserciones INFO no deciden el veredicto y los bloqueos del runner prevalecen', () => {
  const c178 = CASOS.find((c) => c.aserciones.some((a) => a.tipo === 'INFO')) ?? CASOS[CASOS.length - 1];
  const r = todos(c178).map((x) => (x.tipo === 'INFO' ? { ...x, ok: false } : x));
  assert.equal(veredictoCaso(c178, r).estado, ESTADOS.APROBADO);
  assert.equal(veredictoCaso(c178, todos(c178), ['Ingeniero sin alcance']).estado, ESTADOS.BLOQUEADO);
});

test('estadoGrupo agrega con prioridad RECHAZADO > BLOQUEADO', () => {
  assert.equal(estadoGrupo([{ estado: 'APROBADO' }, { estado: 'APROBADO' }]), 'APROBADO');
  assert.equal(estadoGrupo([{ estado: 'APROBADO' }, { estado: 'BLOQUEADO' }, { estado: 'RECHAZADO' }]), 'RECHAZADO');
  assert.equal(estadoGrupo([{ estado: 'APROBADO' }, { estado: 'BLOQUEADO' }]), 'BLOQUEADO');
});

test('cada caso del catálogo tiene aserciones únicas y al menos un criterio ASSERT', () => {
  for (const c of CASOS) {
    const ids = c.aserciones.map((a) => a.id);
    assert.equal(new Set(ids).size, ids.length, c.id);
    assert.ok(c.aserciones.some((a) => a.tipo === 'ASSERT'), c.id);
  }
  assert.deepEqual(CASOS.map((c) => c.id), GRUPO.casosMatriz);
});

// --- Informe ------------------------------------------------------------------

function evidenciaFicticia(version) {
  const veredictos = CASOS.map((c) => veredictoCaso(c, todos(c)));
  return {
    ejecucion: { run_id: generarRunId(GRUPO.corto, version), version, tipo: version === 1 ? 'evaluacion' : 'evaluacion', motivo_version: 'prueba', autorizacion: 'ref', inicio: '2026-10-20T08:00:00.000Z' },
    entorno: { api_base: 'https://www.api.inmero.co/api-sgpmp-test', front_url: 'https://api.inmero.co/sigab-test/' },
    codigo: { rama: 'qa', head: 'abc', vs_origin_test: '0 / 0', cambios_locales_grupo: 'ninguno', huella: { sha256_conjunto: 'f00' } },
    actores: [{ rol: 'Productor', correo: 'p@x.test', nombre_rol: 'Productor' }],
    datos: { estrategia_finca: 'x', entidades: [{ entidad: 'Área', id: 1, origen: 'RUN' }], dependencias: [],
      rango_operativo: { unidad: '°C', min: 20, max: 30, fuente: 'ref', fisico_min: -40, fisico_max: 60, valor_fuera: 45, validos: [25] } },
    sandbox: { run_id_sandbox: 'x', cierre: 'HTTP 200', rollback_confirmado: 'Sí' },
    resultado_propuesto: { casos: veredictos, grupo: estadoGrupo(veredictos) },
    newman: { peticiones: [{ caso: CASOS[0].id, peticion: `${CASOS[0].id.slice(-3)} Dashboard Productor`, http: 200, observado: { total: 1 } }] },
    archivos: ['evidencia.json'],
    riesgos_conocidos: ['r1'],
  };
}

test('el informe V1 sigue el formato histórico y se declara borrador', () => {
  const md = generarInforme(evidenciaFicticia(1), { versiones: [] }, GRUPO, CASOS);
  assert.match(md, new RegExp(`^# ${GRUPO.id} — EVALUACIÓN V1`));
  for (const s of ['## DECISIÓN GENERAL (PROPUESTA)', '## ENTORNO', '## RESULTADOS POR CASO', '## HALLAZGOS', '## SANDBOX Y ROLLBACK', 'BORRADOR TÉCNICO']) assert.ok(md.includes(s), s);
  for (const c of CASOS) assert.ok(md.includes(c.id));
  assert.ok(!md.includes('## ANTECEDENTES'));
  assert.ok(md.includes('Valor físicamente válido y fuera del rango operativo'));
  assert.ok(md.includes(`${CASOS[0].id.slice(-3)} Dashboard Productor`));
});

test('el informe incluye la plantilla de investigación cuando hay fallos', () => {
  const ev = evidenciaFicticia(1);
  ev.resultado_propuesto.casos[0] = veredictoCaso(caso168, fallar(todos(caso168), A1));
  const md = generarInforme(ev, { versiones: [] }, GRUPO, CASOS);
  assert.ok(md.includes('Investigación de cada fallo'));
  assert.ok(md.includes(`| ${caso168.id} | ${A1} | ASSERT | PRODUCTO |`));
});

test('PLAN de G88: los valores fijos de la matriz caben en los rangos físicos y el plan exige especie aislada', () => {
  const ctx = { variables: { 9: { valor_fisico_min: -40, valor_fisico_max: 60 }, 10: { valor_fisico_min: 0, valor_fisico_max: 100 } } };
  assert.deepEqual(PLAN.derivar(ctx).bloqueos, []);
  assert.ok(PLAN.derivar({ variables: { ...ctx.variables, 9: { valor_fisico_min: 25, valor_fisico_max: 60 } } }).bloqueos.length > 0);
  assert.deepEqual(PLAN.especie.requisitos, ['sin_gateway', 'sin_umbral:9', 'sin_umbral:10', 'sin_metricas_obligatorias_individual']);
  assert.equal(PLAN.activo, true);
  // Un sensor por lectura (el dashboard muestra la última lectura de cada sensor).
  const claves = PLAN.sensores.map((s) => s.clave);
  assert.equal(new Set(claves).size, claves.length);
  assert.ok(PLAN.sensores.every((s) => s.calibrar));
});

test('la colección de G88 configura cada umbral antes de sus lecturas y consulta el dashboard antes de reconfigurar', async () => {
  const coleccion = JSON.parse(fs.readFileSync(new URL('./TC-M03-G88.postman_collection.json', import.meta.url), 'utf8'));
  const nombres = coleccion.item.flatMap((f) => f.item).map((i) => i.name);
  const pos = (n) => nombres.indexOf(n);
  const umbrales = nombres.filter((n) => /umbral/i.test(n) && /Registrar|Reconfigurar/.test(n));
  assert.equal(umbrales.length, 6);
  // Entre dos reconfiguraciones siempre hay una consulta del dashboard.
  for (let k = 1; k < umbrales.length; k += 1) {
    const entre = nombres.slice(pos(umbrales[k - 1]) + 1, pos(umbrales[k]));
    assert.ok(entre.some((n) => /Dashboard/.test(n)), `sin dashboard entre «${umbrales[k - 1]}» y «${umbrales[k]}»`);
  }
  // TC-M03-266: misma lectura consultada antes y después de reconfigurar, sin lectura nueva en medio.
  const iIni = pos('266 Dashboard Productor (umbral inicial 10-20)');
  const iFin = pos('266 Dashboard Productor (umbral reconfigurado 20-30)');
  assert.ok(iIni >= 0 && iFin > iIni);
  assert.ok(!nombres.slice(iIni + 1, iFin).some((n) => /Lectura/.test(n)));
});

test('el informe de reevaluación incluye antecedentes y comparación por caso', () => {
  const d = tmp();
  try {
    escribirRun(d, 1, 'G88-EVAL-V1-20261020-080000', ESTADOS_RUN.CONCLUIDA, CASOS.map((c, i) => [c.id, i === CASOS.length - 1 ? 'RECHAZADO' : 'BLOQUEADO']));
    const md = generarInforme(evidenciaFicticia(2), inspeccionarHistorial(d), GRUPO, CASOS);
    assert.match(md, new RegExp(`^# ${GRUPO.id} — REEVALUACIÓN V2`));
    assert.ok(md.includes('## ANTECEDENTES'));
    assert.ok(md.includes('## COMPARACIÓN POR CASO'));
    assert.ok(md.includes(`| ${CASOS[CASOS.length - 1].id} | RECHAZADO | APROBADO | Defecto corregido (verificar) |`));
  } finally { limpiar(d); }
});

// ---- Invocación segura de Cypress (corrección de configFile: false) -------------------------------
import { archivoConfiguracion, opcionesCypress, destinosDiferenciados, aislamientoVerificacion, urls } from './cypress_seguro.mjs';
import { fileURLToPath as aRutaG88 } from 'node:url';
const DIR_G88 = path.dirname(aRutaG88(import.meta.url));
const RAIZ_G88 = path.resolve(DIR_G88, '../../../../..');
const SPEC_G88 = path.join(DIR_G88, 'tc_m03_g88.cy.js');
const CFG_G88 = archivoConfiguracion(DIR_G88, 'g88');
const PROXY_G88 = { HTTP_PROXY: 'http://127.0.0.1:9', HTTPS_PROXY: 'http://127.0.0.1:9' };

test('Cypress: proyecto = carpeta del grupo con su archivo propio; anulaciones en e2e; frontend como baseUrl', () => {
  const o = opcionesCypress({ dirGrupo: DIR_G88, spec: SPEC_G88, configFile: CFG_G88, baseUrl: 'https://front.test.example', capturas: 'c', descargas: 'd', env: { API_BASE: 'https://api.test.example' } });
  assert.equal(o.project, DIR_G88);
  assert.equal(path.resolve(o.project, o.configFile), CFG_G88);
  assert.notEqual(o.configFile, false);
  assert.equal(o.config.baseUrl, undefined);
  assert.equal(o.config.e2e.baseUrl, 'https://front.test.example');
  assert.notEqual(o.config.e2e.baseUrl, o.env.API_BASE);
  assert.equal(path.resolve(o.project, o.config.e2e.specPattern), SPEC_G88);
  assert.deepEqual([o.reporter, o.config.e2e.reporter, o.config.e2e.screenshotOnRunFailure, o.config.e2e.screenshotsFolder, o.config.e2e.downloadsFolder], ['spec', 'spec', false, 'c', 'd']);
});
test('Cypress: el archivo de configuración del grupo existe, apunta al spec y no contiene destinos', () => {
  const cfg = require_G88(CFG_G88);
  assert.deepEqual(urls(cfg), []);
  assert.equal(path.resolve(DIR_G88, cfg.e2e.specPattern), SPEC_G88);
  assert.equal(cfg.e2e.baseUrl, undefined);
  assert.ok(!/configFile:\s*false,/.test(fs.readFileSync(path.join(DIR_G88, 'ejecutar_tc_m03_g88.mjs'), 'utf8')), 'el ejecutor ya no usa configFile: false');
});
test('Destinos diferenciados: frontend y API HTTPS y distintos', () => {
  assert.equal(destinosDiferenciados('https://front.test', 'https://api.test'), true);
  assert.equal(destinosDiferenciados('https://api.test/', 'https://api.test'), false);
  assert.equal(destinosDiferenciados('http://front.test', 'https://api.test'), false);
  assert.equal(destinosDiferenciados('', 'https://api.test'), false);
});
test('Verificación local aislada: detecta configuración raíz, URL remota, CYPRESS_*, falta de proxy y ELECTRON_RUN_AS_NODE', () => {
  const ok = opcionesCypress({ dirGrupo: DIR_G88, spec: SPEC_G88, configFile: CFG_G88, baseUrl: null, env: {} });
  assert.deepEqual(aislamientoVerificacion({ raiz: RAIZ_G88, opciones: ok, entorno: PROXY_G88 }), []);
  const m = (o, e = PROXY_G88) => aislamientoVerificacion({ raiz: RAIZ_G88, opciones: o, entorno: e }).join(' | ');
  assert.match(m({ ...ok, project: RAIZ_G88, configFile: 'cypress.config.cjs' }), /archivo propio del grupo/);
  assert.match(m({ ...ok, config: { e2e: { ...ok.config.e2e, baseUrl: 'https://api.inmero.co' } } }), /no loopback|baseUrl/);
  assert.match(m({ ...ok, env: { API_BASE: 'https://api.inmero.co' } }), /no loopback/);
  assert.match(m(ok, {}), /PROXY/);
  assert.match(m(ok, { ...PROXY_G88, CYPRESS_baseUrl: 'https://api.inmero.co' }), /CYPRESS_baseUrl/);
  assert.match(m(ok, { ...PROXY_G88, ELECTRON_RUN_AS_NODE: '1' }), /ELECTRON_RUN_AS_NODE/);
});
import { createRequire as crearRequireG88 } from 'node:module';
const require_G88 = crearRequireG88(import.meta.url);
