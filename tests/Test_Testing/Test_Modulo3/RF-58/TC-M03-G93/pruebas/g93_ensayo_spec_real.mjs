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
<form id="login"><input type="email"><input type="password"><button type="submit">Entrar</button></form>
<button id="auto">Auto ON</button><input type="text" id="monitoreo-area">
<main id="panel">Cargando…</main><script>
const fase = '__FASE__';
const escenario = '__ESCENARIO__';
const panel = document.getElementById('panel');
document.getElementById('auto').onclick = e => { e.currentTarget.textContent = 'Auto OFF'; };
const pill = (texto, color) => '<span style="border-radius:var(--r-full);color:' + color + '"><svg width="12" height="12"></svg>' + texto + '</span>';
const unidad = (nombre, sensores, datoExtra = '') => '<section><button class="ds-option"><div><div>Icono</div><div><div>' + nombre + '</div><div>Finca local' + (fase === 'V2' ? ' · último dato 25/10/2020 12:34' : '') + '</div></div></div><div>' + pill('Sin datos', 'var(--text-muted)') + datoExtra + '</div></button><div id="area-93">' + sensores + '</div></section>';
async function cargar(id) {
  const res = await fetch('/iot/monitoreo/dashboard' + (id ? '?id_infraestructura=' + id : ''));
  const j = await res.json();
  if (escenario === 'cargainfinita') return;
  const tarjetas = fase === 'V2' && id ? '<button class="ds-option">Sensor INACTIVO desactualizado ' + pill('Requiere calibración', 'var(--sem-warning)') + '</button>'
    + (escenario === 'v2lectura' ? '<span>Temperatura: 12.5 °C</span>' : '') : '';
  const datoExtra = escenario === 'v2contador' && !id ? '<span>0 sensores en línea</span>' : '';
  panel.innerHTML = j.resumen_unidades.length
    ? unidad('Unidad local G93', tarjetas, datoExtra) + unidad('Unidad local G93 ampliada', '')
    : '<p>Sin unidades visibles</p>';
}
document.getElementById('monitoreo-area').oninput = e => cargar(e.target.value);
document.getElementById('login').onsubmit = async e => {
  e.preventDefault();
  try {
    const login = await fetch('/sesiones/', { method: 'POST' });
    if (!login.ok) throw Error('login local falló');
    await login.json();
    const respuestas = await Promise.all([fetch('/usuarios/me'), fetch('/sesiones/me/permisos')]);
    if (respuestas.some(r => !r.ok)) throw Error('sesión local falló');
  } catch (error) { panel.innerHTML = '<div role="alert">' + error.message + '</div>'; }
};
window.addEventListener('popstate', () => { if (location.pathname.endsWith('/telemetria/monitoreo')) cargar(''); });
</script></body></html>`;

if (!isMainThread) {
  let actual = { escenario: 'v1', fase: 'V1' };
  let simulacion = { consultas_dashboard_retenidas: 0, respuestas_dashboard_lentas: 0,
    respuestas_sesion_503: 0,
    respuestas_concurrencia_500: 0, max_solicitudes_simultaneas: 0 };
  let activas = 0;
  const server = http.createServer((req, res) => {
    const url = new URL(req.url, 'http://127.0.0.1');
    const escenario = actual.escenario;
    if (url.pathname === '/login' || url.pathname === '/telemetria/monitoreo') {
      res.writeHead(200, { 'content-type': 'text/html; charset=utf-8' });
      res.end(html.replace('__FASE__', actual.fase).replace('__ESCENARIO__', actual.escenario)); return;
    }
    if (url.pathname === '/usuarios/me' || url.pathname === '/sesiones/me/permisos') {
      activas++;
      simulacion.max_solicitudes_simultaneas = Math.max(simulacion.max_solicitudes_simultaneas, activas);
      const status = escenario === 'fallo' && url.pathname === '/sesiones/me/permisos' ? 503
        : activas > 1 ? 500 : 200;
      if (status === 503) simulacion.respuestas_sesion_503++;
      if (status === 500) simulacion.respuestas_concurrencia_500++;
      setTimeout(() => {
        activas--;
        res.writeHead(status, { 'content-type': 'application/json',
          'x-test-run-id': req.headers['x-test-run-id'] ?? '' });
        res.end(JSON.stringify({ ok: status === 200 }));
      }, 20);
      return;
    }
    if (url.pathname === '/iot/monitoreo/dashboard') {
      if (escenario === 'vencimiento' && url.searchParams.get('id_infraestructura') === '93') {
        simulacion.consultas_dashboard_retenidas++;
        return;
      }
      const responder = () => {
        res.writeHead(200, { 'content-type': 'application/json',
          'x-test-run-id': req.headers['x-test-run-id'] ?? '' });
        res.end(JSON.stringify({ resumen_unidades: escenario === 'v1rechazado' ? [] : [{ id_infraestructura: 93,
          nombre_infraestructura: 'Unidad local G93', estado_general: 'GRIS',
          total_sensores: actual.fase === 'V2' ? 1 : 0 }],
        sensores: actual.fase === 'V2' ? [{ id_infraestructura: 93,
          estado_conectividad: 'INACTIVO', dato_desactualizado: true }] : [] }));
      };
      if (escenario === 'cargalenta') {
        simulacion.respuestas_dashboard_lentas++;
        setTimeout(responder, 1000);
      } else responder();
      return;
    }
    res.writeHead(404); res.end();
  });
  server.listen(0, '127.0.0.1', () => parentPort.postMessage({ port: server.address().port }));
  parentPort.on('message', mensaje => {
    if (mensaje === 'cerrar') server.close();
    else if (mensaje === 'estado_simulacion') parentPort.postMessage({ simulacion });
    else {
      actual = mensaje;
      activas = 0;
      simulacion = { consultas_dashboard_retenidas: 0, respuestas_dashboard_lentas: 0,
        respuestas_sesion_503: 0,
        respuestas_concurrencia_500: 0, max_solicitudes_simultaneas: 0 };
      parentPort.postMessage({ escenario_listo: mensaje.escenario });
    }
  });
} else {
  const temporal = fs.mkdtempSync(path.join(os.tmpdir(), 'g93-spec-real-'));
  const worker = new Worker(fileURLToPath(import.meta.url), { workerData: true });
  const resumen = { spec_real: spec, frontend_real: false, escenarios: [],
    artefactos_v1_preservados: false, temporal_eliminado: true, directorio_temporal_conservado: null };
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
        CYPRESS_PROD_LOGIN_TOKEN: token,
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
      const estadoSimulacion = new Promise(resolve => worker.once('message', resolve));
      worker.postMessage('estado_simulacion');
      const { simulacion } = await estadoSimulacion;
      const actaPath = path.join(carpeta, `UI-184-${fase}.json`);
      const acta = fs.existsSync(actaPath) ? JSON.parse(fs.readFileSync(actaPath, 'utf8')) : null;
      const log = fs.readFileSync(path.join(carpeta, `UI-184-${fase}-${nombre}.diagnostico.log`), 'utf8');
      const capturas = fs.readdirSync(carpeta, { recursive: true }).map(x => String(x))
        .filter(x => x.endsWith('.png') && x.includes(`UI-184-${fase}`));
      const dato = { nombre, fase, esperado, duracion_ms,
        simulacion,
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
      if (nombre === 'vencimiento')
        assert.ok(simulacion.consultas_dashboard_retenidas > 0,
          'vencimiento: ninguna consulta filtrada del dashboard quedó retenida');
      if (nombre === 'cargalenta')
        assert.ok(simulacion.respuestas_dashboard_lentas > 0,
          'cargalenta: ninguna respuesta del dashboard tuvo retraso');
      if (nombre === 'fallo')
        assert.ok(simulacion.respuestas_sesion_503 > 0,
          'fallo: ninguna respuesta HTTP 503 de permisos fue emitida');
      assert.equal(simulacion.respuestas_concurrencia_500, 0,
        `${nombre}: hubo peticiones de sesión simultáneas`);
      assert.ok(simulacion.max_solicitudes_simultaneas <= 1,
        `${nombre}: la cola permitió concurrencia`);
      assert.equal(dato.error_spawn, null, `${nombre}: Cypress no arrancó`);
      assert.equal(dato.pruebas_ejecutadas, 1, `${nombre}: spec en skip o sin prueba`);
      assert.equal(dato.cy_visit, true, `${nombre}: no llegó a cy.visit`);
      assert.equal(dato.acta, true, `${nombre}: falta acta`);
      assert.equal(dato.captura, true, `${nombre}: falta captura`);
      assert.doesNotMatch(log, /LOCAL_FICTICIO(?:_\d+)?/);
      assert.doesNotMatch(JSON.stringify(acta), /LOCAL_FICTICIO(?:_\d+)?/);
      assert.equal(acta.estado, esperado, `${nombre}: estado ${acta.estado}; esperado ${esperado}`);
      return { dato, acta };
    };
    const v1 = await ejecutar('v1', 'V1', 'APROBADO');
    assert.equal(v1.dato.codigo_salida, 0);
    assert.equal(v1.dato.interfaz_observada, true);
    assert.equal(v1.acta.estado, 'APROBADO', 'V1 normal no emitió APROBADO');
    assert.ok(v1.dato.duracion_ms < 45000, 'V1 normal se acercó al vencimiento global');
    const lenta = await ejecutar('cargalenta', 'V1', 'APROBADO');
    assert.equal(lenta.dato.codigo_salida, 0);
    assert.equal(lenta.acta?.ui_inicial?.cargando, false);
    assert.equal(lenta.acta?.ui_objetivo?.cargando, false);
    const v1Archivos = fs.readdirSync(path.join(temporal, 'cypress'), { recursive: true })
      .map(x => path.join(temporal, 'cypress', String(x)))
      .filter(x => fs.statSync(x).isFile() && /V1/.test(path.basename(x)));
    const v1Hashes = new Map(v1Archivos.map(x => [x, hash(x)]));
    const v2 = await ejecutar('v2', 'V2', 'APROBADO');
    assert.equal(v2.dato.codigo_salida, 0);
    assert.equal(v2.dato.interfaz_observada, true);
    assert.equal(v2.acta.estado, 'APROBADO', 'V2 normal no emitió APROBADO');
    assert.equal(v2.acta.ui_inicial?.sin_valores_fabricados, true,
      'Fecha histórica y Sin datos en el panel global se marcaron como valor fabricado');
    assert.equal(v2.acta.ui_objetivo?.sin_valores_fabricados, true,
      'La vista filtrada no aplicó el mismo criterio de ausencia');
    assert.ok(v2.dato.duracion_ms < 45000, 'V2 normal se acercó al vencimiento global');
    const contador = await ejecutar('v2contador', 'V2', 'RECHAZADO');
    assert.equal(contador.dato.codigo_salida, 0);
    assert.equal(contador.acta?.ui_inicial?.sin_valores_fabricados, false);
    assert.equal(contador.acta?.criterio, 'ORACULO_PANEL_GLOBAL_INCUMPLIDO');
    const lectura = await ejecutar('v2lectura', 'V2', 'RECHAZADO');
    assert.equal(lectura.dato.codigo_salida, 0);
    assert.equal(lectura.acta?.ui_objetivo?.sin_valores_fabricados, false);
    assert.equal(lectura.acta?.criterio, 'ORACULO_UI_INCUMPLIDO');
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
    assert.ok(vence.dato.peticiones_acta.some(p => p.alias === 'dashboardGlobal' && !p.fin_presente),
      'vencimiento: la petición esperada por el spec no quedó pendiente');
    const sinRender = await ejecutar('cargainfinita', 'V1', 'NO_CONCLUYENTE', true);
    assert.equal(sinRender.dato.codigo_salida, 0);
    assert.equal(sinRender.acta?.criterio, 'INICIAL:CARGA_SIN_TERMINAR');
    assert.equal(sinRender.acta?.ui_inicial?.cargando, true);
    const fallo = await ejecutar('fallo', 'V2', 'NO_CONCLUYENTE', true);
    assert.equal(fallo.dato.codigo_salida, 0);
    assert.equal(fallo.acta?.estado, 'NO_CONCLUYENTE');
    assert.ok(fallo.dato.peticiones_acta.some(p => p.alias === 'permisosSesion' && p.http === 503
      && p.fin_presente), 'fallo deliberado: HTTP 503 no registrado');
    resumen.valido = true;
  } catch (error) {
    resumen.valido = false; resumen.motivo = error.message;
    process.exitCode = 2;
  } finally {
    worker.postMessage('cerrar'); await worker.terminate();
    if (resumen.valido) fs.rmSync(temporal, { recursive: true, force: true });
    else {
      // El fallo conserva acta, captura y diagnóstico para reproducir la discrepancia.
      resumen.temporal_eliminado = false;
      resumen.directorio_temporal_conservado = temporal;
    }
    console.log(JSON.stringify(resumen, null, 2));
  }
}
