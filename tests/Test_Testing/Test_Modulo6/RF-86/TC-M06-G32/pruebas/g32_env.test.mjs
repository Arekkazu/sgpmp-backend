import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import http from 'node:http';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { leerEnv, pedir, sanear, periodoDestino, preciosVigentes } from '../g32.mjs';
import { CASOS, oficialidadLocal } from '../lib/g32_core.mjs';
import { ejecutarNewman } from './newman_hijo.mjs';

test('leerEnv carga archivo presente sin imprimir secretos y deja la autorización al proceso', () => {
  const p = path.join(os.tmpdir(), `g32-env-${process.pid}.txt`);
  try {
    fs.writeFileSync(p, 'QA_CONTADOR_EMAIL=cuenta@ejemplo.test\nQA_CONTADOR_PASSWORD=clave-local\nQA_AUTORIZADO=SI\n', 'utf8');
    const e = leerEnv({ QA_AUTORIZADO: undefined }, p);
    assert.equal(e.QA_CONTADOR_PASSWORD, 'clave-local');
    assert.equal(e.QA_AUTORIZADO, undefined);
    assert.ok(!sanear('clave-local cuenta@ejemplo.test', ['clave-local']).includes('clave-local'));
    assert.ok(!sanear('clave-local cuenta@ejemplo.test', ['clave-local']).includes('cuenta@ejemplo.test'));
  } finally { fs.rmSync(p, { force: true }); }
});
test('leerEnv tolera archivo ausente', () => {
  const e = leerEnv({ QA_AUTORIZADO: 'SI' }, path.join(os.tmpdir(), `g32-inexistente-${process.pid}`));
  assert.equal(e.QA_AUTORIZADO, 'SI');
  assert.equal(e.QA_CONTADOR_EMAIL, undefined);
});
test('solo el período que contiene hoy ABIERTO es elegible', () => {
  const periodos = [
    { id_periodo_contable: 6, numero_id_tributaria: 'titular-local', estado: 'ABIERTO', fecha_inicio: '2026-10-01', fecha_fin: '2026-10-31' },
    { id_periodo_contable: 7, numero_id_tributaria: 'titular-local', estado: 'CERRADO', fecha_inicio: '2026-11-01', fecha_fin: '2026-11-30' },
    { id_periodo_contable: 8, numero_id_tributaria: 'titular-local', estado: 'ABIERTO', fecha_inicio: '2026-12-01', fecha_fin: '2026-12-31' },
  ];
  assert.match(periodoDestino(periodos, 'titular-local', '2026-11-08').motivo, /CERRADO/);
  periodos[1].estado = 'EN_CIERRE';
  assert.match(periodoDestino(periodos, 'titular-local', '2026-11-08').motivo, /EN_CIERRE/);
  periodos[1].estado = 'ABIERTO';
  assert.equal(periodoDestino(periodos, 'titular-local', '2026-11-08').periodo.id_periodo_contable, 7);
});
test('precio RF-89 elige la última fecha y mayor ID de la fuente prioritaria', () => {
  const base = { id_especie: 39, categoria: 'PESO_KG', fuente: 'MERCADO_ACTIVO', fecha_vencimiento: null };
  const precios = [
    { ...base, id_precio_mercado: 15, fecha_vigencia: '2026-11-01' },
    { ...base, id_precio_mercado: 17, fecha_vigencia: '2026-11-08' },
    { ...base, id_precio_mercado: 18, fecha_vigencia: '2026-11-08' },
    { ...base, id_precio_mercado: 19, fecha_vigencia: '2026-11-08', fuente: 'ESTIMADA' },
  ];
  assert.equal(preciosVigentes(precios, 39, '2026-11-08')?.id_precio_mercado, 18);
});
test('delete_sin_secreto: el cierre lleva X-Sandbox-Secret aun sin runId', async () => {
  const recibidas = [];
  const server = http.createServer((req, res) => {
    recibidas.push({ metodo: req.method, secreto: req.headers['x-sandbox-secret'], run: req.headers['x-test-run-id'] });
    const ok = req.method === 'DELETE' && req.headers['x-sandbox-secret'] === 'secreto-local';
    res.writeHead(ok ? 200 : 400, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify(ok ? { ok: true } : { error_code: 'VAL_ENTRADA' }));
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  try {
    const r = { solicitudes: [], _limite: Date.now() + 30000, _seguidos5xx: 0, _corte: false };
    const api = `http://127.0.0.1:${server.address().port}`;
    const ruta = '/test-control/runs/RUN-G32-V1-20261107-000000';
    const sinSecreto = await pedir(r, api, 'DELETE', ruta);
    assert.equal(sinSecreto.http, 400);
    assert.equal(sinSecreto.fila.cuerpo_saneado, '{"error_code":"VAL_ENTRADA"}');
    const cierre = await pedir(r, api, 'DELETE', ruta, { secreto: 'secreto-local' });
    assert.equal(cierre.http, 200);
    assert.deepEqual(recibidas, [
      { metodo: 'DELETE', secreto: undefined, run: undefined },
      { metodo: 'DELETE', secreto: 'secreto-local', run: undefined },
    ]);
  } finally { await new Promise(resolve => server.close(resolve)); }
});
test('artefactos fuente UTF-8 sin mojibake', () => {
  for (const q of ['../g32.mjs', '../lib/g32_core.mjs', '../README.md', '../G32.postman_collection.json']) {
    const s = fs.readFileSync(new URL(q, import.meta.url), 'utf8');
    assert.doesNotMatch(s, /Ã.|Â.|â€“|â€”|�/);
  }
});
test('oficialidad exige rollback, casos concluyentes y Newman; el aviso persistente no la altera', () => {
  const r = { casos: Object.fromEntries(CASOS.map(k => [k, { estado: 'APROBADO' }])),
    cierre: { rollback: { verificado: true } }, herramientas: { newman: { iteraciones: 1, fallos: 0 } },
    efectos_persistentes_declarados: { precios_registrados: 2, id_precio_mercado: [402, 403] } };
  assert.equal(oficialidadLocal(r), true);
  r.efectos_persistentes_declarados.bandeja_contador_qa = { estado: 'NO_VERIFICABLE' };
  assert.equal(oficialidadLocal(r), true);
  r.casos[CASOS[2]].estado = 'RECHAZADO';
  assert.equal(oficialidadLocal(r), true);
  r.casos[CASOS[2]].estado = 'BLOQUEADO';
  assert.equal(oficialidadLocal(r), false);
  r.casos[CASOS[2]].estado = 'APROBADO';
  r.cierre.rollback.verificado = false;
  assert.equal(oficialidadLocal(r), false);
  r.cierre.rollback.verificado = true;
  r.herramientas.newman.iteraciones = 0;
  assert.equal(oficialidadLocal(r), false);
});

test('newman_hijo exporta fuera del grupo y limpia su directorio temporal', async () => {
  const grupo = fileURLToPath(new URL('../', import.meta.url));
  const antesGrupo = fs.readdirSync(grupo).sort();
  const temporales = () => fs.readdirSync(os.tmpdir()).filter(x => x.startsWith('g32-newman-')).sort();
  const antesTmp = temporales();
  const coleccion = { info: { name: 'G32 local sin solicitudes', _postman_id: 'g32-env-local',
    schema: 'https://schema.getpostman.com/json/collection/v2.1.0/collection.json' }, item: [] };
  const resultado = await ejecutarNewman({ coleccion, environment: { values: [] }, timeout: 1000 });
  assert.equal(resultado.fallido, false);
  assert.equal(resultado.reporte_exportado, true);
  assert.deepEqual(fs.readdirSync(grupo).sort(), antesGrupo);
  assert.deepEqual(temporales(), antesTmp);
});
