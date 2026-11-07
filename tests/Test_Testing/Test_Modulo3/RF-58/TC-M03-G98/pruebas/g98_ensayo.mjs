#!/usr/bin/env node
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import http from 'node:http';
import { evaluar } from '../g98.mjs';
import { clasificarRegistro } from './registro_qa.mjs';
import { CAPACIDADES } from '../lib/g98_escenario.mjs';

const MODOS = [
  ['creacion_correcta', 'APROBADO', true, 3],
  ['post_422', 'NO_CONCLUYENTE', false, 1],
  ['post_duplicado', 'NO_CONCLUYENTE', false, 1],
  ['sin_activo', 'BLOQUEADO', false, 0],
  ['sin_sensores', 'BLOQUEADO', false, 0],
  ['historial_422', 'NO_CONCLUYENTE', false, 0],
  ['rollback_activa', 'NO_CONCLUYENTE', false, 3],
];
const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'g98-v2-ensayo-'));
const responder = (res, code, body, run) => {
  res.writeHead(code, { 'Content-Type': 'application/json', 'X-Test-Run-Id': run ?? '' });
  res.end(JSON.stringify(body));
};
const grados = ['CRITICO', 'MODERADO', 'LEVE'];
const variables = ['pH del agua', 'Amoniaco (NH3)', 'Temperatura Corporal'];
const codigos = ['PH_AGUA', 'NH3', 'TEMPERATURA_CORPORAL'];
const filtrosHistorial = ['tipo_variable', 'sensor_id', 'id_infraestructura', 'especie', 'estado_dato',
  'categoria_variable', 'id_activo_biologico', 'origen_dato'];
const combinacionesValidas = new Set(['', 'tipo_variable', 'sensor_id', 'id_infraestructura', 'especie',
  'id_infraestructura,tipo_variable', 'especie,tipo_variable', 'estado_dato,sensor_id',
  'categoria_variable,id_infraestructura', 'id_activo_biologico']);
