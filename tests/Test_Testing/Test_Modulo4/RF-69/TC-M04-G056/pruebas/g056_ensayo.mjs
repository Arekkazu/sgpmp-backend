import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import http from 'node:http';
import { fileURLToPath } from 'node:url';
import { evaluar, leerEnv } from '../g056.mjs';
import { contextoEjecucion } from '../lib/contrato_ejecutor.mjs';
import { CASOS, PRESUPUESTO, CAPACIDADES } from '../lib/g056_escenario.mjs';
import { clasificarRegistro } from './registro_qa.mjs';
import { contieneMojibake } from '../lib/seguridad.mjs';

const MODOS = [
  ['todo_ok', null, null, true], ['notas_cambian_estado', 0, 'RECHAZADO', true],
  ['veterinario_sin_permiso_notas', 0, 'RECHAZADO', true,
    ['RECHAZADO', 'APROBADO', 'APROBADO', 'APROBADO']],
  ['administrador_sin_permiso_notas', 0, 'RECHAZADO', true],
  ['sin_notas_ambos', 0, 'RECHAZADO', false,
    ['RECHAZADO', 'APROBADO', 'NO_CONCLUYENTE', 'APROBADO']],
  ['rechazada_activable', 1, 'RECHAZADO', true], ['activar_422', 1, 'RECHAZADO', true],
  ['historial_modificable', 1, 'RECHAZADO', true],
  ['aprobada_cambia_tras_nueva', 2, 'RECHAZADO', true],
  ['filtro_no_acota', 3, 'RECHAZADO', true], ['env_archivo', null, null, true],
  ['clave_403', null, 'BLOQUEADO', false], ['error5xx', null, 'BLOQUEADO', false],
  ['sin_respuesta', null, 'NO_CONCLUYENTE', false],
  ['historial_con_consultas', 1, 'APROBADO', true],
  ['datos_heredados_en_listado', 3, 'APROBADO', true],
  ['transicion_alterada', 1, 'RECHAZADO', true]
];
const PASSWORD = 'clave-ensayo-solo-loopback';
const CLAVE = 'clave-interna-ensayo-loopback';
const SANDBOX = 'sandbox-ensayo-loopback';
const METRICAS = { f1_score: 0.91, recall_clase_riesgo_alto: 0.93,
  precision_modelo: 0.92, accuracy: 0.94, roc_auc_score: 0.95,
  recall_por_clase: { riesgo_alto: 0.93 }, matriz_confusion: [[9, 1], [1, 9]] };
