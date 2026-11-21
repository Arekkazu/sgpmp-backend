// Pruebas unitarias locales de G105 con registros sintéticos (sin red ni participantes reales).
import test from 'node:test';
import assert from 'node:assert/strict';
import { CASOS, ESTADOS, REQUERIDAS, LIMITE_S, precondiciones, evaluarEnsayo, evaluarRegistro, capturar } from './ejecutar_tc_m03_g105.mjs';
import { veredictoCasos } from './monitoreo_lib.mjs';

const ensayo = (estado, extra = {}) => ({ participante: 'P01', variable: `Temperatura ${estado}`, estado_presentado: estado, estado_identificado: estado, tiempo_s: 2.4, requirio_informacion_tecnica: false, ...extra });
const registro = (ensayos = ESTADOS.map(e => ensayo(e)), extra = {}) => ({ sesion: { condiciones: 'QA' }, panel: { estados_presentes: [...ESTADOS], alerta_activa_visible: true }, participantes: [{ codigo: 'P01', perfil_productor: true, conocimiento_tecnico: false }], ensayos, ...extra });
const veredicto = r => veredictoCasos({ casos: CASOS, requeridas: REQUERIDAS, estado: 'CONCLUIDA', rollback: true, aserciones: evaluarRegistro(r).aserciones }).grupo;

test('criterio de la matriz: cuatro estados y límite de 5 s', () => {
  assert.deepEqual(ESTADOS, ['VERDE', 'AMARILLO', 'ROJO', 'GRIS']); assert.equal(LIMITE_S, 5);
  assert.deepEqual(REQUERIDAS['TC-M03-205'], ['UI-205-01@VERDE', 'UI-205-01@AMARILLO', 'UI-205-01@ROJO', 'UI-205-01@GRIS']);
});
test('ensayo: correcto, ≤ 5 s y sin información técnica; 5 s exactos cumplen', () => {
  assert.equal(evaluarEnsayo(ensayo('ROJO')).ok, true);
  assert.equal(evaluarEnsayo(ensayo('ROJO', { tiempo_s: 5 })).ok, true);
  assert.match(evaluarEnsayo(ensayo('ROJO', { tiempo_s: 5.01 })).error, /> 5 s/);
  assert.match(evaluarEnsayo(ensayo('ROJO', { estado_identificado: 'AMARILLO' })).error, /identificó AMARILLO/);
  assert.match(evaluarEnsayo(ensayo('GRIS', { estado_identificado: null })).error, /identificó nada/);
  assert.match(evaluarEnsayo(ensayo('VERDE', { requirio_informacion_tecnica: true })).error, /información técnica/);
  assert.equal(evaluarEnsayo(ensayo('verde'.toUpperCase(), { estado_identificado: 'verde' })).ok, true);
});
test('veredicto: APROBADO con los cuatro estados superados; un ensayo fallido rechaza', () => {
  assert.equal(veredicto(registro()), 'APROBADO');
  assert.equal(veredicto(registro([...ESTADOS.map(e => ensayo(e)), ensayo('ROJO', { tiempo_s: 7.3 })])), 'RECHAZADO');
});
test('precondiciones: panel sin GRIS, sin alerta, perfil técnico, datos personales o ensayos incompletos bloquean', () => {
  assert.equal(veredicto(registro(undefined, { panel: { estados_presentes: ['VERDE', 'AMARILLO', 'ROJO'], alerta_activa_visible: true } })), 'BLOQUEADO');
  assert.equal(veredicto(registro(undefined, { panel: { estados_presentes: [...ESTADOS], alerta_activa_visible: false } })), 'BLOQUEADO');
  assert.equal(veredicto(registro(undefined, { participantes: [{ codigo: 'P01', perfil_productor: true, conocimiento_tecnico: true }] })), 'BLOQUEADO');
  assert.equal(veredicto(registro(undefined, { participantes: [{ codigo: 'Juan Pérez', perfil_productor: true, conocimiento_tecnico: false }] })), 'BLOQUEADO');
  assert.ok(precondiciones(registro(undefined, { participantes: [{ codigo: 'P01', correo: 'x@y.z', perfil_productor: true, conocimiento_tecnico: false }] })).some(a => /datos personales/.test(a.nombre) && !a.ok));
  assert.equal(veredicto(registro([ensayo('VERDE', { tiempo_s: 'rápido' })])), 'BLOQUEADO');
  assert.equal(veredicto(registro(ESTADOS.filter(e => e !== 'GRIS').map(e => ensayo(e)))), 'BLOQUEADO');
});
test('un estado sin presentar en el panel invalida solo sus ensayos: un fallo en otro estado sigue rechazando', () => {
  const r = registro([...ESTADOS.map(e => ensayo(e)), ensayo('ROJO', { estado_identificado: 'VERDE' })], { panel: { estados_presentes: ['VERDE', 'AMARILLO', 'ROJO'], alerta_activa_visible: true } });
  assert.equal(veredicto(r), 'RECHAZADO');
});
test('captura moderada: cronometra entre los dos Enter y registra la respuesta', async () => {
  const lineas = ['Sala QA, móvil 360 px', 'VERDE, AMARILLO, ROJO, GRIS', 's', 'P01', 's', 'Temperatura;ROJO', '', '', 'rojo', 'n', '', ''];
  const tiempos = [1000, 4250];
  const salida = [];
  const r = await capturar({ leer: async () => lineas.shift() ?? '', escribir: x => salida.push(x), reloj: () => tiempos.shift() });
  assert.deepEqual(r.panel, { estados_presentes: ESTADOS, alerta_activa_visible: true });
  assert.deepEqual(r.participantes, [{ codigo: 'P01', perfil_productor: true, conocimiento_tecnico: false }]);
  assert.equal(r.ensayos.length, 1);
  assert.deepEqual({ ...r.ensayos[0], cronometro: undefined }, { participante: 'P01', variable: 'Temperatura', estado_presentado: 'ROJO', estado_identificado: 'ROJO', tiempo_s: 3.25, requirio_informacion_tecnica: false, cronometro: undefined });
  assert.equal(evaluarEnsayo(r.ensayos[0]).ok, true);
});
