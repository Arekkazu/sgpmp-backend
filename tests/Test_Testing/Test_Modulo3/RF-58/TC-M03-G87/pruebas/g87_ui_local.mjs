// Ensayo local de la UI G87. No accede a TEST ni escribe en el repositorio.
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import net from 'node:net';
import http from 'node:http';
import { spawn, spawnSync } from 'node:child_process';
import { createRequire } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';

const grupo = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const repo = path.resolve(grupo, '..', '..', '..', '..', '..');
const frontend = path.resolve(repo, '..', 'SGPMP-FRONT-END-PWA');
const resultadosV2 = path.join(grupo, 'EvaluacionV2', 'Resultados');
const requireRepo = createRequire(path.join(repo, 'package.json'));
const runId = 'LOCAL-G87';

function exigir(condicion, mensaje) { if (!condicion) throw new Error(mensaje); }
function leerJson(archivo) { return JSON.parse(fs.readFileSync(archivo, 'utf8')); }
function fuenteOficial() {
  exigir(fs.existsSync(resultadosV2), `No existe el directorio de resultados G87 V2: ${resultadosV2}.`);
  const oficiales = fs.readdirSync(resultadosV2, { withFileTypes: true })
    .filter((x) => x.isDirectory() && /^RUN-G87-V2-\d{8}-\d{6}$/.test(x.name))
    .map((x) => {
      const intento = path.join(resultadosV2, x.name);
      const archivo = path.join(intento, 'resultado.json');
      return fs.existsSync(archivo) ? { intento, resultado: leerJson(archivo) } : null;
    })
    .filter((x) => x?.resultado.oficial === true && x.resultado.clasificacion === 'OFICIAL'
      && x.resultado.version === 2 && x.resultado.run_id === path.basename(x.intento))
    .sort((a, b) => a.resultado.run_id.localeCompare(b.resultado.run_id));
  exigir(oficiales.length > 0, `No existe un RUN oficial G87 V2 con resultado.json válido en ${resultadosV2}.`);
  return oficiales.at(-1);
}
function tokenFicticio(rol) {
  const b64 = (x) => Buffer.from(JSON.stringify(x)).toString('base64url');
  return `${b64({ alg: 'none', typ: 'JWT' })}.${b64({ sub: `local-${rol}`, jti: 'local', rol: rol === 'prod' ? 4 : 5,
    exp: Math.floor(Date.now() / 1000) + 3600, iat: Math.floor(Date.now() / 1000) })}.local`;
}

