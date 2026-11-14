// Ensayo aislado de G88: Vite y Cypress solo en 127.0.0.1; salida en temp.
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import net from 'node:net';
import http from 'node:http';
import { spawn, spawnSync } from 'node:child_process';
import { createRequire } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import vm from 'node:vm';

const grupo = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const repo = path.resolve(grupo, '..', '..', '..', '..', '..');
const frontend = path.resolve(repo, '..', 'SGPMP-FRONT-END-PWA');
const requireRepo = createRequire(path.join(repo, 'package.json'));
const fuente = path.join(grupo, 'pruebas', 'g88_ui_fixtures.json');
const runId = 'LOCAL-G88';
const exigir = (ok, mensaje) => { if (!ok) throw new Error(mensaje); };

function tokenLocal(rol) {
  const b64 = (x) => Buffer.from(JSON.stringify(x)).toString('base64url');
  const ahora = Math.floor(Date.now() / 1000);
  return `${b64({ alg: 'none', typ: 'JWT' })}.${b64({ sub: `local-${rol}`, jti: 'local-g88',
    rol: rol === 'prod' ? 4 : 1, exp: ahora + 3600, iat: ahora })}.local`;
}

function fixtures() {
  const f = JSON.parse(fs.readFileSync(fuente, 'utf8'));
  exigir(f.dashboard?.sensores?.length === 1 && f.dashboard.sensores[0].nombre_sensor === f.sensor_nombre
    && f.dashboard.sensores[0].ultimo_valor === 5 && f.dashboard.sensores[0].ultima_unidad === 'ppm'
    && f.dashboard.sensores[0].estado_semaforo === 'GRIS'
    && f.dashboard.sensores[0].etiqueta_estado === 'Sin umbral configurado',
  'Fixture UI-180 no representa el oráculo sintético requerido.');
  exigir(f.especies?.items?.[0]?.id_especie === f.especie_id
    && f.variables?.items?.[0]?.nombre === f.variable_nombre
    && f.umbrales?.items?.[0]?.id_especie === f.especie_id,
  'Fixtures de navegación M09 incompletas.');
  const construir = (rol) => ({
    dashboard: f.dashboard, especies: f.especies, variables: f.variables, umbrales: f.umbrales,
    login: { token: tokenLocal(rol), tipo: 'bearer', expira_en: 3600, message: 'Sesión local simulada' },
    perfil: { id_usuario: rol === 'prod' ? 9101 : 9102, nombre: 'Usuario', apellidos: 'Local',
      nombre_rol: rol === 'prod' ? 'Productor' : 'Administrador', estado_cuenta: 'Activo',
      fincas: [{ id_finca: 9003, nombre: 'Finca local G88' }] },
    permisos: { permisos: [
      { id_recurso: 33, id_accion: 2, nombre_recurso: 'Monitoreo' },
      { id_recurso: 17, id_accion: 2, nombre_recurso: 'Ciclos biologicos' },
      { id_recurso: 20, id_accion: 2, nombre_recurso: 'Umbrales ambientales' },
      { id_recurso: 20, id_accion: 3, nombre_recurso: 'Umbrales ambientales' },
      { id_recurso: 8, id_accion: 2, nombre_recurso: 'Especies' }
    ] },
    layout: { id_dashboard_layout: null, id_usuario: rol === 'prod' ? 9101 : 9102,
      grid: [], active_widget: [], fecha_actualizacion: null, version_perfil: null },
    contexto: { id_usuario: rol === 'prod' ? 9101 : 9102, nombre_completo: 'Usuario Local',
      id_rol: rol === 'prod' ? 4 : 1, nombre_rol: rol === 'prod' ? 'Productor' : 'Administrador',
      id_finca: 9003, finca_activa: 'Finca local G88', departamento: null,
      especies_configuradas: [], modulos_autorizados: ['telemetria', 'configuracion'],
      identidad_visual: null, accesibilidad: null },
  });
  return { datos: f, roles: { prod: construir('prod'), admin: construir('admin') } };
}

