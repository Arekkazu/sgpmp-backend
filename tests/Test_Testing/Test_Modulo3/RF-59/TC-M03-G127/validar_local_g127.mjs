// Pruebas unitarias locales de G127 con registros de auditoría sintéticos (sin red). Solo validan que
// el evaluador detecta auditorías incompletas o ajenas; no son evidencia funcional de SIGAB.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { CASOS, ATRIBUTOS, requeridas, estadoExportacion, evaluarRegistro, mejorRegistro } from './ejecutar_tc_m03_g127.mjs';
import { veredictoCasos } from './monitoreo_lib.mjs';

const col = JSON.parse(fs.readFileSync(new URL('./TC-M03-G127.postman_collection.json', import.meta.url), 'utf8'));
const op = { id_usuario: 5, filtros: { sensor_id: 70, id_infraestructura: 30, estado_dato: 'LECTURA_VALIDA' }, fecha_inicio: '2026-10-15', fecha_fin: '2026-10-17', total: 3, desde: '2026-10-17T06:00:00Z' };
const rf10 = (detalle = {}, extra = {}) => ({ id_evento: 1, id_usuario: 5, modulo: 'telemetria', descripcion: 'Consulta de historial', fecha_evento: '2026-10-17T06:01:00Z', resultado: 'exitoso', detalle: { filtros: { sensor_id: 70, id_infraestructura: 30, estado_dato: 'LECTURA_VALIDA' }, fecha_inicio: '2026-10-15', fecha_fin: '2026-10-17', total_registros: 3, ...detalle }, ...extra });
const iot = { id_evento: 'u-1', id_usuario: 5, tipo_evento: 'EXPORTACION_HISTORIAL', fecha_hora: '2026-10-17T06:02:00Z', accion_detallada: { sensor_id: 70, id_infraestructura: 30, estado_dato: 'LECTURA_VALIDA', rango: { desde: '2026-10-15T00:00:00', hasta: '2026-10-17T23:59:59' }, cantidad: 3, formato: 'EXCEL' } };

