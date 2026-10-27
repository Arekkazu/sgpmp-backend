import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { createRequire } from 'node:module';
import { CAPACIDADES, CASO, ORACULO, DECISION_METODOLOGICA, LIMITE_LECTURAS_DASHBOARD, avisoSesionTerminada, clasificarApi, clasificarUi, evaluarResultadoCypress, decidir } from '../lib/g95_escenario.mjs';
import { preflight, prevalidarHerramientas, informe } from '../g95.mjs';
import { contextoEjecucion } from '../lib/contrato_ejecutor.mjs';
const { elegirUnidad } = createRequire(import.meta.url)('../lib/g95_unidad.cjs');

const contexto = { version: 1, operacion: 'evaluar', runId: 'RUN-G95-V1-20261026-120000',
  contexto: { grupo: 'G95', version: 1, intento: 1, run_id: 'RUN-G95-V1-20261026-120000',
    operacion: 'EVALUAR', referencia: 'AUT-LOCAL', casos: ['TC-M03-186'],
    alcance_reevaluacion: null, version_anterior: null } };
const env = { QA_AUTORIZADO: 'SI', SIGAB_API_TEST_BASE: 'https://www.api.inmero.co/api-sgpmp-test',
  SIGAB_FRONT_TEST_URL: 'https://api.inmero.co/sigab-test', QA_SANDBOX_SECRET: 'sintetico',
  QA_ADMIN_EMAIL: 'admin@example.test', QA_ADMIN_PASSWORD: 'sintetico',
  QA_PROD_EMAIL: 'prod@example.test', QA_PROD_PASSWORD: 'sintetico' };

test('catálogo canónico, oráculo literal y preflight con contexto del lanzador', () => {
  assert.equal(CAPACIDADES.contrato, 'sigab-qa-ejecutor/1');
  assert.deepEqual(CAPACIDADES.casos, ['TC-M03-186']);
  assert.match(ORACULO, /sin pérdida del estado visual/);
  assert.equal(preflight(contexto, env).ok, true);
  assert.equal(preflight(contexto, { ...env, QA_AUTORIZADO: 'NO' }).ok, false);
  assert.deepEqual(Object.keys(contexto.contexto), ['grupo', 'version', 'intento', 'run_id',
    'operacion', 'referencia', 'casos', 'alcance_reevaluacion', 'version_anterior']);
  assert.deepEqual(preflight(contexto, env).efectos_declarados,
    ['login_y_auditoria_fuera_run', 'lecturas_dashboard_y_posible_correo_E7']);
  assert.equal(preflight(contexto, env).barreras.length, 0);
});

test('plan y ejecutor mantienen el sandbox cerrado durante Cypress y Newman', () => {
  const runner = fs.readFileSync(new URL('../g95.mjs', import.meta.url), 'utf8');
  const plan = preflight(contexto, env).plan;
  assert.deepEqual(plan, ['login Administrador fuera del RUN',
    'Cypress Productor fuera del RUN: login, segundo login, UI',
    'Newman Productor fuera del RUN: token y cookie anteriores',
    'GET /usuarios/me Administrador dentro del RUN con eco', 'DELETE RUN y verificar HTTP']);
  const flujo = runner.slice(runner.indexOf('export async function evaluar('));
  const posicion = x => flujo.indexOf(x);
  assert.ok(posicion("'/sesiones/'") < posicion('ejecutarCypress(c,')
    && posicion('ejecutarCypress(c,') < posicion('ejecutarNewman(c,')
    && posicion('ejecutarNewman(c,') < posicion("'/usuarios/me'")
    && posicion("'/usuarios/me'") < posicion("'DELETE'"));
  assert.match(flujo, /catch \(e\) \{ r\.problemas_tecnicos\.push\(`CYPRESS:[^\n]+\); \}/);
  assert.match(flujo, /catch \(e\) \{ r\.problemas_tecnicos\.push\(`NEWMAN:[^\n]+\); \}\s*aperturaIntentada = true/);
  assert.match(flujo, /'X-Test-Run-Id': c\.runId, 'X-Sandbox-Secret': env\.QA_SANDBOX_SECRET/);
  assert.match(flujo, /admin\.eco === c\.runId/);
  assert.match(flujo, /if \(aperturaIntentada\)[\s\S]*?'DELETE'/);
  assert.match(flujo, /else r\.cierre\.motivo = 'RUN_NO_ABIERTO'/);
});