function instalacion() {
  exigir(fs.existsSync(path.join(frontend, 'node_modules', 'vite', 'dist', 'node', 'index.js'))
    && fs.existsSync(path.join(frontend, 'node_modules', '@vitejs', 'plugin-react', 'dist', 'index.js')),
  'Faltan Vite o React ya instalados en el frontend.');
  let cypress;
  try { cypress = requireRepo('cypress'); } catch { throw new Error('Falta Cypress ya instalado en sgpmp-backend.'); }
  const cache = process.env.CYPRESS_CACHE_FOLDER || path.join(process.env.LOCALAPPDATA || path.join(os.homedir(), 'AppData', 'Local'), 'Cypress', 'Cache');
  const binario = process.env.CYPRESS_RUN_BINARY;
  exigir(binario ? fs.existsSync(binario) : fs.existsSync(cache)
    && fs.readdirSync(cache, { withFileTypes: true }).some((x) => x.isDirectory()
      && fs.existsSync(path.join(cache, x.name, 'Cypress', 'Cypress.exe'))),
  'Falta el binario Cypress ya instalado.');
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
    if (hijo.exitCode !== null) throw new Error(`Vite terminó: ${hijo.exitCode}`);
    const listo = await new Promise((resolve) => {
      const r = http.get(url, { timeout: 1000 }, (res) => { res.resume(); resolve(res.statusCode === 200); });
      r.on('error', () => resolve(false));
      r.on('timeout', () => { r.destroy(); resolve(false); });
    });
    if (listo) return;
    await new Promise((resolve) => setTimeout(resolve, 400));
  }
  throw new Error('Vite no respondió en 90 s; ver vite.log en la carpeta temporal.');
}
function detener(hijo) {
  if (!hijo?.pid || hijo.exitCode !== null) return;
  if (process.platform === 'win32') spawnSync('taskkill', ['/T', '/F', '/PID', String(hijo.pid)], { windowsHide: true, timeout: 10000 });
  else hijo.kill('SIGTERM');
}

function comprobarCabeceras() {
  const spec = fs.readFileSync(path.join(grupo, 'g88.cy.js'), 'utf8');
  const declaraciones = spec.match(/^const leerCabecera = .*;$/gm) ?? [];
  exigir(declaraciones.length === 1, 'Falta la lectura única de cabeceras del spec.');
  const leerCabecera = vm.runInNewContext(`${declaraciones[0]}\nleerCabecera`, {});
  for (const clave of ['x-test-run-id', 'X-Test-Run-Id', 'x-TeSt-RuN-Id']) {
    exigir(leerCabecera({ [clave]: runId }, 'x-test-run-id') === runId,
      `La lectura de ${clave} depende de mayúsculas.`);
  }
  exigir(leerCabecera({}, 'x-test-run-id') === undefined
    && leerCabecera({ 'X-Test-Run-Id': 'OTRO' }, 'x-test-run-id') !== runId,
  'La lectura de cabeceras acepta ausencia o un RUN ajeno.');
  exigir((spec.match(/req\.headers\['x-test-run-id'\] = RUN_ID;/g) ?? []).length === 2,
    'LOCAL y TEST deben añadir la cabecera del RUN a la petición.');
}

