#!/usr/bin/env node
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { leerEnv, preflight } from '../g051.mjs';
import { CASOS } from '../lib/g051_escenario.mjs';

const temporal = fs.mkdtempSync(path.join(os.tmpdir(), 'g051-env-'));
try {
  const archivo = path.join(temporal, '.env.qa');
  const valores = {
    SIGAB_API_TEST_BASE: 'https://www.api.inmero.co/api-sgpmp-test',
    QA_SANDBOX_SECRET: 'MARCADOR_SANDBOX_G051',
    QA_ADMIN_EMAIL: 'marcador@example.test',
    QA_ADMIN_PASSWORD: 'MARCADOR_PASSWORD_G051',
    RF71_INTERNAL_KEY: 'MARCADOR_RF71_G051'
  };
  fs.writeFileSync(archivo, [
    '# archivo temporal; no se usa el .env.qa real',
    ...Object.entries(valores).map(([clave, valor]) => `${clave}="${valor}"`),
    'QA_AUTORIZADO=SI'
  ].join('\n'), 'utf8');
  const proceso = { QA_AUTORIZADO: 'SI' };
  const c = { runId: 'ENSAYO-G051-ENV', version: 1, operacion: 'evaluar' };
  const desdeArchivo = leerEnv(proceso, archivo);
  assert.deepEqual(Object.fromEntries(Object.keys(valores).map(k => [k, desdeArchivo[k]])), valores);
  const pasa = preflight(c, desdeArchivo);
  assert.equal(pasa.ok, true);
  assert.deepEqual(pasa.barreras, []);
  const salida = JSON.stringify(pasa);
  for (const valor of Object.values(valores)) assert.equal(salida.includes(valor), false);

  const ausente = preflight(c, leerEnv(proceso, path.join(temporal, 'ausente.env')));
  assert.equal(ausente.ok, false);
  assert.deepEqual(ausente.barreras, [...Object.keys(valores), 'API_NO_CANONICA']);
  assert.equal(preflight(c, leerEnv({}, archivo)).barreras.includes('QA_AUTORIZADO'), true);
  const prioridad = leerEnv({ ...proceso, QA_ADMIN_EMAIL: 'proceso@example.test' }, archivo);
  assert.equal(prioridad.QA_ADMIN_EMAIL, 'proceso@example.test');
  const reintentoV2 = { ...c, version: 2, operacion: 'reintentar', contexto: {
    version_anterior: 1, alcance_reevaluacion: { casos: CASOS, version_anterior: 1 } } };
  assert.deepEqual(preflight(reintentoV2, desdeArchivo).barreras, []);
  for (const contexto of [undefined, {},
    { ...reintentoV2.contexto, alcance_reevaluacion: undefined },
    { ...reintentoV2.contexto, alcance_reevaluacion: { casos: CASOS.slice(1), version_anterior: 1 } },
    { ...reintentoV2.contexto, alcance_reevaluacion: { casos: CASOS, version_anterior: 2 } },
    { ...reintentoV2.contexto, version_anterior: 2 }]) {
    assert.deepEqual(preflight({ ...reintentoV2, contexto }, desdeArchivo).barreras,
      ['REEVALUACION_SIN_DECISION']);
  }
  assert.deepEqual(preflight({ ...reintentoV2, operacion: 'evaluar' }, desdeArchivo).barreras,
    ['REEVALUACION_SIN_DECISION']);
  assert.deepEqual(preflight({ ...reintentoV2, operacion: 'reevaluar' }, desdeArchivo).barreras, []);
  console.log('OK env_archivo: preflight pasa; ausente falla; autorización y precedencia verificadas; valores ocultos');
} finally {
  if (!path.resolve(temporal).startsWith(path.resolve(os.tmpdir()) + path.sep)) throw Error('TEMP_FUERA_RAIZ');
  fs.rmSync(temporal, { recursive: true, force: true });
}
