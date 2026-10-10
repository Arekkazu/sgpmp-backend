/**
 * TC-M01-074 rev4 TEST — intentar exportar auditoría sin conexión (RF-10 / CU07).
 * Conserva rev1/rev2/rev3. Password via Cypress.env('contrasena').
 *
 * Offline: CDP Network.emulateNetworkConditions + navigator.onLine + evento offline.
 * CDP cubre que fetch/XHR no salgan; el evento es lo que useOnlineStatus/Pa() escucha.
 * Restaura online en after() (CDP + navigator).
 */
const TEST_FRONT = 'https://sigab-frontendtest-6aqrny-d2b730-158-69-200-27.sslip.io';
const EVIDENCIA = 'tests/Test_Testing/Test_Modulo1/RF-10/TC-M01-74/Resultados';
const POST_LOGIN = /\/sesiones\/?$/;
const POST_REFRESH = /\/sesiones\/refresh\/?$/;
const GET_AUDITORIA = /\/auditoria\/?(\?.*)?$/;
const GET_EXPORTAR = /\/auditoria\/exportar\/?(\?.*)?$/;

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

function cdpNetwork(offline) {
  return Cypress.automation('remote:debugger:protocol', {
    command: 'Network.enable',
  }).then(() =>
    Cypress.automation('remote:debugger:protocol', {
      command: 'Network.emulateNetworkConditions',
      params: {
        offline,
        latency: 0,
        downloadThroughput: offline ? 0 : -1,
        uploadThroughput: offline ? 0 : -1,
        connectionType: offline ? 'none' : 'ethernet',
      },
    })
  );
}

function marcarNavegador(win, online) {
  Object.defineProperty(win.navigator, 'onLine', {
    configurable: true,
    get: () => online,
  });
  win.dispatchEvent(new Event(online ? 'online' : 'offline'));
}

