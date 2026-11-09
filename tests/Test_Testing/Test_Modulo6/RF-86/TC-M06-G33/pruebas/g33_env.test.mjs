import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import http from 'node:http';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { leerEnv, sanear, periodoDestino, preciosVigentes } from '../g33.mjs';
import { CASOS, oficialidadLocal, evaluarOraculo } from '../lib/g33_core.mjs';
import { ejecutarNewman } from './newman_hijo.mjs';

test('leerEnv: archivo presente, ausente y autorización del proceso', () => {
  const archivo = path.join(os.tmpdir(), 'g33-env-' + process.pid + '.txt');
  try {
    fs.writeFileSync(archivo, 'QA_CONTADOR_EMAIL=cuenta@ejemplo.test\nQA_CONTADOR_PASSWORD=clave-local\nQA_AUTORIZADO=SI\n');
    const env = leerEnv({ QA_AUTORIZADO: undefined }, archivo);
    assert.equal(env.QA_CONTADOR_PASSWORD, 'clave-local');
    assert.equal(env.QA_AUTORIZADO, undefined);
    assert.ok(!sanear('clave-local cuenta@ejemplo.test', ['clave-local']).includes('clave-local'));
  } finally { fs.rmSync(archivo, { force: true }); }
  assert.equal(leerEnv({ QA_AUTORIZADO: 'SI' }, archivo).QA_AUTORIZADO, 'SI');
});

test('período destino y precio vigente', () => {
  const p = [
    { id_periodo_contable: 7, numero_id_tributaria: 'titular', estado: 'CERRADO', fecha_inicio: '2026-11-01', fecha_fin: '2026-11-30' },
    { id_periodo_contable: 8, numero_id_tributaria: 'titular', estado: 'ABIERTO', fecha_inicio: '2026-12-01', fecha_fin: '2026-12-31' },
  ];
  assert.equal(periodoDestino(p, 'titular', '2026-11-08').periodo.id_periodo_contable, 8);
  p[0].estado = 'EN_CIERRE';
  assert.match(periodoDestino(p, 'titular', '2026-11-08').motivo, /EN_CIERRE/);
  const base = { id_especie: 39, categoria: 'PESO_KG', fecha_vigencia: '2026-11-08' };
  assert.equal(preciosVigentes([{ ...base, id_precio_mercado: 17, fuente: 'MERCADO_ACTIVO' },
    { ...base, id_precio_mercado: 18, fuente: 'MERCADO_ACTIVO' },
    { ...base, id_precio_mercado: 19, fuente: 'ESTIMADA' }], 39, '2026-11-08').id_precio_mercado, 18);
});

test('oráculo exige lectura completa y valor positivo igual', () => {
  const base = { variaciones: [], lineas: [], mediciones: [], calculos: [], auditoria: [], bandeja: [],
    auditoriaCompleta: true, bandejaCompleta: true, calculoUltimo: { id_calculo_valor_razonable: 1, valor_neto: 1000 } };
  const pos = { ...base, auditoria: [{ id_evento: 1, tipo_evento: 'MEDICION_SIN_VARIACION', id_referencia: 9,
    id_activo_biologico: 2, id_periodo_contable: 3, severidad_evento: 'INFO', payload_evento: { valor_neto: '1000' } }] };
  const args = { anterior: base, posterior: pos, eventoId: 9, activoId: 2, periodoId: 3 };
  assert.equal(evaluarOraculo(args).estado, 'APROBADO');
  assert.equal(evaluarOraculo({ ...args, posterior: { ...pos, lineas: [{ id_linea_asiento_nic41: 3, id_activo_biologico: 2 }] } }).estado, 'RECHAZADO');
  assert.equal(evaluarOraculo({ ...args, posterior: { ...pos, auditoriaCompleta: false } }).estado, 'NO_CONCLUYENTE');
});

test('oficialidad requiere cierre, caso concluyente y Newman real', () => {
  const r = { cierre: { rollback: { verificado: true } }, casos: { [CASOS[0]]: { estado: 'APROBADO' } },
    herramientas: { newman: { iteraciones: 1, codigo: 0, fallos: 0 } } };
  assert.equal(oficialidadLocal(r), true);
  r.casos[CASOS[0]].estado = 'RECHAZADO'; r.herramientas.newman.fallos = 1;
  assert.equal(oficialidadLocal(r), true);
  r.casos[CASOS[0]].estado = 'NO_CONCLUYENTE';
  assert.equal(oficialidadLocal(r), false);
});

test('newman_hijo exporta fuera del grupo y limpia su directorio temporal', async () => {
  const grupo = fileURLToPath(new URL('../', import.meta.url));
  const antesGrupo = fs.readdirSync(grupo).sort();
  const temporales = () => fs.readdirSync(os.tmpdir()).filter(x => x.startsWith('g33-newman-')).sort();
  const antesTmp = temporales();
  let lecturas = 0;
  const server = http.createServer((req, res) => {
    lecturas++;
    assert.equal(req.url, '/newman-probe');
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ ok: true }));
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  try {
    const url = `http://127.0.0.1:${server.address().port}/newman-probe`;
    const coleccion = { info: { name: 'G33 sonda local', _postman_id: 'g33-env-local',
      schema: 'https://schema.getpostman.com/json/collection/v2.1.0/collection.json' },
      item: [{ name: 'sonda', request: { method: 'GET', url } }] };
    const resultado = await ejecutarNewman({ coleccion, environment: { values: [] }, timeout: 30000 });
    assert.equal(resultado.fallido, false);
    assert.equal(resultado.reporte_exportado, true);
    assert.equal(resultado.solicitudes.length, 1);
    assert.equal(resultado.solicitudes[0].http, 200);
    assert.equal(lecturas, 1);
    assert.deepEqual(fs.readdirSync(grupo).sort(), antesGrupo);
    assert.deepEqual(temporales(), antesTmp);
  } finally { await new Promise(resolve => server.close(resolve)); }
});
