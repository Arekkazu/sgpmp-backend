/**
 * TC-M09-G99 rev2 TEST — RF-29 (189 es-CO, 190 en-US, 191 sin recarga).
 * Cypress. No sobrescribe evidencia DEV. Un login. Solo panel Mi preferencia.
 *
 * Restore: PATCH personal vía UI (misma sesión). Si after() con JWT de login
 * devolviera TOKEN_REVOCADO, se relogin solo para restaurar.
 */
const TEST_FRONT = 'https://sigab-frontendtest-6aqrny-d2b730-158-69-200-27.sslip.io';
const TEST_API = 'https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test';
const EVIDENCIA = 'tests/Test_Testing/Test_Modulo9/RF-29/TC-M09-G99/Resultados';

const GET_IDIOMA = /\/configuracion\/personalizacion\/idioma\/?(\?.*)?$/;
const PATCH_IDIOMA = /\/configuracion\/personalizacion\/idioma\/?(\?.*)?$/;
const PATCH_IDIOMA_GLOBAL = /\/configuracion\/personalizacion\/idioma\/global\/?$/;
const POST_REFRESH = /\/sesiones\/refresh\/?$/;
const POST_LOGIN = /\/sesiones\/?$/;
const GET_CONTEXTO = /\/configuracion\/interfaz\/contexto\/?$/;

const MARKER = `g99-rev2-${Date.now()}`;
const LS_LOCALE = 'sgpmp-locale';

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
      lower === 'jwt' ||
      lower === 'refresh'
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

