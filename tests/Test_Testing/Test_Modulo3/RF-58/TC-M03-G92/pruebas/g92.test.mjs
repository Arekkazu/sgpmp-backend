import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { evaluar, crearTransporte, comprobar } from '../g92.mjs';
import { CAPACIDADES, LIMITE, diagnosticarPagina, planTemporal, compararDashboard } from '../lib/g92_escenario.mjs';

let regresionesNuevas = 0;
const regresion = (condicion, mensaje) => { assert.equal(condicion, true, mensaje); regresionesNuevas++; };
const dir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
assert.equal(CAPACIDADES.contrato, 'sigab-qa-ejecutor/1');
assert.equal(LIMITE.sensores_referencia, 5);
assert.equal(LIMITE.solicitudes_directas - LIMITE.margen_cierre, 521);
assert.equal(LIMITE.solicitudes_directas, 525);
assert.deepEqual(CAPACIDADES.comprobaciones_obligatorias['TC-M03-181'].API,
  ['API-181-01', 'API-181-02']);
assert.equal(Object.values(CAPACIDADES.comprobaciones_obligatorias)
  .flatMap((x) => x.API).includes('API-181-03'), false);
regresion(Object.values(CAPACIDADES.comprobaciones_obligatorias)
  .flatMap((x) => x.API).length === 6, 'seis ASSERT obligatorias');
assert.equal(comprobar(), 0);
const tiempo = planTemporal('2026-10-25T05:00:00.000Z');
assert.equal(Date.parse(tiempo.inicio) - Date.parse(tiempo.ancla), 120000);
assert.equal(Date.parse(tiempo.marcas[1]) - Date.parse(tiempo.marcas[0]), 5000);
assert.equal(compararDashboard([{ total: 1, sensores: [{ id_sensor: 4, id_infraestructura: 7,
  tiempo_sin_reporte_min: 1 }], resumen_unidades: [{ id_infraestructura: 7,
    total_sensores: 1, alertas_activas_count: 0, estado_general: 'VERDE' }] }],
[{ total: 1, sensores: [{ id_sensor: 4, id_infraestructura: 7,
  tiempo_sin_reporte_min: 9, dato_desactualizado: true }], resumen_unidades: [{ id_infraestructura: 7,
    total_sensores: 1, alertas_activas_count: 0, estado_general: 'GRIS' }] }]), true);
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
await assert.rejects(() => transporteLocal.solicitar('POST', '/configuracion/infraestructuras',
  { cuerpo: { finca_id: 185, especie_id: 126 } }), /ID_FUERA_LISTA_BLANCA/);
const peticionesTope = [];
const transporteTope = crearTransporte({ base: 'http://simulador.invalid',
  runId: 'G92-V1-20261025-050000', secreto: 'SECRETO_LOCAL', bitacora: [], secretos: [],
  limite: 5, fetcher: async (_url, opciones) => {
    peticionesTope.push(opciones.method);
    return { status: 200, headers: { get: () => 'G92-V1-20261025-050000' },
      text: async () => '{}' };
  } });
transporteTope.abrir();
await transporteTope.solicitar('GET', '/usuarios/me');
await assert.rejects(() => transporteTope.solicitar('GET', '/usuarios/me'),
  /LIMITE_SOLICITUDES_FUNCIONALES/);
