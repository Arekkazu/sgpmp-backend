import assert from 'node:assert/strict';
import fs from 'node:fs';
import http from 'node:http';
import os from 'node:os';
import path from 'node:path';
import { evaluar, recuperar, leerEnv } from '../g060.mjs';
import { CASOS, CAPACIDADES, PRESUPUESTO, LLAVES, LINEA_BASE_RECUPERACION,
  llaveId, decidirDisparo } from '../lib/g060_escenario.mjs';
import { clasificarRegistro } from './registro_qa.mjs';

const A = ['APROBADO', 'APROBADO', 'APROBADO', 'APROBADO'];
const cambiar = (i, v = 'RECHAZADO') => A.map((x, j) => i === j ? v : x);
const modosServidor = [
  ['todo_ok', A, true], ['doble_exito_con_solape', cambiar(0), true],
  ['carrera_dos_activas_166', cambiar(0), true],
  ['perdedor_5xx_coherente', A, true], ['perdedor_5xx_incoherente', cambiar(0), true],
  ['misma_version_doble_evento', cambiar(1), true],
  ['misma_version_doble_deprecacion', cambiar(1), true],
  ['misma_version_segunda_2xx_sin_eventos', A, true],
  ['carrera_en_repeticion_7', cambiar(2), true],
  ['estado_intermedio_168', cambiar(2), true],
  ['llave_cancelada_169', cambiar(3), true],
  ['global_en_vez_de_por_llave', cambiar(3), true],
  ['sin_evento_conflicto', A, true],
  ['fallo_preparacion_167', cambiar(1, 'NO_CONCLUYENTE'), false],
  ['env_archivo', A, true], ['login_lento', A, true],
  ['login_sin_red', CASOS.map(() => 'BLOQUEADO'), false],
  ['clave_403', CASOS.map(() => 'BLOQUEADO'), false],
  ['error5xx', CASOS.map(() => 'BLOQUEADO'), false],
  ['corte_5xx_con_cierre', CASOS.map(() => 'BLOQUEADO'), false],
  ['sin_respuesta', cambiar(0, 'NO_CONCLUYENTE'), false]
];
const leer = req => new Promise((resolve, reject) => { const a = [];
  req.on('data', x => a.push(x)); req.on('end', () => resolve(Buffer.concat(a)));
  req.on('error', reject); });
