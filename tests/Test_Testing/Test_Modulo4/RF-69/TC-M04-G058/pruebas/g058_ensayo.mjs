import assert from 'node:assert/strict';
import fs from 'node:fs';
import http from 'node:http';
import os from 'node:os';
import path from 'node:path';
import { evaluar, leerEnv } from '../g058.mjs';
import { CASOS, CAPACIDADES, PRESUPUESTO } from '../lib/g058_escenario.mjs';
import { clasificarRegistro } from './registro_qa.mjs';
import { contieneMojibake } from '../lib/seguridad.mjs';

const modos = [
  ['todo_ok', ['APROBADO', 'APROBADO', 'APROBADO'], true],
  ['registro_rechazada_200', ['APROBADO', 'APROBADO', 'APROBADO'], true],
  ['registro_rechazada_201', ['APROBADO', 'APROBADO', 'APROBADO'], true],
  ['rechazada_activable', ['RECHAZADO', 'APROBADO', 'APROBADO'], true],
  ['rechazada_422', ['RECHAZADO', 'APROBADO', 'APROBADO'], true],
  ['rechazada_un_rol_200', ['RECHAZADO', 'APROBADO', 'APROBADO'], true],
  ['deprecada_reactivable', ['APROBADO', 'RECHAZADO', 'APROBADO'], true],
  ['deprecada_422', ['APROBADO', 'RECHAZADO', 'APROBADO'], true],
  ['deprecada_con_evento_intento', ['APROBADO', 'APROBADO', 'APROBADO'], true],
  ['deprecada_sin_evento', ['APROBADO', 'APROBADO', 'APROBADO'], true],
  ['activa_autodeprecada', ['APROBADO', 'APROBADO', 'RECHAZADO'], true],
  ['activa_422', ['APROBADO', 'APROBADO', 'RECHAZADO'], true],
  ['activa_evento_nuevo', ['APROBADO', 'APROBADO', 'RECHAZADO'], true],
  ['activa_alterada_por_157', ['RECHAZADO', 'APROBADO', 'APROBADO'], true],
  ['activar_a_falla', ['APROBADO', 'NO_CONCLUYENTE', 'APROBADO'], false],
  ['registro_a_falla', ['APROBADO', 'NO_CONCLUYENTE', 'APROBADO'], false],
  ['registro_r_falla', ['NO_CONCLUYENTE', 'APROBADO', 'APROBADO'], false],
  ['intento_5xx', ['RECHAZADO', 'APROBADO', 'APROBADO'], true],
  ['env_archivo', ['APROBADO', 'APROBADO', 'APROBADO'], true],
  ['login_lento', ['APROBADO', 'APROBADO', 'APROBADO'], true],
  ['login_sin_red', ['BLOQUEADO', 'BLOQUEADO', 'BLOQUEADO'], false],
  ['clave_403', ['BLOQUEADO', 'BLOQUEADO', 'BLOQUEADO'], false],
  ['error5xx', ['BLOQUEADO', 'BLOQUEADO', 'BLOQUEADO'], false],
  ['sin_respuesta', ['NO_CONCLUYENTE', 'APROBADO', 'APROBADO'], false],
  ['historial_consultado', ['APROBADO', 'APROBADO', 'APROBADO'], true],
  ['heredada', ['APROBADO', 'APROBADO', 'APROBADO'], true],
];
const PASSWORD = 'clave-local-ensayo';
const CLAVE = 'rf71-local-ensayo';
const SANDBOX = 'sandbox-local-ensayo';
const leer = req => new Promise((resolve, reject) => { const chunks = [];
  req.on('data', x => chunks.push(x)); req.on('end', () => resolve(Buffer.concat(chunks)));
  req.on('error', reject); });
const responder = (res, code, obj, run) => {
  res.writeHead(code, { 'Content-Type': 'application/json', ...(run ? { 'X-Test-Run-Id': run } : {}) });
  res.end(JSON.stringify(obj));
};

