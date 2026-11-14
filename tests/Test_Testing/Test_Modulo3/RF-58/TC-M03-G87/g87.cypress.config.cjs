// Configuración Cypress de g87.mjs. Sin destinos: baseUrl (frontend TEST) y el resto llegan como
// anulaciones dentro de `e2e`. Nunca se carga el cypress.config.cjs raíz.
const fs = require('node:fs');
const path = require('node:path');

module.exports = {
  viewportWidth: 1440,
  viewportHeight: 900,
  e2e: {
    specPattern: 'g87.cy.js',
    supportFile: false,
    fixturesFolder: false,
    video: false,
    screenshotOnRunFailure: true,
    testIsolation: true,
    setupNodeEvents(on, config) {
      const capturasEscaladas = new Set();
      on('before:browser:launch', (browser, launchOptions) => {
        const ancho = Math.max(config.viewportWidth, 1600);
        const alto = Math.max(config.viewportHeight, 1000);
        if (browser.name === 'electron') {
          launchOptions.preferences.width = ancho;
          launchOptions.preferences.height = alto;
        } else if (browser.family === 'chromium') {
          launchOptions.args = launchOptions.args.filter((arg) => !arg.startsWith('--window-size='));
          launchOptions.args.push(`--window-size=${ancho},${alto}`);
        }
        return launchOptions;
      });
      on('after:screenshot', (detalle) => {
        const ruta = path.resolve(detalle.path);
        if (detalle.scaled) capturasEscaladas.add(ruta);
        else capturasEscaladas.delete(ruta);
      });
      on('task', {
        verificarCapturaG87(archivo) {
          if (!/^[A-Za-z0-9_-]+$/.test(archivo)) return { ok: false, motivo: 'nombre de captura inválido' };
          try {
            const ruta = path.join(config.screenshotsFolder, 'g87.cy.js', `${archivo}.png`);
            if (!fs.existsSync(ruta)) return { ok: false, motivo: 'archivo ausente' };
            if (capturasEscaladas.has(path.resolve(ruta))) return { ok: false, motivo: 'captura escalada por Cypress' };
            const datos = fs.readFileSync(ruta);
            const png = datos.length >= 24 && datos.subarray(0, 8).equals(Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]));
            if (!png) return { ok: false, motivo: 'PNG inválido' };
            const ancho = datos.readUInt32BE(16);
            const alto = datos.readUInt32BE(20);
            return ancho >= config.viewportWidth && alto >= config.viewportHeight && datos.length >= 200
              ? { ok: true, ancho, alto, bytes: datos.length }
              : { ok: false, motivo: `captura insuficiente: ${ancho}x${alto}, ${datos.length} bytes; viewport ${config.viewportWidth}x${config.viewportHeight}` };
          } catch { return { ok: false, motivo: 'no se pudo leer la captura' }; }
        },
        registrarRutasLocalesG87(rutas) {
          const archivo = config.env.LOCAL_RUTAS_ARCHIVO;
          if (!config.env.MODO_LOCAL || !archivo) return null;
          const anteriores = fs.existsSync(archivo) ? JSON.parse(fs.readFileSync(archivo, 'utf8')) : [];
          const validas = rutas.filter((ruta) => /^[A-Z]+ \/[^?#\s]*$/.test(ruta));
          fs.writeFileSync(archivo, JSON.stringify([...new Set([...anteriores, ...validas])], null, 2));
          return null;
        },
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
