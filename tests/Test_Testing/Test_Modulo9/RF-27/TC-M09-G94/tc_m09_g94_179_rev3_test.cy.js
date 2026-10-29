/**
 * TC-M09-179 rev3 TEST — variante automatica con la cadena correcta:
 * productor@pecuaria.co → finca activa 1 → identidad 1.
 * PATCH identidad solo finca 1; PATCH tema personal 2→1 temporal (#FFFFFF es insuficiente en Claro).
 * Restore identidad + theme_mode=2.
 */
const TEST_FRONT = 'https://sigab-frontendtest-6aqrny-d2b730-158-69-200-27.sslip.io';
const TEST_API = 'https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test';
const EVIDENCIA = 'tests/Test_Testing/Test_Modulo9/RF-27/TC-M09-G94/Resultados';
const COLOR_BAJO = '#FFFFFF';
const FINCA = 1;

describe('TC-M09-179 rev3 TEST - variante con finca activa correcta', { testIsolation: false }, () => {
  let tokenProd = null;
  let tokenAdmin = null;
  let snapId = null;
  let snapTema = null;
  let patchedId = false;
  let patchedTema = false;

  function pass() {
    const c = Cypress.env('contrasena');
    expect(c, 'contrasena via env').to.be.a('string').and.not.empty;
    return c;
  }

  function api(method, path, token, body) {
    return cy.then(() => {
      const opts = {
        method,
        url: `${TEST_API}${path}`,
        headers: { Authorization: `Bearer ${token}`, Accept: 'application/json' },
        failOnStatusCode: false,
      };
      if (body && method === 'PATCH' && path.indexOf('identidad-visual') >= 0) {
        opts.form = true;
        opts.body = body;
      } else if (body) {
        opts.body = body;
      }
      return cy.request(opts);
    });
  }

  function restoreTodo() {
    if (patchedId && tokenAdmin && snapId) {
      api('GET', `/configuracion/identidad-visual/${FINCA}`, tokenAdmin).then((res) => {
        const ver = res.status === 200 && res.body && typeof res.body.version === 'number' ? res.body.version : snapId.version;
        return api('PATCH', `/configuracion/identidad-visual/${FINCA}`, tokenAdmin, {
          primary_color: snapId.primary_color,
          secondary_color: snapId.secondary_color,
          org_display_name: snapId.org_display_name,
          version: ver,
        });
      }).then((r) => {
        expect(r.status, 'restore identidad HTTP').to.be.oneOf([200, 201]);
      });
    }
    if (patchedTema && tokenProd && snapTema != null) {
      api('PATCH', '/configuracion/personalizacion/tema', tokenProd, { theme_mode: snapTema }).then((r) => {
        expect(r.status, 'restore theme_mode HTTP').to.eq(200);
      });
    }
  }

  after(function () {
    restoreTodo();
  });

  it('precondicion GET contexto productor = finca 1 con identidad', function () {
    const contrasena = pass();
    cy.request({
      method: 'POST',
      url: `${TEST_API}/sesiones/`,
      headers: { 'Content-Type': 'application/json' },
      body: { correo_electronico: 'admin@pecuaria.co', contrasena },
      failOnStatusCode: false,
    }).then((r) => {
      expect(r.status, 'login admin API un intento').to.eq(200);
      tokenAdmin = r.body.token;
    });

    cy.intercept({ method: 'GET', url: /\/configuracion\/interfaz\/contexto\/?$/ }).as('ctxNav');
    cy.intercept({ method: 'POST', url: /\/sesiones\/?$/ }).as('loginProd');
    cy.visit(`${TEST_FRONT}/login`);
    cy.get('input[type="email"]').clear().type('productor@pecuaria.co');
    cy.get('input[type="password"]').clear().type(contrasena, { log: false });
    cy.get('button[type="submit"]').contains(/ingresar/i).click();
    cy.wait('@loginProd').then((intc) => {
      expect(intc.response.statusCode, 'login productor UI un intento').to.eq(200);
      tokenProd = intc.response.body.token;
    });
    cy.url({ timeout: 20000 }).should('include', '/dashboard');

    cy.wait('@ctxNav').then((intc) => {
      expect(intc.response.statusCode, 'GET contexto navegador').to.eq(200);
      const body = intc.response.body;
      cy.writeFile(`${EVIDENCIA}/G94-rev3-179-contexto-inicial-browser.json`, {
        id_usuario: body.id_usuario,
        id_finca: body.id_finca,
        finca_activa: body.finca_activa,
        identidad_visual: body.identidad_visual,
        accesibilidad: body.accesibilidad,
      });
      expect(body.id_finca, 'finca activa').to.eq(1);
      expect(body.identidad_visual, 'identidad no null').to.be.an('object');
      expect(body.accesibilidad, 'accesibilidad no null').to.be.an('object');
      expect(String(body.identidad_visual.primary_color).toUpperCase()).to.eq('#1A6B3C');
    });
  });

  it('PATCH temporal tema=1 e identidad #FFFFFF; UI aplica color_ajustado de finca 1', function () {
    expect(tokenAdmin).to.be.a('string');
    expect(tokenProd).to.be.a('string');
    api('GET', `/configuracion/identidad-visual/${FINCA}`, tokenAdmin).then((idRes) => {
      expect(idRes.status).to.eq(200);
      snapId = {
        primary_color: idRes.body.primary_color,
        secondary_color: idRes.body.secondary_color,
        org_display_name: idRes.body.org_display_name,
        version: idRes.body.version,
        logo_path: idRes.body.logo_path,
      };
      cy.writeFile(`${EVIDENCIA}/G94-rev3-179-baseline-identidad.json`, snapId);
    });

    api('GET', '/configuracion/personalizacion/tema', tokenProd).then((tRes) => {
      expect(tRes.status).to.eq(200);
      snapTema = tRes.body.theme_mode;
      cy.writeFile(`${EVIDENCIA}/G94-rev3-179-baseline-tema.json`, { theme_mode: snapTema, fuente: tRes.body.fuente });
      return api('PATCH', '/configuracion/personalizacion/tema', tokenProd, { theme_mode: 1 });
    }).then((pTema) => {
      expect(pTema.status, 'PATCH tema claro').to.eq(200);
      patchedTema = true;
    });

    api('GET', `/configuracion/identidad-visual/${FINCA}`, tokenAdmin).then((idRes) => {
      return api('PATCH', `/configuracion/identidad-visual/${FINCA}`, tokenAdmin, {
        primary_color: COLOR_BAJO,
        secondary_color: snapId.secondary_color,
        org_display_name: snapId.org_display_name,
        version: idRes.body.version,
      });
    }).then((pId) => {
      expect(pId.status, 'PATCH #FFFFFF finca 1').to.be.oneOf([200, 201]);
      patchedId = true;
      const claro = pId.body.accesibilidad.primary_color.claro;
      expect(claro.cumple_aa).to.eq(false);
      expect(claro.ratio).to.be.lessThan(4.5);
      expect(String(claro.color_ajustado).toUpperCase()).to.not.eq(COLOR_BAJO);
      cy.wrap(claro).as('evalClaro');
      cy.writeFile(`${EVIDENCIA}/G94-rev3-179-patch-identidad.json`, {
        id_finca: pId.body.id_finca,
        primary_color: pId.body.primary_color,
        claro,
      });
    });

    cy.intercept({ method: 'GET', url: /\/configuracion\/interfaz\/contexto\/?$/ }).as('ctxPost');
    cy.visit(`${TEST_FRONT}/dashboard`);
    cy.url().should('include', '/dashboard');
    cy.wait('@ctxPost').then((intc) => {
      const body = intc.response.body;
      cy.writeFile(`${EVIDENCIA}/G94-rev3-179-contexto-despues-browser.json`, {
        http: intc.response.statusCode,
        id_finca: body.id_finca,
        identidad_visual: body.identidad_visual,
        accesibilidad_primary_claro: body.accesibilidad && body.accesibilidad.primary_color && body.accesibilidad.primary_color.claro,
      });
      expect(body.id_finca).to.eq(1);
      expect(body.identidad_visual).to.be.an('object');
      expect(String(body.identidad_visual.primary_color).toUpperCase()).to.eq(COLOR_BAJO);
      const claro = body.accesibilidad.primary_color.claro;
      expect(claro.cumple_aa).to.eq(false);
      expect(claro.color_ajustado).to.be.a('string').and.not.empty;
      cy.get('@evalClaro').then((evalClaro) => {
        expect(String(claro.color_ajustado).toUpperCase()).to.eq(String(evalClaro.color_ajustado).toUpperCase());
      });
      cy.document().then((doc) => {
        const css = doc.documentElement.style.getPropertyValue('--brand-500').trim()
          || getComputedStyle(doc.documentElement).getPropertyValue('--brand-500').trim();
        const dataTheme = doc.documentElement.getAttribute('data-theme');
        cy.writeFile(`${EVIDENCIA}/G94-rev3-179-css.json`, {
          data_theme: dataTheme,
          css_brand_500: css,
          color_ajustado_claro: claro.color_ajustado,
          aplica: css.replace(/\s/g, '').toUpperCase() === String(claro.color_ajustado).toUpperCase(),
        });
        expect(dataTheme, 'tema UI claro para #FFFFFF').to.eq('light');
        expect(css.replace(/\s/g, '').toUpperCase(), 'CSS --brand-500 = color_ajustado de finca 1').to.eq(
          String(claro.color_ajustado).toUpperCase()
        );
      });
      cy.screenshot('G94-rev3-179-dashboard-variante');
    });

    cy.task('getAxeSource').then((src) => {
      cy.window().then((win) => {
        if (!win.axe) {
          const script = win.document.createElement('script');
          script.text = src;
          win.document.documentElement.appendChild(script);
        }
      });
    });
    cy.window().should('have.property', 'axe');
    cy.window().then((win) => win.axe.run(win.document, { runOnly: { type: 'rule', values: ['color-contrast'] } })).then((results) => {
      cy.writeFile(`${EVIDENCIA}/G94-rev3-179-axe.json`, {
        violations: (results.violations || []).length,
        passes_nodes: ((results.passes || []).find((p) => p.id === 'color-contrast') || {}).nodes
          ? ((results.passes || []).find((p) => p.id === 'color-contrast').nodes || []).length
          : 0,
      });
    });
  });

  it('validar restauracion GET identidad y contexto', function () {
    restoreTodo();
    patchedId = false;
    patchedTema = false;
    api('GET', `/configuracion/identidad-visual/${FINCA}`, tokenAdmin).then((r) => {
      expect(String(r.body.primary_color).toUpperCase()).to.eq(String(snapId.primary_color).toUpperCase());
      expect(String(r.body.secondary_color).toUpperCase()).to.eq(String(snapId.secondary_color).toUpperCase());
      cy.writeFile(`${EVIDENCIA}/G94-rev3-179-restauracion-identidad.json`, {
        primary_color: r.body.primary_color,
        secondary_color: r.body.secondary_color,
        version: r.body.version,
        org_display_name: r.body.org_display_name,
        logo_path: r.body.logo_path,
      });
    });
    api('GET', '/configuracion/personalizacion/tema', tokenProd).then((r) => {
      expect(r.body.theme_mode).to.eq(snapTema);
      cy.writeFile(`${EVIDENCIA}/G94-rev3-179-restauracion-tema.json`, { theme_mode: r.body.theme_mode });
    });
    api('GET', '/configuracion/interfaz/contexto', tokenProd).then((r) => {
      expect(r.body.id_finca).to.eq(1);
      expect(String(r.body.identidad_visual.primary_color).toUpperCase()).to.eq('#1A6B3C');
      cy.writeFile(`${EVIDENCIA}/G94-rev3-179-contexto-final.json`, {
        id_finca: r.body.id_finca,
        primary: r.body.identidad_visual.primary_color,
        secondary: r.body.identidad_visual.secondary_color,
      });
    });
  });
});
