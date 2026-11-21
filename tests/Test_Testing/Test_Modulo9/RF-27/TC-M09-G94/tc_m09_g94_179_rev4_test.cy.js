/**
 * TC-M09-179 rev4 TEST — no sobrescribe rev1/rev2/rev3.
 * Cadena: productor id=2 → finca 1 → identidad 1.
 * Espera GET tema theme_mode=1 y html[data-theme=light] ANTES de leer --brand-500.
 * No fuerza data-theme ni setProperty.
 */
const TEST_FRONT = 'https://sigab-frontendtest-6aqrny-d2b730-158-69-200-27.sslip.io';
const TEST_API = 'https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test';
const EVIDENCIA = 'tests/Test_Testing/Test_Modulo9/RF-27/TC-M09-G94/Resultados';
const COLOR_BAJO = '#FFFFFF';
const AJUSTADO = '#757575';
const FINCA = 1;
const TOKENS = ['--brand-500', '--brand-600', '--brand-cta', '--brand-cta-hover', '--brand-400', '--brand-nav'];

describe('TC-M09-179 rev4 TEST', { testIsolation: true }, () => {
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

  function normColor(val) {
    const s = String(val || '').trim();
    if (/^#[0-9A-Fa-f]{6}$/.test(s)) {
      return s.toUpperCase();
    }
    const m = s.match(/rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)/i);
    if (m) {
      return (
        '#' +
        [m[1], m[2], m[3]]
          .map((n) => Number(n).toString(16).padStart(2, '0'))
          .join('')
          .toUpperCase()
      );
    }
    return s.replace(/\s/g, '').toUpperCase();
  }

  function api(method, path, who, body) {
    return cy.then(() => {
      const token = who === 'admin' ? tokenAdmin : tokenProd;
      expect(token, `token ${who} para ${method} ${path}`).to.be.a('string').and.not.empty;
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

  function leerTokens() {
    return cy.document().then((doc) => {
      const cs = doc.defaultView.getComputedStyle(doc.documentElement);
      const inline = doc.documentElement.style;
      const out = { data_theme: doc.documentElement.getAttribute('data-theme') };
      TOKENS.forEach((k) => {
        out[k] = {
          inline: (inline.getPropertyValue(k) || '').trim() || null,
          computed: (cs.getPropertyValue(k) || '').trim() || null,
        };
      });
      return out;
    });
  }

  function restoreTodo() {
    cy.then(() => {
      if (patchedId && tokenAdmin && snapId) {
        api('GET', `/configuracion/identidad-visual/${FINCA}`, 'admin').then((res) => {
          const ver =
            res.status === 200 && res.body && typeof res.body.version === 'number'
              ? res.body.version
              : snapId.version;
          return api('PATCH', `/configuracion/identidad-visual/${FINCA}`, 'admin', {
            primary_color: snapId.primary_color,
            secondary_color: snapId.secondary_color,
            org_display_name: snapId.org_display_name,
            version: ver,
          });
        }).then((r) => {
          expect(r.status, 'restore identidad HTTP').to.be.oneOf([200, 201]);
          patchedId = false;
        });
      }
    });
    cy.then(() => {
      if (patchedTema && tokenProd && snapTema != null) {
        api('PATCH', '/configuracion/personalizacion/tema', 'prod', { theme_mode: snapTema }).then((r) => {
          expect(r.status, 'restore theme_mode HTTP').to.eq(200);
          patchedTema = false;
        });
      }
    });
  }

  after(function () {
    restoreTodo();
  });

  it('TC-M09-179 aplica color_ajustado en --brand-500 con data-theme=light', function () {
    const contrasena = pass();

    cy.request({
      method: 'POST',
      url: `${TEST_API}/sesiones/`,
      headers: { 'Content-Type': 'application/json' },
      body: { correo_electronico: 'admin@pecuaria.co', contrasena },
      failOnStatusCode: false,
    }).then((r) => {
      expect(r.status, 'login admin un intento').to.eq(200);
      tokenAdmin = r.body.token;
    });

    cy.intercept({ method: 'GET', url: /\/configuracion\/interfaz\/contexto\/?$/ }).as('ctx');
    cy.intercept({ method: 'GET', url: /\/configuracion\/personalizacion\/tema\/?$/ }).as('getTema');
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

    cy.wait('@ctx').then((intc) => {
      const body = intc.response.body;
      expect(body.id_finca, 'snapshot contexto finca').to.eq(1);
      cy.writeFile(`${EVIDENCIA}/G94-rev4-179-contexto-antes.json`, {
        id_usuario: body.id_usuario,
        id_finca: body.id_finca,
        finca_activa: body.finca_activa,
        identidad_visual: body.identidad_visual,
        accesibilidad: body.accesibilidad,
      });
    });

    leerTokens().then((css) => {
      cy.writeFile(`${EVIDENCIA}/G94-rev4-179-css-antes.json`, css);
    });

    api('GET', `/configuracion/identidad-visual/${FINCA}`, 'admin').then((idRes) => {
      expect(idRes.status, 'GET identidad snapshot').to.eq(200);
      snapId = {
        primary_color: idRes.body.primary_color,
        secondary_color: idRes.body.secondary_color,
        org_display_name: idRes.body.org_display_name,
        version: idRes.body.version,
        logo_path: idRes.body.logo_path,
      };
      expect(String(snapId.primary_color).toUpperCase()).to.eq('#1A6B3C');
      cy.writeFile(`${EVIDENCIA}/G94-rev4-179-snapshot-identidad.json`, snapId);
    });

    api('GET', '/configuracion/personalizacion/tema', 'prod').then((tRes) => {
      expect(tRes.status).to.eq(200);
      snapTema = tRes.body.theme_mode;
      cy.writeFile(`${EVIDENCIA}/G94-rev4-179-snapshot-tema.json`, {
        theme_mode: tRes.body.theme_mode,
        fuente: tRes.body.fuente,
        id_tema_visual: tRes.body.id_tema_visual,
      });
      expect(snapTema).to.eq(2);
      return api('PATCH', '/configuracion/personalizacion/tema', 'prod', { theme_mode: 1 });
    }).then((pTema) => {
      expect(pTema.status, 'PATCH tema=1').to.eq(200);
      patchedTema = true;
      return api('GET', '/configuracion/personalizacion/tema', 'prod');
    }).then((gTema) => {
      expect(gTema.body.theme_mode, 'GET tema tras PATCH').to.eq(1);
      cy.writeFile(`${EVIDENCIA}/G94-rev4-179-tema-tras-patch.json`, {
        theme_mode: gTema.body.theme_mode,
        fuente: gTema.body.fuente,
      });
    });

    api('GET', `/configuracion/identidad-visual/${FINCA}`, 'admin').then((idRes) => {
      return api('PATCH', `/configuracion/identidad-visual/${FINCA}`, 'admin', {
        primary_color: COLOR_BAJO,
        secondary_color: snapId.secondary_color,
        org_display_name: snapId.org_display_name,
        version: idRes.body.version,
      });
    }).then((pId) => {
      expect(pId.status, 'PATCH primary #FFFFFF').to.be.oneOf([200, 201]);
      patchedId = true;
      const claro = pId.body.accesibilidad.primary_color.claro;
      expect(claro.ratio).to.eq(1);
      expect(claro.cumple_aa).to.eq(false);
      expect(normColor(claro.color_ajustado)).to.eq(AJUSTADO);
    });

    api('GET', `/configuracion/identidad-visual/${FINCA}`, 'admin').then((gId) => {
      expect(normColor(gId.body.primary_color)).to.eq(COLOR_BAJO);
      cy.writeFile(`${EVIDENCIA}/G94-rev4-179-identidad-despues.json`, {
        primary_color: gId.body.primary_color,
        secondary_color: gId.body.secondary_color,
        version: gId.body.version,
        accesibilidad_claro: gId.body.accesibilidad.primary_color.claro,
      });
    });

    api('GET', '/configuracion/interfaz/contexto', 'prod').then((ctx) => {
      expect(ctx.body.id_usuario).to.eq(2);
      expect(ctx.body.id_finca).to.eq(1);
      expect(normColor(ctx.body.identidad_visual.primary_color)).to.eq(COLOR_BAJO);
      const claro = ctx.body.accesibilidad.primary_color.claro;
      expect(claro.ratio).to.eq(1);
      expect(claro.cumple_aa).to.eq(false);
      expect(normColor(claro.color_ajustado)).to.eq(AJUSTADO);
      cy.writeFile(`${EVIDENCIA}/G94-rev4-179-contexto-api-despues.json`, {
        id_usuario: ctx.body.id_usuario,
        id_finca: ctx.body.id_finca,
        identidad_visual: ctx.body.identidad_visual,
        accesibilidad_primary_claro: claro,
      });
    });

    cy.intercept({ method: 'GET', url: /\/configuracion\/interfaz\/contexto\/?$/ }).as('ctxPost');
    cy.intercept({ method: 'GET', url: /\/configuracion\/personalizacion\/tema\/?$/ }).as('temaPost');
    cy.visit(`${TEST_FRONT}/dashboard`);
    cy.url().should('include', '/dashboard');

    cy.wait('@temaPost', { timeout: 20000 }).then((intc) => {
      const mode = intc.response.body && intc.response.body.theme_mode;
      cy.writeFile(`${EVIDENCIA}/G94-rev4-179-tema-browser.json`, {
        http: intc.response.statusCode,
        theme_mode: mode,
      });
      expect(mode, 'GET tema navegador = 1').to.eq(1);
    });

    cy.get('html', { timeout: 20000 }).should('have.attr', 'data-theme', 'light');

    cy.wait('@ctxPost', { timeout: 20000 }).then((intc) => {
      const body = intc.response.body;
      cy.writeFile(`${EVIDENCIA}/G94-rev4-179-contexto-browser.json`, {
        http: intc.response.statusCode,
        id_usuario: body.id_usuario,
        id_finca: body.id_finca,
        identidad_visual: body.identidad_visual,
        accesibilidad_primary_claro: body.accesibilidad && body.accesibilidad.primary_color && body.accesibilidad.primary_color.claro,
      });
      expect(body.id_finca, 'contexto navegador finca 1').to.eq(1);
      expect(body.identidad_visual).to.be.an('object');
      expect(body.accesibilidad).to.be.an('object');
      expect(normColor(body.identidad_visual.primary_color)).to.eq(COLOR_BAJO);
      expect(normColor(body.accesibilidad.primary_color.claro.color_ajustado)).to.eq(AJUSTADO);
    });

    leerTokens().then((css) => {
      const aplicado = normColor(css['--brand-500'].inline || css['--brand-500'].computed);
      cy.writeFile(`${EVIDENCIA}/G94-rev4-179-css-despues.json`, {
        ...css,
        esperado: AJUSTADO,
        brand500_normalizado: aplicado,
      });
      expect(aplicado, '--brand-500 = color_ajustado #757575').to.eq(AJUSTADO);
    });

    cy.screenshot('G94-rev4-179-dashboard-light-variante');

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
    cy.window()
      .then((win) => win.axe.run(win.document, { runOnly: { type: 'rule', values: ['color-contrast'] } }))
      .then((results) => {
        const cc = (results.passes || []).find((p) => p.id === 'color-contrast');
        cy.writeFile(`${EVIDENCIA}/G94-rev4-179-axe.json`, {
          violations: (results.violations || []).length,
          violation_ids: (results.violations || []).map((v) => v.id),
          color_contrast_pass_nodes: cc ? (cc.nodes || []).length : 0,
        });
      });
  });
});
