#!/usr/bin/env node
// Ensayo local del ejecutor y de Newman; nunca usa TEST ni crea un RUN oficial.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import http from 'node:http';
import os from 'node:os';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { CATALOGO, PRESUPUESTO } from '../lib/g96_escenario.mjs';
import { sanearArtefacto } from '../lib/seguridad.mjs';

const raiz = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const runId = 'ENSAYO-G96-20261031-000001-local';
const escenarios = [
  { nombre: 'catalogo_completo', estado: 'APROBADO', peticiones: 19, newman: 5 },
  { nombre: 'valor_online', estado: 'RECHAZADO', peticiones: 19, newman: 5 },
  { nombre: 'desconocido', estado: 'APROBADO', peticiones: 19, newman: 5 },
  { nombre: 'buffer_como_sin_senal', estado: 'RECHAZADO', peticiones: 19, newman: 5 },
  { nombre: 'candidata_sin_sensores', estado: 'APROBADO', peticiones: 20, newman: 5 },
  { nombre: 'ajeno_mantenimiento', estado: 'APROBADO', peticiones: 21, newman: 5 },
  { nombre: 'e7_gris', estado: 'APROBADO', peticiones: 21, newman: 5 },
  { nombre: 'respaldo_administrador', estado: 'APROBADO', peticiones: 19, newman: 5 },
  { nombre: 'sin_dispositivo', estado: 'NO_CONCLUYENTE', peticiones: 17, newman: 4 },
  { nombre: 'transporte_newman', estado: 'NO_CONCLUYENTE', peticiones: 15, newman: 1 },
];

function ejecutarHijo(base, contexto) {
  return new Promise((resolve, reject) => {
    const argumentos = [path.join(raiz, 'g96.mjs'), '--ensayo-loopback', '--operacion', 'evaluar',
      '--version', '1', '--intento', '1', '--run-id', runId, '--autorizacion', 'ENSAYO_LOCAL',
      '--contexto', contexto];
    const hijo = spawn(process.execPath, argumentos, { cwd: raiz, shell: false, windowsHide: true,
      env: { ...process.env, G96_ENSAYO_BASE: base }, stdio: ['ignore', 'pipe', 'pipe'] });
    let stdout = '', stderr = '';
    hijo.stdout.on('data', b => { stdout = (stdout + b.toString()).slice(-5000); });
    hijo.stderr.on('data', b => { stderr = (stderr + b.toString()).slice(-5000); });
    hijo.once('error', reject);
    hijo.once('close', codigo => resolve({ codigo, stdout, stderr }));
  });
}

function diagnosticoHijo(hijo, temporal) {
  const archivos = [];
  const recorrer = (directorio, relativo = '') => {
    for (const entrada of fs.readdirSync(directorio, { withFileTypes: true })) {
      const nombre = path.join(relativo, entrada.name);
      if (entrada.isDirectory()) recorrer(path.join(directorio, entrada.name), nombre);
      else archivos.push(nombre);
    }
  };
  recorrer(temporal);
  const ultimasLineas = texto => sanearArtefacto(texto, ['ENSAYO_SECRET', 'ENSAYO_PASS',
    'ENSAYO_ADMIN_TOKEN', 'ENSAYO_PROD_TOKEN']).split(/\r?\n/).slice(-8).join('\n').slice(-1200);
  return `código=${hijo.codigo}; stdout=${JSON.stringify(ultimasLineas(hijo.stdout))}; `
    + `stderr=${JSON.stringify(ultimasLineas(hijo.stderr))}; archivos=${JSON.stringify(archivos)}`;
}

