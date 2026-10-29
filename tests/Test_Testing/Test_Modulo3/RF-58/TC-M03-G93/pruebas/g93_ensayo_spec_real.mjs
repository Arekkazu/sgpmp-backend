#!/usr/bin/env node
// Ensayo técnico: ejecuta g93.cy.js sin modificar el producto ni contactar TEST.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import crypto from 'node:crypto';
import http from 'node:http';
import { Worker, isMainThread, parentPort, workerData } from 'node:worker_threads';
import { fileURLToPath } from 'node:url';
import { invocarCypressLocal } from '../g93.mjs';

const grupo = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const spec = path.join(grupo, 'g93.cy.js');
const token = 'LOCAL_FICTICIO';
const html = `<!doctype html><html lang="es"><meta charset="utf-8"><body>
<button id="auto">Auto ON</button><input type="number" id="filtro">
<main id="panel">Cargando…</main><script>
const fase = '__FASE__';
const escenario = '__ESCENARIO__';
const panel = document.getElementById('panel');
document.getElementById('auto').onclick = e => { e.currentTarget.textContent = 'Auto OFF'; };
const pill = (texto, color) => '<span style="border-radius:var(--r-full);color:' + color + '"><svg width="12" height="12"></svg>' + texto + '</span>';
const unidad = (nombre, sensores) => '<section><div class="unidad-card"><div><div>Icono</div><div><div>' + nombre + '</div><div>Finca local' + (fase === 'V2' ? ' · último dato 25/10/2020 12:34' : '') + '</div></div></div><div><span>Contador</span>' + pill('Sin datos', 'var(--text-muted)') + '</div></div><div class="rejilla">' + sensores + '</div></section>';
async function cargar(id) {
  const res = await fetch('/iot/monitoreo/dashboard' + (id ? '?id_infraestructura=' + id : ''));
  const j = await res.json();
  const tarjetas = fase === 'V2' && id ? '<button class="ds-option">Sensor INACTIVO desactualizado ' + pill('Requiere calibración', 'var(--sem-warning)') + '</button>' : '';
  panel.innerHTML = j.resumen_unidades.length
    ? unidad('Unidad local G93 ampliada', fase === 'V2' && !id ? '<button class="ds-option">Sensor ajeno desactualizado</button>' : '') + unidad('Unidad local G93', tarjetas)
    : '<p>Sin unidades visibles</p>';
}
document.getElementById('filtro').oninput = e => cargar(e.target.value);
fetch('/sesiones/refresh', { method: 'POST' }).then(r => {
  if (!r.ok) throw Error('refresh local falló');
  return r.json();
}).then(() => fetch('/sesiones/refresh', { method: 'POST' })).then(r => {
  if (!r.ok) throw Error('segundo refresh local falló');
  return cargar('');
}).catch(e => { panel.innerHTML = '<div role="alert">' + e.message + '</div>'; });
</script></body></html>`;

