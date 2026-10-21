// Configuración Cypress propia de TC-M03-G87 (proyecto = esta carpeta). No contiene destinos: el
// baseUrl (frontend de TEST) lo aporta el ejecutor por anulación en `e2e`, y en la verificación local
// es null. Sustituye a `configFile: false`, que Cypress 14 rechaza, y evita cargar el
// cypress.config.cjs raíz (baseUrl remoto del API, mochawesome, capturas).
// Las carpetas de respaldo quedan dentro del grupo; el ejecutor las anula con las del RUN.
module.exports = {
  e2e: {
    specPattern: 'tc_m03_g87.cy.js',
    supportFile: false,
    fixturesFolder: false,
    video: false,
    screenshotOnRunFailure: false,
    reporter: 'spec',
    screenshotsFolder: '_cypress_capturas',
    downloadsFolder: '_cypress_descargas',
  },
};
