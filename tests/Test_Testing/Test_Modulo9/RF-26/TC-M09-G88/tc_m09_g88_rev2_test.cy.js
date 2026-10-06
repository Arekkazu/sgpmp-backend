/**
 * TC-M09-G88 rev2 TEST — RF-26 / TC-M09-168 aplicacion inmediata sin logout.
 * No modifica tc_m09_g88.cy.js ni rev1 DEV.
 * Password via Cypress.env('contrasena'). Restaura color original de Costa Azul si se muta.
 */
const TEST_FRONT = 'https://sigab-frontendtest-6aqrny-d2b730-158-69-200-27.sslip.io';
const COLOR_NUEVO = '#C41E3A';
const COLOR_ORIGINAL = '#007B8A';
const EVIDENCIA = 'tests/Test_Testing/Test_Modulo9/RF-26/TC-M09-G88/Resultados';

function hexToRgbCss(hex) {
  const h = hex.replace('#', '');
  const r = parseInt(h.slice(0, 2), 16);
  const g = parseInt(h.slice(2, 4), 16);
  const b = parseInt(h.slice(4, 6), 16);
  return { r, g, b };
}

function colorCerca(cssColor, hex) {
  const m = String(cssColor || '').match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/i);
  if (!m) return false;
  const tgt = hexToRgbCss(hex);
  const dr = Math.abs(Number(m[1]) - tgt.r);
  const dg = Math.abs(Number(m[2]) - tgt.g);
  const db = Math.abs(Number(m[3]) - tgt.b);
  return dr + dg + db < 80;
}

