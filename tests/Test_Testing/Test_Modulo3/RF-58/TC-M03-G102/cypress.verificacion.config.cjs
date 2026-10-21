// Configuración propia del grupo: loopback por defecto; el ejecutor autorizado anula e2e con TEST.
// Sustituye al cypress.config.cjs raíz, cuyo baseUrl es remoto. Reproduce su estructura (valores
// dentro de `e2e`) con destinos de loopback y valores DISTINTOS de los que anula el ejecutor: si las
// anulaciones no prevalecieran, Cypress intentaría verificar http://127.0.0.1:9 (falla en local) o
// dejaría capturas en _verificacion_capturas/, y la verificación lo marcaría como FALLO.
module.exports = {
  e2e: {
    baseUrl: 'http://127.0.0.1:9',
    specPattern: 'tests/Test_Testing/Test_Modulo3/RF-58/TC-M03-G102/tc_m03_g102.cy.js',
    supportFile: false,
    fixturesFolder: false,
    reporter: 'dot',
    screenshotOnRunFailure: true,
    screenshotsFolder: 'tests/Test_Testing/Test_Modulo3/RF-58/TC-M03-G102/_verificacion_capturas',
    downloadsFolder: 'tests/Test_Testing/Test_Modulo3/RF-58/TC-M03-G102/_verificacion_descargas',
    video: false,
  },
};
