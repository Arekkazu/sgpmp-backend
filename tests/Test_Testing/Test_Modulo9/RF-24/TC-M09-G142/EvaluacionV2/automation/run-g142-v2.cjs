/**
 * Runner Newman de TC-M09-G142 (RF-24 v2.0, CU05 Flujo F) — SEGUNDA EVALUACIÓN.
 *
 * Modos:
 *   precheck  colección de SOLO LECTURA; salida por consola, sin HTML y sin artefactos.
 *   run       colección oficial; un único HTML en RESULTADOS/<RUN>/newman/.
 *
 * Reglas que el runner hace cumplir, no solo documenta:
 *   · la colección es dueña de su sesión: el runner no autentica por fuera ni inyecta tokens;
 *   · presupuesto funcional duro: 1 alta M02 y 1 cierre M02, 0 reintentos;
 *   · PROHIBIDO cualquier POST a /configuracion/calibraciones-vision. El runner aborta si la
 *     colección lo contiene o si una petición lo intenta: el propósito del grupo es demostrar
 *     que M02 dispara el cálculo sin solicitud del usuario.
 *
 * Uso:
 *   node run-g142-v2.cjs precheck
 *   node run-g142-v2.cjs run <RUN_ID>
 */
'use strict';

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');
const os = require('os');

// newman y su reporter viven en la instalación global de npm; este archivo está en el árbol
// de pruebas, donde `require` no los alcanza. Se resuelven por la raíz global, sin copiar
// dependencias dentro del repositorio.
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
const GRUPO = 'TC-M09-G142';

if (path.basename(BASE_DIR) !== 'automation' || path.basename(EVAL_DIR) !== 'EvaluacionV2'
    || path.basename(CASE_DIR) !== GRUPO) {
  throw new Error(`ABORTADO: ruta no autorizada para ${GRUPO}: ${BASE_DIR}`);
}

const BASE_URL = 'https://api.inmero.co/back-sigab-test';
if (!BASE_URL.endsWith('/back-sigab-test')) {
  throw new Error('ABORTADO: el ambiente decisorio de G142 es TEST');
}

const ADMIN = { correo: 'administador.dev@gmail.com', password: 'Test1234!' };
const ADMIN_ALT = { correo: 'admin.dev@gmail.com', password: 'Test1234!' };

const COLECCION = path.join(BASE_DIR, 'TC-M09-G142.postman_collection.json');
const COLECCION_PRECHECK = path.join(BASE_DIR, 'TC-M09-G142.precheck.postman_collection.json');

const PROHIBIDO_POST = /\/configuracion\/calibraciones-vision(\?|$)/;
//: BD de TEST en SOLO LECTURA, para la qualification de fixture. La contrasena llega
//: por G142_DB_PASSWORD y nunca se escribe en disco ni en los artefactos.
const DB = { host: '158.69.200.27', port: '5448', dbname: 'sgpmp_test', user: 'member_qa' };
const PRESUPUESTO = { alta: 1, cierre: 1, vision_manual: 0 };
//: Sello propio de CADA ejecucion. El sufijo del fixture NO puede derivarse del RUN_ID:
//: la politica es "mismo RUN, nueva ejecucion", asi que el nombre del area y el serial de
//: la camara chocarian con los de la ejecucion anterior (409 en el alta del area, que es
//: justo lo que tumbo el primer intento oficial de la ejecucion 2).
const SELLO = new Date().toISOString().replace(/[-:T]/g, '').slice(0, 14).replace(/^(\d{8})(\d{6})$/, '$1-$2');

const modo = (process.argv[2] || '').trim();
const RUN_ID = (process.argv[3] || '').trim();

