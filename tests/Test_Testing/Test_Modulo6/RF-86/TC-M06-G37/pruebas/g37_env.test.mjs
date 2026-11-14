import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { CAPACIDADES, comprobar, contexto, validarPrecondicionIoT, preflight, compararEsquema,
  contrastarRespuesta, esquema } from '../g37.mjs';
import { CASOS, CONTRATO, mock, validarMock, periodoDestino, oraculo011, oraculo013 } from '../lib/g37_core.mjs';

const dir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
test('alcance V2 y colección vigentes', () => {
  assert.deepEqual(CASOS, ['TC-M06-011','TC-M06-013']);
  assert.deepEqual(CAPACIDADES.casos,CASOS);
  assert.equal(comprobar(),0);
  const col = JSON.parse(fs.readFileSync(path.join(dir,'G37.postman_collection.json'),'utf8'));
  assert.deepEqual(col.item.map(x=>x.name),['acumulado','cadena']);
  assert.equal(col.item.some(x=>x.request.url.includes('/estados-resultados')),false);
});
test('contrato y semilla IoT con dispositivo y lectura parametrizados', () => {
  assert.ok(CONTRATO.peticiones.some(x=>x.id==='acumulado'));
  for (const p of CONTRATO.peticiones) assert.equal(validarMock(p.id,mock(p.id)),true);
  const semilla = JSON.parse(fs.readFileSync(path.join(dir,'pruebas/precondicion_iot.json'),'utf8'));
  assert.equal(validarPrecondicionIoT(semilla),semilla);
  assert.equal(semilla.bovinos.length,4);
});
test('periodos: cierre nulo o en proceso y campo accesorio discordante', () => {
  const periodo = mock('periodos')[0];
  assert.equal(compararEsquema('periodos', esquema([periodo])), true);
  const enProceso = { ...periodo, ultimo_cierre: { paso_actual: 3,
    activos_procesados: null, activos_pendientes: null, activos_excluidos: null,
    precios_congelados: null, error_detalle: null, fecha_fin: null,
    tiempo_ejecucion_ms: null, hash_cierre: null } };
  assert.equal(compararEsquema('periodos', esquema([enProceso])), true);
  const r = { contraste_contrato: [], discrepancias_contrato: [], problemas_tecnicos: [], observaciones: {} };
  assert.equal(contrastarRespuesta(r, 'periodos', 'contador', 200,
    [{ ...enProceso, ultimo_cierre: 42 }]), true);
  assert.equal(r.discrepancias_contrato.length, 0);
  assert.equal(r.contraste_contrato[0].resultado, 'observacion');
  assert.ok(r.observaciones.contrato_periodos.length);
  assert.equal(contrastarRespuesta(r, 'periodos', 'contador', 200,
    [{ ...enProceso, estado: 42 }]), false);
  assert.equal(r.discrepancias_contrato.length, 1);
});
test('período destino solo actual ABIERTO', () => {
  const ps = [{ numero_id_tributaria:'NIT-D',fecha_inicio:'2026-01-01',fecha_fin:'2026-12-31',
    estado:'CERRADO' },{ numero_id_tributaria:'NIT-D',fecha_inicio:'2027-01-01',
    fecha_fin:'2027-12-31',estado:'ABIERTO' }];
  assert.equal(periodoDestino(ps,'NIT-D','2026-11-12'),null);
  ps[0].estado='ABIERTO';
  assert.equal(periodoDestino(ps,'NIT-D','2026-11-12'),ps[0]);
});
test('guardia sin autorización bloquea antes de red', () => {
  let llamadas=0;
  const c={runId:'RUN-G37-V2-20261112-000000',ensayo:true};
  const p=preflight(c,{QA_AUTORIZADO:'NO'},'6.2.2');
  assert.equal(p.ok,false); assert.equal(llamadas,0);
});