test('Newman usa reporter JSON y HTML local; versiones tienen límite de 30 s', () => {
  const runner = fs.readFileSync(new URL('../g95.mjs', import.meta.url), 'utf8');
  const newman = runner.slice(runner.indexOf('export function ejecutarNewman'),
    runner.indexOf('export async function evaluar'));
  assert.match(newman, /'--reporters', 'json'/);
  assert.doesNotMatch(newman, /htmlextra|reporter-htmlextra/);
  assert.match(newman, /newman-G95\.html/);
  const invocaciones = [];
  const herramientas = prevalidarHerramientas((comando, args, opciones) => {
    invocaciones.push({ comando, args, opciones });
    return { status: 0, stdout: '1.2.3' };
  });
  assert.equal(herramientas.ok, true);
  assert.equal(invocaciones.length, 2);
  for (const { args, opciones } of invocaciones) {
    assert.equal(args.at(-1), '--version');
    assert.equal(opciones.timeout, 30000);
  }
});

test('API distingue rechazo, datos indebidos, infraestructura y falta de respuesta', () => {
  assert.equal(clasificarApi([{ http: 401 }, { http: 410 }]).estado, 'APROBADO');
  assert.equal(clasificarApi([{ http: 200 }, { http: 401 }]).estado, 'RECHAZADO');
  assert.equal(clasificarApi([{ http: 200 }]).estado, 'RECHAZADO');
  assert.equal(clasificarApi([{ http: 401 }, { http: 500 }]).estado, 'BLOQUEADO');
  assert.equal(clasificarApi([{ http: 401 }]).estado, 'NO_CONCLUYENTE');
});

const acta = { caso: CASO, id: 'UI-186-01/UI-186-02', captura: true,
  dashboard_inicial_200: true, auto_on: true, periodica_200: true, filtro_fijado: true,
  segundo_login_200: true, aviso_texto: 'Sesión expirada',
  dashboard_rechazado_401: true, redirigido_login: true, aviso_sesion_terminada: true,
  sin_200_vencida: true, auto_detenido: true, estado_visual_conservado: true,
  retorno_automatico: true, ruta_aterrizaje: '/telemetria/monitoreo', navegacion_manual: false,
  reingreso_200: true, monitoreo_cargado: true, error_interno_visible: false,
  filtro_conservado: true, auto_conservado: true, recarga_200_posterior: true, infra_5xx: false,
  lecturas_dashboard: 5 };

test('UI clasifica cuatro escenarios y exige ejecución y captura reales', () => {
  assert.deepEqual(Object.values(clasificarUi(acta)).map(x => x.estado), ['APROBADO', 'APROBADO']);
  assert.deepEqual(Object.values(clasificarUi({ ...acta, aviso_sesion_terminada: false, recarga_200_posterior: false })).map(x => x.estado), ['RECHAZADO', 'RECHAZADO']);
  assert.deepEqual(Object.values(clasificarUi({ ...acta, recarga_200_posterior: false })).map(x => x.estado), ['APROBADO', 'RECHAZADO']);
  assert.deepEqual(Object.values(clasificarUi({ ...acta, infra_5xx: true })).map(x => x.estado), ['BLOQUEADO', 'BLOQUEADO']);
  assert.deepEqual(Object.values(clasificarUi({ ...acta, dashboard_rechazado_401: false })).map(x => x.estado), ['NO_CONCLUYENTE', 'NO_CONCLUYENTE']);
  assert.deepEqual(Object.values(clasificarUi({ ...acta, auto_on: false })).map(x => x.estado), ['NO_CONCLUYENTE', 'NO_CONCLUYENTE']);
  const resumen = { totalTests: 1, totalPassed: 1, totalFailed: 0,
    totalPending: 0, totalSkipped: 0, specs: 1 };
  assert.equal(evaluarResultadoCypress({ acta, resumen, capturas: ['x.png'] })['UI-186-01'].estado, 'APROBADO');
  assert.equal(evaluarResultadoCypress({ acta, resumen: { ...resumen, totalTests: 0 }, capturas: ['x.png'] })['UI-186-02'].estado, 'ERROR_QA');
  assert.equal(evaluarResultadoCypress({ acta, resumen, capturas: [] })['UI-186-01'].estado, 'ERROR_QA');
});

