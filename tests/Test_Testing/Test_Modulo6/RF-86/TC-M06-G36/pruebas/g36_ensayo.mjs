import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawn } from 'node:child_process';
import http from 'node:http';
import { fileURLToPath } from 'node:url';
import { CASOS, CAPACIDADES, PRESUPUESTO, periodoDestino, evaluar009, evaluar010 } from '../lib/g36_core.mjs';
import { evaluar, informe, validarColeccionPermisos } from '../g36.mjs';
import { clasificarRegistro } from './registro_qa.mjs';

const periodo = { id_periodo_contable: 241, numero_id_tributaria: 'NIT-D',
  fecha_inicio: '2026-01-01', fecha_fin: '2026-12-31', estado: 'ABIERTO' };
assert.equal(periodoDestino([ { ...periodo, estado: 'CERRADO' },
  { ...periodo, id_periodo_contable: 242, fecha_inicio: '2027-01-01', fecha_fin: '2027-12-31' } ],
  'NIT-D', '2026-11-12'), null);
assert.equal(periodoDestino([periodo], 'NIT-D', '2026-11-12')?.id_periodo_contable, 241);
const col = JSON.parse(fs.readFileSync(new URL('../G36.postman_collection.json', import.meta.url), 'utf8'));
assert.equal(validarColeccionPermisos(col), true);
const ids = [1627,1831];
const mk = (status, body, run, codigo = '') => ({
  status, headers: { get: k => k.toLowerCase() === 'x-test-run-id' ? run : null },
  json: async () => structuredClone(body == null ? { error_code: codigo, message: 'Use el correctivo para corregir la variación.' } : body) });
