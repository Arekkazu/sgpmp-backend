import assert from 'node:assert/strict';
import fs from 'node:fs';
import http from 'node:http';
import os from 'node:os';
import path from 'node:path';
import { evaluar, leerEnv } from '../g059.mjs';
import { CASOS, CAPACIDADES, PRESUPUESTO } from '../lib/g059_escenario.mjs';
import { clasificarRegistro } from './registro_qa.mjs';
import { contieneMojibake } from '../lib/seguridad.mjs';

const A = ['APROBADO', 'APROBADO', 'APROBADO', 'APROBADO', 'APROBADO'];
const cambiar = (i, valor = 'RECHAZADO') => A.map((x, j) => j === i ? valor : x);
const modos = [
  ['todo_ok', A, true], ['historial_consultado', A, true], ['sin_evento_intento', A, true],
  ['campo_extra_rechazado_422', A, true], ['reenvio_crea_version_nueva', A, true],
  ['reenvio_rechazado_409', A, true], ['env_archivo', A, true], ['login_lento', A, true],
  ['directa_2xx_sin_cambio', A, true], ['put_2xx_sin_cambio', A, true],
  ['aprobada_cambia_por_put', cambiar(0), true], ['aprobada_cambia_por_patch', cambiar(0), true],
  ['activa_cambia_por_patch', cambiar(1), true], ['activa_duplicada', cambiar(1), true],
  ['deprecada_reactivable', cambiar(2), true], ['deprecada_cambia_por_put', cambiar(2), true],
  ['rechazada_reactivable', cambiar(3), true], ['rechazada_cambia_por_patch', cambiar(3), true],
  ['reenvio_reevalua_r', cambiar(3), true], ['reenvio_5xx', cambiar(3), true],
  ['deprecacion_directa_existe', cambiar(4), true], ['deprecacion_sin_activar_otra', cambiar(4), true],
  ['campo_extra_cambia_estado', cambiar(0), true],
  ['activar_deprecado_422', cambiar(2), true], ['activar_rechazado_422', cambiar(3), true],
  ['ruta_aprobada_5xx', cambiar(0), true], ['ruta_activa_5xx', cambiar(1), true],
  ['activar_v1_falla', ['APROBADO', 'NO_CONCLUYENTE', 'NO_CONCLUYENTE', 'APROBADO', 'NO_CONCLUYENTE'], false],
  ['activar_v2_falla', ['APROBADO', 'APROBADO', 'NO_CONCLUYENTE', 'APROBADO', 'NO_CONCLUYENTE'], false],
  ['registro_r_falla', ['APROBADO', 'APROBADO', 'APROBADO', 'NO_CONCLUYENTE', 'APROBADO'], false],
  ['login_sin_red', CASOS.map(() => 'BLOQUEADO'), false],
  ['clave_403', CASOS.map(() => 'BLOQUEADO'), false],
  ['error5xx', CASOS.map(() => 'BLOQUEADO'), false],
  ['sin_respuesta', ['APROBADO', 'APROBADO', 'APROBADO', 'NO_CONCLUYENTE', 'APROBADO'], false]
];
const PASSWORD = 'clave-local-ensayo', CLAVE = 'rf71-local-ensayo', SANDBOX = 'sandbox-local-ensayo';
const leer = req => new Promise((resolve, reject) => { const chunks = [];
  req.on('data', x => chunks.push(x)); req.on('end', () => resolve(Buffer.concat(chunks)));
  req.on('error', reject); });
