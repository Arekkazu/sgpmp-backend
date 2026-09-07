const { defineConfig } = require('cypress');

module.exports = defineConfig({
  e2e: {
    baseUrl: 'http://sigab-frontendtest-6aqrny-d2b730-158-69-200-27.sslip.io',
    specPattern: 'tests/Test_Testing/**/*.cy.js',
    supportFile: 'cypress/support/e2e.js',

    reporter: 'mochawesome',
    reporterOptions: {
      reportDir:
        'tests/Test_Testing/Test_Modulo9/RF-27/TC-M09-G94/Resultados',
      overwrite: true,
      html: true,
      json: false,
      charts: true,
      reportPageTitle: 'TC-M09-G94 - RF-27'
    },

    screenshotsFolder:
      'tests/Test_Testing/Test_Modulo9/RF-27/TC-M09-G94/Resultados',

    video: false,
    screenshotOnRunFailure: true
  }
});