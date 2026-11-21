// Pruebas unitarias locales de G129 con datos y respuestas sintéticos (sin red). Validan que la matriz,
// la colección y los evaluadores detectan filtraciones, códigos incorrectos y auditorías ausentes; no son
// evidencia funcional de SIGAB.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { CASOS, MATRIZ, REQUERIDAS, RECURSOS_259, INEXISTENTE, permisosHistorial, resolver, filasMatriz, registroIntento } from './ejecutar_tc_m03_g129.mjs';
import { veredictoCasos } from './monitoreo_lib.mjs';

const col = JSON.parse(fs.readFileSync(new URL('./TC-M03-G129.postman_collection.json', import.meta.url), 'utf8'));
const esc = {
  A: { unidad: 10, sensor: 100, prohibidos: { ids: { id_infraestructura: [10], id_sensor: [100], id_finca: [1] }, nombres: ['Unidad A'] } },
  B1: { unidad: 20, sensor: 200, prohibidos: { ids: { id_infraestructura: [20], id_sensor: [200], id_finca: [2], id_alerta: [900] }, nombres: ['Unidad B1', 'Granja B'] } },
  B2: { unidad: 30, sensor: 300, activo: 3000, prohibidos: { ids: { id_infraestructura: [30], id_sensor: [300], id_finca: [2], id_activo_biologico: [3000] }, nombres: ['Unidad B2', 'Granja B', 'QA-G129-X'] } },
};
const filas = filasMatriz(esc, { api: 'https://api.test.example', fechaInicio: '2026-10-15', fechaFin: '2026-10-17' });
const filaDe = (caso, tipo, variante) => filas.find(f => f.caso === caso && f.tipo === tipo && (variante === undefined || f.variante === variante));

function correr(fila, { code = 200, body, cabeceras = {}, colVars = {} }) {
  const tests = [];
  const pm = {
    iterationData: { get: k => fila[k] },
    response: { code, text: () => body === undefined ? '' : JSON.stringify(body), json: () => { if (body === undefined) throw Error('x'); return body; }, headers: { get: k => cabeceras[k] ?? null } },
    collectionVariables: { get: k => colVars[k], set: (k, v) => { colVars[k] = v; } },
    test: (n, f) => { try { f(); tests.push({ n, ok: true }); } catch { tests.push({ n, ok: false }); } },
    expect: (x, m) => ({ to: { eql: y => { if (JSON.stringify(x) !== JSON.stringify(y)) throw Error(m); } } }),
  };
  new Function('pm', col.item[0].event.find(e => e.listen === 'test').script.exec.join('\n'))(pm);
  return tests;
}
const ok = (t, id) => t.some(x => x.n.includes(id)) && t.filter(x => x.n.includes(id)).every(x => x.ok);
const vacio = { total: 0, pagina: 1, por_pagina: 100, paginas_totales: 1, filtros_aplicados: { id_infraestructura: 20 }, rango_real_datos: { desde: null, hasta: null }, items: [], estadisticas: [] };
const denegado = { error_code: 'ACCESO_DENEGADO', message: 'Acceso denegado.', fields: [], timestamp: 't' };

