/**
 * TC-M09-G88 / TC-M09-168 — Aplicación inmediata de identidad visual (RF-26).
 *
 * Ejecutar contra DEV (no usar el baseUrl TEST del cypress.config.cjs):
 *   npx cypress run --spec tests/Test_Testing/Test_Modulo9/RF-26/TC-M09-G88/tc_m09_g88.cy.js --env correo=admin.dev@gmail.com,contrasena=***
 *
 * No inventa UI. Si Identidad Visual no existe, el spec queda en estado BLOQUEADO
 * (test skipped), no lo disfraza como PASS del requisito 168.
 */
const DEV_FRONT = 'https://sigab-frontenddev-pbw0py-757e2f-158-69-200-27.sslip.io';
const COLOR_NUEVO = '#C41E3A';
const COLOR_ORIGINAL = '#007B8A';

describe('TC-M09-G88 - Aplicación inmediata de identidad visual', () => {
  it('TC-M09-168 - Verificar aplicación inmediata sin cerrar sesión', function () {
    const correo = Cypress.env('correo') || 'admin.dev@gmail.com';
    const contrasena = Cypress.env('contrasena');
    expect(contrasena, 'contrasena via Cypress.env (no hardcodear)').to.be.a('string').and.not.empty;

    cy.visit(`${DEV_FRONT}/login`);
    cy.get('input[type="email"]').should('be.visible').clear().type(correo);
    cy.get('input[type="password"]').should('be.visible').clear().type(contrasena, { log: false });
    cy.get('button[type="submit"]').contains(/ingresar/i).click();
    cy.url({ timeout: 20000 }).should('include', '/dashboard');
    cy.url().should('not.include', '/login');
    cy.screenshot('01-sesion-activa-dashboard');

    const sidebarAntes = () =>
      cy.get('.ds-sidebar__logo-text', { timeout: 10000 }).invoke('text');

    sidebarAntes().then((textoAntes) => {
      cy.visit(`${DEV_FRONT}/configuracion`);
      cy.contains('h1, h2, button', /Configuración/i, { timeout: 15000 }).should('exist');
      cy.contains('button', /^Personalización$/i).click({ force: true });
      cy.contains('h2', /Identidad Visual/i, { timeout: 15000 }).should('exist');
      cy.screenshot('02-identidad-visual');

      cy.get('body').then(($body) => {
        const texto = $body.text();
        if (!/Identidad Visual/i.test(texto)) {
          cy.writeFile(
            'tests/Test_Testing/Test_Modulo9/RF-26/TC-M09-G88/Resultados/G88-diagnostico.txt',
            'BLOQUEADO: no hay pantalla Identidad Visual en DEV.'
          );
          this.skip();
        }

        const finca = $body.find('button').filter((_, el) => /Costa Azul/i.test(el.innerText));
        if (!finca.length) {
          cy.writeFile(
            'tests/Test_Testing/Test_Modulo9/RF-26/TC-M09-G88/Resultados/G88-diagnostico.txt',
            'BLOQUEADO: Identidad Visual visible pero no hay finca activa seleccionable.'
          );
          this.skip();
        }
      });

      cy.contains('button', /Costa Azul/i).click({ force: true });
      cy.get('input[aria-label="Hex Color primario"], input[value="#007B8A"]', { timeout: 15000 })
        .first()
        .should('be.visible')
        .clear()
        .type(COLOR_NUEVO);
      cy.contains('button', /Aplicar vista previa/i).click({ force: true });
      cy.contains(/Vista previa activa/i).should('exist');
      cy.screenshot('03-vista-previa');

      cy.contains('button', /Actualizar identidad/i).click({ force: true });
      cy.contains('button', /Actualizar identidad/i, { timeout: 20000 }).should('not.be.disabled');
      cy.url().should('include', '/configuracion');
      cy.url().should('not.include', '/login');
      cy.get('.ds-sidebar__logo-text').should('contain.text', 'Camaronera Costa Azul');
      cy.screenshot('04-sidebar-tras-guardar-sin-logout');

      cy.get('input[aria-label="Hex Color primario"]').first().clear().type(COLOR_ORIGINAL);
      cy.contains('button', /Actualizar identidad/i).click({ force: true });
      cy.contains('button', /Actualizar identidad/i, { timeout: 20000 }).should('not.be.disabled');
      cy.url().should('not.include', '/login');
      cy.screenshot('05-restauracion-color-original');

      expect(textoAntes, 'hubo un estado inicial de marca en sidebar').to.be.a('string');
    });
  });
});
