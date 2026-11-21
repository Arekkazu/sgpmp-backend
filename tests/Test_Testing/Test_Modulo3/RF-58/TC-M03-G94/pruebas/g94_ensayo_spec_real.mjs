#!/usr/bin/env node
// Ensayo técnico local: Cypress 14 + Chrome contra un frontend y una API loopback.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import http from 'node:http';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { createRequire } from 'node:module';
import { Worker, isMainThread, parentPort } from 'node:worker_threads';
import { fileURLToPath } from 'node:url';

const grupo = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const raiz = path.resolve(grupo, '../../../../..');
const require = createRequire(import.meta.url);
const escenarios = [
  ['OK', 'APROBADO'], ['TEXTO', 'RECHAZADO'], ['AJENAS', 'RECHAZADO'],
  ['SESION500', 'NO_CONCLUYENTE'], ['CARGA', 'NO_CONCLUYENTE'], ['LENTO', 'APROBADO'],
];
const pagina = `<!doctype html><html lang="es"><meta charset="utf-8"><body>
<form id="login"><input type="email"><input type="password"><button type="submit">Entrar</button></form>
<main id="panel"><h1>Monitoreo en tiempo real</h1>
<div role="group" aria-label="Resumen de sensores; pulsa una tarjeta para filtrar">Sensores: 0 · Fuera de rango: 0 · Cerca del límite: 0 · Sin datos: 0 · Normales: 0</div>
<div id="contenido"></div></main><script>
const api = '/api-sgpmp-test';
const contenido = document.getElementById('contenido');
const cargar = () => { contenido.innerHTML = '<div style="display:grid">' +
  Array.from({ length: 8 }, () => '<div style="height:220px;animation: pulse 1.4s ease-in-out infinite"></div>').join('') + '</div>'; };
document.getElementById('login').addEventListener('submit', async event => {
  event.preventDefault();
  try {
    const login = await fetch(api + '/sesiones/', { method: 'POST' });
    if (!login.ok) throw Error('sesión no disponible');
    await login.json();
    const perfil = await fetch(api + '/usuarios/me');
    if (!perfil.ok) throw Error('perfil no disponible');
    await perfil.json();
    const permisos = await fetch(api + '/sesiones/me/permisos');
    if (!permisos.ok) throw Error('permisos no disponibles');
    await permisos.json();
  } catch { contenido.textContent = 'Error de sesión local'; }
});
window.addEventListener('popstate', async () => {
  if (!location.pathname.endsWith('/telemetria/monitoreo')) return;
  cargar();
  try {
    const res = await fetch(api + '/iot/monitoreo/dashboard');
    const datos = await res.json();
    if (!res.ok) throw Error('dashboard no disponible');
    if (datos.mantener_carga) return;
    if (datos.resumen_unidades.length || datos.sensores.length)
      contenido.innerHTML = '<div><section><button class="ds-option">Unidad ajena</button></section></div>';
    else contenido.innerHTML = '<p>' + datos.mensaje + '</p>';
  } catch { contenido.innerHTML = '<div role="alert">Error al cargar el dashboard</div>'; }
});
</script></body></html>`;