describe('TC-M09-G99 rev2 TEST - Cambio de idioma de la interfaz', { testIsolation: false }, () => {
  const notas = {
    fecha: new Date().toISOString(),
    ambiente: 'TEST',
    usuario: null,
    rol: 'Productor',
    clasificacion: 'PENDIENTE',
    resultado189: 'PENDIENTE',
    resultado190: 'PENDIENTE',
    resultado191: 'PENDIENTE',
    pasos: [],
    logins: 0,
    loginHttp: null,
    refreshLlamadas: [],
    getIdiomaInicial: null,
    localeOriginal: null,
    versionPerfilOriginal: null,
    fuenteOriginal: null,
    idPreferenciaOriginal: null,
    patch189: null,
    patch190: null,
    patchRestaurar: null,
    patchGlobalCount: 0,
    textosIniciales: null,
    textosEs: null,
    textosEn: null,
    lang189: null,
    lang190: null,
    ls189: null,
    ls190: null,
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
    navTypeAntes: null,
    navTypeDespues: null,
    restauracion: null,
    getIdiomaFinal: null,
    error: null,
  };

  let token = null;
  let flujoListo = false;
  let versionPerfilActual = null;
  let restaurado = false;

  function registrarPaso(texto) {
    notas.pasos.push(texto);
    cy.log(texto);
  }

  function escribirNotas() {
    cy.writeFile(
      `${EVIDENCIA}/G99-rev2-test-ejecucion.txt`,
      [
        'TC-M09-G99 / RF-29 — ejecución rev2 TEST',
        `Fecha: ${notas.fecha}`,
        `Ambiente: ${notas.ambiente}`,
        `Frontend: ${TEST_FRONT}`,
        `API: ${TEST_API}`,
        `Usuario: ${notas.usuario || 'no registrado'}`,
        `Rol: ${notas.rol}`,
        `Resultado general: ${notas.clasificacion}`,
        `TC-M09-189: ${notas.resultado189}`,
        `TC-M09-190: ${notas.resultado190}`,
        `TC-M09-191: ${notas.resultado191}`,
        '',
        `Logins realizados: ${notas.logins}`,
        `Login HTTP: ${notas.loginHttp}`,
        `Refresh: ${JSON.stringify(notas.refreshLlamadas)}`,
        '',
        `Locale original: ${notas.localeOriginal}`,
        `fuente original: ${notas.fuenteOriginal}`,
        `version_perfil original: ${notas.versionPerfilOriginal}`,
        `id_preferencia_idioma original: ${notas.idPreferenciaOriginal}`,
        `GET idioma inicial: ${JSON.stringify(notas.getIdiomaInicial, null, 2)}`,
        `Textos iniciales: ${notas.textosIniciales}`,
        '',
        `PATCH es-CO (189): ${JSON.stringify(notas.patch189, null, 2)}`,
        `Textos ES observados: ${notas.textosEs}`,
        `html[lang] 189: ${notas.lang189}`,
        `localStorage ${LS_LOCALE} 189: ${notas.ls189}`,
        `URL 189: ${notas.url189}`,
        '',
        `PATCH en-US (190): ${JSON.stringify(notas.patch190, null, 2)}`,
        `Textos EN observados: ${notas.textosEn}`,
        `html[lang] 190: ${notas.lang190}`,
        `localStorage ${LS_LOCALE} 190: ${notas.ls190}`,
        `URL antes 190: ${notas.urlAntes190}`,
        `URL después 190: ${notas.urlDespues190}`,
        '',
        `Marcador esperado: ${notas.marker}`,
        `Marcador antes 190: ${notas.markerAntes190}`,
        `Marcador después 190: ${notas.markerDespues190}`,
        `document.documentElement misma referencia: ${notas.htmlRefIgual}`,
        `performance.timeOrigin antes: ${notas.timeOriginAntes}`,
        `performance.timeOrigin después: ${notas.timeOriginDespues}`,
        `navigation.type antes/después: ${notas.navTypeAntes} / ${notas.navTypeDespues}`,
        `PATCH idioma/global (debe ser 0): ${notas.patchGlobalCount}`,
        '',
        `PATCH restaurar UI: ${JSON.stringify(notas.patchRestaurar, null, 2)}`,
        `Restauración: ${notas.restauracion}`,
        `GET idioma final: ${JSON.stringify(notas.getIdiomaFinal, null, 2)}`,
        '',
        'Pasos:',
        ...notas.pasos.map((p, i) => `${i + 1}. ${p}`),
        '',
        `Error: ${notas.error || 'ninguno'}`,
        '',
        'Herramienta: Cypress 14 (no Playwright). Panel: Mi preferencia. Sin JWT/password.',
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

  function guardarPreferenciaPersonal(localeCode) {
    cy.contains('h2', /^(Idioma|Language)$/).scrollIntoView();
    cy.contains('div', /^(Mi preferencia|My preference)$/).scrollIntoView();
    if (localeCode === 'es-CO') {
      cy.contains('button', /Español|Spanish/i).scrollIntoView().click({ force: true });
      cy.contains(/Colombia/).should('exist');
    } else {
      cy.contains('button', /English|Inglés|Ingles/i).scrollIntoView().click({ force: true });
      cy.contains(/United States/).should('exist');
    }
    cy.contains('button', /^(Guardar idioma|Save language)$/)
      .scrollIntoView()
      .click({ force: true });
  }

  before(function () {
    const correo = Cypress.env('correo') || 'productor@pecuaria.co';
    const contrasena = Cypress.env('contrasena');
    expect(contrasena, 'contrasena via Cypress.env (no hardcodear)').to.be.a('string').and.not.empty;
    notas.usuario = correo;

    cy.intercept({ method: 'POST', url: POST_LOGIN }).as('login');
    cy.intercept({ method: 'POST', url: POST_REFRESH }).as('refreshSesion');
    cy.intercept({ method: 'GET', url: GET_IDIOMA }).as('getIdioma');
    cy.intercept({ method: 'PATCH', url: PATCH_IDIOMA }).as('patchIdioma');
    cy.intercept({ method: 'PATCH', url: PATCH_IDIOMA_GLOBAL }).as('patchIdiomaGlobal');
    cy.intercept({ method: 'GET', url: GET_CONTEXTO }).as('getContexto');

    registrarPaso('Abrir login TEST (único intento de escenario)');
    cy.visit(`${TEST_FRONT}/login`);
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
    });

    cy.url({ timeout: 20000 }).should('include', '/dashboard');
    cy.url().should('not.include', '/login');
    registrarPaso('Dashboard accesible');
    cy.screenshot('G99-01-dashboard');

    registrarPaso('Ir a /configuracion (observar refresh)');
    cy.intercept({ method: 'POST', url: POST_REFRESH }).as('refreshSesion');
    cy.visit(`${TEST_FRONT}/configuracion`);
    cy.wait(2000);
    cy.get('@refreshSesion.all').then((calls) => {
      notas.refreshLlamadas = (calls || []).map((c) => ({
        status: c.response && c.response.statusCode,
        url: c.request && c.request.url,
      }));
      registrarPaso(`POST /sesiones/refresh n=${notas.refreshLlamadas.length} ${JSON.stringify(notas.refreshLlamadas)}`);
    });
    cy.url().then((url) => {
      if (url.includes('/login')) {
        bloquear(
          `Tras /configuracion volvió a /login. Refresh=${JSON.stringify(notas.refreshLlamadas)}. No es veredicto RF-29.`
        );
      }
    });

    cy.contains('h1, h2, button', /Configuración|Settings/i, { timeout: 15000 }).should('exist');
    cy.contains('button', /^(Personalización|Personalization)$/i).click({ force: true });
    cy.contains(/Idioma|Language/i, { timeout: 15000 }).scrollIntoView();
    cy.contains('h2', /^(Idioma|Language)$/, { timeout: 15000 }).should('exist');

    cy.get('body').then(($body) => {
      if (!/Mi preferencia|My preference/.test($body.text())) {
        bloquear('No apareció Mi preferencia / My preference. No se usa Idioma global.');
      }
    });
    cy.document().then((doc) => {
      const texto = doc.body.innerText || '';
      notas.textosIniciales = {
        tieneIdioma: /Idioma/.test(texto),
        tieneLanguage: /\bLanguage\b/.test(texto),
        tieneMiPreferencia: /Mi preferencia/.test(texto),
        tieneMyPreference: /My preference/.test(texto),
        tieneBienvenido: /Bienvenido al sistema/.test(texto),
        tieneWelcome: /Welcome to the system/.test(texto),
        lang: doc.documentElement.getAttribute('lang'),
      };
    });

    cy.get('@getIdioma.all').then((calls) => {
      if (!calls || !calls.length) {
        bloquear('GET idioma no se emitió.');
        return;
      }
      const interception = calls[calls.length - 1];
      notas.getIdiomaInicial = resumenIntercept(interception);
      const status = notas.getIdiomaInicial.status;
      registrarPaso(`GET /configuracion/personalizacion/idioma status=${status}`);
      if (status === 401 || status === 403) {
        bloquear(`GET idioma HTTP ${status}. Permiso o sesión.`);
        return;
      }
      if (status !== 200) {
        bloquear(`GET idioma HTTP ${status}.`);
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
      const nav = win.performance.getEntriesByType('navigation')[0];
      notas.navTypeAntes = nav ? nav.type : null;
    });

    flujoListo = true;
    registrarPaso(`Marcador de documento creado: ${MARKER}`);
    cy.screenshot('G99-02-idioma-inicial');
  });

  beforeEach(function () {
    cy.intercept({ method: 'POST', url: POST_LOGIN }).as('login');
    cy.intercept({ method: 'POST', url: POST_REFRESH }).as('refreshSesion');
    cy.intercept({ method: 'GET', url: GET_IDIOMA }).as('getIdioma');
    cy.intercept({ method: 'PATCH', url: PATCH_IDIOMA }).as('patchIdioma');
    cy.intercept({ method: 'PATCH', url: PATCH_IDIOMA_GLOBAL }).as('patchIdiomaGlobal');
    cy.intercept({ method: 'GET', url: GET_CONTEXTO }).as('getContexto');
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
    cy.contains('h2', /^Idioma$/).scrollIntoView().should('exist');
    cy.contains('button', /^Guardar idioma$/).should('exist');
    cy.contains('div', /^Mi preferencia$/).should('exist');
    cy.contains('Bienvenido al sistema').should('exist');
    cy.contains('Panel principal').should('exist');
    cy.contains('Activos biológicos').should('exist');
    cy.contains('Mi perfil').should('exist');

    cy.url().then((url) => {
      notas.url189 = url;
      expect(url, '189 no va a login').to.not.include('/login');
      expect(url, '189 permanece en configuración').to.include('/configuracion');
    });
    cy.get('html').invoke('attr', 'lang').then((lang) => {
      notas.lang189 = lang;
    });
    cy.window().then((win) => {
      notas.ls189 = win.localStorage.getItem(LS_LOCALE);
      expect(notas.ls189, 'localStorage sgpmp-locale es-CO').to.eq('es-CO');
      expect(win.__g99DocumentMarker, '189 mismo documento').to.eq(MARKER);
    });
    cy.get('body').then(($body) => {
      notas.textosEs = [
        'Idioma',
        'Guardar idioma',
        'Mi preferencia',
        'Bienvenido al sistema',
        'Panel principal',
        'Activos biológicos',
        'Mi perfil',
      ]
        .filter((t) => $body.text().includes(t))
        .join(', ');
    });
    cy.get('@login.all').then((calls) => {
      expect(calls.length, 'un solo login').to.eq(1);
    });
    cy.get('@patchIdiomaGlobal.all').then((calls) => {
      notas.patchGlobalCount = calls.length;
      expect(calls.length, 'no se toca idioma global').to.eq(0);
      notas.resultado189 = 'APROBADO';
      registrarPaso('TC-M09-189 APROBADO');
    });
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
    cy.contains('h2', /^Language$/).scrollIntoView().should('exist');
    cy.contains('button', /^Save language$/).should('exist');
    cy.contains('div', /^My preference$/).should('exist');
    cy.contains('Welcome to the system').should('exist');
    cy.contains('Biological assets').should('exist');
    cy.contains('My profile').should('exist');
    cy.contains('Settings').should('exist');

    cy.url().then((url) => {
      notas.urlDespues190 = url;
      expect(url, '190 no va a login').to.not.include('/login');
      expect(url, '190 permanece en configuración').to.include('/configuracion');
      expect(url, '190 misma URL').to.eq(notas.urlAntes190);
    });
    cy.get('html').invoke('attr', 'lang').then((lang) => {
      notas.lang190 = lang;
    });
    cy.window().then((win) => {
      notas.ls190 = win.localStorage.getItem(LS_LOCALE);
      expect(notas.ls190, 'localStorage sgpmp-locale en-US').to.eq('en-US');
      notas.markerDespues190 = win.__g99DocumentMarker;
      notas.timeOriginDespues = win.performance.timeOrigin;
      notas.htmlRefIgual = win.document.documentElement === win.__g99HtmlRef;
      const nav = win.performance.getEntriesByType('navigation')[0];
      notas.navTypeDespues = nav ? nav.type : null;
      expect(win.__g99DocumentMarker, '190 mismo documento').to.eq(MARKER);
    });
    cy.get('body').then(($body) => {
      notas.textosEn = [
        'Language',
        'Save language',
        'My preference',
        'Welcome to the system',
        'Biological assets',
        'My profile',
        'Settings',
      ]
        .filter((t) => $body.text().includes(t))
        .join(', ');
    });
    cy.get('@login.all').then((calls) => {
      expect(calls.length, '190 sin nuevo POST /sesiones').to.eq(0);
    });
    cy.get('@patchIdiomaGlobal.all').then((calls) => {
      notas.patchGlobalCount = calls.length;
      expect(calls.length, 'no se toca idioma global').to.eq(0);
      notas.resultado190 = 'APROBADO';
      registrarPaso('TC-M09-190 APROBADO');
    });
    cy.screenshot('G99-04-en-US');
  });

  it('TC-M09-191 - Aplicar cambio de idioma sin recargar la sesión', function () {
    if (!flujoListo || notas.resultado189 !== 'APROBADO' || notas.resultado190 !== 'APROBADO') {
      if (notas.resultado191 === 'PENDIENTE') notas.resultado191 = 'BLOQUEADO';
      this.skip();
    }

    registrarPaso('TC-M09-191: mismo documento tras es-CO → en-US (sin cy.visit ni logout)');

    cy.window().then((win) => {
      expect(win.__g99DocumentMarker, 'marcador idéntico').to.eq(MARKER);
      expect(notas.markerAntes190, 'marcador antes 190').to.eq(MARKER);
      expect(notas.markerDespues190, 'marcador después 190').to.eq(MARKER);
      expect(win.document.documentElement === win.__g99HtmlRef, 'misma referencia html').to.eq(true);
      expect(win.performance.timeOrigin, 'timeOrigin no cambió').to.eq(notas.timeOriginAntes);
      expect(notas.navTypeDespues, 'navigation.type estable').to.eq(notas.navTypeAntes);
    });

    cy.url().then((url) => {
      expect(url, '191 no login').to.not.include('/login');
      expect(url, '191 misma ruta').to.include('/configuracion');
      expect(url, '191 URL igual a antes de 190').to.eq(notas.urlAntes190);
    });
    cy.get('html').should('have.attr', 'lang', 'en-US');
    cy.contains('h2', /^Language$/).scrollIntoView().should('exist');
    cy.contains('button', /^Save language$/).should('exist');
    cy.contains('div', /^My preference$/).should('exist');
    cy.get('@login.all').then((calls) => {
      expect(calls.length, '191 sin nuevo POST /sesiones').to.eq(0);
      notas.resultado191 = 'APROBADO';
      registrarPaso('TC-M09-191 APROBADO: cambio visible en el mismo document, sin reload/logout');
    });
    cy.screenshot('G99-05-sin-recarga');

    registrarPaso(`Restaurar locale original ${notas.localeOriginal} vía UI (misma sesión)`);
    guardarPreferenciaPersonal(notas.localeOriginal);
    cy.wait('@patchIdioma', { timeout: 20000 }).then((interception) => {
      notas.patchRestaurar = resumenIntercept(interception);
      const status = notas.patchRestaurar.status;
      const res = (interception.response && interception.response.body) || {};
      registrarPaso(`PATCH restaurar UI status=${status} locale=${res.locale_code}`);
      expect(status, 'PATCH restaurar').to.eq(200);
      expect(res.locale_code, 'locale restaurado').to.eq(notas.localeOriginal);
      restaurado = true;
      notas.restauracion = `OK UI locale_code=${res.locale_code}`;
    });
    cy.get('html').should('have.attr', 'lang', notas.localeOriginal);
    cy.screenshot('G99-06-restaurado');
  });

  after(function () {
    function clasificarYEscribir() {
      const r189 = notas.resultado189;
      const r190 = notas.resultado190;
      const r191 = notas.resultado191;
      if (!flujoListo) {
        notas.clasificacion = 'BLOQUEADO';
        if (notas.resultado189 === 'PENDIENTE') notas.resultado189 = 'BLOQUEADO';
        if (notas.resultado190 === 'PENDIENTE') notas.resultado190 = 'BLOQUEADO';
        if (notas.resultado191 === 'PENDIENTE') notas.resultado191 = 'BLOQUEADO';
      } else if (notas.clasificacion === 'BLOQUEADO') {
        // ya clasificado
      } else if (r189 === 'APROBADO' && r190 === 'APROBADO' && r191 === 'APROBADO') {
        notas.clasificacion = 'APROBADO';
      } else if (r189 === 'BLOQUEADO' || r190 === 'BLOQUEADO' || r191 === 'BLOQUEADO') {
        notas.clasificacion = 'BLOQUEADO';
      } else {
        notas.clasificacion = 'RECHAZADO';
      }
      escribirNotas();
    }

    if (!restaurado && token && notas.localeOriginal) {
      registrarPaso('after(): intentar PATCH restaurar con JWT de login (puede TOKEN_REVOCADO)');
      cy.request({
        method: 'PATCH',
        url: `${TEST_API}/configuracion/personalizacion/idioma`,
        headers: { Authorization: `Bearer ${token}` },
        body: {
          locale_code: notas.localeOriginal,
          version_perfil: versionPerfilActual,
        },
        failOnStatusCode: false,
      }).then((res) => {
        registrarPaso(`after PATCH status=${res.status}`);
        if (res.status === 200) {
          restaurado = true;
          notas.restauracion = `OK after JWT locale_code=${res.body && res.body.locale_code}`;
          clasificarYEscribir();
          return;
        }
        if (res.status === 401) {
          registrarPaso('TOKEN_REVOCADO u 401: relogin solo para restaurar');
          const correo = Cypress.env('correo') || 'productor@pecuaria.co';
          const contrasena = Cypress.env('contrasena');
          cy.request({
            method: 'POST',
            url: `${TEST_API}/sesiones/`,
            body: { correo_electronico: correo, contrasena },
            failOnStatusCode: false,
          }).then((loginRes) => {
            notas.logins += 1;
            registrarPaso(`Login restauración HTTP ${loginRes.status} (logins=${notas.logins})`);
            const tok = loginRes.body && loginRes.body.token;
            if (loginRes.status !== 200 || !tok) {
              notas.restauracion = `FALLIDA relogin=${loginRes.status}`;
              clasificarYEscribir();
              return;
            }
            cy.request({
              method: 'PATCH',
              url: `${TEST_API}/configuracion/personalizacion/idioma`,
              headers: { Authorization: `Bearer ${tok}` },
              body: { locale_code: notas.localeOriginal, version_perfil: versionPerfilActual },
              failOnStatusCode: false,
            }).then((patchRes) => {
              cy.request({
                method: 'GET',
                url: `${TEST_API}/configuracion/personalizacion/idioma`,
                headers: { Authorization: `Bearer ${tok}` },
                failOnStatusCode: false,
              }).then((getRes) => {
                const body = cuerpoSinSecretos(getRes.body);
                notas.getIdiomaFinal = { status: getRes.status, body };
                if (patchRes.status === 200 && getRes.status === 200 && body.locale_code === notas.localeOriginal) {
                  notas.restauracion = `OK relogin locale_code=${body.locale_code}`;
                } else {
                  notas.restauracion = `FALLIDA patch=${patchRes.status} get=${getRes.status} locale=${
                    body && body.locale_code
                  }`;
                }
                clasificarYEscribir();
              });
            });
          });
          return;
        }
        notas.restauracion = `FALLIDA after HTTP ${res.status}`;
        clasificarYEscribir();
      });
      return;
    }

    clasificarYEscribir();
  });
});
