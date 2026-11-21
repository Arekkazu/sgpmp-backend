/**
 * TC-M09-179 rev11 TEST — no modifica ni sobrescribe rev1–rev10.
 *
 * Visual: solo productor@pecuaria.co. Sin GET identidad-visual del admin (ni null ni objeto).
 * Identidad del productor via GET /interfaz/contexto (no RF-26 PATCH).
 * Estímulo: tema personal oscuro (theme_mode=2). PATCH solo si el snapshot no es 2.
 * Restauración: PATCH /personalizacion/tema del productor con login fresco si hubo PATCH.
 * No toca /tema/global ni /identidad-visual. No intercepta identidad.
 *
 * Orden: persistir diagnóstico temprano; esperar CSS --brand-500 === #249453
 * (getComputedStyle(document.documentElement), timeout BRAND_WAIT_MS, reintentos Cypress).
 * Solo entonces medir CSS, ratios (fondos efectivos) y axe. No se fuerza estilo ni DOM.
 *
 * Pendiente de redespliegue de Alex + autorización (NO ejecutar Cypress TEST en esta tarea):
 *   npx cypress run --config-file tests/Test_Testing/Test_Modulo9/RF-27/TC-M09-G94/cypress.config.179.rev11.cjs
 */
const TEST_FRONT = 'https://sigab-frontendtest-6aqrny-d2b730-158-69-200-27.sslip.io';
const TEST_API = 'https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test';
const EVIDENCIA = 'tests/Test_Testing/Test_Modulo9/RF-27/TC-M09-G94/Resultados/rev11';
const PRODUCTOR = 'productor@pecuaria.co';
const FINCA = 1;
const TEMA_OSCURO = 2;
const RATIO_MINIMO_AA = 4.5;
const BRAND_OSCURO_ESPERADO = '#249453';
const TOKENS = [
  '--brand-500',
  '--brand-600',
  '--brand-cta',
  '--brand-cta-hover',
  '--brand-400',
  '--brand-nav',
  '--surface-card',
];

const BRAND_WAIT_MS = 20000;
const SIDEBAR_SELECTORES = [
  '.ds-sidebar__logo-sub',
  '.ds-sidebar__section:nth-child(2) > .ds-sidebar__section-label',
  '.ds-sidebar__section:nth-child(4) > .ds-sidebar__section-label',
  '.ds-sidebar__user-role',
];

