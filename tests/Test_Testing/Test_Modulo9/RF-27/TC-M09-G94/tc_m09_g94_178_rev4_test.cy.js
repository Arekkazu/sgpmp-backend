/**
 * TC-M09-178 rev4 TEST — contraste mínimo WCAG 4.5:1 del tema activo (dashboard).
 * No modifica ni sobrescribe rev1–rev3 ni evidencias 178-rev3.
 *
 * Causa rev3: apiGetLectura hacía expect(tokenAdmin) de forma síncrona al evaluar el it,
 * antes de cy.wait('@loginAdmin'). Aquí el GET autenticado solo se encola con cy.then()
 * después del login y de un token no vacío.
 *
 * Alcance: admin, dashboard, tema activo. Sin PATCH. Sin exigir --brand-500=#249453.
 *
 * Pendiente de autorización (NO ejecutar Cypress TEST en esta tarea):
 *   npx cypress run --config-file tests/Test_Testing/Test_Modulo9/RF-27/TC-M09-G94/cypress.config.178.rev4.cjs
 */
const TEST_FRONT = 'https://sigab-frontendtest-6aqrny-d2b730-158-69-200-27.sslip.io';
const TEST_API = 'https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test';
const EVIDENCIA = 'tests/Test_Testing/Test_Modulo9/RF-27/TC-M09-G94/Resultados/178-rev4';
const ADMIN = 'admin@pecuaria.co';
const RATIO_MINIMO_AA = 4.5;
const SIDEBAR_SELECTORES = [
  '.ds-sidebar__logo-sub',
  '.ds-sidebar__section:nth-child(2) > .ds-sidebar__section-label',
  '.ds-sidebar__section:nth-child(4) > .ds-sidebar__section-label',
  '.ds-sidebar__user-role',
];

