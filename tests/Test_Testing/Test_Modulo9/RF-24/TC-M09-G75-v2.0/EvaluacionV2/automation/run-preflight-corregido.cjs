// VALIDACIÓN SUPLEMENTARIA DE AUTOMATIZACIÓN — TC-M09-G75-v2.0
//
// NO es un RUN funcional y no forma parte del oráculo del grupo.
//
// Ejecuta con Newman la colección auxiliar de preflight corregido
// (../TC-M09-G75-v2.0-preflight.postman_collection.json), que prioriza al Ingeniero de
// Campo en todas las lecturas de precondición y usa al Administrador auxiliar solo como
// fallback de solo lectura.
//
// Garantías que el propio script hace cumplir:
//   - 0 POST de calibración: aborta si la colección contiene cualquier POST que no sea /sesiones/.
//   - el HTML del RUN funcional oficial no se toca: se compara su SHA-256 antes y después.
//   - el HTML suplementario se escribe con otro nombre, dentro del mismo RUN.
//
// Uso:
//   $env:QA_BASE_URL="https://api.inmero.co/back-sigab-test"
//   $env:QA_EMAIL="ingeniero@pecuaria.co"
//   $env:QA_PASSWORD="<secreto>"
//   $env:QA_ADMIN_PRIMARY="administador.dev@gmail.com"
//   $env:QA_ADMIN_PASSWORD="<secreto>"
//   $env:G75_RUN_ID="G75-REEVAL-V2-YYYYMMDD-HHMMSS"
//   node .\run-preflight-corregido.cjs

const fs = require('fs');
const path = require('path');
const H = require('./paths-v2.cjs');

const globalNodeModules = path.join(path.dirname(process.execPath), 'node_modules');
const newman = require(path.join(globalNodeModules, 'newman'));

const runId = process.env.G75_RUN_ID;
if (!runId || !/^G75-REEVAL-V2-\d{8}-\d{6}$/.test(runId)) {
  throw new Error('G75_RUN_ID requerido con formato G75-REEVAL-V2-YYYYMMDD-HHMMSS.');
}

const actorEmail = process.env.QA_EMAIL;
const actorSecret = process.env.QA_PASSWORD;
if (!actorEmail || !actorSecret) throw new Error('QA_EMAIL y QA_PASSWORD requeridos (solo en memoria de proceso).');
const adminEmail = process.env.QA_ADMIN_PRIMARY || '';
const adminSecret = process.env.QA_ADMIN_PASSWORD || '';

const COLECCION = path.join(H.EVAL_DIR, 'TC-M09-G75-v2.0-preflight.postman_collection.json');
if (!fs.existsSync(COLECCION)) throw new Error(`No existe la colección de preflight: ${COLECCION}`);

// -------------------------------------------------- guarda de escritura: 0 POST funcionales
const coleccion = JSON.parse(fs.readFileSync(COLECCION, 'utf8'));
const planos = [];
(function recorrer(items) {
  for (const it of items || []) {
    if (it.item) recorrer(it.item);
    else planos.push(it);
  }
})(coleccion.item);

const escrituras = planos.filter((it) => {
  const metodo = (it.request?.method || 'GET').toUpperCase();
  const url = typeof it.request?.url === 'string' ? it.request.url : it.request?.url?.raw || '';
  if (metodo === 'GET') return false;
  return !(metodo === 'POST' && /\/sesiones\/?$/.test(url)); // la autenticación no escribe datos de negocio
});
if (escrituras.length) {
  throw new Error(
    'ABORTADO: la colección de preflight contiene operaciones de escritura: ' +
    escrituras.map(x => `${x.request.method} ${x.request.url.raw || x.request.url}`).join(', ')
  );
}
if (planos.some(it => /\/calibrar/.test(typeof it.request?.url === 'string' ? it.request.url : it.request?.url?.raw || ''))) {
  throw new Error('ABORTADO: la colección de preflight no puede referenciar el endpoint de calibración.');
}

// ------------------------------------- custodia del HTML del RUN funcional oficial
const newmanDir = H.runDir(runId, 'newman');
const htmlFuncional = path.join(newmanDir, `newman-${H.GROUP_ID}.html`);
const htmlSuplementario = path.join(newmanDir, 'newman-preflight-corregido.html');
if (htmlSuplementario === htmlFuncional) throw new Error('ABORTADO: el HTML suplementario no puede sobrescribir el del RUN funcional.');
if (!fs.existsSync(htmlFuncional)) throw new Error(`ABORTADO: falta el HTML del RUN funcional (${htmlFuncional}).`);
const shaFuncionalAntes = H.sha256(htmlFuncional);

