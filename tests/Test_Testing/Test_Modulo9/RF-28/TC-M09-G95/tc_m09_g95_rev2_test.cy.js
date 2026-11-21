/**
 * TC-M09-G95 / TC-M09-180 — rev2 TEST (RF-28).
 * Cypress. No se sobrescribe evidencia DEV.
 *
 * UI real del bundle TEST: clic catálogo + clic celda (no HTML5 drag).
 * Usuario: contador@pecuaria.co — GET layout 200 (default de rol, sin fila personal).
 * No usar admin/productor: GET layout 500 por JSON legado (fila/columna/span).
 */
const TEST_FRONT = 'https://sigab-frontendtest-6aqrny-d2b730-158-69-200-27.sslip.io';
const TEST_API = 'https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test';
const EVIDENCIA = 'tests/Test_Testing/Test_Modulo9/RF-28/TC-M09-G95/Resultados';

const GET_LAYOUT = /\/configuracion\/personalizacion\/dashboard\/?$/;
const PATCH_LAYOUT = /\/configuracion\/personalizacion\/dashboard\/?$/;
const GET_WIDGETS = /\/configuracion\/personalizacion\/dashboard\/widgets\/?$/;
const POST_RESTAURAR = /\/configuracion\/personalizacion\/dashboard\/restaurar\/?$/;
const POST_REFRESH = /\/sesiones\/refresh\/?$/;
const POST_LOGIN = /\/sesiones\/?$/;
const GET_CONTEXTO = /\/configuracion\/interfaz\/contexto\/?$/;

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
    url: interception.request.url,
    status: interception.response ? interception.response.statusCode : null,
    requestBody: cuerpoSinSecretos(interception.request.body || null),
    responseBody: cuerpoSinSecretos(interception.response ? interception.response.body : null),
  };
}

function firmaVisible(layout) {
  return (layout.grid || [])
    .filter((w) => w.visible)
    .map((w) => `${w.id_widget}@${w.posicion_fila},${w.posicion_columna},span${w.span_columnas}`)
    .sort();
}

