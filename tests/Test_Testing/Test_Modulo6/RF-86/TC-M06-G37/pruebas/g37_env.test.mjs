import assert from 'node:assert/strict';
import test from 'node:test';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';
import { spawn } from 'node:child_process';
import http from 'node:http';
import os from 'node:os';
import { CASOS, CONTRATO, mock, validarMock, leerCampo, validarActor } from '../lib/g37_core.mjs';
import { CAPACIDADES, esquema, compararEsquema, contrastarRespuesta, aplicarDiscrepancias } from '../g37.mjs';
import { directorioNewman, sanearReporte, resumirEjecuciones } from './newman_hijo.mjs';
import fs from 'node:fs';
import { randomInt } from 'node:crypto';
import { leerEnv, principal } from '../g37.mjs';

const dir = path.dirname(fileURLToPath(import.meta.url));
const grupo = path.resolve(dir, '..');
const envLocal = base => [
  `SIGAB_API_TEST_BASE=${base}`, 'QA_SANDBOX_SECRET=secreto-ficticio',
  'QA_CONTADOR_EMAIL=contador@ejemplo.invalid', 'QA_CONTADOR_PASSWORD=clave-ficticia',
  'QA_ADMIN_EMAIL=admin@ejemplo.invalid', 'QA_ADMIN_PASSWORD=clave-ficticia',
  'QA_AUTORIZADO=NO'
].join('\n');
function runTemporal() {
  let runId, directorio;
  const baseTemporal = fs.mkdtempSync(path.join(os.tmpdir(), 'g37-run-'));
  do {
    runId = `RUN-G37-V1-20261108-${String(randomInt(1000000)).padStart(6, '0')}`;
    directorio = path.join(baseTemporal, runId);
  } while (fs.existsSync(directorio));
  fs.mkdirSync(directorio, { recursive: true });
  const referencia = 'AUT-G37-V1-20261108';
  const contexto = path.join(directorio, 'contexto_operacion.json');
  fs.writeFileSync(contexto, JSON.stringify({ grupo: 'G37', run_id: runId, version: 1, intento: 1,
    operacion: 'EVALUAR', referencia, casos: ['TC-M06-011', 'TC-M06-012', 'TC-M06-013'] }));
  return { runId, directorio, baseTemporal, args: ['--autorizacion', referencia, '--operacion', 'evaluar',
    '--version', '1', '--intento', '1', '--run-id', runId, '--contexto', contexto] };
}
function limpiarRun(x) {
  assert.equal(path.dirname(path.resolve(x.directorio)), x.baseTemporal);
  fs.rmSync(x.baseTemporal, { recursive: true, force: true });
}
test('leerEnv usa archivo temporal, prioridad del proceso y autorización solo del proceso', () => {
  const temporal = fs.mkdtempSync(path.join(os.tmpdir(), 'g37-env-'));
  try {
    const archivo = path.join(temporal, 'local.env');
    fs.writeFileSync(archivo, envLocal('http://127.0.0.1:1234'));
    const env = leerEnv({ QA_AUTORIZADO: 'SI', QA_CONTADOR_EMAIL: 'proceso@ejemplo.invalid' }, archivo);
    assert.equal(env.SIGAB_API_TEST_BASE, 'http://127.0.0.1:1234');
    assert.equal(env.QA_CONTADOR_EMAIL, 'proceso@ejemplo.invalid');
    assert.equal(env.QA_AUTORIZADO, 'SI');
    const sinPermiso = leerEnv({ QA_AUTORIZADO: 'NO' }, archivo);
    assert.equal(sinPermiso.SIGAB_API_TEST_BASE, undefined);
    assert.equal(sinPermiso.QA_AUTORIZADO, 'NO');
  } finally { fs.rmSync(temporal, { recursive: true, force: true }); }
});
test('principal escribe preflight antes del primer fetcher con entorno del lanzador', async () => {
  const run = runTemporal(), temporal = fs.mkdtempSync(path.join(os.tmpdir(), 'g37-env-'));
  try {
    const archivo = path.join(temporal, 'local.env');
    fs.writeFileSync(archivo, envLocal('http://127.0.0.1:1234'));
    let llamadas = 0;
    const salida = await principal(run.args, { proceso: { QA_AUTORIZADO: 'SI' }, archivoEnv: archivo,
      ensayo: true, fetcher: async () => {
        llamadas++;
        const p = JSON.parse(fs.readFileSync(path.join(run.directorio, 'preflight.json')));
        assert.equal(p.ok, true);
        assert.equal(p.fase, 'PREFLIGHT');
        return { status: 401, json: async () => null };
      } });
    assert.equal(salida.preflight.ok, true);
    assert.ok(llamadas > 0);
    assert.equal(salida.resultado.oficial, false);
  } finally { limpiarRun(run); fs.rmSync(temporal, { recursive: true, force: true }); }
});
test('principal rechaza secreto ausente sin petición ni resultado oficial', async () => {
  const run = runTemporal(), temporal = fs.mkdtempSync(path.join(os.tmpdir(), 'g37-env-'));
  try {
    const archivo = path.join(temporal, 'local.env');
    fs.writeFileSync(archivo, envLocal('http://127.0.0.1:1234').replace(/^QA_SANDBOX_SECRET=.*\n/m, ''));
    let llamadas = 0;
    const salida = await principal(run.args, { proceso: { QA_AUTORIZADO: 'SI' }, archivoEnv: archivo,
      ensayo: true, fetcher: async () => { llamadas++; throw Error('fetcher prohibido'); } });
    assert.equal(salida.exitCode, 2);
    assert.equal(salida.resultado, null);
    assert.equal(llamadas, 0);
    const p = JSON.parse(fs.readFileSync(path.join(run.directorio, 'preflight.json')));
    assert.equal(p.ok, false);
    assert.ok(p.barreras.includes('QA_SANDBOX_SECRET'));
    assert.equal(fs.existsSync(path.join(run.directorio, 'resultado.json')), false);
  } finally { limpiarRun(run); fs.rmSync(temporal, { recursive: true, force: true }); }
});
test('principal sin archivo env válido deja preflight y cero peticiones', async () => {
  const run = runTemporal(), temporal = fs.mkdtempSync(path.join(os.tmpdir(), 'g37-env-'));
  try {
    let llamadas = 0;
    const salida = await principal(run.args, { proceso: { QA_AUTORIZADO: 'SI' },
      archivoEnv: path.join(temporal, 'inexistente.env'), ensayo: true,
      fetcher: async () => { llamadas++; throw Error('fetcher prohibido'); } });
    assert.equal(salida.exitCode, 2);
    assert.equal(llamadas, 0);
    assert.equal(JSON.parse(fs.readFileSync(path.join(run.directorio, 'preflight.json'))).ok, false);
    assert.equal(fs.existsSync(path.join(run.directorio, 'resultado.json')), false);
  } finally { limpiarRun(run); fs.rmSync(temporal, { recursive: true, force: true }); }
});
test('iot_precondicion_invalida: preflight falla sin peticiones', async () => {
  const run = runTemporal(), temporal = fs.mkdtempSync(path.join(os.tmpdir(), 'g37-iot-'));
  try {
    const archivo = path.join(temporal, 'local.env');
    fs.writeFileSync(archivo, envLocal('http://127.0.0.1:1234'));
    const precondicion = JSON.parse(fs.readFileSync(path.join(grupo, 'pruebas', 'precondicion_iot.json'), 'utf8'));
    precondicion.fecha_evento_tb = '2026-11-09T12:00:00Z';
    const archivoIoT = path.join(temporal, 'precondicion_iot.json');
    fs.writeFileSync(archivoIoT, JSON.stringify(precondicion));
    let llamadas = 0;
    const salida = await principal(run.args, { proceso: { QA_AUTORIZADO: 'SI' }, archivoEnv: archivo,
      ensayo: true, precondicionIoTArchivo: archivoIoT,
      fetcher: async () => { llamadas++; throw Error('No debe haber peticiones'); } });
    assert.equal(salida.preflight.ok, false);
    assert.equal(llamadas, 0);
    assert.match(salida.preflight.barreras.join(' '), /PRECONDICION_IOT/);
    assert.match(salida.preflight.precondicion_iot_sha256, /^[a-f0-9]{64}$/);
    assert.equal(fs.existsSync(path.join(run.directorio, 'resultado.json')), false);
    process.stdout.write('OK escenario_iot_precondicion_invalida: 011=N/C 012=N/C 013=N/C oficial=no solicitudes=0/150\n');
  } finally { limpiarRun(run); fs.rmSync(temporal, { recursive: true, force: true }); }
});
test('CLI real del lanzador sin autorización escribe preflight y no crea resultado', async t => {
  const runId = 'RUN-G37-V1-20261108-000000';
  const directorio = path.join(grupo, 'Resultados', runId);
  assert.equal(fs.existsSync(directorio), false, `RUN sintético ya existente: ${runId}`);
  fs.mkdirSync(directorio);
  try {
    const referencia = 'AUT-G37-V1-20261108';
    const contexto = path.join(directorio, 'contexto_operacion.json');
    fs.writeFileSync(contexto, JSON.stringify({ grupo: 'G37', run_id: runId, version: 1, intento: 1,
      operacion: 'EVALUAR', referencia, casos: ['TC-M06-011', 'TC-M06-012', 'TC-M06-013'] }));
    const args = ['--autorizacion', referencia, '--operacion', 'evaluar', '--version', '1',
      '--intento', '1', '--run-id', runId, '--contexto', contexto];
    let hijo;
    try {
      hijo = spawn(process.execPath, [path.join(grupo, 'g37.mjs'), ...args], {
        cwd: grupo, env: { QA_AUTORIZADO: 'NO', SystemRoot: process.env.SystemRoot },
        stdio: ['ignore', 'pipe', 'pipe'], windowsHide: true });
    } catch (e) { if (e.code === 'EPERM') { t.skip('spawn EPERM: pendiente en Windows'); return; } throw e; }
    const salida = await new Promise((resolve, reject) => {
      let stdout = '', stderr = '';
      hijo.stdout.on('data', x => { stdout += x; });
      hijo.stderr.on('data', x => { stderr += x; });
      hijo.on('error', reject);
      hijo.on('close', code => resolve({ code, stdout, stderr }));
    }).catch(e => { if (e.code === 'EPERM') { t.skip('spawn EPERM: pendiente en Windows'); return null; } throw e; });
    if (!salida) return;
    assert.notEqual(salida.code, 0);
    const p = JSON.parse(fs.readFileSync(path.join(directorio, 'preflight.json')));
    assert.equal(p.ok, false);
    assert.ok(p.barreras.includes('QA_AUTORIZADO'));
    assert.equal(fs.existsSync(path.join(directorio, 'resultado.json')), false);
  } finally {
    assert.equal(path.dirname(path.resolve(directorio)), path.join(grupo, 'Resultados'));
    fs.rmSync(directorio, { recursive: true, force: true });
  }
});
test('CLI real rechaza contexto temporal fuera de Resultados sin escribir archivos', async t => {
  const run = runTemporal();
  const resultados = path.join(grupo, 'Resultados');
  try {
    const archivosAntes = fs.readdirSync(run.directorio).sort();
    const resultadosAntes = fs.readdirSync(resultados, { recursive: true }).sort();
    const grupoAntes = fs.readdirSync(grupo).sort();
    let hijo;
    try {
      hijo = spawn(process.execPath, [path.join(grupo, 'g37.mjs'), ...run.args], {
        cwd: grupo, env: { QA_AUTORIZADO: 'NO', SystemRoot: process.env.SystemRoot },
        stdio: ['ignore', 'pipe', 'pipe'], windowsHide: true });
    } catch (e) { if (e.code === 'EPERM') { t.skip('spawn EPERM: pendiente en Windows'); return; } throw e; }
    const salida = await new Promise((resolve, reject) => {
      let stderr = '';
      hijo.stdout.resume();
      hijo.stderr.on('data', x => { stderr += x; });
      hijo.on('error', reject);
      hijo.on('close', code => resolve({ code, stderr }));
    }).catch(e => { if (e.code === 'EPERM') { t.skip('spawn EPERM: pendiente en Windows'); return null; } throw e; });
    if (!salida) return;
    assert.notEqual(salida.code, 0);
    assert.match(salida.stderr, /Contexto fuera del RUN/);
    assert.deepEqual(fs.readdirSync(run.directorio).sort(), archivosAntes);
    assert.deepEqual(fs.readdirSync(resultados, { recursive: true }).sort(), resultadosAntes);
    assert.deepEqual(fs.readdirSync(grupo).sort(), grupoAntes);
  } finally { limpiarRun(run); }
});
function rutasCampos(obj, prefijo = '') {
  return Object.entries(obj).flatMap(([k, v]) => {
    const ruta = prefijo ? `${prefijo}.${k}` : k;
    if (Array.isArray(v)) return typeof v[0] === 'string' ? [ruta] : rutasCampos(v[0], `${ruta}[]`);
    return typeof v === 'string' ? [ruta] : rutasCampos(v, ruta);
  });
}
test('contrato, mocks y campos leídos', () => {
  for (const p of CONTRATO.peticiones) {
    const cuerpo = mock(p.id);
    assert.equal(validarMock(p.id, cuerpo), true);
    assert.equal(compararEsquema(p.id, esquema(cuerpo)), true);
    assert.equal(validarActor(p.id, p.actor), true);
    const campos = Object.keys(p.fuentes_campos ?? {});
    assert.deepEqual(campos.sort(), [...rutasCampos(p.campos),
      ...(p.subcampos_eslabones ? rutasCampos(p.subcampos_eslabones, 'eslabones') : []),
      ...(p.subcampos_ultimo_cierre ? ['ultimo_cierre.precios_congelados[].precio_unitario'] : [])].sort(),
    `Citas por campo incompletas en ${p.id}`);
    assert.ok(campos.every(k => /\.py:\d/.test(p.fuentes_campos[k])), `Cita incompleta en ${p.id}`);
  }
  const x = mock('variaciones');
  assert.equal(typeof leerCampo('variaciones', x, '[].id_variacion_valor_razonable'), 'number');
  assert.throws(() => leerCampo('variaciones', x, '[].id_evento'), /ausente/);
  assert.throws(() => validarMock('variaciones', [{ ...x[0], id_evento: 1 }]), /no declarado/);
  const sinCampo = { ...x[0] }; delete sinCampo.monto_variacion;
  assert.throws(() => validarMock('variaciones', [sinCampo]), /ausente/);
  assert.throws(() => compararEsquema('variaciones', esquema([sinCampo])), /sin campo/);
  const segundo = { ...x[0], monto_variacion: 'TIPO_INCORRECTO' };
  assert.throws(() => validarMock('variaciones', [segundo]), /Tipo fuera/);
  assert.throws(() => compararEsquema('variaciones', esquema([{ ...x[0], id_activo_biologico: '1' }])), /esperado number, llegó string/);
  assert.throws(() => validarActor('ficha', 'contador'), /sin permiso/);
});
test('esquemas reales del intento 3 y negativos estrictos', () => {
  const run = JSON.parse(fs.readFileSync(path.join(dir, '..', 'Resultados',
    'RUN-G37-V1-20261108-205523', 'resultado.json'), 'utf8'));
  for (const id of ['activos', 'periodos']) {
    const observado = run.contraste_contrato.find(x => x.id === id).esquema_real;
    assert.equal(compararEsquema(id, observado), true);
  }
  const activos = mock('activos');
  activos[0].valor_razonable_neto = null;
  assert.equal(validarMock('activos', activos), true);
  const periodos = mock('periodos');
  periodos[0].numero_id_tributaria = null;
  assert.equal(validarMock('periodos', periodos), true);
  periodos[0].ultimo_cierre = { precios_congelados: [{ precio_unitario: '123.45' }] };
  assert.equal(compararEsquema('periodos', esquema(periodos)), true);
  assert.equal(contrastarRespuesta({ contraste_contrato: [], discrepancias_contrato: [], problemas_tecnicos: [] },
    'periodos', 'contador', 200, periodos), true);
  const v = mock('variaciones');
  v[0].monto_variacion = '0.10';
  assert.equal(validarMock('variaciones', v), true);
  assert.throws(() => validarMock('variaciones', [{ ...v[0], monto_variacion: '1e3' }]), /Tipo fuera/);
  assert.throws(() => compararEsquema('variaciones', esquema([{ ...v[0], tipo: 1 }])), /esperado string, llegó number/);
});
test('precios_post del intento 7 coincide con el contrato y conserva ID', () => {
  const run = JSON.parse(fs.readFileSync(path.join(dir, '..', 'Resultados',
    'RUN-G37-V1-20261108-230500', 'resultado.json'), 'utf8'));
  const observado = run.discrepancias_contrato.find(x => x.id === 'precios_post').esquema_real;
  const respuesta = { id_precio_mercado: 201, estado: 'ACTIVO', unidad_medida: 'kg',
    desviacion_pct: '5.00', fecha_vigencia: '2026-11-08' };
  assert.deepEqual(esquema(respuesta), observado);
  const r = { contraste_contrato: [], discrepancias_contrato: [], problemas_tecnicos: [] };
  assert.equal(contrastarRespuesta(r, 'precios_post', 'contador', 201, respuesta, '/finanzas/precios'), true);
  assert.equal(r.contraste_contrato[0].resultado, 'coincide');
  assert.equal(r.discrepancias_contrato.length, 0);
});
test('cadena real del intento 6 coincide y los tipos erróneos siguen fallando', () => {
  const run = JSON.parse(fs.readFileSync(path.join(dir, '..', 'Resultados',
    'RUN-G37-V1-20261108-220244', 'resultado.json'), 'utf8'));
  const observado = run.contraste_contrato.find(x => x.id === 'cadena' && x.esquema_real).esquema_real;
  assert.equal(compararEsquema('cadena', observado), true);
  const sinFallo = structuredClone(observado);
  sinFallo.eslabones.nivel_fallo = 'null';
  assert.equal(compararEsquema('cadena', sinFallo), true);
  const pendiente = structuredClone(observado);
  pendiente.estado_verificacion = 'null'; pendiente.nivel_fallo = 'null'; pendiente.eslabones = 'null';
  assert.equal(compararEsquema('cadena', pendiente), true);
  const tipoErroneo = structuredClone(pendiente); tipoErroneo.eslabones = 'array';
  assert.throws(() => compararEsquema('cadena', tipoErroneo), /cadena\.eslabones; esperado object\|null, lleg/);
  assert.throws(() => validarMock('cadena', { ...mock('cadena'), eslabones: [] }), /Tipo fuera/);
  const malo = structuredClone(observado);
  malo.eslabones.nivel_fallo = 'string';
  assert.throws(() => compararEsquema('cadena', malo),
    /cadena\.eslabones\.nivel_fallo; esperado number\|null, llegó string/);
  const r = { contraste_contrato: [], discrepancias_contrato: [{ id: 'cadena',
    ruta: '/finanzas/lineas/{linea}/cadena', fase: 'previa', resultado: 'discrepa',
    motivo: 'Esquema discordante: cadena.eslabones.nivel_fallo; esperado string|null, llegó number' }],
    problemas_tecnicos: [], casos: {}, comprobaciones: [], incidencias: [] };
  aplicarDiscrepancias(r);
  for (const caso of ['TC-M06-011', 'TC-M06-012', 'TC-M06-013']) {
    assert.equal(r.casos[caso].estado, 'NO_CONCLUYENTE');
    assert.equal(r.casos[caso].motivo,
      'Lectura previa /finanzas/lineas/{linea}/cadena: campo cadena.eslabones.nivel_fallo esperado string|null, recibido number; sin escrituras.');
  }
});