const env = [
  ['base_url', H.base()],
  ['actor_email', actorEmail],
  ['actor_secret', actorSecret],
  ['admin_email', adminEmail],
  ['admin_secret', adminSecret],
  ['device_id', process.env.G75_DEVICE_ID || '3'],
  ['sensor_id', process.env.G75_SENSOR_ID || '6'],
  ['area_id', process.env.G75_AREA_ID || '3'],
  ['categoria', process.env.G75_CATEGORY || 'TEMPERATURA'],
  // IDs de las calibraciones válidas creadas por el RUN funcional oficial: solo se leen.
  ['ids_validas_del_run', process.env.G75_IDS_VALIDAS || '28,29'],
  ['admin_fallback_usado', 'NO']
];

console.log('VALIDACIÓN SUPLEMENTARIA DE PREFLIGHT — solo lectura, 0 POST de calibración.\n');

newman.run({
  collection: COLECCION,
  reporters: ['cli', 'htmlextra'],
  reporter: {
    htmlextra: {
      export: htmlSuplementario,
      title: 'TC-M09-G75-v2.0 — VALIDACIÓN SUPLEMENTARIA DE AUTOMATIZACIÓN (preflight corregido, solo lectura, 0 POST de calibración)',
      omitHeaders: true,
      showEnvironmentData: false,
      showGlobalData: false,
      skipEnvironmentVars: ['actor_secret', 'admin_secret', 'session_value', 'admin_session'],
      showMarkdownLinks: false
    }
  },
  envVar: env.map(([key, value]) => ({ key, value }))
}, (err, summary) => {
  try {
    finalizar(err, summary);
  } catch (e) {
    console.error('Error al consolidar la validación suplementaria:', e.message);
    process.exitCode = 1;
  }
});

