import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import { CASOS, IDS, CAPACIDADES, igualCampos, evaluar009, evaluar010, operacionesCorrectivas,
  unaIncidencia, rollback, elegirCandidato, requiereRebase, datosPaso, aislarTransformacion } from '../lib/g36_core.mjs';
import { pedir, evaluar, informe, validarColeccionPermisos, sanear } from '../g36.mjs';
import { clasificarRegistro } from './registro_qa.mjs';

const modos = [];
const modo = (nombre, f) => { f(); modos.push(nombre); };
const original = { id_variacion_valor_razonable: 15, uuid: '10000000-0000-4000-8000-000000000015',
  monto_variacion: '100.00', id_variacion_corregida: null };
const linea = { id_linea_asiento_nic41: 22, cuenta_debito: '158405', cuenta_credito: '424805', valor: '100.00' };
const intento = (http = 405, mensaje = 'Use el registro correctivo') => ({ http, codigo: 'METODO_NO_PERMITIDO', mensaje });
const intentos = () => Array.from({ length: 9 }, () => intento());
const antes = { variacion: original, linea };
const despues = structuredClone(antes);
const contrato = [{ ruta: '/finanzas/variaciones/correctivos', metodo: 'POST' },
  { ruta: '/finanzas/variaciones/{id_variacion}/aprobacion', metodo: 'POST' }];
const correcto = () => evaluar010({ contrato, original,
  pendiente: { id_variacion_valor_razonable: 16, id_variacion_corregida: original.uuid, monto_variacion: '-100.00' },
  previo: { efectivo: false }, aprobado: { efectivo: true, original_visible: true, correctivo_visible: true },
  lineaOriginal: linea, lineaCorrectiva: { valor: '100.00', cuenta_debito: '424805', cuenta_credito: '158405' },
  aprobacionHttp: 200 });
modo('todo_conforme', () => {
  assert.equal(evaluar009(intentos(), antes, despues).estado, 'APROBADO');
  assert.equal(correcto().estado, 'APROBADO');
});
modo('bloqueo_sin_orientacion', () => {
  const x = evaluar009(Array.from({ length: 9 }, () => intento(405, 'Método no permitido')), antes, despues);
  assert.equal(x.estado, 'RECHAZADO'); assert.match(x.motivo, /orientaron/);
  assert.doesNotMatch(x.motivo, /Campos alterados|devolvieron 2xx/);
});
modo('modificacion_aceptada', () => {
  const x = intentos(); x[0].http = 200;
  assert.equal(evaluar009(x, antes, despues).estado, 'RECHAZADO');
});
modo('registro_alterado', () => {
  const x = structuredClone(despues); x.variacion.monto_variacion = '101.00';
  assert.equal(igualCampos(antes.variacion, x.variacion), false);
  assert.equal(evaluar009(intentos(), antes, x).estado, 'RECHAZADO');
});
modo('mecanismo_ausente', () => {
  assert.equal(evaluar010({ contrato: [] }).estado, 'RECHAZADO');
  const c = operacionesCorrectivas({ paths: { '/finanzas/periodos/{id}/variaciones': { get: {} } } });
  assert.deepEqual(c, []);
});
modo('incidencia_unica_compartida', () => {
  const x = unaIncidencia({ [CASOS[0]]: { estado: 'RECHAZADO', motivo: 'Sin orientación al correctivo' },
    [CASOS[1]]: { estado: 'RECHAZADO', motivo: 'Sin mecanismo correctivo' } });
  assert.equal(x.length, 1); assert.deepEqual(x[0].casos, CASOS);
  assert.equal(x[0].equipo_inicial, 'Desarrollo'); assert.equal(x[0].defecto_compartido, true);
  assert.match(x[0].titulo, /mecanismo correctivo/);
  assert.match(x[0].requisito, /CA-12, CA-13, Restricción 5.*CU05 FA-6/);
  assert.match(x[0].apoyo_codigo, /m06_router\.py:79-508/);
});
const respuesta = (codigo, cuerpo = {}, eco = null) => ({ status: codigo,
  headers: { get: () => eco }, json: async () => cuerpo });
const registro = () => ({ solicitudes: [], _solicitudesRun: 0, _limite: Date.now() + 900000,
  _corte: false, _seguidos5xx: 0, _secretos: [] });
