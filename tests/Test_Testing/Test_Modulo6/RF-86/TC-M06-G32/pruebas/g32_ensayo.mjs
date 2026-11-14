import assert from 'node:assert/strict';
import fs from 'node:fs';
import http from 'node:http';
import path from 'node:path';
import os from 'node:os';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { evaluar, informe } from '../g32.mjs';
import { CAPACIDADES, CASOS, PRESUPUESTO } from '../lib/g32_core.mjs';
import { clasificarRegistro } from './registro_qa.mjs';

const grupo = fileURLToPath(new URL('../', import.meta.url));
function archivosGrupo(dir = grupo) {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap(x => {
    const ruta = path.join(dir, x.name);
    return x.isDirectory() ? archivosGrupo(ruta) : [path.relative(grupo, ruta)];
  });
}
const archivosIniciales = new Set(archivosGrupo());
const fetchOriginal = globalThis.fetch;
let intentosRemotos = 0;
globalThis.fetch = (url, opciones) => {
  if (!/^http:\/\/(127\.0\.0\.1|localhost):\d+\//.test(String(url))) {
    intentosRemotos++; throw Error('RED_REMOTA_PROHIBIDA_EN_ENSAYO');
  }
  return fetchOriginal(url, opciones);
};

const MODOS = ['todo_ok', 'con_campos_inyectados', 'sin_pm_matriz', 'periodo8_en_cierre', 'v1_500', 'sin_conflicto8', 'v1_409', 'periodo_cerrado_con_posterior_abierto',
  'sin_precondicion', 'sin_ids_origen', 'origen_distinto', 'tratamiento_rechazado',
  'caso001_rebase_precio', 'caso002_rebase_precio', 'estado_inicial_distinto', 'delete_error_400'];
