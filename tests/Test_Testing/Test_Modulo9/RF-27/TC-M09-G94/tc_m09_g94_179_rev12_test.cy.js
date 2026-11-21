/**
 * TC-M09-179 rev12 TEST — revisión independiente. No modifica ni sobrescribe
 * rev1–rev11 ni 178-rev4. Evidencias: Resultados/179-rev12/.
 *
 * Estímulo histórico (rev4): admin PATCH identidad finca 1 primary_color=#FFFFFF
 * (form); productor en tema claro (theme_mode=1); --brand-500 === #757575 con
 * html[data-theme=light]. Axe es diagnóstico, no criterio de aceptación.
 *
 * Arnés (rev11 + 178-rev4): GET/PATCH autenticados solo dentro de cy.then;
 * espera CSS con timeout; persistir evidencias antes de aserciones de marca;
 * restore con login fresco. HTTP 401 no es restauración exitosa.
 *
 * Sesión única (rev12 corrida 38): un segundo POST /sesiones/ invalida el JWT
 * previo. sesionVigente.admin|prod se actualiza en cada loginApi/UI del it;
 * api() solo usa esa referencia. Restore no reutiliza sesionVigente.
 *
 * No toca /tema/global, RLS, otras fincas ni el DOM/CSS a mano.
 *
 * NO ejecutar Cypress TEST sin autorización de escritura:
 *   npx cypress run --config-file tests/Test_Testing/Test_Modulo9/RF-27/TC-M09-G94/cypress.config.179.rev12.cjs
 */
const TEST_FRONT = 'https://sigab-frontendtest-6aqrny-d2b730-158-69-200-27.sslip.io';
const TEST_API = 'https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test';
const EVIDENCIA = 'tests/Test_Testing/Test_Modulo9/RF-27/TC-M09-G94/Resultados/179-rev12';
const ADMIN = 'admin@pecuaria.co';
const PRODUCTOR = 'productor@pecuaria.co';
const FINCA = 1;
const TEMA_CLARO = 1;
const COLOR_BAJO = '#FFFFFF';
const AJUSTADO = '#757575';
const PRIMARY_BASELINE = '#1A6B3C';
const RATIO_MINIMO_AA = 4.5;
const BRAND_WAIT_MS = 20000;
const TOKENS = [
  '--brand-500',
  '--brand-600',
  '--brand-cta',
  '--brand-cta-hover',
  '--brand-400',
  '--brand-nav',
  '--surface-card',
];

