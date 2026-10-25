import assert from 'node:assert/strict';
import test from 'node:test';
import { EventEmitter } from 'node:events';
import { ejecutarCypressControlado } from '../lib/g87_cypress_runner.mjs';
import { cerrarYVerificar, cierreUnico, instalarSenales } from '../lib/g87_cierre.mjs';
import { uiHabilitada, comprobacionesUiFaltantes } from '../lib/g87_preparacion.mjs';

test('Cypress colgado vence por timeout, termina solo su PID y el principal continúa', async () => {
  const pid = 24680, terminados = [];
  const res = await ejecutarCypressControlado({ opciones: {}, timeoutMs: 10,
    spawnFn: () => Object.assign(new EventEmitter(), { pid }),
    terminarArbol: (x) => terminados.push(x) });
  assert.equal(res.timeout, true);
  assert.equal(res.total_pruebas, 0);
  assert.equal(res.navegador, 'chrome');
  assert.deepEqual(terminados, [pid]);
  assert.ok(process.pid !== pid);
});

test('fallo de navegador deja ejecutar cierre; 401 renueva antes del DELETE y conserva evidencia', async () => {
  const llamadas = [];
  const tokens = { admin: 'EXPIRADO' };
  const datos = { area: 349, ocupacion_inicial: 0, bloqueo_s1: true,
    s2: { id: 77, area_original: 328 }, lecturas: { ts: { c1: '2026-10-23T06:32:47Z' } }, ids_telemetria: [116850] };
  const solicitar = async (metodo, ruta, opciones = {}) => {
    llamadas.push(`${metodo} ${ruta}`);
    if (ruta === '/usuarios/me') return { status: 401 };
    if (ruta === '/sesiones/' && metodo === 'POST') return { status: 200, json: { token: 'NUEVO' } };
    if (metodo === 'DELETE') return { status: 200 };
    if (ruta.endsWith('/asociaciones')) return { status: 200, json: { items: [{ id_infraestructura: 328 }] } };
    if (ruta.includes('/dashboard')) return { status: 200, json: { total: 0 } };
    if (ruta.includes('/historial')) return { status: 403 };
    throw new Error('Petición inesperada');
  };
  const errorNavegador = new Error('Chrome EPERM');
  let cierre;
  try { throw errorNavegador; } catch { /* el finally del ejecutor continúa */ }
  finally { cierre = await cerrarYVerificar({ runId: 'G87-V2-20261023-080000', secreto: 'NO_GUARDAR', datos,
    tokens, credenciales: { admin: { correo: 'cuenta', clave: 'clave' } }, solicitar }); }
  assert.equal(cierre.run.cierre_http, 200);
  assert.equal(cierre.rollback.verificado, false);
  assert.equal(cierre.rollback.historial[77].http, 403);
  assert.ok(llamadas.indexOf('POST /sesiones/') < llamadas.indexOf('DELETE /test-control/runs/G87-V2-20261023-080000'));
  assert.equal(tokens.admin, 'NUEVO');
  assert.equal(JSON.stringify(cierre).includes('NO_GUARDAR'), false);
});

test('dos señales disparan un único cierre', async () => {
  let cierres = 0, salidas = 0;
  const cerrar = cierreUnico(async () => { cierres++; });
  const quitar = instalarSenales(cerrar, () => { salidas++; });
  try {
    process.emit('SIGINT'); process.emit('SIGTERM');
    await cerrar();
    assert.equal(cierres, 1);
    assert.equal(salidas, 2);
  } finally { quitar(); }
});

test('178 puede habilitarse sin S1; las pruebas UI ausentes no equivalen a aprobadas', () => {
  const pre = ['PRE-178-01', 'PRE-178-02', 'PRE-178-03'].map((id) => ({ caso: 'TC-M03-178', id, ok: true, tipo: 'PRE', fuente: 'API' }));
  assert.equal(uiHabilitada(pre, 'TC-M03-178', ['PRE-178-01', 'PRE-178-02', 'PRE-178-03'], true, true), true);
  assert.deepEqual(comprobacionesUiFaltantes([], 'TC-M03-178', ['PRE-UI-01', 'UI-178-01']), ['PRE-UI-01', 'UI-178-01']);
});
