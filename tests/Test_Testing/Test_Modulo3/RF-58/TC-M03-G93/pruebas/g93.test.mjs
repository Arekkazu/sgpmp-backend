import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { CAPACIDADES, CONSULTAS_DIAGNOSTICO, evaluarApi, candidataV2,
  revisarCandidataV2, clasificar } from '../lib/g93_escenario.mjs';
import { comprobar, evaluar, diagnostico, baseAlternativaTest, buscarCandidataV2, transporte, preflight, leerEnv, prevalidar,
  registrar, serializarResultado, resolverCliNewman, invocarNewman, newman,
  invocarCypressLocal, cypress } from '../g93.mjs';
import { evaluarRegistro } from '../lib/registro_local.mjs';
import { sanearArtefacto } from '../lib/seguridad.mjs';
import uiReglas from '../lib/g93_ui.cjs';
const { mensajeAusenciaEquivalente, observacionDocumental, clasificarCarga, evaluarOraculoUi, intentarDesactivarAuto } = uiReglas;

const DIR = path.dirname(fileURLToPath(import.meta.url));
const GRUPO = path.dirname(DIR);
const RUN = 'RUN-G93-V1-20261025-090000';
test('ensayo real solo admite contexto temporal, loopback y RUN ENSAYO', () => {
  const temporal = fs.mkdtempSync(path.join(os.tmpdir(), 'g93-gate-'));
  const carpeta = path.join(temporal, 'cypress');
  const runId = 'ENSAYO-G93-20261025-090000-v1';
  const contexto = path.join(temporal, 'contexto_operacion.json');
  fs.writeFileSync(contexto, JSON.stringify({ run_id: runId }));
  const base = 'http://127.0.0.1:32123';
  const variables = { CYPRESS_ENSAYO_G93_SPEC_REAL: 'SI', CYPRESS_ENSAYO_CONTEXTO_TEMPORAL: 'SI',
    CYPRESS_ENSAYO_CONTEXTO_RUTA: contexto, CYPRESS_RUN_ID: runId,
    CYPRESS_API_BASE: base, CYPRESS_FRONT_BASE: base, CYPRESS_ARTIFACTS_DIR: carpeta };
  const spawn = () => ({ status: 1, signal: null, error: null, stdout: '1 failing', stderr: '' });
  try {
    assert.throws(() => invocarCypressLocal({ carpeta, env: { ...variables,
      CYPRESS_RUN_ID: RUN }, spawn }), /ENSAYO_SPEC_REAL_FUERA_DE_TEMPORAL/);
    assert.throws(() => invocarCypressLocal({ carpeta, env: { ...variables,
      CYPRESS_API_BASE: env.SIGAB_API_TEST_BASE }, spawn }), /ENSAYO_SPEC_REAL_FUERA_DE_TEMPORAL/);
    const resultado = invocarCypressLocal({ carpeta, env: variables, spawn });
    assert.equal(resultado.diagnostico.codigo_salida, 1);
    assert.equal(resultado.args[resultado.args.indexOf('--spec') + 1], path.join(GRUPO, 'g93.cy.js'));
    assert.match(fs.readFileSync(path.join(GRUPO, 'g93.cypress.config.cjs'), 'utf8'),
      /trashAssetsBeforeRuns: false/);
    const invocar = ({ carpeta: destino, prefijo }) => {
      const fase = prefijo.endsWith('V1') ? 'V1' : 'V2';
      fs.mkdirSync(destino, { recursive: true });
      fs.writeFileSync(path.join(destino, `UI-184-${fase}.json`), JSON.stringify({
        estado: 'RECHAZADO', criterio: 'ORACULO_UI_INCUMPLIDO', motivo: 'local', peticiones: [] }));
      return { proceso: { status: fase === 'V1' ? 0 : 1, error: null } };
    };
    const parametros = fase => ({ fase, id: 93, nombre: 'Local', fecha: null,
      base, front: base, cookie: 'LOCAL', secreto: 'LOCAL', invocar });
    assert.equal(cypress({ directorio: temporal, runId }, parametros('V1')).estado, 'RECHAZADO');
    const v1 = fs.readFileSync(path.join(carpeta, 'UI-184-V1.json'), 'utf8');
    const uiV2 = cypress({ directorio: temporal, runId }, parametros('V2'));
    assert.equal(uiV2.estado, 'ERROR_QA');
    assert.equal(uiV2.proceso_fallido, true);
    assert.equal(fs.readFileSync(path.join(carpeta, 'UI-184-V1.json'), 'utf8'), v1);
  } finally { fs.rmSync(temporal, { recursive: true, force: true }); }
});
const env = { SIGAB_API_TEST_BASE: 'https://www.api.inmero.co/api-sgpmp-test',
  SIGAB_FRONT_TEST_URL: 'https://api.inmero.co/sigab-test', QA_SANDBOX_SECRET: 'falso-local',
  QA_ADMIN_EMAIL: 'admin@example.test', QA_ADMIN_PASSWORD: 'clave-local',
  QA_PROD_EMAIL: 'prod@example.test', QA_PROD_PASSWORD: 'clave-local', QA_AUTORIZADO: 'SI' };
const respuesta = (http, cuerpo, { run = true, cookie = null } = {}) => ({ status: http,
  headers: { get: k => k.toLowerCase() === 'x-test-run-id' ? run ? RUN : null
    : k.toLowerCase() === 'set-cookie' ? cookie : null }, json: async () => cuerpo });

