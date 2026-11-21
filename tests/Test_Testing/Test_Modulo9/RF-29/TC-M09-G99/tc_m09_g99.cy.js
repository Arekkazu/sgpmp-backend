/**
 * TC-M09-G99 — Cambio de idioma de la interfaz (RF-29).
 *
 *   TC-M09-189 → locale_code=es-CO (Español Colombia)
 *   TC-M09-190 → locale_code=en-US (English United States)
 *   TC-M09-191 → el cambio se aplica en el mismo documento/sesión, sin recarga ni logout
 *
 * Capa: Cypress (el repo no tiene Playwright). Ambiente: DEV.
 * Un solo login. Solo el panel "Mi preferencia" / "My preference" (no idioma global).
 *
 * Ejecutar:
 *   npx cypress run --spec tests/Test_Testing/Test_Modulo9/RF-29/TC-M09-G99/tc_m09_g99.cy.js --env correo=admin.dev@gmail.com,contrasena=***
 *
 * Si POST /sesiones/refresh → 500 y la SPA vuelve a /login: BLOQUEADO, no RECHAZADO de RF-29.
 */
const DEV_FRONT = 'https://sigab-frontenddev-pbw0py-757e2f-158-69-200-27.sslip.io';
const DEV_API = 'https://sigab-backenddev-jpuya4-ea3a74-158-69-200-27.sslip.io/api-sgpmp';
const EVIDENCIA = 'tests/Test_Testing/Test_Modulo9/RF-29/TC-M09-G99/Resultados';

const GET_IDIOMA = /\/configuracion\/personalizacion\/idioma\/?(\?.*)?$/;
const PATCH_IDIOMA = /\/configuracion\/personalizacion\/idioma\/?(\?.*)?$/;
const PATCH_IDIOMA_GLOBAL = /\/configuracion\/personalizacion\/idioma\/global\/?$/;
const POST_REFRESH = /\/sesiones\/refresh\/?$/;
const POST_LOGIN = /\/sesiones\/?$/;

const MARKER = `g99-${Date.now()}`;

function cuerpoSinSecretos(value) {
  if (value == null) return value;
  if (typeof value !== 'object') return value;
  if (Array.isArray(value)) return value.map(cuerpoSinSecretos);
  const out = {};
  Object.keys(value).forEach((k) => {
    const lower = k.toLowerCase();
    if (
      lower.includes('token') ||
      lower.includes('password') ||
      lower.includes('contrasena') ||
      lower.includes('authorization') ||
      lower.includes('cookie') ||
      lower === 'jwt'
    ) {
      out[k] = '[redacted]';
    } else {
      out[k] = cuerpoSinSecretos(value[k]);
    }
  });
  return out;
}

function resumenIntercept(interception) {
  if (!interception || !interception.request) {
    return { presente: false };
  }
  return {
    method: interception.request.method,
    url: interception.request.url.replace(/([?&](token|access_token)=)[^&]+/gi, '$1[redacted]'),
    status: interception.response ? interception.response.statusCode : null,
    requestBody: cuerpoSinSecretos(interception.request.body || null),
    responseBody: cuerpoSinSecretos(interception.response ? interception.response.body : null),
  };
}