if (!isMainThread) {
  let escenario = 'OK';
  let activas = 0;
  let simulacion;
  const reiniciar = () => { simulacion = { rutas: {}, max_simultaneas: 0,
    respuestas_503: 0, respuestas_lentas: 0, cargas_perpetuas: 0, respuestas_ajenas: 0,
    textos_alternativos: 0, respuestas_concurrencia_500: 0 }; };
  reiniciar();
  const servidor = http.createServer((req, res) => {
    const ruta = new URL(req.url, 'http://127.0.0.1').pathname;
    if (ruta === '/sigab-test/login' || ruta === '/sigab-test/telemetria/monitoreo') {
      res.writeHead(200, { 'content-type': 'text/html; charset=utf-8' });
      res.end(pagina); return;
    }
    if (!ruta.startsWith('/api-sgpmp-test/')) { res.writeHead(404); res.end(); return; }
    const recurso = ruta.slice('/api-sgpmp-test'.length);
    activas++;
    res.once('finish', () => { activas--; });
    simulacion.max_simultaneas = Math.max(simulacion.max_simultaneas, activas);
    simulacion.rutas[recurso] = (simulacion.rutas[recurso] ?? 0) + 1;
    const status = activas > 1 ? 500
      : escenario === 'SESION500' && recurso === '/sesiones/me/permisos' ? 503 : 200;
    if (status === 500) simulacion.respuestas_concurrencia_500++;
    if (status === 503) simulacion.respuestas_503++;
    const responder = () => {
      let cuerpo = {};
      if (recurso === '/usuarios/me') cuerpo = { fincas: [] };
      if (recurso === '/iot/monitoreo/dashboard') {
        const ajenas = escenario === 'AJENAS';
        if (ajenas) simulacion.respuestas_ajenas++;
        if (escenario === 'TEXTO') simulacion.textos_alternativos++;
        if (escenario === 'CARGA') simulacion.cargas_perpetuas++;
        cuerpo = { total: ajenas ? 1 : 0,
          resumen_unidades: ajenas ? [{ id_infraestructura: 999 }] : [],
          sensores: ajenas ? [{ id_sensor: 999 }] : [],
          mantener_carga: escenario === 'CARGA',
          mensaje: escenario === 'TEXTO'
            ? 'Tus fincas aún no tienen sensores. Se registran en Configuración › IoT.'
            : 'No tiene unidades productivas asignadas. Contacte al administrador.' };
      }
      res.writeHead(status, { 'content-type': 'application/json',
        'x-test-run-id': req.headers['x-test-run-id'] ?? '' });
      res.end(JSON.stringify(cuerpo));
    };
    if (escenario === 'LENTO' && recurso === '/iot/monitoreo/dashboard') {
      simulacion.respuestas_lentas++;
      setTimeout(responder, 1000);
    } else setTimeout(responder, 20);
  });
  servidor.listen(0, '127.0.0.1', () => parentPort.postMessage({ puerto: servidor.address().port }));
  parentPort.on('message', mensaje => {
    if (mensaje.tipo === 'cerrar') servidor.close();
    if (mensaje.tipo === 'escenario') {
      assert.equal(activas, 0, 'peticiones pendientes antes del siguiente escenario');
      escenario = mensaje.nombre; reiniciar();
      parentPort.postMessage({ listo: escenario });
    }
    if (mensaje.tipo === 'estado') parentPort.postMessage({ simulacion: { ...simulacion, sin_respuesta: activas } });
  });
} else {
  const temporal = fs.mkdtempSync(path.join(os.tmpdir(), 'g94-spec-real-'));
  const worker = new Worker(fileURLToPath(import.meta.url));
  const salida = { grupo: 'G94', caso: 'TC-M03-185', spec: path.join(grupo, 'g94.cy.js'),
    navegador: 'chrome', frontend_real: false, escenarios: [], valido: false,
    directorio_temporal_conservado: null };
  const esperarMensaje = enviar => new Promise((resolve, reject) => {
    const limpiar = () => {
      clearTimeout(reloj); worker.off('message', recibir);
      worker.off('error', fallar); worker.off('exit', salir);
    };
    const recibir = valor => { limpiar(); resolve(valor); };
    const fallar = error => { limpiar(); reject(error); };
    const salir = codigo => fallar(new Error(`SERVIDOR_LOOPBACK_TERMINO_${codigo}`));
    const reloj = setTimeout(() => fallar(new Error('SERVIDOR_LOOPBACK_SIN_RESPUESTA')), 10000);
    worker.once('message', recibir); worker.once('error', fallar); worker.once('exit', salir);
    if (enviar) worker.postMessage(enviar);
  });
  try {
    const puerto = (await esperarMensaje()).puerto;
    const base = `http://127.0.0.1:${puerto}`;
    const paqueteCypress = require.resolve('cypress/package.json', { paths: [raiz] });
    salida.version_cypress = JSON.parse(fs.readFileSync(paqueteCypress, 'utf8')).version;
    assert.match(salida.version_cypress, /^14\./, 'Se requiere Cypress 14 instalado');
    const cli = path.join(path.dirname(paqueteCypress), 'bin', 'cypress');
    const comunes = ['PATH', 'Path', 'PATHEXT', 'SYSTEMROOT', 'SystemRoot', 'WINDIR', 'TEMP', 'TMP',
      'USERPROFILE', 'HOMEDRIVE', 'HOMEPATH', 'APPDATA', 'LOCALAPPDATA', 'PROGRAMFILES',
      'PROGRAMFILES(X86)', 'HOME', 'LANG'];
    const entornoBase = Object.fromEntries(comunes.filter(k => process.env[k] != null).map(k => [k, process.env[k]]));
    for (const [nombre, esperado] of escenarios) {
      assert.equal((await esperarMensaje({ tipo: 'escenario', nombre })).listo, nombre);
      const carpeta = path.join(temporal, nombre);
      fs.mkdirSync(carpeta, { recursive: true });
      const artefactos = path.join(carpeta, 'cypress');
      fs.mkdirSync(artefactos);
      const run = `ENSAYO-G94-${nombre}`;
      const env = { ...entornoBase, CYPRESS_AUTORIZADO_RUN: 'SI', CYPRESS_ENSAYO_LOCAL: 'SI',
        CYPRESS_ENSAYO_TIMEOUT_CORTO: 'SI', CYPRESS_API_BASE: `${base}/api-sgpmp-test`,
        CYPRESS_FRONT_BASE: `${base}/sigab-test`, CYPRESS_RUN_ID: run,
        CYPRESS_SANDBOX_SECRET: 'LOCAL_FICTICIO', CYPRESS_PROD_LOGIN_TOKEN: 'LOCAL_FICTICIO',
        CYPRESS_ARTIFACTS_DIR: artefactos, CYPRESS_NO_TELEMETRY: '1' };
      const args = [cli, 'run', '--project', grupo, '--spec', salida.spec,
        '--config-file', path.join(grupo, 'g94.cypress.config.cjs'),
        '--config', `screenshotsFolder=${artefactos},videosFolder=${artefactos},downloadsFolder=${artefactos}`,
        '--browser', 'chrome', '--headless'];
      const inicio = Date.now();
      const proceso = spawnSync(process.execPath, args, { cwd: grupo, shell: false, env,
        encoding: 'utf8', timeout: 60000, maxBuffer: 8 * 1024 * 1024 });
      const diagnostico = path.join(carpeta, 'diagnostico.log');
      const log = `STDOUT\n${proceso.stdout ?? ''}\nSTDERR\n${proceso.stderr ?? ''}\n`;
      fs.writeFileSync(diagnostico, log.replaceAll('LOCAL_FICTICIO', '[RESERVADO]'));
      const { simulacion } = await esperarMensaje({ tipo: 'estado' });
      const actaArchivo = path.join(artefactos, 'UI-185-01.json');
      const resumenArchivo = path.join(artefactos, 'UI-185-01-cypress.json');
      const acta = fs.existsSync(actaArchivo) ? JSON.parse(fs.readFileSync(actaArchivo, 'utf8')) : null;
      const resumenCypress = fs.existsSync(resumenArchivo) ? JSON.parse(fs.readFileSync(resumenArchivo, 'utf8')) : null;
      const capturas = fs.readdirSync(artefactos, { recursive: true }).map(String)
        .filter(x => x.endsWith('.png') && x.includes('UI-185-01'));
      const dato = { nombre, esperado, observado: acta?.estado ?? null,
        codigo_salida: proceso.status, error_spawn: proceso.error?.code ?? null,
        duracion_ms: Date.now() - inicio, simulacion, captura: capturas.length > 0,
        acta: Boolean(acta), navegador_detectado: /Browser:[^\r\n]*Chrome/i.test(log),
        resumen_cypress: resumenCypress,
        diagnostico: path.relative(temporal, diagnostico) };
      salida.escenarios.push(dato);
      assert.equal(dato.error_spawn, null, `${nombre}: Cypress no arrancó`);
      assert.equal(dato.navegador_detectado, true, `${nombre}: Chrome no consta en diagnóstico`);
      assert.deepEqual({ totalTests: resumenCypress?.totalTests, totalPassed: resumenCypress?.totalPassed,
        totalFailed: resumenCypress?.totalFailed, totalPending: resumenCypress?.totalPending,
        totalSkipped: resumenCypress?.totalSkipped },
      { totalTests: 1, totalPassed: 1, totalFailed: 0, totalPending: 0, totalSkipped: 0 },
      `${nombre}: spec sin una prueba real aprobada`);
      assert.equal(proceso.status, 0, `${nombre}: Cypress terminó con error`);
      assert.equal(dato.captura, true, `${nombre}: falta captura real`);
      assert.equal(acta?.captura, true, `${nombre}: falta captura en acta`);
      assert.equal(acta?.caso, 'TC-M03-185');
      assert.equal(acta?.id, 'UI-185-01');
      assert.equal(acta?.estado, esperado, `${nombre}: estado distinto`);
      assert.equal(simulacion.max_simultaneas, 1, `${nombre}: concurrencia no serializada`);
      assert.equal(simulacion.respuestas_concurrencia_500, 0, `${nombre}: colisión de peticiones`);
      assert.equal(simulacion.sin_respuesta, 0, `${nombre}: API con respuesta pendiente`);
      assert.ok(simulacion.rutas['/usuarios/me'] > 0, `${nombre}: perfil no solicitado`);
      assert.ok(simulacion.rutas['/sesiones/me/permisos'] > 0, `${nombre}: permisos no solicitados`);
      if (nombre !== 'SESION500') assert.ok(simulacion.rutas['/iot/monitoreo/dashboard'] > 0,
        `${nombre}: dashboard no solicitado`);
      if (nombre === 'SESION500') {
        assert.ok(simulacion.respuestas_503 > 0, 'SESION500: no hubo respuesta 503');
        assert.ok(acta.peticiones.some(p => p.ruta === '/sesiones/me/permisos' && p.http === 503));
      }
      if (nombre === 'TEXTO') assert.ok(simulacion.textos_alternativos > 0, 'TEXTO: no se sirvió el mensaje');
      if (nombre === 'AJENAS') {
        assert.ok(simulacion.respuestas_ajenas > 0, 'AJENAS: no se sirvieron datos ajenos');
        assert.equal(acta.datos_ajenos, true);
      }
      if (nombre === 'CARGA') {
        assert.ok(simulacion.cargas_perpetuas > 0, 'CARGA: no se mantuvo la carga');
        assert.equal(acta.carga_sin_terminar, true);
      }
      if (nombre === 'LENTO') {
        assert.ok(simulacion.respuestas_lentas > 0, 'LENTO: no hubo retraso');
        assert.equal(acta.carga_sin_terminar, false);
      }
      if (nombre !== 'CARGA' && nombre !== 'SESION500')
        assert.equal(acta.pendiente_al_terminar, false, `${nombre}: acta con petición pendiente`);
      assert.doesNotMatch(log, /LOCAL_FICTICIO/);
      assert.doesNotMatch(JSON.stringify(acta), /LOCAL_FICTICIO/);
    }
    salida.valido = true;
  } catch (error) {
    salida.error = error.message;
    process.exitCode = 2;
  } finally {
    worker.postMessage({ tipo: 'cerrar' });
    await worker.terminate();
    if (salida.valido) {
      const real = fs.realpathSync(temporal);
      assert.equal(path.dirname(real), fs.realpathSync(os.tmpdir()));
      assert.match(path.basename(real), /^g94-spec-real-/);
      fs.rmSync(real, { recursive: true, force: true });
    }
    else salida.directorio_temporal_conservado = temporal;
    console.log(JSON.stringify(salida, null, 2));
  }
}