export function prepararFixtures() {
  const { intento, resultado } = fuenteOficial();
  const newman = leerJson(path.join(intento, 'newman', 'newman-TC-M03-G87.json'));
  exigir(resultado.grupo === 'TC-M03-G87' && resultado.datos?.s1?.id === 552
    && resultado.datos?.s2?.id === 77 && resultado.datos?.contrato_dashboard?.prod
    && resultado.datos?.contrato_dashboard?.eng,
  `El RUN oficial ${resultado.run_id} no contiene el contrato e IDs de G87.`);
  const extraer = (nombre) => {
    const e = newman.run?.executions?.find((x) => x.item?.name === nombre && x.response?.code === 200);
    exigir(e?.response?.stream, `Falta respuesta Newman: ${nombre}`);
    return JSON.parse(Buffer.from(e.response.stream.data ?? e.response.stream).toString('utf8'));
  };
  const construir = (rol, nombre) => {
    const dashboard = extraer(nombre);
    exigir(dashboard.total === 2 && dashboard.sensores?.length === 2 && dashboard.resumen_unidades?.length === 1,
      `Dashboard ${rol} incompleto.`);
    const esperado = resultado.datos.contrato_dashboard[rol];
    for (const [alias, id] of [['s1', 552], ['s2', 77]]) {
      const sensor = dashboard.sensores.find((s) => s.id_sensor === id);
      exigir(sensor, `Falta ${alias} en ${rol}.`);
      exigir(typeof sensor.nombre_sensor === 'string' && sensor.nombre_sensor.length > 0,
        `Falta nombre de ${alias} en ${rol}.`);
      exigir(esperado?.[alias], `Falta contrato de ${alias} en ${rol}.`);
      for (const [campo, valor] of Object.entries(esperado[alias]))
        exigir(sensor[campo] === valor, `${rol}/${alias}: ${campo} difiere del contrato del RUN oficial.`);
    }
    // Los campos de negocio permanecen idénticos; los nombres se sustituyen por alias locales.
    dashboard.resumen_unidades = dashboard.resumen_unidades.map((u) => ({ ...u,
      nombre_infraestructura: 'Área local G87', nombre_finca: 'Finca local G87' }));
    dashboard.sensores = dashboard.sensores.map((s) => ({ ...s,
      nombre_sensor: s.id_sensor === 552 ? 'Sensor local S1' : 'Sensor local S2',
      nombre_infraestructura: 'Área local G87', nombre_finca: 'Finca local G87' }));
    return {
      dashboard,
      login: { token: tokenFicticio(rol), tipo: 'bearer', expira_en: 3600, message: 'Sesión local simulada' },
      perfil: { id_usuario: rol === 'prod' ? 1001 : 1002, nombre: 'Usuario', apellidos: 'Local',
        nombre_rol: rol === 'prod' ? 'Productor' : 'Ingeniero de Campo', estado_cuenta: 'Activo',
        fincas: [{ id_finca: 184, nombre: 'Finca local G87' }] },
      permisos: { permisos: [{ id_recurso: 33, id_accion: 2, nombre_recurso: 'Monitoreo' }] },
      layout: { id_dashboard_layout: null, id_usuario: rol === 'prod' ? 1001 : 1002,
        grid: [], active_widget: [], fecha_actualizacion: null, version_perfil: null },
      contexto: { id_usuario: rol === 'prod' ? 1001 : 1002, nombre_completo: 'Usuario Local',
        id_rol: rol === 'prod' ? 4 : 5, nombre_rol: rol === 'prod' ? 'Productor' : 'Ingeniero de Campo',
        id_finca: 184, finca_activa: 'Finca local G87', departamento: null,
        especies_configuradas: [], modulos_autorizados: ['telemetria'],
        identidad_visual: null, accesibilidad: null },
    };
  };
  const fixtures = {
    prod: construir('prod', 'Dashboard del Productor'),
    eng: construir('eng', 'Dashboard del Ingeniero de Campo'),
  };
  const p1 = fixtures.prod.dashboard.sensores.find((s) => s.id_sensor === 552);
  const p2 = fixtures.prod.dashboard.sensores.find((s) => s.id_sensor === 77);
  const e2 = fixtures.eng.dashboard.sensores.find((s) => s.id_sensor === 77);
  exigir(p1.ultimo_valor === '25.0000' && p1.ultima_unidad === '°C' && p1.estado_semaforo === 'VERDE'
    && p1.indicador_anomalia === true && p1.estado_calidad === 'FUERA_DE_RANGO', 'S1 no coincide con el RUN oficial.');
  exigir(p2.etiqueta_estado === 'En revisión técnica' && p2.estado_calidad === null
    && p2.nivel_bateria_pct === null && p2.calidad_senal_rssi === null && p2.calidad_senal_snr === null,
  'S2 Productor expone datos técnicos o difiere del RUN oficial.');
  exigir(e2.etiqueta_estado === 'Requiere calibración' && e2.estado_calidad === 'ERROR_CALIBRACION',
    'S2 Ingeniero difiere del RUN oficial.');
  return fixtures;
}

function comprobarInstalacion() {
  exigir(fs.existsSync(path.join(frontend, 'node_modules')), 'Falta SGPMP-FRONT-END-PWA/node_modules; no se instala nada.');
  exigir(fs.existsSync(path.join(frontend, 'node_modules', 'vite', 'dist', 'node', 'index.js')),
    'Falta Vite ya instalado en el frontend; no se instala nada.');
  exigir(fs.existsSync(path.join(frontend, 'node_modules', '@vitejs', 'plugin-react', 'dist', 'index.js')),
    'Falta el plugin React ya instalado en el frontend; no se instala nada.');
  let cypress;
  try { cypress = requireRepo('cypress'); } catch { throw new Error('Falta el paquete Cypress en sgpmp-backend/node_modules; no se instala nada.'); }
  const cache = process.env.CYPRESS_CACHE_FOLDER || path.join(process.env.LOCALAPPDATA || path.join(os.homedir(), 'AppData', 'Local'), 'Cypress', 'Cache');
  const binario = process.env.CYPRESS_RUN_BINARY;
  const instalado = binario ? fs.existsSync(binario) : fs.existsSync(cache) && fs.readdirSync(cache, { withFileTypes: true })
    .filter((x) => x.isDirectory()).some((x) => fs.existsSync(path.join(cache, x.name, 'Cypress', 'Cypress.exe')));
  exigir(instalado, `Falta el binario Cypress ya instalado (caché: ${cache}); no se instala nada.`);
  return cypress;
}

