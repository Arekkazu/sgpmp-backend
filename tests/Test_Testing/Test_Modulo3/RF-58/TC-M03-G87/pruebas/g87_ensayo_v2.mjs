// Ensayo V2 en memoria: no usa red, credenciales, carpetas RUN ni procesos hijo.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import { alcanceCuenta, alcanceV2, rolesParaOperacion, veredictos, versionNewmanLocal } from '../g87.mjs';
import { generarInforme, oficialidad, validarResultadoLocal } from '../lib/g87_informe.mjs';
import { cerrarYVerificar } from '../lib/g87_cierre.mjs';

const ids = {
  'TC-M03-168': { API: [1, 2, 3, 4, 5] },
  'TC-M03-177': { API: [1, 2, 3], UI: [1, 2, 3] },
  'TC-M03-178': { API: [1, 2, 3, 4, 5, 6, 7], UI: [1, 2, 3, 4, 5] },
};
const defs = Object.fromEntries(Object.keys(ids).map((id) => [id, { titulo: id }]));
function base() {
  const comprobaciones = Object.entries(ids).flatMap(([caso, fuentes]) => Object.entries(fuentes).flatMap(([fuente, ns]) =>
    ns.map((n) => ({ caso, fuente, tipo: 'ASSERT', id: `${fuente}-${caso.slice(-3)}-0${n}`,
      descripcion: 'Criterio V1 preservado', ok: true, obtenido: 'conforme' }))));
  return { grupo: 'TC-M03-G87', version: 2, intento: 1, run_id: 'RUN-G87-V2-20261030-120000',
    operacion: 'REEVALUAR', referencia: 'ENSAYO_LOCAL', ambiente: 'SINTÉTICO', estado: 'CONCLUIDA',
    inicio: '2026-10-30T12:00:00Z', fin: '2026-10-30T12:01:00Z', consume_version: true,
    alcance_reevaluacion: { version_anterior: 1, casos: Object.keys(ids) },
    comprobaciones, casos: {}, incidencias: [], cypress: { total_pruebas: 8 },
    datos: { finca: 184, area: 349, s1: { id: 552 }, s2: { id: 77 },
      alcance_cuentas: { prod: alcanceCuenta({ nombre_rol: 'Productor', fincas: [{ id_finca: 184 }] }, 'prod', 184),
        eng: alcanceCuenta({ nombre_rol: 'Ingeniero de Campo', fincas: [{ id_finca: 184 }] }, 'eng', 184) },
      lecturas: { v_a1: 23, v_a2: 24, v_a3: 25, v_fuera: 31, v_c1: 21.7, v_c2: 22.3 },
      visibilidad_por_rol: { prod: { finca_asignada: true, http: 200, s1: true, s2: true },
        eng: { finca_asignada: true, http: 200, s1: true, s2: true } },
      contrato_dashboard: { prod: { s1: { ultimo_valor: 25, estado_calidad: 'FUERA_DE_RANGO', indicador_anomalia: true },
        s2: { ultimo_valor: null, etiqueta_estado: 'En revisión técnica' } },
      eng: { s2: { ultimo_valor: null, estado_calidad: 'ERROR_CALIBRACION', etiqueta_estado: 'Requiere calibración' } } } },
    cierre: { run: { cierre_http: 200 }, rollback: { verificado: true, historial: { 552: {}, 77: {} } } },
    newman: { solicitudes: 9, aserciones: 15, fallidas: 0 },
    herramientas: { node: process.version, newman: versionNewmanLocal() }, evidencias: ['resultado.json'] };
}
const escenarios = {
  todo_corregido: { esperado: ['APROBADO', 'APROBADO', 'APROBADO'], oficial: true },
  ui_login_completo: { esperado: ['APROBADO', 'APROBADO', 'APROBADO'], oficial: true },
  ui_flujo_completo: { esperado: ['APROBADO', 'APROBADO', 'APROBADO'], oficial: true },
  ui_captura_insuficiente: { esperado: ['APROBADO', 'ERROR_QA', 'APROBADO'], oficial: false,
    cambiar: (r) => {
      const x = r.comprobaciones.find((c) => c.id === 'UI-177-01');
      x.ok = false; x.naturaleza = 'AUTOMATIZACION';
      x.obtenido = 'ERROR_QA_EVIDENCIA: TC-M03-177_productor_S1: captura insuficiente: 1x1, 89 bytes';
      r.incidencias.push(`ERROR_QA: ${x.obtenido}`);
    } },
  ui_filtro_area_no_encontrado: { esperado: ['APROBADO', 'BLOQUEADO', 'BLOQUEADO'], oficial: false,
    cambiar: (r) => {
      r.cypress.total_pruebas = 11;
      r.evidencias.push('cypress/PRE-UI-01_filtro_area_fallo.png');
      for (const caso of ['TC-M03-177', 'TC-M03-178']) {
        r.comprobaciones.push({ caso, fuente: 'UI', tipo: 'PRE', id: 'PRE-UI-01', ok: false,
          naturaleza: 'AUTOMATIZACION', obtenido: 'Combobox de Área no encontrado; captura de fallo conservada.' });
      }
      for (const x of r.comprobaciones.filter((c) => c.fuente === 'UI' && c.tipo === 'ASSERT')) x.ok = null;
    } },
  ui_menu_no_habilita: { esperado: ['APROBADO', 'BLOQUEADO', 'BLOQUEADO'], oficial: false,
    cambiar: (r) => {
      r.cypress.total_pruebas = 0;
      for (const caso of ['TC-M03-177', 'TC-M03-178']) {
        r.comprobaciones.push({ caso, fuente: 'UI', tipo: 'PRE', id: 'PRE-UI-01', ok: false,
          naturaleza: 'AUTOMATIZACION', obtenido: 'Navegación UI fallida' });
      }
      for (const x of r.comprobaciones.filter((c) => c.fuente === 'UI')) x.ok = x.tipo === 'PRE' ? false : null;
    } },
  cuentas_ui_para_api: { esperado: ['APROBADO', 'APROBADO', 'APROBADO'], oficial: true,
    cambiar: (r) => { r.datos.cuentas_api = 'cuentas UI del mismo rol (Productor e Ingeniero de Campo)'; } },
  cuenta_ui_sin_finca: { esperado: ['NO_CONCLUYENTE', 'NO_CONCLUYENTE', 'NO_CONCLUYENTE'], oficial: false,
    cambiar: (r) => { r.datos.alcance_cuentas.prod = alcanceCuenta({ nombre_rol: 'Productor', fincas: [] }, 'prod', 184); } },
  cuenta_ui_rol_incorrecto: { esperado: ['APROBADO', 'APROBADO', 'NO_CONCLUYENTE'], oficial: false,
    cambiar: (r) => { r.datos.alcance_cuentas.eng = alcanceCuenta({ nombre_rol: 'Productor', fincas: [{ id_finca: 184 }] }, 'eng', 184); } },
  persiste_177_api: { fallos: ['API-177-03'], esperado: ['APROBADO', 'RECHAZADO', 'APROBADO'] },
  persiste_177_ui: { fallos: ['UI-177-03'], esperado: ['APROBADO', 'RECHAZADO', 'APROBADO'] },
  persiste_178_api: { fallos: ['API-178-06'], esperado: ['APROBADO', 'APROBADO', 'RECHAZADO'] },
  persiste_178_ui: { fallos: ['UI-178-05'], esperado: ['APROBADO', 'APROBADO', 'RECHAZADO'] },
  regresion_168: { fallos: ['API-168-03', 'API-177-02'], esperado: ['RECHAZADO', 'RECHAZADO', 'APROBADO'] },
  productor_ve_datos_tecnicos: { fallos: ['API-178-04', 'UI-178-03'], esperado: ['APROBADO', 'APROBADO', 'RECHAZADO'] },
  contrato_sin_campos_nuevos: { esperado: ['APROBADO', 'APROBADO', 'APROBADO'], oficial: true,
    cambiar: (r) => { r.datos.contrato_dashboard.prod.s1.indicador_anomalia = 'CAMPO_AUSENTE'; } },
  sensor_no_visible_por_finca: { esperado: ['APROBADO', 'APROBADO', 'NO_CONCLUYENTE'],
    cambiar: (r) => { r.datos.visibilidad_por_rol.eng = { finca_asignada: false, http: 200, s1: false, s2: false };
      for (const x of r.comprobaciones.filter((c) => /^API-178-0[567]$|^UI-178-0[45]$/.test(c.id))) x.ok = false; } },
  sensor_no_visible_con_finca: { fallos: ['API-178-05'], esperado: ['APROBADO', 'APROBADO', 'RECHAZADO'],
    cambiar: (r) => { r.datos.visibilidad_por_rol.eng.s2 = false; } },
  s1_no_preparable: { esperado: ['BLOQUEADO', 'BLOQUEADO', 'APROBADO'], cambiar: (r) => {
    r.comprobaciones = r.comprobaciones.filter((x) => x.caso === 'TC-M03-178');
    for (const caso of ['TC-M03-168', 'TC-M03-177']) r.comprobaciones.push({ caso, tipo: 'PRE', fuente: 'API', id: 'PRE-S1-DATOS', ok: false, naturaleza: 'DATOS', obtenido: 'S1 no preparable' });
  } },
  s2_no_preparable: { esperado: ['APROBADO', 'APROBADO', 'BLOQUEADO'], cambiar: (r) => {
    r.comprobaciones = r.comprobaciones.filter((x) => x.caso !== 'TC-M03-178');
    r.comprobaciones.push({ caso: 'TC-M03-178', tipo: 'PRE', fuente: 'API', id: 'PRE-178-DATOS', ok: false, naturaleza: 'DATOS', obtenido: 'S2 no preparable' });
  } },
  login_fallido: { vacio: true, esperado: ['BLOQUEADO', 'BLOQUEADO', 'BLOQUEADO'] },
  clave_403: { esperado: ['BLOQUEADO', 'BLOQUEADO', 'BLOQUEADO'],
    cambiar: (r) => { for (const x of r.comprobaciones) { x.ok = x.fuente === 'UI' ? null : false; x.naturaleza = 'ENTORNO'; } } },
  error5xx: { esperado: ['BLOQUEADO', 'BLOQUEADO', 'BLOQUEADO'],
    cambiar: (r) => { for (const x of r.comprobaciones) { x.ok = x.fuente === 'UI' ? null : false; x.naturaleza = 'ENTORNO'; } } },
  corte_con_cierre: { esperado: ['APROBADO', 'APROBADO', 'APROBADO'], cambiar: (r) => { r.cierre.rollback.verificado = false; } },
  newman_no_disponible: { vacio: true, esperado: ['BLOQUEADO', 'BLOQUEADO', 'BLOQUEADO'] },
  cypress_no_disponible: { esperado: ['APROBADO', 'BLOQUEADO', 'BLOQUEADO'],
    cambiar: (r) => { r.cypress.total_pruebas = 0; for (const x of r.comprobaciones.filter((c) => c.fuente === 'UI')) x.ok = null; } },
};
let aprobados = 0;
for (const [modo, plan] of Object.entries(escenarios)) {
  const r = base();
  if (plan.vacio) r.comprobaciones = [];
  for (const x of r.comprobaciones.filter((c) => plan.fallos?.includes(c.id))) { x.ok = false; x.obtenido = 'diferencia sintética'; }
  plan.cambiar?.(r);
  veredictos(r);
  const actuales = Object.values(r.casos).map((x) => x.estado);
  assert.deepEqual(actuales, plan.esperado, modo);
  r.oficial = oficialidad(r);
  assert.equal(r.oficial, plan.oficial ?? (!plan.vacio && !['corte_con_cierre', 'sensor_no_visible_por_finca', 'cypress_no_disponible', 'clave_403', 'error5xx', 's1_no_preparable', 's2_no_preparable'].includes(modo)), modo);
  const md = generarInforme(r, defs);
  assert.ok(md.includes('V1 → V2; casos'), modo);
  assert.ok(md.includes(`Newman ${versionNewmanLocal()}`), modo);
  if (modo === 'ui_captura_insuficiente') assert.ok(md.includes('Problemas técnicos: ERROR_QA: ERROR_QA_EVIDENCIA'), modo);
  assert.ok(md.startsWith('# REEVALUACIÓN V2 — TC-M03-G87 — '), modo);
  assert.ok(md.includes('REF-G87-01:') && md.includes('REF-G87-02:'), modo);
  assert.match(md, /cuentas UI del mismo rol también en API/);
  assert.doesNotMatch(md, /[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}/);
  assert.deepEqual(validarResultadoLocal(r, ['TC-M03-G87_reevaluacion_V2.md'], null, md), [], modo);
  aprobados++;
}
assert.equal(alcanceV2({ version: 2, operacion: 'reintentar', contexto: {
  version_anterior: 1, alcance_reevaluacion: { casos: Object.keys(ids), version_anterior: 1 } } }).version_anterior, 1);
