/**
 * TC-M09-G95 / TC-M09-180 — Personalización del dashboard con widgets válidos (RF-28).
 *
 * Capa: Cypress (el repo no tiene Playwright; la matriz cita Playwright).
 * Ambiente: DEV. No usar el baseUrl TEST de cypress.config.cjs.
 *
 * Mecanismo real en el bundle DEV (no es drag HTML5):
 *   1) clic en botón del catálogo → selecciona clave (toggle)
 *   2) clic en celda vacía → coloca el widget
 *   3) clic en celda ocupada → quita el widget
 *   4) "Guardar configuración" → PATCH /configuracion/personalizacion/dashboard
 *
 * Ejecutar:
 *   npx cypress run --spec tests/Test_Testing/Test_Modulo9/RF-28/TC-M09-G95/tc_m09_g95.cy.js --env correo=admin.dev@gmail.com,contrasena=***
 *
 * Un solo intento de login. Si HTTP 401, detener y clasificar BLOQUEADO.
 */
const DEV_FRONT = 'https://sigab-frontenddev-pbw0py-757e2f-158-69-200-27.sslip.io';
const EVIDENCIA = 'tests/Test_Testing/Test_Modulo9/RF-28/TC-M09-G95/Resultados';

const GET_LAYOUT = /\/configuracion\/personalizacion\/dashboard\/?$/;
const PATCH_LAYOUT = /\/configuracion\/personalizacion\/dashboard\/?$/;
const GET_WIDGETS = /\/configuracion\/personalizacion\/dashboard\/widgets\/?$/;
const POST_RESTAURAR = /\/configuracion\/personalizacion\/dashboard\/restaurar\/?$/;
const POST_REFRESH = /\/sesiones\/refresh\/?$/;
const POST_LOGIN = /\/sesiones\/?$/;

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
    url: interception.request.url,
    status: interception.response ? interception.response.statusCode : null,
    requestBody: cuerpoSinSecretos(interception.request.body || null),
    responseBody: cuerpoSinSecretos(interception.response ? interception.response.body : null),
  };
}

