// Conserva el prefijo de despliegue /sigab-test en cada navegaci?n directa.
const urlFrontendQA = (ruta) => `${String(Cypress.config('baseUrl') || '').replace(/\/+$/, '')}${ruta}`;

// Peticiones y contenido siempre reales; solo se añaden cabeceras de aislamiento.
const API = String(Cypress.env('API_BASE') || '').replace(/\/+$/, '');
const RUN = Cypress.env('RUN_ID');
const etiquetas = { VERDE: 'Normal', AMARILLO: 'Advertencia', ROJO: 'Fuera de rango', GRIS: 'Sin señal' };
const fuera = [];
let cola = Promise.resolve();
function instalar() {
  cy.intercept({ url: `${API}/**` }, req => {
    let liberar;
    const turno = cola;
    cola = new Promise(resolve => { liberar = resolve; });
    return turno.then(() => {
      req.headers['X-Test-Run-Id'] = RUN;
      req.headers['X-Sandbox-Secret'] = Cypress.env('SANDBOX_SECRET');
      req.continue(res => {
        if (req.method !== 'OPTIONS' && res.headers['x-test-run-id'] !== RUN) fuera.push(req.url);
        liberar();
      });
    });
  });
  cy.intercept({ method: 'GET', url: `${API}/iot/monitoreo/dashboard*` }).as('dashboard');
}
function aislarCanales(win) {
  const WS = win.WebSocket;
  if (WS) win.WebSocket = class extends WS { constructor(url, ...resto) { const u = new URL(String(url), win.location.href); if (!['localhost', '127.0.0.1'].includes(u.hostname)) { win.__qaPushSinSandbox = true; throw Error('PRE: WebSocket sin contrato de sandbox verificable'); } super(url, ...resto); } };
  const ES = win.EventSource;
  if (ES) win.EventSource = class extends ES { constructor(url, ...resto) { const u = new URL(String(url), win.location.href); if (!['localhost', '127.0.0.1'].includes(u.hostname)) { win.__qaPushSinSandbox = true; throw Error('PRE: EventSource sin contrato de sandbox verificable'); } super(url, ...resto); } };
}
function tarjeta() { return cy.contains('button.ds-option', Cypress.env('SENSOR_NOMBRE')); }
describe('TC-M03-G99 - integridad de monitoreo', () => {
  before(() => {
    if (Cypress.env('AUTORIZADO_RUN') !== 'SI' || Cypress.env('QA_AUTORIZADO') !== 'SI' || Cypress.env('AMBIENTE') !== 'TEST' || String(Cypress.env('AUTORIZACION') || '').length < 8 || !RUN || !/^https:\/\//.test(API) || API !== Cypress.env('API_TEST_BASE')) throw Error('BLOQUEO_G99');
    instalar();
    cy.visit(urlFrontendQA('/login'), { onBeforeLoad: aislarCanales });
    cy.get('input[type="email"]').type(Cypress.env('PROD_EMAIL'), { log: false });
    cy.get('input[type="password"]').type(Cypress.env('PROD_PASSWORD'), { log: false });
    cy.get('button[type="submit"]').click();
    cy.visit(urlFrontendQA('/telemetria/monitoreo'), { onBeforeLoad: aislarCanales });
    cy.wait('@dashboard').its('response.statusCode').should('eq', 200);
  });
  it('[TC-M03-192][ASSERT] navegación, filtro y consulta no hacen escrituras de telemetría', () => {
    cy.get('input[type="number"]').first().clear().type(String(Cypress.env('ID_INFRA')));
    cy.wait('@dashboard');
    tarjeta().should('be.visible').click();
    cy.get('[role="dialog"]').should('be.visible');
    cy.get('[role="dialog"] button[aria-label]').first().click();
    cy.get('button[aria-label]').filter((_, e) => /refrescar/i.test(e.getAttribute('aria-label') || '')).first().click();
    cy.wait('@dashboard');
    cy.then(() => expect(fuera, 'solicitudes fuera del sandbox').to.have.length(0));
  });
  it('[TC-M03-193][ASSERT] el estado renderizado coincide con el valor real recibido del backend', () => {
    cy.get('button[aria-label]').filter((_, e) => /refrescar/i.test(e.getAttribute('aria-label') || '')).first().click();
    cy.wait('@dashboard').then(i => {
      expect(i.response?.statusCode).to.eq(200);
      const s = (i.response?.body?.sensores || []).find(x => Number(x.id_sensor) === Number(Cypress.env('SENSOR_ID')));
      expect(s, 'sensor preparado en respuesta real').to.be.an('object');
      expect(Object.keys(etiquetas)).to.include(s.estado_semaforo);
      tarjeta().should('contain.text', etiquetas[s.estado_semaforo]);
    });
    cy.then(() => expect(fuera).to.have.length(0));
  });
});
