import assert from 'node:assert/strict';
import fs from 'node:fs';
import http from 'node:http';
import os from 'node:os';
import path from 'node:path';
import { evaluar, leerEnv } from '../g065.mjs';
import { CASOS, CAPACIDADES, PRESUPUESTO, FUENTES, OBSERVACION } from '../lib/g065_escenario.mjs';
import { clasificarRegistro } from './registro_qa.mjs';

const A = CASOS.map(() => 'APROBADO');
const cambiar = (i, estado = 'RECHAZADO') => A.map((x, j) => i === j ? estado : x);
const modos = [
  ['todo_ok', A, true],
  ['observaciones_truncadas', cambiar(0), true],
  ['sin_observaciones_bloquea', cambiar(0), true],
  ['fuente_no_persistida', cambiar(1), true],
  ['fuente_otro_422', cambiar(1), true],
  ['post5xx_199', cambiar(1), true],
  ['marca_true_con_fuente', cambiar(1), true],
  ['sin_marca_sin_fuente', cambiar(2), true],
  ['contraste_marcado', cambiar(2), true],
  ['marca_solo_en_respuesta', cambiar(2, 'NO_CONCLUYENTE'), false],
  ['fuente_invalida_201', cambiar(3), true],
  ['fuente_invalida_400', A, true],
  ['fuente_invalida_persiste', cambiar(3), true],
  ['mensaje_sin_catalogo', cambiar(3), true],
  ['datos_insuficientes', cambiar(0, 'NO_CONCLUYENTE'), false],
  ['env_archivo', A, true],
  ['login_lento', A, true],
  ['login_sin_red', CASOS.map(() => 'BLOQUEADO'), false],
  ['clave_403', CASOS.map(() => 'BLOQUEADO'), false],
  ['error5xx', CASOS.map(() => 'BLOQUEADO'), false],
  ['sin_respuesta', cambiar(3, 'NO_CONCLUYENTE').map(() => 'NO_CONCLUYENTE'), false],
  ['corte_con_cierre', cambiar(0, 'NO_CONCLUYENTE').map((x, i) => i === 1 || i === 2 ? 'NO_CONCLUYENTE' : x), false],
  ['duplicada_con_reemplazo', A, true],
  ['ventana_con_reemplazo', A, true],
  ['tipo_nulo_version', A, true],
  ['historial_segunda_pagina', A, true],
  ['newman_no_disponible', CASOS.map(() => 'BLOQUEADO'), false]
];
const leer = req => new Promise(resolve => { const partes = []; req.on('data', x => partes.push(x));
  req.on('end', () => resolve(Buffer.concat(partes).toString('utf8'))); });
const responder = (res, codigo, cuerpo, run) => { res.writeHead(codigo,
  { 'Content-Type': 'application/json', ...(run ? { 'X-Test-Run-Id': run } : {}) });
  res.end(JSON.stringify(cuerpo)); };