// ── Guarda estática: la colección no puede contener el POST prohibido ───────
function guardaEstatica(ruta) {
  const col = JSON.parse(fs.readFileSync(ruta, 'utf8'));
  const plano = [];
  (function recorrer(items) {
    (items || []).forEach((it) => {
      if (it.item) return recorrer(it.item);
      plano.push(it);
    });
  })(col.item);
  plano.forEach((it) => {
    const metodo = ((it.request || {}).method || '').toUpperCase();
    const url = (((it.request || {}).url || {}).raw || '');
    if (metodo === 'POST' && PROHIBIDO_POST.test(url)) {
      throw new Error(
        `ABORTADO: la colección contiene un POST a calibraciones-vision en «${it.name}». `
        + 'G142 prohíbe disparar el cálculo VISION a mano.');
    }
  });
  return plano.length;
}

function entorno(extra) {
  const cualificado = FIXTURE_CUALIFICADO ? {
    especie_cualificada: FIXTURE_CUALIFICADO.id_especie,
    ciclo_productivo_cualificado: FIXTURE_CUALIFICADO.id_ciclo_productivo,
    fases_cualificadas: FIXTURE_CUALIFICADO.fases,
    densidad_cualificada: FIXTURE_CUALIFICADO.densidad_maxima_por_especie,
  } : {};
  const valores = Object.assign({
    base_url: BASE_URL,
    admin_correo: ADMIN.correo,
    admin_password: ADMIN.password,
  }, cualificado, extra || {});
  return { name: `${GRUPO}-${modo}`, values: Object.keys(valores).map((k) => ({ key: k, value: String(valores[k]), enabled: true })) };
}

function contadores() {
  return { alta: 0, cierre: 0, vision_manual: 0, fases: 0, vision_m03: 0, get: 0, patch: 0, total: 0 };
}

function clasificar(conteo, metodo, url) {
  conteo.total += 1;
  if (metodo === 'GET') { conteo.get += 1; return; }
  if (metodo === 'PATCH') { conteo.patch += 1; return; }
  if (metodo !== 'POST') return;
  if (PROHIBIDO_POST.test(url)) { conteo.vision_manual += 1; return; }
  if (/\/activos-biologicos\/\d+\/cierre/.test(url)) { conteo.cierre += 1; return; }
  if (/\/activos-biologicos\/\d+\/fases/.test(url)) { conteo.fases += 1; return; }
  if (/\/activos-biologicos(\?|$)/.test(url)) { conteo.alta += 1; return; }
  if (/\/iot\/telemetria\/vision/.test(url)) { conteo.vision_m03 += 1; }
}

