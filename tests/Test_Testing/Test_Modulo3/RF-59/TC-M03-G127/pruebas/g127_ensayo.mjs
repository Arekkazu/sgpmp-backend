#!/usr/bin/env node
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import http from 'node:http';
import { fileURLToPath } from 'node:url';
import { evaluar, informe } from '../g127.mjs';
import { CASOS, CAPACIDADES } from '../lib/g127_escenario.mjs';
import { contextoEjecucion } from '../lib/contrato_ejecutor.mjs';
import { contieneMojibake } from '../lib/seguridad.mjs';
import { clasificarRegistro } from './registro_qa.mjs';

const MODOS = [
  ['auditado_ok', 'APROBADO', true],
  ['sin_evento', 'RECHAZADO', true],
  ['evento_incompleto_rango', 'RECHAZADO', true],
  ['evento_incompleto_cantidad', 'RECHAZADO', true],
  ['auditoria_403', 'BLOQUEADO', false],
  ['error5xx', 'BLOQUEADO', false],
  ['sin_respuesta', 'NO_CONCLUYENTE', false],
];
const token = sub => `x.${Buffer.from(JSON.stringify({ sub: String(sub), id_rol: sub === 7 ? 4 : 1 })).toString('base64url')}.x`;
const responder = (res, code, body, run) => {
  res.writeHead(code, { 'Content-Type': 'application/json', ...(run ? { 'X-Test-Run-Id': run } : {}) });
  res.end(JSON.stringify(body));
};
function evento(modo, peticion) {
  const d = { id_usuario: 7, id_rol: 4,
    filtros: { sensor_id: 6, fecha_inicio: peticion.inicio, fecha_fin: peticion.fin },
    por_pagina: 37, registros_devueltos: 3, exportado: false };
  if (modo === 'evento_incompleto_rango') delete d.filtros.fecha_fin;
  if (modo === 'evento_incompleto_cantidad') delete d.registros_devueltos;
  return { id_evento: 'evento-ensayo', id_usuario: 7, tipo_evento: 'HISTORIAL_CONSULTADO',
    fecha_hora: new Date().toISOString(), accion_detallada: d };
}
async function servidor(modo) {
  const peticiones = [], consulta = { inicio: null, fin: null };
  const server = http.createServer((req, res) => {
    const url = new URL(req.url, 'http://127.0.0.1');
    const run = req.headers['x-test-run-id'];
    peticiones.push({ metodo: req.method, ruta: url.pathname,
      por_pagina: url.searchParams.get('por_pagina') });
    if (url.pathname === '/sesiones/' && req.method === 'POST') {
      let raw = ''; req.on('data', x => { raw += x; }); req.on('end', () => {
        const correo = JSON.parse(raw).correo_electronico;
        responder(res, 200, { token: token(correo === 'productor@example.test' ? 7 : 1) });
      });
      return;
    }
    if (url.pathname.startsWith('/test-control/runs/') && req.method === 'DELETE')
      return responder(res, 200, { status: 'cerrado' });
    if (url.pathname === '/iot/monitoreo/historial') {
      const porPagina = url.searchParams.get('por_pagina');
      if (porPagina === '37') {
        consulta.inicio = url.searchParams.get('fecha_inicio');
        consulta.fin = url.searchParams.get('fecha_fin');
      }
      return responder(res, 200, { total: 3, items: [1, 2, 3].map(i => ({ id_sensor: 6,
        id_lectura: i })) }, run);
    }
    if (url.pathname === '/iot/auditoria') {
      if (url.searchParams.get('tipo_evento') === 'EXPORTACION_FALLIDA')
        return responder(res, 200, { total: 0, items: [] }, run);
      if (modo === 'sin_respuesta') { req.socket.destroy(); return; }
      if (modo === 'auditoria_403') return responder(res, 403,
        { error_code: 'SIN_PERMISO', message: 'Permiso 39,2 no disponible' }, run);
      if (modo === 'error5xx') return responder(res, 500,
        { error_code: 'ERROR_AUDITORIA', message: 'Bitácora no disponible' }, run);
      const items = modo === 'sin_evento' ? [] : [evento(modo, consulta)];
      return responder(res, 200, { total: items.length, items }, run);
    }
    if (url.pathname === '/iot/monitoreo/historial/exportar')
      return responder(res, 503, { error_code: 'M08_NO_DISPONIBLE', message: 'M08 no disponible' }, run);
    responder(res, 404, { error_code: 'NO_ENCONTRADO' }, run);
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  return { server, peticiones, base: `http://127.0.0.1:${server.address().port}` };
}
const temporal = fs.mkdtempSync(path.join(os.tmpdir(), 'g127-ensayo-'));
try {
  for (const [modo, estado, oficial] of MODOS) {
    const s = await servidor(modo);
    try {
      const dir = path.join(temporal, modo); fs.mkdirSync(dir);
      const runId = `ENSAYO-G127-20261027-000000-${modo}`;
      const archivo = path.join(dir, 'contexto_operacion.json');
      const referencia = `ENSAYO_LOCAL_${modo}`;
      fs.writeFileSync(archivo, JSON.stringify({ grupo: 'G127', version: 1, intento: 1,
        run_id: runId, operacion: 'EVALUAR', referencia, casos: CASOS }));
      const c = contextoEjecucion(['--operacion', 'evaluar', '--version', '1', '--intento', '1',
        '--run-id', runId, '--autorizacion', referencia, '--contexto', archivo],
      { grupo: 'G127', casos: CASOS, directorio: path.resolve(fileURLToPath(import.meta.url), '../..'),
        modoEnsayo: true });
      const r = await evaluar(c, { ensayo: true, env: { QA_AUTORIZADO: 'SI',
        SIGAB_API_TEST_BASE: s.base, QA_SANDBOX_SECRET: 'ENSAYO_SECRET',
        QA_PROD_EMAIL: 'productor@example.test', QA_PROD_PASSWORD: 'ENSAYO_PASS',
        QA_ADMIN_EMAIL: 'admin@example.test', QA_ADMIN_PASSWORD: 'ENSAYO_ADMIN_PASS' } });
      assert.equal(r.casos['TC-M03-256'].estado, estado, JSON.stringify(r.problemas_tecnicos));
      assert.equal(r.oficial, oficial);
      assert.equal(r.cierre.run.cierre_http, 200);
      const nombres = fs.readdirSync(dir);
      assert.equal(nombres.filter(x => x.endsWith('.md')).length, 1);
      const guardado = JSON.parse(fs.readFileSync(path.join(dir, 'resultado.json'), 'utf8'));
      assert.deepEqual(guardado.casos, r.casos);
      assert.equal(guardado.run_id, runId);
      const md = fs.readFileSync(path.join(dir, 'TC-M03-G127_resultado.md'), 'utf8');
      assert.equal(md, informe(r));
      assert.equal(contieneMojibake(md), false);
      const presentes = new Set(r.evidencias.filter(x => fs.existsSync(path.join(dir, x))));
      assert.equal(clasificarRegistro(CAPACIDADES, r, presentes, c), oficial);
      const newman = JSON.parse(fs.readFileSync(path.join(dir, 'newman/newman-G127.json'), 'utf8'));
      assert.equal(newman.run.executions.length, 3);
      assert.ok(newman.run.executions.every(x => !('stream' in x) && !('request' in x)));
      assert.equal(newman.run.executions[2].error?.codigo, 'M08_NO_DISPONIBLE');
      assert.ok(s.peticiones.every(x => !x.ruta.includes('/test-control/query')));
      assert.equal(s.peticiones.at(-1).metodo, 'DELETE');
      assert.equal(s.peticiones.filter(x => x.ruta === '/iot/monitoreo/historial' && x.por_pagina === '37').length, 1);
      console.log(`OK ${modo}: ${estado} ${oficial ? 'OFICIAL' : 'TÉCNICO'}`);
    } finally { await new Promise(resolve => s.server.close(resolve)); }
  }
  console.log('OK G127: 7/7 modos; resultado.json e informe coherentes; registro QA fiel');
} finally {
  if (!path.resolve(temporal).startsWith(path.resolve(os.tmpdir()) + path.sep)) throw Error('TEMP_FUERA_RAIZ');
  fs.rmSync(temporal, { recursive: true, force: true });
}
