// Runner reutilizable de TC-M09-G74-v2.0 / TC-M09-141-v2.0 (RF-24 v2.0, CU05 Flujo D).
//
// Ejecuta UN solo RUN oficial con UN solo POST de calibración. No implementa reintentos:
// si el POST falla o se interrumpe, la reconciliación es el GET del historial que la
// colección ejecuta a continuación, nunca un segundo envío.
//
// Credenciales: solo por variables de proceso. El token vive en memoria y se redacta de
// cualquier artefacto. Fixture: los IDs llegan como entrada pero la colección los
// reconfirma por GET antes del POST.
//
// Uso:
//   $env:QA_BASE_URL="https://api.inmero.co/back-sigab-test"
//   $env:TEST_FIELD_ENGINEER_EMAIL="ingeniero@pecuaria.co"
//   $env:TEST_FIELD_ENGINEER_PASSWORD="<secreto>"
//   $env:G74_RUN_ID="run-YYYYMMDD-HHMMSS"
//   node .\run-newman.cjs
//
//   node .\run-newman.cjs --sanitize-html <ruta.html>   (re-sanitiza un HTML existente)

const fs = require('fs');
const path = require('path');
const globalNodeModules = path.join(path.dirname(process.execPath), 'node_modules');
const newman = require(path.join(globalNodeModules, 'newman'));

const CASE_ID = 'TC-M09-141-v2.0';
const GROUP_ID = 'TC-M09-G74-v2.0';
const OBSERVATIONS = 'QA TC-M09-141-v2.0'; // Oráculo textual exacto: no concatenar el RUN_ID.

const root = __dirname;

