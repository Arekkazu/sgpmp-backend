import assert from 'node:assert/strict';
import fs from 'node:fs';
import http from 'node:http';
import os from 'node:os';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { CASO, IDS, CAPACIDADES, evaluarPaso, resultadoFinal, rollback, oficialidad } from '../lib/g35_core.mjs';
import { clasificarRegistro } from './registro_qa.mjs';
import { pedir, evaluar, informe, sanear, entornoNewman, evaluarEvidenciaNewman } from '../g35.mjs';

const snap = (estado = 'ACTIVO') => ({ completa: true, estado,
  eventos: [{ id_eventos: 2 }], variaciones: [], lineas: [], mediciones: [], calculos: [], auditoria: [] });
const base = snap();
const baja = { ...snap('BAJA'), eventos: [...base.eventos, { id_eventos: 8 }],
  lineas: [{ id_linea_asiento_nic41: 9, id_activo_biologico: 3, tipo_hecho: 'BAJA_ACTIVO', id_origen: 8, valor: 100 }] };
const rechBaja = { http: 409, codigo: 'ESTADO_NO_PERMITE_EVENTOS', mensaje: 'Estado actual: BAJA; solo ACTIVO' };
const rechInexistente = { http: 404, codigo: 'ACTIVO_NO_ENCONTRADO', mensaje: 'El activo no existe' };
const modos = [
  ['todo_conforme', () => assert.equal(resultadoFinal({ a: evaluarPaso('baja', base, baja, { http: 201 }, 3, 8, 100),
    b: evaluarPaso('baja_rechazo', baja, baja, rechBaja, 3, 8),
    c: evaluarPaso('inexistente', baja, baja, rechInexistente, 3, 8) }), 'APROBADO')],
  ['baja_con_variacion', () => assert.equal(evaluarPaso('baja', base, { ...baja, variaciones: [{ id_variacion_valor_razonable: 4, id_activo_biologico: 3 }] }, { http: 201 }, 3, 8, 100).estado, 'RECHAZADO')],
  ['baja_sin_linea', () => assert.equal(evaluarPaso('baja', base, { ...baja, lineas: [] }, { http: 201 }, 3, 8, 100).estado, 'RECHAZADO')],
  ['baja_valor_incorrecto', () => assert.equal(evaluarPaso('baja', base, { ...baja, lineas: [{ ...baja.lineas[0], valor: 99 }] }, { http: 201 }, 3, 8, 100).estado, 'RECHAZADO')],
  ['crecimiento_baja_aceptado', () => assert.equal(evaluarPaso('baja_rechazo', baja, { ...baja, eventos: [...baja.eventos, { id_eventos: 10 }] }, { http: 201 }, 3, 8).estado, 'RECHAZADO')],
  ['crecimiento_baja_sin_causa', () => assert.equal(evaluarPaso('baja_rechazo', baja, baja, { http: 409, codigo: 'CONFLICTO', mensaje: 'Conflicto' }, 3, 8).estado, 'RECHAZADO')],
  ['inexistente_crea_datos', () => assert.equal(evaluarPaso('inexistente', baja, { ...baja, lineas: [...baja.lineas, { id_linea_asiento_nic41: 10, id_activo_biologico: 3 }] }, rechInexistente, 3, 8).estado, 'RECHAZADO')],
  ['estado_no_restaurado', () => assert.equal(rollback(base, baja, 8).verificado, false)],
  ['rollback_conforme', () => assert.equal(rollback(base, base, 8).verificado, true)],
  ['lectura_incompleta', () => assert.equal(evaluarPaso('baja', base, { ...baja, completa: false }, { http: 201 }, 3, 8, 100).estado, 'NO_CONCLUYENTE')],
  ['rechazo_inexistente_generico', () => assert.equal(evaluarPaso('inexistente', baja, baja, { http: 404, codigo: 'CONFLICTO', mensaje: 'Error genérico' }, 3, 8).estado, 'RECHAZADO')],
  ['sin_aprobado_parcial', () => assert.equal(resultadoFinal({ a: { estado: 'APROBADO' }, b: { estado: 'NO_CONCLUYENTE' } }), 'NO_CONCLUYENTE')],
  ['rejected_sin_todos_conclusivos_no_oficial', () => assert.equal(oficialidad({ cierre: { rollback: { verificado: true } },
    casos: { [CASO]: { estado: 'RECHAZADO', subcasos: { baja: { estado: 'RECHAZADO' }, baja_rechazo: { estado: 'NO_CONCLUYENTE' }, inexistente: { estado: 'APROBADO' } } } },
    comprobaciones: IDS.map(id => ({ caso: CASO, id, estado: 'RECHAZADO' })), herramientas: { newman: { iteraciones: 1 } } }), false)],
  ['registro_qa_fiel', () => { const r = { run_id: 'RUN-G35-V1-20261108-000000', version: 1, oficial: true,
    consume_version: true, cierre: { run: { cierre_http: 200 }, rollback: { verificado: true } },
    casos: { [CASO]: { estado: 'APROBADO' } }, herramientas: { newman: { iteraciones: 1 } },
    cypress: { total_pruebas: 0 }, comprobaciones: IDS.map(id => ({ caso: CASO, fuente: 'API', id,
      tipo: 'ASSERT', estado: 'APROBADO', evidencia: 'resultado.json' })),
    evidencias: ['resultado.json', 'TC-M06-G35_resultado.md', 'newman/newman-G35.json', 'newman/newman-G35.html'] };
    assert.equal(clasificarRegistro(CAPACIDADES, r, new Set(r.evidencias), { runId: r.run_id, version: 1 }), true);
    r.comprobaciones[0].caso = 'TC-M06-G35 / TC-M06-008';
    assert.equal(clasificarRegistro(CAPACIDADES, r, new Set(r.evidencias), { runId: r.run_id, version: 1 }), false); }],
  ['corte_403', async () => { const r = { solicitudes: [], _limite: Date.now() + 10000, _corte: false, _seguidos5xx: 0, _secretos: [] };
    await pedir(r, 'http://127.0.0.1:1', 'GET', '/x', { fetcher: async () => ({ status: 403, headers: { get: () => null }, json: async () => ({ error_code: 'DENEGADO', message: 'No permitido' }) }) });
    assert.equal(r._corte, true); }],
  ['lectura_5xx', async () => { const r = { solicitudes: [], _limite: Date.now() + 10000, _corte: false, _seguidos5xx: 0, _secretos: [] };
    for (let n = 0; n < 3; n++) await pedir(r, 'http://127.0.0.1:1', 'GET', '/x', { fetcher: async () => ({ status: 503, headers: { get: () => null }, json: async () => ({}) }) });
    assert.equal(r._corte, true); }],
  ['delete_sin_secreto', async () => { const r = { solicitudes: [], _limite: Date.now() + 10000, _corte: false, _seguidos5xx: 0, _secretos: [] };
    const x = await pedir(r, 'http://127.0.0.1:1', 'DELETE', '/test-control/runs/RUN-X', { fetcher: async (_, init) => {
      assert.equal(init.headers['X-Sandbox-Secret'], undefined);
      return { status: 403, headers: { get: () => null }, json: async () => ({ error_code: 'DENEGADO' }) }; } });
    assert.equal(x.http, 403); }],
  ['sin_candidato', async () => { const c = { runId: 'RUN-G35-V1-20261108-000000', version: 1, intento: 1, ensayo: true };
    const env = { SIGAB_API_TEST_BASE: 'http://127.0.0.1:1', QA_SANDBOX_SECRET: 'falso', QA_CONTADOR_EMAIL: 'a@invalid',
      QA_CONTADOR_PASSWORD: 'falso', QA_ADMIN_EMAIL: 'b@invalid', QA_ADMIN_PASSWORD: 'falso', QA_AUTORIZADO: 'SI' };
    const fetcher = async (url, init) => { const ruta = new URL(url).pathname;
      const cuerpo = ruta === '/sesiones/' ? { token: 'falso' } : ruta === '/finanzas/activos' || ruta === '/finanzas/periodos' ? [] :
        ruta === '/finanzas/configuracion' ? { matriz: [] } : {};
      return { status: 200, headers: { get: () => c.runId }, json: async () => cuerpo }; };
    const r = await evaluar(c, { env, fetcher, sinArtefactos: true });
    assert.equal(r.casos[CASO].estado, 'BLOQUEADO'); assert.equal(r.oficial, false); }],
  ['flujo_integrado_local', async ({ tercero = false, precioAnterior = false } = {}) => {
    const c = { runId: 'RUN-G35-V1-20261108-000000', version: 1, intento: 1, ensayo: true };
    const env = { SIGAB_API_TEST_BASE: 'http://127.0.0.1:1', QA_SANDBOX_SECRET: 'falso',
      QA_CONTADOR_EMAIL: 'a@invalid', QA_CONTADOR_PASSWORD: 'falso', QA_ADMIN_EMAIL: 'b@invalid',
      QA_ADMIN_PASSWORD: 'falso', QA_AUTORIZADO: 'SI' };
    let estado = 'ACTIVO', bajaCreada = false, lineaCreada = false;
    const resultado = (status, cuerpo, eco = true) => ({ status, headers: { get: () => eco ? c.runId : null },
      json: async () => cuerpo });
    const fetcher = async (url, init) => {
      const u = new URL(url), ruta = u.pathname;
      if (ruta === '/sesiones/') return resultado(200, { token: 'simulado' }, false);
      if (ruta === '/finanzas/activos') {
        const activo = activoId => ({ id_activo_biologico: activoId,
          id_especie: 2, especie: 'Bovino', tipo: 'INDIVIDUAL', estado: 'ACTIVO', valor_razonable_neto: 100 });
        return resultado(200, tercero ? [activo(1), activo(2), activo(3)] : [activo(3)]);
      }
      if (ruta === '/finanzas/periodos') return resultado(200, [{ id_periodo_contable: 4,
        numero_id_tributaria: 'NIT_SIMULADO', estado: 'ABIERTO', fecha_inicio: '2000-01-01', fecha_fin: '2099-12-31' }]);
      if (ruta === '/finanzas/configuracion') return resultado(200, { matriz: [{ tipo_hecho: 'BAJA_ACTIVO',
        sentido: 'PERDIDA', id_especie: 2, cuenta_debito: 'X', cuenta_credito: 'Y' }] });
      if (ruta === '/finanzas/precios') return resultado(200, [{ id_precio_mercado: 5,
        id_especie: 2, categoria: 'PESO_KG', fuente: 'MERCADO_ACTIVO', fecha_vigencia: '2000-01-01' }]);
      if (tercero && ['/finanzas/activos/1', '/finanzas/activos/2'].includes(ruta))
        return resultado(200, { activo: { numero_id_tributaria: 'NIT_SIMULADO' },
          reconocimientos: [{ estado: 'CONFIRMADO' }], calculos: [], mediciones: [] });
      if (ruta === '/finanzas/activos/3') return resultado(200, { activo: { numero_id_tributaria: 'NIT_SIMULADO' },
        reconocimientos: [{ estado: 'CONFIRMADO' }], calculos: [{ id_calculo_valor_razonable: 6,
          estado: 'CALCULADO', valor_neto: '1.1500', id_periodo_contable: precioAnterior ? 7 : 4,
          id_precio_mercado: precioAnterior ? 17 : 5 }], mediciones: [] });
      if (ruta === '/activos-biologicos/3/ficha-integral') return resultado(200, { estado_actual: estado,
        unidad_peso: 'kg', peso_actual: 10 });
      if (ruta === '/activos-biologicos/3/eventos') return resultado(200, { eventos: bajaCreada ? [{ id_eventos: 2 },
        { id_eventos: 8, baja: { tipo: 'perdida' } }] : [{ id_eventos: 2 }] });
      if (ruta === '/activos-biologicos/100003') return resultado(404, { error_code: 'ACTIVO_NO_ENCONTRADO',
        message: 'El activo no existe' });
      if (ruta === '/activos-biologicos/3/eventos/baja') { estado = 'BAJA'; bajaCreada = true;
        return resultado(201, { id_eventos: 8 }); }
      if (ruta === '/finanzas/eventos/procesar') { lineaCreada = true; return resultado(200, { procesados: 1 }); }
      if (ruta === '/activos-biologicos/3/eventos/crecimiento') return resultado(409,
        { error_code: 'ESTADO_NO_PERMITE_EVENTOS', message: 'Estado actual: BAJA' });
      if (ruta === '/activos-biologicos/100003/eventos/crecimiento') return resultado(404,
        { error_code: 'ACTIVO_NO_ENCONTRADO', message: 'El activo no existe' });
      if (ruta === '/finanzas/periodos/4/variaciones') return resultado(200, []);
      if (ruta === '/finanzas/lineas') return resultado(200, lineaCreada ? [{ id_linea_asiento_nic41: 9,
        tipo_hecho: 'BAJA_ACTIVO', id_origen: 8, id_activo_biologico: 3, valor: '1.15' }] : []);
      if (ruta === '/finanzas/periodos/4/mediciones') return resultado(200, []);
      if (ruta === '/finanzas/auditoria') return resultado(200, { eventos: [], total_registros: 0 });
      if (ruta === '/notificaciones') return resultado(200, { items: [], total: 0 });
      if (ruta.startsWith('/test-control/runs/')) { assert.equal(init.headers['X-Sandbox-Secret'], 'falso');
        estado = 'ACTIVO'; bajaCreada = false; lineaCreada = false; return resultado(200, {}); }
      throw Error('Ruta simulada imprevista: ' + ruta);
    };
    const r = await evaluar(c, { env, fetcher, sinArtefactos: true });
    assert.equal(r.casos[CASO].estado, 'APROBADO');
    assert.equal(r.casos[CASO].activo_id, 3);
    assert.equal(r.casos[CASO].valor_baja_esperado, 1.15);
    assert.equal(r.casos[CASO].diagnostico_por_candidato.length, tercero ? 3 : 1);
    if (tercero) {
      assert.deepEqual(r.casos[CASO].diagnostico_por_candidato.map(x => x.estado),
        ['DESCARTADO', 'DESCARTADO', 'SELECCIONADO']);
      assert.ok(r.casos[CASO].diagnostico_por_candidato.slice(0, 2).every(x => /cálculo CALCULADO/.test(x.motivo)));
    }
    assert.equal(r.solicitudes.some(x => x.ruta === '/finanzas/precios'), false);
    assert.equal(r.cierre.rollback.verificado, true);
    assert.equal(r.solicitudes.filter(x => x.metodo === 'POST' && x.ruta.includes('/eventos/crecimiento')).length, 2);
    assert.ok(r.solicitudes.length <= 60);
    assert.ok(r.comprobaciones.every(x => x.caso === CASO));
    const md = informe({ ...c, referencia: 'AUT-SIMULADA' }, r);
    assert.match(md, /^# TC-M06-G35 — APROBADO\n/);
    for (const seccion of ['Identificación', 'Decisión del caso', 'Detalle por caso', 'Comprobaciones API',
      'Evidencias reales', 'Incidencias de producto', 'Problemas técnicos', 'Cierre y rollback',
      'Conclusión y acciones']) assert.ok(md.includes(`## ${seccion}\n`), seccion);
    for (const subcaso of ['baja', 'baja_rechazo', 'inexistente']) {
      assert.ok(md.includes(`### ${subcaso} —`), subcaso);
    }
    const detalle = md.split('## Detalle por caso\n')[1].split('## Comprobaciones API\n')[0];
    for (const etiqueta of ['Preparación', 'Esperado', 'Observado', 'Qué se cumplió', 'Qué falló y por qué',
      'Decisión']) assert.match(detalle, new RegExp(`\\*\\*${etiqueta}:\\*\\*`));
    assert.match(detalle, /HTTP 201/);
    assert.match(detalle, /HTTP 409, código ESTADO_NO_PERMITE_EVENTOS/);
    assert.match(detalle, /HTTP 404, código ACTIVO_NO_ENCONTRADO/);
    assert.match(detalle, /línea BAJA_ACTIVO vinculada: 9/);
    assert.doesNotMatch(detalle, /Observado:\s*\{|"(?:activo_id|http|codigo_error)"\s*:/);
  }],
  ['sin_residuos', () => assert.equal(fs.readdirSync(os.tmpdir()).filter(x => x.startsWith('g35-newman-')).length, 0)],
];
const flujoIntegradoLocal = modos.find(([nombre]) => nombre === 'flujo_integrado_local')[1];
modos.push(['candidato_tercero', () => flujoIntegradoLocal({ tercero: true })]);
modos.push(['calculo_con_precio_anterior', () => flujoIntegradoLocal({ precioAnterior: true })]);
modos.push(['newman_ficha_con_token_m02', () => {
  const e = entornoNewman({ SIGAB_API_TEST_BASE: 'http://127.0.0.1:1', QA_SANDBOX_SECRET: 'secreto-simulado' },
    { runId: 'RUN-SIMULADO' }, 'contador-simulado', 'admin-simulado', 3, 4, 8, 100);
  const vars = Object.fromEntries(e.values.map(x => [x.key, x.value]));
  assert.equal(vars.token, 'contador-simulado');
  assert.equal(vars.token_m02, 'admin-simulado');
  const s = evaluarEvidenciaNewman(IDS.map(nombre => ({ nombre, http: 200, aserciones: [{ error: null }] })), 0);
  assert.equal(s.problema, false);
  assert.equal(s.iteraciones, 1);
}]);
modos.push(['newman_403', () => {
  const s = evaluarEvidenciaNewman(IDS.map((nombre, i) => ({ nombre,
    http: i === 1 ? 403 : 200, aserciones: [] })), 0);
  assert.equal(s.accesos_denegados, 1);
  assert.equal(s.problema, true);
  assert.equal(s.estado, 'NO_CONCLUYENTE');
  assert.match(s.problema_tecnico, /401\/403/);
}]);
for (const [nombre, prueba] of modos) { await prueba(); console.log('modo ' + nombre + ': OK'); }
const servidor = http.createServer((_, res) => {
  res.writeHead(200, { 'Content-Type': 'application/json' });
  res.end('{"ok":true}');
});
await new Promise(resolve => servidor.listen(0, '127.0.0.1', resolve));
try {
  const url = `http://127.0.0.1:${servidor.address().port}/newman-probe`;
  const entrada = JSON.stringify({ coleccion: { info: { name: 'G35 sonda local',
    schema: 'https://schema.getpostman.com/json/collection/v2.1.0/collection.json' },
    item: [{ name: 'sonda', request: { method: 'GET', url },
      event: [{ listen: 'test', script: { type: 'text/javascript', exec: [
        "pm.test('HTTP 200', () => pm.expect(pm.response.code).to.equal(200));" ] } }] }] },
    environment: { values: [] }, timeout: 30000 });
  const resultado = await new Promise(resolve => {
    let hijo;
    try { hijo = spawn(process.execPath, [fileURLToPath(new URL('./newman_hijo.mjs', import.meta.url))],
      { stdio: ['pipe', 'pipe', 'pipe'], windowsHide: true }); }
    catch (e) { resolve({ error: e.code ?? e.message }); return; }
    let salida = '', stderr = '', error = null;
    hijo.on('error', e => { error = e.code ?? e.message; });
    hijo.stdout.on('data', b => { salida += b.toString(); });
    hijo.stderr.on('data', b => { stderr += b.toString(); });
    hijo.stdin.on('error', () => {});
    hijo.stdin.end(entrada);
    hijo.on('close', codigo => resolve({ codigo, salida, stderr, error }));
  });
  if (['EPERM', 'EACCES'].includes(resultado.error))
    console.log(`OK newman_hijo: no ejecutable en este entorno (${resultado.error})`);
  else {
    assert.equal(resultado.error, null, `newman_hijo: ${sanear(resultado.error)}`);
    const salida = JSON.parse(resultado.salida);
    assert.equal(resultado.codigo, 0, `newman_hijo: ${sanear(resultado.stderr || salida.error)}`);
    assert.equal(salida.error, null);
    assert.equal(salida.reporte_exportado, true);
    assert.equal(salida.solicitudes.length, 1);
    assert.equal(salida.solicitudes[0].http, 200);
    assert.equal(salida.solicitudes[0].aserciones[0].error, null);
    console.log('OK newman_hijo: process.execPath, 1 lectura loopback HTTP 200');
  }
} finally { await new Promise(resolve => servidor.close(resolve)); }
console.log(`OK G35: ${modos.length}/${modos.length} modos; aislamiento y cierre comprobados; registro QA fiel`);
