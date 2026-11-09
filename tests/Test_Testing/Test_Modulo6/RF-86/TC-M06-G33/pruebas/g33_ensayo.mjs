import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import http from 'node:http';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { evaluar, informe } from '../g33.mjs';
import { CAPACIDADES, PRESUPUESTO } from '../lib/g33_core.mjs';
import { clasificarRegistro } from './registro_qa.mjs';

const grupo = fileURLToPath(new URL('../', import.meta.url));
function archivos(dir = grupo) {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap(x => {
    const ruta = path.join(dir, x.name);
    return x.isDirectory() ? archivos(ruta) : [path.relative(grupo, ruta)];
  }).sort();
}
const antes = archivos();
const modos = ['sin_variacion_ok', 'variacion_creada', 'linea_creada', 'auditoria_ausente', 'auditoria_severidad_incorrecta', 'alerta_error',
  'rebase_requerido', 'sin_candidato', 'lectura_5xx', 'delete_sin_secreto', 'corte_403', 'poscierre',
  'registro_qa_fiel', 'sin_archivos', 'bandeja_mas_de_50', 'aviso_ajeno', 'aviso_error_del_activo'];
const hoy = new Intl.DateTimeFormat('en-CA', { timeZone: 'America/Bogota', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date());

async function servidor(modo) {
  const eventos = [], variaciones = [], lineas = [], mediciones = [], auditoria = [], avisos = [];
  if (modo === 'bandeja_mas_de_50') {
    for (let n = 1; n <= 55; n++) avisos.unshift({ id_notificacion: n, fecha_envio: '2026-11-08T00:00:00Z', mensaje: 'Aviso anterior' });
    for (let n = 1; n <= 501; n++) auditoria.push({ id_evento: n, tipo_evento: 'OTRO', severidad_evento: 'INFO' });
  }
  const calculos = [{ id_calculo_valor_razonable: 100, id_activo_biologico: 101,
    id_precio_mercado: modo === 'rebase_requerido' ? 400 : 401, magnitud: 400, unidad_magnitud: 'kg',
    valor_neto: 1000, estado: 'CALCULADO', fecha_calculo: hoy }];
  const registros = []; let procesados = 0, cerrado = false, deleteConSecreto = false, poscierre = 0;
  const send = (res, code, data, run) => {
    res.writeHead(code, { 'Content-Type': 'application/json', ...(run ? { 'X-Test-Run-Id': run } : {}) });
    res.end(JSON.stringify(data));
  };
  const server = http.createServer(async (req, res) => {
    const u = new URL(req.url, 'http://localhost'); const run = req.headers['x-test-run-id'];
    if (cerrado && req.method === 'GET') poscierre++;
    const body = await new Promise(resolve => { let s = ''; req.on('data', x => s += x);
      req.on('end', () => { try { resolve(JSON.parse(s || '{}')); } catch { resolve({}); } }); });
    registros.push({ metodo: req.method, ruta: u.pathname, pagina: u.searchParams.get('pagina'),
      run, secreto: req.headers['x-sandbox-secret'], body });
    if (req.method === 'POST' && u.pathname === '/sesiones/') return send(res, 200, { token: 'token-local' });
    if (req.method === 'DELETE' && u.pathname.startsWith('/test-control/runs/')) {
      deleteConSecreto = req.headers['x-sandbox-secret'] === 'secreto-local';
      if (!deleteConSecreto) return send(res, 400, { error_code: 'SECRETO_REQUERIDO' });
      cerrado = true; eventos.length = 0; variaciones.length = 0; lineas.length = 0;
      mediciones.length = 0; auditoria.length = 0; calculos.splice(1);
      calculos[0].id_precio_mercado = modo === 'rebase_requerido' ? 400 : 401;
      return send(res, 200, { ok: true });
    }
    if (req.method === 'GET' && u.pathname === '/finanzas/activos') {
      if (modo === 'corte_403') return send(res, 403, { error_code: 'SIN_PERMISO' }, run);
      return send(res, 200, modo === 'sin_candidato' ? [] : [{ id_activo_biologico: 101,
        especie: 'Bovino', tipo: 'INDIVIDUAL', estado: 'ACTIVO', valorado_por_costo: false,
        valor_razonable_neto: 1000, id_especie: 39 }], run);
    }
    if (req.method === 'GET' && u.pathname === '/finanzas/periodos') return send(res, 200,
      [{ id_periodo_contable: 201, numero_id_tributaria: 'titular-local', estado: 'ABIERTO',
        fecha_inicio: hoy.slice(0, 4) + '-01-01', fecha_fin: hoy.slice(0, 4) + '-12-31' }], run);
    if (req.method === 'GET' && u.pathname === '/finanzas/precios') return send(res, 200,
      [{ id_precio_mercado: 401, id_especie: 39, categoria: 'PESO_KG', fuente: 'MERCADO_ACTIVO',
        fecha_vigencia: hoy, precio_unitario: 10 }], run);
    if (req.method === 'GET' && u.pathname === '/finanzas/activos/101') return send(res, 200,
      { activo: { numero_id_tributaria: 'titular-local' }, calculos, mediciones }, run);
    if (req.method === 'GET' && u.pathname === '/activos-biologicos/101/ficha-integral') return send(res, 200,
      { peso_actual: 400, unidad_peso: 'kg', estado_actual: 'ACTIVO' }, run);
    if (req.method === 'GET' && u.pathname === '/activos-biologicos/101/eventos') return send(res, 200,
      { eventos: eventos.map(id_eventos => ({ id_eventos })) }, run);
    if (req.method === 'POST' && u.pathname === '/activos-biologicos/101/eventos/crecimiento') {
      assert.equal(body.valor_medicion, 400); assert.equal(body.unidad_medida, 'kg');
      const eid = 301 + eventos.length; eventos.push(eid);
      return send(res, 201, { evento: { id_eventos: eid } }, run);
    }
    if (req.method === 'POST' && u.pathname === '/finanzas/eventos/procesar') {
      procesados++;
      if (modo === 'rebase_requerido' && procesados === 1) {
        calculos.push({ ...calculos[0], id_calculo_valor_razonable: 101, id_precio_mercado: 401 });
        return send(res, 200, { eventos: { procesados: 1 } }, run);
      }
      const eid = eventos.at(-1);
      if (modo === 'variacion_creada') variaciones.push({ id_variacion_valor_razonable: 501,
        id_activo_biologico: 101, monto_variacion: 1 });
      if (modo === 'linea_creada') lineas.push({ id_linea_asiento_nic41: 601, id_activo_biologico: 101, valor: 1 });
      if (modo !== 'auditoria_ausente') auditoria.push({ id_evento: 701, tipo_evento: 'MEDICION_SIN_VARIACION',
        severidad_evento: modo === 'auditoria_severidad_incorrecta' ? 'WARNING' : 'INFO', id_activo_biologico: 101, id_periodo_contable: 201,
        id_referencia: eid, payload_evento: { valor_neto: '1000' } });
      if (modo === 'alerta_error') auditoria.push({ id_evento: 702, tipo_evento: 'MEDICION_PENDIENTE',
        severidad_evento: 'WARNING', id_activo_biologico: 101, id_periodo_contable: 201, id_referencia: eid });
      if (modo === 'bandeja_mas_de_50') for (let n = 56; n <= 106; n++) avisos.unshift({
        id_notificacion: n, fecha_envio: '2026-11-08T01:00:00Z', mensaje: 'Aviso ajeno de otra actividad' });
      if (modo === 'aviso_ajeno' || modo === 'aviso_error_del_activo') avisos.unshift({
        id_notificacion: 56, fecha_envio: '2026-11-08T01:00:00Z',
        mensaje: modo === 'aviso_ajeno' ? 'Error en medición de activo 999' : 'MEDICION_PENDIENTE del activo 101' });
      return send(res, 200, { eventos: { procesados: 1 } }, run);
    }
    if (req.method === 'GET' && u.pathname === '/finanzas/periodos/201/variaciones') {
      if (modo === 'lectura_5xx' && procesados) return send(res, 500, { error_code: 'LOCAL_5XX' }, run);
      return send(res, 200, variaciones, run);
    }
    if (req.method === 'GET' && u.pathname === '/finanzas/lineas') return send(res, 200, lineas, run);
    if (req.method === 'GET' && u.pathname === '/finanzas/periodos/201/mediciones') return send(res, 200, mediciones, run);
    if (req.method === 'GET' && u.pathname === '/finanzas/auditoria') return send(res, 200,
      { total_registros: auditoria.length, eventos: auditoria.slice((Number(u.searchParams.get('pagina') || 1) - 1) * 500,
        Number(u.searchParams.get('pagina') || 1) * 500) }, run);
    if (req.method === 'GET' && u.pathname === '/notificaciones') return send(res, 200,
      { total: avisos.length, items: avisos.slice((Number(u.searchParams.get('pagina') || 1) - 1) * 50,
        Number(u.searchParams.get('pagina') || 1) * 50) }, run);
    return send(res, 404, { error_code: 'NO_ENCONTRADO' }, run);
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  return { server, api: 'http://127.0.0.1:' + server.address().port,
    estado: () => ({ registros, procesados, deleteConSecreto, poscierre }) };
}

let completados = 0;
for (const modo of modos) {
  const s = await servidor(modo);
  try {
    const c = { runId: 'RUN-G33-V1-20261108-000000', version: 1, intento: 1,
      referencia: 'ENSAYO_LOCAL', ensayo: true, directorio: path.join(grupo, 'RUN-PROHIBIDO') };
    const env = { QA_AUTORIZADO: 'SI', SIGAB_API_TEST_BASE: s.api, QA_SANDBOX_SECRET: 'secreto-local',
      QA_CONTADOR_EMAIL: 'contador@local.test', QA_CONTADOR_PASSWORD: 'clave-local',
      QA_ADMIN_EMAIL: 'admin@local.test', QA_ADMIN_PASSWORD: 'clave-local' };
    const r = await evaluar(c, { env, apiOverride: s.api, sinArtefactos: true });
    const esperado = ['variacion_creada', 'linea_creada', 'auditoria_ausente', 'auditoria_severidad_incorrecta', 'alerta_error', 'aviso_error_del_activo'].includes(modo) ? 'RECHAZADO' :
      modo === 'sin_candidato' || modo === 'corte_403' ? 'BLOQUEADO' : modo === 'lectura_5xx' ? 'NO_CONCLUYENTE' : 'APROBADO';
    assert.equal(r.casos['TC-M06-005'].estado, esperado, modo + ': estado');
    assert.deepEqual(r.comprobaciones.map(x => x.caso),
      r.comprobaciones.map(() => 'TC-M06-005'), modo + ': caso corto en comprobaciones');
    assert.ok(r.solicitudes.length <= PRESUPUESTO.solicitudes_totales, modo + ': solicitudes');
    assert.ok(s.estado().deleteConSecreto, modo + ': DELETE con secreto');
    assert.equal(s.estado().registros.filter(x => x.metodo === 'POST' && x.ruta.endsWith('/eventos/crecimiento')).length,
      modo === 'rebase_requerido' ? 2 : ['sin_candidato', 'corte_403'].includes(modo) ? 0 : 1, modo + ': eventos');
    assert.ok(s.estado().registros.filter(x => x.metodo === 'POST' && x.ruta === '/finanzas/eventos/procesar').length <= 2);
    assert.equal(s.estado().registros.filter(x => x.metodo === 'POST' && x.ruta === '/finanzas/precios').length, 0);
    if (!['sin_candidato', 'corte_403', 'lectura_5xx'].includes(modo)) assert.equal(r.cierre.rollback.verificado, true, modo + ': rollback');
    if (modo === 'poscierre') assert.ok(s.estado().poscierre >= 7, 'lecturas públicas poscierre');
    if (modo === 'rebase_requerido') assert.match(r.casos['TC-M06-005'].preparacion.rebase, /evento M02 301/);
    if (modo === 'bandeja_mas_de_50') {
      assert.equal(r.casos['TC-M06-005'].observados.avisos_error, 0);
      assert.equal(r.casos['TC-M06-005'].observados.avisos_ajenos, 51);
      assert.ok(s.estado().registros.some(x => x.ruta === '/finanzas/auditoria' && x.metodo === 'GET'));
      assert.ok(s.estado().registros.some(x => x.ruta === '/finanzas/auditoria' && x.pagina === '2'));
      assert.ok(s.estado().registros.some(x => x.ruta === '/notificaciones' && x.pagina === '2'));
    }
    if (modo === 'aviso_ajeno') assert.equal(r.casos['TC-M06-005'].observados.avisos_ajenos, 1);
    if (modo === 'aviso_error_del_activo') assert.equal(r.casos['TC-M06-005'].observados.avisos_error, 1);
    if (modo === 'sin_variacion_ok') assert.deepEqual(
      r.casos['TC-M06-005'].observados.auditorias_sin_variacion_detalle,
      [{ id: 701, severidad: 'INFO', referencia: 301, periodo: 201 }]);
    if (modo === 'auditoria_ausente') assert.deepEqual(
      r.casos['TC-M06-005'].observados.auditorias_sin_variacion_detalle, []);
    if (modo === 'auditoria_severidad_incorrecta') assert.deepEqual(
      r.casos['TC-M06-005'].observados.auditorias_sin_variacion_detalle,
      [{ id: 701, severidad: 'WARNING', referencia: 301, periodo: 201 }]);
    if (modo === 'registro_qa_fiel') {
      const pub = structuredClone(r); pub.oficial = true; pub.consume_version = true;
      for (const x of pub.comprobaciones) x.evidencia = 'resultado.json';
      pub.herramientas.newman = { iteraciones: 1, fallos: 0 };
      pub.evidencias = ['resultado.json', 'TC-M06-G33_resultado.md', 'newman/newman-G33.json', 'newman/newman-G33.html'];
      const presentes = new Set(pub.evidencias);
      assert.equal(clasificarRegistro(CAPACIDADES, pub, presentes, { runId: c.runId, version: 1 }), true);
      pub.comprobaciones[0].caso = 'TC-M06-G33 / TC-M06-005';
      assert.equal(clasificarRegistro(CAPACIDADES, pub, presentes, { runId: c.runId, version: 1 }), false);
      pub.comprobaciones[0].caso = 'TC-M06-005';
      pub.comprobaciones[0].estado = 'NO_CONCLUYENTE';
      assert.equal(clasificarRegistro(CAPACIDADES, pub, presentes, { runId: c.runId, version: 1 }), false);
    }
    if (modo === 'sin_variacion_ok') {
      const md = informe(c, r); assert.match(md, /Detalle por caso/); assert.match(md, /Cumplido/);
      assert.doesNotMatch(md, /\{\s*"casos"/);
    }
    assert.deepEqual(archivos(), antes, modo + ': archivos en grupo');
    completados++;
  } finally { await new Promise(resolve => s.server.close(resolve)); }
}
const sonda = http.createServer((req, res) => {
  res.writeHead(200, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify({ ok: req.url === '/newman-probe' }));
});
await new Promise(resolve => sonda.listen(0, '127.0.0.1', resolve));
try {
  const url = `http://127.0.0.1:${sonda.address().port}/newman-probe`;
  const entrada = JSON.stringify({ coleccion: { info: { name: 'G33 sonda local',
    _postman_id: 'g33-local', schema: 'https://schema.getpostman.com/json/collection/v2.1.0/collection.json' },
    item: [{ name: 'sonda', request: { method: 'GET', url } }] },
    environment: { values: [] }, timeout: 30000 });
  const resultado = await new Promise(resolve => {
    let hijo;
    try { hijo = spawn(process.execPath, [fileURLToPath(new URL('./newman_hijo.mjs', import.meta.url))],
      { stdio: ['pipe', 'pipe', 'pipe'], windowsHide: true }); }
    catch (e) { resolve({ error: e.code ?? e.message }); return; }
    let salida = '', error = null;
    hijo.on('error', e => { error = e.code ?? e.message; });
    hijo.stdout.on('data', b => { salida += b.toString(); });
    hijo.stdin.on('error', () => {});
    hijo.stdin.end(entrada);
    hijo.on('close', codigo => resolve({ codigo, salida, error }));
  });
  if (resultado.error) console.log(`OK newman_hijo: no ejecutable en este entorno (${resultado.error})`);
  else {
    const salida = JSON.parse(resultado.salida);
    assert.equal(resultado.codigo, 0, `newman_hijo: ${salida.error}`);
    assert.equal(salida.solicitudes.length, 1);
    assert.equal(salida.solicitudes[0].http, 200);
    console.log('OK newman_hijo: process.execPath, 1 lectura loopback HTTP 200');
  }
} finally { await new Promise(resolve => sonda.close(resolve)); }
assert.deepEqual(archivos(), antes, 'El ensayo dejó archivos nuevos dentro de G33');
console.log('OK G33: ' + completados + '/' + modos.length + ' modos; aislamiento y cierre comprobados; registro QA fiel');
