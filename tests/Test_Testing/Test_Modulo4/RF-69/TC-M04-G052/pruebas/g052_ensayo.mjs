#!/usr/bin/env node
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import http from 'node:http';
import { fileURLToPath } from 'node:url';
import { evaluar, leerEnv } from '../g052.mjs';
import { CASOS, CAPACIDADES, PRESUPUESTO } from '../lib/g052_escenario.mjs';
import { contextoEjecucion } from '../lib/contrato_ejecutor.mjs';
import { contieneMojibake } from '../lib/seguridad.mjs';
import { clasificarRegistro } from './registro_qa.mjs';

const MODOS = [
  ['todo_ok', null, 'APROBADO', true],
  ['frontera_inclusiva_rechazada', 3, 'RECHAZADO', true],
  ['umbral_simultaneo_no_exigido', 2, 'RECHAZADO', true],
  ['detalle_generico', 4, 'RECHAZADO', true],
  ['estado_alterable', 5, 'RECHAZADO', true],
  ['rechazo_201', 1, 'RECHAZADO', true],
  ['sin_historial', 0, 'RECHAZADO', true],
  ['error5xx_130', 1, 'RECHAZADO', true],
  ['env_archivo', null, 'APROBADO', true],
  ['clave_403', null, 'BLOQUEADO', false],
  ['error5xx', null, 'BLOQUEADO', false],
  ['sin_respuesta', null, 'NO_CONCLUYENTE', false],
  ['post_lento_creado', 1, 'APROBADO', true],
  ['post_lento_ausente', 1, 'NO_CONCLUYENTE', false]
];
const CLAVE = 'ENSAYO_RF71_G052_SECRETO_123456';
const SANDBOX = 'ENSAYO_SANDBOX_G052_SECRETO_123456';
const PASSWORD = 'ENSAYO_PASSWORD_G052_SECRETO_123456';
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
      const chunks = []; req.on('data', x => chunks.push(x)); req.on('end', () => {
        const body = JSON.parse(Buffer.concat(chunks).toString());
        assert.equal(body.contrasena, PASSWORD);
        responder(res, 200, { token: body.correo_electronico.startsWith('admin') ? 'token-admin' : 'token-vet' });
      }); return;
    }
    if (req.method === 'DELETE' && url.pathname.startsWith('/test-control/runs/'))
      return responder(res, 200, { status: 'Rollback exitoso' });
    if (req.method === 'GET' && url.pathname === '/configuracion/variables-ambientales')
      return responder(res, 200, { total: 1, items: [{ id_variable_ambiental: 7 }] }, run);
    if (req.method === 'GET' && url.pathname === '/prediccion/auditoria') {
      const v = versiones.find(x => String(x.id_version_modelo) === url.searchParams.get('id_referencia'));
      const items = modo === 'sin_historial' ? [] : ['VERSION_REGISTRADA', 'VERSION_APROBADA'].map(tipo => ({
        tipo_evento: tipo, tipo_actor: 'SISTEMA', id_usuario: null,
        id_sistema: v?.id_proceso_rf71, id_referencia: String(v?.id_version_modelo) }));
      return responder(res, 200, { total: items.length, items }, run);
    }
    if (req.method === 'GET' && url.pathname === '/prediccion/modelos') {
      assert.equal(url.searchParams.get('tipo_modelo'), 'MODELO_ESPECIES_GRANDES');
      assert.equal(url.searchParams.get('limit'), '100');
      assert.equal(url.searchParams.get('offset'), '0');
      return responder(res, 200, { total: versiones.length, items: versiones }, run);
    }
    if (req.method === 'GET' && url.pathname.startsWith('/prediccion/modelos/')) {
      const v = versiones.find(x => x.id_version_modelo === Number(url.pathname.split('/').at(-1)));
      return responder(res, v ? 200 : 404, v ?? { error_code: 'NO_ENCONTRADO' }, run);
    }
    if (req.method === 'PATCH' && url.pathname.endsWith('/notas')) {
      const id = Number(url.pathname.split('/').at(-2));
      const v = versiones.find(x => x.id_version_modelo === id);
      const chunks = []; req.on('data', x => chunks.push(x)); req.on('end', () => {
        if (modo === 'estado_alterable' && v && id === 101) {
          v.estado_version = JSON.parse(Buffer.concat(chunks).toString()).estado_version;
          responder(res, 200, v, run);
        } else responder(res, 422, { error_code: 'VAL_ENTRADA', message: 'notas_validacion requerido' }, run);
      }); return;
    }
    if (['PUT', 'PATCH', 'DELETE'].includes(req.method) && url.pathname.startsWith('/prediccion/modelos/')) {
      req.resume(); req.on('end', () => responder(res, 405, { error_code: 'METHOD_NOT_ALLOWED' }, run)); return;
    }
    if (req.method === 'POST' && url.pathname === '/prediccion/modelos') {
      const chunks = []; req.on('data', x => chunks.push(x)); req.on('end', () => {
        const n = peticiones.filter(x => x.metodo === 'POST' && x.ruta === '/prediccion/modelos').length;
        if (modo === 'sin_respuesta' && n === 1) { req.socket.destroy(); return; }
        if (modo === 'clave_403') return responder(res, 403, { error_code: 'REGISTRO_INTERNO_REQUERIDO' }, run);
        if (modo === 'error5xx') return responder(res, 500, { error_code: 'ERROR_MODELO' }, run);
        if (modo === 'error5xx_130' && n === 2) return responder(res, 500, { error_code: 'ERROR_MODELO' }, run);
        assert.equal(req.headers['x-rf71-internal-key'], CLAVE);
        assert.equal(req.headers['x-sandbox-secret'], SANDBOX);
        const raw = Buffer.concat(chunks).toString('latin1');
        assert.ok(raw.includes('name="archivo_modelo"'));
        const metricas = JSON.parse(campo(raw, 'metricas_validacion'));
        const f1 = metricas.f1_score_global, recall = metricas.recall_clase_riesgo_alto;
        const proceso = campo(raw, 'id_proceso_rf71');
        const cumple = f1 >= 0.80 && recall >= 0.85;
        let estado = cumple ? 'APROBADO' : 'RECHAZADO';
        if (modo === 'frontera_inclusiva_rechazada' && n === 4) estado = 'RECHAZADO';
        if (modo === 'umbral_simultaneo_no_exigido' && n === 3) estado = 'APROBADO';
        const defectos = [ ...(f1 < 0.80 ? [`f1_score_global=${f1} < umbral requerido 0.80`] : []),
          ...(recall < 0.85 ? [`recall_clase_riesgo_alto=${recall} < umbral requerido 0.85`] : []) ];
        const detalle = estado === 'APROBADO' ? null : modo === 'detalle_generico' && n === 5 ? 'Umbrales no alcanzados'
          : defectos.join('; ') || 'Umbrales no alcanzados';
        const v = { id_version_modelo: 100 + n, tipo_modelo: campo(raw, 'tipo_modelo'),
          id_proceso_rf71: proceso, estado_version: estado, detalle_validacion: detalle,
          f1_score: f1, recall_clase_riesgo_alto: recall };
        if (n === 2 && ['post_lento_creado', 'post_lento_ausente'].includes(modo)) {
          if (modo === 'post_lento_creado') versiones.push(v);
          return;
        }
        versiones.push(v);
        responder(res, estado === 'RECHAZADO' && !(modo === 'rechazo_201' && n === 2) ? 200 : 201, v, run);
      }); return;
    }
    responder(res, 404, { error_code: 'NO_ENCONTRADO' }, run);
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  return { server, peticiones, base: `http://127.0.0.1:${server.address().port}` };
}