test('registro completo de la consulta: todos los atributos de la matriz', () => {
  assert.deepEqual(evaluarRegistro(rf10(), op), { relacionado: true, usuario: true, filtros: true, rango: true, cantidad: true, timestamp: true, formato: undefined });
});
test('detecta atributos ausentes o incorrectos', () => {
  assert.equal(evaluarRegistro(rf10({ filtros: { sensor_id: 70, id_infraestructura: 30 } }), op).filtros, false, 'falta estado_dato');
  assert.equal(evaluarRegistro(rf10({ total_registros: 4 }), op).cantidad, false);
  assert.equal(evaluarRegistro(rf10({ total_registros: undefined }), op).cantidad, false);
  assert.equal(evaluarRegistro(rf10({ fecha_fin: '2026-10-16' }), op).rango, false);
  assert.equal(evaluarRegistro(rf10({}, { fecha_evento: '2026-10-17T05:00:00Z' }), op).timestamp, false, 'anterior a la operación');
  assert.equal(evaluarRegistro(rf10({}, { fecha_evento: null }), op).timestamp, false);
});
test('exportación: exige además el formato; RF-63 con estructura distinta también se evalúa', () => {
  const e = evaluarRegistro(iot, { ...op, formato: 'EXCEL' });
  assert.equal(Object.values(e).every(x => x === true), true);
  assert.equal(evaluarRegistro({ ...iot, accion_detallada: { ...iot.accion_detallada, formato: 'PDF' } }, { ...op, formato: 'EXCEL' }).formato, false);
});
test('no usa registros de otros usuarios ni eventos no relacionados (p. ej. el login)', () => {
  assert.equal(evaluarRegistro(rf10({}, { id_usuario: 9 }), op).relacionado, false);
  assert.equal(evaluarRegistro({ id_evento: 2, id_usuario: 5, descripcion: 'Inicio de sesión', fecha_evento: '2026-10-17T06:00:30Z', detalle: {} }, op).relacionado, false);
  assert.equal(mejorRegistro([{ id_usuario: 5, descripcion: 'Inicio de sesión', detalle: {} }], op), null);
  const m = mejorRegistro([rf10({ total_registros: 9 }), rf10()], op);
  assert.equal(m.atributos.cantidad, true, 'elige el registro que documenta más atributos');
});
test('exportación: 503 M08_NO_DISPONIBLE no aplica; 2xx aplica; otro estado es indeterminado', () => {
  assert.equal(estadoExportacion(503, 'M08_NO_DISPONIBLE'), 'NO_DISPONIBLE');
  assert.equal(estadoExportacion(200, ''), 'APLICA');
  assert.equal(estadoExportacion(500, 'ERROR'), 'INDETERMINADA');
  assert.equal(estadoExportacion(403, 'ACCESO_DENEGADO'), 'INDETERMINADA');
  assert.equal(requeridas(false)['TC-M03-256'].every(k => k.endsWith('@CONSULTA')), true);
  assert.ok(requeridas(true)['TC-M03-256'].includes('API-256-07@EXPORTACION'));
});
const aserciones = (variante, falla) => [...ATRIBUTOS, ...(variante === 'EXPORTACION' ? [['API-256-07']] : [])].map(([id]) => ({ caso: 'TC-M03-256', tipo: 'ASSERT', id, variante, ok: id !== falla, evidencia: true }));
const v = (exp, a) => veredictoCasos({ casos: CASOS, requeridas: requeridas(exp), estado: 'CONCLUIDA', rollback: true, aserciones: a }).grupo;
test('veredicto: la consulta se decide aunque M08 no esté; la exportación cuenta cuando aplica', () => {
  assert.equal(v(false, aserciones('CONSULTA')), 'APROBADO');
  assert.equal(v(false, aserciones('CONSULTA', 'API-256-01')), 'RECHAZADO', 'sin registro de la consulta');
  assert.equal(v(false, [...aserciones('CONSULTA', 'API-256-01'), { caso: 'TC-M03-256', tipo: 'PRE', variante: null, ok: false }]), 'BLOQUEADO', 'sin testigo positivo');
  assert.equal(v(true, aserciones('CONSULTA')), 'BLOQUEADO', 'exportación disponible pero no evaluada');
  assert.equal(v(true, [...aserciones('CONSULTA'), ...aserciones('EXPORTACION', 'API-256-07')]), 'RECHAZADO', 'exportación sin formato');
  assert.equal(v(true, [...aserciones('CONSULTA'), ...aserciones('EXPORTACION')]), 'APROBADO');
});
test('colección: registra total y estado de la exportación para el ejecutor; barrera propia', () => {
  const correr = (i, code, body) => { const t = []; new Function('pm', col.item[i].event[0].script.exec.join('\n'))({ response: { code, json: () => body }, test: (n, f) => { try { f(); t.push({ n, ok: true }); } catch { t.push({ n, ok: false }); } }, expect: x => ({ to: { eql: y => { if (JSON.stringify(x) !== JSON.stringify(y)) throw Error('x'); } } }) }); return t; };
  assert.ok(correr(0, 200, { total: 3, items: [{}] }).some(t => /\[V:CONSULTA\] total=3$/.test(t.n)));
  assert.ok(correr(0, 500, null).some(t => /\[PRE\]/.test(t.n) && !t.ok));
  assert.ok(correr(1, 503, { error_code: 'M08_NO_DISPONIBLE' }).some(t => /HTTP 503 M08_NO_DISPONIBLE$/.test(t.n)));
  const pre = col.event.find(e => e.listen === 'prerequest').script.exec.join('\n');
  assert.throws(() => new Function('pm', pre)({ environment: { get: k => ({ autorizado_run: 'NO', run_id: 'R', base_url: 'https://x' })[k] }, execution: { skipRequest() {} } }), /BLOQUEO_G127/);
});
