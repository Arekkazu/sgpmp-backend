/**
 * TC-M09-G94 — Contraste mínimo WCAG y variante automática (RF-27).
 *
 *   TC-M09-178 — axe color-contrast en UI + accesibilidad del contexto (identidad)
 *   TC-M09-179 — guardar #FFFFFF (bajo contraste en claro) y comprobar color_ajustado en CSS
 *
 * Ejecutar contra DEV:
 *   npx cypress run --spec tests/Test_Testing/Test_Modulo9/RF-27/TC-M09-G94/tc_m09_g94.cy.js --env correo=admin.dev@gmail.com,contrasena=***
 *
 * Color de prueba 179: #FFFFFF sobre fondo claro #FFFFFF (tests/configuration/test_rf26_rf27_contraste_wcag.py).
 */
const DEV_FRONT = 'https://sigab-frontenddev-pbw0py-757e2f-158-69-200-27.sslip.io';
const DEV_API = 'https://sigab-backenddev-jpuya4-ea3a74-158-69-200-27.sslip.io/api-sgpmp';
const EVIDENCIA = 'tests/Test_Testing/Test_Modulo9/RF-27/TC-M09-G94/Resultados';
const COLOR_BAJO_CONTRASTE = '#FFFFFF';
const CSS_MARCA_PRIMARIA = '--brand-500';

