// Invocación segura de Cypress para el grupo (copia idéntica en TC-M03-G87 y TC-M03-G88).
//
// - El proyecto es la carpeta del grupo y la configuración es su archivo propio (cypress.gXX.config.cjs),
//   que no contiene ningún destino: el cypress.config.cjs raíz (baseUrl https://api.inmero.co,
//   mochawesome, capturas) nunca se carga, ni al ejecutar ni al verificar.
// - `configFile: false` ya no es válido en Cypress 14 ("--config-file cannot be false").
// - Las anulaciones van dentro de `e2e` (en Cypress 14 el bloque e2e del archivo prevalece sobre las de
//   nivel superior). baseUrl es el FRONTEND de TEST; el API va aparte en env.API_BASE.
// - El proceso hijo no hereda ELECTRON_RUN_AS_NODE (la terminal de VS Code la define y Electron no arranca).
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';

const LOOPBACK = /^https?:\/\/(127\.0\.0\.1|localhost|\[::1\])(:\d+)?(\/|$)/i;
export const archivoConfiguracion = (dirGrupo, corto) => path.join(dirGrupo, `cypress.${corto.toLowerCase()}.config.cjs`);

/** Opciones completas de cypress.run para el grupo. */
export function opcionesCypress({ dirGrupo, spec, configFile, baseUrl, capturas, descargas, env, viewport = { ancho: 1366, alto: 900 } }) {
  return {
    project: dirGrupo,
    configFile: path.relative(dirGrupo, configFile).split(path.sep).join('/'),
    testingType: 'e2e', spec, browser: 'electron', headless: true, quiet: true, reporter: 'spec', env,
    config: {
      e2e: {
        baseUrl, specPattern: path.relative(dirGrupo, spec).split(path.sep).join('/'), supportFile: false, fixturesFolder: false,
        video: false, screenshotOnRunFailure: false, trashAssetsBeforeRuns: false, testIsolation: false, retries: 0, reporter: 'spec',
        defaultCommandTimeout: 15000, requestTimeout: 20000, responseTimeout: 30000, viewportWidth: viewport.ancho, viewportHeight: viewport.alto,
        ...(capturas ? { screenshotsFolder: capturas } : {}), ...(descargas ? { downloadsFolder: descargas } : {}),
      },
    },
  };
}
/** Retira ELECTRON_RUN_AS_NODE del proceso antes de lanzar Cypress. */
export function prepararEntorno() { delete process.env.ELECTRON_RUN_AS_NODE; }
/** Frontend y API: ambos HTTPS y distintos (el frontend es el baseUrl de Cypress). */
export function destinosDiferenciados(front, api) {
  const n = u => String(u || '').trim().replace(/\/+$/, '').toLowerCase();
  return /^https:\/\//i.test(front || '') && /^https:\/\//i.test(api || '') && n(front) !== n(api);
}
/** Cadenas con forma de URL (recorrido profundo). */
export function urls(x, out = []) {
  if (typeof x === 'string') { if (/^[a-z]+:\/\//i.test(x)) out.push(x); }
  else if (x && typeof x === 'object') for (const v of Object.values(x)) urls(v, out);
  return out;
}
/**
 * Antes de lanzar Cypress en local: ningún origen de configuración que cargue el proceso deja un destino
 * no loopback (archivo del grupo, anulaciones, entorno del spec, cypress.env.json del proyecto, variables
 * CYPRESS_*), no se usa el cypress.config.cjs raíz y la salida a la red está bloqueada por un proxy de
 * loopback inexistente. Devuelve los motivos que impiden ejecutar (vacío = aislado).
 */
export function aislamientoVerificacion({ raiz, opciones, entorno }) {
  const motivos = [];
  const cfgPath = path.resolve(opciones.project, opciones.configFile || '');
  if (!opciones.configFile || cfgPath === path.join(raiz, 'cypress.config.cjs') || !fs.existsSync(cfgPath)) motivos.push('la configuración debe ser el archivo propio del grupo');
  else {
    const cfg = createRequire(cfgPath)(cfgPath);
    if (urls(cfg).length) motivos.push(`el archivo de configuración contiene destinos: ${urls(cfg).join(', ')}`);
  }
  const remotas = [...urls(opciones.config), ...urls(opciones.env)].filter(u => !LOOPBACK.test(u));
  if (remotas.length) motivos.push(`destinos no loopback en anulaciones o entorno: ${remotas.join(', ')}`);
  if (opciones.config?.e2e?.baseUrl !== null) motivos.push('baseUrl debe ser null en la verificación local');
  for (const dir of [opciones.project, raiz]) {
    const f = path.join(dir, 'cypress.env.json');
    if (fs.existsSync(f) && urls(JSON.parse(fs.readFileSync(f, 'utf8'))).some(u => !LOOPBACK.test(u))) motivos.push(`${f} contiene destinos remotos`);
  }
  const cyVars = Object.entries(entorno).filter(([k, v]) => /^CYPRESS_/i.test(k) && /:\/\//.test(String(v)) && !LOOPBACK.test(String(v)));
  if (cyVars.length) motivos.push(`variables ${cyVars.map(([k]) => k).join(', ')} con destinos remotos`);
  for (const k of ['HTTP_PROXY', 'HTTPS_PROXY']) if (!LOOPBACK.test(entorno[k] || '')) motivos.push(`${k} debe apuntar a un proxy de loopback inexistente`);
  if (entorno.ELECTRON_RUN_AS_NODE) motivos.push('ELECTRON_RUN_AS_NODE sigue definida');
  return motivos;
}
/**
 * Verificación local del descubrimiento del spec, sin red: misma configuración que la ejecución, con
 * baseUrl null, sin autorización (el before del spec se detiene en `bloqueo`) y la salida bloqueada.
 * Exige el spec descubierto, la barrera, ninguna prueba superada y ningún artefacto nuevo.
 */
export async function verificarDescubrimiento({ cypress, raiz, dirGrupo, spec, configFile, bloqueo }) {
  process.env.HTTP_PROXY = process.env.HTTPS_PROXY = 'http://127.0.0.1:9';
  process.env.NO_PROXY = 'localhost,127.0.0.1,::1';
  process.env.CYPRESS_CRASH_REPORTS = '0';
  prepararEntorno();
  const opciones = opcionesCypress({ dirGrupo, spec, configFile, baseUrl: null, env: {} });
  const motivos = aislamientoVerificacion({ raiz, opciones, entorno: process.env });
  if (motivos.length) { for (const m of motivos) console.log(`[FALLA] aislamiento: ${m}`); console.log('Cypress NO se ejecuta.'); return 1; }
  console.log('[OK]    aislamiento: configuración sin destinos, entorno sin URLs remotas y salida bloqueada por proxy inexistente');
  const antes = { raiz: new Set(fs.readdirSync(raiz)), grupo: new Set(fs.readdirSync(dirGrupo)) };
  const r = await cypress.run(opciones);
  const nuevos = [...fs.readdirSync(raiz).filter(x => !antes.raiz.has(x)), ...fs.readdirSync(dirGrupo).filter(x => !antes.grupo.has(x))];
  const specs = (r?.runs || []).map(x => path.resolve(dirGrupo, x.spec?.relative || ''));
  const tests = (r?.runs || []).flatMap(x => x.tests || []);
  const checks = [
    [`Cypress descubre ${path.basename(spec)}`, r?.status !== 'failed' && specs.length === 1 && specs[0] === spec, r?.status === 'failed' ? r.message : ''],
    [`La barrera del spec se detiene en ${bloqueo} sin pruebas superadas`, tests.some(t => t.state === 'failed' && String(t.displayError || '').includes(bloqueo)) && !tests.some(t => t.state === 'passed'), ''],
    ['Sin artefactos nuevos en la raíz ni en la carpeta del grupo', !nuevos.length, nuevos.join(', ')],
  ];
  for (const [n, ok, d] of checks) console.log(`${ok ? '[OK]   ' : '[FALLA]'} ${n}${!ok && d ? ` — ${d}` : ''}`);
  return checks.every(c => c[1]) ? 0 : 1;
}
