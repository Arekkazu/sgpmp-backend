// Pruebas unitarias locales de G128 con JWT y respuestas sintéticos construidos en tiempo de ejecución
// (sin red y sin tokens literales en el repositorio). No son evidencia funcional de SIGAB.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { CASOS, VARIANTES, REQUERIDAS, ALMACEN, claims, expirado, disponibleDesde, manipularFirma, huella, tokenUtilizable } from './ejecutar_tc_m03_g128.mjs';
import { veredictoCasos } from './monitoreo_lib.mjs';

const b64 = o => Buffer.from(JSON.stringify(o)).toString('base64url');
const jwt = (payload, firma = Buffer.from('firma-sintetica-de-prueba-0123456789')) => [b64({ alg: 'HS256', typ: 'JWT' }), b64(payload), firma.toString('base64url')].join('.');
const ahora = Date.parse('2026-10-17T12:00:00Z');
const viejo = jwt({ sub: '5', jti: '77', iat: ahora / 1000 - 9 * 3600, exp: ahora / 1000 - 3600 });
const vigente = jwt({ sub: '5', jti: '78', iat: ahora / 1000 - 600, exp: ahora / 1000 + 8 * 3600 });
const guardado = t => ({ token: t, huella: huella(t), origen: 'POST /sesiones/ (login oficial) dentro de un RUN de sandbox', run: 'G128-TOKEN-1', emitido: 'x' });
const col = JSON.parse(fs.readFileSync(new URL('./TC-M03-G128.postman_collection.json', import.meta.url), 'utf8'));

