import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { autorizar, cobertura, ESTADOS, INTERNO, CONSTRUIBLES, leerEnv, veredicto, cuerpoLectura, serialQa, leerConteo, consultaTestigoDispositivo } from './ejecutar_tc_m03_g96.mjs';

test('parser de configuración conserva valores y comentarios fuera de la clave', () => {
  assert.deepEqual(leerEnv('QA_AUTORIZADO=NO\nQA_PROD_EMAIL="qa@example.test"\n# comentario'), { QA_AUTORIZADO: 'NO', QA_PROD_EMAIL: 'qa@example.test' });
});
test('barrera niega sin autorización, DEV, destino distinto o prefijo inválido; el prefijo vacío no bloquea', () => {
  const v = { QA_AUTORIZADO: 'SI', QA_PROD_EMAIL: 'qa@example.test', QA_SETUP_EMAIL: 'adm@example.test', QA_COMMON_PASSWORD: 'x', QA_SANDBOX_SECRET: 'y', SIGAB_API_TEST_BASE: 'https://www.api.inmero.co/api-sgpmp-test' };
  const a = { ambiente: 'TEST', autorizacion: 'DEV-REF-123', efectos: ['notificacion-login'] };
  assert.equal(autorizar(v, a).ok, true);
  assert.equal(autorizar({ ...v, QA_AUTORIZADO: 'NO' }, a).ok, false);
  assert.equal(autorizar(v, { ...a, ambiente: 'DEV' }).ok, false);
  assert.equal(autorizar({ ...v, SIGAB_API_TEST_BASE: 'https://dev.example.test' }, a).ok, false);
  assert.equal(autorizar(v, { ...a, efectos: [] }).ok, false);
  assert.equal(autorizar({ ...v, QA_DEVICE_PREFIX: 'con espacio' }, a).ok, false);
  assert.equal(serialQa({}, '20261017000000'), 'QAAUTO-G96-20261017000000');
});
test('solo ONLINE se construye; SIN_SEÑAL y OFFLINE dependen de RF-60 (sin simular ausencia de reportes)', () => {
  assert.deepEqual(CONSTRUIBLES, ['ONLINE']);
  assert.deepEqual(INTERNO, { ONLINE: 'ACTIVO', OFFLINE: 'INACTIVO', 'SIN_SEÑAL': 'SIN_SEÑAL' });
  const c = cuerpoLectura({ idDispositivo: 1, idSensor: 2, serial: 'QAAUTO-G96-1', timestamp: '2026-10-17T00:00:00Z' });
  assert.equal(c.estado_conectividad, true);
  assert.equal(c.origen, 'TIEMPO_REAL');
});
test('cobertura: las tres condiciones son obligatorias', () => {
  assert.equal(cobertura(new Set(ESTADOS)), true);
  assert.equal(cobertura(new Set(['ONLINE', 'OFFLINE'])), false);
});
test('testigo de aislamiento sin RLS y lectura del conteo sin convertir fallos en 0', () => {
  assert.match(consultaTestigoDispositivo('QAAUTO-G96-1'), /FROM auditoria\.logs_dml .*tabla_afectada = 'dispositivos_iot'/);
  assert.throws(() => consultaTestigoDispositivo("x' OR '1'='1"));
  assert.equal(leerConteo({ status: 200, data: { data: [{ n: 1 }] } }), 1);
  assert.equal(leerConteo({ status: 400, data: { detail: 'x' } }), null);
});
const a = (condicion, id, ok = true, tipo = 'ASSERT', http = 200) => ({ condicion, nombre: `[TC-M03-187][${tipo}][${id}] x`, ok, http });
const todas = ESTADOS.flatMap(c => [a(c, 'PRE-187-0x', true, 'PRE'), a(c, 'API-187-01'), a(c, 'API-187-02')]);
const base = { estado: 'CONCLUIDA', rollback: true, aserciones: todas, erroresScript: 0, condiciones: ESTADOS };
test('veredicto: APROBADO solo con las tres condiciones verificadas', () => {
  assert.equal(veredicto(base), 'APROBADO');
  assert.equal(veredicto({ ...base, condiciones: ['ONLINE'], aserciones: todas.filter(x => x.condicion === 'ONLINE') }), 'BLOQUEADO');
});
test('veredicto: un ASSERT incumplido con respuesta real rechaza, aunque falten condiciones', () => {
  const online = [a('ONLINE', 'PRE-187-01', true, 'PRE'), a('ONLINE', 'API-187-01', false), a('ONLINE', 'API-187-02', false)];
  assert.equal(veredicto({ ...base, condiciones: ['ONLINE'], aserciones: online }), 'RECHAZADO');
});
test('veredicto: PRE, rollback, estado o errores de script bloquean (no rechazan)', () => {
  assert.equal(veredicto({ ...base, aserciones: [a('ONLINE', 'PRE-187-01', false, 'PRE'), ...todas.slice(1)] }), 'BLOQUEADO');
  assert.equal(veredicto({ ...base, rollback: false }), 'BLOQUEADO');
  assert.equal(veredicto({ ...base, estado: 'INTERRUMPIDA' }), 'BLOQUEADO');
  assert.equal(veredicto({ ...base, erroresScript: 1 }), 'BLOQUEADO');
  assert.equal(veredicto({ ...base, aserciones: [a('ONLINE', 'API-187-01', false, 'ASSERT', null)] }), 'BLOQUEADO');
});
test('la colección omite las condiciones no preparadas y conserva las aserciones originales', () => {
  const c = JSON.parse(fs.readFileSync(new URL('./TC-M03-G96.postman_collection.json', import.meta.url), 'utf8'));
  for (const it of c.item) {
    const t = JSON.stringify(it.event);
    assert.match(t, /skipRequest/);
    assert.match(t, /API-187-01/);
    assert.match(t, /API-187-02/);
  }
});
