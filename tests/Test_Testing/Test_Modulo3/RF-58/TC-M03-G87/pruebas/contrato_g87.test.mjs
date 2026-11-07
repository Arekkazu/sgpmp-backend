import assert from 'node:assert/strict';
import test from 'node:test';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { contextoEjecucion } from '../lib/contrato_ejecutor.mjs';
import { cerrarYVerificar } from '../lib/g87_cierre.mjs';
import { generarInforme } from '../lib/g87_informe.mjs';

const datos = { area: 2, ocupacion_inicial: 0, bloqueo_s1: true,
  s2: { id: 7, area_original: 3 },
  lecturas: { ts: { a: '2026-10-23T10:00:00Z' } }, ids_telemetria: [19] };
async function cierre({ http = 200, previo = null, sinDelete = false, historial = 'vacio',
  asociacion = 3, ocupacion = 0, sesion = true } = {}) {
  const llamadas = [];
  const solicitar = async (metodo, ruta) => {
    llamadas.push([metodo, ruta]);
    if (ruta === '/usuarios/me') return { status: sesion ? 200 : 401 };
    if (metodo === 'POST') return { status: 401 };
    if (metodo === 'DELETE') return { status: http };
    if (ruta.endsWith('/asociaciones')) return { status: 200, json: { items: [{ id_infraestructura: asociacion }] } };
    if (ruta.includes('/dashboard')) return { status: 200, json: { total: ocupacion } };
    if (ruta.includes('/historial')) {
      if (historial === '403') return { status: 403 };
      if (historial === 'id') return { status: 200, json: { total: 1, items: [{ id_telemetria: 19 }] } };
      if (historial === 'incompleto') return { status: 200, json: { total: 1, items: [] } };
      return { status: 200, json: { total: 0, items: [] } };
    }
    throw Error('ruta inesperada');
  };
  const r = await cerrarYVerificar({ runId: 'G87-V1-20261023-100000', secreto: 'SINTETICO',
    datos, tokens: { admin: 'SINTETICO' }, credenciales: { admin: { correo: 'sintetico', clave: 'sintetico' } },
    solicitar, solicitarCierre: !sinDelete, cierrePrevioHttp: previo });
  return { r, llamadas };
}
const recuperaciones = [
  ['B01 DELETE 200 e historial completo', {}, true, true],
  ['B02 DELETE 404 más historial completo', { http: 404 }, true, true],
  ['B03 DELETE 404 aislado no verifica', { http: 404, historial: '403' }, false, true],
  ['B04 lectura tras cierre 200', { sinDelete: true, previo: 200 }, true, false],
  ['B05 lectura tras cierre 404', { sinDelete: true, previo: 404 }, true, false],
  ['B06 lectura 404 sin historial', { sinDelete: true, previo: 404, historial: '403' }, false, false],
  ['B07 sesión vencida sin renovación', { sesion: false }, false, true],
  ['B08 asociación no restaurada', { asociacion: 8 }, false, true],
  ['B09 ocupación no restaurada', { ocupacion: 1 }, false, true],
  ['B10 ID de telemetría persiste', { historial: 'id' }, false, true],
  ['B11 paginación incompleta', { historial: 'incompleto' }, false, true],
];
for (const [name, opts, esperado, conDelete] of recuperaciones) test(name, async () => {
  const { r, llamadas } = await cierre(opts);
  assert.equal(r.rollback.verificado, esperado);
  assert.equal(llamadas.some(([m]) => m === 'DELETE'), conDelete);
});