async function puertoLibre() {
  const servidor = net.createServer();
  await new Promise((resolve, reject) => servidor.once('error', reject).listen(0, '127.0.0.1', resolve));
  const puerto = servidor.address().port;
  await new Promise((resolve) => servidor.close(resolve));
  return puerto;
}

async function esperarServidor(url, hijo) {
  const inicio = Date.now();
  let errorArranque;
  hijo.once('error', (e) => { errorArranque = e; });
  while (Date.now() - inicio < 90000) {
    if (errorArranque) throw new Error(`No se pudo iniciar Vite: ${errorArranque.message}`);
    if (hijo.exitCode !== null) throw new Error(`Vite terminó antes de servir localhost (código ${hijo.exitCode}).`);
    const listo = await new Promise((resolve) => {
      const r = http.get(url, { timeout: 1000 }, (res) => { res.resume(); resolve(res.statusCode === 200); });
      r.on('error', () => resolve(false));
      r.on('timeout', () => { r.destroy(); resolve(false); });
    });
    if (listo) return;
    await new Promise((resolve) => setTimeout(resolve, 400));
  }
  throw new Error('Vite no respondió en 90 s; revise vite.log en la carpeta temporal.');
}

async function pedirCompleto(url) {
  return new Promise((resolve, reject) => {
    const solicitud = http.get(url, { timeout: 120000 }, (res) => {
      const partes = [];
      res.on('data', (parte) => partes.push(parte));
      res.on('end', () => res.statusCode === 200
        ? resolve(Buffer.concat(partes).toString('utf8'))
        : reject(new Error(`Precalentamiento Vite: HTTP ${res.statusCode} en ${new URL(url).pathname}`)));
      res.on('error', reject);
    });
    solicitud.on('timeout', () => solicitud.destroy(new Error(`Precalentamiento Vite agotó 120 s en ${new URL(url).pathname}`)));
    solicitud.on('error', reject);
  });
}

async function calentarVite(baseUrl) {
  const html = await pedirCompleto(`${baseUrl}/`);
  await pedirCompleto(`${baseUrl}/telemetria/monitoreo`);
  const scripts = [...html.matchAll(/<script\b[^>]*\bsrc=["'](\/[^"']+)["']/g)].map((x) => x[1]);
  for (const ruta of new Set(['/@vite/client', ...scripts])) await pedirCompleto(new URL(ruta, baseUrl).href);
}

function detener(hijo) {
  if (!hijo?.pid || hijo.exitCode !== null) return;
  if (process.platform === 'win32') spawnSync('taskkill', ['/T', '/F', '/PID', String(hijo.pid)], { windowsHide: true, timeout: 10000 });
  else hijo.kill('SIGTERM');
}

