#!/usr/bin/env node
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import http from 'node:http';
import { fileURLToPath } from 'node:url';
import { evaluar, informe } from '../g050.mjs';
import { CASOS, TIPOS, CAPACIDADES } from '../lib/g050_escenario.mjs';
import { contextoEjecucion } from '../lib/contrato_ejecutor.mjs';
import { contieneMojibake } from '../lib/seguridad.mjs';
import { clasificarRegistro } from './registro_qa.mjs';
import { camposProto } from '../lib/artefactos.mjs';

const MODOS = [
  ['todo_ok', ['APROBADO', 'APROBADO', 'APROBADO'], true],
  ['v2_corregido', ['APROBADO', 'APROBADO', 'APROBADO'], true],
  ['v2_defecto', ['APROBADO', 'RECHAZADO', 'APROBADO'], true],
  ['tf_como_onnx', ['APROBADO', 'RECHAZADO', 'APROBADO'], true],
  ['tf_422', ['APROBADO', 'RECHAZADO', 'APROBADO'], true],
  ['tipo_422', ['APROBADO', 'APROBADO', 'RECHAZADO'], true],
  ['componente_perdido', ['APROBADO', 'APROBADO', 'RECHAZADO'], true],
  ['clave_403', ['BLOQUEADO', 'BLOQUEADO', 'BLOQUEADO'], false],
  ['error5xx', ['BLOQUEADO', 'BLOQUEADO', 'BLOQUEADO'], false],
  ['sin_respuesta', ['NO_CONCLUYENTE', 'APROBADO', 'NO_CONCLUYENTE'], false]
];
const CLAVE = 'ENSAYO_RF71_SECRETO_G050_123456';
const SANDBOX = 'ENSAYO_SANDBOX_G050_123456';
const PASSWORD = 'ENSAYO_PASSWORD_G050_123456';
const responder = (res, code, body, run = null) => {
  res.writeHead(code, { 'Content-Type': 'application/json', ...(run ? { 'X-Test-Run-Id': run } : {}) });
  res.end(JSON.stringify(body));
};
function campo(raw, key) {
  const re = new RegExp(`name="${key}"[^\\r\\n]*\\r\\n\\r\\n([^\\r\\n]*)`);
  return raw.match(re)?.[1] ?? null;
}
function archivoModelo(raw) {
  const inicio = raw.indexOf('name="archivo_modelo"');
  if (inicio < 0) return null;
  const datos = raw.indexOf('\r\n\r\n', inicio) + 4;
  const fin = raw.indexOf('\r\n--', datos);
  return datos < 4 || fin < 0 ? null : Buffer.from(raw.slice(datos, fin), 'latin1');
}
function formatoPorEstructura(bytes) {
  let campos;
  try { campos = camposProto(bytes); } catch { campos = null; }
  if (campos?.length && campos.every(x => [1, 2].includes(x.numero))
    && campos.some(x => x.numero === 2 && x.wire === 2 && x.valor[0] === 0x0a))
    return 'TENSORFLOW_SAVED_MODEL';
  return bytes?.[0] === 0x08 ? 'ONNX' : 'FORMATO_ARTEFACTO_INVALIDO';
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
        const n = Number(campo(Buffer.concat(chunks).toString('latin1'), 'id_proceso_rf71')?.split('-').at(-1)) || peticiones.filter(x => x.metodo === 'POST' && x.ruta === '/prediccion/modelos').length;
        if (modo === 'sin_respuesta' && n === 1) { req.socket.destroy(); return; }
        if (modo === 'clave_403') return responder(res, 403, { error_code: 'REGISTRO_INTERNO_REQUERIDO' }, run);
        if (modo === 'error5xx') return responder(res, 500, { error_code: 'ERROR_MODELO' }, run);
        assert.equal(req.headers['x-rf71-internal-key'], CLAVE);
        assert.equal(req.headers['x-sandbox-secret'], SANDBOX);
        const raw = Buffer.concat(chunks).toString('latin1');
        assert.ok(raw.includes('name="archivo_modelo"'));
        const formatoDetectado = modo === 'v2_corregido' ? formatoPorEstructura(archivoModelo(raw)) : null;
        if (modo === 'v2_corregido') assert.notEqual(formatoDetectado, 'FORMATO_ARTEFACTO_INVALIDO');
        const tipo = campo(raw, 'tipo_modelo');
        const i = TIPOS.findIndex(x => x.tipo === tipo);
        assert.ok(i >= 0);
        if (modo === 'tf_422' && i === 1 && raw.includes('saved_model.pb'))
          return responder(res, 422, { error_code: 'FORMATO_ARTEFACTO_INVALIDO' }, run);
        if (modo === 'tipo_422' && i === 3) return responder(res, 422, { error_code: 'TIPO_MODELO_INVALIDO' }, run);
        const d = TIPOS[i], met = JSON.parse(campo(raw, 'metricas_validacion'));
        const id = i + 101;
        const registro = { id_version_modelo: id, tipo_modelo: tipo, paradigma: d.paradigma,
          estado_version: 'APROBADO', formato_artefacto: modo === 'v2_corregido' ? formatoDetectado
            : (modo === 'tf_como_onnx' || modo === 'v2_defecto') && i === 1 ? 'ONNX'
            : i === 1 && raw.includes('g050.onnx') ? 'ONNX' : d.formato,
          hash_artefacto_sha256: campo(raw, 'hash_artefacto_sha256'),
          componente: campo(raw, 'componente'),
          metricas_poblacionales: d.paradigma === 'POBLACIONAL' ? {
            calibracion_completada: met.calibracion_completada,
            tasa_falsos_positivos_rutina: met.tasa_falsos_positivos_rutina,
            tasa_deteccion_eventos_clinicos: met.tasa_deteccion_eventos_clinicos } : null,
          f1_score: d.paradigma === 'POBLACIONAL' ? null : met.f1_score_global,
          recall_clase_riesgo_alto: d.paradigma === 'POBLACIONAL' ? null : met.recall_clase_riesgo_alto,
          precision_modelo: d.paradigma === 'POBLACIONAL' ? null : met.precision_global,
          accuracy: d.paradigma === 'POBLACIONAL' ? null : met.accuracy,
          roc_auc_score: d.paradigma === 'POBLACIONAL' ? null : met.roc_auc_score,
          recall_por_clase: d.paradigma === 'POBLACIONAL' ? null : met.recall_por_clase,
          matriz_confusion: d.paradigma === 'POBLACIONAL' ? null : met.matriz_confusion };
        versiones.push(registro); responder(res, 201, registro, run);
      }); return;
    }
    if (req.method === 'GET' && url.pathname.startsWith('/prediccion/modelos/')) {
      const id = Number(url.pathname.split('/').at(-1));
      const version = versiones.find(x => x.id_version_modelo === id);
      if (!version) return responder(res, 404, { error_code: 'NO_ENCONTRADO' }, run);
      const body = structuredClone(version);
      if (modo === 'componente_perdido' && id === 104) body.componente = null;
      return responder(res, 200, body, run);
    }
    responder(res, 404, { error_code: 'NO_ENCONTRADO' }, run);
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  return { server, peticiones, base: `http://127.0.0.1:${server.address().port}` };
}
const temporal = fs.mkdtempSync(path.join(os.tmpdir(), 'g050-ensayo-'));
try {
  for (const [modo, esperados, oficial] of MODOS) {
    const s = await servidor(modo);
    try {
      const dir = path.join(temporal, modo); fs.mkdirSync(dir);
      const runId = `ENSAYO-G050-20261027-000000-${modo}`;
      const archivo = path.join(dir, 'contexto_operacion.json');
      const referencia = `ENSAYO_LOCAL_${modo}`;
      const v2 = modo === 'v2_corregido' || modo === 'v2_defecto';
      fs.writeFileSync(archivo, JSON.stringify({ grupo: 'G050', version: v2 ? 2 : 1,
        ...(v2 ? { version_anterior: 1, alcance_reevaluacion: 'TC-M04-119 y regresión 118/120' } : {}),
        intento: 1, run_id: runId, operacion: v2 ? 'REEVALUAR' : 'EVALUAR', referencia, casos: CASOS }));
      const c = contextoEjecucion(['--operacion', v2 ? 'reevaluar' : 'evaluar', '--version', v2 ? '2' : '1', '--intento', '1',
        '--run-id', runId, '--autorizacion', referencia, '--contexto', archivo],
      { grupo: 'G050', casos: CASOS, directorio: path.resolve(fileURLToPath(import.meta.url), '../..'),
        modoEnsayo: true });
      const r = await evaluar(c, { ensayo: true, env: { QA_AUTORIZADO: 'SI',
        SIGAB_API_TEST_BASE: s.base, QA_SANDBOX_SECRET: SANDBOX,
        RF71_INTERNAL_KEY: CLAVE, QA_ADMIN_EMAIL: 'admin@example.test',
        QA_ADMIN_PASSWORD: PASSWORD } });
      assert.deepEqual(CASOS.map(x => r.casos[x].estado), esperados,
        `${modo}: ${JSON.stringify({ problemas: r.problemas_tecnicos, motivos: r.casos })}`);
      assert.equal(r.oficial, oficial, modo);
      assert.equal(r.cierre.run.cierre_http, 200);
      assert.equal(fs.readdirSync(dir).filter(x => x.endsWith('.md')).length, 1);
      const guardado = JSON.parse(fs.readFileSync(path.join(dir, 'resultado.json'), 'utf8'));
      assert.deepEqual(guardado.casos, r.casos);
      assert.equal(guardado.run_id, runId);
      const nombreInforme = v2 ? 'TC-M04-G050_reevaluacion_V2.md' : 'TC-M04-G050_resultado.md';
      const md = fs.readFileSync(path.join(dir, nombreInforme), 'utf8');
      assert.equal(md, informe(r));
      assert.equal(contieneMojibake(md), false);
      if (v2) {
        assert.ok(md.includes('Comparación V1 → V2'));
        assert.ok(md.includes(modo === 'v2_corregido'
          ? 'INC-M04-G050-119 CORREGIDA' : 'INC-M04-G050-119 sin corrección acreditada'));
        assert.equal(/matriz/i.test(md.replaceAll('matriz_confusion', '')), false);
      }
      const presentes = new Set(r.evidencias.filter(x => fs.existsSync(path.join(dir, x))));
      assert.equal(clasificarRegistro(CAPACIDADES, r, presentes, c), oficial);
      for (const f of ['resultado.json', nombreInforme, 'preflight.json',
        'newman/newman-G050.json', 'newman/newman-G050.html']) {
        if (fs.existsSync(path.join(dir, f))) {
          const txt = fs.readFileSync(path.join(dir, f), 'utf8');
          for (const secret of [CLAVE, SANDBOX, PASSWORD, 'ensayo-token'])
            assert.ok(!txt.includes(secret), `${modo}: secreto en ${f}`);
        }
      }
      assert.ok(s.peticiones.every(x => x.ruta !== '/test-control/query'));
      assert.equal(s.peticiones.at(-1).metodo, 'DELETE');
      const postsModelo = s.peticiones.filter(x => x.metodo === 'POST' && x.ruta === '/prediccion/modelos').length;
      assert.equal(postsModelo, modo === 'tf_422' ? 7 : modo === 'clave_403' || modo === 'error5xx' ? 1 : 6);
      assert.ok(s.peticiones.length <= 18);
      if (modo === 'tf_como_onnx' || modo === 'tf_422')
        assert.deepEqual(r.incidencias.map(x => x.id), ['INC-M04-G050-119']);
      if (modo === 'v2_defecto') assert.deepEqual(r.incidencias.map(x => x.id),
        ['INC-M04-G050-119']);
      if (modo === 'tf_como_onnx') {
        assert.ok(md.includes('Restricción 2, línea 1873: “Solo se aceptan artefactos en formato ONNX o TensorFlow SavedModel.”'));
        assert.ok(md.includes('GET 200, formato_artefacto ONNX'));
        assert.ok(md.includes('formato_artefacto ONNX en lugar de TENSORFLOW_SAVED_MODEL; hash fiel'));
        assert.ok(!r.incidencias[0].pasos.join(' ').includes('V2b'));
      }
      if (modo === 'tf_422') {
        assert.equal(r.respuestas.v2b.post.http, 201);
        assert.equal(r.respuestas.v2b.get.http, 200);
        assert.notEqual(r.datos.version2b.proceso, r.datos.versiones[1].proceso);
        assert.equal(r.respuestas.v2b.post.hash_artefacto_sha256, r.datos.version2b.hash);
        assert.ok(md.includes('V2b se cre'));
      } else assert.equal(r.respuestas.v2b, null);
      console.log(`OK ${modo}: ${esperados.join('/')} ${oficial ? 'OFICIAL' : 'TÉCNICO'}`);
    } finally { await new Promise(resolve => s.server.close(resolve)); }
  }
  console.log(`OK G050: ${MODOS.length}/${MODOS.length} modos`);
} finally {
  if (!path.resolve(temporal).startsWith(path.resolve(os.tmpdir()) + path.sep)) throw Error('TEMP_FUERA_RAIZ');
  fs.rmSync(temporal, { recursive: true, force: true });
}
