import assert from 'node:assert/strict';
import fs from 'node:fs';
import http from 'node:http';
import os from 'node:os';
import path from 'node:path';
import { evaluar, leerEnv } from '../g064.mjs';
import { CASOS, CAPACIDADES, PRESUPUESTO } from '../lib/g064_escenario.mjs';
import { clasificarRegistro } from './registro_qa.mjs';

const A = CASOS.map(() => 'APROBADO');
const inferenciaReciente = '00000000-0000-4000-8000-000000000005';
const cambiar = (i, estado = 'RECHAZADO') => A.map((x, j) => i === j ? estado : x);
const modos = [
  ['todo_ok', A, true],
  ['correcto_con_diagnostico_devuelto', cambiar(0), true],
  ['correcto_sin_estado_registro', cambiar(0), true],
  ['correcto_200', cambiar(0), true],
  ['sin_evento_422', cambiar(1), true],
  ['sin_evento_sin_resultado_con_riesgo', A, true],
  ['parcial_pierde_principal', cambiar(2), true],
  ['parcial_422', cambiar(2), true],
  ['incorrecto_422', cambiar(3), true],
  ['incorrecto_5xx', cambiar(3), true],
  ['datos_insuficientes_197', cambiar(3, 'NO_CONCLUYENTE'), false],
  ['duplicada_409_con_reemplazo', A, true],
  ['campo_falso_positivo_ausente', A, true],
  ['env_archivo', A, true],
  ['login_lento', A, true],
  ['login_sin_red', CASOS.map(() => 'BLOQUEADO'), false],
  ['clave_403', CASOS.map(() => 'BLOQUEADO'), false],
  ['error5xx', CASOS.map(() => 'BLOQUEADO'), false],
  ['sin_respuesta', cambiar(3, 'NO_CONCLUYENTE'), false],
  ['corte_con_cierre', cambiar(3, 'NO_CONCLUYENTE'), false],
  ['correcto_estado_incorrecto', cambiar(0), true],
  ['sin_evento_estado_incorrecto', cambiar(1), true],
  ['parcial_estado_incorrecto', cambiar(2), true],
  ['incorrecto_estado_incorrecto', cambiar(3), true],
  ['sin_auditoria_196', cambiar(2), true],
  ['sin_persistencia_195', cambiar(1), true],
  ['correcto_timestamp_anterior', cambiar(0), true],
  ['ventana_configurada_30', A, true],
  ['resultados_solo_antiguos', CASOS.map(() => 'NO_CONCLUYENTE'), false],
  ['post_fuera_de_ventana_con_reemplazo', A, true],
  ['retro_en_segunda_pagina', A, true],
  ['eventos_solo_alertas', CASOS.map(() => 'NO_CONCLUYENTE'), false],
  ['tipo_modelo_nulo_con_version_individual', A, true],
  ['inferencias_en_segunda_pagina', A, true],
  ['newman_no_disponible', CASOS.map(() => 'BLOQUEADO'), false]
];
const leer = req => new Promise(resolve => { const partes = [];
  req.on('data', x => partes.push(x)); req.on('end', () => resolve(Buffer.concat(partes).toString('utf8')));
});
const responder = (res, codigo, cuerpo, run) => {
  res.writeHead(codigo, { 'Content-Type': 'application/json', ...(run ? { 'X-Test-Run-Id': run } : {}) });
  res.end(JSON.stringify(cuerpo));
};
function servidor(modo) {
  const inferencias = Array.from({ length: modo === 'eventos_solo_alertas' ? 0
    : modo === 'datos_insuficientes_197' ? 3 : 5 }, (_, i) => ({
    id_evento: `00000000-0000-4000-8000-${String(i + 1).padStart(12, '0')}`,
    id_resultado_inferencia: `00000000-0000-4000-8000-${String(i + 1).padStart(12, '0')}`,
    id_activo_biologico: modo === 'inferencias_en_segunda_pagina' ? 101 : 101 + i,
    tipo_evento: 'INFERENCIA',
    fecha_evento: new Date(Date.now() - (modo === 'resultados_solo_antiguos' ? 100
      : modo === 'ventana_configurada_30' ? 20 : 1) * 86400000
      + (modo === 'ventana_configurada_30' ? i * 3600000 : 0)).toISOString(),
    payload: { nivel_riesgo: modo === 'sin_evento_sin_resultado_con_riesgo' ? 0 : i === 0 ? 0 : 2,
      id_patologia: 10,
      tipo_modelo: modo === 'tipo_modelo_nulo_con_version_individual' ? null : 'MODELO_ESPECIES_MEDIANAS',
      id_version_modelo: modo === 'tipo_modelo_nulo_con_version_individual' ? 7 : null } }));
  const retros = [], auditoria = [], rangos = []; let cerrado = false, deleteEnviado = false, historial5xx = 0,
    duplicada = false, fuera = false;
  const server = http.createServer(async (req, res) => {
    const u = new URL(req.url, 'http://127.0.0.1'), run = req.headers['x-test-run-id'];
    const body = req.method === 'POST' ? JSON.parse((await leer(req)) || '{}') : {};
    if (u.pathname === '/sesiones/' && req.method === 'POST') {
      if (modo === 'login_sin_red') { req.socket.destroy(); return; }
      if (modo === 'login_lento') await new Promise(resolve => setTimeout(resolve, 150));
      return responder(res, 200, { token: `local.${Buffer.from(JSON.stringify({ sub: '900' })).toString('base64url')}.firma` });
    }
    if (u.pathname.startsWith('/test-control/runs/') && req.method === 'DELETE') {
      deleteEnviado = true; cerrado = true; return responder(res, 200, { status: 'Rollback exitoso' });
    }
    if (modo === 'clave_403' && run) return responder(res, 403, { error_code: 'CLAVE_INVALIDA' }, run);
    if (u.pathname === '/activos-biologicos') {
      const ids = modo === 'eventos_solo_alertas' ? [101]
        : [...new Set(inferencias.map(x => x.id_activo_biologico))];
      return responder(res, 200, { registros: ids.map(id => ({ id_activo_biologico: id,
        id_especie: 1, tipo: 'INDIVIDUAL' })), total_paginas: 1, total_registros: ids.length }, run);
    }
    if (u.pathname === '/prediccion/modelos/7') return responder(res, 200,
      { id_version_modelo: 7, tipo_modelo: 'MODELO_ESPECIES_MEDIANAS' }, run);
    if (u.pathname.startsWith('/prediccion/historial/')) {
      if (modo === 'error5xx' && historial5xx++ < 3) return responder(res, 500, { error_code: 'ERROR_INTERNO' }, run);
      const activo = Number(u.pathname.split('/').at(-1));
      rangos.push({ inicio: u.searchParams.get('fecha_inicio'), cursor: u.searchParams.get('cursor_paginacion') });
      const eventos = [...inferencias.filter(x => x.id_activo_biologico === activo
        && x.fecha_evento.slice(0, 10) >= u.searchParams.get('fecha_inicio')),
        ...(cerrado ? [] : retros.filter(x => x.id_activo_biologico === activo))];
      if ((modo === 'eventos_solo_alertas' || modo === 'inferencias_en_segunda_pagina')
        && retros.length === 0) {
        const segunda = u.searchParams.get('cursor_paginacion') === 'segunda-pagina';
        const alertas = Array.from({ length: 50 }, (_, i) => ({ tipo_evento: 'ALERTA',
          id_evento: `a${i}`, id_resultado_inferencia: `a${i}`, fecha_evento: new Date().toISOString() }));
        return responder(res, 200, { eventos: segunda
          ? modo === 'eventos_solo_alertas' ? [] : eventos
          : alertas, cursor_siguiente: segunda ? null : 'segunda-pagina' }, run);
      }
      if (modo === 'retro_en_segunda_pagina') {
        const segunda = u.searchParams.get('cursor_paginacion') === 'segunda-pagina';
        return responder(res, 200, { eventos: segunda ? eventos.filter(x => x.tipo_evento === 'RETROALIMENTACION')
          : eventos.filter(x => x.tipo_evento === 'INFERENCIA'),
        cursor_siguiente: segunda ? null : 'segunda-pagina' }, run);
      }
      return responder(res, 200, { eventos: modo === 'sin_persistencia_195' && !cerrado
        ? eventos.filter(x => !(x.tipo_evento === 'RETROALIMENTACION' && x.payload.estado_retroalimentacion === 'SIN_EVENTO'))
        : eventos, cursor_siguiente: null, total_pagina: eventos.length }, run);
    }
    if (u.pathname === '/prediccion/patologias') return responder(res, 200, { total: 2, items: [
      { id_patologia: 10, especie_aplicable: '1', es_activo: true },
      { id_patologia: 11, especie_aplicable: '1', es_activo: true } ] }, run);
    if (u.pathname === '/prediccion/auditoria') return responder(res, 200, { total: auditoria.length,
      items: modo === 'sin_auditoria_196' ? auditoria.filter(x => x.payload_evento.estado_retroalimentacion !== 'PARCIAL')
        : auditoria.filter(x => x.id_referencia === u.searchParams.get('id_referencia')) }, run);
    if (u.pathname === '/prediccion/retroalimentacion' && req.method === 'POST') {
      const n = retros.length + 194;
      if (modo === 'ventana_configurada_30') {
        const inferencia = inferencias.find(x => x.id_resultado_inferencia === body.id_resultado_inferencia);
        if (inferencia && Date.now() - Date.parse(inferencia.fecha_evento) > 30 * 86400000)
          return responder(res, 422, { error_code: 'FUERA_DE_VENTANA_TEMPORAL',
            message: 'Han transcurrido más de 30 días desde el resultado de inferencia.' }, run);
      }
      if (modo === 'duplicada_409_con_reemplazo' && !duplicada) {
        duplicada = true; return responder(res, 409, { error_code: 'RETROALIMENTACION_DUPLICADA' }, run);
      }
      if (modo === 'post_fuera_de_ventana_con_reemplazo' && !fuera) {
        fuera = true; return responder(res, 422, { error_code: 'FUERA_DE_VENTANA_TEMPORAL',
          message: 'Han transcurrido más de 30 días desde el resultado de inferencia.' }, run);
      }
      if ((modo === 'sin_respuesta' || modo === 'corte_con_cierre') && body.estado_retroalimentacion === 'INCORRECTO') {
        req.socket.destroy(); return;
      }
      const errores = { sin_evento_422: 'SIN_EVENTO', parcial_422: 'PARCIAL', incorrecto_422: 'INCORRECTO' };
      if (errores[modo] === body.estado_retroalimentacion)
        return responder(res, 422, { error_code: 'REGLA_NEGOCIO' }, run);
      if (modo === 'incorrecto_5xx' && body.estado_retroalimentacion === 'INCORRECTO')
        return responder(res, 500, { error_code: 'ERROR_INTERNO' }, run);
      if (modo === 'correcto_200' && body.estado_retroalimentacion === 'CORRECTO')
        return responder(res, 200, { ...body, estado_registro: 'ACTIVO' }, run);
      const id = `10000000-0000-4000-8000-${String(retros.length + 1).padStart(12, '0')}`;
      const respuesta = { ...body, id_retroalimentacion: id, estado_registro: 'ACTIVO',
        fecha_retroalimentacion: new Date().toISOString(), id_usuario_veterinario: 900,
        es_fuente_desconocida: body.diagnosticos_reales != null };
      if (modo === 'correcto_con_diagnostico_devuelto' && body.estado_retroalimentacion === 'CORRECTO')
        respuesta.diagnosticos_reales = [10];
      if (modo === 'correcto_sin_estado_registro' && body.estado_retroalimentacion === 'CORRECTO')
        delete respuesta.estado_registro;
      if (modo === 'correcto_timestamp_anterior' && body.estado_retroalimentacion === 'CORRECTO')
        respuesta.fecha_retroalimentacion = new Date(Date.now() - 9 * 86400000).toISOString();
      if (modo === 'parcial_pierde_principal' && body.estado_retroalimentacion === 'PARCIAL')
        respuesta.diagnosticos_reales = [11];
      if (modo.endsWith('_estado_incorrecto') && modo.startsWith(body.estado_retroalimentacion.toLowerCase()))
        respuesta.estado_retroalimentacion = 'OTRO';
      retros.push({ id_evento: id, id_resultado_inferencia: body.id_resultado_inferencia,
        id_activo_biologico: body.id_activo_biologico, tipo_evento: 'RETROALIMENTACION',
        fecha_evento: respuesta.fecha_retroalimentacion,
        payload: { estado_retroalimentacion: body.estado_retroalimentacion } });
      auditoria.push({ tipo_evento: 'RETROALIMENTACION_REGISTRADA', id_referencia: id,
        id_usuario: 900, payload_evento: { estado_retroalimentacion: body.estado_retroalimentacion } });
      return responder(res, 201, respuesta, run);
    }
    responder(res, 404, { error_code: 'NO_ENCONTRADO' }, run);
  });
  return { server, estado: () => ({ deleteEnviado, rangos }) };
}

