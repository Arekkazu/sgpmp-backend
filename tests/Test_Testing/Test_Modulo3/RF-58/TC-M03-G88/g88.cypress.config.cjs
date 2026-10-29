// ConfiguraciÃ³n Cypress propia de TC-M03-G88 (proyecto = esta carpeta). No contiene destinos: el
// baseUrl (frontend de TEST) lo aporta el ejecutor por anulaciÃ³n en `e2e`, y en la verificaciÃ³n local
// es null. Sustituye a `configFile: false`, que Cypress 14 rechaza, y evita cargar el
// cypress.config.cjs raÃ­z (baseUrl remoto del API, mochawesome, capturas).
// Las carpetas de respaldo quedan dentro del grupo; el ejecutor las anula con las del RUN.
module.exports = {
  screenshotsFolder: '_cypress_capturas',
  downloadsFolder: '_cypress_descargas',
  screenshotOnRunFailure: false,
  fixturesFolder: false,
  video: false,
  reporter: 'spec',
  e2e: {
    specPattern: 'g88.cy.js',
    testIsolation: true,
    supportFile: false,
  },
};

