import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';
import { CAPACIDADES, PRESUPUESTO, evaluarPanel, precondicion, riesgoE7,
  SEMILLA_G98, normalizarTipoVariable, elegirTernaSemilla, cuerpoSemilla } from '../lib/g98_escenario.mjs';
import { comprobar, descubrir, descubrirSemilla, evaluarNewman, fallosNewman, informe, preflight } from '../g98.mjs';
import { contextoEjecucion } from '../lib/contrato_ejecutor.mjs';
import { clasificarRegistro } from './registro_qa.mjs';

const ahora = Date.parse('2026-10-31T12:00:00Z');
const alertas = ['CRITICO','MODERADO','LEVE'].map((severidad, i) => ({ id_alerta: 11+i,
  id_sensor: 21+i, id_activo_biologico: 31, estado_alerta: 'ACTIVA', tipo_alerta: 'UMBRAL',
  tipo_variable: 'PH_AGUA', severidad, id_infraestructura: 1,
  fecha_generacion: new Date(ahora-(i+1)*60000).toISOString(), minutos_transcurridos: i+1 }));
const esperado = { total: 3, ids: new Set([11,12,13]) };
const body = xs => ({ panel_alertas_activas: { total: xs.length, alertas: xs } });

test('precondición mixta, sensores distintos y canario E7', () => {
  assert.equal(precondicion(alertas), true);
  assert.equal(precondicion(alertas.map(x => ({ ...x, id_sensor: 21 }))), false);
  assert.equal(precondicion([...alertas.map((x,i) => i === 1 ? { ...x, id_sensor: 21 } : x),
    { ...alertas[2], id_alerta: 14, id_sensor: 24 }]), false);
  assert.equal(precondicion(alertas.slice(0,2)), false);
  assert.equal(riesgoE7({ sensores: [{ estado_semaforo: 'GRIS', dato_desactualizado: false }] }), true);
  assert.equal(riesgoE7({ sensores: [{ estado_semaforo: 'GRIS', dato_desactualizado: true, sin_umbral: false }] }), false);
});
test('panel: contrato, orden, total, ACTIVA, tiempo y alcance', () => {
  const evaluar = (b, e = esperado) => evaluarPanel(b, { ahora, esperado: e, unidad: 1 });
  assert.equal(evaluar(body(alertas)).estado, 'APROBADO');
  assert.equal(evaluar({ sensores: [] }).estado, 'RECHAZADO');
  assert.match(evaluar(body([alertas[2],alertas[0],alertas[1]])).motivo, /orden/);
  assert.match(evaluar(body([{ ...alertas[0], severidad: 'CRITICO', fecha_generacion: alertas[1].fecha_generacion,
    minutos_transcurridos: 2 }, { ...alertas[1], severidad: 'CRITICO', fecha_generacion: alertas[0].fecha_generacion,
    minutos_transcurridos: 1 }, alertas[2]])).motivo, /recencia/);
  assert.match(evaluar({ panel_alertas_activas: { total: 4, alertas } }).motivo, /total/);
  assert.match(evaluar(body(alertas.map((x,i) => i === 1 ? { ...x, id_alerta: 99 } : x))).motivo, /no ACTIVA/);
  assert.match(evaluar(body(alertas.map((x,i) => i === 1 ? { ...x, id_infraestructura: 2 } : x))).motivo, /fuera del área/);
  assert.match(evaluar(body(alertas.map((x,i) => i === 1 ? { ...x, minutos_transcurridos: 999 } : x))).motivo, /minutos/);
});
test('colección y contrato V2 locales', () => {
  const col = JSON.parse(fs.readFileSync(new URL('../G98.postman_collection.json', import.meta.url), 'utf8'));
  assert.equal(col.item.length, 1);
  assert.equal(col.item[0].request.method, 'GET');
  for (const e of col.item[0].event) new vm.Script(e.script.exec.join('\n'));
  assert.equal(CAPACIDADES.versiones.min, 2);
  assert.equal(CAPACIDADES.versiones.max, 3);
  assert.deepEqual(CAPACIDADES.operaciones, ['reevaluar', 'reintentar']);
  assert.equal(PRESUPUESTO.solicitudes_en_run, 224);
  assert.equal(comprobar(), 0);
});
test('REINTENTAR V2 conserva contrato, alcance y preflight local', t => {
  const directorio = path.dirname(fileURLToPath(new URL('../g98.mjs', import.meta.url)));
  const runId = 'RUN-G98-V2-20261101-120000';
  const rutaRun = path.join(directorio, 'EvaluacionV2', 'Resultados', runId);
  const archivo = path.join(rutaRun, 'contexto_operacion.json');
  const referencia = 'AUT-LOCAL';
  const args = ['--operacion', 'reintentar', '--version', '2', '--intento', '3',
    '--run-id', runId, '--autorizacion', referencia, '--contexto', archivo];
  const datos = { grupo: 'G98', version: 2, intento: 3, run_id: runId,
    operacion: 'REINTENTAR', referencia, casos: ['TC-M03-191'],
    alcance_reevaluacion: { casos: ['TC-M03-191'] }, version_anterior: 1 };
  t.mock.method(fs, 'statSync', () => ({ isFile: () => true }));
  t.mock.method(fs, 'lstatSync', () => ({ isSymbolicLink: () => false }));
  t.mock.method(fs, 'readFileSync', () => JSON.stringify(datos));
  const c = contextoEjecucion(args, { grupo: 'G98', casos: ['TC-M03-191'], directorio });
  assert.equal(c.operacion, 'reintentar');
  assert.equal(c.version, 2);
  assert.equal(c.intento, 3);
  assert.equal(c.directorio, rutaRun);
  const env = { QA_AUTORIZADO: 'SI', SIGAB_API_TEST_BASE: 'https://www.api.inmero.co/api-sgpmp-test',
    QA_SANDBOX_SECRET: 'LOCAL', QA_PROD_EMAIL: 'local@example.test', QA_PROD_PASSWORD: 'LOCAL' };
  assert.equal(preflight(c, env).ok, true);
  assert.equal(preflight({ ...c, version: 1 }, env).ok, false);
  datos.version_anterior = 2;
  assert.throws(() => contextoEjecucion(args, { grupo: 'G98', casos: ['TC-M03-191'], directorio }),
    /Falta alcance/);
});
test('REEVALUAR V3 usa EvaluacionV3 y exige version_anterior 2', t => {
  const directorio = path.dirname(fileURLToPath(new URL('../g98.mjs', import.meta.url)));
  const runId = 'RUN-G98-V3-20261101-120000';
  const rutaRun = path.join(directorio, 'EvaluacionV3', 'Resultados', runId);
  const archivo = path.join(rutaRun, 'contexto_operacion.json');
  const args = ['--operacion', 'reevaluar', '--version', '3', '--intento', '1',
    '--run-id', runId, '--autorizacion', 'AUT-LOCAL', '--contexto', archivo];
  const datos = { grupo: 'G98', version: 3, intento: 1, run_id: runId,
    operacion: 'REEVALUAR', referencia: 'AUT-LOCAL', casos: ['TC-M03-191'],
    alcance_reevaluacion: { casos: ['TC-M03-191'] }, version_anterior: 2 };
  t.mock.method(fs, 'statSync', () => ({ isFile: () => true }));
  t.mock.method(fs, 'lstatSync', () => ({ isSymbolicLink: () => false }));
  t.mock.method(fs, 'readFileSync', () => JSON.stringify(datos));
  const c = contextoEjecucion(args, { grupo: 'G98', casos: ['TC-M03-191'], directorio });
  assert.equal(c.directorio, rutaRun);
  assert.equal(c.version, 3);
  assert.equal(c.operacion, 'reevaluar');
  const env = { QA_AUTORIZADO: 'SI', SIGAB_API_TEST_BASE: 'https://www.api.inmero.co/api-sgpmp-test',
    QA_SANDBOX_SECRET: 'LOCAL', QA_PROD_EMAIL: 'local@example.test', QA_PROD_PASSWORD: 'LOCAL' };
  assert.equal(preflight(c, env).ok, true);
  datos.version_anterior = 1;
  assert.throws(() => contextoEjecucion(args, { grupo: 'G98', casos: ['TC-M03-191'], directorio }), /Falta alcance/);
});
test('ventana de tiempo admite reloj fijo del sandbox y rechaza valores imposibles', () => {
  const inicioRun = Date.parse('2026-10-31T18:34:17.500Z');
  const respuesta = Date.parse('2026-10-31T18:34:30Z');
  const base = alertas.map((a, i) => ({ ...a, fecha_generacion: new Date(inicioRun + 9500 + i * 350).toISOString(),
    minutos_transcurridos: -1 }));
  const evaluar = xs => evaluarPanel(body(xs), { ahora: respuesta, inicioRun, esperado, unidad: 1 });
  const fijo = evaluar(base);
  assert.equal(fijo.estado, 'APROBADO');
  assert.match(fijo.observaciones.join(' '), /minutos negativos por now\(\) fijo del sandbox/);
  assert.equal(evaluar(base.map(a => ({ ...a, minutos_transcurridos: 0 }))).estado, 'APROBADO');
  const imposible = evaluar(base.map(a => ({ ...a, minutos_transcurridos: -30 })));
  assert.equal(imposible.estado, 'RECHAZADO');
  assert.match(imposible.motivo, /minutos_transcurridos.*valor -30.*se espera un entero entre/);
  assert.equal(evaluar(base.map(({ minutos_transcurridos, ...a }) => a)).estado, 'RECHAZADO');
  assert.equal(evaluar(base.map(a => ({ ...a, minutos_transcurridos: -0.5 }))).estado, 'RECHAZADO');
  assert.equal(evaluar(base.map(a => ({ ...a, fecha_generacion: new Date(respuesta + 61000).toISOString() }))).estado, 'RECHAZADO');
});
test('semilla usa tres sensores, variables y lecturas reales del mismo activo', () => {
  const candidatos = ['PH_AGUA', 'NH3', 'CO2'].map((tipo_variable, i) => ({
    tipo_variable, id_sensor: 21+i, id_dispositivo_iot: 31+i,
    id_telemetria: 41+i, id_activo_biologico: 51, serial: 'SERIAL_SOLO_LOCAL' }));
  assert.equal(elegirTernaSemilla(candidatos)?.length, 3);
  assert.equal(elegirTernaSemilla(candidatos.map(x => ({ ...x, id_sensor: 21 }))), null);
  assert.equal(elegirTernaSemilla(candidatos.map(x => ({ ...x, tipo_variable: 'NH3' }))), null);
  assert.equal(elegirTernaSemilla(candidatos.map((x,i) => i === 2 ? { ...x, id_activo_biologico: 52 } : x)), null);
  const cuerpo = cuerpoSemilla(candidatos[0], 'CRITICO', new Date(ahora));
  assert.equal(cuerpo.id_telemetria, 41);
  assert.equal(cuerpo.reglas_activadas[0].id, 'RF57_BASE_PH_AGUA');
  assert.equal(cuerpo.valor, '5.0');
});
test('nombres de historial forman la terna normalizada y cuerpos POST válidos', async t => {
  const runId = 'RUN-G98-V2-LOCAL';
  const nombres = [' pH  del  agua ', ' Amoníaco (NH3) ', ' Temperatura  Corporal '];
  const codigos = ['PH_AGUA', 'NH3', 'TEMPERATURA_CORPORAL'];
  const rutasHistorial = [];
  const json = body => new Response(JSON.stringify(body), { status: 200, headers: { 'X-Test-Run-Id': runId } });
  t.mock.method(globalThis, 'fetch', async url => {
    const u = new URL(url);
    if (u.pathname === '/configuracion/dispositivos-iot') return json({ items: [
      { id_dispositivo_iot: 789, id_infraestructura: 702, es_activo: true, serial: 'SERIAL_LOCAL' }] });
    if (u.pathname === '/activos-biologicos') return json({ total_registros: 1,
      registros: [{ id_activo_biologico: 928, id_infraestructura: 702 }] });
    if (u.pathname === '/configuracion/dispositivos-iot/789/sensores') return json({ items: [1210, 1211, 1212]
      .map(id_sensores => ({ id_sensores, id_dispositivo_iot: 789, es_activo: true })) });
    if (u.pathname === '/iot/monitoreo/historial') {
      rutasHistorial.push(u);
      const i = Number(u.searchParams.get('sensor_id')) - 1210;
      const valida = { id_sensor: 1210+i, id_infraestructura: 702, id_activo_biologico: 928,
        id_telemetria: 118639+i, tipo_variable: nombres[i] };
      return json({ items: i === 0 ? [{ ...valida, id_telemetria: 118638,
        tipo_variable: 'Variable desconocida' }, valida] : [valida] });
    }
    if (u.pathname === '/iot/monitoreo/dashboard/702') return json({ sensores: [{ estado_semaforo: 'VERDE',
      dato_desactualizado: false, sin_umbral: false }] });
    throw Error(`Ruta local inesperada: ${u.pathname}`);
  });
  const r = { unidades: [702], bitacora: [], observaciones: [], problemas_tecnicos: [], inicio: new Date().toISOString() };
  const semilla = await descubrirSemilla('http://127.0.0.1', 'TOKEN_LOCAL', { QA_SANDBOX_SECRET: 'LOCAL' },
    { runId }, r, 'Productor');
  assert.equal(semilla?.unidad, 702);
  assert.deepEqual(semilla.terna.map(x => x.tipo_variable), codigos);
  assert.deepEqual(semilla.terna.map(x => x.id_sensor), SEMILLA_G98.sensores);
  assert.deepEqual(semilla.terna.map(x => x.id_activo_biologico), [928, 928, 928]);
  assert.equal(rutasHistorial.length, 3);
  for (const ruta of rutasHistorial) {
    const filtros = [...ruta.searchParams.keys()].filter(x => !['fecha_inicio', 'fecha_fin', 'pagina', 'por_pagina'].includes(x));
    assert.deepEqual(filtros, ['sensor_id']);
    assert.equal(ruta.searchParams.get('por_pagina'), '100');
  }
  assert.match(r.observaciones.join(' '), /variable de historial no reconocido/);
  for (const [i, sensor] of semilla.terna.entries()) {
    const cuerpo = cuerpoSemilla(sensor, ['CRITICO', 'MODERADO', 'LEVE'][i], new Date(ahora));
    assert.equal(cuerpo.tipo_variable, codigos[i]);
    assert.equal(cuerpo.reglas_activadas[0].id, `RF57_BASE_${codigos[i]}`);
    assert.equal(cuerpo.id_telemetria, 118639+i);
    assert.equal(Object.hasOwn(cuerpo, 'categoria_variable'), false);
  }
});
test('historial HTTP 422 conserva código técnico y no se confunde con falta de lecturas', async t => {
  const runId = 'RUN-G98-V2-LOCAL';
  const json = (status, body) => new Response(JSON.stringify(body), { status,
    headers: { 'X-Test-Run-Id': runId } });
  t.mock.method(globalThis, 'fetch', async url => {
    const u = new URL(url);
    if (u.pathname === '/configuracion/dispositivos-iot') return json(200, { items: [
      { id_dispositivo_iot: 789, id_infraestructura: 702, es_activo: true, serial: 'LOCAL' }] });
    if (u.pathname === '/activos-biologicos') return json(200, { total_registros: 1,
      registros: [{ id_activo_biologico: 928, id_infraestructura: 702 }] });
    if (u.pathname === '/configuracion/dispositivos-iot/789/sensores') return json(200, { items: [1210]
      .map(id_sensores => ({ id_sensores, id_dispositivo_iot: 789, es_activo: true })) });
    if (u.pathname === '/iot/monitoreo/historial') return json(422, { error_code: 'COMBINACION_FILTROS_INVALIDA' });
    throw Error(`Ruta local inesperada: ${u.pathname}`);
  });
  const r = { unidades: [702], bitacora: [], observaciones: [], problemas_tecnicos: [], inicio: new Date().toISOString() };
  assert.equal(await descubrirSemilla('http://127.0.0.1', 'TOKEN_LOCAL', { QA_SANDBOX_SECRET: 'LOCAL' },
    { runId }, r, 'Productor'), null);
  assert.deepEqual(r.historial_http, { consultas: 1, errores: 1 });
  assert.match(r.observaciones.join(' '), /historial HTTP 422, código COMBINACION_FILTROS_INVALIDA/);
  assert.deepEqual(r.problemas_tecnicos, ['HISTORIAL_HTTP_422_COMBINACION_FILTROS_INVALIDA']);
});
test('código TEMP_CORPORAL y nombres desconocidos', () => {
  assert.equal(normalizarTipoVariable('  temp_corporal '), 'TEMPERATURA_CORPORAL');
  assert.equal(normalizarTipoVariable(' PH_AGUA '), 'PH_AGUA');
  assert.equal(normalizarTipoVariable('variable desconocida'), null);
});
test('área 702 visible se prioriza; si falta, sigue el descubrimiento normal', async t => {
  const runId = 'RUN-G98-V2-LOCAL';
  let visible = true;
  const rutas = [];
  const json = body => new Response(JSON.stringify(body), { status: 200, headers: { 'X-Test-Run-Id': runId } });
  t.mock.method(globalThis, 'fetch', async url => {
    const u = new URL(url);
    rutas.push(`${u.pathname}${u.search}`);
    if (u.pathname === '/configuracion/infraestructuras') return json({ items: u.searchParams.get('finca_id') === '184'
      ? (visible ? [{ id_infraestructura: 702 }] : []) : [{ id_infraestructura: Number(u.searchParams.get('finca_id')) }] });
    if (u.pathname === '/configuracion/fincas') return json({ items: [{ id_finca: 1 }, { id_finca: 80 }, { id_finca: 184 }] });
    if (u.pathname === '/iot/alertas') return json({ total: 0, items: [] });
    throw Error(`Ruta local inesperada: ${u.pathname}`);
  });
  for (const caso of [true, false]) {
    visible = caso; rutas.length = 0;
    const r = { bitacora: [], observaciones: [], inicio: new Date().toISOString() };
    await descubrir('http://127.0.0.1', 'TOKEN_LOCAL', { QA_SANDBOX_SECRET: 'LOCAL' }, { runId }, r);
    assert.deepEqual(r.unidades, caso ? [702, 1, 80] : [1, 80]);
    assert.match(rutas[0], /finca_id=184/);
    assert.equal(rutas.filter(x => x.includes('finca_id=184')).length, 1);
    if (!caso) assert.match(r.observaciones.join(' '), /no visible/);
  }
});
test('script real de colección clasifica panel y discrepancias en memoria', () => {
  const col = JSON.parse(fs.readFileSync(new URL('../G98.postman_collection.json', import.meta.url), 'utf8'));
  const codigo = col.item[0].event.find(x => x.listen === 'test').script.exec.join('\n');
  const fallos = (b, conObservacion = false) => {
    let n = 0;
    const variables = { run_id: 'ENSAYO-LOCAL', expected_total: '3', expected_ids: '[11,12,13]',
      unidad: '1', inicio_run: new Date(ahora - 15000).toISOString() };
    const pm = { environment: { get: k => variables[k] }, response: { code: 200,
      headers: { get: k => k === 'Date' ? new Date(ahora).toUTCString() : 'ENSAYO-LOCAL' }, json: () => b },
      expect: (x) => ({ to: { eql: y => { if (x !== y) throw Error('ASSERT'); } } }),
      test: (_nombre, f) => { try { f(); } catch { n++; } } };
    pm.environment.set = (k, v) => { variables[k] = v; };
    vm.runInNewContext(codigo, { pm, Date: { now: () => ahora, parse: Date.parse }, Set, JSON, Number, Math, Object, String });
    return conObservacion ? { n, observacion: variables.observacion_tiempo } : n;
  };
  assert.equal(fallos(body(alertas)), 0);
  assert.equal(fallos({ sensores: [] }), 1);
  assert.equal(fallos(body([alertas[2],alertas[0],alertas[1]])), 1);
  assert.equal(fallos({ panel_alertas_activas: { total: 4, alertas } }), 1);
  assert.equal(fallos(body(alertas.map((x,i) => i === 1 ? { ...x, id_alerta: 99 } : x))), 1);
  const recientes = alertas.map(a => ({ ...a, fecha_generacion: new Date(ahora - 5000).toISOString(),
    minutos_transcurridos: -1 }));
  assert.deepEqual(fallos(body(recientes), true), { n: 0,
    observacion: 'minutos negativos por now() fijo del sandbox (indicadores_alertas_repository.py:70); en producción now() es por petición' });
  assert.equal(fallos(body(recientes.map(a => ({ ...a, minutos_transcurridos: 0 })))), 0);
  assert.equal(fallos(body(recientes.map(a => ({ ...a, minutos_transcurridos: -30 })))), 1);
  assert.equal(fallos(body(recientes.map(({ minutos_transcurridos, ...a }) => a))), 1);
  assert.equal(fallos(body(recientes.map(a => ({ ...a, minutos_transcurridos: -0.5 })))), 1);
});
test('Newman: ASSERT funcional y transporte separados', () => {
  const fallo = (name, testName) => ({ error: { name, test: testName }, source: { name: 'API-191-01' } });
  const assertion = fallosNewman({ run: { failures: [fallo('AssertionError','[TC-M03-191][ASSERT][API-191-01] panel y contrato')] } });
  const base = { paginas: [{ http: 200, eco: true, panel: { estado: 'RECHAZADO', motivo: 'sin panel' } }],
    artefactos: ['newman/newman-G98.json'], proceso: { status: 1 } };
  assert.equal(evaluarNewman({ ...base, fallos: assertion }).datos.estado, 'RECHAZADO');
  assert.deepEqual(evaluarNewman({ ...base, fallos: assertion }).problemasTecnicos, []);
  const divergente = evaluarNewman({ ...base, paginas: [{ ...base.paginas[0], panel: { estado: 'APROBADO', motivo: 'Panel acreditado' } }],
    fallos: assertion });
  assert.equal(divergente.datos.estado, 'NO_CONCLUYENTE');
  assert.deepEqual(divergente.problemasTecnicos, ['ORACULOS_DIVERGENTES']);
  const transporte = fallosNewman({ run: { failures: [fallo('Error','')] } });
  assert.deepEqual(evaluarNewman({ paginas: [], fallos: transporte, artefactos: [], proceso: { status: 1 } }).problemasTecnicos,
    ['SIN_REPORTE','NEWMAN_ERROR_SCRIPT_O_TRANSPORTE']);
  const paginaSinRespuesta = { http: null, eco: false, panel: null, activos_panel: [], sensores_alerta: [] };
  const corte = evaluarNewman({ paginas: [paginaSinRespuesta], fallos: transporte,
    artefactos: ['newman/newman-G98.json'], proceso: { status: 1 } });
  assert.equal(corte.datos.estado, 'NO_CONCLUYENTE');
  assert.equal(corte.elegida, undefined);
  assert.deepEqual(corte.problemasTecnicos, ['NEWMAN_ERROR_SCRIPT_O_TRANSPORTE']);
  const asercionTrasCorte = evaluarNewman({ paginas: [paginaSinRespuesta], fallos: [...assertion, ...transporte],
    artefactos: ['newman/newman-G98.json'], proceso: { status: 1 } });
  assert.equal(asercionTrasCorte.datos.estado, 'NO_CONCLUYENTE');
  assert.equal(asercionTrasCorte.elegida, undefined);
  const script = evaluarNewman({ ...base, fallos: fallosNewman({ run: { failures: [fallo('TypeError','')] } }) });
  assert.equal(script.datos.estado, 'NO_CONCLUYENTE');
  assert.equal(script.elegida, undefined);
  assert.deepEqual(script.problemasTecnicos, ['NEWMAN_ERROR_SCRIPT_O_TRANSPORTE']);
});
test('registro oficial V2 exige ASSERT, cierre, rollback e informe único', () => {
  const runId = 'RUN-G98-V2-20261031-120000';
  const evidencias = ['TC-M03-G98_reevaluacion_V2.md','resultado.json','newman/newman-G98.json','newman/newman-G98.html'];
  const r = { run_id: runId, version: 2, oficial: true, consume_version: true,
    casos: { 'TC-M03-191': { estado: 'APROBADO' } },
    comprobaciones: CAPACIDADES.comprobaciones_obligatorias['TC-M03-191'].API.map(id =>
      ({ caso: 'TC-M03-191', fuente: 'API', id, tipo: 'ASSERT', estado: 'APROBADO' })),
    cierre: { run: { cierre_http: 200 }, rollback: { verificado: true } }, cypress: { total_pruebas: 0 }, evidencias };
  assert.equal(clasificarRegistro(CAPACIDADES, r, new Set(evidencias), { runId, version: 2 }), true);
  assert.equal(clasificarRegistro(CAPACIDADES, { ...r, comprobaciones: r.comprobaciones.slice(1) }, new Set(evidencias), { runId, version: 2 }), false);
});
test('informe V2 conserva siete secciones y detalle por caso sin fuente interna', () => {
  const r = { version: 2, operacion: 'reevaluar', run_id: 'RUN-G98-V2-LOCAL', ambiente: 'LOOPBACK_LOCAL',
    autorizacion: 'AUT-LOCAL', oficial: false, preflight_herramientas: {},
    casos: { 'TC-M03-191': { estado: 'NO_CONCLUYENTE', motivo: 'Sin activo biológico vinculado' } },
    comprobaciones: [{ id: 'API-191-03', fuente: 'API', tipo: 'ASSERT', estado: 'NO_CONCLUYENTE',
      motivo: 'Sin activo biológico vinculado', evidencia: 'resultado.json' }],
    paginas: [], evidencias: ['resultado.json'], observaciones: [], problemas_tecnicos: [], bitacora: [],
    cierre: { run: { cierre_http: null }, rollback: { verificado: false, motivo: 'Sin cierre' } } };
  const texto = informe(r);
  for (let i = 1; i <= 7; i++) assert.match(texto, new RegExp(`## ${i}\\.`));
  assert.match(texto, /### TC-M03-191/);
  assert.match(texto, /NO VERIFICADO/);
  assert.match(texto, /semilla persistente QA-G98-PANEL: finca 184, área 702, dispositivo 789, sensores 1210\/1211\/1212, activo biológico 928/);
  assert.match(texto, /alertas se crean y revierten solo dentro del sandbox del RUN/);
  assert.doesNotMatch(texto, /matriz de QA/i);
  const reintento = informe({ ...r, operacion: 'reintentar', intento: 3 });
  assert.match(reintento, /Intento 3/);
  assert.match(reintento, /RUN-G98-V2-20261031-172140 \(no oficial\)/);
});
test('informe V3 explica el falso positivo V2 y separa incidencias del producto', () => {
  const r = { version: 3, operacion: 'reevaluar', run_id: 'RUN-G98-V3-LOCAL', ambiente: 'LOOPBACK_LOCAL',
    autorizacion: 'AUT-LOCAL', oficial: true, inicio: '2026-10-31T18:34:17.500Z',
    preflight_herramientas: { newman: { version: 'LOCAL' } },
    casos: { 'TC-M03-191': { estado: 'APROBADO', motivo: 'Comprobaciones acreditadas' } },
    comprobaciones: [{ id: 'API-191-01', fuente: 'API', estado: 'APROBADO',
      motivo: 'Panel acreditado', evidencia: 'newman/newman-G98.json' }],
    paginas: [{ unidad: 702, http: 200, eco: true, panel: { estado: 'APROBADO', motivo: 'Panel acreditado' } }],
    precondicion: { via: 'CREACION_SANDBOX', unidad: 702, total: 3, ids: [11, 12, 13], activo_vinculado: true },
    ids_creados: [11, 12, 13], evidencias: ['resultado.json', 'newman/newman-G98.json'],
    observaciones: ['minutos negativos por now() fijo del sandbox'], problemas_tecnicos: [], bitacora: [],
    cierre: { run: { cierre_http: 200 }, rollback: { verificado: true, motivo: '3 IDs ausentes' } } };
  const texto = informe(r);
  for (let i = 1; i <= 7; i++) assert.match(texto, new RegExp(`## ${i}\\.`));
  for (const seccion of ['Objetivo', 'Precondiciones', 'Pasos', 'Entradas', 'Esperado', 'Observado',
    'Decisión con porqué', 'Qué falta']) assert.match(texto, new RegExp(`\\*\\*${seccion}:`));
  assert.match(texto, /V1 → V2 → V3/);
  assert.match(texto, /INC-M03-191-G98-02: \*\*ANULADA\*\*/);
  assert.match(texto, /INC-M03-191-G98-01: \*\*CORREGIDA\*\*/);
  assert.match(texto, /indicadores_alertas_repository.py:70/);
  assert.match(texto, /generar_alerta_use_case.py:110/);
  assert.doesNotMatch(texto, /matriz de QA|\[[\s\S]*\{|minutos inválidos 0/i);
  assert.match(informe({ ...r, oficial: false }), /PENDIENTE DE CONFIRMACIÓN EN V3/);
});