const responder = (res, code, obj, run) => {
  res.writeHead(code, { 'Content-Type': 'application/json', ...(run ? { 'X-Test-Run-Id': run } : {}) });
  res.end(JSON.stringify(obj));
};
function servidor(modo) {
  let versiones = [], eventos = [], registros = 0, cerrado = false, n = 0, extraV2 = false;
  let repararDeprecacion = false;
  let yaAlterado = false;
  const evento = (tipo_evento, id, correlacion_id) => eventos.push({ tipo_evento,
    id_referencia: String(id), correlacion_id });
  const server = http.createServer(async (req, res) => {
    const u = new URL(req.url, 'http://127.0.0.1'), run = req.headers['x-test-run-id'];
    n++;
    try {
      if (u.pathname === '/sesiones/' && req.method === 'POST') {
        if (modo === 'login_lento') await new Promise(resolve => setTimeout(resolve, 320));
        await leer(req); return responder(res, 200, { token: `token-local-${n}` });
      }
      if (req.method === 'DELETE' && u.pathname.startsWith('/test-control/runs/')) {
        versiones = []; eventos = []; extraV2 = false; cerrado = true;
        return responder(res, 200, { cerrado: true });
      }
      if (u.pathname === '/configuracion/variables-ambientales')
        return responder(res, 200, { total: 1, items: [{ id_variable_ambiental: 7 }] }, run);
      if (u.pathname === '/prediccion/modelos' && req.method === 'POST') {
        await leer(req); registros++;
        if (modo === 'clave_403') return responder(res, 403, { code: 'CLAVE_INVALIDA' }, run);
        if (modo === 'error5xx' || modo === 'registro_r_falla' && registros === 4)
          return responder(res, 500, { code: 'ERROR_TEMPORAL' }, run);
        if (registros === 5) {
          if (modo === 'reenvio_5xx') return responder(res, 500, { code: 'ERROR_TEMPORAL' }, run);
          if (modo === 'reenvio_rechazado_409') return responder(res, 409, { code: 'DUPLICADO' }, run);
          if (modo === 'reenvio_reevalua_r') {
            const r = versiones.find(v => v.id_version_modelo === 104);
            r.estado_version = 'APROBADO'; r.f1_score = 0.91; r.detalle_validacion = 'reevaluado';
            evento('VERSION_APROBADA', 104, 'mal-r');
            return responder(res, 201, r, run);
          }
          if (modo !== 'reenvio_crea_version_nueva') return responder(res, 409, { code: 'DUPLICADO' }, run);
        }
        const id = 100 + registros, rechazada = registros === 4;
        const v = { id_version_modelo: id, tipo_modelo: 'MODELO_ESPECIES_GRANDES', componente: null,
          estado_version: rechazada ? 'RECHAZADO' : 'APROBADO', esta_produccion: false,
          notas_validacion: null, f1_score: rechazada ? 0.72 : 0.91,
          recall_clase_riesgo_alto: 0.95, detalle_validacion: rechazada ? 'umbral F1' : 'válido' };
        versiones.push(v); evento('VERSION_REGISTRADA', id, `reg-${id}`);
        evento(rechazada ? 'VERSION_RECHAZADA' : 'VERSION_APROBADA', id, `reg-${id}`);
        return responder(res, rechazada ? 200 : 201, v, run);
      }
      if (u.pathname === '/prediccion/modelos' && req.method === 'GET') {
        let items = [...versiones];
        if (u.searchParams.has('estado')) items = items.filter(x => x.estado_version === u.searchParams.get('estado'));
        if (modo === 'activa_duplicada' && extraV2 && u.searchParams.get('estado') === 'ACTIVO')
          items.push({ id_version_modelo: 999, estado_version: 'ACTIVO', tipo_modelo: 'MODELO_ESPECIES_GRANDES' });
        if (modo === 'deprecacion_sin_activar_otra' && repararDeprecacion
          && u.searchParams.get('estado') === 'ACTIVO') {
          responder(res, 200, { total: items.length, items }, run);
          const v1 = versiones.find(x => x.id_version_modelo === 101);
          v1.estado_version = 'DEPRECADO'; v1.esta_produccion = false;
          repararDeprecacion = false;
          return;
        }
        return responder(res, 200, { total: items.length, items }, run);
      }
      if (u.pathname === '/prediccion/auditoria') {
        const id = u.searchParams.get('id_referencia');
        const items = eventos.filter(x => x.id_referencia === id);
        items.push({ tipo_evento: 'HISTORIAL_CONSULTADO', id_referencia: id,
          correlacion_id: `consulta-${n}` });
        return responder(res, 200, { total: items.length, items }, run);
      }
      const m = u.pathname.match(/^\/prediccion\/modelos\/(\d+)(\/notas|\/activar|\/deprecar|\/estado)?$/);
      if (!m) return responder(res, 404, { code: 'NO_ENCONTRADO' }, run);
      const id = Number(m[1]), v = versiones.find(x => x.id_version_modelo === id);
      if (!v) return responder(res, 404, { code: 'NO_ENCONTRADO' }, run);
      if (!m[2] && req.method === 'GET') return responder(res, 200, v, run);
      if (m[2] === '/notas' && req.method === 'PATCH') {
        const b = JSON.parse((await leer(req)).toString());
        if (modo === 'campo_extra_rechazado_422' && b.estado_version)
          return responder(res, 422, { code: 'EXTRA_FORBIDDEN' }, run);
        if (modo === 'campo_extra_cambia_estado' && id === 103 && b.estado_version) {
          v.estado_version = 'RECHAZADO'; yaAlterado = true;
        }
        if (id === 102 && v.estado_version === 'ACTIVO') extraV2 = true;
        if (v.notas_validacion) return responder(res, 409, { code: 'NOTAS_INMUTABLES' }, run);
        v.notas_validacion = b.notas_validacion;
        return responder(res, 200, v, run);
      }
      if (m[2] === '/deprecar' && req.method === 'POST') {
        if (modo === 'deprecacion_directa_existe') {
          v.estado_version = 'DEPRECADO'; v.esta_produccion = false;
          evento('VERSION_DEPRECADA', id, 'mal-directo');
          return responder(res, 200, v, run);
        }
        if (modo === 'directa_2xx_sin_cambio') return responder(res, 200, v, run);
        return responder(res, 404, { code: 'NO_ENCONTRADO' }, run);
      }
      if (m[2] === '/estado' && req.method === 'PATCH') {
        await leer(req); return responder(res, 404, { code: 'NO_ENCONTRADO' }, run);
      }
      if (!m[2] && ['PUT', 'PATCH'].includes(req.method)) {
        const b = JSON.parse((await leer(req)).toString());
        const mutar = {
          aprobada_cambia_por_put: id === 103 && req.method === 'PUT',
          aprobada_cambia_por_patch: id === 103 && req.method === 'PATCH',
          activa_cambia_por_patch: id === 102 && req.method === 'PATCH',
          deprecada_cambia_por_put: id === 101 && req.method === 'PUT' && v.estado_version === 'DEPRECADO',
          rechazada_cambia_por_patch: id === 104 && req.method === 'PATCH'
        }[modo];
        if (mutar && !yaAlterado) {
          yaAlterado = true; v.estado_version = b.estado_version;
          v.esta_produccion = b.estado_version === 'ACTIVO';
          evento('VERSION_CAMBIADA', id, 'mal-put');
          return responder(res, 200, v, run);
        }
        if (modo === 'ruta_aprobada_5xx' && id === 103 && !yaAlterado ||
          modo === 'ruta_activa_5xx' && id === 102 && !yaAlterado) {
          yaAlterado = true; return responder(res, 500, { code: 'ERROR_TEMPORAL' }, run);
        }
        if (modo === 'put_2xx_sin_cambio' && id === 103 && req.method === 'PUT')
          return responder(res, 200, v, run);
        return responder(res, 405, { code: 'METHOD_NOT_ALLOWED' }, run);
      }
      if (m[2] === '/activar' && req.method === 'POST') {
        if (id === 101 && v.estado_version === 'APROBADO' && modo === 'activar_v1_falla'
          || id === 102 && v.estado_version === 'APROBADO' && modo === 'activar_v2_falla')
          return responder(res, 500, { code: 'ERROR_TEMPORAL' }, run);
        if (v.estado_version === 'DEPRECADO') {
          if (modo === 'activar_deprecado_422') return responder(res, 422, { code: 'TRANSICION_ESTADO_INVALIDA' }, run);
          if (modo === 'deprecada_reactivable') {
            v.estado_version = 'ACTIVO'; v.esta_produccion = true;
            evento('VERSION_ACTIVADA', id, 'mal-reactivada');
            return responder(res, 200, v, run);
          }
          return responder(res, 409, { code: 'TRANSICION_ESTADO_INVALIDA' }, run);
        }
        if (v.estado_version === 'RECHAZADO') {
          if (modo === 'sin_respuesta') return;
          if (modo === 'activar_rechazado_422') return responder(res, 422, { code: 'TRANSICION_ESTADO_INVALIDA' }, run);
          if (modo === 'rechazada_reactivable') {
            v.estado_version = 'ACTIVO'; v.esta_produccion = true;
            evento('VERSION_ACTIVADA', id, 'mal-r'); return responder(res, 200, v, run);
          }
          return responder(res, 409, { code: 'TRANSICION_ESTADO_INVALIDA' }, run);
        }
        if (v.estado_version === 'ACTIVO')
          return responder(res, modo === 'activar_activo_422' ? 422 : 409,
            { code: 'VERSION_NO_APROBADA' }, run);
        const previa = versiones.find(x => x.id_version_modelo !== id && x.estado_version === 'ACTIVO');
        if (previa && modo !== 'deprecacion_sin_activar_otra') {
          previa.estado_version = 'DEPRECADO'; previa.esta_produccion = false;
          evento('VERSION_DEPRECADA', previa.id_version_modelo, `act-${id}`);
        }
        v.estado_version = 'ACTIVO'; v.esta_produccion = true;
        if (id === 102 && modo === 'deprecacion_sin_activar_otra') repararDeprecacion = true;
        evento('VERSION_ACTIVADA', id, `act-${id}`);
        return responder(res, 200, v, run);
      }
      responder(res, 404, { code: 'NO_ENCONTRADO' }, run);
    } catch { if (!res.headersSent) responder(res, 500, { code: 'MOCK_ERROR' }, run); }
  });
  return { server, get cerrado() { return cerrado; } };
}

