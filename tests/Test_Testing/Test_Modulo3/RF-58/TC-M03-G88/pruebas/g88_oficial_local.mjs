import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { evaluarOficialidad } from '../lib/g88_oficial.mjs';
import { derivarIncidencias, generarInforme } from '../lib/g88_informe.mjs';

const grupo = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const run = path.join(grupo, 'Resultados', 'RUN-G88-V1-20261030-202846');
export function ensayoOficialidad() {
  globalThis.fetch = () => { throw new Error('BLOQUEO_RED_LOCAL'); };
  const original = JSON.parse(fs.readFileSync(path.join(run, 'resultado.json'), 'utf8'));
  const newman = JSON.parse(fs.readFileSync(path.join(run, 'newman', 'newman-TC-M03-G88.json'), 'utf8'));
  assert.ok((newman.run?.executions ?? []).length > 0, 'Newman oficial legible');
  const r = structuredClone(original);
  Object.assign(r, evaluarOficialidad(r, run));
  assert.equal(r.oficial, true);
  assert.equal(r.clasificacion_prevista, 'OFICIAL');
  assert.equal(r.motivo_no_oficial, null);
  r.incidencias = derivarIncidencias(r);
  assert.equal(r.incidencias.length, 3, 'una incidencia conjunta 170/171, una 172 y una 266');
  assert.deepEqual(r.incidencias[0].casos, ['TC-M03-170', 'TC-M03-171']);
  assert.equal(r.incidencias.find(x => x.caso === 'TC-M03-266')?.equipo, 'Desarrollo');
  const informe = generarInforme(r);
  assert.match(informe, /^# TC-M03-G88 — RECHAZADO/m);
  for (const seccion of ['## Decisión del caso', '## Detalle por caso', '## Incidencias de producto',
    '## Comprobaciones técnicas DBA-01', '## Historial de intentos', '## Cierre y rollback', '## Evidencias y acciones'])
    assert.ok(informe.includes(seccion), seccion);
  for (const n of ['169', '170', '171', '172', '180', '266']) {
    const bloque = informe.split(`### TC-M03-${n}\n`)[1]?.split('\n### ')[0] ?? '';
    for (const linea of ['**Qué se hizo:**', '**Qué se esperaba:**', '**Qué se observó:**', '**Por qué '])
      assert.ok(bloque.includes(linea), `${n}: ${linea}`);
  }
  assert.equal((informe.match(/^### DEV-G88-/gm) ?? []).length, 3);
  assert.ok(!informe.includes('### DEV-171'));
  const sinAssert = structuredClone(r);
  sinAssert.comprobaciones = sinAssert.comprobaciones.filter(x => x.id !== 'API-170-03');
  const falta = evaluarOficialidad(sinAssert, run);
  assert.equal(falta.oficial, false);
  assert.match(falta.motivo_no_oficial, /API-170-03/);
  const sinRollback = structuredClone(r);
  sinRollback.cierre.rollback.verificado = false;
  const rollback = evaluarOficialidad(sinRollback, run);
  assert.equal(rollback.oficial, false);
  assert.match(rollback.motivo_no_oficial, /Rollback no verificado/);
  return { oficial: r.oficial, clasificacion: r.clasificacion_prevista, incidencias: r.incidencias.length,
    primer_lineas: informe.split('\n').slice(0, 40) };
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url))
  console.log(JSON.stringify(ensayoOficialidad(), null, 2));
