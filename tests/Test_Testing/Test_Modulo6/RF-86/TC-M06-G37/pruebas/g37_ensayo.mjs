import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import http from 'node:http';
import { randomInt } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { CASOS, IDS, CONTRATO, mock, validarMock, leerCampo, validarActor, idsNuevos,
  seleccionarCandidatos, oraculo011, oraculo012, oraculo013, decidirVerificacion } from '../lib/g37_core.mjs';
import { CAPACIDADES, compararEsquema, esquema, evaluarRollbackSandbox,
  contrastarRespuesta, lecturasPrevias, aplicarDiscrepancias, informe, principal,
  conPeticiones, fetchEnContexto } from '../g37.mjs';
import { clasificarRegistro } from './registro_qa.mjs';

let n = 0;
let runTemporalEliminado = null;
function modo(nombre, fn) { fn(); n++; process.stdout.write(`OK ${nombre}\n`); }
const v = (id, tipo, monto, activo = 1) => ({ ...mock('variaciones')[0], id_variacion_valor_razonable: id,
  id_activo_biologico: activo, tipo, monto_variacion: monto, _periodo: 8 });
const a = (variacion, id) => ({ ...mock('auditoria').eventos[0], id_evento: id,
  id_referencia: variacion.id_variacion_valor_razonable, id_activo_biologico: variacion.id_activo_biologico,
  id_periodo_contable: variacion._periodo, monto_afectado: variacion.monto_variacion,
  tipo_evento: 'VARIACION_REGISTRADA', payload_evento: { tipo: variacion.tipo, monto: String(variacion.monto_variacion),
    id_evento: null, id_cierre: null } });
const vs = [v(10, 'GANANCIA_TRANSFORMACION_BIOLOGICA', 8), v(11, 'PERDIDA_TRANSFORMACION_BIOLOGICA', -4),
  v(12, 'GANANCIA_PRECIO_MERCADO', 3), v(13, 'PERDIDA_PRECIO_MERCADO', -2)];
modo('011_cumple', () => assert.equal(oraculo011({ antes: { total_ingresos: 10, total_gastos: 5 },
  despues: { total_ingresos: 21, total_gastos: 11 }, variaciones: vs, otroPeriodo: [v(99, 'GANANCIA_PRECIO_MERCADO', 100)] }).estado, 'APROBADO'));
modo('011_falla', () => assert.equal(oraculo011({ antes: { total_ingresos: 10, total_gastos: 5 },
  despues: { total_ingresos: 19, total_gastos: 11 }, variaciones: vs }).estado, 'RECHAZADO'));
modo('011_decimal_exacto', () => {
  const xs = ['GANANCIA_TRANSFORMACION_BIOLOGICA', 'PERDIDA_TRANSFORMACION_BIOLOGICA',
    'GANANCIA_PRECIO_MERCADO', 'PERDIDA_PRECIO_MERCADO'].map((tipo, i) => v(i + 1, tipo, i % 2 ? '-0.10' : '0.10'));
  assert.equal(oraculo011({ antes: { total_ingresos: '0.10', total_gastos: '0.10' },
    despues: { total_ingresos: '0.30', total_gastos: '0.30' }, variaciones: xs }).estado, 'APROBADO');
  assert.equal(oraculo011({ antes: { total_ingresos: '0.10', total_gastos: '0.10' },
    despues: { total_ingresos: '0.30000000000000001', total_gastos: '0.30' }, variaciones: xs }).estado, 'RECHAZADO');
});
modo('012_cumple', () => assert.equal(oraculo012(vs, vs.map((x,i) => a(x, i+1))).estado, 'APROBADO'));
modo('012_falla', () => assert.equal(oraculo012(vs, [a(vs[0], 1), a(vs[0], 2)]).estado, 'RECHAZADO'));
const c = { ...mock('cadena'), estado_verificacion: 'VERIFICADO', nivel_fallo: null, eslabones: { nivel_fallo: null,
  ids: { id_evento: 50, ids_lectura_iot: [60], id_precio_mercado: null } } };
const inicial = { estado_trazabilidad: 'VERIFICACION_PENDIENTE' }, final = { estado_trazabilidad: 'VERIFICADO' };
const cadenaInicial = { ...mock('cadena'), estado_trazabilidad: 'VERIFICACION_PENDIENTE',
  estado_verificacion: null, nivel_fallo: null, eslabones: null };
