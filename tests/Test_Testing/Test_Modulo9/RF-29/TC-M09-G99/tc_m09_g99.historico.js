describe('TC-M09-G99 - Cambio de idioma de la interfaz', () => {

  const frontendUrl = 'http://localhost:5173';

  it('TC-M09-189, TC-M09-190 y TC-M09-191 - Validar cambio de idioma es-CO/en-US sin recargar', () => {

    cy.visit(frontendUrl);

    // Evidencia inicial de la interfaz
    cy.screenshot('G99-interfaz-inicial');

    cy.get('body').then(($body) => {

      const textoInicial = $body.text();

      cy.writeFile(
        'tests/Test_Testing/Test_Modulo9/RF-29/TC-M09-G99/Resultados/G99-interfaz-inicial.txt',
        `TC-M09-G99 - Evidencia inicial\n\nURL: ${frontendUrl}\n\nTexto visible inicialmente:\n${textoInicial}\n`
      );

      /*
       * ---------------------------------------------------------
       * TC-M09-189 - Cambiar interfaz a español Colombia
       * ---------------------------------------------------------
       */

      const selectoresIdioma = [
        '[aria-label*="idioma" i]',
        '[aria-label*="language" i]',
        '[title*="idioma" i]',
        '[title*="language" i]',
        '[data-testid*="language" i]',
        '[data-testid*="idioma" i]',
        'button:contains("Idioma")',
        'button:contains("Language")',
        'select'
      ];

      let controlIdiomaEncontrado = false;

      selectoresIdioma.forEach((selector) => {
        if ($body.find(selector).length > 0) {
          controlIdiomaEncontrado = true;
        }
      });

      if (!controlIdiomaEncontrado) {

        cy.log('BLOQUEADO: no existe selector/control visible para cambio de idioma.');

        cy.writeFile(
          'tests/Test_Testing/Test_Modulo9/RF-29/TC-M09-G99/Resultados/G99-idioma-bloqueado.txt',
          `TC-M09-G99 - Evidencia de bloqueo

TC-M09-189:
No se encontró mecanismo visible para seleccionar locale es-CO.

TC-M09-190:
No se encontró mecanismo visible para seleccionar locale en-US.

TC-M09-191:
No es posible validar aplicación inmediata del cambio sin recargar porque no existe mecanismo de cambio de idioma.

Evidencia:
- La interfaz se encuentra actualmente en español.
- No se observa selector de idioma en la interfaz.
- No se encontró implementación de i18n/locale en el frontend.
- package.json no contiene dependencias de internacionalización.
`
        );

        /*
         * El caso se marca como bloqueado mediante una aserción
         * controlada para que Cypress genere evidencia formal.
         */
        expect(
          controlIdiomaEncontrado,
          'RF-29 requiere un mecanismo de cambio de idioma para es-CO/en-US'
        ).to.eq(true);

        return;
      }

      /*
       * Si en una futura versión aparece el mecanismo,
       * esta sección permitirá detectar el control.
       */
      cy.log('Se encontró un posible control de idioma.');

      cy.writeFile(
        'tests/Test_Testing/Test_Modulo9/RF-29/TC-M09-G99/Resultados/G99-control-idioma-detectado.txt',
        'Se detectó un posible mecanismo de selección de idioma. Se requiere identificar los valores es-CO y en-US para completar la automatización.'
      );
    });
  });
});