const { defineConfig } = require('cypress');
const fs = require('fs');
const path = require('path');

const outDir = path.join(__dirname, 'Resultados', '178-rev4');
const axePath = require.resolve('axe-core/axe.min.js');

module.exports = defineConfig({
  video: false,
  screenshotOnRunFailure: true,
  trashAssetsBeforeRuns: false,
  screenshotsFolder: path.join(outDir, 'screenshots-178-rev4-test'),
  viewportWidth: 1440,
  viewportHeight: 900,
  retries: 0,
  defaultCommandTimeout: 25000,
  requestTimeout: 25000,
  responseTimeout: 30000,
  chromeWebSecurity: false,
  reporter: 'mochawesome',
  reporterOptions: {
    reportDir: outDir,
    reportFilename: 'TC-M09-G94_178_rev4_test',
    overwrite: true,
    html: true,
    json: true,
    charts: true,
  },
  e2e: {
    baseUrl: 'https://sigab-frontendtest-6aqrny-d2b730-158-69-200-27.sslip.io',
    specPattern: path.join(__dirname, 'tc_m09_g94_178_rev4_test.cy.js'),
    supportFile: path.join(__dirname, '../../../../../cypress/support/e2e.js'),
    setupNodeEvents(on) {
      on('task', {
        getAxeSource() {
          return fs.readFileSync(axePath, 'utf8');
        },
      });
    },
  },
});
