describe('TC-M01-074 - Intentar exportar auditoría sin conexión', () => {

  const email = Cypress.env('TEST_EMAIL') || 'admin@pecuaria.co';
  const password = Cypress.env('TEST_PASSWORD') || 'Test1234!';

  const evidenceDir =
    'tests/Test_Testing/Test_Modulo1/RF-10/TC-M01-74/Resultados';

  beforeEach(() => {

    // ============================================================
    // 1. Ingresar al frontend TEST
    // ============================================================

    cy.visit('/login');

    cy.get(
      'input[type="email"], input[name="correo"], input[name="correo_electronico"]',
      { timeout: 15000 }
    )
      .first()
      .should('be.visible')
      .clear()
      .type(email);

    cy.get(
      'input[type="password"], input[name="contrasena"], input[name="password"]',
      { timeout: 15000 }
    )
      .first()
      .should('be.visible')
      .clear()
      .type(password);

    cy.contains(
      'button',
      /iniciar sesión|iniciar sesion|ingresar|login/i,
      { timeout: 15000 }
    )
      .first()
      .should('be.visible')
      .click();

    // Esperar autenticación y llegada al sistema.
    cy.url({ timeout: 15000 }).should('include', '/dashboard');
  });


  it('Debe deshabilitar la exportación de auditoría cuando el navegador está offline', () => {

    // ============================================================
    // 2. Acceder a Auditoría
    // ============================================================

    cy.contains(
      'a, button, [role="menuitem"]',
      /auditoría|auditoria/i,
      { timeout: 15000 }
    )
      .first()
      .should('be.visible')
      .click();

    // Confirmar que estamos en la pantalla de auditoría.
    cy.contains(
      /auditoría|auditoria/i,
      { timeout: 15000 }
    )
      .should('be.visible');

    cy.wait(1000);


    // ============================================================
    // 3. Localizar botón de exportación
    // ============================================================

    cy.contains(
      'button, [role="button"]',
      /exportar/i,
      { timeout: 15000 }
    )
      .first()
      .should('be.visible')
      .as('botonExportar');


    // ============================================================
    // 4. Evidencia antes de desconectar
    // ============================================================

    cy.get('@botonExportar')
      .then(($boton) => {

        cy.writeFile(
          `${evidenceDir}/TC-M01-074-estado-online.txt`,
          [
            'TC-M01-074 - Estado inicial',
            'Red: ONLINE',
            `disabled: ${$boton.prop('disabled')}`,
            `aria-disabled: ${$boton.attr('aria-disabled') || 'no definido'}`
          ].join('\n')
        );
      });

    cy.screenshot(
      'TC-M01-074-01-exportacion-online',
      {
        capture: 'viewport'
      }
    );


    // ============================================================
    // 5. Simular pérdida de conexión
    // ============================================================

    cy.window().then((win) => {

      // Se reemplaza temporalmente navigator.onLine para
      // representar el estado offline en la interfaz.
      Object.defineProperty(win.navigator, 'onLine', {
        configurable: true,
        get: () => false
      });

      win.dispatchEvent(new Event('offline'));
    });


    // ============================================================
    // 6. Verificar que la aplicación detecta estado offline
    // ============================================================

    cy.window().its('navigator.onLine').should('eq', false);

    cy.writeFile(
      `${evidenceDir}/TC-M01-074-estado-offline.txt`,
      [
        'TC-M01-074 - Estado de red',
        'Red: OFFLINE',
        'navigator.onLine: false'
      ].join('\n')
    );


    // ============================================================
    // 7. Verificar botón de exportación
    // ============================================================

    cy.get('@botonExportar')
      .should(($boton) => {

        const disabledProperty = $boton.prop('disabled');
        const ariaDisabled = $boton.attr('aria-disabled');

        expect(
          disabledProperty === true ||
          ariaDisabled === 'true'
        ).to.equal(true);
      });


    // ============================================================
    // 8. Evidencia final
    // ============================================================

    cy.get('@botonExportar')
      .then(($boton) => {

        const disabledProperty = $boton.prop('disabled');
        const ariaDisabled = $boton.attr('aria-disabled');

        cy.writeFile(
          `${evidenceDir}/TC-M01-074-resultado.txt`,
          [
            'TC-M01-074 - Intentar exportar auditoría sin conexión',
            '',
            'Estado de red: OFFLINE',
            'navigator.onLine: false',
            `disabled: ${disabledProperty}`,
            `aria-disabled: ${ariaDisabled || 'no definido'}`,
            '',
            'RESULTADO: APROBADO',
            'La exportación se encuentra deshabilitada mientras no existe conexión.'
          ].join('\n')
        );
      });

    cy.screenshot(
      'TC-M01-074-02-exportacion-offline-deshabilitada',
      {
        capture: 'viewport'
      }
    );
  });


  afterEach(() => {

    // ============================================================
    // Restaurar navigator.onLine para no afectar otras pruebas.
    // ============================================================

    cy.window().then((win) => {

      Object.defineProperty(win.navigator, 'onLine', {
        configurable: true,
        get: () => true
      });

      win.dispatchEvent(new Event('online'));
    });
  });

});