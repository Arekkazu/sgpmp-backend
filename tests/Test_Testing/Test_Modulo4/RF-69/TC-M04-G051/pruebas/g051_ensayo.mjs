#!/usr/bin/env node
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import http from 'node:http';
import { fileURLToPath } from 'node:url';
import { evaluar, informe, leerEnv } from '../g051.mjs';
import { CASOS, CAPACIDADES } from '../lib/g051_escenario.mjs';
import { contextoEjecucion } from '../lib/contrato_ejecutor.mjs';
import { contieneMojibake } from '../lib/seguridad.mjs';
import { clasificarRegistro } from './registro_qa.mjs';

const MODOS = [
  ['todo_ok', null, 'APROBADO', true],
  ['fecha_futura_500', 1, 'RECHAZADO', true],
  ['fecha_futura_aceptada', 1, 'RECHAZADO', true],
  ['variable_inexistente_aceptada', 0, 'RECHAZADO', true],
  ['campo_no_identificado', 3, 'RECHAZADO', true],
  ['rechazo_crea_version', 6, 'RECHAZADO', true],
  ['limite_rechazado', 4, 'RECHAZADO', true],
  ['clave_403', null, 'BLOQUEADO', false],
  ['error5xx', null, 'BLOQUEADO', false],
  ['sin_respuesta', null, 'NO_CONCLUYENTE', false]
];
const CLAVE = 'ENSAYO_RF71_SECRETO_G051_123456';
const SANDBOX = 'ENSAYO_SANDBOX_G051_123456';
const PASSWORD = 'ENSAYO_PASSWORD_G051_123456';
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
    if (req.method === 'GET' && url.pathname === '/prediccion/modelos') {
      assert.equal(url.searchParams.get('tipo_modelo'), 'MODELO_ESPECIES_GRANDES');
      return responder(res, 200, { total: versiones.length, items: [...versiones].reverse() }, run);
    }
    if (req.method === 'GET' && url.pathname.startsWith('/prediccion/modelos/')) {
      const v = versiones.find(x => x.id_version_modelo === Number(url.pathname.split('/').at(-1)));
      return responder(res, v ? 200 : 404, v ?? { error_code: 'NO_ENCONTRADO' }, run);
    }
    if (req.method === 'POST' && url.pathname === '/prediccion/modelos') {
      const chunks = []; req.on('data', x => chunks.push(x)); req.on('end', () => {
        const n = peticiones.filter(x => x.metodo === 'POST' && x.ruta === '/prediccion/modelos').length;
        if (modo === 'sin_respuesta' && n === 1) { req.socket.destroy(); return; }
        if (modo === 'clave_403') return responder(res, 403, { error_code: 'REGISTRO_INTERNO_REQUERIDO' }, run);
        if (modo === 'error5xx') return responder(res, 500, { error_code: 'ERROR_MODELO' }, run);
        assert.equal(req.headers['x-rf71-internal-key'], CLAVE);
        assert.equal(req.headers['x-sandbox-secret'], SANDBOX);
        const raw = Buffer.concat(chunks).toString('latin1');
        assert.ok(raw.includes('name="archivo_modelo"'));
        const tipo = campo(raw, 'tipo_modelo');
        const hash = campo(raw, 'hash_artefacto_sha256');
        const dataset = campo(raw, 'dataset_entrenamiento_hash');
        const metricas = JSON.parse(campo(raw, 'metricas_validacion'));
        const variables = JSON.parse(campo(raw, 'compatibilidad_variables'));
        const fecha = campo(raw, 'fecha_entrenamiento');
        const proceso = campo(raw, 'id_proceso_rf71');
        const error = (code, field, message, httpCode = 422) => responder(res, httpCode,
          { error_code: code, message, fields: field ? [{ field, message }] : [] }, run);
        const crear = (httpCode = 201) => {
          const v = { id_version_modelo: 101 + versiones.length, tipo_modelo: tipo,
            id_proceso_rf71: proceso, estado_version: metricas.f1_score_global === 0 ? 'RECHAZADO' : 'APROBADO',
            fecha_entrenamiento: fecha, f1_score: metricas.f1_score_global,
            hash_artefacto_sha256: hash, dataset_entrenamiento_hash: dataset };
          versiones.push(v); responder(res, httpCode, v, run);
        };
        if (hash === null || dataset === null) {
          if (modo === 'rechazo_crea_version' && hash === null && dataset === null)
            versiones.push({ id_version_modelo: 101 + versiones.length, id_proceso_rf71: proceso,
              tipo_modelo: 'MODELO_ESPECIES_GRANDES' });
          if (modo === 'fecha_futura_500') return responder(res, 400, {
            error_code: 'VAL_ENTRADA', message: 'Errores de validacion en la solicitud',
            fields: ['hash_artefacto_sha256', 'dataset_entrenamiento_hash']
              .filter(f => f === 'hash_artefacto_sha256' ? hash === null : dataset === null)
              .map(field => ({ field, message: 'Este campo es obligatorio.' })) }, run);
          return error('VAL_ENTRADA', null, 'Errores de validacion en la solicitud', 422);
        }
        if (!/^[a-f0-9]{64}$/i.test(hash)) return error('HASH_SHA256_INVALIDO', 'hash_artefacto_sha256',
          'hash_artefacto_sha256 debe ser un hash SHA-256 de 64 caracteres hexadecimales.');
        if (!/^[a-f0-9]{64}$/i.test(dataset)) return error('HASH_SHA256_INVALIDO', 'dataset_entrenamiento_hash',
          'dataset_entrenamiento_hash debe ser un hash SHA-256 de 64 caracteres hexadecimales.');
        if (tipo === '' && modo === 'fecha_futura_500')
          return error('VAL_ENTRADA', 'tipo_modelo', 'Errores de validacion en la solicitud', 400);
        if (tipo !== 'MODELO_ESPECIES_GRANDES') return error('TIPO_MODELO_INVALIDO', 'tipo_modelo',
          'tipo_modelo debe ser uno de: MODELO_ESPECIES_GRANDES, MODELO_ESPECIES_MEDIANAS, MODELO_RIESGO_CONTAGIO, MODELO_AVES, MODELO_PORCINOS, MODELO_ACUICULTURA.');
        for (const f of ['f1_score_global', 'recall_clase_riesgo_alto', 'matriz_confusion'])
          if (!(f in metricas)) return error('METRICAS_INCOMPLETAS', 'metricas_validacion',
            modo === 'campo_no_identificado' ? 'Los metadatos están incompletos.' : `Falta ${f}.`);
        if (metricas.f1_score_global < 0 || metricas.f1_score_global > 1)
          return error('METRICA_FUERA_DE_RANGO', 'metricas_validacion',
            'f1_score_global debe estar en el rango [0.0, 1.0].');
        if (variables.includes(8) && modo !== 'variable_inexistente_aceptada')
          return error('VARIABLE_I3P1_NO_ENCONTRADA', 'compatibilidad_variables',
            'La variable no existe en el catálogo I3P-1.');
        if (new Date(fecha).getTime() > Date.now() && modo === 'fecha_futura_500')
          return error('ERROR_INTERNO', null, 'Ocurrió un error interno.', 500);
        if (new Date(fecha).getTime() > Date.now() && modo !== 'fecha_futura_aceptada')
          return error('FECHA_FUTURA', 'fecha_entrenamiento', 'La fecha no puede ser futura.');
        if (metricas.f1_score_global === 1 && modo === 'limite_rechazado')
          return error('METRICA_FUERA_DE_RANGO', 'metricas_validacion',
            'f1_score_global debe estar en el rango [0.0, 1.0].');
        crear(metricas.f1_score_global === 0 ? 200 : 201);
      }); return;
    }
    responder(res, 404, { error_code: 'NO_ENCONTRADO' }, run);
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  return { server, peticiones, base: `http://127.0.0.1:${server.address().port}` };
}

