describe('TC-M01-074 - Intentar exportar auditoría sin conexión', () => {

  const email = 'admin.dev@gmail.com';
  const password = 'Test1234!';

  const evidenceDir =
    'tests/Test_Testing/Test_Modulo1/RF-10/TC-M01-74/Resultados';

  beforeEach(() => {
    cy.visit('/login');

    // ============================================================
    // 1. Inicio de sesión
    // ============================================================

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

    cy.url({ timeout: 15000 })
      .should('include', '/dashboard');
  });

  it('Debe deshabilitar la exportación de auditoría cuando el navegador está offline', () => {

    // ============================================================
    // 2. Ingresar al módulo de Auditoría
    // ============================================================

    cy.contains(
      'a, button, [role="menuitem"]',
      /auditoría|auditoria/i,
      { timeout: 15000 }
    )
      .first()
      .should('exist')
      .click({ force: true });

    // Esperar carga del módulo
    cy.wait(1500);

    // ============================================================
    // 3. Buscar el botón Exportar
    // ============================================================

    cy.contains(
      'button, [role="button"]',
      /exportar/i,
      { timeout: 15000 }
    )
      .first()
      .should('exist')
      .as('botonExportar');

    // Registrar evidencia inicial
    cy.writeFile(
      `${evidenceDir}/estado_online.txt`,
      'TC-M01-074\n' +
      'Estado inicial: navegador en línea.\n' +
      'Se ingresó correctamente al módulo de Auditoría.\n' +
      'Se encontró el botón Exportar.'
    );

    // ============================================================
    // 4. Verificar estado inicial del botón
    // ============================================================

    cy.get('@botonExportar')
      .should('not.have.attr', 'aria-disabled', 'true')
      .and(($boton) => {
        expect(
          $boton.prop('disabled'),
          'El botón Exportar debe estar habilitado inicialmente'
        ).to.equal(false);
      });

    // ============================================================
    // 5. Simular estado offline
    // ============================================================

    cy.window().then((win) => {

      Object.defineProperty(win.navigator, 'onLine', {
        configurable: true,
        get: () => false
      });

      win.dispatchEvent(new Event('offline'));
    });

    // ============================================================
    // 6. Confirmar que navigator.onLine está en false
    // ============================================================

    cy.window()
      .its('navigator.onLine')
      .should('eq', false);

    cy.writeFile(
      `${evidenceDir}/estado_offline.txt`,
      'TC-M01-074\n' +
      'Estado simulado: navegador offline.\n' +
      'navigator.onLine = false.\n' +
      'Se disparó el evento offline.\n' +
      'No se utiliza cy.screenshot() durante el estado offline para evitar bloqueo del navegador.'
    );

    // ============================================================
    // 7. Verificar que Exportar queda deshabilitado
    // ============================================================

    cy.get('@botonExportar')
      .should(($boton) => {

        const disabledProperty = $boton.prop('disabled');
        const ariaDisabled = $boton.attr('aria-disabled');

        expect(
          disabledProperty === true ||
          ariaDisabled === 'true',
          'El botón Exportar debe estar deshabilitado cuando no hay conexión'
        ).to.equal(true);
      });

    // ============================================================
    // 8. Registrar resultado
    // ============================================================

    cy.writeFile(
      `${evidenceDir}/resultado_TC-M01-074.txt`,
      'TC-M01-074 - APROBADO\n\n' +
      '1. Inicio de sesión realizado correctamente con usuario administrador.\n' +
      '2. Se ingresó al módulo de Auditoría.\n' +
      '3. Se verificó la existencia del botón Exportar.\n' +
      '4. El botón Exportar estaba habilitado inicialmente.\n' +
      '5. Se simuló el estado offline mediante navigator.onLine = false.\n' +
      '6. Se disparó el evento offline.\n' +
      '7. Se verificó que el botón Exportar quedara deshabilitado.\n'
    );
  });

  // ==============================================================
  // 9. Restaurar estado online
  // ==============================================================

  afterEach(() => {

    cy.window({ log: false }).then((win) => {

      Object.defineProperty(win.navigator, 'onLine', {
        configurable: true,
        get: () => true
      });

      win.dispatchEvent(new Event('online'));
    });
  });

});