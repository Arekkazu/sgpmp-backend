import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { CAPACIDADES, CASOS, LIMITE, planTemporal, cuerpoAlerta, exigirAlertaNueva, escrituraPermitida, evaluarComprobacion, decidirCaso } from '../lib/g89_escenario.mjs';
import { crearTransporte, contextoSolicitud, leerEnv, consolidarNewman,
  compararDashboard, confirmarRollback, preflightLocal, evaluar } from '../g89.mjs';
import { informe, validarResultado, completarResultado } from '../lib/g89_presentacion.mjs';

function clasificarRegistro(r, capacidades) {
  const casos = Object.keys(capacidades.comprobaciones_obligatorias);
  const completas = casos.every((caso) => Object.entries(capacidades.comprobaciones_obligatorias[caso])
    .every(([fuente, ids]) => ids.every((id) => r.comprobaciones.some((c) =>
      c.caso === caso && c.fuente === fuente && c.id === id && c.tipo === 'ASSERT'
      && ['APROBADO', 'RECHAZADO'].includes(c.estado)))));
  return r.oficial === true && completas && casos.every((caso) => ['APROBADO', 'RECHAZADO'].includes(r.casos[caso].estado)
    && r.casos[caso].estado_tecnico === 'OK') && r.cierre.run.cierre_http === 200
    && r.cierre.rollback.verificado === true;
}

test('catálogo --capacidades: JSON del lanzador sin autorización ni .env', () => {
  const c = JSON.parse(JSON.stringify(CAPACIDADES));
  assert.equal(c.contrato, 'sigab-qa-ejecutor/1');
  assert.ok(c.operaciones.includes('evaluar') && c.operaciones.includes('reintentar'));
  assert.ok(c.versiones);
  assert.deepEqual(Object.keys(c.comprobaciones_obligatorias), CASOS);
  const ids = Object.values(c.comprobaciones_obligatorias).flatMap((fuentes) => {
    assert.ok(Object.keys(fuentes).every((fuente) => ['API', 'UI'].includes(fuente)));
    return Object.values(fuentes).flatMap((lista) => { assert.ok(Array.isArray(lista) && lista.length); return lista; });
  });
  assert.equal(ids.length, new Set(ids).size);
  assert.ok(ids.every((id) => /^[A-Za-z0-9_-]{1,100}$/.test(id)));
  assert.deepEqual(ids, ['API-173-01', 'API-174-01', 'API-174-02', 'API-174-03', 'API-174-04']);
});

test('plan temporal: ocho marcas anteriores al NOW fijo', () => {
  const p = planTemporal('2026-10-25T12:00:00.000Z');
  assert.equal(p.ancla, '2026-10-25T11:58:00.000Z');
  assert.deepEqual(p.marcas, ['2026-10-25T11:57:20.000Z', '2026-10-25T11:57:25.000Z',
    '2026-10-25T11:57:30.000Z', '2026-10-25T11:57:35.000Z',
    '2026-10-25T11:57:40.000Z', '2026-10-25T11:57:45.000Z',
    '2026-10-25T11:57:50.000Z', '2026-10-25T11:57:55.000Z']);
});

test('preflight local no necesita .env real', () => {
  const d = fs.mkdtempSync(path.join(os.tmpdir(), 'g89-env-'));
  try { assert.deepEqual(leerEnv({ raiz: d, proceso: { QA_AUTORIZADO: 'SI' } }), { QA_AUTORIZADO: 'SI' }); }
  finally { fs.rmSync(d, { recursive: true, force: true }); }
});

test('stub hasta primera petición: cabeceras y sin login dentro del RUN', async () => {
  const original = globalThis.fetch;
  const vistas = [];
  globalThis.fetch = async (_url, op) => {
    vistas.push(op);
    return { status: 200, headers: { get: () => 'G89-PRUEBA' }, text: async () => '{}' };
  };
  try {
    const t = crearTransporte({ base: 'http://local.invalid', runId: 'G89-PRUEBA', secreto: 'falso',
      bitacora: [], secretos: ['falso'] });
    t.abrir();
    await t.solicitar('GET', '/usuarios/me', { token: 'simulado' });
    assert.equal(vistas.length, 1);
    assert.equal(vistas[0].headers['X-Test-Run-Id'], 'G89-PRUEBA');
    assert.equal(vistas[0].headers['X-Sandbox-Secret'], 'falso');
    await assert.rejects(t.solicitar('POST', '/sesiones/', { cuerpo: {} }), /LOGIN_DENTRO_RUN_PROHIBIDO/);
    assert.equal(vistas.length, 1);
    assert.throws(() => contextoSolicitud({ abierto: true, token: 'x', enRun: false }), /CONTEXTO_MIXTO/);
  } finally { globalThis.fetch = original; }
});