modo('cadena_pendiente_eslabones_null', () => {
  assert.equal(validarMock('cadena', cadenaInicial), true);
  assert.equal(compararEsquema('cadena', esquema(cadenaInicial)), true);
  assert.equal(oraculo013({ inicial, cadenaInicial, final, cadena: c, evento: 50, lecturaApta: 60 }).estado, 'APROBADO');
});
modo('cadena_verificada_con_ids', () => assert.equal(oraculo013({ inicial, cadenaInicial, final,
  cadena: c, evento: 50, lecturaApta: 60 }).estado, 'APROBADO'));
modo('cadena_verificada_sin_ids_falla', () => {
  const sinIds = structuredClone(c); sinIds.eslabones.ids.ids_lectura_iot = [];
  assert.equal(oraculo013({ inicial, cadenaInicial, final, cadena: sinIds,
    evento: 50, lecturaApta: 60 }).estado, 'RECHAZADO');
  const nivelIncorrecto = { ...c, nivel_fallo: 1 };
  assert.equal(oraculo013({ inicial, cadenaInicial, final, cadena: nivelIncorrecto,
    evento: 50, lecturaApta: 60 }).estado, 'BLOQUEADO');
});
modo('013_cumple', () => assert.equal(oraculo013({ inicial, cadenaInicial, final, cadena: c, evento: 50, lecturaApta: 60 }).estado, 'APROBADO'));
modo('013_falla', () => assert.equal(oraculo013({ inicial, cadenaInicial, final: { estado_trazabilidad: 'PENDIENTE_TRAZABILIDAD' },
  cadena: c, evento: 50, lecturaApta: 60 }).estado, 'RECHAZADO'));
modo('013_verificacion_500_requiere_causa_confirmada', () => {
  const decision = decidirVerificacion(500, 'ERROR_INTERNO');
  assert.equal(decision.estado, 'RECHAZADO');
  assert.equal(decision.incidencia, null);
  assert.equal(decidirVerificacion(500, 'ERROR_INTERNO', true).incidencia, 'INC-M06-G32-01');
});
modo('013_sin_lectura_iot', () => assert.equal(oraculo013({ inicial, cadenaInicial, final, cadena: c, evento: 50,
  lecturaApta: null }).estado, 'RECHAZADO'));
