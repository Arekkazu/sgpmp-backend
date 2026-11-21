const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');

module.exports = {
  fixturesFolder: false, video: false, screenshotOnRunFailure: false,
  trashAssetsBeforeRuns: false, reporter: 'spec',
  e2e: {
    specPattern: 'g95.cy.js', supportFile: false, testIsolation: true,
    setupNodeEvents(on) {
      on('task', {
        async reemplazarSesion({ tokenAnterior, cookieAnterior }) {
          const base = process.env.CYPRESS_API_BASE_CONTROL;
          const local = process.env.CYPRESS_ENSAYO_LOCAL === 'SI';
          if (process.env.CYPRESS_AUTORIZADO_RUN !== 'SI'
            || (!local && base !== 'https://www.api.inmero.co/api-sgpmp-test')
            || (local && !/^http:\/\/127\.0\.0\.1:\d+\/api-sgpmp-test$/.test(base ?? ''))
            || !tokenAnterior || !cookieAnterior) throw Error('BLOQUEO_G95_REEMPLAZO');
          const res = await fetch(`${base}/sesiones/`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ correo_electronico: process.env.CYPRESS_PROD_EMAIL,
              contrasena: process.env.CYPRESS_PROD_PASSWORD }),
            signal: AbortSignal.timeout(30000),
          });
          if (res.status === 200) {
            const destino = path.resolve(process.env.CYPRESS_HANDOFF ?? '');
            if (!destino.startsWith(path.resolve(os.tmpdir()) + path.sep)
              || path.basename(destino) !== 'auth.json') throw Error('HANDOFF_FUERA_TEMP');
            fs.writeFileSync(destino, JSON.stringify({ token: tokenAnterior, cookie: cookieAnterior }));
          }
          return { http: res.status };
        },
      });
      on('after:run', results => {
        const dir = process.env.CYPRESS_ARTIFACTS_DIR;
        if (!dir) return;
        fs.mkdirSync(dir, { recursive: true });
        fs.writeFileSync(path.join(dir, 'UI-186-01-cypress.json'), JSON.stringify({
          totalTests: results.totalTests, totalPassed: results.totalPassed,
          totalFailed: results.totalFailed, totalPending: results.totalPending,
          totalSkipped: results.totalSkipped, specs: results.runs?.length ?? null,
        }, null, 2));
      });
    },
  },
};
