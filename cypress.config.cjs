const { defineConfig } = require('cypress');
const path = require('path');

module.exports = defineConfig({
  e2e: {
    baseUrl: 'http://sigab-frontendtest-6aqrny-d2b730-158-69-200-27.sslip.io',
    specPattern: 'tests/Test_Testing/**/*.cy.js',
    supportFile: 'cypress/support/e2e.js',

    reporter: 'mochawesome',

    reporterOptions: {
      overwrite: true,
      html: true,
      json: false,
      charts: true
    },

    video: false,
    screenshotOnRunFailure: true
  }
});