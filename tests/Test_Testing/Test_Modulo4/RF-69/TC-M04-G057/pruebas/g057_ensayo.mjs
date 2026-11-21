import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import http from 'node:http';
import { evaluar, leerEnv } from '../g057.mjs';
import { CASOS, CAPACIDADES, PRESUPUESTO } from '../lib/g057_escenario.mjs';
import { clasificarRegistro } from './registro_qa.mjs';
import { contieneMojibake } from '../lib/seguridad.mjs';

const MODOS = [
  ['todo_ok', ['APROBADO', 'APROBADO', 'APROBADO', 'APROBADO'], true],
  ['activa_previa_heredada', ['NO_CONCLUYENTE', 'APROBADO', 'APROBADO', 'APROBADO'], false],
  ['primera_deprecada_indebida', ['RECHAZADO', 'APROBADO', 'APROBADO', 'APROBADO'], true],
  ['coexisten_dos_activas', ['APROBADO', 'RECHAZADO', 'APROBADO', 'APROBADO'], true],
  ['previa_no_deprecada', ['APROBADO', 'RECHAZADO', 'APROBADO', 'APROBADO'], true],
  ['correlacion_distinta', ['APROBADO', 'APROBADO', 'RECHAZADO', 'APROBADO'], true],
  ['sin_correlacion', ['APROBADO', 'APROBADO', 'RECHAZADO', 'APROBADO'], true],
  ['activa_sin_notas', ['APROBADO', 'APROBADO', 'APROBADO', 'RECHAZADO'], true],
  ['espacios_aceptados_y_activa', ['APROBADO', 'APROBADO', 'APROBADO', 'RECHAZADO'], true],
  ['espacios_rechazados_en_patch', ['APROBADO', 'APROBADO', 'APROBADO', 'APROBADO'], true],
  ['respuesta_sin_version_deprecada', ['APROBADO', 'APROBADO', 'APROBADO', 'APROBADO'], true],
  ['env_archivo', ['APROBADO', 'APROBADO', 'APROBADO', 'APROBADO'], true],
  ['activar_a_5xx', ['RECHAZADO', 'APROBADO', 'APROBADO', 'APROBADO'], true],
  ['activar_a_y_b_5xx', ['RECHAZADO', 'RECHAZADO', 'RECHAZADO', 'APROBADO'], true],
  ['activar_b_5xx', ['APROBADO', 'RECHAZADO', 'RECHAZADO', 'APROBADO'], true],
  ['activar_c_5xx', ['APROBADO', 'APROBADO', 'APROBADO', 'RECHAZADO'], true],
  ['clave_403', ['BLOQUEADO', 'BLOQUEADO', 'BLOQUEADO', 'BLOQUEADO'], false],
  ['error5xx', ['BLOQUEADO', 'BLOQUEADO', 'BLOQUEADO', 'BLOQUEADO'], false],
  ['sin_respuesta', ['NO_CONCLUYENTE', 'NO_CONCLUYENTE', 'NO_CONCLUYENTE', 'NO_CONCLUYENTE'], false],
  ['login_lento', ['APROBADO', 'APROBADO', 'APROBADO', 'APROBADO'], true],
  ['login_sin_red', ['BLOQUEADO', 'BLOQUEADO', 'BLOQUEADO', 'BLOQUEADO'], false]
];
const PASSWORD = 'clave-local-ensayo';
const CLAVE = 'rf71-local-ensayo';
const SANDBOX = 'sandbox-local-ensayo';
const respuesta = (res, code, body, run) => {
  res.writeHead(code, { 'Content-Type': 'application/json; charset=utf-8',
    ...(run ? { 'X-Test-Run-Id': run } : {}) }); res.end(JSON.stringify(body));
};
const campo = (raw, nombre) => raw.match(new RegExp(`name="${nombre}"[^\\r\\n]*\\r\\n\\r\\n([^\\r\\n]*)`))?.[1] ?? null;
const leer = async req => { const chunks = []; for await (const x of req) chunks.push(x);
  return Buffer.concat(chunks).toString('utf8'); };

