const fs = require('fs');
const path = require('path');
const globalNodeModules = path.join(path.dirname(process.execPath), 'node_modules');
const newman = require(path.join(globalNodeModules, 'newman'));

const runId = process.env.G74_RUN_ID;
const attempt = process.env.G74_ATTEMPT || '1';
const actorSecret = process.env.TEST_FIELD_ENGINEER_PASSWORD;
if (!runId || !actorSecret) {
  throw new Error('G74_RUN_ID y TEST_FIELD_ENGINEER_PASSWORD deben existir solo en el proceso de ejecución.');
}

const root = __dirname;
const outputDir = path.join(root, 'RESULTADOS', runId);
const htmlPath = path.join(outputDir, 'newman', `newman-TC-M09-141-intento${attempt}.html`);
const jsonPath = path.join(outputDir, `newman-TC-M09-141-intento${attempt}.json`);
fs.mkdirSync(path.dirname(htmlPath), { recursive: true });

const env = [
  ['base_url', 'https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test'],
  ['actor_email', 'ingeniero@pecuaria.co'],
  ['actor_secret', actorSecret],
  ['device_id', process.env.G74_DEVICE_ID || '1'],
  ['sensor_id', process.env.G74_SENSOR_ID || '3'],
  ['area_id', process.env.G74_AREA_ID || '1'],
  ['sensor_category', process.env.G74_SENSOR_CATEGORY || 'OXIGENO'],
  ['reference_value', process.env.G74_REFERENCE_VALUE || '10.0000'],
  ['calibration_at', new Date().toISOString()],
  ['observations', `QA TC-M09-141 G74 ${runId}`]
];

const getResponse = (executions, name) => {
  const execution = executions.find(x => x.item && x.item.name === name);
  if (!execution || !execution.response) return null;
  try { return JSON.parse(execution.response.stream.toString()); } catch { return null; }
};
const getStatus = (executions, name) => {
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

if (process.argv[2] === '--sanitize-html') {
  const target = process.argv[3];
  if (!target || !fs.existsSync(target)) throw new Error('Se requiere un HTML existente para sanitizar.');
  fs.writeFileSync(target, redactHtml(fs.readFileSync(target, 'utf8'), []));
  process.exit(0);
}

newman.run({
  collection: path.join(root, 'TC-M09-G74.postman_collection.json'),
  reporters: ['htmlextra'],
  reporter: { htmlextra: { export: htmlPath, showEnvironmentData: false, showMarkdownLinks: false } },
  envVar: env.map(([key, value]) => ({ key, value }))
}, (err, summary) => {
  const executions = summary && summary.run ? summary.run.executions : [];
  const login = getResponse(executions, 'Login Ingeniero');
  const me = getResponse(executions, 'Identidad del Ingeniero');
  const device = getResponse(executions, 'Dispositivo activo');
  const sensors = getResponse(executions, 'Sensor asociado al dispositivo');
  const associations = getResponse(executions, 'Área activa del sensor');
  const ranges = getResponse(executions, 'Rango técnico del sensor');
  const before = getResponse(executions, 'Historial BEFORE');
  const created = getResponse(executions, 'Registrar calibración TC-M09-141');
  const after = getResponse(executions, 'Historial AFTER');
  const sessionValue = login && login.token;
  if (fs.existsSync(htmlPath)) {
    fs.writeFileSync(htmlPath, redactHtml(fs.readFileSync(htmlPath, 'utf8'), [actorSecret, sessionValue]));
  }
  const selectedSensor = sensors && (sensors.items || []).find(x => x.id_sensores === Number(process.env.G74_SENSOR_ID || 3));
  const selectedAssociation = associations && (associations.items || []).find(x => x.tiene_estado === true && x.fecha_finalizacion === null && x.id_infraestructura === Number(process.env.G74_AREA_ID || 1));
  const selectedRange = ranges && (ranges.items || []).find(x => x.categoria === (process.env.G74_SENSOR_CATEGORY || 'OXIGENO'));
  const failedAssertions = (summary && summary.run && summary.run.failures ? summary.run.failures : []).map(f => ({ source: f.source && f.source.name, error: f.error && f.error.message })).filter(f => f.error);
  const artifact = {
    caso: 'TC-M09-141', grupo: 'TC-M09-G74', runId, intento: Number(attempt),
    actor: me ? { id_usuario: me.id_usuario, rol: me.nombre_rol, correo_coincide: me.correo_electronico === 'ingeniero@pecuaria.co' } : null,
    dispositivo: device ? { id: device.id_dispositivo_iot, serial: device.serial, activo: device.es_activo, id_infraestructura: device.id_infraestructura } : null,
    sensor: selectedSensor ? { id: selectedSensor.id_sensores, nombre: selectedSensor.nombre, categoria: selectedSensor.categoria, activo: selectedSensor.es_activo, id_dispositivo_iot: selectedSensor.id_dispositivo_iot } : null,
    area: selectedAssociation ? { id_infraestructura: selectedAssociation.id_infraestructura, id_dispositivo_iot: selectedAssociation.id_dispositivo_iot, activa: selectedAssociation.tiene_estado } : null,
    rangoTecnico: selectedRange ? { categoria: selectedRange.categoria, min: selectedRange.valor_min, max: selectedRange.valor_max } : null,
    valorReferencia: env.find(x => x[0] === 'reference_value')[1],
    observaciones: env.find(x => x[0] === 'observations')[1],
    endpoint: `/configuracion/sensores/${env.find(x => x[0] === 'sensor_id')[1]}/calibrar`, metodo: 'POST',
    statuses: Object.fromEntries(['Login Ingeniero','Identidad del Ingeniero','Permisos del Ingeniero','Rango técnico del sensor','Dispositivo activo','Sensor asociado al dispositivo','Área activa del sensor','Historial BEFORE','Registrar calibración TC-M09-141','Historial AFTER'].map(name => [name, getStatus(executions, name)])),
    historyBefore: before ? { total: before.total, ids: (before.items || []).map(x => x.id_calibracion) } : null,
    calibracion: created ? { id_calibracion: created.id_calibracion, id_dispositivo_iot: created.id_dispositivo_iot, id_sensor: created.id_sensor, valor_referencia: created.valor_referencia, fecha_calibracion: created.fecha_calibracion, id_usuario: created.id_usuario, observaciones: created.observaciones } : null,
    historyAfter: after ? { total: after.total, ids: (after.items || []).map(x => x.id_calibracion) } : null,
    assertions: { total: summary && summary.run ? summary.run.stats.assertions.total : 0, failed: failedAssertions.length, failures: failedAssertions },
    resultado: err || failedAssertions.length ? 'FAIL' : 'PASS'
  };
  fs.writeFileSync(jsonPath, JSON.stringify(artifact, null, 2));
  if (err) process.exitCode = 1;
  else if (failedAssertions.length) process.exitCode = 2;
});
