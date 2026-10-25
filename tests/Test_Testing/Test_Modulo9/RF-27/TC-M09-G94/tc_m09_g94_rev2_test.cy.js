/**
 * TC-M09-G94 rev2 TEST — RF-27 contraste WCAG y variante automática.
 * No modifica tc_m09_g94.cy.js ni evidencia rev1 DEV.
 *
 *   TC-M09-178 — axe color-contrast + ratios CSS del dashboard (tema actual)
 *   TC-M09-179 — PATCH temporal identidad finca 4 a #FFFFFF y GET accesibilidad; restore
 *
 * GET contexto: RF-25, recurso 22. Variante: ColorHex.ajustar_para_contraste (backend).
 */
const TEST_FRONT = 'https://sigab-frontendtest-6aqrny-d2b730-158-69-200-27.sslip.io';
const TEST_API = 'https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test';
const EVIDENCIA = 'tests/Test_Testing/Test_Modulo9/RF-27/TC-M09-G94/Resultados';
const COLOR_BAJO = '#FFFFFF';
const FINCA_IDENTIDAD = 4;
const CSS_MARCA = '--brand-500';

describe('TC-M09-G94 rev2 TEST - Contraste y variante automatica', { testIsolation: false }, () => {
  let token = null;
  let baseline179 = null;
  let restaurar179 = false;
  let loginHttp = null;
  let contextoBrowser = [];

  function credenciales() {
    const correo = Cypress.env('correo') || 'admin@pecuaria.co';
    const contrasena = Cypress.env('contrasena');
    expect(contrasena, 'contrasena via Cypress.env').to.be.a('string').and.not.empty;
    return { correo, contrasena };
  }

  function apiGet(path) {
    return cy.then(() => {
      expect(token, 'token disponible antes de GET API').to.be.a('string').and.not.empty;
      return cy.request({
        method: 'GET',
        url: `${TEST_API}${path}`,
        headers: { Authorization: `Bearer ${token}` },
        failOnStatusCode: false,
      });
    });
  }

  function extraerContrasteAxe(nodes) {
    return (nodes || []).map((node) => {
      const data = (node.any && node.any[0] && node.any[0].data) || {};
      return {
        html: node.html,
        target: node.target,
        fgColor: data.fgColor || null,
        bgColor: data.bgColor || null,
        contrastRatio: data.contrastRatio || data.contrast || null,
        fontSize: data.fontSize || null,
        fontWeight: data.fontWeight || null,
        expectedContrastRatio: data.expectedContrastRatio || null,
      };
    });
  }

  function relLuma(cssColor) {
    const m = String(cssColor || '').match(/rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*([0-9.]+))?/i);
    if (!m) return null;
    const a = m[4] == null ? 1 : Number(m[4]);
    if (a === 0) return null;
    const ch = [m[1], m[2], m[3]].map((v) => {
      const c = Number(v) / 255;
      return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
    });
    return 0.2126 * ch[0] + 0.7152 * ch[1] + 0.0722 * ch[2];
  }

  function ratioWcag(fg, bg) {
    const a = relLuma(fg);
    const b = relLuma(bg);
    if (a == null || b == null) return null;
    const hi = Math.max(a, b);
    const lo = Math.min(a, b);
    return (hi + 0.05) / (lo + 0.05);
  }

  after(function () {
    if (!restaurar179 || !token || !baseline179) {
      return;
    }
    apiGet(`/configuracion/identidad-visual/${baseline179.id_finca}`).then((res) => {
      const versionActual =
        res.status === 200 && res.body && typeof res.body.version === 'number'
          ? res.body.version
          : baseline179.version;
      cy.request({
        method: 'PATCH',
        url: `${TEST_API}/configuracion/identidad-visual/${baseline179.id_finca}`,
        headers: { Authorization: `Bearer ${token}` },
        form: true,
        body: {
          primary_color: baseline179.primary_color,
          secondary_color: baseline179.secondary_color,
          org_display_name: baseline179.org_display_name,
          version: versionActual,
        },
        failOnStatusCode: false,
      }).then((patchRes) => {
        expect(patchRes.status, 'PATCH restauracion identidad HTTP').to.be.oneOf([200, 201]);
      });
    });
    apiGet(`/configuracion/identidad-visual/${baseline179.id_finca}`).then((res) => {
      expect(res.status, 'GET identidad tras restaurar').to.eq(200);
      expect(String(res.body.primary_color).toUpperCase()).to.eq(String(baseline179.primary_color).toUpperCase());
      expect(String(res.body.secondary_color).toUpperCase()).to.eq(
        String(baseline179.secondary_color).toUpperCase()
      );
      cy.writeFile(`${EVIDENCIA}/G94-rev2-179-restauracion.json`, {
        primary_color: res.body.primary_color,
        secondary_color: res.body.secondary_color,
        org_display_name: res.body.org_display_name,
        version: res.body.version,
        id_finca: res.body.id_finca,
      });
    });
  });

  it('TC-M09-178 - Verificar contraste minimo WCAG 4.5:1', function () {
    const { correo, contrasena } = credenciales();
    cy.intercept({ method: 'POST', url: /\/sesiones\/refresh\/?$/ }).as('refreshSesion');
    cy.intercept({ method: 'POST', url: /\/sesiones\/?$/ }).as('login');
    cy.intercept({ method: 'GET', url: /\/configuracion\/interfaz\/contexto\/?$/ }, (req) => {
      req.continue((res) => {
        contextoBrowser.push({ status: res.statusCode, hasAuth: Boolean(req.headers.authorization) });
      });
    }).as('getContexto');

    cy.visit(`${TEST_FRONT}/login`);
    cy.get('input[type="email"]').should('be.visible').clear().type(correo);
    cy.get('input[type="password"]').should('be.visible').clear().type(contrasena, { log: false });
    cy.get('button[type="submit"]').contains(/ingresar/i).click();
    cy.wait('@login').then((interception) => {
      loginHttp = interception.response && interception.response.statusCode;
      expect(loginHttp, 'login HTTP (un intento)').to.eq(200);
      token = interception.response.body && interception.response.body.token;
      expect(token, 'token de sesion').to.be.a('string').and.not.empty;
    });
    cy.url({ timeout: 20000 }).should('include', '/dashboard');
    cy.url().should('not.include', '/login');
    cy.screenshot('G94-rev2-178-dashboard');

    cy.document().then((doc) => {
      const dataTheme = doc.documentElement.getAttribute('data-theme') || 'light';
      cy.wrap(dataTheme).as('dataTheme178');
    });

    cy.window().then((win) => {
      const pick = (sel) => win.document.querySelector(sel);
      const cs = (el) => (el ? win.getComputedStyle(el) : null);
      const sample = (name, el) => {
        if (!el) return { name, presente: false };
        const s = cs(el);
        return {
          name,
          presente: true,
          selector: el.tagName + (el.className ? `.${String(el.className).split(' ')[0]}` : ''),
          color: s.color,
          backgroundColor: s.backgroundColor,
          fontSize: s.fontSize,
          fontWeight: s.fontWeight,
          ratio: ratioWcag(s.color, s.backgroundColor),
        };
      };
      const html = win.document.documentElement;
      const body = win.document.body;
      const header = pick('header, [role="banner"], nav');
      const mainEl = pick('ion-content, main, [class*="content"]');
      const h1 = pick('h1, h2');
      const p = pick('p, [class*="muted"], small');
      const input = pick('input, textarea');
      const btn = pick('button');
      const link = pick('a[href]');
      const card = pick('[class*="card"], article, section');
      const htmlCs = cs(html);
      const bodyCs = cs(body);
      const brand = htmlCs.getPropertyValue(CSS_MARCA).trim();
      const ratios = [
        sample('html', html),
        sample('body', body),
        sample('header_nav', header),
        sample('main', mainEl),
        sample('heading', h1),
        sample('parrafo_o_muted', p),
        sample('input', input),
        sample('button', btn),
        sample('enlace', link),
        sample('card', card),
      ];
      const snap = {
        dataTheme: html.getAttribute('data-theme'),
        htmlBg: htmlCs.backgroundColor,
        htmlColor: htmlCs.color,
        bodyBg: bodyCs.backgroundColor,
        bodyColor: bodyCs.color,
        brand500: brand || null,
        ratioHtml: ratioWcag(htmlCs.color, htmlCs.backgroundColor),
        ratioBody: ratioWcag(bodyCs.color, bodyCs.backgroundColor),
        componentes: ratios,
      };
      cy.writeFile(`${EVIDENCIA}/G94-rev2-178-ratios-css.json`, snap);
    });

    cy.task('getAxeSource').then((src) => {
      cy.window({ log: false }).then((win) => {
        if (!win.axe) {
          const script = win.document.createElement('script');
          script.text = src;
          win.document.documentElement.appendChild(script);
        }
      });
    });
    cy.window().should('have.property', 'axe');
    cy.window().then((win) => {
      return win.axe.run(win.document, { runOnly: { type: 'rule', values: ['color-contrast'] } });
    }).then((results) => {
      const violations = results.violations || [];
      const axeResumen = {
        fuente: 'axe-core axe.run color-contrast sobre dashboard',
        engine: results.testEngine,
        cantidad_violations: violations.length,
        passes_color_contrast: (results.passes || [])
          .filter((p) => p.id === 'color-contrast')
          .map((p) => ({ id: p.id, nodes: (p.nodes || []).length })),
        violations: violations.map((v) => ({
          id: v.id,
          impact: v.impact,
          description: v.description,
          help: v.help,
          helpUrl: v.helpUrl,
          nodos: extraerContrasteAxe(v.nodes),
        })),
      };
      cy.writeFile(`${EVIDENCIA}/G94-rev2-178-axe.json`, axeResumen);
      const aplicables = [];
      violations.forEach((v) => {
        extraerContrasteAxe(v.nodes).forEach((n) => {
          const expected = n.expectedContrastRatio || 4.5;
          const ratio = n.contrastRatio;
          if (ratio != null && expected >= 4.5 && ratio < 4.5) {
            aplicables.push(n);
          }
        });
      });
      cy.writeFile(`${EVIDENCIA}/G94-rev2-178-axe-aplicables.json`, { n: aplicables.length, nodos: aplicables });
      expect(aplicables, 'violaciones color-contrast texto normal ratio<4.5').to.have.length(0);
    });

    apiGet('/configuracion/personalizacion/tema').then((temaRes) => {
      expect(temaRes.status, 'GET tema resuelto').to.eq(200);
      apiGet('/configuracion/interfaz/contexto').then((res) => {
        cy.writeFile(`${EVIDENCIA}/G94-rev2-178-contexto.json`, {
          http: res.status,
          id_finca: res.body && res.body.id_finca,
          identidad_primary: res.body && res.body.identidad_visual && res.body.identidad_visual.primary_color,
          accesibilidad: res.body && res.body.accesibilidad,
          tema: temaRes.body,
          contexto_browser: contextoBrowser,
        });
        expect(res.status, 'GET /configuracion/interfaz/contexto (Bearer login UI)').to.eq(200);
        cy.get('@dataTheme178').then((dataTheme) => {
          cy.writeFile(`${EVIDENCIA}/G94-rev2-178-tema-ui.json`, {
            data_theme: dataTheme,
            theme_mode: temaRes.body.theme_mode,
            fuente: temaRes.body.fuente,
            id_tema_visual: temaRes.body.id_tema_visual,
            nota: 'Caso historico evaluaba un solo tema (el activo). Admin TEST: theme_mode=1 Claro.',
          });
        });
      });
    });
  });

  it('TC-M09-179 - Variante automatica ante contraste insuficiente', function () {
    if (Cypress.env('solo178')) {
      this.skip();
      return;
    }
    expect(token, 'reutiliza el login de 178 (un intento)').to.be.a('string').and.not.empty;

    apiGet('/configuracion/interfaz/contexto').then((ctxRes) => {
      expect(ctxRes.status, 'GET contexto 179').to.eq(200);
      cy.writeFile(`${EVIDENCIA}/G94-rev2-179-contexto-activo.json`, {
        id_finca_contexto: ctxRes.body && ctxRes.body.id_finca,
        tiene_identidad: Boolean(ctxRes.body && ctxRes.body.identidad_visual),
        nota: 'La finca activa del admin puede no tener identidad; 179 usa GET/PATCH identidad finca 4 (dato real TEST).',
      });
    });

    apiGet(`/configuracion/identidad-visual/${FINCA_IDENTIDAD}`).then((idRes) => {
      expect(idRes.status, 'GET identidad baseline finca 4').to.eq(200);
      expect(idRes.body, 'identidad baseline').to.be.an('object');
      baseline179 = {
        id_finca: idRes.body.id_finca,
        id_identidad_visual: idRes.body.id_identidad_visual,
        primary_color: idRes.body.primary_color,
        secondary_color: idRes.body.secondary_color,
        org_display_name: idRes.body.org_display_name,
        version: idRes.body.version,
        accesibilidad: idRes.body.accesibilidad,
      };
      restaurar179 = true;
      cy.writeFile(`${EVIDENCIA}/G94-rev2-179-baseline.json`, {
        id_finca: baseline179.id_finca,
        primary_color: baseline179.primary_color,
        secondary_color: baseline179.secondary_color,
        org_display_name: baseline179.org_display_name,
        version: baseline179.version,
        accesibilidad: baseline179.accesibilidad,
      });

      cy.request({
        method: 'PATCH',
        url: `${TEST_API}/configuracion/identidad-visual/${baseline179.id_finca}`,
        headers: { Authorization: `Bearer ${token}` },
        form: true,
        body: {
          primary_color: COLOR_BAJO,
          secondary_color: baseline179.secondary_color,
          org_display_name: baseline179.org_display_name,
          version: baseline179.version,
        },
        failOnStatusCode: false,
      }).then((patchRes) => {
        expect(patchRes.status, 'PATCH color de prueba HTTP').to.be.oneOf([200, 201]);
        const acc = patchRes.body && patchRes.body.accesibilidad;
        const claro = acc && acc.primary_color && acc.primary_color.claro;
        expect(claro, 'accesibilidad.primary_color.claro tras PATCH').to.exist;
        expect(String(patchRes.body.primary_color).toUpperCase(), 'almacenado #FFFFFF').to.eq(COLOR_BAJO);
        expect(claro.cumple_aa, 'cumple_aa claro').to.eq(false);
        expect(claro.ratio, 'ratio < 4.5').to.be.lessThan(4.5);
        expect(claro.color_ajustado, 'color_ajustado').to.be.a('string').and.not.empty;
        expect(String(claro.color_ajustado).toUpperCase(), 'ajustado distinto de blanco').to.not.eq(COLOR_BAJO);
        expect(claro.aviso, 'aviso API').to.be.a('string').and.not.empty;

        cy.visit(`${TEST_FRONT}/dashboard`);
        cy.url().should('not.include', '/login');
        cy.document().then((doc) => {
          const cssPrimario =
            doc.documentElement.style.getPropertyValue(CSS_MARCA).trim() ||
            doc.defaultView.getComputedStyle(doc.documentElement).getPropertyValue(CSS_MARCA).trim();
          const aplicado = (cssPrimario || '').replace(/\s/g, '').toUpperCase();
          const ajustado = String(claro.color_ajustado).toUpperCase();
          cy.writeFile(`${EVIDENCIA}/G94-rev2-179-resultado.json`, {
            via: 'PATCH /configuracion/identidad-visual/4 (no CSS del producto)',
            color_enviado: COLOR_BAJO,
            color_almacenado: patchRes.body.primary_color,
            tema_evaluado: 'claro',
            ratio: claro.ratio,
            fondo: claro.fondo,
            cumple_aa: claro.cumple_aa,
            color_ajustado: claro.color_ajustado,
            aviso: claro.aviso,
            css_brand_500: cssPrimario || null,
            css_aplica_ajustado: aplicado === ajustado,
            css_sigue_blanco: aplicado === COLOR_BAJO,
          });
        });
      });
    });
  });
});