function servidor(modo) {
  const versiones = [], eventos = [], peticiones = [];
  let activosFiltrados = 0, consultasA = 0;
  if (modo === 'activa_previa_heredada') versiones.push({ id_version_modelo: 90,
    tipo_modelo: 'MODELO_ESPECIES_GRANDES', componente: null, estado_version: 'ACTIVO',
    esta_produccion: true, notas_validacion: 'heredada' }, { id_version_modelo: 91,
    tipo_modelo: 'MODELO_ESPECIES_MEDIANAS', componente: null, estado_version: 'ACTIVO',
    esta_produccion: true, notas_validacion: 'heredada' });
  if (modo === 'primera_deprecada_indebida') versiones.push({ id_version_modelo: 92,
    tipo_modelo: 'MODELO_ESPECIES_GRANDES', componente: null, estado_version: 'APROBADO',
    esta_produccion: false, notas_validacion: null });
  const iniciales = versiones.map(x => ({ ...x }));
  const server = http.createServer(async (req, res) => {
    try {
      const u = new URL(req.url, 'http://127.0.0.1');
      const run = req.headers['x-test-run-id'];
      peticiones.push(`${req.method} ${u.pathname}`);
      if (req.method === 'POST' && u.pathname === '/sesiones/') {
        const x = JSON.parse(await leer(req)); assert.equal(x.contrasena, PASSWORD);
        // 310 ms simulan 31 s; el ejecutor usa 1200 ms como escala de 120 s en ensayo.
        if (modo === 'login_lento') await new Promise(resolve => setTimeout(resolve, 310));
        return respuesta(res, 200, { token: x.correo_electronico.startsWith('vet') ? 'token-vet' : 'token-admin' });
      }
      if (req.method === 'DELETE' && u.pathname.startsWith('/test-control/runs/')) {
        versiones.splice(0, versiones.length, ...iniciales.map(x => ({ ...x })));
        eventos.length = 0;
        return respuesta(res, 200, { status: 'cerrado', rollback: true });
      }
      if (req.method === 'GET' && u.pathname === '/configuracion/variables-ambientales')
        return respuesta(res, 200, { total: 1, items: [{ id_variable_ambiental: 7 }] }, run);
      if (req.method === 'POST' && u.pathname === '/prediccion/modelos') {
        if (modo === 'sin_respuesta') { req.socket.destroy(); return; }
        const raw = await leer(req);
        if (modo === 'clave_403') return respuesta(res, 403, { code: 'CLAVE_INVALIDA' }, run);
        if (modo === 'error5xx') return respuesta(res, 500, { code: 'ERROR' }, run);
        assert.equal(req.headers['x-rf71-internal-key'], CLAVE);
        assert.equal(req.headers['x-sandbox-secret'], SANDBOX);
        assert.ok(raw.includes('name="archivo_modelo"'));
        const n = versiones.filter(x => x.id_version_modelo >= 101).length;
        const v = { id_version_modelo: 101 + n, tipo_modelo: campo(raw, 'tipo_modelo'),
          componente: null, estado_version: 'APROBADO', esta_produccion: false,
          notas_validacion: null, f1_score: 0.91, recall_clase_riesgo_alto: 0.93 };
        versiones.push(v); return respuesta(res, 201, v, run);
      }
      if (req.method === 'GET' && u.pathname === '/prediccion/modelos') {
        let items = [...versiones];
        if (u.searchParams.has('tipo_modelo')) items = items.filter(x => x.tipo_modelo === u.searchParams.get('tipo_modelo'));
        if (u.searchParams.has('estado')) items = items.filter(x => x.estado_version === u.searchParams.get('estado'));
        if (u.searchParams.get('estado') === 'ACTIVO' && u.searchParams.has('tipo_modelo')) activosFiltrados++;
        if (modo === 'coexisten_dos_activas' && activosFiltrados === 2
          && !items.some(x => x.id_version_modelo === 101)) {
          const a = versiones.find(x => x.id_version_modelo === 101);
          a.estado_version = 'ACTIVO'; a.esta_produccion = true;
          items.push(a);
        }
        return respuesta(res, 200, { total: items.length, items }, run);
      }
      if (req.method === 'GET' && u.pathname === '/prediccion/auditoria') {
        const id = u.searchParams.get('id_referencia');
        const items = eventos.filter(x => x.id_referencia === id);
        items.push({ tipo_evento: 'HISTORIAL_CONSULTADO', id_referencia: id });
        return respuesta(res, 200, { total: items.length, items }, run);
      }
      const m = u.pathname.match(/^\/prediccion\/modelos\/(\d+)(\/notas|\/activar)?$/);
      if (m) {
        const v = versiones.find(x => x.id_version_modelo === Number(m[1]));
        if (!v) return respuesta(res, 404, { code: 'NO_ENCONTRADO' }, run);
        if (!m[2] && req.method === 'GET') {
          if (v.id_version_modelo === 101) consultasA++;
          return respuesta(res, 200, modo === 'previa_no_deprecada' && v.id_version_modelo === 101
            && consultasA === 2 ? { ...v, estado_version: 'ACTIVO', esta_produccion: true } : v, run);
        }
        if (m[2] === '/notas' && req.method === 'PATCH') {
          const x = JSON.parse(await leer(req));
          if (!x.notas_validacion.trim()) {
            if (modo === 'espacios_aceptados_y_activa') { v.notas_validacion = x.notas_validacion;
              return respuesta(res, 200, v, run); }
            return respuesta(res, 422, { code: 'NOTAS_VACIAS' }, run);
          }
          v.notas_validacion = x.notas_validacion;
          return respuesta(res, 200, v, run);
        }
        if (m[2] === '/activar' && req.method === 'POST') {
          if (['activar_a_5xx', 'activar_a_y_b_5xx'].includes(modo) && v.id_version_modelo === 101
            || modo === 'activar_a_y_b_5xx' && v.id_version_modelo === 102
            || modo === 'activar_b_5xx' && v.id_version_modelo === 102
            || modo === 'activar_c_5xx' && v.id_version_modelo === 103)
            return respuesta(res, 500, { code: 'ERROR_TEMPORAL' }, run);
          if (!String(v.notas_validacion ?? '').trim() && !(
            modo === 'activa_sin_notas' && v.id_version_modelo === 103
            || modo === 'espacios_aceptados_y_activa' && v.id_version_modelo === 104))
            return respuesta(res, 422, { code: 'NOTAS_VALIDACION_REQUERIDAS' }, run);
          const previa = versiones.find(x => x.tipo_modelo === v.tipo_modelo && x.componente === v.componente
            && x.estado_version === 'ACTIVO');
          if (previa && previa !== v) {
            previa.estado_version = 'DEPRECADO'; previa.esta_produccion = false;
          }
          if (modo === 'primera_deprecada_indebida' && v.id_version_modelo === 101)
            versiones.find(x => x.id_version_modelo === 92).estado_version = 'DEPRECADO';
          v.estado_version = 'ACTIVO'; v.esta_produccion = true;
          const corr = v.id_version_modelo === 101 ? 'corr-a' : 'corr-b';
          eventos.push({ tipo_evento: 'VERSION_ACTIVADA', id_referencia: String(v.id_version_modelo),
            correlacion_id: modo === 'sin_correlacion' && v.id_version_modelo === 102 ? null : corr });
          if (previa && previa !== v) eventos.push({ tipo_evento: 'VERSION_DEPRECADA',
            id_referencia: String(previa.id_version_modelo),
            correlacion_id: modo === 'sin_correlacion' && v.id_version_modelo === 102 ? null
              : modo === 'correlacion_distinta' && v.id_version_modelo === 102 ? 'corr-otro' : corr });
          const out = { ...v };
          if (modo !== 'respuesta_sin_version_deprecada' && previa && previa !== v)
            out.version_deprecada = previa.id_version_modelo;
          return respuesta(res, 200, out, run);
        }
      }
      respuesta(res, 404, {}, run);
    } catch (e) { respuesta(res, 500, { code: 'MOCK_ERROR' }); }
  });
  return { server, peticiones };
}

