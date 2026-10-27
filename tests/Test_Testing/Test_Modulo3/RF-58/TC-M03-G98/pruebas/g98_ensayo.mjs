#!/usr/bin/env node
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import http from 'node:http';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { clasificarRegistro } from './registro_qa.mjs';
import { CAPACIDADES } from '../lib/g98_escenario.mjs';

const MODOS = [
  ['panel_ok','APROBADO',true], ['sin_panel','RECHAZADO',true],
  ['orden_incorrecto','RECHAZADO',true], ['panel_sin_mixtas','BLOQUEADO',false],
  ['error5xx','BLOQUEADO',false], ['sin_respuesta','NO_CONCLUYENTE',false],
];
const dir = path.dirname(fileURLToPath(import.meta.url));
const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'g98-ensayo-'));
const responder = (res, code, body, run) => { res.writeHead(code, { 'Content-Type': 'application/json', 'X-Test-Run-Id': run ?? '' }); res.end(JSON.stringify(body)); };
const alerta = severidad => ({ tipo_alerta: 'UMBRAL', tipo_variable: 'TEMPERATURA_AMBIENTAL',
  tiempo_transcurrido: '5 min', id_activo_biologico: 42, severidad });
async function simular(modo) {
  const server = http.createServer((req, res) => {
    const url = new URL(req.url, 'http://localhost');
    const run = req.headers['x-test-run-id'];
    if (url.pathname === '/sesiones/' && req.method === 'POST') return responder(res, 200, { token: 'TOKEN_SINTETICO' });
    if (url.pathname === '/configuracion/fincas') return responder(res, 200, { items: [] }, run);
    if (url.pathname.startsWith('/iot/monitoreo/dashboard/')) {
      if (modo === 'sin_respuesta') { req.socket.destroy(); return; }
      if (modo === 'error5xx') return responder(res, 503, { detail: 'simulado' }, run);
      const grados = modo === 'orden_incorrecto' ? ['LEVE','CRITICO','MODERADO']
        : modo === 'panel_sin_mixtas' ? ['CRITICO'] : ['CRITICO','MODERADO','LEVE'];
      const body = { total: grados.length, pagina: 1, por_pagina: 50,
        resumen_unidades: [{ id_infraestructura: 1, alertas_activas_count: grados.length }],
        sensores: grados.map((severidad_alerta, i) => ({ id_sensor: 11 + i, id_alerta: 12 + i, severidad_alerta })) };
      if (modo !== 'sin_panel') { body.total_alertas_activas = grados.length; body.alertas_activas = grados.map(alerta); }
      return responder(res, 200, body, run);
    }
    if (url.pathname.startsWith('/test-control/runs/') && req.method === 'DELETE') return responder(res, 200, { ok: true });
    responder(res, 404, { error: 'ruta' }, run);
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  return server;
}
function correr(args, env) {
  return new Promise(resolve => {
    const p = spawn(process.execPath, args, { cwd: path.resolve(dir, '..'), env, shell: false, windowsHide: true });
    let stdout = '', stderr = '';
    p.stdout.on('data', x => { stdout += x; }); p.stderr.on('data', x => { stderr += x; });
    p.on('close', code => resolve({ code, stdout, stderr }));
  });
}
try {
  let bien = 0;
  for (const [modo, esperado, oficial] of MODOS) {
    const server = await simular(modo);
    try {
      const run = `ENSAYO-G98-20261026-120000-${modo}`;
      const salida = path.join(temp, modo); fs.mkdirSync(salida);
      const contexto = { grupo: 'G98', version: 1, intento: 1, run_id: run,
        operacion: 'EVALUAR', referencia: 'AUT-ENSAYO-LOCAL', casos: ['TC-M03-191'],
        alcance_reevaluacion: null, version_anterior: null };
      const archivo = path.join(salida, 'contexto_operacion.json'); fs.writeFileSync(archivo, JSON.stringify(contexto));
      const api = `http://127.0.0.1:${server.address().port}`;
      const p = await correr([path.resolve(dir, '..', 'g98.mjs'), '--ensayo-loopback', '--operacion', 'evaluar',
        '--version', '1', '--intento', '1', '--run-id', run, '--autorizacion', 'AUT-ENSAYO-LOCAL', '--contexto', archivo],
      { ...process.env, G98_ENSAYO_BASE: api });
      const r = JSON.parse(fs.readFileSync(path.join(salida, 'resultado.json'), 'utf8'));
      const presentes = new Set(['resultado.json', ...fs.readdirSync(salida),
        ...fs.readdirSync(path.join(salida, 'newman')).map(x => `newman/${x}`)]);
      const registro = clasificarRegistro(CAPACIDADES, r, presentes, { runId: run, version: 1 });
      const informe = fs.readFileSync(path.join(salida, 'TC-M03-G98_resultado.md'), 'utf8');
      if (r.casos['TC-M03-191'].estado !== esperado || r.oficial !== oficial || registro !== oficial
        || (p.code !== 0 && modo !== 'sin_respuesta') || !informe.startsWith(`# TC-M03-G98 — ${esperado}\n\n## Decisión del caso`))
        throw Error(`${modo}: ${p.stdout} ${p.stderr} ${JSON.stringify({ estado: r.casos['TC-M03-191'].estado, oficial: r.oficial, registro, problemas: r.problemas_tecnicos, code: p.code })}`);
      console.log(`${modo} ${esperado} ${oficial ? 'OFICIAL' : 'NO_OFICIAL'}`); bien++;
    } finally { await new Promise(resolve => server.close(resolve)); }
  }
  console.log(`G98 ensayo ${bien}/${MODOS.length}`);
} finally {
  if (!path.resolve(temp).startsWith(path.resolve(os.tmpdir()) + path.sep)) throw Error('TEMP_FUERA_RAIZ');
  fs.rmSync(temp, { recursive: true, force: true });
}