test('lista blanca y límites de escritura', () => {
  const c = {};
  const ingesta = { device_id: 357, sensor_id: 552, tipo_variable: 'TEMPERATURA_AMBIENTAL', valor: 25 };
  for (let i = 0; i < LIMITE.ingestas; i++) escrituraPermitida('POST', '/iot/telemetria', ingesta, c);
  assert.throws(() => escrituraPermitida('POST', '/iot/telemetria', ingesta, c), /LIMITE_ESCRITURAS/);
  assert.throws(() => escrituraPermitida('POST', '/configuracion/sensores', ingesta, {}), /LISTA_BLANCA/);
  assert.throws(() => escrituraPermitida('POST', '/iot/alertas', { ...ingesta, sensor_id: 738 }, {}), /OTRA_SEMILLA/);
  assert.throws(() => escrituraPermitida('PATCH', '/iot/alertas/5/estado', { nuevo_estado: 'VENCIDA' }, {}), /NO_PREVISTA/);
  assert.throws(() => escrituraPermitida('PATCH', '/iot/alertas/5/estado', { nuevo_estado: 'DESCARTADA' }, {}), /NO_PREVISTA/);
  const permisos = { marcas: ['2026-10-25T11:57:45.000Z'], valores: [25],
    serial: 'SERIAL_LOCAL', eventos: [{ id: 11, valor: 31, marca: '2026-10-25T11:57:45.000Z' }],
    telemetrias: [11], alertas: [22] };
  assert.throws(() => escrituraPermitida('POST', '/iot/telemetria', { ...ingesta,
    timestamp_captura: '2026-10-25T11:58:00.000Z', serial: 'SERIAL_LOCAL' }, {}, permisos), /FUERA_ESCENARIO/);
  assert.throws(() => escrituraPermitida('POST', '/iot/alertas', { ...ingesta,
    access_key: 'SERIAL_LOCAL', severidad_edge: 'LEVE', id_telemetria: 99 }, {}, permisos), /FUERA_ESCENARIO/);
  const alerta = cuerpoAlerta({ serial: permisos.serial, severidad: 'LEVE',
    idTelemetria: 11, timestampEvento: permisos.marcas[0] });
  assert.doesNotThrow(() => escrituraPermitida('POST', '/iot/alertas', alerta, {}, permisos));
  assert.deepEqual(alerta.correlacion_variables, { HUMEDAD_RELATIVA: 40 });
  assert.throws(() => escrituraPermitida('POST', '/iot/alertas',
    { ...alerta, correlacion_variables: { HUMEDAD_RELATIVA: 41 } }, {}, permisos), /FUERA_ESCENARIO/);
  assert.throws(() => escrituraPermitida('POST', '/iot/alertas',
    { ...alerta, access_key: permisos.serial }, {}, permisos), /FUERA_ESCENARIO/);
  assert.throws(() => escrituraPermitida('POST', '/iot/alertas',
    { ...alerta, serial: 'OTRO_SERIAL' }, {}, permisos), /FUERA_ESCENARIO/);
  assert.throws(() => escrituraPermitida('POST', '/iot/alertas',
    { ...alerta, timestamp_evento: '2026-10-25T11:58:05.000Z' }, {}, permisos), /FUERA_ESCENARIO/);
  assert.throws(() => escrituraPermitida('POST', '/iot/alertas',
    { ...alerta, origen_evento: 'DESCONOCIDO' }, {}, permisos), /FUERA_ESCENARIO/);
  assert.throws(() => escrituraPermitida('PATCH', '/iot/alertas/23/estado',
    { nuevo_estado: 'RESUELTA', motivo: 'QA G89 RESUELTA' }, {}, permisos), /ALERTA_AJENA/);
});

