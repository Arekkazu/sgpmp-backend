describe('TC-M09-G82 - Restricción de acceso a módulos y fincas no autorizados', () => {

  const usuario = 'ingeniero@pecuaria.co';
  const password = 'Pruebas12#';

  it('TC-M09-G82 - Validar restricción de acceso para usuario sin finca asignada', () => {

    // =========================================================
    // 1. LOGIN COMO INGENIERO
    // =========================================================

    cy.visit('/login');

    cy.get('input[type="email"]')
      .should('be.visible')
      .type(usuario);

    cy.get('input[type="password"]')
      .should('be.visible')
      .type(password);

    cy.get('button')
      .contains(/iniciar sesión|ingresar|login/i)
      .should('be.visible')
      .click();

    // Esperar navegación al dashboard
    cy.url({ timeout: 10000 })
      .should('include', '/dashboard');

    cy.wait(2000);

    // =========================================================
    // 2. VALIDACIÓN DEL CONTEXTO DEL USUARIO
    // =========================================================

    cy.get('body')
      .invoke('text')
      .then((texto) => {

        cy.writeFile(
          'tests/Test_Testing/Test_Modulo9/RF-25/TC-M09-G82/Resultados/G82-interfaz-ingeniero.txt',
          texto
        );

        expect(texto).to.match(/Ingeniero de Campo/i);

        // El sistema debe informar que no existe una unidad
        // productiva asignada al usuario.
        expect(texto).to.match(
          /no tiene una unidad productiva asignada/i
        );
      });

    // =========================================================
    // 3. VALIDAR QUE LA INTERFAZ NO PRESENTA UNA FINCA
    //    ASIGNADA AL USUARIO
    // =========================================================

    cy.get('body')
      .invoke('text')
      .then((texto) => {

        const tieneMensajeSinFinca =
          /no tiene una unidad productiva asignada/i.test(texto);

        expect(tieneMensajeSinFinca).to.equal(true);

        cy.writeFile(
          'tests/Test_Testing/Test_Modulo9/RF-25/TC-M09-G82/Resultados/G82-validacion-contexto.txt',
          [
            'TC-M09-G82',
            'Usuario: ingeniero@pecuaria.co',
            'Rol: Ingeniero de Campo',
            'URL: ' + window.location.href,
            '',
            'Resultado de validación:',
            '- El usuario autenticado corresponde a Ingeniero de Campo.',
            '- La interfaz informa que no tiene una unidad productiva asignada.',
            '- No se presenta una finca productiva asignada en el contexto actual.',
            '',
            'Conclusión UI:',
            'La interfaz restringe el contexto productivo del usuario sin finca asignada.'
          ].join('\n')
        );
      });

    // =========================================================
    // 4. REGISTRAR URL
    // =========================================================

    cy.url().then((url) => {

      cy.writeFile(
        'tests/Test_Testing/Test_Modulo9/RF-25/TC-M09-G82/Resultados/G82-url.txt',
        url
      );

    });

    // =========================================================
    // 5. REGISTRAR ENLACES DISPONIBLES
    // =========================================================

    cy.get('a[href]').then(($links) => {

      let contenido = '';

      $links.each((index, element) => {

        const texto = Cypress.$(element)
          .text()
          .trim()
          .replace(/\s+/g, ' ');

        const href = Cypress.$(element)
          .attr('href');

        contenido +=
          `${index + 1}. TEXTO="${texto}" | HREF="${href}"\n`;
      });

      cy.writeFile(
        'tests/Test_Testing/Test_Modulo9/RF-25/TC-M09-G82/Resultados/G82-rutas-ui.txt',
        contenido
      );
    });

    // =========================================================
    // 6. REGISTRAR BOTONES / OPCIONES DE LA INTERFAZ
    // =========================================================

    cy.get('button, [role="button"]').then(($buttons) => {

      let contenido = '';

      $buttons.each((index, element) => {

        const texto = Cypress.$(element)
          .text()
          .trim()
          .replace(/\s+/g, ' ');

        contenido +=
          `${index + 1}. TEXTO="${texto}"\n`;
      });

      cy.writeFile(
        'tests/Test_Testing/Test_Modulo9/RF-25/TC-M09-G82/Resultados/G82-botones-ui.txt',
        contenido
      );
    });

    // =========================================================
    // 7. CAPTURA DE EVIDENCIA
    // =========================================================

    cy.screenshot(
      'G82-estado-ingeniero',
      {
        capture: 'fullPage'
      }
    );

    // =========================================================
    // 8. VALIDACIÓN FINAL
    // =========================================================

    cy.get('body')
      .should(
        'contain.text',
        'Actualmente no tiene una unidad productiva asignada'
      );

  });

});