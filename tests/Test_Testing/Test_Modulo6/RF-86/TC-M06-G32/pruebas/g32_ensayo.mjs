import assert from 'node:assert/strict';
import fs from 'node:fs';
import http from 'node:http';
import path from 'node:path';
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

const MODOS = ['todo_ok', 'notificacion_externa', 'bandeja_no_disponible', 'monto_recalculado', 'pm_creado_en_tb', 'tratamiento_rechazado',
  'pm_trazado_a_m02', 'un_solo_registro', 'tb_creado_sin_cambio', 'sin_precondicion',
  'error5xx', 'sin_respuesta', 'sin_tratamiento', 'delete_sin_secreto', 'delete_error_400',
  'precios_general_500', 'precios_filtrado_500', 'periodo_cerrado_con_posterior_abierto',
  'periodo_en_cierre', 'precio_distinto_calculo_previo', 'diagnostico_conteos',
  'trazabilidad_500_no_bloquea', 'caso002_pesaje_antes_de_tratamiento', 'evidencia_por_caso',
  'verificacion_500_origen_rechazado', 'verificacion_200_origen_ok', 'caso002_rebase_precio', 'origen_distinto',
  'caso001_rebase_precio', 'detalle_legible'];
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
  const send = (res, code, data, run) => { res.writeHead(code, { 'Content-Type': 'application/json', ...(run ? { 'X-Test-Run-Id': run } : {}) }); res.end(JSON.stringify(data)); };
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
          fecha_inicio: hoy.slice(0, 4) + '-01-01', fecha_fin: hoy.slice(0, 4) + '-12-31' }], run);
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
      return send(res, 200, { activo: a, calculos: [{ id_calculo_valor_razonable: 100 + a.id_activo_biologico,
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
          fecha_registro: new Date().toISOString(), estado_trazabilidad: 'VERIFICACION_PENDIENTE',
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
    if (req.method === 'GET' && m) return send(res, 200, vars.map(({ _evento, _precio, ...v }) =>
      modo === 'trazabilidad_500_no_bloquea' ? { ...v, evento_origen_id: v.tipo.includes('PRECIO') ? null : _evento,
        id_precio_mercado: v.tipo.includes('PRECIO') ? _precio : null } : v), run);
    m = u.pathname.match(/^\/finanzas\/periodos\/(\d+)\/mediciones$/);
    if (req.method === 'GET' && m) return send(res, 200,
      [...med.values()].flat().map(x => ({ id_medicion_posterior: x.id_medicion_posterior, estado: 'COMPLETADO' })), run);
    if (req.method === 'GET' && u.pathname === '/finanzas/lineas') return send(res, 200,
      vars.map(x => ({ id_linea_asiento_nic41: x.id_linea, id_origen: x.id_variacion_valor_razonable,
        tipo_hecho: x.tipo.includes('PRECIO') ? 'VARIACION_VR_PM' : 'VARIACION_VR_TB' })), run);
    m = u.pathname.match(/^\/finanzas\/periodos\/(\d+)\/trazabilidad$/);
    if (req.method === 'POST' && m) {
      if (modo === 'verificacion_500_origen_rechazado')
        return send(res, 500, { error_code: 'ERROR_INTERNO' }, run);
      verificado = true;
      return send(res, 200, { verificadas: vars.length }, run);
    }
    m = u.pathname.match(/^\/finanzas\/lineas\/(\d+)\/cadena$/);
    if (req.method === 'GET' && m) { if (modo === 'trazabilidad_500_no_bloquea')
      return send(res, 500, { error_code: 'CADENA_NO_DISPONIBLE' }, run);
      const v = vars.find(x => x.id_linea === Number(m[1]));
      return send(res, 200, { id_origen: v.id_variacion_valor_razonable, eslabones: { ids: verificado ? {
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
for (const modo of MODOS) {
  const { server, url, consultasPrecio, solicitudesPoscierre, operacionesCaso002 } = await servidor(modo);
  try {
    const env = { SIGAB_API_TEST_BASE: url, QA_SANDBOX_SECRET: 'secreto-local',
      QA_CONTADOR_EMAIL: 'contador@ejemplo.test', QA_CONTADOR_PASSWORD: 'clave-local',
      QA_ADMIN_EMAIL: 'admin@ejemplo.test', QA_ADMIN_PASSWORD: 'clave-admin', QA_AUTORIZADO: 'SI' };
    const c = { runId: 'RUN-G32-V1-20261107-000000', version: 1, intento: 1, referencia: 'ENSAYO_LOCAL', ensayo: true };
    const r = await evaluar(c, { env, apiOverride: url, sinArtefactos: true });
    assert.ok(r.solicitudes.length <= PRESUPUESTO.solicitudes_totales, `${modo}: presupuesto de solicitudes excedido`);
    const estados = ['TC-M06-001', 'TC-M06-002', 'TC-M06-003', 'TC-M06-004'].map(k => r.casos[k].estado);
    const esperado = {
      todo_ok: ['APROBADO', 'APROBADO', 'APROBADO', 'APROBADO'],
      notificacion_externa: ['APROBADO', 'APROBADO', 'APROBADO', 'APROBADO'],
      bandeja_no_disponible: ['APROBADO', 'APROBADO', 'APROBADO', 'APROBADO'],
      monto_recalculado: ['RECHAZADO', 'APROBADO', 'APROBADO', 'APROBADO'],
      pm_creado_en_tb: ['RECHAZADO', 'APROBADO', 'APROBADO', 'APROBADO'],
      tratamiento_rechazado: ['APROBADO', 'RECHAZADO', 'APROBADO', 'APROBADO'],
      pm_trazado_a_m02: ['APROBADO', 'APROBADO', 'RECHAZADO', 'RECHAZADO'],
      un_solo_registro: ['APROBADO', 'APROBADO', 'RECHAZADO', 'APROBADO'],
      tb_creado_sin_cambio: ['APROBADO', 'APROBADO', 'APROBADO', 'RECHAZADO'],
      sin_precondicion: ['APROBADO', 'APROBADO', 'APROBADO', 'BLOQUEADO'],
      error5xx: ['APROBADO', 'BLOQUEADO', 'APROBADO', 'APROBADO'],
      sin_respuesta: ['APROBADO', 'NO_CONCLUYENTE', 'APROBADO', 'APROBADO'],
      sin_tratamiento: ['APROBADO', 'APROBADO', 'APROBADO', 'APROBADO'],
      delete_sin_secreto: ['APROBADO', 'APROBADO', 'APROBADO', 'APROBADO'],
      delete_error_400: ['APROBADO', 'APROBADO', 'APROBADO', 'APROBADO'],
      precios_general_500: ['APROBADO', 'APROBADO', 'APROBADO', 'APROBADO'],
      precios_filtrado_500: ['BLOQUEADO', 'BLOQUEADO', 'BLOQUEADO', 'BLOQUEADO'],
      periodo_cerrado_con_posterior_abierto: ['APROBADO', 'APROBADO', 'APROBADO', 'APROBADO'],
      periodo_en_cierre: ['BLOQUEADO', 'BLOQUEADO', 'BLOQUEADO', 'BLOQUEADO'],
      precio_distinto_calculo_previo: ['APROBADO', 'APROBADO', 'APROBADO', 'APROBADO'],
      diagnostico_conteos: ['APROBADO', 'APROBADO', 'APROBADO', 'APROBADO'],
      trazabilidad_500_no_bloquea: ['RECHAZADO', 'RECHAZADO', 'RECHAZADO', 'RECHAZADO'],
      caso002_pesaje_antes_de_tratamiento: ['APROBADO', 'APROBADO', 'APROBADO', 'APROBADO'],
      evidencia_por_caso: ['APROBADO', 'APROBADO', 'APROBADO', 'APROBADO'],
      verificacion_500_origen_rechazado: ['RECHAZADO', 'RECHAZADO', 'RECHAZADO', 'RECHAZADO'],
      verificacion_200_origen_ok: ['APROBADO', 'APROBADO', 'APROBADO', 'APROBADO'],
      caso002_rebase_precio: ['APROBADO', 'APROBADO', 'APROBADO', 'APROBADO'],
      origen_distinto: ['RECHAZADO', 'APROBADO', 'APROBADO', 'APROBADO'],
      caso001_rebase_precio: ['APROBADO', 'APROBADO', 'APROBADO', 'APROBADO'],
      detalle_legible: ['APROBADO', 'APROBADO', 'APROBADO', 'APROBADO'],
    }[modo];
    assert.deepEqual(estados, esperado, `${modo}: ${JSON.stringify(r.casos)}`);
    if (modo === 'tratamiento_rechazado')
      assert.match(r.casos['TC-M06-002'].motivo, /EN_TRATAMIENTO.*HTTP 409/);
    const verificaciones = r.solicitudes.filter(x => x.metodo === 'POST' && /\/trazabilidad$/.test(x.ruta));
    assert.equal(verificaciones.length, estados.every(x => x === 'BLOQUEADO') ? 0 : 1);
    if (verificaciones.length) assert.equal(r.verificaciones_trazabilidad.length, 1);
    if (modo === 'trazabilidad_500_no_bloquea') {
      assert.equal(r.observaciones_auxiliares.filter(x => x.http === 500).length, 5);
      assert.match(informe(c, r), /CADENA_NO_DISPONIBLE/);
      assert.equal(r.incidencias.length, 1);
    }
    if (modo === 'verificacion_500_origen_rechazado') {
      assert.ok(Object.values(r.casos).every(x => x.oraculo_inicial.estado === 'APROBADO'));
      assert.equal(r.verificaciones_trazabilidad[0].http, 500);
      assert.equal(r.verificaciones_trazabilidad[0].cuerpo_saneado, '{"error_code":"ERROR_INTERNO"}');
      assert.equal(r.incidencias.length, 1);
      assert.equal(r.incidencias[0].clave, 'ORIGEN');
      assert.equal(r.incidencias[0].equipo_inicial, 'Desarrollo');
      assert.ok(r.consultas_cadena.every(x => x.cuerpo_saneado &&
        x.ids_observados?.id_evento === null && x.ids_observados?.id_precio_mercado === null));
      assert.match(informe(c, r), /ERROR_INTERNO[\s\S]*\*\*Equipo inicial:\*\* Desarrollo/);
    }
    if (modo === 'verificacion_200_origen_ok') {
      assert.equal(r.verificaciones_trazabilidad[0].http, 200);
      assert.ok(r.consultas_cadena.length >= 5 && r.consultas_cadena.every(x =>
        x.http === 200 && x.cuerpo_saneado.includes('eslabones') && x.ids_observados));
      assert.ok(Object.values(r.casos).every(x => x.variaciones_observadas.every(v => v.origen_fuente.includes('tras POST RF-91'))));
    }
    if (modo === 'origen_distinto') {
      assert.equal(r.casos['TC-M06-001'].variaciones_observadas[0].evento_origen_id, 9999);
      assert.equal(r.incidencias.length, 1);
    }
    if (modo === 'caso002_rebase_precio') {
      assert.ok(r.casos['TC-M06-002'].rebase_precio);
      assert.equal(r.casos['TC-M06-002'].variaciones_observadas.length, 1);
      assert.deepEqual(operacionesCaso002, ['PESAJE', 'PROCESAR', 'PESAJE', 'PATCH', 'PROCESAR']);
    }
    if (['caso001_rebase_precio', 'precio_distinto_calculo_previo'].includes(modo)) {
      assert.ok(r.casos['TC-M06-001'].rebase_precio);
      assert.equal(r.casos['TC-M06-001'].variaciones_observadas.length, 1);
      assert.equal(r.casos['TC-M06-001'].medicion_rf83.precio_mercado, 0);
      assert.equal(r.solicitudes.filter(x => x.ruta === '/activos-biologicos/101/eventos/crecimiento' && x.metodo === 'POST').length, 2);
    }
    if (modo === 'detalle_legible') {
      const texto = informe(c, r);
      const seccion = texto.split('## Detalle por caso\n\n')[1].split('## Comprobaciones API')[0];
      assert.equal((seccion.match(/### TC-M06-G32 \/ TC-M06-00[1-4]/g) ?? []).length, 4);
      for (const titulo of ['Preparación', 'Esperado', 'Observado', 'Cumplido', 'Fallo y motivo', 'Decisión'])
        assert.match(seccion, new RegExp(`\\*\\*${titulo}:`));
      assert.doesNotMatch(seccion, /\"variaciones_observadas\"|\"valor_razonable_anterior\"|\. activo 10[1-4],/);
    }
    if (modo === 'caso002_pesaje_antes_de_tratamiento')
      assert.deepEqual(operacionesCaso002, ['PESAJE', 'PATCH', 'PROCESAR']);
    if (modo === 'evidencia_por_caso') for (const x of Object.values(r.casos)) {
      assert.ok(x.variaciones_observadas?.length && x.medicion_rf83 && x.valores_esperados_calculados);
      assert.match(informe(c, r), new RegExp(String(x.variaciones_observadas[0].id)));
    }
    assert.doesNotMatch(informe(c, r), /\.\.|Se preparó ningún evento/);
    if (modo === 'periodo_en_cierre') {
      assert.equal(r.diagnostico_candidatos.periodo_destino, 0);
      assert.match(r.casos['TC-M06-001'].motivo, /EN_CIERRE/);
      assert.match(informe(c, r), /^# TC-M06-G32 — BLOQUEADO/);
      assert.match(informe(c, r), /Newman: no se ejecutó porque no hubo casos ejecutables/);
    }
    if (modo === 'periodo_cerrado_con_posterior_abierto') {
      assert.equal(r.diagnostico_candidatos.periodo_destino, 4);
      assert.match(r.casos['TC-M06-001'].preparacion, /período 201/);
      assert.ok(r.solicitudes.filter(x => x.ruta === '/finanzas/periodos/201/variaciones').length >= 8);
      assert.ok(!r.solicitudes.some(x => x.ruta === '/finanzas/periodos/200/variaciones'));
    }
    if (modo === 'diagnostico_conteos') {
      assert.equal(r.diagnostico_candidatos.total_recibido, 4);
      assert.equal(r.diagnostico_candidatos.peso_kg, 4);
      assert.match(informe(c, r), /total_recibido: 4/);
    }
    assert.equal(r.cierre.run.cierre_http, modo === 'delete_error_400' ? 400 : 200);
    assert.equal(r.cierre.rollback.verificado, !['sin_respuesta', 'delete_error_400'].includes(modo));
    assert.ok(consultasPrecio.length >= 1 && consultasPrecio.every(x => x.includes('id_especie=')),
      `${modo}: los precios deben consultarse por especie`);
    if (modo === 'precios_general_500') assert.equal(consultasPrecio.filter(x => x === '').length, 0);
    if (modo === 'precios_filtrado_500') {
      assert.equal(consultasPrecio.length, 1, 'una consulta para la única especie candidata');
      assert.equal(r.impedimentos_precios[0].http, 500);
      assert.equal(r.impedimentos_precios[0].cuerpo_saneado, '{"error_code":"ERROR_INTERNO"}');
      for (const k of Object.keys(r.casos)) assert.match(r.casos[k].motivo, /RF-89.*HTTP 500/);
      assert.match(informe(c, r), /Impedimentos observados en precios de mercado[\s\S]*ERROR_INTERNO[\s\S]*Desarrollo/);
    }
    if (modo === 'delete_error_400') {
      assert.equal(r.cierre.run.cuerpo_saneado, '{"error_code":"CIERRE_RECHAZADO"}');
      assert.equal(solicitudesPoscierre.length, 0, 'no debe haber lecturas después de DELETE fallido');
      assert.match(informe(c, r), /CIERRE_RECHAZADO[\s\S]*sin lecturas poscierre/);
    }
    const preciosEsperados = modo === 'sin_precondicion' ? [402] :
      ['precios_filtrado_500', 'periodo_en_cierre'].includes(modo) ? [] : [402, 403];
    assert.deepEqual(r.efectos_persistentes_declarados.id_precio_mercado, preciosEsperados);
    assert.equal(r.efectos_persistentes_declarados.precios_registrados, preciosEsperados.length);
    if (modo === 'bandeja_no_disponible')
      assert.equal(r.efectos_persistentes_declarados.bandeja_contador_qa.estado, 'NO_VERIFICABLE');
    else if (modo !== 'delete_error_400') assert.equal(r.efectos_persistentes_declarados.bandeja_contador_qa.avisos_observados, preciosEsperados.length);
    assert.equal(r.oficial, !['sin_respuesta', 'delete_error_400'].includes(modo) &&
      estados.every(x => ['APROBADO', 'RECHAZADO'].includes(x)));
    if (['todo_ok', 'notificacion_externa', 'bandeja_no_disponible', 'delete_sin_secreto', 'precios_general_500'].includes(modo))
      assert.equal(r.estado_ejecucion, 'OFICIAL_LOCAL');
    const copia = JSON.parse(JSON.stringify(r));
    assert.deepEqual(copia.comprobaciones.map(x => x.caso).sort(), [...CASOS].sort());
    copia.herramientas.newman = { iteraciones: 1 };
    copia.evidencias = ['resultado.json', 'TC-M06-G32_resultado.md', 'newman/newman-G32.json', 'newman/newman-G32.html'];
    for (const x of copia.comprobaciones) x.evidencia = 'resultado.json';
    const presentes = new Set(copia.evidencias);
    assert.equal(clasificarRegistro(CAPACIDADES, copia, presentes, c),
      r.cierre.rollback.verificado && estados.every(x => ['APROBADO', 'RECHAZADO'].includes(x)));
    if (modo === 'todo_ok') {
      copia.comprobaciones[0].caso = `TC-M06-G32 / ${CASOS[0]}`;
      assert.equal(clasificarRegistro(CAPACIDADES, copia, presentes, c), false,
        'el registro QA rechaza el identificador compuesto');
    }
  } finally { await new Promise(resolve => server.close(resolve)); }
}
const sonda = http.createServer((req, res) => {
  res.writeHead(200, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify({ ok: req.url === '/newman-probe' }));
});
await new Promise(resolve => sonda.listen(0, '127.0.0.1', resolve));
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
    console.log('OK newman_hijo: process.execPath, 1 lectura loopback HTTP 200');
  }
} finally { await new Promise(resolve => sonda.close(resolve)); }
assert.deepEqual(archivosGrupo().filter(x => !archivosIniciales.has(x)), [],
  'El ensayo dejó archivos nuevos dentro de G32');
console.log(`OK G32: ${MODOS.length}/${MODOS.length} modos; aislamiento y cierre comprobados; registro QA fiel`);