async function simular(modo) {
  const estado = { alertas: [], posts: 0, borrado: false, nowFijo: Date.now() - 1000 };
  const server = http.createServer(async (req, res) => {
    const url = new URL(req.url, 'http://127.0.0.1');
    const run = req.headers['x-test-run-id'];
    const ruta = url.pathname;
    if (ruta === '/sesiones/' && req.method === 'POST') return responder(res, 200, { token: 'TOKEN_SINTETICO' });
    if (ruta === '/configuracion/fincas') return responder(res, 200, { items: [{ id_finca: 1 }, { id_finca: 80 }, { id_finca: 184 }] }, run);
    if (ruta === '/configuracion/infraestructuras') return responder(res, 200,
      { items: [{ id_infraestructura: url.searchParams.get('finca_id') === '184' ? 702 : Number(url.searchParams.get('finca_id')) }] }, run);
    if (ruta === '/configuracion/dispositivos-iot') return responder(res, 200, { items: [{ id_dispositivo_iot: 789,
      id_infraestructura: 702, serial: 'SERIAL_SINTETICO_SOLO_LOCAL', es_activo: true }] }, run);
    if (ruta === '/activos-biologicos') return responder(res, 200, { total_registros: modo === 'sin_activo' ? 0 : 1,
      registros: modo === 'sin_activo' ? [] : [{ id_activo_biologico: 928, id_infraestructura: 702 }] }, run);
    if (ruta === '/configuracion/dispositivos-iot/789/sensores') return responder(res, 200, { items: modo === 'sin_sensores' ? []
      : [1210, 1211, 1212].map(id_sensores => ({ id_sensores, id_dispositivo_iot: 789, es_activo: true })) }, run);
    if (ruta === '/iot/monitoreo/historial') {
      const filtros = filtrosHistorial.filter(x => url.searchParams.has(x)).sort().join(',');
      if (!url.searchParams.has('fecha_inicio') || !url.searchParams.has('fecha_fin')
        || !combinacionesValidas.has(filtros))
        return responder(res, 422, { error_code: 'COMBINACION_FILTROS_INVALIDA' }, run);
      if (modo === 'historial_422') return responder(res, 422, { error_code: 'HISTORIAL_LOCAL' }, run);
      const id = Number(url.searchParams.get('sensor_id'));
      const i = id - 1210;
      return responder(res, 200, { items: i >= 0 && i < 3 ? [{ id_telemetria: 51+i,
        id_sensor: id, id_infraestructura: 702, id_activo_biologico: 928, tipo_variable: variables[i] }] : [] }, run);
    }
    if (ruta === '/iot/alertas' && req.method === 'POST') {
      estado.posts++;
      let raw = ''; for await (const chunk of req) raw += chunk;
      const cuerpo = JSON.parse(raw);
      if (!run || req.headers['x-sandbox-secret'] !== 'ENSAYO_SECRET'
        || req.headers.authorization !== 'Bearer TOKEN_BROKER_SINTETICO'
        || ![51, 52, 53].includes(cuerpo.id_telemetria)
        || cuerpo.sensor_id !== cuerpo.id_telemetria + 1159
        || cuerpo.device_id !== 789 || cuerpo.tipo_variable !== codigos[cuerpo.sensor_id - 1210])
        return responder(res, 401, { error: 'CABECERAS_O_RELACION' }, run);
      if (modo === 'post_422') return responder(res, 422, { error: 'SEMILLA_LOCAL' }, run);
      if (modo === 'post_duplicado') return responder(res, 201, { es_duplicado: true,
        id_alerta: 99, severidad: cuerpo.severidad_edge }, run);
      const i = estado.alertas.length;
      const alerta = { id_alerta: 11+i, id_sensor: cuerpo.sensor_id, id_activo_biologico: 928,
        identificador_activo: 'ACTIVO_SINTETICO', estado_alerta: 'ACTIVA', tipo_alerta: 'UMBRAL',
        tipo_variable: cuerpo.tipo_variable, severidad: cuerpo.severidad_edge, id_infraestructura: 702,
        fecha_generacion: new Date().toISOString(), minutos_transcurridos: null };
      alerta.minutos_transcurridos = Math.floor((estado.nowFijo - Date.parse(alerta.fecha_generacion)) / 60000);
      estado.alertas.push(alerta);
      return responder(res, 201, { es_duplicado: false, id_alerta: alerta.id_alerta,
        severidad: alerta.severidad }, run);
    }
    if (ruta === '/iot/alertas' && req.method === 'GET') {
      const xs = estado.borrado ? (modo === 'rollback_activa' ? estado.alertas.slice(0, 1) : []) : estado.alertas;
      return responder(res, 200, { total: xs.length, items: xs }, run);
    }
    if (/^\/iot\/alertas\/\d+$/.test(ruta)) {
      const id = Number(ruta.split('/').at(-1));
      const alerta = estado.alertas.find(x => x.id_alerta === id);
      if (!alerta || (estado.borrado && !(modo === 'rollback_activa' && id === 11)))
        return responder(res, 404, { error: 'NO_EXISTE' }, run);
      return responder(res, 200, alerta, run);
    }
    if (ruta === '/iot/monitoreo/dashboard/702') {
      const canario = url.searchParams.get('por_pagina') === '1';
      return responder(res, 200, { total: 3, pagina: 1, por_pagina: canario ? 1 : 50,
        sensores: [{ id_sensor: 1210, id_alerta: estado.alertas[0]?.id_alerta,
          severidad_alerta: 'CRITICO', estado_semaforo: 'ROJO', dato_desactualizado: false, sin_umbral: false }],
        panel_alertas_activas: { total: estado.alertas.length, alertas: estado.alertas },
        resumen_unidades: [{ id_infraestructura: 702, alertas_activas_count: estado.alertas.length }] }, run);
    }
    if (ruta.startsWith('/test-control/runs/') && req.method === 'DELETE') {
      estado.borrado = true; return responder(res, 200, { ok: true });
    }
    responder(res, 404, { error: 'RUTA_LOCAL' }, run);
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  return { server, estado };
}
try {
  let bien = 0;
  for (const [modo, esperado, oficial, posts] of MODOS) {
    const { server, estado } = await simular(modo);
    try {
      const invalida = await fetch(`http://127.0.0.1:${server.address().port}/iot/monitoreo/historial?fecha_inicio=2026-01-01&fecha_fin=2026-01-02&sensor_id=1210&id_infraestructura=702`);
      if (invalida.status !== 422 || (await invalida.json()).error_code !== 'COMBINACION_FILTROS_INVALIDA')
        throw Error('ENSAYO_ACEPTO_COMBINACION_INVALIDA');
      const salida = path.join(temp, modo); fs.mkdirSync(salida);
      const runId = `ENSAYO-G98-20261031-120000-${modo}`;
      const c = { runId, version: 2, operacion: 'reevaluar', referencia: 'AUT-ENSAYO-LOCAL', directorio: salida };
      const env = { QA_AUTORIZADO: 'SI', SIGAB_API_TEST_BASE: `http://127.0.0.1:${server.address().port}`,
        QA_SANDBOX_SECRET: 'ENSAYO_SECRET', QA_PROD_EMAIL: 'productor@example.test', QA_PROD_PASSWORD: 'ENSAYO_PASS',
        BROKER_SERVICE_TOKEN: 'TOKEN_BROKER_SINTETICO' };
      const r = await evaluar(c, { env, ensayo: true });
      const presentes = new Set(r.evidencias.filter(x => fs.existsSync(path.join(salida, x))));
      const registro = clasificarRegistro(CAPACIDADES, r, presentes, { runId, version: 2 });
      if (r.casos['TC-M03-191'].estado !== esperado || r.oficial !== oficial || registro !== oficial
        || estado.posts !== posts || (modo === 'creacion_correcta' && (r.ids_creados.length !== 3
          || r.precondicion?.unidad !== 702 || r.unidades[0] !== 702))
        || (modo === 'historial_422' && (!r.problemas_tecnicos.includes('HISTORIAL_HTTP_422_HISTORIAL_LOCAL')
          || !r.observaciones.some(x => /historial HTTP 422, código HISTORIAL_LOCAL/.test(x))))
        || (modo === 'rollback_activa' && r.cierre.rollback.verificado)
        || (modo === 'creacion_correcta' && (!r.observaciones.some(x => /minutos negativos por now\(\) fijo/.test(x))
          || !estado.alertas.every(x => x.minutos_transcurridos === -1))))
        throw Error(`${modo}: ${JSON.stringify({ caso: r.casos['TC-M03-191'], oficial: r.oficial,
          registro, posts: estado.posts, rollback: r.cierre.rollback, tecnicos: r.problemas_tecnicos })}`);
      console.log(`${modo} ${esperado} POST=${estado.posts} rollback=${r.cierre.rollback.verificado}`); bien++;
    } finally { await new Promise(resolve => server.close(resolve)); }
  }
  console.log(`G98 Newman loopback ${bien}/${MODOS.length}`);
} finally {
  if (!path.resolve(temp).startsWith(path.resolve(os.tmpdir()) + path.sep)) throw Error('TEMP_FUERA_RAIZ');
  fs.rmSync(temp, { recursive: true, force: true });
}