describe('TC-M09-G94 - Contraste mínimo y variante automática', () => {
  let token = null;
  let baseline179 = null;
  let restaurar179 = false;

  function credenciales() {
    const correo = Cypress.env('correo') || 'admin.dev@gmail.com';
    const contrasena = Cypress.env('contrasena');
    expect(contrasena, 'contrasena via Cypress.env (no hardcodear)').to.be.a('string').and.not.empty;
    return { correo, contrasena };
  }

  function interceptarRefresh() {
    cy.intercept({ method: 'POST', url: /\/sesiones\/refresh\/?$/ }).as('refreshSesion');
  }

  function loginDev() {
    const { correo, contrasena } = credenciales();
    interceptarRefresh();
    cy.intercept({ method: 'POST', url: /\/sesiones\/?$/ }).as('login');
    cy.visit(`${DEV_FRONT}/login`);
    cy.get('input[type="email"]').should('be.visible').clear().type(correo);
    cy.get('input[type="password"]').should('be.visible').clear().type(contrasena, { log: false });
    cy.get('button[type="submit"]').contains(/ingresar/i).click();
    cy.wait('@login').then((interception) => {
      expect(interception.response && interception.response.statusCode, 'login HTTP').to.eq(200);
      token = interception.response.body && interception.response.body.token;
      expect(token, 'token de sesión').to.be.a('string').and.not.empty;
    });
    cy.url({ timeout: 20000 }).should('include', '/dashboard');
    cy.url().should('not.include', '/login');
  }

  function apiGet(path) {
    return cy.request({
      method: 'GET',
      url: `${DEV_API}${path}`,
      headers: { Authorization: `Bearer ${token}` },
      failOnStatusCode: false,
    });
  }

  function temaActivoDesdeDom(dataTheme) {
    return dataTheme === 'dark' ? 'oscuro' : 'claro';
  }

  function accesibilidadColor(accesibilidad, campo, tema) {
    if (!accesibilidad || !accesibilidad[campo]) {
      return null;
    }
    return accesibilidad[campo][tema] || null;
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
        expectedContrastRatio: data.expectedContrastRatio || null,
      };
    });
  }

  function irAIdentidadVisual() {
    interceptarRefresh();
    cy.visit(`${DEV_FRONT}/configuracion`);
    cy.wait(500);
    cy.get('body').then(($body) => {
      const url = $body[0].ownerDocument.location.href;
      if (/\/login/.test(url)) {
        cy.writeFile(
          `${EVIDENCIA}/G94-bloqueo-sesion.txt`,
          [
            'BLOQUEADO por ambiente/sesión (no es defecto de contraste RF-27).',
            'Tras visitar /configuracion la URL volvió a /login.',
            'Revisar POST /sesiones/refresh (incidente G90: HTTP 500).',
          ].join('\n')
        );
        return 'login';
      }
      return 'ok';
    });
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
        url: `${DEV_API}/configuracion/identidad-visual/${baseline179.id_finca}`,
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
        expect(patchRes.status, 'PATCH restauración identidad HTTP').to.be.oneOf([200, 201]);
      });
    });
    apiGet(`/configuracion/identidad-visual/${baseline179.id_finca}`).then((res) => {
      expect(res.status, 'GET identidad tras restaurar').to.eq(200);
      expect(String(res.body.primary_color).toUpperCase(), 'primary_color restaurado').to.eq(
        String(baseline179.primary_color).toUpperCase()
      );
      expect(String(res.body.secondary_color).toUpperCase(), 'secondary_color restaurado').to.eq(
        String(baseline179.secondary_color).toUpperCase()
      );
      expect(res.body.org_display_name, 'org_display_name restaurado').to.eq(baseline179.org_display_name);
      cy.writeFile(`${EVIDENCIA}/G94-179-restauracion.json`, {
        primary_color: res.body.primary_color,
        secondary_color: res.body.secondary_color,
        org_display_name: res.body.org_display_name,
        version: res.body.version,
        id_finca: res.body.id_finca,
      });
    });
  });

  it('TC-M09-178 - Verificar contraste mínimo WCAG 4.5:1', function () {
    loginDev();
    cy.screenshot('G94-178-01-dashboard');

    cy.document().then((doc) => {
      const dataTheme = doc.documentElement.getAttribute('data-theme') || 'light';
      cy.wrap(dataTheme).as('dataTheme178');
    });

    cy.injectAxe();
    cy.checkA11y(
      null,
      {
        runOnly: ['color-contrast'],
      },
      (violations) => {
        const axeResumen = {
          fuente: 'A. axe color-contrast sobre la interfaz renderizada',
          cantidad_violations: violations.length,
          violations: violations.map((v) => ({
            id: v.id,
            impact: v.impact,
            description: v.description,
            help: v.help,
            helpUrl: v.helpUrl,
            nodos: extraerContrasteAxe(v.nodes),
          })),
        };
        cy.writeFile(`${EVIDENCIA}/G94-178-axe.json`, axeResumen);
        if (violations.length > 0) {
          throw new Error(
            `TC-M09-178 FAIL (axe): ${violations.length} violation(s) color-contrast. Ver G94-178-axe.json`
          );
        }
      }
    );

    apiGet('/configuracion/interfaz/contexto').then((res) => {
      expect(res.status, 'GET /configuracion/interfaz/contexto').to.eq(200);
      cy.get('@dataTheme178').then((dataTheme) => {
        cy.document().then((doc) => {
        const tema = temaActivoDesdeDom(dataTheme);
        const acc = res.body.accesibilidad || null;
        const primario = accesibilidadColor(acc, 'primary_color', tema);
        const secundario = accesibilidadColor(acc, 'secondary_color', tema);
        const cssPrimario = (
          doc.documentElement.style.getPropertyValue(CSS_MARCA_PRIMARIA) ||
          doc.defaultView.getComputedStyle(doc.documentElement).getPropertyValue(CSS_MARCA_PRIMARIA)
        ).trim();

        const contextoResumen = {
          fuente: 'B. accesibilidad de identidad visual (GET /configuracion/interfaz/contexto)',
          endpoint: 'GET /configuracion/interfaz/contexto',
          data_theme: dataTheme,
          tema_evaluado: tema,
          id_finca: res.body.id_finca,
          identidad_primary_color: res.body.identidad_visual && res.body.identidad_visual.primary_color,
          primario,
          secundario,
          css_brand_500: cssPrimario || null,
          nota:
            'cumple_aa=false no implica FAIL de producto si el CSS aplica color_ajustado. Axe (A) es independiente.',
        };
        cy.writeFile(`${EVIDENCIA}/G94-178-contexto.json`, contextoResumen);

        if (primario && primario.cumple_aa === false && primario.color_ajustado) {
          const aplicado = (cssPrimario || '').replace(/\s/g, '').toUpperCase();
          const ajustado = String(primario.color_ajustado).toUpperCase();
          const original = String(
            (res.body.identidad_visual && res.body.identidad_visual.primary_color) || ''
          ).toUpperCase();
          if (aplicado && ajustado && aplicado !== ajustado && aplicado === original) {
            throw new Error(
              'TC-M09-178 FAIL: cumple_aa=false y el CSS de marca sigue el hex original, no color_ajustado.'
            );
          }
        }
        });
      });
    });
  });

  it('TC-M09-179 - Aplicar variante automática ante contraste insuficiente', function () {
    loginDev();

    apiGet('/configuracion/personalizacion/tema').then((temaRes) => {
      const themeMode = temaRes.status === 200 ? temaRes.body.theme_mode : null;
      apiGet('/configuracion/interfaz/contexto').then((ctxRes) => {
        expect(ctxRes.status, 'GET contexto baseline').to.eq(200);
        const idFinca = ctxRes.body.id_finca;
        if (!idFinca) {
          cy.writeFile(
            `${EVIDENCIA}/G94-179-diagnostico.txt`,
            'BLOQUEADO: el contexto no trae id_finca. No se modifica identidad.'
          );
          this.skip();
          return;
        }
        apiGet(`/configuracion/identidad-visual/${idFinca}`).then((idRes) => {
          expect(idRes.status, 'GET identidad baseline').to.eq(200);
          expect(idRes.body, 'identidad baseline').to.be.an('object');
          baseline179 = {
            id_finca: idRes.body.id_finca,
            id_identidad_visual: idRes.body.id_identidad_visual,
            primary_color: idRes.body.primary_color,
            secondary_color: idRes.body.secondary_color,
            org_display_name: idRes.body.org_display_name,
            version: idRes.body.version,
            theme_mode: themeMode,
            accesibilidad: idRes.body.accesibilidad,
          };
          restaurar179 = true;
          cy.writeFile(`${EVIDENCIA}/G94-179-baseline.json`, {
            id_finca: baseline179.id_finca,
            id_identidad_visual: baseline179.id_identidad_visual,
            primary_color: baseline179.primary_color,
            secondary_color: baseline179.secondary_color,
            org_display_name: baseline179.org_display_name,
            version: baseline179.version,
            theme_mode: baseline179.theme_mode,
            accesibilidad: baseline179.accesibilidad,
          });
          irAIdentidadVisual();
        });
      });
    });
    cy.url().then((url) => {
      if (/\/login/.test(url)) {
        this.skip();
      }
    });

    cy.get('body').then(($body) => {
      if (!/Identidad Visual/i.test($body.text())) {
        cy.writeFile(
          `${EVIDENCIA}/G94-179-diagnostico.txt`,
          'BLOQUEADO: no hay sección Identidad Visual en DEV. No es un FAIL de variante automática.'
        );
        this.skip();
      }
    });

    cy.contains('h1, h2, button', /Configuración/i, { timeout: 15000 }).should('exist');
    cy.contains('button', /^Personalización$/i).click({ force: true });
    cy.contains('h2', /Identidad Visual/i, { timeout: 15000 }).should('exist');

    cy.then(() => {
      const nombreFinca = baseline179 && baseline179.org_display_name;
      if (nombreFinca) {
        cy.get('body').then(($body) => {
          const btn = [...$body.find('button')].find((el) =>
            el.innerText.toLowerCase().includes(String(nombreFinca).toLowerCase().slice(0, 12))
          );
          if (btn) {
            cy.wrap(btn).click({ force: true });
          }
        });
      }
    });

    cy.get('body').then(($body) => {
      const hex = $body.find('input[aria-label="Hex Color primario"]');
      if (!hex.length) {
        cy.writeFile(
          `${EVIDENCIA}/G94-179-via-api.txt`,
          'UI Identidad Visual visible pero sin input Hex Color primario. Se usa PATCH /configuracion/identidad-visual/{id_finca}.'
        );
        cy.request({
          method: 'PATCH',
          url: `${DEV_API}/configuracion/identidad-visual/${baseline179.id_finca}`,
          headers: { Authorization: `Bearer ${token}` },
          form: true,
          body: {
            primary_color: COLOR_BAJO_CONTRASTE,
            secondary_color: baseline179.secondary_color,
            org_display_name: baseline179.org_display_name,
            version: baseline179.version,
          },
          failOnStatusCode: false,
        }).then((patchRes) => {
          expect(patchRes.status, 'PATCH color de prueba HTTP').to.be.oneOf([200, 201]);
        });
        return;
      }
      cy.get('input[aria-label="Hex Color primario"]').first().should('be.visible').clear().type(COLOR_BAJO_CONTRASTE);
      cy.contains('button', /Actualizar identidad/i).click({ force: true });
      cy.contains('button', /Actualizar identidad/i, { timeout: 20000 }).should('not.be.disabled');
      cy.url().should('not.include', '/login');
    });

    cy.reload();
    cy.url().should('not.include', '/login');

    apiGet('/configuracion/interfaz/contexto').then((res) => {
      expect(res.status, 'GET contexto tras guardar #FFFFFF').to.eq(200);
      const stored = res.body.identidad_visual && res.body.identidad_visual.primary_color;
      expect(String(stored).toUpperCase(), 'color almacenado').to.eq(COLOR_BAJO_CONTRASTE);

      cy.document().then((doc) => {
        const dataTheme = doc.documentElement.getAttribute('data-theme') || 'light';
        const tema = temaActivoDesdeDom(dataTheme);
        const evalPrimario = accesibilidadColor(res.body.accesibilidad, 'primary_color', tema);
        expect(evalPrimario, `accesibilidad.primary_color.${tema}`).to.exist;
        expect(evalPrimario.cumple_aa, 'cumple_aa del tema activo').to.eq(false);
        expect(evalPrimario.ratio, 'ratio < 4.5').to.be.lessThan(4.5);
        expect(evalPrimario.color_ajustado, 'color_ajustado presente').to.be.a('string').and.not.empty;
        expect(String(evalPrimario.color_ajustado).toUpperCase(), 'color_ajustado distinto de #FFFFFF').to.not.eq(
          COLOR_BAJO_CONTRASTE
        );
        expect(evalPrimario.aviso, 'aviso de accesibilidad en API').to.be.a('string').and.not.empty;

        const cssPrimario = doc.documentElement.style.getPropertyValue(CSS_MARCA_PRIMARIA).trim()
          || (doc.defaultView && doc.defaultView.getComputedStyle(doc.documentElement).getPropertyValue(CSS_MARCA_PRIMARIA).trim());
        expect(cssPrimario.replace(/\s/g, '').toUpperCase(), `CSS ${CSS_MARCA_PRIMARIA} = color_ajustado`).to.eq(
          String(evalPrimario.color_ajustado).toUpperCase()
        );

        cy.writeFile(`${EVIDENCIA}/G94-179-resultado.json`, {
          color_enviado: COLOR_BAJO_CONTRASTE,
          color_almacenado: stored,
          tema_evaluado: tema,
          data_theme: dataTheme,
          ratio: evalPrimario.ratio,
          cumple_aa: evalPrimario.cumple_aa,
          color_ajustado: evalPrimario.color_ajustado,
          aviso: evalPrimario.aviso,
          css_brand_500: cssPrimario,
          theme_mode_baseline: baseline179 && baseline179.theme_mode,
        });
      });
    });

    cy.get('body').then(($body) => {
      const texto = $body.text();
      const avisoUi = /Aviso de accesibilidad/i.test(texto);
      cy.writeFile(
        `${EVIDENCIA}/G94-179-aviso-ui.txt`,
        avisoUi
          ? 'Aviso de accesibilidad visible en la interfaz.'
          : 'Aviso API presente; texto de aviso no visible en el body en esta pantalla (no se fuerza PASS/FAIL solo por UI).'
      );
    });
  });
});