test('paginación discordante conserva solo esquema y motivo', () => {
  const r = { contraste_contrato: [], discrepancias_contrato: [], problemas_tecnicos: [] };
  const data = mock('auditoria');
  data.pagina_actual = 2; data.registros_por_pagina = 500;
  assert.equal(contrastarRespuesta(r, 'auditoria', 'contador', 200, data,
    '/finanzas/auditoria?pagina=1&tamano=500'), false);
  assert.equal(r.discrepancias_contrato[0].motivo, 'Paginación distinta del contrato');
  assert.equal(r.discrepancias_contrato[0].esquema_real.pagina_actual, 'number');
});
test('permisos de cada llamada Newman y del ejecutor', () => {
  const col = JSON.parse(fs.readFileSync(path.join(dir, '..', 'G37.postman_collection.json'), 'utf8'));
  assert.equal(col.item.length, 3);
  for (const p of CONTRATO.peticiones) {
    assert.equal(validarActor(p.id, p.actor), true);
    for (const actor of Object.keys(CONTRATO.roles).filter(x => x !== p.actor))
      assert.throws(() => validarActor(p.id, actor), /sin permiso/);
  }
  for (const item of col.item) {
    const p = CONTRATO.peticiones.find(x => x.id === item.name);
    assert.ok(p);
    assert.equal(item.request.method, p.metodo);
    assert.equal(item.request.header.find(x => x.key === 'Authorization')?.value, `Bearer {{${p.actor}_token}}`);
  }
  assert.deepEqual(CAPACIDADES.operaciones, ['evaluar', 'reintentar', 'reevaluar']);
  assert.equal(CAPACIDADES.limite.solicitudes_totales, 150);
});
test('ruta y version del paquete Newman junto al ejecutable de Node', () => {
  assert.equal(directorioNewman, path.join(path.dirname(process.execPath), 'node_modules', 'newman'));
  const require = createRequire(import.meta.url);
  const version = require(path.join(directorioNewman, 'package.json')).version;
  assert.match(version, /^\d+\.\d+\.\d+/);
  process.stdout.write(`OK paquete_newman ${version}\n`);
});
test('hijo Newman ejecuta una lectura HTTP loopback con el protocolo del RUN', async t => {
  const grupo = path.resolve(dir, '..');
  const archivosAntes = fs.readdirSync(grupo).sort();
  const baseTemporal = fs.realpathSync(os.tmpdir());
  const temporal = fs.mkdtempSync(path.join(baseTemporal, 'g37-newman-'));
  const salida = path.join(temporal, 'RUN-G37-V1-20261108-000000', 'newman');
  const runId = 'RUN-G37-V1-20261108-000000';
  const token = 'token-local-ficticio';
  const secreto = 'secreto-local-ficticio';
  let lecturas = 0;
  const servidor = http.createServer((req, res) => {
    lecturas++;
    if (req.method !== 'GET' || req.url !== '/finanzas/periodos/8/estados-resultados') {
      res.writeHead(404).end();
      return;
    }
    res.writeHead(200, { 'Content-Type': 'application/json', 'X-Test-Run-Id': req.headers['x-test-run-id'] });
    res.end(JSON.stringify(mock('estados_get')));
  });
  try {
    await new Promise(resolve => servidor.listen(0, '127.0.0.1', resolve));
    const puerto = servidor.address().port;
    const coleccionVigente = JSON.parse(fs.readFileSync(path.join(grupo, 'G37.postman_collection.json'), 'utf8'));
    const coleccion = { ...coleccionVigente, item: [coleccionVigente.item[0]] };
    const environment = { values: Object.entries({ base_url: `http://127.0.0.1:${puerto}`, run_id: runId,
      sandbox_secret: secreto, contador_token: token, admin_token: token, periodo: '8', linea: '0' })
      .map(([key, value]) => ({ key, value, enabled: true })) };
    let hijo;
    try {
      hijo = spawn(process.execPath, [path.join(dir, 'newman_hijo.mjs')], {
        stdio: ['pipe', 'pipe', 'pipe'], windowsHide: true, timeout: 160000 });
    } catch (e) { if (e.code === 'EPERM') { t.skip('spawn EPERM: pendiente en Windows'); return; } throw e; }
    let stdout = '', stderr = '';
    hijo.stdout.setEncoding('utf8').on('data', x => { stdout += x; });
    hijo.stderr.setEncoding('utf8').on('data', x => { stderr += x; });
    const fin = new Promise((resolve, reject) => {
      hijo.once('error', reject);
      hijo.once('close', (code, signal) => resolve({ code, signal }));
    });
    hijo.stdin.end(JSON.stringify({ coleccion, environment, timeout: 30000, salida }));
    const { code, signal } = await fin;
    const stderrSaneado = sanearReporte(stderr, [token, secreto]);
    assert.equal(code, 0, `Hijo Newman: codigo ${code}, senal ${signal}; stderr saneado: ${stderrSaneado}`);
    let resumen;
    try { resumen = JSON.parse(stdout); }
    catch { assert.fail(`Salida JSON invalida del hijo Newman; stderr saneado: ${stderrSaneado}`); }
    assert.equal(lecturas, 1);
    assert.equal(resumen.error, null);
    assert.equal(resumen.solicitudes.length, 1);
    assert.equal(resumen.solicitudes[0].nombre, 'estados_get');
    assert.equal(resumen.solicitudes[0].http, 200);
    assert.equal(resumen.solicitudes[0].contraste.resultado, 'coincide');
    assert.ok(resumen.solicitudes[0].aserciones.length > 0);
    assert.equal(resumen.solicitudes[0].aserciones.filter(x => x.error).length, 0);
    assert.deepEqual(resumen.reportes, { json: true, html: true });
    assert.equal(path.relative(baseTemporal, salida).startsWith('..'), false);
    assert.ok(fs.existsSync(path.join(salida, 'newman-G37.json')));
    assert.ok(fs.existsSync(path.join(salida, 'newman-G37.html')));
    assert.deepEqual(fs.readdirSync(grupo).sort(), archivosAntes);
    process.stdout.write('OK newman_hijo: process.execPath, 1 lectura loopback HTTP 200\n');
  } finally {
    if (servidor.listening) await new Promise(resolve => servidor.close(resolve));
    assert.equal(path.dirname(fs.realpathSync(temporal)), baseTemporal);
    fs.rmSync(temporal, { recursive: true, force: true });
  }
  assert.equal(fs.existsSync(temporal), false);
});
test('reportes Newman saneados sin perder conteos', () => {
  const entrada = JSON.stringify({ run: { stats: { requests: { total: 3 } }, executions: [
    { request: { header: [{ key: 'Authorization', value: 'token-ficticio-abc' }], body: 'privado' },
      response: { stream: 'privado', code: 200 } }] } });
  const salida = sanearReporte(entrada, ['token-ficticio-abc'], true);
  assert.equal(JSON.parse(salida).run.stats.requests.total, 3);
  assert.ok(!salida.includes('token-ficticio-abc'));
  assert.ok(!salida.includes('privado'));
  assert.ok(!sanearReporte('<div>token-ficticio-abc ejemplo@dominio.test</div>', ['token-ficticio-abc'])
    .includes('ejemplo@dominio.test'));
});

