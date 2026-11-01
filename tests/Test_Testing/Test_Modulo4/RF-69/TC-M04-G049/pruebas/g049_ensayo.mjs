#!/usr/bin/env node
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import http from 'node:http';
import { fileURLToPath } from 'node:url';
import { evaluar, informe } from '../g049.mjs';
import { CASOS, CAPACIDADES } from '../lib/g049_escenario.mjs';
import { contextoEjecucion } from '../lib/contrato_ejecutor.mjs';
import { contieneMojibake } from '../lib/seguridad.mjs';
import { clasificarRegistro } from './registro_qa.mjs';

const MODOS = [
  ['todo_ok', ['APROBADO', 'APROBADO', 'APROBADO', 'APROBADO'], true],
  ['v2_reevaluacion', ['APROBADO', 'APROBADO', 'APROBADO', 'APROBADO'], true],
  ['snapshot_final', ['APROBADO', 'APROBADO', 'APROBADO', 'APROBADO'], true],
  ['id_uuid', ['APROBADO', 'RECHAZADO', 'APROBADO', 'NO_CONCLUYENTE'], false],
  ['id_cadena', ['APROBADO', 'APROBADO', 'APROBADO', 'APROBADO'], true],
  ['id_repetido', ['APROBADO', 'RECHAZADO', 'APROBADO', 'APROBADO'], true],
  ['id_nulo', ['NO_CONCLUYENTE', 'RECHAZADO', 'NO_CONCLUYENTE', 'NO_CONCLUYENTE'], false],
  ['id_cero', ['NO_CONCLUYENTE', 'RECHAZADO', 'NO_CONCLUYENTE', 'NO_CONCLUYENTE'], false],
  ['id_negativo', ['APROBADO', 'RECHAZADO', 'APROBADO', 'APROBADO'], true],
  ['id_decimal', ['APROBADO', 'RECHAZADO', 'APROBADO', 'APROBADO'], true],
  ['referencia_distinta', ['APROBADO', 'APROBADO', 'APROBADO', 'RECHAZADO'], true],
  ['referencia_422', ['APROBADO', 'NO_CONCLUYENTE', 'APROBADO', 'RECHAZADO'], false],
  ['campo_faltante', ['APROBADO', 'APROBADO', 'RECHAZADO', 'APROBADO'], true],
  ['sin_referencia', ['APROBADO', 'APROBADO', 'APROBADO', 'RECHAZADO'], true],
  ['sin_historial', ['RECHAZADO', 'APROBADO', 'APROBADO', 'APROBADO'], true],
  ['clave_403', ['BLOQUEADO', 'BLOQUEADO', 'BLOQUEADO', 'BLOQUEADO'], false],
  ['error5xx', ['BLOQUEADO', 'BLOQUEADO', 'BLOQUEADO', 'BLOQUEADO'], false],
  ['sin_respuesta', ['NO_CONCLUYENTE', 'NO_CONCLUYENTE', 'NO_CONCLUYENTE', 'NO_CONCLUYENTE'], false],
];
const CLAVE = 'ENSAYO_RF71_SECRETO_G049_123456';
const UUIDS = ['aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa1',
  'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa2', 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa3'];
const ENTEROS = [58, 59, 60];
const responder = (res, code, body, run = null) => {
  res.writeHead(code, { 'Content-Type': 'application/json', ...(run ? { 'X-Test-Run-Id': run } : {}) });
  res.end(JSON.stringify(body));
};
function campo(raw, key) {
  const re = new RegExp(`name="${key}"[^\\r\\n]*\\r\\n\\r\\n([^\\r\\n]*)`);
  return raw.match(re)?.[1] ?? null;
}
async function servidor(modo) {
  const versiones = [], peticiones = [];
  const server = http.createServer((req, res) => {
    const url = new URL(req.url, 'http://127.0.0.1');
    const run = req.headers['x-test-run-id'];
    peticiones.push({ metodo: req.method, ruta: url.pathname });
    if (req.method === 'POST' && url.pathname === '/sesiones/') {
      req.resume(); req.on('end', () => responder(res, 200, { token: 'ensayo-token' })); return;
    }
    if (req.method === 'DELETE' && url.pathname.startsWith('/test-control/runs/'))
      return responder(res, 200, { status: 'Rollback exitoso' });
    if (req.method === 'GET' && url.pathname === '/configuracion/variables-ambientales')
      return responder(res, 200, { total: 1, items: [{ id_variable_ambiental: 7 }] }, run);
    if (req.method === 'POST' && url.pathname === '/prediccion/modelos') {
      const chunks = []; req.on('data', x => chunks.push(x)); req.on('end', () => {
        if (modo === 'sin_respuesta') { req.socket.destroy(); return; }
        if (modo === 'clave_403') return responder(res, 403, { error_code: 'REGISTRO_INTERNO_REQUERIDO' }, run);
        if (modo === 'error5xx') return responder(res, 500, { error_code: 'ERROR_MODELO' }, run);
        if (modo === 'referencia_422' && versiones.length === 2)
          return responder(res, 422, { error_code: 'REFERENCIA_RECHAZADA' }, run);
        assert.equal(req.headers['x-rf71-internal-key'], CLAVE);
        const raw = Buffer.concat(chunks).toString('latin1');
        assert.ok(raw.includes('name="archivo_modelo"'));
        const numero = versiones.length + 1;
        const id = modo === 'id_uuid' ? UUIDS[numero - 1]
          : modo === 'id_nulo' && numero === 1 ? null
            : modo === 'id_cero' && numero === 1 ? 0
              : modo === 'id_negativo' && numero === 1 ? -1
                : modo === 'id_decimal' && numero === 1 ? 1.5
          : modo === 'id_repetido' && numero === 3 ? 59
            : modo === 'id_cadena' ? String(ENTEROS[numero - 1]) : ENTEROS[numero - 1];
        const metricas = JSON.parse(campo(raw, 'metricas_validacion'));
        const registro = { id_version: id, tipo_modelo: campo(raw, 'tipo_modelo'), estado: 'APROBADO',
          metricas_validacion: metricas, dataset_entrenamiento_hash: campo(raw, 'dataset_entrenamiento_hash'),
          hash_artefacto_modelo: campo(raw, 'hash_artefacto_sha256'),
          fecha_entrenamiento: campo(raw, 'fecha_entrenamiento'),
          timestamp_registro: new Date().toISOString(),
          id_proceso_rf71: campo(raw, 'id_proceso_rf71'), notas_validacion: null,
          version_referencia: campo(raw, 'version_referencia') };
        versiones.push(registro); responder(res, 201, registro, run);
      }); return;
    }
    if (req.method === 'GET' && url.pathname.startsWith('/prediccion/modelos/')) {
      const id = decodeURIComponent(url.pathname.split('/').at(-1));
      const version = [...versiones].reverse().find(x => String(x.id_version) === id);
      if (!version) return responder(res, 404, { error_code: 'NO_ENCONTRADO' }, run);
      const body = structuredClone(version);
      if (modo === 'campo_faltante' && String(body.id_version) === String(versiones[0].id_version))
        delete body.metricas_validacion.roc_auc_score;
      if (modo === 'sin_referencia' && String(body.id_version) === String(versiones[2]?.id_version))
        delete body.version_referencia;
      if (modo === 'referencia_distinta' && String(body.id_version) === String(versiones[2]?.id_version))
        body.version_referencia = 58;
      return responder(res, 200, body, run);
    }
    if (req.method === 'GET' && url.pathname === '/prediccion/auditoria') {
      const id = url.searchParams.get('id_referencia');
      const version = versiones.find(x => String(x.id_version) === id);
      const events = !version || modo === 'sin_historial' ? [] : [
        { tipo_evento: 'VERSION_REGISTRADA', tipo_actor: 'SISTEMA', id_usuario: null,
          id_sistema: version.id_proceso_rf71, id_referencia: id,
          payload_evento: { estado_version: modo === 'snapshot_final' ? 'APROBADO' : 'EN_VALIDACION' } },
        { tipo_evento: 'VERSION_APROBADA', tipo_actor: 'SISTEMA', id_usuario: null,
          id_sistema: version.id_proceso_rf71, id_referencia: id,
          payload_evento: { estado_version: 'APROBADO' } } ];
      return responder(res, 200, { total: events.length, items: events }, run);
    }
    responder(res, 404, { error_code: 'NO_ENCONTRADO' }, run);
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  return { server, peticiones, base: `http://127.0.0.1:${server.address().port}` };
}
const temporal = fs.mkdtempSync(path.join(os.tmpdir(), 'g049-ensayo-'));
try {
  for (const [modo, esperados, oficial] of MODOS) {
    const s = await servidor(modo);
    try {
      const dir = path.join(temporal, modo); fs.mkdirSync(dir);
      const runId = `ENSAYO-G049-20261027-000000-${modo}`;
      const archivo = path.join(dir, 'contexto_operacion.json');
      const referencia = `ENSAYO_LOCAL_${modo}`;
      const esV2 = modo === 'v2_reevaluacion';
      fs.writeFileSync(archivo, JSON.stringify({ grupo: 'G049', version: esV2 ? 2 : 1, intento: 1,
        run_id: runId, operacion: esV2 ? 'REEVALUAR' : 'EVALUAR', referencia, casos: CASOS,
        ...(esV2 ? { version_anterior: 1, alcance_reevaluacion: 'TC-M04-114 a TC-M04-117' } : {}) }));
      const c = esV2 ? { operacion: 'reevaluar', version: 2, intento: 1, runId,
        referencia, directorio: dir, ensayo: true }
        : contextoEjecucion(['--operacion', 'evaluar', '--version', '1', '--intento', '1',
          '--run-id', runId, '--autorizacion', referencia, '--contexto', archivo],
        { grupo: 'G049', casos: CASOS, directorio: path.resolve(fileURLToPath(import.meta.url), '../..'),
          modoEnsayo: true });
      const r = await evaluar(c, { ensayo: true, env: { QA_AUTORIZADO: 'SI',
        SIGAB_API_TEST_BASE: s.base, QA_SANDBOX_SECRET: 'ENSAYO_SANDBOX_123456',
        RF71_INTERNAL_KEY: CLAVE, QA_ADMIN_EMAIL: 'admin@example.test',
        QA_ADMIN_PASSWORD: 'ENSAYO_PASSWORD_123456' } });
      assert.deepEqual(CASOS.map(x => r.casos[x].estado), esperados,
        `${modo}: ${JSON.stringify({ problemas: r.problemas_tecnicos, motivos: r.casos })}`);
      if (modo === 'id_uuid') assert.deepEqual(r.incidencias.map(x => x.id), ['INC-M04-G049-115-V2']);
      if (modo === 'id_cadena') assert.match(r.comprobaciones[1].observacion, /cadena de dígitos/);
      if (modo === 'campo_faltante') assert.equal(r.casos['TC-M04-116'].estado, 'RECHAZADO');
      if (modo === 'snapshot_final') assert.match(r.comprobaciones[0].observacion, /foto del estado final/);
      assert.equal(r.oficial, oficial, modo);
      assert.equal(r.cierre.run.cierre_http, 200);
      assert.equal(fs.readdirSync(dir).filter(x => x.endsWith('.md')).length, 1);
      const guardado = JSON.parse(fs.readFileSync(path.join(dir, 'resultado.json'), 'utf8'));
      assert.deepEqual(guardado.casos, r.casos);
      assert.equal(guardado.run_id, runId);
      const nombreInforme = esV2 ? 'TC-M04-G049_reevaluacion_V2.md' : 'TC-M04-G049_resultado.md';
      const md = fs.readFileSync(path.join(dir, nombreInforme), 'utf8');
      assert.equal(md, informe(r));
      if (esV2) {
        assert.match(md, /Comparación V1 → V2 por caso/);
        assert.match(md, /CERRADA POR CAMBIO DE REQUISITO/);
        assert.match(md, /documento de requerimientos aún no está actualizado/);
        assert.ok(!fs.existsSync(path.join(dir, 'TC-M04-G049_resultado.md')));
      }
      assert.equal(contieneMojibake(md), false);
      const presentes = new Set(r.evidencias.filter(x => fs.existsSync(path.join(dir, x))));
      assert.equal(clasificarRegistro(CAPACIDADES, r, presentes, c), oficial);
      for (const f of ['resultado.json', nombreInforme, 'preflight.json',
        'newman/newman-G049.json', 'newman/newman-G049.html']) {
        if (fs.existsSync(path.join(dir, f))) {
          const texto = fs.readFileSync(path.join(dir, f), 'utf8');
          assert.ok(!texto.includes(CLAVE), `${modo}: clave en ${f}`);
          assert.ok(!texto.includes('ENSAYO_SANDBOX_123456'), `${modo}: sandbox en ${f}`);
          assert.ok(!texto.includes('ENSAYO_PASSWORD_123456'), `${modo}: password en ${f}`);
        }
      }
      assert.ok(s.peticiones.every(x => x.ruta !== '/test-control/query'));
      assert.equal(s.peticiones.at(-1).metodo, 'DELETE');
      assert.ok(s.peticiones.filter(x => x.metodo === 'POST' && x.ruta === '/prediccion/modelos').length <= 3);
      if (modo === 'todo_ok') assert.deepEqual(s.peticiones.slice(2, 9).map(x => `${x.metodo} ${x.ruta}`), [
        'POST /prediccion/modelos', 'GET /prediccion/modelos/' + ENTEROS[0],
        'GET /prediccion/auditoria', 'POST /prediccion/modelos',
        'GET /prediccion/modelos/' + ENTEROS[1], 'POST /prediccion/modelos',
        'GET /prediccion/modelos/' + ENTEROS[2] ]);
      console.log(`OK ${modo}: ${esperados.join('/')} ${oficial ? 'OFICIAL' : 'TÉCNICO'}`);
    } finally { await new Promise(resolve => s.server.close(resolve)); }
  }
  console.log(`OK G049: ${MODOS.length}/${MODOS.length} modos`);
} finally {
  if (!path.resolve(temporal).startsWith(path.resolve(os.tmpdir()) + path.sep)) throw Error('TEMP_FUERA_RAIZ');
  fs.rmSync(temporal, { recursive: true, force: true });
}
