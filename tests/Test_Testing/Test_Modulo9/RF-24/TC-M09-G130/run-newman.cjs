// Runner del único RUN oficial de TC-M09-G130 (RF-24 v2.0, CU05 Flujo D).
//
// TC-M09-256: dispositivo inexistente en el body, sensor real en la ruta.
// TC-M09-257: sensor inexistente en la ruta, dispositivo real en el body.
// En ambos se exige HTTP 404 con el mensaje COMÚN de referencia del RF y cero persistencia.
//
// Presupuesto: 2 POST de calibración, uno por caso. No hay reintentos: si un POST queda
// ambiguo, se reconcilia con el GET del historial y no se reenvía.
//
// Uso:
//   $env:QA_BASE_URL="https://api.inmero.co/back-sigab-test"
//   $env:QA_ING_EMAIL / $env:QA_ING_PASSWORD
//   $env:QA_ADMIN_PRIMARY / $env:QA_ADMIN_SECONDARY / $env:QA_ADMIN_PASSWORD
//   $env:G130_RUN_ID="run-YYYYMMDD-HHMMSS"
//   node .\run-newman.cjs

const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');

// Guard de carpeta: esta prueba vive en su carpeta oficial, sin sufijo -v2.0.
const FOLDER = 'TC-M09-G130';
if (path.basename(__dirname) !== FOLDER) {
  throw new Error(`Directorio no autorizado para ${FOLDER}`);
}

const globalNodeModules = path.join(path.dirname(process.execPath), 'node_modules');
const newman = require(path.join(globalNodeModules, 'newman'));

const GROUP_ID = 'TC-M09-G130';
const CASOS = ['TC-M09-256', 'TC-M09-257'];
const RF = 'RF-24 v2.0';
const CU = 'CU05 — Gestionar Dispositivos IoT, Flujo D';

// Mensaje COMÚN exigido por RF-24 v2.0 para referencias a hardware inexistente.
// No se adapta al backend ni se reinterpreta después de ver la respuesta.
const MENSAJE_404 =
  'Error de referencia: El sensor o dispositivo especificado no existe. ' +
  'No se puede registrar una calibración sobre un hardware inexistente.';

const runId = process.env.G130_RUN_ID;
if (!runId || !/^run-\d{8}-\d{6}$/.test(runId)) throw new Error('G130_RUN_ID requerido con formato run-YYYYMMDD-HHMMSS.');
const base = (process.env.QA_BASE_URL || '').replace(/\/$/, '');
if (!base) throw new Error('QA_BASE_URL requerido.');
const ingEmail = process.env.QA_ING_EMAIL;
const ingSecret = process.env.QA_ING_PASSWORD;
const adminSecret = process.env.QA_ADMIN_PASSWORD;
if (!ingEmail || !ingSecret || !adminSecret) throw new Error('Credenciales requeridas solo por variables de proceso.');

const outDir = path.join(__dirname, 'RESULTADOS', runId);
if (fs.existsSync(outDir)) throw new Error(`La carpeta ${runId} ya existe. Un RUN oficial no se repite ni se sobrescribe.`);
fs.mkdirSync(outDir, { recursive: true });
const htmlPath = path.join(outDir, 'newman.html');

// Fixture real preferido por la matriz; se valida por GET y no se asume vigente.
const FIXTURE = {
  sensor: Number(process.env.G130_SENSOR_ID || 6),
  dispositivo: Number(process.env.G130_DEVICE_ID || 3),
  area: Number(process.env.G130_AREA_ID || 3),
  categoria: process.env.G130_CATEGORY || 'TEMPERATURA',
  valor: process.env.G130_VALOR || '22.5000',
};
// IDs inexistentes candidatos: el primero que se confirme inexistente es el que se usa.
const CANDIDATOS_INEXISTENTES = (process.env.G130_IDS_INEXISTENTES || '999999,999998,888888')
  .split(',').map(s => Number(s.trim())).filter(Boolean);

const log = (...a) => console.log(...a);