test('firma manipulada: misma cabecera y contenido, firma distinta y estructura válida', () => {
  const m = manipularFirma(vigente);
  const [h, p, s] = vigente.split('.'), [h2, p2, s2] = m.split('.');
  assert.equal(m.split('.').length, 3);
  assert.equal(h2, h); assert.equal(p2, p);
  assert.notDeepEqual(Buffer.from(s2, 'base64url'), Buffer.from(s, 'base64url'));
  assert.deepEqual(claims(m), claims(vigente));
  assert.throws(() => manipularFirma('no-es-jwt'));
});
test('expiración: solo cuenta pasado exp + tolerancia + margen; sin claims no hay expiración', () => {
  assert.equal(expirado(viejo, ahora), true);
  assert.equal(expirado(vigente, ahora), false);
  assert.equal(expirado(jwt({ sub: '5', jti: '1', exp: ahora / 1000 - 60 }), ahora), false, 'dentro de la tolerancia');
  assert.equal(expirado('a.b.c', ahora), false);
  assert.equal(disponibleDesde(vigente), new Date((ahora / 1000 + 8 * 3600) * 1000 + 150000).toISOString());
});
test('token expirado utilizable: procedencia oficial, huella coherente, cuenta del Ingeniero y ya expirado', () => {
  assert.equal(tokenUtilizable(guardado(viejo), 5, ahora).ok, true);
  assert.match(tokenUtilizable(null, 5, ahora).motivos.join(), /preparar-token-expirable/);
  assert.match(tokenUtilizable(guardado(vigente), 5, ahora).motivos.join(), /aún no ha expirado: disponible desde/);
  assert.match(tokenUtilizable({ ...guardado(viejo), huella: 'x' }, 5, ahora).motivos.join(), /huella/);
  assert.match(tokenUtilizable({ ...guardado(viejo), origen: 'variable de entorno' }, 5, ahora).motivos.join(), /procedencia/);
  assert.match(tokenUtilizable(guardado(viejo), 6, ahora).motivos.join(), /no pertenece/);
  assert.match(tokenUtilizable(guardado(jwt({ sub: '5', exp: 1 })), 5, ahora).motivos.join(), /claims/);
});
test('el token emitido se guarda fuera del repositorio', () => {
  const raiz = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../../../..');
  assert.ok(!path.resolve(ALMACEN).startsWith(raiz));
});
function correr(variante, { code, body, cabeceras = {}, env = {} }) {
  const it = col.item.find(i => i.name.includes(`[V:${variante}]`));
  const tests = []; let saltada = false;
  const e = { nombre_sensor: 'QA G128 X U S001', nombre_unidad: 'QA G128 X U', token_expirado: 't', ...env };
  const pm = {
    response: { code, text: () => body === undefined ? '' : JSON.stringify(body), json: () => { if (body === undefined) throw Error('x'); return body; }, headers: { get: k => cabeceras[k] ?? null } },
    environment: { get: k => e[k] }, execution: { skipRequest: () => { saltada = true; } },
    test: (n, f) => { try { f(); tests.push({ n, ok: true }); } catch { tests.push({ n, ok: false }); } },
    expect: (x, m) => ({ to: { eql: y => { if (JSON.stringify(x) !== JSON.stringify(y)) throw Error(m); } } }),
  };
  const pre = it.event.find(x => x.listen === 'prerequest');
  if (pre) new Function('pm', pre.script.exec.join('\n'))(pm);
  if (!saltada) new Function('pm', it.event.find(x => x.listen === 'test').script.exec.join('\n'))(pm);
  return { tests, saltada };
}
const ok = (t, id) => t.some(x => x.n.includes(id)) && t.filter(x => x.n.includes(id)).every(x => x.ok);
const negado = { error_code: 'TOKEN_REQUERIDO', message: 'Se requiere autenticación.', fields: [], timestamp: 'x' };
test('las seis combinaciones: 401 limpio aprueba; datos, nombres o archivos se detectan', () => {
  for (const v of VARIANTES) {
    const t = correr(v, { code: 401, body: negado, cabeceras: { 'Content-Type': 'application/json' } }).tests;
    assert.ok(ok(t, 'API-257-01') && ok(t, 'API-257-02'), v);
  }
  const conDatos = correr('HISTORIAL_FIRMA', { code: 200, body: { total: 1, items: [{ id_sensor: 1 }], estadisticas: [] } }).tests;
  assert.ok(!ok(conDatos, 'API-257-01') && !ok(conDatos, 'API-257-02'));
  assert.ok(!ok(correr('HISTORIAL_SIN_TOKEN', { code: 401, body: { message: 'sin acceso a QA G128 X U S001' } }).tests, 'API-257-02'), 'nombre del sensor expuesto');
  assert.ok(!ok(correr('EXPORTAR_FIRMA', { code: 401, body: undefined, cabeceras: { 'Content-Disposition': 'attachment; filename="h.xlsx"' } }).tests, 'API-257-02'), 'archivo');
  assert.ok(!ok(correr('EXPORTAR_SIN_TOKEN', { code: 401, body: { detalle: { alertas: [] } } }).tests, 'API-257-02'), 'clave anidada');
  assert.ok(!ok(correr('EXPORTAR_EXPIRADO', { code: 403, body: negado }).tests, 'API-257-01'), '403 no es 401');
});
test('sin token expirado utilizable, sus dos peticiones no se envían; sin token no lleva Authorization', () => {
  assert.equal(correr('HISTORIAL_EXPIRADO', { code: 401, body: negado, env: { token_expirado: '' } }).saltada, true);
  assert.equal(correr('EXPORTAR_EXPIRADO', { code: 401, body: negado, env: { token_expirado: '' } }).saltada, true);
  for (const v of ['HISTORIAL_SIN_TOKEN', 'EXPORTAR_SIN_TOKEN']) assert.ok(!col.item.find(i => i.name.includes(`[V:${v}]`)).request.header.some(h => /authorization/i.test(h.key)));
});
test('veredicto: seis 401 limpios aprueban; un fallo real rechaza; sin token expirado bloquea', () => {
  const todas = VARIANTES.flatMap(v => ['API-257-01', 'API-257-02'].map(id => ({ caso: 'TC-M03-257', tipo: 'ASSERT', id, variante: v, ok: true, evidencia: true })));
  const b = { casos: CASOS, requeridas: REQUERIDAS, estado: 'CONCLUIDA', rollback: true };
  assert.equal(veredictoCasos({ ...b, aserciones: todas }).grupo, 'APROBADO');
  assert.equal(veredictoCasos({ ...b, aserciones: todas.map(a => a.variante === 'EXPORTAR_FIRMA' && a.id === 'API-257-01' ? { ...a, ok: false } : a) }).grupo, 'RECHAZADO');
  const sinExpirado = [...todas.filter(a => !/EXPIRADO/.test(a.variante)), ...['HISTORIAL_EXPIRADO', 'EXPORTAR_EXPIRADO'].map(v => ({ caso: 'TC-M03-257', tipo: 'PRE', variante: v, ok: false }))];
  assert.equal(veredictoCasos({ ...b, aserciones: sinExpirado }).grupo, 'BLOQUEADO');
  assert.equal(veredictoCasos({ ...b, aserciones: [...sinExpirado.filter(a => a.tipo === 'PRE'), ...todas.filter(a => !/EXPIRADO/.test(a.variante)).map(a => a.variante === 'HISTORIAL_FIRMA' && a.id === 'API-257-02' ? { ...a, ok: false } : a)] }).grupo, 'RECHAZADO', 'un fallo real se conserva aunque falte el expirado');
});
test('barrera de la colección: sin autorización vigente no se envía ninguna petición', () => {
  const pre = col.event.find(e => e.listen === 'prerequest').script.exec.join('\n');
  const pm = v => ({ environment: { get: k => v[k] }, execution: { skipRequest() {} } });
  assert.throws(() => new Function('pm', pre)(pm({ autorizado_run: 'NO', run_id: 'R', base_url: 'https://x' })), /BLOQUEO_G128/);
  assert.throws(() => new Function('pm', pre)(pm({ autorizado_run: 'SI', run_id: 'R', base_url: 'http://127.0.0.1:9' })), /BLOQUEO_G128/);
});