function simulador(modo, runId) {
  let remote = 0, solicitudes = 0, aprobaciones = 0, cerrado = false;
  let correctivos = [];
  const estado = Object.fromEntries(ids.map(x => [x, { peso: 100, eventos: [], vars: [], lineas: [], mediciones: [] }]));
  const fetcher = async (url, opt) => {
    if (!url.startsWith('http://127.0.0.1:1234/')) { remote++; throw Error('RED_REMOTA'); }
    const u = new URL(url), ruta = u.pathname, method = opt.method, aid = Number(ruta.match(/activos-biologicos\/(\d+)/)?.[1] ??
      ruta.match(/finanzas\/activos\/(\d+)/)?.[1]);
    const run = opt.headers['X-Test-Run-Id'] ?? null;
    const send = (http, body, codigo) => mk(http, http >= 400 ?
      { fields: null, timestamp: '2026-11-12T00:00:00Z', ...body } : body, run, codigo);
    if (ruta === '/sesiones/') return send(200, { token: JSON.parse(opt.body).correo_electronico.includes('contador2') ?
      'segundo' : JSON.parse(opt.body).correo_electronico.includes('admin') ? 'admin' : 'primero' });
    if (ruta === '/test-control/runs/' + runId) {
      cerrado = true;
      if (modo === 'delete_fallido') return send(500, { error_code: 'FALLO', message: 'Fallo local' });
      for (const x of Object.values(estado)) { x.peso = 100; x.eventos = []; x.vars = []; x.lineas = []; x.mediciones = []; }
      correctivos = [];
      return send(200, {});
    }
    if (ruta === '/finanzas/activos') return send(200, ids.map(x => ({ id_activo_biologico: x,
      especie: 'Bovino', id_especie: 1, tipo: 'INDIVIDUAL', estado: 'ACTIVO', valor_razonable_neto: '1000' })));
    if (ruta === '/finanzas/periodos') return send(200, [modo === 'periodo_cerrado' ? { ...periodo, estado: 'CERRADO' } : periodo]);
    if (ruta === '/finanzas/configuracion') return send(200, { matriz: ['VARIACION_VR_TB','VARIACION_VR_PM'].map(tipo_hecho =>
      ({ tipo_hecho, sentido: 'GANANCIA', id_especie: 1, cuenta_debito: '1500', cuenta_credito: '4000' })) });
    if (ruta === '/finanzas/precios') return send(200, [{ id_precio_mercado: 18, id_especie: 1, categoria: 'PESO_KG',
      fecha_vigencia: '2026-01-01', fuente: 'MERCADO_ACTIVO' }]);
    if (ruta === '/finanzas/activos/' + aid) return send(200, { activo: { numero_id_tributaria: 'NIT-D' },
      reconocimientos: [{ estado: 'CONFIRMADO' }], calculos: [{ id_calculo_valor_razonable: aid,
        id_precio_mercado: 18, magnitud: 100, valor_neto: 1000, estado: 'CALCULADO' }], mediciones: estado[aid].mediciones });
    if (ruta === '/activos-biologicos/' + aid + '/ficha-integral') return send(200,
      { estado_actual: 'ACTIVO', peso_actual: estado[aid].peso, unidad_peso: 'kg' });
    if (ruta === '/activos-biologicos/' + aid + '/eventos' && method === 'GET') return send(200, { eventos: estado[aid].eventos });
    if (ruta === '/activos-biologicos/' + aid + '/eventos/crecimiento') {
      const eid = aid + 1000; estado[aid].peso = 102;
      estado[aid].eventos.push({ id_eventos: eid });
      return send(201, { evento: { id_eventos: eid } });
    }
    if (ruta === '/finanzas/eventos/procesar') {
      for (const x of ids) if (estado[x].eventos.length && !estado[x].vars.length) {
        const vid = x + 2000, lid = x + 3000;
        estado[x].vars.push({ id_variacion_valor_razonable: vid, id_activo_biologico: x,
          tipo: 'GANANCIA_TRANSFORMACION_BIOLOGICA', monto_variacion: '20.00', id_linea: lid,
          ...(modo === 'campos_inyectados' ? { campo_extra: { origen: 'local' } } : {}) });
        estado[x].lineas.push({ id_linea_asiento_nic41: lid, id_activo_biologico: x,
          tabla_origen: 'variaciones_valor_razonable', id_origen: vid, valor: '20.00',
          cuenta_debito: '1500', cuenta_credito: '4000',
          ...(modo === 'campos_inyectados' ? { campo_extra: true } : {}) });
        estado[x].mediciones.push({ id_medicion_posterior: x + 4000, id_evento: x + 1000 });
      }
      return send(200, {});
    }
    if (ruta === '/finanzas/periodos/241/variaciones' && method === 'GET')
      return send(200, ids.flatMap(x => estado[x].vars));
    if (ruta === '/finanzas/lineas' && method === 'GET') return send(200, ids.flatMap(x => estado[x].lineas));
    if (ruta === '/finanzas/correctivos' && method === 'GET') return send(200, correctivos);
    if (ruta === '/finanzas/auditoria') return send(200, { eventos: [], total_registros: 0 });
    if (ruta.startsWith('/finanzas/variaciones/') && ruta.endsWith('/correctivos') && method === 'POST') {
      solicitudes++;
      if (modo !== 'v1') correctivos.push({ id_solicitud_correctivo_variacion: 51, estado: 'PENDIENTE' });
      if (modo === 'efectivo_antes') estado[1831].vars.push({ id_variacion_valor_razonable: 8001,
        id_activo_biologico: 1831, es_correctivo: true, id_variacion_corregida: 3831,
        monto_variacion: '-20.00' });
      return send(modo === 'v1' ? 404 : 201, modo === 'v1' ?
        { error_code: '', message: 'Not Found' } :
        { id_solicitud_correctivo_variacion: 51, id_variacion_valor_razonable: 3831,
          estado: 'PENDIENTE', monto_correctivo: '-20.00' });
    }
    if (ruta === '/finanzas/correctivos/51/aprobacion') {
      aprobaciones++;
      if (opt.headers.Authorization === 'Bearer primero' && modo === 'autoaprobacion_409') return send(409,
        { error_code: 'CONFLICTO', message: 'Conflicto local de aprobacion.' });
      if (opt.headers.Authorization === 'Bearer primero' && modo !== 'autoaprobacion_2xx') return send(403,
        { error_code: 'APROBADOR_DEBE_SER_OTRO', message: 'Debe aprobar otro Contador.' });
      if (modo !== 'v1') {
        correctivos[0].estado = 'APROBADA';
        const x = estado[1831], original = x.vars[0], linea = x.lineas[0];
        x.vars.push({ id_variacion_valor_razonable: 9001, id_activo_biologico: 1831,
          tipo: original.tipo, monto_variacion: '-20.00', es_correctivo: true,
          id_variacion_corregida: original.id_variacion_valor_razonable });
        x.lineas.push({ id_linea_asiento_nic41: 9002, id_activo_biologico: 1831,
          tabla_origen: 'variaciones_valor_razonable', id_origen: 9001, id_linea_corregida: 4831,
          valor: modo === 'linea_negativa' ? '-20.00' : '20.00',
          cuenta_debito: modo === 'cuentas_no_invertidas' ? linea.cuenta_debito : linea.cuenta_credito, cuenta_credito: linea.cuenta_debito });
      }
      return send(modo === 'autoaprobacion_2xx' && opt.headers.Authorization === 'Bearer primero' ? 201 : 200,
        { estado: 'APROBADA', id_variacion_corregida: 3831,
        id_variacion_correctiva: 9001, monto_variacion: '-20.00',
        lineas_inversas: [{ id_linea: 9002, id_linea_corregida: 4831,
          valor: modo === 'linea_negativa' ? '-20.00' : '20.00',
          cuenta_debito: modo === 'cuentas_no_invertidas' ? '1500' : '4000', cuenta_credito: '1500' }] });
    }
    if (['PUT','PATCH','DELETE'].includes(method) && (ruta.includes('/variaciones/') || ruta.includes('/lineas/'))) {
      const linea = ruta.includes('/lineas/');
      const codigo = linea ? 'LINEA_ASIENTO_INMUTABLE' : 'VARIACION_INMUTABLE';
      return send(modo === 'v1' ? 404 : 409, { error_code: modo === 'v1' ? '' : codigo,
        message: modo === 'v1' ? 'Not Found' : modo === 'sin_orientacion' ? 'Registro inmutable.' :
          'Use el correctivo para corregir la variacion.' });
    }
    throw Error('Ruta local no prevista: ' + ruta);
  };
  return { fetcher, stats: () => ({ remote, solicitudes, aprobaciones, cerrado }) };
}
const env = { QA_AUTORIZADO: 'SI', SIGAB_API_TEST_BASE: 'http://127.0.0.1:1234',
  QA_SANDBOX_SECRET: 'local', QA_CONTADOR_EMAIL: 'contador@ejemplo.invalid', QA_CONTADOR_PASSWORD: 'local',
  QA_CONTADOR2_EMAIL: 'contador2@ejemplo.invalid', QA_CONTADOR2_PASSWORD: 'local',
  QA_ADMIN_EMAIL: 'admin@ejemplo.invalid', QA_ADMIN_PASSWORD: 'local' };
