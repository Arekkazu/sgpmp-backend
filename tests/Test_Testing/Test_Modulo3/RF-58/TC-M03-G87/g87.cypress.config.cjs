// Configuración Cypress de g87.mjs. Sin destinos: baseUrl (frontend TEST) y el resto llegan como
// anulaciones dentro de `e2e`. Nunca se carga el cypress.config.cjs raíz.
const fs = require('node:fs');

module.exports = {
  e2e: {
    specPattern: 'g87.cy.js',
    supportFile: false,
    fixturesFolder: false,
    video: false,
    screenshotOnRunFailure: false,
    testIsolation: true,
    setupNodeEvents(on, config) {
      on('task', {
        // Guarda el JWT de la sesión UI para que g87.mjs la cierre tras el rollback.
        registrarSesionG87({ rol, token }) {
          const archivo = config.env.SESIONES_UI;
          const sesiones = fs.existsSync(archivo) ? JSON.parse(fs.readFileSync(archivo, 'utf8')) : {};
          sesiones[rol] = token;
          fs.writeFileSync(archivo, JSON.stringify(sesiones), { mode: 0o600 });
          return true;
        },
      });
      return config;
    },
  },
};