const responder = (res, code, body, run) => {
  res.writeHead(code, { 'Content-Type': 'application/json', ...(run ? { 'X-Test-Run-Id': run } : {}) });
  res.end(JSON.stringify(body));
};
const campo = (s, nombre) => {
  const m = s.match(new RegExp(`name="${nombre}"[^\\r\\n]*\\r?\\n\\r?\\n([^\\r\\n]*)`));
  return m?.[1] ?? null;
};
function servidor(modo) {
  const versiones = [], eventos = [], ultimo = new Map();
  const peticiones = [];
  let n = 100, registros = 0, rep168 = 0, yaError = false, activaciones169 = 0;
  const ev = (tipo_evento, id, correlacion) => eventos.push({ tipo_evento,
    id_referencia: String(id), correlacion_id: correlacion });
  const key = v => `${v.tipo_modelo}/${v.componente ?? ''}`;
  const server = http.createServer(async (req, res) => {
    const u = new URL(req.url, 'http://127.0.0.1'), run = req.headers['x-test-run-id'];
    peticiones.push({ metodo: req.method, ruta: u.pathname, run: run ?? null });
    try {
      if (u.pathname === '/sesiones/' && req.method === 'POST') {
        await leer(req);
        if (modo === 'login_sin_red') return req.socket.destroy();
        if (modo === 'login_lento') await new Promise(ok => setTimeout(ok, 150));
        return responder(res, 200, { token: `token-local-${n++}` });
      }
      if (req.method === 'DELETE' && u.pathname.startsWith('/test-control/runs/')) {
        versiones.length = 0; eventos.length = 0;
        if (modo.startsWith('recuperar_')) for (const k of LLAVES[169])
          for (const id of LINEA_BASE_RECUPERACION.por_llave[llaveId(k)].ids)
            versiones.push({ id_version_modelo: modo === 'recuperar_diferencia_ajena' && id === 43
              ? 99 : id, tipo_modelo: k.tipo, componente: k.componente, estado_version: 'ACTIVO' });
        if (modo === 'recuperar_delete_ya_cerrado')
          return responder(res, 404, { detail: 'Run ID no encontrado.' });
        return responder(res, 200, { cerrado: true });
      }
      if (u.pathname === '/configuracion/variables-ambientales')
        return responder(res, 200, { total: 1, items: [{ id_variable_ambiental: 7 }] }, run);
      if (u.pathname === '/prediccion/modelos' && req.method === 'POST') {
        const body = (await leer(req)).toString('utf8'); registros++;
        if (modo === 'clave_403') return responder(res, 403, { code: 'CLAVE_INVALIDA' }, run);
        if (['error5xx', 'corte_5xx_con_cierre'].includes(modo))
          return responder(res, 500, { code: 'ERROR_TEMPORAL' }, run);
        if (modo === 'fallo_preparacion_167' && registros === 7)
          return responder(res, 422, { code: 'DATO_INVALIDO' }, run);
        const tipo = campo(body, 'tipo_modelo') ?? 'MODELO_ESPECIES_GRANDES';
        const comp = campo(body, 'componente') || null;
        const v = { id_version_modelo: n++, tipo_modelo: tipo, componente: comp,
          estado_version: 'APROBADO', esta_produccion: false, notas_validacion: null };
        versiones.push(v); ev('VERSION_APROBADA', v.id_version_modelo, `reg-${v.id_version_modelo}`);
        return responder(res, 201, v, run);
      }
      if (u.pathname === '/prediccion/modelos' && req.method === 'GET') {
        let items = versiones.filter(v => !u.searchParams.has('tipo_modelo')
          || v.tipo_modelo === u.searchParams.get('tipo_modelo'));
        if (u.searchParams.has('estado')) items = items.filter(v => v.estado_version === u.searchParams.get('estado'));
        if (modo === 'recuperar_id_del_run_activo'
          && u.searchParams.get('tipo_modelo') === 'MODELO_ESPECIES_GRANDES')
          items.push({ id_version_modelo: 112, tipo_modelo: 'MODELO_ESPECIES_GRANDES',
            componente: null, estado_version: 'ACTIVO' });
        return responder(res, 200, { total: items.length, items }, run);
      }
      if (u.pathname === '/prediccion/auditoria') {
        const id = u.searchParams.get('id_referencia');
        const items = eventos.filter(x => x.id_referencia === id);
        return responder(res, 200, { total: items.length, items }, run);
      }
      const m = u.pathname.match(/^\/prediccion\/modelos\/(\d+)(\/notas|\/activar)?$/);
      if (!m) return responder(res, 404, { code: 'NO_ENCONTRADO' }, run);
      if (modo === 'recuperar_version_persiste' && m[1] === '112' && req.method === 'GET')
        return responder(res, 200, { id_version_modelo: 112 }, run);
      const v = versiones.find(x => x.id_version_modelo === Number(m[1]));
      if (!v) return responder(res, 404, { code: 'NO_ENCONTRADO' }, run);
      if (!m[2] && req.method === 'GET') return responder(res, 200, v, run);
      if (m[2] === '/notas' && req.method === 'PATCH') {
        const b = JSON.parse((await leer(req)).toString('utf8'));
        v.notas_validacion = b.notas_validacion;
        return responder(res, 200, v, run);
      }
      if (m[2] === '/activar' && req.method === 'POST') {
        await leer(req);
        const k = key(v), previo = versiones.find(x => key(x) === k && x.estado_version === 'ACTIVO');
        const ahora = Date.now(), simultanea = ahora - (ultimo.get(k) ?? 0) < 120;
        ultimo.set(k, ahora);
        const es166 = k === key({ ...LLAVES[166], tipo_modelo: LLAVES[166].tipo });
        const es168 = v.tipo_modelo === LLAVES[168].tipo && v.componente === LLAVES[168].componente;
        const es169 = LLAVES[169].some(x => x.tipo === v.tipo_modelo && x.componente === v.componente);
        if (es168 && !simultanea) rep168++;
        if (es169) activaciones169++;
        if (modo === 'sin_respuesta' && es166 && simultanea && !yaError) {
          yaError = true; return req.socket.destroy();
        }
        if (modo === 'llave_cancelada_169' && es169 && activaciones169 === 4
          || modo === 'global_en_vez_de_por_llave' && es169 && activaciones169 > 1)
          return responder(res, 409, { code: 'CONCURRENCIA_GLOBAL' }, run);
        if (modo === 'perdedor_5xx_coherente' && es166 && simultanea
          || modo === 'perdedor_5xx_incoherente' && es166 && simultanea) {
          if (modo === 'perdedor_5xx_incoherente') { v.estado_version = 'ACTIVO'; v.esta_produccion = true; }
          await new Promise(ok => setTimeout(ok, 20));
          return responder(res, 500, { code: 'PERSISTENCIA_FALLIDA' }, run);
        }
        const segundaValida = modo === 'doble_exito_con_solape' && es166 && simultanea;
        const carrera166 = modo === 'carrera_dos_activas_166' && es166 && simultanea;
        const carrera168 = modo === 'carrera_en_repeticion_7' && es168 && rep168 === 7 && simultanea;
        const segunda167 = modo === 'misma_version_segunda_2xx_sin_eventos'
          && v.estado_version === 'ACTIVO' && !es166 && !es168 && !es169;
        if (segunda167) { await new Promise(ok => setTimeout(ok, 20)); return responder(res, 200, v, run); }
        if (v.estado_version !== 'APROBADO' || simultanea && !segundaValida && !carrera166 && !carrera168) {
          await new Promise(ok => setTimeout(ok, 20));
          return responder(res, 409, { code: 'VERSION_NO_APROBADA' }, run);
        }
        const correlacion = `act-${v.id_version_modelo}`;
        if (previo && !carrera166 && !carrera168) {
          previo.estado_version = 'DEPRECADO'; previo.esta_produccion = false;
          ev('VERSION_DEPRECADA', previo.id_version_modelo, correlacion);
          if (modo === 'misma_version_doble_deprecacion' && !es166 && !es168 && !es169)
            ev('VERSION_DEPRECADA', previo.id_version_modelo, correlacion);
        }
        v.estado_version = modo === 'estado_intermedio_168' && es168 && rep168 === 1
          ? 'EN_VALIDACION' : 'ACTIVO';
        v.esta_produccion = v.estado_version === 'ACTIVO';
        ev('VERSION_ACTIVADA', v.id_version_modelo, correlacion);
        if (modo === 'misma_version_doble_evento' && !es166 && !es168 && !es169)
          ev('VERSION_ACTIVADA', v.id_version_modelo, correlacion);
        await new Promise(ok => setTimeout(ok, 20));
        return responder(res, 200, v, run);
      }
      return responder(res, 405, { code: 'METODO_INVALIDO' }, run);
    } catch { if (!res.headersSent) responder(res, 500, { code: 'LOOPBACK_ERROR' }, run); }
  });
  server.peticiones = peticiones;
  return server;
}

