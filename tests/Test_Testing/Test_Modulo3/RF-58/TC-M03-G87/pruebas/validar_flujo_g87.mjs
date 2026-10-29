// Simulación local en proceso del flujo canónico: sin red, procesos hijo ni RUN.
import assert from 'node:assert/strict';
import test from 'node:test';
import { EventEmitter } from 'node:events';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { versionSiguiente } from '../g87.mjs';
import { oficialidad, validarResultadoLocal, generarInforme } from '../lib/g87_informe.mjs';
import { ejecutarCypressControlado } from '../lib/g87_cypress_runner.mjs';
import { cerrarYVerificar, cierreUnico, instalarSenales } from '../lib/g87_cierre.mjs';
import { sanearArtefacto } from '../lib/g87_seguridad.mjs';

const defs = {
  'TC-M03-168': { titulo: 'Última lectura válida', esperado: 'HTTP 200 y última LECTURA_VALIDA' },
  'TC-M03-177': { titulo: 'Anomalía visible', esperado: '25 y ROJO/ícono' },
  'TC-M03-178': { titulo: 'Diferencia de rol', esperado: 'ERROR_CALIBRACION diferenciado' },
};
function muestra() {
  const casos = Object.fromEntries(Object.keys(defs).map((id) => [id, { estado: 'APROBADO', motivo: 'Comprobado' }]));
  const comprobaciones = Object.keys(defs).flatMap((caso) => {
    const n = caso.slice(-3);
    const api = n === '168' ? 5 : n === '177' ? 3 : 7;
    const ui = n === '168' ? 0 : n === '177' ? 3 : 5;
    return [...Array.from({ length: api }, (_, i) => ({ caso, tipo: 'ASSERT', id: `API-${n}-0${i + 1}`, descripcion: 'API', fuente: 'API', estado: 'APROBADO', ok: true })),
      ...Array.from({ length: ui }, (_, i) => ({ caso, tipo: 'ASSERT', id: `UI-${n}-0${i + 1}`, descripcion: 'UI', fuente: 'UI', estado: 'APROBADO', ok: true }))];
  });
  return { grupo: 'TC-M03-G87', run_id: 'RUN-G87-V1-20261023-100000', version: 1, inicio: '2026-10-23T10:00:00Z',
    fin: '2026-10-23T10:01:00Z', referencia: 'SIMULACION', ambiente: 'SINTÉTICO', estado: 'CONCLUIDA',
    casos, comprobaciones, incidencias: [], evidencias: ['resultado.json'], cypress: { total_pruebas: 8 },
    cierre: { run: { cierre_http: 200 }, rollback: { verificado: true, historial: { 1: {} } }, sesiones: {} },
    veredicto_grupo: 'APROBADO', herramientas: { node: process.version } };
}

test('evaluación V1 con Resultados vacío', () => { const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'g87-version-')); try { fs.mkdirSync(path.join(dir, 'Resultados')); assert.deepEqual(fs.readdirSync(path.join(dir, 'Resultados')), []); assert.deepEqual(versionSiguiente('evaluacion'), { version: 1, intento: null }); } finally { assert.ok(path.resolve(dir).startsWith(path.resolve(os.tmpdir()) + path.sep)); fs.rmSync(dir, { recursive: true, force: true }); } });
test('reintento técnico conserva V1', () => assert.deepEqual(versionSiguiente('reintento'), { version: 1, intento: null }));
test('tipo inválido se bloquea', () => assert.ok(versionSiguiente('reevaluacion').error));
test('UI con cero pruebas jamás hace oficial el RUN', () => { const r = muestra(); r.cypress.total_pruebas = 0; assert.equal(oficialidad(r), false); assert.ok(validarResultadoLocal(r, ['TC-M03-G87_resultado.md']).includes('UI aprobada con cero pruebas')); });
test('criterios API/UI y cierre con historial permiten oficialidad sintética', () => { const r = muestra(); assert.equal(oficialidad(r), true); r.oficial = true; assert.deepEqual(validarResultadoLocal(r, ['TC-M03-G87_resultado.md']), []); });
test('validador impide informe duplicado, equipo inventado y dato privado', () => { const r = muestra(); assert.ok(validarResultadoLocal(r, ['informe.md', 'TC-M03-G87_resultado.md']).length); r.incidencias_funcionales = [{ responsable: 'Backend' }]; const md = generarInforme(r, defs) + '\ncorreo@example.invalid'; const errores = validarResultadoLocal(r, ['TC-M03-G87_resultado.md'], null, md); assert.ok(errores.includes('equipo no permitido')); assert.ok(errores.includes('posible secreto o dato privado en informe')); });
test('generador separa incidencias funcionales y problemas QA', () => { const r = muestra(); r.casos['TC-M03-177'].estado = 'RECHAZADO'; r.comprobaciones.find((x) => x.caso === 'TC-M03-177' && x.fuente === 'API').estado = 'RECHAZADO'; r.incidencias.push('ERROR_QA: Cypress no produjo captura'); r.oficial = false; const md = generarInforme(r, defs); for (const s of ['Incidencias funcionales', 'Problemas de automatización QA', 'Desarrollo', 'Análisis de fallos', 'Conclusión y acciones']) assert.ok(md.includes(s)); assert.ok(!md.includes('informe.md')); assert.deepEqual(validarResultadoLocal(r, ['resultado.json', 'TC-M03-G87_resultado.md'], null, md), []); });
test('Cypress colgado termina PID simulado sin spawn real', async () => { const terminados = []; const res = await ejecutarCypressControlado({ opciones: {}, timeoutMs: 5, spawnFn: () => Object.assign(new EventEmitter(), { pid: 12345 }), terminarArbol: (pid) => terminados.push(pid) }); assert.equal(res.total_pruebas, 0); assert.equal(res.timeout, true); assert.deepEqual(terminados, [12345]); });
test('cierre inyectado: re-login, DELETE y falta de historial impiden verificar rollback', async () => { const eventos = []; const tokens = { admin: 'EXPIRADO' }; const solicitar = async (metodo, ruta) => { eventos.push(`${metodo} ${ruta}`); if (ruta === '/usuarios/me') return { status: 401 }; if (ruta === '/sesiones/' && metodo === 'POST') return { status: 200, json: { token: 'RENOVADO' } }; if (metodo === 'DELETE') return { status: 200 }; if (ruta.endsWith('/asociaciones')) return { status: 200, json: { items: [] } }; if (ruta.includes('/dashboard')) return { status: 200, json: { total: 0 } }; if (ruta.includes('/historial')) return { status: 403 }; throw Error('ruta imprevista'); }; const r = await cerrarYVerificar({ runId: 'SIMULADO', secreto: 'SINTETICO', datos: { area: 1, ocupacion_inicial: 0, bloqueo_s1: true, s2: { id: 2, area_original: null }, lecturas: { ts: { a: '2026-10-23T10:00:00Z' } } }, tokens, credenciales: { admin: { correo: 'local.invalid', clave: 'sintetica' } }, solicitar }); assert.equal(tokens.admin, 'RENOVADO'); assert.equal(r.run.cierre_http, 200); assert.equal(r.rollback.verificado, false); assert.ok(eventos.indexOf('POST /sesiones/') < eventos.indexOf('DELETE /test-control/runs/SIMULADO')); });
test('dos señales comparten un solo cierre', async () => { let n = 0; const cerrar = cierreUnico(async () => { n++; }); const quitar = instalarSenales(cerrar, () => {}); try { process.emit('SIGINT'); process.emit('SIGTERM'); await cerrar(); assert.equal(n, 1); } finally { quitar(); } });

