// Runner del único RUN oficial de TC-M09-G80-v2.0 (RF-24 v2.0 / TC-M09-151-v2.0).
//
// Flujo: el Ingeniero ejecuta UNA calibración SENSOR y el Administrador consulta el historial
// RF-10 (GET /auditoria/) dentro de una ventana construida con los tiempos reales de esa
// calibración. El oráculo es encontrar un evento correlacionable con la operación.
//
// Presupuesto: 1 POST de calibración. No hay segundo POST automático. Si queda ambiguo, se
// reconcilia por GET del historial y no se reenvía.
//
// Uso:
//   $env:QA_BASE_URL="https://api.inmero.co/back-sigab-test"
//   $env:QA_ING_EMAIL / $env:QA_ING_PASSWORD
//   $env:QA_ADMIN_PRIMARY / $env:QA_ADMIN_SECONDARY / $env:QA_ADMIN_PASSWORD
//   $env:G80_RUN_ID="run-YYYYMMDD-HHMMSS"
//   node .\run-newman.cjs

const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');

// Guard de aislamiento: no puede ejecutarse desde la carpeta histórica TC-M09-G80/.
const FOLDER = 'TC-M09-G80-v2.0';
if (path.basename(__dirname) !== FOLDER) {
  throw new Error(`Directorio no autorizado para ${FOLDER}`);
}

const globalNodeModules = path.join(path.dirname(process.execPath), 'node_modules');
const newman = require(path.join(globalNodeModules, 'newman'));

const GROUP_ID = 'TC-M09-G80-v2.0';
const CASO = 'TC-M09-151-v2.0';
const RF = 'RF-24 v2.0';
const CU = 'CU05 — Gestionar Dispositivos IoT, Flujo D';
const OBSERVACIONES = 'QA TC-M09-151-v2.0';

const runId = process.env.G80_RUN_ID;
if (!runId || !/^run-\d{8}-\d{6}$/.test(runId)) throw new Error('G80_RUN_ID requerido con formato run-YYYYMMDD-HHMMSS.');
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

// Fixture preferido por la matriz; se valida por GET y no se asume vigente.
const FIXTURE = {
  sensor: Number(process.env.G80_SENSOR_ID || 6),
  dispositivo: Number(process.env.G80_DEVICE_ID || 3),
  area: Number(process.env.G80_AREA_ID || 3),
  categoria: process.env.G80_CATEGORY || 'TEMPERATURA',
  valor: process.env.G80_VALOR || '22.5000',
};

const log = (...a) => console.log(...a);

