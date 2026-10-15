// TC-M09-G32 / TC-M09-69 — REEVALUACION V2. Verificacion de la integracion RF-17 → Monitoreo
// SOLO LECTURA (login + GET) en el ambiente indicado por G32_ENV (TEST | DEV). No hace UPDATE:
// el checklist previo exige una API de Monitoreo correlacionable que no existe (ver reporte).
const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');
const newman = require('newman');
require.resolve('newman-reporter-htmlextra');

const ENVS = {
  TEST: { base: 'https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test', suministrada: 'http://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test',
    actores: [['administador.dev@gmail.com', 'TEST_ADMIN_PASSWORD']] },
  DEV: { base: 'https://sigab-backenddev-jpuya4-ea3a74-158-69-200-27.sslip.io/api-sgpmp', suministrada: 'https://sigab-backenddev-jpuya4-ea3a74-158-69-200-27.sslip.io/api-sgpmp',
    actores: [['administador.dev@gmail.com', 'TEST_ADMIN_PASSWORD'], ['admin.general@pecuaria.co', 'DEV_ADMIN_PASSWORD']] },
};
const runId = process.env.G32_REEVAL_V2_RUN_ID;
const envName = process.env.G32_ENV;
if (!runId || !/^[\w-]+$/.test(runId)) throw Error('G32_REEVAL_V2_RUN_ID requerido');
if (!ENVS[envName]) throw Error('G32_ENV debe ser TEST o DEV');
const E = ENVS[envName];
const R = path.join(__dirname, 'RESULTADOS', runId);
fs.mkdirSync(path.join(R, 'newman'), { recursive: true });
const BACKEND = path.resolve(__dirname, '..', '..', '..', '..', '..', '..');
const secretos = () => [process.env.TEST_ADMIN_PASSWORD, process.env.DEV_ADMIN_PASSWORD].filter(Boolean);
const clean = (s) => { s = String(s); for (const x of secretos()) s = s.split(x).join('[REDACTED]');
  return s.replace(/eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+/g, '[JWT REDACTED]').replace(/Bearer\s+(?!\{\{)[A-Za-z0-9_.\-]+/g, 'Bearer [REDACTED]'); };
const save = (name, obj) => { const p = path.join(R, name); if (fs.existsSync(p)) throw Error('No sobrescribir: ' + name);
  fs.writeFileSync(p, clean(JSON.stringify({ grupo: 'TC-M09-G32', caso: 'TC-M09-69', rf: 'RF-17', tipo: 'REEVALUACION V2', runId, ambiente: envName, fecha: new Date().toISOString(), ...obj }, null, 2))); };
// git grep sin coincidencias sale con codigo 1: se interpreta como resultado vacio.
const git = (...a) => { try { return execFileSync('git', a, { cwd: BACKEND, encoding: 'utf8' }); } catch (e) { if (a[0] === 'grep' && e.status === 1) return ''; throw e; } };

async function http(url, { metodo = 'GET', token, cuerpo } = {}) {
  const r = await fetch(url, { method: metodo, headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: cuerpo ? JSON.stringify(cuerpo) : undefined, redirect: 'manual', signal: AbortSignal.timeout(30000) });
  let body = null; try { body = await r.json(); } catch { /* sin JSON */ }
  return { status: r.status, body };
}

(async () => {
  const preflight = [];
  for (const u of [...new Set([E.suministrada, E.base])]) { const h = await http(u + '/health').catch((e) => ({ status: 'ERR ' + e.message })); preflight.push({ url: u + '/health', status: h.status }); }
  if (!preflight.some((p) => p.status === 200)) throw Error('ENVIRONMENT_ERROR: backend no accesible');

  // Actor: primero la cuenta comun; en DEV, fallback al Administrador DEV (paquete §14).
  let token = null; const intentosLogin = [];
  for (const [correo, varPass] of E.actores) {
    if (!process.env[varPass]) { intentosLogin.push({ correo, status: 'SIN_VARIABLE' }); continue; }
    const r = await http(E.base + '/sesiones/', { metodo: 'POST', cuerpo: { correo_electronico: correo, contrasena: process.env[varPass] } });
    intentosLogin.push({ correo, status: r.status });
    if (r.status === 200 && r.body?.token) { token = r.body.token; break; }
  }
  if (!token) throw Error('BLOCKED: ningun actor autorizado autentico: ' + JSON.stringify(intentosLogin));
  const me = (await http(E.base + '/usuarios/me', { token })).body;
  const perms = (await http(E.base + '/sesiones/me/permisos', { token })).body.permisos;
  const permisos = (rec) => perms.filter((p) => p.id_recurso === rec).map((p) => p.id_accion).sort();
  const actor = { correo: me.correo_electronico, id_usuario: me.id_usuario, rol: me.nombre_rol, estado: me.estado_cuenta,
    permisosRF17_r20: permisos(20), permisosDashboard_r33: permisos(33), permisosHistorial_r34: permisos(34), intentosLogin };

  // Configuracion RF-17 de referencia (solo lectura). TEST: preferir el umbral QA #39 creado por G22 V2.
  const especies = (await http(E.base + '/configuracion/especies', { token })).body.items.filter((s) => s.es_activo);
  const variables = (await http(E.base + '/configuracion/variables-ambientales', { token })).body.items;
  let cfg = null, especie = null;
  const preferido = envName === 'TEST' ? 39 : null;
  for (const s of especies) {
    const items = (await http(E.base + `/configuracion/umbrales?id_especie=${s.id_especie}`, { token })).body.items.filter((u) => u.es_activo);
    const u = preferido ? items.find((x) => x.id_umbral_ambiental === preferido) : items[0];
    if (u) { cfg = u; especie = s; if (!preferido || u.id_umbral_ambiental === preferido) break; }
  }
  if (!cfg) throw Error('BLOCKED: sin configuracion RF-17 activa');
  const variable = variables.find((v) => v.id_variable_ambiental === cfg.id_variable_ambiental);
  const rf17Before = { id_umbral_ambiental: cfg.id_umbral_ambiental, especie: { id: especie.id_especie, nombre: especie.nombre, es_activo: especie.es_activo },
    variable: { id: variable?.id_variable_ambiental, nombre: variable?.nombre, unidad: variable?.unidad }, valor_min: cfg.valor_min, valor_max: cfg.valor_max,
    niveles: cfg.niveles, es_activo: cfg.es_activo, fecha_actualizacion: cfg.fecha_actualizacion,
    origen: envName === 'TEST' && cfg.id_umbral_ambiental === 39 ? 'Umbral QA creado por TC-M09-G22 EvaluacionV2 (TC-M09-47, Tilapia + Temperatura del agua)' : 'Umbral activo existente, usado solo para lectura' };

  const hoy = new Date(); const desde = new Date(hoy.getTime() - 30 * 86400e3);
  const f = (d) => d.toISOString().slice(0, 10);
  const dashboard = await http(E.base + '/iot/monitoreo/dashboard?pagina=1&por_pagina=50', { token });
  const historial = await http(E.base + `/iot/monitoreo/historial?fecha_inicio=${f(desde)}&fecha_fin=${f(hoy)}&pagina=1&por_pagina=50&orden=DESC`, { token });
  const sensores = dashboard.body?.sensores || [];
  const lecturas = historial.body?.items || [];
  const mismaVariable = (x) => variable && (String(x.id_variable) === String(variable.id_variable_ambiental) || (x.tipo_variable || '').toLowerCase() === variable.nombre.toLowerCase());
  const monitoringBefore = {
    dashboard: { endpoint: 'GET /iot/monitoreo/dashboard', status: dashboard.status, total: dashboard.body?.total ?? null, camposEstadoSensor: sensores[0] ? Object.keys(sensores[0]) : [],
      sensoresDeLaVariable: sensores.filter(mismaVariable).map((x) => ({ id_sensor: x.id_sensor, tipo_variable: x.tipo_variable, ultimo_valor: x.ultimo_valor, estado_semaforo: x.estado_semaforo, id_infraestructura: x.id_infraestructura })).slice(0, 10),
      semaforos: [...new Set(sensores.map((x) => x.estado_semaforo))] },
    historial: { endpoint: 'GET /iot/monitoreo/historial', ventana: [f(desde), f(hoy)], status: historial.status, total: historial.body?.total ?? null, camposLectura: lecturas[0] ? Object.keys(lecturas[0]) : [],
      lecturasDeLaVariable: lecturas.filter(mismaVariable).map((x) => ({ id_telemetria: x.id_telemetria, tipo_variable: x.tipo_variable, valor: x.valor, especie: x.especie, estado_semaforo_historico: x.estado_semaforo_historico })).slice(0, 10),
      semaforosHistoricos: [...new Set(lecturas.map((x) => x.estado_semaforo_historico))], lecturasConEspecie: lecturas.filter((x) => x.especie).length },
  };
  const camposUmbral = (campos) => campos.filter((c) => /(^|_)umbral|valor_min|valor_max|^niveles$|nivel(es)?_(normal|precaucion|critico|alerta)|limite_(inferior|superior)|version_config/i.test(c));
  const correlacion = {
    monitoreoExponeConfiguracionRF17: camposUmbral(monitoringBefore.dashboard.camposEstadoSensor).length > 0 || camposUmbral(monitoringBefore.historial.camposLectura).length > 0,
    dashboardExponeEspecie: monitoringBefore.dashboard.camposEstadoSensor.some((c) => /especie/i.test(c)),
    semaforoHistoricoCalculado: monitoringBefore.historial.semaforosHistoricos.some((s) => s && s !== 'GRIS'),
    RF17_BEFORE_igual_MONITORING_BEFORE: 'No verificable: Monitoreo no expone rango, niveles ni referencia al umbral',
  };

  // Newman: misma verificacion con aserciones (precondiciones + oraculo).
  const html = path.join(R, 'newman', `newman-TC-M09-69-v2-${envName}.html`);
  if (fs.existsSync(html)) throw Error('No sobrescribir HTML');
  const collection = JSON.parse(fs.readFileSync(path.join(__dirname, 'TC-M09-G32-reevaluacion-v2.postman_collection.json'), 'utf8'));
  const summary = await new Promise((resolve, reject) => newman.run({
    collection, reporters: ['htmlextra'], timeoutRequest: 30000,
    reporter: { htmlextra: { export: html, omitHeaders: true, showEnvironmentData: false, showGlobalData: false, skipEnvironmentVars: ['token'], logs: false, silentProgressBar: true, title: `TC-M09-69 — G32 V2 — RF-17 → Monitoreo — ${envName} (solo lectura)` } },
    environment: { values: Object.entries({ base_url: E.base, token, id_especie: especie.id_especie, id_umbral: cfg.id_umbral_ambiental, fecha_inicio: f(desde), fecha_fin: f(hoy) }).map(([key, value]) => ({ key, value: String(value), enabled: true })) },
  }, (err, s) => (err ? reject(Error('Newman execution error')) : resolve(s))));
  fs.writeFileSync(html, clean(fs.readFileSync(html, 'utf8')));
  const aserciones = [];
  for (const ex of summary.run.executions) for (const a of ex.assertions || []) aserciones.push({ request: ex.item.name, test: a.assertion, ok: !a.error, detalle: a.error ? clean(a.error.message).slice(0, 300) : undefined });

  save(`rf17-before-${envName}.json`, { actor: { correo: actor.correo, rol: actor.rol }, RF17_BEFORE: rf17Before });
  save(`monitoring-before-${envName}.json`, { MONITORING_BEFORE: monitoringBefore, correlacion });

  const codigo = envName === 'TEST' ? {
    rama: git('branch', '--show-current').trim(), head: git('rev-parse', 'HEAD').trim(), originDev: git('rev-parse', 'origin/dev').trim(),
    diffSrcHeadVsOriginDev: git('diff', '--stat', 'HEAD', 'origin/dev', '--', 'src').trim() || '(sin diferencias)',
    umbralHistoricoM09Adapter: git('show', 'origin/dev:src/telemetry/infrastructure/adapters/umbral_historico_m09_adapter.py').split('\n').map((l) => l.trim()).filter((l) => /return|class|Stub|GRIS/.test(l)),
    lecturasDeTablasRF17FueraDeConfiguration: git('grep', '-n', '-i', '-E', 'umbrales_ambientales|niveles_alerta_ambientales|UmbralAmbientalRepository', 'origin/dev', '--', 'src/telemetry', 'src/prediction', 'src/shared').trim().split('\n').filter(Boolean),
    fuenteSemaforoDashboard: git('grep', '-n', 'FROM modulo3.estados_actuales_sensores', 'origin/dev', '--', 'src/telemetry/infrastructure/repositories/monitoreo_repository.py').trim().split('\n').filter(Boolean),
  } : undefined;
  save(`TC-M09-69-evidencia-${envName}.json`, {
    preflight, actor, RF17_BEFORE: rf17Before, MONITORING_BEFORE: { dashboard: { status: dashboard.status, campos: monitoringBefore.dashboard.camposEstadoSensor }, historial: { status: historial.status, campos: monitoringBefore.historial.camposLectura, semaforos: monitoringBefore.historial.semaforosHistoricos } },
    correlacion, updateEjecutado: false, motivoSinUpdate: 'Checklist §140: API de Monitoreo sin configuracion efectiva correlacionable (items 11, 12 y 15 = No)',
    RF17_AFTER: null, MONITORING_AFTER: null, versionOCorrelacion: null, probeValue: null, clasificacion: null, tiempoPropagacion: null,
    codigo, newman: { html: path.relative(R, html).split(path.sep).join('/'), assertions: summary.run.stats.assertions, aserciones },
  });
  console.log(envName, '| actor', actor.correo, actor.rol, 'r20', JSON.stringify(actor.permisosRF17_r20), 'r33', JSON.stringify(actor.permisosDashboard_r33), 'r34', JSON.stringify(actor.permisosHistorial_r34), '| logins', JSON.stringify(intentosLogin));
  console.log('RF17_BEFORE', rf17Before.id_umbral_ambiental, rf17Before.especie.nombre, rf17Before.variable.nombre, rf17Before.valor_min, rf17Before.valor_max);
  console.log('dashboard', dashboard.status, 'sensores', sensores.length, 'semaforos', JSON.stringify(monitoringBefore.dashboard.semaforos), '| historial', historial.status, 'lecturas', lecturas.length, 'semaforos', JSON.stringify(monitoringBefore.historial.semaforosHistoricos), 'conEspecie', monitoringBefore.historial.lecturasConEspecie);
  console.log('correlacion', JSON.stringify(correlacion));
  aserciones.forEach((a) => console.log(a.ok ? '  PASS' : '  FAIL', a.request, '::', a.test, a.ok ? '' : '-> ' + (a.detalle || '').slice(0, 140)));
})().catch((e) => { console.log('ERROR:', clean(e.message)); process.exitCode = 1; });