test('síntesis Newman contrasta nombres y tipos sin valores', () => {
  const cuerpo = mock('estados_get');
  delete cuerpo[0].total_gastos;
  cuerpo[0].estado = 'PRIVADO_SIN_SALIDA';
  const resumen = resumirEjecuciones({ run: { executions: [{ item: { name: 'estados_get' },
    response: { code: 200, json: () => cuerpo }, assertions: [] }] } },
  { environment: { values: [{ key: 'periodo', value: '8' }, { key: 'linea', value: '9' }] } });
  assert.equal(resumen[0].contraste.resultado, 'discrepa');
  assert.equal(resumen[0].contraste.esquema_real.items[0].total_gastos, undefined);
  assert.ok(!JSON.stringify(resumen).includes('PRIVADO_SIN_SALIDA'));
});

// El servidor representa solamente el contrato HTTP local. Cada respuesta tarda lo suficiente
// para detectar peticiones simultáneas tanto del ejecutor como del hijo Newman.
async function flujoCompletoSerie(t, conNewman, escenario = 'normal') {
  const probable = ['probable', 'iot_precondicion_rf91_500', 'fila_rf93_post', 'fila_rf91', 'replay_intento7_500'].includes(escenario);
  const replay = escenario.startsWith('replay_intento7_');
  const rf93NoCerrado = probable || replay;
  const fechaIncoherente = escenario.startsWith('iot_fecha_');
  const codigoFecha = escenario === 'iot_fecha_anterior_registro' ? 'FECHA_ANTERIOR_REGISTRO' :
    escenario === 'iot_fecha_futura' ? 'FECHA_FUTURA' : 'FECHA_INCOHERENTE';
  const sinLectura = escenario === 'iot_lectura_no_navegable';
  const sin943 = escenario === 'iot_943_no_elegible';
  const run = runTemporal();
  const temporal = fs.mkdtempSync(path.join(os.tmpdir(), 'g37-flujo-'));
  const estado = { abiertas: 0, solapamientos: 0, peticiones: [], cerrado: false,
    eventos: [], precios: [], variaciones: [], lineas: [], mediciones: [], auditorias: [],
    estados: [], siguienteEvento: 100, siguientePrecio: 200, siguienteVariacion: 300,
    inyectado: false, lineasLeidas: 0, cadenasLeidas: 0,
    siguienteLinea: 400, siguienteAuditoria: 500, siguienteEstado: 600 };
  const copia = id => structuredClone(mock(id));
  const fecha = new Date().toLocaleDateString('en-CA', { timeZone: 'America/Bogota' });
  const servidor = http.createServer(async (req, res) => {
    const ruta = new URL(req.url, 'http://127.0.0.1');
    const runHeader = req.headers['x-test-run-id'];
    const esNewman = req.headers['user-agent']?.includes('PostmanRuntime') ?? false;
    const registro = { metodo: req.method, ruta: ruta.pathname, consulta: ruta.search, newman: esNewman,
      poscierre: estado.cerrado, run: runHeader };
    estado.peticiones.push(registro);
    const solapada = estado.abiertas > 0;
    if (solapada) estado.solapamientos++;
    estado.abiertas++;
    try {
      let cuerpo = '';
      for await (const chunk of req) cuerpo += chunk;
      if (req.method === 'POST' && ruta.pathname.endsWith('/eventos/crecimiento')) {
        registro.fecha = JSON.parse(cuerpo).fecha ?? null;
      }
      await new Promise(resolve => setTimeout(resolve, 8));
      if (solapada) {
        registro.http = 500;
        res.writeHead(500, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ code: 'CONCURRENCIA' }));
        return;
      }
      let status = 200, data = null;
      const p = ruta.pathname, metodo = req.method;
      if (metodo === 'GET' && p === '/finanzas/lineas') estado.lineasLeidas++;
      if (metodo === 'GET' && /\/finanzas\/lineas\/\d+\/cadena$/.test(p)) estado.cadenasLeidas++;
      const falloFila = !estado.inyectado && (
        escenario === 'fila_seleccion' && p === '/finanzas/activos' ||
        escenario === 'fila_permisos' && p === '/sesiones/me/permisos' ||
        escenario === 'fila_lecturas_previas' && p === '/finanzas/periodos/8/estados-resultados' && metodo === 'GET' ||
        escenario === 'fila_rebase' && p === '/activos-biologicos/943/eventos/crecimiento' && cuerpo.includes('Rebase QA') ||
        escenario === 'fila_eventos_m02' && p === '/activos-biologicos/943/eventos/crecimiento' ||
        escenario === 'fila_patch_estado' && p === '/activos-biologicos/944/estado' ||
        escenario === 'fila_precios' && p === '/finanzas/precios' && metodo === 'POST' ||
        escenario === 'fila_procesar' && p === '/finanzas/eventos/procesar' && metodo === 'POST' ||
        escenario === 'fila_lecturas_posteriores' && p === '/finanzas/lineas' && estado.lineasLeidas === 2 ||
        escenario === 'fila_cadena_inicial' && /\/finanzas\/lineas\/\d+\/cadena$/.test(p) && estado.cadenasLeidas === 1 ||
        escenario === 'fila_cadena_final' && /\/finanzas\/lineas\/\d+\/cadena$/.test(p) && estado.cadenasLeidas === 2 ||
        escenario === 'fila_cierre' && p === `/test-control/runs/${run.runId}` && metodo === 'DELETE');
      if (falloFila) {
        estado.inyectado = true;
        status = escenario === 'fila_permisos' ? 403 : escenario === 'fila_rebase' ? 400 : 500;
        data = { error_code: status === 400 ? 'FECHA_INCOHERENTE' : 'ERROR_INTERNO', message: 'Fallo simulado', fields: [], timestamp: new Date().toISOString() };
        registro.http = status;
        res.writeHead(status, { 'Content-Type': 'application/json', 'X-Test-Run-Id': run.runId });
        res.end(JSON.stringify(data)); return;
      }
      const activo = Number(p.match(/\/(\d+)\/(?:ficha-integral|eventos(?:\/crecimiento)?|estado)$/)?.[1]);
      if (p === '/sesiones/' && metodo === 'POST') data = { token: 'token-local-ficticio' };
      else if (p === '/sesiones/me/permisos') data = { permisos: Object.entries(CONTRATO.roles.contador.permisos).flatMap(([nombre_recurso, acciones]) => acciones.map(id_accion => ({ id_recurso: 1, id_accion, nombre_recurso }))).concat(Object.entries(CONTRATO.roles.admin.permisos).flatMap(([nombre_recurso, acciones]) => acciones.map(id_accion => ({ id_recurso: 1, id_accion, nombre_recurso })))) };
      else if (p === '/notificaciones') data = { items: [] };
      else if (p === '/finanzas/activos') data = [943, 944, 945, 946, 947, 948, 1567, 951,
        1568, 1572, 1573, 1569, 1570, 1571, 950, 949].map((aid, i) => ({ ...copia('activos')[0],
        id_activo_biologico: aid, id_especie: i < 6 ? 10 : 11 + (i % 4),
        especie: i < 6 ? 'Bovino' : 'Otra especie', tipo: 'INDIVIDUAL',
        estado: aid === 948 || sin943 && aid === 943 ? 'INACTIVO' : 'ACTIVO', valorado_por_costo: i >= 6 }));
      else if (p === '/finanzas/periodos') data = [{ ...copia('periodos')[0], id_periodo_contable: 8,
        numero_id_tributaria: 'NIT_LOCAL', fecha_inicio: '2026-01-01', fecha_fin: '2027-12-31', estado: 'ABIERTO' }];
      else if (/^\/finanzas\/activos\/\d+$/.test(p)) {
        data = copia('activo_detalle'); data.activo.numero_id_tributaria = 'NIT_LOCAL';
        const aid = Number(p.split('/').at(-1));
        data.activo.id_dispositivo_iot = ({ 943: 849, 944: 850, 946: 851 })[aid] ?? null;
        data.calculos[0].estado = 'CALCULADO'; data.calculos[0].id_precio_mercado = escenario === 'fila_rebase' && aid === 943 ? 19 : 20;
        data.calculos[0].fecha_calculo = fecha;
      }
      else if (p.endsWith('/ficha-integral')) {
        data = copia('ficha'); data.peso_actual = '100.00'; data.unidad_peso = 'kg';
        data.estado_actual = estado.cerrado || !estado.eventos.some(x => x.activo === activo && x.tratamiento) ?
          'ACTIVO' : 'EN_TRATAMIENTO';
      }
      else if (p.endsWith('/eventos/crecimiento') && metodo === 'POST') {
        if (fechaIncoherente && activo === 943) {
          status = 400; data = { error_code: codigoFecha, message: 'Fecha incoherente', fields: [], timestamp: new Date().toISOString() };
        } else {
          status = 201; data = copia('evento_crecimiento'); data.evento.id_eventos = ++estado.siguienteEvento;
          estado.eventos.push({ id: data.evento.id_eventos, activo, procesado: false });
        }
      }
      else if (p.endsWith('/eventos') && metodo === 'GET') {
        data = copia('eventos_get'); data.eventos = estado.cerrado ? [] :
          estado.eventos.filter(x => x.activo === activo).map(x => ({ id_eventos: x.id }));
      }
      else if (p.endsWith('/estado') && metodo === 'PATCH') {
        data = copia('estado_patch'); const ultimo = [...estado.eventos].reverse().find(x => x.activo === activo);
        if (ultimo) ultimo.tratamiento = true;
      }
      else if (p === '/finanzas/precios' && metodo === 'GET') {
        const especie = Number(ruta.searchParams.get('id_especie') ?? 10);
        data = [{ ...copia('precios_get')[0], id_precio_mercado: 20, id_especie: especie,
          categoria: 'PESO_KG', fuente: 'MERCADO_ACTIVO', fecha_vigencia: '2026-01-01', fecha_vencimiento: '2027-12-31' },
        ...(estado.cerrado ? [] : estado.precios)];
      }
      else if (p === '/finanzas/precios' && metodo === 'POST') {
        status = 201; data = copia('precios_post'); data.id_precio_mercado = ++estado.siguientePrecio;
        estado.precios.push({ ...copia('precios_get')[0], id_precio_mercado: data.id_precio_mercado,
          id_especie: 10, categoria: 'PESO_KG', fuente: 'MERCADO_ACTIVO',
          fecha_vigencia: fecha, fecha_vencimiento: '2027-12-31' });
      }
      else if (p === '/finanzas/eventos/procesar' && metodo === 'POST') {
        data = copia('procesar');
        for (const ev of estado.eventos.filter(x => !x.procesado)) {
          ev.procesado = true;
          const v = copia('variaciones')[0];
          Object.assign(v, { id_variacion_valor_razonable: ++estado.siguienteVariacion,
            id_activo_biologico: ev.activo, id_linea: ++estado.siguienteLinea,
            tipo: ['GANANCIA_TRANSFORMACION_BIOLOGICA', 'PERDIDA_TRANSFORMACION_BIOLOGICA',
              'GANANCIA_PRECIO_MERCADO', 'PERDIDA_PRECIO_MERCADO'][(ev.activo - 943) % 4],
            monto_variacion: (ev.activo - 943) % 2 ? '-1.00' : '1.00', estado_trazabilidad: 'VERIFICACION_PENDIENTE' });
          estado.variaciones.push(v);
          estado.lineas.push({ ...copia('lineas')[0], id_linea_asiento_nic41: v.id_linea });
          const au = copia('auditoria').eventos[0];
          Object.assign(au, { id_evento: ++estado.siguienteAuditoria, id_referencia: v.id_variacion_valor_razonable,
            id_activo_biologico: ev.activo, id_periodo_contable: 8, tipo_evento: 'VARIACION_REGISTRADA',
            monto_afectado: v.monto_variacion });
          au.payload_evento = { tipo: v.tipo, monto: v.monto_variacion, id_evento: ev.id, id_cierre: null };
          estado.auditorias.push(au);
        }
      }
      else if (/^\/finanzas\/periodos\/8\/variaciones$/.test(p)) data = estado.cerrado ? [] : estado.variaciones;
      else if (/^\/finanzas\/periodos\/8\/mediciones$/.test(p)) data = estado.cerrado ? [] : estado.mediciones;
      else if (p === '/finanzas/lineas') data = estado.cerrado ? [] : estado.lineas;
      else if (/^\/finanzas\/lineas\/\d+\/cadena$/.test(p)) {
        data = copia('cadena'); data.id_linea_asiento_nic41 = Number(p.split('/')[3]);
        const verificada = estado.variaciones.some(x => x.id_linea === data.id_linea_asiento_nic41 &&
          x.estado_trazabilidad === 'VERIFICADO');
        data.estado_trazabilidad = verificada ? 'VERIFICADO' : 'VERIFICACION_PENDIENTE';
        data.estado_verificacion = verificada ? 'VERIFICADO' : null; data.nivel_fallo = null;
        if (verificada) {
          data.eslabones.nivel_fallo = null;
          data.eslabones.ids.id_evento = estado.eventos[0]?.id ?? 1;
          data.eslabones.ids.ids_lectura_iot = [120011];
        } else data.eslabones = null;
      }
      else if (/^\/finanzas\/periodos\/8\/estados-resultados$/.test(p) && metodo === 'POST') {
        if (rf93NoCerrado) { status = 422; data = { error_code: 'PERIODO_NO_CERRADO', message: 'Período no cerrado', fields: [], timestamp: new Date().toISOString() }; }
        else { status = 201; data = copia('estado_post'); data.id_estado = ++estado.siguienteEstado;
          estado.estados.push({ ...copia('estados_get')[0], id_estado: data.id_estado, id_periodo_contable: 8 }); }
      }
      else if (/^\/finanzas\/periodos\/8\/estados-resultados$/.test(p))
        data = estado.cerrado || rf93NoCerrado ? [] : [{ ...copia('estados_get')[0], id_estado: 1, id_periodo_contable: 8 }, ...estado.estados];
      else if (/^\/finanzas\/estados-resultados\/\d+$/.test(p)) data = copia('estado_detalle');
      else if (p === '/finanzas/auditoria') {
        data = copia('auditoria'); data.eventos = estado.cerrado ? [] : estado.auditorias;
        data.total_registros = data.eventos.length; data.pagina_actual = Number(ruta.searchParams.get('pagina') ?? 1);
        data.registros_por_pagina = 500;
      }
      else if (p === '/iot/monitoreo/historial') {
        data = copia('m03_historial');
        const paginaSensor = Number(ruta.searchParams.get('pagina'));
        data.items = (sinLectura && ruta.searchParams.get('sensor_id') === '1311') ||
          (escenario === 'iot_paginacion_sensor' && paginaSensor === 1) ?
          [] : [{ ...data.items[0], id_telemetria: 120011, id_activo_biologico: null }];
        data.total = data.items.length;
        data.pagina = paginaSensor; data.por_pagina = 100;
        data.paginas_totales = escenario === 'iot_paginacion_sensor' ? 3 : 1;
      }
      else if (/^\/finanzas\/periodos\/8\/trazabilidad$/.test(p) && metodo === 'POST') {
        if (probable) { status = 500; data = { error_code: 'ERROR_INTERNO', message: 'Error interno', fields: [], timestamp: new Date().toISOString() }; }
        else { data = copia('trazabilidad');
          estado.variaciones.forEach(x => { x.estado_trazabilidad = 'VERIFICADO'; }); }
      }
      else if (p === `/test-control/runs/${run.runId}` && metodo === 'DELETE') {
        data = {}; estado.cerrado = true;
      }
      else { status = 404; data = { code: 'RUTA_NO_SIMULADA' }; }
      registro.http = status;
      res.writeHead(status, { 'Content-Type': 'application/json', 'X-Test-Run-Id': run.runId });
      res.end(JSON.stringify(data));
    } finally { estado.abiertas--; }
  });
  try {
    await new Promise(resolve => servidor.listen(0, '127.0.0.1', resolve));
    const archivo = path.join(temporal, 'local.env');
    fs.writeFileSync(archivo, envLocal(`http://127.0.0.1:${servidor.address().port}`));
    const salida = await principal(run.args, { proceso: { QA_AUTORIZADO: 'SI' }, archivoEnv: archivo,
      ensayo: true, sinNewman: !conNewman });
    const r = salida.resultado;
    assert.ok(r, `Preflight: ${salida.preflight.barreras.join(', ')}`);
    if (conNewman && r.herramientas.newman?.error === 'EPERM') {
      t.skip('spawn EPERM: flujo con Newman pendiente para Windows'); return;
    }
    if (escenario.startsWith('fila_')) {
      assert.ok(estado.inyectado || ['fila_rf93_post', 'fila_rf91', 'fila_newman'].includes(escenario),
        `No se ejercitó la fila ${escenario}`);
      assert.equal(estado.solapamientos, 0);
      assert.ok(estado.peticiones.length <= 150);
      assert.ok(CASOS.every(k => r.casos[k]?.estado));
      if (escenario === 'fila_rf93_post') assert.equal(r.casos['TC-M06-011'].estado, 'RECHAZADO');
      if (escenario === 'fila_rf91') assert.equal(r.casos['TC-M06-013'].estado, 'RECHAZADO');
      if (escenario === 'fila_rebase') {
        assert.equal(r.casos['TC-M06-013'].estado, 'BLOQUEADO');
        const eventos943 = estado.peticiones.filter(x => x.ruta === '/activos-biologicos/943/eventos/crecimiento');
        assert.equal(eventos943.length, 1);
        assert.equal(eventos943[0].fecha, '2026-11-08T11:58:00Z');
      }
      process.stdout.write(`OK escenario_${escenario}: 011=${r.casos['TC-M06-011'].estado} 012=${r.casos['TC-M06-012'].estado} 013=${r.casos['TC-M06-013'].estado} oficial=${r.oficial ? 'sí' : 'no'} solicitudes=${estado.peticiones.length}/150\n`);
      return;
    }
    const peticionesNewman = estado.peticiones.filter(x => x.newman).length;
    const peticionesEjecutor = estado.peticiones.length - peticionesNewman;
    assert.equal(estado.solapamientos, 0);
    assert.ok(estado.peticiones.every(x => x.http !== 404 &&
      (x.http !== 500 || probable && x.ruta === '/finanzas/periodos/8/trazabilidad')));
    assert.equal(r.problemas_tecnicos.filter(x => x.includes('PETICION_CONCURRENTE')).length, 0);
    assert.equal(r.cierre.run.cierre_http, 200);
    assert.equal(r.cierre.rollback.verificado, true, JSON.stringify({ rollback: r.cierre.rollback,
      problemas: r.problemas_tecnicos, pasos: [1, 2, 3, 4].map(i => r.observaciones[`paso_${i}`]),
      nuevos: r.observaciones.nuevos }));
    if (replay) {
      assert.deepEqual([1, 2, 3, 4].map(i => r.observaciones[`paso_${i}`]?.estado),
        ['REGISTRADO', 'REGISTRADO', 'REGISTRADO', 'REGISTRADO']);
      assert.deepEqual(['TC-M06-011', 'TC-M06-012', 'TC-M06-013'].map(k => r.casos[k].estado),
        ['RECHAZADO', 'APROBADO', probable ? 'RECHAZADO' : 'APROBADO']);
      assert.equal(r.efectos_persistentes_declarados.registros_sin_id, 0);
      assert.ok(estado.peticiones.some(x => x.metodo === 'POST' && x.ruta.endsWith('/trazabilidad')));
      if (conNewman) assert.equal(r.oficial, true);
      process.stdout.write(`OK escenario_replay_intento7: 011=${r.casos['TC-M06-011'].estado} 012=${r.casos['TC-M06-012'].estado} 013=${r.casos['TC-M06-013'].estado} oficial=${r.oficial ? 'sí' : 'no'} solicitudes=${estado.peticiones.length}/150\n`);
    }
    assert.ok(estado.peticiones.some(x => x.metodo === 'POST' && x.ruta === '/finanzas/eventos/procesar'));
    if (!fechaIncoherente && !sinLectura && !sin943)
      assert.ok(estado.peticiones.some(x => x.metodo === 'POST' && x.ruta.endsWith('/trazabilidad')));
    const verificaciones = estado.peticiones.map((x, i) => x.metodo === 'POST' && x.ruta.endsWith('/trazabilidad') ? i : -1)
      .filter(i => i >= 0);
    const cadenas = estado.peticiones.map((x, i) => x.metodo === 'GET' && /\/finanzas\/lineas\/\d+\/cadena$/.test(x.ruta) ? i : -1)
      .filter(i => i >= 0);
    if (!fechaIncoherente && !sinLectura && !sin943)
      assert.ok(cadenas.some(i => i < verificaciones[0]) &&
        (probable || cadenas.some(i => i > verificaciones[0])));
    assert.ok(estado.peticiones.some(x => x.poscierre && x.ruta.endsWith('/variaciones')));
    assert.ok(r.cierre.lecturas_poscierre.length >= 4);
    assert.ok(estado.peticiones.some(x => x.metodo === 'DELETE' && x.http === 200));
    assert.equal(peticionesNewman, conNewman ? 3 : 0);
    if (conNewman) assert.equal(r.herramientas.newman.iteraciones, 1);
    if (probable && conNewman) {
      assert.deepEqual(['TC-M06-011', 'TC-M06-012', 'TC-M06-013'].map(k => r.casos[k].estado),
        ['RECHAZADO', 'APROBADO', 'RECHAZADO']);
      assert.equal(r.oficial, true);
      assert.equal(r.herramientas.newman.fallos, 0);
    }
    const fechados = estado.peticiones.filter(x => x.ruta.endsWith('/eventos/crecimiento'));
    if (!sinLectura && !sin943) {
      assert.ok(fechados.some(x => x.ruta.includes('/943/') && x.fecha === '2026-11-08T12:00:00Z'));
      assert.ok(fechados.filter(x => !x.ruta.includes('/943/')).every(x => x.fecha === null));
    }
    if (fechaIncoherente) {
      assert.equal(r.casos['TC-M06-013'].estado, 'BLOQUEADO');
      assert.match(r.casos['TC-M06-013'].motivo, new RegExp(codigoFecha));
      assert.equal(fechados.filter(x => x.ruta.includes('/943/')).length, 1);
    }
    if (sinLectura) {
      assert.equal(r.casos['TC-M06-013'].estado, 'BLOQUEADO');
      assert.equal(fechados.some(x => x.ruta.includes('/943/')), false);
    }
    if (escenario === 'iot_paginacion_sensor') {
      const paginas = estado.peticiones.filter(x => x.ruta === '/iot/monitoreo/historial' &&
        x.consulta.includes('sensor_id=1311'));
      assert.deepEqual(paginas.map(x => Number(new URLSearchParams(x.consulta).get('pagina'))), [1, 2]);
      const primeraEscritura = estado.peticiones.findIndex(x => ['POST', 'PATCH'].includes(x.metodo) &&
        !x.ruta.endsWith('/sesiones/'));
      assert.ok(estado.peticiones.indexOf(paginas[1]) < primeraEscritura);
      assert.equal(r.casos['TC-M06-013'].estado, 'APROBADO');
    }
    if (sin943) {
      assert.equal(r.casos['TC-M06-013'].estado, 'BLOQUEADO');
      assert.match(r.casos['TC-M06-013'].motivo, /estado distinto de ACTIVO/);
      assert.equal(fechados.some(x => x.ruta.includes('/943/')), false);
    }
    if (escenario === 'iot_precondicion_valida') assert.equal(r.casos['TC-M06-013'].estado, 'APROBADO');
    if (escenario === 'iot_precondicion_rf91_500') assert.equal(r.casos['TC-M06-013'].estado, 'RECHAZADO');
    if (['normal', 'iot_precondicion_valida', 'iot_precondicion_rf91_500'].includes(escenario) || replay) {
      assert.equal(r.observaciones.periodo_destino, 8);
      assert.deepEqual(r.observaciones.precio_tb_943,
        { id_precio_mercado: 20, fecha_hecho: '2026-11-08', fecha_vigencia: '2026-01-01' });
      assert.equal(r.observaciones.paso_1.precio, 20);
      const evento943 = estado.peticiones.findIndex(x => x.ruta === '/activos-biologicos/943/eventos/crecimiento');
      const precioDuranteRun = estado.peticiones.findIndex(x => x.metodo === 'POST' && x.ruta === '/finanzas/precios');
      assert.ok(evento943 >= 0 && precioDuranteRun > evento943);
      assert.ok(estado.peticiones.some(x => x.ruta === '/iot/monitoreo/historial' &&
        x.consulta.includes('fecha_inicio=2026-11-07') && x.consulta.includes('fecha_fin=2026-11-07') &&
        x.consulta.includes('sensor_id=1311')));
    }
    process.stdout.write(`OK escenario_${escenario}: 011=${r.casos['TC-M06-011'].estado} 012=${r.casos['TC-M06-012'].estado} 013=${r.casos['TC-M06-013'].estado} oficial=${r.oficial ? 'sí' : 'no'} solicitudes=${estado.peticiones.length}/150\n`);
    process.stdout.write(`OK ${conNewman ? 'flujo_completo_serie' : 'flujo_completo_serie_sin_newman'}: ` +
      `${estado.peticiones.length} peticiones (ejecutor ${peticionesEjecutor}, Newman ${peticionesNewman}), ` +
      '0 solapamientos, DELETE 200\n');
  } finally {
    if (servidor.listening) await new Promise(resolve => servidor.close(resolve));
    limpiarRun(run); fs.rmSync(temporal, { recursive: true, force: true });
  }
}

