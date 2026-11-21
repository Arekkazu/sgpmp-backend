const fs = require('fs');
const path = require('path');
const globalNodeModules = path.join(path.dirname(process.execPath), 'node_modules');
const newman = require(path.join(globalNodeModules, 'newman'));

const runId = process.env.G80_RUN_ID;
const adminSecret = process.env.TEST_ADMIN_PASSWORD;
if (!runId || !adminSecret) {
  throw new Error('G80_RUN_ID y TEST_ADMIN_PASSWORD deben existir solo en el proceso de ejecución.');
}

const root = __dirname;
const outputDir = path.join(root, 'RESULTADOS', runId);
const htmlPath = path.join(outputDir, 'newman', 'newman-TC-M09-151-auditoria-oraculo.html');
const jsonPath = path.join(outputDir, 'audit-oracle.json');
fs.mkdirSync(path.dirname(htmlPath), { recursive: true });

const env = [
  ['base_url', 'https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test'],
  ['admin_email', 'admin@pecuaria.co'],
  ['admin_secret', adminSecret],
  ['source_user_id', '4'],
  ['source_from', '2026-09-06T04:10:00Z'],
  ['source_to', '2026-09-06T04:20:00Z']
];

const responseFor = (executions, name) => {
  const execution = executions.find(x => x.item && x.item.name === name);
  if (!execution || !execution.response) return null;
  try { return JSON.parse(execution.response.stream.toString()); } catch { return null; }
};
const statusFor = (executions, name) => {
  const execution = executions.find(x => x.item && x.item.name === name);
  return execution && execution.response ? execution.response.code : null;
};
const replaceAll = (value, secret) => secret ? value.split(secret).join('[REDACTED]') : value;
const redactHtml = (html, values) => {
  let result = html;
  for (const value of values) result = replaceAll(result, value);
  return result
    .replace(/Authorization/gi, '[REDACTED_HEADER]')
    .replace(/Bearer\s+[^\s<"']+/gi, '[REDACTED_HEADER]')
    .replace(/Bearer/gi, '[REDACTED_HEADER]')
    .replace(/access_token/gi, '[REDACTED]')
    .replace(/refresh_token/gi, '[REDACTED]')
    .replace(/password/gi, '[REDACTED]')
    .replace(/cookie/gi, '[REDACTED]')
    .replace(/jwt/gi, '[REDACTED]');
};

newman.run({
  collection: path.join(root, 'TC-M09-G80.postman_collection.json'),
  reporters: ['htmlextra'],
  reporter: { htmlextra: { export: htmlPath, showEnvironmentData: false, showMarkdownLinks: false } },
  envVar: env.map(([key, value]) => ({ key, value }))
}, (err, summary) => {
  const executions = summary && summary.run ? summary.run.executions : [];
  const login = responseFor(executions, 'Login Administrador');
  const me = responseFor(executions, 'Identidad Administrador');
  const catalog = responseFor(executions, 'Catálogo D09');
  const audit = responseFor(executions, 'D09 filtrado por evento G74');
  const session = login && login.token;
  if (fs.existsSync(htmlPath)) {
    fs.writeFileSync(htmlPath, redactHtml(fs.readFileSync(htmlPath, 'utf8'), [adminSecret, session]));
  }
  const failures = (summary && summary.run && summary.run.failures ? summary.run.failures : [])
    .map(f => ({ source: f.source && f.source.name, error: f.error && f.error.message }))
    .filter(f => f.error);
  const names = Array.isArray(catalog) ? catalog.map(x => x.nombre).filter(Boolean) : [];
  const items = audit && Array.isArray(audit.items) ? audit.items : [];
  const artifact = {
    caso: 'TC-M09-151',
    grupo: 'TC-M09-G80',
    runId,
    actor: me ? { id_usuario: me.id_usuario, rol: me.nombre_rol, correo_coincide: me.correo_electronico === 'admin@pecuaria.co' } : null,
    sourceWindow: { id_usuario: 4, desde: '2026-09-06T04:10:00Z', hasta: '2026-09-06T04:20:00Z', fuente: 'TC-M09-141 / G74, calibración ID 9' },
    statuses: {
      login_administrador: statusFor(executions, 'Login Administrador'),
      identidad_administrador: statusFor(executions, 'Identidad Administrador'),
      catalogo_d09: statusFor(executions, 'Catálogo D09'),
      consulta_d09_filtrada: statusFor(executions, 'D09 filtrado por evento G74')
    },
    catalogo: { total: names.length, eventos_calibracion_o_sensor: names.filter(x => /calibr|sensor/i.test(x)) },
    consultaD09: {
      total: audit ? audit.total : null,
      tipos_evento: items.map(x => x.tipo_evento),
      modulos: items.map(x => x.modulo),
      resultados: items.map(x => x.resultado),
      eventos_con_texto_calibracion: items.filter(x => /calibr/i.test(JSON.stringify(x))).length
    },
    assertions: { total: summary && summary.run ? summary.run.stats.assertions.total : 0, failed: failures.length, failures },
    resultado: err || failures.length ? 'FAIL' : 'PASS'
  };
  fs.writeFileSync(jsonPath, JSON.stringify(artifact, null, 2));
  if (err) process.exitCode = 1;
  else if (failures.length) process.exitCode = 2;
});
