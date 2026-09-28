/**
 * TC-M01-074 rev2 TEST — exportar auditoría sin conexión.
 * Un login. Offline SOLO después de /auditoria estable.
 * Restaura online en after().
 */
const TEST_FRONT = 'https://sigab-frontendtest-6aqrny-d2b730-158-69-200-27.sslip.io';
const EVIDENCIA = 'tests/Test_Testing/Test_Modulo1/RF-10/TC-M01-74/Resultados';
const POST_LOGIN = /\/sesiones\/?$/;
const POST_REFRESH = /\/sesiones\/refresh\/?$/;
const GET_AUDITORIA = /\/auditoria\/?(\?.*)?$/;

function snapshotBoton($btn) {
  const el = $btn[0];
  return {
    text: ($btn.text() || '').replace(/\s+/g, ' ').trim(),
    visible: $btn.is(':visible'),
    disabledProp: Boolean(el.disabled),
    disabledAttr: $btn.attr('disabled') ?? null,
    ariaDisabled: $btn.attr('aria-disabled') ?? null,
    className: el.className || '',
  };
}

describe('TC-M01-074 rev2 TEST - exportar auditoría offline', () => {
  const notas = {
    fecha: new Date().toISOString(),
    ambiente: 'TEST',
    usuario: null,
    logins: 0,
    loginHttp: null,
    refreshLlamadas: [],
    getAuditoria: [],
    urlTrasNavegar: null,
    online: null,
    offline: null,
    onLineAntes: null,
    onLineOffline: null,
    onLineRestaurado: null,
    urlOffline: null,
    escenario: 'PENDIENTE',
    clasificacion: 'PENDIENTE',
  };

  after(() => {
    cy.window({ log: false }).then((win) => {
      try {
        Object.defineProperty(win.navigator, 'onLine', {
          configurable: true,
          get: () => true,
        });
      } catch (e) {
        /* ignore */
      }
      win.dispatchEvent(new Event('online'));
      notas.onLineRestaurado = win.navigator.onLine;
    });
    cy.writeFile(`${EVIDENCIA}/TC-M01-074_rev2_notas.json`, notas);
  });

  it('online llega a auditoría y luego offline evalúa Exportar CSV', function () {
    const correo = Cypress.env('correo') || 'admin@pecuaria.co';
    const contrasena = Cypress.env('contrasena');
    expect(contrasena, 'contrasena via Cypress.env').to.be.a('string').and.not.empty;
    notas.usuario = correo;

    cy.intercept({ method: 'POST', url: POST_LOGIN }).as('login');
    cy.intercept({ method: 'POST', url: POST_REFRESH }, (req) => {
      req.continue((res) => {
        notas.refreshLlamadas.push({
          status: res.statusCode,
          url: req.url,
        });
      });
    }).as('refresh');
    cy.intercept({ method: 'GET', url: GET_AUDITORIA }, (req) => {
      req.continue((res) => {
        notas.getAuditoria.push({ status: res.statusCode });
      });
    }).as('getAuditoria');

    cy.visit(`${TEST_FRONT}/login`);
    cy.get('input[type="email"]').should('be.visible').clear().type(correo);
    cy.get('input[type="password"]').should('be.visible').clear().type(contrasena, { log: false });
    cy.get('button[type="submit"]').contains(/ingresar/i).click();
    notas.logins += 1;
    cy.wait('@login').then((intc) => {
      notas.loginHttp = intc.response ? intc.response.statusCode : null;
      expect(notas.loginHttp, 'login un intento').to.eq(200);
    });
    cy.url({ timeout: 20000 }).should('include', '/dashboard');
    cy.url().should('not.include', '/login');

    cy.contains('a', /^Auditoría$/).should('be.visible').click();
    cy.url({ timeout: 15000 }).should('include', '/auditoria');
    cy.url().then((u) => {
      notas.urlTrasNavegar = u;
      expect(u, 'sesión no redirigió a login').to.not.include('/login');
    });
    cy.contains('h1', /^Auditoría$/).should('be.visible');
    cy.wait('@getAuditoria').then((intc) => {
      const st = intc.response ? intc.response.statusCode : null;
      expect(st, 'GET auditoria online').to.be.oneOf([200, 206]);
    });
    cy.get('table tbody tr', { timeout: 20000 }).should('have.length.greaterThan', 0);

    cy.contains('button', /Exportar CSV/i)
      .scrollIntoView()
      .should('be.visible')
      .then(($btn) => {
        notas.online = snapshotBoton($btn);
        expect(notas.online.disabledProp, 'online: Exportar habilitado si hay eventos').to.eq(false);
      });
    cy.screenshot('074-rev2-online-exportar', { overwrite: true });

    cy.window().then((win) => {
      notas.onLineAntes = win.navigator.onLine;
      expect(notas.onLineAntes, 'antes de emular: online').to.eq(true);
      Object.defineProperty(win.navigator, 'onLine', {
        configurable: true,
        get: () => false,
      });
      win.dispatchEvent(new Event('offline'));
    });

    cy.window().its('navigator.onLine').should('eq', false);
    cy.window().then((win) => {
      notas.onLineOffline = win.navigator.onLine;
    });
    cy.url().then((u) => {
      notas.urlOffline = u;
    });
    cy.contains('h1', /^Auditoría$/).should('be.visible');
    cy.url().should('include', '/auditoria');
    cy.url().should('not.include', '/login');

    cy.contains('button', /Exportar CSV/i)
      .scrollIntoView()
      .should('be.visible')
      .then(($btn) => {
        notas.offline = snapshotBoton($btn);
        const bloqueado = notas.offline.disabledProp === true || notas.offline.ariaDisabled === 'true';
        if (bloqueado) {
          notas.escenario = 'E';
          notas.clasificacion = 'APROBADO';
        } else {
          notas.escenario = 'D';
          notas.clasificacion = 'RECHAZADO';
        }
        expect(
          bloqueado,
          'matriz: exportación deshabilitada sin conexión (disabled o aria-disabled)'
        ).to.eq(true);
      });
  });
});