const temporal = fs.mkdtempSync(path.join(os.tmpdir(), 'g051-ensayo-'));
try {
  for (const [modo, indice, esperado, oficial] of MODOS) {
    const s = await servidor(modo);
    try {
      const dir = path.join(temporal, modo); fs.mkdirSync(dir);
      const runId = `ENSAYO-G051-20261027-000000-${modo}`;
      const archivo = path.join(dir, 'contexto_operacion.json');
      const referencia = `ENSAYO_LOCAL_${modo}`;
      fs.writeFileSync(archivo, JSON.stringify({ grupo: 'G051', version: 1, intento: 1,
        run_id: runId, operacion: 'EVALUAR', referencia, casos: CASOS }));
      const c = contextoEjecucion(['--operacion', 'evaluar', '--version', '1', '--intento', '1',
        '--run-id', runId, '--autorizacion', referencia, '--contexto', archivo],
      { grupo: 'G051', casos: CASOS, directorio: path.resolve(fileURLToPath(import.meta.url), '../..'),
        modoEnsayo: true });
      const variables = { SIGAB_API_TEST_BASE: s.base, QA_SANDBOX_SECRET: SANDBOX,
        RF71_INTERNAL_KEY: CLAVE, QA_ADMIN_EMAIL: 'admin@example.test',
        QA_ADMIN_PASSWORD: PASSWORD };
      let env = { QA_AUTORIZADO: 'SI', ...variables };
      if (modo === 'todo_ok') {
        const archivoEnv = path.join(dir, '.env.qa');
        fs.writeFileSync(archivoEnv, Object.entries(variables)
          .map(([clave, valor]) => `${clave}=${valor}`).join('\n'), 'utf8');
        env = leerEnv({ QA_AUTORIZADO: 'SI' }, archivoEnv);
        assert.deepEqual(Object.fromEntries(Object.keys(variables).map(k => [k, env[k]])), variables);
      }
      const r = await evaluar(c, { ensayo: true, env });
      const estados = CASOS.map(x => r.casos[x].estado);
      if (indice !== null) assert.equal(estados[indice], esperado, `${modo}: ${JSON.stringify(r.problemas_tecnicos)}`);
      if (modo === 'todo_ok') assert.deepEqual(estados, Array(7).fill('APROBADO'), JSON.stringify(r.problemas_tecnicos));
      if (modo === 'fecha_futura_500') {
        assert.deepEqual(estados, ['APROBADO', 'RECHAZADO', 'RECHAZADO',
          ...Array(3).fill('APROBADO'), 'RECHAZADO']);
        assert.equal(r.incidencias.length, 2);
        assert.equal(r.incidencias[0].titulo,
          'Una fecha de entrenamiento futura produce error interno 500 en lugar de rechazo 422');
        assert.equal(r.incidencias[0].severidad, 'MEDIA');
        assert.match(r.incidencias[0].obtenido, /mañana \([^)]*\): HTTP 500, código ERROR_INTERNO/);
        assert.equal(r.incidencias[1].id, 'INC-M04-G051-VAL400');
        assert.deepEqual(r.incidencias[1].casos_afectados, ['TC-M04-123', 'TC-M04-127']);
        assert.equal(r.incidencias[1].severidad, 'BAJA');
        assert.equal(r.incidencias[1].obtenido.match(/HTTP 400/g)?.length, 4);
        assert.equal(r.conteo.delta, 4);
        assert.equal(s.peticiones.filter(x => x.metodo === 'POST' && x.ruta === '/prediccion/modelos').length, 23);
      }
      if (modo === 'clave_403' || modo === 'error5xx') assert.deepEqual(estados, Array(7).fill('BLOQUEADO'));
      if (modo === 'sin_respuesta') assert.ok(estados.includes('NO_CONCLUYENTE'));
      assert.equal(r.oficial, oficial, `${modo}: ${JSON.stringify(r.problemas_tecnicos)}`);
      assert.equal(r.cierre.run.cierre_http, 200);
      assert.equal(fs.readdirSync(dir).filter(x => x.endsWith('.md')).length, 1);
      const guardado = JSON.parse(fs.readFileSync(path.join(dir, 'resultado.json'), 'utf8'));
      assert.deepEqual(guardado.casos, r.casos);
      assert.equal(guardado.run_id, runId);
      const md = fs.readFileSync(path.join(dir, 'TC-M04-G051_resultado.md'), 'utf8');
      assert.equal(md, informe(r));
      assert.equal(contieneMojibake(md), false);
      const presentes = new Set(r.evidencias.filter(x => fs.existsSync(path.join(dir, x))));
      assert.equal(clasificarRegistro(CAPACIDADES, r, presentes, c), oficial);
      for (const f of ['resultado.json', 'TC-M04-G051_resultado.md', 'preflight.json',
        'newman/newman-G051.json', 'newman/newman-G051.html']) {
        if (fs.existsSync(path.join(dir, f))) {
          const txt = fs.readFileSync(path.join(dir, f), 'utf8');
          for (const secret of [CLAVE, SANDBOX, PASSWORD, 'ensayo-token'])
            assert.ok(!txt.includes(secret), `${modo}: secreto en ${f}`);
        }
      }
      assert.ok(s.peticiones.every(x => x.ruta !== '/test-control/query'));
      assert.equal(s.peticiones.at(-1).metodo, 'DELETE');
      assert.ok(s.peticiones.length <= 33);
      if (modo === 'todo_ok') {
        assert.equal(s.peticiones.filter(x => x.metodo === 'POST' && x.ruta === '/prediccion/modelos').length, 23);
        assert.equal(s.peticiones.length, 32);
        assert.equal(r.conteo.aceptados, 4);
        assert.equal(r.conteo.delta, 4);
      }
      if (modo === 'clave_403' || modo === 'error5xx')
        assert.equal(s.peticiones.filter(x => x.metodo === 'POST' && x.ruta === '/prediccion/modelos').length,
          modo === 'clave_403' ? 1 : 3);
      console.log(`OK ${modo}: ${estados.join('/')} ${oficial ? 'OFICIAL' : 'TÉCNICO'}`);
    } finally { await new Promise(resolve => s.server.close(resolve)); }
  }
  console.log('OK G051: 10/10 modos; resultado.json e informe coherentes; secretos ausentes; registro QA fiel');
} finally {
  if (!path.resolve(temporal).startsWith(path.resolve(os.tmpdir()) + path.sep)) throw Error('TEMP_FUERA_RAIZ');
  fs.rmSync(temporal, { recursive: true, force: true });
}