function iniciarServidor(escenario, eventos) {
  return http.createServer(async (req, res) => {
    const url = new URL(req.url, 'http://127.0.0.1');
    const enRun = req.headers['x-test-run-id'] === runId;
    const evento = { metodo: req.method, ruta: url.pathname, area: Number(url.searchParams.get('id_infraestructura')),
      estado: url.searchParams.get('estado'),
      por_pagina: url.searchParams.get('por_pagina'), en_run: enRun,
      rol: req.headers.authorization === 'Bearer ENSAYO_ADMIN_TOKEN' ? 'Administrador' : 'Productor' };
    eventos.push(evento);
    const enviar = (codigo, cuerpo) => {
      res.writeHead(codigo, { 'Content-Type': 'application/json', ...(enRun ? { 'X-Test-Run-Id': runId } : {}) });
      res.end(JSON.stringify(cuerpo));
    };
    if (!/^127\.0\.0\.1:\d+$/.test(req.headers.host ?? '')) return enviar(400, {});
    if (req.method === 'POST' && url.pathname === '/sesiones/') {
      let texto = '';
      for await (const b of req) texto += b;
      const correo = JSON.parse(texto).correo_electronico;
      return enviar(200, { token: correo === 'administrador@example.test' ? 'ENSAYO_ADMIN_TOKEN' : 'ENSAYO_PROD_TOKEN' });
    }
    if (req.method === 'GET' && url.pathname === '/usuarios/me')
      return enviar(200, { rol: req.headers.authorization === 'Bearer ENSAYO_ADMIN_TOKEN' ? 'Administrador' : 'Productor' });
    if (req.method === 'GET' && url.pathname === '/iot/dispositivos') {
      const indice = CATALOGO.indexOf(url.searchParams.get('estado'));
      if (!enRun || (indice < 0 && url.searchParams.has('estado'))) return enviar(400, {});
      const filas = CATALOGO.flatMap((estado, i) => escenario.nombre === 'sin_dispositivo' && i === 1 ? []
        : [{ id_dispositivo_iot: i + 1, id_infraestructura: i + 1, estado_actual: estado }]);
      if (escenario.nombre === 'candidata_sin_sensores') filas.unshift({ id_dispositivo_iot: 6,
        id_infraestructura: 6, estado_actual: 'ACTIVO' });
      if (['ajeno_mantenimiento', 'e7_gris'].includes(escenario.nombre)) filas.push(
        { id_dispositivo_iot: 7, id_infraestructura: 6, estado_actual: 'EN_MANTENIMIENTO' },
        { id_dispositivo_iot: 8, id_infraestructura: 7, estado_actual: 'EN_MANTENIMIENTO' });
      return enviar(200, indice < 0 ? filas.filter(d => escenario.nombre !== 'respaldo_administrador'
        || d.estado_actual !== 'EN_MANTENIMIENTO') : filas.filter(d => d.estado_actual === CATALOGO[indice]));
    }
    if (req.method === 'GET' && url.pathname === '/iot/monitoreo/dashboard') {
      const area = Number(url.searchParams.get('id_infraestructura'));
      const porPagina = Number(url.searchParams.get('por_pagina'));
      if (!enRun || !Number.isInteger(area) || area < 1 || area > 7
        || url.searchParams.get('pagina') !== '1' || ![1, 50].includes(porPagina)) return enviar(400, {});
      if (area === 6 && escenario.nombre === 'candidata_sin_sensores') return enviar(200, { total: 0, sensores: [] });
      if (['ajeno_mantenimiento', 'e7_gris'].includes(escenario.nombre) && [5, 6].includes(area))
        return enviar(200, { total: 1, sensores: [{ id_dispositivo_iot: 999,
          estado_conectividad: area === 5 && escenario.nombre === 'e7_gris' ? 'DESCONOCIDO' : 'ACTIVO',
          estado_semaforo: area === 5 && escenario.nombre === 'e7_gris' ? 'GRIS' : 'VERDE',
          dato_desactualizado: false, sin_umbral: area === 5 && escenario.nombre === 'e7_gris' }] });
      if (escenario.nombre === 'transporte_newman' && porPagina === 50) {
        evento.cortada = true;
        req.socket.destroy();
        return;
      }
      const valor = area === 7 ? 'EN_MANTENIMIENTO' : escenario.nombre === 'valor_online' && area === 1 ? 'ONLINE'
        : escenario.nombre === 'buffer_como_sin_senal' && area === 3 ? 'SIN_SEÑAL' : CATALOGO[area - 1];
      const sensores = [{ id_dispositivo_iot: area === 7 ? 8 : area, estado_conectividad: valor }];
      if (escenario.nombre === 'desconocido' && area === 1) sensores.push({ id_dispositivo_iot: 999,
        estado_conectividad: 'DESCONOCIDO' });
      return enviar(200, { total: sensores.length, sensores: sensores.slice(0, porPagina) });
    }
    if (req.method === 'DELETE' && url.pathname === `/test-control/runs/${runId}`)
      return enviar(200, { cerrado: true });
    return enviar(404, {});
  });
}

