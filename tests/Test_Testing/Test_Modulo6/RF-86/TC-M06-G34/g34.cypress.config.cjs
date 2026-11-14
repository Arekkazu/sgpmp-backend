const fs = require('node:fs');
const path = require('node:path');

const dir = process.env.CYPRESS_ARTIFACTS_DIR;
module.exports = {
  fixturesFolder: false, video: false, screenshotOnRunFailure: false,
  trashAssetsBeforeRuns: false, reporter: 'spec',
  screenshotsFolder: dir ? path.join(dir, 'screenshots') : path.join(__dirname, 'cypress-no-ejecutar'),
  e2e: {
    specPattern: 'g34.cy.js', supportFile: false, testIsolation: true,
    setupNodeEvents(on) {
      on('after:run', results => {
        const dir = process.env.CYPRESS_ARTIFACTS_DIR;
        if (!dir) return;
        fs.mkdirSync(dir, { recursive: true });
        const resumen = {
          totalTests: results.totalTests,
          totalPassed: results.totalPassed,
          totalFailed: results.totalFailed,
          totalPending: results.totalPending,
          totalSkipped: results.totalSkipped,
          specs: results.runs?.length ?? null,
        };
        fs.writeFileSync(path.join(dir, 'G34-cypress.json'), JSON.stringify(resumen, null, 2));
      });
    },
  },
};
