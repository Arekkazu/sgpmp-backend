/**
 * TC-M09-G90 — Aplicación de temas Claro, Oscuro y Automático (RF-27).
 *
 *   TC-M09-170 → theme_mode=1 → Claro  → html[data-theme="light"]
 *   TC-M09-171 → theme_mode=2 → Oscuro → html[data-theme="dark"]
 *   TC-M09-172 → theme_mode=3 → Automático según prefers-color-scheme
 *
 * Ejecutar contra DEV (no usar el baseUrl TEST de cypress.config.cjs):
 *   npx cypress run --spec tests/Test_Testing/Test_Modulo9/RF-27/TC-M09-G90/tc_m09_g90.cy.js --env correo=admin.dev@gmail.com,contrasena=***
 *
 * Si Tema Visual no está en la UI, los tests se marcan skipped (BLOQUEADO), no como
 * defecto de producto. TC-M09-172 se marca BLOQUEADO si CDP no actualiza matchMedia.
 */
const DEV_FRONT = 'https://sigab-frontenddev-pbw0py-757e2f-158-69-200-27.sslip.io';
const DEV_API = 'https://sigab-backenddev-jpuya4-ea3a74-158-69-200-27.sslip.io/api-sgpmp';
const EVIDENCIA = 'tests/Test_Testing/Test_Modulo9/RF-27/TC-M09-G90/Resultados';

const GET_TEMA = /\/configuracion\/personalizacion\/tema\/?$/;
const PATCH_TEMA = /\/configuracion\/personalizacion\/tema\/?$/;