assert.equal(alcanceV2({ version: 2, operacion: 'reevaluar', contexto: {
  version_anterior: 1, alcance_reevaluacion: { casos: Object.keys(ids) } } }).version_anterior, 1);
assert.match(versionNewmanLocal(), /^\d+\.\d+\.\d+/);

// El task de Cypress se ejercita con un filesystem PNG simulado en memoria.
const png = (ancho, alto, bytes = 300) => {
  const b = Buffer.alloc(bytes);
  Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]).copy(b);
  b.writeUInt32BE(ancho, 16); b.writeUInt32BE(alto, 20);
  return b;
};
const capturas = new Map();
const tareas = {};
let lanzamiento;
let despuesCaptura;
const moduloConfig = { exports: {} };
vm.runInNewContext(fs.readFileSync(new URL('../g87.cypress.config.cjs', import.meta.url), 'utf8'), {
  module: moduloConfig, Buffer,
  require: (nombre) => nombre === 'node:fs' ? {
    existsSync: (ruta) => capturas.has(ruta), readFileSync: (ruta) => capturas.get(ruta),
  } : nombre === 'node:path' ? path : null,
});
moduloConfig.exports.e2e.setupNodeEvents((evento, registros) => {
  if (evento === 'task') Object.assign(tareas, registros);
  if (evento === 'before:browser:launch') lanzamiento = registros;
  if (evento === 'after:screenshot') despuesCaptura = registros;
}, { screenshotsFolder: 'capturas', viewportWidth: 1440, viewportHeight: 900, env: {} });
const chrome = lanzamiento({ name: 'chrome', family: 'chromium' },
  { args: ['--window-size=1280,720'], preferences: {} });
