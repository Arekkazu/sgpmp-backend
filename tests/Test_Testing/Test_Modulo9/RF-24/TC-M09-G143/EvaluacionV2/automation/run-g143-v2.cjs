/**
 * Runner Newman de TC-M09-G143 (RF-24 v2.0, CU05 Flujo F) — SEGUNDA EVALUACIÓN, parte de TEST.
 *
 * Cubre TC-M09-290 (disparo automático tras el alta de lote, con CERO observaciones) y
 * TC-M09-291 (rechazo manual de un área sin cámara + auditoría RF-10). TC-M09-292 es LOCAL y
 * no pasa por aquí.
 *
 * Modos:
 *   precheck  colección de SOLO LECTURA; consola, sin HTML y sin artefactos.
 *   run       colección oficial; un único HTML en RESULTADOS/<RUN>/newman/.
 *
 * Reglas que el runner hace cumplir, no solo documenta:
 *   · la colección es dueña de sus dos sesiones; el runner no autentica por fuera;
 *   · presupuesto duro: 1 alta M02 (TC-290) y 1 POST VISION (TC-291, sobre A2), 0 reintentos;
 *   · `POST /iot/telemetria/vision` = 0: TC-290 exige un área sin observaciones;
 *   · el único POST a calibraciones-vision debe apuntar a A2, nunca a A1: disparar VISION a
 *     mano sobre A1 cambiaría el caso de TC-290.
 *
 * Uso:
 *   node run-g143-v2.cjs precheck
 *   node run-g143-v2.cjs run <RUN_ID>
 */
'use strict';

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

function requerirNewman() {
  try {
    return require('newman');
  } catch (e) {
    const raiz = execSync('npm root -g', { encoding: 'utf8' }).trim();
    module.paths.push(raiz);
    return require(path.join(raiz, 'newman'));
  }
}
const newman = requerirNewman();

const BASE_DIR = __dirname;
const EVAL_DIR = path.dirname(BASE_DIR);
const CASE_DIR = path.dirname(EVAL_DIR);
const GRUPO = 'TC-M09-G143';
if (path.basename(BASE_DIR) !== 'automation' || path.basename(EVAL_DIR) !== 'EvaluacionV2'
    || path.basename(CASE_DIR) !== GRUPO) {
  throw new Error(`ABORTADO: ruta no autorizada para ${GRUPO}: ${BASE_DIR}`);
}

const BASE_URL = 'https://api.inmero.co/back-sigab-test';
if (!BASE_URL.endsWith('/back-sigab-test')) {
  throw new Error('ABORTADO: el ambiente decisorio de TC-290 y TC-291 es TEST');
}

const ACTORES = {
  admin_correo: 'administador.dev@gmail.com',
  admin_password: 'Test1234!',
  ing_correo: 'ingeniero@pecuaria.co',
  ing_password: 'Test1234!',
};

const COLECCION = path.join(BASE_DIR, 'TC-M09-G143.postman_collection.json');
const PRECHECK = path.join(BASE_DIR, 'TC-M09-G143.precheck.postman_collection.json');

const RE_VISION_CALC = /\/configuracion\/calibraciones-vision(\?|$)/;
const RE_M03 = /\/iot\/telemetria\/vision/;
const RE_ALTA = /\/activos-biologicos(\?|$)/;
const PRESUPUESTO = { alta: 1, vision_manual: 1, m03: 0 };
//: Sello propio de CADA ejecucion. El sufijo del fixture NO puede derivarse del RUN_ID:
//: la politica es "mismo RUN, nueva ejecucion", y las areas 292/293 de la ejecucion 1 ya
//: llevan ese sufijo, asi que la creacion del area responderia 409.
const SELLO = new Date().toISOString().replace(/[-:T]/g, '').slice(0, 14)
  .replace(/^(\d{8})(\d{6})$/, '$1-$2');

const modo = (process.argv[2] || '').trim();
const RUN_ID = (process.argv[3] || '').trim();