// --------------------------------------------------------------------- sanitización
const secretos = () => [ingSecret, adminSecret].filter(Boolean);
function clean(texto) {
  let s = String(texto);
  for (const x of new Set(secretos())) s = s.split(x).join('[REDACTED]');
  return s
    .replace(/eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]*/g, '[JWT REDACTED]')
    .replace(/Bearer\s+[A-Za-z0-9_.-]{12,}/g, 'Bearer [REDACTED]')
    .replace(/(postgres(?:ql)?:\/\/[^:/\s]+):[^@\s]+@/g, '$1:[REDACTED]@');
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
    grupo: GROUP_ID, caso: CASO, requisito: RF, casoDeUso: CU, run_id: runId,
    ambiente: { decisorio: 'TEST', base_url: base },
    carpeta: `tests/Test_Testing/Test_Modulo9/RF-24/${FOLDER}/`,
  };

  // ------------------------------------------------------------------- git
  evidencia.git = {
    rama: git(['branch', '--show-current']),
    status_short: git(['status', '--short']) || '(vacio)',
    diff_stat: git(['diff', '--stat']) || '(vacio)',
    diff_cached_stat: git(['diff', '--cached', '--stat']) || '(vacio)',
    head: git(['rev-parse', 'HEAD']),
    origin_test: git(['rev-parse', 'origin/test']),
    divergencia: git(['rev-list', '--left-right', '--count', 'HEAD...origin/test']),
    historica_g80_status: git(['status', '--short', '--', 'tests/Test_Testing/Test_Modulo9/RF-24/TC-M09-G80']) || '(vacio = intacta)',
  };

  // ------------------------------------------------------------------- OpenAPI
  const openapi = await (await fetch(base + '/openapi.json', { signal: AbortSignal.timeout(30000) })).json();
  const requeridos = [
    ['post', '/configuracion/sensores/{id_sensor}/calibrar'],
    ['get', '/configuracion/sensores/{id_sensor}/calibraciones'],
    ['get', '/auditoria/'],
    ['get', '/auditoria/catalogo/tipos-evento'],
  ];
  evidencia.openapi = { fuente: base + '/openapi.json', endpoints: {} };
  for (const [m, p] of requeridos) {
    const op = openapi.paths?.[p]?.[m] || null;
    evidencia.openapi.endpoints[`${m.toUpperCase()} ${p}`] = {
      presente: Boolean(op), codigosDeclarados: op ? Object.keys(op.responses || {}) : [],
    };
  }
  for (const [m, p] of requeridos.slice(0, 3)) {
    if (!openapi.paths?.[p]?.[m]) throw new Error(`BLOQUEADO: ${m.toUpperCase()} ${p} no está desplegado en TEST.`);
  }
  evidencia.openapi.modo_calibracion_declarado = JSON.stringify(openapi).includes('modo_calibracion');

  // ------------------------------------------------------------------- Admin efectivo
  let adminUsado = null, tokenAdmin = null;
  const intentosAdmin = [];
  for (const correo of [process.env.QA_ADMIN_PRIMARY, process.env.QA_ADMIN_SECONDARY].filter(Boolean)) {
    const r = await login(correo, adminSecret);
    if (r.status === 200 && r.token) { adminUsado = correo; tokenAdmin = r.token; intentosAdmin.push({ correo, resultado: 'autentica' }); break; }
    intentosAdmin.push({ correo, resultado: `no autentica (HTTP ${r.status}${r.errorCode ? ' ' + r.errorCode : ''})` });
  }
  if (!tokenAdmin) throw new Error('BLOQUEADO: ningún Administrador autenticó; sin él no puede consultarse /auditoria/.');
  log(`Administrador efectivo: ${adminUsado}`);

  // Catálogo de tipos de evento: hallazgo de preflight, no cierra el caso por sí solo.
  const catalogo = await pedir('/auditoria/catalogo/tipos-evento', tokenAdmin);
  const tiposCatalogo = catalogo.cuerpo?.items || catalogo.cuerpo || [];
  const tiposCalibracion = (Array.isArray(tiposCatalogo) ? tiposCatalogo : [])
    .filter(t => JSON.stringify(t).toLowerCase().includes('calibr'));
  evidencia.catalogo_tipos_evento = {
    http: catalogo.status,
    total: Array.isArray(tiposCatalogo) ? tiposCatalogo.length : null,
    tiposRelacionadosConCalibracion: tiposCalibracion,
    nota: 'La ausencia de un tipo de evento para calibración EXITOSA es un hallazgo de preflight; el caso se decide con la verificación empírica de /auditoria/.',
  };
  log(`Catálogo de tipos de evento: ${tiposCalibracion.length} relacionados con calibración ` +
      `(${tiposCalibracion.map(t => t.nombre).join(', ') || 'ninguno'})`);

  log('\nIniciando el RUN oficial. POST de calibración planificados: 1.\n');

  const env = [
    ['base_url', base],
    ['ing_email', ingEmail], ['ing_secret', ingSecret],
    ['admin_email', adminUsado], ['admin_secret', adminSecret],
    ['device_id', String(FIXTURE.dispositivo)], ['sensor_id', String(FIXTURE.sensor)],
    ['area_id', String(FIXTURE.area)], ['categoria', FIXTURE.categoria], ['valor', FIXTURE.valor],
    ['observaciones', OBSERVACIONES],
    ['body_calibracion', '{' +
      '"modo_calibracion":"SENSOR",' +
      `"id_dispositivo_iot":${FIXTURE.dispositivo},` +
      `"id_infraestructura":${FIXTURE.area},` +
      `"valor_referencia":${FIXTURE.valor},` +
      `"observaciones":${JSON.stringify(OBSERVACIONES)},` +
      '"fecha_calibracion":"__FECHA__"' +
      '}'],
  ];

  newman.run({
    collection: path.join(__dirname, 'TC-M09-G80-v2.0.postman_collection.json'),
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
    finalizar(err, summary, tokenAdmin, adminUsado, intentosAdmin, evidencia)
      .catch((e) => { console.error('Error al consolidar el RUN:', e.message); process.exitCode = 1; });
  });
})().catch((e) => { console.error('\nRUN NO COMPLETADO:', e.message); process.exitCode = 1; });