const temporal = fs.mkdtempSync(path.join(os.tmpdir(), 'g057-ensayo-'));
try {
  for (const [modo, esperados, oficial] of MODOS) {
    const s = servidor(modo);
    await new Promise(resolve => s.server.listen(0, '127.0.0.1', resolve));
    try {
      const puerto = s.server.address().port;
      if (modo === 'login_sin_red') await new Promise(resolve => s.server.close(resolve));
      const runId = `ENSAYO-G057-20261028-000000-${modo}`;
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
      assert.equal(r.oficial, oficial, `${modo} oficial`);
      if (oficial) assert.equal(r.solicitudes.length,
        modo === 'activar_a_5xx' ? PRESUPUESTO.contingencia_maxima
          : modo === 'activar_a_y_b_5xx' ? 38 : PRESUPUESTO.total, `${modo} presupuesto`);
      const presentes = new Set(r.evidencias.filter(x => fs.existsSync(path.join(directorio, x))));
      assert.equal(clasificarRegistro(CAPACIDADES, r, presentes, c), oficial, `${modo} registro QA`);
      const persistido = JSON.parse(fs.readFileSync(path.join(directorio, 'resultado.json'), 'utf8'));
      assert.deepEqual(CASOS.map(x => persistido.casos[x].estado), estados);
      assert.equal(persistido.run_id, runId);
      const md = fs.readFileSync(path.join(directorio, 'TC-M04-G057_resultado.md'), 'utf8');
      const decision = estados.includes('RECHAZADO') ? 'RECHAZADO'
        : estados.every(x => x === 'APROBADO') ? 'APROBADO'
          : estados.includes('BLOQUEADO') ? 'BLOQUEADO' : 'NO_CONCLUYENTE';
      assert.ok(md.startsWith(`# TC-M04-G057 — ${decision}\n`), `${modo} título`);
      assert.ok(md.includes(`**RUN oficial: no.**`), `${modo} clasificación local`);
      assert.ok(md.includes('**Qué falta: '), `${modo} acción pendiente`);
       const seccion = md.match(/## Detalle por caso\n\n([\s\S]*?)\n\n## Esperado y observado/);
       assert.ok(seccion, `${modo} sección de detalle`);
       const apartados = [...seccion[1].matchAll(/### (TC-M04-\d{3}) — (APROBADO|RECHAZADO|BLOQUEADO|NO_CONCLUYENTE)\n\n([\s\S]*?)(?=\n\n### |$)/g)];
       assert.equal(apartados.length, CASOS.length, `${modo} cuatro apartados`);
       apartados.forEach((apartado, i) => {
         assert.equal(apartado[1], CASOS[i], `${modo} caso del detalle`);
         assert.equal(apartado[2], estados[i], `${modo} decisión del detalle`);
         const lineas = apartado[3].trim().split('\n');
         assert.equal(lineas.length, 4, `${modo} cuatro líneas del detalle`);
         ['Qué se hizo', 'Qué se esperaba', 'Qué se observó', `Por qué ${estados[i]}`]
           .forEach((rotulo, j) => assert.ok(lineas[j].startsWith(`**${rotulo}:** `), `${modo} ${rotulo}`));
         assert.ok(lineas[1].includes('RF-69') && lineas[1].includes('líneas '), `${modo} cita del requisito`);
       });
       assert.ok(!/HTTP_null|=\{A\}|<NULL>|LOGIN_[A-Z_]+/.test(seccion[1]), `${modo} lenguaje claro`);
       assert.ok(!seccion[1].includes('undefined'), `${modo} valores definidos`);
       if (modo === 'login_sin_red') assert.ok(seccion[1].includes('no se ejecutó ninguna prueba del caso'));
       if (modo === 'activar_a_5xx') assert.ok(seccion[1].includes('activación inicial de versión 102'));
      if (r.solicitudes.some(x => x.ruta === '/configuracion/variables-ambientales')) {
        assert.ok(md.includes(' | 1 | 1 variables | '), `${modo} fila del catálogo`);
        assert.ok(!md.includes('undefined:null'), `${modo} catálogo sin campos ajenos`);
      }
      assert.ok(!contieneMojibake(md));
      for (const valor of [PASSWORD, CLAVE, SANDBOX, 'admin@example.test', 'vet@example.test']) {
        assert.ok(!md.includes(valor));
        assert.ok(!fs.readFileSync(path.join(directorio, 'resultado.json'), 'utf8').includes(valor));
      }
      if (modo === 'respuesta_sin_version_deprecada')
        assert.ok(r.observaciones.some(x => x.includes('version_deprecada')));
      if (modo === 'activa_previa_heredada') assert.equal(r.oficial, false);
      if (modo === 'login_lento') {
        assert.equal(r.solicitudes.length, PRESUPUESTO.total);
        assert.ok(r.solicitudes.slice(0, 2).every(x => x.ruta === '/sesiones/'
          && x.duracion_ms >= 310 && x.duracion_ms < 1200 && x.http === 200));
      }
      if (modo === 'login_sin_red') {
        assert.equal(r.solicitudes.length, 1);
        assert.equal(r.solicitudes[0].error, 'SIN_RESPUESTA');
        assert.equal(r.solicitudes[0].tipo_fallo, 'ECONNREFUSED');
        assert.ok(Number.isFinite(r.solicitudes[0].duracion_ms));
        assert.ok(CASOS.every(x => r.casos[x].motivo.includes('LOGIN_ADMIN_SIN_RESPUESTA_ECONNREFUSED')));
        assert.ok(md.includes('LOGIN_ADMIN_SIN_RESPUESTA_ECONNREFUSED'));
        assert.ok(md.includes('no hubo peticiones dentro del RUN'));
        assert.ok(!r.solicitudes.some(x => x.eco !== undefined && x.eco !== null));
      }
      if (modo.startsWith('activar_') && modo.endsWith('_5xx')) {
        const incidencias5xx = r.incidencias.filter(x => x.http >= 500);
        assert.equal(incidencias5xx.length, 1, `${modo} una causa, una incidencia`);
        assert.equal(incidencias5xx[0].codigo, 'ERROR_TEMPORAL');
        assert.ok(incidencias5xx[0].estado_antes && incidencias5xx[0].estado_despues);
        assert.deepEqual(incidencias5xx[0].casos,
          modo === 'activar_a_5xx' ? [CASOS[0]]
            : modo === 'activar_c_5xx' ? [CASOS[3]]
              : modo === 'activar_b_5xx' ? [CASOS[1], CASOS[2]] : CASOS.slice(0, 3));
      }
      console.log(`${modo}: ${estados.join('/')}; ${oficial ? 'OFICIAL' : 'TÉCNICO/NO_CONCLUYENTE'}`);
    } finally { if (s.server.listening) await new Promise(resolve => s.server.close(resolve)); }
  }
  console.log(`OK G057: ${MODOS.length}/${MODOS.length} modos; presupuesto ${PRESUPUESTO.total} (máx. ${PRESUPUESTO.contingencia_maxima}); registro QA fiel`);
} finally { fs.rmSync(temporal, { recursive: true, force: true }); }