describe('TC-M09-179 rev11 TEST', { testIsolation: true }, () => {
  let tokenProd = null;
  let snapTema = null;
  let ajustadoOscuro = null;
  let ajustadoClaro = null;
  let primaryCrudo = null;
  let medicion = null;
  let patchedTema = false;
  let lastStep = 'inicio';
  let axeEjecutado = false;
  const refreshLog = [];
  const temaBrowserLog = [];

  function pass() {
    const c = Cypress.env('contrasena');
    expect(c, 'contrasena via env').to.be.a('string').and.not.empty;
    return c;
  }

  function errorCode(body) {
    if (!body || typeof body !== 'object') return null;
    return body.error_code || body.code || null;
  }

  function redactBody(body) {
    if (!body || typeof body !== 'object') return body;
    const out = Array.isArray(body) ? body.slice() : { ...body };
    if (!Array.isArray(out)) {
      delete out.token;
      delete out.refresh_token;
      delete out.access_token;
    }
    return out;
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

  function relLumaHex(hex) {
    const n = normColor(hex);
    const m = n.match(/^#([0-9A-F]{6})$/);
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
    if (rgba) return rgba.hex;
    const n = normColor(s);
    return /^#[0-9A-F]{6}$/.test(n) ? n : null;
  }

  function fondoEfectivoElemento(el, doc) {
    const win = doc.defaultView;
    let n = el;
    while (n && n.nodeType === 1) {
      const cs = win.getComputedStyle(n);
      const parsed = parseRgba(cs.backgroundColor);
      if (parsed && parsed.hex) {
        return {
          hex: parsed.hex,
          origen: n === el ? 'self' : n.className || n.tagName,
          computed: cs.backgroundColor,
        };
      }
      if (!parsed) {
        const hex = hexRenderizado(cs.backgroundColor);
        if (hex) {
          return {
            hex,
            origen: n === el ? 'self' : n.className || n.tagName,
            computed: cs.backgroundColor,
          };
        }
      }
      n = n.parentElement;
    }
    return { hex: null, origen: 'no_opaco', computed: null };
  }

  function leerBrand500Computed(doc) {
    return String(
      doc.defaultView.getComputedStyle(doc.documentElement).getPropertyValue('--brand-500') || '',
    )
      .trim()
      .toUpperCase();
  }

  function fondoRenderizado(css) {
    const card = css['--surface-card'] || {};
    const desdeCard = hexRenderizado(card.inline || card.computed);
    if (desdeCard) return { hex: desdeCard, origen: 'surface-card' };
    const desdeHtml = hexRenderizado(css.html_background);
    if (desdeHtml) return { hex: desdeHtml, origen: 'html_background' };
    return { hex: null, origen: 'no_renderizado' };
  }

  function leerEstadoTema() {
    return cy.document().then((doc) => {
      const html = doc.documentElement;
      const body = doc.body;
      return {
        origin: doc.location.origin,
        pathname: doc.location.pathname,
        href_sin_query: `${doc.location.origin}${doc.location.pathname}`,
        html_tag: html.tagName,
        html_has_data_theme: html.hasAttribute('data-theme'),
        html_data_theme: html.getAttribute('data-theme'),
        body_tag: body ? body.tagName : null,
        body_has_data_theme: !!(body && body.hasAttribute('data-theme')),
        body_data_theme: body ? body.getAttribute('data-theme') : null,
        html_class: html.className || null,
        ready_state: doc.readyState,
        brand_wait_ms: BRAND_WAIT_MS,
        brand500_computed: leerBrand500Computed(doc),
        brand_oscuro_esperado: BRAND_OSCURO_ESPERADO,
      };
    });
  }

  function leerSidebarNodos() {
    return cy.document().then((doc) => {
      return SIDEBAR_SELECTORES.map((selector) => {
        const el = doc.querySelector(selector);
        if (!el) {
          return { selector, presente: false };
        }
        const cs = doc.defaultView.getComputedStyle(el);
        const fg = hexRenderizado(cs.color);
        const fondo = fondoEfectivoElemento(el, doc);
        return {
          selector,
          presente: true,
          tag: el.tagName,
          texto: String(el.textContent || '').trim().slice(0, 200),
          fg_computed: cs.color || null,
          bg_computed: cs.backgroundColor || null,
          bg_efectivo_computed: fondo.computed,
          bg_efectivo_origen: fondo.origen,
          fg_hex: fg,
          bg_hex: fondo.hex,
          ratio: fg && fondo.hex ? ratioWcagHex(fg, fondo.hex) : null,
          fontSize: cs.fontSize || null,
          fontWeight: cs.fontWeight || null,
        };
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

  function apiProd(method, path, body) {
    return cy.then(() => {
      expect(tokenProd, `token prod ${method} ${path}`).to.be.a('string').and.not.empty;
      const opts = {
        method,
        url: `${TEST_API}${path}`,
        headers: { Authorization: `Bearer ${tokenProd}`, Accept: 'application/json' },
        failOnStatusCode: false,
      };
      if (body) opts.body = body;
      return cy.request(opts);
    });
  }

  function loginProdApi() {
    return cy.request({
      method: 'POST',
      url: `${TEST_API}/sesiones/`,
      headers: { 'Content-Type': 'application/json' },
      body: { correo_electronico: PRODUCTOR, contrasena: pass() },
      failOnStatusCode: false,
    });
  }

  function leerTokens() {
    return cy.document().then((doc) => {
      const cs = doc.defaultView.getComputedStyle(doc.documentElement);
      const inline = doc.documentElement.style;
      const out = {
        data_theme: doc.documentElement.getAttribute('data-theme'),
        html_background: cs.backgroundColor || null,
      };
      TOKENS.forEach((k) => {
        out[k] = {
          inline: (inline.getPropertyValue(k) || '').trim() || null,
          computed: (cs.getPropertyValue(k) || '').trim() || null,
        };
      });
      return out;
    });
  }

  function restoreTema() {
    const informe = {
      omitido: false,
      sonda_token_prod_capturado: null,
      refresh_durante_it: refreshLog,
      login_prod_restore: null,
      patch_tema: null,
      get_tema_final: null,
      coincide_snapshot: null,
    };

    cy.then(() => {
      if (!patchedTema || snapTema == null) {
        informe.omitido = true;
        informe.razon = 'no hubo PATCH de tema personal';
        cy.writeFile(`${EVIDENCIA}/G94-rev11-179-restore.json`, informe);
        return;
      }

      const sonda = tokenProd
        ? cy
            .request({
              method: 'GET',
              url: `${TEST_API}/configuracion/personalizacion/tema`,
              headers: { Authorization: `Bearer ${tokenProd}`, Accept: 'application/json' },
              failOnStatusCode: false,
            })
            .then((r) => {
              informe.sonda_token_prod_capturado = {
                http: r.status,
                error_code: errorCode(r.body),
                message: r.body && r.body.message ? r.body.message : null,
                body_redactado: redactBody(r.body),
              };
            })
        : cy.then(() => {
            informe.sonda_token_prod_capturado = { http: null, nota: 'tokenProd ausente' };
          });

      sonda
        .then(() => loginProdApi())
        .then((loginRes) => {
          informe.login_prod_restore = {
            http: loginRes.status,
            error_code: errorCode(loginRes.body),
          };
          const tok = loginRes.body && loginRes.body.token;
          if (loginRes.status !== 200 || !tok) {
            informe.patch_tema = { http: null, nota: 'login productor restore falló' };
            return;
          }
          return cy
            .request({
              method: 'PATCH',
              url: `${TEST_API}/configuracion/personalizacion/tema`,
              headers: { Authorization: `Bearer ${tok}`, Accept: 'application/json' },
              body: { theme_mode: snapTema },
              failOnStatusCode: false,
            })
            .then((p) => {
              informe.patch_tema = { http: p.status, error_code: errorCode(p.body) };
              return cy.request({
                method: 'GET',
                url: `${TEST_API}/configuracion/personalizacion/tema`,
                headers: { Authorization: `Bearer ${tok}`, Accept: 'application/json' },
                failOnStatusCode: false,
              });
            })
            .then((g) => {
              informe.get_tema_final = {
                http: g.status,
                theme_mode: g.body && g.body.theme_mode,
                fuente: g.body && g.body.fuente,
              };
            });
        })
        .then(() => {
          const ok =
            informe.patch_tema &&
            informe.patch_tema.http === 200 &&
            informe.get_tema_final &&
            informe.get_tema_final.http === 200 &&
            informe.get_tema_final.theme_mode === snapTema;
          informe.coincide_snapshot = { tema: !!ok };
          cy.writeFile(`${EVIDENCIA}/G94-rev11-179-restore.json`, informe);
          cy.writeFile(`${EVIDENCIA}/G94-rev11-179-verificacion-final.json`, {
            snapshot_theme_mode: snapTema,
            get_tema_final: informe.get_tema_final,
            coincide_snapshot: informe.coincide_snapshot,
            sonda_token_prod_capturado: informe.sonda_token_prod_capturado,
            refresh_durante_it: informe.refresh_durante_it,
          });
          expect(informe.patch_tema && informe.patch_tema.http, 'restore theme_mode HTTP').to.eq(200);
          expect(informe.coincide_snapshot.tema, 'GET tema final = snapshot').to.eq(true);
        });
    });
  }

  after(function () {
    restoreTema();
  });

  afterEach(function () {
    const err = this.currentTest && this.currentTest.err;
    const axeInfo = {
      ejecutado: axeEjecutado,
      violations: medicion && medicion.axe_violations != null ? medicion.axe_violations : null,
      nota: axeEjecutado
        ? 'axe color-contrast se ejecutó y se persistió G94-rev11-179-axe.json'
        : 'axe no se ejecutó; no hay violaciones que reportar como 0',
    };
    cy.writeFile(`${EVIDENCIA}/G94-rev11-179-ultimo-paso.json`, {
      last_step: lastStep,
      mocha_state: this.currentTest ? this.currentTest.state : null,
      mocha_error: err && err.message ? String(err.message) : null,
      refresh_log: refreshLog,
      tema_browser_log: temaBrowserLog,
      patched_tema: patchedTema,
      axe: axeInfo,
      pathname: medicion && medicion.pathname,
      data_theme: medicion && medicion.data_theme,
      brand500_normalizado: medicion && medicion.brand500_normalizado,
      esperado_ajustado_oscuro: medicion && medicion.esperado_ajustado_oscuro,
      coincide_oscuro: medicion && medicion.coincide_oscuro,
    });
    leerEstadoTema().then((estado) => {
      cy.writeFile(`${EVIDENCIA}/G94-rev11-179-estado-tema-final.json`, {
        last_step: lastStep,
        mocha_state: this.currentTest ? this.currentTest.state : null,
        mocha_error: err && err.message ? String(err.message) : null,
        ...estado,
        nota:
          estado.html_data_theme === 'dark'
            ? 'html data-theme=dark al cerrar el it'
            : 'html sin data-theme=dark al cerrar el it; no se asume tema oscuro',
      });
    });
    if (!axeEjecutado) {
      cy.writeFile(`${EVIDENCIA}/G94-rev11-179-axe.json`, {
        ejecutado: false,
        last_step: lastStep,
        violations: null,
        nota: 'axe no alcanzó a correr; no se declara color-contrast = 0',
      });
    }
  });

  it('TC-M09-179 aplica color_ajustado oscuro en --brand-500 con data-theme=dark', function () {
    const contrasena = pass();

    cy.intercept({ method: 'GET', url: /\/configuracion\/interfaz\/contexto\/?$/ }).as('ctx');
    cy.intercept({ method: 'POST', url: /\/sesiones\/?$/ }).as('loginProd');
    cy.intercept({ method: 'POST', url: /\/sesiones\/refresh\/?$/ }, (req) => {
      req.continue((res) => {
        const body = res.body && typeof res.body === 'object' ? res.body : {};
        refreshLog.push({
          http: res.statusCode,
          error_code: body.error_code || body.code || null,
        });
      });
    }).as('refreshSesion');
    cy.intercept({ method: 'GET', url: /\/configuracion\/personalizacion\/tema\/?$/ }, (req) => {
      req.continue((res) => {
        const body = res.body && typeof res.body === 'object' ? res.body : {};
        temaBrowserLog.push({
          http: res.statusCode,
          error_code: body.error_code || body.code || null,
        });
      });
    }).as('getTemaBrowser');

    cy.visit(`${TEST_FRONT}/login`);
    cy.get('input[type="email"]').clear().type(PRODUCTOR);
    cy.get('input[type="password"]').clear().type(contrasena, { log: false });
    cy.get('button[type="submit"]').contains(/ingresar/i).click();
    cy.wait('@loginProd').then((intc) => {
      expect(intc.response.statusCode, 'login productor UI').to.eq(200);
      tokenProd = intc.response.body.token;
      lastStep = 'login_prod_ui';
    });
    cy.url({ timeout: 20000 })
      .should('include', '/dashboard')
      .then(() => {
        lastStep = 'dashboard';
      });

    apiProd('GET', '/configuracion/personalizacion/tema').then((tRes) => {
      expect(tRes.status, 'GET tema snapshot').to.eq(200);
      snapTema = tRes.body.theme_mode;
      cy.writeFile(`${EVIDENCIA}/G94-rev11-179-snapshot-tema.json`, {
        theme_mode: tRes.body.theme_mode,
        fuente: tRes.body.fuente,
        id_tema_visual: tRes.body.id_tema_visual,
      });
      expect(tRes.body.fuente, 'fuente tema personal').to.eq('personal');
      lastStep = 'snapshot_tema';
    });

    apiProd('GET', '/configuracion/interfaz/contexto').then((ctx) => {
      expect(ctx.status, 'GET contexto').to.eq(200);
      expect(ctx.body.id_usuario).to.eq(2);
      expect(ctx.body.id_finca, 'finca productor').to.eq(FINCA);
      expect(ctx.body.identidad_visual).to.be.an('object');
      primaryCrudo = normColor(ctx.body.identidad_visual.primary_color);
      const oscuro = ctx.body.accesibilidad && ctx.body.accesibilidad.primary_color && ctx.body.accesibilidad.primary_color.oscuro;
      expect(oscuro, 'bloque accesibilidad oscuro').to.be.an('object');
      expect(oscuro.cumple_aa, 'precondición oscuro cumple_aa false').to.eq(false);
      ajustadoOscuro = normColor(oscuro.color_ajustado);
      ajustadoClaro = normColor(ctx.body.accesibilidad.primary_color.claro.color_ajustado);
      expect(ajustadoOscuro, 'color_ajustado oscuro').to.match(/^#[0-9A-F]{6}$/);
      expect(ajustadoOscuro, 'variante distinta del primario crudo').to.not.eq(primaryCrudo);
      cy.writeFile(`${EVIDENCIA}/G94-rev11-179-contexto-antes.json`, {
        id_usuario: ctx.body.id_usuario,
        id_finca: ctx.body.id_finca,
        identidad_visual: ctx.body.identidad_visual,
        accesibilidad_primary_oscuro: oscuro,
        accesibilidad_primary_claro: ctx.body.accesibilidad.primary_color.claro,
        brand_oscuro_esperado_css: BRAND_OSCURO_ESPERADO,
        color_ajustado_api: ajustadoOscuro,
      });
      lastStep = 'contexto';
    });

    apiProd('GET', '/configuracion/personalizacion/tema').then((tRes) => {
      if (tRes.body.theme_mode === TEMA_OSCURO) {
        lastStep = 'tema_sin_patch';
        cy.writeFile(`${EVIDENCIA}/G94-rev11-179-tema-sin-patch.json`, {
          theme_mode: tRes.body.theme_mode,
          nota: 'Ya estaba en oscuro; no se PATCH para no alterar innecesariamente.',
        });
        return;
      }
      return apiProd('PATCH', '/configuracion/personalizacion/tema', { theme_mode: TEMA_OSCURO }).then((p) => {
        expect(p.status, 'PATCH tema personal = 2').to.eq(200);
        patchedTema = true;
        return apiProd('GET', '/configuracion/personalizacion/tema').then((g) => {
          expect(g.body.theme_mode, 'GET tema tras PATCH').to.eq(TEMA_OSCURO);
          lastStep = 'tema_tras_patch';
          cy.writeFile(`${EVIDENCIA}/G94-rev11-179-tema-tras-patch.json`, {
            theme_mode: g.body.theme_mode,
            fuente: g.body.fuente,
          });
        });
      });
    });

    cy.then(() => {
      if (patchedTema) {
        lastStep = 'reload_tras_patch';
        cy.reload();
      }
    });
    cy.url().should('include', '/dashboard');

    leerEstadoTema().then((temprano) => {
      lastStep = 'diagnostico_temprano';
      return cy.writeFile(`${EVIDENCIA}/G94-rev11-179-diagnostico-temprano.json`, {
        ...temprano,
        refresh_log: refreshLog,
        tema_browser_log: temaBrowserLog,
        nota: `Snapshot antes de esperar --brand-500 === ${BRAND_OSCURO_ESPERADO} (${BRAND_WAIT_MS} ms). No se fuerza CSS ni DOM.`,
      });
    });

    cy.document({ timeout: BRAND_WAIT_MS }).should((doc) => {
      const observado = leerBrand500Computed(doc);
      const theme = doc.documentElement.getAttribute('data-theme');
      const url = `${doc.location.origin}${doc.location.pathname}`;
      expect(
        observado,
        `--brand-500 debe ser ${BRAND_OSCURO_ESPERADO} en ${BRAND_WAIT_MS}ms (observado=${observado || '(vacío)'}, data-theme=${theme === null ? 'null' : theme}, url=${url}, timeout=${BRAND_WAIT_MS}ms). Ver diagnostico-temprano.json. No se fuerza CSS.`,
      ).to.eq(BRAND_OSCURO_ESPERADO);
    });
    cy.then(() => {
      lastStep = 'brand_confirmado';
    });

    cy.location('pathname').then((pathname) => {
      return leerTokens().then((css) => {
        return leerSidebarNodos().then((sidebar) => {
          const aplicado = hexRenderizado(css['--brand-500'].inline || css['--brand-500'].computed);
          const fondo = fondoRenderizado(css);
          const ratioMarca = aplicado && fondo.hex ? ratioWcagHex(aplicado, fondo.hex) : null;
          medicion = {
            pathname,
            data_theme: css.data_theme,
            brand500_inline: css['--brand-500'].inline,
            brand500_computed: css['--brand-500'].computed,
            brand500_normalizado: aplicado,
            fondo_normalizado: fondo.hex,
            fondo_origen: fondo.origen,
            ratio_brand_vs_fondo: ratioMarca,
            ratio_api_oscuro_no_usado: true,
            primary_crudo: primaryCrudo,
            esperado_ajustado_oscuro: ajustadoOscuro,
            ajustado_claro: ajustadoClaro,
            coincide_oscuro: aplicado === ajustadoOscuro,
            coincide_crudo: aplicado === primaryCrudo,
            coincide_claro: aplicado === ajustadoClaro,
            sidebar,
            axe_violations: null,
          };
          lastStep = 'css_capturado';
          const diagnostico = {
            ...medicion,
            css,
            ratio_minimo_aa: RATIO_MINIMO_AA,
            refresh_log: refreshLog,
            tema_browser_log: temaBrowserLog,
          };
          return cy
            .writeFile(`${EVIDENCIA}/G94-rev11-179-diagnostico.json`, diagnostico)
            .then(() =>
              cy.writeFile(`${EVIDENCIA}/G94-rev11-179-ubicacion.json`, {
                pathname,
                data_theme: css.data_theme,
                brand500_normalizado: aplicado,
                nota: `Persistido tras --brand-500 === ${BRAND_OSCURO_ESPERADO} y antes de aserciones.`,
              }),
            )
            .then(() =>
              cy.writeFile(`${EVIDENCIA}/G94-rev11-179-css-despues.json`, {
                ...css,
                pathname,
                primary_crudo: primaryCrudo,
                esperado_ajustado: ajustadoOscuro,
                brand500_normalizado: aplicado,
                fondo_normalizado: fondo.hex,
                fondo_origen: fondo.origen,
                ratio_brand_vs_fondo: ratioMarca,
                ratio_minimo_aa: RATIO_MINIMO_AA,
                refresh_count: refreshLog.length,
              }),
            )
            .then(() =>
              cy.writeFile(`${EVIDENCIA}/G94-rev11-179-sidebar-nodos.json`, {
                nodos: sidebar,
                ratio_minimo_aa: RATIO_MINIMO_AA,
              }),
            )
            .then(() => {
              lastStep = 'diagnostico_persistido';
            });
        });
      });
    });

    cy.screenshot('G94-rev11-179-dashboard-dark-variante');

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
          .writeFile(`${EVIDENCIA}/G94-rev11-179-axe.json`, {
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

    cy.writeFile(`${EVIDENCIA}/G94-rev11-179-refresh.json`, {
      llamadas: refreshLog,
      tema_browser: temaBrowserLog,
    });

    cy.then(() => {
      lastStep = 'aserciones';
      expect(medicion, 'medición CSS persistida').to.be.an('object');
      expect(medicion.data_theme, 'data-theme=dark').to.eq('dark');
      expect(medicion.brand500_normalizado, '--brand-500 presente y hex').to.match(/^#[0-9A-F]{6}$/);
      expect(medicion.fondo_origen, 'fondo CSS renderizado (no constante de API)').to.be.oneOf([
        'surface-card',
        'html_background',
      ]);
      expect(medicion.brand500_normalizado, '--brand-500 = #249453 (criterio de espera)').to.eq(
        BRAND_OSCURO_ESPERADO,
      );
      expect(medicion.brand500_normalizado, '--brand-500 = color_ajustado oscuro API').to.eq(
        medicion.esperado_ajustado_oscuro,
      );
      expect(medicion.ratio_brand_vs_fondo, 'ratio WCAG --brand-500 vs superficie >= 4.5').to.be.a('number');
      expect(medicion.ratio_brand_vs_fondo, 'ratio WCAG --brand-500 vs superficie >= 4.5').to.be.at.least(
        RATIO_MINIMO_AA,
      );
      expect(axeEjecutado, 'axe se ejecutó').to.eq(true);
      expect(medicion.axe_violations, 'axe color-contrast violations').to.eq(0);
      expect(medicion.sidebar, 'cuatro nodos sidebar').to.be.an('array').and.have.length(4);
      medicion.sidebar.forEach((nodo) => {
        expect(nodo.presente, `sidebar presente ${nodo.selector}`).to.eq(true);
        expect(nodo.ratio, `sidebar ratio número ${nodo.selector}`).to.be.a('number');
        expect(nodo.ratio, `sidebar ratio >= 4.5 ${nodo.selector}`).to.be.at.least(RATIO_MINIMO_AA);
      });
    });
  });
});