describe('TC-M09-G95 rev2 TEST - Personalización del dashboard con widgets válidos', () => {
  const notas = {
    fecha: new Date().toISOString(),
    ambiente: 'TEST',
    caso: 'TC-M09-180',
    usuario: null,
    rol: 'Contador',
    clasificacion: 'PENDIENTE',
    pasos: [],
    loginHttp: null,
    refreshLlamadas: [],
    getContexto: null,
    getLayout: null,
    getWidgets: null,
    patchGuardar: null,
    patchRestaurar: null,
    postRestaurarUi: null,
    layoutInicial: null,
    layoutTrasColocar: null,
    layoutTrasRestaurar: null,
    widgetColocado: null,
    widgetId: null,
    celdaUsada: null,
    urlAntesAccion: null,
    urlDespuesAccion: null,
    navTypeAntes: null,
    navTypeDespues: null,
    markerAntes: null,
    recargaDetectada: null,
    restauracion: null,
    error: null,
  };

  let tokenSesion = null;
  let snapshotInicial = null;
  let sePersisted = false;

  function registrarPaso(texto) {
    notas.pasos.push(texto);
    cy.log(texto);
  }

  function escribirNotas() {
    cy.writeFile(`${EVIDENCIA}/G95-rev2-test-ejecucion.txt`, [
      'TC-M09-G95 / TC-M09-180 — ejecución rev2 TEST',
      `Fecha: ${notas.fecha}`,
      `Ambiente: ${notas.ambiente}`,
      `Frontend: ${TEST_FRONT}`,
      `API: ${TEST_API}`,
      `Usuario: ${notas.usuario || 'no registrado'}`,
      `Rol: ${notas.rol}`,
      `Resultado general: ${notas.clasificacion}`,
      '',
      'Pasos:',
      ...notas.pasos.map((p, i) => `${i + 1}. ${p}`),
      '',
      `Login HTTP: ${notas.loginHttp}`,
      `Refresh llamadas: ${JSON.stringify(notas.refreshLlamadas, null, 2)}`,
      `GET contexto: ${JSON.stringify(notas.getContexto, null, 2)}`,
      `GET layout: ${JSON.stringify(notas.getLayout, null, 2)}`,
      `GET widgets: ${JSON.stringify(notas.getWidgets, null, 2)}`,
      `PATCH guardar: ${JSON.stringify(notas.patchGuardar, null, 2)}`,
      `PATCH restaurar snapshot: ${JSON.stringify(notas.patchRestaurar, null, 2)}`,
      `POST restaurar: ${JSON.stringify(notas.postRestaurarUi, null, 2)}`,
      '',
      `Distribución inicial: ${JSON.stringify(notas.layoutInicial, null, 2)}`,
      `Widget colocado: ${notas.widgetColocado} id=${notas.widgetId}`,
      `Celda usada: ${notas.celdaUsada}`,
      `Distribución tras colocar: ${JSON.stringify(notas.layoutTrasColocar, null, 2)}`,
      `Distribución tras restaurar: ${JSON.stringify(notas.layoutTrasRestaurar, null, 2)}`,
      `Restauración: ${notas.restauracion}`,
      `URL antes de acción: ${notas.urlAntesAccion}`,
      `URL después de acción: ${notas.urlDespuesAccion}`,
      `performance.navigation.type antes: ${notas.navTypeAntes}`,
      `performance.navigation.type después: ${notas.navTypeDespues}`,
      `Recarga completa detectada: ${notas.recargaDetectada}`,
      '',
      `Error: ${notas.error || 'ninguno'}`,
      '',
      'Herramienta: Cypress 14 (no Playwright). Interacción: clic catálogo + clic celda.',
      'No se incluye password, JWT ni cookies.',
    ].join('\n'));
  }

  function fallar(clasificacion, mensaje) {
    notas.clasificacion = clasificacion;
    notas.error = mensaje;
    escribirNotas();
    cy.then(() => {
      throw new Error(`${clasificacion}: ${mensaje}`);
    });
  }

  function restaurarSiAplica() {
    if (!sePersisted || !tokenSesion || !snapshotInicial) {
      return;
    }
    if (notas.layoutTrasRestaurar) {
      return;
    }
    cy.request({
      method: 'PATCH',
      url: `${TEST_API}/configuracion/personalizacion/dashboard`,
      headers: { Authorization: `Bearer ${tokenSesion}` },
      body: {
        layout_config: snapshotInicial.grid,
        active_widget: snapshotInicial.active_widget,
        version_perfil: snapshotInicial.version_perfil,
      },
      failOnStatusCode: false,
    }).then((resp) => {
      notas.patchRestaurar = {
        method: 'PATCH',
        url: `${TEST_API}/configuracion/personalizacion/dashboard`,
        status: resp.status,
        requestBody: {
          layout_config: snapshotInicial.grid,
          active_widget: snapshotInicial.active_widget,
          version_perfil: snapshotInicial.version_perfil,
        },
        responseBody: cuerpoSinSecretos(resp.body),
      };
      registrarPaso(`PATCH restaurar snapshot HTTP ${resp.status}`);
      if (resp.status !== 200) {
        notas.restauracion = `FALLO HTTP ${resp.status}`;
        return;
      }
      notas.layoutTrasRestaurar = cuerpoSinSecretos(resp.body);
      const idsInicial = firmaVisible(snapshotInicial);
      const idsRestaurados = firmaVisible(resp.body);
      if (JSON.stringify(idsInicial) !== JSON.stringify(idsRestaurados)) {
        notas.restauracion = 'NO coincidió con la distribución inicial';
      } else {
        notas.restauracion =
          'OK: misma grilla visible. Nota: GET inicial tenía id_dashboard_layout=null; tras PATCH queda fila personal del usuario.';
      }
    });
  }

  it('TC-M09-180 - Personalización del dashboard con widgets válidos (TEST)', function () {
    const correo = Cypress.env('correo') || 'contador@pecuaria.co';
    const contrasena = Cypress.env('contrasena');
    expect(contrasena, 'contrasena via Cypress.env (no hardcodear)').to.be.a('string').and.not.empty;
    notas.usuario = correo;

    cy.intercept({ method: 'POST', url: POST_LOGIN }).as('login');
    cy.intercept({ method: 'POST', url: POST_REFRESH }).as('refreshSesion');
    cy.intercept({ method: 'GET', url: GET_LAYOUT }).as('getLayout');
    cy.intercept({ method: 'PATCH', url: PATCH_LAYOUT }).as('patchLayout');
    cy.intercept({ method: 'GET', url: GET_WIDGETS }).as('getWidgets');
    cy.intercept({ method: 'POST', url: POST_RESTAURAR }).as('postRestaurar');
    cy.intercept({ method: 'GET', url: GET_CONTEXTO }).as('getContexto');

    registrarPaso('Abrir login TEST');
    cy.visit(`${TEST_FRONT}/login`);
    cy.get('input[type="email"]').should('be.visible').clear().type(correo);
    cy.get('input[type="password"]').should('be.visible').clear().type(contrasena, { log: false });
    cy.get('button[type="submit"]').contains(/ingresar/i).click();

    cy.wait('@login').then((interception) => {
      const status = interception.response && interception.response.statusCode;
      notas.loginHttp = status;
      registrarPaso(`Login POST /sesiones status=${status}`);
      if (status === 401) {
        fallar('BLOQUEADO', 'Login HTTP 401. Un solo intento; no se reintenta.');
      }
      expect(status, 'login HTTP').to.eq(200);
      const body = interception.response.body || {};
      tokenSesion = body.token || (body.data && body.data.token) || null;
      notas.pasos.push(`token de sesión presente=${Boolean(tokenSesion)} (no se registra el valor)`);
    });

    cy.url({ timeout: 20000 }).should('include', '/dashboard');
    cy.url().should('not.include', '/login');
    registrarPaso('Dashboard accesible');
    cy.screenshot('G95-01-dashboard');

    registrarPaso('Ir a /configuracion (misma navegación que G90/G95 DEV, para observar refresh)');
    cy.intercept({ method: 'POST', url: POST_REFRESH }).as('refreshSesion');
    cy.visit(`${TEST_FRONT}/configuracion`);
    cy.wait(2000);

    cy.url({ timeout: 20000 }).then((url) => {
      if (url.includes('/login')) {
        fallar('BLOQUEADO', `Tras Configuración la URL volvió a /login (${url}).`);
      }
    });

    cy.get('@refreshSesion.all').then((calls) => {
      notas.refreshLlamadas = (calls || []).map((c) => ({
        status: c.response && c.response.statusCode,
        url: c.request && c.request.url,
        momento: 'tras-navegacion-configuracion',
        requestBodyKeys: c.request && c.request.body ? Object.keys(c.request.body) : [],
      }));
      registrarPaso(`POST /sesiones/refresh n=${notas.refreshLlamadas.length} ${JSON.stringify(notas.refreshLlamadas)}`);
      const fail500 = notas.refreshLlamadas.find((x) => x.status === 500);
      if (fail500) {
        registrarPaso('POST /sesiones/refresh HTTP 500 observado; no se clasifica RF-28 aún');
      }
    });
    cy.url().then((url) => {
      if (url.includes('/login')) {
        fallar(
          'ERROR DE AMBIENTE',
          `Sesión perdida (URL ${url}) tras Configuración. Refresh=${JSON.stringify(notas.refreshLlamadas)}`
        );
      }
    });

    cy.get('@getContexto.all').then((calls) => {
      if (calls && calls.length) {
        notas.getContexto = resumenIntercept(calls[calls.length - 1]);
      }
    });

    cy.contains('h1, h2, button', /Configuración/i, { timeout: 15000 }).should('exist');
    cy.contains('button', /^Personalización$/i).click({ force: true });
    registrarPaso('Pestaña Personalización; desplazar hasta Dashboard Personalizable');
    cy.contains(/Dashboard Personalizable/i, { timeout: 20000 }).scrollIntoView();
    cy.contains('h2', /Dashboard Personalizable/i).should('be.visible');
    cy.contains('h2', /Dashboard Personalizable/i, { timeout: 15000 }).should('exist');
    cy.contains(/Grilla del dashboard \(4 columnas × 3 filas\)/i).should('exist');
    cy.contains(/Catálogo de Widgets/i).should('exist');

    cy.wait(['@getLayout', '@getWidgets'], { timeout: 20000 });
    cy.get('@getLayout.all').then((calls) => {
      const interception = calls[calls.length - 1];
      notas.getLayout = resumenIntercept(interception);
      const status = notas.getLayout.status;
      registrarPaso(`GET /configuracion/personalizacion/dashboard status=${status} (última de ${calls.length})`);
      if (status !== 200) {
        fallar('RECHAZADO', `GET layout HTTP ${status}. Distribución inicial no disponible.`);
      }
      notas.layoutInicial = cuerpoSinSecretos(interception.response.body);
      snapshotInicial = interception.response.body;
    });
    cy.get('@getWidgets.all').then((calls) => {
      const interception = calls[calls.length - 1];
      notas.getWidgets = resumenIntercept(interception);
      const status = notas.getWidgets.status;
      registrarPaso(`GET widgets status=${status} (última de ${calls.length})`);
      if (status !== 200) {
        fallar('BLOQUEADO', `GET catálogo widgets HTTP ${status}.`);
      }
      const lista = interception.response.body;
      if (!Array.isArray(lista) || lista.length === 0) {
        fallar('BLOQUEADO', 'El catálogo de widgets del ambiente está vacío.');
      }
    });

    cy.screenshot('G95-02-personalizacion-inicial');

    cy.get('body').then(($body) => {
      const celdasVacias = [...$body.find('button[aria-label^="Celda vacía"], button[aria-label^="Colocar "]')];
      const celdasOcupadas = [...$body.find('button[aria-label^="Quitar "]')];
      registrarPaso(`Grilla: vacías=${celdasVacias.length} ocupadas=${celdasOcupadas.length}`);

      const catalogo = notas.getWidgets.responseBody || [];
      const visibles = (notas.layoutInicial.grid || []).filter((w) => w.visible);
      const idsEnGrid = visibles.map((w) => w.id_widget);
      let candidato = catalogo.find((w) => !idsEnGrid.includes(w.id_widget));
      if (!candidato && catalogo.length) {
        candidato = catalogo.find((w) => w.clave === 'hist_hum') || catalogo[catalogo.length - 1];
        registrarPaso(
          `Catálogo ya está en la grilla; se reubica widget válido ${candidato.nombre} (id=${candidato.id_widget}) a celda vacía`
        );
      }
      if (!candidato) {
        fallar('BLOQUEADO', 'No hay widget válido en el catálogo.');
      }
      notas.widgetColocado = candidato.nombre;
      notas.widgetId = candidato.id_widget;

      if (idsEnGrid.includes(candidato.id_widget)) {
        const ariaQuitar = `Quitar ${candidato.nombre}`;
        const btn = [...$body.find(`button[aria-label="${ariaQuitar}"]`)][0];
        if (!btn) {
          fallar('ERROR DE PRUEBA', `No se encontró ${ariaQuitar} para liberar y reubicar.`);
        }
        cy.wrap(btn).click({ force: true });
        registrarPaso(`Liberar posición actual: ${ariaQuitar}`);
      }
    });

    cy.window().then((win) => {
      win.__g95DocMarker = 'tc-m09-180-rev2';
      notas.markerAntes = win.__g95DocMarker;
      const nav = win.performance.getEntriesByType('navigation')[0];
      notas.navTypeAntes = nav ? nav.type : String(win.performance.navigation && win.performance.navigation.type);
    });
    cy.url().then((url) => {
      notas.urlAntesAccion = url;
    });

    cy.then(() => {
      const nombre = notas.widgetColocado;
      registrarPaso(`Seleccionar widget del catálogo: ${nombre}`);
      cy.get('button[type="button"]')
        .filter((_, el) => !el.getAttribute('aria-label') && el.innerText.includes(nombre))
        .filter(':visible')
        .first()
        .should('not.be.disabled')
        .click({ force: true });
      cy.contains(/Widget seleccionado:/i, { timeout: 10000 }).should('exist');
    });

    cy.get('button[aria-label^="Celda vacía"], button[aria-label^="Colocar "]')
      .filter(':visible')
      .then(($btns) => {
        const dest =
          [...$btns].find((el) => /fila 2 columna 1/i.test(el.getAttribute('aria-label') || '')) ||
          $btns.get(2) ||
          $btns.get(0);
        const aria = dest.getAttribute('aria-label');
        notas.celdaUsada = aria;
        registrarPaso(`Colocar en celda índice destino: ${aria} (evitar el hueco original de F1)`);
        cy.wrap(dest).click({ force: true });
      });

    cy.then(() => {
      const nombre = notas.widgetColocado;
      cy.get(`button[aria-label="Quitar ${nombre}"]`, { timeout: 10000 }).should('exist');
      registrarPaso(`La grilla muestra Quitar ${nombre} sin recargar`);
    });

    registrarPaso('Guardar configuración → PATCH');
    cy.contains('button', /^Guardar configuración$/i).click({ force: true });
    cy.wait('@patchLayout', { timeout: 20000 }).then((interception) => {
      notas.patchGuardar = resumenIntercept(interception);
      const status = notas.patchGuardar.status;
      registrarPaso(`PATCH /configuracion/personalizacion/dashboard status=${status}`);
      expect(status, 'PATCH guardar layout').to.be.oneOf([200, 201]);
      sePersisted = true;
      notas.layoutTrasColocar = cuerpoSinSecretos(interception.response.body);
      const idsAntes = firmaVisible(snapshotInicial);
      const idsDespues = firmaVisible(interception.response.body);
      expect(idsDespues, 'distribución cambió respecto al snapshot').to.not.deep.eq(idsAntes);
      const colocado = (interception.response.body.grid || []).find(
        (w) => w.id_widget === notas.widgetId && w.visible
      );
      expect(colocado, 'widget reubicado visible en respuesta PATCH').to.exist;
      expect(colocado.posicion_fila, 'fila destino 1–3').to.be.within(1, 3);
      expect(colocado.posicion_columna, 'columna destino 1–4').to.be.within(1, 4);
    });

    cy.contains(/El layout del dashboard se actualizó correctamente/i, { timeout: 10000 }).should('exist');
    cy.url().then((url) => {
      notas.urlDespuesAccion = url;
      expect(url, 'URL tras guardar').to.include('/configuracion');
      expect(url, 'no redirige a login').to.not.include('/login');
      expect(url, 'URL estable').to.eq(notas.urlAntesAccion);
    });
    cy.window().then((win) => {
      const nav = win.performance.getEntriesByType('navigation')[0];
      notas.navTypeDespues = nav ? nav.type : null;
      notas.recargaDetectada = win.__g95DocMarker !== 'tc-m09-180-rev2';
      expect(win.__g95DocMarker, 'mismo documento (sin recarga)').to.eq('tc-m09-180-rev2');
      expect(notas.navTypeDespues, 'navigation entry type no cambió a reload').to.eq(notas.navTypeAntes);
    });
    cy.screenshot('G95-03-tras-guardar');

    cy.get('@postRestaurar.all').then((calls) => {
      notas.postRestaurarUi = calls && calls.length ? calls.map(resumenIntercept) : { presente: false };
    });

    restaurarSiAplica();

    cy.then(() => {
      if (notas.restauracion && notas.restauracion.startsWith('NO')) {
        notas.clasificacion = 'RECHAZADO';
        fallar('RECHAZADO', notas.restauracion);
      }
      notas.clasificacion = 'APROBADO';
      registrarPaso('Camino feliz + restauración snapshot');
    });
    cy.screenshot('G95-04-tras-restaurar');
  });

  after(() => {
    restaurarSiAplica();
    cy.then(() => {
      escribirNotas();
    });
  });
});