assert.equal(chrome.args.filter((a) => a.startsWith('--window-size=')).join(), '--window-size=1600,1000');
const electron = lanzamiento({ name: 'electron', family: 'chromium' }, { args: [], preferences: {} });
assert.equal(electron.preferences.width, 1600);
assert.equal(electron.preferences.height, 1000);
const rutaPng = (archivo) => path.join('capturas', 'g87.cy.js', `${archivo}.png`);
assert.equal(tareas.verificarCapturaG87('TC-M03-177_productor_S1').ok, false);
capturas.set(rutaPng('TC-M03-177_productor_S1'), png(1, 1, 89));
assert.equal(tareas.verificarCapturaG87('TC-M03-177_productor_S1').ok, false);
capturas.set(rutaPng('TC-M03-177_productor_S1'), png(1000, 48));
assert.equal(tareas.verificarCapturaG87('TC-M03-177_productor_S1').ok, false);
capturas.set(rutaPng('TC-M03-177_productor_S1'), png(1440, 900));
assert.equal(tareas.verificarCapturaG87('TC-M03-177_productor_S1').ok, true);
despuesCaptura({ path: rutaPng('TC-M03-177_productor_S1'), scaled: true });
assert.equal(tareas.verificarCapturaG87('TC-M03-177_productor_S1').ok, false);
despuesCaptura({ path: rutaPng('TC-M03-177_productor_S1'), scaled: false });
assert.equal(tareas.verificarCapturaG87('TC-M03-177_productor_S1').ok, true);
assert.equal(tareas.verificarCapturaG87('../fuera').ok, false);
const coleccion = JSON.parse(fs.readFileSync(new URL('../G87.postman_collection.json', import.meta.url), 'utf8'));
const scriptProductor = coleccion.item.find((x) => x.name === 'Dashboard del Productor').event.find((x) => x.listen === 'test').script.exec.join('\n');
function criterioProductor(id, s1, s2 = { id_sensor: 77 }) {
  let ejecutado = false;
  const variables = { s1_id: 552, s2_id: 77, s1_ejecutar: 'SI', s2_ejecutar: 'SI', v_a3: 25, v_c1: 21.7, v_c2: 22.3 };
  const pm = { response: { code: 200, json: () => ({ sensores: [s1, s2] }) },
    environment: { get: (k) => variables[k] },
    test: (titulo, fn) => { if (titulo.includes(`[${id}]`)) { ejecutado = true; fn(); } },
    expect: (actual) => ({ to: { eql: (esperado) => assert.equal(actual, esperado) } }) };
  vm.runInNewContext(scriptProductor, { pm });
  assert.equal(ejecutado, true, id);
}
criterioProductor('API-177-03', { id_sensor: 552, ultimo_valor: 25, indicador_anomalia: true });
assert.throws(() => criterioProductor('API-177-03', { id_sensor: 552, ultimo_valor: 31, indicador_anomalia: true }));
assert.throws(() => criterioProductor('API-177-03', { id_sensor: 552, ultimo_valor: 25, estado_semaforo: 'VERDE' }));
criterioProductor('API-178-04', { id_sensor: 552 }, { id_sensor: 77, etiqueta_estado: 'En revisión técnica' });
assert.throws(() => criterioProductor('API-178-04', { id_sensor: 552 }, { id_sensor: 77, estado_calidad: 'ERROR_CALIBRACION' }));
assert.match(fs.readFileSync(new URL('../g87.mjs', import.meta.url), 'utf8'), /EvaluacionV\$\{version\}.*Resultados/);
assert.deepEqual(rolesParaOperacion(2, 'reevaluar'), ['admin', 'ui_prod', 'ui_eng']);
assert.deepEqual(rolesParaOperacion(1, 'evaluar'), ['admin', 'prod', 'eng', 'ui_prod', 'ui_eng']);
const spec = fs.readFileSync(new URL('../g87.cy.js', import.meta.url), 'utf8');
assert.match(spec, /const DASHBOARD_REQUEST_TIMEOUT = 90000;/);
for (const alias of ['dashboard', 'dashboardArea'])
  assert.ok(spec.includes(`cy.wait('@${alias}', { requestTimeout: DASHBOARD_REQUEST_TIMEOUT })`),
    `espera explícita de ${alias} durante carga inicial lenta`);