const asyncModos = [
  ['lectura_5xx', async () => { const r = registro();
    await pedir(r, 'http://127.0.0.1:1', 'GET', '/lectura', { fetcher: async () => respuesta(503) });
    assert.equal(r._seguidos5xx, 1); assert.equal(r._corte, false);
    await pedir(r, 'http://127.0.0.1:1', 'GET', '/lectura', { fetcher: async () => respuesta(503) });
    await pedir(r, 'http://127.0.0.1:1', 'GET', '/lectura', { fetcher: async () => respuesta(503) });
    assert.equal(r._corte, true);
  }],
  ['corte_403', async () => { const r = registro();
    await pedir(r, 'http://127.0.0.1:1', 'GET', '/lectura', { fetcher: async () => respuesta(403) });
    const x = await pedir(r, 'http://127.0.0.1:1', 'POST', '/escritura', { fetcher: async () => respuesta(200) });
    assert.equal(r._corte, true); assert.equal(x.fallo, 'CORTE_POLITICA');
  }],
  ['delete_sin_secreto', async () => { const r = registro(); let tiene = false;
    await pedir(r, 'http://127.0.0.1:1', 'DELETE', '/test-control/runs/local', { cierre: true,
      fetcher: async (_, opts) => { tiene = Object.hasOwn(opts.headers, 'X-Sandbox-Secret'); return respuesta(403); } });
    assert.equal(tiene, false); assert.equal(r.solicitudes.at(-1).http, 403);
  }],
];
for (const [nombre, f] of asyncModos) { await f(); modos.push(nombre); }
const peticiones = [];
const runId = 'RUN-G36-V1-20261108-000000';
const env = { QA_AUTORIZADO: 'SI', SIGAB_API_TEST_BASE: 'http://127.0.0.1:1234', QA_SANDBOX_SECRET: 'secreto-local',
  QA_CONTADOR_EMAIL: 'contador@ejemplo.invalid', QA_CONTADOR_PASSWORD: 'clave-local',
  QA_ADMIN_EMAIL: 'admin@ejemplo.invalid', QA_ADMIN_PASSWORD: 'clave-local' };
const fetcher = async (url, opts) => {
  const ruta = new URL(url).pathname;
  peticiones.push({ ruta, metodo: opts.method, headers: opts.headers });
  if (ruta === '/sesiones/') return respuesta(200, { token: opts.body.includes('contador') ? 'token-contador' : 'token-admin' });
  if (ruta === '/openapi.json') return respuesta(200, { openapi: '3.1.0', paths: {
    '/finanzas/periodos/{id}/variaciones': { get: {} } } });
  if (ruta === '/finanzas/activos' || ruta === '/finanzas/periodos') return respuesta(200, [], runId);
  if (ruta === '/finanzas/configuracion') return respuesta(200, { matriz: [] }, runId);
  if (ruta === '/test-control/runs/' + runId) return respuesta(200, { cerrado: true });
  throw Error('Ruta local no prevista: ' + ruta);
};
const rEnsayo = await evaluar({ runId, version: 1, intento: 1, referencia: 'ensayo-local', ensayo: true },
  { env, fetcher, sinArtefactos: true });