describe('TC-M09-G95 - Personalización del dashboard con widgets válidos', () => {
  const notas = {
    fecha: new Date().toISOString(),
    ambiente: 'DEV',
    caso: 'TC-M09-180',
    usuario: null,
    clasificacion: 'PENDIENTE',
    pasos: [],
    loginHttp: null,
    refreshHttp: null,
    getLayout: null,
    getWidgets: null,
    patchGuardar: null,
    patchRestaurar: null,
    postRestaurarUi: null,
    layoutInicial: null,
    layoutTrasColocar: null,
    layoutTrasRestaurar: null,
    widgetColocado: null,
    celdaUsada: null,
    documentoIdAntes: null,
    recargaDetectada: null,
    urlAntesGuardar: null,
    urlDespuesGuardar: null,
    restauracion: null,
    error: null,
  };

  function registrarPaso(texto) {
    notas.pasos.push(texto);
    cy.log(texto);
  }

  function escribirNotas() {
    cy.writeFile(`${EVIDENCIA}/G95-rev1-dev-ejecucion.txt`, [
      'TC-M09-G95 / TC-M09-180 — ejecución rev1 DEV',
      `Fecha: ${notas.fecha}`,
      `Ambiente: ${notas.ambiente}`,
      'Frontend: https://sigab-frontenddev-pbw0py-757e2f-158-69-200-27.sslip.io',
      'API: https://sigab-backenddev-jpuya4-ea3a74-158-69-200-27.sslip.io/api-sgpmp',
      `Usuario: ${notas.usuario || 'no registrado'}`,
      `Resultado general: ${notas.clasificacion}`,
      '',
      'Pasos:',
      ...notas.pasos.map((p, i) => `${i + 1}. ${p}`),
      '',
      `Login HTTP: ${notas.loginHttp}`,
      `Refresh HTTP (si ocurrió): ${notas.refreshHttp}`,
      `GET layout: ${JSON.stringify(notas.getLayout, null, 2)}`,
      `GET widgets: ${JSON.stringify(notas.getWidgets, null, 2)}`,
      `PATCH guardar: ${JSON.stringify(notas.patchGuardar, null, 2)}`,
      `PATCH restaurar distribución inicial: ${JSON.stringify(notas.patchRestaurar, null, 2)}`,
      `POST restaurar (no debe usarse para devolver el default del rol): ${JSON.stringify(notas.postRestaurarUi, null, 2)}`,
      '',
      `Distribución inicial: ${JSON.stringify(notas.layoutInicial, null, 2)}`,
      `Widget colocado: ${notas.widgetColocado}`,
      `Celda usada: ${notas.celdaUsada}`,
      `Distribución tras colocar: ${JSON.stringify(notas.layoutTrasColocar, null, 2)}`,
      `Distribución tras restaurar: ${JSON.stringify(notas.layoutTrasRestaurar, null, 2)}`,
      `Restauración: ${notas.restauracion}`,
      `URL antes de guardar: ${notas.urlAntesGuardar}`,
      `URL después de guardar: ${notas.urlDespuesGuardar}`,
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

  it('TC-M09-180 - Personalización del dashboard con widgets válidos (camino feliz)', function () {
    const correo = Cypress.env('correo') || 'admin.dev@gmail.com';
    const contrasena = Cypress.env('contrasena');
    expect(contrasena, 'contrasena via Cypress.env (no hardcodear)').to.be.a('string').and.not.empty;
    notas.usuario = correo;

    cy.intercept({ method: 'POST', url: POST_LOGIN }).as('login');
    cy.intercept({ method: 'POST', url: POST_REFRESH }).as('refreshSesion');
    cy.intercept({ method: 'GET', url: GET_LAYOUT }).as('getLayout');
    cy.intercept({ method: 'PATCH', url: PATCH_LAYOUT }).as('patchLayout');
    cy.intercept({ method: 'GET', url: GET_WIDGETS }).as('getWidgets');
    cy.intercept({ method: 'POST', url: POST_RESTAURAR }).as('postRestaurar');

    registrarPaso('Abrir login DEV');
    cy.visit(`${DEV_FRONT}/login`);
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
    });

    cy.url({ timeout: 20000 }).should('include', '/dashboard');
    cy.url().should('not.include', '/login');
    registrarPaso('Dashboard accesible');
    cy.screenshot('G95-01-dashboard');

    registrarPaso('Ir a Configuración (misma ruta observada en G88: /configuracion)');
    cy.visit(`${DEV_FRONT}/configuracion`);
    cy.url().then((url) => {
      if (url.includes('/login')) {
        fallar(
          'BLOQUEADO',
          `Tras visitar /configuracion la URL volvió a /login (${url}). Posible POST /sesiones/refresh fallido.`
        );
      }
    });
    cy.contains('h1, h2, button', /Configuración/i, { timeout: 15000 }).should('exist');
    cy.contains('button', /^Personalización$/i).click({ force: true });

    cy.get('body').then(($body) => {
      if (!/Dashboard Personalizable/i.test($body.text())) {
        fallar(
          'BLOQUEADO',
          'No apareció la sección Dashboard Personalizable tras Personalización. No se simula la UI.'
        );
      }
    });

    registrarPaso('Sección Dashboard Personalizable visible');
    cy.contains('h2', /Dashboard Personalizable/i, { timeout: 15000 }).should('exist');
    cy.contains(/Grilla del dashboard \(4 columnas × 3 filas\)/i).should('exist');
    cy.contains(/Catálogo de Widgets/i).should('exist');
    cy.contains(/Organiza los widgets en la grilla 4×3/i).should('exist');

    cy.wait('@getLayout', { timeout: 20000 }).then((interception) => {
      notas.getLayout = resumenIntercept(interception);
      const status = notas.getLayout.status;
      registrarPaso(`GET /configuracion/personalizacion/dashboard status=${status}`);
      if (status !== 200) {
        fallar('BLOQUEADO', `GET layout HTTP ${status}. No hay distribución inicial confiable.`);
      }
      notas.layoutInicial = cuerpoSinSecretos(interception.response.body);
    });

    cy.wait('@getWidgets', { timeout: 20000 }).then((interception) => {
      notas.getWidgets = resumenIntercept(interception);
      const status = notas.getWidgets.status;
      registrarPaso(`GET /configuracion/personalizacion/dashboard/widgets status=${status}`);
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
      const celdasVacias = [...$body.find('button[aria-label^="Celda vacía"]')];
      const celdasOcupadas = [...$body.find('button[aria-label^="Quitar "]')];
      registrarPaso(
        `Grilla visible: ${celdasVacias.length} celdas vacías, ${celdasOcupadas.length} ocupadas (span>1 no renderiza botón de ocupación)`
      );

      const idsEnGrid = (notas.layoutInicial.grid || [])
        .filter((w) => w.visible)
        .map((w) => w.id_widget);
      const catalogo = notas.getWidgets.responseBody || [];
      const candidato = catalogo.find((w) => !idsEnGrid.includes(w.id_widget));

      if (celdasVacias.length === 0 && celdasOcupadas.length === 0) {
        fallar('BLOQUEADO', 'No hay botones de celda con aria-label Celda vacía / Quitar.');
      }

      if (!candidato && celdasVacias.length === 0) {
        fallar(
          'BLOQUEADO',
          'No hay posición disponible ni widget del catálogo fuera de la grilla para colocar uno válido.'
        );
      }

      notas.widgetColocado = candidato ? candidato.nombre : null;

      if (celdasVacias.length === 0) {
        const ocupada = celdasOcupadas[0];
        const aria = ocupada.getAttribute('aria-label');
        registrarPaso(`Grilla llena: clic en ${aria} para liberar una posición (handler P quita)`);
        cy.wrap(ocupada).click({ force: true });
      }
    });

    cy.then(() => {
      const nombre = notas.widgetColocado;
      if (!nombre) {
        fallar('BLOQUEADO', 'No se eligió un widget válido del catálogo.');
      }
      registrarPaso(`Seleccionar widget del catálogo: ${nombre} (handler D, toggle de clave)`);
      cy.get('button[type="button"]')
        .filter((_, el) => !el.getAttribute('aria-label') && el.innerText.includes(nombre))
        .filter(':visible')
        .first()
        .should('not.be.disabled')
        .click({ force: true });

      cy.contains(/Widget seleccionado:/i, { timeout: 10000 }).should('exist');
      cy.contains(/Haz clic en una celda vacía de la grilla/i).should('exist');
    });

    cy.get('button[aria-label^="Celda vacía"], button[aria-label^="Colocar "]')
      .filter(':visible')
      .first()
      .then(($btn) => {
        const aria = $btn.attr('aria-label');
        notas.celdaUsada = aria;
        registrarPaso(`Colocar en celda: ${aria} (handler P)`);
        cy.wrap($btn).click({ force: true });
      });

    cy.then(() => {
      const nombre = notas.widgetColocado;
      cy.get(`button[aria-label="Quitar ${nombre}"]`, { timeout: 10000 }).should('exist');
      registrarPaso(`La grilla muestra Quitar ${nombre} sin recargar`);
    });

    cy.window().then((win) => {
      win.__g95DocMarker = 'tc-m09-180';
      notas.documentoIdAntes = win.__g95DocMarker;
    });
    cy.url().then((url) => {
      notas.urlAntesGuardar = url;
    });

    registrarPaso('Guardar configuración (handler B → PATCH)');
    cy.contains('button', /^Guardar configuración$/i).click({ force: true });
    cy.wait('@patchLayout', { timeout: 20000 }).then((interception) => {
      notas.patchGuardar = resumenIntercept(interception);
      const status = notas.patchGuardar.status;
      registrarPaso(`PATCH /configuracion/personalizacion/dashboard status=${status}`);
      expect(status, 'PATCH guardar layout').to.be.oneOf([200, 201]);
      notas.layoutTrasColocar = cuerpoSinSecretos(interception.response.body);
      const nombresActivos = (notas.layoutTrasColocar.active_widget || []).join(',');
      registrarPaso(`active_widget tras guardar: ${nombresActivos}`);
    });

    cy.contains(/El layout del dashboard se actualizó correctamente/i, { timeout: 10000 }).should('exist');
    cy.url().then((url) => {
      notas.urlDespuesGuardar = url;
      expect(url, 'URL tras guardar').to.include('/configuracion');
      expect(url, 'no redirige a login').to.not.include('/login');
    });
    cy.window().then((win) => {
      notas.recargaDetectada = win.__g95DocMarker !== 'tc-m09-180';
      expect(win.__g95DocMarker, 'mismo documento tras guardar (sin recarga)').to.eq('tc-m09-180');
    });
    cy.screenshot('G95-03-tras-guardar');

    registrarPaso('Restaurar distribución inicial: quitar el widget colocado y volver a guardar');
    cy.then(() => {
      const nombre = notas.widgetColocado;
      cy.get(`button[aria-label="Quitar ${nombre}"]`).click({ force: true });
    });
    cy.contains('button', /^Guardar configuración$/i).click({ force: true });
    cy.wait('@patchLayout', { timeout: 20000 }).then((interception) => {
      notas.patchRestaurar = resumenIntercept(interception);
      const status = notas.patchRestaurar.status;
      registrarPaso(`PATCH restaurar status=${status}`);
      expect(status, 'PATCH restaurar layout inicial').to.be.oneOf([200, 201]);
      notas.layoutTrasRestaurar = cuerpoSinSecretos(interception.response.body);

      const idsInicial = (notas.layoutInicial.grid || [])
        .filter((w) => w.visible)
        .map((w) => `${w.id_widget}@${w.posicion_fila},${w.posicion_columna}`)
        .sort();
      const idsRestaurados = (notas.layoutTrasRestaurar.grid || [])
        .filter((w) => w.visible)
        .map((w) => `${w.id_widget}@${w.posicion_fila},${w.posicion_columna}`)
        .sort();
      if (JSON.stringify(idsInicial) !== JSON.stringify(idsRestaurados)) {
        notas.restauracion = 'NO coincidió con la distribución inicial';
        notas.clasificacion = 'RECHAZADO';
        notas.error = `Restauración distinta. inicial=${idsInicial.join('|')} restaurado=${idsRestaurados.join('|')}`;
        escribirNotas();
        expect(idsRestaurados, 'distribución restaurada').to.deep.eq(idsInicial);
      } else {
        notas.restauracion = 'OK: misma grilla visible que al inicio';
      }
    });

    cy.get('@postRestaurar.all').then((calls) => {
      if (calls && calls.length) {
        notas.postRestaurarUi = calls.map(resumenIntercept);
        registrarPaso('POST /restaurar se disparó; no se usó como restauración exacta');
      } else {
        notas.postRestaurarUi = { presente: false };
      }
    });

    notas.clasificacion = 'APROBADO';
    registrarPaso('Validaciones de camino feliz completadas');
    cy.screenshot('G95-04-tras-restaurar');
  });

  after(() => {
    escribirNotas();
  });
});