describe('TC-M01-074 rev4 TEST - exportar auditoría offline', () => {
  const notas = {
    caso: 'TC-M01-074',
    revision: 4,
    fecha: new Date().toISOString(),
    ambiente: 'TEST',
    front: TEST_FRONT,
    usuario: null,
    logins: 0,
    loginHttp: null,
    refreshLlamadas: [],
    getAuditoria: [],
    exportApiHits: [],
    blobUrlCallsOffline: 0,
    blobUrlCallsOnline: 0,
    urlTrasNavegar: null,
    online: null,
    offline: null,
    recuperacion: null,
    onLineAntes: null,
    onLineOffline: null,
    onLineRestaurado: null,
    cdpOfflineOk: null,
    cdpOnlineOk: null,
    urlOffline: null,
    h1Offline: null,
    alertaOffline: null,
    clickOfflineDisparado: null,
    escenario: 'PENDIENTE',
    clasificacion: 'PENDIENTE',
    notaAuth: null,
  };

  after(() => {
    cy.window({ log: false }).then((win) => {
      try {
        marcarNavegador(win, true);
      } catch (e) {
        /* ignore */
      }
      notas.onLineRestaurado = win.navigator.onLine;
    });
    cy.then(() => cdpNetwork(false).then(() => {
      notas.cdpOnlineOk = true;
    })).then(
      () => undefined,
      () => {
        notas.cdpOnlineOk = false;
      }
    );
  });

  it('online, offline y recuperación de Exportar CSV en auditoría TEST', function () {
    const correo = Cypress.env('correo') || 'admin@pecuaria.co';
    const contrasena = Cypress.env('contrasena');
    expect(contrasena, 'contrasena via Cypress.env (no hardcodear)').to.be.a('string').and.not.empty;
    notas.usuario = correo;

    cy.intercept({ method: 'POST', url: POST_LOGIN }).as('login');
    cy.intercept({ method: 'POST', url: POST_REFRESH }, (req) => {
      req.continue((res) => {
        notas.refreshLlamadas.push({
          status: res.statusCode,
          url: String(req.url || '').replace(/([?&]token=)[^&]+/gi, '$1[REDACTED]'),
        });
      });
    }).as('refresh');
    cy.intercept({ method: 'GET', url: GET_AUDITORIA }, (req) => {
      req.continue((res) => {
        notas.getAuditoria.push({ status: res.statusCode });
      });
    }).as('getAuditoria');
    cy.intercept({ method: 'GET', url: GET_EXPORTAR }, (req) => {
      notas.exportApiHits.push({
        when: new Date().toISOString(),
        url: String(req.url || '').split('?')[0],
      });
      req.continue();
    }).as('exportarCsv');
    notas.exportApiHitsOnlineBaseline = 0;

    cy.visit(`${TEST_FRONT}/login`);
    cy.get('input[type="email"], input[name="correo_electronico"]').first().should('be.visible').clear().type(correo);
    cy.get('input[type="password"]').first().should('be.visible').clear().type(contrasena, {
      log: false,
      parseSpecialCharSequences: false,
    });
    cy.get('button[type="submit"]').contains(/ingresar|iniciar sesión|login/i).click();
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
    cy.contains(/Panel principal|Auditoría|Configuración/i, { timeout: 20000 }).should('exist');
    cy.screenshot('074-rev4-01-dashboard');

    cy.contains('a, button, [role="button"]', /^Auditoría$/i).should('be.visible').click();
    cy.url({ timeout: 20000 }).then((u) => {
      notas.urlTrasNavegar = u;
      if (u.includes('/login')) {
        notas.clasificacion = 'BLOQUEADO';
        notas.notaAuth = 'Redirect a /login al navegar Auditoría, antes de offline.';
        notas.escenario = 'NAV';
      }
    });
    cy.url().should('include', '/auditoria');
    cy.url().should('not.include', '/login');
    cy.contains('h1', /Auditoría/i).should('be.visible');
    cy.wait('@getAuditoria').then((intc) => {
      const st = intc.response ? intc.response.statusCode : null;
      expect(st, 'GET auditoria online').to.be.oneOf([200, 206]);
    });
    cy.get('table tbody tr', { timeout: 20000 }).should('have.length.greaterThan', 0);

    cy.contains('button', /Exportar CSV|Export CSV/i)
      .scrollIntoView()
      .should('be.visible')
      .then(($btn) => {
        notas.online = snapshotBoton($btn);
        expect(notas.online.disabledProp, 'online: Exportar habilitado si hay eventos').to.eq(false);
      });
    cy.screenshot('074-rev4-02-online-exportar');
    cy.get('@exportarCsv.all').then((calls) => {
      notas.exportApiHitsOnlineBaseline = (calls || []).length;
    });

    cy.window().then((win) => {
      notas.onLineAntes = win.navigator.onLine;
      expect(notas.onLineAntes, 'antes de emular: online').to.eq(true);
      const origCreate = win.URL.createObjectURL.bind(win.URL);
      notas.blobUrlCallsOffline = 0;
      win.URL.createObjectURL = function blobProbe() {
        notas.blobUrlCallsOffline += 1;
        return origCreate.apply(win.URL, arguments);
      };
      return cdpNetwork(true)
        .then(() => {
          notas.cdpOfflineOk = true;
        })
        .catch((err) => {
          notas.cdpOfflineOk = false;
          notas.cdpOfflineError = String(err && err.message ? err.message : err);
        })
        .then(() => {
          marcarNavegador(win, false);
        });
    });

    cy.window().its('navigator.onLine').should('eq', false);
    cy.window().then((win) => {
      notas.onLineOffline = win.navigator.onLine;
    });
    cy.wait(800);
    cy.url().then((u) => {
      notas.urlOffline = u;
    });
    cy.contains('h1', /Auditoría/i).should('be.visible');
    cy.get('h1').invoke('text').then((t) => {
      notas.h1Offline = String(t || '').trim();
    });
    cy.url().should('include', '/auditoria');
    cy.url().should('not.include', '/login');

    cy.get('body').then(($body) => {
      const txt = $body.text();
      notas.alertaOffline = /sin conexión|requiere conexión|requires a connection/i.test(txt);
    });

    cy.contains('button', /Exportar CSV|Export CSV/i)
      .scrollIntoView()
      .should('be.visible')
      .then(($btn) => {
        notas.offline = snapshotBoton($btn);
        const bloqueado = notas.offline.disabledProp === true || notas.offline.ariaDisabled === 'true';
        if (bloqueado) {
          notas.escenario = 'E';
          notas.clasificacion = 'APROBADO';
          notas.clickOfflineDisparado = false;
        } else {
          notas.escenario = 'D';
          notas.clasificacion = 'RECHAZADO';
          cy.wrap($btn).click();
          notas.clickOfflineDisparado = true;
        }
      });
    cy.wait(500);
    cy.get('@exportarCsv.all').then((calls) => {
      const total = (calls || []).length;
      notas.exportApiHitsOffline = total - (notas.exportApiHitsOnlineBaseline || 0);
    });
    cy.screenshot('074-rev4-03-offline-exportar');

    cy.then(() => {
      const bloqueado =
        notas.offline && (notas.offline.disabledProp === true || notas.offline.ariaDisabled === 'true');
      const sinDescarga = !notas.clickOfflineDisparado && (notas.exportApiHitsOffline || 0) === 0;
      notas.descargaImpedidaOffline = sinDescarga;
    });
    cy.writeFile(`${EVIDENCIA}/TC-M01-074_rev4_notas.json`, notas);
    cy.then(() => {
      const bloqueado =
        notas.offline && (notas.offline.disabledProp === true || notas.offline.ariaDisabled === 'true');
      expect(bloqueado, 'exportación deshabilitada sin conexión (disabled o aria-disabled)').to.eq(true);
      expect(notas.descargaImpedidaOffline, 'sin click ni GET exportar en offline').to.eq(true);
      expect(notas.alertaOffline, 'alerta de sin conexión visible').to.eq(true);
    });

    cy.window().then((win) => {
      return cdpNetwork(false)
        .then(() => {
          notas.cdpOnlineOk = true;
        })
        .catch(() => {
          notas.cdpOnlineOk = false;
        })
        .then(() => {
          marcarNavegador(win, true);
        });
    });
    cy.window().its('navigator.onLine').should('eq', true);
    cy.wait(800);
    cy.url().should('include', '/auditoria');
    cy.url().should('not.include', '/login');
    cy.contains('button', /Exportar CSV|Export CSV/i)
      .scrollIntoView()
      .should('be.visible')
      .then(($btn) => {
        notas.recuperacion = snapshotBoton($btn);
        expect(notas.recuperacion.disabledProp, 'online restaurado: Exportar vuelve a habilitarse').to.eq(false);
      });
    cy.screenshot('074-rev4-04-online-restaurado');

    cy.contains('button', /Exportar CSV|Export CSV/i).click();
    cy.wait(1500);
    cy.get('@exportarCsv.all').then((calls) => {
      notas.exportApiHitsOnline = (calls || []).length;
    });
    cy.screenshot('074-rev4-05-export-tras-recuperacion');
    cy.writeFile(`${EVIDENCIA}/TC-M01-074_rev4_notas.json`, notas);
  });
});