async function uno(modo, esperado, oficialEsperado) {
  const server = servidor(modo);
  await new Promise(ok => server.listen(0, '127.0.0.1', ok));
  const temp = fs.mkdtempSync(path.join(os.tmpdir(), `g060-${modo}-`));
  try {
    const runId = `ENSAYO-G060-20261028-000000-${modo}`;
    const c = { runId, version: 1, intento: 1, operacion: 'evaluar', referencia: 'Ensayo local',
      directorio: temp, ensayo: true };
    const env = { SIGAB_API_TEST_BASE: `http://127.0.0.1:${server.address().port}`,
      QA_SANDBOX_SECRET: 'sandbox-local-ensayo', RF71_INTERNAL_KEY: 'rf71-local-ensayo',
      QA_ADMIN_EMAIL: 'admin@ejemplo.test', QA_ADMIN_PASSWORD: 'clave-local-ensayo',
      QA_VETERINARIO_EMAIL: 'vet@ejemplo.test', QA_COMMON_PASSWORD: 'clave-local-ensayo',
      QA_AUTORIZADO: 'SI' };
    let usado = env;
    if (modo === 'env_archivo') {
      const archivo = path.join(temp, '.env.qa');
      fs.writeFileSync(archivo, Object.entries(env).filter(([k]) => k !== 'QA_AUTORIZADO')
        .map(([k, v]) => `${k}=${v}`).join('\n'));
      usado = leerEnv({ QA_AUTORIZADO: 'SI' }, archivo);
    }
    const r = await evaluar(c, { env: usado, ensayo: true });
    if (JSON.stringify(CASOS.map(x => r.casos[x].estado)) !== JSON.stringify(esperado))
      console.error(JSON.stringify({ modo, casos: r.casos, problemas: r.problemas_tecnicos,
        solicitudes: r.solicitudes.filter(x => x.metodo === 'POST').slice(0, 18), detalle: r.detalle }));
    assert.deepEqual(CASOS.map(x => r.casos[x].estado), esperado, modo);
    assert.equal(r.oficial, oficialEsperado, modo);
    if (modo === 'todo_ok') {
      assert.equal(r.solicitudes.length, PRESUPUESTO.solicitudes_normales);
      assert.equal(r.solicitudes.filter(x => x.rol === 'RF-71 interno').length, 22);
      assert.equal(r.repeticiones.length, 10);
    }
    if (modo === 'corte_5xx_con_cierre') {
      assert.equal(r.problemas_tecnicos.includes('TRES_5XX_CONSECUTIVOS'), true);
      assert.equal(r.cierre.run.cierre_http, 200);
      assert.equal(r.cierre.rollback.verificado, true);
      assert.equal(server.peticiones.filter(x => x.metodo === 'DELETE').length, 1);
      assert.equal(r.solicitudes.filter(x => x.rol === 'Administrador poscierre').length, 7);
    }
    if (modo === 'login_sin_red') {
      assert.equal(server.peticiones.filter(x => x.metodo === 'DELETE').length, 1);
      assert.equal(r.cierre.rollback.verificado, false);
    }
    if (modo === 'carrera_en_repeticion_7') assert.equal(r.repeticiones.length, 7);
    if (modo === 'perdedor_5xx_coherente')
      assert(r.observaciones.some(x => x.includes('Perdedor HTTP 5xx')));
    if (modo === 'sin_evento_conflicto')
      assert(r.observaciones.some(x => x.includes('FA-09')));
    if (oficialEsperado) {
      const presentes = new Set(fs.readdirSync(temp).concat(fs.existsSync(path.join(temp, 'newman'))
        ? fs.readdirSync(path.join(temp, 'newman')).map(x => `newman/${x}`) : []));
      assert(clasificarRegistro(CAPACIDADES, JSON.parse(fs.readFileSync(path.join(temp, 'resultado.json'))), presentes, c), modo);
    }
    return r;
  } finally {
    await new Promise(ok => server.close(ok));
    fs.rmSync(temp, { recursive: true, force: true });
  }
}