const replaceAll = (value, secret) => (secret ? value.split(secret).join('[REDACTED]') : value);
const redactHtml = (html, values) => {
  let result = html;
  for (const value of values) result = replaceAll(result, value);
  return result
    .replace(/Authorization/gi, '[REDACTED_HEADER]')
    .replace(/Bearer\s+[^\s<"']+/gi, '[REDACTED_HEADER]')
    .replace(/Bearer/gi, '[REDACTED_HEADER]')
    .replace(/access_token/gi, '[REDACTED]')
    .replace(/refresh_token/gi, '[REDACTED]')
    .replace(/contrasena/gi, '[REDACTED]')
    .replace(/password/gi, '[REDACTED]')
    .replace(/cookie/gi, '[REDACTED]')
    .replace(/jwt/gi, '[REDACTED]');
};

// Modo utilitario: sanitizar un HTML ya generado no cuenta como una segunda ejecución.
if (process.argv[2] === '--sanitize-html') {
  const target = process.argv[3];
  if (!target || !fs.existsSync(target)) throw new Error('Se requiere un HTML existente para sanitizar.');
  fs.writeFileSync(target, redactHtml(fs.readFileSync(target, 'utf8'), []));
  process.exit(0);
}

const runId = process.env.G74_RUN_ID;
const baseUrl = process.env.QA_BASE_URL;
const actorEmail = process.env.TEST_FIELD_ENGINEER_EMAIL;
const actorSecret = process.env.TEST_FIELD_ENGINEER_PASSWORD;
// Administrador auxiliar: SOLO para los dos GET de reconfirmación del fixture que el
// Ingeniero no puede leer en TEST (detalle de dispositivo RF-21 y asociaciones RF-22).
// Nunca ejecuta el POST funcional del caso.
const adminEmail = process.env.TEST_ADMIN_EMAIL;
const adminSecret = process.env.TEST_ADMIN_PASSWORD;

if (!runId || !baseUrl || !actorEmail || !actorSecret) {
  throw new Error(
    'Faltan variables de proceso. Requeridas: G74_RUN_ID, QA_BASE_URL, ' +
    'TEST_FIELD_ENGINEER_EMAIL, TEST_FIELD_ENGINEER_PASSWORD. ' +
    'Las credenciales no deben escribirse en archivos.'
  );
}
if (!adminEmail || !adminSecret) {
  throw new Error(
    'Faltan TEST_ADMIN_EMAIL y TEST_ADMIN_PASSWORD. Se usan solo para los GET auxiliares ' +
    'de solo lectura del fixture (dispositivo y asociaciones), no para el POST del caso.'
  );
}
if (!/^run-\d{8}-\d{6}$/.test(runId)) {
  throw new Error('G74_RUN_ID debe tener el formato run-YYYYMMDD-HHMMSS.');
}

const outputDir = path.join(root, 'RESULTADOS', runId);
if (fs.existsSync(outputDir)) {
  throw new Error(
    `La carpeta ${runId} ya existe. Un RUN oficial no se repite ni se sobrescribe: ` +
    'use un RUN_ID nuevo si la ejecución fue autorizada de nuevo.'
  );
}
const evidenceDir = path.join(outputDir, 'evidencia');
const htmlPath = path.join(outputDir, 'newman', `newman-${CASE_ID}.html`);
const jsonPath = path.join(outputDir, `${CASE_ID}.json`);
fs.mkdirSync(path.dirname(htmlPath), { recursive: true });
fs.mkdirSync(evidenceDir, { recursive: true });

// La fecha se genera en cada ejecución, inmediatamente antes del RUN.
const calibrationAt = new Date().toISOString();

const env = [
  ['base_url', baseUrl],
  ['actor_email', actorEmail],
  ['actor_secret', actorSecret],
  ['admin_email', adminEmail],
  ['admin_secret', adminSecret],
  ['device_id', process.env.G74_DEVICE_ID || '3'],
  ['sensor_id', process.env.G74_SENSOR_ID || '6'],
  ['area_id', process.env.G74_AREA_ID || '3'],
  ['sensor_category', process.env.G74_SENSOR_CATEGORY || 'TEMPERATURA'],
  ['reference_value', process.env.G74_REFERENCE_VALUE || '22.5000'],
  ['calibration_at', calibrationAt],
  ['observations', OBSERVATIONS]
];

const ITEMS = [
  'Login Ingeniero',
  'Identidad del Ingeniero',
  'Permisos del Ingeniero',
  'Login Administrador auxiliar',
  'Dispositivo activo',
  'Sensor asociado al dispositivo',
  'Área activa del sensor',
  'Rango técnico del sensor',
  'Historial PRE',
  `Registrar calibración ${CASE_ID}`,
  'Historial POST'
];

const findExecution = (executions, name) => executions.find(x => x.item && x.item.name === name);
const getResponse = (executions, name) => {
  const execution = findExecution(executions, name);
  if (!execution || !execution.response) return null;
  try { return JSON.parse(execution.response.stream.toString()); } catch { return null; }
};
const getStatus = (executions, name) => {
  const execution = findExecution(executions, name);
  return execution && execution.response ? execution.response.code : null;
};
// TEST puede exponer el identificador del sensor como id_sensor o id_sensores.
const sensorIdOf = (row) => (row.id_sensor !== undefined ? row.id_sensor : row.id_sensores);
const sameInstant = (a, b) => {
  if (!a || !b) return false;
  const ta = new Date(a).getTime();
  const tb = new Date(b).getTime();
  return Number.isFinite(ta) && Number.isFinite(tb) && ta === tb;
};
const sameDecimal = (a, b) => {
  if (a === null || a === undefined || b === null || b === undefined) return false;
  return Number(a) === Number(b);
};
const writeJson = (file, data) => fs.writeFileSync(file, JSON.stringify(data, null, 2));

const value = (key) => env.find(x => x[0] === key)[1];

newman.run({
  collection: path.join(root, 'TC-M09-G74-v2.0.postman_collection.json'),
  reporters: ['cli', 'htmlextra'],
  reporter: { htmlextra: { export: htmlPath, showEnvironmentData: false, showMarkdownLinks: false } },
  envVar: env.map(([key, val]) => ({ key, value: val }))
}, (err, summary) => {
  const executions = summary && summary.run ? summary.run.executions : [];

  const login = getResponse(executions, 'Login Ingeniero');
  const me = getResponse(executions, 'Identidad del Ingeniero');
  const device = getResponse(executions, 'Dispositivo activo');
  const sensors = getResponse(executions, 'Sensor asociado al dispositivo');
  const associations = getResponse(executions, 'Área activa del sensor');
  const ranges = getResponse(executions, 'Rango técnico del sensor');
  const historyPre = getResponse(executions, 'Historial PRE');
  const created = getResponse(executions, `Registrar calibración ${CASE_ID}`);
  const historyPost = getResponse(executions, 'Historial POST');

  const sessionValue = login && login.token;
  const adminLogin = getResponse(executions, 'Login Administrador auxiliar');
  const adminSession = adminLogin && adminLogin.token;

  // El HTML se redacta antes de quedar como evidencia.
  if (fs.existsSync(htmlPath)) {
    fs.writeFileSync(htmlPath, redactHtml(fs.readFileSync(htmlPath, 'utf8'), [actorSecret, adminSecret, sessionValue, adminSession]));
  }

  // Evidencia cruda sanitizada del caso (ninguno de estos cuerpos contiene secretos).
  if (historyPre) writeJson(path.join(evidenceDir, 'historial_pre.json'), historyPre);
  if (created) writeJson(path.join(evidenceDir, 'response_calibracion.json'), created);
  if (historyPost) writeJson(path.join(evidenceDir, 'historial_post.json'), historyPost);
  // El request funcional no tiene secretos: se conserva para trazabilidad del oráculo.
  writeJson(path.join(evidenceDir, 'request_calibracion.json'), {
    endpoint: `/configuracion/sensores/${value('sensor_id')}/calibrar`,
    metodo: 'POST',
    headers: { Authorization: '[REDACTED]', 'Content-Type': 'application/json' },
    body: {
      modo_calibracion: 'SENSOR',
      id_dispositivo_iot: Number(value('device_id')),
      id_infraestructura: Number(value('area_id')),
      valor_referencia: Number(value('reference_value')),
      observaciones: OBSERVATIONS,
      fecha_calibracion: calibrationAt
    }
  });

  const selectedSensor = sensors && (sensors.items || []).find(x => sensorIdOf(x) === Number(value('sensor_id')));
  const selectedAssociation = associations && (associations.items || []).find(x =>
    x.tiene_estado === true &&
    (x.fecha_finalizacion === null || x.fecha_finalizacion === undefined) &&
    sensorIdOf(x) === Number(value('sensor_id')) &&
    x.id_dispositivo_iot === Number(value('device_id')) &&
    x.id_infraestructura === Number(value('area_id'))
  );
  const selectedRange = ranges && (ranges.items || []).find(x => x.categoria === value('sensor_category'));

  const preIds = historyPre ? (historyPre.items || []).map(x => x.id_calibracion) : [];
  const postIds = historyPost ? (historyPost.items || []).map(x => x.id_calibracion) : [];
  const createdId = created ? created.id_calibracion : null;
  const persisted = historyPost && createdId !== null
    ? (historyPost.items || []).find(x => x.id_calibracion === createdId) || null
    : null;

  const postStatus = getStatus(executions, `Registrar calibración ${CASE_ID}`);

  // Oráculo oficial del caso, recalculado sobre las respuestas reales.
  const oraculo = {
    http_exito_2xx: postStatus !== null && postStatus >= 200 && postStatus <= 299,
    id_calibracion_nuevo: createdId !== null && !preIds.includes(createdId),
    id_dispositivo_iot: created ? created.id_dispositivo_iot === Number(value('device_id')) : false,
    id_sensor: created ? created.id_sensor === Number(value('sensor_id')) : false,
    id_usuario: created && me ? created.id_usuario === me.id_usuario : false,
    fecha_calibracion_mismo_instante: created ? sameInstant(created.fecha_calibracion, calibrationAt) : false,
    valor_referencia_equivalente: created ? sameDecimal(created.valor_referencia, value('reference_value')) : false,
    observaciones: created ? created.observaciones === OBSERVATIONS : false,
    registro_en_historial: Boolean(persisted),
    historial_conserva_los_seis_valores: Boolean(persisted) && (
      persisted.id_dispositivo_iot === Number(value('device_id')) &&
      persisted.id_sensor === Number(value('sensor_id')) &&
      (me ? persisted.id_usuario === me.id_usuario : false) &&
      sameDecimal(persisted.valor_referencia, value('reference_value')) &&
      persisted.observaciones === OBSERVATIONS &&
      sameInstant(persisted.fecha_calibracion, calibrationAt)
    )
  };

  const failedAssertions = (summary && summary.run && summary.run.failures ? summary.run.failures : [])
    .map(f => ({ source: f.source && f.source.name, error: f.error && f.error.message }))
    .filter(f => f.error);

  const artifact = {
    caso: CASE_ID,
    grupo: GROUP_ID,
    requisito: 'RF-24 v2.0',
    casoDeUso: 'CU05 — Gestionar Dispositivos IoT, Flujo D',
    runId,
    ambiente: { decisorio: 'TEST', base_url: baseUrl },
    administradorAuxiliar: {
      usado: true,
      motivo: 'El Ingeniero no tiene dispositivos en su alcance en TEST: GET /configuracion/dispositivos-iot devuelve total 0, por lo que el detalle de dispositivo (RF-21) y las asociaciones del sensor (RF-22) responden 404 para ese actor.',
      gets: [
        'GET /configuracion/dispositivos-iot/{device_id}',
        'GET /configuracion/sensores/{sensor_id}/asociaciones'
      ],
      ejecuta_post_funcional: false
    },
    modo_calibracion: 'SENSOR',
    actor: me ? {
      id_usuario: me.id_usuario,
      rol: me.nombre_rol,
      correo_coincide: me.correo_electronico === actorEmail
    } : null,
    dispositivo: device ? {
      id: device.id_dispositivo_iot,
      serial: device.serial,
      activo: device.es_activo,
      id_infraestructura: device.id_infraestructura
    } : null,
    sensor: selectedSensor ? {
      id: sensorIdOf(selectedSensor),
      nombre: selectedSensor.nombre,
      categoria: selectedSensor.categoria,
      activo: selectedSensor.es_activo,
      id_dispositivo_iot: selectedSensor.id_dispositivo_iot
    } : null,
    area: selectedAssociation ? {
      id_infraestructura: selectedAssociation.id_infraestructura,
      id_dispositivo_iot: selectedAssociation.id_dispositivo_iot,
      vigente: selectedAssociation.tiene_estado
    } : null,
    rangoTecnico: selectedRange ? {
      categoria: selectedRange.categoria,
      min: selectedRange.valor_min,
      max: selectedRange.valor_max
    } : null,
    valorReferencia: value('reference_value'),
    fechaCalibracionEnviada: calibrationAt,
    observaciones: OBSERVATIONS,
    endpoint: `/configuracion/sensores/${value('sensor_id')}/calibrar`,
    metodo: 'POST',
    postsEjecutados: postStatus === null ? 0 : 1,
    httpPost: postStatus,
    statuses: Object.fromEntries(ITEMS.map(name => [name, getStatus(executions, name)])),
    historialPre: historyPre ? { total: historyPre.total, ids: preIds } : null,
    calibracion: created ? {
      id_calibracion: created.id_calibracion,
      id_dispositivo_iot: created.id_dispositivo_iot,
      id_sensor: created.id_sensor,
      id_usuario: created.id_usuario,
      valor_referencia: created.valor_referencia,
      fecha_calibracion: created.fecha_calibracion,
      observaciones: created.observaciones
    } : null,
    historialPost: historyPost ? { total: historyPost.total, ids: postIds } : null,
    registroPersistido: persisted,
    oraculo,
    assertions: {
      total: summary && summary.run ? summary.run.stats.assertions.total : 0,
      failed: failedAssertions.length,
      failures: failedAssertions
    },
    resultado: err || failedAssertions.length || Object.values(oraculo).some(v => v !== true) ? 'FAIL' : 'PASS'
  };

  writeJson(jsonPath, artifact);

  console.log(`\nRUN_ID: ${runId}`);
  console.log(`POST ejecutados: ${artifact.postsEjecutados} | HTTP: ${postStatus}`);
  console.log(`id_calibracion: ${createdId === null ? 'N/A' : createdId}`);
  console.log(`Assertions: ${artifact.assertions.total} | Failures: ${artifact.assertions.failed}`);
  console.log(`Resultado: ${artifact.resultado}`);
  console.log(`Artefacto: ${jsonPath}`);

  if (err) process.exitCode = 1;
  else if (artifact.resultado === 'FAIL') process.exitCode = 2;
});