async function ensayar(escenario) {
  const temporal = fs.mkdtempSync(path.join(os.tmpdir(), `g96-ensayo-${escenario.nombre}-`));
  const eventos = [];
  const servidor = iniciarServidor(escenario, eventos);
  let valido = false;
  let hijo = { codigo: null, stdout: '', stderr: '' };
  try {
    await new Promise((resolve, reject) => {
      servidor.once('error', reject);
      servidor.listen(0, '127.0.0.1', resolve);
    });
    const puerto = servidor.address().port;
    const contexto = path.join(temporal, 'contexto_operacion.json');
    fs.writeFileSync(contexto, JSON.stringify({ grupo: 'G96', version: 1, intento: 1, run_id: runId,
      operacion: 'EVALUAR', referencia: 'ENSAYO_LOCAL', casos: ['TC-M03-187'] }));
    hijo = await ejecutarHijo(`http://127.0.0.1:${puerto}`, contexto);
    const codigoEsperado = escenario.nombre === 'transporte_newman' ? 2 : 0;
    if (hijo.codigo !== codigoEsperado || !fs.existsSync(path.join(temporal, 'resultado.json')))
      throw Error(`${escenario.nombre}: salida incompleta del hijo; ${diagnosticoHijo(hijo, temporal)}`);
    const resultado = JSON.parse(fs.readFileSync(path.join(temporal, 'resultado.json'), 'utf8'));
    const reporte = path.join(temporal, 'newman', 'newman-G96.json');
    assert.ok(fs.existsSync(reporte), `${escenario.nombre}: Newman no generó reporte; ${hijo.stderr}`);
    assert.ok(fs.existsSync(path.join(temporal, 'newman', 'newman-G96.html')));
    const newman = JSON.parse(fs.readFileSync(reporte, 'utf8'));
    const paginas = eventos.filter(e => e.ruta === '/iot/monitoreo/dashboard' && e.por_pagina === '50');
    assert.equal(resultado.casos['TC-M03-187'].estado, escenario.estado, escenario.nombre);
    assert.equal(eventos.length, escenario.peticiones, `${escenario.nombre}: peticiones`);
    assert.equal(paginas.length, escenario.newman, `${escenario.nombre}: peticiones Newman`);
    assert.equal(newman.run.executions.length, escenario.newman, `${escenario.nombre}: ejecuciones Newman`);
    assert.equal(eventos.filter(e => e.ruta === '/sesiones/').length, 2);
    assert.equal(eventos.filter(e => e.ruta === '/iot/dispositivos').length, 6);
    assert.equal(eventos.filter(e => e.ruta === `/test-control/runs/${runId}`).length, 1);
    assert.ok(eventos.filter(e => e.en_run).every(e => e.metodo === 'GET'));
    assert.ok(eventos.filter(e => e.en_run).length <= PRESUPUESTO.solicitudes_en_run);
    assert.ok(resultado.bitacora.filter(e => e.en_run).length <= PRESUPUESTO.solicitudes_en_run);
    assert.ok(paginas.length <= PRESUPUESTO.paginas_dashboard);
    assert.ok(eventos.filter(e => e.ruta === '/iot/monitoreo/dashboard' && e.por_pagina === '1').length
      <= PRESUPUESTO.canarios_e7);
    assert.ok(eventos.every(e => ['/sesiones/', '/iot/dispositivos', '/iot/monitoreo/dashboard',
      `/test-control/runs/${runId}`].includes(e.ruta)));
    assert.equal(resultado.oficial, false);
    if (escenario.nombre === 'desconocido') assert.equal(resultado.desconocido, 1);
    if (escenario.nombre === 'sin_dispositivo') {
      assert.equal(resultado.cobertura['SIN_SEÑAL'].estado, 'NO_CONCLUYENTE');
      assert.match(resultado.cobertura['SIN_SEÑAL'].motivo, /sin escrituras/);
    }
    if (escenario.nombre === 'candidata_sin_sensores') {
      assert.equal(resultado.canarios[0].area, 6);
      assert.equal(resultado.canarios[0].total, 0);
      assert.equal(resultado.cobertura.ACTIVO.area, 1);
      assert.ok(!resultado.unidades.some(u => u.area === 6));
    }
    if (escenario.nombre === 'respaldo_administrador') {
      assert.equal(resultado.cobertura.EN_MANTENIMIENTO.rol, 'Administrador');
      assert.ok(paginas.some(e => e.rol === 'Administrador'));
    }
    if (['ajeno_mantenimiento', 'e7_gris'].includes(escenario.nombre)) {
      assert.equal(resultado.disponibles.EN_MANTENIMIENTO, 3);
      assert.deepEqual(resultado.canarios.filter(x => [5, 6, 7].includes(x.area)).map(x => x.area), [5, 6, 7]);
      assert.equal(resultado.cobertura.EN_MANTENIMIENTO.dispositivo, 8);
      assert.equal(resultado.cobertura.EN_MANTENIMIENTO.sensores_cotejados, 1);
      assert.ok(!paginas.some(e => [5, 6].includes(Number(e.area))));
      assert.ok(resultado.descartadas.some(x => x.area === 6 && x.dispositivo === 7));
      if (escenario.nombre === 'e7_gris') {
        assert.ok(resultado.descartadas.some(x => x.area === 5 && /E7/.test(x.motivo)));
        assert.ok(resultado.canarios.some(x => x.area === 5 && x.excluida_e7));
      } else assert.ok(resultado.descartadas.some(x => x.area === 5 && x.dispositivo === 5));
    }
    if (escenario.nombre === 'buffer_como_sin_senal')
      assert.equal(resultado.cobertura.BUFFER_ACTIVO.estado, 'RECHAZADO');
    if (escenario.nombre === 'transporte_newman') {
      assert.equal(paginas.filter(e => e.cortada).length, 1);
      assert.ok(resultado.problemas_tecnicos.some(x => x.startsWith('NEWMAN_')));
      assert.notEqual(hijo.codigo, 0);
    } else {
      assert.equal(hijo.codigo, 0, `${escenario.nombre}: ${hijo.stderr}`);
      assert.deepEqual(resultado.problemas_tecnicos, []);
    }
    valido = true;
    return { escenario: escenario.nombre, estado: escenario.estado, peticiones: eventos.length,
      newman: paginas.length, valido };
  } catch (e) {
    return { escenario: escenario.nombre, valido, error: e.code ?? e.message,
      detalle: sanearArtefacto(e.message, []), diagnostico: diagnosticoHijo(hijo, temporal), temporal };
  } finally {
    await new Promise(resolve => servidor.close(resolve));
    if (valido) fs.rmSync(temporal, { recursive: true, force: true });
  }
}

const resultados = [];
for (const escenario of escenarios) {
  const resultado = await ensayar(escenario);
  resultados.push(resultado);
  if (resultado.error === 'EPERM') break;
}
const valido = resultados.length === escenarios.length && resultados.every(x => x.valido);
console.log(JSON.stringify({ grupo: 'G96', valido, escenarios: resultados }));
if (!valido) process.exitCode = 1;
