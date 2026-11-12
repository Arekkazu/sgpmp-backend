import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { CONTRATO, mock, seleccionarCandidatos, oraculo013, decidirVerificacion } from '../lib/g37_core.mjs';
import { verificarPermisos } from '../g37.mjs';

const permisos = actor => ({ permisos: Object.entries(CONTRATO.roles[actor].permisos)
  .flatMap(([nombre_recurso, acciones], id_recurso) => acciones.map(id_accion =>
    ({ id_recurso: id_recurso + 1, id_accion, nombre_recurso }))) });

test('permisos de ambos actores: pares exactos y esquema', () => {
  for (const actor of ['contador', 'admin']) assert.equal(verificarPermisos(permisos(actor), actor), true);
  const falta = permisos('contador');
  falta.permisos = falta.permisos.filter(x => !(x.nombre_recurso === 'trazabilidad_contable' && x.id_accion === 5));
  assert.throws(() => verificarPermisos(falta, 'contador'), /trazabilidad_contable:5/);
  assert.throws(() => verificarPermisos({ permisos: [{ id_recurso: '1' }] }, 'contador'), /Esquema/);
});

test('precondición coherente prioriza el activo', () => {
  const base = { especie: 'Bovino', tipo: 'INDIVIDUAL', estado: 'ACTIVO', valorado_por_costo: false,
    periodo: { id_periodo_contable: 8, estado: 'ABIERTO' }, precio: { id_precio_mercado: 20 },
    calculo: { id_precio_mercado: 20, estado: 'CALCULADO' }, peso: 100 };
  const candidatos = [943, 944, 945, 946, 947].map(id_activo_biologico =>
    ({ ...base, id_activo_biologico, dispositivo: id_activo_biologico === 947 ? 77 : null }));
  const p = { id_activo_biologico: 947, id_dispositivo_iot: 77 };
  assert.equal(seleccionarCandidatos(candidatos, 4, p).elegido[0].id_activo_biologico, 947);
});

test('RF-91 HTTP 500 rechaza aun sin historial M03', () => {
  assert.equal(decidirVerificacion(500, 'ERROR_INTERNO').estado, 'RECHAZADO');
});

test('RF-91 422 PERIODO_NO_ABIERTO queda NO_CONCLUYENTE técnico', () => {
  const decision = decidirVerificacion(422, 'PERIODO_NO_ABIERTO');
  assert.equal(decision.estado, 'NO_CONCLUYENTE');
  assert.match(decision.motivo, /período 8.*ABIERTO/);
});

test('RF-91 nivel 1 bloquea sin precondición; 2 a 4 rechazan', () => {
  const inicial = { estado_trazabilidad: 'VERIFICACION_PENDIENTE' };
  const cadenaInicial = { ...mock('cadena'), estado_trazabilidad: 'VERIFICACION_PENDIENTE',
    estado_verificacion: null, nivel_fallo: null, eslabones: null };
  const final = { estado_trazabilidad: 'PENDIENTE_TRAZABILIDAD' };
  for (const nivel_fallo of [1, 2, 3, 4]) {
    const cadena = { ...mock('cadena'), nivel_fallo, estado_verificacion: 'FALLIDO' };
    assert.equal(oraculo013({ inicial, cadenaInicial, final, cadena, evento: 1, lecturaApta: null }).estado,
      nivel_fallo === 1 ? 'BLOQUEADO' : 'RECHAZADO');
  }
});

test('Newman acepta lista vacía y eslabones null sin asignar línea cero', () => {
  const dir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
  const col = JSON.parse(fs.readFileSync(path.join(dir, 'G37.postman_collection.json'), 'utf8'));
  assert.equal(col.item.length, 3);
  const scripts = col.item.map(x => x.event[0].script.exec.join('\n'));
  assert.match(scripts[0], /an\('array'\)/);
  assert.match(scripts[2], /property\('eslabones'\)/);
  assert.doesNotMatch(fs.readFileSync(path.join(dir, 'g37.mjs'), 'utf8'), /linea: String\(linea \?\? 0\)/);
});