test('flujo completo del ejecutor en serie sin hijo Newman', t => flujoCompletoSerie(t, false));
test('flujo completo en serie con hijo Newman real', t => flujoCompletoSerie(t, true));
test('RF-93 422, cuatro variaciones auditadas y RF-91 500: RUN oficial local', t =>
  flujoCompletoSerie(t, true, 'probable'));
for (const escenario of ['iot_precondicion_valida', 'iot_precondicion_rf91_500',
  'iot_fecha_incoherente', 'iot_fecha_anterior_registro', 'iot_fecha_futura',
  'iot_lectura_no_navegable', 'iot_943_no_elegible', 'iot_paginacion_sensor'])
  test(escenario, t => flujoCompletoSerie(t, false, escenario));
for (const escenario of ['iot_precondicion_valida', 'iot_precondicion_rf91_500'])
  test(`${escenario} con Newman real`, t => flujoCompletoSerie(t, true, escenario));
for (const escenario of ['replay_intento7_500', 'replay_intento7_200']) {
  test(`${escenario} sin Newman`, t => flujoCompletoSerie(t, false, escenario));
  test(`${escenario} con Newman real`, t => flujoCompletoSerie(t, true, escenario));
}
for (const fila of ['seleccion', 'permisos', 'lecturas_previas', 'rf93_post', 'rebase',
  'eventos_m02', 'patch_estado', 'precios', 'procesar', 'lecturas_posteriores',
  'cadena_inicial', 'rf91', 'cadena_final', 'cierre'])
  test(`tabla de decisiones: ${fila}`, t => flujoCompletoSerie(t, false, `fila_${fila}`));
test('tabla de decisiones: Newman', t => flujoCompletoSerie(t, true, 'fila_newman'));