test('POST broker y PATCH administrador: contrato, RUN y bitácora saneada', async () => {
  const original = globalThis.fetch;
  const vistas = []; const bitacora = [];
  globalThis.fetch = async (url, op) => {
    vistas.push({ url, op });
    return { status: op.method === 'POST' ? 201 : 200,
      headers: { get: () => 'G89-PRUEBA' }, text: async () => '{}' };
  };
  try {
    const t = crearTransporte({ base: 'http://local.invalid', runId: 'G89-PRUEBA',
      secreto: 'SECRETO_LOCAL', bitacora, secretos: ['SECRETO_LOCAL', 'BROKER_LOCAL', 'JWT_LOCAL'] });
    const ancla = '2026-10-25T11:58:00.000Z';
    t.configurarEscenario({ marcas: [], valores: [], serial: 'SERIAL_LOCAL',
      eventos: [{ id: 11, valor: 31, marca: ancla }], telemetrias: [11], alertas: [22] });
    t.abrir();
    const cuerpo = cuerpoAlerta({ serial: 'SERIAL_LOCAL', severidad: 'LEVE',
      idTelemetria: 11, timestampEvento: ancla });
    await t.solicitar('POST', '/iot/alertas', { token: 'BROKER_LOCAL', cuerpo });
    await t.solicitar('PATCH', '/iot/alertas/22/estado', { token: 'JWT_LOCAL',
      cuerpo: { nuevo_estado: 'EN_ATENCION', motivo: 'QA G89 EN_ATENCION' } });
    assert.deepEqual(JSON.parse(vistas[0].op.body), cuerpo);
    assert.equal(Object.hasOwn(cuerpo, 'access_key'), false);
    assert.equal(vistas[0].op.headers.Authorization, 'Bearer BROKER_LOCAL');
    assert.equal(vistas[1].op.headers.Authorization, 'Bearer JWT_LOCAL');
    assert.deepEqual(JSON.parse(vistas[1].op.body),
      { nuevo_estado: 'EN_ATENCION', motivo: 'QA G89 EN_ATENCION' });
    for (const v of vistas) {
      assert.equal(v.op.headers['X-Test-Run-Id'], 'G89-PRUEBA');
      assert.equal(v.op.headers['X-Sandbox-Secret'], 'SECRETO_LOCAL');
    }
    assert.doesNotMatch(JSON.stringify(bitacora), /BROKER_LOCAL|JWT_LOCAL|SECRETO_LOCAL|SERIAL_LOCAL/);
  } finally { globalThis.fetch = original; }
});

test('deduplicación de 30 minutos: cierres permiten 173→174 y duplicado falla explícitamente', () => {
  const alertas = []; let siguiente = 40; const ahora = Date.parse('2026-10-25T12:00:00.000Z');
  const generar = (severidad) => {
    const previa = alertas.find((a) => a.sensor === 552 && a.variable === 'TEMPERATURA_AMBIENTAL'
      && ['ACTIVA', 'EN_ATENCION'].includes(a.estado) && a.fecha >= ahora - 30 * 60_000);
    if (previa) return { status: 201, json: { es_duplicado: true, id_alerta: previa.id,
      alerta_existente_id: previa.id } };
    const a = { id: ++siguiente, sensor: 552, variable: 'TEMPERATURA_AMBIENTAL',
      severidad, estado: 'ACTIVA', fecha: ahora }; alertas.push(a);
    return { status: 201, json: { es_duplicado: false, id_alerta: a.id, severidad } };
  };
  const critica = exigirAlertaNueva(generar('CRITICO'), 'CRITICO');
  assert.equal(alertas[0].estado, 'ACTIVA');
  assert.throws(() => exigirAlertaNueva(generar('LEVE'), 'LEVE'), /ALERTA_DUPLICADA_LEVE_ID_EXISTENTE_41/);
  alertas[0].estado = 'EN_ATENCION'; alertas[0].estado = 'RESUELTA';
  assert.equal(alertas[0].id, critica);
  const leve = exigirAlertaNueva(generar('LEVE'), 'LEVE');
  alertas[1].estado = 'EN_ATENCION'; alertas[1].estado = 'RESUELTA';
  const moderada = exigirAlertaNueva(generar('MODERADO'), 'MODERADO');
  assert.notEqual(moderada, leve);
  assert.equal(alertas[2].estado, 'ACTIVA');
});