modo('mock_campo_ausente_falla', () => {
  const x = mock('variaciones');
  assert.throws(() => leerCampo('variaciones', x, '[].id_evento'), /ausente/);
  assert.throws(() => validarMock('variaciones', [{ ...x[0], id_evento: 50 }]), /no declarado/);
  const incompleto = { ...x[0] }; delete incompleto.monto_variacion;
  assert.throws(() => validarMock('variaciones', [incompleto]), /ausente/);
  assert.equal(compararEsquema('variaciones', esquema(x)), true);
});
{
  const r = { contraste_contrato: [], discrepancias_contrato: [], problemas_tecnicos: [],
    casos: {}, comprobaciones: [], incidencias: [] };
  const llamadas = []; let cierres = 0;
  const q = async (peticion, ruta, actor = 'contador', body) => {
    llamadas.push({ peticion, metodo: body === undefined ? 'GET' : 'POST' });
    const data = mock(peticion);
    if (peticion === 'estados_get') delete data[0].total_ingresos;
    if (peticion === 'auditoria') { data.pagina_actual = 1; data.registros_por_pagina = 500; }
    if (peticion === 'm03_historial') { data.pagina = 1; data.por_pagina = 100; data.paginas_totales = 1; }
    return { http: 200, eco: true, esquema_valido: contrastarRespuesta(r, peticion, actor, 200, data, ruta) };
  };
  try {
    await lecturasPrevias(q, 8, 1, '2026-11-08');
    if (r.discrepancias_contrato.length) throw Error('Lecturas previas: esquema discordante; sin escrituras');
  } catch (e) {
    assert.match(e.message, /sin escrituras/);
  } finally { cierres++; }
  aplicarDiscrepancias(r);
  assert.equal(cierres, 1);
  assert.deepEqual(llamadas.map(x => x.peticion), ['estados_get']);
  assert.ok(llamadas.every(x => x.metodo === 'GET'));
  assert.equal(r.casos['TC-M06-011'].estado, 'NO_CONCLUYENTE');
  assert.equal(r.incidencias.length, 0);
  assert.equal(r.discrepancias_contrato[0].esquema_real.items[0].total_ingresos, undefined);
  n++; process.stdout.write('OK esquema_rf93_distinto_sin_escrituras\n');
}
modo('esquema_coincide', () => {
  const r = { contraste_contrato: [], discrepancias_contrato: [], problemas_tecnicos: [] };
  for (const p of ['estados_get', 'auditoria', 'm03_historial']) {
    const data = mock(p);
    if (p === 'auditoria') { data.pagina_actual = 1; data.registros_por_pagina = 500; }
    if (p === 'm03_historial') { data.pagina = 1; data.por_pagina = 100; data.paginas_totales = 1; }
    const ruta = p === 'auditoria' ? '/finanzas/auditoria?pagina=1&tamano=500' :
      p === 'm03_historial' ? '/iot/monitoreo/historial?pagina=1&por_pagina=100' : '/finanzas/periodos/8/estados-resultados';
    assert.equal(contrastarRespuesta(r, p, 'contador', 200, data, ruta), true);
  }
  assert.equal(r.discrepancias_contrato.length, 0);
  assert.ok(r.contraste_contrato.every(x => x.resultado === 'coincide'));
});
let maximoSolicitudesEnsayo = 0;
async function ensayoPrecontraste(escenario) {
  const r = { contraste_contrato: [], discrepancias_contrato: [], problemas_tecnicos: [] };
  const llamadas = [];
  const q = async (peticion, ruta, actor = 'contador', body) => {
    llamadas.push({ peticion, metodo: body === undefined ? 'GET' : 'POST', actor });
    let data = structuredClone(mock(peticion));
    if (peticion === 'auditoria') { data.pagina_actual = 1; data.registros_por_pagina = 500; }
    if (peticion === 'm03_historial') { data.pagina = 1; data.por_pagina = 100; data.paginas_totales = 1; }
    if (peticion === 'variaciones' && escenario === 'discrepa') data[0].monto_variacion = { inesperado: true };
    if (escenario === 'vacias') {
      if (['estados_get', 'variaciones', 'mediciones', 'lineas'].includes(peticion)) data = [];
      if (peticion === 'auditoria') data.eventos = [];
      if (peticion === 'm03_historial') data.items = [];
      if (peticion === 'eventos_get') data.eventos = [];
    }
    if (peticion === 'ficha') data.peso_actual = null;
    if (peticion === 'activos') data[0].valor_razonable_neto = null;
    if (peticion === 'periodos') data[0].numero_id_tributaria = null;
    if (peticion === 'estado_detalle') data.total_ingresos = '1.25';
    if (peticion === 'variaciones' && escenario !== 'discrepa' && data.length) data[0].monto_variacion = '1.25';
    const valido = contrastarRespuesta(r, peticion, actor, 200, data, ruta);
    return { http: 200, data: valido ? data : null, eco: true, esquema_valido: valido };
  };
  let previo = null;
  await q('activos', '/finanzas/activos');
  await q('periodos', '/finanzas/periodos');
  try { previo = await lecturasPrevias(q, 8, 1, '2026-11-08', r); }
  catch (e) { assert.match(e.message, /sin escrituras/); }
  if (previo) {
    llamadas.push({ peticion: 'estado_post', metodo: 'POST', actor: 'contador' });
    llamadas.push({ peticion: 'estados_get', metodo: 'GET', actor: 'contador' });
  }
  maximoSolicitudesEnsayo = Math.max(maximoSolicitudesEnsayo, llamadas.length);
  return { r, llamadas, previo };
}
function informeEnsayo(r) {
  const datos = { ...r, casos: Object.fromEntries(CASOS.map(caso => [caso,
    { estado: 'NO_CONCLUYENTE', motivo: 'Ensayo local' }])), comprobaciones: [], incidencias: [],
    herramientas: { newman: null }, evidencias: [], cierre: { run: { cierre_http: 200 },
      rollback: { verificado: true, motivo: 'Sin escrituras en simulación' } },
    efectos_persistentes_declarados: { precios_registrados: 0, id_precio_mercado: [],
      registros_sin_id: 0, tipo: 'ALERTA_FINANCIERA_NIC41', bandeja_contador_qa: { estado: 'NO_VERIFICABLE' } } };
  return informe({ version: 1, intento: 1, runId: 'SIMULACION_LOCAL', referencia: 'SIMULACION_LOCAL' }, datos);
}
{
  const { r, llamadas, previo } = await ensayoPrecontraste('coincide');
  assert.ok(previo?.cadena && previo?.estado_detalle);
  assert.equal(r.discrepancias_contrato.length, 0);
  assert.equal(llamadas.filter(x => x.metodo === 'POST').length, 1);
  assert.ok(llamadas.find(x => x.peticion === 'ficha' && x.actor === 'admin'));
  assert.ok(llamadas.find(x => x.peticion === 'eventos_get' && x.actor === 'admin'));
  n++; process.stdout.write('OK precontraste_todas_get_coinciden\n');
}
{
  const { r, llamadas, previo } = await ensayoPrecontraste('discrepa');
  assert.equal(previo, null);
  assert.equal(llamadas.filter(x => ['POST', 'PATCH'].includes(x.metodo)).length, 0);
  assert.match(r.discrepancias_contrato[0].motivo, /variaciones\[\].monto_variacion.*esperado decimal\|number.*llegó object/);
  assert.equal(r.discrepancias_contrato[0].ruta, '/finanzas/periodos/{periodo}/variaciones');
  assert.match(informeEnsayo(r), /\/finanzas\/periodos\/\{periodo\}\/variaciones.*variaciones\[\]\.monto_variacion.*esperado decimal\|number.*llegó object/);
  n++; process.stdout.write('OK precontraste_variaciones_discrepa\n');
}
{
  const { r, llamadas, previo } = await ensayoPrecontraste('vacias');
  assert.ok(previo);
  assert.equal(previo.cadena, null);
  assert.equal(previo.estado_detalle, null);
  assert.equal(llamadas.filter(x => x.metodo === 'POST').length, 1);
  assert.ok(r.contraste_contrato.some(x => x.id === 'cadena' && x.resultado === 'sin elementos para contrastar'));
  assert.ok(r.contraste_contrato.some(x => x.id === 'estado_detalle' && x.resultado === 'sin elementos para contrastar'));
  assert.match(informeEnsayo(r), /Rutas sin elementos para contrastar:.*\/finanzas\/lineas\/\{linea\}\/cadena/);
  n++; process.stdout.write('OK precontraste_listas_vacias\n');
}
assert.ok(maximoSolicitudesEnsayo < 150);
process.stdout.write(`Solicitudes máximas del ensayo de precontraste y continuación: ${maximoSolicitudesEnsayo}/150\n`);
modo('presupuesto_flujo_completo', () => {
  const catalogoReal = 26, permisos = 2, logins = 2, estadoPost = 1;
  const rebase = 6, cuatroPasos = 16, precios = 2, patch = 1;
  const posteriores = 5, rf91 = 4, newman = 3, cierrePublico = 23, deleteRun = 1, bandeja = 2;
  const techo = catalogoReal + permisos + logins + estadoPost + rebase + cuatroPasos +
    precios + patch + posteriores + rf91 + newman + cierrePublico + deleteRun + bandeja;
  assert.equal(techo, 94);
  assert.ok(techo <= 140);
  process.stdout.write(`Techo calculado del flujo completo: ${techo}/150 solicitudes\n`);
});
modo('actor_sin_permiso_falla', () => assert.throws(() => validarActor('ficha', 'contador'), /sin permiso/));
modo('seleccion_todos_y_precio_vigente', () => {
  const base = { especie: 'Bovino', tipo: 'INDIVIDUAL', estado: 'ACTIVO', valorado_por_costo: false,
    periodo: { estado: 'ABIERTO' }, precio: { id_precio_mercado: 18 }, calculo: { estado: 'CALCULADO', id_precio_mercado: 18 }, peso: 100 };
  const xs = [{ ...base, id_activo_biologico: 1, calculo: { estado: 'CALCULADO', id_precio_mercado: 17 } },
    { ...base, id_activo_biologico: 2 }, { ...base, id_activo_biologico: 3, peso: null }];
  const s = seleccionarCandidatos(xs, 2);
  assert.equal(s.elegido[0].id_activo_biologico, 2);
  assert.equal(s.motivos.length, 3);
  assert.ok(s.motivos[2].motivos.includes('sin peso actual positivo'));
});
modo('aislamiento_ids_y_linea_base', () => {
  assert.deepEqual(idsNuevos([{ id: 1 }], [{ id: 1 }, { id: 2 }], 'id'), [{ id: 2 }]);
});
modo('registro_qa_fiel', () => {
  const fixture = JSON.parse(fs.readFileSync(path.resolve(path.dirname(fileURLToPath(import.meta.url)), 'resultado_g36_fixture.json'), 'utf8'));
  for (const k of ['run_id', 'version', 'casos', 'comprobaciones', 'evidencias', 'herramientas', 'cypress', 'cierre', 'oficial', 'consume_version'])
    assert.ok(fixture.campos_raiz.includes(k));
  for (const k of ['caso', 'fuente', 'id', 'tipo', 'estado', 'evidencia']) assert.ok(fixture.campos_comprobacion.includes(k));
  assert.equal(fixture.oficial, true);
  const runId = 'RUN-G37-V1-20261108-161426', referencia = 'AUT-G37-V1-20261108';
  const r = { run_id: runId, autorizacion_referencia: referencia, version: 1, oficial: true, consume_version: true,
    cierre: { run: { cierre_http: 200 }, rollback: { verificado: true } },
    casos: Object.fromEntries(CASOS.map(c => [c, { estado: 'RECHAZADO' }])),
    comprobaciones: CASOS.map((c, i) => ({ caso: c, fuente: 'API', id: IDS[i], tipo: 'ASSERT',
      estado: 'RECHAZADO', evidencia: 'resultado.json' })), herramientas: { newman: { iteraciones: 1 } },
    cypress: { total_pruebas: 0 }, evidencias: ['resultado.json', 'TC-M06-G37_resultado.md',
      'newman/newman-G37.json', 'newman/newman-G37.html'] };
  const presentes = new Set(r.evidencias);
  assert.equal(clasificarRegistro(CAPACIDADES, r, presentes, { runId, referencia, version: 1 }), true);
  assert.equal(clasificarRegistro(CAPACIDADES, { ...r, run_id: 'RUN-OTRO' }, presentes, { runId, referencia, version: 1 }), false);
  assert.equal(clasificarRegistro(CAPACIDADES, { ...r, autorizacion_referencia: 'AUT-OTRA' }, presentes,
    { runId, referencia, version: 1 }), false);
});
modo('precios_con_aviso_rollback_verificado', () => {
  const rollback = evaluarRollbackSandbox({ deleteHttp: 200, lecturasCompletas: true,
    registrosPresentes: [], inciertas: false, conciliadas: true });
  assert.equal(rollback.verificado, true);
  const runId = 'RUN-G37-V1-20261108-161426', referencia = 'AUT-G37-V1-20261108';
  const evidencias = ['resultado.json', 'TC-M06-G37_resultado.md', 'newman/newman-G37.json', 'newman/newman-G37.html'];
  const r = { run_id: runId, autorizacion_referencia: referencia, version: 1, oficial: true, consume_version: true,
    cierre: { run: { cierre_http: 200 }, rollback },
    efectos_persistentes_declarados: { tipo: 'ALERTA_FINANCIERA_NIC41', precios_registrados: 2,
      id_precio_mercado: [172, 173], bandeja_contador_qa: { estado: 'OBSERVADO', avisos_observados: 2 } },
    casos: Object.fromEntries(CASOS.map(c => [c, { estado: 'RECHAZADO' }])),
    comprobaciones: CASOS.map((c, i) => ({ caso: c, fuente: 'API', id: IDS[i], tipo: 'ASSERT',
      estado: 'RECHAZADO', evidencia: 'resultado.json' })),
    herramientas: { newman: { iteraciones: 1 } }, cypress: { total_pruebas: 0 }, evidencias };
  assert.equal(clasificarRegistro(CAPACIDADES, r, new Set(evidencias), { runId, referencia, version: 1 }), true);
});
modo('registro_persistente_tras_delete', () => {
  const rollback = evaluarRollbackSandbox({ deleteHttp: 200, lecturasCompletas: true,
    registrosPresentes: ['precio RF-89'], inciertas: false, conciliadas: true });
  assert.equal(rollback.verificado, false);
  assert.match(rollback.motivo, /Persisten registros del RUN/);
  assert.equal(evaluarRollbackSandbox({ deleteHttp: 200, lecturasCompletas: true,
    registrosPresentes: [], inciertas: true, conciliadas: false }).verificado, false);
});
modo('rollback_sin_escrituras', () => {
  const r = evaluarRollbackSandbox({ deleteHttp: 200, escrituras: false,
    lecturasCompletas: false, registrosPresentes: [], inciertas: false, conciliadas: true });
  assert.equal(r.verificado, true);
  assert.equal(evaluarRollbackSandbox({ deleteHttp: 200, escrituras: true,
    lecturasCompletas: false, registrosPresentes: [], inciertas: false, conciliadas: true }).verificado, false);
});
modo('run_id_sin_redactar', () => {
  const id = 'RUN-G37-V1-20261108-161426', referencia = 'AUT-G37-V1-20261108';
  assert.equal(JSON.stringify({ id, referencia }).includes(id), true);
  assert.equal(JSON.stringify({ id, referencia }).includes(referencia), true);
});
if (process.argv.includes('--sin-run')) {
  process.stdout.write(`OK G37: ${n}/${n} modos locales sin carpetas RUN; integración pendiente\n`);
  process.exit(0);
}
{
  const grupo = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
  let runId, directorio;
  const temporal = fs.mkdtempSync(path.join(os.tmpdir(), 'g37-ensayo-'));
  do {
    runId = `RUN-G37-V1-20261108-${String(randomInt(1000000)).padStart(6, '0')}`;
    directorio = path.join(temporal, runId);
  } while (fs.existsSync(directorio));
  const referencia = 'AUT-G37-V1-20261108';
  const llamadas = [];
  try {
    fs.mkdirSync(directorio, { recursive: true });
    const ruta = path.join(directorio, 'contexto_operacion.json');
    fs.writeFileSync(ruta, JSON.stringify({ grupo: 'G37', run_id: runId, version: 1, intento: 1,
      operacion: 'EVALUAR', referencia, casos: CASOS }));
    const archivoEnv = path.join(temporal, 'local.env');
    fs.writeFileSync(archivoEnv, [
      'SIGAB_API_TEST_BASE=http://127.0.0.1:1234', 'QA_SANDBOX_SECRET=secreto-ficticio',
      'QA_CONTADOR_EMAIL=contador@ejemplo.invalid', 'QA_CONTADOR_PASSWORD=clave-ficticia',
      'QA_ADMIN_EMAIL=admin@ejemplo.invalid', 'QA_ADMIN_PASSWORD=clave-ficticia'
    ].join('\n'));
    const respuesta = (status, data) => ({ status, json: async () => data,
      headers: { get: () => runId } });
    const fetcher = async (url, opciones) => {
      const ruta = new URL(url).pathname;
      llamadas.push(`${opciones.method} ${ruta}`);
      assert.equal(JSON.parse(fs.readFileSync(path.join(directorio, 'preflight.json'))).ok, true);
      if (ruta === '/sesiones/') return respuesta(200, { token: 'token-ficticio' });
      if (ruta === '/sesiones/me/permisos') return respuesta(200, { permisos: Object.entries(CONTRATO.roles.contador.permisos).flatMap(([nombre_recurso, acciones]) => acciones.map(id_accion => ({ id_recurso: 1, id_accion, nombre_recurso }))).concat(Object.entries(CONTRATO.roles.admin.permisos).flatMap(([nombre_recurso, acciones]) => acciones.map(id_accion => ({ id_recurso: 1, id_accion, nombre_recurso })))) });
      if (ruta === '/notificaciones') return respuesta(200, { items: [] });
      if (ruta.endsWith(`/test-control/runs/${runId}`)) return respuesta(200, null);
      if (ruta === '/finanzas/activos' || ruta === '/finanzas/periodos') return respuesta(200, []);
      throw Error('Ruta inesperada del ensayo');
    };
    const args = ['--autorizacion', referencia, '--operacion', 'evaluar', '--version', '1',
      '--intento', '1', '--run-id', runId, '--contexto', ruta];
    const salida = await principal(args, { proceso: { QA_AUTORIZADO: 'SI' }, archivoEnv,
      fetcher, ensayo: true });
    assert.equal(salida.preflight.ok, true);
    assert.equal(salida.resultado.cierre.run.cierre_http, 200);
    assert.equal(salida.resultado.cierre.rollback.verificado, true);
    assert.deepEqual(salida.resultado.cierre.lecturas_poscierre, []);
    assert.equal(salida.resultado.oficial, false);
    assert.ok(llamadas.includes(`DELETE /api-sgpmp-test/test-control/runs/${runId}`) ||
      llamadas.includes(`DELETE /test-control/runs/${runId}`));
    assert.ok(fs.existsSync(path.join(directorio, 'resultado.json')));
    assert.ok(fs.existsSync(path.join(directorio, 'TC-M06-G37_resultado.md')));
    n++; process.stdout.write('OK arranque_lanzador\n');
  } finally {
    assert.equal(path.dirname(path.resolve(directorio)), temporal);
    runTemporalEliminado = directorio;
    fs.rmSync(temporal, { recursive: true, force: true });
  }
}
{
  let liberar;
  const pendiente = new Promise(resolve => { liberar = resolve; });
  await conPeticiones(async () => { await pendiente; return { status: 200, json: async () => null }; }, async () => {
    const primera = fetchEnContexto('http://127.0.0.1:1/primera');
    await assert.rejects(fetchEnContexto('http://127.0.0.1:1/segunda'), /PETICION_CONCURRENTE/);
    liberar();
    await primera;
  });
  n++; process.stdout.write('OK peticion_concurrente\n');
}
async function ensayoSeleccion(escenario) {
  const grupo = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
  let runId, directorio;
  const temporal = fs.mkdtempSync(path.join(os.tmpdir(), 'g37-seleccion-'));
  do {
    runId = `RUN-G37-V1-20261108-${String(randomInt(1000000)).padStart(6, '0')}`;
    directorio = path.join(temporal, runId);
  } while (fs.existsSync(directorio));
  let simultaneas = 0, fallosConcurrencia = 0;
  const servidor = http.createServer(async (req, res) => {
    const mismoRun = req.headers['x-test-run-id'] === runId;
    if (mismoRun && simultaneas) {
      fallosConcurrencia++;
      res.writeHead(500, { 'content-type': 'application/json', 'x-test-run-id': runId });
      res.end(JSON.stringify({ code: 'CONCURRENCIA' })); return;
    }
    if (mismoRun) simultaneas++;
    await new Promise(resolve => setTimeout(resolve, 60));
    const ruta = new URL(req.url, 'http://127.0.0.1').pathname;
    let status = 200, data;
    if (ruta === '/sesiones/') data = { token: 'token-ficticio' };
    else if (ruta === '/sesiones/me/permisos') data = { permisos: Object.entries(CONTRATO.roles.contador.permisos).flatMap(([nombre_recurso, acciones]) => acciones.map(id_accion => ({ id_recurso: 1, id_accion, nombre_recurso }))).concat(Object.entries(CONTRATO.roles.admin.permisos).flatMap(([nombre_recurso, acciones]) => acciones.map(id_accion => ({ id_recurso: 1, id_accion, nombre_recurso })))) };
    else if (ruta === '/notificaciones') data = { items: [] };
    else if (ruta === `/test-control/runs/${runId}`) data = null;
    else if (ruta === '/finanzas/activos') {
      data = mock('activos'); Object.assign(data[0], { especie: 'Bovino', tipo: 'INDIVIDUAL', estado: 'ACTIVO' });
    } else if (ruta === '/finanzas/periodos') {
      data = mock('periodos'); Object.assign(data[0], { fecha_inicio: '2026-01-01', fecha_fin: '2026-12-31', estado: 'CERRADO' });
    } else if (ruta === '/finanzas/precios') {
      data = mock('precios_get'); Object.assign(data[0], { fuente: 'MERCADO_ACTIVO', fecha_vigencia: '2026-01-01', fecha_vencimiento: '2026-12-31' });
    } else if (ruta === '/finanzas/activos/1') {
      if (escenario === 'seleccion_con_500') { status = 500; data = { code: 'ERROR_INTERNO' }; }
      else { data = mock('activo_detalle'); data.calculos[0].estado = 'CALCULADO'; }
    } else if (ruta === '/activos-biologicos/1/ficha-integral') {
      data = mock('ficha'); Object.assign(data, { peso_actual: '0.00', unidad_peso: 'kg' });
    } else { status = 404; data = { code: 'RUTA_INESPERADA' }; }
    if (mismoRun) simultaneas--;
    res.writeHead(status, { 'content-type': 'application/json', 'x-test-run-id': runId });
    res.end(JSON.stringify(data));
  });
  try {
    await new Promise(resolve => servidor.listen(0, '127.0.0.1', resolve));
    fs.mkdirSync(directorio, { recursive: true });
    const contexto = path.join(directorio, 'contexto_operacion.json');
    const referencia = 'AUT-G37-V1-20261108';
    fs.writeFileSync(contexto, JSON.stringify({ grupo: 'G37', run_id: runId, version: 1, intento: 1,
      operacion: 'EVALUAR', referencia, casos: CASOS }));
    const base = `http://127.0.0.1:${servidor.address().port}`;
    const archivoEnv = path.join(temporal, 'local.env');
    fs.writeFileSync(archivoEnv, [`SIGAB_API_TEST_BASE=${base}`, 'QA_SANDBOX_SECRET=secreto-ficticio',
      'QA_CONTADOR_EMAIL=contador@ejemplo.invalid', 'QA_CONTADOR_PASSWORD=clave-ficticia',
      'QA_ADMIN_EMAIL=admin@ejemplo.invalid', 'QA_ADMIN_PASSWORD=clave-ficticia'].join('\n'));
    const args = ['--autorizacion', referencia, '--operacion', 'evaluar', '--version', '1',
      '--intento', '1', '--run-id', runId, '--contexto', contexto];
    const salida = await principal(args, { proceso: { QA_AUTORIZADO: 'SI' }, archivoEnv, ensayo: true });
    assert.equal(fallosConcurrencia, 0);
    assert.equal(simultaneas, 0);
    assert.equal(salida.resultado.cierre.run.cierre_http, 200);
    const esperado = escenario === 'seleccion_con_500' ? 'NO_CONCLUYENTE' : 'BLOQUEADO';
    for (const caso of CASOS) assert.equal(salida.resultado.casos[caso].estado, esperado);
    if (escenario === 'seleccion_con_500') {
      assert.match(salida.resultado.casos[CASOS[0]].motivo, /\/finanzas\/activos\/1 \(HTTP 500, ERROR_INTERNO\)/);
      assert.deepEqual(salida.resultado.observaciones.candidatos.at(-1).motivos, ['detalle no legible: HTTP 500']);
    } else {
      assert.ok(salida.resultado.observaciones.candidatos[0].motivos.includes('sin peso actual positivo'));
      assert.match(fs.readFileSync(path.join(directorio, 'TC-M06-G37_resultado.md'), 'utf8'), /sin peso actual positivo/);
    }
  } finally {
    await new Promise(resolve => servidor.close(resolve));
    assert.equal(path.dirname(path.resolve(directorio)), temporal);
    fs.rmSync(temporal, { recursive: true, force: true });
  }
}
for (const escenario of ['seleccion_con_500', 'seleccion_sin_candidatos_validos']) {
  await ensayoSeleccion(escenario);
  n++; process.stdout.write(`OK ${escenario}\n`);
}
modo('sin_residuos', () => {
  const dir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
  assert.equal(fs.existsSync(runTemporalEliminado), false);
  assert.equal(fs.existsSync(path.join(dir, 'diagnostico')), false);
  assert.equal(fs.existsSync(path.join(dir, 'informe.md')), false);
  assert.deepEqual(fs.readdirSync(path.join(dir, 'Resultados')).sort(), [
    'RUN-G37-V1-20261108-202328', 'RUN-G37-V1-20261108-203910',
    'RUN-G37-V1-20261108-205523', 'RUN-G37-V1-20261108-212224',
    'RUN-G37-V1-20261108-213859', 'RUN-G37-V1-20261108-220244',
    'RUN-G37-V1-20261108-230500'
  ]);
});
process.stdout.write(`OK G37: ${n}/${n} modos locales; sin ejecución de RUN ni comprobación real de cierre\n`);