const c = { runId: 'RUN-G36-V2-20261112-000000', version: 2, intento: 1,
  operacion: 'reevaluar', version_anterior: 1, referencia: 'ENSAYO_LOCAL', ensayo: true };
for (const [modo, esperado, oficial] of [
  ['conforme', ['APROBADO','APROBADO'], true],
  ['autoaprobacion_2xx', ['APROBADO','APROBADO'], true],
  ['autoaprobacion_409', ['APROBADO','APROBADO'], true],
  ['campos_inyectados', ['APROBADO','APROBADO'], true],
  ['reintentar', ['APROBADO','APROBADO'], true],
  ['v1', ['RECHAZADO','RECHAZADO'], true],
  ['sin_orientacion', ['RECHAZADO','APROBADO'], true],
  ['linea_negativa', ['APROBADO','RECHAZADO'], true],
  ['cuentas_no_invertidas', ['APROBADO','RECHAZADO'], true],
  ['efectivo_antes', ['APROBADO','RECHAZADO'], true],
  ['periodo_cerrado', ['NO_CONCLUYENTE','NO_CONCLUYENTE'], false],
  ['delete_fallido', ['APROBADO','APROBADO'], false]
]) {
  const sim = simulador(modo === 'reintentar' ? 'conforme' : modo, c.runId);
  const contexto = modo === 'reintentar' ? { ...c, operacion: 'reintentar', version_anterior: null,
    alcance_reevaluacion: { motivo: 'Reintento local' } } : c;
  const r = await evaluar(contexto, { env, fetcher: sim.fetcher, sinArtefactos: true });
  assert.deepEqual(CASOS.map(x => r.casos[x].estado), esperado, modo + ': ' + JSON.stringify({ casos:r.casos, preflight:r.preflight_vivo, problemas:r.problemas_tecnicos }));
  assert.equal(r.oficial, oficial, modo);
  assert.equal(sim.stats().remote, 0);
  assert.equal(sim.stats().cerrado, true);
  assert.ok(r._solicitudesRun <= PRESUPUESTO.solicitudes_totales);
  if (modo === 'conforme') {
    assert.equal(r.seguimiento_incidencias_v1[0].estado_v2, 'CORREGIDA');
    assert.equal(sim.stats().aprobaciones, 2);
    assert.equal(r.casos[CASOS[0]].observados.intentos.length, 9);
    assert.match(informe(c,r), /ENSAYO_LOCAL/);
    const copia = structuredClone(r);
    copia.evidencias = ['resultado.json', 'TC-M06-G36_reevaluacion_V2.md',
      'newman/newman-G36.json', 'newman/newman-G36.html'];
    for (const x of copia.comprobaciones) x.evidencia = 'resultado.json';
    assert.equal(clasificarRegistro(CAPACIDADES, copia, new Set(copia.evidencias), c), true);
    copia.comprobaciones[0].caso = 'G36/009';
    assert.equal(clasificarRegistro(CAPACIDADES, copia, new Set(copia.evidencias), c), false);
  }
  if (['conforme', 'autoaprobacion_2xx', 'autoaprobacion_409'].includes(modo)) {
    const observado = r.casos[CASOS[1]].observados;
    assert.equal(sim.stats().aprobaciones, modo === 'autoaprobacion_2xx' ? 1 : 2, modo);
    assert.equal(observado.aprobacion_http, modo === 'autoaprobacion_2xx' ? 201 : 200, modo);
    assert.match(observado.doble_control, modo === 'conforme' ? /Doble control activo/ :
      modo === 'autoaprobacion_2xx' ? /permitio la autoaprobacion/ : /HTTP 409/, modo);
    assert.ok(informe(c, r).includes(observado.doble_control), modo);
  }
  if (modo === 'periodo_cerrado') assert.equal(sim.stats().solicitudes, 0);
}
console.log('OK G36 ensayo local: escenarios y guarda de red');