await transporteTope.solicitar('DELETE', '/test-control/runs/G92-V1-20261025-050000', { cierre: true });
for (let i = 0; i < 4; i++) await transporteTope.solicitar('GET', '/configuracion/fincas/184');
regresion(peticionesTope.join(',') === 'GET,DELETE,GET,GET,GET,GET' &&
  transporteTope.estado().exceso_cierre === 1, 'no hay operación funcional tras el límite y el cierre lo supera');

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
  const eventos = [], alertasCreadas = [], vistas = new Map(), consultasNewman = [];
  const sensoresSemilla = Array.from({ length: 1 }, (_, i) => ({
    id_sensor: 9000 + i, id_infraestructura: 349, estado_semaforo: 'VERDE' }));
  const areas = new Map(), dispositivos = new Map(), sensores = new Map(), alertas = new Map();
  let areaId = 1000, dispositivoId = 2000, sensorId = 3000, alertaId = 4000, telemetriaId = 5000;
  let cerrado = false, falla = null, umbralesLeidos = 0;
  const respuesta = (status, cuerpo, eco = true) => ({ status,
    headers: { get: (k) => k.toLowerCase() === 'x-test-run-id' && eco ? 'G92-V1-20261025-050000' : null },
    text: async () => JSON.stringify(cuerpo) });
  const listaSensores357 = () => {
    const items = Array.from({ length: falla === 'seis-sensores' ? 6 : 1 }, (_, i) =>
      ({ id_sensores: 358 + i, id_dispositivo_iot: 357, es_activo: true }));
    return { total: items.length, items };
  };
  const resumen = (area) => ({ id_infraestructura: area,
    total_sensores: area === 349 ? sensoresSemilla.length : [...sensores.values()].filter((s) => s.area === area && s.telemetria).length,
    estado_general: [...sensores.values()].filter((s) => s.area === area).some((s) => s.estado === 'ROJO') ? 'ROJO'
      : [...sensores.values()].filter((s) => s.area === area).some((s) => s.estado === 'AMARILLO') ? 'AMARILLO' : 'VERDE',
    alertas_activas_count: [...alertas.values()].filter((a) => a.area === area && a.estado === 'ACTIVA').length,
    ultimo_dato_recibido: '2026-10-25T05:00:00Z' });
  const dashboard = (ruta) => {
    const u = new URL('http://local' + ruta);
    const area = Number(u.searchParams.get('id_infraestructura')) || null;
    const pagina = Number(u.searchParams.get('pagina')) || 1;
    const todos = [...sensoresSemilla.filter((s) => s.id_infraestructura === area),
      ...[...sensores.entries()].filter(([, s]) => s.telemetria && s.area === area)
        .map(([id_sensor, s]) => ({ id_sensor, id_infraestructura: s.area, estado_semaforo: s.estado }))]
      .sort((a, b) => a.id_sensor - b.id_sensor);
    const porPagina = 50;
    const sensoresPagina = todos.slice((pagina - 1) * porPagina, pagina * porPagina)
      .map((s) => ({ ...s, tiempo_sin_reporte_min: cerrado ? 9 : 1,
        dato_desactualizado: cerrado }));
    const areasConDatos = [...new Set(todos.map((s) => s.id_infraestructura))];
    const unidades = areasConDatos.map(resumen);
    // Simula el defecto de recálculo local: página 1 AMARILLO con el ROJO en 55.
    if (area && pagina === 1 && todos.length === 60 && falla !== '183-correcto') unidades[0].estado_general =
      sensoresPagina.some((s) => s.estado_semaforo === 'ROJO') ? 'ROJO'
        : sensoresPagina.some((s) => s.estado_semaforo === 'AMARILLO') ? 'AMARILLO' : 'VERDE';
    if (area && todos.length === 3 && falla === '181-01') unidades[0].estado_general = 'VERDE';
    if (area && todos.length === 3 && falla === '181-03-presente')
      unidades[0].variables_en_atencion = ['TEMPERATURA_AMBIENTAL'];
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
      if (ruta.startsWith('/iot/alertas?')) return respuesta(200, { total: 0, items: [] });
      if (ruta.startsWith('/iot/monitoreo/historial')) return respuesta(200,
        falla === 'telemetria' && ruta.includes('sensor_id=3001')
          ? { total: 1, total_encontrado: 1, items: [{ id_telemetria: 5001 }] }
          : { total: 0, total_encontrado: 0, items: [] });
      if (ruta.startsWith('/iot/monitoreo/dashboard')) {
        if (falla === 'dashboard-404') return respuesta(404, { code: 'AREA_NO_ENCONTRADA' });
        if (falla === 'dashboard-403') return respuesta(403, { code: 'ACCESO_DENEGADO' });
        if (falla === 'dashboard-500') return respuesta(500, { code: 'ERROR_INTERNO' });
        if (falla === 'dashboard-timeout-cierre') throw new Error('The operation was aborted due to timeout');
        return respuesta(200, dashboard(ruta));
      }
      if (ruta === '/iot/alertas?id_sensor=358&fecha_desde=2026-10-25T04%3A58%3A00.000Z&fecha_hasta=2026-10-26T05%3A00%3A00.000Z&por_pagina=200')
        return respuesta(200, { total: 0, items: [] });
      if (/^\/configuracion\/sensores\/\d+\/(calibraciones|asociaciones)$/.test(ruta)) {
        if (ruta.startsWith('/configuracion/sensores/358/')) return respuesta(200,
          { total: 1, items: [{ id_sensor: 358, id_calibracion: 700,
            ...(falla === 'semilla-config' ? { ganancia: 2 } : { ganancia: 1 }) }] });
        if (falla === 'asociacion-404' && ruta === '/configuracion/sensores/3001/asociaciones')
          return respuesta(404, { code: 'SENSOR_NO_ENCONTRADO' });
        return respuesta(200, ['calibracion', 'asociacion'].includes(falla) &&
          ruta === `/configuracion/sensores/3001/${falla === 'calibracion' ? 'calibraciones' : 'asociaciones'}`
          ? { total: 1, items: [{ id_sensor: 3001 }] } : { total: 0, items: [] });
      }
      if (ruta === '/configuracion/dispositivos-iot/357/sensores')
        return respuesta(200, listaSensores357());
      if (ruta === '/configuracion/fincas/184') return respuesta(200,
        { id_finca: 184, es_activo: falla !== 'semilla' });
      if (ruta === '/configuracion/infraestructuras/349') return respuesta(200,
        { id_infraestructura: 349, id_finca: 184, especie_id: 126, es_activo: true, tipo_area: 'Corral' });
      if (ruta === '/configuracion/dispositivos-iot/357') return respuesta(200,
        { id_dispositivo_iot: 357, id_infraestructura: 349, categoria: 'SENSOR', id_tipo_dispositivo: 5 });
      if (ruta.startsWith('/configuracion/umbrales')) return respuesta(200,
        { items: [{ es_activo: true, id_variable_ambiental: 1,
          niveles: [{ nivel: 'normal', limite_inferior: 20, limite_superior: 30 }] }] });
      if (/^\/configuracion\/infraestructuras\/\d+$/.test(ruta)) return respuesta(404, {});
      if (/^\/configuracion\/dispositivos-iot\/\d+$/.test(ruta)) return respuesta(404, {});
      if (/^\/configuracion\/dispositivos-iot\/\d+\/sensores$/.test(ruta))
        return respuesta(200, falla === 'sensor-residuo' && ruta.includes('/2001/')
          ? { total: 1, items: [{ id_sensores: 3001 }] } : { total: 0, items: [] });
    }
    assert.equal(options.headers['X-Test-Run-Id'], 'G92-V1-20261025-050000');
    assert.equal(options.headers['X-Sandbox-Secret'], env.QA_SANDBOX_SECRET);
    if (ruta === '/usuarios/me') return respuesta(200, { id_usuario: 1 });
    if (ruta.startsWith('/iot/monitoreo/dashboard')) {
      if (falla === 'dashboard-timeout-preparacion') throw new Error('The operation was aborted due to timeout');
      return respuesta(200, dashboard(ruta));
    }
    if (ruta === '/configuracion/infraestructuras/349') return respuesta(200,
      { id_infraestructura: 349, id_finca: 184, especie_id: 126, es_activo: true, tipo_area: 'Corral' });
    if (ruta === '/configuracion/dispositivos-iot/357') return respuesta(200,
      { id_dispositivo_iot: 357, id_infraestructura: 349, categoria: 'SENSOR', id_tipo_dispositivo: 5 });
    if (ruta === '/configuracion/dispositivos-iot/357/sensores') return respuesta(200,
      listaSensores357());
    if (ruta.startsWith('/configuracion/sensores/358/')) return respuesta(200,
      { total: 1, items: [{ id_sensor: 358, id_calibracion: 700, ganancia: 1 }] });
    if (ruta.startsWith('/iot/alertas?id_sensor=358&')) return respuesta(200, { total: 0, items: [] });
    if (ruta.startsWith('/iot/monitoreo/historial?') && ruta.includes('id_infraestructura=349'))
      return respuesta(200, { total: 0, total_encontrado: 0, items: [] });
    if (ruta === '/configuracion/fincas/184') return respuesta(200,
      { id_finca: 184, es_activo: true });
    if (ruta.startsWith('/configuracion/umbrales')) return respuesta(200,
      { items: [{ es_activo: falla !== 'umbral-falta' || ++umbralesLeidos < 2, id_variable_ambiental: 1,
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
      { id_sensores_area_asociada: Number(ruta.split('/')[3]) + 10000,
        id_sensor: Number(ruta.split('/')[3]), id_infraestructura: body.id_infraestructura, tiene_estado: true });
    if (/\/calibrar$/.test(ruta)) return respuesta(201, { id_calibracion: 1 });
    if (ruta === '/iot/telemetria') {
      assert.equal(options.headers.Authorization, 'Bearer BROKER_LOCAL');
      assert.equal(body.access_key, undefined);
      sensores.get(body.sensor_id).telemetria = ++telemetriaId;
      return respuesta(201, { id_telemetria: telemetriaId, estado_calidad: 'LECTURA_VALIDA',
        ...(falla === 'ingesta-gris' ? { estado_semaforo: 'GRIS' } : {}) });
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
    consultasNewman.push(variables.consulta);
    const cuerpo = dashboard('/iot/monitoreo/dashboard' + variables.consulta);
    vistas.set(variables.fase, cuerpo);
    const archivo = `newman/newman-${variables.fase}.json`;
    fs.mkdirSync(path.join(contrato.directorio, 'newman'), { recursive: true });
    fs.writeFileSync(path.join(contrato.directorio, archivo), JSON.stringify({ simulador_local: true }));
    return { archivo, cuerpo, http: 200, proceso: 0, eco: true, fallos: [], aserciones: 4 };
  };
  const code = await evaluar(contrato, { env, newman, fetcher });
  const r = JSON.parse(fs.readFileSync(path.join(run, 'resultado.json'), 'utf8'));
  assert.equal(code, 0);
  assert.equal(r.oficial, true);
  assert.equal(r.casos['TC-M03-181'].estado, 'APROBADO');
  assert.equal(r.casos['TC-M03-181'].estado_tecnico, 'OK');
  regresion(r.casos['TC-M03-181'].estado === 'APROBADO', '181 aprobado sin campo excluido');
  assert.equal(r.casos['TC-M03-182'].estado, 'APROBADO');
  assert.equal(r.casos['TC-M03-183'].estado, 'RECHAZADO');
  regresion(r.casos['TC-M03-183'].estado === 'RECHAZADO', '183 rechaza recálculo por página');
  assert.equal(r.casos['TC-M03-183'].estado_tecnico, 'OK');
  assert.equal(r.comprobaciones.find((x) => x.id === 'PRE-183-01').estado, 'APROBADO');
  assert.equal(r.comprobaciones.find((x) => x.id === 'API-183-01').estado, 'APROBADO');
  assert.equal(r.comprobaciones.find((x) => x.id === 'API-183-02').estado, 'RECHAZADO');
  const excluida = r.comprobaciones.find((x) => x.id === 'API-181-03');
  assert.equal(excluida.estado, 'EXCLUIDA_DEL_ORACULO');
  assert.equal(excluida.tipo, 'EXCLUIDA');
  assert.deepEqual(excluida.valor_observado, { campo: null, presente: false });
  assert.equal(excluida.motivo, 'Exigencia de la matriz no contemplada en RF-58 (decisión QA 2026-10-25)');
  assert.equal(r.comprobaciones.filter((x) => x.tipo === 'ASSERT' && x.estado === 'APROBADO').length, 5);
  assert.equal(r.comprobaciones.filter((x) => x.estado === 'APROBADO').some((x) => x.id === 'API-181-03'), false);
  regresion(excluida.tipo === 'EXCLUIDA' && excluida.estado === 'EXCLUIDA_DEL_ORACULO',
    '181-03 excluida de aprobadas');
  const informe = fs.readFileSync(path.join(run, 'TC-M03-G92_resultado.md'), 'utf8');
  assert.match(informe, /## Observaciones documentales/);
  assert.match(informe, /API-181-03 \| EXCLUIDA \| EXCLUIDA_DEL_ORACULO/);
  assert.match(informe, /Valor observado en TEST:.*"presente": false/s);
  assert.equal(informe.slice(informe.indexOf('## Incidencias de producto'),
    informe.indexOf('## Incidencias técnicas QA')).includes('API-181-03'), false);
  regresion(informe.includes('## Observaciones documentales'), 'observación documental propia');
  assert.equal(r.cierre.rollback.verificado, true);
  assert.equal(r.cierre.run.cierre_http, 200);
  assert.equal(r.datos.ids_telemetria.length, 63);
  assert.equal(r.datos.inventario.length, 323);
  assert.equal(r.cierre.rollback.semilla_intacta, true);
  assert.equal(r.cierre.rollback.comprobaciones.filter((x) => x.tipo === 'calibracion_por_sensor').length, 63);
  assert.equal(r.cierre.rollback.comprobaciones.filter((x) => x.tipo === 'asociacion_por_sensor').length, 63);
  assert.equal(r.cierre.rollback.comprobaciones.filter((x) => x.tipo === 'telemetria_por_sensor').length, 63);
  assert.equal(r.newman.length, 4);
  assert.equal(r.bitacora.filter((x) => x.via !== 'Newman').length, 497);
  assert.equal(r.bitacora.filter((x) => !x.via && (x.metodo !== 'POST' || x.ruta !== '/sesiones/'))
    .every((x) => Object.hasOwn(x, 'respuesta')), true);
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
  assert.equal(fs.readdirSync(path.join(dir, 'Resultados')).filter((x) => x.endsWith('.md')).length, 0);
  regresion(r.cierre.rollback.semilla_intacta &&
    !eventos.some((x) => x.ruta.startsWith('/iot/monitoreo/dashboard?id_infraestructura=349')),
  'baseline 349 sin dashboard');
  regresion(r.comprobaciones.find((x) => x.id === 'PRE-182-01').estado === 'APROBADO' &&
    r.comprobaciones.find((x) => x.id === 'PRE-182-01').evidencias.length === 3,
  'PRE-182-01 derivada de a1 y b1');
  regresion(eventos.filter((x) => x.ruta.startsWith('/iot/monitoreo/dashboard'))
    .every((x) => new URL('http://local' + x.ruta).searchParams.has('id_infraestructura')) &&
    consultasNewman.every((x) => new URL('http://local/' + x).searchParams.has('id_infraestructura') &&
      new URL('http://local/' + x).searchParams.get('id_infraestructura') !== '349'),
  'ninguna consulta global del dashboard');
  regresion(eventos.filter((x) => x.ruta === '/configuracion/umbrales?id_especie=126').length === 6,
    'umbral revisado antes de cuatro Newman y en ambas semillas');
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
  assert.deepEqual(r.presupuesto, { nominal_directas: 497, maximo_directas: 521,
    tope_operativo_directas: 525, margen_cierre: 4,
    solicitudes_directas: 497, exceso_cierre: 0 });
  falla = 'seis-sensores'; cerrado = false; areas.clear(); dispositivos.clear(); sensores.clear(); alertas.clear();
  eventos.length = 0; consultasNewman.length = 0;
  await evaluar(contrato, { env, newman, fetcher });
  const abortado = JSON.parse(fs.readFileSync(path.join(run, 'resultado.json'), 'utf8'));
  assert.equal(abortado.estado, 'NO_CONCLUYENTE');
  assert.equal(abortado.cierre.run.cierre_http, 200);
  assert.equal(eventos.filter((x) => x.metodo === 'DELETE').length, 1);
  assert.equal(eventos.some((x) => x.metodo === 'POST' && x.ruta !== '/sesiones/'), false);
  assert.equal(consultasNewman.length, 0);
  regresion(abortado.problemas_tecnicos.some((x) => x.includes('SENSORES_357_EXCEDE_MAXIMO_5')),
    'seis sensores abortan antes de escrituras');

  falla = 'limite'; cerrado = false; areas.clear(); dispositivos.clear(); sensores.clear(); alertas.clear();
  areaId = 1000; dispositivoId = 2000; sensorId = 3000; alertaId = 4000; telemetriaId = 5000;
  eventos.length = 0; consultasNewman.length = 0;
  await evaluar(contrato, { env, newman, fetcher, limiteDirectas: 284 });
  const acotado = JSON.parse(fs.readFileSync(path.join(run, 'resultado.json'), 'utf8'));
  assert.equal(acotado.cierre.run.cierre_http, 200);
  assert.equal(acotado.cierre.rollback.verificado, true);
  assert.equal(acotado.presupuesto.solicitudes_directas, 497);
  assert.equal(acotado.presupuesto.exceso_cierre, 213);
  assert.equal(eventos.findIndex((x) => x.metodo === 'DELETE'), 280);
  assert.equal(acotado.cierre.rollback.comprobaciones.filter((x) => x.tipo === 'telemetria_por_sensor').length, 63);
  regresion(acotado.cierre.rollback.verificado && acotado.presupuesto.exceso_cierre === 213,
    'tope alcanzado conserva cierre completo y documenta exceso');
  eventos.length = 0; consultasNewman.length = 0;
  for (const variante of ['181-01', '181-03-presente', '183-correcto']) {
    falla = variante; cerrado = false; areas.clear(); dispositivos.clear(); sensores.clear(); alertas.clear();
    areaId = 1000; dispositivoId = 2000; sensorId = 3000; alertaId = 4000; telemetriaId = 5000;
    await evaluar(contrato, { env, newman, fetcher });
    const resultado = JSON.parse(fs.readFileSync(path.join(run, 'resultado.json'), 'utf8'));
    if (variante === '181-01') {
      assert.equal(resultado.casos['TC-M03-181'].estado, 'RECHAZADO');
      assert.equal(resultado.comprobaciones.find((x) => x.id === 'API-181-03').estado,
        'EXCLUIDA_DEL_ORACULO');
      regresion(resultado.casos['TC-M03-181'].estado === 'RECHAZADO',
        '181 rechaza solo fallo obligatorio');
    } else if (variante === '181-03-presente') {
      const observada = resultado.comprobaciones.find((x) => x.id === 'API-181-03');
      assert.equal(resultado.casos['TC-M03-181'].estado, 'APROBADO');
      assert.equal(observada.tipo, 'EXCLUIDA');
      assert.deepEqual(observada.valor_observado,
        { campo: 'variables_en_atencion', presente: true });
      regresion(observada.estado === 'EXCLUIDA_DEL_ORACULO',
        'presencia del campo sigue excluida');
    } else {
      assert.equal(resultado.casos['TC-M03-181'].estado, 'APROBADO');
      assert.equal(resultado.casos['TC-M03-182'].estado, 'APROBADO');
      assert.equal(resultado.casos['TC-M03-183'].estado, 'APROBADO');
      assert.equal(resultado.oficial, true);
      regresion(resultado.oficial, 'oficialidad posible sin 181-03');
    }
  }
  for (const defecto of ['calibracion', 'asociacion', 'asociacion-404', 'telemetria', 'semilla', 'semilla-config', 'sensor-residuo',
    'dashboard-404', 'dashboard-403', 'dashboard-500', 'dashboard-timeout-cierre',
    'umbral-falta', 'ingesta-gris']) {
    falla = defecto; cerrado = false; areas.clear(); dispositivos.clear(); sensores.clear(); alertas.clear();
    areaId = 1000; dispositivoId = 2000; sensorId = 3000; alertaId = 4000; telemetriaId = 5000; umbralesLeidos = 0;
    await evaluar(contrato, { env, newman, fetcher });
    const variante = JSON.parse(fs.readFileSync(path.join(run, 'resultado.json'), 'utf8'));
    assert.equal(variante.cierre.run.cierre_http, 200);
    if (!['umbral-falta', 'ingesta-gris'].includes(defecto))
      assert.equal(variante.cierre.rollback.verificado, false, defecto);
    if (['semilla', 'semilla-config'].includes(defecto)) {
      assert.equal(variante.cierre.rollback.semilla_intacta, false);
      if (defecto === 'semilla-config') regresion(true, 'alteración de calibración de 349 detectada');
    } else if (defecto === 'umbral-falta' || defecto === 'ingesta-gris') {
      assert.equal(variante.estado, 'NO_CONCLUYENTE');
      assert.equal(variante.casos['TC-M03-181'].veredicto, null);
      regresion(variante.problemas_tecnicos.some((x) => x.includes('RIESGO_AVISO_SIN_UMBRAL')) &&
        variante.newman.length === 0, 'sensor GRIS o umbral ausente aborta antes de Newman');
    } else if (defecto.startsWith('dashboard-timeout')) {
      assert.equal(variante.estado, 'NO_CONCLUYENTE');
      assert.equal(variante.casos['TC-M03-183'].veredicto, null);
      regresion(variante.problemas_tecnicos.some((x) => x.includes('Timeout técnico QA') &&
        x.includes('cierre fuera del RUN')), 'timeout filtrado en cierre es técnico QA');
    } else if (defecto === 'asociacion-404') {
      regresion(variante.cierre.rollback.comprobaciones.some((x) => x.tipo === 'asociacion_por_sensor' &&
        x.http === 404 && x.coincide === false), '404 por sensor o alcance no acredita rollback');
    } else if (defecto === 'sensor-residuo') {
      regresion(variante.cierre.rollback.comprobaciones.some((x) => x.tipo === 'sensores_del_dispositivo' &&
        x.coincide === false) && !variante.bitacora.some((x) =>
        x.metodo === 'GET' && x.ruta.startsWith('/iot/monitoreo/dashboard') && x.en_run === false),
      'residuo de sensor impide dashboard de cierre');
    } else if (defecto.startsWith('dashboard-')) {
      regresion(variante.cierre.rollback.verificado === false, `${defecto} no verifica cierre`);
    } else assert.equal(variante.cierre.rollback.comprobaciones.some((x) => x.tipo.includes(defecto)
      && x.coincide === false), true, defecto);
  }
  for (const archivo of ['preflight.json', 'resultado.json', 'TC-M03-G92_resultado.md',
    ...fs.readdirSync(path.join(run, 'newman')).map((x) => `newman/${x}`)]) {
    const contenido = fs.readFileSync(path.join(run, archivo), 'utf8');
    const seriales = eventos.filter((x) => x.metodo === 'POST' && x.ruta === '/configuracion/dispositivos-iot')
      .map((x) => x.body.serial);
    for (const secreto of [env.QA_SANDBOX_SECRET, env.BROKER_SERVICE_TOKEN,
      env.QA_ADMIN_EMAIL, env.QA_ADMIN_PASSWORD, env.QA_PROD_EMAIL, env.QA_PROD_PASSWORD,
      ...seriales]) assert.equal(contenido.includes(secreto), false, archivo);
  }
} finally { fs.rmSync(temporal, { recursive: true, force: true }); }
assert.equal(regresionesNuevas, 24);
console.log(`G92 simulador local: ${regresionesNuevas}/24 regresiones nuevas; anteriores OK`);