async function main() {
  exigir(process.argv.length === 2 || (process.argv.length === 3 && process.argv[2] === '--comprobar'),
    'Uso: node pruebas/g88_ui_local.mjs [--comprobar]');
  const { datos, roles } = fixtures();
  const cypress = instalacion();
  if (process.argv.includes('--comprobar')) {
    comprobarCabeceras();
    console.log('OK G88 UI local: fixtures, cabeceras y dependencias instaladas; sin procesos ni red.');
    return;
  }
  const temporal = fs.mkdtempSync(path.join(os.tmpdir(), 'g88-ui-local-'));
  console.log(`Salida G88 UI local: ${temporal}`);
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
    const apiBase = `http://127.0.0.1:${puertoApi}`;
    const vite = pathToFileURL(path.join(frontend, 'node_modules', 'vite', 'dist', 'node', 'index.js')).href;
    const react = pathToFileURL(path.join(frontend, 'node_modules', '@vitejs', 'plugin-react', 'dist', 'index.js')).href;
    const codigo = `import { createServer } from ${JSON.stringify(vite)};
      import react from ${JSON.stringify(react)};
      const s = await createServer({ configFile: false, plugins: [react()], root: ${JSON.stringify(frontend)},
        envDir: ${JSON.stringify(temporal)}, cacheDir: ${JSON.stringify(path.join(temporal, 'vite-cache'))},
        server: { host: '127.0.0.1', port: ${puerto}, strictPort: true } });
      await s.listen();`;
    const log = fs.openSync(path.join(temporal, 'vite.log'), 'w');
    hijo = spawn(process.execPath, ['--input-type=module', '-e', codigo], {
      cwd: frontend, windowsHide: true, stdio: ['ignore', log, log],
      env: { ...Object.fromEntries(Object.entries(process.env).filter(([k]) => !k.startsWith('VITE_'))),
        VITE_API_BASE_URL: apiBase, VITE_BASE_PATH: '/', VITE_RECAPTCHA_SITE_KEY: '',
        VITE_AGROFUSION_LOGIN_URL: '', BROWSER: 'none' },
    });
    fs.closeSync(log);
    await esperarServidor(baseUrl, hijo);
    const resultados = [];
    for (const [rol, caso] of [['prod', '180'], ['admin', '172']]) {
      const carpeta = path.join(temporal, caso);
      const rutas = path.join(carpeta, 'rutas-sin-fixture.json');
      fs.mkdirSync(carpeta, { recursive: true });
      const res = await cypress.run({ project: grupo, configFile: 'g88.cypress.config.cjs', spec: path.join(grupo, 'g88.cy.js'),
        browser: 'electron', headed: false, quiet: true, reporter: 'spec',
        config: { baseUrl, pageLoadTimeout: 180000, viewportWidth: 1440, viewportHeight: 900,
          requestTimeout: 90000, responseTimeout: 90000, defaultCommandTimeout: 15000,
          screenshotsFolder: path.join(carpeta, 'capturas'), downloadsFolder: path.join(carpeta, 'descargas'),
          videosFolder: path.join(carpeta, 'videos') },
        env: { MODO_LOCAL: true, AUTORIZADO_RUN: 'LOCAL', API_BASE: apiBase, RUN_ID: runId,
          ARTIFACTS_DIR: carpeta, LOCAL_RUTAS_ARCHIVO: rutas, LOCAL_FIXTURES: roles,
          ID_INFRA: datos.area_id, SENSOR_180_NOMBRE: datos.sensor_nombre, VALOR_180: 5, UNIDAD_180: 'ppm',
          ID_ESPECIE: datos.especie_id, VARIABLE_NOMBRE: datos.variable_nombre,
          PROD_EMAIL: 'productor@local.invalid', PROD_PASSWORD: 'local',
          ADMIN_EMAIL: 'admin@local.invalid', ADMIN_PASSWORD: 'local',
          CHECK_180: caso === '180' ? 'SI' : 'NO', CHECK_172: caso === '172' ? 'SI' : 'NO' } });
      const pruebas = (res.runs || []).flatMap((r) => r.tests || [])
        .filter((t) => (t.title?.at(-1) || '').startsWith(`[TC-M03-${caso}]`))
        .map((t) => ({ titulo: t.title.join(' > '), estado: t.state,
          error: t.displayError ? String(t.displayError).split('\n')[0] : null }));
      resultados.push({ caso, total: pruebas.length, aprobadas: pruebas.filter((t) => t.estado === 'passed').length,
        fallidas: pruebas.filter((t) => t.estado === 'failed').length,
        omitidas: pruebas.filter((t) => !['passed', 'failed'].includes(t.estado)).length,
        rutas_sin_fixture: fs.existsSync(rutas) ? JSON.parse(fs.readFileSync(rutas, 'utf8')) : [], pruebas });
    }
    fs.writeFileSync(path.join(temporal, 'resultado-ui-local.json'), JSON.stringify(resultados, null, 2));
    for (const r of resultados) console.log(`UI-${r.caso}: ${r.aprobadas} aprobadas, ${r.fallidas} fallidas, ${r.omitidas} omitidas`);
    const [u180, u172] = resultados;
    const esperado = u180.total === 4 && u180.aprobadas === 4 && u180.fallidas === 0
      && u172.total === 1 && u172.fallidas === 1
      && /control de T o tolerancia/i.test(u172.pruebas[0]?.error || '')
      && resultados.every((r) => r.rutas_sin_fixture.length === 0);
    if (!esperado) { console.error('Ensayo G88 UI local fuera del patrón esperado; revisar resultado-ui-local.json y capturas.'); process.exitCode = 1; }
    else console.log('OK G88 UI local: 4 aprobadas, 1 fallida esperada por ausencia de T, 0 omitidas.');
  } finally {
    detener(hijo);
    process.removeListener('SIGINT', interrumpir);
    process.removeListener('SIGTERM', interrumpir);
  }
}
main().catch((e) => { console.error(`FALLÓ G88 UI local: ${e.message}`); process.exitCode = 1; });