modo('sin_candidato', () => {
  assert.equal(rEnsayo.casos[CASOS[0]].estado, 'BLOQUEADO');
  assert.equal(rEnsayo.casos[CASOS[1]].estado, 'RECHAZADO');
  assert.equal(rEnsayo.cierre.rollback.verificado, true);
  assert.equal(peticiones.filter(x => x.ruta === '/sesiones/').length, 2);
  assert.equal(peticiones.filter(x => x.ruta.startsWith('/test-control/runs/')).length, 1);
  assert.equal(peticiones.some(x => x.ruta.startsWith('/activos-biologicos/')), false);
  const ctx = { runId, version: 1, intento: 1, referencia: 'ensayo-local' };
  const reporte = informe(ctx, rEnsayo);
  assert.match(reporte, /^# TC-M06-G36 — RECHAZADO\n/);
  assert.match(reporte, /Contrato \/openapi\.json: HTTP 200; operaciones M06 1; operaciones correctivas ninguna; huella SHA-256 [a-f0-9]{64}\./);
  for (const [estados, titulo] of [
    [['APROBADO', 'APROBADO'], 'APROBADO'],
    [['APROBADO', 'BLOQUEADO'], 'BLOQUEADO'],
    [['APROBADO', 'NO_CONCLUYENTE'], 'NO_CONCLUYENTE'],
    [['RECHAZADO', 'APROBADO'], 'RECHAZADO']
  ]) {
    const casos = Object.fromEntries(CASOS.map((caso, i) => [caso, { estado: estados[i], motivo: 'ensayo-local' }]));
    assert.match(informe(ctx, { ...rEnsayo, casos }), new RegExp(`^# TC-M06-G36 — ${titulo}\\n`));
  }
  const observados = { creacion_http: 201, aprobacion_http: 200, original_id: 15, correctivo_id: 16,
    monto_opuesto: true, referencia_uuid: true, efectivo_antes: false, original_visible: true,
    correctivo_visible: true, linea_inversa: true };
  const conFlujo = informe(ctx, { ...rEnsayo,
    contrato: { ...rEnsayo.contrato, correctivas: [
      { ruta: '/finanzas/variaciones/correctivos', metodo: 'POST', operationId: 'crearCorrectivo' },
      { ruta: '/finanzas/variaciones/{id}/aprobacion', metodo: 'POST', operationId: 'aprobarCorrectivo' }] },
    casos: { ...rEnsayo.casos, [CASOS[1]]: { ...rEnsayo.casos[CASOS[1]], observados } } });
  assert.match(conFlujo, /crearCorrectivo \(POST\); aprobarCorrectivo \(POST\)/);
  assert.match(conFlujo, /Flujo correctivo: creación HTTP 201, aprobación HTTP 200/);
  assert.match(conFlujo, /efectivo antes false, original visible true/);
  assert.equal(conFlujo.includes(JSON.stringify(observados)), false);
  assert.doesNotMatch(conFlujo, /"creacion_http"\s*:/);
});
modo('plantilla_informe_incidente', () => {
  const ctx = { runId, version: 1, intento: 1, referencia: 'ensayo-local' };
  const intentos = ['/finanzas/variaciones/249', '/finanzas/periodos/8/variaciones/249', '/finanzas/lineas/892']
    .flatMap(ruta => ['PUT', 'PATCH', 'DELETE'].map(metodo => ({ metodo, ruta, http: 404, codigo: '', mensaje: 'Not Found' })));
  const huella = { campos: ['id'], sha256_antes: 'abc', sha256_despues: 'abc' };
  const casos = {
    [CASOS[0]]: { estado: 'RECHAZADO', motivo: '9 respuestas no orientaron al correctivo.',
      observados: { intentos, bloqueados: 9, orientados: 0, campos_alterados: [] },
      comparacion_campo_a_campo: { variacion: huella, linea: huella } },
    [CASOS[1]]: { estado: 'RECHAZADO', motivo: 'Sin operaciones públicas para crear y aprobar correctivo.' }
  };
  const preparacion = { activo_id: 945, periodo_id: 8, precio_id: 18, rebase: false,
    evento_id: 1286, variacion_id: 249, linea_id: 892 };
  const incidencias = unaIncidencia(casos, { preparacion, contrato: rEnsayo.contrato, newman: true });
  const reporte = informe(ctx, { ...rEnsayo, casos, preparacion, incidencias, oficial: true });
  assert.match(reporte, /9 intentos PUT, PATCH y DELETE.*todos HTTP 404 Not Found, sin código de error ni mensaje/);
  assert.match(reporte, /SHA-256 idéntica antes y después/);
  assert.match(reporte, /CA-12:.*orientaron al correctivo/);
  assert.match(reporte, /CA-13:.*crear y aprobar correctivo/);
  assert.match(reporte, /\*\*Pasos para reproducir:\*\*/);
  assert.match(reporte, /\*\*Apoyo de código leído, sin atribución causal:\*\*/);
  assert.match(reporte, /\*\*Impacto y severidad:\*\* ALTA/);
  assert.match(reporte, /Ambos incumplimientos se agrupan en una sola incidencia/);
  assert.equal((reporte.match(/### INC-M06-G36-/g) ?? []).length, 1);
});
modo('newman_actores', () => {
  const col = JSON.parse(fs.readFileSync(new URL('../G36.postman_collection.json', import.meta.url), 'utf8'));
  assert.equal(validarColeccionPermisos(col), true);
  for (let i = 0; i < col.item.length; i++) {
    const malo = structuredClone(col);
    if (i < 2) malo.item[i].request.header.find(x => x.key === 'Authorization').value = 'Bearer {{otro}}';
    else malo.item[i].request.header.push({ key: 'Authorization', value: 'Bearer {{otro}}' });
    assert.equal(validarColeccionPermisos(malo), false);
  }
});
modo('registro_qa_fiel', () => {
  const presentes = new Set(['resultado.json', 'TC-M06-G36_resultado.md',
    'newman/newman-G36.json', 'newman/newman-G36.html']);
  const r = { run_id: 'RUN-G36-V1-20261108-000000', version: 1, oficial: true, consume_version: true,
    casos: Object.fromEntries(CASOS.map(c => [c, { estado: 'RECHAZADO' }])),
    cierre: { run: { cierre_http: 200 }, rollback: { verificado: true } },
    herramientas: { newman: { iteraciones: 1 } }, cypress: { total_pruebas: 0 },
    comprobaciones: CASOS.flatMap(c => IDS[c].map(id => ({ caso: c, fuente: 'API', id, tipo: 'ASSERT',
      estado: 'RECHAZADO', evidencia: 'resultado.json' }))), evidencias: [...presentes] };
  const ctx = { runId: r.run_id, version: 1 };
  assert.equal(clasificarRegistro(CAPACIDADES, r, presentes, ctx), true);
  r.comprobaciones[0].caso = 'TC-M06-G36 / TC-M06-009';
  assert.equal(clasificarRegistro(CAPACIDADES, r, presentes, ctx), false);
});
modo('sin_residuos', () => {
  const base = { completa: true, estado: 'ACTIVO', peso: 100, eventos: [], variaciones: [],
    lineas: [], calculos: [], auditoria: [] };
  assert.equal(rollback(base, structuredClone(base), [], null, null).verificado, true);
  assert.equal(fs.readdirSync(os.tmpdir()).filter(x => x.startsWith('g36-newman-')).length, 0);
});
const elegible = (activo, precioPrevio, precioActual) => ({ fila: { activo_id: activo },
  calc: { id_precio_mercado: precioPrevio, magnitud: 345 },
  precio: { id_precio_mercado: precioActual }, peso: 345 });
modo('preferir_precio_vigente', () => {
  const candidatos = [elegible(943, 17, 18), elegible(945, 18, 18)];
  assert.equal(elegirCandidato(candidatos), candidatos[1]);
  assert.equal(requiereRebase(candidatos[1]), false);
  assert.match(candidatos[0].fila.motivo, /rebase/);
  assert.equal(candidatos[1].fila.estado, 'SELECCIONADO');
  const soloRebase = [elegible(1, 17, 18), elegible(2, 16, 18)];
  assert.equal(elegirCandidato(soloRebase), soloRebase[0]);
  assert.equal(requiereRebase(soloRebase[0]), true);
});
const snap = (variaciones = [], lineas = [], mediciones = []) =>
  ({ completa: true, variaciones, lineas, mediciones });
const variacionTB = { id_variacion_valor_razonable: 71, id_activo_biologico: 945,
  tipo: 'GANANCIA_TRANSFORMACION_BIOLOGICA', monto_variacion: '20.00', id_linea: 81,
  estado_trazabilidad: 'PENDIENTE' };
const lineaTB = { id_linea_asiento_nic41: 81, id_activo_biologico: 945,
  tabla_origen: 'variaciones_valor_razonable', id_origen: 71, id_periodo_contable: 8,
  tipo_hecho: 'VARIACION_VR_TB', valor: '20.00', estado: 'PENDIENTE' };
const medicionTB = { id_medicion_posterior: 91, id_evento: 601,
  id_periodo_contable: 8, origen_medicion: 'EVENTO_M02', variacion_total: '20.00' };
modo('rebase_luego_pesaje', () => {
  const base = snap();
  const rebase = snap([{ ...variacionTB, id_variacion_valor_razonable: 70, id_linea: 80 }],
    [{ ...lineaTB, id_linea_asiento_nic41: 80, id_origen: 70 }],
    [{ ...medicionTB, id_medicion_posterior: 90, id_evento: 600 }]);
  const pesaje = snap([...rebase.variaciones, variacionTB], [...rebase.lineas, lineaTB],
    [...rebase.mediciones, medicionTB]);
  assert.equal(aislarTransformacion(rebase, pesaje, 945, 601).variacion.id_variacion_valor_razonable, 71);
  assert.equal(datosPaso(rebase, base, 945).variaciones[0].id, 70);
  assert.equal(datosPaso(pesaje, rebase, 945).variaciones[0].id_linea, 81);
  assert.equal(datosPaso(pesaje, rebase, 945).mediciones[0].id_evento, 601);
});
modo('variacion_ausente_tras_pesaje', () => {
  const pre = snap(); const post = snap([], [], [medicionTB]);
  const aislada = aislarTransformacion(pre, post, 945, 601);
  assert.equal(aislada.estado, 'NO_CONCLUYENTE');
  assert.match(aislada.motivo, /ganancias TB nuevas 0/);
  assert.deepEqual(datosPaso(post, pre, 945).variaciones, []);
});
modo('run_id_sin_redactar', () => {
  const entrada = 'RUN-G36-V1-20261108-160315 AUT-G36-V1-20261108 2026-11-08 activo 945 contador@ejemplo.invalid secreto-local';
  const salida = sanear(entrada, ['secreto-local']);
  assert.match(salida, /RUN-G36-V1-20261108-160315 AUT-G36-V1-20261108 2026-11-08 activo 945/);
  assert.doesNotMatch(salida, /contador@ejemplo.invalid|secreto-local/);
  assert.match(salida, /\[CORREO_REDACTADO\].*\[REDACTADO\]/);
  const datos = JSON.parse(sanear('{"run_id":"RUN-G36-V1-20261108-160315","id":945,"numero_id_tributaria":"123456789"}'));
  assert.equal(datos.run_id, 'RUN-G36-V1-20261108-160315');
  assert.equal(datos.id, 945);
  assert.equal(datos.numero_id_tributaria, '[DATO_PERSONAL_REDACTADO]');
});
assert.equal(modos.length, 18);
console.log(`OK G36: ${modos.length}/${modos.length} modos; aislamiento y cierre comprobados; registro QA fiel`);
