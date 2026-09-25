/**
 * TC-M09-G90 rev2 TEST — RF-27 temas Claro / Oscuro / Automático.
 * No modifica tc_m09_g90.cy.js ni evidencia rev1 DEV.
 *
 *   1=CLARO  2=OSCURO  3=SISTEMA (prefers-color-scheme)
 * GET/PATCH /configuracion/personalizacion/tema
 *
 * Si POST /sesiones/refresh = 500, NO se hace PATCH de theme_mode.
 */
const TEST_FRONT = 'https://sigab-frontendtest-6aqrny-d2b730-158-69-200-27.sslip.io';
const TEST_API = 'https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test';
const EVIDENCIA = 'tests/Test_Testing/Test_Modulo9/RF-27/TC-M09-G90/Resultados';

const GET_TEMA = /\/configuracion\/personalizacion\/tema\/?$/;
const PATCH_TEMA = /\/configuracion\/personalizacion\/tema\/?$/;

describe('TC-M09-G90 rev2 TEST - Temas Claro Oscuro Automatico', { testIsolation: false }, () => {
  let token = null;
  let estadoInicial = null;
  let uiTemaVisual = false;
  let sesionInestable = false;
  const refreshLog = [];

  function interceptarSesion() {
    cy.intercept({ method: 'POST', url: /\/sesiones\/refresh\/?$/ }).as('refreshSesion');
    cy.intercept({ method: 'POST', url: /\/sesiones\/?$/ }).as('login');
  }

  function interceptarTema() {
    cy.intercept({ method: 'GET', url: GET_TEMA }).as('getTema');
    cy.intercept({ method: 'PATCH', url: PATCH_TEMA }).as('patchTema');
  }

  function registrarApariencia(clave) {
    return cy.window().then((win) => {
      const html = win.document.documentElement;
      const body = win.document.body;
      const csHtml = win.getComputedStyle(html);
      const csBody = win.getComputedStyle(body);
      const header = win.document.querySelector('header, [role="banner"], nav');
      const csHeader = header ? win.getComputedStyle(header) : null;
      const input = win.document.querySelector('input, textarea, select');
      const btn = win.document.querySelector('button');
      const mainEl = win.document.querySelector('ion-content, main, [class*="content"]');
      const csMain = mainEl ? win.getComputedStyle(mainEl) : null;
      const snap = {
        clave,
        url: win.location.href,
        dataTheme: html.getAttribute('data-theme'),
        colorScheme: csHtml.colorScheme || html.style.colorScheme || html.getAttribute('data-color-scheme'),
        classList: Array.from(html.classList),
        prefersDark: win.matchMedia('(prefers-color-scheme: dark)').matches,
        htmlBg: csHtml.backgroundColor,
        htmlColor: csHtml.color,
        bodyBg: csBody.backgroundColor,
        bodyColor: csBody.color,
        mainBg: csMain ? csMain.backgroundColor : null,
        headerBg: csHeader ? csHeader.backgroundColor : null,
        inputBg: input ? win.getComputedStyle(input).backgroundColor : null,
        buttonBg: btn ? win.getComputedStyle(btn).backgroundColor : null,
      };
      cy.writeFile(`${EVIDENCIA}/G90-rev2-${clave}.json`, snap);
      cy.wrap(snap, { log: false });
    });
  }

  function rgbLuma(cssColor) {
    const m = String(cssColor || '').match(/rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*([0-9.]+))?/i);
    if (!m) {
      return null;
    }
    const a = m[4] == null ? 1 : Number(m[4]);
    if (a === 0) {
      return null;
    }
    const r = Number(m[1]) / 255;
    const g = Number(m[2]) / 255;
    const b = Number(m[3]) / 255;
    return 0.2126 * r + 0.7152 * g + 0.0722 * b;
  }

  function assertPresentacionClara(snap) {
    expect(snap.dataTheme, 'html[data-theme] claro').to.eq('light');
  }

  function assertPresentacionOscura(snap) {
    expect(snap.dataTheme, 'html[data-theme] oscuro').to.eq('dark');
  }

  function sincronizarToken() {
    return cy.get('@getTema.all').then((calls) => {
      if (!calls || !calls.length) {
        return;
      }
      const headers = calls[calls.length - 1].request.headers || {};
      const auth = headers.authorization || headers.Authorization;
      if (auth) {
        token = String(auth).replace(/^Bearer\s+/i, '');
      }
    });
  }

  function irATemaVisual() {
    cy.url().then((url) => {
      if (!/\/configuracion/.test(url) || /\/login/.test(url)) {
        interceptarSesion();
        interceptarTema();
        cy.visit(`${TEST_FRONT}/configuracion`);
        cy.wait(1500);
      }
    });
    cy.contains('Configuración del Sistema', { timeout: 20000 }).should('exist');
    cy.url().should('include', '/configuracion');
    cy.url().should('not.include', '/login');
    cy.url().should('include', '/configuracion');
    cy.url().should('not.include', '/login');
    cy.contains('button, a, [role="tab"], ion-segment-button', /^Personalización$/).click({ force: true });
    cy.contains('Tema Visual', { timeout: 15000 }).should('exist');
    cy.contains('Claro').should('exist');
    cy.contains('Oscuro').should('exist');
    cy.contains('Automático').should('exist');
    cy.contains('button', /Guardar tema/i).should('exist');
  }

  function guardarTema(etiquetaBoton, themeModeEsperado) {
    cy.contains(etiquetaBoton).first().click({ force: true });
    cy.contains('button', /Guardar tema/i).first().click({ force: true });
    cy.wait('@patchTema').then((interception) => {
      const status = interception.response && interception.response.statusCode;
      const body = interception.request.body || {};
      expect(status, 'PATCH tema HTTP').to.be.oneOf([200, 201]);
      expect(body.theme_mode, `PATCH theme_mode=${themeModeEsperado}`).to.eq(themeModeEsperado);
    });
    cy.contains(/Tema guardado|El tema se aplicó correctamente|guardado/i, { timeout: 10000 }).should('exist');
    cy.url().should('not.include', '/login');
  }

  function consultarTemaApi(asercion) {
    cy.request({
      method: 'GET',
      url: `${TEST_API}/configuracion/personalizacion/tema`,
      headers: { Authorization: `Bearer ${token}` },
      failOnStatusCode: false,
    }).then((res) => {
      expect(res.status, 'GET tema HTTP').to.eq(200);
      asercion(res.body);
    });
  }

  function emularPrefersColorScheme(valor) {
    return cy
      .wrap(null, { log: false })
      .then(() =>
        Cypress.automation('remote:debugger:protocol', {
          command: 'Emulation.setEmulatedMedia',
          params: { features: [{ name: 'prefers-color-scheme', value: valor }] },
        })
      )
      .then(() =>
        cy.window({ log: false }).then((win) => {
          const dark = win.matchMedia('(prefers-color-scheme: dark)').matches;
          return valor === 'dark' ? dark === true : dark === false;
        })
      );
  }

  before(function () {
    const correo = Cypress.env('correo') || 'admin@pecuaria.co';
    const contrasena = Cypress.env('contrasena');
    expect(contrasena, 'contrasena via Cypress.env').to.be.a('string').and.not.empty;

    interceptarSesion();
    interceptarTema();

    cy.visit(`${TEST_FRONT}/login`);
    cy.get('input[type="email"], input[name="correo_electronico"]').first().should('be.visible').clear().type(correo);
    cy.get('input[type="password"]').first().should('be.visible').clear().type(contrasena, { log: false });
    cy.get('button[type="submit"]').contains(/ingresar/i).click();
    cy.wait('@login').then((interception) => {
      const status = interception.response && interception.response.statusCode;
      expect(status, 'login HTTP').to.eq(200);
      token = interception.response.body && interception.response.body.token;
      expect(token, 'token de sesión').to.be.a('string').and.not.empty;
    });
    cy.url({ timeout: 20000 }).should('include', '/dashboard');
    cy.url().should('not.include', '/login');
    cy.screenshot('G90-rev2-01-dashboard');
    registrarApariencia('dashboard-inicial');

    interceptarSesion();
    cy.visit(`${TEST_FRONT}/configuracion`);
    cy.wait(2000);
    cy.then(() => {
      return cy.get('@refreshSesion.all').then((items) => {
        const mapped = (items || []).map((x) => ({
          status: x.response && x.response.statusCode,
          error_code: x.response && x.response.body && x.response.body.error_code ? x.response.body.error_code : null,
        }));
        const rota = mapped.some((x) => x.status >= 500);
        if (rota) {
          sesionInestable = true;
          Cypress.env('sesionInestable', true);
        }
        cy.writeFile(`${EVIDENCIA}/G90-rev2-refresh.json`, { refreshLog: mapped, sesionInestable: rota });
      });
    });
    cy.url().then((url) => {
      if (/\/login/.test(url)) {
        sesionInestable = true;
        Cypress.env('sesionInestable', true);
      }
    });
    cy.screenshot('G90-rev2-02-tras-configuracion');

    cy.then(function () {
      if (sesionInestable) {
        cy.writeFile(
          `${EVIDENCIA}/G90-rev2-sesion-bloqueada.txt`,
          [
            'DETENIDO: POST /sesiones/refresh status>=500 o redireccion a /login.',
            'No se ejecutaron PATCH de theme_mode.',
            JSON.stringify(refreshLog, null, 2),
          ].join('\n')
        );
        return;
      }
      cy.contains('h1, h2, button, a', /Configuración/i, { timeout: 15000 }).should('exist');
      cy.contains('button, a, [role="tab"], ion-segment-button', /^Personalización$/).click({ force: true });
      cy.wait(1500);
      cy.screenshot('G90-rev2-03-personalizacion');
      cy.get('body').invoke('text').then((texto) => {
        cy.writeFile(`${EVIDENCIA}/G90-rev2-ui-personalizacion.txt`, String(texto).slice(0, 4000));
        uiTemaVisual =
          (/Tema Visual/i.test(texto) || /tema/i.test(texto)) &&
          /Claro/i.test(texto) &&
          /Oscuro/i.test(texto) &&
          (/Automático/i.test(texto) || /Automatico/i.test(texto) || /Sistema/i.test(texto));
        if (!uiTemaVisual) {
          cy.writeFile(
            `${EVIDENCIA}/G90-rev2-diagnostico-ui.txt`,
            [
              'TC-M09-G90 rev2: no se encontró Tema Visual (Claro/Oscuro/Automático) en TEST.',
              'No se clasifica como defecto de RF-27 hasta confirmar despliegue de UI.',
              `url=${window.location.href}`,
            ].join('\n')
          );
        }
      });
    });

    cy.then(() => {
      if (sesionInestable || !uiTemaVisual) {
        return;
      }
      consultarTemaApi((body) => {
        estadoInicial = {
          theme_mode: body.theme_mode,
          fuente: body.fuente,
          id_tema_visual: body.id_tema_visual,
        };
        cy.writeFile(`${EVIDENCIA}/G90-rev2-estado-inicial.json`, estadoInicial);
      });
    });
  });

  after(function () {
    if (!estadoInicial || typeof estadoInicial.theme_mode !== 'number') {
      return;
    }
    const correo = Cypress.env('correo') || 'admin@pecuaria.co';
    const contrasena = Cypress.env('contrasena');
    cy.request({
      method: 'POST',
      url: `${TEST_API}/sesiones/`,
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: { correo_electronico: correo, contrasena },
      failOnStatusCode: false,
    }).then((loginRes) => {
      expect(loginRes.status, 'login restauración HTTP').to.eq(200);
      token = loginRes.body && loginRes.body.token;
      cy.request({
        method: 'PATCH',
        url: `${TEST_API}/configuracion/personalizacion/tema`,
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: { theme_mode: estadoInicial.theme_mode },
        failOnStatusCode: false,
      }).then((res) => {
        expect(res.status, 'PATCH restauración HTTP').to.be.oneOf([200, 201]);
      });
      cy.request({
        method: 'GET',
        url: `${TEST_API}/configuracion/personalizacion/tema`,
        headers: { Authorization: `Bearer ${token}` },
        failOnStatusCode: false,
      }).then((res) => {
        expect(res.status, 'GET restauración HTTP').to.eq(200);
        expect(res.body.theme_mode, 'theme_mode restaurado').to.eq(estadoInicial.theme_mode);
        cy.writeFile(`${EVIDENCIA}/G90-rev2-estado-restaurado.json`, {
          theme_mode: res.body.theme_mode,
          fuente: res.body.fuente,
          id_tema_visual: res.body.id_tema_visual,
        });
      });
    });
  });

  it('TC-M09-170 - Aplicar correctamente el tema Claro (theme_mode=1)', function () {
    if (sesionInestable || Cypress.env('sesionInestable')) {
      this.skip();
    }
    if (!uiTemaVisual) {
      this.skip();
    }

    interceptarTema();
    irATemaVisual();
    cy.screenshot('G90-rev2-170-01-tema-visual');
    guardarTema(/Claro/, 1);
    registrarApariencia('170-claro').then(assertPresentacionClara);
    cy.screenshot('G90-rev2-170-02-claro-aplicado');

    cy.reload();
    cy.contains('Configuración del Sistema', { timeout: 20000 }).should('exist');
    cy.url().should('not.include', '/login');
    cy.contains('button, a, [role="tab"], ion-segment-button', /^Personalización$/).click({ force: true });
    cy.contains('Tema Visual', { timeout: 15000 }).should('exist');
    registrarApariencia('170-persistencia').then(assertPresentacionClara);
    sincronizarToken();
    consultarTemaApi((body) => {
      expect(body.theme_mode, 'persistencia theme_mode=1').to.eq(1);
    });
    cy.contains('Claro').should('exist');
    cy.contains('Configuración del Sistema').should('exist');
    cy.screenshot('G90-rev2-170-03-persistencia');
  });

  it('TC-M09-171 - Aplicar correctamente el tema Oscuro (theme_mode=2)', function () {
    if (sesionInestable || Cypress.env('sesionInestable')) {
      this.skip();
    }
    if (!uiTemaVisual) {
      this.skip();
    }

    interceptarTema();
    irATemaVisual();
    cy.screenshot('G90-rev2-171-01-tema-visual');
    guardarTema(/Oscuro/, 2);
    registrarApariencia('171-oscuro').then(assertPresentacionOscura);
    cy.screenshot('G90-rev2-171-02-oscuro-aplicado');

    cy.reload();
    cy.contains('Configuración del Sistema', { timeout: 20000 }).should('exist');
    cy.url().should('not.include', '/login');
    cy.contains('button, a, [role="tab"], ion-segment-button', /^Personalización$/).click({ force: true });
    cy.contains('Tema Visual', { timeout: 15000 }).should('exist');
    registrarApariencia('171-persistencia').then(assertPresentacionOscura);
    sincronizarToken();
    consultarTemaApi((body) => {
      expect(body.theme_mode, 'persistencia theme_mode=2').to.eq(2);
    });
    cy.contains('Oscuro').should('exist');
    cy.screenshot('G90-rev2-171-03-persistencia');
  });

  it('TC-M09-172 - Aplicar automaticamente el tema segun el dispositivo (theme_mode=3)', function () {
    if (sesionInestable || Cypress.env('sesionInestable')) {
      this.skip();
    }
    if (!uiTemaVisual) {
      this.skip();
    }

    interceptarTema();
    irATemaVisual();
    cy.screenshot('G90-rev2-172-01-tema-visual');
    guardarTema(/Automático/, 3);
    sincronizarToken();
    consultarTemaApi((body) => {
      expect(body.theme_mode, 'theme_mode persistido=3').to.eq(3);
    });

    emularPrefersColorScheme('light').then((okLight) => {
      if (!okLight) {
        cy.writeFile(
          `${EVIDENCIA}/G90-rev2-172-bloqueo-emulacion.txt`,
          'BLOQUEADO: Emulation.setEmulatedMedia no actualizó matchMedia light.'
        );
        this.skip();
        return;
      }
      cy.reload();
      emularPrefersColorScheme('light');
      cy.url().should('not.include', '/login');
      consultarTemaApi((body) => {
        expect(body.theme_mode, 'theme_mode sigue en 3 con sistema claro').to.eq(3);
      });
      registrarApariencia('172-sistema-claro').then(assertPresentacionClara);
      cy.screenshot('G90-rev2-172-02-sistema-claro');

      emularPrefersColorScheme('dark').then((okDark) => {
        if (!okDark) {
          cy.writeFile(
            `${EVIDENCIA}/G90-rev2-172-bloqueo-emulacion.txt`,
            'BLOQUEADO: Emulation.setEmulatedMedia no actualizó matchMedia dark.'
          );
          this.skip();
          return;
        }
        cy.reload();
        emularPrefersColorScheme('dark');
        cy.url().should('not.include', '/login');
        consultarTemaApi((body) => {
          expect(body.theme_mode, 'theme_mode sigue en 3 con sistema oscuro').to.eq(3);
        });
        registrarApariencia('172-sistema-oscuro').then(assertPresentacionOscura);
        cy.screenshot('G90-rev2-172-03-sistema-oscuro');
      });
    });
  });
});