function planos(ruta) {
  const col = JSON.parse(fs.readFileSync(ruta, 'utf8'));
  const fuera = [];
  (function recorrer(items) {
    (items || []).forEach((it) => (it.item ? recorrer(it.item) : fuera.push(it)));
  })(col.item);
  return fuera;
}

/** Guarda estática: el único POST a calibraciones-vision debe ser el de TC-291 sobre A2. */
function guardaEstatica(ruta, { exigirVisionSobreA2 }) {
  const items = planos(ruta);
  const visionPosts = items.filter((it) => {
    const m = ((it.request || {}).method || '').toUpperCase();
    const u = (((it.request || {}).url || {}).raw || '');
    return m === 'POST' && RE_VISION_CALC.test(u);
  });
  const m03Posts = items.filter((it) => {
    const m = ((it.request || {}).method || '').toUpperCase();
    const u = (((it.request || {}).url || {}).raw || '');
    return m === 'POST' && RE_M03.test(u);
  });
  if (m03Posts.length > 0) {
    throw new Error('ABORTADO: la colección contiene ingesta M03; TC-290 exige un área con '
                    + `CERO observaciones (${m03Posts.map((i) => i.name).join(', ')}).`);
  }
  if (exigirVisionSobreA2) {
    if (visionPosts.length !== 1) {
      throw new Error(`ABORTADO: se esperaba exactamente 1 POST a calibraciones-vision (TC-291); hay ${visionPosts.length}.`);
    }
    const it = visionPosts[0];
    const scripts = JSON.stringify(it.event || []);
    if (!/a2_id/.test(scripts)) {
      throw new Error(`ABORTADO: el POST a calibraciones-vision de «${it.name}» no apunta a A2. `
                      + 'Disparar VISION a mano sobre A1 cambiaría el caso de TC-290.');
    }
    if (/a1_id/.test(scripts)) {
      throw new Error(`ABORTADO: el POST a calibraciones-vision de «${it.name}» referencia A1.`);
    }
  } else if (visionPosts.length > 0) {
    throw new Error('ABORTADO: el precheck no puede contener POST a calibraciones-vision.');
  }
  return items.length;
}

function entorno(extra) {
  const v = Object.assign({ base_url: BASE_URL }, ACTORES, extra || {});
  return {
    name: `${GRUPO}-${modo}`,
    values: Object.keys(v).map((k) => ({ key: k, value: String(v[k]), enabled: true })),
  };
}

function contadores() {
  return { alta: 0, vision_manual: 0, m03: 0, get: 0, patch: 0, login: 0, otros_post: 0, total: 0 };
}