describe('TC-M09-G99 - Cambio de idioma de la interfaz', { testIsolation: false }, () => {
  const notas = {
    fecha: new Date().toISOString(),
    ambiente: 'DEV',
    usuario: null,
    clasificacion: 'PENDIENTE',
    resultado189: 'PENDIENTE',
    resultado190: 'PENDIENTE',
    resultado191: 'PENDIENTE',
    pasos: [],
    logins: 0,
    loginHttp: null,
    refreshHttp: null,
    getIdiomaInicial: null,
    localeOriginal: null,
    versionPerfilOriginal: null,
    fuenteOriginal: null,
    idPreferenciaOriginal: null,
    patch189: null,
    patch190: null,
    patchGlobalCount: 0,
    textosEs: null,
    textosEn: null,
    lang189: null,
    lang190: null,
    urlInicial: null,
    url189: null,
    urlAntes190: null,
    urlDespues190: null,
    marker: MARKER,
    markerAntes190: null,
    markerDespues190: null,
    htmlRefIgual: null,
    timeOriginAntes: null,
    timeOriginDespues: null,
    restauracion: null,
    getIdiomaFinal: null,
    error: null,
  };

  let token = null;
  let flujoListo = false;
  let versionPerfilActual = null;

  function registrarPaso(texto) {
    notas.pasos.push(texto);
    cy.log(texto);
  }

  function escribirNotas() {
    cy.writeFile(
      `${EVIDENCIA}/TC-M09-G99_rev1_dev-ejecucion.txt`,
      [
        'TC-M09-G99 / RF-29 — ejecución rev1 DEV',
        `Fecha: ${notas.fecha}`,
        `Ambiente: ${notas.ambiente}`,
        `Frontend: ${DEV_FRONT}`,
        `API: ${DEV_API}`,
        `Usuario: ${notas.usuario || 'no registrado'}`,
        `Resultado general: ${notas.clasificacion}`,
        `TC-M09-189: ${notas.resultado189}`,
        `TC-M09-190: ${notas.resultado190}`,
        `TC-M09-191: ${notas.resultado191}`,
        '',
        `Logins realizados: ${notas.logins} (máximo permitido: 1)`,
        `Login HTTP: ${notas.loginHttp}`,
        `Refresh HTTP (si ocurrió): ${notas.refreshHttp}`,
        '',
        `Locale original: ${notas.localeOriginal}`,
        `fuente original: ${notas.fuenteOriginal}`,
        `version_perfil original: ${notas.versionPerfilOriginal}`,
        `id_preferencia_idioma original: ${notas.idPreferenciaOriginal}`,
        `GET idioma inicial: ${JSON.stringify(notas.getIdiomaInicial, null, 2)}`,
        '',
        `PATCH es-CO (189): ${JSON.stringify(notas.patch189, null, 2)}`,
        `Textos ES observados: ${notas.textosEs}`,
        `html[lang] 189: ${notas.lang189}`,
        `URL 189: ${notas.url189}`,
        '',
        `PATCH en-US (190): ${JSON.stringify(notas.patch190, null, 2)}`,
        `Textos EN observados: ${notas.textosEn}`,
        `html[lang] 190: ${notas.lang190}`,
        `URL antes 190: ${notas.urlAntes190}`,
        `URL después 190: ${notas.urlDespues190}`,
        '',
        `Marcador esperado: ${notas.marker}`,
        `Marcador antes 190: ${notas.markerAntes190}`,
        `Marcador después 190: ${notas.markerDespues190}`,
        `document.documentElement misma referencia: ${notas.htmlRefIgual}`,
        `performance.timeOrigin antes: ${notas.timeOriginAntes}`,
        `performance.timeOrigin después: ${notas.timeOriginDespues}`,
        `PATCH idioma/global (debe ser 0): ${notas.patchGlobalCount}`,
        '',
        `Restauración: ${notas.restauracion}`,
        `GET idioma final: ${JSON.stringify(notas.getIdiomaFinal, null, 2)}`,
        '',
        'Pasos:',
        ...notas.pasos.map((p, i) => `${i + 1}. ${p}`),
        '',
        `Error: ${notas.error || 'ninguno'}`,
        '',
        'Herramienta: Cypress 14 (no Playwright). Panel usado: Mi preferencia. No JWT/password.',
      ].join('\n')
    );
  }

  function bloquear(mensaje) {
    notas.clasificacion = 'BLOQUEADO';
    notas.error = mensaje;
    if (notas.resultado189 === 'PENDIENTE') notas.resultado189 = 'BLOQUEADO';
    if (notas.resultado190 === 'PENDIENTE') notas.resultado190 = 'BLOQUEADO';
    if (notas.resultado191 === 'PENDIENTE') notas.resultado191 = 'BLOQUEADO';
    registrarPaso(`BLOQUEADO: ${mensaje}`);
    escribirNotas();
    cy.then(() => {
      throw new Error(`BLOQUEADO: ${mensaje}`);
    });
  }

  function panelMiPreferencia() {
    return cy
      .contains('div', /^(Mi preferencia|My preference)$/)
      .should('be.visible')
      .parent()
      .parent()
      .parent();
  }

  function guardarPreferenciaPersonal(localeCode) {
    panelMiPreferencia().within(() => {
      if (localeCode === 'es-CO') {
        cy.contains('button', /Español/).should('be.visible').click({ force: true });
        cy.contains(/Colombia/).should('exist');
      } else {
        cy.contains('button', /English/).should('be.visible').click({ force: true });
        cy.contains(/United States/).should('exist');
      }
      cy.contains('button', /^(Guardar idioma|Save language)$/)
        .should('not.be.disabled')
        .click({ force: true });
    });
  }

  function capturarRefreshSiExiste() {
    cy.get('@refreshSesion.all').then((calls) => {
      if (calls && calls.length) {
        const last = calls[calls.length - 1];
        notas.refreshHttp = last.response ? last.response.statusCode : null;
        registrarPaso(`POST /sesiones/refresh status=${notas.refreshHttp} (n=${calls.length})`);
      }
    });
  }

  before(function () {
    const correo = Cypress.env('correo') || 'admin.dev@gmail.com';
    const contrasena = Cypress.env('contrasena');
    expect(contrasena, 'contrasena via Cypress.env (no hardcodear)').to.be.a('string').and.not.empty;
    notas.usuario = correo;

    cy.intercept({ method: 'POST', url: POST_LOGIN }).as('login');
    cy.intercept({ method: 'POST', url: POST_REFRESH }).as('refreshSesion');
    cy.intercept({ method: 'GET', url: GET_IDIOMA }).as('getIdioma');
    cy.intercept({ method: 'PATCH', url: PATCH_IDIOMA }).as('patchIdioma');
    cy.intercept({ method: 'PATCH', url: PATCH_IDIOMA_GLOBAL }).as('patchIdiomaGlobal');

    registrarPaso('Abrir login DEV (único intento)');
    cy.visit(`${DEV_FRONT}/login`);
    cy.get('input[type="email"]').should('be.visible').clear().type(correo);
    cy.get('input[type="password"]').should('be.visible').clear().type(contrasena, { log: false });
    cy.get('button[type="submit"]').contains(/ingresar/i).click();

    cy.wait('@login').then((interception) => {
      const status = interception.response && interception.response.statusCode;
      notas.loginHttp = status;
      notas.logins = 1;
      registrarPaso(`Login POST /sesiones status=${status}`);
      if (status === 401) {
        bloquear('Login HTTP 401. Un solo intento; no se reintenta.');
        return;
      }
      if (status !== 200) {
        bloquear(`Login HTTP ${status}. No se reintenta.`);
        return;
      }
      token = interception.response.body && interception.response.body.token;
      if (!token) {
        bloquear('Login 200 sin token en el cuerpo. No se reintenta.');
      }
    });

    cy.url({ timeout: 20000 }).should('include', '/dashboard');
    cy.url().should('not.include', '/login');
    registrarPaso('Dashboard accesible');
    cy.screenshot('G99-01-dashboard');

    registrarPaso('Ir a Configuración');
    cy.visit(`${DEV_FRONT}/configuracion`);
    cy.contains(/Iniciar sesión|Configuración|Settings/i, { timeout: 20000 }).should('exist');
    capturarRefreshSiExiste();
    cy.url().then((url) => {
      if (url.includes('/login')) {
        bloquear(
          `Tras visitar /configuracion la URL volvió a /login (${url}). POST /sesiones/refresh HTTP ${notas.refreshHttp}. Dependencia de sesión; no es veredicto de RF-29.`
        );
      }
    });

    cy.contains('h1, h2, button', /Configuración|Settings/i, { timeout: 15000 }).should('exist');
    cy.contains('button', /^(Personalización|Personalization)$/i).click({ force: true });

    cy.get('body', { timeout: 15000 }).should(($body) => {
      const texto = $body.text();
      expect(
        /Idioma|Language/.test(texto),
        'sección de idioma visible tras Personalización'
      ).to.eq(true);
    });

    cy.contains('h2', /^(Idioma|Language)$/, { timeout: 15000 }).should('exist');

    cy.get('body').then(($body) => {
      if (!/Mi preferencia|My preference/.test($body.text())) {
        bloquear('No apareció el panel Mi preferencia / My preference. No se usa Idioma global.');
      }
    });

    cy.wait('@getIdioma', { timeout: 20000 }).then((interception) => {
      notas.getIdiomaInicial = resumenIntercept(interception);
      const status = notas.getIdiomaInicial.status;
      registrarPaso(`GET /configuracion/personalizacion/idioma status=${status}`);
      if (status === 401 || status === 403) {
        bloquear(`GET idioma HTTP ${status}. Permiso o sesión; no se clasifica como defecto de RF-29 UI.`);
        return;
      }
      if (status !== 200) {
        bloquear(`GET idioma HTTP ${status}. Endpoint no usable.`);
        return;
      }
      const body = interception.response.body || {};
      notas.localeOriginal = body.locale_code;
      notas.versionPerfilOriginal = body.version_perfil;
      notas.fuenteOriginal = body.fuente;
      notas.idPreferenciaOriginal = body.id_preferencia_idioma;
      versionPerfilActual = body.version_perfil;
      registrarPaso(
        `Precheck locale=${body.locale_code} fuente=${body.fuente} version_perfil=${body.version_perfil}`
      );
    });

    cy.url().then((url) => {
      notas.urlInicial = url;
    });

    cy.window().then((win) => {
      win.__g99DocumentMarker = MARKER;
      win.__g99HtmlRef = win.document.documentElement;
      notas.timeOriginAntes = win.performance.timeOrigin;
    });

    flujoListo = true;
    registrarPaso(`Marcador de documento creado: ${MARKER}`);
    cy.screenshot('G99-02-idioma-inicial');
  });

  it('TC-M09-189 - Cambiar interfaz a español Colombia (es-CO)', function () {
    if (!flujoListo) {
      this.skip();
    }

    registrarPaso('TC-M09-189: seleccionar Español / Colombia en Mi preferencia y guardar');
    guardarPreferenciaPersonal('es-CO');

    cy.wait('@patchIdioma', { timeout: 20000 }).then((interception) => {
      notas.patch189 = resumenIntercept(interception);
      const status = notas.patch189.status;
      const req = (interception.request && interception.request.body) || {};
      const res = (interception.response && interception.response.body) || {};
      registrarPaso(`PATCH personal es-CO status=${status} locale_req=${req.locale_code}`);
      expect(status, 'PATCH es-CO HTTP').to.eq(200);
      expect(req.locale_code, 'body locale_code es-CO').to.eq('es-CO');
      expect(res.locale_code, 'respuesta locale_code es-CO').to.eq('es-CO');
      if (res.version_perfil != null) {
        versionPerfilActual = res.version_perfil;
      }
    });

    cy.get('html').should('have.attr', 'lang', 'es-CO');
    cy.contains('h2', /^Idioma$/).should('be.visible');
    cy.contains('button', /^Guardar idioma$/).should('exist');
    cy.contains('div', /^Mi preferencia$/).should('be.visible');
    cy.contains('Bienvenido al sistema').should('exist');

    cy.url().then((url) => {
      notas.url189 = url;
      expect(url, '189 no va a login').to.not.include('/login');
      expect(url, '189 permanece en configuración').to.include('/configuracion');
    });
    cy.get('html').invoke('attr', 'lang').then((lang) => {
      notas.lang189 = lang;
    });
    cy.get('body').then(($body) => {
      notas.textosEs = ['Idioma', 'Guardar idioma', 'Mi preferencia', 'Bienvenido al sistema']
        .filter((t) => $body.text().includes(t))
        .join(', ');
    });
    cy.window().then((win) => {
      expect(win.__g99DocumentMarker, '189 mismo documento').to.eq(MARKER);
    });
    cy.get('@login.all').then((calls) => {
      expect(calls.length, 'un solo login').to.eq(1);
    });
    cy.get('@patchIdiomaGlobal.all').then((calls) => {
      notas.patchGlobalCount = calls.length;
      expect(calls.length, 'no se toca idioma global').to.eq(0);
    });

    notas.resultado189 = 'APROBADO';
    registrarPaso('TC-M09-189 APROBADO');
    cy.screenshot('G99-03-es-CO');
  });

  it('TC-M09-190 - Cambiar interfaz a inglés Estados Unidos (en-US)', function () {
    if (!flujoListo || notas.resultado189 !== 'APROBADO') {
      if (notas.resultado190 === 'PENDIENTE') notas.resultado190 = 'BLOQUEADO';
      this.skip();
    }

    cy.window().then((win) => {
      notas.markerAntes190 = win.__g99DocumentMarker;
      notas.timeOriginAntes = win.performance.timeOrigin;
      expect(win.__g99DocumentMarker, 'marcador intacto antes de 190').to.eq(MARKER);
    });
    cy.url().then((url) => {
      notas.urlAntes190 = url;
    });

    registrarPaso('TC-M09-190: seleccionar English / United States en Mi preferencia y guardar');
    guardarPreferenciaPersonal('en-US');

    cy.wait('@patchIdioma', { timeout: 20000 }).then((interception) => {
      notas.patch190 = resumenIntercept(interception);
      const status = notas.patch190.status;
      const req = (interception.request && interception.request.body) || {};
      const res = (interception.response && interception.response.body) || {};
      registrarPaso(`PATCH personal en-US status=${status} locale_req=${req.locale_code}`);
      expect(status, 'PATCH en-US HTTP').to.eq(200);
      expect(req.locale_code, 'body locale_code en-US').to.eq('en-US');
      expect(res.locale_code, 'respuesta locale_code en-US').to.eq('en-US');
      if (res.version_perfil != null) {
        versionPerfilActual = res.version_perfil;
      }
    });

    cy.get('html').should('have.attr', 'lang', 'en-US');
    cy.contains('h2', /^Language$/).should('be.visible');
    cy.contains('button', /^Save language$/).should('exist');
    cy.contains('div', /^My preference$/).should('be.visible');
    cy.contains('Welcome to the system').should('exist');

    cy.url().then((url) => {
      notas.urlDespues190 = url;
      expect(url, '190 no va a login').to.not.include('/login');
      expect(url, '190 permanece en configuración').to.include('/configuracion');
    });
    cy.get('html').invoke('attr', 'lang').then((lang) => {
      notas.lang190 = lang;
    });
    cy.get('body').then(($body) => {
      notas.textosEn = ['Language', 'Save language', 'My preference', 'Welcome to the system']
        .filter((t) => $body.text().includes(t))
        .join(', ');
    });
    cy.window().then((win) => {
      notas.markerDespues190 = win.__g99DocumentMarker;
      notas.timeOriginDespues = win.performance.timeOrigin;
      notas.htmlRefIgual = win.document.documentElement === win.__g99HtmlRef;
      expect(win.__g99DocumentMarker, '190 mismo documento').to.eq(MARKER);
    });
    cy.get('@login.all').then((calls) => {
      expect(calls.length, 'sigue habiendo un solo login').to.eq(1);
    });
    cy.get('@patchIdiomaGlobal.all').then((calls) => {
      notas.patchGlobalCount = calls.length;
      expect(calls.length, 'no se toca idioma global').to.eq(0);
    });

    notas.resultado190 = 'APROBADO';
    registrarPaso('TC-M09-190 APROBADO');
    cy.screenshot('G99-04-en-US');
  });

  it('TC-M09-191 - Aplicar cambio de idioma sin recargar la sesión', function () {
    if (!flujoListo || notas.resultado189 !== 'APROBADO' || notas.resultado190 !== 'APROBADO') {
      if (notas.resultado191 === 'PENDIENTE') notas.resultado191 = 'BLOQUEADO';
      this.skip();
    }

    registrarPaso('TC-M09-191: evidenciar mismo documento tras es-CO → en-US (sin cy.visit ni logout)');

    cy.window().then((win) => {
      expect(win.__g99DocumentMarker, 'marcador idéntico').to.eq(MARKER);
      expect(notas.markerAntes190, 'marcador antes 190').to.eq(MARKER);
      expect(notas.markerDespues190, 'marcador después 190').to.eq(MARKER);
      expect(win.document.documentElement === win.__g99HtmlRef, 'misma referencia html').to.eq(true);
      expect(win.performance.timeOrigin, 'timeOrigin no cambió (no hay documento nuevo)').to.eq(
        notas.timeOriginAntes
      );
    });

    cy.url().then((url) => {
      expect(url, '191 no login').to.not.include('/login');
      expect(url, '191 misma ruta funcional').to.include('/configuracion');
      expect(notas.urlAntes190, 'URL previa 190').to.include('/configuracion');
    });
    cy.get('html').should('have.attr', 'lang', 'en-US');
    cy.contains('h2', /^Language$/).should('be.visible');
    cy.contains('button', /^Save language$/).should('exist');
    cy.contains('div', /^My preference$/).should('be.visible');
    cy.get('@login.all').then((calls) => {
      expect(calls.length, '191 sin segundo login').to.eq(1);
    });

    notas.resultado191 = 'APROBADO';
    registrarPaso('TC-M09-191 APROBADO: cambio visible en el mismo document, sin reload/logout');
    cy.screenshot('G99-05-sin-recarga');
  });

  after(function () {
    const localeOriginal = notas.localeOriginal;
    const puedeRestaurar = Boolean(token && localeOriginal);

    if (puedeRestaurar) {
      registrarPaso(`Restaurar locale original ${localeOriginal} vía PATCH personal`);
      cy.request({
        method: 'PATCH',
        url: `${DEV_API}/configuracion/personalizacion/idioma`,
        headers: { Authorization: `Bearer ${token}` },
        body: {
          locale_code: localeOriginal,
          version_perfil: versionPerfilActual,
        },
        failOnStatusCode: false,
      }).then((res) => {
        const patchOk = res.status === 200;
        registrarPaso(`PATCH restaurar status=${res.status}`);
        cy.request({
          method: 'GET',
          url: `${DEV_API}/configuracion/personalizacion/idioma`,
          headers: { Authorization: `Bearer ${token}` },
          failOnStatusCode: false,
        }).then((getRes) => {
          const body = cuerpoSinSecretos(getRes.body);
          notas.getIdiomaFinal = { status: getRes.status, body };
          if (!patchOk || getRes.status !== 200 || !body || body.locale_code !== localeOriginal) {
            notas.restauracion = `FALLIDA patch=${res.status} get=${getRes.status} locale=${
              body && body.locale_code
            }`;
            registrarPaso(`Restauración fallida: ${notas.restauracion}`);
          } else {
            notas.restauracion = `OK locale_code=${body.locale_code}`;
            registrarPaso(`Restauración OK locale_code=${body.locale_code}`);
          }
        });
      });
    } else {
      notas.restauracion = 'NO APLICA: no hubo token o GET inicial';
    }

    cy.then(() => {
      const r189 = notas.resultado189;
      const r190 = notas.resultado190;
      const r191 = notas.resultado191;
      if (!flujoListo) {
        notas.clasificacion = 'BLOQUEADO';
        if (notas.resultado189 === 'PENDIENTE') notas.resultado189 = 'BLOQUEADO';
        if (notas.resultado190 === 'PENDIENTE') notas.resultado190 = 'BLOQUEADO';
        if (notas.resultado191 === 'PENDIENTE') notas.resultado191 = 'BLOQUEADO';
        if (!notas.error) {
          notas.error =
            'No se alcanzó el panel de idioma autenticado (sesión/refresh u otra precondición).';
        }
      } else if (notas.clasificacion === 'BLOQUEADO') {
        // ya clasificado
      } else if (r189 === 'APROBADO' && r190 === 'APROBADO' && r191 === 'APROBADO') {
        notas.clasificacion = 'APROBADO';
      } else if (r189 === 'BLOQUEADO' || r190 === 'BLOQUEADO' || r191 === 'BLOQUEADO') {
        notas.clasificacion = 'BLOQUEADO';
      } else {
        notas.clasificacion = 'RECHAZADO';
      }
      if (notas.restauracion && String(notas.restauracion).startsWith('FALLIDA')) {
        registrarPaso('RF-29 pudo ejecutarse pero la restauración quedó pendiente/fallida');
      }
      escribirNotas();
    });
  });
});