function servidor(modo) {
  const inicial = modo === 'heredada' ? [{ id_version_modelo: 90,
    tipo_modelo: 'MODELO_ESPECIES_GRANDES', componente: null, estado_version: 'ACTIVO',
    esta_produccion: true }] : [];
  let versiones = structuredClone(inicial);
  let eventos = [];
  let registros = 0, rIntentos = 0, cerrado = false, nSolicitudes = 0;
  const server = http.createServer(async (req, res) => {
    const u = new URL(req.url, 'http://127.0.0.1');
    const run = req.headers['x-test-run-id'];
    nSolicitudes++;
    try {
      if (u.pathname === '/sesiones/' && req.method === 'POST') {
        if (modo === 'login_lento') await new Promise(resolve => setTimeout(resolve, 310));
        await leer(req);
        return responder(res, 200, { token: `token-local-${nSolicitudes}` });
      }
      if (req.method === 'DELETE' && u.pathname.startsWith('/test-control/runs/')) {
        versiones = structuredClone(inicial); eventos = []; cerrado = true;
        return responder(res, 200, { cerrado: true });
      }
      if (u.pathname === '/configuracion/variables-ambientales')
        return responder(res, 200, { total: 1, items: [{ id_variable_ambiental: 7 }] }, run);
      if (u.pathname === '/prediccion/modelos' && req.method === 'POST') {
        await leer(req);
        if (modo === 'clave_403') return responder(res, 403, { code: 'CLAVE_INVALIDA' }, run);
        if (modo === 'error5xx') return responder(res, 500, { code: 'ERROR_TEMPORAL' }, run);
        registros++;
        if (modo === 'registro_a_falla' && registros === 1
          || modo === 'registro_r_falla' && registros === 3)
          return responder(res, 500, { code: 'ERROR_TEMPORAL' }, run);
        const id = 100 + registros;
        const v = { id_version_modelo: id, tipo_modelo: 'MODELO_ESPECIES_GRANDES',
          componente: null, estado_version: registros === 3 ? 'RECHAZADO' : 'APROBADO',
          esta_produccion: false, notas_validacion: null };
        versiones.push(v);
        eventos.push({ tipo_evento: 'VERSION_REGISTRADA', id_referencia: String(id), correlacion_id: `reg-${id}` });
        eventos.push({ tipo_evento: registros === 3 ? 'VERSION_RECHAZADA' : 'VERSION_APROBADA',
          id_referencia: String(id), correlacion_id: `reg-${id}` });
        return responder(res, registros === 3 && modo !== 'registro_rechazada_201' ? 200 : 201, v, run);
      }
      if (u.pathname === '/prediccion/modelos' && req.method === 'GET') {
        let items = [...versiones];
        if (u.searchParams.has('tipo_modelo')) items = items.filter(x => x.tipo_modelo === u.searchParams.get('tipo_modelo'));
        if (u.searchParams.has('estado')) items = items.filter(x => x.estado_version === u.searchParams.get('estado'));
        return responder(res, 200, { total: items.length, items }, run);
      }
      if (u.pathname === '/prediccion/auditoria') {
        const id = u.searchParams.get('id_referencia');
        const items = eventos.filter(x => x.id_referencia === id);
        items.push({ tipo_evento: 'HISTORIAL_CONSULTADO', id_referencia: id,
          correlacion_id: `consulta-${nSolicitudes}` });
        return responder(res, 200, { total: items.length, items }, run);
      }
      const m = u.pathname.match(/^\/prediccion\/modelos\/(\d+)(\/notas|\/activar)?$/);
      if (m) {
        const id = Number(m[1]);
        const v = versiones.find(x => x.id_version_modelo === id);
        if (!v) return responder(res, 404, { code: 'NO_ENCONTRADO' }, run);
        if (!m[2] && req.method === 'GET') return responder(res, 200, v, run);
        if (m[2] === '/notas' && req.method === 'PATCH') {
          const b = JSON.parse((await leer(req)).toString());
          v.notas_validacion = b.notas_validacion;
          return responder(res, 200, v, run);
        }
        if (m[2] === '/activar' && req.method === 'POST') {
          if (id === 101 && modo === 'activar_a_falla')
            return responder(res, 500, { code: 'ERROR_TEMPORAL' }, run);
          if (id === 103) {
            rIntentos++;
            if (modo === 'sin_respuesta' && rIntentos === 1) return;
            if (modo === 'intento_5xx' && rIntentos === 1)
              return responder(res, 500, { code: 'ERROR_TEMPORAL' }, run);
            if (modo === 'rechazada_422') return responder(res, 422, { code: 'VERSION_NO_APROBADA' }, run);
            if (modo === 'rechazada_un_rol_200' && rIntentos === 1)
              return responder(res, 200, v, run);
            if (modo === 'rechazada_activable') {
              const previa = versiones.find(x => x.estado_version === 'ACTIVO');
              if (previa) { previa.estado_version = 'DEPRECADO'; previa.esta_produccion = false; }
              v.estado_version = 'ACTIVO'; v.esta_produccion = true;
              eventos.push({ tipo_evento: 'VERSION_ACTIVADA', id_referencia: '103', correlacion_id: 'mal-r' });
              return responder(res, 200, v, run);
            }
            if (modo === 'activa_alterada_por_157' && rIntentos === 2) {
              const b = versiones.find(x => x.id_version_modelo === 102);
              b.estado_version = 'DEPRECADO'; b.esta_produccion = false;
              eventos.push({ tipo_evento: 'VERSION_DEPRECADA', id_referencia: '102', correlacion_id: 'mal-r' });
            }
            return responder(res, 409, { code: 'TRANSICION_ESTADO_INVALIDA' }, run);
          }
          if (id === 101 && v.estado_version === 'DEPRECADO') {
            if (modo === 'deprecada_422') return responder(res, 422, { code: 'TRANSICION_ESTADO_INVALIDA' }, run);
            if (modo === 'deprecada_con_evento_intento') eventos.push({ tipo_evento: 'INTENTO_ACTIVACION_INVALIDA',
              id_referencia: '101', correlacion_id: 'intento-a' });
            if (modo === 'deprecada_reactivable') {
              const previa = versiones.find(x => x.estado_version === 'ACTIVO');
              if (previa) { previa.estado_version = 'DEPRECADO'; previa.esta_produccion = false; }
              v.estado_version = 'ACTIVO'; v.esta_produccion = true;
              eventos.push({ tipo_evento: 'VERSION_ACTIVADA', id_referencia: '101', correlacion_id: 'mal-a' });
              return responder(res, 200, v, run);
            }
            return responder(res, 409, { code: 'TRANSICION_ESTADO_INVALIDA' }, run);
          }
          if (id === 102 && v.estado_version === 'ACTIVO') {
            if (modo === 'activa_422') return responder(res, 422, { code: 'VERSION_NO_APROBADA' }, run);
            if (modo === 'activa_evento_nuevo') eventos.push({ tipo_evento: 'VERSION_ACTIVADA',
              id_referencia: '102', correlacion_id: 'duplicado-b' });
            if (modo === 'activa_autodeprecada') {
              v.estado_version = 'DEPRECADO'; v.esta_produccion = false;
              eventos.push({ tipo_evento: 'VERSION_DEPRECADA', id_referencia: '102', correlacion_id: 'mal-b' });
            }
            return responder(res, 409, { code: 'VERSION_NO_APROBADA' }, run);
          }
          if (v.estado_version !== 'APROBADO') return responder(res, 409, { code: 'VERSION_NO_APROBADA' }, run);
          const previa = versiones.find(x => x.id_version_modelo !== id && x.estado_version === 'ACTIVO');
          if (previa) {
            previa.estado_version = 'DEPRECADO'; previa.esta_produccion = false;
            eventos.push({ tipo_evento: 'VERSION_DEPRECADA', id_referencia: String(previa.id_version_modelo),
              correlacion_id: `act-${id}` });
          }
          v.estado_version = 'ACTIVO'; v.esta_produccion = true;
          eventos.push({ tipo_evento: 'VERSION_ACTIVADA', id_referencia: String(id), correlacion_id: `act-${id}` });
          return responder(res, 200, v, run);
        }
      }
      responder(res, 404, {}, run);
    } catch { if (!res.headersSent) responder(res, 500, { code: 'MOCK_ERROR' }, run); }
  });
  return { server, get cerrado() { return cerrado; } };
}