test('sin pausa fija y decisiones independientes por caso', () => {
  const ejecutor = fs.readFileSync(new URL('../g89.mjs', import.meta.url), 'utf8');
  assert.doesNotMatch(ejecutor, /pausa\(|setTimeout\(|31_000/);
  const estado173 = decidirCaso({ comprobaciones: [], errorTecnico: 'ALERTA_DUPLICADA_CRITICO' });
  const estado174 = decidirCaso({ comprobaciones: [{ cumple: true }] });
  assert.equal(estado173.veredicto, null);
  assert.equal(estado174.veredicto, 'APROBADO');
});

test('oráculos 173 y 174: crítico, activa, resuelta, descartada y elevación indebida', () => {
  const estado = (semaforo, id_alerta = null) => ({ sensores: [{ id_sensor: 552, estado_semaforo: semaforo, id_alerta, ultimo_valor: 25 }] });
  assert.equal(evaluarComprobacion(CASOS[0], 'critica', estado('ROJO', 41), 41).cumple, true);
  assert.equal(evaluarComprobacion(CASOS[0], 'critica', estado('ROJO', 42), 41).cumple, false);
  assert.equal(evaluarComprobacion(CASOS[1], 'noCriticaActiva', estado('AMARILLO', 42)).cumple, true);
  assert.equal(evaluarComprobacion(CASOS[1], 'resuelta', estado('VERDE')).cumple, true);
  assert.equal(evaluarComprobacion(CASOS[1], 'descartada', estado('VERDE')).cumple, true);
  assert.equal(evaluarComprobacion(CASOS[1], 'resuelta', estado('AMARILLO')).cumple, false);
  assert.equal(evaluarComprobacion(CASOS[1], 'resuelta', estado('VERDE', 42)).cumple, false);
  assert.equal(evaluarComprobacion(CASOS[1], 'descartada', estado('AMARILLO', 42)).cumple, false);
});

test('veredicto funcional separado del estado técnico', () => {
  assert.deepEqual(decidirCaso({ comprobaciones: [{ cumple: true }] }), { veredicto: 'APROBADO', estado_tecnico: 'OK' });
  assert.deepEqual(decidirCaso({ comprobaciones: [{ cumple: false }] }), { veredicto: 'RECHAZADO', estado_tecnico: 'OK' });
  assert.equal(decidirCaso({ comprobaciones: [{ cumple: false }], errorTecnico: 'timeout' }).veredicto, null);
  assert.equal(decidirCaso({ comprobaciones: [], prerequisitos: ['semilla'] }).estado_tecnico, 'NO_CONCLUYENTE');
});

test('informe y resultado coherentes; rollback exige GET y enlaces existentes', () => {
  const padre = fs.mkdtempSync(path.join(os.tmpdir(), 'g89-informe-'));
  const dir = path.join(padre, 'RUN-G89-V1-20261025-120000');
  fs.mkdirSync(path.join(dir, 'newman'), { recursive: true });
  try {
    fs.writeFileSync(path.join(dir, 'newman', 'x.json'), '{}');
    fs.writeFileSync(path.join(dir, 'resultado.json'), '{}');
    const r = { grupo: 'G89', rf: 'RF-58', ejecucion: { run_id: path.basename(dir), version: 1,
      ambiente: 'TEST', autorizacion: 'PRUEBA_LOCAL', operacion: 'evaluar', commit: 'NO_VERIFICADO',
      inicio: 'x', fin: 'x' }, casos: Object.fromEntries(CASOS.map((id) => [id, {
      veredicto: null, estado_tecnico: 'NO_EJECUTADA', comprobaciones: [], prerequisitos: [] }])),
    semilla: null, plan_temporal: null, newman: [], bitacora: [], evidencias: ['resultado.json', 'newman/x.json'],
    telemetrias_creadas: [], alertas_creadas: [], hallazgos: [], problemas_tecnicos: [], cierre: { http: 200, rollback_verificado: false,
      comprobaciones: [{ tipo: 'dashboard_previo', http: 500, coincide: false }], motivo: 'No confirmado' },
    estado: 'NO_CONCLUYENTE' };
    completarResultado(r, dir);
    fs.writeFileSync(path.join(dir, 'TC-M03-G89_resultado.md'), informe(r));
    assert.match(fs.readFileSync(path.join(dir, 'TC-M03-G89_resultado.md'), 'utf8'), /NO CONFIRMADO/);
    validarResultado(r, dir);
    r.cierre.rollback_verificado = true;
    completarResultado(r, dir);
    assert.throws(() => validarResultado(r, dir), /ROLLBACK_SIN_COMPROBACION/);
    r.cierre.rollback_verificado = false;
    r.casos[CASOS[0]].veredicto = 'APROBADO';
    completarResultado(r, dir);
    assert.throws(() => validarResultado(r, dir), /APROBACION_SIN_EVIDENCIA/);
  } finally { fs.rmSync(padre, { recursive: true, force: true }); }
});

test('registro local: RUN completo e incompleto, sin crear artefactos de grupo', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'RUN-G89-V1-'));
  const runId = path.basename(dir);
  try {
    fs.mkdirSync(path.join(dir, 'newman'));
    fs.mkdirSync(path.join(dir, 'api'));
    fs.writeFileSync(path.join(dir, 'resultado.json'), '{}');
    fs.writeFileSync(path.join(dir, 'newman', 'newman-TC-M03-G89.json'), '{}');
    fs.writeFileSync(path.join(dir, 'newman', 'newman-TC-M03-G89.html'), '<html></html>');
    const casos = Object.fromEntries(CASOS.map((id) => [id, {
      veredicto: 'APROBADO', estado_tecnico: 'OK', comprobaciones: [], prerequisitos: [] }]));
    const ids = { 'TC-M03-173': ['API-173-01'],
      'TC-M03-174': ['API-174-01', 'API-174-02', 'API-174-03', 'API-174-04'] };
    for (const caso of CASOS) for (const id of ids[caso]) {
      const evidencia = `api/${id}.json`;
      fs.writeFileSync(path.join(dir, evidencia), '{}');
      casos[caso].comprobaciones.push({ id_comprobacion: id, cumple: true,
        http: 200, evidencia, observado: { estado_semaforo: 'VERDE' } });
    }
    const r = { grupo: 'G89', ejecucion: { run_id: runId, version: 1 }, casos,
      telemetrias_creadas: [101], alertas_creadas: [201],
      newman: [{ archivo: 'newman/newman-TC-M03-G89.json' }],
      evidencias: ['resultado.json', 'newman/newman-TC-M03-G89.json',
        'newman/newman-TC-M03-G89.html', ...Object.values(ids).flat().map((id) => `api/${id}.json`)],
      cierre: { http: 200, rollback_verificado: true,
        comprobaciones: [
          { tipo: 'dashboard_previo', http: 200, previo_completo: true,
            posterior_completo: true, coincide: true },
          { tipo: 'alerta_ausente', id_alerta: 201, http: 404, coincide: true },
          { tipo: 'telemetrias_ausentes', http: 200, completo: true,
            total_ids: 1, coincide: true }] } };
    const capacidades = JSON.parse(JSON.stringify(CAPACIDADES));
    completarResultado(r, dir);
    assert.equal(clasificarRegistro(r, capacidades), true);
    assert.equal(r.oficial, true);
    assert.equal(r.casos['TC-M03-173'].estado, 'APROBADO');
    assert.deepEqual(r.datos.ids_telemetria, [101]);
    assert.equal(r.consume_version, true);
    assert.ok(r.evidencias.every((archivo) => !archivo.includes('..') && fs.existsSync(path.join(dir, archivo))));
    r.casos['TC-M03-174'].veredicto = null;
    r.casos['TC-M03-174'].estado_tecnico = 'NO_CONCLUYENTE';
    completarResultado(r, dir);
    assert.equal(clasificarRegistro(r, capacidades), false);
    assert.equal(r.oficial, false);
    assert.equal(r.casos['TC-M03-174'].estado, 'NO_CONCLUYENTE');
    r.casos['TC-M03-174'].veredicto = 'RECHAZADO';
    r.casos['TC-M03-174'].estado_tecnico = 'OK';
    r.casos['TC-M03-174'].comprobaciones[0].cumple = false;
    completarResultado(r, dir);
    assert.equal(r.comprobaciones.find((c) => c.id === 'API-174-01').estado, 'RECHAZADO');
    assert.equal(clasificarRegistro(r, capacidades), true);
  } finally { fs.rmSync(dir, { recursive: true, force: true }); }
});