async function finalizar(err, summary, tokenAdmin, adminUsado, intentosAdmin, evidencia) {
  const ex = summary?.run?.executions || [];
  const find = (n) => ex.find(x => x.item && x.item.name === n);
  const cuerpoDe = (n) => { const e = find(n); if (!e || !e.response) return null; try { return JSON.parse(e.response.stream.toString()); } catch { return null; } };
  const statusDe = (n) => { const e = find(n); return e && e.response ? e.response.code : null; };
  const enviadoDe = (n) => { const e = find(n); try { return JSON.parse(e.request.body.raw.toString()); } catch { return null; } };
  const envDe = (k) => summary?.environment?.values?.find?.(x => x.key === k)?.value ?? null;

  if (fs.existsSync(htmlPath)) fs.writeFileSync(htmlPath, cleanHtml(fs.readFileSync(htmlPath, 'utf8')));

  const perfilIng = cuerpoDe('Identidad Ingeniero');
  const perfilAdm = cuerpoDe('Identidad Administrador');
  const pre = cuerpoDe('Historial PRE');
  const resp = cuerpoDe('POST calibrar');
  const post = cuerpoDe('Historial POST');
  const statusPost = statusDe('POST calibrar');
  const enviado = enviadoDe('POST calibrar');

  evidencia.actor_calibracion = perfilIng ? {
    correo: perfilIng.correo_electronico, id_usuario: perfilIng.id_usuario,
    rol: perfilIng.nombre_rol, estado_cuenta: perfilIng.estado_cuenta, credencial: '[REDACTED]',
  } : null;
  evidencia.actor_auditoria = {
    correo: adminUsado, id_usuario: perfilAdm?.id_usuario ?? null, rol: perfilAdm?.nombre_rol ?? null,
    credencial: '[REDACTED]', intentos: intentosAdmin,
    uso: 'consulta de /auditoria/ y GET de fixture fuera del alcance del Ingeniero; no ejecuta la calibración',
  };
  evidencia.fixture = {
    origen: 'fixture oficial del caso, validado por GET en este RUN',
    id_sensor: FIXTURE.sensor, id_dispositivo_iot: FIXTURE.dispositivo,
    id_infraestructura: FIXTURE.area, categoria: FIXTURE.categoria, valor_referencia: FIXTURE.valor,
  };

  const idCalibracion = resp?.id_calibracion ?? null;
  const preIds = pre ? (pre.items || []).map(x => x.id_calibracion) : null;
  const postIds = post ? (post.items || []).map(x => x.id_calibracion) : null;
  const persistido = post && idCalibracion ? (post.items || []).find(x => x.id_calibracion === idCalibracion) || null : null;

  evidencia.calibracion = {
    pre: pre ? { total: pre.total, ids: preIds } : null,
    request: enviado ? {
      endpoint: `/configuracion/sensores/${FIXTURE.sensor}/calibrar`, metodo: 'POST',
      headers: { Authorization: '[REDACTED]', 'Content-Type': 'application/json' }, body: enviado,
    } : null,
    response: { http: statusPost, cuerpo: resp },
    post: post ? { total: post.total, ids: postIds } : null,
    id_calibracion: idCalibracion,
    registro_persistido: persistido,
    timestamps: {
      t_request_before: envDe('t_request_before'),
      t_response_after: envDe('t_response_after'),
      fecha_enviada: enviado?.fecha_calibracion ?? null,
      fecha_persistida: resp?.fecha_calibracion ?? null,
    },
    postsEjecutados: statusPost === null ? 0 : 1,
  };

  // ---------------------------------------------- oráculo de auditoría RF-10
  const ventanaDesde = envDe('ventana_desde');
  const ventanaHasta = envDe('ventana_hasta');
  const auditoriaStatus = statusDe('Auditoría RF-10');
  const auditoriaP1 = cuerpoDe('Auditoría RF-10');

  let eventos = auditoriaP1 ? (auditoriaP1.items || []).slice() : [];
  const totalAuditoria = auditoriaP1 ? Number(auditoriaP1.total) : null;
  const paginas = [{ pagina: 1, http: auditoriaStatus, devueltos: eventos.length }];

  // Si hay más de una página, se recorren todas con la misma fecha_hasta: no se concluye
  // ausencia de evento mirando solo la primera página.
  if (tokenAdmin && totalAuditoria && totalAuditoria > eventos.length && perfilIng) {
    const tamano = 50;
    const totalPaginas = Math.ceil(totalAuditoria / tamano);
    for (let p = 2; p <= totalPaginas && p <= 40; p += 1) {
      const q = `/auditoria/?id_usuario=${perfilIng.id_usuario}` +
                `&fecha_desde=${encodeURIComponent(ventanaDesde)}` +
                `&fecha_hasta=${encodeURIComponent(ventanaHasta)}&tamano=${tamano}&pagina=${p}`;
      const r = await pedir(q, tokenAdmin);
      const lote = r.cuerpo?.items || [];
      paginas.push({ pagina: p, http: r.status, devueltos: lote.length });
      eventos = eventos.concat(lote);
      if (!lote.length) break;
    }
  }

  // Correlación ESTRICTA: el evento debe contener a la vez sensor, dispositivo y valor.
  // Un login o cualquier otro evento del mismo usuario en la ventana no satisface el caso.
  const sensorStr = String(FIXTURE.sensor);
  const dispStr = String(FIXTURE.dispositivo);
  const valorNum = Number(FIXTURE.valor);
  const textoDe = (ev) => `${JSON.stringify(ev.detalle ?? {})} ${ev.descripcion ?? ''}`;
  const correlaciona = (ev) => {
    const t = textoDe(ev);
    const tieneValor = t.includes(String(valorNum)) || t.includes(valorNum.toFixed(4)) || t.includes(FIXTURE.valor);
    const tieneCalibracion = idCalibracion !== null && t.includes(String(idCalibracion));
    const dentro = ventanaDesde && ventanaHasta &&
      new Date(ev.fecha_evento) >= new Date(ventanaDesde) && new Date(ev.fecha_evento) <= new Date(ventanaHasta);
    const delIngeniero = perfilIng ? ev.id_usuario === perfilIng.id_usuario : false;
    return {
      ev, dentro, delIngeniero,
      tieneSensor: t.includes(sensorStr), tieneDispositivo: t.includes(dispStr),
      tieneValor, tieneIdCalibracion: tieneCalibracion,
      esMatch: dentro && delIngeniero && t.includes(sensorStr) && t.includes(dispStr) && tieneValor,
    };
  };
  const analisis = eventos.map(correlaciona);
  const match = analisis.find(a => a.esMatch) || null;

  evidencia.auditoria_rf10 = {
    actor: adminUsado,
    consulta: `GET /auditoria/?id_usuario=${perfilIng?.id_usuario ?? '<ing>'}&fecha_desde=${ventanaDesde}&fecha_hasta=${ventanaHasta}&tamano=50`,
    http: auditoriaStatus,
    ventana: { desde: ventanaDesde, hasta: ventanaHasta, criterio: 'timestamp real de la calibración ±1 minuto' },
    total_consultado: totalAuditoria,
    paginas_recorridas: paginas,
    eventos_recuperados: eventos.length,
    eventos: eventos.map(ev => ({
      id_evento: ev.id_evento, tipo_evento: ev.tipo_evento, fecha_evento: ev.fecha_evento,
      modulo: ev.modulo, resultado: ev.resultado, categoria: ev.categoria,
      id_usuario: ev.id_usuario, descripcion: ev.descripcion,
      detalle: ev.detalle, integridad_ok: ev.integridad_ok,
    })),
    correlacion: analisis.map(a => ({
      id_evento: a.ev.id_evento, tipo_evento: a.ev.tipo_evento, fecha_evento: a.ev.fecha_evento,
      dentroDeVentana: a.dentro, delIngeniero: a.delIngeniero, tieneSensor: a.tieneSensor,
      tieneDispositivo: a.tieneDispositivo, tieneValor: a.tieneValor,
      tieneIdCalibracion: a.tieneIdCalibracion, esMatch: a.esMatch,
    })),
    match: match ? {
      id_evento: match.ev.id_evento, tipo_evento: match.ev.tipo_evento,
      fecha_evento: match.ev.fecha_evento, modulo: match.ev.modulo,
      resultado: match.ev.resultado, integridad_ok: match.ev.integridad_ok,
    } : null,
    criterio: 'Un evento solo cuenta si contiene simultáneamente sensor, dispositivo y valor de la operación, pertenece al Ingeniero y cae dentro de la ventana.',
  };

  // Diagnóstico secundario: la auditoría interna de M09 no sustituye al esperado RF-10.
  evidencia.diagnostico_bd = {
    disponible: false,
    auditoria_modulo9: null,
    motivo: 'No hay acceso SQL autorizado de solo lectura a la base de TEST desde este entorno; el caso se decide con la API.',
    nota: 'Una fila en modulo9.auditorias_calibraciones no aprobaría G80-v2.0 si falta el registro correlacionable en RF-10.',
  };

  // ---------------------------------------------- resultado
  const failures = (summary?.run?.failures || [])
    .map(f => ({ item: f.source?.name, assertion: f.error?.test, error: f.error?.message })).filter(f => f.error);
  const calibracionOk = statusPost !== null && statusPost >= 200 && statusPost < 300 && Boolean(idCalibracion) && Boolean(persistido);

  let resultado, motivo, causa, incidencia;
  if (!calibracionOk) {
    resultado = 'BLOQUEADO / NO VERIFICABLE';
    motivo = `No pudo crearse la calibración de setup (HTTP ${statusPost}), de modo que el oráculo de auditoría no es alcanzable.`;
    causa = 'Precondición funcional no disponible en TEST.';
    incidencia = {
      requerida: 'Por determinar', nota: 'Depende de si el fallo del POST proviene del dato de prueba o de un defecto del producto.',
      detalleRespuesta: resp,
    };
  } else if (match) {
    resultado = 'APROBADO';
    motivo = 'La calibración SENSOR creada durante el RUN fue encontrada en /auditoria/ y sus datos coinciden con la operación.';
    causa = null;
    incidencia = { requerida: 'NO' };
  } else {
    resultado = 'RECHAZADO';
    motivo = 'La calibración SENSOR se creó correctamente, pero el historial RF-10 no contiene un evento que registre esa calibración dentro de la ventana evaluada.';
    causa = 'Por determinar';
    incidencia = { requerida: 'SÍ' };
  }

  evidencia.resultado = resultado;
  evidencia.motivo = motivo;
  evidencia.causa = causa;
  evidencia.incidencia = incidencia;
  evidencia.newman = {
    assertions: summary?.run?.stats?.assertions?.total || 0,
    failures: failures.length, detalleFailures: failures,
  };

  // Revisión de secretos sobre la propia evidencia, registrada aquí mismo.
  const serializada = JSON.stringify(evidencia);
  const patrones = [
    ['credencial en claro', new RegExp([ingSecret, adminSecret].filter(Boolean).map(s => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|'))],
    ['JWT', /eyJ[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,}\./],
    ['Authorization con token', /Bearer\s+[A-Za-z0-9_.-]{12,}/],
    ['cadena de conexión con contraseña', /postgres(?:ql)?:\/\/[^:/\s]+:[^@\s]+@/],
  ];
  evidencia.seguridad = {
    hallazgos: patrones.filter(([, re]) => re.source && re.test(serializada)).map(([n]) => n),
    limpio: !patrones.some(([, re]) => re.source && re.test(serializada)),
    criterio: 'Se buscan valores de secreto, no vocabulario. El reporte Newman se genera con omitHeaders y sin environment, y se sanitiza después.',
  };

  guardarJson('evidencia.json', evidencia);

  log('\n================ RESUMEN DEL RUN ================');
  log(`RUN_ID: ${runId}`);
  log(`Fixture: sensor ${FIXTURE.sensor} / dispositivo ${FIXTURE.dispositivo} / área ${FIXTURE.area} / valor ${FIXTURE.valor}`);
  log(`Ingeniero id_usuario: ${perfilIng?.id_usuario ?? 'N/A'} | Administrador: ${adminUsado}`);
  log(`Calibración: HTTP ${statusPost} | id_calibracion ${idCalibracion ?? 'N/A'} | persistida: ${persistido ? 'SÍ' : 'NO'}`);
  log(`Ventana RF-10: ${ventanaDesde} -> ${ventanaHasta}`);
  log(`Auditoría: HTTP ${auditoriaStatus} | total ${totalAuditoria} | eventos recuperados ${eventos.length}`);
  log(`Match correlacionado: ${match ? 'SÍ (id_evento ' + match.ev.id_evento + ')' : 'NO'}`);
  log(`Assertions: ${evidencia.newman.assertions} | Failures: ${evidencia.newman.failures}`);
  log(`CASO ${CASO} → ${resultado}`);
  log(`GRUPO ${GROUP_ID} → ${resultado}`);
  log('=================================================\n');

  if (err) process.exitCode = 1;
  else if (resultado !== 'APROBADO') process.exitCode = 2;
}