test('matriz: cuatro casos, tres recursos en 259 con existencia y control inexistente, ambos endpoints', () => {
  assert.deepEqual([...new Set(MATRIZ.map(f => f.caso))], CASOS);
  for (const x of RECURSOS_259) for (const t of ['ajeno', 'inexistente']) assert.ok(MATRIZ.some(f => f.variante === x && f.tipo === t), `${x} ${t}`);
  assert.ok(MATRIZ.filter(f => f.tipo.startsWith('existe')).every(f => f.actor === 'SETUP'));
  assert.ok(filas.every(f => f.url.startsWith('https://api.test.example/')));
  assert.match(filaDe('TC-M03-260', 'exportar_sin_permiso').url, /historial\/exportar\?.*formato=EXCEL.*id_infraestructura=10/);
  assert.match(filaDe('TC-M03-259', 'inexistente', 'SENSOR').url, new RegExp(`sensor_id=${INEXISTENTE}`));
  assert.match(filaDe('TC-M03-259', 'ajeno', 'ACTIVO').url, /id_activo_biologico=3000/);
  assert.equal(filaDe('TC-M03-259', 'existe_get', 'ACTIVO').url, 'https://api.test.example/activos-biologicos/3000');
  assert.deepEqual(JSON.parse(filaDe('TC-M03-261', 'lectura_sin_permiso').prohibidos).ids.id_infraestructura, [10, 20, 30]);
  assert.throws(() => resolver('B3.unidad', esc));
});
test('permisos reales del historial: lectura y ejecución por separado', () => {
  assert.deepEqual(permisosHistorial([{ id_recurso: 34, id_accion: 2, es_activo: true }]), { leer: true, ejecutar: false });
  assert.deepEqual(permisosHistorial([{ id_recurso: 34, id_accion: 2, es_activo: true }, { id_recurso: 34, id_accion: 5, es_activo: true }]), { leer: true, ejecutar: true });
  assert.deepEqual(permisosHistorial([{ id_recurso: 34, id_accion: 2, es_activo: false }, { id_recurso: 33, id_accion: 2, es_activo: true }]), { leer: false, ejecutar: false });
  assert.equal(permisosHistorial(null), null);
});
test('258: sin código HTTP impuesto; detecta datos, nombres o alertas de la granja B', () => {
  const f = filaDe('TC-M03-258', 'ajeno');
  for (const [code, body] of [[200, vacio], [403, denegado], [404, denegado]]) { const t = correr(f, { code, body }); assert.ok(ok(t, 'API-258-01') && ok(t, 'API-258-02'), `HTTP ${code}`); }
  assert.ok(!ok(correr(f, { body: { ...vacio, total: 2, items: [{ id_sensor: 200 }, { id_sensor: 200 }] } }), 'API-258-01'));
  assert.ok(!ok(correr(f, { body: { ...vacio, estadisticas: [{ tipo_variable: 'T', total_lecturas: 2 }] } }), 'API-258-01'));
  assert.ok(!ok(correr(f, { body: { ...vacio, rango_real_datos: { desde: '2026-10-17T00:00:00', hasta: null } } }), 'API-258-01'));
  assert.ok(!ok(correr(f, { code: 403, body: { message: 'La Unidad B1 pertenece a otra granja' } }), 'API-258-02'));
  assert.ok(!ok(correr(f, { body: { ...vacio, detalle: { id_alerta: 900 } } }), 'API-258-02'));
});
test('259: indistinguible de un identificador inexistente; el eco de filtros no cuenta como exposición', () => {
  for (const x of RECURSOS_259) {
    const ajeno = filaDe('TC-M03-259', 'ajeno', x), nx = filaDe('TC-M03-259', 'inexistente', x);
    const cv = {};
    assert.ok(ok(correr(ajeno, { body: { ...vacio, filtros_aplicados: { sensor_id: 300 } }, colVars: cv }), 'API-259-01'));
    assert.ok(ok(correr(nx, { body: { ...vacio, filtros_aplicados: { sensor_id: INEXISTENTE } }, colVars: cv }), 'API-259-02'), x);
    const cv2 = {};
    correr(ajeno, { code: 403, body: denegado, colVars: cv2 });
    assert.ok(!ok(correr(nx, { code: 200, body: vacio, colVars: cv2 }), 'API-259-02'), `${x}: 403 frente a 200 revela existencia`);
    const cv3 = {};
    correr(ajeno, { code: 404, body: { ...denegado, message: 'Sensor 300 de otra granja' }, colVars: cv3 });
    assert.ok(!ok(correr(nx, { code: 404, body: { ...denegado, message: 'Sensor no encontrado' }, colVars: cv3 }), 'API-259-02'), `${x}: mensaje distinto`);
  }
  assert.ok(!ok(correr(filaDe('TC-M03-259', 'ajeno', 'UNIDAD'), { body: { ...vacio, total: 1, items: [{ id_sensor: 300, id_infraestructura: 30 }] } }), 'API-259-01'));
});
test('259 ACTIVO: precondición de contrato del filtro (dependencia dinámica, no permanente)', () => {
  const f = filaDe('TC-M03-259', 'ajeno', 'ACTIVO');
  assert.ok(correr(f, { body: vacio }).some(t => /\[PRE\].*id_activo_biologico/.test(t.n) && !t.ok), 'hoy no está en filtros_aplicados');
  assert.ok(correr(f, { body: { ...vacio, filtros_aplicados: { id_activo_biologico: 3000 } } }).some(t => /\[PRE\].*id_activo_biologico/.test(t.n) && t.ok));
});
test('260: solo HTTP 403 cumple; sin archivo, enlace ni identificador de descarga', () => {
  const f = filaDe('TC-M03-260', 'exportar_sin_permiso');
  const t = correr(f, { code: 403, body: denegado, cabeceras: { 'Content-Type': 'application/json' } });
  assert.ok(ok(t, 'API-260-01') && ok(t, 'API-260-02'));
  for (const code of [200, 401, 404, 503]) assert.ok(!ok(correr(f, { code, body: denegado }), 'API-260-01'), `HTTP ${code} no equivale a 403`);
  assert.ok(!ok(correr(f, { code: 403, body: undefined, cabeceras: { 'Content-Disposition': 'attachment; filename="h.xlsx"' } }), 'API-260-02'));
  assert.ok(!ok(correr(f, { code: 403, body: { ...denegado, url_descarga: 'https://x/f.xlsx' } }), 'API-260-02'));
  assert.ok(!ok(correr(f, { code: 403, body: { ...denegado, detalle: { id_exportacion: 55 } } }), 'API-260-02'));
});
test('261: denegado sin código impuesto; un historial vacío con 200 no es denegación', () => {
  const f = filaDe('TC-M03-261', 'lectura_sin_permiso');
  for (const code of [403, 401, 404]) { const t = correr(f, { code, body: denegado }); assert.ok(ok(t, 'API-261-01') && ok(t, 'API-261-02'), `HTTP ${code}`); }
  const vacio200 = correr(f, { body: vacio });
  assert.ok(!ok(vacio200, 'API-261-01') && ok(vacio200, 'API-261-02'));
  const datos = correr(f, { body: { ...vacio, total: 1, items: [{ id_sensor: 100 }] } });
  assert.ok(!ok(datos, 'API-261-01') && !ok(datos, 'API-261-02'));
});
test('controles: existencia demostrada por actor autorizado (200 con el recurso)', () => {
  assert.ok(correr(filaDe('TC-M03-259', 'existe', 'SENSOR'), { body: { ...vacio, items: [{ id_sensor: 300 }] } }).every(t => t.ok));
  assert.ok(correr(filaDe('TC-M03-259', 'existe', 'SENSOR'), { body: vacio }).some(t => !t.ok), 'sin datos el recurso no se da por existente');
  assert.ok(correr(filaDe('TC-M03-259', 'existe_get', 'ACTIVO'), { body: { id_activo_biologico: 3000 } }).every(t => t.ok));
});
test('auditoría: registro completo del intento; se descartan el login y otros usuarios', () => {
  const i258 = { id_usuario: 5, id_unidad: 20 }, i260 = { id_usuario: 7, id_unidad: null };
  const r258 = { id_usuario: 5, fecha_evento: 't', resultado: 'fallido', detalle: { id_infraestructura: 20, motivo: 'GRANJA_NO_AUTORIZADA' } };
  assert.equal(registroIntento(r258, i258).completo, true);
  assert.equal(registroIntento({ ...r258, detalle: { id_infraestructura: 20 } }, i258).completo, false, 'sin motivo');
  assert.equal(registroIntento({ ...r258, id_usuario: 6 }, i258).coincide, false);
  assert.equal(registroIntento({ id_usuario: 5, descripcion: 'Inicio de sesión', fecha_evento: 't', detalle: {} }, i258).coincide, false);
  const r260 = { id_usuario: 7, fecha_hora: 't', tipo_evento: 'EXPORTACION_HISTORIAL', descripcion: 'Exportación denegada', accion_detallada: { codigo_error: 'ACCESO_DENEGADO' } };
  assert.equal(registroIntento(r260, i260).completo, true);
  assert.equal(registroIntento({ ...r260, tipo_evento: 'CONSULTA', descripcion: 'x' }, i260).coincide, false);
});
const todas = () => Object.entries(REQUERIDAS).flatMap(([caso, ks]) => ks.map(k => ({ caso, tipo: 'ASSERT', id: k.split('@')[0], variante: k.split('@')[1], ok: true, evidencia: true })));
const v = a => veredictoCasos({ casos: CASOS, requeridas: REQUERIDAS, estado: 'CONCLUIDA', rollback: true, aserciones: a });
test('veredicto: cada caso por separado; bitácora no observable solo bloquea la auditoría', () => {
  assert.equal(v(todas()).grupo, 'APROBADO');
  const falla258 = todas().map(a => a.id === 'API-258-01' ? { ...a, ok: false } : a);
  const sinBitacora = [...falla258.filter(a => a.variante !== 'GRANJA_AUDITORIA'), { caso: 'TC-M03-258', tipo: 'PRE', variante: 'GRANJA_AUDITORIA', ok: false }];
  assert.equal(v(sinBitacora).casos['TC-M03-258'], 'RECHAZADO', 'la denegación fallida se conserva');
  assert.equal(v(todas().filter(a => a.variante !== 'GRANJA_AUDITORIA')).casos['TC-M03-258'], 'BLOQUEADO');
  const sinActivo = [...todas().filter(a => a.variante !== 'ACTIVO'), { caso: 'TC-M03-259', tipo: 'PRE', variante: 'ACTIVO', ok: false }];
  assert.deepEqual([v(sinActivo).casos['TC-M03-259'], v(sinActivo).grupo], ['BLOQUEADO', 'BLOQUEADO']);
  const sinActor260 = [...todas().filter(a => a.caso !== 'TC-M03-260'), { caso: 'TC-M03-260', tipo: 'PRE', variante: null, ok: false }];
  assert.equal(v(sinActor260).casos['TC-M03-260'], 'BLOQUEADO');
  assert.equal(v(sinActor260).casos['TC-M03-261'], 'APROBADO');
  assert.equal(v(todas().map(a => a.id === 'API-260-01' ? { ...a, ok: false } : a)).casos['TC-M03-260'], 'RECHAZADO');
});
test('barrera de la colección: sin autorización o con destinos no HTTPS no se envía ninguna petición; sin actor la fila se omite', () => {
  const pre = col.event.find(e => e.listen === 'prerequest').script.exec.join('\n');
  const pm = (env, fila) => ({ environment: { get: k => env[k] }, iterationData: { get: k => fila[k] }, execution: { skipRequest() {} } });
  assert.throws(() => new Function('pm', pre)(pm({ autorizado_run: 'NO', run_id: 'R', base_url: 'https://x' }, { url: 'https://x/y' })), /BLOQUEO_G129/);
  assert.throws(() => new Function('pm', pre)(pm({ autorizado_run: 'SI', run_id: 'R', base_url: 'https://x' }, { url: 'http://127.0.0.1:9/y' })), /BLOQUEO_G129/);
  let saltada = false;
  const item = col.item[0].event.find(e => e.listen === 'prerequest').script.exec.join('\n');
  new Function('pm', item)({ iterationData: { get: () => 'EXP' }, environment: { get: () => '' }, variables: { set() {} }, execution: { skipRequest: () => { saltada = true; } } });
  assert.equal(saltada, true);
});