const temporal = fs.mkdtempSync(path.join(os.tmpdir(), 'g052-ensayo-'));
try {
  for (const [modo, indice, esperado, oficial] of MODOS) {
    const s = await servidor(modo);
    try {
      const dir = path.join(temporal, modo); fs.mkdirSync(dir);
      const runId = `ENSAYO-G052-20261028-000000-${modo}`;
      const archivo = path.join(dir, 'contexto_operacion.json');
      const referencia = `ENSAYO_LOCAL_${modo}`;
      fs.writeFileSync(archivo, JSON.stringify({ grupo: 'G052', version: 1, intento: 1,
        run_id: runId, operacion: 'EVALUAR', referencia, casos: CASOS }));
      const c = contextoEjecucion(['--operacion', 'evaluar', '--version', '1', '--intento', '1',
        '--run-id', runId, '--autorizacion', referencia, '--contexto', archivo],
      { grupo: 'G052', casos: CASOS, directorio: path.resolve(fileURLToPath(import.meta.url), '../..'),
        modoEnsayo: true });
      const variables = { SIGAB_API_TEST_BASE: s.base, QA_SANDBOX_SECRET: SANDBOX,
        RF71_INTERNAL_KEY: CLAVE, QA_ADMIN_EMAIL: 'admin@example.test', QA_ADMIN_PASSWORD: PASSWORD,
        QA_VETERINARIO_EMAIL: 'vet@example.test', QA_COMMON_PASSWORD: PASSWORD };
      let env = { QA_AUTORIZADO: 'SI', ...variables };
      if (modo === 'env_archivo' || modo === 'todo_ok') {
        const archivoEnv = path.join(dir, '.env.qa');
        fs.writeFileSync(archivoEnv, Object.entries(variables)
          .map(([clave, valor]) => `${clave}=${valor}`).join('\n'), 'utf8');
        env = leerEnv({ QA_AUTORIZADO: 'SI' }, archivoEnv);
        assert.deepEqual(Object.fromEntries(Object.keys(variables).map(k => [k, env[k]])), variables);
      }
      const r = await evaluar(c, { ensayo: true, env });
      const estados = CASOS.map(x => r.casos[x].estado);
      if (indice !== null) {
        assert.equal(estados[indice], esperado, `${modo}: ${JSON.stringify(r.problemas_tecnicos)}`);
        if (oficial && esperado === 'RECHAZADO') assert.equal(estados.filter(x => x === 'RECHAZADO').length, 1,
          `${modo}: discrepancia afectó más de un caso: ${JSON.stringify(estados)}`);
      }
      if (modo === 'todo_ok' || modo === 'env_archivo') assert.deepEqual(estados, Array(6).fill('APROBADO'));
      if (modo === 'post_lento_creado') {
        assert.equal(r.solicitudes[1].post.http, null);
        assert.equal(r.solicitudes[1].post.recuperado, true);
        assert.equal(r.solicitudes[1].get.http, 200);
        assert.ok(r.observaciones.some(x => /130: POST sin respuesta; versión localizada/.test(x)));
      }
      if (modo === 'post_lento_ausente') {
        assert.equal(r.solicitudes[1].post.recuperado, false);
        assert.equal(r.casos[CASOS[1]].estado, 'NO_CONCLUYENTE');
        assert.equal(r.casos[CASOS[4]].estado, 'NO_CONCLUYENTE');
        assert.equal(r.detalle_133.sin_evidencia[0].dato, '130');
      }
      if (modo === 'umbral_simultaneo_no_exigido' || modo === 'error5xx_130') {
        const caso = modo === 'error5xx_130' ? CASOS[1] : CASOS[2];
        const dato = modo === 'error5xx_130' ? '130' : '131';
        assert.deepEqual(estados, CASOS.map(x => x === caso ? 'RECHAZADO' : 'APROBADO'));
        assert.equal(r.detalle_133.evaluadas.length, 4);
        assert.equal(r.detalle_133.excluidas.length, 1);
        assert.equal(r.detalle_133.excluidas[0].dato, dato);
        assert.equal(r.detalle_133.excluidas[0].caso, caso);
        assert.ok(r.incidencias.some(x => x.id === r.detalle_133.excluidas[0].incidencia));
      }
      if (modo === 'sin_respuesta') {
        assert.equal(r.casos[CASOS[0]].estado, 'NO_CONCLUYENTE');
        assert.equal(r.casos[CASOS[3]].estado, 'APROBADO');
        assert.equal(r.casos[CASOS[4]].estado, 'APROBADO');
      }
      if (r.casos[CASOS[3]].estado === 'APROBADO')
        for (const i of [3, 4, 5, 6]) assert.equal(r.solicitudes[i].get?.http, 200);
      if (r.casos[CASOS[4]].estado === 'APROBADO')
        for (const i of [1, 2, 4, 5, 6].filter(i =>
          r.detalle_133.evaluadas.some(x => x.dato === (i === 1 ? '130' : i === 2 ? '131' : `132-${'abcd'[i - 3]}`)))) {
          assert.equal(r.solicitudes[i].get?.http, 200);
          assert.equal(r.solicitudes[i].get?.estado, 'RECHAZADO');
        }
      for (const solicitud of r.solicitudes) if (solicitud.post.duracion_ms !== null)
        assert.ok(Number.isInteger(solicitud.post.duracion_ms));
      if (!['clave_403', 'error5xx'].includes(modo))
        assert.ok(r.solicitudes.every(x => Number.isInteger(x.post.duracion_ms)));
      if (!oficial) assert.ok(estados.includes(esperado), `${modo}: ${JSON.stringify(estados)}`);
      assert.equal(r.oficial, oficial, `${modo}: oficial=${r.oficial}; ${JSON.stringify(r.problemas_tecnicos)}`);
      assert.equal(r.cierre.run.cierre_http, 200);
      const presentes = new Set(fs.readdirSync(dir).flatMap(x => x === 'newman'
        ? fs.readdirSync(path.join(dir, x)).map(y => `newman/${y}`) : [x]));
      if (oficial) assert.equal(clasificarRegistro(CAPACIDADES, r, presentes,
        { runId, version: 1 }), true, `${modo}: registro QA no oficial`);
      const texto = fs.readFileSync(path.join(dir, 'TC-M04-G052_resultado.md'), 'utf8');
      const json = fs.readFileSync(path.join(dir, 'resultado.json'), 'utf8');
      const detalle = texto.split('## Detalle por caso\n\n')[1]?.split('\n\n## Identificación')[0];
      assert.ok(detalle, modo + ': falta Detalle por caso');
      const apartados = detalle.split(/\n\n(?=### TC-M04-)/);
      assert.equal(apartados.length, CASOS.length, modo + ': número de apartados');
      for (const [i, apartado] of apartados.entries()) {
        const lineas = apartado.trim().split('\n');
        assert.equal(lineas.length, 5, modo + ': cuatro líneas en ' + CASOS[i]);
        assert.equal(lineas[0], '### ' + CASOS[i] + ' — ' + r.casos[CASOS[i]].estado);
        for (const [j, etiqueta] of ['Qué se hizo:', 'Qué se esperaba:', 'Qué se observó:',
          'Por qué ' + r.casos[CASOS[i]].estado + ':'].entries())
          assert.ok(lineas[j + 1].startsWith('**' + etiqueta + '** '), modo + ': ' + etiqueta);
      }
      assert.ok(texto.includes('TC-M04-133: detalle de versiones rechazadas'));
      for (const x of r.detalle_133.evaluadas) assert.ok(texto.includes(`| ${x.dato} | ${x.caso} | ${x.version} |`));
      for (const x of r.detalle_133.excluidas)
        assert.ok(texto.includes(`no evaluable en 133 por ${x.incidencia} de ${x.caso}`));
      assert.ok(texto.includes('Duración POST (ms)'));
      assert.equal(JSON.parse(json).solicitudes.length, 7);
      assert.equal(contieneMojibake(texto + json), false);
      for (const secreto of [CLAVE, SANDBOX, PASSWORD, 'admin@example.test', 'vet@example.test']) {
        assert.equal(texto.includes(secreto) || json.includes(secreto), false);
        if (presentes.has('newman/newman-G052.json'))
          assert.equal(fs.readFileSync(path.join(dir, 'newman/newman-G052.json'), 'utf8').includes(secreto), false);
      }
      assert.equal(fs.readdirSync(dir).filter(x => x.endsWith('.md')).length, 1);
      if (modo === 'todo_ok') assert.equal(s.peticiones.length, PRESUPUESTO.total);
      console.log(`OK ${modo}: ${estados.join(',')} ${r.oficial ? 'OFICIAL_LOCAL' : 'TÉCNICO'}`);
    } finally { await new Promise(resolve => s.server.close(resolve)); }
  }
  console.log(`OK G052: ${MODOS.length}/${MODOS.length} modos; presupuesto ${PRESUPUESTO.total} solicitudes; sin APROBADO parcial`);
} finally {
  if (!path.resolve(temporal).startsWith(path.resolve(os.tmpdir()) + path.sep)) throw Error('TEMP_FUERA_RAIZ');
  fs.rmSync(temporal, { recursive: true, force: true });
}
