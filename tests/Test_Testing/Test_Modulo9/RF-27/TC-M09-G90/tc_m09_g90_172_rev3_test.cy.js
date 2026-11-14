/**
 * TC-M09-172 rev3 TEST — únicamente Automático (theme_mode=3).
 * No ejecuta TC-M09-170 ni TC-M09-171.
 * No intercepta ni altera POST /sesiones/refresh.
 * No escribe data-theme a mano.
 *
 * Frontend TEST: SISTEMA usa matchMedia('(prefers-color-scheme: dark)')
 * y addEventListener('change') para setAttribute('data-theme', ...).
 */
const TEST_FRONT = 'https://sigab-frontendtest-6aqrny-d2b730-158-69-200-27.sslip.io';
const TEST_API = 'https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test';
const EVIDENCIA = 'tests/Test_Testing/Test_Modulo9/RF-27/TC-M09-G90/Resultados';
const TEMA = /\/configuracion\/personalizacion\/tema\/?$/;

describe('TC-M09-172 rev3 TEST - Tema automatico', { testIsolation: true }, () => {
  let tokenSesion = null;
  let themeModeInicial = null;

  function emularPrefersColorScheme(valor) {
    return cy.wrap(null, { log: false }).then(() =>
      Cypress.automation('remote:debugger:protocol', {
        command: 'Emulation.setEmulatedMedia',
        params: { features: [{ name: 'prefers-color-scheme', value: valor }] },
      })
    ).then(() =>
      cy.window({ log: false }).then((win) => {
        const dark = win.matchMedia('(prefers-color-scheme: dark)').matches;
        return valor === 'dark' ? dark === true : dark === false;
      })
    );
  }

  function esperarDataTheme(esperado) {
    return cy.get('html', { timeout: 10000 }).should('have.attr', 'data-theme', esperado);
  }

  function snapshotApariencia(clave) {
    return cy.window().then((win) => {
      const html = win.document.documentElement;
      const snap = {
        clave,
        url: win.location.href,
        dataTheme: html.getAttribute('data-theme'),
        prefersDark: win.matchMedia('(prefers-color-scheme: dark)').matches,
        loggedIn: !/\/login/.test(win.location.href),
      };
      cy.writeFile(`${EVIDENCIA}/G90-172-rev3-${clave}.json`, snap);
      cy.wrap(snap, { log: false });
    });
  }

  after(function () {
    if (!tokenSesion) {
      return;
    }
    cy.request({
      method: 'PATCH',
      url: `${TEST_API}/configuracion/personalizacion/tema`,
      headers: {
        Authorization: `Bearer ${tokenSesion}`,
        'Content-Type': 'application/json',
      },
      body: { theme_mode: 1 },
      failOnStatusCode: false,
    }).then((res) => {
      if (res.status === 401 || res.status === 410) {
        cy.writeFile(
          `${EVIDENCIA}/G90-172-rev3-restore-aviso.txt`,
          'PATCH restore 401/410 con token de la sesion UI; se intenta login de restauracion unico.'
        );
        const correo = Cypress.env('correo') || 'admin@pecuaria.co';
        const contrasena = Cypress.env('contrasena');
        cy.request({
          method: 'POST',
          url: `${TEST_API}/sesiones/`,
          headers: { 'Content-Type': 'application/json' },
          body: { correo_electronico: correo, contrasena },
          failOnStatusCode: false,
        }).then((loginRes) => {
          expect(loginRes.status, 'login restauracion').to.eq(200);
          const tok = loginRes.body && loginRes.body.token;
          cy.request({
            method: 'PATCH',
            url: `${TEST_API}/configuracion/personalizacion/tema`,
            headers: { Authorization: `Bearer ${tok}`, 'Content-Type': 'application/json' },
            body: { theme_mode: 1 },
            failOnStatusCode: false,
          }).then((r2) => {
            expect(r2.status, 'PATCH restore tras login').to.be.oneOf([200, 201]);
          });
          cy.request({
            method: 'GET',
            url: `${TEST_API}/configuracion/personalizacion/tema`,
            headers: { Authorization: `Bearer ${tok}` },
            failOnStatusCode: false,
          }).then((g) => {
            expect(g.status).to.eq(200);
            expect(g.body.theme_mode, 'theme_mode restaurado=1').to.eq(1);
            cy.writeFile(`${EVIDENCIA}/G90-172-rev3-estado-restaurado.json`, {
              theme_mode: g.body.theme_mode,
              fuente: g.body.fuente,
            });
          });
        });
        return;
      }
      expect(res.status, 'PATCH restore HTTP').to.be.oneOf([200, 201]);
      cy.request({
        method: 'GET',
        url: `${TEST_API}/configuracion/personalizacion/tema`,
        headers: { Authorization: `Bearer ${tokenSesion}` },
        failOnStatusCode: false,
      }).then((g) => {
        expect(g.status).to.eq(200);
        expect(g.body.theme_mode, 'theme_mode restaurado=1').to.eq(1);
        cy.writeFile(`${EVIDENCIA}/G90-172-rev3-estado-restaurado.json`, {
          theme_mode: g.body.theme_mode,
          fuente: g.body.fuente,
        });
      });
    });
  });

  it('TC-M09-172 - Aplicar automaticamente el tema segun el dispositivo (theme_mode=3)', function () {
    const correo = Cypress.env('correo') || 'admin@pecuaria.co';
    const contrasena = Cypress.env('contrasena');
    expect(contrasena, 'contrasena via Cypress.env').to.be.a('string').and.not.empty;

    cy.intercept({ method: 'POST', url: /\/sesiones\/?$/ }).as('login');
    cy.intercept({ method: 'GET', url: TEMA }).as('getTema');
    cy.intercept({ method: 'PATCH', url: TEMA }).as('patchTema');

    cy.visit(`${TEST_FRONT}/login`);
    cy.get('input[type="email"], input[name="correo_electronico"]').first().should('be.visible').clear().type(correo);
    cy.get('input[type="password"]').first().should('be.visible').clear().type(contrasena, { log: false });
    cy.get('button[type="submit"]').contains(/ingresar/i).click();
    cy.wait('@login').then((interception) => {
      expect(interception.response.statusCode, 'login HTTP').to.eq(200);
    });
    cy.url({ timeout: 20000 }).should('include', '/dashboard');
    cy.url().should('not.include', '/login');
    cy.wait('@getTema').then((interception) => {
      expect(interception.response.statusCode, 'GET tema inicial HTTP').to.eq(200);
      themeModeInicial = interception.response.body && interception.response.body.theme_mode;
      cy.writeFile(`${EVIDENCIA}/G90-172-rev3-estado-inicial.json`, {
        theme_mode: themeModeInicial,
        fuente: interception.response.body && interception.response.body.fuente,
      });
    });

    cy.visit(`${TEST_FRONT}/configuracion`);
    cy.contains('Configuración del Sistema', { timeout: 20000 }).should('exist');
    cy.url().should('include', '/configuracion');
    cy.url().should('not.include', '/login');

    cy.contains('button, a, [role="tab"], ion-segment-button', /^Personalización$/).click({ force: true });
    cy.contains('Tema Visual', { timeout: 15000 }).should('exist');
    cy.contains('Automático').should('exist');

    cy.contains('Automático').first().click({ force: true });
    cy.contains('button', /Guardar tema/i).first().click({ force: true });
    cy.wait('@patchTema').then((interception) => {
      expect(interception.response.statusCode, 'PATCH tema HTTP').to.be.oneOf([200, 201]);
      const body = interception.request.body || {};
      expect(body.theme_mode, 'PATCH envia theme_mode=3').to.eq(3);
      const resp = interception.response.body || {};
      expect(resp.theme_mode, 'PATCH respuesta almacena theme_mode=3').to.eq(3);
      const headers = interception.request.headers || {};
      const auth = headers.authorization || headers.Authorization;
      expect(auth, 'Authorization del PATCH de la app').to.be.a('string');
      tokenSesion = String(auth).replace(/^Bearer\s+/i, '');
      cy.writeFile(`${EVIDENCIA}/G90-172-rev3-patch.json`, {
        request_theme_mode: body.theme_mode,
        response_theme_mode: resp.theme_mode,
        es_global: resp.es_global,
      });
    });
    cy.contains(/Tema guardado|El tema se aplicó correctamente/i, { timeout: 10000 }).should('exist');
    cy.url().should('not.include', '/login');

    emularPrefersColorScheme('light').then((okLight) => {
      if (!okLight) {
        cy.writeFile(
          `${EVIDENCIA}/G90-172-rev3-bloqueo-emulacion.txt`,
          'BLOQUEADO: Emulation.setEmulatedMedia no actualizo matchMedia light.'
        );
        this.skip();
        return;
      }
      cy.window().then((win) => {
        if (win.document.documentElement.getAttribute('data-theme') !== 'light') {
          cy.reload();
          emularPrefersColorScheme('light');
        }
      });
      esperarDataTheme('light');
      snapshotApariencia('sistema-claro').then((snap) => {
        expect(snap.dataTheme).to.eq('light');
        expect(snap.prefersDark).to.eq(false);
        expect(snap.loggedIn).to.eq(true);
      });
      cy.contains('Configuración del Sistema').should('exist');
      cy.contains('Tema Visual').should('exist');
      cy.screenshot('G90-172-rev3-automatico-sistema-claro');
    });

    emularPrefersColorScheme('dark').then((okDark) => {
      if (!okDark) {
        cy.writeFile(
          `${EVIDENCIA}/G90-172-rev3-bloqueo-emulacion.txt`,
          'BLOQUEADO: Emulation.setEmulatedMedia no actualizo matchMedia dark.'
        );
        this.skip();
        return;
      }
      cy.window().then((win) => {
        if (win.document.documentElement.getAttribute('data-theme') !== 'dark') {
          cy.reload();
          emularPrefersColorScheme('dark');
        }
      });
      esperarDataTheme('dark');
      snapshotApariencia('sistema-oscuro').then((snap) => {
        expect(snap.dataTheme).to.eq('dark');
        expect(snap.prefersDark).to.eq(true);
        expect(snap.loggedIn).to.eq(true);
      });
      cy.contains('Configuración del Sistema').should('exist');
      cy.screenshot('G90-172-rev3-automatico-sistema-oscuro');
    });

    cy.intercept({ method: 'GET', url: TEMA }).as('getTemaPostAuto');
    cy.contains('button, a, [role="tab"], ion-segment-button', /^Catálogo$|^Catalogo$/).click({ force: true });
    cy.contains('button, a, [role="tab"], ion-segment-button', /^Personalización$/).click({ force: true });
    cy.contains('Tema Visual', { timeout: 15000 }).should('exist');
    cy.wait('@getTemaPostAuto').then((interception) => {
      expect(interception.response.statusCode, 'GET tema post-escenarios HTTP').to.eq(200);
      expect(interception.response.body.theme_mode, 'theme_mode sigue en 3').to.eq(3);
      cy.writeFile(`${EVIDENCIA}/G90-172-rev3-persistencia.json`, {
        theme_mode: interception.response.body.theme_mode,
        fuente: interception.response.body.fuente,
        via: 'GET posterior a light/dark, intercept nuevo',
      });
    });
    cy.url().should('not.include', '/login');
  });
});