test('aviso visible acepta equivalencias de significado y rechaza su ausencia', () => {
  for (const aviso_texto of ['Sesión cerrada', 'Tu sesión expiró', 'Inicia sesión nuevamente']) {
    assert.equal(avisoSesionTerminada(aviso_texto), true, aviso_texto);
    assert.equal(clasificarUi({ ...acta, aviso_texto })['UI-186-01'].estado, 'APROBADO');
  }
  assert.equal(avisoSesionTerminada(''), false);
  assert.equal(clasificarUi({ ...acta, aviso_texto: '', aviso_sesion_terminada: false })['UI-186-01'].estado, 'RECHAZADO');
  assert.equal(clasificarUi({ ...acta, aviso_texto: 'Aviso genérico' })['UI-186-01'].estado, 'RECHAZADO');
});

test('seis modos del ensayo conservan los veredictos esperados', () => {
  const modos = [
    ['ok', acta, ['APROBADO', 'APROBADO']],
    ['texto', { ...acta, aviso_texto: 'Sesión cerrada. Ingresa de nuevo.', estado_visual_conservado: false,
      retorno_automatico: false, ruta_aterrizaje: '/dashboard', navegacion_manual: true,
      filtro_conservado: false, auto_conservado: false }, ['APROBADO', 'APROBADO']],
    ['sin_aviso', { ...acta, aviso_texto: '', aviso_sesion_terminada: false,
      estado_visual_conservado: false, retorno_automatico: false }, ['RECHAZADO', 'APROBADO']],
    ['sin_recarga', { ...acta, recarga_200_posterior: false }, ['APROBADO', 'RECHAZADO']],
    ['sesion500', { ...acta, infra_5xx: true }, ['BLOQUEADO', 'BLOQUEADO']],
    ['lento', { ...acta, dashboard_rechazado_401: false }, ['NO_CONCLUYENTE', 'NO_CONCLUYENTE']],
  ];
  for (const [modo, entrada, esperado] of modos) {
    assert.deepEqual(Object.values(clasificarUi(entrada)).map(x => x.estado), esperado, modo);
  }
});

test('aterrizar en dashboard y cargar monitoreo con GET nuevo 200 aprueba con observaciones', () => {
  const ui = clasificarUi({ ...acta, ruta_aterrizaje: '/dashboard', navegacion_manual: true,
    retorno_automatico: false, filtro_conservado: false, auto_conservado: false });
  assert.equal(ui['UI-186-02'].estado, 'APROBADO');
  assert.equal(ui['UI-186-02'].observaciones.length, 3);
});

test('sin recarga 200 o con error interno visible rechaza UI-186-02', () => {
  assert.equal(clasificarUi({ ...acta, recarga_200_posterior: false })['UI-186-02'].estado, 'RECHAZADO');
  assert.equal(clasificarUi({ ...acta, error_interno_visible: true })['UI-186-02'].estado, 'RECHAZADO');
});

test('observaciones UX no cambian el veredicto', () => {
  for (const cambios of [
    { filtro_conservado: false }, { auto_conservado: false },
    { ruta_aterrizaje: '/dashboard', navegacion_manual: true, retorno_automatico: false },
  ]) assert.equal(clasificarUi({ ...acta, ...cambios })['UI-186-02'].estado, 'APROBADO');
});