// --------------------------------------------------------------------- sanitización
function clean(texto) {
  let s = String(texto);
  for (const x of new Set([ingSecret, adminSecret].filter(Boolean))) s = s.split(x).join('[REDACTED]');
  return s
    .replace(/eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]*/g, '[JWT REDACTED]')
    .replace(/Bearer\s+[A-Za-z0-9_.-]{12,}/g, 'Bearer [REDACTED]');
}
function cleanHtml(html) {
  return clean(html)
    .replace(/Authorization/gi, '[REDACTED_HEADER]')
    .replace(/Bearer/gi, '[REDACTED_HEADER]')
    .replace(/contrasena/gi, '[REDACTED]')
    .replace(/password/gi, '[REDACTED]')
    .replace(/set-cookie/gi, '[REDACTED]')
    .replace(/refresh_token/gi, '[REDACTED]')
    .replace(/\bjwt\b/gi, '[REDACTED]');
}
const guardarJson = (nombre, valor) =>
  fs.writeFileSync(path.join(outDir, nombre), clean(JSON.stringify(valor, null, 2)));

// --------------------------------------------------------------------- git
const repoRoot = (() => {
  let d = __dirname;
  for (let i = 0; i < 12; i += 1) {
    if (fs.existsSync(path.join(d, '.git'))) return d;
    const p = path.dirname(d);
    if (p === d) break;
    d = p;
  }
  return __dirname;
})();
const git = (args) => {
  try { return execFileSync('git', args, { cwd: repoRoot, encoding: 'utf8' }).trim(); }
  catch (e) { return `ERROR: ${e.message}`; }
};

// --------------------------------------------------------------------- HTTP directo
async function pedir(ruta, token) {
  const r = await fetch(base + ruta, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    signal: AbortSignal.timeout(30000),
  });
  return { status: r.status, cuerpo: await r.json().catch(() => null) };
}
async function login(correo, password) {
  const r = await fetch(base + '/sesiones/', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ correo_electronico: correo, contrasena: password }),
    signal: AbortSignal.timeout(30000),
  });
  const c = await r.json().catch(() => null);
  return { status: r.status, token: c?.token || null, errorCode: c?.error_code || null };
}

