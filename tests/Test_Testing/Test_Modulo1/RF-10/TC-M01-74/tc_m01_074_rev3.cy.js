/**
 * TC-M01-074 rev3 TEST — exportar auditoría sin conexión.
 * Conserva rev1/rev2. Offline SOLO después de /auditoria estable.
 * Offline: navigator.onLine + evento offline (sin CDP). Restaura online en after().
 */
const TEST_FRONT = 'https://api.inmero.co';
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
    title: $btn.attr('title') ?? null,
    className: el.className || '',
  };
}

describe('TC-M01-074 rev3 TEST - exportar auditoría offline', () => {
  const notas = {
    revision: 3,
    fecha: new Date().toISOString(),
    ambiente: 'TEST',
    front: TEST_FRONT,
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
    h1Offline: null,
    alertaOffline: null,
    escenario: 'PENDIENTE',
    clasificacion: 'PENDIENTE',
    notaAuth: null,
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
    cy.writeFile(`${EVIDENCIA}/TC-M01-074_rev3_notas.json`, notas);
  });

  it('online llega a auditoría y luego offline evalúa Exportar CSV', function () {
    const correo = Cypress.env('correo') || 'admin@pecuaria.co';
    const contrasena = Cypress.env('contrasena');
    expect(contrasena, 'contrasena via Cypress.env (no hardcodear)').to.be.a('string').and.not.empty;
    notas.usuario = correo;

    cy.intercept({ method: 'POST', url: POST_LOGIN }).as('login');
    cy.intercept({ method: 'POST', url: POST_REFRESH }, (req) => {
      req.continue((res) => {
        notas.refreshLlamadas.push({
          status: res.statusCode,
          url: req.url.replace(/([?&]token=)[^&]+/gi, '$1[REDACTED]'),
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
      if (notas.loginHttp !== 200) {
        notas.clasificacion = 'BLOQUEADO';
        notas.notaAuth = `Login HTTP ${notas.loginHttp}. No se evalua Exportar CSV.`;
        notas.escenario = 'AUTH';
      }
      expect(notas.loginHttp, 'login un intento').to.eq(200);
    });
    cy.url({ timeout: 20000 }).should('include', '/dashboard');
    cy.url().should('not.include', '/login');

    cy.contains('a', /^Auditoría$/).should('be.visible').click();
    cy.url({ timeout: 15000 }).then((u) => {
      notas.urlTrasNavegar = u;
      if (u.includes('/login')) {
        notas.clasificacion = 'BLOQUEADO';
        notas.notaAuth = 'Redirect a /login al navegar Auditoría, antes de offline.';
        notas.escenario = 'NAV';
      }
    });
    cy.url().should('include', '/auditoria');
    cy.url().should('not.include', '/login');
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
    cy.screenshot('074-rev3-online-exportar', { overwrite: true });

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
    cy.get('h1').invoke('text').then((t) => {
      notas.h1Offline = String(t || '').trim();
    });
    cy.url().should('include', '/auditoria');
    cy.url().should('not.include', '/login');

    cy.get('body').then(($body) => {
      const txt = $body.text();
      notas.alertaOffline = /sin conexión|requiere conexión/i.test(txt);
    });

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
    cy.screenshot('074-rev3-offline-exportar', { overwrite: true });
  });
});