async function ensayoRecuperar(modo, esperado, conBase = true) {
  const server = servidor(modo);
  await new Promise(ok => server.listen(0, '127.0.0.1', ok));
  const temp = fs.mkdtempSync(path.join(os.tmpdir(), `g060-${modo}-`));
  try {
    const runId = 'RUN-G060-V1-20261028-162607';
    const base = Object.fromEntries(LLAVES[169].map(k => [llaveId(k),
      [...LINEA_BASE_RECUPERACION.por_llave[llaveId(k)].ids]]));
    fs.writeFileSync(path.join(temp, 'resultado.json'), JSON.stringify({ grupo: 'G060',
      run_id: runId, version: 1, oficial: false,
      ...(conBase ? { estado_inicial_activo: base } : {}) }));
    const c = { runId, objetivo: runId, version: 1, operacion: 'recuperar',
      referencia: 'Ensayo local', directorio: temp };
    const env = { SIGAB_API_TEST_BASE: `http://127.0.0.1:${server.address().port}`,
      QA_SANDBOX_SECRET: 'sandbox-local-ensayo', QA_ADMIN_EMAIL: 'admin@ejemplo.test',
      QA_ADMIN_PASSWORD: 'clave-local-ensayo', QA_AUTORIZADO: 'SI' };
    const r = await recuperar(c, { env, ensayo: true });
    assert.equal(r.rollback_verificado, esperado, modo);
    assert.equal(r.cierre_solicitado, true);
    assert.equal(r.cierre_confirmado, true);
    assert.equal(r.cierre.run.estaba_abierto, modo !== 'recuperar_delete_ya_cerrado');
    assert.equal(r.comprobacion.versiones_404_sin_cabecera_run,
      modo !== 'recuperar_version_persiste');
    assert.equal(r.comprobacion.ids_del_run_activos, modo === 'recuperar_id_del_run_activo');
    if (modo === 'recuperar_linea_base_coincide')
      assert.deepEqual(r.comprobacion.diferencias_linea_base, []);
    if (modo === 'recuperar_diferencia_ajena') {
      assert.deepEqual(r.comprobacion.diferencias_linea_base,
        ['MODELO_ESPECIES_MEDIANAS/SIN_COMPONENTE']);
      assert(r.observaciones.some(x => x.includes('posible actividad ajena')));
    }
    if (modo === 'recuperar_sin_base_inicial')
      assert(r.lineas_base[llaveId(LLAVES[169][0])].fuente.includes('G059/'));
    assert.equal(r.solicitudes.length, 19);
    assert.equal(server.peticiones.length, 19);
    assert(server.peticiones.every(x => x.run === null));
    assert.equal(server.peticiones.filter(x => x.metodo === 'DELETE').length, 1);
    assert.equal(server.peticiones.filter(x => x.ruta === '/sesiones/').length, 1);
    const evidencias = fs.readdirSync(temp).filter(x => /^recuperacion-\d{14}\.json$/.test(x));
    assert.equal(evidencias.length, 1);
    const d = JSON.parse(fs.readFileSync(path.join(temp, evidencias[0]), 'utf8'));
    // Misma decisión de scripts/ejecutar_autorizado.py:518-537 sobre la evidencia nueva.
    const clasificacion = d.rollback_verificado === true ? 'ROLLBACK_CONFIRMADO' : 'NO_CONCLUYENTE';
    const cierre = { solicitado: d.cierre_solicitado === true,
      confirmado: d.cierre_confirmado === true, http: d.cierre?.run?.cierre_http };
    const intento = { cierre };
    if (d.rollback_verificado === true) {
      intento.rollback = 'CONFIRMADO'; intento.estado_run = 'CERRADO';
      if (JSON.parse(fs.readFileSync(path.join(temp, 'resultado.json'))).oficial === false)
        intento.clasificacion = 'TECNICO';
    }
    assert.equal(clasificacion, esperado ? 'ROLLBACK_CONFIRMADO' : 'NO_CONCLUYENTE');
    assert.deepEqual(cierre, { solicitado: true, confirmado: true,
      http: modo === 'recuperar_delete_ya_cerrado' ? 404 : 200 });
    assert.equal(intento.rollback, esperado ? 'CONFIRMADO' : undefined);
    assert.equal(intento.estado_run, esperado ? 'CERRADO' : undefined);
    assert.equal(intento.clasificacion, esperado ? 'TECNICO' : undefined);
  } finally {
    await new Promise(ok => server.close(ok));
    fs.rmSync(temp, { recursive: true, force: true });
  }
}