const hoy = new Intl.DateTimeFormat('en-CA', { timeZone: 'America/Bogota', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date());
const mesActual = hoy.slice(0, 7);
const mesSiguiente = new Date(Date.UTC(Number(hoy.slice(0, 4)), Number(hoy.slice(5, 7)), 1)).toISOString().slice(0, 7);
const finMes = mes => new Date(Date.UTC(Number(mes.slice(0, 4)), Number(mes.slice(5, 7)), 0)).toISOString().slice(0, 10);
async function servidor(modo) {
  const activos = [101, 102, 103, 104].map((id, i) => ({ id_activo_biologico: id, especie: 'Bovino', tipo: 'INDIVIDUAL',
    estado: 'ACTIVO', valorado_por_costo: false,
    valor_razonable_neto: 1000, id_especie: modo === 'sin_precondicion' && i === 3 ? 5 : 4, numero_id_tributaria: '123' }));
  const precios = [{ id_precio_mercado: 401, id_especie: 4, categoria: 'PESO_KG', precio_unitario: 10,
    fuente: 'MERCADO_ACTIVO', fecha_vigencia: hoy, estado: 'ACTIVO' }];
  const vars = [], med = new Map(), audit = [], eventos = new Map(), eventosHistoricos = new Map(), avisos = [];
  const rebaseProcesado = new Set(); let nextPrecio = 402, nextEvento = 301, ultimoActivo = null, verificado = false;
  const modoRebase = ['precio_distinto_calculo_previo', 'caso001_rebase_precio', 'caso002_rebase_precio'].includes(modo);
  const requiereRebase = aid => modoRebase && [101, 102].includes(aid);
  if (modo === 'notificacion_externa') avisos.push({ id_notificacion: 1,
    mensaje: 'Hay un nuevo precio de mercado vigente. Aviso NIC41 anterior al ensayo.' });
  const consultasPrecio = [], solicitudesPoscierre = [], operacionesCaso002 = []; let cierreIntentado = false;
  const tipo = ['GANANCIA_TRANSFORMACION_BIOLOGICA', 'PERDIDA_TRANSFORMACION_BIOLOGICA',
    'GANANCIA_TRANSFORMACION_BIOLOGICA', 'GANANCIA_PRECIO_MERCADO'];
  const send = (res, code, data, run) => { res.writeHead(code, { 'Content-Type': 'application/json', ...(run ? { 'X-Test-Run-Id': run } : {}) });
    res.end(JSON.stringify(modo === 'con_campos_inyectados' && data && !Array.isArray(data) ?
      { ...data, campo_inyectado: 'IGNORAR' } : data)); };
  const server = http.createServer(async (req, res) => {
    const u = new URL(req.url, 'http://localhost'); const run = req.headers['x-test-run-id'];
    if (cierreIntentado && req.method !== 'DELETE') solicitudesPoscierre.push({ metodo: req.method, ruta: u.pathname });
    const body = await new Promise(resolve => { let s = ''; req.on('data', x => s += x); req.on('end', () => { try { resolve(JSON.parse(s || '{}')); } catch { resolve({}); } }); });
    if (req.method === 'POST' && u.pathname === '/sesiones/') return send(res, 200, { token: 'local-token' });
    if (req.method === 'DELETE' && u.pathname.startsWith('/test-control/runs/')) {
      cierreIntentado = true;
      if (['delete_sin_secreto', 'delete_error_400'].includes(modo) && req.headers['x-sandbox-secret'] !== 'secreto-local')
        return send(res, 400, { error_code: 'VAL_ENTRADA' });
      if (modo === 'delete_error_400') return send(res, 400, { error_code: 'CIERRE_RECHAZADO' });
      precios.splice(1); vars.length = 0; eventos.clear(); eventosHistoricos.clear(); med.clear(); audit.length = 0;
      activos[1].estado = 'ACTIVO';
      return send(res, 200, { ok: true });
    }
    if (req.method === 'GET' && u.pathname === '/notificaciones' && modo === 'bandeja_no_disponible')
      return send(res, 403, { error_code: 'SIN_LECTURA_BANDEJA' }, run);
    if (req.method === 'GET' && u.pathname === '/notificaciones') return send(res, 200,
      { total: avisos.length, no_leidas: avisos.length, pagina: 1, tamano: 50,
        items: [...avisos].reverse().slice(0, 50) }, run);
    if (req.method === 'GET' && u.pathname === '/finanzas/activos') return send(res, 200, activos, run);
    if (req.method === 'GET' && u.pathname === '/finanzas/periodos') return send(res, 200,
      ['periodo_cerrado_con_posterior_abierto', 'periodo_en_cierre'].includes(modo) ? [
        { id_periodo_contable: 200, numero_id_tributaria: '123', estado: modo === 'periodo_en_cierre' ? 'EN_CIERRE' : 'CERRADO',
          fecha_inicio: `${mesActual}-01`, fecha_fin: finMes(mesActual) },
        { id_periodo_contable: 201, numero_id_tributaria: '123', estado: 'ABIERTO',
          fecha_inicio: `${mesSiguiente}-01`, fecha_fin: finMes(mesSiguiente) }] :
        [{ id_periodo_contable: 201, numero_id_tributaria: '123', estado: 'ABIERTO',
          fecha_inicio: hoy.slice(0, 4) + '-01-01', fecha_fin: hoy.slice(0, 4) + '-12-31' },
        { id_periodo_contable: 7, numero_id_tributaria: 'NIT-A', estado: 'CERRADO',
          fecha_inicio: `${mesActual}-01`, fecha_fin: finMes(mesActual) },
        { id_periodo_contable: 8, numero_id_tributaria: 'NIT-A', estado: modo === 'periodo8_en_cierre' ? 'EN_CIERRE' : 'ABIERTO',
          fecha_inicio: `${mesSiguiente}-01`, fecha_fin: finMes(mesSiguiente) }], run);
    if (req.method === 'GET' && u.pathname === '/finanzas/configuracion') return send(res, 200,
      { matriz: [
        { id_asignacion_cuenta_contable: 12, tipo_hecho: 'VARIACION_VR_TB', sentido: 'GANANCIA', id_especie: null, subtipo_costo: null, cuenta_debito: '158405', cuenta_credito: '424805' },
        { id_asignacion_cuenta_contable: 13, tipo_hecho: 'VARIACION_VR_TB', sentido: 'PERDIDA', id_especie: null, subtipo_costo: null, cuenta_debito: '539505', cuenta_credito: '158405' },
        ...(modo === 'sin_pm_matriz' ? [] : [
          { id_asignacion_cuenta_contable: 17, tipo_hecho: 'VARIACION_VR_PM', sentido: 'GANANCIA', id_especie: null, subtipo_costo: null, cuenta_debito: '158405', cuenta_credito: '424805' },
          { id_asignacion_cuenta_contable: 18, tipo_hecho: 'VARIACION_VR_PM', sentido: 'PERDIDA', id_especie: null, subtipo_costo: null, cuenta_debito: '539505', cuenta_credito: '158405' }])
      ] }, run);
    if (req.method === 'GET' && u.pathname === '/finanzas/precios') {
      consultasPrecio.push(u.search);
      if (!u.searchParams.has('id_especie') && modo === 'precios_general_500')
        return send(res, 500, { error_code: 'ERROR_INTERNO' }, run);
      if (u.searchParams.has('id_especie') && modo === 'precios_filtrado_500')
        return send(res, 500, { error_code: 'ERROR_INTERNO' }, run);
      return send(res, 200, precios.filter(p => p.id_especie === Number(u.searchParams.get('id_especie'))), run);
    }
    if (req.method === 'POST' && u.pathname === '/finanzas/precios') {
      const p = { ...body, id_precio_mercado: nextPrecio++, estado: 'ACTIVO' }; precios.push(p);
      avisos.push({ id_notificacion: avisos.length + 1, mensaje: 'Hay un nuevo precio de mercado vigente. Aviso NIC41.' });
      return send(res, 201, { id_precio_mercado: p.id_precio_mercado, estado: 'ACTIVO' }, run);
    }
    let m = u.pathname.match(/^\/finanzas\/activos\/(\d+)$/);
    if (req.method === 'GET' && m) { const a = activos.find(x => x.id_activo_biologico === Number(m[1]));
      return send(res, 200, { activo: a, valoracion_costo: [], reconocimientos: [{ estado: 'CONFIRMADO' }], calculos: [{ id_calculo_valor_razonable: 100 + a.id_activo_biologico,
        id_precio_mercado: rebaseProcesado.has(a.id_activo_biologico) ? 401 :
          modoRebase ? 400 : 401,
        magnitud: 400, unidad_magnitud: 'kg', valor_neto: 1000, estado: 'CALCULADO', fecha_calculo: hoy }],
        mediciones: med.get(a.id_activo_biologico) ?? [] }, run); }
    m = u.pathname.match(/^\/activos-biologicos\/(\d+)\/ficha-integral$/);
    if (req.method === 'GET' && m) return send(res, 200,
      { peso_actual: 400, unidad_peso: 'kg', estado_actual: activos.find(x => x.id_activo_biologico === Number(m[1]))?.estado }, run);
    m = u.pathname.match(/^\/activos-biologicos\/(\d+)\/estado$/);
    if (req.method === 'PATCH' && m) { if (Number(m[1]) === 102) operacionesCaso002.push('PATCH');
      activos.find(x => x.id_activo_biologico === Number(m[1])).estado = body.estado_nuevo;
      return send(res, 200, { estado_nuevo: body.estado_nuevo }, run); }
    m = u.pathname.match(/^\/activos-biologicos\/(\d+)\/eventos\/crecimiento$/);
    if (req.method === 'POST' && m) { const aid = Number(m[1]);
      if (aid === 102) operacionesCaso002.push('PESAJE');
      if (activos.find(x => x.id_activo_biologico === aid)?.estado !== 'ACTIVO')
        return send(res, 409, { error_code: 'ESTADO_NO_PERMITE_EVENTOS' }, run);
      const eid = nextEvento++; eventos.set(aid, eid); ultimoActivo = aid;
      eventosHistoricos.set(aid, [...(eventosHistoricos.get(aid) ?? []), eid]);
      return send(res, 201, { evento: { id_eventos: eid } }, run); }
    m = u.pathname.match(/^\/activos-biologicos\/(\d+)\/eventos$/);
    if (req.method === 'GET' && m) return send(res, 200,
      { eventos: (eventosHistoricos.get(Number(m[1])) ?? []).map(eid => ({ id_eventos: eid })) }, run);
    if (req.method === 'POST' && u.pathname === '/finanzas/eventos/procesar') {
      const aid = ultimoActivo, i = aid - 101, eid = eventos.get(aid);
      if (aid === 102) operacionesCaso002.push('PROCESAR');
      if (requiereRebase(aid) && !rebaseProcesado.has(aid)) {
        rebaseProcesado.add(aid);
        vars.push({ id_variacion_valor_razonable: 501 + vars.length, id_activo_biologico: aid,
          tipo: 'GANANCIA_PRECIO_MERCADO', monto_variacion: 80,
          valor_razonable_anterior: 1000, valor_razonable_nuevo: 1080,
          fecha_registro: new Date().toISOString(), estado_trazabilidad: 'VERIFICACION_PENDIENTE',
          id_linea: 601 + vars.length, _evento: eid, _precio: 401 });
        return send(res, 200, { eventos: { procesados: 1 } }, run);
      }
      if (modo === 'tratamiento_rechazado' && i === 1)
        return send(res, 409, { error_code: 'ESTADO_NO_ADMITIDO_M06' }, run);
      if (modo === 'error5xx' && i === 1) return send(res, 500, { error_code: 'LOCAL_5XX' }, run);
      if (modo === 'sin_respuesta' && i === 1) return req.socket.destroy();
      if (!(modo === 'tratamiento_rechazado' && i === 1)) {
        const tb = [20, -20, 92, 0][i];
        const pm = [0, 0, -80, 80][i];
        med.set(aid, [{ id_medicion_posterior: 701 + i, id_evento: eid, ganancia_perdida_transformacion: tb,
          ganancia_perdida_precio_mercado: pm, variacion_total: tb + pm,
          valor_razonable_anterior: 1000, valor_razonable_actual: 1000 + tb + pm }]);
        const add = (t, monto) => { const vid = 501 + vars.length, v = {
          id_variacion_valor_razonable: vid, id_activo_biologico: aid, tipo: t,
          monto_variacion: modo === 'monto_recalculado' && i === 0 ? monto - 10 : monto,
          valor_razonable_anterior: 1000, valor_razonable_nuevo: 1000 + tb + pm,
          fecha_registro: new Date().toISOString(), estado_trazabilidad:
            modo === 'estado_inicial_distinto' && i === 0 ? 'VERIFICADO' : 'VERIFICACION_PENDIENTE',
          id_linea: vid + 100, _evento: eid,
          _precio: i >= 2 ? precios.at(-1).id_precio_mercado : 401 };
          vars.push(v); audit.push({ tipo_evento: 'VARIACION_REGISTRADA', id_referencia: vid,
            tipo_actor: 'SISTEMA', id_usuario: null, id_sistema: 'M06_PROCESO_AUTOMATICO' }); };
        add(tipo[i], i === 3 ? pm : tb);
        if (i === 0 && modo === 'pm_creado_en_tb') add('GANANCIA_PRECIO_MERCADO', 1);
        if (i === 2 && modo !== 'un_solo_registro') add('PERDIDA_PRECIO_MERCADO', pm);
        if (i === 3 && modo === 'tb_creado_sin_cambio') add('GANANCIA_TRANSFORMACION_BIOLOGICA', 1);
      }
      return send(res, 200, { eventos: { procesados: 1 } }, run);
    }
    m = u.pathname.match(/^\/finanzas\/periodos\/(\d+)\/variaciones$/);
    if (req.method === 'GET' && m && Number(m[1]) === 7) return send(res, 200,
      [{ id_variacion_valor_razonable: 900 }], run);
    if (req.method === 'GET' && m) return send(res, 200, vars.map(({ _evento, _precio, ...v }) =>
      modo === 'trazabilidad_500_no_bloquea' ? { ...v, evento_origen_id: v.tipo.includes('PRECIO') ? null : _evento,
        id_precio_mercado: v.tipo.includes('PRECIO') ? _precio : null } : v), run);
    m = u.pathname.match(/^\/finanzas\/periodos\/(\d+)\/mediciones$/);
    if (req.method === 'GET' && m) return send(res, 200,
      [...med.values()].flat().map(x => ({ id_medicion_posterior: x.id_medicion_posterior, estado: 'COMPLETADO' })), run);
    if (req.method === 'GET' && u.pathname === '/finanzas/lineas' && u.searchParams.get('id_periodo_contable') === '8')
      return send(res, 200, modo === 'sin_conflicto8' ? [] : [{ id_linea_asiento_nic41: 9, id_origen: 900,
        tabla_origen: 'variaciones_valor_razonable', estado_trazabilidad: 'PENDIENTE_TRAZABILIDAD' }], run);
    if (req.method === 'GET' && u.pathname === '/finanzas/lineas') return send(res, 200,
      vars.map(x => ({ id_linea_asiento_nic41: x.id_linea, id_origen: x.id_variacion_valor_razonable,
        tipo_hecho: x.tipo.includes('PRECIO') ? 'VARIACION_VR_PM' : 'VARIACION_VR_TB' })), run);
    m = u.pathname.match(/^\/finanzas\/periodos\/(\d+)\/trazabilidad$/);
    if (req.method === 'POST' && m) {
      if (modo === 'v1_500') return send(res, 500, { error_code: 'ERROR_INTERNO' }, run);
      if (Number(m[1]) === 8 && modo === 'v1_409') return send(res, 409,
        { error_code: 'PERIODO_NO_ABIERTO', message: 'Condición cambió' }, run);
      if (modo === 'verificacion_500_origen_rechazado')
        return send(res, 500, { error_code: 'ERROR_INTERNO' }, run);
      verificado = true;
      return send(res, 200, { verificadas: vars.length,
        pendientes: Number(m[1]) === 8 ? [{ id_linea: 9, motivo: 'No se pudo registrar la verificación' }] : [] }, run);
    }
    m = u.pathname.match(/^\/finanzas\/lineas\/(\d+)\/cadena$/);
    if (req.method === 'GET' && m) { if (modo === 'trazabilidad_500_no_bloquea')
      return send(res, 500, { error_code: 'CADENA_NO_DISPONIBLE' }, run);
      const v = vars.find(x => x.id_linea === Number(m[1]));
      return send(res, 200, { id_origen: v.id_variacion_valor_razonable, eslabones: { ids: modo === 'sin_ids_origen' ? {} : verificado ? {
        id_evento: modo === 'origen_distinto' && v.id_activo_biologico === 101 ? 9999 :
          v.tipo.includes('PRECIO') && modo !== 'pm_trazado_a_m02' ? null : v._evento,
        id_precio_mercado: v._precio } : {} } }, run); }
    if (req.method === 'GET' && u.pathname === '/finanzas/auditoria') return send(res, 200,
      { eventos: audit.filter(x => vars.find(v => v.id_variacion_valor_razonable === x.id_referencia)?.id_activo_biologico === Number(u.searchParams.get('id_activo_biologico'))) }, run);
    send(res, 404, { error_code: 'NO_ENCONTRADO' }, run);
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  return { server, url: `http://127.0.0.1:${server.address().port}`, consultasPrecio, solicitudesPoscierre, operacionesCaso002 };
}
if (process.argv[2] === '--servidor') {
  assert.equal(process.argv[3], 'todo_ok');
  const { url } = await servidor('todo_ok');
  process.stdout.write(`${url}\n`);
  await new Promise(() => {});
} else {
for (const modo of MODOS) {
  const { server, url, solicitudesPoscierre } = await servidor(modo);
  try {
    const env = { SIGAB_API_TEST_BASE: url, QA_SANDBOX_SECRET: 'secreto-local',
      QA_CONTADOR_EMAIL: 'contador@ejemplo.test', QA_CONTADOR_PASSWORD: 'clave-local',
      QA_ADMIN_EMAIL: 'admin@ejemplo.test', QA_ADMIN_PASSWORD: 'clave-admin', QA_AUTORIZADO: 'SI' };
    const c = { runId: 'RUN-G32-V2-20261111-000000', version: 2, intento: 1,
      operacion: 'reevaluar', version_anterior: 1, referencia: 'AUT-G32-V2-20261111', ensayo: true };
    const r = await evaluar(c, { env, apiOverride: url, sinArtefactos: true });
    const estados = CASOS.map(k => r.casos[k].estado);
    const noDatos = ['periodo_cerrado_con_posterior_abierto', 'sin_precondicion', 'sin_pm_matriz'].includes(modo);
    assert.deepEqual(estados, noDatos ? Array(4).fill('NO_CONCLUYENTE') :
      ['v1_500', 'sin_ids_origen'].includes(modo) ? Array(4).fill('RECHAZADO') :
      modo === 'origen_distinto' ? ['RECHAZADO','APROBADO','APROBADO','APROBADO'] :
      modo === 'estado_inicial_distinto' ? ['RECHAZADO','APROBADO','APROBADO','APROBADO'] :
      modo === 'tratamiento_rechazado' ? ['APROBADO','NO_CONCLUYENTE','APROBADO','APROBADO'] :
      Array(4).fill('APROBADO'), modo);
    assert.equal(r.cierre.run.cierre_http, modo === 'delete_error_400' ? 400 : 200);
    assert.equal(r.oficial, !noDatos && !['delete_error_400', 'tratamiento_rechazado'].includes(modo));
    assert.ok(r.solicitudes.length <= PRESUPUESTO.solicitudes_totales);
    assert.ok(r.solicitudes.every(x => !x.ruta.startsWith('http')), 'solo loopback local');
    assert.equal(r.preflight.requisitos.length, 5);
    assert.ok(r.preflight.requisitos.every(x => typeof x.cumple === 'boolean' && typeof x.bloqueante === 'boolean'));
    const matriz = r.preflight.requisitos.find(x => x.requisito === 'matriz_tb_pm_activa');
    assert.equal(matriz.cumple, modo !== 'sin_pm_matriz', modo);
    if (modo === 'sin_pm_matriz') assert.deepEqual(matriz.observado.tipos, ['VARIACION_VR_TB']);
    if (noDatos) assert.equal(r.solicitudes.filter(x => ['POST','PATCH'].includes(x.metodo) && x.ruta !== '/sesiones/').length, 0);
    if (modo === 'periodo_cerrado_con_posterior_abierto') assert.equal(r.diagnostico_candidatos.periodo_destino, 0);
    if (modo === 'sin_precondicion') assert.match(r.casos[CASOS[0]].motivo, /cuatro_bovinos_elegibles/);
    if (modo === 'todo_ok') {
      assert.equal(r.seguimiento_incidencias_v1[0].estado_v2, 'CORREGIDA');
      assert.equal(r.consultas_cadena.length, 5);
      assert.ok(r.consultas_cadena.every(x => x.cuerpo_saneado && x.ids_observados));
      assert.equal(r.verificaciones_trazabilidad.length, 2);
      assert.match(informe(c, r), /## Preflight vivo[\s\S]*Seguimiento de incidencias V1/);
      assert.match(informe(c, r), /ambiente SIMULADOR_LOCAL/);
      assert.doesNotMatch(informe(c, r), /primer período ABIERTO posterior/);
    }
    if (['v1_500', 'sin_ids_origen'].includes(modo))
      assert.equal(r.seguimiento_incidencias_v1[0].estado_v2, 'REPRODUCIDA');
    if (modo === 'v1_500') assert.ok(r.incidencias.every(x => x.severidad === 'ALTA'));
    if (modo === 'estado_inicial_distinto') assert.equal(r.incidencias[0].severidad, 'MEDIA');
    if (modo === 'sin_conflicto8') assert.equal(r.seguimiento_incidencias_v1[0].estado_v2, 'NO_REPRODUCIDA');
    if (modo === 'periodo8_en_cierre') {
      assert.equal(r.seguimiento_incidencias_v1[0].estado_v2, 'NO_REPRODUCIDA');
      assert.match(r.seguimiento_incidencias_v1[0].motivo, /condición ausente: período 8 en estado EN_CIERRE/i);
    }
    if (modo === 'v1_409') assert.equal(r.seguimiento_incidencias_v1[0].estado_v2, 'NO_CONCLUYENTE');
    if (modo === 'sin_ids_origen') assert.ok(r.consultas_cadena.every(x => x.ids_observados &&
      x.ids_observados.id_evento === null && x.ids_observados.id_precio_mercado === null));
    if (modo === 'delete_error_400') assert.equal(solicitudesPoscierre.length, 0);
    const copia = JSON.parse(JSON.stringify(r));
    copia.herramientas.newman = { iteraciones: 1, fallos: 0 };
    copia.evidencias = ['resultado.json', 'TC-M06-G32_reevaluacion_V2.md', 'newman/newman-G32.json', 'newman/newman-G32.html'];
    for (const x of copia.comprobaciones) x.evidencia = 'resultado.json';
    assert.equal(clasificarRegistro(CAPACIDADES, copia, new Set(copia.evidencias), c), r.oficial);
    assert.match(informe(c, r), /AUT-G32-V2-20261111/);
    assert.match(informe(c, r), /Efecto persistente declarado bajo la autorización de este RUN \(AUT-G32-V2-20261111\) y su SOL de V2/);
    assert.doesNotMatch(informe(c, r), /2026-11-07/);
  } finally { await new Promise(resolve => server.close(resolve)); }
}
const sonda = http.createServer((req, res) => {
  res.writeHead(200, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify({ ok: req.url === '/newman-probe' }));
});
await new Promise(resolve => sonda.listen(0, '127.0.0.1', resolve));
let newmanEjecutable = false;
try {
  const url = `http://127.0.0.1:${sonda.address().port}/newman-probe`;
  const entrada = JSON.stringify({ coleccion: { info: { name: 'G32 sonda local',
    _postman_id: 'g32-local', schema: 'https://schema.getpostman.com/json/collection/v2.1.0/collection.json' },
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
    newmanEjecutable = true;
    console.log('OK newman_hijo: process.execPath, 1 lectura loopback HTTP 200');
  }
} finally { await new Promise(resolve => sonda.close(resolve)); }
if (newmanEjecutable) {
  const hijo = spawn(process.execPath, [fileURLToPath(import.meta.url), '--servidor', 'todo_ok'],
    { stdio: ['ignore', 'pipe', 'pipe'], windowsHide: true });
  let hijoCerrado = false;
  hijo.on('close', () => { hijoCerrado = true; });
  try {
  const url = await new Promise((resolve, reject) => {
    let salida = '', error = '';
    hijo.stdout.on('data', b => {
      salida += b.toString();
      const linea = salida.split(/\r?\n/, 1)[0];
      if (salida.includes('\n')) {
        if (/^http:\/\/127\.0\.0\.1:\d+$/.test(linea)) resolve(linea);
        else reject(Error(`Servidor A4 entregó puerto inválido: ${linea}`));
      }
    });
    hijo.stderr.on('data', b => { error += b.toString(); });
    hijo.on('error', reject);
    hijo.on('close', codigo => reject(Error(`Servidor A4 terminó antes de iniciar (${codigo}): ${error}`)));
  });
    const ejemplo = path.join(os.tmpdir(), 'g32-verificar-ejemplo');
    fs.rmSync(ejemplo, { recursive: true, force: true });
    const runId = `RUN-G32-V2-${new Intl.DateTimeFormat('en-CA', { timeZone: 'America/Bogota',
      year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date()).replaceAll('-', '')}-${
      new Date().toISOString().slice(11, 19).replaceAll(':', '')}`;
    const directorio = path.join(ejemplo, runId);
    fs.mkdirSync(directorio, { recursive: true });
    const env = { SIGAB_API_TEST_BASE: url, QA_SANDBOX_SECRET: 'secreto-local',
      QA_CONTADOR_EMAIL: 'contador@ejemplo.test', QA_CONTADOR_PASSWORD: 'clave-local',
      QA_ADMIN_EMAIL: 'admin@ejemplo.test', QA_ADMIN_PASSWORD: 'clave-admin', QA_AUTORIZADO: 'SI' };
    const c = { runId, directorio, version: 2, intento: 1, operacion: 'reevaluar',
      version_anterior: 1, referencia: 'ENSAYO_LOCAL', ensayo: true };
    const r = await evaluar(c, { env, apiOverride: url });
    fs.writeFileSync(path.join(ejemplo, 'capacidades.json'), JSON.stringify(CAPACIDADES, null, 2));
    if (r.oficial) {
      const presentes = new Set(r.evidencias.filter(x => fs.existsSync(path.join(directorio, x))));
      assert.ok(clasificarRegistro(CAPACIDADES, r, presentes, c));
      console.log(`OK ejemplo local V2: ${directorio}`);
      console.log(`resultado.json: ${path.join(directorio, 'resultado.json')}`);
      console.log(`capacidades.json: ${path.join(ejemplo, 'capacidades.json')}`);
    } else console.log(`Ejemplo local V2 no oficial: ${JSON.stringify({
      casos: Object.fromEntries(CASOS.map(k => [k, { estado: r.casos[k]?.estado, motivo: r.casos[k]?.motivo }])),
      cierre_http: r.cierre?.run?.cierre_http, rollback: r.cierre?.run,
      newman_fallos: r.herramientas?.newman?.fallos
    })}`);
  } finally {
    if (!hijoCerrado) {
      const cierre = new Promise(resolve => hijo.once('close', resolve));
      hijo.kill();
      await cierre;
    }
  }
}
assert.deepEqual(archivosGrupo().filter(x => !archivosIniciales.has(x)), [],
  'El ensayo dejó archivos nuevos dentro de G32');
assert.equal(intentosRemotos, 0, 'El ensayo intentó una conexión remota');
console.log(`OK G32: ${MODOS.length}/${MODOS.length} modos; aislamiento y cierre comprobados; registro QA fiel`);
}