const temporal = fs.mkdtempSync(path.join(os.tmpdir(), 'g058-ensayo-'));
try {
  for (const [modo, esperados, oficial] of modos) {
    const s = servidor(modo);
    await new Promise(resolve => s.server.listen(0, '127.0.0.1', resolve));
    try {
      const puerto = s.server.address().port;
      if (modo === 'login_sin_red') await new Promise(resolve => s.server.close(resolve));
      const runId = `ENSAYO-G058-20261028-000000-${modo}`;
      const directorio = path.join(temporal, modo); fs.mkdirSync(directorio);
      const c = { version: 1, intento: modo === 'registro_rechazada_200' ? 2 : 1,
        operacion: modo === 'registro_rechazada_200' ? 'reintentar' : 'evaluar', runId,
        referencia: 'ensayo local', directorio, ensayo: true };
      const entorno = { QA_AUTORIZADO: 'SI', SIGAB_API_TEST_BASE: `http://127.0.0.1:${puerto}`,
        QA_SANDBOX_SECRET: SANDBOX, RF71_INTERNAL_KEY: CLAVE,
        QA_ADMIN_EMAIL: 'admin@example.test', QA_ADMIN_PASSWORD: PASSWORD,
        QA_VETERINARIO_EMAIL: 'vet@example.test', QA_COMMON_PASSWORD: PASSWORD };
      if (modo === 'env_archivo') {
        const archivo = path.join(directorio, '.env.qa');
        fs.writeFileSync(archivo, Object.entries(entorno).filter(([k]) => k !== 'QA_AUTORIZADO')
          .map(([k, v]) => `${k}=${v}`).join('\n'), 'utf8');
        Object.assign(entorno, leerEnv({ QA_AUTORIZADO: 'SI' }, archivo));
        fs.unlinkSync(archivo);
      }
      const r = await evaluar(c, { env: entorno, ensayo: true });
      const estados = CASOS.map(x => r.casos[x].estado);
      assert.deepEqual(estados, esperados, `${modo}: ${JSON.stringify(r.casos)}`);
      assert.equal(r.oficial, oficial, `${modo} oficial`);
      assert.ok(r.incidencias.every(x => ['ALTA', 'MEDIA', 'BAJA', 'CRÍTICA'].includes(x.severidad)
        && x.equipo_inicial === 'Desarrollo' && x.certeza === 'CONFIRMADA'), `${modo} incidencias`);
      if (modo.endsWith('_422')) assert.ok(r.incidencias.every(x => x.severidad === 'MEDIA'));
      if (oficial) assert.equal(r.solicitudes.length, r.presupuesto_esperado, `${modo} presupuesto exacto aplicable`);
      if (['todo_ok', 'registro_rechazada_200', 'registro_rechazada_201'].includes(modo)) {
        assert.equal(r.solicitudes.length, PRESUPUESTO.total, 'presupuesto exacto en camino completo');
        assert.deepEqual(r.solicitudes.filter(x => x.metodo === 'POST' && x.ruta.endsWith('/activar')
          && ['ACTIVO', 'DEPRECADO', 'RECHAZADO'].includes(x.estado_antes))
          .map(x => x.estado_antes), ['ACTIVO', 'DEPRECADO', 'RECHAZADO', 'RECHAZADO']);
        assert.equal(r.solicitudes.find(x => x.metodo === 'POST' && x.dato === 'R').http,
          modo === 'registro_rechazada_201' ? 201 : 200, `${modo} HTTP registro R`);
        assert.deepEqual(r.solicitudes.filter(x => x.rol === 'Administrador poscierre')
          .map(x => x.http), [404, 404, 404, 200], `${modo} rollback sobre A/B/R y listado`);
        assert.equal(r.cierre.rollback.verificado, true, `${modo} rollback acreditado`);
        assert.equal(r.solicitudes.filter(x => x.ruta === '/prediccion/modelos/103/activar').length,
          2, `${modo} ambos intentos de 157`);
        assert.equal(r.observaciones.some(x => x.includes('Registro R RECHAZADO respondió HTTP 201')),
          modo === 'registro_rechazada_201', `${modo} observación HTTP 201`);
      }
      const presentes = new Set(r.evidencias.filter(x => fs.existsSync(path.join(directorio, x))));
      assert.equal(clasificarRegistro(CAPACIDADES, r, presentes, c), oficial, `${modo} registro QA`);
      const persistido = JSON.parse(fs.readFileSync(path.join(directorio, 'resultado.json'), 'utf8'));
      assert.deepEqual(CASOS.map(x => persistido.casos[x].estado), estados);
      assert.equal(persistido.run_id, runId);
      assert.equal(clasificarRegistro(CAPACIDADES, persistido, presentes, c), oficial,
        `${modo} resultado.json en registro QA`);
      const md = fs.readFileSync(path.join(directorio, 'TC-M04-G058_resultado.md'), 'utf8');
      const decision = estados.includes('RECHAZADO') ? 'RECHAZADO'
        : estados.every(x => x === 'APROBADO') ? 'APROBADO'
          : estados.includes('BLOQUEADO') ? 'BLOQUEADO' : 'NO_CONCLUYENTE';
      assert.ok(md.startsWith(`# TC-M04-G058 — ${decision}\n`), `${modo} título`);
      assert.ok(md.includes('**RUN oficial: no.**'), `${modo} no TEST`);
      assert.ok(md.includes('**Qué falta: '), `${modo} acción`);
      if (modo === 'registro_rechazada_200') {
        assert.ok(md.includes('### Intento 1 — RUN-G058-V1-20261028-143302'));
        assert.ok(md.includes('rollback NO_VERIFICADO'));
      }
      if (modo === 'registro_rechazada_201')
        assert.ok(md.includes('Registro R RECHAZADO respondió HTTP 201'),
          'HTTP 201 de R queda como observación en el informe');
      const seccion = md.match(/## Detalle por caso\n\n([\s\S]*?)\n\n## Esperado y observado/);
      assert.ok(seccion, `${modo} detalle`);
      const apartados = [...seccion[1].matchAll(/### (TC-M04-\d{3}) — (APROBADO|RECHAZADO|BLOQUEADO|NO_CONCLUYENTE)\n\n([\s\S]*?)(?=\n\n### |$)/g)];
      assert.equal(apartados.length, CASOS.length, `${modo} casos`);
      apartados.forEach((a, i) => {
        assert.equal(a[1], CASOS[i]); assert.equal(a[2], estados[i]);
        const lineas = a[3].trim().split('\n');
        assert.equal(lineas.length, 4, `${modo} cuatro líneas`);
        ['Qué se hizo', 'Qué se esperaba', 'Qué se observó', `Por qué ${estados[i]}`]
          .forEach((rotulo, j) => assert.ok(lineas[j].startsWith(`**${rotulo}:** `)));
        assert.ok(lineas[1].includes('RF-69') && lineas[1].includes('líneas '));
        assert.ok(!lineas[3].includes('Las respuestas y estados posteriores cumplieron el criterio.'),
          `${modo} motivo específico por caso`);
        if (estados[i] === 'APROBADO')
          assert.ok(lineas[3].includes('HTTP 409') && lineas[3].includes('versión'),
            `${modo} motivo con respuesta y versión`);
      });
      assert.ok(!contieneMojibake(md), `${modo} codificación`);
      for (const valor of [PASSWORD, CLAVE, SANDBOX, 'admin@example.test', 'vet@example.test']) {
        assert.ok(!md.includes(valor), `${modo} secreto en informe`);
        assert.ok(!fs.readFileSync(path.join(directorio, 'resultado.json'), 'utf8').includes(valor), `${modo} secreto en JSON`);
        for (const evidencia of r.evidencias.filter(x => x.startsWith('newman/')))
          assert.ok(!fs.readFileSync(path.join(directorio, evidencia), 'utf8').includes(valor),
            `${modo} secreto en Newman`);
      }
      if (modo === 'deprecada_con_evento_intento') assert.ok(md.includes('INTENTO_ACTIVACION_INVALIDA'));
      if (modo === 'deprecada_sin_evento') assert.ok(md.includes('sin requisito normativo localizado'));
      if (modo === 'login_lento') assert.ok(r.solicitudes.slice(0, 2).every(x => x.duracion_ms >= 310));
      if (modo === 'login_sin_red') {
        assert.equal(r.solicitudes.length, 1);
        assert.equal(r.solicitudes[0].tipo_fallo, 'ECONNREFUSED');
      }
      if (modo === 'activar_a_falla') {
        assert.equal(r.solicitudes.filter(x => x.ruta === '/prediccion/modelos/101/activar').length, 1);
        assert.ok(!r.problemas_tecnicos.some(x => x.includes('Presupuesto')));
      }
      if (modo === 'registro_a_falla')
        assert.equal(r.solicitudes.filter(x => x.ruta === '/prediccion/modelos/101/activar').length, 0);
      if (['registro_a_falla', 'registro_r_falla'].includes(modo))
        assert.equal(r.cierre.rollback.verificado, false, `${modo} falta ID para acreditar tres 404`);
      if (modo === 'deprecada_reactivable')
        assert.equal(r.incidencias.length, 1, 'reactivación de A: una incidencia de 158');
      if (['rechazada_activable', 'activa_alterada_por_157', 'deprecada_reactivable'].includes(modo))
        assert.deepEqual(r.problemas_tecnicos, [], `${modo} sin falla técnica por defecto funcional`);
      if (modo === 'activa_autodeprecada') {
        assert.ok(r.observaciones.some(x => x.includes('no había versión ACTIVO')));
        assert.equal(r.solicitudes.length, PRESUPUESTO.total - 2);
      }
      console.log(`${modo}: ${estados.join('/')}; ${oficial ? 'OFICIAL' : 'TÉCNICO/NO_CONCLUYENTE'}`);
    } finally {
      if (s.server.listening) { s.server.closeAllConnections(); await new Promise(resolve => s.server.close(resolve)); }
    }
  }
  console.log(`OK G058: ${modos.length}/${modos.length} modos; presupuesto ${PRESUPUESTO.total}; registro QA fiel`);
} finally { fs.rmSync(temporal, { recursive: true, force: true }); }