async function main() {
  const fixtures = prepararFixtures();
  const cypress = comprobarInstalacion();
  if (process.argv.includes('--comprobar')) {
    console.log('OK G87 UI local: fixtures del RUN oficial V2 y dependencias instaladas comprobadas; sin procesos ni red.');
    return;
  }
  exigir(process.argv.length === 2, 'Uso: node pruebas/g87_ui_local.mjs [--comprobar]');
  const temporal = fs.mkdtempSync(path.join(os.tmpdir(), 'g87-ui-local-'));
  console.log(`Salida G87 UI local: ${temporal}`);
  process.env.CYPRESS_TELEMETRY_ENABLED = '0';
  process.env.CYPRESS_CRASH_REPORTS = '0';
  let hijo;
  const interrumpir = () => { detener(hijo); process.exit(130); };
  process.once('SIGINT', interrumpir);
  process.once('SIGTERM', interrumpir);
  try {
    const puerto = await puertoLibre();
    let puertoApi = await puertoLibre();
    while (puertoApi === puerto) puertoApi = await puertoLibre();
    const baseUrl = `http://127.0.0.1:${puerto}`;
    const apiBase = `http://127.0.0.1:${puertoApi}`; // libre y sin servidor; Cypress intercepta toda petición
    const vite = pathToFileURL(path.join(frontend, 'node_modules', 'vite', 'dist', 'node', 'index.js')).href;
    const react = pathToFileURL(path.join(frontend, 'node_modules', '@vitejs', 'plugin-react', 'dist', 'index.js')).href;
    const codigo = `import { createServer } from ${JSON.stringify(vite)};
      import react from ${JSON.stringify(react)};
      const s = await createServer({ configFile: false, plugins: [react()], root: ${JSON.stringify(frontend)},
        envDir: ${JSON.stringify(temporal)},
        cacheDir: ${JSON.stringify(path.join(temporal, 'vite-cache'))},
        server: { host: '127.0.0.1', port: ${puerto}, strictPort: true } });
      await s.listen();`;
    const log = fs.openSync(path.join(temporal, 'vite.log'), 'w');
    hijo = spawn(process.execPath, ['--input-type=module', '-e', codigo], {
      cwd: frontend, windowsHide: true, stdio: ['ignore', log, log],
      env: { ...process.env, VITE_API_BASE_URL: apiBase, VITE_BASE_PATH: '/', VITE_RECAPTCHA_SITE_KEY: '',
        VITE_AGROFUSION_LOGIN_URL: '', BROWSER: 'none' },
    });
    fs.closeSync(log);
    await esperarServidor(baseUrl, hijo);
    await calentarVite(baseUrl);
    const rutasArchivo = path.join(temporal, 'rutas-sin-fixture.json');
    const res = await cypress.run({ project: grupo, configFile: 'g87.cypress.config.cjs', spec: path.join(grupo, 'g87.cy.js'),
      browser: 'electron', headed: false, quiet: true, reporter: 'spec',
      config: { baseUrl, pageLoadTimeout: 180000, screenshotsFolder: path.join(temporal, 'capturas'),
        downloadsFolder: path.join(temporal, 'descargas'), videosFolder: path.join(temporal, 'videos') },
      env: { MODO_LOCAL: true, AUTORIZADO: 'LOCAL', API_BASE: apiBase, RUN_ID: runId,
        LOCAL_RUTAS_ARCHIVO: rutasArchivo, AREA_ID: 349,
        S1_NOMBRE: 'Sensor local S1', S2_NOMBRE: 'Sensor local S2', VALOR_25: 25, VALOR_FUERA: 31,
        VALORES_ERROR: [21.7, 22.3], UI_177: true, UI_178_PROD: true, UI_178_ENG: true,
        PROD_EMAIL: 'qa@local.invalid', ENG_EMAIL: 'qa@local.invalid',
        PROD_PASSWORD: 'local', ENG_PASSWORD: 'local', LOCAL_FIXTURES: fixtures },
    });
    const pruebas = (res.runs || []).flatMap((r) => r.tests || []).map((t) => ({ titulo: t.title.join(' > '), estado: t.state,
      error: t.displayError ? String(t.displayError).split('\n')[0] : null }));
    const aprobadas = pruebas.filter((p) => p.estado === 'passed');
    const fallidas = pruebas.filter((p) => p.estado === 'failed');
    const omitidas = pruebas.filter((p) => p.estado !== 'passed' && p.estado !== 'failed');
    const total = res.totalTests || pruebas.length;
    const rutasSinFixture = fs.existsSync(rutasArchivo) ? leerJson(rutasArchivo) : [];
    fs.writeFileSync(path.join(temporal, 'resultado-ui-local.json'), JSON.stringify({ total,
      aprobadas: aprobadas.length, fallidas: fallidas.length, omitidas: omitidas.length,
      rutas_sin_fixture: rutasSinFixture, pruebas }, null, 2));
    if (res.status === 'failed' || aprobadas.length !== total || rutasSinFixture.length) {
      console.error(`FALLÓ G87 UI local: ${aprobadas.length}/${total} comprobaciones UI`);
      for (const p of fallidas) console.error(`- Fallida: ${p.titulo}: ${p.error || p.estado}`);
      for (const p of omitidas) console.error(`- Omitida: ${p.titulo}: ${p.estado}`);
      for (const ruta of rutasSinFixture) console.error(`- Sin fixture: ${ruta}`);
      process.exitCode = 1;
    } else console.log(`OK G87 UI local: ${aprobadas.length}/${total} comprobaciones UI`);
  } finally {
    detener(hijo);
    process.removeListener('SIGINT', interrumpir);
    process.removeListener('SIGTERM', interrumpir);
  }
}

main().catch((e) => { console.error(`FALLÓ G87 UI local: ${e.message}`); process.exitCode = 1; });