describe('TC-M09-179 rev12 TEST', { testIsolation: true }, () => {
  const sesionVigente = { admin: null, prod: null };
  let snapId = null;
  let snapTema = null;
  let snapTemaFuente = null;
  let patchedId = false;
  let patchedTema = false;
  let escrituraIdentidadIniciada = false;
  let escrituraTemaIniciada = false;
  let preflightOk = false;
  let restoreDetenido = false;
  let lastStep = 'inicio';
  let medicion = null;
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

  function diagnosticoHttp(res) {
    const body = res && res.body && typeof res.body === 'object' && !Array.isArray(res.body) ? res.body : {};
    const msg = typeof body.message === 'string' ? body.message.slice(0, 200) : null;
    return {
      http: res && res.status != null ? res.status : null,
      error_code: errorCode(body),
      message: msg,
    };
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

  function loginApi(correo) {
    return cy.request({
      method: 'POST',
      url: `${TEST_API}/sesiones/`,
      headers: { 'Content-Type': 'application/json' },
      body: { correo_electronico: correo, contrasena: pass() },
      failOnStatusCode: false,
    });
  }

  function adoptarJwt(who, loginRes) {
    if (who !== 'admin' && who !== 'prod') return null;
    const status = loginRes && (loginRes.status != null ? loginRes.status : loginRes.statusCode);
    const tok = loginRes && loginRes.body && loginRes.body.token;
    if (status === 200 && typeof tok === 'string' && tok.length > 0) {
      sesionVigente[who] = tok;
      return tok;
    }
    return null;
  }

  function reqConToken(method, path, token, body, identidadForm) {
    const opts = {
      method,
      url: `${TEST_API}${path}`,
      headers: { Authorization: `Bearer ${token}`, Accept: 'application/json' },
      failOnStatusCode: false,
    };
    if (body && identidadForm) {
      opts.form = true;
      opts.body = body;
    } else if (body) {
      opts.body = body;
    }
    return cy.request(opts);
  }

  function api(method, path, who, body) {
    return cy.then(() => {
      const token = who === 'admin' ? sesionVigente.admin : sesionVigente.prod;
      expect(token, `sesionVigente.${who} para ${method} ${path}`).to.be.a('string').and.not.empty;
      const identidadForm = !!(body && method === 'PATCH' && path.indexOf('identidad-visual') >= 0);
      return reqConToken(method, path, token, body, identidadForm);
    });
  }

  function loginProductorUi() {
    cy.visit(`${TEST_FRONT}/login`);
    cy.get('input[type="email"]').clear().type(PRODUCTOR);
    cy.get('input[type="password"]').clear().type(pass(), { log: false });
    cy.get('button[type="submit"]').contains(/ingresar/i).click();
    cy.wait('@loginProd').then((intc) => {
      expect(intc.response.statusCode, 'login productor UI').to.eq(200);
      const tok = adoptarJwt('prod', intc.response);
      expect(tok, 'sesionVigente.prod tras login UI').to.be.a('string').and.not.empty;
    });
    cy.url({ timeout: 20000 }).should('include', '/dashboard');
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

  function payloadIdentidad(version) {
    return {
      primary_color: snapId.primary_color,
      secondary_color: snapId.secondary_color,
      org_display_name: snapId.org_display_name,
      version,
    };
  }

  function hexValido(val) {
    return /^#[0-9A-F]{6}$/.test(normColor(val));
  }

  function camposRestoreCompletos() {
    return !!(
      snapId &&
      snapId.id_finca === FINCA &&
      hexValido(snapId.primary_color) &&
      hexValido(snapId.secondary_color) &&
      typeof snapId.org_display_name === 'string' &&
      snapId.org_display_name.trim().length >= 1 &&
      snapId.org_display_name.trim().length <= 50 &&
      typeof snapId.version === 'number'
    );
  }

  function coincideIdentidad(body) {
    if (!body || typeof body !== 'object' || !snapId) return false;
    return (
      body.id_finca === FINCA &&
      normColor(body.primary_color) === normColor(snapId.primary_color) &&
      normColor(body.secondary_color) === normColor(snapId.secondary_color) &&
      String(body.org_display_name || '') === String(snapId.org_display_name || '') &&
      String(body.logo_path || '') === String(snapId.logo_path || '')
    );
  }

  function pareceEstimuloIdentidad(body) {
    return !!(body && normColor(body.primary_color) === COLOR_BAJO);
  }

  function pareceEstimuloTema(themeMode) {
    return themeMode === TEMA_CLARO && snapTema !== TEMA_CLARO;
  }

  function debeRestaurarIdentidad() {
    return !!(snapId && camposRestoreCompletos() && (patchedId || escrituraIdentidadIniciada));
  }

  function debeRestaurarTema() {
    return snapTema != null && (patchedTema || escrituraTemaIniciada);
  }

  function restaurarIdentidad(informe) {
    if (restoreDetenido) {
      informe.identidad.omitido = true;
      informe.identidad.razon = 'restore detenido: no agravar tras fallo previo';
      return cy.then(() => informe);
    }
    if (!debeRestaurarIdentidad()) {
      informe.identidad.omitido = true;
      informe.identidad.razon = 'no se inició escritura de identidad o snapshot incompleto';
      return cy.then(() => informe);
    }

    return loginApi(ADMIN)
      .then((loginRes) => {
        informe.identidad.login_admin_restore = {
          http: loginRes.status,
          error_code: errorCode(loginRes.body),
        };
        const tok = loginRes.body && loginRes.body.token;
        if (loginRes.status !== 200 || !tok) {
          restoreDetenido = true;
          informe.identidad.pendiente = true;
          informe.identidad.nota = 'login admin restore no es 200; no se PATCH con token de SPA';
          return null;
        }
        return reqConToken('GET', `/configuracion/identidad-visual/${FINCA}`, tok).then((g) => {
          informe.identidad.get_antes_patch = {
            http: g.status,
            error_code: errorCode(g.body),
            version: g.body && g.body.version,
            primary_color: g.body && g.body.primary_color,
            secondary_color: g.body && g.body.secondary_color,
            org_display_name: g.body && g.body.org_display_name,
            logo_path: g.body && g.body.logo_path,
            id_usuario: g.body && g.body.id_usuario,
            id_usuario_snapshot: snapId && snapId.id_usuario,
            nota_id_usuario:
              'id_usuario no viaja en el DTO PATCH; el use case lo asigna al admin que escribe.',
          };
          if (g.status !== 200 || !g.body || typeof g.body !== 'object') {
            restoreDetenido = true;
            informe.identidad.pendiente = true;
            informe.identidad.nota = 'GET identidad restore no es 200 objeto; no se PATCH';
            return null;
          }
          if (coincideIdentidad(g.body)) {
            patchedId = false;
            escrituraIdentidadIniciada = false;
            informe.identidad.patch_omitido_ya_coincide = true;
            informe.identidad.coincide_snapshot = true;
            informe.identidad.get_final = informe.identidad.get_antes_patch;
            informe.identidad.nota =
              'GET ya coincide con snapshot; no se PATCH (evita pisar ni inflar version)';
            return null;
          }
          if (!pareceEstimuloIdentidad(g.body)) {
            restoreDetenido = true;
            informe.identidad.pendiente = true;
            informe.identidad.conflicto_concurrente = true;
            informe.identidad.coincide_snapshot = false;
            informe.identidad.nota =
              'GET no es snapshot ni estímulo #FFFFFF; no se PATCH para no sobrescribir un cambio concurrente';
            return null;
          }
          const ver = typeof g.body.version === 'number' ? g.body.version : snapId.version;
          return reqConToken(
            'PATCH',
            `/configuracion/identidad-visual/${FINCA}`,
            tok,
            payloadIdentidad(ver),
            true,
          ).then((p) => {
            informe.identidad.patch = {
              http: p.status,
              error_code: errorCode(p.body),
            };
            if (p.status === 401) {
              restoreDetenido = true;
              informe.identidad.pendiente = true;
              informe.identidad.nota = 'PATCH identidad HTTP 401 no es restauración exitosa';
              return null;
            }
            if (p.status !== 200 && p.status !== 201) {
              restoreDetenido = true;
              informe.identidad.pendiente = true;
              informe.identidad.nota = `PATCH identidad HTTP ${p.status}; no se reintenta`;
              return null;
            }
            patchedId = false;
            escrituraIdentidadIniciada = false;
            return reqConToken('GET', `/configuracion/identidad-visual/${FINCA}`, tok).then((gf) => {
              informe.identidad.get_final = {
                http: gf.status,
                error_code: errorCode(gf.body),
                id_finca: gf.body && gf.body.id_finca,
                primary_color: gf.body && gf.body.primary_color,
                secondary_color: gf.body && gf.body.secondary_color,
                org_display_name: gf.body && gf.body.org_display_name,
                logo_path: gf.body && gf.body.logo_path,
                version: gf.body && gf.body.version,
                id_usuario: gf.body && gf.body.id_usuario,
                id_usuario_snapshot: snapId && snapId.id_usuario,
                nota_id_usuario:
                  'Tras restore, id_usuario suele ser el admin restaurador; no se aserta igualdad con el snapshot.',
              };
              informe.identidad.coincide_snapshot = gf.status === 200 && coincideIdentidad(gf.body);
              if (!informe.identidad.coincide_snapshot) {
                informe.identidad.pendiente = true;
                informe.identidad.nota =
                  'PATCH restore HTTP 200/201 pero GET final no coincide con snapshot (primary/secondary/org/logo)';
              }
            });
          });
        });
      })
      .then(() => informe);
  }

  function restaurarTema(informe) {
    if (!debeRestaurarTema()) {
      informe.tema.omitido = true;
      informe.tema.razon = 'no se inició escritura de tema personal';
      return cy.then(() => informe);
    }

    return loginApi(PRODUCTOR)
      .then((loginRes) => {
        informe.tema.login_prod_restore = {
          http: loginRes.status,
          error_code: errorCode(loginRes.body),
        };
        const tok = loginRes.body && loginRes.body.token;
        if (loginRes.status !== 200 || !tok) {
          informe.tema.pendiente = true;
          informe.tema.nota = 'login productor restore no es 200; no se PATCH con token de SPA';
          return null;
        }
        return reqConToken('GET', '/configuracion/personalizacion/tema', tok).then((g0) => {
          informe.tema.get_antes_patch = {
            http: g0.status,
            theme_mode: g0.body && g0.body.theme_mode,
            fuente: g0.body && g0.body.fuente,
          };
          if (g0.status !== 200) {
            informe.tema.pendiente = true;
            informe.tema.nota = 'GET tema restore no es 200; no se PATCH';
            return null;
          }
          if (g0.body && g0.body.theme_mode === snapTema) {
            patchedTema = false;
            escrituraTemaIniciada = false;
            informe.tema.patch_omitido_ya_coincide = true;
            informe.tema.coincide_snapshot = true;
            informe.tema.get_final = informe.tema.get_antes_patch;
            informe.tema.nota = 'GET tema ya coincide con snapshot; no se PATCH';
            return null;
          }
          if (!pareceEstimuloTema(g0.body && g0.body.theme_mode)) {
            informe.tema.pendiente = true;
            informe.tema.conflicto_concurrente = true;
            informe.tema.coincide_snapshot = false;
            informe.tema.nota =
              'GET tema no es snapshot ni el claro del estímulo; no se PATCH (posible cambio concurrente)';
            return null;
          }
          return reqConToken('PATCH', '/configuracion/personalizacion/tema', tok, {
          theme_mode: snapTema,
        }).then((p) => {
          informe.tema.patch = {
            http: p.status,
            error_code: errorCode(p.body),
          };
          if (p.status === 401) {
            informe.tema.pendiente = true;
            informe.tema.nota = 'PATCH tema HTTP 401 no es restauración exitosa';
            return null;
          }
          if (p.status !== 200) {
            informe.tema.pendiente = true;
            informe.tema.nota = `PATCH tema HTTP ${p.status}; no se reintenta`;
            return null;
          }
          patchedTema = false;
          escrituraTemaIniciada = false;
          return reqConToken('GET', '/configuracion/personalizacion/tema', tok).then((g) => {
            informe.tema.get_final = {
              http: g.status,
              error_code: errorCode(g.body),
              theme_mode: g.body && g.body.theme_mode,
              fuente: g.body && g.body.fuente,
            };
            informe.tema.coincide_snapshot =
              g.status === 200 && g.body && g.body.theme_mode === snapTema;
            if (!informe.tema.coincide_snapshot) {
              informe.tema.pendiente = true;
              informe.tema.nota = 'PATCH tema HTTP 200 pero GET final theme_mode != snapshot';
            }
          });
        });
        });
      })
      .then(() => informe);
  }

  function restoreTodo() {
    const debiaIdentidad = debeRestaurarIdentidad();
    const debiaTema = debeRestaurarTema();
    const informe = {
      identidad: { omitido: false, pendiente: false, coincide_snapshot: null },
      tema: { omitido: false, pendiente: false, coincide_snapshot: null },
      refresh_durante_it: refreshLog,
      debia_restaurar_identidad: debiaIdentidad,
      debia_restaurar_tema: debiaTema,
    };

    cy.then(() => restaurarIdentidad(informe))
      .then(() => restaurarTema(informe))
      .then(() => {
        cy.writeFile(`${EVIDENCIA}/G94-rev12-179-restore.json`, informe);
        cy.writeFile(`${EVIDENCIA}/G94-rev12-179-verificacion-final.json`, {
          snapshot_identidad: snapId,
          snapshot_theme_mode: snapTema,
          identidad: informe.identidad,
          tema: informe.tema,
        });
        const pendiente =
          (debiaIdentidad && (!informe.identidad.coincide_snapshot || informe.identidad.pendiente)) ||
          (debiaTema && (!informe.tema.coincide_snapshot || informe.tema.pendiente));
        if (pendiente) {
          cy.writeFile(`${EVIDENCIA}/G94-rev12-179-RESTORE-PENDIENTE.json`, {
            pendiente: true,
            snapshot_identidad: snapId,
            snapshot_theme_mode: snapTema,
            identidad: informe.identidad,
            tema: informe.tema,
            nota: 'Restore incompleto. Ver Resultados/179-rev12/RECUPERACION_MANUAL.md. No reintentar en bucle.',
          });
        }
        if (debiaIdentidad) {
          expect(informe.identidad.pendiente, 'identidad pendiente de restore').to.eq(false);
          expect(informe.identidad.coincide_snapshot, 'GET identidad final = snapshot (colores, org, logo)').to.eq(
            true,
          );
          if (!informe.identidad.patch_omitido_ya_coincide) {
            expect(informe.identidad.patch && informe.identidad.patch.http, 'restore identidad HTTP').to.be.oneOf([
              200,
              201,
            ]);
          }
        }
        if (debiaTema) {
          expect(informe.tema.pendiente, 'tema pendiente de restore').to.eq(false);
          expect(informe.tema.coincide_snapshot, 'GET tema final = snapshot').to.eq(true);
          if (!informe.tema.patch_omitido_ya_coincide) {
            expect(informe.tema.patch && informe.tema.patch.http, 'restore theme_mode HTTP').to.eq(200);
          }
        }
      });
  }

  after(function () {
    restoreTodo();
  });

  afterEach(function () {
    const err = this.currentTest && this.currentTest.err;
    cy.writeFile(`${EVIDENCIA}/G94-rev12-179-ultimo-paso.json`, {
      last_step: lastStep,
      mocha_state: this.currentTest ? this.currentTest.state : null,
      mocha_error: err && err.message ? String(err.message) : null,
      patched_id: patchedId,
      patched_tema: patchedTema,
      escritura_identidad_iniciada: escrituraIdentidadIniciada,
      escritura_tema_iniciada: escrituraTemaIniciada,
      preflight_ok: preflightOk,
      restore_detenido: restoreDetenido,
      axe: {
        ejecutado: axeEjecutado,
        violations: medicion && medicion.axe_violations != null ? medicion.axe_violations : null,
        nota: 'axe es diagnóstico; no es criterio de aceptación de rev12',
      },
      brand500_normalizado: medicion && medicion.brand500_normalizado,
      data_theme: medicion && medicion.data_theme,
    });
    if (!axeEjecutado) {
      cy.writeFile(`${EVIDENCIA}/G94-rev12-179-axe.json`, {
        ejecutado: false,
        last_step: lastStep,
        violations: null,
        criterio_aceptacion: false,
        nota: 'axe no alcanzó a correr; no se declara color-contrast = 0',
      });
    }
  });

  it('TC-M09-179 aplica color_ajustado #757575 en --brand-500 con data-theme=light', function () {
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
          theme_mode: body.theme_mode != null ? body.theme_mode : null,
        });
      });
    }).as('getTemaBrowser');

    loginApi(ADMIN).then((r) => {
      expect(r.status, 'login admin API un intento').to.eq(200);
      const tok = adoptarJwt('admin', r);
      expect(tok, 'sesionVigente.admin tras login API').to.be.a('string').and.not.empty;
      lastStep = 'login_admin_api';
    });

    loginProductorUi();
    cy.then(() => {
      lastStep = 'login_prod_ui';
    });

    cy.wait('@ctx').then((intc) => {
      const body = intc.response.body;
      expect(body.id_finca, 'snapshot contexto finca').to.eq(FINCA);
      expect(body.id_usuario, 'productor id').to.eq(2);
      cy.writeFile(`${EVIDENCIA}/G94-rev12-179-contexto-antes.json`, {
        id_usuario: body.id_usuario,
        id_finca: body.id_finca,
        finca_activa: body.finca_activa,
        identidad_visual: body.identidad_visual,
        accesibilidad: body.accesibilidad,
      });
      lastStep = 'contexto_antes';
    });

    api('GET', `/configuracion/identidad-visual/${FINCA}`, 'admin').then((idRes) => {
      expect(idRes.status, 'GET identidad snapshot').to.eq(200);
      expect(idRes.body, 'identidad snapshot objeto (no null)').to.be.an('object');
      expect(idRes.body.id_finca, 'GET identidad id_finca').to.eq(FINCA);
      snapId = {
        id_identidad_visual: idRes.body.id_identidad_visual,
        id_finca: idRes.body.id_finca,
        id_usuario: idRes.body.id_usuario,
        primary_color: idRes.body.primary_color,
        secondary_color: idRes.body.secondary_color,
        org_display_name: idRes.body.org_display_name,
        version: idRes.body.version,
        logo_path: idRes.body.logo_path,
        fecha_creacion: idRes.body.fecha_creacion,
      };
      expect(normColor(snapId.primary_color), 'baseline primary finca 1').to.eq(PRIMARY_BASELINE);
      expect(hexValido(snapId.secondary_color), 'secondary_color hex para PATCH form').to.eq(true);
      expect(snapId.org_display_name, 'org_display_name para PATCH form').to.be.a('string').and.not.empty;
      expect(typeof snapId.version, 'version para restore').to.eq('number');
      expect(camposRestoreCompletos(), 'snapshot cubre campos del DTO PATCH').to.eq(true);
      cy.writeFile(`${EVIDENCIA}/G94-rev12-179-snapshot-identidad.json`, {
        ...snapId,
        accesibilidad: idRes.body.accesibilidad,
        nota: 'logo_path no viaja en PATCH form; omitir archivo conserva el logo (actualizar_identidad_visual_use_case).',
      });
      lastStep = 'snapshot_identidad';
    });

    api('GET', '/configuracion/personalizacion/tema', 'prod').then((tRes) => {
      expect(tRes.status, 'GET tema snapshot').to.eq(200);
      snapTema = tRes.body.theme_mode;
      snapTemaFuente = tRes.body.fuente;
      cy.writeFile(`${EVIDENCIA}/G94-rev12-179-snapshot-tema.json`, {
        theme_mode: tRes.body.theme_mode,
        fuente: tRes.body.fuente,
        id_tema_visual: tRes.body.id_tema_visual,
      });
      lastStep = 'snapshot_tema';
      cy.writeFile(`${EVIDENCIA}/G94-rev12-179-paquete-recuperacion.json`, {
        generado: 'antes de cualquier PATCH',
        snapshot_valido: camposRestoreCompletos() && snapTema != null,
        campos_restore_completos: camposRestoreCompletos(),
        finca: FINCA,
        identidad_patch_form: {
          path: `/configuracion/identidad-visual/${FINCA}`,
          primary_color: snapId.primary_color,
          secondary_color: snapId.secondary_color,
          org_display_name: snapId.org_display_name,
          version_en_snapshot: snapId.version,
          nota_version: 'En recuperación manual usar la version del GET vigente, no necesariamente esta.',
          logo: 'omitir campo logo para conservar logo_path del snapshot',
          logo_path_esperado: snapId.logo_path,
        },
        id_usuario_original_fila: snapId.id_usuario,
        nota_id_usuario:
          'El PATCH no envía id_usuario; ActualizarIdentidadVisualUseCase lo cambia al admin que escribe. No se revierte ese campo.',
        estimulo_primary: COLOR_BAJO,
        tema_patch_json: {
          path: '/configuracion/personalizacion/tema',
          theme_mode: snapTema,
        },
        estimulo_theme_mode: TEMA_CLARO,
        actores: { admin: ADMIN, productor: PRODUCTOR },
      });
    });

    cy.then(() => {
      lastStep = 'preflight_restore';
      const preflight = {
        lectura_identidad: null,
        lectura_tema: null,
        login_admin_fresco: null,
        login_prod_fresco: null,
        apto: false,
      };
      return loginApi(ADMIN)
        .then((la) => {
          preflight.login_admin_fresco = { http: la.status, error_code: errorCode(la.body) };
          const tokA = adoptarJwt('admin', la);
          if (!tokA) return preflight;
          return reqConToken('GET', `/configuracion/identidad-visual/${FINCA}`, tokA).then((g) => {
            preflight.lectura_identidad = {
              http: g.status,
              objeto: !!(g.body && typeof g.body === 'object' && g.body.primary_color),
              version: g.body && g.body.version,
              primary_color: g.body && g.body.primary_color,
            };
            return loginApi(PRODUCTOR).then((lp) => {
              preflight.login_prod_fresco = { http: lp.status, error_code: errorCode(lp.body) };
              const tokP = adoptarJwt('prod', lp);
              if (!tokP) return preflight;
              return reqConToken('GET', '/configuracion/personalizacion/tema', tokP).then((gt) => {
                preflight.lectura_tema = {
                  http: gt.status,
                  theme_mode: gt.body && gt.body.theme_mode,
                  fuente: gt.body && gt.body.fuente,
                };
                preflight.apto =
                  preflight.lectura_identidad &&
                  preflight.lectura_identidad.http === 200 &&
                  preflight.lectura_identidad.objeto === true &&
                  preflight.lectura_tema &&
                  preflight.lectura_tema.http === 200 &&
                  camposRestoreCompletos() &&
                  snapTema != null;
                return preflight;
              });
            });
          });
        })
        .then((pf) => {
          preflightOk = !!(pf && pf.apto);
          cy.writeFile(`${EVIDENCIA}/G94-rev12-179-preflight-restore.json`, {
            ...pf,
            jwt_vigente_actualizado: {
              admin: !!(sesionVigente.admin && pf && pf.login_admin_fresco && pf.login_admin_fresco.http === 200),
              prod: !!(sesionVigente.prod && pf && pf.login_prod_fresco && pf.login_prod_fresco.http === 200),
            },
            nota:
              'Solo lecturas y logins frescos. Tras cada login 200, api() usa sesionVigente (sesión única). Sin PATCH. Si apto=false no hay escritura de estímulo. JWT no se escribe.',
            mecanismo_restore: {
              identidad: `PATCH form /configuracion/identidad-visual/${FINCA} (admin, recurso 23) con snapshot + version vigente`,
              tema: 'PATCH JSON /configuracion/personalizacion/tema (productor, recurso 24) con theme_mode del snapshot',
            },
          });
          expect(preflightOk, 'preflight: login fresco + GET identidad/tema HTTP 200').to.eq(true);
        });
    });

    api('GET', '/configuracion/personalizacion/tema', 'prod').then((tRes) => {
      expect(tRes.status, 'GET tema con JWT vigente antes de estímulo').to.eq(200);
      if (tRes.body.theme_mode === TEMA_CLARO) {
        lastStep = 'tema_sin_patch';
        cy.writeFile(`${EVIDENCIA}/G94-rev12-179-tema-sin-patch.json`, {
          theme_mode: tRes.body.theme_mode,
          nota: 'Ya estaba en claro; no se PATCH para no alterar innecesariamente.',
        });
        return;
      }
      escrituraTemaIniciada = true;
      lastStep = 'tema_patch_enviando';
      return api('PATCH', '/configuracion/personalizacion/tema', 'prod', { theme_mode: TEMA_CLARO }).then(
        (pTema) => {
          cy.writeFile(`${EVIDENCIA}/G94-rev12-179-tema-patch-estimulo.json`, diagnosticoHttp(pTema));
          expect(pTema.status, 'PATCH tema=1').to.eq(200);
          patchedTema = true;
          return api('GET', '/configuracion/personalizacion/tema', 'prod').then((gTema) => {
            expect(gTema.body.theme_mode, 'GET tema tras PATCH').to.eq(TEMA_CLARO);
            lastStep = 'tema_tras_patch';
            cy.writeFile(`${EVIDENCIA}/G94-rev12-179-tema-tras-patch.json`, {
              theme_mode: gTema.body.theme_mode,
              fuente: gTema.body.fuente,
            });
          });
        },
      );
    });

    api('GET', `/configuracion/identidad-visual/${FINCA}`, 'admin').then((idRes) => {
      expect(idRes.status, 'GET identidad antes de estímulo').to.eq(200);
      escrituraIdentidadIniciada = true;
      lastStep = 'identidad_patch_enviando';
      return api('PATCH', `/configuracion/identidad-visual/${FINCA}`, 'admin', {
        primary_color: COLOR_BAJO,
        secondary_color: snapId.secondary_color,
        org_display_name: snapId.org_display_name,
        version: idRes.body.version,
      });
    }).then((pId) => {
      expect(pId.status, 'PATCH primary #FFFFFF').to.be.oneOf([200, 201]);
      patchedId = true;
      lastStep = 'identidad_tras_patch';
      const claro = pId.body.accesibilidad.primary_color.claro;
      expect(claro.ratio).to.eq(1);
      expect(claro.cumple_aa).to.eq(false);
      expect(normColor(claro.color_ajustado)).to.eq(AJUSTADO);
    });

    api('GET', `/configuracion/identidad-visual/${FINCA}`, 'admin').then((gId) => {
      expect(normColor(gId.body.primary_color)).to.eq(COLOR_BAJO);
      cy.writeFile(`${EVIDENCIA}/G94-rev12-179-identidad-despues.json`, {
        primary_color: gId.body.primary_color,
        secondary_color: gId.body.secondary_color,
        version: gId.body.version,
        accesibilidad_claro: gId.body.accesibilidad.primary_color.claro,
      });
    });

    api('GET', '/configuracion/interfaz/contexto', 'prod').then((ctx) => {
      expect(ctx.body.id_usuario).to.eq(2);
      expect(ctx.body.id_finca).to.eq(FINCA);
      expect(normColor(ctx.body.identidad_visual.primary_color)).to.eq(COLOR_BAJO);
      const claro = ctx.body.accesibilidad.primary_color.claro;
      expect(claro.ratio).to.eq(1);
      expect(claro.cumple_aa).to.eq(false);
      expect(normColor(claro.color_ajustado)).to.eq(AJUSTADO);
      cy.writeFile(`${EVIDENCIA}/G94-rev12-179-contexto-api-despues.json`, {
        id_usuario: ctx.body.id_usuario,
        id_finca: ctx.body.id_finca,
        identidad_visual: ctx.body.identidad_visual,
        accesibilidad_primary_claro: claro,
      });
      lastStep = 'contexto_api_despues';
    });

    cy.intercept({ method: 'GET', url: /\/configuracion\/interfaz\/contexto\/?$/ }).as('ctxPost');
    cy.intercept({ method: 'GET', url: /\/configuracion\/personalizacion\/tema\/?$/ }).as('temaPost');
    cy.then(() => {
      lastStep = 'sesion_navegador_tras_estimulo';
    });
    loginProductorUi();

    cy.wait('@temaPost', { timeout: 20000 }).then((intc) => {
      const mode = intc.response.body && intc.response.body.theme_mode;
      cy.writeFile(`${EVIDENCIA}/G94-rev12-179-tema-browser.json`, {
        http: intc.response.statusCode,
        theme_mode: mode,
      });
      expect(mode, 'GET tema navegador = 1').to.eq(TEMA_CLARO);
      lastStep = 'tema_browser';
    });

    leerTokens().then((temprano) => {
      lastStep = 'diagnostico_temprano';
      return cy.writeFile(`${EVIDENCIA}/G94-rev12-179-diagnostico-temprano.json`, {
        ...temprano,
        brand_wait_ms: BRAND_WAIT_MS,
        esperado: AJUSTADO,
        nota: `Snapshot antes de esperar --brand-500 === ${AJUSTADO} y data-theme=light (${BRAND_WAIT_MS} ms). No se fuerza CSS ni DOM.`,
      });
    });

    cy.document({ timeout: BRAND_WAIT_MS }).should((doc) => {
      const observado = leerBrand500Computed(doc);
      const theme = doc.documentElement.getAttribute('data-theme');
      const url = `${doc.location.origin}${doc.location.pathname}`;
      expect(
        theme,
        `data-theme debe ser light en ${BRAND_WAIT_MS}ms (observado=${theme === null ? 'null' : theme}, url=${url}). No se fuerza CSS.`,
      ).to.eq('light');
      expect(
        observado,
        `--brand-500 debe ser ${AJUSTADO} en ${BRAND_WAIT_MS}ms (observado=${observado || '(vacío)'}, data-theme=${theme === null ? 'null' : theme}, url=${url}, timeout=${BRAND_WAIT_MS}ms). Ver diagnostico-temprano.json. No se fuerza CSS.`,
      ).to.eq(AJUSTADO);
    });
    cy.then(() => {
      lastStep = 'brand_confirmado';
    });

    cy.location('pathname').then((pathname) => {
      return leerTokens().then((css) => {
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
          ratio_minimo_aa: RATIO_MINIMO_AA,
          primario_estimulo: COLOR_BAJO,
          esperado_ajustado_claro: AJUSTADO,
          snapshot_theme_mode: snapTema,
          snapshot_theme_fuente: snapTemaFuente,
          coincide_ajustado: aplicado === AJUSTADO,
          axe_violations: null,
          axe_es_criterio_aceptacion: false,
        };
        lastStep = 'css_capturado';
        return cy
          .writeFile(`${EVIDENCIA}/G94-rev12-179-diagnostico.json`, {
            ...medicion,
            css,
            refresh_log: refreshLog,
            tema_browser_log: temaBrowserLog,
          })
          .then(() =>
            cy.writeFile(`${EVIDENCIA}/G94-rev12-179-css-despues.json`, {
              ...css,
              esperado: AJUSTADO,
              brand500_normalizado: aplicado,
              fondo_normalizado: fondo.hex,
              fondo_origen: fondo.origen,
              ratio_brand_vs_fondo: ratioMarca,
              ratio_minimo_aa: RATIO_MINIMO_AA,
            }),
          )
          .then(() => {
            lastStep = 'diagnostico_persistido';
          });
      });
    });

    cy.screenshot('G94-rev12-179-dashboard-light-variante');

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
          .writeFile(`${EVIDENCIA}/G94-rev12-179-axe.json`, {
            ejecutado: true,
            criterio_aceptacion: false,
            violations: viol.length,
            violation_ids: viol.map((v) => v.id),
            color_contrast_pass_nodes: cc ? (cc.nodes || []).length : 0,
            violation_nodes: viol.length ? extraerNodosAxe(viol[0].nodes) : [],
            nota: 'Diagnóstico. El oráculo de rev12 es --brand-500=#757575, no violations===0.',
          })
          .then(() => {
            axeEjecutado = true;
          });
      });

    cy.writeFile(`${EVIDENCIA}/G94-rev12-179-refresh.json`, {
      llamadas: refreshLog,
      tema_browser: temaBrowserLog,
    });

    cy.then(() => {
      lastStep = 'aserciones';
      expect(medicion, 'medición CSS persistida').to.be.an('object');
      expect(medicion.data_theme, 'data-theme=light').to.eq('light');
      expect(medicion.brand500_normalizado, '--brand-500 = color_ajustado #757575').to.eq(AJUSTADO);
    });
  });
});
