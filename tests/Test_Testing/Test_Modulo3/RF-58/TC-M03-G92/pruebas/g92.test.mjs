import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { evaluar, crearTransporte, comprobar } from '../g92.mjs';
import { CAPACIDADES, diagnosticarPagina, planTemporal } from '../lib/g92_escenario.mjs';

const dir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
assert.equal(CAPACIDADES.contrato, 'sigab-qa-ejecutor/1');
assert.equal(comprobar(), 0);
const tiempo = planTemporal('2026-10-25T05:00:00.000Z');
assert.equal(Date.parse(tiempo.inicio) - Date.parse(tiempo.ancla), 120000);
assert.equal(Date.parse(tiempo.marcas[1]) - Date.parse(tiempo.marcas[0]), 5000);
const pagina = diagnosticarPagina({ inicial: { total: 3, sensores: [
  { id_sensor: 1, id_infraestructura: 2, estado_semaforo: 'VERDE' },
  { id_sensor: 2, id_infraestructura: 2, estado_semaforo: 'AMARILLO' },
  { id_sensor: 3, id_infraestructura: 2, estado_semaforo: 'ROJO' }],
resumen_unidades: [{ id_infraestructura: 2, estado_general: 'ROJO',
  alertas_activas_count: 2, ultimo_dato_recibido: '2026-10-25T05:00:00Z' }] }, areaA: 1, areaB: 2 });
assert.equal(pagina.checks['API-181-01'], true);
assert.equal(pagina.checks['API-181-03'], false);
const sensoresA = Array.from({ length: 60 }, (_, i) => ({ id_sensor: i + 1,
  id_infraestructura: 1, estado_semaforo: i === 54 ? 'ROJO' : 'VERDE' }));
const paginaA = { total: 60, sensores: sensoresA.slice(0, 50), resumen_unidades: [
  { id_infraestructura: 1, estado_general: 'VERDE', total_sensores: 60 }] };
const paginaA2 = { total: 60, sensores: sensoresA.slice(50), resumen_unidades: [
  { id_infraestructura: 1, estado_general: 'ROJO', total_sensores: 60 }] };
const diagnosticoA = (a1) => diagnosticarPagina({ a1, a2: paginaA2, areaA: 1, areaB: 2 });
assert.equal(diagnosticoA(paginaA).checks['PRE-183-01'], true);
for (const heredado of ['AMARILLO', 'ROJO']) {
  const a1 = structuredClone(paginaA);
  a1.sensores[2].estado_semaforo = heredado;
  assert.equal(diagnosticoA(a1).checks['PRE-183-01'], false,
    `Un ${heredado} heredado en A debe invalidar la precondiciÃ³n 183`);
}
const transporteLocal = crearTransporte({ base: 'http://simulador.invalid',
  runId: 'G92-V1-20261025-050000', secreto: 'SECRETO_LOCAL',
  bitacora: [], secretos: [], fetcher: () => { throw new Error('RED_INESPERADA'); } });
transporteLocal.abrir();
await assert.rejects(() => transporteLocal.solicitar('PATCH', '/iot/alertas/1/estado',
  { cuerpo: { nuevo_estado: 'RESUELTA' } }), /ESCRITURA_FUERA_LISTA_BLANCA/);