const id = n => `00000000-0000-4000-8000-${String(n).padStart(12, '0')}`;
function servidor(modo) {
  const cantidad = modo === 'datos_insuficientes' ? 8 : 12;
  const inferencias = Array.from({ length: cantidad }, (_, i) => ({ id_evento: id(i + 1),
    id_resultado_inferencia: id(i + 1), id_activo_biologico: 885, tipo_evento: 'INFERENCIA',
    fecha_evento: new Date(Date.now() - 86400000 + i * 60000).toISOString(),
    payload: { nivel_riesgo: i % 4, id_patologia: 10,
      tipo_modelo: modo === 'tipo_nulo_version' ? null : 'MODELO_ESPECIES_MEDIANAS',
      id_version_modelo: modo === 'tipo_nulo_version' ? 43 : null } }));
  const retros = [], auditoria = [], recibidos = [];
  let cerrado = false, deleteEnviado = false, duplicada = false, fuera = false, histErrores = 0;
  const server = http.createServer(async (req, res) => {
    const u = new URL(req.url, 'http://127.0.0.1'), run = req.headers['x-test-run-id'];
    const body = req.method === 'POST' ? JSON.parse((await leer(req)) || '{}') : {};
    if (u.pathname === '/sesiones/' && req.method === 'POST') {
      if (modo === 'login_sin_red') { req.socket.destroy(); return; }
      if (modo === 'login_lento') await new Promise(resolve => setTimeout(resolve, 150));
      return responder(res, 200, { token: `local.${Buffer.from(JSON.stringify({ sub: '900' })).toString('base64url')}.firma` });
    }
    if (u.pathname.startsWith('/test-control/runs/') && req.method === 'DELETE') {
      cerrado = true; deleteEnviado = true; return responder(res, 200, { status: 'Rollback exitoso' });
    }
    if (modo === 'clave_403' && run) return responder(res, 403, { error_code: 'CLAVE_INVALIDA' }, run);
    if (u.pathname === '/activos-biologicos') return responder(res, 200, {
      registros: [885, 886, 887].map(n => ({ id_activo_biologico: n, id_especie: 1, tipo: 'INDIVIDUAL' })),
      total_paginas: 1, total_registros: 3 }, run);
    if (u.pathname === '/prediccion/modelos/43') return responder(res, 200,
      { id_version_modelo: 43, tipo_modelo: 'MODELO_ESPECIES_MEDIANAS' }, run);
    if (u.pathname.startsWith('/prediccion/historial/')) {
      if (modo === 'error5xx' && histErrores++ < 3) return responder(res, 500, { error_code: 'ERROR_INTERNO' }, run);
      const activo = Number(u.pathname.split('/').at(-1));
      let eventos = [...inferencias.filter(x => x.id_activo_biologico === activo),
        ...(cerrado ? [] : retros.filter(x => x.id_activo_biologico === activo))];
      if (modo === 'historial_segunda_pagina') {
        const segunda = u.searchParams.has('cursor_paginacion');
        if (!segunda) return responder(res, 200, { eventos: eventos.filter(x => x.tipo_evento === 'INFERENCIA'),
          cursor_siguiente: 'segunda' }, run);
        eventos = eventos.filter(x => x.tipo_evento === 'RETROALIMENTACION');
      }
      return responder(res, 200, { eventos, cursor_siguiente: null, total_pagina: eventos.length }, run);
    }
    if (u.pathname === '/prediccion/patologias') return responder(res, 200, { total: 1,
      items: [{ id_patologia: 10, especie_aplicable: '1', es_activo: true }] }, run);
    if (u.pathname === '/prediccion/auditoria') {
      let items = auditoria.filter(x => x.tipo_evento === 'RETROALIMENTACION_REGISTRADA');
      if (u.searchParams.has('id_referencia')) items = items.filter(x =>
        x.id_referencia === u.searchParams.get('id_referencia'));
      if (modo === 'marca_solo_en_respuesta') items = items.map(x => ({ ...x,
        payload_evento: x.payload_evento.estado_retroalimentacion === 'PARCIAL'
          ? Object.fromEntries(Object.entries(x.payload_evento)
            .filter(([k]) => k !== 'es_fuente_desconocida')) : x.payload_evento }));
      return responder(res, 200, { total: items.length, items }, run);
    }
    if (u.pathname === '/prediccion/retroalimentacion' && req.method === 'POST') {
      recibidos.push(body);
      const invalid = body.fuente_diagnostico === 'RESONANCIA_MAGNETICA';
      const conFuente = !!body.fuente_diagnostico && !invalid;
      if (modo === 'duplicada_con_reemplazo' && !duplicada) {
        duplicada = true; return responder(res, 409, { error_code: 'RETROALIMENTACION_DUPLICADA' }, run);
      }
      if (modo === 'ventana_con_reemplazo' && !fuera) {
        fuera = true; return responder(res, 422, { error_code: 'FUERA_DE_VENTANA_TEMPORAL',
          message: 'Han transcurrido más de 30 días desde el resultado de inferencia.' }, run);
      }
      if ((modo === 'sin_respuesta' && invalid) || (modo === 'corte_con_cierre'
        && recibidos.length === 2)) { req.socket.destroy(); return; }
      if (modo === 'sin_observaciones_bloquea' && body.estado_retroalimentacion === 'CORRECTO'
        && !Object.hasOwn(body, 'observaciones_clinicas'))
        return responder(res, 422, { error_code: 'OBSERVACIONES_REQUERIDAS' }, run);
      if (modo === 'fuente_otro_422' && body.fuente_diagnostico === 'OTRO')
        return responder(res, 422, { error_code: 'FUENTE_DIAGNOSTICO_INVALIDA' }, run);
      if (modo === 'post5xx_199' && body.fuente_diagnostico === 'OTRO')
        return responder(res, 500, { error_code: 'ERROR_INTERNO' }, run);
      if (invalid && !['fuente_invalida_201', 'fuente_invalida_persiste'].includes(modo)) {
        const texto = modo === 'mensaje_sin_catalogo' ? 'fuente_diagnostico no válida'
          : `El valor de fuente_diagnostico no es válido. Valores permitidos: ${FUENTES.join(', ')}.`;
        return responder(res, modo === 'fuente_invalida_400' ? 400 : 422,
          { error_code: 'FUENTE_DIAGNOSTICO_INVALIDA', message: texto,
            fields: [{ field: 'fuente_diagnostico', message: texto }] }, run);
      }
      const numero = retros.length + 1, rid = id(100 + numero);
      const respuesta = { ...body, id_retroalimentacion: rid, estado_registro: 'ACTIVO',
        fecha_retroalimentacion: new Date().toISOString(), id_usuario_veterinario: 900,
        observaciones_clinicas: body.observaciones_clinicas ?? null,
        fuente_diagnostico: body.fuente_diagnostico ?? null,
        es_fuente_desconocida: !conFuente && body.estado_retroalimentacion !== 'CORRECTO' };
      if (modo === 'marca_true_con_fuente' && conFuente && recibidos.length >= 5
        && recibidos.length <= 8) respuesta.es_fuente_desconocida = true;
      if (modo === 'sin_marca_sin_fuente' && !conFuente && !invalid) respuesta.es_fuente_desconocida = false;
      if (modo === 'contraste_marcado' && body.estado_retroalimentacion === 'PARCIAL' && conFuente)
        respuesta.es_fuente_desconocida = true;
      if (modo === 'fuente_no_persistida' && conFuente && recibidos.length >= 5
        && recibidos.length <= 8) respuesta.fuente_diagnostico = null;
      const payload = { ...respuesta, id_resultado_inferencia: body.id_resultado_inferencia };
      if (modo === 'observaciones_truncadas' && body.observaciones_clinicas === OBSERVACION)
        payload.observaciones_clinicas = OBSERVACION.slice(0, -2);
      retros.push({ id_evento: rid, id_resultado_inferencia: body.id_resultado_inferencia,
        id_activo_biologico: body.id_activo_biologico, tipo_evento: 'RETROALIMENTACION',
        fecha_evento: respuesta.fecha_retroalimentacion,
        payload: { estado_retroalimentacion: body.estado_retroalimentacion,
          observaciones_clinicas: payload.observaciones_clinicas, id_usuario_veterinario: 900 } });
      auditoria.push({ tipo_evento: 'RETROALIMENTACION_REGISTRADA', id_referencia: rid,
        id_usuario: 900, payload_evento: payload });
      if (modo === 'fuente_invalida_persiste' && invalid) return responder(res, 422,
        { error_code: 'FUENTE_DIAGNOSTICO_INVALIDA',
          message: `fuente_diagnostico; Valores permitidos: ${FUENTES.join(', ')}`,
          fields: [{ field: 'fuente_diagnostico' }] }, run);
      return responder(res, 201, respuesta, run);
    }
    responder(res, 404, { error_code: 'NO_ENCONTRADO' }, run);
  });
  return { server, estado: () => ({ deleteEnviado, recibidos }) };
}

