import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import { comprobar, crearTransporte, informe, registroOficial, preflight,
  autenticarSinFinca, rlsSinFincaNoConcluyente,
  diagnosticarCanario, canariosAntesDashboard, relojServidor,
  evaluarRlsSinFinca, umbralAmbientalSeguro, clasificarRollback } from '../g92.mjs';
import { CASOS, CAPACIDADES, LIMITE, SEMILLA, VALORES, VALORES_ALERTA,
  diagnosticarPagina, validarSemillaPersistente, registrarAlertaDeArea,
  estadoDashboard } from '../lib/g92_escenario.mjs';

assert.equal(comprobar(), 0);
const casos = [];
const modo = (nombre, prueba) => { prueba(); casos.push(nombre); };
const A = 697, B = 698;
const sensoresA = Array.from({ length: 60 }, (_, i) => ({ id_sensor: 1142 + i,
  id_infraestructura: A, estado_semaforo: i === 54 ? 'ROJO' : 'VERDE' }));
const sensoresB = ['VERDE', 'VERDE', 'ROJO'].map((estado_semaforo, i) => ({
  id_sensor: 1202 + i, id_infraestructura: B, estado_semaforo,
  tipo_variable: 'TEMPERATURA_AMBIENTAL',
  ...(i === 2 ? { id_alerta: 2002, severidad_alerta: 'CRITICO' } : {}) }));
const resumen = (area, estado_general, total_sensores, alertas_activas_count) => ({
  id_infraestructura: area, estado_general, total_sensores, alertas_activas_count,
  ultimo_dato_recibido: '2026-10-30T20:00:00Z' });
const panelB = { alertas: [{ id_alerta: 2002, id_infraestructura: B,
  severidad: 'CRITICO' }] };
const conforme = () => ({ inicial: { total: 3, sensores: structuredClone(sensoresB),
  resumen_unidades: [resumen(B, 'ROJO', 3, 1)], panel_alertas_activas: panelB },
  a1: { total: 60, sensores: structuredClone(sensoresA.slice(0, 50)),
    resumen_unidades: [resumen(A, 'ROJO', 60, 1)] },
  a2: { total: 60, sensores: structuredClone(sensoresA.slice(50)),
    resumen_unidades: [resumen(A, 'ROJO', 60, 1)] },
  b1: { total: 3, sensores: structuredClone(sensoresB),
    resumen_unidades: [resumen(B, 'ROJO', 3, 1)] },
  alcanceA: true, alcanceB: true, areaA: A, areaB: B, alertasActivas: 2 });
