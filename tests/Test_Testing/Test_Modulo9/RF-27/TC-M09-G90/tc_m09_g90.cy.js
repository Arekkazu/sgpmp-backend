describe('TC-M09-G90 - Aplicación de temas Claro, Oscuro y Automático', () => {

  const email = 'admin@pecuaria.co';
  const password = 'Test1234!';

  beforeEach(() => {
    cy.visit('/login');

    cy.get('input[type="email"], input[name="correo_electronico"]')
      .first()
      .should('be.visible')
      .type(email);

    cy.get('input[type="password"], input[name="contrasena"]')
      .first()
      .should('be.visible')
      .type(password);

    cy.contains('button', /iniciar sesión|ingresar|login/i)
      .should('be.visible')
      .click();

    cy.url().should('not.include', '/login');
  });

  it('TC-M09-170, TC-M09-171 y TC-M09-172 - Aplicar temas Claro, Oscuro y Automático', () => {

    // ---------------------------------------------------------
    // 1. Diagnóstico inicial
    // ---------------------------------------------------------

    cy.screenshot('01-dashboard-inicial');

    cy.document().then((doc) => {
      const texto = doc.body.innerText;

      cy.writeFile(
        'tests/Test_Testing/Test_Modulo9/RF-27/TC-M09-G90/Resultados/G90-dashboard-inicial.txt',
        texto
      );

      cy.log('URL inicial: ' + doc.location.href);
    });

    // ---------------------------------------------------------
    // 2. Entrar a Configuración
    // ---------------------------------------------------------

    cy.contains('a, button, [role="button"]', /^Configuración$/i)
      .should('exist')
      .click({ force: true });

    cy.wait(1000);

    cy.screenshot('02-configuracion');

    // ---------------------------------------------------------
    // 3. Buscar la configuración de temas
    // ---------------------------------------------------------

    cy.get('body').then(($body) => {

      const texto = $body.text();

      cy.writeFile(
        'tests/Test_Testing/Test_Modulo9/RF-27/TC-M09-G90/Resultados/G90-configuracion.txt',
        texto
      );

      const tieneTema =
        /tema visual/i.test(texto) ||
        /temas visuales/i.test(texto) ||
        /\bClaro\b/i.test(texto) ||
        /\bOscuro\b/i.test(texto) ||
        /Automático/i.test(texto) ||
        /theme_mode/i.test(texto);

      if (!tieneTema) {

        cy.writeFile(
          'tests/Test_Testing/Test_Modulo9/RF-27/TC-M09-G90/Resultados/G90-diagnostico.txt',
          [
            'TC-M09-G90 BLOQUEADO',
            '',
            'No se encontró en la interfaz actual una opción identificable',
            'para configurar los temas Claro, Oscuro o Automático.',
            '',
            'Validaciones previstas:',
            'TC-M09-170 -> theme_mode=1 -> Claro',
            'TC-M09-171 -> theme_mode=2 -> Oscuro',
            'TC-M09-172 -> theme_mode=3 -> Automático',
            '',
            'URL: ' + window.location.href
          ].join('\n')
        );

        throw new Error(
          'TC-M09-G90 BLOQUEADO: la configuración de temas Claro/Oscuro/Automático no está disponible en la interfaz actual.'
        );
      }
    });

    // ---------------------------------------------------------
    // 4. Localizar controles de tema
    // ---------------------------------------------------------

    cy.contains(
      'label, button, [role="button"], option, span, div',
      /Tema visual|Temas visuales|Claro|Oscuro|Automático/i
    )
      .should('exist')
      .then(($element) => {

        cy.log(
          'Control de tema encontrado: ' +
          $element.first().text()
        );
      });

    // ---------------------------------------------------------
    // 5. Guardar información de controles encontrados
    // ---------------------------------------------------------

    cy.get('input, select, button, [role="button"]')
      .then(($elements) => {

        const elementos = [];

        $elements.each((index, element) => {
          elementos.push({
            tag: element.tagName,
            type: element.getAttribute('type'),
            name: element.getAttribute('name'),
            value: element.getAttribute('value'),
            text: element.innerText
          });
        });

        cy.writeFile(
          'tests/Test_Testing/Test_Modulo9/RF-27/TC-M09-G90/Resultados/G90-controles.json',
          elementos
        );
      });

    // ---------------------------------------------------------
    // IMPORTANTE
    // ---------------------------------------------------------
    //
    // Las siguientes tres validaciones NO se fuerzan todavía.
    //
    // Necesitamos conocer el selector real utilizado por el
    // frontend para cambiar theme_mode.
    //
    // Una vez identificado:
    //
    // 170 -> Claro
    // 171 -> Oscuro
    // 172 -> Automático
    //
    // se validará visualmente el cambio y su persistencia.
    // ---------------------------------------------------------

    cy.log('TC-M09-170: pendiente de selector real para theme_mode=1');
    cy.log('TC-M09-171: pendiente de selector real para theme_mode=2');
    cy.log('TC-M09-172: pendiente de selector real para theme_mode=3');

  });

});