describe('TC-M09-G88 rev2 TEST - Aplicacion inmediata identidad visual', { testIsolation: false }, () => {
  it('TC-M09-168 - Verificar aplicacion inmediata sin cerrar sesion', function () {
    const correo = Cypress.env('correo') || 'admin@pecuaria.co';
    const contrasena = Cypress.env('contrasena');
    expect(contrasena, 'contrasena via Cypress.env (no hardcodear)').to.be.a('string').and.not.empty;

    let sidebarAntes = '';
    let fincaNombre = '';
    let colorOriginalLeido = COLOR_ORIGINAL;

    cy.intercept({ method: 'POST', url: /\/sesiones\/?$/ }).as('login');
    cy.intercept({ method: 'POST', url: /\/sesiones\/refresh\/?$/ }).as('refreshSesion');
    cy.intercept({ method: 'PATCH', url: /\/configuracion\/identidad-visual\// }).as('patchIv');

    cy.visit(`${TEST_FRONT}/login`);
    cy.get('input[type="email"], input[name="correo_electronico"]').first().should('be.visible').clear().type(correo);
    cy.get('input[type="password"]').first().should('be.visible').clear().type(contrasena, { log: false });
    cy.get('button[type="submit"]').contains(/ingresar|iniciar sesión|login/i).click();
    cy.wait('@login').then((intc) => {
      expect(intc.response && intc.response.statusCode, 'login HTTP').to.eq(200);
    });
    cy.url({ timeout: 20000 }).should('include', '/dashboard');
    cy.url().should('not.include', '/login');
    cy.contains(/Panel principal|Configuración/i, { timeout: 20000 }).should('exist');
    cy.screenshot('G88-rev2-01-dashboard');

    cy.get('.ds-sidebar__logo-text, [class*="sidebar"] [class*="logo"]').first().then(($el) => {
      sidebarAntes = ($el.text() || '').trim();
    });

    cy.contains('a, button, [role="button"]', /^Configuración$/i, { timeout: 15000 }).click({ force: true });
    cy.contains(/Configuración del Sistema|Personalización|Catálogo/i, { timeout: 20000 }).should('exist');
    cy.get('body').then(($body) => {
      if (/No se pudo restaurar tu sesión/i.test($body.text())) {
        cy.screenshot('G88-rev2-sesion-rota');
        throw new Error(
          'TC-M09-G88 ERROR DE AMBIENTE: el frontend TEST no pudo restaurar la sesion (refresh 401).'
        );
      }
    });
    cy.contains('button, [role="tab"], a, ion-segment-button, span', /^Personalización$/i).click({ force: true });
    cy.contains(
      'button',
      /Costa Azul|Finca Activa Prueba|El Remanso|Los Esteros|La Esperanza|El palmar/i,
      { timeout: 25000 }
    ).should('be.visible');
    cy.contains(/Identidad Visual/i, { timeout: 15000 }).should('exist');
    cy.screenshot('G88-rev2-02-identidad-visual');

    cy.get('body').then(($body) => {
      const texto = $body.text();
      cy.writeFile(`${EVIDENCIA}/G88-rev2-ui-personalizacion.txt`, texto.slice(0, 8000));
      if (/No hay fincas activas/i.test(texto)) {
        throw new Error(
          'TC-M09-G88 BLOQUEADO: Identidad Visual visible pero no hay fincas activas seleccionables para el usuario de prueba.'
        );
      }
      const bots = [...$body.find('button, ion-button, [role="button"]')];
      const farm =
        bots.find((el) => /Costa Azul/i.test(el.innerText || '')) ||
        bots.find((el) => {
          const t = (el.innerText || '').replace(/\s+/g, ' ').trim();
          return t.length > 3 && t.length < 80 && /Finca Activa Prueba|El Remanso|Los Esteros|La Esperanza|El palmar/i.test(t);
        });
      if (!farm) {
        throw new Error(
          'TC-M09-G88 BLOQUEADO: no hay boton de finca seleccionable en Identidad Visual.'
        );
      }
      fincaNombre = (farm.innerText || '').trim();
      cy.wrap(farm).click({ force: true });
    });

    cy.get('input[aria-label="Hex Color primario"]', { timeout: 15000 })
      .first()
      .should('be.visible')
      .invoke('val')
      .then((val) => {
        if (val && /^#[0-9A-Fa-f]{6}$/.test(String(val))) {
          colorOriginalLeido = String(val);
        }
      });
    cy.get('input[aria-label="Hex Color primario"]')
      .first()
      .clear({ force: true })
      .type(COLOR_NUEVO, { force: true });

    cy.contains('button', /Aplicar vista previa/i).click({ force: true });
    cy.contains(/Vista previa activa/i, { timeout: 10000 }).should('exist');
    cy.screenshot('G88-rev2-03-vista-previa');

    cy.contains('button', /Actualizar identidad/i).click({ force: true });
    cy.contains(/Identidad visual actualizada/i, { timeout: 20000 }).should('be.visible');
    cy.url().should('include', '/configuracion');
    cy.url().should('not.include', '/login');
    cy.get('input[aria-label="Hex Color primario"]').first().should('have.value', COLOR_NUEVO);
    cy.get('.ds-sidebar__logo-text, [class*="sidebar"] [class*="logo"]').first().should('contain.text', 'Costa Azul');

    cy.window().then((win) => {
      const logo = win.document.querySelector('.ds-sidebar__logo-text, [class*="sidebar"] [class*="logo"]');
      const sidebar = win.document.querySelector('.ds-sidebar, aside, nav');
      const bg = sidebar ? win.getComputedStyle(sidebar).backgroundColor : '';
      const logoText = logo ? (logo.textContent || '').trim() : '';
      cy.writeFile(`${EVIDENCIA}/G88-rev2-sidebar-tras-guardar.json`, {
        sidebarAntes,
        fincaNombre,
        logoText,
        sidebarBg: bg,
        colorEsperado: COLOR_NUEVO,
        bgCercaNuevo: colorCerca(bg, COLOR_NUEVO),
        url: win.location.href,
      });
      expect(/Costa Azul/i.test(logoText), 'sidebar muestra Costa Azul sin logout').to.eq(true);
      expect(bg, 'sidebar deja de ser el verde generico previo').to.not.eq('rgb(23, 64, 36)');
    });
    cy.screenshot('G88-rev2-04-sidebar-sin-logout');

    cy.get('input[aria-label="Hex Color primario"]')
      .first()
      .clear({ force: true })
      .type(colorOriginalLeido, { force: true });
    cy.contains('button', /Actualizar identidad/i).click({ force: true });
    cy.contains(/Identidad visual actualizada/i, { timeout: 20000 }).should('be.visible');
    cy.url().should('not.include', '/login');
    cy.get('input[aria-label="Hex Color primario"]').first().should('have.value', colorOriginalLeido);
    cy.screenshot('G88-rev2-05-restauracion');

    cy.window().then((win) => {
      const logo = win.document.querySelector('.ds-sidebar__logo-text, [class*="sidebar"] [class*="logo"]');
      const sidebar = win.document.querySelector('.ds-sidebar, aside, nav');
      const bg = sidebar ? win.getComputedStyle(sidebar).backgroundColor : '';
      const logoText = logo ? (logo.textContent || '').trim() : '';
      cy.writeFile(`${EVIDENCIA}/G88-rev2-sidebar-restaurado.json`, {
        sidebarBg: bg,
        logoText,
        colorOriginal: colorOriginalLeido,
        bgCercaOriginal: colorCerca(bg, colorOriginalLeido),
        url: win.location.href,
      });
      expect(/Costa Azul/i.test(logoText), 'marca Costa Azul permanece').to.eq(true);
      expect(bg, 'sidebar ya no queda en el rojo de prueba').to.not.eq('rgb(88, 14, 26)');
    });
  });
});