modo('colección y ejecutor concuerdan en PRE-181-01 y obligatorias', () => {
  const coleccion = JSON.parse(fs.readFileSync(new URL('../G92.postman_collection.json', import.meta.url), 'utf8'));
  const script = coleccion.item[0].event.find((x) => x.listen === 'test').script.exec.join('\n');
  const pre = script.split('\n').find((linea) => linea.includes("pm.test(pre('TC-M03-181','PRE-181-01')"));
  assert.match(pre, /\['VERDE','ROJO'\]/);
  assert.doesNotMatch(pre, /AMARILLO/);
  assert.deepEqual(CAPACIDADES.comprobaciones_obligatorias['TC-M03-181'].API,
    ['API-181-01', 'API-181-02']);
  assert.doesNotMatch(script, /pm\.test\(id\('TC-M03-181','API-181-03'/);
  assert.match(script, /obs_181_03/);
  const ejecutor = fs.readFileSync(new URL('../g92.mjs', import.meta.url), 'utf8');
  assert.match(ejecutor, /tipo: id === 'API-181-03' \? 'OBS'/);
  assert.match(ejecutor, /estado: id === 'API-181-03' \? 'EXCLUIDA_DEL_ORACULO'/);
  const variables = new Map([['fase', 'inicial'], ['area_a', A], ['area_b', B], ['run_id', 'RUN_LOCAL']]);
  const pruebas = [];
  const pm = {
    environment: { get: (key) => variables.get(key), set: (key, value) => variables.set(key, value) },
    response: { code: 200, json: () => conforme().inicial,
      headers: { get: () => 'RUN_LOCAL' } },
    test: (name, fn) => { fn(); pruebas.push(name); },
    expect: (actual) => ({ to: { eql: (esperado) => assert.deepEqual(actual, esperado),
      include: (esperado) => assert.ok(actual.includes(esperado)),
      be: { get ok() { assert.ok(actual); return true; } } } }),
  };
  vm.runInNewContext(script, { pm });
  assert.equal(pruebas.length, 4);
  assert.ok(pruebas.every((nombre) => !nombre.includes('API-181-03')));
  assert.equal(variables.get('obs_181_amarillo'), 'false');
  assert.deepEqual(JSON.parse(variables.get('obs_181_03')),
    { atencion_en_resumen: false, criticas_en_resumen: false });
});
modo('E14 consolida LEVE a CRITICO dentro del RUN y rechaza alerta ajena', () => {
  const creadas = new Map();
  assert.deepEqual(registrarAlertaDeArea({ es_duplicado: false, id_alerta: 1346,
    severidad: 'LEVE' }, B, creadas), { id: 1346, nueva: true, consolidada: false });
  assert.deepEqual(registrarAlertaDeArea({ es_duplicado: true, id_alerta: 1346,
    alerta_existente_id: 1346, severidad: 'CRITICO' }, B, creadas),
  { id: 1346, nueva: false, consolidada: true });
  assert.deepEqual([...creadas], [[1346, B]]);
  assert.throws(() => registrarAlertaDeArea({ es_duplicado: true, id_alerta: 1346,
    alerta_existente_id: 1346 }, A, creadas), /ALERTA_DUPLICADA_ERROR_QA/);
  assert.throws(() => registrarAlertaDeArea({ es_duplicado: true, id_alerta: 9999,
    alerta_existente_id: 9999 }, B, creadas), /ALERTA_DUPLICADA_ERROR_QA/);
  assert.throws(() => registrarAlertaDeArea({ es_duplicado: false, id_alerta: 1347 },
    B, creadas), /ALERTA_DUPLICADA_ERROR_QA/);
});
modo('todo conforme', () => {
  const d = diagnosticarPagina(conforme());
  assert.ok(Object.values(d.checks).every(Boolean));
  assert.equal(d.observado.posicion_rojo, 55);
  const ids = Object.values(CAPACIDADES.comprobaciones_obligatorias).flatMap((x) => x.API);
  const r = { comprobaciones: ids.map((id) => ({ id, tipo: 'ASSERT', estado: 'APROBADO' })),
    casos: Object.fromEntries(CASOS.map((id) => [id, { estado: 'APROBADO' }])),
    cierre: { run: { cierre_http: 200 }, rollback: { verificado: true } },
    canarios: ['previo-newman', 'cierre'].flatMap((fase) => [A, B].map((area) =>
      ({ fase, area, seguro: true, evidencia: `api/E7-CANARIO-${fase}-${area}.json` }))),
    newman: [{}], evidencias: ['resultado.json', 'TC-M03-G92_resultado.md',
      'newman/newman-TC-M03-G92.json', 'newman/newman-TC-M03-G92.html',
      ...['previo-newman', 'cierre'].flatMap((fase) => [A, B].map((area) =>
        `api/E7-CANARIO-${fase}-${area}.json`))] };
  assert.equal(registroOficial(r, () => true), true);
  assert.equal(registroOficial({ ...r, canarios: r.canarios.slice(1) }, () => true), false);
  assert.equal(registroOficial(r, (x) => x !== 'TC-M03-G92_resultado.md'), false);
  assert.equal(registroOficial({ ...r, cierre: { ...r.cierre,
    rollback: { verificado: false } } }, () => true), false);
  assert.equal(registroOficial({ ...r, cierre: { ...r.cierre,
    run: { cierre_http: 500 } } }, () => true), false);
  assert.equal(registroOficial({ ...r, newman: [] }, () => true), false);
  assert.equal(registroOficial({ ...r, casos: { ...r.casos,
    'TC-M03-183': { estado: 'NO_CONCLUYENTE' } } }, () => true), false);
  const checks = ids.map((id) => ({ id, caso: CASOS.find((caso) => caso.endsWith(id.split('-')[1])),
    tipo: 'ASSERT', estado: 'APROBADO', evidencia: 'newman/newman-TC-M03-G92.json',
    evidencias: ['newman/newman-TC-M03-G92.json'] }));
  const reporte = informe({ ...r, run_id: 'SIMULADO_LOCAL', version: 1,
    autorizacion: 'SIMULACION_LOCAL', commit: 'LOCAL', oficial: true,
    directorio: '/', evidencias: [], comprobaciones: checks,
    comprobaciones_tecnicas: [{ id: 'RLS-G92-03', estado: 'NO_CONCLUYENTE',
      motivo: 'UPDATE público no disponible', evidencia: 'resultado.json' }],
    casos: Object.fromEntries(CASOS.map((id) => [id, { estado: 'APROBADO',
      veredicto: 'APROBADO', estado_tecnico: 'OK', observado: {},
      comprobaciones: checks.filter((x) => x.caso === id) }])),
    problemas_tecnicos: [], bitacora: [], estado: 'COMPLETO',
    cierre: { run: { cierre_http: 200 }, motivo: 'simulación', rollback: {
      verificado: true, comprobaciones: [], riesgos_residuales: [] } } });
  assert.match(reporte, /^# TC-M03-G92 — APROBADO/);
  assert.match(reporte, /Decisión del caso:\*\* \*\*APROBADO/);
  assert.match(reporte, /RLS-G92-03: NO_CONCLUYENTE/);
});
modo('181 sin ROJO consolidado', () => {
  const x = conforme(); x.inicial.resumen_unidades[0].estado_general = 'VERDE';
  const d = diagnosticarPagina(x);
  assert.equal(d.checks['PRE-181-01'], true);
  assert.equal(d.checks['API-181-01'], false);
  assert.equal(d.checks['API-181-03'], true);
});
modo('182 con datos de otra unidad', () => {
  const x = conforme(); x.a1.sensores[0].id_infraestructura = B;
  assert.equal(diagnosticarPagina(x).checks['API-182-01'], false);
});
modo('182 con resumen ajeno en segunda página', () => {
  const x = conforme(); x.a2.resumen_unidades.push(resumen(B, 'ROJO', 3, 1));
  const d = diagnosticarPagina(x);
  assert.equal(d.checks['PRE-182-01'], true);
  assert.equal(d.checks['API-182-02'], false);
  assert.deepEqual(d.observado.ids_ajenos, [B]);
});
modo('183 sin consolidar ROJO fuera de página', () => {
  const x = conforme(); x.a1.resumen_unidades[0].estado_general = 'VERDE';
  const d = diagnosticarPagina(x);
  assert.equal(d.checks['PRE-183-01'], true);
  assert.equal(d.checks['API-183-02'], false);
});
modo('RUN 021342 saneado reproduce la limitación y el nuevo plan descubre 183', () => {
  const real = JSON.parse(fs.readFileSync(new URL('./respuestas_run_021342_saneadas.json', import.meta.url), 'utf8'));
  const entrada = { ...real, alcanceA: true, alcanceB: true, areaA: A, areaB: B,
    alertasActivas: 1 };
  const observado = diagnosticarPagina(entrada);
  assert.equal(observado.checks['PRE-181-01'], true);
  assert.equal(observado.checks['API-181-01'], true);
  assert.equal(observado.checks['API-181-02'], true);
  assert.equal(observado.checks['PRE-183-01'], false);
  const plan = structuredClone(entrada); // Simulación local del plan; no es evidencia de TEST.
  for (const pagina of [plan.a1, plan.a2]) {
    for (const sensor of pagina.sensores) {
      sensor.ultimo_valor = 25;
      if (sensor.id_sensor === 1196) sensor.estado_semaforo = 'ROJO';
    }
    pagina.resumen_unidades[0].alertas_activas_count = 1;
  }
  for (const pagina of [plan.inicial, plan.b1])
    for (const sensor of pagina.sensores) sensor.ultimo_valor = 25;
  plan.alertasActivas = 2;
  const defecto = diagnosticarPagina(plan);
  assert.equal(defecto.checks['PRE-181-01'], true);
  assert.equal(defecto.checks['PRE-183-01'], true);
  assert.equal(defecto.checks['API-183-02'], false);
  plan.a1.resumen_unidades[0].estado_general = 'ROJO';
  assert.equal(diagnosticarPagina(plan).checks['API-183-02'], true);
});
modo('E7 evitado en la semilla local', () => {
  assert.deepEqual(VALORES, { VERDE: 25 });
  assert.deepEqual(VALORES_ALERTA, { ROJO: 29 });
  assert.equal(LIMITE.telemetrias, 63);
  assert.equal(LIMITE.alertas, 2);
  assert.ok([...sensoresA, ...sensoresB].every((s) => s.estado_semaforo !== 'GRIS'));
  assert.equal(LIMITE.newman, 1);
});
const apertura = Date.parse('2026-10-31T01:47:00Z');
const semillaConforme = () => {
  const ids = [...SEMILLA.sensoresA, ...SEMILLA.sensoresB];
  return {
    finca: { id_finca: 184, es_activo: true },
    areas: [0, 1].map((i) => ({ id_infraestructura: SEMILLA.areas[i], id_finca: 184,
      especie_id: 126, es_activo: true, nombre_infraestructura: `QA G92 Unidad ${i ? 'B' : 'A'}` })),
    dispositivos: [0, 1].map((i) => ({ id_dispositivo_iot: SEMILLA.dispositivos[i],
      id_infraestructura: SEMILLA.areas[i], es_activo: true,
      id_dispositivo_gateway: null, categoria: 'SENSOR', serial: `SERIAL_FICTICIO_${i}` })),
    sensores: [SEMILLA.sensoresA, SEMILLA.sensoresB].map((lista, i) => lista.map((id) =>
      ({ id_sensores: id, id_dispositivo_iot: SEMILLA.dispositivos[i],
        es_activo: true, categoria: 'TEMPERATURA' }))),
    asociaciones: ids.map((id, i) => [{ id_sensores_area_asociada: 804 + i,
      id_sensor: id, id_dispositivo_iot: i < 60 ? 785 : 786,
      id_infraestructura: i < 60 ? 697 : 698, tiene_estado: true,
      fecha_asociacion: '2026-10-30T01:44:00Z', fecha_finalizacion: null }]),
    calibraciones: ids.map((id, i) => [{ id_calibracion: 319 + i,
      id_sensor: id, id_dispositivo_iot: i < 60 ? 785 : 786,
      valor_referencia: 25, ganancia: 1, offset: 0,
      modo_calibracion: 'SENSOR', fecha_calibracion: '2026-10-30T00:00:00Z' }]),
    alertas: [{ total: 0, items: [] }, { total: 0, items: [] }],
    historial: [{ total: 0, total_encontrado: 0, items: [] },
      { total: 0, total_encontrado: 0, items: [] }]
  };
};
modo('semilla persistente conforme y sensor 1196 en posicion 55', () => {
  assert.deepEqual(validarSemillaPersistente(semillaConforme(),
    ['SERIAL_FICTICIO_0', 'SERIAL_FICTICIO_1'], apertura), []);
  assert.equal(SEMILLA.sensoresA[54], 1196);
});
modo('semilla alterada aborta antes de escrituras', () => {
  const x = semillaConforme(); x.asociaciones[54][0].tiene_estado = false;
  let escrituras = 0;
  const preparar = () => {
    const errores = validarSemillaPersistente(x,
      ['SERIAL_FICTICIO_0', 'SERIAL_FICTICIO_1'], apertura);
    if (errores.length) throw new Error(errores[0]);
    escrituras++;
  };
  assert.throws(preparar, /ASOCIACION_1196/);
  assert.equal(escrituras, 0);
});
modo('serial ausente bloquea preflight', () => {
  const x = preflight({ operacion: 'reintentar', version: 1, runId: 'SIMULADO' }, {});
  assert.ok(x.barreras.includes('QA_G92_A_SERIAL'));
  assert.ok(x.barreras.includes('QA_G92_B_SERIAL'));
});
modo('rollback compara estado y mantiene semilla', () => {
  const antes = { total: 1, sensores: [{ id_sensor: 1142, estado_semaforo: 'GRIS',
    ultimo_valor: null }], resumen_unidades: [{ id_infraestructura: 697,
    estado_general: 'GRIS', alertas_activas_count: 0 }] };
  assert.deepEqual(estadoDashboard(antes), estadoDashboard(structuredClone(antes)));
  const despues = structuredClone(antes); despues.sensores[0].estado_semaforo = 'VERDE';
  assert.notDeepEqual(estadoDashboard(antes), estadoDashboard(despues));
});
modo('umbral 70 real de temperatura ambiental permite continuar', () => {
  // Valores locales para verificar el filtro del umbral, independientes del historial de RUN.
  const niveles = (normal, precaucion, critico) => [
    { nivel: 'normal', limite_inferior: normal[0], limite_superior: normal[1] },
    { nivel: 'precaucion', limite_inferior: precaucion[0], limite_superior: precaucion[1] },
    { nivel: 'critico', limite_inferior: critico[0], limite_superior: critico[1] }];
  const umbrales = { items: [
    { id_umbral_ambiental: 71, id_especie: 126, id_variable_ambiental: 1,
      es_activo: true, valor_min: '14.00', valor_max: '30.00',
      niveles: niveles(['20.00', '30.00'], ['18.00', '20.00'], ['14.00', '18.00']) },
    { id_umbral_ambiental: 70, id_especie: 126, id_variable_ambiental: 9,
      es_activo: true, valor_min: '15.00', valor_max: '30.00',
      niveles: niveles(['20.00', '30.00'], ['19.00', '20.00'], ['15.00', '19.00']) }
  ] };
  const variables = { total: 2, items: [
    { id_variable_ambiental: 1, nombre: 'OTRA_VARIABLE' },
    { id_variable_ambiental: 9, nombre: 'TEMPERATURA_AMBIENTAL' }
  ] };
  assert.equal(umbralAmbientalSeguro(variables, umbrales), true);
  assert.equal(umbralAmbientalSeguro(variables, { items: [umbrales.items[0]] }), false);
  assert.equal(umbralAmbientalSeguro({ ...variables, items: variables.items.slice(0, 1) }, umbrales), false);
});
modo('aborto sin escrituras clasifica rollback sin exigir baseline', () => {
  const escritura = { sensores: 0, telemetrias: 0, alertas: 0 };
  assert.equal(clasificarRollback(escritura), 'SIN_ESCRITURAS_QUE_REVERTIR');
  assert.equal(clasificarRollback(escritura, true), 'SIN_ESCRITURAS_QUE_REVERTIR');
  assert.equal(clasificarRollback({ ...escritura, sensores: 1 }), 'NO_VERIFICADO');
  assert.equal(clasificarRollback({ ...escritura, sensores: 1 }, true), 'VERIFICADO');
  const r = { version: 1, run_id: 'SIMULADO', autorizacion: 'SIMULACION_LOCAL',
    commit: 'LOCAL', newman: [], casos: Object.fromEntries(CASOS.map((id) =>
      [id, { veredicto: null, estado_tecnico: 'NO_EJECUTADA', observado: null, comprobaciones: [] }])),
    comprobaciones: [], comprobaciones_tecnicas: [], evidencias: [],
    problemas_tecnicos: [], bitacora: [], canarios: [], estado: 'NO_CONCLUYENTE',
    cierre: { run: { cierre_http: 200 }, motivo: 'Sin escrituras.', rollback: {
      estado: clasificarRollback(escritura), verificado: false,
      comprobaciones: [], riesgos_residuales: [] } } };
  assert.match(informe(r), /rollback SIN_ESCRITURAS_QUE_REVERTIR/);
});
modo('canario permite dashboard sin estado antes y despues del RUN', () => {
  assert.equal(diagnosticarCanario(200,
    { total: 0, sensores: [], resumen_unidades: [resumen(A, 'GRIS', 0, 0)] },
    { area: A, permitirVacia: true }).seguro, true);
});

const runId = 'G92-V1-20261030-000000';
const respuesta = (status, body) => ({ status,
  headers: { get: (nombre) => nombre === 'Date' ? 'Fri, 30 Oct 2026 00:00:00 GMT' : runId },
  text: async () => body });
const transporte = (respuestas, bitacora = [], permitidos = {}) => {
  let i = 0;
  const t = crearTransporte({ base: 'http://memoria.invalid', runId,
    secreto: 'SECRETO_FICTICIO', bitacora, secretos: ['SECRETO_FICTICIO'], permitidos,
    fetcher: async () => {
      const r = respuestas[Math.min(i, respuestas.length - 1)]; i++;
      if (r instanceof Error) throw r;
      return r;
    } });
  t.abrir(); return t;
};
const asincronos = [];
const modoAsync = (nombre, prueba) => asincronos.push((async () => {
  await prueba(); casos.push(nombre);
})());
modoAsync('login sin finca 401 permite continuar', async () => {
  const llamadas = [], secretos = ['CLAVE_FICTICIA', 'opcional@example.invalid'];
  const env = { QA_PROD_SIN_FINCA_EMAIL: 'opcional@example.invalid',
    QA_PROD_SIN_FINCA_PASSWORD: 'CLAVE_FICTICIA' };
  const t = crearTransporte({ base: 'http://memoria.invalid', runId,
    secreto: 'SECRETO_FICTICIO', bitacora: [], secretos,
    fetcher: async (url, opciones) => {
      llamadas.push(`${opciones.method} ${new URL(url).pathname}`);
      return llamadas.length === 1
        ? respuesta(401, JSON.stringify({ detalle: 'CLAVE_FICTICIA', email: env.QA_PROD_SIN_FINCA_EMAIL }))
        : respuesta(200, '{}');
    } });
  const login = await autenticarSinFinca(t.solicitar, env, secretos);
  const rls = rlsSinFincaNoConcluyente(login.motivo);
  assert.equal(login.token, null);
  assert.equal(rls.estado, 'NO_CONCLUYENTE');
  assert.match(rls.motivo, /HTTP 401/);
  assert.equal(rls.motivo.includes('CLAVE_FICTICIA'), false);
  assert.equal(rls.motivo.includes('opcional@example.invalid'), false);
  assert.match(rls.motivo, /REDACTADO/);
  t.abrir();
  assert.equal((await t.solicitar('GET', '/usuarios/me', { token: 'PRODUCTOR_FICTICIO' })).status, 200);
  assert.deepEqual(llamadas, ['POST /sesiones/', 'GET /usuarios/me']);
});
modoAsync('variables sin finca ausentes permiten continuar', async () => {
  const llamadas = [];
  const t = crearTransporte({ base: 'http://memoria.invalid', runId,
    secreto: 'SECRETO_FICTICIO', bitacora: [], secretos: [],
    fetcher: async (url, opciones) => {
      llamadas.push(`${opciones.method} ${new URL(url).pathname}`);
      return respuesta(200, '{}');
    } });
  const login = await autenticarSinFinca(t.solicitar, {}, []);
  assert.equal(login.token, null);
  assert.equal(rlsSinFincaNoConcluyente(login.motivo).estado, 'NO_CONCLUYENTE');
  assert.match(login.motivo, /Variables.*ausentes/);
  t.abrir();
  assert.equal((await t.solicitar('GET', '/usuarios/me', { token: 'PRODUCTOR_FICTICIO' })).status, 200);
  assert.deepEqual(llamadas, ['GET /usuarios/me']);
});
modoAsync('500 al crear sensor', async () => {
  const log = [];
  const t = transporte([respuesta(500, '{"error":"RLS"}')], log,
    { dispositivos: new Map([[785, { area: 697, serial: 'SERIAL_FICTICIO' }]]) });
  const x = await t.solicitar('POST', '/configuracion/dispositivos-iot/785/sensores',
    { token: 'JWT_FICTICIO', cuerpo: { nombre: 'QA local', categoria: 'TEMPERATURA' } });
  assert.equal(x.status, 500);
  assert.equal(JSON.parse(log[0].cuerpo_error).error, 'RLS');
});
modoAsync('422 con cuerpo guardado', async () => {
  const log = [], t = transporte([respuesta(422, '{"detalle":"campo inválido"}')], log);
  assert.equal((await t.solicitar('GET', '/usuarios/me')).status, 422);
  assert.match(log[0].cuerpo_error, /campo inválido/);
});
modoAsync('5xx aislado', async () => {
  const t = transporte([respuesta(500, '{}'), respuesta(200, '{}')]);
  assert.equal((await t.solicitar('GET', '/usuarios/me')).status, 500);
  assert.equal((await t.solicitar('GET', '/usuarios/me')).status, 200);
});
modoAsync('tres 5xx seguidos', async () => {
  const t = transporte([respuesta(500, '{}')]);
  await t.solicitar('GET', '/usuarios/me');
  await t.solicitar('GET', '/usuarios/me');
  await assert.rejects(() => t.solicitar('GET', '/usuarios/me'), /TRES_5XX_CONSECUTIVOS/);
});
modoAsync('403 de clave', async () => {
  const t = transporte([respuesta(403, '{"error":"clave"}')]);
  await assert.rejects(() => t.solicitar('GET', '/usuarios/me'), /CLAVE_O_ACCESO_403/);
});
modoAsync('timeout', async () => {
  const t = transporte([new Error('The operation was aborted due to timeout')]);
  await assert.rejects(() => t.solicitar('GET', '/usuarios/me'), /timeout/);
});
modoAsync('límite funcional conserva cierre y lecturas', async () => {
  const t = crearTransporte({ base: 'http://memoria.invalid', runId,
    secreto: 'SECRETO_FICTICIO', bitacora: [], secretos: [], limite: 5,
    fetcher: async () => respuesta(200, '{}') });
  t.abrir();
  await t.solicitar('GET', '/usuarios/me');
  await assert.rejects(() => t.solicitar('GET', '/usuarios/me'), /LIMITE_SOLICITUDES_FUNCIONALES/);
  await t.solicitar('DELETE', `/test-control/runs/${runId}`, { cierre: true });
  assert.equal((await t.solicitar('GET', '/usuarios/me')).status, 200);
});
modoAsync('lista blanca rechaza escritura e ID ajenos', async () => {
  let llamadas = 0;
  const t = crearTransporte({ base: 'http://memoria.invalid', runId,
    secreto: 'SECRETO_FICTICIO', bitacora: [], secretos: [],
    fetcher: async () => { llamadas++; return respuesta(201, '{}'); } });
  t.abrir();
  await assert.rejects(() => t.solicitar('PATCH', '/configuracion/sensores/301',
    { cuerpo: { id_dispositivo_iot: 999 } }), /ESCRITURA_FUERA_LISTA_BLANCA/);
  await assert.rejects(() => t.solicitar('POST', '/configuracion/dispositivos-iot/999/sensores',
    { cuerpo: { nombre: 'QA local', categoria: 'TEMPERATURA' } }), /ID_FUERA_LISTA_BLANCA/);
  await assert.rejects(() => t.solicitar('POST', '/configuracion/infraestructuras',
    { cuerpo: { finca_id: 184 } }), /ESCRITURA_FUERA_LISTA_BLANCA/);
  await assert.rejects(() => t.solicitar('POST', '/configuracion/sensores/1196/asociar',
    { cuerpo: { id_infraestructura: 697 } }), /ESCRITURA_FUERA_LISTA_BLANCA/);
  await assert.rejects(() => t.solicitar('POST', '/configuracion/sensores/1196/calibrar',
    { cuerpo: { id_infraestructura: 697 } }), /ESCRITURA_FUERA_LISTA_BLANCA/);
  assert.equal(llamadas, 0);
});
for (const [nombre, sensor, continua] of [
  ['canario conforme continúa', { estado_semaforo: 'VERDE', dato_desactualizado: false }, true],
  ['canario GRIS detiene y cierra', { estado_semaforo: 'GRIS', dato_desactualizado: false }, false],
  ['canario sin_umbral detiene y cierra', { estado_semaforo: 'VERDE', sin_umbral: true }, false],
]) modoAsync(nombre, async () => {
  const areasConsultadas = [], acciones = [];
  let cerrado = false, problema = null;
  try {
    const seguro = await canariosAntesDashboard([A, A, B], async (area) => {
      areasConsultadas.push(area);
      const d = diagnosticarCanario(200, { total: 3, sensores: [
        { id_sensor: 101, id_infraestructura: area, ...sensor }] }, { area });
      if (!d.seguro) problema = 'E7-CANARIO';
      return d.seguro;
    });
    if (seguro) acciones.push('NEWMAN_UNICO');
  } finally { cerrado = true; acciones.push('DELETE'); }
  assert.equal(cerrado, true);
  assert.deepEqual(areasConsultadas, continua ? [A, B] : [A]);
  assert.deepEqual(acciones, continua ? ['NEWMAN_UNICO', 'DELETE'] : ['DELETE']);
  assert.equal(problema, continua ? null : 'E7-CANARIO');
});
modoAsync('cuerpo de error saneado', async () => {
  const bitacora = [];
  const t = transporte([respuesta(422, '{"detalle":"SECRETO_FICTICIO"}')], bitacora);
  await t.solicitar('GET', '/usuarios/me');
  assert.equal(JSON.stringify(bitacora).includes('SECRETO_FICTICIO'), false);
  assert.ok(bitacora[0].cuerpo_error);
});
modoAsync('NOW() de transaccion: 65 marcas posteriores a semilla y entre 60 y 44 segundos', async () => {
  let transcurrido = 0;
  const reloj = relojServidor({ ahora: () => transcurrido });
  const inicio = '2026-10-31T01:47:00.000Z';
  reloj.observar(inicio);
  reloj.fijarInicio(inicio);
  transcurrido = 10_000;
  reloj.observar('2026-10-31T01:47:10.000Z');
  const fechas = { asociacion: '2026-10-30T01:44:00.000Z',
    calibracion: '2026-10-30T00:00:00.000Z' };
  const marcas = [];
  for (let i = 0; i < 65; i++) marcas.push(await reloj.marca(fechas));
  assert.equal(Date.parse(marcas[0]), Date.parse(inicio) - 60_000);
  assert.equal(Date.parse(marcas.at(-1)), Date.parse(inicio) - 44_000);
  assert.ok(marcas.every((m) => Date.parse(m) >= Date.parse(fechas.asociacion) &&
    Date.parse(m) >= Date.parse(fechas.calibracion) &&
    Date.parse(m) <= Date.parse(inicio) - 43_000));
  assert.ok(marcas.every((m, i) => i === 0 ||
    Date.parse(m) - Date.parse(marcas[i - 1]) === 250));
});
modoAsync('400 ERROR_TIEMPO conserva cuerpo de escritura saneado', async () => {
  const log = [];
  const t = transporte([respuesta(400, '{"error_code":"ERROR_TIEMPO"}')], log,
    { dispositivos: new Map([[201, { area: 101, serial: 'SERIAL_FICTICIO' }]]),
      sensores: new Map([[301, { dispositivo: 201, area: 101 }]]) });
  const cuerpo = { device_id: 201, sensor_id: 301, serial: 'SERIAL_FICTICIO',
    timestamp_captura: '2026-10-31T01:15:02.000Z', valor: 25 };
  assert.equal((await t.solicitar('POST', '/iot/telemetria',
    { token: 'TOKEN_FICTICIO', cuerpo })).status, 400);
  assert.equal(log[0].cuerpo_solicitud.timestamp_captura, cuerpo.timestamp_captura);
  assert.equal(log[0].cuerpo_solicitud.valor, 25);
  assert.equal(log[0].cuerpo_solicitud.serial, '[REDACTADO]');
  assert.equal(log[0].respuesta.error_code, 'ERROR_TIEMPO');
});
modo('RLS-02 lectura vacía y 403 por rol', () => {
  const d = evaluarRlsSinFinca({ status: 200, json: { total: 0, items: [] } },
    { status: 403, json: { error_code: 'ACCESO_DENEGADO' } });
  assert.equal(d.estado, 'APROBADO');
  assert.match(d.motivo, /no aísla RLS de INSERT/);
  assert.equal(evaluarRlsSinFinca({ status: 200, json: { total: 1, items: [{}] } },
    { status: 403, json: {} }).estado, 'FALLA');
  assert.equal(evaluarRlsSinFinca({ status: 404, json: {} },
    { status: 201, json: { id_sensores: 301 } }).estado, 'FALLA');
});
await Promise.all(asincronos);
modo('informe oficial por caso legible y sin volcado JSON', () => {
  const ruta = new URL('../Resultados/RUN-G92-V1-20261031-022537/resultado.json', import.meta.url);
  const r = JSON.parse(fs.readFileSync(ruta, 'utf8'));
  const reporte = informe(r);
  const secciones = CASOS.map((id, i) => reporte.split(`### ${id}\n\n`)[1]
    .split(i < CASOS.length - 1 ? `### ${CASOS[i + 1]}` : 'La matriz exige API')[0]);
  for (const [i, seccion] of secciones.entries()) {
    assert.match(seccion, /\*\*Caso original y objetivo:\*\*/);
    assert.match(seccion, /\*\*Precondiciones:\*\*/);
    assert.match(seccion, /\*\*Pasos ejecutados:\*\*/);
    assert.match(seccion, /\*\*Entradas:\*\*/);
    assert.match(seccion, /\*\*Esperado:\*\*/);
    assert.match(seccion, /\*\*Observado por API pública:\*\*/);
    assert.match(seccion, /\*\*Decisión del caso:\*\*/);
    assert.match(seccion, /\*\*Qué falta o cambió:\*\*/);
    assert.doesNotMatch(seccion, /Observado:\s*\{|"resumen_a_p1"|"ids_ajenos"/);
    assert.match(seccion, new RegExp(`API-${181 + i}-`));
  }
  assert.match(secciones[0], /1204 ROJO/);
  assert.match(secciones[0], /EXCLUIDA_DEL_ORACULO/);
  assert.doesNotMatch(secciones[0], /APROBADO \(falló en Newman\)|conciliación del responsable QA/);
  assert.match(secciones[1], /A: 50\+10; B: 3/);
  assert.match(secciones[2], /página 1 VERDE; página 2 ROJO/);
  assert.match(reporte, /PRE-181-01, API-181-03 y API-183-02/);
  assert.doesNotMatch(reporte, /\| — \|/);
});
assert.equal(casos.length, 34);
console.log(`OK G92: ${casos.length}/${casos.length} modos; sin red ni RUN; registro QA fiel`);
