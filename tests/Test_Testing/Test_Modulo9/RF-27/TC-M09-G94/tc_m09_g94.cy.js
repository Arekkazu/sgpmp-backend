describe('TC-M09-G94 - Contraste mínimo y variante automática', () => {
  const email = Cypress.env('TEST_EMAIL') || 'productor@pecuaria.co';
  const password = Cypress.env('TEST_PASSWORD') || 'Test1234!';

  const evidenceDir =
    'tests/Test_Testing/Test_Modulo9/RF-27/TC-M09-G94/Resultados';

  beforeEach(() => {
    cy.visit('/login');
  });

  it('Verifica contraste mínimo 4.5:1 y comprueba la aplicación de variante automática ante contraste insuficiente', () => {
    // ============================================================
    // Preparación: autenticación
    // ============================================================
    cy.get('input[type="email"]', { timeout: 15000 })
      .should('be.visible')
      .clear()
      .type(email);

    cy.get('input[type="password"]', { timeout: 15000 })
      .should('be.visible')
      .clear()
      .type(password);

    cy.get('button[type="submit"]', { timeout: 15000 })
      .should('be.visible')
      .click();

    cy.url({ timeout: 15000 }).should('include', '/dashboard');

    // ============================================================
    // TC-M09-178: contraste mínimo 4.5:1
    // ============================================================
    cy.injectAxe();

    cy.document().then((doc) => {
      const theme =
        doc.documentElement.getAttribute('data-theme') || 'sin-definir';

      cy.writeFile(
        `${evidenceDir}/G94-tema-inicial.txt`,
        `data-theme inicial: ${theme}\nURL: ${doc.location.href}\n`
      );
    });

    cy.checkA11y(
      null,
      {
        runOnly: ['color-contrast'],
        includedImpacts: ['critical', 'serious', 'moderate', 'minor']
      },
      (violations) => {
        const evidence = violations.length
          ? violations
              .map((violation) => {
                const nodes = violation.nodes
                  .map((node) => `  - ${node.html}`)
                  .join('\n');

                return [
                  `ID: ${violation.id}`,
                  `Impacto: ${violation.impact}`,
                  `Descripción: ${violation.description}`,
                  `Ayuda: ${violation.help}`,
                  'Nodos afectados:',
                  nodes
                ].join('\n');
              })
              .join('\n\n')
          : 'No se detectaron violaciones de contraste mediante axe.';

        cy.writeFile(
          `${evidenceDir}/G94-178-contraste.txt`,
          [
            'TC-M09-G94 - Validación TC-M09-178',
            'Criterio: contraste mínimo WCAG 2.1 AA = 4.5:1',
            '',
            evidence
          ].join('\n')
        );

        if (violations.length > 0) {
          throw new Error(
            `TC-M09-G94 / TC-M09-178: se detectaron ${violations.length} violaciones de contraste. Revisar G94-178-contraste.txt`
          );
        }
      }
    );

    // ============================================================
    // TC-M09-179: variante automática ante contraste insuficiente
    //
    // No se fuerza artificialmente un color de bajo contraste:
    // eso probaría axe, pero no la funcionalidad de la aplicación.
    // ============================================================
    cy.document().then((doc) => {
      const html = doc.documentElement;

      const initialTheme =
        html.getAttribute('data-theme') || 'sin-definir';

      const initialClass = html.className || '';

      const possibleVariantAttributes = [
        'data-theme-variant',
        'data-contrast',
        'data-accessibility-theme',
        'data-color-variant'
      ];

      const initialVariantAttribute =
        possibleVariantAttributes
          .map((attribute) => ({
            attribute,
            value: html.getAttribute(attribute)
          }))
          .find((item) => item.value !== null) || null;

      cy.writeFile(
        `${evidenceDir}/G94-179-variante-inicial.txt`,
        [
          'TC-M09-G94 - Validación TC-M09-179',
          `data-theme: ${initialTheme}`,
          `class HTML: ${initialClass}`,
          `atributo de variante detectado: ${
            initialVariantAttribute
              ? `${initialVariantAttribute.attribute}=${initialVariantAttribute.value}`
              : 'ninguno'
          }`,
          '',
          'No se fuerza artificialmente una combinación de colores de bajo contraste.',
          'La variante automática solo puede considerarse implementada si la aplicación',
          'dispone de una lógica real que cambie la variante ante contraste insuficiente.'
        ].join('\n')
      );

      if (!initialVariantAttribute) {
        cy.writeFile(
          `${evidenceDir}/G94-179-variante.txt`,
          [
            'RESULTADO: BLOQUEADO / NO IMPLEMENTADO',
            '',
            'La interfaz actual no expone un mecanismo identificable de variante automática',
            'por contraste insuficiente.',
            'Se observó únicamente el atributo data-theme para light/dark.',
            '',
            'No se inventa ni se simula la funcionalidad para hacer pasar el caso.',
            'Debe verificarse con Desarrollo la implementación exigida por RF-27.'
          ].join('\n')
        );

        throw new Error(
          'TC-M09-G94 / TC-M09-179: BLOQUEADO. No se identificó una variante automática de contraste en la interfaz actual.'
        );
      }
    });
  });
});