function ejecutar(opciones, conteo) {
  return new Promise((resolve, reject) => {
    const corrida = newman.run(opciones, (err, resumen) => (err ? reject(err) : resolve(resumen)));
    corrida.on('beforeRequest', (err, args) => {
      if (err || !args || !args.request) return;
      const metodo = String(args.request.method || '').toUpperCase();
      const url = args.request.url ? args.request.url.toString() : '';
      if (metodo === 'POST' && PROHIBIDO_POST.test(url)) {
        throw new Error('ABORTADO: intento de POST manual a calibraciones-vision durante el RUN.');
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
    errores: (r.failures || []).length,
    detalle_fallos: (r.failures || []).map((f) => ({
      item: ((f.source || {}).name) || '(sin nombre)',
      assertion: (f.error || {}).test || '(sin assertion)',
      mensaje: String((f.error || {}).message || '').slice(0, 400),
    })),
  };
}

function valoresFinales(resumen) {
  const fuera = {};
  const env = ((resumen.environment || {}).values) || { each: () => {} };
  const lista = (env.members || env.values || []);
  (Array.isArray(lista) ? lista : []).forEach((v) => {
    if (!v || !v.key) return;
    if (/password|session|token|access_key|serial|cuerpo_/i.test(v.key)) return;
    fuera[v.key] = v.value;
  });
  return fuera;
}

// ── Qualification de fixture (§26 a §33) ───────────────────────────────────
// Por que vive aqui y no en la coleccion: el gate necesita saber, ANTES de crear el
// area y el lote, si la especie candidata tiene un ciclo productivo con al menos una
// fase. Ninguna API lista ciclos productivos por especie —solo por activo ya creado—,
// asi que la fuente autoritativa es el SELECT de solo lectura sobre modulo9. La
// ejecucion 1 descubrio esto a mitad del RUN, con el lote ya dado de alta; este gate
// lo detecta antes de escribir nada.
//
// La condicion real del disparo automatico es `es_poblacional(area.tipo_modelo_asignado)`
// y RF-20 exige `area.tipo_modelo_asignado == especie.tipo_modelo`, de modo que la
// especie necesita un tipo_modelo POBLACIONAL (AVES, PORCINOS o ACUICULTURA). Y el
// cierre de M02 exige fase activa, que exige un ciclo productivo DE ESA especie.
const MODELOS_POBLACIONAL = ['MODELO_AVES', 'MODELO_PORCINOS', 'MODELO_ACUICULTURA'];

function cualificarFixture() {
  const clave = process.env.G142_DB_PASSWORD || '';
  if (!clave) {
    return { verificable: false, motivo: 'falta G142_DB_PASSWORD en el proceso (no se persiste)' };
  }
  // El programa va a un archivo temporal fuera del repositorio: un `-c` multilinea no
  // sobrevive al shell de Windows. Se borra siempre, y la contrasena viaja por entorno,
  // nunca por argv ni por disco.
  const programa = [
    'import json, os, re',
    'import psycopg2, psycopg2.extras',
    '',
    'PRIVS = (',
    '    "SELECT "',
    '    " has_table_privilege(\'member_qa\',\'modulo9.ciclos_productivos\',\'SELECT\') AS cp,"',
    '    " has_table_privilege(\'member_qa\',\'modulo9.ciclos_biologicos\',\'SELECT\') AS cb,"',
    '    " has_table_privilege(\'member_qa\',\'modulo9.ciclos_productivos_biologicos\',\'SELECT\') AS cpb,"',
    '    " has_table_privilege(\'member_qa\',\'modulo9.especies\',\'SELECT\') AS esp"',
    ')',
    'CANDIDATAS = (',
    '    "SELECT e.id_especie, e.nombre, e.tipo_modelo, e.densidad_maxima_por_especie,"',
    '    "       cp.id_ciclo_productivo,"',
    '    "       COUNT(cpb.id_ciclos_productivo_biologico) AS fases"',
    '    "  FROM modulo9.especies e"',
    '    "  JOIN modulo9.ciclos_biologicos cb ON cb.id_especie = e.id_especie"',
    '    "  JOIN modulo9.ciclos_productivos cp"',
    '    "    ON cp.id_ciclo_biologico = cb.id_ciclo_biologico"',
    '    "  LEFT JOIN modulo9.ciclos_productivos_biologicos cpb"',
    '    "    ON cpb.id_ciclo_productivo = cp.id_ciclo_productivo"',
    '    " WHERE e.es_activo AND e.tipo_modelo = ANY(%(modelos)s)"',
    '    " GROUP BY e.id_especie, e.nombre, e.tipo_modelo,"',
    '    "          e.densidad_maxima_por_especie, cp.id_ciclo_productivo"',
    '    " HAVING COUNT(cpb.id_ciclos_productivo_biologico) > 0"',
    '    " ORDER BY e.id_especie, cp.id_ciclo_productivo"',
    ')',
    'POBLACIONALES = (',
    '    "SELECT id_especie, tipo_modelo, densidad_maxima_por_especie"',
    '    "  FROM modulo9.especies"',
    '    " WHERE es_activo AND tipo_modelo = ANY(%(modelos)s)"',
    '    " ORDER BY id_especie"',
    ')',
    'CICLOS = (',
    '    "SELECT cp.id_ciclo_productivo, cb.id_especie, e.tipo_modelo,"',
    '    "       e.densidad_maxima_por_especie"',
    '    "  FROM modulo9.ciclos_productivos cp"',
    '    "  JOIN modulo9.ciclos_biologicos cb"',
    '    "    ON cb.id_ciclo_biologico = cp.id_ciclo_biologico"',
    '    "  LEFT JOIN modulo9.especies e ON e.id_especie = cb.id_especie"',
    '    " ORDER BY cp.id_ciclo_productivo"',
    ')',
    'ESCRITURA = r"\\b(insert|update|delete|alter|drop|truncate|create|grant|revoke)\\b"',
    'for consulta in (PRIVS, CANDIDATAS, POBLACIONALES, CICLOS):',
    '    if re.search(ESCRITURA, consulta, re.I):',
    '        raise SystemExit("ABORTADO: la consulta no es de solo lectura")',
    '',
    'dsn = ("host=%s port=%s dbname=%s user=%s password=%s connect_timeout=25" % (',
    '    os.environ["H"], os.environ["P"], os.environ["D"],',
    '    os.environ["U"], os.environ["W"]))',
    'conexion = psycopg2.connect(dsn)',
    'conexion.autocommit = True',
    'conexion.set_session(readonly=True)',
    'cursor = conexion.cursor(cursor_factory=psycopg2.extras.RealDictCursor)',
    'modelos = json.loads(os.environ["M"])',
    'cursor.execute(PRIVS)',
    'privilegios = dict(cursor.fetchone())',
    'salida = {"privilegios": privilegios}',
    'if all(privilegios.values()):',
    '    cursor.execute(CANDIDATAS, {"modelos": modelos})',
    '    salida["candidatas"] = [dict(f) for f in cursor.fetchall()]',
    '    cursor.execute(POBLACIONALES, {"modelos": modelos})',
    '    salida["poblacionales"] = [dict(f) for f in cursor.fetchall()]',
    '    cursor.execute(CICLOS)',
    '    salida["ciclos_productivos"] = [dict(f) for f in cursor.fetchall()]',
    'cursor.close()',
    'conexion.close()',
    'print(json.dumps(salida, default=str, ensure_ascii=False))',
    '',
  ].join('\n');
  const archivo = path.join(os.tmpdir(), `g142-qualify-${process.pid}.py`);
  fs.writeFileSync(archivo, programa, { encoding: 'utf8' });
  let salida;
  try {
    salida = execSync(`python -I -X utf8 "${archivo}"`, {
      encoding: 'utf8',
      timeout: 180000,
      env: Object.assign({}, process.env, {
        H: DB.host, P: DB.port, D: DB.dbname, U: DB.user, W: clave,
        M: JSON.stringify(MODELOS_POBLACIONAL),
      }),
    });
  } catch (e) {
    const detalle = String((e.stderr || e.message || '')).trim().split('\n').pop();
    return { verificable: false, motivo: `no se pudo consultar la BD: ${detalle.slice(0, 220)}` };
  } finally {
    try { fs.unlinkSync(archivo); } catch (e) { /* el temporal ya no existe */ }
  }
  let datos;
  try {
    datos = JSON.parse(salida);
  } catch (e) {
    return { verificable: false, motivo: 'la consulta no devolvio JSON' };
  }
  const privs = datos.privilegios || {};
  const claves = Object.keys(privs);
  if (!claves.length || !claves.every((k) => privs[k] === true)) {
    return {
      verificable: false,
      privilegios: privs,
      motivo: 'member_qa no tiene SELECT sobre las tablas de ciclos; resolver por API (§31)',
    };
  }
  const candidatas = Array.isArray(datos.candidatas) ? datos.candidatas : [];
  // La especie tambien necesita densidad maxima configurada o el alta devuelve 422
  // DENSIDAD_MAXIMA_NO_CONFIGURADA.
  const aptas = candidatas.filter((c) => c.densidad_maxima_por_especie !== null
    && String(c.densidad_maxima_por_especie) !== '');
  return {
    verificable: true,
    privilegios: privs,
    poblacionales: (datos.poblacionales || []).length,
    ciclos_productivos_del_sistema: (datos.ciclos_productivos || []).length,
    con_ciclo_y_fase: candidatas,
    aptas,
    apto: aptas.length > 0,
    elegida: aptas.length ? aptas[0] : null,
    diagnostico: (datos.ciclos_productivos || []).map((c) => ({
      ciclo: c.id_ciclo_productivo,
      especie: c.id_especie,
      tipo_modelo: c.tipo_modelo,
      densidad: c.densidad_maxima_por_especie,
    })),
  };
}

//: Resultado de la compuerta. La coleccion NO vuelve a elegir especie por su cuenta:
//: usa la que el gate cualifico contra la BD. Asi la seleccion no depende de que el id
//: mas bajo resulte ser el bueno, y los ids no quedan incrustados en el arnes.
let FIXTURE_CUALIFICADO = null;

function compuertaDeFixture() {
  const q = cualificarFixture();
  FIXTURE_CUALIFICADO = (q && q.apto && q.elegida) ? q.elegida : null;
  console.log('\n──────── QUALIFICATION DE FIXTURE (§26 a §33)');
  if (!q.verificable) {
    console.log(`verificable     : NO — ${q.motivo}`);
    console.log('FIXTURE_G142_APTO: NO VERIFICABLE');
    console.log('AUTORIZAR_RUN: NO');
    return false;
  }
  console.log(`especies POBLACIONAL activas          : ${q.poblacionales}`);
  console.log(`ciclos productivos en el sistema      : ${q.ciclos_productivos_del_sistema}`);
  console.log(`POBLACIONAL con ciclo y >= 1 fase     : ${q.con_ciclo_y_fase.length}`);
  console.log(`  ... y con densidad configurada      : ${q.aptas.length}`);
  if (!q.apto) {
    q.diagnostico.forEach((d) => console.log(
      `  ciclo ${d.ciclo} -> especie ${d.especie} (tipo_modelo ${d.tipo_modelo})`));
    console.log('\nFIXTURE_G142_APTO: NO');
    console.log('TC289_PRECONDICION: NO MONTABLE');
    console.log('Causa: ninguna especie activa con tipo_modelo POBLACIONAL tiene un ciclo');
    console.log('       productivo con fases, y las que tienen ciclo productivo tienen');
    console.log('       tipo_modelo nulo, con lo que el area no puede ser POBLACIONAL (RF-20)');
    console.log('       y el disparo automatico no aplica.');
    console.log('Responsable probable: Implementacion / DBA (datos) — no hay API que cree');
    console.log('       filas en modulo9.ciclos_productivos.');
    console.log('AUTORIZAR_RUN: NO');
    return false;
  }
  console.log(`especie elegida : ${JSON.stringify(q.elegida)}`);
  console.log('FIXTURE_G142_APTO: SÍ');
  return true;
}

async function precheck() {
  const fixtureApto = compuertaDeFixture();
  // Modo diagnostico del arnes: con G142_SOLO_ARNES=1 la coleccion de solo lectura se
  // ejecuta aunque la compuerta de fixture no abra, para poder reportar la salud del
  // arnes (sintaxis, rutas, limites, campos) sin escribir nada. NUNCA autoriza el RUN.
  const soloArnes = /^(1|si|s[ií]|true)$/i.test(String(process.env.G142_SOLO_ARNES || ''));
  if (!fixtureApto && !soloArnes) {
    process.exitCode = 1;
    return;
  }
  if (!fixtureApto) {
    console.log('');
    console.log('MODO DIAGNOSTICO DEL ARNES (G142_SOLO_ARNES): la compuerta de fixture');
    console.log('sigue cerrada y AUTORIZAR_RUN seguira siendo NO. Solo se mide el arnes.');
  }
  const items = guardaEstatica(COLECCION_PRECHECK);
  guardaEstatica(COLECCION);
  console.log(`PRECHECK ${GRUPO} — colección de solo lectura (${items} items); sin HTML y sin artefactos.`);
  const conteo = contadores();
  let resumen;
  try {
    resumen = await ejecutar({
      collection: COLECCION_PRECHECK,
      environment: entorno(),
      reporters: ['cli'],
      insecure: false,
      timeoutRequest: 120000,
    }, conteo);
  } catch (e) {
    console.log(`\nPRECHECK: error de automatización — ${e.message}`);
    console.log('AUTORIZAR_RUN: NO');
    process.exitCode = 1;
    return;
  }
  const r = resumenDe(resumen);
  const escrituras = conteo.alta + conteo.cierre + conteo.vision_manual + conteo.fases + conteo.vision_m03 + conteo.patch;
  console.log('\n──────── PRECHECK');
  console.log(`requests        : ${r.requests}`);
  console.log(`assertions      : ${r.assertions}`);
  console.log(`failures        : ${r.failures}`);
  console.log(`escrituras      : ${escrituras} (debe ser 0)`);
  console.log(`valores         : ${JSON.stringify(valoresFinales(resumen))}`);
  r.detalle_fallos.forEach((f) => console.log(`  FALLO · ${f.item} · ${f.assertion} · ${f.mensaje}`));
  const arnesSano = r.failures === 0 && r.errores === 0 && escrituras === 0;
  console.log(`AUTOMATION_PRECHECK: ${arnesSano ? 'PASS' : 'FAIL'}`);
  const autorizar = arnesSano && fixtureApto;
  console.log(`\nAUTORIZAR_RUN: ${autorizar ? 'SÍ' : 'NO'}`);
  if (!autorizar) process.exitCode = 1;
}

async function run() {
  if (!/^run-\d{8}-\d{6}$/.test(RUN_ID)) {
    throw new Error('ABORTADO: falta el RUN_ID (formato run-YYYYMMDD-HHMMSS)');
  }
  // §32/§33: sin fixture apto no se escribe nada y no se tocan los artefactos vigentes.
  if (!compuertaDeFixture()) {
    throw new Error('ABORTADO: FIXTURE_G142_APTO = NO; no se inicia ningun POST funcional '
      + 'y no se sobrescriben los artefactos oficiales.');
  }
  const runDir = path.join(EVAL_DIR, 'RESULTADOS', RUN_ID);
  const newmanDir = path.join(runDir, 'newman');
  fs.mkdirSync(newmanDir, { recursive: true });
  const html = path.join(newmanDir, 'newman-TC-M09-G142.html');
  // La politica del grupo es "mismo RUN logico, varias ejecuciones": los artefactos
  // tecnicos representan la ejecucion oficial mas reciente y el historial vive en el
  // informe. Por eso el HTML existente no bloquea una reejecucion legitima, pero tampoco
  // se sobrescribe por accidente: hay que declararlo con G142_SOBRESCRIBIR_OFICIAL=1.
  // Antes esta guarda abortaba siempre y obligaba a borrar el HTML a mano, que es
  // precisamente la clase de paso manual que acaba perdiendo evidencia.
  const sobrescribir = /^(1|si|s[ií]|true)$/i.test(
    String(process.env.G142_SOBRESCRIBIR_OFICIAL || ''));
  if (fs.existsSync(html)) {
    if (!sobrescribir) {
      throw new Error(
        `ABORTADO: ya existe el HTML oficial de una ejecucion anterior en ${html}.
`
        + 'Si esta es una reejecucion autorizada del mismo RUN, repite con '
        + 'G142_SOBRESCRIBIR_OFICIAL=1; conserva antes una copia si necesitas el HTML '
        + 'anterior, porque el historial de resultados se guarda en el informe, no en el HTML.');
    }
    console.log(`AVISO: se sobrescribe el HTML oficial anterior (${path.basename(html)}) `
      + 'por reejecucion declarada con G142_SOBRESCRIBIR_OFICIAL.');
  }
  const items = guardaEstatica(COLECCION);
  console.log(`RUN OFICIAL ${GRUPO} — ${RUN_ID} (${items} items)`);

  const conteo = contadores();
  const resumen = await ejecutar({
    collection: COLECCION,
    environment: entorno({ run_id: RUN_ID, sufijo: SELLO }),
    reporters: ['cli', 'htmlextra'],
    reporter: {
      htmlextra: {
        export: html,
        title: `${GRUPO} — disparo automático M02 → M09 (VISION) — ${RUN_ID}`,
        browserTitle: `${GRUPO} ${RUN_ID}`,
        showEnvironmentData: false,
        skipSensitiveData: true,
        omitRequestBodies: false,
        omitHeaders: true,
      },
    },
    insecure: false,
    timeoutRequest: 180000,
    // Espaciado entre peticiones: da una ventana de observación real después de cada
    // evento M02 sin introducir ninguna escritura.
    delayRequest: 1500,
  }, conteo);

  const r = resumenDe(resumen);
  const valores = valoresFinales(resumen);
  const evidencia = {
    run_id: RUN_ID,
    grupo: GRUPO,
    ambiente: 'TEST',
    base_url: BASE_URL,
    generado: new Date().toISOString(),
    newman: {
      html: path.relative(runDir, html).replace(/\\/g, '/'),
      requests: r.requests,
      assertions: r.assertions,
      failures: r.failures,
      detalle_fallos: r.detalle_fallos,
    },
    presupuesto: {
      alta_m02: conteo.alta,
      cierre_m02: conteo.cierre,
      post_manual_calibraciones_vision: conteo.vision_manual,
      fases_setup: conteo.fases,
      lotes_m03_setup: conteo.vision_m03,
      get: conteo.get,
      patch_restauracion: conteo.patch,
      reintentos: 0,
    },
    valores_finales: valores,
  };
  fs.writeFileSync(path.join(runDir, 'newman-resumen.json'),
                   JSON.stringify(evidencia, null, 2), 'utf8');

  console.log('\n──────── RUN OFICIAL');
  console.log(`requests        : ${r.requests}`);
  console.log(`assertions      : ${r.assertions}`);
  console.log(`failures        : ${r.failures}`);
  console.log(`alta M02        : ${conteo.alta} (presupuesto ${PRESUPUESTO.alta})`);
  console.log(`cierre M02      : ${conteo.cierre} (presupuesto ${PRESUPUESTO.cierre})`);
  console.log(`POST VISION man.: ${conteo.vision_manual} (presupuesto ${PRESUPUESTO.vision_manual})`);
  console.log(`HTML            : ${html}`);
  r.detalle_fallos.forEach((f) => console.log(`  FALLO · ${f.item} · ${f.assertion} · ${f.mensaje}`));

  if (conteo.vision_manual !== PRESUPUESTO.vision_manual) {
    throw new Error(`ABORTADO: se ejecutaron ${conteo.vision_manual} POST manuales a calibraciones-vision.`);
  }
  if (conteo.alta > PRESUPUESTO.alta || conteo.cierre > PRESUPUESTO.cierre) {
    throw new Error(`ABORTADO: presupuesto funcional excedido (alta ${conteo.alta}, cierre ${conteo.cierre}).`);
  }
  console.log('\nLos fallos funcionales, si los hay, son evidencia del caso: no se relajan las assertions.');
}

(async () => {
  if (modo === 'precheck') return precheck();
  if (modo === 'run') return run();
  throw new Error('Uso: node run-g142-v2.cjs precheck | run <RUN_ID>');
})().catch((e) => {
  console.error(e.message);
  process.exitCode = 1;
});