const temporal = fs.mkdtempSync(path.join(os.tmpdir(), 'g92-prueba-'));
try {
  const runId = 'RUN-G92-V1-20261025-050000';
  const run = path.join(temporal, runId);
  const contrato = { runId, version: 1, operacion: 'evaluar', referencia: 'SIMULADOR_LOCAL',
    contexto: { commit: 'NO_VERIFICADO' }, directorio: run };
  const env = { QA_AUTORIZADO: 'SI', SIGAB_API_TEST_BASE: 'http://simulador.invalid',
    QA_SANDBOX_SECRET: 'SECRETO_LOCAL', BROKER_SERVICE_TOKEN: 'BROKER_LOCAL',
    QA_ADMIN_EMAIL: 'admin@local.invalid', QA_ADMIN_PASSWORD: 'CLAVE_ADMIN_LOCAL',
    QA_PROD_EMAIL: 'prod@local.invalid', QA_PROD_PASSWORD: 'CLAVE_PROD_LOCAL' };
  const eventos = [], alertasCreadas = [], vistas = new Map();
  const areas = new Map(), dispositivos = new Map(), sensores = new Map(), alertas = new Map();
  let areaId = 1000, dispositivoId = 2000, sensorId = 3000, alertaId = 4000, telemetriaId = 5000;
  let cerrado = false;
  const respuesta = (status, cuerpo, eco = true) => ({ status,
    headers: { get: (k) => k.toLowerCase() === 'x-test-run-id' && eco ? 'G92-V1-20261025-050000' : null },
    text: async () => JSON.stringify(cuerpo) });
  const resumen = (area) => ({ id_infraestructura: area,
    total_sensores: [...sensores.values()].filter((s) => s.area === area && s.telemetria).length,
    estado_general: [...sensores.values()].filter((s) => s.area === area).some((s) => s.estado === 'ROJO') ? 'ROJO'
      : [...sensores.values()].filter((s) => s.area === area).some((s) => s.estado === 'AMARILLO') ? 'AMARILLO' : 'VERDE',
    alertas_activas_count: [...alertas.values()].filter((a) => a.area === area && a.estado === 'ACTIVA').length,
    ultimo_dato_recibido: '2026-10-25T05:00:00Z' });
  const dashboard = (ruta) => {
    const u = new URL('http://local' + ruta);
    const area = Number(u.searchParams.get('id_infraestructura')) || null;
    const pagina = Number(u.searchParams.get('pagina')) || 1;
    const todos = [...sensores.entries()].filter(([, s]) => s.telemetria && (!area || s.area === area))
      .sort(([a], [b]) => a - b).map(([id_sensor, s]) => ({ id_sensor,
        id_infraestructura: s.area, estado_semaforo: s.estado }));
    const porPagina = 50;
    const sensoresPagina = todos.slice((pagina - 1) * porPagina, pagina * porPagina);
    const areasConDatos = [...new Set(todos.map((s) => s.id_infraestructura))];
    const unidades = areasConDatos.map(resumen);
    // Simula el defecto de recálculo local: página 1 AMARILLO con el ROJO en 55.
    if (area && pagina === 1 && todos.length === 60) unidades[0].estado_general =
      sensoresPagina.some((s) => s.estado_semaforo === 'ROJO') ? 'ROJO'
        : sensoresPagina.some((s) => s.estado_semaforo === 'AMARILLO') ? 'AMARILLO' : 'VERDE';
    return { total: todos.length, pagina, por_pagina: porPagina,
      sensores: sensoresPagina, resumen_unidades: unidades };
  };
  const fetcher = async (url, options) => {
    assert.equal(fs.existsSync(path.join(run, 'preflight.json')), true, 'preflight antes de red');
    const ruta = new URL(url).pathname + new URL(url).search;
    const body = options.body ? JSON.parse(options.body) : null;
    eventos.push({ metodo: options.method, ruta, headers: options.headers, body });
    if (ruta === '/sesiones/') {
      assert.equal(options.headers['X-Test-Run-Id'], undefined, 'login fuera del RUN');
      return respuesta(200, { token: body.correo_electronico.startsWith('admin') ? 'JWT_ADMIN_SIM' : 'JWT_PROD_SIM' }, false);
    }
    if (options.method === 'DELETE') { cerrado = true; areas.clear(); dispositivos.clear();
      sensores.clear(); alertas.clear(); return respuesta(200, {}, false); }
    if (cerrado) {
      if (ruta.startsWith('/iot/alertas/')) return respuesta(404, {});
      if (ruta.startsWith('/iot/monitoreo/historial')) return respuesta(200, { total: 0, items: [] });
      if (ruta.startsWith('/iot/monitoreo/dashboard')) return respuesta(200, dashboard(ruta));
      if (/^\/configuracion\/infraestructuras\/\d+$/.test(ruta)) return respuesta(404, {});
      if (/^\/configuracion\/dispositivos-iot\/\d+$/.test(ruta)) return respuesta(404, {});
      if (/^\/configuracion\/dispositivos-iot\/\d+\/sensores$/.test(ruta))
        return respuesta(200, { total: 0, items: [] });
    }
    assert.equal(options.headers['X-Test-Run-Id'], 'G92-V1-20261025-050000');
    assert.equal(options.headers['X-Sandbox-Secret'], env.QA_SANDBOX_SECRET);
    if (ruta === '/usuarios/me') return respuesta(200, { id_usuario: 1 });
    if (ruta.startsWith('/iot/monitoreo/dashboard')) return respuesta(200, dashboard(ruta));
    if (ruta === '/configuracion/infraestructuras/349') return respuesta(200,
      { id_infraestructura: 349, id_finca: 184, especie_id: 126, es_activo: true, tipo_area: 'Corral' });
    if (ruta === '/configuracion/dispositivos-iot/357') return respuesta(200,
      { id_dispositivo_iot: 357, categoria: 'SENSOR', id_tipo_dispositivo: 5 });
    if (ruta === '/configuracion/fincas/184') return respuesta(200,
      { id_finca: 184, es_activo: true });
    if (ruta.startsWith('/configuracion/umbrales')) return respuesta(200,
      { items: [{ es_activo: true, id_variable_ambiental: 1,
        niveles: [{ nivel: 'normal', limite_inferior: 20, limite_superior: 30 }] }] });
    if (ruta === '/configuracion/infraestructuras' && options.method === 'POST') {
      const id_infraestructura = ++areaId;
      areas.set(id_infraestructura, body); return respuesta(201, { id_infraestructura, id_finca: 184 });
    }
    if (/^\/configuracion\/infraestructuras\/\d+$/.test(ruta)) {
      const id = Number(ruta.split('/').at(-1)); return respuesta(200, { id_infraestructura: id, id_finca: 184 });
    }
    if (ruta === '/configuracion/dispositivos-iot' && options.method === 'POST') {
      assert.equal(body.id_dispositivo_gateway, undefined);
      const id_dispositivo_iot = ++dispositivoId;
      dispositivos.set(id_dispositivo_iot, body);
      return respuesta(201, { id_dispositivo_iot, categoria: 'SENSOR', id_dispositivo_gateway: null });
    }
    if (/^\/configuracion\/dispositivos-iot\/\d+\/sensores$/.test(ruta)) {
      const id_sensores = ++sensorId;
      const dispositivo = Number(ruta.split('/')[3]);
      sensores.set(id_sensores, { area: dispositivos.get(dispositivo).id_infraestructura, estado: 'VERDE' });
      return respuesta(201, { id_sensores });
    }
    if (/\/asociar$/.test(ruta)) return respuesta(201,
      { id_sensor: Number(ruta.split('/')[3]), id_infraestructura: body.id_infraestructura, tiene_estado: true });
    if (/\/calibrar$/.test(ruta)) return respuesta(201, { id_calibracion: 1 });
    if (ruta === '/iot/telemetria') {
      assert.equal(options.headers.Authorization, 'Bearer BROKER_LOCAL');
      assert.equal(body.access_key, undefined);
      sensores.get(body.sensor_id).telemetria = ++telemetriaId;
      return respuesta(201, { id_telemetria: telemetriaId, estado_calidad: 'LECTURA_VALIDA' });
    }
    if (ruta === '/iot/alertas' && options.method === 'POST') {
      assert.equal(options.headers.Authorization, 'Bearer BROKER_LOCAL');
      assert.equal(body.access_key, undefined);
      const id_alerta = ++alertaId;
      const s = sensores.get(body.sensor_id);
      s.estado = body.severidad_edge === 'CRITICO' ? 'ROJO' : 'AMARILLO';
      alertas.set(id_alerta, { sensor: body.sensor_id, area: s.area,
        severidad: body.severidad_edge, estado: 'ACTIVA' });
      alertasCreadas.push({ sensor: body.sensor_id, area: s.area,
        severidad: body.severidad_edge, estado: 'ACTIVA' });
      return respuesta(201, { id_alerta, es_duplicado: false });
    }
    if (/^\/iot\/alertas\/\d+$/.test(ruta) && options.method === 'GET') {
      const a = alertas.get(Number(ruta.split('/').at(-1)));
      return respuesta(200, { id_sensor: a.sensor, estado_alerta: a.estado, severidad: a.severidad });
    }
    throw new Error(`Ruta inesperada ${ruta}`);
  };
  const newman = ({ contrato, variables }) => {
    const cuerpo = dashboard('/iot/monitoreo/dashboard' + variables.consulta);
    vistas.set(variables.fase, cuerpo);
    const archivo = `newman/newman-${variables.fase}.json`;
    fs.mkdirSync(path.join(contrato.directorio, 'newman'), { recursive: true });
    fs.writeFileSync(path.join(contrato.directorio, archivo), JSON.stringify({ simulador_local: true }));
    return { archivo, cuerpo, http: 200, proceso: 0, eco: true, fallos: [], aserciones: 4 };
  };
  const code = await evaluar(contrato, { env, newman, fetcher });
  assert.equal(code, 0);
  const r = JSON.parse(fs.readFileSync(path.join(run, 'resultado.json'), 'utf8'));
  assert.equal(r.oficial, true);
  assert.equal(r.casos['TC-M03-181'].estado, 'RECHAZADO');
  assert.equal(r.casos['TC-M03-182'].estado, 'APROBADO');
  assert.equal(r.casos['TC-M03-183'].estado, 'RECHAZADO');
  assert.equal(r.casos['TC-M03-183'].estado_tecnico, 'OK');
  assert.equal(r.comprobaciones.find((x) => x.id === 'PRE-183-01').estado, 'APROBADO');
  assert.equal(r.comprobaciones.find((x) => x.id === 'API-183-01').estado, 'APROBADO');
  assert.equal(r.comprobaciones.find((x) => x.id === 'API-183-02').estado, 'RECHAZADO');
  assert.equal(r.comprobaciones.find((x) => x.id === 'API-181-03').estado, 'RECHAZADO');
  assert.equal(r.cierre.rollback.verificado, true);
  assert.equal(r.cierre.run.cierre_http, 200);
  assert.equal(r.datos.ids_telemetria.length, 63);
  assert.equal(r.newman.length, 5);
  assert.equal(r.bitacora.filter((x) => x.via !== 'Newman').length, 289);
  assert.equal(r.casos['TC-M03-183'].observado.posicion_rojo, 55);
  const areaA = vistas.get('a1').sensores[0].id_infraestructura;
  const areaB = vistas.get('inicial').sensores[0].id_infraestructura;
  assert.notEqual(areaA, areaB);
  assert.equal(vistas.get('inicial').sensores.every((s) => s.id_infraestructura === areaB), true);
  assert.equal(vistas.get('a1').sensores.every((s) => s.estado_semaforo === 'VERDE'), true);
  assert.equal(alertasCreadas.filter((a) => a.area === areaA).length, 1);
  assert.equal(alertasCreadas.filter((a) => a.area === areaB).length, 2);
  assert.equal(alertasCreadas.every((a) => a.estado === 'ACTIVA'), true);
  for (const archivo of r.evidencias) assert.equal(fs.existsSync(path.join(run, archivo)), true);
  assert.equal(fs.readdirSync(run).filter((x) => x.endsWith('.md')).length, 1);
  assert.equal(fs.existsSync(path.join(dir, 'Resultados')), false);
  const texto = fs.readFileSync(path.join(run, 'resultado.json'), 'utf8');
  for (const secreto of [env.QA_SANDBOX_SECRET, env.BROKER_SERVICE_TOKEN,
    env.QA_ADMIN_EMAIL, env.QA_ADMIN_PASSWORD, env.QA_PROD_EMAIL, env.QA_PROD_PASSWORD])
    assert.equal(texto.includes(secreto), false);
  assert.equal(eventos.filter((x) => x.ruta === '/sesiones/').length, 4);
  assert.equal(eventos.filter((x) => x.metodo === 'DELETE').length, 1);
  assert.equal(eventos.filter((x) => x.metodo === 'POST' && x.ruta === '/configuracion/infraestructuras').length, 2);
  assert.equal(eventos.filter((x) => x.metodo === 'POST' && x.ruta === '/configuracion/dispositivos-iot').length, 2);
  assert.equal(eventos.filter((x) => x.metodo === 'POST' && /^\/configuracion\/dispositivos-iot\/\d+\/sensores$/.test(x.ruta)).length, 63);
  assert.equal(eventos.filter((x) => x.ruta === '/iot/telemetria').length, 63);
  assert.equal(eventos.filter((x) => x.ruta === '/iot/alertas' && x.metodo === 'POST').length, 3);
  assert.equal(eventos.filter((x) => x.ruta.startsWith('/configuracion/sensores/') && x.ruta.endsWith('/asociar')).length, 63);
  assert.equal(eventos.filter((x) => x.ruta.startsWith('/configuracion/sensores/') && x.ruta.endsWith('/calibrar')).length, 63);
  assert.equal(eventos.filter((x) => x.metodo === 'PATCH').length, 0);
  assert.equal(eventos.some((x) => x.ruta.includes('test-control/query')), false);
  assert.equal(cerrado, true);
} finally { fs.rmSync(temporal, { recursive: true, force: true }); }
console.log('G92 simulador local: OK');