test('equivalencia aceptada; ninguna aprobación sin UI, cierre o cobertura', () => {
  const cs = CAPACIDADES.comprobaciones_obligatorias[CASO];
  const checks = [...cs.API, ...cs.UI].map(id => ({ id, estado: 'APROBADO' }));
  const datos = { uiPruebas: 1, captura: true, cierreHttp: 200 };
  assert.equal(decidir(checks, datos), 'APROBADO');
  assert.match(DECISION_METODOLOGICA.texto, /Acepto el segundo login real/);
  assert.equal(decidir(checks, { ...datos, equivalenciaAprobada: false }), 'APROBADO');
  assert.equal(decidir(checks, { ...datos, uiPruebas: 0 }), 'NO_CONCLUYENTE');
  assert.equal(decidir(checks, { ...datos, captura: false }), 'NO_CONCLUYENTE');
  assert.equal(decidir(checks.map(x => x.id === 'UI-186-01' ? { ...x, estado: 'RECHAZADO' } : x), datos), 'RECHAZADO');
});

test('contrato rechaza contexto ausente sin crear RUN', () => {
  assert.throws(() => contextoEjecucion([], { grupo: 'G95', casos: [CASO], directorio: '.' }));
});

test('informe futuro comienza por decisión e incluye método y aviso exacto', () => {
    const r = { grupo: 'G95', run_id: contexto.runId, version: 1, autorizacion: 'AUT-LOCAL',
      frontend_referencia: 'SGPMP-FRONT-END-PWA origin/test 81058af57d5d80d523fb5225f8eab48e0307ba85',
      casos: { [CASO]: { estado: 'RECHAZADO', motivo: 'Discrepancia pública acreditada' } },
      comprobaciones: [
        { id: 'API-186-01', estado: 'APROBADO', fuente: 'API', motivo: '401/401' },
        { id: 'UI-186-01', estado: 'RECHAZADO', fuente: 'UI', motivo: 'aviso ausente' },
        { id: 'UI-186-02', estado: 'RECHAZADO', fuente: 'UI', motivo: 'sin recarga', observaciones: ['Reingreso aterrizó en /dashboard', 'Filtro por unidad no conservado'] },
      ], evidencias: [], observado: { ui: {} }, problemas_tecnicos: [],
      cypress: { total_pruebas: 1 }, cierre: { run: { cierre_http: 200 },
        rollback: { verificado: false, estado: 'NO_VERIFICADO', motivo: 'Sin comprobación' }, motivo: 'Sin cierre' },
      equivalencia_aprobada: true, preflight_herramientas: {}, consume_version: true };
    r.observado.ui.aviso_texto = 'Sesión cerrada. Iniciaste sesión desde otro dispositivo.';
    const md = informe(r);
    assert.match(md, /^# TC-M03-G95 — RECHAZADO\n\n## Decisión del caso/);
    assert.match(md, /## Decisiones metodológicas/);
    assert.match(md, /Sí, ajusta UI-186-02/);
    assert.match(md, /Especificacion-Requerimientos-Modulo3.md:5338-5350,5442-5446/);
    assert.match(md, /## Observaciones\n\n- Reingreso aterrizó en \/dashboard/);
    assert.match(md, /Sesión cerrada o sesión expirada dan a entender lo mismo/);
    assert.match(md, /Iniciaste sesión desde otro dispositivo/);
    assert.match(md, /frontend de referencia SGPMP-FRONT-END-PWA origin\/test 81058af57d5d80d523fb5225f8eab48e0307ba85/);
    assert.equal(md.includes('DEFECTO_FUNCIONAL_CANDIDATO'), false);
});

test('spec activa Auto por clic, guarda aviso y no envía cabeceras del RUN del Productor', () => {
  const spec = fs.readFileSync(new URL('../g95.cy.js', import.meta.url), 'utf8');
  const config = fs.readFileSync(new URL('../g95.cypress.config.cjs', import.meta.url), 'utf8');
  const runner = fs.readFileSync(new URL('../g95.mjs', import.meta.url), 'utf8');
  assert.match(spec, /Auto OFF[\s\S]*cy\.wrap\(boton\)\.click\(\)/);
  assert.match(spec, /aviso_texto =/);
  assert.match(spec, /periodica_200/);
  assert.doesNotMatch(spec + config, /X-Test-Run-Id|X-Sandbox-Secret/);
  assert.match(runner, /'API-186-01'/);
  assert.doesNotMatch(runner.slice(runner.indexOf('const vars = { CYPRESS_'), runner.indexOf('export function ejecutarNewman')), /X-Test-Run-Id|X-Sandbox-Secret/);
});

test('paginación permite unidad acreditada y registra riesgo E7 en fallback', () => {
  const resumen_unidades = [
    { id_infraestructura: 7, total_sensores: 2 },
    { id_infraestructura: 8, total_sensores: 1 },
  ];
  const pagina = { total: 70, resumen_unidades, sensores: [
    { id_infraestructura: 7, estado_semaforo: 'VERDE', dato_desactualizado: false },
    { id_infraestructura: 8, estado_semaforo: 'VERDE', dato_desactualizado: false },
  ] };
  assert.deepEqual([elegirUnidad(pagina).id, elegirUnidad(pagina).e7_riesgo,
    elegirUnidad(pagina).bloqueo_datos], [8, false, null]);
  const incompleta = { ...pagina, sensores: pagina.sensores.slice(0, 1) };
  assert.deepEqual([elegirUnidad(incompleta).id, elegirUnidad(incompleta).e7_riesgo,
    elegirUnidad(incompleta).bloqueo_datos], [7, true, null]);
  assert.match(elegirUnidad(incompleta).motivo, /E7/);
});

test('resumen vacío bloquea; presupuesto de dashboard excedido es ERROR_QA', () => {
  assert.equal(LIMITE_LECTURAS_DASHBOARD, 6);
  const vacio = elegirUnidad({ total: 70, resumen_unidades: [], sensores: [] });
  assert.equal(vacio.bloqueo_datos, 'RESUMEN_UNIDADES_VACIO');
  assert.deepEqual(Object.values(clasificarUi({ ...acta, bloqueo_datos: vacio.bloqueo_datos }))
    .map(x => x.estado), ['BLOQUEADO', 'BLOQUEADO']);
  assert.deepEqual(Object.values(clasificarUi({ ...acta, lecturas_dashboard: LIMITE_LECTURAS_DASHBOARD })).map(x => x.estado),
    ['APROBADO', 'APROBADO']);
  assert.deepEqual(Object.values(clasificarUi({ ...acta, lecturas_dashboard: LIMITE_LECTURAS_DASHBOARD + 1 }))
    .map(x => x.estado), ['ERROR_QA', 'ERROR_QA']);
  assert.deepEqual(Object.values(clasificarUi({ ...acta, lecturas_dashboard: undefined }))
    .map(x => x.estado), ['ERROR_QA', 'ERROR_QA']);
});

test('selector de Área corresponde al spec preparado para origin/test', () => {
  const spec = fs.readFileSync(new URL('../g95.cy.js', import.meta.url), 'utf8');
  assert.match(spec, /cy\.contains\('label', \/\^Área\$\//);
  assert.match(spec, /input\[role=\"combobox\"\]/);
  assert.match(spec, /\.type\(String\(id\)\)/);
  assert.doesNotMatch(spec, /input\[type=\"number\"\]/);
});

test('Auto ON inicial se verifica sin pulsarlo', () => {
  const spec = fs.readFileSync(new URL('../g95.cy.js', import.meta.url), 'utf8');
  assert.match(spec, /if \(\/Auto OFF\/\.test\(boton\.textContent/);
  assert.match(spec, /contains\(\/\^Auto ON\$\//);
});

test('error de selector conserva etapa y selector y se clasifica ERROR_QA', () => {
  const fallo = { ...acta, error_selector: { etapa: 'combobox_area', selector: 'input[role="combobox"]' } };
  const estados = clasificarUi(fallo);
  assert.equal(estados['UI-186-01'].estado, 'ERROR_QA');
  assert.match(estados['UI-186-02'].motivo, /ERROR_SELECTOR:combobox_area:input/);
});

test('GRIS vigente descarta unidad segura; GRIS desactualizado permite elegirla', () => {
  const resumen_unidades = [
    { id_infraestructura: 7, total_sensores: 1 },
    { id_infraestructura: 8, total_sensores: 1 },
  ];
  const gris = { id_infraestructura: 7, estado_semaforo: 'GRIS', dato_desactualizado: false };
  const verde = { id_infraestructura: 8, estado_semaforo: 'VERDE', dato_desactualizado: false };
  assert.deepEqual([elegirUnidad({ resumen_unidades, sensores: [gris, verde] }).id,
    elegirUnidad({ resumen_unidades, sensores: [gris, verde] }).e7_riesgo], [8, false]);
  assert.deepEqual([elegirUnidad({ resumen_unidades, sensores: [gris] }).id,
    elegirUnidad({ resumen_unidades, sensores: [gris] }).e7_riesgo], [7, true]);
  assert.deepEqual([elegirUnidad({ resumen_unidades, sensores: [{ ...gris, dato_desactualizado: true }] }).id,
    elegirUnidad({ resumen_unidades, sensores: [{ ...gris, dato_desactualizado: true }] }).e7_riesgo], [7, false]);
});

test('contrato del registro QA clasifica resultado.json sintético completo y rechaza faltantes', () => {
  const informeNombre = 'TC-M03-G95_resultado.md';
  const archivos = new Set([informeNombre, 'resultado.json', 'cypress/UI-186-01.png',
    'cypress/UI-186-01.json', 'newman/newman-G95.json']);
  const ids = CAPACIDADES.comprobaciones_obligatorias[CASO];
  const base = {
    run_id: contexto.runId, version: 1, oficial: true, consume_version: true,
    cierre: { run: { cierre_http: 200 }, rollback: { verificado: true } },
    casos: { [CASO]: { estado: 'RECHAZADO' } },
    comprobaciones: [...ids.API.map(id => ({ caso: CASO, fuente: 'API', id, tipo: 'ASSERT', estado: 'APROBADO' })),
      ...ids.UI.map(id => ({ caso: CASO, fuente: 'UI', id, tipo: 'ASSERT', estado: 'RECHAZADO' }))],
    cypress: { total_pruebas: 1 },
    evidencias: ['resultado.json', informeNombre, 'cypress/UI-186-01.png',
      'cypress/UI-186-01.json', 'newman/newman-G95.json'],
  };
  const conforme = (obj, presentes = archivos) => {
    const r = JSON.parse(JSON.stringify(obj));
    const checks = [...ids.API.map(id => [id, 'API']), ...ids.UI.map(id => [id, 'UI'])];
    return r.run_id === contexto.runId && r.version === contexto.version
      && r.cierre?.run?.cierre_http === 200 && r.cierre?.rollback?.verificado === true
      && typeof r.consume_version === 'boolean'
      && JSON.stringify(Object.keys(r.casos).sort()) === JSON.stringify([CASO])
      && ['APROBADO', 'RECHAZADO'].includes(r.casos[CASO].estado)
      && checks.every(([id, fuente]) => r.comprobaciones.some(x => x.caso === CASO
        && x.fuente === fuente && x.id === id && x.tipo === 'ASSERT'
        && ['APROBADO', 'RECHAZADO'].includes(x.estado)))
      && r.cypress?.total_pruebas > 0 && presentes.has(informeNombre)
      && r.evidencias.every(x => typeof x === 'string' && !x.includes('..')
        && !/^[/\\]|^[A-Za-z]:/.test(x) && presentes.has(x))
      && r.oficial === true;
  };
  assert.equal(conforme(base), true, 'RUN completo con caso RECHAZADO es OFICIAL');
  const uiInconclusa = structuredClone(base);
  uiInconclusa.comprobaciones.find(x => x.id === 'UI-186-01').estado = 'NO_CONCLUYENTE';
  assert.equal(conforme(uiInconclusa), false);
  assert.equal(conforme({ ...base, cierre: { ...base.cierre, run: { cierre_http: 500 } } }), false);
  assert.equal(conforme({ ...base, evidencias: ['../fuera.json'] }), false);
  assert.equal(conforme({ ...base, evidencias: ['inexistente.json'] }), false);
});