const temporal = fs.mkdtempSync(path.join(os.tmpdir(), 'g059-ensayo-'));
try {
  for (const [modo, esperados, oficial] of modos.filter(x => !process.env.G059_MODO || x[0] === process.env.G059_MODO)) {
    const s = servidor(modo);
    await new Promise(resolve => s.server.listen(0, '127.0.0.1', resolve));
    try {
      const puerto = s.server.address().port;
      if (modo === 'login_sin_red') await new Promise(resolve => s.server.close(resolve));
      const runId = `ENSAYO-G059-20261028-000000-${modo}`;
      const directorio = path.join(temporal, modo); fs.mkdirSync(directorio);
      const c = { version: 1, intento: 1, operacion: 'evaluar', runId,
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
      assert.equal(r.oficial, oficial, `${modo} oficial: ${JSON.stringify({ solicitudes: r.solicitudes.length, limite: CAPACIDADES.limite.solicitudes_totales, cierre: r.cierre, problemas: r.problemas_tecnicos, evidencias: r.evidencias, presentes: r.evidencias.map(x => [x, fs.existsSync(path.join(directorio, x))]), casos: r.casos, condiciones: [CASOS.every(x => ['APROBADO','RECHAZADO'].includes(r.casos[x].estado)), !r.problemas_tecnicos.length, r.cierre.run.cierre_http === 200, r.cierre.rollback.verificado, r.solicitudes.length <= CAPACIDADES.limite.solicitudes_totales, r.evidencias.some(x => x.endsWith('.html'))] })}`);
      const presentes = new Set(r.evidencias.filter(x => fs.existsSync(path.join(directorio, x))));
      assert.equal(clasificarRegistro(CAPACIDADES, r, presentes, c), oficial, `${modo} registro QA`);
      const persistido = JSON.parse(fs.readFileSync(path.join(directorio, 'resultado.json'), 'utf8'));
      assert.deepEqual(CASOS.map(x => persistido.casos[x].estado), estados);
      assert.equal(clasificarRegistro(CAPACIDADES, persistido, presentes, c), oficial,
        `${modo} resultado.json`);
      const md = fs.readFileSync(path.join(directorio, 'TC-M04-G059_resultado.md'), 'utf8');
      assert.ok(md.includes('## Detalle por caso') && md.includes('## Catorce combinaciones'));
      const combinaciones = md.split('## Catorce combinaciones\n')[1].split('\n## Observaciones')[0];
      assert.equal((combinaciones.match(/^\| TC-M04-16[1-4] \| /gm) ?? []).length, 14);
      assert.ok(!md.includes('GET HTTP 200 ;'), `${modo} volcado de lecturas`);
      assert.ok(!contieneMojibake(md), `${modo} codificación`);
      for (const valor of [PASSWORD, CLAVE, SANDBOX, 'admin@example.test', 'vet@example.test']) {
        assert.ok(!md.includes(valor), `${modo} secreto en informe`);
        assert.ok(!fs.readFileSync(path.join(directorio, 'resultado.json'), 'utf8').includes(valor));
      }
      if (modo === 'todo_ok') {
        assert.equal(combinaciones.split('\n').filter(x => x.startsWith(`| TC-M04-162 | V2 ${persistido.versiones.V2} ACTIVO →`)).length, 3);
        assert.equal(r.solicitudes.length, PRESUPUESTO.total, 'presupuesto exacto completo');
        assert.equal(r.cierre.rollback.verificado, true);
        assert.equal(r.combinaciones.length, 14);
      }
      if (modo === 'reenvio_crea_version_nueva') assert.equal(r.solicitudes.length, PRESUPUESTO.total + 1);
      if (modo === 'login_lento') assert.ok(r.solicitudes.slice(0, 2).every(x => x.duracion_ms >= 300));
      if (modo === 'sin_respuesta') assert.ok(r.problemas_tecnicos.some(x => x.includes('sin respuesta')));
      console.log(`${modo}: ${estados.join('/')}; ${oficial ? 'OFICIAL' : 'TÉCNICO/NO_CONCLUYENTE'}`);
    } finally {
      if (s.server.listening) { s.server.closeAllConnections(); await new Promise(resolve => s.server.close(resolve)); }
    }
  }
  if (!process.env.G059_MODO)
    console.log(`OK G059: ${modos.length}/${modos.length} modos; presupuesto ${PRESUPUESTO.total}; registro QA fiel`);
} finally { fs.rmSync(temporal, { recursive: true, force: true }); }