(async () => {
  const evidencia = {
    grupo: GROUP_ID, casos: CASOS, requisito: RF, casoDeUso: CU, run_id: runId,
    ambiente: 'TEST', prueba_local: false, base_url: base,
    carpeta: `tests/Test_Testing/Test_Modulo9/RF-24/${FOLDER}/`,
    mensaje_comun_esperado: MENSAJE_404,
  };

  evidencia.git = {
    rama: git(['branch', '--show-current']),
    status_short: git(['status', '--short']) || '(vacio)',
    diff_stat: git(['diff', '--stat']) || '(vacio)',
    diff_cached_stat: git(['diff', '--cached', '--stat']) || '(vacio)',
    head: git(['rev-parse', 'HEAD']),
    origin_test: git(['rev-parse', 'origin/test']),
    divergencia: git(['rev-list', '--left-right', '--count', 'HEAD...origin/test']),
  };

  // ------------------------------------------------------------------- OpenAPI
  const openapi = await (await fetch(base + '/openapi.json', { signal: AbortSignal.timeout(30000) })).json();
  const requeridos = [
    ['post', '/configuracion/sensores/{id_sensor}/calibrar'],
    ['get', '/configuracion/sensores/{id_sensor}/calibraciones'],
    ['get', '/configuracion/dispositivos-iot/{id_dispositivo_iot}'],
  ];
  evidencia.openapi = { fuente: base + '/openapi.json', endpoints: {} };
  for (const [m, p] of requeridos) {
    const op = openapi.paths?.[p]?.[m] || null;
    evidencia.openapi.endpoints[`${m.toUpperCase()} ${p}`] = {
      presente: Boolean(op), codigosDeclarados: op ? Object.keys(op.responses || {}) : [],
    };
    if (!op) throw new Error(`BLOQUEADO: ${m.toUpperCase()} ${p} no está desplegado en TEST.`);
  }
  evidencia.openapi.nota = 'Los códigos declarados se registran como contexto; el oráculo del RF no se ajusta a OpenAPI.';

  // ------------------------------------------------------------------- Admin auxiliar
  let adminUsado = null, tokenAdmin = null;
  const intentosAdmin = [];
  for (const correo of [process.env.QA_ADMIN_PRIMARY, process.env.QA_ADMIN_SECONDARY].filter(Boolean)) {
    const r = await login(correo, adminSecret);
    if (r.status === 200 && r.token) { adminUsado = correo; tokenAdmin = r.token; intentosAdmin.push({ correo, resultado: 'autentica' }); break; }
    intentosAdmin.push({ correo, resultado: `no autentica (HTTP ${r.status}${r.errorCode ? ' ' + r.errorCode : ''})` });
  }
  if (!tokenAdmin) throw new Error('BLOQUEADO: ningún Administrador autenticó; sin él no puede acreditarse que un ID de dispositivo no existe.');
  log(`Administrador auxiliar: ${adminUsado}`);

  // --------------------------------- elección de los IDs inexistentes, verificada por GET
  // El Administrador es quien puede acreditar inexistencia: para el Ingeniero incluso un
  // dispositivo real responde 404 por alcance de finca.
  let deviceInexistente = null;
  const pruebasDispositivo = [];
  for (const id of CANDIDATOS_INEXISTENTES) {
    const r = await pedir(`/configuracion/dispositivos-iot/${id}`, tokenAdmin);
    pruebasDispositivo.push({ id, http: r.status, error_code: r.cuerpo?.error_code ?? null });
    if (r.status === 404) { deviceInexistente = id; break; }
  }
  if (!deviceInexistente) {
    throw new Error('BLOQUEADO: ninguno de los IDs candidatos resultó inexistente como dispositivo; no se crean ni eliminan datos para conseguirlo.');
  }

  const tokenIngPrevio = (await login(ingEmail, ingSecret)).token;
  if (!tokenIngPrevio) throw new Error('BLOQUEADO: el Ingeniero no autentica.');
  let sensorInexistente = null;
  const pruebasSensor = [];
  for (const id of CANDIDATOS_INEXISTENTES) {
    const r = await pedir(`/configuracion/sensores/${id}/calibraciones`, tokenIngPrevio);
    const total = Number(r.cuerpo?.total ?? -1);
    pruebasSensor.push({ id, http: r.status, total, items: (r.cuerpo?.items || []).length });
    if (r.status === 200 && total === 0) { sensorInexistente = id; break; }
  }
  if (!sensorInexistente) {
    throw new Error('BLOQUEADO: ninguno de los IDs candidatos se comporta como sensor inexistente (total 0 sin calibraciones).');
  }

  evidencia.ids_inexistentes = {
    candidatos: CANDIDATOS_INEXISTENTES,
    dispositivo_inexistente: deviceInexistente,
    sensor_inexistente: sensorInexistente,
    verificacion_dispositivo: pruebasDispositivo,
    verificacion_sensor: pruebasSensor,
    criterio: 'La inexistencia del dispositivo se acredita con el Administrador, que ve todos los dispositivos: el 404 del Ingeniero no distinguiría inexistencia de falta de alcance. El sensor se acredita por historial total 0 sin calibraciones.',
  };
  log(`IDs inexistentes confirmados: dispositivo ${deviceInexistente}, sensor ${sensorInexistente}`);

  log('\nIniciando el RUN oficial. POST de calibración planificados: 2.\n');

  const cuerpo = (dispositivo, observaciones) => '{' +
    '"modo_calibracion":"SENSOR",' +
    `"id_dispositivo_iot":${dispositivo},` +
    `"id_infraestructura":${FIXTURE.area},` +
    `"valor_referencia":${FIXTURE.valor},` +
    `"observaciones":${JSON.stringify(observaciones)},` +
    '"fecha_calibracion":"__FECHA__"' +
    '}';

  const env = [
    ['base_url', base],
    ['ing_email', ingEmail], ['ing_secret', ingSecret],
    ['admin_email', adminUsado], ['admin_secret', adminSecret],
    ['device_id', String(FIXTURE.dispositivo)], ['sensor_id', String(FIXTURE.sensor)],
    ['area_id', String(FIXTURE.area)], ['categoria', FIXTURE.categoria], ['valor', FIXTURE.valor],
    ['device_inexistente', String(deviceInexistente)], ['sensor_inexistente', String(sensorInexistente)],
    ['exp_msg', MENSAJE_404], ['stop_all', 'NO'],
    // TC-256: dispositivo inexistente en el body, sensor real en la ruta.
    ['body_256', cuerpo(deviceInexistente, 'QA TC-M09-256')],
    // TC-257: dispositivo real en el body, sensor inexistente en la ruta.
    ['body_257', cuerpo(FIXTURE.dispositivo, 'QA TC-M09-257')],
  ];

  newman.run({
    collection: path.join(__dirname, 'TC-M09-G130.postman_collection.json'),
    reporters: ['cli', 'htmlextra'],
    reporter: {
      htmlextra: {
        export: htmlPath, omitHeaders: true, showEnvironmentData: false, showGlobalData: false,
        skipEnvironmentVars: ['ing_secret', 'admin_secret', 'ing_session', 'admin_session'],
        showMarkdownLinks: false,
      },
    },
    envVar: env.map(([key, value]) => ({ key, value })),
  }, (err, summary) => {
    try {
      finalizar(err, summary, { adminUsado, intentosAdmin, deviceInexistente, sensorInexistente, evidencia });
    } catch (e) { console.error('Error al consolidar el RUN:', e.message); process.exitCode = 1; }
  });
})().catch((e) => { console.error('\nRUN NO COMPLETADO:', e.message); process.exitCode = 1; });

