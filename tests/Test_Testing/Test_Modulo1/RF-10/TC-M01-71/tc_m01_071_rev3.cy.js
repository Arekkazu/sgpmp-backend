/**
 * TC-M01-071 rev3 TEST — RF-10 paginación UI del historial de auditoría.
 * Un login. No asume tamano=50 en UI (front usa default 20; máximo RF-10 es 50).
 * No falla el caso por ausencia de fecha_hasta en el cliente; se documenta.
 */
const TEST_FRONT = 'https://sigab-frontendtest-6aqrny-d2b730-158-69-200-27.sslip.io';
const EVIDENCIA = 'tests/Test_Testing/Test_Modulo1/RF-10/TC-M01-71/Resultados';
const POST_LOGIN = /\/sesiones\/?$/;
const GET_AUDITORIA = /\/auditoria\/?(\?.*)?$/;

function idsDeTabla($rows) {
  return [...$rows].map((row) => Number(row.querySelector('td')?.textContent?.trim()));
}

describe('TC-M01-071 rev3 TEST - paginación UI auditoría', { testIsolation: false }, () => {
  const notas = {
    fecha: new Date().toISOString(),
    ambiente: 'TEST',
    usuario: null,
    loginHttp: null,
    logins: 0,
    tamanoUiEsperado: 20,
    consultas: [],
    idsPagina: {},
    paginaUi: {},
    observacionFechaHasta: null,
    clasificacionUi: 'PENDIENTE',
  };

  function registrarConsulta(interception) {
    const url = interception.request && interception.request.url ? interception.request.url : '';
    const qs = {};
    try {
      const u = new URL(url);
      u.searchParams.forEach((v, k) => {
        qs[k] = v;
      });
    } catch (e) {
      /* ignore */
    }
    const body = interception.response ? interception.response.body : null;
    const items = body && Array.isArray(body.items) ? body.items : [];
    notas.consultas.push({
      status: interception.response ? interception.response.statusCode : null,
      query: qs,
      total: body ? body.total : null,
      pagina: body ? body.pagina : null,
      tamano: body ? body.tamano : null,
      items: items.length,
      first: items[0] ? items[0].id_evento : null,
      last: items.length ? items[items.length - 1].id_evento : null,
      fecha_hasta_query: qs.fecha_hasta || null,
      fecha_hasta_response: body ? body.fecha_hasta || null : null,
    });
  }

  it('navega páginas 1-2-3 y anterior/siguiente en Auditoría', function () {
    const correo = Cypress.env('correo') || 'admin@pecuaria.co';
    const contrasena = Cypress.env('contrasena');
    expect(contrasena, 'contrasena via Cypress.env').to.be.a('string').and.not.empty;
    notas.usuario = correo;

    cy.intercept({ method: 'POST', url: POST_LOGIN }).as('login');
    cy.intercept({ method: 'GET', url: GET_AUDITORIA }).as('getAuditoria');

    cy.visit(`${TEST_FRONT}/login`);
    cy.get('input[type="email"]').should('be.visible').clear().type(correo);
    cy.get('input[type="password"]').should('be.visible').clear().type(contrasena, { log: false });
    cy.get('button[type="submit"]').contains(/ingresar/i).click();
    notas.logins += 1;
    cy.wait('@login').then((intc) => {
      notas.loginHttp = intc.response ? intc.response.statusCode : null;
      expect(notas.loginHttp, 'login HTTP un intento').to.eq(200);
    });
    cy.url({ timeout: 20000 }).should('include', '/dashboard');

    cy.contains('a', /^Auditoría$/).should('be.visible').click();
    cy.url({ timeout: 15000 }).should('include', '/auditoria');
    cy.contains('h1', /^Auditoría$/).should('be.visible');

    cy.wait('@getAuditoria').then((intc) => {
      registrarConsulta(intc);
      const body = intc.response.body;
      expect([200, 206]).to.include(intc.response.statusCode);
      expect(body.tamano, 'tamano UI default').to.be.at.most(50);
      expect(body.items.length).to.be.at.most(50);
      expect(body.items.length).to.be.greaterThan(0);
    });

    cy.get('table tbody tr').should('have.length.greaterThan', 0).then(($rows) => {
      expect($rows.length, 'filas visibles <= 50').to.be.at.most(50);
      notas.idsPagina[1] = idsDeTabla($rows);
    });
    cy.contains('span', /Página 1 de \d+/).scrollIntoView().should('be.visible').then(($el) => {
      notas.paginaUi[1] = $el.text().trim();
    });
    cy.contains('button', /Anterior/).scrollIntoView().should('be.disabled');
    cy.contains('button', /Siguiente/).scrollIntoView().should('not.be.disabled');
    cy.screenshot('ui-pagina-1', { overwrite: true });

    cy.contains('button', /Siguiente/).scrollIntoView().click();
    cy.wait('@getAuditoria').then((intc) => {
      registrarConsulta(intc);
    });
    cy.contains('span', /Página 2 de \d+/).scrollIntoView().should('be.visible').then(($el) => {
      notas.paginaUi[2] = $el.text().trim();
    });
    cy.get('table tbody tr').should('have.length.greaterThan', 0).then(($rows) => {
      expect($rows.length).to.be.at.most(50);
      notas.idsPagina[2] = idsDeTabla($rows);
      expect(notas.idsPagina[2].join(','), 'página 2 no es idéntica a página 1').to.not.eq(
        notas.idsPagina[1].join(',')
      );
    });

    cy.contains('button', /Siguiente/).scrollIntoView().click();
    cy.wait('@getAuditoria').then((intc) => {
      registrarConsulta(intc);
    });
    cy.contains('span', /Página 3 de \d+/).scrollIntoView().should('be.visible').then(($el) => {
      notas.paginaUi[3] = $el.text().trim();
    });
    cy.get('table tbody tr').should('have.length.greaterThan', 0).then(($rows) => {
      expect($rows.length).to.be.at.most(50);
      notas.idsPagina[3] = idsDeTabla($rows);
      expect(notas.idsPagina[3].join(',')).to.not.eq(notas.idsPagina[2].join(','));
    });
    cy.contains('button', /Siguiente/).scrollIntoView().then(($btn) => {
      const textoPagina = notas.paginaUi[3] || '';
      const m = textoPagina.match(/Página (\d+) de (\d+)/);
      if (m && m[1] === m[2]) {
        expect($btn, 'Siguiente deshabilitado en última página').to.be.disabled;
      } else {
        expect($btn, 'Siguiente habilitado si no es última').to.not.be.disabled;
      }
    });

    cy.contains('button', /Anterior/).scrollIntoView().should('not.be.disabled').click();
    cy.wait('@getAuditoria');
    cy.contains('span', /Página 2 de \d+/).scrollIntoView().should('be.visible');

    cy.contains('button', /Anterior/).scrollIntoView().click();
    cy.wait('@getAuditoria');
    cy.contains('span', /Página 1 de \d+/).scrollIntoView().should('be.visible');
    cy.contains('button', /Anterior/).scrollIntoView().should('be.disabled');

    const envioAncla = notas.consultas.filter((c) => Number(c.query.pagina) > 1);
    const conAncla = envioAncla.filter((c) => c.query.fecha_hasta);
    notas.observacionFechaHasta = {
      paginasPosteriores: envioAncla.length,
      conFechaHasta: conAncla.length,
      detalle:
        conAncla.length === 0
          ? 'UI no reenvía fecha_hasta al cambiar de página (useAuditoria default solo pagina/tamano).'
          : 'UI reenvía fecha_hasta.',
    };
    notas.clasificacionUi = 'APROBADO_NAVEGACION';

    cy.writeFile(`${EVIDENCIA}/TC-M01-071_rev3_cypress_notas.json`, notas);
  });
});
