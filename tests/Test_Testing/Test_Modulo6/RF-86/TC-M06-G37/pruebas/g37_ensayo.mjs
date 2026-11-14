import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import http from 'node:http';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { randomInt } from 'node:crypto';
import { principal, CAPACIDADES } from '../g37.mjs';
import { CASOS, CONTRATO, mock, oraculo011, oraculo013, periodoDestino } from '../lib/g37_core.mjs';
import { clasificarRegistro } from './registro_qa.mjs';

const DIR = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const TMP_EXAMPLE = path.join(os.tmpdir(), 'g37-verificar-ejemplo');
const pre = JSON.parse(fs.readFileSync(path.join(DIR, 'pruebas/precondicion_iot.json'), 'utf8'));
const hoy = () => new Intl.DateTimeFormat('en-CA', { timeZone: 'America/Bogota',
  year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date());
const copia = id => structuredClone(mock(id));
function respuesta(res, status, data, runId) {
  res.writeHead(status, { 'content-type': 'application/json', 'x-test-run-id': runId });
  res.end(JSON.stringify(data));
}
async function simular(escenario, conservar = false) {
  const base = fs.mkdtempSync(path.join(os.tmpdir(), 'g37-ensayo-v2-'));
  const runId = `RUN-G37-V2-20261112-${String(randomInt(1000000)).padStart(6, '0')}`;
  const dir = path.join(base, runId); fs.mkdirSync(dir);
  const referencia = 'AUT-LOCAL-SIMULADO';
  const contexto = path.join(dir, 'contexto_operacion.json');
  fs.writeFileSync(contexto, JSON.stringify({ grupo: 'G37', run_id: runId, version: 2,
    intento: 1, operacion: escenario === 'reintentar' ? 'REINTENTAR' : 'REEVALUAR',
    version_anterior: escenario === 'reintentar' ? null : 1,
    alcance_reevaluacion: { motivo: 'Simulación local V2', casos: CASOS }, referencia, casos: CASOS }));
  const estado = { borrado: false, escritos: 0, solicitudes: [], eventos: [], variaciones: [],
    lineas: [], auditorias: [], precios: [], verificado: false, siguiente: 1000 };
  const bovinos = [1831, 1627, 1832, 1833];
  let servidor;
  try {
    servidor = http.createServer(async (req, res) => {
      const u = new URL(req.url, 'http://127.0.0.1'), p = u.pathname, m = req.method;
      let body = ''; for await (const x of req) body += x;
      const registro = { metodo: m, ruta: p, run: req.headers['x-test-run-id'] ?? null };
      estado.solicitudes.push(registro);
      if (['POST','PATCH'].includes(m) && p !== '/sesiones/') estado.escritos++;
      let status = 200, data = null;
      const activo = Number(p.match(/\/activos-biologicos\/(\d+)/)?.[1]);
      if (p === '/sesiones/' && m === 'POST') data = { token: 'token-local-ficticio' };
      else if (p === '/sesiones/me/permisos') data = { permisos:
        Object.values(CONTRATO.roles).flatMap(rol => Object.entries(rol.permisos).flatMap(
          ([nombre_recurso, acciones]) => acciones.map(id_accion => ({ id_recurso: 1, id_accion, nombre_recurso })))) };
      else if (p === '/notificaciones') data = { items: [] };
      else if (p === '/finanzas/activos') data = bovinos.map(id => ({ ...copia('activos')[0],
        id_activo_biologico: id, id_especie: 10, especie: 'Bovino', tipo: 'INDIVIDUAL',
        estado: 'ACTIVO', valorado_por_costo: false }));
      else if (p === '/finanzas/periodos') data = [241,220].map(id => ({ ...copia('periodos')[0],
        id_periodo_contable: id, numero_id_tributaria: 'NIT-D',
        fecha_inicio: '2026-01-01', fecha_fin: '2026-12-31',
        estado: id === 241 && escenario === 'cerrado' ? 'CERRADO' : 'ABIERTO',
        ...(id === 241 && escenario === 'periodo_estado_invalido' ? { estado: 42 } : {}),
        ...(id === 241 && escenario === 'cierre_en_proceso' ? { ultimo_cierre: {
          paso_actual: 3, activos_procesados: null, activos_pendientes: null,
          activos_excluidos: null, precios_congelados: null, error_detalle: null,
          fecha_fin: null, tiempo_ejecucion_ms: null, hash_cierre: null } } : {}),
        ...(id === 241 && escenario === 'periodo_forma_extra' ? { ultimo_cierre: 42 } : {}) }));
      else if (/^\/finanzas\/activos\/\d+$/.test(p)) {
        data = copia('activo_detalle'); const id = Number(p.split('/').at(-1));
        data.activo.numero_id_tributaria = 'NIT-D';
        data.activo.id_dispositivo_iot = id === 1831 && escenario !== 'sin_dispositivo' ? 856 : null;
        data.calculos[0].estado = 'CALCULADO'; data.calculos[0].id_precio_mercado = 18;
        data.calculos[0].fecha_calculo = hoy();
      }
      else if (p.endsWith('/ficha-integral')) {
        data = copia('ficha'); data.peso_actual = '100.00'; data.unidad_peso = 'kg';
        data.estado_actual = estado.borrado ? 'ACTIVO' :
          estado.eventos.some(e => e.activo === activo && e.tratamiento) ? 'EN_TRATAMIENTO' : 'ACTIVO';
      }
      else if (p.endsWith('/eventos') && m === 'GET') {
        data = copia('eventos_get'); data.eventos = estado.borrado ? [] :
          estado.eventos.filter(e => e.activo === activo).map(e => ({ id_eventos: e.id }));
      }
      else if (p.endsWith('/eventos/crecimiento') && m === 'POST') {
        status = 201; data = copia('evento_crecimiento'); data.evento.id_eventos = ++estado.siguiente;
        estado.eventos.push({ id: data.evento.id_eventos, activo, procesado: false });
      }
      else if (p.endsWith('/estado') && m === 'PATCH') {
        data = copia('estado_patch'); const ev = [...estado.eventos].reverse().find(e => e.activo === activo);
        if (ev) ev.tratamiento = true;
      }
      else if (p === '/finanzas/precios' && m === 'GET') data = [{ ...copia('precios_get')[0],
        id_precio_mercado: 18, id_especie: 10, categoria: 'PESO_KG', fuente: 'MERCADO_ACTIVO',
        fecha_vigencia: '2026-01-01', fecha_vencimiento: '2026-12-31',
        precio_unitario: '18.00' }, ...(estado.borrado ? [] : estado.precios)];
      else if (p === '/finanzas/precios' && m === 'POST') {
        status = 201; data = copia('precios_post'); data.id_precio_mercado = ++estado.siguiente;
        estado.precios.push({ ...copia('precios_get')[0], id_precio_mercado: data.id_precio_mercado,
          id_especie: 10, categoria: 'PESO_KG', fuente: 'MERCADO_ACTIVO',
          fecha_vigencia: hoy(), fecha_vencimiento: '2026-12-31' });
      }
      else if (p === '/finanzas/eventos/procesar' && m === 'POST') {
        data = copia('procesar');
        for (const ev of estado.eventos.filter(e => !e.procesado)) {
          ev.procesado = true;
          const tipos = ev.activo === 1831 ? [['GANANCIA_TRANSFORMACION_BIOLOGICA','10.00']] :
            ev.activo === 1627 ? [['PERDIDA_TRANSFORMACION_BIOLOGICA','-4.00']] :
            ev.activo === 1832 ? [['GANANCIA_TRANSFORMACION_BIOLOGICA','5.00'],
              ['PERDIDA_PRECIO_MERCADO','-2.00']] : [['GANANCIA_PRECIO_MERCADO','8.00']];
          for (const [tipo, monto] of tipos) {
            const v = copia('variaciones')[0];
            Object.assign(v, { id_variacion_valor_razonable: ++estado.siguiente,
              id_activo_biologico: ev.activo, id_linea: ++estado.siguiente,
              tipo, monto_variacion: monto, estado_trazabilidad: 'VERIFICACION_PENDIENTE' });
            estado.variaciones.push(v);
            estado.lineas.push({ ...copia('lineas')[0], id_linea_asiento_nic41: v.id_linea });
            const a = copia('auditoria').eventos[0];
            Object.assign(a, { id_evento: ++estado.siguiente,
              id_referencia: v.id_variacion_valor_razonable, id_activo_biologico: ev.activo,
              id_periodo_contable: 241, tipo_evento: 'VARIACION_REGISTRADA', monto_afectado: monto });
            a.payload_evento = { tipo, monto, id_evento: ev.id, id_cierre: null };
            estado.auditorias.push(a);
          }
        }
      }
      else if (p === '/finanzas/periodos/241/variaciones') data = estado.borrado ? [] : estado.variaciones;
      else if (p === '/finanzas/periodos/241/mediciones') data = [];
      else if (p === '/finanzas/lineas') data = estado.borrado ? [] : estado.lineas;
      else if (/^\/finanzas\/lineas\/\d+\/cadena$/.test(p)) {
        data = copia('cadena'); data.id_linea_asiento_nic41 = Number(p.split('/')[3]);
        data.estado_trazabilidad = estado.verificado ? 'VERIFICADO' : 'VERIFICACION_PENDIENTE';
        data.estado_verificacion = estado.verificado ? 'VERIFICADO' : null; data.nivel_fallo = null;
        if (estado.verificado) {
          data.eslabones.nivel_fallo = null;
          data.eslabones.ids.id_evento = estado.eventos.find(e => e.activo === 1831)?.id ?? 1;
          data.eslabones.ids.ids_lectura_iot = escenario === 'sin_lectura_cadena' ? [] : [120035];
        } else data.eslabones = null;
      }
      else if (/^\/finanzas\/periodos\/(241|220)\/estado-resultados\/acumulado$/.test(p)) {
        const id = Number(p.split('/')[3]);
        if (id === 241 && escenario === 'codigo_v1') { status = 422; data = { error_code:'PERIODO_NO_CERRADO' }; }
        else {
          data = copia('acumulado');
          data.id_periodo_contable = id; data.estado_periodo = 'ABIERTO'; data.es_definitivo = false;
          const vs = id === 241 && !estado.borrado ? estado.variaciones : [];
          const sum = tipo => vs.filter(x => x.tipo === tipo).reduce((n,x) => n + Math.abs(Number(x.monto_variacion)),0);
          const comp = data.componentes;
          for (const [tipo,campo] of Object.entries({
            GANANCIA_TRANSFORMACION_BIOLOGICA:'ganancia_transformacion_biologica',
            PERDIDA_TRANSFORMACION_BIOLOGICA:'perdida_transformacion_biologica',
            GANANCIA_PRECIO_MERCADO:'ganancia_precio_mercado',
            PERDIDA_PRECIO_MERCADO:'perdida_precio_mercado'
          })) comp[campo] = String(sum(tipo).toFixed(2));
          data.total_ingresos = String((sum('GANANCIA_TRANSFORMACION_BIOLOGICA') +
            sum('GANANCIA_PRECIO_MERCADO')).toFixed(2));
          data.total_gastos = String((sum('PERDIDA_TRANSFORMACION_BIOLOGICA') +
            sum('PERDIDA_PRECIO_MERCADO')).toFixed(2));
          if (escenario === 'sin_delta' && id === 241) {
            data.total_ingresos = '0.00'; comp.ganancia_transformacion_biologica = '0.00';
          }
          if (escenario === 'otro_alterado' && id === 220 && estado.variaciones.length) data.total_ingresos = '1.00';
        }
      }
      else if (p === '/finanzas/auditoria') {
        data = copia('auditoria'); data.eventos = estado.borrado ? [] : estado.auditorias;
        data.total_registros = data.eventos.length; data.pagina_actual = Number(u.searchParams.get('pagina'));
        data.registros_por_pagina = 500;
      }
      else if (p === '/iot/monitoreo/historial') {
        data = copia('m03_historial'); data.items = [{ ...data.items[0],
          id_telemetria: 120035, id_activo_biologico: 1831,
          timestamp_captura: pre.timestamp_lectura }];
        data.total = 1; data.pagina = 1; data.por_pagina = 100; data.paginas_totales = 1;
      }
      else if (p === '/finanzas/periodos/241/trazabilidad' && m === 'POST') {
        if (escenario === 'codigo_v1') { status = 500; data = { error_code: 'ERROR_INTERNO' }; }
        else { data = copia('trazabilidad'); data.verificadas = estado.variaciones.length;
          data.pendientes = []; estado.verificado = true;
          estado.variaciones.forEach(v => { v.estado_trazabilidad = 'VERIFICADO'; }); }
      }
      else if (p === `/test-control/runs/${runId}` && m === 'DELETE') {
        status = escenario === 'delete_fallido' ? 500 : 200;
        if (status === 200) estado.borrado = true;
        data = {};
      }
      else { status = 404; data = { error_code: 'RUTA_NO_SIMULADA' }; }
      if (escenario === 'con_campos' && status === 200 && data && !Array.isArray(data) &&
          typeof data === 'object') data.campo_adicional = true;
      registro.http = status;
      respuesta(res,status,data,runId);
    });
    await new Promise(resolve => servidor.listen(0,'127.0.0.1',resolve));
    const baseUrl = `http://127.0.0.1:${servidor.address().port}`;
    const args = ['--autorizacion',referencia,'--operacion',
      escenario === 'reintentar' ? 'reintentar' : 'reevaluar','--version','2',
      '--intento','1','--run-id',runId,'--contexto',contexto];
    const proceso = { QA_AUTORIZADO:'SI', SIGAB_API_TEST_BASE:baseUrl,
      QA_SANDBOX_SECRET:'secreto-local', QA_CONTADOR_EMAIL:'contador@invalid.local',
      QA_CONTADOR_PASSWORD:'local', QA_ADMIN_EMAIL:'admin@invalid.local',
      QA_ADMIN_PASSWORD:'local' };
    const archivoIoT = escenario === 'plazo_vencido' ? path.join(base,'iot-vencido.json') : null;
    if (archivoIoT) fs.writeFileSync(archivoIoT,JSON.stringify({ ...pre, timestamp_lectura:'2026-11-10T07:06:25Z' }));
    const salida = await principal(args,{ proceso, archivoEnv:path.join(base,'no-existe.env'),
      ensayo:true, precondicionIoTArchivo:archivoIoT });
    if (!salida.resultado) throw Error(`Preflight estático: ${salida.preflight.barreras.join(', ')}`);
    const r = salida.resultado;
    if (conservar) {
      assert.equal(path.resolve(TMP_EXAMPLE),path.join(os.tmpdir(),'g37-verificar-ejemplo'));
      fs.rmSync(TMP_EXAMPLE,{recursive:true,force:true});
      fs.mkdirSync(TMP_EXAMPLE);
      fs.cpSync(dir,path.join(TMP_EXAMPLE,runId),{recursive:true});
      fs.writeFileSync(path.join(TMP_EXAMPLE,'capacidades.json'),JSON.stringify(CAPACIDADES,null,2));
      process.stdout.write(`EJEMPLO_RUN=${path.join(TMP_EXAMPLE,runId)}\nEJEMPLO_CAPACIDADES=${path.join(TMP_EXAMPLE,'capacidades.json')}\n`);
    }
    const presentes = new Set(r.evidencias.filter(x => fs.existsSync(path.join(dir,x))));
    const informe = fs.readFileSync(path.join(dir, 'TC-M06-G37_reevaluacion_V2.md'), 'utf8');
    return { r, estado, runId, dir, salida, presentes, informe };
  } finally {
    if (servidor) await new Promise(resolve => servidor.close(resolve));
    fs.rmSync(base,{recursive:true,force:true});
  }
}
function validar(r, estado, esperado) {
  assert.deepEqual(Object.keys(r.casos).sort(), [...CASOS].sort());
  assert.deepEqual(CASOS.map(k => r.casos[k].estado), esperado);
  assert.equal(estado.solicitudes.some(x => x.ruta.includes('/estados-resultados') &&
    x.metodo === 'POST'), false);
  assert.equal(estado.solicitudes.some(x => x.ruta === '/finanzas/periodos/241/trazabilidad' &&
    x.metodo === 'POST') || esperado[1] === 'NO_CONCLUYENTE', true);
  assert.ok(estado.solicitudes.every(x => x.run == null ||
    x.run.startsWith('RUN-G37-V2-')));
}
if (process.argv.includes('--example-child')) {
  await simular('conforme',true);
} else {
  let n = 0;
  const seguro = { QA_AUTORIZADO:'NO' };
  // A1: el módulo importado y los oráculos no deben iniciar red.
  let remotos = 0; const original = globalThis.fetch;
  globalThis.fetch = async () => { remotos++; throw Error('Red prohibida'); };
  try {
    assert.equal(periodoDestino([{ numero_id_tributaria:'NIT-D',estado:'CERRADO',
      fecha_inicio:'2026-01-01',fecha_fin:'2026-12-31' }],'NIT-D',hoy()),null);
    assert.equal(remotos,0); n++;
  } finally { globalThis.fetch = original; }
  for (const [escenario,esperado,oficial] of [
    ['conforme',['APROBADO','APROBADO'],true],
    ['cierre_en_proceso',['APROBADO','APROBADO'],true],
    ['periodo_forma_extra',['APROBADO','APROBADO'],true],
    ['periodo_estado_invalido',['NO_CONCLUYENTE','NO_CONCLUYENTE'],false],
    ['con_campos',['APROBADO','APROBADO'],true],
    ['codigo_v1',['RECHAZADO','RECHAZADO'],true],
    ['sin_delta',['RECHAZADO','APROBADO'],true],
    ['otro_alterado',['RECHAZADO','APROBADO'],true],
    ['sin_lectura_cadena',['APROBADO','RECHAZADO'],true],
    ['sin_dispositivo',['NO_CONCLUYENTE','NO_CONCLUYENTE'],false],
    ['plazo_vencido',['NO_CONCLUYENTE','NO_CONCLUYENTE'],false],
    ['cerrado',['NO_CONCLUYENTE','NO_CONCLUYENTE'],false],
    ['reintentar',['APROBADO','APROBADO'],true],
    ['delete_fallido',['APROBADO','APROBADO'],false]
  ]) {
    const { r,estado,presentes,informe } = await simular(escenario);
    validar(r,estado,esperado);
    assert.equal(r.oficial,oficial,`${escenario}: ${JSON.stringify(r.condiciones_oficialidad)}; ${JSON.stringify(r.cierre.rollback)}; ${r.problemas_tecnicos.join('; ')}`);
    if (escenario === 'conforme' || escenario === 'reintentar')
      assert.deepEqual(Object.values(r.seguimiento),['CORREGIDA','CORREGIDA']);
    if (escenario === 'periodo_forma_extra') {
      assert.ok(r.contraste_contrato.some(x => x.id === 'periodos' && x.resultado === 'observacion'));
      assert.equal(r.discrepancias_contrato.some(x => x.id === 'periodos'), false);
    }
    if (escenario === 'periodo_estado_invalido') {
      assert.match(informe, /Problema técnico de automatización \(ERROR_QA\), no incidencia del producto/);
      assert.match(informe, /Sin incidencia de producto nueva comprobada/);
      assert.equal(estado.escritos, 0);
    }
    if (escenario === 'codigo_v1')
      assert.deepEqual(Object.values(r.seguimiento),['REPRODUCIDA','REPRODUCIDA']);
    if (['sin_dispositivo','plazo_vencido','cerrado'].includes(escenario)) {
      assert.equal(estado.escritos,0); assert.ok(estado.solicitudes.some(x => x.metodo === 'DELETE'));
    }
    if (escenario === 'delete_fallido') assert.equal(r.condiciones_oficialidad.delete_200,false);
    if (oficial) {
      assert.equal(clasificarRegistro(CAPACIDADES,r,presentes,
        {runId:r.run_id,referencia:r.autorizacion_referencia,version:2}),true);
    }
    n++; process.stdout.write(`OK ${escenario}: ${esperado.join('/')} oficial=${r.oficial} solicitudes=${r.solicitudes_totales}/150\n`);
  }
  const ejemplo = await new Promise(resolve => {
    let h;
    try { h = spawn(process.execPath,[fileURLToPath(import.meta.url),'--example-child'],
      {cwd:DIR,windowsHide:true,stdio:['ignore','pipe','pipe']}); }
    catch(e) { resolve({error:e}); return; }
    let out='',err='';
    h.stdout.on('data',x=>{out+=x});
    h.stderr.on('data',x=>{err+=x});
    h.on('error',e=>resolve({error:e}));
    h.on('close',code=>resolve({code,out,err}));
  });
  if (ejemplo.error?.code === 'EPERM') process.stdout.write('A4 spawn EPERM: ejemplo pendiente\n');
  else {
    assert.equal(ejemplo.code,0,ejemplo.err);
    assert.match(ejemplo.out,/EJEMPLO_RUN=/);
    process.stdout.write(ejemplo.out);
    n++;
  }
  process.stdout.write(`OK G37 V2: ${n} comprobaciones locales\n`);
}