test('HTML Newman consolidado conserva nombres de solicitudes y aserciones', () => {
  const d = fs.mkdtempSync(path.join(os.tmpdir(), 'g89-newman-html-'));
  try {
    fs.mkdirSync(path.join(d, 'newman'));
    const archivo = 'newman/newman-TC-M03-173-01.json';
    fs.writeFileSync(path.join(d, archivo), JSON.stringify({ run: { executions: [{
      item: { name: 'Dashboard G89' }, request: { method: 'GET' }, response: { code: 200 },
      assertions: [{ assertion: 'Semáforo esperado' }, { assertion: 'Eco RUN' }] }] } }));
    const r = { newman: [{ caso: 'TC-M03-173', check_id: 'API-173-01', archivo,
      http: 200, aserciones: 2, fallos: [], ejecuciones: 1 }], evidencias: [] };
    consolidarNewman(r, d);
    const html = fs.readFileSync(path.join(d, 'newman', 'newman-TC-M03-G89.html'), 'utf8');
    assert.match(html, /Dashboard G89/);
    assert.match(html, /Semáforo esperado/);
    assert.match(html, /Eco RUN/);
    assert.deepEqual(r.evidencias, ['newman/newman-TC-M03-G89.html']);
  } finally { fs.rmSync(d, { recursive: true, force: true }); }
});