test('Cypress 14 usa configuración propia, conserva salida saneada y falla técnicamente sin acta', () => {
  const temporal = fs.mkdtempSync(path.join(os.tmpdir(), 'g93-cy-(local)-'));
  const carpeta = path.join(temporal, 'cypress');
  const secreto = 'SECRETO_LOCAL_XYZ';
  const cookie = 'COOKIE_LOCAL_XYZ';
  const jwt = 'eyJaaaaaa.bbbbbbb.cccccccc';
  let llamada;
  const spawn = (exe, args, opciones) => {
    llamada = { exe, args, opciones };
    return { status: 1, signal: null, error: null,
      stdout: `error ${secreto} refresh_token=${cookie} admin@example.test ${jwt}`,
      stderr: `password=clave-local ${cookie}` };
  };
  try {
    const ejecutar = opciones => invocarCypressLocal({ ...opciones, spawn,
      secretos: [secreto, cookie, 'clave-local'] });
    const ui = cypress({ directorio: temporal, runId: RUN }, {
      fase: 'V1', id: 900, nombre: 'Local', fecha: null,
      base: 'https://api.inmero.co/api-sgpmp-test',
      front: env.SIGAB_FRONT_TEST_URL, cookie, secreto, secretos: [secreto, cookie, 'clave-local'],
      invocar: ejecutar });
    assert.equal(ui.estado, 'ERROR_QA');
    assert.equal(ui.ejecutadas, 0);
    assert.equal(ui.proceso_fallido, true);
    assert.match(ui.motivo, /diagnostico\.json/);
    assert.equal(fs.existsSync(path.join(temporal, ui.rel)), true);
    assert.equal(fs.existsSync(path.join(temporal, ui.log_rel)), true);
    const diagnostico = JSON.parse(fs.readFileSync(path.join(temporal, ui.rel), 'utf8'));
    const log = fs.readFileSync(path.join(temporal, ui.log_rel), 'utf8');
    assert.equal(diagnostico.codigo_salida, 1);
    assert.equal(diagnostico.navegador, 'chrome');
    assert.equal(diagnostico.version_cypress, '14.5.4');
    assert.equal(diagnostico.cwd, GRUPO);
    assert.equal(diagnostico.error_spawn, null);
    assert.ok(diagnostico.duracion_ms >= 0);
    assert.equal(llamada.exe, process.execPath);
    assert.equal(llamada.opciones.shell, false);
    assert.equal(llamada.opciones.timeout, 150000);
    assert.equal(llamada.opciones.encoding, 'utf8');
    assert.equal(llamada.opciones.env.CYPRESS_API_BASE, 'https://api.inmero.co/api-sgpmp-test');
    assert.equal(llamada.opciones.env.CYPRESS_FRONT_BASE, env.SIGAB_FRONT_TEST_URL);
    assert.equal(llamada.args[1], 'run');
    assert.equal(llamada.args[llamada.args.indexOf('--config-file') + 1],
      path.join(GRUPO, 'g93.cypress.config.cjs'));
    assert.equal(llamada.args[llamada.args.indexOf('--spec') + 1], path.join(GRUPO, 'g93.cy.js'));
    assert.deepEqual(llamada.args.slice(-3), ['--browser', 'chrome', '--headless']);
    assert.doesNotMatch(JSON.stringify(llamada.args), /--config-file[" ,]+false/);
    assert.doesNotMatch(log + JSON.stringify(diagnostico),
      /SECRETO_LOCAL_XYZ|COOKIE_LOCAL_XYZ|clave-local|admin@example\.test|eyJaaaaaa/);
    assert.match(log, /STDOUT[\s\S]*STDERR/);
    const r = { run_id: RUN, version: 1, casos: { 'TC-M03-184': { estado: 'NO_CONCLUYENTE' } },
      comprobaciones: [], cypress: { total_pruebas: 0 }, evidencias: [ui.rel, ui.log_rel],
      cierre: { run: { cierre_http: null }, rollback: { verificado: false } }, oficial: false };
    registrar(r, 'UI-184-01', 'UI', ui.estado, ui.motivo, ui.rel);
    const revision = evaluarRegistro(r, temporal, { runId: RUN, version: 1 });
    assert.equal(revision.estructura, true);
    assert.equal(revision.evidencias, true);
    assert.equal(revision.oficialPosible, false);
    const sinProceso = invocarCypressLocal({ carpeta: path.join(temporal, 'eprem'),
      prefijo: 'spawn', secretos: [secreto], spawn: () => ({ status: null,
        signal: null, error: Object.assign(new Error(`spawn ${secreto}`), { code: 'EPERM' }),
        stdout: '', stderr: '' }) });
    assert.equal(sinProceso.diagnostico.error_spawn.codigo, 'EPERM');
    assert.equal(sinProceso.diagnostico.codigo_salida, null);
    assert.doesNotMatch(fs.readFileSync(path.join(temporal, 'eprem', 'spawn.diagnostico.json'), 'utf8'),
      /SECRETO_LOCAL_XYZ/);
  } finally { fs.rmSync(temporal, { recursive: true, force: true }); }
});

test('diagnóstico Cypress sanea también la cookie rotada durante el proceso', () => {
  const temporal = fs.mkdtempSync(path.join(os.tmpdir(), 'g93-cookie-log-'));
  const carpeta = path.join(temporal, 'cypress');
  const cookieFile = path.join(temporal, 'refresh-cookie.txt');
  const rotada = 'COOKIE_ROTADA_LOCAL';
  try {
    invocarCypressLocal({ carpeta, env: { CYPRESS_REFRESH_COOKIE_FILE: cookieFile },
      secretos: ['COOKIE_ORIGINAL_LOCAL'], spawn: () => {
        fs.writeFileSync(cookieFile, rotada);
        return { status: 1, signal: null, error: null, stdout: rotada, stderr: rotada };
      } });
    const log = fs.readFileSync(path.join(carpeta, 'UI-184-V1.diagnostico.log'), 'utf8');
    const diagnostico = fs.readFileSync(path.join(carpeta, 'UI-184-V1.diagnostico.json'), 'utf8');
    assert.doesNotMatch(log + diagnostico, /COOKIE_ROTADA_LOCAL|COOKIE_ORIGINAL_LOCAL/);
    assert.match(log, /\[REDACTADO\]/);
  } finally { fs.rmSync(temporal, { recursive: true, force: true }); }
});

test('Newman usa el mismo CLI Node sin shell en prevalidación y ejecución', () => {
  const temporal = fs.mkdtempSync(path.join(os.tmpdir(), 'g93-cli (local)-'));
  const global = path.join(temporal, 'npm global (QA)');
  const cli = path.join(global, 'node_modules', 'newman', 'bin', 'newman.js');
  const runDir = path.join(temporal, 'RUN (local)');
  const llamadas = [];
  try {
    fs.mkdirSync(path.dirname(cli), { recursive: true });
    fs.mkdirSync(runDir);
    fs.writeFileSync(path.join(global, 'newman.cmd'), 'shim local');
    fs.writeFileSync(cli, 'script local');
    assert.equal(resolverCliNewman(global, temporal), cli);
    const backend = path.join(temporal, 'backend (local)');
    const dependencia = path.join(backend, 'node_modules', 'newman');
    fs.mkdirSync(path.join(dependencia, 'bin'), { recursive: true });
    fs.writeFileSync(path.join(dependencia, 'package.json'), '{"name":"newman","version":"0.0.0"}');
    fs.writeFileSync(path.join(dependencia, 'bin', 'newman.js'), 'script local');
    assert.equal(resolverCliNewman(path.join(temporal, 'sin cli'), backend),
      path.join(dependencia, 'bin', 'newman.js'));
    assert.throws(() => resolverCliNewman(path.join(temporal, 'sin cli'), temporal),
      /NEWMAN_CLI_NO_RESUELTO/);
    const spawn = (exe, args, opciones) => {
      llamadas.push({ exe, args, opciones });
      if (args[1] === 'run') {
        const reporte = args[args.indexOf('--reporter-json-export') + 1];
        fs.writeFileSync(reporte, JSON.stringify({ run: { executions: [{
          response: { code: 200, stream: { data: [] }, header: [] } }], failures: [] } }));
      }
      return { status: 0 };
    };
    const invocar = (args, timeout, opciones = {}) =>
      invocarNewman(args, timeout, { cli: opciones.cli ?? cli, spawn });
    const barrera = prevalidar({ ...env, PATH: global },
      { resolver: () => cli, invocar });
    assert.equal(barrera.herramientas.newman, true);
    assert.equal(barrera.diagnostico_herramientas.newman.status, 0);
    assert.ok(barrera.diagnostico_herramientas.newman.duracion_ms >= 0);
    const token = 'TOKEN_LOCAL_SECRETO';
    const secreto = 'SECRETO_LOCAL';
    const salida = newman({ runId: RUN, directorio: runDir }, {
      fase: 'V1', id: 900, base: env.SIGAB_API_TEST_BASE,
      token, secreto, secretos: [token, secreto], invocar, tempDir: temporal });
    assert.equal(salida.http, 200);
    assert.equal(llamadas.length, 2);
    assert.deepEqual(llamadas[0], { exe: process.execPath, args: [cli, '--version'],
      opciones: { encoding: 'utf8', shell: false, timeout: 30000 } });
    const ejecucion = llamadas[1];
    assert.equal(ejecucion.exe, process.execPath);
    assert.deepEqual(ejecucion.args.slice(0, 3), [cli, 'run', path.join(GRUPO, 'G93.postman_collection.json')]);
    assert.deepEqual(ejecucion.opciones, { encoding: 'utf8', shell: false, timeout: 45000 });
    assert.equal(ejecucion.args[ejecucion.args.indexOf('-e') + 1].includes(' '), true);
    assert.equal(ejecucion.args[ejecucion.args.indexOf('-e') + 1].includes('('), true);
    assert.equal(ejecucion.args[ejecucion.args.indexOf('--reporter-json-export') + 1].includes('('), true);
    assert.deepEqual(ejecucion.args.slice(-4), ['--timeout-request', '30000', '--color', 'off']);
    assert.equal(JSON.stringify(llamadas).includes(token), false);
    assert.equal(JSON.stringify(llamadas).includes(secreto), false);
    const runner = fs.readFileSync(path.join(GRUPO, 'g93.mjs'), 'utf8');
    assert.doesNotMatch(runner, /spawnSync\(['"]newman(?:\.cmd)?['"]/);
    assert.doesNotMatch(runner, /shell:\s*true|shell:\s*process\.platform\s*===\s*['"]win32['"]/);
    const sinCli = prevalidar({ ...env, PATH: path.join(temporal, 'sin cli') },
      { resolver: () => resolverCliNewman(path.join(temporal, 'sin cli'), temporal), invocar });
    assert.equal(sinCli.valido, false);
    assert.equal(sinCli.barreras.includes('NEWMAN_CLI_NO_RESUELTO'), true);
    assert.equal(sinCli.barreras.includes('HERRAMIENTA_NEWMAN_AUSENTE'), true);
    assert.equal(sinCli.herramientas.newman, false);
    assert.equal(llamadas.length, 2);
    assert.throws(() => newman({ runId: RUN, directorio: runDir }, {
      fase: 'V2', id: 900, base: env.SIGAB_API_TEST_BASE,
      token, secreto, secretos: [token, secreto],
      invocar: args => invocarNewman(args, 45000, {
        cli: resolverCliNewman(path.join(temporal, 'sin cli'), temporal), spawn })
    }), /NEWMAN_CLI_NO_RESUELTO/);
  } finally { fs.rmSync(temporal, { recursive: true, force: true }); }
});

test('prevalidar distingue timeout, status y éxito con diagnóstico saneado de Newman y Cypress', () => {
  const secreto = 'SECRETO_LOCAL_XYZ';
  const proceso = { ...env, QA_SANDBOX_SECRET: secreto };
  const opciones = {
    resolver: () => 'newman-local.js', resolverCypress: () => 'cypress-local.js',
    invocarCypress: (exe, args, opts) => {
      assert.equal(exe, process.execPath);
      assert.deepEqual(args, ['cypress-local.js', '--version']);
      assert.equal(opts.timeout, 30000);
      return { status: 0, stdout: 'Cypress package version: 14.5.4', stderr: '' };
    },
  };
  const vencido = prevalidar(proceso, { ...opciones, invocar: (args, timeout) => {
    assert.deepEqual(args, ['--version']);
    assert.equal(timeout, 30000);
    return { status: null, signal: 'SIGTERM',
      error: Object.assign(new Error(`proceso ${secreto}`), { code: 'ETIMEDOUT' }),
      stdout: '', stderr: `timeout ${secreto}` };
  } });
  assert.equal(vencido.valido, false);
  assert.equal(vencido.herramientas.newman, false);
  assert.ok(vencido.barreras.includes('HERRAMIENTA_NEWMAN_AUSENTE'));
  assert.ok(vencido.barreras.includes('HERRAMIENTA_NEWMAN_TIMEOUT'));
  assert.equal(vencido.diagnostico_herramientas.newman.error_code, 'ETIMEDOUT');
  assert.equal(vencido.diagnostico_herramientas.newman.signal, 'SIGTERM');
  assert.equal(vencido.diagnostico_herramientas.newman.vencio_tiempo, true);
  const fallido = prevalidar(proceso, { ...opciones, invocar: (_args, timeout) => {
    assert.equal(timeout, 30000);
    return { status: 9, stdout: '', stderr: `fallo ${secreto}\nC:\\Users\\privado\\cli.js` };
  } });
  assert.ok(fallido.barreras.includes('HERRAMIENTA_NEWMAN_STATUS_9'));
  assert.equal(fallido.diagnostico_herramientas.newman.status, 9);
  assert.match(fallido.diagnostico_herramientas.newman.stderr, /\[REDACTADO\]/);
  assert.match(fallido.diagnostico_herramientas.newman.stderr, /\[RUTA_REDACTADA\]/);
  const correcto = prevalidar(proceso, { ...opciones, invocar: (_args, timeout) => {
    assert.equal(timeout, 30000);
    return { status: 0, stdout: 'newman 6.2.1', stderr: '' };
  } });
  assert.equal(correcto.herramientas.newman, true);
  assert.equal(correcto.diagnostico_herramientas.newman.version, '6.2.1');
  assert.equal(correcto.diagnostico_herramientas.cypress.version, '14.5.4');
  assert.ok(correcto.diagnostico_herramientas.newman.duracion_ms >= 0);
  assert.doesNotMatch(JSON.stringify([vencido, fallido, correcto]), /SECRETO_LOCAL_XYZ|privado/);
});

test('preflight conserva diagnóstico y aborta antes de cualquier solicitud', async () => {
  const temporal = fs.mkdtempSync(path.join(os.tmpdir(), 'g93-preflight-local-'));
  const directorio = path.join(temporal, 'ENSAYO-G93-PREFLIGHT');
  let peticiones = 0;
  try {
    const barrera = prevalidar(env, {
      resolver: () => 'newman-local.js', invocar: () => ({ status: null,
        error: Object.assign(new Error('local'), { code: 'ETIMEDOUT' }) }),
      resolverCypress: () => 'cypress-local.js', invocarCypress: () => ({ status: 0,
        stdout: 'Cypress package version: 14.5.4' }),
    });
    const r = await evaluar({ operacion: 'evaluar', version: 1, runId: 'ENSAYO-G93-PREFLIGHT',
      referencia: 'LOCAL', directorio }, { env, validarHerramientas: true,
      prevalidarHerramientas: () => barrera, fetcher: () => { peticiones++; throw Error('RED_PROHIBIDA'); } });
    const previo = JSON.parse(fs.readFileSync(path.join(directorio, 'preflight.json'), 'utf8'));
    assert.equal(previo.diagnostico_herramientas.newman.vencio_tiempo, true);
    assert.ok(previo.barreras.includes('HERRAMIENTA_NEWMAN_TIMEOUT'));
    assert.equal(previo.herramientas.newman, false);
    assert.equal(previo.ok, false);
    assert.equal(r.casos['TC-M03-184'].estado, 'NO_EJECUTADA');
    assert.equal(r.codigo_salida, 2);
    assert.equal(peticiones, 0);
  } finally { fs.rmSync(temporal, { recursive: true, force: true }); }
});

test('contrato local y oráculos API sin acomodar resultados del código', () => {
  assert.equal(comprobar(), 0);
  assert.equal(CAPACIDADES.contrato, 'sigab-qa-ejecutor/1');
  assert.deepEqual(CAPACIDADES.comprobaciones_obligatorias['TC-M03-184'].UI,
    ['UI-184-01', 'UI-184-02']);
  assert.equal(evaluarApi('V1', { http: 200, cuerpo: { sensores: [], resumen_unidades: [] } }, 900).estado, 'RECHAZADO');
  assert.equal(evaluarApi('V1', { http: 200, cuerpo: { sensores: [], resumen_unidades: [
    { id_infraestructura: 900, estado_general: 'SIN_DATOS', ultimo_dato_recibido: null }] } }, 900).estado, 'RECHAZADO');
  assert.equal(evaluarApi('V1', { http: 500 }, 900).estado, 'RECHAZADO');
  assert.equal(candidataV2({ http: 200, cuerpo: { resumen_unidades: [], sensores: [] } }, 349,
    { fincasVisibles: [184] }), false);
  const v2 = { http: 200, cuerpo: { resumen_unidades: [{ id_infraestructura: 349,
    id_finca: 184, estado_general: 'GRIS', total_sensores: 1, ultimo_dato_recibido: '2026-10-20T10:00:00Z' }],
  sensores: [{ id_infraestructura: 349, estado_conectividad: 'SIN_SEÑAL', dato_desactualizado: true,
    tiempo_sin_reporte_min: 30, ultimo_timestamp_captura: '2026-10-20T10:00:00Z' }] } };
  assert.equal(candidataV2(v2, 349, { fincasVisibles: [184] }), true);
  assert.equal(evaluarApi('V2', v2, 349).estado, 'APROBADO');
  v2.cuerpo.sensores[0].dato_desactualizado = false;
  assert.equal(candidataV2(v2, 349, { fincasVisibles: [184] }), true);
  assert.equal(clasificar([], { candidata: false, cierreVerificado: true }).estado, 'BLOQUEADO');
  assert.equal(clasificar([{ tipo: 'ASSERT', estado: 'RECHAZADO' }],
    { candidata: false, cierreVerificado: true }).estado, 'RECHAZADO');
  assert.equal(clasificar(CAPACIDADES.comprobaciones_obligatorias['TC-M03-184'].API
    .concat(CAPACIDADES.comprobaciones_obligatorias['TC-M03-184'].UI)
    .map(id => ({ id, tipo: 'ASSERT', estado: 'APROBADO' })),
  { candidata: true, cierreVerificado: true }).estado, 'APROBADO');
  assert.equal(clasificar([], { candidata: true, cierreVerificado: false }).estado, 'BLOQUEADO');
});

test('selección V2 usa conectividad de todos los sensores y finca visible', () => {
  const unidad = { id_infraestructura: 349, id_finca: 184, total_sensores: 1 };
  const sensor = { id_infraestructura: 349, estado_conectividad: 'SIN_SEÑAL' };
  const respuestaV2 = { http: 200, cuerpo: { resumen_unidades: [unidad], sensores: [sensor] } };
  assert.equal(candidataV2(respuestaV2, 349, { fincasVisibles: [184] }), true);
  assert.equal(revisarCandidataV2(respuestaV2, 349, { fincasVisibles: [184] }).ultimo_dato_recibido, null);
  assert.equal(revisarCandidataV2(respuestaV2, 349, { fincasVisibles: [80] }).motivo, 'finca_no_visible');
  assert.equal(revisarCandidataV2(respuestaV2, 349, { fincasVisibles: [184], idAreaV1: 349 }).motivo, 'area_v1');
  unidad.total_sensores = 0; respuestaV2.cuerpo.sensores = [];
  assert.equal(revisarCandidataV2(respuestaV2, 349, { fincasVisibles: [184] }).motivo, 'sin_sensores');
  unidad.total_sensores = 1; respuestaV2.cuerpo.sensores = [{ ...sensor, estado_conectividad: 'ACTIVO' }];
  assert.equal(revisarCandidataV2(respuestaV2, 349, { fincasVisibles: [184] }).motivo, 'sensor_fuera_estados_sin_comunicacion');
  assert.equal(revisarCandidataV2({ http: 503 }, 349, { fincasVisibles: [184] }).motivo, 'http_503');
});

test('API-184-03 evalúa tres INACTIVO con tiempo sin reporte cero o nulo', () => {
  const sensor = tiempo_sin_reporte_min => ({ id_infraestructura: 1,
    estado_conectividad: 'INACTIVO', dato_desactualizado: true, tiempo_sin_reporte_min });
  const respuestaV2 = { http: 200, cuerpo: {
    resumen_unidades: [{ id_infraestructura: 1, id_finca: 184,
      estado_general: 'GRIS', total_sensores: 3 }],
    sensores: [sensor(0), sensor(null), sensor(0)],
  } };
  const revision = revisarCandidataV2(respuestaV2, 1, { fincasVisibles: [184] });
  assert.equal(revision.motivo, 'aceptada');
  assert.deepEqual(revision.tiempo_sin_reporte_min, { 0: 2, NO_INFORMADO: 1 });
  assert.equal(evaluarApi('V2', respuestaV2, 1).estado, 'APROBADO');
  const coleccion = JSON.parse(fs.readFileSync(path.join(GRUPO, 'G93.postman_collection.json'), 'utf8'));
  const script = coleccion.item[0].event[0].script.exec.join('\n');
  assert.doesNotMatch(script, /tiempo_sin_reporte_min/);
  respuestaV2.cuerpo.sensores[2] = { ...sensor(0), estado_conectividad: 'ACTIVO' };
  assert.equal(revisarCandidataV2(respuestaV2, 1, { fincasVisibles: [184] }).motivo,
    'sensor_fuera_estados_sin_comunicacion');
  assert.equal(evaluarApi('V2', respuestaV2, 1).estado, 'NO_CONCLUYENTE');
});

test('decisión QA: estados originales, mezclas permitidas y fecha histórica opcional', () => {
  const unidad = { id_infraestructura: 1, id_finca: 184, estado_general: 'GRIS', total_sensores: 2 };
  const sensor = estado_conectividad => ({ id_infraestructura: 1, estado_conectividad,
    dato_desactualizado: true, tiempo_sin_reporte_min: 30 });
  const respuestaV2 = { http: 200, cuerpo: { resumen_unidades: [unidad],
    sensores: [sensor('INACTIVO'), sensor('INACTIVO')] } };
  const revisar = () => revisarCandidataV2(respuestaV2, 1, { fincasVisibles: [184] });
  assert.equal(revisar().motivo, 'aceptada');
  assert.deepEqual(revisar().estados_originales, ['INACTIVO', 'INACTIVO']);
  assert.equal(evaluarApi('V2', respuestaV2, 1).estado, 'APROBADO');
  respuestaV2.cuerpo.sensores = [sensor('SIN_SEÑAL'), sensor('SIN_SEÑAL')];
  assert.equal(revisar().motivo, 'aceptada');
  respuestaV2.cuerpo.sensores[1] = sensor('INACTIVO');
  assert.equal(revisar().motivo, 'aceptada');
  assert.deepEqual(revisar().estados_originales, ['SIN_SEÑAL', 'INACTIVO']);
  unidad.ultimo_dato_recibido = '2026-10-20T10:00:00Z';
  assert.equal(evaluarApi('V2', respuestaV2, 1).estado, 'APROBADO');
  respuestaV2.cuerpo.sensores[1].ultimo_timestamp_captura = '2026-10-21T10:00:00Z';
  assert.equal(evaluarApi('V2', respuestaV2, 1).estado, 'RECHAZADO');
  delete unidad.ultimo_dato_recibido;
  for (const estado of ['ACTIVO', 'BUFFER_ACTIVO', 'EN_MANTENIMIENTO', 'DESCONOCIDO', null]) {
    respuestaV2.cuerpo.sensores[1] = sensor(estado);
    assert.equal(revisar().motivo, 'sensor_fuera_estados_sin_comunicacion');
    assert.deepEqual(revisar().estados_originales, ['SIN_SEÑAL', estado]);
  }
  unidad.total_sensores = 0; respuestaV2.cuerpo.sensores = [];
  assert.equal(revisar().motivo, 'sin_sensores');
  unidad.total_sensores = 2;
  assert.equal(revisarCandidataV2(respuestaV2, 1, { fincasVisibles: [] }).motivo, 'finca_no_visible');
  const coleccion = JSON.parse(fs.readFileSync(path.join(GRUPO, 'G93.postman_collection.json'), 'utf8'));
  const script = coleccion.item[0].event[0].script.exec.join('\n');
  assert.match(script, /\['SIN_SEÑAL','INACTIVO'\]/);
  assert.doesNotMatch(script, /ultimo_dato_recibido\)\.to\.be\.ok/);
});

test('descubrimiento por dispositivos agrupa IDs, pagina más de 50 y sanea seriales', async () => {
  const sensores = Array.from({ length: 51 }, () => ({ id_infraestructura: 349, estado_conectividad: 'SIN_SEÑAL' }));
  const rutas = [];
  const get = async ruta => {
    rutas.push(ruta);
    const pagina = Number(new URL(`https://local.invalid${ruta}`).searchParams.get('pagina'));
    return { http: 200, cuerpo: { resumen_unidades: [{ id_infraestructura: 349,
      id_finca: 184, total_sensores: 51 }], sensores: pagina === 1 ? sensores.slice(0, 50) : sensores.slice(50) } };
  };
  const opciones = { dispositivos: [{ id_infraestructura: 514, serial: 'SERIAL_PRIVADO' },
    { id_infraestructura: 349, serial: 'SERIAL_PRIVADO' }, { id_infraestructura: 349 }],
  fincasVisibles: [184], idAreaV1: 514, get };
  const encontrada = await buscarCandidataV2(opciones);
  assert.equal(encontrada.encontrada.id, 349);
  assert.deepEqual(encontrada.revisiones.map(x => x.motivo), ['area_v1', 'aceptada']);
  assert.deepEqual(rutas.map(x => new URL(`https://local.invalid${x}`).searchParams.get('pagina')), ['1', '2']);
  assert.equal(JSON.stringify(encontrada.revisiones).includes('SERIAL_PRIVADO'), false);
  const incompleta = await buscarCandidataV2({ ...opciones, maxPaginasAdicionales: 0 });
  assert.equal(incompleta.revisiones[1].motivo, 'paginacion_incompleta');
  assert.equal(revisarCandidataV2({ http: 200, cuerpo: { resumen_unidades: [{ id_infraestructura: 349,
    id_finca: 184, total_sensores: 51 }], sensores: sensores.slice(0, 50) } }, 349,
  { diagnostico: true }).motivo, 'paginacion_no_verificable_en_diagnostico');
});

test('diagnóstico respeta consultas y presupuesto; solo login escribe y no hay cabeceras RUN', async () => {
  const temporal = fs.mkdtempSync(path.join(os.tmpdir(), 'g93-diag-local-'));
  const llamadas = [];
  const consultas = CONSULTAS_DIAGNOSTICO.slice(0, 3);
  try {
    const resumen = await diagnostico({ referencia: 'REF_LOCAL', consultas, maxPeticiones: 3,
      env, directorio: temporal, ahora: new Date('2026-10-25T15:49:13Z'),
      fetcher: async (url, opciones) => {
        llamadas.push({ url, opciones });
        return { status: 200, json: async () => opciones.method === 'POST'
          ? { token: 'TOKEN_PRIVADO' } : { resumen_unidades: [{ id_infraestructura:
            Number(new URL(url).searchParams.get('id_infraestructura')), id_finca: 184,
            total_sensores: 1 }], sensores: [{ id_infraestructura:
            Number(new URL(url).searchParams.get('id_infraestructura')), estado_conectividad: 'SIN_SEÑAL' }] } };
      } });
    assert.equal(resumen.salida, 'diagnostico/DIAG-G93-20261025-154913');
    assert.equal(resumen.peticiones_realizadas, 3);
    assert.deepEqual(resumen.consultas, consultas);
    assert.deepEqual(JSON.parse(fs.readFileSync(path.join(temporal, resumen.salida,
      'bitacora_resumen.json'), 'utf8')), resumen);
    assert.equal(fs.readFileSync(path.join(temporal, resumen.salida,
      'bitacora_resumen.json'), 'utf8'), JSON.stringify(resumen));
    const candidatas = fs.readFileSync(path.join(temporal, resumen.salida, 'candidatas.json'), 'utf8');
    assert.equal(candidatas.includes('TOKEN_PRIVADO'), false);
    assert.deepEqual(JSON.parse(candidatas).candidatas.map(x => x.motivo), ['aceptada', 'aceptada']);
    assert.deepEqual(llamadas.map(x => x.opciones.method), ['POST', 'GET', 'GET']);
    assert.equal(llamadas.some(x => Object.keys(x.opciones.headers)
      .some(k => /X-Test-Run-Id|X-Sandbox-Secret/i.test(k))), false);
    assert.equal(JSON.stringify(llamadas.slice(1)).includes(env.QA_PROD_PASSWORD), false);
    await assert.rejects(diagnostico({ referencia: 'REF_LOCAL', consultas,
      maxPeticiones: 2, env, directorio: temporal }), /DIAGNOSTICO_LIMITE_INVALIDO/);
    await assert.rejects(diagnostico({ referencia: 'REF_LOCAL', consultas: [consultas[0],
      'GET /iot/dispositivos?estado=SIN_SEÑAL'], maxPeticiones: 2, env,
      directorio: temporal }), /DIAGNOSTICO_CONSULTAS_INVALIDAS/);
    const runner = fs.readFileSync(path.join(GRUPO, 'g93.mjs'), 'utf8');
    assert.match(runner, /console\.log\(JSON\.stringify\(resumen\)\)/);
  } finally { fs.rmSync(temporal, { recursive: true, force: true }); }
});

test('diagnóstico de autenticación registra ambos roles, HTTP adverso y comparación de base', async () => {
  const temporal = fs.mkdtempSync(path.join(os.tmpdir(), 'g93-auth-local-'));
  const llamadas = [];
  try {
    const resumen = await diagnostico({ referencia: 'REF_LOCAL', consultas: ['POST /sesiones/'],
      maxPeticiones: 4, env, directorio: temporal, ahora: new Date('2026-10-25T18:00:00Z'),
      fetcher: async (url, opciones) => {
        llamadas.push({ url, opciones });
        return { status: llamadas.length === 1 ? 401 : 503,
          headers: { get: () => null }, json: async () => ({ token: 'TOKEN_PRIVADO',
            correo_electronico: 'privado@example.test' }) };
      } });
    assert.deepEqual(llamadas.map(x => JSON.parse(x.opciones.body).correo_electronico),
      [env.QA_ADMIN_EMAIL, env.QA_PROD_EMAIL]);
    assert.equal(resumen.peticiones_realizadas, 2);
    assert.deepEqual(resumen.consultas, ['POST /sesiones/', 'POST /sesiones/']);
    assert.deepEqual(resumen.solicitudes.map(x => x.http), [401, 503]);
    assert.deepEqual(resumen.solicitudes.map(x => x.rol), ['Administrador', 'Productor']);
    assert.equal(resumen.comparacion_frontend.coincide, false);
    assert.deepEqual(resumen.comparacion_frontend.diferencias, ['host_con_sin_www']);
    assert.ok(resumen.solicitudes.every(x => x.base === 'principal'
      && x.host === 'www.api.inmero.co' && x.path_base === '/api-sgpmp-test'
      && x.con_token === true && x.con_cookie_refresco === false && x.duracion_ms >= 0));
    assert.ok(llamadas.every(x => x.opciones.method === 'POST'
      && x.opciones.signal && !Object.keys(x.opciones.headers).some(k => /sandbox|run-id/i.test(k))));
    const carpeta = path.join(temporal, resumen.salida);
    const bitacora = fs.readFileSync(path.join(carpeta, 'bitacora_resumen.json'), 'utf8');
    const auth = fs.readFileSync(path.join(carpeta, 'autenticacion.json'), 'utf8');
    assert.equal(bitacora, JSON.stringify(resumen));
    assert.deepEqual(JSON.parse(auth).solicitudes, resumen.solicitudes);
    assert.doesNotMatch(bitacora + auth, /TOKEN_PRIVADO|privado@example\.test|clave-local|admin@example\.test|prod@example\.test/);
  } finally { fs.rmSync(temporal, { recursive: true, force: true }); }
});

test('diagnóstico de autenticación limita el fallback a red/timeout, registra fallos y máximo cuatro', async () => {
  const temporal = fs.mkdtempSync(path.join(os.tmpdir(), 'g93-auth-fallback-'));
  const llamadas = [];
  try {
    const resumen = await diagnostico({ referencia: 'REF_LOCAL', consultas: ['POST /sesiones/'],
      maxPeticiones: 4, env, directorio: temporal, ahora: new Date('2026-10-25T18:00:01Z'),
      fetcher: async (url, opciones) => {
        llamadas.push({ url, opciones });
        if (llamadas.length === 1) throw Object.assign(new Error('TOKEN_PRIVADO'), { name: 'TimeoutError' });
        if (llamadas.length === 3) throw new TypeError('privado@example.test');
        return { status: 200, headers: { get: () => 'refresh_token=COOKIE_PRIVADA; HttpOnly' },
          json: async () => ({ token: 'TOKEN_PRIVADO' }) };
      } });
    assert.equal(resumen.peticiones_realizadas, 4);
    assert.deepEqual(resumen.consultas, Array(4).fill('POST /sesiones/'));
    assert.deepEqual(resumen.solicitudes.map(x => [x.rol, x.base, x.http]), [
      ['Administrador', 'principal', null], ['Administrador', 'alternativa', 200],
      ['Productor', 'principal', null], ['Productor', 'alternativa', 200]]);
    assert.deepEqual(resumen.solicitudes.filter(x => x.error).map(x => x.error.codigo),
      ['TIMEOUT', 'ERROR_RED']);
    assert.deepEqual(llamadas.map(x => new URL(x.url).hostname),
      ['www.api.inmero.co', 'api.inmero.co', 'www.api.inmero.co', 'api.inmero.co']);
    assert.equal(resumen.solicitudes.filter(x => x.con_cookie_refresco).length, 2);
    const carpeta = path.join(temporal, resumen.salida);
    const contenido = fs.readFileSync(path.join(carpeta, 'autenticacion.json'), 'utf8')
      + fs.readFileSync(path.join(carpeta, 'bitacora_resumen.json'), 'utf8');
    assert.doesNotMatch(contenido, /TOKEN_PRIVADO|COOKIE_PRIVADA|privado@example\.test|clave-local/);
    assert.equal(baseAlternativaTest('https://www.api.inmero.co/api-sgpmp-test'),
      'https://api.inmero.co/api-sgpmp-test');
    assert.equal(baseAlternativaTest('https://www.api.inmero.co/api-sgpmp-prod'), null);
    assert.equal(baseAlternativaTest('https://www.api.inmero.co.evil.test/api-sgpmp-test'), null);
    const sinWww = await diagnostico({ referencia: 'REF_LOCAL', consultas: ['POST /sesiones/'],
      maxPeticiones: 4, env: { ...env,
        SIGAB_API_TEST_BASE: 'https://api.inmero.co/api-sgpmp-test' },
      directorio: temporal, ahora: new Date('2026-10-25T18:00:02Z'),
      fetcher: async () => ({ status: 401, headers: { get: () => null },
        json: async () => ({}) }) });
    assert.equal(sinWww.comparacion_frontend.coincide, true);
    assert.deepEqual(sinWww.comparacion_frontend.diferencias, []);
    let fueraTest = 0;
    await assert.rejects(diagnostico({ referencia: 'REF_LOCAL', consultas: ['POST /sesiones/'],
      maxPeticiones: 4, env: { ...env,
        SIGAB_API_TEST_BASE: 'https://www.api.inmero.co.evil.test/api-sgpmp-test' },
      directorio: temporal, fetcher: () => { fueraTest++; } }), /DIAGNOSTICO_CONFIG_INVALIDA/);
    assert.equal(fueraTest, 0);
    await assert.rejects(diagnostico({ referencia: 'REF_LOCAL', consultas: ['POST /sesiones/'],
      maxPeticiones: 3, env, directorio: temporal, fetcher: () => { throw new Error('RED'); } }),
    /DIAGNOSTICO_LIMITE_INVALIDO/);
  } finally { fs.rmSync(temporal, { recursive: true, force: true }); }
});

test('transporte impide escrituras ajenas, login dentro del RUN y respeta cabeceras', async () => {
  const peticiones = [];
  const t = transporte({ base: env.SIGAB_API_TEST_BASE, runId: RUN, secreto: env.QA_SANDBOX_SECRET,
    bitacora: [], fetcher: async (url, opts) => { peticiones.push({ url, opts }); return respuesta(200, {}); } });
  t.abrir();
  await assert.rejects(() => t.solicitar('POST', '/sesiones/', { login: true }), /LOGIN_DENTRO_RUN/);
  await assert.rejects(() => t.solicitar('POST', '/configuracion/dispositivos-iot/2/sensores',
    { cuerpo: {} }), /ESCRITURA_FUERA_LISTA_BLANCA/);
  await t.solicitar('GET', '/iot/monitoreo/dashboard/349');
  assert.equal(peticiones[0].opts.headers['X-Test-Run-Id'], RUN);
  assert.equal(peticiones[0].opts.headers['X-Sandbox-Secret'], env.QA_SANDBOX_SECRET);
  assert.equal(peticiones[0].url.includes('/dashboard?'), false);
});

test('simulador aislado: preflight, RECHAZADO por unidad ausente, cierre y único informe', async () => {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'g93-local-'));
  const runDir = path.join(tmp, 'Resultados', RUN);
  fs.mkdirSync(runDir, { recursive: true });
  const contrato = { operacion: 'evaluar', version: 1, intento: 1, runId: RUN,
    referencia: 'LOCAL_SIMULADO', directorio: runDir };
  const llamadas = [];
  let cerrado = false;
  const fetcher = async (url, opts) => {
    assert.equal(fs.existsSync(path.join(runDir, 'preflight.json')), true);
    const ruta = new URL(url).pathname.replace('/api-sgpmp-test', '');
    llamadas.push({ metodo: opts.method, ruta, headers: opts.headers });
    if (ruta === '/sesiones/') return respuesta(200, { token: 'jwt-falso' },
      { run: false, cookie: 'refresh_token=cookie-falsa; HttpOnly; Path=/' });
    if (ruta === `/test-control/runs/${RUN}`) { cerrado = true; return respuesta(200, { status: 'Rollback exitoso' }, { run: false }); }
    if (ruta === '/configuracion/fincas/184') return respuesta(200, { id_finca: 184, es_activo: true });
    if (ruta === '/configuracion/infraestructuras/349') return respuesta(200,
      { id_infraestructura: 349, id_finca: 184, es_activo: true, especies: [126], tipo_area: 'ESTANQUE', superficie: '10' });
    if (ruta === '/configuracion/infraestructuras' && opts.method === 'POST') return respuesta(201, { id_infraestructura: 900 });
    if (ruta === '/configuracion/infraestructuras/900') return respuesta(cerrado ? 404 : 200,
      cerrado ? {} : { id_infraestructura: 900 });
    if (ruta === '/configuracion/fincas') return respuesta(200, { items: [{ id_finca: 184 }] });
    if (ruta === '/iot/dispositivos') return respuesta(200, [{ id_infraestructura: 349 }]);
    if (/^\/iot\/monitoreo\/dashboard\/(1|2|3|349)$/.test(ruta)) return respuesta(200, { sensores: [], resumen_unidades: [] });
    if (ruta === '/iot/monitoreo/dashboard/900') return respuesta(200, { total: 0, sensores: [], resumen_unidades: [] }, { run: !cerrado });
    throw Error(`Ruta inesperada ${ruta}`);
  };
  const runNewman = (c, { fase }) => {
    assert.equal(fase, 'V1');
    fs.mkdirSync(path.join(c.directorio, 'newman'), { recursive: true });
    fs.writeFileSync(path.join(c.directorio, 'newman/newman-V1.json'), '{}');
    return { rel: 'newman/newman-V1.json', http: 200, eco: true,
      cuerpo: { total: 0, sensores: [], resumen_unidades: [] }, fallos: [] };
  };
  try {
    const r = await evaluar(contrato, { env, fetcher, runNewman,
      runCypress: () => ({ estado: 'NO_EJECUTADA', motivo: 'Simulador local', rel: null }) });
    assert.equal(r.casos['TC-M03-184'].estado, 'RECHAZADO');
    assert.equal(r.cierre.rollback.verificado, true);
    assert.deepEqual(r.cierre.rollback.comprobaciones.map(x => [x.recurso, x.http, x.ok]),
      [['area_v1', 404, true], ['dashboard_area_v1', 200, true]]);
    assert.equal(r.datos.ids_telemetria.length, 0);
    assert.equal(r.variantes.V2, 'BLOQUEADO');
    assert.equal(llamadas.filter(x => x.ruta === '/sesiones/').length, 2);
    assert.equal(llamadas.some(x => x.ruta === '/iot/monitoreo/dashboard'), false);
    assert.equal(llamadas.some(x => x.ruta.includes('/sensores')), false);
    assert.equal(llamadas.find(x => x.ruta === '/configuracion/infraestructuras' && x.metodo === 'POST').headers['X-Test-Run-Id'], RUN);
    assert.equal(fs.readdirSync(runDir).filter(x => x.endsWith('.md')).length, 1);
    const salida = JSON.parse(fs.readFileSync(path.join(runDir, 'resultado.json'), 'utf8'));
    assert.equal(salida.run_id, RUN);
    assert.equal(salida.comprobaciones.find(x => x.id === 'API-184-01').estado, 'RECHAZADO');
    for (const campo of ['grupo', 'run_id', 'version', 'operacion', 'autorizacion', 'casos',
      'variantes', 'comprobaciones', 'bitacora', 'newman', 'cypress', 'evidencias',
      'problemas_tecnicos', 'dependencias', 'cierre', 'presupuesto'])
      assert.ok(Object.hasOwn(salida, campo), `Falta ${campo} en resultado.json`);
    assert.equal(salida.casos['TC-M03-184'].estado, 'RECHAZADO');
    assert.equal(salida.variantes.V2, 'BLOQUEADO');
    assert.match(salida.dependencias.join(' '), /ninguna candidata/);
    assert.equal(salida.comprobaciones.length, 5);
    assert.equal(salida.comprobaciones.some(x => x.id.startsWith('UI') && x.estado === 'APROBADO'), false);
    const artefactos = fs.readdirSync(runDir, { recursive: true }).map(String);
    assert.equal(artefactos.filter(x => x.endsWith('.md')).length, 1);
    assert.equal(artefactos.every(x => !path.isAbsolute(x)), true);
    const informe = fs.readFileSync(path.join(runDir, 'TC-M03-G93_resultado.md'), 'utf8');
    for (const seccion of ['## Incidencias de producto', '## Incidencias técnicas QA',
      '## Observaciones documentales', '## Cierre y rollback', '## Criterio de carga inicial UI',
      '## Hallazgos de rendimiento pendientes de diagnóstico'])
      assert.ok(informe.includes(seccion), `Falta ${seccion}`);
    assert.match(informe, /Equipo inicial: Desarrollo/);
    assert.match(informe, /severidad MEDIA/);
    assert.doesNotMatch(informe, /Equipo inicial: (?:Backend|Frontend|DevOps|QA)\b/);
    assert.equal(salida.evidencias.every(x => fs.existsSync(path.join(runDir, x))), true);
    for (const valor of ['falso-local', 'cookie-falsa', 'jwt-falso', 'clave-local']) {
      assert.equal(JSON.stringify(salida).includes(valor), false);
      assert.equal(informe.includes(valor), false);
    }
  } finally { fs.rmSync(tmp, { recursive: true, force: true }); }
});

test('spec UI conserva peticiones reales y artefactos dentro del RUN', () => {
  const spec = fs.readFileSync(path.join(GRUPO, 'g93.cy.js'), 'utf8');
  const runner = fs.readFileSync(path.join(GRUPO, 'g93.mjs'), 'utf8');
  assert.match(spec, /req\.continue\(/);
  assert.ok(spec.indexOf('esperas.global = crearEspera(') < spec.indexOf('cy.visit('));
  assert.match(spec, /cy\.then\(\(\) => cy\.wrap\(esperas\.global\.promise/);
  assert.match(spec, /cy\.then\(\(\) => cy\.wrap\(esperas\.objetivo\.promise/);
  assert.equal(spec.split(/\r?\n/).some(line => /^\s*cy\.wrap\(esperas\./.test(line)), false);
  assert.match(spec, /X-Test-Run-Id/);
  assert.match(spec, /X-Sandbox-Secret/);
  assert.doesNotMatch(spec, /req\.reply|fixture\(/);
  assert.match(runner, /screenshotsFolder=\$\{carpeta\}/);
  assert.equal(preflight({ runId: RUN, version: 1, operacion: 'evaluar' }, env).ok, true);
});

test('callback de respuesta resuelve ambas esperas sin releer propiedades de req', () => {
  const spec = fs.readFileSync(path.join(GRUPO, 'g93.cy.js'), 'utf8');
  const callback = spec.split('req.continue(res => {')[1]?.split('\n    });')[0];
  assert.ok(callback, 'falta el callback de respuesta');
  assert.doesNotMatch(callback, /\breq\./);
  assert.ok(spec.indexOf('const tipo = ') < spec.indexOf('req.continue(res => {'));
  assert.match(callback, /tipo === 'global'\) esperas\.global\?\.terminar\(/);
  assert.match(callback, /tipo === 'objetivo'\) esperas\.objetivo\?\.terminar\(/);
  assert.match(callback, /registro\.duracion_ms = Date\.now\(\) - inicio/);
  assert.match(callback, /registro\.http = res\?\.statusCode/);
  assert.match(callback, /registro\.eco_run = res\?\.headers\?\.\['x-test-run-id'\] === RUN/);
  assert.match(spec, /crearEspera\(40000\)/);
  assert.match(spec, /\? 2000 : 60000\)/);
  assert.match(spec, /cy\.writeFile\(`\$\{CARPETA\}\/UI-184-/);
  assert.match(spec, /cy\.screenshot\(`UI-184-/);
});

test('capacidades y comprobar publican contrato local sin red ni RUN', () => {
  assert.deepEqual(CAPACIDADES.casos, ['TC-M03-184']);
  assert.deepEqual(CAPACIDADES.operaciones, ['evaluar', 'reintentar', 'reevaluar', 'diagnostico']);
  assert.equal(CAPACIDADES.solo_lectura, true);
  assert.deepEqual(CAPACIDADES.consultas, CONSULTAS_DIAGNOSTICO);
  assert.equal(CAPACIDADES.max_peticiones, 30);
  assert.equal(CAPACIDADES.limite.ui_api, 25);
  assert.equal(CAPACIDADES.limite.candidatas, 10);
  assert.equal(comprobar(), 0);
  const runner = fs.readFileSync(path.join(GRUPO, 'g93.mjs'), 'utf8');
  assert.match(runner, /process\.argv\.includes\('--capacidades'\)/);
  assert.match(runner, /process\.argv\.includes\('--comprobar'\)/);
});

test('transporte reserva cierre, aplica lista blanca antes del POST y no inicia login en RUN', async () => {
  const llamadas = [];
  const t = transporte({ base: env.SIGAB_API_TEST_BASE, runId: RUN, secreto: env.QA_SANDBOX_SECRET,
    bitacora: [], limite: 8, fetcher: async (url, opts) => {
      llamadas.push({ url, opts }); return respuesta(200, {});
    } });
  await t.solicitar('POST', '/sesiones/', { login: true });
  t.abrir();
  await assert.rejects(() => t.solicitar('POST', '/sesiones/', { login: true }), /LOGIN_DENTRO_RUN/);
  await assert.rejects(() => t.solicitar('POST', '/configuracion/infraestructuras',
    { cuerpo: { finca_id: 999, especies: [126], nombre_infraestructura: `G93-${RUN}` } }), /ID_FUERA_LISTA_BLANCA/);
  assert.equal(llamadas.length, 1);
  await t.solicitar('GET', '/iot/monitoreo/dashboard/349');
  await t.solicitar('GET', '/iot/monitoreo/dashboard/349');
  await assert.rejects(() => t.solicitar('GET', '/iot/monitoreo/dashboard/349'), /LIMITE_SOLICITUDES_FUNCIONALES/);
  await t.solicitar('DELETE', `/test-control/runs/${RUN}`, { cierre: true });
  assert.equal(t.estado().cerrado, true);
  assert.equal(llamadas.at(-1).opts.method, 'DELETE');
  assert.equal(llamadas.slice(1, -1).every(x => x.opts.headers['X-Test-Run-Id'] === RUN
    && x.opts.headers['X-Sandbox-Secret'] === env.QA_SANDBOX_SECRET), true);
  assert.equal(llamadas.every(x => !new URL(x.url).pathname.endsWith('/iot/monitoreo/dashboard')), true);
});

test('clasificación exige UI real y mantiene V2 sin candidata BLOQUEADO', () => {
  const soloApi = CAPACIDADES.comprobaciones_obligatorias['TC-M03-184'].API
    .map(id => ({ id, tipo: 'ASSERT', estado: 'APROBADO' }));
  assert.notEqual(clasificar(soloApi, { candidata: true, cierreVerificado: true }).estado, 'APROBADO');
  const sinCandidata = clasificar(soloApi, { candidata: false, cierreVerificado: true });
  assert.equal(sinCandidata.estado, 'BLOQUEADO');
  assert.match(sinCandidata.motivo, /No hubo unidad|RF-60/);
  assert.equal(clasificar(soloApi, { candidata: true, cierreVerificado: false }).estado, 'BLOQUEADO');
});

test('spec permite dashboard global real; Newman sigue filtrado y no crea sensores', () => {
  const spec = fs.readFileSync(path.join(GRUPO, 'g93.cy.js'), 'utf8');
  const runner = fs.readFileSync(path.join(GRUPO, 'g93.mjs'), 'utf8');
  const coleccion = JSON.parse(fs.readFileSync(path.join(GRUPO, 'G93.postman_collection.json'), 'utf8'));
  assert.equal(coleccion.item.length, 1);
  assert.match(coleccion.item[0].request.url, /dashboard\/\{\{id_infraestructura\}\}/);
  assert.doesNotMatch(coleccion.item[0].request.url, /\/dashboard\?/);
  assert.match(runner, /\/iot\/monitoreo\/dashboard\/\$\{id\}/);
  assert.doesNotMatch(runner, /POST[^\n]*sensores/);
  assert.doesNotMatch(spec, /req\.url\s*=/);
  assert.doesNotMatch(spec, /req\.reply\s*\(|fixture\s*\(/);
  assert.doesNotMatch(spec, /req\.destroy\(|UI_DEPENDIENTE_CONSULTA_GLOBAL|req\.reply\s*\(/);
  assert.match(spec, /req\.alias = filtro \? 'dashboardFiltrado' : 'dashboardGlobal'/);
  assert.match(spec, /\? 2000 : 60000\)/);
  assert.match(spec, /crearEspera\(40000\)/);
  assert.match(spec, /fin_observacion/);
  assert.match(spec, /duracion_observada_ms/);
  assert.match(spec, /ui_inicial = observar/);
  assert.match(spec, /cy\.screenshot\(`UI-184-/);
  assert.match(spec, /rutaSegura/);
  assert.match(spec, /intentarDesactivarAuto\(\$body\[0\]\)/);
  assert.doesNotMatch(spec, /cy\.reload\(|req\.url\s*=/);
  assert.equal((spec.match(/cy\.visit\(/g) || []).length, 1);
  assert.match(spec, /req\.headers\['X-Test-Run-Id'\] = RUN/);
  assert.match(spec, /req\.headers\['X-Sandbox-Secret'\]/);
  assert.match(spec, /peticiones > 25/);
  assert.match(runner, /timeout = 150000/);
  assert.doesNotMatch(spec, /texto_literal|includes\('Sin datos disponibles'\)|textContent\.trim\(\) === 'Sin datos'/);
  assert.doesNotMatch(runner, /texto literal "Sin datos disponibles"/);
});

test('clasificación UI: 200 y unidad ausente, 5xx, 60 s, sesión y eco', () => {
  assert.equal(clasificarCarga({ http: 200, eco: true }).estado, 'EVALUAR_UI');
  assert.equal(evaluarOraculoUi({ unidad_objetivo_presente: false }, { unidad_objetivo_presente: true }).estado, 'RECHAZADO');
  assert.equal(clasificarCarga({ http: 503, eco: true }).estado, 'RECHAZADO');
  for (const carga of [{ http: null, vencio: true }, { http: null, errorRed: 'sin conexión' }]) {
    const decision = clasificarCarga(carga);
    assert.equal(decision.estado, 'NO_CONCLUYENTE');
    assert.notEqual(decision.estado, 'APROBADO');
    assert.notEqual(decision.estado, 'ERROR_QA');
  }
  assert.equal(clasificarCarga({ http: 401, eco: false }).estado, 'ERROR_QA');
  assert.equal(clasificarCarga({ http: 200, eco: false }).estado, 'ERROR_QA');
  assert.equal(clasificar([{ id: 'UI-184-01', tipo: 'ASSERT', estado: 'NO_CONCLUYENTE' }],
    { candidata: true, cierreVerificado: true }).estado, 'NO_CONCLUYENTE');
});

test('oráculo UI exige presencia y atributos en panel global y vista filtrada', () => {
  const correcta = { unidad_objetivo_presente: true, gris: true, mensaje_ausencia: 'Sin datos disponibles',
    fecha_historica: true, sin_valores_fabricados: true, desde_cache: false };
  assert.deepEqual(evaluarOraculoUi({ ...correcta, unidad_objetivo_presente: false }, correcta),
    { estado: 'RECHAZADO', criterio: 'UNIDAD_DESAPARECE_DEL_PANEL' });
  assert.equal(evaluarOraculoUi(correcta, correcta).estado, 'APROBADO');
  assert.equal(evaluarOraculoUi({ ...correcta, gris: false }, correcta).estado, 'RECHAZADO');
  assert.equal(evaluarOraculoUi(correcta, { ...correcta, mensaje_ausencia: '' }).estado, 'RECHAZADO');
  for (const texto of ['Sin datos', '  SIN   DATOS  ', 'Sin datos disponibles', '  sin  DATOS  disponibles ']) {
    assert.equal(mensajeAusenciaEquivalente(texto), true, texto);
    assert.equal(evaluarOraculoUi({ ...correcta, mensaje_ausencia: texto },
      { ...correcta, mensaje_ausencia: texto }).estado, 'APROBADO', texto);
  }
  for (const texto of ['', 'Sin señal', 'Sin umbral configurado', 'Error', 'Cargando', 'Sin datos: error']) {
    assert.equal(mensajeAusenciaEquivalente(texto), false, texto);
    assert.equal(evaluarOraculoUi(correcta, { ...correcta, mensaje_ausencia: texto }).estado, 'RECHAZADO', texto);
  }
  assert.match(observacionDocumental('V1', 'panel global', 'Sin datos'), /texto observado «Sin datos»/);
  assert.equal(observacionDocumental('V1', 'panel global', 'Sin datos disponibles'), null);
  assert.equal(observacionDocumental('V1', 'panel global', 'Sin señal'), null);
});

test('control Auto ON ausente o no pulsable genera incidencia técnica sin decidir UI', () => {
  const cuerpo = boton => ({ querySelectorAll: () => boton ? [boton] : [] });
  assert.equal(intentarDesactivarAuto(cuerpo(null)), 'CONTROL_AUTO_ON_AUSENTE');
  assert.equal(intentarDesactivarAuto(cuerpo({ textContent: 'Auto ON', disabled: true,
    getClientRects: () => [{}] })), 'CONTROL_AUTO_ON_NO_PULSABLE');
  assert.equal(intentarDesactivarAuto(cuerpo({ textContent: 'Auto ON', disabled: false,
    getClientRects: () => [{}], click: () => { throw Error('No pulsable'); } })), 'CONTROL_AUTO_ON_NO_PULSABLE');
  let pulsaciones = 0;
  assert.equal(intentarDesactivarAuto(cuerpo({ textContent: 'Auto ON', disabled: false,
    getClientRects: () => [{}], click: () => { pulsaciones++; } })), null);
  assert.equal(pulsaciones, 1);
});

test('transporte bloquea peticiones propias durante Cypress y reanuda tras su salida', async () => {
  const llamadas = [];
  const t = transporte({ base: env.SIGAB_API_TEST_BASE, runId: RUN, secreto: env.QA_SANDBOX_SECRET,
    bitacora: [], fetcher: async (url, opts) => { llamadas.push([url, opts.method]); return respuesta(200, {}); } });
  t.abrir();
  t.iniciarUi();
  await assert.rejects(() => t.solicitar('GET', '/iot/monitoreo/dashboard/349'), /PETICION_DURANTE_CYPRESS/);
  await assert.rejects(() => t.solicitar('DELETE', `/test-control/runs/${RUN}`, { cierre: true }), /PETICION_DURANTE_CYPRESS/);
  assert.equal(llamadas.length, 0);
  t.terminarUi();
  await t.solicitar('GET', '/iot/monitoreo/dashboard/349');
  await t.solicitar('DELETE', `/test-control/runs/${RUN}`, { cierre: true });
  assert.deepEqual(llamadas.map(x => x[1]), ['GET', 'DELETE']);
});

test('saneamiento elimina cookie, secreto y credenciales de artefactos', () => {
  const secreto = 'secreto-simulado-123';
  const cookie = 'cookie-simulada-456';
  const json = JSON.stringify({ headers: [{ key: 'X-Sandbox-Secret', value: secreto },
    { key: 'Cookie', value: `refresh_token=${cookie}` }], token: 'jwt-local',
    body: { password: 'clave-local' } });
  const limpio = sanearArtefacto(json, [secreto, cookie, 'clave-local']);
  for (const valor of [secreto, cookie, 'clave-local', 'jwt-local']) assert.equal(limpio.includes(valor), false);
  const spec = fs.readFileSync(path.join(GRUPO, 'g93.cy.js'), 'utf8');
  assert.match(spec, /acta\.peticiones\.push\(registro\)/);
  assert.doesNotMatch(spec, /acta\.(?:cookie|secreto|headers)\s*=/);
});

async function simularConFetch(fetcher, revisar, { newmanV2 = null, runCypress = () => ({ estado: 'NO_EJECUTADA', motivo: 'Simulador local', rel: null }), runNewmanFalla = false } = {}) {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'g93-local-'));
  const runDir = path.join(tmp, 'Resultados', RUN);
  fs.mkdirSync(runDir, { recursive: true });
  const contrato = { operacion: 'evaluar', version: 1, intento: 1, runId: RUN,
    referencia: 'LOCAL_SIMULADO', directorio: runDir };
  try {
    const resultado = await evaluar(contrato, { env, fetcher: (url, opts) => {
      assert.equal(fs.existsSync(path.join(runDir, 'preflight.json')), true);
      return fetcher(new URL(url).pathname.replace('/api-sgpmp-test', ''), opts, new URL(url).search);
    }, runNewman: (c, { fase, base }) => {
      assert.equal(base, env.SIGAB_API_TEST_BASE);
      if (runNewmanFalla && fase === 'V1') throw new Error('NEWMAN_CLI_NO_RESUELTO');
      const rel = `newman/newman-${fase}.json`;
      fs.mkdirSync(path.join(c.directorio, 'newman'), { recursive: true });
      fs.writeFileSync(path.join(c.directorio, rel), '{}');
      return { rel, http: 200, eco: true, cuerpo: fase === 'V2' && newmanV2
        ? newmanV2 : { total: 0, sensores: [], resumen_unidades: [] }, fallos: [] };
    }, runCypress });
    await revisar(resultado, runDir);
  } finally { fs.rmSync(tmp, { recursive: true, force: true }); }
}

test('API y UI continúan independientes aunque Newman falle o rechace', async () => {
  for (const falla of [true, false]) {
    let cerrado = false, ejecucionesUi = 0, uiEnCurso = false;
    await simularConFetch((ruta, opts) => {
      assert.equal(uiEnCurso, false, 'El ejecutor lanzó una petición mientras Cypress seguía activo');
      if (ruta === '/sesiones/') return respuesta(200, { token: 'jwt-local' },
        { run: false, cookie: 'refresh_token=cookie-local; HttpOnly' });
      if (ruta === `/test-control/runs/${RUN}`) { cerrado = true; return respuesta(200, {}, { run: false }); }
      if (ruta === '/configuracion/fincas/184') return respuesta(200, { id_finca: 184, es_activo: true });
      if (ruta === '/configuracion/infraestructuras/349') return respuesta(200,
        { id_infraestructura: 349, id_finca: 184, es_activo: true, especies: [126], tipo_area: 'ESTANQUE', superficie: 10 });
      if (ruta === '/configuracion/infraestructuras' && opts.method === 'POST') return respuesta(201, { id_infraestructura: 900 });
      if (ruta === '/configuracion/infraestructuras/900') return respuesta(cerrado ? 404 : 200,
        cerrado ? {} : { id_infraestructura: 900 });
      if (ruta === '/configuracion/fincas') return respuesta(200, { items: [] });
      if (ruta === '/iot/dispositivos') return respuesta(200, []);
      if (ruta === '/iot/monitoreo/dashboard/900') return respuesta(200,
        { total: 0, sensores: [], resumen_unidades: [] });
      throw Error(`Ruta inesperada ${ruta}`);
    }, (r, runDir) => {
      assert.equal(ejecucionesUi, 1);
      assert.equal(r.comprobaciones.find(x => x.id === 'UI-184-01').estado, 'APROBADO');
      assert.equal(r.casos['TC-M03-184'].observado.UI_V1.panel_global, 'Sin datos');
      assert.equal(r.casos['TC-M03-184'].observado.UI_V1.vista_filtrada, 'Sin datos disponibles');
      assert.equal(r.observaciones_documentales.length, 1);
      assert.match(r.observaciones_documentales[0], /texto observado «Sin datos»/);
      assert.equal(JSON.parse(fs.readFileSync(path.join(runDir, 'resultado.json'), 'utf8'))
        .observaciones_documentales.length, 1);
      const informe = fs.readFileSync(path.join(runDir, 'TC-M03-G93_resultado.md'), 'utf8');
      assert.match(informe, /## Observaciones documentales\n\n- V1, panel global: texto observado «Sin datos»/);
      assert.doesNotMatch(informe, /texto literal "Sin datos disponibles" según la matriz/);
      assert.ok(r.problemas_tecnicos.includes('UI V1: CONTROL_AUTO_ON_AUSENTE'));
      assert.equal(r.comprobaciones.find(x => x.id === 'API-184-01')?.estado,
        falla ? 'NO_EJECUTADA' : 'RECHAZADO');
      if (falla) {
        assert.match(r.problemas_tecnicos.join(' '), /API V1: NEWMAN_CLI_NO_RESUELTO/);
        assert.notEqual(r.casos['TC-M03-184'].estado, 'RECHAZADO');
      }
      assert.equal(r.cierre.run.cierre_http, 200);
    }, { runNewmanFalla: falla, runCypress: async () => {
      ejecucionesUi++;
      uiEnCurso = true;
      await new Promise(resolve => setTimeout(resolve, 1));
      uiEnCurso = false;
      return { estado: 'APROBADO', motivo: 'UI simulada independiente', rel: null,
        ui_inicial: { mensaje_ausencia: 'Sin datos' },
        ui_objetivo: { mensaje_ausencia: 'Sin datos disponibles' },
        observaciones_documentales: [observacionDocumental('V1', 'panel global', 'Sin datos')],
        incidencias_tecnicas: ['CONTROL_AUTO_ON_AUSENTE'] };
    } });
  }
});

test('rollback no se acredita ante área 403, dashboard 5xx ni timeout', async () => {
  for (const modo of ['area403', 'dashboard500', 'timeout']) {
    let cerrado = false;
    await simularConFetch((ruta, opts) => {
      if (ruta === '/sesiones/') return respuesta(200, { token: 'jwt-local' },
        { run: false, cookie: 'refresh_token=cookie-local; HttpOnly' });
      if (ruta === `/test-control/runs/${RUN}`) { cerrado = true; return respuesta(200, {} , { run: false }); }
      if (ruta === '/configuracion/fincas/184') return respuesta(200, { id_finca: 184, es_activo: true });
      if (ruta === '/configuracion/infraestructuras/349') return respuesta(200,
        { id_infraestructura: 349, id_finca: 184, es_activo: true, especies: [126], tipo_area: 'ESTANQUE', superficie: 10 });
      if (ruta === '/configuracion/infraestructuras' && opts.method === 'POST') return respuesta(201, { id_infraestructura: 900 });
      if (ruta === '/configuracion/infraestructuras/900') return respuesta(cerrado ? modo === 'area403' ? 403 : 404 : 200,
        cerrado ? {} : { id_infraestructura: 900 });
      if (ruta === '/configuracion/fincas') return respuesta(200, { items: [] });
      if (ruta === '/iot/dispositivos') return respuesta(200, []);
      if (ruta === '/iot/monitoreo/dashboard/900') {
        if (cerrado && modo === 'timeout') throw new Error('TIMEOUT_SIMULADO');
        return respuesta(cerrado && modo === 'dashboard500' ? 500 : 200,
          { total: 0, sensores: [], resumen_unidades: [] });
      }
      throw Error(`Ruta inesperada ${ruta}`);
    }, (r, runDir) => {
      assert.equal(cerrado, true);
      assert.equal(r.cierre.rollback.verificado, false, modo);
      assert.equal(r.casos['TC-M03-184'].estado, 'BLOQUEADO');
      const salida = JSON.parse(fs.readFileSync(path.join(runDir, 'resultado.json'), 'utf8'));
      assert.equal(salida.cierre.rollback.verificado, false);
    });
  }
});

test('búsqueda V2 inspecciona como máximo diez candidatas sin crear sensores', async () => {
  const ids = [];
  const areas = Array.from({ length: 13 }, (_, i) => ({ id_infraestructura: 100 + i,
    serial: `SERIAL_PRIVADO_${i}` }));
  await simularConFetch((ruta) => {
    if (ruta === '/sesiones/') return respuesta(200, { token: 'jwt-local' },
      { run: false, cookie: 'refresh_token=cookie-local; HttpOnly' });
    if (ruta === `/test-control/runs/${RUN}`) return respuesta(200, {}, { run: false });
    if (ruta === '/configuracion/fincas/184') return respuesta(403, {});
    if (ruta === '/configuracion/fincas') return respuesta(200, { items: [{ id_finca: 184 }] });
    if (ruta === '/iot/dispositivos') return respuesta(200, areas);
    const m = /^\/iot\/monitoreo\/dashboard\/(\d+)$/.exec(ruta);
    if (m) { ids.push(Number(m[1])); return respuesta(200, { sensores: [], resumen_unidades: [] }); }
    throw Error(`Ruta inesperada ${ruta}`);
  }, (r) => {
    assert.deepEqual(ids, [1, 2, 3, 100, 101, 102, 103, 104, 105, 106]);
    assert.equal(r.variantes.V2, 'BLOQUEADO');
    assert.match(r.dependencias.join(' '), /hasta 10 áreas/);
    assert.equal(r.datos.candidatas_v2.length, 10);
    assert.equal(JSON.stringify(r.datos).includes('SERIAL_PRIVADO'), false);
    assert.equal(r.datos.id_area_v2, null);
    assert.equal(r.bitacora.some(x => x.metodo === 'POST' && x.ruta.includes('sensores')), false);
  });
});

test('rollback compara semilla V2 estable y rechaza cambio posterior al cierre', async () => {
  const candidato = { total: 1, resumen_unidades: [{ id_infraestructura: 349,
    id_finca: 184, nombre_infraestructura: 'Unidad local', estado_general: 'GRIS', total_sensores: 1,
    ultimo_dato_recibido: '2026-10-20T10:00:00Z' }],
  sensores: [{ id_infraestructura: 349, estado_conectividad: 'SIN_SEÑAL',
    dato_desactualizado: true, tiempo_sin_reporte_min: 30,
    ultimo_timestamp_captura: '2026-10-20T10:00:00Z' }] };
  for (const cambia of [false, true]) {
    let cerrado = false;
    await simularConFetch((ruta) => {
      if (ruta === '/sesiones/') return respuesta(200, { token: 'jwt-local' },
        { run: false, cookie: 'refresh_token=cookie-local; HttpOnly' });
      if (ruta === `/test-control/runs/${RUN}`) { cerrado = true; return respuesta(200, {}, { run: false }); }
      if (ruta === '/configuracion/fincas/184') return respuesta(403, {});
      if (ruta === '/configuracion/fincas') return respuesta(200, { items: [{ id_finca: 184 }] });
      if (ruta === '/iot/dispositivos') return respuesta(200, [{ id_infraestructura: 349 }]);
    if (ruta === '/iot/monitoreo/dashboard/349') return respuesta(200, candidato);
    if (/^\/iot\/monitoreo\/dashboard\/(1|2|3)$/.test(ruta)) return respuesta(200, { sensores: [], resumen_unidades: [] });
      if (ruta === '/configuracion/infraestructuras/349') return respuesta(200, {
        id_infraestructura: 349, nombre_infraestructura: cerrado && cambia ? 'Modificada' : 'Unidad local',
        id_finca: 184, es_activo: true, especies: [126] });
      throw Error(`Ruta inesperada ${ruta}`);
    }, r => {
      assert.equal(r.datos.id_area_v2, 349);
      assert.equal(r.cierre.rollback.comprobaciones.find(x => x.recurso === 'semilla_v2_estable').ok, !cambia);
      assert.equal(r.cierre.rollback.verificado, !cambia);
      assert.equal(r.casos['TC-M03-184'].estado, 'BLOQUEADO');
    }, { newmanV2: candidato });
  }
});

test('preferencia 1→2→3 y cambio de estado antes de Newman o Cypress', async () => {
  for (const cambioEn of [2, 3]) {
    const lecturas = new Map();
    const candidato = id => ({ resumen_unidades: [{ id_infraestructura: id,
      id_finca: 184, nombre_infraestructura: `Unidad ${id}`, estado_general: 'GRIS',
      total_sensores: 1 }], sensores: [{ id_infraestructura: id,
        estado_conectividad: id === 1 && lecturas.get(1) >= cambioEn ? 'ACTIVO' : 'INACTIVO',
        dato_desactualizado: true, tiempo_sin_reporte_min: 30 }] });
    await simularConFetch(ruta => {
      if (ruta === '/sesiones/') return respuesta(200, { token: 'jwt-local' },
        { run: false, cookie: 'refresh_token=cookie-local; HttpOnly' });
      if (ruta === `/test-control/runs/${RUN}`) return respuesta(200, {}, { run: false });
      if (ruta === '/configuracion/fincas/184') return respuesta(403, {});
      if (ruta === '/configuracion/fincas') return respuesta(200, { items: [{ id_finca: 184 }] });
      if (/^\/configuracion\/infraestructuras\/[12]$/.test(ruta)) {
        const id = Number(ruta.split('/').at(-1));
        return respuesta(200, { id_infraestructura: id, id_finca: 184,
          nombre_infraestructura: `Unidad ${id}`, es_activo: true, especies: [126] });
      }
      const m = /^\/iot\/monitoreo\/dashboard\/([123])$/.exec(ruta);
      if (m) {
        const id = Number(m[1]); lecturas.set(id, (lecturas.get(id) ?? 0) + 1);
        return respuesta(200, candidato(id));
      }
      throw Error(`Ruta inesperada ${ruta}`);
    }, r => {
      assert.equal(r.datos.id_area_v2, 2);
      assert.deepEqual(r.datos.candidatas_v2.filter(x => !x.momento).map(x => x.id_infraestructura),
        [1, 2]);
      assert.ok(r.datos.candidatas_v2.some(x => x.evento === 'candidata_cambio_estado'
        && x.id_infraestructura === 1 && x.estados_originales.includes('ACTIVO')));
      assert.equal(r.comprobaciones.find(x => x.id === 'API-184-03')?.estado, 'APROBADO');
      assert.equal(r.comprobaciones.find(x => x.id === 'UI-184-02')?.estado, 'NO_EJECUTADA');
      assert.deepEqual(r.newman.filter(x => x.fase === 'V2').map(x => x.id_infraestructura),
        cambioEn === 2 ? [2] : [1, 2]);
    }, { newmanV2: candidato(2) });
  }
});

test('sin alternativa tras cambio de estado V2 queda BLOQUEADO sin UI', async () => {
  let lecturas1 = 0;
  await simularConFetch(ruta => {
    if (ruta === '/sesiones/') return respuesta(200, { token: 'jwt-local' },
      { run: false, cookie: 'refresh_token=cookie-local; HttpOnly' });
    if (ruta === `/test-control/runs/${RUN}`) return respuesta(200, {}, { run: false });
    if (ruta === '/configuracion/fincas/184') return respuesta(403, {});
    if (ruta === '/configuracion/fincas') return respuesta(200, { items: [{ id_finca: 184 }] });
    if (ruta === '/iot/dispositivos') return respuesta(200, []);
    const m = /^\/iot\/monitoreo\/dashboard\/([123])$/.exec(ruta);
    if (m) {
      const id = Number(m[1]);
      if (id === 1) lecturas1++;
      return respuesta(200, id !== 1 ? { resumen_unidades: [], sensores: [] }
        : { resumen_unidades: [{ id_infraestructura: 1, id_finca: 184, total_sensores: 1 }],
          sensores: [{ id_infraestructura: 1,
            estado_conectividad: lecturas1 === 1 ? 'INACTIVO' : 'ACTIVO' }] });
    }
    throw Error(`Ruta inesperada ${ruta}`);
  }, r => {
    assert.equal(r.variantes.V2, 'BLOQUEADO');
    assert.equal(r.datos.id_area_v2, null);
    assert.equal(r.comprobaciones.find(x => x.id === 'UI-184-02')?.estado, 'NO_EJECUTADA');
    assert.ok(r.datos.candidatas_v2.some(x => x.evento === 'candidata_cambio_estado'));
  });
});

test('descubrimiento complementario encuentra área solo en INACTIVO', async () => {
  const candidato = { resumen_unidades: [{ id_infraestructura: 4, id_finca: 184,
    nombre_infraestructura: 'Unidad 4', estado_general: 'GRIS', total_sensores: 1 }],
  sensores: [{ id_infraestructura: 4, estado_conectividad: 'INACTIVO',
    dato_desactualizado: true, tiempo_sin_reporte_min: 30 }] };
  await simularConFetch((ruta, opts, search) => {
    if (ruta === '/sesiones/') return respuesta(200, { token: 'jwt-local' },
      { run: false, cookie: 'refresh_token=cookie-local; HttpOnly' });
    if (ruta === `/test-control/runs/${RUN}`) return respuesta(200, {}, { run: false });
    if (ruta === '/configuracion/fincas/184') return respuesta(403, {});
    if (ruta === '/configuracion/fincas') return respuesta(200, { items: [{ id_finca: 184 }] });
    if (ruta === '/iot/dispositivos') {
      const estado = new URLSearchParams(search).get('estado');
      return respuesta(200, estado === 'INACTIVO' ? [{ id_infraestructura: 4, serial: 'SERIAL_PRIVADO' }] : []);
    }
    if (ruta === '/configuracion/infraestructuras/4') return respuesta(200,
      { id_infraestructura: 4, id_finca: 184, nombre_infraestructura: 'Unidad 4',
        es_activo: true, especies: [126] });
    if (ruta === '/iot/monitoreo/dashboard/4') return respuesta(200, candidato);
    if (/^\/iot\/monitoreo\/dashboard\/[123]$/.test(ruta)) return respuesta(200, { resumen_unidades: [], sensores: [] });
    throw Error(`Ruta inesperada ${ruta}`);
  }, r => {
    assert.equal(r.datos.id_area_v2, 4);
    assert.deepEqual(r.datos.descubrimiento_v2.map(x => x.ruta),
      ['/iot/dispositivos?estado=SIN_SEÑAL', '/iot/dispositivos?estado=INACTIVO']);
    assert.equal(JSON.stringify(r.datos).includes('SERIAL_PRIVADO'), false);
  }, { newmanV2: candidato });
});

test('cookie rotada pasa de V1 a V2, se sanea y se borra fuera del RUN', async () => {
  const candidato = { resumen_unidades: [{ id_infraestructura: 1, id_finca: 184,
    nombre_infraestructura: 'Unidad 1', estado_general: 'GRIS', total_sensores: 1 }],
  sensores: [{ id_infraestructura: 1, estado_conectividad: 'INACTIVO', dato_desactualizado: true }] };
  const archivos = [];
  await simularConFetch((ruta, opts) => {
    if (ruta === '/sesiones/') return respuesta(200, { token: 'jwt-local' },
      { run: false, cookie: 'refresh_token=COOKIE_ORIGINAL_LOCAL; HttpOnly' });
    if (ruta === `/test-control/runs/${RUN}`) return respuesta(200, {}, { run: false });
    if (ruta === '/configuracion/fincas/184') return respuesta(200, { id_finca: 184, es_activo: true });
    if (ruta === '/configuracion/fincas') return respuesta(200, { items: [{ id_finca: 184 }] });
    if (ruta === '/configuracion/infraestructuras/349') return respuesta(200,
      { id_infraestructura: 349, id_finca: 184, es_activo: true, especies: [126], tipo_area: 'ESTANQUE', superficie: 10 });
    if (ruta === '/configuracion/infraestructuras' && opts.method === 'POST') return respuesta(201, { id_infraestructura: 900 });
    if (ruta === '/configuracion/infraestructuras/900') return respuesta(200, { id_infraestructura: 900 });
    if (ruta === '/configuracion/infraestructuras/1') return respuesta(200,
      { id_infraestructura: 1, id_finca: 184, nombre_infraestructura: 'Unidad 1', es_activo: true, especies: [126] });
    if (ruta === '/iot/monitoreo/dashboard/900') return respuesta(200, { resumen_unidades: [], sensores: [] });
    if (ruta === '/iot/monitoreo/dashboard/1') return respuesta(200, candidato);
    throw Error(`Ruta inesperada ${ruta}`);
  }, (r, runDir) => {
    assert.equal(archivos.length, 2);
    assert.equal(archivos.every(x => !fs.existsSync(x) && x.startsWith(os.tmpdir())), true);
    assert.doesNotMatch(JSON.stringify(r), /COOKIE_(?:ORIGINAL|ROTADA)_LOCAL/);
    assert.doesNotMatch(fs.readFileSync(path.join(runDir, 'resultado.json'), 'utf8'), /COOKIE_(?:ORIGINAL|ROTADA)_LOCAL/);
  }, { newmanV2: candidato, runCypress: (contrato, opciones) => {
    archivos.push(opciones.cookieFile);
    assert.equal(opciones.base, 'https://api.inmero.co/api-sgpmp-test');
    assert.equal(opciones.front, env.SIGAB_FRONT_TEST_URL);
    assert.equal(opciones.cookie, archivos.length === 1 ? 'COOKIE_ORIGINAL_LOCAL' : 'COOKIE_ROTADA_LOCAL');
    fs.writeFileSync(opciones.cookieFile, archivos.length === 1 ? 'COOKIE_ROTADA_LOCAL' : 'COOKIE_ROTADA_LOCAL_2');
    return { estado: 'NO_EJECUTADA', motivo: 'Simulación local', rel: null };
  } });
});

test('carga un .env.qa sintético, respeta proceso y no hereda autorización del archivo', () => {
  const archivo = path.join(path.resolve(GRUPO, '../../../../..'), '.env.qa');
  const existe = fs.existsSync;
  const leer = fs.readFileSync;
  fs.existsSync = (ruta) => ruta === archivo ? true : existe(ruta);
  fs.readFileSync = (ruta, ...opciones) => ruta === archivo
    ? 'QA_ADMIN_EMAIL=archivo@example.test\nQA_AUTORIZADO=SI\n'
    : leer(ruta, ...opciones);
  try {
    const efectivo = leerEnv({ ...env, QA_ADMIN_EMAIL: 'override@example.test' });
    assert.equal(efectivo.QA_ADMIN_EMAIL, 'override@example.test');
    assert.equal(preflight({ runId: RUN, version: 1, operacion: 'reintentar' }, efectivo).ok, true);
    assert.notEqual(leerEnv({}).QA_AUTORIZADO, 'SI');
  } finally {
    fs.existsSync = existe;
    fs.readFileSync = leer;
  }
  const barrera = prevalidar({ QA_ADMIN_EMAIL: 'override@example.test' });
  assert.equal(barrera.barreras.every(x => x.startsWith('HERRAMIENTA_')
    || ['NEWMAN_CLI_NO_RESUELTO', 'CYPRESS_BINARIO_NO_INSTALADO'].includes(x)), true);
  assert.equal(barrera.variables.length, 7);
  assert.equal(JSON.stringify(barrera).includes('override@example.test'), false);
});

test('aborto previo no emite veredicto funcional ni consume versión y sale con error', async () => {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'g93-aborto-'));
  const dir = path.join(tmp, RUN);
  try {
    const r = await evaluar({ operacion: 'reintentar', version: 1, intento: 2, runId: RUN,
      referencia: 'LOCAL', directorio: dir }, { env: { QA_AUTORIZADO: 'SI' },
      fetcher: () => { throw Error('RED_PROHIBIDA'); } });
    assert.equal(r.codigo_salida, 2);
    assert.equal(r.casos['TC-M03-184'].estado, 'NO_EJECUTADA');
    assert.equal(r.oficial, false);
    assert.equal(r.consume_version, false);
    assert.equal(r.cierre.run.cierre_http, null);
    assert.deepEqual([r.cierre.rollback.verificado, r.cierre.rollback.estado], [false, 'NO_APLICA']);
    assert.equal(r.cypress.total_pruebas, 0);
    assert.equal(r.comprobaciones.every(x => ['API', 'UI'].includes(x.fuente)), true);
    assert.equal(evaluarRegistro(r, dir, { runId: RUN, version: 1 }).clasificacion, 'TECNICO');
    assert.equal(evaluarRegistro({ ...r, cypress: [] }, dir).clasificacion, 'INCIERTO');
    assert.equal(evaluarRegistro({ ...r, run_id: 'INCORRECTO' }, dir,
      { runId: RUN, version: 1 }).clasificacion, 'INCIERTO');
  } finally { fs.rmSync(tmp, { recursive: true, force: true }); }
});

test('serialización completa y barreras de oficialidad del registro', () => {
  const temporal = fs.mkdtempSync(path.join(os.tmpdir(), 'g93-serializacion-'));
  try {
    const variantes = ['aprobado', 'rechazado', 'comprobacion_pendiente', 'cypress_cero',
      'delete_no_200', 'rollback_no_verificado', 'evidencia_ausente', 'informe_ausente'];
    for (const variante of variantes) {
      const directorio = path.join(temporal, variante);
      fs.mkdirSync(directorio);
      const contrato = { runId: RUN, version: 1, directorio };
      fs.writeFileSync(path.join(directorio, 'preflight.json'), '{}');
      fs.mkdirSync(path.join(directorio, 'actas'));
      for (const fase of ['V1', 'V2']) fs.writeFileSync(path.join(directorio, `actas/${fase}.json`), '{}');
      const r = { grupo: 'G93', run_id: RUN, version: 1, autorizacion: 'LOCAL_SINTETICO',
        directorio, oficial: false, consume_version: true, operacion: 'evaluar', commit: null,
        datos: { ids_telemetria: [], id_area_v1: 900, id_area_v2: 349 },
        casos: { 'TC-M03-184': { id: 'TC-M03-184', estado: 'NO_EJECUTADA',
          estado_tecnico: 'NO_EJECUTADA', motivo: 'Sin iniciar', observado: {} } },
        variantes: { V1: 'APROBADO', V2: 'APROBADO' }, comprobaciones: [], bitacora: [],
        newman: [], cypress: { total_pruebas: 2, detalle: [
          { fase: 'V1', ejecutadas: 1 }, { fase: 'V2', ejecutadas: 1 }] },
        evidencias: ['preflight.json', 'resultado.json', 'actas/V1.json', 'actas/V2.json'],
        problemas_tecnicos: [], hallazgos_rendimiento: [], dependencias: [],
        observaciones_documentales: [], cierre: { run: { cierre_http: 200 },
          rollback: { verificado: true, estado: 'CONFIRMADO', comprobaciones: [
            { recurso: 'area_v1', http: 404, ok: true },
            { recurso: 'dashboard_area_v1', http: 200, ok: true },
            { recurso: 'semilla_v2_estable', http: 200, ok: true }] },
          motivo: 'DELETE y relaciones públicas acreditadas' } };
      for (const [fuente, ids] of Object.entries(CAPACIDADES.comprobaciones_obligatorias['TC-M03-184'])) {
        for (const id of ids) registrar(r, id, fuente,
          variante === 'rechazado' && id === 'API-184-01' ? 'RECHAZADO'
            : variante === 'comprobacion_pendiente' && id === 'UI-184-02' ? 'NO_EJECUTADA' : 'APROBADO',
          'Resultado de orquestación sintético', fuente === 'UI'
            ? `actas/${id === 'UI-184-01' ? 'V1' : 'V2'}.json` : 'preflight.json');
      }
      if (variante === 'cypress_cero') r.cypress.total_pruebas = 0;
      if (variante === 'delete_no_200') r.cierre.run.cierre_http = 500;
      if (variante === 'rollback_no_verificado') r.cierre.rollback.verificado = false;
      if (variante === 'evidencia_ausente') r.evidencias.push('actas/no-existe.json');
      serializarResultado(contrato, r, { escribirInforme: variante !== 'informe_ausente' });
      const salida = JSON.parse(fs.readFileSync(path.join(directorio, 'resultado.json'), 'utf8'));
      const revision = evaluarRegistro(salida, directorio, { runId: RUN, version: 1 });
      assert.equal(revision.estructura, true, variante);
      assert.equal(salida.consume_version, true, variante);
      assert.equal(salida.comprobaciones.length, 5, variante);
      if (['aprobado', 'rechazado'].includes(variante)) {
        assert.equal(revision.completo, true, variante);
        assert.equal(revision.estado_run, 'CERRADO', variante);
        assert.equal(revision.evidencias, true, variante);
        assert.equal(revision.oficialPosible, true, variante);
        assert.equal(revision.clasificacion, 'OFICIAL', variante);
        assert.equal(salida.oficial, true, variante);
        assert.equal(salida.cypress.total_pruebas, 2, variante);
        assert.equal(salida.cierre.run.cierre_http, 200, variante);
        assert.equal(salida.cierre.rollback.verificado, true, variante);
        assert.equal(salida.casos['TC-M03-184'].estado,
          variante === 'rechazado' ? 'RECHAZADO' : 'APROBADO');
        assert.equal(fs.readdirSync(directorio).filter(x => x.endsWith('.md')).length, 1);
      } else {
        assert.equal(revision.oficialPosible, false, variante);
        assert.notEqual(revision.clasificacion, 'OFICIAL', variante);
        assert.equal(salida.oficial, false, variante);
        if (variante === 'cypress_cero') {
          assert.notEqual(salida.casos['TC-M03-184'].estado, 'APROBADO');
          assert.equal(salida.casos['TC-M03-184'].estado_tecnico, 'ERROR_QA');
        }
      }
    }
  } finally { fs.rmSync(temporal, { recursive: true, force: true }); }
});