describe('TC-M09-G90 - Aplicación de temas Claro, Oscuro y Automático', { testIsolation: false }, () => {
  let token = null;
  let estadoInicial = null;
  let uiTemaVisual = false;

  function interceptarTema() {
    cy.intercept({ method: 'GET', url: GET_TEMA }).as('getTema');
    cy.intercept({ method: 'PATCH', url: PATCH_TEMA }).as('patchTema');
  }

  function irATemaVisual() {
    cy.visit(`${DEV_FRONT}/configuracion`);
    cy.contains('h1, h2, button', /Configuración/i, { timeout: 15000 }).should('exist');
    cy.url().should('include', '/configuracion');
    cy.url().should('not.include', '/login');
    cy.contains('button', /^Personalización$/i).click({ force: true });
    cy.contains('h2', /Tema Visual/i, { timeout: 15000 }).should('exist');
    cy.contains('button', /^Claro$/).should('exist');
    cy.contains('button', /^Oscuro$/).should('exist');
    cy.contains('button', /^Automático$/).should('exist');
    cy.contains('button', /Guardar tema/i).should('exist');
  }

  function guardarTema(etiquetaBoton, themeModeEsperado) {
    cy.contains('button', etiquetaBoton).click({ force: true });
    cy.contains('button', /Guardar tema/i).click({ force: true });
    cy.wait('@patchTema').then((interception) => {
      const status = interception.response && interception.response.statusCode;
      const body = interception.request.body || {};
      expect(status, 'PATCH tema HTTP').to.be.oneOf([200, 201]);
      expect(body.theme_mode, `PATCH theme_mode=${themeModeEsperado}`).to.eq(themeModeEsperado);
    });
    cy.contains(/Tema guardado|El tema se aplicó correctamente/i, { timeout: 10000 }).should('exist');
    cy.url().should('not.include', '/login');
  }

  function consultarTemaApi(asercion) {
    cy.request({
      method: 'GET',
      url: `${DEV_API}/configuracion/personalizacion/tema`,
      headers: { Authorization: `Bearer ${token}` },
      failOnStatusCode: false,
    }).then((res) => {
      expect(res.status, 'GET tema HTTP').to.eq(200);
      asercion(res.body);
    });
  }

  /**
   * Emula prefers-color-scheme vía CDP. No toca data-theme.
   * Devuelve true si matchMedia refleja la emulación; si no, el caller debe BLOQUEAR 172.
   */
  function emularPrefersColorScheme(valor) {
    return cy
      .wrap(null, { log: false })
      .then(() =>
        Cypress.automation('remote:debugger:protocol', {
          command: 'Emulation.setEmulatedMedia',
          params: {
            features: [{ name: 'prefers-color-scheme', value: valor }],
          },
        })
      )
      .then(() =>
        cy.window({ log: false }).then((win) => {
          const dark = win.matchMedia('(prefers-color-scheme: dark)').matches;
          const ok = valor === 'dark' ? dark === true : dark === false;
          return ok;
        })
      );
  }

  before(function () {
    const correo = Cypress.env('correo') || 'admin.dev@gmail.com';
    const contrasena = Cypress.env('contrasena');
    expect(contrasena, 'contrasena via Cypress.env (no hardcodear)').to.be.a('string').and.not.empty;

    interceptarTema();
    cy.intercept({ method: 'POST', url: /\/sesiones\/?$/ }).as('login');

    cy.visit(`${DEV_FRONT}/login`);
    cy.get('input[type="email"]').should('be.visible').clear().type(correo);
    cy.get('input[type="password"]').should('be.visible').clear().type(contrasena, { log: false });
    cy.get('button[type="submit"]').contains(/ingresar/i).click();
    cy.wait('@login').then((interception) => {
      const status = interception.response && interception.response.statusCode;
      expect(status, 'login HTTP').to.eq(200);
      token = interception.response.body && interception.response.body.token;
      expect(token, 'token de sesión').to.be.a('string').and.not.empty;
    });
    cy.url({ timeout: 20000 }).should('include', '/dashboard');
    cy.url().should('not.include', '/login');
    cy.screenshot('G90-01-dashboard-inicial');

    cy.visit(`${DEV_FRONT}/configuracion`);
    cy.contains('h1, h2, button', /Configuración/i, { timeout: 15000 }).should('exist');
    cy.contains('button', /^Personalización$/i).click({ force: true });

    cy.get('body').then(($body) => {
      const texto = $body.text();
      uiTemaVisual = /Tema Visual/i.test(texto) && /Claro/.test(texto) && /Oscuro/.test(texto) && /Automático/.test(texto);
      if (!uiTemaVisual) {
        cy.writeFile(
          `${EVIDENCIA}/G90-diagnostico-ui.txt`,
          [
            'TC-M09-G90 BLOQUEADO',
            '',
            'No se encontró la sección Tema Visual (Claro / Oscuro / Automático) en DEV.',
            'No se clasifica como defecto de producto hasta confirmar el despliegue.',
            `URL: ${window.location.href}`,
          ].join('\n')
        );
      }
    });

    cy.then(() => {
      if (!uiTemaVisual) {
        return;
      }
      consultarTemaApi((body) => {
        estadoInicial = {
          theme_mode: body.theme_mode,
          fuente: body.fuente,
          id_tema_visual: body.id_tema_visual,
        };
        cy.writeFile(`${EVIDENCIA}/G90-estado-inicial.json`, estadoInicial);
      });
    });
  });

  after(function () {
    if (!token || !estadoInicial || typeof estadoInicial.theme_mode !== 'number') {
      return;
    }
    cy.request({
      method: 'PATCH',
      url: `${DEV_API}/configuracion/personalizacion/tema`,
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: { theme_mode: estadoInicial.theme_mode },
      failOnStatusCode: false,
    }).then((res) => {
      expect(res.status, 'PATCH restauración HTTP').to.be.oneOf([200, 201]);
    });
    consultarTemaApi((body) => {
      expect(body.theme_mode, 'theme_mode restaurado al valor inicial').to.eq(estadoInicial.theme_mode);
      cy.writeFile(`${EVIDENCIA}/G90-estado-restaurado.json`, body);
    });
  });

  it('TC-M09-170 - Aplicar correctamente el tema Claro (theme_mode=1)', function () {
    if (!uiTemaVisual) {
      this.skip();
    }

    interceptarTema();
    irATemaVisual();
    cy.screenshot('G90-170-01-tema-visual');

    guardarTema(/^Claro$/, 1);

    cy.get('html').should('have.attr', 'data-theme', 'light');
    cy.screenshot('G90-170-02-claro-aplicado');

    interceptarTema();
    cy.reload();
    cy.url().should('include', '/configuracion');
    cy.url().should('not.include', '/login');
    cy.contains('h2', /Tema Visual/i, { timeout: 15000 }).should('exist');
    cy.get('html').should('have.attr', 'data-theme', 'light');
    consultarTemaApi((body) => {
      expect(body.theme_mode, 'persistencia theme_mode=1').to.eq(1);
    });
    cy.screenshot('G90-170-03-persistencia');
  });

  it('TC-M09-171 - Aplicar correctamente el tema Oscuro (theme_mode=2)', function () {
    if (!uiTemaVisual) {
      this.skip();
    }

    interceptarTema();
    irATemaVisual();
    cy.screenshot('G90-171-01-tema-visual');

    guardarTema(/^Oscuro$/, 2);

    cy.get('html').should('have.attr', 'data-theme', 'dark');
    cy.screenshot('G90-171-02-oscuro-aplicado');

    interceptarTema();
    cy.reload();
    cy.url().should('include', '/configuracion');
    cy.url().should('not.include', '/login');
    cy.contains('h2', /Tema Visual/i, { timeout: 15000 }).should('exist');
    cy.get('html').should('have.attr', 'data-theme', 'dark');
    consultarTemaApi((body) => {
      expect(body.theme_mode, 'persistencia theme_mode=2').to.eq(2);
    });
    cy.screenshot('G90-171-03-persistencia');
  });

  it('TC-M09-172 - Aplicar automáticamente el tema según el dispositivo (theme_mode=3)', function () {
    if (!uiTemaVisual) {
      this.skip();
    }

    interceptarTema();
    irATemaVisual();
    cy.screenshot('G90-172-01-tema-visual');

    guardarTema(/^Automático$/, 3);
    consultarTemaApi((body) => {
      expect(body.theme_mode, 'theme_mode persistido=3').to.eq(3);
    });

    emularPrefersColorScheme('dark').then((okDark) => {
      if (!okDark) {
        cy.writeFile(
          `${EVIDENCIA}/G90-172-bloqueo-emulacion.txt`,
          [
            'TC-M09-172 BLOQUEADO',
            '',
            'Cypress.automation(Emulation.setEmulatedMedia) no actualizó',
            'window.matchMedia("(prefers-color-scheme: dark)").matches.',
            'No se forzó data-theme ni se declaró PASS.',
            'Limitación de herramienta (CDP / Electron), no defecto de producto demostrado.',
          ].join('\n')
        );
        this.skip();
        return;
      }

      cy.get('html').should('have.attr', 'data-theme', 'dark');
      consultarTemaApi((body) => {
        expect(body.theme_mode, 'theme_mode sigue en 3 con sistema oscuro').to.eq(3);
      });
      cy.url().should('not.include', '/login');
      cy.screenshot('G90-172-02-sistema-oscuro');

      emularPrefersColorScheme('light').then((okLight) => {
        if (!okLight) {
          cy.writeFile(
            `${EVIDENCIA}/G90-172-bloqueo-emulacion.txt`,
            [
              'TC-M09-172 BLOQUEADO',
              '',
              'La emulación de prefers-color-scheme: light no se reflejó en matchMedia.',
              'No se forzó data-theme ni se declaró PASS.',
            ].join('\n')
          );
          this.skip();
          return;
        }

        cy.get('html').should('have.attr', 'data-theme', 'light');
        consultarTemaApi((body) => {
          expect(body.theme_mode, 'theme_mode sigue en 3 con sistema claro').to.eq(3);
        });
        cy.url().should('not.include', '/login');
        cy.screenshot('G90-172-03-sistema-claro');
      });
    });
  });
});