const casos = ['TC-M03-168', 'TC-M03-177', 'TC-M03-178'];
function fixture(version = 1, operacion = 'evaluar', extra = {}) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'g87-contrato-'));
  const runId = 'RUN-G87-V' + version + '-20261023-110000';
  const dir = path.join(root, ...(version === 1 ? ['Resultados'] : ['EvaluacionV' + version, 'Resultados']), runId);
  fs.mkdirSync(dir, { recursive: true });
  const archivo = path.join(dir, operacion === 'recuperar' ? 'recuperacion-20261023110000.contexto.json' : 'contexto_operacion.json');
  const contexto = { grupo: 'G87', version, intento: 7, run_id: runId, operacion: operacion.toUpperCase(),
    referencia: 'AUT-G87-CONTRATO-01', casos, alcance_reevaluacion: operacion === 'reevaluar'
      ? { casos, version_anterior: version - 1, motivo: 'verificar corrección' } : null,
    version_anterior: operacion === 'reevaluar' ? version - 1 : null,
    ...(operacion === 'recuperar' ? { run_objetivo: runId } : {}), ...extra };
  fs.writeFileSync(archivo, JSON.stringify(contexto));
  const args = ['--autorizacion', contexto.referencia, '--operacion', operacion, '--version', String(version),
    '--intento', '7', '--run-id', runId, '--contexto', archivo];
  if (operacion === 'recuperar') args.push('--run-objetivo', runId);
  return { root, runId, dir, archivo, contexto, args, ejecutar: (a = args) => contextoEjecucion(a,
    { grupo: 'G87', casos, directorio: root }), cerrar: () => fs.rmSync(root, { recursive: true, force: true }) };
}
function conFixture(version, op, fn) {
  const f = fixture(version, op);
  try { fn(f); } finally { f.cerrar(); }
}
test('D01 ruta V1', () => conFixture(1, 'evaluar', (f) => assert.equal(f.ejecutar().directorio, f.dir)));
test('D02 ruta V2', () => conFixture(2, 'reevaluar', (f) => assert.equal(f.ejecutar().version, 2)));
test('D03 ruta V5', () => conFixture(5, 'reevaluar', (f) => assert.equal(f.ejecutar().version, 5)));
test('D04 referencia incongruente', () => conFixture(1, 'evaluar', (f) => assert.throws(() =>
  f.ejecutar(f.args.map((x) => x === 'AUT-G87-CONTRATO-01' ? 'AUT-OTRA' : x)))));
test('D05 versión incongruente', () => conFixture(2, 'reevaluar', (f) => assert.throws(() =>
  f.ejecutar(f.args.map((x) => x === '2' ? '3' : x)))));
test('D06 RUN incongruente', () => conFixture(1, 'evaluar', (f) => assert.throws(() =>
  f.ejecutar(f.args.map((x) => x === f.runId ? 'RUN-G87-V1-20261023-120000' : x)))));
test('D07 contexto fuera de RUN', () => conFixture(1, 'evaluar', (f) => {
  const fuera = path.join(f.root, 'otro.json'); fs.copyFileSync(f.archivo, fuera);
  assert.throws(() => f.ejecutar(f.args.map((x) => x === f.archivo ? fuera : x)));
}));
test('D08 recuperación sin objetivo', () => conFixture(1, 'recuperar', (f) =>
  assert.throws(() => f.ejecutar(f.args.slice(0, -2)))));
test('D09 recuperación coherente', () => conFixture(1, 'recuperar', (f) =>
  assert.equal(f.ejecutar().objetivo, f.runId)));
test('D10 reevaluación sin alcance', () => conFixture(2, 'reevaluar', (f) => {
  fs.writeFileSync(f.archivo, JSON.stringify({ ...f.contexto, alcance_reevaluacion: null }));
  assert.throws(() => f.ejecutar());
}));
const defs = Object.fromEntries(casos.map((c) => [c, { titulo: c, esperado: 'criterio original' }]));
function informe(version) {
  return generarInforme({ grupo: 'TC-M03-G87', version, run_id: 'RUN-G87-V' + version + '-20261023-110000',
    intento: 7, operacion: version === 1 ? 'REINTENTAR' : 'REEVALUAR', ambiente: 'SINTETICO',
    inicio: '2026-10-23T11:00:00Z', cierre: { run: {}, rollback: {} }, casos: {}, comprobaciones: [],
    incidencias: [], alcance_reevaluacion: { version_anterior: version - 1, casos,
      motivo: 'revisar', incumplimientos_previos: 'pendiente', correcciones_informadas: 'texto aportado literalmente',
      resultado_esperado: 'comprobar' } }, defs);
}
test('D11 informe V2 preserva corrección informada', () => {
  const md = informe(2); assert.match(md, /texto aportado literalmente/); assert.match(md, /Alcance de reevaluación/);
});
test('D12 informe V1 no agrega reevaluación', () => assert.doesNotMatch(informe(1), /Alcance de reevaluación/));