describe('TC-M09-178 rev4 TEST', { testIsolation: true }, () => {
  let lastStep = 'inicio';
  let axeEjecutado = false;
  let medicion = null;
  let tokenAdmin = null;

  function pass() {
    const c = Cypress.env('contrasena');
    expect(c, 'contrasena via env').to.be.a('string').and.not.empty;
    return c;
  }

  function parseRgba(val) {
    const m = String(val || '').match(
      /rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)(?:\s*,\s*([0-9.]+))?\s*\)/i,
    );
    if (!m) return null;
    const a = m[4] == null ? 1 : Number(m[4]);
    if (!(a > 0)) return { hex: null, transparente: true };
    return {
      hex: (
        '#' +
        [m[1], m[2], m[3]]
          .map((n) => Number(n).toString(16).padStart(2, '0'))
          .join('')
          .toUpperCase()
      ),
      transparente: false,
    };
  }

  function hexRenderizado(val) {
    const s = String(val || '').trim();
    if (/^#[0-9A-Fa-f]{6}$/.test(s)) return s.toUpperCase();
    const rgba = parseRgba(s);
    return rgba ? rgba.hex : null;
  }

  function relLumaHex(hex) {
    const n = hexRenderizado(hex);
    const m = String(n || '').match(/^#([0-9A-F]{6})$/);
    if (!m) return null;
    const raw = m[1];
    const ch = [0, 2, 4].map((i) => {
      const c = parseInt(raw.slice(i, i + 2), 16) / 255;
      return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
    });
    return 0.2126 * ch[0] + 0.7152 * ch[1] + 0.0722 * ch[2];
  }

  function ratioWcagHex(a, b) {
    const la = relLumaHex(a);
    const lb = relLumaHex(b);
    if (la == null || lb == null) return null;
    const hi = Math.max(la, lb);
    const lo = Math.min(la, lb);
    return (hi + 0.05) / (lo + 0.05);
  }

  function fondoEfectivo(el, doc) {
    let n = el;
    while (n && n.nodeType === 1) {
      const cs = doc.defaultView.getComputedStyle(n);
      const parsed = parseRgba(cs.backgroundColor);
      if (parsed && parsed.hex) {
        return { hex: parsed.hex, origen: n === el ? 'self' : n.className || n.tagName };
      }
      if (!parsed || parsed.transparente) {
        const hex = hexRenderizado(cs.backgroundColor);
        if (hex) {
          return { hex, origen: n === el ? 'self' : n.className || n.tagName };
        }
      }
      n = n.parentElement;
    }
    return { hex: null, origen: 'no_opaco' };
  }

  /** Encola el GET. El expect del token corre dentro de cy.then, nunca al evaluar el it. */
  function apiGetLectura(path) {
    return cy.then(() => {
      const tok = tokenAdmin;
      expect(
        tok,
        `token GET ${path}: debe existir tras login (observado=${tok == null ? 'null' : typeof tok}). No se envía Authorization vacío.`,
      )
        .to.be.a('string')
        .and.not.empty;
      return cy.request({
        method: 'GET',
        url: `${TEST_API}${path}`,
        headers: { Authorization: `Bearer ${tok}`, Accept: 'application/json' },
        failOnStatusCode: false,
        log: false,
      });
    });
  }

  function extraerNodosAxe(nodes) {
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

  afterEach(function () {
    const err = this.currentTest && this.currentTest.err;
    cy.writeFile(`${EVIDENCIA}/G94-178-rev4-ultimo-paso.json`, {
      last_step: lastStep,
      mocha_state: this.currentTest ? this.currentTest.state : null,
      mocha_error: err && err.message ? String(err.message) : null,
      axe_ejecutado: axeEjecutado,
      axe_violations: medicion && medicion.axe_violations,
      token_presente: typeof tokenAdmin === 'string' && tokenAdmin.length > 0,
    });
    if (!axeEjecutado) {
      cy.writeFile(`${EVIDENCIA}/G94-178-rev4-axe.json`, {
        ejecutado: false,
        last_step: lastStep,
        violations: null,
        nota: 'axe no alcanzó a correr; no se declara color-contrast = 0',
      });
    }
  });

  it('TC-M09-178 verifica contraste minimo WCAG 4.5:1 en dashboard (tema activo)', function () {
    const contrasena = pass();

    cy.intercept({ method: 'POST', url: /\/sesiones\/?$/ }).as('loginAdmin');

    cy.visit(`${TEST_FRONT}/login`);
    cy.get('input[type="email"]').clear().type(ADMIN);
    cy.get('input[type="password"]').clear().type(contrasena, { log: false });
    cy.get('button[type="submit"]').contains(/ingresar/i).click();
    cy.wait('@loginAdmin', { log: false }).then((intc) => {
      const http = intc.response && intc.response.statusCode;
      const tok = intc.response && intc.response.body && intc.response.body.token;
      return cy
        .writeFile(`${EVIDENCIA}/G94-178-rev4-login.json`, {
          http,
          token_presente: typeof tok === 'string' && tok.length > 0,
          nota: 'Sin cuerpo de sesión ni token. Solo lectura posterior.',
        })
        .then(() => {
          expect(http, `login admin UI HTTP (observado=${http == null ? 'null' : http})`).to.eq(200);
          expect(
            tok,
            `token admin tras login HTTP ${http} (observado=${tok == null ? 'null' : typeof tok})`,
          )
            .to.be.a('string')
            .and.not.empty;
          tokenAdmin = tok;
          lastStep = 'login_admin_ui';
        });
    });
    cy.url({ timeout: 20000 })
      .should('include', '/dashboard')
      .and('not.include', '/login')
      .then(() => {
        lastStep = 'dashboard';
      });

    cy.then(() => {
      expect(
        tokenAdmin,
        `token antes de GET autenticados (last_step=${lastStep}, observado=${
          tokenAdmin == null ? 'null' : typeof tokenAdmin
        }). No se continúa sin token.`,
      )
        .to.be.a('string')
        .and.not.empty;
    });

    apiGetLectura('/configuracion/personalizacion/tema').then((temaRes) => {
      expect(temaRes.status, 'GET tema (solo lectura)').to.eq(200);
      return apiGetLectura('/configuracion/interfaz/contexto').then((ctxRes) => {
        expect(ctxRes.status, 'GET contexto (solo lectura)').to.eq(200);
        lastStep = 'api_lectura';
        return cy.writeFile(`${EVIDENCIA}/G94-178-rev4-contexto.json`, {
          tema: {
            theme_mode: temaRes.body && temaRes.body.theme_mode,
            fuente: temaRes.body && temaRes.body.fuente,
          },
          id_finca: ctxRes.body && ctxRes.body.id_finca,
          identidad_primary:
            ctxRes.body && ctxRes.body.identidad_visual && ctxRes.body.identidad_visual.primary_color,
          accesibilidad_primary:
            ctxRes.body && ctxRes.body.accesibilidad && ctxRes.body.accesibilidad.primary_color,
          nota: 'Solo lectura. No se PATCH tema ni identidad. No se exige body null.',
        });
      });
    });

    cy.document().then((doc) => {
      const html = doc.documentElement;
      const brand = String(
        doc.defaultView.getComputedStyle(html).getPropertyValue('--brand-500') || '',
      )
        .trim()
        .toUpperCase();
      const sidebar = SIDEBAR_SELECTORES.map((selector) => {
        const el = doc.querySelector(selector);
        if (!el) return { selector, presente: false };
        const cs = doc.defaultView.getComputedStyle(el);
        const fg = hexRenderizado(cs.color);
        const fondo = fondoEfectivo(el, doc);
        return {
          selector,
          presente: true,
          texto: String(el.textContent || '').trim().slice(0, 200),
          fg_hex: fg,
          bg_hex: fondo.hex,
          bg_origen: fondo.origen,
          ratio: fg && fondo.hex ? ratioWcagHex(fg, fondo.hex) : null,
          fontSize: cs.fontSize,
        };
      });
      medicion = {
        pathname: doc.location.pathname,
        html_data_theme: html.getAttribute('data-theme'),
        brand500_computed: brand || null,
        sidebar,
        axe_violations: null,
      };
      lastStep = 'css_capturado';
      return cy
        .writeFile(`${EVIDENCIA}/G94-178-rev4-diagnostico.json`, {
          ...medicion,
          ratio_minimo_aa: RATIO_MINIMO_AA,
          nota: 'Tema activo del admin. No se fuerza data-theme ni --brand-500.',
        })
        .then(() => cy.writeFile(`${EVIDENCIA}/G94-178-rev4-sidebar-nodos.json`, { nodos: sidebar }));
    });

    cy.screenshot('G94-178-rev4-dashboard');

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
        const viol = (results.violations || []).filter((v) => v.id === 'color-contrast');
        const cc = (results.passes || []).find((p) => p.id === 'color-contrast');
        if (medicion) medicion.axe_violations = viol.length;
        lastStep = 'axe_persistido';
        return cy
          .writeFile(`${EVIDENCIA}/G94-178-rev4-axe.json`, {
            ejecutado: true,
            violations: viol.length,
            violation_ids: viol.map((v) => v.id),
            color_contrast_pass_nodes: cc ? (cc.nodes || []).length : 0,
            violation_nodes: viol.length ? extraerNodosAxe(viol[0].nodes) : [],
          })
          .then(() => {
            axeEjecutado = true;
          });
      });

    cy.then(() => {
      lastStep = 'aserciones';
      expect(axeEjecutado, 'axe se ejecutó').to.eq(true);
      expect(medicion, 'medición persistida').to.be.an('object');
      expect(medicion.pathname, 'dashboard').to.eq('/dashboard');
      expect(medicion.axe_violations, 'axe color-contrast violations').to.eq(0);
      expect(medicion.sidebar, 'cuatro nodos sidebar').to.be.an('array').and.have.length(4);
      medicion.sidebar.forEach((nodo) => {
        expect(nodo.presente, `sidebar presente ${nodo.selector}`).to.eq(true);
        expect(nodo.ratio, `sidebar ratio ${nodo.selector}`).to.be.a('number');
        expect(nodo.ratio, `sidebar AA ${nodo.selector}`).to.be.at.least(RATIO_MINIMO_AA);
      });
    });
  });
});