if (process.argv.includes('--servidor-ejemplo')) {
  const sim = simulador('conforme', c.runId);
  const server = http.createServer(async (req, res) => {
    let body = '';
    for await (const chunk of req) body += chunk;
    try {
      const x = await sim.fetcher('http://127.0.0.1:1234' + req.url, {
        method: req.method, body,
        headers: { Authorization: req.headers.authorization,
          'X-Test-Run-Id': req.headers['x-test-run-id'] } });
      res.writeHead(x.status, { 'Content-Type': 'application/json',
        'X-Test-Run-Id': req.headers['x-test-run-id'] ?? '' });
      res.end(JSON.stringify(await x.json()));
    } catch (e) { res.writeHead(500); res.end(JSON.stringify({ error_code: 'SIMULADOR_ERROR', message: e.message })); }
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  console.log('http://127.0.0.1:' + server.address().port);
  await new Promise(() => {});
} else {
  let hijo;
  try { hijo = spawn(process.execPath, [fileURLToPath(import.meta.url), '--servidor-ejemplo'],
    { stdio: ['ignore','pipe','pipe'], windowsHide: true }); }
  catch (e) { if (e.code !== 'EPERM') throw e; console.log('A4 pendiente: spawn EPERM'); }
  if (hijo) {
    let error = null;
    hijo.on('error', e => { error = e.code ?? e.message; });
    const puerto = await new Promise(resolve => {
      let salida = '';
      hijo.stdout.on('data', b => { salida += b.toString(); if (salida.includes('\n')) {
        const m = salida.match(/http:\/\/127\.0\.0\.1:\d+/);
        if (m) resolve(m[0]);
      } });
      hijo.on('close', () => resolve(null));
    });
    try {
      if (!puerto) { console.log('A4 pendiente: ' + (error ?? 'servidor hijo sin puerto')); }
      else {
        const ejemplo = path.join(os.tmpdir(), 'g36-verificar-ejemplo');
        if (path.resolve(ejemplo) !== path.resolve(os.tmpdir(), 'g36-verificar-ejemplo'))
          throw Error('Destino temporal invalido');
        fs.rmSync(ejemplo, { recursive: true, force: true });
        const trabajo = path.join(ejemplo, 'trabajo', c.runId);
        const salida = path.join(ejemplo, c.runId);
        fs.mkdirSync(trabajo, { recursive: true });
        const resultado = await evaluar({ ...c, directorio: trabajo }, {
          env: { ...env, SIGAB_API_TEST_BASE: puerto }, fetcher: fetch });
        fs.cpSync(trabajo, salida, { recursive: true });
        fs.writeFileSync(path.join(ejemplo, 'capacidades.json'), JSON.stringify(CAPACIDADES, null, 2));
        if (resultado.oficial) {
          const presentes = new Set(resultado.evidencias.filter(x => fs.existsSync(path.join(salida, x))));
          assert.equal(clasificarRegistro(CAPACIDADES, resultado, presentes, c), true);
        }
        console.log('A4 ' + (resultado.oficial ? 'oficial' : 'no oficial') + ': ' +
          JSON.stringify(resultado.condiciones_oficialidad));
        console.log('resultado.json: ' + path.join(salida, 'resultado.json'));
        console.log('capacidades.json: ' + path.join(ejemplo, 'capacidades.json'));
      }
    } finally { hijo.kill(); }
  }
}
