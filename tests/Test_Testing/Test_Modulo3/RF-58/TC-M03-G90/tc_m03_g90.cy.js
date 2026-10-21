// Conserva el prefijo de despliegue /sigab-test en cada navegaci?n directa.
const urlFrontendQA = (ruta) => `${String(Cypress.config('baseUrl') || '').replace(/\/+$/, '')}${ruta}`;

// Solo ejecutable desde el runner después de demostrar SIN_SEÑAL aislado.
const env = (k) => Cypress.env(k);
const API = String(env('API_BASE') || '').replace(/\/+$/, '');
const RUN = env('RUN_ID');
const nombre = (k) => env(`SENSOR_${k}_NOMBRE`);
let cola = Promise.resolve();
const fuera = [];

function instalarSandbox() {
  cy.intercept({ url: `${API}/**` }, (req) => {
    let liberar;
    const turno = cola;
    cola = new Promise((resolve) => { liberar = resolve; });
    return turno.then(() => {
      req.headers['X-Test-Run-Id'] = RUN;
      req.headers['X-Sandbox-Secret'] = env('SANDBOX_SECRET');
      req.continue((res) => {
        if (req.method !== 'OPTIONS' && res.headers['x-test-run-id'] !== RUN) fuera.push(req.url);
        liberar();
      });
    });
  });
  cy.intercept({ method: 'GET', url: `${API}/iot/monitoreo/dashboard*` }).as('dashboard');
}

function tarjeta(k) { return cy.contains('button.ds-option', nombre(k), { timeout: 20000 }); }
function ingresar() {
  cy.visit(urlFrontendQA('/login'), { onBeforeLoad(win) {
    if (win.indexedDB?.databases) win.indexedDB.databases().then((dbs) => dbs.forEach((d) => d.name && win.indexedDB.deleteDatabase(d.name)));
  } });
  cy.get('input[type="email"]').type(env('PROD_EMAIL'), { log: false });
  cy.get('input[type="password"]').type(env('PROD_PASSWORD'), { log: false });
  cy.get('button[type="submit"]').click();
  cy.visit(urlFrontendQA('/telemetria/monitoreo'));
  cy.wait('@dashboard').then((i) => {
    expect(i.response?.statusCode).to.eq(200);
    expect(i.response?.headers['x-test-run-id']).to.eq(RUN);
  });
  cy.get('input[type="number"]').first().clear().type(String(env('ID_INFRA')));
  cy.wait('@dashboard');
}

describe('TC-M03-G90 — sensor sin señal', () => {
  before(() => {
    if (env('AUTORIZADO_RUN') !== 'SI' || !RUN || !/^https:\/\//.test(API)) throw new Error('BLOQUEO_G90');
    instalarSandbox();
    ingresar();
  });

  it('[TC-M03-175][ASSERT][UI-175-01] conserva sensor, último valor y alerta crítica', () => {
    tarjeta('175').should('be.visible').within(() => {
      cy.get('[role="img"][aria-label]').should('have.attr', 'aria-label').and('include', '25');
      cy.get('[aria-label]').filter((_, el) => /alerta/i.test(el.getAttribute('aria-label') || '')).should('exist');
    });
    tarjeta('175').click();
    cy.get('[role="dialog"]').should('contain.text', 'Crítico').and('contain.text', '25').screenshot('TC-M03-175_sin_senal_con_alerta');
    cy.get('[role="dialog"]').invoke('text').should('match', /hace\s+\d+\s+min/i);
    cy.get('[role="dialog"] button[aria-label]').first().click();
    cy.then(() => expect(fuera, 'solicitudes fuera de sandbox').to.have.length(0));
  });

  it('[TC-M03-176][ASSERT][UI-176-01] tarjeta gris conserva último valor y marca desactualizado', () => {
    tarjeta('176').should('be.visible').within(() => {
      cy.get('[role="img"][aria-label]').should('have.attr', 'aria-label').and('include', '25');
      cy.contains('desactualizado').should('be.visible');
      cy.contains('Sin señal').should('be.visible');
    });
    tarjeta('176').screenshot('TC-M03-176_gris_ultimo_valor').click();
    cy.get('[role="dialog"]').should('contain.text', '25').invoke('text').should('match', /hace\s+\d+\s+min/i);
    cy.then(() => expect(fuera, 'solicitudes fuera de sandbox').to.have.length(0));
  });
});