test('rollback compara ausencia o presencia con respuestas completas y todas las creaciones', () => {
  const respuesta = (sensores, total = sensores.length) => ({
    status: 200, json: { sensores, total, pagina: 1, por_pagina: 50 } });
  const ausente = compararDashboard(respuesta([]), respuesta([]));
  assert.equal(ausente.coincide, true);
  assert.equal(ausente.sensor_previo_presente, false);
  assert.equal(ausente.sensor_posterior_presente, false);
  const base = { http: 200, comprobaciones: [ausente,
    { tipo: 'alerta_ausente', id_alerta: 295, http: 404, coincide: true },
    { tipo: 'telemetrias_ausentes', http: 200, completo: true, total_ids: 1, coincide: true }] };
  assert.equal(confirmarRollback(base, [295], [117075]), true);
  assert.equal(confirmarRollback({ ...base, http: 500 }, [295], [117075]), false);
  assert.equal(confirmarRollback(base, [295, 296], [117075]), false);
  assert.equal(confirmarRollback(base, [295], [117075, 117076]), false);
  assert.equal(confirmarRollback({ ...base, comprobaciones: [ausente] }, [], []), true);
  const sensor = { id_sensor: 552, estado_semaforo: 'VERDE', id_alerta: null, ultimo_valor: 25 };
  assert.equal(compararDashboard(respuesta([sensor]), respuesta([sensor])).coincide, true);
  assert.equal(compararDashboard(respuesta([]), respuesta([sensor])).coincide, false);
  assert.equal(compararDashboard(respuesta([{ id_sensor: 1, estado_semaforo: 'VERDE' }]),
    respuesta([{ id_sensor: 1, estado_semaforo: 'AMARILLO' }])).coincide, false);
  assert.equal(compararDashboard(respuesta([], 51), respuesta([])).coincide, false);
  assert.equal(compararDashboard(respuesta([]), respuesta([], 1)).coincide, false);
  assert.equal(confirmarRollback({ ...base, comprobaciones: [
    ausente, { tipo: 'alerta_ausente', id_alerta: 295, http: 200, coincide: false },
    base.comprobaciones[2]] }, [295], [117075]), false);
  assert.equal(confirmarRollback({ ...base, comprobaciones: [
    ausente, base.comprobaciones[1],
    { ...base.comprobaciones[2], coincide: false }] }, [295], [117075]), false);
  assert.equal(confirmarRollback({ ...base, comprobaciones: [
    ausente, base.comprobaciones[1],
    { ...base.comprobaciones[2], completo: false }] }, [295], [117075]), false);
});

