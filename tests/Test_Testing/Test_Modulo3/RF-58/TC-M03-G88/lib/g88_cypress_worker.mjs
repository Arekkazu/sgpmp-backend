// Proceso aislado: el padre conserva el control del timeout y del cierre del RUN.
import fs from 'node:fs';
import { createRequire } from 'node:module';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { sanearArtefacto } from './g88_seguridad.mjs';

const dir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
let entrada = '';
for await (const trozo of process.stdin) entrada += trozo;
const opciones = JSON.parse(entrada);
const salida = process.argv[2];
const carpeta = path.resolve(String(opciones.env?.ARTIFACTS_DIR ?? ''));
const carpetaValida = path.isAbsolute(String(opciones.env?.ARTIFACTS_DIR ?? ''))
  && /^RUN-G88-V\d+-\d{8}-\d{6}$/.test(path.basename(path.dirname(carpeta)))
  && path.basename(carpeta) === 'cypress'
  && (carpeta.startsWith(path.join(dir, 'Resultados') + path.sep)
    || carpeta.startsWith(path.join(dir, 'EvaluacionV2', 'Resultados') + path.sep));
const errorPublico = (valor) => String(valor ?? '').split('\n')
  .filter((linea, indice) => indice === 0 || /(?:GET|POST|PUT|PATCH|DELETE)\s|https?:\/\/|ECONNRESET|ETIMEDOUT|socket hang up|network error/i.test(linea))
  .filter((linea) => !/authorization|cookie|password|token|secret/i.test(linea))
  .map((linea) => linea.replace(/\?[^\s'"<>]*/g, '?[QUERY_OMITIDA]'))
  .join('\n').slice(0, 3000);
const escribir = (valor) => fs.writeFileSync(salida, sanearArtefacto(JSON.stringify(valor), [
  opciones.env?.SANDBOX_SECRET, opciones.env?.PROD_PASSWORD, opciones.env?.ADMIN_PASSWORD,
  opciones.env?.PROD_EMAIL, opciones.env?.ADMIN_EMAIL, opciones.env?.SENSOR_180_NOMBRE,
  opciones.env?.PROD_LOGIN?.token, opciones.env?.ADMIN_LOGIN?.token]));
try {
  if (!carpetaValida) throw new Error('Carpeta Cypress fuera del RUN de G88.');
  const cy = createRequire(path.join(dir, '..', '..', '..', '..', '..', 'package.json'))('cypress');
  const cypressVersion = cy.version ?? createRequire(path.join(dir, '..', '..', '..', '..', '..', 'package.json'))('cypress/package.json').version;
  const res = await cy.run({ project: dir, configFile: 'g88.cypress.config.cjs', spec: path.join(dir, 'g88.cy.js'),
    browser: 'chrome', headed: false, quiet: true, reporter: 'spec', ...opciones,
    config: { ...opciones.config, screenshotsFolder: carpeta, downloadsFolder: carpeta } });
  const prefijo = opciones.env?.CHECK_172 === 'SI' ? '[TC-M03-172]' : '[TC-M03-180]';
  const tests = (res.runs ?? []).flatMap((x) => x.tests ?? [])
    .filter((t) => (t.title?.at(-1) ?? '').startsWith(prefijo))
    .map((t) => ({ title: t.title, state: t.state, displayError: errorPublico(t.displayError) }));
  escribir({ status: res.status, totalTests: tests.length,
    totalFailed: tests.filter((t) => t.state === 'failed').length,
    browserName: res.browserName ?? 'chrome', browserVersion: res.browserVersion ?? null,
    cypressVersion, tests });
  process.exitCode = res.status === 'failed' || res.totalFailed ? 1 : 0;
} catch (e) {
  escribir({ status: 'failed', totalTests: 0, tests: [], message: e.message });
  process.exitCode = 1;
}