let exitosos = 0;
for (const [modo, esperado, oficial] of modos) {
  const { server, estado } = servidor(modo);
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const temporal = fs.mkdtempSync(path.join(os.tmpdir(), `g064-${modo}-`));
  const c = { version: 1, runId: `RUN-G064-V1-20261029-000000`, referencia: 'ENSAYO_LOCAL',
    operacion: 'evaluar', directorio: temporal, ensayo: true };
  try {
    let env = { SIGAB_API_TEST_BASE: `http://127.0.0.1:${server.address().port}`,
      QA_SANDBOX_SECRET: 'sandbox-local', QA_VETERINARIO_EMAIL: 'vet@local.invalid',
      QA_COMMON_PASSWORD: 'clave-local', QA_AUTORIZADO: 'SI' };
    if (modo === 'env_archivo') {
      const archivo = path.join(temporal, '.env.qa');
      fs.writeFileSync(archivo, Object.entries(env).filter(([k]) => k !== 'QA_AUTORIZADO')
        .map(([k, v]) => `${k}=${v}`).join('\n'), 'utf8');
      env = leerEnv({ QA_AUTORIZADO: 'SI' }, archivo);
    }
    const r = await evaluar(c, { env, ...(modo === 'newman_no_disponible'
      ? { newmanVersion: { ok: false, error: 'NEWMAN_NO_DISPONIBLE' } } : {}) });
    assert.deepEqual(CASOS.map(x => r.casos[x].estado), esperado, modo);
    assert.equal(r.oficial, oficial, `${modo}: ${JSON.stringify({ casos: r.casos, post: r.solicitudes.filter(x => x.metodo === 'POST'), observaciones: r.observaciones })}`);
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
      assert.equal(reportes.length, 8);
      for (const relativo of reportes) {
        const archivo = path.join(temporal, relativo);
        assert.ok(fs.existsSync(archivo), relativo);
        const contenido = fs.readFileSync(archivo, 'utf8');
        for (const secreto of [env.QA_SANDBOX_SECRET, env.QA_VETERINARIO_EMAIL,
          env.QA_COMMON_PASSWORD, 'local.']) assert.equal(contenido.includes(secreto), false, relativo);
        assert.equal(/\w+@\w+\.\w+/.test(contenido), false, relativo);
        if (relativo.endsWith('.json')) {
          const reporte = JSON.parse(contenido);
          assert.equal(reporte.run.executions[0].http, 201);
          assert.equal(reporte.run.stats.assertions.failed, 0);
          assert.ok(reporte.run.stats.assertions.total >= 3);
        }
      }
      assert.ok(r.solicitudes.filter(x => x.herramienta === 'Newman').length === 4);
    }
    const informe = fs.readFileSync(path.join(temporal, 'TC-M04-G064_resultado.md'), 'utf8');
    assert.equal((informe.match(/### TC-M04-/g) ?? []).length, 4);
    assert.ok(informe.includes('## Herramientas'), modo);
    if (modo === 'newman_no_disponible') assert.ok(informe.includes('No hubo POST evaluados con Newman'));
    assert.equal(/[Ã�]|â[€œ]/.test(informe), false, `codificación ${modo}`);
    assert.ok(informe.includes('## Precondición de datos (semilla)'), modo);
    assert.equal(informe.includes('[filtro]'), false, modo);
    assert.equal(/\*\*Por qué [^\n]+persistencia y auditoría verificadas/i.test(informe), false, modo);
    if (modo === 'sin_evento_sin_resultado_con_riesgo')
      assert.ok(r.observaciones.some(x => x.includes('riesgo mayor que cero')));
    if (modo === 'login_lento') assert.ok(r.solicitudes[0].duracion_ms >= 100);
    if (modo === 'ventana_configurada_30') {
      assert.ok(estado().rangos.length >= 5);
      assert.equal(r.datos_elegidos['TC-M04-194'].id_resultado_inferencia,
        inferenciaReciente);
      assert.equal(estado().rangos[0].inicio,
        new Intl.DateTimeFormat('en-CA', { timeZone: 'America/Bogota', year: 'numeric',
          month: '2-digit', day: '2-digit' }).format(new Date(Date.now() - 88 * 86400000)));
    }
    if (modo === 'resultados_solo_antiguos') assert.equal(r.solicitudes.some(x => x.metodo === 'POST'
      && x.ruta === '/prediccion/retroalimentacion'), false);
    if (modo === 'post_fuera_de_ventana_con_reemplazo') {
      assert.ok(r.observaciones.some(x => x.includes('ventana vencida (422)')));
      assert.equal(r.solicitudes.filter(x => x.metodo === 'POST'
        && x.ruta === '/prediccion/retroalimentacion').length, 5);
    }
    if (modo === 'retro_en_segunda_pagina') assert.ok(estado().rangos.some(x => x.cursor === 'segunda-pagina'));
    if (modo === 'eventos_solo_alertas') {
      assert.equal(r.diagnostico_seleccion.agregado.por_tipo_evento.ALERTA, 50);
      assert.equal(r.diagnostico_seleccion.agregado.por_tipo_evento.INFERENCIA, 0);
      assert.ok(r.casos['TC-M04-194'].motivo.includes('50 eventos'));
      assert.ok(informe.includes('50 eventos'));
    }
    if (modo === 'tipo_modelo_nulo_con_version_individual') {
      assert.equal(r.diagnostico_seleccion.tipos_recuperados, 1);
      assert.equal(r.datos_elegidos['TC-M04-194'].tipo_modelo, 'MODELO_ESPECIES_MEDIANAS');
    }
    if (modo === 'inferencias_en_segunda_pagina') {
      assert.ok(estado().rangos.some(x => x.cursor === 'segunda-pagina'));
      assert.equal(r.diagnostico_seleccion.historiales[0].resumen.eventos, 55);
    }
    console.log(`${modo}: ${esperado.join('/')} ${oficial ? 'OFICIAL' : 'TÉCNICO'}`);
    exitosos++;
  } finally {
    server.closeAllConnections();
    await new Promise(resolve => server.close(resolve));
    fs.rmSync(temporal, { recursive: true, force: true });
  }
}
console.log(`OK G064: ${exitosos}/${modos.length} modos; presupuesto ${PRESUPUESTO.solicitudes_totales}; registro QA fiel; newman verificado`);