let bien = 0;
for (const [modo, esperado, oficial] of modosServidor) {
  await uno(modo, esperado, oficial); bien++;
}
for (const [modo, esperado, conBase] of [
  ['recuperar_ok', true, true], ['recuperar_version_persiste', false, true],
  ['recuperar_delete_ya_cerrado', true, true], ['recuperar_sin_base_inicial', true, false],
  ['recuperar_linea_base_coincide', true, true],
  ['recuperar_id_del_run_activo', false, true],
  ['recuperar_diferencia_ajena', true, true]
]) { await ensayoRecuperar(modo, esperado, conBase); bien++; }
// El cliente siempre libera juntas ambas llamadas; este modo prueba el criterio temporal
// con una traza serializada aportada por el servidor, sin inventar un RUN remoto.
const base = { caso: 'TC-M04-166', claveCaso: LLAVES[166], previos: [], candidatos: [1, 2],
  posteriores: [{ http: 200, cuerpo: { id_version_modelo: 1, estado_version: 'DEPRECADO', esta_produccion: false } },
    { http: 200, cuerpo: { id_version_modelo: 2, estado_version: 'ACTIVO', esta_produccion: true } }],
  activos: [{ id: 2, estado: 'ACTIVO', tipo: LLAVES[166].tipo,
    componente: LLAVES[166].componente }], eventosAntes: [],
  eventosDespues: [{ tipo: 'VERSION_ACTIVADA', ref: '1', correlacion: 'a' },
    { tipo: 'VERSION_ACTIVADA', ref: '2', correlacion: 'b' },
    { tipo: 'VERSION_DEPRECADA', ref: '1', correlacion: 'b' }] };
assert.equal(decidirDisparo({ ...base, respuestas: [
  { http: 200, envio_ms: 10, respuesta_ms: 20 },
  { http: 200, envio_ms: 21, respuesta_ms: 30 }] }).estado, 'APROBADO'); bien++;
assert.equal(decidirDisparo({ ...base, respuestas: [
  { http: 200, envio_ms: 10, respuesta_ms: 30 },
  { http: 200, envio_ms: 20, respuesta_ms: 40 }] }).estado, 'RECHAZADO'); bien++;
console.log(`OK G060: ${bien}/${modosServidor.length + 9} modos; presupuesto ${PRESUPUESTO.solicitudes_normales}; registro QA fiel`);