test('evidencia: se sanean token, cabeceras, serial y correo incluso en respuesta codificada', () => {
  const sensible = { request: { header: [{ key: 'Authorization', value: 'Bearer privado' },
    { key: 'X-Sandbox-Secret', value: 'privado' }] }, serial: 'SERIAL-PRIVADO',
  correo_electronico: 'persona@example.invalid', response: { stream: { data: [...Buffer.from('{"token":"privado","serial":"SERIAL-PRIVADO"}')] } } };
  const limpio = sanearArtefacto(JSON.stringify(sensible), ['privado']);
  for (const secreto of ['privado', 'SERIAL-PRIVADO', 'persona@example.invalid']) assert.ok(!limpio.includes(secreto));
  assert.ok(JSON.parse(limpio).response.stream.data.length > 0);
});

test('cierre: historial completo y sin IDs del RUN confirma; 403, 404 o paginación incompleta no', async () => {
  const runId = 'SIMULADO';
  const datos = { area: 349, ocupacion_inicial: 0, bloqueo_s1: false,
    s1: { id: 552, area_original: 349 }, s2: { id: 77, area_original: 328 },
    lecturas: { ts: { a1: '2026-10-23T06:32:47Z', c1: '2026-10-23T06:33:47Z' } },
    ids_telemetria: [116846, 116850] };
  async function verificar(historial, { area77 = 328, total = 0 } = {}) {
    const solicitar = async (metodo, ruta) => {
      if (metodo === 'DELETE') return { status: 200 };
      if (ruta === '/usuarios/me') return { status: 200 };
      if (ruta.endsWith('/asociaciones')) return { status: 200, json: { items: [{ id_infraestructura: ruta.includes('/552/') ? 349 : area77 }] } };
      if (ruta.includes('/dashboard')) return { status: 200, json: { total } };
      if (ruta.includes('/historial')) return historial(ruta.includes('sensor_id=552') ? 552 : 77);
      throw Error(`ruta inesperada: ${ruta}`);
    };
    return cerrarYVerificar({ runId, secreto: 'SINTETICO', datos, tokens: { admin: 'SINTETICO' },
      credenciales: {}, solicitar });
  }
  const vacio = () => ({ status: 200, json: { total: 0, items: [] } });
  const confirmado = await verificar(vacio);
  assert.equal(confirmado.rollback.verificado, true);
  assert.equal(confirmado.rollback.conclusion, 'ROLLBACK_CONFIRMADO');
  for (const codigo of [403, 404]) {
    const r = await verificar(() => ({ status: codigo }));
    assert.equal(r.rollback.verificado, false);
    assert.equal(r.rollback.historial[552].http, codigo);
    assert.equal(r.rollback.conclusion, 'ROLLBACK_RESPALDADO_INDIRECTO');
  }
  const conId = await verificar((sensor) => sensor === 552
    ? { status: 200, json: { total: 1, items: [{ id_telemetria: 116846 }] } } : vacio());
  assert.equal(conId.rollback.verificado, false);
  assert.equal(conId.rollback.conclusion, 'NO_CONCLUYENTE');
  assert.deepEqual(conId.rollback.historial[552].coincidencias, [116846]);
  const incompleto = await verificar(() => ({ status: 200, json: { total: 2, items: [] } }));
  assert.equal(incompleto.rollback.verificado, false);
  assert.equal(incompleto.rollback.conclusion, 'NO_CONCLUYENTE');
  assert.equal(incompleto.rollback.historial[77].completo, false);
  assert.equal((await verificar(vacio, { area77: 349 })).rollback.conclusion, 'NO_CONCLUYENTE');
  assert.equal((await verificar(vacio, { total: 1 })).rollback.conclusion, 'NO_CONCLUYENTE');
});
