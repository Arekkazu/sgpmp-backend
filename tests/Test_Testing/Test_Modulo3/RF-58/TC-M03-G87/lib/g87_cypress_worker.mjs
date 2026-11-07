// Proceso aislado: el padre conserva el control del timeout y del cierre del RUN.
import fs from 'node:fs';
import { createRequire } from 'node:module';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { sanearArtefacto } from './g87_seguridad.mjs';

const dir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
let entrada = '';
for await (const trozo of process.stdin) entrada += trozo;
const opciones = JSON.parse(entrada);
const salida = process.argv[2];
const escribir = (valor) => fs.writeFileSync(salida, sanearArtefacto(JSON.stringify(valor), [
  opciones.env?.SANDBOX_SECRET, opciones.env?.PROD_PASSWORD, opciones.env?.ENG_PASSWORD,
  opciones.env?.PROD_EMAIL, opciones.env?.ENG_EMAIL,
  opciones.env?.PROD_LOGIN?.token, opciones.env?.ENG_LOGIN?.token]));
try {
  const cy = createRequire(path.join(dir, '..', '..', '..', '..', '..', 'package.json'))('cypress');
  const res = await cy.run({ project: dir, configFile: 'g87.cypress.config.cjs', spec: path.join(dir, 'g87.cy.js'),
    browser: 'chrome', headed: false, quiet: true, reporter: 'spec', ...opciones });
  escribir({ status: res.status, totalTests: res.totalTests ?? 0,
    totalFailed: res.totalFailed ?? 0, browserName: res.browserName ?? 'chrome', browserVersion: res.browserVersion ?? null,
    tests: (res.runs ?? []).flatMap((x) => x.tests ?? []).map((t) => ({ title: t.title, state: t.state,
      displayError: String(t.displayError ?? '').split('\n')[0] })) });
  process.exitCode = res.status === 'failed' || res.totalFailed ? 1 : 0;
} catch (e) {
  escribir({ status: 'failed', totalTests: 0, tests: [], message: e.message });
  process.exitCode = 1;
}