if (!isMainThread) {
  let actual = { escenario: 'v1', fase: 'V1' };
  let refreshActual = token;
  let rotaciones = 0;
  const server = http.createServer((req, res) => {
    const url = new URL(req.url, 'http://127.0.0.1');
    const escenario = actual.escenario;
    if (url.pathname === '/telemetria/monitoreo') {
      res.writeHead(200, { 'content-type': 'text/html; charset=utf-8' });
      res.end(html.replace('__FASE__', actual.fase).replace('__ESCENARIO__', actual.escenario)); return;
    }
    if (url.pathname === '/sesiones/refresh') {
      const recibido = /(?:^|;\s*)refresh_token=([^;]+)/.exec(req.headers.cookie || '')?.[1];
      const status = escenario === 'fallo' ? 503 : recibido === refreshActual ? 200 : 401;
      const cabeceras = { 'content-type': 'application/json', 'x-test-run-id': req.headers['x-test-run-id'] ?? '' };
      if (status === 200) {
        refreshActual = `LOCAL_FICTICIO_${++rotaciones}`;
        cabeceras['set-cookie'] = `refresh_token=${refreshActual}; Path=/; HttpOnly`;
      }
      res.writeHead(status, cabeceras);
      res.end(JSON.stringify(status === 401 ? { error_code: 'REFRESH_TOKEN_REUTILIZADO' } : { token })); return;
    }
    if (url.pathname === '/iot/monitoreo/dashboard') {
      if (escenario === 'vencimiento' && !url.searchParams.has('id_infraestructura')) return;
      res.writeHead(200, { 'content-type': 'application/json',
        'x-test-run-id': req.headers['x-test-run-id'] ?? '' });
      res.end(JSON.stringify({ resumen_unidades: escenario === 'v1rechazado' ? [] : [{ id_infraestructura: 93,
        nombre_infraestructura: 'Unidad local G93', estado_general: 'GRIS',
        total_sensores: actual.fase === 'V2' ? 1 : 0 }],
      sensores: actual.fase === 'V2' ? [{ id_infraestructura: 93,
        estado_conectividad: 'INACTIVO', dato_desactualizado: true }] : [] })); return;
    }
    res.writeHead(404); res.end();
  });
  server.listen(0, '127.0.0.1', () => parentPort.postMessage({ port: server.address().port }));
  parentPort.on('message', mensaje => {
    if (mensaje === 'cerrar') server.close();
    else { actual = mensaje; parentPort.postMessage({ escenario_listo: mensaje.escenario }); }
  });
} else {
  const temporal = fs.mkdtempSync(path.join(os.tmpdir(), 'g93-spec-real-'));
  const worker = new Worker(fileURLToPath(import.meta.url), { workerData: true });
  const resumen = { spec_real: spec, frontend_real: false, escenarios: [],
    artefactos_v1_preservados: false, temporal_eliminado: true };
  const hash = archivo => crypto.createHash('sha256').update(fs.readFileSync(archivo)).digest('hex');
  try {
    const port = await new Promise((resolve, reject) => {
      worker.once('message', x => resolve(x.port)); worker.once('error', reject);
    });
    const base = `http://127.0.0.1:${port}`;
    const carpeta = path.join(temporal, 'cypress');
    const fecha = new Date().toISOString().replace(/[-:]/g, '').slice(0, 15).replace('T', '-');
    let cookieVigente = token;
    const ejecutar = async (nombre, fase, esperado, corto = false) => {
      const runId = `ENSAYO-G93-${fecha}-${nombre}`;
      const contexto = path.join(temporal, 'contexto_operacion.json');
      const cookieFile = path.join(temporal, 'refresh-cookie.txt');
      fs.writeFileSync(contexto, JSON.stringify({ grupo: 'G93', run_id: runId, escenario: nombre }));
      const env = Object.fromEntries(Object.entries(process.env)
        .filter(([k]) => !/^CYPRESS_|^QA_|^SIGAB_/i.test(k)));
      Object.assign(env, {
        CYPRESS_AUTORIZADO_RUN: 'SI', CYPRESS_ENSAYO_G93_SPEC_REAL: 'SI',
        CYPRESS_ENSAYO_CONTEXTO_TEMPORAL: 'SI', CYPRESS_ENSAYO_CONTEXTO_RUTA: contexto,
        CYPRESS_ENSAYO_TIMEOUT_CORTO: corto ? 'SI' : 'NO',
        CYPRESS_RUN_ID: runId, CYPRESS_FASE: fase, CYPRESS_ID_INFRA: '93',
        CYPRESS_NOMBRE_INFRA: 'Unidad local G93',
        CYPRESS_FECHA_HISTORICA: fase === 'V2' ? '2020-10-25T12:34:00' : '',
        CYPRESS_API_BASE: base, CYPRESS_FRONT_BASE: base,
        CYPRESS_SANDBOX_SECRET: token, CYPRESS_REFRESH_COOKIE: cookieVigente,
        CYPRESS_REFRESH_COOKIE_FILE: cookieFile,
        CYPRESS_ARTIFACTS_DIR: carpeta,
      });
      const listo = new Promise(resolve => worker.once('message', resolve));
      worker.postMessage({ escenario: nombre, fase });
      assert.equal((await listo).escenario_listo, nombre);
      const inicio = Date.now();
      const { proceso, diagnostico } = invocarCypressLocal({ carpeta, env,
        prefijo: `UI-184-${fase}-${nombre}`, timeout: 150000, secretos: [token, cookieVigente] });
      const duracion_ms = Date.now() - inicio;
      if (fs.existsSync(cookieFile)) {
        cookieVigente = fs.readFileSync(cookieFile, 'utf8').trim();
        fs.rmSync(cookieFile, { force: true });
      }
      const actaPath = path.join(carpeta, `UI-184-${fase}.json`);
      const acta = fs.existsSync(actaPath) ? JSON.parse(fs.readFileSync(actaPath, 'utf8')) : null;
      const log = fs.readFileSync(path.join(carpeta, `UI-184-${fase}-${nombre}.diagnostico.log`), 'utf8');
      const capturas = fs.readdirSync(carpeta, { recursive: true }).map(x => String(x))
        .filter(x => x.endsWith('.png') && x.includes(`UI-184-${fase}`));
      const dato = { nombre, fase, esperado, duracion_ms,
        codigo_salida: proceso.status, error_spawn: proceso.error?.code ?? null,
        version: diagnostico.version_cypress, navegador: diagnostico.navegador,
        pruebas_ejecutadas: /1 (passing|failing)/i.test(log) ? 1 : 0,
        cy_visit: /Visit\s+http:\/\/127\.0\.0\.1/i.test(log) || Boolean(acta?.peticiones?.length),
        acta: Boolean(acta), estado_acta: acta?.estado ?? null,
        criterio_acta: acta?.criterio ?? null, motivo_acta: acta?.motivo ?? null,
        peticiones_acta: acta?.peticiones?.map(p => ({ metodo: p.metodo, ruta: p.ruta,
          alias: p.alias ?? null, alias_en_callback: p.alias_en_callback ?? null,
          http: p.http, duracion_ms: p.duracion_ms,
          eco_run: p.eco_run, fin_presente: Boolean(p.fin),
          espera_disponible: p.espera_disponible ?? null,
          espera_cerrada_antes: p.espera_cerrada_antes ?? null })) ?? [],
        interfaz_observada: Boolean(acta?.ui_inicial),
        captura: capturas.length > 0,
        diagnostico_resumen: log.split(/\r?\n/).filter(x => /1 passing|1 failing|AssertionError|Error:|Timed out/i.test(x))
          .slice(-4).map(x => x.trim().slice(0, 180)),
        diagnostico: path.basename(path.join(carpeta, `UI-184-${fase}-${nombre}.diagnostico.log`)) };
      resumen.escenarios.push(dato);
      assert.equal(dato.error_spawn, null, `${nombre}: Cypress no arrancó`);
      assert.equal(dato.pruebas_ejecutadas, 1, `${nombre}: spec en skip o sin prueba`);
      assert.equal(dato.cy_visit, true, `${nombre}: no llegó a cy.visit`);
      assert.equal(dato.acta, true, `${nombre}: falta acta`);
      assert.equal(dato.captura, true, `${nombre}: falta captura`);
      assert.doesNotMatch(log, /LOCAL_FICTICIO(?:_\d+)?/);
      assert.doesNotMatch(JSON.stringify(acta), /LOCAL_FICTICIO(?:_\d+)?/);
      return { dato, acta };
    };
    const v1 = await ejecutar('v1', 'V1', 'APROBADO');
    assert.equal(v1.dato.codigo_salida, 0);
    assert.equal(v1.dato.interfaz_observada, true);
    assert.equal(v1.acta.estado, 'APROBADO', 'V1 normal no emitió APROBADO');
    assert.ok(v1.dato.duracion_ms < 45000, 'V1 normal se acercó al vencimiento global');
    const v1Archivos = fs.readdirSync(path.join(temporal, 'cypress'), { recursive: true })
      .map(x => path.join(temporal, 'cypress', String(x)))
      .filter(x => fs.statSync(x).isFile() && /V1/.test(path.basename(x)));
    const v1Hashes = new Map(v1Archivos.map(x => [x, hash(x)]));
    const v2 = await ejecutar('v2', 'V2', 'APROBADO');
    assert.equal(v2.dato.codigo_salida, 0);
    assert.equal(v2.dato.interfaz_observada, true);
    assert.equal(v2.acta.estado, 'APROBADO', 'V2 normal no emitió APROBADO');
    assert.ok(v2.dato.duracion_ms < 45000, 'V2 normal se acercó al vencimiento global');
    for (const normal of [v1, v2]) {
      for (const alias of ['dashboardGlobal', 'dashboardObjetivo']) {
        assert.ok(normal.dato.peticiones_acta.some(p => p.alias === alias && p.fin_presente
          && p.http === 200 && p.eco_run && Number.isFinite(p.duracion_ms)),
        `${normal.dato.nombre}: ${alias} sin respuesta acreditada`);
      }
    }
    resumen.artefactos_v1_preservados = [...v1Hashes].every(([x, digest]) => fs.existsSync(x) && hash(x) === digest);
    assert.equal(resumen.artefactos_v1_preservados, true);
    const rechazo = await ejecutar('v1rechazado', 'V1', 'RECHAZADO');
    assert.equal(rechazo.dato.codigo_salida, 0);
    assert.equal(rechazo.acta.estado, 'RECHAZADO', 'V1 sin unidad no emitió RECHAZADO');
    assert.ok(rechazo.dato.duracion_ms < 45000, 'V1 sin unidad se acercó al vencimiento global');
    const vence = await ejecutar('vencimiento', 'V1', 'NO_CONCLUYENTE', true);
    assert.equal(vence.dato.codigo_salida, 0);
    assert.equal(vence.acta?.estado, 'NO_CONCLUYENTE');
    assert.equal(vence.acta?.criterio?.includes('CARGA_SIN_RESPUESTA'), true);
    const fallo = await ejecutar('fallo', 'V2', 'ERROR_QA');
    assert.notEqual(fallo.dato.codigo_salida, 0);
    assert.equal(fallo.acta?.estado, 'ERROR_QA');
    assert.ok(fallo.dato.peticiones_acta.some(p => p.alias === 'refresh' && p.http === 503
      && p.fin_presente), 'fallo deliberado: HTTP 503 no registrado');
    resumen.valido = true;
  } catch (error) {
    resumen.valido = false; resumen.motivo = error.message;
    process.exitCode = 2;
  } finally {
    worker.postMessage('cerrar'); await worker.terminate();
    fs.rmSync(temporal, { recursive: true, force: true });
    console.log(JSON.stringify(resumen, null, 2));
  }
}
