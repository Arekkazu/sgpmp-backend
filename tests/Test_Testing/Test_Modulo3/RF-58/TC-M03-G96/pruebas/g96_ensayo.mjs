#!/usr/bin/env node
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import http from 'node:http';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const MODOS = [
  ['catalogo_ok', 'APROBADO', true], ['fuera_catalogo', 'RECHAZADO', true],
  ['cobertura_incompleta', 'BLOQUEADO', false], ['error5xx', 'BLOQUEADO', false],
  ['sin_respuesta', 'NO_CONCLUYENTE', false],
];
const raiz = path.dirname(fileURLToPath(import.meta.url));
const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'g96-ensayo-'));
const respuesta = (res, code, body, run) => { res.writeHead(code, { 'Content-Type': 'application/json', 'X-Test-Run-Id': run ?? '' }); res.end(JSON.stringify(body)); };
async function simular(modo) {
  const server = http.createServer((req, res) => {
    const url = new URL(req.url, 'http://localhost');
    const run = req.headers['x-test-run-id'];
    if (url.pathname === '/sesiones/' && req.method === 'POST') return respuesta(res, 200, { token: 'TOKEN_SINTETICO' });
    if (url.pathname === '/configuracion/fincas') return respuesta(res, 200, { items: [] }, run);
    if (url.pathname.startsWith('/iot/monitoreo/dashboard/')) {
      if (modo === 'sin_respuesta') { req.socket.destroy(); return; }
      if (modo === 'error5xx') return respuesta(res, 503, { error: 'simulado' }, run);
      const valores = modo === 'catalogo_ok' ? ['ONLINE', 'OFFLINE', 'SIN_SEÑAL']
        : modo === 'fuera_catalogo' ? ['ACTIVO', 'INACTIVO'] : ['ONLINE'];
      return respuesta(res, 200, { total: valores.length, pagina: 1, por_pagina: 50,
        sensores: valores.map(estado_conectividad => ({ estado_conectividad })) }, run);
    }
    if (url.pathname.startsWith('/test-control/runs/') && req.method === 'DELETE') return respuesta(res, 200, { ok: true });
    respuesta(res, 404, { error: 'ruta' }, run);
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  return server;
}
function correr(args, env) {
  return new Promise(resolve => {
    const p = spawn(process.execPath, args, { cwd: path.resolve(raiz, '..'), env, shell: false, windowsHide: true });
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
      const run = `ENSAYO-G96-20261026-120000-${modo}`;
      const dir = path.join(temp, modo); fs.mkdirSync(dir);
      const contexto = { grupo: 'G96', version: 1, intento: 1, run_id: run,
        operacion: 'EVALUAR', referencia: 'AUT-ENSAYO-LOCAL', casos: ['TC-M03-187'],
        alcance_reevaluacion: null, version_anterior: null };
      const archivo = path.join(dir, 'contexto_operacion.json');
      fs.writeFileSync(archivo, JSON.stringify(contexto));
      const api = `http://127.0.0.1:${server.address().port}`;
      const p = await correr([path.resolve(raiz, '..', 'g96.mjs'), '--ensayo-loopback', '--operacion', 'evaluar',
        '--version', '1', '--intento', '1', '--run-id', run, '--autorizacion', 'AUT-ENSAYO-LOCAL', '--contexto', archivo],
      { ...process.env, G96_ENSAYO_BASE: api });
      const r = JSON.parse(fs.readFileSync(path.join(dir, 'resultado.json'), 'utf8'));
      if (r.casos['TC-M03-187'].estado !== esperado || r.oficial !== oficial || p.code !== 0) {
        const reporte = path.join(dir, 'newman', 'newman-G96.json');
        const fallos = fs.existsSync(reporte)
          ? (JSON.parse(fs.readFileSync(reporte, 'utf8')).run?.failures ?? []).map(f => ({
            tipo: f.error?.name ?? '', test: f.error?.test ?? '', item: f.source?.name ?? '',
            mensaje: f.error?.message ?? '',
          })) : [];
        throw Error(`${modo}: ${p.stdout} ${p.stderr} ${JSON.stringify({ estado: r.casos['TC-M03-187'].estado, oficial: r.oficial, problemas: r.problemas_tecnicos, fallos })}`);
      }
      console.log(`${modo} ${esperado} ${oficial ? 'OFICIAL' : 'NO_OFICIAL'}`); bien++;
    } finally { await new Promise(resolve => server.close(resolve)); }
  }
  console.log(`G96 ensayo ${bien}/${MODOS.length}`);
} finally {
  if (!path.resolve(temp).startsWith(path.resolve(os.tmpdir()) + path.sep)) throw Error('TEMP_FUERA_RAIZ');
  fs.rmSync(temp, { recursive: true, force: true });
}
