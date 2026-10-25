const fs = require('fs');
const path = require('path');

const globalNodeModules = path.join(path.dirname(process.execPath), 'node_modules');
const newman = require(path.join(globalNodeModules, 'newman'));

const testCase = process.env.G32_CASE;
const runId = process.env.G32_RUN_ID;
const adminSecret = process.env.TEST_ADMIN_PASSWORD;
if (testCase !== 'TC-M09-69' || !runId || !adminSecret) {
  throw new Error('G32_CASE=TC-M09-69, G32_RUN_ID y TEST_ADMIN_PASSWORD deben existir solo durante la ejecución.');
}

const baseUrl = 'https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test';
const adminEmail = 'admin@pecuaria.co';
const root = __dirname;
const outputDir = path.join(root, 'RESULTADOS', runId);
const htmlPath = path.join(outputDir, 'newman', 'newman-TC-M09-69-intento1.html');
const jsonPath = path.join(outputDir, 'newman-TC-M09-69-intento1.json');
fs.mkdirSync(path.dirname(htmlPath), { recursive: true });

const readJson = async (response, route) => {
  if (!response.ok) throw new Error(`GET ${route} respondió HTTP ${response.status}.`);
  return response.json();
};

const redact = (content, secret, token) => {
  let safe = content.split(secret).join('[REDACTED]');
  if (token) safe = safe.split(token).join('[REDACTED]');
  return safe
    .replace(/("contrasena"\s*:\s*")[^"]*(")/gi, '$1[REDACTED]$2')
    .replace(/("token"\s*:\s*")[^"]*(")/gi, '$1[REDACTED]$2')
    .replace(/Authorization/gi, '[REDACTED_HEADER]')
    .replace(/Bearer\s+[^\s<"']+/gi, '[REDACTED_HEADER]')
    .replace(/\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b/g, '[REDACTED]')
    .replace(/access_token/gi, '[REDACTED]')
    .replace(/refresh_token/gi, '[REDACTED]')
    .replace(/password/gi, '[REDACTED]')
    .replace(/cookie/gi, '[REDACTED]')
    .replace(/jwt/gi, '[REDACTED]');
};

async function get(route, token) {
  return readJson(await fetch(`${baseUrl}${route}`, { headers: { Authorization: `Bearer ${token}` } }), route);
}

async function discover() {
  const login = await fetch(`${baseUrl}/sesiones/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ correo_electronico: adminEmail, contrasena: adminSecret }),
  });
  if (!login.ok) throw new Error(`Login de discovery respondió HTTP ${login.status}.`);
  const session = await login.json();
  if (!session.token) throw new Error('El login de discovery no devolvió una sesión utilizable.');

  const [identity, species, dashboard, history] = await Promise.all([
    get('/usuarios/me', session.token),
    get('/configuracion/especies?solo_activas=true', session.token),
    get('/iot/monitoreo/dashboard?pagina=1&por_pagina=50', session.token),
    get('/iot/monitoreo/historial?fecha_inicio=2026-07-01&fecha_fin=2026-09-06&pagina=1&por_pagina=100', session.token),
  ]);

  const bySpecies = await Promise.all((species.items || []).map(async (item) => ({
    especie: { id_especie: item.id_especie, nombre: item.nombre },
    body: await get(`/configuracion/umbrales?id_especie=${encodeURIComponent(item.id_especie)}&solo_activas=true`, session.token),
  })));
  const configurations = bySpecies.flatMap(({ especie, body }) => (body.items || []).map((item) => ({
    id_umbral_ambiental: item.id_umbral_ambiental,
    id_especie: especie.id_especie,
    especie: especie.nombre,
    id_variable_ambiental: item.id_variable_ambiental,
    unidad_medida: item.unidad_medida,
    valor_min: item.valor_min,
    valor_max: item.valor_max,
    es_activo: item.es_activo,
    niveles: (item.niveles || []).map((level) => ({
      nivel: level.nivel,
      limite_inferior: level.limite_inferior,
      limite_superior: level.limite_superior,
    })),
  })));
  const variablesInHistory = new Set((history.items || []).map((item) => item.id_variable));
  const candidate = configurations.find((item) => variablesInHistory.has(item.id_variable_ambiental)) || configurations[0] || null;
  return { identity, dashboard, history, configurations, candidate, sessionToken: session.token };
}

function buildCollection(discovery) {
  const collection = JSON.parse(fs.readFileSync(path.join(root, 'TC-M09-G32.postman_collection.json'), 'utf8'));
  const authHeader = [{ key: 'Authorization', value: 'Bearer {{session_token}}' }];
  const candidateSpecies = discovery.candidate?.id_especie;
  collection.item = [
    {
      name: 'Login Administrador',
      request: {
        method: 'POST',
        header: [{ key: 'Content-Type', value: 'application/json' }],
        body: { mode: 'raw', raw: '{\n  "correo_electronico": "{{admin_email}}",\n  "contrasena": "{{admin_secret}}"\n}' },
        url: '{{base_url}}/sesiones/',
      },
      event: [{ listen: 'test', script: { type: 'text', exec: [
        'const body = pm.response.json();',
        "pm.test('Login responde HTTP 200', () => pm.response.to.have.status(200));",
        "pm.expect(body.token).to.be.a('string').and.not.empty;",
        "pm.environment.set('session_token', body.token);",
      ] } }],
    },
    {
      name: 'Identidad Administrador',
      request: { method: 'GET', header: authHeader, url: '{{base_url}}/usuarios/me' },
      event: [{ listen: 'test', script: { type: 'text', exec: [
        "pm.test('Identidad responde HTTP 200', () => pm.response.to.have.status(200));",
        "pm.expect(pm.response.json().nombre_rol).to.equal('Administrador');",
      ] } }],
    },
    {
      name: 'Configuración RF-17 BEFORE',
      request: { method: 'GET', header: authHeader, url: `{{base_url}}/configuracion/umbrales?id_especie=${candidateSpecies}&solo_activas=true` },
      event: [{ listen: 'test', script: { type: 'text', exec: [
        "pm.test('Configuración RF-17 responde HTTP 200', () => pm.response.to.have.status(200));",
        "pm.expect(pm.response.json().items).to.be.an('array').and.not.empty;",
      ] } }],
    },
    {
      name: 'Monitoreo BEFORE Dashboard',
      request: { method: 'GET', header: authHeader, url: '{{base_url}}/iot/monitoreo/dashboard?pagina=1&por_pagina=50' },
      event: [{ listen: 'test', script: { type: 'text', exec: [
        "pm.test('Dashboard responde HTTP 200', () => pm.response.to.have.status(200));",
        "pm.expect(pm.response.json().sensores).to.be.an('array');",
      ] } }],
    },
    {
      name: 'Monitoreo BEFORE Historial',
      request: { method: 'GET', header: authHeader, url: '{{base_url}}/iot/monitoreo/historial?fecha_inicio=2026-07-01&fecha_fin=2026-09-06&pagina=1&por_pagina=100' },
      event: [{ listen: 'test', script: { type: 'text', exec: [
        "pm.test('Historial responde HTTP 200', () => pm.response.to.have.status(200));",
        "pm.expect(pm.response.json().items).to.be.an('array');",
      ] } }],
    },
  ];
  return collection;
}

const executionFor = (executions, name) => executions.find((entry) => entry.item?.name === name);
const bodyFor = (executions, name) => {
  const entry = executionFor(executions, name);
  try { return entry?.response ? JSON.parse(entry.response.stream.toString()) : null; } catch { return null; }
};

(async () => {
  const discovery = await discover();
  const collection = buildCollection(discovery);
  const summary = await new Promise((resolve, reject) => {
    newman.run({
      collection,
      reporters: ['htmlextra'],
      reporter: { htmlextra: { export: htmlPath, showEnvironmentData: false, showMarkdownLinks: false } },
      envVar: [
        { key: 'base_url', value: baseUrl },
        { key: 'admin_email', value: adminEmail },
        { key: 'admin_secret', value: adminSecret },
        { key: 'session_token', value: '' },
      ],
    }, (error, result) => error ? reject(error) : resolve(result));
  });
  const executions = summary.run.executions || [];
  const failures = (summary.run.failures || []).map((failure) => ({
    source: failure.source?.name || null,
    error: failure.error?.message || null,
  })).filter((item) => item.error);
  const monitoringBefore = {
    dashboard_status: executionFor(executions, 'Monitoreo BEFORE Dashboard')?.response?.code ?? null,
    dashboard_sensor_fields: Object.keys(bodyFor(executions, 'Monitoreo BEFORE Dashboard')?.sensores?.[0] || {}).sort(),
    dashboard_sensors: (bodyFor(executions, 'Monitoreo BEFORE Dashboard')?.sensores || []).map((sensor) => ({
      id_sensor: sensor.id_sensor,
      id_dispositivo_iot: sensor.id_dispositivo_iot,
      tipo_variable: sensor.tipo_variable,
      estado_semaforo: sensor.estado_semaforo,
      ultimo_valor: sensor.ultimo_valor,
      ultima_unidad: sensor.ultima_unidad,
      ultimo_timestamp_captura: sensor.ultimo_timestamp_captura,
    })),
    historial_status: executionFor(executions, 'Monitoreo BEFORE Historial')?.response?.code ?? null,
    historial_lecturas: (bodyFor(executions, 'Monitoreo BEFORE Historial')?.items || []).map((item) => ({
      id_telemetria: item.id_telemetria,
      id_sensor: item.id_sensor,
      id_variable: item.id_variable,
      tipo_variable: item.tipo_variable,
      id_activo_biologico: item.id_activo_biologico,
      especie: item.especie,
      estado_semaforo_historico: item.estado_semaforo_historico,
    })),
  };
  if (fs.existsSync(htmlPath)) fs.writeFileSync(htmlPath, redact(fs.readFileSync(htmlPath, 'utf8'), adminSecret, discovery.sessionToken));
  fs.writeFileSync(jsonPath, JSON.stringify({
    caso: testCase,
    grupo: 'TC-M09-G32',
    intento: 1,
    ejecucion: 'discovery-read-only',
    actor: { correo: adminEmail, rol: discovery.identity.nombre_rol, autenticacion: 'HTTP 200' },
    configuracion_before: discovery.candidate,
    configuraciones_activas_descubiertas: discovery.configurations.length,
    monitoring_before: monitoringBefore,
    correlacion_before: {
      demostrada: false,
      motivo: 'Monitoreo no expone id_umbral_ambiental, rango efectivo ni especie/activo para relacionar una configuración RF-17 concreta.',
    },
    modificacion: { metodo: 'PATCH', endpoint: '/configuracion/umbrales/{id_umbral_ambiental}', ejecutada: false, motivo: 'Precondición de correlación BEFORE no demostrable.' },
    configuracion_after: null,
    monitoring_after: null,
    propagacion_comprobada: false,
    assertions: { total: summary.run.stats.assertions.total, failed: failures.length, failures },
    resultado: 'BLOCKED_CONFIGURACION_EFECTIVA_MONITOREO_NO_VERIFICABLE_EN_TEST',
  }, null, 2));
  if (failures.length) process.exitCode = 2;
})().catch((error) => {
  if (fs.existsSync(htmlPath)) fs.writeFileSync(htmlPath, redact(fs.readFileSync(htmlPath, 'utf8'), adminSecret, ''));
  process.stderr.write(`G32 finalizó sin exponer secretos: ${error.message}\n`);
  process.exitCode = 1;
});
