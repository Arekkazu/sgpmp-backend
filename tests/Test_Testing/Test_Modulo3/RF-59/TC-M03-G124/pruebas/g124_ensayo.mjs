#!/usr/bin/env node
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import http from 'node:http';
import { fileURLToPath } from 'node:url';
import { evaluar, informe } from '../g124.mjs';
import { CASOS, CAPACIDADES } from '../lib/g124_escenario.mjs';
import { contextoEjecucion } from '../lib/contrato_ejecutor.mjs';
import { contieneMojibake } from '../lib/seguridad.mjs';
import { clasificarRegistro } from './registro_qa.mjs';
import { pdfSintetico, excelSintetico } from './fixtures.mjs';

const MODOS = [
  ['m08_no_disponible', ['BLOQUEADO', 'BLOQUEADO', 'BLOQUEADO']],
  ['exporta_ok', ['APROBADO', 'APROBADO', 'NO_CONCLUYENTE']],
  ['pdf_incompleto', ['RECHAZADO', 'APROBADO', 'NO_CONCLUYENTE']],
  ['excel_sin_hojas', ['APROBADO', 'RECHAZADO', 'NO_CONCLUYENTE']],
  ['otro_5xx', ['RECHAZADO', 'RECHAZADO', 'NO_CONCLUYENTE']],
  ['sin_respuesta', ['NO_CONCLUYENTE', 'NO_CONCLUYENTE', 'NO_CONCLUYENTE']],
  ['seleccion_automatica', ['APROBADO', 'APROBADO', 'NO_CONCLUYENTE']],
];
const responder = (res, code, body, run, contentType = 'application/json') => {
  res.writeHead(code, { 'Content-Type': contentType, ...(run ? { 'X-Test-Run-Id': run } : {}) });
  res.end(Buffer.isBuffer(body) ? body : JSON.stringify(body));
};
const leer = req => new Promise(resolve => {
  let s = ''; req.on('data', x => { s += x; }); req.on('end', () => {
    try { resolve(JSON.parse(s)); } catch { resolve(null); }
  });
});
async function servidor(modo) {
  const peticiones = [];
  const server = http.createServer(async (req, res) => {
    const url = new URL(req.url, 'http://127.0.0.1');
    const run = req.headers['x-test-run-id'];
    peticiones.push({ metodo: req.method, ruta: url.pathname,
      sensorId: url.searchParams.get('sensor_id'), inicio: url.searchParams.get('fecha_inicio'),
      fin: url.searchParams.get('fecha_fin') });
    if (url.pathname === '/sesiones/' && req.method === 'POST') {
      const login = await leer(req);
      return responder(res, login?.correo_electronico === 'productor@example.test' ? 200 : 401,
        { token: 'TOKEN_SINTETICO' }, null);
    }
    if (url.pathname.startsWith('/test-control/runs/') && req.method === 'DELETE')
      return responder(res, 200, { status: 'cerrado' }, null);
    if (url.pathname === '/iot/monitoreo/dashboard') return responder(res, 200,
      { total: 1, resumen_unidades: [{ id_infraestructura: 1 }], sensores: [{ id_sensor: 73 }] }, run);
    if (url.pathname === '/iot/monitoreo/dashboard/1') return responder(res, 200,
      { total: 1, sensores: [{ id_sensor: 73, ultimo_timestamp_captura: new Date().toISOString() }] }, run);
    if (url.pathname === '/iot/monitoreo/historial') {
      const id = url.searchParams.get('sensor_id');
      const encontrado = modo === 'seleccion_automatica' ? id === '73' : id === '6';
      return responder(res, 200, { total: encontrado ? 1 : 0,
        items: encontrado ? [{ id_sensor: Number(id), timestamp_captura: new Date().toISOString(), valor: 25 }] : [] }, run);
    }
    if (url.pathname === '/iot/monitoreo/historial/exportar') {
      const sensorEsperado = modo === 'seleccion_automatica' ? '73' : '6';
      if (url.searchParams.get('sensor_id') !== sensorEsperado || !url.searchParams.get('fecha_inicio')
        || !url.searchParams.get('fecha_fin')) return responder(res, 400,
        { error_code: 'EXPORTAR_SIN_FILTROS', message: 'Falta filtro' }, run);
      if (modo === 'sin_respuesta') { req.socket.destroy(); return; }
      if (modo === 'm08_no_disponible') return responder(res, 503,
        { error_code: 'M08_NO_DISPONIBLE', message: 'M08 no disponible' }, run);
      if (modo === 'otro_5xx') return responder(res, 500,
        { error_code: 'ERROR_INTERNO', message: 'Error interno' }, run);
      const meta = { sensorId: Number(sensorEsperado), inicio: url.searchParams.get('fecha_inicio'),
        fin: url.searchParams.get('fecha_fin') };
      if (url.searchParams.get('formato') === 'PDF') return responder(res, 200,
        pdfSintetico({ ...meta, incompleto: modo === 'pdf_incompleto' }), run, 'application/pdf');
      return responder(res, 200, excelSintetico({ ...meta, sinHojas: modo === 'excel_sin_hojas' }), run,
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
    }
    responder(res, 404, { error_code: 'NO_ENCONTRADO', message: 'Ruta ausente' }, run);
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  return { server, peticiones, base: `http://127.0.0.1:${server.address().port}` };
}

const temporal = fs.mkdtempSync(path.join(os.tmpdir(), 'g124-ensayo-'));
try {
  for (const [modo, esperado] of MODOS) {
    const s = await servidor(modo);
    try {
      const runId = `ENSAYO-G124-20261026-120000-${modo}`;
      const dir = path.join(temporal, modo); fs.mkdirSync(dir);
      const archivo = path.join(dir, 'contexto_operacion.json');
      const referencia = `ENSAYO_LOCAL_${modo}`;
      fs.writeFileSync(archivo, JSON.stringify({ grupo: 'G124', version: 1, intento: 1,
        run_id: runId, operacion: 'EVALUAR', referencia, casos: CASOS }));
      const c = contextoEjecucion(['--operacion', 'evaluar', '--version', '1', '--intento', '1',
        '--run-id', runId, '--autorizacion', referencia, '--contexto', archivo],
      { grupo: 'G124', casos: CASOS, directorio: path.resolve(fileURLToPath(import.meta.url), '../..'), modoEnsayo: true });
      const r = await evaluar(c, { ensayo: true, env: { QA_AUTORIZADO: 'SI', SIGAB_API_TEST_BASE: s.base,
        QA_SANDBOX_SECRET: 'ENSAYO_SECRET', QA_PROD_EMAIL: 'productor@example.test',
        QA_PROD_PASSWORD: 'ENSAYO_PASS' } });
      assert.deepEqual(CASOS.map(x => r.casos[x].estado), esperado, JSON.stringify(r.problemas_tecnicos));
      assert.equal(r.cierre.run.cierre_http, 200);
      const nombres = fs.readdirSync(dir);
      assert.equal(nombres.filter(x => x.endsWith('.md')).length, 1);
      const guardado = JSON.parse(fs.readFileSync(path.join(dir, 'resultado.json'), 'utf8'));
      assert.deepEqual(guardado.casos, r.casos);
      const newman = JSON.parse(fs.readFileSync(path.join(dir, 'newman/newman-G124.json'), 'utf8'));
      assert.equal(newman.run.executions.length, 3);
      assert.ok(newman.run.executions.every(x => !('stream' in x) && !('request' in x)));
      if (modo === 'm08_no_disponible') {
        assert.deepEqual(newman.run.executions.slice(1).map(x => x.error?.codigo),
          ['M08_NO_DISPONIBLE', 'M08_NO_DISPONIBLE']);
        assert.ok(newman.run.executions.slice(1).every(x => x.error?.mensaje));
      }
      const md = fs.readFileSync(path.join(dir, 'TC-M03-G124_resultado.md'), 'utf8');
      assert.equal(md, informe(r));
      assert.equal(contieneMojibake(md), false);
      const presentes = new Set(r.evidencias.filter(x => fs.existsSync(path.join(dir, x))));
      assert.equal(clasificarRegistro(CAPACIDADES, r, presentes, c), r.oficial);
      assert.equal(r.oficial, false);
      assert.deepEqual(s.peticiones.map(x => x.metodo), modo === 'seleccion_automatica'
        ? ['POST', 'GET', 'GET', 'GET', 'GET', 'GET', 'GET', 'GET', 'GET', 'DELETE']
        : ['POST', 'GET', 'GET', 'GET', 'GET', 'DELETE']);
      assert.equal(r.diagnostico_seleccion.modo, 'seleccion_automatica');
      assert.equal(r.semilla.sensorId, modo === 'seleccion_automatica' ? 73 : 6);
      if (modo === 'seleccion_automatica') {
        assert.deepEqual(r.diagnostico_seleccion.intentos.map(x => x.total), [0, 0, 1]);
        assert.equal(r.diagnostico_seleccion.seleccion.sensor_id, 73);
        assert.deepEqual(r.diagnostico_seleccion.intentos.slice(0, 2).map(x =>
          (Date.parse(x.fin) - Date.parse(x.inicio)) / 86400000), [7, 30]);
      }
      const exportaciones = s.peticiones.filter(x => x.ruta.endsWith('/exportar'));
      assert.equal(exportaciones.length, 2);
      assert.ok(exportaciones.every(x => x.sensorId === String(r.semilla.sensorId)
        && x.inicio === r.semilla.inicio && x.fin === r.semilla.fin));
      assert.ok(s.peticiones.every(x => !x.ruta.includes('/test-control/query')));
      console.log(`OK ${modo}: ${esperado.join(', ')}; registro TÉCNICO`);
    } finally { await new Promise(resolve => s.server.close(resolve)); }
  }
  console.log('OK G124: 7/7 modos, resultado.json = informe, registro QA fiel');
} finally {
  if (!path.resolve(temporal).startsWith(path.resolve(os.tmpdir()) + path.sep)) throw Error('TEMP_FUERA_RAIZ');
  fs.rmSync(temporal, { recursive: true, force: true });
}
