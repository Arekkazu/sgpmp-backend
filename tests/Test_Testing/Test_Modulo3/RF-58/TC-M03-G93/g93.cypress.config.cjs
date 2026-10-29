// Configuración propia de G93; el ejecutor anula las carpetas de artefactos dentro del RUN.
// En la prueba local, las anula dentro de os.tmpdir(). No hay destino remoto aquí.
module.exports = {
  fixturesFolder: false,
  video: false,
  screenshotOnRunFailure: false,
  trashAssetsBeforeRuns: false,
  reporter: 'spec',
  e2e: {
    specPattern: '**/*.cy.js',
    supportFile: false,
    testIsolation: true,
    setupNodeEvents(on, config) {
      const fs = require('node:fs');
      const os = require('node:os');
      const path = require('node:path');
      on('task', {
        guardarCookieRotada({ ruta, cookie }) {
          const destino = path.resolve(ruta || '');
          if (!destino.startsWith(path.resolve(os.tmpdir()) + path.sep)
            || path.basename(destino) !== 'refresh-cookie.txt'
            || typeof cookie !== 'string' || !/^[A-Za-z0-9._~-]+$/.test(cookie))
            throw new Error('Destino o formato de cookie temporal inválido');
          fs.writeFileSync(destino, cookie, { encoding: 'utf8', mode: 0o600 });
          return null;
        },
      });
      return config;
    },
  },
};
