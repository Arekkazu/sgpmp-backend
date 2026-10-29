/**
 * TC-M09-G85 rev2 TEST — RF-26 / TC-M09-160 registro UI de identidad visual.
 * No modifica tc_m09_g85.cy.js ni evidencias historicas.
 * Password via --env contrasena (Cypress.env). Sin fallback hardcodeado.
 *
 * Si la UI muestra Identidad Visual pero "No hay fincas activas", el spec
 * falla con mensaje BLOQUEADO (no se disfraza como PASS).
 */
const TEST_FRONT = 'https://sigab-frontendtest-6aqrny-d2b730-158-69-200-27.sslip.io';
const TEST_API = 'https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test';
const EVIDENCIA = 'tests/Test_Testing/Test_Modulo9/RF-26/TC-M09-G85/Resultados';
const COLOR_PRI = '#2E6B4A';
const COLOR_SEC = '#E8F5E9';
const ORG = 'QA G85 rev2 TEST';

function pass() {
  const contrasena = Cypress.env('contrasena');
  expect(contrasena, 'contrasena via Cypress.env (no hardcodear)').to.be.a('string').and.not.empty;
  return contrasena;
}

function redactMe(body) {
  if (!body || typeof body !== 'object') return body;
  const copy = { ...body };
  delete copy.token;
  if (Array.isArray(copy.fincas)) {
    copy.n_fincas = copy.fincas.length;
  }
  return copy;
}

describe('TC-M09-G85 rev2 TEST - Registro identidad visual', { testIsolation: false }, () => {
  it('TC-M09-160 - Guardar identidad visual con datos validos en TEST', () => {
    const correo = Cypress.env('correo') || 'admin@pecuaria.co';
    const contrasena = pass();

    cy.intercept({ method: 'POST', url: /\/sesiones\/?$/ }).as('login');
    cy.intercept({ method: 'POST', url: /\/sesiones\/refresh\/?$/ }).as('refreshSesion');
    cy.intercept({ method: 'GET', url: /\/usuarios\/me\/?$/ }).as('me');
    cy.intercept({ method: 'GET', url: /\/fincas/ }).as('fincas');
    cy.intercept({ method: 'POST', url: /\/configuracion\/identidad-visual\/?$/ }).as('postIv');

    cy.visit(`${TEST_FRONT}/login`);
    cy.get('input[type="email"], input[name="correo_electronico"]').first().should('be.visible').clear().type(correo);
    cy.get('input[type="password"]').first().should('be.visible').clear().type(contrasena, { log: false });
    cy.get('button[type="submit"]').contains(/ingresar|iniciar sesión|login/i).click();
    cy.wait('@login').then((intc) => {
      expect(intc.response && intc.response.statusCode, 'login HTTP').to.eq(200);
    });
    cy.url({ timeout: 20000 }).should('include', '/dashboard');
    cy.contains(/Panel principal|Configuración/i, { timeout: 20000 }).should('exist');
    cy.screenshot('G85-rev2-01-dashboard');

    cy.contains('a, button, [role="button"]', /^Configuración$/i, { timeout: 15000 }).click({ force: true });
    cy.contains(/Configuración del Sistema|Personalización|Catálogo/i, { timeout: 20000 }).should('exist');
    cy.get('body').then(($body) => {
      if (/No se pudo restaurar tu sesión/i.test($body.text())) {
        cy.screenshot('G85-rev2-sesion-rota');
        throw new Error(
          'TC-M09-G85 ERROR DE AMBIENTE: el frontend TEST no pudo restaurar la sesion (refresh 401).'
        );
      }
    });
    cy.screenshot('G85-rev2-02-configuracion');

    cy.contains('button, [role="tab"], a, ion-segment-button, span', /^Personalización$/i, { timeout: 10000 })
      .should('be.visible')
      .click({ force: true });
    cy.contains(/Identidad Visual/i, { timeout: 15000 }).should('exist');
    cy.contains(
      'button',
      /Costa Azul|Finca Activa Prueba|El Remanso|Los Esteros|La Esperanza|El palmar/i,
      { timeout: 25000 }
    ).should('be.visible');
    cy.screenshot('G85-rev2-03-identidad-visual');

    cy.get('body').then(($body) => {
      const texto = $body.text();
      cy.writeFile(`${EVIDENCIA}/G85-rev2-ui-personalizacion.txt`, texto.slice(0, 8000));
      if (/No hay fincas activas/i.test(texto)) {
        throw new Error(
          'TC-M09-G85 BLOQUEADO: Identidad Visual visible pero no hay fincas activas en el picker del usuario de prueba.'
        );
      }
    });

    cy.get('button, ion-button, [role="button"]').then(($els) => {
      const lista = [...$els].filter((el) => {
        const t = (el.innerText || '').replace(/\s+/g, ' ').trim();
        if (!t || t.length > 80) return false;
        return /Costa Azul|Finca Activa Prueba|El Remanso|Los Esteros|La Esperanza|El palmar/i.test(t);
      });
      const preferida =
        lista.find((el) => /Finca Activa Prueba/i.test(el.innerText || '')) ||
        lista.find((el) => /El palmar/i.test(el.innerText || '')) ||
        lista.find((el) => !/Costa Azul/i.test(el.innerText || '')) ||
        lista[0];
      if (!preferida) {
        throw new Error(
          'TC-M09-G85 BLOQUEADO: no hay boton de finca seleccionable en Identidad Visual.'
        );
      }
      cy.wrap(preferida).click({ force: true });
    });

    cy.get('input[aria-label="Hex Color primario"]', { timeout: 15000 })
      .first()
      .should('be.visible')
      .clear({ force: true })
      .type(COLOR_PRI, { force: true });

    cy.get('input[aria-label="Hex Color secundario"], input[aria-label*="Hex Color secundario" i]', { timeout: 8000 })
      .first()
      .should('be.visible')
      .clear({ force: true })
      .type(COLOR_SEC, { force: true });

    cy.get('input:not([type="file"]):not([type="color"])').then(($inputs) => {
      const name = [...$inputs].find((input) => {
        const attrs = `${input.name} ${input.id} ${input.placeholder} ${input.getAttribute('aria-label') || ''}`.toLowerCase();
        return attrs.includes('organiz') || attrs.includes('display') || attrs.includes('nombre');
      });
      if (name) {
        cy.wrap(name).clear({ force: true }).type(ORG, { force: true });
      }
    });

    cy.get('body').then(($body) => {
      if (/Aplicar vista previa/i.test($body.text())) {
        cy.contains('button', /Aplicar vista previa/i).click({ force: true });
      }
    });

    cy.contains('button', /Actualizar identidad|Guardar identidad/i, { timeout: 10000 })
      .should('be.visible')
      .click({ force: true });

    cy.contains(
      /Identidad (visual )?(guardada|actualizada)|cambios guardados|guardada con éxito|actualizada con éxito/i,
      { timeout: 20000 }
    ).should('be.visible');
    cy.contains(/aún no están guardados/i).should('not.exist');
    cy.screenshot('G85-rev2-04-guardado');
  });
});
