describe(
  'TC-M09-G85 - Registro exitoso de identidad visual con datos válidos',
  () => {

    const email = 'admin@pecuaria.co';
    const password = 'Test1234!';

    it('TC-M09-160 - Guardar identidad visual con datos válidos', () => {

      // ============================================================
      // 1. INICIAR SESIÓN
      // ============================================================

      cy.visit('/login');

      cy.get('input[type="email"]', { timeout: 10000 })
        .should('be.visible')
        .clear()
        .type(email);

      cy.get('input[type="password"]')
        .should('be.visible')
        .clear()
        .type(password);

      cy.contains(
        'button',
        /iniciar sesión|ingresar|login/i
      )
        .should('be.visible')
        .click();

      cy.url({ timeout: 15000 })
        .should('include', '/dashboard');

      // ============================================================
      // 2. INGRESAR A CONFIGURACIÓN
      // ============================================================

      cy.contains(
        'a, button, [role="button"]',
        /^Configuración$/i,
        { timeout: 10000 }
      )
        .should('exist')
        .click({ force: true });

      cy.wait(1000);

      cy.screenshot('G85-configuracion');

      // ============================================================
      // 3. BUSCAR IDENTIDAD VISUAL
      // ============================================================

      cy.get('body').then(($body) => {

        const texto = $body.text();

        cy.log('Contenido de Configuración:');
        cy.log(texto);

        const existeIdentidadVisual =
          /Identidad Visual/i.test(texto);

        if (!existeIdentidadVisual) {

          cy.writeFile(
            'tests/Test_Testing/Test_Modulo9/RF-26/TC-M09-G85/Resultados/G85-diagnostico.txt',
            `TC-M09-G85 - Diagnóstico

URL:
${window.location.href}

Resultado:
No se encontró la opción "Identidad Visual".

Contenido de la página:
${texto}
`
          );

          throw new Error(
            'TC-M09-G85 BLOQUEADO: la opción "Identidad Visual" no está disponible en Configuración.'
          );
        }
      });

      // ============================================================
      // 4. ENTRAR A IDENTIDAD VISUAL
      // ============================================================

      cy.contains(
        'a, button, [role="button"]',
        /Identidad Visual/i
      )
        .should('be.visible')
        .click({ force: true });

      cy.wait(500);

      cy.screenshot('G85-identidad-visual');

      // ============================================================
      // 5. VALIDAR CONFIGURACIÓN DE COLORES
      // ============================================================

      cy.get('body').should(($body) => {

        const texto = $body.text();

        expect(
          /color|primario|secundario/i.test(texto),
          'La pantalla debe permitir configurar la identidad visual'
        ).to.equal(true);
      });

      // ============================================================
      // 6. COLOR PRIMARIO
      // ============================================================

      cy.get('input').then(($inputs) => {

        const inputPrimario = [...$inputs].find((input) => {

          const atributos = `
            ${input.name}
            ${input.id}
            ${input.placeholder}
            ${input.getAttribute('aria-label') || ''}
          `.toLowerCase();

          return (
            atributos.includes('primario') ||
            atributos.includes('primary')
          );
        });

        if (!inputPrimario) {
          throw new Error(
            'No se encontró el campo de color primario de RF-26.'
          );
        }

        cy.wrap(inputPrimario)
          .clear()
          .type('#3A7BD5');
      });

      // ============================================================
      // 7. COLOR SECUNDARIO
      // ============================================================

      cy.get('input').then(($inputs) => {

        const inputSecundario = [...$inputs].find((input) => {

          const atributos = `
            ${input.name}
            ${input.id}
            ${input.placeholder}
            ${input.getAttribute('aria-label') || ''}
          `.toLowerCase();

          return (
            atributos.includes('secundario') ||
            atributos.includes('secondary')
          );
        });

        if (!inputSecundario) {
          throw new Error(
            'No se encontró el campo de color secundario de RF-26.'
          );
        }

        cy.wrap(inputSecundario)
          .clear()
          .type('#FFFFFF');
      });

      // ============================================================
      // 8. GUARDAR IDENTIDAD VISUAL
      // ============================================================

      cy.contains(
        'button',
        /guardar|guardar cambios|save/i
      )
        .should('be.visible')
        .click();

      // ============================================================
      // 9. VALIDAR CONFIRMACIÓN
      // ============================================================

      cy.contains(
        /guardado|guardada|guardados|guardadas|éxito|exitosamente|actualizado|correctamente/i,
        { timeout: 10000 }
      )
        .should('be.visible');

      cy.screenshot('G85-guardado-exitoso');

    });
  }
);