function responder(res, code, obj, run) {
  res.writeHead(code, { 'Content-Type': 'application/json; charset=utf-8',
    ...(run ? { 'X-Test-Run-Id': run } : {}) }); res.end(JSON.stringify(obj));
}
function campo(raw, nombre) {
  const re = new RegExp(`name="${nombre}"[^\\r\\n]*\\r\\n\\r\\n([^\\r\\n]*)`);
  return raw.match(re)?.[1] ?? null;
}
function servidor(modo) {
  const versiones = [], peticiones = [], consultasAuditoria = new Map();
  const server = http.createServer((req, res) => {
    const u = new URL(req.url, 'http://127.0.0.1');
    const run = req.headers['x-test-run-id'];
    const rol = req.headers.authorization === 'Bearer token-vet' ? 'Veterinario' : 'Administrador';
    peticiones.push(`${req.method} ${u.pathname}`);
    if (req.method === 'POST' && u.pathname === '/sesiones/') {
      const chunks = []; req.on('data', x => chunks.push(x)); req.on('end', () => {
        const x = JSON.parse(Buffer.concat(chunks).toString()); assert.equal(x.contrasena, PASSWORD);
        responder(res, 200, { token: x.correo_electronico.startsWith('vet') ? 'token-vet' : 'token-admin' });
      }); return;
    }
    if (req.method === 'DELETE' && u.pathname.startsWith('/test-control/runs/'))
      return responder(res, 200, { status: 'cerrado' });
    if (req.method === 'GET' && u.pathname === '/configuracion/variables-ambientales')
      return responder(res, 200, { total: 1, items: [{ id_variable_ambiental: 7 }] }, run);
    if (req.method === 'POST' && u.pathname === '/prediccion/modelos') {
      const chunks = []; req.on('data', x => chunks.push(x)); req.on('end', () => {
        if (modo === 'sin_respuesta') { req.socket.destroy(); return; }
        if (modo === 'clave_403') return responder(res, 403, { error_code: 'CLAVE_INVALIDA' }, run);
        if (modo === 'error5xx') return responder(res, 500, { error_code: 'ERROR' }, run);
        assert.equal(req.headers['x-rf71-internal-key'], CLAVE);
        assert.equal(req.headers['x-sandbox-secret'], SANDBOX);
        const raw = Buffer.concat(chunks).toString('latin1');
        assert.ok(raw.includes('name="archivo_modelo"'));
        const m = JSON.parse(campo(raw, 'metricas_validacion'));
        const n = versiones.length + 1, rechazado = m.f1_score_global < 0.80;
        const v = { id_version_modelo: 100 + n, tipo_modelo: campo(raw, 'tipo_modelo'),
          estado_version: rechazado ? 'RECHAZADO' : 'APROBADO', esta_produccion: false,
          notas_validacion: null, id_proceso_rf71: campo(raw, 'id_proceso_rf71'),
          ...METRICAS, f1_score: m.f1_score_global, recall_clase_riesgo_alto: m.recall_clase_riesgo_alto };
        versiones.push(v); responder(res, rechazado ? 200 : 201, v, run);
      }); return;
    }
    if (u.pathname === '/prediccion/auditoria') {
      if (req.method !== 'GET') return responder(res,
        modo === 'historial_modificable' && req.method === 'PUT' && rol === 'Administrador' ? 200 : 405, {}, run);
      const id = u.searchParams.get('id_referencia');
      const consultas = (consultasAuditoria.get(id) ?? 0) + 1;
      consultasAuditoria.set(id, consultas);
      const items = [{ id_evento: `a-${id}`, tipo_evento: 'VERSION_REGISTRADA', id_referencia: id,
        estado_nuevo: modo === 'transicion_alterada' && consultas > 1 ? 'APROBADO' : 'RECHAZADO' }];
      if (modo === 'historial_con_consultas') for (let i = 1; i <= consultas; i++)
        items.push({ id_evento: `consulta-${id}-${i}`, tipo_evento: 'HISTORIAL_CONSULTADO', id_referencia: id });
      return responder(res, 200, { total: items.length, items }, run);
    }
    if (u.pathname === '/prediccion/modelos' && req.method === 'GET') {
      let items = [...versiones];
      if (modo === 'datos_heredados_en_listado' && !u.searchParams.has('tipo_modelo') && !u.searchParams.has('estado')) {
        items.push({ id_version_modelo: 56, tipo_modelo: 'MODELO_ACUICULTURA', paradigma: 'POBLACIONAL',
          estado_version: 'APROBADO', metricas_poblacionales: { calibracion_completada: true },
          f1_score: null, recall_clase_riesgo_alto: null });
        items.push({ id_version_modelo: 57, tipo_modelo: 'MODELO_RIESGO_CONTAGIO', paradigma: 'META',
          estado_version: 'ACTIVO', f1_score: null, recall_clase_riesgo_alto: null });
        for (let id = 8; id <= 31; id++) items.push({ id_version_modelo: id,
          tipo_modelo: null, paradigma: null, estado_version: 'EN_VALIDACION',
          f1_score: null, recall_clase_riesgo_alto: null });
      }
      if (u.searchParams.has('tipo_modelo')) items = items.filter(x => x.tipo_modelo === u.searchParams.get('tipo_modelo'));
      if (u.searchParams.has('estado')) items = items.filter(x => x.estado_version === u.searchParams.get('estado'));
      if (modo === 'filtro_no_acota' && u.searchParams.get('estado') === 'RECHAZADO') items.push(versiones[0]);
      return responder(res, 200, { total: items.length, items }, run);
    }
    const m = u.pathname.match(/^\/prediccion\/modelos\/(\d+)(\/notas|\/activar)?$/);
    if (m) {
      const v = versiones.find(x => x.id_version_modelo === Number(m[1]));
      if (!v) return responder(res, 404, { error_code: 'NO_ENCONTRADO' }, run);
      if (m[2] === '/notas' && req.method === 'PATCH') {
        const chunks = []; req.on('data', x => chunks.push(x)); req.on('end', () => {
          if (v.notas_validacion != null) return responder(res, 409, { error_code: 'NOTAS_INMUTABLES' }, run);
          if ((modo === 'veterinario_sin_permiso_notas' || modo === 'sin_notas_ambos') && rol === 'Veterinario')
            return responder(res, 403, { error_code: 'SIN_PERMISO' }, run);
          if ((modo === 'administrador_sin_permiso_notas' || modo === 'sin_notas_ambos') && rol === 'Administrador')
            return responder(res, 403, { error_code: 'SIN_PERMISO' }, run);
          const x = JSON.parse(Buffer.concat(chunks).toString()); v.notas_validacion = x.notas_validacion;
          responder(res, 200, v, run);
        }); return;
      }
      if (m[2] === '/activar' && req.method === 'POST') return responder(res,
        modo === 'rechazada_activable' ? 200 : modo === 'activar_422' ? 422 : 409, v, run);
      if (!m[2] && req.method === 'GET') {
        const x = { ...v };
        if (modo === 'notas_cambian_estado' && Number(m[1]) === 101
          && peticiones.filter(p => p === 'GET /prediccion/modelos/101').length === 1)
          x.estado_version = 'ACTIVO';
        if (modo === 'aprobada_cambia_tras_nueva' && Number(m[1]) === 101 && versiones.length === 4)
          x.estado_version = 'DEPRECADO';
        return responder(res, 200, x, run);
      }
      if (!m[2] && ['PUT', 'PATCH'].includes(req.method)) return responder(res, 405, {}, run);
    }
    responder(res, 404, {}, run);
  });
  return { server, peticiones, versiones };
}
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'g056-ensayo-'));
try {
  for (const [modo, indice, esperado, oficial, estadosEsperados] of MODOS) {
    const s = servidor(modo);
    await new Promise(resolve => s.server.listen(0, '127.0.0.1', resolve));
    try {
      const dir = path.join(tmp, modo); fs.mkdirSync(dir);
      const runId = `ENSAYO-G056-20261028-000000-${modo}`;
      const ref = `ENSAYO_LOCAL_${modo}`;
      const p = path.join(dir, 'contexto_operacion.json');
      fs.writeFileSync(p, JSON.stringify({ grupo: 'G056', version: 1, intento: 1,
        run_id: runId, operacion: 'EVALUAR', referencia: ref, casos: CASOS }));
      const c = contextoEjecucion(['--operacion', 'evaluar', '--version', '1', '--intento', '1',
        '--run-id', runId, '--autorizacion', ref, '--contexto', p],
      { grupo: 'G056', casos: CASOS, directorio: path.resolve(fileURLToPath(import.meta.url), '../..'), modoEnsayo: true });
      const variables = { SIGAB_API_TEST_BASE: `http://127.0.0.1:${s.server.address().port}`,
        QA_SANDBOX_SECRET: SANDBOX, RF71_INTERNAL_KEY: CLAVE,
        QA_ADMIN_EMAIL: 'admin@example.test', QA_ADMIN_PASSWORD: PASSWORD,
        QA_VETERINARIO_EMAIL: 'vet@example.test', QA_COMMON_PASSWORD: PASSWORD };
      let env = { QA_AUTORIZADO: 'SI', ...variables };
      if (['todo_ok', 'env_archivo'].includes(modo)) {
        const archivo = path.join(dir, '.env.qa');
        fs.writeFileSync(archivo, Object.entries(variables).map(([k, v]) => `${k}=${v}`).join('\n'));
        env = leerEnv({ QA_AUTORIZADO: 'SI' }, archivo);
      }
      const r = await evaluar(c, { env, ensayo: true });
      const estados = CASOS.map(x => r.casos[x].estado);
      if (indice != null) { assert.equal(estados[indice], esperado, modo);
        assert.equal(estados.filter(x => x === 'RECHAZADO').length, esperado === 'RECHAZADO' ? 1 : 0, modo); }
      else assert.deepEqual(estados, Array(4).fill(esperado ?? 'APROBADO'), `${modo}: ${r.problemas_tecnicos.join(',')}`);
      if (estadosEsperados) assert.deepEqual(estados, estadosEsperados, modo);
      if (modo === 'veterinario_sin_permiso_notas') {
        assert.ok(r.observaciones.includes('TC-M04-148: versión usada V1b; Administrador'), modo);
        assert.deepEqual(r.problemas_tecnicos, [], modo);
      }
      if (modo === 'sin_notas_ambos') {
        assert.ok(r.observaciones.includes('TC-M04-148: versión usada ninguna; sin nota registrada en V1 ni V1b'), modo);
        assert.deepEqual(r.problemas_tecnicos, [], modo);
      }
      if (modo === 'datos_heredados_en_listado') {
        assert.ok(r.observaciones.some(x => x.includes('versión 57') && x.includes('métricas almacenadas incompletas')), modo);
        assert.ok(r.observaciones.some(x => x.includes('versión 8') && x.includes('tipo_modelo nulo')), modo);
        assert.ok(r.observaciones.some(x => x.includes('versión 31') && x.includes('tipo_modelo nulo')), modo);
      }
      if (modo === 'historial_con_consultas') assert.equal(r.casos['TC-M04-147'].estado, 'APROBADO', modo);
      if (modo === 'transicion_alterada') assert.ok(r.casos['TC-M04-147'].motivo.includes('transiciones'), modo);
      assert.equal(r.oficial, oficial, modo);
      assert.equal(r.cierre.run.cierre_http, 200, modo);
      assert.equal(r.cierre.rollback.verificado, true, modo);
      const md = fs.readFileSync(path.join(dir, 'TC-M04-G056_resultado.md'), 'utf8');
      const json = fs.readFileSync(path.join(dir, 'resultado.json'), 'utf8');
      assert.ok(md.startsWith(`# TC-M04-G056 — ${esperado ?? 'APROBADO'}\n`), `${modo}: título`);
      assert.ok(md.includes('## Decisión del caso\n') && md.includes('| Caso | Comprobación | Decisión | Motivo breve |'), `${modo}: bloque de decisión`);
      if (modo === 'veterinario_sin_permiso_notas') assert.ok(md.includes('versión usada V1b; Administrador'), modo);
      if (modo === 'sin_notas_ambos') assert.ok(md.includes('versión usada ninguna; sin nota registrada en V1 ni V1b'), modo);
      assert.equal(contieneMojibake(md + json), false, modo);
      assert.equal(JSON.parse(json).run_id, runId, modo);
      const presentes = new Set(fs.readdirSync(dir, { recursive: true }).filter(x => fs.statSync(path.join(dir, x)).isFile())
        .map(x => x.replaceAll('\\', '/')));
      assert.equal(clasificarRegistro(CAPACIDADES, JSON.parse(json), presentes, c), oficial, `${modo}: registro QA fiel`);
      assert.equal(JSON.parse(json).cypress.total_pruebas, 0, modo);
      assert.ok(JSON.parse(json).comprobaciones.every(x => x.tipo === 'ASSERT' && x.motivo && x.evidencia === 'resultado.json'), modo);
      for (const secreto of [PASSWORD, CLAVE, SANDBOX, ...[variables.QA_ADMIN_EMAIL, variables.QA_VETERINARIO_EMAIL]]) {
        assert.equal(md.includes(secreto) || json.includes(secreto), false, modo);
        for (const f of fs.readdirSync(path.join(dir, 'newman'), { recursive: true })) {
          const full = path.join(dir, 'newman', f);
          if (fs.statSync(full).isFile()) assert.equal(fs.readFileSync(full, 'utf8').includes(secreto), false, modo);
        }
      }
      assert.equal(fs.readdirSync(dir).filter(x => x.endsWith('.md')).length, 1, modo);
      if (modo === 'todo_ok') {
        assert.equal(s.peticiones.length, PRESUPUESTO.total, modo);
        assert.equal(s.peticiones.filter(x => x === 'POST /prediccion/modelos').length, 4, modo);
        assert.equal(s.peticiones.filter(x => x === 'PATCH /prediccion/modelos/101/notas').length, 1, modo);
        assert.equal(s.peticiones.filter(x => x === 'PATCH /prediccion/modelos/102/notas').length, 1, modo);
        assert.equal(s.peticiones.filter(x => x === 'PATCH /prediccion/modelos/103/notas').length, 0, modo);
      }
      console.log(`OK ${modo}: ${estados.join(',')} ${r.oficial ? 'OFICIAL_LOCAL' : 'TÉCNICO'}`);
    } finally { await new Promise(resolve => s.server.close(resolve)); }
  }
  console.log(`OK G056: ${MODOS.length}/${MODOS.length} modos; presupuesto ${PRESUPUESTO.total} solicitudes; registro QA fiel`);
} finally {
  if (!path.resolve(tmp).startsWith(path.resolve(os.tmpdir()) + path.sep)) throw Error('TEMP_FUERA_RAIZ');
  fs.rmSync(tmp, { recursive: true, force: true });
}