function clasificar(c, metodo, url) {
  c.total += 1;
  if (metodo === 'GET') { c.get += 1; return; }
  if (metodo === 'PATCH') { c.patch += 1; return; }
  if (metodo !== 'POST') return;
  // El login abre la sesion de la propia coleccion: no es una escritura funcional.
  if (/\/sesiones\/?($|\?)/.test(url)) { c.login += 1; return; }
  if (RE_M03.test(url)) { c.m03 += 1; return; }
  if (RE_VISION_CALC.test(url)) { c.vision_manual += 1; return; }
  if (/\/activos-biologicos\/\d+\//.test(url)) { c.otros_post += 1; return; }
  if (RE_ALTA.test(url)) { c.alta += 1; return; }
  c.otros_post += 1;
}

function ejecutar(opciones, conteo) {
  return new Promise((resolve, reject) => {
    const corrida = newman.run(opciones, (err, resumen) => (err ? reject(err) : resolve(resumen)));
    corrida.on('beforeRequest', (err, args) => {
      if (err || !args || !args.request) return;
      const metodo = String(args.request.method || '').toUpperCase();
      const url = args.request.url ? args.request.url.toString() : '';
      if (metodo === 'POST' && RE_M03.test(url)) {
        throw new Error('ABORTADO: intento de ingesta M03 durante el RUN; TC-290 exige 0 observaciones.');
      }
      clasificar(conteo, metodo, url);
    });
  });
}

function resumenDe(resumen) {
  const r = resumen.run;
  return {
    requests: r.stats.requests.total,
    assertions: r.stats.assertions.total,
    failures: r.stats.assertions.failed,
    detalle_fallos: (r.failures || []).map((f) => ({
      item: ((f.source || {}).name) || '(sin nombre)',
      assertion: (f.error || {}).test || '(sin assertion)',
      mensaje: String((f.error || {}).message || '').slice(0, 400),
    })),
  };
}

function valoresFinales(resumen) {
  const fuera = {};
  const env = ((resumen.environment || {}).values) || {};
  const lista = (env.members || env.values || []);
  (Array.isArray(lista) ? lista : []).forEach((v) => {
    if (!v || !v.key) return;
    if (/password|session|token|access_key|serial|cuerpo_/i.test(v.key)) return;
    fuera[v.key] = v.value;
  });
  return fuera;
}

async function precheck() {
  const n = guardaEstatica(PRECHECK, { exigirVisionSobreA2: false });
  guardaEstatica(COLECCION, { exigirVisionSobreA2: true });
  console.log(`PRECHECK ${GRUPO} — solo lectura (${n} items); sin HTML y sin artefactos.`);
  const conteo = contadores();
  let resumen;
  try {
    resumen = await ejecutar({
      collection: PRECHECK, environment: entorno(), reporters: ['cli'], timeoutRequest: 120000,
    }, conteo);
  } catch (e) {
    console.log(`\nPRECHECK: error de automatización — ${e.message}`);
    console.log('AUTORIZAR_RUN: NO');
    process.exitCode = 1;
    return;
  }
  const r = resumenDe(resumen);
  const escrituras = conteo.alta + conteo.vision_manual + conteo.m03 + conteo.patch + conteo.otros_post;
  console.log(`logins          : ${conteo.login} (sesiones de la coleccion, no son escrituras)`);
  console.log('\n──────── PRECHECK');
  console.log(`requests        : ${r.requests}`);
  console.log(`assertions      : ${r.assertions}`);
  console.log(`failures        : ${r.failures}`);
  console.log(`escrituras      : ${escrituras} (debe ser 0)`);
  console.log(`valores         : ${JSON.stringify(valoresFinales(resumen))}`);
  r.detalle_fallos.forEach((f) => console.log(`  FALLO · ${f.item} · ${f.assertion} · ${f.mensaje}`));
  const ok = r.failures === 0 && escrituras === 0;
  console.log(`\nAUTORIZAR_RUN: ${ok ? 'SÍ' : 'NO'}`);
  if (!ok) process.exitCode = 1;
}

async function run() {
  if (!/^run-\d{8}-\d{6}$/.test(RUN_ID)) {
    throw new Error('ABORTADO: falta el RUN_ID (formato run-YYYYMMDD-HHMMSS)');
  }
  const runDir = path.join(EVAL_DIR, 'RESULTADOS', RUN_ID);
  const newmanDir = path.join(runDir, 'newman');
  fs.mkdirSync(newmanDir, { recursive: true });
  const html = path.join(newmanDir, 'newman-TC-M09-G143.html');
  // La politica del grupo es "mismo RUN logico, varias ejecuciones": los artefactos
  // tecnicos representan la ejecucion oficial mas reciente y el historial vive en el
  // informe. El HTML anterior no bloquea una reejecucion autorizada, pero tampoco se
  // sobrescribe por accidente: hay que declararlo con G143_SOBRESCRIBIR_OFICIAL=1.
  const sobrescribir = /^(1|si|s[ií]|true)$/i.test(
    String(process.env.G143_SOBRESCRIBIR_OFICIAL || ''));
  if (fs.existsSync(html)) {
    if (!sobrescribir) {
      throw new Error(
        `ABORTADO: ya existe el HTML oficial de una ejecucion anterior en ${html}.
`
        + 'Si esta es una reejecucion autorizada del mismo RUN, repite con '
        + 'G143_SOBRESCRIBIR_OFICIAL=1; el historial de resultados se conserva en el '
        + 'informe, no en el HTML.');
    }
    console.log('AVISO: se sobrescribe el HTML oficial anterior por reejecucion declarada '
      + 'con G143_SOBRESCRIBIR_OFICIAL.');
  }
  const n = guardaEstatica(COLECCION, { exigirVisionSobreA2: true });
  console.log(`RUN OFICIAL ${GRUPO} — ${RUN_ID} (${n} items)`);

  const conteo = contadores();
  const resumen = await ejecutar({
    collection: COLECCION,
    environment: entorno({ run_id: RUN_ID, sufijo: SELLO }),
    reporters: ['cli', 'htmlextra'],
    reporter: {
      htmlextra: {
        export: html,
        title: `${GRUPO} — disparo automático sin observaciones y rechazo sin cámara — ${RUN_ID}`,
        browserTitle: `${GRUPO} ${RUN_ID}`,
        showEnvironmentData: false,
        skipSensitiveData: true,
        omitHeaders: true,
      },
    },
    timeoutRequest: 180000,
    // Espaciado: da ventana de observación real tras el alta, sin introducir escrituras.
    delayRequest: 1500,
  }, conteo);

  const r = resumenDe(resumen);
  fs.writeFileSync(path.join(runDir, 'newman-resumen.json'), JSON.stringify({
    run_id: RUN_ID, grupo: GRUPO, ambiente: 'TEST', base_url: BASE_URL,
    casos: ['TC-M09-290', 'TC-M09-291'],
    generado: new Date().toISOString(),
    newman: {
      html: path.relative(runDir, html).replace(/\\/g, '/'),
      requests: r.requests, assertions: r.assertions, failures: r.failures,
      detalle_fallos: r.detalle_fallos,
    },
    presupuesto: {
      alta_m02: conteo.alta,
      post_manual_calibraciones_vision: conteo.vision_manual,
      ingesta_m03: conteo.m03,
      get: conteo.get,
      patch_restauracion: conteo.patch,
      otros_post: conteo.otros_post,
      logins: conteo.login,
      reintentos: 0,
    },
    valores_finales: valoresFinales(resumen),
  }, null, 2), 'utf8');

  console.log('\n──────── RUN OFICIAL');
  console.log(`requests        : ${r.requests}`);
  console.log(`assertions      : ${r.assertions}`);
  console.log(`failures        : ${r.failures}`);
  console.log(`alta M02        : ${conteo.alta} (presupuesto ${PRESUPUESTO.alta})`);
  console.log(`POST VISION      : ${conteo.vision_manual} (presupuesto ${PRESUPUESTO.vision_manual}, solo TC-291 sobre A2)`);
  console.log(`ingesta M03     : ${conteo.m03} (presupuesto ${PRESUPUESTO.m03})`);
  console.log(`HTML            : ${html}`);
  r.detalle_fallos.forEach((f) => console.log(`  FALLO · ${f.item} · ${f.assertion} · ${f.mensaje}`));

  if (conteo.m03 !== PRESUPUESTO.m03) {
    throw new Error(`ABORTADO: se ingirieron ${conteo.m03} lotes M03; TC-290 exige 0.`);
  }
  if (conteo.alta > PRESUPUESTO.alta || conteo.vision_manual > PRESUPUESTO.vision_manual) {
    throw new Error(`ABORTADO: presupuesto excedido (alta ${conteo.alta}, VISION ${conteo.vision_manual}).`);
  }
  console.log('\nLos fallos funcionales, si los hay, son evidencia del caso: no se relajan las assertions.');
}

(async () => {
  if (modo === 'precheck') return precheck();
  if (modo === 'run') return run();
  throw new Error('Uso: node run-g143-v2.cjs precheck | run <RUN_ID>');
})().catch((e) => {
  console.error(e.message);
  process.exitCode = 1;
});