const definicionPill = spec.match(/function etiquetaAnomaliaRecortada\([\s\S]*?\n\}/)?.[0];
assert.ok(definicionPill, 'control de recorte de la píldora');
const pillRecortada = vm.runInNewContext(`${definicionPill}\netiquetaAnomaliaRecortada`);
const vistaPill = { innerWidth: 1440, innerHeight: 900, getComputedStyle: (e) => e.estilo };
const pill = (caja, clientWidth, scrollWidth, overflowX = 'visible') => ({
  getBoundingClientRect: () => caja, clientWidth, scrollWidth, clientHeight: 16, scrollHeight: 16,
  estilo: { overflowX, overflowY: 'visible' },
});
assert.equal(pillRecortada(pill({ width: 150, height: 16, top: 100, bottom: 116, left: 20, right: 170 },
  0, 150), vistaPill), false, 'píldora inline completa de 16 px');
assert.equal(pillRecortada(pill({ width: 70, height: 16, top: 100, bottom: 116, left: 20, right: 90 },
  70, 150, 'hidden'), vistaPill), true, 'píldora con texto recortado');
assert.equal(pillRecortada(pill({ width: 150, height: 16, top: 100, bottom: 116, left: 1350, right: 1500 },
  0, 150), vistaPill), true, 'píldora fuera de la ventana');
