#!/usr/bin/env node
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import http from 'node:http';
import { fileURLToPath } from 'node:url';
import { CAPACIDADES, CASOS } from '../lib/g120_escenario.mjs';
import { contextoEjecucion } from '../lib/contrato_ejecutor.mjs';
import { contieneMojibake } from '../lib/seguridad.mjs';
import { evaluar, informe as crearInforme } from '../g120.mjs';
import { clasificarRegistro } from './registro_qa.mjs';

const MODOS = [
  ['aprobado', ['APROBADO', 'APROBADO', 'APROBADO'], true],
  ['semilla_dashboard_verde', ['APROBADO', 'APROBADO', 'APROBADO'], true],
  ['semilla_dashboard_reciente', ['APROBADO', 'APROBADO', 'APROBADO'], true],
  ['intento2_dashboard', ['APROBADO', 'APROBADO', 'APROBADO'], true],
  ['intento3_sin_lecturas_recientes', ['APROBADO', 'APROBADO', 'APROBADO'], true],
  ['unidad_timeout_continua', ['APROBADO', 'APROBADO', 'APROBADO'], true],
  ['sin_valor_seguro', ['BLOQUEADO', 'BLOQUEADO', 'BLOQUEADO'], false],
  ['busqueda_acotada', ['NO_CONCLUYENTE', 'NO_CONCLUYENTE', 'NO_CONCLUYENTE'], false],
  ['rf60_activo_recurso', ['APROBADO', 'APROBADO', 'APROBADO'], true],
  ['timestamp_alterado', ['RECHAZADO', 'APROBADO', 'APROBADO'], true],
  ['duplicado', ['APROBADO', 'RECHAZADO', 'APROBADO'], true],
  ['origen_incorrecto', ['RECHAZADO', 'APROBADO', 'APROBADO'], true],
  ['sync_invalido', ['APROBADO', 'APROBADO', 'APROBADO'], true],
  ['sync_ausente', ['APROBADO', 'APROBADO', 'APROBADO'], true],
  ['auditoria_denegada', ['APROBADO', 'APROBADO', 'APROBADO'], true],
  ['todo_rechazado_cuerpo', ['NO_CONCLUYENTE', 'NO_CONCLUYENTE', 'NO_CONCLUYENTE'], false],
  ['rechazo_por_antiguedad_23h', ['APROBADO', 'APROBADO', 'RECHAZADO'], true],
  ['contraste_404', ['NO_CONCLUYENTE', 'APROBADO', 'APROBADO'], false],
  ['contraste_error_tiempo', ['NO_CONCLUYENTE', 'APROBADO', 'APROBADO'], false],
  ['contraste_existente', ['APROBADO', 'APROBADO', 'APROBADO'], true],
  ['error5xx', ['APROBADO', 'APROBADO', 'BLOQUEADO'], false],
  ['sin_semilla', ['BLOQUEADO', 'BLOQUEADO', 'BLOQUEADO'], false],
  ['contrato_inesperado', ['NO_CONCLUYENTE', 'NO_CONCLUYENTE', 'NO_CONCLUYENTE'], false],
  ['sin_eco', ['NO_CONCLUYENTE', 'NO_CONCLUYENTE', 'NO_CONCLUYENTE'], false],
];
const dir = path.dirname(fileURLToPath(import.meta.url));
const raiz = path.resolve(dir, '..');
const temporal = fs.mkdtempSync(path.join(os.tmpdir(), 'g120-ensayo-'));
const enviar = (res, code, body, run, eco = true) => {
  res.writeHead(code, { 'Content-Type': 'application/json', ...(run && eco ? { 'X-Test-Run-Id': run } : {}) });
  res.end(JSON.stringify(body));
};
const leer = req => new Promise(resolve => {
  let b = ''; req.on('data', x => { b += x; }); req.on('end', () => { try { resolve(JSON.parse(b)); } catch { resolve(null); } });
});
async function servidor(modo) {
  const escritos = new Map();
  const dashboardPrimero = ['intento2_dashboard', 'busqueda_acotada', 'unidad_timeout_continua'].includes(modo);
  const semilla = { id_dispositivo_iot: 37, id_infraestructura: dashboardPrimero ? 268
    : modo === 'intento3_sin_lecturas_recientes' ? 1 : 9,
    serial: 'SERIAL_SINTETICO', categoria: 'SENSOR', es_activo: true };
  const vacios = Array.from({ length: dashboardPrimero ? 182 : modo === 'rf60_activo_recurso' ? 12 : 0 }, (_, i) =>
    ({ id_dispositivo_iot: 1000 + i, id_infraestructura: 500 + i, serial: `SINTETICO_${i}`,
      categoria: dashboardPrimero && i < 5 ? 'CAMARA' : 'SENSOR', es_activo: true }));
  const sensor = { id_sensores: 73, id_dispositivo_iot: 37, es_activo: true };
  const base = { id_telemetria: 1, id_sensor: 73, id_variable: 8,
    tipo_variable: 'Temperatura Ambiental', unidad_medida: '°C',
    valor: modo === 'intento3_sin_lecturas_recientes' ? 22 : 25, estado_calidad: 'LECTURA_VALIDA', estado_semaforo_historico: 'VERDE',
    ...(modo === 'intento3_sin_lecturas_recientes' ? { valor_min_umbral: 20, valor_max_umbral: 30 } : {}),
    timestamp_captura: new Date(Date.now() - (modo === 'intento3_sin_lecturas_recientes' ? 120 * 86400000 : 1800000)).toISOString(),
    origen_dato: modo === 'contraste_existente' ? 'TIEMPO_REAL' : 'BUFFER_LOCAL' };
  let next = 100;
  const server = http.createServer(async (req, res) => {
    const url = new URL(req.url, 'http://localhost');
    const run = req.headers['x-test-run-id'];
    if (url.pathname === '/openapi.json') return enviar(res, 200, { paths: {
      '/iot/telemetria/batch': { post: {} }, '/iot/telemetria': { post: {} },
      '/configuracion/variables-ambientales': { get: {} }, '/iot/monitoreo/historial': { get: {} } },
    components: { schemas: { dto: { serial: true, timestamp_captura: true, timestamp_envio: true,
      origen: true, registros: true } } } });
    if (url.pathname === '/sesiones/' && req.method === 'POST') {
      const datos = await leer(req);
      return enviar(res, 200, { token: datos?.correo_electronico === 'admin@example.test' ? 'TOKEN_ADMIN_SINTETICO' : 'TOKEN_SINTETICO' });
    }
    if (url.pathname === '/iot/auditoria') {
      if (modo === 'auditoria_denegada') return enviar(res, 403, { detail: 'permiso 39,2 no disponible' }, run);
      const id = url.searchParams.get('entidad_afectada_id');
      return enviar(res, 200, { total: 1, items: [{ id_evento: 'EVENTO_SINTETICO', entidad_afectada_id: id,
        tipo_evento: 'SINCRONIZACION', fecha_hora: new Date().toISOString(),
        accion_detallada: { timestamp_sincronizacion: new Date().toISOString() } }] }, run);
    }
    if (url.pathname.startsWith('/test-control/runs/') && req.method === 'DELETE') {
      escritos.clear(); return enviar(res, 200, { status: 'Rollback exitoso' });
    }
    if (url.pathname === '/configuracion/dispositivos-iot') return enviar(res, 200,
      modo === 'contrato_inesperado' ? [semilla] : { total: modo === 'sin_semilla' ? 0 : vacios.length + 1,
        items: modo === 'sin_semilla' ? [] : modo === 'rf60_activo_recurso'
          ? [semilla, ...vacios] : [...vacios, semilla] }, run);
    if (url.pathname === '/configuracion/variables-ambientales') return enviar(res, 200,
      { total: 1, items: [{ id_variable_ambiental: 8, nombre: 'Temperatura Ambiental', unidad: '°C',
        valor_fisico_min: -40, valor_fisico_max: 80 }] }, run);
    if (url.pathname === '/iot/dispositivos') return enviar(res, 200,
      [...vacios.map((x, i) => ({ id_dispositivo_iot: x.id_dispositivo_iot,
        estado_actual: dashboardPrimero && i === 0 ? 'ACTIVO' : 'SIN_SEÑAL' })),
        { id_dispositivo_iot: 37, estado_actual: modo === 'rf60_activo_recurso' ? 'ACTIVO' : 'SIN_SEÑAL' }], run);
    if (/^\/configuracion\/dispositivos-iot\/\d+\/sensores$/.test(url.pathname)
      && url.pathname !== '/configuracion/dispositivos-iot/37/sensores') return enviar(res, 200, { total: 0, items: [] }, run);
    if (url.pathname === '/configuracion/dispositivos-iot/37/sensores') return enviar(res, 200,
      { total: 1, items: [sensor] }, run);
    if (url.pathname.startsWith('/iot/monitoreo/dashboard/')) {
      if (modo === 'unidad_timeout_continua' && url.pathname.endsWith('/1')) { req.socket.destroy(); return; }
      const visible = (['semilla_dashboard_verde', 'semilla_dashboard_reciente'].includes(modo) && url.pathname.endsWith('/9'))
        || (['intento2_dashboard', 'unidad_timeout_continua'].includes(modo) && url.pathname.endsWith('/268'))
        || (modo === 'intento3_sin_lecturas_recientes' && url.pathname.endsWith('/1'));
      return enviar(res, 200, { total: visible ? 1 : 0,
        sensores: visible ? [{ id_sensor: 73, id_dispositivo_iot: 37,
          tipo_variable: 'Temperatura Ambiental', ultima_unidad: '°C', ultimo_valor: 25,
          ultimo_timestamp_captura: base.timestamp_captura,
          estado_semaforo: modo === 'semilla_dashboard_reciente' ? 'AMARILLO'
            : modo === 'intento3_sin_lecturas_recientes' ? 'GRIS' : 'VERDE',
          estado_calidad: modo === 'intento3_sin_lecturas_recientes' ? null : 'LECTURA_VALIDA' }] : [] }, run);
    }
    if (url.pathname === '/iot/monitoreo/historial') {
      const items = [...(modo === 'sin_valor_seguro' ? [] : [base]), ...(run ? [...escritos.values()].flat() : [])].filter(x =>
        Number(x.id_sensor) === Number(url.searchParams.get('sensor_id')));
      const conEco = !(modo === 'sin_eco' && escritos.size > 0);
      return enviar(res, 200, { total: items.length, items }, run, conEco);
    }
    if (url.pathname === '/iot/telemetria/batch' && req.method === 'POST') {
      if (req.headers.authorization !== 'Bearer ENSAYO_BROKER') return enviar(res, 401, { error: 'token' }, run);
      const body = await leer(req); const registros = body?.registros ?? [];
      if (registros.some(x => x.tipo_variable !== 'TEMPERATURA_AMBIENTAL'
        || x.id_variable !== 8 || x.unidad !== '°C' || x.serial !== 'SERIAL_SINTETICO'))
        return enviar(res, 200, { total: registros.length, aceptados: 0, rechazados: registros.length,
          duplicados: 0, detalle: registros.map(x => ({ sensor_id: x.sensor_id,
            timestamp_captura: x.timestamp_captura, estado: 'RECHAZADO', error: 'La variable no existe o está inactiva en el catálogo M09.' })) }, run);
      if (modo === 'rechazo_por_antiguedad_23h' && registros.some(x =>
        Date.parse(x.timestamp_envio) - Date.parse(x.timestamp_captura) >= 23 * 3600000))
        return enviar(res, 200, { total: registros.length, aceptados: 0, rechazados: registros.length,
          duplicados: 0, detalle: registros.map(x => ({ sensor_id: x.sensor_id,
            timestamp_captura: x.timestamp_captura, estado: 'RECHAZADO', error: 'Dato de BUFFER_LOCAL con retraso superior a 72 horas.' })) }, run);
      if (modo === 'error5xx' && registros.some(x => Date.parse(x.timestamp_envio) - Date.parse(x.timestamp_captura) >= 23 * 3600000))
        return enviar(res, 503, { error: 'simulado' }, run);
      let aceptados = 0, duplicados = 0;
      const detalle = registros.map(x => {
        const clave = `${x.sensor_id}|${x.tipo_variable}|${x.timestamp_captura}|${x.origen}`;
        const previo = escritos.get(clave);
        if (previo && modo !== 'duplicado') { duplicados++; return { sensor_id: x.sensor_id,
          timestamp_captura: x.timestamp_captura, estado: 'ERROR_DUPLICADO' }; }
        const fila = { id_telemetria: next++, id_sensor: x.sensor_id, id_variable: x.id_variable,
          tipo_variable: 'Temperatura Ambiental',
          timestamp_captura: modo === 'timestamp_alterado' && registros.length === 3
            ? new Date(Date.parse(x.timestamp_captura) + 1000).toISOString() : x.timestamp_captura,
          origen_dato: modo === 'origen_incorrecto' && registros.length === 3 ? 'TIEMPO_REAL' : x.origen,
          unidad_medida: x.unidad, valor: x.valor };
        escritos.set(clave, [...(previo ?? []), fila]); aceptados++;
        return { sensor_id: x.sensor_id, timestamp_captura: x.timestamp_captura,
          estado: 'LECTURA_VALIDA', id_telemetria: fila.id_telemetria,
          ...(modo === 'sync_ausente' ? {} : { timestamp_sincronizacion: modo === 'sync_invalido' ? null
            : new Date(Date.parse(x.timestamp_envio) + 10000).toISOString() }) };
      });
      return enviar(res, 200, { total: registros.length, aceptados, rechazados: 0, duplicados, detalle }, run);
    }
    if (url.pathname === '/iot/telemetria' && req.method === 'POST') {
      const x = await leer(req);
      if (modo === 'contraste_error_tiempo') return enviar(res, 400,
        { codigo: 'ERROR_TIEMPO', mensaje: 'La fecha de captura de la lectura no es válida.' }, run);
      if (modo !== 'contraste_404' && (Date.parse(x.timestamp_captura) > Date.now() - 4 * 60000
        || Date.parse(x.timestamp_envio) < Date.parse(x.timestamp_captura))) return enviar(res, 400,
        { codigo: 'ERROR_TIEMPO', mensaje: 'La fecha de captura de la lectura no es válida.' }, run);
      if (x.tipo_variable !== 'TEMPERATURA_AMBIENTAL' || modo === 'contraste_404') return enviar(res, 404,
        { error_code: 'VARIABLE_NO_ENCONTRADA', message: 'La variable no existe o está inactiva en el catálogo M09.' }, run);
      const clave = `${x.sensor_id}|${x.tipo_variable}|${x.timestamp_captura}|${x.origen}`;
      const fila = { id_telemetria: next++, id_sensor: x.sensor_id, id_variable: x.id_variable,
        tipo_variable: 'Temperatura Ambiental',
        timestamp_captura: x.timestamp_captura, origen_dato: x.origen, unidad_medida: x.unidad, valor: x.valor };
      escritos.set(clave, [fila]); return enviar(res, 201, { id_telemetria: fila.id_telemetria,
        estado_calidad: 'LECTURA_VALIDA', timestamp_procesamiento: new Date().toISOString() }, run);
    }
    return enviar(res, 404, { error: 'ruta' }, run);
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  return server;
}
try {
  let ok = 0;
  for (const [modo, esperado, oficial] of MODOS) {
    const server = await servidor(modo);
    try {
      const run = `ENSAYO-G120-20261026-120000-${modo}`;
      const salida = path.join(temporal, modo); fs.mkdirSync(salida);
      const contexto = { grupo: 'G120', version: 1, intento: 1, run_id: run,
        operacion: 'EVALUAR', referencia: 'AUT-ENSAYO-LOCAL', casos: CASOS,
        alcance_reevaluacion: null, version_anterior: null };
      const archivo = path.join(salida, 'contexto_operacion.json');
      fs.writeFileSync(archivo, JSON.stringify(contexto));
      const api = `http://127.0.0.1:${server.address().port}`;
      const c = contextoEjecucion(['--operacion', 'evaluar', '--version', '1', '--intento', '1',
        '--run-id', run, '--autorizacion', 'AUT-ENSAYO-LOCAL', '--contexto', archivo],
      { grupo: 'G120', casos: CASOS, directorio: raiz, modoEnsayo: true });
      const env = { QA_AUTORIZADO: 'SI', SIGAB_API_TEST_BASE: api, QA_SANDBOX_SECRET: 'ENSAYO_SECRET',
        BROKER_SERVICE_TOKEN: 'ENSAYO_BROKER', QA_PROD_EMAIL: 'productor@example.test',
        QA_PROD_PASSWORD: 'ENSAYO_PASS', QA_ADMIN_EMAIL: 'admin@example.test',
        QA_ADMIN_PASSWORD: 'ENSAYO_ADMIN_PASS',
        QA_G120_ENSAYO_TIPO_INVALIDO: modo === 'todo_rechazado_cuerpo' ? 'SI' : 'NO' };
      await evaluar(c, { env, ensayo: true });
      const resultado = JSON.parse(fs.readFileSync(path.join(salida, 'resultado.json'), 'utf8'));
      const informe = new TextDecoder('utf-8', { fatal: true })
        .decode(fs.readFileSync(path.join(salida, 'TC-M03-G120_resultado.md')));
      if (contieneMojibake(informe)) throw Error(`${modo}: informe con texto mojibake`);
      const estados = CASOS.map(c => resultado.casos[c].estado);
      const presentes = new Set(['resultado.json', ...fs.readdirSync(salida),
        ...(fs.existsSync(path.join(salida, 'newman')) ? fs.readdirSync(path.join(salida, 'newman')).map(x => `newman/${x}`) : [])]);
      const registro = clasificarRegistro(CAPACIDADES, resultado, presentes, { runId: run, version: 1 });
      const incidenciaEdad = modo === 'rechazo_por_antiguedad_23h'
        ? crearInforme({ ...resultado, ambiente: 'TEST' }) : '';
      const coincide = JSON.stringify(estados) === JSON.stringify(esperado) && resultado.oficial === oficial
        && registro === oficial && resultado.cierre.run.cierre_http === 200
        && (modo === 'sin_semilla' || modo === 'contrato_inesperado'
          ? resultado.cierre.rollback.verificado === true && resultado.cierre.rollback.metodo === 'sin_escrituras'
          : true)
        && (modo !== 'contrato_inesperado' || resultado.problemas_tecnicos.some(x => x.startsWith('ERROR_QA_CONTRATO_SEMILLA')))
        && (modo !== 'sin_semilla' || (resultado.diagnostico_semilla.pasos[0].recibidos === 0
          && resultado.problemas_tecnicos.length === 0))
        && (modo !== 'aprobado' || (resultado.diagnostico_semilla.fuente_valor.origen === 'historial_LECTURA_VALIDA'
          && resultado.diagnostico_semilla.fuente_valor.rango === null && resultado.semilla.valor === 25))
        && (modo !== 'semilla_dashboard_verde' || resultado.diagnostico_semilla.fuente === 'dashboard')
        && (modo !== 'semilla_dashboard_reciente' || resultado.diagnostico_semilla.fuente === 'dashboard')
        && (modo !== 'intento2_dashboard' || (resultado.diagnostico_semilla.fuente === 'dashboard'
          && resultado.diagnostico_semilla.pasos[0].recibidos === 183
          && resultado.diagnostico_semilla.pasos[0].filtros.activos_no_camara_aptos === 178
          && resultado.diagnostico_semilla.conectividad.activo === 1
          && resultado.diagnostico_semilla.pasos.filter(x => x.paso === 'sensores').length === 1
          && resultado.diagnostico_semilla.pasos.findIndex(x => x.paso === 'dashboard_unidad')
            < resultado.diagnostico_semilla.pasos.findIndex(x => x.paso === 'sensores')))
        && (modo !== 'rf60_activo_recurso' || (resultado.diagnostico_semilla.estado_conectividad_informativo === 'ACTIVO'
          && resultado.diagnostico_semilla.pasos.filter(x => x.paso === 'sensores').length === 1))
        && (modo !== 'intento3_sin_lecturas_recientes' || (resultado.diagnostico_semilla.fuente === 'dashboard'
          && resultado.diagnostico_semilla.fuente_valor.origen === 'historial_umbral_punto_medio'
          && resultado.semilla.valor === 25 && resultado.diagnostico_semilla.pasos.some(x => x.paso === 'dashboard_unidad'
            && x.recibidos === 1 && x.filtros.lecturas_validas_recientes === 0)))
        && (modo !== 'unidad_timeout_continua' || (resultado.diagnostico_semilla.errores_unidad === 1
          && resultado.diagnostico_semilla.pasos.some(x => x.paso === 'dashboard_unidad' && x.error)
          && resultado.diagnostico_semilla.fuente === 'dashboard' && resultado.problemas_tecnicos.length === 0))
        && (modo !== 'sin_valor_seguro' || (resultado.diagnostico_semilla.sin_valor_seguro === 1
          && resultado.casos[CASOS[0]].motivo === 'DATOS_SEMILLA_SIN_VALOR_SEGURO'
          && resultado.problemas_tecnicos.length === 0))
        && (modo !== 'busqueda_acotada' || (resultado.problemas_tecnicos.includes('ERROR_QA_BUSQUEDA_SEMILLA_ACOTADA')
          && resultado.diagnostico_semilla.alcance_incompleto === true
          && resultado.diagnostico_semilla.pasos.filter(x => x.paso === 'sensores').length === 12
          && resultado.diagnostico_semilla.pasos.findIndex(x => x.paso === 'dashboard_unidad')
            < resultado.diagnostico_semilla.pasos.findIndex(x => x.paso === 'sensores')))
        && (modo !== 'auditoria_denegada' || resultado.observacion_sincronizacion.auditoria.consultas.every(x => x.http === 403))
        && (modo !== 'sync_ausente' || resultado.observacion_sincronizacion.batch.estado === 'ausente')
        && (modo !== 'todo_rechazado_cuerpo' || (resultado.problemas_tecnicos.some(x => x.startsWith('ERROR_QA_CUERPO_'))
          && Object.values(resultado.ingestas).filter(x => x.detalle).every(x => x.detalle.every(z => z.error?.includes('variable')))
          && resultado.ingestas.real.http === 404
          && resultado.ingestas.real.error_cuerpo?.codigo === 'VARIABLE_NO_ENCONTRADA'
          && !informe.includes('### INC-M03-')))
        && (modo !== 'rechazo_por_antiguedad_23h' || (resultado.ingestas.bordes.detalle.every(x => x.error?.includes('72 horas'))
          && incidenciaEdad.includes('### INC-M03-243-G120-01')
          && incidenciaEdad.includes('Restricción 14, Especificacion-Requerimientos-Modulo3.md:5718-5721')
          && !incidenciaEdad.includes('### INC-M03-241-G120-01')))
        && (modo !== 'contraste_404' || (resultado.ingestas.real.http === 404
          && resultado.ingestas.real.error_cuerpo?.codigo === 'VARIABLE_NO_ENCONTRADA'
          && resultado.problemas_tecnicos.includes('ERROR_QA_CONTRASTE_TIEMPO_REAL')
          && !informe.includes('### INC-M03-241-G120-01')))
        && (modo !== 'aprobado' || (resultado.semilla.tipo_variable === 'TEMPERATURA_AMBIENTAL'
          && resultado.semilla.id_variable === 8 && resultado.problemas_tecnicos.length === 0))
        && (modo !== 'contraste_error_tiempo' || (resultado.ingestas.real.http === 400
          && resultado.ingestas.real.error_cuerpo?.codigo === 'ERROR_TIEMPO'
          && Date.parse(resultado.marcas.envio) - Date.parse(resultado.marcas.real) > 4 * 60000
          && resultado.casos[CASOS[0]].motivo.includes('Intervalo BUFFER_LOCAL acreditado')
          && resultado.casos[CASOS[0]].motivo.includes('TIEMPO_REAL NO_CONCLUYENTE')
          && resultado.problemas_tecnicos.includes('ERROR_QA_CONTRASTE_TIEMPO_REAL')
          && !informe.includes('### INC-M03-241-G120-01')))
        && (modo !== 'contraste_existente' || (resultado.ingestas.real.fuente === 'historial_existente'
          && resultado.ingestas.real.http === null && resultado.ingestas.real.id_telemetria === 1
          && !resultado.bitacora.some(x => x.metodo === 'POST' && x.ruta === '/iot/telemetria')
          && resultado.problemas_tecnicos.length === 0))
        && !JSON.stringify(resultado).includes('ENSAYO_SECRET') && !JSON.stringify(resultado).includes('ENSAYO_BROKER')
        && !JSON.stringify(resultado).includes('SERIAL_SINTETICO')
        && informe.startsWith(`# TC-M03-G120 — ${oficial && esperado.includes('RECHAZADO') ? 'RECHAZADO' : oficial ? 'APROBADO' : 'NO_CONCLUYENTE'}`)
        && ['## Decisión del caso', '## Observaciones', '## Incidencias de producto',
          '## Efectos, cierre y rollback'].every(x => informe.includes(x))
        && (modo !== 'sync_ausente' || informe.includes('Su ausencia no cambia el veredicto'))
        && resultado.run_id === run;
      if (!coincide) throw Error(`${modo}: esperado=${JSON.stringify(esperado)}/${oficial}, obtenido=${JSON.stringify(estados)}/${resultado.oficial}, registro=${registro}, problemas=${JSON.stringify(resultado.problemas_tecnicos)}`);
      console.log(`OK ${modo}: ${estados.join(',')} oficial=${oficial} registro=${registro}`); ok++;
    } finally { await new Promise(resolve => server.close(resolve)); }
  }
  console.log(`G120 ENSAYO ${ok}/${MODOS.length}`);
} catch (e) {
  if (e.code === 'EPERM') {
    console.log('ENSAYO_NO_EJECUTABLE: spawn EPERM');
    process.exitCode = 2;
  } else throw e;
} finally {
  if (!path.resolve(temporal).startsWith(path.resolve(os.tmpdir()) + path.sep)) throw Error('TEMP_FUERA_RAIZ');
  fs.rmSync(temporal, { recursive: true, force: true });
}