function finalizar(err, summary) {
  if (fs.existsSync(htmlSuplementario)) {
    fs.writeFileSync(htmlSuplementario, H.cleanHtml(fs.readFileSync(htmlSuplementario, 'utf8')));
  }
  const shaFuncionalDespues = H.sha256(htmlFuncional);
  const originalIntacto = shaFuncionalAntes === shaFuncionalDespues;

  const ejecuciones = summary?.run?.executions || [];
  const valorEnv = (k) => summary?.environment?.values?.find?.(x => x.key === k)?.value ?? null;

  const porItem = ejecuciones.map((e) => {
    const metodo = (e.request?.method || '').toUpperCase();
    const url = e.request?.url ? e.request.url.toString() : null;
    const asserts = (e.assertions || []).map(a => ({ assertion: a.assertion, paso: !a.error, error: a.error ? a.error.message : null }));
    return {
      item: e.item?.name ?? null,
      metodo,
      url,
      http: e.response?.code ?? null,
      esAutenticacion: metodo === 'POST' && /\/sesiones\/?$/.test(url || ''),
      assertions: asserts.length,
      fallidas: asserts.filter(a => !a.paso).length,
      detalle: asserts
    };
  });

  const itemsDeLaColeccion = planos.map(x => x.name);
  const ejecutados = porItem.map(x => x.item);
  const omitidos = itemsDeLaColeccion.filter(n => !ejecutados.includes(n));

  const getEjecutados = porItem.filter(x => x.metodo === 'GET').length;
  const postAutenticacion = porItem.filter(x => x.esAutenticacion).length;
  const postFuncionales = porItem.filter(x => x.metodo !== 'GET' && !x.esAutenticacion).length;

  const fallos = (summary?.run?.failures || [])
    .map(f => ({ item: f.source?.name, assertion: f.error?.test, error: f.error?.message }))
    .filter(f => f.error);

  const assertionsTotal = summary?.run?.stats?.assertions?.total || 0;
  const verificada = !err && fallos.length === 0 && postFuncionales === 0 &&
    valorEnv('disp_fuente') === 'Ingeniero' && valorEnv('asoc_fuente') === 'Ingeniero';

  const artefacto = {
    grupo: H.GROUP_ID,
    runIdFuncional: runId,
    tipo: 'validacion_suplementaria_qa',
    formaParteDelRunFuncional: false,
    fecha: new Date().toISOString(),
    ambiente: 'TEST',
    base_url: H.base(),
    soloLectura: true,
    postDeCalibracionEjecutados: 0,
    postFuncionalesEjecutados: postFuncionales,
    postDeAutenticacionEjecutados: postAutenticacion,
    getEjecutados,
    requestsEjecutados: porItem.length,
    itemsOmitidosPorElFallbackNoNecesario: omitidos,
    assertions: { total: assertionsTotal, fallidas: fallos.length, fallos },
    discovery: {
      actorPrincipal: 'Ingeniero de Campo',
      usuarioActor: actorEmail,
      administradorComoFallbackDeSoloLectura: true,
      administradorConfigurado: adminEmail || null,
      administradorRealmenteUsado: valorEnv('admin_fallback_usado') === 'SI',
      dispositivo: { fuenteDeLectura: valorEnv('disp_fuente'), httpConIngeniero: valorEnv('disp_http_ingeniero'), httpConAdministrador: valorEnv('disp_http_administrador') },
      asociaciones: { fuenteDeLectura: valorEnv('asoc_fuente'), httpConIngeniero: valorEnv('asoc_http_ingeniero'), httpConAdministrador: valorEnv('asoc_http_administrador') }
    },
    fixtureComprobado: {
      id_dispositivo_iot: Number(process.env.G75_DEVICE_ID || 3),
      id_sensor: Number(process.env.G75_SENSOR_ID || 6),
      id_infraestructura: Number(process.env.G75_AREA_ID || 3),
      categoria: process.env.G75_CATEGORY || 'TEMPERATURA',
      rangoVigente: { min: valorEnv('range_min'), max: valorEnv('range_max') }
    },
    persistenciaDeLasValidasDelRun: {
      ids: String(process.env.G75_IDS_VALIDAS || '28,29').split(',').filter(Boolean).map(Number),
      historialTotal: valorEnv('historial_total'),
      historialIds: valorEnv('historial_ids'),
      nota: 'Comprobado con GET: las assertions del item «Historial del sensor» verifican que cada id siga presente.'
    },
    custodiaDelRunFuncional: {
      html: `newman/newman-${H.GROUP_ID}.html`,
      sha256Antes: shaFuncionalAntes,
      sha256Despues: shaFuncionalDespues,
      intacto: originalIntacto
    },
    htmlSuplementario: 'newman/newman-preflight-corregido.html',
    resultado: verificada ? 'CORRECCION VERIFICADA' : 'CORRECCION NO VERIFICADA',
    nota: 'Esta validacion no reemplaza ni modifica el Newman del RUN funcional oficial y no interviene en el oraculo de TC-M09-142/143/144/145-v2.0.'
  };

  H.save(runId, 'validacion_suplementaria_preflight.json', artefacto);

  console.log('\n======== VALIDACIÓN SUPLEMENTARIA DE PREFLIGHT ========');
  console.log(`RUN funcional de referencia: ${runId} (no se re-ejecuta)`);
  console.log(`requests: ${porItem.length} | GET: ${getEjecutados} | POST de autenticación: ${postAutenticacion} | POST funcionales: ${postFuncionales}`);
  console.log(`assertions: ${assertionsTotal} | fallidas: ${fallos.length}`);
  console.log(`dispositivo leído por: ${artefacto.discovery.dispositivo.fuenteDeLectura} | asociaciones leídas por: ${artefacto.discovery.asociaciones.fuenteDeLectura}`);
  console.log(`fallback de Administrador realmente usado: ${artefacto.discovery.administradorRealmenteUsado ? 'SÍ' : 'NO'}`);
  console.log(`items omitidos (fallback innecesario): ${omitidos.length ? omitidos.join(' | ') : 'ninguno'}`);
  console.log(`HTML del RUN funcional intacto: ${originalIntacto ? 'SÍ' : 'NO'} (${shaFuncionalAntes.slice(0, 16)}…)`);
  console.log(`RESULTADO: ${artefacto.resultado}`);
  console.log('=======================================================\n');

  if (err) process.exitCode = 1;
  else if (!originalIntacto) process.exitCode = 4;
  else if (!verificada) process.exitCode = 2;
}