const ejecutor = fs.readFileSync(new URL('../g87.mjs', import.meta.url), 'utf8');
const rutasSpec = spec.match(/^const (?:FRONT|BASE|ORIGEN_FRONT) = .*;$/gm);
assert.equal(rutasSpec?.length, 3);
for (const [baseUrl, prefijo] of [
  ['http://127.0.0.1:4173', ''],
  ['https://ejemplo.invalid/sigab-test', '/sigab-test'],
  ['https://ejemplo.invalid/sigab-test/', '/sigab-test'],
]) {
  const rutas = vm.runInNewContext(`${rutasSpec.join('\n')}\n({ base: BASE, origin: ORIGEN_FRONT,
    dashboard: \`\${BASE}/dashboard\`, monitoreo: \`\${BASE}/telemetria/monitoreo\` })`,
  { Cypress: { config: () => baseUrl }, URL });
  assert.equal(rutas.base, prefijo, baseUrl);
  assert.equal(rutas.origin, new URL(baseUrl).origin, baseUrl);
  assert.equal(rutas.dashboard, `${prefijo}/dashboard`, baseUrl);
  assert.equal(rutas.monitoreo, `${prefijo}/telemetria/monitoreo`, baseUrl);
}
assert.match(ejecutor, /respuestasLoginUi\[rol\] = l\.json/);
assert.match(ejecutor, /PROD_LOGIN: escenarioV2 \? respuestasLoginUi\.ui_prod/);
assert.match(ejecutor, /ENG_LOGIN: escenarioV2 \? respuestasLoginUi\.ui_eng/);
assert.match(spec, /req\.reply\(\{ statusCode: 200, body: respuesta \}\)/);
assert.match(spec, /cy\.visit\(`\$\{FRONT\}\/login`/);
assert.match(spec, /url\.origin === ORIGEN_FRONT/);
assert.match(spec, /should\('eq', `\$\{BASE\}\/dashboard`\)/);
assert.match(spec, /win\.history\.pushState\(\{\}, '', `\$\{BASE\}\/telemetria\/monitoreo`\)/);
assert.match(spec, /should\('eq', `\$\{BASE\}\/telemetria\/monitoreo`\)/);
assert.match(spec, /win\.dispatchEvent\(new win\.PopStateEvent\('popstate'\)\)/);
assert.match(spec, /cy\.contains\('label', \/\^Área\$\//);
assert.match(spec, /combobox de monitoreo/);
assert.doesNotMatch(spec, /input\[type="number"\]/);
assert.match(fs.readFileSync(new URL('../g87.cypress.config.cjs', import.meta.url), 'utf8'), /screenshotOnRunFailure: true/);
assert.match(ejecutor, /fs\.cpSync\(capturas, path\.join\(dir, 'cypress'\)/);
assert.doesNotMatch(spec, /have\.attr', 'aria-disabled'/);
assert.match(spec, /else req\.continue\(\); \/\/ V1/);
const datosCierre = { area: 349, ocupacion_inicial: 3, s1: { id: 552, area_original: 349 }, bloqueo_s2: true,
  lecturas: { ts: { a: '2026-10-30T12:00:00Z' } }, ids_telemetria: [] };
async function ensayoCierre(fallaLogin) {
  const peticiones = [];
  const tokens = { admin: 'token-inicial-invalido' };
  const cierre = await cerrarYVerificar({ runId: 'RUN-SINTETICO', secreto: 'secreto-sintetico', datos: datosCierre,
    tokens, credenciales: { admin: { correo: 'cuenta-sintetica', clave: 'clave-sintetica' } },
    solicitar: async (metodo, ruta, opciones) => {
      peticiones.push({ metodo, ruta, token: opciones.token });
      if (metodo === 'DELETE') return { status: 200 };
      if (metodo === 'POST') return fallaLogin ? { status: 401 } : { status: 200, json: { token: 'token-nuevo' } };
      if (ruta === '/usuarios/me') return { status: 0, error: 'TIMEOUT 30 s' };
      assert.equal(opciones.token, 'token-nuevo');
      if (ruta.includes('/asociaciones')) return { status: 200, json: { items: [{ id_infraestructura: 349 }] } };
      if (ruta.includes('/dashboard')) return { status: 200, json: { total: 3 } };
      if (ruta.includes('/historial')) return { status: 200, json: { total: 0, items: [] } };
      throw Error('Ruta sintética inesperada');
    } });
  assert.deepEqual(peticiones.slice(0, 3).map((p) => p.metodo), ['DELETE', 'GET', 'POST']);
  assert.equal(cierre.run.cierre_http, 200);
  assert.equal(cierre.rollback.verificado, !fallaLogin);
  assert.equal(cierre.rollback.conclusion, fallaLogin ? 'NO_CONCLUYENTE' : 'ROLLBACK_CONFIRMADO');
  const resultado = base();
  resultado.cierre = cierre;
  veredictos(resultado);
  assert.equal(oficialidad(resultado), !fallaLogin);
  if (fallaLogin) assert.match(cierre.errores.join(' '), /Administrador sin sesión vigente/);
  else {
    assert.equal(cierre.rollback.asociaciones_actuales[552], 349);
    assert.equal(cierre.rollback.ocupacion_area, 3);
    assert.equal(cierre.rollback.historial[552].completo, true);
  }
}
await ensayoCierre(false); // admin_token_invalido_en_cierre
aprobados++;
await ensayoCierre(true); // admin_relogin_falla
aprobados++;
console.log(`OK G87 V2: ${aprobados}/${Object.keys(escenarios).length + 2} modos; informe, sesión UI y cierre comprobados en memoria.`);
