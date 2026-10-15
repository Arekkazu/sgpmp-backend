const { defineConfig } = require('cypress');
const path = require('path');

module.exports = defineConfig({
  e2e: {
    baseUrl: 'https://api.inmero.co',
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