// Configuración Cypress propia de TC-M03-G88 (proyecto = esta carpeta). No contiene destinos: el
// baseUrl (frontend de TEST) lo aporta el ejecutor por anulación en `e2e`, y en la verificación local
// es null. Sustituye a `configFile: false`, que Cypress 14 rechaza, y evita cargar el
// cypress.config.cjs raíz (baseUrl remoto del API, mochawesome, capturas).
// Las carpetas de respaldo son temporales; el ejecutor usa cypress/ del RUN.
module.exports = {
  screenshotsFolder: require('node:path').join(require('node:os').tmpdir(), 'g88-cypress-capturas'),
  downloadsFolder: require('node:path').join(require('node:os').tmpdir(), 'g88-cypress-descargas'),
  screenshotOnRunFailure: false,
  fixturesFolder: false,
  video: false,
  reporter: 'spec',
  e2e: {
    specPattern: 'g88.cy.js',
    testIsolation: false,
    supportFile: false,
    setupNodeEvents(on, config) {
      const fs = require('node:fs');
      const path = require('node:path');
      on('task', {
        verificarCapturaG88(nombre) {
          const carpeta = config.screenshotsFolder;
          const recorrer = (dir) => fs.existsSync(dir) ? fs.readdirSync(dir, { withFileTypes: true })
            .flatMap((e) => e.isDirectory() ? recorrer(path.join(dir, e.name)) : [path.join(dir, e.name)]) : [];
          const archivo = recorrer(carpeta).find((x) => path.basename(x) === `${nombre}.png`);
          if (!archivo) return { ok: false, motivo: 'PNG ausente' };
          const cabecera = Buffer.alloc(24);
          const fd = fs.openSync(archivo, 'r');
          try { fs.readSync(fd, cabecera, 0, 24, 0); } finally { fs.closeSync(fd); }
          const png = cabecera.subarray(0, 8).equals(Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]));
          const ancho = png ? cabecera.readUInt32BE(16) : 0;
          const alto = png ? cabecera.readUInt32BE(20) : 0;
          return ancho >= config.viewportWidth && alto >= config.viewportHeight
            ? { ok: true, ancho, alto } : { ok: false, motivo: `PNG ${ancho}x${alto}; viewport ${config.viewportWidth}x${config.viewportHeight}` };
        },
        registrarRutasLocalesG88(rutas) {
          const archivo = config.env.LOCAL_RUTAS_ARCHIVO;
          if (archivo) fs.writeFileSync(archivo, JSON.stringify(rutas));
          return null;
        },
        guardarTokenRefrescoG88(token) {
          const archivo = config.env.TOKEN_REFRESH_FILE;
          if (archivo && typeof token === 'string' && token.length > 20)
            fs.writeFileSync(archivo, token, { mode: 0o600 });
          return null;
        },
      });
      on('before:browser:launch', (browser, launchOptions) => {
        if (browser.name === 'electron') launchOptions.preferences = {
          ...launchOptions.preferences, width: 1600, height: 1000,
        };
        else if (browser.family === 'chromium') launchOptions.args.push('--window-size=1600,1000');
        return launchOptions;
      });
    },
  },
};