let exitosos = 0;
for (const [modo, esperado, oficial] of modos) {
  const { server, estado } = servidor(modo);
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const temporal = fs.mkdtempSync(path.join(os.tmpdir(), `g065-${modo}-`));
  const c = { version: 1, runId: 'RUN-G065-V1-20261029-000000', referencia: 'ENSAYO_LOCAL',
    operacion: 'evaluar', directorio: temporal, ensayo: true };
  try {
    let env = { SIGAB_API_TEST_BASE: `http://127.0.0.1:${server.address().port}`,
      QA_SANDBOX_SECRET: 'sandbox-local', QA_VETERINARIO_EMAIL: 'vet@local.invalid',
      QA_COMMON_PASSWORD: 'local', QA_AUTORIZADO: 'SI' };
    if (modo === 'env_archivo') {
      const archivo = path.join(temporal, '.env.qa');
      fs.writeFileSync(archivo, Object.entries(env).filter(([k]) => k !== 'QA_AUTORIZADO')
        .map(([k, v]) => `${k}=${v}`).join('\n'), 'utf8');
      env = leerEnv({ QA_AUTORIZADO: 'SI' }, archivo);
    }
    const r = await evaluar(c, { env, ...(modo === 'newman_no_disponible'
      ? { newmanVersion: { ok: false, error: 'NEWMAN_NO_DISPONIBLE' } } : {}) });
    assert.deepEqual(CASOS.map(x => r.casos[x].estado), esperado, modo);
    assert.equal(r.oficial, oficial, modo);
    if (!['login_sin_red', 'newman_no_disponible'].includes(modo)) assert.equal(estado().deleteEnviado, true, modo);
    const presentes = new Set([...fs.readdirSync(temporal),
      ...r.evidencias.filter(x => fs.existsSync(path.join(temporal, x)))]);
    assert.equal(clasificarRegistro(CAPACIDADES, r, presentes, { runId: c.runId, version: 1 }), oficial, modo);
    assert.ok(r.solicitudes.length <= PRESUPUESTO.solicitudes_totales, modo);
    assert.equal(r.cypress.total_pruebas, 0, modo);
    if (modo === 'newman_no_disponible') {
      assert.equal(r.solicitudes.length, 0);
      assert.ok(r.casos[CASOS[0]].motivo.includes('NEWMAN_NO_DISPONIBLE'));
      assert.equal(fs.existsSync(path.join(temporal, 'newman')), false);
    }
    if (modo === 'todo_ok') {
      const reportes = r.evidencias.filter(x => x.startsWith('newman/'));
      assert.equal(reportes.length, 20);
      assert.equal(r.solicitudes.filter(x => x.herramienta === 'Newman').length, 10);
      for (const relativo of reportes) {
        const archivo = path.join(temporal, relativo);
        assert.ok(fs.existsSync(archivo), relativo);
        const contenido = fs.readFileSync(archivo, 'utf8');
        for (const secreto of [env.QA_SANDBOX_SECRET, env.QA_VETERINARIO_EMAIL,
          env.QA_COMMON_PASSWORD, OBSERVACION, 'local.'])
          assert.equal(contenido.includes(secreto), false, relativo);
        assert.equal(/\w+@\w+\.\w+/.test(contenido), false, relativo);
        if (relativo.endsWith('.json')) {
          const reporte = JSON.parse(contenido);
          assert.equal(reporte.run.stats.assertions.failed, 0);
          assert.equal(reporte.run.stats.assertions.total, 2);
          assert.equal(reporte.run.executions[0].aserciones.length, 2);
        }
      }
    }
    const informe = fs.readFileSync(path.join(temporal, 'TC-M04-G065_resultado.md'), 'utf8');
    assert.ok(informe.includes('## Herramientas'), modo);
    if (modo === 'newman_no_disponible') assert.ok(informe.includes('No hubo POST evaluados con Newman'));
    assert.equal((informe.match(/### TC-M04-/g) ?? []).length, 4, modo);
    assert.equal(/^\*\*Por qué .*[Cc]oncordantes/m.test(informe), false, modo);
    if (modo === 'fuente_invalida_400') {
      assert.equal(r.incidencias.some(x => x.casos.includes('TC-M04-224')), false);
      assert.ok(informe.includes('OBS-M04-G065-224'));
      assert.ok(informe.includes('### TC-M04-224 — APROBADO'));
    }
    assert.ok(informe.includes('## Precondición de datos (semilla)'), modo);
    assert.equal(informe.includes('[filtro]'), false, modo);
    assert.equal(/[Ã�]|â[€œ]/.test(informe), false, `codificación ${modo}`);
    if (modo === 'todo_ok') assert.equal(estado().recibidos.length, 10);
    if (modo === 'login_lento') assert.ok(r.solicitudes[0].duracion_ms >= 100);
    console.log(`${modo}: ${esperado.join('/')} ${oficial ? 'OFICIAL' : 'TÉCNICO'}`);
    exitosos++;
  } finally {
    server.closeAllConnections(); await new Promise(resolve => server.close(resolve));
    fs.rmSync(temporal, { recursive: true, force: true });
  }
}
console.log(`OK G065: ${exitosos}/${modos.length} modos; presupuesto ${PRESUPUESTO.solicitudes_totales}; registro QA fiel; newman verificado`);