test('preflight local se escribe antes de peticiones y no contiene valores sensibles', async () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'g89-pre-'));
  const dir = path.join(root, 'RUN-G89-V1-20261025-120000');
  fs.mkdirSync(dir);
  const contrato = { runId: path.basename(dir), directorio: dir, operacion: 'evaluar',
    version: 1, intento: 2, referencia: 'LOCAL', contexto: { casos: CASOS } };
  const valores = Object.fromEntries(['SIGAB_API_TEST_BASE', 'QA_SANDBOX_SECRET',
    'QA_ADMIN_EMAIL', 'QA_ADMIN_PASSWORD', 'QA_PROD_EMAIL', 'QA_PROD_PASSWORD',
    'BROKER_SERVICE_TOKEN', 'QA_G88_169_171_SERIAL'].map((x) => [x, 'MARCADOR_SECRETO']));
  valores.SIGAB_API_TEST_BASE = 'http://local.invalid';
  valores.QA_AUTORIZADO = 'SI';
  try {
    const local = preflightLocal(contrato, valores);
    assert.equal(local.resultado.ok, true);
    assert.equal(local.resultado.fase, 'PREFLIGHT_LOCAL');
    assert.deepEqual(local.resultado.casos, CASOS);
    assert.equal(local.resultado.plan_temporal.calculable, true);
    assert.equal(local.resultado.lista_blanca.length, 4);
    assert.doesNotMatch(JSON.stringify(local.resultado), /MARCADOR_SECRETO/);
    let peticiones = 0;
    const previo = globalThis.fetch;
    globalThis.fetch = () => { peticiones++; throw new Error('RED_PROHIBIDA'); };
    try {
      assert.equal(await evaluar(contrato, { valores: { ...valores, QA_AUTORIZADO: '' } }), 2);
    } finally { globalThis.fetch = previo; }
    const p = JSON.parse(fs.readFileSync(path.join(dir, 'preflight.json'), 'utf8'));
    assert.equal(p.ok, false);
    assert.ok(p.barreras.includes('QA_AUTORIZADO_AUSENTE'));
    assert.equal(peticiones, 0);
  } finally { fs.rmSync(root, { recursive: true, force: true }); }
});

test('informe temporal del RUN oficial consolida 174 y separa incidencias QA', () => {
  const run = path.dirname(fileURLToPath(new URL('../Resultados/RUN-G89-V1-20261025-045219/resultado.json', import.meta.url)));
  const temporal = fs.mkdtempSync(path.join(os.tmpdir(), 'g89-informe-historico-'));
  try {
  fs.copyFileSync(path.join(run, 'resultado.json'), path.join(temporal, 'resultado.json'));
  const original = JSON.parse(fs.readFileSync(path.join(temporal, 'resultado.json'), 'utf8'));
  const copia = structuredClone(original);
  // Ejercitar las ramas técnicas con una variante temporal; la evidencia oficial permanece intacta.
  copia.cierre.rollback_verificado = false;
  copia.evidencias = copia.evidencias.filter((archivo) => archivo !== 'preflight.json');
  const md = informe(copia);
  assert.equal((md.match(/^## Incidencias$/gm) ?? []).length, 1);
  assert.equal((md.match(/^### INC-G89-174-01/gm) ?? []).length, 1);
  assert.match(md, /LEVE a RESUELTA/);
  assert.match(md, /MODERADO a DESCARTADA/);
  assert.match(md, /alerta 299/);
  assert.match(md, /alerta 300/);
  for (const archivo of ['newman-TC-M03-174-05.json', 'newman-TC-M03-174-08.json'])
    assert.match(md, new RegExp(archivo.replaceAll('.', '\\.')));
  for (const campo of ['Contexto funcional', 'Precondiciones', 'Pasos y escenarios',
    'Esperado y fundamento', 'Observado', 'Requisito incumplido', 'Evidencia',
    'Impacto', 'Severidad', 'Certeza', 'Equipo inicial', 'Análisis técnico',
    'Acción correctiva', 'Criterio de aceptación', 'Estado actual'])
    assert.ok(md.includes('**' + campo + ':**'), campo);
  assert.doesNotMatch(md, /Reproducir y revisar|Discrepancia funcional comprobada|Primera discrepancia/);
  assert.match(md, /### Automatización QA/);
  assert.match(md, /Rollback no concluyente/);
  assert.match(md, /Preflight ausente/);
  for (const archivo of original.evidencias) assert.ok(fs.existsSync(path.join(run, archivo)));
  for (const [, archivo] of md.matchAll(/\]\((newman\/[^)]+)\)/g))
    assert.ok(fs.existsSync(path.join(run, archivo)), archivo);
  } finally { fs.rmSync(temporal, { recursive: true, force: true }); }
});
