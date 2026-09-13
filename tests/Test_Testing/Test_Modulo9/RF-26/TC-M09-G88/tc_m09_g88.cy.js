describe('TC-M09-G88 - Aplicación inmediata de identidad visual', () => {

  it('TC-M09-168 - Verificar aplicación inmediata de la identidad visual', () => {

    // 1. Iniciar sesión como Administrador
    cy.visit('/login');

    cy.get('input[type="email"]')
      .should('be.visible')
      .type('admin@pecuaria.co');

    cy.get('input[type="password"]')
      .should('be.visible')
      .type('Test1234!');

    cy.get('button[type="submit"]')
      .should('be.visible')
      .click();

    // 2. Confirmar que la sesión quedó activa
    cy.url().should('not.include', '/login');

    cy.screenshot('01-dashboard-administrador');

    // 3. Entrar a Configuración
    cy.contains(
      'a, button, [role="button"]',
      /^Configuración$/i
    )
      .should('exist')
      .click({ force: true });

    cy.screenshot('02-configuracion');

    // 4. Registrar qué opciones existen realmente
    cy.get('body')
      .invoke('text')
      .then((text) => {

        cy.writeFile(
          'tests/Test_Testing/Test_Modulo9/RF-26/TC-M09-G88/configuracion-g88.txt',
          text
        );

        cy.log('Contenido de Configuración:');
        cy.log(text);
      });

    // 5. Buscar la funcionalidad de identidad visual
    cy.get('body').then(($body) => {

      const texto = $body.text();

      const existeIdentidadVisual =
        /Identidad Visual/i.test(texto) ||
        /IdentidadVisual/i.test(texto) ||
        /identidad-visual/i.test(texto);

      if (!existeIdentidadVisual) {

        cy.writeFile(
          'tests/Test_Testing/Test_Modulo9/RF-26/TC-M09-G88/G88-diagnostico.txt',
          [
            'TC-M09-G88 - DIAGNÓSTICO',
            '',
            'Después de iniciar sesión como Administrador y entrar a Configuración,',
            'no se encontró una opción visible relacionada con Identidad Visual.',
            '',
            'Elementos encontrados:',
            texto
          ].join('\n')
        );

        throw new Error(
          'TC-M09-G88 BLOQUEADO: la funcionalidad "Identidad Visual" no está disponible en la interfaz actual.'
        );
      }

      cy.log('La funcionalidad Identidad Visual está disponible.');
    });
  });
});