function finalizar(err, summary, ctx) {
  const { adminUsado, intentosAdmin, deviceInexistente, sensorInexistente, evidencia } = ctx;
  const ex = summary?.run?.executions || [];
  const find = (n) => ex.find(x => x.item && x.item.name === n);
  const cuerpoDe = (n) => { const e = find(n); if (!e || !e.response) return null; try { return JSON.parse(e.response.stream.toString()); } catch { return null; } };
  const statusDe = (n) => { const e = find(n); return e && e.response ? e.response.code : null; };
  const enviadoDe = (n) => { const e = find(n); try { return JSON.parse(e.request.body.raw.toString()); } catch { return null; } };

  if (fs.existsSync(htmlPath)) fs.writeFileSync(htmlPath, cleanHtml(fs.readFileSync(htmlPath, 'utf8')));

  const perfil = cuerpoDe('Identidad Ingeniero');
  evidencia.actor = perfil ? {
    correo: perfil.correo_electronico, id_usuario: perfil.id_usuario,
    rol: perfil.nombre_rol, estado_cuenta: perfil.estado_cuenta, credencial: '[REDACTED]',
    nota: 'Los dos POST del caso los ejecuta el Ingeniero de Campo.',
  } : null;
  evidencia.actor_auxiliar = {
    correo: adminUsado, credencial: '[REDACTED]', intentos: intentosAdmin,
    uso: 'GET de precondición: fixture fuera del alcance del Ingeniero y acreditación de la inexistencia del dispositivo. No ejecuta POST.',
  };
  evidencia.fixture = {
    origen: 'fixture oficial del caso, validado por GET en este RUN',
    sensor_real: FIXTURE.sensor, dispositivo_real: FIXTURE.dispositivo,
    id_infraestructura: FIXTURE.area, categoria: FIXTURE.categoria, valor_referencia: FIXTURE.valor,
  };

  // ---------------------------------------------------------------- TC-M09-256
  const pre256 = cuerpoDe('256 Historial PRE');
  const resp256 = cuerpoDe('256 POST calibrar');
  const post256 = cuerpoDe('256 Historial POST');
  const status256 = statusDe('256 POST calibrar');
  const enviado256 = enviadoDe('256 POST calibrar');
  const preIds256 = pre256 ? (pre256.items || []).map(x => x.id_calibracion) : null;
  const postIds256 = post256 ? (post256.items || []).map(x => x.id_calibracion) : null;
  const nuevos256 = preIds256 && postIds256 ? postIds256.filter(x => !preIds256.includes(x)) : null;
  const msg256 = resp256 ? resp256.message ?? null : null;

  const oraculo256 = {
    id_dispositivo_confirmado_inexistente: true,
    actor_ingeniero: perfil?.nombre_rol === 'Ingeniero de Campo',
    sensor_de_ruta_valido: true,
    http_404: status256 === 404,
    mensaje_exacto: msg256 === MENSAJE_404,
    sin_id_calibracion: resp256 ? resp256.id_calibracion === undefined : false,
    mismos_ids: Array.isArray(nuevos256) && nuevos256.length === 0 &&
      JSON.stringify((preIds256 || []).slice().sort()) === JSON.stringify((postIds256 || []).slice().sort()),
    mismo_total: Boolean(pre256) && Boolean(post256) && Number(pre256.total) === Number(post256.total),
  };
  const res256 = status256 === null ? 'BLOQUEADO / NO VERIFICABLE'
    : Object.values(oraculo256).every(v => v === true) ? 'APROBADO' : 'RECHAZADO';

  evidencia['TC-M09-256'] = {
    escenario: 'dispositivo inexistente en el body, sensor real en la ruta',
    id_dispositivo_inexistente: deviceInexistente,
    sensor_de_ruta: FIXTURE.sensor,
    pre: pre256 ? { total: pre256.total, ids: preIds256 } : null,
    request: enviado256 ? {
      endpoint: `/configuracion/sensores/${FIXTURE.sensor}/calibrar`, metodo: 'POST',
      headers: { Authorization: '[REDACTED]', 'Content-Type': 'application/json' }, body: enviado256,
    } : null,
    response: { http: status256, cuerpo: resp256 },
    post: post256 ? { total: post256.total, ids: postIds256 } : null,
    ids_nuevos: nuevos256,
    mensaje_esperado: MENSAJE_404, mensaje_obtenido: msg256,
    diferencia_de_mensaje: msg256 !== null && msg256 !== MENSAJE_404
      ? { esperado: MENSAJE_404, obtenido: msg256, nota: 'comparación exacta; un mensaje específico por entidad no es PASS aunque el HTTP sea 404' } : null,
    oraculo: oraculo256,
    resultado: res256,
    motivo: res256 === 'APROBADO'
      ? 'El POST con dispositivo inexistente fue rechazado con HTTP 404, el mensaje coincide con el mensaje común del RF y no se creó ninguna calibración.'
      : res256 === 'RECHAZADO'
        ? (oraculo256.http_404 && !oraculo256.mensaje_exacto
            ? 'El endpoint devolvió HTTP 404 y no persistió nada, pero el mensaje no coincide con el definido por RF-24 v2.0.'
            : 'El rechazo no cumple el oráculo del caso: ver el detalle del oráculo.')
        : 'No pudo ejecutarse el POST del caso.',
  };

  // ---------------------------------------------------------------- TC-M09-257
  const pre257 = cuerpoDe('Confirmar sensor inexistente (historial PRE)');
  const resp257 = cuerpoDe('257 POST calibrar');
  const post257 = cuerpoDe('257 Historial POST del sensor inexistente');
  const status257 = statusDe('257 POST calibrar');
  const enviado257 = enviadoDe('257 POST calibrar');
  const msg257 = resp257 ? resp257.message ?? null : null;
  const ejecutado257 = status257 !== null;

  const oraculo257 = {
    id_sensor_confirmado_inexistente: true,
    actor_ingeniero: perfil?.nombre_rol === 'Ingeniero de Campo',
    dispositivo_del_body_valido: true,
    http_404: status257 === 404,
    mensaje_exacto: msg257 === MENSAJE_404,
    sin_id_calibracion: resp257 ? resp257.id_calibracion === undefined : false,
    historial_inexistente_total_cero: Boolean(post257) && Number(post257.total) === 0 && (post257.items || []).length === 0,
  };
  const res257 = !ejecutado257 ? 'BLOQUEADO / NO VERIFICABLE'
    : Object.values(oraculo257).every(v => v === true) ? 'APROBADO' : 'RECHAZADO';

  evidencia['TC-M09-257'] = {
    escenario: 'sensor inexistente en la ruta, dispositivo real en el body',
    id_sensor_inexistente: sensorInexistente,
    dispositivo_del_body: FIXTURE.dispositivo,
    pre: pre257 ? { total: pre257.total, items: pre257.items } : null,
    request: enviado257 ? {
      endpoint: `/configuracion/sensores/${sensorInexistente}/calibrar`, metodo: 'POST',
      headers: { Authorization: '[REDACTED]', 'Content-Type': 'application/json' }, body: enviado257,
    } : null,
    response: { http: status257, cuerpo: resp257 },
    post: post257 ? { total: post257.total, items: post257.items } : null,
    mensaje_esperado: MENSAJE_404, mensaje_obtenido: msg257,
    diferencia_de_mensaje: msg257 !== null && msg257 !== MENSAJE_404
      ? { esperado: MENSAJE_404, obtenido: msg257, nota: 'comparación exacta; un mensaje específico por entidad no es PASS aunque el HTTP sea 404' } : null,
    oraculo: oraculo257,
    resultado: res257,
    motivo: res257 === 'APROBADO'
      ? 'El POST sobre un sensor inexistente fue rechazado con HTTP 404, el mensaje coincide con el mensaje común del RF y el historial de ese sensor sigue en total 0.'
      : res257 === 'RECHAZADO'
        ? (oraculo257.http_404 && !oraculo257.mensaje_exacto
            ? 'El endpoint devolvió HTTP 404 y no persistió nada, pero el mensaje no coincide con el definido por RF-24 v2.0.'
            : 'El rechazo no cumple el oráculo del caso: ver el detalle del oráculo.')
        : 'No se ejecutó el POST del caso (posible STOP_ALL por contaminación en TC-M09-256).',
  };

  // ---------------------------------------------------------------- consolidación
  const stopAll = summary?.environment?.values?.find?.(x => x.key === 'stop_all')?.value === 'SI' ||
    (Array.isArray(nuevos256) && nuevos256.length > 0);
  const stopMotivo = summary?.environment?.values?.find?.(x => x.key === 'stop_all_motivo')?.value;
  const failures = (summary?.run?.failures || [])
    .map(f => ({ item: f.source?.name, assertion: f.error?.test, error: f.error?.message })).filter(f => f.error);

  const resultados = [res256, res257];
  const resultadoGeneral = resultados.includes('RECHAZADO') ? 'RECHAZADO'
    : resultados.includes('BLOQUEADO / NO VERIFICABLE') ? 'BLOQUEADO / NO VERIFICABLE' : 'APROBADO';

  // La causa se consolida solo si ambas manifestaciones comparten raíz.
  const mismaCausa = oraculo256.http_404 && oraculo257.http_404 &&
    !oraculo256.mensaje_exacto && !oraculo257.mensaje_exacto;

  let incidencia;
  if (resultadoGeneral === 'APROBADO') {
    incidencia = { requerida: 'NO' };
  } else if (mismaCausa) {
    incidencia = {
      requerida: 'SÍ', grupo_responsable: 'Desarrollo', grupo_de_prueba: GROUP_ID,
      casos_afectados: 'ambos (TC-M09-256 y TC-M09-257)', resultado: 'RECHAZADO',
      motivo: 'Ambos escenarios devuelven HTTP 404 correctamente y sin persistencia, pero con mensajes específicos por entidad en lugar del mensaje común de referencia que define RF-24 v2.0.',
      esperado: MENSAJE_404,
      obtenido: { 'TC-M09-256': msg256, 'TC-M09-257': msg257 },
      causa_raiz: 'La validación de existencia de hardware emite el mensaje propio de cada entidad y no el mensaje común del flujo alterno de RF-24 v2.0. No es un fallo de validación: el código HTTP y la ausencia de persistencia son correctos.',
      type: 'bug', severity: 'Normal', priority: 'Normal',
      consolidada: 'Una sola incidencia: ambas manifestaciones comparten la misma causa raíz.',
      evidencia: 'evidencia.json / newman.html',
    };
  } else {
    incidencia = {
      requerida: 'SÍ', grupo_responsable: 'Por determinar', grupo_de_prueba: GROUP_ID,
      casos_afectados: resultados.map((r, i) => (r !== 'APROBADO' ? CASOS[i] : null)).filter(Boolean).join(', '),
      resultado: resultadoGeneral,
      motivo: 'Los dos casos no fallan por la misma manifestación; revisar el oráculo de cada uno antes de consolidar.',
      esperado: MENSAJE_404, obtenido: { 'TC-M09-256': msg256, 'TC-M09-257': msg257 },
      causa_raiz: 'Por determinar', type: 'bug', severity: 'Normal', priority: 'Normal',
      evidencia: 'evidencia.json / newman.html',
    };
  }

  evidencia.resultado_general = resultadoGeneral;
  evidencia.motivo_general = resultadoGeneral === 'APROBADO'
    ? 'Ambos escenarios de hardware inexistente fueron rechazados con HTTP 404, el mensaje común del RF y sin crear calibraciones.'
    : resultadoGeneral === 'RECHAZADO'
      ? 'El oráculo se alcanzó y el producto incumple: los rechazos ocurren con el código y sin persistencia, pero el mensaje no es el que define RF-24 v2.0.'
      : 'No pudo alcanzarse el oráculo en al menos uno de los casos.';
  evidencia.stop_all = stopAll ? 'SI' : 'NO';
  evidencia.stop_all_motivo = stopMotivo ? JSON.parse(stopMotivo) : null;
  evidencia.presupuesto = {
    postPlanificados: 2,
    postEjecutados: (status256 === null ? 0 : 1) + (status257 === null ? 0 : 1),
  };
  evidencia.incidencia = incidencia;
  evidencia.newman = {
    assertions: summary?.run?.stats?.assertions?.total || 0,
    failures: failures.length, detalleFailures: failures,
  };

  const serializada = JSON.stringify(evidencia);
  const patrones = [
    ['credencial en claro', new RegExp([ingSecret, adminSecret].filter(Boolean).map(s => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|'))],
    ['JWT', /eyJ[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,}\./],
    ['Authorization con token', /Bearer\s+[A-Za-z0-9_.-]{12,}/],
  ];
  evidencia.seguridad = {
    hallazgos: patrones.filter(([, re]) => re.source && re.test(serializada)).map(([n]) => n),
    limpio: !patrones.some(([, re]) => re.source && re.test(serializada)),
    criterio: 'Se buscan valores de secreto, no vocabulario. El reporte Newman se genera con omitHeaders y sin environment, y se sanitiza después.',
  };

  guardarJson('evidencia.json', evidencia);

  log('\n================ RESUMEN DEL RUN ================');
  log(`RUN_ID: ${runId}`);
  log(`Fixture real: sensor ${FIXTURE.sensor} / dispositivo ${FIXTURE.dispositivo} / área ${FIXTURE.area} / valor ${FIXTURE.valor}`);
  log(`IDs inexistentes: dispositivo ${deviceInexistente} | sensor ${sensorInexistente}`);
  log(`POST ejecutados: ${evidencia.presupuesto.postEjecutados}/2 | STOP_ALL: ${evidencia.stop_all}`);
  log(`  TC-M09-256 HTTP=${status256} mensaje=${oraculo256.mensaje_exacto ? 'EXACTO' : 'NO COINCIDE'} persistencia=${oraculo256.mismos_ids ? 'NO' : 'SI/?'} → ${res256}`);
  log(`  TC-M09-257 HTTP=${status257} mensaje=${oraculo257.mensaje_exacto ? 'EXACTO' : 'NO COINCIDE'} historial_total0=${oraculo257.historial_inexistente_total_cero ? 'SI' : 'NO'} → ${res257}`);
  log(`GRUPO ${GROUP_ID} → ${resultadoGeneral}`);
  log(`Assertions: ${evidencia.newman.assertions} | Failures: ${evidencia.newman.failures}`);
  log('=================================================\n');

  if (err) process.exitCode = 1;
  else if (resultadoGeneral !== 'APROBADO') process.exitCode = 2;
}
